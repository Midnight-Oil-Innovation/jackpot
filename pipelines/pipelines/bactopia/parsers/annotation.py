"""
bactopia annotation file collector.

bactopia runs Bakta (preferred) or Prokka and writes a GFF3 per sample
under ``annotation/<sample>/<sample>.gff3`` (or ``.gff`` for older Prokka
output).  We register the GFF as a ``sample_files`` entry so downstream
tools can pull it via presigned URL.

No typed result table is produced — annotation features live only on
disk; we intentionally do not explode every CDS into a row.
"""

from __future__ import annotations

from pathlib import Path

from shared.parsers.types import FileArtifact, RunMetadata

FILE_TYPE = "gff"
FILE_SUBTYPE = "annotation"
_ACCEPTED_SUFFIXES = (".gff3", ".gff3.gz", ".gff", ".gff.gz")


def collect(annotation_dir: Path, metadata: RunMetadata) -> list[FileArtifact]:  # noqa: ARG001
    if not annotation_dir.exists():
        return []
    artifacts: list[FileArtifact] = []
    for sample_dir in sorted(annotation_dir.iterdir()):
        if not sample_dir.is_dir():
            # Allow flat layout too: annotation/<sample>.gff3
            if sample_dir.is_file() and any(
                sample_dir.name.endswith(s) for s in _ACCEPTED_SUFFIXES
            ):
                sample_id = _strip_suffix(sample_dir.name)
                artifacts.append(
                    FileArtifact(
                        sample_id=sample_id,
                        relative_path=f"annotation/{sample_dir.name}",
                        file_type=FILE_TYPE,
                        file_subtype=FILE_SUBTYPE,
                    )
                )
            continue
        for path in sorted(sample_dir.iterdir()):
            if not path.is_file():
                continue
            if not any(path.name.endswith(s) for s in _ACCEPTED_SUFFIXES):
                continue
            artifacts.append(
                FileArtifact(
                    sample_id=sample_dir.name,
                    relative_path=f"annotation/{sample_dir.name}/{path.name}",
                    file_type=FILE_TYPE,
                    file_subtype=FILE_SUBTYPE,
                )
            )
    return artifacts


def _strip_suffix(name: str) -> str:
    for suffix in _ACCEPTED_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name
