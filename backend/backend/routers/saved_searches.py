from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/saved-searches", tags=["saved_searches"])


@router.get("/")
def list_saved_searches() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "saved_searches"}
