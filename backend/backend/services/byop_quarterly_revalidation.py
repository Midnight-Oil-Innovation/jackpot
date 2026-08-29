# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""B-BYOP-6 — quarterly BYOP revalidation background job (design doc §5.4).

Re-runs the B-BYOP-2 Stage 1 static validator (``services.byop_validator``,
via the router's ``_run_stage1`` operator-policy wrapper) against every
ACTIVE BYOP pipeline on a quarterly cadence (configurable; default 90 days)
to catch upstream rot that would otherwise surface only at launch time:

- deleted containers (``container_references`` check fails)
- expired / revoked licenses (``license`` check fails)
- vanished reference-data URLs (``reference_data`` check fails)

Per §5.4, a pipeline that fails revalidation transitions to ``DEACTIVATED``
with a notification to its registrar; prior ``pipeline_results`` rows are
untouched (immutability). Stage 2 (sandbox) is out of scope — this job is
Stage 1 revalidation only.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

import yaml
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.notifications import create_notification
from backend.routers.byop import ByopPipeline, _run_stage1

logger = logging.getLogger(__name__)

# §5.4: "Quarterly background validation job runs (configurable cadence;
# default 90 days)".
DEFAULT_REVALIDATION_INTERVAL_SECONDS = 90 * 24 * 3600

# Stage 1 check_name → upstream-rot condition it evidences.
ROT_CONDITIONS = {
    "container_references": "deleted_container",
    "license": "expired_license",
    "reference_data": "vanished_reference_data_url",
}


def revalidation_interval_seconds() -> int:
    """Cadence in seconds — env-configurable like the other BYOP knobs."""
    return int(
        os.environ.get(
            "JACKPOT_BYOP_REVALIDATION_INTERVAL_SECONDS",
            str(DEFAULT_REVALIDATION_INTERVAL_SECONDS),
        )
    )


def register(scheduler) -> None:
    """Wire the job onto the app's AsyncIOScheduler (called from main.py)."""
    scheduler.add_job(
        run_byop_quarterly_revalidation,
        "interval",
        seconds=revalidation_interval_seconds(),
        id="byop_quarterly_revalidation",
        replace_existing=True,
        max_instances=1,
    )


def _rot_conditions(report) -> list[str]:
    return [
        ROT_CONDITIONS[check.check_name]
        for check in report.checks
        if not check.passed and check.check_name in ROT_CONDITIONS
    ]


def _notify_registrar(pipeline: ByopPipeline, rot: list[str], db: Session) -> None:
    """§5.4 — failed re-validation notifies the registrar. Best-effort."""
    try:
        recipient_id = int(pipeline.registered_by_user_id)
    except (TypeError, ValueError):
        logger.warning(
            "BYOP pipeline %s: registrar id %r is not numeric; skipping notification",
            pipeline.id,
            pipeline.registered_by_user_id,
        )
        return
    create_notification(
        recipient_id=recipient_id,
        event_type="BYOP_REVALIDATION_FAILED",
        title=f"BYOP pipeline {pipeline.name}@{pipeline.version} deactivated",
        body=(
            "Quarterly revalidation failed"
            + (f" ({', '.join(rot)})" if rot else "")
            + ". The pipeline has been deactivated pending remediation."
        ),
        resource_type="byop_pipeline",
        resource_id=str(pipeline.id),
        action_url=None,
        db_conn=db,
    )


def _revalidate_one(pipeline: ByopPipeline, db: Session) -> bool:
    """Re-run Stage 1 on one pipeline, record the outcome. True = still valid."""
    now = datetime.now(UTC)
    manifest = yaml.safe_load(pipeline.manifest_yaml)
    if not isinstance(manifest, dict):
        raise ValueError("stored manifest_yaml is not a YAML mapping")

    report = _run_stage1(manifest)
    validation_log = "\n".join(
        f"[{'PASS' if c.passed else 'FAIL'}] {c.check_name}: {c.message}" for c in report.checks
    )

    if report.passed:
        pipeline.validation_log = validation_log
        pipeline.last_validated_at = now
        logger.info(
            "BYOP quarterly revalidation: pipeline %s (%s@%s) passed",
            pipeline.id,
            pipeline.name,
            pipeline.version,
        )
        return True

    rot = _rot_conditions(report)
    pipeline.validation_log = validation_log + (
        f"\n[ROT] upstream-rot conditions: {', '.join(rot)}" if rot else ""
    )
    pipeline.pipeline_status = "DEACTIVATED"
    pipeline.deactivated_at = now
    logger.warning(
        "BYOP quarterly revalidation: pipeline %s (%s@%s) FAILED; deactivated (rot conditions: %s)",
        pipeline.id,
        pipeline.name,
        pipeline.version,
        ", ".join(rot) or "none classified",
    )
    _notify_registrar(pipeline, rot, db)
    return False


def revalidate_active_byop_pipelines(db: Session) -> dict[str, int]:
    """Re-run Stage 1 against every ACTIVE BYOP pipeline.

    One bad pipeline never aborts the run: per-pipeline exceptions are
    logged, that pipeline's changes are rolled back, and the loop continues.
    Outcomes are committed per pipeline so failures stay isolated.
    """
    pipelines = db.query(ByopPipeline).filter(ByopPipeline.pipeline_status == "ACTIVE").all()
    counters = {"checked": 0, "passed": 0, "deactivated": 0, "errors": 0}
    for pipeline in pipelines:
        counters["checked"] += 1
        try:
            if _revalidate_one(pipeline, db):
                counters["passed"] += 1
            else:
                counters["deactivated"] += 1
            db.commit()
        except Exception:
            db.rollback()
            counters["errors"] += 1
            logger.exception(
                "BYOP quarterly revalidation: pipeline %s raised; continuing",
                pipeline.id,
            )
    logger.info("BYOP quarterly revalidation complete: %s", counters)
    return counters


async def run_byop_quarterly_revalidation() -> dict[str, int]:
    """Scheduler entrypoint — same shape as the other APScheduler jobs."""
    with get_db() as db:
        return revalidate_active_byop_pipelines(db)
