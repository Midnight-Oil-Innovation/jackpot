"""Regression tests for the FIX-1 invariant in ``todo.md`` lines 218 / 222.

When the caller's transaction rolls back, the rows ``log_audit()`` and
``create_notification()`` wrote inside that transaction must roll back
with it — both helpers share the caller's ``db_conn`` (forwarded as
``conn=db_conn`` into ``execute_write``), so a parent-operation
rollback is the only thing standing between an audit row that
references work that never happened.

These tests use a deliberately-orphaned action / event_type
(``ROLLBACK_REGRESSION_*``) so the assertions can search by the
constant without false positives from real audit / notification
writes that happen during the rest of the suite.

Companion positive test confirms the rollback test isn't a false
negative — the same helper call followed by a ``commit`` puts the row
in the table where the rollback assertion expects to find nothing.
"""

from __future__ import annotations

from backend.audit import log_audit
from backend.database import _get_engine, execute_query, execute_write
from backend.notifications import create_notification

_TEST_AUDIT_ACTION = "ROLLBACK_REGRESSION_AUDIT"
_TEST_NOTIFICATION_EVENT = "ROLLBACK_REGRESSION_NOTIFICATION"


def _cleanup_test_audit_rows(action: str) -> None:
    execute_write("DELETE FROM audit_log WHERE action = :a", {"a": action})


def _cleanup_test_notifications(event_type: str) -> None:
    execute_write(
        "DELETE FROM notifications WHERE event_type = :e",
        {"e": event_type},
    )


# ─────────────────── log_audit rollback contract ───────────────────


def test_log_audit_row_rolls_back_with_parent_transaction():
    """FIX-1 regression. ``log_audit(db_conn=db)`` shares the caller's
    transaction; rolling that transaction back must also drop the
    audit row."""
    _cleanup_test_audit_rows(_TEST_AUDIT_ACTION)
    _, session_local = _get_engine()
    db = session_local()
    try:
        log_audit(
            action=_TEST_AUDIT_ACTION,
            actor_id=1,
            resource_type="test",
            resource_id="rollback-audit-001",
            before=None,
            after=None,
            metadata={"reason": "transaction-rollback regression"},
            db_conn=db,
        )
        # Caller's parent operation fails: rollback the transaction.
        db.rollback()
    finally:
        db.close()

    rows = execute_query(
        "SELECT id FROM audit_log WHERE action = :a AND resource_id = :r",
        {"a": _TEST_AUDIT_ACTION, "r": "rollback-audit-001"},
    )
    assert rows == [], (
        "log_audit row survived the parent rollback — db_conn forwarding "
        "is broken and the FIX-1 over-claim has regressed."
    )


def test_log_audit_row_commits_with_parent_transaction():
    """Positive companion. Same helper call followed by ``commit``
    must leave the row in audit_log — proves the rollback test isn't
    a false negative."""
    _cleanup_test_audit_rows(_TEST_AUDIT_ACTION)
    _, session_local = _get_engine()
    db = session_local()
    try:
        log_audit(
            action=_TEST_AUDIT_ACTION,
            actor_id=1,
            resource_type="test",
            resource_id="commit-audit-001",
            before=None,
            after=None,
            metadata={"reason": "transaction-commit positive"},
            db_conn=db,
        )
        db.commit()
    finally:
        db.close()

    try:
        rows = execute_query(
            "SELECT id, action FROM audit_log WHERE action = :a AND resource_id = :r",
            {"a": _TEST_AUDIT_ACTION, "r": "commit-audit-001"},
        )
        assert len(rows) == 1
    finally:
        _cleanup_test_audit_rows(_TEST_AUDIT_ACTION)


# ─────────────────── create_notification rollback contract ───────────────────


def test_create_notification_rolls_back_with_parent_transaction():
    """FIX-1 regression for the second helper. ``create_notification``
    forwards ``conn=db_conn`` into the INSERT; a parent rollback must
    take the notification row with it."""
    _cleanup_test_notifications(_TEST_NOTIFICATION_EVENT)
    _, session_local = _get_engine()
    db = session_local()
    try:
        create_notification(
            recipient_id=1,
            event_type=_TEST_NOTIFICATION_EVENT,
            title="rollback regression",
            body="body",
            resource_type="test",
            resource_id="rollback-notif-001",
            action_url=None,
            db_conn=db,
        )
        db.rollback()
    finally:
        db.close()

    rows = execute_query(
        "SELECT id FROM notifications WHERE event_type = :e AND resource_id = :r",
        {"e": _TEST_NOTIFICATION_EVENT, "r": "rollback-notif-001"},
    )
    assert rows == [], (
        "create_notification row survived the parent rollback — db_conn forwarding is broken."
    )


def test_create_notification_row_commits_with_parent_transaction():
    """Positive companion for create_notification."""
    _cleanup_test_notifications(_TEST_NOTIFICATION_EVENT)
    _, session_local = _get_engine()
    db = session_local()
    try:
        create_notification(
            recipient_id=1,
            event_type=_TEST_NOTIFICATION_EVENT,
            title="commit positive",
            body="body",
            resource_type="test",
            resource_id="commit-notif-001",
            action_url=None,
            db_conn=db,
        )
        db.commit()
    finally:
        db.close()

    try:
        rows = execute_query(
            "SELECT id FROM notifications WHERE event_type = :e AND resource_id = :r",
            {"e": _TEST_NOTIFICATION_EVENT, "r": "commit-notif-001"},
        )
        assert len(rows) == 1
    finally:
        _cleanup_test_notifications(_TEST_NOTIFICATION_EVENT)
