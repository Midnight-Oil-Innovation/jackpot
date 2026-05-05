"""P0g G-2 — seed verification.

Three things to prove:

1. Applying the migration against a database with at least one user
   leaves a single ``default-local`` profile in place with the
   expected column values.
2. Re-applying the migration (``alembic upgrade head`` twice) does
   NOT duplicate the seed row — ``ON CONFLICT (name) DO NOTHING``
   keeps the row count at one.
3. Applying the migration against a database with zero users skips
   the seed without raising.

The third case is awkward because the shared session-scoped
testcontainer always has a baseline-seeded admin user. We spin up a
fresh ``PostgresContainer`` for that one test, run alembic against it,
and inspect the result.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import sqlalchemy as sa
from testcontainers.postgres import PostgresContainer

from backend.database import execute_query

REVISION = "bac8dbb11c0b"
PREV = "3644749bf4c6"
_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"


def _alembic_upgrade(target: str, db_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", target],
        env=env,
        cwd=_BACKEND_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic upgrade {target} failed:\n{result.stdout}\n{result.stderr}")


@pytest.mark.integration
def test_seed_default_local_profile_present(test_db_url):
    """The session-scoped fixture has already run upgrade head against
    a DB with the baseline-seeded admin user. The seed must have fired
    and produced exactly one default-local row."""
    rows = execute_query(
        """
        SELECT name, executor_type, container_engine, work_dir,
               is_default, active, config_overrides
          FROM execution_profiles
         WHERE name = 'default-local'
        """
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["executor_type"] == "LOCAL"
    assert row["container_engine"] == "DOCKER"
    assert row["work_dir"] == "/srv/jackpot/work"
    assert row["is_default"] is True
    assert row["active"] is True
    # JSONB '{}' returns as an empty dict via SQLAlchemy.
    assert row["config_overrides"] == {}


@pytest.mark.integration
def test_seed_idempotent_under_double_upgrade(test_db_url):
    """Running ``alembic upgrade head`` a second time must not
    duplicate the seed row — ON CONFLICT (name) DO NOTHING is what
    keeps the seed safe for re-runs."""
    before = execute_query(
        "SELECT COUNT(*) AS n FROM execution_profiles WHERE name = 'default-local'"
    )[0]["n"]
    assert before == 1

    _alembic_upgrade("head", test_db_url)

    after = execute_query(
        "SELECT COUNT(*) AS n FROM execution_profiles WHERE name = 'default-local'"
    )[0]["n"]
    assert after == 1


@pytest.mark.integration
def test_seed_skipped_when_users_table_empty():
    """A fresh testcontainer with no users must complete the migration
    cleanly with zero execution_profiles rows. The DO $$ block guards
    on a non-NULL seed_user_id; the IF wrapping the INSERT means the
    upgrade succeeds when the table is empty."""
    with PostgresContainer("postgres:16") as pg:
        db_url = pg.get_connection_url()
        # Bring DB to the previous revision (everything but P0g).
        _alembic_upgrade(PREV, db_url)

        # Wipe users (and CASCADE everything that depends on them).
        # The baseline migration seeds an admin; we have to remove it
        # before the next upgrade fires the seed DO block.
        engine = sa.create_engine(db_url)
        with engine.begin() as conn:
            conn.execute(sa.text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
            assert conn.execute(sa.text("SELECT COUNT(*) FROM users")).scalar() == 0

        # Now upgrade past P0g; the seed DO block sees zero users and
        # skips the INSERT.
        _alembic_upgrade("head", db_url)

        with engine.begin() as conn:
            count = conn.execute(sa.text("SELECT COUNT(*) FROM execution_profiles")).scalar()
            assert count == 0
            # Tables are still in place (DDL ran).
            exists = conn.execute(
                sa.text(
                    "SELECT EXISTS ("
                    "  SELECT 1 FROM information_schema.tables "
                    "   WHERE table_name = 'execution_profiles'"
                    ")"
                )
            ).scalar()
            assert exists is True
        engine.dispose()
