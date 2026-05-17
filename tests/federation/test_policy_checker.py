# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""PolicyChecker (B-CWB-POLICY-1) tests.

Covers the three enforcement paths and the audit-log accumulation:

  - Access-control denial (`access_policy` returns False) -> DENY
    ACCESS_DENIED; the repeated-query budget is NOT consumed (a denied
    request must not enable a later legitimate query to be wrongly
    flagged as a repeat).
  - Track 2 attestation denial (federation-originated requests only) ->
    DENY UNATTESTED_REQUESTER; access policy ran first.
  - Repeated-query detection -> first call ALLOW, immediate replay DENY
    REPEATED_QUERY; replay after the sliding window has elapsed re-ALLOWs.
  - Distinct operand digests from the same requester are tracked
    independently (per-pair budget, not per-requester).
  - Audit log accumulates verdicts in adjudication order.
  - Default-construction uses NullAISFederationHooks (Track 1 ships).
  - Constructor validates window / repeat parameters.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from backend.crypto._ais_hooks import HEOperation
from backend.federation._ais_hooks import NullAISFederationHooks
from backend.federation.models import FederatedInstance, FederationRole
from backend.federation.policy_checker import (
    EncryptedQueryRequest,
    PolicyChecker,
    PolicyDecision,
    PolicyDenialReason,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


T0 = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)


class _Clock:
    """Mutable clock for deterministic sliding-window tests."""

    def __init__(self, start: datetime = T0) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


def _request(
    *,
    requester_id: str = "lab-alpha",
    operation: HEOperation = HEOperation.MASS_BALANCE,
    target_dataset_id: str = "ww-segment-7",
    operand_digest: str = "sha256:operand-A",
    submitted_at: datetime = T0,
    requester_instance: FederatedInstance | None = None,
) -> EncryptedQueryRequest:
    return EncryptedQueryRequest(
        requester_id=requester_id,
        operation=operation,
        target_dataset_id=target_dataset_id,
        encrypted_operand_digest=operand_digest,
        submitted_at=submitted_at,
        requester_instance=requester_instance,
    )


def _instance(name: str = "partner") -> FederatedInstance:
    return FederatedInstance(
        id=uuid4(),
        name=name,
        base_url=f"https://{name}.example.test/",
        role=FederationRole.DATA_SOURCE_LAB,
        federation_enabled=True,
        min_sharing_level_for_federation="DISCOVERABLE",
        hub_instance_url=None,
        api_key_secret_name=f"fed/{name}/key",
        last_seen_at=None,
        created_at=T0,
        updated_at=T0,
    )


class _RejectingAttestHooks(NullAISFederationHooks):
    def attest_partner(self, instance: FederatedInstance) -> bool:
        return False


def _allow_all(_requester: str, _op: HEOperation, _dataset: str) -> bool:
    return True


def _deny_all(_requester: str, _op: HEOperation, _dataset: str) -> bool:
    return False


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


def test_access_policy_denial_returns_access_denied_verdict() -> None:
    checker = PolicyChecker(access_policy=_deny_all, clock=_Clock())
    verdict = checker.check(_request())
    assert verdict.decision is PolicyDecision.DENY
    assert verdict.denial_code is PolicyDenialReason.ACCESS_DENIED
    assert "lab-alpha" in verdict.reason
    assert verdict.request.requester_id == "lab-alpha"


def test_access_denial_does_not_consume_repeated_query_budget() -> None:
    """A denied request must not show up in the sliding window. Otherwise a
    later legitimate request from the same requester for the same operand
    would be wrongly flagged as a repeat."""
    clock = _Clock()
    # Access is denied for the first call, allowed for the second.
    decisions = iter([False, True])
    checker = PolicyChecker(
        access_policy=lambda *_args: next(decisions),
        clock=clock,
    )
    req = _request()

    first = checker.check(req)
    second = checker.check(req)

    assert first.decision is PolicyDecision.DENY
    assert second.decision is PolicyDecision.ALLOW


# ---------------------------------------------------------------------------
# Track 2 attestation
# ---------------------------------------------------------------------------


def test_attestation_failure_denies_federation_originated_request() -> None:
    checker = PolicyChecker(
        access_policy=_allow_all,
        hooks=_RejectingAttestHooks(),
        clock=_Clock(),
    )
    verdict = checker.check(_request(requester_instance=_instance("partner")))
    assert verdict.decision is PolicyDecision.DENY
    assert verdict.denial_code is PolicyDenialReason.UNATTESTED_REQUESTER
    assert "partner" in verdict.reason


def test_local_request_skips_attestation_hook() -> None:
    """When requester_instance is None (local non-federation caller), the
    attestation hook is bypassed entirely — even a rejecting hook lets the
    request through to the repeated-query check."""
    checker = PolicyChecker(
        access_policy=_allow_all,
        hooks=_RejectingAttestHooks(),
        clock=_Clock(),
    )
    verdict = checker.check(_request(requester_instance=None))
    assert verdict.decision is PolicyDecision.ALLOW


# ---------------------------------------------------------------------------
# Repeated-query detection
# ---------------------------------------------------------------------------


def test_first_query_is_allowed_and_recorded() -> None:
    clock = _Clock()
    checker = PolicyChecker(access_policy=_allow_all, clock=clock)
    verdict = checker.check(_request())
    assert verdict.decision is PolicyDecision.ALLOW
    assert verdict.denial_code is None


def test_immediate_replay_within_window_is_denied() -> None:
    clock = _Clock()
    checker = PolicyChecker(
        access_policy=_allow_all,
        repeat_window=timedelta(seconds=60),
        max_repeats_in_window=1,
        clock=clock,
    )
    req = _request()
    first = checker.check(req)
    clock.advance(timedelta(seconds=5))
    second = checker.check(req)

    assert first.decision is PolicyDecision.ALLOW
    assert second.decision is PolicyDecision.DENY
    assert second.denial_code is PolicyDenialReason.REPEATED_QUERY
    assert "exceeded" in second.reason.lower()


def test_replay_after_window_expires_is_allowed_again() -> None:
    clock = _Clock()
    checker = PolicyChecker(
        access_policy=_allow_all,
        repeat_window=timedelta(seconds=60),
        max_repeats_in_window=1,
        clock=clock,
    )
    req = _request()
    checker.check(req)
    clock.advance(timedelta(seconds=61))
    second = checker.check(req)

    assert second.decision is PolicyDecision.ALLOW


def test_max_repeats_threshold_is_enforced() -> None:
    """With max_repeats_in_window=3, the first three identical queries
    inside the window all ALLOW; the fourth DENYs."""
    clock = _Clock()
    checker = PolicyChecker(
        access_policy=_allow_all,
        repeat_window=timedelta(seconds=60),
        max_repeats_in_window=3,
        clock=clock,
    )
    req = _request()
    for _ in range(3):
        assert checker.check(req).decision is PolicyDecision.ALLOW
        clock.advance(timedelta(seconds=1))
    fourth = checker.check(req)
    assert fourth.decision is PolicyDecision.DENY
    assert fourth.denial_code is PolicyDenialReason.REPEATED_QUERY


def test_distinct_operand_digests_tracked_independently() -> None:
    """Two different ciphertexts from the same requester share neither the
    sliding-window key nor each other's denial budget."""
    clock = _Clock()
    checker = PolicyChecker(
        access_policy=_allow_all,
        max_repeats_in_window=1,
        clock=clock,
    )
    a1 = checker.check(_request(operand_digest="sha256:operand-A"))
    b1 = checker.check(_request(operand_digest="sha256:operand-B"))
    a2 = checker.check(_request(operand_digest="sha256:operand-A"))

    assert a1.decision is PolicyDecision.ALLOW
    assert b1.decision is PolicyDecision.ALLOW
    assert a2.decision is PolicyDecision.DENY


def test_different_requesters_tracked_independently() -> None:
    clock = _Clock()
    checker = PolicyChecker(
        access_policy=_allow_all,
        max_repeats_in_window=1,
        clock=clock,
    )
    first = checker.check(_request(requester_id="lab-alpha"))
    second = checker.check(_request(requester_id="lab-beta"))
    assert first.decision is PolicyDecision.ALLOW
    assert second.decision is PolicyDecision.ALLOW


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


def test_audit_log_records_all_verdicts_in_order() -> None:
    clock = _Clock()
    checker = PolicyChecker(
        access_policy=_allow_all,
        max_repeats_in_window=1,
        clock=clock,
    )
    req = _request()
    checker.check(req)  # ALLOW
    clock.advance(timedelta(seconds=1))
    checker.check(req)  # DENY (replay)
    clock.advance(timedelta(seconds=61))
    checker.check(req)  # ALLOW (window expired)

    log = checker.audit_log
    assert [v.decision for v in log] == [
        PolicyDecision.ALLOW,
        PolicyDecision.DENY,
        PolicyDecision.ALLOW,
    ]
    assert log[1].denial_code is PolicyDenialReason.REPEATED_QUERY


def test_audit_log_returns_a_defensive_copy() -> None:
    checker = PolicyChecker(access_policy=_allow_all, clock=_Clock())
    checker.check(_request())
    snapshot = checker.audit_log
    snapshot.clear()
    assert len(checker.audit_log) == 1


# ---------------------------------------------------------------------------
# Default hooks construction
# ---------------------------------------------------------------------------


def test_default_construction_uses_null_hooks() -> None:
    """With no hooks injected, federation-originated requests with the
    Track 1 NullAISFederationHooks default pass attestation (True) and
    progress to the repeated-query check."""
    checker = PolicyChecker(access_policy=_allow_all, clock=_Clock())
    verdict = checker.check(_request(requester_instance=_instance("partner")))
    assert verdict.decision is PolicyDecision.ALLOW


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


def test_constructor_rejects_zero_max_repeats() -> None:
    with pytest.raises(ValueError, match="max_repeats_in_window"):
        PolicyChecker(access_policy=_allow_all, max_repeats_in_window=0)


def test_constructor_rejects_non_positive_window() -> None:
    with pytest.raises(ValueError, match="repeat_window"):
        PolicyChecker(
            access_policy=_allow_all,
            repeat_window=timedelta(seconds=0),
        )
