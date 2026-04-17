from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.audit import AuditActions, log_audit
from backend.auth.guards import get_current_user, require_platform_admin
from backend.database import execute_query, execute_write, get_db_dep
from backend.pagination import paginate
from backend.responses import error, success, success_list, success_message

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_platform_admin: bool | None = None
    is_data_analyst: bool | None = None
    is_active: bool | None = None
    organization_id: int | None = None


_SELF_EDITABLE = {"name"}
_ADMIN_EDITABLE = {
    "name",
    "is_platform_admin",
    "is_data_analyst",
    "is_active",
    "organization_id",
}


def _serialise(row: dict) -> dict:
    result = dict(row)
    for k, v in result.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
    return result


def _get_lab_memberships(user_id: int, db) -> list[dict]:
    rows = execute_query(
        """
        SELECT lm.lab_id, lm.is_lab_director, lm.permission_group_id,
               l.display_name AS lab_name, pg.name AS permission_group_name
        FROM lab_membership lm
        JOIN labs l ON l.id = lm.lab_id
        JOIN permission_groups pg ON pg.id = lm.permission_group_id
        WHERE lm.user_id = :uid
        ORDER BY l.display_name
        """,
        {"uid": user_id},
        conn=db,
    )
    return [_serialise(r) for r in rows]


@router.get("/me")
def get_me(request: Request, db=Depends(get_db_dep)):  # noqa: B008
    user = get_current_user(request)
    rows = execute_query(
        "SELECT * FROM users WHERE id = :id LIMIT 1",
        {"id": user["id"]},
        conn=db,
    )
    if not rows:
        return error("NOT_FOUND", "User record not found.", status_code=404)
    data = _serialise(rows[0])
    data["lab_memberships"] = _get_lab_memberships(user["id"], db)
    return success(data=data)


@router.get("/")
def list_users(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    search: str | None = None,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_platform_admin(user)

    base_query = "SELECT * FROM users"
    params: dict = {}
    if search:
        base_query += " WHERE email ILIKE :search OR name ILIKE :search"
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


@router.get("/{user_id}")
def get_user(
    user_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    current = get_current_user(request)
    if not current.get("is_platform_admin") and current["id"] != user_id:
        return error(
            "ACCESS_DENIED",
            "You do not have access to this user record.",
            status_code=403,
        )

    rows = execute_query(
        "SELECT * FROM users WHERE id = :id LIMIT 1",
        {"id": user_id},
        conn=db,
    )
    if not rows:
        return error("NOT_FOUND", f"User {user_id} not found.", status_code=404)
    return success(data=_serialise(rows[0]))


@router.patch("/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    current = get_current_user(request)
    is_admin = bool(current.get("is_platform_admin"))
    is_self = current["id"] == user_id
    if not is_admin and not is_self:
        return error(
            "ACCESS_DENIED",
            "You do not have access to this user record.",
            status_code=403,
        )

    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    allowed = _ADMIN_EDITABLE if is_admin else _SELF_EDITABLE
    forbidden = set(updates) - allowed
    if forbidden:
        return error(
            "ACCESS_DENIED",
            f"Fields not permitted for this role: {sorted(forbidden)}.",
            status_code=403,
        )

    before_rows = execute_query(
        "SELECT * FROM users WHERE id = :id LIMIT 1",
        {"id": user_id},
        conn=db,
    )
    if not before_rows:
        return error("NOT_FOUND", f"User {user_id} not found.", status_code=404)
    before = before_rows[0]

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    params = dict(updates)
    params["id"] = user_id
    rows = execute_write(
        f"UPDATE users SET {set_clause}, updated_at = NOW() WHERE id = :id RETURNING *",
        params,
        conn=db,
    )
    after = rows[0]

    log_audit(
        action=AuditActions.UPDATE_USER,
        actor_id=current["id"],
        resource_type="user",
        resource_id=str(user_id),
        before=_serialise(before),
        after=_serialise(after),
        metadata=None,
        db_conn=db,
    )
    return success(data=_serialise(after))


@router.delete("/{user_id}")
def deactivate_user(
    user_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    current = get_current_user(request)
    require_platform_admin(current)

    before_rows = execute_query(
        "SELECT * FROM users WHERE id = :id LIMIT 1",
        {"id": user_id},
        conn=db,
    )
    if not before_rows:
        return error("NOT_FOUND", f"User {user_id} not found.", status_code=404)
    before = before_rows[0]

    rows = execute_write(
        "UPDATE users SET is_active = FALSE, updated_at = NOW() WHERE id = :id RETURNING *",
        {"id": user_id},
        conn=db,
    )
    after = rows[0]

    log_audit(
        action=AuditActions.UPDATE_USER,
        actor_id=current["id"],
        resource_type="user",
        resource_id=str(user_id),
        before=_serialise(before),
        after=_serialise(after),
        metadata={"soft_delete": True},
        db_conn=db,
    )
    return success_message("User deactivated.")
