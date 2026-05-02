# JACKPOT — first 10 minutes

Welcome. This guide walks you from a fresh `git clone` to a running
JACKPOT instance with `/health` returning 200, in under 10 minutes,
for the **laptop scenario** (Scenario A).

For the other 6 scenarios (B/C/D/E/F/T) the bootstrap shape is the
same; the differences live in `jackpot init`'s scenario defaults
(scope of cloud services, federation posture, CARE Principles
defaults for Tribal-sovereignty deployments). See the per-scenario
guides under `docs/deploy/stlt/` for the operational specifics.

## Prerequisites

- **Docker Desktop** (or Docker Engine + docker-compose v2.4+)
  — needed for `docker compose up -d` of the local stack.
- **uv** — Python package + workspace manager.
  Install: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **git** — for `git clone`.

## Step 1 — clone the monorepo

```bash
git clone https://github.com/Midnight-Oil-Innovation/jackpot.git
cd jackpot
```

## Step 2 — install Python dependencies

```bash
uv sync
```

The workspace pulls down backend + CLI + schema in one resolution.
Takes ~30 seconds on a warm cache.

## Step 3 — run `jackpot init`

For laptop dev, the entire bootstrap takes 3 commands:

```bash
# Detect-and-confirm scenario (skip with --scenario A if you already know).
uv run jackpot init configure --scenario A --instance-name local --no-gh

# Generate JWT signing key + per-instance secrets.
uv run jackpot init secrets --instance local

# Bring the stack up.
docker compose --env-file instances/local/.env.local up -d

# Apply schema + seed + smoke-test /health.
uv run jackpot init bootstrap --instance local
```

The bootstrap step takes ~30 seconds the first time (alembic runs all
migrations) and ~2 seconds on subsequent runs. When it finishes you'll
see a green `✓ healthy after 1.3s (version=5.0.0)` line.

## Step 4 — open the UI

```bash
open http://localhost:8501       # macOS
xdg-open http://localhost:8501   # linux
# or just point your browser at the URL
```

The Streamlit researcher UI logs you in as the seeded `admin@example.org`
mock user and shows the 9 researcher pages.

## What you have now

- A running stack at `http://localhost:8000` (API) and `http://localhost:8501` (UI)
- A configured local instance at `instances/local/` with:
  - `jackpot.toml` — your scenario + operator overrides
  - `.env.local` — docker-compose env vars (`COMPOSE_PROFILES=laptop`)
  - `secrets/jwt_signing_key.txt` — generated, 0600 perms
  - `seed.sql` — operator seed-data SQL (mostly empty for laptop scenario)
- A seeded DB with one Example Org, one Example Lab, the admin user

## Next steps

- **Run the test suite:** `uv run pytest` (615+ tests, ~20 seconds with Docker)
- **Try the upload CLI:** `uv run jackpot upload --help`
- **Read the spec:** `spec.md` for the full architecture
- **Switch scenarios:** want to deploy to GCP for real? Re-run
  `jackpot init configure --scenario B --instance-name production`
  in a new instance directory and follow `docs/deploy/stlt/state-health-department.md`
  (or whichever scenario fits your operator type).

## Troubleshooting

**`docker compose up -d` says "no services to start":** the
`COMPOSE_PROFILES` env var isn't set. Use the `--env-file` flag
(`docker compose --env-file instances/local/.env.local up -d`) or
explicitly pass `--profile laptop`. See `docker-compose.yml` for the
service-to-profile matrix.

**`jackpot init bootstrap` reports "missing required files":** you
skipped `jackpot init configure` or `jackpot init secrets`. The
bootstrap precondition check lists the exact paths — re-run the
missing step.

**`/health` keeps timing out:** the API container may not be ready
yet. Check `docker compose --env-file instances/local/.env.local logs api`
for the actual error. The most common cause is a stale `postgres_data`
volume from a prior install — `docker compose down -v` clears it.

## Re-running `jackpot init`

`jackpot init configure` and `jackpot init secrets` are idempotent.
On re-run:

- Non-secret files (jackpot.toml, .env.local, etc.) are overwritten by
  default. Pass `--no-overwrite-non-secrets` to preserve operator
  hand-edits.
- Secret files are **always preserved** unless you pass
  `--regenerate-secrets`, which prompts per-secret before overwriting.

The committed `instances/ci/` directory is **never overwritten** by
`jackpot init` — Critical Rule 56 enforcement. Reproduce CI locally
with `--instance-name ci-local` instead.
