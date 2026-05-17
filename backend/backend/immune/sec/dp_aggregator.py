"""
Differential-privacy aggregator for federation-wide shared signals.

Supported signal types
----------------------
- member_count       : int  -> noised int (floor(max(0, v + noise)))
- lineage_frequencies: dict[str, float] -> per-key noised floats, re-normalised to sum 1
- amr_fingerprint    : dict[str, float] -> per-key noised floats (no re-normalisation)

All noise is injected via AISPrivacyHooks.dp_noise so that:
  a) unit tests can swap in a NullPrivacyHooks (zero noise) stub without
     patching internals
  b) the production hooks can call into the real privacy library without
     this module knowing

Budget tracking is delegated to AISPrivacyHooks.track_dp_budget after every
call so the caller's budget ledger stays consistent.

Default epsilon is read from settings.DP_EPSILON at import time. Callers may
override epsilon per-call.
"""

from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

from backend.settings import settings


@runtime_checkable
class AISPrivacyHooks(Protocol):
    """Protocol seam for DP noise injection and budget tracking.

    Mirrors the broader ``backend.privacy._ais_hooks.AISPrivacyHooks``
    seam pattern but narrows the surface to just the two methods this
    aggregator needs. Concrete production hooks live in
    ``backend/immune/sec/privacy_hooks.py`` (delivered in a later IM-4
    session); tests swap in :class:`NullPrivacyHooks` or a hand-rolled
    spy.
    """

    def dp_noise(self, sensitivity: float, epsilon: float) -> float:
        """Return a single Laplace noise sample scaled to sensitivity/epsilon."""
        ...

    def track_dp_budget(self, epsilon: float, signal_type: str) -> None:
        """Record epsilon expenditure in the caller's budget ledger."""
        ...


class NullPrivacyHooks:
    """Zero-noise default — safe for tests and local dev; never ship to prod."""

    def dp_noise(self, sensitivity: float, epsilon: float) -> float:  # noqa: ARG002
        return 0.0

    def track_dp_budget(self, epsilon: float, signal_type: str) -> None:  # noqa: ARG002
        return


class DPAggregator:
    """Aggregate federation-wide signals under differential privacy.

    Parameters
    ----------
    hooks:
        AISPrivacyHooks implementation. Defaults to NullPrivacyHooks.
    default_epsilon:
        Privacy budget per aggregation call. Defaults to settings.DP_EPSILON.
    """

    def __init__(
        self,
        hooks: AISPrivacyHooks | None = None,
        default_epsilon: float | None = None,
    ) -> None:
        self._hooks: AISPrivacyHooks = hooks or NullPrivacyHooks()
        self._epsilon: float = (
            default_epsilon if default_epsilon is not None else settings.DP_EPSILON
        )

    def aggregate_member_count(
        self,
        count: int,
        sensitivity: float = 1.0,
        epsilon: float | None = None,
    ) -> int:
        """Return a differentially-private integer member count.

        Noise is drawn from Laplace(sensitivity/epsilon) via the hooks
        implementation. Result is clamped to [0, +inf) and rounded to
        nearest int.
        """
        eps = epsilon if epsilon is not None else self._epsilon
        noise = self._hooks.dp_noise(sensitivity=sensitivity, epsilon=eps)
        self._hooks.track_dp_budget(epsilon=eps, signal_type="member_count")
        return max(0, math.floor(count + noise + 0.5))

    def aggregate_lineage_frequencies(
        self,
        frequencies: dict[str, float],
        sensitivity: float = 1.0,
        epsilon: float | None = None,
    ) -> dict[str, float]:
        """Return per-lineage DP-noised frequencies, re-normalised to sum 1.

        An empty input dict returns an empty dict without budget expenditure.
        """
        if not frequencies:
            return {}
        eps = epsilon if epsilon is not None else self._epsilon
        noised = {
            k: max(0.0, v + self._hooks.dp_noise(sensitivity=sensitivity, epsilon=eps))
            for k, v in frequencies.items()
        }
        total = sum(noised.values())
        if total == 0.0:
            n = len(noised)
            normalised = {k: 1.0 / n for k in noised}
        else:
            normalised = {k: v / total for k, v in noised.items()}
        self._hooks.track_dp_budget(epsilon=eps, signal_type="lineage_frequencies")
        return normalised

    def aggregate_amr_fingerprint(
        self,
        fingerprint: dict[str, float],
        sensitivity: float = 1.0,
        epsilon: float | None = None,
    ) -> dict[str, float]:
        """Return per-resistance-gene DP-noised AMR fingerprint values.

        Values are clamped to [0, +inf); no re-normalisation is applied
        because AMR presence scores are independent, not a probability
        simplex. An empty input dict returns an empty dict without budget
        expenditure.
        """
        if not fingerprint:
            return {}
        eps = epsilon if epsilon is not None else self._epsilon
        noised = {
            k: max(0.0, v + self._hooks.dp_noise(sensitivity=sensitivity, epsilon=eps))
            for k, v in fingerprint.items()
        }
        self._hooks.track_dp_budget(epsilon=eps, signal_type="amr_fingerprint")
        return noised
