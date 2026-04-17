"""
viralrecon parsers — orchestrates pangolin, nextclade, variants, freyja.

viralrecon (``nf-core/viralrecon``) writes per-caller subdirectories
under a top-level ``variants/`` / ``consensus/`` hierarchy.  We look
for the canonical locations produced by the default configuration:

* ``pangolin/*.pangolin.csv``  (per-sample, same schema as Cecret's aggregated)
* ``nextclade/*.nextclade.tsv``   (per-sample)
* ``variants/ivar/*.tsv``         (per-sample iVar calls)
* ``consensus/bcftools/*.consensus.fa.gz``   (per-sample)
* ``variants/ivar/freyja/*-aggregate.tsv``    (wastewater mode only)

Pangolin / nextclade files are scanned as a group and concatenated so
the shared parsers can iterate row-by-row regardless of whether the
upstream pipeline aggregated the per-sample outputs.
"""

from __future__ import annotations

from pathlib import Path

from shared.parsers import FileArtifact, ParsedResult, RunMetadata
from shared.parsers import nextclade as shared_nextclade
from shared.parsers import pangolin as shared_pangolin

from . import consensus, freyja, variants

SUPPORTED_PIPELINE_VERSIONS: list[str] = [
    "2.5",
    "2.6",
    "2.6.0",
    "2.6.1",
    "2.7",
    "2.7.0",
]


def parse(output_dir: Path, metadata: RunMetadata) -> list[ParsedResult]:
    results: list[ParsedResult] = []

    for report in sorted(_iter_pangolin_reports(output_dir)):
        results.extend(shared_pangolin.parse(report, metadata))

    for tsv in sorted(_iter_nextclade_tsvs(output_dir)):
        results.extend(shared_nextclade.parse(tsv, metadata))

    for ivar_tsv in sorted(_iter_ivar_variants(output_dir)):
        results.extend(variants.parse(ivar_tsv, metadata))

    freyja_tsv = _find_freyja_aggregate(output_dir)
    if freyja_tsv is not None:
        results.extend(freyja.parse(freyja_tsv, metadata))

    return results


def collect_files(output_dir: Path, metadata: RunMetadata) -> list[FileArtifact]:
    artifacts: list[FileArtifact] = []
    for consensus_dir in _iter_consensus_dirs(output_dir):
        artifacts.extend(consensus.collect(consensus_dir, metadata))
    return artifacts


def _iter_pangolin_reports(output_dir: Path):
    pangolin_dir = output_dir / "pangolin"
    if not pangolin_dir.exists():
        return []
    # Accept either aggregated lineage_report.csv or per-sample *.pangolin.csv
    aggregated = pangolin_dir / "lineage_report.csv"
    if aggregated.exists():
        return [aggregated]
    return list(pangolin_dir.glob("*.pangolin.csv"))


def _iter_nextclade_tsvs(output_dir: Path):
    nc_dir = output_dir / "nextclade"
    if not nc_dir.exists():
        return []
    aggregated = nc_dir / "nextclade.tsv"
    if aggregated.exists():
        return [aggregated]
    return list(nc_dir.glob("*.nextclade.tsv"))


def _iter_ivar_variants(output_dir: Path):
    variants_dir = output_dir / "variants" / "ivar"
    if not variants_dir.exists():
        return []
    return [p for p in variants_dir.glob("*.tsv") if not p.name.endswith("summary.tsv")]


def _find_freyja_aggregate(output_dir: Path) -> Path | None:
    # viralrecon wastewater mode lands freyja results under a nested
    # `variants/ivar/freyja/` directory.
    for candidate in (
        output_dir / "variants" / "ivar" / "freyja" / "aggregated-freyja.tsv",
        output_dir / "freyja" / "aggregated-freyja.tsv",
    ):
        if candidate.exists():
            return candidate
    return None


def _iter_consensus_dirs(output_dir: Path):
    # Both bcftools- and ivar-consensus layouts
    candidates = [
        output_dir / "consensus" / "bcftools",
        output_dir / "consensus" / "ivar",
        output_dir / "consensus",
    ]
    return [c for c in candidates if c.exists()]


__all__ = [
    "SUPPORTED_PIPELINE_VERSIONS",
    "collect_files",
    "consensus",
    "freyja",
    "parse",
    "variants",
]
