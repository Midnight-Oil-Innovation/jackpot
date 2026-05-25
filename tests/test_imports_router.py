"""I-1 router tests for /api/v1/imports/sessions/."""

from __future__ import annotations

import pytest

from backend.database import execute_write


def _cleanup_sessions(user_id: int = 1) -> None:
    execute_write(
        "DELETE FROM import_sessions WHERE created_by_user_id = :uid",
        {"uid": user_id},
    )


@pytest.mark.asyncio
async def test_create_session_csv_returns_session_id_and_metadata(client):
    _cleanup_sessions()
    csv_bytes = b"Sample ID,Country\nEX-001,USA\n"
    resp = await client.post(
        "/api/v1/imports/sessions/",
        data={"lab_id": "1"},
        files={"file": ("samples.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["file_name"] == "samples.csv"
    assert data["file_format"] == "csv"
    assert data["current_step"] == 1
    assert data["status"] == "in_progress"
    assert "spreadsheet_meta" in data
    _cleanup_sessions()


@pytest.mark.asyncio
async def test_create_session_unsupported_extension_returns_400(client):
    resp = await client.post(
        "/api/v1/imports/sessions/",
        data={"lab_id": "1"},
        files={"file": ("samples.txt", b"junk", "text/plain")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_session_empty_file_returns_400(client):
    resp = await client.post(
        "/api/v1/imports/sessions/",
        data={"lab_id": "1"},
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_sessions_returns_user_in_progress(client):
    _cleanup_sessions()
    csv_bytes = b"Sample ID\nEX-001\n"
    await client.post(
        "/api/v1/imports/sessions/",
        data={"lab_id": "1"},
        files={"file": ("a.csv", csv_bytes, "text/csv")},
    )
    resp = await client.get("/api/v1/imports/sessions/")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert any(s["file_name"] == "a.csv" for s in data)
    _cleanup_sessions()


@pytest.mark.asyncio
async def test_get_session_round_trip(client):
    _cleanup_sessions()
    create = await client.post(
        "/api/v1/imports/sessions/",
        data={"lab_id": "1"},
        files={"file": ("rt.csv", b"Sample ID\nX\n", "text/csv")},
    )
    sid = create.json()["data"]["id"]
    resp = await client.get(f"/api/v1/imports/sessions/{sid}")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == sid
    _cleanup_sessions()


@pytest.mark.asyncio
async def test_patch_session_invalidates_downstream_state(client):
    _cleanup_sessions()
    create = await client.post(
        "/api/v1/imports/sessions/",
        data={"lab_id": "1"},
        files={"file": ("p.csv", b"A,B\n1,2\n", "text/csv")},
    )
    sid = create.json()["data"]["id"]
    # Seed downstream cached state via direct UPDATE so we can verify
    # the PATCH endpoint clears it. Pass the JSON via bound params —
    # inlining literal JSON breaks SQLAlchemy's colon-parameter parser.
    execute_write(
        "UPDATE import_sessions SET preview_results = CAST(:p AS JSONB), "
        "diff_results = CAST(:d AS JSONB) WHERE id = :id",
        {"id": sid, "p": '{"x":1}', "d": '{"y":2}'},
    )
    resp = await client.patch(
        f"/api/v1/imports/sessions/{sid}",
        json={"column_mapping": {"A": "sample_id"}},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["preview_results"] is None
    assert data["diff_results"] is None
    _cleanup_sessions()


@pytest.mark.asyncio
async def test_delete_session_marks_abandoned(client):
    _cleanup_sessions()
    create = await client.post(
        "/api/v1/imports/sessions/",
        data={"lab_id": "1"},
        files={"file": ("d.csv", b"A\n1\n", "text/csv")},
    )
    sid = create.json()["data"]["id"]
    resp = await client.delete(f"/api/v1/imports/sessions/{sid}")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "abandoned"
    _cleanup_sessions()


@pytest.mark.asyncio
async def test_get_session_expired_returns_410(client):
    _cleanup_sessions()
    create = await client.post(
        "/api/v1/imports/sessions/",
        data={"lab_id": "1"},
        files={"file": ("e.csv", b"A\n1\n", "text/csv")},
    )
    sid = create.json()["data"]["id"]
    execute_write(
        "UPDATE import_sessions SET expires_at = NOW() - INTERVAL '1 hour' WHERE id = :id",
        {"id": sid},
    )
    resp = await client.get(f"/api/v1/imports/sessions/{sid}")
    assert resp.status_code == 410
    _cleanup_sessions()
