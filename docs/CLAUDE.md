# CLAUDE.md — jackpot-backend

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
python3 -c "import yaml; yaml.safe_load(open('schema/schema/jackpot_schema.yaml'))"

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
- is_lab_admin=TRUE on lab_membership = Lab Director
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

## mypy
mypy is NOT in pre-commit hooks — too noisy during early development.
Run manually when needed: `uv run mypy backend/`
Re-add to pre-commit once the codebase stabilises (Month 2+).
