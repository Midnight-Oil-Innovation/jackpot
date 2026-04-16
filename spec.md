# JACKPOT — Project Specification

**Version:** 1.0
**Last updated:** 2026-04-15
**Status:** Active development — Month 1
**Audience:** Claude Code autonomous agent

---

## 1. Project Goal

Build **JACKPOT** — a pathogen genomics platform for genomic epidemiology,
bioinformatics, and public health research — for the Arizona Department of
Health Services (ADHS). JACKPOT is the successor to APGAP
(ASU-RSE-Services). It must be APGAP-compatible: same org/lab/project/user
hierarchy, same PermissionGroups enum string values, same role semantics.

The platform enables public health labs to:
- Ingest raw sequencing data (FASTQ, FASTA) with structured metadata
- Validate metadata against a tiered quality model (PRELIMINARY / ANALYZABLE / SUBMITTABLE)
- Scrub human reads from sequencing data before analysis
- Launch bioinformatics pipelines (nf-core, GHRU) against their samples
- Export data to GISAID, NCBI BioSample/SRA, and TOSTADAS
- Search, filter, and analyze samples across the platform
- Control data access with a fine-grained sharing and governance model

---

## 2. Current Baseline

- **275 tests passing, 0 failed, 75.62% coverage**
- CI threshold: 60% — must never fall below this
- Health check: `curl http://localhost:8000/health` → `{"status":"ok","version":"5.0.0","project":"JACKPOT","database":"connected"}`
- All 27 database tables loaded in PostgreSQL via Alembic migrations
- `development` and `main` branches are at the same commit
- All 21 routers registered in `main.py` (as stubs returning `{"status": "not implemented"}`)
- Two routers fully implemented: `auth.py`, `gisaid.py`
- Seed data loaded: 75 reportable organisms, 3 sequencing labs

---

## 3. Architecture Constraints

These constraints are non-negotiable. Every implementation must respect them.

### Language and Tools
- Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2
- `uv run` for all Python commands — never `pip`, never activate venv
- `gac "type: description"` for all commits (runs ruff fix/format then commits)

### Database
- PostgreSQL (local dev via Docker Compose) / Cloud SQL PostgreSQL (production)
- All schema changes go through Alembic migrations — never edit `db/init.sql` directly
- After any schema change: regenerate `backend/models_generated.py` with `gen-pydantic --pydantic-version 2` then apply the boolean keyword patch (Critical Rule 20)

### API
- All routes prefixed `/api/v1/` — set in the router's `prefix`, not in `main.py`
- All responses use `backend/responses.py` helpers: `success()`, `success_list()`, `success_message()`, `error()`
- All list endpoints use `backend/pagination.py` — never raw OFFSET/LIMIT
- All state-changing endpoints call `log_audit()` from `backend/audit.py`
- All PATCH endpoints use `model_dump(exclude_none=True)` for partial updates
- All INSERT/UPDATE use PostgreSQL `RETURNING *` — never SELECT after write

### Authentication
- `get_current_user` / `require_platform_admin` / `require_lab_director` / `require_lab_access` from `backend/auth/guards.py`
- `from jose import jwt` — never `import jwt` (package is `python-jose`)
- Local dev: mock user via `MOCK_USER_EMAIL` in `docker-compose.yml`

### Storage
- All GCS/MinIO operations go through `backend/storage.py` — routers never call boto3 directly
- Local dev: MinIO via `STORAGE_BACKEND=minio`; production: GCS via `STORAGE_BACKEND=gcs`

### Business Logic Constraints
- `PermissionGroups` enum values are sacred — must match APGAP exactly (see Critical Rule 1)
- `sequencing_lab` validated at runtime against `sequencing_labs` DB table — not a static enum
- `surveillance_relevant` computed only by `compute_surveillance_relevant()` in `validator.py`
- `quality_status` computed only by `compute_quality_status()` in `validator.py`
- Epiweeks computed only by `compute_epiweeks()` in `epiweek.py` — called at ingest, never by user
- File parsing lives only in `backend/file_detector.py` — nowhere else
- `scrub_status = SKIPPED` set only in validator.py (FASTA-only auto-skip) or scrub override workflow
- One CSV row = one sample — files semicolon-delimited in a single cell
- `adhs_medsis_id` required for HumanSample only
- `active` column for orgs/labs; `is_active` for all other tables
- Background jobs use APScheduler (local) / Cloud Scheduler (production) — no Celery, no Redis as task broker

### Database Dependency Injection
- Routers use `get_db_dep()` with `Depends()` for database access
- All writes share one transaction via `conn` parameter: `execute_write(..., conn=db)`, `log_audit(..., db_conn=db)`, `create_notification(..., db_conn=db)`

---

## 4. What Needs to Be Built — Month 1

### Pre-Session Fixes (must be done before any router session)

These bugs will cause immediate test failures if not fixed first:

1. **`tests/conftest.py` missing Alembic migrations** — `initialize_test_db` only runs `db/init.sql`, never `alembic upgrade head`. The 31 columns added via migration don't exist in the test DB. Fix: add `alembic upgrade head` to the fixture.
2. **`routers/auth.py` module-level `settings = get_settings()`** — causes test isolation failure. Fix: move inside function scope, matching the pattern already fixed in `guards.py`, `oauth.py`, `storage.py`.
3. **`valid_human_sample` fixture still has old "Otero Lab" reference** — locate with `grep -n "Otero" tests/conftest.py tests/test_samples_api.py` and fix.
4. **`active` vs `is_active` inconsistency** — `organizations` and `labs` tables use `active`; everything else uses `is_active`. Add note to CLAUDE.md Critical Rules and fix router implementations accordingly.
5. **Missing JWT refresh endpoint** — `issue_refresh_token()` exists but no `POST /api/v1/auth/refresh` endpoint. 15-minute access tokens expire with no renewal path. Add to `routers/auth.py`.

### Router Sessions A–H

Each session implements one router end-to-end: replace the stub, write full endpoint logic, write tests. Sessions must be completed in this order (each depends on previous):

| Session | Router | Key Dependencies |
|---------|--------|-----------------|
| A | `organizations` | No dependencies |
| B | `labs` + `lab_membership` | organizations |
| C | `users` | organizations |
| D | `domain_whitelist` | needed for OAuth login |
| E | `sequencing_labs` | required by ingest validator |
| F | `tokens` | API token management for CLI; needs default lab_id + project_id |
| G | `ingest` | all of the above; most complex |
| H | `samples` | lists/gets/updates what ingest created |

### Additional Month 1 Work

- `projects` router (stub → full) — needed by ingest (`?name=` filter required for CLI)
- `dataharmonizer` router (stub → full) — CSV template generation + column mapping
- JWT refresh endpoint in `routers/auth.py`
- `tests/conftest.py` improvements: remove `contextlib.suppress(Exception)` from DB setup

---

## 5. Router Specifications

### Session A — organizations

**Endpoints:**
- `GET /api/v1/organizations/` — paginated list (Platform Admin only)
- `POST /api/v1/organizations/` — create org (Platform Admin only)
- `GET /api/v1/organizations/{id}` — get org (Platform Admin or org member)
- `PATCH /api/v1/organizations/{id}` — partial update (Platform Admin only)
- `DELETE /api/v1/organizations/{id}` — soft delete, set `active=False` (Platform Admin only)

**Key rules:**
- Use `active` column (not `is_active`) for orgs
- `log_audit()` on all writes with `CREATE_ORG` / `UPDATE_ORG` actions
- Partial update via `model_dump(exclude_none=True)`

**Tests:** CRUD round-trip, role enforcement (non-admin gets 403), pagination, soft delete.

---

### Session B — labs + lab_membership

**Endpoints:**
- `GET /api/v1/labs/` — paginated list (Platform Admin sees all; others see their labs)
- `POST /api/v1/labs/` — create lab under an org (Platform Admin only)
- `GET /api/v1/labs/{id}` — get lab detail (lab member or Platform Admin)
- `PATCH /api/v1/labs/{id}` — partial update (Lab Director or Platform Admin)
- `DELETE /api/v1/labs/{id}` — soft delete `active=False` (Platform Admin only)
- `GET /api/v1/labs/{id}/members` — list members (Lab Director or Platform Admin)
- `POST /api/v1/labs/{id}/members` — add member (Lab Director or Platform Admin)
- `PATCH /api/v1/labs/{id}/members/{user_id}` — change role (Lab Director or Platform Admin)
- `DELETE /api/v1/labs/{id}/members/{user_id}` — remove member (Lab Director or Platform Admin)

**Key rules:**
- Use `active` column (not `is_active`) for labs
- `is_lab_director` flag on `lab_membership` — not a separate permission check
- Membership changes: `ADD_LAB_MEMBER`, `REMOVE_LAB_MEMBER`, `CHANGE_MEMBER_ROLE` audit actions
- `sequencing_lab_assignments` join table links sequencing facilities to JACKPOT labs

**Tests:** Role enforcement at every tier, membership lifecycle, soft delete.

---

### Session C — users

**Endpoints:**
- `GET /api/v1/users/` — list users (Platform Admin only)
- `GET /api/v1/users/me` — current user profile (any authenticated user)
- `GET /api/v1/users/{id}` — get user (Platform Admin or same user)
- `PATCH /api/v1/users/{id}` — partial update (Platform Admin or same user)
- `DELETE /api/v1/users/{id}` — deactivate `is_active=False` (Platform Admin only)

**Tests:** Self-service vs admin access, deactivation, pagination.

---

### Session D — domain_whitelist

**Endpoints:**
- `GET /api/v1/domain-whitelist/` — list whitelisted domains (Platform Admin)
- `POST /api/v1/domain-whitelist/` — add domain (Platform Admin)
- `DELETE /api/v1/domain-whitelist/{id}` — remove domain (Platform Admin)

**Purpose:** Controls which email domains can self-register via Google OAuth.

**Tests:** Add/remove domain, non-admin 403.

---

### Session E — sequencing_labs

**Endpoints:**
- `GET /api/v1/sequencing-labs/` — list all sequencing labs (any authenticated user)
- `POST /api/v1/sequencing-labs/` — create lab (Platform Admin only)
- `GET /api/v1/sequencing-labs/{id}` — get detail (any authenticated)
- `PATCH /api/v1/sequencing-labs/{id}` — update (Platform Admin only)
- `POST /api/v1/sequencing-labs/{id}/assign/{lab_id}` — assign to JACKPOT lab (Platform Admin)
- `DELETE /api/v1/sequencing-labs/{id}/assign/{lab_id}` — unassign (Platform Admin)

**Purpose:** Validates `sequencing_lab` field at ingest; drives Globus arrival notifications.

**Tests:** CRUD, assignment workflow, list returns seed data (Sonora Quest, LabCorp, Otero Outpost).

---

### Session F — tokens

**Endpoints:**
- `GET /api/v1/tokens/` — list my tokens (authenticated user)
- `POST /api/v1/tokens/` — create token (authenticated user)
- `DELETE /api/v1/tokens/{id}` — revoke token (owner or Platform Admin)

**Key rules:**
- Tokens store `default_lab_id` and `default_project_id` for CLI convenience
- `GET /api/v1/projects/` must support `?name=` filter (needed by CLI project lookup)
- Token value shown once at creation — stored as hash in DB

**Tests:** Create/revoke, project name lookup, token isolation between users.

---

### Session G — ingest

**Endpoints:**
- `POST /api/v1/ingest/upload` — GUI/API file + metadata upload
- `POST /api/v1/ingest/csv` — CSV bulk metadata upload (files staged separately)
- `POST /api/v1/ingest/globus` — Globus deposit-first webhook (Platform Admin / system)

**Key rules — read every one before implementing:**
- `sequencing_lab` validated against `sequencing_labs` DB table — return 422 with request workflow message if unknown
- `adhs_medsis_id` required for `source_type == "Human"` only
- `file_detector.py` is the only place filename/pairing logic lives
- `compute_epiweeks(date_collected, precision)` called before every DB write — precision from validator
- `scrub_status = PENDING` on all new samples with raw reads; `SKIPPED` only via validator (FASTA-only) or override workflow
- `compute_surveillance_relevant()` and `compute_quality_status()` called from validator — never in router directly
- `log_audit(CREATE_SAMPLE, ...)` on every successful ingest
- One CSV row = one sample; `files` column is semicolon-delimited
- `dlp_scanner.py` scans all free-text fields (when `DLP_ENABLED=true`)
- `epiweek` computed at ingest, written to DB

**Tests:** Valid human upload (Tier 1, 2, 3), FASTA-only auto-skip, unknown sequencing lab 422, missing adhs_medsis_id 422, file detection for R1/R2 pairs, multi-lane, nanopore.

---

### Session H — samples

**Endpoints:**
- `GET /api/v1/samples/` — paginated list with full filter surface (authenticated, access-controlled)
- `GET /api/v1/samples/{id}` — get sample detail (access-controlled via `can_access_sample()`)
- `PATCH /api/v1/samples/{id}` — partial metadata update (Lab Collaborator+, own lab only)
- `DELETE /api/v1/samples/{id}` — soft delete / archive (Lab Director or Platform Admin)
- `GET /api/v1/samples/{id}/files` — list associated files
- `GET /api/v1/samples/{id}/download` — presigned download URL

**Key rules:**
- `can_access_sample()` enforces: Platform Admin → lab member → PUBLIC → ADHS oversight (surveillance_relevant only) → approved request
- `?select_all=true` returns IDs only (no pagination) for bulk select
- Filters: `organism_name`, `source_type`, `sector`, `quality_status`, `scrub_status`, `sharing_level`, `lab_id`, `project_id`, `date_collected` range, `surveillance_relevant`
- `log_audit(UPDATE_SAMPLE / ARCHIVE_SAMPLE)` on writes
- Partial update via `model_dump(exclude_none=True)` — never overwrite quality_status or surveillance_relevant directly

**Tests:** Role-based access, filter combinations, bulk select, download URL generation, unauthorized access 403.

---

## 6. Test Requirements

Every router session must produce a `tests/test_{router}_api.py` file with:
- Full CRUD round-trip test
- Role enforcement: one test per unauthorized role (Platform Admin protected → Lab Director gets 403; Lab-level protected → Lab Reader gets 403)
- Pagination test for list endpoints
- At least one error case (404 on missing resource, 409 on duplicate)
- Edge case specific to the router (e.g., ingest: unknown sequencing lab → 422)

Coverage must stay ≥ 60% after every session. Run `uv run pytest --cov=backend --cov-report=term-missing` and check.

---

## 7. Verification

After every router session, verify:

```bash
# Tests pass and coverage holds
uv run pytest
# Expected: ≥275 tests passing initially; grows with each session

# Health check still green
curl http://localhost:8000/health
# Expected: {"status":"ok","version":"5.0.0","project":"JACKPOT","database":"connected"}

# New endpoints reachable
curl -s http://localhost:8000/api/v1/{router}/ | python3 -m json.tool
# Expected: JSON response (not 404, not 500)

# Audit log populated on writes
psql postgresql://jackpot:jackpot@localhost:5432/jackpot_db \  # pragma: allowlist secret
  -c "SELECT action, resource_type, created_at FROM audit_log ORDER BY id DESC LIMIT 5;"

# No coverage regression
uv run pytest --cov=backend --cov-fail-under=60
```

Pre-session fixes are verified by:
```bash
# Alembic fix — test DB has all migration columns
uv run pytest tests/test_validator.py -v   # was failing pre-fix

# auth.py settings fix — no test isolation failure
uv run pytest tests/ -x -v  # all pass without early stop

# JWT refresh
curl -s -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Cookie: refresh_token=..." | python3 -m json.tool
```
