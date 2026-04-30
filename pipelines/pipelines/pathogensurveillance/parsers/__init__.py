"""
nf-core/pathogensurveillance pipeline-level parser.

Expected layout (1.1.0)::

    <output>/
    ├── sendsketch/<sample>.sendsketch.txt
    ├── amrfinderplus/<sample>.tsv
    ├── mlst/<sample>.tsv
    ├── variants/graphtyper/<sample>.vcf[.gz]
    ├── reference_selection/<sample>.reference.tsv
    ├── phylogeny/
    │   ├── core_gene/<group>.treefile
    │   ├── busco/<group>.treefile
    │   └── snp/<group>.treefile
    └── report/pathogensurveillance_report.html

The invariants we rely on are the **file naming conventions** inside
each subdirectory, not the directory tree itself — future 1.x releases
that shuffle the top-level folder names can be handled by adjusting
the ``_LAYOUT`` dict below rather than per-call sitewide changes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from shared.parsers import FileArtifact, ParsedResult, RunMetadata

from . import amr, identification, mlst, phylogeny, reference_selection, report, variants

SUPPORTED_PIPELINE_VERSIONS: list[str] = [
    "1.1.0",
]
"""
Version pinning.

The Session M spec explicitly pins to 1.1.0.  This list is the single
source of truth the launcher reads at run start to decide whether to
emit a ``pipeline_events`` warning for out-of-range versions — do not
add new versions without updating the fixtures and regenerating the
parser tests.
"""

DEFAULT_AMRFINDER_TOOL_VERSION = "3.12.8"
DEFAULT_AMRFINDER_DATABASE_VERSION = "2024-01-31.1"


_LAYOUT: dict[str, str] = {
    "sendsketch": "sendsketch",
    "amrfinderplus": "amrfinderplus",
    "mlst": "mlst",
    "variants": "variants/graphtyper",
    "reference_selection": "reference_selection",
    "phylogeny": "phylogeny",
    "report": "report",
}


def parse(
    output_dir: Path,
    metadata: RunMetadata,
    *,
    amrfinder_tool_version: str = DEFAULT_AMRFINDER_TOOL_VERSION,
    amrfinder_database_version: str = DEFAULT_AMRFINDER_DATABASE_VERSION,
    runner=subprocess.run,
) -> list[ParsedResult]:
    """Run every sub-parser that has input; concatenate ParsedResults."""
    results: list[ParsedResult] = []

    sendsketch_dir = output_dir / _LAYOUT["sendsketch"]
    if sendsketch_dir.exists():
        results.extend(identification.parse(sendsketch_dir, metadata))

    amr_dir = output_dir / _LAYOUT["amrfinderplus"]
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

    mlst_dir = output_dir / _LAYOUT["mlst"]
    if mlst_dir.exists():
        results.extend(mlst.parse(mlst_dir, metadata))

    variants_dir = output_dir / _LAYOUT["variants"]
    if variants_dir.exists():
        results.extend(variants.parse(variants_dir, metadata))

    reference_dir = output_dir / _LAYOUT["reference_selection"]
    if reference_dir.exists():
        results.extend(reference_selection.parse(reference_dir, metadata))

    return results


def collect_files(output_dir: Path, metadata: RunMetadata) -> list[FileArtifact]:
    """Return phylogeny trees + interactive HTML report as FileArtifacts."""
    artifacts: list[FileArtifact] = []
    phylogeny_dir = output_dir / _LAYOUT["phylogeny"]
    if phylogeny_dir.exists():
        artifacts.extend(phylogeny.collect(phylogeny_dir, metadata))
    report_dir = output_dir / _LAYOUT["report"]
    if report_dir.exists():
        artifacts.extend(report.collect(report_dir, metadata))
    return artifacts


__all__ = [
    "DEFAULT_AMRFINDER_DATABASE_VERSION",
    "DEFAULT_AMRFINDER_TOOL_VERSION",
    "SUPPORTED_PIPELINE_VERSIONS",
    "amr",
    "collect_files",
    "identification",
    "mlst",
    "parse",
    "phylogeny",
    "reference_selection",
    "report",
    "variants",
]
