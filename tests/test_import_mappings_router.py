"""I-1 router tests for /api/v1/import_mappings/."""

from __future__ import annotations

import pytest

from backend.database import execute_write


def _cleanup() -> None:
    execute_write("DELETE FROM import_mappings WHERE display_name LIKE 'I1-MAP-%'")


@pytest.mark.asyncio
async def test_create_then_get_mapping(client):
    _cleanup()
    body = {
        "lab_id": 1,
        "display_name": "I1-MAP-A",
        "description": "Test mapping",
        "column_mapping": {"Sample ID": "sample_id"},
        "file_reference_pattern": {"type": "none"},
    }
    create = await client.post("/api/v1/import_mappings/", json=body)
    assert create.status_code == 201, create.text
    mid = create.json()["data"]["id"]

    fetch = await client.get(f"/api/v1/import_mappings/{mid}")
    assert fetch.status_code == 200
    fetched = fetch.json()["data"]
    assert fetched["display_name"] == "I1-MAP-A"
    assert fetched["column_mapping"] == {"Sample ID": "sample_id"}
    _cleanup()


@pytest.mark.asyncio
async def test_list_mappings_returns_envelope_with_pagination(client):
    _cleanup()
    for i in range(3):
        await client.post(
            "/api/v1/import_mappings/",
            json={
                "lab_id": 1,
                "display_name": f"I1-MAP-LIST-{i}",
                "column_mapping": {"a": "sample_id"},
            },
        )
    resp = await client.get("/api/v1/import_mappings/?lab_id=1")
    assert resp.status_code == 200
    body = resp.json()
    assert "pagination" in body
    names = {r["display_name"] for r in body["data"]}
    assert any(n.startswith("I1-MAP-LIST") for n in names)
    _cleanup()


@pytest.mark.asyncio
async def test_patch_mapping_updates_fields(client):
    _cleanup()
    create = await client.post(
        "/api/v1/import_mappings/",
        json={
            "lab_id": 1,
            "display_name": "I1-MAP-P",
            "column_mapping": {"a": "sample_id"},
        },
    )
    mid = create.json()["data"]["id"]
    patch = await client.patch(
        f"/api/v1/import_mappings/{mid}",
        json={"display_name": "I1-MAP-P-renamed", "description": "updated"},
    )
    assert patch.status_code == 200
    data = patch.json()["data"]
    assert data["display_name"] == "I1-MAP-P-renamed"
    assert data["description"] == "updated"
    _cleanup()


@pytest.mark.asyncio
async def test_delete_mapping_soft_deletes(client):
    _cleanup()
    create = await client.post(
        "/api/v1/import_mappings/",
        json={
            "lab_id": 1,
            "display_name": "I1-MAP-D",
            "column_mapping": {"a": "sample_id"},
        },
    )
    mid = create.json()["data"]["id"]
    resp = await client.delete(f"/api/v1/import_mappings/{mid}")
    assert resp.status_code == 200
    fetch = await client.get(f"/api/v1/import_mappings/{mid}")
    assert fetch.json()["data"]["is_active"] is False
    _cleanup()


@pytest.mark.asyncio
async def test_get_unknown_mapping_returns_404(client):
    resp = await client.get("/api/v1/import_mappings/9999999")
    assert resp.status_code == 404
