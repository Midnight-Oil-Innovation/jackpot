# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""M2-DROP-PRE slice 2 — which principal shape reaches which deletion-plane route.

**Why this file exists at all.** The baseline migration seeds
``admin@example.org`` as a platform admin *and* as Lab Director of lab 1, so
every pre-existing test that acts "as admin" holds the Instance Administrator
grants and the Lab Lead grants at once. Those tests stayed green through this
batch — including the two routes it deliberately takes away from an
instance admin — because the lab_lead grant carried them. A green suite said
nothing about which rung fired.

So every principal here is built to hold exactly one shape:

- ``pure_admin``     platform admin, NO lab membership  -> instance_administrator only
- ``lab_lead``       Lab Director of lab 1, not an admin -> lab_lead only
- ``lab_reader``     Lab Reader of lab 1                 -> lab_member_ro only
- ``outsider``       no membership anywhere, owns nothing -> no grants on lab 1

and the assertions are about the *difference* between them.

The line the batch drew (access_model.md §4.1, §4.5, §8.2): an instance admin
keeps routes that read or execute a governance RECORD, and loses routes that
return sample CONTENT or make a consent decision.
"""

import pytest
from authz_helpers import (
    ADMIN_PRESET,
    grant_instance_preset,
    sync_grants_from_legacy_roles,
)

from backend.config import get_settings
from backend.database import execute_query, execute_write

LAB_ID = 1
PURE_ADMIN = "slice2-pure-admin@example.org"
LAB_LEAD = "slice2-lab-lead@example.org"
LAB_READER = "slice2-lab-reader@example.org"
OUTSIDER = "slice2-outsider@example.org"
EMAILS = (PURE_ADMIN, LAB_LEAD, LAB_READER, OUTSIDER)


def _mk_user(email: str, *, admin: bool = False) -> int:
    uid = execute_write(
        "INSERT INTO users (email, name, organization_id, is_active) "
        "VALUES (:e, :e, 1, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET is_active = TRUE RETURNING id",
        {"e": email},
    )[0]["id"]
    # The instance role is the grants now (M2-DROP). Both directions, because
    # this upserts on a re-used email: the whole point of these personas is
    # that each holds EXACTLY one role, so a leftover grant defeats the file.
    grant_instance_preset(uid, ADMIN_PRESET if admin else None)
    return uid


def _add_membership(user_id: int, group: str, *, director: bool) -> None:
    execute_write(
        "INSERT INTO lab_membership (user_id, lab_id, permission_group_id, is_lab_director) "
        "SELECT :u, :l, pg.id, :d FROM permission_groups pg WHERE pg.name = :g "
        "ON CONFLICT (user_id, lab_id) DO UPDATE SET "
        "permission_group_id = EXCLUDED.permission_group_id, "
        "is_lab_director = EXCLUDED.is_lab_director",
        {"u": user_id, "l": LAB_ID, "g": group, "d": director},
    )


def _act_as(email: str, monkeypatch) -> None:
    monkeypatch.setenv("MOCK_USER_EMAIL", email)
    get_settings.cache_clear()


@pytest.fixture
def principals():
    """Four single-shape principals, with their grants materialized."""
    ids = {
        PURE_ADMIN: _mk_user(PURE_ADMIN, admin=True),
        LAB_LEAD: _mk_user(LAB_LEAD),
        LAB_READER: _mk_user(LAB_READER),
        OUTSIDER: _mk_user(OUTSIDER),
    }
    # The pure admin's defining property: no lab_membership row at all. An
    # ON CONFLICT upsert cannot express "no row", so delete any leftover.
    execute_write(
        "DELETE FROM lab_membership WHERE user_id IN (:a, :o)",
        {"a": ids[PURE_ADMIN], "o": ids[OUTSIDER]},
    )
    _add_membership(ids[LAB_LEAD], "Lab Director", director=True)
    _add_membership(ids[LAB_READER], "Lab Reader", director=False)
    sync_grants_from_legacy_roles()
    yield ids
    for uid in ids.values():
        execute_write(
            "DELETE FROM authz_capability_grants WHERE principal_id = :p", {"p": str(uid)}
        )
        execute_write("DELETE FROM lab_membership WHERE user_id = :u", {"u": uid})
        execute_write("UPDATE samples SET owner_id = 1 WHERE owner_id = :u", {"u": uid})
        execute_write("UPDATE audit_log SET actor_id = NULL WHERE actor_id = :u", {"u": uid})
        execute_write("DELETE FROM users WHERE id = :u", {"u": uid})


def _mk_sample(sid: str, **overrides) -> dict:
    _cleanup(sid)
    cols = {
        "sample_id": sid,
        "lab_id": LAB_ID,
        "project_id": 1,
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
        "fastq_r1_uri": f"gs://jackpot-sequences/{sid}/R1.fastq.gz",
        **overrides,
    }
    names = ", ".join(cols)
    binds = ", ".join(f":{k}" for k in cols)
    return execute_write(f"INSERT INTO samples ({names}) VALUES ({binds}) RETURNING *", cols)[0]  # noqa: S608


def _cleanup(sid: str) -> None:
    for row in execute_query("SELECT id FROM samples WHERE sample_id = :s", {"s": sid}):
        execute_write(
            "DELETE FROM external_retraction_requests WHERE sample_id = :id", {"id": row["id"]}
        )
        execute_write(
            "UPDATE audit_log SET actor_id = NULL WHERE resource_type = 'sample' "
            "AND resource_id = :rid",
            {"rid": str(row["id"])},
        )
    execute_write("DELETE FROM samples WHERE sample_id = :s", {"s": sid})


def _tombstone(sample_pk: int, requester_id: int = 1) -> None:
    """Straight to TOMBSTONED, skipping the request/approve routes.

    ``deletion_requested_at`` is not optional decoration:
    ``samples_deletion_active_requested_chk`` asserts
    ``(deletion_status = 'ACTIVE') = (deletion_requested_at IS NULL)``, so a
    tombstone without a request timestamp is rejected by the database.
    """
    execute_write(
        "UPDATE samples SET deletion_status = 'TOMBSTONED', "
        "deletion_requested_at = CURRENT_TIMESTAMP, "
        "deletion_requested_by_user_id = :u, deletion_reason = 'slice2 fixture', "
        "tombstoned_at = CURRENT_TIMESTAMP WHERE id = :id RETURNING id",
        {"id": sample_pk, "u": requester_id},
    )


# ── the record half: an instance admin KEEPS these ──────────────────────────


@pytest.mark.asyncio
async def test_pure_instance_admin_reads_the_deletion_report(client, principals, monkeypatch):
    """deletion:read_report is in the Instance Administrator preset.

    This is the assertion the seeded dual-role admin could not make: with no
    lab membership, the only grant that can carry this is the instance one.
    """
    s = _mk_sample("SLICE2-RPT-ADMIN")
    _act_as(PURE_ADMIN, monkeypatch)
    resp = await client.get(f"/api/v1/samples/{s['id']}/deletion-report")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["sample_id"] == s["id"]
    _cleanup("SLICE2-RPT-ADMIN")


@pytest.mark.asyncio
async def test_pure_instance_admin_reverses_a_tombstone_and_vacuums(
    client, principals, monkeypatch
):
    """Both operational verbs survive the drop of the is_platform_admin read."""
    s = _mk_sample("SLICE2-OPS-ADMIN")
    _tombstone(s["id"])
    _act_as(PURE_ADMIN, monkeypatch)

    resp = await client.post(f"/api/v1/samples/{s['id']}/reverse-tombstone")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["deletion_status"] == "ACTIVE"

    _tombstone(s["id"])
    resp = await client.post(
        f"/api/v1/samples/{s['id']}/vacuum-now", json={"justification": "slice2 test"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["deletion_status"] == "VACUUMED"
    _cleanup("SLICE2-OPS-ADMIN")


@pytest.mark.asyncio
async def test_lab_reader_reads_the_deletion_report(client, principals, monkeypatch):
    """_require_lab_tie admitted ANY lab member; read-only keeps the report."""
    s = _mk_sample("SLICE2-RPT-RO")
    _act_as(LAB_READER, monkeypatch)
    resp = await client.get(f"/api/v1/samples/{s['id']}/deletion-report")
    assert resp.status_code == 200, resp.text
    _cleanup("SLICE2-RPT-RO")


@pytest.mark.asyncio
async def test_owner_outside_the_lab_still_reads_the_report(client, principals, monkeypatch):
    """The LADDER_POLICIES owner_id rung, which is the only thing carrying this.

    ``outsider`` holds no grant on lab 1 — the preceding test proves a
    non-member is refused — so a 200 here can only come from ownership.
    """
    s = _mk_sample("SLICE2-RPT-OWNER", owner_id=principals[OUTSIDER])
    _act_as(OUTSIDER, monkeypatch)
    resp = await client.get(f"/api/v1/samples/{s['id']}/deletion-report")
    assert resp.status_code == 200, resp.text
    _cleanup("SLICE2-RPT-OWNER")


@pytest.mark.asyncio
async def test_owner_outside_the_lab_can_request_deletion(client, principals, monkeypatch):
    """The ownership rung has to reach deletion:request, not just the reads.

    M3 replaced the route's in-line "owner, or lab member" ladder with
    require_capability("deletion:request") and recorded that ownership survived
    as LADDER_POLICIES' owner_id rung. It did not: _matches compares capability
    by equality and no rung named deletion:request, so an owner with no grant
    over the sample was refused deletion of their own row.
    """
    s = _mk_sample("SLICE2-REQ-OWNER", owner_id=principals[OUTSIDER])
    _act_as(OUTSIDER, monkeypatch)
    resp = await client.post(
        f"/api/v1/samples/{s['id']}/request-deletion",
        json={"reason": "owner exercising RTBF over their own row"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["deletion_status"] == "DELETION_REQUESTED"
    _cleanup("SLICE2-REQ-OWNER")


@pytest.mark.asyncio
async def test_non_owner_non_member_cannot_request_deletion(client, principals, monkeypatch):
    """The rung is ownership, not "anyone with no tie" — the paired negative."""
    s = _mk_sample("SLICE2-REQ-DENY")
    _act_as(OUTSIDER, monkeypatch)
    resp = await client.post(
        f"/api/v1/samples/{s['id']}/request-deletion", json={"reason": "not mine"}
    )
    assert resp.status_code == 403, resp.text
    _cleanup("SLICE2-REQ-DENY")


@pytest.mark.asyncio
async def test_non_member_non_owner_is_refused_the_report(client, principals, monkeypatch):
    s = _mk_sample("SLICE2-RPT-DENY")
    _act_as(OUTSIDER, monkeypatch)
    resp = await client.get(f"/api/v1/samples/{s['id']}/deletion-report")
    assert resp.status_code == 403, resp.text
    _cleanup("SLICE2-RPT-DENY")


# ── the content / consent half: an instance admin LOSES these ───────────────


@pytest.mark.asyncio
async def test_pure_instance_admin_cannot_download_raw_fastq(client, principals, monkeypatch):
    """Deliberate narrowing (§8.2). The legacy branch admitted a platform admin.

    An operational admin holds no ``sample:read_detail``; letting it reach the
    *pre-scrub* original would be a side door into un-scrubbed PII.
    """
    s = _mk_sample("SLICE2-RAW-ADMIN", raw_fastq_uri="gs://jackpot-sequences/raw/R1.fastq.gz")
    _act_as(PURE_ADMIN, monkeypatch)
    resp = await client.get(f"/api/v1/samples/{s['id']}/download?file_type=raw_fastq")
    assert resp.status_code == 403, resp.text
    _cleanup("SLICE2-RAW-ADMIN")


@pytest.mark.asyncio
async def test_lab_lead_downloads_raw_fastq(client, principals, monkeypatch):
    """The positive half, which no test asserted before: sample:read_unscrubbed
    is granted, so the verb did not simply close the route to everyone."""
    s = _mk_sample("SLICE2-RAW-LEAD", raw_fastq_uri="gs://jackpot-sequences/raw/R1.fastq.gz")
    _act_as(LAB_LEAD, monkeypatch)
    resp = await client.get(f"/api/v1/samples/{s['id']}/download?file_type=raw_fastq")
    assert resp.status_code == 200, resp.text
    _cleanup("SLICE2-RAW-LEAD")


@pytest.mark.asyncio
async def test_lab_reader_cannot_download_raw_fastq(client, principals, monkeypatch):
    """sample:read_unscrubbed sits inside sample:read_detail, not beside it: a
    reader passes the outer check and is stopped by the inner one."""
    s = _mk_sample("SLICE2-RAW-RO", raw_fastq_uri="gs://jackpot-sequences/raw/R1.fastq.gz")
    _act_as(LAB_READER, monkeypatch)
    assert (await client.get(f"/api/v1/samples/{s['id']}")).status_code == 200
    resp = await client.get(f"/api/v1/samples/{s['id']}/download?file_type=raw_fastq")
    assert resp.status_code == 403, resp.text
    _cleanup("SLICE2-RAW-RO")


@pytest.mark.asyncio
async def test_pure_instance_admin_cannot_request_a_retraction(client, principals, monkeypatch):
    """Asking a repository to withdraw a published record is a consent act —
    the same call M3 made for deletion:approve (§8.2's note)."""
    s = _mk_sample("SLICE2-RTR-ADMIN")
    _act_as(PURE_ADMIN, monkeypatch)
    resp = await client.post(
        f"/api/v1/samples/{s['id']}/retraction-requests", json={"repository": "NCBI"}
    )
    assert resp.status_code == 403, resp.text
    _cleanup("SLICE2-RTR-ADMIN")


@pytest.mark.asyncio
async def test_lab_lead_requests_a_retraction(client, principals, monkeypatch):
    s = _mk_sample("SLICE2-RTR-LEAD")
    _act_as(LAB_LEAD, monkeypatch)
    resp = await client.post(
        f"/api/v1/samples/{s['id']}/retraction-requests",
        json={"repository": "NCBI", "accession": "SRR000002"},
    )
    assert resp.status_code == 201, resp.text
    _cleanup("SLICE2-RTR-LEAD")


@pytest.mark.asyncio
async def test_lab_lead_cannot_vacuum(client, principals, monkeypatch):
    """The mirror of the admin cases: deletion:vacuum is instance-only, so a
    Lab Lead's broad lab authority does not reach it."""
    s = _mk_sample("SLICE2-VAC-LEAD")
    _tombstone(s["id"])
    _act_as(LAB_LEAD, monkeypatch)
    resp = await client.post(
        f"/api/v1/samples/{s['id']}/vacuum-now", json={"justification": "should not pass"}
    )
    assert resp.status_code == 403, resp.text
    _cleanup("SLICE2-VAC-LEAD")
