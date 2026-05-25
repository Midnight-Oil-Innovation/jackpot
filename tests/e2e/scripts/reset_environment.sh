#!/usr/bin/env bash
# E-1 — full environment reset between major UAT scenarios.
#
# What it does
# ------------
# 1. Stops the laptop compose stack and DROPS the postgres + minio
#    volumes so Alembic re-runs against a fresh DB.
# 2. Brings the stack back up (delegates to setup_local_env.sh).
# 3. Removes any temp files E-1 helpers wrote under /tmp/jackpot* and
#    /tmp/jackpot-executions* (the I-3b execution scratch root).
#
# When to run
# -----------
# - Between role-by-role UAT scenarios that need a clean DB substrate
#   (e.g. before testing Lab Director invite flows fresh).
# - After any test that mutates seed data in a way later tests do not
#   expect.
#
# When NOT to run
# ---------------
# - Inside a single role's test sequence — you will lose the in-progress
#   state. Prefer dev_login.sh for identity switches alone.
# - When you have unsubmitted submission packages on disk that you want
#   to keep — this drops the postgres volume but does not garbage the
#   filesystem-resident submission dirs unless you also wipe the
#   submissions output root.
#
# Successful output
# -----------------
#   ✓ stack reset; api healthy
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "→ tearing down stack + volumes..."
docker compose --profile laptop down -v

echo "→ removing /tmp/jackpot* scratch..."
rm -rf /tmp/jackpot_*  /tmp/jackpot-executions  >/dev/null 2>&1 || true

echo "→ bringing the stack back up..."
exec "$(dirname "$0")/setup_local_env.sh"
