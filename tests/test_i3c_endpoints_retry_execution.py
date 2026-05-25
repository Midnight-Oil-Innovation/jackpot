"""I-3c: ``POST /api/v1/submissions/{id}/retry-execution`` gate matrix."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.config import get_settings
from backend.credentials import _reset_backend, _set_backend
from backend.credentials.test_helpers import InMemoryBackend
from backend.database import execute_query, execute_write

SEED_USER_ID = 1
SEED_LAB_ID = 1
SAMPLE_PREFIX = "I3C-RETRY-S-"
SUB_PREFIX = "I3C-RETRY-"


def _cleanup() -> None:
    rows = execute_query("SELECT id FROM submissions WHERE title LIKE :p", {"p": f"{SUB_PREFIX}%"})
    for r in rows:
        sid = r["id"]
        execute_write("DELETE FROM submission_samples WHERE submission_id = :id", {"id": sid})
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
        "SELECT id FROM samples WHERE sample_id LIKE :p", {"p": f"{SAMPLE_PREFIX}%"}
    )
    for r in rows:
        sid = r["id"]
        execute_write("DELETE FROM submission_samples WHERE sample_id_fk = :id", {"id": sid})
        execute_write("DELETE FROM sample_files WHERE sample_id_fk = :id", {"id": sid})
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
            :sample_id, :lab_id, 1, :owner_id, 'Human',
            'Severe acute respiratory syndrome coronavirus 2', 'WGS',
            'ARTIC', 'https://www.protocols.io/view/artic-v4-1', 'Illumina',
            'Example Sequencing Lab', '2026-01-15', '2026-01-17',
            'Example Hospital', 'United States', 'PRIVATE',
            'gs://test/R1.fq.gz', FALSE
        ) RETURNING id
        """,
        {"sample_id": sample_id, "lab_id": SEED_LAB_ID, "owner_id": SEED_USER_ID},
    )
    return rows[0]["id"]


def _make_submission(suffix: str, *, status: str) -> int:
    sample_id = _insert_sample(f"{SAMPLE_PREFIX}{suffix}")
    rows = execute_write(
        """
        INSERT INTO submissions (
            created_by_user_id, lab_id, target_repository, title, status,
            package_path, execution_attempt_count, executor_backend,
            execution_error_message
        ) VALUES (
            :uid, :lid, 'NCBI', :title, :status, :pkg, 1,
            'seqsender_subprocess', 'previous failure'
        ) RETURNING id
        """,
        {
            "uid": SEED_USER_ID,
            "lid": SEED_LAB_ID,
            "title": f"{SUB_PREFIX}{suffix}",
            "status": status,
            "pkg": f"/tmp/jackpot-test/{suffix}",
        },
    )
    sub_id = rows[0]["id"]
    execute_write(
        "INSERT INTO submission_samples (submission_id, sample_id_fk) VALUES (:sub, :sid)",
        {"sub": sub_id, "sid": sample_id},
    )
    return sub_id


@pytest.fixture(autouse=True)
def _set_backend_creds():
    _cleanup()
    backend = InMemoryBackend(
        {
            "ncbi_submission_username": "submitter@example.org",
            "ncbi_submission_password": "secret-test",
        }
    )
    _set_backend(backend)
    yield backend
    _reset_backend()
    _cleanup()


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("ALLOW_BACKEND_SUBMISSION", "true")
    monkeypatch.setenv("BACKEND_SUBMISSION_REPOS", "ncbi")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def fake_scheduler():
    fake = MagicMock()
    with patch("backend.main.scheduler", fake):
        yield fake


@pytest.mark.asyncio
@pytest.mark.parametrize("starting_status", ["EXECUTION_FAILED", "EXECUTION_INTERRUPTED"])
async def test_retry_202_path(client, enabled, fake_scheduler, starting_status):
    sub_id = _make_submission(f"OK-{starting_status}", status=starting_status)
    resp = await client.post(f"/api/v1/submissions/{sub_id}/retry-execution")
    assert resp.status_code == 202, resp.text
    body = resp.json()["data"]
    assert body["status"] == "EXECUTING"
    # Attempt count was 1 going in; retry increments to 2.
    assert body["execution_attempt_count"] == 2
    fake_scheduler.add_job.assert_called_once()
    _, kwargs = fake_scheduler.add_job.call_args
    assert kwargs["args"] == [sub_id]
    assert "attempt_2" in kwargs["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "starting_status",
    ["DRAFT", "READY_TO_SUBMIT", "SUBMITTED", "ACCEPTED", "EMBARGOED", "EXECUTING"],
)
async def test_retry_rejects_non_failure_states(client, enabled, fake_scheduler, starting_status):
    sub_id = _make_submission(f"BAD-{starting_status}", status=starting_status)
    resp = await client.post(f"/api/v1/submissions/{sub_id}/retry-execution")
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["detail"]["error_code"] == "INVALID_STATE"
    fake_scheduler.add_job.assert_not_called()


@pytest.mark.asyncio
async def test_retry_disabled_globally(client, fake_scheduler, monkeypatch):
    monkeypatch.setenv("ALLOW_BACKEND_SUBMISSION", "false")
    get_settings.cache_clear()
    sub_id = _make_submission("DIS", status="EXECUTION_FAILED")
    resp = await client.post(f"/api/v1/submissions/{sub_id}/retry-execution")
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["detail"]["error_code"] == "BACKEND_EXECUTION_DISABLED"


@pytest.mark.asyncio
async def test_retry_missing_credentials(client, enabled, fake_scheduler):
    backend = InMemoryBackend()  # neither cred present
    _set_backend(backend)
    try:
        sub_id = _make_submission("MISS-CRED", status="EXECUTION_FAILED")
        resp = await client.post(f"/api/v1/submissions/{sub_id}/retry-execution")
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["detail"]["error_code"] == "MISSING_CREDENTIALS"
        assert set(body["error"]["detail"]["missing_keys"]) == {
            "ncbi_submission_username",
            "ncbi_submission_password",
        }
    finally:
        _reset_backend()


@pytest.mark.asyncio
async def test_retry_unknown_submission(client, enabled, fake_scheduler):
    resp = await client.post("/api/v1/submissions/99999999/retry-execution")
    assert resp.status_code == 404
