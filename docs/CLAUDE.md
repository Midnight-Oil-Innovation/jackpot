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
backend/         FastAPI application code
  main.py        App entrypoint — router imports go here
  config.py      Settings class; ENV=local or gcp
  permissions.py PermissionGroups enum — DO NOT rename values
  auth/          Google OAuth exchange + JWT middleware
  routers/       One file per API resource
db/
  init.sql       Reference schema (PostgreSQL)
  migrations/    Alembic migration files
schema/          git submodule → jackpot-schema repo
  schema/
    jackpot_schema.yaml  Single source of truth for all metadata
tests/
scripts/
```

## Critical Rules — Read Before Making Any Change

1. **PermissionGroups enum values are sacred.**
   They must match asu_apgap/utils/permissions.py exactly.
   DO NOT rename: "Platform Admin", "Lab Director", etc.

2. **All schema changes go through Alembic.**
   Never edit db/init.sql directly in production.
   Command: `uv run alembic revision --autogenerate -m "description"`

3. **Regenerate Python models after schema changes.**
   Command: `uv run gen-pydantic schema/schema/jackpot_schema.yaml > backend/models_generated.py`

4. **Every state-changing endpoint calls log_audit().**
   Import from audit.py. Use the constants (CREATE_SAMPLE etc).

5. **sequencing_lab is NOT a static enum.**
   Validated at runtime against the sequencing_labs table.
   Unknown values: return 422 with message directing user to request workflow.

6. **All API routes must be prefixed /api/v1/**

7. **Use `uv run` for all Python commands.**
   Never activate a venv manually. Never use pip.

8. **adhs_medsis_id is required for HumanSample.**
   It is NOT the same as case_id.
   adhs_medsis_id = ADHS-issued anonymized ID or exemption code.
   case_id = generic non-ADHS public health case identifier.

9. **Epiweek is computed at ingest, never by the user.**
   Call compute_epiweeks(date_collected) from epiweek.py
   before writing any sample to the database.

10. **fastq_r1_uri and fastq_r2_uri are convenience fields, not the source of truth.**
    The sample_files table is the canonical file registry.
    These columns are populated automatically by get_convenience_uris()
    from file_detector.py for simple 2-file paired runs only.
    For all other cases query sample_files for the complete file list.

11. **Never parse filenames anywhere except file_detector.py.**
    All NGS filename logic lives exclusively in backend/file_detector.py.

12. **Supported file extensions: .fastq, .fq, .fasta, .fa, .fna + .gz/.bz2.**
    Adding a new extension requires only editing _FASTQ_BASES or
    _FASTA_BASES in file_detector.py. Nothing else needs to change.

## Common Commands
```bash
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
uv run pytest
uv run pytest tests/test_validator.py -v
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"
uv run gen-pydantic schema/schema/jackpot_schema.yaml > backend/models_generated.py
uv run gen-json-schema schema/schema/jackpot_schema.yaml > schema/schema/jackpot_schema.json
docker compose up -d
docker compose ps
curl http://localhost:8000/health
docker compose logs -f api
psql postgresql://jackpot:jackpot@localhost:5432/jackpot_db
git submodule update --remote schema && git add schema && git commit -m "chore: update schema"
```

## APGAP Migration Context
- Organization → Lab → Project → User hierarchy is identical
- PermissionGroups enum values match APGAP exactly
- is_lab_admin=TRUE on lab_membership = Lab Director
- Projects preserve all Seqera fields
- Migration script: scripts/migrate_from_apgap.py

## OrganismNameEnum
62 values from ADHS mandatory reportable communicable diseases.
Additions: Coccidioides immitis, Coccidioides posadasii, metagenome, novel pathogen.
All NCBI Taxonomy format. Platform Admins add new values via admin UI.

## Testing Philosophy
60% coverage minimum. Priority:
1. validator.py — every required field, every enum value
2. auth/middleware.py — all six role combinations
3. routers/ingest.py — valid upload, missing fields, scrub status
4. file_detector.py — all extensions, all naming conventions
5. routers/gisaid.py — all required EpiCoV columns present
