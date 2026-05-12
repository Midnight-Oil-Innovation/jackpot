# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Track-2 AIS hook surface tests.

Pins the `NullAISFederationHooks` no-op contract for all five Protocol
methods, and verifies that `NullAISFederationHooks` is recognized as an
`AISFederationHooks` at runtime via `runtime_checkable`. Together these
guarantees ensure that Track 1 ships unchanged when Track 2 hook
implementations land — the seam holds.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from backend.federation._ais_hooks import (
    AISFederationHooks,
    NullAISFederationHooks,
)
from backend.federation.models import (
    FederatedInstance,
    FederationPushPayload,
    FederationQuery,
    FederationQueryResult,
    FederationRole,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _instance() -> FederatedInstance:
    return FederatedInstance(
        id=uuid4(),
        name="Partner",
        base_url="https://partner.example.test/",
        role=FederationRole.PEER,
        federation_enabled=True,
        min_sharing_level_for_federation="DISCOVERABLE",
        hub_instance_url=None,
        api_key_secret_name="fed/partner/key",
        last_seen_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _result() -> FederationQueryResult:
    return FederationQueryResult(
        sample_id="P-1",
        organism="SARS-CoV-2",
        date_collected=date(2026, 1, 15),
        country="US",
        state="AZ",
        source_type="clinical",
        sector="clinical",
        quality_tier="ANALYZABLE",
        surveillance_relevant=True,
        source_instance_id=uuid4(),
        source_instance_name="Partner",
    )


def _payload() -> FederationPushPayload:
    return FederationPushPayload(
        sample_id="P-1",
        organism="SARS-CoV-2",
        date_collected=date(2026, 1, 15),
        country="US",
        state="AZ",
        source_type="clinical",
        sector="clinical",
        quality_tier="ANALYZABLE",
        surveillance_relevant=True,
        fasta_url="https://signed.example.test/fasta/P-1.fasta",
        typing_results={},
        amr_profile={},
        lineage=None,
        clade=None,
        host_age_range=None,
        originating_lab="Partner Lab",
        submitting_lab=None,
        data_generator=None,
        pushed_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Null-impl behavior — every method returns the documented Track 1 safe default
# ---------------------------------------------------------------------------


def test_null_hooks_secure_aggregate_is_identity() -> None:
    hooks = NullAISFederationHooks()
    results = [_result(), _result()]
    partners = [_instance(), _instance()]
    out = hooks.secure_aggregate(results, partners)
    # Track 1 contract: identity. Not a copy, the same list object —
    # which is fine; the caller does not mutate after.
    assert out == results


def test_null_hooks_secure_aggregate_handles_empty_results() -> None:
    hooks = NullAISFederationHooks()
    assert hooks.secure_aggregate([], []) == []


def test_null_hooks_attest_partner_always_true() -> None:
    hooks = NullAISFederationHooks()
    assert hooks.attest_partner(_instance()) is True


def test_null_hooks_detect_anomalous_traffic_always_false() -> None:
    hooks = NullAISFederationHooks()
    assert hooks.detect_anomalous_traffic(FederationQuery(), _instance()) is False


def test_null_hooks_threshold_approve_always_true() -> None:
    hooks = NullAISFederationHooks()
    assert (
        hooks.threshold_approve(
            action="REMOVE_PARTNER",
            affected_partners=[_instance()],
        )
        is True
    )


def test_null_hooks_threshold_approve_with_empty_partner_list() -> None:
    hooks = NullAISFederationHooks()
    assert hooks.threshold_approve(action="EMERGENCY_FEDERATION_HALT", affected_partners=[]) is True


def test_null_hooks_validate_push_payload_always_true() -> None:
    hooks = NullAISFederationHooks()
    assert hooks.validate_push_payload(_payload(), _instance()) is True


# ---------------------------------------------------------------------------
# Protocol shape — runtime_checkable
# ---------------------------------------------------------------------------


def test_null_impl_satisfies_protocol_at_runtime() -> None:
    """`@runtime_checkable` on `AISFederationHooks` means `isinstance`
    succeeds on any object with the right method names. This is the contract
    federation modules rely on when they accept `hooks: AISFederationHooks`."""
    assert isinstance(NullAISFederationHooks(), AISFederationHooks)


def test_arbitrary_object_with_matching_methods_satisfies_protocol() -> None:
    """The Protocol is structural, not nominal — any object exposing the
    five methods qualifies. This is what lets Track 2's
    `RealAISFederationHooks` slot in without inheriting from the Protocol."""

    class CustomHooks:
        def secure_aggregate(self, results, partner_set):
            return results

        def attest_partner(self, instance):
            return True

        def detect_anomalous_traffic(self, query, partner):
            return False

        def threshold_approve(self, action, affected_partners):
            return True

        def validate_push_payload(self, payload, target):
            return True

    assert isinstance(CustomHooks(), AISFederationHooks)


def test_object_missing_a_method_does_not_satisfy_protocol() -> None:
    """A truly bare object must not be recognized as an AISFederationHooks.
    Pins that `runtime_checkable` is actually working (not silently True)."""

    class Empty:
        pass

    assert not isinstance(Empty(), AISFederationHooks)
