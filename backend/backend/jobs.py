"""APScheduler job functions.

Each job is idempotent — running twice produces the same result as
running once. The bodies here are also reachable via the manual
trigger endpoint so local dev and Cloud Scheduler hit identical code.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
from time import monotonic
from urllib.parse import urlparse

from backend.audit import AuditActions, log_audit
from backend.config import get_settings
from backend.database import execute_query, execute_write, get_db
from backend.file_fingerprint import cheap_fingerprint
from backend.notifications import NotificationEvents, create_notification

logger = logging.getLogger(__name__)

FULL_HASH_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB streaming buffer for SHA-256.

# Phase P0f F-9: streaming-copy chunk size for ``promote_file_storage``.
# The runtime value is ``settings.promote_chunk_size_mb * 1024 * 1024``;
# this constant is the fallback used by helpers that don't accept a
# chunk-size parameter (the httpx streaming wrapper) and for tests.
PROMOTE_CHUNK_SIZE = 8 * 1024 * 1024


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


# ── Phase P0f F-5: verify_file_references background job ───────────────────


_FAILURE_KINDS = ("MISSING", "SIZE_CHANGED", "READ_ERROR")


async def verify_file_references() -> dict[str, int]:
    """Re-stat EXTERNAL/MIRRORED sample_files; transition stale rows to BROKEN.

    The safety net for the no-copy ingest model: if JACKPOT references a
    file in place and the user later deletes or relocates that file,
    this job notices and surfaces the broken reference to the lab
    director(s) of every sample using it before a pipeline tries to
    launch and fails mid-run. See ``spec.md`` Phase P0f Specification
    (the "New modules" subsection) and Critical Rules 4 (state changes
    audited), 22 (idempotent, manual-trigger-friendly), and 57 (no copy
    on ingest — verification is the correctness mechanism that makes
    the policy safe).

    The three-strike rule is intentional: transient I/O failures are
    common (NAS hiccups, brief permission glitches, network blips), and
    BROKEN is a state operators have to recover from manually. Only
    persistent failures across three consecutive ticks transition the
    row.

    Returns counts ``{"verified_ok", "verification_failed",
    "transitioned_to_broken", "skipped"}`` for monitoring.
    """
    settings = get_settings()
    counters = {
        "verified_ok": 0,
        "verification_failed": 0,
        "transitioned_to_broken": 0,
        "skipped": 0,
    }

    rows = execute_query(
        """
        SELECT id, uri, file_size_bytes, head64k_hash, tail64k_hash,
               last_verification_status, storage_state
        FROM sample_files
        WHERE storage_state IN ('EXTERNAL', 'MIRRORED')
          AND COALESCE(is_deleted, FALSE) = FALSE
        ORDER BY last_verified_at ASC NULLS FIRST
        LIMIT :limit
        """,
        {"limit": settings.verification_files_per_tick},
    )
    if not rows:
        return counters

    threshold = settings.verification_consecutive_failures_to_break
    re_fp = settings.verification_re_fingerprint

    for row in rows:
        kind = _verify_one(row, re_fingerprint=re_fp)

        with get_db() as db:
            if kind is None:
                execute_write(
                    """
                    UPDATE sample_files
                    SET last_verified_at = NOW(),
                        last_verification_status = 'OK'
                    WHERE id = :id
                    """,
                    {"id": row["id"]},
                    conn=db,
                )
                counters["verified_ok"] += 1
                continue

            new_status, count = _next_failure_status(row.get("last_verification_status"), kind)
            counters["verification_failed"] += 1

            if count >= threshold:
                execute_write(
                    """
                    UPDATE sample_files
                    SET storage_state = 'BROKEN',
                        last_verified_at = NOW(),
                        last_verification_status = :status
                    WHERE id = :id
                    """,
                    {"status": new_status, "id": row["id"]},
                    conn=db,
                )
                log_audit(
                    action=AuditActions.VERIFY_FILE_FAILED,
                    actor_id=None,
                    resource_type="sample_files",
                    resource_id=str(row["id"]),
                    before=None,
                    after=None,
                    metadata={
                        "uri": row["uri"],
                        "status": new_status,
                        "count": count,
                    },
                    db_conn=db,
                )
                _emit_broken_audit_and_notifications(row, new_status, db)
                counters["transitioned_to_broken"] += 1
            else:
                execute_write(
                    """
                    UPDATE sample_files
                    SET last_verified_at = NOW(),
                        last_verification_status = :status
                    WHERE id = :id
                    """,
                    {"status": new_status, "id": row["id"]},
                    conn=db,
                )
                log_audit(
                    action=AuditActions.VERIFY_FILE_FAILED,
                    actor_id=None,
                    resource_type="sample_files",
                    resource_id=str(row["id"]),
                    before=None,
                    after=None,
                    metadata={
                        "uri": row["uri"],
                        "status": new_status,
                        "count": count,
                    },
                    db_conn=db,
                )

    logger.info("verify_file_references: %s", json.dumps(counters))
    return counters


def _verify_one(row: dict, *, re_fingerprint: bool) -> str | None:
    """Return ``None`` on OK, otherwise the failure kind string.

    Failure kinds: ``MISSING`` (URI does not resolve), ``SIZE_CHANGED``
    (size differs from the recorded ``file_size_bytes``, or — when
    ``re_fingerprint`` is true — the cheap fingerprint differs), or
    ``READ_ERROR`` (anything else: timeouts, permission failures,
    transient cloud errors).
    """
    uri = row["uri"]
    try:
        size = _stat_uri(uri)
    except FileNotFoundError:
        return "MISSING"
    except Exception as exc:  # noqa: BLE001 — categorize as transient and retry
        logger.warning("verify_file_references: stat error on %s: %s", uri, exc)
        return "READ_ERROR"

    expected_size = row.get("file_size_bytes")
    if expected_size is not None and size is not None and size != expected_size:
        return "SIZE_CHANGED"

    if re_fingerprint:
        try:
            _, head_hash, tail_hash = cheap_fingerprint(uri)
        except Exception as exc:  # noqa: BLE001
            logger.warning("verify_file_references: re-fingerprint failed on %s: %s", uri, exc)
            return "READ_ERROR"
        prev_head = row.get("head64k_hash")
        prev_tail = row.get("tail64k_hash")
        if prev_head and prev_tail and (head_hash != prev_head or tail_hash != prev_tail):
            return "SIZE_CHANGED"

    return None


def _stat_uri(uri: str) -> int | None:
    """Return the size in bytes for ``uri``, or raise.

    Mirrors the scheme handling in ``backend.file_fingerprint`` but only
    issues a HEAD/stat — never reads file body. Raises
    ``FileNotFoundError`` on definite-missing, anything else on
    transient/unknown failures (caller maps to ``READ_ERROR``). SRA
    URIs return ``None`` to signal "size unknown, treat OK" because
    archives don't yield to byte-range reads.
    """
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    if scheme in ("", "file"):
        path = parsed.path if scheme == "file" else uri
        return os.stat(path).st_size
    if scheme in ("gs", "s3"):
        from botocore.exceptions import ClientError

        from backend.storage import _get_client

        client = _get_client()
        try:
            head = client.head_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            http_status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code in ("NoSuchKey", "NotFound", "404") or http_status == 404:
                raise FileNotFoundError(uri) from exc
            raise
        return int(head["ContentLength"])
    if scheme in ("http", "https"):
        import httpx

        with httpx.Client(follow_redirects=True, timeout=30.0) as client:
            resp = client.head(uri)
            if resp.status_code == 404:
                raise FileNotFoundError(uri)
            resp.raise_for_status()
            cl = resp.headers.get("Content-Length")
            return int(cl) if cl is not None else None
    if scheme == "sra":
        return None  # archives — caller treats None as "size check skipped"
    raise ValueError(f"Unsupported URI scheme for verification: {scheme!r}")


def _parse_failure_count(status: str | None) -> int:
    """Extract the consecutive-failure count from a ``last_verification_status``.

    ``None``/``OK`` → 0; ``MISSING``/``READ_ERROR``/``SIZE_CHANGED`` → 1;
    suffixed forms (``MISSING_2``, ``READ_ERROR_3``) → the suffixed number.
    Unknown shapes default to 1 — that's safer than 0 because it preserves
    the existing failure run rather than silently resetting it.
    """
    if status is None or status == "OK":
        return 0
    suffix = status.rsplit("_", 1)[-1]
    if suffix.isdigit():
        return int(suffix)
    return 1


def _next_failure_status(prev_status: str | None, new_kind: str) -> tuple[str, int]:
    """Return ``(new_status, consecutive_failure_count)`` for a failed tick.

    The kind in the returned status is always the most recent failure —
    operators see what failed last, not what failed two ticks ago. Counts
    cap at 3 so the state machine stays deterministic if a row is
    re-verified after the BROKEN transition (which shouldn't happen, but
    defends against it cheaply).
    """
    if new_kind not in _FAILURE_KINDS:
        raise ValueError(f"Unknown failure kind: {new_kind!r}")
    new_count = min(_parse_failure_count(prev_status) + 1, 3)
    if new_count == 1:
        return (new_kind, 1)
    return (f"{new_kind}_{new_count}", new_count)


def _lab_directors_for_sample_file(sample_file_id: int, db) -> list[int]:
    """Distinct user_ids of all lab directors of all live samples
    referencing this ``sample_files`` row.

    Soft-deleted samples (``is_deleted=TRUE``) are excluded. If every
    referencing sample is deleted, returns ``[]`` — caller treats as
    orphan and logs a WARNING rather than emitting silent BROKEN
    transitions.
    """
    rows = execute_query(
        """
        SELECT DISTINCT lm.user_id
        FROM sample_files sf
        JOIN samples s ON s.id = sf.sample_id_fk AND s.is_deleted = FALSE
        JOIN lab_membership lm ON lm.lab_id = s.lab_id
        WHERE sf.id = :sfid
          AND lm.is_lab_director = TRUE
        """,
        {"sfid": sample_file_id},
        conn=db,
    )
    return [r["user_id"] for r in rows]


def _emit_broken_audit_and_notifications(row: dict, status_at_break: str, db) -> None:
    """Audit the BROKEN transition and notify lab directors."""
    sample_file_id = row["id"]
    uri = row["uri"]
    log_audit(
        action=AuditActions.MARK_FILE_BROKEN,
        actor_id=None,
        resource_type="sample_files",
        resource_id=str(sample_file_id),
        before={"storage_state": row["storage_state"]},
        after={"storage_state": "BROKEN"},
        metadata={"uri": uri, "last_verification_status": status_at_break},
        db_conn=db,
    )
    directors = _lab_directors_for_sample_file(sample_file_id, db)
    if not directors:
        logger.warning(
            "verify_file_references: sample_files row %s transitioned to "
            "BROKEN with no lab-director recipients (orphan)",
            sample_file_id,
        )
        return
    filename = uri.rsplit("/", 1)[-1] or uri
    body = (
        f"JACKPOT can no longer reach a registered file ({uri}). "
        f"The latest verification reported {status_at_break}. "
        "Re-locate the file, re-upload it, or mark the affected sample "
        "inactive."
    )
    for user_id in directors:
        create_notification(
            recipient_id=user_id,
            event_type=NotificationEvents.FILE_REFERENCE_BROKEN,
            title=f"File reference broken: {filename}",
            body=body,
            resource_type="sample_files",
            resource_id=str(sample_file_id),
            action_url=f"/files/{sample_file_id}",
            db_conn=db,
        )


# ── Phase P0f F-9: promote_file_storage one-shot job ───────────────────────


# Module-level in-memory tracker for promotion jobs. The /api/v1/files/
# jobs/{job_id} endpoint reads from here so the CLI's --wait flag can
# poll. Single-process scope: a job started on one API instance is
# invisible to siblings, and an interrupted promotion's tracker entry
# disappears with the process. The destination may be half-written on
# crash but the source is intact and the sample_files row is unchanged
# (see ``_promote_finalize`` for the atomicity argument). A persistent
# jobs table is a future P-x improvement.
_PROMOTE_JOBS: dict[str, dict] = {}
_PROMOTE_JOBS_MAX = 1000


def _record_promote_job(job_id: str, **fields) -> None:
    """Insert or update an entry in :data:`_PROMOTE_JOBS`.

    Bounded at :data:`_PROMOTE_JOBS_MAX` entries by dropping the oldest
    (insertion-order) when the cap would be exceeded.
    """
    if job_id not in _PROMOTE_JOBS and len(_PROMOTE_JOBS) >= _PROMOTE_JOBS_MAX:
        oldest = next(iter(_PROMOTE_JOBS))
        _PROMOTE_JOBS.pop(oldest, None)
    entry = _PROMOTE_JOBS.setdefault(job_id, {})
    entry.update(fields)


def get_promote_job_status(job_id: str) -> dict | None:
    """Look up a promotion job in the in-memory tracker.

    Returns ``None`` when the job is unknown to this process — either
    because it never ran, ran on another instance, or the process was
    restarted since.
    """
    return _PROMOTE_JOBS.get(job_id)


def _join_uri(root: str, *parts: str) -> str:
    """Compose ``root/parts/.../`` keeping exactly one slash between segments."""
    pieces = [root.rstrip("/")] + [p.strip("/") for p in parts if p]
    return "/".join(pieces)


def _filename_from_uri(uri: str) -> str:
    parsed = urlparse(uri)
    path = parsed.path if parsed.scheme else uri
    name = os.path.basename(path) or "file.bin"
    return name


def _scheme_of(uri: str) -> str:
    return urlparse(uri).scheme.lower() or "file"


def _bucket_and_key(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    return parsed.netloc, parsed.path.lstrip("/")


def _open_source_stream(uri: str, *, chunk_size: int) -> tuple:
    """Open a readable stream + content-length for ``uri``.

    Returns ``(stream, size_bytes)``. Caller is responsible for closing
    the stream. Implementations match :mod:`backend.file_fingerprint`'s
    scheme dispatch — local via ``open``, ``gs://`` / ``s3://`` via the
    boto3 client, ``http(s)://`` via ``httpx``. ``sra://`` is rejected:
    archives can't be byte-streamed without ``fasterq-dump`` and a
    promotion of an SRA reference is not a meaningful operation in F-9.
    """
    scheme = _scheme_of(uri)
    if scheme in ("file", ""):
        path = urlparse(uri).path if scheme == "file" else uri
        size = os.stat(path).st_size
        return open(path, "rb"), size  # noqa: SIM115 — caller closes
    if scheme in ("gs", "s3"):
        from backend.storage import _get_client

        bucket, key = _bucket_and_key(uri)
        client = _get_client()
        head = client.head_object(Bucket=bucket, Key=key)
        body = client.get_object(Bucket=bucket, Key=key)["Body"]
        return body, int(head["ContentLength"])
    if scheme in ("http", "https"):
        import httpx

        client = httpx.Client(follow_redirects=True, timeout=300.0)
        resp = client.send(client.build_request("GET", uri), stream=True)
        resp.raise_for_status()
        cl = resp.headers.get("Content-Length")
        size = int(cl) if cl else 0

        class _HttpxStream:
            def __init__(self, resp, client, chunk_size):
                self._resp = resp
                self._client = client
                self._iter = resp.iter_bytes(chunk_size=chunk_size)
                self._buf = b""

            def read(self, n: int = -1) -> bytes:
                if n is None or n < 0:
                    chunks = [self._buf, *list(self._iter)]
                    self._buf = b""
                    return b"".join(chunks)
                while len(self._buf) < n:
                    try:
                        self._buf += next(self._iter)
                    except StopIteration:
                        break
                out, self._buf = self._buf[:n], self._buf[n:]
                return out

            def close(self) -> None:
                with contextlib.suppress(Exception):
                    self._resp.close()
                with contextlib.suppress(Exception):
                    self._client.close()

        return _HttpxStream(resp, client, chunk_size), size
    if scheme == "sra":
        raise ValueError(
            "Cannot promote an sra:// reference — SRA accessions are "
            "fetched fresh at pipeline time and have no persistent bytes "
            "to copy. Use a different ingest path if you need a stable "
            "managed copy."
        )
    raise ValueError(f"Unsupported source scheme for promote: {scheme!r}")


def _stream_copy_with_hash(source_uri: str, dest_uri: str, *, chunk_size: int) -> tuple[int, str]:
    """Copy ``source_uri`` → ``dest_uri`` byte-for-byte with SHA-256.

    Returns ``(bytes_copied, sha256_hex)``. Streaming is the lowest
    common denominator — works regardless of source/destination scheme
    pairing. Same-cloud transitions get an early server-side fast-path
    in :func:`_promote_copy` and never reach this helper.

    The destination is opened, written, and closed inside this helper;
    the source stream is closed in the caller's ``finally`` block so
    that retries don't leak file descriptors.
    """
    sha = hashlib.sha256()
    bytes_copied = 0
    src_stream, _src_size = _open_source_stream(source_uri, chunk_size=chunk_size)
    try:
        dest_scheme = _scheme_of(dest_uri)
        if dest_scheme in ("file", ""):
            path = urlparse(dest_uri).path if dest_scheme == "file" else dest_uri
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as dest:
                while True:
                    chunk = src_stream.read(chunk_size)
                    if not chunk:
                        break
                    dest.write(chunk)
                    sha.update(chunk)
                    bytes_copied += len(chunk)
        elif dest_scheme in ("gs", "s3"):
            import io

            from backend.storage import _get_client

            bucket, key = _bucket_and_key(dest_uri)
            buffer = io.BytesIO()
            while True:
                chunk = src_stream.read(chunk_size)
                if not chunk:
                    break
                buffer.write(chunk)
                sha.update(chunk)
                bytes_copied += len(chunk)
            buffer.seek(0)
            _get_client().put_object(Bucket=bucket, Key=key, Body=buffer.getvalue())
        else:
            raise ValueError(f"Unsupported destination scheme for promote: {dest_scheme!r}")
    finally:
        with contextlib.suppress(Exception):
            src_stream.close()
    return bytes_copied, sha.hexdigest()


def _server_side_copy_if_supported(source_uri: str, dest_uri: str) -> bool:
    """Try a server-side copy when both URIs are on the same backend.

    Returns ``True`` when the copy was issued server-side and no host
    bytes were streamed; ``False`` when the caller should fall back to
    streaming. Same-bucket and cross-bucket are both handled — the
    storage layer routes both to S3-compatible CopyObject. Hash
    verification still happens in the caller via
    :func:`_destination_full_sha256`.
    """
    src_scheme = _scheme_of(source_uri)
    dst_scheme = _scheme_of(dest_uri)
    if src_scheme != dst_scheme or src_scheme not in ("gs", "s3"):
        return False
    from backend.storage import _get_client

    src_bucket, src_key = _bucket_and_key(source_uri)
    dst_bucket, dst_key = _bucket_and_key(dest_uri)
    _get_client().copy_object(
        Bucket=dst_bucket,
        Key=dst_key,
        CopySource={"Bucket": src_bucket, "Key": src_key},
    )
    return True


def _destination_full_sha256(dest_uri: str, chunk_size: int) -> str:
    """Re-stream the destination and return its SHA-256.

    Used for server-side copies (where we never see the bytes locally
    and therefore haven't hashed them on the way through). Adds an
    extra full read at the destination but is the only way to verify
    a CopyObject result without trusting the backend. ``chunk_size``
    is reserved for backends that benefit from a tunable read size;
    the underlying ``_stream_full_sha256`` reads in 8 MB blocks.
    """
    del chunk_size  # honoured by _stream_full_sha256's internal default
    return _stream_full_sha256(dest_uri)


def _delete_destination_quietly(dest_uri: str) -> None:
    """Best-effort cleanup of a partial destination after a failed copy."""
    scheme = _scheme_of(dest_uri)
    try:
        if scheme in ("file", ""):
            path = urlparse(dest_uri).path if scheme == "file" else dest_uri
            if os.path.exists(path):
                os.unlink(path)
        elif scheme in ("gs", "s3"):
            from backend.storage import _get_client

            bucket, key = _bucket_and_key(dest_uri)
            _get_client().delete_object(Bucket=bucket, Key=key)
    except Exception as exc:  # noqa: BLE001 — best effort
        logger.warning("promote: failed to clean up partial dest %s: %s", dest_uri, exc)


def _promote_destination_uri(file_row: dict, sample_id_int: int, settings) -> str:
    """Compute the managed-side URI for a promotion.

    The convention mirrors ``/upload``'s staging path: outputs go under
    ``{managed_storage_root}/sample_{sample_id_int}/{filename}`` so two
    samples that share a filename can both be promoted without
    collision. ``managed_storage_root`` carries no default — operators
    set it via ``Settings.managed_storage_root``.
    """
    if not settings.managed_storage_root:
        raise RuntimeError(
            "managed_storage_root is not configured. Set the "
            "MANAGED_STORAGE_ROOT environment variable (or the "
            "managed_storage_root setting) to the operator-controlled "
            "managed-storage URI prefix before promoting files."
        )
    filename = _filename_from_uri(file_row["uri"])
    return _join_uri(settings.managed_storage_root, f"sample_{sample_id_int}", filename)


def _promote_finalize(
    *,
    file_id: int,
    target_state: str,
    retention_policy: str,
    source_uri: str,
    dest_uri: str,
    db,
) -> None:
    """Atomically transition a sample_files row to the target state.

    Both the row update and the audit log entry land in the same
    transaction so a partial state (state changed but audit missing,
    or vice versa) is impossible. ``alternate_uris`` carries the
    pre-promotion URI for traceability so callers reading by either
    URI still find the row after promotion.

    For ``MANAGED``: the row's primary ``uri`` becomes the new managed
    location; ``original_uri`` records where the file came from.
    For ``MIRRORED``: the primary ``uri`` stays at the source (still
    authoritative); the managed copy is recorded in ``alternate_uris``
    and ``original_uri`` mirrors the primary ``uri``.
    """
    if target_state == "MANAGED":
        execute_write(
            """
            UPDATE sample_files
            SET storage_state = 'MANAGED',
                uri = :new_uri,
                original_uri = :orig_uri,
                retention_policy = :rp,
                alternate_uris = (
                    CASE
                      WHEN :orig_uri = ANY(COALESCE(alternate_uris, ARRAY[]::TEXT[]))
                      THEN alternate_uris
                      ELSE array_append(COALESCE(alternate_uris, ARRAY[]::TEXT[]), :orig_uri)
                    END
                )
            WHERE id = :id
            """,
            {"new_uri": dest_uri, "orig_uri": source_uri, "rp": retention_policy, "id": file_id},
            conn=db,
        )
    else:  # MIRRORED
        execute_write(
            """
            UPDATE sample_files
            SET storage_state = 'MIRRORED',
                original_uri = :orig_uri,
                retention_policy = :rp,
                alternate_uris = (
                    CASE
                      WHEN :new_uri = ANY(COALESCE(alternate_uris, ARRAY[]::TEXT[]))
                      THEN alternate_uris
                      ELSE array_append(COALESCE(alternate_uris, ARRAY[]::TEXT[]), :new_uri)
                    END
                )
            WHERE id = :id
            """,
            {"new_uri": dest_uri, "orig_uri": source_uri, "rp": retention_policy, "id": file_id},
            conn=db,
        )


async def promote_file_storage(
    file_id: int,
    target_state: str,
    retention_policy: str,
    trigger_user_id: int,
    job_id: str,
) -> dict:
    """Stream-copy a file to managed storage; transition the row on success.

    Phase P0f F-9. APScheduler one-shot job triggered by
    ``POST /api/v1/files/{file_id}/promote``.

    Per Critical Rule 4 (audit on state change), 22 (idempotent — a
    second run against an already-promoted row is a no-op),
    57 (copies are explicit), and 58 (sample_files is the dedup
    primitive — promotion mutates state, never the dedup keying).

    Returns a counters dict that's both logged and stored on the
    in-memory tracker entry so the CLI ``--wait`` poller can read it.

    Failure semantics: the source file is never touched, and the
    sample_files row only transitions if the copy plus hash check both
    succeed inside the same transaction. A failed copy leaves the row
    untouched, deletes any partial destination, audits ``PROMOTE_FILE_FAILED``,
    and notifies ``trigger_user_id`` via ``FILE_PROMOTION_FAILED``.
    """
    settings = get_settings()
    chunk_size = settings.promote_chunk_size_mb * 1024 * 1024
    counters = {
        "file_id": file_id,
        "job_id": job_id,
        "target_state": target_state,
        "outcome": "RUNNING",
        "copied_bytes": 0,
        "elapsed_seconds": 0.0,
        "verified_hash": None,
        "error_message": None,
    }
    _record_promote_job(job_id, status="RUNNING", file_id=file_id, target_state=target_state)
    started = monotonic()

    rows = execute_query(
        """
        SELECT id, sample_id_fk, uri, storage_state, file_size_bytes
        FROM sample_files
        WHERE id = :id
          AND COALESCE(is_deleted, FALSE) = FALSE
        LIMIT 1
        """,
        {"id": file_id},
    )
    if not rows:
        counters["outcome"] = "FAILURE"
        counters["error_message"] = f"sample_files {file_id} not found"
        _record_promote_job(job_id, status="FAILED", error=counters["error_message"])
        logger.error("promote_file_storage: %s", counters["error_message"])
        return counters
    file_row = rows[0]
    source_uri = file_row["uri"]
    sample_id_int = file_row["sample_id_fk"]

    if file_row["storage_state"] == target_state:
        counters["outcome"] = "SUCCESS"
        counters["error_message"] = "already_in_target_state"
        _record_promote_job(job_id, status="COMPLETED", outcome="NOOP")
        return counters

    try:
        dest_uri = _promote_destination_uri(file_row, sample_id_int, settings)
    except RuntimeError as exc:
        counters["outcome"] = "FAILURE"
        counters["error_message"] = str(exc)
        _record_promote_job(job_id, status="FAILED", error=str(exc))
        logger.error("promote_file_storage: %s", exc)
        return counters

    digest: str | None = None
    bytes_copied = 0
    try:
        if _server_side_copy_if_supported(source_uri, dest_uri):
            if settings.promote_verify_hash:
                digest = _destination_full_sha256(dest_uri, chunk_size)
            bytes_copied = file_row.get("file_size_bytes") or 0
        else:
            bytes_copied, digest = _stream_copy_with_hash(
                source_uri, dest_uri, chunk_size=chunk_size
            )
    except Exception as exc:  # noqa: BLE001 — copy failures are user-surfaceable
        counters["outcome"] = "FAILURE"
        counters["error_message"] = f"{type(exc).__name__}: {exc}"
        counters["elapsed_seconds"] = monotonic() - started
        _delete_destination_quietly(dest_uri)
        with get_db() as db:
            log_audit(
                action=AuditActions.PROMOTE_FILE_FAILED,
                actor_id=trigger_user_id,
                resource_type="sample_files",
                resource_id=str(file_id),
                before={"storage_state": file_row["storage_state"], "uri": source_uri},
                after=None,
                metadata={
                    "target_state": target_state,
                    "job_id": job_id,
                    "error": counters["error_message"],
                },
                db_conn=db,
            )
            create_notification(
                recipient_id=trigger_user_id,
                event_type=NotificationEvents.FILE_PROMOTION_FAILED,
                title=f"File promotion failed (file_id={file_id})",
                body=(
                    f"JACKPOT could not copy {source_uri} into managed "
                    f"storage. Error: {counters['error_message']}. The "
                    "file is unchanged; retry once the underlying issue "
                    "is resolved."
                ),
                resource_type="sample_files",
                resource_id=str(file_id),
                action_url=f"/files/{file_id}",
                db_conn=db,
            )
        _record_promote_job(
            job_id,
            status="FAILED",
            error=counters["error_message"],
            elapsed_seconds=counters["elapsed_seconds"],
        )
        logger.warning(
            "promote_file_storage: file_id=%s failed: %s", file_id, counters["error_message"]
        )
        return counters

    counters["copied_bytes"] = bytes_copied
    counters["verified_hash"] = digest

    with get_db() as db:
        _promote_finalize(
            file_id=file_id,
            target_state=target_state,
            retention_policy=retention_policy,
            source_uri=source_uri,
            dest_uri=dest_uri,
            db=db,
        )
        log_audit(
            action=AuditActions.PROMOTE_FILE,
            actor_id=trigger_user_id,
            resource_type="sample_files",
            resource_id=str(file_id),
            before={"storage_state": file_row["storage_state"], "uri": source_uri},
            after={"storage_state": target_state, "uri": dest_uri},
            metadata={
                "target_state": target_state,
                "retention_policy": retention_policy,
                "job_id": job_id,
                "copied_bytes": bytes_copied,
                "verified_hash": digest,
            },
            db_conn=db,
        )
        create_notification(
            recipient_id=trigger_user_id,
            event_type=NotificationEvents.FILE_PROMOTED,
            title=f"File promoted to {target_state}",
            body=(
                f"JACKPOT now manages a copy of {_filename_from_uri(source_uri)} at "
                f"{dest_uri} (storage_state={target_state})."
            ),
            resource_type="sample_files",
            resource_id=str(file_id),
            action_url=f"/files/{file_id}",
            db_conn=db,
        )

    counters["outcome"] = "SUCCESS"
    counters["elapsed_seconds"] = monotonic() - started
    _record_promote_job(
        job_id,
        status="COMPLETED",
        outcome="SUCCESS",
        copied_bytes=bytes_copied,
        verified_hash=digest,
        elapsed_seconds=counters["elapsed_seconds"],
        dest_uri=dest_uri,
    )
    logger.info("promote_file_storage: file_id=%s outcome=SUCCESS bytes=%s", file_id, bytes_copied)
    return counters


# ── Phase P0f F-9: per-file verification helper for the /verify endpoint ──


def verify_sample_file(file_id: int) -> dict:
    """Synchronous re-stat of one sample_files row.

    Phase P0f F-9. Powers ``POST /api/v1/files/{file_id}/verify`` so a
    user can clear a stale ``BROKEN`` state immediately after putting
    the file back, instead of waiting for the daily verification job.

    The check uses the same ``_verify_one`` machinery as the
    background job — what differs is the post-check behavior:

    * On a failed check against a non-BROKEN row: write the
      consecutive-failure status (with the same three-strike rule),
      transition to ``BROKEN`` only if the third strike has been
      reached.
    * On a failed check against an already-BROKEN row: keep
      ``BROKEN``, refresh ``last_verification_status``.
    * On a successful check against a ``BROKEN`` row: clear back to
      the row's pre-broken non-terminal state (``EXTERNAL`` or
      ``MIRRORED`` — inferred from ``original_uri``).
    * On a successful check against any other state: refresh
      ``last_verified_at`` and set ``last_verification_status='OK'``.

    Returns the post-verify row snapshot ``{file_id, uri, storage_state,
    last_verification_status, last_verified_at}``. Raises
    ``FileNotFoundError`` when the row does not exist.
    """
    settings = get_settings()
    rows = execute_query(
        """
        SELECT id, uri, file_size_bytes, head64k_hash, tail64k_hash,
               last_verification_status, storage_state, original_uri
        FROM sample_files
        WHERE id = :id
          AND COALESCE(is_deleted, FALSE) = FALSE
        LIMIT 1
        """,
        {"id": file_id},
    )
    if not rows:
        raise FileNotFoundError(f"sample_files row {file_id} not found")
    row = rows[0]

    kind = _verify_one(row, re_fingerprint=settings.verification_re_fingerprint)
    threshold = settings.verification_consecutive_failures_to_break

    with get_db() as db:
        if kind is None:
            if row["storage_state"] == "BROKEN":
                # Recover: clear back to the appropriate non-terminal
                # state. ``original_uri`` is set on MIRRORED rows after
                # promotion (see _promote_finalize); when present we
                # treat the file as MIRRORED, otherwise EXTERNAL.
                recovered_state = "MIRRORED" if row.get("original_uri") else "EXTERNAL"
                execute_write(
                    """
                    UPDATE sample_files
                    SET storage_state = CAST(:s AS file_storage_state),
                        last_verified_at = NOW(),
                        last_verification_status = 'OK'
                    WHERE id = :id
                    """,
                    {"s": recovered_state, "id": file_id},
                    conn=db,
                )
                log_audit(
                    action=AuditActions.VERIFY_FILE_TRIGGERED,
                    actor_id=None,
                    resource_type="sample_files",
                    resource_id=str(file_id),
                    before={"storage_state": "BROKEN"},
                    after={"storage_state": recovered_state},
                    metadata={"uri": row["uri"], "outcome": "RECOVERED"},
                    db_conn=db,
                )
            else:
                execute_write(
                    """
                    UPDATE sample_files
                    SET last_verified_at = NOW(),
                        last_verification_status = 'OK'
                    WHERE id = :id
                    """,
                    {"id": file_id},
                    conn=db,
                )
                log_audit(
                    action=AuditActions.VERIFY_FILE_TRIGGERED,
                    actor_id=None,
                    resource_type="sample_files",
                    resource_id=str(file_id),
                    before=None,
                    after=None,
                    metadata={"uri": row["uri"], "outcome": "OK"},
                    db_conn=db,
                )
        else:
            new_status, count = _next_failure_status(row.get("last_verification_status"), kind)
            if count >= threshold and row["storage_state"] != "BROKEN":
                execute_write(
                    """
                    UPDATE sample_files
                    SET storage_state = 'BROKEN',
                        last_verified_at = NOW(),
                        last_verification_status = :s
                    WHERE id = :id
                    """,
                    {"s": new_status, "id": file_id},
                    conn=db,
                )
                _emit_broken_audit_and_notifications(row, new_status, db)
            else:
                execute_write(
                    """
                    UPDATE sample_files
                    SET last_verified_at = NOW(),
                        last_verification_status = :s
                    WHERE id = :id
                    """,
                    {"s": new_status, "id": file_id},
                    conn=db,
                )
            log_audit(
                action=AuditActions.VERIFY_FILE_TRIGGERED,
                actor_id=None,
                resource_type="sample_files",
                resource_id=str(file_id),
                before=None,
                after=None,
                metadata={
                    "uri": row["uri"],
                    "outcome": "FAILED",
                    "kind": kind,
                    "status": new_status,
                    "count": count,
                },
                db_conn=db,
            )

    refreshed = execute_query(
        """
        SELECT id, uri, storage_state, last_verification_status, last_verified_at
        FROM sample_files
        WHERE id = :id
        """,
        {"id": file_id},
    )
    out = dict(refreshed[0])
    return {
        "file_id": out["id"],
        "uri": out["uri"],
        "storage_state": out["storage_state"],
        "last_verification_status": out["last_verification_status"],
        "last_verified_at": (
            out["last_verified_at"].isoformat() if out["last_verified_at"] else None
        ),
    }


# Re-export for tests and ergonomic imports.
async def release_embargoed_submissions() -> dict[str, int]:
    """I-2 daily job that promotes EMBARGOED submissions whose
    ``release_date`` has passed to ``RELEASED`` and notifies the
    creator. Idempotent — running twice is a no-op the second time.
    """
    released_ids: list[int] = []
    with get_db() as db:
        rows = execute_query(
            """
            SELECT id, created_by_user_id, title FROM submissions
             WHERE status = 'EMBARGOED'
               AND release_date <= CURRENT_DATE
               AND is_deleted = FALSE
            """,
            conn=db,
        )
        for row in rows:
            sid = row["id"]
            execute_write(
                "UPDATE submissions SET status = 'RELEASED' WHERE id = :id",
                {"id": sid},
                conn=db,
            )
            log_audit(
                action="SUBMISSION_RELEASED",
                actor_id=None,
                resource_type="submission",
                resource_id=str(sid),
                before={"status": "EMBARGOED"},
                after={"status": "RELEASED"},
                metadata={"job": "release_embargoed_submissions"},
                db_conn=db,
            )
            create_notification(
                recipient_id=row["created_by_user_id"],
                event_type="SUBMISSION_RELEASED",
                title=f"Submission released: {row['title']}",
                body="Embargo period has ended. The submission is now public.",
                resource_type="submission",
                resource_id=str(sid),
                action_url=f"/submissions/{sid}",
                db_conn=db,
            )
            released_ids.append(sid)
    logger.info("release_embargoed_submissions: released %d", len(released_ids))
    return {"released": len(released_ids)}


async def cleanup_expired_import_sessions() -> dict[str, int]:
    """I-1 hourly cleanup for import_sessions.

    Two sweeps:

    1. Expired in-progress sessions (``expires_at < NOW()``) are
       deleted outright — file bytes are too large to leave in the
       table indefinitely.
    2. Terminal-status (``imported`` / ``abandoned``) sessions older
       than 7 days are deleted. We keep recent terminal rows around
       so the UI can show "you imported X 3 days ago", but not
       forever.

    Idempotent: running twice produces the same final state. The
    audit log records counts so operators can see the working set
    over time.
    """
    deleted_expired = 0
    deleted_old_terminal = 0
    with get_db() as db:
        rows = execute_write(
            "DELETE FROM import_sessions "
            "WHERE status = 'in_progress' AND expires_at < NOW() "
            "RETURNING id",
            conn=db,
        )
        deleted_expired = len(rows)
        rows = execute_write(
            "DELETE FROM import_sessions "
            "WHERE status IN ('imported', 'abandoned') "
            "AND created_at < NOW() - INTERVAL '7 days' "
            "RETURNING id",
            conn=db,
        )
        deleted_old_terminal = len(rows)
        log_audit(
            action="CLEANUP_IMPORT_SESSIONS",
            actor_id=None,
            resource_type="import_sessions",
            resource_id="*",
            before=None,
            after={
                "deleted_expired": deleted_expired,
                "deleted_old_terminal": deleted_old_terminal,
            },
            metadata={"job": "cleanup_expired_import_sessions"},
            db_conn=db,
        )
    logger.info(
        "cleanup_expired_import_sessions: expired=%d, terminal=%d",
        deleted_expired,
        deleted_old_terminal,
    )
    return {
        "deleted_expired": deleted_expired,
        "deleted_old_terminal": deleted_old_terminal,
    }


__all__ = [
    "cleanup_expired_import_sessions",
    "compute_full_content_hash",
    "get_promote_job_status",
    "promote_file_storage",
    "release_embargoed_submissions",
    "run_access_request_job",
    "run_scrubber_queue_job",
    "verify_file_references",
    "verify_sample_file",
    "FULL_HASH_CHUNK_SIZE",
]
