from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/labs", tags=["labs"])


@router.get("/")
def list_labs() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "labs"}
