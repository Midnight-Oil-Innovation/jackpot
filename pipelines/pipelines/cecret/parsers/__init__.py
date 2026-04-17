"""
Cecret parsers — orchestrates the individual file parsers.

Cecret (``UPHL-BioNGS/Cecret``) writes one directory per analysis step.
The pipeline-level :func:`parse` walks those directories in a fixed
order:

1. ``pangolin/lineage_report.csv``   → ``pangolin_results``
2. ``nextclade/nextclade.tsv``       → ``nextclade_results``
3. ``freyja/aggregated-freyja.tsv``  → ``wastewater_lineage_abundance``
   (only present for wastewater runs)

``collect_files`` returns the FASTA artifacts separately because they
are registered through a different transport (``sample_files``).
"""

from __future__ import annotations

from pathlib import Path

from shared.parsers import FileArtifact, ParsedResult, RunMetadata
from shared.parsers import nextclade as shared_nextclade
from shared.parsers import pangolin as shared_pangolin

from . import consensus, freyja

SUPPORTED_PIPELINE_VERSIONS: list[str] = [
    "3.6",
    "3.7",
    "3.8",
    "3.9",
    "3.10",
    "3.11",
    "3.12",
    "3.13",
    "3.14",
    "3.15",
    "3.16",
    "3.20",
    "3.30",
    "3.40",
    "3.50",
    "3.60",
    "3.66",
]


def parse(output_dir: Path, metadata: RunMetadata) -> list[ParsedResult]:
    """Run every applicable sub-parser; concatenate their ParsedResults."""
    results: list[ParsedResult] = []

    pangolin_report = output_dir / "pangolin" / "lineage_report.csv"
    if pangolin_report.exists():
        results.extend(shared_pangolin.parse(pangolin_report, metadata))

    nextclade_tsv = output_dir / "nextclade" / "nextclade.tsv"
    if nextclade_tsv.exists():
        results.extend(shared_nextclade.parse(nextclade_tsv, metadata))

    freyja_tsv = output_dir / "freyja" / "aggregated-freyja.tsv"
    if freyja_tsv.exists():
        results.extend(freyja.parse(freyja_tsv, metadata))

    return results


def collect_files(output_dir: Path, metadata: RunMetadata) -> list[FileArtifact]:
    """Collect registrable artifacts (consensus FASTAs) from a Cecret run."""
    consensus_dir = output_dir / "consensus"
    if not consensus_dir.exists():
        return []
    return consensus.collect(consensus_dir, metadata)


__all__ = [
    "SUPPORTED_PIPELINE_VERSIONS",
    "collect_files",
    "consensus",
    "freyja",
    "parse",
]
