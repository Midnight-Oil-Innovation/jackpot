> **Status:** Canonical — E-1 laptop UAT plan, 6-role RBAC.

# JACKPOT end-to-end laptop UAT plan

This is the canonical test plan for verifying that JACKPOT works
end-to-end on a developer laptop. It has two tiers:

- A **smoke test** (~30 minutes, Platform Admin only) that exercises
  a single happy path through the platform's major feature areas.
  Run before any change set lands on `development`.
- A **UAT** (3–4 hours, all six roles, real-shaped data) that
  exercises every role's capability matrix, both happy-path and
  boundary-denial cases, plus the P0f and I-2 state machines and the
  R-1 security boundaries.

The smoke test is the daily / per-PR sanity gate. The UAT runs after
major feature batches (P0f, P0g, I-1, I-2, R-1+R-2+R-3) ship, and is
what `E-1` produces the artifacts for. The operator runs the actual UAT after
this plan merges; this document is what they run against.

This plan is read against, not memorised. Pages, role names, and
endpoint paths are pulled from the running platform — if a future
change diverges from the plan, fix the plan rather than work around
the divergence in the test run.

## Prerequisites

- macOS / Linux laptop with Docker Desktop or Colima available, plus
  a working `docker compose` invocation. Container engine for the
  pipeline-execution portion is optional (see Pipeline execution
  requirements below).
- This repository checked out, on `development` or a feature branch.
- `uv` available for running pytest from outside containers when
  needed.
- Free ports 5432, 8000, 8501, 9000, 9001 — `docker compose down`
  any other stack first.
- Helper scripts under `tests/e2e/scripts/` and fixtures under
  `tests/fixtures/e2e/` (this directory).

## Authentication for testing

Local mode bypasses JWT validation entirely:
`backend.auth.guards.get_current_user` returns whichever user matches
`settings.mock_user_email`. The seed data ships one user
(`admin@example.org`) wearing both Platform Admin and Lab Director
hats for the seed Example Lab.

For the smoke test that single user is enough. For the UAT the test
plan needs to switch identities six times. To avoid bouncing the
backend per role switch, E-1 added a small dev-only endpoint:

- `POST /api/v1/auth/dev-login`
- 404s in any environment other than `settings.env == "local"`
- Body: `{email, role?, lab_id?, name?}`
- Looks up the user, creating them if absent; updates the role flags
  (`is_platform_admin`, `is_data_analyst`) and lab membership row
  when relevant; mutates the cached `mock_user_email` so subsequent
  same-process requests resolve as that identity.
- No JWT minted; cookies untouched. The endpoint emits an
  `AUTH_DEV_LOGIN` audit row for forensics.

Helpers `tests/e2e/scripts/dev_login.sh` and the alias `set_role.sh`
wrap this endpoint; the UAT calls them by name.

## Pipeline execution requirements

`POST /api/v1/pipelines/launch` does not spawn Nextflow. It validates
the launch request, renders a `nextflow.config`, writes a
`pipeline_runs` row with `status = QUEUED`, and returns a config path
plus a per-run `pipeline_token`. Driving the run to completion is the
operator's job: invoke `nextflow run nf-core/viralrecon -profile test
-c <rendered config>` from the laptop, and Nextflow itself posts back
to `/api/v1/pipelines/<id>/results` via the weblog hook in the config.

In practice this means the smoke test has two acceptable end states:

- **Launch-handoff** — JACKPOT renders a valid config and the
  `pipeline_runs` row reads `QUEUED`. Operator did not run Nextflow.
  This still validates the platform's launch surface.
- **Completion** — operator did run `nextflow run …`, the
  `pipeline_runs` row transitioned to `SUCCESS`, and JSONB result
  blobs are present in `pipeline_results`. Required for the full
  smoke pass criterion.

P0g `local` execution profiles render `process.executor = 'local'`,
so a developer laptop with Nextflow + Docker / Singularity installed
can drive the test profile to completion in well under the 30-minute
budget.

## Streamlit page navigation

`frontend/app.py` is the landing splash; the sidebar lists the 12
pages under `frontend/pages/`. Their `PAGE_TITLE` constants are:

- Dashboard
- Search samples
- My samples
- Upload samples
- Metadata entry
- Datasets (Month 3 placeholder; renders without errors)
- Pipelines
- Access requests
- Notifications (Month 3 placeholder)
- Broken files
- Import spreadsheet
- Submissions

The admin pages (`lab_director`, `platform_admin`, `archive_requests`,
`billing`) referenced in `app.py`'s splash text are deferred to a
later milestone and are not part of the UAT yet — the per-role
sections below test the equivalent admin actions through the API
directly.

## Smoke test (~30 minutes)

Goal: a Platform Admin walks through 12 steps from cold start to a
generated submission package without errors. All commands run from
the repository root. Time the run; aim for under 30 minutes.

### Smoke step 1 — cold start

```
tests/e2e/scripts/setup_local_env.sh
```

Pass: prints `✓ /health says database is connected` within 60 seconds.

### Smoke step 2 — authenticate as Platform Admin

```
tests/e2e/scripts/dev_login.sh admin@example.org "Platform Admin"
```

Pass: JSON response shows `user.is_platform_admin = true` and
`active_role = "Platform Admin"`.

### Smoke step 3 — confirm seeded substrate

`docker exec jackpot_postgres psql -U jackpot -d jackpot_db -c
"SELECT id, display_name FROM labs"` returns at least one row
(Example Lab, id=1). The `projects` table similarly returns the
seeded Dev Project.

If empty: the seed migration did not run; bounce with
`reset_environment.sh` and re-check.

### Smoke step 4 — create a project under Example Lab

In the Streamlit UI (browse to `http://localhost:8501`) or via API:

```
curl -fsS -X POST http://localhost:8000/api/v1/projects/ \
  -H 'Content-Type: application/json' \
  -d '{"lab_id": 1, "display_name": "E1 Smoke Project",
       "description": "E-1 smoke run",
       "pathogen_scope": ["Severe acute respiratory syndrome coronavirus 2"]}'
```

Pass: 201 with the new project id.

### Smoke step 5 — DataHarmonizer-CSV ingest path

Open the **Upload samples** page in Streamlit. Drag in
`tests/fixtures/e2e/smoke/metadata.csv` and submit.

Alternative API path:

```
curl -fsS -X POST http://localhost:8000/api/v1/ingest/upload \
  -F file=@tests/fixtures/e2e/smoke/metadata.csv -F lab_id=1
```

Pass: three samples with `sample_id` values `E1-SMOKE-001` through
`-003` appear on the **Search samples** page (or in
`SELECT sample_id FROM samples WHERE sample_id LIKE 'E1-SMOKE-%'`).

### Smoke step 6 — I-1 spreadsheet importer wizard path

Convert `tests/fixtures/e2e/smoke/metadata_xlsx.csv` to `.xlsx` (any
spreadsheet tool will do). Open **Import spreadsheet** in Streamlit
and drop the `.xlsx` in. Walk the wizard:

- Step 1: column-mapping suggestions land for every renamed header
  (e.g. "Sample ID" → `sample_id` with confidence ≥ 0.7).
- Step 2: accept the suggestions; the validation preview shows three
  rows landing at the highest-tier `quality_status`.
- Step 3: complete the import.

Pass: three samples `E1-SMOKE-XLSX-001` through `-003` appear in the
**Search samples** page.

### Smoke step 7 — register FASTQs as `file://` references

Stage the viralrecon test FASTQs locally, e.g. by letting the
pipeline pull them on demand or by manually downloading from
`https://github.com/nf-core/test-datasets`. Then register a single
pair against `E1-SMOKE-001`:

```
curl -fsS -X POST http://localhost:8000/api/v1/ingest/register \
  -H 'Content-Type: application/json' \
  -d '{"sample_metadata": {"sample_id": "E1-SMOKE-001", "lab_id": 1},
       "files": [
         {"role": "fastq_r1", "uri": "file:///abs/path/to/R1.fastq.gz"},
         {"role": "fastq_r2", "uri": "file:///abs/path/to/R2.fastq.gz"}
       ]}'
```

Pass: 201 with two `sample_files` rows reading `storage_state =
"EXTERNAL"` and a non-empty `cheap_fingerprint`. Repeat for the
remaining smoke samples (or use `register_files.py` against a flat
directory).

### Smoke step 8 — F-4 full content hash

Either wait for the F-4 cron tick (`full_hash_interval_seconds`,
default 5 minutes) or trigger it now:

```
tests/e2e/scripts/trigger_jobs.py compute_full_content_hash
```

Pass: returned JSON shows non-zero `hashes_computed` and a follow-up
`SELECT content_hash FROM sample_files WHERE sample_id IN (…)`
returns non-NULL hashes.

### Smoke step 9 — launch viralrecon test profile

Use the **Pipelines** page or:

```
curl -fsS -X POST http://localhost:8000/api/v1/pipelines/launch \
  -H 'Content-Type: application/json' \
  -d '{"pipeline_catalog_id": <viralrecon catalog id>,
       "lab_id": 1, "project_id": <smoke project id>,
       "sample_ids": [<sample pks>],
       "parameters": {"profile": "test"}}'
```

Pass: 201 returns a `run_id`, `work_dir`, `result_uri`, and config
path. The `pipeline_runs` row reads `status = "QUEUED"`. If running
Nextflow yourself: invoke
`nextflow run nf-core/viralrecon -c <config path> -profile test` and
wait for it to finish; status transitions to `SUCCESS` via the weblog
hook.

### Smoke step 10 — verify pipeline outputs (only if Nextflow ran)

Once `status = SUCCESS`:
- `SELECT result_data FROM pipeline_results WHERE run_id = '<run_id>'`
  returns at least one row.
- The JSONB references the shape documented in
  `tests/fixtures/e2e/smoke/smoke_expected_outputs.md` (consensus
  FASTA, VADR pass list, variants VCF, coverage TSV).

If the operator did not run Nextflow: skip this step and document so
in the run notes.

### Smoke step 11 — generate an NCBI submission package

Open **Submissions**, create a new draft against the smoke samples
targeting NCBI, validate, and click "Generate package" (or POST to
`/api/v1/submissions/{id}/generate`). The submission state should
move from `DRAFT` to `READY_TO_SUBMIT`.

Pass: a `submission_<id>/` directory appears under
`settings.submissions_output_root` containing `biosample.tsv`,
`sra.tsv`, `files/`, `seqsender_config.yaml`, and `README.md` per the
shape checklist.

### Smoke step 12 — mark submitted

Click "Mark submitted" in the UI or POST to
`/api/v1/submissions/{id}/mark-submitted`.

Pass: the submission row's `state` reads `SUBMITTED`. An
`AUDIT_LOG` row exists with the matching action.

### Smoke gate

Run `tests/e2e/scripts/verify_smoke_outputs.py`. All four shape
checks (`samples`, `sample_files`, `pipeline_runs`,
`submission_package`) must print `✓`. Any `✗` is a fail; investigate
before declaring the smoke run good.

### Smoke reset

```
tests/e2e/scripts/reset_environment.sh
```

Drops volumes + clears scratch + brings the stack back to seed.

## UAT (~3–4 hours)

The UAT walks every role through their capability matrix entry from
`docs/architecture.md` v6.0 §7.1, plus a battery of cross-cutting
tests for state machines, security boundaries, and UI flows. It runs
against a freshly reset environment plus the realistic SARS-CoV-2
fixture set under `tests/fixtures/e2e/uat/`.

Run the UAT in the order below; each per-role section assumes the
preceding ones ran or were skipped cleanly.

### UAT setup

1. `tests/e2e/scripts/reset_environment.sh` to clear seed data
   pollution from previous runs.
2. Stage real SARS-CoV-2 FASTQs under
   `tests/fixtures/e2e/uat/sars-cov-2/`. The `realistic_metadata.csv`
   fixture references them by sample id; either name the directories
   to match or edit the CSV's `sample_id` column.
3. `tests/e2e/scripts/dev_login.sh admin@example.org "Platform Admin"`
   to start as Platform Admin.

Per-role sections (1–6) run in a fresh seed substrate; you can mix
and match if you only have time for a subset, but the per-role
sections each assume the seed Example Lab is intact.

### UAT role 1 — Platform Admin

Set role: `set_role.sh admin@example.org "Platform Admin"`.

- **Create user, lab, project** — `register_user_lab_project.py
  "Acme Lab Director" "Lab Director"` lays down a new user, lab, and
  project. Verify all three rows appear.
- **List all labs** — `GET /api/v1/labs/` returns rows from every
  organisation, not just the caller's.
- **View cross-lab samples** — `GET /api/v1/samples?lab_id=<other>`
  returns rows owned by another lab without 403.
- **Approve scrub-skip request** — file a request as a Lab
  Collaborator (later in the UAT), then return here and approve via
  `POST /api/v1/samples/<id>/scrub-skip/approve`. Verify the audit
  log records `APPROVE_SCRUB_SKIP`.
- **Approve deletion** — request a non-surveillance deletion as a
  Lab Director, then approve here. Verify state transitions through
  `REQUESTED → APPROVED → COMPLETED`.
- **Manage sequencing labs** — `POST /api/v1/sequencing-labs` adds a
  new external lab; `PATCH /api/v1/sequencing-labs/<id>` toggles
  `is_active`. Pass: round-trip succeeds.
- **View billing across labs** — `GET /api/v1/billing/summary` (or
  the UI when present) returns rows for every lab.
- **Cannot be assigned to a lab** — POST a `dev-login` request with
  `role = "Platform Admin"` and `lab_id = 1` and confirm 400 with
  the `cannot be assigned to a lab` detail.

### UAT role 2 — Lab Director

Set role: `set_role.sh director@example.org "Lab Director" 1`
(uses the seed Example Lab).

- **Invite a lab member** — `POST /api/v1/labs/1/members` adds
  `collab@example.org` as a Lab Collaborator. Pass: 201 and the
  membership row exists.
- **Cross-lab boundary** — try `POST /api/v1/labs/<other-lab>/members`
  for a lab the director is not in. Pass: 403.
- **Approve access request** — file a request as a Lab Reader (later
  in the UAT), then approve via
  `POST /api/v1/access-requests/<id>/approve`.
- **Approve non-surveillance deletion** — file a deletion request
  for a `PRIVATE` non-surveillance sample, then approve here.
- **Edit sample metadata** — `PATCH /api/v1/samples/<id>` updates a
  field; verify audit log entry.
- **Launch a pipeline** — same as smoke step 9, scoped to the seed
  lab.
- **Submit to NCBI** — generate a submission package and mark it
  submitted. Pass: state transition to `SUBMITTED`.
- **View own lab's billing** — `GET /api/v1/billing/summary?lab_id=1`
  returns rows; same call with another lab id returns 403.
- **Mixed roles** — without changing user, run
  `dev_login.sh director@example.org "Lab Collaborator" <other-lab>`
  to add a Collaborator membership in a second lab. Verify both
  memberships are read back via `GET /api/v1/users/me`.

### UAT role 3 — Lab Collaborator

Set role: `set_role.sh collab@example.org "Lab Collaborator" 1`.

- **Upload sequences + metadata** — same upload flow as smoke step
  5, but with `realistic_metadata.csv`.
- **Edit metadata** — `PATCH /api/v1/samples/<id>` succeeds.
- **Launch a pipeline** — succeeds.
- **Submit to NCBI** — generate package and mark submitted; verify
  state machine moves through DRAFT → READY_TO_SUBMIT → SUBMITTED.
- **Cannot invite/remove members** — `POST /api/v1/labs/1/members`
  returns 403.
- **Cannot approve access requests** — file a request first as a
  Lab Reader; then `POST /api/v1/access-requests/<id>/approve`
  returns 403.
- **Cannot approve scrub skip** — file a scrub-skip request as
  yourself; switching back to Collaborator and trying to self-approve
  returns 403.
- **Cannot view billing** — `GET /api/v1/billing/summary` returns
  403.

### UAT role 4 — Lab Reader

Set role: `set_role.sh reader@example.org "Lab Reader" 1`.

- **View own lab samples** — `GET /api/v1/samples` returns the lab's
  rows.
- **View DISCOVERABLE in other labs** — pre-seeded
  `realistic_metadata.csv` includes `DISCOVERABLE` rows; verify they
  are visible.
- **Cannot upload** — `POST /api/v1/ingest/upload` returns 403 with
  a clear message naming the role.
- **Cannot edit** — `PATCH /api/v1/samples/<id>` returns 403.
- **Cannot launch** — `POST /api/v1/pipelines/launch` returns 403.
- **Cannot submit** — `POST /api/v1/submissions` returns 403.
- **Cannot approve anything** — every approve endpoint returns 403.

### UAT role 5 — Bioinformatics User

Set role: `set_role.sh bioinf@example.org "Bioinformatics User" 1`.

- **Same upload / edit / launch / submit as Lab Collaborator** —
  succeeds.
- **Request a new sequencing lab** — `POST
  /api/v1/sequencing-lab-requests` succeeds; verify a row in
  `sequencing_lab_requests` reads `status = PENDING`.
- **Cannot approve access requests** — 403.
- **Cannot manage members** — 403.

### UAT role 6 — Data Analyst

Set role: `set_role.sh analyst@example.org "Data Analyst"` (no lab
id; the role is global).

- **Cross-lab DISCOVERABLE read** — `GET /api/v1/samples` returns
  rows from every lab whose `sharing_level` is `DISCOVERABLE` or
  `PUBLIC`.
- **No raw sequences** — `GET /api/v1/samples/<id>/files` returns
  403 (or omits the file URIs in the response).
- **Cannot upload / edit / launch / submit** — all return 403.
- **Cannot be assigned to a lab** — POST a `dev-login` with
  `role = "Data Analyst"` and `lab_id = 1` and confirm 400.

### UAT cross-cutting A — Authentication flows

- **Mock login** — `dev_login.sh` round-trip succeeds end-to-end.
- **Logout** — `POST /api/v1/auth/logout` clears cookies and
  succeeds even if the cookie was already missing.
- **Refresh happy path** — issue a token (in a deployment with real
  OAuth, since local mode bypasses the token machinery), then `POST
  /api/v1/auth/refresh`. Verify a fresh access cookie comes back. In
  pure local mode this exercise is skipped; document so.
- **Token expiry** — manually advance an issued refresh token's
  `expires_at` in the DB and verify `/refresh` returns 401 with
  `error_code = INVALID_REFRESH_TOKEN`.

### UAT cross-cutting B — Security boundary negative tests

These verify the six R-1 fixes hold integrated:

- Register a `file://` URI in a non-local environment (deploy a
  staging copy with `ENV=gcp` if available) — expect 400 with the
  unsupported-scheme message. Skip if no non-local environment is
  available; the unit test `test_register_uri_scheme_rejected_in_gcp`
  covers it.
- Register an `http://169.254.169.254/...` URI — expect 400.
- Register an `http://internal-host/` URI — expect 400.
- Register a bare path with no scheme — expect 400.
- Try to create a pipeline catalog entry whose name contains shell
  metacharacters — expect validator rejection.
- Path-traversal-via-executor-type — covered by unit test; one quick
  POST with `executor_type = "../../etc"` confirms 400.

### UAT cross-cutting C — DataHarmonizer web UI flow

Open the DataHarmonizer page from the Upload samples page (or the
linked external editor in test-mode). Enter a single row of
metadata, generate a CSV via the DataHarmonizer download button,
upload the resulting CSV via JACKPOT's CSV ingest path, and verify
the sample lands at the expected `quality_status`. Validation
warnings render with their row + column references.

### UAT cross-cutting D — I-1 spreadsheet importer wizard flow

Use `tests/fixtures/e2e/uat/tricky_metadata.csv`:

- Upload via Import spreadsheet.
- Wizard auto-suggest step shows confidence scores; "Sample ID" →
  `sample_id` reads ≥ 0.7, "Hosp" maps to a controlled-vocab field
  with a lower confidence.
- Accept the suggestions; the preview step flags rows 5 and 6
  (missing `date_collected`, missing `sequencing_lab`) as PRELIMINARY
  tier and row 3 (date format `04/03/2026`) as a coercion warning.
- Refresh the browser at this step; resume the wizard from the
  Import spreadsheet page and verify state survives.
- Complete the import. Resulting samples land at the expected
  tiers.

### UAT cross-cutting E — File state machine (P0f) end-to-end

- Register a fresh EXTERNAL file via `/register`.
- `trigger_jobs.py compute_full_content_hash` populates
  `content_hash`.
- `rm` the file from the laptop filesystem.
- `trigger_jobs.py verify_file_references` marks it BROKEN.
- Try to launch a pipeline against that sample — expect 400 with
  `BROKEN_INPUTS`.
- Re-stage the same content at a new local path; re-register —
  verify dedup hit (the same `sample_files` row is reused with the
  new URI added to `alternate_uris`).
- Re-launch — expect success.
- Run `jackpot files promote --sample <id>` (the operator CLI) and
  verify the row transitions to MANAGED with an audit log entry.

### UAT cross-cutting F — Submission state machine (I-2) end-to-end

- Create a submission as Lab Collaborator (DRAFT).
- Add three samples.
- Validate readiness — moves to READY_TO_SUBMIT or stays in DRAFT
  with validation errors logged.
- Generate the package — DRAFT → READY_TO_SUBMIT.
- Mark submitted — READY_TO_SUBMIT → SUBMITTED.
- Register accessions for all samples — SUBMITTED → ACCEPTED. If the
  bulk register only fills a subset, expect PARTIAL_SUCCESS.
- For an embargoed submission: set `release_date` to one day ago,
  `trigger_jobs.py release_embargoed_submissions`; the row moves
  ACCEPTED → RELEASED.
- Withdraw flow: walk a separate submission to ACCEPTED, then `POST
  /api/v1/submissions/<id>/withdraw`. State moves to WITHDRAWN.

### UAT cross-cutting G — Streamlit UI smoke

Click through every page in the sidebar. Each must:

- Render without a Python traceback in the page body.
- Show the active user identity in the sidebar / header.
- Allow at least one navigation event back to Dashboard without
  reload.
- Have one action per page that reaches the API: e.g. Search
  samples runs a query and renders rows; Pipelines lists runs;
  Submissions lists drafts; Broken files lists nothing on a fresh
  reset.

### UAT cross-cutting H — Reset procedures

- **Standard reset** — `reset_environment.sh`.
- **Submission scratch wipe** — additionally `rm -rf
  $JACKPOT_SUBMISSIONS_OUTPUT_ROOT/submission_*` to drop on-disk
  packages.
- **Browser cookies** — clear the `localhost:8501` cookies between
  the OAuth-flow exercise (cross-cutting A) and the next role; the
  Streamlit session lives outside the dev-login mutation.
- **Fixture re-staging** — running `reset_environment.sh` does not
  re-register files; rerun `register_files.py
  tests/fixtures/e2e/uat/sars-cov-2/` after a reset.

## Troubleshooting

- **`/health` reports `database = error`** — Alembic migration
  failed. Check `docker compose logs api`. The most common cause is a
  schema-drift between branches; running `reset_environment.sh` from
  the target branch is the canonical fix.
- **`dev-login` returns 404** — `settings.env != "local"`. Verify
  the `ENV` env var on the api container (`docker compose exec api
  env | grep ^ENV=`). Local laptop should always read `ENV=local`.
- **`register` returns 400 for `file://`** — same root cause: env is
  not local. Confirm before chasing other issues.
- **Pipeline launch returns 400 with `gcp_project_id not
  configured`** — the legacy GCP-Batch fallback path is in use
  because no execution profile resolved. Either register a
  `local`-executor profile (P0g G-2 seed migration) or set
  `GCP_PROJECT_ID=jackpot-test` (the test-fixture value) for laptop
  runs that won't actually launch on GCP.
- **Streamlit page shows "API unreachable"** — the api container is
  down or not yet healthy. Check `docker compose ps`; rerun
  `setup_local_env.sh`.
- **`trigger_jobs.py` fails with "container not running"** — `docker
  ps` shows no `jackpot_api`; `setup_local_env.sh` first.
- **`verify_smoke_outputs.py` reports "0/6 smoke samples present"** —
  ingest steps did not commit. Inspect the api logs around the time
  of upload. Most likely cause: the operator skipped or aborted the
  Streamlit upload click.

## Appendix — reset procedures (full reference)

- `reset_environment.sh` — drops volumes, clears `/tmp/jackpot*`,
  brings the stack back. ~30 seconds.
- `docker compose --profile laptop down` (without `-v`) — keeps DB,
  bounces processes. Faster (~10 seconds), useful when the goal is
  to pick up a code change without losing state.
- `rm -rf $JACKPOT_SUBMISSIONS_OUTPUT_ROOT/submission_*` — drops
  on-disk submission packages without touching the DB rows.
- `docker compose exec postgres psql -U jackpot -d jackpot_db -c
  "TRUNCATE samples, sample_files, pipeline_runs, pipeline_results,
  submissions CASCADE"` — surgical truncate when you want a fresh
  data slate but don't want to lose users / labs / projects.

## Appendix — helper scripts reference

`tests/e2e/scripts/` contains:

- `setup_local_env.sh` — cold-start
- `dev_login.sh` / `set_role.sh` — switch active user/role
- `register_user_lab_project.py` — create user / lab / project
- `register_files.py` — bulk-register paired-end FASTQs
- `trigger_jobs.py` — manually invoke a background job
- `verify_smoke_outputs.py` — shape-check the smoke run
- `reset_environment.sh` — full reset

`tests/e2e/README.md` documents argument shapes and exit codes for
each script.

## Cross-references

- `docs/architecture.md` v6.0 §7.1 — canonical role capability
  matrix. Every role test case in this plan grounds in that section.
- `spec.md` — Submissions, Credentials, P0f file references, P0g
  execution profiles, I-1 spreadsheet importer, I-2 submission
  packages, I-3 backend execution.
- `docs/CLAUDE.md` — Critical Rules 1–62. Rules 8 (mock user), 22
  (lab tenancy), 24 (response envelopes), 55 (no operator-specific
  defaults in source), 57 (no copy on ingest), 61 (branch
  verification), 62 (credential abstraction) are the ones the UAT
  most directly probes.
- `docs/api/file_references.md`, `docs/api/imports.md`,
  `docs/api/submissions.md`, `docs/api/credentials.md` — endpoint
  reference detail referenced inline by the cross-cutting sections.
