# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""FED-B router tests against the real Postgres testcontainer.

Path convention: this file lives at ``tests/test_federation_router_api.py``
(not ``tests/federation/test_router.py``) so it picks up the root
``tests/conftest.py`` testcontainer fixtures. ``tests/federation/conftest.py``
intentionally no-ops those fixtures for the pure-HTTP FED-A package tests;
router-level integration tests need the real DB, so they sit alongside the
other ``tests/test_*_api.py`` router suites.

Covers:
  * GET  /api/v1/federation/instances        — admin only
  * POST /api/v1/federation/instances        — admin only, conflict path
  * POST /api/v1/federation/search           — authenticated user; fans out
                                                via FederationClient (respx-mocked)
  * POST /api/v1/federation/push             — X-JACKPOT-Federation-Key auth
  * POST /api/v1/federation/access-requests  — X-JACKPOT-Federation-Key auth
"""

from __future__ import annotations

import httpx
import pytest
import respx

from backend.config import get_settings
from backend.credentials import _reset_backend, _set_backend
from backend.credentials.test_helpers import InMemoryBackend
from backend.database import execute_query, execute_write
from backend.responses import success_list


def _partner_envelope(*rows):
    """Response envelope a real JACKPOT peer emits for GET /samples/.

    Built via ``success_list`` — the helper the samples router itself
    uses — so partner mocks track the real contract. These previously
    hand-wrote a ``results`` key that no endpoint emits, which is why
    the federation client's mismatched key passed the suite.
    """
    import json as _json

    return _json.loads(success_list(data=list(rows), page=1, per_page=50, total=len(rows)).body)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    return row[0]["id"]


def _cleanup_user(email: str) -> None:
    execute_write(
        "UPDATE audit_log SET actor_id = NULL WHERE actor_id IN "
        "(SELECT id FROM users WHERE email = :e)",
        {"e": email},
    )
    execute_write("DELETE FROM users WHERE email = :e", {"e": email})


def _cleanup_instances() -> None:
    # No FK from audit_log to federated_instances; audit rows persist
    # across tests within the testcontainer session, matching the
    # convention used by tests/test_domain_whitelist_api.py.
    execute_write("DELETE FROM federated_instances")


def _register_instance(
    *,
    name: str,
    base_url: str,
    api_key_secret_name: str,
    role: str = "peer",
    federation_enabled: bool = True,
    min_sharing_level: str = "DISCOVERABLE",
) -> dict:
    rows = execute_write(
        """
        INSERT INTO federated_instances
            (name, base_url, role, federation_enabled,
             min_sharing_level_for_federation, api_key_secret_name)
        VALUES
            (:name, :base_url, CAST(:role AS federation_role),
             :enabled, :slv, :secret_name)
        RETURNING *
        """,
        {
            "name": name,
            "base_url": base_url,
            "role": role,
            "enabled": federation_enabled,
            "slv": min_sharing_level,
            "secret_name": api_key_secret_name,
        },
    )
    return rows[0]


@pytest.fixture
def fed_credentials():
    """Swap an InMemoryBackend for the credentials facade for the duration of the test."""
    backend = InMemoryBackend()
    _set_backend(backend)
    yield backend
    _reset_backend()


@pytest.fixture(autouse=True)
def _isolate_instances():
    """Clean the federated_instances table before and after each test."""
    _cleanup_instances()
    yield
    _cleanup_instances()


# ---------------------------------------------------------------------------
# GET /instances
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_instances_admin_returns_envelope(client):
    resp = await client.get("/api/v1/federation/instances")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"] == []
    assert body["pagination"]["total"] == 0


@pytest.mark.asyncio
async def test_list_instances_returns_existing_rows(client):
    _register_instance(
        name="arizona-dhs",
        base_url="https://az.example.test/",
        api_key_secret_name="fed/az/key",
    )
    resp = await client.get("/api/v1/federation/instances")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    names = [r["name"] for r in body["data"]]
    assert names == ["arizona-dhs"]
    row = body["data"][0]
    assert row["role"] == "peer"
    assert row["federation_enabled"] is True
    assert row["api_key_secret_name"] == "fed/az/key"
    # Server-side fields are stringified for JSON.
    assert isinstance(row["id"], str)
    assert "created_at" in row


@pytest.mark.asyncio
async def test_list_instances_non_admin_forbidden(client, monkeypatch):
    try:
        _ensure_user("reader@example.org", is_platform_admin=False)
        _switch_user(monkeypatch, "reader@example.org")
        resp = await client.get("/api/v1/federation/instances")
        assert resp.status_code == 403, resp.text
    finally:
        _switch_user(monkeypatch, "admin@example.org")
        _cleanup_user("reader@example.org")


# ---------------------------------------------------------------------------
# POST /instances
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_instance_admin_creates_row(client):
    payload = {
        "name": "new-mexico-dhs",
        "base_url": "https://nm.example.test/",
        "role": "peer",
        "federation_enabled": True,
        "min_sharing_level_for_federation": "DISCOVERABLE",
        "api_key_secret_name": "fed/nm/key",
    }
    resp = await client.post("/api/v1/federation/instances", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["name"] == "new-mexico-dhs"
    assert body["data"]["role"] == "peer"
    # Round-trip: row is in DB.
    rows = execute_query(
        "SELECT * FROM federated_instances WHERE name = :n",
        {"n": "new-mexico-dhs"},
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_register_instance_rejects_plaintext_http_peer(client):
    """The federation API key travels as a request header to base_url
    on every fan-out, so a plaintext peer puts the key on the wire in
    the clear. Registration must refuse it."""
    payload = {
        "name": "plaintext-peer",
        "base_url": "http://insecure.example.test/",
        "role": "peer",
        "api_key_secret_name": "fed/insecure/key",
    }
    resp = await client.post("/api/v1/federation/instances", json=payload)
    assert resp.status_code == 422, resp.text
    # And nothing was written.
    rows = execute_query(
        "SELECT * FROM federated_instances WHERE name = :n",
        {"n": "plaintext-peer"},
    )
    assert rows == []


@pytest.mark.asyncio
async def test_register_instance_allows_loopback_over_http(client):
    """Two JACKPOT instances on one developer machine talk over
    http://localhost. Loopback traffic never reaches a network, so the
    key cannot be intercepted and the https rule does not apply."""
    payload = {
        "name": "local-peer",
        "base_url": "http://localhost:8001/",
        "role": "peer",
        "api_key_secret_name": "fed/local/key",
    }
    resp = await client.post("/api/v1/federation/instances", json=payload)
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_register_instance_rejects_plaintext_hub_url(client):
    """hub_instance_url is the L2 push target and carries the same key."""
    payload = {
        "name": "spoke-peer",
        "base_url": "https://spoke.example.test/",
        "role": "spoke",
        "hub_instance_url": "http://hub.example.test/",
        "api_key_secret_name": "fed/spoke/key",
    }
    resp = await client.post("/api/v1/federation/instances", json=payload)
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_register_instance_duplicate_name_conflict(client):
    _register_instance(
        name="dup",
        base_url="https://dup.example.test/",
        api_key_secret_name="fed/dup/key",
    )
    payload = {
        "name": "dup",
        "base_url": "https://dup2.example.test/",
        "role": "peer",
        "api_key_secret_name": "fed/dup/key2",
    }
    resp = await client.post("/api/v1/federation/instances", json=payload)
    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_register_instance_non_admin_forbidden(client, monkeypatch):
    try:
        _ensure_user("reader@example.org", is_platform_admin=False)
        _switch_user(monkeypatch, "reader@example.org")
        resp = await client.post(
            "/api/v1/federation/instances",
            json={
                "name": "forbidden",
                "base_url": "https://x.example.test/",
                "role": "peer",
                "api_key_secret_name": "fed/x/key",
            },
        )
        assert resp.status_code == 403, resp.text
    finally:
        _switch_user(monkeypatch, "admin@example.org")
        _cleanup_user("reader@example.org")


# ---------------------------------------------------------------------------
# POST /search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_search_fans_out_to_enabled_partners(client, fed_credentials):
    fed_credentials.set("fed/az/key", "az-key")
    fed_credentials.set("fed/nm/key", "nm-key")
    _register_instance(
        name="az",
        base_url="https://az.example.test/",
        api_key_secret_name="fed/az/key",
    )
    _register_instance(
        name="nm",
        base_url="https://nm.example.test/",
        api_key_secret_name="fed/nm/key",
    )

    sample_row = {
        "sample_id": "AZ-1",
        "organism": "SARS-CoV-2",
        "date_collected": "2026-01-15",
        "country": "US",
        "state": "AZ",
        "source_type": "clinical",
        "sector": "clinical",
        "quality_tier": "ANALYZABLE",
        "surveillance_relevant": True,
    }
    nm_sample = dict(sample_row, sample_id="NM-1", state="NM")
    az_route = respx.get("https://az.example.test/api/v1/samples/").mock(
        return_value=httpx.Response(200, json=_partner_envelope(sample_row))
    )
    nm_route = respx.get("https://nm.example.test/api/v1/samples/").mock(
        return_value=httpx.Response(200, json=_partner_envelope(nm_sample))
    )

    resp = await client.post(
        "/api/v1/federation/search",
        json={"query": {"organism": "SARS-CoV-2"}},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    sample_ids = sorted(r["sample_id"] for r in body["data"])
    assert sample_ids == ["AZ-1", "NM-1"]

    # Confirm the federation-key header was attached on each outbound call.
    assert az_route.called
    assert nm_route.called
    az_req = az_route.calls.last.request
    nm_req = nm_route.calls.last.request
    assert az_req.headers["X-JACKPOT-Federation-Key"] == "az-key"
    assert nm_req.headers["X-JACKPOT-Federation-Key"] == "nm-key"


@pytest.mark.asyncio
@respx.mock
async def test_search_skips_disabled_partners(client, fed_credentials):
    fed_credentials.set("fed/on/key", "on-key")
    fed_credentials.set("fed/off/key", "off-key")
    _register_instance(
        name="on",
        base_url="https://on.example.test/",
        api_key_secret_name="fed/on/key",
        federation_enabled=True,
    )
    _register_instance(
        name="off",
        base_url="https://off.example.test/",
        api_key_secret_name="fed/off/key",
        federation_enabled=False,
    )
    on_route = respx.get("https://on.example.test/api/v1/samples/").mock(
        return_value=httpx.Response(200, json=_partner_envelope())
    )
    off_route = respx.get("https://off.example.test/api/v1/samples/").mock(
        return_value=httpx.Response(200, json=_partner_envelope())
    )

    resp = await client.post("/api/v1/federation/search", json={"query": {}})
    assert resp.status_code == 200, resp.text
    assert on_route.called
    assert not off_route.called


@pytest.mark.asyncio
@respx.mock
async def test_search_skips_plaintext_partner_seeded_in_db(client, fed_credentials):
    """Registration rejects plaintext peers, but rows can be seeded straight
    into `federated_instances` by a migration, a restore, or psql — none of
    which pass through InstanceCreate. The fan-out attaches the federation
    key as a header, so a plaintext peer must be skipped at dial time, and
    skipped alone: the valid peers in the same fan-out still answer."""
    fed_credentials.set("fed/secure/key", "secure-key")
    fed_credentials.set("fed/plain/key", "plain-key")
    _register_instance(
        name="secure",
        base_url="https://secure.example.test/",
        api_key_secret_name="fed/secure/key",
    )
    _register_instance(
        name="plaintext",
        base_url="http://plain.example.test/",
        api_key_secret_name="fed/plain/key",
    )
    secure_route = respx.get("https://secure.example.test/api/v1/samples/").mock(
        return_value=httpx.Response(200, json=_partner_envelope())
    )
    plain_route = respx.get("http://plain.example.test/api/v1/samples/").mock(
        return_value=httpx.Response(200, json=_partner_envelope())
    )

    resp = await client.post("/api/v1/federation/search", json={"query": {}})
    assert resp.status_code == 200, resp.text
    assert secure_route.called
    assert not plain_route.called


@pytest.mark.asyncio
@respx.mock
async def test_search_dials_loopback_partner_over_http(client, fed_credentials):
    """The loopback carve-out survives at the dial site too — a two-instance
    developer federation on one machine must still fan out."""
    fed_credentials.set("fed/local/key", "local-key")
    _register_instance(
        name="local",
        base_url="http://localhost:8001/",
        api_key_secret_name="fed/local/key",
    )
    local_route = respx.get("http://localhost:8001/api/v1/samples/").mock(
        return_value=httpx.Response(200, json=_partner_envelope())
    )

    resp = await client.post("/api/v1/federation/search", json={"query": {}})
    assert resp.status_code == 200, resp.text
    assert local_route.called


@pytest.mark.asyncio
async def test_search_with_no_partners_returns_empty(client, fed_credentials):
    resp = await client.post("/api/v1/federation/search", json={"query": {}})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == []


# ---------------------------------------------------------------------------
# POST /push
# ---------------------------------------------------------------------------


_PUSH_PAYLOAD = {
    "sample_id": "EXT-001",
    "organism": "Mycobacterium tuberculosis",
    "date_collected": "2026-02-01",
    "country": "US",
    "state": "AZ",
    "source_type": "clinical",
    "sector": "clinical",
    "quality_tier": "ANALYZABLE",
    "surveillance_relevant": True,
    "fasta_url": "https://example.test/presigned/EXT-001.fasta",
    "typing_results": {"mlst": "ST-12"},
    "amr_profile": {"rifampicin": "R"},
    "lineage": "L4",
    "clade": "4.9",
    "host_age_range": "30-39",
    "originating_lab": "AZ-Lab",
    "submitting_lab": "AZ-Lab",
    "data_generator": "AZ-Sequencing",
    "pushed_at": "2026-02-02T03:00:00+00:00",
}


@pytest.mark.asyncio
async def test_push_valid_federation_key_returns_202(client, fed_credentials):
    fed_credentials.set("fed/peer/key", "peer-secret")
    peer = _register_instance(
        name="peer",
        base_url="https://peer.example.test/",
        api_key_secret_name="fed/peer/key",
    )
    resp = await client.post(
        "/api/v1/federation/push",
        json=_PUSH_PAYLOAD,
        headers={"X-JACKPOT-Federation-Key": "peer-secret"},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["sample_id"] == "EXT-001"
    assert body["data"]["source_instance_id"] == str(peer["id"])
    assert body["data"]["received"] is True


@pytest.mark.asyncio
async def test_push_missing_federation_key_returns_401(client, fed_credentials):
    fed_credentials.set("fed/peer/key", "peer-secret")
    _register_instance(
        name="peer",
        base_url="https://peer.example.test/",
        api_key_secret_name="fed/peer/key",
    )
    resp = await client.post("/api/v1/federation/push", json=_PUSH_PAYLOAD)
    assert resp.status_code == 401, resp.text
    body = resp.json()
    assert body["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_push_invalid_federation_key_returns_401(client, fed_credentials):
    fed_credentials.set("fed/peer/key", "peer-secret")
    _register_instance(
        name="peer",
        base_url="https://peer.example.test/",
        api_key_secret_name="fed/peer/key",
    )
    resp = await client.post(
        "/api/v1/federation/push",
        json=_PUSH_PAYLOAD,
        headers={"X-JACKPOT-Federation-Key": "wrong-key"},
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_push_disabled_instance_cannot_authenticate(client, fed_credentials):
    """Disabled partners are excluded from the auth lookup — their key
    cannot be presented even if the secret backend still resolves."""
    fed_credentials.set("fed/peer/key", "peer-secret")
    _register_instance(
        name="peer",
        base_url="https://peer.example.test/",
        api_key_secret_name="fed/peer/key",
        federation_enabled=False,
    )
    resp = await client.post(
        "/api/v1/federation/push",
        json=_PUSH_PAYLOAD,
        headers={"X-JACKPOT-Federation-Key": "peer-secret"},
    )
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# POST /access-requests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_access_request_valid_key_and_origin_returns_202(client, fed_credentials):
    fed_credentials.set("fed/peer/key", "peer-secret")
    peer = _register_instance(
        name="peer",
        base_url="https://peer.example.test/",
        api_key_secret_name="fed/peer/key",
    )
    payload = {
        "request_id": "11111111-1111-1111-1111-111111111111",
        "requesting_instance_id": str(peer["id"]),
        "requesting_user_email": "researcher@peer.example.test",
        "target_sample_id": "OUR-SAMPLE-1",
        "target_instance_id": "22222222-2222-2222-2222-222222222222",
        "purpose": "Outbreak investigation, IRB-2026-04",
        "duo_codes": ["DUO:0000004"],
    }
    resp = await client.post(
        "/api/v1/federation/access-requests",
        json=payload,
        headers={"X-JACKPOT-Federation-Key": "peer-secret"},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["request_id"] == "11111111-1111-1111-1111-111111111111"
    assert body["data"]["status"] == "RECEIVED"
    assert body["data"]["source_instance_id"] == str(peer["id"])


@pytest.mark.asyncio
async def test_access_request_mismatched_origin_forbidden(client, fed_credentials):
    fed_credentials.set("fed/peer/key", "peer-secret")
    _register_instance(
        name="peer",
        base_url="https://peer.example.test/",
        api_key_secret_name="fed/peer/key",
    )
    payload = {
        "request_id": "11111111-1111-1111-1111-111111111111",
        # Wrong instance id — does not match the authenticated peer.
        "requesting_instance_id": "33333333-3333-3333-3333-333333333333",
        "requesting_user_email": "spoofer@example.test",
        "target_sample_id": "OUR-SAMPLE-1",
        "target_instance_id": "22222222-2222-2222-2222-222222222222",
        "purpose": "spoof",
        "duo_codes": [],
    }
    resp = await client.post(
        "/api/v1/federation/access-requests",
        json=payload,
        headers={"X-JACKPOT-Federation-Key": "peer-secret"},
    )
    assert resp.status_code == 403, resp.text
    body = resp.json()
    assert body["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_access_request_missing_key_returns_401(client, fed_credentials):
    payload = {
        "request_id": "11111111-1111-1111-1111-111111111111",
        "requesting_instance_id": "44444444-4444-4444-4444-444444444444",
        "requesting_user_email": "researcher@peer.example.test",
        "target_sample_id": "OUR-SAMPLE-1",
        "target_instance_id": "22222222-2222-2222-2222-222222222222",
        "purpose": "x",
        "duo_codes": [],
    }
    resp = await client.post("/api/v1/federation/access-requests", json=payload)
    assert resp.status_code == 401, resp.text
