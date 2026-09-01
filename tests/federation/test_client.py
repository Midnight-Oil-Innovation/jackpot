# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""FederationClient (Level 1) tests using respx-mocked partner endpoints.

Covers:
  - Happy-path fanout against multiple respx-mocked partners with merged
    + source-attributed results
  - Partner timeout, partner 4xx, partner 5xx — failing partner gets skipped,
    other partners still return data
  - `X-JACKPOT-Federation-Key` header carries the API key from the
    api_key_resolver callable
  - Result aggregation across multiple partners
  - `detect_anomalous_traffic` is consulted per partner with the query
  - `federation_enabled=False` partners are silently skipped
  - `attest_partner=False` partners are skipped
  - Empty eligible set short-circuits without HTTP calls
  - `secure_aggregate` wraps the merged result list before return
  - Construction without an http_client and without async-context-entry raises
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import respx

from backend.federation._ais_hooks import (
    AISFederationHooks,
    NullAISFederationHooks,
)
from backend.federation.client import FederationClient
from backend.federation.models import (
    FederatedInstance,
    FederationQuery,
    FederationRole,
)
from backend.responses import success_list

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_instance(
    name: str,
    base_url: str,
    *,
    federation_enabled: bool = True,
    role: FederationRole = FederationRole.PEER,
) -> FederatedInstance:
    return FederatedInstance(
        id=uuid4(),
        name=name,
        base_url=base_url,
        role=role,
        federation_enabled=federation_enabled,
        min_sharing_level_for_federation="DISCOVERABLE",
        hub_instance_url=None,
        api_key_secret_name=f"fed/{name}/key",
        last_seen_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _sample_row(sample_id: str) -> dict[str, Any]:
    return {
        "sample_id": sample_id,
        "organism": "SARS-CoV-2",
        "date_collected": date(2026, 1, 15).isoformat(),
        "country": "US",
        "state": "AZ",
        "source_type": "clinical",
        "sector": "clinical",
        "quality_tier": "ANALYZABLE",
        "surveillance_relevant": True,
    }


def _envelope(*rows: dict[str, Any]) -> dict[str, Any]:
    """Wrap rows in the response envelope a real JACKPOT peer emits.

    Built by calling ``success_list`` — the same helper the samples
    router uses — so these mocks track the real contract instead of
    restating it. Hand-written payloads here previously used a
    ``results`` key that no endpoint emits, which let the client's
    matching bug pass the suite unnoticed.
    """
    return json.loads(success_list(data=list(rows), page=1, per_page=50, total=len(rows)).body)


class RecordingHooks(NullAISFederationHooks):
    """No-op hooks that record what they were called with."""

    def __init__(self) -> None:
        self.attest_calls: list[FederatedInstance] = []
        self.anomaly_calls: list[tuple[FederationQuery, FederatedInstance]] = []
        self.secure_aggregate_calls: list[tuple[list[Any], list[FederatedInstance]]] = []

    def attest_partner(self, instance: FederatedInstance) -> bool:
        self.attest_calls.append(instance)
        return True

    def detect_anomalous_traffic(self, query: FederationQuery, partner: FederatedInstance) -> bool:
        self.anomaly_calls.append((query, partner))
        return False

    def secure_aggregate(self, results, partner_set):
        self.secure_aggregate_calls.append((list(results), list(partner_set)))
        return results


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@respx.mock
async def test_client_happy_path_fanout_two_partners() -> None:
    az = _make_instance("az", "https://az.example.test/")
    nm = _make_instance("nm", "https://nm.example.test/")
    api_keys = {az.id: "az-key", nm.id: "nm-key"}

    respx.post("https://az.example.test/api/v1/federation/query").mock(
        return_value=httpx.Response(200, json=_envelope(_sample_row("AZ-1"), _sample_row("AZ-2")))
    )
    respx.post("https://nm.example.test/api/v1/federation/query").mock(
        return_value=httpx.Response(200, json=_envelope(_sample_row("NM-1")))
    )

    hooks = RecordingHooks()
    async with FederationClient(hooks=hooks) as fc:
        results = await fc.query(
            FederationQuery(organism="SARS-CoV-2"),
            partners=[az, nm],
            api_key_resolver=lambda p: api_keys[p.id],
        )

    sample_ids = {r.sample_id for r in results}
    assert sample_ids == {"AZ-1", "AZ-2", "NM-1"}

    # Source attribution is set by the client, not by the partner.
    by_id = {r.sample_id: r for r in results}
    assert by_id["AZ-1"].source_instance_id == az.id
    assert by_id["AZ-1"].source_instance_name == "az"
    assert by_id["NM-1"].source_instance_id == nm.id

    # Hooks were consulted once per eligible partner.
    assert len(hooks.attest_calls) == 2
    assert len(hooks.anomaly_calls) == 2
    assert [partner for _, partner in hooks.anomaly_calls] == [az, nm]
    # secure_aggregate runs once with the merged list.
    assert len(hooks.secure_aggregate_calls) == 1
    aggregated, partner_set = hooks.secure_aggregate_calls[0]
    assert len(aggregated) == 3
    assert partner_set == [az, nm]


@respx.mock
async def test_client_parses_the_real_jackpot_response_envelope() -> None:
    """Partners are JACKPOT instances, so the wire format is whatever
    ``backend.responses.success_list`` emits — that is the contract,
    not a shape chosen here.

    The mock payload is therefore built by calling that helper rather
    than hand-writing a dict. A hand-written payload can agree with a
    wrong implementation forever; one derived from the real helper
    cannot.
    """
    envelope = json.loads(
        success_list(data=[_sample_row("AZ-1")], page=1, per_page=50, total=1).body
    )
    az = _make_instance("az", "https://az.example.test/")
    respx.post("https://az.example.test/api/v1/federation/query").mock(
        return_value=httpx.Response(200, json=envelope)
    )

    async with FederationClient() as fc:
        results = await fc.query(
            FederationQuery(organism="SARS-CoV-2"),
            partners=[az],
            api_key_resolver=lambda p: "az-key",
        )

    assert [r.sample_id for r in results] == ["AZ-1"]


@respx.mock
async def test_client_sends_federation_key_header() -> None:
    az = _make_instance("az", "https://az.example.test/")
    route = respx.post("https://az.example.test/api/v1/federation/query").mock(
        return_value=httpx.Response(200, json=_envelope())
    )

    async with FederationClient() as fc:
        await fc.query(
            FederationQuery(),
            partners=[az],
            api_key_resolver=lambda p: "secret-key-xyz",
        )

    assert route.called
    req = route.calls.last.request
    assert req.headers["X-JACKPOT-Federation-Key"] == "secret-key-xyz"
    assert req.headers["X-JACKPOT-Federation-Origin"] == str(az.id)


@respx.mock
async def test_client_forces_analyzable_floor_at_wire() -> None:
    """Even if caller passes a lower quality_tier_min, the wire request must
    set ANALYZABLE. (FederationQuery defaults to ANALYZABLE, but the client
    re-applies a setdefault as a belt-and-suspenders guarantee.)"""
    az = _make_instance("az", "https://az.example.test/")
    route = respx.post("https://az.example.test/api/v1/federation/query").mock(
        return_value=httpx.Response(200, json=_envelope())
    )

    async with FederationClient() as fc:
        await fc.query(
            FederationQuery(),
            partners=[az],
            api_key_resolver=lambda p: "k",
        )

    assert route.called
    # The wire-level floor now travels in the POST body rather than the query
    # string: the inbound route takes a FederationQuery, not GET filters.
    body = json.loads(route.calls.last.request.content)
    assert body["quality_tier_min"] == "ANALYZABLE"


# ---------------------------------------------------------------------------
# Failure isolation
# ---------------------------------------------------------------------------


@respx.mock
async def test_client_isolates_partner_5xx_failure() -> None:
    good = _make_instance("good", "https://good.example.test/")
    bad = _make_instance("bad", "https://bad.example.test/")

    respx.post("https://good.example.test/api/v1/federation/query").mock(
        return_value=httpx.Response(200, json=_envelope(_sample_row("G-1")))
    )
    respx.post("https://bad.example.test/api/v1/federation/query").mock(
        return_value=httpx.Response(503, json={"detail": "down"})
    )

    async with FederationClient() as fc:
        results = await fc.query(
            FederationQuery(),
            partners=[good, bad],
            api_key_resolver=lambda p: "k",
        )

    assert [r.sample_id for r in results] == ["G-1"]


@respx.mock
async def test_client_isolates_partner_4xx_failure() -> None:
    good = _make_instance("good", "https://good.example.test/")
    forbidden = _make_instance("forb", "https://forbidden.example.test/")

    respx.post("https://good.example.test/api/v1/federation/query").mock(
        return_value=httpx.Response(200, json=_envelope(_sample_row("G-1")))
    )
    respx.post("https://forbidden.example.test/api/v1/federation/query").mock(
        return_value=httpx.Response(403, json={"detail": "key invalid"})
    )

    async with FederationClient() as fc:
        results = await fc.query(
            FederationQuery(),
            partners=[good, forbidden],
            api_key_resolver=lambda p: "k",
        )

    assert [r.sample_id for r in results] == ["G-1"]


@respx.mock
async def test_client_isolates_partner_timeout() -> None:
    good = _make_instance("good", "https://good.example.test/")
    slow = _make_instance("slow", "https://slow.example.test/")

    respx.post("https://good.example.test/api/v1/federation/query").mock(
        return_value=httpx.Response(200, json=_envelope(_sample_row("G-1")))
    )
    respx.post("https://slow.example.test/api/v1/federation/query").mock(
        side_effect=httpx.ReadTimeout("partner timed out")
    )

    async with FederationClient(timeout=0.1) as fc:
        results = await fc.query(
            FederationQuery(),
            partners=[good, slow],
            api_key_resolver=lambda p: "k",
        )

    assert [r.sample_id for r in results] == ["G-1"]


# ---------------------------------------------------------------------------
# Gating: federation_enabled, attest_partner, detect_anomalous_traffic
# ---------------------------------------------------------------------------


@respx.mock
async def test_client_skips_disabled_partners() -> None:
    enabled = _make_instance("on", "https://on.example.test/")
    disabled = _make_instance("off", "https://off.example.test/", federation_enabled=False)

    enabled_route = respx.post("https://on.example.test/api/v1/federation/query").mock(
        return_value=httpx.Response(200, json=_envelope(_sample_row("ON-1")))
    )
    disabled_route = respx.post("https://off.example.test/api/v1/federation/query").mock(
        return_value=httpx.Response(200, json=_envelope(_sample_row("OFF-1")))
    )

    async with FederationClient() as fc:
        results = await fc.query(
            FederationQuery(),
            partners=[enabled, disabled],
            api_key_resolver=lambda p: "k",
        )

    assert [r.sample_id for r in results] == ["ON-1"]
    assert enabled_route.called
    assert not disabled_route.called


class RejectingAttestHooks(NullAISFederationHooks):
    def __init__(self, reject_names: set[str]) -> None:
        self._reject = reject_names

    def attest_partner(self, instance: FederatedInstance) -> bool:
        return instance.name not in self._reject


@respx.mock
async def test_client_skips_partners_failing_attestation() -> None:
    a = _make_instance("a", "https://a.example.test/")
    b = _make_instance("b", "https://b.example.test/")

    a_route = respx.post("https://a.example.test/api/v1/federation/query").mock(
        return_value=httpx.Response(200, json=_envelope(_sample_row("A-1")))
    )
    b_route = respx.post("https://b.example.test/api/v1/federation/query").mock(
        return_value=httpx.Response(200, json=_envelope(_sample_row("B-1")))
    )

    async with FederationClient(hooks=RejectingAttestHooks({"b"})) as fc:
        results = await fc.query(
            FederationQuery(),
            partners=[a, b],
            api_key_resolver=lambda p: "k",
        )

    assert [r.sample_id for r in results] == ["A-1"]
    assert a_route.called
    assert not b_route.called


class FlagAnomalyHooks(NullAISFederationHooks):
    def __init__(self, flag_names: set[str]) -> None:
        self._flag = flag_names

    def detect_anomalous_traffic(self, query: FederationQuery, partner: FederatedInstance) -> bool:
        return partner.name in self._flag


@respx.mock
async def test_client_skips_partners_flagged_anomalous() -> None:
    a = _make_instance("a", "https://a.example.test/")
    b = _make_instance("b", "https://b.example.test/")

    a_route = respx.post("https://a.example.test/api/v1/federation/query").mock(
        return_value=httpx.Response(200, json=_envelope(_sample_row("A-1")))
    )
    b_route = respx.post("https://b.example.test/api/v1/federation/query").mock(
        return_value=httpx.Response(200, json=_envelope(_sample_row("B-1")))
    )

    async with FederationClient(hooks=FlagAnomalyHooks({"a"})) as fc:
        results = await fc.query(
            FederationQuery(),
            partners=[a, b],
            api_key_resolver=lambda p: "k",
        )

    assert [r.sample_id for r in results] == ["B-1"]
    assert not a_route.called
    assert b_route.called


async def test_client_empty_eligible_set_short_circuits() -> None:
    """When every partner is filtered out, the client returns [] without
    making any HTTP call (so respx doesn't need to be active)."""
    disabled = _make_instance("off", "https://off.example.test/", federation_enabled=False)
    async with FederationClient() as fc:
        results = await fc.query(
            FederationQuery(),
            partners=[disabled],
            api_key_resolver=lambda p: "k",
        )
    assert results == []


# ---------------------------------------------------------------------------
# Construction guard
# ---------------------------------------------------------------------------


async def test_client_query_without_context_raises() -> None:
    """Direct instantiation without entering the async context manager — and
    without an injected http_client — must raise rather than crash deeper."""
    fc = FederationClient()
    with pytest.raises(RuntimeError, match="async context manager"):
        await fc.query(
            FederationQuery(),
            partners=[_make_instance("x", "https://x.example.test/")],
            api_key_resolver=lambda p: "k",
        )


async def test_client_accepts_injected_http_client() -> None:
    """Passing an http_client at construction skips the auto-create path and
    leaves cleanup to the caller. This exercises the
    ``self._owns_http_client = False`` branch."""
    injected = httpx.AsyncClient()
    fc = FederationClient(http_client=injected)
    # No context entry; query should still work because http is preset.
    with respx.mock:
        x = _make_instance("x", "https://x.example.test/")
        respx.post("https://x.example.test/api/v1/federation/query").mock(
            return_value=httpx.Response(200, json=_envelope())
        )
        await fc.query(
            FederationQuery(),
            partners=[x],
            api_key_resolver=lambda p: "k",
        )
    # __aexit__ on injected client should NOT close it.
    async with fc:
        pass
    assert not injected.is_closed
    await injected.aclose()


# ---------------------------------------------------------------------------
# Protocol shape
# ---------------------------------------------------------------------------


def test_null_hooks_satisfies_protocol() -> None:
    assert isinstance(NullAISFederationHooks(), AISFederationHooks)


# Smoke import of types referenced above to keep type-checker happy in
# environments that don't otherwise touch them.
_ = (UUID,)
