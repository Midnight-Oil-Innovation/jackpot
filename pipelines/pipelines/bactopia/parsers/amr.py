"""
bactopia AMRFinderPlus parser.

bactopia's ``bactopia tools`` AMR module runs AMRFinderPlus per sample
and writes:

    amrfinderplus/<sample>.tsv

We defer all column mapping to the shared AMRFinderPlus parser, which
pipes the raw TSV through hAMRonization.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from shared.parsers import amrfinderplus as shared_amr
from shared.parsers.types import ParsedResult, RunMetadata

_AMR_DIR_NAME = "amrfinderplus"
_ACCEPTED_SUFFIX = ".tsv"


def parse(
    amr_dir: Path,
    metadata: RunMetadata,
    *,
    tool_version: str,
    database_version: str,
    runner=subprocess.run,
) -> list[ParsedResult]:
    """Iterate every ``<sample>.tsv`` under ``amrfinderplus/``."""
    if not amr_dir.exists():
        return []
    results: list[ParsedResult] = []
    for path in sorted(amr_dir.iterdir()):
        if not path.is_file() or not path.name.endswith(_ACCEPTED_SUFFIX):
            continue
        sample_id = path.name[: -len(_ACCEPTED_SUFFIX)]
        if not sample_id:
            continue
        results.extend(
            shared_amr.parse(
                path,
                metadata,
                sample_id=sample_id,
                tool_version=tool_version,
                database_version=database_version,
                runner=runner,
            )
        )
    return results
