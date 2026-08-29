# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Tests for the B-CWB-MB-2 QC + trigger-point functions (Driver et al. 2024 Table 2)."""

import math

import pytest

from backend.wastewater.mass_balance import (
    clamp_negative_mb,
    handle_non_detects,
    propagate_error,
    rolling_average,
    trigger_point,
)

# --- handle_non_detects ---


def test_handle_non_detects_replaces_none():
    result = handle_non_detects([None, 2.0, None], lod=1.0)
    assert math.isclose(result[0], 0.5)
    assert math.isclose(result[1], 2.0)
    assert math.isclose(result[2], 0.5)


def test_handle_non_detects_all_present():
    values: list[float | None] = [1.0, 2.5, 3.0]
    result = handle_non_detects(values, lod=1.0)
    assert result == pytest.approx(values)


def test_handle_non_detects_empty():
    assert handle_non_detects([], lod=1.0) == []


# --- clamp_negative_mb ---


def test_clamp_negative_mb_clamps(caplog):
    with caplog.at_level("WARNING"):
        result = clamp_negative_mb(-3.5)
    assert math.isclose(result, 0.0)
    assert any("clamped" in r.message for r in caplog.records)


def test_clamp_negative_mb_zero():
    assert math.isclose(clamp_negative_mb(0.0), 0.0)


def test_clamp_negative_mb_positive():
    assert math.isclose(clamp_negative_mb(2.0), 2.0)


# --- propagate_error ---


def test_propagate_error_basic():
    # (10*0.1)**2 + (20*0.05)**2 = 1 + 1 = 2
    assert math.isclose(propagate_error([10.0, 20.0], [0.1, 0.05]), math.sqrt(2.0))


def test_propagate_error_length_mismatch():
    with pytest.raises(ValueError, match="equal length"):
        propagate_error([1.0], [0.1, 0.2])


# --- rolling_average ---


def test_rolling_average_full_window():
    result = rolling_average([1.0, 2.0, 3.0, 4.0], window=3)
    assert result == pytest.approx([1.0, 1.5, 2.0, 3.0])


def test_rolling_average_partial_prefix():
    result = rolling_average([4.0, 6.0], window=5)
    assert result == pytest.approx([4.0, 5.0])


def test_rolling_average_window_one():
    values = [3.0, 1.0, 2.0]
    assert rolling_average(values, window=1) == pytest.approx(values)


# --- trigger_point ---


def test_trigger_point_above_threshold():
    assert trigger_point(mb=50.0, population=100_000, threshold_per_100k=50.0) is True


def test_trigger_point_below_threshold():
    assert trigger_point(mb=49.9, population=100_000, threshold_per_100k=50.0) is False


def test_trigger_point_zero_population():
    with pytest.raises(ValueError, match="population"):
        trigger_point(mb=1.0, population=0, threshold_per_100k=1.0)


def test_trigger_point_negative_population():
    with pytest.raises(ValueError, match="population"):
        trigger_point(mb=1.0, population=-100, threshold_per_100k=1.0)
