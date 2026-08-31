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


def _ensure_lab(display_name: str) -> int:
    existing = execute_query(
        "SELECT id FROM labs WHERE display_name = :n LIMIT 1",
        {"n": display_name},
    )
    if existing:
        return existing[0]["id"]
    rows = execute_write(
        """
        INSERT INTO labs (organization_id, display_name, description, active)
        VALUES (1, :n, '', TRUE) RETURNING id
        """,
        {"n": display_name},
    )
    return rows[0]["id"]


def _add_lab_membership(user_id: int, lab_id: int, pg_name: str, *, director: bool = False) -> None:
    execute_write(
        """
        INSERT INTO lab_membership
            (user_id, lab_id, permission_group_id, is_lab_director)
        VALUES (:uid, :lid, :pg, :d)
        ON CONFLICT DO NOTHING
        """,
        {"uid": user_id, "lid": lab_id, "pg": _pg_id(pg_name), "d": director},
    )
    # A membership is only access once grants exist for it (M2-B1).
    sync_grants_from_legacy_roles()


def _cleanup_project_by_name(name: str) -> None:
    execute_write(
        "DELETE FROM project_membership WHERE project_id IN "
        "(SELECT id FROM projects WHERE display_name = :n)",
        {"n": name},
    )
    execute_write("DELETE FROM projects WHERE display_name = :n", {"n": name})


def _cleanup_lab_by_name(name: str) -> None:
    execute_write(
        "DELETE FROM project_membership WHERE project_id IN "
        "(SELECT id FROM projects WHERE lab_id IN "
        "(SELECT id FROM labs WHERE display_name = :n))",
        {"n": name},
    )
    execute_write(
        "DELETE FROM projects WHERE lab_id IN (SELECT id FROM labs WHERE display_name = :n)",
        {"n": name},
    )
    execute_write(
        "DELETE FROM lab_membership WHERE lab_id IN (SELECT id FROM labs WHERE display_name = :n)",
        {"n": name},
    )
    execute_write("DELETE FROM labs WHERE display_name = :n", {"n": name})


def _cleanup_user(email: str) -> None:
    execute_write(
        "DELETE FROM lab_membership WHERE user_id IN (SELECT id FROM users WHERE email = :e)",
        {"e": email},
    )
    execute_write(
        "DELETE FROM project_membership WHERE user_id IN (SELECT id FROM users WHERE email = :e)",
        {"e": email},
    )
    execute_write(
        "UPDATE projects SET created_by_id = NULL WHERE created_by_id IN "
        "(SELECT id FROM users WHERE email = :e)",
        {"e": email},
    )
    execute_write(
        "UPDATE audit_log SET actor_id = NULL WHERE actor_id IN "
        "(SELECT id FROM users WHERE email = :e)",
        {"e": email},
    )
    execute_write("DELETE FROM users WHERE email = :e", {"e": email})


@pytest.mark.asyncio
async def test_create_project_as_admin(client):
    name = "Project-Admin-Create"
    _cleanup_project_by_name(name)
    resp = await client.post(
        "/api/v1/projects/",
        json={"lab_id": 1, "display_name": name, "description": "x"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["data"]["display_name"] == name
    assert body["data"]["active"] is True
    assert body["data"]["status"] == "ACTIVE"
    pid = body["data"]["id"]

    audits = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'project' AND resource_id = :rid",
        {"rid": str(pid)},
    )
    assert any(a["action"] == "CREATE_PROJECT" for a in audits)
    _cleanup_project_by_name(name)


@pytest.mark.asyncio
async def test_create_project_as_director(client, monkeypatch):
    lab_name = "Project-Dir-Lab"
    project_name = "Project-Dir-Create"
    _cleanup_lab_by_name(lab_name)
    _cleanup_project_by_name(project_name)
    lab_id = _ensure_lab(lab_name)

    email = "project_director@test.com"
    uid = _ensure_user(email)
    _add_lab_membership(uid, lab_id, "Lab Director", director=True)

    _switch_user(monkeypatch, email)
    resp = await client.post(
        "/api/v1/projects/",
        json={"lab_id": lab_id, "display_name": project_name},
    )
    assert resp.status_code == 201, resp.text

    _cleanup_user(email)
    _cleanup_lab_by_name(lab_name)


@pytest.mark.asyncio
async def test_create_project_as_reader_returns_403(client, monkeypatch):
    lab_name = "Project-Reader-Lab"
    _cleanup_lab_by_name(lab_name)
    lab_id = _ensure_lab(lab_name)

    email = "project_reader@test.com"
    uid = _ensure_user(email)
    _add_lab_membership(uid, lab_id, "Lab Reader")

    _switch_user(monkeypatch, email)
    resp = await client.post(
        "/api/v1/projects/",
        json={"lab_id": lab_id, "display_name": "Should-Fail"},
    )
    assert resp.status_code == 403

    _cleanup_user(email)
    _cleanup_lab_by_name(lab_name)


@pytest.mark.asyncio
async def test_create_project_invalid_lab_returns_403(client, monkeypatch):
    email = "project_outsider@test.com"
    _ensure_user(email)
    _switch_user(monkeypatch, email)
    resp = await client.post(
        "/api/v1/projects/",
        json={"lab_id": 999999, "display_name": "Ghost Project"},
    )
    # Non-admin without director role on unknown lab → 403 from require_lab_director
    assert resp.status_code == 403
    _cleanup_user(email)


@pytest.mark.asyncio
async def test_create_project_admin_unknown_lab_returns_404(client):
    resp = await client.post(
        "/api/v1/projects/",
        json={"lab_id": 999999, "display_name": "Ghost"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_projects_admin_sees_all(client):
    name_a = "ListProj-A"
    name_b = "ListProj-B"
    _cleanup_project_by_name(name_a)
    _cleanup_project_by_name(name_b)
    await client.post("/api/v1/projects/", json={"lab_id": 1, "display_name": name_a})
    await client.post("/api/v1/projects/", json={"lab_id": 1, "display_name": name_b})

    resp = await client.get("/api/v1/projects/?per_page=200")
    assert resp.status_code == 200
    names = {p["display_name"] for p in resp.json()["data"]}
    assert {name_a, name_b}.issubset(names)

    _cleanup_project_by_name(name_a)
    _cleanup_project_by_name(name_b)


@pytest.mark.asyncio
async def test_list_projects_non_admin_filters_to_their_labs(client, monkeypatch):
    lab_mine = "Proj-Mine-Lab"
    lab_theirs = "Proj-Theirs-Lab"
    _cleanup_lab_by_name(lab_mine)
    _cleanup_lab_by_name(lab_theirs)
    mine_id = _ensure_lab(lab_mine)
    theirs_id = _ensure_lab(lab_theirs)

    name_mine = "Proj-Visible"
    name_theirs = "Proj-Hidden"
    _cleanup_project_by_name(name_mine)
    _cleanup_project_by_name(name_theirs)
    execute_write(
        "INSERT INTO projects (lab_id, display_name) VALUES (:l, :n)",
        {"l": mine_id, "n": name_mine},
    )
    execute_write(
        "INSERT INTO projects (lab_id, display_name) VALUES (:l, :n)",
        {"l": theirs_id, "n": name_theirs},
    )

    email = "proj_list_user@test.com"
    uid = _ensure_user(email)
    _add_lab_membership(uid, mine_id, "Lab Collaborator")

    _switch_user(monkeypatch, email)
    resp = await client.get("/api/v1/projects/?per_page=200")
    assert resp.status_code == 200
    names = {p["display_name"] for p in resp.json()["data"]}
    assert name_mine in names
    assert name_theirs not in names

    _cleanup_user(email)
    _cleanup_lab_by_name(lab_mine)
    _cleanup_lab_by_name(lab_theirs)


@pytest.mark.asyncio
async def test_list_projects_filter_by_lab(client):
    name = "Proj-Lab-Filter"
    _cleanup_project_by_name(name)
    await client.post("/api/v1/projects/", json={"lab_id": 1, "display_name": name})
    resp = await client.get("/api/v1/projects/?lab_id=1&per_page=200")
    assert resp.status_code == 200
    for p in resp.json()["data"]:
        assert p["lab_id"] == 1
    _cleanup_project_by_name(name)


@pytest.mark.asyncio
async def test_get_project_as_admin(client):
    name = "Proj-Admin-Get"
    _cleanup_project_by_name(name)
    create = await client.post(
        "/api/v1/projects/",
        json={"lab_id": 1, "display_name": name},
    )
    pid = create.json()["data"]["id"]
    resp = await client.get(f"/api/v1/projects/{pid}")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == pid
    _cleanup_project_by_name(name)


@pytest.mark.asyncio
async def test_get_project_non_member_returns_403(client, monkeypatch):
    lab_name = "Proj-Private-Lab"
    _cleanup_lab_by_name(lab_name)
    lab_id = _ensure_lab(lab_name)
    name = "Proj-Private"
    _cleanup_project_by_name(name)
    rows = execute_write(
        "INSERT INTO projects (lab_id, display_name) VALUES (:l, :n) RETURNING id",
        {"l": lab_id, "n": name},
    )
    pid = rows[0]["id"]

    email = "proj_get_outsider@test.com"
    _ensure_user(email)
    _switch_user(monkeypatch, email)
    resp = await client.get(f"/api/v1/projects/{pid}")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ACCESS_DENIED"

    _cleanup_user(email)
    _cleanup_lab_by_name(lab_name)


@pytest.mark.asyncio
async def test_get_project_not_found_returns_404(client):
    resp = await client.get("/api/v1/projects/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_project_as_admin(client):
    name = "Proj-Patch"
    _cleanup_project_by_name(name)
    create = await client.post(
        "/api/v1/projects/",
        json={"lab_id": 1, "display_name": name},
    )
    pid = create.json()["data"]["id"]

    resp = await client.patch(
        f"/api/v1/projects/{pid}",
        json={"description": "Updated"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["description"] == "Updated"

    # audit entry
    audits = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'project' AND resource_id = :rid",
        {"rid": str(pid)},
    )
    assert any(a["action"] == "UPDATE_PROJECT" for a in audits)

    _cleanup_project_by_name(name)


@pytest.mark.asyncio
async def test_patch_project_empty_body_returns_400(client):
    name = "Proj-Patch-Empty"
    _cleanup_project_by_name(name)
    create = await client.post(
        "/api/v1/projects/",
        json={"lab_id": 1, "display_name": name},
    )
    pid = create.json()["data"]["id"]
    resp = await client.patch(f"/api/v1/projects/{pid}", json={})
    assert resp.status_code == 400
    _cleanup_project_by_name(name)


@pytest.mark.asyncio
async def test_patch_project_as_reader_returns_403(client, monkeypatch):
    lab_name = "Proj-Reader-Lab"
    _cleanup_lab_by_name(lab_name)
    lab_id = _ensure_lab(lab_name)
    name = "Proj-Reader-Patch"
    _cleanup_project_by_name(name)
    rows = execute_write(
        "INSERT INTO projects (lab_id, display_name) VALUES (:l, :n) RETURNING id",
        {"l": lab_id, "n": name},
    )
    pid = rows[0]["id"]

    email = "proj_patch_reader@test.com"
    uid = _ensure_user(email)
    _add_lab_membership(uid, lab_id, "Lab Reader")

    _switch_user(monkeypatch, email)
    resp = await client.patch(
        f"/api/v1/projects/{pid}",
        json={"description": "Hack"},
    )
    assert resp.status_code == 403

    _cleanup_user(email)
    _cleanup_lab_by_name(lab_name)


@pytest.mark.asyncio
async def test_patch_project_not_found_returns_404(client):
    resp = await client.patch(
        "/api/v1/projects/999999",
        json={"description": "x"},
    )
    assert resp.status_code == 404
