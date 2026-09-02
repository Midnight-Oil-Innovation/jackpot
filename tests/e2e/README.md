# tests/e2e/ — end-to-end UAT plumbing (E-1)

Helper scripts and a small standing fixture set for the laptop UAT
described in `docs/e2e_uat_plan.md`. The scripts are semi-automation
for the API portions of the test plan; the UI portions remain manual
walkthroughs in the doc itself.

This directory does NOT contain pytest test files — those live under
`tests/`. The scripts here exec against a running laptop stack
(`docker compose --profile laptop up`), not the in-process FastAPI app
the unit tests use.

## Scripts

All scripts live in `tests/e2e/scripts/`. Shell scripts have shebang
lines and `chmod +x` is set; Python scripts use `urllib` from the
stdlib (no extra deps) and are also executable.

- `setup_local_env.sh` — cold-start the laptop compose stack and wait
  for `/health` to report `database = connected`. Run once at the top
  of every smoke / UAT cycle.
- `dev_login.sh <email> [<role>] [<lab_id>]` — POST to
  `/api/v1/auth/dev-login` to switch the active mock user. The
  endpoint mutates the cached `settings.mock_user_email`, so all
  subsequent same-process API requests resolve as the new identity.
- `set_role.sh` — alias for `dev_login.sh` with role-switch
  semantics. Same arguments, same behaviour. Used in the UAT doc
  because it reads naturally as "set the active role to X".
- `register_user_lab_project.py <name> <role>` — create a user, lab,
  and project as Platform Admin via the public REST API. Used by the
  UAT setup phase to lay down the multi-role substrate.
- `register_files.py <fastq_dir>` — bulk-register paired-end FASTQs
  in a directory tree as `file://` references on the active sample.
  Local-mode-only (R-1 #2 rejects `file://` outside `env=local`).
- `trigger_jobs.py <job_name>` — invoke a JACKPOT background job
  inside the api container (`docker exec`), bypassing the
  APScheduler cron. Supports the four jobs the UAT may want to fire
  manually: F-4 hash, F-5 verify, embargo release, access-request
  sweep.
- `verify_smoke_outputs.py [--submissions-root PATH]` — assert the
  shape checks documented in
  `tests/fixtures/e2e/smoke/smoke_expected_outputs.md`.
- `reset_environment.sh` — full reset (volumes + scratch + stack
  bounce) between major UAT scenarios.

## How the test plan uses them

The smoke test section opens with `setup_local_env.sh`, calls
`dev_login.sh admin@example.org "Platform Admin"` once, and runs the
12 happy-path steps; `verify_smoke_outputs.py` is the final gate.

The UAT section uses `set_role.sh` at the head of every per-role
section (1–6) and `reset_environment.sh` between major boundary tests
that mutate seed data.

## Conventions

- Every script honours `JACKPOT_API_URL` if set; defaults to
  `http://localhost:8000`.
- Every script returns non-zero on failure and prints a single-line
  diagnostic to stderr — call sites can check exit codes without
  parsing output.
- Successful output goes to stdout in a stable format
  (`✓ <description>` for shell, JSON for Python).
- Scripts are idempotent where possible: re-running
  `dev_login.sh` for an existing user just re-assigns the role;
  re-running `register_files.py` for the same FASTQ dir hits the
  P0f content-hash dedup path and reuses existing `sample_files`
  rows.
- Scripts live in the dev environment (`settings.env == "local"`).
  Calling them against any other environment will surface either
  HTTP 404 (dev-login) or HTTP 400 (register with `file://`) and is
  expected to fail.
