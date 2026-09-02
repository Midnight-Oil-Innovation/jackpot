"""P1: ``cleanup_old_refresh_tokens`` APScheduler job tests.

The job purges revoked-or-expired rows whose ``revoked_at`` /
``expires_at`` is older than
``Settings.refresh_token_retention_after_revoke_seconds``. Active
rows (``revoked_at IS NULL`` and ``expires_at >= cutoff``) are never
touched.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.config import get_settings
from backend.database import execute_query, execute_write
from backend.jobs import cleanup_old_refresh_tokens

USER_EMAIL = "p1cleanup@test.com"


def _seed_user() -> int:
    execute_write(
        """
        INSERT INTO users (email, name, organization_id, is_active)
        VALUES (:e, 'P1 Cleanup User', 1, TRUE)
        ON CONFLICT (email) DO UPDATE SET is_active = TRUE
        """,
        {"e": USER_EMAIL},
    )
    return execute_query("SELECT id FROM users WHERE email = :e", {"e": USER_EMAIL})[0]["id"]


def _delete_user() -> None:
    execute_write(
        "UPDATE audit_log SET actor_id = NULL WHERE actor_id IN "
        "(SELECT id FROM users WHERE email = :e)",
        {"e": USER_EMAIL},
    )
    execute_write("DELETE FROM users WHERE email = :e", {"e": USER_EMAIL})


def _insert_token(
    *,
    jti: str,
    user_id: int,
    issued_offset: timedelta,
    expires_offset: timedelta,
    revoked_offset: timedelta | None = None,
    revoked_reason: str | None = None,
) -> None:
    """Offsets are interpreted relative to now (negative = past)."""
    now = datetime.now(UTC)
    execute_write(
        """
        INSERT INTO refresh_tokens (
            jti, user_id, issued_at, expires_at, revoked_at, revoked_reason
        ) VALUES (
            :jti, :uid, :iat, :exp, :rev, :reason
        )
        """,
        {
            "jti": jti,
            "uid": user_id,
            "iat": now + issued_offset,
            "exp": now + expires_offset,
            "rev": (now + revoked_offset) if revoked_offset is not None else None,
            "reason": revoked_reason,
        },
    )


@pytest.mark.asyncio
async def test_cleanup_purges_old_revoked_and_expired_only():
    user_id = _seed_user()
    retention = get_settings().refresh_token_retention_after_revoke_seconds
    well_past = timedelta(seconds=retention + 86400)  # 1 day past the cutoff
    not_yet_cutoff = timedelta(seconds=-(retention - 3600))  # still within retention
    try:
        # Five rows representing the full state-space:
        # 1. active (issued recently, future expiry, not revoked) → KEEP
        _insert_token(
            jti="cleanup-active",
            user_id=user_id,
            issued_offset=timedelta(hours=-1),
            expires_offset=timedelta(days=7),
        )
        # 2. revoked recently (within retention window) → KEEP
        _insert_token(
            jti="cleanup-revoked-recent",
            user_id=user_id,
            issued_offset=timedelta(days=-1),
            expires_offset=timedelta(days=6),
            revoked_offset=not_yet_cutoff,
            revoked_reason="logout",
        )
        # 3. revoked long ago (past retention) → PURGE
        _insert_token(
            jti="cleanup-revoked-old",
            user_id=user_id,
            issued_offset=timedelta(days=-90),
            expires_offset=timedelta(days=-83),
            revoked_offset=-well_past,
            revoked_reason="rotated",
        )
        # 4. expired recently, never revoked (within retention) → KEEP
        _insert_token(
            jti="cleanup-expired-recent",
            user_id=user_id,
            issued_offset=timedelta(days=-8),
            expires_offset=not_yet_cutoff,
        )
        # 5. expired long ago, never revoked → PURGE
        _insert_token(
            jti="cleanup-expired-old",
            user_id=user_id,
            issued_offset=timedelta(days=-90),
            expires_offset=-well_past,
        )

        out = await cleanup_old_refresh_tokens()
        assert out["purged"] >= 2  # exactly the two "old" rows we inserted

        survivors = {
            r["jti"]
            for r in execute_query(
                "SELECT jti FROM refresh_tokens WHERE user_id = :u",
                {"u": user_id},
            )
        }
        assert "cleanup-active" in survivors
        assert "cleanup-revoked-recent" in survivors
        assert "cleanup-expired-recent" in survivors
        assert "cleanup-revoked-old" not in survivors
        assert "cleanup-expired-old" not in survivors
    finally:
        execute_write(
            "DELETE FROM refresh_tokens WHERE user_id = :u",
            {"u": user_id},
        )
        _delete_user()


@pytest.mark.asyncio
async def test_cleanup_returns_counter_dict():
    user_id = _seed_user()
    retention = get_settings().refresh_token_retention_after_revoke_seconds
    well_past = timedelta(seconds=retention + 86400)
    try:
        for n in range(3):
            _insert_token(
                jti=f"cleanup-counter-{n}",
                user_id=user_id,
                issued_offset=timedelta(days=-90),
                expires_offset=-well_past,
            )
        out = await cleanup_old_refresh_tokens()
        assert isinstance(out, dict)
        assert out.get("purged", 0) >= 3
    finally:
        execute_write(
            "DELETE FROM refresh_tokens WHERE user_id = :u",
            {"u": user_id},
        )
        _delete_user()


@pytest.mark.asyncio
async def test_cleanup_is_idempotent_when_nothing_to_purge():
    """Running the job on a clean table is a no-op that returns
    ``purged=0`` — no errors, no spurious side effects."""
    user_id = _seed_user()
    try:
        # Only an active row; nothing to purge.
        _insert_token(
            jti="cleanup-noop",
            user_id=user_id,
            issued_offset=timedelta(hours=-1),
            expires_offset=timedelta(days=7),
        )
        out1 = await cleanup_old_refresh_tokens()
        survivors_1 = execute_query(
            "SELECT jti FROM refresh_tokens WHERE user_id = :u",
            {"u": user_id},
        )
        out2 = await cleanup_old_refresh_tokens()
        survivors_2 = execute_query(
            "SELECT jti FROM refresh_tokens WHERE user_id = :u",
            {"u": user_id},
        )
        # Active row survives both runs; per-run purge count is zero.
        assert {r["jti"] for r in survivors_1} == {"cleanup-noop"}
        assert {r["jti"] for r in survivors_2} == {"cleanup-noop"}
        assert out1["purged"] == 0
        assert out2["purged"] == 0
    finally:
        execute_write(
            "DELETE FROM refresh_tokens WHERE user_id = :u",
            {"u": user_id},
        )
        _delete_user()
