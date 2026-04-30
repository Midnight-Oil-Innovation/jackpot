"""
Kraken2 report parser — shared by Grandeur and taxprofiler (Session L).

A Kraken2 report is a six-column TSV:

    <pct>\\t<clade_reads>\\t<taxon_reads>\\t<rank>\\t<taxid>\\t<name>

For **single-organism isolate** use (Grandeur) we keep only the top
``S`` (species) row — the platform spec requires storing the top hit
only, not a full ranked list.  For metagenomic use (Session L) pass
``top_only=False`` to retain every species / genus / higher rank
supplied.
"""

from __future__ import annotations

import csv
from pathlib import Path

from shared.parsers.types import ParsedResult, RunMetadata
from shared.schemas import TaxonomicProfile

RESULT_TYPE = "taxonomic_profile"
TOOL_NAME = "kraken2"
DEFAULT_REFERENCE_DB = "kraken2_standard"


class Kraken2ParseError(ValueError):
    """Raised on malformed Kraken2 report input."""


def parse(
    path: Path,
    metadata: RunMetadata,
    *,
    sample_id: str,
    tool_version: str | None = None,
    reference_database: str = DEFAULT_REFERENCE_DB,
    top_only: bool = True,
    species_only: bool = True,
) -> list[ParsedResult]:
    """
    Parameters
    ----------
    top_only
        When ``True`` (isolate use), keep only the single highest
        clade-reads row.  Set to ``False`` for metagenomic profiling
        (taxprofiler) to retain a ranked list.
    species_only
        When ``True`` (default), filter to rank ``S`` rows before
        ``top_only`` selection, falling back to all ranks only if no
        species row is present.  Set to ``False`` to retain every row
        regardless of rank — required for taxprofiler's full ranked
        output.
    """
    if not path.exists():
        raise FileNotFoundError(f"Kraken2 report not found: {path}")
    rows = list(_iter_rows(path))
    if not rows:
        return []
    if species_only:
        species_rows = [r for r in rows if r["rank"] == "S"]
        selected = species_rows or rows
    else:
        selected = rows
    if top_only:
        # Highest clade-read count wins.
        top = max(selected, key=lambda r: r["clade_reads"])
        selected = [top]
    results: list[ParsedResult] = []
    for row in selected:
        model = TaxonomicProfile(
            sample_id=sample_id,
            taxon_id=row["taxid"],
            taxon_name=row["name"],
            rank=row["rank"],
            abundance_percent=row["percent"],
            read_count=row["clade_reads"],
            reference_database=reference_database,
            tool_name=TOOL_NAME,
            tool_version=tool_version or metadata.pipeline_version,
        )
        results.append(ParsedResult.from_model(RESULT_TYPE, model))
    return results


def _iter_rows(path: Path):
    with path.open(newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        for raw in reader:
            if not raw:
                continue
            if len(raw) < 6:
                raise Kraken2ParseError(
                    f"Kraken2 row has fewer than 6 columns: {raw!r}",
                )
            try:
                percent = float(raw[0].strip())
                clade_reads = int(raw[1].strip())
                taxon_reads = int(raw[2].strip())
            except ValueError as exc:
                raise Kraken2ParseError(
                    f"Kraken2 numeric field parse failure: {raw!r}",
                ) from exc
            yield {
                "percent": percent,
                "clade_reads": clade_reads,
                "taxon_reads": taxon_reads,
                "rank": raw[3].strip(),
                "taxid": raw[4].strip(),
                "name": raw[5].strip(),
            }
