from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/")
def list_users() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "users"}
