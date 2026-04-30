"""
Freyja ``aggregated-freyja.tsv`` parser.

Freyja's ``aggregate`` command writes one TSV row per wastewater
sample.  The first column (unnamed in the header) holds the per-sample
input filename (e.g. ``AZ-WW-001.freyja.tsv``); ``lineages`` and
``abundances`` are space-separated strings of equal length that we
explode into one :class:`WastewaterLineageAbundance` per lineage.

Abundances below 1e-6 are dropped — Freyja rounds sub-resolution
components to zero which would violate ``ge=0`` checks only if
the exported value were negative, but near-zero noise lineages add
no analytical value and bloat the ``wastewater_lineage_abundance``
table.
"""

from __future__ import annotations

import csv
from pathlib import Path

from shared.parsers.types import ParsedResult, RunMetadata
from shared.schemas import WastewaterLineageAbundance

RESULT_TYPE = "wastewater_lineage_abundance"
TOOL_NAME = "freyja"
ABUNDANCE_FLOOR = 1e-6


class FreyjaParseError(ValueError):
    """Raised when an aggregated-freyja row cannot be interpreted."""


def parse(
    path: Path,
    metadata: RunMetadata,
    *,
    tool_version: str | None = None,
    barcode_version: str | None = None,
) -> list[ParsedResult]:
    if not path.exists():
        raise FileNotFoundError(f"Freyja aggregated TSV not found: {path}")
    version = tool_version or metadata.pipeline_version
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fieldnames = reader.fieldnames or []
        if "lineages" not in fieldnames or "abundances" not in fieldnames:
            raise FreyjaParseError(
                f"aggregated-freyja.tsv missing required columns: {fieldnames}",
            )
        sample_col = _sample_column(fieldnames)
        results: list[ParsedResult] = []
        for row in reader:
            sample_id = _sample_id_from_row(row, sample_col)
            if not sample_id:
                continue
            results.extend(
                _explode_row(
                    row,
                    sample_id=sample_id,
                    tool_version=version,
                    barcode_version=barcode_version,
                ),
            )
    return results


def _sample_column(fieldnames: list[str]) -> str:
    # Freyja writes the sample filename under the first column which is
    # typically unnamed ('') — fall back to the first field regardless.
    return fieldnames[0]


def _sample_id_from_row(row: dict[str, str], sample_col: str) -> str | None:
    raw = (row.get(sample_col) or "").strip()
    if not raw:
        return None
    stem = Path(raw).name
    for suffix in (".freyja.tsv", ".tsv", ".freyja"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem or None


def _explode_row(
    row: dict[str, str],
    *,
    sample_id: str,
    tool_version: str,
    barcode_version: str | None,
) -> list[ParsedResult]:
    lineages = (row.get("lineages") or "").split()
    abundances_raw = (row.get("abundances") or "").split()
    if len(lineages) != len(abundances_raw):
        raise FreyjaParseError(
            f"lineages / abundances length mismatch for sample {sample_id}: "
            f"{len(lineages)} vs {len(abundances_raw)}",
        )
    coverage = _to_float(row.get("coverage"))
    results: list[ParsedResult] = []
    for lineage, raw_abundance in zip(lineages, abundances_raw, strict=False):
        abundance = _to_float(raw_abundance)
        if abundance is None or abundance < ABUNDANCE_FLOOR:
            continue
        if abundance > 1.0:
            abundance = 1.0
        model = WastewaterLineageAbundance(
            sample_id=sample_id,
            lineage=lineage,
            abundance=abundance,
            coverage_depth=coverage,
            tool_name=TOOL_NAME,
            tool_version=tool_version,
            barcode_version=barcode_version,
        )
        results.append(ParsedResult.from_model(RESULT_TYPE, model))
    return results


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError:
        return None
