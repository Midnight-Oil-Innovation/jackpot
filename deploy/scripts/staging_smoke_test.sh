#!/usr/bin/env bash
# Post-deploy smoke test for the JACKPOT staging environment.
#
# Runs as the last step of .github/workflows/deploy-staging.yml and can
# also be run locally against staging. Exits non-zero on any failure.
#
# Usage:
#   JACKPOT_API_URL=https://api.staging.<your-jackpot-domain> ./scripts/staging_smoke_test.sh
#
# Optional:
#   JACKPOT_API_TOKEN     Bearer token to exercise an auth-gated endpoint.
#   PROJECT_ID            GCP project, required for --check-buckets.
#   GKE_CLUSTER           Cluster name, required for --check-kube.
#   GKE_REGION            Region, required for --check-kube.
#
# Flags:
#   --check-kube          Also check pod readiness and alembic Job success.
#   --check-buckets       Also check the 7 GCS buckets exist + are writable.

set -euo pipefail

API_URL="${JACKPOT_API_URL:-}"
API_TOKEN="${JACKPOT_API_TOKEN:-}"
CHECK_KUBE=0
CHECK_BUCKETS=0

for arg in "$@"; do
    case "$arg" in
        --check-kube)    CHECK_KUBE=1 ;;
        --check-buckets) CHECK_BUCKETS=1 ;;
        *) echo "Unknown arg: $arg" >&2; exit 2 ;;
    esac
done

if [[ -z "$API_URL" ]]; then
    echo "JACKPOT_API_URL must be set." >&2
    exit 2
fi

PASS=0
FAIL=0

ok()   { echo "  ✓ $1"; PASS=$((PASS + 1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL + 1)); }

hr() { printf -- '─%.0s' {1..60}; echo; }

# ── 1. Health endpoint ────────────────────────────────────────────────────────
echo "Checking API health at $API_URL"
http_status=$(curl -s -o /tmp/jackpot_health.json -w '%{http_code}' \
    --max-time 10 "$API_URL/health" || echo "000")
if [[ "$http_status" == "200" ]]; then
    if grep -q '"status":"ok"' /tmp/jackpot_health.json; then
        ok "/health returned 200 with status=ok"
    else
        fail "/health returned 200 but status != ok: $(cat /tmp/jackpot_health.json)"
    fi
else
    fail "/health returned $http_status"
fi

# ── 2. OpenAPI schema served ──────────────────────────────────────────────────
http_status=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
    "$API_URL/openapi.json" || echo "000")
if [[ "$http_status" == "200" ]]; then
    ok "/openapi.json served"
else
    fail "/openapi.json returned $http_status"
fi

# ── 3. Auth gate enforced on protected endpoint ──────────────────────────────
http_status=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
    "$API_URL/api/v1/samples/" || echo "000")
if [[ "$http_status" == "401" || "$http_status" == "403" ]]; then
    ok "/api/v1/samples/ requires auth (got $http_status)"
else
    fail "/api/v1/samples/ should require auth but returned $http_status"
fi

# ── 4. Authenticated request (optional) ──────────────────────────────────────
if [[ -n "$API_TOKEN" ]]; then
    http_status=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
        -H "Authorization: Bearer $API_TOKEN" \
        "$API_URL/api/v1/users/me" || echo "000")
    if [[ "$http_status" == "200" ]]; then
        ok "/api/v1/users/me returns 200 for authenticated caller"
    else
        fail "/api/v1/users/me returned $http_status with provided token"
    fi
else
    echo "  • JACKPOT_API_TOKEN not set — skipping authenticated check"
fi

# ── 5. (Optional) Kubernetes: Deployment ready, migrations succeeded ─────────
if [[ "$CHECK_KUBE" == "1" ]]; then
    hr
    echo "Kubernetes checks"
    : "${GKE_CLUSTER:?GKE_CLUSTER must be set for --check-kube}"
    : "${GKE_REGION:?GKE_REGION must be set for --check-kube}"
    : "${PROJECT_ID:?PROJECT_ID must be set for --check-kube}"

    gcloud container clusters get-credentials "$GKE_CLUSTER" \
        --region "$GKE_REGION" --project "$PROJECT_ID" >/dev/null

    ready_replicas=$(kubectl -n jackpot get deploy jackpot-api \
        -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    desired=$(kubectl -n jackpot get deploy jackpot-api \
        -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    if [[ "$ready_replicas" -ge 1 && "$ready_replicas" == "$desired" ]]; then
        ok "jackpot-api Deployment ready ($ready_replicas/$desired)"
    else
        fail "jackpot-api Deployment not ready ($ready_replicas/$desired)"
    fi

    migrate_job=$(kubectl -n jackpot get jobs \
        -l component=migrations -o jsonpath='{.items[-1:].metadata.name}' 2>/dev/null || echo "")
    if [[ -n "$migrate_job" ]]; then
        succeeded=$(kubectl -n jackpot get job "$migrate_job" \
            -o jsonpath='{.status.succeeded}' 2>/dev/null || echo "0")
        if [[ "$succeeded" == "1" ]]; then
            ok "Alembic migration Job $migrate_job succeeded"
        else
            fail "Alembic migration Job $migrate_job did not succeed (status: $succeeded)"
        fi
    else
        fail "No alembic migration Job found"
    fi
fi

# ── 6. (Optional) Bucket accessibility ───────────────────────────────────────
if [[ "$CHECK_BUCKETS" == "1" ]]; then
    hr
    echo "Bucket checks"
    : "${PROJECT_ID:?PROJECT_ID must be set for --check-buckets}"

    BUCKETS=(
        jackpot-staging-sequences
        jackpot-staging-references
        jackpot-staging-results
        jackpot-staging-staging
        jackpot-staging-work
        jackpot-staging-backups
        jackpot-staging-portal-exports
    )
    for b in "${BUCKETS[@]}"; do
        if gsutil ls -b "gs://$b" >/dev/null 2>&1; then
            ok "gs://$b reachable"
        else
            fail "gs://$b missing or inaccessible"
        fi
    done
fi

# ── Report ────────────────────────────────────────────────────────────────────
hr
echo "Smoke test: $PASS passed, $FAIL failed"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
