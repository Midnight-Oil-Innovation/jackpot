"""
mycosnp fungal typing parser.

When mycosnp is run against an MLST-supported fungal species (e.g.
Candida auris, Cryptococcus neoformans) it writes a per-sample TSV at::

    typing/<sample>_<scheme>.tsv

with columns::

    sample_id    scheme    sequence_type    clade    allele_calls

(allele_calls is a ``|``-separated ``locus:allele`` list).  Absent when
the input species has no fungal MLST scheme — parser silently returns
an empty list in that case.
"""

from __future__ import annotations

import csv
from pathlib import Path

from shared.parsers.types import ParsedResult, RunMetadata
from shared.schemas import TypingResult

RESULT_TYPE = "typing_results"
TOOL_NAME = "mycosnp_typing"
REQUIRED_COLUMNS = frozenset({"sample_id", "scheme", "sequence_type"})


class FungalTypingParseError(ValueError):
    """Raised when the typing TSV is present but malformed."""


def parse(typing_dir: Path, metadata: RunMetadata) -> list[ParsedResult]:
    if not typing_dir.exists():
        return []
    results: list[ParsedResult] = []
    for path in sorted(typing_dir.iterdir()):
        if not path.is_file() or not path.name.endswith(".tsv"):
            continue
        results.extend(_parse_file(path, metadata=metadata))
    return results


def _parse_file(path: Path, *, metadata: RunMetadata) -> list[ParsedResult]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise FungalTypingParseError(
                f"Fungal typing TSV {path.name} missing columns: {sorted(missing)}",
            )
        parsed: list[ParsedResult] = []
        for row in reader:
            sample_id = (row.get("sample_id") or "").strip()
            if not sample_id:
                continue
            model = TypingResult(
                sample_id=sample_id,
                scheme=row["scheme"].strip() or "fungal_mlst",
                scheme_version=_blank_to_none(row.get("scheme_version")),
                sequence_type=_blank_to_none(row.get("sequence_type")),
                clade=_blank_to_none(row.get("clade")),
                allele_calls=_parse_alleles(row.get("allele_calls")),
                tool_name=TOOL_NAME,
                tool_version=metadata.pipeline_version,
            )
            parsed.append(ParsedResult.from_model(RESULT_TYPE, model))
    return parsed


def _parse_alleles(raw: str | None) -> dict | None:
    if not raw:
        return None
    mapping: dict[str, str] = {}
    for token in raw.split("|"):
        token = token.strip()
        if not token or ":" not in token:
            continue
        locus, allele = token.split(":", 1)
        mapping[locus.strip()] = allele.strip()
    return mapping or None


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
