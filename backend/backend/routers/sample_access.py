from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/sample-access", tags=["sample_access"])


@router.get("/")
def list_sample_access() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "sample_access"}
