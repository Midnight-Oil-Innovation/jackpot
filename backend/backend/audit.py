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
    EXPIRE_ACCESS_GRANT = "EXPIRE_ACCESS_GRANT"
    MOOT_ACCESS_REQUEST = "MOOT_ACCESS_REQUEST"

    # Deletion
    REQUEST_DELETION = "REQUEST_DELETION"
    APPROVE_DELETION = "APPROVE_DELETION"
    DENY_DELETION = "DENY_DELETION"
    COMPLETE_DELETION = "COMPLETE_DELETION"

    # Org / Lab / Project / User
    CREATE_ORG = "CREATE_ORG"
    UPDATE_ORG = "UPDATE_ORG"
    CREATE_LAB = "CREATE_LAB"
    UPDATE_LAB = "UPDATE_LAB"
    CREATE_PROJECT = "CREATE_PROJECT"
    UPDATE_PROJECT = "UPDATE_PROJECT"
    ADD_LAB_MEMBER = "ADD_LAB_MEMBER"
    REMOVE_LAB_MEMBER = "REMOVE_LAB_MEMBER"
    CHANGE_MEMBER_ROLE = "CHANGE_MEMBER_ROLE"
    UPDATE_USER = "UPDATE_USER"

    # Domain whitelist
    ADD_WHITELIST_DOMAIN = "ADD_WHITELIST_DOMAIN"
    REMOVE_WHITELIST_DOMAIN = "REMOVE_WHITELIST_DOMAIN"

    # Sequencing labs
    CREATE_SEQUENCING_LAB = "CREATE_SEQUENCING_LAB"
    UPDATE_SEQUENCING_LAB = "UPDATE_SEQUENCING_LAB"
    ASSIGN_SEQUENCING_LAB = "ASSIGN_SEQUENCING_LAB"
    UNASSIGN_SEQUENCING_LAB = "UNASSIGN_SEQUENCING_LAB"

    # Personal API tokens
    CREATE_TOKEN = "CREATE_TOKEN"
    REVOKE_TOKEN = "REVOKE_TOKEN"

    # Pipelines
    REGISTER_PIPELINE_RESULT = "REGISTER_PIPELINE_RESULT"
    CREATE_PIPELINE_RUN = "CREATE_PIPELINE_RUN"
    RESUME_PIPELINE_RUN = "RESUME_PIPELINE_RUN"
    REGISTER_CUSTOM_PIPELINE = "REGISTER_CUSTOM_PIPELINE"
    PROMOTE_PIPELINE = "PROMOTE_PIPELINE"
    # P0g G-4: launch resolved an execution_profiles row and rendered
    # nextflow.config from that profile (vs. the legacy GCP-Batch path).
    LAUNCH_WITH_PROFILE = "LAUNCH_WITH_PROFILE"
    # P0h H-3: launch overrode the active Slurm profile's default
    # account with a per-launch ``launch_account`` so a lab member
    # could charge a specific grant. P0c multi-tenancy middleware is
    # the validator once it lands; today the override is accepted
    # verbatim with this audit row capturing actor + override value.
    SLURM_LAUNCH_ACCOUNT_OVERRIDE = "SLURM_LAUNCH_ACCOUNT_OVERRIDE"

    # File references (Phase P0f)
    RECONCILE_SAMPLE_FILES_HASH_COLLISION = "RECONCILE_SAMPLE_FILES_HASH_COLLISION"
    VERIFY_FILE_FAILED = "VERIFY_FILE_FAILED"
    MARK_FILE_BROKEN = "MARK_FILE_BROKEN"
    REGISTER_FILE = "REGISTER_FILE"
    DEDUP_FILE = "DEDUP_FILE"
    # Phase P0f F-9
    PROMOTE_FILE = "PROMOTE_FILE"
    PROMOTE_FILE_FAILED = "PROMOTE_FILE_FAILED"
    VERIFY_FILE_TRIGGERED = "VERIFY_FILE_TRIGGERED"

    # Submission lifecycle (I-2)
    SUBMISSION_CREATED = "SUBMISSION_CREATED"
    SUBMISSION_SAMPLES_ADDED = "SUBMISSION_SAMPLES_ADDED"
    SUBMISSION_SAMPLES_REMOVED = "SUBMISSION_SAMPLES_REMOVED"
    SUBMISSION_VALIDATED = "SUBMISSION_VALIDATED"
    SUBMISSION_GENERATED = "SUBMISSION_GENERATED"
    SUBMISSION_MARKED_SUBMITTED = "SUBMISSION_MARKED_SUBMITTED"
    SUBMISSION_REGISTERED_ACCESSIONS = "SUBMISSION_REGISTERED_ACCESSIONS"
    SUBMISSION_MARKED_REJECTED = "SUBMISSION_MARKED_REJECTED"
    SUBMISSION_RELEASED = "SUBMISSION_RELEASED"
    SUBMISSION_WITHDRAWN = "SUBMISSION_WITHDRAWN"

    # Auth (P1: refresh-token rotation)
    AUTH_TOKEN_REFRESHED = "AUTH_TOKEN_REFRESHED"
    AUTH_TOKEN_REPLAY_DETECTED = "AUTH_TOKEN_REPLAY_DETECTED"
    AUTH_LOGOUT = "AUTH_LOGOUT"
    # Reserved for future admin-revoke functionality (admin UI; not used in P1).
    AUTH_TOKEN_REVOKED_BY_ADMIN = "AUTH_TOKEN_REVOKED_BY_ADMIN"
    # E-1: dev-only role-switch endpoint (POST /api/v1/auth/dev-login).
    # Emitted only when settings.env == "local"; the endpoint 404s in any
    # other env so this action never appears in production audit trails.
    AUTH_DEV_LOGIN = "AUTH_DEV_LOGIN"

    # Backend submission execution (I-3a; some emitted by I-3b)
    SUBMISSION_BACKEND_EXECUTION_QUEUED = "SUBMISSION_BACKEND_EXECUTION_QUEUED"
    SUBMISSION_BACKEND_EXECUTION_STARTED = "SUBMISSION_BACKEND_EXECUTION_STARTED"
    SUBMISSION_BACKEND_EXECUTION_COMPLETED = "SUBMISSION_BACKEND_EXECUTION_COMPLETED"
    SUBMISSION_BACKEND_EXECUTION_FAILED = "SUBMISSION_BACKEND_EXECUTION_FAILED"
    SUBMISSION_BACKEND_EXECUTION_INTERRUPTED = "SUBMISSION_BACKEND_EXECUTION_INTERRUPTED"
    SUBMISSION_BACKEND_EXECUTION_RETRY_QUEUED = "SUBMISSION_BACKEND_EXECUTION_RETRY_QUEUED"


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
