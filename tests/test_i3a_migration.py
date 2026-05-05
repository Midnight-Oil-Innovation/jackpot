"""I-3a migration: upgrade/downgrade round-trip.

Runs the new alembic revision against a clean test container, then
downgrades, then upgrades again. Asserts the schema before and after
each step.

Uses subprocess + the shared `test_db_url` fixture from conftest. The
session-scoped `initialize_test_db` fixture has already brought the DB
to ``head`` (which is `3644749bf4c6` in this PR), so step one is a
downgrade-from-head.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from backend.database import execute_query, execute_write, reset_engine

REVISION = "3644749bf4c6"
PREV = "2a1b3c4d5e6f"
_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"


def _alembic(target: str, db_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", target]
        if target != "downgrade"
        else ["uv", "run", "alembic", "downgrade", PREV],
        env=env,
        cwd=_BACKEND_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic {target} failed:\n{result.stdout}\n{result.stderr}")
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


def _check_constraint_definition(name: str) -> str | None:
    rows = execute_query(
        """
        SELECT pg_get_constraintdef(c.oid) AS def
          FROM pg_constraint c
          JOIN pg_class t ON t.oid = c.conrelid
         WHERE c.conname = :n AND t.relname = 'submissions'
        """,
        {"n": name},
    )
    return rows[0]["def"] if rows else None


@pytest.mark.integration
def test_migration_upgrade_downgrade_roundtrip(test_db_url):
    # We start at head (test fixtures already upgraded). Verify we have
    # the I-3a columns + index.
    cols = _column_names("submissions")
    expected_new = {
        "execution_started_at",
        "execution_completed_at",
        "execution_log_uris",
        "execution_error_message",
        "execution_attempt_count",
        "executor_backend",
    }
    assert expected_new.issubset(cols), f"missing: {expected_new - cols}"
    assert _index_exists("idx_submissions_status_executing")
    cdef = _check_constraint_definition("submissions_status_valid")
    assert cdef is not None
    for st in ("EXECUTING", "EXECUTION_FAILED", "EXECUTION_INTERRUPTED"):
        assert st in cdef, f"new state {st} missing from CHECK"

    # Round-trip: downgrade one revision; the I-3a columns + index disappear.
    _alembic("downgrade", test_db_url)
    cols = _column_names("submissions")
    for col in expected_new:
        assert col not in cols, f"column {col} should be gone after downgrade"
    assert not _index_exists("idx_submissions_status_executing")
    cdef_after_down = _check_constraint_definition("submissions_status_valid")
    assert cdef_after_down is not None
    for st in ("EXECUTING", "EXECUTION_FAILED", "EXECUTION_INTERRUPTED"):
        assert st not in cdef_after_down, f"new state {st} leaked into pre-I3a CHECK"

    # Upgrade again; assert clean.
    _alembic("head", test_db_url)
    cols = _column_names("submissions")
    assert expected_new.issubset(cols)
    assert _index_exists("idx_submissions_status_executing")


@pytest.mark.integration
def test_columns_round_trip_values(test_db_url):
    """Insert a row using the new columns; read it back; verify
    JSONB and INTEGER defaults work as advertised."""
    # Need a user + lab + sample to satisfy FKs.
    rows = execute_write(
        """
        INSERT INTO samples (
            sample_id, lab_id, project_id, owner_id, source_type,
            organism_name, type_of_experiment, library_preparation_method,
            sequencing_protocol, sequencing_platform, sequencing_lab,
            date_collected, date_sequenced, collection_facility,
            collection_location_country, sharing_level, fastq_r1_uri,
            surveillance_relevant
        ) VALUES (
            'I3A-MIG-S1', 1, 1, 1, 'Human',
            'Severe acute respiratory syndrome coronavirus 2', 'WGS',
            'ARTIC', 'https://www.protocols.io/view/artic-v4-1', 'Illumina',
            'Example Sequencing Lab', '2026-01-15', '2026-01-17',
            'Example Hospital', 'United States', 'PRIVATE',
            'gs://test/R1.fq.gz', FALSE
        ) RETURNING id
        """
    )
    sample_id = rows[0]["id"]
    rows = execute_write(
        """
        INSERT INTO submissions (
            created_by_user_id, lab_id, target_repository, title, status,
            execution_log_uris, execution_attempt_count, executor_backend
        ) VALUES (
            1, 1, 'NCBI', 'I3A-MIG-S1', 'EXECUTING',
            '["file:///tmp/log-1.log"]'::jsonb, 1, 'seqsender_subprocess'
        ) RETURNING id
        """
    )
    sub_id = rows[0]["id"]
    try:
        row = execute_query("SELECT * FROM submissions WHERE id = :id", {"id": sub_id})[0]
        assert row["execution_log_uris"] == ["file:///tmp/log-1.log"]
        assert row["execution_attempt_count"] == 1
        assert row["executor_backend"] == "seqsender_subprocess"
        assert row["execution_error_message"] is None
    finally:
        execute_write("DELETE FROM submissions WHERE id = :id", {"id": sub_id})
        execute_write("DELETE FROM samples WHERE id = :id", {"id": sample_id})


@pytest.mark.integration
def test_default_values_for_existing_rows():
    """A row inserted without specifying the new columns must pick up
    the column defaults: execution_log_uris=[], execution_attempt_count=0."""
    rows = execute_write(
        """
        INSERT INTO samples (
            sample_id, lab_id, project_id, owner_id, source_type,
            organism_name, type_of_experiment, library_preparation_method,
            sequencing_protocol, sequencing_platform, sequencing_lab,
            date_collected, date_sequenced, collection_facility,
            collection_location_country, sharing_level, fastq_r1_uri,
            surveillance_relevant
        ) VALUES (
            'I3A-MIG-S2', 1, 1, 1, 'Human',
            'Severe acute respiratory syndrome coronavirus 2', 'WGS',
            'ARTIC', 'https://www.protocols.io/view/artic-v4-1', 'Illumina',
            'Example Sequencing Lab', '2026-01-15', '2026-01-17',
            'Example Hospital', 'United States', 'PRIVATE',
            'gs://test/R1.fq.gz', FALSE
        ) RETURNING id
        """
    )
    sample_id = rows[0]["id"]
    rows = execute_write(
        """
        INSERT INTO submissions (
            created_by_user_id, lab_id, target_repository, title
        ) VALUES (1, 1, 'NCBI', 'I3A-MIG-DEFAULTS') RETURNING id
        """
    )
    sub_id = rows[0]["id"]
    try:
        row = execute_query("SELECT * FROM submissions WHERE id = :id", {"id": sub_id})[0]
        assert row["execution_log_uris"] == []
        assert row["execution_attempt_count"] == 0
        assert row["executor_backend"] is None
    finally:
        execute_write("DELETE FROM submissions WHERE id = :id", {"id": sub_id})
        execute_write("DELETE FROM samples WHERE id = :id", {"id": sample_id})
