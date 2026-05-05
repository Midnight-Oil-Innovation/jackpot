"""I-3c: ``POST /api/v1/submissions/{id}/execute`` pre-flight gates + 202 path."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.config import get_settings
from backend.credentials import _reset_backend, _set_backend
from backend.credentials.test_helpers import InMemoryBackend
from backend.database import execute_query, execute_write

SEED_USER_ID = 1
SEED_LAB_ID = 1
SAMPLE_PREFIX = "I3C-EXEC-S-"
SUB_PREFIX = "I3C-EXEC-"


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


def _make_submission(
    suffix: str,
    *,
    target_repository: str = "NCBI",
    status: str = "READY_TO_SUBMIT",
) -> int:
    sample_id = _insert_sample(f"{SAMPLE_PREFIX}{suffix}")
    rows = execute_write(
        """
        INSERT INTO submissions (
            created_by_user_id, lab_id, target_repository, title, status,
            package_path
        ) VALUES (
            :uid, :lid, :repo, :title, :status, :pkg
        ) RETURNING id
        """,
        {
            "uid": SEED_USER_ID,
            "lid": SEED_LAB_ID,
            "repo": target_repository,
            "title": f"{SUB_PREFIX}{suffix}",
            "status": status,
            "pkg": f"/tmp/jackpot-test/{suffix}",
        },
    )
    sub_id = rows[0]["id"]
    execute_write(
        """
        INSERT INTO submission_samples (submission_id, sample_id_fk)
        VALUES (:sub, :sid)
        """,
        {"sub": sub_id, "sid": sample_id},
    )
    return sub_id


def _row(sub_id: int) -> dict:
    return execute_query("SELECT * FROM submissions WHERE id = :id", {"id": sub_id})[0]


@pytest.fixture(autouse=True)
def _set_backend_creds(monkeypatch):
    """Populate NCBI credentials in the in-memory backend so the
    pre-flight credential check passes by default."""
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
    """Enable backend execution for NCBI in the deployment."""
    monkeypatch.setenv("ALLOW_BACKEND_SUBMISSION", "true")
    monkeypatch.setenv("BACKEND_SUBMISSION_REPOS", "ncbi")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def fake_scheduler():
    """Replace the lazily-imported scheduler so add_job calls don't try
    to reach a running event loop. We assert on the recorded call later."""
    fake = MagicMock()
    with patch("backend.main.scheduler", fake):
        yield fake


# ── 202 success path ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_202_path(client, enabled, fake_scheduler):
    sub_id = _make_submission("OK")
    resp = await client.post(f"/api/v1/submissions/{sub_id}/execute")
    assert resp.status_code == 202, resp.text
    body = resp.json()["data"]
    assert body["status"] == "EXECUTING"
    assert body["execution_attempt_count"] == 1
    fake_scheduler.add_job.assert_called_once()
    _, kwargs = fake_scheduler.add_job.call_args
    assert kwargs["args"] == [sub_id]
    assert "attempt_1" in kwargs["id"]


@pytest.mark.asyncio
async def test_execute_with_optional_executor_backend(client, enabled, fake_scheduler):
    sub_id = _make_submission("OK-BODY")
    resp = await client.post(
        f"/api/v1/submissions/{sub_id}/execute",
        json={"executor_backend": "seqsender_subprocess"},
    )
    assert resp.status_code == 202


# ── BACKEND_EXECUTION_DISABLED ───────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_disabled_globally(client, fake_scheduler, monkeypatch):
    monkeypatch.setenv("ALLOW_BACKEND_SUBMISSION", "false")
    get_settings.cache_clear()
    sub_id = _make_submission("DIS")
    resp = await client.post(f"/api/v1/submissions/{sub_id}/execute")
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["detail"]["error_code"] == "BACKEND_EXECUTION_DISABLED"
    fake_scheduler.add_job.assert_not_called()


# ── REPO_NOT_ENABLED ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_repo_not_in_enabled_list(client, fake_scheduler, monkeypatch):
    monkeypatch.setenv("ALLOW_BACKEND_SUBMISSION", "true")
    monkeypatch.setenv("BACKEND_SUBMISSION_REPOS", "ena")  # NCBI not enabled
    get_settings.cache_clear()
    sub_id = _make_submission("NOT-ENABLED")
    resp = await client.post(f"/api/v1/submissions/{sub_id}/execute")
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["detail"]["error_code"] == "REPO_NOT_ENABLED"


# ── REPO_NOT_SUPPORTED ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_gisaid_unsupported(client, enabled, fake_scheduler):
    sub_id = _make_submission("GISAID", target_repository="GISAID_EPICOV")
    resp = await client.post(f"/api/v1/submissions/{sub_id}/execute")
    assert resp.status_code == 409
    body = resp.json()
    # GISAID isn't in backend_submission_repos either, so REPO_NOT_ENABLED
    # fires first per the documented gate ordering.
    assert body["error"]["detail"]["error_code"] in {
        "REPO_NOT_ENABLED",
        "REPO_NOT_SUPPORTED",
    }


@pytest.mark.asyncio
async def test_execute_ddbj_unsupported_when_enabled(client, fake_scheduler, monkeypatch):
    """If the operator enabled DDBJ in backend_submission_repos (which
    the predicate doesn't validate against the supported set), the
    REPO_NOT_SUPPORTED gate catches it."""
    monkeypatch.setenv("ALLOW_BACKEND_SUBMISSION", "true")
    monkeypatch.setenv("BACKEND_SUBMISSION_REPOS", "ddbj")
    get_settings.cache_clear()
    sub_id = _make_submission("DDBJ", target_repository="DDBJ")
    resp = await client.post(f"/api/v1/submissions/{sub_id}/execute")
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["detail"]["error_code"] == "REPO_NOT_SUPPORTED"


# ── INVALID_STATE ────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    ["DRAFT", "SUBMITTED", "ACCEPTED", "EMBARGOED", "WITHDRAWN", "EXECUTING"],
)
async def test_execute_rejects_wrong_status(client, enabled, fake_scheduler, status):
    sub_id = _make_submission(f"BAD-{status}", status=status)
    resp = await client.post(f"/api/v1/submissions/{sub_id}/execute")
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["detail"]["error_code"] == "INVALID_STATE"


# ── MISSING_CREDENTIALS ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_missing_credentials(client, enabled, fake_scheduler):
    # Re-bind backend without the password — username present but
    # password missing should still raise MISSING_CREDENTIALS naming
    # exactly the missing keys.
    backend = InMemoryBackend({"ncbi_submission_username": "submitter@example.org"})
    _set_backend(backend)
    try:
        sub_id = _make_submission("MISS-CRED")
        resp = await client.post(f"/api/v1/submissions/{sub_id}/execute")
        assert resp.status_code == 400, resp.text
        body = resp.json()
        assert body["error"]["detail"]["error_code"] == "MISSING_CREDENTIALS"
        assert "ncbi_submission_password" in body["error"]["detail"]["missing_keys"]
        fake_scheduler.add_job.assert_not_called()
    finally:
        _reset_backend()


# ── 404 not found ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_unknown_submission(client, enabled, fake_scheduler):
    resp = await client.post("/api/v1/submissions/99999999/execute")
    assert resp.status_code == 404
