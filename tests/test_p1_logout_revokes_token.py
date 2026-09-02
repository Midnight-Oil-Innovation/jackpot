"""P1: ``POST /api/v1/auth/logout`` revokes the current refresh token.

Logout is best-effort: missing / malformed / expired cookies still
clear cookies and return success. When the refresh cookie is parseable
(even if expired — ``verify_exp=False`` lets the handler still revoke
the row), the matching refresh-token row is marked
``revoked_reason='logout'`` and an ``AUTH_LOGOUT`` audit event is
emitted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from backend.auth.oauth import _new_jti
from backend.database import execute_query, execute_write

JWT_KEY = "test-jwt-signing-key"
ALGO = "HS256"


def _seed_user(email: str) -> int:
    execute_write(
        """
        INSERT INTO users (email, name, organization_id, is_active)
        VALUES (:e, 'P1 Logout User', 1, TRUE)
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
    email: str,
    expired: bool = False,
) -> str:
    now = datetime.now(UTC)
    exp = now - timedelta(seconds=60) if expired else now + timedelta(seconds=600)
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "iat": int(now.timestamp()),
            "exp": exp,
            "type": "refresh",
            "jti": jti,
        },
        JWT_KEY,
        algorithm=ALGO,
    )


def _register_token(*, jti: str, user_id: int) -> None:
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
            "exp": now + timedelta(days=7),
        },
    )


@pytest.mark.asyncio
async def test_logout_with_valid_cookie_revokes_row(client):
    email = "p1logout_valid@test.com"
    user_id = _seed_user(email)
    jti = _new_jti()
    token = _make_refresh_jwt(user_id=user_id, jti=jti, email=email)
    _register_token(jti=jti, user_id=user_id)
    try:
        client.cookies.set("refresh", token)
        resp = await client.post("/api/v1/auth/logout")
        client.cookies.clear()

        assert resp.status_code == 200
        assert resp.json() == {"status": "logged out"}

        row = execute_query("SELECT * FROM refresh_tokens WHERE jti = :j", {"j": jti})[0]
        assert row["revoked_at"] is not None
        assert row["revoked_reason"] == "logout"

        # Cookies cleared (delete_cookie sends Max-Age=0).
        set_cookie_headers = [h.lower() for h in resp.headers.get_list("set-cookie")]
        assert any("access=" in h and "max-age=0" in h for h in set_cookie_headers)
        assert any("refresh=" in h and "max-age=0" in h for h in set_cookie_headers)
    finally:
        _delete_user(email)


@pytest.mark.asyncio
async def test_logout_without_cookie_succeeds(client):
    """No refresh cookie → no row to revoke, but logout still returns 200
    and clears cookies. No DB row is created or modified."""
    client.cookies.clear()
    pre_count = execute_query("SELECT COUNT(*) AS n FROM refresh_tokens")[0]["n"]
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    post_count = execute_query("SELECT COUNT(*) AS n FROM refresh_tokens")[0]["n"]
    assert pre_count == post_count


@pytest.mark.asyncio
async def test_logout_with_malformed_cookie_succeeds(client):
    """Garbage refresh cookie does not raise — the JWTError handler
    swallows the decode failure and the endpoint clears cookies anyway."""
    client.cookies.set("refresh", "not-a-real-jwt")
    resp = await client.post("/api/v1/auth/logout")
    client.cookies.clear()
    assert resp.status_code == 200
    assert resp.json() == {"status": "logged out"}


@pytest.mark.asyncio
async def test_logout_with_expired_cookie_still_revokes_row(client):
    """``verify_exp=False`` in the logout handler lets us revoke
    expired-but-otherwise-valid tokens so operators see a clean
    ``logout`` reason rather than an orphaned row aging out."""
    email = "p1logout_expired@test.com"
    user_id = _seed_user(email)
    jti = _new_jti()
    token = _make_refresh_jwt(user_id=user_id, jti=jti, email=email, expired=True)
    _register_token(jti=jti, user_id=user_id)
    try:
        client.cookies.set("refresh", token)
        resp = await client.post("/api/v1/auth/logout")
        client.cookies.clear()

        assert resp.status_code == 200
        row = execute_query("SELECT * FROM refresh_tokens WHERE jti = :j", {"j": jti})[0]
        assert row["revoked_at"] is not None
        assert row["revoked_reason"] == "logout"
    finally:
        _delete_user(email)


@pytest.mark.asyncio
async def test_logout_emits_audit_event(client):
    email = "p1logout_audit@test.com"
    user_id = _seed_user(email)
    jti = _new_jti()
    token = _make_refresh_jwt(user_id=user_id, jti=jti, email=email)
    _register_token(jti=jti, user_id=user_id)
    try:
        client.cookies.set("refresh", token)
        resp = await client.post("/api/v1/auth/logout")
        client.cookies.clear()
        assert resp.status_code == 200

        rows = execute_query(
            """
            SELECT * FROM audit_log
             WHERE action = 'AUTH_LOGOUT'
               AND actor_id = :uid
             ORDER BY id DESC
             LIMIT 1
            """,
            {"uid": user_id},
        )
        assert rows, "expected AUTH_LOGOUT audit event"
        assert rows[0]["resource_type"] == "refresh_token"
        assert rows[0]["resource_id"] == jti
    finally:
        _delete_user(email)


@pytest.mark.asyncio
async def test_logout_does_not_re_revoke_already_revoked_row(client):
    """If the refresh-token row was already revoked (e.g., earlier
    rotation), the WHERE clause's ``revoked_at IS NULL`` predicate
    leaves the existing reason intact — logout does not overwrite a
    'rotated' reason with 'logout'."""
    email = "p1logout_idempotent@test.com"
    user_id = _seed_user(email)
    jti = _new_jti()
    token = _make_refresh_jwt(user_id=user_id, jti=jti, email=email)
    _register_token(jti=jti, user_id=user_id)
    execute_write(
        """
        UPDATE refresh_tokens
           SET revoked_at = NOW(), revoked_reason = 'rotated'
         WHERE jti = :j
        """,
        {"j": jti},
    )
    try:
        client.cookies.set("refresh", token)
        resp = await client.post("/api/v1/auth/logout")
        client.cookies.clear()
        assert resp.status_code == 200

        row = execute_query("SELECT * FROM refresh_tokens WHERE jti = :j", {"j": jti})[0]
        # Reason stays 'rotated' — the partial update WHERE clause
        # protects the original revocation history.
        assert row["revoked_reason"] == "rotated"
    finally:
        _delete_user(email)
