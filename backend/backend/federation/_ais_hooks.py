"""
AIS extension points for federation.

These are Track 2 scaffolding. Track 1 ships with `NullAISFederationHooks`
in every code path so the AIS work can land later without any changes to
client.py / push.py / access.py.

Each hook is documented with:
  - The AIS doc section it ties to
  - The Track 2 implementation module that will satisfy it (under
    backend/immune/) and the sibling immune-platform modules it imports
  - The expertise area needed to land the concrete implementation
  - The minimum-viable signature (extend if needed; don't break it)

When the AIS work is ready, define a real implementation that satisfies the
`AISFederationHooks` protocol and inject it via the constructor of any
federation class:

    from backend.immune.net.federation_hooks import RealAISFederationHooks
    client = FederationClient(hooks=RealAISFederationHooks(...))

The seam is the constructor argument. Track 1 deployment uses
`NullAISFederationHooks`, Track 2 deployment uses the real one. Direction
of import is one-way: this module never imports from `backend/immune/`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.federation.models import (
    FederatedInstance,
    FederationPushPayload,
    FederationQuery,
    FederationQueryResult,
)


@runtime_checkable
class AISFederationHooks(Protocol):
    """Extension surface for AIS-flavored federation augmentation.

    See `Jackpot_AIS.md` Part 1 for the AIS conceptual model. This protocol
    is the bridge from Track 1 federation implementations to Track 2
    AIS-augmented behavior. Default implementations are no-ops; the AIS work
    overrides them via dependency injection.
    """

    def secure_aggregate(
        self,
        results: list[FederationQueryResult],
        partner_set: list[FederatedInstance],
    ) -> list[FederationQueryResult]:
        """Aggregate query results across partners with privacy guarantees.

        AIS doc:        §1.6 (inter-instance signaling)
        Security doc:   Capability 1 (FL) + Capability 2 (DP)
        Track 2 impl:   backend/immune/net/federation_hooks.py imports this
                        from backend/immune/sec/cs_cyber_federated.py
        Expertise:      applied cryptography (secure-aggregation protocols,
                        DP budget composition, FL parameter selection)

        Track 1 default (NullAISFederationHooks): identity — return results
        unchanged.

        Track 2 expected: cryptographic secure aggregation across partners
        so neither the coordinator nor any individual partner sees another
        partner's contribution. Composable with DP-SGD when the upstream
        caller is doing federated learning rather than just federated query.
        """
        ...

    def attest_partner(
        self,
        instance: FederatedInstance,
    ) -> bool:
        """Verify a partner's TEE attestation evidence before trusting them.

        AIS doc:        §1.7 (attribution & deception)
        Security doc:   Foundation 3 (Confidential Computing as Target G)
        Track 2 impl:   backend/immune/net/federation_hooks.py imports
                        attestation primitives from backend/immune/sec/
                        (new module — to be added with TEE deployment work)
        Expertise:      TEE / remote attestation, trusted-hardware
                        deployments, Confidential JACKPOT (Target G) sponsor

        Track 1 default (NullAISFederationHooks): always True. Track 1
        federation runs without TEE; this hook returns True to keep the
        traffic flowing.

        Track 2 expected: validate the partner's remote attestation evidence
        against a known-good policy (image hash, TEE provider, signing key).
        Reject and log if the evidence doesn't verify. Slot this into the
        FederationClient before issuing any query.
        """
        ...

    def detect_anomalous_traffic(
        self,
        query: FederationQuery,
        partner: FederatedInstance,
    ) -> bool:
        """Flag federation queries that match attacker patterns.

        AIS doc:        §1.3 (innate immunity — fast pattern-based detection)
        Security doc:   AI Agent OPSEC (Part 5)
        Track 2 impl:   backend/immune/net/federation_hooks.py imports from
                        backend/immune/algorithms/featurizers/ (diversity-
                        based detection) and from
                        backend/immune/redteam/attack_federation.py (known
                        attack patterns, used as inverse-classifier training)
        Expertise:      AIS theory (diversity / anomaly detection) +
                        adversarial ML (red-team-derived attack patterns)

        Track 1 default (NullAISFederationHooks): False — no anomaly.

        Track 2 expected: classify the (query, partner, timing, history)
        tuple. Patterns to flag include rapid drill-down on rare clades,
        exfiltration signatures (paginating through everything), and
        coordinated query bursts across multiple partners. On True, the
        caller emits a cytokine signal to other federation members and
        rate-limits the partner.
        """
        ...

    def threshold_approve(
        self,
        action: str,
        affected_partners: list[FederatedInstance],
    ) -> bool:
        """M-of-N threshold-signature check for sensitive federation actions.

        AIS doc:        §1.8 (tolerance / regulation — anti-autoimmune)
        Security doc:   Capability 6 (threshold cryptography for governance)
        Track 2 impl:   backend/immune/net/federation_hooks.py imports
                        threshold-crypto primitives from backend/immune/sec/
                        (new module — to be added)
        Expertise:      applied cryptography (FROST / BLS / DKG, distributed
                        key generation, M-of-N quorum protocols)

        Track 1 default (NullAISFederationHooks): True — single-admin
        approval suffices in Track 1. This is consistent with the existing
        Lab Director model and gets us federation L1/L2/L3 working without
        introducing a hard governance dependency.

        Track 2 expected: collect M-of-N threshold signatures from the
        affected partners' federation governance keys (FROST or BLS). Reject
        if quorum not met. Examples of actions:
          - "REMOVE_PARTNER"
          - "CHANGE_HUB_POLICY"
          - "RAISE_MIN_SHARING_LEVEL"
          - "EMERGENCY_FEDERATION_HALT"
        """
        ...

    def validate_push_payload(
        self,
        payload: FederationPushPayload,
        target: FederatedInstance,
    ) -> bool:
        """Final sanity check on outbound L2 push payloads.

        AIS doc:        §1.8 (tolerance — don't attack self)
        Security doc:   Foundation 5 (WORM audit) + privacy gates
        Track 2 impl:   backend/immune/net/federation_hooks.py imports from
                        backend/immune/sec/refusal.py and
                        backend/immune/sec/parsers_safe.py
        Expertise:      platform-internal — no external collaboration
                        required. Payload-anomaly heuristics composed from
                        the existing scrubber / DLP / refusal-rule machinery.

        Track 1 default (NullAISFederationHooks): True. Track 1 relies on
        the existing scrubber + DLP gate at ingest plus the explicit
        de-identification of the payload schema; this hook is reserved.

        Track 2 expected: detect "self attack" — payloads that are
        unexpectedly different from this instance's typical push profile
        (organism mix, volume, geographic distribution). Flag and require
        threshold approval before sending.
        """
        ...


class NullAISFederationHooks:
    """No-op default implementation — ships with Track 1.

    Every method returns the safe default that lets the underlying Track 1
    code path run unchanged. This is what `__init__.py` exposes as the
    default `hooks=` argument everywhere in the package.

    DO NOT add behavior here. This class is the seam, not the hook
    implementation. Real behavior goes in `research/ais/federation_hooks.py`
    or wherever the AIS work lives.
    """

    def secure_aggregate(
        self,
        results: list[FederationQueryResult],
        partner_set: list[FederatedInstance],
    ) -> list[FederationQueryResult]:
        return results

    def attest_partner(self, instance: FederatedInstance) -> bool:
        return True

    def detect_anomalous_traffic(
        self,
        query: FederationQuery,
        partner: FederatedInstance,
    ) -> bool:
        return False

    def threshold_approve(
        self,
        action: str,
        affected_partners: list[FederatedInstance],
    ) -> bool:
        return True

    def validate_push_payload(
        self,
        payload: FederationPushPayload,
        target: FederatedInstance,
    ) -> bool:
        return True
