"""
Grandeur AMRFinderPlus parser.

Grandeur writes one TSV per sample under ``amrfinderplus/`` — same
layout as bactopia (``<sample>.tsv``) plus an optional pre-hamronized
canonical output (``<sample>.hamronized.tsv``) starting in 4.x.  When
the canonical file is available we parse it directly and skip the
hamronize round-trip; otherwise we defer to the shared AMRFinderPlus
parser.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from shared.parsers import amrfinderplus as shared_amr
from shared.parsers.types import ParsedResult, RunMetadata

_AMR_DIR_NAME = "amrfinderplus"
_RAW_SUFFIX = ".tsv"
_CANONICAL_SUFFIX = ".hamronized.tsv"


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
    seen_samples: set[str] = set()
    for path in sorted(amr_dir.iterdir()):
        if not path.is_file() or not path.name.endswith(_CANONICAL_SUFFIX):
            continue
        sample_id = path.name[: -len(_CANONICAL_SUFFIX)]
        if not sample_id:
            continue
        seen_samples.add(sample_id)
        results.extend(
            shared_amr.parse_canonical(path, metadata, sample_id=sample_id),
        )
    for path in sorted(amr_dir.iterdir()):
        if not path.is_file() or not path.name.endswith(_RAW_SUFFIX):
            continue
        if path.name.endswith(_CANONICAL_SUFFIX):
            continue
        sample_id = path.name[: -len(_RAW_SUFFIX)]
        if not sample_id or sample_id in seen_samples:
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
