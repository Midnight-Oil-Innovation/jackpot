from config import get_settings
from database import execute_query
from fastapi import HTTPException, Request
from jose import jwt

settings = get_settings()


def get_current_user(request: Request) -> dict:
    """
    Local dev (ENV=local): returns the mock user from settings.mock_user_email.
    Production: validates JWT access cookie.
    """
    if settings.env == "local":
        rows = execute_query(
            "SELECT * FROM users WHERE email = :e AND is_active = TRUE LIMIT 1",
            {"e": settings.mock_user_email},
        )
        return (
            rows[0]
            if rows
            else {
                "id": 1,
                "email": settings.mock_user_email,
                "name": "Dev User",
                "is_platform_admin": True,
                "is_data_analyst": False,
                "is_active": True,
                "organization_id": 1,
            }
        )

    token = request.cookies.get("access")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Access token expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token.") from exc

    rows = execute_query(
        "SELECT id, email, name, is_platform_admin, is_data_analyst, "
        "is_active, organization_id FROM users "
        "WHERE id = :uid AND is_active = TRUE LIMIT 1",
        {"uid": payload["sub"]},
    )
    if not rows:
        raise HTTPException(status_code=401, detail="User not found or inactive.")
    return rows[0]


def get_user_lab_membership(user_id: int, lab_id: int) -> dict | None:
    rows = execute_query(
        "SELECT lm.*, pg.name AS permission_group_name, lm.is_lab_admin "
        "FROM lab_membership lm "
        "JOIN permission_groups pg ON pg.id = lm.permission_group_id "
        "WHERE lm.user_id = :uid AND lm.lab_id = :lid LIMIT 1",
        {"uid": user_id, "lid": lab_id},
    )
    return rows[0] if rows else None


def require_platform_admin(current_user: dict) -> None:
    if not current_user.get("is_platform_admin"):
        raise HTTPException(status_code=403, detail="Platform Admin required.")


def require_lab_director(current_user: dict, lab_id: int) -> None:
    if current_user.get("is_platform_admin"):
        return
    m = get_user_lab_membership(current_user["id"], lab_id)
    if not m or not m.get("is_lab_admin"):
        raise HTTPException(status_code=403, detail="Lab Director required.")


def require_lab_access(current_user: dict, lab_id: int) -> None:
    if current_user.get("is_platform_admin"):
        return
    if get_user_lab_membership(current_user["id"], lab_id):
        return
    rows = execute_query(
        "SELECT 1 FROM project_membership pm "
        "JOIN projects p ON p.id = pm.project_id "
        "WHERE pm.user_id = :uid AND p.lab_id = :lid LIMIT 1",
        {"uid": current_user["id"], "lid": lab_id},
    )
    if not rows:
        raise HTTPException(status_code=403, detail="Lab access required.")
