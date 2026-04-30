"""
GTDB-Tk summary parser for nf-core/mag.

GTDB-Tk emits one summary file per domain — bacteria and archaea::

    Taxonomy/GTDB-Tk/gtdbtk.bac120.summary.tsv
    Taxonomy/GTDB-Tk/gtdbtk.ar53.summary.tsv

The columns we rely on are a stable subset across GTDB-Tk 2.x
releases::

    user_genome    bin identifier (matches CheckM2 Name column)
    classification d__Bacteria;p__...;c__...;o__...;f__...;g__...;s__...
    classification_method   ANI / placement / ...
    closest_genome_reference_radius, other_related_references, ...

Each accepted row becomes one :class:`TaxonomicProfile`.  The MAG bin is
itself the "sample" from GTDB-Tk's perspective — so ``sample_id`` on
the emitted row is set to the **bin_id** (matching the
``MAGQC.bin_id`` produced by CheckM2).  The backend will have already
registered a derived sample for that bin_id (linked to the parent
metagenomic sample via ``sample_associations``) by the time this row
is written.

No call → empty results list.  An ``Unclassified`` row with no
discernible lineage is skipped rather than emitted as a placeholder.
"""

from __future__ import annotations

import csv
from pathlib import Path

from shared.parsers import ParsedResult, RunMetadata
from shared.schemas import TaxonomicProfile

RESULT_TYPE = "taxonomic_profile"
TOOL_NAME = "gtdbtk"
DEFAULT_REFERENCE_DB = "GTDB"

_SEARCH_DIRS = (
    "Taxonomy/GTDB-Tk",
    "Taxonomy/GTDBTk",
    "Taxonomy/gtdbtk",
    "GTDBTk",
    "GTDB-Tk",
    "gtdbtk",
)
_SUMMARY_GLOBS = ("gtdbtk.*.summary.tsv", "*.summary.tsv")

_RANK_PREFIXES = {
    "d__": "domain",
    "p__": "phylum",
    "c__": "class",
    "o__": "order",
    "f__": "family",
    "g__": "genus",
    "s__": "species",
}


class GTDBTkParseError(ValueError):
    """Raised when the GTDB-Tk summary is missing required columns."""


def parse(
    output_dir: Path,
    metadata: RunMetadata,
    *,
    tool_version: str | None = None,
    reference_database: str = DEFAULT_REFERENCE_DB,
) -> list[ParsedResult]:
    summaries = _locate_summaries(output_dir)
    results: list[ParsedResult] = []
    for summary in summaries:
        results.extend(
            parse_summary(
                summary,
                metadata,
                tool_version=tool_version,
                reference_database=reference_database,
            )
        )
    return results


def parse_summary(
    summary: Path,
    metadata: RunMetadata,
    *,
    tool_version: str | None = None,
    reference_database: str = DEFAULT_REFERENCE_DB,
) -> list[ParsedResult]:
    if not summary.exists():
        raise FileNotFoundError(f"GTDB-Tk summary not found: {summary}")
    rows: list[ParsedResult] = []
    with summary.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if (
            reader.fieldnames is None
            or "user_genome" not in reader.fieldnames
            or "classification" not in reader.fieldnames
        ):
            raise GTDBTkParseError(
                f"GTDB-Tk summary missing required columns: {summary}",
            )
        for raw in reader:
            bin_id = (raw.get("user_genome") or "").strip()
            classification = (raw.get("classification") or "").strip()
            if not bin_id or not classification:
                continue
            if classification == "Unclassified":
                continue
            rank, name = _most_specific_rank(classification)
            if name is None:
                continue
            model = TaxonomicProfile(
                sample_id=bin_id,
                taxon_id=classification,
                taxon_name=name,
                rank=rank,
                lineage=classification,
                reference_database=reference_database,
                tool_name=TOOL_NAME,
                tool_version=tool_version or metadata.pipeline_version,
            )
            rows.append(ParsedResult.from_model(RESULT_TYPE, model))
    return rows


def _locate_summaries(output_dir: Path) -> list[Path]:
    if not output_dir.exists():
        return []
    found: list[Path] = []
    for sub in _SEARCH_DIRS:
        base = output_dir / sub
        if not base.exists():
            continue
        for pattern in _SUMMARY_GLOBS:
            found.extend(sorted(base.glob(pattern)))
        if found:
            return _dedupe(found)
    for pattern in _SUMMARY_GLOBS:
        found.extend(sorted(output_dir.glob(pattern)))
    return _dedupe(found)


def _dedupe(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def _most_specific_rank(classification: str) -> tuple[str | None, str | None]:
    """Walk a GTDB classification from species back to domain; return the
    lowest populated rank.
    """
    parts = [p.strip() for p in classification.split(";") if p.strip()]
    for part in reversed(parts):
        prefix = part[:3]
        value = part[3:].strip()
        if prefix in _RANK_PREFIXES and value:
            return _RANK_PREFIXES[prefix], value
    return None, None
