import pytest

from backend.config import get_settings
from backend.database import execute_query, execute_write


def _switch_user(monkeypatch, email: str) -> None:
    monkeypatch.setenv("MOCK_USER_EMAIL", email)
    get_settings.cache_clear()


def _ensure_user(
    email: str,
    *,
    name: str = "Test User",
    is_platform_admin: bool = False,
    is_active: bool = True,
) -> int:
    execute_write(
        """
        INSERT INTO users (email, name, is_platform_admin, is_active, organization_id)
        VALUES (:e, :n, :a, :act, 1)
        ON CONFLICT (email) DO UPDATE
        SET name = :n, is_platform_admin = :a, is_active = :act, organization_id = 1
        """,
        {"e": email, "n": name, "a": is_platform_admin, "act": is_active},
    )
    row = execute_query("SELECT id FROM users WHERE email = :e", {"e": email})
    return row[0]["id"]


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


def _pg_id(name: str) -> int:
    row = execute_query(
        "SELECT id FROM permission_groups WHERE name = :n",
        {"n": name},
    )
    return row[0]["id"]


@pytest.mark.asyncio
async def test_get_me_returns_current_user(client):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["email"] == "admin@example.org"
    assert "lab_memberships" in body["data"]
    assert isinstance(body["data"]["lab_memberships"], list)


@pytest.mark.asyncio
async def test_get_me_includes_lab_memberships(client, monkeypatch):
    email = "users_me_member@test.com"
    uid = _ensure_user(email)
    execute_write(
        """
        INSERT INTO lab_membership (user_id, lab_id, permission_group_id, is_lab_director)
        VALUES (:uid, 1, :pgid, FALSE)
        ON CONFLICT DO NOTHING
        """,
        {"uid": uid, "pgid": _pg_id("Lab Reader")},
    )
    _switch_user(monkeypatch, email)
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 200
    memberships = resp.json()["data"]["lab_memberships"]
    assert any(m["lab_id"] == 1 and m["permission_group_name"] == "Lab Reader" for m in memberships)
    _cleanup_user(email)


@pytest.mark.asyncio
async def test_list_users_admin(client):
    resp = await client.get("/api/v1/users/?per_page=5")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "pagination" in body
    assert isinstance(body["data"], list)


@pytest.mark.asyncio
async def test_list_users_search(client):
    email = "users_search_target@test.com"
    _ensure_user(email, name="Unique Search Target")
    resp = await client.get("/api/v1/users/?search=Unique+Search+Target")
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()["data"]]
    assert email in emails
    _cleanup_user(email)


@pytest.mark.asyncio
async def test_list_users_non_admin_returns_403(client, monkeypatch):
    email = "users_list_nonadmin@test.com"
    _ensure_user(email)
    _switch_user(monkeypatch, email)
    resp = await client.get("/api/v1/users/")
    assert resp.status_code == 403
    _cleanup_user(email)


@pytest.mark.asyncio
async def test_get_user_self(client, monkeypatch):
    email = "users_self_get@test.com"
    uid = _ensure_user(email)
    _switch_user(monkeypatch, email)
    resp = await client.get(f"/api/v1/users/{uid}")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == uid
    _cleanup_user(email)


@pytest.mark.asyncio
async def test_get_other_user_as_non_admin_returns_403(client, monkeypatch):
    other_email = "users_other@test.com"
    other_id = _ensure_user(other_email)
    requester_email = "users_nonadmin_reader@test.com"
    _ensure_user(requester_email)
    _switch_user(monkeypatch, requester_email)
    resp = await client.get(f"/api/v1/users/{other_id}")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ACCESS_DENIED"
    _cleanup_user(requester_email)
    _cleanup_user(other_email)


@pytest.mark.asyncio
async def test_get_user_not_found(client):
    resp = await client.get("/api/v1/users/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_user_self_updates_name(client, monkeypatch):
    email = "users_self_patch@test.com"
    uid = _ensure_user(email, name="Before")
    _switch_user(monkeypatch, email)
    resp = await client.patch(f"/api/v1/users/{uid}", json={"name": "After"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["name"] == "After"

    rows = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'user' AND resource_id = :rid",
        {"rid": str(uid)},
    )
    assert any(r["action"] == "UPDATE_USER" for r in rows)
    _cleanup_user(email)


@pytest.mark.asyncio
async def test_patch_user_self_cannot_promote_self(client, monkeypatch):
    email = "users_selfpromote@test.com"
    uid = _ensure_user(email)
    _switch_user(monkeypatch, email)
    resp = await client.patch(
        f"/api/v1/users/{uid}",
        json={"is_platform_admin": True},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ACCESS_DENIED"

    # DB unchanged
    row = execute_query("SELECT is_platform_admin FROM users WHERE id = :id", {"id": uid})
    assert row[0]["is_platform_admin"] is False
    _cleanup_user(email)


@pytest.mark.asyncio
async def test_patch_user_admin_can_flip_admin_flag(client):
    email = "users_admin_flip@test.com"
    uid = _ensure_user(email)
    resp = await client.patch(
        f"/api/v1/users/{uid}",
        json={"is_platform_admin": True},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_platform_admin"] is True
    _cleanup_user(email)


@pytest.mark.asyncio
async def test_patch_user_non_admin_non_self_returns_403(client, monkeypatch):
    target_email = "users_patch_target@test.com"
    target_id = _ensure_user(target_email)
    requester_email = "users_patch_requester@test.com"
    _ensure_user(requester_email)
    _switch_user(monkeypatch, requester_email)
    resp = await client.patch(f"/api/v1/users/{target_id}", json={"name": "Hacked"})
    assert resp.status_code == 403
    _cleanup_user(requester_email)
    _cleanup_user(target_email)


@pytest.mark.asyncio
async def test_patch_user_empty_body_returns_400(client, monkeypatch):
    email = "users_empty_patch@test.com"
    uid = _ensure_user(email)
    _switch_user(monkeypatch, email)
    resp = await client.patch(f"/api/v1/users/{uid}", json={})
    assert resp.status_code == 400
    _cleanup_user(email)


@pytest.mark.asyncio
async def test_delete_user_soft_delete(client):
    email = "users_soft_delete@test.com"
    uid = _ensure_user(email)
    resp = await client.delete(f"/api/v1/users/{uid}")
    assert resp.status_code == 200
    assert resp.json()["message"] == "User deactivated."

    row = execute_query("SELECT is_active FROM users WHERE id = :id", {"id": uid})
    assert row[0]["is_active"] is False

    rows = execute_query(
        "SELECT action, metadata FROM audit_log "
        "WHERE resource_type = 'user' AND resource_id = :rid",
        {"rid": str(uid)},
    )
    assert any(r["action"] == "UPDATE_USER" for r in rows)
    _cleanup_user(email)


@pytest.mark.asyncio
async def test_delete_user_non_admin_returns_403(client, monkeypatch):
    target_email = "users_delete_target@test.com"
    target_id = _ensure_user(target_email)
    requester_email = "users_delete_requester@test.com"
    _ensure_user(requester_email)
    _switch_user(monkeypatch, requester_email)
    resp = await client.delete(f"/api/v1/users/{target_id}")
    assert resp.status_code == 403
    _cleanup_user(requester_email)
    _cleanup_user(target_email)


@pytest.mark.asyncio
async def test_delete_user_not_found(client):
    resp = await client.delete("/api/v1/users/999999")
    assert resp.status_code == 404
