from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.logging_config import configure_logging
from backend.middleware import RequestIDMiddleware
from backend.routers import gisaid, samples

app = FastAPI(
    title="JACKPOT API",
    description=(
        "JACKPOT pathogen genomics platform. APGAP-compatible. "
        "Standards: GenEpiO, NCBI BioSample, PHA4GE, MIxS, GA4GH DUO, "
        "LOINC, SNOMED CT, MMWR epiweek."
    ),
    version="4.0.0",
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

# Add router imports here as each is implemented:
# from routers import auth, samples, ingest, labs, projects, users, ...
# for r in [auth, samples, ...]:
#     app.include_router(r.router, prefix="/api/v1")


@app.on_event("startup")
def startup() -> None:
    configure_logging()
    get_settings().validate_for_production()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "5.0.0", "project": "JACKPOT"}
