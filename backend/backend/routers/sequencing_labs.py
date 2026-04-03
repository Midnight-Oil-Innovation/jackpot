from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/sequencing-labs", tags=["sequencing_labs"])


@router.get("/")
def list_sequencing_labs() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "sequencing_labs"}
