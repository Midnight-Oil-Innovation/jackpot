# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Unit tests for backend.immune.sec.dp_aggregator.

These tests use NullPrivacyHooks and hand-rolled spy hooks classes; no
real Laplace/Gaussian noise is exercised here. The aim is to pin the
DPAggregator <-> AISPrivacyHooks Protocol contract, not the underlying
noise mechanics (which live behind the seam in a later IM-4 session).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.immune.sec.dp_aggregator import (
    AISPrivacyHooks,
    DPAggregator,
    NullPrivacyHooks,
)
from backend.settings import settings

# ---------------------------------------------------------------------------
# Spy hook helpers
# ---------------------------------------------------------------------------


class _FixedNoiseSpy:
    """Hooks stub that returns a constant noise value and records every call."""

    def __init__(self, noise: float) -> None:
        self.noise = noise
        self.dp_noise_calls: list[tuple[float, float]] = []
        self.budget_calls: list[tuple[float, str]] = []

    def dp_noise(self, sensitivity: float, epsilon: float) -> float:
        self.dp_noise_calls.append((sensitivity, epsilon))
        return self.noise

    def track_dp_budget(self, epsilon: float, signal_type: str) -> None:
        self.budget_calls.append((epsilon, signal_type))


class _StrictEpsilonHooks:
    """Hooks stub that rejects epsilon <= 0 — used to pin the ε>0 contract."""

    def dp_noise(self, sensitivity: float, epsilon: float) -> float:  # noqa: ARG002
        if epsilon <= 0:
            raise ValueError("epsilon must be > 0")
        return 0.0

    def track_dp_budget(self, epsilon: float, signal_type: str) -> None:  # noqa: ARG002
        return


# ---------------------------------------------------------------------------
# Happy-path tests (NullPrivacyHooks — zero noise)
# ---------------------------------------------------------------------------


def test_aggregate_member_count_zero_noise() -> None:
    agg = DPAggregator(hooks=NullPrivacyHooks())
    assert agg.aggregate_member_count(100) == 100


def test_aggregate_member_count_custom_epsilon() -> None:
    spy = MagicMock(wraps=NullPrivacyHooks())
    spy.dp_noise.return_value = 0.0
    agg = DPAggregator(hooks=spy)
    result = agg.aggregate_member_count(100, epsilon=0.5)
    assert result == 100
    spy.track_dp_budget.assert_called_once_with(epsilon=0.5, signal_type="member_count")


def test_aggregate_lineage_frequencies_zero_noise() -> None:
    agg = DPAggregator(hooks=NullPrivacyHooks())
    out = agg.aggregate_lineage_frequencies({"A": 0.6, "B": 0.4})
    assert out == {"A": 0.6, "B": 0.4}


def test_aggregate_lineage_frequencies_renormalises() -> None:
    spy = _FixedNoiseSpy(noise=0.1)
    agg = DPAggregator(hooks=spy)
    out = agg.aggregate_lineage_frequencies({"A": 0.6, "B": 0.4})
    assert sum(out.values()) == pytest.approx(1.0, abs=1e-9)
    # Each output should still be positive and reflect the +0.1 noise per key.
    assert out["A"] == pytest.approx(0.7 / 1.2, abs=1e-9)
    assert out["B"] == pytest.approx(0.5 / 1.2, abs=1e-9)


def test_aggregate_amr_fingerprint_zero_noise() -> None:
    agg = DPAggregator(hooks=NullPrivacyHooks())
    out = agg.aggregate_amr_fingerprint({"blaZ": 0.9, "mecA": 0.3})
    assert out == {"blaZ": 0.9, "mecA": 0.3}


def test_aggregate_amr_fingerprint_no_renormalisation() -> None:
    spy = _FixedNoiseSpy(noise=0.1)
    agg = DPAggregator(hooks=spy)
    out = agg.aggregate_amr_fingerprint({"blaZ": 0.9, "mecA": 0.3})
    # Raw clamping only — not re-normalised to sum 1.
    assert out == {"blaZ": pytest.approx(1.0), "mecA": pytest.approx(0.4)}
    assert sum(out.values()) != pytest.approx(1.0)


def test_empty_lineage_frequencies_returns_empty() -> None:
    spy = _FixedNoiseSpy(noise=0.0)
    agg = DPAggregator(hooks=spy)
    assert agg.aggregate_lineage_frequencies({}) == {}
    assert spy.budget_calls == []


def test_empty_amr_fingerprint_returns_empty() -> None:
    spy = _FixedNoiseSpy(noise=0.0)
    agg = DPAggregator(hooks=spy)
    assert agg.aggregate_amr_fingerprint({}) == {}
    assert spy.budget_calls == []


def test_default_epsilon_from_settings() -> None:
    agg = DPAggregator()
    assert agg._epsilon == settings.DP_EPSILON


# ---------------------------------------------------------------------------
# Failure-path / edge-case tests
# ---------------------------------------------------------------------------


def test_member_count_clamped_to_zero() -> None:
    spy = _FixedNoiseSpy(noise=-9999.0)
    agg = DPAggregator(hooks=spy)
    assert agg.aggregate_member_count(100) == 0


def test_lineage_frequencies_all_zero_after_noise() -> None:
    spy = _FixedNoiseSpy(noise=-9999.0)
    agg = DPAggregator(hooks=spy)
    out = agg.aggregate_lineage_frequencies({"A": 0.6, "B": 0.4})
    # All values clamped to 0 -> uniform fallback distribution.
    assert out == {"A": 0.5, "B": 0.5}


def test_amr_fingerprint_clamped_to_zero() -> None:
    spy = _FixedNoiseSpy(noise=-9999.0)
    agg = DPAggregator(hooks=spy)
    out = agg.aggregate_amr_fingerprint({"blaZ": 0.9, "mecA": 0.3})
    assert out == {"blaZ": 0.0, "mecA": 0.0}


def test_track_budget_not_called_on_empty_lineage() -> None:
    spy = _FixedNoiseSpy(noise=0.0)
    agg = DPAggregator(hooks=spy)
    agg.aggregate_lineage_frequencies({})
    assert spy.budget_calls == []
    assert spy.dp_noise_calls == []


def test_track_budget_not_called_on_empty_amr() -> None:
    spy = _FixedNoiseSpy(noise=0.0)
    agg = DPAggregator(hooks=spy)
    agg.aggregate_amr_fingerprint({})
    assert spy.budget_calls == []
    assert spy.dp_noise_calls == []


def test_null_hooks_conforms_to_protocol() -> None:
    assert isinstance(NullPrivacyHooks(), AISPrivacyHooks)


def test_invalid_epsilon_zero_raises() -> None:
    agg = DPAggregator(hooks=_StrictEpsilonHooks())
    with pytest.raises(ValueError, match="epsilon must be > 0"):
        agg.aggregate_member_count(10, epsilon=0.0)
