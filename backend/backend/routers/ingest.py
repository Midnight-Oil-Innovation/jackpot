from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])


@router.get("/")
def list_ingest() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "ingest"}
