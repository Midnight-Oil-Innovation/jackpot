"""
Session O — sample_access router end-to-end tests.

Covers every endpoint introduced in Session O plus the access-grant
expiry job and the can_access_sample() update:

    POST   /api/v1/sample-access/requests
    GET    /api/v1/sample-access/requests
    POST   /api/v1/sample-access/requests/{id}/approve
    POST   /api/v1/sample-access/requests/{id}/deny

The seed DB has admin@example.org (uid 1, Platform Admin) as a
member of Example Lab (id 1). Other-lab scenarios spin up a throw-away
lab + project so the access-control matrix can be exercised without
mutating the seed lab.
"""

from __future__ import annotations

import uuid

import pytest

from backend.config import get_settings
from backend.database import execute_query, execute_write
from backend.jobs import run_access_request_job
from backend.permissions import can_access_sample

SEED_USER_ID = 1
SEED_LAB_ID = 1
SEED_PROJECT_ID = 1


# ────────────────────────── helpers ──────────────────────────


def _switch_user(email: str, monkeypatch) -> None:
    monkeypatch.setenv("MOCK_USER_EMAIL", email)
    get_settings.cache_clear()


def _make_user(
    email: str,
    *,
    is_platform_admin: bool = False,
    is_data_analyst: bool = False,
) -> int:
    rows = execute_write(
        "INSERT INTO users (email, name, organization_id, "
        "is_platform_admin, is_data_analyst, is_active) "
        "VALUES (:e, :e, 1, :pa, :da, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET "
        "is_platform_admin = EXCLUDED.is_platform_admin, "
        "is_data_analyst = EXCLUDED.is_data_analyst, is_active = TRUE "
        "RETURNING id",
        {"e": email, "pa": is_platform_admin, "da": is_data_analyst},
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


def _ensure_other_lab() -> int:
    rows = execute_query("SELECT id FROM labs WHERE display_name = 'Other Lab O'")
    if rows:
        return rows[0]["id"]
    new = execute_write(
        "INSERT INTO labs (organization_id, display_name, description, created_by_id) "
        "VALUES (1, 'Other Lab O', 'Sample-access tests', 1) RETURNING id"
    )
    lab_id = new[0]["id"]
    execute_write(
        "INSERT INTO projects (lab_id, display_name, description, created_by_id) "
        "VALUES (:l, 'Other Project O', 'Other lab project', 1)",
        {"l": lab_id},
    )
    return lab_id


def _other_project_id(lab_id: int) -> int:
    rows = execute_query(
        "SELECT id FROM projects WHERE lab_id = :l ORDER BY id LIMIT 1",
        {"l": lab_id},
    )
    return rows[0]["id"]


def _insert_sample(
    sample_id: str,
    *,
    lab_id: int = SEED_LAB_ID,
    project_id: int = SEED_PROJECT_ID,
    owner_id: int = SEED_USER_ID,
    sharing_level: str = "DISCOVERABLE",
    organism_name: str = "Severe acute respiratory syndrome coronavirus 2",
) -> dict:
    payload = {
        "sample_id": sample_id,
        "lab_id": lab_id,
        "project_id": project_id,
        "owner_id": owner_id,
        "source_type": "Human",
        "organism_name": organism_name,
        "type_of_experiment": "WGS",
        "library_preparation_method": "ARTIC",
        "sequencing_protocol": "https://www.protocols.io/view/artic-v4-1",
        "sequencing_platform": "Illumina",
        "sequencing_lab": "Example Sequencing Lab",
        "date_collected": "2026-01-15",
        "date_sequenced": "2026-01-17",
        "collection_facility": "Example Hospital",
        "collection_location_country": "United States",
        "sharing_level": sharing_level,
        "fastq_r1_uri": "gs://jackpot-sequences/test/R1.fastq.gz",
        "scrub_status": "COMPLETE",
        "quality_status": "ANALYZABLE",
    }
    cols = sorted(payload.keys())
    placeholders = [f":{c}" for c in cols]
    rows = execute_write(
        f"INSERT INTO samples ({', '.join(cols)}) VALUES ({', '.join(placeholders)}) RETURNING *",
        payload,
    )
    return rows[0]


def _cleanup_samples(prefix: str) -> None:
    rows = execute_query(
        "SELECT id FROM samples WHERE sample_id LIKE :p",
        {"p": f"{prefix}%"},
    )
    for r in rows:
        sid = r["id"]
        execute_write("DELETE FROM sample_access_grants WHERE sample_id = :id", {"id": sid})
        execute_write("DELETE FROM sample_access_requests WHERE sample_id = :id", {"id": sid})
        execute_write("DELETE FROM sample_files WHERE sample_id_fk = :id", {"id": sid})
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'sample' AND resource_id = :rid",
            {"rid": str(sid)},
        )
        execute_write("DELETE FROM samples WHERE id = :id", {"id": sid})


def _cleanup_users(emails: list[str]) -> None:
    for e in emails:
        rows = execute_query("SELECT id FROM users WHERE email = :e", {"e": e})
        if not rows:
            continue
        uid = rows[0]["id"]
        execute_write("DELETE FROM lab_membership WHERE user_id = :u", {"u": uid})
        execute_write("DELETE FROM project_membership WHERE user_id = :u", {"u": uid})
        # Clear review/approve/deny FKs from any request this user touched so
        # the user row can be removed even after an approve/deny ran.
        execute_write(
            "UPDATE sample_access_requests SET reviewed_by_id = NULL WHERE reviewed_by_id = :u",
            {"u": uid},
        )
        execute_write(
            "UPDATE sample_access_requests SET approved_by_id = NULL WHERE approved_by_id = :u",
            {"u": uid},
        )
        execute_write(
            "UPDATE sample_access_requests SET denied_by_id = NULL WHERE denied_by_id = :u",
            {"u": uid},
        )
        execute_write(
            "DELETE FROM sample_access_grants WHERE requester_id = :u OR granted_by_id = :u",
            {"u": uid},
        )
        execute_write(
            "DELETE FROM sample_access_requests WHERE requester_id = :u OR owner_id = :u",
            {"u": uid},
        )
        # Any samples this user owns must go before the user row itself.
        owned = execute_query("SELECT id FROM samples WHERE owner_id = :u", {"u": uid})
        for row in owned:
            sid_pk = row["id"]
            execute_write("DELETE FROM sample_access_grants WHERE sample_id = :id", {"id": sid_pk})
            execute_write(
                "DELETE FROM sample_access_requests WHERE sample_id = :id", {"id": sid_pk}
            )
            execute_write("DELETE FROM sample_files WHERE sample_id_fk = :id", {"id": sid_pk})
            execute_write(
                "UPDATE audit_log SET actor_id = NULL "
                "WHERE resource_type = 'sample' AND resource_id = :rid",
                {"rid": str(sid_pk)},
            )
            execute_write("DELETE FROM samples WHERE id = :id", {"id": sid_pk})
        execute_write("UPDATE audit_log SET actor_id = NULL WHERE actor_id = :u", {"u": uid})
        execute_write("DELETE FROM users WHERE id = :u", {"u": uid})


def _get_request_row(req_id: int) -> dict:
    rows = execute_query("SELECT * FROM sample_access_requests WHERE id = :id", {"id": req_id})
    return rows[0]


def _get_grant_row(req_id: int) -> dict | None:
    rows = execute_query(
        "SELECT * FROM sample_access_grants WHERE request_id = :id ORDER BY id DESC LIMIT 1",
        {"id": req_id},
    )
    return rows[0] if rows else None


@pytest.fixture
def as_platform_admin(monkeypatch):
    _switch_user("admin@example.org", monkeypatch)


# ────────────────────────── POST /requests ──────────────────────────


@pytest.mark.asyncio
async def test_create_request_against_discoverable_returns_201(client, monkeypatch):
    sid = "O-CR-DISC"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid,
        lab_id=other_lab,
        project_id=other_project,
        sharing_level="DISCOVERABLE",
    )

    email = f"requester-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email])
    _make_user(email)
    _switch_user(email, monkeypatch)

    body = {
        "sample_id": s["id"],
        "justification": "Outbreak investigation requires full metadata.",
        "requested_duration_days": 30,
    }
    resp = await client.post("/api/v1/sample-access/requests", json=body)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["status"] == "PENDING"
    assert data["sample_id"] == s["id"]
    assert data["requested_duration_days"] == 30
    assert data["auto_approve_after"] is not None

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_create_request_against_private_returns_403(client, monkeypatch):
    sid = "O-CR-PRIV"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid,
        lab_id=other_lab,
        project_id=other_project,
        sharing_level="PRIVATE",
    )

    email = f"requester-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email])
    _make_user(email)
    _switch_user(email, monkeypatch)

    body = {
        "sample_id": s["id"],
        "justification": "Need this private sample for a study.",
        "requested_duration_days": 30,
    }
    resp = await client.post("/api/v1/sample-access/requests", json=body)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ACCESS_DENIED"

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_create_request_owner_self_returns_409(client, monkeypatch):
    sid = "O-CR-SELF"
    _cleanup_samples(sid)
    email = f"owner-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email])
    uid = _make_user(email)
    _switch_user(email, monkeypatch)
    s = _insert_sample(sid, owner_id=uid, sharing_level="DISCOVERABLE")

    body = {
        "sample_id": s["id"],
        "justification": "Trying to request my own sample.",
        "requested_duration_days": 30,
    }
    resp = await client.post("/api/v1/sample-access/requests", json=body)
    assert resp.status_code == 409
    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_create_request_duplicate_pending_returns_409(client, monkeypatch):
    sid = "O-CR-DUP"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid,
        lab_id=other_lab,
        project_id=other_project,
        sharing_level="DISCOVERABLE",
    )
    email = f"dup-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email])
    _make_user(email)
    _switch_user(email, monkeypatch)

    body = {
        "sample_id": s["id"],
        "justification": "First time asking.",
        "requested_duration_days": 14,
    }
    r1 = await client.post("/api/v1/sample-access/requests", json=body)
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/sample-access/requests", json=body)
    assert r2.status_code == 409

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_create_request_missing_sample_returns_404(client, as_platform_admin):
    body = {
        "sample_id": 999_999_999,
        "justification": "Asking about a sample that does not exist.",
        "requested_duration_days": 7,
    }
    resp = await client.post("/api/v1/sample-access/requests", json=body)
    assert resp.status_code == 404


# ────────────────────────── GET /requests ──────────────────────────


@pytest.mark.asyncio
async def test_list_requests_admin_sees_all(client, monkeypatch):
    sid = "O-LIST-ADM"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid,
        lab_id=other_lab,
        project_id=other_project,
        sharing_level="DISCOVERABLE",
    )
    email = f"req-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email])
    uid = _make_user(email)

    execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, "
        "status, justification, requested_duration_days) "
        "VALUES (:sid, :uid, :owner, 'PENDING', 'Test list as admin', 14)",
        {"sid": s["id"], "uid": uid, "owner": SEED_USER_ID},
    )

    _switch_user("admin@example.org", monkeypatch)
    resp = await client.get(f"/api/v1/sample-access/requests?sample_id={s['id']}")
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert any(r["sample_id"] == s["id"] for r in rows)

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_list_requests_requester_only_sees_own(client, monkeypatch):
    sid_a = "O-LIST-OWN-A"
    sid_b = "O-LIST-OWN-B"
    _cleanup_samples(sid_a)
    _cleanup_samples(sid_b)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s_a = _insert_sample(
        sid_a, lab_id=other_lab, project_id=other_project, sharing_level="DISCOVERABLE"
    )
    s_b = _insert_sample(
        sid_b, lab_id=other_lab, project_id=other_project, sharing_level="DISCOVERABLE"
    )

    email_self = f"self-{uuid.uuid4().hex[:6]}@test.com"
    email_other = f"other-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email_self, email_other])
    uid_self = _make_user(email_self)
    uid_other = _make_user(email_other)

    execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, "
        "status, justification, requested_duration_days) "
        "VALUES (:sid, :uid, :owner, 'PENDING', 'Mine', 14)",
        {"sid": s_a["id"], "uid": uid_self, "owner": SEED_USER_ID},
    )
    execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, "
        "status, justification, requested_duration_days) "
        "VALUES (:sid, :uid, :owner, 'PENDING', 'Other', 14)",
        {"sid": s_b["id"], "uid": uid_other, "owner": SEED_USER_ID},
    )

    _switch_user(email_self, monkeypatch)
    resp = await client.get("/api/v1/sample-access/requests")
    assert resp.status_code == 200
    rows = resp.json()["data"]
    requester_ids = {r["requester_id"] for r in rows}
    assert requester_ids == {uid_self}

    _cleanup_users([email_self, email_other])
    _cleanup_samples(sid_a)
    _cleanup_samples(sid_b)


@pytest.mark.asyncio
async def test_list_requests_lab_director_sees_lab_requests(client, monkeypatch):
    sid = "O-LIST-LD"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid, lab_id=other_lab, project_id=other_project, sharing_level="DISCOVERABLE"
    )

    email_ld = f"ld-{uuid.uuid4().hex[:6]}@test.com"
    email_req = f"req-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email_ld, email_req])
    uid_ld = _make_user(email_ld)
    _add_membership(uid_ld, other_lab, "Lab Director", is_director=True)
    uid_req = _make_user(email_req)
    execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, "
        "status, justification, requested_duration_days) "
        "VALUES (:sid, :uid, :owner, 'PENDING', 'Need access', 14)",
        {"sid": s["id"], "uid": uid_req, "owner": SEED_USER_ID},
    )

    _switch_user(email_ld, monkeypatch)
    resp = await client.get(f"/api/v1/sample-access/requests?lab_id={other_lab}")
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert any(r["sample_id"] == s["id"] and r["requester_id"] == uid_req for r in rows)

    _cleanup_users([email_ld, email_req])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_list_requests_filter_status(client, monkeypatch):
    sid = "O-LIST-STATUS"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid, lab_id=other_lab, project_id=other_project, sharing_level="DISCOVERABLE"
    )
    email = f"r-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email])
    uid = _make_user(email)
    execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, "
        "status, justification, requested_duration_days) "
        "VALUES (:sid, :uid, :owner, 'DENIED', 'Old denied req', 14)",
        {"sid": s["id"], "uid": uid, "owner": SEED_USER_ID},
    )

    _switch_user("admin@example.org", monkeypatch)
    resp = await client.get(f"/api/v1/sample-access/requests?status=DENIED&sample_id={s['id']}")
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert all(r["status"] == "DENIED" for r in rows)

    _cleanup_users([email])
    _cleanup_samples(sid)


# ────────────────────────── /approve ──────────────────────────


@pytest.mark.asyncio
async def test_approve_as_lab_director_creates_grant(client, monkeypatch):
    sid = "O-APR-LD"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid, lab_id=other_lab, project_id=other_project, sharing_level="DISCOVERABLE"
    )

    email_ld = f"ld-{uuid.uuid4().hex[:6]}@test.com"
    email_req = f"req-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email_ld, email_req])
    uid_ld = _make_user(email_ld)
    _add_membership(uid_ld, other_lab, "Lab Director", is_director=True)
    uid_req = _make_user(email_req)

    inserted = execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, "
        "status, justification, requested_duration_days) "
        "VALUES (:sid, :uid, :owner, 'PENDING', 'Approve me', 30) RETURNING id",
        {"sid": s["id"], "uid": uid_req, "owner": SEED_USER_ID},
    )
    req_id = inserted[0]["id"]

    _switch_user(email_ld, monkeypatch)
    resp = await client.post(f"/api/v1/sample-access/requests/{req_id}/approve")
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["request"]["status"] == "APPROVED"
    assert body["grant"]["sample_id"] == s["id"]
    assert body["grant"]["requester_id"] == uid_req

    grant = _get_grant_row(req_id)
    assert grant is not None
    assert grant["revoked"] is False

    _cleanup_users([email_ld, email_req])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_approve_grant_unlocks_can_access_sample(client, monkeypatch):
    """Sanity check the can_access_sample() update — grant flips access from False to True."""
    sid = "O-APR-CAN"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid, lab_id=other_lab, project_id=other_project, sharing_level="DISCOVERABLE"
    )

    email_ld = f"ld-{uuid.uuid4().hex[:6]}@test.com"
    email_req = f"req-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email_ld, email_req])
    uid_ld = _make_user(email_ld)
    _add_membership(uid_ld, other_lab, "Lab Director", is_director=True)
    uid_req = _make_user(email_req)
    requester = {"id": uid_req, "is_platform_admin": False}

    # Before any request — DISCOVERABLE is visible but detail access is denied.
    assert can_access_sample(requester, s) is False

    inserted = execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, "
        "status, justification, requested_duration_days) "
        "VALUES (:sid, :uid, :owner, 'PENDING', 'Need access', 60) RETURNING id",
        {"sid": s["id"], "uid": uid_req, "owner": SEED_USER_ID},
    )
    req_id = inserted[0]["id"]

    _switch_user(email_ld, monkeypatch)
    resp = await client.post(f"/api/v1/sample-access/requests/{req_id}/approve")
    assert resp.status_code == 200

    assert can_access_sample(requester, s) is True

    _cleanup_users([email_ld, email_req])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_approve_as_non_director_returns_403(client, monkeypatch):
    sid = "O-APR-403"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid, lab_id=other_lab, project_id=other_project, sharing_level="DISCOVERABLE"
    )

    email_outsider = f"out-{uuid.uuid4().hex[:6]}@test.com"
    email_req = f"req-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email_outsider, email_req])
    _make_user(email_outsider)
    uid_req = _make_user(email_req)
    inserted = execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, "
        "status, justification, requested_duration_days) "
        "VALUES (:sid, :uid, :owner, 'PENDING', 'No', 7) RETURNING id",
        {"sid": s["id"], "uid": uid_req, "owner": SEED_USER_ID},
    )
    req_id = inserted[0]["id"]

    _switch_user(email_outsider, monkeypatch)
    resp = await client.post(f"/api/v1/sample-access/requests/{req_id}/approve")
    assert resp.status_code == 403

    _cleanup_users([email_outsider, email_req])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_approve_already_decided_returns_409(client, as_platform_admin):
    sid = "O-APR-DECIDED"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid, lab_id=other_lab, project_id=other_project, sharing_level="DISCOVERABLE"
    )
    email = f"r-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email])
    uid = _make_user(email)
    inserted = execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, "
        "status, justification, requested_duration_days) "
        "VALUES (:sid, :uid, :owner, 'DENIED', 'Already', 7) RETURNING id",
        {"sid": s["id"], "uid": uid, "owner": SEED_USER_ID},
    )
    req_id = inserted[0]["id"]
    resp = await client.post(f"/api/v1/sample-access/requests/{req_id}/approve")
    assert resp.status_code == 409

    _cleanup_users([email])
    _cleanup_samples(sid)


# ────────────────────────── /deny ──────────────────────────


@pytest.mark.asyncio
async def test_deny_as_lab_director_sets_status(client, monkeypatch):
    sid = "O-DEN-LD"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid, lab_id=other_lab, project_id=other_project, sharing_level="DISCOVERABLE"
    )

    email_ld = f"ld-{uuid.uuid4().hex[:6]}@test.com"
    email_req = f"req-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email_ld, email_req])
    uid_ld = _make_user(email_ld)
    _add_membership(uid_ld, other_lab, "Lab Director", is_director=True)
    uid_req = _make_user(email_req)
    inserted = execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, "
        "status, justification, requested_duration_days) "
        "VALUES (:sid, :uid, :owner, 'PENDING', 'Plz', 7) RETURNING id",
        {"sid": s["id"], "uid": uid_req, "owner": SEED_USER_ID},
    )
    req_id = inserted[0]["id"]

    _switch_user(email_ld, monkeypatch)
    resp = await client.post(
        f"/api/v1/sample-access/requests/{req_id}/deny",
        json={"denial_reason": "Not appropriate for the requested study."},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] == "DENIED"
    assert "Not appropriate" in body["denial_reason"]

    grant = _get_grant_row(req_id)
    assert grant is None

    _cleanup_users([email_ld, email_req])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_deny_as_non_director_returns_403(client, monkeypatch):
    sid = "O-DEN-403"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid, lab_id=other_lab, project_id=other_project, sharing_level="DISCOVERABLE"
    )

    email_outsider = f"out-{uuid.uuid4().hex[:6]}@test.com"
    email_req = f"req-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email_outsider, email_req])
    _make_user(email_outsider)
    uid_req = _make_user(email_req)
    inserted = execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, "
        "status, justification, requested_duration_days) "
        "VALUES (:sid, :uid, :owner, 'PENDING', 'No', 7) RETURNING id",
        {"sid": s["id"], "uid": uid_req, "owner": SEED_USER_ID},
    )
    req_id = inserted[0]["id"]

    _switch_user(email_outsider, monkeypatch)
    resp = await client.post(f"/api/v1/sample-access/requests/{req_id}/deny")
    assert resp.status_code == 403

    _cleanup_users([email_outsider, email_req])
    _cleanup_samples(sid)


# ────────────────────────── can_access_sample / expiry ──────────────────────────


@pytest.mark.asyncio
async def test_expired_grant_blocks_access():
    """Grant past its access_expires_at must NOT grant access."""
    sid = "O-EXP-BLK"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid, lab_id=other_lab, project_id=other_project, sharing_level="DISCOVERABLE"
    )

    email = f"exp-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email])
    uid = _make_user(email)

    execute_write(
        "INSERT INTO sample_access_grants (sample_id, requester_id, granted_by_id, "
        "access_expires_at) "
        "VALUES (:sid, :uid, :uid, NOW() - INTERVAL '1 day')",
        {"sid": s["id"], "uid": uid},
    )
    user_dict = {"id": uid, "is_platform_admin": False}
    assert can_access_sample(user_dict, s) is False

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_active_grant_allows_access():
    sid = "O-EXP-OK"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid, lab_id=other_lab, project_id=other_project, sharing_level="DISCOVERABLE"
    )

    email = f"act-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email])
    uid = _make_user(email)
    execute_write(
        "INSERT INTO sample_access_grants (sample_id, requester_id, granted_by_id, "
        "access_expires_at) "
        "VALUES (:sid, :uid, :uid, NOW() + INTERVAL '30 days')",
        {"sid": s["id"], "uid": uid},
    )
    user_dict = {"id": uid, "is_platform_admin": False}
    assert can_access_sample(user_dict, s) is True

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_revoked_grant_blocks_access():
    sid = "O-REV-BLK"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid, lab_id=other_lab, project_id=other_project, sharing_level="DISCOVERABLE"
    )

    email = f"rev-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email])
    uid = _make_user(email)
    execute_write(
        "INSERT INTO sample_access_grants (sample_id, requester_id, granted_by_id, "
        "access_expires_at, revoked, revoked_at) "
        "VALUES (:sid, :uid, :uid, NOW() + INTERVAL '30 days', TRUE, NOW())",
        {"sid": s["id"], "uid": uid},
    )
    user_dict = {"id": uid, "is_platform_admin": False}
    assert can_access_sample(user_dict, s) is False

    _cleanup_users([email])
    _cleanup_samples(sid)


# ────────────────────────── background job ──────────────────────────


@pytest.mark.asyncio
async def test_job_auto_approves_overdue_pending():
    sid = "O-JOB-AUTO"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid, lab_id=other_lab, project_id=other_project, sharing_level="DISCOVERABLE"
    )

    email = f"auto-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email])
    uid = _make_user(email)
    inserted = execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, "
        "status, justification, requested_duration_days, auto_approve_after) "
        "VALUES (:sid, :uid, :owner, 'PENDING', 'Auto', 30, NOW() - INTERVAL '1 day') "
        "RETURNING id",
        {"sid": s["id"], "uid": uid, "owner": SEED_USER_ID},
    )
    req_id = inserted[0]["id"]

    await run_access_request_job()

    after = _get_request_row(req_id)
    assert after["status"] == "AUTO_APPROVED"
    grant = _get_grant_row(req_id)
    assert grant is not None
    assert grant["revoked"] is False

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_job_expires_grants_past_window():
    sid = "O-JOB-EXP"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid, lab_id=other_lab, project_id=other_project, sharing_level="DISCOVERABLE"
    )

    email = f"jexp-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email])
    uid = _make_user(email)

    inserted = execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, "
        "status, justification, requested_duration_days, "
        "approved_at, access_expires_at) "
        "VALUES (:sid, :uid, :owner, 'APPROVED', 'Pre-expired', 1, "
        "NOW() - INTERVAL '2 days', NOW() - INTERVAL '1 day') RETURNING id",
        {"sid": s["id"], "uid": uid, "owner": SEED_USER_ID},
    )
    req_id = inserted[0]["id"]
    execute_write(
        "INSERT INTO sample_access_grants (sample_id, requester_id, request_id, "
        "granted_by_id, access_expires_at) "
        "VALUES (:sid, :uid, :req, :uid, NOW() - INTERVAL '1 day')",
        {"sid": s["id"], "uid": uid, "req": req_id},
    )

    await run_access_request_job()

    grant = _get_grant_row(req_id)
    assert grant is not None
    assert grant["revoked"] is True
    after_req = _get_request_row(req_id)
    assert after_req["status"] == "EXPIRED"

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_job_moots_request_when_sample_becomes_public():
    sid = "O-JOB-MOOT"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid, lab_id=other_lab, project_id=other_project, sharing_level="DISCOVERABLE"
    )

    email = f"moot-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email])
    uid = _make_user(email)
    inserted = execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, "
        "status, justification, requested_duration_days, auto_approve_after) "
        "VALUES (:sid, :uid, :owner, 'PENDING', 'Will be public', 14, "
        "NOW() + INTERVAL '5 days') RETURNING id",
        {"sid": s["id"], "uid": uid, "owner": SEED_USER_ID},
    )
    req_id = inserted[0]["id"]
    execute_write(
        "UPDATE samples SET sharing_level = 'PUBLIC' WHERE id = :id",
        {"id": s["id"]},
    )

    await run_access_request_job()
    after = _get_request_row(req_id)
    assert after["status"] == "MOOT"

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_job_sends_75_day_warning_once():
    sid = "O-JOB-WARN"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _other_project_id(other_lab)
    s = _insert_sample(
        sid, lab_id=other_lab, project_id=other_project, sharing_level="DISCOVERABLE"
    )

    email_ld = f"ld-{uuid.uuid4().hex[:6]}@test.com"
    email_req = f"req-{uuid.uuid4().hex[:6]}@test.com"
    _cleanup_users([email_ld, email_req])
    uid_ld = _make_user(email_ld)
    _add_membership(uid_ld, other_lab, "Lab Director", is_director=True)
    uid_req = _make_user(email_req)

    inserted = execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, "
        "status, justification, requested_duration_days, auto_approve_after) "
        "VALUES (:sid, :uid, :owner, 'PENDING', 'Soon-due', 30, "
        "NOW() + INTERVAL '5 days') RETURNING id",
        {"sid": s["id"], "uid": uid_req, "owner": SEED_USER_ID},
    )
    req_id = inserted[0]["id"]

    await run_access_request_job()

    notes = execute_query(
        "SELECT * FROM notifications WHERE recipient_id = :uid "
        "AND event_type = 'ACCESS_APPROVE_WARNING' "
        "AND resource_id = :rid",
        {"uid": uid_ld, "rid": str(req_id)},
    )
    assert len(notes) == 1

    # Re-running must not double-fire (last_warning_sent_at gates it).
    await run_access_request_job()
    notes2 = execute_query(
        "SELECT * FROM notifications WHERE recipient_id = :uid "
        "AND event_type = 'ACCESS_APPROVE_WARNING' "
        "AND resource_id = :rid",
        {"uid": uid_ld, "rid": str(req_id)},
    )
    assert len(notes2) == 1

    _cleanup_users([email_ld, email_req])
    _cleanup_samples(sid)
