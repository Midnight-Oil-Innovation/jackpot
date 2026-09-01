# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Sovereignty-compliant deletion lifecycle (B-CARE-3a..3g).

Service layer for the four-state lifecycle from
``docs/architecture/sovereignty-compliant-deletion.md``:

    ACTIVE → DELETION_REQUESTED → TOMBSTONED → VACUUMED

Routers own authorization (§10); this module owns state-machine
preconditions (§3), derivative sealing (§13 B-CARE-3b), the vacuum
sequence (§5/§13 B-CARE-3c), and audit wiring (B-CARE-3f). Every state
transition writes an ``audit_log`` row via the pre-existing
deletion-adjacent ``AuditActions`` constants — no parallel constants.

Vacuum ordering per §13: database content is cleared first in the
caller's transaction; storage deletes are issued after. A storage-delete
failure sets ``samples.vacuum_retry_at`` and records the failed URIs in
the ``HARD_DELETE_SAMPLE`` audit row so the scheduled job can retry.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from urllib.parse import urlparse

from fastapi import HTTPException

from backend.audit import AuditActions, log_audit
from backend.authz.reseed import sync_sample_access_grants
from backend.database import execute_query, execute_write
from backend.federation.deletion_propagation import enqueue_deletion_events
from backend.notifications import create_notification
from backend.storage import StorageError, delete_file

logger = logging.getLogger(__name__)

# In-row content columns cleared at vacuum time (design §5). The CHECK
# constraint samples_vacuumed_content_gone_chk enforces these are NULL
# on every VACUUMED row.
CONTENT_URI_COLUMNS = (
    "fastq_r1_uri",
    "fastq_r2_uri",
    "raw_fastq_uri",
    "consensus_fasta_uri",
    "assembly_uri",
)

# Submission statuses that count as "pending external submission" for the
# DELETION_REQUESTED → TOMBSTONED precondition (§11).
_PENDING_SUBMISSION_STATUSES = (
    "READY_TO_SUBMIT",
    "SUBMITTED",
    "PARTIAL_SUCCESS",
    "EMBARGOED",
)


def get_sample_any_state(sample_id: int, conn) -> dict | None:
    """Fetch a sample with NO archive/deletion visibility filter.

    Lifecycle endpoints must see tombstoned and vacuumed rows that the
    normal query surfaces hide.
    """
    rows = execute_query(
        "SELECT * FROM samples WHERE id = :id LIMIT 1",
        {"id": sample_id},
        conn=conn,
    )
    return rows[0] if rows else None


def _audit(action, actor_id, sample_id, before, after, metadata, conn) -> None:
    log_audit(
        action=action,
        actor_id=actor_id,
        resource_type="sample",
        resource_id=str(sample_id),
        before=before,
        after=after,
        metadata=metadata,
        db_conn=conn,
    )


def _lifecycle_fields(row: dict) -> dict:
    return {
        "deletion_status": row.get("deletion_status"),
        "deletion_requested_at": str(row.get("deletion_requested_at") or ""),
        "tombstoned_at": str(row.get("tombstoned_at") or ""),
        "vacuumed_at": str(row.get("vacuumed_at") or ""),
        "deletion_reason": row.get("deletion_reason"),
    }


def request_deletion(sample: dict, actor: dict, reason: str, conn) -> dict:
    """ACTIVE → DELETION_REQUESTED (§3). Reason text is required."""
    if not reason or not reason.strip():
        raise HTTPException(status_code=422, detail="A deletion reason is required.")
    if sample["deletion_status"] != "ACTIVE":
        raise HTTPException(
            status_code=409,
            detail=(
                "Deletion already requested or in progress "
                f"(deletion_status={sample['deletion_status']})."
            ),
        )
    row = execute_write(
        "UPDATE samples SET deletion_status = 'DELETION_REQUESTED', "
        "deletion_requested_at = NOW(), deletion_requested_by_user_id = :uid, "
        "deletion_reason = :reason WHERE id = :id AND deletion_status = 'ACTIVE' "
        "RETURNING *",
        {"uid": actor["id"], "reason": reason.strip(), "id": sample["id"]},
        conn=conn,
    )[0]
    _audit(
        AuditActions.REQUEST_DELETION,
        actor["id"],
        sample["id"],
        _lifecycle_fields(sample),
        _lifecycle_fields(row),
        {"reason": reason.strip()},
        conn,
    )
    _notify_approvers(sample, actor, conn)
    return row


def _notify_approvers(sample: dict, actor: dict, conn) -> None:
    directors = execute_query(
        "SELECT user_id FROM lab_membership WHERE lab_id = :lab AND is_lab_director = TRUE",
        {"lab": sample["lab_id"]},
        conn=conn,
    )
    for d in directors:
        create_notification(
            recipient_id=d["user_id"],
            event_type="SAMPLE_DELETION_REQUESTED",
            title=f"Deletion requested for sample {sample['sample_id']}",
            body=f"User {actor.get('email', actor['id'])} requested deletion; approval needed.",
            resource_type="sample",
            resource_id=str(sample["id"]),
            action_url=f"/samples/{sample['id']}",
            db_conn=conn,
        )


def cancel_deletion(sample: dict, actor: dict, conn) -> dict:
    """DELETION_REQUESTED → ACTIVE (§3 cancel)."""
    if sample["deletion_status"] != "DELETION_REQUESTED":
        raise HTTPException(
            status_code=409,
            detail=f"No pending deletion request (deletion_status={sample['deletion_status']}).",
        )
    row = execute_write(
        "UPDATE samples SET deletion_status = 'ACTIVE', deletion_requested_at = NULL, "
        "deletion_requested_by_user_id = NULL, deletion_reason = NULL "
        "WHERE id = :id RETURNING *",
        {"id": sample["id"]},
        conn=conn,
    )[0]
    _audit(
        AuditActions.DENY_DELETION,
        actor["id"],
        sample["id"],
        _lifecycle_fields(sample),
        _lifecycle_fields(row),
        {"stage": "cancelled"},
        conn,
    )
    return row


def approve_deletion(sample: dict, actor: dict, conn, *, self_approve: bool = False) -> dict:
    """DELETION_REQUESTED → TOMBSTONED (§3 approve) + derivative sealing (3b)."""
    if sample["deletion_status"] != "DELETION_REQUESTED":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Sample is not deletion-requested (deletion_status={sample['deletion_status']})."
            ),
        )
    if sample["deletion_requested_by_user_id"] == actor["id"] and not (
        actor.get("is_platform_admin") and self_approve
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Approver must differ from the requester (platform admins may "
                "self-approve with platform_admin_self_approve=true)."
            ),
        )
    pending = execute_query(
        "SELECT sub.id, sub.status FROM submissions sub "
        "JOIN submission_samples ss ON ss.submission_id = sub.id "
        "WHERE ss.sample_id_fk = :id AND sub.is_archived = FALSE "
        f"AND sub.status IN {_PENDING_SUBMISSION_STATUSES}",
        {"id": sample["id"]},
        conn=conn,
    )
    if pending:
        raise HTTPException(
            status_code=409,
            detail=(
                "PENDING_EXTERNAL_SUBMISSION: withdraw or resolve submission(s) "
                f"{[p['id'] for p in pending]} before approving deletion."
            ),
        )
    row = execute_write(
        "UPDATE samples SET deletion_status = 'TOMBSTONED', tombstoned_at = NOW() "
        "WHERE id = :id RETURNING *",
        {"id": sample["id"]},
        conn=conn,
    )[0]
    _seal_derivatives(row, actor, conn)
    # B-CARE-4 (§9): tombstone events MUST reach all federation peers
    # within the SLA. Enqueued here in the same transaction; the
    # propagation job delivers and collects signed receipts.
    enqueue_deletion_events(row, "TOMBSTONE", conn)
    _audit(
        AuditActions.APPROVE_DELETION,
        actor["id"],
        sample["id"],
        _lifecycle_fields(sample),
        _lifecycle_fields(row),
        {"self_approve": self_approve},
        conn,
    )
    return row


def _seal_derivatives(sample: dict, actor: dict, conn) -> None:
    """Seal derivative rows in the caller's transaction (§13 B-CARE-3b)."""
    sealed = execute_write(
        "UPDATE pipeline_results SET tombstoned = TRUE WHERE sample_id = :sid RETURNING id",
        {"sid": sample["sample_id"]},
        conn=conn,
    )
    revoked = execute_write(
        "UPDATE sample_access_grants SET revoked = TRUE, revoked_at = NOW() "
        "WHERE sample_id = :id AND revoked = FALSE RETURNING id",
        {"id": sample["id"]},
        conn=conn,
    )
    # Every requester at once — no requester_id filter. A tombstoned sample
    # conveys access to nobody, and leaving capability grants behind would let
    # the guard allow a read the access table has already withdrawn.
    sync_sample_access_grants(conn, sample_id=sample["id"])
    memberships = execute_query(
        "SELECT * FROM dataset_files WHERE original_sample_id = :id",
        {"id": sample["id"]},
        conn=conn,
    )
    execute_write(
        "DELETE FROM dataset_files WHERE original_sample_id = :id RETURNING id",
        {"id": sample["id"]},
        conn=conn,
    )
    cancelled = execute_write(
        "UPDATE pipeline_runs SET status = 'CANCELLED', completed_at = NOW() "
        "WHERE :id = ANY(sample_ids) AND status IN ('PENDING', 'QUEUED', 'RUNNING') "
        "RETURNING id",
        {"id": sample["id"]},
        conn=conn,
    )
    _audit(
        AuditActions.SOFT_DELETE_SAMPLE,
        actor["id"],
        sample["id"],
        None,
        None,
        {
            "pipeline_results_sealed": len(sealed),
            "grants_revoked": len(revoked),
            # IDs stashed so reverse_tombstone restores exactly these grants
            # (a grant revoked before tombstoning must stay revoked).
            "grants_revoked_ids": [g["id"] for g in revoked],
            # Full rows stashed so reverse_tombstone can restore memberships.
            "dataset_files_removed": [
                {k: (str(v) if v is not None else None) for k, v in m.items()} for m in memberships
            ],
            "pipeline_runs_cancelled": [c["id"] for c in cancelled],
            "cancel_reason": "SAMPLE_TOMBSTONED",
        },
        conn,
    )


def reverse_tombstone(sample: dict, actor: dict, conn) -> dict:
    """TOMBSTONED → ACTIVE (§3 reversal, platform admin only — router enforces)."""
    if sample["deletion_status"] != "TOMBSTONED" or sample.get("vacuumed_at"):
        raise HTTPException(
            status_code=409,
            detail=(
                "Only tombstoned, not-yet-vacuumed samples can be reversed "
                f"(deletion_status={sample['deletion_status']})."
            ),
        )
    row = execute_write(
        "UPDATE samples SET deletion_status = 'ACTIVE', deletion_requested_at = NULL, "
        "deletion_requested_by_user_id = NULL, deletion_reason = NULL, "
        "tombstoned_at = NULL WHERE id = :id RETURNING *",
        {"id": sample["id"]},
        conn=conn,
    )[0]
    execute_write(
        "UPDATE pipeline_results SET tombstoned = FALSE WHERE sample_id = :sid RETURNING id",
        {"sid": sample["sample_id"]},
        conn=conn,
    )
    _restore_sealed_grants(sample, conn)
    _restore_dataset_memberships(sample, conn)
    _audit(
        AuditActions.DENY_DELETION,
        actor["id"],
        sample["id"],
        _lifecycle_fields(sample),
        _lifecycle_fields(row),
        {"stage": "reverse_tombstone"},
        conn,
    )
    return row


def _restore_sealed_grants(sample: dict, conn) -> None:
    """Un-revoke exactly the grants that tombstone sealing revoked."""
    rows = execute_query(
        "SELECT metadata FROM audit_log WHERE action = :a AND resource_type = 'sample' "
        "AND resource_id = :rid ORDER BY id DESC LIMIT 1",
        {"a": AuditActions.SOFT_DELETE_SAMPLE, "rid": str(sample["id"])},
        conn=conn,
    )
    if not rows or not rows[0].get("metadata"):
        return
    ids = [int(g) for g in rows[0]["metadata"].get("grants_revoked_ids", [])]
    if ids:
        execute_write(
            "UPDATE sample_access_grants SET revoked = FALSE, revoked_at = NULL "
            "WHERE id = ANY(:ids) RETURNING id",
            {"ids": ids},
            conn=conn,
        )
        # Reversing the tombstone restores the rows; the grants must follow or
        # the restored access exists only in the access table.
        sync_sample_access_grants(conn, sample_id=sample["id"])


def _restore_dataset_memberships(sample: dict, conn) -> None:
    rows = execute_query(
        "SELECT metadata FROM audit_log WHERE action = :a AND resource_type = 'sample' "
        "AND resource_id = :rid ORDER BY id DESC LIMIT 1",
        {"a": AuditActions.SOFT_DELETE_SAMPLE, "rid": str(sample["id"])},
        conn=conn,
    )
    if not rows or not rows[0].get("metadata"):
        return
    for m in rows[0]["metadata"].get("dataset_files_removed", []):
        dataset = execute_query(
            "SELECT id FROM analytical_datasets WHERE id = :d",
            {"d": int(m["analytical_dataset_id"])},
            conn=conn,
        )
        if not dataset:
            continue  # dataset no longer exists — nothing to restore into
        execute_write(
            "INSERT INTO dataset_files (analytical_dataset_id, original_sample_id, "
            "gcs_file_path, file_size, status) VALUES (:d, :s, :p, :z, :st) RETURNING id",
            {
                "d": int(m["analytical_dataset_id"]),
                "s": sample["id"],
                "p": m["gcs_file_path"],
                "z": int(m["file_size"]) if m.get("file_size") else None,
                "st": m.get("status") or "PENDING",
            },
            conn=conn,
        )


def _delete_storage_uri(uri: str) -> bool:
    """Delete a bucket-style object. Non-bucket URIs are logged and skipped."""
    parsed = urlparse(uri)
    if parsed.scheme not in ("gs", "s3", "minio"):
        logger.info("vacuum: skipping non-bucket URI %s", uri)
        return True
    try:
        delete_file(parsed.netloc, parsed.path.lstrip("/"))
        return True
    except StorageError:
        logger.exception("vacuum: storage delete failed for %s", uri)
        return False


def vacuum_sample(
    sample: dict,
    actor_id: int | None,
    conn,
    *,
    trigger: str,
    justification: str | None = None,
) -> dict:
    """TOMBSTONED → VACUUMED (§5, §13 B-CARE-3c/3d).

    DB content is cleared first in the caller's transaction; storage
    deletes follow. Failed deletes set ``vacuum_retry_at`` and are stored
    in the ``HARD_DELETE_SAMPLE`` audit row for the retry job.
    """
    if sample["deletion_status"] != "TOMBSTONED":
        raise HTTPException(
            status_code=409,
            detail=(
                "Only tombstoned samples can be vacuumed "
                f"(deletion_status={sample['deletion_status']})."
            ),
        )
    uris = {sample[c] for c in CONTENT_URI_COLUMNS if sample.get(c)}
    file_rows = execute_query(
        "SELECT uri, raw_uri FROM sample_files WHERE sample_id_fk = :id",
        {"id": sample["id"]},
        conn=conn,
    )
    for fr in file_rows:
        uris.update(u for u in (fr["uri"], fr.get("raw_uri")) if u)
    # Dedup guard (Critical Rule 58 analogue): an object still registered
    # to another sample must survive this sample's vacuum.
    if uris:
        shared = execute_query(
            "SELECT DISTINCT uri FROM sample_files WHERE uri = ANY(:uris) AND sample_id_fk <> :id",
            {"uris": list(uris), "id": sample["id"]},
            conn=conn,
        )
        uris -= {s["uri"] for s in shared}

    sentinel_ts = datetime.now(UTC).isoformat()
    execute_write(
        "UPDATE pipeline_results SET tombstoned = TRUE, metrics = CAST(:sent AS JSONB), "
        "results_json = CAST(:sent AS JSONB) WHERE sample_id = :sid RETURNING id",
        {
            "sid": sample["sample_id"],
            "sent": f'{{"vacuumed": true, "vacuumed_at": "{sentinel_ts}"}}',
        },
        conn=conn,
    )
    execute_write(
        "DELETE FROM sample_files WHERE sample_id_fk = :id RETURNING id",
        {"id": sample["id"]},
        conn=conn,
    )
    execute_write(
        "DELETE FROM dataset_files WHERE original_sample_id = :id RETURNING id",
        {"id": sample["id"]},
        conn=conn,
    )
    row = execute_write(
        "UPDATE samples SET "
        + ", ".join(f"{c} = NULL" for c in CONTENT_URI_COLUMNS)
        + ", deletion_status = 'VACUUMED', vacuumed_at = NOW() WHERE id = :id RETURNING *",
        {"id": sample["id"]},
        conn=conn,
    )[0]
    _audit(
        AuditActions.COMPLETE_DELETION,
        actor_id,
        sample["id"],
        _lifecycle_fields(sample),
        _lifecycle_fields(row),
        {"trigger": trigger, "justification": justification},
        conn,
    )

    deleted, failed = [], []
    for uri in sorted(uris):
        (deleted if _delete_storage_uri(uri) else failed).append(uri)
    if failed:
        execute_write(
            "UPDATE samples SET vacuum_retry_at = NOW() WHERE id = :id RETURNING id",
            {"id": sample["id"]},
            conn=conn,
        )
    _audit(
        AuditActions.HARD_DELETE_SAMPLE,
        actor_id,
        sample["id"],
        None,
        None,
        {"trigger": trigger, "storage_deleted": deleted, "storage_failed": failed},
        conn,
    )
    # B-CARE-4 (§9): vacuum events follow the same propagation pattern as
    # tombstone events; peers that fail to acknowledge within 2× the SLA
    # are auto-flagged for operator intervention.
    enqueue_deletion_events(row, "VACUUM", conn)
    return row


def retry_failed_storage_deletes(conn) -> int:
    """Retry storage deletes recorded as failed by a prior vacuum."""
    retried = 0
    rows = execute_query(
        "SELECT id FROM samples WHERE deletion_status = 'VACUUMED' AND vacuum_retry_at IS NOT NULL",
        conn=conn,
    )
    for r in rows:
        audit = execute_query(
            "SELECT metadata FROM audit_log WHERE action = :a AND resource_type = 'sample' "
            "AND resource_id = :rid ORDER BY id DESC LIMIT 1",
            {"a": AuditActions.HARD_DELETE_SAMPLE, "rid": str(r["id"])},
            conn=conn,
        )
        pending = (audit[0].get("metadata") or {}).get("storage_failed", []) if audit else []
        still_failed = [u for u in pending if not _delete_storage_uri(u)]
        if not still_failed:
            execute_write(
                "UPDATE samples SET vacuum_retry_at = NULL WHERE id = :id RETURNING id",
                {"id": r["id"]},
                conn=conn,
            )
            retried += 1
        _audit(
            AuditActions.HARD_DELETE_SAMPLE,
            None,
            r["id"],
            None,
            None,
            {
                "trigger": "retry",
                "storage_deleted": [u for u in pending if u not in still_failed],
                "storage_failed": still_failed,
            },
            conn,
        )
    return retried


def deletion_report(sample: dict, conn) -> dict:
    """RTBF confirmation report (B-CARE-3g): lifecycle + erasure state."""
    file_count = execute_query(
        "SELECT COUNT(*) AS n FROM sample_files WHERE sample_id_fk = :id",
        {"id": sample["id"]},
        conn=conn,
    )[0]["n"]
    trail = execute_query(
        'SELECT action, actor_id, "timestamp" FROM audit_log '
        "WHERE resource_type = 'sample' AND resource_id = :rid AND action IN "
        "('REQUEST_DELETION', 'APPROVE_DELETION', 'DENY_DELETION', "
        "'SOFT_DELETE_SAMPLE', 'COMPLETE_DELETION', 'HARD_DELETE_SAMPLE') "
        "ORDER BY id",
        {"rid": str(sample["id"])},
        conn=conn,
    )
    retractions = execute_query(
        "SELECT repository, accession, retraction_protocol, status, requested_at "
        "FROM external_retraction_requests WHERE sample_id = :id ORDER BY id",
        {"id": sample["id"]},
        conn=conn,
    )
    previously_published = bool(
        sample.get("biosample_accession")
        or sample.get("sra_accession")
        or sample.get("genbank_accession")
        or sample.get("gisaid_accession")
        or sample.get("ncbi_submission_status") not in (None, "NOT_SUBMITTED")
        or sample.get("gisaid_submission_status") not in (None, "NOT_SUBMITTED")
    )
    return {
        "sample_id": sample["id"],
        "external_sample_id": sample["sample_id"],
        **_lifecycle_fields(sample),
        "content_erased": (
            sample["deletion_status"] == "VACUUMED"
            and all(not sample.get(c) for c in CONTENT_URI_COLUMNS)
            and file_count == 0
        ),
        "registered_file_count": file_count,
        "storage_delete_retry_pending": sample.get("vacuum_retry_at") is not None,
        "previously_published": previously_published,
        "audit_trail": [
            {"action": t["action"], "actor_id": t["actor_id"], "at": str(t["timestamp"])}
            for t in trail
        ],
        "external_retraction_requests": [
            {**r, "requested_at": str(r["requested_at"])} for r in retractions
        ],
    }


def record_retraction_request(
    sample: dict,
    actor: dict,
    conn,
    *,
    repository: str,
    accession: str | None,
    retraction_protocol: str | None,
) -> dict:
    """B-CARE-3g stub: record external-retraction intent. No protocol I/O."""
    row = execute_write(
        "INSERT INTO external_retraction_requests "
        "(sample_id, repository, accession, retraction_protocol, requested_by_user_id) "
        "VALUES (:sid, :repo, :acc, :proto, :uid) RETURNING *",
        {
            "sid": sample["id"],
            "repo": repository,
            "acc": accession,
            "proto": retraction_protocol,
            "uid": actor["id"],
        },
        conn=conn,
    )[0]
    _audit(
        AuditActions.REQUEST_DELETION,
        actor["id"],
        sample["id"],
        None,
        None,
        {"kind": "external_retraction", "repository": repository, "accession": accession},
        conn,
    )
    return row
