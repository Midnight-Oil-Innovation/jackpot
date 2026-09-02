"""P1 ``POST /api/v1/auth/refresh`` endpoint tests.

Covers the success path (cookie / body / both-with-cookie-winning),
each of the six error codes, the bulk-revoke side effect on replay,
the cookie attributes set on success, and the audit-log emission.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from backend.auth.oauth import _new_jti
from backend.config import get_settings
from backend.database import execute_query, execute_write

JWT_KEY = "test-jwt-signing-key"
ALGO = "HS256"


def _seed_user(email: str) -> int:
    execute_write(
        """
        INSERT INTO users (email, name, organization_id, is_active)
        VALUES (:e, 'P1 Refresh User', 1, TRUE)
        ON CONFLICT (email) DO UPDATE SET is_active = TRUE
        """,
        {"e": email},
    )
    return execute_query("SELECT id FROM users WHERE email = :e", {"e": email})[0]["id"]


def _delete_user(email: str) -> None:
    execute_write(
        "UPDATE audit_log SET actor_id = NULL WHERE actor_id IN "
        "(SELECT id FROM users WHERE email = :e)",
        {"e": email},
    )
    execute_write("DELETE FROM users WHERE email = :e", {"e": email})


def _make_refresh_jwt(
    *,
    user_id: int,
    jti: str,
    email: str = "refresh@test.com",
    exp_offset_seconds: int = 604800,
    token_type: str = "refresh",
    expired: bool = False,
) -> str:
    """Mint a JWT signed with the test key. ``expired=True`` overrides
    ``exp`` to a past timestamp."""
    now = datetime.now(UTC)
    exp = now - timedelta(seconds=60) if expired else now + timedelta(seconds=exp_offset_seconds)
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "iat": int(now.timestamp()),
            "exp": exp,
            "type": token_type,
            "jti": jti,
        },
        JWT_KEY,
        algorithm=ALGO,
    )


def _register_token(*, jti: str, user_id: int, expires_in_seconds: int = 604800) -> None:
    now = datetime.now(UTC)
    execute_write(
        """
        INSERT INTO refresh_tokens (jti, user_id, issued_at, expires_at)
        VALUES (:jti, :uid, :iat, :exp)
        """,
        {
            "jti": jti,
            "uid": user_id,
            "iat": now,
            "exp": now + timedelta(seconds=expires_in_seconds),
        },
    )


@pytest.mark.asyncio
async def test_refresh_from_cookie_succeeds(client):
    email = "refresh_cookie@test.com"
    user_id = _seed_user(email)
    old_jti = _new_jti()
    token = _make_refresh_jwt(user_id=user_id, jti=old_jti, email=email)
    _register_token(jti=old_jti, user_id=user_id)
    try:
        client.cookies.set("refresh", token)
        resp = await client.post("/api/v1/auth/refresh")
        client.cookies.clear()

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert isinstance(body["access_token"], str) and body["access_token"]
        assert body["expires_in"] == get_settings().access_token_lifetime_seconds

        # Old token is now revoked with reason='rotated' and points at the
        # new JTI; the new JTI is registered as an active row.
        old_row = execute_query("SELECT * FROM refresh_tokens WHERE jti = :j", {"j": old_jti})[0]
        assert old_row["revoked_reason"] == "rotated"
        assert old_row["revoked_at"] is not None
        assert old_row["replaced_by_jti"] is not None

        new_row = execute_query(
            "SELECT * FROM refresh_tokens WHERE jti = :j",
            {"j": old_row["replaced_by_jti"]},
        )[0]
        assert new_row["revoked_at"] is None
        assert new_row["user_id"] == user_id
    finally:
        _delete_user(email)


@pytest.mark.asyncio
async def test_refresh_from_body_succeeds(client):
    email = "refresh_body@test.com"
    user_id = _seed_user(email)
    old_jti = _new_jti()
    token = _make_refresh_jwt(user_id=user_id, jti=old_jti, email=email)
    _register_token(jti=old_jti, user_id=user_id)
    try:
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["token_type"] == "bearer"
        # Old token rotated.
        old_row = execute_query("SELECT * FROM refresh_tokens WHERE jti = :j", {"j": old_jti})[0]
        assert old_row["revoked_reason"] == "rotated"
    finally:
        _delete_user(email)


@pytest.mark.asyncio
async def test_refresh_cookie_wins_over_body(client):
    """When both cookie and body present, cookie wins (defense in depth
    against confused-deputy attacks)."""
    email = "refresh_priority@test.com"
    user_id = _seed_user(email)
    cookie_jti = _new_jti()
    body_jti = _new_jti()
    cookie_token = _make_refresh_jwt(user_id=user_id, jti=cookie_jti, email=email)
    body_token = _make_refresh_jwt(user_id=user_id, jti=body_jti, email=email)
    _register_token(jti=cookie_jti, user_id=user_id)
    _register_token(jti=body_jti, user_id=user_id)
    try:
        client.cookies.set("refresh", cookie_token)
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": body_token})
        client.cookies.clear()
        assert resp.status_code == 200, resp.text

        # Cookie's token rotated; body's token untouched.
        cookie_row = execute_query(
            "SELECT * FROM refresh_tokens WHERE jti = :j", {"j": cookie_jti}
        )[0]
        body_row = execute_query("SELECT * FROM refresh_tokens WHERE jti = :j", {"j": body_jti})[0]
        assert cookie_row["revoked_reason"] == "rotated"
        assert body_row["revoked_at"] is None
    finally:
        _delete_user(email)


@pytest.mark.asyncio
async def test_refresh_missing_token_returns_401(client):
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401
    detail = resp.json()["error"]["detail"]
    assert detail["error_code"] == "MISSING_REFRESH_TOKEN"


@pytest.mark.asyncio
async def test_refresh_malformed_jwt_returns_401(client):
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-jwt"})
    assert resp.status_code == 401
    detail = resp.json()["error"]["detail"]
    assert detail["error_code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.asyncio
async def test_refresh_expired_jwt_returns_401(client):
    """Even though the JTI is in the table, an expired JWT is rejected
    at decode time (jose's verify_exp default)."""
    email = "refresh_expired@test.com"
    user_id = _seed_user(email)
    jti = _new_jti()
    token = _make_refresh_jwt(user_id=user_id, jti=jti, email=email, expired=True)
    _register_token(jti=jti, user_id=user_id)
    try:
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert resp.status_code == 401
        assert resp.json()["error"]["detail"]["error_code"] == "INVALID_REFRESH_TOKEN"
    finally:
        _delete_user(email)


@pytest.mark.asyncio
async def test_refresh_wrong_token_type_returns_401(client):
    """Submitting an access token (type='access') hits the type guard
    BEFORE the table lookup."""
    email = "refresh_wrongtype@test.com"
    user_id = _seed_user(email)
    jti = _new_jti()
    token = _make_refresh_jwt(user_id=user_id, jti=jti, email=email, token_type="access")
    try:
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert resp.status_code == 401
        assert resp.json()["error"]["detail"]["error_code"] == "WRONG_TOKEN_TYPE"
    finally:
        _delete_user(email)


@pytest.mark.asyncio
async def test_refresh_token_not_tracked_returns_401(client):
    """Valid JWT (correct signature, not expired, type=refresh) but JTI
    is not in the table — pre-P1 token, or forged with a leaked key."""
    email = "refresh_untracked@test.com"
    user_id = _seed_user(email)
    jti = _new_jti()
    token = _make_refresh_jwt(user_id=user_id, jti=jti, email=email)
    # Deliberately do NOT register the JTI.
    try:
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert resp.status_code == 401
        assert resp.json()["error"]["detail"]["error_code"] == "TOKEN_NOT_TRACKED"
    finally:
        _delete_user(email)


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["logout", "admin_revoke"])
async def test_refresh_revoked_token_returns_401(client, reason):
    """A revoked-but-not-rotated token returns plain TOKEN_REVOKED, with
    the revoked_reason echoed back so clients can disambiguate."""
    email = f"refresh_revoked_{reason}@test.com"
    user_id = _seed_user(email)
    jti = _new_jti()
    token = _make_refresh_jwt(user_id=user_id, jti=jti, email=email)
    _register_token(jti=jti, user_id=user_id)
    execute_write(
        """
        UPDATE refresh_tokens
           SET revoked_at = NOW(), revoked_reason = :r
         WHERE jti = :j
        """,
        {"r": reason, "j": jti},
    )
    try:
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert resp.status_code == 401
        detail = resp.json()["error"]["detail"]
        assert detail["error_code"] == "TOKEN_REVOKED"
        assert detail["revoked_reason"] == reason
    finally:
        _delete_user(email)


@pytest.mark.asyncio
async def test_refresh_replay_detected_revokes_all_active(client):
    """Reusing a token already revoked with reason='rotated' is treated
    as an attack indicator: the endpoint revokes ALL of the user's
    currently-active refresh tokens, emits a TOKEN_REPLAY_DETECTED audit
    event, and returns the dedicated error code."""
    email = "refresh_replay@test.com"
    user_id = _seed_user(email)
    rotated_jti = _new_jti()
    other_active_jti_1 = _new_jti()
    other_active_jti_2 = _new_jti()
    rotated_token = _make_refresh_jwt(user_id=user_id, jti=rotated_jti, email=email)
    _register_token(jti=rotated_jti, user_id=user_id)
    _register_token(jti=other_active_jti_1, user_id=user_id)
    _register_token(jti=other_active_jti_2, user_id=user_id)
    # Mark the replayed token as already-rotated.
    execute_write(
        """
        UPDATE refresh_tokens
           SET revoked_at = NOW(), revoked_reason = 'rotated',
               replaced_by_jti = 'some-rotated-successor'
         WHERE jti = :j
        """,
        {"j": rotated_jti},
    )
    try:
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": rotated_token})
        assert resp.status_code == 401
        assert resp.json()["error"]["detail"]["error_code"] == "TOKEN_REPLAY_DETECTED"

        # All previously-active tokens for this user are now revoked
        # with reason='replay_detected'.
        for jti in (other_active_jti_1, other_active_jti_2):
            row = execute_query("SELECT * FROM refresh_tokens WHERE jti = :j", {"j": jti})[0]
            assert row["revoked_at"] is not None
            assert row["revoked_reason"] == "replay_detected"

        # AUTH_TOKEN_REPLAY_DETECTED audit event was emitted.
        audit_rows = execute_query(
            """
            SELECT * FROM audit_log
             WHERE action = 'AUTH_TOKEN_REPLAY_DETECTED'
               AND actor_id = :uid
             ORDER BY id DESC
             LIMIT 1
            """,
            {"uid": user_id},
        )
        assert audit_rows, "expected AUTH_TOKEN_REPLAY_DETECTED audit event"
        assert audit_rows[0]["resource_type"] == "refresh_token"
        assert audit_rows[0]["resource_id"] == rotated_jti
    finally:
        _delete_user(email)


@pytest.mark.asyncio
async def test_refresh_success_sets_cookies_with_correct_attributes(client):
    """Both ``access`` and ``refresh`` cookies must come back HttpOnly,
    Secure, SameSite=Lax, with Max-Age matching the configured lifetimes."""
    email = "refresh_cookies@test.com"
    user_id = _seed_user(email)
    jti = _new_jti()
    token = _make_refresh_jwt(user_id=user_id, jti=jti, email=email)
    _register_token(jti=jti, user_id=user_id)
    settings = get_settings()
    try:
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert resp.status_code == 200, resp.text

        set_cookie_headers = [h.lower() for h in resp.headers.get_list("set-cookie")]
        access_header = next(h for h in set_cookie_headers if h.startswith("access="))
        refresh_header = next(h for h in set_cookie_headers if h.startswith("refresh="))

        for header in (access_header, refresh_header):
            assert "httponly" in header
            assert "secure" in header
            assert "samesite=lax" in header

        assert f"max-age={settings.access_token_lifetime_seconds}" in access_header
        assert f"max-age={settings.refresh_token_lifetime_seconds}" in refresh_header
    finally:
        _delete_user(email)


@pytest.mark.asyncio
async def test_refresh_emits_audit_event_on_success(client):
    email = "refresh_audit@test.com"
    user_id = _seed_user(email)
    jti = _new_jti()
    token = _make_refresh_jwt(user_id=user_id, jti=jti, email=email)
    _register_token(jti=jti, user_id=user_id)
    try:
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert resp.status_code == 200, resp.text

        rows = execute_query(
            """
            SELECT * FROM audit_log
             WHERE action = 'AUTH_TOKEN_REFRESHED'
               AND actor_id = :uid
             ORDER BY id DESC
             LIMIT 1
            """,
            {"uid": user_id},
        )
        assert rows, "expected AUTH_TOKEN_REFRESHED audit event"
        assert rows[0]["resource_type"] == "refresh_token"
        # The metadata column should reference both the old and new JTI
        # so a forensic query can trace the rotation chain.
        meta = rows[0]["metadata"]
        assert meta is not None
        assert meta.get("old_jti") == jti
        assert meta.get("new_jti")
        assert meta["new_jti"] != jti
    finally:
        _delete_user(email)


@pytest.mark.asyncio
async def test_refresh_invalid_subject_claim_returns_401(client):
    """A signed token with a non-integer ``sub`` is rejected via the
    INVALID_REFRESH_TOKEN guard before any DB lookup."""
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "not-a-number",
            "email": "garbage@test.com",
            "iat": int(now.timestamp()),
            "exp": now + timedelta(seconds=600),
            "type": "refresh",
            "jti": _new_jti(),
        },
        JWT_KEY,
        algorithm=ALGO,
    )
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert resp.status_code == 401
    assert resp.json()["error"]["detail"]["error_code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.asyncio
async def test_refresh_missing_jti_claim_returns_401(client):
    """A signed refresh JWT without a ``jti`` claim is rejected."""
    user_id = _seed_user("refresh_no_jti@test.com")
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(user_id),
            "email": "refresh_no_jti@test.com",
            "iat": int(now.timestamp()),
            "exp": now + timedelta(seconds=600),
            "type": "refresh",
            # no jti
        },
        JWT_KEY,
        algorithm=ALGO,
    )
    try:
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert resp.status_code == 401
        assert resp.json()["error"]["detail"]["error_code"] == "INVALID_REFRESH_TOKEN"
    finally:
        _delete_user("refresh_no_jti@test.com")
