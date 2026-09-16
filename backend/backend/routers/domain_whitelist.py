from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from backend.audit import AuditActions, log_audit
from backend.auth.guards import get_current_user, require_capability
from backend.database import execute_query, execute_write, get_db_dep
from backend.pagination import paginate
from backend.responses import error, success, success_list, success_message

router = APIRouter(prefix="/api/v1/domain-whitelist", tags=["domain_whitelist"])


class DomainCreate(BaseModel):
    domain: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)


def _serialise(row: dict) -> dict:
    result = dict(row)
    for k, v in result.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
    return result


@router.get("/")
def list_domains(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort_by: str = "created_at",
    sort_dir: str = "asc",
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_capability("whitelist:manage")(user)

    rows, total = paginate(
        query="SELECT * FROM domain_whitelist",
        params={},
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


@router.post("/", status_code=201)
def add_domain(
    payload: DomainCreate,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_capability("whitelist:manage")(user)

    normalised = payload.domain.strip().lower()
    if not normalised:
        return error("VALIDATION_ERROR", "Domain must not be empty.", status_code=422)

    existing = execute_query(
        "SELECT id FROM domain_whitelist WHERE domain = :d LIMIT 1",
        {"d": normalised},
        conn=db,
    )
    if existing:
        return error(
            "CONFLICT",
            f"Domain '{normalised}' is already whitelisted.",
            status_code=409,
        )

    # The SELECT above answers the ordinary case with a clean 409. It cannot
    # answer the concurrent one: two admins adding the same domain both pass the
    # check, and `domain` is TEXT NOT NULL UNIQUE, so the loser hits the
    # constraint. Catching it here turns that into the same 409 rather than an
    # unhandled IntegrityError surfacing as a 500 — the constraint is the real
    # arbiter, the SELECT is just the fast path with a better message.
    try:
        rows = execute_write(
            """
            INSERT INTO domain_whitelist (domain, description)
            VALUES (:domain, :description)
            RETURNING *
            """,
            {"domain": normalised, "description": payload.description or ""},
            conn=db,
        )
    except IntegrityError:
        # Nothing after this needs the session — the handler returns — so this
        # rollback is currently unobservable, and removing it leaves every test
        # green. It stays because the alternative is a landmine: after a failed
        # statement the session is in InFailedSqlTransaction, so the first
        # person to audit the conflict or read anything here gets an
        # InternalError from a line that looks innocent.
        db.rollback()
        return error(
            "CONFLICT",
            f"Domain '{normalised}' is already whitelisted.",
            status_code=409,
        )
    row = rows[0]
    log_audit(
        action=AuditActions.ADD_WHITELIST_DOMAIN,
        actor_id=user["id"],
        resource_type="domain_whitelist",
        resource_id=str(row["id"]),
        before=None,
        after=_serialise(row),
        metadata=None,
        db_conn=db,
    )
    return success(data=_serialise(row), status_code=201)


@router.delete("/{domain_id}")
def remove_domain(
    domain_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_capability("whitelist:manage")(user)

    before_rows = execute_query(
        "SELECT * FROM domain_whitelist WHERE id = :id LIMIT 1",
        {"id": domain_id},
        conn=db,
    )
    if not before_rows:
        return error("NOT_FOUND", f"Whitelist entry {domain_id} not found.", status_code=404)
    before = before_rows[0]

    execute_write(
        "DELETE FROM domain_whitelist WHERE id = :id",
        {"id": domain_id},
        conn=db,
    )
    log_audit(
        action=AuditActions.REMOVE_WHITELIST_DOMAIN,
        actor_id=user["id"],
        resource_type="domain_whitelist",
        resource_id=str(domain_id),
        before=_serialise(before),
        after=None,
        metadata=None,
        db_conn=db,
    )
    return success_message(f"Domain '{before['domain']}' removed from whitelist.")
