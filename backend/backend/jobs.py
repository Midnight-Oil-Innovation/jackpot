"""APScheduler job functions.

Each job is idempotent — running twice produces the same result as
running once. The bodies here are also reachable via the manual
trigger endpoint so local dev and Cloud Scheduler hit identical code.
"""

from __future__ import annotations

import json
import logging

from backend.audit import AuditActions, log_audit
from backend.database import execute_query, execute_write, get_db
from backend.notifications import NotificationEvents, create_notification

logger = logging.getLogger(__name__)


async def run_scrubber_queue_job() -> None:
    """
    Auto-deny scrub override requests pending for > 48 hours.
    Conservative default: if Lab Director doesn't decide, scrubber runs.
    Implement fully when scrub override workflow is built (Month 2).
    """
    logger.info("run_scrubber_queue_job: not yet implemented")


async def run_access_request_job() -> None:
    """Sweep the access-request lifecycle.

    Five buckets are processed in one transaction so the run is atomic
    end-to-end — partial sweeps would either re-fire warnings or skip
    expirations on retry. Each bucket short-circuits cleanly when there
    are no rows to act on.

      1. AUTO_APPROVE — PENDING requests whose ``auto_approve_after``
         has elapsed. Status flips to AUTO_APPROVED, a grant is created,
         and the requester is notified.
      2. APPROVE WARNING (75-day) — PENDING requests within 15 days of
         their auto-approve deadline. Notifies the Lab Director that an
         answer is overdue. ``last_warning_sent_at`` is stamped so
         reruns do not double-fire.
      3. EXPIRY WARNING (7-day) — APPROVED requests whose grants expire
         within 7 days. One-shot warning to the requester.
      4. EXPIRE GRANTS — grants whose ``access_expires_at`` is in the
         past flip to revoked, and the linked request transitions to
         EXPIRED.
      5. MOOT — PENDING requests on samples that have since become
         PUBLIC. The request is no longer needed; mark MOOT and notify.
    """
    logger.info("run_access_request_job: starting sweep")
    counters = {
        "auto_approved": 0,
        "approve_warnings": 0,
        "expiry_warnings": 0,
        "expired_grants": 0,
        "mooted": 0,
    }
    with get_db() as db:
        counters["auto_approved"] = _auto_approve_due_requests(db)
        counters["approve_warnings"] = _send_approve_warnings(db)
        counters["expiry_warnings"] = _send_expiry_warnings(db)
        counters["expired_grants"] = _expire_grants(db)
        counters["mooted"] = _moot_public_sample_requests(db)
    logger.info("run_access_request_job: %s", json.dumps(counters))


# ── private helpers ─────────────────────────────────────────────────────────


def _auto_approve_due_requests(db) -> int:
    """Auto-approve PENDING requests past auto_approve_after."""
    due = execute_query(
        """
        SELECT sar.*, s.lab_id AS sample_lab_id, s.sample_id AS sample_external_id
        FROM sample_access_requests sar
        JOIN samples s ON s.id = sar.sample_id
        WHERE sar.status = 'PENDING'
          AND sar.auto_approve_after IS NOT NULL
          AND sar.auto_approve_after <= NOW()
        """,
        conn=db,
    )
    if not due:
        return 0
    for req in due:
        duration = req.get("requested_duration_days") or 90
        execute_write(
            """
            UPDATE sample_access_requests
            SET status = 'AUTO_APPROVED',
                approved_at = NOW(),
                reviewed_at = NOW(),
                access_expires_at = NOW() + (:days || ' days')::INTERVAL
            WHERE id = :id
            """,
            {"days": str(duration), "id": req["id"]},
            conn=db,
        )
        execute_write(
            """
            INSERT INTO sample_access_grants
                (sample_id, requester_id, request_id, granted_by_id, access_expires_at)
            VALUES
                (:sid, :rid, :req_id, NULL, NOW() + (:days || ' days')::INTERVAL)
            """,
            {
                "sid": req["sample_id"],
                "rid": req["requester_id"],
                "req_id": req["id"],
                "days": str(duration),
            },
            conn=db,
        )
        create_notification(
            recipient_id=req["requester_id"],
            event_type=NotificationEvents.ACCESS_AUTO_APPROVED,
            title=f"Access auto-approved: {req['sample_external_id']}",
            body=(
                "Your access request was auto-approved after the 7-day Lab Director "
                f"response window elapsed. Access expires in {duration} days."
            ),
            resource_type="sample_access_request",
            resource_id=str(req["id"]),
            action_url=f"/samples/{req['sample_id']}",
            db_conn=db,
        )
        log_audit(
            action=AuditActions.AUTO_APPROVE_ACCESS_REQUEST,
            actor_id=None,
            resource_type="sample_access_request",
            resource_id=str(req["id"]),
            before=None,
            after=None,
            metadata={"sample_id": req["sample_id"], "duration_days": duration},
            db_conn=db,
        )
    return len(due)


def _send_approve_warnings(db) -> int:
    """75-day-style warning when an unanswered request is 15d from auto-approve."""
    rows = execute_query(
        """
        SELECT sar.id, sar.requester_id, sar.sample_id, s.sample_id AS sample_external_id,
               s.lab_id AS sample_lab_id
        FROM sample_access_requests sar
        JOIN samples s ON s.id = sar.sample_id
        WHERE sar.status = 'PENDING'
          AND sar.auto_approve_after IS NOT NULL
          AND sar.auto_approve_after - INTERVAL '15 days' <= NOW()
          AND sar.auto_approve_after > NOW()
          AND sar.last_warning_sent_at IS NULL
        """,
        conn=db,
    )
    for row in rows:
        directors = execute_query(
            "SELECT user_id FROM lab_membership WHERE lab_id = :lid AND is_lab_director = TRUE",
            {"lid": row["sample_lab_id"]},
            conn=db,
        )
        for d in directors:
            create_notification(
                recipient_id=d["user_id"],
                event_type=NotificationEvents.ACCESS_APPROVE_WARNING,
                title=f"Access request awaiting decision: {row['sample_external_id']}",
                body=(
                    "An access request has been pending and will auto-approve in "
                    "less than 15 days unless you decide it now."
                ),
                resource_type="sample_access_request",
                resource_id=str(row["id"]),
                action_url=f"/sample-access/requests/{row['id']}",
                db_conn=db,
            )
        execute_write(
            "UPDATE sample_access_requests SET last_warning_sent_at = NOW() WHERE id = :id",
            {"id": row["id"]},
            conn=db,
        )
    return len(rows)


def _send_expiry_warnings(db) -> int:
    """7-day expiry warning to the requester."""
    rows = execute_query(
        """
        SELECT sar.id, sar.requester_id, sar.sample_id, sar.access_expires_at,
               s.sample_id AS sample_external_id
        FROM sample_access_requests sar
        JOIN samples s ON s.id = sar.sample_id
        WHERE sar.status IN ('APPROVED', 'AUTO_APPROVED')
          AND sar.access_expires_at IS NOT NULL
          AND sar.access_expires_at - INTERVAL '7 days' <= NOW()
          AND sar.access_expires_at > NOW()
          AND (sar.last_warning_sent_at IS NULL
               OR sar.last_warning_sent_at < sar.access_expires_at - INTERVAL '7 days')
        """,
        conn=db,
    )
    for row in rows:
        create_notification(
            recipient_id=row["requester_id"],
            event_type=NotificationEvents.ACCESS_EXPIRING,
            title=f"Access expiring soon: {row['sample_external_id']}",
            body=(
                "Your access to this sample expires within 7 days. Submit a new "
                "request if you still need access."
            ),
            resource_type="sample_access_request",
            resource_id=str(row["id"]),
            action_url=f"/sample-access/requests/{row['id']}",
            db_conn=db,
        )
        execute_write(
            "UPDATE sample_access_requests SET last_warning_sent_at = NOW() WHERE id = :id",
            {"id": row["id"]},
            conn=db,
        )
    return len(rows)


def _expire_grants(db) -> int:
    """Revoke grants past their access_expires_at and mark linked requests EXPIRED."""
    expired = execute_query(
        """
        SELECT id, request_id, sample_id, requester_id
        FROM sample_access_grants
        WHERE revoked = FALSE
          AND access_expires_at IS NOT NULL
          AND access_expires_at <= NOW()
        """,
        conn=db,
    )
    if not expired:
        return 0
    for grant in expired:
        execute_write(
            "UPDATE sample_access_grants SET revoked = TRUE, revoked_at = NOW() WHERE id = :id",
            {"id": grant["id"]},
            conn=db,
        )
        if grant["request_id"]:
            execute_write(
                "UPDATE sample_access_requests SET status = 'EXPIRED' "
                "WHERE id = :id AND status IN ('APPROVED', 'AUTO_APPROVED')",
                {"id": grant["request_id"]},
                conn=db,
            )
        log_audit(
            action=AuditActions.EXPIRE_ACCESS_GRANT,
            actor_id=None,
            resource_type="sample_access_grant",
            resource_id=str(grant["id"]),
            before=None,
            after=None,
            metadata={
                "sample_id": grant["sample_id"],
                "requester_id": grant["requester_id"],
                "request_id": grant["request_id"],
            },
            db_conn=db,
        )
    return len(expired)


def _moot_public_sample_requests(db) -> int:
    """PENDING requests on samples that became PUBLIC are no longer needed."""
    rows = execute_query(
        """
        SELECT sar.id, sar.requester_id, sar.sample_id, s.sample_id AS sample_external_id
        FROM sample_access_requests sar
        JOIN samples s ON s.id = sar.sample_id
        WHERE sar.status = 'PENDING' AND s.sharing_level = 'PUBLIC'
        """,
        conn=db,
    )
    if not rows:
        return 0
    for row in rows:
        execute_write(
            "UPDATE sample_access_requests SET status = 'MOOT', reviewed_at = NOW() WHERE id = :id",
            {"id": row["id"]},
            conn=db,
        )
        create_notification(
            recipient_id=row["requester_id"],
            event_type=NotificationEvents.ACCESS_REQUEST_APPROVED,
            title=f"Sample {row['sample_external_id']} is now PUBLIC",
            body=(
                "Your access request is no longer needed — the sample's sharing "
                "level was changed to PUBLIC."
            ),
            resource_type="sample_access_request",
            resource_id=str(row["id"]),
            action_url=f"/samples/{row['sample_id']}",
            db_conn=db,
        )
        log_audit(
            action=AuditActions.MOOT_ACCESS_REQUEST,
            actor_id=None,
            resource_type="sample_access_request",
            resource_id=str(row["id"]),
            before=None,
            after=None,
            metadata={"sample_id": row["sample_id"]},
            db_conn=db,
        )
    return len(rows)
