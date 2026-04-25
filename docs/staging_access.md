# JACKPOT Staging — Access & Deployment Runbook

Last updated: 2026-04-18 (post-Session 5)

This is the operational guide for the JACKPOT staging environment on GCP.
Covers normal deploys, access, troubleshooting, and recovery paths. Written
from the hard-won experience of the first successful deploy.

---

## 1. Staging environment summary

| Resource | Identifier |
|---|---|
| GCP project | `gotero3-acdp-488517` |
| GCP region | `us-central1` |
| GKE cluster | `jackpot-staging-gke` (regional) |
| K8s namespace | `jackpot` |
| Helm release | `jackpot-api` |
| Cloud SQL instance | `jackpot-staging-db` (POSTGRES_16, zonal us-central1-f) |
| Cloud SQL database | `jackpot_db` |
| Cloud SQL private IP | `10.188.230.3` |
| Cloud SQL tier | `db-custom-1-3840` (1 vCPU, 3.75 GB) |
| Service URL (in-cluster) | `http://jackpot-api.jackpot.svc.cluster.local` |
| Service URL (external) | Not yet configured — Ingress/DNS is a P1 item |
| GCS buckets | `jackpot-staging-{sequences,staging,references,results,work,backups,portal-exports}` |

---

## 2. Normal deploy flow

Deploys are triggered by pushing to the `staging` branch in `jackpot-iac`.
The GitHub Actions workflow `deploy-staging.yml` handles the rest:

1. Checks out `jackpot-iac` and `jackpot-backend` (both at `staging` branch).
2. Initialises submodules in `jackpot-backend` (`schema`, `nf`) using PAT
   injection via `url.insteadOf`.
3. Authenticates to GCP via Workload Identity Federation.
4. Builds the API image and pushes to Artifact Registry.
5. Gets GKE credentials.
6. Syncs `jackpot-api-secrets` from Secret Manager.
7. Runs `helm upgrade --install --wait` — this triggers the Alembic
   migration Job as a pre-upgrade hook, then rolls out the Deployment.
8. Runs the smoke test via in-cluster `kubectl port-forward`.

Trigger a fresh deploy manually:

```bash
cd ~/ASU/jackpot/jackpot-iac
gh workflow run deploy-staging.yml --ref staging
gh run watch
```

Monitor cluster-side during the deploy:

```bash
watch -n 2 'kubectl -n jackpot get jobs,pods,deployment'
```

Tail API pod logs as they come up:

```bash
kubectl -n jackpot logs -l app.kubernetes.io/name=jackpot-api -f --tail=100
```

---

## 3. Accessing the API

### In-cluster (works today)

```bash
kubectl -n jackpot port-forward svc/jackpot-api 8080:80
curl http://localhost:8080/health
```

### From the workflow runner (for smoke tests)

The deploy workflow's smoke test step is already wired to do this. See
`.github/workflows/deploy-staging.yml` "Smoke test (via kubectl
port-forward)" step.

### Public URL

Not yet provisioned. Ingress + DNS + managed cert is a P1 backlog item.
When it lands, update `values-staging.yaml` env:
- `JACKPOT_API_URL`
- `CORS_ORIGINS`
- `GOOGLE_OAUTH_REDIRECT_URL`

And flip `scripts/staging_smoke_test.sh` to hit the public URL.

---

## 4. Cloud SQL access

### Connection string format

The canonical `DATABASE_URL` is:

```
postgresql://jackpot:<password>@10.188.230.3:5432/jackpot_db
```

**IMPORTANT: database name is `jackpot_db`, not `jackpot`.** This bit us
in Session 5 because a `docs/staging_access.md` example (an earlier
version of this file) incorrectly said `jackpot`. The database name is
set by the Terraform module default in
`terraform/modules/cloud-sql/variables.tf:83` — `default = "jackpot_db"`.

### Connect directly from your laptop

Cloud SQL is on a private IP, so you need the Cloud SQL Proxy:

```bash
# Install (once)
brew install cloud-sql-proxy

# Start the proxy (leave running in a terminal)
cloud-sql-proxy \
    --project=gotero3-acdp-488517 \
    gotero3-acdp-488517:us-central1:jackpot-staging-db

# In another terminal — get the password from Secret Manager
PGPASSWORD=$(gcloud secrets versions access latest \
    --secret=jackpot-staging-database-url \
    --project=gotero3-acdp-488517 \
    | sed -E 's|.*:([^@]+)@.*|\1|') \
psql "postgresql://jackpot@127.0.0.1:5432/jackpot_db"
```

### Rotate the database password

```bash
NEW_PASS=$(openssl rand -base64 24 | tr -d '=+/')
echo "New password (save this): $NEW_PASS"

# Rotate in Cloud SQL
gcloud sql users set-password jackpot \
    --instance=jackpot-staging-db \
    --password="$NEW_PASS" \
    --project=gotero3-acdp-488517

# Update Secret Manager — MUST include the /jackpot_db suffix
gcloud secrets versions add jackpot-staging-database-url \
    --project=gotero3-acdp-488517 \
    --data-file=- \
    <<< "postgresql://jackpot:${NEW_PASS}@10.188.230.3:5432/jackpot_db"

# Redeploy so pods pick up the new Secret
cd ~/ASU/jackpot/jackpot-iac
gh workflow run deploy-staging.yml --ref staging
```

---

## 5. Secret management

### Workflow-synced secrets

These are populated by the `Sync Kubernetes Secret from Secret Manager`
step on every deploy:

| Kubernetes key | Secret Manager secret name |
|---|---|
| `SECRET_KEY` | `jackpot-staging-secret-key` |
| `DATABASE_URL` | `jackpot-staging-database-url` |
| `GOOGLE_OAUTH_CLIENT_ID` | `jackpot-staging-google-oauth-client-id` |
| `GOOGLE_OAUTH_CLIENT_SECRET` | `jackpot-staging-google-oauth-client-secret` |
| `NCBI_API_KEY` | `jackpot-staging-ncbi-api-key` |

### Update a Secret Manager value

```bash
gcloud secrets versions add <secret-name> \
    --project=gotero3-acdp-488517 \
    --data-file=- \
    <<< "<new-value>"
```

The next workflow run will sync the new value into Kubernetes.

### IMPORTANT: don't paste secrets from other systems

Session 5 had `CROSS_REPO_PAT` (GitHub Actions secret) accidentally
overwritten with a Google OAuth client secret (`GOCSPX-` prefix). The
classes of secret are visually similar but completely different. If a
command looks like `gh secret set CROSS_REPO_PAT`, the value must start
with `ghp_` or `github_pat_`. Cross-check the prefix before pasting.

---

## 6. One-time baseline stamp for environments deployed before Q-9

Q-9 closed the bootstrap gap: `alembic upgrade head` now builds the
full schema from an empty database via the baseline migration
`5adf11b77c19`. **Fresh environments need nothing extra** — Terraform
applies, the Helm pre-upgrade migration Job runs `alembic upgrade
head`, and the schema is built.

**Environments deployed pre-Q-9** (where the legacy bootstrap Job
loaded `init.sql` and stamped Alembic at `a7fd1fcccb77`) need a
one-time stamp at the new baseline before the next deploy, so Alembic
recognises that the existing tables correspond to the baseline
revision rather than the now-orphaned `a7fd1fcccb77` head:

```bash
kubectl -n jackpot exec -it deploy/jackpot-api -- \
    /opt/venv/bin/alembic stamp 5adf11b77c19
```

After this, `helm upgrade` runs normally — the pre-upgrade migration
Job sees the chain at the baseline and applies only the deltas above
it. The `a7fd1fcccb77` rename migration is idempotent (only renames
`is_lab_admin` if the column still exists) so it's a clean no-op
against any DB built from the baseline.

---

## 7. Troubleshooting runbook

### Helm release stuck at `pending-upgrade` or `pending-install`

**Symptom:** Every deploy attempt fails immediately with no real work
done. `helm history` shows a revision stuck at `pending-*`.

**Cause:** A previous upgrade timed out (`--wait --timeout 10m`) or was
interrupted before Helm could record success or failure. Helm refuses
new upgrades on a release that's mid-transaction.

**Fix:**

```bash
# Find the last known-good revision
helm -n jackpot history jackpot-api

# Roll back to it (most recent "deployed" status row)
helm -n jackpot rollback jackpot-api <revision-number>

# Verify
helm -n jackpot status jackpot-api
# STATUS should now be "deployed"

# Now retry the upgrade
gh workflow run deploy-staging.yml --ref staging
```

### API pods in `CrashLoopBackOff`

**Always grab logs first:**

```bash
# Current attempt
kubectl -n jackpot logs -l app.kubernetes.io/name=jackpot-api --tail=100

# Previous attempt (often clearer — full traceback before restart)
kubectl -n jackpot logs -l app.kubernetes.io/name=jackpot-api --previous --tail=100

# Exit status detail
kubectl -n jackpot describe pod <pod-name> | tail -40
```

**Common causes:**

1. **ImportError from a router module.** If the traceback ends in
   `ModuleNotFoundError` (e.g. `No module named 'shared'`), the image
   is missing a directory. Check `Dockerfile.api` COPY statements.
2. **Pydantic-settings value error.** If the traceback is in
   `_settings_build_values`, a ConfigMap or Secret has a format the
   Settings class can't parse. Check the specific field named in the
   error.
3. **Cloud SQL connection failure.** If the traceback is a
   `psycopg2.OperationalError`, check DATABASE_URL in the Secret and
   the Cloud SQL instance state.

### Migration Job fails

**Symptom:** Helm upgrade fails with `pre-upgrade hooks failed: 1 error
occurred: * job jackpot-api-migrate-... failed: BackoffLimitExceeded`.

**Grab the migration pod's logs before they're garbage-collected:**

```bash
# Job may still be present
kubectl -n jackpot get jobs

# Pods may still be present too
kubectl -n jackpot get pods -l component=migrations

# Get the most recent migration pod's logs
kubectl -n jackpot logs -l component=migrations --tail=300

# If the Job is already gone, check events (retained ~1 hour)
kubectl -n jackpot get events --sort-by='.lastTimestamp' | \
    grep -i "migrate\|migration"
```

**Common causes:**

1. **Relation does not exist.** The Alembic chain assumes tables that
   aren't there. Usually means this is a fresh environment that needs
   the bootstrap Job (section 6). Once P0.1 lands, this won't happen.
2. **Password authentication failed.** DATABASE_URL Secret has a stale
   password. Rotate per section 4.
3. **Database does not exist.** DATABASE_URL points at a database name
   that Cloud SQL doesn't have. Check the URL ends with `/jackpot_db`,
   not `/jackpot`.

### Workflow fails immediately (0s elapsed)

**Cause:** YAML syntax error or schema error in `deploy-staging.yml`.

**Fix:** Validate locally. PyYAML's `safe_load` is too permissive — it
silently accepts duplicate keys that GitHub's validator rejects. Use
both:

```bash
cd ~/ASU/jackpot/jackpot-iac
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-staging.yml')); print('YAML OK')"

# Then visually eyeball the diff to spot duplicate keys or indentation issues
git diff HEAD~1 .github/workflows/deploy-staging.yml
```

### Submodule checkout fails with 403 or "terminal prompts disabled"

**Cause:** The `CROSS_REPO_PAT` GitHub Actions secret either doesn't
have access to the submodule repo, or contains the wrong token type.

**Diagnostic:** Check what's actually in the secret by adding a
temporary debug step to the workflow:

```yaml
- name: Debug PAT
  env:
    GH_PAT: ${{ secrets.CROSS_REPO_PAT }}
  run: |
    echo "PAT length: ${#GH_PAT}"
    echo "PAT prefix: ${GH_PAT:0:8}..."
    code=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $GH_PAT" \
        https://api.github.com/repos/gotero/jackpot-backend)
    echo "api.github.com status: $code"
```

**Valid GitHub PAT prefixes:**
- `ghp_` — classic PAT
- `github_pat_` — fine-grained PAT

**Invalid prefixes** (likely pasted from wrong source):
- `GOCSPX-` — Google OAuth client secret
- `AIza` — Google API key
- `sk-` — OpenAI key

If you need to replace the PAT:

```bash
gh secret set CROSS_REPO_PAT --repo gotero/jackpot-iac
# Paste the correct PAT when prompted, then Ctrl-D
```

---

## 8. Tear-down / cost controls

### Scale API nodes to zero when staging is idle

Preserves everything (Helm release, DB, buckets) while stopping the
~$280/mo Compute Engine bill.

```bash
# Scale down
gcloud container clusters resize jackpot-staging-gke \
    --num-nodes=0 --region=us-central1 --node-pool=api-pool \
    --project=gotero3-acdp-488517 --quiet

# Scale back up when needed
gcloud container clusters resize jackpot-staging-gke \
    --num-nodes=2 --region=us-central1 --node-pool=api-pool \
    --project=gotero3-acdp-488517 --quiet
```

### Stop Cloud SQL for longer idle periods

Additional ~$50-60/mo savings. Instance storage is preserved.

```bash
# Stop
gcloud sql instances patch jackpot-staging-db \
    --activation-policy=NEVER --project=gotero3-acdp-488517

# Restart (~2 min to come back up)
gcloud sql instances patch jackpot-staging-db \
    --activation-policy=ALWAYS --project=gotero3-acdp-488517
```

### Do NOT `terraform destroy` casually

Rebuilding staging means re-running the bootstrap Job, re-validating the
PAT scope on GitHub, re-applying all migrations. ~1 hour of work to
recover. Only destroy if you're walking away for weeks and the
~$400/mo run-rate matters more than the recovery time.

---

## 9. Quick-reference commands

```bash
# Show Helm release status
helm -n jackpot status jackpot-api

# Show all recent revisions
helm -n jackpot history jackpot-api

# Show what values the release is running with
helm -n jackpot get values jackpot-api

# Show all deployed resources
kubectl -n jackpot get all

# Check ConfigMap contents (confirm env vars rendered correctly)
kubectl -n jackpot get configmap jackpot-api-config -o yaml

# Check which image is running
kubectl -n jackpot get deployment jackpot-api \
    -o jsonpath='{.spec.template.spec.containers[0].image}'; echo

# Tail API logs
kubectl -n jackpot logs -l app.kubernetes.io/name=jackpot-api -f

# Exec into a running API pod
POD=$(kubectl -n jackpot get pod -l app.kubernetes.io/name=jackpot-api \
    -o jsonpath='{.items[0].metadata.name}')
kubectl -n jackpot exec -it $POD -- /bin/bash
```
