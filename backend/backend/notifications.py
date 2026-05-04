import logging

from backend.database import execute_write

logger = logging.getLogger(__name__)


class NotificationEvents:
    # Scrub override
    SCRUB_SKIP_REQUESTED = "SCRUB_SKIP_REQUESTED"
    SCRUB_SKIP_APPROVED = "SCRUB_SKIP_APPROVED"
    SCRUB_SKIP_DENIED = "SCRUB_SKIP_DENIED"
    SCRUB_SKIP_AUTO_DENIED = "SCRUB_SKIP_AUTO_DENIED"

    # Access requests
    ACCESS_REQUEST_SUBMITTED = "ACCESS_REQUEST_SUBMITTED"
    ACCESS_REQUEST_APPROVED = "ACCESS_REQUEST_APPROVED"
    ACCESS_REQUEST_DENIED = "ACCESS_REQUEST_DENIED"
    ACCESS_AUTO_APPROVED = "ACCESS_AUTO_APPROVED"
    ACCESS_APPROVE_WARNING = "ACCESS_APPROVE_WARNING"
    ACCESS_EXPIRING = "ACCESS_EXPIRING"

    # Pipelines
    PIPELINE_COMPLETE = "PIPELINE_COMPLETE"
    PIPELINE_FAILED = "PIPELINE_FAILED"

    # Ingest
    GLOBUS_FILES_ARRIVED = "GLOBUS_FILES_ARRIVED"
    METADATA_COMPLETION_NEEDED = "METADATA_COMPLETION_NEEDED"
    ERRONEOUS_UPLOAD_EXPIRING = "ERRONEOUS_UPLOAD_EXPIRING"

    # Surveillance
    SURVEILLANCE_OVERRIDE_REQUESTED = "SURVEILLANCE_OVERRIDE_REQUESTED"
    SURVEILLANCE_OVERRIDE_DECIDED = "SURVEILLANCE_OVERRIDE_DECIDED"

    # File references (Phase P0f)
    FILE_REFERENCE_BROKEN = "FILE_REFERENCE_BROKEN"
    # Default-disabled (high volume); operators can enable for diagnostics.
    FILE_DEDUPLICATED = "FILE_DEDUPLICATED"
    # Phase P0f F-9
    FILE_PROMOTED = "FILE_PROMOTED"
    FILE_PROMOTION_FAILED = "FILE_PROMOTION_FAILED"

    # Submission lifecycle (I-2)
    SUBMISSION_PACKAGE_READY = "SUBMISSION_PACKAGE_READY"
    SUBMISSION_ACCEPTED = "SUBMISSION_ACCEPTED"
    SUBMISSION_PARTIAL_SUCCESS = "SUBMISSION_PARTIAL_SUCCESS"
    SUBMISSION_REJECTED = "SUBMISSION_REJECTED"
    SUBMISSION_RELEASED = "SUBMISSION_RELEASED"
    SUBMISSION_WITHDRAWN = "SUBMISSION_WITHDRAWN"


def create_notification(
    recipient_id: int,
    event_type: str,
    title: str,
    body: str,
    resource_type: str,
    resource_id: str,
    action_url: str | None,
    db_conn,
) -> None:
    """
    Write a notification record synchronously within the caller's transaction.
    Failures are logged and swallowed — a notification failure must never
    roll back the triggering action.
    """
    try:
        execute_write(
            """
            INSERT INTO notifications
                (recipient_id, event_type, title, body,
                 resource_type, resource_id, action_url)
            VALUES
                (:recipient_id, :event_type, :title, :body,
                 :resource_type, :resource_id, :action_url)
            """,
            {
                "recipient_id": recipient_id,
                "event_type": event_type,
                "title": title,
                "body": body,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action_url": action_url,
            },
            conn=db_conn,
        )
    except Exception as exc:
        logger.error(
            "Notification write failed",
            exc_info=exc,
            extra={"event_type": event_type, "recipient_id": recipient_id},
        )
