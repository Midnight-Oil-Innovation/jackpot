"""
pathogensurveillance phylogeny tree collector.

pathogensurveillance emits up to three cohort-level Newick trees per
outbreak or sample group:

* ``phylogeny/core_gene/<group>.treefile``  — core gene phylogeny
* ``phylogeny/busco/<group>.treefile``      — BUSCO phylogeny
* ``phylogeny/snp/<group>.treefile``        — SNP phylogeny

These are **run-level** artifacts — one tree covers many samples — so
we emit each with the sentinel ``sample_id='_run_'`` (same convention
used by ``pipelines.mycosnp.parsers.tree``).  The backend's
registration endpoint links a run-level file to every sample in the
run via ``sample_associations``.

The subtype mapping distinguishes the three tree varieties so the UI
can label them correctly in the phylogeny viewer.
"""

from __future__ import annotations

from pathlib import Path

from shared.parsers.types import FileArtifact, RunMetadata

FILE_TYPE = "newick"
RUN_LEVEL_SAMPLE_ID = "_run_"

_ACCEPTED_SUFFIXES = (".treefile", ".tree", ".nwk", ".newick")

# Map a (lower-cased) sub-directory name to its file_subtype.  We match
# any ancestor directory so reshuffled 1.1.x layouts still resolve.
_SUBTYPE_BY_DIR: dict[str, str] = {
    "core_gene": "core_tree",
    "core_gene_phylogeny": "core_tree",
    "coregene": "core_tree",
    "busco": "busco_tree",
    "busco_phylogeny": "busco_tree",
    "snp": "snp_tree",
    "snp_phylogeny": "snp_tree",
}


def collect(phylogeny_dir: Path, metadata: RunMetadata) -> list[FileArtifact]:  # noqa: ARG001
    if not phylogeny_dir.exists():
        return []
    artifacts: list[FileArtifact] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted(phylogeny_dir.rglob("*")):
        if not path.is_file():
            continue
        if not _has_tree_suffix(path.name):
            continue
        subtype = _resolve_subtype(path, phylogeny_dir)
        if subtype is None:
            continue
        rel = str(path.relative_to(phylogeny_dir.parent))
        key = (subtype, rel)
        if key in seen:
            continue
        seen.add(key)
        artifacts.append(
            FileArtifact(
                sample_id=RUN_LEVEL_SAMPLE_ID,
                relative_path=rel,
                file_type=FILE_TYPE,
                file_subtype=subtype,
            )
        )
    return artifacts


def _has_tree_suffix(name: str) -> bool:
    return any(name.endswith(s) for s in _ACCEPTED_SUFFIXES)


def _resolve_subtype(path: Path, phylogeny_dir: Path) -> str | None:
    rel = path.relative_to(phylogeny_dir)
    # Walk the *directory* parts only (exclude the filename itself).
    for part in rel.parts[:-1]:
        subtype = _SUBTYPE_BY_DIR.get(part.lower())
        if subtype:
            return subtype
    # Fall back to filename hints so that a flat layout
    # (phylogeny/core_gene.treefile) still resolves.
    stem = path.name.lower()
    for key, subtype in _SUBTYPE_BY_DIR.items():
        if key in stem:
            return subtype
    return None
