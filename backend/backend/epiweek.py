from datetime import date

from epiweeks import Week


def compute_epiweeks(collection_date: date) -> dict[str, int]:
    """Compute CDC MMWR and ISO epiweeks. Called at ingest, before DB write."""
    mmwr = Week.fromdate(collection_date, system="CDC")
    iso = Week.fromdate(collection_date, system="ISO")
    return {
        "mmwr_year": mmwr.year,
        "mmwr_week": mmwr.week,
        "iso_year": iso.year,
        "iso_week": iso.week,
    }
