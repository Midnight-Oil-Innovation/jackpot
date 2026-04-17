"""
walkercreek per-segment consensus FASTA collector.

IRMA writes one FASTA per (sample, segment) pair.  walkercreek packs
them into ``consensus/`` under one of two layouts:

* Per-sample subdirectories (Illumina default):
  ``consensus/<sample>/<SEGMENT>.fa``
* Flat filenames (Nanopore default):
  ``consensus/<sample>_<SEGMENT>.fa``

Influenza IRMA segment names are ``HA``, ``NA``, ``MP``, ``NP``,
``NS``, ``PA``, ``PB1``, ``PB2`` and, for type B, ``HE``.  RSV runs
produce ``L``, ``G``, etc.  We do not enforce a fixed segment
vocabulary — any token after the last underscore (flat layout) or
before the suffix (nested layout) is accepted.

Every artifact is tagged ``file_type='fasta'`` and
``file_subtype='segment_<NAME>'`` so the backend can distinguish the
per-segment FASTAs in a single sample_files query.
"""

from __future__ import annotations

from pathlib import Path

from shared.parsers.types import FileArtifact, RunMetadata

FILE_TYPE = "fasta"
_ACCEPTED_SUFFIXES = (".fa", ".fasta", ".fa.gz", ".fasta.gz")


def collect(consensus_dir: Path, metadata: RunMetadata) -> list[FileArtifact]:  # noqa: ARG001
    if not consensus_dir.exists():
        return []
    artifacts: list[FileArtifact] = []
    for path in sorted(consensus_dir.rglob("*")):
        if not path.is_file() or not _matches_fasta(path):
            continue
        parsed = _sample_segment_for(path, consensus_dir)
        if parsed is None:
            continue
        sample_id, segment = parsed
        relative = path.relative_to(consensus_dir.parent)
        artifacts.append(
            FileArtifact(
                sample_id=sample_id,
                relative_path=str(relative),
                file_type=FILE_TYPE,
                file_subtype=f"segment_{segment}",
            )
        )
    return artifacts


def _matches_fasta(path: Path) -> bool:
    return any(path.name.endswith(suffix) for suffix in _ACCEPTED_SUFFIXES)


def _strip_suffix(name: str) -> str:
    for suffix in _ACCEPTED_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _sample_segment_for(path: Path, consensus_dir: Path) -> tuple[str, str] | None:
    stem = _strip_suffix(path.name)
    if not stem:
        return None

    if path.parent != consensus_dir:
        # Nested layout: consensus/<sample>/<SEGMENT>.fa
        sample_id = path.parent.name
        segment = stem
        if sample_id and segment:
            return sample_id, segment
        return None

    # Flat layout: consensus/<sample>_<SEGMENT>.fa
    if "_" not in stem:
        return None
    sample_id, _, segment = stem.rpartition("_")
    if not sample_id or not segment:
        return None
    return sample_id, segment
