#!/usr/bin/env python3
"""
JACKPOT File Writer 2 — writes all remaining application files.

Complements write_files.py which wrote the core backend modules.
This script writes:
  - Docker / CI configuration
  - db/init.sql and db/migrations/env.py
  - backend/auth/* (oauth, middleware, dependencies)
  - backend/validator.py and backend/harmonizer.py
  - backend/routers/* (gisaid fully; all others as working stubs)
  - frontend/pages/* and frontend/components/* (stubs)
  - pipelines/ingest_gate.nf and pipelines/nextflow.config
  - scripts/portal_to_tostadas.py
  - tests/* (conftest + all test files)
  - docs/CLAUDE.md
  - .pre-commit-config.yaml
  - .github/workflows/test.yml

Usage:
    cd ~/ASU/jackpot
    python3 write_files_2.py              # skip existing files
    python3 write_files_2.py --overwrite  # overwrite existing files
    python3 write_files_2.py --dry-run    # print what would be written
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
    parser = argparse.ArgumentParser(description="Write remaining JACKPOT files")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for repo in [BACKEND, FRONT, SCHEMA]:
        if not repo.exists():
            print(f"ERROR: {repo} does not exist. Run bootstrap.sh first.")
            sys.exit(1)

    ow, dry = args.overwrite, args.dry_run
    print(f"\nJACKPOT File Writer 2 {'(DRY RUN) ' if dry else ''}— Base: {BASE}\n")

    # =========================================================================
    # DOCKER AND CI
    # =========================================================================

    write(
        BACKEND / "docker-compose.yml",
        """
services:

  postgres:
    image: postgres:16
    platform: linux/arm64
    container_name: jackpot_postgres
    environment:
      POSTGRES_USER:     jackpot
      POSTGRES_PASSWORD: jackpot
      POSTGRES_DB:       jackpot_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U jackpot"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:latest
    platform: linux/arm64
    container_name: jackpot_minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER:     minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 3

  minio_init:
    image: minio/mc:latest
    platform: linux/arm64
    container_name: jackpot_minio_init
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set local http://minio:9000 minioadmin minioadmin;
      mc mb --ignore-existing local/jackpot-raw;
      mc mb --ignore-existing local/jackpot-sequences;
      mc mb --ignore-existing local/jackpot-staging;
      mc mb --ignore-existing local/jackpot-results;
      mc mb --ignore-existing local/jackpot-datasets;
      mc mb --ignore-existing local/jackpot-pipelines;
      mc mb --ignore-existing local/jackpot-submissions;
      echo 'All buckets ready.';
      "

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    container_name: jackpot_api
    environment:
      ENV:                        local
      DATABASE_URL: postgresql://jackpot:jackpot@postgres:5432/jackpot_db # pragma: allowlist secret
      STORAGE_ENDPOINT:           http://minio:9000
      STORAGE_ACCESS_KEY:         minioadmin
      STORAGE_SECRET_KEY:         minioadmin
      STORAGE_BUCKET_SEQUENCES:   jackpot-sequences
      STORAGE_BUCKET_RAW:         jackpot-raw
      STORAGE_BUCKET_STAGING:     jackpot-staging
      STORAGE_BUCKET_DATASETS:    jackpot-datasets
      STORAGE_BUCKET_SUBMISSIONS: jackpot-submissions
      SECRET_KEY:                 dev-secret-key-change-in-prod
      MOCK_USER_EMAIL:            gotero@linuxprophet.com
      GOOGLE_OAUTH_CLIENT_ID:     ""
      GOOGLE_OAUTH_CLIENT_SECRET: ""
      GOOGLE_OAUTH_REDIRECT_URL:  postmessage
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
      - ./schema:/schema
    depends_on:
      postgres:
        condition: service_healthy
      minio:
        condition: service_healthy
    command: uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  ui:
    build:
      context: .
      dockerfile: Dockerfile.ui
    container_name: jackpot_ui
    environment:
      API_BASE_URL:    http://api:8000
      ENV:             local
      MOCK_USER_EMAIL: gotero@linuxprophet.com
    ports:
      - "8501:8501"
    volumes:
      - ./frontend:/app
      - ./schema:/schema
    depends_on:
      - api
    command: uv run streamlit run app.py --server.port=8501 --server.address=0.0.0.0

volumes:
  postgres_data:
  minio_data:
""",
        ow,
        dry,
    )

    write(
        BACKEND / "Dockerfile.api",
        """
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ .
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
""",
        ow,
        dry,
    )

    write(
        BACKEND / "Dockerfile.ui",
        """
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY frontend/ .
EXPOSE 8501
CMD ["uv", "run", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
""",
        ow,
        dry,
    )

    write(
        BACKEND / ".pre-commit-config.yaml",
        """
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        args: [--ignore-missing-imports, --strict]
        additional_dependencies: [pydantic, sqlalchemy]

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: [--baseline, .secrets.baseline]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-toml
      - id: check-merge-conflict
      - id: no-commit-to-branch
        args: [--branch, main]
""",
        ow,
        dry,
    )

    write(
        BACKEND / ".github" / "workflows" / "test.yml",
        """
name: Test & Lint

on:
  push:
    branches: [main, development]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER:     jackpot
          POSTGRES_PASSWORD: jackpot
          POSTGRES_DB:       jackpot_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: uv sync --frozen

      - name: Run pre-commit hooks
        run: uv run pre-commit run --all-files

      - name: Run Alembic migrations
        env:
          DATABASE_URL: postgresql://jackpot:jackpot@localhost:5432/jackpot_test
        run: uv run alembic upgrade head

      - name: Run tests
        env:
          DATABASE_URL: postgresql://jackpot:jackpot@localhost:5432/jackpot_test
          ENV: local
        run: uv run pytest --cov=backend --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
""",
        ow,
        dry,
    )

    # =========================================================================
    # DATABASE
    # =========================================================================

    # db/init.sql is the full reference schema — too large to inline here.
    # It is documented in full in Section 11.12 of the architecture doc.
    # Copy it manually: nvim db/init.sql (paste from arch doc Section 11.12)
    # Or: the Alembic autogenerate approach below creates it from models.
    write(
        BACKEND / "db" / "init.sql",
        """
-- JACKPOT Database Schema v4.1
-- Copy full content from Section 11.12 of jackpot_architecture_v4.md
-- This placeholder ensures the file exists so docker-compose mounts correctly.
-- Replace with the full schema before running docker compose up -d.

-- Minimal seed to allow API to start:
CREATE TABLE IF NOT EXISTS permission_groups (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

INSERT INTO permission_groups (name) VALUES
    (\'Platform Admin\'), (\'Lab Director\'), (\'Lab Collaborator\'),
    (\'Lab Reader\'), (\'Bioinformatics User\'), (\'Data Analyst\')
ON CONFLICT DO NOTHING;
""",
        ow,
        dry,
    )

    write(
        BACKEND / "db" / "migrations" / "env.py",
        """
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys
import os

# Add backend/ to path so config.py is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from config import get_settings

config = context.config
settings = get_settings()

# Override sqlalchemy.url from our Settings object
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
""",
        ow,
        dry,
    )

    # =========================================================================
    # AUTH
    # =========================================================================

    write(BACKEND / "backend" / "auth" / "__init__.py", "", ow, dry)

    write(
        BACKEND / "backend" / "auth" / "oauth.py",
        '''
import httpx
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from config import get_settings
from database import execute_query

settings = get_settings()
GOOGLE_TOKEN_URL  = "https://oauth2.googleapis.com/token"
ACCESS_TOKEN_TTL  = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=7)


async def exchange_google_code(code: str, redirect_uri: str) -> dict[str, str]:
    """Exchange Google auth code for user email and name."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "redirect_uri":  redirect_uri,
            "grant_type":    "authorization_code",
        })
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange Google auth code.")
    payload = jwt.decode(
        resp.json()["id_token"], options={"verify_signature": False}
    )
    return {"email": payload["email"], "name": payload.get("name", "")}


def issue_access_token(user_id: int, email: str) -> str:
    return jwt.encode({
        "sub":   str(user_id),
        "email": email,
        "exp":   datetime.now(timezone.utc) + ACCESS_TOKEN_TTL,
        "type":  "access",
    }, settings.secret_key, algorithm="HS256")


def issue_refresh_token(user_id: int, email: str) -> str:
    return jwt.encode({
        "sub":   str(user_id),
        "email": email,
        "exp":   datetime.now(timezone.utc) + REFRESH_TOKEN_TTL,
        "type":  "refresh",
    }, settings.secret_key, algorithm="HS256")


def check_domain_whitelist(email: str) -> bool:
    domain = email.split("@")[-1].lower()
    rows = execute_query(
        "SELECT 1 FROM domain_whitelist WHERE LOWER(domain) = :d LIMIT 1",
        {"d": domain},
    )
    return bool(rows)


def get_user_by_email(email: str) -> dict | None:
    rows = execute_query(
        "SELECT * FROM users WHERE email = :e AND is_active = TRUE LIMIT 1",
        {"e": email},
    )
    return rows[0] if rows else None
''',
        ow,
        dry,
    )

    write(
        BACKEND / "backend" / "auth" / "guards.py",
        '''
from fastapi import Request, HTTPException
import jwt
from config import get_settings
from database import execute_query

settings = get_settings()


def get_current_user(request: Request) -> dict:
    """
    Local dev (ENV=local): returns the mock user from settings.mock_user_email.
    Production: validates JWT access cookie.
    """
    if settings.env == "local":
        rows = execute_query(
            "SELECT * FROM users WHERE email = :e AND is_active = TRUE LIMIT 1",
            {"e": settings.mock_user_email},
        )
        return rows[0] if rows else {
            "id": 1, "email": settings.mock_user_email, "name": "Dev User",
            "is_platform_admin": True, "is_data_analyst": False,
            "is_active": True, "organization_id": 1,
        }

    token = request.cookies.get("access")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Access token expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")

    rows = execute_query(
        "SELECT id, email, name, is_platform_admin, is_data_analyst, "
        "is_active, organization_id FROM users "
        "WHERE id = :uid AND is_active = TRUE LIMIT 1",
        {"uid": payload["sub"]},
    )
    if not rows:
        raise HTTPException(status_code=401, detail="User not found or inactive.")
    return rows[0]


def get_user_lab_membership(user_id: int, lab_id: int) -> dict | None:
    rows = execute_query(
        "SELECT lm.*, pg.name AS permission_group_name, lm.is_lab_director "
        "FROM lab_membership lm "
        "JOIN permission_groups pg ON pg.id = lm.permission_group_id "
        "WHERE lm.user_id = :uid AND lm.lab_id = :lid LIMIT 1",
        {"uid": user_id, "lid": lab_id},
    )
    return rows[0] if rows else None


def require_platform_admin(current_user: dict) -> None:
    if not current_user.get("is_platform_admin"):
        raise HTTPException(status_code=403, detail="Platform Admin required.")


def require_lab_director(current_user: dict, lab_id: int) -> None:
    if current_user.get("is_platform_admin"):
        return
    m = get_user_lab_membership(current_user["id"], lab_id)
    if not m or not m.get("is_lab_director"):
        raise HTTPException(status_code=403, detail="Lab Director required.")


def require_lab_access(current_user: dict, lab_id: int) -> None:
    if current_user.get("is_platform_admin"):
        return
    if get_user_lab_membership(current_user["id"], lab_id):
        return
    rows = execute_query(
        "SELECT 1 FROM project_membership pm "
        "JOIN projects p ON p.id = pm.project_id "
        "WHERE pm.user_id = :uid AND p.lab_id = :lid LIMIT 1",
        {"uid": current_user["id"], "lid": lab_id},
    )
    if not rows:
        raise HTTPException(status_code=403, detail="Lab access required.")
''',
        ow,
        dry,
    )

    write(
        BACKEND / "backend" / "auth" / "dependencies.py",
        '''
from fastapi import Request, Depends
from auth.guards import get_current_user


def current_user(request: Request) -> dict:
    """FastAPI dependency — inject current user into route handlers."""
    return get_current_user(request)
''',
        ow,
        dry,
    )

    # =========================================================================
    # VALIDATOR AND HARMONIZER
    # =========================================================================

    write(
        BACKEND / "backend" / "validator.py",
        '''
"""
JACKPOT LinkML validator.

Validates sample metadata dicts against jackpot_schema v4.1.
Returns a ValidationResult with valid flag, field-level errors, and warnings.

All ingest paths (GUI upload, CSV batch, signed URL) call validate_sample()
before writing any record to the database.
"""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
import re

# Schema path — relative to where the API process runs (jackpot-backend/)
SCHEMA_PATH = Path("schema/schema/jackpot_schema.yaml")

# Required fields for every sample regardless of source_type
BASE_REQUIRED = [
    "sample_id", "organism_name", "source_type", "date_collected",
    "collection_location_country", "sequencing_platform", "sequencing_lab",
    "type_of_experiment", "library_preparation_method",
    "sequencing_protocol", "collection_facility",
    "purpose_for_collection",
]

# Additional required fields per source_type
SOURCE_REQUIRED: dict[str, list[str]] = {
    "Human": ["adhs_medsis_id", "biospecimen_type", "reason_for_collection",
              "host_disease"],
    "Wildlife": ["host_species", "biospecimen_type", "host_disease"],
    "CompanionAnimal": ["host_species", "biospecimen_type", "host_disease"],
    "Livestock": ["host_species", "biospecimen_type", "livestock_products",
                  "host_disease"],
    "Vector": ["vector_species", "biospecimen_type"],
    "Wastewater": ["population_served", "sample_type", "sample_matrix",
                   "pretreatment", "concentration_method", "flow_rate_mgd"],
    "Water": ["water_temperature_c", "turbidity_ntu", "ph", "salinity_ppm"],
    "Air": ["air_source", "airflow_rate_m3_s", "pm25_ug_m3", "pm10_ug_m3"],
    "Soil": ["soil_site_type", "sample_depth_cm"],
    "Surface": ["indoor_space", "indoor_surface", "surface_material"],
    "Food": ["food_location_type", "food_product_type"],
    "ProduceAg": ["plant_species", "produce_water_source",
                  "near_animal_agriculture"],
}

# Recommended (non-required) fields that produce warnings when absent
RECOMMENDED: list[str] = [
    "collection_location_state", "strain", "sequencing_instrument",
    "coverage_depth", "genome_completeness",
]

# Valid enum values loaded once at import time
# These mirror OrganismNameEnum, SequencingPlatformEnum, SharingLevelEnum,
# ExperimentTypeEnum, ScrubStatusEnum, PIIScanStatusEnum from the schema.
# Keeping them here avoids a full LinkML parse on every request.
VALID_SHARING_LEVELS  = {"PRIVATE", "LAB", "DISCOVERABLE", "PUBLIC"}
VALID_SCRUB_STATUSES  = {"PENDING", "IN_PROGRESS", "COMPLETE", "FAILED", "SKIPPED"}
VALID_PII_STATUSES    = {"PENDING", "COMPLETE", "PII_DETECTED", "FAILED"}
VALID_INGEST_METHODS  = {"gui", "csv", "rsync", "curl", "globus"}
VALID_SOURCE_TYPES    = set(SOURCE_REQUIRED.keys())
VALID_PLATFORMS = {
    "Illumina", "Oxford_Nanopore", "PacBio", "Ion_Torrent", "Other",
}
VALID_EXPERIMENT_TYPES = {
    "WGS", "WES", "RNAseq", "shotgun_DNA_sequencing",
    "amplicon_sequencing", "targeted_sequencing",
}
VALID_VADR_STATUSES = {"PASS", "FAIL", "SKIP", "PENDING"}


@dataclass
class ValidationResult:
    valid:    bool
    errors:   list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_sample(data: dict) -> ValidationResult:
    """
    Validate a sample metadata dict against the JACKPOT schema.
    Returns ValidationResult(valid, errors, warnings).

    Errors  → ingest is rejected; user must fix before re-submitting.
    Warnings → ingest proceeds; user is notified but no action required.
    """
    errors:   list[str] = []
    warnings: list[str] = []

    # ── Base required fields ──────────────────────────────────────────────
    for field_name in BASE_REQUIRED:
        val = data.get(field_name)
        if val is None or (isinstance(val, (str, list)) and not val):
            errors.append(f"Missing required field: {field_name}")

    # ── Enum validation ───────────────────────────────────────────────────
    source_type = data.get("source_type", "")
    if source_type and source_type not in VALID_SOURCE_TYPES:
        errors.append(
            f"Invalid source_type '{source_type}'. "
            f"Must be one of: {sorted(VALID_SOURCE_TYPES)}"
        )

    platform = data.get("sequencing_platform", "")
    if platform and platform not in VALID_PLATFORMS:
        errors.append(
            f"Invalid sequencing_platform '{platform}'. "
            f"Must be one of: {sorted(VALID_PLATFORMS)}"
        )

    exp_type = data.get("type_of_experiment", "")
    if exp_type and exp_type not in VALID_EXPERIMENT_TYPES:
        errors.append(
            f"Invalid type_of_experiment '{exp_type}'. "
            f"Must be one of: {sorted(VALID_EXPERIMENT_TYPES)}"
        )

    sharing = data.get("sharing_level", "")
    if sharing and sharing not in VALID_SHARING_LEVELS:
        errors.append(
            f"Invalid sharing_level '{sharing}'. "
            f"Must be one of: {sorted(VALID_SHARING_LEVELS)}"
        )

    vadr = data.get("vadr_status", "")
    if vadr and vadr not in VALID_VADR_STATUSES:
        errors.append(
            f"Invalid vadr_status '{vadr}'. "
            f"Must be one of: {sorted(VALID_VADR_STATUSES)}"
        )

    # ── Date validation ───────────────────────────────────────────────────
    raw_date = data.get("date_collected")
    if raw_date:
        try:
            if isinstance(raw_date, str):
                collected = date.fromisoformat(raw_date)
            elif isinstance(raw_date, date):
                collected = raw_date
            else:
                raise ValueError("not a date")
            if collected > date.today():
                errors.append("date_collected cannot be in the future.")
            elif (date.today() - collected).days > 365 * 5:
                warnings.append(
                    "date_collected is more than 5 years in the past — "
                    "please verify this is correct."
                )
        except ValueError:
            errors.append(
                f"date_collected '{raw_date}' is not a valid ISO 8601 date (YYYY-MM-DD)."
            )

    raw_seq_date = data.get("date_sequenced")
    if raw_seq_date and raw_date:
        try:
            if isinstance(raw_seq_date, str):
                seq_date = date.fromisoformat(raw_seq_date)
            elif isinstance(raw_seq_date, date):
                seq_date = raw_seq_date
            else:
                raise ValueError
            if seq_date > date.today():
                errors.append("date_sequenced cannot be in the future.")
            if isinstance(raw_date, str):
                coll = date.fromisoformat(raw_date)
            else:
                coll = raw_date
            if seq_date < coll:
                errors.append("date_sequenced cannot be before date_collected.")
        except ValueError:
            errors.append(
                f"date_sequenced '{raw_seq_date}' is not a valid ISO 8601 date."
            )

    # ── Source-type-specific required fields ──────────────────────────────
    if source_type in SOURCE_REQUIRED:
        for field_name in SOURCE_REQUIRED[source_type]:
            val = data.get(field_name)
            if val is None or (isinstance(val, (str, list)) and not val):
                errors.append(
                    f"Missing required field for {source_type} samples: {field_name}"
                )

    # ── Numeric range checks ──────────────────────────────────────────────
    numeric_ranges: dict[str, tuple[float, float]] = {
        "host_age":           (0, 120),
        "ct_value":           (0, 50),
        "ph":                 (0, 14),
        "soil_ph":            (0, 14),
        "turbidity_ntu":      (0, 4000),
        "genome_completeness":(0, 100),
        "nextclade_qc_score": (0, 100),
    }
    for field_name, (lo, hi) in numeric_ranges.items():
        val = data.get(field_name)
        if val is not None:
            try:
                fval = float(val)
                if not (lo <= fval <= hi):
                    if field_name == "turbidity_ntu" and fval > 4000:
                        warnings.append(
                            f"turbidity_ntu={fval} is above 4000 NTU — "
                            "please confirm (possible decimal error)."
                        )
                    else:
                        errors.append(
                            f"{field_name}={fval} is outside expected range "
                            f"[{lo}, {hi}]."
                        )
            except (TypeError, ValueError):
                errors.append(f"{field_name} must be numeric, got '{val}'.")

    # ── URI scheme check ──────────────────────────────────────────────────
    for uri_field in ("fastq_r1_uri", "fastq_r2_uri", "consensus_fasta_uri"):
        uri = data.get(uri_field)
        if uri and not (
            uri.startswith("gs://") or
            uri.startswith("s3://") or
            uri.startswith("drs://")
        ):
            warnings.append(
                f"{uri_field} '{uri}' does not use a recognised URI scheme "
                "(expected gs://, s3://, or drs://)."
            )

    # ── Recommended fields ────────────────────────────────────────────────
    for field_name in RECOMMENDED:
        val = data.get(field_name)
        if val is None or (isinstance(val, str) and not val):
            warnings.append(
                f"Recommended field '{field_name}' is missing. "
                "Consider providing it for better data quality."
            )

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
''',
        ow,
        dry,
    )

    write(
        BACKEND / "backend" / "harmonizer.py",
        '''
"""
JACKPOT CSV column harmonizer.

Maps raw CSV column names to JACKPOT schema field names using a
mapping_config YAML file. Called by the batch ingest router before
validate_sample().

Mapping config format (see schema/mapping_configs/asu_human_v1.yaml):
    source_format: asu_human_v1
    target_class: HumanSample
    column_mappings:
      "Raw Column Name": schema_field_name
    file_detection:
      files_column: "FASTQ files"
      separator: ";"
      auto_detect_pairs: true
"""

from pathlib import Path
from typing import Any
import yaml


_MAPPING_DIR = Path("schema/schema/mapping_configs")
_cache: dict[str, dict] = {}


def load_mapping(mapping_name: str) -> dict:
    """
    Load a mapping config YAML by name (without .yaml extension).
    Results are cached in memory for the process lifetime.

    Example: load_mapping("asu_human_v1")
    """
    if mapping_name in _cache:
        return _cache[mapping_name]

    path = _MAPPING_DIR / f"{mapping_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Mapping config '{mapping_name}' not found at {path}. "
            f"Available: {[p.stem for p in _MAPPING_DIR.glob('*.yaml')]}"
        )
    with open(path) as f:
        config = yaml.safe_load(f)
    _cache[mapping_name] = config
    return config


def harmonize_row(raw: dict[str, Any], mapping: dict) -> dict[str, Any]:
    """
    Apply a mapping config to a single CSV row dict.

    Returns a new dict with JACKPOT schema field names as keys.
    Fields already using schema names pass through unchanged.
    Unknown columns are preserved with their original names.
    """
    column_map: dict[str, str] = mapping.get("column_mappings", {})
    result: dict[str, Any] = {}

    for raw_key, value in raw.items():
        # Skip empty values
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        # Map to schema field name if a mapping exists, else keep as-is
        schema_key = column_map.get(raw_key, raw_key)
        result[schema_key] = value.strip() if isinstance(value, str) else value

    return result


def harmonize_csv(
    rows: list[dict[str, Any]],
    mapping_name: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Harmonize all rows in a CSV using a named mapping config.

    Returns (harmonized_rows, warnings).
    Warnings are generated for unknown columns not in the mapping.
    """
    mapping = load_mapping(mapping_name)
    column_map: dict[str, str] = mapping.get("column_mappings", {})
    harmonized: list[dict[str, Any]] = []
    warnings: list[str] = []

    if rows:
        unknown = [k for k in rows[0] if k not in column_map and k not in column_map.values()]
        if unknown:
            warnings.append(
                f"Unknown columns not in mapping '{mapping_name}': "
                f"{unknown}. They will be passed through unchanged."
            )

    for row in rows:
        harmonized.append(harmonize_row(row, mapping))

    return harmonized, warnings
''',
        ow,
        dry,
    )

    # =========================================================================
    # ROUTERS — fully implemented where designed, stubs elsewhere
    # =========================================================================

    write(BACKEND / "backend" / "routers" / "__init__.py", "", ow, dry)

    # auth router
    write(
        BACKEND / "backend" / "routers" / "auth.py",
        '''
from fastapi import APIRouter, Request, Response, HTTPException
from auth.oauth import (
    exchange_google_code, issue_access_token, issue_refresh_token,
    check_domain_whitelist, get_user_by_email,
)
from config import get_settings

router  = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()


@router.post("/google/login")
async def google_login(code: str, request: Request, response: Response) -> dict:
    """Exchange Google auth code for JWT cookies."""
    redirect_uri = settings.google_oauth_redirect_url
    user_info = await exchange_google_code(code, redirect_uri)
    email = user_info["email"]

    if not check_domain_whitelist(email):
        raise HTTPException(
            status_code=403,
            detail=f"Domain '{email.split('@')[1]}' is not authorised. "
                   "Contact a Platform Admin.",
        )

    user = get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=403,
            detail="Account not found. A Platform Admin must create your "
                   "account before you can log in.",
        )

    access_token  = issue_access_token(user["id"], email)
    refresh_token = issue_refresh_token(user["id"], email)

    response.set_cookie("access",  access_token,  httponly=True, secure=True,
                        samesite="lax", max_age=900)
    response.set_cookie("refresh", refresh_token, httponly=True, secure=True,
                        samesite="lax", max_age=604800)

    return {"email": email, "name": user.get("name", "")}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie("access")
    response.delete_cookie("refresh")
    return {"status": "logged out"}
''',
        ow,
        dry,
    )

    # gisaid router — fully implemented (from architecture doc)
    write(
        BACKEND / "backend" / "routers" / "gisaid.py",
        '''
import csv
import io
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from auth.guards import get_current_user, require_lab_access
from database import execute_query

router = APIRouter(prefix="/api/v1/gisaid", tags=["gisaid"])

GISAID_SARS_COV2_COLUMNS: list[str] = [
    "Virus name", "Type", "Passage details/history", "Collection date",
    "Location", "Additional location information", "Host",
    "Additional host information", "Gender", "Patient age",
    "Patient status", "Specimen source", "Outbreak",
    "Last vaccinated", "Treatment", "Sequencing technology",
    "Assembly method", "Coverage", "Originating lab", "Address",
    "Sample ID given by the originating laboratory",
    "Submitting lab", "Address_submitting",
    "Sample ID given by the submitting laboratory",
    "Authors", "Submitter", "GISAID Accession ID",
]


@router.post("/export/{lab_id}")
def export_gisaid_csv(
    lab_id: int, sample_ids: list[int], pathogen: str, request: Request,
) -> StreamingResponse:
    """
    Generate a GISAID-compatible CSV for the specified samples.
    Supports SARS-CoV-2 (EpiCoV), Influenza (EpiFlu), Mpox (EpiPox).
    """
    user = get_current_user(request)
    require_lab_access(user, lab_id)

    if not sample_ids:
        raise HTTPException(status_code=400, detail="No sample IDs provided.")

    placeholders = ",".join(f":id_{i}" for i in range(len(sample_ids)))
    params = {f"id_{i}": sid for i, sid in enumerate(sample_ids)}
    params["lab_id"] = lab_id

    samples = execute_query(
        f"""
        SELECT s.*, u.email AS owner_email, l.display_name AS lab_name
        FROM samples s
        JOIN users u ON u.id = s.owner_id
        JOIN labs l  ON l.id = s.lab_id
        WHERE s.id IN ({placeholders})
          AND s.lab_id = :lab_id AND s.is_deleted = FALSE
        """,
        params,
    )
    if not samples:
        raise HTTPException(status_code=404, detail="No samples found.")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=GISAID_SARS_COV2_COLUMNS,
                            extrasaction="ignore")
    writer.writeheader()

    for s in samples:
        row = {
            "Virus name": (
                f"hCoV-19/{s[\'collection_location_country\'].replace(\' \', \'_\')}/"
                f"{s[\'sample_id\']}/{str(s[\'date_collected\'])[:4]}"
            ),
            "Type":                 "betacoronavirus",
            "Passage details/history": "Original",
            "Collection date":      str(s.get("date_collected", "")),
            "Location": (
                f"North America / {s.get(\'collection_location_country\', \'\')} / "
                f"{s.get(\'collection_location_state\', \'\')}"
            ),
            "Additional location information": s.get("collection_location_county", ""),
            "Host": "Human" if s["source_type"] == "Human"
                    else s.get("host_species", ""),
            "Gender":               s.get("host_sex", "unknown"),
            "Patient age":          s.get("host_age", ""),
            "Patient status":       s.get("clinical_outcome", "unknown"),
            "Specimen source":      s.get("sequencing_protocol", ""),
            "Last vaccinated":      s.get("vaccination_status", ""),
            "Sequencing technology":s.get("sequencing_platform", ""),
            "Assembly method":      s.get("assembly_method", ""),
            "Coverage":             s.get("coverage_depth", ""),
            "Originating lab":      s.get("lab_name", ""),
            "Sample ID given by the originating laboratory": s["sample_id"],
            "Submitting lab":       s.get("lab_name", ""),
            "Sample ID given by the submitting laboratory":  s["sample_id"],
            "Submitter":            s.get("owner_email", ""),
            "GISAID Accession ID":  s.get("gisaid_accession", ""),
        }
        writer.writerow(row)

    output.seek(0)
    filename = f"gisaid_{pathogen}_{datetime.now().strftime(\'%Y%m%d\')}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
''',
        ow,
        dry,
    )

    # Stub routers — these get full implementations in later sessions
    stub_routers = [
        "samples",
        "ingest",
        "organizations",
        "labs",
        "projects",
        "users",
        "datasets",
        "sample_access",
        "dataset_access",
        "archive_requests",
        "ncbi_submissions",
        "notifications",
        "domain_whitelist",
        "sequencing_labs",
        "billing",
        "tokens",
        "saved_searches",
        "dataharmonizer",
        "pipelines",
    ]
    for name in stub_routers:
        write(
            BACKEND / "backend" / "routers" / f"{name}.py",
            f'''
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/{name.replace("_", "-")}", tags=["{name}"])


@router.get("/")
def list_{name}() -> dict:
    """Stub — implement in Month 1 sprint."""
    return {{"status": "not implemented", "router": "{name}"}}
''',
            ow,
            dry,
        )

    # =========================================================================
    # FRONTEND — app.py written by write_files.py; pages are stubs
    # =========================================================================

    front_pages = [
        "search",
        "upload",
        "data_entry",
        "my_samples",
        "datasets",
        "access_requests",
        "archive_requests",
        "ncbi_submission",
        "gisaid_export",
        "lab_admin",
        "org_admin",
        "notifications",
        "billing",
        "pipelines",
    ]
    for name in front_pages:
        title = name.replace("_", " ").title()
        write(
            FRONT / "frontend" / "pages" / f"{name}.py",
            f'''
import streamlit as st

def render(api_base: str, user_email: str, me: dict) -> None:
    """Stub — implement in Month 1 sprint."""
    st.title("{title}")
    st.info("This page is not yet implemented.")
''',
            ow,
            dry,
        )

    front_components = ["sample_card", "permission_check", "notification_badge"]
    for name in front_components:
        write(
            FRONT / "frontend" / "components" / f"{name}.py",
            f"""
# {name} component — implement as needed
""",
            ow,
            dry,
        )

    # =========================================================================
    # PIPELINES
    # =========================================================================

    write(
        BACKEND / "pipelines" / "nextflow.config",
        """
// JACKPOT Nextflow configuration
// Used by ingest_gate.nf and pipeline runs on GCP Batch

manifest {
    name        = "jackpot-pipelines"
    version     = "4.0.0"
    description = "JACKPOT pathogen genomics pipelines"
}

process {
    executor = "google-batch"

    withName: "SCRUB_HUMAN_READS" {
        machineType = "n2-standard-4"
        container   = "ncbi/sra-human-scrubber:latest"
    }
}

google {
    project = System.env.PROJECT_ID ?: "jackpot-local"
    region  = "us-west1"
    batch {
        serviceAccountEmail = System.env.GCP_SERVICE_ACCOUNT ?: ""
    }
}

// Local development: run without GCP Batch
if (System.env.ENV == "local") {
    process.executor = "local"
}
""",
        ow,
        dry,
    )

    write(
        BACKEND / "pipelines" / "ingest_gate.nf",
        '''
nextflow.enable.dsl = 2

// Ingest gate pipeline — runs SRA-human-scrubber on every uploaded FASTQ.
// Triggered via Cloud Pub/Sub when files land in the staging bucket.
// See Section 14 of jackpot_architecture_v4.md for full documentation.

params.staging_bucket   = "gs://${System.env.PROJECT_ID}-staging"
params.sequences_bucket = "gs://${System.env.PROJECT_ID}-sequences"
params.api_url          = System.env.JACKPOT_API_URL ?: "http://localhost:8000"

process SCRUB_HUMAN_READS {
    container   "ncbi/sra-human-scrubber:latest"
    errorStrategy "retry"
    maxRetries 2

    input:
    tuple val(sample_id), val(org_slug), val(lab_prefix),
          path(r1), path(r2_or_empty)

    output:
    tuple val(sample_id), val(org_slug), val(lab_prefix),
          path("${sample_id}_R1_scrubbed.fastq.gz"),
          path("${sample_id}_R2_scrubbed.fastq.gz"), optional: true

    script:
    def r2_cmd = r2_or_empty.name != "empty" ? """
        scrub_human_data --input ${r2_or_empty} \\
            --output ${sample_id}_R2_scrubbed.fastq.gz
    """ : ""
    """
    scrub_human_data --input ${r1} \\
        --output ${sample_id}_R1_scrubbed.fastq.gz
    ${r2_cmd}
    """
}

process REGISTER_AND_MOVE {
    input:
    tuple val(sample_id), val(org_slug), val(lab_prefix),
          path(r1_scrubbed), path(r2_scrubbed)

    script:
    def r2_dest = r2_scrubbed.name != "empty" ?
        "${params.sequences_bucket}/${org_slug}/${lab_prefix}/${sample_id}/${r2_scrubbed}" : ""
    """
    gcloud storage cp ${r1_scrubbed} \\
        ${params.sequences_bucket}/${org_slug}/${lab_prefix}/${sample_id}/${r1_scrubbed}

    if [ -n "${r2_dest}" ]; then
        gcloud storage cp ${r2_scrubbed} ${r2_dest}
    fi

    curl -s -X PATCH ${params.api_url}/api/v1/samples/${sample_id}/scrub-status \\
        -H "Content-Type: application/json" \\
        -d "{\\"scrub_status\\":\\"COMPLETE\\",\\"fastq_r1_uri\\":\\"${params.sequences_bucket}/${org_slug}/${lab_prefix}/${sample_id}/${r1_scrubbed}\\",\\"fastq_r2_uri\\":\\"${r2_dest}\\"}"
    """
}

workflow {
    Channel
        .fromPath("${params.staging_bucket}/**/*.fastq.gz")
        .map { f ->
            def parts = f.parent.toString().split("/")
            tuple(parts[-1], parts[-3], parts[-2], f)
        }
        .groupTuple(by: [0, 1, 2])
        .map { sid, org, lab, files ->
            def r1 = files.find { it.name.contains("_R1") } ?: files[0]
            def r2 = files.find { it.name.contains("_R2") } ?: file("empty")
            tuple(sid, org, lab, r1, r2)
        }
        | SCRUB_HUMAN_READS
        | REGISTER_AND_MOVE
}
''',
        ow,
        dry,
    )

    # =========================================================================
    # SCRIPTS
    # =========================================================================

    write(
        BACKEND / "scripts" / "portal_to_tostadas.py",
        '''
#!/usr/bin/env python3
"""
Convert JACKPOT sample metadata JSON to TOSTADAS config.yaml.
Maps portal schema fields to NCBI BioSample attribute names.

Usage:
    python3 portal_to_tostadas.py \\
        --input submission_metadata.json \\
        --output tostadas_config/
"""

import argparse
import json
from pathlib import Path

import yaml

BIOSAMPLE_FIELD_MAP: dict[str, str] = {
    "organism_name":               "organism",
    "strain":                      "strain",
    "isolate":                     "isolate",
    "serotype":                    "serotype",
    "date_collected":              "collection_date",
    "collection_location_country": "geo_loc_name",
    "host_species":                "host",
    "host_age":                    "host_age",
    "host_sex":                    "host_sex",
    "sequencing_platform":         "sequencing_platform",
    "library_preparation_method":  "library_strategy",
    "env_broad_scale":             "env_broad_scale",
    "env_local_scale":             "env_local_scale",
    "env_medium":                  "env_medium",
    "pango_lineage":               "lineage",
}

SOURCE_TYPE_PACKAGE: dict[str, str] = {
    "Human":         "MIMS.me.human-associated.6.0",
    "Wildlife":      "MIMS.me.animal-associated.6.0",
    "CompanionAnimal":"MIMS.me.animal-associated.6.0",
    "Livestock":     "MIMS.me.animal-associated.6.0",
    "Wastewater":    "MIMS.me.wastewater.6.0",
    "Water":         "MIMS.me.water.6.0",
    "Air":           "MIMS.me.air.6.0",
    "Soil":          "MIMS.me.soil.6.0",
    "Surface":       "MIMS.me.built_environment.6.0",
}


def convert_sample(sample: dict) -> dict:
    biosample: dict = {}
    for portal_field, ncbi_attr in BIOSAMPLE_FIELD_MAP.items():
        val = sample.get(portal_field)
        if val:
            biosample[ncbi_attr] = str(val)

    country = sample.get("collection_location_country", "")
    state   = sample.get("collection_location_state", "")
    biosample["geo_loc_name"] = f"{country}: {state}" if state else country
    biosample["package"] = SOURCE_TYPE_PACKAGE.get(
        sample.get("source_type", ""), "Generic.1.0"
    )

    return {
        "sample_name":     sample["sample_id"],
        "bioproject":      sample.get("bioproject_accession", ""),
        "biosample_attrs": biosample,
        "fastq_r1":        sample["fastq_r1_uri"],
        "fastq_r2":        sample.get("fastq_r2_uri", ""),
        "consensus_fasta": sample.get("consensus_fasta_uri", ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",  required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    samples   = data.get("samples", [data])
    converted = [convert_sample(s) for s in samples]
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = {"submission": {
        "submission_name": data.get("submission_name", "jackpot_submission"),
        "samples": converted,
    }}
    with open(output_dir / "config.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    print(f"Generated TOSTADAS config for {len(converted)} samples → {output_dir}")


if __name__ == "__main__":
    main()
''',
        ow,
        dry,
    )

    write(
        BACKEND / "scripts" / "migrate_from_apgap.py",
        '''
#!/usr/bin/env python3
"""
Migrate data from APGAP PostgreSQL to JACKPOT PostgreSQL.

Migrates: Organizations, Users, Labs, Projects, Lab Memberships,
          Project Memberships, Domain Whitelist.

Usage:
    APGAP_DB_URL=postgresql://user:pass@host:5432/apgap_db \\
        python3 migrate_from_apgap.py --dry-run

    APGAP_DB_URL=postgresql://user:pass@host:5432/apgap_db \\  # pragma: allowlist secret
        python3 migrate_from_apgap.py
"""

import argparse
import os
import sys
from sqlalchemy import create_engine, text

APGAP_DB_URL  = os.environ.get("APGAP_DB_URL", "")
JACKPOT_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://jackpot:jackpot@localhost:5432/jackpot_db",
)


def migrate(dry_run: bool = True) -> None:
    if not APGAP_DB_URL:
        print("ERROR: Set APGAP_DB_URL environment variable first.")
        sys.exit(1)

    apgap   = create_engine(APGAP_DB_URL)
    jackpot = create_engine(JACKPOT_DB_URL)

    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"\\nJACKPOT migration from APGAP [{mode}]\\n")

    with apgap.connect() as src, jackpot.connect() as dst:

        # Organizations
        orgs = src.execute(text(
            "SELECT display_name, default_approve_analytical_dataset_requests "
            "FROM organizations WHERE active = TRUE"
        )).fetchall()
        print(f"  Organizations: {len(orgs)}")
        if not dry_run:
            for o in orgs:
                dst.execute(text(
                    "INSERT INTO organizations (display_name, "
                    "default_approve_analytical_dataset_requests) "
                    "VALUES (:name, :approve) ON CONFLICT DO NOTHING"
                ), {"name": o[0], "approve": o[1]})

        # Domain whitelist
        domains = src.execute(text(
            "SELECT domain, description FROM domain_whitelist"
        )).fetchall()
        print(f"  Domain whitelist entries: {len(domains)}")
        if not dry_run:
            for d in domains:
                dst.execute(text(
                    "INSERT INTO domain_whitelist (domain, description) "
                    "VALUES (:domain, :desc) ON CONFLICT DO NOTHING"
                ), {"domain": d[0], "desc": d[1] or ""})

        # Users (without FKs first — created_by_id etc handled separately)
        users = src.execute(text(
            "SELECT email, name, is_platform_admin, is_data_analyst, is_active "
            "FROM users WHERE is_active = TRUE"
        )).fetchall()
        print(f"  Users: {len(users)}")
        if not dry_run:
            for u in users:
                dst.execute(text(
                    "INSERT INTO users "
                    "(email, name, is_platform_admin, is_data_analyst, is_active) "
                    "VALUES (:email, :name, :admin, :analyst, :active) "
                    "ON CONFLICT DO NOTHING"
                ), {
                    "email": u[0], "name": u[1] or "",
                    "admin": u[2], "analyst": u[3], "active": u[4],
                })

        if not dry_run:
            dst.commit()

    print(f"\\nMigration [{mode}] complete.")
    if dry_run:
        print("Run without --dry-run to apply changes.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=False)
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
''',
        ow,
        dry,
    )

    # =========================================================================
    # TESTS
    # =========================================================================

    write(
        BACKEND / "tests" / "conftest.py",
        """
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from testcontainers.postgres import PostgresContainer
from sqlalchemy import create_engine, text
from backend.main import app
from backend.config import get_settings


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16") as pg:
        yield pg


@pytest.fixture(scope="session")
def test_db_url(postgres_container):
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session", autouse=True)
def initialize_test_db(test_db_url):
    engine = create_engine(test_db_url)
    with open("db/init.sql") as f:
        sql = f.read()
    with engine.connect() as conn:
        for stmt in sql.split(";"):
            s = stmt.strip()
            if s:
                try:
                    conn.execute(text(s))
                except Exception:
                    pass  # ignore IF NOT EXISTS errors on re-run
        conn.commit()
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def override_settings(test_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL",       test_db_url)
    monkeypatch.setenv("ENV",                "local")
    monkeypatch.setenv("MOCK_USER_EMAIL",    "gotero@linuxprophet.com")
    monkeypatch.setenv("STORAGE_ENDPOINT",   "http://localhost:9000")
    monkeypatch.setenv("STORAGE_ACCESS_KEY", "minioadmin")
    monkeypatch.setenv("STORAGE_SECRET_KEY", "minioadmin")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as c:
        yield c


@pytest.fixture
def valid_human_sample():
    return {
        "sample_id":                   "AZ-TEST-001",
        "organism_name":               "Severe acute respiratory syndrome coronavirus 2",
        "source_type":                 "Human",
        "date_collected":              "2026-01-15",
        "date_sequenced":              "2026-01-17",
        "collection_location_country": "United States",
        "collection_location_state":   "Arizona",
        "sequencing_platform":         "Illumina",
        "sequencing_lab":              "Otero Lab",
        "type_of_experiment":          "WGS",
        "library_preparation_method":  "ARTIC",
        "nucleic_acid_extraction_method": ["QIAamp DSP Viral RNA"],
        "sequencing_protocol":         "https://www.protocols.io/view/artic-v4-1",
        "collection_facility":         "Mayo Clinic Phoenix",
        "purpose_for_collection":      ["clinical"],
        "sharing_level":               "PRIVATE",
        "scrub_status":                "PENDING",
        "pii_scan_status":             "PENDING",
        "ingest_method":               "gui",
        "fastq_r1_uri": "gs://jackpot-sequences/asu/otero/AZ-TEST-001/R1.fastq.gz",
        "adhs_medsis_id":              "ADHS-2026-001",
        "biospecimen_type":            "nasopharyngeal_swab",
        "reason_for_collection":       ["clinical"],
        "host_disease":                ["covid-19"],
        "project_id":                  "1",
        "lab_id":                      "1",
    }
""",
        ow,
        dry,
    )

    write(
        BACKEND / "tests" / "test_validator.py",
        """
import pytest
from datetime import date, timedelta
from hypothesis import given, strategies as st
from backend.validator import validate_sample, ValidationResult


def test_valid_human_sample_passes(valid_human_sample):
    result = validate_sample(valid_human_sample)
    assert result.valid, f"Expected valid but got errors: {result.errors}"


@pytest.mark.parametrize("missing_field", [
    "sample_id", "organism_name", "source_type", "date_collected",
    "collection_location_country", "sequencing_platform", "fastq_r1_uri",
    "adhs_medsis_id",
])
def test_missing_required_field_fails(valid_human_sample, missing_field):
    data = {k: v for k, v in valid_human_sample.items() if k != missing_field}
    result = validate_sample(data)
    assert not result.valid
    assert any(missing_field in e for e in result.errors)


@pytest.mark.parametrize("bad_source", ["human", "HUMAN", "clinical", ""])
def test_invalid_source_type_fails(valid_human_sample, bad_source):
    result = validate_sample({**valid_human_sample, "source_type": bad_source})
    assert not result.valid


@pytest.mark.parametrize("platform", [
    "Illumina", "Oxford_Nanopore", "PacBio", "Ion_Torrent", "Other",
])
def test_all_valid_platforms_pass(valid_human_sample, platform):
    result = validate_sample({**valid_human_sample, "sequencing_platform": platform})
    assert result.valid


@pytest.mark.parametrize("bad_sharing", ["private", "open", "shared", ""])
def test_invalid_sharing_level_fails(valid_human_sample, bad_sharing):
    result = validate_sample({**valid_human_sample, "sharing_level": bad_sharing})
    assert not result.valid


@pytest.mark.parametrize("good_sharing", ["PRIVATE", "LAB", "DISCOVERABLE", "PUBLIC"])
def test_all_sharing_levels_pass(valid_human_sample, good_sharing):
    result = validate_sample({**valid_human_sample, "sharing_level": good_sharing})
    assert result.valid


def test_future_date_fails(valid_human_sample):
    future = (date.today() + timedelta(days=10)).isoformat()
    result = validate_sample({**valid_human_sample, "date_collected": future})
    assert not result.valid
    assert any("future" in e for e in result.errors)


def test_old_date_warns(valid_human_sample):
    old = "2015-01-01"
    result = validate_sample({**valid_human_sample, "date_collected": old})
    assert result.valid
    assert any("5 years" in w for w in result.warnings)


def test_invalid_vadr_status_fails(valid_human_sample):
    result = validate_sample({**valid_human_sample, "vadr_status": "UNKNOWN"})
    assert not result.valid


@pytest.mark.parametrize("vadr", ["PASS", "FAIL", "SKIP", "PENDING"])
def test_valid_vadr_statuses_pass(valid_human_sample, vadr):
    result = validate_sample({**valid_human_sample, "vadr_status": vadr})
    assert result.valid


def test_host_age_out_of_range_errors(valid_human_sample):
    result = validate_sample({**valid_human_sample, "host_age": 200})
    assert not result.valid


@given(st.text(min_size=0, max_size=200))
def test_any_organism_name_never_crashes(organism_name):
    result = validate_sample({"organism_name": organism_name, "source_type": "Human"})
    assert isinstance(result.valid, bool)
    assert isinstance(result.errors, list)
""",
        ow,
        dry,
    )

    write(
        BACKEND / "tests" / "test_epiweek.py",
        """
import pytest
from datetime import date
from backend.epiweek import compute_epiweeks


def test_all_fields_present():
    result = compute_epiweeks(date(2026, 3, 15))
    for key in ("mmwr_year", "mmwr_week", "iso_year", "iso_week"):
        assert key in result


def test_week_in_valid_range():
    for month in range(1, 13):
        result = compute_epiweeks(date(2026, month, 15))
        assert 1 <= result["mmwr_week"] <= 53
        assert 1 <= result["iso_week"]  <= 53


@pytest.mark.parametrize("input_date,expected_mmwr_week", [
    (date(2026, 1, 4),  2),
    (date(2026, 1, 11), 3),
    (date(2026, 3, 22), 13),
])
def test_specific_mmwr_weeks(input_date, expected_mmwr_week):
    result = compute_epiweeks(input_date)
    assert result["mmwr_week"] == expected_mmwr_week


def test_mmwr_and_iso_can_differ():
    # The week systems can give different years near Jan 1
    result = compute_epiweeks(date(2026, 1, 1))
    assert isinstance(result["mmwr_year"], int)
    assert isinstance(result["iso_year"],  int)
""",
        ow,
        dry,
    )

    write(
        BACKEND / "tests" / "test_permissions.py",
        """
import pytest
from unittest.mock import patch
from backend.auth.guards import (
    require_platform_admin, require_lab_director, require_lab_access,
)
from fastapi import HTTPException


def make_user(is_platform_admin=False, is_data_analyst=False, uid=1):
    return {
        "id": uid, "email": f"user{uid}@test.com",
        "is_platform_admin": is_platform_admin,
        "is_data_analyst":   is_data_analyst,
        "is_active": True, "organization_id": 1,
    }


def test_platform_admin_passes():
    require_platform_admin(make_user(is_platform_admin=True))


def test_non_admin_denied():
    with pytest.raises(HTTPException) as exc:
        require_platform_admin(make_user())
    assert exc.value.status_code == 403


def test_data_analyst_not_platform_admin():
    with pytest.raises(HTTPException):
        require_platform_admin(make_user(is_data_analyst=True))


def test_lab_director_passes():
    membership = {"lab_id": 5, "is_lab_director": True,
                  "permission_group_name": "Lab Director"}
    with patch("backend.auth.guards.get_user_lab_membership",
               return_value=membership):
        require_lab_director(make_user(uid=2), lab_id=5)


def test_platform_admin_bypasses_director_check():
    with patch("backend.auth.guards.get_user_lab_membership",
               return_value=None):
        require_lab_director(make_user(is_platform_admin=True), lab_id=5)


def test_lab_collaborator_not_director():
    membership = {"lab_id": 5, "is_lab_director": False,
                  "permission_group_name": "Lab Collaborator"}
    with patch("backend.auth.guards.get_user_lab_membership",
               return_value=membership):
        with pytest.raises(HTTPException) as exc:
            require_lab_director(make_user(uid=3), lab_id=5)
        assert exc.value.status_code == 403


@pytest.mark.parametrize("role", [
    "Lab Director", "Lab Collaborator", "Lab Reader", "Bioinformatics User",
])
def test_all_lab_roles_have_access(role):
    membership = {"lab_id": 5, "is_lab_director": role == "Lab Director",
                  "permission_group_name": role}
    with patch("backend.auth.guards.get_user_lab_membership",
               return_value=membership):
        require_lab_access(make_user(uid=5), lab_id=5)


def test_non_member_denied_lab_access():
    with patch("backend.auth.guards.get_user_lab_membership",
               return_value=None):
        with patch("backend.auth.guards.execute_query",
                   return_value=[]):
            with pytest.raises(HTTPException) as exc:
                require_lab_access(make_user(uid=7), lab_id=5)
            assert exc.value.status_code == 403
""",
        ow,
        dry,
    )

    write(
        BACKEND / "tests" / "test_samples_api.py",
        """
import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["project"] == "JACKPOT"


@pytest.mark.asyncio
async def test_samples_stub_responds(client):
    resp = await client.get("/api/v1/samples/")
    # Stub returns 200 with not-implemented message
    assert resp.status_code == 200
""",
        ow,
        dry,
    )

    write(
        BACKEND / "tests" / "test_file_detector.py",
        """
import pytest
from backend.file_detector import (
    detect_files, get_file_type, is_sequence_file, get_convenience_uris,
)


@pytest.mark.parametrize("filename,expected_type", [
    ("sample_R1.fastq",      "FASTQ"),
    ("sample_R1.fastq.gz",   "FASTQ"),
    ("sample_R1.fastq.bz2",  "FASTQ"),
    ("sample_R1.fq",         "FASTQ"),
    ("sample_R1.fq.gz",      "FASTQ"),
    ("sample_R1.fq.bz2",     "FASTQ"),
    ("assembly.fa",          "FASTA"),
    ("assembly.fa.gz",       "FASTA"),
    ("assembly.fna",         "FASTA"),
    ("assembly.fna.gz",      "FASTA"),
    ("assembly.fasta",       "FASTA"),
    ("assembly.fasta.gz",    "FASTA"),
    ("SAMPLE.FASTQ.GZ",      "FASTQ"),
    ("report.html",          "OTHER"),
    ("metadata.csv",         "OTHER"),
])
def test_get_file_type(filename, expected_type):
    assert get_file_type(filename) == expected_type


@pytest.mark.parametrize("r1,r2", [
    ("sample_R1.fastq.gz",   "sample_R2.fastq.gz"),
    ("sample_R1.fq.gz",      "sample_R2.fq.gz"),
    ("sample_R1.fq.bz2",     "sample_R2.fq.bz2"),
    ("sample_R1.fasta.gz",   "sample_R2.fasta.gz"),
    ("sample_R1.fa.gz",      "sample_R2.fa.gz"),
    ("sample_R1.fna.gz",     "sample_R2.fna.gz"),
    ("sample_1.fastq.gz",    "sample_2.fastq.gz"),
    ("sample_1.fq.gz",       "sample_2.fq.gz"),
    ("sample_reads_1.fq",    "sample_reads_2.fq"),
    ("sample_forward.fa.gz", "sample_reverse.fa.gz"),
])
def test_paired_detection(r1, r2):
    result = detect_files([r1, r2])
    assert result.has_paired, f"Expected paired: {result.warnings}"
    assert not result.warnings


def test_multilane_illumina():
    files = [
        "sample_L001_R1_001.fastq.gz", "sample_L001_R2_001.fastq.gz",
        "sample_L002_R1_001.fastq.gz", "sample_L002_R2_001.fastq.gz",
    ]
    result = detect_files(files)
    assert result.has_paired
    assert result.lane_count == 2


def test_nanopore_chunks():
    files = [f"barcode01_{i}.fq.gz" for i in range(4)]
    result = detect_files(files)
    assert result.has_unpaired
    assert not result.has_paired
    assert all(f.chunk_index is not None for f in result.files)


def test_r1_without_r2_warns():
    result = detect_files(["sample_R1.fastq.gz"])
    assert result.has_unpaired
    assert any("R2" in w for w in result.warnings)


def test_non_sequence_files_skipped():
    result = detect_files([
        "sample_R1.fastq.gz", "sample_R2.fastq.gz", "metadata.csv",
    ])
    assert len(result.files) == 2
    assert any("Skipped" in w for w in result.warnings)


def test_convenience_uris_simple_paired():
    result = detect_files(["AZ-001_R1.fastq.gz", "AZ-001_R2.fastq.gz"])
    uri_map = {
        "AZ-001_R1.fastq.gz": "gs://bucket/AZ-001_R1.fastq.gz",
        "AZ-001_R2.fastq.gz": "gs://bucket/AZ-001_R2.fastq.gz",
    }
    r1, r2 = get_convenience_uris(result, uri_map)
    assert r1 is not None and "R1" in r1
    assert r2 is not None and "R2" in r2


@pytest.mark.parametrize("filenames", [
    [], [""], ["single.fastq.gz"],
    ["a.fastq.gz", "b.fastq.gz", "c.fastq.gz"],
])
def test_never_raises(filenames):
    result = detect_files(filenames)
    assert isinstance(result.has_paired, bool)
    assert isinstance(result.warnings, list)
""",
        ow,
        dry,
    )

    write(
        BACKEND / "tests" / "test_gisaid_export.py",
        """
import pytest
from backend.routers.gisaid import GISAID_SARS_COV2_COLUMNS


def test_all_required_gisaid_columns_present():
    required = [
        "Virus name", "Type", "Collection date", "Location",
        "Host", "Gender", "Patient age", "Sequencing technology",
        "Originating lab", "Submitting lab", "Authors", "Submitter",
    ]
    for col in required:
        assert col in GISAID_SARS_COV2_COLUMNS, f"Missing: {col}"


@pytest.mark.asyncio
async def test_gisaid_export_empty_ids_returns_400(client):
    resp = await client.post(
        "/api/v1/gisaid/export/1",
        params={"pathogen": "SARS-CoV-2"},
        json=[],
    )
    assert resp.status_code == 400
""",
        ow,
        dry,
    )

    write(
        BACKEND / "tests" / "test_tostadas_converter.py",
        """
import pytest
from scripts.portal_to_tostadas import convert_sample, SOURCE_TYPE_PACKAGE


def minimal_sample(source_type="Human", **kwargs):
    base = {
        "sample_id":                   "AZ-001",
        "source_type":                 source_type,
        "organism_name":               "Severe acute respiratory syndrome coronavirus 2",
        "collection_location_country": "United States",
        "fastq_r1_uri":                "gs://bucket/R1.fastq.gz",
    }
    base.update(kwargs)
    return base


def test_human_gets_correct_package():
    result = convert_sample(minimal_sample())
    assert result["biosample_attrs"]["package"] == SOURCE_TYPE_PACKAGE["Human"]


def test_wastewater_gets_correct_package():
    result = convert_sample(minimal_sample(source_type="Wastewater"))
    assert result["biosample_attrs"]["package"] == SOURCE_TYPE_PACKAGE["Wastewater"]


def test_geo_loc_name_combines_country_and_state():
    result = convert_sample(minimal_sample(
        collection_location_country="United States",
        collection_location_state="Arizona",
    ))
    assert result["biosample_attrs"]["geo_loc_name"] == "United States: Arizona"


def test_geo_loc_name_country_only():
    result = convert_sample(minimal_sample())
    assert result["biosample_attrs"]["geo_loc_name"] == "United States"


def test_sample_name_is_sample_id():
    result = convert_sample(minimal_sample())
    assert result["sample_name"] == "AZ-001"


def test_missing_optional_fields_dont_crash():
    result = convert_sample(minimal_sample())
    assert result["fastq_r2"] == ""
    assert result["consensus_fasta"] == ""
""",
        ow,
        dry,
    )

    # =========================================================================
    # DOCS / CLAUDE.md
    # =========================================================================

    write(
        BACKEND / "docs" / "CLAUDE.md",
        """# CLAUDE.md — jackpot-backend

## Project: JACKPOT
Pathogen genomics platform for genomic epidemiology, bioinformatics,
and public health research. Successor to APGAP (ASU-RSE-Services).

## Tech Stack
- Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2
- PostgreSQL (local dev) / BigQuery (production)
- MinIO (local) / GCS (production) — same boto3 code, different endpoint
- LinkML v4.1 schema: schema/schema/jackpot_schema.yaml (git submodule)
- Authentication: Google OAuth 2.0 + JWT httponly cookies
- Environment management: uv — never use pip directly
- Tests: pytest + testcontainers (real PostgreSQL in tests)

## Directory Structure
```
backend/          FastAPI application code
  main.py         App entrypoint — add router imports here as you build them
  config.py       Settings class; ENV=local or gcp
  permissions.py  PermissionGroups enum — DO NOT rename values
  validator.py    LinkML-based metadata validator — gate on all ingest paths
  harmonizer.py   CSV column mapper using mapping_config YAMLs
  file_detector.py  NGS file pairing and extension detection — only place for this logic
  auth/           Google OAuth exchange + JWT middleware
  routers/        One file per API resource
db/
  init.sql        Reference schema — copy from Section 11.12 of arch doc
  migrations/     Alembic migration files — all schema changes go here
schema/           git submodule → jackpot-schema repo
  schema/
    jackpot_schema.yaml  Single source of truth for all metadata
tests/
scripts/
```

## Critical Rules — Read Before Making Any Change

1. **PermissionGroups enum values are sacred.**
   Values MUST match asu_apgap/utils/permissions.py exactly.
   DO NOT rename: "Platform Admin", "Lab Director", etc.

2. **All database schema changes go through Alembic.**
   Never edit db/init.sql directly in production.
   Command: `uv run alembic revision --autogenerate -m "description"`

3. **Regenerate Python models after any schema change.**
   Command: `uv run gen-pydantic schema/schema/jackpot_schema.yaml > backend/models_generated.py`

4. **Every state-changing endpoint calls log_audit().**
   Import from audit.py. Use the action name constants (CREATE_SAMPLE etc.).

5. **sequencing_lab is NOT a static enum.**
   Validated at runtime against the sequencing_labs database table.
   Unknown values: return 422 with message directing user to request workflow.

6. **All API routes must be prefixed /api/v1/**

7. **Use `uv run` for all Python commands. Never pip, never activate venv.**

8. **adhs_medsis_id is required for HumanSample. It is NOT the same as case_id.**
   adhs_medsis_id = ADHS-issued anonymized ID or exemption code.
   case_id = generic non-ADHS public health case identifier (CDC NEDSS etc.).

9. **Epiweek is computed at ingest, never by the user.**
   Call compute_epiweeks(date_collected) from epiweek.py before DB write.

10. **fastq_r1_uri and fastq_r2_uri are convenience fields, not the source of truth.**
    The sample_files table is the canonical per-file registry.
    These columns are auto-populated by get_convenience_uris() from file_detector.py
    for simple 2-file paired runs only.

11. **Never parse filenames anywhere except file_detector.py.**
    All NGS filename logic lives exclusively in backend/file_detector.py.

12. **Supported file extensions: .fastq, .fq, .fasta, .fa, .fna + .gz/.bz2.**
    To add a new extension: edit _FASTQ_BASES or _FASTA_BASES in file_detector.py only.

## Common Commands
```bash
# Development
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
uv run pytest
uv run pytest tests/test_validator.py -v
uv run pytest -k "test_paired" -v

# Database
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "add_new_column"
psql postgresql://jackpot:jackpot@localhost:5432/jackpot_db

# Schema
uv run gen-pydantic schema/schema/jackpot_schema.yaml > backend/models_generated.py
uv run gen-json-schema schema/schema/jackpot_schema.yaml > schema/schema/jackpot_schema.json
python3 -c "import yaml; yaml.safe_load(open(\'schema/schema/jackpot_schema.yaml\'))"

# Docker
docker compose up -d
docker compose ps
docker compose logs -f api
curl http://localhost:8000/health

# Submodule
git submodule update --remote schema
git add schema && git commit -m "chore: update schema submodule"
```

## APGAP Migration Compatibility
- Organization → Lab → Project → User hierarchy is identical
- PermissionGroups enum string values match APGAP exactly
- is_lab_director=TRUE on lab_membership = Lab Director
- Projects preserve all Seqera fields (workspace_id, compute_env_id, credentials_id)
- Migration script: scripts/migrate_from_apgap.py

## OrganismNameEnum (62 values)
Derived from ADHS mandatory reportable communicable diseases list.
Additions: Coccidioides immitis, Coccidioides posadasii (Valley fever),
metagenome (metagenomic samples), novel pathogen (emerging/exotic disease).
All values use NCBI Taxonomy names for BioSample/SRA/GenBank/GISAID compatibility.
Platform Admins add new values via the admin UI — never hardcode new organisms.

## Testing Philosophy
60% coverage minimum enforced in CI (pytest --cov-fail-under=60).
Priority order:
  1. backend/validator.py — every required field, every enum value, date checks
  2. backend/auth/guards.py — all six role combinations
  3. backend/file_detector.py — all extensions, all naming conventions
  4. backend/routers/ingest.py — valid upload, missing fields, file detection
  5. backend/routers/gisaid.py — all required EpiCoV columns present
  6. scripts/portal_to_tostadas.py — correct BioSample package by source type
""",
        ow,
        dry,
    )

    # =========================================================================
    # SUMMARY
    # =========================================================================

    written = [
        "docker-compose.yml",
        "Dockerfile.api",
        "Dockerfile.ui",
        ".pre-commit-config.yaml",
        ".github/workflows/test.yml",
        "db/init.sql (placeholder — replace with full schema from arch doc)",
        "db/migrations/env.py",
        "backend/auth/__init__.py",
        "backend/auth/oauth.py",
        "backend/auth/guards.py",
        "backend/auth/dependencies.py",
        "backend/validator.py",
        "backend/harmonizer.py",
        "backend/routers/__init__.py",
        "backend/routers/auth.py",
        "backend/routers/gisaid.py (full)",
        f"backend/routers/<{len(stub_routers)} stub routers>",
        "frontend/pages/<14 stub pages>",
        "frontend/components/<3 stub components>",
        "pipelines/nextflow.config",
        "pipelines/ingest_gate.nf",
        "scripts/portal_to_tostadas.py",
        "scripts/migrate_from_apgap.py",
        "tests/conftest.py",
        "tests/test_validator.py",
        "tests/test_epiweek.py",
        "tests/test_permissions.py",
        "tests/test_samples_api.py",
        "tests/test_file_detector.py",
        "tests/test_gisaid_export.py",
        "tests/test_tostadas_converter.py",
        "docs/CLAUDE.md",
    ]

    print(f"\n{'═'*55}")
    print(f"{'DRY RUN complete' if dry else 'Files written successfully.'}")
    print(f"\nFiles covered ({len(written)}):")
    for f in written:
        print(f"  {f}")

    print("\nImportant next steps:")
    print("  1. Replace db/init.sql placeholder with full schema from")
    print("     Section 11.12 of jackpot_architecture_v4.md")
    print("  2. Run: uv run pre-commit install")
    print("  3. Run: uv run detect-secrets scan > .secrets.baseline")
    print("  4. Run: docker compose up -d")
    print("  5. Run: curl http://localhost:8000/health")
    print("  6. Run: uv run pytest  (most tests will pass immediately)")


if __name__ == "__main__":
    main()
