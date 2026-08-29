# CLAUDE.md — backend/

Implementation reference for `backend/`. Migrated out of the root
`CLAUDE.md` on 2026-08-21 (doctor pass) — this content only matters
when you're implementing routers, jobs, storage, or pipeline launch
code, so it loads here instead of every session. The 67 Critical
Rules in the root CLAUDE.md still apply everywhere, including here —
this file adds detail, it doesn't replace them.

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

# With non-fatal advisory warnings (Phase P0f F-6 — e.g. /api/v1/ingest/csv
# surfacing the new EXTERNAL default when storage_intent column is absent)
{
  "success": true,
  "data": {...},
  "warnings": [
    "storage_intent column missing from CSV. Files registered with the default storage_state='EXTERNAL'..."
  ]
}
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
    "message": "Sample EXAMPLE-2026-001 not found.",
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
| `BROKEN_INPUTS` | 400 | Pipeline launch refused because one or more input `sample_files` rows are in `BROKEN` storage state (Phase P0f F-8) |
| `FILE_UNREACHABLE` | 400 | URI provided to ingest cannot be read (404, permission denied, network error). Phase P0f F-6. |
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

The `audit_log` table must already exist (it is part of the Alembic
baseline migration `5adf11b77c19`). `log_audit()` must be created in
`backend/audit.py` before the first state-changing endpoint is written.

---

## Background Job Infrastructure

Background jobs use **APScheduler** running inside the FastAPI process,
started in `backend/main.py` on application startup. This is the correct
pattern for the prototype — no separate GKE CronJob needed until Month 2+.

### Setup (backend/main.py)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.jobs import run_access_request_job, run_scrubber_queue_job

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def start_scheduler():
    scheduler.add_job(run_scrubber_queue_job, "interval", seconds=60,
                      id="scrubber_queue")
    scheduler.add_job(run_access_request_job, "cron", hour=2, minute=0,
                      id="access_request_expiry")
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
async def run_scrubber_queue_job() -> None:
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

All file storage operations go through `backend/storage/` (a multi-backend
package as of 2026-04-26). Routers never call boto3 or the GCS client
directly.

### Environment variables

| Variable | Local dev value | Production value |
|---|---|---|
| `STORAGE_ENDPOINT` | `http://minio:9000` | (unset → GCS native) |
| `STORAGE_ACCESS_KEY` | `minioadmin` | — |
| `STORAGE_SECRET_KEY` | `minioadmin` | — |
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

All functions are backend-agnostic — the `backend/storage/factory.py`
module inspects `STORAGE_ENDPOINT` at construction time and selects
S3-compatible (boto3) vs native GCS. Never branch on storage-backend
identity inside a router.

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
| `STORAGE_ENDPOINT` | `http://minio:9000` | (unset) | Set → S3-compatible mode; unset → GCS native |
| `SCHEDULER_ENABLED` | `true` | `false` | APScheduler runs locally; Cloud Scheduler takes over in GKE |
| `PIPELINE_EXECUTOR` | `local` | `gcp_batch` | Nextflow runs locally or submits to GCP Batch |
| `WORKSPACE_ENABLED` | `false` | `true` | JupyterHub launch endpoint active only in GKE |

### Component-by-component mapping

| Component | Local dev | GCP production | Transition complexity |
|---|---|---|---|
| Object storage | MinIO via boto3 | GCS via google-cloud-storage | `STORAGE_ENDPOINT` set vs unset — factory selects backend |
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

- **Production**: use the deployed API URL configured per-instance (the
  hostname under which the JACKPOT API is reachable from the GCP Batch
  network — operator's choice, not encoded in this repo per Rule 55)
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


---

## Caching Architecture — Why Not Celery/Redis

JACKPOT deliberately avoids Celery and Redis as a general-purpose task
queue. Heavy compute is offloaded to GCP-native services (GCP Batch,
GKE Jobs, Cloud Scheduler) rather than managed through a worker pool.
This section documents what replaces each Celery/Redis use case and
where Redis is legitimately used.

### What replaces Celery/Redis

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
