from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/pipelines", tags=["pipelines"])


@router.get("/")
def list_pipelines() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "pipelines"}
