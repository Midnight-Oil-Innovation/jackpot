"""
pathogensurveillance AMRFinderPlus parser.

Same layout as bactopia: one TSV per sample under ``amrfinderplus/``.
All column mapping is deferred to ``shared.parsers.amrfinderplus``,
which pipes the raw TSV through hAMRonization — this guarantees
cross-pipeline AMR output parity (the M-2 validator test asserts this
invariant).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from shared.parsers import amrfinderplus as shared_amr
from shared.parsers.types import ParsedResult, RunMetadata

_ACCEPTED_SUFFIX = ".tsv"


def parse(
    amr_dir: Path,
    metadata: RunMetadata,
    *,
    tool_version: str,
    database_version: str,
    runner=subprocess.run,
) -> list[ParsedResult]:
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
