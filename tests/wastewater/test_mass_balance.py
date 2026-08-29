# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Tests for the plaintext wastewater mass-balance module.

Covers unit conversions, cryptWWDB Use Case 1 + Use Case 2 math,
non-detect handling per Hornung & Reed 1990, negative-mass-balance
handling per Bowes 2023b / Tempe 2023a, and the deferred DB-glue
stub. See ``backend/backend/wastewater/mass_balance.py``.
"""

from __future__ import annotations

import math
from datetime import datetime

import pytest

from backend.wastewater.mass_balance import (
    Concentration,
    ConcentrationUnit,
    FlowRate,
    FlowUnit,
    MassBalanceInputs,
    QualityFlag,
    compute_mass_load,
    compute_time_aware_mass_load,
    to_copies_per_l,
    to_l_per_day,
    to_ng_per_l,
)

# 1 US gallon = 3.785411784 L exactly; 1 MGD = 3,785,411.784 L/day.
_L_PER_DAY_FROM_MGD = 3_785_411.784


@pytest.mark.parametrize(
    "value,unit,expected_l_per_day",
    [
        (1.0, FlowUnit.L_PER_DAY, 1.0),
        (5.0, FlowUnit.L_PER_DAY, 5.0),
        (1.0, FlowUnit.M3_PER_DAY, 1_000.0),
        (2.5, FlowUnit.M3_PER_DAY, 2_500.0),
        (1.0, FlowUnit.L_PER_SEC, 86_400.0),
        (0.5, FlowUnit.L_PER_SEC, 43_200.0),
        (1.0, FlowUnit.MGD, _L_PER_DAY_FROM_MGD),
        (3.0, FlowUnit.MGD, 3 * _L_PER_DAY_FROM_MGD),
    ],
)
def test_to_l_per_day(value: float, unit: FlowUnit, expected_l_per_day: float) -> None:
    assert math.isclose(to_l_per_day(FlowRate(value, unit)), expected_l_per_day)


@pytest.mark.parametrize(
    "value,unit,expected_ng_per_l",
    [
        (1.0, ConcentrationUnit.NG_PER_L, 1.0),
        (42.0, ConcentrationUnit.NG_PER_L, 42.0),
        (1.0, ConcentrationUnit.UG_PER_L, 1_000.0),
        (2.5, ConcentrationUnit.UG_PER_L, 2_500.0),
        (1.0, ConcentrationUnit.MG_PER_L, 1_000_000.0),
        (0.5, ConcentrationUnit.MG_PER_L, 500_000.0),
    ],
)
def test_to_ng_per_l_mass_units(
    value: float, unit: ConcentrationUnit, expected_ng_per_l: float
) -> None:
    assert math.isclose(to_ng_per_l(Concentration(value, unit)), expected_ng_per_l)


@pytest.mark.parametrize(
    "unit",
    [ConcentrationUnit.COPIES_PER_ML, ConcentrationUnit.COPIES_PER_L],
)
def test_to_ng_per_l_raises_on_copies_unit(unit: ConcentrationUnit) -> None:
    with pytest.raises(ValueError, match="copies-based"):
        to_ng_per_l(Concentration(1.0, unit))


@pytest.mark.parametrize(
    "value,unit,expected_copies_per_l",
    [
        (1.0, ConcentrationUnit.COPIES_PER_L, 1.0),
        (42.0, ConcentrationUnit.COPIES_PER_L, 42.0),
        (1.0, ConcentrationUnit.COPIES_PER_ML, 1_000.0),
        (3.5, ConcentrationUnit.COPIES_PER_ML, 3_500.0),
    ],
)
def test_to_copies_per_l_copies_units(
    value: float, unit: ConcentrationUnit, expected_copies_per_l: float
) -> None:
    assert math.isclose(to_copies_per_l(Concentration(value, unit)), expected_copies_per_l)


@pytest.mark.parametrize(
    "unit",
    [
        ConcentrationUnit.NG_PER_L,
        ConcentrationUnit.UG_PER_L,
        ConcentrationUnit.MG_PER_L,
    ],
)
def test_to_copies_per_l_raises_on_mass_unit(unit: ConcentrationUnit) -> None:
    with pytest.raises(ValueError, match="mass-based"):
        to_copies_per_l(Concentration(1.0, unit))


def test_use_case_1_pathogen_copies_per_l() -> None:
    """Hand-computed pathogen case in canonical copies/L + L/day units."""
    inputs = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(100.0, ConcentrationUnit.COPIES_PER_L),
        downstream_flow=FlowRate(1500.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(200.0, ConcentrationUnit.COPIES_PER_L),
        target_pathogen_id="sars-cov-2",
    )
    # downstream load = 1500 * 200 = 300_000; upstream = 1000 * 100 = 100_000
    result = compute_mass_load(inputs)
    assert math.isclose(result.mass_load_value, 200_000.0)
    assert result.mass_load_unit == "copies/day"
    assert result.quality_flags == ()
    assert result.negative_mass_balance is False


def test_use_case_1_chemical_ng_per_l() -> None:
    """Hand-computed chemical mass case in canonical ng/L + L/day units."""
    inputs = MassBalanceInputs(
        upstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(10.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(2500.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(25.0, ConcentrationUnit.NG_PER_L),
    )
    # downstream = 2500 * 25 = 62_500; upstream = 2000 * 10 = 20_000
    result = compute_mass_load(inputs)
    assert math.isclose(result.mass_load_value, 42_500.0)
    assert result.mass_load_unit == "ng/day"
    assert result.quality_flags == ()


def test_use_case_1_mixed_units_mgd_and_ug_per_l() -> None:
    """Hand-computed chemical case with MGD flow + ug/L concentration."""
    inputs = MassBalanceInputs(
        upstream_flow=FlowRate(1.0, FlowUnit.MGD),
        upstream_concentration=Concentration(1.0, ConcentrationUnit.UG_PER_L),
        downstream_flow=FlowRate(2.0, FlowUnit.MGD),
        downstream_concentration=Concentration(2.0, ConcentrationUnit.UG_PER_L),
    )
    # upstream = 3_785_411.784 * 1_000 ng/L = 3_785_411_784 ng/day
    # downstream = 7_570_823.568 * 2_000 = 15_141_647_136 ng/day
    expected = 15_141_647_136.0 - 3_785_411_784.0
    result = compute_mass_load(inputs)
    assert math.isclose(result.mass_load_value, expected, rel_tol=1e-9)
    assert result.mass_load_unit == "ng/day"


def test_use_case_1_unit_incompatible_raises() -> None:
    inputs = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(10.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(10.0, ConcentrationUnit.COPIES_PER_L),
    )
    with pytest.raises(ValueError, match="both be mass-based"):
        compute_mass_load(inputs)


def test_use_case_2_time_aware_positive_delta() -> None:
    """Use Case 2 with the segment's contribution growing between t1 and t2."""
    t1 = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(10.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(50.0, ConcentrationUnit.NG_PER_L),
        timestamp=datetime(2026, 1, 1, 0, 0, 0),
    )
    t2 = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(20.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(80.0, ConcentrationUnit.NG_PER_L),
        timestamp=datetime(2026, 1, 8, 0, 0, 0),
    )
    # load_t1 = 100_000 - 10_000 = 90_000; load_t2 = 160_000 - 20_000 = 140_000
    result = compute_time_aware_mass_load(t1, t2)
    assert math.isclose(result.mass_load_value, 50_000.0)
    assert result.mass_load_unit == "ng/day"
    assert result.negative_mass_balance is False
    assert QualityFlag.NEGATIVE_MASS_BALANCE not in result.quality_flags


def test_use_case_2_time_aware_negative_delta_zero_handling() -> None:
    t1 = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(20.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(80.0, ConcentrationUnit.NG_PER_L),
    )
    t2 = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(10.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(50.0, ConcentrationUnit.NG_PER_L),
    )
    # load_t1 = 140_000; load_t2 = 90_000; delta = -50_000
    result = compute_time_aware_mass_load(t1, t2)
    assert result.mass_load_value == 0.0
    assert result.negative_mass_balance is True
    assert QualityFlag.NEGATIVE_MASS_BALANCE in result.quality_flags


def test_use_case_2_time_aware_negative_delta_raw_handling() -> None:
    t1 = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(20.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(80.0, ConcentrationUnit.NG_PER_L),
    )
    t2 = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(10.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(50.0, ConcentrationUnit.NG_PER_L),
    )
    result = compute_time_aware_mass_load(t1, t2, negative_handling="raw")
    assert math.isclose(result.mass_load_value, -50_000.0)
    assert result.negative_mass_balance is True


def test_use_case_2_time_aware_negative_delta_mdl_handling() -> None:
    t1 = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(20.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(80.0, ConcentrationUnit.NG_PER_L, lod=4.0),
    )
    t2 = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(10.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(50.0, ConcentrationUnit.NG_PER_L, lod=4.0),
    )
    # Negative delta. mdl = downstream_flow(t2) * lod/2 = 2000 * 2 = 4000.
    result = compute_time_aware_mass_load(t1, t2, negative_handling="mdl")
    assert math.isclose(result.mass_load_value, 4_000.0)
    assert result.negative_mass_balance is True


def test_use_case_2_time_aware_unit_mismatch_raises() -> None:
    t1 = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(10.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(50.0, ConcentrationUnit.NG_PER_L),
    )
    t2 = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(10.0, ConcentrationUnit.COPIES_PER_L),
        downstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(50.0, ConcentrationUnit.COPIES_PER_L),
    )
    with pytest.raises(ValueError, match="matching units"):
        compute_time_aware_mass_load(t1, t2)


def test_non_detect_upstream_with_lod_applies_mdl_substitution() -> None:
    inputs = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(0.0, ConcentrationUnit.NG_PER_L, lod=4.0),
        downstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(50.0, ConcentrationUnit.NG_PER_L),
    )
    # Substituted upstream c = 4/2 = 2 ng/L; up_load = 2000; down_load = 100_000
    result = compute_mass_load(inputs)
    assert math.isclose(result.mass_load_value, 98_000.0)
    assert QualityFlag.NON_DETECT_UPSTREAM in result.quality_flags
    assert QualityFlag.MISSING_DATA not in result.quality_flags


def test_non_detect_upstream_without_lod_flags_missing_data() -> None:
    inputs = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(0.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(50.0, ConcentrationUnit.NG_PER_L),
    )
    # Upstream load forced to 0; downstream = 100_000.
    result = compute_mass_load(inputs)
    assert math.isclose(result.mass_load_value, 100_000.0)
    assert QualityFlag.NON_DETECT_UPSTREAM in result.quality_flags
    assert QualityFlag.MISSING_DATA in result.quality_flags


def test_non_detect_downstream_with_lod_applies_mdl_substitution() -> None:
    inputs = MassBalanceInputs(
        upstream_flow=FlowRate(100.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(5.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(0.0, ConcentrationUnit.NG_PER_L, lod=4.0),
    )
    # Substituted downstream c = 2 ng/L; down_load = 2000; up_load = 500.
    result = compute_mass_load(inputs)
    assert math.isclose(result.mass_load_value, 1_500.0)
    assert QualityFlag.NON_DETECT_DOWNSTREAM in result.quality_flags
    assert result.negative_mass_balance is False


def test_below_lod_substitution_flags_below_lod() -> None:
    inputs = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(1.0, ConcentrationUnit.NG_PER_L, lod=5.0),
        downstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(20.0, ConcentrationUnit.NG_PER_L),
    )
    # value < lod → substitute lod/2 = 2.5 ng/L.
    # up_load = 1000 * 2.5 = 2500; down_load = 40_000; mass_load = 37_500.
    result = compute_mass_load(inputs)
    assert math.isclose(result.mass_load_value, 37_500.0)
    assert QualityFlag.BELOW_LOD_UPSTREAM in result.quality_flags
    assert QualityFlag.NON_DETECT_UPSTREAM not in result.quality_flags


def test_below_lod_substitution_downstream() -> None:
    inputs = MassBalanceInputs(
        upstream_flow=FlowRate(100.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(5.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(1.0, ConcentrationUnit.NG_PER_L, lod=6.0),
    )
    # Downstream substituted to 3 ng/L; down_load = 6000; up_load = 500;
    # mass_load = 5500 ng/day.
    result = compute_mass_load(inputs)
    assert math.isclose(result.mass_load_value, 5_500.0)
    assert QualityFlag.BELOW_LOD_DOWNSTREAM in result.quality_flags


def _make_negative_mass_balance_inputs(*, downstream_lod: float | None = None) -> MassBalanceInputs:
    return MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(100.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(
            10.0, ConcentrationUnit.NG_PER_L, lod=downstream_lod
        ),
    )


def test_negative_mass_balance_zero_handling_clamps_to_zero() -> None:
    # up_load = 100_000, down_load = 10_000, raw = -90_000.
    result = compute_mass_load(_make_negative_mass_balance_inputs(), negative_handling="zero")
    assert result.mass_load_value == 0.0
    assert result.negative_mass_balance is True
    assert QualityFlag.NEGATIVE_MASS_BALANCE in result.quality_flags


def test_negative_mass_balance_mdl_handling_uses_downstream_lod() -> None:
    # Downstream lod = 5; mdl_load = 1000 * (5/2) = 2500 ng/day.
    inputs = _make_negative_mass_balance_inputs(downstream_lod=5.0)
    result = compute_mass_load(inputs, negative_handling="mdl")
    assert math.isclose(result.mass_load_value, 2_500.0)
    assert result.negative_mass_balance is True
    assert QualityFlag.NEGATIVE_MASS_BALANCE in result.quality_flags


def test_negative_mass_balance_mdl_handling_without_lod_flags_missing_data() -> None:
    inputs = _make_negative_mass_balance_inputs(downstream_lod=None)
    result = compute_mass_load(inputs, negative_handling="mdl")
    assert result.mass_load_value == 0.0
    assert result.negative_mass_balance is True
    assert QualityFlag.NEGATIVE_MASS_BALANCE in result.quality_flags
    assert QualityFlag.MISSING_DATA in result.quality_flags


def test_negative_mass_balance_raw_handling_preserves_raw() -> None:
    inputs = _make_negative_mass_balance_inputs()
    result = compute_mass_load(inputs, negative_handling="raw")
    assert math.isclose(result.mass_load_value, -90_000.0)
    assert result.negative_mass_balance is True


def test_negative_mass_balance_unknown_handling_raises() -> None:
    inputs = _make_negative_mass_balance_inputs()
    with pytest.raises(ValueError, match="Unknown negative_handling"):
        compute_mass_load(inputs, negative_handling="bogus")  # type: ignore[arg-type]


def test_missing_target_pathogen_id_is_not_an_error() -> None:
    inputs = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(100.0, ConcentrationUnit.COPIES_PER_L),
        downstream_flow=FlowRate(1500.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(200.0, ConcentrationUnit.COPIES_PER_L),
        target_pathogen_id=None,
    )
    result = compute_mass_load(inputs)
    assert math.isclose(result.mass_load_value, 200_000.0)
    assert result.quality_flags == ()


def test_zero_upstream_flow_returns_zero_with_missing_data() -> None:
    inputs = MassBalanceInputs(
        upstream_flow=FlowRate(0.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(10.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(50.0, ConcentrationUnit.NG_PER_L),
    )
    result = compute_mass_load(inputs)
    assert result.mass_load_value == 0.0
    assert QualityFlag.MISSING_DATA in result.quality_flags
    assert result.negative_mass_balance is False


def test_zero_downstream_flow_returns_zero_with_missing_data() -> None:
    inputs = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(10.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(0.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(50.0, ConcentrationUnit.NG_PER_L),
    )
    result = compute_mass_load(inputs)
    assert result.mass_load_value == 0.0
    assert QualityFlag.MISSING_DATA in result.quality_flags


def test_pathogen_below_lod_with_copies_per_ml_unit_substitutes() -> None:
    """Exercises the copies-unit branch of the canonical-factor helper.

    Pathogen concentration in copies/mL with an LOD set; the value is below
    the LOD so the LOD/2 substitution path runs against the copies-unit
    conversion factor.
    """
    inputs = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(0.5, ConcentrationUnit.COPIES_PER_ML, lod=2.0),
        downstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(10.0, ConcentrationUnit.COPIES_PER_ML),
    )
    # Upstream canonical = 0.5 * 1000 = 500 copies/L; lod canonical = 2000;
    # 500 < 2000 -> substitute 1000 copies/L.
    # up_load = 1000 * 1000 = 1_000_000; down_load = 2000 * (10 * 1000) = 20_000_000.
    result = compute_mass_load(inputs)
    assert math.isclose(result.mass_load_value, 19_000_000.0)
    assert QualityFlag.BELOW_LOD_UPSTREAM in result.quality_flags
    assert result.mass_load_unit == "copies/day"


def test_time_aware_merges_per_endpoint_flags() -> None:
    """The merged-flag loop should carry per-timestamp flags into the result."""
    t1 = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(0.0, ConcentrationUnit.NG_PER_L, lod=4.0),
        downstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(50.0, ConcentrationUnit.NG_PER_L),
    )
    t2 = MassBalanceInputs(
        upstream_flow=FlowRate(1000.0, FlowUnit.L_PER_DAY),
        upstream_concentration=Concentration(10.0, ConcentrationUnit.NG_PER_L),
        downstream_flow=FlowRate(2000.0, FlowUnit.L_PER_DAY),
        downstream_concentration=Concentration(60.0, ConcentrationUnit.NG_PER_L),
    )
    result = compute_time_aware_mass_load(t1, t2)
    assert QualityFlag.NON_DETECT_UPSTREAM in result.quality_flags
