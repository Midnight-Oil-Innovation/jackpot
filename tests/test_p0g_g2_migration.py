"""P0g G-2 — Alembic round-trip + structural assertions.

Verifies the new revision creates ``execution_profiles`` and
``pipeline_default_profile`` with the expected columns, the partial
unique index that enforces "at most one is_default=true" row, the FK
cascade from ``pipeline_default_profile.profile_id``, and the
composite primary key on ``pipeline_default_profile``. Then downgrades
and verifies both tables and the index disappear; then upgrades again
and verifies a clean re-apply.

Pattern borrowed from ``tests/test_i3a_migration.py`` — uses subprocess
+ the shared ``test_db_url`` fixture from conftest.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from backend.database import execute_query, execute_write, reset_engine

REVISION = "bac8dbb11c0b"
PREV = "3644749bf4c6"
_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"


def _alembic(target: str, db_url: str) -> None:
    """Run alembic upgrade <target> or downgrade <PREV> with DATABASE_URL."""
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    cmd = (
        ["uv", "run", "alembic", "downgrade", PREV]
        if target == "downgrade"
        else ["uv", "run", "alembic", "upgrade", target]
    )
    result = subprocess.run(
        cmd,
        env=env,
        cwd=_BACKEND_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic {target} failed:\n{result.stdout}\n{result.stderr}")
    reset_engine()


def _table_exists(name: str) -> bool:
    rows = execute_query(
        """
        SELECT 1 FROM information_schema.tables
         WHERE table_name = :n AND table_schema = 'public'
        """,
        {"n": name},
    )
    return bool(rows)


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


@pytest.fixture
def _seed_user_id() -> int:
    """The lowest-id user — created by the baseline migration."""
    rows = execute_query("SELECT id FROM users ORDER BY id ASC LIMIT 1")
    assert rows, "baseline migration should have seeded at least one user"
    return rows[0]["id"]


@pytest.fixture
def _cleanup_profiles():
    """Delete any test-created profiles after each test. The seeded
    default-local row stays (deleting it would re-trigger the partial
    unique index when other tests assert on it)."""
    yield
    execute_write("DELETE FROM pipeline_default_profile")
    execute_write("DELETE FROM execution_profiles WHERE name <> 'default-local'")


@pytest.mark.integration
def test_tables_and_index_present_at_head(test_db_url):
    assert _table_exists("execution_profiles")
    assert _table_exists("pipeline_default_profile")

    profile_cols = _column_names("execution_profiles")
    expected_profile_cols = {
        "profile_id",
        "name",
        "executor_type",
        "container_engine",
        "work_dir",
        "config_overrides",
        "is_default",
        "created_by_id",
        "created_at",
        "active",
    }
    assert expected_profile_cols.issubset(
        profile_cols
    ), f"missing columns: {expected_profile_cols - profile_cols}"

    assoc_cols = _column_names("pipeline_default_profile")
    assert {"pipeline_id", "profile_id", "priority"} == assoc_cols

    assert _index_exists("idx_execution_profiles_one_default")


@pytest.mark.integration
def test_partial_unique_index_blocks_second_default(test_db_url, _seed_user_id, _cleanup_profiles):
    """Inserting a second is_default=TRUE profile must raise.
    Many is_default=FALSE rows are always permitted."""
    # The seed already inserted one is_default=TRUE row (default-local).
    # Attempt to insert a second.
    with pytest.raises(IntegrityError):
        execute_write(
            """
            INSERT INTO execution_profiles (
                name, executor_type, container_engine, work_dir,
                is_default, created_by_id
            ) VALUES (
                'second-default', 'LOCAL', 'DOCKER', '/tmp/work',
                TRUE, :uid
            )
            """,
            {"uid": _seed_user_id},
        )

    # Two is_default=FALSE rows in addition to the seed are fine.
    execute_write(
        """
        INSERT INTO execution_profiles (
            name, executor_type, container_engine, work_dir,
            is_default, created_by_id
        ) VALUES
            ('non-default-1', 'SLURM', 'APPTAINER', '/scratch/jp', FALSE, :uid),
            ('non-default-2', 'GCP_BATCH', 'DOCKER', 'gs://x/work', FALSE, :uid)
        """,
        {"uid": _seed_user_id},
    )
    rows = execute_query("SELECT name FROM execution_profiles WHERE is_default = FALSE")
    names = {r["name"] for r in rows}
    assert {"non-default-1", "non-default-2"}.issubset(names)


@pytest.mark.integration
def test_executor_type_check_constraint(test_db_url, _seed_user_id, _cleanup_profiles):
    """An executor_type outside the LinkML-permitted values must be rejected."""
    with pytest.raises(IntegrityError):
        execute_write(
            """
            INSERT INTO execution_profiles (
                name, executor_type, container_engine, work_dir,
                created_by_id
            ) VALUES (
                'bad-executor', 'MESOS', 'DOCKER', '/tmp/x', :uid
            )
            """,
            {"uid": _seed_user_id},
        )


@pytest.mark.integration
def test_container_engine_check_constraint(test_db_url, _seed_user_id, _cleanup_profiles):
    """A container_engine outside the LinkML-permitted values must be rejected."""
    with pytest.raises(IntegrityError):
        execute_write(
            """
            INSERT INTO execution_profiles (
                name, executor_type, container_engine, work_dir,
                created_by_id
            ) VALUES (
                'bad-engine', 'LOCAL', 'PODMAN', '/tmp/x', :uid
            )
            """,
            {"uid": _seed_user_id},
        )


@pytest.mark.integration
def test_unique_name_constraint(test_db_url, _seed_user_id, _cleanup_profiles):
    """name UNIQUE — second insert with the same name must reject."""
    execute_write(
        """
        INSERT INTO execution_profiles (
            name, executor_type, container_engine, work_dir, created_by_id
        ) VALUES ('dup-name', 'LOCAL', 'DOCKER', '/tmp/x', :uid)
        """,
        {"uid": _seed_user_id},
    )
    with pytest.raises(IntegrityError):
        execute_write(
            """
            INSERT INTO execution_profiles (
                name, executor_type, container_engine, work_dir, created_by_id
            ) VALUES ('dup-name', 'SLURM', 'APPTAINER', '/scratch/y', :uid)
            """,
            {"uid": _seed_user_id},
        )


@pytest.mark.integration
def test_pipeline_default_profile_fk_cascade(test_db_url, _seed_user_id, _cleanup_profiles):
    """Hard-deleting an execution_profiles row cascades to its
    pipeline_default_profile associations."""
    rows = execute_write(
        """
        INSERT INTO execution_profiles (
            name, executor_type, container_engine, work_dir, created_by_id
        ) VALUES ('cascade-target', 'LOCAL', 'DOCKER', '/tmp/x', :uid)
        RETURNING profile_id
        """,
        {"uid": _seed_user_id},
    )
    profile_id = rows[0]["profile_id"]
    pipeline_id = uuid.uuid4()

    execute_write(
        """
        INSERT INTO pipeline_default_profile (pipeline_id, profile_id, priority)
        VALUES (:pipeline_id, :profile_id, 50)
        """,
        {"pipeline_id": str(pipeline_id), "profile_id": str(profile_id)},
    )
    assoc_count = execute_query(
        "SELECT COUNT(*) AS n FROM pipeline_default_profile WHERE profile_id = :p",
        {"p": str(profile_id)},
    )[0]["n"]
    assert assoc_count == 1

    execute_write(
        "DELETE FROM execution_profiles WHERE profile_id = :p",
        {"p": str(profile_id)},
    )
    assoc_count = execute_query(
        "SELECT COUNT(*) AS n FROM pipeline_default_profile WHERE profile_id = :p",
        {"p": str(profile_id)},
    )[0]["n"]
    assert assoc_count == 0


@pytest.mark.integration
def test_pipeline_default_profile_composite_pk_rejects_duplicate(
    test_db_url, _seed_user_id, _cleanup_profiles
):
    """The composite PRIMARY KEY (pipeline_id, profile_id) blocks duplicate
    associations of the same pipeline-to-profile pair."""
    rows = execute_write(
        """
        INSERT INTO execution_profiles (
            name, executor_type, container_engine, work_dir, created_by_id
        ) VALUES ('pk-target', 'LOCAL', 'DOCKER', '/tmp/x', :uid)
        RETURNING profile_id
        """,
        {"uid": _seed_user_id},
    )
    profile_id = rows[0]["profile_id"]
    pipeline_id = uuid.uuid4()

    execute_write(
        """
        INSERT INTO pipeline_default_profile (pipeline_id, profile_id, priority)
        VALUES (:pipeline_id, :profile_id, 1)
        """,
        {"pipeline_id": str(pipeline_id), "profile_id": str(profile_id)},
    )
    with pytest.raises(IntegrityError):
        execute_write(
            """
            INSERT INTO pipeline_default_profile (pipeline_id, profile_id, priority)
            VALUES (:pipeline_id, :profile_id, 99)
            """,
            {"pipeline_id": str(pipeline_id), "profile_id": str(profile_id)},
        )


@pytest.mark.integration
def test_priority_defaults_to_100(test_db_url, _seed_user_id, _cleanup_profiles):
    """Omitting priority on insert should default to 100 per the migration."""
    rows = execute_write(
        """
        INSERT INTO execution_profiles (
            name, executor_type, container_engine, work_dir, created_by_id
        ) VALUES ('prio-target', 'LOCAL', 'DOCKER', '/tmp/x', :uid)
        RETURNING profile_id
        """,
        {"uid": _seed_user_id},
    )
    profile_id = rows[0]["profile_id"]
    pipeline_id = uuid.uuid4()
    execute_write(
        """
        INSERT INTO pipeline_default_profile (pipeline_id, profile_id)
        VALUES (:pipeline_id, :profile_id)
        """,
        {"pipeline_id": str(pipeline_id), "profile_id": str(profile_id)},
    )
    rows = execute_query(
        "SELECT priority FROM pipeline_default_profile WHERE profile_id = :p",
        {"p": str(profile_id)},
    )
    assert rows[0]["priority"] == 100


@pytest.mark.integration
def test_migration_round_trip(test_db_url):
    """downgrade -> upgrade brings the schema back to head cleanly.

    Run last in this module because it leaves the DB at a different
    state mid-test; we restore by upgrading at the end. Even so, the
    fixture's session scope means subsequent test modules get a clean
    head state.
    """
    # Sanity: tables exist at head.
    assert _table_exists("execution_profiles")
    assert _table_exists("pipeline_default_profile")
    assert _index_exists("idx_execution_profiles_one_default")

    # Round-trip: downgrade past P0g.
    _alembic("downgrade", test_db_url)
    assert not _table_exists("execution_profiles")
    assert not _table_exists("pipeline_default_profile")
    assert not _index_exists("idx_execution_profiles_one_default")

    # Upgrade again; assert clean.
    _alembic("head", test_db_url)
    assert _table_exists("execution_profiles")
    assert _table_exists("pipeline_default_profile")
    assert _index_exists("idx_execution_profiles_one_default")
    # The seed re-fires; default-local should be present once.
    rows = execute_query(
        "SELECT COUNT(*) AS n FROM execution_profiles WHERE name = 'default-local'"
    )
    assert rows[0]["n"] == 1
