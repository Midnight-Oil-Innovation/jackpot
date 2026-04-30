"""
bactopia pipeline-level parser.

bactopia writes a tree like::

    <output_dir>/
    ├── amrfinderplus/<sample>.tsv
    ├── mlst/<sample>.tsv
    ├── assembly/<sample>/shovill/<sample>.contigs.fa
    ├── assembly/<sample>/quast/report.tsv
    └── annotation/<sample>/<sample>.gff3

The top-level :func:`parse` runs every sub-parser that has output
available.  :func:`collect_files` returns FileArtifact entries (contigs,
annotation GFFs) which the wrapper registers through the ``sample_files``
transport.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from shared.parsers import FileArtifact, ParsedResult, RunMetadata

from . import amr, annotation, assembly, mlst

SUPPORTED_PIPELINE_VERSIONS: list[str] = [
    "2.2.0",
    "3.0.0",
    "3.0.1",
    "3.1.0",
]

# AMRFinderPlus ships its DB version separately from the binary — the
# wrapper supplies both through run params.  These defaults exist so the
# parser layer can be invoked directly in tests without threading the
# values through every call site.
DEFAULT_AMRFINDER_TOOL_VERSION = "3.12.8"
DEFAULT_AMRFINDER_DATABASE_VERSION = "2024-01-31.1"


def parse(
    output_dir: Path,
    metadata: RunMetadata,
    *,
    amrfinder_tool_version: str = DEFAULT_AMRFINDER_TOOL_VERSION,
    amrfinder_database_version: str = DEFAULT_AMRFINDER_DATABASE_VERSION,
    runner=subprocess.run,
) -> list[ParsedResult]:
    """Run every sub-parser; concatenate ParsedResults in a stable order."""
    results: list[ParsedResult] = []

    amr_dir = output_dir / "amrfinderplus"
    if amr_dir.exists():
        results.extend(
            amr.parse(
                amr_dir,
                metadata,
                tool_version=amrfinder_tool_version,
                database_version=amrfinder_database_version,
                runner=runner,
            )
        )

    mlst_dir = output_dir / "mlst"
    if mlst_dir.exists():
        results.extend(mlst.parse(mlst_dir, metadata))

    assembly_dir = output_dir / "assembly"
    if assembly_dir.exists():
        results.extend(assembly.parse(assembly_dir, metadata))

    return results


def collect_files(output_dir: Path, metadata: RunMetadata) -> list[FileArtifact]:
    """Return contigs FASTAs + annotation GFFs as FileArtifact entries."""
    artifacts: list[FileArtifact] = []
    assembly_dir = output_dir / "assembly"
    if assembly_dir.exists():
        artifacts.extend(assembly.collect(assembly_dir, metadata))
    annotation_dir = output_dir / "annotation"
    if annotation_dir.exists():
        artifacts.extend(annotation.collect(annotation_dir, metadata))
    return artifacts


__all__ = [
    "DEFAULT_AMRFINDER_DATABASE_VERSION",
    "DEFAULT_AMRFINDER_TOOL_VERSION",
    "SUPPORTED_PIPELINE_VERSIONS",
    "amr",
    "annotation",
    "assembly",
    "collect_files",
    "mlst",
    "parse",
]
