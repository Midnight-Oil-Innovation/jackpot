"""M2-B2 — route-level wiring tests for the sample-plane guards.

The pre-cutover harness (``tests/authz/``) proves ``permit()`` reaches the
right *decision*. It says nothing about whether a given route asks it the
right question — which capability, at which scope, before or after the side
effect. That is what this file pins, one case per converted route.

Each test drives a real HTTP request as a user holding exactly one thing, so
a route that quietly checked a different capability, checked at lab scope
where the map says Sample, or skipped the check entirely would fail here and
nowhere else.
"""

import uuid

import pytest
from authz_helpers import sync_grants_from_legacy_roles

from backend.config import get_settings
from backend.database import execute_query, execute_write

SEED_USER_ID = 1
SEED_LAB_ID = 1
SEED_PROJECT_ID = 1


# ─────────────────────────── fixtures / helpers ────────────────────────────


def _switch_user(email: str, monkeypatch) -> None:
    monkeypatch.setenv("MOCK_USER_EMAIL", email)
    get_settings.cache_clear()


def _make_user(email: str) -> int:
    rows = execute_write(
        "INSERT INTO users (email, name, organization_id, is_active) "
        "VALUES (:e, :e, 1, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET is_active = TRUE RETURNING id",
        {"e": email},
    )
    return rows[0]["id"]


def _add_membership(user_id: int, lab_id: int, role: str, *, is_director: bool = False) -> None:
    execute_write(
        "INSERT INTO lab_membership (user_id, lab_id, permission_group_id, is_lab_director) "
        "SELECT :u, :l, pg.id, :d FROM permission_groups pg WHERE pg.name = :r "
        "ON CONFLICT (user_id, lab_id) DO UPDATE SET "
        "permission_group_id = EXCLUDED.permission_group_id, "
        "is_lab_director = EXCLUDED.is_lab_director",
        {"u": user_id, "l": lab_id, "r": role, "d": is_director},
    )


def _other_lab() -> int:
    rows = execute_query("SELECT id FROM labs WHERE display_name = 'Other Lab'")
    if rows:
        return rows[0]["id"]
    lab_id = execute_write(
        "INSERT INTO labs (organization_id, display_name, description, created_by_id) "
        "VALUES (1, 'Other Lab', 'Test lab', 1) RETURNING id"
    )[0]["id"]
    execute_write(
        "INSERT INTO projects (lab_id, display_name, description, created_by_id) "
        "VALUES (:l, 'Other Project', 'x', 1)",
        {"l": lab_id},
    )
    return lab_id


def _project_of(lab_id: int) -> int:
    rows = execute_query(
        "SELECT id FROM projects WHERE lab_id = :l ORDER BY id LIMIT 1", {"l": lab_id}
    )
    return rows[0]["id"] if rows else SEED_PROJECT_ID


def _insert_sample(sample_id: str, *, lab_id, project_id, sharing_level="PRIVATE", **over) -> dict:
    payload = {
        "sample_id": sample_id,
        "lab_id": lab_id,
        "project_id": project_id,
        "owner_id": SEED_USER_ID,
        "source_type": "Human",
        "organism_name": "Severe acute respiratory syndrome coronavirus 2",
        "date_collected": "2026-01-15",
        "sequencing_lab": "Example Sequencing Lab",
        "type_of_experiment": "WGS",
        "library_preparation_method": "Illumina DNA Prep",
        "sequencing_protocol": "ARTIC v4.1",
        "sequencing_platform": "Illumina MiSeq",
        "date_sequenced": "2026-01-20",
        "collection_facility": "Example Facility",
        "collection_location_country": "USA",
        "sharing_level": sharing_level,
        "surveillance_relevant": False,
        "fastq_r1_uri": "gs://jackpot-sequences/test/R1.fastq.gz",
        "quality_status": "ANALYZABLE",
        "scrub_status": "PENDING",
    }
    payload.update(over)
    cols = ", ".join(payload)
    binds = ", ".join(f":{k}" for k in payload)
    return execute_write(f"INSERT INTO samples ({cols}) VALUES ({binds}) RETURNING *", payload)[0]


def _cleanup_samples(prefix: str) -> None:
    for r in execute_query("SELECT id FROM samples WHERE sample_id LIKE :p", {"p": f"{prefix}%"}):
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
        execute_write("DELETE FROM lab_membership WHERE user_id = :u", {"u": uid})
        execute_write(
            "DELETE FROM authz_capability_grants WHERE principal_id = :u", {"u": str(uid)}
        )
        execute_write(
            "DELETE FROM sample_access_requests WHERE requester_id = :u OR owner_id = :u",
            {"u": uid},
        )
        execute_write("UPDATE audit_log SET actor_id = NULL WHERE actor_id = :u", {"u": uid})
        execute_write("DELETE FROM users WHERE id = :u", {"u": uid})


@pytest.fixture
def outsider(monkeypatch):
    """An authenticated user with no membership anywhere and no grants."""
    email = f"outsider-{uuid.uuid4().hex[:6]}@test.com"
    uid = _make_user(email)
    sync_grants_from_legacy_roles()
    _switch_user(email, monkeypatch)
    yield {"id": uid, "email": email}
    _cleanup_users([email])


def _member(email_prefix: str, lab_id: int, role: str, monkeypatch, *, director=False) -> dict:
    email = f"{email_prefix}-{uuid.uuid4().hex[:6]}@test.com"
    uid = _make_user(email)
    _add_membership(uid, lab_id, role, is_director=director)
    sync_grants_from_legacy_roles()
    _switch_user(email, monkeypatch)
    return {"id": uid, "email": email}


# ───────────────────────────── samples router ──────────────────────────────


@pytest.mark.asyncio
async def test_sample_detail_denies_an_outsider(client, outsider):
    sid = "B2-DET-01"
    _cleanup_samples(sid)
    lab = _other_lab()
    s = _insert_sample(sid, lab_id=lab, project_id=_project_of(lab))
    try:
        resp = await client.get(f"/api/v1/samples/{s['id']}")
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_sample_detail_allows_a_lab_reader(client, monkeypatch):
    """sample:read_detail is in lab_member_ro — the weakest membership reads."""
    sid = "B2-DET-02"
    emails: list[str] = []
    _cleanup_samples(sid)
    lab = _other_lab()
    s = _insert_sample(sid, lab_id=lab, project_id=_project_of(lab))
    try:
        u = _member("reader", lab, "Lab Reader", monkeypatch)
        emails.append(u["email"])
        resp = await client.get(f"/api/v1/samples/{s['id']}")
        assert resp.status_code == 200, resp.text
    finally:
        _cleanup_samples(sid)
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_missing_sample_is_404_not_403(client, monkeypatch):
    """The fetch stays ahead of the guard, so 404 semantics are unchanged."""
    u = _member("admin2", SEED_LAB_ID, "Lab Director", monkeypatch, director=True)
    try:
        resp = await client.get("/api/v1/samples/99999999")
        assert resp.status_code == 404, resp.text
    finally:
        _cleanup_users([u["email"]])


@pytest.mark.asyncio
async def test_patch_denied_for_lab_reader_allowed_for_collaborator(client, monkeypatch):
    """sample:update is in lab_member_rw and deliberately not in lab_member_ro."""
    sid = "B2-PATCH-01"
    emails: list[str] = []
    _cleanup_samples(sid)
    lab = _other_lab()
    s = _insert_sample(sid, lab_id=lab, project_id=_project_of(lab))
    try:
        reader = _member("ro", lab, "Lab Reader", monkeypatch)
        emails.append(reader["email"])
        resp = await client.patch(f"/api/v1/samples/{s['id']}", json={"strain": "X"})
        assert resp.status_code == 403, resp.text

        rw = _member("rw", lab, "Lab Collaborator", monkeypatch)
        emails.append(rw["email"])
        resp = await client.patch(f"/api/v1/samples/{s['id']}", json={"strain": "X"})
        assert resp.status_code == 200, resp.text
    finally:
        _cleanup_samples(sid)
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_archive_needs_the_lead_preset_not_merely_write(client, monkeypatch):
    """sample:archive is lab_lead-only — a Collaborator who may update may not archive."""
    sid = "B2-ARCH-01"
    emails: list[str] = []
    _cleanup_samples(sid)
    lab = _other_lab()
    s = _insert_sample(sid, lab_id=lab, project_id=_project_of(lab))
    try:
        rw = _member("rw2", lab, "Lab Collaborator", monkeypatch)
        emails.append(rw["email"])
        resp = await client.delete(f"/api/v1/samples/{s['id']}")
        assert resp.status_code == 403, resp.text

        lead = _member("lead", lab, "Lab Director", monkeypatch, director=True)
        emails.append(lead["email"])
        resp = await client.delete(f"/api/v1/samples/{s['id']}")
        assert resp.status_code == 200, resp.text
    finally:
        _cleanup_samples(sid)
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_public_sample_is_readable_by_an_outsider(client, outsider):
    """The PUBLIC attribute-policy — no grant covers this caller at all."""
    sid = "B2-PUB-01"
    _cleanup_samples(sid)
    lab = _other_lab()
    s = _insert_sample(sid, lab_id=lab, project_id=_project_of(lab), sharing_level="PUBLIC")
    try:
        for path in (f"/api/v1/samples/{s['id']}", f"/api/v1/samples/{s['id']}/files"):
            resp = await client.get(path)
            assert resp.status_code == 200, (path, resp.text)
    finally:
        _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_public_is_readable_but_not_writable(client, outsider):
    """The permissive rungs are read-plane only."""
    sid = "B2-PUB-02"
    _cleanup_samples(sid)
    lab = _other_lab()
    s = _insert_sample(sid, lab_id=lab, project_id=_project_of(lab), sharing_level="PUBLIC")
    try:
        assert (
            await client.patch(f"/api/v1/samples/{s['id']}", json={"strain": "X"})
        ).status_code == 403
        assert (await client.delete(f"/api/v1/samples/{s['id']}")).status_code == 403
    finally:
        _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_download_denied_to_an_outsider(client, outsider):
    sid = "B2-DL-01"
    _cleanup_samples(sid)
    lab = _other_lab()
    s = _insert_sample(sid, lab_id=lab, project_id=_project_of(lab))
    try:
        resp = await client.get(f"/api/v1/samples/{s['id']}/download")
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup_samples(sid)


# ────────────────────────── sample-access router ───────────────────────────


@pytest.mark.asyncio
async def test_access_request_allowed_on_discoverable_denied_on_private(client, outsider):
    """access:request is held by nobody — the DISCOVERABLE policy is the only path."""
    _cleanup_samples("B2-REQ")
    lab = _other_lab()
    proj = _project_of(lab)
    disc = _insert_sample("B2-REQ-DISC", lab_id=lab, project_id=proj, sharing_level="DISCOVERABLE")
    priv = _insert_sample("B2-REQ-PRIV", lab_id=lab, project_id=proj, sharing_level="PRIVATE")
    try:
        ok = await client.post(
            "/api/v1/sample-access/requests",
            json={
                "sample_id": disc["id"],
                "justification": "for an outbreak investigation",
                "requested_duration_days": 30,
            },
        )
        assert ok.status_code == 201, ok.text

        denied = await client.post(
            "/api/v1/sample-access/requests",
            json={
                "sample_id": priv["id"],
                "justification": "for an outbreak investigation",
                "requested_duration_days": 30,
            },
        )
        assert denied.status_code == 403, denied.text
    finally:
        _cleanup_samples("B2-REQ")


@pytest.mark.asyncio
async def test_approve_denied_to_a_director_of_another_lab(client, monkeypatch):
    """Grants are scoped: a lab_lead grant on lab A does not reach a sample in lab B."""
    sid = "B2-APR-X"
    emails: list[str] = []
    _cleanup_samples(sid)
    lab = _other_lab()
    s = _insert_sample(sid, lab_id=lab, project_id=_project_of(lab), sharing_level="DISCOVERABLE")
    requester = _make_user(f"req-{uuid.uuid4().hex[:6]}@test.com")
    emails.append(
        execute_query("SELECT email FROM users WHERE id = :u", {"u": requester})[0]["email"]
    )
    req_id = execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, status, "
        "justification, requested_duration_days) "
        "VALUES (:s, :u, :o, 'PENDING', 'x', 30) RETURNING id",
        {"s": s["id"], "u": requester, "o": SEED_USER_ID},
    )[0]["id"]
    try:
        # Director of the *seed* lab, not the sample's lab.
        wrong = _member("otherld", SEED_LAB_ID, "Lab Director", monkeypatch, director=True)
        emails.append(wrong["email"])
        resp = await client.post(f"/api/v1/sample-access/requests/{req_id}/approve")
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup_samples(sid)
        _cleanup_users(emails)


# ───────────────────────────── ingest router ───────────────────────────────


@pytest.mark.asyncio
async def test_register_denied_into_a_lab_the_caller_cannot_write(client, monkeypatch):
    """Closes a real pre-M2 gap: lab_id came from the body and nothing checked it."""
    emails: list[str] = []
    _cleanup_samples("B2-ING")
    lab = _other_lab()
    try:
        # A Collaborator on the SEED lab, ingesting into Other Lab.
        u = _member("ing", SEED_LAB_ID, "Lab Collaborator", monkeypatch)
        emails.append(u["email"])
        body = {
            "sample_metadata": {
                "sample_id": "B2-ING-01",
                "lab_id": lab,
                "project_id": _project_of(lab),
                "source_type": "Human",
                "organism_name": "Severe acute respiratory syndrome coronavirus 2",
                "date_collected": "2026-01-15",
                "sequencing_lab": "Example Sequencing Lab",
                "external_case_id": "EX-1",
            },
            "files": [{"uri": "gs://bucket/B2-ING-01_R1.fastq.gz", "role": "R1"}],
        }
        resp = await client.post("/api/v1/ingest/register", json=body)
        assert resp.status_code == 403, resp.text

        body["sample_metadata"]["lab_id"] = SEED_LAB_ID
        body["sample_metadata"]["project_id"] = SEED_PROJECT_ID
        resp = await client.post("/api/v1/ingest/register", json=body)
        assert resp.status_code != 403, resp.text
    finally:
        _cleanup_samples("B2-ING")
        _cleanup_users(emails)


# ───────────────────────────── imports router ──────────────────────────────


@pytest.mark.asyncio
async def test_import_session_creation_denied_for_a_lab_reader(client, monkeypatch):
    """Narrower than the membership test it replaced: a Reader holds no sample:create."""
    emails: list[str] = []
    try:
        u = _member("impro", SEED_LAB_ID, "Lab Reader", monkeypatch)
        emails.append(u["email"])
        resp = await client.post(
            "/api/v1/imports/sessions/",
            data={"lab_id": str(SEED_LAB_ID)},
            files={"file": ("x.csv", b"sample_id\nA-1\n", "text/csv")},
        )
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup_users(emails)


# ────────────────────────────── files router ───────────────────────────────
#
# The file routes are the ones where a denial is *not* a 403: each collapses
# it into FILE_NOT_FOUND so the row's existence is not leaked. That makes
# them the easiest place for a missing guard to hide — a route that skipped
# the check entirely would return 200, and a route that kept the check would
# return 404, but nothing in between is distinguishable from the outside.


def _insert_file(sample_row: dict, *, filename="R1.fastq.gz") -> dict:
    return execute_write(
        "INSERT INTO sample_files (sample_id_fk, uri, filename, file_type, "
        "storage_state, ingest_method) "
        "VALUES (:s, :u, :f, 'fastq', 'EXTERNAL', 'register') RETURNING *",
        {
            "s": sample_row["id"],
            "u": f"gs://bucket/{sample_row['sample_id']}/{filename}",
            "f": filename,
        },
    )[0]


@pytest.mark.asyncio
async def test_file_detail_is_404_for_an_outsider_not_403(client, outsider):
    """The denial collapses into FILE_NOT_FOUND — existence must not leak."""
    sid = "B2-FILE-01"
    _cleanup_samples(sid)
    lab = _other_lab()
    s = _insert_sample(sid, lab_id=lab, project_id=_project_of(lab))
    f = _insert_file(s)
    try:
        resp = await client.get(f"/api/v1/files/{f['id']}")
        assert resp.status_code == 404, resp.text
        assert resp.json()["error"]["code"] == "FILE_NOT_FOUND"
    finally:
        _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_file_detail_visible_to_a_lab_reader(client, monkeypatch):
    """sample:read_detail, so the weakest membership sees the file."""
    sid = "B2-FILE-02"
    emails: list[str] = []
    _cleanup_samples(sid)
    lab = _other_lab()
    s = _insert_sample(sid, lab_id=lab, project_id=_project_of(lab))
    f = _insert_file(s)
    try:
        u = _member("fro", lab, "Lab Reader", monkeypatch)
        emails.append(u["email"])
        resp = await client.get(f"/api/v1/files/{f['id']}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["samples"][0]["id"] == s["id"]
    finally:
        _cleanup_samples(sid)
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_file_verify_needs_write_not_merely_read(client, monkeypatch):
    """verify takes sample:update — strictly narrower than get_file's read verb."""
    sid = "B2-FILE-03"
    emails: list[str] = []
    _cleanup_samples(sid)
    lab = _other_lab()
    s = _insert_sample(sid, lab_id=lab, project_id=_project_of(lab))
    f = _insert_file(s)
    try:
        reader = _member("vro", lab, "Lab Reader", monkeypatch)
        emails.append(reader["email"])
        # Can read it...
        assert (await client.get(f"/api/v1/files/{f['id']}")).status_code == 200
        # ...but not re-stat it.
        resp = await client.post(f"/api/v1/files/{f['id']}/verify")
        assert resp.status_code == 404, resp.text
        assert resp.json()["error"]["code"] == "FILE_NOT_FOUND"
    finally:
        _cleanup_samples(sid)
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_promote_allowed_for_collaborator_denied_for_reader(client, monkeypatch):
    """Pins the deliberate WIDENING: the map gives promote sample:update, which
    lab_member_rw holds — the legacy branch required a Lab Director."""
    sid = "B2-FILE-04"
    emails: list[str] = []
    _cleanup_samples(sid)
    lab = _other_lab()
    s = _insert_sample(sid, lab_id=lab, project_id=_project_of(lab))
    f = _insert_file(s)
    body = {"to": "MANAGED", "retention_policy": "STANDARD"}
    try:
        reader = _member("pro", lab, "Lab Reader", monkeypatch)
        emails.append(reader["email"])
        resp = await client.post(f"/api/v1/files/{f['id']}/promote", json=body)
        assert resp.status_code == 404, resp.text

        rw = _member("prw", lab, "Lab Collaborator", monkeypatch)
        emails.append(rw["email"])
        resp = await client.post(f"/api/v1/files/{f['id']}/promote", json=body)
        assert resp.status_code == 202, resp.text
    finally:
        _cleanup_samples(sid)
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_promote_job_lookup_is_scoped_to_the_file(client, monkeypatch):
    """The job id is predictable, so the lookup is guarded at the file's sample."""
    sid = "B2-FILE-05"
    emails: list[str] = []
    _cleanup_samples(sid)
    lab = _other_lab()
    s = _insert_sample(sid, lab_id=lab, project_id=_project_of(lab))
    f = _insert_file(s)
    try:
        rw = _member("jrw", lab, "Lab Collaborator", monkeypatch)
        emails.append(rw["email"])
        started = await client.post(
            f"/api/v1/files/{f['id']}/promote",
            json={"to": "MANAGED", "retention_policy": "STANDARD"},
        )
        assert started.status_code == 202, started.text
        job_id = started.json()["data"]["job_id"]

        assert (await client.get(f"/api/v1/files/jobs/{job_id}")).status_code == 200

        # An outsider holding nothing gets the same 404 an unknown job gets.
        email = f"nosy-{uuid.uuid4().hex[:6]}@test.com"
        _make_user(email)
        emails.append(email)
        sync_grants_from_legacy_roles()
        _switch_user(email, monkeypatch)
        resp = await client.get(f"/api/v1/files/jobs/{job_id}")
        assert resp.status_code == 404, resp.text
        assert resp.json()["error"]["code"] == "JOB_NOT_FOUND"
    finally:
        _cleanup_samples(sid)
        _cleanup_users(emails)


# ─────────────────── imports: the per-step re-check ────────────────────────


@pytest.mark.asyncio
async def test_import_session_steps_recheck_the_lab(client, monkeypatch):
    """Owning the session is not enough — the lab capability is re-checked on
    each step, so revoked membership stops an in-flight import."""
    emails: list[str] = []
    try:
        u = _member("impw", SEED_LAB_ID, "Lab Collaborator", monkeypatch)
        emails.append(u["email"])
        created = await client.post(
            "/api/v1/imports/sessions/",
            data={"lab_id": str(SEED_LAB_ID)},
            files={"file": ("x.csv", b"sample_id\nA-1\n", "text/csv")},
        )
        assert created.status_code == 201, created.text
        session_id = created.json()["data"]["id"]

        assert (await client.get(f"/api/v1/imports/sessions/{session_id}")).status_code == 200

        # Demote to Lab Reader and reseed: sample:create is gone, sample:read stays.
        _add_membership(u["id"], SEED_LAB_ID, "Lab Reader")
        execute_write(
            "DELETE FROM authz_capability_grants WHERE principal_id = :u", {"u": str(u["id"])}
        )
        sync_grants_from_legacy_roles()

        assert (await client.get(f"/api/v1/imports/sessions/{session_id}")).status_code == 200
        resp = await client.patch(
            f"/api/v1/imports/sessions/{session_id}", json={"current_step": 2}
        )
        assert resp.status_code == 403, resp.text
        resp = await client.delete(f"/api/v1/imports/sessions/{session_id}")
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup_users(emails)


# ───────────────────── ingest: the CSV per-row decision ────────────────────


@pytest.mark.asyncio
async def test_csv_rows_are_authorized_per_lab(client, monkeypatch):
    """A row targeting a lab the caller cannot write fails as that row's
    error; rows for a lab they can write still land."""
    emails: list[str] = []
    _cleanup_samples("B2-CSV")
    other = _other_lab()
    try:
        u = _member("csv", SEED_LAB_ID, "Lab Collaborator", monkeypatch)
        emails.append(u["email"])
        header = (
            "sample_id,lab_id,project_id,source_type,organism_name,date_collected,"
            "date_sequenced,sequencing_lab,type_of_experiment,library_preparation_method,"
            "sequencing_protocol,sequencing_platform,collection_facility,"
            "collection_location_country,external_case_id,files"
        )
        tail = (
            "Human,Severe acute respiratory syndrome coronavirus 2,2026-01-15,2026-01-20,"
            "Example Sequencing Lab,WGS,Illumina DNA Prep,ARTIC v4.1,"
            "Illumina,Example Facility,USA,EX-1,B2-CSV-{n}_R1.fastq.gz"
        )
        csv_text = "\n".join(
            [
                header,
                f"B2-CSV-1,{SEED_LAB_ID},{SEED_PROJECT_ID}," + tail.format(n=1),
                f"B2-CSV-2,{other},{_project_of(other)}," + tail.format(n=2),
            ]
        )
        resp = await client.post(
            "/api/v1/ingest/csv",
            files={"file": ("rows.csv", csv_text.encode(), "text/csv")},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        by_sample = {e["sample_id"]: str(e["detail"]) for e in data["errors"]}

        # The invariant is that the guard discriminated by lab. Asserted this
        # way rather than "row 1 succeeds" so the test does not also depend on
        # the validator's required-field list for Human samples, which is a
        # different rule that would otherwise break this one when it changes.
        assert "sample:create" in by_sample.get("B2-CSV-2", ""), data
        assert "sample:create" not in by_sample.get("B2-CSV-1", ""), data
    finally:
        _cleanup_samples("B2-CSV")
        _cleanup_users(emails)
