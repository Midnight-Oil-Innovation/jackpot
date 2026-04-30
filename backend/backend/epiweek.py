from datetime import date

from epiweeks import Week


def compute_epiweeks(
    date_collected: date,
    precision: str = "day",
) -> dict[str, int | None]:
    """
    Compute CDC MMWR and ISO epiweeks. Called at ingest, before DB write.
    If precision is 'year' or 'month', all four values are None —
    epiweek cannot be reliably computed without day precision.
    """
    if precision in ("year", "month"):
        return {
            "mmwr_year": None,
            "mmwr_week": None,
            "iso_year": None,
            "iso_week": None,
        }
    mmwr = Week.fromdate(date_collected, system="CDC")
    iso = Week.fromdate(date_collected, system="ISO")
    return {
        "mmwr_year": mmwr.year,
        "mmwr_week": mmwr.week,
        "iso_year": iso.year,
        "iso_week": iso.week,
    }
