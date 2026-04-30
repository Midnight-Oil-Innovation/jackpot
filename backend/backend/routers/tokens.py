import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.audit import AuditActions, log_audit
from backend.auth.guards import get_current_user
from backend.database import execute_query, execute_write, get_db_dep
from backend.pagination import paginate
from backend.responses import error, success, success_list, success_message

router = APIRouter(prefix="/api/v1/tokens", tags=["tokens"])

_PUBLIC_COLUMNS = (
    "id, user_id, name, scopes, last_used, expires_at, created_at, "
    "default_lab_id, default_project_id"
)


class TokenCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    default_lab_id: int | None = None
    default_project_id: int | None = None


def _serialise(row: dict) -> dict:
    result = dict(row)
    for k, v in result.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
    return result


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@router.get("/")
def list_tokens(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    base_query = f"SELECT {_PUBLIC_COLUMNS} FROM personal_tokens WHERE user_id = :uid"
    rows, total = paginate(
        query=base_query,
        params={"uid": user["id"]},
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
def create_token(
    payload: TokenCreate,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)

    if payload.default_lab_id is not None:
        exists = execute_query(
            "SELECT 1 FROM labs WHERE id = :id LIMIT 1",
            {"id": payload.default_lab_id},
            conn=db,
        )
        if not exists:
            return error(
                "NOT_FOUND",
                f"Lab {payload.default_lab_id} not found.",
                status_code=404,
            )

    if payload.default_project_id is not None:
        exists = execute_query(
            "SELECT 1 FROM projects WHERE id = :id LIMIT 1",
            {"id": payload.default_project_id},
            conn=db,
        )
        if not exists:
            return error(
                "NOT_FOUND",
                f"Project {payload.default_project_id} not found.",
                status_code=404,
            )

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)

    rows = execute_write(
        f"""
        INSERT INTO personal_tokens
            (user_id, name, token_hash, default_lab_id, default_project_id)
        VALUES
            (:uid, :name, :hash, :lab, :proj)
        RETURNING {_PUBLIC_COLUMNS}
        """,
        {
            "uid": user["id"],
            "name": payload.name,
            "hash": token_hash,
            "lab": payload.default_lab_id,
            "proj": payload.default_project_id,
        },
        conn=db,
    )
    row = rows[0]
    log_audit(
        action=AuditActions.CREATE_TOKEN,
        actor_id=user["id"],
        resource_type="personal_token",
        resource_id=str(row["id"]),
        before=None,
        after=_serialise(row),
        metadata={"name": payload.name},
        db_conn=db,
    )
    data = _serialise(row)
    data["token"] = raw_token
    return success(data=data, status_code=201)


@router.delete("/{token_id}")
def revoke_token(
    token_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    rows = execute_query(
        f"SELECT {_PUBLIC_COLUMNS} FROM personal_tokens WHERE id = :id LIMIT 1",
        {"id": token_id},
        conn=db,
    )
    if not rows:
        return error("NOT_FOUND", f"Token {token_id} not found.", status_code=404)
    before = rows[0]

    if before["user_id"] != user["id"] and not user.get("is_platform_admin"):
        raise HTTPException(status_code=403, detail="Not your token.")

    execute_write(
        "DELETE FROM personal_tokens WHERE id = :id",
        {"id": token_id},
        conn=db,
    )
    log_audit(
        action=AuditActions.REVOKE_TOKEN,
        actor_id=user["id"],
        resource_type="personal_token",
        resource_id=str(token_id),
        before=_serialise(before),
        after=None,
        metadata={"owner_user_id": before["user_id"]},
        db_conn=db,
    )
    return success_message(f"Token {token_id} revoked.")
