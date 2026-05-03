"""APScheduler job functions.

Each job is idempotent — running twice produces the same result as
running once. The bodies here are also reachable via the manual
trigger endpoint so local dev and Cloud Scheduler hit identical code.
"""

from __future__ import annotations

import hashlib
import json
import logging
from time import monotonic
from urllib.parse import urlparse

from backend.audit import AuditActions, log_audit
from backend.config import get_settings
from backend.database import execute_query, execute_write, get_db
from backend.notifications import NotificationEvents, create_notification

logger = logging.getLogger(__name__)

FULL_HASH_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB streaming buffer for SHA-256.


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


# ── Phase P0f F-4: full-content-hash background job ────────────────────────


async def compute_full_content_hash() -> dict[str, int]:
    """Compute SHA-256 for sample_files rows where content_hash IS NULL.

    Reconciles fingerprint-collision dedup that the cheap fingerprint
    missed (vanishingly rare for distinct content). See
    ``spec.md`` Phase P0f Specification (the "New modules" subsection)
    and Critical Rule 58 (sample_files is the dedup primitive,
    content_hash is the logical key). Per Critical Rule 22, this job
    is idempotent and triggerable via the admin manual-trigger
    endpoint.

    Returns a counts dict ``{"hashed", "reconciled", "skipped",
    "errors"}`` for monitoring.
    """
    settings = get_settings()
    counters = {"hashed": 0, "reconciled": 0, "skipped": 0, "errors": 0}
    deadline = monotonic() + settings.full_hash_max_seconds_per_tick

    rows = _select_rows_to_hash(
        skip_remote=settings.skip_remote_full_hash,
        include_sra=settings.compute_sra_full_hash,
    )
    if not rows:
        return counters

    for row in rows:
        if monotonic() >= deadline:
            counters["skipped"] += 1
            continue

        try:
            digest = _stream_full_sha256(row["uri"])
        except Exception as exc:  # noqa: BLE001 — leave row NULL, retry next tick
            logger.warning(
                "compute_full_content_hash: failed to hash %s: %s",
                row["uri"],
                exc,
            )
            counters["errors"] += 1
            continue

        with get_db() as db:
            collision = execute_query(
                """
                SELECT id, alternate_uris
                FROM sample_files
                WHERE content_hash = :h
                  AND id != :self_id
                """,
                {"h": digest, "self_id": row["id"]},
                conn=db,
            )
            if collision:
                _reconcile_collision(row, digest, collision[0], db)
                counters["reconciled"] += 1
            else:
                execute_write(
                    "UPDATE sample_files SET content_hash = :h WHERE id = :id",
                    {"h": digest, "id": row["id"]},
                    conn=db,
                )
                counters["hashed"] += 1

    logger.info("compute_full_content_hash: %s", json.dumps(counters))
    return counters


def _select_rows_to_hash(skip_remote: bool, include_sra: bool) -> list[dict]:
    """Find sample_files rows that still need a full content hash.

    Filters out schemes the operator has opted out of (remote, SRA).
    Ordered by ``first_seen_at`` so the oldest unhashed rows go first
    — bounded-progress under wall-clock pressure.
    """
    excluded_prefixes: list[str] = []
    if skip_remote:
        excluded_prefixes += ["gs://", "s3://", "http://", "https://"]
    if not include_sra:
        excluded_prefixes.append("sra://")

    where_clauses = ["content_hash IS NULL"]
    params: dict = {}
    for i, prefix in enumerate(excluded_prefixes):
        key = f"prefix_{i}"
        where_clauses.append(f"uri NOT LIKE :{key}")
        params[key] = f"{prefix}%"

    sql = (
        "SELECT id, uri, alternate_uris FROM sample_files "
        f"WHERE {' AND '.join(where_clauses)} "
        "ORDER BY first_seen_at ASC"
    )
    return execute_query(sql, params)


def _stream_full_sha256(uri: str) -> str:
    """Stream the full URI contents into a SHA-256 in 8 MB chunks.

    Schemes mirror ``backend.file_fingerprint`` — local, gs/s3 via the
    storage layer, http(s) via httpx. Compressed bytes are hashed as-is
    (no decompression), matching the F-3 convention.
    """
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    if scheme in ("", "file"):
        path = parsed.path if scheme == "file" else uri
        return _stream_local(path)
    if scheme in ("gs", "s3"):
        return _stream_object_storage(parsed.netloc, parsed.path.lstrip("/"))
    if scheme in ("http", "https"):
        return _stream_http(uri)
    if scheme == "sra":
        # The select-rows filter normally excludes these, but defend
        # against direct calls. SRA accessions can't be byte-streamed
        # without fasterq-dump; F-4 leaves that to a future enhancement.
        raise ValueError(f"sra:// URIs cannot be streamed by F-4: {uri}")
    raise ValueError(f"Unsupported URI scheme for full hash: {scheme!r}")


def _stream_local(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(FULL_HASH_CHUNK_SIZE)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


def _stream_object_storage(bucket: str, key: str) -> str:
    from backend.storage import _get_client

    client = _get_client()
    body = client.get_object(Bucket=bucket, Key=key)["Body"]
    sha = hashlib.sha256()
    try:
        for chunk in body.iter_chunks(chunk_size=FULL_HASH_CHUNK_SIZE):
            sha.update(chunk)
    finally:
        body.close()
    return sha.hexdigest()


def _stream_http(uri: str) -> str:
    import httpx

    sha = hashlib.sha256()
    with (
        httpx.Client(follow_redirects=True) as client,
        client.stream("GET", uri) as resp,
    ):
        resp.raise_for_status()
        for chunk in resp.iter_bytes(chunk_size=FULL_HASH_CHUNK_SIZE):
            sha.update(chunk)
    return sha.hexdigest()


def _reconcile_collision(
    row: dict,
    digest: str,
    survivor: dict,
    db,
) -> None:
    """Merge ``row`` into ``survivor`` when both share the same content.

    Appends ``row.uri`` to the survivor's ``alternate_uris`` (deduped),
    redirects any inbound ``paired_file_id`` references to the survivor,
    deletes ``row``, and emits a ``RECONCILE_SAMPLE_FILES_HASH_COLLISION``
    audit entry. Same-transaction so a partial failure leaves either
    state fully reconciled or fully untouched.
    """
    existing = list(survivor.get("alternate_uris") or [])
    if row["uri"] not in existing:
        execute_write(
            """
            UPDATE sample_files
            SET alternate_uris = array_append(alternate_uris, :u)
            WHERE id = :id
            """,
            {"u": row["uri"], "id": survivor["id"]},
            conn=db,
        )
    execute_write(
        "UPDATE sample_files SET paired_file_id = :sid WHERE paired_file_id = :rid",
        {"sid": survivor["id"], "rid": row["id"]},
        conn=db,
    )
    execute_write(
        "DELETE FROM sample_files WHERE id = :id",
        {"id": row["id"]},
        conn=db,
    )
    log_audit(
        action=AuditActions.RECONCILE_SAMPLE_FILES_HASH_COLLISION,
        actor_id=None,
        resource_type="sample_files",
        resource_id=str(survivor["id"]),
        before=None,
        after=None,
        metadata={
            "survivor_id": survivor["id"],
            "merged_id": row["id"],
            "merged_uri": row["uri"],
            "content_hash": digest,
        },
        db_conn=db,
    )


# Re-export for tests and ergonomic imports.
__all__ = [
    "compute_full_content_hash",
    "run_access_request_job",
    "run_scrubber_queue_job",
    "FULL_HASH_CHUNK_SIZE",
]
