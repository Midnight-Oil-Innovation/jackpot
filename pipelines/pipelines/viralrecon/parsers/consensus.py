"""
viralrecon consensus FASTA collector.

viralrecon writes consensus sequences under either ``consensus/bcftools/``
or ``consensus/ivar/``.  Filenames follow
``<sample>.consensus.fa[.gz]`` — identical to Cecret's layout.
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
    parent = consensus_dir.parent.name or consensus_dir.name
    rel_root = (
        f"{parent}/{consensus_dir.name}" if parent != consensus_dir.name else consensus_dir.name
    )
    for path in sorted(consensus_dir.iterdir()):
        if not path.is_file():
            continue
        sample_id = _sample_id_for(path)
        if not sample_id:
            continue
        artifacts.append(
            FileArtifact(
                sample_id=sample_id,
                relative_path=f"{rel_root}/{path.name}",
                file_type=FILE_TYPE,
                file_subtype=FILE_SUBTYPE,
            )
        )
    return artifacts


def _sample_id_for(path: Path) -> str | None:
    for suffix in _ACCEPTED_SUFFIXES:
        if path.name.endswith(suffix):
            return path.name[: -len(suffix)] or None
    return None
