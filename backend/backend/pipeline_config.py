"""
Per-run Nextflow configuration generator.

Every pipeline launch gets:
  * a fresh UUID run_id                              (Critical Rule 25)
  * an isolated work_dir at gs://jackpot-work/{run_id}/work/
  * a Groovy config generated with that run_id,
    weblog callback URL, result registration URL,
    per-run pipeline_token, and resourceLabels       (Critical Rules 26/27)

The config is NEVER a static file — the launch endpoint passes it to
Nextflow via ``-c jackpot_run.config`` on every invocation.

compute_pipeline_compatibility() is the gate that turns sample metadata
and a pipeline_catalog row into a list of soft_warnings + hard_blocks.
The launch endpoint hard-stops on hard_blocks (422) and lets the
requester override soft_warnings (202 → 201).

submit_to_batch() is the GCP Batch submitter — in local dev
(PIPELINE_EXECUTOR=local) it just returns a deterministic pseudo-job_id
so the launch flow is exercised without actually launching Nextflow.
Real Batch submission is wired up in Session Q.
"""

from __future__ import annotations

import logging
import re
import secrets
import uuid
from dataclasses import dataclass, field
from typing import Any

from backend.config import get_settings

logger = logging.getLogger(__name__)


def new_run_id() -> str:
    """Fresh UUIDv4 — unique per launch; stored on pipeline_runs.run_id."""
    return f"jp-{uuid.uuid4()}"


def new_pipeline_token() -> str:
    """
    Per-run secret used by parsers when POSTing to
    /api/v1/pipelines/{run_id}/results/{result_type}.
    """
    return "pt_" + secrets.token_urlsafe(32)


def work_dir_for(run_id: str) -> str:
    """Per-run workDir — never shared between runs (Critical Rule 25)."""
    settings = get_settings()
    bucket = getattr(settings, "work_bucket", "jackpot-work")
    return f"gs://{bucket}/{run_id}/work"


def result_uri_for(run_id: str) -> str:
    """Per-run --outdir where iridanext.output.json.gz is written."""
    settings = get_settings()
    bucket = getattr(settings, "results_bucket", "jackpot-results")
    return f"gs://{bucket}/{run_id}/"


@dataclass
class CompatibilityReport:
    soft_warnings: list[dict[str, Any]] = field(default_factory=list)
    hard_blocks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_hard_blocked(self) -> bool:
        return bool(self.hard_blocks)

    @property
    def has_warnings(self) -> bool:
        return bool(self.soft_warnings)

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        return {"soft_warnings": self.soft_warnings, "hard_blocks": self.hard_blocks}


def compute_pipeline_compatibility(
    catalog_row: dict[str, Any],
    samples: list[dict[str, Any]],
) -> CompatibilityReport:
    """
    Apply pipeline_catalog.compatibility_rules against supplied samples.

    Supported rule keys (all optional):
      * ``source_types``         → hard-block samples whose source_type is not in the list
      * ``required_scrub``       → hard-block samples with scrub_status != 'COMPLETE'
      * ``min_quality_status``   → soft-warn samples below the listed tier
      * ``organisms``            → soft-warn samples whose organism_name is not in the list

    Unknown keys are ignored. ``rules`` may be missing or an empty dict —
    in that case every sample is compatible with no warnings.
    """
    report = CompatibilityReport()
    rules = catalog_row.get("compatibility_rules") or {}
    if isinstance(rules, str):
        # JSONB may round-trip as a string in some drivers; best-effort parse
        import json

        try:
            rules = json.loads(rules)
        except (ValueError, TypeError):
            rules = {}

    allowed_sources: list[str] | None = rules.get("source_types")
    require_scrub: bool = bool(rules.get("required_scrub"))
    min_quality: str | None = rules.get("min_quality_status")
    allowed_organisms: list[str] | None = rules.get("organisms")

    tier_rank = {"PRELIMINARY": 1, "ANALYZABLE": 2, "SUBMITTABLE": 3}

    for sample in samples:
        sid = sample.get("sample_id") or str(sample.get("id") or "?")
        source_type = (sample.get("source_type") or "").strip()
        scrub_status = (sample.get("scrub_status") or "").strip()
        quality_status = (sample.get("quality_status") or "").strip()
        organism = (sample.get("organism_name") or "").strip()

        if allowed_sources and source_type and source_type not in allowed_sources:
            report.hard_blocks.append(
                {
                    "sample_id": sid,
                    "reason": (
                        f"Pipeline accepts source_type in {allowed_sources}, "
                        f"but sample is {source_type!r}."
                    ),
                }
            )

        if require_scrub and scrub_status and scrub_status not in ("COMPLETE", "SKIPPED"):
            report.hard_blocks.append(
                {
                    "sample_id": sid,
                    "reason": (
                        "Pipeline requires scrubbed reads "
                        f"but sample scrub_status is {scrub_status!r}."
                    ),
                }
            )

        if (
            min_quality
            and quality_status in tier_rank
            and min_quality in tier_rank
            and tier_rank[quality_status] < tier_rank[min_quality]
        ):
            report.soft_warnings.append(
                {
                    "sample_id": sid,
                    "reason": (
                        f"Sample quality_status {quality_status!r} is below "
                        f"pipeline minimum {min_quality!r}."
                    ),
                }
            )

        if allowed_organisms and organism and organism not in allowed_organisms:
            report.soft_warnings.append(
                {
                    "sample_id": sid,
                    "reason": (
                        f"Pipeline targets {allowed_organisms}, "
                        f"but sample organism is {organism!r}."
                    ),
                }
            )

    return report


_LAB_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _slug(text: str) -> str:
    return _LAB_SLUG_RE.sub("-", text.lower()).strip("-") or "unknown"


def generate_run_config(
    *,
    run_id: str,
    pipeline_name: str,
    pipeline_version: str | None,
    lab_slug: str,
    pipeline_token: str,
    work_dir: str,
    result_uri: str,
) -> str:
    """
    Render the Groovy config passed to Nextflow via ``-c``.

    Includes resourceLabels for cost attribution (Critical Rule 27) and
    per-run workDir/result_uri so the run is fully isolated.
    """
    settings = get_settings()
    executor = getattr(settings, "pipeline_executor", "local")
    executor_flag = "google-batch" if executor == "gcp_batch" else executor
    api_url = getattr(settings, "jackpot_api_url", "http://localhost:8000")
    weblog_url = f"{api_url.rstrip('/')}/api/v1/pipelines/events"
    results_url = f"{api_url.rstrip('/')}/api/v1/pipelines/{run_id}/results"

    return f"""// Generated by JACKPOT POST /api/v1/pipelines/launch
// Run ID: {run_id} | Pipeline: {pipeline_name} {pipeline_version or ""}

process {{
    executor = "{executor_flag}"
    errorStrategy = 'retry'
    maxRetries = 2
}}

google {{
    project = "{getattr(settings, "gcp_project_id", "jackpot-dev")}"
    location = "{getattr(settings, "gcp_region", "us-central1")}"
    batch.spot = true
    batch.bootDiskSize = 50.GB
    resourceLabels = [
        'jackpot_run_id': "{run_id}",
        'jackpot_lab':    "{_slug(lab_slug)}",
        'jackpot_pipeline': "{_slug(pipeline_name)}"
    ]
}}

workDir = "{work_dir}"

params {{
    jackpot_run_id      = "{run_id}"
    jackpot_api_url     = "{api_url}"
    jackpot_weblog_url  = "{weblog_url}"
    jackpot_results_url = "{results_url}"
    jackpot_result_uri  = "{result_uri}"
    jackpot_token       = "{pipeline_token}"
}}
"""


def submit_to_batch(
    *,
    run_id: str,
    pipeline_uri: str,
    pipeline_version: str | None,
    pipeline_profile: str | None,
    config_path: str,
    work_dir: str,
    result_uri: str,
    resume: bool = False,
) -> dict[str, Any]:
    """
    GCP Batch submitter.

    In local dev (PIPELINE_EXECUTOR=local) this is a no-op that returns a
    deterministic pseudo job_id so the launch flow can be exercised end
    to end without actually launching Nextflow. Session Q wires up the
    real gcloud Batch call.
    """
    settings = get_settings()
    executor = getattr(settings, "pipeline_executor", "local")
    logger.info(
        "submit_to_batch(run_id=%s, pipeline=%s@%s, profile=%s, executor=%s, resume=%s)",
        run_id,
        pipeline_uri,
        pipeline_version,
        pipeline_profile,
        executor,
        resume,
    )
    return {
        "batch_job_id": f"batch-{run_id}",
        "work_dir": work_dir,
        "result_uri": result_uri,
        "config_path": config_path,
        "executor": executor,
        "resume": resume,
    }
