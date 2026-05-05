"""I-3a lifespan recovery: ``recover_interrupted_executions``.

Direct tests of the recovery hook itself plus an integration check that
running it twice is idempotent. The hook is wired into the FastAPI
lifespan in ``backend.main``; the lifespan tests stay out of scope here
(no FastAPI startup harness in this PR's test surface).
"""

from __future__ import annotations

import pytest

from backend.audit import AuditActions
from backend.database import execute_query, execute_write, get_db
from backend.notifications import NotificationEvents
from backend.submissions import (
    create_submission,
    recover_interrupted_executions,
)

SEED_USER_ID = 1
SEED_LAB_ID = 1
SAMPLE_PREFIX = "I3A-RC-SAMPLE-"
SUB_PREFIX = "I3A-RC-"


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
        execute_write(
            "DELETE FROM notifications WHERE resource_type = 'submission' AND resource_id = :rid",
            {"rid": str(sid)},
        )
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'submission' AND resource_id = :rid",
            {"rid": str(sid)},
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
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'sample' AND resource_id = :rid",
            {"rid": str(sid)},
        )
        execute_write("DELETE FROM samples WHERE id = :id", {"id": sid})


def _make_executing(suffix: str) -> int:
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
    execute_write(
        "UPDATE submissions SET status = 'EXECUTING', "
        "execution_attempt_count = 1, "
        "executor_backend = 'seqsender_subprocess' "
        "WHERE id = :id",
        {"id": sub["id"]},
    )
    return sub["id"]


@pytest.fixture(autouse=True)
def _around_each():
    _cleanup()
    yield
    _cleanup()


def test_no_executing_returns_zero():
    with get_db() as db:
        result = recover_interrupted_executions(db)
    assert result == {"recovered": 0}


def test_three_executing_recovered():
    ids = [_make_executing(f"MULTI-{i}") for i in range(3)]
    with get_db() as db:
        result = recover_interrupted_executions(db)
    assert result == {"recovered": 3}
    for sub_id in ids:
        row = execute_query("SELECT * FROM submissions WHERE id = :id", {"id": sub_id})[0]
        assert row["status"] == "EXECUTION_INTERRUPTED"
        assert row["execution_error_message"] == "API restart detected during execution"
        assert row["execution_completed_at"] is not None
        # Each transition emitted both an audit event and a notification.
        audit_rows = execute_query(
            "SELECT action FROM audit_log WHERE resource_type = 'submission' "
            "AND resource_id = :rid",
            {"rid": str(sub_id)},
        )
        assert AuditActions.SUBMISSION_BACKEND_EXECUTION_INTERRUPTED in [
            r["action"] for r in audit_rows
        ]
        notif_rows = execute_query(
            "SELECT event_type FROM notifications WHERE resource_type = 'submission' "
            "AND resource_id = :rid",
            {"rid": str(sub_id)},
        )
        assert NotificationEvents.SUBMISSION_EXECUTION_INTERRUPTED in [
            r["event_type"] for r in notif_rows
        ]


def test_other_states_untouched():
    """Submissions in non-EXECUTING states must not be recovered."""
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
            "sample_id": f"{SAMPLE_PREFIX}OTHER",
            "lab_id": SEED_LAB_ID,
            "project_id": 1,
            "owner_id": SEED_USER_ID,
        },
    )
    sample_id = rows[0]["id"]
    statuses = [
        "DRAFT",
        "READY_TO_SUBMIT",
        "SUBMITTED",
        "ACCEPTED",
        "EMBARGOED",
        "WITHDRAWN",
        "EXECUTION_FAILED",
        "EXECUTION_INTERRUPTED",
    ]
    sub_ids = []
    for st in statuses:
        with get_db() as db:
            sub = create_submission(
                user_id=SEED_USER_ID,
                lab_id=SEED_LAB_ID,
                target_repository="NCBI",
                title=f"{SUB_PREFIX}OTHER-{st}",
                sample_ids=[sample_id],
                conn=db,
            )
        execute_write(
            "UPDATE submissions SET status = :st WHERE id = :id",
            {"st": st, "id": sub["id"]},
        )
        sub_ids.append(sub["id"])

    with get_db() as db:
        result = recover_interrupted_executions(db)
    assert result == {"recovered": 0}

    for sub_id, expected_status in zip(sub_ids, statuses, strict=True):
        row = execute_query("SELECT status FROM submissions WHERE id = :id", {"id": sub_id})[0]
        assert row["status"] == expected_status


def test_idempotent_when_already_recovered():
    sub_id = _make_executing("IDEM")
    with get_db() as db:
        first = recover_interrupted_executions(db)
        second = recover_interrupted_executions(db)
    assert first == {"recovered": 1}
    assert second == {"recovered": 0}
    row = execute_query("SELECT status FROM submissions WHERE id = :id", {"id": sub_id})[0]
    assert row["status"] == "EXECUTION_INTERRUPTED"


def test_concurrent_state_change_skipped_silently(monkeypatch):
    """If a row leaves EXECUTING between the SELECT scan and the
    per-row UPDATE inside ``mark_execution_interrupted`` (a concurrent
    retry, etc.), the recovery hook must skip it and continue rather
    than abort. We simulate by stubbing ``mark_execution_interrupted``
    to raise HTTPException for one specific id."""
    from fastapi import HTTPException

    keep_id = _make_executing("CONC-KEEP")
    skip_id = _make_executing("CONC-SKIP")

    import backend.submissions as subs

    real = subs.mark_execution_interrupted

    def stub(*, submission_id: int, **kwargs):
        if submission_id == skip_id:
            raise HTTPException(status_code=422, detail="raced out")
        return real(submission_id=submission_id, **kwargs)

    monkeypatch.setattr(subs, "mark_execution_interrupted", stub)
    with get_db() as db:
        result = subs.recover_interrupted_executions(db)
    # One row recovered; the raced one is skipped silently.
    assert result == {"recovered": 1}
    keep_row = execute_query("SELECT status FROM submissions WHERE id = :id", {"id": keep_id})[0]
    skip_row = execute_query("SELECT status FROM submissions WHERE id = :id", {"id": skip_id})[0]
    assert keep_row["status"] == "EXECUTION_INTERRUPTED"
    assert skip_row["status"] == "EXECUTING"


def test_skips_soft_deleted_executing_rows():
    """Soft-deleted submissions in EXECUTING (an unlikely but
    well-formed state) are NOT touched by the recovery hook."""
    sub_id = _make_executing("SOFT-DEL")
    execute_write("UPDATE submissions SET is_deleted = TRUE WHERE id = :id", {"id": sub_id})
    with get_db() as db:
        result = recover_interrupted_executions(db)
    assert result == {"recovered": 0}
    row = execute_query("SELECT status FROM submissions WHERE id = :id", {"id": sub_id})[0]
    assert row["status"] == "EXECUTING"  # untouched
