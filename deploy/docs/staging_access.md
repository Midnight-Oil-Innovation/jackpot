# Staging access

Quick reference for reaching a JACKPOT staging environment, who has
access, what the endpoints are, and how to redeploy.

This runbook is operator-agnostic per Critical Rule 55. Replace the
`<placeholder>` values with whatever your operator actually uses
(GCP project ID, hostnames, etc.). The values come from the operator's
`jackpot init` configuration (P0e) and from the GitHub Actions
environment variables documented in `docs/deploy/production-deploy.md`.

## Endpoints

| Endpoint | URL |
|---|---|
| API (TLS) | `https://api.staging.<your-jackpot-domain>` |
| Health check | `https://api.staging.<your-jackpot-domain>/health` |
| OpenAPI | `https://api.staging.<your-jackpot-domain>/openapi.json` |
| Frontend | `https://staging.<your-jackpot-domain>` *(Month 2+)* |

The hostnames are operator-specific. Set `STAGING_JACKPOT_API_URL` and
`STAGING_CORS_ORIGINS` in the repo's `staging` GitHub environment vars;
the deploy workflow plumbs them through to the running API. Update DNS
records (Cloud DNS / Route53 / Cloudflare etc.) at the same time.

## GCP project

| | |
|---|---|
| Project ID | `<your-gcp-project>` |
| Region | `us-central1` (or operator's choice — set `GCP_REGION`) |
| Backups region | `us-east1` |
| GKE cluster | `<your-gke-cluster>` (set `GCP_CLUSTER_NAME`) |
| Cloud SQL instance | `jackpot-staging-db` |
| Artifact Registry | `<region>-docker.pkg.dev/<your-gcp-project>/jackpot` |
| Namespace | `<your-namespace>` (set `GCP_NAMESPACE`) |

## Who has access

| Role | Principal | Granted via |
|---|---|---|
| Project Owner | `<operator-bootstrap-account>` | Manual — bootstrap account |
| GitHub Actions deploy | `jackpot-staging-deploy@<project>.iam.gserviceaccount.com` SA | Workload Identity Federation (`<github-org>/<repo>`) |
| Backend pod workload identity | `jackpot-api@<project>.iam.gserviceaccount.com` SA | KSA `<namespace>/jackpot-api` |
| Nextflow controllers | `jackpot-nextflow@<project>.iam.gserviceaccount.com` SA | KSA `<namespace>/jackpot-nextflow` |
| Scrubber GKE Jobs | `jackpot-scrubber@<project>.iam.gserviceaccount.com` SA | KSA `<namespace>/jackpot-scrubber` |

Add new human users at the project IAM level — never add them to the
deploy SA's impersonation set.

## First-time setup (local)

```bash
gcloud auth login
gcloud config set project <your-gcp-project>

# GKE credentials for kubectl / helm / k9s
gcloud container clusters get-credentials <your-gke-cluster> \
    --region us-central1
```

## Seeding secret values after `terraform apply`

After the staging Terraform is applied, the Secret Manager resources
exist but have no versions. Populate them with:

```bash
# Copy-paste from `terraform output secret_seed_commands` and replace
# REPLACE_ME with real values before running.

PROJECT_ID=<your-gcp-project>

echo -n "$(openssl rand -hex 32)" | gcloud secrets versions add \
    jackpot-staging-secret-key --data-file=- --project=$PROJECT_ID

# DATABASE_URL format: postgresql://jackpot:<password>@<private-ip>:5432/jackpot_db
# Private IP comes from `terraform output cloudsql_private_ip`.
echo -n "postgresql://jackpot:<DB_PASSWORD>@<PRIVATE_IP>:5432/jackpot_db" | \
    gcloud secrets versions add jackpot-staging-database-url \
    --data-file=- --project=$PROJECT_ID

echo -n "<google-oauth-client-id>" | gcloud secrets versions add \
    jackpot-staging-google-oauth-client-id --data-file=- --project=$PROJECT_ID

echo -n "<google-oauth-client-secret>" | gcloud secrets versions add \
    jackpot-staging-google-oauth-client-secret --data-file=- --project=$PROJECT_ID

echo -n "<ncbi-api-key>" | gcloud secrets versions add \
    jackpot-staging-ncbi-api-key --data-file=- --project=$PROJECT_ID

echo -n "<gisaid-username>" | gcloud secrets versions add \
    jackpot-staging-gisaid-username --data-file=- --project=$PROJECT_ID

echo -n "<gisaid-password>" | gcloud secrets versions add \
    jackpot-staging-gisaid-password --data-file=- --project=$PROJECT_ID
```

Rotate the Cloud SQL user password separately:

```bash
gcloud sql users set-password jackpot \
    --instance=jackpot-staging-db \
    --password='<new-password>'
```

Then update the `jackpot-staging-database-url` secret with the new value.

## Redeploying the API

Three paths:

1. **Push to `staging` branch** — triggers
   `.github/workflows/deploy-staging.yml`.
2. **Manual workflow dispatch** — GitHub Actions → `deploy-staging` →
   Run workflow → optionally pass `image_tag` input.
3. **Local** (emergency only):

   ```bash
   PROJECT_ID=<your-gcp-project>
   IMAGE=us-central1-docker.pkg.dev/$PROJECT_ID/jackpot/jackpot-api:$(git rev-parse --short HEAD)
   docker build -f Dockerfile.api -t "$IMAGE" .
   docker push "$IMAGE"

   kubectl create namespace <your-namespace> --dry-run=client -o yaml | kubectl apply -f -

   helm upgrade --install jackpot-api ./helm/jackpot-api \
       --namespace <your-namespace> \
       --values ./helm/jackpot-api/values-staging.yaml \
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
    ./scripts/staging_smoke_test.sh

# Smoke test with cluster-level checks
PROJECT_ID=<your-gcp-project> \
    GKE_CLUSTER=<your-gke-cluster> \
    GKE_REGION=us-central1 \
    JACKPOT_API_URL="$JACKPOT_API_URL" \
    ./scripts/staging_smoke_test.sh --check-kube --check-buckets
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

## Database access

```bash
# From a Compute Engine VM or Cloud Shell in the same VPC
psql "postgresql://jackpot:<password>@<private-ip>:5432/jackpot_db"

# From laptop via Cloud SQL Auth Proxy
cloud-sql-proxy <your-gcp-project>:us-central1:jackpot-staging-db
# Then: psql "postgresql://jackpot:<password>@localhost:5432/jackpot_db"
```

## Rolling back

```bash
NAMESPACE=<your-namespace>

# Show release history
helm -n $NAMESPACE history jackpot-api

# Roll back to previous revision (runs alembic pre-upgrade hook on the
# OLD image — be careful if the schema delta isn't reversible)
helm -n $NAMESPACE rollback jackpot-api <REVISION>
```

If a migration needs to be reversed, prefer PITR over `alembic downgrade`
(see `docs/deploy/pitr-restore-drill.md` and the production runbook).

## Shutting down to save cost

This is a staging environment — it's expected to be live for active
development. If you genuinely need to pause it overnight, scale to zero:

```bash
NAMESPACE=<your-namespace>

# Zero out the API Deployment
kubectl -n $NAMESPACE scale deploy/jackpot-api --replicas=0

# Stop the Cloud SQL instance (saves ~75% — restart takes ~2 minutes)
gcloud sql instances patch jackpot-staging-db --activation-policy=NEVER

# Resume:
gcloud sql instances patch jackpot-staging-db --activation-policy=ALWAYS
kubectl -n $NAMESPACE scale deploy/jackpot-api --replicas=2
```

`terraform destroy` is NOT the right way to pause — it drops the Cloud
SQL instance, GKE cluster, and all buckets. Use the commands above.
