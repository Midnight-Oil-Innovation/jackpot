# CLAUDE.md — jackpot-backend

## Project: JACKPOT

Pathogen genomics platform for genomic epidemiology, bioinformatics,
and public health research. Successor to APGAP (ASU-RSE-Services).

---

## Tech Stack

- Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2
- PostgreSQL (local dev) / BigQuery (production)
- MinIO (local) / GCS (production) — same boto3 code, different endpoint
- LinkML v4.1 schema: `schema/schema/jackpot_schema.yaml` (git submodule)
- Authentication: Google OAuth 2.0 + JWT httponly cookies (mock in local dev)
- Environment management: uv — never use pip directly
- Tests: pytest + testcontainers (real PostgreSQL container in tests)

---

## Directory Structure

```
~/ASU/jackpot/               ← workspace folder (not a git repo)
└── jackpot-backend/         ← git repository (this repo)
    ├── backend/             ← Python source code — imported as `backend`
    │   ├── main.py          App entrypoint — add router imports here
    │   ├── config.py        Settings class; ENV=local or gcp
    │   ├── permissions.py   PermissionGroups enum — DO NOT rename values
    │   ├── database.py      Lazy engine; execute_query / execute_write / reset_engine
    │   ├── validator.py     LinkML-based metadata validator — gate on all ingest paths
    │   ├── harmonizer.py    CSV column mapper using mapping_config YAMLs
    │   ├── file_detector.py NGS file pairing and extension detection — only place for this logic
    │   ├── auth/
    │   │   ├── guards.py        get_current_user, require_platform_admin, require_lab_access
    │   │   ├── dependencies.py  FastAPI dependency injection wrapper
    │   │   └── oauth.py         Google OAuth flow (production only)
    │   └── routers/         One file per feature area; each registers its own APIRouter
    ├── db/
    │   ├── init.sql         Reference schema (27 tables) — never edit in production
    │   └── migrations/      Alembic migration files — all schema changes go here
    ├── schema/              git submodule → jackpot-schema repo
    │   └── schema/
    │       └── jackpot_schema.yaml   Single source of truth for all metadata
    ├── tests/
    ├── scripts/
    └── docs/
        └── CLAUDE.md        ← this file
```

**Why `schema/schema/`?** The submodule mounts at `schema/` inside
`jackpot-backend/`. The YAML file lives at `schema/jackpot_schema.yaml`
inside the submodule repo. So the full path from the repo root is always
`schema/schema/jackpot_schema.yaml` — the doubling is intentional.

---

## Current Baseline

- **95 tests passing, 0 failed, 63.96% coverage**
- CI threshold: 60% — do not let coverage fall below this
- Health check: `curl http://localhost:8000/health` → `{"status":"ok","version":"4.0.0","project":"JACKPOT"}`
- All 27 database tables loaded in PostgreSQL
- Both `development` and `main` are at the same commit

Do not regress the test count or coverage without a deliberate reason.
After every implementation session, run `uv run pytest` and confirm both
numbers are stable or improved.

---

## Critical Rules — Read Before Making Any Change

**1. PermissionGroups enum values are sacred.**
Values MUST match `asu_apgap/utils/permissions.py` exactly.
DO NOT rename: `"Platform Admin"`, `"Lab Director"`, `"Lab Collaborator"`,
`"Lab Reader"`, `"Bioinformatics User"`, `"Data Analyst"`.

**2. All database schema changes go through Alembic.**
Never edit `db/init.sql` directly in production.
Command: `uv run alembic revision --autogenerate -m "description"`

**3. Regenerate Python models after any schema change.**
Command: `uv run gen-pydantic schema/schema/jackpot_schema.yaml > backend/models_generated.py`
Note the doubled path — `schema/schema/` — explained in the directory structure section above.

**4. Every state-changing endpoint calls `log_audit()`.**
Import from `audit.py`. Use the action name constants (`CREATE_SAMPLE`, etc.).

**5. `sequencing_lab` is NOT a static enum.**
Validated at runtime against the `sequencing_labs` database table.
Unknown values: return 422 with a message directing the user to the request workflow.

**6. All API routes must be prefixed `/api/v1/`.**
Each router file sets its own `prefix` (e.g. `prefix="/api/v1/samples"`).
When registering in `main.py`, do NOT add a prefix again — it will double
to `/api/v1/api/v1/samples`.

**7. Use `uv run` for all Python commands. Never `pip`, never activate venv.**

**8. `adhs_medsis_id` is required for HumanSample. It is NOT the same as `case_id`.**
`adhs_medsis_id` = ADHS-issued anonymized ID or exemption code.
`case_id` = generic non-ADHS public health case identifier (CDC NEDSS etc.).

**9. Epiweek is computed at ingest, never by the user.**
Call `compute_epiweeks(date_collected)` from `epiweek.py` before every DB write.

**10. `fastq_r1_uri` and `fastq_r2_uri` are convenience fields, not the source of truth.**
The `sample_files` table is the canonical per-file registry.
These columns are auto-populated by `get_convenience_uris()` from `file_detector.py`
for simple 2-file paired runs only.

**11. Never parse filenames anywhere except `file_detector.py`.**
All NGS filename logic lives exclusively in `backend/file_detector.py`.

**12. Supported file extensions: `.fastq`, `.fq`, `.fasta`, `.fa`, `.fna` + `.gz`/`.bz2`.**
To add a new extension: edit `_FASTQ_BASES` or `_FASTA_BASES` in `file_detector.py` only.

**13. Never write `import jwt`. Use `from jose import jwt`.**
The installed package is `python-jose`, not PyJWT. The import is different
but all method signatures (`jwt.encode()`, `jwt.decode()`) are identical.
This applies to `auth/guards.py`, `auth/oauth.py`, and any new file that
handles tokens.

**14. Never break the lazy engine pattern in `database.py`.**
`database.py` uses `_engine = None` at module level and creates the engine
inside `_get_engine()` on first call. It exposes `reset_engine()` which
test fixtures call to force reconnection to the testcontainer URL.
If the engine is created at import time, all database tests will fail
because the engine connects to `localhost:5432` before the testcontainer starts.
Do not change the initialization pattern without understanding this.

**15. Implementing a stub router: replace, don't append.**
Every router in `backend/routers/` starts as a 5-line stub returning
`{"status": "not implemented"}`. When implementing a router, replace the
entire file. After implementing, add the router import and
`app.include_router()` call to `backend/main.py`.

---

## Local Dev Role Switching

In local dev (`ENV=local`), the mock user is determined by `MOCK_USER_EMAIL`
in `docker-compose.yml`. The `get_current_user()` function in `auth/guards.py`
looks up that email in the `users` table. If the email is not found, it falls
back to a Platform Admin dict so the API never breaks.

To test a specific role, insert the user and membership into the database
and change the env var:

```sql
-- Create a Lab Director user for testing
INSERT INTO users (email, name, is_platform_admin, is_active, organization_id)
VALUES ('director@test.com', 'Lab Director', FALSE, TRUE, 1);

INSERT INTO lab_membership (user_id, lab_id, permission_group_id, is_lab_admin)
SELECT u.id, 1,
  (SELECT id FROM permission_groups WHERE name = 'Lab Director'),
  TRUE
FROM users u WHERE u.email = 'director@test.com';
```

Then update `MOCK_USER_EMAIL` in `docker-compose.yml` and restart the API
container only (not postgres — that would lose the inserted rows):

```bash
docker compose up -d api
```

Revert by changing `MOCK_USER_EMAIL` back to `gotero@linuxprophet.com`
and running `docker compose up -d api` again.

---

## Common Commands

```bash
# Development
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
uv run pytest
uv run pytest tests/test_validator.py -v
uv run pytest -k "test_paired" -v
uv run pytest -x                          # stop on first failure

# Database
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "add_new_column"
psql postgresql://jackpot:jackpot@localhost:5432/jackpot_db
psql postgresql://jackpot:jackpot@localhost:5432/jackpot_db -c "\dt"

# Schema
uv run gen-pydantic schema/schema/jackpot_schema.yaml > backend/models_generated.py
uv run gen-json-schema schema/schema/jackpot_schema.yaml > schema/schema/jackpot_schema.json
python3 -c "import yaml; yaml.safe_load(open('schema/schema/jackpot_schema.yaml'))"

# Docker
docker compose up -d
docker compose up -d api                  # restart API only (preserves DB data)
docker compose ps
docker compose logs -f api
docker compose down
docker compose down -v                    # also deletes data volumes (full reset)
curl http://localhost:8000/health

# Submodule
git submodule update --remote schema
git add schema && git commit -m "chore: update schema submodule"

# mypy (not in pre-commit — run manually)
uv run mypy backend/
```

---

## APGAP Migration Compatibility

- Organization → Lab → Project → User hierarchy is identical
- PermissionGroups enum string values match APGAP exactly
- `is_lab_admin=TRUE` on `lab_membership` = Lab Director
- Projects preserve all Seqera fields (`workspace_id`, `compute_env_id`, `credentials_id`)
- Migration script: `scripts/migrate_from_apgap.py`

---

## OrganismNameEnum (62 values)

Derived from ADHS mandatory reportable communicable diseases list.
Additions: `Coccidioides immitis`, `Coccidioides posadasii` (Valley fever),
`metagenome` (metagenomic samples), `novel pathogen` (emerging/exotic disease).
All values use NCBI Taxonomy names for BioSample/SRA/GenBank/GISAID compatibility.
Platform Admins add new values via the admin UI — never hardcode new organisms.

---

## Testing Philosophy

60% coverage minimum enforced in CI (`pytest --cov-fail-under=60`).
Priority order for new tests:

1. `backend/validator.py` — every required field, every enum value, date checks
2. `backend/auth/guards.py` — all six role combinations
3. `backend/file_detector.py` — all extensions, all naming conventions
4. `backend/routers/ingest.py` — valid upload, missing fields, file detection
5. `backend/routers/gisaid.py` — all required EpiCoV columns present
6. `scripts/portal_to_tostadas.py` — correct BioSample package by source type

Stub routers are excluded from coverage measurement in `pyproject.toml`
`[tool.coverage.run] omit` so they don't drag the percentage down unfairly.

---

## mypy

mypy is NOT in pre-commit hooks — too noisy during early development.
Run manually when needed: `uv run mypy backend/`
Re-add to pre-commit once the codebase stabilises (Month 2+).
