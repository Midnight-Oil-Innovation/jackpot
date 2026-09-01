"""M2-B4 — the prepare/approve split, and the import-mapping read/manage split.

Both batches of routes turn on one boundary each, and in both cases the
check they replaced could not express it: a single "is a lab member" test
gated building a submission and sending it, and reading a mapping config and
rewriting it.

The seeded admin holds both halves (it is a platform admin *and* Lab Director
of lab 1), which is why the existing suites stayed green through this change
and why the boundary needs its own tests.
"""

import uuid

import pytest
from authz_helpers import sync_grants_from_legacy_roles

from backend.config import get_settings
from backend.database import execute_query, execute_write

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


def _cleanup_users(emails: list[str]) -> None:
    for e in emails:
        rows = execute_query("SELECT id FROM users WHERE email = :e", {"e": e})
        if not rows:
            continue
        uid = rows[0]["id"]
        execute_write(
            "UPDATE submissions SET created_by_user_id = 1 WHERE created_by_user_id = :u",
            {"u": uid},
        )
        execute_write("DELETE FROM import_mappings WHERE created_by_user_id = :u", {"u": uid})
        execute_write("DELETE FROM lab_membership WHERE user_id = :u", {"u": uid})
        execute_write(
            "DELETE FROM authz_capability_grants WHERE principal_id = :u", {"u": str(uid)}
        )
        execute_write("UPDATE audit_log SET actor_id = NULL WHERE actor_id = :u", {"u": uid})
        execute_write("DELETE FROM users WHERE id = :u", {"u": uid})


def _insert_sample() -> int:
    payload = {
        "sample_id": f"B4-{uuid.uuid4().hex[:8]}",
        "lab_id": SEED_LAB_ID,
        "project_id": SEED_PROJECT_ID,
        "owner_id": 1,
        "source_type": "Human",
        "organism_name": "Severe acute respiratory syndrome coronavirus 2",
        "type_of_experiment": "WGS",
        "library_preparation_method": "ARTIC",
        "sequencing_protocol": "https://www.protocols.io/view/artic-v4-1",
        "sequencing_platform": "Illumina",
        "sequencing_lab": "Example Sequencing Lab",
        "date_collected": "2026-01-15",
        "date_sequenced": "2026-01-17",
        "collection_facility": "Example Hospital",
        "collection_location_country": "United States",
        "sharing_level": "PRIVATE",
        "fastq_r1_uri": "gs://test/R1.fq.gz",
        "surveillance_relevant": False,
    }
    cols = sorted(payload)
    return execute_write(
        f"INSERT INTO samples ({', '.join(cols)}) "
        f"VALUES ({', '.join(':' + c for c in cols)}) RETURNING id",
        payload,
    )[0]["id"]


async def _new_submission(client) -> int:
    resp = await client.post(
        "/api/v1/submissions/",
        json={
            "lab_id": SEED_LAB_ID,
            "target_repository": "NCBI",
            "title": f"b4-{uuid.uuid4().hex[:6]}",
            "sample_ids": [_insert_sample()],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


# ───────────────────── submissions: prepare vs approve ────────────────────


@pytest.mark.asyncio
async def test_collaborator_may_prepare(client, monkeypatch):
    """submission:prepare sits in lab_member_rw — §8.2's note on that preset
    says a member cannot *approve* submissions, which distinguishes preparing
    from approving rather than putting submissions out of reach."""
    emails: list[str] = []
    try:
        u = _member("b4rw", "Lab Collaborator", monkeypatch)
        emails.append(u["email"])
        sid = await _new_submission(client)
        patched = await client.patch(f"/api/v1/submissions/{sid}", json={"title": "edited"})
        assert patched.status_code == 200, patched.text
        assert (await client.post(f"/api/v1/submissions/{sid}/validate")).status_code == 200
    finally:
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_a_collaborator_may_not_send_what_they_prepared(client, monkeypatch):
    """The separation this batch exists for. Before M2-B4 the *creator* of a
    submission could mark it submitted, execute it, and register accessions —
    the same person who built the package could send it."""
    emails: list[str] = []
    try:
        u = _member("b4sep", "Lab Collaborator", monkeypatch)
        emails.append(u["email"])
        sid = await _new_submission(client)
        # Each body must be VALID: FastAPI validates the body before the
        # handler runs, so an invalid one answers 422 and proves nothing
        # about the guard.
        for path, body in (
            (f"/api/v1/submissions/{sid}/mark-submitted", {}),
            (f"/api/v1/submissions/{sid}/mark-rejected", {"reason": "not this time"}),
            (f"/api/v1/submissions/{sid}/withdraw", {"reason": "changed our minds"}),
            (f"/api/v1/submissions/{sid}/execute", {}),
            (f"/api/v1/submissions/{sid}/retry-execution", {}),
        ):
            resp = await client.post(path, json=body)
            assert resp.status_code == 403, (path, resp.status_code, resp.text)
    finally:
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_a_lab_lead_holds_both_halves(client, monkeypatch):
    """Prepare and approve are separate verbs, not exclusive ones — §6.2-1b's
    separation-of-duties DENY covers deletion, not submissions."""
    emails: list[str] = []
    try:
        u = _member("b4lead", "Lab Director", monkeypatch, director=True)
        emails.append(u["email"])
        sid = await _new_submission(client)
        assert (
            await client.patch(f"/api/v1/submissions/{sid}", json={"title": "x"})
        ).status_code == 200
        # Past the guard; whatever the lifecycle says about a draft is not
        # this test's business.
        assert (
            await client.post(f"/api/v1/submissions/{sid}/mark-submitted", json={})
        ).status_code != 403
    finally:
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_a_reader_can_see_a_submission_but_not_build_one(client, monkeypatch):
    """Reads take sample:read, which every lab preset holds."""
    emails: list[str] = []
    try:
        author = _member("b4auth", "Lab Director", monkeypatch, director=True)
        emails.append(author["email"])
        sid = await _new_submission(client)

        reader = _member("b4ro", "Lab Reader", monkeypatch)
        emails.append(reader["email"])
        assert (await client.get(f"/api/v1/submissions/{sid}")).status_code == 200
        assert (
            await client.patch(f"/api/v1/submissions/{sid}", json={"title": "no"})
        ).status_code == 403
        # Valid payload, so a 403 is the guard talking and not the schema.
        assert (
            await client.post(
                "/api/v1/submissions/",
                json={
                    "lab_id": SEED_LAB_ID,
                    "target_repository": "NCBI",
                    "title": "no",
                    "sample_ids": [_insert_sample()],
                },
            )
        ).status_code == 403
    finally:
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_another_labs_member_reaches_nothing(client, monkeypatch):
    """Grants are scoped: the verb is held at a lab, not globally."""
    emails: list[str] = []
    other = execute_query("SELECT id FROM labs WHERE display_name = 'Other Lab'")
    other_lab = (
        other[0]["id"]
        if other
        else execute_write(
            "INSERT INTO labs (organization_id, display_name, description, created_by_id) "
            "VALUES (1, 'Other Lab', 'x', 1) RETURNING id"
        )[0]["id"]
    )
    try:
        author = _member("b4own", "Lab Director", monkeypatch, director=True)
        emails.append(author["email"])
        sid = await _new_submission(client)

        outsider = _member("b4out", "Lab Director", monkeypatch, lab_id=other_lab, director=True)
        emails.append(outsider["email"])
        assert (await client.get(f"/api/v1/submissions/{sid}")).status_code == 403
        assert (
            await client.patch(f"/api/v1/submissions/{sid}", json={"title": "no"})
        ).status_code == 403
    finally:
        _cleanup_users(emails)


# ──────────────────── import mappings: read vs manage ─────────────────────


async def _new_mapping(client) -> int:
    resp = await client.post(
        "/api/v1/import_mappings/",
        json={
            "lab_id": SEED_LAB_ID,
            "display_name": f"b4-map-{uuid.uuid4().hex[:6]}",
            "column_mapping": {"sample_id": "Sample"},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


@pytest.mark.asyncio
async def test_reader_may_read_a_mapping_but_not_rewrite_it(client, monkeypatch):
    """import:read is in every lab preset; import:manage is not in read-only.
    The membership test this replaced could not tell the two apart."""
    emails: list[str] = []
    try:
        author = _member("b4mw", "Lab Collaborator", monkeypatch)
        emails.append(author["email"])
        mid = await _new_mapping(client)

        reader = _member("b4mr", "Lab Reader", monkeypatch)
        emails.append(reader["email"])
        assert (await client.get(f"/api/v1/import_mappings/{mid}")).status_code == 200
        listed = await client.get("/api/v1/import_mappings/")
        assert listed.status_code == 200
        assert mid in {r["id"] for r in listed.json()["data"]}

        assert (
            await client.patch(f"/api/v1/import_mappings/{mid}", json={"display_name": "no"})
        ).status_code == 403
        assert (await client.delete(f"/api/v1/import_mappings/{mid}")).status_code == 403
    finally:
        _cleanup_users(emails)


@pytest.mark.asyncio
async def test_mapping_list_does_not_leak_another_lab(client, monkeypatch):
    """The list dropped a platform-admin bypass and a 'labs I am a member of'
    subquery for the compiled lab-level filter (M2-B7's builder)."""
    emails: list[str] = []
    try:
        author = _member("b4ml", "Lab Collaborator", monkeypatch)
        emails.append(author["email"])
        mid = await _new_mapping(client)

        other = execute_query("SELECT id FROM labs WHERE display_name = 'Other Lab'")
        other_lab = (
            other[0]["id"]
            if other
            else execute_write(
                "INSERT INTO labs (organization_id, display_name, description, created_by_id) "
                "VALUES (1, 'Other Lab', 'x', 1) RETURNING id"
            )[0]["id"]
        )
        outsider = _member("b4mo", "Lab Collaborator", monkeypatch, lab_id=other_lab)
        emails.append(outsider["email"])
        listed = await client.get("/api/v1/import_mappings/")
        assert listed.status_code == 200, listed.text
        assert mid not in {r["id"] for r in listed.json()["data"]}
    finally:
        _cleanup_users(emails)
