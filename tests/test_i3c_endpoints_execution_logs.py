"""I-3c: ``GET /api/v1/submissions/{id}/execution-logs``."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.database import execute_query, execute_write

SEED_USER_ID = 1
SEED_LAB_ID = 1
SAMPLE_PREFIX = "I3C-LOGS-S-"
SUB_PREFIX = "I3C-LOGS-"


def _cleanup() -> None:
    rows = execute_query("SELECT id FROM submissions WHERE title LIKE :p", {"p": f"{SUB_PREFIX}%"})
    for r in rows:
        sid = r["id"]
        execute_write("DELETE FROM submission_samples WHERE submission_id = :id", {"id": sid})
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


def _make_submission(suffix: str, *, log_uris: list[str] | None = None) -> int:
    sample_id = _insert_sample(f"{SAMPLE_PREFIX}{suffix}")
    rows = execute_write(
        """
        INSERT INTO submissions (
            created_by_user_id, lab_id, target_repository, title, status
        ) VALUES (
            :uid, :lid, 'NCBI', :title, 'EXECUTION_FAILED'
        ) RETURNING id
        """,
        {
            "uid": SEED_USER_ID,
            "lid": SEED_LAB_ID,
            "title": f"{SUB_PREFIX}{suffix}",
        },
    )
    sub_id = rows[0]["id"]
    execute_write(
        "INSERT INTO submission_samples (submission_id, sample_id_fk) VALUES (:sub, :sid)",
        {"sub": sub_id, "sid": sample_id},
    )
    if log_uris:
        import json as _json

        execute_write(
            "UPDATE submissions SET execution_log_uris = CAST(:uris AS jsonb) WHERE id = :id",
            {"uris": _json.dumps(log_uris), "id": sub_id},
        )
    return sub_id


@pytest.fixture(autouse=True)
def _around():
    _cleanup()
    yield
    _cleanup()


@pytest.mark.asyncio
async def test_logs_empty(client):
    sub_id = _make_submission("EMPTY")
    resp = await client.get(f"/api/v1/submissions/{sub_id}/execution-logs")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["submission_id"] == sub_id
    assert body["entries"] == []


@pytest.mark.asyncio
async def test_logs_single_entry(client):
    sub_id = _make_submission("ONE", log_uris=["file:///tmp/jackpot-execs/sub_42_attempt_1.log"])
    resp = await client.get(f"/api/v1/submissions/{sub_id}/execution-logs")
    assert resp.status_code == 200
    entries = resp.json()["data"]["entries"]
    assert len(entries) == 1
    assert entries[0]["attempt"] == 1
    assert entries[0]["log_uri"] == "file:///tmp/jackpot-execs/sub_42_attempt_1.log"
    # file:// URIs are returned unchanged for log_view_url.
    assert entries[0]["log_view_url"].startswith("file://")


@pytest.mark.asyncio
async def test_logs_multiple_entries_ordered(client):
    uris = [
        "file:///tmp/log_attempt_1.log",
        "file:///tmp/log_attempt_2.log",
        "file:///tmp/log_attempt_3.log",
    ]
    sub_id = _make_submission("MULTI", log_uris=uris)
    resp = await client.get(f"/api/v1/submissions/{sub_id}/execution-logs")
    entries = resp.json()["data"]["entries"]
    assert [e["attempt"] for e in entries] == [1, 2, 3]
    assert [e["log_uri"] for e in entries] == uris


@pytest.mark.asyncio
async def test_logs_cloud_uri_presigned(client):
    """For ``s3://`` and ``gs://`` URIs, the helper presigns. We patch
    ``generate_presigned_url`` and assert the helper called it once."""
    sub_id = _make_submission("CLOUD", log_uris=["s3://jackpot-submissions/exec/sub_42.log"])
    with patch(
        "backend.storage.generate_presigned_url",
        return_value="https://signed.example.org/sub_42.log",
    ) as mocked:
        resp = await client.get(f"/api/v1/submissions/{sub_id}/execution-logs")
    assert resp.status_code == 200
    entries = resp.json()["data"]["entries"]
    assert entries[0]["log_view_url"] == "https://signed.example.org/sub_42.log"
    mocked.assert_called_once()


@pytest.mark.asyncio
async def test_logs_presign_failure_falls_back_to_raw_uri(client):
    """If presign generation raises (network blip, missing IAM, etc.)
    the endpoint returns the raw URI rather than 500ing."""
    sub_id = _make_submission("PRESIGN-FAIL", log_uris=["s3://bucket/key.log"])
    with patch(
        "backend.storage.generate_presigned_url",
        side_effect=RuntimeError("transient"),
    ):
        resp = await client.get(f"/api/v1/submissions/{sub_id}/execution-logs")
    assert resp.status_code == 200
    entries = resp.json()["data"]["entries"]
    assert entries[0]["log_view_url"] == "s3://bucket/key.log"


@pytest.mark.asyncio
async def test_logs_unknown_submission(client):
    resp = await client.get("/api/v1/submissions/99999999/execution-logs")
    assert resp.status_code == 404
