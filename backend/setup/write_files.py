#!/usr/bin/env python3
"""
JACKPOT File Writer — writes all application files to correct locations.

Usage:
    cd ~/ASU/jackpot
    python3 write_files.py              # skip existing files
    python3 write_files.py --overwrite  # overwrite existing files
    python3 write_files.py --dry-run    # show what would be written
"""

import argparse
import sys
from pathlib import Path
from textwrap import dedent

BASE = Path.home() / "ASU" / "jackpot"
BACKEND = BASE / "jackpot-backend"
FRONT = BASE / "jackpot-frontend"
SCHEMA = BASE / "jackpot-schema"


def write(path: Path, content: str, overwrite: bool, dry_run: bool) -> None:
    if dry_run:
        print(f"  [DRY RUN] {path.relative_to(BASE)}")
        return
    if path.exists() and not overwrite:
        print(f"  [SKIP]    {path.relative_to(BASE)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip("\n"))
    print(f"  [WRITE]   {path.relative_to(BASE)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for repo in [BACKEND, FRONT, SCHEMA]:
        if not repo.exists():
            print(f"ERROR: {repo} does not exist. Run bootstrap.sh first.")
            sys.exit(1)

    ow, dry = args.overwrite, args.dry_run
    print(f"\nJACKPOT File Writer {'(DRY RUN) ' if dry else ''}— Base: {BASE}\n")

    # ── permissions.py ───────────────────────────────────────────────────────
    write(
        BACKEND / "backend" / "permissions.py",
        '''
from enum import Enum


class PermissionGroups(str, Enum):
    """APGAP-identical role names. DO NOT rename."""
    PLATFORM_ADMIN      = "Platform Admin"
    LAB_DIRECTOR        = "Lab Director"
    LAB_COLLABORATOR    = "Lab Collaborator"
    LAB_READER          = "Lab Reader"
    BIOINFORMATICS_USER = "Bioinformatics User"
    DATA_ANALYST        = "Data Analyst"
''',
        ow,
        dry,
    )

    # ── config.py ────────────────────────────────────────────────────────────
    write(
        BACKEND / "backend" / "config.py",
        """
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    env:                        str  = "local"
    database_url: str = "postgresql://jackpot:jackpot@localhost:5432/jackpot_db" # pragma: allowlist secret
    storage_endpoint:           str | None = None
    storage_access_key:         str | None = None
    storage_secret_key:         str | None = None
    storage_bucket_sequences:   str = "jackpot-sequences"
    storage_bucket_raw:         str = "jackpot-raw"
    storage_bucket_staging:     str = "jackpot-staging"
    storage_bucket_datasets:    str = "jackpot-datasets"
    storage_bucket_submissions: str = "jackpot-submissions"
    gcp_project_id:             str = ""
    bigquery_dataset:           str = "jackpot_db"
    secret_key:                 str = "dev-secret-key-change-in-prod"
    mock_user_email:            str = "gotero@linuxprophet.com"
    google_oauth_client_id:     str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_url:  str = "postmessage"
    adhs_organization_name:     str = "ADHS"
    ncbi_api_key:               str = ""
    jackpot_api_token:          str = ""

    class Config:
        env_file = ".env.local"

    def validate_for_production(self) -> None:
        if self.env == "gcp":
            required = [
                ("google_oauth_client_id",     self.google_oauth_client_id),
                ("google_oauth_client_secret", self.google_oauth_client_secret),
                ("gcp_project_id",             self.gcp_project_id),
                ("secret_key",                 self.secret_key),
            ]
            if missing := [n for n, v in required if not v]:
                raise RuntimeError(f"Missing required config: {missing}")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
""",
        ow,
        dry,
    )

    # ── database.py ──────────────────────────────────────────────────────────
    write(
        BACKEND / "backend" / "database.py",
        """
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from config import get_settings

engine = create_engine(
    get_settings().database_url, pool_pre_ping=True, pool_size=5, max_overflow=10,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db():
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def execute_query(query: str, params: dict | None = None) -> list[dict]:
    with get_db() as db:
        result = db.execute(text(query), params or {})
        if result.returns_rows:
            cols = result.keys()
            return [dict(zip(cols, row)) for row in result.fetchall()]
        return []


def execute_write(query: str, params: dict | None = None) -> None:
    with get_db() as db:
        db.execute(text(query), params or {})
""",
        ow,
        dry,
    )

    # ── logging_config.py ────────────────────────────────────────────────────
    write(
        BACKEND / "backend" / "logging_config.py",
        """
import logging
import json
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname, "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("request_id", "user_email", "lab_id",
                    "action", "sample_id", "pipeline_run_id"):
            if hasattr(record, key):
                log[key] = getattr(record, key)
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
""",
        ow,
        dry,
    )

    # ── middleware.py ────────────────────────────────────────────────────────
    write(
        BACKEND / "backend" / "middleware.py",
        """
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
""",
        ow,
        dry,
    )

    # ── audit.py ─────────────────────────────────────────────────────────────
    write(
        BACKEND / "backend" / "audit.py",
        '''
import json
import logging
from database import execute_write

logger = logging.getLogger(__name__)

CREATE_SAMPLE   = "CREATE_SAMPLE"
UPDATE_SAMPLE   = "UPDATE_SAMPLE"
DELETE_SAMPLE   = "DELETE_SAMPLE"
APPROVE_ACCESS  = "APPROVE_ACCESS"
DENY_ACCESS     = "DENY_ACCESS"
DOWNLOAD_FILE   = "DOWNLOAD_FILE"
LAUNCH_PIPELINE = "LAUNCH_PIPELINE"
SUBMIT_NCBI     = "SUBMIT_NCBI"
SUBMIT_GISAID   = "SUBMIT_GISAID"
CHANGE_ROLE     = "CHANGE_ROLE"
CREATE_LAB      = "CREATE_LAB"
ARCHIVE_REQUEST = "ARCHIVE_REQUEST"


def log_audit(
    user_id: int, action: str, resource: str, resource_id: str,
    detail: dict | None = None, request_id: str | None = None,
    ip_address: str | None = None,
) -> None:
    """Write immutable audit record. Failures are logged, never raised."""
    try:
        execute_write(
            """
            INSERT INTO audit_log
                (user_id, action, resource, resource_id, detail, request_id, ip_address)
            VALUES
                (:uid, :action, :resource, :rid, :detail::jsonb, :req_id, :ip)
            """,
            {
                "uid": user_id, "action": action, "resource": resource,
                "rid": resource_id,
                "detail": json.dumps(detail) if detail else None,
                "req_id": request_id, "ip": ip_address,
            },
        )
    except Exception as exc:
        logger.error("Audit log write failed", exc_info=exc,
                     extra={"action": action, "resource": resource,
                            "resource_id": resource_id})
''',
        ow,
        dry,
    )

    # ── epiweek.py ───────────────────────────────────────────────────────────
    write(
        BACKEND / "backend" / "epiweek.py",
        '''
from datetime import date
from epiweeks import Week


def compute_epiweeks(collection_date: date) -> dict[str, int]:
    """Compute CDC MMWR and ISO epiweeks. Called at ingest, before DB write."""
    mmwr = Week.fromdate(collection_date, system="CDC")
    iso  = Week.fromdate(collection_date, system="ISO")
    return {
        "mmwr_year": mmwr.year, "mmwr_week": mmwr.week,
        "iso_year":  iso.year,  "iso_week":  iso.week,
    }
''',
        ow,
        dry,
    )

    # ── file_detector.py ─────────────────────────────────────────────────────
    # Single source of truth for NGS file pairing and extension detection.
    # Called by the ingest router to populate sample_files and convenience
    # URI fields. See Section 11.13 for full documentation.
    write(
        BACKEND / "backend" / "file_detector.py",
        '''
"""
JACKPOT file pairing detector.
Single source of truth for all file extension and naming convention logic.
Called by the ingest router to populate sample_files and convenience URI fields.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

# ── Supported extensions ─────────────────────────────────────────────────────
# Add new extensions here ONLY. Every regex pattern uses FASTQ_EXT automatically.

_FASTQ_BASES = r"fastq|fq"
_FASTA_BASES = r"fasta|fa|fna"
_ALL_BASES   = rf"(?:{_FASTQ_BASES}|{_FASTA_BASES})"
_COMPRESSION = r"(?:\\.gz|\\.bz2)?"

FASTQ_EXT = rf"\\.(?:{_ALL_BASES}){_COMPRESSION}"

_EXT_TO_FILE_TYPE: dict[str, str] = {
    "fastq": "FASTQ", "fq":    "FASTQ",
    "fasta": "FASTA", "fa":    "FASTA", "fna":   "FASTA",
}


def get_file_type(filename: str) -> str:
    """Return FASTQ, FASTA, or OTHER from a filename."""
    name = filename.lower()
    for suffix in (".gz", ".bz2"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return _EXT_TO_FILE_TYPE.get(Path(name).suffix.lstrip("."), "OTHER")


def is_sequence_file(filename: str) -> bool:
    return get_file_type(filename) in ("FASTQ", "FASTA")


# ── Pairing patterns — ordered most-specific to least-specific ───────────────

PAIRED_PATTERNS: list[re.Pattern] = [
    re.compile(rf"^(?P<prefix>.+?)_(?P<lane>L\\d+)_(?P<dir>R[12])(?:_\\d+)?{FASTQ_EXT}$",
               re.IGNORECASE),
    re.compile(rf"^(?P<prefix>.+?)_(?P<dir>R[12])(?:_\\d+)?{FASTQ_EXT}$",
               re.IGNORECASE),
    re.compile(rf"^(?P<prefix>.+?)_(?P<dir>[12]){FASTQ_EXT}$"),
    re.compile(rf"^(?P<prefix>.+?)_reads_(?P<dir>[12]){FASTQ_EXT}$"),
    re.compile(rf"^(?P<prefix>.+?)_(?P<dir>forward|reverse){FASTQ_EXT}$",
               re.IGNORECASE),
]

CHUNK_PATTERN = re.compile(
    rf"^(?P<prefix>.+?)_(?P<idx>\\d{{1,4}}){FASTQ_EXT}$", re.IGNORECASE,
)

DIRECTION_MAP: dict[str, str] = {
    "r1": "R1", "1": "R1", "forward": "R1",
    "r2": "R2", "2": "R2", "reverse": "R2",
}


@dataclass
class DetectedFile:
    filename:       str
    file_type:      str        = "FASTQ"
    library_layout: str        = "UNPAIRED"
    read_direction: str | None = None
    lane:           str | None = None
    chunk_index:    int | None = None
    prefix:         str | None = None


@dataclass
class DetectionResult:
    files:       list[DetectedFile]
    warnings:    list[str] = field(default_factory=list)
    has_paired:  bool      = False
    has_unpaired:bool      = False
    lane_count:  int       = 0


def detect_files(filenames: list[str]) -> DetectionResult:
    """Analyse filenames for a single sample. Non-sequence files skipped."""
    seq_files = [f for f in filenames if is_sequence_file(f)]
    skipped   = [f for f in filenames if not is_sequence_file(f)]
    detected: list[DetectedFile] = []
    warnings: list[str] = []

    if skipped:
        warnings.append(
            f"Skipped {len(skipped)} non-sequence file(s): "
            f"{', '.join(skipped[:5])}{'...' if len(skipped) > 5 else ''}"
        )

    groups: dict[tuple[str, str | None], dict[str, str]] = {}
    unmatched: list[str] = []

    for fname in seq_files:
        matched = False
        for pattern in PAIRED_PATTERNS:
            m = pattern.match(fname)
            if m:
                gd        = m.groupdict()
                prefix    = gd.get("prefix", "")
                lane      = gd.get("lane")
                direction = DIRECTION_MAP.get(gd.get("dir", "").lower(),
                                              gd.get("dir", "").upper())
                key       = (prefix, lane)
                groups.setdefault(key, {})
                if direction in groups[key]:
                    warnings.append(
                        f"Duplicate {direction} for \'{prefix}\'"
                        f"{f\', lane {lane}\' if lane else \'\'}: "
                        f"\'{groups[key][direction]}\' and \'{fname}\'"
                    )
                groups[key][direction] = fname
                matched = True
                break
        if not matched:
            unmatched.append(fname)

    has_paired = False
    has_unpaired = False
    lanes: set[str] = set()

    for (prefix, lane), dir_map in groups.items():
        has_r1, has_r2 = "R1" in dir_map, "R2" in dir_map
        if has_r1 and has_r2:
            has_paired = True
            if lane:
                lanes.add(lane)
            for direction, fname in dir_map.items():
                detected.append(DetectedFile(
                    filename=fname, file_type=get_file_type(fname),
                    library_layout="PAIRED", read_direction=direction,
                    lane=lane, prefix=prefix,
                ))
        elif has_r1:
            warnings.append(f"R1 \'{dir_map[\'R1\']}\' has no R2 — single-end.")
            has_unpaired = True
            detected.append(DetectedFile(
                filename=dir_map["R1"], file_type=get_file_type(dir_map["R1"]),
                library_layout="SINGLE", read_direction="R1",
                lane=lane, prefix=prefix,
            ))
        else:
            warnings.append(f"R2 \'{dir_map[\'R2\']}\' has no R1 — orphaned.")
            has_unpaired = True
            detected.append(DetectedFile(
                filename=dir_map["R2"], file_type=get_file_type(dir_map["R2"]),
                library_layout="SINGLE", read_direction="R2",
                lane=lane, prefix=prefix,
            ))

    chunk_groups: dict[str, list[tuple[int, str]]] = {}
    truly_unmatched: list[str] = []

    for fname in unmatched:
        m = CHUNK_PATTERN.match(fname)
        if m:
            chunk_groups.setdefault(m.group("prefix"), []).append(
                (int(m.group("idx")), fname)
            )
        else:
            truly_unmatched.append(fname)

    for prefix, chunks in chunk_groups.items():
        has_unpaired = True
        for idx, fname in sorted(chunks):
            detected.append(DetectedFile(
                filename=fname, file_type=get_file_type(fname),
                library_layout="UNPAIRED", chunk_index=idx, prefix=prefix,
            ))

    for fname in truly_unmatched:
        has_unpaired = True
        detected.append(DetectedFile(
            filename=fname, file_type=get_file_type(fname),
            library_layout="UNPAIRED",
        ))
        warnings.append(
            f"\'{fname}\' did not match any known convention — registered as unpaired."
        )

    return DetectionResult(
        files=detected, warnings=warnings,
        has_paired=has_paired, has_unpaired=has_unpaired,
        lane_count=len(lanes),
    )


def get_convenience_uris(
    result: DetectionResult,
    uri_map: dict[str, str],
) -> tuple[str | None, str | None]:
    """Return (fastq_r1_uri, fastq_r2_uri) convenience values for samples table."""
    r1_files = sorted(
        [f for f in result.files if f.read_direction == "R1"],
        key=lambda f: (f.lane or "", f.chunk_index or 0),
    )
    r2_files = sorted(
        [f for f in result.files if f.read_direction == "R2"],
        key=lambda f: (f.lane or "", f.chunk_index or 0),
    )
    r1_uri = uri_map.get(r1_files[0].filename) if r1_files else None
    r2_uri = uri_map.get(r2_files[0].filename) if r2_files else None
    if r1_uri is None and result.files:
        r1_uri = uri_map.get(result.files[0].filename)
    return r1_uri, r2_uri
''',
        ow,
        dry,
    )

    # ── storage.py ───────────────────────────────────────────────────────────
    write(
        BACKEND / "backend" / "storage.py",
        """
import os
import boto3
from botocore.client import Config as BotoConfig
from config import get_settings

settings = get_settings()


def _get_client():
    if settings.storage_endpoint:
        return boto3.client(
            "s3", endpoint_url=settings.storage_endpoint,
            aws_access_key_id=settings.storage_access_key,
            aws_secret_access_key=settings.storage_secret_key,
            config=BotoConfig(signature_version="s3v4"), region_name="us-east-1",
        )
    return boto3.client(
        "s3", endpoint_url="https://storage.googleapis.com",
        aws_access_key_id=os.environ.get("GCS_HMAC_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("GCS_HMAC_SECRET"),
        config=BotoConfig(signature_version="s3v4"), region_name="auto",
    )


def upload_fileobj(fileobj, bucket: str, key: str) -> str:
    _get_client().upload_fileobj(fileobj, bucket, key)
    return f"{'s3' if settings.storage_endpoint else 'gs'}://{bucket}/{key}"


def generate_presigned_url(bucket: str, key: str, expires: int = 3600) -> str:
    return _get_client().generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires,
    )


def generate_presigned_upload_url(bucket: str, key: str, expires: int = 86400) -> str:
    return _get_client().generate_presigned_url(
        "put_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires,
    )


def object_exists(bucket: str, key: str) -> bool:
    try:
        _get_client().head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False
""",
        ow,
        dry,
    )

    # ── pagination.py ────────────────────────────────────────────────────────
    write(
        BACKEND / "backend" / "pagination.py",
        """
from pydantic import BaseModel
from typing import Generic, TypeVar

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    results:     list[T]
    total_count: int
    limit:       int
    offset:      int
    has_more:    bool
""",
        ow,
        dry,
    )

    # ── main.py ──────────────────────────────────────────────────────────────
    write(
        BACKEND / "backend" / "main.py",
        """
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from logging_config import configure_logging
from middleware import RequestIDMiddleware
from config import get_settings

app = FastAPI(
    title="JACKPOT API",
    description=(
        "JACKPOT pathogen genomics platform. APGAP-compatible. "
        "Standards: GenEpiO, NCBI BioSample, PHA4GE, MIxS, GA4GH DUO, "
        "LOINC, SNOMED CT, MMWR epiweek."
    ),
    version="4.0.0",
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:4200"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
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
    return {"status": "ok", "version": "4.0.0", "project": "JACKPOT"}
""",
        ow,
        dry,
    )

    # ── pyproject.toml ───────────────────────────────────────────────────────
    write(
        BACKEND / "pyproject.toml",
        """
[project]
name = "jackpot-backend"
version = "4.0.0"
requires-python = ">=3.11"
description = "JACKPOT pathogen genomics platform backend"

[tool.pytest.ini_options]
asyncio_mode  = "auto"
testpaths     = ["tests"]
addopts       = "--cov=backend --cov-report=term-missing --cov-fail-under=60"

[tool.coverage.run]
omit = ["backend/models_generated.py", "tests/*", "scripts/*", "db/migrations/*"]

[tool.ruff]
line-length    = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]

[tool.mypy]
python_version         = "3.11"
strict                 = true
ignore_missing_imports = true
""",
        ow,
        dry,
    )

    # ── schema placeholder (copy actual YAML separately) ────────────────────
    schema_placeholder = (
        "# Copy jackpot_schema_v4_1.yaml here.\n"
        "# Generate artifacts:\n"
        "#   uv run gen-pydantic schema/jackpot_schema.yaml > backend/models_generated.py\n"
        "#   uv run gen-json-schema schema/jackpot_schema.yaml > schema/jackpot_schema.json\n"
    )
    write(SCHEMA / "schema" / "jackpot_schema.yaml", schema_placeholder, ow, dry)

    # ── mapping configs ──────────────────────────────────────────────────────
    write(
        SCHEMA / "schema" / "mapping_configs" / "asu_human_v1.yaml",
        """
source_format: asu_human_v1
target_class: HumanSample
column_mappings:
  "Sample ID":          sample_id
  "Collection Date":    date_collected
  "Pathogen":           organism_name
  "Sequencer":          sequencing_platform
  "Protocol":           sequencing_protocol
  "Age":                host_age
  "Sex":                host_sex
  "State":              collection_location_state
  "Country":            collection_location_country
  "MEDSIS ID":          adhs_medsis_id
  "Clinical Outcome":   clinical_outcome
  "Strain":             strain
  "Sequencing Lab":     sequencing_lab

# File detection configuration
# The ingest router calls detect_files() from file_detector.py on the
# semicolon-split value of the files_column for each row.
file_detection:
  files_column:      "FASTQ files"   # semicolon-separated list of filenames
  prefix_column:     "FASTQ prefix"  # fallback: scan staging bucket for prefix
  separator:         ";"
  auto_detect_pairs: true            # run detect_files() on result
  allow_prefix_scan: true            # fall back to prefix scan if files_column empty
""",
        ow,
        dry,
    )

    write(
        SCHEMA / "schema" / "mapping_configs" / "asu_wastewater_v1.yaml",
        """
source_format: asu_wastewater_v1
target_class: WastewaterSample
column_mappings:
  "Sample ID":          sample_id
  "Collection Date":    date_collected
  "Pathogen":           organism_name
  "Sequencer":          sequencing_platform
  "Protocol":           sequencing_protocol
  "WWTP Name":          wwtp_name
  "Zip Code":           sample_location_zipcode
  "County":             county_names
  "Population Served":  population_served
  "Sample Type":        sample_type
  "Sample Matrix":      sample_matrix
  "Flow Rate (MGD)":    flow_rate_mgd
  "Concentration Method": concentration_method
  "PCR Target":         pcr_target
  "Sequencing Lab":     sequencing_lab

file_detection:
  files_column:      "FASTQ files"
  prefix_column:     "FASTQ prefix"
  separator:         ";"
  auto_detect_pairs: true
  allow_prefix_scan: true
""",
        ow,
        dry,
    )

    write(
        SCHEMA / "schema" / "mapping_configs" / "asu_wildlife_v1.yaml",
        """
source_format: asu_wildlife_v1
target_class: WildlifeSample
column_mappings:
  "Sample ID":          sample_id
  "Collection Date":    date_collected
  "Pathogen":           organism_name
  "Sequencer":          sequencing_platform
  "Protocol":           sequencing_protocol
  "Host Species":       host_species
  "State":              collection_location_state
  "Country":            collection_location_country
  "Disease":            host_disease
  "Strain":             strain
  "Sequencing Lab":     sequencing_lab

file_detection:
  files_column:      "FASTQ files"
  prefix_column:     "FASTQ prefix"
  separator:         ";"
  auto_detect_pairs: true
  allow_prefix_scan: true
""",
        ow,
        dry,
    )

    write(
        SCHEMA / "schema" / "mapping_configs" / "ncbi_biosample_v1.yaml",
        """
source_format: ncbi_biosample_v1
target_class: Sample
column_mappings:
  "host_subject_id":    sample_id
  "collection_date":    date_collected
  "organism":           organism_name
  "sequencing_platform":sequencing_platform
  "geo_loc_name":       collection_location_country
  "host":               host_species
  "isolation_source":   isolation_source
  "strain":             strain
  "isolate":            isolate

file_detection:
  files_column:      "fastq_files"
  separator:         ";"
  auto_detect_pairs: true
  allow_prefix_scan: false
""",
        ow,
        dry,
    )

    # ── .gitignore ───────────────────────────────────────────────────────────
    write(
        BACKEND / ".gitignore",
        """
__pycache__/
*.py[cod]
*.pyo
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
dist/
build/
*.egg-info/
.venv/
uv.lock.tmp
.env
.env.local
.env.gcp
.env.*.local
*.secrets
.secrets.baseline.local
.vscode/settings.json
.idea/
backend/models_generated.py
db/bigquery_schema.sql
docs/schema.md
.DS_Store
Thumbs.db
""",
        ow,
        dry,
    )

    print(f"\n{'═'*50}")
    print(f"{'DRY RUN complete' if dry else 'Files written successfully.'}")
    print("\nNext:")
    print(f"  1. Copy jackpot_schema_v4_1.yaml to {SCHEMA}/schema/jackpot_schema.yaml")
    print(f"  2. cd {BACKEND} && docker compose up -d")
    print("  3. curl http://localhost:8000/health")
    print(f"  4. cd {BACKEND} && claude   (start Claude Code)")


if __name__ == "__main__":
    main()
