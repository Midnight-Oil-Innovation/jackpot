"""
nf-core/mag pipeline-level parser.

Expected layout (nf-core/mag 2.x–3.x)::

    <output>/
    ├── GenomeBinning/
    │   ├── MetaBAT2/bins/<bin>.fa[.gz]
    │   ├── MaxBin2/bins/<bin>.fa[.gz]
    │   └── DAS_Tool/bins/<bin>.fa[.gz]
    ├── CheckM2/checkm2_quality_report.tsv     (aggregated across bins)
    └── Taxonomy/GTDB-Tk/
        ├── gtdbtk.bac120.summary.tsv
        └── gtdbtk.ar53.summary.tsv

The parser is intentionally flexible about exact subdirectory names so
future nf-core/mag versions that reshuffle output paths don't require
per-version special-casing — the invariants we rely on are the file
name conventions, not the directory tree.
"""

from __future__ import annotations

from pathlib import Path

from shared.parsers import FileArtifact, ParsedResult, RunMetadata

from . import bin_registry, checkm2, gtdbtk

SUPPORTED_PIPELINE_VERSIONS: list[str] = [
    "2.5.4",
    "3.0.0",
    "3.0.3",
    "3.1.0",
]


def parse(
    output_dir: Path,
    metadata: RunMetadata,
) -> list[ParsedResult]:
    """Run every sub-parser; concatenate ParsedResults in a stable order."""
    results: list[ParsedResult] = []
    results.extend(checkm2.parse(output_dir, metadata))
    results.extend(gtdbtk.parse(output_dir, metadata))
    return results


def collect_files(output_dir: Path, metadata: RunMetadata) -> list[FileArtifact]:
    """Register every MAG bin FASTA as a ``sample_files`` entry."""
    return bin_registry.collect(output_dir, metadata)


__all__ = [
    "SUPPORTED_PIPELINE_VERSIONS",
    "bin_registry",
    "checkm2",
    "collect_files",
    "gtdbtk",
    "parse",
]
