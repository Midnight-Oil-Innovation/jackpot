from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


@router.get("/")
def list_datasets() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "datasets"}
