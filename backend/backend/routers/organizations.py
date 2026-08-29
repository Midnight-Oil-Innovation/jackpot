from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field

from backend.audit import AuditActions, log_audit
from backend.auth.guards import get_current_user, require_capability
from backend.database import execute_query, execute_write, get_db_dep
from backend.pagination import paginate
from backend.responses import error, success, success_list, success_message

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])


class OrgCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=255)
    default_approve_analytical_dataset_requests: bool = False
    org_type: str | None = None
    contact_email: EmailStr | None = None


class OrgUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    default_approve_analytical_dataset_requests: bool | None = None
    active: bool | None = None


_DB_COLUMNS = {"display_name", "default_approve_analytical_dataset_requests", "active"}


@router.post("/", status_code=201)
def create_organization(
    payload: OrgCreate,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_capability("org:manage")(user)

    existing = execute_query(
        "SELECT id FROM organizations WHERE display_name = :n LIMIT 1",
        {"n": payload.display_name},
        conn=db,
    )
    if existing:
        return error(
            "CONFLICT",
            f"Organization '{payload.display_name}' already exists.",
            status_code=409,
        )

    rows = execute_write(
        """
        INSERT INTO organizations
            (display_name, default_approve_analytical_dataset_requests, active)
        VALUES (:display_name, :default_approve, TRUE)
        RETURNING *
        """,
        {
            "display_name": payload.display_name,
            "default_approve": payload.default_approve_analytical_dataset_requests,
        },
        conn=db,
    )
    org = rows[0]
    log_audit(
        action=AuditActions.CREATE_ORG,
        actor_id=user["id"],
        resource_type="organization",
        resource_id=str(org["id"]),
        before=None,
        after=_serialise(org),
        metadata=None,
        db_conn=db,
    )
    return success(data=_serialise(org), status_code=201)


@router.get("/")
def list_organizations(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    search: str | None = None,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_capability("org:manage")(user)

    base_query = "SELECT * FROM organizations"
    params: dict = {}
    if search:
        base_query += " WHERE display_name ILIKE :search"
        params["search"] = f"%{search}%"

    rows, total = paginate(
        query=base_query,
        params=params,
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


@router.get("/{org_id}")
def get_organization(
    org_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    rows = execute_query(
        "SELECT * FROM organizations WHERE id = :id LIMIT 1",
        {"id": org_id},
        conn=db,
    )
    if not rows:
        return error("NOT_FOUND", f"Organization {org_id} not found.", status_code=404)

    if not user.get("is_platform_admin") and user.get("organization_id") != org_id:
        return error(
            "ACCESS_DENIED",
            "You do not have access to this organization.",
            status_code=403,
        )
    return success(data=_serialise(rows[0]))


@router.patch("/{org_id}")
def update_organization(
    org_id: int,
    payload: OrgUpdate,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_capability("org:manage")(user)

    current = execute_query(
        "SELECT * FROM organizations WHERE id = :id LIMIT 1",
        {"id": org_id},
        conn=db,
    )
    if not current:
        return error("NOT_FOUND", f"Organization {org_id} not found.", status_code=404)
    before = current[0]

    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates if k in _DB_COLUMNS)
    if not set_clause:
        raise HTTPException(status_code=400, detail="No updatable fields supplied.")

    params = {k: v for k, v in updates.items() if k in _DB_COLUMNS}
    params["id"] = org_id
    rows = execute_write(
        f"UPDATE organizations SET {set_clause} WHERE id = :id RETURNING *",
        params,
        conn=db,
    )
    after = rows[0]

    log_audit(
        action=AuditActions.UPDATE_ORG,
        actor_id=user["id"],
        resource_type="organization",
        resource_id=str(org_id),
        before=_serialise(before),
        after=_serialise(after),
        metadata=None,
        db_conn=db,
    )
    return success(data=_serialise(after))


@router.delete("/{org_id}")
def deactivate_organization(
    org_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_capability("org:manage")(user)

    current = execute_query(
        "SELECT * FROM organizations WHERE id = :id LIMIT 1",
        {"id": org_id},
        conn=db,
    )
    if not current:
        return error("NOT_FOUND", f"Organization {org_id} not found.", status_code=404)
    before = current[0]

    rows = execute_write(
        "UPDATE organizations SET active = FALSE WHERE id = :id RETURNING *",
        {"id": org_id},
        conn=db,
    )
    after = rows[0]

    log_audit(
        action=AuditActions.UPDATE_ORG,
        actor_id=user["id"],
        resource_type="organization",
        resource_id=str(org_id),
        before=_serialise(before),
        after=_serialise(after),
        metadata={"soft_delete": True},
        db_conn=db,
    )
    return success_message("Organization deactivated.")


def _serialise(row: dict) -> dict:
    result = dict(row)
    for k, v in result.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
    return result
