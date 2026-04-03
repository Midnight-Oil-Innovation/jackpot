from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/tokens", tags=["tokens"])


@router.get("/")
def list_tokens() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "tokens"}
