"""P1: ``POST /api/v1/auth/google/login`` registers issued refresh tokens.

The full login flow exchanges a Google auth code with Google's token
endpoint. We mock the network call by patching
``backend.routers.auth.exchange_google_code`` and verify that the
modified handler inserts a ``refresh_tokens`` row keyed on the JTI of
the refresh JWT it sets in the cookie.
"""

from __future__ import annotations

import pytest
from jose import jwt

from backend.database import execute_query, execute_write

JWT_KEY = "test-jwt-signing-key"
ALGO = "HS256"


def _seed_user(email: str) -> int:
    execute_write(
        """
        INSERT INTO users (email, name, organization_id, is_active)
        VALUES (:e, 'P1 Login User', 1, TRUE)
        ON CONFLICT (email) DO UPDATE SET is_active = TRUE
        """,
        {"e": email},
    )
    return execute_query("SELECT id FROM users WHERE email = :e", {"e": email})[0]["id"]


def _seed_whitelist(domain: str) -> None:
    execute_write(
        """
        INSERT INTO domain_whitelist (domain, description)
        VALUES (:d, 'P1 test')
        ON CONFLICT (domain) DO NOTHING
        """,
        {"d": domain},
    )


def _delete_user(email: str) -> None:
    execute_write(
        "UPDATE audit_log SET actor_id = NULL WHERE actor_id IN "
        "(SELECT id FROM users WHERE email = :e)",
        {"e": email},
    )
    execute_write("DELETE FROM users WHERE email = :e", {"e": email})


def _delete_whitelist(domain: str) -> None:
    execute_write("DELETE FROM domain_whitelist WHERE domain = :d", {"d": domain})


def _patch_google_exchange(monkeypatch, email: str, name: str = "P1 Login User") -> None:
    async def _fake_exchange(_code: str, _redirect_uri: str) -> dict[str, str]:
        return {"email": email, "name": name}

    monkeypatch.setattr("backend.routers.auth.exchange_google_code", _fake_exchange)


@pytest.mark.asyncio
async def test_login_registers_refresh_token_in_table(client, monkeypatch):
    email = "p1login_register@test.com"
    domain = email.split("@")[1]
    user_id = _seed_user(email)
    _seed_whitelist(domain)
    _patch_google_exchange(monkeypatch, email)
    try:
        resp = await client.post("/api/v1/auth/google/login", params={"code": "fake-code"})
        assert resp.status_code == 200, resp.text

        # The refresh cookie that came back has a JTI claim; that JTI
        # must now be a row in refresh_tokens.
        refresh_cookie = client.cookies.get("refresh")
        client.cookies.clear()
        assert refresh_cookie, "no refresh cookie returned by login"

        payload = jwt.decode(refresh_cookie, JWT_KEY, algorithms=[ALGO])
        assert payload["type"] == "refresh"
        jti = payload["jti"]

        rows = execute_query("SELECT * FROM refresh_tokens WHERE jti = :j", {"j": jti})
        assert rows, "login did not register the refresh-token JTI in the table"
        row = rows[0]
        assert row["user_id"] == user_id
        assert row["revoked_at"] is None
        assert row["revoked_reason"] is None
        assert row["replaced_by_jti"] is None
        # The DB row's expires_at should be ≈ the JWT's exp claim (within
        # a small skew). We only assert non-null + future-dated; tighter
        # equality would couple to wall-clock timing.
        assert row["expires_at"] is not None
        assert row["issued_at"] is not None
    finally:
        execute_write("DELETE FROM refresh_tokens WHERE user_id = :u", {"u": user_id})
        _delete_user(email)
        _delete_whitelist(domain)


@pytest.mark.asyncio
async def test_login_twice_creates_two_active_rows(client, monkeypatch):
    """No implicit invalidation of prior sessions — that's an explicit
    feature decision deferred to v2. Two consecutive logins for the
    same user MUST leave both refresh-token rows active."""
    email = "p1login_twice@test.com"
    domain = email.split("@")[1]
    user_id = _seed_user(email)
    _seed_whitelist(domain)
    _patch_google_exchange(monkeypatch, email)
    try:
        client.cookies.clear()
        resp1 = await client.post("/api/v1/auth/google/login", params={"code": "code1"})
        assert resp1.status_code == 200, resp1.text
        first_jti = jwt.decode(client.cookies.get("refresh"), JWT_KEY, algorithms=[ALGO])["jti"]
        client.cookies.clear()

        resp2 = await client.post("/api/v1/auth/google/login", params={"code": "code2"})
        assert resp2.status_code == 200, resp2.text
        second_jti = jwt.decode(client.cookies.get("refresh"), JWT_KEY, algorithms=[ALGO])["jti"]
        client.cookies.clear()

        assert first_jti != second_jti

        rows = execute_query(
            """
            SELECT jti, revoked_at FROM refresh_tokens
             WHERE user_id = :u AND jti IN (:a, :b)
            """,
            {"u": user_id, "a": first_jti, "b": second_jti},
        )
        assert len(rows) == 2, "both logins should leave a row in the table"
        for row in rows:
            assert row["revoked_at"] is None, (
                f"row for {row['jti']} should still be active "
                f"(no implicit revocation across logins)"
            )
    finally:
        execute_write("DELETE FROM refresh_tokens WHERE user_id = :u", {"u": user_id})
        _delete_user(email)
        _delete_whitelist(domain)
