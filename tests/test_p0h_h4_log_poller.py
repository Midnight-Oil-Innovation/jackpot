"""Phase P0h H-4 — sidecar Nextflow log poller.

Active cluster runs whose compute nodes have no outbound HTTP cannot
deliver weblog events. The poller in ``backend.log_poller`` tails
``<work_dir>/runs/<run_id>/.nextflow.log`` on the shared filesystem
and synthesises the workflow-state transitions the receiver would
have written.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from test_pipelines_router_api import (
    SEED_PROJECT_ID,
    SEED_USER_ID,
)

from backend.database import execute_query, execute_write
from backend.log_poller import (
    _classify,
    _log_uri_for,
    _read_from_offset,
    poll_cluster_run_logs,
)


def _insert_run(
    *,
    run_id: str,
    work_dir: str,
    status: str = "QUEUED",
    poller_log_offset: int = 0,
) -> None:
    execute_write(
        """
        INSERT INTO pipeline_runs
            (lab_id, project_id, launched_by_id, pipeline_name,
             sample_ids, status, run_id, work_dir, poller_log_offset,
             pipeline_token)
        VALUES
            (1, :pid, :uid, 'jp-h4-fixture',
             ARRAY[]::INTEGER[], :status, :run_id, :wdir, :offset,
             'pt-fixture')
        """,
        {
            "pid": SEED_PROJECT_ID,
            "uid": SEED_USER_ID,
            "status": status,
            "run_id": run_id,
            "wdir": work_dir,
            "offset": poller_log_offset,
        },
    )


def _drop_run(run_id: str) -> None:
    execute_write("DELETE FROM pipeline_runs WHERE run_id = :r", {"r": run_id})


def _fetch_run(run_id: str) -> dict:
    rows = execute_query(
        "SELECT status, poller_log_offset FROM pipeline_runs WHERE run_id = :r",
        {"r": run_id},
    )
    assert rows, f"run {run_id} not found"
    return rows[0]


def _write_log(work_dir: Path, run_id: str, content: str) -> Path:
    """Place a .nextflow.log at the canonical
    ``<work_dir>/runs/<run_id>/.nextflow.log`` location and return the
    path. Mirrors the layout the renderer + Nextflow produce."""
    log_dir = work_dir / "runs" / run_id
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / ".nextflow.log"
    log_path.write_text(content, encoding="utf-8")
    return log_path


# ───────────────────────── _classify ─────────────────────────


def test_classify_started_line():
    assert _classify("DEBUG nextflow.Session - Workflow started: 2026-01-01") == "started"


def test_classify_completed_line():
    assert _classify("INFO nextflow.Session - Workflow completed OK") == "completed"


def test_classify_failed_via_execution_status():
    assert (
        _classify("INFO nextflow.Session - Workflow completed\nExecution status: FAILED")
        == "failed"
    )


def test_classify_no_match():
    assert _classify("INFO nextflow.Session - Pulling images") is None


def test_classify_terminal_wins_over_started():
    """If a poller catches up to a long log containing both start and
    completion markers, the terminal classification wins."""
    blob = (
        "DEBUG nextflow.Session - Workflow started: t0\n"
        "INFO nextflow.Session - Workflow completed OK\n"
    )
    assert _classify(blob) == "completed"


# ───────────────────────── _log_uri_for ─────────────────────────


def test_log_uri_for_appends_run_id_to_bare_workdir(tmp_path: Path):
    uri = _log_uri_for({"run_id": "jp-foo", "work_dir": str(tmp_path)})
    assert uri == f"{tmp_path}/runs/jp-foo/.nextflow.log"


def test_log_uri_for_strips_trailing_work_segment(tmp_path: Path):
    work_dir = f"{tmp_path}/runs/jp-foo/work"
    uri = _log_uri_for({"run_id": "jp-foo", "work_dir": work_dir})
    assert uri == f"{tmp_path}/runs/jp-foo/.nextflow.log"


def test_log_uri_for_returns_none_when_missing_pieces():
    assert _log_uri_for({"run_id": "jp-foo"}) is None
    assert _log_uri_for({"work_dir": "/srv"}) is None


# ───────────────────────── _read_from_offset ─────────────────────────


def test_read_from_offset_returns_empty_when_file_missing(tmp_path: Path):
    text, offset = _read_from_offset(str(tmp_path / "nothing.log"), 0)
    assert text == ""
    assert offset == 0


def test_read_from_offset_advances_on_read(tmp_path: Path):
    p = tmp_path / "log.txt"
    p.write_text("hello world\n", encoding="utf-8")
    text, new_offset = _read_from_offset(str(p), 0)
    assert text == "hello world\n"
    assert new_offset == p.stat().st_size


def test_read_from_offset_resets_when_file_shrinks(tmp_path: Path):
    p = tmp_path / "log.txt"
    p.write_text("longer original content here\n", encoding="utf-8")
    big_offset = p.stat().st_size + 50
    p.write_text("tiny\n", encoding="utf-8")
    text, new_offset = _read_from_offset(str(p), big_offset)
    # Reset to 0, re-read the whole (smaller) file.
    assert text == "tiny\n"
    assert new_offset == p.stat().st_size


# ───────────────────────── poll_cluster_run_logs ─────────────────────────


def test_poll_started_marker_moves_run_to_running(tmp_path: Path):
    run_id = "jp-h4-started-001"
    _drop_run(run_id)
    try:
        _insert_run(run_id=run_id, work_dir=str(tmp_path), status="QUEUED")
        _write_log(
            tmp_path,
            run_id,
            "Apr-15 10:00:01 DEBUG nextflow.Session - Workflow started: 2026-04-15\n",
        )
        summary = poll_cluster_run_logs()
        assert summary["polled"] >= 1
        assert summary["state_shifts"] >= 1
        assert summary["failures"] == 0
        run = _fetch_run(run_id)
        assert run["status"] == "RUNNING"
        assert run["poller_log_offset"] > 0
    finally:
        _drop_run(run_id)


def test_poll_completed_marker_invokes_handle_workflow_complete(tmp_path: Path):
    run_id = "jp-h4-completed-002"
    _drop_run(run_id)
    try:
        _insert_run(run_id=run_id, work_dir=str(tmp_path), status="RUNNING")
        _write_log(
            tmp_path,
            run_id,
            "Apr-15 10:00:01 DEBUG nextflow.Session - Workflow started\n"
            "Apr-15 10:30:00 INFO nextflow.Session - Workflow completed OK\n",
        )
        with patch("backend.log_poller._handle_workflow_complete") as m:
            summary = poll_cluster_run_logs()
        assert summary["state_shifts"] >= 1
        # The handler is called with success=True derived from "completed".
        assert m.call_count == 1
        call_kwargs = m.call_args.kwargs
        assert call_kwargs["run_id"] == run_id
        assert call_kwargs["event_body"] == {"workflow": {"success": True}}
    finally:
        _drop_run(run_id)


def test_poll_failed_marker_invokes_handle_workflow_complete_with_success_false(
    tmp_path: Path,
):
    run_id = "jp-h4-failed-003"
    _drop_run(run_id)
    try:
        _insert_run(run_id=run_id, work_dir=str(tmp_path), status="RUNNING")
        _write_log(
            tmp_path,
            run_id,
            "Apr-15 10:00:01 DEBUG nextflow.Session - Workflow started\n"
            "Apr-15 10:30:00 ERROR nextflow.Session - Workflow execution stopped\n",
        )
        with patch("backend.log_poller._handle_workflow_complete") as m:
            poll_cluster_run_logs()
        assert m.call_count == 1
        assert m.call_args.kwargs["event_body"] == {"workflow": {"success": False}}
    finally:
        _drop_run(run_id)


def test_poll_skips_terminal_runs(tmp_path: Path):
    run_id = "jp-h4-terminal-004"
    _drop_run(run_id)
    try:
        _insert_run(run_id=run_id, work_dir=str(tmp_path), status="COMPLETED")
        _write_log(
            tmp_path,
            run_id,
            "Apr-15 10:00:01 DEBUG nextflow.Session - Workflow started\n",
        )
        with patch("backend.log_poller._handle_workflow_complete") as m:
            poll_cluster_run_logs()
        # Terminal runs are skipped; the handler is not called for them.
        assert m.call_count == 0
        # Offset stays at 0 because the run was filtered out.
        run = _fetch_run(run_id)
        assert run["poller_log_offset"] == 0
    finally:
        _drop_run(run_id)


def test_poll_advances_offset_even_without_match(tmp_path: Path):
    """A 50-MB log with no terminal marker should not be re-scanned in
    full every 30 seconds — the poller advances the offset whether or
    not it found a state-shift pattern."""
    run_id = "jp-h4-noise-005"
    _drop_run(run_id)
    try:
        _insert_run(run_id=run_id, work_dir=str(tmp_path), status="RUNNING")
        noise = "INFO nextflow.Executor - Submitted process > FOO\n" * 10
        _write_log(tmp_path, run_id, noise)
        poll_cluster_run_logs()
        run = _fetch_run(run_id)
        # Status unchanged; offset advanced past the noise.
        assert run["status"] == "RUNNING"
        assert run["poller_log_offset"] == len(noise)
    finally:
        _drop_run(run_id)


def test_poll_is_idempotent_on_resubmission(tmp_path: Path):
    """A second tick with no new bytes is a no-op: same offset, no
    extra handler call."""
    run_id = "jp-h4-idem-006"
    _drop_run(run_id)
    try:
        _insert_run(run_id=run_id, work_dir=str(tmp_path), status="RUNNING")
        _write_log(
            tmp_path,
            run_id,
            "Apr-15 10:00:01 DEBUG nextflow.Session - Workflow started\n",
        )
        poll_cluster_run_logs()
        first_offset = _fetch_run(run_id)["poller_log_offset"]

        with patch("backend.log_poller._handle_workflow_complete") as m:
            poll_cluster_run_logs()

        second_offset = _fetch_run(run_id)["poller_log_offset"]
        assert second_offset == first_offset
        # The first tick already moved the run to RUNNING; second tick
        # has no new bytes and so does not call the workflow-complete
        # handler.
        assert m.call_count == 0
    finally:
        _drop_run(run_id)


def test_poll_missing_log_file_is_silent_noop(tmp_path: Path):
    """A QUEUED run whose Nextflow has not yet started writing a log
    should not flip to RUNNING and should not be counted as a failure."""
    run_id = "jp-h4-nolog-007"
    _drop_run(run_id)
    try:
        _insert_run(run_id=run_id, work_dir=str(tmp_path), status="QUEUED")
        # No log file written.
        summary = poll_cluster_run_logs()
        assert summary["failures"] == 0
        run = _fetch_run(run_id)
        assert run["status"] == "QUEUED"
        assert run["poller_log_offset"] == 0
    finally:
        _drop_run(run_id)
