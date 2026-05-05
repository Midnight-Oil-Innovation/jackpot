"""I-3b: ``_append_execution_log_uri`` JSONB-array-append correctness.

A unit-level test of the helper, complementing the
end-to-end retry test in ``test_i3b_execute_submission.py``. The helper
is exercised by ``execute_submission`` on every successful or failed
attempt; this pinpoints behavior so a regression doesn't get masked by
an unrelated execution-flow change.
"""

from __future__ import annotations

import pytest

from backend.database import execute_query, execute_write, get_db
from backend.jobs import _append_execution_log_uri
from backend.submissions import create_submission

SEED_USER_ID = 1
SEED_LAB_ID = 1
SAMPLE_PREFIX = "I3B-LURI-SAMPLE-"
SUB_PREFIX = "I3B-LURI-"


def _cleanup() -> None:
    rows = execute_query(
        "SELECT id FROM submissions WHERE title LIKE :p",
        {"p": f"{SUB_PREFIX}%"},
    )
    for r in rows:
        sid = r["id"]
        execute_write(
            "DELETE FROM submission_samples WHERE submission_id = :id",
            {"id": sid},
        )
        execute_write("DELETE FROM submissions WHERE id = :id", {"id": sid})
    rows = execute_query(
        "SELECT id FROM samples WHERE sample_id LIKE :p",
        {"p": f"{SAMPLE_PREFIX}%"},
    )
    for r in rows:
        sid = r["id"]
        execute_write("DELETE FROM submission_samples WHERE sample_id_fk = :id", {"id": sid})
        execute_write("DELETE FROM sample_files WHERE sample_id_fk = :id", {"id": sid})
        execute_write("DELETE FROM samples WHERE id = :id", {"id": sid})


def _new_submission(suffix: str) -> int:
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
            :sample_id, :lab_id, :project_id, :owner_id, 'Human',
            'Severe acute respiratory syndrome coronavirus 2', 'WGS',
            'ARTIC', 'https://www.protocols.io/view/artic-v4-1', 'Illumina',
            'Example Sequencing Lab', '2026-01-15', '2026-01-17',
            'Example Hospital', 'United States', 'PRIVATE',
            'gs://test/R1.fq.gz', FALSE
        ) RETURNING id
        """,
        {
            "sample_id": f"{SAMPLE_PREFIX}{suffix}",
            "lab_id": SEED_LAB_ID,
            "project_id": 1,
            "owner_id": SEED_USER_ID,
        },
    )
    sample_id = rows[0]["id"]
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title=f"{SUB_PREFIX}{suffix}",
            sample_ids=[sample_id],
            conn=db,
        )
    return sub["id"]


@pytest.fixture(autouse=True)
def _around_each():
    _cleanup()
    yield
    _cleanup()


def test_append_to_empty_array():
    sub_id = _new_submission("EMPTY")
    with get_db() as db:
        _append_execution_log_uri(db, sub_id, "file:///tmp/log-1.log")
    row = execute_query(
        "SELECT execution_log_uris FROM submissions WHERE id = :id", {"id": sub_id}
    )[0]
    assert row["execution_log_uris"] == ["file:///tmp/log-1.log"]


def test_append_preserves_prior_entries():
    sub_id = _new_submission("MULTI")
    execute_write(
        """
        UPDATE submissions
           SET execution_log_uris = '["file:///tmp/log-1.log"]'::jsonb
         WHERE id = :id
        """,
        {"id": sub_id},
    )
    with get_db() as db:
        _append_execution_log_uri(db, sub_id, "file:///tmp/log-2.log")
    row = execute_query(
        "SELECT execution_log_uris FROM submissions WHERE id = :id", {"id": sub_id}
    )[0]
    assert row["execution_log_uris"] == [
        "file:///tmp/log-1.log",
        "file:///tmp/log-2.log",
    ]


def test_append_supports_cloud_uri_strings():
    """gs://, s3://, file:// — all just strings to PostgreSQL JSONB."""
    sub_id = _new_submission("CLOUD")
    with get_db() as db:
        _append_execution_log_uri(db, sub_id, "gs://jackpot-submissions/exec/sub_42.log")
    row = execute_query(
        "SELECT execution_log_uris FROM submissions WHERE id = :id", {"id": sub_id}
    )[0]
    assert row["execution_log_uris"] == ["gs://jackpot-submissions/exec/sub_42.log"]
