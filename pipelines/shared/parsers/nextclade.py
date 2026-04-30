"""
Shared nextclade ``nextclade.tsv`` parser.

Cecret and viralrecon both run Nextclade and emit the standard TSV.
The TSV does not include the Nextclade software version — it must
come from :class:`RunMetadata` or a sibling ``nextclade.version.txt``
file (``cecret`` writes one; ``viralrecon`` does not).

Nextclade emits mutation lists as comma-separated strings; we split
them into Python lists for the ``substitutions`` / ``aa_substitutions``
fields so downstream consumers don't re-parse.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..schemas import NextcladeResult
from .types import ParsedResult, RunMetadata

RESULT_TYPE = "nextclade_results"
REQUIRED_COLUMNS = frozenset({"seqName"})


class NextcladeParseError(ValueError):
    """Raised when the nextclade TSV is missing required columns."""


def parse(
    path: Path,
    metadata: RunMetadata,
    *,
    nextclade_version: str | None = None,
    dataset_name: str | None = None,
    dataset_version: str | None = None,
) -> list[ParsedResult]:
    if not path.exists():
        raise FileNotFoundError(f"Nextclade TSV not found: {path}")
    version = nextclade_version or _read_sibling_version(path) or metadata.pipeline_version
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise NextcladeParseError(
                f"Nextclade TSV missing columns: {sorted(missing)}",
            )
        results: list[ParsedResult] = []
        for row in reader:
            sample_id = (row.get("seqName") or "").strip()
            if not sample_id:
                continue
            results.append(
                _parse_row(
                    row,
                    sample_id=sample_id,
                    nextclade_version=version,
                    dataset_name=dataset_name,
                    dataset_version=dataset_version,
                )
            )
    return results


def _parse_row(
    row: dict[str, str],
    *,
    sample_id: str,
    nextclade_version: str,
    dataset_name: str | None,
    dataset_version: str | None,
) -> ParsedResult:
    model = NextcladeResult(
        sample_id=sample_id,
        clade=_blank_to_none(row.get("clade")),
        nextclade_pango=_blank_to_none(
            row.get("Nextclade_pango") or row.get("nextclade_pango"),
        ),
        qc_overall_status=_blank_to_none(row.get("qc.overallStatus")),
        qc_overall_score=_to_float(row.get("qc.overallScore")),
        total_substitutions=_to_int(row.get("totalSubstitutions")),
        total_deletions=_to_int(row.get("totalDeletions")),
        total_insertions=_to_int(row.get("totalInsertions")),
        total_missing=_to_int(row.get("totalMissing")),
        total_non_acgtns=_to_int(row.get("totalNonACGTNs")),
        total_frame_shifts=_to_int(row.get("totalFrameShifts")),
        substitutions=_split_list(row.get("substitutions")),
        aa_substitutions=_split_list(row.get("aaSubstitutions")),
        nextclade_version=nextclade_version,
        dataset_name=dataset_name,
        dataset_version=dataset_version,
    )
    return ParsedResult.from_model(RESULT_TYPE, model)


def _read_sibling_version(tsv_path: Path) -> str | None:
    candidate = tsv_path.parent / "nextclade.version.txt"
    if candidate.exists():
        text = candidate.read_text().strip()
        return text or None
    return None


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


def _to_int(value: str | None) -> int | None:
    cleaned = _blank_to_none(value)
    if cleaned is None:
        return None
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def _split_list(value: str | None) -> list[str] | None:
    cleaned = _blank_to_none(value)
    if cleaned is None:
        return None
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    return parts or None
