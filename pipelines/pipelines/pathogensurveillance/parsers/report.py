"""
pathogensurveillance interactive HTML report collector.

1.1.0 writes a single report per run at::

    report/pathogensurveillance_report.html

Accepted alternates cover minor-release rename drift:

* ``report.html``
* ``psv_report.html``
* ``pathogensurveillance.html``

The report is served in the JACKPOT UI via a presigned URL inside an
iframe (see ``jackpot-frontend/pages/pipelines.py``); the frontend
only needs the sample_files row to locate the object.

Emitted as a single run-level ``FileArtifact`` with
``file_subtype='report'`` — the backend links it to every sample in
the run via ``sample_associations`` (same pattern as the phylogeny
trees).
"""

from __future__ import annotations

from pathlib import Path

from shared.parsers.types import FileArtifact, RunMetadata

FILE_TYPE = "html"
FILE_SUBTYPE = "report"
RUN_LEVEL_SAMPLE_ID = "_run_"

_ACCEPTED_NAMES = {
    "pathogensurveillance_report.html",
    "pathogensurveillance.html",
    "psv_report.html",
    "report.html",
}


def collect(report_dir: Path, metadata: RunMetadata) -> list[FileArtifact]:  # noqa: ARG001
    if not report_dir.exists():
        return []
    artifacts: list[FileArtifact] = []
    seen: set[str] = set()
    for path in sorted(report_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name.lower() not in _ACCEPTED_NAMES:
            continue
        rel = str(path.relative_to(report_dir.parent))
        if rel in seen:
            continue
        seen.add(rel)
        artifacts.append(
            FileArtifact(
                sample_id=RUN_LEVEL_SAMPLE_ID,
                relative_path=rel,
                file_type=FILE_TYPE,
                file_subtype=FILE_SUBTYPE,
            )
        )
    return artifacts
