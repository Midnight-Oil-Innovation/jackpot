# JACKPOT — To-Do List

**Last updated:** 2026-04-16
**Baseline:** 384 tests passing, 84.20% coverage — Session E (sequencing_labs) complete
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

- [ ] **F-1: Implement `GET /api/v1/projects/` `?name=` filter**
  - Required for CLI project lookup by name
  - Add `?name=` query param to the projects list endpoint
  - Exact match (case-insensitive)

- [ ] **F-2: Implement `GET /api/v1/tokens/`** (authenticated user)
  - Returns user's own tokens only (never other users')
  - Shows: id, name, last_used_at, default_lab_id, default_project_id — never the token value

- [ ] **F-3: Implement `POST /api/v1/tokens/`** (authenticated user)
  - Generates a secure random token (32 bytes, URL-safe base64)
  - Stores bcrypt hash in DB
  - Returns full token value in response exactly once
  - Stores `default_lab_id` and `default_project_id` if provided

- [ ] **F-4: Implement `DELETE /api/v1/tokens/{id}`** (owner or Platform Admin)
  - Hard delete — tokens have no soft-delete lifecycle

- [ ] **F-5: Write `tests/test_tokens_api.py`**
  - Create token: response contains value; subsequent GET does not
  - Revoke own token
  - Cannot see/revoke other user's token → 403
  - Project name lookup returns correct project

- [ ] **F-6: Run tests and commit**
  - `uv run pytest tests/test_tokens_api.py -v`
  - `gac "feat: tokens router + project name filter + tests"`

---

## Phase 7 — Session G: ingest router

This is the most complex router. Read the ingest-specific reminders in
`docs/CLAUDE.md` and `spec.md` Section 5 (Session G) before writing a
single line.

- [ ] **G-1: Implement `POST /api/v1/ingest/upload`** — GUI/API file + metadata
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

- [ ] **G-2: Implement `POST /api/v1/ingest/csv`** — bulk CSV upload
  - Accepts CSV file where files column is semicolon-delimited per row
  - Processes each row through same pipeline as GUI upload
  - Returns summary: `{"success": N, "failed": M, "errors": [...]}`
  - Partial success is acceptable — does not roll back on per-row failures

- [ ] **G-3: Implement `POST /api/v1/ingest/globus`** — Globus webhook
  - Platform Admin / system token only
  - Looks up sequencing lab from Globus endpoint ID
  - Finds matching JACKPOT labs via `sequencing_lab_assignments`
  - Notifies Lab Directors via `create_notification(NotificationEvents.GLOBUS_FILES_ARRIVED, ...)`
  - Sets `scrub_status = PENDING` for all new samples
  - Returns 200 with file count

- [ ] **G-4: Write `tests/test_ingest_api.py`**
  - Valid HumanSample upload → Tier 1 PRELIMINARY, scrub_status PENDING
  - Valid HumanSample upload with all fields → Tier 3 SUBMITTABLE
  - FASTA-only upload → scrub_status SKIPPED (auto)
  - Missing `adhs_medsis_id` for HumanSample → 422
  - Unknown `sequencing_lab` → 422 with request workflow message
  - R1/R2 paired file detection works correctly
  - Non-human sample (isolate) with all fields → SUBMITTABLE, no adhs_medsis_id required
  - Audit log entry created on successful ingest
  - epiweek fields populated correctly

- [ ] **G-5: Run tests and commit**
  - `uv run pytest tests/test_ingest_api.py -v`
  - `uv run pytest --cov=backend --cov-fail-under=60`
  - `gac "feat: ingest router — upload + CSV + globus endpoints + tests"`

---

## Phase 8 — Session H: samples router

- [ ] **H-1: Implement `GET /api/v1/samples/`** (authenticated, access-controlled)
  - Full filter surface: `organism_name`, `source_type`, `sector`, `quality_status`,
    `scrub_status`, `sharing_level`, `lab_id`, `project_id`, `date_from`, `date_to`,
    `surveillance_relevant`
  - `?select_all=true` returns IDs only (no pagination) for bulk select
  - Applies `can_see_sample()` access control per row
  - Paginated via `paginate()`

- [ ] **H-2: Implement `GET /api/v1/samples/{id}`** (access-controlled)
  - Applies `can_access_sample()` — returns 403 if denied, 404 if not found
  - Returns full sample detail including associated file list

- [ ] **H-3: Implement `PATCH /api/v1/samples/{id}`** (Lab Collaborator+, own lab only)
  - Partial update via `model_dump(exclude_none=True)`
  - Must NOT allow direct update of: `quality_status`, `surveillance_relevant`,
    `scrub_status`, `mmwr_week`, `iso_week`
  - After metadata update, recompute `quality_status` and `surveillance_relevant`
    by calling validator
  - Logs `UPDATE_SAMPLE`

- [ ] **H-4: Implement `DELETE /api/v1/samples/{id}`** (Lab Director or Platform Admin)
  - Soft delete / archive — sets `is_archived=True`
  - Logs `ARCHIVE_SAMPLE`

- [ ] **H-5: Implement `GET /api/v1/samples/{id}/files`** (access-controlled)
  - Returns records from `sample_files` table for this sample
  - Applies same `can_access_sample()` check

- [ ] **H-6: Implement `GET /api/v1/samples/{id}/download`** (access-controlled)
  - Generates presigned URL via `storage.generate_presigned_url()`
  - Default TTL: 3600 seconds
  - Returns `{"url": "...", "expires_in": 3600}`

- [ ] **H-7: Write `tests/test_samples_router_api.py`**
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

- [ ] **H-8: Run tests and commit**
  - `uv run pytest tests/test_samples_router_api.py -v`
  - `uv run pytest --cov=backend --cov-fail-under=60`
  - `gac "feat: samples router — list/get/update/archive + tests"`

---

## Phase 9 — Month 1 Stretch Goals

These are important but not blocking for the core ingest/samples flow.

- [ ] **S-1: Implement `projects` router** (stub → full)
  - Required endpoints: `GET /api/v1/projects/`, `POST /`, `GET /{id}`, `PATCH /{id}`
  - `?name=` filter required (needed by CLI via tokens router)
  - Projects belong to a lab; members inherit lab access

- [ ] **S-2: Implement `dataharmonizer` router** (stub → full)
  - `GET /api/v1/templates/{source_type}/{tier}` — download CSV template
  - `POST /api/v1/templates/validate` — validate a CSV against a template
  - Templates generated by `backend/template_generator.py` — never hand-written

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
