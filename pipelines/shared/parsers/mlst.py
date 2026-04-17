"""
Tseemann ``mlst`` TSV parser — shared by bactopia and Grandeur.

``mlst`` (https://github.com/tseemann/mlst) writes a tab-separated line
per input contig:

    <filename>\\t<scheme>\\t<ST>\\t<locus1>(<allele>)\\t...(7 loci)

There is no header row.  We parse positionally, strip the allele
parenthesis into an ``allele_calls`` dict, and emit one
:class:`TypingResult` per non-empty row.  The schema name is
preserved verbatim (e.g. ``senterica``, ``ecoli``, ``abaumannii_2``).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from shared.parsers.types import ParsedResult, RunMetadata
from shared.schemas import TypingResult

RESULT_TYPE = "typing_results"
TOOL_NAME = "mlst"

_ALLELE_RE = re.compile(r"^(?P<locus>[A-Za-z0-9_]+)\((?P<allele>[^)]+)\)$")


class MLSTParseError(ValueError):
    """Raised on malformed mlst TSV input."""


def parse(
    path: Path,
    metadata: RunMetadata,
    *,
    sample_id: str | None = None,
    tool_version: str | None = None,
) -> list[ParsedResult]:
    """Parse a Tseemann ``mlst`` TSV into TypingResult ParsedResults."""
    if not path.exists():
        raise FileNotFoundError(f"mlst TSV not found: {path}")
    results: list[ParsedResult] = []
    with path.open(newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if not row or not row[0].strip():
                continue
            # Defensive: mlst has no header, but some pipelines prepend one.
            if row[0].lower() in {"file", "filename", "sample", "sample_id"}:
                continue
            if len(row) < 3:
                raise MLSTParseError(
                    f"mlst row has fewer than 3 columns: {row!r}",
                )
            results.append(
                _parse_row(
                    row,
                    default_sample_id=sample_id,
                    tool_version=tool_version or metadata.pipeline_version,
                )
            )
    return results


def _parse_row(
    row: list[str],
    *,
    default_sample_id: str | None,
    tool_version: str,
) -> ParsedResult:
    filename, scheme, st, *loci = row
    resolved_sample_id = default_sample_id or _sample_id_from_filename(filename)
    allele_calls: dict[str, str] = {}
    for cell in loci:
        cell = cell.strip()
        if not cell or cell == "-":
            continue
        match = _ALLELE_RE.match(cell)
        if match:
            allele_calls[match.group("locus")] = match.group("allele")
        else:
            # e.g. "adk(~10)" when mlst couldn't call cleanly — keep raw.
            allele_calls[cell] = cell
    model = TypingResult(
        sample_id=resolved_sample_id,
        scheme=scheme or "mlst",
        sequence_type=_blank_to_none(st),
        allele_calls=allele_calls or None,
        tool_name=TOOL_NAME,
        tool_version=tool_version,
    )
    return ParsedResult.from_model(RESULT_TYPE, model)


def _sample_id_from_filename(filename: str) -> str:
    name = Path(filename).name
    for suffix in (".fa.gz", ".fasta.gz", ".fa", ".fasta", ".fna", ".contigs"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or stripped == "-":
        return None
    return stripped
