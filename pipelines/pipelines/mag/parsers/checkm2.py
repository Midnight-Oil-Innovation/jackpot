"""
CheckM2 report parser for nf-core/mag.

CheckM2 writes one aggregated quality report per run::

    <output>/CheckM2/checkm2_quality_report.tsv

Columns (CheckM2 v1.x)::

    Name, Completeness, Contamination, Completeness_Model_Used,
    Translation_Table_Used, Coding_Density, Contig_N50,
    Average_Gene_Length, Genome_Size, GC_Content,
    Total_Coding_Sequences, Total_Contigs, Max_Contig_Length,
    Additional_Notes

``Name`` is the bin identifier — typically ``<parent_sample>.<binner>.<n>``
or ``<parent_sample>_<binner>.<n>``.  We take everything before the
first ``.`` as the parent metagenomic sample_id; a custom
``sample_id_resolver`` callable can override this if a site uses a
different bin naming convention.

Strain heterogeneity is a CheckM1 metric — CheckM2 does not emit it.
We leave ``strain_heterogeneity`` unset (``None``) in that case; the
schema marks it optional.
"""

from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path

from shared.parsers import ParsedResult, RunMetadata
from shared.schemas import MAGQC

RESULT_TYPE = "mag_qc"
TOOL_NAME = "checkm2"
DEFAULT_REPORT_NAMES = (
    "checkm2_quality_report.tsv",
    "quality_report.tsv",
)
_SEARCH_DIRS = ("CheckM2", "checkm2", "QC/CheckM2", "GenomeBinning/QC/CheckM2")


class CheckM2ParseError(ValueError):
    """Raised when the CheckM2 report is missing required columns."""


def _default_resolver(bin_name: str) -> str:
    """Parent sample = everything before the first ``.`` in the bin name."""
    return bin_name.split(".", 1)[0]


def parse(
    output_dir: Path,
    metadata: RunMetadata,
    *,
    tool_version: str | None = None,
    sample_id_resolver: Callable[[str], str] = _default_resolver,
) -> list[ParsedResult]:
    report = _locate_report(output_dir)
    if report is None:
        return []
    return parse_report(
        report,
        metadata,
        tool_version=tool_version,
        sample_id_resolver=sample_id_resolver,
    )


def parse_report(
    report: Path,
    metadata: RunMetadata,
    *,
    tool_version: str | None = None,
    sample_id_resolver: Callable[[str], str] = _default_resolver,
) -> list[ParsedResult]:
    if not report.exists():
        raise FileNotFoundError(f"CheckM2 report not found: {report}")
    rows: list[ParsedResult] = []
    with report.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if reader.fieldnames is None or "Name" not in reader.fieldnames:
            raise CheckM2ParseError(
                f"CheckM2 report missing 'Name' column: {report}",
            )
        for raw in reader:
            bin_name = (raw.get("Name") or "").strip()
            if not bin_name:
                continue
            parent = sample_id_resolver(bin_name).strip()
            if not parent:
                parent = bin_name
            model = MAGQC(
                sample_id=parent,
                bin_id=bin_name,
                completeness_percent=_float(raw.get("Completeness")),
                contamination_percent=_float(raw.get("Contamination")),
                bin_size_bp=_int(raw.get("Genome_Size")),
                num_contigs=_int(raw.get("Total_Contigs")),
                n50=_int(raw.get("Contig_N50")),
                gc_percent=_float(raw.get("GC_Content")),
                tool_name=TOOL_NAME,
                tool_version=tool_version or metadata.pipeline_version,
            )
            rows.append(ParsedResult.from_model(RESULT_TYPE, model))
    return rows


def _locate_report(output_dir: Path) -> Path | None:
    if not output_dir.exists():
        return None
    for sub in _SEARCH_DIRS:
        for name in DEFAULT_REPORT_NAMES:
            candidate = output_dir / sub / name
            if candidate.is_file():
                return candidate
    for name in DEFAULT_REPORT_NAMES:
        candidate = output_dir / name
        if candidate.is_file():
            return candidate
    return None


def _float(raw: str | None) -> float | None:
    if raw is None:
        return None
    stripped = raw.strip()
    if stripped in {"", "-", "N/A", "NA"}:
        return None
    try:
        return float(stripped)
    except ValueError:
        return None


def _int(raw: str | None) -> int | None:
    f = _float(raw)
    return int(f) if f is not None else None
