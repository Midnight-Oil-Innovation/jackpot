import pytest
from authz_helpers import sync_grants_from_legacy_roles

from backend.config import get_settings
from backend.database import execute_query, execute_write


def _switch_user(monkeypatch, email: str) -> None:
    monkeypatch.setenv("MOCK_USER_EMAIL", email)
    get_settings.cache_clear()


def _ensure_user(email: str, *, is_platform_admin: bool = False) -> int:
    execute_write(
        """
        INSERT INTO users (email, name, is_platform_admin, is_active, organization_id)
        VALUES (:e, 'Test User', :a, TRUE, 1)
        ON CONFLICT (email) DO UPDATE
        SET is_platform_admin = :a, is_active = TRUE, organization_id = 1
        """,
        {"e": email, "a": is_platform_admin},
    )
    row = execute_query("SELECT id FROM users WHERE email = :e", {"e": email})
    # Guards decide on grants since M2-B1; translate the role flags.
    sync_grants_from_legacy_roles()
    return row[0]["id"]


def _pg_id(name: str) -> int:
    row = execute_query(
        "SELECT id FROM permission_groups WHERE name = :n",
        {"n": name},
    )
    return row[0]["id"]


def _cleanup_lab_by_name(name: str) -> None:
    execute_write(
        "DELETE FROM lab_membership WHERE lab_id IN (SELECT id FROM labs WHERE display_name = :n)",
        {"n": name},
    )
    execute_write(
        "DELETE FROM sequencing_labs WHERE lab_id IN (SELECT id FROM labs WHERE display_name = :n)",
        {"n": name},
    )
    execute_write("DELETE FROM labs WHERE display_name = :n", {"n": name})


def _cleanup_user(email: str) -> None:
    execute_write(
        "DELETE FROM lab_membership WHERE user_id IN (SELECT id FROM users WHERE email = :e)",
        {"e": email},
    )
    execute_write(
        "UPDATE audit_log SET actor_id = NULL WHERE actor_id IN "
        "(SELECT id FROM users WHERE email = :e)",
        {"e": email},
    )
    execute_write("DELETE FROM users WHERE email = :e", {"e": email})


@pytest.mark.asyncio
async def test_create_lab_success(client):
    name = "Test Lab CRUD"
    _cleanup_lab_by_name(name)

    resp = await client.post(
        "/api/v1/labs/",
        json={
            "organization_id": 1,
            "display_name": name,
            "description": "A test lab.",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["display_name"] == name
    assert body["data"]["active"] is True
    assert body["data"]["organization_id"] == 1

    lab_id = body["data"]["id"]

    # Audit recorded
    rows = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'lab' AND resource_id = :rid",
        {"rid": str(lab_id)},
    )
    assert any(r["action"] == "CREATE_LAB" for r in rows)

    _cleanup_lab_by_name(name)


@pytest.mark.asyncio
async def test_create_lab_invalid_org_returns_404(client):
    resp = await client.post(
        "/api/v1/labs/",
        json={"organization_id": 999999, "display_name": "Orphan Lab"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_create_lab_non_admin_returns_403(client, monkeypatch):
    email = "lab_nonadmin_create@test.com"
    _ensure_user(email)
    _switch_user(monkeypatch, email)
    resp = await client.post(
        "/api/v1/labs/",
        json={"organization_id": 1, "display_name": "Blocked Lab"},
    )
    assert resp.status_code == 403
    _cleanup_user(email)


@pytest.mark.asyncio
async def test_get_lab_404(client):
    resp = await client.get("/api/v1/labs/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_lab_as_admin(client):
    name = "Admin Gettable Lab"
    _cleanup_lab_by_name(name)
    resp = await client.post(
        "/api/v1/labs/",
        json={"organization_id": 1, "display_name": name},
    )
    assert resp.status_code == 201
    lab_id = resp.json()["data"]["id"]

    resp = await client.get(f"/api/v1/labs/{lab_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == lab_id
    _cleanup_lab_by_name(name)


@pytest.mark.asyncio
async def test_get_lab_non_member_returns_403(client, monkeypatch):
    name = "Private Lab"
    _cleanup_lab_by_name(name)
    resp = await client.post(
        "/api/v1/labs/",
        json={"organization_id": 1, "display_name": name},
    )
    lab_id = resp.json()["data"]["id"]

    email = "lab_outsider@test.com"
    _ensure_user(email)
    _switch_user(monkeypatch, email)
    resp = await client.get(f"/api/v1/labs/{lab_id}")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ACCESS_DENIED"
    _cleanup_user(email)
    _cleanup_lab_by_name(name)


@pytest.mark.asyncio
async def test_patch_lab_as_admin(client):
    name = "Patch Lab"
    _cleanup_lab_by_name(name)
    resp = await client.post(
        "/api/v1/labs/",
        json={"organization_id": 1, "display_name": name},
    )
    lab_id = resp.json()["data"]["id"]

    resp = await client.patch(
        f"/api/v1/labs/{lab_id}",
        json={"description": "Updated description"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["description"] == "Updated description"

    # Empty patch rejected
    resp = await client.patch(f"/api/v1/labs/{lab_id}", json={})
    assert resp.status_code == 400
    _cleanup_lab_by_name(name)


@pytest.mark.asyncio
async def test_patch_lab_by_director(client, monkeypatch):
    name = "Director Patch Lab"
    _cleanup_lab_by_name(name)
    resp = await client.post(
        "/api/v1/labs/",
        json={"organization_id": 1, "display_name": name},
    )
    lab_id = resp.json()["data"]["id"]

    director_email = "lab_director_patch@test.com"
    director_id = _ensure_user(director_email)
    # add as director
    resp = await client.post(
        f"/api/v1/labs/{lab_id}/members",
        json={
            "user_id": director_id,
            "permission_group_id": _pg_id("Lab Director"),
            "is_lab_director": True,
        },
    )
    assert resp.status_code == 201
    # The membership was created after _ensure_user ran, so re-sync: a
    # membership only becomes access once grants exist for it. In production
    # M2-B5 makes POST /labs/{id}/members issue the grants directly — until
    # then a new member holds nothing until a reseed runs.
    sync_grants_from_legacy_roles()

    _switch_user(monkeypatch, director_email)
    resp = await client.patch(
        f"/api/v1/labs/{lab_id}",
        json={"description": "Director-updated"},
    )
    assert resp.status_code == 200
    _cleanup_user(director_email)
    _cleanup_lab_by_name(name)


@pytest.mark.asyncio
async def test_patch_lab_by_reader_returns_403(client, monkeypatch):
    name = "Reader Blocked Lab"
    _cleanup_lab_by_name(name)
    resp = await client.post(
        "/api/v1/labs/",
        json={"organization_id": 1, "display_name": name},
    )
    lab_id = resp.json()["data"]["id"]

    reader_email = "lab_reader@test.com"
    reader_id = _ensure_user(reader_email)
    resp = await client.post(
        f"/api/v1/labs/{lab_id}/members",
        json={
            "user_id": reader_id,
            "permission_group_id": _pg_id("Lab Reader"),
            "is_lab_director": False,
        },
    )
    assert resp.status_code == 201

    _switch_user(monkeypatch, reader_email)
    resp = await client.patch(
        f"/api/v1/labs/{lab_id}",
        json={"description": "Hack"},
    )
    assert resp.status_code == 403
    _cleanup_user(reader_email)
    _cleanup_lab_by_name(name)


@pytest.mark.asyncio
async def test_delete_lab_soft(client):
    name = "Deletable Lab"
    _cleanup_lab_by_name(name)
    resp = await client.post(
        "/api/v1/labs/",
        json={"organization_id": 1, "display_name": name},
    )
    lab_id = resp.json()["data"]["id"]

    resp = await client.delete(f"/api/v1/labs/{lab_id}")
    assert resp.status_code == 200
    assert "deactivated" in resp.json()["message"].lower()

    resp = await client.get(f"/api/v1/labs/{lab_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["active"] is False
    _cleanup_lab_by_name(name)


@pytest.mark.asyncio
async def test_delete_lab_non_admin_returns_403(client, monkeypatch):
    name = "Protected Lab"
    _cleanup_lab_by_name(name)
    resp = await client.post(
        "/api/v1/labs/",
        json={"organization_id": 1, "display_name": name},
    )
    lab_id = resp.json()["data"]["id"]

    email = "lab_del_blocked@test.com"
    _ensure_user(email)
    _switch_user(monkeypatch, email)
    resp = await client.delete(f"/api/v1/labs/{lab_id}")
    assert resp.status_code == 403
    _cleanup_user(email)
    _cleanup_lab_by_name(name)


@pytest.mark.asyncio
async def test_list_labs_admin_sees_all(client):
    names = [f"ListAll-{i}" for i in range(3)]
    for n in names:
        _cleanup_lab_by_name(n)
        resp = await client.post(
            "/api/v1/labs/",
            json={"organization_id": 1, "display_name": n},
        )
        assert resp.status_code == 201

    resp = await client.get("/api/v1/labs/?per_page=200")
    assert resp.status_code == 200
    found = {x["display_name"] for x in resp.json()["data"]}
    assert set(names).issubset(found)
    for n in names:
        _cleanup_lab_by_name(n)


@pytest.mark.asyncio
async def test_list_labs_non_admin_sees_only_their_labs(client, monkeypatch):
    mine = "MineLab"
    theirs = "TheirsLab"
    _cleanup_lab_by_name(mine)
    _cleanup_lab_by_name(theirs)
    r1 = await client.post(
        "/api/v1/labs/",
        json={"organization_id": 1, "display_name": mine},
    )
    await client.post(
        "/api/v1/labs/",
        json={"organization_id": 1, "display_name": theirs},
    )
    mine_id = r1.json()["data"]["id"]

    email = "lab_list_user@test.com"
    uid = _ensure_user(email)
    resp = await client.post(
        f"/api/v1/labs/{mine_id}/members",
        json={
            "user_id": uid,
            "permission_group_id": _pg_id("Lab Collaborator"),
        },
    )
    assert resp.status_code == 201

    _switch_user(monkeypatch, email)
    resp = await client.get("/api/v1/labs/?per_page=200")
    assert resp.status_code == 200
    names = {x["display_name"] for x in resp.json()["data"]}
    assert mine in names
    assert theirs not in names

    _cleanup_user(email)
    _cleanup_lab_by_name(mine)
    _cleanup_lab_by_name(theirs)


@pytest.mark.asyncio
async def test_members_lifecycle(client):
    name = "Members Lab"
    _cleanup_lab_by_name(name)
    resp = await client.post(
        "/api/v1/labs/",
        json={"organization_id": 1, "display_name": name},
    )
    lab_id = resp.json()["data"]["id"]

    email = "member@test.com"
    uid = _ensure_user(email)
    pg_collaborator = _pg_id("Lab Collaborator")
    pg_director = _pg_id("Lab Director")

    # Add
    resp = await client.post(
        f"/api/v1/labs/{lab_id}/members",
        json={"user_id": uid, "permission_group_id": pg_collaborator},
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["is_lab_director"] is False

    # List
    resp = await client.get(f"/api/v1/labs/{lab_id}/members")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert any(m["user_id"] == uid for m in data)
    mine = next(m for m in data if m["user_id"] == uid)
    assert mine["permission_group_name"] == "Lab Collaborator"
    assert mine["email"] == email

    # Duplicate add → 409
    resp = await client.post(
        f"/api/v1/labs/{lab_id}/members",
        json={"user_id": uid, "permission_group_id": pg_collaborator},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"

    # Change role
    resp = await client.patch(
        f"/api/v1/labs/{lab_id}/members/{uid}",
        json={"permission_group_id": pg_director, "is_lab_director": True},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_lab_director"] is True

    # Remove
    resp = await client.delete(f"/api/v1/labs/{lab_id}/members/{uid}")
    assert resp.status_code == 200

    # Second remove → 404
    resp = await client.delete(f"/api/v1/labs/{lab_id}/members/{uid}")
    assert resp.status_code == 404

    # Audit entries
    audits = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'lab_membership' "
        "ORDER BY id DESC LIMIT 20",
    )
    actions = [r["action"] for r in audits]
    for expected in ("ADD_LAB_MEMBER", "CHANGE_MEMBER_ROLE", "REMOVE_LAB_MEMBER"):
        assert expected in actions

    _cleanup_user(email)
    _cleanup_lab_by_name(name)


@pytest.mark.asyncio
async def test_members_add_unknown_user_returns_404(client):
    name = "Unknown User Lab"
    _cleanup_lab_by_name(name)
    resp = await client.post(
        "/api/v1/labs/",
        json={"organization_id": 1, "display_name": name},
    )
    lab_id = resp.json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/labs/{lab_id}/members",
        json={"user_id": 999999, "permission_group_id": _pg_id("Lab Reader")},
    )
    assert resp.status_code == 404
    _cleanup_lab_by_name(name)


@pytest.mark.asyncio
async def test_members_add_unknown_permission_group_returns_404(client):
    name = "Unknown PG Lab"
    _cleanup_lab_by_name(name)
    resp = await client.post(
        "/api/v1/labs/",
        json={"organization_id": 1, "display_name": name},
    )
    lab_id = resp.json()["data"]["id"]

    email = "pg_test@test.com"
    uid = _ensure_user(email)
    resp = await client.post(
        f"/api/v1/labs/{lab_id}/members",
        json={"user_id": uid, "permission_group_id": 999999},
    )
    assert resp.status_code == 404
    _cleanup_user(email)
    _cleanup_lab_by_name(name)


@pytest.mark.asyncio
async def test_members_endpoint_non_director_returns_403(client, monkeypatch):
    name = "Members Protected Lab"
    _cleanup_lab_by_name(name)
    resp = await client.post(
        "/api/v1/labs/",
        json={"organization_id": 1, "display_name": name},
    )
    lab_id = resp.json()["data"]["id"]

    reader_email = "members_reader@test.com"
    reader_id = _ensure_user(reader_email)
    resp = await client.post(
        f"/api/v1/labs/{lab_id}/members",
        json={
            "user_id": reader_id,
            "permission_group_id": _pg_id("Lab Reader"),
        },
    )
    assert resp.status_code == 201

    _switch_user(monkeypatch, reader_email)
    resp = await client.get(f"/api/v1/labs/{lab_id}/members")
    assert resp.status_code == 403
    _cleanup_user(reader_email)
    _cleanup_lab_by_name(name)
