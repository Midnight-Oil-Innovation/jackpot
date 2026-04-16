"""
Pipelines router.

Implements:
  POST /api/v1/pipelines/events  — Nextflow weblog receiver (no auth,
                                   run_id acts as bearer token)

Stubs (Month 2 implementation):
  GET  /api/v1/pipelines/
  POST /api/v1/pipelines/launch
  GET  /api/v1/pipelines/{run_id}
  GET  /api/v1/pipelines/{run_id}/tasks
  GET  /api/v1/pipelines/{run_id}/results
  GET  /api/v1/pipelines/{run_id}/files
  POST /api/v1/pipelines/{run_id}/resume
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.database import execute_query, execute_write, get_db_dep
from backend.pipeline_results_loader import load_pipeline_results

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pipelines", tags=["pipelines"])


# ── Weblog event receiver ──────────────────────────────────────────────────────


def _handle_workflow_complete(
    run_id: str,
    event_body: dict[str, Any],
    conn: Any,
) -> None:
    """
    Triggered when Nextflow posts a workflow.complete event.
    Looks up the pipeline_run record, then calls the results loader.
    """
    # Look up the run record to get result_uri, pipeline name/version,
    # and the user who launched it
    rows = execute_query(
        """
        SELECT result_uri, pipeline_name, pipeline_version, launched_by_id
        FROM pipeline_runs
        WHERE run_id = :run_id
        """,
        {"run_id": run_id},
        conn=conn,
    )
    if not rows:
        logger.error("workflow.complete received for unknown run_id: %s", run_id)
        return

    run = rows[0]
    result_uri = run["result_uri"]

    if not result_uri:
        logger.error("pipeline_run %s has no result_uri — cannot load results", run_id)
        return

    # Mark run as completed in pipeline_runs
    workflow_stats = event_body.get("workflow", {})
    success_flag = workflow_stats.get("success", False)
    status = "completed" if success_flag else "failed"

    execute_write(
        """
        UPDATE pipeline_runs
        SET status = :status, completed_at = NOW()
        WHERE run_id = :run_id
        """,
        {"status": status, "run_id": run_id},
        conn=conn,
    )

    if not success_flag:
        logger.warning("Pipeline %s completed with failure — skipping result load", run_id)
        return

    # Load the results
    loader_result = load_pipeline_results(
        run_id=run_id,
        result_uri=result_uri,
        pipeline_name=run["pipeline_name"],
        pipeline_version=run["pipeline_version"],
        launched_by_id=run["launched_by_id"],
        conn=conn,
    )

    if not loader_result.success:
        logger.error(
            "Result loader errors for run %s: %s",
            run_id,
            loader_result.errors,
        )
    else:
        logger.info(
            "Results loaded for run %s: %d samples, %d files",
            run_id,
            len(loader_result.samples_updated),
            loader_result.files_registered,
        )


@router.post("/events")
def receive_pipeline_event(
    body: dict[str, Any],
    db=Depends(get_db_dep),  # noqa: B008
) -> dict:
    """
    Nextflow weblog receiver.

    Nextflow posts events here via -weblog during pipeline execution.
    No authentication — the run_id embedded in the event acts as a bearer.

    Handled events:
      workflow.started   → update pipeline_run status to 'running'
      workflow.complete  → load results from iridanext.output.json.gz
      process.submitted  → record task event
      process.started    → record task event
      process.completed  → record task event
      process.failed     → record task event, mark run failed

    All other events are stored as raw pipeline_events rows and ignored.
    """
    event = body.get("event", "")
    run_id = body.get("runId") or body.get("run_id", "")

    if not run_id:
        raise HTTPException(status_code=400, detail="Missing runId in event body")

    # Store the raw event regardless of type
    try:
        execute_write(
            """
            INSERT INTO pipeline_events (run_id, event_type, event_json, received_at)
            VALUES (:run_id, :event_type, :event_json, NOW())
            """,
            {
                "run_id": run_id,
                "event_type": event,
                "event_json": str(body),
            },
            conn=db,
        )
    except Exception as e:
        # Don't fail the response if event storage fails — Nextflow will retry
        logger.error("Failed to store pipeline event: %s", e)

    # Handle specific events
    if event == "workflow.started":
        try:
            execute_write(
                """
                UPDATE pipeline_runs
                SET status = 'running', launched_at = NOW()
                WHERE run_id = :run_id
                """,
                {"run_id": run_id},
                conn=db,
            )
        except Exception as e:
            logger.error("Failed to update run status to running: %s", e)

    elif event == "workflow.complete":
        try:
            _handle_workflow_complete(run_id=run_id, event_body=body, conn=db)
        except Exception as e:
            # Log but don't raise — Nextflow doesn't retry on 500
            logger.error("Error handling workflow.complete for %s: %s", run_id, e)

    elif event in ("process.submitted", "process.started", "process.completed", "process.failed"):
        # Task-level events — store in pipeline_tasks
        trace = body.get("trace", {})
        if trace:
            try:
                execute_write(
                    """
                    INSERT INTO pipeline_tasks
                        (run_id, task_id, task_name, status,
                         container, cpus, memory_mb, duration_ms,
                         submitted_at, started_at, completed_at)
                    VALUES
                        (:run_id, :task_id, :task_name, :status,
                         :container, :cpus, :memory_mb, :duration_ms,
                         :submitted_at, :started_at, :completed_at)
                    ON CONFLICT (run_id, task_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        duration_ms = EXCLUDED.duration_ms,
                        completed_at = EXCLUDED.completed_at
                    """,
                    {
                        "run_id": run_id,
                        "task_id": str(trace.get("taskId", "")),
                        "task_name": trace.get("name", ""),
                        "status": trace.get("status", ""),
                        "container": trace.get("container", ""),
                        "cpus": trace.get("cpus"),
                        "memory_mb": (
                            trace.get("memory", 0) // (1024 * 1024) if trace.get("memory") else None
                        ),
                        "duration_ms": trace.get("duration"),
                        "submitted_at": trace.get("submit"),
                        "started_at": trace.get("start"),
                        "completed_at": trace.get("complete"),
                    },
                    conn=db,
                )
            except Exception as e:
                logger.error("Failed to store task trace: %s", e)

    return {"status": "ok", "event": event, "run_id": run_id}


# ── Stubs — implement in Month 2 ──────────────────────────────────────────────


@router.get("/")
def list_pipelines() -> dict:
    """Stub — implement in Month 2."""
    return {"status": "not implemented", "router": "pipelines"}


@router.post("/launch")
def launch_pipeline() -> dict:
    """Stub — implement in Month 2."""
    return {"status": "not implemented", "router": "pipelines"}


@router.get("/{run_id}")
def get_pipeline_run(run_id: str) -> dict:
    """Stub — implement in Month 2."""
    return {"status": "not implemented", "run_id": run_id}


@router.get("/{run_id}/tasks")
def get_pipeline_tasks(run_id: str) -> dict:
    """Stub — implement in Month 2."""
    return {"status": "not implemented", "run_id": run_id}


@router.get("/{run_id}/results")
def get_pipeline_results(run_id: str) -> dict:
    """Stub — implement in Month 2."""
    return {"status": "not implemented", "run_id": run_id}


@router.get("/{run_id}/files")
def get_pipeline_files(run_id: str) -> dict:
    """Stub — implement in Month 2."""
    return {"status": "not implemented", "run_id": run_id}


@router.post("/{run_id}/resume")
def resume_pipeline(run_id: str) -> dict:
    """Stub — implement in Month 2."""
    return {"status": "not implemented", "run_id": run_id}
