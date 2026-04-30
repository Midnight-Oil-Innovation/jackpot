"""
TB-Profiler drug resistance → WHO catalogue susceptibility + amr_results mirror.

TB-Profiler's JSON carries a ``dr_variants`` array with entries shaped
like::

    {
        "gene": "rpoB",
        "change": "p.Ser450Leu",
        "freq": 0.98,
        "drugs": [
            {"drug": "rifampicin", "confidence": "1) Assoc w R", "who_confidence": "Assoc w R"},
            ...
        ],
        "locus_tag": "Rv0667",
        "type": "missense",
    }

Two outputs are produced:

1. ``build_who_susceptibility`` — a compact ``{drug: {...}}`` dict that
   populates ``TBTypingResult.who_drug_susceptibility``.
2. ``to_amr_results`` — one :class:`AMRResult` ParsedResult per
   (variant, drug) pair, so TB drug resistance appears in platform-wide
   AMR searches with ``reference_database=WHO_catalogue`` (per spec).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.parsers.types import ParsedResult, RunMetadata
from shared.schemas import AMRResult

AMR_RESULT_TYPE = "amr_results"
TOOL_NAME = "tb-profiler"
REFERENCE_DATABASE = "WHO_catalogue"


def build_who_susceptibility(data: dict[str, Any]) -> dict | None:
    """Summarise ``dr_variants`` → ``{drug: {predicted, variants, who_confidence}}``."""
    variants = data.get("dr_variants") or []
    if not variants:
        return None
    by_drug: dict[str, dict[str, Any]] = {}
    for entry in variants:
        if not isinstance(entry, dict):
            continue
        gene = entry.get("gene")
        change = entry.get("change")
        freq = entry.get("freq")
        for drug_entry in entry.get("drugs") or []:
            if not isinstance(drug_entry, dict):
                continue
            drug = drug_entry.get("drug")
            if not drug:
                continue
            bucket = by_drug.setdefault(
                drug,
                {
                    "predicted": "resistant",
                    "variants": [],
                    "who_confidences": [],
                },
            )
            bucket["variants"].append(
                {
                    "gene": gene,
                    "change": change,
                    "frequency": freq,
                }
            )
            confidence = drug_entry.get("who_confidence") or drug_entry.get("confidence")
            if confidence and confidence not in bucket["who_confidences"]:
                bucket["who_confidences"].append(confidence)
    return by_drug or None


def to_amr_results(
    path: Path,
    data: dict[str, Any],
    metadata: RunMetadata,
) -> list[ParsedResult]:
    """Emit one AMRResult ParsedResult per (variant, drug) pair."""
    variants = data.get("dr_variants") or []
    if not variants:
        return []
    sample_id = (data.get("id") or "").strip() or _sample_id_from_path(path)
    pipeline = data.get("pipeline") or {}
    tool_version = pipeline.get("software_version") or metadata.pipeline_version
    db_version = pipeline.get("db_version")
    rows: list[ParsedResult] = []
    for entry in variants:
        if not isinstance(entry, dict):
            continue
        gene = entry.get("gene") or ""
        change = entry.get("change") or ""
        for drug_entry in entry.get("drugs") or []:
            if not isinstance(drug_entry, dict):
                continue
            drug = drug_entry.get("drug")
            if not drug:
                continue
            model = AMRResult(
                sample_id=sample_id,
                gene_symbol=gene or drug,
                gene_name=f"{gene} {change}".strip() or None,
                drug_class="antimycobacterial",
                drug=drug,
                resistance_phenotype="resistant",
                reference_database=REFERENCE_DATABASE,
                reference_accession=_reference_accession(db_version),
                tool_name=TOOL_NAME,
                tool_version=tool_version,
            )
            rows.append(ParsedResult.from_model(AMR_RESULT_TYPE, model))
    return rows


def _sample_id_from_path(path: Path) -> str:
    name = path.name
    if name.endswith(".results.json"):
        return name[: -len(".results.json")]
    return path.stem


def _reference_accession(db_version: str | None) -> str | None:
    if not db_version:
        return None
    return f"WHO-Catalogue/{db_version}"
