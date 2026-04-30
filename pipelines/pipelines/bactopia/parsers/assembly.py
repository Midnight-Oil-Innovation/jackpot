"""
bactopia assembly + QUAST parser.

Layout::

    assembly/<sample>/shovill/<sample>.contigs.fa[.gz]
    assembly/<sample>/quast/report.tsv

We emit one :class:`AssemblyQC` per sample (from QUAST's
``report.tsv``) and register every contigs FASTA as a
:class:`FileArtifact` with ``file_subtype='assembly'``.

QUAST's ``report.tsv`` is a two-column file — metric name, value.
We map the subset of columns that our ``AssemblyQC`` schema exposes,
silently ignoring any QUAST columns not in the map.
"""

from __future__ import annotations

import csv
from pathlib import Path

from shared.parsers.types import FileArtifact, ParsedResult, RunMetadata
from shared.schemas import AssemblyQC

RESULT_TYPE = "assembly_qc"
TOOL_NAME = "quast"
FILE_TYPE = "fasta"
FILE_SUBTYPE = "assembly"

_CONTIG_SUFFIXES = (".contigs.fa", ".contigs.fa.gz", ".contigs.fasta")

_QUAST_COLUMN_MAP: dict[str, str] = {
    "Total length": "total_length",
    "# contigs": "num_contigs",
    "Largest contig": "largest_contig",
    "N50": "n50",
    "L50": "l50",
    "GC (%)": "gc_percent",
    "N's per 100 kbp": "n_count",
}


def parse(
    assembly_dir: Path,
    metadata: RunMetadata,
    *,
    tool_version: str | None = None,
) -> list[ParsedResult]:
    """Emit an AssemblyQC ParsedResult for every sample with a QUAST report."""
    if not assembly_dir.exists():
        return []
    results: list[ParsedResult] = []
    for sample_dir in sorted(assembly_dir.iterdir()):
        if not sample_dir.is_dir():
            continue
        report = sample_dir / "quast" / "report.tsv"
        if not report.is_file():
            continue
        model = _parse_quast(
            report,
            sample_id=sample_dir.name,
            tool_version=tool_version or metadata.pipeline_version,
        )
        results.append(ParsedResult.from_model(RESULT_TYPE, model))
    return results


def collect(assembly_dir: Path, metadata: RunMetadata) -> list[FileArtifact]:  # noqa: ARG001
    """Register contigs FASTAs as ``sample_files`` entries."""
    if not assembly_dir.exists():
        return []
    artifacts: list[FileArtifact] = []
    for sample_dir in sorted(assembly_dir.iterdir()):
        if not sample_dir.is_dir():
            continue
        sample_id = sample_dir.name
        shovill = sample_dir / "shovill"
        candidates = shovill if shovill.exists() else sample_dir
        for path in sorted(candidates.iterdir()):
            if not path.is_file():
                continue
            if not any(path.name.endswith(suf) for suf in _CONTIG_SUFFIXES):
                continue
            rel = f"assembly/{sample_id}/{candidates.name}/{path.name}"
            if candidates is sample_dir:
                rel = f"assembly/{sample_id}/{path.name}"
            artifacts.append(
                FileArtifact(
                    sample_id=sample_id,
                    relative_path=rel,
                    file_type=FILE_TYPE,
                    file_subtype=FILE_SUBTYPE,
                )
            )
    return artifacts


def _parse_quast(
    report: Path,
    *,
    sample_id: str,
    tool_version: str,
) -> AssemblyQC:
    fields: dict[str, object] = {
        "sample_id": sample_id,
        "tool_name": TOOL_NAME,
        "tool_version": tool_version,
        "assembly_method": "shovill",
    }
    with report.open(newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if len(row) < 2:
                continue
            key = row[0].strip()
            raw = row[1].strip()
            if key not in _QUAST_COLUMN_MAP or raw in {"", "-"}:
                continue
            column = _QUAST_COLUMN_MAP[key]
            fields[column] = _coerce(column, raw)
    return AssemblyQC(**fields)


def _coerce(column: str, raw: str) -> object:
    float_cols = {"gc_percent"}
    int_cols = {"total_length", "num_contigs", "largest_contig", "n50", "l50", "n_count"}
    try:
        if column in float_cols:
            return float(raw)
        if column in int_cols:
            # QUAST sometimes emits floats ("0.00") for N count — cast via float first.
            return int(float(raw))
    except ValueError:
        return None
    return raw
