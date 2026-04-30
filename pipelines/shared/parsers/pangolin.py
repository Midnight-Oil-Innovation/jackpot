"""
Shared pangolin ``lineage_report.csv`` parser.

Used by both Cecret and viralrecon — their pangolin step emits the same
CSV layout. The parser takes the path to ``lineage_report.csv`` plus
:class:`RunMetadata` and returns one :class:`ParsedResult` per row,
validated against :class:`PangolinResult`.

Pangolin's CSV occasionally emits blank cells for numeric columns when
a score could not be computed; those are coerced to ``None`` rather
than rejected so real-world inputs round-trip cleanly.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..schemas import PangolinResult
from .types import ParsedResult, RunMetadata

RESULT_TYPE = "pangolin_results"
REQUIRED_COLUMNS = frozenset({"taxon", "lineage", "pangolin_version"})


class PangolinParseError(ValueError):
    """Raised when the lineage report is missing required columns."""


def parse(path: Path, metadata: RunMetadata) -> list[ParsedResult]:  # noqa: ARG001
    if not path.exists():
        raise FileNotFoundError(f"Pangolin report not found: {path}")
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise PangolinParseError(
                f"Pangolin report missing columns: {sorted(missing)}",
            )
        return [_parse_row(row) for row in reader if row.get("taxon")]


def _parse_row(row: dict[str, Any]) -> ParsedResult:
    model = PangolinResult(
        sample_id=row["taxon"],
        lineage=row["lineage"],
        conflict=_to_float(row.get("conflict")),
        ambiguity_score=_to_float(row.get("ambiguity_score")),
        scorpio_call=_blank_to_none(row.get("scorpio_call")),
        scorpio_support=_to_float(row.get("scorpio_support")),
        scorpio_conflict=_to_float(row.get("scorpio_conflict")),
        scorpio_notes=_blank_to_none(row.get("scorpio_notes")),
        pangolin_version=row["pangolin_version"],
        pangolin_data_version=_blank_to_none(
            row.get("pangolin_data_version") or row.get("version"),
        ),
        scorpio_version=_blank_to_none(row.get("scorpio_version")),
        constellation_version=_blank_to_none(row.get("constellation_version")),
        qc_status=_blank_to_none(row.get("qc_status")),
        qc_notes=_blank_to_none(row.get("qc_notes")),
        note=_blank_to_none(row.get("note")),
    )
    return ParsedResult.from_model(RESULT_TYPE, model)


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _to_float(value: str | None) -> float | None:
    cleaned = _blank_to_none(value)
    if cleaned is None:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None
