from fastapi import APIRouter, Depends, Query, Request

from backend.auth.guards import get_current_user
from backend.database import execute_query, get_db_dep
from backend.pagination import paginate
from backend.responses import error, success, success_list

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _serialise(row: dict) -> dict:
    result = dict(row)
    for k, v in result.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
    return result


@router.get("/")
def list_projects(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort_by: str = "display_name",
    sort_dir: str = "asc",
    name: str | None = None,
    db=Depends(get_db_dep),  # noqa: B008
):
    get_current_user(request)

    base_query = "SELECT * FROM projects"
    params: dict = {}
    if name is not None:
        base_query += " WHERE LOWER(display_name) = LOWER(:name)"
        params["name"] = name

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
    get_current_user(request)
    rows = execute_query(
        "SELECT * FROM projects WHERE id = :id LIMIT 1",
        {"id": project_id},
        conn=db,
    )
    if not rows:
        return error("NOT_FOUND", f"Project {project_id} not found.", status_code=404)
    return success(data=_serialise(rows[0]))
