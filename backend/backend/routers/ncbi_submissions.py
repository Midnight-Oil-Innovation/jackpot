from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/ncbi-submissions", tags=["ncbi_submissions"])


@router.get("/")
def list_ncbi_submissions() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "ncbi_submissions"}
