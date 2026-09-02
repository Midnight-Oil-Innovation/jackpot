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
    # The role is the grants now: this no longer writes the column and asks
    # reseed() to translate it, ahead of M2-DROP removing it. Issued either
    # way so a re-used email is demoted rather than keeping a stale grant.
    grant_instance_preset(uid, ADMIN_PRESET if is_platform_admin else None)
    return uid


def _cleanup_user(email: str) -> None:
    execute_write(
        "UPDATE audit_log SET actor_id = NULL WHERE actor_id IN "
        "(SELECT id FROM users WHERE email = :e)",
        {"e": email},
    )
    execute_write("DELETE FROM users WHERE email = :e", {"e": email})


def _cleanup_domain(domain: str) -> None:
    execute_write(
        "DELETE FROM domain_whitelist WHERE domain = :d",
        {"d": domain.lower()},
    )


@pytest.mark.asyncio
async def test_list_domains_admin(client):
    resp = await client.get("/api/v1/domain-whitelist/")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    domains = [d["domain"] for d in body["data"]]
    assert "example.org" in domains


@pytest.mark.asyncio
async def test_list_domains_non_admin_returns_403(client, monkeypatch):
    email = "whitelist_nonadmin_list@test.com"
    _ensure_user(email)
    _switch_user(monkeypatch, email)
    resp = await client.get("/api/v1/domain-whitelist/")
    assert resp.status_code == 403
    _cleanup_user(email)


@pytest.mark.asyncio
async def test_add_domain_success(client):
    _cleanup_domain("example.org")
    resp = await client.post(
        "/api/v1/domain-whitelist/",
        json={"domain": "example.org", "description": "Test entry"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["data"]["domain"] == "example.org"
    assert body["data"]["description"] == "Test entry"

    new_id = body["data"]["id"]
    rows = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'domain_whitelist' "
        "AND resource_id = :rid",
        {"rid": str(new_id)},
    )
    assert any(r["action"] == "ADD_WHITELIST_DOMAIN" for r in rows)
    _cleanup_domain("example.org")


@pytest.mark.asyncio
async def test_add_domain_normalises_to_lowercase(client):
    _cleanup_domain("UPPER.example")
    resp = await client.post(
        "/api/v1/domain-whitelist/",
        json={"domain": "UPPER.example"},
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["domain"] == "upper.example"
    _cleanup_domain("upper.example")


@pytest.mark.asyncio
async def test_add_domain_duplicate_returns_409(client):
    _cleanup_domain("dup.example")
    r1 = await client.post("/api/v1/domain-whitelist/", json={"domain": "dup.example"})
    assert r1.status_code == 201

    r2 = await client.post("/api/v1/domain-whitelist/", json={"domain": "dup.example"})
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "CONFLICT"

    # Case-insensitive duplicate also rejected
    r3 = await client.post("/api/v1/domain-whitelist/", json={"domain": "DUP.example"})
    assert r3.status_code == 409

    _cleanup_domain("dup.example")


@pytest.mark.asyncio
async def test_add_domain_non_admin_returns_403(client, monkeypatch):
    email = "whitelist_nonadmin_add@test.com"
    _ensure_user(email)
    _switch_user(monkeypatch, email)
    resp = await client.post(
        "/api/v1/domain-whitelist/",
        json={"domain": "blocked.example"},
    )
    assert resp.status_code == 403
    _cleanup_user(email)


@pytest.mark.asyncio
async def test_delete_domain_success(client):
    _cleanup_domain("deletable.example")
    r1 = await client.post("/api/v1/domain-whitelist/", json={"domain": "deletable.example"})
    assert r1.status_code == 201
    new_id = r1.json()["data"]["id"]

    r2 = await client.delete(f"/api/v1/domain-whitelist/{new_id}")
    assert r2.status_code == 200
    assert "removed" in r2.json()["message"]

    # Gone from DB
    row = execute_query(
        "SELECT id FROM domain_whitelist WHERE id = :id",
        {"id": new_id},
    )
    assert row == []

    rows = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'domain_whitelist' "
        "AND resource_id = :rid",
        {"rid": str(new_id)},
    )
    assert any(r["action"] == "REMOVE_WHITELIST_DOMAIN" for r in rows)


@pytest.mark.asyncio
async def test_delete_domain_not_found(client):
    resp = await client.delete("/api/v1/domain-whitelist/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_domain_non_admin_returns_403(client, monkeypatch):
    _cleanup_domain("victim.example")
    r1 = await client.post("/api/v1/domain-whitelist/", json={"domain": "victim.example"})
    new_id = r1.json()["data"]["id"]

    email = "whitelist_nonadmin_del@test.com"
    _ensure_user(email)
    _switch_user(monkeypatch, email)
    resp = await client.delete(f"/api/v1/domain-whitelist/{new_id}")
    assert resp.status_code == 403
    _cleanup_user(email)
    _cleanup_domain("victim.example")
