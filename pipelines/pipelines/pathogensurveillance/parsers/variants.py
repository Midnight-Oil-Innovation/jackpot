"""
pathogensurveillance graphtyper VCF summariser.

graphtyper emits a per-sample VCF (gzipped or plain) under
``variants/graphtyper/<sample>.vcf[.gz]``.  Storing every variant call
in PostgreSQL would be wasteful — downstream surveillance work uses
only aggregate counts.  We therefore emit a single ``pipeline_metrics``
row per sample with:

* ``variant_count``           — total records in the VCF body
* ``filtered_variant_count``  — records whose FILTER column is not
  "PASS" (and not empty / ".")
* ``passed_variant_count``    — variant_count − filtered_variant_count
* ``source_file``             — relative path so the UI can link back

We count lines directly rather than pulling in pysam / cyvcf2 so the
parser is importable in minimal CI images.  Unsupported / binary .bcf
files are ignored (pathogensurveillance 1.1.0 emits text VCF only).
"""

from __future__ import annotations

import gzip
from dataclasses import dataclass
from pathlib import Path

from shared.parsers.types import ParsedResult, RunMetadata

RESULT_TYPE = "pipeline_metrics"
METRIC_GROUP = "graphtyper_variants"
_ACCEPTED_SUFFIXES = (".vcf", ".vcf.gz")


@dataclass(frozen=True)
class VcfSummary:
    sample_id: str
    variant_count: int
    passed_variant_count: int
    filtered_variant_count: int


def parse(variants_dir: Path, metadata: RunMetadata) -> list[ParsedResult]:  # noqa: ARG001
    if not variants_dir.exists():
        return []
    results: list[ParsedResult] = []
    for path in sorted(variants_dir.iterdir()):
        if not path.is_file():
            continue
        stem = _strip_vcf_suffix(path.name)
        if stem is None:
            continue
        summary = _summarise(path, sample_id=stem)
        payload = {
            "sample_id": summary.sample_id,
            "metric_group": METRIC_GROUP,
            "variant_count": summary.variant_count,
            "passed_variant_count": summary.passed_variant_count,
            "filtered_variant_count": summary.filtered_variant_count,
            "source_file": f"variants/graphtyper/{path.name}",
        }
        results.append(ParsedResult(result_type=RESULT_TYPE, payload=payload))
    return results


def _strip_vcf_suffix(name: str) -> str | None:
    for suffix in _ACCEPTED_SUFFIXES:
        if name.endswith(suffix):
            stem = name[: -len(suffix)]
            return stem or None
    return None


def _summarise(path: Path, *, sample_id: str) -> VcfSummary:
    opener = gzip.open if path.name.endswith(".gz") else open
    total = 0
    filtered = 0
    with opener(path, "rt") as f:
        for line in f:
            if not line or line.startswith("#"):
                continue
            total += 1
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 7:
                # Truncated record: don't let it crash the whole sample;
                # count as a variant but skip the PASS inspection.
                continue
            filt = cols[6].strip()
            if filt and filt != "PASS" and filt != ".":
                filtered += 1
    return VcfSummary(
        sample_id=sample_id,
        variant_count=total,
        passed_variant_count=total - filtered,
        filtered_variant_count=filtered,
    )
