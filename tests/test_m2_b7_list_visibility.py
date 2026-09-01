"""M2-B7 — route-level tests for the list endpoints' new visibility filter.

The equivalence proof lives in ``tests/authz/test_cutover_preflight.py``:
new ⊆ legacy per persona, and the SQL fragment agreeing with ``permit()``
row by row on PostgreSQL. What it cannot show is that a given *route* uses
the fragment — a list that forgot to apply it returns 200 with too many
rows, which is the failure mode this batch exists to prevent and the one
nothing else would catch.

So each test here drives a real request as a principal holding exactly one
thing, and asserts on which rows come back.
"""

import uuid

import pytest
from authz_helpers import sync_grants_from_legacy_roles

from backend.config import get_settings
from backend.database import execute_query, execute_write

SEED_LAB_ID = 1
SEED_PROJECT_ID = 1
SEED_USER_ID = 1
PREFIX = "B7-"


def _switch_user(email: str, monkeypatch) -> None:
    monkeypatch.setenv("MOCK_USER_EMAIL", email)
    get_settings.cache_clear()


def _make_user(email: str) -> int:
    return execute_write(
        "INSERT INTO users (email, name, organization_id, is_platform_admin, "
        "is_data_analyst, is_active) VALUES (:e, :e, 1, FALSE, FALSE, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET is_active = TRUE RETURNING id",
        {"e": email},
    )[0]["id"]


def _member(prefix: str, role: str, monkeypatch, *, lab_id=SEED_LAB_ID) -> dict:
    email = f"{prefix}-{uuid.uuid4().hex[:6]}@test.com"
    uid = _make_user(email)
    execute_write(
        "INSERT INTO lab_membership (user_id, lab_id, permission_group_id, is_lab_director) "
        "SELECT :u, :l, pg.id, FALSE FROM permission_groups pg WHERE pg.name = :r "
        "ON CONFLICT (user_id, lab_id) DO UPDATE SET "
        "permission_group_id = EXCLUDED.permission_group_id",
        {"u": uid, "l": lab_id, "r": role},
    )
    sync_grants_from_legacy_roles()
    _switch_user(email, monkeypatch)
    return {"id": uid, "email": email}


def _stranger(prefix: str, monkeypatch) -> dict:
    email = f"{prefix}-{uuid.uuid4().hex[:6]}@test.com"
    uid = _make_user(email)
    sync_grants_from_legacy_roles()
    _switch_user(email, monkeypatch)
    return {"id": uid, "email": email}


def _other_lab() -> tuple[int, int]:
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
        return lab_id, proj[0]["id"]
    pid = execute_write(
        "INSERT INTO projects (lab_id, display_name, description, created_by_id) "
        "VALUES (:l, 'Other Project', 'x', 1) RETURNING id",
        {"l": lab_id},
    )[0]["id"]
    return lab_id, pid


def _sample(sample_id: str, *, lab_id, project_id, sharing_level="PRIVATE", **over) -> dict:
    payload = {
        "sample_id": sample_id,
        "lab_id": lab_id,
        "project_id": project_id,
        "owner_id": SEED_USER_ID,
        "source_type": "Human",
        "organism_name": "Severe acute respiratory syndrome coronavirus 2",
        "date_collected": "2026-01-15",
        "date_sequenced": "2026-01-20",
        "sequencing_lab": "Example Sequencing Lab",
        "type_of_experiment": "WGS",
        "library_preparation_method": "Illumina DNA Prep",
        "sequencing_protocol": "ARTIC v4.1",
        "sequencing_platform": "Illumina",
        "collection_facility": "Example Facility",
        "collection_location_country": "USA",
        "sharing_level": sharing_level,
        "surveillance_relevant": False,
        "fastq_r1_uri": "gs://b/R1.fastq.gz",
        "quality_status": "ANALYZABLE",
        "scrub_status": "PENDING",
    }
    payload.update(over)
    cols = ", ".join(payload)
    binds = ", ".join(f":{k}" for k in payload)
    return execute_write(f"INSERT INTO samples ({cols}) VALUES ({binds}) RETURNING *", payload)[0]


def _cleanup() -> None:
    for r in execute_query("SELECT id FROM samples WHERE sample_id LIKE :p", {"p": f"{PREFIX}%"}):
        sid = r["id"]
        execute_write("DELETE FROM sample_files WHERE sample_id_fk = :id", {"id": sid})
        execute_write("DELETE FROM sample_access_requests WHERE sample_id = :id", {"id": sid})
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'sample' AND resource_id = :r",
            {"r": str(sid)},
        )
        execute_write("DELETE FROM samples WHERE id = :id", {"id": sid})


def _cleanup_users(emails: list[str]) -> None:
    for e in emails:
        rows = execute_query("SELECT id FROM users WHERE email = :e", {"e": e})
        if not rows:
            continue
        uid = rows[0]["id"]
        execute_write("DELETE FROM import_sessions WHERE created_by_user_id = :u", {"u": uid})
        execute_write(
            "DELETE FROM sample_access_requests WHERE requester_id = :u OR owner_id = :u",
            {"u": uid},
        )
        execute_write("DELETE FROM lab_membership WHERE user_id = :u", {"u": uid})
        execute_write(
            "DELETE FROM authz_capability_grants WHERE principal_id = :u", {"u": str(uid)}
        )
        execute_write("UPDATE audit_log SET actor_id = NULL WHERE actor_id = :u", {"u": uid})
        execute_write(
            "UPDATE pipeline_runs SET launched_by_id = 1 WHERE launched_by_id = :u", {"u": uid}
        )
        execute_write("DELETE FROM users WHERE id = :u", {"u": uid})


@pytest.fixture
def world():
    """One lab-A sample, one lab-B sample, one PUBLIC lab-B sample."""
    _cleanup()
    other_lab, other_project = _other_lab()
    rows = {
        "A": _sample(f"{PREFIX}A", lab_id=SEED_LAB_ID, project_id=SEED_PROJECT_ID),
        "B": _sample(f"{PREFIX}B", lab_id=other_lab, project_id=other_project),
        "B-PUB": _sample(
            f"{PREFIX}B-PUB",
            lab_id=other_lab,
            project_id=other_project,
            sharing_level="PUBLIC",
        ),
    }
    yield rows
    _cleanup()


def _listed(body) -> set[str]:
    return {r["sample_id"] for r in body["data"]}


@pytest.mark.asyncio
async def test_samples_list_shows_own_lab_and_public_only(client, world, monkeypatch):
    emails: list[str] = []
    try:
        u = _member("b7a", "Lab Reader", monkeypatch)
        emails.append(u["email"])
        resp = await client.get("/api/v1/samples/?per_page=200")
        assert resp.status_code == 200, resp.text
        listed = _listed(resp.json())
        assert f"{PREFIX}A" in listed, "own lab missing — filter over-narrowed"
        assert f"{PREFIX}B-PUB" in listed, "PUBLIC missing — policies not compiled in"
        assert f"{PREFIX}B" not in listed, "another lab's PRIVATE row leaked"
    finally:
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_samples_list_denies_everything_to_a_stranger(client, world, monkeypatch):
    """Default-deny: no grants means only what a policy admits."""
    emails: list[str] = []
    try:
        u = _stranger("b7none", monkeypatch)
        emails.append(u["email"])
        resp = await client.get("/api/v1/samples/?per_page=200")
        listed = _listed(resp.json())
        assert listed & {f"{PREFIX}A", f"{PREFIX}B"} == set()
        assert f"{PREFIX}B-PUB" in listed
    finally:
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_select_all_uses_the_same_filter_as_the_page(client, world, monkeypatch):
    """select_all takes a different code path; a filter applied to only one of
    the two is exactly the kind of gap a page-only test would miss."""
    emails: list[str] = []
    try:
        u = _member("b7sa", "Lab Reader", monkeypatch)
        emails.append(u["email"])
        page = await client.get("/api/v1/samples/?per_page=200")
        every = await client.get("/api/v1/samples/?select_all=true")
        assert every.status_code == 200, every.text
        assert set(every.json()["data"]["ids"]) == {r["id"] for r in page.json()["data"]}
    finally:
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_wastewater_lists_are_scoped(client, monkeypatch):
    emails: list[str] = []
    _cleanup()
    other_lab, other_project = _other_lab()
    _sample(
        f"{PREFIX}WW-A",
        lab_id=SEED_LAB_ID,
        project_id=SEED_PROJECT_ID,
        sector="environmental",
        wwtp_name="Plant-A",
    )
    _sample(
        f"{PREFIX}WW-B",
        lab_id=other_lab,
        project_id=other_project,
        sector="environmental",
        wwtp_name="Plant-B",
    )
    try:
        u = _member("b7ww", "Lab Reader", monkeypatch)
        emails.append(u["email"])
        resp = await client.get("/api/v1/wastewater/sites")
        assert resp.status_code == 200, resp.text
        sites = set(resp.json()["data"])
        assert "Plant-B" not in sites, "another lab's site leaked"
    finally:
        _cleanup()
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_files_list_follows_its_sample(client, world, monkeypatch):
    emails: list[str] = []
    for key in ("A", "B"):
        execute_write(
            "INSERT INTO sample_files (sample_id_fk, uri, filename, file_type, "
            "storage_state, ingest_method) "
            "VALUES (:s, :u, :f, 'fastq', 'EXTERNAL', 'register')",
            {"s": world[key]["id"], "u": f"gs://b/{key}.fastq", "f": f"{key}.fastq"},
        )
    try:
        u = _member("b7f", "Lab Reader", monkeypatch)
        emails.append(u["email"])
        resp = await client.get("/api/v1/files/?per_page=200")
        assert resp.status_code == 200, resp.text
        listed = {r["sample_id"] for r in resp.json()["data"]}
        assert f"{PREFIX}A" in listed
        assert f"{PREFIX}B" not in listed
    finally:
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_access_request_list_needs_the_approve_verb(client, world, monkeypatch):
    """The list shows a request only to its requester or someone who could act
    on it — the same verb the approve route checks."""
    emails: list[str] = []
    requester = _make_user(f"b7req-{uuid.uuid4().hex[:6]}@test.com")
    emails.append(
        execute_query("SELECT email FROM users WHERE id = :u", {"u": requester})[0]["email"]
    )
    execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, status, "
        "justification, requested_duration_days) "
        "VALUES (:s, :u, :o, 'PENDING', 'for an investigation', 30)",
        {"s": world["A"]["id"], "u": requester, "o": SEED_USER_ID},
    )
    try:
        # A plain reader in the sample's lab holds no access:approve_request.
        reader = _member("b7ar", "Lab Reader", monkeypatch)
        emails.append(reader["email"])
        resp = await client.get("/api/v1/sample-access/requests")
        assert resp.status_code == 200, resp.text
        assert all(r["sample_id"] != world["A"]["id"] for r in resp.json()["data"])

        # The director of that lab does.
        director = _member("b7ad", "Lab Director", monkeypatch)
        emails.append(director["email"])
        execute_write(
            "UPDATE lab_membership SET is_lab_director = TRUE WHERE user_id = :u AND lab_id = :l",
            {"u": director["id"], "l": SEED_LAB_ID},
        )
        sync_grants_from_legacy_roles()
        resp = await client.get("/api/v1/sample-access/requests")
        assert any(r["sample_id"] == world["A"]["id"] for r in resp.json()["data"])
    finally:
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_pipeline_run_list_is_project_scoped(client, monkeypatch):
    """Runs in another lab's project are not listed, but your own launch is."""
    emails: list[str] = []
    other_lab, other_project = _other_lab()
    mine = f"jp-{uuid.uuid4()}"
    theirs = f"jp-{uuid.uuid4()}"
    try:
        u = _member("b7pr", "Lab Reader", monkeypatch)
        emails.append(u["email"])
        for rid, lab, proj, launcher in (
            (mine, SEED_LAB_ID, SEED_PROJECT_ID, u["id"]),
            (theirs, other_lab, other_project, SEED_USER_ID),
        ):
            execute_write(
                "INSERT INTO pipeline_runs (lab_id, project_id, launched_by_id, "
                "pipeline_name, pipeline_version, sample_ids, status, launcher_type, "
                "run_id, pipeline_token, work_dir, result_uri) "
                "VALUES (:l, :p, :u, 'b7', '1.0.0', '{}', 'QUEUED', 'native', :r, :t, "
                "'gs://w', 'gs://r')",
                {"l": lab, "p": proj, "u": launcher, "r": rid, "t": f"pt_{uuid.uuid4().hex}"},
            )
        resp = await client.get("/api/v1/pipelines/?per_page=200")
        assert resp.status_code == 200, resp.text
        listed = {r["run_id"] for r in resp.json()["data"]}
        assert mine in listed
        assert theirs not in listed
    finally:
        for rid in (mine, theirs):
            execute_write("DELETE FROM pipeline_runs WHERE run_id = :r", {"r": rid})
        _cleanup_users(emails)
