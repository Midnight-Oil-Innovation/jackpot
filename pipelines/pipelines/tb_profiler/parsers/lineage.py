"""
TB-Profiler lineage + spoligotype parser.

TB-Profiler writes one JSON per sample at
``results/<sample>.results.json`` with a stable shape::

    {
        "id": "AZ-TB-001",
        "main_lin": "lineage4",
        "sub_lin": "lineage4.9",
        "drtype": "Sensitive",
        "spoligotype": {"octal": "777000377760771", ...},
        "pipeline": {"software_version": "6.2.0", "db_version": "2024-05-09"},
        "dr_variants": [...],   # handled by drug_resistance.py
        ...
    }

We emit a single :class:`TBTypingResult` ParsedResult per sample
carrying the lineage, sub-lineage, spoligotype, resistance profile,
and (when ``include_drug_resistance=True``) the per-drug susceptibility
map built by ``drug_resistance.build_who_susceptibility``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.parsers.types import ParsedResult, RunMetadata
from shared.schemas import TBTypingResult

from . import drug_resistance

RESULT_TYPE = "tb_typing_results"


class TBProfilerParseError(ValueError):
    """Raised when the TB-Profiler JSON is malformed or missing required keys."""


def parse(
    results_dir: Path,
    metadata: RunMetadata,
    *,
    include_drug_resistance: bool = True,
) -> list[ParsedResult]:
    if not results_dir.exists():
        return []
    parsed: list[ParsedResult] = []
    for path in sorted(results_dir.iterdir()):
        if not path.is_file() or not path.name.endswith(".results.json"):
            continue
        parsed.append(
            _parse_file(
                path,
                metadata=metadata,
                include_drug_resistance=include_drug_resistance,
            )
        )
    return parsed


def parse_file(
    path: Path,
    metadata: RunMetadata,
    *,
    include_drug_resistance: bool = True,
) -> ParsedResult:
    """Parse one ``.results.json`` file directly — convenience for tests."""
    if not path.exists():
        raise FileNotFoundError(f"TB-Profiler JSON not found: {path}")
    return _parse_file(
        path,
        metadata=metadata,
        include_drug_resistance=include_drug_resistance,
    )


def _parse_file(
    path: Path,
    *,
    metadata: RunMetadata,
    include_drug_resistance: bool,
) -> ParsedResult:
    try:
        data: dict[str, Any] = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise TBProfilerParseError(f"Cannot parse JSON: {path}") from exc
    sample_id = (data.get("id") or _sample_id_from_path(path)).strip()
    if not sample_id:
        raise TBProfilerParseError(f"TB-Profiler JSON has no sample id: {path}")
    pipeline = data.get("pipeline") or {}
    spoligotype = data.get("spoligotype") or {}
    who_map: dict | None = None
    if include_drug_resistance:
        who_map = drug_resistance.build_who_susceptibility(data)
    model = TBTypingResult(
        sample_id=sample_id,
        main_lineage=_blank_to_none(data.get("main_lin")),
        sub_lineage=_blank_to_none(data.get("sub_lin")),
        spoligotype=_blank_to_none(
            spoligotype.get("octal") if isinstance(spoligotype, dict) else None
        ),
        drug_resistance_profile=_blank_to_none(data.get("drtype")),
        who_drug_susceptibility=who_map,
        tbprofiler_version=pipeline.get("software_version") or metadata.pipeline_version,
        tbprofiler_db_version=_blank_to_none(pipeline.get("db_version")),
    )
    return ParsedResult.from_model(RESULT_TYPE, model)


def _sample_id_from_path(path: Path) -> str:
    name = path.name
    if name.endswith(".results.json"):
        return name[: -len(".results.json")]
    return path.stem


def _blank_to_none(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None
