"""Tests for /api/v1/ingest/upload's MANAGED storage state and fingerprint.

Phase P0f F-6 changed /upload so it (a) records storage_state='MANAGED'
on every staged sample_files row and (b) populates the cheap-fingerprint
columns from the bytes in hand. These tests guard both behaviors.
"""

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


def _meta(sample_id: str) -> dict:
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
        "external_case_id": "CASE-2026-001",
        "biospecimen_type": "nasopharyngeal_swab",
        "reason_for_collection": ["clinical"],
        "host_disease": ["covid-19"],
        "lab_id": 1,
        "project_id": 1,
    }


@pytest.mark.asyncio
async def test_upload_records_managed_storage_state(client, mock_storage):
    sid = "ING-UP-MANAGED-001"
    _cleanup_sample(sid)
    resp = await client.post(
        "/api/v1/ingest/upload",
        data={"metadata": json.dumps(_meta(sid))},
        files={
            "fastq_r1": (
                f"{sid}_R1.fastq.gz",
                b"@SEQ\nACGT\n+\n!!!!\n",
                "application/gzip",
            ),
        },
    )
    assert resp.status_code == 201, resp.text
    rows = execute_query(
        "SELECT storage_state, head64k_hash, tail64k_hash, file_size_bytes "
        "FROM sample_files sf JOIN samples s ON s.id = sf.sample_id_fk "
        "WHERE s.sample_id = :sid",
        {"sid": sid},
    )
    assert rows
    row = rows[0]
    assert row["storage_state"] == "MANAGED"
    # Phase P0f F-6: cheap fingerprint columns populated from bytes.
    assert row["head64k_hash"] is not None
    assert row["tail64k_hash"] is not None
    assert row["file_size_bytes"] == len(b"@SEQ\nACGT\n+\n!!!!\n")
    _cleanup_sample(sid)
