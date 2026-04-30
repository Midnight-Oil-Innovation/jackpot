"""
pathogensurveillance sendsketch identification parser.

nf-core/pathogensurveillance runs BBTools ``sendsketch.sh`` against RefSeq
to get a rough-cut identification before it selects a reference for
variant calling.  Typical output looks like::

    Query: AZ-PSV-001.contigs.fa   Sketches: 1   DB: RefSeq
    WKID    KID     ANI     Complt  Contam  Matches  Unique  noHit  TaxID  \
        gSize   gSeqs   taxName
    97.85   96.42   98.12   99.5    0.3     9876     8765    123    562    \
        4876523 58      Escherichia coli
    96.50   95.01   97.82   99.1    0.4     9800     8700    130    28901  \
        5000000 30      Salmonella enterica

We emit **one** ``TaxonomicProfile`` per sample — the top-ranked hit
(first data row after the header).  ``abundance_percent`` is filled
from the ``ANI`` column (average nucleotide identity) since sendsketch
is a sketch-based distance metric, not an abundance estimator;
downstream consumers treat abundance_percent on sendsketch rows as
an identity score, which spec.md §Session M accepts.

Falls back gracefully when the header is missing (some 1.1.0 releases
skip it for empty queries) and yields no result for that sample rather
than raising.
"""

from __future__ import annotations

import csv
from pathlib import Path

from shared.parsers.types import ParsedResult, RunMetadata
from shared.schemas import TaxonomicProfile

RESULT_TYPE = "taxonomic_profile"
TOOL_NAME = "sendsketch"
DEFAULT_REFERENCE_DB = "RefSeq"

_ACCEPTED_SUFFIXES = (".sendsketch.txt", ".sendsketch.tsv", "_sendsketch.txt")
_REQUIRED_COLUMNS = {"TaxID", "taxName"}


class SendsketchParseError(ValueError):
    """Raised when a sendsketch file has no parseable data rows."""


def parse(
    sendsketch_dir: Path,
    metadata: RunMetadata,
    *,
    tool_version: str | None = None,
) -> list[ParsedResult]:
    if not sendsketch_dir.exists():
        return []
    results: list[ParsedResult] = []
    for path in sorted(sendsketch_dir.iterdir()):
        if not path.is_file():
            continue
        sample_id = _sample_id(path.name)
        if sample_id is None:
            continue
        top = _parse_top_hit(path)
        if top is None:
            # Empty sendsketch output is not an error — some isolates
            # produce no sketch hits above the pipeline's threshold.
            continue
        model = TaxonomicProfile(
            sample_id=sample_id,
            taxon_id=top["taxid"],
            taxon_name=top["taxon_name"],
            rank="species",
            abundance_percent=top["ani"],
            reference_database=DEFAULT_REFERENCE_DB,
            tool_name=TOOL_NAME,
            tool_version=tool_version or metadata.pipeline_version,
        )
        results.append(ParsedResult.from_model(RESULT_TYPE, model))
    return results


def _sample_id(filename: str) -> str | None:
    for suffix in _ACCEPTED_SUFFIXES:
        if filename.endswith(suffix):
            stem = filename[: -len(suffix)]
            return stem or None
    return None


def _parse_top_hit(path: Path) -> dict | None:
    """Return the top row of the sendsketch table or ``None`` if empty."""
    header_row: list[str] | None = None
    with path.open(newline="") as f:
        # sendsketch writes a free-form preamble (``Query: ...``) before the
        # data table; skip until we see a line whose first cell is "WKID".
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if not row:
                continue
            first = row[0].strip()
            if not first or first.startswith("#"):
                continue
            if first == "WKID":
                header_row = [c.strip() for c in row]
                break
            # Some 1.1.0 releases skip the preamble entirely; if a data
            # line shows up before the header, treat the first whitespace
            # triple as columns and bail.
            if first.startswith("Query:"):
                continue
        if header_row is None:
            return None
        missing = _REQUIRED_COLUMNS - set(header_row)
        if missing:
            raise SendsketchParseError(
                f"sendsketch header missing required columns {sorted(missing)}: {header_row!r}"
            )
        for row in reader:
            if not row or all(not c.strip() for c in row):
                continue
            values = [c.strip() for c in row]
            if len(values) < len(header_row):
                continue
            mapped = dict(zip(header_row, values, strict=False))
            taxid = mapped.get("TaxID", "").strip()
            taxon_name = mapped.get("taxName", "").strip()
            if not taxid or not taxon_name:
                continue
            ani_raw = mapped.get("ANI", "").strip()
            try:
                ani = float(ani_raw) if ani_raw else None
            except ValueError:
                ani = None
            return {"taxid": taxid, "taxon_name": taxon_name, "ani": ani}
    return None
