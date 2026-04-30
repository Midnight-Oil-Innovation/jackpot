"""
viralrecon iVar variants TSV parser.

iVar emits one TSV per sample with PASS/FAIL rows.  We summarise the
per-sample variant call load into a single entry written to
``pipeline_results.metrics`` (JSONB) — the spec records per-variant
detail is surfaced through sample_files (the raw TSV), not a typed
result table.

The parser emits a single :class:`ParsedResult` with result_type
``pipeline_metrics`` — a sentinel value used by the wrapper's metrics
update path.  Because the backend does not yet expose a typed schema
for metrics, this payload shape is deliberately minimal and
documented here:

    {
        "sample_id": "AZ-WW-001",
        "variant_caller": "ivar",
        "total_variants": 57,
        "pass_variants": 52,
        "fail_variants": 5,
        "source_file": "variants/ivar/AZ-WW-001.tsv"
    }
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from shared.parsers.types import ParsedResult, RunMetadata

RESULT_TYPE = "pipeline_metrics"
REQUIRED_COLUMNS = frozenset({"REGION", "POS", "REF", "ALT", "PASS"})


@dataclass(frozen=True)
class IVarSummary:
    sample_id: str
    total_variants: int
    pass_variants: int
    fail_variants: int


def parse(path: Path, metadata: RunMetadata) -> list[ParsedResult]:  # noqa: ARG001
    if not path.exists():
        raise FileNotFoundError(f"iVar variants TSV not found: {path}")
    sample_id = _sample_id_from_path(path)
    summary = _summarise(path, sample_id=sample_id)
    payload = {
        "sample_id": sample_id,
        "variant_caller": "ivar",
        "total_variants": summary.total_variants,
        "pass_variants": summary.pass_variants,
        "fail_variants": summary.fail_variants,
        "source_file": f"variants/ivar/{path.name}",
    }
    return [ParsedResult(result_type=RESULT_TYPE, payload=payload)]


def _summarise(path: Path, *, sample_id: str) -> IVarSummary:
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"iVar TSV missing required columns: {sorted(missing)}",
            )
        total = 0
        passed = 0
        for row in reader:
            total += 1
            if (row.get("PASS") or "").strip().upper() == "TRUE":
                passed += 1
        return IVarSummary(
            sample_id=sample_id,
            total_variants=total,
            pass_variants=passed,
            fail_variants=total - passed,
        )


def _sample_id_from_path(path: Path) -> str:
    stem = path.name
    for suffix in (".tsv", ".ivar", ".variants"):
        while stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem
