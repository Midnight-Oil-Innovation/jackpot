# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""FederationAccessGateway (Level 3) tests.

Covers:
  - `build_outbound_request` produces a PENDING `FederationAccessRequest`
    with correct attribution
  - `submit_outbound` consults `attest_partner` — failure withholds the
    request; success raises `NotImplementedError` (current Track 1 STUB)
  - `receive_inbound` consults `attest_partner` and `threshold_approve` in
    order — either failure rejects the inbound; both passing raises
    `NotImplementedError` (current Track 1 STUB)
  - Request lifecycle states PENDING / APPROVED / DENIED transitions are
    reflected in the model

When the L3 IO lands (Year 2 late), the NotImplementedError-pinning tests
fail and get replaced with respx-mocked happy-path + retry coverage.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import respx

from backend.federation._ais_hooks import NullAISFederationHooks
from backend.federation.access import FederationAccessGateway
from backend.federation.models import (
    FederatedInstance,
    FederationAccessRequest,
    FederationRole,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _instance(name: str, url: str) -> FederatedInstance:
    return FederatedInstance(
        id=uuid4(),
        name=name,
        base_url=url,
        role=FederationRole.PEER,
        federation_enabled=True,
        min_sharing_level_for_federation="DISCOVERABLE",
        hub_instance_url=None,
        api_key_secret_name=f"fed/{name}/key",
        last_seen_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


class RejectingAttestHooks(NullAISFederationHooks):
    def __init__(self) -> None:
        self.threshold_called = False

    def attest_partner(self, instance: FederatedInstance) -> bool:
        return False

    def threshold_approve(self, action, affected_partners) -> bool:
        self.threshold_called = True
        return True


class RejectingThresholdHooks(NullAISFederationHooks):
    def __init__(self) -> None:
        self.attest_called = False

    def attest_partner(self, instance: FederatedInstance) -> bool:
        self.attest_called = True
        return True

    def threshold_approve(self, action, affected_partners) -> bool:
        return False


class RecordingApprovalHooks(NullAISFederationHooks):
    def __init__(self) -> None:
        self.attest_calls: list[FederatedInstance] = []
        self.threshold_calls: list[tuple] = []

    def attest_partner(self, instance: FederatedInstance) -> bool:
        self.attest_calls.append(instance)
        return True

    def threshold_approve(self, action, affected_partners) -> bool:
        self.threshold_calls.append((action, affected_partners))
        return True


# ---------------------------------------------------------------------------
# build_outbound_request
# ---------------------------------------------------------------------------


def test_build_outbound_request_happy_path() -> None:
    target = _instance("az", "https://az.example.test/")
    requester_id = uuid4()
    gw = FederationAccessGateway()
    req = gw.build_outbound_request(
        target_sample_id="AZ-001",
        target_instance=target,
        requesting_instance_id=requester_id,
        requesting_user_email="alice@orgb.example.test",
        purpose="Outbreak investigation 2026-Q1",
        duo_codes=["DUO:0000004"],
    )
    assert isinstance(req, FederationAccessRequest)
    assert req.status == "PENDING"
    assert req.target_sample_id == "AZ-001"
    assert req.target_instance_id == target.id
    assert req.requesting_instance_id == requester_id
    assert req.requesting_user_email == "alice@orgb.example.test"
    assert req.duo_codes == ["DUO:0000004"]
    assert req.requested_at.tzinfo is not None


def test_build_outbound_request_defaults_duo_codes_to_empty() -> None:
    target = _instance("az", "https://az.example.test/")
    gw = FederationAccessGateway()
    req = gw.build_outbound_request(
        target_sample_id="AZ-001",
        target_instance=target,
        requesting_instance_id=uuid4(),
        requesting_user_email="bob@orgb.example.test",
        purpose="surveillance",
    )
    assert req.duo_codes == []


def test_request_lifecycle_states_round_trip() -> None:
    """The model captures the full PENDING/APPROVED/DENIED lifecycle. The
    state machine itself is owned by the existing internal sample_access
    workflow — the model is the carrier across the wire."""
    now = datetime.now(UTC)
    base = {
        "request_id": uuid4(),
        "requesting_instance_id": uuid4(),
        "requesting_user_email": "alice@orgb.example.test",
        "target_sample_id": "AZ-001",
        "target_instance_id": uuid4(),
        "purpose": "trial",
        "duo_codes": [],
        "requested_at": now,
    }
    pending = FederationAccessRequest(**base, status="PENDING")
    approved = FederationAccessRequest(**base, status="APPROVED", approved_at=now, expires_at=now)
    denied = FederationAccessRequest(**base, status="DENIED", denied_at=now)
    assert pending.status == "PENDING"
    assert pending.approved_at is None and pending.denied_at is None
    assert approved.status == "APPROVED" and approved.approved_at == now
    assert approved.expires_at == now
    assert denied.status == "DENIED" and denied.denied_at == now


# ---------------------------------------------------------------------------
# submit_outbound — STUB pinning + attest gate
# ---------------------------------------------------------------------------


@respx.mock
async def test_submit_outbound_withholds_when_attest_rejects() -> None:
    target = _instance("az", "https://az.example.test/")
    gw = FederationAccessGateway(hooks=RejectingAttestHooks())
    req = gw.build_outbound_request(
        target_sample_id="AZ-001",
        target_instance=target,
        requesting_instance_id=uuid4(),
        requesting_user_email="alice@orgb.example.test",
        purpose="surveillance",
    )
    # Mock route should not be hit when attest rejects.
    route = respx.post("https://az.example.test/api/v1/federation/access-requests").mock(
        return_value=respx.MockResponse(status_code=200, json={"status": "PENDING"})
    )

    result = await gw.submit_outbound(req, target)
    assert result is None
    assert not route.called


@respx.mock
async def test_submit_outbound_raises_not_implemented_when_attest_passes() -> None:
    """Pins the current Track 1 STUB boundary."""
    target = _instance("az", "https://az.example.test/")
    hooks = RecordingApprovalHooks()
    gw = FederationAccessGateway(hooks=hooks)
    req = gw.build_outbound_request(
        target_sample_id="AZ-001",
        target_instance=target,
        requesting_instance_id=uuid4(),
        requesting_user_email="alice@orgb.example.test",
        purpose="surveillance",
    )
    respx.post("https://az.example.test/api/v1/federation/access-requests").mock(
        return_value=respx.MockResponse(status_code=200, json={"status": "PENDING"})
    )

    with pytest.raises(NotImplementedError, match="Level 3 IO not yet"):
        await gw.submit_outbound(req, target)
    assert hooks.attest_calls == [target]


# ---------------------------------------------------------------------------
# receive_inbound — both hooks + STUB pinning
# ---------------------------------------------------------------------------


def _inbound_request(source_id) -> FederationAccessRequest:
    return FederationAccessRequest(
        request_id=uuid4(),
        requesting_instance_id=source_id,
        requesting_user_email="researcher@source.example.test",
        target_sample_id="LOCAL-1",
        target_instance_id=uuid4(),
        purpose="cross-org outbreak investigation",
        duo_codes=["DUO:0000007"],
        requested_at=datetime.now(UTC),
        status="PENDING",
    )


async def test_receive_inbound_rejects_when_attest_fails() -> None:
    source = _instance("partner", "https://partner.example.test/")
    hooks = RejectingAttestHooks()
    gw = FederationAccessGateway(hooks=hooks)
    req = _inbound_request(source.id)

    result = await gw.receive_inbound(req, source)
    assert result is None
    # threshold_approve must NOT be called when attest rejects.
    assert hooks.threshold_called is False


async def test_receive_inbound_rejects_when_threshold_fails() -> None:
    source = _instance("partner", "https://partner.example.test/")
    hooks = RejectingThresholdHooks()
    gw = FederationAccessGateway(hooks=hooks)
    req = _inbound_request(source.id)

    result = await gw.receive_inbound(req, source)
    assert result is None
    assert hooks.attest_called is True


async def test_receive_inbound_raises_not_implemented_when_both_hooks_pass() -> None:
    """Pins the Track 1 STUB boundary and the GRANT_FEDERATION_ACCESS
    action label used by the threshold hook."""
    source = _instance("partner", "https://partner.example.test/")
    hooks = RecordingApprovalHooks()
    gw = FederationAccessGateway(hooks=hooks)
    req = _inbound_request(source.id)

    with pytest.raises(NotImplementedError, match="Level 3 IO not yet"):
        await gw.receive_inbound(req, source)

    assert hooks.attest_calls == [source]
    assert len(hooks.threshold_calls) == 1
    action, partners = hooks.threshold_calls[0]
    assert action == "GRANT_FEDERATION_ACCESS"
    assert partners == [source]


# ---------------------------------------------------------------------------
# Default-hooks construction
# ---------------------------------------------------------------------------


async def test_access_gateway_default_hooks_are_null_impl() -> None:
    """With no hooks injected, both Null defaults allow through to the stub."""
    target = _instance("az", "https://az.example.test/")
    gw = FederationAccessGateway()
    req = gw.build_outbound_request(
        target_sample_id="AZ-001",
        target_instance=target,
        requesting_instance_id=uuid4(),
        requesting_user_email="alice@orgb.example.test",
        purpose="surveillance",
    )
    with pytest.raises(NotImplementedError):
        await gw.submit_outbound(req, target)
