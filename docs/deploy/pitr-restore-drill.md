# PITR Restore Drill (DEPLOY-2)

This document is a runbook for the **point-in-time recovery (PITR)
restore drill** that should be exercised on every JACKPOT instance
before going live with real data, and quarterly thereafter.

The drill validates two distinct claims:

1. **Cloud SQL PITR is actually configured** — automated backups +
   binary logs are retained for at least 7 days, and a snapshot from
   any second within that window can be restored.
2. **Your team can execute the restore** — the runbook works, the
   permissions are right, and the recovered database is usable.

A backup you cannot restore from is not a backup. A restore procedure
nobody has run is not a procedure.

## Required permissions

The operator running the drill needs:

- **`roles/cloudsql.admin`** on the GCP project (or at minimum
  `cloudsql.instances.restoreBackup` + `cloudsql.instances.create`)
- **`roles/iam.serviceAccountUser`** on the Cloud SQL service account
  (if the production instance uses a custom SA for IAM authentication)
- **`roles/logging.viewer`** to confirm the restored instance's logs
  are wired up

These are operator-agnostic role names. The list of human accounts
holding them is per-instance configuration.

## Pre-drill checklist (one-time, per instance)

Before the first drill, confirm Terraform has set:

```hcl
# deploy/terraform/modules/cloud_sql/main.tf — verify these two blocks
backup_configuration {
  enabled                        = true
  point_in_time_recovery_enabled = true
  start_time                     = "03:00"   # UTC
  transaction_log_retention_days = 7         # max for PostgreSQL
  backup_retention_settings {
    retained_backups = 14
    retention_unit   = "COUNT"
  }
}
```

If `point_in_time_recovery_enabled = false`, the drill cannot run —
fix Terraform first, apply, wait 24 hours for the first WAL window to
build, then run the drill.

## The drill

Estimated wall time: **45–90 minutes**, mostly waiting on instance
provisioning. Only the first ~5 minutes require operator attention;
the rest is wait-and-verify.

### Step 1 — Pick a recovery target time

Choose a timestamp from the last 24 hours that's at least 15 minutes
in the past (so the WAL window is fully closed) and at most
`transaction_log_retention_days` days back. Format as RFC 3339 UTC.

```bash
TARGET_TIME="2026-05-01T15:30:00.000Z"
SOURCE_INSTANCE="<production-instance-name>"
TARGET_INSTANCE="${SOURCE_INSTANCE}-pitr-drill-$(date +%Y%m%d-%H%M%S)"
PROJECT_ID="<production-project-id>"
REGION="<region>"
```

These four variables drive the rest of the drill — set them as
environment variables in your shell before running the gcloud
commands below.

### Step 2 — Confirm the source instance has PITR enabled

```bash
gcloud sql instances describe "$SOURCE_INSTANCE" \
  --project="$PROJECT_ID" \
  --format="value(settings.backupConfiguration.pointInTimeRecoveryEnabled)"
```

Expected output: `True`. If `False`, abort — you cannot drill what
isn't configured.

### Step 3 — Restore to a NEW instance (never overwrite production)

```bash
gcloud sql instances clone "$SOURCE_INSTANCE" "$TARGET_INSTANCE" \
  --project="$PROJECT_ID" \
  --point-in-time="$TARGET_TIME"
```

This kicks off an asynchronous clone. Track progress:

```bash
gcloud sql operations list \
  --project="$PROJECT_ID" \
  --instance="$TARGET_INSTANCE" \
  --limit=5
```

Wait for the clone operation to show `STATUS: DONE`. Typical wall
time is 20–60 minutes depending on database size.

**Note on credentials:** a Cloud SQL clone inherits all DB users and
their passwords from the source instance. The `postgres` user
password and any application-role passwords are identical to
production. Do not rotate them on the clone — that's pointless and
wastes the drill window — just dispose of the clone in step 6.

### Step 4 — Verify the restored instance is reachable

```bash
gcloud sql instances describe "$TARGET_INSTANCE" \
  --project="$PROJECT_ID" \
  --format="value(state,ipAddresses[0].ipAddress)"
```

Expected: `RUNNABLE` plus an IP address.

### Step 5 — Connect and verify data integrity

Set up a local connection through Cloud SQL Auth Proxy:

```bash
cloud-sql-proxy \
  --port 5433 \
  "$PROJECT_ID:$REGION:$TARGET_INSTANCE" &
PROXY_PID=$!
trap 'kill "$PROXY_PID" 2>/dev/null || true' EXIT
sleep 5
```

Run the verification queries against the restored instance. Pick
queries that exercise the major tables — you want evidence the data
is consistent, not just present:

```bash
# Count rows in the most important tables. Compare these to
# production at the recovery target time (you may need a separate
# read-only proxy session against production to confirm).
PGPASSWORD="<restored-instance-password>" psql \
  -h localhost -p 5433 -U postgres -d jackpot_db <<SQL
\echo === Instance identity (should be the cloned instance, not production) ===
SELECT inet_server_addr() AS server_ip, current_database();

\echo === Row counts ===
SELECT 'organizations' AS tbl, COUNT(*) FROM organizations
UNION ALL SELECT 'labs',        COUNT(*) FROM labs
UNION ALL SELECT 'users',       COUNT(*) FROM users
UNION ALL SELECT 'samples',     COUNT(*) FROM samples
UNION ALL SELECT 'sample_files',COUNT(*) FROM sample_files
UNION ALL SELECT 'pipeline_runs', COUNT(*) FROM pipeline_runs
ORDER BY tbl;

\echo === Most recent sample (sanity-check timestamp ≤ target time) ===
SELECT id, sample_id, created_at FROM samples
ORDER BY created_at DESC LIMIT 1;

\echo === Alembic version ===
SELECT version_num FROM alembic_version;
SQL
```

**Pass criteria:**
- Row counts are within ±1% of production at the target time (small
  drift is expected because PITR has second-level granularity).
- The most recent sample's `created_at` is **before or equal to**
  `$TARGET_TIME` — never after.
- The `alembic_version` matches what production was running at the
  target time.

If any of these fail, do NOT trust the production PITR config. Open
an incident, file a Cloud SQL support ticket, and re-test against a
known good backup.

### Step 6 — Tear down the test instance

```bash
kill "$PROXY_PID" 2>/dev/null || true
gcloud sql instances delete "$TARGET_INSTANCE" \
  --project="$PROJECT_ID" \
  --quiet
```

Confirm deletion:

```bash
gcloud sql instances list --project="$PROJECT_ID" \
  | grep "$TARGET_INSTANCE" || echo "Cleaned up."
```

The drill instance bills by uptime; leaving it running costs roughly
the same per hour as production. Don't skip cleanup.

## After the drill

Record the result. The minimum: append a one-line entry to
`docs/learnings.md` with the drill date, the target time, the
operator, and PASS / FAIL. If FAIL, file an issue in the repo and
block any production deploys (DEPLOY-1) until the failure is
understood.

Recommended: open a recurring calendar reminder to drill again in 90
days.

## Cost notes

Cloud SQL clone instances are full instances — the same machine type
as the source. A 2-hour drill against a `db-custom-4-15360` instance
costs roughly **$0.50** at us-central1 list price. The drill is
cheap; not drilling is expensive.

## Operator-agnostic posture

This runbook deliberately uses placeholder values
(`<production-project-id>`, `<region>`,
`<production-instance-name>`, `<restored-instance-password>`). Each
JACKPOT instance fills these in from its own configuration; the
runbook itself encodes no operator-specific identifiers.

## See also

- `docs/deploy/production-deploy.md` (DEPLOY-1) — the production
  deploy gate that references this runbook.
- `deploy/terraform/modules/cloud_sql/` — where PITR is enabled.
- Cloud SQL PITR docs:
  https://cloud.google.com/sql/docs/postgres/backup-recovery/pitr
