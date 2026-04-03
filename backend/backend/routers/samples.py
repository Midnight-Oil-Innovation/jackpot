from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/samples", tags=["samples"])


@router.get("/")
def list_samples() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "samples"}
