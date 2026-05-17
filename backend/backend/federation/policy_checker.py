# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""
Encrypted-query policy checker — Track 1 implementation.

Sits between the federation router (entry) and the HE compute backend
(exit). Per Driver et al. 2024 cryptWWDB design (Sci Total Environ §3.1),
the computation coordinator must enforce two policies on every encrypted
query before it reaches the HE backend:

  1. Access control — the requester is allowed to run this HE operation
     against this dataset.
  2. Repeated-query detection — the same (requester, encrypted-operand
     digest) pair has not been seen too many times inside a sliding time
     window. Repeated identical encrypted queries are a known side-channel
     against HE schemes: a coordinator that re-runs the same ciphertext
     leaks correlation information through observed traffic / response
     timing even when each individual ciphertext stays opaque.

Currently these responsibilities are implicit in the federation router;
making them a discrete module makes the policy enforcement auditable and
testable. The federation router calls ``PolicyChecker.check()`` and acts
on the returned ``PolicyVerdict``; the HE compute backend never sees a
request the checker denied.

AIS hook seam:
  - ``attest_partner()`` is consulted when the caller passes a
    ``requester_instance``. Track 1 ``NullAISFederationHooks`` always
    returns True; Track 2 verifies remote attestation evidence before the
    request enters the HE compute backend.

The audit log is in-memory by design — durable persistence (e.g. to a
``federation_policy_audit`` table) is the responsibility of the federation
router that owns this checker, just as durable persistence of access
requests is the responsibility of callers of ``FederationAccessGateway``.

Cross-references:
  - backend/backend/federation/_ais_hooks.py — Track 2 seam
  - backend/backend/crypto/_ais_hooks.py — HEOperation enum
  - docs/federation.md §"Policy-checker module surfaced"
  - Driver et al. 2024, Science of the Total Environment 940:173315
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

from backend.crypto._ais_hooks import HEOperation
from backend.federation._ais_hooks import (
    AISFederationHooks,
    NullAISFederationHooks,
)

if TYPE_CHECKING:
    from backend.federation.models import FederatedInstance

logger = logging.getLogger(__name__)

DEFAULT_REPEAT_WINDOW = timedelta(seconds=60)
DEFAULT_MAX_REPEATS_IN_WINDOW = 1


AccessPolicy = Callable[[str, HEOperation, str], bool]
"""Predicate ``(requester_id, operation, dataset_id) -> bool``.

Returning True permits the request to proceed to repeated-query detection.
Returning False produces an ACCESS_DENIED verdict immediately. The callable
is injected at construction so the checker stays independent of the
identity / authz subsystem (which lives upstream in the router).
"""


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class PolicyDenialReason(StrEnum):
    ACCESS_DENIED = "access_denied"
    UNATTESTED_REQUESTER = "unattested_requester"
    REPEATED_QUERY = "repeated_query"


@dataclass(frozen=True)
class EncryptedQueryRequest:
    """One encrypted query awaiting policy adjudication.

    ``encrypted_operand_digest`` is a hash over the ciphertext bytes (not
    the plaintext) — typically SHA-256 of the serialized HE ciphertext.
    The checker treats this as an opaque identifier; the only requirement
    is that identical ciphertexts produce identical digests so the
    repeated-query detector can spot replays.
    """

    requester_id: str
    operation: HEOperation
    target_dataset_id: str
    encrypted_operand_digest: str
    submitted_at: datetime
    requester_instance: FederatedInstance | None = None


@dataclass(frozen=True)
class PolicyVerdict:
    decision: PolicyDecision
    reason: str
    request: EncryptedQueryRequest
    evaluated_at: datetime
    denial_code: PolicyDenialReason | None = None


@dataclass
class _RequesterHistory:
    """Sliding-window history for one (requester_id, operand_digest) pair.

    Held as a deque so window-eviction is O(k) where k is the number of
    expired entries since the last check, not O(n) over the full history.
    """

    timestamps: deque[datetime] = field(default_factory=deque)


class PolicyChecker:
    """Discrete coordinator between federation router and HE compute backend.

    Enforces access control and repeated-query detection on every encrypted
    query the router forwards. The router obtains a ``PolicyVerdict`` via
    ``check(request)`` and only forwards ALLOW verdicts to the HE backend.

    Construction:

      access_policy: required callable that decides whether a requester
        may run the given HE operation against the given dataset. The
        checker treats this as an opaque oracle so the router can plug in
        the existing ``can_access_sample()`` machinery (or a federation-
        flavored variant) without this module needing to know about it.

      repeat_window: sliding window for the repeated-query detector.
        Default 60s — short enough that legitimate retries after transient
        backend failures still hit the limit (and should be deduplicated
        upstream), long enough that a determined replay attacker has to
        slow down meaningfully.

      max_repeats_in_window: how many times the same (requester,
        operand-digest) pair may appear inside ``repeat_window`` before a
        REPEATED_QUERY denial fires. Default 1 — first occurrence allowed,
        second within the window denied. Operators tune upward only with
        an explicit decision and an audit-log review.

      hooks: optional Track 2 ``AISFederationHooks``. Track 1 default is
        ``NullAISFederationHooks`` (``attest_partner`` always True).

      clock: optional callable returning the current ``datetime``. Default
        ``datetime.now(UTC)``. Injected for deterministic tests of the
        sliding-window behavior without ``freezegun``.
    """

    def __init__(
        self,
        *,
        access_policy: AccessPolicy,
        repeat_window: timedelta = DEFAULT_REPEAT_WINDOW,
        max_repeats_in_window: int = DEFAULT_MAX_REPEATS_IN_WINDOW,
        hooks: AISFederationHooks | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if max_repeats_in_window < 1:
            raise ValueError(
                "max_repeats_in_window must be >= 1; "
                "use a different denial path to block all queries."
            )
        if repeat_window <= timedelta(0):
            raise ValueError("repeat_window must be a positive duration.")

        self._access_policy: AccessPolicy = access_policy
        self._repeat_window: timedelta = repeat_window
        self._max_repeats: int = max_repeats_in_window
        self._hooks: AISFederationHooks = hooks or NullAISFederationHooks()
        self._clock: Callable[[], datetime] = clock or (lambda: datetime.now(UTC))
        self._history: dict[tuple[str, str], _RequesterHistory] = defaultdict(_RequesterHistory)
        self._audit: list[PolicyVerdict] = []

    def check(self, request: EncryptedQueryRequest) -> PolicyVerdict:
        """Adjudicate one encrypted query against access + repeat policy.

        Order of checks (each short-circuits on first denial):

          1. ``access_policy`` — fast, in-process
          2. ``hooks.attest_partner`` — only when ``requester_instance``
             is set (federation-originated requests); local requests skip
          3. Repeated-query detection against the sliding window

        On ALLOW the request's timestamp is recorded in the sliding
        window. On DENY nothing is recorded — a denied request must not
        consume the requester's repeated-query budget.

        Every adjudication, ALLOW or DENY, is appended to the in-memory
        audit log accessible via ``audit_log``.
        """
        now = self._clock()

        if not self._access_policy(
            request.requester_id,
            request.operation,
            request.target_dataset_id,
        ):
            return self._record(
                request=request,
                evaluated_at=now,
                decision=PolicyDecision.DENY,
                denial_code=PolicyDenialReason.ACCESS_DENIED,
                reason=(
                    f"Requester {request.requester_id} is not permitted to run "
                    f"operation {request.operation} against dataset "
                    f"{request.target_dataset_id}."
                ),
            )

        if request.requester_instance is not None and not self._hooks.attest_partner(
            request.requester_instance
        ):
            return self._record(
                request=request,
                evaluated_at=now,
                decision=PolicyDecision.DENY,
                denial_code=PolicyDenialReason.UNATTESTED_REQUESTER,
                reason=(
                    f"Requester instance {request.requester_instance.name} "
                    "failed Track 2 attestation."
                ),
            )

        history = self._history[(request.requester_id, request.encrypted_operand_digest)]
        self._evict_expired(history, now)
        if len(history.timestamps) >= self._max_repeats:
            return self._record(
                request=request,
                evaluated_at=now,
                decision=PolicyDecision.DENY,
                denial_code=PolicyDenialReason.REPEATED_QUERY,
                reason=(
                    f"Requester {request.requester_id} exceeded the repeated-"
                    f"query limit ({self._max_repeats} in {self._repeat_window})."
                ),
            )

        history.timestamps.append(now)
        return self._record(
            request=request,
            evaluated_at=now,
            decision=PolicyDecision.ALLOW,
            denial_code=None,
            reason="Access and repeated-query policy checks passed.",
        )

    @property
    def audit_log(self) -> list[PolicyVerdict]:
        """Return a defensive copy of the in-memory audit log.

        Durable persistence is the responsibility of the federation router
        that owns the checker; the in-memory log is a forensics surface
        for the lifetime of one router instance.
        """
        return list(self._audit)

    def _evict_expired(self, history: _RequesterHistory, now: datetime) -> None:
        window_start = now - self._repeat_window
        timestamps = history.timestamps
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

    def _record(
        self,
        *,
        request: EncryptedQueryRequest,
        evaluated_at: datetime,
        decision: PolicyDecision,
        denial_code: PolicyDenialReason | None,
        reason: str,
    ) -> PolicyVerdict:
        verdict = PolicyVerdict(
            decision=decision,
            reason=reason,
            request=request,
            evaluated_at=evaluated_at,
            denial_code=denial_code,
        )
        self._audit.append(verdict)
        if decision is PolicyDecision.DENY:
            logger.warning(
                "policy_checker DENY %s requester=%s operation=%s dataset=%s",
                denial_code,
                request.requester_id,
                request.operation,
                request.target_dataset_id,
            )
        return verdict
