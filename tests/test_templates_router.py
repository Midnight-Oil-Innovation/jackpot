"""Tests for the templates router — coverage gap closure (P0e D).

The Phase 22 review showed templates.py at 53%; uncovered lines were
the actual CSV-generation path (58-72), the xlsx 501 branch, the
companion-enums endpoint (97-98), and source-types (104).
"""

import csv
import io

import pytest


@pytest.mark.asyncio
async def test_template_csv_for_human_preliminary(client):
    resp = await client.get(
        "/api/v1/templates/",
        params={"source_type": "human", "tier": "PRELIMINARY"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "human_preliminary" in resp.headers["content-disposition"].lower()
    # CSV body must parse and have a header row.
    rows = list(csv.reader(io.StringIO(resp.text)))
    assert len(rows) >= 1
    assert "sample_id" in rows[0]


@pytest.mark.asyncio
async def test_template_csv_for_human_analyzable_default_tier(client):
    # Default tier when omitted is ANALYZABLE.
    resp = await client.get(
        "/api/v1/templates/",
        params={"source_type": "human"},
    )
    assert resp.status_code == 200
    assert "human_analyzable" in resp.headers["content-disposition"].lower()


@pytest.mark.asyncio
async def test_template_csv_metagenomics_overlay(client):
    resp = await client.get(
        "/api/v1/templates/",
        params={
            "source_type": "human",
            "tier": "ANALYZABLE",
            "metagenomics": True,
        },
    )
    assert resp.status_code == 200
    # File name suffix encodes the metagenomics overlay.
    assert "metagenomics" in resp.headers["content-disposition"].lower()
    rows = list(csv.reader(io.StringIO(resp.text)))
    headers = rows[0]
    assert "target_organisms" in headers


@pytest.mark.asyncio
async def test_template_xlsx_returns_501(client):
    """XLSX generation is Month 2 work; for now returns 501."""
    resp = await client.get(
        "/api/v1/templates/",
        params={"source_type": "human", "format": "xlsx"},
    )
    assert resp.status_code == 501
    body = resp.json()
    # Note: this endpoint pre-dates the envelope-conformance push for
    # stub routers; the body is the raw {"detail": "..."} from the
    # legacy hand-built JSONResponse. Acceptable for now — flag for
    # later cleanup if a future P fixes the envelope shape here too.
    assert "XLSX" in body.get("detail", "")


@pytest.mark.asyncio
async def test_template_unknown_source_type_falls_back_to_default(client):
    """`source_type` Query enum= is OpenAPI metadata only — Click
    doesn't enforce. Unknown values fall through to the default
    template generator without raising. (If Phase 28 hardens this
    to 422, update the assertion.)"""
    resp = await client.get(
        "/api/v1/templates/",
        params={"source_type": "definitely_not_a_real_source_type"},
    )
    assert resp.status_code == 200
    # Body is still a CSV with the canonical sample_id column.
    rows = list(csv.reader(io.StringIO(resp.text)))
    assert "sample_id" in rows[0]


@pytest.mark.asyncio
async def test_template_enums_endpoint(client):
    """The /enums endpoint returns the enum values for each enum-typed
    field in the template (used by LIMS integrations).

    Shape: {<field_name>: {label, values: list[str], required_at_tier}}.
    """
    resp = await client.get(
        "/api/v1/templates/enums",
        params={"source_type": "human", "tier": "ANALYZABLE"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, dict)
    # Spot-check a known enum field by walking the actual shape.
    assert any(
        isinstance(v, dict) and isinstance(v.get("values"), list) and len(v["values"]) > 0
        for v in body.values()
    )


@pytest.mark.asyncio
async def test_template_enums_metagenomics_overlay(client):
    resp = await client.get(
        "/api/v1/templates/enums",
        params={
            "source_type": "human",
            "tier": "ANALYZABLE",
            "metagenomics": True,
        },
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_source_types_returns_keys_and_labels(client):
    resp = await client.get("/api/v1/templates/source-types")
    assert resp.status_code == 200
    body = resp.json()
    assert "source_types" in body
    types = body["source_types"]
    assert isinstance(types, list)
    assert len(types) >= 1
    # Each entry must have the contract shape.
    for entry in types:
        assert "key" in entry
        assert "class_name" in entry
        assert "label" in entry
    # `human` must be among them — it's the canonical Scenario A/B/C source.
    keys = {e["key"] for e in types}
    assert "human" in keys
