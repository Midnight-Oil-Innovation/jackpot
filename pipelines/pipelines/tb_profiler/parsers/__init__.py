"""
TB-Profiler pipeline-level parser.

TB-Profiler writes one JSON per sample at ``results/<sample>.results.json``.
The top-level :func:`parse` emits both:

1. One :class:`TBTypingResult` per sample (lineage, spoligotype, DR
   summary with per-drug WHO susceptibility map) to
   ``tb_typing_results``.
2. One :class:`AMRResult` per (variant, drug) pair so TB resistance
   surfaces in the platform-wide AMR search — with
   ``reference_database=WHO_catalogue`` per spec.
"""

from __future__ import annotations

import json
from pathlib import Path

from shared.parsers import ParsedResult, RunMetadata

from . import drug_resistance, lineage

SUPPORTED_PIPELINE_VERSIONS: list[str] = [
    "5.0.0",
    "6.0.0",
    "6.1.0",
    "6.2.0",
]


def parse(output_dir: Path, metadata: RunMetadata) -> list[ParsedResult]:
    """Emit TB typing + mirrored AMR results for every JSON under ``results/``."""
    results_dir = output_dir / "results"
    if not results_dir.exists():
        return []
    parsed: list[ParsedResult] = []
    for path in sorted(results_dir.iterdir()):
        if not path.is_file() or not path.name.endswith(".results.json"):
            continue
        data = json.loads(path.read_text())
        parsed.append(
            lineage.parse_file(path, metadata, include_drug_resistance=True),
        )
        parsed.extend(drug_resistance.to_amr_results(path, data, metadata))
    return parsed


def collect_files(output_dir: Path, metadata: RunMetadata) -> list:  # noqa: ARG001
    """TB-Profiler produces no registrable FileArtifact outputs."""
    return []


__all__ = [
    "SUPPORTED_PIPELINE_VERSIONS",
    "collect_files",
    "drug_resistance",
    "lineage",
    "parse",
]
