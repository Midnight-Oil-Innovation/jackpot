"""P1 migration: refresh_tokens upgrade/downgrade round-trip.

The session-scoped ``initialize_test_db`` fixture has already brought
the DB to ``head``, so step one verifies the table + indexes + CHECK
constraint are in place. We then downgrade past P1, verify the table
is gone, upgrade again, and verify a clean rebuild.
"""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from backend.database import execute_query, execute_write, reset_engine

REVISION = "9b62dcbacaeb"
PREV = "bac8dbb11c0b"
_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"


def _alembic(args: list[str], db_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    result = subprocess.run(
        ["uv", "run", "alembic", *args],
        env=env,
        cwd=_BACKEND_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}")
    reset_engine()


def _column_names(table: str) -> set[str]:
    rows = execute_query(
        """
        SELECT column_name FROM information_schema.columns
         WHERE table_name = :t
        """,
        {"t": table},
    )
    return {r["column_name"] for r in rows}


def _index_exists(name: str) -> bool:
    rows = execute_query(
        "SELECT 1 FROM pg_indexes WHERE indexname = :n",
        {"n": name},
    )
    return bool(rows)


def _table_exists(name: str) -> bool:
    rows = execute_query(
        """
        SELECT 1 FROM information_schema.tables
         WHERE table_name = :n
        """,
        {"n": name},
    )
    return bool(rows)


def _seed_user(email: str = "p1mig_user@test.com") -> int:
    execute_write(
        """
        INSERT INTO users (email, name, organization_id, is_platform_admin, is_active)
        VALUES (:e, 'P1 Mig User', 1, FALSE, TRUE)
        ON CONFLICT (email) DO UPDATE SET is_active = TRUE
        """,
        {"e": email},
    )
    return execute_query("SELECT id FROM users WHERE email = :e", {"e": email})[0]["id"]


def _delete_user(email: str) -> None:
    # ON DELETE CASCADE on refresh_tokens removes any rows we inserted.
    execute_write(
        "UPDATE audit_log SET actor_id = NULL WHERE actor_id IN "
        "(SELECT id FROM users WHERE email = :e)",
        {"e": email},
    )
    execute_write("DELETE FROM users WHERE email = :e", {"e": email})


@pytest.mark.integration
def test_table_and_indexes_exist_at_head():
    assert _table_exists("refresh_tokens"), "refresh_tokens table missing at head"
    cols = _column_names("refresh_tokens")
    expected = {
        "jti",
        "user_id",
        "issued_at",
        "expires_at",
        "revoked_at",
        "revoked_reason",
        "replaced_by_jti",
    }
    assert expected.issubset(cols), f"missing columns: {expected - cols}"
    assert _index_exists("idx_refresh_tokens_user_id")
    assert _index_exists("idx_refresh_tokens_expires_active")


@pytest.mark.integration
def test_revoked_reason_check_rejects_invalid_values():
    user_id = _seed_user()
    now = datetime.now(UTC)
    try:
        execute_write(
            """
            INSERT INTO refresh_tokens (jti, user_id, issued_at, expires_at)
            VALUES (:jti, :uid, :iat, :exp)
            """,
            {
                "jti": "p1mig-baseline",
                "uid": user_id,
                "iat": now,
                "exp": now + timedelta(days=7),
            },
        )
        with pytest.raises(IntegrityError):
            execute_write(
                """
                UPDATE refresh_tokens
                   SET revoked_at = NOW(), revoked_reason = 'not-a-valid-reason'
                 WHERE jti = :jti
                """,
                {"jti": "p1mig-baseline"},
            )
        # Each of the four allowed values is accepted.
        for reason in ("rotated", "logout", "admin_revoke", "replay_detected"):
            execute_write(
                """
                INSERT INTO refresh_tokens (
                    jti, user_id, issued_at, expires_at, revoked_at, revoked_reason
                ) VALUES (:jti, :uid, :iat, :exp, NOW(), :r)
                """,
                {
                    "jti": f"p1mig-{reason}",
                    "uid": user_id,
                    "iat": now,
                    "exp": now + timedelta(days=7),
                    "r": reason,
                },
            )
    finally:
        _delete_user("p1mig_user@test.com")


@pytest.mark.integration
def test_fk_cascade_on_user_delete():
    """Deleting a user purges their refresh-token rows (ON DELETE CASCADE)."""
    user_id = _seed_user("p1mig_cascade@test.com")
    now = datetime.now(UTC)
    execute_write(
        """
        INSERT INTO refresh_tokens (jti, user_id, issued_at, expires_at)
        VALUES (:jti, :uid, :iat, :exp)
        """,
        {
            "jti": "p1mig-cascade",
            "uid": user_id,
            "iat": now,
            "exp": now + timedelta(days=7),
        },
    )
    rows = execute_query("SELECT 1 FROM refresh_tokens WHERE jti = :jti", {"jti": "p1mig-cascade"})
    assert rows, "row should exist before cascade"
    _delete_user("p1mig_cascade@test.com")
    rows = execute_query("SELECT 1 FROM refresh_tokens WHERE jti = :jti", {"jti": "p1mig-cascade"})
    assert rows == [], "row should be cascade-deleted with the user"


@pytest.mark.integration
def test_partial_index_definition():
    """The active-rows index must be partial — predicate ``revoked_at IS NULL``."""
    rows = execute_query(
        """
        SELECT indexdef FROM pg_indexes
         WHERE indexname = 'idx_refresh_tokens_expires_active'
        """
    )
    assert rows, "partial index missing"
    indexdef = rows[0]["indexdef"]
    # Different Postgres versions format predicates slightly differently;
    # the key invariant is that the index predicate filters on revoked_at.
    assert "revoked_at IS NULL" in indexdef, f"expected partial predicate; got {indexdef}"


@pytest.mark.integration
def test_migration_upgrade_downgrade_roundtrip(test_db_url):
    # Start at head — table exists.
    assert _table_exists("refresh_tokens")

    # Downgrade past P1; table should disappear.
    _alembic(["downgrade", PREV], test_db_url)
    assert not _table_exists("refresh_tokens")
    assert not _index_exists("idx_refresh_tokens_user_id")
    assert not _index_exists("idx_refresh_tokens_expires_active")

    # Upgrade back to head; table reappears with full structure.
    _alembic(["upgrade", "head"], test_db_url)
    assert _table_exists("refresh_tokens")
    cols = _column_names("refresh_tokens")
    expected = {
        "jti",
        "user_id",
        "issued_at",
        "expires_at",
        "revoked_at",
        "revoked_reason",
        "replaced_by_jti",
    }
    assert expected.issubset(cols)
    assert _index_exists("idx_refresh_tokens_user_id")
    assert _index_exists("idx_refresh_tokens_expires_active")
