import pytest

from backend.config import get_settings
from backend.database import execute_query, execute_write


def _make_non_admin(email: str = "nonadmin@test.com") -> None:
    execute_write(
        """
        INSERT INTO users (email, name, is_active, organization_id)
        VALUES (:e, 'Non Admin', TRUE, 1)
        ON CONFLICT (email) DO UPDATE
        SET is_active = TRUE, organization_id = 1
        """,
        {"e": email},
    )


def _make_org_member(email: str, org_id: int) -> None:
    execute_write(
        """
        INSERT INTO users (email, name, is_active, organization_id)
        VALUES (:e, 'Org Member', TRUE, :o)
        ON CONFLICT (email) DO UPDATE
        SET organization_id = :o, is_active = TRUE
        """,
        {"e": email, "o": org_id},
    )


def _switch_user(monkeypatch, email: str) -> None:
    monkeypatch.setenv("MOCK_USER_EMAIL", email)
    get_settings.cache_clear()


def _cleanup_org(name: str) -> None:
    execute_write(
        "UPDATE users SET organization_id = 1 "
        "WHERE organization_id = (SELECT id FROM organizations WHERE display_name = :n)",
        {"n": name},
    )
    execute_write("DELETE FROM organizations WHERE display_name = :n", {"n": name})


@pytest.mark.asyncio
async def test_crud_roundtrip(client):
    name = "Test Org CRUD"
    _cleanup_org(name)

    # CREATE
    resp = await client.post(
        "/api/v1/organizations/",
        json={"display_name": name, "default_approve_analytical_dataset_requests": True},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["success"] is True
    org_id = body["data"]["id"]
    assert body["data"]["display_name"] == name
    assert body["data"]["active"] is True
    assert body["data"]["default_approve_analytical_dataset_requests"] is True

    # GET single
    resp = await client.get(f"/api/v1/organizations/{org_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == org_id

    # PATCH
    resp = await client.patch(
        f"/api/v1/organizations/{org_id}",
        json={"default_approve_analytical_dataset_requests": False},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["default_approve_analytical_dataset_requests"] is False

    # DELETE (soft)
    resp = await client.delete(f"/api/v1/organizations/{org_id}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert "deactivated" in resp.json()["message"].lower()

    # Verify active=False
    resp = await client.get(f"/api/v1/organizations/{org_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["active"] is False

    # Verify audit rows written
    rows = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'organization' "
        "AND resource_id = :rid ORDER BY id",
        {"rid": str(org_id)},
    )
    actions = [r["action"] for r in rows]
    assert "CREATE_ORG" in actions
    assert "UPDATE_ORG" in actions

    _cleanup_org(name)


@pytest.mark.asyncio
async def test_create_duplicate_returns_409(client):
    name = "Duplicate Org"
    _cleanup_org(name)
    resp = await client.post("/api/v1/organizations/", json={"display_name": name})
    assert resp.status_code == 201
    resp = await client.post("/api/v1/organizations/", json={"display_name": name})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"
    _cleanup_org(name)


@pytest.mark.asyncio
async def test_get_missing_returns_404(client):
    resp = await client.get("/api/v1/organizations/999999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_patch_missing_returns_404(client):
    resp = await client.patch("/api/v1/organizations/999999", json={"display_name": "nope"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_empty_body_returns_400(client):
    resp = await client.post("/api/v1/organizations/", json={"display_name": "Empty Patch Org"})
    assert resp.status_code == 201
    org_id = resp.json()["data"]["id"]
    resp = await client.patch(f"/api/v1/organizations/{org_id}", json={})
    assert resp.status_code == 400
    _cleanup_org("Empty Patch Org")


@pytest.mark.asyncio
async def test_non_admin_post_returns_403(client, monkeypatch):
    _make_non_admin("nonadmin_post@test.com")
    _switch_user(monkeypatch, "nonadmin_post@test.com")
    resp = await client.post("/api/v1/organizations/", json={"display_name": "Blocked Org"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_patch_returns_403(client, monkeypatch):
    # Create org as admin first
    resp = await client.post("/api/v1/organizations/", json={"display_name": "Patch Block Org"})
    assert resp.status_code == 201
    org_id = resp.json()["data"]["id"]

    _make_non_admin("nonadmin_patch@test.com")
    _switch_user(monkeypatch, "nonadmin_patch@test.com")
    resp = await client.patch(f"/api/v1/organizations/{org_id}", json={"display_name": "Hijacked"})
    assert resp.status_code == 403
    _cleanup_org("Patch Block Org")


@pytest.mark.asyncio
async def test_non_admin_delete_returns_403(client, monkeypatch):
    resp = await client.post("/api/v1/organizations/", json={"display_name": "Delete Block Org"})
    assert resp.status_code == 201
    org_id = resp.json()["data"]["id"]

    _make_non_admin("nonadmin_del@test.com")
    _switch_user(monkeypatch, "nonadmin_del@test.com")
    resp = await client.delete(f"/api/v1/organizations/{org_id}")
    assert resp.status_code == 403
    _cleanup_org("Delete Block Org")


@pytest.mark.asyncio
async def test_non_admin_list_returns_403(client, monkeypatch):
    _make_non_admin("nonadmin_list@test.com")
    _switch_user(monkeypatch, "nonadmin_list@test.com")
    resp = await client.get("/api/v1/organizations/")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_org_member_can_get_own_org(client, monkeypatch):
    # seed org
    resp = await client.post("/api/v1/organizations/", json={"display_name": "MemberOrg"})
    assert resp.status_code == 201
    org_id = resp.json()["data"]["id"]

    _make_org_member("member@test.com", org_id)
    _switch_user(monkeypatch, "member@test.com")
    resp = await client.get(f"/api/v1/organizations/{org_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == org_id
    _cleanup_org("MemberOrg")


@pytest.mark.asyncio
async def test_non_member_get_other_org_returns_403(client, monkeypatch):
    # Create target org
    resp = await client.post("/api/v1/organizations/", json={"display_name": "OtherOrg"})
    assert resp.status_code == 201
    org_id = resp.json()["data"]["id"]

    # Non-admin who belongs to organization_id=1, not this new one
    _make_non_admin("outsider@test.com")
    _switch_user(monkeypatch, "outsider@test.com")
    resp = await client.get(f"/api/v1/organizations/{org_id}")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ACCESS_DENIED"
    _cleanup_org("OtherOrg")


@pytest.mark.asyncio
async def test_list_pagination_and_search(client):
    names = [f"PaginateOrg-{i}" for i in range(5)]
    for n in names:
        _cleanup_org(n)
        resp = await client.post("/api/v1/organizations/", json={"display_name": n})
        assert resp.status_code == 201

    # per_page=2, page=1 with search filter
    resp = await client.get("/api/v1/organizations/?page=1&per_page=2&search=PaginateOrg")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pagination"]["total"] == 5
    assert body["pagination"]["per_page"] == 2
    assert body["pagination"]["pages"] == 3
    assert len(body["data"]) == 2

    # page=3 should have 1 result
    resp = await client.get("/api/v1/organizations/?page=3&per_page=2&search=PaginateOrg")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1

    for n in names:
        _cleanup_org(n)


@pytest.mark.asyncio
async def test_list_without_search_includes_seed_orgs(client):
    resp = await client.get("/api/v1/organizations/?per_page=200")
    assert resp.status_code == 200
    names = [o["display_name"] for o in resp.json()["data"]]
    assert "Example Org" in names
