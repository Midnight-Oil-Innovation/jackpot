# JACKPOT — To-Do List

**Last updated:** 2026-04-16
**Baseline:** 477 tests passing, 86.99% coverage — Session S (projects + dataharmonizer) complete
**Active sprint:** Month 1 — Core Router Implementation

Instructions for Claude Code: Work through items in order. Check off each item
only after `uv run pytest` passes. Never skip an item — if blocked, note the
blocker in `docs/review_log.md` and move to the next unblocked item.

---

## Phase 0 — Pre-Session Fixes

These must be completed before any router session. They are blocking bugs.

- [x] **P0-1: Fix `tests/conftest.py` — missing Alembic migrations**
  - Add `alembic upgrade head` to the `initialize_test_db` fixture in `tests/conftest.py`
  - Verify: `uv run pytest tests/test_validator.py -v` passes (was failing due to missing columns)

- [x] **P0-2: Fix `routers/auth.py` — module-level `settings = get_settings()`**
  - Move `settings` instantiation inside function scope (match pattern in `guards.py`, `oauth.py`, `storage.py`)
  - Verify: `uv run pytest -x -v` completes without test isolation failure

- [x] **P0-3: Fix "Otero Lab" stale reference in test fixtures**
  - Run: `grep -n "Otero" tests/conftest.py tests/test_samples_api.py`
  - Fix all stale occurrences in `valid_human_sample` fixture
  - Verify: `uv run pytest tests/test_samples_api.py -v` passes

- [x] **P0-4: Add JWT refresh endpoint to `routers/auth.py`**
  - Implement `POST /api/v1/auth/refresh` using existing `issue_refresh_token()` infrastructure
  - Access tokens are 15 min; refresh tokens are 7 days
  - Verify: `uv run pytest tests/ -k "refresh" -v` passes

- [x] **P0-5: Fix `contextlib.suppress(Exception)` in test DB setup**
  - Replace bare exception suppression in `tests/conftest.py` with specific SQL error handling
  - Schema load errors must surface, not be silently swallowed
  - Verify: intentionally break `db/init.sql` temporarily and confirm test fails visibly

- [x] **P0-6: Run full test suite and confirm baseline is stable**
  - Run: `uv run pytest`
  - Expected: ≥275 tests passing, 0 failed, ≥60% coverage
  - Commit: `gac "fix: pre-session baseline fixes — conftest migrations, auth settings, fixtures"`

- [x] **P0-7: Fix `log_audit()` — forward `db_conn` to `execute_write()`**
  - Add `conn=db_conn` to the `execute_write()` call in `backend/audit.py`
  - Without this, audit writes are in separate transactions — CLIA compliance gap
  - Verify: write a test that rolls back a business write and confirms no orphan audit row

- [x] **P0-8: Fix `create_notification()` — forward `db_conn` to `execute_write()`**
  - Add `conn=db_conn` to the `execute_write()` call in `backend/notifications.py`
  - Same transactional cohesion issue as audit

- [x] **P0-9: Fix `execute_query()` — add `conn=` parameter**
  - `backend/routers/pipelines.py` calls `execute_query(..., conn=conn)` but
    `execute_query()` doesn't accept `conn=` — will crash on workflow.complete events
  - Add `conn=None` parameter matching `execute_write()` pattern

- [x] **P0-10: Fix JWT type claim validation in `guards.py`**
  - After `jwt.decode()`, check `payload.get("type") == "access"`
  - Without this, 7-day refresh tokens are accepted as 15-min access tokens

- [x] **P0-11: Fix health endpoint — return 503 when DB unavailable**
  - Change to `return JSONResponse(status_code=503, content={...})` when `db_status == "unavailable"`
  - GKE readiness probes need a non-200 to stop routing traffic to broken pods

- [x] **P0-12: Fix APScheduler job intervals and IDs in `main.py`**
  - Scrubber queue: `hours=1` → `seconds=60` (architecture doc says every 60s)
  - Access request: `hours=1` → `hours=24` or cron (architecture doc says nightly)
  - Fix job IDs: `scrub_override_auto_deny` → `scrubber_queue`; `access_request_auto_approve` → `access_request_expiry`

- [x] **P0-13: Fix validator BASE_REQUIRED — split into tier-specific lists**
  - Current BASE_REQUIRED hard-rejects samples missing Tier 2/3 fields
  - Tier 1 minimum should only require: sample_id, organism_name, source_type, sector, date_collected, collection_location_country
  - Move sequencing_lab, collection_facility, library_preparation_method, sequencing_protocol, purpose_for_collection to Tier 2 warnings

- [x] **P0-14: Add `Isolate` source type to validator**
  - Add `"Isolate": []` to `SOURCE_REQUIRED` dict (no source-specific required fields)

- [x] **P0-15: Fix validator docstring — v4.1 → v4.4**

- [x] **P0-16: Make CORS origins configurable**
  - Add `cors_origins: list[str]` to Settings class with default `["http://localhost:8501", "http://localhost:4200"]`
  - Use `settings.cors_origins` in `main.py` CORSMiddleware config
---

## Phase 1 — Session A: organizations router

- [x] **A-1: Implement `POST /api/v1/organizations/`** (Platform Admin only)
  - Accepts: `display_name`, `org_type`, `contact_email`, optional policy fields
  - Writes to `organizations` table with `active=True`
  - Calls `log_audit(AuditActions.CREATE_ORG, ...)`
  - Returns `success(data=org_dict, status_code=201)`

- [x] **A-2: Implement `GET /api/v1/organizations/`** (Platform Admin only)
  - Paginated via `paginate()`
  - Supports `?search=` filter on `display_name`
  - Returns `success_list(...)`

- [x] **A-3: Implement `GET /api/v1/organizations/{id}`** (Platform Admin or org member)
  - Returns 404 if not found
  - Returns 403 if requester has no org membership and is not Platform Admin

- [x] **A-4: Implement `PATCH /api/v1/organizations/{id}`** (Platform Admin only)
  - Uses `model_dump(exclude_none=True)` for partial update
  - Logs `UPDATE_ORG` audit action with `before`/`after` state
  - Returns updated org

- [x] **A-5: Implement `DELETE /api/v1/organizations/{id}`** (Platform Admin only)
  - Soft delete: sets `active=False`, does not physically delete
  - Returns `success_message("Organization deactivated.")`

- [x] **A-6: Write `tests/test_organizations_api.py`**
  - CRUD round-trip (create → get → patch → soft-delete)
  - Non-admin POST → 403
  - Non-admin PATCH → 403
  - GET missing org → 404
  - Pagination test (create 5 orgs, verify page/per_page behavior)

- [x] **A-7: Run tests and commit**
  - `uv run pytest tests/test_organizations_api.py -v`
  - `uv run pytest --cov=backend --cov-fail-under=60`
  - `gac "feat: organizations router — CRUD endpoints + tests"`

---

## Phase 2 — Session B: labs + lab_membership router

- [x] **B-1: Implement `POST /api/v1/labs/`** (Platform Admin only)
  - Requires valid `organization_id`
  - Sets `active=True`
  - Logs `CREATE_LAB`

- [x] **B-2: Implement `GET /api/v1/labs/`** (Platform Admin sees all; others see their labs)
  - For non-admins: joins `lab_membership` to filter to user's labs
  - Paginated

- [x] **B-3: Implement `GET /api/v1/labs/{id}`** (lab member or Platform Admin)
  - Returns 403 if requester has no membership and is not Platform Admin

- [x] **B-4: Implement `PATCH /api/v1/labs/{id}`** (Lab Director or Platform Admin)
  - Partial update with `model_dump(exclude_none=True)`
  - Logs `UPDATE_LAB`

- [x] **B-5: Implement `DELETE /api/v1/labs/{id}`** (Platform Admin only)
  - Soft delete: `active=False`

- [x] **B-6: Implement `GET /api/v1/labs/{id}/members`** (Lab Director or Platform Admin)
  - Returns list of users with their `permission_group` and `is_lab_director` flag

- [x] **B-7: Implement `POST /api/v1/labs/{id}/members`** (Lab Director or Platform Admin)
  - Adds user to `lab_membership` with a `permission_group_id`
  - Logs `ADD_LAB_MEMBER`
  - Returns 409 if user is already a member

- [x] **B-8: Implement `PATCH /api/v1/labs/{id}/members/{user_id}`** (Lab Director or Platform Admin)
  - Changes `permission_group_id` and/or `is_lab_director` flag
  - Logs `CHANGE_MEMBER_ROLE`

- [x] **B-9: Implement `DELETE /api/v1/labs/{id}/members/{user_id}`** (Lab Director or Platform Admin)
  - Removes from `lab_membership`
  - Logs `REMOVE_LAB_MEMBER`

- [x] **B-10: Write `tests/test_labs_api.py`**
  - Lab CRUD with role enforcement
  - Membership lifecycle: add → change role → remove
  - Non-member GET → 403
  - Lab Reader cannot PATCH lab → 403
  - Duplicate member add → 409

- [x] **B-11: Run tests and commit**
  - `uv run pytest tests/test_labs_api.py -v`
  - `uv run pytest --cov=backend --cov-fail-under=60`
  - `gac "feat: labs router — CRUD + lab_membership endpoints + tests"`

---

## Phase 3 — Session C: users router

- [x] **C-1: Implement `GET /api/v1/users/me`** (any authenticated user)
  - Returns full user profile including lab memberships

- [x] **C-2: Implement `GET /api/v1/users/`** (Platform Admin only)
  - Paginated, supports `?search=` on email/name
  - Returns 403 for non-admins

- [x] **C-3: Implement `GET /api/v1/users/{id}`** (Platform Admin or same user)
  - Returns 403 if requester is neither

- [x] **C-4: Implement `PATCH /api/v1/users/{id}`** (Platform Admin or same user)
  - Partial update — users can update their own name/preferences
  - Platform Admin can update `is_platform_admin`, `is_active`

- [x] **C-5: Implement `DELETE /api/v1/users/{id}`** (Platform Admin only)
  - Soft delete: sets `is_active=False`

- [x] **C-6: Write `tests/test_users_api.py`**
  - `/me` returns correct user
  - User can update own name; cannot promote self to Platform Admin
  - Platform Admin can deactivate user
  - Non-admin list → 403
  - Get other user as non-admin non-self → 403

- [x] **C-7: Run tests and commit**
  - `uv run pytest tests/test_users_api.py -v`
  - `uv run pytest --cov=backend --cov-fail-under=60`
  - `gac "feat: users router — CRUD endpoints + tests"`

---

## Phase 4 — Session D: domain_whitelist router

- [x] **D-1: Implement `GET /api/v1/domain-whitelist/`** (Platform Admin only)
- [x] **D-2: Implement `POST /api/v1/domain-whitelist/`** (Platform Admin only)
  - Normalizes domain to lowercase
  - Returns 409 on duplicate
- [x] **D-3: Implement `DELETE /api/v1/domain-whitelist/{id}`** (Platform Admin only)

- [x] **D-4: Write `tests/test_domain_whitelist_api.py`**
  - Add domain, list shows it, delete removes it
  - Duplicate add → 409
  - Non-admin → 403

- [x] **D-5: Run tests and commit**
  - `uv run pytest tests/test_domain_whitelist_api.py -v`
  - `gac "feat: domain_whitelist router + tests"`

---

## Phase 5 — Session E: sequencing_labs router

- [x] **E-1: Implement `GET /api/v1/sequencing-labs/`** (any authenticated user)
  - Returns all sequencing labs including seed data (Sonora Quest, LabCorp, Otero Outpost)

- [x] **E-2: Implement `POST /api/v1/sequencing-labs/`** (Platform Admin only)
- [x] **E-3: Implement `GET /api/v1/sequencing-labs/{id}`** (any authenticated user)
- [x] **E-4: Implement `PATCH /api/v1/sequencing-labs/{id}`** (Platform Admin only)

- [x] **E-5: Implement `POST /api/v1/sequencing-labs/{id}/assign/{lab_id}`** (Platform Admin)
  - Inserts into `sequencing_lab_assignments` (sequencing_lab_id, lab_id)
  - Returns 409 if assignment already exists

- [x] **E-6: Implement `DELETE /api/v1/sequencing-labs/{id}/assign/{lab_id}`** (Platform Admin)

- [x] **E-7: Write `tests/test_sequencing_labs_api.py`**
  - Seed data visible in list
  - CRUD lifecycle
  - Assignment round-trip
  - Non-admin create → 403

- [x] **E-8: Run tests and commit**
  - `uv run pytest tests/test_sequencing_labs_api.py -v`
  - `gac "feat: sequencing_labs router — CRUD + assignments + tests"`

---

## Phase 6 — Session F: tokens router

- [x] **F-1: Implement `GET /api/v1/projects/` `?name=` filter**
  - Required for CLI project lookup by name
  - Add `?name=` query param to the projects list endpoint
  - Exact match (case-insensitive)

- [x] **F-2: Implement `GET /api/v1/tokens/`** (authenticated user)
  - Returns user's own tokens only (never other users')
  - Shows: id, name, last_used_at, default_lab_id, default_project_id — never the token value

- [x] **F-3: Implement `POST /api/v1/tokens/`** (authenticated user)
  - Generates a secure random token (32 bytes, URL-safe base64)
  - Stores bcrypt hash in DB
  - Returns full token value in response exactly once
  - Stores `default_lab_id` and `default_project_id` if provided

- [x] **F-4: Implement `DELETE /api/v1/tokens/{id}`** (owner or Platform Admin)
  - Hard delete — tokens have no soft-delete lifecycle

- [x] **F-5: Write `tests/test_tokens_api.py`**
  - Create token: response contains value; subsequent GET does not
  - Revoke own token
  - Cannot see/revoke other user's token → 403
  - Project name lookup returns correct project

- [x] **F-6: Run tests and commit**
  - `uv run pytest tests/test_tokens_api.py -v`
  - `gac "feat: tokens router + project name filter + tests"`

---

## Phase 7 — Session G: ingest router

This is the most complex router. Read the ingest-specific reminders in
`docs/CLAUDE.md` and `spec.md` Section 5 (Session G) before writing a
single line.

- [x] **G-1: Implement `POST /api/v1/ingest/upload`** — GUI/API file + metadata
  - Accepts multipart: `metadata` (JSON), `fastq_r1` (file), `fastq_r2` (optional file)
  - Validates `sequencing_lab` against DB — 422 with request workflow message if unknown
  - Calls `validator.validate(metadata)` → ValidationResult
  - Calls `compute_epiweeks(date_collected, precision)` from ValidationResult
  - Sets `scrub_status = PENDING` (raw reads) or `SKIPPED` (FASTA-only, via validator)
  - Calls `compute_surveillance_relevant()` and `compute_quality_status()` from validator
  - Stages files via `storage.stage_file()`
  - Calls `file_detector.detect_files()` for pairing, convenience URI population
  - Writes to `samples` table then `sample_files` table in same transaction
  - Calls `log_audit(AuditActions.CREATE_SAMPLE, ...)`
  - Returns `success(data=sample_dict, status_code=201)`

- [x] **G-2: Implement `POST /api/v1/ingest/csv`** — bulk CSV upload
  - Accepts CSV file where files column is semicolon-delimited per row
  - Processes each row through same pipeline as GUI upload
  - Returns summary: `{"success": N, "failed": M, "errors": [...]}`
  - Partial success is acceptable — does not roll back on per-row failures

- [x] **G-3: Implement `POST /api/v1/ingest/globus`** — Globus webhook
  - Platform Admin / system token only
  - Looks up sequencing lab from Globus endpoint ID
  - Finds matching JACKPOT labs via `sequencing_lab_assignments`
  - Notifies Lab Directors via `create_notification(NotificationEvents.GLOBUS_FILES_ARRIVED, ...)`
  - Sets `scrub_status = PENDING` for all new samples
  - Returns 200 with file count

- [x] **G-4: Write `tests/test_ingest_api.py`**
  - Valid HumanSample upload → Tier 1 PRELIMINARY, scrub_status PENDING
  - Valid HumanSample upload with all fields → Tier 3 SUBMITTABLE
  - FASTA-only upload → scrub_status SKIPPED (auto)
  - Missing `adhs_medsis_id` for HumanSample → 422
  - Unknown `sequencing_lab` → 422 with request workflow message
  - R1/R2 paired file detection works correctly
  - Non-human sample (isolate) with all fields → SUBMITTABLE, no adhs_medsis_id required
  - Audit log entry created on successful ingest
  - epiweek fields populated correctly

- [x] **G-5: Run tests and commit**
  - `uv run pytest tests/test_ingest_api.py -v`
  - `uv run pytest --cov=backend --cov-fail-under=60`
  - `gac "feat: ingest router — upload + CSV + globus endpoints + tests"`

---

## Phase 8 — Session H: samples router

- [x] **H-1: Implement `GET /api/v1/samples/`** (authenticated, access-controlled)
  - Full filter surface: `organism_name`, `source_type`, `sector`, `quality_status`,
    `scrub_status`, `sharing_level`, `lab_id`, `project_id`, `date_from`, `date_to`,
    `surveillance_relevant`
  - `?select_all=true` returns IDs only (no pagination) for bulk select
  - Applies `can_see_sample()` access control per row
  - Paginated via `paginate()`

- [x] **H-2: Implement `GET /api/v1/samples/{id}`** (access-controlled)
  - Applies `can_access_sample()` — returns 403 if denied, 404 if not found
  - Returns full sample detail including associated file list

- [x] **H-3: Implement `PATCH /api/v1/samples/{id}`** (Lab Collaborator+, own lab only)
  - Partial update via `model_dump(exclude_none=True)`
  - Must NOT allow direct update of: `quality_status`, `surveillance_relevant`,
    `scrub_status`, `mmwr_week`, `iso_week`
  - After metadata update, recompute `quality_status` and `surveillance_relevant`
    by calling validator
  - Logs `UPDATE_SAMPLE`

- [x] **H-4: Implement `DELETE /api/v1/samples/{id}`** (Lab Director or Platform Admin)
  - Soft delete / archive — sets `is_deleted=True`, `deleted_at=NOW()`, `deleted_by_id`
    (init.sql samples table uses `is_deleted`, not `is_archived`)
  - Logs `ARCHIVE_SAMPLE`

- [x] **H-5: Implement `GET /api/v1/samples/{id}/files`** (access-controlled)
  - Returns records from `sample_files` table for this sample
  - Applies same `can_access_sample()` check

- [x] **H-6: Implement `GET /api/v1/samples/{id}/download`** (access-controlled)
  - Generates presigned URL via `storage.generate_presigned_url()`
  - Default TTL: 3600 seconds
  - Returns `{"url": "...", "expires_in": 3600}`

- [x] **H-7: Write `tests/test_samples_router_api.py`**
  - Get own sample (Lab Collaborator) → 200
  - Get other lab's PRIVATE sample → 403
  - Get DISCOVERABLE sample → 200 for authenticated users
  - Get PUBLIC sample → 200 for any authenticated user
  - PATCH own sample → metadata updated, quality_status recomputed
  - PATCH locked fields (quality_status) → rejected
  - Archive (Lab Director) → is_archived True
  - Archive (Lab Collaborator) → 403
  - Filter by `organism_name` → returns only matching samples
  - `?select_all=true` returns IDs only

- [x] **H-8: Run tests and commit**
  - `uv run pytest tests/test_samples_router_api.py -v`
  - `uv run pytest --cov=backend --cov-fail-under=60`
  - `gac "feat: samples router — list/get/update/archive + tests"`

---

## Phase 9 — Month 1 Stretch Goals

These are important but not blocking for the core ingest/samples flow.

- [x] **S-1: Implement `projects` router** (stub → full)
  - Required endpoints: `GET /api/v1/projects/`, `POST /`, `GET /{id}`, `PATCH /{id}`
  - `?name=` filter required (needed by CLI via tokens router)
  - Projects belong to a lab; members inherit lab access
  - Added `?lab_id=` filter; list filters non-admins to their lab/project membership
  - Added `AuditActions.CREATE_PROJECT` / `UPDATE_PROJECT`
  - 15 new tests in `tests/test_projects_api.py`

- [x] **S-2: Implement `dataharmonizer` router** (stub → full)
  - `GET /api/v1/dataharmonizer/templates/{source_type}/{tier}` — download CSV template
  - `POST /api/v1/dataharmonizer/validate` — validate a CSV against the LinkML schema
  - Templates generated by `backend/template_generator.py` — never hand-written
  - Validation delegates to `backend.validator.validate_sample` row-by-row
  - Removed `backend/routers/dataharmonizer.py` from coverage omit (94% covered)
  - 12 new tests in `tests/test_dataharmonizer_api.py`

- [ ] **S-3: Full test suite regression check**
  - `uv run pytest`
  - All tests passing, coverage ≥ 60%
  - Merge `development` → `main`

---

## Phase 10 — Month 2 (Future)

Tracked here for completeness. Not in scope for Month 1.

- [ ] `sample_access` router — access request lifecycle (submit / approve / deny / expire)
- [ ] `notifications` router — GET notifications, mark read
- [ ] `pipelines` router — launch, status, weblog callback, results
- [ ] `ncbi_submissions` router — BioSample / SRA submission workflow
- [ ] `datasets` router — analytical dataset creation and export
- [ ] `archive_requests` router — formal deletion request workflow
- [ ] `saved_searches` router — save and recall search filter sets
- [ ] JupyterHub workspace integration (Minikube setup, spawner profiles)
- [ ] Streamlit frontend pages (dashboard, search, upload, lab director, platform admin)
- [ ] US-states controlled vocabulary for `collection_location_state`
- [ ] Rate limiting on public endpoints
- [ ] CORS restriction from dev wildcard to specific origins
- [ ] Re-enable detect-secrets in `.pre-commit-config.yaml` before first GCP deployment

---

## Periodic Review Checkpoint

After every ~20 completed tasks, pause and run this review:

```
Review spec.md and the current implementation for gaps.
Check: are all Critical Rules from CLAUDE.md being followed?
Check: has coverage stayed above 60%?
Check: are there any TODO comments or placeholder code left in place?
Log findings to docs/review_log.md and resolve before continuing.
```

- [ ] **SEC-1: Tighten CORS methods/headers in `backend/main.py`** — replace `allow_methods=["*"]` with `["GET","POST","PATCH","DELETE","OPTIONS"]` and restrict `allow_headers` to the actually needed set
- [ ] **SEC-2: Add rate limiting** — `slowapi` on auth endpoints (`/api/v1/auth/login`, `/api/v1/auth/callback`) and ingest endpoints before GCP deployment

- [ ] **DEPLOY-1: Document staging→production gate** — add a required manual approval step in `.github/workflows/` before production deploy
- [ ] **DEPLOY-2: Test backup restore** — run a full PITR restore drill to a separate Cloud SQL instance before going live with real data

## Phase 11 — Session I: jackpot-nf plugin scaffolding + result registration endpoint

- [x] **I-1: Create new `jackpot-nf` repo**

  - Location: `~/ASU/jackpot/jackpot-nf`

  - Structure:

    ```
    jackpot-nf/
    ├── plugins/nf-jackpot/       # Nextflow plugin — generic weblog/workdir
    ├── pipelines/                # Per-pipeline wrapper directories (populated in Sessions J-M)
    ├── shared/
    │   ├── jackpot_register_client.py
    │   ├── hamronization_normalizer.py
    │   └── schemas/              # Pydantic result payloads
    ├── tests/
    │   └── fixtures/             # Real pipeline outputs per pipeline
    ├── pyproject.toml
    └── README.md
    ```

  - Add to `jackpot-backend` as git submodule at `nf/`

  - Verify: `git submodule status` shows jackpot-nf

- [x] **I-2: Implement `jackpot_register_client.py`**

  - Shared HTTP client used by all parsers to POST results back to JACKPOT
  - Reads `JACKPOT_API_URL`, `JACKPOT_RUN_ID`, `JACKPOT_PIPELINE_TOKEN` from env
  - Single method: `register_result(result_type: str, payload: dict) -> dict`
  - Retries on 5xx with exponential backoff (max 3 attempts)
  - Raises `RegistrationError` on 4xx or persistent 5xx

- [x] **I-3: Define Pydantic result schemas in `shared/schemas/`**

  - One schema per result table: `AMRResult`, `TypingResult`, `PangolinResult`, `NextcladeResult`, `TBTypingResult`, `AssemblyQC`, `MAGQC`, `TaxonomicProfile`, `WastewaterLineageAbundance`
  - Each schema mirrors the corresponding DB table exactly
  - Shared with `backend/models_generated.py` via schema import

- [x] **I-4: Implement `POST /api/v1/pipelines/{run_id}/results/{result_type}`**

  - Router: `backend/routers/pipelines.py`
  - Auth: `pipeline_token` from header must match `pipeline_runs.pipeline_token`
  - Validates payload against result_type's Pydantic schema
  - Writes to correct typed table in same transaction as pipeline_results metrics update
  - Returns `{"status": "registered", "result_id": N}`

- [x] **I-5: Implement `hamronization_normalizer.py`**

  - Wrapper around hAMRonization tool (pip install hAMRonization)
  - Input: raw AMR output file + tool name (amrfinderplus / resfinder / rgi)
  - Output: list of AMRResult objects in canonical format
  - Used by bactopia, Grandeur, and pathogensurveillance parsers

- [x] **I-6: Write `tests/test_pipelines_registration_api.py`**

  - Valid registration → 201, result in DB
  - Wrong pipeline_token → 401
  - Invalid payload schema → 422 with specific field errors
  - Duplicate registration → 409 or idempotent update (decide via spec)
  - Test fixture: mock pipeline_runs row with valid pipeline_token

- [x] **I-7: Run tests and commit**

  - `uv run pytest tests/test_pipelines_registration_api.py -v`
  - `uv run pytest --cov=backend --cov-fail-under=60`
  - `gac "feat: jackpot-nf scaffolding + result registration endpoint"`

---

## Phase 12 — Session J: Viral pipeline parsers (Cecret, viralrecon, walkercreek)

- [x] **J-1: Cecret parser** (`jackpot-nf/pipelines/cecret/parsers/`)
  - `pangolin.py`: parse `pangolin/lineage_report.csv` → PangolinResult per sample
  - `nextclade.py`: parse `nextclade/nextclade.tsv` → NextcladeResult per sample
  - `freyja.py`: parse `freyja/aggregated-freyja.tsv` → WastewaterLineageAbundance
  - `consensus.py`: register `consensus/*.consensus.fa` → sample_files (FASTA)
  - Wrapper: `jackpot_wrapper.nf` — calls Cecret, then runs parsers, then calls register_client
  - Supports Cecret version range 3.6–3.66 (current)

- [x] **J-2: viralrecon parser** (`jackpot-nf/pipelines/viralrecon/parsers/`)
  - `consensus.py`: register `*.consensus.fa` per sample
  - `pangolin.py`: parse pangolin output (shares Cecret's parser via `shared/`)
  - `nextclade.py`: parse nextclade output (shares Cecret's parser)
  - `variants.py`: parse iVar variant calls → pipeline_results.metrics
  - Wastewater mode: also populate WastewaterLineageAbundance

- [x] **J-3: walkercreek parser** (`jackpot-nf/pipelines/walkercreek/parsers/`)
  - `irma.py`: parse IRMA flu/RSV output → TypingResult (subtype, clade)
  - `consensus.py`: register per-segment consensus FASTAs
  - Handles both Illumina and Nanopore output structures

- [x] **J-4: Test fixtures for viral parsers**
  - Small real outputs from Cecret (SARS-CoV-2, MPX), viralrecon (wastewater), walkercreek (flu)
  - Store in `tests/fixtures/cecret/`, `tests/fixtures/viralrecon/`, `tests/fixtures/walkercreek/`
  - Each fixture is a minimal output directory that covers all parsed file types

- [x] **J-5: Unit tests per parser**
  - Each parser has `tests/test_{parser}.py`
  - Parses fixture → emits expected list of result payloads
  - Schema validation passes
  - Edge cases: empty file, malformed file, missing expected field

- [x] **J-6: Run tests and commit in jackpot-nf**
  - `cd jackpot-nf && uv run pytest` — 79/79 passing (was 35)
  - Commit in jackpot-nf repo — `2a098b0`
  - Update submodule pointer in jackpot-backend
  - `gac "feat: viral pipeline parsers — Cecret, viralrecon, walkercreek"`

---

## Phase 13 — Session K: Bacterial isolate parsers (bactopia, Grandeur, mycosnp, tb-profiler)

- [ ] **K-1: bactopia parser**
  - `amr.py`: parse AMRFinderPlus TSV → hAMRonization-normalized AMRResult
  - `mlst.py`: parse MLST output → TypingResult
  - `assembly.py`: register assembly FASTA + parse QUAST metrics → AssemblyQC
  - `annotation.py`: register Bakta/Prokka GFF to sample_files

- [ ] **K-2: Grandeur parser**
  - `amr.py`: parse AMRFinderPlus output (shares bactopia normalizer)
  - `mlst.py`: parse MLST (shares bactopia parser)
  - `kraken2.py`: parse Kraken2 species ID → TaxonomicProfile (single-organism isolate)
  - `blast.py`: parse BLAST against local DB → pipeline_results.metrics

- [ ] **K-3: mycosnp-nf parser**
  - `snippy.py`: parse variant calls → pipeline_results.metrics
  - `tree.py`: register SNP tree Newick to sample_files
  - `typing.py`: fungal MLST when available → TypingResult

- [ ] **K-4: tb-profiler parser**
  - `lineage.py`: parse lineage JSON → TBTypingResult (lineage, spoligotype)
  - `drug_resistance.py`: parse DR calls → TBTypingResult.who_drug_susceptibility JSONB
  - Populates tb_typing_results table specifically

- [ ] **K-5: Test fixtures + unit tests**
  - Real outputs from each of the four pipelines
  - One fixture per parser at minimum

- [ ] **K-6: Run tests and commit**

---

## Phase 14 — Session L: Metagenomic parsers (nf-core/mag, nf-core/taxprofiler)

- [ ] **L-1: nf-core/mag parser**
  - `checkm2.py`: parse CheckM2 output → MAGQC per MAG bin (completeness, contamination, strain heterogeneity, bin size)
  - `gtdbtk.py`: parse GTDB-Tk taxonomy → TaxonomicProfile
  - `bin_registry.py`: register each MAG bin as assembly file linked to sample
  - Critical: handle one-sample-to-many-MAGs relationship (sample_associations with type=mag_bin)

- [ ] **L-2: nf-core/taxprofiler parser**
  - `kraken2.py`: parse Kraken2 report → TaxonomicProfile (ranked list of taxa with abundance)
  - `bracken.py`: parse Bracken abundance estimates → TaxonomicProfile
  - `diamond.py`: parse DIAMOND protein profile (when present) → pipeline_results.metrics
  - Reuses Grandeur's kraken2 parser where possible

- [ ] **L-3: Test fixtures + unit tests**

- [ ] **L-4: Run tests and commit**

---

## Phase 15 — Session M: Pathogensurveillance parser + AMR/typing shared parsers

- [ ] **M-1: nf-core/pathogensurveillance parser** (version 1.1.0 pinned)
  - `identification.py`: parse sendsketch output → TaxonomicProfile + identified organism
  - `amr.py`: parse AMR results (shares bactopia normalizer)
  - `mlst.py`: parse MLST results (shares bactopia parser)
  - `phylogeny.py`: register SNP tree + core gene tree + BUSCO tree to sample_files
  - `variants.py`: parse graphtyper VCF → pipeline_results.metrics (variant count, filtered count)
  - `report.py`: register the interactive HTML report to sample_files (served via presigned URL)

- [ ] **M-2: Shared AMR normalization validator**
  - Test that AMR results from bactopia, Grandeur, and pathogensurveillance produce comparable canonical AMRResult output
  - Catches divergence when underlying tools update output formats

- [ ] **M-3: Parser version matrix**
  - Document in `jackpot-nf/README.md`: which parser version supports which pipeline version range
  - Add `parser_version` column to `pipeline_catalog` table (schema migration)
  - Wrapper validates pipeline version at run start, warns if outside supported range

- [ ] **M-4: End-to-end integration test**
  - Not a unit test — a full workflow test that simulates running all 11 wrapped pipelines against fixtures
  - Verifies each parser produces valid result payloads
  - Skipped in CI by default (slow), run manually before tagging releases

- [ ] **M-5: Run tests and commit**

---

## Phase 16 — Session N: pipelines router (launch, monitor, resume, BYOP skeleton)

- [ ] **N-1: Implement `POST /api/v1/pipelines/launch`**
  - Request body: `{pipeline_id, sample_ids, parameters, project_id}`
  - Compatibility check: `compute_pipeline_compatibility()` returns soft_warnings + hard_blocks
  - Hard block returns 422 with detailed reason
  - Soft warning returns 202 with warnings list, caller must confirm with `?override=true`
  - Generates per-run config with `pipeline_config.py` (work_dir, weblog URL, pipeline_token, resourceLabels)
  - Submits to GCP Batch via Nextflow launcher
  - Writes pipeline_runs row with status=QUEUED, returns `{run_id, status}`
  - Logs CREATE_PIPELINE_RUN audit

- [ ] **N-2: Implement `POST /api/v1/pipelines/events`**
  - No auth — run_id in path acts as bearer (but cross-check pipeline_token header per audit SEC-4)
  - Receives raw Nextflow weblog JSON
  - Writes to pipeline_events (raw) and updates pipeline_tasks (parsed)
  - Updates pipeline_runs.status on workflow-level events (started/completed/failed)

- [ ] **N-3: Implement `GET /api/v1/pipelines/{run_id}`**
  - Returns full run detail + last 20 events + task summary
  - Access control: lab member or Platform Admin
  - 403 if user has no access to the owning lab

- [ ] **N-4: Implement `GET /api/v1/pipelines/{run_id}/tasks`** and `GET /api/v1/pipelines/{run_id}/events`
  - Paginated
  - Same access control

- [ ] **N-5: Implement `POST /api/v1/pipelines/{run_id}/resume`**
  - Requires previous run to be in FAILED state
  - New pipeline_runs row created with new run_id
  - pipeline_restarts row links new_run_id ↔ previous_run_id
  - Reuses same work_dir for Nextflow -resume
  - Logs RESUME_PIPELINE_RUN audit

- [ ] **N-6: Implement BYOP registration skeleton `POST /api/v1/pipelines/custom`**
  - Accepts GitHub/GitLab URL + revision + parameter schema
  - Validates schema JSON shape only (no actual Nextflow fetch in Month 2 — that's Month 3)
  - Writes to project_pipelines with status=UNVERIFIED
  - Returns 202 with message "BYOP registered pending verification (Month 3 feature)"

- [ ] **N-7: Implement pipeline promotion `POST /api/v1/pipelines/{id}/promote`**
  - project → lab: requires Lab Director
  - lab → zoo: requires Platform Admin
  - Logged with source tier, target tier, promoter user_id

- [ ] **N-8: Write `tests/test_pipelines_router_api.py`**
  - Launch with valid sample_ids → 201 + run_id
  - Launch with hard_block → 422
  - Launch with soft_warning → 202, then ?override=true → 201
  - Events callback with valid run_id → 200, row written
  - Get run detail → 200 with tasks + events
  - Resume FAILED run → new run_id, restart row created
  - Resume non-FAILED run → 400
  - BYOP registration returns 202 (not full implementation)
  - Promote project→lab as Lab Collaborator → 403
  - Promote project→lab as Lab Director → 200

- [ ] **N-9: Run tests and commit**
  - `gac "feat: pipelines router — launch, monitor, resume, BYOP skeleton"`

---

## Phase 17 — Session O: sample_access router

- [ ] **O-1: Implement `POST /api/v1/sample_access/requests`**
  - Request body: `{sample_id, justification, requested_duration_days}`
  - Sample must be DISCOVERABLE (not PRIVATE/LAB — those require Lab Director to change sharing_level)
  - Creates row in sample_access_requests with status=PENDING, auto_approve_after=NOW+7d
  - Notifies Lab Director of owning lab
  - Returns 201 with request_id

- [ ] **O-2: Implement `GET /api/v1/sample_access/requests`**
  - Filters: `?status=`, `?lab_id=` (owning lab), `?requester_id=`
  - Lab Director sees pending requests for their labs
  - Platform Admin sees all
  - Requester sees their own

- [ ] **O-3: Implement `POST /api/v1/sample_access/requests/{id}/approve`**
  - Lab Director or Platform Admin only
  - Sets status=APPROVED, access_expires_at = NOW + requested_duration_days
  - Creates access grant in sample_access_grants table
  - Notifies requester

- [ ] **O-4: Implement `POST /api/v1/sample_access/requests/{id}/deny`**
  - Lab Director or Platform Admin only
  - Sets status=DENIED, optional denial_reason
  - Notifies requester

- [ ] **O-5: Update `can_access_sample()` in guards.py**
  - Add check: user has active grant in sample_access_grants for this sample
  - Grant must not be expired (access_expires_at > NOW)

- [ ] **O-6: Background job: access request expiry**
  - Already in main.py scheduler — wire up logic in `run_access_request_job()` in `backend/jobs.py`
  - Auto-approve at auto_approve_after
  - Send 75-day warning at auto_approve_after - 15 days
  - Send 7-day expiry warning before access_expires_at
  - Expire grants where access_expires_at <= NOW

- [ ] **O-7: Write `tests/test_sample_access_router_api.py`**
  - Request access to DISCOVERABLE sample → 201
  - Request access to PRIVATE sample → 403
  - Approve as Lab Director → grant created, can_access_sample() returns True
  - Deny as Lab Director → status DENIED
  - Auto-approve past auto_approve_after via scheduler → status AUTO_APPROVED
  - Expired grant → can_access_sample() returns False

- [ ] **O-8: Run tests and commit**

---

## Phase 18 — Session P: Streamlit researcher pages

- [ ] **P-1: `frontend/pages/dashboard.py`** — personal dashboard
  - Recent samples (last 10), pending access requests, active pipeline runs
  - Tier badges, quality_status indicators
  - Uses `GET /api/v1/samples/?owner=me`, `/sample_access/requests?requester_id=me`, `/pipelines/?user_id=me`

- [ ] **P-2: `frontend/pages/search.py`** — sample search
  - Full filter sidebar: organism, source_type, sector, quality_status, sharing_level, lab, project, date range
  - Bulk select with select-all-N, persistent selection across filter changes
  - Split action bar: export / launch pipeline / add to dataset / request access
  - Tier badges on each result row
  - External database search toggle (JACKPOT samples vs external — uses `/api/v1/external-search/` when implemented; placeholder message for Month 2)

- [ ] **P-3: `frontend/pages/upload.py`** — ingest UI
  - Drag-and-drop file upload + metadata form
  - Live tier indicator as fields are completed
  - Scrubber skip request button with justification
  - Multi-file support: shows paired R1/R2 detection, lane grouping
  - Calls `POST /api/v1/ingest/upload`

- [ ] **P-4: `frontend/pages/data_entry.py`** — guided metadata entry
  - Used for completing pending Globus-imported samples and editing existing samples
  - Pre-filled form from sample record
  - Post-submission edit warning for NCBI/GISAID-submitted samples (per backlog topic 57)
  - Auto-save draft every 30s
  - Calls `PATCH /api/v1/samples/{id}`

- [ ] **P-5: `frontend/pages/my_samples.py`** — user's samples
  - Table of samples where current user is owner/submitting_lab_member
  - Tier badges, scrub_status icons, quick edit link
  - Filters: only mine / my lab / my project

- [ ] **P-6: `frontend/pages/datasets.py`** — analytical datasets
  - List user's accessible datasets
  - Create new dataset from selection (flows back from search page)
  - Export: CSV / BCO / sample manifest
  - Microreact integration stub

- [ ] **P-7: `frontend/pages/access_requests.py`** — access request management
  - Tabs: my requests (as requester) / incoming (as Lab Director)
  - Approve/deny UI with grant duration selector
  - Request history with status timeline

- [ ] **P-8: `frontend/pages/notifications.py`** — notification inbox
  - List with read/unread filter
  - Mark all read button
  - Click notification → navigate to action_url
  - Calls `GET /api/v1/notifications/` (router deferred to Month 3, use placeholder)

- [ ] **P-9: `frontend/pages/pipelines.py`** — pipeline launch + monitor
  - Launch dialog: pipeline selector, parameter form auto-generated from nextflow_schema.json
  - Compatibility check badges (soft warnings overridable, hard blocks explained)
  - Four-tab monitoring view: Overview / Tasks / Events / Files
  - Resume button for FAILED runs
  - MultiQC iframe for completed runs

- [ ] **P-10: Write `tests/test_streamlit_pages.py`**
  - Smoke tests: each page imports cleanly, renders without errors
  - Mock API responses, verify page reacts correctly
  - No full end-to-end UI tests in Month 2 (Playwright deferred to Month 3)

- [ ] **P-11: Run tests and commit**

---

## Phase 19 — Session Q: GCP staging environment (IaC + deploy)

- [ ] **Q-1: jackpot-iac Terraform for staging**
  - `jackpot-iac/terraform/staging/`
  - Cloud SQL instance (smallest tier, daily backups, PITR 7 days)
  - GKE cluster with 3 node pools (api-pool min=1, workspace-pool min=0, scrubber-pool min=0)
  - GCS buckets: jackpot-staging-raw, jackpot-staging-sequences, jackpot-staging-work, jackpot-staging-results, jackpot-staging-datasets, jackpot-staging-submissions, jackpot-staging-backups
  - All lifecycle rules configured per architecture doc
  - resourceLabels on all resources: `env=staging`, `project=jackpot`

- [ ] **Q-2: Secrets Manager entries**
  - SECRET_KEY, Google OAuth client/secret, NCBI API key, GISAID credentials
  - All generated fresh, not reused from local dev

- [ ] **Q-3: Cloud Deploy or GitHub Actions deployment pipeline**
  - Trigger: push to `staging` branch
  - Steps: build image → push to Artifact Registry → helm upgrade api/scrubber/nextflow deployments → run `alembic upgrade head` against Cloud SQL
  - Staging uses separate Docker image tags from production

- [ ] **Q-4: Deploy jackpot-backend to staging**
  - Alembic migrations run against Cloud SQL
  - Seed data loaded (orgs, labs, sequencing_labs, reportable_organisms, pipeline_catalog)
  - Health check returns 200 from staging endpoint

- [ ] **Q-5: End-to-end pipeline test on staging**
  - Run Cecret against a SARS-CoV-2 test sample through full stack
  - Verify: sample uploaded → staged → scrubbed → pipeline launched → events received → results registered → pangolin_results/nextclade_results tables populated
  - Document in `docs/staging_e2e_test.md`

- [ ] **Q-6: Staging smoke test suite**
  - `scripts/staging_smoke_test.sh` — hits all endpoints, verifies auth, runs one pipeline
  - Run after every staging deploy
  - Red/green dashboard

- [ ] **Q-7: Document staging access**
  - `docs/staging_access.md` — how to reach staging, who has access, how to redeploy
  - Add staging URLs to `.env.staging` template

- [ ] **Q-8: Commit and tag**
  - `gac "feat: GCP staging environment — IaC + deployment + E2E verified"`
  - `git tag -a month-2-complete -m "Month 2 complete: pipelines + parsers + sample_access + Streamlit + GCP staging"`

---

## Phase 20 — Month 3 Stretch Goals (Tracked, Not Scheduled)

- [ ] Streamlit admin pages: `lab_director.py`, `platform_admin.py`, `archive_requests.py`, `billing.py`
- [ ] JupyterHub workspace with all three profiles (Analyst, Bioinformatician, Developer)
- [ ] BYOP wire-up: fetch nextflow_schema.json from registered repo, validate, enable launching
- [ ] GCP production deployment
- [ ] `ncbi_submissions` router (TOSTADAS integration)
- [ ] `datasets` router (table exists, router stub)
- [ ] `archive_requests` router
- [ ] `saved_searches` router
- [ ] `notifications` router (full)
- [ ] Remaining parsers if any pipelines were deferred
- [ ] External database search (`/api/v1/external-search/` — NCBI, ENA, GISAID proxy)
- [ ] Re-enable detect-secrets in pre-commit
- [ ] Playwright end-to-end UI tests
