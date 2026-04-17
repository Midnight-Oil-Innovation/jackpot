"""
MAG bin FASTA collector for nf-core/mag.

nf-core/mag writes bin FASTAs under one of::

    GenomeBinning/<binner>/bins/<bin>.fa[.gz]
    GenomeBinning/<binner>_bins/<bin>.fa[.gz]
    GenomeBinning/DAS_Tool/bins/<bin>.fa[.gz]

The binner directory names vary by version (MetaBAT2, MaxBin2,
CONCOCT, DAS_Tool, ...).  Rather than enumerate every legal name, we
rglob the ``GenomeBinning/`` tree for FASTA files and emit one
:class:`FileArtifact` per bin with:

* ``sample_id = bin_id`` — the bin basename without extension, which
  matches the ``MAGQC.bin_id`` that CheckM2 and GTDB-Tk emit for the
  same bin.  The backend creates a derived sample row for that bin_id
  and links it to the parent metagenomic sample via
  ``sample_associations(association_type='mag_bin')``.
* ``file_subtype = 'mag_bin'`` — distinguishes MAG bin FASTAs from
  primary assembly contigs (``file_subtype='assembly'``).
"""

from __future__ import annotations

from pathlib import Path

from shared.parsers import FileArtifact, RunMetadata

FILE_TYPE = "fasta"
FILE_SUBTYPE = "mag_bin"

_ACCEPTED_SUFFIXES = (".fa", ".fa.gz", ".fasta", ".fasta.gz", ".fna", ".fna.gz")
_BIN_ROOT_NAMES = ("GenomeBinning", "Bins", "bins")


def collect(output_dir: Path, metadata: RunMetadata) -> list[FileArtifact]:  # noqa: ARG001
    if not output_dir.exists():
        return []
    artifacts: list[FileArtifact] = []
    seen: set[tuple[str, str]] = set()
    roots = [output_dir / name for name in _BIN_ROOT_NAMES if (output_dir / name).exists()]
    # Fall back to scanning the whole output tree when no canonical root exists.
    if not roots:
        roots = [output_dir]
    for root in roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if not _has_accepted_suffix(path.name):
                continue
            if not _is_bin_file(path, output_dir):
                continue
            bin_id = _strip_suffix(path.name)
            if not bin_id:
                continue
            rel = str(path.relative_to(output_dir))
            key = (bin_id, rel)
            if key in seen:
                continue
            seen.add(key)
            artifacts.append(
                FileArtifact(
                    sample_id=bin_id,
                    relative_path=rel,
                    file_type=FILE_TYPE,
                    file_subtype=FILE_SUBTYPE,
                )
            )
    return artifacts


def _has_accepted_suffix(name: str) -> bool:
    return any(name.endswith(s) for s in _ACCEPTED_SUFFIXES)


def _strip_suffix(name: str) -> str:
    for suf in _ACCEPTED_SUFFIXES:
        if name.endswith(suf):
            return name[: -len(suf)]
    return name


def _is_bin_file(path: Path, output_dir: Path) -> bool:
    """Filter out assembly contigs and reference FASTAs that also live under
    the output tree.  Bin files sit under a ``bins/`` directory or under a
    binner-specific dir (``MetaBAT2/``, ``DAS_Tool/``, ...).  Anything
    directly under ``Assembly/`` is a primary assembly, not a bin.
    """
    rel_parts = {part.lower() for part in path.relative_to(output_dir).parts}
    if "assembly" in rel_parts and "genomebinning" not in rel_parts:
        return False
    if "bins" in rel_parts:
        return True
    # Accept if any ancestor directory hints at binning output.
    binner_hints = {
        "metabat2",
        "maxbin2",
        "concoct",
        "das_tool",
        "dastool",
        "semibin",
        "genomebinning",
    }
    return bool(rel_parts & binner_hints)
