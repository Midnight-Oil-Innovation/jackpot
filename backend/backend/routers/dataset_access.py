from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/dataset-access", tags=["dataset_access"])


@router.get("/")
def list_dataset_access() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {"status": "not implemented", "router": "dataset_access"}
