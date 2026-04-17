"""
AMRFinderPlus shared parser.

Both bactopia and Grandeur (and pathogensurveillance, Session M) run
NCBI's AMRFinderPlus.  Rather than reinvent the column mapping in each
pipeline we funnel the raw TSV through the hAMRonization CLI wrapper in
``shared.hamronization_normalizer`` — that is the single canonical path
from "tool-specific output" to ``AMRResult``.

Tests inject a ``runner`` callable to avoid requiring the real
``hamronize`` binary in CI.  Production runs the real CLI as packaged in
the JACKPOT pipeline container image.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from shared.hamronization_normalizer import (
    HamronizeInput,
    normalize,
    parse_canonical_tsv,
)
from shared.parsers.types import ParsedResult, RunMetadata
from shared.schemas import AMRResult

RESULT_TYPE = "amr_results"
TOOL_NAME = "amrfinderplus"


def parse(
    path: Path,
    metadata: RunMetadata,
    *,
    sample_id: str,
    tool_version: str,
    database_version: str,
    runner=subprocess.run,
    executable: str | None = None,
) -> list[ParsedResult]:
    """Hamronize an AMRFinderPlus TSV and return AMRResult ParsedResults."""
    if not path.exists():
        raise FileNotFoundError(f"AMRFinderPlus TSV not found: {path}")
    spec = HamronizeInput(
        tool=TOOL_NAME,
        raw_output_path=path,
        sample_id=sample_id,
        analysis_software_version=tool_version,
        reference_database_version=database_version,
        input_file_name=path.name,
    )
    amr_results = normalize(spec, runner=runner, executable=executable)
    return [
        ParsedResult.from_model(RESULT_TYPE, _with_metadata(r, metadata=metadata))
        for r in amr_results
    ]


def parse_canonical(
    canonical_tsv_path: Path,
    metadata: RunMetadata,
    *,
    sample_id: str,
) -> list[ParsedResult]:
    """Parse a pre-hamronized canonical TSV, bypassing the CLI.

    Useful when the pipeline already stores the canonical output
    (Grandeur 4.x writes it alongside the raw AMRFinderPlus TSV).
    """
    if not canonical_tsv_path.exists():
        raise FileNotFoundError(f"Canonical AMR TSV not found: {canonical_tsv_path}")
    amr_results = parse_canonical_tsv(canonical_tsv_path.read_text(), sample_id=sample_id)
    return [
        ParsedResult.from_model(RESULT_TYPE, _with_metadata(r, metadata=metadata))
        for r in amr_results
    ]


def _with_metadata(result: AMRResult, *, metadata: RunMetadata) -> AMRResult:
    """Stamp the run pipeline version onto AMR rows that lack a tool_version."""
    if result.tool_version:
        return result
    return result.model_copy(update={"tool_version": metadata.pipeline_version})
