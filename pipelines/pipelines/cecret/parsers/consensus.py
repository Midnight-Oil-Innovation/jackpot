"""
Cecret consensus FASTA collector.

Cecret writes consensus sequences to ``consensus/<sample>.consensus.fa``.
We detect them by extension rather than by name parsing so both single
``.fa`` and gzipped ``.fa.gz`` are picked up.  The sample_id is taken
from the filename stem up to the first ``.consensus`` marker — this
matches Cecret's naming scheme across 3.6–3.66.
"""

from __future__ import annotations

from pathlib import Path

from shared.parsers.types import FileArtifact, RunMetadata

FILE_TYPE = "fasta"
FILE_SUBTYPE = "consensus"
_ACCEPTED_SUFFIXES = (".consensus.fa", ".consensus.fasta", ".consensus.fa.gz")


def collect(consensus_dir: Path, metadata: RunMetadata) -> list[FileArtifact]:  # noqa: ARG001
    if not consensus_dir.exists():
        return []
    artifacts: list[FileArtifact] = []
    for path in sorted(consensus_dir.iterdir()):
        if not path.is_file():
            continue
        sample_id = _sample_id_for(path)
        if not sample_id:
            continue
        artifacts.append(
            FileArtifact(
                sample_id=sample_id,
                relative_path=f"{consensus_dir.name}/{path.name}",
                file_type=FILE_TYPE,
                file_subtype=FILE_SUBTYPE,
            )
        )
    return artifacts


def _sample_id_for(path: Path) -> str | None:
    name = path.name
    for suffix in _ACCEPTED_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)] or None
    return None
