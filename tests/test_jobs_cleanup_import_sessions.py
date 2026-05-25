"""I-1 tests for the cleanup_expired_import_sessions APScheduler job."""

from __future__ import annotations

import pytest

from backend.database import execute_query, execute_write
from backend.jobs import cleanup_expired_import_sessions

SEED_USER_ID = 1
SEED_LAB_ID = 1


def _insert(*, status: str, expires_offset: str, created_offset: str = "0") -> int:
    rows = execute_write(
        """
        INSERT INTO import_sessions (
            created_by_user_id, lab_id, file_name, file_format,
            file_bytes, file_size_bytes, current_step, status,
            expires_at, created_at
        ) VALUES (
            :uid, :lab, :fn, 'csv',
            :bytes, :sz, 1, :status,
            NOW() + CAST(:exp AS interval), NOW() - CAST(:cre AS interval)
        )
        RETURNING id
        """,
        {
            "uid": SEED_USER_ID,
            "lab": SEED_LAB_ID,
            "fn": "t.csv",
            "bytes": b"a,b\n1,2\n",
            "sz": 8,
            "status": status,
            "exp": expires_offset,
            "cre": created_offset,
        },
    )
    return rows[0]["id"]


def _cleanup_all() -> None:
    execute_write(
        "DELETE FROM import_sessions WHERE created_by_user_id = :uid",
        {"uid": SEED_USER_ID},
    )


@pytest.mark.asyncio
async def test_cleanup_deletes_expired_in_progress():
    _cleanup_all()
    expired_id = _insert(status="in_progress", expires_offset="-1 hour")
    fresh_id = _insert(status="in_progress", expires_offset="23 hours")
    out = await cleanup_expired_import_sessions()
    assert out["deleted_expired"] >= 1
    rows = execute_query(
        "SELECT id FROM import_sessions WHERE id IN (:a, :b)",
        {"a": expired_id, "b": fresh_id},
    )
    surviving = {r["id"] for r in rows}
    assert fresh_id in surviving
    assert expired_id not in surviving
    _cleanup_all()


@pytest.mark.asyncio
async def test_cleanup_deletes_old_imported_sessions():
    _cleanup_all()
    old_id = _insert(status="imported", expires_offset="-1 day", created_offset="8 days")
    recent_id = _insert(status="imported", expires_offset="-1 day", created_offset="1 day")
    out = await cleanup_expired_import_sessions()
    assert out["deleted_old_terminal"] >= 1
    rows = execute_query(
        "SELECT id FROM import_sessions WHERE id IN (:a, :b)",
        {"a": old_id, "b": recent_id},
    )
    surviving = {r["id"] for r in rows}
    assert recent_id in surviving
    assert old_id not in surviving
    _cleanup_all()


@pytest.mark.asyncio
async def test_cleanup_deletes_old_abandoned_sessions():
    _cleanup_all()
    old_id = _insert(status="abandoned", expires_offset="-1 day", created_offset="8 days")
    out = await cleanup_expired_import_sessions()
    assert out["deleted_old_terminal"] >= 1
    rows = execute_query(
        "SELECT id FROM import_sessions WHERE id = :a",
        {"a": old_id},
    )
    assert rows == []
    _cleanup_all()


@pytest.mark.asyncio
async def test_cleanup_preserves_recent_in_progress():
    _cleanup_all()
    fresh_id = _insert(status="in_progress", expires_offset="22 hours")
    await cleanup_expired_import_sessions()
    rows = execute_query("SELECT id FROM import_sessions WHERE id = :a", {"a": fresh_id})
    assert rows
    _cleanup_all()


@pytest.mark.asyncio
async def test_cleanup_preserves_recent_terminal():
    _cleanup_all()
    recent_id = _insert(status="imported", expires_offset="-1 day", created_offset="2 days")
    await cleanup_expired_import_sessions()
    rows = execute_query("SELECT id FROM import_sessions WHERE id = :a", {"a": recent_id})
    assert rows
    _cleanup_all()


@pytest.mark.asyncio
async def test_cleanup_writes_audit_log():
    _cleanup_all()
    _insert(status="in_progress", expires_offset="-1 hour")
    out = await cleanup_expired_import_sessions()
    rows = execute_query(
        "SELECT * FROM audit_log WHERE action = 'CLEANUP_IMPORT_SESSIONS' ORDER BY id DESC LIMIT 1"
    )
    assert rows
    assert out["deleted_expired"] >= 1
    _cleanup_all()
