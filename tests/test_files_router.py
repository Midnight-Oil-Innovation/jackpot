# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""HTTP-level tests for /api/v1/files/ endpoints (Phase P0f F-9).

The promote endpoint is exercised in QUEUED-only mode here — the
copy-job logic has its own unit tests in
``tests/test_jobs_promote.py``. Endpoint tests assert transition
validation, visibility scoping, error envelopes, and audit emission.
"""

from __future__ import annotations

import uuid

import pytest

from backend.config import get_settings
from backend.database import execute_query, execute_write

SEED_USER_ID = 1
SEED_LAB_ID = 1
SEED_PROJECT_ID = 1


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _switch_user(email: str, monkeypatch) -> None:
    monkeypatch.setenv("MOCK_USER_EMAIL", email)
    get_settings.cache_clear()


@pytest.fixture
def as_platform_admin(monkeypatch):
    _switch_user("admin@example.org", monkeypatch)


def _insert_sample(sample_id: str, *, lab_id: int = SEED_LAB_ID) -> dict:
    rows = execute_write(
        """
        INSERT INTO samples
            (sample_id, lab_id, project_id, owner_id, source_type, organism_name,
             type_of_experiment, library_preparation_method, sequencing_protocol,
             sequencing_platform, sequencing_lab, date_collected, date_sequenced,
             collection_facility, collection_location_country, sharing_level,
             fastq_r1_uri, scrub_status, quality_status)
        VALUES
            (:sid, :lid, :pid, :oid, 'Human',
             'Severe acute respiratory syndrome coronavirus 2',
             'WGS', 'ARTIC', 'https://www.protocols.io/view/artic-v4-1',
             'Illumina', 'Example Sequencing Lab', '2026-01-15', '2026-01-17',
             'Example Hospital', 'United States', 'PRIVATE',
             'gs://jackpot-sequences/test/R1.fastq.gz', 'COMPLETE', 'ANALYZABLE')
        RETURNING *
        """,
        {"sid": sample_id, "lid": lab_id, "pid": SEED_PROJECT_ID, "oid": SEED_USER_ID},
    )
    return rows[0]


def _insert_sample_file(
    *,
    sample_pk: int,
    uri: str,
    storage_state: str = "EXTERNAL",
    file_size_bytes: int | None = None,
    last_verification_status: str | None = None,
    staged_for_run_id: str | None = None,
) -> int:
    if storage_state in ("MANAGED", "STAGED") and file_size_bytes is None:
        file_size_bytes = 1024
    if storage_state == "STAGED" and staged_for_run_id is None:
        staged_for_run_id = uuid.uuid4().hex
    rows = execute_write(
        "INSERT INTO sample_files "
        "    (sample_id_fk, uri, filename, file_type, library_layout, "
        "     storage_state, file_size_bytes, last_verification_status, "
        "     staged_for_run_id) "
        "VALUES (:sid, :uri, :fn, 'FASTQ', 'PAIRED', "
        "        CAST(:state AS file_storage_state), :sz, :lvs, "
        "        CAST(:run_id AS UUID)) "
        "RETURNING id",
        {
            "sid": sample_pk,
            "uri": uri,
            "fn": uri.rsplit("/", 1)[-1],
            "state": storage_state,
            "sz": file_size_bytes,
            "lvs": last_verification_status,
            "run_id": staged_for_run_id,
        },
    )
    return rows[0]["id"]


def _cleanup_samples(prefix: str) -> None:
    rows = execute_query(
        "SELECT id FROM samples WHERE sample_id LIKE :p",
        {"p": f"{prefix}%"},
    )
    for r in rows:
        sid = r["id"]
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type IN ('sample','sample_files') "
            "AND resource_id IN (SELECT id::text FROM sample_files WHERE sample_id_fk = :s)",
            {"s": sid},
        )
        execute_write("DELETE FROM sample_files WHERE sample_id_fk = :s", {"s": sid})
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'sample' AND resource_id = :rid",
            {"rid": str(sid)},
        )
        execute_write("DELETE FROM samples WHERE id = :id", {"id": sid})


# ── POST /{file_id}/promote — transition validation ─────────────────────


@pytest.mark.asyncio
async def test_promote_external_to_managed_returns_202(client, as_platform_admin):
    prefix = _unique("PRO")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    file_id = _insert_sample_file(
        sample_pk=sample["id"],
        uri=f"file:///srv/seq/{prefix}/R1.fastq.gz",
        file_size_bytes=200 * 1024 * 1024,
    )
    try:
        resp = await client.post(
            f"/api/v1/files/{file_id}/promote",
            json={"to": "MANAGED"},
        )
        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["file_id"] == file_id
        assert data["current_state"] == "EXTERNAL"
        assert data["target_state"] == "MANAGED"
        assert data["status"] == "QUEUED"
        assert data["job_id"].startswith(f"promote_{file_id}_")
        # ~100 MB/s → 200 MB → ~2 seconds
        assert data["estimated_seconds"] >= 1
        # PROMOTE_FILE audit row written
        audit = execute_query(
            "SELECT action, after_state FROM audit_log "
            "WHERE resource_type = 'sample_files' AND resource_id = :rid "
            "ORDER BY id DESC LIMIT 1",
            {"rid": str(file_id)},
        )
        assert audit[0]["action"] == "PROMOTE_FILE"
    finally:
        _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_promote_external_to_mirrored_returns_202(client, as_platform_admin):
    prefix = _unique("PRO")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-B")
    file_id = _insert_sample_file(
        sample_pk=sample["id"], uri=f"file:///srv/seq/{prefix}/R1.fastq.gz"
    )
    try:
        resp = await client.post(
            f"/api/v1/files/{file_id}/promote",
            json={"to": "MIRRORED", "retention_policy": "LONG_TERM"},
        )
        assert resp.status_code == 202, resp.text
        data = resp.json()["data"]
        assert data["target_state"] == "MIRRORED"
        assert data["retention_policy"] == "LONG_TERM"
    finally:
        _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_promote_managed_to_managed_returns_409(client, as_platform_admin):
    prefix = _unique("PRO")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-C")
    file_id = _insert_sample_file(
        sample_pk=sample["id"],
        uri=f"file:///srv/seq/{prefix}/R1.fastq.gz",
        storage_state="MANAGED",
    )
    try:
        resp = await client.post(f"/api/v1/files/{file_id}/promote", json={"to": "MANAGED"})
        assert resp.status_code == 409, resp.text
        assert resp.json()["error"]["code"] == "ALREADY_IN_TARGET_STATE"
    finally:
        _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_promote_broken_returns_422(client, as_platform_admin):
    prefix = _unique("PRO")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-D")
    file_id = _insert_sample_file(
        sample_pk=sample["id"],
        uri=f"file:///srv/seq/{prefix}/R1.fastq.gz",
        storage_state="BROKEN",
        last_verification_status="MISSING_3",
    )
    try:
        resp = await client.post(f"/api/v1/files/{file_id}/promote", json={"to": "MANAGED"})
        assert resp.status_code == 422, resp.text
        assert resp.json()["error"]["code"] == "INVALID_TRANSITION"
    finally:
        _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_promote_staged_returns_422(client, as_platform_admin):
    prefix = _unique("PRO")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-E")
    file_id = _insert_sample_file(
        sample_pk=sample["id"],
        uri=f"file:///srv/seq/{prefix}/R1.fastq.gz",
        storage_state="STAGED",
        file_size_bytes=1024,
    )
    try:
        resp = await client.post(f"/api/v1/files/{file_id}/promote", json={"to": "MANAGED"})
        assert resp.status_code == 422, resp.text
        assert resp.json()["error"]["code"] == "INVALID_TRANSITION"
    finally:
        _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_promote_target_external_returns_422(client, as_platform_admin):
    prefix = _unique("PRO")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-F")
    file_id = _insert_sample_file(
        sample_pk=sample["id"], uri=f"file:///srv/seq/{prefix}/R1.fastq.gz"
    )
    try:
        resp = await client.post(f"/api/v1/files/{file_id}/promote", json={"to": "EXTERNAL"})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INVALID_TRANSITION"
    finally:
        _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_promote_invalid_retention_returns_422(client, as_platform_admin):
    prefix = _unique("PRO")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-G")
    file_id = _insert_sample_file(
        sample_pk=sample["id"], uri=f"file:///srv/seq/{prefix}/R1.fastq.gz"
    )
    try:
        resp = await client.post(
            f"/api/v1/files/{file_id}/promote",
            json={"to": "MANAGED", "retention_policy": "FOREVER"},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    finally:
        _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_promote_nonexistent_file_returns_404(client, as_platform_admin):
    resp = await client.post("/api/v1/files/999999999/promote", json={"to": "MANAGED"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "FILE_NOT_FOUND"


# ── GET /{file_id} ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_file_returns_full_row_with_referencing_sample(client, as_platform_admin):
    prefix = _unique("GET")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    file_id = _insert_sample_file(
        sample_pk=sample["id"], uri=f"file:///srv/seq/{prefix}/R1.fastq.gz"
    )
    try:
        resp = await client.get(f"/api/v1/files/{file_id}")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["id"] == file_id
        assert data["storage_state"] == "EXTERNAL"
        # The referenced sample appears in the embedded list
        assert isinstance(data.get("samples"), list)
        assert any(s.get("sample_id") == f"{prefix}-A" for s in data["samples"])
    finally:
        _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_get_file_404_for_missing(client, as_platform_admin):
    resp = await client.get("/api/v1/files/999999999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "FILE_NOT_FOUND"


# ── GET / (list) ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_files_filters_by_storage_state(client, as_platform_admin):
    prefix = _unique("LST")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    ext_id = _insert_sample_file(
        sample_pk=sample["id"], uri=f"file:///srv/seq/{prefix}/ext.fastq.gz"
    )
    mng_id = _insert_sample_file(
        sample_pk=sample["id"],
        uri=f"file:///srv/seq/{prefix}/mng.fastq.gz",
        storage_state="MANAGED",
    )
    try:
        resp = await client.get(
            "/api/v1/files/", params={"storage_state": "MANAGED", "sample_id": sample["id"]}
        )
        assert resp.status_code == 200, resp.text
        ids = {row["id"] for row in resp.json()["data"]}
        assert mng_id in ids
        assert ext_id not in ids
    finally:
        _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_list_files_invalid_storage_state_returns_422(client, as_platform_admin):
    resp = await client.get("/api/v1/files/", params={"storage_state": "WRONG"})
    assert resp.status_code == 422


# ── POST /{file_id}/verify ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_file_returns_status_and_audit(client, as_platform_admin, tmp_path):
    prefix = _unique("VER")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    real = tmp_path / f"{prefix}.fastq.gz"
    real.write_bytes(b"GATTACA" * 1000)
    file_id = _insert_sample_file(
        sample_pk=sample["id"],
        uri=str(real),
        file_size_bytes=real.stat().st_size,
    )
    try:
        resp = await client.post(f"/api/v1/files/{file_id}/verify")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["file_id"] == file_id
        assert data["last_verification_status"] == "OK"
        # Audit entry recorded the trigger
        audit = execute_query(
            "SELECT action FROM audit_log "
            "WHERE resource_type = 'sample_files' AND resource_id = :rid "
            "ORDER BY id DESC LIMIT 1",
            {"rid": str(file_id)},
        )
        assert audit[0]["action"] == "VERIFY_FILE_TRIGGERED"
    finally:
        _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_verify_missing_file_increments_failure_status(client, as_platform_admin, tmp_path):
    prefix = _unique("VER")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-B")
    file_id = _insert_sample_file(
        sample_pk=sample["id"], uri=str(tmp_path / "does-not-exist.fastq.gz")
    )
    try:
        resp = await client.post(f"/api/v1/files/{file_id}/verify")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        # First strike — status reflects MISSING but row stays EXTERNAL
        assert data["last_verification_status"] == "MISSING"
        assert data["storage_state"] == "EXTERNAL"
    finally:
        _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_verify_nonexistent_file_returns_404(client, as_platform_admin):
    resp = await client.post("/api/v1/files/999999999/verify")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "FILE_NOT_FOUND"


# ── GET /jobs/{job_id} ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_promote_job_status_404_for_unknown(client, as_platform_admin):
    resp = await client.get("/api/v1/files/jobs/promote_1_unknown")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "JOB_NOT_FOUND"


@pytest.mark.asyncio
async def test_promote_job_status_returns_queued_after_promote(client, as_platform_admin):
    """The QUEUED entry recorded by the endpoint when the scheduler
    isn't running is readable from /jobs/{job_id} immediately."""
    prefix = _unique("JOB")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    file_id = _insert_sample_file(
        sample_pk=sample["id"], uri=f"file:///srv/seq/{prefix}/R1.fastq.gz"
    )
    try:
        resp = await client.post(f"/api/v1/files/{file_id}/promote", json={"to": "MANAGED"})
        assert resp.status_code == 202
        job_id = resp.json()["data"]["job_id"]

        status_resp = await client.get(f"/api/v1/files/jobs/{job_id}")
        assert status_resp.status_code == 200, status_resp.text
        body = status_resp.json()["data"]
        assert body["job_id"] == job_id
        assert body["status"] == "QUEUED"
        assert body["file_id"] == file_id
    finally:
        _cleanup_samples(prefix)
