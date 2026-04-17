"""
hAMRonization wrapper.

``hAMRonization`` is the community AMR output harmonizer
(https://github.com/pha4ge/hAMRonization). Different AMR tools
(AMRFinderPlus, ResFinder, RGI, etc.) emit incompatible TSVs; the
harmonizer reads tool-specific output and writes a single canonical TSV
with a stable column set.

This module wraps the harmonizer CLI and converts its canonical TSV into
a list of :class:`AMRResult` payloads that the JACKPOT API can register.

Used by the bactopia, Grandeur, and pathogensurveillance parsers.

Design notes
------------
- We shell out to the ``hamronize`` CLI (pip install hAMRonization) rather
  than import the Python API because the CLI is the documented stable
  interface and parsers may run in separate images.
- Each caller supplies the raw tool output, the source tool name, and the
  metadata fields (``input_file_name``, ``analysis_software_version``,
  ``reference_database_version``) that the harmonizer requires.
- The sample_id is stamped onto every emitted row; the harmonizer knows
  nothing about JACKPOT sample IDs.
"""

from __future__ import annotations

import csv
import io
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .schemas.amr import AMRResult

logger = logging.getLogger(__name__)


SUPPORTED_TOOLS: set[str] = {
    "amrfinderplus",
    "resfinder",
    "rgi",
    "ariba",
    "abricate",
    "srax",
    "staramr",
    "groot",
    "deeparg",
}


class HamronizationError(Exception):
    """Raised when hamronization cannot be completed."""


@dataclass
class HamronizeInput:
    """Inputs required to run hamronization against one tool's output."""

    tool: str
    raw_output_path: Path
    sample_id: str
    analysis_software_version: str
    reference_database_version: str
    input_file_name: str | None = None
    extra_args: list[str] = field(default_factory=list)


_HAMRONIZE_TO_AMR_COLUMN: dict[str, str] = {
    "gene_symbol": "gene_symbol",
    "gene_name": "gene_name",
    "drug_class": "drug_class",
    "antimicrobial_agent": "drug",
    "coverage_percentage": "coverage_percent",
    "sequence_identity": "identity_percent",
    "reference_database_name": "reference_database",
    "reference_accession": "reference_accession",
    "input_sequence_id": "contig_id",
    "input_gene_start": "start_pos",
    "input_gene_stop": "end_pos",
    "strand_orientation": "strand",
    "analysis_software_name": "tool_name",
    "analysis_software_version": "tool_version",
    "predicted_phenotype": "resistance_phenotype",
}


def run_hamronize(
    spec: HamronizeInput,
    *,
    executable: str | None = None,
    runner=subprocess.run,
) -> str:
    """
    Invoke the hamronize CLI; return the canonical TSV as a string.

    Raises ``HamronizationError`` on unsupported tools, missing CLI, or
    non-zero exit.
    """
    if spec.tool not in SUPPORTED_TOOLS:
        raise HamronizationError(
            f"Unsupported tool: {spec.tool} (expected one of {sorted(SUPPORTED_TOOLS)})"
        )
    if not spec.raw_output_path.exists():
        raise HamronizationError(f"Raw output does not exist: {spec.raw_output_path}")

    cli = executable or shutil.which("hamronize")
    if not cli:
        raise HamronizationError(
            "hamronize executable not found on PATH; pip install hAMRonization",
        )

    cmd = [
        cli,
        spec.tool,
        str(spec.raw_output_path),
        "--format",
        "tsv",
        "--analysis_software_version",
        spec.analysis_software_version,
        "--reference_database_version",
        spec.reference_database_version,
    ]
    if spec.input_file_name:
        cmd.extend(["--input_file_name", spec.input_file_name])
    cmd.extend(spec.extra_args)

    completed = runner(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise HamronizationError(
            f"hamronize exited {completed.returncode}: {completed.stderr.strip()}"
        )
    return completed.stdout


def parse_canonical_tsv(tsv_text: str, sample_id: str) -> list[AMRResult]:
    """Parse a hamronize canonical TSV into AMRResult payloads."""
    if not tsv_text.strip():
        return []
    reader = csv.DictReader(io.StringIO(tsv_text), delimiter="\t")
    results: list[AMRResult] = []
    for row in reader:
        mapped: dict = {"sample_id": sample_id}
        for src_col, dst_col in _HAMRONIZE_TO_AMR_COLUMN.items():
            raw = row.get(src_col, "")
            if raw is None or raw == "":
                continue
            mapped[dst_col] = _coerce(dst_col, raw)
        if "gene_symbol" not in mapped or "tool_name" not in mapped:
            # hamronize occasionally emits rows with no gene symbol (header re-echo
            # or zero-hit placeholder). Skip those.
            continue
        results.append(AMRResult(**mapped))
    return results


def normalize(spec: HamronizeInput, **kwargs) -> list[AMRResult]:
    """Run the harmonizer and return parsed AMRResult payloads."""
    tsv = run_hamronize(spec, **kwargs)
    return parse_canonical_tsv(tsv, sample_id=spec.sample_id)


def _coerce(column: str, raw: str) -> object:
    if column in {"start_pos", "end_pos"}:
        try:
            return int(raw)
        except ValueError:
            return None
    if column in {"coverage_percent", "identity_percent"}:
        try:
            return float(raw)
        except ValueError:
            return None
    return raw
