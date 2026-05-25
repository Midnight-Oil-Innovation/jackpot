#!/usr/bin/env bash
# E-1 setup helper — cold-start the laptop compose stack.
#
# What it does
# ------------
# 1. Tears down any stale `laptop`-profile services + volumes so the
#    next bring-up runs Alembic against a clean DB.
# 2. Brings the `laptop` profile back up in detached mode.
# 3. Polls /health on the api service until it responds with
#    `database = connected` (or fails the 60-second deadline).
#
# When to run
# -----------
# - Once per smoke / UAT cycle, before any other E-1 helpers.
# - Re-run after `reset_environment.sh` to take you back to a clean
#   seeded state.
#
# Successful output
# -----------------
#   ✓ laptop services running
#   ✓ /health says database is connected
#
# Exit codes
# ----------
#   0  api healthy within deadline
#   1  api never reached `database = connected`
#   2  docker compose command failed
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "→ tearing down existing laptop stack..."
docker compose --profile laptop down -v >/dev/null 2>&1 || true

echo "→ bringing laptop stack up..."
docker compose --profile laptop up -d || exit 2

echo "→ waiting for /health..."
deadline=$((SECONDS + 60))
while (( SECONDS < deadline )); do
  body="$(curl -fsS http://localhost:8000/health 2>/dev/null || true)"
  if echo "$body" | grep -q '"database":[ ]*"connected"'; then
    echo "✓ laptop services running"
    echo "✓ /health says database is connected"
    exit 0
  fi
  sleep 2
done

echo "✗ /health never reached database=connected within 60s"
docker compose --profile laptop logs --tail 30 api
exit 1
