from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/archive-requests", tags=["archive_requests"])


@router.get("/")
def list_archive_requests() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "archive_requests"}
