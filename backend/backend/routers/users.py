from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.audit import AuditActions, log_audit
from backend.auth.guards import get_current_user, permits, require_capability
from backend.authz.reseed import INSTANCE_PRESETS, sync_instance_preset
from backend.database import execute_query, execute_write, get_db_dep
from backend.pagination import paginate
from backend.responses import error, success, success_list, success_message

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class UserUpdate(BaseModel):
    # Unknown fields are an error, not noise. Pydantic drops them by default,
    # which for THIS model means a stale client sending the pre-slice-7 body
    # gets a 200 having assigned nothing — the caller believing they promoted
    # someone who holds none of it. That is the failure mode a breaking rename
    # exists to prevent, so the rename has to be loud.
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    #: Instance-scope role, by preset name (access_model.md §8.2) — or an
    #: explicit null to remove it. Replaces the is_platform_admin /
    #: is_data_analyst booleans this endpoint used to accept: a role write is
    #: a capability ASSIGNMENT, and the model's unit of assignment is a
    #: preset, not a flag. Lab-scoped roles are assigned through membership
    #: (M2-B5), not here.
    instance_preset: str | None = None
    is_active: bool | None = None
    organization_id: int | None = None


_SELF_EDITABLE = {"name"}
#: The field whose write issues grants rather than editing a profile.
_ROLE_FIELD = "instance_preset"
_ADMIN_EDITABLE = {
    "name",
    "instance_preset",
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
    require_capability("user:manage")(user)

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
    # M2-B5: self, or user:manage. Self is not a capability — §3.1's scope
    # tree has no user level, so "you are yourself" cannot be expressed as a
    # grant and stays an identity comparison (§4.7).
    if current["id"] != user_id and not permits(current, "user:manage"):
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
    is_admin = permits(current, "user:manage")
    is_self = current["id"] == user_id
    if not is_admin and not is_self:
        return error(
            "ACCESS_DENIED",
            "You do not have access to this user record.",
            status_code=403,
        )

    # An explicit null on the role field means "remove the Instance role",
    # which exclude_none cannot distinguish from "not supplied" (Rule 39's
    # partial-update shape has no way to say it). model_fields_set answers a
    # different question — did the caller supply this — so it gets its own name
    # and is the only thing consulted about the role field.
    role_written = _ROLE_FIELD in payload.model_fields_set
    updates = payload.model_dump(exclude_none=True)
    if not updates and not role_written:
        raise HTTPException(status_code=400, detail="No fields to update.")

    allowed = _ADMIN_EDITABLE if is_admin else _SELF_EDITABLE
    forbidden = (set(updates) | ({_ROLE_FIELD} if role_written else set())) - allowed
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

    # The preset is the only representation now — M2-DROP removed the
    # columns this used to also write, and the grants are the assignment.
    if role_written:
        preset = payload.instance_preset
        if preset is not None and preset not in INSTANCE_PRESETS:
            return error(
                "INVALID_PRESET",
                f"instance_preset must be null or one of {sorted(INSTANCE_PRESETS)}.",
                status_code=422,
            )
        updates.pop(_ROLE_FIELD, None)

    # A role-only PATCH now touches no column at all: instance_preset is not
    # one, and M2-DROP removed the two it used to translate into. Before the
    # drop `updates` was never empty here, so the SET clause was always
    # well-formed; now it can be, and `SET , updated_at = ...` is a syntax
    # error. The row still gets its updated_at bumped — a role assignment is
    # a change to the user even when no column of theirs holds it.
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    set_clause = f"{set_clause}, updated_at = NOW()" if set_clause else "updated_at = NOW()"
    params = dict(updates)
    params["id"] = user_id
    rows = execute_write(
        f"UPDATE users SET {set_clause} WHERE id = :id RETURNING *",
        params,
        conn=db,
    )
    after = rows[0]

    # The role changed, so the grants must too. §4.5 scopes user:manage as
    # "assign capabilities" — issuing the grants IS the assignment. On the
    # request's own connection so the row and the grants land in one
    # transaction: a half-applied pair leaves the principal either inert or
    # over-privileged. Mirrors labs.py's _sync_grants_for (M2-B5).
    if role_written:
        sync_instance_preset(db, user_id=user_id, preset=payload.instance_preset)

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
    require_capability("user:manage")(current)

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
