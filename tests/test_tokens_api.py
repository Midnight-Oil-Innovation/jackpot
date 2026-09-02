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
    execute_write(
        "DELETE FROM personal_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :e)",
        {"e": email},
    )
    execute_write("DELETE FROM users WHERE email = :e", {"e": email})


def _cleanup_tokens_by_name(name: str) -> None:
    execute_write("DELETE FROM personal_tokens WHERE name = :n", {"n": name})


@pytest.mark.asyncio
async def test_create_token_returns_value_once(client):
    name = "cli-token-once"
    _cleanup_tokens_by_name(name)
    resp = await client.post("/api/v1/tokens/", json={"name": name})
    assert resp.status_code == 201, resp.text
    body = resp.json()["data"]
    assert body["name"] == name
    assert "token" in body and isinstance(body["token"], str) and len(body["token"]) > 20
    tid = body["id"]

    # Subsequent list must not reveal token value or hash
    list_resp = await client.get("/api/v1/tokens/")
    assert list_resp.status_code == 200
    match = next(r for r in list_resp.json()["data"] if r["id"] == tid)
    assert "token" not in match
    assert "token_hash" not in match
    _cleanup_tokens_by_name(name)


@pytest.mark.asyncio
async def test_list_tokens_only_returns_own(client, monkeypatch):
    owner_email = "tokens_owner@test.com"
    other_email = "tokens_other@test.com"
    _ensure_user(owner_email)
    _ensure_user(other_email)

    _switch_user(monkeypatch, owner_email)
    r1 = await client.post("/api/v1/tokens/", json={"name": "owner-tok"})
    assert r1.status_code == 201

    _switch_user(monkeypatch, other_email)
    r2 = await client.get("/api/v1/tokens/")
    assert r2.status_code == 200
    names = [t["name"] for t in r2.json()["data"]]
    assert "owner-tok" not in names

    _cleanup_user(owner_email)
    _cleanup_user(other_email)


@pytest.mark.asyncio
async def test_revoke_own_token(client):
    name = "revokable"
    _cleanup_tokens_by_name(name)
    r1 = await client.post("/api/v1/tokens/", json={"name": name})
    tid = r1.json()["data"]["id"]

    r2 = await client.delete(f"/api/v1/tokens/{tid}")
    assert r2.status_code == 200

    # Deleted → audit log captured it
    rows = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'personal_token' "
        "AND resource_id = :rid",
        {"rid": str(tid)},
    )
    actions = [r["action"] for r in rows]
    assert "CREATE_TOKEN" in actions
    assert "REVOKE_TOKEN" in actions

    # Second revoke → 404
    r3 = await client.delete(f"/api/v1/tokens/{tid}")
    assert r3.status_code == 404


@pytest.mark.asyncio
async def test_revoke_other_users_token_forbidden(client, monkeypatch):
    owner_email = "tokens_rev_owner@test.com"
    intruder_email = "tokens_rev_intruder@test.com"
    _ensure_user(owner_email)
    _ensure_user(intruder_email)

    _switch_user(monkeypatch, owner_email)
    r1 = await client.post("/api/v1/tokens/", json={"name": "owner-guarded"})
    tid = r1.json()["data"]["id"]

    _switch_user(monkeypatch, intruder_email)
    r2 = await client.delete(f"/api/v1/tokens/{tid}")
    assert r2.status_code == 403

    _cleanup_user(owner_email)
    _cleanup_user(intruder_email)


@pytest.mark.asyncio
async def test_platform_admin_can_revoke_any_token(client, monkeypatch):
    owner_email = "tokens_admin_target@test.com"
    _ensure_user(owner_email)

    _switch_user(monkeypatch, owner_email)
    r1 = await client.post("/api/v1/tokens/", json={"name": "admin-revokable"})
    tid = r1.json()["data"]["id"]

    # Default MOCK_USER_EMAIL (admin@example.org) is Platform Admin in seed data
    monkeypatch.setenv("MOCK_USER_EMAIL", "admin@example.org")
    get_settings.cache_clear()

    r2 = await client.delete(f"/api/v1/tokens/{tid}")
    assert r2.status_code == 200

    _cleanup_user(owner_email)


@pytest.mark.asyncio
async def test_create_token_with_defaults(client):
    name = "default-lab-proj"
    _cleanup_tokens_by_name(name)
    resp = await client.post(
        "/api/v1/tokens/",
        json={"name": name, "default_lab_id": 1, "default_project_id": 1},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()["data"]
    assert body["default_lab_id"] == 1
    assert body["default_project_id"] == 1
    _cleanup_tokens_by_name(name)


@pytest.mark.asyncio
async def test_create_token_unknown_lab_returns_404(client):
    resp = await client.post(
        "/api/v1/tokens/",
        json={"name": "bad-lab", "default_lab_id": 999999},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_token_unknown_project_returns_404(client):
    resp = await client.post(
        "/api/v1/tokens/",
        json={"name": "bad-proj", "default_project_id": 999999},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revoke_unknown_token_returns_404(client):
    resp = await client.delete("/api/v1/tokens/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_projects_list_name_filter_exact_match(client):
    resp = await client.get("/api/v1/projects/?name=Dev Project")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["display_name"] == "Dev Project"


@pytest.mark.asyncio
async def test_projects_list_name_filter_case_insensitive(client):
    resp = await client.get("/api/v1/projects/?name=dev PROJECT")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["display_name"] == "Dev Project"


@pytest.mark.asyncio
async def test_projects_list_name_filter_no_match(client):
    resp = await client.get("/api/v1/projects/?name=No Such Project")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_projects_list_without_filter(client):
    resp = await client.get("/api/v1/projects/")
    assert resp.status_code == 200
    names = [p["display_name"] for p in resp.json()["data"]]
    assert "Dev Project" in names


@pytest.mark.asyncio
async def test_get_project_by_id(client):
    resp = await client.get("/api/v1/projects/1")
    assert resp.status_code == 200
    assert resp.json()["data"]["display_name"] == "Dev Project"


@pytest.mark.asyncio
async def test_get_project_not_found(client):
    resp = await client.get("/api/v1/projects/999999")
    assert resp.status_code == 404
