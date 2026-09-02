"""E-1 — tests for ``POST /api/v1/auth/dev-login``.

Covers the local-mode-only role-switch endpoint added to support the
end-to-end UAT. Verifies the local-mode gating, user creation, role
flag updates, lab-membership upsert, and ``settings.mock_user_email``
mutation contract.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.config import get_settings
from backend.database import execute_query, execute_write
from backend.main import app


def _cleanup_user(email: str) -> None:
    execute_write(
        "DELETE FROM lab_membership WHERE user_id IN (SELECT id FROM users WHERE email = :e)",
        {"e": email},
    )
    execute_write(
        "UPDATE audit_log SET actor_id = NULL "
        "WHERE actor_id IN (SELECT id FROM users WHERE email = :e)",
        {"e": email},
    )
    execute_write("DELETE FROM users WHERE email = :e", {"e": email})


@pytest.mark.asyncio
async def test_dev_login_local_mode_creates_user_and_returns_payload():
    email = "e1-newuser@example.org"
    _cleanup_user(email)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/dev-login",
                json={"email": email, "role": "Lab Collaborator"},
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["user"]["email"] == email
        # A lab role carries no Instance-scope preset: its authority comes
        # from the membership grants, not from anything at the instance root.
        assert body["instance_preset"] is None
        assert body["active_role"] == "Lab Collaborator"
        assert body["membership"]["permission_group"] == "Lab Collaborator"
        assert body["membership"]["is_lab_director"] is False
    finally:
        _cleanup_user(email)


@pytest.mark.asyncio
async def test_dev_login_returns_404_outside_local_mode(monkeypatch):
    monkeypatch.setenv("ENV", "gcp")
    # Force a fresh Settings load with env=gcp; the production
    # validate_for_production check would normally trip, but the
    # endpoint only inspects ``settings.env`` so the bare swap works.
    get_settings.cache_clear()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/dev-login",
                json={"email": "should-404@example.org"},
            )
        assert resp.status_code == 404
    finally:
        monkeypatch.setenv("ENV", "local")
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_dev_login_existing_user_role_update():
    email = "e1-existing@example.org"
    _cleanup_user(email)
    try:
        execute_write(
            "INSERT INTO users (email, name, organization_id, is_platform_admin) "
            "VALUES (:e, 'E1 Existing', 1, FALSE)",
            {"e": email},
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/dev-login",
                json={"email": email, "role": "Platform Admin"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["instance_preset"] == "instance_administrator"
        assert body["membership"] is None

        # The grants are the assignment. The legacy column is still written
        # so reseed() stays consistent, and M2-DROP deletes both that write
        # and this assertion.
        uid = execute_query("SELECT id FROM users WHERE email = :e", {"e": email})[0]["id"]
        held = {
            r["capability"]
            for r in execute_query(
                "SELECT capability FROM authz_capability_grants WHERE principal_id = :p",
                {"p": str(uid)},
            )
        }
        assert "user:manage" in held, held
        rows = execute_query(
            "SELECT is_platform_admin FROM users WHERE email = :e",
            {"e": email},
        )
        assert rows[0]["is_platform_admin"] is True
    finally:
        _cleanup_user(email)


@pytest.mark.asyncio
async def test_dev_login_mutates_mock_user_email():
    email = "e1-mutates@example.org"
    _cleanup_user(email)
    settings = get_settings()
    original = settings.mock_user_email
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/dev-login",
                json={"email": email, "role": "Lab Reader"},
            )
        assert resp.status_code == 200
        assert get_settings().mock_user_email == email
    finally:
        get_settings().mock_user_email = original
        _cleanup_user(email)


@pytest.mark.asyncio
async def test_dev_login_platform_admin_with_lab_id_rejected():
    email = "e1-pa-with-lab@example.org"
    _cleanup_user(email)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/dev-login",
                json={
                    "email": email,
                    "role": "Platform Admin",
                    "lab_id": 1,
                },
            )
        assert resp.status_code == 400
        assert "cannot be assigned to a lab" in resp.text
    finally:
        _cleanup_user(email)


@pytest.mark.asyncio
async def test_dev_login_unknown_role_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/api/v1/auth/dev-login",
            json={"email": "e1-unknown@example.org", "role": "Sandwich Artist"},
        )
    assert resp.status_code == 400
    assert "role must be one of" in resp.text


@pytest.mark.asyncio
async def test_dev_login_invalid_email_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/api/v1/auth/dev-login",
            json={"email": "not-an-email"},
        )
    assert resp.status_code == 400
    assert "valid email" in resp.text


@pytest.mark.asyncio
async def test_dev_login_lab_director_membership_upserted():
    email = "e1-director@example.org"
    _cleanup_user(email)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r1 = await c.post(
                "/api/v1/auth/dev-login",
                json={"email": email, "role": "Lab Collaborator"},
            )
            assert r1.status_code == 200
            assert r1.json()["membership"]["is_lab_director"] is False
            r2 = await c.post(
                "/api/v1/auth/dev-login",
                json={"email": email, "role": "Lab Director"},
            )
            assert r2.status_code == 200
            assert r2.json()["membership"]["is_lab_director"] is True

        rows = execute_query(
            "SELECT lm.is_lab_director, pg.name "
            "FROM lab_membership lm "
            "JOIN permission_groups pg ON pg.id = lm.permission_group_id "
            "JOIN users u ON u.id = lm.user_id "
            "WHERE u.email = :e",
            {"e": email},
        )
        assert len(rows) == 1
        assert rows[0]["is_lab_director"] is True
        assert rows[0]["name"] == "Lab Director"
    finally:
        _cleanup_user(email)
