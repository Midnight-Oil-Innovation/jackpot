> **Status:** Canonical — binding operating rules and Critical Rules for this repo.

# CLAUDE.md — jackpot-backend

## Project: JACKPOT

Pathogen genomics platform for genomic epidemiology, bioinformatics,
and public health research.

**Project context (April 2026 pivot):** JACKPOT is an independent project under
`Midnight-Oil-Innovation/jackpot`, licensed AGPL-3.0. The platform is
multi-deployment-target by design — production code is operator-agnostic and
serves **4** canonical install scenarios (A self-hosted commodity from laptop
to multi-lab agency, B HPC with Apptainer + Slurm + institutional storage, C
single-org cloud with Kubernetes, D CI test) with **federation, multi-tenancy,
and Indigenous data sovereignty as runtime configurations** (not separate
scenarios). Sovereignty-as-runtime-policy per `docs/architecture.md` §22
provides deletion-on-request, no-auto-publish defaults, federation off-by-default,
and CARE Principles compliance documented in
`governance/care-principles-and-tribal-data-sovereignty.md`. The
`jackpot init` CLI handles per-operator bootstrap (shipped in P0e).

Phasing, with status as of 2026-08-28 — cleanup phases 6.1–11, P0d
(monorepo migration), P0e (install/CLI), Phase 24.5 (architectural design
lockdown), and P0b (Schema v5.0, migration `c871b28bbdab`, merged
2026-07-06) are **complete**. P0f (BYOP infrastructure) is **in progress**.
P0c (multi-tenancy middleware + sovereignty deletion) and P1–P5 remain.
Per-item status lives in `active_backlog.yaml`, not here.

---

## Autonomous Operating Mode

### Before Starting Any Work

1. Read `active_backlog.yaml` — the canonical list of currently-actionable work.
   For architecture read `docs/architecture.md`; for why a decision was made read
   `docs/adr/`; for what a term means read `CONTEXT.md`. (`spec.md` was demoted to a
   redirect stub on 2026-08-28 — it is no longer the specification.)
2. Read `todo.md` — find the next unchecked task
3. Re-read this file (`docs/CLAUDE.md`) — all 67 Critical Rules apply at all times
4. Confirm the baseline is stable: `uv run pytest tests/ schema/tests/ cli/tests/` from the workspace root. The expected test count is `test_count` in `docs/STATUS.md` — never a number quoted in prose here or elsewhere. Coverage must stay at or above the CI threshold of 80%. The post-P0d 39% number we carried briefly was a pytest-cov misconfiguration (omit list wasn't reaching the report-time matcher); fixed by making `--cov-config=pyproject.toml` explicit in addopts — see `docs/learnings.md` "Coverage measurement bug" entry. P0e (`docs/architecture/jackpot-init-cli.md`) shipped `jackpot init` operator-bootstrap CLI plus 13 absorbed Phase 22 cleanup items; see `docs/review_log.md` "P0e closeout" section.

## Session-start checklist

**Run this as the FIRST action of any session involving file edits, git ops, schema work, or backlog edits.** Paste the output to the chat verbatim so Claude has verified state before proposing any commands. Applies in Claude Code, Claude in chat, and any other Claude surface. Skipping it is a Critical Rule N violation (pre-action state verification), regardless of how trivial the requested action appears.

```bash
# 1. Working tree + index state
pwd
git status

# 2. Origin divergence — has anything moved since last sync?
git fetch origin
BRANCH=$(git branch --show-current)
echo "=== local ahead of origin/$BRANCH ===" && git log --oneline "origin/$BRANCH..HEAD"
echo "=== origin ahead of local  ($BRANCH) ===" && git log --oneline "HEAD..origin/$BRANCH"

# 3. Recent history for context
git log --oneline -5

# 4. Worktree check (Critical Rule 61 — confirm you're in the worktree you think you are)
git worktree list
```

### What Claude does with this output

- **`git status` shows unexpected modified/staged files** (files Claude didn't author this session, files unrelated to the current task) → ask before proceeding. Don't assume the maintainer wants them included.
- **`origin/$BRANCH..HEAD` is non-empty** → local commits exist that aren't pushed. Warn before any `reset --hard` or destructive operation.
- **`HEAD..origin/$BRANCH` is non-empty** → origin has moved since last sync. Treat any uploaded files as STALE per Critical Rule N+3 (stale upload detection). Warn before any merge script run or backlog edit that depends on anchor strings — they may have shifted in the new commits.
- **`git worktree list` shows multiple worktrees** and the current `pwd` doesn't match the intended branch → stop, switch worktrees per Critical Rule 61 before continuing.

### When to re-run mid-session

- After the maintainer runs any terminal command Claude didn't propose (especially git operations).
- After any `git fetch` / `git pull` / `git push` / `git rebase` / `git reset`.
- Before any merge script run, even if the script ran successfully earlier in the session — anchors may have shifted.
- Before any `git commit -a -m`, to confirm only the intended files are modified/staged.

### When the maintainer can skip it

- Pure-conversation sessions with no file or git operations (asking questions, reviewing designs, drafting docs into chat).
- Read-only inspection sessions (`view`, `cat`, `grep` only).

If the session crosses from conversation into action — even a single edit — run the checklist first.

### Work Loop

- Take the **next unchecked item** from `todo.md`
- Cross-check it against `docs/architecture.md` and the relevant `docs/adr/` entry before writing code
- Write the code — no placeholders, no `# TODO`, no `# ... rest of code here`
- Run the relevant tests: `uv run pytest tests/test_{module}.py -v`
- If tests pass: check the item off in `todo.md`, commit with `git commit -a -m`, move to the next item
- If tests fail: fix and rerun — **never mark a task complete without passing tests**
- Every ~20 tasks: pause, review `docs/architecture.md` vs the current implementation for gaps,
  log findings to `docs/review_log.md`, and resolve all gaps before continuing

### Decision Rules

- **Never ask for confirmation** on anything resolvable by reading this file and running tests
- **Never lower the coverage threshold** — if a new file pulls coverage below 60%, add tests first
- **Never mark a task done** without `uv run pytest` showing it pass
- **Never write placeholder code** — every function must be fully implemented
- **Always use `uv run python` / `uv run python3`** — never bare `python` or `python3`; the shell aliases do not apply in Claude Code sessions
- When blocked on intent: check `docs/architecture.md` and `docs/adr/`, then the relevant section of this file,
  then log the question to `docs/review_log.md` and continue with the next unblocked task
- For non-trivial architectural changes: write the plan to `docs/review_log.md` and
  wait for explicit "Go" before proceeding

### Commit Convention

Use `git commit -a -m "type: description"` for every commit.
`-a` stages all tracked, modified files; new/untracked files still need `git add` first.
The `.pre-commit-config.yaml` ruff hooks run at commit time. If they auto-fix
files, the commit aborts; re-stage with `git add -u` and run the same
`git commit -a -m` again. To land fixes on the first attempt, optionally pre-run
`uv run ruff check --fix . && uv run ruff format .` before committing.
Valid types: `feat`, `fix`, `test`, `chore`, `refactor`
Examples: `git commit -a -m "feat: organizations router CRUD endpoints + tests"`
          `git commit -a -m "fix: conftest alembic migration in test DB setup"`

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

- Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2
  (canonical version lives in `docs/STATUS.md`; both `backend/pyproject.toml`
  and `cli/pyproject.toml` pin `requires-python = ">=3.12"`)
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

### ruff version is pinned across three sources of truth

ruff is pinned to one specific version in three independent places that
all must match:

| Where | What |
|---|---|
| `.pre-commit-config.yaml` | `rev: v<version>` under `astral-sh/ruff-pre-commit` |
| `backend/pyproject.toml` | `ruff==<version>` in the `dev` dependency group |
| `cli/pyproject.toml` | `ruff==<version>` in the `dev` dependency group |

Plus `schema/pyproject.toml` if it lists ruff (currently does not).

After bumping the version in any of these places, **all** of them must be
bumped together, then everyone pulling the change must run:

```bash
uv run pre-commit clean
uv run pre-commit install --install-hooks
uv sync
```

This refreshes the pre-commit hook cache (which doesn't auto-detect
version changes) and the resolved lockfile.

Why this matters: pre-commit caches hook environments by config hash, not
by version. The result of misalignment is "lint clean locally, fails on
CI" — which bit PR #22 (P1) on its first run before the in-PR reformat
workaround. This permanent pin alignment (PR #N) prevents recurrence.

---

## Directory Structure

The post-P0d monorepo lives at `~/Projects/operation_jackpot/jackpot/`. It is the
canonical layout under `Midnight-Oil-Innovation/jackpot`. The previous
six-repo + git-submodule arrangement is gone; what used to be submodules
(`schema/`, `nf/`) is now subtree-merged at the top level.


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
before implementing any router. See the API Response Conventions and
Notification System sections in `backend/CLAUDE.md` for their exact
interfaces.

**Reference docs moved out of this file (2026-08-21 doctor pass):**
backend implementation conventions (API responses, pagination, audit
logging, background jobs, notifications, storage, testing patterns,
epiweek computation, GCP env-var mapping, Nextflow pipeline execution,
caching) now live in `backend/CLAUDE.md`. GKE autoscaling and disaster
recovery now live in `deploy/CLAUDE.md`. The LLM support assistant
design now lives in the `llm-assistant-design` skill. They load
automatically when you work in those directories or invoke that skill —
no need to read them proactively otherwise.

---

## Current Baseline

- **Test count, Python version, schema version, and Alembic head are NOT
  restated here.** `docs/STATUS.md` is the single canonical source for all
  four, regenerated by `make status`. Read it instead of trusting a number
  written in prose — this block previously carried a test baseline that was
  stale by several hundred tests, and `spec.md` carried three mutually
  contradictory ones before it was demoted on 2026-08-28.
- **Coverage** must not fall below the CI threshold of 80%. The pre-P0d 86.99% baseline was
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
    aggregate diff, **merge-commit — never squash**. Squashing a
    release orphans `main`'s history from `development` and makes
    every subsequent release PR conflict on any file both sides
    touched since (release #99 did this; #118 required a
    reconnecting back-merge to fix). CI runs on PRs to `main` as a
    safety net.
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
    `uv run gen-pydantic --pydantic-version 2 schema/schema/jackpot_schema.yaml > backend/backend/models_generated.py`
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
`success_list`, `success_message`, and `error` from `backend/responses.py`.
The response envelope shape is fixed — routers never construct it manually.

Auth is the same story: routers take their identity and authorization from
`get_current_user`, `require_platform_admin`, `require_lab_director`, and
`require_lab_access` in `backend/auth/guards.py` — never by re-deriving
membership inline.

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
that makes scenarios A through D (and their runtime-config variants: federation, multi-tenancy, sovereignty) feasible from a single codebase.

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
treating the HTTP weblog receiver as **best-effort** and running a
log poller as the always-on fallback so cluster runs reach a
terminal state regardless of compute-node egress policy.

**Two paths, both running concurrently:**

- **HTTP weblog (best-effort):** every rendered `nextflow.config`
  carries a `weblog` directive pointing at
  `/api/v1/pipelines/events`. The receiver in
  `backend/backend/routers/pipelines.py` **never raises on errors**
  — Nextflow does not retry weblog delivery. The receiver tolerates
  duplicate events idempotently because `pipeline_runs.status`
  writes are idempotent, `pipeline_tasks` upserts on `(run_id,
  task_id)`, and the diagnostic `pipeline_events` table accepts
  duplicate inserts. Per-task accounting (`process.submitted`,
  `process.completed`, etc.) is weblog-only — the poller observes
  workflow-level state but not individual task transitions.
- **Log poller (always-on fallback):** an APScheduler job in
  `backend/backend/log_poller.py` fires every
  `settings.log_poller_interval_seconds` (default 30) for every run
  in `('PENDING', 'QUEUED', 'RUNNING')` whose `work_dir` is set.
  The poller tails `<work_dir>/runs/<run_id>/.nextflow.log` from a
  per-run `pipeline_runs.poller_log_offset` byte position, parses
  Nextflow's logger-prefixed start/completed/failed lines, and
  dispatches terminal classifications through the same
  `_handle_workflow_complete` codepath the receiver uses (so result
  loading runs once whether the trigger came through HTTP or
  polling). No flag gates the poller — it runs unconditionally;
  idempotency keeps state consistent when both paths observe the
  same event.

**Pre-launch reachability gate:** the launch endpoint runs
`sinfo -h` on the API host before queueing a SLURM-targeted run
(via `backend/backend/pipeline_config/cluster_reachability.py`).
Failure surfaces as 400 `SLURM_UNREACHABLE` with a pointer to
`jackpot doctor slurm --check-cluster`. Reachability is cached per
`(account, partition)` for 60 seconds so bulk launches don't spawn
50 subprocesses; tests opt out via
`settings.slurm_reachability_check_enabled = False`.

**For Scenario B (HPC) deployments with multi-tenancy enabled**, per-launch
`launch_account` overrides (which Slurm account to charge) must be
validated against the user's lab memberships via the P0c
multi-tenancy guard. Today's launch_account flow is a P0c stub:
the override is accepted verbatim and an
`SLURM_LAUNCH_ACCOUNT_OVERRIDE` audit row captures actor + before
(profile default) + after (override value) so a P0c-aware audit
review can retroactively flag overrides that would have been
rejected. Never trust `launch_account` from the request body alone
once P0c lands.

**Related schema:** `pipeline_runs.poller_log_offset` (per-run
poller byte position), `execution_profiles.config_overrides`
(Slurm-specific knobs in JSONB).

**Related backlog:** Phase P0h in `todo.md`,
`backend/backend/log_poller.py`,
`backend/backend/pipeline_config/cluster_reachability.py`,
`backend/backend/pipeline_config/profile_validation.py`,
`cli/jackpot/cli/doctor.py`. See `docs/slurm_executor.md` for the
operator-facing setup guide.

---

**61. Worktree + branch verification at session start.**

Every Claude Code session that runs in a git worktree must run a verification
check as its first action and refuse to proceed if either assertion fails.
The check (with `<branch>` filled in per session):

```bash
EXPECTED_WORKTREE="$HOME/Projects/operation_jackpot/jackpot-<branch>"
EXPECTED_BRANCH="<branch-name>"
[ "$(pwd -P)" = "$EXPECTED_WORKTREE" ] || { echo "FATAL: wrong cwd ($(pwd -P)). Stop." >&2; exit 1; }
[ "$(git branch --show-current)" = "$EXPECTED_BRANCH" ] || { echo "FATAL: wrong branch ($(git branch --show-current)). Stop." >&2; exit 1; }
echo "Worktree + branch verified."
```

Why this matters: parallel Claude Code sessions sharing one filesystem can
silently cross-pollute working trees when an agent starts in the wrong cwd
or when `git switch` is run inside a worktree. The Sessions 20-21
worktree-contamination saga consumed significant recovery time and prompted
this rule. Never `git switch` inside a worktree — each worktree is pinned
to its anchor branch by virtue of being created with `-b`.

**62. Credential reads go through `CredentialFacade`, never directly via env var or `Settings`.**

Sensitive string values (NCBI/ENA/GISAID API keys, Globus client secret,
JWT signing key, future federation peer keys, future LLM API keys) are
read via the C-1 credential infrastructure:

```python
from backend.credentials import credentials

api_key = credentials.get("ncbi_api_key")               # raises CredentialNotFoundError if missing
optional_token = credentials.get_optional("github_token")   # returns None if missing
```

Never read these from `os.environ` directly, never expose them as plain
`Settings` fields. Routes through the facade are the only call shape
that:

- inherits the operator-selected backend (env / file YAML / GCP Secret
  Manager / future AWS / Azure / OS keychain) without per-call branching;
- emits the `CREDENTIAL_READ` / `CREDENTIAL_READ_FAILED` audit events
  to the dedicated `backend.credentials.audit` stdlib logger;
- is registered in `backend/credentials/registry.py`'s
  `REQUIRED_CREDENTIALS` so `validate_required()` at startup catches a
  mis-configured deployment before the first request.

Adding a new credential is a three-step change: (1) add a
`CredentialSpec(...)` to `REQUIRED_CREDENTIALS` with a
`required_predicate` against `Settings`; (2) add the value to whichever
backends the deployment uses (env var / YAML key / GCP secret); (3)
read via `credentials.get(...)` from the consuming module.

Selectors live in `Settings`:

| Field | Default | Meaning |
|---|---|---|
| `credential_backend` | `"env"` | One of `"env"`, `"file"`, `"gcp_secret_manager"` |
| `credential_file_path` | `~/.config/jackpot/credentials.yaml` | Used only when `credential_backend = "file"`; file mode must be 0600 |
| `credential_gcp_secret_prefix` | `"jackpot-cred-"` | Used only when `credential_backend = "gcp_secret_manager"` |
| `credential_cache_ttl_seconds` | `300` | Facade-level TTL'd cache |

Existing migrated call sites: Globus client_id/client_secret/endpoint_id,
cloud-storage service-account credentials, JWT signing key. New code
follows the same pattern. See the Phase C-1 Specification in
`docs/archived/spec_v2.2_2026-04-29.md` for the
full design.

**63 — Pre-action state verification.** Before any operation that modifies the repo (file edits, git operations, applying patches, merge-script runs), Claude must verify and report three things: (a) `git status` output for the current working tree state; (b) `git fetch && git log --oneline HEAD..origin/<current-branch>` output showing whether origin has moved since Claude's last verified context; (c) the actual current state of any file Claude is about to modify (via `view` or `cat`, not relying on prior uploads). If any check returns unexpected state — divergence, stale uploads, files modified by something other than the current Claude session — Claude pauses and asks before continuing. Operating on stale context is the most common failure mode and is preventable. Anchor session: 2026-05-12 cryptWWDB merge — ~45 minutes of git recovery from skipping this check.

**64 — Manual edits below 20-edit threshold.** For one-off backlog edits, doc additions, or other structural changes affecting fewer than ~20 edits, Claude provides exact text + unambiguous placement markers (line numbers, surrounding context, section headers) and the maintainer edits the file directly in their editor. Merge scripts (`merge_*.py` pattern) are only warranted for: (a) repeated structural changes across many files; (b) edits with mechanical regularity that benefit from programmatic application; (c) >20 edits to a single file; (d) edits the maintainer explicitly requests as scripted. The cost of debugging a brittle merge script exceeds the cost of manual edits below this threshold.

**65 — Merge scripts must be drift-resistant.** When merge scripts are warranted (per Rule N+1), they must: (a) be idempotent — detect already-applied state and exit cleanly without re-applying; (b) use structural anchors (section headers + subsection navigation) rather than long exact-string matches that break on any nearby edit; (c) print a pre-flight diff showing what WOULD change before any write occurs, and require explicit confirmation to apply; (d) verify anchor uniqueness against the live file at run time, not against the file Claude assumed when authoring the script; (e) state in their docstring the exact baseline commit SHA they were authored against; (f) write to `.new` files first, never modify in place. Scripts that work once and break on the next commit are violations.

**66 — Stale upload detection.** When the maintainer uploads a file, that upload reflects a single point in time. If the maintainer has taken any terminal actions between the upload and Claude's next operation (running scripts, git operations, edits), Claude treats the uploaded file as STALE and re-verifies state before acting. When Claude is about to give commands that depend on file content (anchor strings, line numbers, item IDs), Claude first asks "have you run anything that might have changed this file since the upload?" If yes or uncertain, request fresh state via `cat` / `git show HEAD -- <file>` / equivalent before proceeding.

**67 — Operating-protocol rules are read-first.** Rules N through N+3 are session-level operational rules. Every Claude session involving file edits, schema work, git operations, or backlog work must reference these rules explicitly before taking action. The rules don't enforce themselves — they require maintainer call-out when violated until the pattern is internalized. If Claude proposes commands without verifying state per Rule N, or proposes a merge script below the Rule N+1 threshold without justification, the maintainer should pause the session and reference the rule number.

**68 — Session prompt closing-steps mandatory.** Every JACKPOT session prompt that produces a code commit MUST include a Closing Steps section executing the following sequence after the commit lands:

1. `git push -u origin <branch>`
2. `gh pr create --base development --title "..." --body "..."` with the full PR body following the template at `docs/session_prompt_template.md`
3. `gh pr merge --squash --delete-branch`
4. `git -C ~/Projects/operation_jackpot/jackpot fetch --prune`
5. `git -C ~/Projects/operation_jackpot/jackpot pull --ff-only origin development`
6. Session summary reports PR URL, merge SHA, main checkout HEAD SHA after sync, and an explicit "maintainer next step: run `jackpot-finish <branch>` from outside the session to remove the worktree and delete the local branch"

The session MUST NOT include `git worktree remove` of the current worktree — git refuses to remove the in-use worktree, and the maintainer's `jackpot-finish` helper handles this from outside. Out of Scope sections must include this exclusion explicitly.

Every code-commit session prompt structure must follow `docs/session_prompt_template.md`: required sections (Operating Rules, Role, Session Task, Acceptance Criteria, Out of Scope, Closing Steps, Source-of-truth docs to verify before coding), required acceptance criteria for the push/PR/merge/sync sequence, and the PR body template.

Sessions that do NOT produce a code commit (pure-research, pure-design, pure-documentation-without-commit) are exempt from Closing Steps but must explicitly state this exemption in Operating Rules.

**69 — Active-flag column naming: `active` for orgs and labs, `is_active` everywhere else.**

`organizations` and `labs` use a bare `active` column. Every other table
uses `is_active`. There is no principle behind the split — it is historical —
which is exactly why it needs writing down: the convention is undiscoverable
from any single table, and guessing wrong produces a query that silently
returns nothing rather than an error.

```sql
SELECT * FROM organizations WHERE active   = TRUE;   -- orgs, labs
SELECT * FROM users         WHERE is_active = TRUE;  -- everything else
```

Do not "fix" the inconsistency by renaming one side without a migration and a
sweep of every call site. Recorded here after it was found living only in the
demoted `spec.md` §3.

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

## Agent skills

Per-repo configuration consumed by the `mattpocock-skills` engineering
skills. Edit these files directly to change the conventions; re-run
`/mattpocock-skills:setup-matt-pocock-skills` only to switch issue
trackers or start over.

### Issue tracker

Issues live in GitHub Issues on `Midnight-Oil-Innovation/jackpot`, via
the `gh` CLI. PRs are not treated as a request surface. See
`docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, using the default label strings
(`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`,
`wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root, neither of
which exists yet — `docs/domain_reference.md` and `docs/architecture.md`
serve as the working glossary and decision record in the meantime. See
`docs/agents/domain.md`.

## Alembic single-flight (hard rule)

Only one migration may be in flight at a time. Before writing a migration, confirm no
other branch or open PR adds one. Never create a migration that shares a
`down_revision` with an existing migration. Run `uv run python scripts/check_migration_heads.py`
before committing any migration.

## Authorization-path serialization (hard rule)

Work on the **authorization decision path** runs one session at a time. Never
parallel-batch it, never run two such branches concurrently.

The path is:

- `backend/backend/auth/guards.py` — `require_capability`, `get_current_user`,
  the federation peer authenticator
- `backend/backend/authz/**` — the `permit()` engine, `visibility_sql_clause`,
  scope construction, principal loading, the reseed
- `backend/backend/permissions.py` — the legacy ladder, until M2 deletes it
- migrations that create or populate `authz_capability_grants` /
  `authz_policies`
- any route change that adds, removes, or moves a permission check
- `tests/authz/**`, especially `preflight.py` and its divergence registry

**Why, and it is not merge friction.** Authorization failures fail *open*. A
bad merge in most code throws, 500s, or fails a test; a bad merge here returns
200 to a request that should have been refused, and nothing in the response,
the logs, or the audit trail says so. The cost of catching it late is not a
rollback — it is not knowing who saw what in the meantime. Serial review is
cheap against that.

Secondary: every batch touches `tests/authz/preflight.py`, which encodes what
"correct" means. Two branches editing it produce a conflict resolved by
whoever merges second, in the file that would otherwise have caught the error.

**In practice:** `parallel_safe: false` on the backlog entry, one open PR at a
time across these files, and a full `uv run pytest tests/authz/` before each
merge — not just the tests the change touched.

**Provenance:** the phrase "auth-adjacent, do not parallel-batch" appeared in
backlog `parallel_safe_reason` fields from May 2026, citing
`scripts_jackpot/coding_scripts_howto.md`. That document describes the batch
tooling and contains no such rule — the citation never resolved. This section
is the rule the entries were reaching for, written down (2026-08-31).

## Dependency policy (hard rule)

Every new dependency passes two gates before it lands:
1. License compatible with AGPL-3.0 (`scripts/verify_licenses.py`). BSL, SSPL, and
   other non-compatible licenses are rejected regardless of technical merit.
2. No known blocking vulnerability (deptrust).
Check both before proposing a dependency. Commit `pyproject.toml` and `uv.lock` together.
