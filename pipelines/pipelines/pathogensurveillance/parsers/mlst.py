"""
pathogensurveillance MLST parser.

pathogensurveillance ships Torsten Seemann's ``mlst`` tool, which
writes one concatenated TSV per sample under ``mlst/<sample>.tsv``.
The positional column layout is identical across bactopia, Grandeur,
and pathogensurveillance — we defer the row-level work to
``shared.parsers.mlst``.

The shared parser derives ``sample_id`` from the FASTA filename in
column 0 when no explicit sample_id is supplied; pathogensurveillance
writes the FASTA basename there, so no override is needed.
"""

from __future__ import annotations

from pathlib import Path

from shared.parsers import mlst as shared_mlst
from shared.parsers.types import ParsedResult, RunMetadata

_ACCEPTED_SUFFIX = ".tsv"


def parse(
    mlst_dir: Path,
    metadata: RunMetadata,
    *,
    tool_version: str | None = None,
) -> list[ParsedResult]:
    if not mlst_dir.exists():
        return []
    results: list[ParsedResult] = []
    for path in sorted(mlst_dir.iterdir()):
        if not path.is_file() or not path.name.endswith(_ACCEPTED_SUFFIX):
            continue
        sample_id = path.name[: -len(_ACCEPTED_SUFFIX)]
        if not sample_id:
            continue
        results.extend(
            shared_mlst.parse(
                path,
                metadata,
                sample_id=sample_id,
                tool_version=tool_version,
            )
        )
    return results
