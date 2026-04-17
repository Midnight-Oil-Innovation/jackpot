import pytest


@pytest.mark.asyncio
async def test_download_template_csv(client):
    resp = await client.get("/api/v1/dataharmonizer/templates/human/ANALYZABLE")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    body = resp.text
    first_line = body.splitlines()[0]
    # header row should expose schema field names
    assert "sample_id" in first_line
    assert "source_type" in first_line


@pytest.mark.asyncio
async def test_download_template_lowercase_tier(client):
    resp = await client.get("/api/v1/dataharmonizer/templates/human/preliminary")
    assert resp.status_code == 200
    assert "preliminary" in resp.headers["content-disposition"].lower()


@pytest.mark.asyncio
async def test_download_template_metagenomics(client):
    resp = await client.get("/api/v1/dataharmonizer/templates/water/ANALYZABLE?metagenomics=true")
    assert resp.status_code == 200
    assert "metagenomics" in resp.headers["content-disposition"]


@pytest.mark.asyncio
async def test_download_template_unknown_source_returns_400(client):
    resp = await client.get("/api/v1/dataharmonizer/templates/martian/ANALYZABLE")
    assert resp.status_code == 400
    assert "source_type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_download_template_unknown_tier_returns_400(client):
    resp = await client.get("/api/v1/dataharmonizer/templates/human/LEGENDARY")
    assert resp.status_code == 400
    assert "tier" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_validate_empty_body_returns_400(client):
    resp = await client.post(
        "/api/v1/dataharmonizer/validate",
        content=b"",
        headers={"content-type": "text/csv"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_validate_no_data_rows_returns_400(client):
    # Only a header → no records
    csv_body = "sample_id,organism_name\n"
    resp = await client.post(
        "/api/v1/dataharmonizer/validate",
        content=csv_body.encode(),
        headers={"content-type": "text/csv"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_validate_valid_row(client):
    # Use "Isolate" — no source-type-specific required fields
    csv_body = (
        "sample_id,organism_name,source_type,date_collected,"
        "collection_location_country,sequencing_platform,type_of_experiment\n"
        "AZ-001,Escherichia coli,Isolate,"
        "2026-01-15,United States,Illumina,WGS\n"
    )
    resp = await client.post(
        "/api/v1/dataharmonizer/validate",
        content=csv_body.encode(),
        headers={"content-type": "text/csv"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_rows"] == 1
    assert body["valid_rows"] == 1
    row = body["results"][0]
    assert row["sample_id"] == "AZ-001"
    assert row["valid"] is True
    assert row["errors"] == []


@pytest.mark.asyncio
async def test_validate_missing_required_row(client):
    # Missing organism_name, date_collected, etc.
    csv_body = "sample_id,source_type\nAZ-002,Human\n"
    resp = await client.post(
        "/api/v1/dataharmonizer/validate",
        content=csv_body.encode(),
        headers={"content-type": "text/csv"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_rows"] == 1
    assert body["valid_rows"] == 0
    row = body["results"][0]
    assert row["valid"] is False
    assert any("organism_name" in e for e in row["errors"])


@pytest.mark.asyncio
async def test_validate_multiple_rows(client):
    csv_body = (
        "sample_id,organism_name,source_type,date_collected,"
        "collection_location_country,sequencing_platform,type_of_experiment\n"
        "AZ-100,Escherichia coli,Isolate,"
        "2026-01-15,United States,Illumina,WGS\n"
        "AZ-101,,Isolate,2026-01-16,United States,Illumina,WGS\n"
    )
    resp = await client.post(
        "/api/v1/dataharmonizer/validate",
        content=csv_body.encode(),
        headers={"content-type": "text/csv"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_rows"] == 2
    assert body["valid_rows"] == 1
    assert body["results"][0]["valid"] is True
    assert body["results"][1]["valid"] is False


@pytest.mark.asyncio
async def test_validate_non_utf8_returns_400(client):
    # Invalid UTF-8 bytes
    bad = b"sample_id\n\xff\xfe bad \n"
    resp = await client.post(
        "/api/v1/dataharmonizer/validate",
        content=bad,
        headers={"content-type": "text/csv"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_validate_skips_template_meta_rows(client):
    # Full template has header + label + tier-tag + hint + example rows.
    # Parser should skip the meta rows and validate only real data.
    csv_body = (
        "sample_id,organism_name,source_type,date_collected,"
        "collection_location_country,sequencing_platform,type_of_experiment\n"
        "Sample ID,Organism Name,Source Type,Date Collected,Country,Platform,Experiment\n"
        "REQUIRED,REQUIRED,REQUIRED,REQUIRED,REQUIRED,REQUIRED,REQUIRED\n"
        "AZ-ID,Pathogen species name,Human,YYYY-MM-DD,Country name,Illumina/ONT,WGS\n"
        "AZ-200,Severe acute respiratory syndrome coronavirus 2,Human,"
        "2026-02-01,United States,Illumina,WGS\n"
    )
    resp = await client.post(
        "/api/v1/dataharmonizer/validate",
        content=csv_body.encode(),
        headers={"content-type": "text/csv"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Should find exactly 1 data row — the one after REQUIRED tag row
    sample_ids = [r["sample_id"] for r in body["results"]]
    assert "AZ-200" in sample_ids
