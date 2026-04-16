from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import get_settings
from backend.database import execute_query
from backend.jobs import run_access_request_job, run_scrubber_queue_job
from backend.logging_config import configure_logging
from backend.middleware import RequestIDMiddleware
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


@app.get("/health")
def health() -> dict:
    try:
        execute_query("SELECT 1")
        db_status = "connected"
    except Exception:
        db_status = "unavailable"
    if db_status == "unavailable":
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "version": __version__,
                "project": "JACKPOT",
                "database": db_status,
            },
        )
    return {"status": "ok", "version": __version__, "project": "JACKPOT", "database": db_status}
