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
async def test_service_info_carries_no_operator_values_by_default(client, monkeypatch):
    """Critical Rule 55 — the defaults must be operator-agnostic.

    The input is pinned rather than read from the ambient environment: a
    CI job exporting SERVICE_ID would otherwise make this guard pass or
    fail for reasons unrelated to Rule 55, which is the Rule 74 shape —
    a guard that quietly stops testing what its name says.
    """
    blank = Settings(service_id="", host_organization_url="")
    monkeypatch.setattr("backend.main.get_settings", lambda: blank)

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


def test_production_refuses_to_start_without_a_configured_service_id():
    """A shared GA4GH id across deployments is a federation-visible defect.

    The endpoint's fallback keeps local and CI conformant, but a real
    deployment publishing `org.example.jackpot` would be indistinguishable
    from every other one to a peer. Production fails fast instead.
    """
    import pytest as _pytest

    base = dict(
        env="gcp",
        google_oauth_client_id="x",
        gcp_project_id="y",
    )
    with _pytest.raises(RuntimeError, match="service_id"):
        Settings(**base, service_id="").validate_for_production()

    # Configured: no raise.
    Settings(**base, service_id="org.acme-health.jackpot").validate_for_production()
