"""Grandeur MLST parser — identical layout to bactopia; reuses shared parser."""

from __future__ import annotations

from pathlib import Path

from shared.parsers import mlst as shared_mlst
from shared.parsers.types import ParsedResult, RunMetadata

_MLST_DIR_NAME = "mlst"


def parse(mlst_dir: Path, metadata: RunMetadata) -> list[ParsedResult]:
    if not mlst_dir.exists():
        return []
    results: list[ParsedResult] = []
    for path in sorted(mlst_dir.iterdir()):
        if not path.is_file() or not path.name.endswith(".tsv"):
            continue
        sample_id = path.name[: -len(".tsv")]
        if not sample_id:
            continue
        results.extend(
            shared_mlst.parse(path, metadata, sample_id=sample_id),
        )
    return results
