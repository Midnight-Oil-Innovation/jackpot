# CLAUDE.md — jackpot-backend

## Project: JACKPOT

Pathogen genomics platform for genomic epidemiology, bioinformatics,
and public health research.

**Project context (April 2026 pivot):** JACKPOT is an independent project under
`Midnight-Oil-Innovation/jackpot`, licensed AGPL-3.0. The platform is
multi-deployment-target by design — production code is operator-agnostic and
serves **7** install scenarios (A laptop, B single-org cloud, C multi-lab
agency, D hosted SaaS, E federation member, F CI test, **T Tribal-sovereignty
deployment** — variant of A or E with sovereignty-aware defaults: deletion-
on-request, no auto-publish, federation off-by-default, CARE Principles
compliance documented in
`governance/care-principles-and-tribal-data-sovereignty.md`). The
`jackpot init` CLI (coming in P0e) handles per-operator bootstrap. Phasing:
cleanup phases 6.1–11 → P0d (monorepo migration, in progress) →
P0e (install/CLI) → Phase 24.5 (architectural design lockdown) →
P0f (BYOP infrastructure) → P0b (Schema v5.0 with instances/tenants/
federated_peers + BYOP/eukaryotic schema) → P0c (multi-tenancy middleware
+ sovereignty deletion) → P1–P5.

---

## Autonomous Operating Mode

### Before Starting Any Work

1. Read `spec.md` — understand the goals and constraints for the current sprint
2. Read `todo.md` — find the next unchecked task
3. Re-read this file (`docs/CLAUDE.md`) — all 56 Critical Rules apply at all times
4. Confirm the baseline is stable: `uv run pytest tests/ schema/tests/ cli/tests/` from the workspace root — **≥970 tests passing, ≥80% coverage** (post-P0e baseline). The post-P0d 39% number we carried briefly was a pytest-cov misconfiguration (omit list wasn't reaching the report-time matcher); fixed by making `--cov-config=pyproject.toml` explicit in addopts — see `docs/learnings.md` "Coverage measurement bug" entry. P0e (`docs/architecture/jackpot-init-cli.md`) shipped `jackpot init` operator-bootstrap CLI plus 13 absorbed Phase 22 cleanup items; see `docs/review_log.md` "P0e closeout" section.

### Work Loop

- Take the **next unchecked item** from `todo.md`
- Cross-check it against `spec.md` before writing code
- Write the code — no placeholders, no `# TODO`, no `# ... rest of code here`
- Run the relevant tests: `uv run pytest tests/test_{module}.py -v`
- If tests pass: check the item off in `todo.md`, commit with `gac`, move to the next item
- If tests fail: fix and rerun — **never mark a task complete without passing tests**
- Every ~20 tasks: pause, review `spec.md` vs the current implementation for gaps,
  log findings to `docs/review_log.md`, and resolve all gaps before continuing

### Decision Rules

- **Never ask for confirmation** on anything resolvable by reading this file and running tests
- **Never lower the coverage threshold** — if a new file pulls coverage below 60%, add tests first
- **Never mark a task done** without `uv run pytest` showing it pass
- **Never write placeholder code** — every function must be fully implemented
- **Always use `uv run python` / `uv run python3`** — never bare `python` or `python3`; the shell aliases do not apply in Claude Code sessions
- When blocked on intent: check `spec.md`, then the relevant section of this file,
  then log the question to `docs/review_log.md` and continue with the next unblocked task
- For non-trivial architectural changes: write the plan to `docs/review_log.md` and
  wait for explicit "Go" before proceeding

### Commit Convention

Use the `gac` alias for every commit: `gac "type: description"`
NEVER use `git commit -m` directly — always `gac`.
If pre-commit hooks modify files and the commit fails, just run `gac` again.
The alias runs ruff fix + format before staging, so auto-fixed files are
always included in the same commit.
Valid types: `feat`, `fix`, `test`, `chore`, `refactor`
Examples: `gac "feat: organizations router — CRUD endpoints + tests"`
          `gac "fix: conftest alembic migration in test DB setup"`

---

## Learning and Explanation Style

When implementing new patterns, routers, or non-trivial logic:
- Briefly explain **why** a design decision was made, not just what was done
- For new architectural patterns (e.g. first time using a new dependency), generate
  a short ASCII diagram showing how the pieces connect
- After implementing a router, offer a one-paragraph plain-English summary of
  what it does and what could go wrong — suitable for a code reviewer unfamiliar
  with the codebase
- When fixing a bug, explain the root cause before showing the fix

Do NOT over-explain trivial changes. Reserve explanations for non-obvious decisions.

After completing any router session or significant fix, append a new entry to
`docs/learnings.md` using this format:

    ## [Session/feature name] — [date]
    **What was built:** one sentence
    **Key decisions:** bullet list of non-obvious choices and why
    **Watch out for:** gotchas, edge cases, constraints to remember
    **ASCII diagram:** (if a new pattern was introduced)


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
- MinIO (local) / GCS (production) — same boto3 code via
  `backend/storage/` (a multi-backend package since 2026-04-26).
  Transition = `STORAGE_ENDPOINT` env var: set (e.g.
  `http://minio:9000`) → S3-compatible mode; unset → GCS native.
- LinkML v4.4 schema: `schema/schema/jackpot_schema.yaml` (git submodule)
- Authentication: Google OAuth 2.0 + JWT httponly cookies (mock in local dev)
- Environment management: uv — never use pip directly
- Tests: pytest + testcontainers (real PostgreSQL container in tests)

---

## Directory Structure

The post-P0d monorepo lives at `~/projects/jackpot/`. It is the
canonical layout under `Midnight-Oil-Innovation/jackpot`. The previous
six-repo + git-submodule arrangement is gone; what used to be submodules
(`schema/`, `nf/`) is now subtree-merged at the top level.

```
~/projects/jackpot/                ← uv workspace root + git repository
├── backend/                       ← workspace member (jackpot-backend)
│   ├── pyproject.toml
│   ├── alembic.ini                Alembic config — script_location = db/migrations
│   ├── docker-compose.yml         Local dev stack (api + postgres + minio + ui)
│   ├── Dockerfile.api             API image
│   ├── Dockerfile.ui              Streamlit image
│   ├── backend/                   Python package — imported as `backend`
│   │   ├── main.py                  App entrypoint
│   │   ├── config.py                Settings; ENV=local or gcp
│   │   ├── permissions.py           PermissionGroups enum — DO NOT rename values
│   │   ├── database.py              Lazy engine; execute_query/execute_write/reset_engine
│   │   ├── validator.py             LinkML-based metadata validator — uses jackpot_schema.SCHEMA_YAML_PATH
│   │   ├── template_generator.py    CSV template generator — uses jackpot_schema.SCHEMA_JSON_PATH
│   │   ├── dlp_scanner.py           Cloud DLP metadata PII scanner — uses jackpot_schema.SCHEMA_JSON_PATH
│   │   ├── harmonizer.py            CSV column mapper — uses jackpot_schema.MAPPING_CONFIGS_DIR
│   │   ├── file_detector.py         NGS file pairing — only place for this logic
│   │   ├── audit.py / notifications.py / storage/ / responses.py / pagination.py
│   │   ├── epiweek.py / middleware.py / logging_config.py / cache.py / jobs.py / rate_limit.py
│   │   ├── pipeline_config.py / pipeline_results_loader.py / pipeline_schemas/
│   │   ├── models_generated.py    LinkML-generated; never edit manually (Critical Rule 20)
│   │   ├── auth/                  guards.py / dependencies.py / oauth.py
│   │   └── routers/               One file per feature area
│   ├── db/
│   │   ├── SCHEMA.sql             Read-only reference snapshot (27 tables)
│   │   └── migrations/            Alembic migration files — single source of truth for schema
│   ├── frontend/                  Streamlit researcher UI (canonical; jackpot-frontend repo retired in P0d)
│   ├── jackpot-course/            Operator-facing course content (engagement story)
│   ├── deploy/                    Backend-internal deployment configs (single-tenant AWS, etc.)
│   ├── pipelines/                 Backend-internal Nextflow config (ingest_gate.nf, nextflow.config)
│   ├── scripts/ / setup/
├── cli/                           ← workspace member (jackpot-cli)
│   ├── pyproject.toml
│   ├── jackpot/
│   │   ├── cli/                   Click commands (auth, init, samples, pipelines, upload)
│   │   ├── init/                  P0e bootstrap library: detector + writers + secrets + validator + github_vars
│   │   ├── core/                  client + exceptions
│   │   └── sdk/                   programmatic SDK (samples, pipelines, datasets, references, etc.)
│   └── tests/                     CLI's own tests
├── schema/                        ← workspace member (jackpot-schema)
│   ├── pyproject.toml
│   ├── jackpot_schema/            Helper module exposing SCHEMA_YAML_PATH, SCHEMA_JSON_PATH, MAPPING_CONFIGS_DIR
│   ├── jackpot_scenarios/         P0e: 7-scenario defaults registry + detector (Decision 8 co-located)
│   ├── schema/                    LinkML data — jackpot_schema.yaml/json + mapping_configs/
│   ├── course/                    Schema-blueprint course content (technical)
│   ├── setup/                     Schema-update scripts
│   └── tests/                     Schema-side tests (scenarios + detector)
├── pipelines/                     ← NOT a workspace member; member-local pyproject.toml + uv.lock
│   ├── pipelines/                 Nextflow workflows
│   ├── plugins/                   nf-jackpot plugin (Groovy)
│   ├── shared/                    Shared parser package
│   └── tests/                     Pipelines' own tests (run by .github/workflows/test.yml pipelines-test job)
├── deploy/                        Terraform + Helm + deploy scripts (no Python)
│   ├── terraform/                 Per-env tfvars + modules
│   ├── helm/jackpot-api/          Chart + values-staging.yaml
│   ├── scripts/                   bootstrap_project.sh, staging_smoke_test.sh
│   └── docs/                      Deploy-specific docs (production_runbook, env examples)
├── docs/                          Product + design docs (CLAUDE.md, learnings, design overviews)
│   ├── CLAUDE.md                  ← this file
│   ├── architecture/              P0e: jackpot-init-cli.md design lockdown
│   ├── install/                   P0e: quickstart.md (10-minute fresh-clone walk)
│   ├── deploy/stlt/               Five STLT-tier deploy guides (Phase 21.5)
│   ├── fhir-mapping.md            FHIR R5 translation map
│   └── jackpot_*_overview.md      Pathoplexus, CDC DMI, BYOP design documents
├── governance/                    8 charter + policy markdown files (P0d Phase 21.5)
├── instances/                     P0e: per-instance jackpot init output (gitignored except instances/ci/)
│   ├── .gitignore                 Whitelist: only ci/ + .gitignore are committed
│   └── ci/                        Critical Rule 56 — synthetic-only canonical CI fixture
├── tests/                         Backend's integration tests (Postgres testcontainer)
├── pyproject.toml                 Workspace root: uv.workspace.members + pytest + coverage + ruff config
├── pyrightconfig.json             Pyright config for the whole workspace
├── uv.lock                        Single workspace-wide lock
├── README.md / spec.md / todo.md / NOTICE / COPYRIGHT / LICENSE (AGPL-3.0)
└── .github/workflows/             test.yml + deploy-staging.yml + deploy-production.yml (production gated by GitHub environment Required Reviewers — Phase 22)
```

**Why the doubled `schema/schema/` path?** Historical: pre-P0d the
`jackpot-schema` repo was a submodule that mounted at `schema/`, and
the YAML lived at `schema/jackpot_schema.yaml` inside the submodule.
P0d subtree-merged the repo's full content into top-level `schema/`,
preserving the same on-disk path. Backend code never references this
path directly any more — it imports `from jackpot_schema import
SCHEMA_YAML_PATH` (and the matching SCHEMA_JSON_PATH /
MAPPING_CONFIGS_DIR) from the workspace member.

**Pre-requisite files — must exist before first router session:**
`backend/responses.py` and `backend/notifications.py` must be created
before implementing any router. See API Response Conventions and
Notification System sections for their exact interfaces.

---

## Current Baseline

- **970 tests passing, 1 skipped, 0 failed** (post-P0e); up from 944
  at P0e close + 26 from the ultrareview security follow-up.
- **Coverage: 86%+** workspace-wide. The pre-P0d 86.99% baseline was
  briefly under-reported as 39% due to a pytest-cov misconfiguration
  (omit list wasn't reaching the report-time matcher because
  `--cov-config=pyproject.toml` wasn't explicit in addopts). Fix landed
  post-Phase-22; see `docs/learnings.md` "Coverage measurement bug"
  entry for the full diagnosis. CI threshold is now 80%.
- Health check local: `curl http://localhost:8000/health` → `{"status":"ok","version":"5.0.0","project":"JACKPOT","database":"connected"}`
- Health check staging (via `kubectl port-forward`): identical envelope
- All 27 database tables loaded in PostgreSQL via Alembic; baseline
  migration `5adf11b77c19` seeds operator-agnostic Example Org/Lab/
  admin/Sequencing Lab/Reference Lab directly (P0e A.3); the 3 rename
  migrations after it are historical-no-op on fresh installs.
- The `jackpot init` CLI (P0e) bootstraps any of the 7 install
  scenarios from a fresh clone in under 10 minutes — see
  `docs/install/quickstart.md` and `docs/architecture/jackpot-init-cli.md`.
- **Branching workflow (formally adopted, May 2026):** long-lived
  `development` integration branch.
  - **Feature branches** are cut from `development` and PR back into
    `development`. Squash-merge, delete the branch.
  - **`development`** is the integration branch. Every feature lands
    here first. CI runs on every push and on every PR targeting
    `development`. `development` is allowed to be temporarily
    inconsistent between merges — that is the point of having it.
  - **`main`** represents released code. `development` → `main` is a
    deliberate release act — open a PR from `development` to `main`
    when a coherent batch of features is ready to ship, review the
    aggregate diff, squash- or merge-commit. CI runs on PRs to
    `main` as a safety net.
  - **`staging`** is push-triggered for the GCP staging deploy
    (`.github/workflows/deploy-staging.yml`). Promote
    `development` → `staging` to test the integrated stack in cloud,
    then `staging` → `main` (or `development` → `main` directly,
    if the staging slot has already validated that commit) for
    release.
  - **Production deploys** are `workflow_dispatch`-only with a
    Required-Reviewer gate (`deploy-production.yml`). The branch
    flow does not auto-deploy to production.
  - Never push directly to `main` or `staging`. Do not bypass the
    `development` integration step except for emergency fixes,
    which still require a PR (just retroactive).
  - **PR #1 (F-1, 2026-05-03)** and **PR #4 (this housekeeping
    batch)** were the last two PRs cut against `main` directly —
    historical artefacts of the interim period before this decision.
    All subsequent PRs target `development`.

Do not regress the test count or coverage without a deliberate reason.
Do not lower the 80% threshold without a documented architectural
decision.

---

## Critical Rules — Read Every Rule Before Making Any Change

**1. PermissionGroups enum values are sacred.**

DO NOT rename: `"Platform Admin"`, `"Lab Director"`, `"Lab Collaborator"`,
`"Lab Reader"`, `"Bioinformatics User"`, `"Data Analyst"`.

**2. All database schema changes go through Alembic.**
`db/SCHEMA.sql` is a read-only reference snapshot — never edit it; the
Alembic chain is the single source of truth (Critical Rule 52).
JACKPOT uses raw SQL, not SQLAlchemy ORM models, so `--autogenerate` will
fail with "no MetaData object". Always use the manual form instead:
Command: `uv run alembic revision -m "description"` (no --autogenerate)
Then hand-write the `upgrade()` and `downgrade()` functions in the generated file.

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

**8. `external_case_id` is required for HumanSample. It is NOT the same as `case_id`.**
`external_case_id` = operator-issued anonymized ID or exemption code.
`case_id` = generic non-host public health case identifier (CDC NEDSS etc.).

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

**Tier logic (corrected Session 3):**
- SUBMITTABLE gates on field presence only — no date precision constraint.
  NCBI BioSample and GISAID both accept YYYY, YYYY-MM, and YYYY-MM-DD.
- ANALYZABLE requires month-or-better date precision for time-series.
- Tiers are partially orthogonal: a sample can be SUBMITTABLE but not
  ANALYZABLE (year-only date with all other fields present).
- host_age and host_sex are conditional on source_type == "Human".
  Non-human source types can reach SUBMITTABLE without them.

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
(2) Apply the boolean keyword patch AND trailing newline fix immediately after:

```python
from pathlib import Path
content = Path('backend/models_generated.py').read_text()
# Boolean keyword patch — gen-pydantic emits True/False as enum member names
# which are Python keywords and cause SyntaxError on import
content = content.replace('\n    True = "True"',   '\n    true = "True"')
content = content.replace('\n    False = "False"', '\n    false = "False"')
# Trailing newline — pre-commit end-of-file-fixer requires it
content = content.rstrip('\n') + '\n'
Path('backend/models_generated.py').write_text(content)
print('Patched.')
```

Both fixes are applied automatically by `schema_update.py`. When running
manually, always apply both in the same step — never commit
`models_generated.py` without the patch applied or the pre-commit hooks
will modify the file and block the commit.

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

**35. Never disable PITR on the Cloud SQL instance.**
Point-in-time recovery is the primary defense against bad migrations.
It must always be enabled. If a migration is about to run that you're
uncertain about, note the current timestamp before running it so you
know exactly where to restore to if needed.

**36. After any database restore, always run `uv run alembic upgrade head`.**
A restored database may be behind the current schema version. Never
operate JACKPOT against a database that hasn't been brought to the current
migration head after a restore. Check with `uv run alembic current`.

**37. Never manually configure GCS bucket settings in the GCP console.**
All bucket configuration (versioning, lifecycle rules, Object Lock,
IAM) is defined in jackpot-iac/terraform/gcs.tf. Manual console changes
will be overwritten on the next `terraform apply` and create drift between
the IaC and the actual state. Make changes in Terraform, apply, commit.

**38. Never enable versioning on jackpot-work bucket.**
The Nextflow work directory bucket has a 90-day lifecycle rule that
deletes stale task caches. Versioning would conflict with this rule and
accumulate unbounded storage costs. jackpot-work is intentionally
ephemeral — pipelines are restartable via -resume.

**39. All PATCH endpoints use `model_dump(exclude_none=True)` for partial updates.**
Build a dict of only the supplied fields using Pydantic's model_dump with
exclude_none=True. Construct the UPDATE statement dynamically from that dict.
Never UPDATE all columns unconditionally — only update what was supplied.
Example pattern:
```python
updates = payload.model_dump(exclude_none=True)
if not updates:
    raise HTTPException(status_code=400, detail="No fields to update.")
set_clause = ", ".join(f"{k} = :{k}" for k in updates)
updates["id"] = resource_id
row = execute_write(f"UPDATE table SET {set_clause} WHERE id = :id RETURNING *", updates, conn)
```

**40. All INSERT and UPDATE statements use RETURNING to get back the row.**
Never do a separate SELECT after a write. Use PostgreSQL's RETURNING clause
in execute_write() calls to return the created or updated row directly.
Always use `RETURNING *` unless only specific columns are needed.
Example: `INSERT INTO samples (...) VALUES (...) RETURNING *`
This applies to every router — never write a row and then SELECT it back.

**41. Routers use `get_db_dep()` with `Depends()` for database access.**
Import `get_db_dep` from `backend.database` and `Depends` from `fastapi`.
Pass the session as `conn` to `execute_write()`, `log_audit()`, and
`create_notification()` so all writes share one transaction — if any
write fails, all roll back together.
```python
from fastapi import APIRouter, Depends
from backend.database import execute_query, execute_write, get_db_dep
from backend.audit import log_audit, AuditActions
from backend.responses import success, error

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])

@router.post("/", status_code=201)
def create_org(payload: OrgCreate, db=Depends(get_db_dep)):
    row = execute_write(
        "INSERT INTO organizations (display_name) VALUES (:name) RETURNING *",
        {"name": payload.display_name},
        conn=db,
    )
    log_audit(
        action=AuditActions.CREATE_ORG,
        actor_id=current_user["id"],
        resource_type="organization",
        resource_id=str(row[0]["id"]),
        before=None,
        after=row[0],
        metadata=None,
        db_conn=db,
    )
    return success(data=row[0], status_code=201)
```

**42. Templates are generated artifacts — never hand-maintained.**
CSV/XLSX templates are generated from the LinkML JSON Schema by
`backend/template_generator.py`. Templates are produced along two axes:
source_type (12 types) × tier (PRELIMINARY/ANALYZABLE/SUBMITTABLE), with
an optional metagenomics overlay. The template endpoints are public (no
auth required). Never create template files manually in the repository.
If a field is missing from a template, fix the schema — the generator
will pick it up automatically.

**43. DLP metadata scan runs on all free-text fields before DB commit.**
`backend/dlp_scanner.py` scans every string field not backed by an enum
for PII (names, emails, SSNs, MRNs, phone numbers) via GCP Cloud DLP API.
`pii_scan_status` works like `scrub_status`: FLAGGED samples are stored
but blocked from queries, pipelines, and export until a Lab Director
overrides or the submitter fixes the flagged fields. In local dev,
`DLP_ENABLED=false` (default) bypasses the scan and returns CLEAN.
Exception: `pi_name` is excluded from the PERSON_NAME check because
it is expected to contain a name.

**44. Alembic must reach head from an empty database.**
The full database schema must be reachable via `alembic upgrade head`
from a completely empty PostgreSQL instance. No migration in the chain
may assume the existence of tables created outside the Alembic graph.

Q-9 closed this with the baseline migration `5adf11b77c19` (which
embeds the v4.1 DDL formerly in `db/init.sql`). The local Compose
postgres no longer mounts an init script, and the api container runs
`alembic upgrade head` on startup via `backend/entrypoint.sh`.

**How to enforce.** When adding any Alembic migration, test it locally
against a fresh empty database:

```bash
docker compose down -v && docker compose up -d
docker compose logs -f api  # expect "alembic upgrade head" then uvicorn
curl http://localhost:8000/health
```

If this fails with "relation does not exist" or similar, the chain
depends on pre-existing state. Fix by either adding the missing DDL
to the baseline migration (only when correcting a bug — never to
sneak in schema changes), or by making the dependent migration create
what it needs.

See also Critical Rule 52.

**45. `list[str]` Settings fields require a multi-form validator.**
When declaring a `list[str]` or similar field in `backend/config.py`'s
`Settings` class, always pair it with a
`field_validator(mode="before")` that accepts (a) a real list, (b) a
JSON-array string, (c) a comma-separated string, and (d) an empty
string. Use `Annotated[list[str], NoDecode]` to disable pydantic's
eager JSON parsing.

**The correct pattern** (applied to `cors_origins` in Q-10; see
`backend/config.py` for the live reference):

```python
from typing import Annotated
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode

class Settings(BaseSettings):
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:8501",
        "http://localhost:4200",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v):
        import json
        if v is None or v == "":
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):
                try:
                    return json.loads(s)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"cors_origins looks like JSON but won't parse: {e}"
                    ) from e
            return [item.strip() for item in s.split(",") if item.strip()]
        raise ValueError(f"cors_origins must be str or list, got {type(v).__name__}")
```

See also Critical Rule 53.

**46. `nf/` submodule is runtime-only — backend never imports across the boundary.**
The `jackpot-nf` submodule at `nf/` ships Nextflow processes, parsers,
plugins, and result schemas that run inside GCP Batch containers. The
backend MUST NOT import any module from `nf/` at Python import time.
Anything the backend genuinely needs from nf is vendored into the
backend package and kept in sync via explicit code review (Q-11 closed
this for `RESULT_SCHEMAS` — see `backend/pipeline_schemas/`).

`backend/routers/pipelines.py` imports `RESULT_SCHEMAS` from
`backend.pipeline_schemas`, never from `nf/shared/schemas`. The
`Dockerfile.api` does NOT `COPY nf/`, and `.dockerignore` excludes
`nf/` from the build context.

**Required in CI checkout:** `submodules: recursive` on
`actions/checkout@v4` is still needed for the `schema` submodule (the
LinkML source) — but `nf/` is no longer required for the backend
build. CI workflows that only test/build the backend can skip `nf/`.

**Required in git config:** `.gitmodules` for `jackpot-backend` must
reference `git@github.com:<your-org>/jackpot-nf.git`, never a local
filesystem path. Same applies to the `schema` submodule.

See also Critical Rule 54.

**47. Never paste across secret types.**
GitHub Actions secrets, GCP Secret Manager entries, and Google OAuth
client credentials are visually similar strings but completely
different secret types. Before `gh secret set` or
`gcloud secrets versions add`, cross-check the prefix of the value
against the expected type for the secret.

**Known prefixes:**

| Prefix | Secret type |
|--------|-------------|
| `ghp_` | GitHub classic PAT |
| `github_pat_` | GitHub fine-grained PAT |
| `GOCSPX-` | Google OAuth client secret |
| `AIza` | Google API key |
| `sk-` | OpenAI API key (if ever used) |
| 40-char hex | Generic session / secret key |

Session 5 had `CROSS_REPO_PAT` (which must be a GitHub PAT) silently
overwritten with a Google OAuth client secret during an unrelated
Secret Manager edit. The workflow kept failing with 401s for hours
because every other system assumed the secret was valid.

**Verification step** — add as a temporary debug step when a
secret-based auth fails in CI:

```yaml
- name: Debug PAT
  env:
    GH_PAT: ${{ secrets.CROSS_REPO_PAT }}
  run: |
    echo "PAT length: ${#GH_PAT}"
    echo "PAT prefix: ${GH_PAT:0:8}..."
```

**48. `yaml.safe_load` is not a valid CI YAML linter.**
Do not trust `python3 -c "import yaml; yaml.safe_load(...)"` alone to
verify a GitHub Actions workflow file is valid. PyYAML accepts duplicate
mapping keys silently (last-wins). GitHub's own workflow validator
rejects duplicate keys, so a file that parses locally will still fail
at 0s elapsed in Actions.

Session 5 had a workflow edit that produced two adjacent
`submodules: recursive` lines. PyYAML reported success. GitHub rejected
it. Two wasted push attempts.

**Better verification:**

1. Read the diff carefully before committing. Duplicate keys are
   visually obvious if you're looking.
2. After pushing, watch `gh run list` for 0s-elapsed failures — that
   pattern almost always means the workflow file itself is invalid to
   Actions.
3. For structural confidence, check that every `with:` block has
   exactly one entry per key.

**49. Helm `--wait` timeouts leave the release in `pending-*`.**
Deploys using `helm upgrade --wait --timeout <N>m` may leave the release
stuck at `pending-upgrade` status on timeout. Before the next deploy,
check `helm history <release>` and roll back to the last `deployed`
revision if the most recent is `pending-*` or `failed`.

Helm doesn't auto-rollback on timeout — it considers the deploy
incomplete. Subsequent upgrade attempts silently no-op because the
release is mid-transaction.

**Recovery:**

```bash
helm -n <ns> history <release>    # note the last "deployed" revision
helm -n <ns> rollback <release> <rev>
helm -n <ns> status <release>     # verify STATUS: deployed
```

**Related backlog:** Q-15 in `todo.md` — add `--atomic` to the workflow,
or a cleanup step that auto-rolls-back before each upgrade attempt.

**50. Streamlit `frontend` package must be importable from `/app`.**
The Streamlit UI lives in `jackpot-backend/frontend/` and uses absolute
imports like `from frontend.lib.session import current_user`. Streamlit
sets `sys.path[0]` to the script's directory — i.e. `/app/frontend/`
inside the container — which does NOT put `frontend` itself on the path.

**The container layout must be:**

```
/app/
├── frontend/
│   ├── __init__.py
│   ├── app.py
│   ├── lib/
│   ├── pages/
│   └── components/
└── (other source dirs)
```

**Dockerfile.ui** must preserve the package name:

```dockerfile
COPY frontend/ ./frontend/               # NOT: COPY frontend/ .
CMD ["/opt/venv/bin/streamlit", "run", "frontend/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
```

**docker-compose.yml `ui` service** must mount the package correctly
and set PYTHONPATH:

```yaml
ui:
  build:
    context: .
    dockerfile: Dockerfile.ui
  environment:
    API_BASE_URL:    http://api:8000
    ENV:             local
    MOCK_USER_EMAIL: admin@example.org
    PYTHONPATH:      /app                  # REQUIRED
  volumes:
    - ./frontend:/app/frontend             # NOT: ./frontend:/app
    - ./schema:/app/schema
```

Do **not** add a `command:` directive to the compose service — it will
override the image's CMD. Let the Dockerfile's CMD drive.

**`MOCK_USER_EMAIL` must be set on BOTH the `ui` and `api` services.**
The UI client ships `X-Mock-User-Email` as a parity header, but the
actual identity lookup happens server-side via
`os.getenv("MOCK_USER_EMAIL")` on the API container.

Session 5's UI debugging resolved six distinct bugs that all trace back
to violations of this rule — Dockerfile flattening the layout, compose
mount overriding the image layout, explicit `command:` overriding the
CMD, missing PYTHONPATH, `ApiClient` reading only `JACKPOT_API_URL`
(not `API_BASE_URL`), and mismatched `MOCK_USER_EMAIL` between
services. `frontend/lib/api.py`'s `ApiClient` now reads both env var
names as fallbacks; keep that behavior.

Rule 51 — Pyright LSP runs live during Claude Code sessions.
Configuration lives at ./pyrightconfig.json. Excludes
models_generated.py (generator output, hand-patched per Rule 20) and
generated migration files. If Pyright flags an error on a PR, fix it
before merging — don't # type: ignore without explaining why in the
comment.

**52. The full schema must be reachable via `alembic upgrade head` from
an empty database.** Never depend on `db/SCHEMA.sql` (or any other SQL
file) running before Alembic in any deployment target. Alembic is the
single source of truth.

`db/SCHEMA.sql` is a regenerable reference snapshot for humans
reviewing the schema; it has no role at runtime. The baseline
migration `5adf11b77c19` is what builds an empty DB. See Rule 44 for
the empty-DB upgrade test.

**53. List-typed Settings fields need multi-form validators.**

Any list-typed Settings field that may be populated from an env var
must use `Annotated[list[*], NoDecode]` plus a
`@field_validator(mode="before")` that accepts JSON arrays,
comma-separated strings, empty strings, and real lists.
Pydantic-settings v2 unconditionally `json.loads()` list fields
otherwise, which is what crashed the staging Alembic Job in Session 5.

See Rule 45 for the worked code template.

**54. Backend code MUST NOT import from sibling repos via sys.path manipulation.**

Anything the backend needs at import time must live inside the
`backend/` package. Cross-repo Python (e.g. nf-iridanext result
schemas) is vendored into `backend/` and kept in sync via explicit
code review, not via import-time path tricks. Any tool that
evaluates backend code without the sibling repo present (linting
in CI, tests in sandboxes, backend-only docker builds) must work.

**55. Production code is operator-agnostic — no operator-specific values in source.**

JACKPOT is multi-deployment-target (scenarios A–F). Production code MUST NOT
hardcode any of these:

- Organization names ("Linux Prophet", "Midnight-Oil-Innovation", any specific lab name)
- Email domains, contact addresses, or admin handles
- Jurisdiction-specific reportable-organism lists (the 62-value seed set is a default reference, not a constant)
- GCP project IDs, region names, bucket names, or any infrastructure identifier
- Globus endpoint IDs, NCBI submitter accounts, GISAID credentials
- File-naming conventions specific to one sequencing lab

Anything in the above list comes from one of three runtime sources:

1. **Environment variables** (set per-instance, e.g. `JACKPOT_ORG_NAME`, `GCP_PROJECT_ID`)
2. **Database tables** (seeded at install time by `jackpot init`, mutable by Platform Admins via admin UI — `organizations`, `sequencing_labs`, `reportable_organisms`, `lab_pipelines`, etc.)
3. **Operator config files** (per-deployment YAML/JSON loaded at startup, e.g. `config/operator.yaml`, never committed to the source tree of the operator-agnostic monorepo)

If you find yourself about to write `if org_name == "Linux Prophet" or `BUCKET = "jackpot-raw-prod-1234"` in production source — STOP. That value belongs in env vars, the database, or operator config. Tests can use fixtures with operator-shaped values, but the values themselves stay in the test fixtures, not in production modules.

The `jackpot init` CLI (P0e) is the only place where operator-specific values are *learned* — the CLI prompts for them and writes them into env vars, the database, and operator config. Production code reads from those three sources and stays clean.

**56. `instances/ci/` is the only committed instance directory; it MUST contain zero secrets, zero PII, and zero real operator-specific values.** All other `instances/*/` paths are gitignored. The `instances/ci/` directory exists as the committed Scenario F (CI test) artifact set: pinned-forever values that produce reproducible green CI runs. It uses synthetic operator names (`CI Test Organization`, `ci@example.org`), `auth_method = "mock"` in jackpot.toml (no real OAuth client), filesystem storage (`STORAGE_ENDPOINT` empty in `.env.local`), and a randomly-generated-but-fixed JWT signing key (committed; CI is the only scenario where a known-fixed key is acceptable because there's no real auth to compromise). No GCS, no GISAID, no NCBI submission, no federation. The `jackpot init` CLI REFUSES to overwrite `instances/ci/` files; developers reproducing CI locally use `jackpot init --scenario F --instance-name ci-local` (or any name other than `ci`) and `instances/ci-local/` is gitignored.

**57. JACKPOT does not copy data on ingest. Default storage_state is `EXTERNAL`.**

Pointing JACKPOT at a file path or URI **registers** the file; it does
not copy. The `file_references` row gets `storage_state='EXTERNAL'`,
the original file stays where the operator put it, and JACKPOT reads
in place at pipeline time. This is the inversion of the historical
"ingest = copy" model and is the only way the platform stays viable
on shared lab/cluster filesystems where a 4× duplication of FASTQ
data would exhaust storage.

Copies happen in exactly four cases, all explicit:

1. The user sets `storage_intent='MANAGED'` (or `'MIRRORED'`) at ingest.
2. A pipeline produces output files — outputs default to `MANAGED`
   because JACKPOT owns the lifecycle of derived data.
3. The user runs `jackpot files promote --to managed` (or
   `--to mirrored`) on an existing `file_reference`.
4. A pipeline run stages an input across a compute boundary
   (e.g., on-prem to GCP Batch). Staging produces a `STAGED`
   `file_reference` that is auto-cleaned after run completion +
   retention window.

The ingest UI must surface storage state plainly. Never default to
copying "for safety" — that creates exactly the duplication problem
this rule prevents. If the user wants JACKPOT to take ownership, they
say so.

**Related schema:** `file_references.storage_state`, the
`FileStorageState` enum, the `sample_files` association table.

**Related backlog:** Phase P0f in `todo.md`, end-to-end test
`tests/e2e/test_no_copy_on_ingest.py` verifying that running a
pipeline against an `EXTERNAL` input leaves the input's
`storage_state` unchanged.

---

**58. file_references is the dedup primitive. content_hash, not URI, is the logical key.**

A `file_reference` row is uniquely identified by `content_hash`
(SHA-256 hex). Multiple URIs may point to the same `file_reference`
via the `alternate_uris` array. Multiple samples may reference the
same `file_reference` via the `sample_files` association table. The
common cases:

- Two labs both register data from `SRR12345` — one `file_reference`,
  two `sample_files` rows linking it to two different samples.
- A control sample is reused across runs — one `file_reference`,
  N `sample_files` rows.
- The same FASTQ exists at `/srv/seq/runs/...` and at
  `gs://lab-archive/...` — one `file_reference`, two URIs.

When registering a new file, always check for an existing
`file_reference` with matching cheap fingerprint
(`size_bytes` + `head64k_hash` + `tail64k_hash`) before INSERTing a
new row. The cheap fingerprint is computed in
`backend/file_fingerprint.py` from the first 64 KB and last 64 KB of
the file — no full read at ingest time. If the fingerprint matches,
link to the existing row and append the new URI to `alternate_uris`
if different. The full SHA-256 is computed lazily by the
`compute_full_content_hash` APScheduler job and used to reconcile
fingerprint collisions (vanishingly rare for distinct content).

The deprecated `samples.fastq_r1_uri` / `fastq_r2_uri` /
`long_read_uri` / `assembly_uri` columns are **not** the source of
truth — they exist for one release for backward compatibility and
will be removed. New code reads files via `sample_files` joined to
`file_references`.

**Related schema:** `file_references` table, indexes
`file_references_content_hash_uniq` and
`file_references_fingerprint_idx`.

---

**59. Pipeline executor selection is per-run, not per-deployment.**

The same JACKPOT instance can submit one run to local Nextflow, the
next to a Slurm cluster, the next to GCP Batch — using the same
pipeline definitions in the zoo. This is the architectural unlock
that makes scenarios A through G feasible from a single codebase.

Selection happens via `execution_profiles`. Profiles are configured
by the operator at deployment time (`jackpot init`) or later
(`jackpot profiles add`). Each profile carries an `executor_type`
(`LOCAL`, `SLURM`, `PBS`, `LSF`, `GCP_BATCH`, `AWS_BATCH`,
`KUBERNETES`), a `container_engine` (`DOCKER`, `APPTAINER`,
`SINGULARITY`, `NONE`), a `work_dir`, and executor-specific
overrides in `config_overrides` JSONB.

**Resolution at launch time:**

1. Explicit `profile_name` in the launch request body wins.
2. Otherwise, the pipeline's first matching default profile by
   `pipeline_default_profile.priority` (lowest priority number wins).
3. Otherwise, the deployment's `is_default=true` profile.
4. Otherwise, fail with `400 NO_PROFILE_AVAILABLE` listing the
   configured profiles.

If `profile_name` is provided but the profile is missing or
`active=false`, fail with `400 PROFILE_NOT_FOUND` listing the
available names.

The launch endpoint generates a `nextflow.config` per run from the
chosen profile via `backend/pipeline_config/profile_renderer.py`
(extends Critical Rule 26). The generated config is stored at
`<work_dir>/runs/<run_id>/jackpot_run.config` for audit and
reproducibility. Quick-fast pipelines (file_detector smoke runs, DLP
scans, validation) default to the `LOCAL` profile during seeding —
they always run on the API server. Heavy pipelines (PHoeNIx, MIRA-NF,
MycoSNP-NF, aquascope) have no default seeded; the operator picks at
launch or sets one.

**Related schema:** `execution_profiles` table,
`pipeline_default_profile` association table.

**Related backlog:** Phase P0g in `todo.md`.

---

**60. Cluster-bound pipeline runs must work whether or not compute nodes can reach the API.**

Many HPC clusters block outbound HTTPS from compute nodes. This
breaks Nextflow's standard weblog mechanism, which expects to POST
trace events to a URL during execution. JACKPOT handles this by
treating the HTTP weblog receiver as **best-effort** and providing a
log poller as the source of truth when reachability is uncertain.

**Two paths, both supported:**

- **HTTP weblog (default):** compute nodes POST to
  `/api/v1/pipelines/events`. The receiver in `backend/routers/pipelines.py`
  **never raises on errors** — Nextflow does not retry weblog
  delivery. Receiver tolerates duplicate events idempotently on
  `(run_id, task_id, status)`.
- **Log poller (fallback):** when the launch profile has
  `weblog_reachable=false`, the launch endpoint omits the weblog
  directive from the generated `nextflow.config` and instead starts
  an APScheduler job in `backend/pipelines/log_poller.py`. The poller
  tails `<work_dir>/runs/<run_id>/.nextflow.log` over the shared
  filesystem every 30 seconds, parses Nextflow's known event
  patterns, and emits synthetic events to the same handler the HTTP
  receiver uses.

The two paths can coexist for redundancy without duplicating writes,
because the receiver dedups on the `(run_id, task_id, status)`
tuple. Operators in scenario C (university research-computing
hosted) typically run with `weblog_reachable=false` and rely solely
on the poller; scenario B operators with their own server typically
run with `weblog_reachable=true`.

**For multi-tenant scenario C deployments**, per-launch
`launch_account` overrides (which Slurm account to charge) must be
validated against the user's lab memberships via the P0c
multi-tenancy guard. Never trust `launch_account` from the request
body alone.

**Related schema:** `execution_profiles.config_overrides`
(`weblog_reachable` boolean for Slurm/PBS/LSF profiles).

**Related backlog:** Phase P0h in `todo.md`,
`backend/pipelines/log_poller.py`, `backend/pipelines/cluster_health.py`.

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

INSERT INTO lab_membership (user_id, lab_id, permission_group_id, is_lab_director)
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

Revert by changing `MOCK_USER_EMAIL` back to `admin@example.org`
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
uv run alembic revision -m "add_new_column"  # no --autogenerate — JACKPOT uses raw SQL
psql postgresql://jackpot:jackpot@localhost:5432/jackpot_db  # pragma: allowlist secret
psql postgresql://jackpot:jackpot@localhost:5432/jackpot_db -c "\dt"  # pragma: allowlist secret

# Schema (run from workspace root; codegen deps live in schema's
# optional `codegen` extra — install with `uv sync --extra codegen`).
uv sync --extra codegen
uv run gen-pydantic --pydantic-version 2 schema/schema/jackpot_schema.yaml > backend/backend/models_generated.py
# Then apply boolean keyword patch — see Critical Rule 20
uv run gen-json-schema schema/schema/jackpot_schema.yaml > schema/schema/jackpot_schema.json
uv run python -c "import yaml; yaml.safe_load(open('schema/schema/jackpot_schema.yaml'))"

# Docker (from backend/ — that's where docker-compose.yml lives)
cd backend && docker compose up -d
cd backend && docker compose up -d api    # restart API only (preserves DB data)
cd backend && docker compose ps
cd backend && docker compose logs -f api
cd backend && docker compose down
cd backend && docker compose down -v      # also deletes data volumes (full reset)
curl http://localhost:8000/health

# Schema updates (post-P0d: schema/ is a workspace member, not a
# submodule — `git submodule update` no longer applies). Edit
# schema/schema/jackpot_schema.yaml directly, regenerate the JSON form
# and the Pydantic models per the commands above, then commit.

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

## APGAP Compatibility (historical)

> **Note:** APGAP-compatibility is no longer a hard constraint. JACKPOT is now an independent project, not specifically the APGAP successor. The compatibility points below are preserved for any in-flight migration of an APGAP deployment to JACKPOT, and because the org/lab/project/user hierarchy and PermissionGroups enum values designed for APGAP-compat happen to be solid choices in their own right. New deployments don't need to satisfy any of these.

- Organization → Lab → Project → User hierarchy is identical
- PermissionGroups enum string values match APGAP exactly (also enforced by Critical Rule 1 for backwards compatibility on existing deployments)
- `is_lab_director=TRUE` on `lab_membership` = Lab Director
- Projects preserve all Seqera fields (`workspace_id`, `compute_env_id`, `credentials_id`)
- Migration script: `scripts/migrate_from_apgap.py` (only relevant for APGAP→JACKPOT migration deployments)

---

## OrganismNameEnum (62 values in default reference set)

The default 62-value enum was originally derived from a specific jurisdiction's mandatory reportable communicable diseases list and includes one-Health additions (`Coccidioides immitis`, `Coccidioides posadasii` for Valley fever, `metagenome` for metagenomic samples, `novel pathogen` for emerging/exotic disease). All values use NCBI Taxonomy names for BioSample/SRA/GenBank/GISAID compatibility.

**Operator-agnostic from P0e onward:** the seed enum values become an operator-configurable list at install time (`jackpot init`). Production code references the runtime enum from the database (table seeded at install) — never a hardcoded Python list. Platform Admins add new values via the admin UI; never hardcode new organisms in source. See Rule 55.

---

## Testing Philosophy

**Current baseline:** 80% coverage minimum enforced in CI
(`pytest --cov-fail-under=80`, set in workspace `pyproject.toml`),
real measured value 84%. The "39% post-P0d coverage drop" we
quoted for several phases was a measurement bug — pytest-cov
needs `--cov-config=pyproject.toml` explicit in addopts to load
the omit list (it does NOT auto-discover the
`[tool.coverage.run]` table the way the coverage CLI does).
Real gaps to close (still tracked as action item 15 in
`docs/review_log.md` but smaller than thought):
`harmonizer.py` 0% (no tests), `routers/gisaid.py` 43%,
`routers/templates.py` 53%, `dlp_scanner.py` 71%.
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

## Local Development Stack — What Runs Where

JACKPOT uses a **hybrid local dev stack**. Docker Compose is the primary
environment for all Month 1 and Month 2 backend/frontend work. Minikube
is added specifically for JupyterHub workspace testing in Month 2.
Never migrate the full stack to minikube.

### Docker Compose (primary — always running)

```
api               FastAPI API          localhost:8000
ui                Streamlit UI         localhost:8501   (source: jackpot-backend/frontend/)
postgres          PostgreSQL           localhost:5432
minio             Object storage       localhost:9000 (API), 9001 (console)
```

Note: the UI source lives inside `jackpot-backend/frontend/`, not in the
separate `jackpot-frontend` repo. That repo is a vestigial stub
(`print("Hello from jackpot-frontend!")`) kept only as a placeholder for
the Month 3 React migration — retiring it is on the Month 3 backlog.

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

## Disaster Recovery and Backup Architecture

This section documents the backup strategy for every stateful component.
Understanding this is important when writing migrations, storage operations,
or anything that touches the database or GCS buckets.

### Cloud SQL (operational database) — most critical

Three layers of protection, all defined in jackpot-iac/terraform/cloudsql.tf:

**Automated daily backups** — full backup once per day during 2–4am AZ
maintenance window. Stored in GCS. 30-day retention. Costs a few dollars
per month at JACKPOT's scale.

**Point-in-time recovery (PITR)** — continuous transaction log shipping
to GCS. Enables recovery to any second within the last 7 days. This is
the most operationally useful feature. If a bad migration runs at 2pm,
restore to 1:59pm. Always enabled. Flag: --enable-point-in-time-recovery.

**Weekly SQL dump export** — Cloud Scheduler triggers a full SQL export
to gs://jackpot-backups/ every Sunday night. Independent recovery path
if Cloud SQL's built-in backup mechanism fails. jackpot-backups bucket
has Object Lock (WORM) — exports cannot be deleted or modified before
their 90-day retention expires. Protects against accidental deletion and
satisfies public health audit requirements.

**Cross-region replica** — deferred from prototype. Add when platform has
real production users. Enables promotion to primary if us-central1 has
an outage.

### GCS buckets — per-bucket policy

| Bucket | Versioning | Region | Object Lock | Notes |
|---|---|---|---|---|
| `jackpot-sequences` | Enabled | Standard | No | Irreplaceable raw FASTQs. Versioning allows recovery from accidental deletion. |
| `jackpot-references` | Enabled | Standard | No | Reference genomes. Write-once in practice. |
| `jackpot-results` | No | Standard | No | Pipeline outputs. Regenerable by re-running pipelines. |
| `jackpot-staging` | No | Standard | No | Temporary — files move to sequences after scrubbing. |
| `jackpot-work` | No | Standard | No | Nextflow work dirs. 90-day lifecycle rule. Versioning would fight lifecycle rule. |
| `jackpot-backups` | No | Different region | Yes (WORM) | Weekly SQL exports. Object Lock prevents tampering. 90-day lifecycle. |

**Never enable versioning on jackpot-work.** The combination of Nextflow
work directories (many large files) and versioning would accumulate
enormous storage costs and conflict with the 90-day lifecycle rule.

### GKE workspace PVCs (JupyterHub user data)

Each researcher's persistent volume claim contains notebooks, local data,
and conda environments. Protected via GCP Compute Engine scheduled
snapshots:

- Daily snapshot of each active workspace PVC
- 14-day snapshot retention
- Defined in jackpot-iac/terraform/snapshots.tf
- Idle PVCs (culled pods): snapshot on demand before deletion

If a researcher accidentally deletes a notebook: restore from the previous
day's PVC snapshot. Expected recovery time: 15 minutes.

### GKE cluster state

Not backed up separately — the git repository IS the backup. All cluster
state (Deployments, ConfigMaps, Services, HPA configs, CronJobs) is
defined in jackpot-iac Terraform and Kubernetes manifests. If the cluster
is destroyed, `terraform apply` + `kubectl apply` rebuild it from scratch.
Never configure cluster resources manually in the GCP console — always
use IaC so the git history is the authoritative record.

### Alembic migration history

Backed up by git. If the database is restored from a backup, run
`uv run alembic upgrade head` to bring the schema current. Never skip
this step after a database restore.

### Disaster recovery runbook (jackpot-iac/docs/disaster-recovery.md)

Five documented scenarios:

**Scenario 1 — Accidental row deletion (most common)**
Recovery: PITR or restore specific rows from daily backup.
GCS files: recover from object versioning on jackpot-sequences.
Expected RTO: 30 minutes.

**Scenario 2 — Bad Alembic migration corrupts data**
Recovery: PITR to the timestamp immediately before the migration ran.
After restore: fix the migration, test in dev, re-apply.
Expected RTO: 1–2 hours.

**Scenario 3 — Cloud SQL instance failure**
Recovery: restore from automated daily backup to new Cloud SQL instance.
Update DB_URL in GKE secrets. Redeploy API pods.
Expected RTO: 2–4 hours.

**Scenario 4 — Regional GCP outage (us-central1 unavailable)**
Recovery: promote Cloud SQL replica to primary (when replica is enabled).
Update DNS. Redeploy GKE cluster from jackpot-iac in backup region.
Expected RTO: 4–8 hours. Not fully automated in prototype.

**Scenario 5 — GCS bucket data loss**
Recovery: restore from object versioning (jackpot-sequences, jackpot-references)
or from weekly SQL export in jackpot-backups.
Expected RTO: varies by data volume.

### New IaC components (jackpot-iac/terraform/)

| File | What it defines |
|---|---|
| `cloudsql.tf` | Daily backups, PITR, 30-day retention, weekly export scheduler |
| `gcs.tf` | Versioning on sequences/references, Object Lock on backups, lifecycle rules |
| `snapshots.tf` | GKE PVC daily snapshot schedule, 14-day retention |
| `budgets.tf` | Already planned — budget alerts at 50%/80%/100% |

---

## Frontend Architecture — Streamlit Now, React Later

JACKPOT's frontend runs on **Streamlit** for the prototype (Month 1–2).
This is the right choice for a solo Python developer on a 3-month timeline.
However, Streamlit has known limitations that will matter at production
scale. Understanding this informs how to structure the Streamlit code now
so that a future migration is as painless as possible.

### Why Streamlit works for the prototype

- No JavaScript/HTML/CSS required — iterate on UI in Python
- Fast gap between idea and working screen
- Backend and UI can be developed in the same session

### When Streamlit starts to hurt

The signal to begin the React migration is when any of these are true:
- Writing more `st.components.v1.html()` than `st.dataframe()`
- Multi-step ingest workflows feel fragile due to `st.session_state` complexity
- Pipeline monitoring real-time updates feel choppy with polling
- Notification badges across sessions require external pub/sub
- Bulk select and complex table interactions require injected HTML

### How to structure Streamlit code for future migration

Keep `jackpot-backend/frontend/` organized so each Streamlit page maps 1:1 to a
future React route. This makes migration surgical rather than a rewrite.
The code lives inside `jackpot-backend/` (not in the `jackpot-frontend`
repo, which is a vestigial stub — see Critical Rule 50).

```
jackpot-backend/frontend/
├── __init__.py
├── app.py                  # Entry point — navigation only
├── pages/                  # Streamlit auto-loads each file as a sidebar page
│   ├── __init__.py
│   ├── dashboard.py        # → /dashboard
│   ├── search.py           # → /search
│   ├── upload.py           # → /upload
│   ├── data_entry.py       # → /data-entry
│   ├── my_samples.py       # → /my-samples
│   ├── datasets.py         # → /datasets
│   ├── access_requests.py  # → /access-requests
│   ├── notifications.py    # → /notifications
│   └── pipelines.py        # → /pipelines
├── lib/                    # Cross-page helpers
│   ├── __init__.py
│   ├── api.py              # ApiClient + ApiError — single HTTP surface
│   └── session.py          # current_user(), my_user_id(), etc.
└── components/             # Reusable widgets
    ├── __init__.py
    ├── sample_table.py     # Sample list with bulk select (Month 2+)
    ├── pipeline_status.py  # Pipeline run status widget (Month 2+)
    ├── metadata_form.py    # Tier-aware metadata input form (Month 2+)
    ├── scrub_badge.py      # Scrub status indicator (Month 2+)
    └── notifications.py    # Notification badge and drawer (Month 2+)
```

Admin pages (`lab_director`, `platform_admin`, `archive_requests`,
`billing`) are intentionally absent — they're deferred to Month 3.

Never put business logic in Streamlit pages — all logic belongs in the
FastAPI backend. Streamlit pages are thin display layers that call the
API and render responses. This constraint makes the React migration
straightforward: replace the display layer, keep everything else.

### Migration path (Year 2)

When the signal arrives: build React + shadcn/ui + TanStack Query in
`jackpot-frontend`. Run Streamlit and React in parallel — Streamlit for
admin/power users, React for the polished researcher-facing UI. Retire
Streamlit when React covers all the same ground. The FastAPI backend
requires zero changes — it is already frontend-agnostic.

---

## LLM Support Assistant Architecture

JACKPOT includes a context-aware LLM support assistant for site orientation,
how-to guidance, and support topics. This section documents the architecture,
implementation pattern, and constraints that all assistant-related code must
follow.

### Core pattern: RAG, not fine-tuning

The assistant uses Retrieval-Augmented Generation (RAG). The LLM is never
fine-tuned on JACKPOT data — documentation is the retrieval source, not
baked into model weights. This means the assistant stays current as
documentation changes without retraining, and answers are grounded in
authoritative sources rather than model hallucination.

### Two implementation levels

**Level 1 — Documentation RAG (Year 2, early)**
Covers orientation and how-to questions. Static knowledge base of chunked
JACKPOT documentation stored in a vector database. No access to live data.

```
User question
  ↓
Embed query → retrieve top-k chunks from docs vector DB
  ↓
LLM prompt: system context + retrieved chunks + user question
  ↓
Grounded response with source citations
```

**Level 2 — Tool-augmented RAG (Year 2, later)**
Covers data-specific support questions ("why is my sample stuck?").
The LLM is given access to a curated set of read-only JACKPOT API
endpoints as tools. Requires the same access control as the API —
the assistant can only call endpoints the logged-in user is authorized
to call. Never give the assistant write access.

```
User: "Why is sample EXAMPLE-2026-001 stuck?"
  ↓
LLM decides: data question → call sample lookup tool
  ↓
Tool call: GET /api/v1/samples/EXAMPLE-2026-001 (as the logged-in user)
  ↓
Response grounded in live data, not guesswork
```

### Chat API endpoint

```
POST /api/v1/assistant/chat
{
  "message": "How do I request a scrub skip?",
  "context": {
    "current_page": "/projects/42/samples",
    "user_role": "Lab Collaborator",
    "lab_id": 7
  }
}
```

The `context` block is injected by the frontend automatically — the user
never fills it in. It allows the assistant to give role-appropriate answers.
A Lab Director asking "how do I approve a scrub skip?" gets a different
answer than a Lab Collaborator asking the same question.

### Knowledge base (RAG source documents)

Start with existing markdown documentation. Chunk, embed, and store in
the vector database whenever docs are updated (Cloud Scheduler job or
triggered on doc deployment):

- JACKPOT user guide (to be written, Month 1-2)
- Pipeline descriptions and parameter guides
- Metadata tier explanations and DataHarmonizer template docs
- Governance policy summaries (scrub skip, access requests, deletion)
- Role and permission descriptions
- FAQ

CLAUDE.md is a developer guide — do not include it in the user-facing
knowledge base.

### Model choice

**Default: Anthropic API (claude-haiku-4-5-20251001)**
Cheapest, fastest, sufficient for documentation Q&A. No new vendor
relationship — uses the same Anthropic API as the rest of the platform.
env var: `ASSISTANT_MODEL=claude-haiku-4-5-20251001`

**Alternative: Local model via Ollama (if data sensitivity required)**
If users are likely to paste sample IDs or clinical details into the chat,
a local model that never sends data to a third-party API is worth
considering. Llama 3.1 8B or Mistral 7B on a GKE GPU node. Set
`ASSISTANT_BACKEND=ollama`, `OLLAMA_ENDPOINT=http://ollama-service:11434`.

### Hallucination controls — mandatory

These constraints must be in every system prompt for the assistant:

1. **Grounded responses only** — answer only from retrieved context, never
   from general LLM knowledge about bioinformatics. If no relevant context
   is found, say "I don't have documentation on that — please contact
   support or check the user guide."

2. **Source citations** — every answer must cite which document section
   it came from. Enables users to verify answers and helps identify docs
   that need improvement.

3. **Explicit capability boundary** — the assistant answers questions about
   JACKPOT features and workflows only. It does not answer clinical
   interpretation questions, give advice about specific pathogens, comment
   on surveillance findings, or interpret pipeline results clinically.

4. **Role-scoped tool access** — in Level 2, the assistant inherits the
   logged-in user's permissions. It cannot retrieve data the user cannot
   see. Tool calls are authenticated with the user's session token, not
   a privileged service account.

### UI placement

Slide-out help panel accessible from every page via a "Help" button in
the navigation bar. Opens without leaving the current page. In Streamlit:
custom sidebar component or `st.expander`. In React: standard side drawer.
Never a full-page navigation — the assistant is a support tool, not a
primary feature.

### New environment variables

| Variable | Default | Description |
|---|---|---|
| `ASSISTANT_ENABLED` | `false` | Feature flag — disabled until Year 2 |
| `ASSISTANT_BACKEND` | `anthropic` | `anthropic` or `ollama` |
| `ASSISTANT_MODEL` | `claude-haiku-4-5-20251001` | Model name — use full string |
| `OLLAMA_ENDPOINT` | not set | Ollama service URL if backend=ollama |
| `ASSISTANT_VECTOR_DB` | `pgvector` | Vector store: `pgvector` or `chroma` |
| `ASSISTANT_MAX_CHUNKS` | `5` | Max retrieved chunks per query |
| `ASSISTANT_CACHE_TTL` | `3600` | Response cache TTL in seconds |

### Vector database choice

**pgvector (default)** — PostgreSQL extension for vector similarity search.
Runs in the existing Cloud SQL instance. No new infrastructure needed for
Level 1. Add the `pgvector` extension via Alembic migration when the
assistant is implemented.

**Chroma or Weaviate** — dedicated vector databases with richer retrieval
features. Overkill for a documentation-only knowledge base at JACKPOT's
scale. Consider if the knowledge base grows beyond ~1,000 documents.

### Real-world precedent

The PRIDE database at EBI built a directly comparable chatbot for their
proteomics data repository — same use case (documentation Q&A + dataset
search), same RAG architecture, published in Proteomics (2024).
Reference: https://www.ebi.ac.uk/pride/chatbot/
