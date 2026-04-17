"""
mycosnp Snippy variants parser.

mycosnp runs Snippy per sample and produces a summary TXT ::

    snippy/<sample>/<sample>.txt

with content like::

    DateTime    2026-04-17T00:00:00
    Reference   CandidaAurisB11205
    Software    snippy 4.6.0
    Variant-COMPLEX 12
    Variant-DEL     8
    Variant-INS     5
    Variant-MNP     3
    Variant-SNP     241
    VariantTotal    269

We emit one ``pipeline_metrics`` ParsedResult per sample summarising
the variant counts.  The raw VCF is registered separately through
``sample_files`` by the mycosnp wrapper.
"""

from __future__ import annotations

from pathlib import Path

from shared.parsers.types import ParsedResult, RunMetadata

RESULT_TYPE = "pipeline_metrics"
_SUMMARY_SUFFIX = ".txt"
_COUNT_KEYS = {
    "Variant-SNP": "snp_count",
    "Variant-INS": "insertion_count",
    "Variant-DEL": "deletion_count",
    "Variant-MNP": "mnp_count",
    "Variant-COMPLEX": "complex_count",
    "VariantTotal": "total_variants",
}


def parse(snippy_dir: Path, metadata: RunMetadata) -> list[ParsedResult]:  # noqa: ARG001
    if not snippy_dir.exists():
        return []
    results: list[ParsedResult] = []
    for sample_dir in sorted(snippy_dir.iterdir()):
        if not sample_dir.is_dir():
            continue
        summary = sample_dir / f"{sample_dir.name}{_SUMMARY_SUFFIX}"
        if not summary.is_file():
            # Fall back to a plain "summary.txt" if the per-sample name is absent.
            summary = sample_dir / "summary.txt"
            if not summary.is_file():
                continue
        payload = _parse_summary(summary, sample_id=sample_dir.name)
        results.append(ParsedResult(result_type=RESULT_TYPE, payload=payload))
    return results


def _parse_summary(path: Path, *, sample_id: str) -> dict:
    fields: dict[str, object] = {
        "sample_id": sample_id,
        "metric_group": "snippy",
        "source_file": f"snippy/{sample_id}/{path.name}",
    }
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        key = parts[0]
        if key == "Reference":
            fields["reference"] = parts[1]
        elif key == "Software":
            fields["software"] = " ".join(parts[1:])
        elif key in _COUNT_KEYS:
            try:
                fields[_COUNT_KEYS[key]] = int(parts[1])
            except ValueError:
                continue
    return fields
