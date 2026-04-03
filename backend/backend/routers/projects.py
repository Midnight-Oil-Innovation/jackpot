from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("/")
def list_projects() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "projects"}
