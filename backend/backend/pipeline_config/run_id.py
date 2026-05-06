"""Run-scoped identifier and URI helpers (Critical Rule 25)."""

from __future__ import annotations

import secrets
import uuid

from backend.config import get_settings


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
