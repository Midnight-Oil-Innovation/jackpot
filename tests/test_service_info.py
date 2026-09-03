"""GA4GH service-info endpoint (P0i).

The spec's required fields are id, name, type{group,artifact,version},
organization{name,url} and version. A consumer that cannot find one of
those treats the service as non-conformant, so each is asserted here
rather than spot-checking the envelope.
"""

import pytest

from backend.config import Settings
from backend.version import __version__

REQUIRED_TOP_LEVEL = ("id", "name", "type", "organization", "version")


@pytest.mark.asyncio
async def test_service_info_is_public_and_conformant(client):
    resp = await client.get("/service-info")
    assert resp.status_code == 200

    body = resp.json()
    # Not the success() envelope — GA4GH consumers parse the object directly.
    for field in REQUIRED_TOP_LEVEL:
        assert body.get(field), f"GA4GH required field missing or empty: {field}"

    assert {"group", "artifact", "version"} <= set(body["type"])
    assert {"name", "url"} <= set(body["organization"])


@pytest.mark.asyncio
async def test_service_info_reports_the_running_version(client):
    body = (await client.get("/service-info")).json()
    assert body["version"] == __version__


@pytest.mark.asyncio
async def test_service_info_does_not_claim_ga4gh_standard_apis(client):
    """JACKPOT serves no DRS/WES/Beacon API yet.

    Advertising one in `type.artifact` would make a discovery client route
    real requests at endpoints that do not exist. Reverse when such an API
    actually ships.
    """
    body = (await client.get("/service-info")).json()
    assert body["type"]["artifact"] not in {"drs", "wes", "trs", "beacon"}


@pytest.mark.asyncio
async def test_service_info_carries_no_operator_values_by_default(client):
    """Critical Rule 55 — defaults must be operator-agnostic."""
    body = (await client.get("/service-info")).json()
    assert "example" in body["id"]
    assert "example" in body["organization"]["url"]


@pytest.mark.asyncio
async def test_service_info_stays_conformant_when_env_vars_are_blank(client, monkeypatch):
    """An env var set to the empty string beats a pydantic default.

    `jackpot init` writes `HOST_ORGANIZATION_NAME=` unconditionally
    (cli/jackpot/init/writers.py), so blank-not-absent is the shape a
    stock install actually produces. Without a fallback at the read site
    the endpoint serves an empty required field and fails conformance.
    """
    blank = Settings(
        service_id="",
        host_organization_name="",
        host_organization_url="",
        service_contact_url="",
    )
    monkeypatch.setattr("backend.main.get_settings", lambda: blank)

    body = (await client.get("/service-info")).json()
    for field in REQUIRED_TOP_LEVEL:
        assert body.get(field), f"blank env produced empty required field: {field}"
    assert body["organization"]["name"]
    assert body["organization"]["url"]
    assert "contactUrl" not in body
