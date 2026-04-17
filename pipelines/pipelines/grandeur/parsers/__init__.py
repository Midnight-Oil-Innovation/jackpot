"""
Grandeur pipeline-level parser.

Grandeur (``UPHL-BioNGS/Grandeur``) produces the same amrfinderplus /
mlst layout as bactopia plus Kraken2 species ID and a local BLAST
check::

    <output_dir>/
    ├── amrfinderplus/<sample>.tsv[,.hamronized.tsv]
    ├── mlst/<sample>.tsv
    ├── kraken2/<sample>_report.txt
    └── blast/<sample>_blast.tsv

Grandeur does not expose assembly FASTAs or annotation through the
same sub-directory structure — those flow through separate wrappers
(or a downstream bactopia run) and are not part of this parser.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from shared.parsers import ParsedResult, RunMetadata

from . import amr, blast, kraken2, mlst

SUPPORTED_PIPELINE_VERSIONS: list[str] = [
    "3.2.0",
    "3.3.0",
    "4.0.0",
    "4.1.0",
    "4.2.0",
]

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

    kraken_dir = output_dir / "kraken2"
    if kraken_dir.exists():
        results.extend(kraken2.parse(kraken_dir, metadata))

    blast_dir = output_dir / "blast"
    if blast_dir.exists():
        results.extend(blast.parse(blast_dir, metadata))

    return results


def collect_files(output_dir: Path, metadata: RunMetadata) -> list:  # noqa: ARG001
    """Grandeur has no FileArtifact-grade outputs — files are handled elsewhere."""
    return []


__all__ = [
    "DEFAULT_AMRFINDER_DATABASE_VERSION",
    "DEFAULT_AMRFINDER_TOOL_VERSION",
    "SUPPORTED_PIPELINE_VERSIONS",
    "amr",
    "blast",
    "collect_files",
    "kraken2",
    "mlst",
    "parse",
]
