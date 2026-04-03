from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/dataharmonizer", tags=["dataharmonizer"])


@router.get("/")
def list_dataharmonizer() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "dataharmonizer"}
