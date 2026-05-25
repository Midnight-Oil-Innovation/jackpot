from backend.privacy.coarsening import Coarsener, CoarseningPolicy


def _coarsen(granularity: str, date_str: str | None) -> str | None:
    return Coarsener(CoarseningPolicy(date_granularity=granularity)).coarsen_date(date_str)


def test_week_granularity_buckets_by_iso_week_not_month():
    """'week' must produce ISO-week buckets, not silently degrade to month."""
    # Two dates in the same calendar month but different ISO weeks.
    same_month_diff_week_a = _coarsen("week", "2024-03-04")  # Mon, ISO week
    same_month_diff_week_b = _coarsen("week", "2024-03-11")  # following Mon

    assert same_month_diff_week_a is not None
    assert "-W" in same_month_diff_week_a  # YYYY-Www, not YYYY-MM
    # Distinct weeks within the same month must not collapse together.
    assert same_month_diff_week_a != same_month_diff_week_b


def test_week_granularity_groups_same_iso_week():
    """Dates in the same ISO week share a bucket."""
    monday = _coarsen("week", "2024-03-04")
    friday = _coarsen("week", "2024-03-08")
    assert monday == friday


def test_month_and_day_granularity_unchanged():
    assert _coarsen("month", "2024-03-08") == "2024-03"
    assert _coarsen("day", "2024-03-08") == "2024-03-08"


def test_week_granularity_falls_back_on_unparseable_date():
    assert _coarsen("week", "garbage") == "garbage"[:7]


def test_coarsen_date_none_passthrough():
    assert _coarsen("week", None) is None
