"""I-2 release_embargoed_submissions daily-job tests."""

from __future__ import annotations

import pytest

from backend.database import execute_query, execute_write
from backend.jobs import release_embargoed_submissions

SEED_USER_ID = 1
SEED_LAB_ID = 1


def _cleanup() -> None:
    rows = execute_query("SELECT id FROM submissions WHERE title LIKE 'I2-RELEASE-%'")
    for r in rows:
        execute_write("DELETE FROM submission_samples WHERE submission_id = :id", {"id": r["id"]})
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'submission' AND resource_id = :rid",
            {"rid": str(r["id"])},
        )
        execute_write("DELETE FROM submissions WHERE id = :id", {"id": r["id"]})


def _insert_submission(*, status: str, release_offset_days: int, title: str) -> int:
    rows = execute_write(
        """
        INSERT INTO submissions (
            created_by_user_id, lab_id, target_repository, title, status,
            release_date
        ) VALUES (
            :uid, :lab, 'NCBI', :title, :status,
            CURRENT_DATE + (CAST(:offset AS integer) * INTERVAL '1 day')
        )
        RETURNING id
        """,
        {
            "uid": SEED_USER_ID,
            "lab": SEED_LAB_ID,
            "title": title,
            "status": status,
            "offset": release_offset_days,
        },
    )
    return rows[0]["id"]


@pytest.mark.asyncio
async def test_release_embargoed_with_past_release_date_promotes_to_released():
    _cleanup()
    target = _insert_submission(status="EMBARGOED", release_offset_days=-1, title="I2-RELEASE-PAST")
    fresh = _insert_submission(
        status="EMBARGOED", release_offset_days=30, title="I2-RELEASE-FUTURE"
    )
    out = await release_embargoed_submissions()
    assert out["released"] >= 1
    rows = execute_query(
        "SELECT id, status FROM submissions WHERE id IN (:a, :b) ORDER BY id",
        {"a": target, "b": fresh},
    )
    by_id = {r["id"]: r["status"] for r in rows}
    assert by_id[target] == "RELEASED"
    assert by_id[fresh] == "EMBARGOED"
    _cleanup()


@pytest.mark.asyncio
async def test_release_embargoed_skips_non_embargoed():
    _cleanup()
    accepted = _insert_submission(status="ACCEPTED", release_offset_days=-1, title="I2-RELEASE-ACC")
    await release_embargoed_submissions()
    rows = execute_query("SELECT status FROM submissions WHERE id = :id", {"id": accepted})
    assert rows[0]["status"] == "ACCEPTED"
    _cleanup()


@pytest.mark.asyncio
async def test_release_embargoed_writes_audit_log():
    _cleanup()
    target = _insert_submission(status="EMBARGOED", release_offset_days=-1, title="I2-RELEASE-AUD")
    await release_embargoed_submissions()
    rows = execute_query(
        "SELECT action FROM audit_log "
        "WHERE resource_type = 'submission' AND resource_id = :rid "
        "ORDER BY id DESC LIMIT 1",
        {"rid": str(target)},
    )
    assert rows
    assert rows[0]["action"] == "SUBMISSION_RELEASED"
    _cleanup()


@pytest.mark.asyncio
async def test_release_embargoed_idempotent():
    _cleanup()
    target = _insert_submission(status="EMBARGOED", release_offset_days=-1, title="I2-RELEASE-IDEM")
    out_a = await release_embargoed_submissions()
    out_b = await release_embargoed_submissions()
    rows = execute_query("SELECT status FROM submissions WHERE id = :id", {"id": target})
    assert rows[0]["status"] == "RELEASED"
    assert out_a["released"] >= 1
    assert out_b["released"] == 0
    _cleanup()
