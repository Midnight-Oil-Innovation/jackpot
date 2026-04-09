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
