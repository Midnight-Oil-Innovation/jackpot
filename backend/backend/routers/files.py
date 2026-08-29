# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""sample_files-centric API surface for the P0f file_references model.

Phase P0f F-10 added the read-side ``/broken`` listing for the
operator dashboard. Phase P0f F-9 extends this router with the
write-side ``promote`` endpoint, single-row ``GET``, list/filter
``GET``, ``verify`` endpoint, and a job-status endpoint the CLI
``--wait`` flag polls.

See ``spec.md`` Phase P0f Specification, Critical Rules 4 (audit on
state change), 22 (background jobs in ``backend/jobs.py``), 23
(pagination via ``backend/pagination.py``), 24 (response envelopes
via ``backend/responses.py``), 57 (no copy on ingest), 58
(sample_files is the dedup primitive).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.audit import AuditActions, log_audit
from backend.auth.guards import get_current_user, get_user_lab_membership
from backend.database import execute_query, get_db_dep
from backend.pagination import paginate
from backend.permissions import visibility_sql_clause
from backend.responses import error, success, success_list

router = APIRouter(prefix="/api/v1/files", tags=["files"])


# Verification statuses written by ``verify_file_references`` (F-5).
# Listed here so the broken-files endpoint can validate the
# ``status_filter`` query parameter rather than passing arbitrary
# strings into the SQL.
_VERIFICATION_STATUSES: frozenset[str] = frozenset(
    {
        "MISSING",
        "MISSING_2",
        "MISSING_3",
        "READ_ERROR",
        "READ_ERROR_2",
        "READ_ERROR_3",
        "SIZE_CHANGED",
    }
)

# Phase P0f F-9: promotable storage states. ``EXTERNAL`` and
# ``MIRRORED`` can promote; ``MANAGED`` is the terminal target;
# ``BROKEN`` and ``STAGED`` reject promotion outright.
_VALID_TARGET_STATES: frozenset[str] = frozenset({"MANAGED", "MIRRORED"})
_VALID_RETENTION_POLICIES: frozenset[str] = frozenset({"STANDARD", "LONG_TERM", "EPHEMERAL"})
_PROMOTABLE_FROM_STATES: frozenset[str] = frozenset({"EXTERNAL", "MIRRORED"})
_LISTABLE_STORAGE_STATES: frozenset[str] = frozenset(
    {"EXTERNAL", "MANAGED", "MIRRORED", "STAGED", "BROKEN"}
)
_LIST_SORT_COLUMNS: frozenset[str] = frozenset(
    {"first_seen_at", "last_verified_at", "file_size_bytes", "id"}
)


def _serialise(row: dict) -> dict:
    out = dict(row)
    for k, v in out.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
    return out


def _load_file_row_for_user(file_id: int, user: dict, db) -> dict | None:
    """Fetch a sample_files row scoped to the caller's visibility.

    The visibility ladder is the same one ``visibility_sql_clause``
    enforces for the samples list — owner / lab / project membership /
    approved access request / active grant / PUBLIC / DISCOVERABLE.
    Returns the row when visible, ``None`` otherwise. The caller maps
    ``None`` to ``FILE_NOT_FOUND`` (404) without distinguishing
    "doesn't exist" from "not visible to you", so the row presence
    isn't leaked across access boundaries.
    """
    vis_clause, vis_params = visibility_sql_clause(user)
    params: dict = {"id": file_id}
    params.update(vis_params)
    rows = execute_query(
        f"""
        SELECT sf.id, sf.uri, sf.alternate_uris, sf.original_uri,
               sf.filename, sf.file_type, sf.file_size_bytes,
               sf.head64k_hash, sf.tail64k_hash, sf.content_hash,
               sf.storage_state, sf.library_layout, sf.read_direction,
               sf.first_seen_at, sf.last_verified_at,
               sf.last_verification_status, sf.retention_policy,
               sf.staged_for_run_id, sf.ingest_method,
               sf.sample_id_fk, s.lab_id, s.project_id
          FROM sample_files sf
          JOIN samples s ON s.id = sf.sample_id_fk
         WHERE sf.id = :id
           AND COALESCE(sf.is_archived, FALSE) = FALSE
           AND COALESCE(s.is_archived, FALSE) = FALSE
           AND {vis_clause}
         LIMIT 1
        """,
        params,
        conn=db,
    )
    return rows[0] if rows else None


def _samples_for_file(file_id: int, user: dict, db) -> list[dict]:
    """Return the list of (visible) samples that reference ``file_id``.

    Currently sample_files has a single ``sample_id_fk``, so the list
    is at most one row. Returned as a list to keep the response shape
    forward-compatible when the dedup model evolves into a join table.
    """
    vis_clause, vis_params = visibility_sql_clause(user)
    params: dict = {"id": file_id}
    params.update(vis_params)
    rows = execute_query(
        f"""
        SELECT s.id, s.sample_id, s.project_id, s.lab_id
          FROM samples s
          JOIN sample_files sf ON sf.sample_id_fk = s.id
         WHERE sf.id = :id
           AND COALESCE(s.is_archived, FALSE) = FALSE
           AND {vis_clause}
        """,
        params,
        conn=db,
    )
    return [_serialise(r) for r in rows]


# ── F-10: GET /broken (existing) ──────────────────────────────────────────


@router.get("/broken")
def list_broken_files(
    request: Request,
    project_id: int | None = None,
    lab_id: int | None = None,
    status_filter: str | None = None,
    page: int = 1,
    per_page: int = Query(50, ge=1, le=500),
    sort_by: str = "last_verified_at",
    sort_dir: str = "desc",
    db=Depends(get_db_dep),  # noqa: B008
):
    """List ``sample_files`` rows in the ``BROKEN`` storage state.

    Phase P0f F-10. Powers the broken-files admin page. Lab access
    scoping uses the same ``visibility_sql_clause`` ladder as the
    samples list endpoint, so the user only sees broken files for
    samples they could otherwise see in /samples/.
    """
    user = get_current_user(request)

    vis_clause, vis_params = visibility_sql_clause(user)
    where: list[str] = [
        "sf.is_archived = FALSE",
        "sf.storage_state = 'BROKEN'",
        "s.is_archived = FALSE",
        vis_clause,
    ]
    params: dict = dict(vis_params)

    if project_id is not None:
        where.append("s.project_id = :project_id")
        params["project_id"] = project_id
    if lab_id is not None:
        where.append("s.lab_id = :lab_id")
        params["lab_id"] = lab_id
    if status_filter is not None:
        if status_filter not in _VERIFICATION_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid status_filter {status_filter!r}; must be one of "
                    f"{sorted(_VERIFICATION_STATUSES)}."
                ),
            )
        where.append("sf.last_verification_status = :status_filter")
        params["status_filter"] = status_filter

    where_sql = " AND ".join(where)
    base_query = f"""
        SELECT
            sf.id AS sample_files_id,
            sf.uri,
            sf.filename,
            sf.file_size_bytes,
            sf.last_verification_status,
            sf.last_verified_at,
            sf.first_seen_at,
            sf.storage_state,
            s.id AS sample_id_int,
            s.sample_id,
            s.lab_id,
            s.project_id
          FROM sample_files sf
          JOIN samples s ON s.id = sf.sample_id_fk
         WHERE {where_sql}
    """
    results, total = paginate(
        base_query,
        params,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return success_list(
        data=[_serialise(r) for r in results],
        page=page,
        per_page=per_page,
        total=total,
    )


# ── F-9: GET / (paginated, filterable) ────────────────────────────────────


@router.get("/")
def list_files(
    request: Request,
    storage_state: str | None = None,
    sample_id: int | None = None,
    project_id: int | None = None,
    page: int = 1,
    per_page: int = Query(50, ge=1, le=500),
    sort_by: str = "first_seen_at",
    sort_dir: str = "desc",
    db=Depends(get_db_dep),  # noqa: B008
):
    """Paginated, filterable list of ``sample_files`` rows.

    Phase P0f F-9. Filters: ``storage_state`` (one of the five enum
    values), ``sample_id`` (numeric ``samples.id``), ``project_id``.
    Visibility is scoped via :func:`visibility_sql_clause`. The
    ``/broken`` endpoint is the listing shorthand for ``BROKEN`` rows
    and remains in place for backward compatibility.
    """
    user = get_current_user(request)
    if storage_state is not None and storage_state not in _LISTABLE_STORAGE_STATES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid storage_state {storage_state!r}; must be one of "
                f"{sorted(_LISTABLE_STORAGE_STATES)}."
            ),
        )
    if sort_by not in _LIST_SORT_COLUMNS:
        raise HTTPException(
            status_code=422,
            detail=(f"Invalid sort_by {sort_by!r}; must be one of {sorted(_LIST_SORT_COLUMNS)}."),
        )

    vis_clause, vis_params = visibility_sql_clause(user)
    where: list[str] = [
        "sf.is_archived = FALSE",
        "s.is_archived = FALSE",
        vis_clause,
    ]
    params: dict = dict(vis_params)
    if storage_state is not None:
        where.append("sf.storage_state = :state")
        params["state"] = storage_state
    if sample_id is not None:
        where.append("sf.sample_id_fk = :sample_id")
        params["sample_id"] = sample_id
    if project_id is not None:
        where.append("s.project_id = :project_id")
        params["project_id"] = project_id

    where_sql = " AND ".join(where)
    base_query = f"""
        SELECT
            sf.id,
            sf.uri,
            sf.filename,
            sf.file_type,
            sf.file_size_bytes,
            sf.storage_state,
            sf.last_verified_at,
            sf.last_verification_status,
            sf.first_seen_at,
            s.id AS sample_id_int,
            s.sample_id,
            s.project_id,
            s.lab_id
          FROM sample_files sf
          JOIN samples s ON s.id = sf.sample_id_fk
         WHERE {where_sql}
    """
    results, total = paginate(
        base_query,
        params,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return success_list(
        data=[_serialise(r) for r in results],
        page=page,
        per_page=per_page,
        total=total,
    )


# ── F-9: GET /{file_id} ────────────────────────────────────────────────────


@router.get("/{file_id}")
def get_file(
    file_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    """Retrieve a single ``sample_files`` row plus the referencing samples."""
    user = get_current_user(request)
    file_row = _load_file_row_for_user(file_id, user, db)
    if not file_row:
        return error("FILE_NOT_FOUND", f"File {file_id} not found.", status_code=404)
    samples = _samples_for_file(file_id, user, db)
    payload = _serialise(file_row)
    payload["samples"] = samples
    return success(data=payload)


# ── F-9: POST /{file_id}/promote ──────────────────────────────────────────


class _PromoteRequest(BaseModel):
    """Request body for promote.

    ``to`` is the only required field; ``retention_policy`` defaults
    to ``STANDARD``. Both are validated up-front against the
    project-wide allowlist before scheduling the copy job.
    """

    to: str = Field(..., description="Target storage_state: MANAGED or MIRRORED.")
    retention_policy: str | None = Field(
        default="STANDARD",
        description="STANDARD | LONG_TERM | EPHEMERAL.",
    )


def _new_promote_job_id(file_id: int) -> str:
    """Build a stable, sortable job id for the in-memory tracker."""
    iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return f"promote_{file_id}_{iso}"


def _estimate_seconds(file_row: dict) -> int:
    """Rough completion estimate: ~100 MB/sec, floor of 1 second.

    Documented in the response so callers know to treat it as
    advisory. A real implementation would consult per-deployment
    bandwidth telemetry; F-9 keeps it predictable and small so the
    UI can show a useful progress hint without misleading the user.
    """
    size = file_row.get("file_size_bytes") or 0
    return max(1, int(size // (100 * 1024 * 1024)))


def _validate_promote_request(payload: _PromoteRequest) -> tuple[str, str, JSONResponse | None]:
    """Normalise + validate ``to``/``retention_policy``. Returns (target, retention, err)."""
    target = (payload.to or "").strip().upper()
    retention = (payload.retention_policy or "STANDARD").strip().upper()

    if target not in _VALID_TARGET_STATES:
        return (
            target,
            retention,
            error(
                "INVALID_TRANSITION",
                f"Target state must be one of {sorted(_VALID_TARGET_STATES)}; got {target!r}.",
                status_code=422,
            ),
        )
    if retention not in _VALID_RETENTION_POLICIES:
        return (
            target,
            retention,
            error(
                "VALIDATION_ERROR",
                (
                    f"Invalid retention_policy {retention!r}; must be one of "
                    f"{sorted(_VALID_RETENTION_POLICIES)}."
                ),
                status_code=422,
            ),
        )
    return target, retention, None


def _authorize_promote(file_id: int, user: dict, db) -> tuple[dict | None, JSONResponse | None]:
    """Load the file (visibility-scoped) and enforce write authority. Returns (file_row, err)."""
    file_row = _load_file_row_for_user(file_id, user, db)
    if not file_row:
        return None, error("FILE_NOT_FOUND", f"File {file_id} not found.", status_code=404)

    # Promotion triggers an expensive storage copy; gate it behind write
    # authority (Lab Director of the file's lab, or Platform Admin) rather
    # than mere read-visibility, matching sample archival in routers/samples.py.
    if not user.get("is_platform_admin"):
        member = get_user_lab_membership(user["id"], file_row["lab_id"])
        if not member or not member.get("is_lab_director"):
            return None, error(
                "ACCESS_DENIED",
                "Lab Director or Platform Admin required to promote files.",
                status_code=403,
            )
    return file_row, None


def _validate_promote_transition(file_id: int, current: str, target: str) -> JSONResponse | None:
    """Reject storage_state transitions the promote endpoint doesn't support."""
    if current == "BROKEN":
        return error(
            "INVALID_TRANSITION",
            "Cannot promote a BROKEN file. Re-register the file from a working URI first.",
            status_code=422,
        )
    if current == "STAGED":
        return error(
            "INVALID_TRANSITION",
            "STAGED files are run-scoped and auto-cleaned; promotion is not permitted.",
            status_code=422,
        )
    if current == target:
        return error(
            "ALREADY_IN_TARGET_STATE",
            f"File {file_id} is already in storage_state={target}.",
            status_code=409,
        )
    is_mirrored_to_managed = current == "MIRRORED" and target == "MANAGED"
    if current not in _PROMOTABLE_FROM_STATES and not is_mirrored_to_managed:
        # Catches MANAGED → MIRRORED (downgrade) and MANAGED → EXTERNAL.
        return error(
            "INVALID_TRANSITION",
            f"Cannot promote from {current} to {target}.",
            status_code=422,
        )
    return None


def _schedule_promote_job(
    file_id: int, target: str, retention: str, actor_id: int, job_id: str
) -> None:
    """Hand the promote job to the scheduler, or record it directly in test envs."""
    # Schedule via the application's AsyncIOScheduler. The lazy import
    # avoids a circular dependency between main.py and this router
    # (main.py imports the router at module import time).
    from backend.main import scheduler

    if scheduler.running:
        scheduler.add_job(
            _promote_file_storage_wrapper,
            trigger="date",
            run_date=datetime.now(UTC),
            args=[file_id, target, retention, actor_id, job_id],
            id=job_id,
            replace_existing=False,
        )
    else:
        # Test / non-scheduler envs: register the job in the in-memory
        # tracker so the endpoint contract is honoured even when the
        # scheduler isn't running. Tests that exercise the copy path
        # call promote_file_storage directly.
        from backend.jobs import _record_promote_job

        _record_promote_job(job_id, status="QUEUED", file_id=file_id, target_state=target)


@router.post("/{file_id}/promote", status_code=202)
def promote_file(
    file_id: int,
    payload: _PromoteRequest,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    """Schedule a one-shot copy job to promote a file to MANAGED/MIRRORED.

    Phase P0f F-9. Returns 202 immediately with a ``job_id`` the caller
    polls via ``GET /api/v1/files/jobs/{job_id}``. The actual byte copy
    runs in :func:`backend.jobs.promote_file_storage` against the
    application's APScheduler instance.
    """
    user = get_current_user(request)

    target, retention, err = _validate_promote_request(payload)
    if err:
        return err

    file_row, err = _authorize_promote(file_id, user, db)
    if err:
        return err
    assert file_row is not None  # narrowed by `if err: return err` above

    current = file_row["storage_state"]
    err = _validate_promote_transition(file_id, current, target)
    if err:
        return err

    job_id = _new_promote_job_id(file_id)
    estimated_seconds = _estimate_seconds(file_row)
    _schedule_promote_job(file_id, target, retention, user["id"], job_id)

    log_audit(
        action=AuditActions.PROMOTE_FILE,
        actor_id=user["id"],
        resource_type="sample_files",
        resource_id=str(file_id),
        before={"storage_state": current, "uri": file_row["uri"]},
        after={"target_state": target, "job_id": job_id},
        metadata={
            "retention_policy": retention,
            "stage": "QUEUED",
        },
        db_conn=db,
    )

    return success(
        data={
            "file_id": file_id,
            "current_state": current,
            "target_state": target,
            "job_id": job_id,
            "retention_policy": retention,
            "estimated_seconds": estimated_seconds,
            "status": "QUEUED",
        },
        status_code=202,
    )


async def _promote_file_storage_wrapper(
    file_id: int,
    target_state: str,
    retention_policy: str,
    trigger_user_id: int,
    job_id: str,
):
    """Thin async wrapper for APScheduler's ``add_job``.

    APScheduler awaits async callables passed via ``trigger='date'``;
    we keep the wrapper here so that test-time scheduling can be
    swapped out without touching :mod:`backend.jobs`.
    """
    from backend.jobs import promote_file_storage

    return await promote_file_storage(
        file_id=file_id,
        target_state=target_state,
        retention_policy=retention_policy,
        trigger_user_id=trigger_user_id,
        job_id=job_id,
    )


# ── F-9: GET /jobs/{job_id} ───────────────────────────────────────────────


@router.get("/jobs/{job_id}")
def get_promote_job(
    job_id: str,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    """Look up a promotion job's status.

    Phase P0f F-9. Reads from the in-memory tracker in
    :mod:`backend.jobs`. Returns ``404`` when the job is unknown to
    this process, which the CLI ``--wait`` poller treats as transient
    until the per-job timeout expires (handles "scheduled but not yet
    run" and "ran on a sibling instance" the same way).
    """
    user = get_current_user(request)
    from backend.jobs import get_promote_job_status

    entry = get_promote_job_status(job_id)
    if entry is None:
        return error("JOB_NOT_FOUND", f"Job {job_id} not found.", status_code=404)
    # Scope to the file's visibility. The job_id is predictable
    # (promote_{file_id}_{iso}), so without this any authenticated user
    # could read another user's job metadata. Collapse "not visible" into
    # the same 404 as "unknown job" so existence isn't leaked.
    file_id = entry.get("file_id")
    if file_id is None or _load_file_row_for_user(file_id, user, db) is None:
        return error("JOB_NOT_FOUND", f"Job {job_id} not found.", status_code=404)
    out = {"job_id": job_id, **entry}
    return success(data=out)


# ── F-9: POST /{file_id}/verify ───────────────────────────────────────────


@router.post("/{file_id}/verify")
def verify_file_endpoint(
    file_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    """Force a synchronous re-stat of one file.

    Phase P0f F-9. Wraps :func:`backend.jobs.verify_sample_file` so a
    user can clear a stale ``BROKEN`` state immediately after putting
    the file back, instead of waiting for the daily verification job.

    Visibility scoping matches :func:`get_file`: the caller must be
    able to see at least one sample referencing this file.
    """
    user = get_current_user(request)
    file_row = _load_file_row_for_user(file_id, user, db)
    if not file_row:
        return error("FILE_NOT_FOUND", f"File {file_id} not found.", status_code=404)
    from backend.jobs import verify_sample_file

    try:
        result = verify_sample_file(file_id)
    except FileNotFoundError:
        # The visibility check already passed but the row vanished
        # between the two queries — shouldn't normally happen, but the
        # caller sees a clean 404 if it does.
        return error("FILE_NOT_FOUND", f"File {file_id} not found.", status_code=404)
    return success(data=result)
