"""Phase P0h H-4 — sidecar Nextflow log poller.

Scenario-C deployments often run on university clusters whose compute
nodes have no outbound HTTP. The Nextflow weblog hook (configured into
every JACKPOT-rendered nextflow.config) cannot deliver in that
environment, so the API server polls the per-run ``.nextflow.log``
file over the shared filesystem and synthesises the same state
transitions the receiver would have produced.

The poller is intentionally narrow: it observes workflow-level state
shifts (started → running, completed/failed → terminal) and dispatches
into the same ``_handle_workflow_complete`` codepath the weblog
receiver uses, so result loading runs once whether the trigger came
through HTTP or polling. Per-task accounting (process.submitted /
started / completed) remains a weblog-only concern; clusters that
need full task-level visibility have to relax outbound HTTP.

Idempotency
-----------

Per-run ``poller_log_offset`` advances monotonically; each tick reads
only bytes past the offset and persists the new offset before
returning. If the weblog and the poller both observe the same
workflow-completion event, ``_handle_workflow_complete`` writes the
same terminal status either way and the result loader is a no-op on
the second call (status already terminal).

Activation
----------

Wired by ``backend.main`` as an APScheduler job firing every
``settings.log_poller_interval_seconds`` (default 30). Disabled when
``settings.scheduler_enabled = False`` (test runs).
"""

from __future__ import annotations

import logging
import re
from typing import Any

import fsspec

from backend.database import execute_query, execute_write, get_db
from backend.routers.pipelines import _handle_workflow_complete

logger = logging.getLogger(__name__)


# Statuses for which the poller still has work to do. Terminal states
# (COMPLETED, FAILED) are skipped so the poller doesn't re-tail logs
# after the run finished.
_ACTIVE_STATUSES: tuple[str, ...] = ("PENDING", "QUEUED", "RUNNING")


# Nextflow's per-run ``.nextflow.log`` is verbose and version-sensitive,
# but the workflow start and end lines have been stable for years. The
# patterns below are conservative — they require the canonical Nextflow
# logger prefix so we don't false-positive on a pipeline that printed
# the word "Workflow" in stdout.
_WORKFLOW_STARTED_RE = re.compile(
    r"\bnextflow\.Session\b.*\bWorkflow started",
    re.IGNORECASE,
)
_WORKFLOW_COMPLETED_RE = re.compile(
    r"\bnextflow\.Session\b.*\bWorkflow completed",
    re.IGNORECASE,
)
# When success isn't directly stated on the completion line, Nextflow
# emits a separate "Execution status: ..." line. Match either spelling.
_WORKFLOW_FAILED_RE = re.compile(
    r"\b(Execution status:\s*FAILED|Workflow execution stopped|Pipeline failed)\b",
    re.IGNORECASE,
)


def _log_uri_for(run: dict) -> str | None:
    """Return the canonical Nextflow log URI for a run, or None.

    The render path writes the per-run config to
    ``<work_dir>/runs/<run_id>/jackpot_run.config`` and Nextflow drops
    its log next to the config as ``.nextflow.log``. ``work_dir`` may
    be a bare path (Slurm shared FS), a ``file://`` URI, or a cloud
    URI (gs://, s3://) — fsspec handles all three.
    """
    work_dir = run.get("work_dir")
    run_id = run.get("run_id")
    if not work_dir or not run_id:
        return None
    base = work_dir.rstrip("/")
    # work_dir already includes /runs/<run_id>/work for the profile path
    # (see backend/backend/routers/pipelines.py:382-383). The .nextflow.log
    # lives in the parent (runs/<run_id>/) — strip the trailing /work
    # segment when present, otherwise assume the work_dir is the runs
    # base and append /<run_id>.
    if base.endswith(f"/runs/{run_id}/work"):
        run_dir = base[: -len("/work")]
    elif base.endswith(f"/runs/{run_id}"):
        run_dir = base
    else:
        run_dir = f"{base}/runs/{run_id}"
    return f"{run_dir}/.nextflow.log"


def _read_from_offset(uri: str, offset: int) -> tuple[str, int]:
    """Read ``uri`` starting at byte ``offset``; return (text, new_offset).

    Returns an empty string and the unchanged offset if the file does
    not yet exist (the run was queued but Nextflow hasn't started
    writing yet) or if the file is shorter than the offset (operator
    truncated or replaced the file — log a warning, reset offset to 0,
    re-read in the next tick).
    """
    try:
        fs, fs_path = fsspec.core.url_to_fs(uri)
    except (ValueError, ImportError) as exc:
        logger.debug("log_poller: cannot resolve URI %s: %s", uri, exc)
        return "", offset

    try:
        size = fs.size(fs_path)
    except FileNotFoundError:
        return "", offset
    except OSError as exc:
        logger.debug("log_poller: stat %s failed: %s", uri, exc)
        return "", offset

    if size < offset:
        logger.warning(
            "log_poller: %s shrank from offset=%d to size=%d; resetting to 0",
            uri,
            offset,
            size,
        )
        offset = 0
    if size == offset:
        return "", offset

    try:
        with fs.open(fs_path, "rb") as fh:
            fh.seek(offset)
            chunk = fh.read()
    except (FileNotFoundError, OSError) as exc:
        logger.debug("log_poller: open %s failed: %s", uri, exc)
        return "", offset

    text = chunk.decode("utf-8", errors="replace")
    return text, offset + len(chunk)


def _classify(text: str) -> str | None:
    """Return ``'started'``, ``'completed'``, ``'failed'``, or ``None``.

    A single chunk can contain multiple lifecycle markers (a long-
    running poller catching up after a downtime); the most-terminal
    classification wins (failed > completed > started).
    """
    if _WORKFLOW_FAILED_RE.search(text):
        return "failed"
    if _WORKFLOW_COMPLETED_RE.search(text):
        return "completed"
    if _WORKFLOW_STARTED_RE.search(text):
        return "started"
    return None


def _persist_offset(run_id: str, new_offset: int, conn: Any) -> None:
    execute_write(
        "UPDATE pipeline_runs SET poller_log_offset = :off WHERE run_id = :rid",
        {"off": new_offset, "rid": run_id},
        conn=conn,
    )


def _apply_classification(
    run_id: str,
    classification: str,
    conn: Any,
) -> None:
    """Translate a classification into the same DB writes the weblog
    receiver would have produced. ``_handle_workflow_complete`` is the
    canonical terminal handler for COMPLETED / FAILED and runs the
    result loader; the poller calls it directly so result loading
    happens regardless of which path observed the event."""
    if classification == "started":
        execute_write(
            """
            UPDATE pipeline_runs
            SET status = 'RUNNING'
            WHERE run_id = :rid AND status IN ('PENDING', 'QUEUED')
            """,
            {"rid": run_id},
            conn=conn,
        )
    elif classification in ("completed", "failed"):
        success_flag = classification == "completed"
        # Synthesise the minimum event body _handle_workflow_complete
        # consumes: it reads ``workflow.success`` to decide between
        # COMPLETED and FAILED.
        synthetic = {"workflow": {"success": success_flag}}
        _handle_workflow_complete(run_id=run_id, event_body=synthetic, conn=conn)


def poll_cluster_run_logs() -> dict[str, int]:
    """APScheduler entry point. Returns a small summary dict for
    observability — counts of runs polled / events synthesised /
    errors swallowed."""
    polled = 0
    state_shifts = 0
    failures = 0
    with get_db() as db:
        rows = execute_query(
            "SELECT run_id, work_dir, status, poller_log_offset "
            "FROM pipeline_runs "
            "WHERE status = ANY(:active) AND work_dir IS NOT NULL",
            {"active": list(_ACTIVE_STATUSES)},
            conn=db,
        )
        for run in rows:
            polled += 1
            run_id = run["run_id"]
            log_uri = _log_uri_for(run)
            if log_uri is None:
                continue
            try:
                text, new_offset = _read_from_offset(log_uri, run.get("poller_log_offset") or 0)
            except Exception:  # noqa: BLE001 — failure here is per-run, not job-fatal
                logger.exception("log_poller: read failed for run %s", run_id)
                failures += 1
                continue

            if not text:
                continue

            classification = _classify(text)
            if classification:
                try:
                    _apply_classification(run_id, classification, conn=db)
                    state_shifts += 1
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "log_poller: apply failed for run %s (%s)",
                        run_id,
                        classification,
                    )
                    failures += 1
                    # Don't advance the offset on apply failure: the
                    # next tick re-reads and retries.
                    continue

            # Advance offset whether or not we matched a pattern; we
            # don't want to re-scan a 50-MB log every 30 seconds for
            # a run that simply has no terminal markers yet.
            _persist_offset(run_id, new_offset, conn=db)

        db.commit()

    return {
        "polled": polled,
        "state_shifts": state_shifts,
        "failures": failures,
    }
