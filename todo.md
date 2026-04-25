# JACKPOT — To-Do List

**Last updated:** 2026-04-19 early AM (post-Session 5 — staging deploy + Streamlit local debug)
**Baseline:** 477 tests passing, 86.99% coverage — Session S (projects + dataharmonizer) complete, Session 5 staging deploy work landed on top
**Active sprint:** Phase 21 (UI page triage) + Phase 20 (Session 5 debt)

Instructions for Claude Code: Work through items in order within each phase.
Check off each item only after `uv run pytest` passes. Never skip an item —
if blocked, note the blocker in `docs/review_log.md` and move to the next
unblocked item.

---

## Current state (verified end of Session 5)

**Backend — Month 1 + most of Month 2 complete:**

- **Fully implemented routers:** `auth`, `gisaid`, `organizations`, `labs`
  (including `lab_membership`), `projects`, `users`, `domain_whitelist`,
  `sequencing_labs`, `tokens`, `dataharmonizer`, `ingest` (upload, csv,
  globus), `samples` (list, get, update, archive, files, download),
  `pipelines` (launch, events, monitor, results, resume, BYOP,
  promotion — 10 endpoints), `sample_access`, `templates`.
- **Backend modules:** `validator`, `file_detector`, `harmonizer`,
  `epiweek`, `audit`, `permissions`, `dlp_scanner`,
  `pipeline_results_loader`, `pipeline_config`, `template_generator`,
  `notifications`, `responses`, `pagination`, `storage`, `config`,
  `database`, `middleware`, `logging`, `version`.
- **jackpot-nf:** 11 pipeline parsers (viral, bacterial, metagenomic),
  nf-jackpot plugin, shared result schemas, hamronization normalizer.
- **Test suite:** 477 tests passing, 86.99% coverage as of Session S
  complete. Session 5 added staging infra changes without net-new test
  coverage.
- **Local Docker Compose stack:** running cleanly — `api`, `postgres`,
  `minio`, `minio_init`, `ui` all green. `/health` returns DB-connected.
- **GCP staging:** deployed Session 5, API live, `/health` green
  in-cluster. 6 known quirks from Session 5 debugging documented in
  `docs/staging_access.md`.

**Frontend — scaffold complete, renders, authenticates:**

- Streamlit pages live in `jackpot-backend/frontend/` (not the separate
  `jackpot-frontend` repo, which is a vestigial stub).
- All 9 researcher pages exist: `dashboard`, `search`, `upload`,
  `data_entry`, `my_samples`, `datasets`, `access_requests`,
  `notifications`, `pipelines`. Admin pages (`lab_director`,
  `platform_admin`, `archive_requests`, `billing`) intentionally
  deferred to Month 3.
- Landing page renders at `http://localhost:8501`. Sidebar shows all 9
  pages. Mock auth works end-to-end — `current_user()` returns the
  seeded admin user with lab memberships.
- **Unknown:** individual page render behavior. Phase 21 UI-B through
  UI-F walks every page to find out.

---

## Phase 0 — Pre-Session Fixes (COMPLETE)

These were the blocking bugs resolved before any router session began.

- [x] **P0-1 through P0-16** — all completed. Summary: conftest Alembic
  migrations, auth settings isolation, JWT refresh endpoint,
  audit/notification transaction cohesion, execute_query conn param,
  JWT type claim validation, /health 503 on DB down, APScheduler job
  intervals, tier-specific validator BASE_REQUIRED, Isolate source
  type, validator docstring v4.1→v4.4, configurable CORS origins.

## Phase 1 — Session A: organizations router (COMPLETE)

- [x] A-1 through A-7 — POST / GET / GET{id} / PATCH / DELETE, tests,
  commit.

## Phase 2 — Session B: labs + lab_membership router (COMPLETE)

- [x] B-1 through B-11 — CRUD on labs, full membership lifecycle
  (add / change role / remove), tests, commit.

## Phase 3 — Session C: users router (COMPLETE)

- [x] C-1 through C-7 — `/me`, CRUD, self-update guardrails, Platform
  Admin override, tests, commit.

## Phase 4 — Session D: domain_whitelist router (COMPLETE)

- [x] D-1 through D-5 — domain whitelist CRUD + tests.

## Phase 5 — Session E: sequencing_labs router (COMPLETE)

- [x] E-1 through E-8 — CRUD + assignments to labs + tests.

## Phase 6 — Session F: tokens router (COMPLETE)

- [x] F-1 through F-6 — API token CRUD with bcrypt hashing, project
  name filter, tests.

## Phase 7 — Session G: ingest router (COMPLETE)

- [x] G-1 through G-5 — upload, csv, globus endpoints. Full ingest
  pipeline: validate → epiweek → scrub_status → surveillance_relevant
  → quality_status → stage files → sample + sample_files writes in one
  transaction → audit.

## Phase 8 — Session H: samples router (COMPLETE)

- [x] H-1 through H-8 — list with full filter surface and `select_all`,
  get, update (with locked-field protection), archive, files, download
  with presigned URLs.

## Phase 9 — Month 1 Stretch Goals

- [x] S-1: projects router — full, with `?name=` filter for CLI
- [x] S-2: dataharmonizer router — full, 94% coverage
- [ ] S-3: Full test suite regression check + merge development → main
  - `uv run pytest` all passing, coverage ≥ 60%
  - Currently only blocked by developer choosing to tag and merge;
    Month 1 itself is feature-complete.

## Phase 11 — Session I: jackpot-nf plugin + result registration (COMPLETE)

- [x] I-1 through I-7 — jackpot-nf repo created, register_client,
  Pydantic schemas, `POST /api/v1/pipelines/{run_id}/results/{result_type}`
  endpoint, hAMRonization normalizer, tests.

## Phase 12 — Session J: Viral pipeline parsers (COMPLETE)

- [x] J-1 through J-6 — Cecret (pangolin, nextclade, freyja, consensus),
  viralrecon (consensus, pangolin, nextclade, variants, wastewater),
  walkercreek (irma, consensus). 79/79 tests passing.

## Phase 13 — Session K: Bacterial isolate parsers (COMPLETE)

- [x] K-1 through K-6 — bactopia (amr, mlst, assembly, annotation),
  Grandeur (amr, mlst, kraken2, blast), mycosnp-nf (snippy, tree,
  typing), tb-profiler (lineage, drug_resistance). Tests + commit.

## Phase 14 — Session L: Metagenomic parsers (COMPLETE)

- [x] L-1 through L-4 — nf-core/mag (checkm2, gtdbtk, bin_registry),
  nf-core/taxprofiler (kraken2, bracken, diamond). Tests + commit.

## Phase 15 — Session M: pathogensurveillance + shared parsers (COMPLETE)

- [x] M-1 through M-5 — pathogensurveillance parser (v1.1.0 pinned),
  shared AMR normalization validator, parser version matrix, end-to-end
  integration test framework.

## Phase 16 — Session N: pipelines router (COMPLETE)

- [x] N-1 through N-9 — launch with compatibility check, events
  weblog receiver, monitoring (run detail, tasks, events), resume for
  FAILED runs, BYOP registration skeleton, pipeline promotion workflow.

## Phase 17 — Session O: sample_access router (COMPLETE)

- [x] O-1 through O-8 — access request CRUD, approve/deny workflow,
  `can_access_sample()` integration with grants, background expiry job.

## Phase 18 — Session P: Streamlit researcher pages (COMPLETE)

- [x] P-1 through P-11 — all 9 researcher pages implemented in
  `jackpot-backend/frontend/pages/`: dashboard, search, upload,
  data_entry, my_samples, datasets, access_requests, notifications,
  pipelines. Plus smoke tests for page imports.

- [x] **UI plumbing verified (early 2026-04-19):**
  - `frontend/app.py` exists and renders
  - `frontend/lib/session.py` + `frontend/lib/api.py` wire mock auth
  - `frontend/components/` and `frontend/lib/` packages present
  - Docker Compose `ui` service works after fixes in Phase 20
    UI-plumbing block
  - Landing page shows "Signed in as Glen Otero" with the seeded
    platform admin user
  - Sidebar lists all 9 pages

---

## Phase 19 — Session Q: GCP staging environment (MOSTLY COMPLETE)

- [x] **Q-1: jackpot-iac Terraform for staging** — network, Cloud SQL,
  GKE (3 node pools), 7 GCS buckets, Artifact Registry, IAM (3 GSAs +
  Workload Identity bindings). Commit `e15f40e`.
- [x] **Q-2: Secret Manager entries** — `SECRET_KEY`, `DATABASE_URL`,
  `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`,
  `NCBI_API_KEY`. Commit `6131563`.
- [x] **Q-3: GitHub Actions deployment pipeline** — WIF → build → push
  → helm upgrade (migrations as pre-upgrade hook). Commit `ab755ca`.
  Session 5 added: split checkout, PAT `insteadOf` submodule auth,
  in-cluster port-forward smoke test.
- [x] **Q-4: Deploy jackpot-backend to staging** — deployed Session 5,
  API live, `/health` returns `{"status":"ok","database":"connected"}`,
  Alembic head at `c536de6329e0`, 2/2 pods Ready.
- [ ] **Q-5: End-to-end pipeline test on staging** — Cecret (or
  viralrecon) full stack. **Blocked on:** P3.1 (test_batch.nf minimal
  harness) + UI-B/C for driving the flow. See Phase 24.
- [x] **Q-6: Staging smoke test suite** — `scripts/staging_smoke_test.sh`
  exists, runs in CI, currently uses `kubectl port-forward` (tactical
  Session 5 fix).
- [x] **Q-7: Document staging access** — `docs/staging_access.md`
  exists in `jackpot-iac/docs/`. Updated Session 5 with bootstrap Job
  YAML, troubleshooting runbook, cost controls.
- [ ] **Q-8: Commit and tag `month-2-complete`** — blocked on Q-5 and
  the permanent fixes in Phase 20.

---

## Phase 20 — Session 5 Debt

Tactical fixes from the first staging deploy + Streamlit UI debugging
are in place, but the permanent fixes aren't. These land the cleanup
before a second environment (staging-clone, production) is attempted,
and before any teammate tries to run the stack locally.

### UI-plumbing — DONE (2026-04-19 early AM)

Completed inline during Streamlit debug session. Recorded here for the
next developer who might otherwise re-encounter the same six bugs:

- [x] **Dockerfile.ui layout fix** — `COPY frontend/ .` (flattens)
      replaced with `COPY frontend/ ./frontend/` (preserves package);
      `CMD` path updated to `frontend/app.py`.
- [x] **docker-compose.yml mount fix** — `./frontend:/app` (overrode
      image layout) replaced with `./frontend:/app/frontend`; schema
      mount moved to `/app/schema`.
- [x] **docker-compose.yml command override removed** — explicit
      `command:` directive was still pointing at the old flattened
      `app.py` path; removed so image CMD takes over.
- [x] **PYTHONPATH=/app added to ui service env** — Streamlit runs
      with `sys.path[0]` set to `/app/frontend/` so the `frontend`
      package couldn't resolve its own absolute imports without `/app`
      also on the path.
- [x] **API_BASE_URL read by ApiClient** — `frontend/lib/api.py` now
      reads `API_BASE_URL` as a fallback after `JACKPOT_API_URL`
      (compose was setting the former, client only read the latter).
- [x] **MOCK_USER_EMAIL already set on api service** — confirmed line
      78 of `docker-compose.yml`. Both ui and api containers get the
      env var; the X-Mock-User-Email header round-trip works.

### Q-9: Alembic baseline migration ✅ CLOSED

Baseline revision: **`5adf11b77c19`** (`baseline schema from init.sql`).

- [x] Added Alembic revision `5adf11b77c19` containing the full v4.1
      DDL from the former `db/init.sql` as a single `op.execute()`.
- [x] Chained `a7fd1fcccb77` after it
      (`down_revision = "5adf11b77c19"`).
- [x] Set `down_revision = None` on the new baseline.
- [x] Verified `alembic upgrade head` against a fresh empty DB:
      `docker compose down -v && docker compose up -d` → api container
      runs `alembic upgrade head` via `backend/entrypoint.sh` →
      `/health` returns `{"status":"ok","database":"connected"}`.
      Round-trip `downgrade base` + `upgrade head` rebuilds cleanly.
- [x] Renamed `db/init.sql` → `db/SCHEMA.sql` (read-only reference
      snapshot with header). Removed Postgres entrypoint mount from
      `docker-compose.yml`.
- [x] Added Critical Rule 52 to `docs/CLAUDE.md`. Amended Rule 44 to
      drop the bootstrap-Job/Q-9-pending caveats.
- [x] Documented cut-over path in `docs/staging_access.md §6`:
      one-time `kubectl exec ... alembic stamp 5adf11b77c19` for
      environments deployed pre-Q-9.
- [x] `tests/conftest.py` no longer loads init.sql — runs only
      `alembic upgrade head`, exercising the same path as production.
- [x] 549 tests passing, 87.56% coverage (above ≥477 / ≥86.99% baseline).

### Q-10: cors_origins validator in `backend/config.py` ✅ CLOSED

Validator + 11 unit tests in `tests/test_config.py`. Pydantic-settings
bumped to `>=2.3.0,<3` (resolved 2.14.0) so `NoDecode` is importable.

- [x] Applied `Annotated[list[str], NoDecode]` + `field_validator(mode="before")`
      to `cors_origins` in `backend/config.py`. Accepts JSON arrays,
      comma-separated strings, empty strings, `None`, and real lists;
      raises `ValueError` with a helpful message on malformed JSON.
- [x] Bumped `pydantic-settings>=2.3.0,<3` in `pyproject.toml`
      (was `==2.2.1`). `uv lock` regenerated.
- [x] Reverted `jackpot-iac/helm/jackpot-api/values-staging.yaml` line
      24 CORS_ORIGINS to plain comma-separated form.
- [x] Added Critical Rule 53 to `docs/CLAUDE.md`. Amended Rule 45 to
      drop the cors-specific Q-10 backlog caveat (mirrors Q-9's
      Rule 44 ↔ Rule 52 split).
- [x] 560 tests passing, 87.62% coverage (was 549/87.56% baseline —
      +11 new config tests, no regressions).
- [x] Compose smoke: api boots cleanly with both CSV
      (`http://localhost:8501,http://localhost:4200`) and JSON-array
      (`'["http://localhost:8501","http://localhost:4200"]'`) forms;
      `/health` returns `{"status":"ok","database":"connected"}`.

### Q-11: Remove `sys.path` hack from `pipelines.py`

- [ ] Option A (preferred): move `nf/shared/schemas/__init__.py`
      content into `backend/pipeline_schemas.py`. Change
      `from shared.schemas import RESULT_SCHEMAS` →
      `from backend.pipeline_schemas import RESULT_SCHEMAS`. Remove
      `sys.path.insert` from `pipelines.py`.
- [ ] Alternative Option B: vendor `nf/shared/` into
      `backend/vendored/nf_shared/` if `nf/shared/` has ongoing
      independent development.
- [ ] Verify: `docker run --rm jackpot-api:local-test /opt/venv/bin/python -c "from backend.main import app"`
      succeeds *without* `COPY nf/` in the Dockerfile.
- [ ] Can then remove `COPY nf/ ./nf/` from `Dockerfile.api`.

### Q-12: Terraform-owned DATABASE_URL Secret

- [ ] Wire `terraform/modules/secrets/` to construct `DATABASE_URL`
      from Cloud SQL module outputs (`private_ip`, port, db name) +
      password Secret reference.
- [ ] Eliminates the hand-populated Secret that caused the `/jackpot`
      vs `/jackpot_db` drift in Session 5.

### Q-13: Rotate staging DB password

- [ ] Run the rotation (password visible in chat during Session 5
      debugging — staging only, low blast radius):

```bash
NEW_PASS=$(openssl rand -base64 24 | tr -d '=+/')
gcloud sql users set-password jackpot \
    --instance=jackpot-staging-db \
    --password="$NEW_PASS" \
    --project=gotero3-acdp-488517
gcloud secrets versions add jackpot-staging-database-url \
    --project=gotero3-acdp-488517 \
    --data-file=- \
    <<< "postgresql://jackpot:${NEW_PASS}@10.188.230.3:5432/jackpot_db"
cd ~/ASU/jackpot/jackpot-iac
gh workflow run deploy-staging.yml --ref staging
```

### Q-14: Public Ingress + DNS + managed cert for staging

- [ ] Terraform additions: GKE Ingress (or `LoadBalancer` Service),
      Cloud DNS record, managed SSL cert.
- [ ] Update `JACKPOT_API_URL`, `CORS_ORIGINS`,
      `GOOGLE_OAUTH_REDIRECT_URL` in `values-staging.yaml` to real URL.
- [ ] Flip `scripts/staging_smoke_test.sh` back to hitting real URL
      instead of `localhost:8080` port-forward.
- [ ] **Unblocks:** end-to-end Google OAuth testing, Q-5 (staging E2E
      pipeline test with real weblog callbacks).

### Q-15: Helm upgrade hardening

- [ ] Option A: add `--atomic` to the workflow's `helm upgrade` —
      auto-rolls-back on failure, keeps release clean, but loses debug
      evidence on timeout.
- [ ] Option B: add a pre-upgrade step that detects `pending-*` status
      and rolls back automatically.
- [ ] Manual recovery command if stuck:
      `helm -n jackpot rollback jackpot-api <last-good-rev>`

### Q-16: Bump GitHub Actions to Node 24

- [ ] Either set `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` at the
      workflow `env:` level, or upgrade actions when `@v5` versions
      are available.
- [ ] Every workflow run currently warns Node 20 is deprecated as of
      2026-09-16.

### Q-17: Update CLAUDE.md with Session 5 lessons

- [ ] Add Critical Rules 42-47 from `claude_md_rules_addendum.md`:
  - Rule 42: Alembic must reach head from empty DB
  - Rule 43: list-typed settings need multi-form validators
  - Rule 44: `nf/` submodule must be importable or wrapped
  - Rule 45: Never paste across secret types (prefix check)
  - Rule 46: `yaml.safe_load` is not a GitHub Actions validator
  - Rule 47: Helm `--wait` timeouts wedge at `pending-*`

### Q-18: Fix misleading "API unreachable" banner in `frontend/app.py`

- [ ] `current_user()` in `frontend/lib/session.py` returns `None` for
      both auth failures and network failures. The landing page in
      `frontend/app.py` shows "API unreachable" for both cases. Fix
      the distinction:
  - Option A: change `ApiClient` to raise different exceptions for
    network vs. auth; let `app.py` render different banners.
  - Option B: probe `/health` first in `app.py`; show "API unreachable"
    only if that fails, otherwise show "Not signed in."
- [ ] **Estimated effort:** 15 minutes with fresh eyes.

---

## Phase 21 — UI Page Triage

The Streamlit shell is green. What remains is walking every page to
see which render cleanly against the running backend vs. which break.
Do these in order — each builds on earlier ones.

### UI-A: Landing page smoke (COMPLETE)

- [x] Hit http://localhost:8501 → landing page renders
- [x] Sidebar shows all 9 pages
- [x] Auth probe via `current_user()` returns Glen Otero (platform
      admin, Otero Lab director)

### UI-B: Upload page

- [ ] Navigate to Upload.
- [ ] Verify the form renders — all BaseSample fields present,
      sequencing lab dropdown populated from
      `GET /api/v1/sequencing-labs/`, project dropdown populated
      from `GET /api/v1/projects/`.
- [ ] Upload a test FASTQ + full metadata (HumanSample, clinical
      sector, organism SARS-CoV-2, all Tier 3 fields).
- [ ] Submit → expect success response with `sample_id` and computed
      `quality_status`.
- [ ] If broken, triage and log the failure in `docs/review_log.md`.

### UI-C: Search page

- [ ] Filter by the sample uploaded in UI-B (organism, collection date).
- [ ] Expected: the sample appears in the result list with tier badge
      and quality_status.
- [ ] Verify bulk-select mechanic works.

### UI-D: Sample detail page

- [ ] Click into the sample from search results.
- [ ] Verify all metadata visible, file list shows the uploaded file,
      download link generates a presigned URL.
- [ ] PATCH a metadata field → expect `quality_status` recomputation.
- [ ] PATCH a locked field (e.g. `quality_status`) → expect rejection.

### UI-E: Dashboard page

- [ ] Recent samples list should include the UI-B upload.
- [ ] Quick actions (Upload / Search / New Dataset) navigate correctly.

### UI-F: My Samples, Access Requests, Notifications, Datasets, Pipelines

- [ ] Click each in turn. Log which render cleanly vs. which show
      error banners vs. which are "Month 3 placeholder" by design.
- [ ] Build a per-page bug list before scheduling fixes. Some pages
      may call endpoints that don't exist yet (e.g. `notifications`
      router is deferred to Month 3).

### UI-G: End-of-Phase-21 commit

- [ ] `gac "feat(ui): Phase 21 page triage complete — see review_log.md"`
- [ ] Update `docs/review_log.md` with the per-page status.

---

## Phase 22 — Periodic Review Checkpoint

After every ~20 completed tasks, pause and run this review:

```
Review spec.md and the current implementation for gaps.
Check: are all Critical Rules from CLAUDE.md being followed?
Check: has coverage stayed above 60%?
Check: are there any TODO comments or placeholder code left in place?
Log findings to docs/review_log.md and resolve before continuing.
```

- [ ] **SEC-1: Tighten CORS methods/headers in `backend/main.py`** —
      replace `allow_methods=["*"]` with
      `["GET","POST","PATCH","DELETE","OPTIONS"]` and restrict
      `allow_headers` to the actually needed set.
- [ ] **SEC-2: Add rate limiting** — `slowapi` on auth endpoints
      (`/api/v1/auth/login`, `/api/v1/auth/callback`) and ingest
      endpoints before GCP production deployment.
- [ ] **DEPLOY-1: Document staging→production gate** — add a required
      manual approval step in `.github/workflows/` before production
      deploy.
- [ ] **DEPLOY-2: Test backup restore** — run a full PITR restore drill
      to a separate Cloud SQL instance before going live with real data.

---

## Phase 23 — Minimal Nextflow Test Pipeline

### P3.1 — `scripts/test_batch.nf`

- [ ] Build a 20-line Nextflow pipeline: echo a string, write a tiny
      result file, exit.
- [ ] Configure with `-weblog http://localhost:8000/api/v1/pipelines/events`
      for local dev, the public URL (from Q-14) for staging.
- [ ] Run against local stack: verify the pipelines router receives
      events, registers a run, transitions state correctly.
- [ ] Smallest-possible exerciser of the weblog receiver and pipeline
      state machine. Worth having before viralrecon or any nf-core
      pipeline is attempted.

---

## Phase 24 — End-to-end Pipeline Test on Staging (closes Q-5)

**Depends on:** Q-9 (Alembic baseline), Q-14 (public URL), P3.1 (test
harness), UI-B (Upload page working), UI-F pipelines-page entry.

- [ ] Pick viralrecon as the first real pipeline test (better-documented
      than Cecret as an nf-core pipeline).
- [ ] Upload a test SARS-CoV-2 sample via the UI.
- [ ] Launch viralrecon via the pipelines page.
- [ ] Verify the full chain: sample uploaded → staged → scrubbed →
      pipeline launched → events received → results registered →
      `pangolin_results` + `nextclade_results` tables populated →
      MultiQC report viewable in the UI.
- [ ] Document the full run in `docs/staging_e2e_test.md`.
- [ ] Tag: `git tag -a month-2-complete -m "Month 2 complete: pipelines + parsers + sample_access + Streamlit + GCP staging + E2E verified"`

---

## Phase 25 — Month 3 Stretch Goals (Tracked, Not Scheduled)

- [ ] Streamlit admin pages: `lab_director.py`, `platform_admin.py`,
      `archive_requests.py`, `billing.py`
- [ ] JupyterHub workspace with all three profiles (Analyst,
      Bioinformatician, Developer)
- [ ] BYOP full wire-up: fetch `nextflow_schema.json` from registered
      repo, validate, enable launching
- [ ] GCP production deployment
- [ ] `ncbi_submissions` router (TOSTADAS integration)
- [ ] `datasets` router (table exists, router stub)
- [ ] `archive_requests` router
- [ ] `saved_searches` router
- [ ] `notifications` router (full — currently placeholder in UI)
- [ ] Remaining parsers if any pipelines were deferred
- [ ] External database search (`/api/v1/external-search/` — NCBI, ENA,
      GISAID proxy)
- [ ] Re-enable detect-secrets in pre-commit
- [ ] Playwright end-to-end UI tests
- [ ] US-states controlled vocabulary for `collection_location_state`
- [ ] Retire `jackpot-frontend` repo (vestigial stub — real UI lives
      in `jackpot-backend/frontend/`)

---

## Done in Session 5 (2026-04-17 evening — 2026-04-19 early AM)

**First staging deploy to GKE** — 10 root causes diagnosed and fixed:

- `jackpot-nf` pushed to GitHub (was only on local Mac).
- `.gitmodules` URL fixed (filesystem path → GitHub URL).
- `submodules: recursive` + PAT `insteadOf` injection in workflow.
- `Dockerfile.api` updated to `COPY nf/`.
- `cors_origins` ConfigMap format tactical fix (JSON-array string).
- `DATABASE_URL` Secret corrected (`/jackpot` → `/jackpot_db`).
- `CROSS_REPO_PAT` restored (had been overwritten with a Google OAuth
  client secret).
- Helm release unstuck from `pending-upgrade` via manual rollback.
- Smoke test rewired to use `kubectl port-forward`.
- Bootstrap Job written for fresh-DB init.sql + alembic stamp flow.

**Streamlit UI local** — 6 chained bugs diagnosed and fixed:

- `Dockerfile.ui` `COPY frontend/ .` was flattening the layout.
- `docker-compose.yml` `./frontend:/app` mount was overriding the image
  layout with the flattened form.
- `docker-compose.yml` `command:` directive was overriding the image
  CMD with the old `app.py` path.
- Streamlit's `sys.path[0]` is the script dir, so `/app/frontend/` was
  on the path but not `/app/` — `PYTHONPATH=/app` fixed it.
- `ApiClient` in `frontend/lib/api.py` was reading `JACKPOT_API_URL`
  but compose was setting `API_BASE_URL` — added as fallback.
- `MOCK_USER_EMAIL` was already on the api service (line 78 of
  compose) but a first-pass diagnostic missed it — resulted in a
  momentary duplicate-key error after my patch attempt.

All permanent fixes for these are tracked in Phase 20 Q-9 through Q-18.

---

## Notes for the next session

**Fresh morning, 5 minutes first:** open http://localhost:8501 and
confirm the landing page says "Signed in as Glen Otero" (should be
correct given last night's fixes). Then walk Phase 21 UI-B through
UI-G to build the per-page bug list.

**Before any GCP deploy to a new environment:** run
`local_test_checklist.md` top to bottom. Specifically Part 1 step 5
(Alembic from empty DB) — if that fails, Q-9 hasn't landed and you
need the bootstrap Job workaround.

**For the Month 1 human-testable demo:** Phase 21 IS the demo. Once
UI-B through UI-D are green, you can show "upload a sample → find it
in search → view its details" in a browser. That's the full Month 1
scope.

**For production readiness:** Q-9 (Alembic baseline) is the most
important unblock. It makes every fresh deploy honest and eliminates
the bootstrap Job dependency.

**For closing Month 2:** Q-5 (staging E2E pipeline test) gates the
`month-2-complete` tag. Phases 20, 21, 23, and 24 are the ordered
critical path to get there.
