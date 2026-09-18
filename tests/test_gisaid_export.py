import csv
import io

import pytest

from backend.database import execute_write
from backend.routers.gisaid import GISAID_SARS_COV2_COLUMNS

SEED_LAB_ID = 1


def _insert_sars_cov2_sample(sample_id: str, **overrides) -> dict:
    """Seed a SARS-CoV-2 sample suitable for GISAID export."""
    payload = {
        "sample_id": sample_id,
        "lab_id": SEED_LAB_ID,
        "project_id": 1,
        "owner_id": 1,
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
        "collection_location_state": "California",
        "sharing_level": "PRIVATE",
        "fastq_r1_uri": "gs://jackpot-sequences/test/R1.fastq.gz",
    }
    payload.update(overrides)
    cols = sorted(payload.keys())
    placeholders = [f":{c}" for c in cols]
    rows = execute_write(
        f"INSERT INTO samples ({', '.join(cols)}) VALUES ({', '.join(placeholders)}) RETURNING *",
        payload,
    )
    return rows[0]


@pytest.fixture
def cleanup_sample():
    """Track inserted sample IDs and delete them after the test."""
    inserted: list[int] = []
    yield inserted
    for sid in inserted:
        execute_write("DELETE FROM samples WHERE id = :id", {"id": sid})


def test_all_required_gisaid_columns_present():
    required = [
        "Virus name",
        "Type",
        "Collection date",
        "Location",
        "Host",
        "Gender",
        "Patient age",
        "Sequencing technology",
        "Originating lab",
        "Submitting lab",
        "Authors",
        "Submitter",
    ]
    for col in required:
        assert col in GISAID_SARS_COV2_COLUMNS, f"Missing: {col}"


@pytest.mark.asyncio
async def test_gisaid_export_unsupported_pathogen_returns_501(client):
    resp = await client.post(
        "/api/v1/gisaid/export/1",
        params={"pathogen": "Influenza"},
        json=[1],
    )
    assert resp.status_code == 501


@pytest.mark.asyncio
async def test_gisaid_export_empty_ids_returns_400(client):
    resp = await client.post(
        "/api/v1/gisaid/export/1",
        params={"pathogen": "SARS-CoV-2"},
        json=[],
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_gisaid_export_no_matching_samples_returns_404(client):
    # IDs that don't exist in the DB.
    resp = await client.post(
        "/api/v1/gisaid/export/1",
        params={"pathogen": "SARS-CoV-2"},
        json=[999999],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_gisaid_export_streams_csv_with_seeded_sample(client, cleanup_sample):
    sample = _insert_sars_cov2_sample("EX-GISAID-001")
    cleanup_sample.append(sample["id"])

    resp = await client.post(
        f"/api/v1/gisaid/export/{SEED_LAB_ID}",
        params={"pathogen": "SARS-CoV-2"},
        json=[sample["id"]],
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    assert "gisaid_SARS-CoV-2_" in resp.headers["content-disposition"]

    # Parse the streamed body and confirm the row is well-formed.
    body = resp.text
    reader = csv.DictReader(io.StringIO(body))
    rows = list(reader)
    assert len(rows) == 1
    row = rows[0]
    # GISAID Virus name format: hCoV-19/<Country>/<sample_id>/<year>
    assert row["Virus name"] == "hCoV-19/United_States/EX-GISAID-001/2026"
    assert row["Type"] == "betacoronavirus"
    assert row["Collection date"] == "2026-01-15"
    assert "United States" in row["Location"]
    assert row["Host"] == "Human"
    assert row["Sample ID given by the originating laboratory"] == "EX-GISAID-001"


@pytest.mark.asyncio
async def test_gisaid_export_multiple_samples_one_csv(client, cleanup_sample):
    s1 = _insert_sars_cov2_sample("EX-GISAID-A")
    s2 = _insert_sars_cov2_sample("EX-GISAID-B")
    cleanup_sample.extend([s1["id"], s2["id"]])

    resp = await client.post(
        f"/api/v1/gisaid/export/{SEED_LAB_ID}",
        params={"pathogen": "SARS-CoV-2"},
        json=[s1["id"], s2["id"]],
    )
    assert resp.status_code == 200
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    assert len(rows) == 2
    sample_ids = {r["Sample ID given by the originating laboratory"] for r in rows}
    assert sample_ids == {"EX-GISAID-A", "EX-GISAID-B"}


@pytest.mark.asyncio
async def test_gisaid_export_non_human_source_uses_host_species(client, cleanup_sample):
    sample = _insert_sars_cov2_sample(
        "EX-GISAID-WILDLIFE",
        source_type="Wildlife",
        host_species="Mustela furo",
    )
    cleanup_sample.append(sample["id"])

    resp = await client.post(
        f"/api/v1/gisaid/export/{SEED_LAB_ID}",
        params={"pathogen": "SARS-CoV-2"},
        json=[sample["id"]],
    )
    assert resp.status_code == 200
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    # Non-Human source_type → Host populated from host_species.
    assert rows[0]["Host"] == "Mustela furo"


@pytest.mark.asyncio
async def test_a_flagged_sample_refuses_the_whole_export(client, cleanup_sample):
    """Critical Rule 43 blocks flagged samples from export.

    The refusal covers the whole request rather than dropping the flagged
    rows from the CSV: a submitter who asked for two samples and got one
    has no way to notice, and the omission would surface as a gap in
    GISAID instead of as an error here.
    """
    clean = _insert_sars_cov2_sample("EX-GISAID-PII-CLEAN")
    flagged = _insert_sars_cov2_sample("EX-GISAID-PII-BAD", pii_scan_status="PII_DETECTED")
    cleanup_sample.extend([clean["id"], flagged["id"]])

    resp = await client.post(
        f"/api/v1/gisaid/export/{SEED_LAB_ID}",
        params={"pathogen": "SARS-CoV-2"},
        json=[clean["id"], flagged["id"]],
    )
    assert resp.status_code == 422, resp.text
    detail = str(resp.json())
    assert "EX-GISAID-PII-BAD" in detail
    assert "EX-GISAID-PII-CLEAN" not in detail


@pytest.mark.asyncio
async def test_an_unscanned_sample_still_exports(client, cleanup_sample):
    """PENDING is not a refusal — see the pipeline-gate reasoning.

    Rows sit in PENDING for the length of a Cloud DLP outage; blocking on
    it would make export availability track a Google API's.
    """
    sample = _insert_sars_cov2_sample("EX-GISAID-PII-PENDING", pii_scan_status="PENDING")
    cleanup_sample.append(sample["id"])

    resp = await client.post(
        f"/api/v1/gisaid/export/{SEED_LAB_ID}",
        params={"pathogen": "SARS-CoV-2"},
        json=[sample["id"]],
    )
    assert resp.status_code == 200, resp.text
