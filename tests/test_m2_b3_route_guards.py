"""M2-B3 — route-level wiring tests for the pipeline-plane guards.

Same brief as ``test_m2_b2_route_guards.py``: the engine's decisions are
proved in ``tests/authz/``, so what these pin is that each route asks the
right question — which capability, at which scope.

The distinction this batch turns on is read-versus-run. §4 defines
``pipeline:read`` as "the pipeline zoo, the BYOP registry, and run status",
and it sits in every lab preset; ``pipeline:run`` is the launch verb and
sits only in ``lab_lead`` and the Bioinformatics User extra. A route that
confused the two would either hide a lab's own runs from its members or let
a read-only member start compute.
"""

import uuid

import pytest
from authz_helpers import sync_grants_from_legacy_roles

from backend.config import get_settings
from backend.database import execute_query, execute_write

SEED_USER_ID = 1
SEED_LAB_ID = 1
SEED_PROJECT_ID = 1


def _switch_user(email: str, monkeypatch) -> None:
    monkeypatch.setenv("MOCK_USER_EMAIL", email)
    get_settings.cache_clear()


def _member(prefix: str, role: str, monkeypatch, *, lab_id=SEED_LAB_ID, director=False) -> dict:
    email = f"{prefix}-{uuid.uuid4().hex[:6]}@test.com"
    uid = execute_write(
        "INSERT INTO users (email, name, organization_id, is_platform_admin, "
        "is_data_analyst, is_active) VALUES (:e, :e, 1, FALSE, FALSE, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET is_active = TRUE RETURNING id",
        {"e": email},
    )[0]["id"]
    execute_write(
        "INSERT INTO lab_membership (user_id, lab_id, permission_group_id, is_lab_director) "
        "SELECT :u, :l, pg.id, :d FROM permission_groups pg WHERE pg.name = :r "
        "ON CONFLICT (user_id, lab_id) DO UPDATE SET "
        "permission_group_id = EXCLUDED.permission_group_id, "
        "is_lab_director = EXCLUDED.is_lab_director",
        {"u": uid, "l": lab_id, "r": role, "d": director},
    )
    sync_grants_from_legacy_roles()
    _switch_user(email, monkeypatch)
    return {"id": uid, "email": email}


def _outsider(prefix: str, monkeypatch) -> dict:
    email = f"{prefix}-{uuid.uuid4().hex[:6]}@test.com"
    uid = execute_write(
        "INSERT INTO users (email, name, organization_id, is_platform_admin, "
        "is_data_analyst, is_active) VALUES (:e, :e, 1, FALSE, FALSE, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET is_active = TRUE RETURNING id",
        {"e": email},
    )[0]["id"]
    sync_grants_from_legacy_roles()
    _switch_user(email, monkeypatch)
    return {"id": uid, "email": email}


def _cleanup_users(emails: list[str]) -> None:
    for e in emails:
        rows = execute_query("SELECT id FROM users WHERE email = :e", {"e": e})
        if not rows:
            continue
        uid = rows[0]["id"]
        execute_write("DELETE FROM lab_membership WHERE user_id = :u", {"u": uid})
        execute_write(
            "DELETE FROM authz_capability_grants WHERE principal_id = :u", {"u": str(uid)}
        )
        execute_write("UPDATE audit_log SET actor_id = NULL WHERE actor_id = :u", {"u": uid})
        execute_write(
            "UPDATE pipeline_runs SET launched_by_id = 1 WHERE launched_by_id = :u", {"u": uid}
        )
        execute_write("DELETE FROM users WHERE id = :u", {"u": uid})


def _foreign_project() -> int:
    """A project in a lab other than the seed lab, created if absent.

    Both halves are ensured independently: another module may have created
    'Other Lab' without a project, and a helper that only seeded the project
    on the lab-insert path fails on the second run — which is exactly what
    happened in full-suite order.
    """
    rows = execute_query("SELECT id FROM labs WHERE display_name = 'Other Lab'")
    lab_id = (
        rows[0]["id"]
        if rows
        else execute_write(
            "INSERT INTO labs (organization_id, display_name, description, created_by_id) "
            "VALUES (1, 'Other Lab', 'Test lab', 1) RETURNING id"
        )[0]["id"]
    )
    proj = execute_query(
        "SELECT id FROM projects WHERE lab_id = :l ORDER BY id LIMIT 1", {"l": lab_id}
    )
    if proj:
        return proj[0]["id"]
    return execute_write(
        "INSERT INTO projects (lab_id, display_name, description, created_by_id) "
        "VALUES (:l, 'Other Project', 'x', 1) RETURNING id",
        {"l": lab_id},
    )[0]["id"]


def _seed_run(**over) -> str:
    run_id = f"jp-{uuid.uuid4()}"
    params = {
        "rid": run_id,
        "tok": f"pt_{uuid.uuid4().hex}",
        "lab": over.get("lab_id", SEED_LAB_ID),
        "proj": over.get("project_id", SEED_PROJECT_ID),
    }
    execute_write(
        """
        INSERT INTO pipeline_runs
            (lab_id, project_id, launched_by_id, pipeline_name, pipeline_version,
             sample_ids, status, launcher_type, run_id, pipeline_token, work_dir,
             result_uri)
        VALUES
            (:lab, :proj, 1, 'b3-test', '1.0.0', '{}', 'QUEUED', 'native', :rid, :tok,
             'gs://jackpot-work/w', 'gs://jackpot-results/r')
        """,
        params,
    )
    return run_id


def _drop_run(run_id: str) -> None:
    execute_write("DELETE FROM pipeline_runs WHERE run_id = :r", {"r": run_id})


# ─────────────────── run status: pipeline:read, not pipeline:run ───────────


@pytest.mark.asyncio
async def test_lab_reader_can_see_a_run_in_their_lab(client, monkeypatch):
    """The whole point of the map correction. Under the map's original
    pipeline:run this would have been 403 for every Collaborator and Reader."""
    emails: list[str] = []
    run_id = _seed_run()
    try:
        u = _member("prd", "Lab Reader", monkeypatch)
        emails.append(u["email"])
        for path in (
            f"/api/v1/pipelines/{run_id}",
            f"/api/v1/pipelines/{run_id}/tasks",
            f"/api/v1/pipelines/{run_id}/events",
        ):
            resp = await client.get(path)
            assert resp.status_code == 200, (path, resp.text)
    finally:
        _drop_run(run_id)
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_outsider_cannot_see_a_run(client, monkeypatch):
    emails: list[str] = []
    run_id = _seed_run()
    try:
        u = _outsider("pnone", monkeypatch)
        emails.append(u["email"])
        resp = await client.get(f"/api/v1/pipelines/{run_id}")
        assert resp.status_code == 403, resp.text
    finally:
        _drop_run(run_id)
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_reading_a_run_does_not_confer_resuming_it(client, monkeypatch):
    """pipeline:read is in every lab preset; pipeline:run is not. A Reader who
    can watch a run must not be able to start work from it."""
    emails: list[str] = []
    run_id = _seed_run()
    try:
        u = _member("prr", "Lab Reader", monkeypatch)
        emails.append(u["email"])
        assert (await client.get(f"/api/v1/pipelines/{run_id}")).status_code == 200
        resp = await client.post(f"/api/v1/pipelines/{run_id}/resume", json={})
        assert resp.status_code == 403, resp.text
    finally:
        _drop_run(run_id)
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_lab_collaborator_may_launch(client, monkeypatch):
    """The access the reseed exclusion was silently removing."""
    emails: list[str] = []
    try:
        u = _member("plw", "Lab Collaborator", monkeypatch)
        emails.append(u["email"])
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={"pipeline_id": 1, "project_id": SEED_PROJECT_ID, "sample_ids": ["nope"]},
        )
        # Past the guard: whatever the launch path then says about a
        # nonexistent sample is not this test's business.
        assert resp.status_code != 403, resp.text
    finally:
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_bioinformatics_user_may_resume(client, monkeypatch):
    """A Bioinformatics User maps to lab_member_rw, which holds pipeline:run."""
    emails: list[str] = []
    run_id = _seed_run()
    try:
        u = _member("pbi", "Bioinformatics User", monkeypatch)
        emails.append(u["email"])
        resp = await client.post(f"/api/v1/pipelines/{run_id}/resume", json={})
        # Not 403: the guard let it through. Whatever the resume path then
        # decides about a QUEUED run is not this test's business.
        assert resp.status_code != 403, resp.text
    finally:
        _drop_run(run_id)
        _cleanup_users(emails)


# ────────────────────────────── launch ────────────────────────────────────


@pytest.mark.asyncio
async def test_launch_denied_without_pipeline_run(client, monkeypatch):
    """A Lab Reader holds pipeline:read but not pipeline:run.

    This test originally used a Lab Collaborator, which passed — because the
    reseed wrongly withheld pipeline:run from lab_member_rw. §8.2's preset
    block puts it there. A Collaborator launching is correct behaviour, so
    the denial case has to be the read-only member.
    """
    emails: list[str] = []
    try:
        u = _member("plc", "Lab Reader", monkeypatch)
        emails.append(u["email"])
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={"pipeline_id": 1, "project_id": SEED_PROJECT_ID, "sample_ids": ["nope"]},
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["error"]["code"] == "ACCESS_DENIED"
    finally:
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_launch_project_scope_does_not_cross_labs(client, monkeypatch):
    """The grant is at the member's own lab; another lab's project is outside it."""
    emails: list[str] = []
    foreign_project = _foreign_project()
    try:
        u = _member("pld", "Lab Director", monkeypatch, director=True)
        emails.append(u["email"])
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={"pipeline_id": 1, "project_id": foreign_project, "sample_ids": ["nope"]},
        )
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup_users(emails)
