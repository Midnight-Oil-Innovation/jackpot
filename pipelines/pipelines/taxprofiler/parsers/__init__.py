"""
nf-core/taxprofiler pipeline-level parser.

taxprofiler emits per-classifier subdirectories — we target Kraken2,
Bracken, and DIAMOND.  Each classifier / database combination gets its
own output file named ``<sample>_<database>.<classifier>.<ext>`` or
similar; the parser discovers them by suffix rather than by hard-coded
database name.

Expected layout (taxprofiler 1.x)::

    <output>/
    ├── kraken2/<sample>_<db>.kraken2.kraken2.report.txt
    ├── bracken/<sample>_<db>.bracken.tsv
    └── diamond/<sample>_<db>.diamond.tsv

taxprofiler is a cohort pipeline — the parent metagenomic sample
stays the ``sample_id`` on every emitted row.  No derived samples are
created (contrast with nf-core/mag, which fans out into MAG bins).
"""

from __future__ import annotations

from pathlib import Path

from shared.parsers import ParsedResult, RunMetadata

from . import bracken, diamond, kraken2

SUPPORTED_PIPELINE_VERSIONS: list[str] = [
    "1.1.5",
    "1.1.6",
    "1.2.0",
]


def parse(output_dir: Path, metadata: RunMetadata) -> list[ParsedResult]:
    results: list[ParsedResult] = []
    kraken_dir = output_dir / "kraken2"
    if kraken_dir.exists():
        results.extend(kraken2.parse(kraken_dir, metadata))
    bracken_dir = output_dir / "bracken"
    if bracken_dir.exists():
        results.extend(bracken.parse(bracken_dir, metadata))
    diamond_dir = output_dir / "diamond"
    if diamond_dir.exists():
        results.extend(diamond.parse(diamond_dir, metadata))
    return results


def collect_files(output_dir: Path, metadata: RunMetadata) -> list:  # noqa: ARG001
    """taxprofiler produces no registrable FileArtifact outputs."""
    return []


__all__ = [
    "SUPPORTED_PIPELINE_VERSIONS",
    "bracken",
    "collect_files",
    "diamond",
    "kraken2",
    "parse",
]
