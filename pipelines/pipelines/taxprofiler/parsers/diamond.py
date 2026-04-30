"""
DIAMOND protein profile summary parser for nf-core/taxprofiler.

DIAMOND's default taxprofiler output is tabular — every row is one
alignment hit against a reference protein.  We don't store the per-hit
detail in a typed table: instead we summarise into a single
``pipeline_metrics`` row per (sample, database) capturing

* ``total_hits``
* ``top_subject``         — highest-bitscore subject sequence
* ``top_bitscore``
* ``top_identity_percent``

taxprofiler emits DIAMOND under ``diamond/<sample>_<db>.diamond.tsv``
using the standard BLAST outfmt-6 column ordering::

    qseqid, sseqid, pident, length, mismatch, gapopen, qstart,
    qend, sstart, send, evalue, bitscore

Malformed rows (too few columns, non-numeric bitscore) are skipped;
an input with only malformed rows still emits a summary with
``total_hits = 0`` so the absence of DIAMOND hits is preserved as a
result rather than silently dropped.
"""

from __future__ import annotations

import csv
from pathlib import Path

from shared.parsers import ParsedResult, RunMetadata

RESULT_TYPE = "pipeline_metrics"
TOOL_NAME = "diamond"
_REPORT_SUFFIXES = (".diamond.tsv", ".diamond.txt")
_MIN_COLUMNS = 12


def parse(
    diamond_dir: Path,
    metadata: RunMetadata,
    *,
    tool_version: str | None = None,
) -> list[ParsedResult]:
    if not diamond_dir.exists():
        return []
    results: list[ParsedResult] = []
    for path in sorted(diamond_dir.iterdir()):
        if not path.is_file():
            continue
        stripped = _strip_suffix(path.name)
        if stripped is None:
            continue
        sample_id, db_name = _split_sample_and_db(stripped)
        if not sample_id:
            continue
        results.append(
            _summarise(
                path,
                metadata,
                sample_id=sample_id,
                reference_database=db_name,
                tool_version=tool_version,
            )
        )
    return results


def _summarise(
    path: Path,
    metadata: RunMetadata,
    *,
    sample_id: str,
    reference_database: str,
    tool_version: str | None,
) -> ParsedResult:
    total_hits = 0
    top_subject: str | None = None
    top_bitscore: float | None = None
    top_identity: float | None = None
    with path.open(newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        for raw in reader:
            if len(raw) < _MIN_COLUMNS:
                continue
            bitscore = _float(raw[11])
            identity = _float(raw[2])
            if bitscore is None:
                continue
            total_hits += 1
            if top_bitscore is None or bitscore > top_bitscore:
                top_bitscore = bitscore
                top_identity = identity
                top_subject = raw[1].strip()
    payload = {
        "sample_id": sample_id,
        "total_hits": total_hits,
        "tool_name": TOOL_NAME,
        "tool_version": tool_version or metadata.pipeline_version,
    }
    if reference_database:
        payload["reference_database"] = reference_database
    if top_subject is not None:
        payload["top_subject"] = top_subject
    if top_bitscore is not None:
        payload["top_bitscore"] = top_bitscore
    if top_identity is not None:
        payload["top_identity_percent"] = top_identity
    return ParsedResult(result_type=RESULT_TYPE, payload=payload)


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


def _float(raw: str) -> float | None:
    try:
        return float(raw.strip())
    except (ValueError, AttributeError):
        return None
