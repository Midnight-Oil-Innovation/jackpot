# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""B-BYOP-10 — BYOP telemetry aggregation against real PostgreSQL.

No mocking: rows go into ``byop_pipelines`` / ``pipeline_results`` via
the session-scoped testcontainer (root ``conftest.py``) and the service
runs its real aggregation SQL (FILTER, PERCENTILE_CONT, JSONB casts).
"""

from __future__ import annotations

import json

import pytest

from backend.database import _get_engine, execute_write
from backend.services.byop_telemetry import get_pipeline_telemetry

_SEQ = iter(range(10_000))


@pytest.fixture
def db():
    _, session_local = _get_engine()
    session = session_local()
    try:
        yield session
        session.rollback()  # nothing persists past the test
    finally:
        session.close()


def _insert_pipeline(db, name: str) -> int:
    rows = execute_write(
        """
        INSERT INTO byop_pipelines
            (name, display_name, version, engine_type, engine_version,
             source_type, manifest_yaml, registered_by_user_id, license_spdx)
        VALUES
            (:name, :name, '1.0.0', 'nextflow', '23.10',
             'git', 'metadata: {}', 1, 'MIT')
        RETURNING id
        """,
        {"name": name},
        conn=db,
    )
    return rows[0]["id"]


def _insert_result(db, pipeline_id: int, status: str, walltime: float, cost: float) -> None:
    execute_write(
        """
        INSERT INTO pipeline_results
            (run_id, sample_id, byop_pipeline_id, metrics)
        VALUES
            (:run_id, :sample_id, :pid, CAST(:metrics AS JSONB))
        """,
        {
            "run_id": f"telemetry-run-{next(_SEQ)}",
            "sample_id": f"telemetry-sample-{next(_SEQ)}",
            "pid": pipeline_id,
            "metrics": json.dumps(
                {"status": status, "walltime_seconds": walltime, "cost_usd": cost}
            ),
        },
        conn=db,
    )


@pytest.mark.asyncio
async def test_single_pipeline_aggregates(db):
    pid = _insert_pipeline(db, "telemetry-happy")
    walltimes = [100.0, 200.0, 300.0, 400.0]
    costs = [1.0, 2.0, 3.0, 4.0]
    statuses = ["success", "success", "success", "failed"]
    for status, walltime, cost in zip(statuses, walltimes, costs, strict=True):
        _insert_result(db, pid, status, walltime, cost)

    rows = get_pipeline_telemetry(db, pid)

    assert len(rows) == 1
    row = rows[0]
    assert row["pipeline_id"] == pid
    assert row["name"] == "telemetry-happy"
    assert row["total_runs"] == 4
    assert row["success_rate"] == pytest.approx(0.75)
    assert row["mean_walltime_seconds"] == pytest.approx(250.0)
    # PERCENTILE_CONT(0.95) over [100, 200, 300, 400] = 385.0
    assert row["p95_walltime_seconds"] == pytest.approx(385.0)
    assert row["mean_cost_usd"] == pytest.approx(2.5)


@pytest.mark.asyncio
async def test_filter_by_pipeline_id(db):
    pid_a = _insert_pipeline(db, "telemetry-filter-a")
    pid_b = _insert_pipeline(db, "telemetry-filter-b")
    _insert_result(db, pid_a, "success", 10.0, 0.1)
    _insert_result(db, pid_b, "failed", 20.0, 0.2)

    rows = get_pipeline_telemetry(db, pid_a)

    assert [r["pipeline_id"] for r in rows] == [pid_a]
    assert rows[0]["success_rate"] == pytest.approx(1.0)

    all_rows = get_pipeline_telemetry(db)
    ids = {r["pipeline_id"] for r in all_rows}
    assert {pid_a, pid_b} <= ids


@pytest.mark.asyncio
async def test_pipeline_with_no_results(db):
    pid = _insert_pipeline(db, "telemetry-empty")

    rows = get_pipeline_telemetry(db, pid)

    assert len(rows) == 1
    row = rows[0]
    assert row["total_runs"] == 0
    assert row["success_rate"] is None
    assert row["mean_walltime_seconds"] is None
    assert row["p95_walltime_seconds"] is None
    assert row["mean_cost_usd"] is None


@pytest.mark.asyncio
async def test_unknown_pipeline_id_returns_empty(db):
    assert get_pipeline_telemetry(db, 999_999_999) == []


@pytest.mark.asyncio
async def test_all_failed_runs_success_rate_zero(db):
    pid = _insert_pipeline(db, "telemetry-all-failed")
    for _ in range(3):
        _insert_result(db, pid, "failed", 60.0, 0.5)

    rows = get_pipeline_telemetry(db, pid)

    assert rows[0]["success_rate"] == pytest.approx(0.0)
    assert rows[0]["total_runs"] == 3


@pytest.mark.asyncio
async def test_router_endpoint_delegates(db):
    """GET /byop/telemetry handler returns the service output."""
    from backend.routers.byop import get_telemetry

    pid = _insert_pipeline(db, "telemetry-endpoint")
    _insert_result(db, pid, "success", 30.0, 0.3)

    rows = get_telemetry(db=db, current_user={"id": 1}, pipeline_id=pid)

    assert len(rows) == 1
    assert rows[0]["pipeline_id"] == pid
