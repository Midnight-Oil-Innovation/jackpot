# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""FederationPushJob (Level 2) tests.

Covers:
  - The three qualification gates from jackpot_architecture.md §22 Level 2:
    surveillance_relevant, sharing_level >= min_sharing_level_for_federation,
    quality_status >= ANALYZABLE
  - `build_payload` composes the de-identified push payload from a sample row
    and a presigned FASTA URL
  - `push_to_hub` consults `validate_push_payload` and `threshold_approve`
    before attempting any IO; if either returns False it withholds the
    payload (no NotImplementedError, no HTTP call)
  - Current push IO is a documented STUB (Year 2 early); when both AIS hooks
    pass, `push_to_hub` raises `NotImplementedError`. This test pins that
    boundary so the day the L2 IO lands, the stub test fails and the new
    behavior gets new tests.

Note: `push_to_hub` does not yet issue an HTTP call (FED-A is interface-only
for L2 IO). The respx safety net below confirms no HTTP traffic is generated
by the current implementation when the gates pass — when the L2 IO lands,
the respx mock will need a happy-path return and a retry-on-5xx scenario
in this file.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
import respx

from backend.federation._ais_hooks import NullAISFederationHooks
from backend.federation.models import (
    FederatedInstance,
    FederationPushPayload,
    FederationRole,
)
from backend.federation.push import FederationPushJob

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hub() -> FederatedInstance:
    return FederatedInstance(
        id=uuid4(),
        name="National Hub",
        base_url="https://hub.example.test/",
        role=FederationRole.HUB,
        federation_enabled=True,
        min_sharing_level_for_federation="LAB",
        hub_instance_url=None,
        api_key_secret_name="fed/hub/key",
        last_seen_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _sample_row() -> dict:
    return {
        "sample_id": "AZ-001",
        "organism": "SARS-CoV-2",
        "date_collected": date(2026, 1, 15),
        "country": "US",
        "state": "AZ",
        "source_type": "clinical",
        "sector": "clinical",
        "quality_status": "ANALYZABLE",
        "surveillance_relevant": True,
        "typing_results": {"mlst": "ST-1"},
        "amr_profile": {"blaKPC": "present"},
        "lineage": "BA.2.86",
        "clade": "23I",
        "host_age_range": "30-39",
        "originating_lab": "Arizona DHS Lab",
        "submitting_lab": "Arizona DHS Lab",
        "data_generator": "Arizona DHS Lab",
    }


# ---------------------------------------------------------------------------
# Qualification gates
# ---------------------------------------------------------------------------


def test_qualifying_sample_all_gates_pass() -> None:
    assert FederationPushJob.is_qualifying_sample(
        surveillance_relevant=True,
        sharing_level="DISCOVERABLE",
        quality_status="ANALYZABLE",
        min_sharing_level_for_federation="LAB",
    )


def test_qualifying_sample_rejects_non_surveillance() -> None:
    assert not FederationPushJob.is_qualifying_sample(
        surveillance_relevant=False,
        sharing_level="PUBLIC",
        quality_status="SUBMITTABLE",
        min_sharing_level_for_federation="LAB",
    )


@pytest.mark.parametrize(
    "sharing_level,minimum,expected",
    [
        ("PRIVATE", "LAB", False),
        ("LAB", "LAB", True),
        ("DISCOVERABLE", "LAB", True),
        ("REGISTERED_ACCESS", "DISCOVERABLE", True),
        ("PUBLIC", "REGISTERED_ACCESS", True),
        ("LAB", "DISCOVERABLE", False),
        ("DISCOVERABLE", "PUBLIC", False),
    ],
)
def test_qualifying_sample_sharing_level_ordering(
    sharing_level: str, minimum: str, expected: bool
) -> None:
    assert (
        FederationPushJob.is_qualifying_sample(
            surveillance_relevant=True,
            sharing_level=sharing_level,
            quality_status="ANALYZABLE",
            min_sharing_level_for_federation=minimum,
        )
        is expected
    )


@pytest.mark.parametrize(
    "quality_status,expected",
    [
        ("PRELIMINARY", False),
        ("ANALYZABLE", True),
        ("SUBMITTABLE", True),
    ],
)
def test_qualifying_sample_quality_floor_is_analyzable(quality_status: str, expected: bool) -> None:
    assert (
        FederationPushJob.is_qualifying_sample(
            surveillance_relevant=True,
            sharing_level="DISCOVERABLE",
            quality_status=quality_status,
            min_sharing_level_for_federation="LAB",
        )
        is expected
    )


def test_qualifying_sample_unknown_sharing_level_rejected() -> None:
    """An unknown sharing_level string should not silently qualify."""
    assert not FederationPushJob.is_qualifying_sample(
        surveillance_relevant=True,
        sharing_level="MYSTERY",
        quality_status="ANALYZABLE",
        min_sharing_level_for_federation="LAB",
    )


def test_qualifying_sample_unknown_quality_status_rejected() -> None:
    assert not FederationPushJob.is_qualifying_sample(
        surveillance_relevant=True,
        sharing_level="DISCOVERABLE",
        quality_status="UNRATED",
        min_sharing_level_for_federation="LAB",
    )


# ---------------------------------------------------------------------------
# build_payload
# ---------------------------------------------------------------------------


def test_build_payload_happy_path() -> None:
    job = FederationPushJob()
    payload = job.build_payload(
        sample=_sample_row(),
        fasta_presigned_url="https://signed.example.test/fasta/AZ-001.fasta?token=abc",
    )
    assert isinstance(payload, FederationPushPayload)
    assert payload.sample_id == "AZ-001"
    assert payload.quality_tier == "ANALYZABLE"
    assert payload.lineage == "BA.2.86"
    assert payload.host_age_range == "30-39"
    assert payload.typing_results == {"mlst": "ST-1"}
    assert str(payload.fasta_url).startswith("https://signed.example.test/")
    # pushed_at stamped at build time, must be UTC-aware.
    assert payload.pushed_at.tzinfo is not None


def test_build_payload_minimal_optional_fields() -> None:
    row = _sample_row()
    # Drop every optional field. submitting_lab, data_generator, lineage,
    # clade, host_age_range, sector, country, state, typing_results,
    # amr_profile — all default to None / {}.
    for k in [
        "submitting_lab",
        "data_generator",
        "lineage",
        "clade",
        "host_age_range",
        "sector",
        "country",
        "state",
        "typing_results",
        "amr_profile",
    ]:
        row.pop(k)
    job = FederationPushJob()
    payload = job.build_payload(
        sample=row,
        fasta_presigned_url="https://signed.example.test/fasta/AZ-001.fasta",
    )
    assert payload.lineage is None
    assert payload.typing_results == {}
    assert payload.amr_profile == {}
    assert payload.sector is None


# ---------------------------------------------------------------------------
# push_to_hub — AIS hook gates
# ---------------------------------------------------------------------------


class RejectingValidateHooks(NullAISFederationHooks):
    def __init__(self) -> None:
        self.threshold_called = False

    def validate_push_payload(self, payload, target) -> bool:
        return False

    def threshold_approve(self, action, affected_partners) -> bool:
        self.threshold_called = True
        return True


class RejectingThresholdHooks(NullAISFederationHooks):
    def __init__(self) -> None:
        self.validate_called = False

    def validate_push_payload(self, payload, target) -> bool:
        self.validate_called = True
        return True

    def threshold_approve(self, action, affected_partners) -> bool:
        return False


class RecordingApprovalHooks(NullAISFederationHooks):
    def __init__(self) -> None:
        self.validate_calls: list[tuple] = []
        self.threshold_calls: list[tuple] = []

    def validate_push_payload(self, payload, target) -> bool:
        self.validate_calls.append((payload, target))
        return True

    def threshold_approve(self, action, affected_partners) -> bool:
        self.threshold_calls.append((action, affected_partners))
        return True


@respx.mock
async def test_push_to_hub_withholds_when_validate_rejects() -> None:
    """validate_push_payload=False → silent withhold, no NotImplementedError,
    no HTTP call. (When L2 IO lands, this should also assert no respx call.)"""
    hooks = RejectingValidateHooks()
    job = FederationPushJob(hooks=hooks)
    payload = job.build_payload(
        sample=_sample_row(),
        fasta_presigned_url="https://signed.example.test/fasta/AZ-001.fasta",
    )
    # Mounting a route here would fail loudly if push_to_hub started issuing
    # HTTP calls; today the stub never does.
    respx.post("https://hub.example.test/api/v1/federation/push").mock(
        return_value=respx.MockResponse(status_code=500)
    )

    # No exception expected; just an early return after the hook.
    result = await job.push_to_hub(payload, _hub())
    assert result is None
    # When validate_push_payload returns False, threshold_approve must NOT
    # be consulted — the gate ordering is documented.
    assert hooks.threshold_called is False


@respx.mock
async def test_push_to_hub_withholds_when_threshold_rejects() -> None:
    hooks = RejectingThresholdHooks()
    job = FederationPushJob(hooks=hooks)
    payload = job.build_payload(
        sample=_sample_row(),
        fasta_presigned_url="https://signed.example.test/fasta/AZ-001.fasta",
    )
    respx.post("https://hub.example.test/api/v1/federation/push").mock(
        return_value=respx.MockResponse(status_code=500)
    )

    result = await job.push_to_hub(payload, _hub())
    assert result is None
    assert hooks.validate_called is True


@respx.mock
async def test_push_to_hub_calls_both_hooks_in_order_then_io_stub() -> None:
    """When both AIS gates pass, the current stub raises NotImplementedError
    — this pins the boundary between Track 1 scaffold and the real L2 IO.
    When the IO lands, this test fails and gets replaced with a
    happy-path-with-respx test."""
    hooks = RecordingApprovalHooks()
    job = FederationPushJob(hooks=hooks)
    payload = job.build_payload(
        sample=_sample_row(),
        fasta_presigned_url="https://signed.example.test/fasta/AZ-001.fasta",
    )
    target = _hub()
    respx.post("https://hub.example.test/api/v1/federation/push").mock(
        return_value=respx.MockResponse(status_code=200)
    )

    with pytest.raises(NotImplementedError, match="Level 2 IO not yet wired"):
        await job.push_to_hub(payload, target)

    assert len(hooks.validate_calls) == 1
    assert len(hooks.threshold_calls) == 1
    assert hooks.validate_calls[0][1] is target
    action, partners = hooks.threshold_calls[0]
    assert action == "ROUTINE_PUSH"
    assert partners == [target]


# ---------------------------------------------------------------------------
# Default-hooks construction
# ---------------------------------------------------------------------------


async def test_push_job_default_hooks_are_null_impl() -> None:
    """With no hooks injected, FederationPushJob uses NullAISFederationHooks
    — both gates pass and the stub raises NotImplementedError."""
    job = FederationPushJob()
    payload = job.build_payload(
        sample=_sample_row(),
        fasta_presigned_url="https://signed.example.test/fasta/AZ-001.fasta",
    )
    with pytest.raises(NotImplementedError):
        await job.push_to_hub(payload, _hub())
