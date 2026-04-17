"""
mycosnp-nf pipeline-level parser.

mycosnp output layout::

    <output_dir>/
    ├── snippy/<sample>/<sample>.txt
    ├── tree/core.aln.treefile
    └── typing/<sample>_<scheme>.tsv    (optional, species-dependent)

Emits per-sample ``pipeline_metrics`` ParsedResults from Snippy,
optional ``typing_results`` from fungal MLST, and a single run-level
SNP tree FileArtifact.
"""

from __future__ import annotations

from pathlib import Path

from shared.parsers import FileArtifact, ParsedResult, RunMetadata

from . import snippy, tree, typing

SUPPORTED_PIPELINE_VERSIONS: list[str] = [
    "1.5",
    "1.6",
    "2.0",
    "2.1",
]


def parse(output_dir: Path, metadata: RunMetadata) -> list[ParsedResult]:
    results: list[ParsedResult] = []

    snippy_dir = output_dir / "snippy"
    if snippy_dir.exists():
        results.extend(snippy.parse(snippy_dir, metadata))

    typing_dir = output_dir / "typing"
    if typing_dir.exists():
        results.extend(typing.parse(typing_dir, metadata))

    return results


def collect_files(output_dir: Path, metadata: RunMetadata) -> list[FileArtifact]:
    artifacts: list[FileArtifact] = []
    for candidate in (output_dir / "tree", output_dir / "phylogeny"):
        if candidate.exists():
            artifacts.extend(tree.collect(candidate, metadata))
    return artifacts


__all__ = [
    "SUPPORTED_PIPELINE_VERSIONS",
    "collect_files",
    "parse",
    "snippy",
    "tree",
    "typing",
]
