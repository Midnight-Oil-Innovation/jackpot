from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.audit import AuditActions, log_audit
from backend.auth.guards import (
    get_current_user,
    get_user_lab_membership,
    require_lab_director,
)
from backend.database import execute_query, execute_write, get_db_dep
from backend.pagination import paginate
from backend.responses import error, success, success_list

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    lab_id: int
    display_name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    gcs_bucket: str | None = None
    project_prefix: str | None = None
    pathogen_scope: list[str] | None = None
    status: str | None = None


class ProjectUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    gcs_bucket: str | None = None
    project_prefix: str | None = None
    pathogen_scope: list[str] | None = None
    status: str | None = None
    build_status: str | None = None
    active: bool | None = None


_PROJECT_COLUMNS = {
    "display_name",
    "description",
    "gcs_bucket",
    "project_prefix",
    "pathogen_scope",
    "status",
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
def create_project(
    payload: ProjectCreate,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_lab_director(user, payload.lab_id)

    lab = execute_query(
        "SELECT id FROM labs WHERE id = :id LIMIT 1",
        {"id": payload.lab_id},
        conn=db,
    )
    if not lab:
        return error("NOT_FOUND", f"Lab {payload.lab_id} not found.", status_code=404)

    params: dict = {
        "lab_id": payload.lab_id,
        "display_name": payload.display_name,
        "description": payload.description,
        "gcs_bucket": payload.gcs_bucket,
        "project_prefix": payload.project_prefix,
        "pathogen_scope": payload.pathogen_scope,
        "status": payload.status or "ACTIVE",
        "created_by": user["id"],
    }
    rows = execute_write(
        """
        INSERT INTO projects
            (lab_id, display_name, description,
             gcs_bucket, project_prefix, pathogen_scope,
             status, active, created_by_id)
        VALUES (:lab_id, :display_name, :description,
                :gcs_bucket, :project_prefix, :pathogen_scope,
                :status, TRUE, :created_by)
        RETURNING *
        """,
        params,
        conn=db,
    )
    project = rows[0]
    log_audit(
        action=AuditActions.CREATE_PROJECT,
        actor_id=user["id"],
        resource_type="project",
        resource_id=str(project["id"]),
        before=None,
        after=_serialise(project),
        metadata={"lab_id": payload.lab_id},
        db_conn=db,
    )
    return success(data=_serialise(project), status_code=201)


@router.get("/")
def list_projects(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort_by: str = "display_name",
    sort_dir: str = "asc",
    name: str | None = None,
    lab_id: int | None = None,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)

    params: dict = {}
    where: list[str] = []

    if not user.get("is_platform_admin"):
        where.append(
            "(p.lab_id IN (SELECT lab_id FROM lab_membership WHERE user_id = :uid) "
            "OR p.id IN (SELECT project_id FROM project_membership WHERE user_id = :uid))"
        )
        params["uid"] = user["id"]

    if name is not None:
        where.append("LOWER(p.display_name) = LOWER(:name)")
        params["name"] = name

    if lab_id is not None:
        where.append("p.lab_id = :lab_id")
        params["lab_id"] = lab_id

    base_query = "SELECT p.* FROM projects p"
    if where:
        base_query += " WHERE " + " AND ".join(where)

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


@router.get("/{project_id}")
def get_project(
    project_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    rows = execute_query(
        "SELECT * FROM projects WHERE id = :id LIMIT 1",
        {"id": project_id},
        conn=db,
    )
    if not rows:
        return error("NOT_FOUND", f"Project {project_id} not found.", status_code=404)
    project = rows[0]

    if not user.get("is_platform_admin"):
        lab_member = get_user_lab_membership(user["id"], project["lab_id"])
        if not lab_member:
            proj_member = execute_query(
                "SELECT 1 FROM project_membership "
                "WHERE user_id = :uid AND project_id = :pid LIMIT 1",
                {"uid": user["id"], "pid": project_id},
                conn=db,
            )
            if not proj_member:
                return error(
                    "ACCESS_DENIED",
                    "You do not have access to this project.",
                    status_code=403,
                )
    return success(data=_serialise(project))


@router.patch("/{project_id}")
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)

    current = execute_query(
        "SELECT * FROM projects WHERE id = :id LIMIT 1",
        {"id": project_id},
        conn=db,
    )
    if not current:
        return error("NOT_FOUND", f"Project {project_id} not found.", status_code=404)
    before = current[0]

    require_lab_director(user, before["lab_id"])

    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates if k in _PROJECT_COLUMNS)
    if not set_clause:
        raise HTTPException(status_code=400, detail="No updatable fields supplied.")

    params = {k: v for k, v in updates.items() if k in _PROJECT_COLUMNS}
    params["id"] = project_id
    rows = execute_write(
        f"UPDATE projects SET {set_clause} WHERE id = :id RETURNING *",
        params,
        conn=db,
    )
    after = rows[0]

    log_audit(
        action=AuditActions.UPDATE_PROJECT,
        actor_id=user["id"],
        resource_type="project",
        resource_id=str(project_id),
        before=_serialise(before),
        after=_serialise(after),
        metadata=None,
        db_conn=db,
    )
    return success(data=_serialise(after))
