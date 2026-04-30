"""
taxprofiler Kraken2 report parser — full ranked-list retention.

taxprofiler writes a Kraken2 kreport per (sample, database) pair at::

    kraken2/<sample>_<database>.kraken2.kraken2.report.txt

We reuse the shared Kraken2 parser (Grandeur's isolate parser uses the
same module) but pass ``top_only=False`` so every row survives.  The
database token parsed from the filename is forwarded as
``reference_database`` so downstream surveillance queries can filter
by "standard" vs. "viral-only" vs. custom DBs.

Filename token parsing is deliberately conservative: if we can't find
the ``.kraken2.`` separator we fall back to stripping the ``.report.txt``
suffix and treating the whole remainder as ``<sample>``, leaving the
DB name empty.
"""

from __future__ import annotations

from pathlib import Path

from shared.parsers import ParsedResult, RunMetadata
from shared.parsers import kraken2 as shared_kraken2

_REPORT_SUFFIXES = (
    ".kraken2.kraken2.report.txt",
    ".kraken2.report.txt",
    "_report.txt",
)


def parse(
    kraken_dir: Path,
    metadata: RunMetadata,
    *,
    tool_version: str | None = None,
) -> list[ParsedResult]:
    if not kraken_dir.exists():
        return []
    results: list[ParsedResult] = []
    for path in sorted(kraken_dir.iterdir()):
        if not path.is_file():
            continue
        stripped = _strip_report_suffix(path.name)
        if stripped is None:
            continue
        sample_id, db_name = _split_sample_and_db(stripped)
        if not sample_id:
            continue
        reference_db = db_name or shared_kraken2.DEFAULT_REFERENCE_DB
        results.extend(
            shared_kraken2.parse(
                path,
                metadata,
                sample_id=sample_id,
                tool_version=tool_version,
                reference_database=reference_db,
                top_only=False,
                species_only=False,
            )
        )
    return results


def _strip_report_suffix(name: str) -> str | None:
    for suffix in _REPORT_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return None


def _split_sample_and_db(stem: str) -> tuple[str, str]:
    """Split ``<sample>_<database>`` with a conservative heuristic.

    taxprofiler uses ``_`` as the separator but sample IDs themselves
    may contain underscores (AZ-META-001_lane1 etc.).  We split on the
    **last** underscore — if the user's database token happens to have
    one, they'll need to override via a config override (noted in the
    Session L learnings).
    """
    if "_" not in stem:
        return stem, ""
    sample, _, db = stem.rpartition("_")
    return sample, db
