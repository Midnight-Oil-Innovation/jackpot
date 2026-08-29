"""
Sample-access router — request → approve/deny → grant lifecycle.

Endpoints (all under ``/api/v1/sample-access``):
    POST   /requests                    request access to a DISCOVERABLE sample
    GET    /requests                    list requests, scoped by role
    POST   /requests/{id}/approve       approve (Lab Director or Platform Admin)
    POST   /requests/{id}/deny          deny   (Lab Director or Platform Admin)

Why a separate ``sample_access_grants`` table — the request row records
the conversation (who asked, why, when, what was decided). The grant row
is the durable artefact that actually unlocks reads. Splitting the two
keeps audit history intact when a grant is revoked or expires while
also letting ``can_access_sample()`` answer in a single indexed lookup
without re-deriving "is this APPROVED *and* still inside its window" on
every authz check.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.audit import AuditActions, log_audit
from backend.auth.guards import get_current_user, get_user_lab_membership
from backend.database import execute_query, execute_write, get_db_dep
from backend.notifications import NotificationEvents, create_notification
from backend.pagination import paginate
from backend.responses import error, success, success_list

router = APIRouter(prefix="/api/v1/sample-access", tags=["sample_access"])


# ── Constants ─────────────────────────────────────────────────────────────────

# Per spec.md §5 Session O — auto-approve window for an unanswered request.
AUTO_APPROVE_WINDOW = timedelta(days=7)
# Sharing levels eligible for the request workflow. PRIVATE / LAB samples
# require talking to the Lab Director directly — there is no self-serve
# request path for them.
REQUESTABLE_SHARING_LEVELS = {"DISCOVERABLE"}


# ── Pydantic bodies ───────────────────────────────────────────────────────────


class AccessRequestCreate(BaseModel):
    sample_id: int = Field(..., description="Numeric samples.id (PK), not the textual sample_id.")
    justification: str = Field(..., min_length=10, max_length=4000)
    requested_duration_days: int = Field(..., gt=0, le=365)


class DenyBody(BaseModel):
    denial_reason: str | None = Field(default=None, max_length=2000)


# ── Serialisation ─────────────────────────────────────────────────────────────


def _serialise(row: dict | None) -> dict:
    if not row:
        return {}
    out: dict[str, Any] = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


# ── Helpers ───────────────────────────────────────────────────────────────────


def _fetch_request(request_id: int, db) -> dict | None:
    rows = execute_query(
        "SELECT * FROM sample_access_requests WHERE id = :id LIMIT 1",
        {"id": request_id},
        conn=db,
    )
    return rows[0] if rows else None


def _fetch_sample(sample_id: int, db) -> dict | None:
    rows = execute_query(
        "SELECT * FROM samples WHERE id = :id AND is_archived = FALSE LIMIT 1",
        {"id": sample_id},
        conn=db,
    )
    return rows[0] if rows else None


def _fetch_lab_directors(lab_id: int, db) -> list[dict]:
    return execute_query(
        "SELECT u.id, u.email, u.name FROM lab_membership lm "
        "JOIN users u ON u.id = lm.user_id "
        "WHERE lm.lab_id = :lid AND lm.is_lab_director = TRUE AND u.is_active = TRUE",
        {"lid": lab_id},
        conn=db,
    )


def _is_lab_director_or_admin(user: dict, lab_id: int, db) -> bool:
    if user.get("is_platform_admin"):
        return True
    member = get_user_lab_membership(user["id"], lab_id)
    return bool(member and member.get("is_lab_director"))


# ── POST /requests ────────────────────────────────────────────────────────────


@router.post("/requests", status_code=201)
def create_access_request(
    payload: AccessRequestCreate,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    """Submit an access request against a DISCOVERABLE sample."""
    user = get_current_user(request)
    sample = _fetch_sample(payload.sample_id, db)
    if not sample:
        return error("NOT_FOUND", f"Sample {payload.sample_id} not found.", status_code=404)

    if sample["sharing_level"] not in REQUESTABLE_SHARING_LEVELS:
        return error(
            "ACCESS_DENIED",
            (
                f"Sample sharing_level is {sample['sharing_level']!r}; the "
                "self-serve access workflow only applies to DISCOVERABLE "
                "samples. Contact the owning Lab Director directly for "
                "PRIVATE or LAB samples."
            ),
            status_code=403,
        )

    # Owner cannot request access to their own sample — they already have it.
    if sample["owner_id"] == user["id"]:
        return error(
            "CONFLICT",
            "You already own this sample; no access request needed.",
            status_code=409,
        )

    # Guard against duplicate pending request from the same requester.
    existing = execute_query(
        "SELECT id FROM sample_access_requests "
        "WHERE sample_id = :sid AND requester_id = :uid AND status = 'PENDING' LIMIT 1",
        {"sid": sample["id"], "uid": user["id"]},
        conn=db,
    )
    if existing:
        return error(
            "CONFLICT",
            "You already have a pending access request for this sample.",
            status_code=409,
        )

    rows = execute_write(
        """
        INSERT INTO sample_access_requests
            (sample_id, requester_id, owner_id, status,
             justification, requested_duration_days,
             auto_approve_after, purpose)
        VALUES
            (:sid, :uid, :owner, 'PENDING',
             :just, :dur,
             NOW() + (:days || ' days')::INTERVAL, :just)
        RETURNING *
        """,
        {
            "sid": sample["id"],
            "uid": user["id"],
            "owner": sample["owner_id"],
            "just": payload.justification,
            "dur": payload.requested_duration_days,
            "days": str(AUTO_APPROVE_WINDOW.days),
        },
        conn=db,
    )
    req_row = rows[0]

    # Notify every Lab Director on the owning lab. The Platform Admin path
    # is intentionally a fallback: if no Lab Director exists, notify the
    # sample owner so the request never goes silently ignored.
    directors = _fetch_lab_directors(sample["lab_id"], db)
    recipients = [d["id"] for d in directors] if directors else [sample["owner_id"]]
    title = f"Access request: sample {sample['sample_id']}"
    body = (
        f"{user.get('email', 'A user')} requested access to sample "
        f"{sample['sample_id']} for {payload.requested_duration_days} days."
    )
    action_url = f"/sample-access/requests/{req_row['id']}"
    for recipient_id in recipients:
        create_notification(
            recipient_id=recipient_id,
            event_type=NotificationEvents.ACCESS_REQUEST_SUBMITTED,
            title=title,
            body=body,
            resource_type="sample_access_request",
            resource_id=str(req_row["id"]),
            action_url=action_url,
            db_conn=db,
        )

    log_audit(
        action=AuditActions.CREATE_ACCESS_REQUEST,
        actor_id=user["id"],
        resource_type="sample_access_request",
        resource_id=str(req_row["id"]),
        before=None,
        after=_serialise(req_row),
        metadata={
            "sample_id": sample["id"],
            "sample_external_id": sample["sample_id"],
            "lab_id": sample["lab_id"],
        },
        db_conn=db,
    )
    return success(data=_serialise(req_row), status_code=201)


# ── GET /requests ─────────────────────────────────────────────────────────────


def _resolve_requester_filter_id(requester_id: str | None, user: dict) -> int | None:
    """Translate the ``requester_id`` query param — ``'me'`` or a numeric id."""
    if requester_id is None:
        return None
    if requester_id == "me":
        return user["id"]
    try:
        return int(requester_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="requester_id must be an integer or 'me'."
        ) from exc


def _build_access_request_scope(user: dict, db) -> tuple[str, dict[str, Any]]:
    """Non-admin visibility scope: own requests, plus requests on labs I direct.

    The director_lab_ids subquery tightens the filter at the DB tier so
    non-admins can never accidentally page through other labs' requests
    by omitting filters.
    """
    director_labs = execute_query(
        "SELECT lab_id FROM lab_membership WHERE user_id = :uid AND is_lab_director = TRUE",
        {"uid": user["id"]},
        conn=db,
    )
    director_lab_ids = [r["lab_id"] for r in director_labs]
    params: dict[str, Any] = {"scope_uid": user["id"]}
    if not director_lab_ids:
        return "sar.requester_id = :scope_uid", params

    placeholders = ",".join(f":dl{i}" for i in range(len(director_lab_ids)))
    for i, lid in enumerate(director_lab_ids):
        params[f"dl{i}"] = lid
    return f"(sar.requester_id = :scope_uid OR s.lab_id IN ({placeholders}))", params


@router.get("/requests")
def list_access_requests(
    request: Request,
    status: str | None = Query(default=None),
    lab_id: int | None = Query(default=None),
    requester_id: str | None = Query(
        default=None,
        description="Numeric user id, or 'me' for the current user.",
    ),
    sample_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
    db=Depends(get_db_dep),  # noqa: B008
):
    """List access requests visible to the caller.

    Visibility ladder:
      * Platform Admin       — sees everything.
      * Lab Director         — sees requests targeting their lab.
      * Anyone else          — sees only their own.
    """
    user = get_current_user(request)
    is_admin = bool(user.get("is_platform_admin"))

    # Pagination sorts on `created_at` by default but the underlying
    # column is `requested_at`. Keep the public name and translate.
    if sort_by == "created_at":
        sort_by = "requested_at"

    where: list[str] = []
    params: dict[str, Any] = {}

    if status:
        where.append("sar.status = :status")
        params["status"] = status
    if sample_id is not None:
        where.append("sar.sample_id = :sid")
        params["sid"] = sample_id

    requester_filter_id = _resolve_requester_filter_id(requester_id, user)
    if requester_filter_id is not None:
        where.append("sar.requester_id = :rid")
        params["rid"] = requester_filter_id

    if lab_id is not None:
        where.append("s.lab_id = :lab_id")
        params["lab_id"] = lab_id

    if not is_admin:
        scope, scope_params = _build_access_request_scope(user, db)
        where.append(scope)
        params.update(scope_params)

    where_sql = " AND ".join(where) if where else "TRUE"
    base_query = (
        "SELECT sar.*, s.sample_id AS sample_external_id, s.lab_id AS sample_lab_id "
        "FROM sample_access_requests sar "
        "JOIN samples s ON s.id = sar.sample_id "
        f"WHERE {where_sql}"
    )

    rows, total = paginate(
        base_query,
        params,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return success_list(
        data=[_serialise(r) for r in rows],
        page=page,
        per_page=per_page,
        total=total,
    )


# ── POST /requests/{id}/approve ───────────────────────────────────────────────


@router.post("/requests/{request_id}/approve")
def approve_access_request(
    request_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    req_row = _fetch_request(request_id, db)
    if not req_row:
        return error("NOT_FOUND", f"Access request {request_id} not found.", status_code=404)

    sample = _fetch_sample(req_row["sample_id"], db)
    if not sample:
        return error("NOT_FOUND", "Underlying sample no longer exists.", status_code=404)

    if not _is_lab_director_or_admin(user, sample["lab_id"], db):
        return error(
            "ACCESS_DENIED",
            "Lab Director or Platform Admin required to approve access requests.",
            status_code=403,
        )

    if req_row["status"] != "PENDING":
        return error(
            "CONFLICT",
            f"Request is in status {req_row['status']!r}; only PENDING can be approved.",
            status_code=409,
        )

    duration_days = req_row.get("requested_duration_days") or 90
    updated = execute_write(
        """
        UPDATE sample_access_requests
        SET status = 'APPROVED',
            approved_by_id = :uid,
            approved_at = NOW(),
            reviewed_by_id = :uid,
            reviewed_at = NOW(),
            access_expires_at = NOW() + (:days || ' days')::INTERVAL
        WHERE id = :id
        RETURNING *
        """,
        {"uid": user["id"], "days": str(duration_days), "id": request_id},
        conn=db,
    )
    new_req = updated[0] if updated else req_row

    grant_rows = execute_write(
        """
        INSERT INTO sample_access_grants
            (sample_id, requester_id, request_id, granted_by_id, access_expires_at)
        VALUES
            (:sid, :rid, :req_id, :uid, NOW() + (:days || ' days')::INTERVAL)
        RETURNING *
        """,
        {
            "sid": req_row["sample_id"],
            "rid": req_row["requester_id"],
            "req_id": request_id,
            "uid": user["id"],
            "days": str(duration_days),
        },
        conn=db,
    )
    grant = grant_rows[0] if grant_rows else None

    create_notification(
        recipient_id=req_row["requester_id"],
        event_type=NotificationEvents.ACCESS_REQUEST_APPROVED,
        title=f"Access approved: {sample['sample_id']}",
        body=(
            f"Your access request for sample {sample['sample_id']} was approved. "
            f"Access expires in {duration_days} days."
        ),
        resource_type="sample_access_request",
        resource_id=str(request_id),
        action_url=f"/samples/{sample['id']}",
        db_conn=db,
    )

    log_audit(
        action=AuditActions.APPROVE_ACCESS_REQUEST,
        actor_id=user["id"],
        resource_type="sample_access_request",
        resource_id=str(request_id),
        before=_serialise(req_row),
        after=_serialise(new_req),
        metadata={
            "sample_id": sample["id"],
            "grant_id": grant["id"] if grant else None,
            "duration_days": duration_days,
        },
        db_conn=db,
    )
    return success(
        data={
            "request": _serialise(new_req),
            "grant": _serialise(grant),
        }
    )


# ── POST /requests/{id}/deny ──────────────────────────────────────────────────


@router.post("/requests/{request_id}/deny")
def deny_access_request(
    request_id: int,
    request: Request,
    payload: DenyBody | None = None,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    req_row = _fetch_request(request_id, db)
    if not req_row:
        return error("NOT_FOUND", f"Access request {request_id} not found.", status_code=404)

    sample = _fetch_sample(req_row["sample_id"], db)
    if not sample:
        return error("NOT_FOUND", "Underlying sample no longer exists.", status_code=404)

    if not _is_lab_director_or_admin(user, sample["lab_id"], db):
        return error(
            "ACCESS_DENIED",
            "Lab Director or Platform Admin required to deny access requests.",
            status_code=403,
        )

    if req_row["status"] != "PENDING":
        return error(
            "CONFLICT",
            f"Request is in status {req_row['status']!r}; only PENDING can be denied.",
            status_code=409,
        )

    reason = payload.denial_reason if payload else None
    updated = execute_write(
        """
        UPDATE sample_access_requests
        SET status = 'DENIED',
            denied_by_id = :uid,
            denied_at = NOW(),
            reviewed_by_id = :uid,
            reviewed_at = NOW(),
            denial_reason = :reason
        WHERE id = :id
        RETURNING *
        """,
        {"uid": user["id"], "reason": reason, "id": request_id},
        conn=db,
    )
    new_req = updated[0] if updated else req_row

    create_notification(
        recipient_id=req_row["requester_id"],
        event_type=NotificationEvents.ACCESS_REQUEST_DENIED,
        title=f"Access denied: {sample['sample_id']}",
        body=(
            f"Your access request for sample {sample['sample_id']} was denied."
            + (f" Reason: {reason}" if reason else "")
        ),
        resource_type="sample_access_request",
        resource_id=str(request_id),
        action_url=f"/sample-access/requests/{request_id}",
        db_conn=db,
    )

    log_audit(
        action=AuditActions.DENY_ACCESS_REQUEST,
        actor_id=user["id"],
        resource_type="sample_access_request",
        resource_id=str(request_id),
        before=_serialise(req_row),
        after=_serialise(new_req),
        metadata={"sample_id": sample["id"], "denial_reason": reason},
        db_conn=db,
    )
    return success(data=_serialise(new_req))
