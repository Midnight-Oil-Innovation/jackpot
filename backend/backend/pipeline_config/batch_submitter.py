"""GCP Batch submitter (legacy single-executor path)."""

from __future__ import annotations

import logging
from typing import Any

from backend.config import get_settings

logger = logging.getLogger(__name__)


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
