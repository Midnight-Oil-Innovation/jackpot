from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])


@router.get("/")
def list_organizations() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "organizations"}
