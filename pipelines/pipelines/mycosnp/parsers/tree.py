"""
mycosnp SNP-tree Newick collector.

mycosnp writes the final SNP tree at one of::

    tree/core.aln.tree
    tree/core.aln.treefile
    phylogeny/iqtree/core.aln.treefile

Because the tree is cohort-level (one file per run, not one per sample)
we emit it with the sentinel sample_id ``_run_`` and mark it so the
wrapper knows to link it to every sample via sample_associations.

No typed result is produced; the tree lives in ``sample_files`` only.
"""

from __future__ import annotations

from pathlib import Path

from shared.parsers.types import FileArtifact, RunMetadata

FILE_TYPE = "newick"
FILE_SUBTYPE = "snp_tree"
RUN_LEVEL_SAMPLE_ID = "_run_"
_ACCEPTED_NAMES = {
    "core.aln.tree",
    "core.aln.treefile",
    "core.treefile",
    "core.tree",
}


def collect(tree_dir: Path, metadata: RunMetadata) -> list[FileArtifact]:  # noqa: ARG001
    if not tree_dir.exists():
        return []
    artifacts: list[FileArtifact] = []
    for path in sorted(tree_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name not in _ACCEPTED_NAMES:
            continue
        relative = path.relative_to(tree_dir.parent)
        artifacts.append(
            FileArtifact(
                sample_id=RUN_LEVEL_SAMPLE_ID,
                relative_path=str(relative),
                file_type=FILE_TYPE,
                file_subtype=FILE_SUBTYPE,
            )
        )
    return artifacts
