import pytest

from backend.routers.gisaid import GISAID_SARS_COV2_COLUMNS


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
async def test_gisaid_export_empty_ids_returns_400(client):
    resp = await client.post(
        "/api/v1/gisaid/export/1",
        params={"pathogen": "SARS-CoV-2"},
        json=[],
    )
    assert resp.status_code == 400
