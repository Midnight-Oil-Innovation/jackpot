# `instances/ci/` — committed canonical CI instance

This is the only `instances/<name>/` directory committed to the JACKPOT
repository. Per **Critical Rule 56** (`docs/CLAUDE.md`):

- ZERO secrets, ZERO PII, ZERO real operator-specific values
- All values are synthetic-only (`ci@example.org`, `CI Test Organization`)
- The JWT signing key in `secrets/jwt_signing_key.txt` is randomly
  generated but committed — CI is the only scenario where a known-fixed
  key is acceptable because there is no real auth to compromise

## Scenario

**F — CI / e2e test harness**

Mock auth, filesystem storage, no DLP, no NCBI/GISAID, no federation,
no scheduler.

## Use

The CI workflow runs:

```bash
docker compose --env-file instances/ci/.env.local up -d
uv run pytest
```

`COMPOSE_PROFILES=ci` in `.env.local` activates the `postgres + minio +
api` services (no `ui` for CI).

## Reproducing CI locally

**Do NOT overwrite this directory.** The committed config is the
contract CI runs against. To reproduce CI locally, generate a parallel
gitignored instance:

```bash
uv run jackpot init configure --scenario F --instance-name ci-local --non-interactive --no-gh
uv run jackpot init secrets --instance ci-local --non-interactive
docker compose --env-file instances/ci-local/.env.local up -d
```

`jackpot init configure` and `jackpot init secrets` both refuse to
write to `instances/ci/` (Critical Rule 56 enforcement at the CLI
level).

## Re-deriving the canonical CI config

If the scenario F defaults change (`schema/jackpot_scenarios/scenarios.py`)
and the committed CI config drifts, regenerate it:

```bash
# Generate fresh under a temporary name
uv run jackpot init configure --scenario F --instance-name ci-regen \
    --instances-dir /tmp --non-interactive --no-gh
uv run jackpot init secrets --instance ci-regen --instances-dir /tmp --non-interactive

# Manually copy + rename instance_name from "ci-regen" to "ci"
# in jackpot.toml, .env.local, seed.sql, README.md
cp /tmp/ci-regen/{.env.local,jackpot.toml,seed.sql,values.local.yaml} instances/ci/
cp /tmp/ci-regen/secrets/jwt_signing_key.txt instances/ci/secrets/
# (then edit instance_name occurrences)
```

The JWT signing key gets regenerated each time but that's fine — CI
auth is mock-only, no live tokens.
