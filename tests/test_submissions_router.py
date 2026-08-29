"""I-2 router tests for /api/v1/submissions/."""

from __future__ import annotations

import pytest

from backend.database import execute_query, execute_write

SEED_USER_ID = 1
SEED_LAB_ID = 1


def _cleanup_submissions(prefix: str = "I2-RT-") -> None:
    rows = execute_query("SELECT id FROM submissions WHERE title LIKE :p", {"p": f"{prefix}%"})
    for r in rows:
        execute_write("DELETE FROM submission_samples WHERE submission_id = :id", {"id": r["id"]})
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'submission' AND resource_id = :rid",
            {"rid": str(r["id"])},
        )
        execute_write("DELETE FROM submissions WHERE id = :id", {"id": r["id"]})


def _cleanup_samples(prefix: str = "I2-RT-S-") -> None:
    rows = execute_query("SELECT id FROM samples WHERE sample_id LIKE :p", {"p": f"{prefix}%"})
    for r in rows:
        execute_write("DELETE FROM sample_files WHERE sample_id_fk = :id", {"id": r["id"]})
        execute_write("DELETE FROM submission_samples WHERE sample_id_fk = :id", {"id": r["id"]})
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'sample' AND resource_id = :rid",
            {"rid": str(r["id"])},
        )
        execute_write("DELETE FROM samples WHERE id = :id", {"id": r["id"]})


def _insert_sample(sample_id: str, **overrides) -> int:
    payload = {
        "sample_id": sample_id,
        "lab_id": SEED_LAB_ID,
        "project_id": 1,
        "owner_id": SEED_USER_ID,
        "source_type": "Human",
        "organism_name": "Severe acute respiratory syndrome coronavirus 2",
        "type_of_experiment": "WGS",
        "library_preparation_method": "ARTIC",
        "sequencing_protocol": "https://www.protocols.io/view/artic-v4-1",
        "sequencing_platform": "Illumina",
        "sequencing_lab": "Example Sequencing Lab",
        "date_collected": "2026-01-15",
        "date_sequenced": "2026-01-17",
        "collection_facility": "Example Hospital",
        "collection_location_country": "United States",
        "sharing_level": "PRIVATE",
        "fastq_r1_uri": "gs://test/R1.fq.gz",
        "surveillance_relevant": False,
    }
    payload.update(overrides)
    cols = sorted(payload.keys())
    placeholders = [f":{c}" for c in cols]
    rows = execute_write(
        f"INSERT INTO samples ({', '.join(cols)}) VALUES ({', '.join(placeholders)}) RETURNING id",
        payload,
    )
    return rows[0]["id"]


@pytest.mark.asyncio
async def test_create_then_get_submission(client):
    _cleanup_submissions()
    _cleanup_samples()
    sid = _insert_sample("I2-RT-S-A")
    create = await client.post(
        "/api/v1/submissions/",
        json={
            "lab_id": SEED_LAB_ID,
            "target_repository": "NCBI",
            "title": "I2-RT-A",
            "sample_ids": [sid],
        },
    )
    assert create.status_code == 201, create.text
    sid_sub = create.json()["data"]["id"]

    get = await client.get(f"/api/v1/submissions/{sid_sub}")
    assert get.status_code == 200
    body = get.json()["data"]
    assert body["title"] == "I2-RT-A"
    assert len(body["samples"]) == 1
    _cleanup_submissions()
    _cleanup_samples()


@pytest.mark.asyncio
async def test_list_submissions_returns_pagination_envelope(client):
    _cleanup_submissions()
    _cleanup_samples()
    sid = _insert_sample("I2-RT-S-LIST")
    for i in range(3):
        await client.post(
            "/api/v1/submissions/",
            json={
                "lab_id": SEED_LAB_ID,
                "target_repository": "NCBI",
                "title": f"I2-RT-LIST-{i}",
                "sample_ids": [sid],
            },
        )
    resp = await client.get(f"/api/v1/submissions/?lab_id={SEED_LAB_ID}")
    assert resp.status_code == 200
    body = resp.json()
    assert "pagination" in body
    titles = {r["title"] for r in body["data"]}
    assert any(t.startswith("I2-RT-LIST-") for t in titles)
    _cleanup_submissions()
    _cleanup_samples()


@pytest.mark.asyncio
async def test_create_rejects_invalid_repository(client):
    sid = _insert_sample("I2-RT-S-INV")
    resp = await client.post(
        "/api/v1/submissions/",
        json={
            "lab_id": SEED_LAB_ID,
            "target_repository": "GARBAGE",
            "title": "I2-RT-INV",
            "sample_ids": [sid],
        },
    )
    assert resp.status_code == 422
    _cleanup_samples()


@pytest.mark.asyncio
async def test_add_remove_samples_round_trip(client):
    _cleanup_submissions()
    _cleanup_samples()
    a = _insert_sample("I2-RT-S-AR-A")
    b = _insert_sample("I2-RT-S-AR-B")
    create = await client.post(
        "/api/v1/submissions/",
        json={
            "lab_id": SEED_LAB_ID,
            "target_repository": "NCBI",
            "title": "I2-RT-AR",
            "sample_ids": [a],
        },
    )
    sid_sub = create.json()["data"]["id"]
    add = await client.post(f"/api/v1/submissions/{sid_sub}/samples", json={"sample_ids": [b]})
    assert add.status_code == 200
    assert add.json()["data"]["added"] == 1
    rm = await client.request(
        "DELETE",
        f"/api/v1/submissions/{sid_sub}/samples",
        json={"sample_ids": [a]},
    )
    assert rm.status_code == 200
    assert rm.json()["data"]["removed"] == 1
    _cleanup_submissions()
    _cleanup_samples()


@pytest.mark.asyncio
async def test_validate_endpoint_returns_per_sample_results(client):
    _cleanup_submissions()
    _cleanup_samples()
    bad = _insert_sample("I2-RT-S-VAL", organism_name="")
    create = await client.post(
        "/api/v1/submissions/",
        json={
            "lab_id": SEED_LAB_ID,
            "target_repository": "NCBI",
            "title": "I2-RT-VAL",
            "sample_ids": [bad],
        },
    )
    sid_sub = create.json()["data"]["id"]
    resp = await client.post(f"/api/v1/submissions/{sid_sub}/validate")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["valid"] is False
    assert any(s["sample_id"] == "I2-RT-S-VAL" for s in data["per_sample"])
    _cleanup_submissions()
    _cleanup_samples()


@pytest.mark.asyncio
async def test_lifecycle_mark_submitted_register_accessions(client, tmp_path, monkeypatch):
    _cleanup_submissions()
    _cleanup_samples()
    monkeypatch.setenv("SUBMISSIONS_OUTPUT_ROOT", str(tmp_path))
    from backend.config import get_settings

    get_settings.cache_clear()

    sid = _insert_sample("I2-RT-S-LIFE")
    # Attach a local fastq so package generation succeeds.
    fastq = tmp_path / "x.fastq"
    fastq.write_bytes(b"@A\nN\n+\n!\n")
    execute_write(
        """
        INSERT INTO sample_files (
            sample_id_fk, uri, filename, file_size_bytes,
            file_type, library_layout, read_direction,
            storage_state, scrub_status, ingest_method
        ) VALUES (
            :sid, :uri, 'x.fastq', :sz,
            'FASTQ', 'PAIRED', 'R1',
            CAST('EXTERNAL' AS file_storage_state), 'PENDING', 'register'
        )
        """,
        {"sid": sid, "uri": f"file://{fastq}", "sz": fastq.stat().st_size},
    )

    create = await client.post(
        "/api/v1/submissions/",
        json={
            "lab_id": SEED_LAB_ID,
            "target_repository": "NCBI",
            "title": "I2-RT-LIFE",
            "sample_ids": [sid],
        },
    )
    sid_sub = create.json()["data"]["id"]

    gen = await client.post(f"/api/v1/submissions/{sid_sub}/generate", json={"copy_files": False})
    assert gen.status_code == 200, gen.text
    assert "package_path" in gen.json()["data"]

    mark = await client.post(f"/api/v1/submissions/{sid_sub}/mark-submitted")
    assert mark.status_code == 200
    assert mark.json()["data"]["status"] == "SUBMITTED"

    reg = await client.post(
        f"/api/v1/submissions/{sid_sub}/register-accessions",
        json={
            "accessions": [
                {
                    "sample_id": "I2-RT-S-LIFE",
                    "biosample": "SAMN9999",
                    "sra": "SRR9999",
                }
            ]
        },
    )
    assert reg.status_code == 200, reg.text
    assert reg.json()["data"]["status"] in ("RELEASED", "ACCEPTED")
    get_settings.cache_clear()
    _cleanup_submissions()
    _cleanup_samples()


@pytest.mark.asyncio
async def test_delete_submission_only_in_draft(client):
    _cleanup_submissions()
    _cleanup_samples()
    sid = _insert_sample("I2-RT-S-DEL")
    create = await client.post(
        "/api/v1/submissions/",
        json={
            "lab_id": SEED_LAB_ID,
            "target_repository": "NCBI",
            "title": "I2-RT-DEL",
            "sample_ids": [sid],
        },
    )
    sid_sub = create.json()["data"]["id"]
    resp = await client.delete(f"/api/v1/submissions/{sid_sub}")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_archived"] is True
    _cleanup_submissions()
    _cleanup_samples()


@pytest.mark.asyncio
async def test_register_accessions_via_tsv_upload(client, tmp_path, monkeypatch):
    _cleanup_submissions()
    _cleanup_samples()
    monkeypatch.setenv("SUBMISSIONS_OUTPUT_ROOT", str(tmp_path))
    from backend.config import get_settings

    get_settings.cache_clear()
    sid = _insert_sample("I2-RT-S-TSV")
    fastq = tmp_path / "x.fastq"
    fastq.write_bytes(b"@A\nN\n+\n!\n")
    execute_write(
        """
        INSERT INTO sample_files (
            sample_id_fk, uri, filename, file_size_bytes,
            file_type, library_layout, read_direction,
            storage_state, scrub_status, ingest_method
        ) VALUES (
            :sid, :uri, 'x.fastq', :sz,
            'FASTQ', 'PAIRED', 'R1',
            CAST('EXTERNAL' AS file_storage_state), 'PENDING', 'register'
        )
        """,
        {"sid": sid, "uri": f"file://{fastq}", "sz": fastq.stat().st_size},
    )

    create = await client.post(
        "/api/v1/submissions/",
        json={
            "lab_id": SEED_LAB_ID,
            "target_repository": "NCBI",
            "title": "I2-RT-TSV",
            "sample_ids": [sid],
        },
    )
    sid_sub = create.json()["data"]["id"]
    await client.post(f"/api/v1/submissions/{sid_sub}/generate", json={"copy_files": False})
    await client.post(f"/api/v1/submissions/{sid_sub}/mark-submitted")

    tsv = (
        b"sample_id\tbiosample\tsra\tgenbank\tgisaid\tena\tddbj\trejection_reason\n"
        b"I2-RT-S-TSV\tSAMN42\tSRR42\t-\t-\t-\t-\t-\n"
    )
    resp = await client.post(
        f"/api/v1/submissions/{sid_sub}/register-accessions",
        files={"file": ("accessions.tsv", tsv, "text/tab-separated-values")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["status"] in ("RELEASED", "ACCEPTED")
    get_settings.cache_clear()
    _cleanup_submissions()
    _cleanup_samples()


@pytest.mark.asyncio
async def test_get_unknown_submission_returns_404(client):
    resp = await client.get("/api/v1/submissions/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_without_lab_id_for_non_admin_returns_400(client, monkeypatch):
    # Switch to non-admin user
    execute_write(
        "INSERT INTO users (email, name, organization_id, "
        "is_platform_admin, is_active) "
        "VALUES ('i2-rt-nonadmin@test.com', 'NonAdmin', 1, FALSE, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET is_platform_admin = FALSE",
    )
    monkeypatch.setenv("MOCK_USER_EMAIL", "i2-rt-nonadmin@test.com")
    from backend.config import get_settings

    get_settings.cache_clear()
    resp = await client.get("/api/v1/submissions/")
    assert resp.status_code == 400
    execute_write("DELETE FROM users WHERE email = 'i2-rt-nonadmin@test.com'")
