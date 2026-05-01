# JACKPOT — To-Do List

**Last updated:** 2026-05-01 (post-Phase-22 review checkpoint)
**Baseline:** 615 backend tests passing, 1 skipped, **84.09% coverage** (CI threshold restored to 80%, was wrongly held at 35% for several phases). The "39% coverage post-P0d" we carried through Phase 22 was a pytest-cov misconfiguration — the `[tool.coverage.run].omit` block was never reaching the report-time matcher because pytest-cov requires explicit `--cov-config=pyproject.toml`, which addopts didn't supply. Fix landed post-Phase-22; see `docs/learnings.md` "Coverage measurement bug — what we got wrong" entry. Real coverage gaps remaining (action item 15): `harmonizer.py` 0%, `gisaid.py` 43%, `templates.py` 53%, `dlp_scanner.py` 71%. Session S complete, Session 5 staging deploy on top, P0d done + validated, Phase 22 review checkpoint complete (including three ultrareview passes).
**Active sprint:** P0e (jackpot init CLI). Phase 22 COMPLETE — see Session 13 in jackpot_session_summary_and_backlog.md, the Phase 22 entry in learnings.md, and `docs/review_log.md` for findings + 19-item action list.

**Project context as of 2026-04-28:** JACKPOT pivoted to an independent project under `Midnight-Oil-Innovation/jackpot` (no longer ADHS/ASU-coupled, no longer the APGAP successor). License flipped from Apache 2.0 to **AGPL-3.0**. New multi-deployment-target architecture covers 7 install scenarios (A laptop, B single-org cloud, C multi-lab agency, D hosted SaaS, E federation member, F CI test, **T Tribal-sovereignty deployment**). Cleanup A through J COMPLETE → **P0d COMPLETE and VALIDATED (2026-04-30 → 2026-05-01)** → P0e (jackpot init CLI, next) → **P0f (BYOP infrastructure)** → P0b/c (multi-tenancy schema + middleware, **gated on Phase 24.5 sovereignty design** AND **must include BYOP + eukaryotic schema additions**) → P1–P5. See `jackpot_pathoplexus_loculus_overview.md`, `jackpot_cdc_dmi_stlt_overview.md`, and `jackpot_byop_and_eukaryotic_design.md` for the analyses driving Phases 26, 27, P0f, and 28.

**Priority shift (2026-04-28):** With CARE Principles, STLT alignment, and DMI/North Star analysis in scope, several items that were "Year 2 stretch" deserve to land *during* P0d (governance docs, deploy guide reorganization, layer-cake framing) because P0d is already touching exactly those files. The architectural design for delete-on-request (B-CARE-3) is now **Phase 24.5** — must lock in *before* P0b schema work to avoid retrofit.

**Phasing decision for BYOP and eukaryotic pipelines (2026-04-29):** The 25 backlog items from `jackpot_byop_and_eukaryotic_design.md` are NOT homogeneously deferrable to a single late phase. They split three ways: (1) **schema items move to P0b** alongside the existing Schema v5.0 work — otherwise we migrate twice. The 4 schema items (B-BYOP-9, B-EUK-1, B-EUK-2, B-EUK-3) are now bundled into Phase 24.5's design-lockdown deliverables. (2) **BYOP infrastructure (10 items) gets a new P0f phase** between P0e and P0b/c, because eukaryotic pipelines need BYOP to land first, and BYOP can't wait for P1. (3) **Default eukaryotic pipelines + parsers + dashboards (11 items) stay in Phase 28** but are internally tier-prioritized: Tier 1 (Plasmodium, Crypto/Giardia) ships first.

Phase 21 UI triage stays where it is — Session 5 debt, ship-blocker, not displaceable.

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

## Out-of-band housekeeping

- **2026-04-24** — Renamed JACKPOT organisation "host academic operator" → "Example Org"
  via migration `c1bd67369a7c`. Same migration renames the
  `sequencing_labs.organization` denormalised text and the
  `domain_whitelist` row. Seed snapshot updated in `db/SCHEMA.sql`.
  Pattern documented in `docs/learnings.md`.

- **2026-04-26 to 2026-04-28** — Cleanup A through J: removed institutional
  references (ADHS/ASU/Linux Prophet/Otero/Sonora Quest/Maricopa/Phoenix/etc.)
  from the codebase to align with the operator-agnostic principle (Critical
  Rule 55). Production code now knows nothing about any specific operator;
  only the eventual `jackpot init` bootstrap step learns operator names at
  install time.

  | Letter | Scope                              | Commit    | Notes |
  |--------|------------------------------------|-----------|-------|
  | A      | docs cleanup                        | `68e3565` | jackpot-backend |
  | B      | schema rename `adhs_medsis_id` → `external_case_id` | `667aaaf` | + submodule `8416e28` |
  | C      | HTML course content                 | `b804e76` | + submodule `684a0c4` |
  | D      | test fixture data                   | `d51e39d` | jackpot-backend |
  | E      | straggler test fixtures             | `c29fa42` | jackpot-backend |
  | F      | seed scripts genericized            | `771cbc8` | + new migration `00b4bd99ddee` |
  | G      | submodule schema-update scripts     | (no-op)   | already clean from prior work |
  | H      | misc files + 2 deletions            | `83f9f28` | deleted `CLAUDE_addition.md`, `rewrite_validator.py` |
  | I      | nf/ test fixtures (AZ-* → EX-*)     | `a9a2a94` | + submodule `f11e719` |
  | J      | Streamlit frontend                  | (no-op)   | grep matches were all 'banner' false positives |

  Net result: the codebase is operator-agnostic. The next phase, P0d, is
  the monorepo migration to `Midnight-Oil-Innovation/jackpot`.

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
  - Landing page shows "Signed in as the maintainer" with the seeded
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

### Q-11: Remove `sys.path` hack from `pipelines.py` ✅ CLOSED

Vendored `nf/shared/schemas/` → `backend/pipeline_schemas/` (10-file
package, identical layout — preserves diff-ability with the nf side).

- [x] Picked Option B (layout-preserving vendor) — `backend/pipeline_schemas/`
      is a package mirroring `nf/shared/schemas/` file-for-file, not a
      flattened single module. Easier upstream-diff. Provenance noted
      in the package `__init__.py` docstring.
- [x] `backend/routers/pipelines.py` now does
      `from backend.pipeline_schemas import RESULT_SCHEMAS`. Deleted
      the `_NF_ROOT` block, the `sys.path.insert`, and the late
      `from shared.schemas import …`. `import sys` removed (no other
      usage); `Path` retained (used elsewhere).
- [x] `Dockerfile.api` no longer has `COPY nf/`. New `.dockerignore`
      at repo root excludes `nf/` (and other build-context bloat) so
      the API image is smaller and won't accidentally regress.
- [x] Critical Rule 54 added; Rule 46 amended to drop the Q-11 caveat
      and reflect the new boundary (mirrors Q-9/Q-10 split pattern).
- [x] Verified `from backend.routers import pipelines` succeeds with
      `nf/` absent from disk (mv nf nf.bak simulation).
- [x] Verified docker build succeeds with `nf/` excluded; image's
      `/app/` no longer contains `nf/`; `from backend.pipeline_schemas
      import RESULT_SCHEMAS` works inside the container (9 schemas).
- [x] `docker compose down && up -d --build` brings stack up clean;
      `/health` → `{"status":"ok","database":"connected"}`.
- [x] `jackpot-nf` submodule unchanged (SHA `a45fb13`).
- [x] 560 tests passing, 88.34% coverage (was 560/87.62% — coverage
      ticked up because the vendored schemas count toward the
      measured surface).

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
    --project=jackpot-staging-project
gcloud secrets versions add jackpot-staging-database-url \
    --project=jackpot-staging-project \
    --data-file=- \
    <<< "postgresql://jackpot:${NEW_PASS}@10.188.230.3:5432/jackpot_db"
cd ~/jackpot/jackpot-iac
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
- [x] Auth probe via `current_user()` returns the maintainer (platform
      admin, Example Lab director)

### UI-B: Upload page ✅ CONTRACT VERIFIED (2026-04-24) — browser walk still owed

Reframed to backend-contract + page-code review (no headless-browser
tooling in session). Detailed report: `docs/learnings.md` "UI-B —
Upload page triage". Two real backend bugs found and fixed at root.

- [x] **Backend ingest contract**: happy + 4 error scenarios verified
      via curl against the live local stack. Envelope shape matches
      `frontend/lib/api.py` expectations.
- [x] **Bug fix 1 — `validate_file_type()` was never called on
      upload.** Now invoked in `backend/routers/ingest.py:upload()`
      via tempfile, with `FileDetectorError` → 400. CSV-named-fasta
      and gzipped-CSV-named-fastq.gz now rejected with human messages.
      Regression: `test_upload_rejects_csv_renamed_to_fasta`,
      `test_upload_rejects_gzipped_csv_renamed_to_fastq_gz`.
- [x] **Bug fix 2 — HTTPException-based errors bypassed the JACKPOT
      envelope.** Added global `HTTPException` and
      `RequestValidationError` handlers in `backend/main.py` that
      normalise every error to `{"success": false, "error": {...}}`.
      Also fixed `dataharmonizer.py` raw `JSONResponse({"detail": ...})`
      → `responses.error()`. Regression:
      `test_validation_error_uses_jackpot_envelope`,
      `test_string_detail_http_exception_uses_envelope`.
- [x] **Page-code review**: `upload.py` + `api.py` confirmed to parse
      the new envelope correctly. Every error path → `ApiError.message`
      → `st.error("Upload failed: ...")`. No paths produce raw JSON
      dumps post-fix.
- [x] **Seed rename**: "Example Lab" → "Example Lab" via Alembic
      migration `e5315db18d40`. `db/SCHEMA.sql` snapshot updated.
- [x] **564 tests passing, 88.22% coverage** (was 560/87.62%; +4
      regression tests, no skips).
- [ ] **Browser walkthrough still owed** — needs a human at the
      keyboard to confirm rendering. Steps to click through (matches
      contract walkthrough): valid upload → error scenarios 7/8/9.
      Step 6 (missing host_age) doesn't trigger as the task assumed
      — host_age is optional in the current validator; product-owner
      decision needed if it should be required for Human samples.
- [ ] **Recommend opening UI-B2** for missing form fields:
      sequencing-lab + project dropdowns, sector auto-derive, host
      species/age/sex, isolation source, organism autocomplete,
      year-only date tolerance UI. Current page is an MVP scaffold.

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

## Phase 21.5 — Interstitial During-P0d Quick Wins

**Status (2026-05-01):** all items below COMPLETE. Phase 21.5 docs landed during P0d execution (commit `2d340af docs(p0d): Phase 21.5 quick-wins — STLT guides, FHIR mapping, README, spec edits` plus `f46f7ee docs(p0d): governance/ directory — 8 charter + policy documents`).

**Why this phase existed:** P0d was already touching the docs tree, the repo structure, the README, and the directory layout. These items were pure-documentation or near-pure-documentation work that rode along naturally with the monorepo migration. Doing them as part of P0d was more efficient than scheduling them as separate phases — the alternative was reopening the same files later. None added engineering scope; they all added clarity / governance / grant-narrative quality.

The items below are kept for historical record with checkboxes marked. Order was rough effort ascending.

### B-DMI-3: "Single-entry-point" framing in spec.md

- [x] Add a short subsection to spec.md §1 (or §3 depending on where the ingest-paths description lives now) documenting JACKPOT's six ingest paths as "the single entry point for genomic data into a public health agency." (Landed in spec.md §1.1 in P0d.)
- [x] Effort: half a session, ~30 min of writing.

### B-STLT-2: Layer-cake diagram in spec.md

- [x] Add the layer-cake diagram from `jackpot_cdc_dmi_stlt_overview.md` §9.1 to spec.md. (Landed in spec.md §3.0 in P0d.)
- [x] Frame as "JACKPOT integrates with these systems; it does not replace them."
- [x] Effort: 1 session.

### B-GOV-1 + B-CARE-1: Governance directory with CARE Principles

Combined — same act of writing.

- [x] Create `governance/` directory at repo root with:
  - [x] `charter.md`
  - [x] `coi-policy.md`
  - [x] `jurisdiction-and-data-residency.md`
  - [x] `benefits-sharing-framework.md`
  - [x] `access-grievance-procedure.md`
  - [x] `platform-shutdown-data-portability-plan.md`
  - [x] `advisory-board.md`
  - [x] `care-principles-and-tribal-data-sovereignty.md`
- [x] Link from README.md and from spec.md.
- [x] Effort: 1 session of writing.

### B-CARE-2: Add Scenario T to spec.md scenarios list

- [x] Update spec.md §1 scenarios table from 6 entries to 7 — added **T (Tribal-sovereignty deployment)** in the §1 pivot blockquote.
- [x] Brief mention in CLAUDE.md project header. (Bumped from "6 install scenarios" to "7" with the T variant called out.)
- [x] Effort: half a session.

### B-DMI-1: FHIR-translatable data model documentation

- [x] Add `docs/fhir-mapping.md` documenting how JACKPOT's LinkML schema entities map to FHIR R5 resources. (Landed in P0d.)
- [x] Pure documentation; no implementation. Sets up `B-DMI-2` (actual FHIR ingest router) for Year 2.
- [x] Effort: 2 sessions of writing.

### B-STLT-1: Five STLT deploy guides under `docs/deploy/stlt/`

- [x] `state-health-department.md`
- [x] `territorial-health-agency.md`
- [x] `local-health-department.md`
- [x] `tribal-authority.md`
- [x] `tribal-epidemiology-center.md`

- [x] Effort: 5 sessions total — landed in P0d alongside the monorepo work.

### B-STLT-3: Funding-source map in deploy guides

- [x] Funding-source map from `jackpot_cdc_dmi_stlt_overview.md` §10 included in each STLT deploy guide.
- [x] Effort: rolled into B-STLT-1.

### Phase 21.5 success criterion

By the time P0d is otherwise complete:

- [x] `governance/` directory exists with all 8 markdown files
- [x] spec.md has Scenario T, layer-cake diagram, single-entry-point framing
- [x] `docs/deploy/stlt/` has all 5 STLT deploy guides
- [x] `docs/fhir-mapping.md` documents FHIR-translatable schema
- [x] CLAUDE.md mentions Scenario T in the project header
- [x] README.md links to governance/ directory

If any of these slip past P0d, that's fine — they're not gating. But if you're touching docs anyway during P0d, you should be touching these.

---

## Phase 21.6 — P0d.1 Post-Execution Cleanup (COMPLETE 2026-05-01)

Four structural follow-ups surfaced AFTER P0d's `p0d-complete` tag landed (commit `d32f40a`) but before the local dev stack actually ran. None were caught by P0d's own success criteria — those covered tests-pass and /ultrareview-clean and gh-archive-done, but didn't include "`docker compose up` brings the full stack up." Documented in detail in `learnings.md` ("P0d.1 — Post-execution cleanup" entry) and `jackpot_session_summary_and_backlog.md` Session 12.

Items, all complete:

- [x] **docker-compose.yml moved from `backend/` to monorepo root.** P0d's filter-repo carried it along with backend's other root-level files; relative paths broke in the new layout.
- [x] **Dockerfile.api and Dockerfile.ui rewritten for workspace-aware paths.** Now copy full uv workspace (root pyproject + all member directories) before `uv sync --frozen` so workspace resolution sees all member metadata.
- [x] **entrypoint.sh updated for new layout.** `cd /app/backend` before alembic (script_location=db/migrations), `cd /app` before uvicorn (backend.main:app import).
- [x] **Frontend canonicalization.** P0d's design kept canonical Streamlit at `backend/frontend/`; chat-side analysis incorrectly deleted it as a "stale shadow" (commit `5dd4806`). Recovery: filter-repo merge of archived gotero/jackpot-frontend brought in a half-finished uv-init stub (not useful); canonical files restored from `5dd4806^` and relocated to `frontend/` at monorepo root (more aligned with P0d's "each component at top level" intent than its actual `backend/frontend/` placement).
- [x] **`p0d-validated` tag added** at the commit where the stack genuinely runs end-to-end. `p0d-complete` kept at d32f40a for historical record.
- [x] **End-to-end smoke validated:** API healthy with all 17 alembic migrations applied, Streamlit on 8501 with 9 researcher pages, /health returns 200, 55 OpenAPI paths registered.

**Lessons folded back into learnings.md:**

- "Shadows that aren't shadows" — always `git ls-files <canonical-path>` before deleting apparent duplicates
- `backend/backend/` for uv workspaces is a standard layout, not an anti-pattern
- git filter-repo `--to-subdirectory-filter` wraps structure, doesn't flatten it
- Docker workspace pattern: copy full workspace (root pyproject + all members) before `uv sync`
- Compose file location matters in monorepo migrations — should be at root
- `gotero/jackpot-frontend` was a uv-init stub; the canonical streamlit lived inside `jackpot-backend`
- Future structural-migration phases should include "fresh-clone smoke test" in the success criteria, not just unit-test pass

---

## Phase 22 — Periodic Review Checkpoint (COMPLETE 2026-05-01)

Four-agent parallel review (Critical Rules, spec drift, coverage, TODOs)
followed by four sequential security/deploy commits. Findings synthesized
into `docs/review_log.md` (commit `8cbb993`) — that file is the canonical
output and carries the 19-item action list. Session 13 in
`jackpot_session_summary_and_backlog.md` and the Phase 22 entry in
`learnings.md` carry the play-by-play.

Named deliverables, all done:

- [x] **SEC-1: Tighten CORS methods/headers in `backend/backend/main.py`** —
      replaced `allow_methods=["*"]` / `allow_headers=["*"]` with explicit
      lists. Commit `cea62b6`.
- [x] **SEC-2: Add rate limiting** — `slowapi==0.1.9` on
      `/api/v1/auth/google/login` (5/min) and `/api/v1/ingest/{upload,csv,globus}`
      (60/min); env-tunable; envelope-conforming 429 handler; 3 new tests.
      Commit `a1ed4ab`.
- [x] **DEPLOY-1: Document staging→production gate** — new
      `.github/workflows/deploy-production.yml` declaring
      `environment: name: production` (Required Reviewers configured in
      GitHub UI, per-instance); workflow_dispatch only with mandatory
      `image_tag` + `reason` inputs; runbook at
      `docs/deploy/production-deploy.md`. Commit `f7680ea`.
- [x] **DEPLOY-2: PITR restore drill procedure** —
      `docs/deploy/pitr-restore-drill.md` with permissions, 6-step drill,
      explicit pass criteria, cleanup. README.md gained an "Operations
      runbooks" index. Live drill execution deferred to per-instance
      go-live (procedure-only here). Commit `6d35d20`.

Action items deferred to later phases (numbered per `docs/review_log.md`):

- **P0e (next sprint) absorbs:**
  - 5: ~~Fix coverage docs~~ — RESOLVED post-Phase-22 by commit `863fd18` once
    the real measurement bug was identified (the framing was wrong, not the docs).
  - 6: ~~Change `--cov=backend` → `--cov=backend/backend`~~ — RESOLVED post-Phase-22
    by commit `863fd18` with the correct fix (`--cov` bare + explicit
    `--cov-config=pyproject.toml` + `source_pkgs = ["backend"]`).
  - 7: Remove 9 stale CLI TODO comments
  - 8: Wire 3 SDK methods (`Sample.download_fastq`, `SamplesModule.search/get`)
    — backend endpoints already live
  - 9: Fix CLI Rule 55 (Glen-introduced) — `cli/jackpot/cli/upload.py:442,474,478,485`,
    `cli/jackpot/cli/main.py:25,47`, remove dead `ADHS_ORGANIZATION_NAME` from Helm values
  - 10: Stub routers return 501 instead of 200 (datasets, notifications,
    archive_requests, saved_searches, billing, dataset_access, ncbi_submissions)
  - 11: Fix 5 inherited Rule 55 CRITICAL violations (`backend/setup/write_files*.py`,
    baseline migration `5adf11b77c19`, `Chart.yaml`, `bootstrap_project.sh`) — these
    block any non-Glen operator deploys. Also fold in the 6 inherited Rule 55
    violations in `deploy/helm/jackpot-api/values-staging.yaml` (project ID, SA
    email, `JACKPOT_API_URL`, `CORS_ORIGINS`, dead `ADHS_ORGANIZATION_NAME`)
    flagged by UR pass-3 — `jackpot init` is the natural operator-bootstrap
    point for all of these.
  - 12: Implement `POST /api/v1/auth/refresh` OR remove the spec claim that it exists
  - 13: Resolve `backend/backend/storage/*.py` SPDX `Apache-2.0` vs project AGPL-3.0
    (needs human decision on whether storage module was adapted from Apache source)
  - 14: Update spec — drop the 60% coverage claim conflict (post-fix: real coverage
    is 84%, threshold restored to 80%); update §10 frontend path; close Q-10/Q-11;
    update §3 `STORAGE_BACKEND` to `STORAGE_ENDPOINT`
  - 15 (revised): Close the 4 real coverage gaps surfaced by the post-Phase-22
    measurement fix — `harmonizer.py` 0% (no tests), `routers/gisaid.py` 43%
    (~17 missing stmts in lines 57-116), `routers/templates.py` 53% (~9 missing
    stmts in lines 58-68, 97-104), `dlp_scanner.py` 71% (~34 missing stmts).
    Estimate: ~20 targeted tests, not the ~100 we previously planned. Lifts
    coverage from 84% → ~90% if all four gaps close.
  - 16: Implement `jackpot auth login` OAuth flow + backend `/auth/cli-login-url`
  - 18: Move Rule 18 violation in `ingest.py:288` (FASTA scrub_status logic) into
    `validator.py.ValidationResult` (lighter than expected — was tagged "Phase 24
    refactor" but fits naturally with P0e's CLI-touches-ingest work)

- **Month 3 / Phase 24+:**
  - 17: Build out 7 stub routers (datasets, notifications, archive_requests,
    saved_searches, billing, dataset_access, ncbi_submissions)

- **CI track (separate from feature phases):**
  - 19: Investigate testcontainers DinD reliability if integration tests are
    erroring silently in CI

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

## Phase 24.5 — Architectural Design Lockdown Before P0b Schema Work

**Why this phase exists:** P0b will land Schema v5.0 (instances/tenants/federated_peers). If P0b ships without thinking through these architectural decisions, the schema will need to be retrofitted later — meaning another migration, another data-handling review, another round of operator-deploy churn. Two distinct architectural gates must be locked in before P0b touches the schema:

1. **Sovereignty-compliant deletion** (CARE Principle "Authority to Control" requires withdrawn-consent data to actually leave the system, not just get soft-deleted)
2. **BYOP + eukaryotic schema additions** (the BYOP `byop_pipelines` table and `pipeline_results` FK additions, plus the eukaryotic OrganismNameEnum/samples-column/8-pipeline-result-table additions, all need to land *with* P0b — otherwise they require a second schema migration cycle)

This is a **design + schema-spec phase**. Implementation of the deletion logic lands in P0c. Implementation of BYOP infrastructure lands in P0f. Implementation of eukaryotic pipelines lands in Phase 28. But the schema decisions for all three land here.

### Design tasks

- [ ] **B-CARE-3-DESIGN**: Write `docs/architecture/sovereignty-compliant-deletion.md` covering:
  - [ ] `samples.deletion_status` enum: `ACTIVE | DELETION_REQUESTED | TOMBSTONED | VACUUMED`
  - [ ] State machine — who can request, who can approve, what triggers vacuum
  - [ ] Tombstone vs vacuum distinction — tombstone seals derivative rows, vacuum physically removes content
  - [ ] What gets vacuumed: file URIs in samples, GCS/MinIO objects, `pipeline_results.result_data` JSONB, cached intermediate artifacts, dataset memberships
  - [ ] What survives vacuum: audit log records of *what happened* (sample existed, was tombstoned at T1, vacuumed at T2 by user U), but NOT the deleted content itself
  - [ ] Vacuum cadence: configurable per operator policy; Scenario T defaults to 24 hours; other scenarios may default to 30 days
  - [ ] Derivative-analysis policy: cluster recompute (Scenario T default) vs cluster-with-asterisk (other scenarios) vs mark-stale-and-recompute-on-schedule
  - [ ] Already-published handling: pre-publish CARE confirmation checklist; "previously published" tag persists past vacuum; cannot retract from external party but system is honest about what's still in the wild
  - [ ] Federation propagation requirements (deferred to B-CARE-4 implementation): tombstone events pushed to peers, signed receipts, SLA, non-compliance flagging
  - [ ] Auth model: who can request deletion (sample submitter? lab director? platform admin?), who must approve (defaults: lab director for own-lab samples; platform admin for cross-lab; Tribal authority designee for Scenario T)
  - [ ] Edge cases: deletion during pipeline run (cancel pipeline?), deletion during pending submission to NCBI (block submission), deletion of sample that's part of an active outbreak investigation (require override)

- [ ] **Schema constraints from this design** that P0b must honor:
  - [ ] `samples.deletion_status` column with the 4-value enum
  - [ ] `samples.deletion_requested_at`, `deletion_requested_by_user_id`, `deletion_reason` columns
  - [ ] `samples.tombstoned_at`, `vacuumed_at` timestamp columns
  - [ ] `audit_log.event_type` enum extension: `sample_deletion_requested`, `sample_tombstoned`, `sample_vacuumed`
  - [ ] `pipeline_results` rows need a `tombstoned` boolean (cheaper than chasing every JSONB blob to mark it)
  - [ ] Foreign key from `pipeline_results.sample_id` should NOT cascade-delete on sample deletion (we want to keep tombstone records; the actual JSONB content is what gets vacuumed)

- [ ] **Implementation handoff to P0c**: docs/architecture/sovereignty-compliant-deletion.md is the spec for the implementation work in P0c. Tagged in P0c work as `B-CARE-3` (the actual implementation, after schema is in place).

- [ ] Review with anyone consulted on Tribal-authority deployment scenarios (NPAIHB outreach per B-CARE-6 should happen in parallel — their input on the design before locking is high-value).

### Schema additions for BYOP + eukaryotic pathogen support (must land with P0b)

These are not separate design work — the design exists in `jackpot_byop_and_eukaryotic_design.md`. They are **schema migration items** that must land in the same P0b migration cycle as the sovereignty additions and the existing v5.0 plan. Splitting them into a later migration creates double-migrate operator churn.

- [ ] **B-BYOP-9** Add `byop_pipelines` table per `jackpot_byop_and_eukaryotic_design.md` §7. Includes 27 columns covering manifest content, source type, lifecycle status, validation/sandbox logs, license, citation, cost estimate. Plus 4 new enums: `PipelineEngineEnum`, `PipelineSourceTypeEnum`, `PipelineStatusEnum`, `DataTypeEnum`. (1 session, P0b)

- [ ] **B-BYOP-9b** Add `byop_pipeline_id` and `byop_pipeline_version` foreign-key columns to existing `pipeline_results` table. (Half session, P0b — bundle with B-BYOP-9.)

- [ ] **B-EUK-1** Add ~25 OrganismNameEnum values for eukaryotic pathogens per `jackpot_byop_and_eukaryotic_design.md` §12.1: 6 *Plasmodium*, 6 *Leishmania*, 5 *Trypanosoma*, 5 *Schistosoma*, 7 STH, 3 filarial, 4 protozoa (*Crypto*/*Giardia*), 3 *Toxo*/*Entamoeba*. Plus new `ParasiteDevelopmentalStageEnum` and `SamplePreservationMethodEnum`. Plus new `samples` columns: `parasite_developmental_stage`, `sample_preservation_method`, `parasitemia_percent`, `multiplicity_of_infection`, `coinfection_organisms`. (1 session, P0b)

- [ ] **B-EUK-2** Add 8 new pipeline-result tables per `jackpot_byop_and_eukaryotic_design.md` §12.3: `plasmodium_drug_resistance_results`, `leishmania_typing_results`, `trypanosoma_typing_results`, `schistosoma_typing_results`, `helminth_drug_resistance_results`, `filarial_typing_results`, `cryptogiardia_typing_results`, `toxo_entamoeba_typing_results`. Plus supporting enums: `TcDTUEnum`, `GiardiaAssemblageEnum`, `ToxoClonalLineageEnum`, `EhVsEdEnum`, `WolbachiaStatusEnum`, `ResistanceCallEnum`. (1-2 sessions, P0b)

- [ ] **B-EUK-3** Update `validator.py` for eukaryotic-aware tier rules: new tier-2 fields (developmental stage, preservation method), new tier-3 fields (parasitemia, MOI, coinfection). Update `compute_surveillance_relevant()` to include eukaryotic pathogens by default. (1 session, P0b — bundle with B-EUK-1.)

### Phase 24.5 success criterion

- [ ] `docs/architecture/sovereignty-compliant-deletion.md` exists, is reviewable
- [ ] P0b schema design has accommodated the sovereignty columns + enum extensions (sovereignty block above)
- [ ] P0b schema design has accommodated `byop_pipelines` table, `pipeline_results` FK, eukaryotic OrganismNameEnum additions, eukaryotic samples columns, 8 eukaryotic pipeline-result tables, and supporting enums (BYOP/eukaryotic block above)
- [ ] Implementation tasks are queued: `B-CARE-3` for P0c (sovereignty deletion), `B-BYOP-1` through `B-BYOP-10` for P0f (BYOP infrastructure), `B-EUK-PLAS-*` through `B-EUK-TOXO-*` for Phase 28 (default eukaryotic pipelines)

**Effort:** 1 session for the sovereignty design doc + 1-2 sessions for the BYOP + eukaryotic schema migration work + half a session of P0b integration discussion. Total: 3-4 sessions for Phase 24.5.

**Phase placement justification:** All these schema decisions must be locked before P0b touches the schema. Doing them now means P0b is one migration, not three. Implementation work for the deletion logic, BYOP infrastructure, and default eukaryotic pipelines all happens in later phases (P0c, P0f, Phase 28 respectively) — but the *schema* lands in P0b alongside the existing v5.0 work.

---

## Phase 24.7 — P0f BYOP Infrastructure

**Why this phase exists:** BYOP (Bring Your Own Pipeline) infrastructure is the prerequisite for shipping default eukaryotic pathogen pipelines (Phase 28) AND for any operator wanting to register a custom workflow. It can't wait for P1 because eukaryotic coverage depends on it. It can't land in P0b because that's schema-only. P0f sits between P0e (where `jackpot init` becomes real and operator config is structured) and P0b/c (multi-tenancy schema + middleware), so BYOP allowed-registries / allowed-licenses / sandbox-resource-limits are install-time questions that `jackpot init` can prompt for.

**Source:** `jackpot_byop_and_eukaryotic_design.md` Part I (Sections 1-10). Schema migration items already covered in Phase 24.5 (B-BYOP-9, B-BYOP-9b).

**Phase placement justification:** P0e finishes the install-CLI work (operator config gets structured). P0f adds BYOP infrastructure that uses that operator config. Then P0b/c handles multi-tenancy schema + middleware. Then P1 handles operator-type configurability of the now-real BYOP system.

### N. BYOP architecture (overview §1-10 of `jackpot_byop_and_eukaryotic_design.md`)

```text
[ ] B-BYOP-1   Implement jackpot-pipeline.yaml manifest schema. Create
               schema/byop-pipeline-manifest.schema.json. Document under
               docs/byop/manifest.md. Specifies the 9-section YAML format:
               api_version, kind, metadata, engine, applicability,
               resources, reference_data, containers, inputs, outputs,
               permissions, cost. (1-2 sessions, P0f start)

[ ] B-BYOP-2   Implement backend/services/byop_validator.py — Stage 1
               static validation. Per-engine syntax checks (nextflow
               inspect, snakemake --lint, miniwdl check, bash -n / python
               -c), container resolution (registry reachability, tag
               existence, digest verification), reference data resolution
               (HTTP HEAD + checksum), license compatibility (SPDX
               against operator allowlist), permissions sanity (egress
               allowlist, GPU availability, internet_required vs
               Scenario T policy). (3-4 sessions, P0f)

[ ] B-BYOP-3   Implement backend/services/byop_sandbox.py — Stage 2
               sandbox dry-run with isolation. Per-engine dry-run
               mechanic: nextflow -stub-run, snakemake -n,
               miniwdl --task-only-resources, manifest engine via
               JACKPOT_DRY_RUN=1 env var with 60s fallback timeout.
               Kubernetes-namespace isolation for cloud, Docker-network
               isolation for local. Egress restricted to operator
               allowlist. 5-minute hard timeout. 2 CPU / 4 GB RAM /
               10 GB storage cap. Synthetic test inputs from
               backend/test_data/byop_sandbox/. (1 week, P0f — most
               complex item in the phase)

[ ] B-BYOP-4   Implement backend/routers/byop.py — full CRUD API.
               POST /api/v1/byop/pipelines (register), GET (list),
               GET /{id} (detail), PATCH /{id}, POST /{id}/revalidate,
               POST /{id}/deactivate, DELETE /{id} (move to ARCHIVED),
               GET /{id}/manifest, GET /{id}/validation,
               GET /api/v1/byop/manifest-schema,
               GET /api/v1/byop/test-data. Existing
               /api/v1/pipelines/launch accepts byop_pipeline_id
               alongside pipeline_zoo_id. (2-3 sessions, P0f)

[ ] B-BYOP-5   Implement engine launchers — 4 sub-items in parallel.
               (a) backend/services/nextflow_launcher.py — harden
                   existing path, auto-inject -weblog, enable -resume
                   with JACKPOT-managed work directory.
               (b) backend/services/snakemake_launcher.py — new.
                   Read Snakefile, resolve singularity:/container:/
                   conda: directives, wrap with event-streaming script
                   that polls --report JSON every 30s.
               (c) backend/services/wdl_launcher.py — new. Support
                   both Cromwell (heavyweight) and miniwdl (lightweight)
                   via JACKPOT_WDL_BACKEND. Populate inputs.json from
                   manifest. Poll Cromwell metadata API or parse
                   miniwdl structured logs.
               (d) backend/services/manifest_launcher.py — new.
                   Docker run wrapper for the manifest engine. Single
                   container, single command, structured timing and
                   exit-code event emission.
               (2-3 sessions per launcher = 1.5-2 weeks total, P0f)

[ ] B-BYOP-6   Implement backend/services/byop_quarterly_revalidation.py
               background job. Re-runs Stage 1 + Stage 2 against
               registered pipelines on configurable cadence (default
               90 days) to catch silently-broken upstream containers
               or moved Git refs. Failed re-validation transitions
               pipeline to DEACTIVATED with notification. (1 session, P0f)

[ ] B-BYOP-7   Implement Streamlit BYOP registration wizard (new page).
               6-step wizard: source type → source details → manifest
               preview → validation status (live updates via polling)
               → sandbox status → activated. Per-source-type forms
               (public Git, private Git with deploy key gen, tarball
               upload, Docker image). (2-3 sessions, P0f)

[ ] B-BYOP-8   Implement Streamlit BYOP catalog tab on the Pipelines
               page. List registered BYOP pipelines with status badges,
               filter by engine/organism/status, link to detail view.
               Sample-detail-page launch dropdown shows BYOP pipelines
               whose applicability.organism_names matches the sample's
               organism. (1-2 sessions, P0f)

[ ] B-BYOP-10  Implement BYOP telemetry — aggregated success rate,
               walltime, peak memory, cost per run for each registered
               pipeline. Auto-deactivate pipelines whose success rate
               drops below operator-configured threshold (default 50%)
               with platform admin notification. (1-2 sessions, P0f)
```

### Phase 24.7 / P0f success criterion

- [ ] All 4 engine types (Nextflow, Snakemake, WDL, manifest) can register a pipeline through the API
- [ ] Two-stage validation gates work end-to-end on a real test pipeline per engine
- [ ] Streamlit registration wizard works for all 4 source types
- [ ] BYOP catalog tab shows registered pipelines correctly
- [ ] At least one example BYOP pipeline per engine type is documented and tested
- [ ] Quarterly revalidation job runs on schedule
- [ ] Telemetry surface in catalog UI

**Total effort:** ~3-4 weeks of full-time engineering work, parallelizable across 2-3 contributors.

---

## Phase 25 — Month 3 Stretch Goals (Tracked, Not Scheduled)

- [ ] Streamlit admin pages: `lab_director.py`, `platform_admin.py`,
      `archive_requests.py`, `billing.py`
- [ ] JupyterHub workspace with all three profiles (Analyst,
      Bioinformatician, Developer)
- [ ] BYOP full wire-up: fetch `nextflow_schema.json` from registered
      repo, validate, enable launching — *largely superseded by Phase 24.7 / P0f (BYOP infrastructure with multi-engine support, manifest schema, two-stage validation). This Phase 25 stretch goal becomes "remaining UI polish" once P0f lands.*
- [ ] GCP production deployment
- [ ] `ncbi_submissions` router (TOSTADAS integration) — *see also `B-LOC-1` Phase 26 (lift Loculus `ena-submission/` as the ENA broker, AGPL-3.0 → AGPL-3.0 frictionless)*
- [ ] `datasets` router (table exists, router stub)
- [ ] `archive_requests` router
- [ ] `saved_searches` router
- [ ] `notifications` router (full — currently placeholder in UI)
- [ ] Remaining parsers if any pipelines were deferred
- [ ] External database search (`/api/v1/external-search/` — NCBI, ENA,
      GISAID proxy) — *see also `B-EB-3` Phase 26 (daily SRA auto-scan pipeline pattern from EnteroBase, complementary to one-shot search)*
- [ ] Re-enable detect-secrets in pre-commit
- [ ] Playwright end-to-end UI tests
- [ ] US-states controlled vocabulary for `collection_location_state`
- [ ] Retire `jackpot-frontend` repo (vestigial stub — real UI lives
      in `jackpot-backend/frontend/`)

## Phase 26 — Pathoplexus/Loculus Comparative Analysis Backlog (Tracked, Not Scheduled)

**Source:** `jackpot_pathoplexus_loculus_overview.md` (April 2026 working session). Cross-references to overview document sections in parentheses. Full effort and phase metadata for each item lives in overview Section 16.10. Items refining or decomposing existing Phase 25 / Year 2 entries are marked `[refines #X]`.

### A. Loculus code adoption (overview §11 A1-A6, §12.1a)

- [ ] **B-LOC-1** Lift Loculus `ena-submission/` as JACKPOT ENA broker. AGPL-3.0 → AGPL-3.0. (1-2 sessions, P0d or after)
- [ ] **B-LOC-2** Lift Loculus `ingest/Snakefile` clean-room as `pipelines/insdc-ingest/`. NCBI Datasets CLI based. (2-3 sessions, P0d)
- [ ] **B-LOC-3** Add `backend/routers/preprocessing.py` implementing the Loculus `/extract-unprocessed-data` and `/submit-processed-data` HTTP contract. (2-3 sessions, P1)
- [ ] **B-LOC-4** Update `ValidationResult` to Loculus structured error/warning schema (FieldRef, ProcessingIssue, validator_version). (1 session, any)
- [ ] **B-LOC-5** Switch CSV ingest to NDJSON streaming (memory O(N) → O(1)). (1 session, any)
- [ ] **B-LOC-6** Add `validator_version` and reprocessing background job. Modeled on Loculus `pipelineVersion` auto-promotion. (1-2 sessions, with B-LOC-3)
- [ ] **B-LOC-7** Add `jackpot submit/revise/revoke` CLI commands modeled on Loculus `cli/`. (2 sessions, P0e)

### B. NCBI integrations (overview §12.0, §16.4)

- [ ] **B-NCBI-1** BigQuery JOIN for NCBI Pathogen Detection — surface PDS# cluster IDs and MicroBIGG-E AMR results in samples table. (2 sessions, post-staging-cutover)
- [ ] **B-NCBI-2** hAMRonization output mandate for all AMR pipelines in the zoo. (1 session per pipeline, pipeline zoo work)
- [ ] **B-NCBI-3** Mint stable JACKPOT cluster accessions (JKPT-prefixed, versioned) for any cgMLST/SNP cluster. Persist tree representations in newick + JSON. (1 week, Year 2 with cgMLST clustering)

### C. Governance & Pathoplexus UI patterns (overview §12.1)

- [ ] **B-GOV-1** Create `governance/` directory with charter.md, coi-policy.md, jurisdiction-and-data-residency.md, benefits-sharing-framework.md, access-grievance-procedure.md, platform-shutdown-data-portability-plan.md, advisory-board.md. Modeled on Pathoplexus governance docs. (3-5 hours of writing, P0d alongside monorepo)
- [ ] **B-PPX-1** Adopt per-sample OPEN/RESTRICTED radio button on Streamlit upload page. Schema already supports it; just wire UI. (half a session, any)

### D. Pathogenwatch (overview §12.2a, §16.2)

- [ ] **B-PWATCH-1** Pathogenwatch results-pull for bacterial samples (Salmonella, Klebsiella, Mtb, Neisseria). Push assembly via API, pull cgMLST/MLST/AMR/SNP-tree results back into pipeline_results. (3-4 sessions, Year 2)
- [ ] **B-PW-1** Add `pathogenwatch-oss/speciator` as Level-1 pipeline-zoo entry — Mash-based species ID. (1 session, any pipeline-zoo work)
- [ ] **B-PW-2** Add `pathogenwatch-oss/mlst` as Level-1 zoo entry — MLST/cgMLST per-pathogen schemes. (1-2 sessions, any pipeline-zoo work)
- [ ] **B-PW-3** Vendor `pathogenwatch-oss/amr-libraries` as JACKPOT reference data under `reference-data/amr-libraries/`. (1 session, P0d)
- [ ] **B-PW-4** Add seroba (pneumococcus), vista (cholera), inctyper (plasmid Inc) as zoo entries when relevant pathogens come into scope. (1 session each)
- [ ] **B-PW-5** Phylocanvas + Leaflet + metadata-table tri-pane for collection visualizations. (1-2 weeks, Year 2 React migration) `[refines Phase 25 / Year 2 #5]`
- [ ] **B-PW-6** Add `/priority-pathogens` dashboard page mapping WHO BPPL 2024 to JACKPOT's organism enum. (1 session, any)

### E. GenSpectrum / LAPIS (overview §12.2c, §16.1)

- [ ] **B-LAPIS-1** Expose LAPIS-compatible REST endpoint for JACKPOT viral data. (1-2 weeks, Year 2)
- [ ] **B-GS-1** Embed GenSpectrum `dashboard-components` for viral variant tracking when JACKPOT migrates from Streamlit to React. AGPL-3.0 → AGPL-3.0. (3-5 sessions, Year 2 post-Streamlit migration)
- [ ] **B-GS-2** Make all JACKPOT search/filter/dashboard state URL-encoded via `st.query_params`, so any view is shareable. (1-2 sessions across all Streamlit pages, any)

### F. EnteroBase (overview §12.2b, §16.3)

- [ ] **B-EBASE-1** EnteroBase HierCC pull for Salmonella and E. coli. (2-3 sessions, Year 2) `[refines Phase 25 / Year 2 #6 — lightweight pull path]`
- [ ] **B-EB-2** Implement native hierarchical clustering codes (JACKPOT-HC) for any cgMLST-typed bacterial sample. 11 distance thresholds matching EnteroBase HierCC. (2-3 weeks, Year 2) `[native-computation companion to #6; basis for federation]`
- [ ] **B-EB-3** Add `pipelines/insdc-daily-scan/` — daily Snakemake job that scans NCBI SRA for new sequences matching the operator's organism enum, auto-ingests via B-LOC-2. Operator-opt-in. (1 week, Year 2) `[continuous-scan companion to Month 1 #4]`

### G. BV-BRC (overview §16.5)

- [ ] **B-BVBRC-1** Add a fast-track queue lane for jobs <30s (BLAST, single-genome typing) separate from the long-running pipeline lane. Modeled on BV-BRC's two-tier queue. (2-3 sessions, when scale demands it — Year 2+)
- [ ] **B-BVBRC-2** Add explicit "publish" ceremony when transitioning sample from DISCOVERABLE to PUBLIC — generates citation block, mints persistent identifier, snapshots metadata. (1-2 sessions, any)

### H. Solu (overview §16.6)

- [ ] **B-SOLU-1** Design a "rapid triage" pipeline that runs species ID + AMR + nearest-neighbour phylogeny in <5 minutes for single-sample uploads. "Is this an outbreak strain we've seen?" — yes/no plus context. (2-3 weeks, Year 2)
- [ ] **B-SOLU-2** Add a continuous-surveillance background job that re-runs cluster computation on all samples of an organism when new samples arrive. Updates `samples.cluster_id`; preserves immutable historical pipeline_results. (1 week, Year 2)
- [ ] **B-SOLU-3** Add `docs/trust.md` (later promoted to `trust.jackpot.health` subdomain) documenting security practices, data residency, encryption, audit log, DLP, scrubber, deletion lifecycle. (4-6 hours of writing, with B-GOV-1)

### I. RT-MetA (overview §12.3, §16.7)

- [ ] **B-RTMA-1** Reach out to the RT-MetA team about collaboration on offline-capable architecture. They're IPSN-funded and explicitly looking for collaborators. (1 email + one call, now)
- [ ] **B-RTMA-2** Design offline-first mode for Scenario A — SQLite-only backend, optional sync-when-online to a parent instance, conflict-resolution policy. (2-3 weeks design + more for implementation, Year 2) `[architectural companion to Phase 25 / Year 2 #7 hub-and-spoke federation]`
- [ ] **B-RTMA-3** Adopt RT-MetA's untargeted metagenomics framework as a JACKPOT pipeline-zoo entry, paired with nf-core/taxprofiler. (4-6 weeks, Year 2+)

### J. GISAID-derived (overview §16.8)

- [ ] **B-GISAID-1** When exporting a dataset, auto-generate a structured Acknowledgments block citing each originating lab, sample IDs, and submission dates. Format aligned with Nature/PHA4GE recommended citation conventions. (1-2 sessions, any)

### Phase 26 quick-win priority order (from overview §16.9)

If grabbing low-effort high-ROI items between sprints:

1. **B-PW-1** Speciator (1 session) — bacterial species ID is foundational
2. **B-PW-2** MLST/cgMLST (1-2 sessions) — closes a major bacterial gap
3. **B-PW-3** AMR libraries vendored (1 session) — curated reference data
4. **B-GS-2** URL-encoded query state (1-2 sessions) — shareable views
5. **B-GISAID-1** Auto-Acknowledgments on export (1-2 sessions) — submission-incentive loop

---

## Phase 27 — CDC DMI / North Star / STLT Alignment Backlog (Tracked, Not Scheduled)

**Source:** `jackpot_cdc_dmi_stlt_overview.md` (April 2026 working session). This is parallel to Phase 26 — different lens. Where Phase 26 covers "things lifted from open-source peer platforms" (Loculus, Pathogenwatch, etc.), Phase 27 covers "things adapted from US public-health-data ecosystem" (CDC DMI, North Star Architecture, STLT operator needs, CARE Principles for Indigenous Data Sovereignty). 14 items total across 3 groups.

**Already moved to other phases:**

- `B-DMI-3`, `B-STLT-2`, `B-GOV-1` (combined with `B-CARE-1`), `B-CARE-2`, `B-DMI-1`, `B-STLT-1`, `B-STLT-3` are in **Phase 21.5** (Interstitial During-P0d Quick Wins) since they ride along with monorepo / docs work
- `B-CARE-3-DESIGN` is in **Phase 24.5** (Architectural Design Lockdown) since it gates P0b schema work

The items below are the ones that don't fit those interstitial buckets — implementation items, larger work, or pure outreach.

### K. Tribal sovereignty / CARE Principles (overview §11-12 of `jackpot_cdc_dmi_stlt_overview.md`)

- [ ] **B-CARE-3** (implementation) Implement true delete-on-request via tombstone-and-vacuum lifecycle per the design from Phase 24.5. Code: `samples.deletion_status` enum migration, tombstone-marking logic, vacuum background job, audit log integration, GCS/MinIO object deletion, JSONB content scrubbing. (2-3 sessions, **P0c — multi-tenancy middleware**)
- [ ] **B-CARE-4** Federation-aware deletion propagation. Tombstone events pushed to peers; signed receipts; SLA tracking; non-compliance flagging. Depends on B-CARE-3 + Scenario E federation work. (1 week, Year 2)
- [ ] **B-CARE-5** Pre-publish review checklist with CARE-Principle confirmation. Scenario T defaults to no-auto-publish; explicit per-sample approval required. "Previously published" tag persists past vacuum. (1-2 sessions, with B-CARE-3 implementation in P0c)
- [ ] **B-CARE-6** Reach out to NPAIHB / Northwest TEC about Scenario T pilot. Highest-fit Tribal Epidemiology Center based on existing data-modernization work. **Do this in parallel with Phase 24.5 design** so their input lands before the design is locked. (1 email + 1 call, **now**)

### L. STLT-tier alignment (overview §6, §10 of `jackpot_cdc_dmi_stlt_overview.md`)

(Most STLT items are in Phase 21.5 — they're documentation that rides along with P0d. The implementation-shape items below are separate.)

- [ ] **B-STLT-4** (NEW) Build a **scenario detector** in `jackpot init` that asks operator-type questions (state? local? Tribal? academic?) and selects appropriate scenario defaults (Scenario A vs B vs C vs T) plus seeds appropriate config. (1-2 sessions, **P0e** with `jackpot init` work)

### M. CDC DMI / North Star alignment (overview §3-5 of `jackpot_cdc_dmi_stlt_overview.md`)

- [ ] **B-DMI-2** Build `backend/routers/fhir.py` for FHIR `Specimen` + `MolecularSequence` ingest, `Observation` + `Provenance` emit. Gated on operator demand — don't build speculatively. (1-2 weeks, Year 2)
- [ ] **B-DMI-4** APHL Communities of Practice engagement — propose a JACKPOT presentation at the AMD CoP or Bioinformatics and Molecular Epidemiology fellowship cohort. Awareness-building. (1 email + 1 talk preparation, opportunistic)
- [ ] **B-DMI-5** Investigate APHL AMD National Bioinformatics Platform for partner-vs-peer relationship. Could be parallel to JACKPOT, could be complementary, could share components. Worth a fact-finding call before assuming the relationship. (1 fact-finding call, opportunistic)

### Phase 27 quick-win priority order

The highest-leverage items have *already moved* to Phase 21.5 (governance docs, layer-cake, deploy guides) and Phase 24.5 (sovereignty design). What's left in Phase 27 proper is a mix of larger implementation work and outreach. The two items worth doing soonest:

1. **B-CARE-6** (NPAIHB outreach) — must happen *before* Phase 24.5 design is locked, so their input shapes it. **This is technically in this list but should be acted on as soon as Phase 24.5 starts.**
2. **B-DMI-5** (APHL AMD fact-finding) — opportunistic; sets up future positioning. Can happen anytime.

The rest is implementation work that gates on P0b/c/e or Year 2.

---

## Phase 28 — Default Eukaryotic Pathogen Pipelines (Tracked, Tier-Prioritized)

**Source:** `jackpot_byop_and_eukaryotic_design.md` Part II (Sections 11-16). Schema work for these pipelines already in Phase 24.5 (B-EUK-1, B-EUK-2, B-EUK-3). BYOP infrastructure required to register them as zoo entries already in Phase 24.7 / P0f. This phase is the actual pipeline implementations + parsers + dashboards.

**11 implementation items** organized into **3 tier-prioritized groups** by global disease burden, surveillance utility, and community tooling availability. Each pipeline ships with its parser; dashboards group two pathogen groups per page.

**All pipelines:** AGPL-3.0, hosted under `Midnight-Oil-Innovation/jackpot-pipelines-eukaryotic` (single repo, one subdirectory per pipeline), registered as Level-1 zoo entries via P0f BYOP infrastructure.

### Phase 28 Tier 1 — ship first (highest priority)

Highest global disease burden + most active surveillance community + largest existing tooling base. Builds JACKPOT credibility for global infectious disease surveillance work.

```text
[ ] B-EUK-PLAS-1  jackpot-plasmodium-typer pipeline (Nextflow). Drug
                  resistance loci genotyping (pfk13, pfdhfr, pfdhps,
                  pfcrt, pfmdr1) + HRP2/HRP3 deletion detection +
                  lineage assignment. Wraps bcftools for SNP calling
                  against PlasmoDB references. (1-2 weeks, post-P0f)

[ ] B-EUK-CRYP-1  jackpot-cryptogiardia-typer pipeline (Nextflow).
                  GP60 subtyping for Cryptosporidium (gold-standard
                  outbreak typing) + Giardia assemblage assignment +
                  WGS SNP outbreak clustering. US-relevant for
                  waterborne outbreak surveillance. Smallest eukaryotic
                  genome → fastest pipeline. (1-2 weeks, post-P0f)

[ ] B-EUK-PARSE-T1  Parsers for Tier 1 pipelines:
                    plasmodium_drug_resistance_results parser,
                    cryptogiardia_typing_results parser. Follow
                    existing pattern in backend/parsers/.
                    (1 session per parser, post-P0f)

[ ] B-EUK-DASH-T1   Streamlit dashboard pages for Tier 1:
                    Malaria dashboard (drug resistance prevalence by
                    region/year, pfk13 SNP frequency, HRP deletion
                    prevalence, MOI distribution),
                    Crypto/Giardia dashboard (outbreak cluster map,
                    GP60 subtype trends, assemblage distribution).
                    (2-3 sessions per dashboard, post-pipelines)
```

### Phase 28 Tier 2

Medium-priority pathogens with significant disease burden but less active surveillance community or smaller existing tooling base.

```text
[ ] B-EUK-LEIS-1  jackpot-leishmania-typer pipeline (Nextflow).
                  Species discrimination + MLST + drug resistance
                  (antimony, miltefosine, paromomycin). Maps against
                  TriTrypDB references. (1-2 weeks, post-Tier-1)

[ ] B-EUK-TRYP-1  jackpot-trypanosoma-dtu-caller pipeline (Nextflow).
                  DTU assignment for T. cruzi (TcI through TcVI) +
                  drug resistance for T. brucei spp. Handles the
                  high heterozygosity / aneuploidy of T. cruzi.
                  (1-2 weeks, post-Tier-1)

[ ] B-EUK-SCHI-1  jackpot-schistosoma-barcode pipeline (Snakemake —
                  first non-Nextflow default pipeline, exercises P0f
                  Snakemake launcher). cox1/nad1/ITS markers +
                  hybrid detection (S. haematobium × S. bovis).
                  (1 week, post-Tier-1)

[ ] B-EUK-PARSE-T2  Parsers for Tier 2 pipelines:
                    leishmania_typing_results,
                    trypanosoma_typing_results,
                    schistosoma_typing_results.
                    (1 session per parser, with each pipeline)

[ ] B-EUK-DASH-T2   Streamlit dashboard pages for Tier 2:
                    Leishmania dashboard (species distribution, drug
                    resistance trends, HIV co-infection cases),
                    Trypanosoma dashboard (DTU geographic distribution,
                    treatment-outcome correlation),
                    Schistosoma dashboard (hybrid detection map, PZQ
                    resistance, cox1 haplotype trees).
                    (2-3 sessions per dashboard, post-pipelines)
```

### Phase 28 Tier 3

Lower-priority for sequencing-based surveillance (most STH and filarial work is amplicon/PCR rather than WGS), but completes the eukaryotic coverage picture.

```text
[ ] B-EUK-STH-1   jackpot-sth-nemabiome pipeline (Nextflow). Wraps
                  existing nemabiome amplicon analysis from Tasmania.
                  Species ID + β-tubulin codon 167/198/200 SNPs
                  (benzimidazole resistance markers). (3-5 sessions,
                  post-Tier-2)

[ ] B-EUK-STH-2   jackpot-sth-wgs pipeline (Nextflow). WGS-based SNP +
                  resistance + population structure for soil-
                  transmitted helminths. For labs with WGS rather
                  than amplicon capacity. (1-2 weeks, post-Tier-2)

[ ] B-EUK-FILA-1  jackpot-filarial-typer pipeline (Nextflow). Species
                  ID (W. bancrofti, B. malayi, B. timori) + Wolbachia
                  endosymbiont status (basis for doxycycline therapy)
                  + ivermectin resistance. (1-2 weeks, post-Tier-2)

[ ] B-EUK-TOXO-1  jackpot-toxo-entamoeba-typer pipeline (Nextflow).
                  Toxoplasma 15-marker MLST + clonal lineage
                  assignment (Type I/II/III + atypical) +
                  Entamoeba histolytica vs E. dispar discrimination
                  (most "histolytica" in microscopy is dispar — no
                  treatment needed). (1 week, post-Tier-2)

[ ] B-EUK-PLAS-2  jackpot-plasmodium-mippy pipeline (Nextflow). Wraps
                  existing mippy for amplicon-based malaria surveillance.
                  For labs running amplicon panels rather than WGS.
                  (3-5 sessions, post-Tier-2)

[ ] B-EUK-PARSE-T3  Parsers for Tier 3 pipelines:
                    helminth_drug_resistance_results,
                    filarial_typing_results,
                    toxo_entamoeba_typing_results.
                    (1 session per parser, with each pipeline)

[ ] B-EUK-DASH-T3   Streamlit dashboard pages for Tier 3:
                    STH dashboard (β-tubulin SNP prevalence, species
                    map),
                    Filarial dashboard (elimination program tracking,
                    ivermectin resistance, Wolbachia status),
                    Toxo/Entamoeba dashboard (lineage geographic
                    distribution, E. histolytica vs E. dispar
                    differential).
                    (2-3 sessions per dashboard, post-pipelines)
```

### Phase 28 success criterion

- [ ] All 10 default eukaryotic pipelines registered as Level-1 zoo entries via P0f BYOP infrastructure
- [ ] All 8 dashboard pages live in Streamlit researcher view
- [ ] All 8 pipeline-result tables receiving data from real pipeline runs
- [ ] At least one end-to-end test sample per pathogen group with verified results
- [ ] Documentation under `docs/pipelines/eukaryotic/` describing each pipeline

**Total effort:** ~10-15 weeks if sequential, ~4-6 weeks if parallelized across 3 contributors. Each pipeline is genuinely independent work.

**Phase placement justification:** Cannot start until P0f (BYOP infrastructure) is real, since these pipelines register *via* BYOP. Schema is ready in P0b. Internal tier-priority orders the actual implementation order based on global health impact and tooling availability.

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
confirm the landing page says "Signed in as the maintainer" (should be
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
