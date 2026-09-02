import pytest
from authz_helpers import ADMIN_PRESET, grant_instance_preset

from backend.config import get_settings
from backend.database import execute_query, execute_write


def _switch_user(monkeypatch, email: str) -> None:
    monkeypatch.setenv("MOCK_USER_EMAIL", email)
    get_settings.cache_clear()


def _ensure_user(email: str, *, is_platform_admin: bool = False) -> int:
    execute_write(
        """
        INSERT INTO users (email, name, is_active, organization_id)
        VALUES (:e, 'Test User', TRUE, 1)
        ON CONFLICT (email) DO UPDATE
        SET is_active = TRUE, organization_id = 1
        """,
        {"e": email},
    )
    row = execute_query("SELECT id FROM users WHERE email = :e", {"e": email})
    uid = row[0]["id"]
    # The role is the grants now (M2-DROP). Issued in both directions: these
    # helpers upsert on a re-used email, so a demotion must revoke rather than
    # leave a stale admin grant behind.
    grant_instance_preset(uid, ADMIN_PRESET if is_platform_admin else None)
    return uid


def _cleanup_user(email: str) -> None:
    execute_write(
        "UPDATE audit_log SET actor_id = NULL WHERE actor_id IN "
        "(SELECT id FROM users WHERE email = :e)",
        {"e": email},
    )
    execute_write("DELETE FROM users WHERE email = :e", {"e": email})


def _cleanup_seq_lab_by_name(name: str) -> None:
    execute_write(
        "DELETE FROM sequencing_lab_assignments WHERE sequencing_lab_id IN "
        "(SELECT id FROM sequencing_labs WHERE name = :n)",
        {"n": name},
    )
    execute_write("DELETE FROM sequencing_labs WHERE name = :n", {"n": name})


def _cleanup_lab_by_name(name: str) -> None:
    execute_write(
        "DELETE FROM sequencing_lab_assignments WHERE lab_id IN "
        "(SELECT id FROM labs WHERE display_name = :n)",
        {"n": name},
    )
    execute_write(
        "DELETE FROM lab_membership WHERE lab_id IN (SELECT id FROM labs WHERE display_name = :n)",
        {"n": name},
    )
    execute_write("DELETE FROM labs WHERE display_name = :n", {"n": name})


@pytest.mark.asyncio
async def test_list_sequencing_labs_seed_data_visible(client):
    resp = await client.get("/api/v1/sequencing-labs/?per_page=200")
    assert resp.status_code == 200, resp.text
    names = [r["name"] for r in resp.json()["data"]]
    assert "Example Sequencing Lab" in names
    assert "Example Reference Lab" in names


@pytest.mark.asyncio
async def test_list_sequencing_labs_any_authenticated(client, monkeypatch):
    email = "seq_labs_reader@test.com"
    _ensure_user(email)
    _switch_user(monkeypatch, email)
    resp = await client.get("/api/v1/sequencing-labs/")
    assert resp.status_code == 200
    _cleanup_user(email)


@pytest.mark.asyncio
async def test_create_sequencing_lab_admin(client):
    name = "Test Seq Lab"
    _cleanup_seq_lab_by_name(name)
    resp = await client.post(
        "/api/v1/sequencing-labs/",
        json={"name": name, "organization": "Org", "is_external": True},
    )
    assert resp.status_code == 201, resp.text
    row = resp.json()["data"]
    assert row["name"] == name
    assert row["is_active"] is True

    rows = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'sequencing_lab' "
        "AND resource_id = :rid",
        {"rid": str(row["id"])},
    )
    assert any(r["action"] == "CREATE_SEQUENCING_LAB" for r in rows)
    _cleanup_seq_lab_by_name(name)


@pytest.mark.asyncio
async def test_create_sequencing_lab_duplicate_returns_409(client):
    name = "Dup Seq Lab"
    _cleanup_seq_lab_by_name(name)
    r1 = await client.post("/api/v1/sequencing-labs/", json={"name": name})
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/sequencing-labs/", json={"name": name})
    assert r2.status_code == 409
    _cleanup_seq_lab_by_name(name)


@pytest.mark.asyncio
async def test_create_sequencing_lab_non_admin_returns_403(client, monkeypatch):
    email = "seq_labs_nonadmin_create@test.com"
    _ensure_user(email)
    _switch_user(monkeypatch, email)
    resp = await client.post("/api/v1/sequencing-labs/", json={"name": "Blocked SL"})
    assert resp.status_code == 403
    _cleanup_user(email)


@pytest.mark.asyncio
async def test_get_sequencing_lab(client):
    name = "Gettable Seq Lab"
    _cleanup_seq_lab_by_name(name)
    r1 = await client.post("/api/v1/sequencing-labs/", json={"name": name})
    sid = r1.json()["data"]["id"]

    r2 = await client.get(f"/api/v1/sequencing-labs/{sid}")
    assert r2.status_code == 200
    assert r2.json()["data"]["name"] == name
    _cleanup_seq_lab_by_name(name)


@pytest.mark.asyncio
async def test_get_sequencing_lab_not_found(client):
    resp = await client.get("/api/v1/sequencing-labs/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_sequencing_lab(client):
    name = "Patchable Seq Lab"
    _cleanup_seq_lab_by_name(name)
    r1 = await client.post("/api/v1/sequencing-labs/", json={"name": name})
    sid = r1.json()["data"]["id"]

    r2 = await client.patch(
        f"/api/v1/sequencing-labs/{sid}",
        json={"organization": "New Org", "is_active": False},
    )
    assert r2.status_code == 200
    data = r2.json()["data"]
    assert data["organization"] == "New Org"
    assert data["is_active"] is False

    # Empty patch rejected
    r3 = await client.patch(f"/api/v1/sequencing-labs/{sid}", json={})
    assert r3.status_code == 400
    _cleanup_seq_lab_by_name(name)


@pytest.mark.asyncio
async def test_patch_sequencing_lab_non_admin_returns_403(client, monkeypatch):
    name = "Protected Seq Lab"
    _cleanup_seq_lab_by_name(name)
    r1 = await client.post("/api/v1/sequencing-labs/", json={"name": name})
    sid = r1.json()["data"]["id"]

    email = "seq_labs_nonadmin_patch@test.com"
    _ensure_user(email)
    _switch_user(monkeypatch, email)
    r2 = await client.patch(f"/api/v1/sequencing-labs/{sid}", json={"organization": "Hack"})
    assert r2.status_code == 403
    _cleanup_user(email)
    _cleanup_seq_lab_by_name(name)


@pytest.mark.asyncio
async def test_assign_sequencing_lab_roundtrip(client):
    sname = "Assignable Seq Lab"
    lname = "Assignable Lab"
    _cleanup_seq_lab_by_name(sname)
    _cleanup_lab_by_name(lname)

    s = await client.post("/api/v1/sequencing-labs/", json={"name": sname})
    sid = s.json()["data"]["id"]
    lab_resp = await client.post(
        "/api/v1/labs/",
        json={"organization_id": 1, "display_name": lname},
    )
    lid = lab_resp.json()["data"]["id"]

    # Assign
    r1 = await client.post(f"/api/v1/sequencing-labs/{sid}/assign/{lid}")
    assert r1.status_code == 201, r1.text
    assignment_id = r1.json()["data"]["id"]

    # Duplicate assign → 409
    r2 = await client.post(f"/api/v1/sequencing-labs/{sid}/assign/{lid}")
    assert r2.status_code == 409

    rows = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'sequencing_lab_assignment' "
        "AND resource_id = :rid",
        {"rid": str(assignment_id)},
    )
    assert any(r["action"] == "ASSIGN_SEQUENCING_LAB" for r in rows)

    # Unassign
    r3 = await client.delete(f"/api/v1/sequencing-labs/{sid}/assign/{lid}")
    assert r3.status_code == 200

    # Second unassign → 404
    r4 = await client.delete(f"/api/v1/sequencing-labs/{sid}/assign/{lid}")
    assert r4.status_code == 404

    _cleanup_lab_by_name(lname)
    _cleanup_seq_lab_by_name(sname)


@pytest.mark.asyncio
async def test_assign_unknown_sequencing_lab_returns_404(client):
    resp = await client.post("/api/v1/sequencing-labs/999999/assign/1")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_assign_unknown_lab_returns_404(client):
    sname = "SL for unknown lab"
    _cleanup_seq_lab_by_name(sname)
    r1 = await client.post("/api/v1/sequencing-labs/", json={"name": sname})
    sid = r1.json()["data"]["id"]

    resp = await client.post(f"/api/v1/sequencing-labs/{sid}/assign/999999")
    assert resp.status_code == 404
    _cleanup_seq_lab_by_name(sname)


@pytest.mark.asyncio
async def test_assign_sequencing_lab_non_admin_returns_403(client, monkeypatch):
    email = "seq_labs_nonadmin_assign@test.com"
    _ensure_user(email)
    _switch_user(monkeypatch, email)
    resp = await client.post("/api/v1/sequencing-labs/1/assign/1")
    assert resp.status_code == 403
    _cleanup_user(email)
