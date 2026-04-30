from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("/")
def list_notifications() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "notifications"}
