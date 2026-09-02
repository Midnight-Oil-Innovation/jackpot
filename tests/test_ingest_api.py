import json

import pytest

from backend.database import execute_query, execute_write


def _fake_stage_file(fileobj, destination_key):
    if hasattr(fileobj, "read"):
        fileobj.read()
    return f"gs://jackpot-staging/{destination_key}"


@pytest.fixture
def mock_storage(monkeypatch):
    monkeypatch.setattr("backend.routers.ingest.stage_file", _fake_stage_file)


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


def _cleanup_samples(prefix: str) -> None:
    rows = execute_query(
        "SELECT sample_id FROM samples WHERE sample_id LIKE :p",
        {"p": f"{prefix}%"},
    )
    for r in rows:
        _cleanup_sample(r["sample_id"])


def _base_metadata(sample_id: str = "ING-TEST-001", **overrides) -> dict:
    meta = {
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
        "external_case_id": "CASE-2026-001",
        "biospecimen_type": "nasopharyngeal_swab",
        "reason_for_collection": ["clinical"],
        "host_disease": ["covid-19"],
        "project_id": 1,
        "lab_id": 1,
    }
    meta.update(overrides)
    return meta


@pytest.mark.asyncio
async def test_upload_valid_human_sample_returns_201(client, mock_storage):
    sid = "ING-HU-001"
    _cleanup_sample(sid)
    meta = _base_metadata(sid)
    resp = await client.post(
        "/api/v1/ingest/upload",
        data={"metadata": json.dumps(meta)},
        files={
            "fastq_r1": (
                f"{sid}_R1.fastq.gz",
                b"@SEQ\nACGT\n+\n!!!!\n",
                "application/gzip",
            ),
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["sample_id"] == sid
    assert data["scrub_status"] == "PENDING"
    assert data["sector"] == "clinical"
    assert data["quality_status"] in ("PRELIMINARY", "ANALYZABLE", "SUBMITTABLE")
    assert data["fastq_r1_uri"].startswith("gs://jackpot-staging/")
    assert len(data["files"]) == 1
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_upload_paired_files_detected(client, mock_storage):
    sid = "ING-PAIR-001"
    _cleanup_sample(sid)
    meta = _base_metadata(sid)
    resp = await client.post(
        "/api/v1/ingest/upload",
        data={"metadata": json.dumps(meta)},
        files={
            "fastq_r1": (
                f"{sid}_R1.fastq.gz",
                b"@SEQ\nACGT\n+\n!!!!\n",
                "application/gzip",
            ),
            "fastq_r2": (
                f"{sid}_R2.fastq.gz",
                b"@SEQ\nACGT\n+\n!!!!\n",
                "application/gzip",
            ),
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["fastq_r1_uri"].endswith("_R1.fastq.gz")
    assert data["fastq_r2_uri"].endswith("_R2.fastq.gz")
    layouts = {f["library_layout"] for f in data["files"]}
    assert layouts == {"PAIRED"}
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_upload_submittable_tier(client, mock_storage):
    sid = "ING-SUB-001"
    _cleanup_sample(sid)
    meta = _base_metadata(
        sid,
        originating_lab="Example Hospital",
        submitting_lab="Example Lab",
        collection_location_county="San Diego",
        host_sex="female",
        host_age=42,
    )
    resp = await client.post(
        "/api/v1/ingest/upload",
        data={"metadata": json.dumps(meta)},
        files={
            "fastq_r1": (
                f"{sid}_R1.fastq.gz",
                b"@SEQ\nACGT\n+\n!!!!\n",
                "application/gzip",
            ),
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["quality_status"] == "SUBMITTABLE"
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_upload_fasta_only_skips_scrub(client, mock_storage):
    sid = "ING-FA-001"
    _cleanup_sample(sid)
    meta = _base_metadata(sid)
    resp = await client.post(
        "/api/v1/ingest/upload",
        data={"metadata": json.dumps(meta)},
        files={
            "fastq_r1": (
                f"{sid}_consensus.fasta",
                b">seq1\nACGTACGT\n",
                "text/plain",
            ),
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["scrub_status"] == "SKIPPED"
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_upload_unknown_sequencing_lab_returns_422(client, mock_storage):
    sid = "ING-BAD-LAB"
    _cleanup_sample(sid)
    meta = _base_metadata(sid, sequencing_lab="Nonexistent Lab Corp")
    resp = await client.post(
        "/api/v1/ingest/upload",
        data={"metadata": json.dumps(meta)},
        files={
            "fastq_r1": (
                f"{sid}_R1.fastq.gz",
                b"@SEQ\nACGT\n+\n!!!!\n",
                "application/gzip",
            ),
        },
    )
    assert resp.status_code == 422
    assert "Unknown sequencing lab" in str(resp.json()["error"]["message"])
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_upload_missing_external_case_id_returns_422(client, mock_storage):
    sid = "ING-NO-CASE-ID"
    _cleanup_sample(sid)
    meta = _base_metadata(sid)
    meta.pop("external_case_id")
    resp = await client.post(
        "/api/v1/ingest/upload",
        data={"metadata": json.dumps(meta)},
        files={
            "fastq_r1": (
                f"{sid}_R1.fastq.gz",
                b"@SEQ\nACGT\n+\n!!!!\n",
                "application/gzip",
            ),
        },
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert "external_case_id" in body["error"]["message"]
    detail = body["error"]["detail"]
    assert any("external_case_id" in e for e in detail.get("errors", []))
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_upload_invalid_metadata_json_returns_422(client, mock_storage):
    resp = await client.post(
        "/api/v1/ingest/upload",
        data={"metadata": "{not valid json"},
        files={
            "fastq_r1": (
                "bad_R1.fastq.gz",
                b"@SEQ\nACGT\n+\n!!!!\n",
                "application/gzip",
            ),
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upload_epiweek_populated_for_day_precision(client, mock_storage):
    sid = "ING-EPI-001"
    _cleanup_sample(sid)
    meta = _base_metadata(sid, date_collected="2026-01-15", date_collected_precision="day")
    resp = await client.post(
        "/api/v1/ingest/upload",
        data={"metadata": json.dumps(meta)},
        files={
            "fastq_r1": (
                f"{sid}_R1.fastq.gz",
                b"@SEQ\nACGT\n+\n!!!!\n",
                "application/gzip",
            ),
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["mmwr_year"] == 2026
    assert data["mmwr_week"] is not None
    assert data["iso_year"] == 2026
    assert data["iso_week"] is not None
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_upload_epiweek_null_for_year_precision(client, mock_storage):
    sid = "ING-EPI-Y"
    _cleanup_sample(sid)
    meta = _base_metadata(sid, date_collected="2026-01-01", date_collected_precision="year")
    resp = await client.post(
        "/api/v1/ingest/upload",
        data={"metadata": json.dumps(meta)},
        files={
            "fastq_r1": (
                f"{sid}_R1.fastq.gz",
                b"@SEQ\nACGT\n+\n!!!!\n",
                "application/gzip",
            ),
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["mmwr_year"] is None
    assert data["mmwr_week"] is None
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_upload_writes_audit_log(client, mock_storage):
    sid = "ING-AUDIT-001"
    _cleanup_sample(sid)
    meta = _base_metadata(sid)
    resp = await client.post(
        "/api/v1/ingest/upload",
        data={"metadata": json.dumps(meta)},
        files={
            "fastq_r1": (
                f"{sid}_R1.fastq.gz",
                b"@SEQ\nACGT\n+\n!!!!\n",
                "application/gzip",
            ),
        },
    )
    assert resp.status_code == 201
    new_id = resp.json()["data"]["id"]
    rows = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'sample' AND resource_id = :rid",
        {"rid": str(new_id)},
    )
    actions = [r["action"] for r in rows]
    assert "CREATE_SAMPLE" in actions
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_upload_sample_files_row_created(client, mock_storage):
    sid = "ING-FILES-001"
    _cleanup_sample(sid)
    meta = _base_metadata(sid)
    resp = await client.post(
        "/api/v1/ingest/upload",
        data={"metadata": json.dumps(meta)},
        files={
            "fastq_r1": (
                f"{sid}_R1.fastq.gz",
                b"@SEQ\nACGT\n+\n!!!!\n",
                "application/gzip",
            ),
        },
    )
    assert resp.status_code == 201
    new_id = resp.json()["data"]["id"]
    rows = execute_query(
        "SELECT filename, file_type, scrub_status FROM sample_files WHERE sample_id_fk = :id",
        {"id": new_id},
    )
    assert len(rows) == 1
    assert rows[0]["filename"] == f"{sid}_R1.fastq.gz"
    assert rows[0]["file_type"] == "FASTQ"
    assert rows[0]["scrub_status"] == "PENDING"
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_upload_rejects_future_date(client, mock_storage):
    sid = "ING-FUT-001"
    _cleanup_sample(sid)
    meta = _base_metadata(sid, date_collected="2099-12-31")
    resp = await client.post(
        "/api/v1/ingest/upload",
        data={"metadata": json.dumps(meta)},
        files={
            "fastq_r1": (
                f"{sid}_R1.fastq.gz",
                b"@SEQ\nACGT\n+\n!!!!\n",
                "application/gzip",
            ),
        },
    )
    assert resp.status_code == 422
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_csv_ingest_success(client, mock_storage):
    prefix = "ING-CSV-"
    _cleanup_samples(prefix)
    sid = f"{prefix}001"
    csv_content = (
        "sample_id,organism_name,source_type,date_collected,"
        "collection_location_country,collection_location_state,"
        "sequencing_platform,sequencing_lab,type_of_experiment,"
        "library_preparation_method,nucleic_acid_extraction_method,"
        "sequencing_protocol,collection_facility,"
        "external_case_id,biospecimen_type,reason_for_collection,host_disease,"
        "date_sequenced,purpose_for_collection,lab_id,project_id,files\n"
        f"{sid},Severe acute respiratory syndrome coronavirus 2,Human,"
        "2026-01-15,United States,California,Illumina,"
        "Example Sequencing Lab,WGS,ARTIC,QIAamp DSP Viral RNA,"
        "https://www.protocols.io/view/artic-v4-1,Example Hospital,"
        "CASE-2026-001,nasopharyngeal_swab,clinical,covid-19,"
        f"2026-01-17,clinical,1,1,{sid}_R1.fastq.gz\n"
    )
    resp = await client.post(
        "/api/v1/ingest/csv",
        files={"file": ("batch.csv", csv_content.encode(), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["success"] == 1
    assert data["failed"] == 0
    _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_csv_ingest_partial_failure(client, mock_storage):
    prefix = "ING-CSV-PF-"
    _cleanup_samples(prefix)
    good = f"{prefix}OK"
    bad = f"{prefix}BAD"
    csv_content = (
        "sample_id,organism_name,source_type,date_collected,"
        "collection_location_country,collection_location_state,"
        "sequencing_platform,sequencing_lab,type_of_experiment,"
        "library_preparation_method,nucleic_acid_extraction_method,"
        "sequencing_protocol,collection_facility,"
        "external_case_id,biospecimen_type,reason_for_collection,host_disease,"
        "date_sequenced,purpose_for_collection,lab_id,project_id,files\n"
        f"{good},Severe acute respiratory syndrome coronavirus 2,Human,"
        "2026-01-15,United States,California,Illumina,"
        "Example Sequencing Lab,WGS,ARTIC,QIAamp DSP Viral RNA,"
        "https://www.protocols.io/view/artic-v4-1,Example Hospital,"
        "CASE-2026-001,nasopharyngeal_swab,clinical,covid-19,"
        f"2026-01-17,clinical,1,1,{good}_R1.fastq.gz\n"
        f"{bad},Severe acute respiratory syndrome coronavirus 2,Human,"
        "2026-01-15,United States,California,Illumina,"
        "Nonexistent Lab,WGS,ARTIC,QIAamp DSP Viral RNA,"
        "https://www.protocols.io/view/artic-v4-1,Example Hospital,"
        "CASE-2026-001,nasopharyngeal_swab,clinical,covid-19,"
        f"2026-01-17,clinical,1,1,{bad}_R1.fastq.gz\n"
    )
    resp = await client.post(
        "/api/v1/ingest/csv",
        files={"file": ("batch.csv", csv_content.encode(), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["success"] == 1
    assert data["failed"] == 1
    assert len(data["errors"]) == 1
    _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_globus_ingest_requires_platform_admin(client, monkeypatch):
    # Switch to a non-admin user by creating one and switching
    execute_write(
        "INSERT INTO users (email, name, is_active, organization_id) "
        "VALUES ('globus_non_admin@test.com', 'Non Admin', TRUE, 1) "
        "ON CONFLICT (email) DO UPDATE SET is_active = TRUE",
    )
    monkeypatch.setenv("MOCK_USER_EMAIL", "globus_non_admin@test.com")
    from backend.config import get_settings

    get_settings.cache_clear()

    resp = await client.post(
        "/api/v1/ingest/globus",
        json={"sequencing_lab": "Example Sequencing Lab", "files": ["x.fq.gz"]},
    )
    assert resp.status_code == 403

    execute_write("DELETE FROM users WHERE email = 'globus_non_admin@test.com'")


@pytest.mark.asyncio
async def test_globus_ingest_unknown_lab_returns_422(client):
    resp = await client.post(
        "/api/v1/ingest/globus",
        json={"sequencing_lab": "Lab Nobody Knows", "files": ["x.fq.gz"]},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_globus_ingest_notifies_directors(client):
    resp = await client.post(
        "/api/v1/ingest/globus",
        json={
            "sequencing_lab": "Example Sequencing Lab",
            "files": ["EX-001_R1.fastq.gz", "EX-001_R2.fastq.gz"],
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["file_count"] == 2
    assert "sequencing_lab_id" in data


@pytest.mark.asyncio
async def test_globus_ingest_requires_files_list(client):
    resp = await client.post(
        "/api/v1/ingest/globus",
        json={"sequencing_lab": "Example Sequencing Lab"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_root_lists_endpoints(client):
    resp = await client.get("/api/v1/ingest/")
    assert resp.status_code == 200
    assert "endpoints" in resp.json()


# ── UI-B regression tests ────────────────────────────────────────────────────
# Both of these guard against the bugs Phase 21 UI-B uncovered: file-content
# validation was being skipped on upload, and HTTPException-based errors
# bypassed the JACKPOT envelope so the frontend rendered raw JSON dumps.


@pytest.mark.asyncio
async def test_upload_rejects_csv_renamed_to_fasta(client, mock_storage):
    """CSV bytes named .fasta must be rejected by file_detector content sniffing."""
    sid = "ING-EXT-LIE"
    _cleanup_sample(sid)
    meta = _base_metadata(sid)
    resp = await client.post(
        "/api/v1/ingest/upload",
        data={"metadata": json.dumps(meta)},
        files={
            "fastq_r1": (
                "fake.fasta",
                b"col1,col2,col3\na,b,c\nd,e,f\n",
                "application/octet-stream",
            ),
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "HTTP_400"
    # Human-readable, names the file and the extension. Not a stack trace.
    assert "fake.fasta" in body["error"]["message"]
    assert ".fasta" in body["error"]["message"]
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_upload_rejects_gzipped_csv_renamed_to_fastq_gz(client, mock_storage):
    """Gzipped CSV named .fastq.gz must be rejected — file_detector peeks through gzip."""
    import gzip as _gzip

    sid = "ING-GZ-LIE"
    _cleanup_sample(sid)
    meta = _base_metadata(sid)
    payload = _gzip.compress(b"col1,col2,col3\na,b,c\nd,e,f\n")
    resp = await client.post(
        "/api/v1/ingest/upload",
        data={"metadata": json.dumps(meta)},
        files={
            "fastq_r1": ("fake.fastq.gz", payload, "application/gzip"),
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert "fake.fastq.gz" in body["error"]["message"]
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_validation_error_uses_jackpot_envelope(client, mock_storage):
    """HTTPException(detail={...}) responses are normalised to the JACKPOT envelope.

    Pre-fix, the raw FastAPI shape `{"detail": {...}}` reached the frontend and
    the ApiClient fell back to dumping the whole body as the error message.
    The global handler in main.py now wraps every HTTPException in
    {"success": false, "error": {"code", "message", "detail"}}.
    """
    sid = "ING-ENVELOPE"
    _cleanup_sample(sid)
    meta = _base_metadata(sid)
    meta.pop("organism_name")  # BASE_REQUIRED — triggers validator failure
    resp = await client.post(
        "/api/v1/ingest/upload",
        data={"metadata": json.dumps(meta)},
        files={
            "fastq_r1": (
                f"{sid}_R1.fastq.gz",
                b"@SEQ\nACGT\n+\n!!!!\n",
                "application/gzip",
            ),
        },
    )
    assert resp.status_code == 422
    body = resp.json()
    # Envelope contract — these keys are what frontend/lib/api.py reads.
    assert body["success"] is False
    assert body["error"]["code"] == "HTTP_422"
    assert "organism_name" in body["error"]["message"]
    assert isinstance(body["error"]["detail"], dict)
    _cleanup_sample(sid)


@pytest.mark.asyncio
async def test_string_detail_http_exception_uses_envelope(client, mock_storage):
    """HTTPException(detail='string') also normalises (sequencing_lab is rejected)."""
    sid = "ING-ENVELOPE-STR"
    _cleanup_sample(sid)
    meta = _base_metadata(sid, sequencing_lab="Nonexistent Sequencing Lab")
    resp = await client.post(
        "/api/v1/ingest/upload",
        data={"metadata": json.dumps(meta)},
        files={
            "fastq_r1": (
                f"{sid}_R1.fastq.gz",
                b"@SEQ\nACGT\n+\n!!!!\n",
                "application/gzip",
            ),
        },
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert "Unknown sequencing lab" in body["error"]["message"]
    _cleanup_sample(sid)
