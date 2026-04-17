"""
pathogensurveillance reference-selection parser.

nf-core/pathogensurveillance auto-picks a reference genome per sample
(from the sendsketch hit or a pre-approved curated set) and records
the choice in ``reference_selection/<sample>.reference.tsv`` (or
``.selected.tsv`` depending on the minor release).  Two layouts are
observed in 1.1.0:

    # layout A — key/value pairs, no header
    reference_accession\tGCF_000005845.2
    reference_name\tEscherichia coli K-12 MG1655
    reference_source\tRefSeq

    # layout B — header + single data row
    reference_accession\treference_name\treference_source
    GCF_000005845.2\tEscherichia coli K-12 MG1655\tRefSeq

We emit a single ``pipeline_metrics`` row per sample with the
``reference_selection`` metric group.  Capturing this in a structured
metric (rather than a JSONB blob on the run) makes the "which reference
was used for sample X" question answerable via a plain SELECT —
required by the Session M reproducibility guarantee.
"""

from __future__ import annotations

import csv
from pathlib import Path

from shared.parsers.types import ParsedResult, RunMetadata

RESULT_TYPE = "pipeline_metrics"
METRIC_GROUP = "reference_selection"
_ACCEPTED_SUFFIXES = (".reference.tsv", ".selected.tsv", ".reference.txt")
_FIELDS = {"reference_accession", "reference_name", "reference_source"}


def parse(reference_dir: Path, metadata: RunMetadata) -> list[ParsedResult]:  # noqa: ARG001
    if not reference_dir.exists():
        return []
    results: list[ParsedResult] = []
    for path in sorted(reference_dir.iterdir()):
        if not path.is_file():
            continue
        sample_id = _sample_id(path.name)
        if sample_id is None:
            continue
        fields = _parse_fields(path)
        if not fields:
            continue
        payload = {
            "sample_id": sample_id,
            "metric_group": METRIC_GROUP,
            "source_file": f"reference_selection/{path.name}",
            **fields,
        }
        results.append(ParsedResult(result_type=RESULT_TYPE, payload=payload))
    return results


def _sample_id(filename: str) -> str | None:
    for suffix in _ACCEPTED_SUFFIXES:
        if filename.endswith(suffix):
            stem = filename[: -len(suffix)]
            return stem or None
    return None


def _parse_fields(path: Path) -> dict[str, str]:
    """Parse either layout A (key/value rows) or B (header + row)."""
    with path.open(newline="") as f:
        rows = [row for row in csv.reader(f, delimiter="\t") if row]
    if not rows:
        return {}
    # Layout B — header + data row.  Distinguished from layout A by having
    # ≥ 2 cells in the first row *all* of which are _FIELDS keys.  Layout A
    # has key/value pairs where the second cell is a free-form value that
    # is never in _FIELDS.
    first = [c.strip() for c in rows[0]]
    if len(first) >= 2 and all(c in _FIELDS for c in first) and len(rows) >= 2:
        values = [c.strip() for c in rows[1]]
        mapped = dict(zip(first, values, strict=False))
        return {k: v for k, v in mapped.items() if k in _FIELDS and v}
    # Layout A — key/value two-column rows.
    mapped: dict[str, str] = {}
    for row in rows:
        if len(row) < 2:
            continue
        key = row[0].strip()
        value = row[1].strip()
        if key in _FIELDS and value:
            mapped[key] = value
    return mapped
