"""
walkercreek parsers.

walkercreek emits a consolidated typing summary (``typing/typing_summary.tsv``)
with one row per sample + subtype + clade, plus per-segment consensus
FASTAs under ``consensus/<sample>/<SEGMENT>.fa`` (Illumina) or
``consensus/<sample>_<SEGMENT>.fa`` (Nanopore).  The parsers here
handle both layouts.
"""

from __future__ import annotations

from pathlib import Path

from shared.parsers import FileArtifact, ParsedResult, RunMetadata

from . import consensus, irma

SUPPORTED_PIPELINE_VERSIONS: list[str] = [
    "1.0",
    "1.1",
    "1.1.4",
    "1.2",
]


def parse(output_dir: Path, metadata: RunMetadata) -> list[ParsedResult]:
    typing_summary = _find_typing_summary(output_dir)
    if typing_summary is None:
        return []
    return irma.parse(typing_summary, metadata)


def collect_files(output_dir: Path, metadata: RunMetadata) -> list[FileArtifact]:
    consensus_dir = output_dir / "consensus"
    if not consensus_dir.exists():
        return []
    return consensus.collect(consensus_dir, metadata)


def _find_typing_summary(output_dir: Path) -> Path | None:
    for candidate in (
        output_dir / "typing" / "typing_summary.tsv",
        output_dir / "typing" / "typing_summary.csv",
        output_dir / "irma" / "typing_summary.tsv",
    ):
        if candidate.exists():
            return candidate
    return None


__all__ = [
    "SUPPORTED_PIPELINE_VERSIONS",
    "collect_files",
    "consensus",
    "irma",
    "parse",
]
