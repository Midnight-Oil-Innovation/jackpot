# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""B-CARE-3a..3g — sovereignty deletion lifecycle tests.

Covers the state machine (request → cancel/approve → reverse/vacuum),
derivative sealing, vacuum content erasure + mechanical invariant, the
RTBF deletion report, the retraction stub, and audit wiring for the
seven pre-existing deletion-adjacent AuditActions constants.
"""

import pytest
from authz_helpers import sync_grants_from_legacy_roles

from backend.config import get_settings
from backend.database import execute_query, execute_write
from backend.deletion import CONTENT_URI_COLUMNS

ADMIN = "admin@example.org"


def _mk_sample(sid: str) -> dict:
    return execute_write(
        "INSERT INTO samples (sample_id, lab_id, project_id, owner_id, source_type, "
        "organism_name, type_of_experiment, library_preparation_method, "
        "sequencing_protocol, sequencing_platform, sequencing_lab, date_collected, "
        "date_sequenced, collection_facility, collection_location_country, "
        "sharing_level, fastq_r1_uri) VALUES "
        f"('{sid}', 1, 1, 1, 'Human', "
        "'Severe acute respiratory syndrome coronavirus 2', 'WGS', 'ARTIC', "
        "'https://www.protocols.io/view/artic-v4-1', 'Illumina', "
        "'Example Sequencing Lab', '2026-01-15', '2026-01-17', 'Example Hospital', "
        f"'United States', 'PRIVATE', 'gs://jackpot-sequences/{sid}/R1.fastq.gz') "
        "RETURNING *",
    )[0]


def _mk_requester() -> int:
    return execute_write(
        "INSERT INTO users (email, name, organization_id, is_platform_admin, is_active) "
        "VALUES ('deletion-requester@example.org', 'Requester', 1, FALSE, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET is_active = TRUE RETURNING id",
    )[0]["id"]


def _cleanup(sid: str) -> None:
    rows = execute_query("SELECT id FROM samples WHERE sample_id = :s", {"s": sid})
    for r in rows:
        for q in (
            "DELETE FROM sample_files WHERE sample_id_fk = :id",
            "DELETE FROM external_retraction_requests WHERE sample_id = :id",
            "DELETE FROM dataset_files WHERE original_sample_id = :id",
            "DELETE FROM sample_access_grants WHERE sample_id = :id",
        ):
            execute_write(q, {"id": r["id"]})
        execute_write(
            "UPDATE audit_log SET actor_id = NULL WHERE resource_type = 'sample' "
            "AND resource_id = :rid",
            {"rid": str(r["id"])},
        )
        execute_write("DELETE FROM pipeline_results WHERE sample_id = :s", {"s": sid})
        execute_write("DELETE FROM samples WHERE id = :id", {"id": r["id"]})


@pytest.fixture
def as_admin(monkeypatch):
    monkeypatch.setenv("MOCK_USER_EMAIL", ADMIN)
    get_settings.cache_clear()


def _audit_actions(sample_pk: int) -> list[str]:
    return [
        r["action"]
        for r in execute_query(
            "SELECT action FROM audit_log WHERE resource_type = 'sample' "
            "AND resource_id = :rid ORDER BY id",
            {"rid": str(sample_pk)},
        )
    ]


async def _request(client, pk, reason="consent withdrawn"):
    return await client.post(f"/api/v1/samples/{pk}/request-deletion", json={"reason": reason})


# ── 3a/3b: request → approve (tombstone) ────────────────────────────────────


@pytest.mark.asyncio
async def test_full_lifecycle_request_approve_vacuum(client, as_admin):
    sid = "BCARE3-LIFE-01"
    _cleanup(sid)
    s = _mk_sample(sid)
    requester = _mk_requester()
    execute_write(
        "UPDATE samples SET owner_id = :u WHERE id = :id", {"u": requester, "id": s["id"]}
    )
    # derivative rows to seal / vacuum
    execute_write(
        "INSERT INTO pipeline_results (run_id, sample_id, metrics, results_json) "
        "VALUES ('run-bcare3', :sid, '{\"x\": 1}', '{\"y\": 2}') RETURNING id",
        {"sid": sid},
    )
    execute_write(
        "INSERT INTO sample_files (sample_id_fk, uri, filename) "
        "VALUES (:id, :uri, 'R1.fastq.gz') RETURNING id",
        {"id": s["id"], "uri": f"gs://jackpot-sequences/{sid}/R1.fastq.gz"},
    )
    execute_write(
        "INSERT INTO sample_access_grants (sample_id, requester_id) VALUES (:id, :u) RETURNING id",
        {"id": s["id"], "u": requester},
    )

    resp = await _request(client, s["id"])
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["deletion_status"] == "DELETION_REQUESTED"
    assert body["deletion_requested_at"] is not None
    assert body["deletion_reason"] == "consent withdrawn"

    # requester (admin) differs from deletion_requested_by? admin requested;
    # self-approve flag path for platform admin:
    resp = await client.post(
        f"/api/v1/samples/{s['id']}/approve-deletion",
        json={"platform_admin_self_approve": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["deletion_status"] == "TOMBSTONED"
    assert body["tombstoned_at"] is not None

    # sealing effects
    pr = execute_query("SELECT tombstoned FROM pipeline_results WHERE sample_id = :s", {"s": sid})
    assert all(r["tombstoned"] for r in pr)
    grants = execute_query(
        "SELECT revoked FROM sample_access_grants WHERE sample_id = :id", {"id": s["id"]}
    )
    assert all(g["revoked"] for g in grants)

    # tombstoned sample is invisible to the normal detail surface (§2)
    resp = await client.get(f"/api/v1/samples/{s['id']}")
    assert resp.status_code == 404

    # 3d vacuum-now (platform admin, justification required)
    resp = await client.post(
        f"/api/v1/samples/{s['id']}/vacuum-now", json={"justification": "test erasure"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["deletion_status"] == "VACUUMED"
    assert body["vacuumed_at"] is not None
    for col in CONTENT_URI_COLUMNS:
        assert body[col] is None
    assert (
        execute_query(
            "SELECT COUNT(*) AS n FROM sample_files WHERE sample_id_fk = :id", {"id": s["id"]}
        )[0]["n"]
        == 0
    )
    pr = execute_query("SELECT results_json FROM pipeline_results WHERE sample_id = :s", {"s": sid})
    assert all(r["results_json"].get("vacuumed") is True for r in pr)

    # 3g RTBF report reflects vacuumed state
    resp = await client.get(f"/api/v1/samples/{s['id']}/deletion-report")
    assert resp.status_code == 200
    report = resp.json()["data"]
    assert report["deletion_status"] == "VACUUMED"
    assert report["content_erased"] is True
    assert "REQUEST_DELETION" in [t["action"] for t in report["audit_trail"]]

    # 3f audit wiring — the deletion-adjacent constants all fired
    actions = _audit_actions(s["id"])
    for expected in (
        "REQUEST_DELETION",
        "APPROVE_DELETION",
        "SOFT_DELETE_SAMPLE",
        "COMPLETE_DELETION",
        "HARD_DELETE_SAMPLE",
    ):
        assert expected in actions, f"missing audit action {expected}"
    _cleanup(sid)


@pytest.mark.asyncio
async def test_duplicate_deletion_request_is_409(client, as_admin):
    """Failure path (3a/3b): tombstoning/requesting twice is rejected."""
    sid = "BCARE3-DUP-01"
    _cleanup(sid)
    s = _mk_sample(sid)
    assert (await _request(client, s["id"])).status_code == 200
    resp = await _request(client, s["id"])
    assert resp.status_code == 409
    _cleanup(sid)


@pytest.mark.asyncio
async def test_request_deletion_nonexistent_sample_404(client, as_admin):
    resp = await _request(client, 99999999)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_and_reverse_paths(client, as_admin):
    sid = "BCARE3-CXL-01"
    _cleanup(sid)
    s = _mk_sample(sid)
    # cancel from DELETION_REQUESTED
    assert (await _request(client, s["id"])).status_code == 200
    resp = await client.post(f"/api/v1/samples/{s['id']}/cancel-deletion")
    assert resp.status_code == 200
    assert resp.json()["data"]["deletion_status"] == "ACTIVE"
    # failure path: cancel with nothing pending
    resp = await client.post(f"/api/v1/samples/{s['id']}/cancel-deletion")
    assert resp.status_code == 409
    # reverse-tombstone restores ACTIVE — and un-revokes only the grants
    # that sealing revoked (a grant revoked beforehand stays revoked)
    requester = _mk_requester()
    live = execute_write(
        "INSERT INTO sample_access_grants (sample_id, requester_id) VALUES (:id, :u) RETURNING id",
        {"id": s["id"], "u": requester},
    )[0]["id"]
    prior = execute_write(
        "INSERT INTO sample_access_grants (sample_id, requester_id, revoked, revoked_at) "
        "VALUES (:id, :u, TRUE, NOW()) RETURNING id",
        {"id": s["id"], "u": requester},
    )[0]["id"]
    assert (await _request(client, s["id"])).status_code == 200
    resp = await client.post(
        f"/api/v1/samples/{s['id']}/approve-deletion",
        json={"platform_admin_self_approve": True},
    )
    assert resp.status_code == 200
    resp = await client.post(f"/api/v1/samples/{s['id']}/reverse-tombstone")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["deletion_status"] == "ACTIVE"
    assert body["tombstoned_at"] is None
    grants = {
        g["id"]: g["revoked"]
        for g in execute_query(
            "SELECT id, revoked FROM sample_access_grants WHERE sample_id = :id", {"id": s["id"]}
        )
    }
    assert grants[live] is False, "grant revoked by sealing must be restored"
    assert grants[prior] is True, "grant revoked before tombstoning must stay revoked"
    _cleanup(sid)


# ── 3c/3d failure paths ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_vacuum_rejected_unless_tombstoned(client, as_admin):
    """Failure path (3d + invariant): vacuum on an ACTIVE sample is 409."""
    sid = "BCARE3-VAC-409"
    _cleanup(sid)
    s = _mk_sample(sid)
    resp = await client.post(
        f"/api/v1/samples/{s['id']}/vacuum-now", json={"justification": "nope"}
    )
    assert resp.status_code == 409
    _cleanup(sid)


def test_vacuumed_content_gone_check_constraint():
    """Failure path: the DB refuses a VACUUMED row that still has content."""
    sid = "BCARE3-CHK-01"
    _cleanup(sid)
    s = _mk_sample(sid)
    with pytest.raises(Exception, match="samples_vacuumed_content_gone_chk"):
        execute_write(
            "UPDATE samples SET deletion_status = 'VACUUMED', "
            "deletion_requested_at = NOW(), vacuumed_at = NOW() "
            "WHERE id = :id RETURNING id",
            {"id": s["id"]},
        )
    _cleanup(sid)


def test_scheduled_vacuum_job_vacuums_due_tombstones(monkeypatch):
    """3c: the APScheduler job vacuums rows past the retention window and
    skips rows with no children without error (propagation no-op path)."""
    from backend.jobs import vacuum_tombstoned_samples_job

    sid = "BCARE3-JOB-01"
    _cleanup(sid)
    s = _mk_sample(sid)
    execute_write(
        "UPDATE samples SET deletion_status = 'TOMBSTONED', deletion_requested_at = NOW(), "
        "tombstoned_at = NOW() - INTERVAL '31 days' WHERE id = :id RETURNING id",
        {"id": s["id"]},
    )
    result = vacuum_tombstoned_samples_job()
    assert result["vacuumed"] >= 1
    row = execute_query("SELECT * FROM samples WHERE id = :id", {"id": s["id"]})[0]
    assert row["deletion_status"] == "VACUUMED"
    _cleanup(sid)


# ── 3e: pre-publish gate ────────────────────────────────────────────────────


def test_submission_gate_blocks_deletion_lifecycle_samples(as_admin):
    from fastapi import HTTPException

    from backend.submissions import add_samples_to_submission, create_submission

    sid = "BCARE3-SUB-01"
    sid_active = "BCARE3-SUB-ACT"
    _cleanup(sid)
    _cleanup(sid_active)
    s = _mk_sample(sid)
    active = _mk_sample(sid_active)
    execute_write(
        "UPDATE samples SET deletion_status = 'DELETION_REQUESTED', "
        "deletion_requested_at = NOW() WHERE id = :id RETURNING id",
        {"id": s["id"]},
    )
    sub = create_submission(
        user_id=1,
        lab_id=1,
        target_repository="NCBI",
        title="gate test",
        sample_ids=[active["id"]],
        conn=None,
    )
    with pytest.raises(HTTPException) as exc:
        add_samples_to_submission(
            submission_id=sub["id"], sample_ids=[s["id"]], actor_id=1, conn=None
        )
    assert exc.value.status_code == 422
    execute_write(
        "DELETE FROM submission_samples WHERE submission_id = :id RETURNING submission_id",
        {"id": sub["id"]},
    )
    execute_write("UPDATE submissions SET is_archived = TRUE WHERE id = :id", {"id": sub["id"]})
    _cleanup(sid)
    _cleanup(sid_active)


# ── 3g: retraction stub failure path ───────────────────────────────────────


@pytest.mark.asyncio
async def test_deletion_report_nonexistent_sample_404(client, as_admin):
    resp = await client.get("/api/v1/samples/99999999/deletion-report")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_retraction_request_recorded(client, as_admin):
    sid = "BCARE3-RTR-01"
    _cleanup(sid)
    s = _mk_sample(sid)
    resp = await client.post(
        f"/api/v1/samples/{s['id']}/retraction-requests",
        json={"repository": "NCBI", "accession": "SRR000001"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["status"] == "RECORDED"
    _cleanup(sid)


# ── 3f: constants wired, no parallel set ────────────────────────────────────


def test_deletion_audit_constants_have_call_sites():
    """Every pre-existing deletion-adjacent constant is used outside its
    definition; no parallel constants were introduced."""
    import pathlib

    backend_dir = pathlib.Path(__file__).resolve().parents[1] / "backend" / "backend"
    sources = "\n".join(p.read_text() for p in backend_dir.rglob("*.py") if p.name != "audit.py")
    for const in (
        "REQUEST_DELETION",
        "APPROVE_DELETION",
        "DENY_DELETION",
        "COMPLETE_DELETION",
        "SOFT_DELETE_SAMPLE",
        "HARD_DELETE_SAMPLE",
        "ARCHIVE_SAMPLE",
    ):
        assert f"AuditActions.{const}" in sources, f"{const} has no call site"


@pytest.mark.asyncio
async def test_non_admin_cannot_self_approve_via_the_request_flag(client, monkeypatch):
    """§6.2-1b's escape must be a capability, not caller-supplied input.

    Before M2-DROP-PRE the route passed ``platform_admin_self_approve`` from
    the request body straight into the policy condition, so the
    separation-of-duties DENY was liftable by anyone who set it. It was never
    exploitable end to end — ``deletion.py`` re-checked ``is_platform_admin``
    and 403'd — but that check reads a legacy column scheduled for removal,
    and removing it would have opened the hole. The route now ANDs the request
    with ``deletion:self_approve``, which only ``instance_administrator``
    holds.

    A Lab Lead is the right adversary here: they legitimately hold
    ``deletion:approve`` at their lab, so the only thing standing between them
    and approving their own deletion request is this rule.
    """
    sid = "DEL-SELFAPPROVE"
    _cleanup(sid)
    s = _mk_sample(sid)

    email = "lab-lead-selfapprove@example.org"
    uid = execute_write(
        "INSERT INTO users (email, name, organization_id, is_platform_admin, is_active) "
        "VALUES (:e, 'Lab Lead', 1, FALSE, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET is_active = TRUE RETURNING id",
        {"e": email},
    )[0]["id"]
    execute_write(
        "INSERT INTO lab_membership (user_id, lab_id, permission_group_id, is_lab_director) "
        "SELECT :u, 1, pg.id, TRUE FROM permission_groups pg WHERE pg.name = 'Lab Director' "
        "ON CONFLICT DO NOTHING",
        {"u": uid},
    )
    sync_grants_from_legacy_roles()

    monkeypatch.setenv("MOCK_USER_EMAIL", email)
    get_settings.cache_clear()

    resp = await client.post(
        f"/api/v1/samples/{s['id']}/request-deletion",
        json={"reason": "consent withdrawn"},
    )
    assert resp.status_code == 200, resp.text

    # Same actor, asking to skip the second pair of eyes.
    resp = await client.post(
        f"/api/v1/samples/{s['id']}/approve-deletion",
        json={"platform_admin_self_approve": True},
    )
    assert resp.status_code == 403, resp.text

    still = execute_query("SELECT deletion_status FROM samples WHERE id = :id", {"id": s["id"]})[0][
        "deletion_status"
    ]
    assert still == "DELETION_REQUESTED", "the deletion must not have been approved"

    execute_write("DELETE FROM lab_membership WHERE user_id = :u", {"u": uid})
    _cleanup(sid)
