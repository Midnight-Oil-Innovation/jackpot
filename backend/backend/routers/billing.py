from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


@router.get("/")
def list_billing() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "billing"}
