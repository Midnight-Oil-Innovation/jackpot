"""Tests for POST /api/v1/ingest/register (Phase P0f F-6).

Covers happy path, dedup, behavior under MANAGED/MIRRORED intent (the
copy itself is F-9 — F-6 only sets the storage_state flag), file-
unreachable handling, transactional rollback on partial failure, audit
log writes, and request-shape validation.
"""

import pytest

from backend.database import execute_query, execute_write


def _cleanup_sample(sample_id: str) -> None:
    execute_write(
        "DELETE FROM sample_files WHERE sample_id_fk IN "
        "(SELECT id FROM samples WHERE sample_id = :s)",
        {"s": sample_id},
    )
    execute_write(
        "UPDATE audit_log SET actor_id = NULL "
        "WHERE resource_type = 'sample' AND resource_id IN "
        "(SELECT id::text FROM samples WHERE sample_id = :s)",
        {"s": sample_id},
    )
    execute_write("DELETE FROM samples WHERE sample_id = :s", {"s": sample_id})


@pytest.fixture
def fastq_files(tmp_path):
    """Create two real FASTQ files we can fingerprint deterministically."""
    r1 = tmp_path / "REG-R1.fastq"
    r2 = tmp_path / "REG-R2.fastq"
    r1.write_bytes(b"@SEQ1\nACGTACGT\n+\nIIIIIIII\n" * 200)
    r2.write_bytes(b"@SEQ2\nTGCATGCA\n+\nIIIIIIII\n" * 200)
    return r1, r2


def _base_metadata(sample_id: str) -> dict:
    return {
        "sample_id": sample_id,
        "organism_name": "Severe acute respiratory syndrome coronavirus 2",
        "source_type": "Human",
        "date_collected": "2026-01-15",
        "date_collected_precision": "day",
        "date_sequenced": "2026-01-17",
        "collection_location_country": "United States",
        "collection_location_state": "California",
        "sequencing_platform": "Illumina",
        "sequencing_lab": "Example Sequencing Lab",
        "type_of_experiment": "WGS",
        "library_preparation_method": "ARTIC",
        "nucleic_acid_extraction_method": ["QIAamp DSP Viral RNA"],
        "sequencing_protocol": "https://www.protocols.io/view/artic-v4-1",
        "collection_facility": "Example Hospital",
        "purpose_for_collection": ["clinical"],
        "sharing_level": "PRIVATE",
        "external_case_id": "CASE-REG-001",
        "biospecimen_type": "nasopharyngeal_swab",
        "reason_for_collection": ["clinical"],
        "host_disease": ["covid-19"],
        "project_id": 1,
        "lab_id": 1,
    }


@pytest.mark.asyncio
async def test_register_single_file_external(client, fastq_files):
    r1, _r2 = fastq_files
    sid = "REG-EXT-001"
    _cleanup_sample(sid)
    resp = await client.post(
        "/api/v1/ingest/register",
        json={
            "sample_metadata": _base_metadata(sid),
            "files": [{"role": "R1", "uri": f"file://{r1}"}],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["sample_id"] == sid
    assert len(data["files"]) == 1
    assert data["files"][0]["storage_state"] == "EXTERNAL"
    assert data["files"][0]["deduplicated"] is False
    rows = execute_query(
        "SELECT storage_state FROM sample_files WHERE id = :id",
        {"id": data["files"][0]["sample_files_id"]},
    )
    assert rows[0]["storage_state"] == "EXTERNAL"
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_register_paired_files_external(client, fastq_files):
    r1, r2 = fastq_files
    sid = "REG-PAIR-001"
    _cleanup_sample(sid)
    resp = await client.post(
        "/api/v1/ingest/register",
        json={
            "sample_metadata": _base_metadata(sid),
            "files": [
                {"role": "R1", "uri": f"file://{r1}"},
                {"role": "R2", "uri": f"file://{r2}"},
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert len(data["files"]) == 2
    states = {f["storage_state"] for f in data["files"]}
    assert states == {"EXTERNAL"}
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_register_with_managed_intent(client, fastq_files):
    """MANAGED intent records storage_state='MANAGED' but does not copy.

    The actual byte-copy is owned by F-9 (`promote`); F-6 only sets the
    flag. The row is treated as MANAGED by downstream consumers.
    """
    r1, _r2 = fastq_files
    sid = "REG-MAN-001"
    _cleanup_sample(sid)
    resp = await client.post(
        "/api/v1/ingest/register",
        json={
            "sample_metadata": _base_metadata(sid),
            "files": [{"role": "R1", "uri": f"file://{r1}", "storage_intent": "MANAGED"}],
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["files"][0]["storage_state"] == "MANAGED"
    rows = execute_query(
        "SELECT storage_state FROM sample_files WHERE id = :id",
        {"id": data["files"][0]["sample_files_id"]},
    )
    assert rows[0]["storage_state"] == "MANAGED"
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_register_dedup_on_second_call(client, fastq_files):
    r1, _r2 = fastq_files
    sid_a = "REG-DEDUP-A"
    sid_b = "REG-DEDUP-B"
    _cleanup_sample(sid_a)
    _cleanup_sample(sid_b)
    first = await client.post(
        "/api/v1/ingest/register",
        json={
            "sample_metadata": _base_metadata(sid_a),
            "files": [{"role": "R1", "uri": f"file://{r1}"}],
        },
    )
    assert first.status_code == 201, first.text
    first_id = first.json()["data"]["files"][0]["sample_files_id"]
    second = await client.post(
        "/api/v1/ingest/register",
        json={
            "sample_metadata": _base_metadata(sid_b),
            "files": [{"role": "R1", "uri": f"file://{r1}"}],
        },
    )
    assert second.status_code == 201, second.text
    sf = second.json()["data"]["files"][0]
    assert sf["sample_files_id"] == first_id
    assert sf["deduplicated"] is True
    _cleanup_sample(sid_a)
    _cleanup_sample(sid_b)


@pytest.mark.asyncio
async def test_register_dedup_appends_alternate_uri(client, fastq_files, tmp_path):
    r1, _r2 = fastq_files
    # Same content at a second path so the cheap fingerprint matches.
    r1_alt = tmp_path / "REG-R1-alt.fastq"
    r1_alt.write_bytes(r1.read_bytes())

    sid_a = "REG-ALT-A"
    sid_b = "REG-ALT-B"
    _cleanup_sample(sid_a)
    _cleanup_sample(sid_b)
    await client.post(
        "/api/v1/ingest/register",
        json={
            "sample_metadata": _base_metadata(sid_a),
            "files": [{"role": "R1", "uri": f"file://{r1}"}],
        },
    )
    second = await client.post(
        "/api/v1/ingest/register",
        json={
            "sample_metadata": _base_metadata(sid_b),
            "files": [{"role": "R1", "uri": f"file://{r1_alt}"}],
        },
    )
    assert second.status_code == 201, second.text
    sf_id = second.json()["data"]["files"][0]["sample_files_id"]
    rows = execute_query(
        "SELECT alternate_uris FROM sample_files WHERE id = :id",
        {"id": sf_id},
    )
    alts = rows[0]["alternate_uris"] or []
    assert any(str(r1_alt) in alt for alt in alts)
    _cleanup_sample(sid_a)
    _cleanup_sample(sid_b)


@pytest.mark.asyncio
async def test_register_unreachable_file_returns_400(client):
    sid = "REG-MISSING-001"
    _cleanup_sample(sid)
    resp = await client.post(
        "/api/v1/ingest/register",
        json={
            "sample_metadata": _base_metadata(sid),
            "files": [{"role": "R1", "uri": "file:///definitely/not/here.fastq"}],
        },
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["success"] is False
    detail = body["error"]["detail"]
    assert detail["code"] == "FILE_UNREACHABLE"
    assert "/definitely/not/here.fastq" in detail["message"]
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_register_invalid_storage_intent_returns_422(client, fastq_files):
    r1, _r2 = fastq_files
    sid = "REG-BADINTENT-001"
    _cleanup_sample(sid)
    for bad in ("STAGED", "BROKEN", "GARBAGE"):
        resp = await client.post(
            "/api/v1/ingest/register",
            json={
                "sample_metadata": _base_metadata(sid),
                "files": [{"role": "R1", "uri": f"file://{r1}", "storage_intent": bad}],
            },
        )
        assert resp.status_code == 422, f"intent={bad}: {resp.text}"
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_register_partial_failure_rolls_back_sample(client, fastq_files):
    r1, _r2 = fastq_files
    sid = "REG-ROLLBACK-001"
    _cleanup_sample(sid)
    resp = await client.post(
        "/api/v1/ingest/register",
        json={
            "sample_metadata": _base_metadata(sid),
            "files": [
                {"role": "R1", "uri": f"file://{r1}"},
                {"role": "R2", "uri": "file:///definitely/not/here_R2.fastq"},
            ],
        },
    )
    assert resp.status_code == 400
    # The whole sample row must have been rolled back — half-registered
    # samples are confusing.
    rows = execute_query("SELECT 1 FROM samples WHERE sample_id = :s", {"s": sid})
    assert rows == []
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_register_creates_audit_log(client, fastq_files):
    r1, _r2 = fastq_files
    sid = "REG-AUDIT-001"
    _cleanup_sample(sid)
    resp = await client.post(
        "/api/v1/ingest/register",
        json={
            "sample_metadata": _base_metadata(sid),
            "files": [{"role": "R1", "uri": f"file://{r1}"}],
        },
    )
    assert resp.status_code == 201
    sf_id = resp.json()["data"]["files"][0]["sample_files_id"]
    rows = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'sample_files' AND resource_id = :rid",
        {"rid": str(sf_id)},
    )
    actions = [r["action"] for r in rows]
    assert "REGISTER_FILE" in actions
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_register_creates_dedup_audit_when_deduped(client, fastq_files):
    r1, _r2 = fastq_files
    sid_a = "REG-AUD-DEDUP-A"
    sid_b = "REG-AUD-DEDUP-B"
    _cleanup_sample(sid_a)
    _cleanup_sample(sid_b)
    await client.post(
        "/api/v1/ingest/register",
        json={
            "sample_metadata": _base_metadata(sid_a),
            "files": [{"role": "R1", "uri": f"file://{r1}"}],
        },
    )
    second = await client.post(
        "/api/v1/ingest/register",
        json={
            "sample_metadata": _base_metadata(sid_b),
            "files": [{"role": "R1", "uri": f"file://{r1}"}],
        },
    )
    sf_id = second.json()["data"]["files"][0]["sample_files_id"]
    rows = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'sample_files' AND resource_id = :rid",
        {"rid": str(sf_id)},
    )
    actions = [r["action"] for r in rows]
    assert "DEDUP_FILE" in actions
    _cleanup_sample(sid_a)
    _cleanup_sample(sid_b)


@pytest.mark.asyncio
async def test_register_validation_error_on_metadata(client, fastq_files):
    r1, _r2 = fastq_files
    sid = "REG-BADMETA-001"
    _cleanup_sample(sid)
    meta = _base_metadata(sid)
    meta.pop("organism_name")  # BASE_REQUIRED — validator must reject
    resp = await client.post(
        "/api/v1/ingest/register",
        json={
            "sample_metadata": meta,
            "files": [{"role": "R1", "uri": f"file://{r1}"}],
        },
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert "organism_name" in str(body["error"])
    _cleanup_sample(sid)
