"""Tests for the per-row storage_intent column in /api/v1/ingest/csv.

Phase P0f F-6 added an optional ``storage_intent`` column to the CSV
ingest format. Without it, rows default to ``EXTERNAL`` (Critical Rule
57) and the response surfaces a warning. With it, each row's
``storage_state`` matches the column value. Invalid values cause that
row to fail while others succeed (existing per-row error behavior).
"""

import pytest

from backend.database import execute_query, execute_write


def _cleanup_samples(prefix: str) -> None:
    rows = execute_query(
        "SELECT sample_id FROM samples WHERE sample_id LIKE :p",
        {"p": f"{prefix}%"},
    )
    for r in rows:
        sid = r["sample_id"]
        execute_write(
            "DELETE FROM sample_files WHERE sample_id_fk IN "
            "(SELECT id FROM samples WHERE sample_id = :s)",
            {"s": sid},
        )
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'sample' AND resource_id IN "
            "(SELECT id::text FROM samples WHERE sample_id = :s)",
            {"s": sid},
        )
        execute_write("DELETE FROM samples WHERE sample_id = :s", {"s": sid})


_CSV_HEADER_NO_INTENT = (
    "sample_id,organism_name,source_type,date_collected,"
    "collection_location_country,collection_location_state,"
    "sequencing_platform,sequencing_lab,type_of_experiment,"
    "library_preparation_method,nucleic_acid_extraction_method,"
    "sequencing_protocol,collection_facility,"
    "external_case_id,biospecimen_type,reason_for_collection,host_disease,"
    "date_sequenced,purpose_for_collection,lab_id,project_id,files\n"
)

_CSV_HEADER_WITH_INTENT = _CSV_HEADER_NO_INTENT.rstrip("\n") + ",storage_intent\n"


def _row(sample_id: str, intent: str | None = None) -> str:
    base = (
        f"{sample_id},Severe acute respiratory syndrome coronavirus 2,Human,"
        "2026-01-15,United States,California,Illumina,"
        "Example Sequencing Lab,WGS,ARTIC,QIAamp DSP Viral RNA,"
        "https://www.protocols.io/view/artic-v4-1,Example Hospital,"
        "CASE-2026-001,nasopharyngeal_swab,clinical,covid-19,"
        f"2026-01-17,clinical,1,1,{sample_id}_R1.fastq.gz"
    )
    if intent is None:
        return base + "\n"
    return f"{base},{intent}\n"


@pytest.mark.asyncio
async def test_csv_storage_intent_column_missing_defaults_external(client):
    prefix = "ING-CSV-INT-MISS-"
    _cleanup_samples(prefix)
    sid = f"{prefix}001"
    body = _CSV_HEADER_NO_INTENT + _row(sid)
    resp = await client.post(
        "/api/v1/ingest/csv",
        files={"file": ("batch.csv", body.encode(), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["data"]["success"] == 1
    assert "warnings" in payload
    assert any("storage_intent column missing" in w for w in payload["warnings"])
    rows = execute_query(
        "SELECT storage_state FROM sample_files sf "
        "JOIN samples s ON s.id = sf.sample_id_fk "
        "WHERE s.sample_id = :sid",
        {"sid": sid},
    )
    assert rows
    assert all(r["storage_state"] == "EXTERNAL" for r in rows)
    _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_csv_storage_intent_column_present_per_row(client):
    prefix = "ING-CSV-INT-OK-"
    _cleanup_samples(prefix)
    a = f"{prefix}EXT"
    b = f"{prefix}MAN"
    body = _CSV_HEADER_WITH_INTENT + _row(a, "EXTERNAL") + _row(b, "MANAGED")
    resp = await client.post(
        "/api/v1/ingest/csv",
        files={"file": ("batch.csv", body.encode(), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["data"]["success"] == 2
    # No advisory warning when the column is supplied explicitly.
    assert "warnings" not in payload or not payload["warnings"]
    rows = execute_query(
        "SELECT s.sample_id, sf.storage_state FROM sample_files sf "
        "JOIN samples s ON s.id = sf.sample_id_fk "
        "WHERE s.sample_id LIKE :p",
        {"p": f"{prefix}%"},
    )
    by_sid = {r["sample_id"]: r["storage_state"] for r in rows}
    assert by_sid[a] == "EXTERNAL"
    assert by_sid[b] == "MANAGED"
    _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_csv_storage_intent_invalid_value_row_fails(client):
    prefix = "ING-CSV-INT-BAD-"
    _cleanup_samples(prefix)
    good = f"{prefix}OK"
    bad = f"{prefix}BAD"
    body = (
        _CSV_HEADER_WITH_INTENT
        + _row(good, "EXTERNAL")
        + _row(bad, "STAGED")  # internal lifecycle state — not a valid intent
    )
    resp = await client.post(
        "/api/v1/ingest/csv",
        files={"file": ("batch.csv", body.encode(), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["success"] == 1
    assert data["failed"] == 1
    assert any(bad in str(e) for e in data["errors"])
    _cleanup_samples(prefix)
