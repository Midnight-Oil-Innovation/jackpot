from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.audit import AuditActions, log_audit
from backend.auth.guards import (
    get_current_user,
    get_user_lab_membership,
    require_capability,
)
from backend.database import execute_query, execute_write, get_db_dep
from backend.pagination import paginate
from backend.responses import error, success, success_list, success_message

router = APIRouter(prefix="/api/v1/labs", tags=["labs"])


class LabCreate(BaseModel):
    organization_id: int
    display_name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    gcs_bucket: str | None = None
    project_prefix: str | None = None


class LabUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    gcs_bucket: str | None = None
    project_prefix: str | None = None
    build_status: str | None = None
    active: bool | None = None


class MemberAdd(BaseModel):
    user_id: int
    permission_group_id: int
    is_lab_director: bool = False


class MemberUpdate(BaseModel):
    permission_group_id: int | None = None
    is_lab_director: bool | None = None


_LAB_COLUMNS = {
    "display_name",
    "description",
    "gcs_bucket",
    "project_prefix",
    "build_status",
    "active",
}


def _serialise(row: dict) -> dict:
    result = dict(row)
    for k, v in result.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
    return result


@router.post("/", status_code=201)
def create_lab(
    payload: LabCreate,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_capability("org:manage")(user)

    org = execute_query(
        "SELECT id FROM organizations WHERE id = :id LIMIT 1",
        {"id": payload.organization_id},
        conn=db,
    )
    if not org:
        return error(
            "NOT_FOUND",
            f"Organization {payload.organization_id} not found.",
            status_code=404,
        )

    rows = execute_write(
        """
        INSERT INTO labs
            (organization_id, display_name, description,
             gcs_bucket, project_prefix, active, created_by_id)
        VALUES (:org_id, :display_name, :description,
                :gcs_bucket, :project_prefix, TRUE, :created_by)
        RETURNING *
        """,
        {
            "org_id": payload.organization_id,
            "display_name": payload.display_name,
            "description": payload.description,
            "gcs_bucket": payload.gcs_bucket,
            "project_prefix": payload.project_prefix,
            "created_by": user["id"],
        },
        conn=db,
    )
    lab = rows[0]
    log_audit(
        action=AuditActions.CREATE_LAB,
        actor_id=user["id"],
        resource_type="lab",
        resource_id=str(lab["id"]),
        before=None,
        after=_serialise(lab),
        metadata=None,
        db_conn=db,
    )
    return success(data=_serialise(lab), status_code=201)


@router.get("/")
def list_labs(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    organization_id: int | None = None,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)

    if user.get("is_platform_admin"):
        base_query = "SELECT * FROM labs"
        params: dict = {}
        if organization_id is not None:
            base_query += " WHERE organization_id = :org_id"
            params["org_id"] = organization_id
    else:
        base_query = (
            "SELECT l.* FROM labs l "
            "JOIN lab_membership lm ON lm.lab_id = l.id "
            "WHERE lm.user_id = :uid"
        )
        params = {"uid": user["id"]}
        if organization_id is not None:
            base_query += " AND l.organization_id = :org_id"
            params["org_id"] = organization_id

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


@router.get("/{lab_id}")
def get_lab(
    lab_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    rows = execute_query(
        "SELECT * FROM labs WHERE id = :id LIMIT 1",
        {"id": lab_id},
        conn=db,
    )
    if not rows:
        return error("NOT_FOUND", f"Lab {lab_id} not found.", status_code=404)

    if not user.get("is_platform_admin") and not get_user_lab_membership(user["id"], lab_id):
        return error(
            "ACCESS_DENIED",
            "You are not a member of this lab.",
            status_code=403,
        )
    return success(data=_serialise(rows[0]))


@router.patch("/{lab_id}")
def update_lab(
    lab_id: int,
    payload: LabUpdate,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_capability("org:manage")(user, lab_id=lab_id)

    current = execute_query(
        "SELECT * FROM labs WHERE id = :id LIMIT 1",
        {"id": lab_id},
        conn=db,
    )
    if not current:
        return error("NOT_FOUND", f"Lab {lab_id} not found.", status_code=404)
    before = current[0]

    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates if k in _LAB_COLUMNS)
    if not set_clause:
        raise HTTPException(status_code=400, detail="No updatable fields supplied.")

    params = {k: v for k, v in updates.items() if k in _LAB_COLUMNS}
    params["id"] = lab_id
    rows = execute_write(
        f"UPDATE labs SET {set_clause} WHERE id = :id RETURNING *",
        params,
        conn=db,
    )
    after = rows[0]

    log_audit(
        action=AuditActions.UPDATE_LAB,
        actor_id=user["id"],
        resource_type="lab",
        resource_id=str(lab_id),
        before=_serialise(before),
        after=_serialise(after),
        metadata=None,
        db_conn=db,
    )
    return success(data=_serialise(after))


@router.delete("/{lab_id}")
def deactivate_lab(
    lab_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_capability("org:manage")(user)

    current = execute_query(
        "SELECT * FROM labs WHERE id = :id LIMIT 1",
        {"id": lab_id},
        conn=db,
    )
    if not current:
        return error("NOT_FOUND", f"Lab {lab_id} not found.", status_code=404)
    before = current[0]

    rows = execute_write(
        "UPDATE labs SET active = FALSE WHERE id = :id RETURNING *",
        {"id": lab_id},
        conn=db,
    )
    after = rows[0]

    log_audit(
        action=AuditActions.UPDATE_LAB,
        actor_id=user["id"],
        resource_type="lab",
        resource_id=str(lab_id),
        before=_serialise(before),
        after=_serialise(after),
        metadata={"soft_delete": True},
        db_conn=db,
    )
    return success_message("Lab deactivated.")


@router.get("/{lab_id}/members")
def list_members(
    lab_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_capability("user:manage")(user, lab_id=lab_id)

    lab = execute_query(
        "SELECT id FROM labs WHERE id = :id LIMIT 1",
        {"id": lab_id},
        conn=db,
    )
    if not lab:
        return error("NOT_FOUND", f"Lab {lab_id} not found.", status_code=404)

    rows = execute_query(
        """
        SELECT lm.id AS membership_id, lm.user_id, lm.lab_id,
               lm.permission_group_id, lm.is_lab_director,
               lm.granted_at,
               u.email, u.name,
               pg.name AS permission_group_name
        FROM lab_membership lm
        JOIN users u ON u.id = lm.user_id
        JOIN permission_groups pg ON pg.id = lm.permission_group_id
        WHERE lm.lab_id = :lid
        ORDER BY lm.granted_at ASC
        """,
        {"lid": lab_id},
        conn=db,
    )
    return success(data=[_serialise(r) for r in rows])


@router.post("/{lab_id}/members", status_code=201)
def add_member(
    lab_id: int,
    payload: MemberAdd,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_capability("user:manage")(user, lab_id=lab_id)

    lab = execute_query(
        "SELECT id FROM labs WHERE id = :id LIMIT 1",
        {"id": lab_id},
        conn=db,
    )
    if not lab:
        return error("NOT_FOUND", f"Lab {lab_id} not found.", status_code=404)

    target = execute_query(
        "SELECT id FROM users WHERE id = :id AND is_active = TRUE LIMIT 1",
        {"id": payload.user_id},
        conn=db,
    )
    if not target:
        return error(
            "NOT_FOUND",
            f"User {payload.user_id} not found.",
            status_code=404,
        )

    pg = execute_query(
        "SELECT id FROM permission_groups WHERE id = :id LIMIT 1",
        {"id": payload.permission_group_id},
        conn=db,
    )
    if not pg:
        return error(
            "NOT_FOUND",
            f"Permission group {payload.permission_group_id} not found.",
            status_code=404,
        )

    existing = execute_query(
        "SELECT id FROM lab_membership WHERE user_id = :uid AND lab_id = :lid LIMIT 1",
        {"uid": payload.user_id, "lid": lab_id},
        conn=db,
    )
    if existing:
        return error(
            "CONFLICT",
            f"User {payload.user_id} is already a member of lab {lab_id}.",
            status_code=409,
        )

    rows = execute_write(
        """
        INSERT INTO lab_membership
            (user_id, lab_id, permission_group_id, is_lab_director, granted_by_id)
        VALUES (:uid, :lid, :pg, :director, :granted_by)
        RETURNING *
        """,
        {
            "uid": payload.user_id,
            "lid": lab_id,
            "pg": payload.permission_group_id,
            "director": payload.is_lab_director,
            "granted_by": user["id"],
        },
        conn=db,
    )
    membership = rows[0]

    log_audit(
        action=AuditActions.ADD_LAB_MEMBER,
        actor_id=user["id"],
        resource_type="lab_membership",
        resource_id=str(membership["id"]),
        before=None,
        after=_serialise(membership),
        metadata={"lab_id": lab_id, "user_id": payload.user_id},
        db_conn=db,
    )
    return success(data=_serialise(membership), status_code=201)


@router.patch("/{lab_id}/members/{user_id}")
def update_member(
    lab_id: int,
    user_id: int,
    payload: MemberUpdate,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_capability("user:manage")(user, lab_id=lab_id)

    current = execute_query(
        "SELECT * FROM lab_membership WHERE user_id = :uid AND lab_id = :lid LIMIT 1",
        {"uid": user_id, "lid": lab_id},
        conn=db,
    )
    if not current:
        return error(
            "NOT_FOUND",
            f"User {user_id} is not a member of lab {lab_id}.",
            status_code=404,
        )
    before = current[0]

    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    if "permission_group_id" in updates:
        pg = execute_query(
            "SELECT id FROM permission_groups WHERE id = :id LIMIT 1",
            {"id": updates["permission_group_id"]},
            conn=db,
        )
        if not pg:
            return error(
                "NOT_FOUND",
                f"Permission group {updates['permission_group_id']} not found.",
                status_code=404,
            )

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    params = dict(updates)
    params["uid"] = user_id
    params["lid"] = lab_id
    rows = execute_write(
        f"UPDATE lab_membership SET {set_clause} "
        "WHERE user_id = :uid AND lab_id = :lid RETURNING *",
        params,
        conn=db,
    )
    after = rows[0]

    log_audit(
        action=AuditActions.CHANGE_MEMBER_ROLE,
        actor_id=user["id"],
        resource_type="lab_membership",
        resource_id=str(before["id"]),
        before=_serialise(before),
        after=_serialise(after),
        metadata={"lab_id": lab_id, "user_id": user_id},
        db_conn=db,
    )
    return success(data=_serialise(after))


@router.delete("/{lab_id}/members/{user_id}")
def remove_member(
    lab_id: int,
    user_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_capability("user:manage")(user, lab_id=lab_id)

    current = execute_query(
        "SELECT * FROM lab_membership WHERE user_id = :uid AND lab_id = :lid LIMIT 1",
        {"uid": user_id, "lid": lab_id},
        conn=db,
    )
    if not current:
        return error(
            "NOT_FOUND",
            f"User {user_id} is not a member of lab {lab_id}.",
            status_code=404,
        )
    before = current[0]

    execute_write(
        "DELETE FROM lab_membership WHERE user_id = :uid AND lab_id = :lid",
        {"uid": user_id, "lid": lab_id},
        conn=db,
    )

    log_audit(
        action=AuditActions.REMOVE_LAB_MEMBER,
        actor_id=user["id"],
        resource_type="lab_membership",
        resource_id=str(before["id"]),
        before=_serialise(before),
        after=None,
        metadata={"lab_id": lab_id, "user_id": user_id},
        db_conn=db,
    )
    return success_message("Member removed.")
