"""
Grandeur BLAST-vs-local-DB parser.

Grandeur runs BLASTn against a curated local database as part of its
species confirmation check, writing tabular (``-outfmt 6``) output
under ``blast/<sample>_blast.tsv``.  The tabular format has 12 fixed
columns:

    qseqid sseqid pident length mismatch gapopen qstart qend
    sstart send evalue bitscore

Rather than explode every hit into a typed row, we emit a summary
``pipeline_metrics`` ParsedResult per sample — top-hit identity,
number of hits, best-hit subject id.  Used as context for the Kraken2
species call, not as a separately reportable entity.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from shared.parsers.types import ParsedResult, RunMetadata

RESULT_TYPE = "pipeline_metrics"
_ACCEPTED_SUFFIX = "_blast.tsv"


@dataclass(frozen=True)
class BlastSummary:
    sample_id: str
    total_hits: int
    top_subject: str | None
    top_pident: float | None
    top_bitscore: float | None


def parse(blast_dir: Path, metadata: RunMetadata) -> list[ParsedResult]:  # noqa: ARG001
    if not blast_dir.exists():
        return []
    results: list[ParsedResult] = []
    for path in sorted(blast_dir.iterdir()):
        if not path.is_file() or not path.name.endswith(_ACCEPTED_SUFFIX):
            continue
        sample_id = path.name[: -len(_ACCEPTED_SUFFIX)]
        if not sample_id:
            continue
        summary = _summarise(path, sample_id=sample_id)
        payload = {
            "sample_id": sample_id,
            "metric_group": "blast",
            "total_hits": summary.total_hits,
            "top_subject": summary.top_subject,
            "top_identity_percent": summary.top_pident,
            "top_bitscore": summary.top_bitscore,
            "source_file": f"blast/{path.name}",
        }
        # Payload keys with None values dropped so the metrics JSONB stays compact.
        payload = {k: v for k, v in payload.items() if v is not None}
        results.append(ParsedResult(result_type=RESULT_TYPE, payload=payload))
    return results


def _summarise(path: Path, *, sample_id: str) -> BlastSummary:
    with path.open(newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        hits = 0
        best: tuple[str, float, float] | None = None
        for row in reader:
            if len(row) < 12:
                continue
            hits += 1
            try:
                pident = float(row[2])
                bitscore = float(row[11])
            except ValueError:
                continue
            if best is None or bitscore > best[2]:
                best = (row[1], pident, bitscore)
    return BlastSummary(
        sample_id=sample_id,
        total_hits=hits,
        top_subject=best[0] if best else None,
        top_pident=best[1] if best else None,
        top_bitscore=best[2] if best else None,
    )
