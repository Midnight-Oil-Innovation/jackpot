"""I-3c: ``GET /api/v1/settings/public`` exposure endpoint."""

from __future__ import annotations

import pytest

from backend.config import get_settings


@pytest.fixture
def fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_public_settings_default_off(client, fresh_settings, monkeypatch):
    monkeypatch.delenv("ALLOW_BACKEND_SUBMISSION", raising=False)
    monkeypatch.delenv("BACKEND_SUBMISSION_REPOS", raising=False)
    get_settings.cache_clear()
    resp = await client.get("/api/v1/settings/public")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["allow_backend_submission"] is False
    assert body["backend_submission_repos"] == []


@pytest.mark.asyncio
async def test_public_settings_reports_enabled_state(
    client, fresh_settings, monkeypatch
):
    monkeypatch.setenv("ALLOW_BACKEND_SUBMISSION", "true")
    monkeypatch.setenv("BACKEND_SUBMISSION_REPOS", "ncbi,ena")
    get_settings.cache_clear()
    resp = await client.get("/api/v1/settings/public")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["allow_backend_submission"] is True
    assert sorted(body["backend_submission_repos"]) == ["ena", "ncbi"]


@pytest.mark.asyncio
async def test_public_settings_unauthenticated(client):
    """The endpoint is intentionally unauthenticated. The response must
    contain only safe-to-disclose flags — no infrastructure identifiers,
    no secrets, no operator identity."""
    resp = await client.get("/api/v1/settings/public")
    assert resp.status_code == 200
    body = resp.json()["data"]
    forbidden_keys = {
        "database_url",
        "credential_backend",
        "credential_file_path",
        "gcp_project_id",
        "host_organization_name",
        "google_oauth_client_id",
        "ncbi_api_key",
        "jackpot_api_token",
    }
    leaked = forbidden_keys & set(body.keys())
    assert not leaked, f"public settings leaked: {leaked}"
