import json
import logging

from database import execute_write

logger = logging.getLogger(__name__)

CREATE_SAMPLE = "CREATE_SAMPLE"
UPDATE_SAMPLE = "UPDATE_SAMPLE"
DELETE_SAMPLE = "DELETE_SAMPLE"
APPROVE_ACCESS = "APPROVE_ACCESS"
DENY_ACCESS = "DENY_ACCESS"
DOWNLOAD_FILE = "DOWNLOAD_FILE"
LAUNCH_PIPELINE = "LAUNCH_PIPELINE"
SUBMIT_NCBI = "SUBMIT_NCBI"
SUBMIT_GISAID = "SUBMIT_GISAID"
CHANGE_ROLE = "CHANGE_ROLE"
CREATE_LAB = "CREATE_LAB"
ARCHIVE_REQUEST = "ARCHIVE_REQUEST"


def log_audit(
    user_id: int,
    action: str,
    resource: str,
    resource_id: str,
    detail: dict | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
) -> None:
    """Write immutable audit record. Failures are logged, never raised."""
    try:
        execute_write(
            """
            INSERT INTO audit_log
                (user_id, action, resource, resource_id, detail, request_id, ip_address)
            VALUES
                (:uid, :action, :resource, :rid, :detail::jsonb, :req_id, :ip)
            """,
            {
                "uid": user_id,
                "action": action,
                "resource": resource,
                "rid": resource_id,
                "detail": json.dumps(detail) if detail else None,
                "req_id": request_id,
                "ip": ip_address,
            },
        )
    except Exception as exc:
        logger.error(
            "Audit log write failed",
            exc_info=exc,
            extra={"action": action, "resource": resource, "resource_id": resource_id},
        )
