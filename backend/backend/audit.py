import json
import logging

from backend.database import execute_write

logger = logging.getLogger(__name__)


class AuditActions:
    # Samples
    CREATE_SAMPLE = "CREATE_SAMPLE"
    UPDATE_SAMPLE = "UPDATE_SAMPLE"
    DELETE_SAMPLE = "DELETE_SAMPLE"
    ARCHIVE_SAMPLE = "ARCHIVE_SAMPLE"
    SOFT_DELETE_SAMPLE = "SOFT_DELETE_SAMPLE"
    HARD_DELETE_SAMPLE = "HARD_DELETE_SAMPLE"

    # Scrub override
    REQUEST_SCRUB_SKIP = "REQUEST_SCRUB_SKIP"
    APPROVE_SCRUB_SKIP = "APPROVE_SCRUB_SKIP"
    DENY_SCRUB_SKIP = "DENY_SCRUB_SKIP"
    AUTO_DENY_SCRUB_SKIP = "AUTO_DENY_SCRUB_SKIP"
    SYSTEM_SKIP_SCRUB = "SYSTEM_SKIP_SCRUB"

    # Surveillance override
    REQUEST_SURVEILLANCE_OVERRIDE = "REQUEST_SURVEILLANCE_OVERRIDE"
    APPROVE_SURVEILLANCE_OVERRIDE = "APPROVE_SURVEILLANCE_OVERRIDE"
    DENY_SURVEILLANCE_OVERRIDE = "DENY_SURVEILLANCE_OVERRIDE"

    # Access requests
    CREATE_ACCESS_REQUEST = "CREATE_ACCESS_REQUEST"
    APPROVE_ACCESS_REQUEST = "APPROVE_ACCESS_REQUEST"
    DENY_ACCESS_REQUEST = "DENY_ACCESS_REQUEST"
    AUTO_APPROVE_ACCESS_REQUEST = "AUTO_APPROVE_ACCESS_REQUEST"
    REVOKE_ACCESS = "REVOKE_ACCESS"

    # Deletion
    REQUEST_DELETION = "REQUEST_DELETION"
    APPROVE_DELETION = "APPROVE_DELETION"
    DENY_DELETION = "DENY_DELETION"
    COMPLETE_DELETION = "COMPLETE_DELETION"

    # Org / Lab / User
    CREATE_ORG = "CREATE_ORG"
    UPDATE_ORG = "UPDATE_ORG"
    CREATE_LAB = "CREATE_LAB"
    UPDATE_LAB = "UPDATE_LAB"
    ADD_LAB_MEMBER = "ADD_LAB_MEMBER"
    REMOVE_LAB_MEMBER = "REMOVE_LAB_MEMBER"
    CHANGE_MEMBER_ROLE = "CHANGE_MEMBER_ROLE"


def log_audit(
    action: str,
    actor_id: int | None,
    resource_type: str,
    resource_id: str,
    before: dict | None,
    after: dict | None,
    metadata: dict | None,
    db_conn,
) -> None:
    """Write immutable audit record. Failures are logged, never raised."""
    try:
        execute_write(
            """
            INSERT INTO audit_log
                (action, actor_id, resource_type, resource_id,
                 before_state, after_state, metadata)
            VALUES
                (:action, :actor_id, :resource_type, :resource_id,
                 CAST(:before AS JSONB), CAST(:after AS JSONB), CAST(:metadata AS JSONB))
            """,
            {
                "action": action,
                "actor_id": actor_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "before": json.dumps(before) if before else None,
                "after": json.dumps(after) if after else None,
                "metadata": json.dumps(metadata) if metadata else None,
            },
            conn=db_conn,
        )
    except Exception as exc:
        logger.error(
            "Audit log write failed",
            exc_info=exc,
            extra={"action": action, "resource_type": resource_type, "resource_id": resource_id},
        )
