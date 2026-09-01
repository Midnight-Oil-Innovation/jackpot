"""M2-B6 — route wiring for the two per-run SERVICE callbacks.

The backlog's one constraint: "Do not weaken the token check while adding
permit() — it is the authentication half and stays." So these tests are
mostly about the token check still behaving exactly as it did, with the
authorization call added beside it rather than in place of it.
"""

import uuid

import pytest

from backend.database import execute_query, execute_write


def _seed_run(*, project_id: int | None = 1) -> tuple[str, str]:
    run_id = f"jp-{uuid.uuid4()}"
    token = f"pt_{uuid.uuid4().hex}"
    execute_write(
        """
        INSERT INTO pipeline_runs
            (lab_id, project_id, launched_by_id, pipeline_name, pipeline_version,
             sample_ids, status, launcher_type, run_id, pipeline_token, work_dir,
             result_uri)
        VALUES (1, :proj, 1, 'b6-test', '1.0.0', '{}', 'RUNNING', 'native',
                :rid, :tok, 'gs://w', 'gs://r')
        """,
        {"rid": run_id, "tok": token, "proj": project_id},
    )
    return run_id, token


def _drop(run_id: str) -> None:
    execute_write("DELETE FROM pipeline_events WHERE run_id = :r", {"r": run_id})
    execute_write("DELETE FROM pipeline_runs WHERE run_id = :r", {"r": run_id})


# ── the authentication half, unchanged ────────────────────────────────────


@pytest.mark.asyncio
async def test_events_still_401s_without_a_token(client):
    run_id, _ = _seed_run()
    try:
        resp = await client.post("/api/v1/pipelines/events", json={"runId": run_id})
        assert resp.status_code == 401, resp.text
    finally:
        _drop(run_id)


@pytest.mark.asyncio
async def test_events_still_401s_on_a_wrong_token(client):
    run_id, _ = _seed_run()
    try:
        resp = await client.post(
            "/api/v1/pipelines/events",
            json={"runId": run_id},
            headers={"X-Pipeline-Token": "pt_wrong"},
        )
        assert resp.status_code == 401, resp.text
    finally:
        _drop(run_id)


@pytest.mark.asyncio
async def test_another_runs_token_does_not_authenticate_this_run(client):
    """The property the per-run token has always had, pinned here because
    M2-B6 is where someone might be tempted to widen the principal to a lab
    or project and quietly lose it."""
    run_a, _ = _seed_run()
    run_b, token_b = _seed_run()
    try:
        resp = await client.post(
            "/api/v1/pipelines/events",
            json={"runId": run_a},
            headers={"X-Pipeline-Token": token_b},
        )
        assert resp.status_code == 401, resp.text
    finally:
        _drop(run_a)
        _drop(run_b)


# ── the authorization half, added beside it ───────────────────────────────


@pytest.mark.asyncio
async def test_a_valid_token_still_gets_through_both_halves(client):
    run_id, token = _seed_run()
    try:
        resp = await client.post(
            "/api/v1/pipelines/events",
            json={"runId": run_id, "event": "started"},
            headers={"X-Pipeline-Token": token},
        )
        assert resp.status_code == 200, resp.text
        rows = execute_query("SELECT 1 FROM pipeline_events WHERE run_id = :r", {"r": run_id})
        assert rows, "event was authorized but not persisted"
    finally:
        _drop(run_id)


@pytest.mark.asyncio
async def test_authentication_is_checked_before_authorization(client):
    """Ordering matters for what the caller learns. A bad token must answer
    401 (who are you), not 403 (you may not) — otherwise a wrong token would
    confirm the run exists and is writable."""
    run_id, _ = _seed_run()
    try:
        resp = await client.post(
            f"/api/v1/pipelines/{run_id}/results/wastewater_lineage_abundance",
            json={},
            headers={"X-Pipeline-Token": "pt_wrong"},
        )
        assert resp.status_code == 401, resp.text
        assert resp.json()["error"]["code"] == "INVALID_TOKEN"
    finally:
        _drop(run_id)


@pytest.mark.asyncio
async def test_results_route_selects_the_project_it_scopes_against(client):
    """The results route did not previously SELECT project_id; M2-B6 added it
    because the SERVICE principal is scoped to the run's project. If that
    column stops being selected, pipeline_run_principal raises rather than
    falling back to the instance root — this asserts the happy path so the
    regression is visible as a 500, not as a silent widening."""
    run_id, token = _seed_run()
    try:
        resp = await client.post(
            f"/api/v1/pipelines/{run_id}/results/wastewater_lineage_abundance",
            json={"sample_id": "B6-S1", "lineage": "BA.2", "abundance": 0.5},
            headers={"X-Pipeline-Token": token},
        )
        # Whatever the schema makes of the payload, the guard let it past.
        assert resp.status_code != 403, resp.text
        assert resp.status_code != 500, resp.text
    finally:
        execute_write("DELETE FROM wastewater_lineage_abundance WHERE run_id = :r", {"r": run_id})
        _drop(run_id)
