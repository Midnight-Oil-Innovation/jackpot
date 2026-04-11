from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.jobs import run_access_request_job, run_scrubber_queue_job
from backend.logging_config import configure_logging
from backend.middleware import RequestIDMiddleware
from backend.routers import gisaid, samples
from backend.version import __version__

app = FastAPI(
    title="JACKPOT API",
    description=(
        "JACKPOT pathogen genomics platform. APGAP-compatible. "
        "Standards: GenEpiO, NCBI BioSample, PHA4GE, MIxS, GA4GH DUO, "
        "LOINC, SNOMED CT, MMWR epiweek."
    ),
    version=__version__,
)

app.include_router(gisaid.router)
app.include_router(samples.router)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = AsyncIOScheduler()


@app.on_event("startup")
def startup() -> None:
    configure_logging()
    get_settings().validate_for_production()
    if get_settings().scheduler_enabled:
        scheduler.add_job(
            run_scrubber_queue_job,
            "interval",
            hours=1,
            id="scrub_override_auto_deny",
        )
        scheduler.add_job(
            run_access_request_job,
            "interval",
            hours=1,
            id="access_request_auto_approve",
        )
        scheduler.start()


@app.on_event("shutdown")
def shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__, "project": "JACKPOT"}
