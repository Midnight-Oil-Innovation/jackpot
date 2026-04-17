"""
Pipelines router.

Implements:
  POST /api/v1/pipelines/events                         — Nextflow weblog receiver
  POST /api/v1/pipelines/{run_id}/results/{result_type} — parser registration

Stubs (Month 2 implementation):
  GET  /api/v1/pipelines/
  POST /api/v1/pipelines/launch
  GET  /api/v1/pipelines/{run_id}
  GET  /api/v1/pipelines/{run_id}/tasks
  GET  /api/v1/pipelines/{run_id}/results
  GET  /api/v1/pipelines/{run_id}/files
  POST /api/v1/pipelines/{run_id}/resume
"""

import hmac
import json
import logging
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from backend.audit import AuditActions, log_audit
from backend.database import execute_query, execute_write, get_db_dep
from backend.pipeline_results_loader import load_pipeline_results
from backend.responses import error, success

# jackpot-nf ships the canonical result schemas used by both the parsers
# and this registration endpoint. The submodule lives at ``nf/`` next to
# this repo and exposes the ``shared`` package. Prepend its path so
# ``from shared.schemas import RESULT_SCHEMAS`` resolves.
_NF_ROOT = Path(__file__).resolve().parents[2] / "nf"
if str(_NF_ROOT) not in sys.path:
    sys.path.insert(0, str(_NF_ROOT))

from shared.schemas import RESULT_SCHEMAS  # noqa: E402

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


# ── Parser registration ───────────────────────────────────────────────────────


def _split_jsonb_fields(payload: dict) -> tuple[list[str], list[str], dict]:
    """
    Build column list, bind-placeholder list, and params for an INSERT
    from a Pydantic-validated payload. dict/list values are serialized
    to JSON and cast to JSONB; scalars pass through.
    """
    cols: list[str] = []
    placeholders: list[str] = []
    params: dict = {}
    for key, value in payload.items():
        cols.append(key)
        if isinstance(value, dict | list):
            placeholders.append(f"CAST(:{key} AS JSONB)")
            params[key] = json.dumps(value)
        else:
            placeholders.append(f":{key}")
            params[key] = value
    return cols, placeholders, params


@router.post("/{run_id}/results/{result_type}")
def register_pipeline_result(
    run_id: str,
    result_type: str,
    body: dict[str, Any],
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    """
    Parser registration endpoint.

    Parsers running inside a pipeline POST canonical result payloads here.
    The run is authenticated with a per-run ``X-Pipeline-Token`` minted
    when the pipeline was launched. The payload is validated against the
    Pydantic schema registered for ``result_type``, persisted into the
    matching typed result table, and summarized into ``pipeline_results``
    in the same transaction.
    """
    schema_cls = RESULT_SCHEMAS.get(result_type)
    if schema_cls is None:
        return error(
            "UNKNOWN_RESULT_TYPE",
            f"Unknown result_type: {result_type}",
            detail={"allowed": sorted(RESULT_SCHEMAS.keys())},
            status_code=422,
        )

    rows = execute_query(
        """
        SELECT pipeline_token, pipeline_name, pipeline_version
        FROM pipeline_runs
        WHERE run_id = :run_id
        """,
        {"run_id": run_id},
        conn=db,
    )
    if not rows:
        return error(
            "RUN_NOT_FOUND",
            f"Unknown run_id: {run_id}",
            status_code=404,
        )
    run = rows[0]

    supplied_token = request.headers.get("X-Pipeline-Token", "")
    expected_token = run.get("pipeline_token") or ""
    if not expected_token or not hmac.compare_digest(supplied_token, expected_token):
        return error(
            "INVALID_TOKEN",
            "Invalid or missing X-Pipeline-Token",
            status_code=401,
        )

    try:
        validated = schema_cls(**body)
    except ValidationError as exc:
        return error(
            "INVALID_PAYLOAD",
            "Payload failed schema validation",
            detail={"errors": exc.errors()},
            status_code=422,
        )

    record = validated.model_dump(exclude_unset=True)
    record.setdefault("run_id", run_id)
    # run_id from the URL is authoritative — never trust the body.
    record["run_id"] = run_id

    cols, placeholders, params = _split_jsonb_fields(record)
    insert_sql = (
        f"INSERT INTO {result_type} ({', '.join(cols)}) "
        f"VALUES ({', '.join(placeholders)}) "
        "ON CONFLICT DO NOTHING RETURNING id"
    )
    try:
        inserted = execute_write(insert_sql, params, conn=db)
    except Exception as exc:
        logger.error("Typed-table insert failed for %s/%s: %s", run_id, result_type, exc)
        raise HTTPException(status_code=500, detail="Result persistence failed") from exc

    if not inserted:
        return error(
            "DUPLICATE_RESULT",
            "Result already registered for this run/sample",
            status_code=409,
        )
    result_id = inserted[0]["id"]

    sample_id = record.get("sample_id")
    metrics_payload = json.dumps({result_type: {"registered": True}})
    execute_write(
        """
        INSERT INTO pipeline_results
            (run_id, sample_id, pipeline_name, pipeline_version, metrics)
        VALUES
            (:run_id, :sample_id, :pipeline_name, :pipeline_version,
             CAST(:metrics AS JSONB))
        ON CONFLICT (run_id, sample_id) DO UPDATE SET
            metrics = pipeline_results.metrics || EXCLUDED.metrics,
            pipeline_name = COALESCE(pipeline_results.pipeline_name, EXCLUDED.pipeline_name),
            pipeline_version = COALESCE(
                pipeline_results.pipeline_version, EXCLUDED.pipeline_version
            ),
            updated_at = NOW()
        """,
        {
            "run_id": run_id,
            "sample_id": sample_id,
            "pipeline_name": run.get("pipeline_name"),
            "pipeline_version": run.get("pipeline_version"),
            "metrics": metrics_payload,
        },
        conn=db,
    )

    log_audit(
        action=AuditActions.REGISTER_PIPELINE_RESULT,
        actor_id=None,
        resource_type="pipeline_result",
        resource_id=f"{run_id}:{result_type}:{result_id}",
        before=None,
        after={"result_type": result_type, "sample_id": sample_id},
        metadata={"run_id": run_id},
        db_conn=db,
    )

    return success(
        {"status": "registered", "result_id": result_id},
        status_code=201,
    )


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
