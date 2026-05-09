"""AIS hook seams for backend.privacy.

Defines the Protocol surface that connects Track 1 privacy primitives to
Track 2 AIS-augmented overlays. Track 1 ships with NullAISPrivacyHooks as
a no-op default; concrete implementations live in
backend/immune/sec/privacy_hooks.py and import this Protocol.

Direction of dependency is one-way: backend.privacy never imports from
backend.immune; backend.immune.sec.privacy_hooks imports AISPrivacyHooks
defined here.

Hook -> AIS doc mapping is documented in README.md.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AISPrivacyHooks(Protocol):
    """Extension points for AIS-augmented privacy overlays.

    All hooks are optional; the Null default below provides safe behavior for
    Track 1 deployments. Concrete impls are wired via dependency injection on
    the Track 1 primitive classes (Coarsener, DLPScanner, ScrubberOrchestrator,
    DPBudgetLedger).
    """

    def dp_noise(
        self,
        query_result: Any,
        sensitivity: float,
        epsilon: float,
    ) -> Any:
        """Add calibrated noise to a query result.

        Track 1 default: returns query_result unchanged.
        Track 2 impl: backend/immune/sec/dp_layer.py (calibrated DP mechanisms).
        AIS layer: section 1.4 adaptive immunity (memory).
        AIS doc: Jackpot_AIS.md Part 3 Capability 2 (~L2674).
        """
        ...

    def track_dp_budget(
        self,
        requester_id: str,
        epsilon_spent: float,
    ) -> float:
        """Record an epsilon expenditure and return remaining budget.

        Track 1 default: returns float('inf') (no enforcement).
        Track 2 impl: backend/immune/sec/dp_budget.py (RDP/zCDP accountant).
        AIS layer: section 1.8 tolerance / regulation.
        AIS doc: Jackpot_AIS.md Part 3 Capability 2; curriculum PP-DP modules.
        """
        ...

    def fl_aggregate(
        self,
        local_updates: list[Any],
        schema: dict[str, Any],
    ) -> Any:
        """Securely aggregate local model updates into a global update.

        Track 1 default: raises NotImplementedError (no Track 1 FL primitive).
        Track 2 impl: backend/immune/sec/cs_cyber_federated.py.
        AIS layer: section 1.6 inter-instance signaling (federation cytokine bus).
        AIS doc: Jackpot_AIS.md Part 3 Capability 1 (~L2649).
        """
        ...

    def he_compute(
        self,
        encrypted_inputs: list[bytes],
        op: str,
        key_ref: str,
    ) -> bytes:
        """Compute on homomorphically encrypted inputs.

        Track 1 default: raises NotImplementedError.
        Track 2 impl: backend/immune/sec/he_backend.py.
        AIS layer: section 1.4 adaptive immunity (state-bearing computation).
        AIS doc: Jackpot_AIS.md Part 3 Capability 3 (~L2699).
        """
        ...

    def mpc_protocol(
        self,
        parties: list[str],
        computation_spec: dict[str, Any],
    ) -> Any:
        """Run a multi-party computation across the given parties.

        Track 1 default: raises NotImplementedError.
        Track 2 impl: backend/immune/sec/mpc_backend.py.
        AIS layer: section 1.6 inter-instance signaling.
        AIS doc: Jackpot_AIS.md Part 3 Capability 4 (~L2722).
        """
        ...

    def synthetic_substitute(
        self,
        real_dataset: Any,
        fidelity_target: float,
    ) -> Any:
        """Substitute a real dataset with a synthetic surrogate.

        Track 1 default: returns real_dataset unchanged (passthrough).
        Track 2 impl: backend/immune/algorithms/featurizers/ (synth generators).
        AIS layer: section 1.5 diversity layer (N-variant surrogates).
        AIS doc: Jackpot_AIS.md curriculum PP-3 + Part 3 (~L2167).
        """
        ...


class NullAISPrivacyHooks:
    """No-op default implementation. Track 1 ships with this.

    Behaviors:
      - dp_noise: identity (returns input unchanged)
      - track_dp_budget: returns float('inf') (unlimited budget)
      - synthetic_substitute: identity (returns input unchanged)
      - fl_aggregate / he_compute / mpc_protocol: raise NotImplementedError
        (these have no Track 1 fallback; callers must wire Track 2 explicitly)
    """

    def dp_noise(
        self,
        query_result: Any,
        sensitivity: float,
        epsilon: float,
    ) -> Any:
        return query_result

    def track_dp_budget(
        self,
        requester_id: str,
        epsilon_spent: float,
    ) -> float:
        return float("inf")

    def fl_aggregate(
        self,
        local_updates: list[Any],
        schema: dict[str, Any],
    ) -> Any:
        raise NotImplementedError(
            "fl_aggregate has no Track 1 implementation. "
            "Wire backend.immune.sec.privacy_hooks.RealAISPrivacyHooks via DI."
        )

    def he_compute(
        self,
        encrypted_inputs: list[bytes],
        op: str,
        key_ref: str,
    ) -> bytes:
        raise NotImplementedError(
            "he_compute has no Track 1 implementation. "
            "Wire backend.immune.sec.privacy_hooks.RealAISPrivacyHooks via DI."
        )

    def mpc_protocol(
        self,
        parties: list[str],
        computation_spec: dict[str, Any],
    ) -> Any:
        raise NotImplementedError(
            "mpc_protocol has no Track 1 implementation. "
            "Wire backend.immune.sec.privacy_hooks.RealAISPrivacyHooks via DI."
        )

    def synthetic_substitute(
        self,
        real_dataset: Any,
        fidelity_target: float,
    ) -> Any:
        return real_dataset
