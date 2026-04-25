from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import get_settings
from backend.database import execute_query
from backend.jobs import run_access_request_job, run_scrubber_queue_job
from backend.logging_config import configure_logging
from backend.middleware import RequestIDMiddleware
from backend.responses import error
from backend.routers import (
    archive_requests,
    auth,
    billing,
    dataharmonizer,
    dataset_access,
    datasets,
    domain_whitelist,
    gisaid,
    ingest,
    labs,
    ncbi_submissions,
    notifications,
    organizations,
    pipelines,
    projects,
    sample_access,
    samples,
    saved_searches,
    sequencing_labs,
    templates,
    tokens,
    users,
)
from backend.version import __version__

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    get_settings().validate_for_production()
    if get_settings().scheduler_enabled:
        scheduler.add_job(
            run_scrubber_queue_job,
            "interval",
            seconds=60,
            id="scrubber_queue",
        )
        scheduler.add_job(
            run_access_request_job,
            "cron",
            hour=2,
            minute=0,
            id="access_request_expiry",
        )
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown()


app = FastAPI(
    title="JACKPOT API",
    description=(
        "JACKPOT pathogen genomics platform. APGAP-compatible. "
        "Standards: GenEpiO, NCBI BioSample, PHA4GE, MIxS, GA4GH DUO, "
        "LOINC, SNOMED CT, MMWR epiweek."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.include_router(archive_requests.router)
app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(dataharmonizer.router)
app.include_router(dataset_access.router)
app.include_router(datasets.router)
app.include_router(domain_whitelist.router)
app.include_router(gisaid.router)
app.include_router(ingest.router)
app.include_router(labs.router)
app.include_router(ncbi_submissions.router)
app.include_router(notifications.router)
app.include_router(organizations.router)
app.include_router(pipelines.router)
app.include_router(projects.router)
app.include_router(sample_access.router)
app.include_router(samples.router)
app.include_router(saved_searches.router)
app.include_router(sequencing_labs.router)
app.include_router(tokens.router)
app.include_router(users.router)
app.include_router(templates.router)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Critical Rule 24: every error response goes through the JACKPOT envelope
# from backend/responses.py. A handful of routers still raise HTTPException
# directly (FastAPI's idiomatic error pattern); these handlers normalise
# the response shape so the frontend ApiClient can always extract a clean
# message from `error.message` instead of falling back to a raw JSON dump.
@app.exception_handler(HTTPException)
async def _http_exception_to_envelope(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        # Structured detail (e.g. validator output: {"errors": [...], "warnings": [...]}).
        # Primary message = first error if available; full structure preserved in detail.
        errors = detail.get("errors") if isinstance(detail.get("errors"), list) else None
        message = errors[0] if errors else "Request failed."
        return error(
            code=f"HTTP_{exc.status_code}",
            message=message,
            detail=detail,
            status_code=exc.status_code,
        )
    return error(
        code=f"HTTP_{exc.status_code}",
        message=str(detail) if detail is not None else "Request failed.",
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def _request_validation_to_envelope(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # FastAPI's auto-422 for missing/invalid request fields. Surface the first
    # validation error as the primary message so the UI gets a readable string.
    errs = exc.errors()
    if errs:
        first = errs[0]
        loc = ".".join(str(p) for p in first.get("loc", []) if p not in ("body",))
        message = f"{loc}: {first.get('msg', 'invalid')}" if loc else first.get("msg", "invalid")
    else:
        message = "Request validation failed."
    return error(
        code="HTTP_422",
        message=message,
        detail={"errors": errs},
        status_code=422,
    )


@app.get("/health")
def health() -> JSONResponse:
    try:
        execute_query("SELECT 1")
        db_status = "connected"
    except Exception:
        db_status = "unavailable"
    status_code = 503 if db_status == "unavailable" else 200
    body_status = "unavailable" if db_status == "unavailable" else "ok"
    return JSONResponse(
        status_code=status_code,
        content={
            "status": body_status,
            "version": __version__,
            "project": "JACKPOT",
            "database": db_status,
        },
    )
