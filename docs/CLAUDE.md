# CLAUDE.md — jackpot-backend

## Project: JACKPOT

Pathogen genomics platform for genomic epidemiology, bioinformatics,
and public health research. Successor to APGAP (ASU-RSE-Services).

---

## Tech Stack

- Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2
- PostgreSQL (local dev) / Cloud SQL PostgreSQL (production) — operational
  database for all transactional workloads. Alembic, SQLAlchemy, and all
  queries work identically against both. Transition = connection string change.
- BigQuery (production only) — separate analytical layer for surveillance
  dashboards, turnaround reporting, and population-level queries. Populated
  via ETL from Cloud SQL. The FastAPI API never queries BigQuery directly.
  Not present in local dev. Month 3+ concern.
- MinIO (local) / GCS (production) — same boto3 code via backend/storage.py,
  different endpoint. Transition = STORAGE_BACKEND env var change.
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
Command: `uv run gen-pydantic --pydantic-version 2 schema/schema/jackpot_schema.yaml > backend/models_generated.py`
Then apply the boolean keyword patch — see Critical Rule 20.
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
uv run gen-pydantic --pydantic-version 2 schema/schema/jackpot_schema.yaml > backend/models_generated.py
# Then apply boolean keyword patch — see Critical Rule 20
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

## GCP Production Architecture

The local dev stack and the GCP production stack are deliberately parallel
but not identical. Several components have no local equivalent and several
env vars control which backend is active. Understand this mapping before
implementing any component that touches infrastructure.

### Environment variables that control backend selection

| Variable | Local dev value | GCP production value | Effect |
|---|---|---|---|
| `ENV` | `local` | `gcp` | Master switch — changes OAuth, storage, DB |
| `STORAGE_BACKEND` | `minio` | `gcs` | Routes backend/storage.py to MinIO or GCS |
| `SCHEDULER_ENABLED` | `true` | `false` | APScheduler runs locally; Cloud Scheduler takes over in GKE |
| `PIPELINE_EXECUTOR` | `local` | `gcp_batch` | Nextflow runs locally or submits to GCP Batch |
| `WORKSPACE_ENABLED` | `false` | `true` | JupyterHub launch endpoint active only in GKE |

### Component-by-component mapping

| Component | Local dev | GCP production | Transition complexity |
|---|---|---|---|
| Object storage | MinIO via boto3 | GCS via boto3 | STORAGE_BACKEND env var — genuinely simple |
| Operational DB | PostgreSQL in Docker | Cloud SQL PostgreSQL | Connection string — genuinely simple |
| Analytics layer | Not present | BigQuery (ETL from Cloud SQL) | Separate ETL pipeline — Month 3+ |
| Background jobs | APScheduler in-process | Cloud Scheduler → HTTP endpoint | SCHEDULER_ENABLED env var |
| Pipeline execution | Nextflow local/Docker | GCP Batch via Nextflow config | PIPELINE_EXECUTOR env var |
| Authentication | Mock user (MOCK_USER_EMAIL) | Google OAuth | ENV=gcp flag — already implemented |
| Workspace | Not present | JupyterHub on GKE | GCP-only — WORKSPACE_ENABLED env var |
| Globus endpoint | MinIO staging | GCS staging collection | Storage backend env var |
| API server | uvicorn local | GKE deployment | jackpot-iac Terraform |
| Notifications | Cloud SQL table | Cloud SQL table | No change |
| Audit log | Cloud SQL table | Cloud SQL table | No change |
| Pipeline telemetry | Cloud SQL table | Cloud SQL table | No change |

### Why Cloud SQL, not BigQuery, for the operational database

BigQuery is an analytical warehouse. It does not support:
- Row-level locking (required by access request approval workflow)
- Foreign key constraints (required by referential integrity model)
- ACID transactions across multiple tables (required by audit log pattern)
- Efficient row-level UPDATEs and DELETEs (required by status updates,
  deletion lifecycle, scrub_status changes)
- SERIAL PRIMARY KEY autoincrement
- Alembic migrations

Cloud SQL PostgreSQL supports all of the above and is what the FastAPI
API uses in production. BigQuery is a separate analytical layer populated
by a periodic ETL job from Cloud SQL — it is never queried by the API
directly.

### Background job production pattern

APScheduler runs inside the FastAPI process in local dev. In GKE production
SCHEDULER_ENABLED=false disables APScheduler, and Cloud Scheduler fires
HTTP requests to the job trigger endpoint on each schedule:

```
Cloud Scheduler (cron) → POST /api/v1/admin/jobs/{job_id}/run → job executes once
```

This avoids the multi-pod race condition where N replicas each run the
same job N times simultaneously. The job logic itself does not change —
only who triggers it. Cloud Scheduler is defined in jackpot-iac Terraform.

### Pipeline execution production pattern

In local dev, PIPELINE_EXECUTOR=local shells out to `nextflow run` directly.
In GCP production, PIPELINE_EXECUTOR=gcp_batch submits to GCP Batch via
a Nextflow config file that specifies the GCP Batch executor. The launch
endpoint constructs the appropriate submission based on this env var. The
Nextflow -weblog callback to POST /api/v1/pipelines/events works identically
in both environments — it's an HTTP call from wherever Nextflow runs.

### What has no local dev equivalent

These features simply do not exist in local dev. Their endpoints return a
meaningful error when WORKSPACE_ENABLED=false or equivalent:

- JupyterHub workspace (WORKSPACE_ENABLED=false returns 503)
- Globus endpoint registration (handled by jackpot-iac, not the API)
- Cloud Scheduler job triggers (use manual trigger endpoint in dev)
- BigQuery analytics queries (not implemented in dev)

---

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

---

## API Response Conventions

Every endpoint returns a consistent JSON envelope. Never invent a custom
response shape in a router — use the helpers from `backend/responses.py`.

### Success responses

```python
# Single resource
{"success": true, "data": {...}}

# Collection (paginated)
{
  "success": true,
  "data": [...],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 847,
    "pages": 17
  }
}

# Action with no resource to return (e.g. DELETE, state change)
{"success": true, "message": "Sample archived."}
```

### Error responses

```python
# Validation failure (422)
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Metadata validation failed.",
    "detail": {
      "errors": ["date_collected: future dates not accepted"],
      "tier": 0,
      "tier2_missing": ["collection_location_state"],
      "tier3_missing": ["originating_lab", "submitting_lab"]
    }
  }
}

# Access denied (403)
{
  "success": false,
  "error": {
    "code": "ACCESS_DENIED",
    "message": "You do not have access to this sample.",
    "detail": {}
  }
}

# Not found (404)
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Sample AZ-2026-001 not found.",
    "detail": {}
  }
}
```

### Standard error codes

| Code | HTTP status | When to use |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Metadata fails tier-aware validator |
| `ACCESS_DENIED` | 403 | can_access_sample() or role check fails |
| `NOT_FOUND` | 404 | Resource does not exist or not visible |
| `CONFLICT` | 409 | Duplicate sample_id, duplicate access request |
| `SCRUB_PENDING` | 409 | Files not yet available (scrub in progress) |
| `SCRUB_APPROVAL_REQUIRED` | 409 | Skip requested, awaiting Lab Director approval |
| `INTERNAL_ERROR` | 500 | Unexpected exception — log and return generic message |

### Response helpers (backend/responses.py)

```python
from backend.responses import success, success_list, error

# In a router:
return success(data=sample_dict)
return success_list(data=samples, page=1, per_page=50, total=847)
return error("ACCESS_DENIED", "You do not have access to this sample.", status_code=403)
```

`backend/responses.py` must be created before the first router is implemented.
It is the single place that constructs response envelopes. Routers never
build dicts directly.

---

## Pagination Convention

All list endpoints use the same query parameters and response shape.

### Query parameters

```
GET /api/v1/samples/?page=1&per_page=50&sort_by=date_collected&sort_dir=desc
```

| Parameter | Type | Default | Max | Description |
|---|---|---|---|---|
| `page` | int | 1 | — | 1-indexed page number |
| `per_page` | int | 50 | 200 | Items per page |
| `sort_by` | str | `created_at` | — | Column to sort by |
| `sort_dir` | str | `desc` | — | `asc` or `desc` |

### Pagination helper (backend/pagination.py)

`backend/pagination.py` already exists. Use it in every list endpoint:

```python
from backend.pagination import paginate

results, total = paginate(
    query=base_query,
    page=page,
    per_page=per_page,
    sort_by=sort_by,
    sort_dir=sort_dir
)
return success_list(data=results, page=page, per_page=per_page, total=total)
```

Never implement manual OFFSET/LIMIT in a router — always go through `paginate()`.

The `select-all-N-results` bulk select feature uses a separate endpoint
parameter `?select_all=true` which bypasses pagination and returns only
IDs (not full records) for the entire result set, regardless of page.

---

## Audit Logging

Every state-changing endpoint calls `log_audit()`. This is Critical Rule 4
— this section defines the exact function signature and required usage.

### Function signature (backend/audit.py)

```python
def log_audit(
    action: str,           # Action constant from AuditActions — see below
    actor_id: int | None,  # User ID performing the action. None = SYSTEM
    resource_type: str,    # "sample", "lab", "org", "access_request", etc.
    resource_id: str,      # String ID of the affected resource
    before: dict | None,   # State before change (for updates). None for creates.
    after: dict | None,    # State after change. None for deletes.
    metadata: dict | None, # Extra context (reason, override_category, etc.)
    db_conn,               # Active database connection
) -> None:
```

### Action constants (backend/audit.py)

```python
class AuditActions:
    # Samples
    CREATE_SAMPLE            = "CREATE_SAMPLE"
    UPDATE_SAMPLE            = "UPDATE_SAMPLE"
    DELETE_SAMPLE            = "DELETE_SAMPLE"
    ARCHIVE_SAMPLE           = "ARCHIVE_SAMPLE"
    SOFT_DELETE_SAMPLE       = "SOFT_DELETE_SAMPLE"
    HARD_DELETE_SAMPLE       = "HARD_DELETE_SAMPLE"

    # Scrub override
    REQUEST_SCRUB_SKIP       = "REQUEST_SCRUB_SKIP"
    APPROVE_SCRUB_SKIP       = "APPROVE_SCRUB_SKIP"
    DENY_SCRUB_SKIP          = "DENY_SCRUB_SKIP"
    AUTO_DENY_SCRUB_SKIP     = "AUTO_DENY_SCRUB_SKIP"
    SYSTEM_SKIP_SCRUB        = "SYSTEM_SKIP_SCRUB"

    # Surveillance override
    REQUEST_SURVEILLANCE_OVERRIDE = "REQUEST_SURVEILLANCE_OVERRIDE"
    APPROVE_SURVEILLANCE_OVERRIDE = "APPROVE_SURVEILLANCE_OVERRIDE"
    DENY_SURVEILLANCE_OVERRIDE    = "DENY_SURVEILLANCE_OVERRIDE"

    # Access requests
    CREATE_ACCESS_REQUEST    = "CREATE_ACCESS_REQUEST"
    APPROVE_ACCESS_REQUEST   = "APPROVE_ACCESS_REQUEST"
    DENY_ACCESS_REQUEST      = "DENY_ACCESS_REQUEST"
    AUTO_APPROVE_ACCESS_REQUEST = "AUTO_APPROVE_ACCESS_REQUEST"
    REVOKE_ACCESS            = "REVOKE_ACCESS"

    # Deletion
    REQUEST_DELETION         = "REQUEST_DELETION"
    APPROVE_DELETION         = "APPROVE_DELETION"
    DENY_DELETION            = "DENY_DELETION"
    COMPLETE_DELETION        = "COMPLETE_DELETION"

    # Org / Lab / User
    CREATE_ORG               = "CREATE_ORG"
    UPDATE_ORG               = "UPDATE_ORG"
    CREATE_LAB               = "CREATE_LAB"
    UPDATE_LAB               = "UPDATE_LAB"
    ADD_LAB_MEMBER           = "ADD_LAB_MEMBER"
    REMOVE_LAB_MEMBER        = "REMOVE_LAB_MEMBER"
    CHANGE_MEMBER_ROLE       = "CHANGE_MEMBER_ROLE"
```

### Usage example

```python
from backend.audit import log_audit, AuditActions

# In an ingest endpoint after writing the sample:
log_audit(
    action=AuditActions.CREATE_SAMPLE,
    actor_id=current_user["id"],
    resource_type="sample",
    resource_id=str(new_sample_id),
    before=None,
    after=sample_dict,
    metadata={"ingest_method": "gui", "tier": validation_result.tier},
    db_conn=conn,
)
```

The `audit_log` table must already exist (it is part of `db/init.sql`).
`log_audit()` must be created in `backend/audit.py` before the first
state-changing endpoint is written.

---

## Background Job Infrastructure

Background jobs use **APScheduler** running inside the FastAPI process,
started in `backend/main.py` on application startup. This is the correct
pattern for the prototype — no separate GKE CronJob needed until Month 2+.

### Setup (backend/main.py)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.jobs import run_access_request_job, run_scrub_override_job

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def start_scheduler():
    scheduler.add_job(run_scrub_override_job, "interval", hours=1,
                      id="scrub_override_auto_deny")
    scheduler.add_job(run_access_request_job, "interval", hours=1,
                      id="access_request_auto_approve")
    scheduler.start()

@app.on_event("shutdown")
async def stop_scheduler():
    scheduler.shutdown()
```

### Job modules (backend/jobs.py)

All background jobs live in `backend/jobs.py`. Each job is a standalone
async function that opens its own database connection. Jobs are idempotent —
running them twice produces the same result as running them once.

```python
async def run_scrub_override_job() -> None:
    """
    Auto-deny scrub override requests that have been pending for > 48 hours.
    Conservative default: if Lab Director doesn't decide, scrubber runs.
    """

async def run_access_request_job() -> None:
    """
    Auto-approve access requests where auto_approve_after <= NOW().
    Send 75-day warnings where auto_approve_after is within 15 days.
    Send 7-day warnings where access_expires_at is within 7 days.
    Expire approved grants where access_expires_at <= NOW().
    Mark pending requests as moot where sample.sharing_level = 'PUBLIC'.
    """
```

### Manual trigger endpoint (Platform Admin only)

For local dev and testing, jobs can be triggered manually:

```
POST /api/v1/admin/jobs/{job_id}/run
```

This avoids waiting for the scheduler interval during development.

---

## Notification System

Notifications are written to the `notifications` table synchronously
within the same database transaction as the triggering action. They are
NOT delivered via Pub/Sub or any async queue in the prototype.

### Helper function (backend/notifications.py)

```python
def create_notification(
    recipient_id: int,      # User ID to notify
    event_type: str,        # NotificationEvents constant — see below
    title: str,             # Short title shown in notification badge
    body: str,              # Full notification text
    resource_type: str,     # "sample", "access_request", "pipeline_run", etc.
    resource_id: str,       # ID of the related resource
    action_url: str | None, # Deep link into the JACKPOT UI
    db_conn,
) -> None:
```

### Notification events (backend/notifications.py)

```python
class NotificationEvents:
    # Scrub override
    SCRUB_SKIP_REQUESTED     = "SCRUB_SKIP_REQUESTED"
    SCRUB_SKIP_APPROVED      = "SCRUB_SKIP_APPROVED"
    SCRUB_SKIP_DENIED        = "SCRUB_SKIP_DENIED"
    SCRUB_SKIP_AUTO_DENIED   = "SCRUB_SKIP_AUTO_DENIED"

    # Access requests
    ACCESS_REQUEST_SUBMITTED = "ACCESS_REQUEST_SUBMITTED"
    ACCESS_REQUEST_APPROVED  = "ACCESS_REQUEST_APPROVED"
    ACCESS_REQUEST_DENIED    = "ACCESS_REQUEST_DENIED"
    ACCESS_AUTO_APPROVED     = "ACCESS_AUTO_APPROVED"
    ACCESS_APPROVE_WARNING   = "ACCESS_APPROVE_WARNING"   # 75-day warning to owner
    ACCESS_EXPIRING          = "ACCESS_EXPIRING"          # 7-day warning to requester

    # Pipelines
    PIPELINE_COMPLETE        = "PIPELINE_COMPLETE"
    PIPELINE_FAILED          = "PIPELINE_FAILED"

    # Ingest
    GLOBUS_FILES_ARRIVED     = "GLOBUS_FILES_ARRIVED"
    METADATA_COMPLETION_NEEDED = "METADATA_COMPLETION_NEEDED"
    ERRONEOUS_UPLOAD_EXPIRING = "ERRONEOUS_UPLOAD_EXPIRING"

    # Surveillance
    SURVEILLANCE_OVERRIDE_REQUESTED = "SURVEILLANCE_OVERRIDE_REQUESTED"
    SURVEILLANCE_OVERRIDE_DECIDED   = "SURVEILLANCE_OVERRIDE_DECIDED"
```

### Usage example

```python
from backend.notifications import create_notification, NotificationEvents

# After a scrub skip request is submitted:
create_notification(
    recipient_id=lab_director_id,
    event_type=NotificationEvents.SCRUB_SKIP_REQUESTED,
    title="Scrub skip requested",
    body=f"{requester_name} requested to skip the scrubber for sample {sample_id}. Reason: {reason}",
    resource_type="sample_scrub_override_request",
    resource_id=str(override_request_id),
    action_url=f"/labs/{lab_id}/access-requests#scrub-{override_request_id}",
    db_conn=conn,
)
```

`backend/notifications.py` must be created before the first endpoint that
triggers a notification (the ingest endpoint). Email delivery is deferred —
the notifications table is the only delivery mechanism in Month 1.

---

## Storage Abstraction (MinIO local / GCS production)

All file storage operations go through `backend/storage.py`. Routers never
call boto3 or the GCS client directly.

### Environment variables

| Variable | Local dev value | Production value |
|---|---|---|
| `STORAGE_BACKEND` | `minio` | `gcs` |
| `MINIO_ENDPOINT` | `http://minio:9000` | — |
| `MINIO_ACCESS_KEY` | `minioadmin` | — |
| `MINIO_SECRET_KEY` | `minioadmin` | — |
| `GCS_PROJECT_ID` | — | `jackpot-prod` |
| `SEQUENCES_BUCKET` | `jackpot-sequences` | `jackpot-sequences-prod` |
| `STAGING_BUCKET` | `jackpot-staging` | `jackpot-staging-prod` |
| `RESULTS_BUCKET` | `jackpot-results` | `jackpot-results-prod` |
| `REFERENCES_BUCKET` | `jackpot-references` | `jackpot-references-prod` |

### Storage helper functions (backend/storage.py)

```python
def stage_file(local_path: str, destination_key: str) -> str:
    """Upload a file to the staging bucket. Returns the URI."""

def move_to_sequences(staging_key: str, sequences_key: str) -> str:
    """Move a scrubbed file from staging to the sequences bucket."""

def generate_presigned_url(bucket: str, key: str, ttl_seconds: int = 3600) -> str:
    """Generate a presigned download URL."""

def generate_signed_upload_url(bucket: str, key: str, ttl_seconds: int = 14400) -> str:
    """Generate a signed upload URL (4-hour default TTL)."""

def delete_file(bucket: str, key: str) -> None:
    """Delete a file from a bucket."""

def file_exists(bucket: str, key: str) -> bool:
    """Check if a file exists without downloading it."""
```

All functions are backend-agnostic — they read `STORAGE_BACKEND` at call
time and route to either boto3 (MinIO) or the GCS client. Never check
`STORAGE_BACKEND` in a router.

---

## Testing Patterns

Use these patterns for all new tests. Do not invent new fixture approaches.

### Standard fixtures (tests/conftest.py)

```python
# Database connection — uses testcontainers PostgreSQL
@pytest.fixture
def db_conn(postgres_container):
    """Real PostgreSQL connection in a testcontainer."""

# Pre-created test users for each role
@pytest.fixture
def platform_admin_user(db_conn) -> dict:
    """Returns a Platform Admin user dict."""

@pytest.fixture
def lab_director_user(db_conn) -> dict:
    """Returns a Lab Director user dict."""

@pytest.fixture
def lab_collaborator_user(db_conn) -> dict:
    """Returns a Lab Collaborator user dict."""

@pytest.fixture
def bioinformatics_user(db_conn) -> dict:
    """Returns a Bioinformatics User dict."""

# Pre-created test resources
@pytest.fixture
def test_org(db_conn) -> dict:
    """Returns a test Organization dict."""

@pytest.fixture
def test_lab(db_conn, test_org) -> dict:
    """Returns a test Lab dict."""

@pytest.fixture
def test_project(db_conn, test_lab) -> dict:
    """Returns a test Project dict."""

@pytest.fixture
def test_sample(db_conn, test_lab, test_project) -> dict:
    """Returns a minimal valid sample dict (Tier 1, PRELIMINARY)."""

# Storage mock — avoids real GCS/MinIO calls in tests
@pytest.fixture(autouse=True)
def mock_storage(monkeypatch):
    """Patches backend.storage to use in-memory dict instead of real buckets."""
```

### FastAPI test client

```python
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_create_sample(db_conn, test_lab, lab_collaborator_user):
    response = client.post(
        "/api/v1/ingest/upload",
        headers={"Authorization": f"Bearer {lab_collaborator_user['token']}"},
        data={"metadata": json.dumps({
            "sample_id": "AZ-TEST-001",
            "organism_name": "Salmonella enterica",
            "source_type": "isolate",
            "sector": "clinical",
            ...
        })},
        files={"fastq_r1": ("test_R1.fastq.gz", b"fake_content", "application/gzip")}
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["quality_status"] == "PRELIMINARY"
```

### Mocking surveillance_relevant computation in tests

```python
from unittest.mock import patch

def test_ingest_sets_surveillance_true_for_reportable_organism(db_conn, ...):
    with patch("backend.validator.get_reportable_organisms") as mock_reportable:
        mock_reportable.return_value = {"Salmonella enterica"}
        # ... rest of test
```

Never hit the real `reportable_organisms` table in unit tests — always mock
`get_reportable_organisms()`. Integration tests that need the real table
use the `db_conn` fixture with seed data loaded from the migration.

---

## Epiweek Computation

MMWR epiweeks are computed from `date_collected` at ingest using the
`epiweeks` Python package. This is Critical Rule 9 — this section defines
the exact behavior.

### Function (backend/epiweek.py)

```python
from epiweeks import Week, CDC
from datetime import date

def compute_epiweeks(
    date_collected: date,
    precision: str,        # "day" | "month" | "year"
) -> dict:
    """
    Returns dict with mmwr_year, mmwr_week, iso_year, iso_week.
    If precision is "year" or "month", all four values are None
    (epiweek cannot be reliably computed without day precision).
    """
    if precision in ("year", "month"):
        return {
            "mmwr_year": None,
            "mmwr_week": None,
            "iso_year": None,
            "iso_week": None,
        }
    w = Week.fromdate(date_collected, system="CDC")
    iso = Week.fromdate(date_collected, system="ISO")
    return {
        "mmwr_year": w.year,
        "mmwr_week": w.week,
        "iso_year": iso.year,
        "iso_week": iso.week,
    }
```

Call `compute_epiweeks(date_collected, precision)` in the ingest endpoint
immediately before writing the sample row. Write all four returned values
to the database. Never compute epiweeks in the validator — the validator
only determines precision. Never compute epiweeks in the router logic
directly — always call `compute_epiweeks()`.

---

## Critical Rules (continued)

**16. `surveillance_relevant` is always computed by `compute_surveillance_relevant()`
in `validator.py`.**
Never set this field directly in a router. The validator is the only
place that reads from `reportable_organisms` and applies metagenomics
target_organisms logic. Ingest endpoints call the validator and use the
returned value.

**17. `quality_status` is always set by `compute_quality_status()` —
never hardcoded in routers.**
The validator returns a `ValidationResult` with a `tier` integer (1, 2, or 3).
`compute_quality_status(validation_result)` converts that to the string
("PRELIMINARY", "ANALYZABLE", "SUBMITTABLE"). Routers call this function —
they never write quality_status strings directly.

**18. `scrub_status = 'SKIPPED'` is only set in two places:**
(1) `validator.py` — FASTA-only auto-skip (no raw reads, approved_by=SYSTEM).
(2) The scrub override approval workflow — after Lab Director approval.
Ingest endpoints must not set scrub_status = SKIPPED directly under any
other circumstance. SRA-imported samples are also auto-SKIPPED by the
validator with skip_reason = 'sra_imported'.

**19. One CSV row = one sample. Files are associated via `file_detector.py`
pairing logic, never by requiring per-file rows from the user.**
The `files` column in any CSV or metadata form is semicolon-delimited
within a single cell: `AZ-001_R1.fastq.gz;AZ-001_R2.fastq.gz`.
`file_detector.py` is called on the parsed file list for every ingest path.
Never write file parsing or pairing logic in a router.

**20. `gen-pydantic` requires two steps after every run:**
(1) Always use the `--pydantic-version 2` flag:
    `uv run gen-pydantic --pydantic-version 2 schema/schema/jackpot_schema.yaml > backend/models_generated.py`
(2) Apply the boolean keyword patch immediately after generation:

```python
from pathlib import Path
content = Path('backend/models_generated.py').read_text()
content = content.replace('\n    True = "True"', '\n    true = "True"')
content = content.replace('\n    False = "False"', '\n    false = "False"')
Path('backend/models_generated.py').write_text(content)
```

`models_generated.py` is excluded from ruff linting (generated code).
Never edit it manually — always regenerate then patch.

**21. Sequencing lab → JACKPOT lab linkage uses `sequencing_lab_assignments`.**
The `sequencing_labs` table (the registry of physical sequencing facilities)
and the `labs` table (JACKPOT organizational units) are linked via a join
table `sequencing_lab_assignments` (sequencing_lab_id, lab_id). A single
sequencing facility may serve multiple JACKPOT labs. This join table is
used by the Globus deposit-first workflow to identify which Lab Directors
to notify when files arrive from a given sequencing facility.

**22. Background jobs are implemented in `backend/jobs.py` using APScheduler.**
Jobs are started in `backend/main.py` at application startup using
`AsyncIOScheduler`. Jobs are idempotent — running twice = same result as
running once. Every job can also be triggered manually via
`POST /api/v1/admin/jobs/{job_id}/run` (Platform Admin only) for local dev.
Never use `asyncio.create_task()` directly in routers for deferred work —
always add a job to the scheduler.

**23. All list endpoints use `backend/pagination.py` — never raw OFFSET/LIMIT.**
See the Pagination Convention section. The `select-all-N-results` bulk
select uses `?select_all=true` which returns IDs only, no pagination.

**24. All responses use `backend/responses.py` helpers — never raw dicts.**
See the API Response Conventions section. Every router imports `success`,
`success_list`, and `error` from `backend/responses.py`. The response
envelope shape is fixed — routers never construct it manually.

---

## Local Development Stack — What Runs Where

JACKPOT uses a **hybrid local dev stack**. Docker Compose is the primary
environment for all Month 1 and Month 2 backend/frontend work. Minikube
is added specifically for JupyterHub workspace testing in Month 2.
Never migrate the full stack to minikube.

### Docker Compose (primary — always running)

```
jackpot-backend   FastAPI API          localhost:8000
jackpot-frontend  Streamlit UI         localhost:8501
postgres          PostgreSQL           localhost:5432
minio             Object storage       localhost:9000 (API), 9001 (console)
```

Start/stop:
```bash
docker compose up -d          # start all services
docker compose up -d api      # restart API only (preserves DB data)
docker compose down           # stop (preserves volumes)
docker compose down -v        # stop and delete all data volumes
```

### Minikube (Month 2 only — JupyterHub workspace)

Minikube runs JupyterHub only. The FastAPI backend stays in Docker Compose.
JupyterHub pods reach the API via `minikube tunnel`.

```bash
# One-time setup (Month 2)
minikube start --driver=docker --cpus=4 --memory=4096
minikube addons enable ingress
minikube addons enable gcp-auth   # for GCS and GCP IAM simulation

# Deploy JupyterHub
helm repo add jupyterhub https://hub.jupyter.org/helm-chart/
helm upgrade --install jhub jupyterhub/jupyterhub -f jackpot-iac/jupyterhub/values.yaml

# Open tunnel so JupyterHub pods reach Docker Compose API
minikube tunnel   # keep running in a separate terminal
```

### Apple Silicon (M1/M2/M3) container note

Many bioinformatics tool containers are x86-only. When using
`PIPELINE_EXECUTOR=local` on Apple Silicon, add `--platform linux/amd64`
to the Nextflow process config. When using `PIPELINE_EXECUTOR=gcp_batch`,
GCP Batch VMs are x86 by default — no platform flag needed. Prefer
`gcp_batch` for pipeline testing even during development to avoid ARM
compatibility issues. GCP Batch spot instances are cheap for short test
runs.

---

## Nextflow Pipeline Execution

JACKPOT's pipeline launch endpoint submits Nextflow jobs to either a local
executor or GCP Batch depending on `PIPELINE_EXECUTOR`. This section
defines the config format, per-run isolation model, and callback pattern
that all pipeline work must follow.

### PIPELINE_EXECUTOR values

| Value | When used | How Nextflow runs |
|---|---|---|
| `local` | Local dev, small test runs | `nextflow run` on the API server directly |
| `gcp_batch` | Production and pipeline dev testing | Submits tasks to GCP Batch; Mac is controller |

### Local dev with gcp_batch (recommended for pipeline work)

Your Mac is the Nextflow controller. Tasks run on GCP Batch VMs.
Prerequisites (one-time):

```bash
# Install Nextflow (requires Java 17)
brew install openjdk@17
curl -s https://get.nextflow.io | bash
chmod +x nextflow && sudo mv nextflow /usr/local/bin/

# Authenticate with GCP
gcloud auth login
gcloud auth application-default login

# Enable required APIs
gcloud services enable batch.googleapis.com compute.googleapis.com

# Create the JACKPOT work bucket (one-time, done in jackpot-iac)
gcloud storage buckets create gs://jackpot-work-dev --location=us-central1
```

### Per-run GCS work directory

Every pipeline run gets an isolated GCS work directory. This is stored in
`pipeline_runs.work_dir` and is required for `-resume` to work correctly.
Two runs must never share a `workDir` prefix or their task caches collide.

```
gs://jackpot-work/{run_id}/work/
```

The JACKPOT launch endpoint passes `run_id` as a Nextflow parameter.
The Nextflow config uses it to set `workDir`.

### JACKPOT Nextflow config template

The launch endpoint generates this config file per run. It is written to
a temp file and passed via `-c jackpot_run.config`. Never hardcode run IDs
or URLs in a static config file.

```groovy
// Generated by JACKPOT POST /api/v1/pipelines/launch
// Run ID: ${run_id} | Pipeline: ${pipeline_name} ${pipeline_version}

process {
    executor = "${pipeline_executor}"   // local or google-batch
    errorStrategy = 'retry'
    maxRetries = 2
}

google {
    project = "${gcp_project_id}"
    location = "${gcp_region}"
    batch.spot = true                   // spot instances — ~90% cost saving
    batch.bootDiskSize = 50.GB
    resourceLabels = [
        'jackpot_run_id': "${run_id}",
        'jackpot_lab':    "${lab_slug}",
        'jackpot_pipeline': "${pipeline_name}"
    ]
}

workDir = "gs://jackpot-work/${run_id}/work"

params {
    jackpot_run_id    = "${run_id}"
    jackpot_api_url   = "${jackpot_api_url}"
    jackpot_weblog_url = "${jackpot_api_url}/api/v1/pipelines/events"
    jackpot_results_url = "${jackpot_api_url}/api/v1/pipelines/${run_id}/results"
    jackpot_token     = "${pipeline_token}"
}
```

### Nextflow launch command (from the API)

```bash
nextflow run ${pipeline_uri} \
    -revision ${pipeline_version} \
    -profile ${pipeline_profile} \
    -c jackpot_run.config \
    -resume \
    -weblog ${jackpot_weblog_url}
```

### Weblog callback in gcp_batch mode

When `PIPELINE_EXECUTOR=gcp_batch`, Nextflow runs on GCP Batch VMs.
The `-weblog` callback URL must be publicly reachable from those VMs.

- **Production**: use the deployed API URL (`https://api.jackpot.adhs.az.gov`)
- **Local dev testing with gcp_batch**: use `ngrok` or `cloudflared tunnel`
  to expose the local API temporarily:

```bash
# In a separate terminal — expose local API to internet for weblog callbacks
cloudflared tunnel --url http://localhost:8000

# Use the generated https://xxx.trycloudflare.com URL as jackpot_api_url
# in your local .env when testing gcp_batch mode
```

Never commit a cloudflared or ngrok URL. It is a temporary dev-only override.

### Result registration callback

After a pipeline completes, its final process calls the result registration
endpoint via `curl`. This is added as a `publishDir` + `exec` step in the
JACKPOT-specific pipeline wrapper, not in the upstream nf-core pipeline itself:

```bash
curl -s -X POST "${params.jackpot_results_url}" \
    -H "Authorization: Bearer ${params.jackpot_token}" \
    -H "Content-Type: application/json" \
    -d "{\"status\": \"complete\", \"run_id\": \"${params.jackpot_run_id}\"}"
```

### resourceLabels and cost tracking

Every GCP Batch job spawned by a JACKPOT pipeline run is tagged with
`jackpot_run_id`, `jackpot_lab`, and `jackpot_pipeline` via `resourceLabels`.
These labels appear in GCP Billing and feed JACKPOT's billing dashboard
(`GET /api/v1/billing/`) which aggregates cost by lab and pipeline.
Always include `resourceLabels` in the generated config — never omit it.

### GCS work bucket lifecycle rule

The `jackpot-work` bucket has a lifecycle rule (defined in jackpot-iac)
that deletes objects older than 90 days. This prevents stale work directories
from accumulating. The lifecycle rule is applied at bucket creation — never
delete work directories manually as this breaks `-resume` for in-flight runs.

### Minimal test pipeline (verify GCP Batch connectivity)

Before implementing the full launch endpoint, verify GCP Batch connectivity
with this minimal pipeline. Run it from `scripts/test_batch.nf`:

```groovy
nextflow.enable.dsl=2

process verifyBatchNode {
    input:
    val x

    output:
    stdout

    script:
    """
    echo "JACKPOT GCP Batch test: processing ${x} on \$(hostname)"
    echo "Weblog URL: ${params.jackpot_weblog_url}"
    curl -s -o /dev/null -w "%{http_code}" -X POST "${params.jackpot_weblog_url}" \
        -H "Content-Type: application/json" \
        -d '{"event": "process_completed", "runName": "test_run"}'
    """
}

workflow {
    Channel.of('Alpha', 'Beta', 'Gamma') | verifyBatchNode | view
}
```

Run with:
```bash
nextflow run scripts/test_batch.nf \
    -c jackpot_run.config \
    -weblog http://localhost:8000/api/v1/pipelines/events
```

---

## Critical Rules (continued)

**25. Every pipeline run gets an isolated GCS work directory.**
Format: `gs://jackpot-work/{run_id}/work/`. Never share workDir between runs.
The run_id is always passed as a Nextflow parameter by the launch endpoint.
Stored in `pipeline_runs.work_dir` for `-resume` support.

**26. The Nextflow config is always generated per-run by the launch endpoint.**
Never use a static `nextflow.config` for JACKPOT pipeline runs. The launch
endpoint templates the config with run_id, API URL, weblog URL, result URL,
and pipeline token. Written to a temp file and passed via `-c jackpot_run.config`.

**27. `resourceLabels` must be included in every generated Nextflow config.**
Labels `jackpot_run_id`, `jackpot_lab`, `jackpot_pipeline` are required for
GCP Billing cost attribution and the JACKPOT billing dashboard. Never omit.

**28. Minikube is for JupyterHub only. Docker Compose is the primary dev environment.**
Do not run jackpot-backend, postgres, or minio in minikube. JupyterHub pods
reach the Docker Compose API via `minikube tunnel`. This separation mirrors
the production topology where JupyterHub and the API are separate services.

**29. On Apple Silicon, use `PIPELINE_EXECUTOR=gcp_batch` for pipeline testing.**
Many bioinformatics containers are x86-only. GCP Batch VMs are x86 by
default, avoiding ARM compatibility issues. Spot instances make this cheap
for short test runs. Only use `PIPELINE_EXECUTOR=local` for pipelines
verified to have ARM-compatible containers.

---

## GKE Autoscaling Architecture

JACKPOT uses three separate GKE node pools, each tuned to its workload.
Pipeline compute runs on GCP Batch entirely outside GKE — GKE only runs
the lightweight Nextflow controller process. Never submit pipeline tasks
as GKE pods.

### Node pool summary

| Pool | Workload | Machine type | Min nodes | Max nodes | Spot? |
|---|---|---|---|---|---|
| `api-pool` | FastAPI, Streamlit, Nextflow controllers | n2-standard-4 (4CPU/16GB) | 2 | 6 | No — always on |
| `workspace-pool` | JupyterHub user pods | n2-standard-8 (8CPU/32GB) | 0 | 10 | No — user-interactive |
| `scrubber-pool` | SRA Human Scrubber GKE Jobs | n2-highmem-4 (4CPU/32GB) | 0 | 20 | Yes — restartable |

GCP Batch (not GKE) handles all Nextflow pipeline task compute. GKE only
runs the Nextflow process itself (~2CPU/4GB) in the api-pool.

### Autoscaling per workload

**API and frontend (api-pool)**
HPA based on CPU utilization — adds FastAPI/Streamlit pods across existing
api-pool nodes when load increases. Min replicas=2 for availability.
api-pool never scales to zero — always at least 2 nodes running.

**Workspace pods (workspace-pool)**
No pod-level autoscaling — each pod is personal to one researcher, sized
by their chosen profile. Scaling unit is nodes: cluster autoscaler adds
workspace-pool nodes as more pods are scheduled. Scale-to-zero when no
workspaces active. Placeholder pod (low-priority pause container) keeps
one node warm during business hours (8am–8pm AZ) via CronJob — prevents
3–5 minute cold starts for the first researcher of the day.

**Scrubber jobs (scrubber-pool)**
GKE Jobs (not Deployments) — one Job per scrubber invocation. Scale-to-zero
when no scrubbing in progress. Cluster autoscaler adds scrubber-pool nodes
as Jobs are submitted. Spot/preemptible nodes — scrubber is restartable
if preempted (sample stays IN_PROGRESS, job resubmitted).

**Scrubber concurrency limit (critical for bulk uploads)**
When a Globus deposit brings in 100 samples simultaneously, submitting 100
GKE Jobs at once would spike cost unpredictably. Instead, a scrubber job
queue in the database controls concurrency:

- All pending scrubber jobs enter the queue as scrub_status=PENDING
- `run_scrubber_queue_job()` in backend/jobs.py fires every minute
- Checks how many scrubber jobs are currently IN_PROGRESS
- If below the concurrency limit (default=10, configurable), promotes
  the next PENDING samples to IN_PROGRESS and submits their GKE Jobs
- Runs via APScheduler locally, Cloud Scheduler in production
- Concurrency limit configurable via SCRUBBER_MAX_CONCURRENT env var

### Workspace cold start mitigation

Scale-to-zero means the first workspace launch after inactivity waits for
node provisioning (~3–5 minutes without mitigation). Two mitigations:

1. **Placeholder pod (CronJob)**: low-priority pause container keeps one
   workspace-pool node warm 8am–8pm AZ time. Evicted when a real workspace
   pod is scheduled. Defined in jackpot-iac as a Kubernetes CronJob.

2. **Pre-cached node image**: workspace-pool uses a custom node image with
   JupyterHub spawner container layers pre-cached. Reduces cold start from
   3–5 minutes to ~60–90 seconds. Defined in jackpot-iac node pool config.

### Cost controls

- **Workspace idle timeout**: 1hr (Analyst), 2hr (Bioinformatician), longer
  (Developer). Biggest single cost lever for JupyterHub.
- **Pipeline spot instances**: google.batch.spot=true in all Nextflow configs.
  ~90% cost saving. Safe because -resume recovers from preemptions.
- **Scrubber spot nodes**: scrubber-pool is preemptible. Scrubber is
  restartable — no data loss on preemption.
- **Max workspace pods per user**: JupyterHub named_server max=2.
- **GCP Budget alerts**: 50%/80%/100% of monthly budget. Defined in
  jackpot-iac. Not a hard cap — visibility only.
- **resourceLabels on all Batch jobs**: enables per-lab, per-pipeline cost
  breakdown in GCP Billing console.
- **90-day lifecycle rule on jackpot-work bucket**: deletes stale work dirs.

### IaC components (jackpot-iac)

All autoscaling configuration lives in jackpot-iac Terraform:
- Three node pool definitions with cluster autoscaler config
- HPA manifest for API and frontend deployments
- Workspace placeholder pod CronJob (8am–8pm AZ)
- Scrubber GKE Job template
- GCP Budget alert policies
- jackpot-work bucket with lifecycle rule

### New env vars

| Variable | Default | Description |
|---|---|---|
| `SCRUBBER_MAX_CONCURRENT` | `10` | Max simultaneous scrubber jobs |
| `SCRUBBER_QUEUE_INTERVAL_SECONDS` | `60` | How often queue job fires |

---

## Critical Rules (continued)

**30. Pipeline compute runs on GCP Batch, not GKE pods.**
Never submit Nextflow tasks as GKE pod workloads. GKE runs only the
Nextflow controller process (~2CPU/4GB) in the api-pool. All task compute
is submitted to GCP Batch by Nextflow directly.

**31. Bulk scrubber submissions use the queue — never submit all jobs at once.**
When multiple samples arrive simultaneously (Globus batch, CSV upload),
add all to the scrubber queue (scrub_status=PENDING). The
`run_scrubber_queue_job()` background job controls concurrency via
SCRUBBER_MAX_CONCURRENT. Never submit more than SCRUBBER_MAX_CONCURRENT
scrubber GKE Jobs simultaneously.

**32. Scrubber GKE Jobs run on the scrubber-pool using spot nodes.**
The scrubber Job manifest must include nodeSelector for scrubber-pool and
toleration for spot nodes. Scrubber is restartable — if a spot node is
preempted, the sample stays IN_PROGRESS and the job is resubmitted by
the queue job on its next cycle.

---

## Caching Architecture — Why Not Celery/Redis

JACKPOT deliberately avoids Celery and Redis as a general-purpose task
queue. Heavy compute is offloaded to GCP-native services (GCP Batch,
GKE Jobs, Cloud Scheduler) rather than managed through a worker pool.
This section documents what replaces each Celery/Redis use case and
where Redis is legitimately used.

### What replaces Celery/Redis

| APGAP pattern | JACKPOT replacement | Why |
|---|---|---|
| Celery tasks for pipeline execution | GCP Batch + Nextflow | Nextflow manages its own worker VMs |
| Celery tasks for scrubbing | GKE Jobs + scrubber queue in jobs.py | Container manages its own lifecycle |
| Celery tasks for background jobs | APScheduler (local) / Cloud Scheduler (GKE) | Lightweight DB operations, no worker needed |
| Celery tasks for email delivery | Cloud Tasks (when email is built) | GCP-native, no broker to manage |
| Celery tasks for SRA downloads | GKE Jobs | Container manages its own lifecycle |
| Redis as task broker | Not needed | No Celery |
| Redis as result backend | Not needed | Results written directly to Cloud SQL |

### Where Redis IS used — external search cache only

Multi-pod GKE deployments have a per-pod in-memory cache problem: a query
that ran on pod A is re-executed on pod B because each pod has its own
cache. For external database search results (NCBI/ENA/GISAID — 30-minute
cache) this causes unnecessary API calls to external services and
inconsistent behavior.

**Cloud Memorystore for Redis** (GCP managed Redis) is used as a shared
cache across all API pod replicas, exclusively for external search results.
Not used as a task broker, not used as a result backend, not used for
sessions or any other purpose.

### Cache abstraction (backend/cache.py)

```python
def get_cache() -> Cache:
    """
    Returns a cache instance based on SEARCH_CACHE_BACKEND env var.
    'memory' → SimpleCache (dict, local dev, single pod)
    'redis'  → RedisCache (Cloud Memorystore, GKE production)
    """

def cache_get(key: str) -> dict | None:
    """Retrieve cached value. Returns None if not found or expired."""

def cache_set(key: str, value: dict, ttl_seconds: int = 1800) -> None:
    """Store value with TTL. Default 30 minutes for external search."""

def cache_delete(key: str) -> None:
    """Invalidate a cache entry."""
```

All external search result caching goes through `backend/cache.py`.
Never use an in-memory dict directly in a router or service for shared
cache. Never cache anything other than external search results in Redis —
it is not a general-purpose cache layer.

### New environment variables

| Variable | Local dev | GCP production | Description |
|---|---|---|---|
| `SEARCH_CACHE_BACKEND` | `memory` | `redis` | Cache backend for external search results |
| `REDIS_URL` | not set | `redis://10.x.x.x:6379` | Cloud Memorystore connection string |
| `SEARCH_CACHE_TTL_SECONDS` | `1800` | `1800` | External search result TTL (default 30 min) |

### IaC

Cloud Memorystore for Redis defined in jackpot-iac Terraform:
- Basic tier, 1GB capacity (external search results are small)
- Same VPC as GKE cluster (private IP, no public endpoint)
- No persistence needed (cache is ephemeral by design)

### Cloud Tasks for future email delivery

When email notifications are implemented, use **Cloud Tasks** rather than
Celery. Cloud Tasks is GCP-native, requires no broker, and integrates
directly with GKE endpoints:

```
create_notification() writes to notifications table (synchronous, Month 1)
  ↓ (future — Month 3+)
enqueue_email_task() creates a Cloud Tasks task pointing to
  POST /api/v1/internal/send-email
  → Cloud Tasks delivers with retry logic
  → SendGrid/SES sends the email
```

Never introduce Celery. If a new async workload arises that doesn't fit
APScheduler, GKE Jobs, or Cloud Tasks, discuss before implementing.

---

## Critical Rules (continued)

**33. Never use per-pod in-memory caching for data shared across API replicas.**
In multi-pod GKE deployments, per-pod dicts create cache inconsistency.
Use `backend/cache.py` which routes to Redis (production) or a simple
dict (local dev) based on SEARCH_CACHE_BACKEND. Only external search
results are cached. Never add new cache categories without discussion.

**34. No Celery. No Redis as a task broker or result backend.**
JACKPOT uses GCP-native services for async work: GCP Batch (pipelines),
GKE Jobs (scrubber, SRA downloads), Cloud Scheduler (background jobs),
Cloud Tasks (future email). Redis is used only as a shared cache for
external search results via backend/cache.py.
