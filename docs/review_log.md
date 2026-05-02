# Phase 22 Review Log — 2026-05-01

Periodic review checkpoint after P0d (monorepo migration) + P0d.1 (post-execution
cleanup). Source artifacts: `/tmp/phase22_agent{1,2,3,4}_*.md` (review agents).
Path normalization: all references use canonical `/Users/glen/Projects/jackpot/`
(macOS APFS is case-insensitive; agent 3's report typed `projects` lowercase in
three places — same files, no findings affected).

## Executive summary

Codebase is structurally healthy post-P0d. `backend/backend/` core production code
is **clean** of operator-specific values (Critical Rule 55) and follows the Rule
41 transactional pattern, Rule 23 pagination pattern, and Rule 14 lazy-engine
pattern. The four CRITICAL Rule 55 violations carried over from before P0d
(`backend/setup/write_files*.py`, baseline migration `5adf11b77c19`,
`deploy/helm/jackpot-api/Chart.yaml`, `deploy/scripts/bootstrap_project.sh`) are
all still present — they were known going into Phase 22 and remain real work.

P0d introduced **two new HIGH** Rule 55 violations in `cli/` user-visible help
text (`cli/jackpot/cli/upload.py:442` operator path, `cli/jackpot/cli/main.py:25,47`
ADHS URL example) and one **dead env var** (`ADHS_ORGANIZATION_NAME` in Helm
values, not consumed by `config.py`). These are quick fixes (small, safe).

**The 39% coverage figure is real, not a measurement artifact.** Pytest-cov
correctly instruments `backend/backend/*.py`. The 47-point drop from the 86.99%
Session-H baseline is organic dilution — Sessions I–Q added ~800 statements with
low/no coverage (sample_access, larger ingest, pipeline_results_loader). Restoring
60% requires writing tests for those modules, not fixing tooling.

**44 incomplete-work markers.** Auth, migrations, and router production logic are
clean. The biggest concern: 7 stub routers return HTTP 200 with
`{"status": "not implemented"}` (silent-failure risk; should be 501) and 9 stale
CLI TODO comments lie about commands that already work end-to-end.

Spec drift is minor and mostly documentation-side: `POST /api/v1/auth/refresh`
declared complete in pre-session-fix #5 but not implemented; `STORAGE_BACKEND` env
var referenced but not in `config.py` (factory infers from `storage_endpoint`);
`backend/storage/` is a package, not the flat file the spec describes;
`backend/backend/storage/*.py` SPDX headers say `Apache-2.0` while project license
flipped to AGPL-3.0.

Nothing CRITICAL is blocking. The four Phase 22 named deliverables (SEC-1, SEC-2,
DEPLOY-1, DEPLOY-2) execute next.

---

## Critical Rules compliance

### CRITICAL — Rule 55 (operator-agnostic production code) — 5 inherited violations

All flagged in `learnings.md` P0d.1 entry; verified still present.

1. **`backend/setup/write_files.py:6,17,91,95`** — `~/ASU/jackpot` paths;
   `mock_user_email = "gotero@linuxprophet.com"`; `adhs_organization_name = "ADHS"`.
2. **`backend/setup/write_files_2.py`** — comprehensive (lines 21, 32, 148, 1639,
   1641, 1646, 1653, 1987, 2104, 2161, 2215). Arizona, Otero Lab, Mayo Clinic
   Phoenix, ADHS-2026-001, AZ-001 fixtures, "Successor to APGAP", ADHS reportable
   diseases reference.
3. **`backend/db/migrations/versions/5adf11b77c19_baseline_schema_from_init_sql.py`**
   (lines 59, 609, 614, 618, 622, 636) — seeds `Sonora Quest Laboratories`, `ASU`,
   `ADHS`, `gotero@linuxprophet.com`, `Otero Lab` directly into the DB. Migration
   chain ultimately resolves to clean `Example Org` at head (via `00b4bd99ddee`),
   but the baseline alone is the structural violation.
4. **`deploy/helm/jackpot-api/Chart.yaml:7,9,10`** — icon URL points at
   `linuxprophet/jackpot-backend`; maintainer is `Glen Otero` /
   `gotero@linuxprophet.com`.
5. **`deploy/scripts/bootstrap_project.sh:19,25,152`** — usage examples hardcode
   `gotero3-acdp-488517`; line 152 is a runtime-executing WIF attribute filter
   `assertion.repository_owner == 'linuxprophet'` that would block any other
   operator.

### HIGH — Rule 55 — NEW, P0d-introduced

6. **`cli/jackpot/cli/upload.py:442`** — Click `--source-path` `help=` string
   shows `/scratch/otero/sequences/`. User-visible runtime text, not a comment.
   Same file lines 474, 478, 485 — `\b`-formatted docstring blocks shown in
   `--help` reference `# Transfer from ASU Sol HPC` and `--source-endpoint asu-sol`.
7. **`cli/jackpot/cli/main.py:25,47`** — Click docstrings shown in `jackpot --help`
   and `jackpot config set --help` use `https://api.jackpot.adhs.az.gov` as the
   example URL. Plus dead `ADHS_ORGANIZATION_NAME: "ADHS"` env var in
   `deploy/helm/jackpot-api/values.yaml:70`,
   `deploy/helm/jackpot-api/values-staging.yaml:21`,
   `deploy/docs/.env.staging.example:49` — backend `config.py` consumes
   `host_organization_name`, never `ADHS_ORGANIZATION_NAME`.

### MEDIUM

8. **Rule 18 — `backend/backend/routers/ingest.py:288`** — FASTA-only auto-skip
   (`scrub_status = "PENDING" if "FASTQ" in file_types else "SKIPPED"`) lives in
   the router. Rule 18 places this in `validator.py`. `ValidationResult` has no
   `scrub_status` field. Behavior is correct; placement contradicts the rule.
9. **Rule 54 — `backend/db/migrations/env.py:9`** — Alembic `sys.path.insert()`
   to import `config.py`. Common Alembic pattern; rule text is broad but the
   intent ("cross-repo imports") may not target intra-repo path manipulation.
10. **Rule 55 — `deploy/docs/staging_access.md`,
    `deploy/docs/.env.staging.example`, `deploy/helm/jackpot-api/values-staging.yaml`**
    — `gotero3-acdp-488517` GCP project ID and `gotero3@asu.edu` operator email
    embedded throughout. `values-staging.yaml` is a deployed artifact.

### LOW

11. **Rule 54 — `backend/setup/write_files_2.py:369`,
    `backend/scripts/seed_sequencing_labs.py:14`,
    `backend/scripts/seed_reportable_organisms.py:18`** — `sys.path.insert()` in
    setup/seed scripts (not runtime API). Low because they aren't deployed.
12. **Rule 24 — `backend/backend/routers/pipelines.py:520` (Nextflow webhook),
    `auth.py:47,54` (`/me`, `/logout`), `dataharmonizer.py:146`** — return raw
    dicts instead of `success()` wrappers.

### Suspicious — needs human review

- **`schema/schema/jackpot_schema.yaml:226`** — LinkML field description text says
  *"Seeded values: 'Sonora Quest Laboratories', 'Laboratory Corporation of
  America'"*. Documentation, not runtime constraint. Update or accept as
  historical context.
- **`backend/backend/storage/*.py:2`** — `# Copyright (c) 2024-present Glen Otero`.
  Not "operator config" by Rule 55's definitions; legal authorship metadata.
  Decide: update to `Midnight-Oil-Innovation` now or defer to a license-cleanup
  phase.
- **`backend/setup/write_files_2.py:428,500`** — bare `import jwt`. Almost
  certainly a string literal *being written* to disk (not a live import), but
  Rule 13 prohibits `import jwt` outright; needs human confirmation.

### Clean

44 of 55 rules verified clean. Notable confirmations:

- Rule 1 (PermissionGroups exact), Rule 2 (Alembic-only DDL),
  Rule 3 (models_generated patch), Rule 4 (audit on writes),
  Rule 13 (`from jose import jwt` only in production), Rule 14 (lazy engine),
  Rule 20/52 (Alembic sole authority), Rule 23 (paginate), Rule 41 (transactional
  cohesion verified in organizations/samples/labs/ingest),
  Rule 44/52 (full chain reachable), Rule 45/53 (`cors_origins` NoDecode + before
  validator), Rule 50 (Dockerfile.ui + compose mount + PYTHONPATH).

---

## Spec→implementation drift

### Spec says X but code does Y / nothing

**§1 — Scenario T defaults absent from `config.py`.** Spec, decisions log, and
governance doc all say Scenario T has `deletion-on-request`,
`no auto-publish`, `federation off-by-default`. `Settings` has no
`deletion_on_request`, `auto_publish`, `federation_enabled`, or
`deployment_scenario` field. Governance layer exists; config layer is empty.
Correctly deferred to P0c per the phase chain — flag only.

**§3 — `STORAGE_BACKEND` env var is a fiction.** Spec §3 and `CLAUDE.md` document
`STORAGE_BACKEND=minio/gcs`. `config.py` has no such field. The factory
(`backend/backend/storage/factory.py`) infers backend type from whether
`storage_endpoint` is set. `docker-compose.yml` correctly uses `STORAGE_ENDPOINT`.
Spec/CLAUDE.md mis-document.

**Pre-session fix #5 — `POST /api/v1/auth/refresh` declared complete, not in
code.** `auth.py` has only `POST /google/login` and `POST /logout`.
`issue_refresh_token()` exists in `auth/oauth.py` and the refresh cookie is set at
login, but no endpoint redeems it. Browser-cookie flow may make this moot for the
Streamlit UI; CLI/SDK clients calling `/auth/refresh` would 404.

**§2/§6 — Coverage threshold mismatch.** Spec says 60% gate; `pyproject.toml`
enforces 35%. CLAUDE.md acknowledges this as post-P0d interim. Spec text not
updated.

**§5 Session G — `GET /api/v1/ingest/`** (line 329 of `ingest.py`) is an
undocumented self-index endpoint not in the 3-endpoint spec list.

**§5 Session N — `GET /api/v1/pipelines/`** (line 100 of `pipelines.py`) is a
list-runs endpoint not in the 9-endpoint spec list. Used by the Streamlit
dashboard.

**§3/§1 — `backend/storage.py` → `backend/storage/` package.** Spec describes a
flat file. Post-P0d it's a package (`__init__.py`, `factory.py`, `s3.py`,
`gcs.py`, `local.py`, `base.py`, `exceptions.py`, `settings.py`). Public
interface unchanged.

**§12 — Two reference materials missing from `docs/`.**
`jackpot_gcp_staging_deployment.html` and `jackpot_architecture_v5.md` are listed
but not in the repo. May be external session artifacts; if authoritative, should
be committed.

**§10 — Frontend path stale.** Spec says `jackpot-backend/frontend/`; post-P0d
canonical is `frontend/` at monorepo root.

**§11.1 — Q-10 / Q-11 status.** Both implemented (verified in `config.py` and
`pipeline_schemas/` package); spec still shows them as open.

### Code does X but spec doesn't mention it

- `backend/backend/permissions.py` — `PermissionGroups` enum, `can_access_sample`,
  `can_see_sample`, `visibility_sql_clause`. Substantive; not named in spec.
- `backend/backend/middleware.py` — `RequestIDMiddleware`. Not in spec.
- `backend/backend/logging_config.py` — structured logging. Not in spec.
- `backend/backend/version.py` — `__version__ = "5.0.0"`. Used by `/health`.
- `backend/backend/pipeline_schemas/` — package (9 modules) where spec said flat
  `pipeline_schemas.py`. Code is better organized than spec'd.
- `backend/backend/harmonizer.py` — separate module from the `dataharmonizer`
  router. Not in spec.
- `gisaid.py` — `POST /api/v1/gisaid/export/{lab_id}` takes integer PKs;
  spec examples use string `sample_id`. Internally consistent with DB schema.

### Decisions log conflicts

1. **AGPL-3.0 vs `Apache-2.0` SPDX in `backend/backend/storage/*.py`.** All 8
   storage module files carry `# SPDX-License-Identifier: Apache-2.0` headers.
   Direct conflict with the project-level AGPL-3.0 decision. Either the storage
   module was adapted from an Apache-licensed source (legal review needed) or the
   headers are stale from before the license flip. **Needs human decision.**
2. **`POST /api/v1/auth/refresh`** — declared complete, not implemented (above).
3. **§10 frontend path** stale (above).

### No premature schema landings

`byop_pipelines` table absent. Eukaryotic organism enums absent. Plasmodium /
Leishmania pipeline-result tables absent. B-BYOP-9 / B-EUK-1/2/3 correctly
deferred to Phase 24.5.

---

## Test coverage health

**Hypothesis: real, not measurement artifact.** Coverage measurement is working
correctly. The 47-point drop is organic dilution.

### Verification

```
uv run python -c "import backend; print(backend.__file__)"
# → /Users/glen/Projects/jackpot/backend/backend/__init__.py
```

Coverage data file (`.coverage`) contains entries for 43 files at correct
absolute paths under `backend/backend/`. Coverage table from the post-P0d run:

| Module | Stmts | Cover |
|---|---|---|
| `auth/guards.py` | 44 | 20% |
| `config.py` | 61 | 74% |
| `database.py` | 57 | 23% |
| `dlp_scanner.py` | 119 | 29% |
| `file_detector.py` | 158 | 27% |
| `harmonizer.py` | 39 | 0% (no tests) |
| `jobs.py` | 63 | 22% |
| `main.py` | 78 | 62% |
| `permissions.py` | 46 | 35% |
| `pipeline_results_loader.py` | 128 | 18% |
| `pipeline_schemas/*.py` | 174 | 100% (data-only) |
| `routers/ingest.py` | 230 | 19% |
| `routers/labs.py` | 166 | 29% |
| `routers/sample_access.py` | 150 | 23% |
| `routers/samples.py` | 181 | 17% |
| `routers/organizations.py` | 87 | 33% |
| `template_generator.py` | 130 | 21% |
| `validator.py` | 145 | 21% |
| `backend/storage/**` | omitted | — |
| **TOTAL** | **2664** | **39%** (CI) / **32%** (no Docker) |

### Three findings

1. **Documentation error in `learnings.md` and `CLAUDE.md`.** They say
   `backend/storage/` "shows 0% measured." Truth: it is **omit-listed**
   (`**/backend/storage/**` in `pyproject.toml` `[tool.coverage.run].omit`) —
   doesn't appear in the report at all. The omit pattern works. The 42 storage
   tests in `tests/storage/` exist and would cover the module if the omit were
   removed.

2. **`--cov=backend` is fragile but working.** `backend` is both a directory and
   a package name in this workspace. Coverage prefers the directory (correct
   here) but the unambiguous form is `--cov=backend/backend`. Easy fix.

3. **The 47-point drop is organic, not tooling.** 86.99% baseline was after
   Session H (~2000 stmts, 477 tests). Sessions I–Q added ~660 new stmts with
   mostly 0–25% coverage (sample_access 150 stmts at 23%; expanded ingest 230 at
   19%; pipeline_results_loader 128 at 18%). Math:
   `1740 covered / 2664 denominator ≈ 65%` if old code stayed fully covered, less
   if coverage dropped on existing code from the migration; observed 39% is
   consistent with new code averaging ~5–10% covered.

### Recommended fixes (effort-ranked)

1. **(5 min) Fix the docs.** Update `learnings.md` P0d entry and `CLAUDE.md`
   "Current Baseline" to drop the "storage shows 0%" and "pytest-cov measurement
   gap" claims. Replace with: organic dilution from Sessions I–Q untested code.
2. **(10 min) Change `--cov=backend` → `--cov=backend/backend`** in
   `pyproject.toml` `addopts`. Identical results today, eliminates the
   directory-vs-package ambiguity.
3. **(30 min) Consider un-omitting `backend/storage/`** — 42 tests exist; would
   add ~150 stmts at high coverage and lift the overall %. Need to confirm the
   storage tests run without external deps (moto for S3 etc.).
4. **(days) Write tests for Sessions I–Q.** Sample_access (150 stmts at 23% →
   target 70%), ingest (230 at 19% → 60%), labs (166 at 29% → 70%),
   template_generator and validator both at ~21% → ~60%. ~100 new tests overall
   to clear 60%.

Local-only blocker: `conftest.py` `postgres_container` autouse fixture errors 606
of 640 tests without Docker. CI uses testcontainers DinD. Local rapid-iteration
needs Docker running.

---

## Incomplete work inventory

**Total: 44 markers.** Auth: 0. Migrations: 0. Router production logic: 0
(`placeholders` hits in routers are SQL bind-parameter variable names, not
incomplete-work markers).

### Real work (11 items, ranked)

1. **`cli/jackpot/cli/auth.py:59`** — `jackpot auth login` is a paste-token stub.
   No `/api/v1/auth/cli-login-url` endpoint exists. CLI not user-ready.
2. **`cli/jackpot/cli/auth.py:143`** — `jackpot auth revoke` is a no-op (UI
   redirect message). No "delete current bearer token" endpoint.
3. **`cli/jackpot/cli/upload.py:517`** — `jackpot upload-globus` exits 1.
   Backend `POST /api/v1/ingest/globus` is a sequencing-facility webhook, not
   the pre-register/transfer/callback flow the CLI expects.
4. **`cli/jackpot/sdk/samples.py:52`** — `Sample.download_fastq()` raises
   `NotImplementedError` despite live backend `GET /samples/{id}/files` and
   `/download`. Pure wiring miss.
5. **`cli/jackpot/sdk/samples.py:120`** — `SamplesModule.search()` raises
   `NotImplementedError`; backend `GET /samples/` is live; SDK builds the
   correct `params` dict before raising.
6. **`cli/jackpot/sdk/samples.py:129`** — `SamplesModule.get()` raises
   `NotImplementedError`; backend `GET /samples/{id}` is live.
7. **Stub routers `datasets`, `notifications`, `archive_requests`,
   `saved_searches`, `billing`, `dataset_access`, `ncbi_submissions`** — return
   HTTP 200 with `{"status": "not implemented"}`. Visible in `/docs` Swagger UI.
   Silent-failure risk: a client that doesn't inspect the body will think the
   call succeeded. **Should return 501.** (Especially `datasets` and
   `notifications`, which the frontend actively calls.)
8. **`cli/jackpot/cli/auth.py:99`** — `jackpot auth status` checks token via a
   stub comment; never makes an API call. Backend has `GET /api/v1/users/me`.
   Stale path reference (TODO names `/auth/me`, which doesn't exist).

### Stale (9 items — should be deleted)

CLI commands that already work but have lying TODO comments:

- `cli/jackpot/cli/pipelines.py:72,186,212` — pipelines list/launch/status
- `cli/jackpot/cli/samples.py:113,167` — samples list/get
- `cli/jackpot/cli/upload.py:240,407` — upload + bulk upload-dir
- `cli/jackpot/sdk/pipelines.py:120,135` — SDK pipelines launch + list

Each says `# TODO: implement when X is built`; X is built; the CLI already calls
the correct URL. Comments create false impression of non-functionality.

### Out of scope (10 items, tracked for later phases)

- Month 2 / P0e: SRA `fetch()`, SRA `import_to_jackpot()`, references
  `download()`/`get_path()`, samples `register_from_workspace()`, CLI upload
  file_detector, samples free-text search.
- Month 3 / Phase 24: datasets `register_from_notebook()`, references admin list.
- Phase 26: NCBI submissions (TOSTADAS/ENA/Loculus).
- Month 3+ SaaS only: billing.
- Documentation TBDs (3 in `docs/*.md`).

### Harmless (14 items)

- `backend/backend/storage/base.py` — 9 `raise NotImplementedError` in
  `@abstractmethod` bodies (correct ABC pattern).
- `backend/backend/models_generated.py:27` — bare `pass` in
  `ConfiguredBaseModel(BaseModel)` body.
- Setup/script `pass` in `except` clauses with explanatory comments.
- Frontend pages `notifications.py`, `datasets.py`, `search.py` — intentional
  scaffolds with banner messages until endpoints ship.
- Test fixture string `"placeholder\n"`.

---

## Action items

Ordered by priority within Phase 22.

| # | Action | Effort | Phase placement |
|---|---|---|---|
| 1 | **SEC-1**: tighten CORS methods/headers in `backend/backend/main.py` | S | Phase 22 (this checkpoint) |
| 2 | **SEC-2**: rate limiting via `slowapi` on auth + ingest endpoints | M | Phase 22 |
| 3 | **DEPLOY-1**: production deploy approval gate + procedure doc | S | Phase 22 |
| 4 | **DEPLOY-2**: PITR restore drill procedure doc | S | Phase 22 (procedure-only; live drill deferred) |
| 5 | Fix coverage docs in `learnings.md` + `CLAUDE.md` (drop "0% storage" + "measurement gap" claims; describe organic dilution) | S | Phase 22D wrap |
| 6 | Change `--cov=backend` → `--cov=backend/backend` in `pyproject.toml` | S | Phase 22D wrap |
| 7 | Remove 9 stale CLI TODO comments | S | Phase 22D wrap or P0e |
| 8 | Wire 3 SDK methods (`Sample.download_fastq`, `SamplesModule.search/get`) — endpoints already live | S | P0e (alongside CLI work) |
| 9 | Fix CLI Rule 55 (Glen-introduced) — `cli/jackpot/cli/upload.py:442,474,478,485`; `cli/jackpot/cli/main.py:25,47`; remove dead `ADHS_ORGANIZATION_NAME` from Helm values | S | P0e |
| 10 | Stub routers return 501 instead of 200 (datasets, notifications, archive_requests, saved_searches, billing, dataset_access, ncbi_submissions) | S | P0e or earlier |
| 11 | Fix the 5 inherited Rule 55 CRITICAL violations: `backend/setup/write_files*.py`, baseline migration `5adf11b77c19`, `Chart.yaml`, `bootstrap_project.sh` | M | P0e (must land before any non-Glen operator deploys) |
| 12 | Implement `POST /api/v1/auth/refresh` OR remove the spec claim that it exists | S | P0e |
| 13 | Resolve `backend/backend/storage/*.py` SPDX `Apache-2.0` vs project AGPL-3.0 | S, needs decision | P0e or dedicated license cleanup |
| 14 | Update spec: replace 60% coverage with interim 35% + restoration plan; update §10 frontend path; close Q-10/Q-11 entries; update §3 `STORAGE_BACKEND` to `STORAGE_ENDPOINT` | S | P0e |
| 15 | Restore 60% coverage by writing tests for Sessions I–Q routers | L (~100 tests) | Pre-Phase-26 (was Phase 21.5 follow-up) |
| 16 | Implement `jackpot auth login` OAuth flow + backend `/auth/cli-login-url` endpoint | M | Month 2 / P0e or after |
| 17 | Build out 7 stub routers (datasets, notifications, archive_requests, saved_searches, billing, dataset_access, ncbi_submissions) | L | Month 3 / Phase 24+ |
| 18 | Move Rule 18 violation in `ingest.py:288` (FASTA scrub_status logic) into `validator.py.ValidationResult` | S | Refactor pass alongside Phase 24 |
| 19 | CI track separate from Phase 22: investigate testcontainers DinD reliability if integration tests are erroring silently | M | CI track |

---

## Notes for next phase

- Critical Rule 55 inherited violations are now formally tracked and dated — they
  shouldn't surprise anyone again.
- The "coverage measurement gap" framing should be retired from internal docs;
  the gap is real coverage debt from Sessions I–Q.
- `backend/backend/` core code is in good shape — the next refactor pass should
  focus on CLI and deploy, where most of the new debt lives.

---

# P0e closeout — 2026-05-02

P0e shipped `jackpot init` (operator-bootstrap CLI) and absorbed 13
cleanup items the Phase 22 review had explicitly tagged for it. This
section closes out which Phase 22 action items P0e resolved and which
got deferred further.

## Phase 22 action items resolved by P0e

| # | Item | P0e commit(s) | Outcome |
|---|---|---|---|
| 5 | Fix coverage docs in `learnings.md` + `CLAUDE.md` | (resolved post-Phase-22 by 863fd18) | Already done |
| 6 | Change `--cov=backend` → `--cov=backend/backend` | (resolved post-Phase-22 by 863fd18) | Already done |
| 7 | Remove 9 stale CLI TODO comments | 6b3bc7b | 7 stale comments deleted (the 9th + 10th were classified non-stale on closer inspection) |
| 8 | Wire 3 SDK methods | 6b3bc7b | `Sample.download_fastq`, `SamplesModule.search`, `SamplesModule.get` all wired against live backend endpoints |
| 9 | Fix CLI Rule 55 (Glen-introduced) | 7d1a2e3 + f2626a1 | `cli/jackpot/cli/upload.py:442/474/478/485` + `cli/jackpot/cli/main.py:25,47` operator strings replaced; dead `ADHS_ORGANIZATION_NAME` env var deleted from 3 deploy files |
| 10 | Stub routers 200 → 501 | e0e2046 | 7 stub routers convert to HTTP 501 with envelope-conforming HTTPException; 14 contract tests guard the new status code |
| 11 | Fix 5 inherited Rule 55 CRITICAL violations | 3369eb8 + 156b7ab + 7465d45 + b3d4978 + 204c493 | All 5 inherited + 6 in `values-staging.yaml` + 7 misc CLI/deploy strings now operator-agnostic. `backend/setup/` deleted entirely (3,378 lines of vestigial scaffold). Baseline migration seeds Example Org/Lab/admin directly; rename chain becomes historical no-op. |
| 12 | Implement `POST /api/v1/auth/refresh` OR remove the spec claim | d037ea4 | Deferred to P1. Spec.md fix #5 carries a ⚠️ note. The refresh-token cookie IS issued at login; only the explicit-refresh endpoint is missing. |
| 13 | Storage SPDX `Apache-2.0` vs project AGPL-3.0 | d7be3ff | git-history audit confirmed the storage refactor predated the AGPL flip by 2 days; SPDX headers were stale, not derived. Flipped 14 files to `AGPL-3.0-or-later`. |
| 14 | Spec updates (60→80%, STORAGE_BACKEND→STORAGE_ENDPOINT, close Q-10/Q-11) | c02b44c | spec.md aligned to current state |
| 15 (revised) | Close 4 real coverage gaps | 961610f | `harmonizer.py` 0→97%, `gisaid.py` 43→100%, `templates.py` 53→100%, `dlp_scanner.py` 71→81%; overall 84→86% |
| 16 | Implement `jackpot auth login` OAuth flow | (deferred to Month 2) | Out of P0e scope per the kickoff plan |
| 18 | Move Rule 18 violation in `ingest.py:288` | 083ec88 | `compute_scrub_status` now lives in `validator.py`; ingest router calls it as a one-liner |

## P0e additions beyond the Phase 22 action list

- **Critical Rule 56** (`d14f415`) — formalized "instances/ci/ ships
  with synthetic-only values, never real secrets/PII." Enforced at
  the CLI level (configure/secrets/bootstrap all refuse to overwrite
  the committed CI dir).
- **`schema/jackpot_scenarios/` registry** (`6b1cea2`) — new
  workspace-co-located package exposing the 7-scenario defaults.
  Used by `jackpot init` and importable from backend / CI for runtime
  scenario checks.
- **Compose profiles refactor** (`5dd3e25`) — `docker-compose.yml`
  per-service `profiles:` keys map cleanly to the 5 scenario
  compose-profile names; `required: false` on api→minio depends_on
  resolves cleanly for cloud profiles that don't activate minio.
- **`docs/install/quickstart.md`** (`5b526c6`) — the 10-minute
  fresh-clone-to-running-stack guide that anchors the new operator
  experience.

## Items remaining open

- **Action item 17** (build out 7 stub routers): Month 3 / Phase 24+
  scope. Now visibly stubbed via 501 (item 10), so the deferral is
  honest rather than silent.
- **Action item 19** (CI testcontainers DinD reliability): CI track,
  not part of P0e.
- **B-FED-1** (central-CA federation peer authentication): newly
  documented in the design lockdown; trigger is "federation
  membership exceeds 5 instances" or "first revocation event."

## Tests + coverage at P0e close

- 944 backend + schema + CLI tests passing
- 1 skipped (the long-standing pre-P0e skip)
- 86.20% overall coverage (workspace-wide)
- `jackpot/init/` package: 87% coverage
- Critical Rule 55: zero NEW violations introduced; 11 + inherited
  resolved; only historical-no-op SQL UPDATE strings in 3 rename
  migrations remain (functionally required, not violations)
