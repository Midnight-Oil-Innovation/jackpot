from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/archive-requests", tags=["archive_requests"])


@router.get("/")
def list_archive_requests() -> None:
    """Stub — implement in Phase 24+ (Month 3).

    Phase 22 review action item 10: stub routers MUST return 501,
    never 200 — silent-failure hazard for clients that don't inspect
    the response body. The HTTPException is caught by the global
    `_http_exception_to_envelope` handler in main.py and rendered
    through the JACKPOT envelope (Critical Rule 24).
    """
    raise HTTPException(
        status_code=501,
        detail=(
            "The archive_requests router is not yet implemented. "
            "Tracked as P0e action item 10 / Phase 24 (Month 3) work."
        ),
    )
