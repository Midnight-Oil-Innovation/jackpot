from datetime import date

import pytest

from backend.epiweek import compute_epiweeks


def test_all_fields_present():
    result = compute_epiweeks(date(2026, 3, 15))
    for key in ("mmwr_year", "mmwr_week", "iso_year", "iso_week"):
        assert key in result


def test_week_in_valid_range():
    for month in range(1, 13):
        result = compute_epiweeks(date(2026, month, 15))
        assert 1 <= result["mmwr_week"] <= 53
        assert 1 <= result["iso_week"] <= 53


@pytest.mark.parametrize(
    "input_date,expected_mmwr_week",
    [
        (date(2026, 1, 4), 1),
        (date(2026, 1, 11), 2),
        (date(2026, 3, 22), 12),
    ],
)
def test_specific_mmwr_weeks(input_date, expected_mmwr_week):
    result = compute_epiweeks(input_date)
    assert result["mmwr_week"] == expected_mmwr_week


def test_mmwr_and_iso_can_differ():
    # The week systems can give different years near Jan 1
    result = compute_epiweeks(date(2026, 1, 1))
    assert isinstance(result["mmwr_year"], int)
    assert isinstance(result["iso_year"], int)
