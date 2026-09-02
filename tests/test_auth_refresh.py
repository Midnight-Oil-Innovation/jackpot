"""R-1 #6 — refresh-token rotation must be atomic under concurrent
presentations of the same token.

Without ``SELECT ... FOR UPDATE`` on the JTI lookup, two simultaneous
``POST /api/v1/auth/refresh`` requests can both pass the
``revoked_at IS NULL`` check and both perform rotation, issuing two
valid refresh tokens for one original. The fix locks the JTI row for
the duration of each rotation; the second request blocks until the
first commits, then sees ``revoked_at`` set and falls into the
replay-detection branch.

This test fires the two requests via :func:`asyncio.gather` over two
independent event loops (one per worker thread). Real OS-level
concurrency is required because the production code path uses
synchronous SQLAlchemy calls — running both requests on a single
event loop would naturally serialise them, hiding the race.

The test asserts exactly one returned 200 and the other 401, plus
DB-level state showing only one rotation occurred.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from backend.auth.oauth import _new_jti
from backend.database import execute_query, execute_write
from backend.main import app

# Inlined seeding helpers (peers of tests/test_p1_refresh_endpoint.py).
# Cross-test-module imports require a tests/ package init that this
# repository doesn't ship; duplicating these few lines is preferable
# to introducing one for one test file.

_JWT_KEY = "test-jwt-signing-key"
_ALGO = "HS256"


def _seed_user(email: str) -> int:
    execute_write(
        """
        INSERT INTO users (email, name, organization_id, is_active)
        VALUES (:e, 'R-1 #6 User', 1, TRUE)
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


def _make_refresh_jwt(*, user_id: int, jti: str, email: str) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "iat": int(now.timestamp()),
            "exp": now + timedelta(seconds=604800),
            "type": "refresh",
            "jti": jti,
        },
        _JWT_KEY,
        algorithm=_ALGO,
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
            "exp": now + timedelta(seconds=604800),
        },
    )


def _refresh_in_thread(token: str) -> int:
    """Fire one refresh request from inside a dedicated event loop in
    its own OS thread, returning the HTTP status. Each thread gets a
    fresh asyncio loop so the two requests do not share the event
    loop and can genuinely race at the database layer."""

    async def _do() -> int:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/auth/refresh", json={"refresh_token": token})
            return resp.status_code

    return asyncio.run(_do())


@pytest.mark.asyncio
async def test_concurrent_refresh_only_one_succeeds():
    """Fire two refresh requests with the same token in parallel; the
    row-lock must serialise them so one succeeds and the other gets a
    401 (replay-detected or revoked).

    The DB state after both requests must show:
    - The original JTI revoked exactly once (reason='rotated' or
      'replay_detected' depending on which task lost the race).
    - At most one new JTI row with revoked_at IS NULL (the winning
      rotation's replacement; the losing task's replay-detect branch
      bulk-revokes everything).
    """
    email = "concurrent_refresh@test.com"
    user_id = _seed_user(email)
    old_jti = _new_jti()
    token = _make_refresh_jwt(user_id=user_id, jti=old_jti, email=email)
    _register_token(jti=old_jti, user_id=user_id)

    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=2) as ex:
            statuses = await asyncio.gather(
                loop.run_in_executor(ex, _refresh_in_thread, token),
                loop.run_in_executor(ex, _refresh_in_thread, token),
            )

        # Exactly one 200 (the rotation that won the lock) and one
        # 401 (the loser, which sees the JTI revoked when the lock
        # releases).
        assert sorted(statuses) == [200, 401], (
            f"Expected exactly one 200 and one 401, got {statuses}. "
            "If both succeeded, the row-lock is missing — a concurrent "
            "rotation slipped through."
        )

        # Database-level invariant: at most one valid (non-revoked)
        # chain of refresh tokens exists for this user. The losing
        # request triggered the replay-detection bulk sweep, which
        # revokes ALL active tokens for this user (defense in depth)
        # — so we may see 0 active. Either 0 or 1 is acceptable; >1
        # means two rotations succeeded.
        active_rows = execute_query(
            "SELECT jti FROM refresh_tokens WHERE user_id = :uid AND revoked_at IS NULL",
            {"uid": user_id},
        )
        assert len(active_rows) <= 1, (
            f"Expected at most one active refresh-token row, found "
            f"{len(active_rows)}. Concurrent rotation produced multiple."
        )

        # The original JTI must be revoked.
        original = execute_query(
            "SELECT revoked_at, revoked_reason FROM refresh_tokens WHERE jti = :j",
            {"j": old_jti},
        )
        assert original
        assert original[0]["revoked_at"] is not None
        # Reason is either 'rotated' (winning rotation) or
        # 'replay_detected' (if the bulk sweep raced ahead).
        assert original[0]["revoked_reason"] in ("rotated", "replay_detected")
    finally:
        _delete_user(email)
