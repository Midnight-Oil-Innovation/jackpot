"""
Grandeur Kraken2 parser — single-organism species ID.

Grandeur writes ``kraken2/<sample>_report.txt`` per sample.  Because
Grandeur targets single-organism isolates rather than communities, we
keep only the top species-level hit (see shared ``kraken2`` parser:
``top_only=True``).
"""

from __future__ import annotations

from pathlib import Path

from shared.parsers import kraken2 as shared_kraken2
from shared.parsers.types import ParsedResult, RunMetadata

_REPORT_SUFFIX = "_report.txt"


def parse(
    kraken_dir: Path,
    metadata: RunMetadata,
    *,
    tool_version: str | None = None,
    reference_database: str = shared_kraken2.DEFAULT_REFERENCE_DB,
) -> list[ParsedResult]:
    if not kraken_dir.exists():
        return []
    results: list[ParsedResult] = []
    for path in sorted(kraken_dir.iterdir()):
        if not path.is_file() or not path.name.endswith(_REPORT_SUFFIX):
            continue
        sample_id = path.name[: -len(_REPORT_SUFFIX)]
        if not sample_id:
            continue
        results.extend(
            shared_kraken2.parse(
                path,
                metadata,
                sample_id=sample_id,
                tool_version=tool_version,
                reference_database=reference_database,
                top_only=True,
            )
        )
    return results
