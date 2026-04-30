"""
Bracken abundance parser for nf-core/taxprofiler.

Bracken re-estimates read abundance at a specified rank using Kraken2
counts.  taxprofiler writes one TSV per (sample, database) pair at::

    bracken/<sample>_<database>.bracken.tsv

Columns (Bracken 2.x)::

    name, taxonomy_id, taxonomy_lvl, kraken_assigned_reads,
    added_reads, new_est_reads, fraction_total_reads

The ``fraction_total_reads`` column is 0.0–1.0; we multiply by 100 so
it matches ``TaxonomicProfile.abundance_percent`` (0–100).
"""

from __future__ import annotations

import csv
from pathlib import Path

from shared.parsers import ParsedResult, RunMetadata
from shared.schemas import TaxonomicProfile

RESULT_TYPE = "taxonomic_profile"
TOOL_NAME = "bracken"
DEFAULT_REFERENCE_DB = "bracken_standard"
_REPORT_SUFFIXES = (".bracken.tsv", ".bracken.txt")

_RANK_MAP = {
    "D": "domain",
    "P": "phylum",
    "C": "class",
    "O": "order",
    "F": "family",
    "G": "genus",
    "S": "species",
    "S1": "subspecies",
}


class BrackenParseError(ValueError):
    """Raised on malformed Bracken TSV input."""


def parse(
    bracken_dir: Path,
    metadata: RunMetadata,
    *,
    tool_version: str | None = None,
) -> list[ParsedResult]:
    if not bracken_dir.exists():
        return []
    results: list[ParsedResult] = []
    for path in sorted(bracken_dir.iterdir()):
        if not path.is_file():
            continue
        stripped = _strip_suffix(path.name)
        if stripped is None:
            continue
        sample_id, db_name = _split_sample_and_db(stripped)
        if not sample_id:
            continue
        results.extend(
            parse_file(
                path,
                metadata,
                sample_id=sample_id,
                reference_database=db_name or DEFAULT_REFERENCE_DB,
                tool_version=tool_version,
            )
        )
    return results


def parse_file(
    path: Path,
    metadata: RunMetadata,
    *,
    sample_id: str,
    reference_database: str = DEFAULT_REFERENCE_DB,
    tool_version: str | None = None,
) -> list[ParsedResult]:
    if not path.exists():
        raise FileNotFoundError(f"Bracken TSV not found: {path}")
    results: list[ParsedResult] = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        required = {"name", "taxonomy_id", "taxonomy_lvl", "new_est_reads"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise BrackenParseError(
                f"Bracken TSV missing required columns: {path}",
            )
        for raw in reader:
            taxid = (raw.get("taxonomy_id") or "").strip()
            name = (raw.get("name") or "").strip()
            if not taxid or not name:
                continue
            rank_code = (raw.get("taxonomy_lvl") or "").strip()
            rank = _RANK_MAP.get(rank_code, rank_code or None)
            fraction = _float(raw.get("fraction_total_reads"))
            abundance = round(fraction * 100, 4) if fraction is not None else None
            read_count = _int(raw.get("new_est_reads"))
            model = TaxonomicProfile(
                sample_id=sample_id,
                taxon_id=taxid,
                taxon_name=name,
                rank=rank,
                abundance_percent=abundance,
                read_count=read_count,
                reference_database=reference_database,
                tool_name=TOOL_NAME,
                tool_version=tool_version or metadata.pipeline_version,
            )
            results.append(ParsedResult.from_model(RESULT_TYPE, model))
    return results


def _strip_suffix(name: str) -> str | None:
    for suf in _REPORT_SUFFIXES:
        if name.endswith(suf):
            return name[: -len(suf)]
    return None


def _split_sample_and_db(stem: str) -> tuple[str, str]:
    if "_" not in stem:
        return stem, ""
    sample, _, db = stem.rpartition("_")
    return sample, db


def _float(raw: str | None) -> float | None:
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError:
        return None


def _int(raw: str | None) -> int | None:
    f = _float(raw)
    return int(f) if f is not None else None
