# Staging access

Quick reference for reaching a JACKPOT staging environment: who has access, what
the endpoints are, how to redeploy, and how to recover when a deploy goes wrong.

This runbook is operator-agnostic per Critical Rule 55. Replace the
`<placeholder>` values with whatever your operator actually uses (GCP project ID,
hostnames, cluster name, namespace). Those values come from the operator's
`jackpot init` configuration (P0e) and from the GitHub Actions environment
variables in the repo's `staging` environment. Values shown literally (the
`jackpot-staging-db` instance name, the `jackpot_db` database name, the
`jackpot` DB user, secret-name suffixes) are JACKPOT conventions set by the
Terraform modules, not operator identity, so they are safe to keep as written.

Secret names use the `${GCP_SECRET_PREFIX}` prefix, default `jackpot-staging`.
If your operator set a different prefix, adjust the secret names below to match.

## Endpoints

| Endpoint | URL |
|---|---|
| API (TLS) | `https://api.staging.<your-jackpot-domain>` |
| Health check | `https://api.staging.<your-jackpot-domain>/health` |
| OpenAPI | `https://api.staging.<your-jackpot-domain>/openapi.json` |
| Frontend | `https://staging.<your-jackpot-domain>` *(Month 2+)* |

The hostnames are operator-specific. Set `STAGING_JACKPOT_API_URL` and
`STAGING_CORS_ORIGINS` in the repo's `staging` GitHub environment vars; the
deploy workflow plumbs them through to the running API. Update DNS records
(Cloud DNS, Route53, Cloudflare, or whatever the operator uses) at the same
time.

## GCP project

| | |
|---|---|
| Project ID | `<your-gcp-project>` (set `GCP_PROJECT_ID`) |
| Region | `us-central1`, or operator's choice (set `GCP_REGION`) |
| Backups region | `us-east1` |
| GKE cluster | `<your-gke-cluster>` (set `GCP_CLUSTER_NAME`) |
| Cloud SQL instance | `jackpot-staging-db` |
| Cloud SQL database | `jackpot_db` |
| Cloud SQL private IP | from `terraform output cloudsql_private_ip` |
| Artifact Registry | `<region>-docker.pkg.dev/<your-gcp-project>/jackpot` |
| Namespace | `<your-namespace>` (set `GCP_NAMESPACE`) |

## Who has access

| Role | Principal | Granted via |
|---|---|---|
| Project Owner | `<operator-bootstrap-account>` | Manual, bootstrap account |
| GitHub Actions deploy | `jackpot-staging-deploy@<project>.iam.gserviceaccount.com` SA | Workload Identity Federation (`<github-org>/<repo>`) |
| Backend pod workload identity | `jackpot-api@<project>.iam.gserviceaccount.com` SA | KSA `<namespace>/jackpot-api` |
| Nextflow controllers | `jackpot-nextflow@<project>.iam.gserviceaccount.com` SA | KSA `<namespace>/jackpot-nextflow` |
| Scrubber GKE Jobs | `jackpot-scrubber@<project>.iam.gserviceaccount.com` SA | KSA `<namespace>/jackpot-scrubber` |

Add new human users at the project IAM level. Never add them to the deploy SA's
impersonation set.

## First-time setup (local)

```bash
gcloud auth login
gcloud config set project <your-gcp-project>

# GKE credentials for kubectl / helm / k9s
gcloud container clusters get-credentials <your-gke-cluster> \
    --region us-central1
```

## If `kubectl` hangs: authorized networks

`get-credentials` talks to `container.googleapis.com` and will succeed even when
you cannot reach the cluster — the first real symptom is `kubectl` hanging until
timeout, which reads like a flake rather than a refusal.

The control-plane endpoint only accepts the CIDRs in
`master_authorized_networks`, and an empty list accepts none. That is
deliberate (the module used to leave the endpoint open to `0.0.0.0/0` whenever
the list was empty), but it applies to break-glass access too — including the
Rule 49 `helm rollback` for a release wedged in `pending-upgrade`, at exactly
the moment you least want an IAM detour.

Confirm that is what you are hitting, then add your address:

```bash
# Is the endpoint refusing you, or is something else wrong?
# masterAuthorizedNetworksConfig is the deprecated field; ask for both so
# this works against current and older clusters. A diagnostic that prints
# nothing reads as "no restriction configured", which is the wrong answer.
gcloud container clusters describe <cluster> --region <region> \
    --format='value(controlPlaneEndpointsConfig.ipEndpointsConfig.authorizedNetworksConfig,
                    masterAuthorizedNetworksConfig)'

# Your current egress address
# -4 is not optional: on a dual-stack host curl may return an IPv6 address,
# and appending /32 to one authorises a prefix rather than your host — on a
# field GKE expects to hold IPv4 CIDRs to begin with.
curl -4 -sS https://ifconfig.me

# Add it in terraform.tfvars and apply — not in the console, which
# terraform will revert on the next run (Critical Rule 37).
#   master_authorized_networks = [
#     { cidr_block = "<your-ip>/32", display_name = "operator-break-glass" },
#   ]
```

A home or cafe address is as dynamic as a runner's. If you need reliable
incident access, the durable answers are Connect Gateway or a bastion with a
static egress IP, not a growing list of `/32`s.

## Seeding secret values after `terraform apply`

After the staging Terraform is applied, the Secret Manager resources exist but
have no versions. Populate them with:

```bash
PROJECT_ID=<your-gcp-project>

echo -n "$(openssl rand -hex 32)" | gcloud secrets versions add \
    jackpot-staging-secret-key --data-file=- --project=$PROJECT_ID

# DATABASE_URL format: postgresql://jackpot:<password>@<private-ip>:5432/jackpot_db
# Private IP comes from `terraform output cloudsql_private_ip`.
# The /jackpot_db suffix is mandatory (see "Database access" below).
echo -n "postgresql://jackpot:<DB_PASSWORD>@<PRIVATE_IP>:5432/jackpot_db" | \
    gcloud secrets versions add jackpot-staging-database-url \
    --data-file=- --project=$PROJECT_ID

echo -n "<google-oauth-client-id>" | gcloud secrets versions add \
    jackpot-staging-google-oauth-client-id --data-file=- --project=$PROJECT_ID

echo -n "<google-oauth-client-secret>" | gcloud secrets versions add \
    jackpot-staging-google-oauth-client-secret --data-file=- --project=$PROJECT_ID

echo -n "<ncbi-api-key>" | gcloud secrets versions add \
    jackpot-staging-ncbi-api-key --data-file=- --project=$PROJECT_ID
```

Verify each secret value against its expected format before you seed it. The
secret classes are visually similar but not interchangeable, and a value in the
wrong slot fails at runtime as a confusing auth error rather than a clear one:

- Google OAuth client secret starts with `GOCSPX-`.
- Google OAuth client ID ends with `.apps.googleusercontent.com`.
- Google API key starts with `AIza`.
- A GitHub PAT (if you seed one for any reason) starts with `ghp_` or
  `github_pat_`, never `GOCSPX-`.

Cross-check the prefix before pasting.

## Database access

The database name is `jackpot_db`, not `jackpot`. Dropping the `_db` suffix
produces auth and connection failures that look like password problems but are
not. The name is the `db_name` default in the cloud-sql Terraform module
(`default = "jackpot_db"`); the `DATABASE_URL` secret and every direct `psql`
connection must end in `/jackpot_db`.

```bash
# From a Compute Engine VM or Cloud Shell in the same VPC
psql "postgresql://jackpot:<password>@<private-ip>:5432/jackpot_db"
```

```bash
# From a laptop via the Cloud SQL Auth Proxy (Cloud SQL is on a private IP)

# Install once
brew install cloud-sql-proxy

# Start the proxy, leave it running in one terminal
cloud-sql-proxy <your-gcp-project>:us-central1:jackpot-staging-db

# In another terminal, pull the password out of the DATABASE_URL secret
# so you never have to know or paste it
PGPASSWORD=$(gcloud secrets versions access latest \
    --secret=jackpot-staging-database-url \
    --project=<your-gcp-project> \
    | sed -E 's|.*:([^@]+)@.*|\1|') \
psql "postgresql://jackpot@127.0.0.1:5432/jackpot_db"
```

## Rotating the database password

```bash
PROJECT_ID=<your-gcp-project>
NEW_PASS=$(openssl rand -base64 24 | tr -d '=+/')
echo "New password (save this): $NEW_PASS"

# Rotate in Cloud SQL
gcloud sql users set-password jackpot \
    --instance=jackpot-staging-db \
    --password="$NEW_PASS" \
    --project=$PROJECT_ID

# Update Secret Manager. The /jackpot_db suffix is mandatory.
PRIVATE_IP=$(gcloud sql instances describe jackpot-staging-db \
    --project=$PROJECT_ID --format='value(ipAddresses[0].ipAddress)')
gcloud secrets versions add jackpot-staging-database-url \
    --project=$PROJECT_ID \
    --data-file=- \
    <<< "postgresql://jackpot:${NEW_PASS}@${PRIVATE_IP}:5432/jackpot_db"

# Redeploy so pods pick up the new Secret
gh workflow run deploy-staging.yml --ref staging
```

## Baseline stamp for environments deployed before Q-9

Q-9 closed the bootstrap gap: `alembic upgrade head` now builds the full schema
from an empty database via the baseline migration `5adf11b77c19`. Fresh
environments need nothing extra. Terraform applies, the Helm pre-upgrade
migration Job runs `alembic upgrade head`, and the schema is built.

Environments deployed before Q-9 (where the legacy bootstrap Job loaded
`init.sql` and stamped Alembic at `a7fd1fcccb77`) need a one-time stamp at the
new baseline before the next deploy, so Alembic recognizes that the existing
tables correspond to the baseline revision rather than the now-orphaned
`a7fd1fcccb77` head:

```bash
kubectl -n <your-namespace> exec -it deploy/jackpot-api -- \
    /opt/venv/bin/alembic stamp 5adf11b77c19
```

After this, `helm upgrade` runs normally: the pre-upgrade migration Job sees the
chain at the baseline and applies only the deltas above it. The `a7fd1fcccb77`
rename migration is idempotent (it only renames `is_lab_admin` if the column
still exists) so it is a clean no-op against any DB built from the baseline.

## Redeploying the API

Three paths:

1. **Push to `staging` branch**, which triggers
   `.github/workflows/deploy-staging.yml`.
2. **Manual workflow dispatch**: GitHub Actions, `deploy-staging`, Run workflow,
   optionally pass an `image_tag` input.
3. **Local** (emergency only):

   ```bash
   PROJECT_ID=<your-gcp-project>
   NAMESPACE=<your-namespace>
   IMAGE=us-central1-docker.pkg.dev/$PROJECT_ID/jackpot/jackpot-api:$(git rev-parse --short HEAD)
   docker build -f backend/Dockerfile.api -t "$IMAGE" backend
   docker push "$IMAGE"

   kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

   helm upgrade --install jackpot-api ./deploy/helm/jackpot-api \
       --namespace "$NAMESPACE" \
       --values ./deploy/helm/jackpot-api/values-staging.yaml \
       --set image.repository="us-central1-docker.pkg.dev/$PROJECT_ID/jackpot/jackpot-api" \
       --set image.tag="$(git rev-parse --short HEAD)" \
       --set serviceAccount.gcpServiceAccountEmail="jackpot-api@$PROJECT_ID.iam.gserviceaccount.com" \
       --set env.GCP_PROJECT_ID="$PROJECT_ID" \
       --set env.JACKPOT_API_URL="https://api.staging.<your-jackpot-domain>" \
       --set env.CORS_ORIGINS="https://staging.<your-jackpot-domain>" \
       --wait --timeout 10m
   ```

## Verifying a deploy

```bash
JACKPOT_API_URL=https://api.staging.<your-jackpot-domain>

# Health
curl -s "$JACKPOT_API_URL/health" | jq

# Full smoke test (from repo root)
JACKPOT_API_URL="$JACKPOT_API_URL" \
    ./deploy/scripts/staging_smoke_test.sh

# Smoke test with cluster-level checks
PROJECT_ID=<your-gcp-project> \
    GKE_CLUSTER=<your-gke-cluster> \
    GKE_REGION=us-central1 \
    JACKPOT_API_URL="$JACKPOT_API_URL" \
    ./deploy/scripts/staging_smoke_test.sh --check-kube --check-buckets
```

## Tailing logs

```bash
NAMESPACE=<your-namespace>
PROJECT_ID=<your-gcp-project>
GKE_CLUSTER=<your-gke-cluster>

# API logs
kubectl -n $NAMESPACE logs -f deploy/jackpot-api

# Alembic migration Job (most recent)
kubectl -n $NAMESPACE logs job/$(kubectl -n $NAMESPACE get jobs \
    -l component=migrations -o jsonpath='{.items[-1:].metadata.name}')

# Cloud Logging via gcloud
gcloud logging read "resource.type=\"k8s_container\" resource.labels.cluster_name=\"$GKE_CLUSTER\"" \
    --project=$PROJECT_ID --limit=50 --format=json
```

## Troubleshooting

### Helm release stuck at `pending-upgrade` or `pending-install`

**Symptom:** Every deploy attempt fails immediately with no real work done.
`helm history` shows a revision stuck at `pending-*`.

**Cause:** A previous upgrade timed out (`--wait --timeout 10m`) or was
interrupted before Helm could record success or failure. Helm refuses new
upgrades on a release that is mid-transaction.

**Fix:**

```bash
NAMESPACE=<your-namespace>

# Find the last known-good revision
helm -n $NAMESPACE history jackpot-api

# Roll back to it (most recent row with "deployed" status)
helm -n $NAMESPACE rollback jackpot-api <revision-number>

# Verify: STATUS should now be "deployed"
helm -n $NAMESPACE status jackpot-api

# Retry the upgrade
gh workflow run deploy-staging.yml --ref staging
```

### API pods in `CrashLoopBackOff`

Always grab logs first:

```bash
NAMESPACE=<your-namespace>

# Current attempt
kubectl -n $NAMESPACE logs -l app.kubernetes.io/name=jackpot-api --tail=100

# Previous attempt (often clearer, full traceback before restart)
kubectl -n $NAMESPACE logs -l app.kubernetes.io/name=jackpot-api --previous --tail=100

# Exit status detail
kubectl -n $NAMESPACE describe pod <pod-name> | tail -40
```

**Common causes:**

1. **ImportError from a router module.** If the traceback ends in
   `ModuleNotFoundError` (for example `No module named 'shared'`), the image is
   missing a directory. Check the `COPY` statements in `backend/Dockerfile.api`.
2. **Pydantic-settings value error.** If the traceback is in
   `_settings_build_values`, a ConfigMap or Secret has a format the Settings
   class cannot parse. Check the specific field named in the error.
3. **Cloud SQL connection failure.** If the traceback is a
   `psycopg2.OperationalError`, check `DATABASE_URL` in the Secret and the Cloud
   SQL instance state.

### Migration Job fails

**Symptom:** Helm upgrade fails with `pre-upgrade hooks failed: 1 error
occurred: * job jackpot-api-migrate-... failed: BackoffLimitExceeded`.

Grab the migration pod's logs before they are garbage-collected:

```bash
NAMESPACE=<your-namespace>

# Job and pods may still be present
kubectl -n $NAMESPACE get jobs
kubectl -n $NAMESPACE get pods -l component=migrations

# Most recent migration pod's logs
kubectl -n $NAMESPACE logs -l component=migrations --tail=300

# If the Job is already gone, check events (retained ~1 hour)
kubectl -n $NAMESPACE get events --sort-by='.lastTimestamp' | \
    grep -i "migrate\|migration"
```

**Common causes:**

1. **Relation does not exist.** On a fresh environment this should not happen
   post-Q-9, since `alembic upgrade head` builds the full schema from empty via
   baseline `5adf11b77c19`. If you see it, the migration Job is likely running
   an image built before Q-9, or the DB was partially initialized. For an
   environment deployed before Q-9, apply the one-time stamp (see "Baseline
   stamp for environments deployed before Q-9").
2. **Password authentication failed.** The `DATABASE_URL` Secret has a stale
   password. Rotate per "Rotating the database password."
3. **Database does not exist.** `DATABASE_URL` points at a database name Cloud
   SQL does not have. Check the URL ends with `/jackpot_db`, not `/jackpot`.

### Workflow fails immediately (0s elapsed)

**Cause:** YAML syntax error or schema error in `deploy-staging.yml`.

**Fix:** Validate locally. PyYAML's `safe_load` is too permissive; it silently
accepts duplicate keys that GitHub's validator rejects. Use both:

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-staging.yml')); print('YAML OK')"

# Then eyeball the diff for duplicate keys or indentation issues
git diff HEAD~1 .github/workflows/deploy-staging.yml
```

## Rolling back

```bash
NAMESPACE=<your-namespace>

# Show release history
helm -n $NAMESPACE history jackpot-api

# Roll back to a previous revision. This runs the alembic pre-upgrade hook on
# the OLD image, so be careful if the schema delta is not reversible.
helm -n $NAMESPACE rollback jackpot-api <REVISION>
```

If a migration needs to be reversed, prefer PITR over `alembic downgrade` (see
`docs/deploy/pitr-restore-drill.md` and the production runbook).

## Shutting down to save cost

This is a staging environment, expected to be live during active development.
Pick the lever that matches how long you are pausing.

```bash
NAMESPACE=<your-namespace>
PROJECT_ID=<your-gcp-project>

# Quick pause: zero out the API Deployment. Nodes stay up, so this stops the
# app but not the node bill.
kubectl -n $NAMESPACE scale deploy/jackpot-api --replicas=0

# Real cost saving: resize the api node pool to zero. This stops the Compute
# Engine node charge while preserving the Helm release, DB, and buckets.
gcloud container clusters resize <your-gke-cluster> \
    --num-nodes=0 --region=us-central1 --node-pool=api-pool \
    --project=$PROJECT_ID --quiet

# Scale back up when you return
gcloud container clusters resize <your-gke-cluster> \
    --num-nodes=2 --region=us-central1 --node-pool=api-pool \
    --project=$PROJECT_ID --quiet

# Longer idle: stop the Cloud SQL instance too (saves ~75%, restart ~2 min).
# Storage is preserved.
gcloud sql instances patch jackpot-staging-db \
    --activation-policy=NEVER --project=$PROJECT_ID
gcloud sql instances patch jackpot-staging-db \
    --activation-policy=ALWAYS --project=$PROJECT_ID
```

Do not `terraform destroy` to pause. It drops the Cloud SQL instance, the GKE
cluster, and all buckets, and rebuilding staging (re-apply, re-validate IAM,
re-seed secrets, re-run migrations) is about an hour of work to recover. Only
destroy if you are walking away for weeks and the run-rate matters more than the
recovery time.

## Quick reference

```bash
NAMESPACE=<your-namespace>

# Helm release status, history, and running values
helm -n $NAMESPACE status jackpot-api
helm -n $NAMESPACE history jackpot-api
helm -n $NAMESPACE get values jackpot-api

# All deployed resources
kubectl -n $NAMESPACE get all

# Confirm env vars rendered correctly
kubectl -n $NAMESPACE get configmap jackpot-api-config -o yaml

# Which image is running
kubectl -n $NAMESPACE get deployment jackpot-api \
    -o jsonpath='{.spec.template.spec.containers[0].image}'; echo

# Tail API logs
kubectl -n $NAMESPACE logs -l app.kubernetes.io/name=jackpot-api -f

# Exec into a running API pod
POD=$(kubectl -n $NAMESPACE get pod -l app.kubernetes.io/name=jackpot-api \
    -o jsonpath='{.items[0].metadata.name}')
kubectl -n $NAMESPACE exec -it $POD -- /bin/bash
```
