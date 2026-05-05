"""I-3b: full execute_submission lifecycle.

Mocks ``run_seqsender`` and the storage upload so we can exercise the
job's branches (success, failure, timeout, unsupported repo) end-to-end
against the real DB without depending on Seqsender or a live storage
backend.

Each test:
  - creates a submission in EXECUTING via direct SQL (the I-3a
    state-machine tests already cover the transitions; here we want to
    drive ``execute_submission`` from a known-good starting state)
  - patches ``run_seqsender`` to return a controlled result
  - patches the executor's ``_upload_execution_log`` so log content is
    captured in memory rather than uploaded to MinIO/GCS
  - asserts on the resulting DB state, audit trail, and notification log
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.audit import AuditActions
from backend.credentials import _reset_backend, _set_backend
from backend.credentials.test_helpers import InMemoryBackend
from backend.database import execute_query, execute_write, get_db
from backend.jobs import execute_submission
from backend.notifications import NotificationEvents
from backend.submission_executors.seqsender import SeqsenderRunResult
from backend.submissions import create_submission

SEED_USER_ID = 1
SEED_LAB_ID = 1
SAMPLE_PREFIX = "I3B-EXEC-SAMPLE-"
SUB_PREFIX = "I3B-EXEC-"


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


def _make_executing_submission(
    suffix: str,
    *,
    target_repository: str = "NCBI",
    package_path: str | None = None,
) -> int:
    sample_id = _insert_sample(f"{SAMPLE_PREFIX}{suffix}")
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository=target_repository,
            title=f"{SUB_PREFIX}{suffix}",
            sample_ids=[sample_id],
            conn=db,
        )
    pkg = package_path or f"/tmp/jackpot-test/sub_{sub['id']}_pkg"
    execute_write(
        """
        UPDATE submissions
           SET status = 'EXECUTING',
               execution_started_at = NOW(),
               execution_attempt_count = 1,
               executor_backend = 'seqsender_subprocess',
               package_path = :pkg
         WHERE id = :id
        """,
        {"id": sub["id"], "pkg": pkg},
    )
    return sub["id"]


def _row(sub_id: int) -> dict:
    return execute_query("SELECT * FROM submissions WHERE id = :id", {"id": sub_id})[0]


def _audit_actions(sub_id: int) -> list[str]:
    rows = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'submission' "
        "AND resource_id = :rid ORDER BY id ASC",
        {"rid": str(sub_id)},
    )
    return [r["action"] for r in rows]


def _notification_events(sub_id: int) -> list[str]:
    rows = execute_query(
        "SELECT event_type FROM notifications WHERE resource_type = 'submission' "
        "AND resource_id = :rid ORDER BY id ASC",
        {"rid": str(sub_id)},
    )
    return [r["event_type"] for r in rows]


@pytest.fixture(autouse=True)
def _around_each(tmp_path):
    _cleanup()
    backend = InMemoryBackend(
        {
            "ncbi_submission_username": "submitter@example.org",
            "ncbi_submission_password": "ncbi-test-secret",
        }
    )
    _set_backend(backend)
    yield
    _reset_backend()
    _cleanup()


@pytest.fixture
def temp_working_root(tmp_path, monkeypatch):
    """Override the execution working dir root so success/failure path
    tests can probe whether the per-execution dir was deleted or kept."""
    root = tmp_path / "executions"
    root.mkdir()
    monkeypatch.setenv("EXECUTION_WORKING_DIR_ROOT", str(root))
    from backend.config import get_settings

    get_settings.cache_clear()
    return root


@pytest.fixture
def captured_uploads():
    """Replace the storage upload helper with a capture-and-return stub.

    The real helper hits a MinIO container; that's tested by the storage
    suite. Here we want to verify what bytes the executor *would* have
    uploaded.
    """
    captured: list[dict] = []

    async def _stub_upload(*, submission_id, attempt, content, completed_at):
        captured.append(
            {
                "submission_id": submission_id,
                "attempt": attempt,
                "content": content,
                "completed_at": completed_at,
            }
        )
        return f"file:///tmp/fake/sub-{submission_id}-attempt-{attempt}.log"

    with patch("backend.jobs._upload_execution_log", AsyncMock(side_effect=_stub_upload)):
        yield captured


def _patch_run_seqsender(result: SeqsenderRunResult | None = None):
    """Convenience: patch run_seqsender to return ``result``."""
    if result is None:
        result = SeqsenderRunResult(
            exit_code=0,
            stdout_bytes=b"ok",
            stderr_bytes=b"",
            wall_time_seconds=1.0,
            timed_out=False,
            invocation_command=[
                "/opt/seqsender/seqsender-kickoff",
                "submit",
                "--biosample",
            ],
        )
    return patch("backend.jobs.run_seqsender", AsyncMock(return_value=result))


# ── success path ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_success_transitions_to_submitted(temp_working_root, captured_uploads):
    sub_id = _make_executing_submission("OK")
    with _patch_run_seqsender():
        result = await execute_submission(sub_id)

    assert result == {"completed": 1}
    row = _row(sub_id)
    assert row["status"] == "SUBMITTED"
    assert row["execution_completed_at"] is not None
    assert len(row["execution_log_uris"]) == 1
    actions = _audit_actions(sub_id)
    assert AuditActions.SUBMISSION_BACKEND_EXECUTION_STARTED in actions
    assert AuditActions.SUBMISSION_BACKEND_EXECUTION_COMPLETED in actions
    assert NotificationEvents.SUBMISSION_EXECUTION_COMPLETED in _notification_events(sub_id)


@pytest.mark.asyncio
async def test_success_deletes_working_dir(temp_working_root, captured_uploads):
    sub_id = _make_executing_submission("OK-CLEAN")
    with _patch_run_seqsender():
        await execute_submission(sub_id)
    expected = temp_working_root / f"submission_{sub_id}_attempt_1"
    assert not expected.exists(), f"working dir {expected} should be deleted on success"


# ── failure path ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_failure_transitions_to_execution_failed(temp_working_root, captured_uploads):
    sub_id = _make_executing_submission("FAIL")
    failed = SeqsenderRunResult(
        exit_code=1,
        stdout_bytes=b"partial",
        stderr_bytes=b"Error: rejected\n",
        wall_time_seconds=2.0,
        timed_out=False,
        invocation_command=["seqsender", "submit"],
    )
    with _patch_run_seqsender(failed):
        result = await execute_submission(sub_id)

    assert result["failed"] == 1
    assert result.get("timed_out", 0) == 0
    row = _row(sub_id)
    assert row["status"] == "EXECUTION_FAILED"
    assert "non-zero status 1" in (row["execution_error_message"] or "")
    assert len(row["execution_log_uris"]) == 1
    actions = _audit_actions(sub_id)
    # Both the I-3a transition's failed event and the executor's
    # follow-up failed event are emitted; the second carries the
    # working_dir_preserved key.
    assert actions.count(AuditActions.SUBMISSION_BACKEND_EXECUTION_FAILED) >= 1
    assert NotificationEvents.SUBMISSION_EXECUTION_FAILED in _notification_events(sub_id)


@pytest.mark.asyncio
async def test_failure_preserves_working_dir(temp_working_root, captured_uploads):
    sub_id = _make_executing_submission("FAIL-KEEP")
    failed = SeqsenderRunResult(
        exit_code=1,
        stdout_bytes=b"",
        stderr_bytes=b"",
        wall_time_seconds=0.5,
        timed_out=False,
        invocation_command=["seqsender"],
    )
    with _patch_run_seqsender(failed):
        await execute_submission(sub_id)
    expected = temp_working_root / f"submission_{sub_id}_attempt_1"
    assert expected.exists(), f"working dir {expected} should be preserved on failure"


# ── timeout path ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_timeout_transitions_to_failed_with_timeout_message(
    temp_working_root, captured_uploads
):
    sub_id = _make_executing_submission("TIMEOUT")
    timeout = SeqsenderRunResult(
        exit_code=-9,
        stdout_bytes=b"",
        stderr_bytes=b"",
        wall_time_seconds=3600.0,
        timed_out=True,
        invocation_command=["seqsender"],
    )
    with _patch_run_seqsender(timeout):
        result = await execute_submission(sub_id)

    assert result["failed"] == 1
    assert result["timed_out"] == 1
    row = _row(sub_id)
    assert row["status"] == "EXECUTION_FAILED"
    assert "timeout" in (row["execution_error_message"] or "").lower()


# ── unsupported repo path ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unsupported_repo_ena_fails_without_subprocess(temp_working_root, captured_uploads):
    sub_id = _make_executing_submission("ENA", target_repository="ENA")

    with patch("backend.jobs.run_seqsender", AsyncMock()) as mocked:
        result = await execute_submission(sub_id)

    assert result == {"unsupported_repo": 1}
    mocked.assert_not_called()
    row = _row(sub_id)
    assert row["status"] == "EXECUTION_FAILED"
    msg = row["execution_error_message"] or ""
    assert "ENA" in msg
    assert "Webin-CLI" in msg


@pytest.mark.asyncio
async def test_unsupported_repo_gisaid_fails_without_subprocess(
    temp_working_root, captured_uploads
):
    sub_id = _make_executing_submission("GISAID", target_repository="GISAID_EPICOV")

    with patch("backend.jobs.run_seqsender", AsyncMock()) as mocked:
        result = await execute_submission(sub_id)

    assert result == {"unsupported_repo": 1}
    mocked.assert_not_called()
    row = _row(sub_id)
    assert row["status"] == "EXECUTION_FAILED"
    assert "not supported" in (row["execution_error_message"] or "").lower()


# ── defensive: wrong status ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_wrong_status_refuses_to_run():
    sub_id = _make_executing_submission("WRONG-STATUS")
    execute_write("UPDATE submissions SET status = 'DRAFT' WHERE id = :id", {"id": sub_id})
    with patch("backend.jobs.run_seqsender", AsyncMock()) as mocked:
        result = await execute_submission(sub_id)
    assert result == {"wrong_status": 1}
    mocked.assert_not_called()
    row = _row(sub_id)
    assert row["status"] == "DRAFT"  # untouched


# ── missing package path ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_missing_package_path_fails_clearly():
    sub_id = _make_executing_submission("NO-PKG", package_path="")
    execute_write("UPDATE submissions SET package_path = NULL WHERE id = :id", {"id": sub_id})
    with patch("backend.jobs.run_seqsender", AsyncMock()) as mocked:
        result = await execute_submission(sub_id)
    assert result == {"missing_package": 1}
    mocked.assert_not_called()
    row = _row(sub_id)
    assert row["status"] == "EXECUTION_FAILED"
    assert "package_path" in (row["execution_error_message"] or "")


# ── credential redaction in captured log ─────────────────────────────


@pytest.mark.asyncio
async def test_credential_values_not_in_uploaded_log(temp_working_root, captured_uploads):
    """End-to-end redaction: stub Seqsender to deliberately echo the
    NCBI credential values in stdout/stderr (simulating a misbehaving
    executor). Verify the bytes that would have been uploaded contain
    no credential value, and that ***REDACTED*** appears."""
    sub_id = _make_executing_submission("REDACT")
    leaky = SeqsenderRunResult(
        exit_code=0,
        stdout_bytes=(
            b"Connecting with submitter@example.org\nAuthentication: ncbi-test-secret\nDone.\n"
        ),
        stderr_bytes=b"Reminder: ncbi-test-secret was used\n",
        wall_time_seconds=1.0,
        timed_out=False,
        invocation_command=["seqsender", "submit"],
    )
    with _patch_run_seqsender(leaky):
        await execute_submission(sub_id)

    assert len(captured_uploads) == 1
    log_bytes = captured_uploads[0]["content"]
    # Neither credential value may appear anywhere in the log content.
    assert b"submitter@example.org" not in log_bytes
    assert b"ncbi-test-secret" not in log_bytes
    assert b"***REDACTED***" in log_bytes


# ── log_uri append correctness across attempts ───────────────────────


@pytest.mark.asyncio
async def test_log_uri_appended_across_retries(temp_working_root, captured_uploads):
    sub_id = _make_executing_submission("RETRY-APPEND")

    # Attempt 1 fails.
    failed = SeqsenderRunResult(
        exit_code=1,
        stdout_bytes=b"",
        stderr_bytes=b"",
        wall_time_seconds=0.5,
        timed_out=False,
        invocation_command=["seqsender"],
    )
    with _patch_run_seqsender(failed):
        await execute_submission(sub_id)

    row = _row(sub_id)
    assert row["status"] == "EXECUTION_FAILED"
    assert len(row["execution_log_uris"]) == 1

    # Operator retries: re-queue (use the I-3a transition) then re-execute.
    from backend.submissions import mark_execution_retried

    with get_db() as db:
        mark_execution_retried(
            submission_id=sub_id,
            executor_backend="seqsender_subprocess",
            actor_id=SEED_USER_ID,
            conn=db,
        )

    # Attempt 2 succeeds.
    with _patch_run_seqsender():
        await execute_submission(sub_id)

    row = _row(sub_id)
    assert row["status"] == "SUBMITTED"
    assert len(row["execution_log_uris"]) == 2  # both attempts logged
    assert row["execution_attempt_count"] == 2


# ── per-repo concurrency: NCBI serializes, NCBI+ENA parallel ──────────


@pytest.mark.asyncio
async def test_two_ncbi_submissions_serialize(temp_working_root, captured_uploads):
    """Two NCBI submissions queued concurrently — observe that the second
    only starts after the first finishes, by recording timestamps from
    a fake run_seqsender."""
    sub_a = _make_executing_submission("CONC-A")
    sub_b = _make_executing_submission("CONC-B")

    timestamps: list[tuple[str, float]] = []
    inflight_event = asyncio.Event()
    release_event = asyncio.Event()

    async def fake_run(*args, **kwargs):
        # Record the moment we enter, then block until released.
        marker = "A" if "CONC-A" in str(kwargs.get("package_dir", "")) else "B"
        # The package_dir paths in the test rows include sub IDs but not
        # markers; instead, infer order by enter timing alone.
        marker = f"enter@{asyncio.get_event_loop().time():.4f}"
        timestamps.append((marker, asyncio.get_event_loop().time()))
        if not inflight_event.is_set():
            inflight_event.set()
        await release_event.wait()
        return SeqsenderRunResult(
            exit_code=0,
            stdout_bytes=b"",
            stderr_bytes=b"",
            wall_time_seconds=0.1,
            timed_out=False,
            invocation_command=["seqsender"],
        )

    with patch("backend.jobs.run_seqsender", AsyncMock(side_effect=fake_run)):
        task_a = asyncio.create_task(execute_submission(sub_a))
        # Wait until A is inside the lock + fake_run, then start B.
        await inflight_event.wait()
        task_b = asyncio.create_task(execute_submission(sub_b))
        # Give B a chance to be scheduled if the lock weren't blocking.
        await asyncio.sleep(0.05)
        # Only one timestamp recorded so far — B is blocked on the lock.
        assert len(timestamps) == 1, f"expected serialization; got {timestamps}"
        # Release A; B should then enter.
        release_event.set()
        await asyncio.gather(task_a, task_b)

    assert len(timestamps) == 2
    # And both submissions reach SUBMITTED.
    for sid in (sub_a, sub_b):
        assert _row(sid)["status"] == "SUBMITTED"


@pytest.mark.asyncio
async def test_ncbi_and_ena_run_concurrently(temp_working_root, captured_uploads):
    """ENA short-circuits without subprocess; one NCBI submission can run
    while ENA is being rejected. They use different repo locks anyway, so
    even when ENA grows a real executor they will run in parallel."""
    sub_ncbi = _make_executing_submission("PARA-NCBI", target_repository="NCBI")
    sub_ena = _make_executing_submission("PARA-ENA", target_repository="ENA")

    with _patch_run_seqsender():
        results = await asyncio.gather(
            execute_submission(sub_ncbi),
            execute_submission(sub_ena),
        )

    assert results[0] == {"completed": 1}
    assert results[1] == {"unsupported_repo": 1}
    assert _row(sub_ncbi)["status"] == "SUBMITTED"
    assert _row(sub_ena)["status"] == "EXECUTION_FAILED"


# ── working dir naming uses attempt number ───────────────────────────


@pytest.mark.asyncio
async def test_working_dir_name_includes_attempt(temp_working_root, captured_uploads):
    sub_id = _make_executing_submission("WD-NAME")
    # First attempt uses attempt=1.
    failed = SeqsenderRunResult(
        exit_code=1,
        stdout_bytes=b"",
        stderr_bytes=b"",
        wall_time_seconds=0.1,
        timed_out=False,
        invocation_command=["s"],
    )
    with _patch_run_seqsender(failed):
        await execute_submission(sub_id)
    assert (temp_working_root / f"submission_{sub_id}_attempt_1").exists()

    from backend.submissions import mark_execution_retried

    with get_db() as db:
        mark_execution_retried(
            submission_id=sub_id,
            executor_backend="seqsender_subprocess",
            actor_id=SEED_USER_ID,
            conn=db,
        )
    with _patch_run_seqsender():
        await execute_submission(sub_id)
    # Attempt 2 succeeds and gets cleaned up.
    assert not (temp_working_root / f"submission_{sub_id}_attempt_2").exists()
    # Attempt 1's preserved directory is still there.
    assert (temp_working_root / f"submission_{sub_id}_attempt_1").exists()


# ── config file always deleted, even on failure ──────────────────────


@pytest.mark.asyncio
async def test_config_file_always_deleted(temp_working_root, captured_uploads, monkeypatch):
    """Capture the config path written by write_seqsender_config and
    assert it's gone after execute_submission returns, regardless of
    success/failure."""
    sub_id = _make_executing_submission("CFG-DELETE")
    captured_paths: list[Path] = []

    from backend.submission_executors import seqsender as ssmod

    real_writer = ssmod.write_seqsender_config

    def spy(**kwargs):
        path, values = real_writer(**kwargs)
        captured_paths.append(path)
        return path, values

    monkeypatch.setattr("backend.jobs.write_seqsender_config", spy)

    failed = SeqsenderRunResult(
        exit_code=1,
        stdout_bytes=b"",
        stderr_bytes=b"",
        wall_time_seconds=0.1,
        timed_out=False,
        invocation_command=["s"],
    )
    with _patch_run_seqsender(failed):
        await execute_submission(sub_id)

    assert len(captured_paths) == 1
    assert not captured_paths[
        0
    ].exists(), f"config file {captured_paths[0]} should have been deleted"
