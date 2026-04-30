"""
IRMA typing summary parser for walkercreek.

walkercreek aggregates IRMA's per-sample subtype calls into a single
typing summary file.  The layout is stable across 1.0–1.2:

    sample_id\tsubtype\tclade\tirma_version\tscheme

Emits one :class:`TypingResult` per row.  ``scheme`` is the typing
scheme name (``h1n1pdm09``, ``h3n2``, ``flub_victoria``, ``rsv_a``,
etc.); ``sequence_type`` carries the IRMA subtype string.

Both TSV and CSV are accepted — walkercreek 1.0 emitted CSV, 1.1+
switched to TSV.
"""

from __future__ import annotations

import csv
from pathlib import Path

from shared.parsers.types import ParsedResult, RunMetadata
from shared.schemas import TypingResult

RESULT_TYPE = "typing_results"
REQUIRED_COLUMNS = frozenset({"sample_id", "subtype"})


class IRMAParseError(ValueError):
    """Raised when the typing summary is missing required columns."""


def parse(path: Path, metadata: RunMetadata) -> list[ParsedResult]:
    if not path.exists():
        raise FileNotFoundError(f"walkercreek typing summary not found: {path}")
    delimiter = _detect_delimiter(path)
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise IRMAParseError(
                f"walkercreek typing summary missing columns: {sorted(missing)}",
            )
        results: list[ParsedResult] = []
        for row in reader:
            sample_id = (row.get("sample_id") or "").strip()
            if not sample_id:
                continue
            results.append(_parse_row(row, sample_id=sample_id, metadata=metadata))
    return results


def _parse_row(row: dict[str, str], *, sample_id: str, metadata: RunMetadata) -> ParsedResult:
    scheme = _blank_to_none(row.get("scheme")) or _default_scheme(row.get("subtype", ""))
    tool_version = _blank_to_none(row.get("irma_version")) or metadata.pipeline_version
    model = TypingResult(
        sample_id=sample_id,
        scheme=scheme,
        scheme_version=_blank_to_none(row.get("scheme_version")),
        sequence_type=_blank_to_none(row.get("subtype")),
        clade=_blank_to_none(row.get("clade")),
        tool_name="irma",
        tool_version=tool_version,
    )
    return ParsedResult.from_model(RESULT_TYPE, model)


def _detect_delimiter(path: Path) -> str:
    with path.open() as f:
        header = f.readline()
    if "\t" in header:
        return "\t"
    return ","


def _default_scheme(subtype: str) -> str:
    subtype = subtype.strip().lower()
    if not subtype:
        return "irma"
    if "h1" in subtype:
        return "h1n1"
    if "h3" in subtype:
        return "h3n2"
    if "hb" in subtype or "victoria" in subtype or "yamagata" in subtype:
        return "flub"
    if "rsv" in subtype:
        return "rsv"
    return "irma"


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
