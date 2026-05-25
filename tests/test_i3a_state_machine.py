"""I-3a state-machine: backend-execution transition functions.

Exercises the six new transition functions in
:mod:`backend.submissions` plus the extended ``withdraw_submission``
reachability and the still-narrow ``mark_rejected`` reachability. Each
test sets up a row in the precondition status, calls the function,
and asserts the post-state and audit/notification side effects.

The fixture pattern matches ``test_submissions_module.py`` — direct
SQL inserts under the I3A- prefix with cleanup helpers.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.audit import AuditActions
from backend.database import execute_query, execute_write, get_db
from backend.notifications import NotificationEvents
from backend.submissions import (
    create_submission,
    mark_execution_completed,
    mark_execution_failed,
    mark_execution_interrupted,
    mark_execution_queued,
    mark_execution_retried,
    mark_rejected,
    withdraw_submission,
)

SEED_USER_ID = 1
SEED_LAB_ID = 1
SAMPLE_PREFIX = "I3A-SM-SAMPLE-"
SUB_PREFIX = "I3A-SM-"


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
        execute_write(
            "DELETE FROM submission_samples WHERE sample_id_fk = :id",
            {"id": sid},
        )
        execute_write("DELETE FROM sample_files WHERE sample_id_fk = :id", {"id": sid})
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'sample' AND resource_id = :rid",
            {"rid": str(sid)},
        )
        execute_write("DELETE FROM samples WHERE id = :id", {"id": sid})


def _insert_sample(sample_id: str) -> int:
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
            "sample_id": sample_id,
            "lab_id": SEED_LAB_ID,
            "project_id": 1,
            "owner_id": SEED_USER_ID,
        },
    )
    return rows[0]["id"]


def _new_submission(suffix: str, *, status: str | None = None) -> int:
    sample_id = _insert_sample(f"{SAMPLE_PREFIX}{suffix}")
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title=f"{SUB_PREFIX}{suffix}",
            sample_ids=[sample_id],
            conn=db,
        )
    if status is not None:
        execute_write(
            "UPDATE submissions SET status = :st WHERE id = :id",
            {"st": status, "id": sub["id"]},
        )
    return sub["id"]


def _row(sub_id: int) -> dict:
    return execute_query("SELECT * FROM submissions WHERE id = :id", {"id": sub_id})[0]


def _audit_actions(sub_id: int) -> list[str]:
    rows = execute_query(
        """
        SELECT action FROM audit_log
         WHERE resource_type = 'submission' AND resource_id = :rid
         ORDER BY id ASC
        """,
        {"rid": str(sub_id)},
    )
    return [r["action"] for r in rows]


def _notification_events(sub_id: int) -> list[str]:
    rows = execute_query(
        """
        SELECT event_type FROM notifications
         WHERE resource_type = 'submission' AND resource_id = :rid
         ORDER BY id ASC
        """,
        {"rid": str(sub_id)},
    )
    return [r["event_type"] for r in rows]


@pytest.fixture(autouse=True)
def _around_each():
    _cleanup()
    yield
    _cleanup()


# ── mark_execution_queued ────────────────────────────────────────────


def test_queued_from_ready_to_submit_succeeds():
    sub_id = _new_submission("QUEUE-OK", status="READY_TO_SUBMIT")
    with get_db() as db:
        result = mark_execution_queued(
            submission_id=sub_id,
            executor_backend="seqsender_subprocess",
            actor_id=SEED_USER_ID,
            conn=db,
        )
    assert result["status"] == "EXECUTING"
    row = _row(sub_id)
    assert row["status"] == "EXECUTING"
    assert row["execution_started_at"] is not None
    assert row["execution_completed_at"] is None
    assert row["execution_attempt_count"] == 1
    assert row["executor_backend"] == "seqsender_subprocess"
    assert AuditActions.SUBMISSION_BACKEND_EXECUTION_QUEUED in _audit_actions(sub_id)
    assert NotificationEvents.SUBMISSION_EXECUTION_QUEUED in _notification_events(sub_id)


@pytest.mark.parametrize(
    "starting_status",
    ["DRAFT", "SUBMITTED", "ACCEPTED", "EMBARGOED", "WITHDRAWN", "EXECUTING"],
)
def test_queued_rejects_invalid_starting_status(starting_status):
    sub_id = _new_submission(f"QUEUE-BAD-{starting_status}", status=starting_status)
    with get_db() as db, pytest.raises(HTTPException) as exc:
        mark_execution_queued(
            submission_id=sub_id,
            executor_backend="seqsender_subprocess",
            actor_id=SEED_USER_ID,
            conn=db,
        )
    assert exc.value.status_code == 422


# ── mark_execution_retried ───────────────────────────────────────────


@pytest.mark.parametrize("starting_status", ["EXECUTION_FAILED", "EXECUTION_INTERRUPTED"])
def test_retried_from_failure_states_succeeds(starting_status):
    sub_id = _new_submission(f"RETRY-OK-{starting_status}", status=starting_status)
    # Seed a prior attempt count and error message.
    execute_write(
        """
        UPDATE submissions
           SET execution_attempt_count = 1,
               execution_error_message = 'previous failure',
               execution_log_uris = '["file:///tmp/log-1.txt"]'::jsonb
         WHERE id = :id
        """,
        {"id": sub_id},
    )
    with get_db() as db:
        result = mark_execution_retried(
            submission_id=sub_id,
            executor_backend="seqsender_subprocess",
            actor_id=SEED_USER_ID,
            conn=db,
        )
    assert result["status"] == "EXECUTING"
    row = _row(sub_id)
    assert row["execution_attempt_count"] == 2
    assert row["execution_error_message"] is None
    assert row["execution_log_uris"] == ["file:///tmp/log-1.txt"]
    assert AuditActions.SUBMISSION_BACKEND_EXECUTION_RETRY_QUEUED in _audit_actions(sub_id)
    assert NotificationEvents.SUBMISSION_EXECUTION_QUEUED in _notification_events(sub_id)


@pytest.mark.parametrize("starting_status", ["READY_TO_SUBMIT", "EXECUTING", "SUBMITTED"])
def test_retried_rejects_invalid_starting_status(starting_status):
    sub_id = _new_submission(f"RETRY-BAD-{starting_status}", status=starting_status)
    with get_db() as db, pytest.raises(HTTPException) as exc:
        mark_execution_retried(
            submission_id=sub_id,
            executor_backend="seqsender_subprocess",
            actor_id=SEED_USER_ID,
            conn=db,
        )
    assert exc.value.status_code == 422


# ── mark_execution_completed ─────────────────────────────────────────


def test_completed_from_executing_transitions_to_submitted():
    sub_id = _new_submission("DONE-OK", status="EXECUTING")
    execute_write(
        "UPDATE submissions SET execution_attempt_count = 1 WHERE id = :id",
        {"id": sub_id},
    )
    with get_db() as db:
        result = mark_execution_completed(
            submission_id=sub_id,
            actor_id=SEED_USER_ID,
            conn=db,
        )
    assert result["status"] == "SUBMITTED"
    row = _row(sub_id)
    assert row["status"] == "SUBMITTED"
    assert row["submitted_at"] is not None
    assert row["execution_completed_at"] is not None
    assert AuditActions.SUBMISSION_BACKEND_EXECUTION_COMPLETED in _audit_actions(sub_id)
    assert NotificationEvents.SUBMISSION_EXECUTION_COMPLETED in _notification_events(sub_id)


@pytest.mark.parametrize("starting_status", ["READY_TO_SUBMIT", "SUBMITTED", "WITHDRAWN"])
def test_completed_rejects_invalid_starting_status(starting_status):
    sub_id = _new_submission(f"DONE-BAD-{starting_status}", status=starting_status)
    with get_db() as db, pytest.raises(HTTPException) as exc:
        mark_execution_completed(submission_id=sub_id, conn=db)
    assert exc.value.status_code == 422


# ── mark_execution_failed ────────────────────────────────────────────


def test_failed_from_executing_with_log_uri():
    sub_id = _new_submission("FAIL-OK", status="EXECUTING")
    execute_write(
        "UPDATE submissions SET execution_attempt_count = 1 WHERE id = :id",
        {"id": sub_id},
    )
    with get_db() as db:
        mark_execution_failed(
            submission_id=sub_id,
            error_message="repo-rejected: BioProject mismatch",
            log_uri="file:///tmp/seqsender-attempt-1.log",
            actor_id=SEED_USER_ID,
            conn=db,
        )
    row = _row(sub_id)
    assert row["status"] == "EXECUTION_FAILED"
    assert row["execution_completed_at"] is not None
    assert row["execution_error_message"] == "repo-rejected: BioProject mismatch"
    assert row["execution_log_uris"] == ["file:///tmp/seqsender-attempt-1.log"]
    assert AuditActions.SUBMISSION_BACKEND_EXECUTION_FAILED in _audit_actions(sub_id)
    assert NotificationEvents.SUBMISSION_EXECUTION_FAILED in _notification_events(sub_id)


def test_failed_appends_log_uri_across_attempts():
    sub_id = _new_submission("FAIL-APPEND", status="EXECUTING")
    execute_write(
        """
        UPDATE submissions
           SET execution_attempt_count = 2,
               execution_log_uris = '["file:///tmp/log-1.txt"]'::jsonb
         WHERE id = :id
        """,
        {"id": sub_id},
    )
    with get_db() as db:
        mark_execution_failed(
            submission_id=sub_id,
            error_message="second failure",
            log_uri="file:///tmp/log-2.txt",
            conn=db,
        )
    row = _row(sub_id)
    assert row["execution_log_uris"] == [
        "file:///tmp/log-1.txt",
        "file:///tmp/log-2.txt",
    ]


def test_failed_without_log_uri():
    sub_id = _new_submission("FAIL-NOLOG", status="EXECUTING")
    with get_db() as db:
        mark_execution_failed(
            submission_id=sub_id,
            error_message="generic failure",
            conn=db,
        )
    row = _row(sub_id)
    assert row["status"] == "EXECUTION_FAILED"
    assert row["execution_log_uris"] == []


def test_failed_rejects_blank_error_message():
    sub_id = _new_submission("FAIL-BLANK", status="EXECUTING")
    with get_db() as db, pytest.raises(HTTPException) as exc:
        mark_execution_failed(submission_id=sub_id, error_message="   ", conn=db)
    assert exc.value.status_code == 422


@pytest.mark.parametrize("starting_status", ["READY_TO_SUBMIT", "SUBMITTED", "DRAFT"])
def test_failed_rejects_invalid_starting_status(starting_status):
    sub_id = _new_submission(f"FAIL-BAD-{starting_status}", status=starting_status)
    with get_db() as db, pytest.raises(HTTPException) as exc:
        mark_execution_failed(submission_id=sub_id, error_message="msg", conn=db)
    assert exc.value.status_code == 422


# ── mark_execution_interrupted ───────────────────────────────────────


def test_interrupted_from_executing_default_message():
    sub_id = _new_submission("INTR-OK", status="EXECUTING")
    with get_db() as db:
        mark_execution_interrupted(submission_id=sub_id, conn=db)
    row = _row(sub_id)
    assert row["status"] == "EXECUTION_INTERRUPTED"
    assert row["execution_error_message"] == "API restart detected during execution"
    assert AuditActions.SUBMISSION_BACKEND_EXECUTION_INTERRUPTED in _audit_actions(sub_id)
    assert NotificationEvents.SUBMISSION_EXECUTION_INTERRUPTED in _notification_events(sub_id)


def test_interrupted_custom_message():
    sub_id = _new_submission("INTR-CUSTOM", status="EXECUTING")
    with get_db() as db:
        mark_execution_interrupted(submission_id=sub_id, error_message="OOM kill", conn=db)
    row = _row(sub_id)
    assert row["execution_error_message"] == "OOM kill"


@pytest.mark.parametrize("starting_status", ["READY_TO_SUBMIT", "SUBMITTED"])
def test_interrupted_rejects_invalid_starting_status(starting_status):
    sub_id = _new_submission(f"INTR-BAD-{starting_status}", status=starting_status)
    with get_db() as db, pytest.raises(HTTPException) as exc:
        mark_execution_interrupted(submission_id=sub_id, conn=db)
    assert exc.value.status_code == 422


# ── withdraw reachability ────────────────────────────────────────────


@pytest.mark.parametrize("starting_status", ["EXECUTION_FAILED", "EXECUTION_INTERRUPTED"])
def test_withdraw_from_new_states_succeeds(starting_status):
    sub_id = _new_submission(f"WD-OK-{starting_status}", status=starting_status)
    with get_db() as db:
        withdraw_submission(
            submission_id=sub_id,
            reason="user gave up",
            actor_id=SEED_USER_ID,
            conn=db,
        )
    row = _row(sub_id)
    assert row["status"] == "WITHDRAWN"


def test_withdraw_from_executing_uses_specific_error_message():
    sub_id = _new_submission("WD-EXEC", status="EXECUTING")
    with get_db() as db, pytest.raises(HTTPException) as exc:
        withdraw_submission(
            submission_id=sub_id,
            reason="trying anyway",
            actor_id=SEED_USER_ID,
            conn=db,
        )
    assert exc.value.status_code == 409
    msg = str(exc.value.detail)
    assert "in progress" in msg
    assert "Wait for it to complete or fail" in msg


# ── mark_rejected does NOT reach the new states ──────────────────────


@pytest.mark.parametrize(
    "starting_status",
    ["EXECUTING", "EXECUTION_FAILED", "EXECUTION_INTERRUPTED"],
)
def test_mark_rejected_unreachable_from_new_states(starting_status):
    sub_id = _new_submission(f"MR-{starting_status}", status=starting_status)
    with get_db() as db, pytest.raises(HTTPException) as exc:
        mark_rejected(
            submission_id=sub_id,
            reason="repo rejection",
            actor_id=SEED_USER_ID,
            conn=db,
        )
    assert exc.value.status_code == 422


# ── audit/notification payloads do not leak credentials or values ────


def test_queued_audit_payload_has_no_credential_value():
    """Credential values must never appear in audit payloads (C-1
    precedent). The transition functions only embed key + backend
    name; this test pins that contract."""
    sub_id = _new_submission("AUDIT-NOLEAK", status="READY_TO_SUBMIT")
    with get_db() as db:
        mark_execution_queued(
            submission_id=sub_id,
            executor_backend="seqsender_subprocess",
            actor_id=SEED_USER_ID,
            conn=db,
        )
    rows = execute_query(
        """
        SELECT after_state FROM audit_log
         WHERE resource_type = 'submission' AND resource_id = :rid
           AND action = :a
        """,
        {"rid": str(sub_id), "a": AuditActions.SUBMISSION_BACKEND_EXECUTION_QUEUED},
    )
    assert len(rows) == 1
    after = rows[0]["after_state"] or {}
    assert after.get("status") == "EXECUTING"
    assert after.get("executor_backend") == "seqsender_subprocess"
    # The audit row is structured JSON — no free-text credential leakage.
    serialized = str(after)
    for forbidden in ("ncbi_submission_password", "ena_webin_password", "GOCSPX-"):
        assert forbidden not in serialized
