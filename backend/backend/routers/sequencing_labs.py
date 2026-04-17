from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.audit import AuditActions, log_audit
from backend.auth.guards import get_current_user, require_platform_admin
from backend.database import execute_query, execute_write, get_db_dep
from backend.pagination import paginate
from backend.responses import error, success, success_list, success_message

router = APIRouter(prefix="/api/v1/sequencing-labs", tags=["sequencing_labs"])


class SequencingLabCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    organization: str | None = Field(default=None, max_length=255)
    is_external: bool = True


class SequencingLabUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    organization: str | None = Field(default=None, max_length=255)
    is_external: bool | None = None
    is_active: bool | None = None


_UPDATABLE = {"name", "organization", "is_external", "is_active"}


def _serialise(row: dict) -> dict:
    result = dict(row)
    for k, v in result.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
    return result


@router.get("/")
def list_sequencing_labs(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort_by: str = "name",
    sort_dir: str = "asc",
    search: str | None = None,
    db=Depends(get_db_dep),  # noqa: B008
):
    get_current_user(request)

    base_query = "SELECT * FROM sequencing_labs"
    params: dict = {}
    if search:
        base_query += " WHERE name ILIKE :search OR organization ILIKE :search"
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


@router.post("/", status_code=201)
def create_sequencing_lab(
    payload: SequencingLabCreate,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_platform_admin(user)

    existing = execute_query(
        "SELECT id FROM sequencing_labs WHERE name = :n LIMIT 1",
        {"n": payload.name},
        conn=db,
    )
    if existing:
        return error(
            "CONFLICT",
            f"Sequencing lab '{payload.name}' already exists.",
            status_code=409,
        )

    rows = execute_write(
        """
        INSERT INTO sequencing_labs (name, organization, is_external, is_active)
        VALUES (:name, :organization, :is_external, TRUE)
        RETURNING *
        """,
        {
            "name": payload.name,
            "organization": payload.organization,
            "is_external": payload.is_external,
        },
        conn=db,
    )
    row = rows[0]
    log_audit(
        action=AuditActions.CREATE_SEQUENCING_LAB,
        actor_id=user["id"],
        resource_type="sequencing_lab",
        resource_id=str(row["id"]),
        before=None,
        after=_serialise(row),
        metadata=None,
        db_conn=db,
    )
    return success(data=_serialise(row), status_code=201)


@router.get("/{seq_lab_id}")
def get_sequencing_lab(
    seq_lab_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    get_current_user(request)
    rows = execute_query(
        "SELECT * FROM sequencing_labs WHERE id = :id LIMIT 1",
        {"id": seq_lab_id},
        conn=db,
    )
    if not rows:
        return error("NOT_FOUND", f"Sequencing lab {seq_lab_id} not found.", status_code=404)
    return success(data=_serialise(rows[0]))


@router.patch("/{seq_lab_id}")
def update_sequencing_lab(
    seq_lab_id: int,
    payload: SequencingLabUpdate,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_platform_admin(user)

    current = execute_query(
        "SELECT * FROM sequencing_labs WHERE id = :id LIMIT 1",
        {"id": seq_lab_id},
        conn=db,
    )
    if not current:
        return error("NOT_FOUND", f"Sequencing lab {seq_lab_id} not found.", status_code=404)
    before = current[0]

    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    updates = {k: v for k, v in updates.items() if k in _UPDATABLE}
    if not updates:
        raise HTTPException(status_code=400, detail="No updatable fields supplied.")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    params = dict(updates)
    params["id"] = seq_lab_id
    rows = execute_write(
        f"UPDATE sequencing_labs SET {set_clause} WHERE id = :id RETURNING *",
        params,
        conn=db,
    )
    after = rows[0]

    log_audit(
        action=AuditActions.UPDATE_SEQUENCING_LAB,
        actor_id=user["id"],
        resource_type="sequencing_lab",
        resource_id=str(seq_lab_id),
        before=_serialise(before),
        after=_serialise(after),
        metadata=None,
        db_conn=db,
    )
    return success(data=_serialise(after))


@router.post("/{seq_lab_id}/assign/{lab_id}", status_code=201)
def assign_sequencing_lab(
    seq_lab_id: int,
    lab_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_platform_admin(user)

    seq = execute_query(
        "SELECT id FROM sequencing_labs WHERE id = :id LIMIT 1",
        {"id": seq_lab_id},
        conn=db,
    )
    if not seq:
        return error("NOT_FOUND", f"Sequencing lab {seq_lab_id} not found.", status_code=404)

    lab = execute_query(
        "SELECT id FROM labs WHERE id = :id LIMIT 1",
        {"id": lab_id},
        conn=db,
    )
    if not lab:
        return error("NOT_FOUND", f"Lab {lab_id} not found.", status_code=404)

    existing = execute_query(
        "SELECT id FROM sequencing_lab_assignments "
        "WHERE sequencing_lab_id = :sid AND lab_id = :lid LIMIT 1",
        {"sid": seq_lab_id, "lid": lab_id},
        conn=db,
    )
    if existing:
        return error(
            "CONFLICT",
            f"Sequencing lab {seq_lab_id} is already assigned to lab {lab_id}.",
            status_code=409,
        )

    rows = execute_write(
        """
        INSERT INTO sequencing_lab_assignments (sequencing_lab_id, lab_id)
        VALUES (:sid, :lid)
        RETURNING *
        """,
        {"sid": seq_lab_id, "lid": lab_id},
        conn=db,
    )
    row = rows[0]
    log_audit(
        action=AuditActions.ASSIGN_SEQUENCING_LAB,
        actor_id=user["id"],
        resource_type="sequencing_lab_assignment",
        resource_id=str(row["id"]),
        before=None,
        after=_serialise(row),
        metadata={"sequencing_lab_id": seq_lab_id, "lab_id": lab_id},
        db_conn=db,
    )
    return success(data=_serialise(row), status_code=201)


@router.delete("/{seq_lab_id}/assign/{lab_id}")
def unassign_sequencing_lab(
    seq_lab_id: int,
    lab_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_platform_admin(user)

    existing = execute_query(
        "SELECT * FROM sequencing_lab_assignments "
        "WHERE sequencing_lab_id = :sid AND lab_id = :lid LIMIT 1",
        {"sid": seq_lab_id, "lid": lab_id},
        conn=db,
    )
    if not existing:
        return error(
            "NOT_FOUND",
            f"No assignment between sequencing lab {seq_lab_id} and lab {lab_id}.",
            status_code=404,
        )
    before = existing[0]

    execute_write(
        "DELETE FROM sequencing_lab_assignments WHERE sequencing_lab_id = :sid AND lab_id = :lid",
        {"sid": seq_lab_id, "lid": lab_id},
        conn=db,
    )
    log_audit(
        action=AuditActions.UNASSIGN_SEQUENCING_LAB,
        actor_id=user["id"],
        resource_type="sequencing_lab_assignment",
        resource_id=str(before["id"]),
        before=_serialise(before),
        after=None,
        metadata={"sequencing_lab_id": seq_lab_id, "lab_id": lab_id},
        db_conn=db,
    )
    return success_message(
        f"Sequencing lab {seq_lab_id} unassigned from lab {lab_id}.",
    )
