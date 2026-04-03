from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/domain-whitelist", tags=["domain_whitelist"])


@router.get("/")
def list_domain_whitelist() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "domain_whitelist"}
