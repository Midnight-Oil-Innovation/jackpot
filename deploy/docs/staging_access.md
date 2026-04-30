# Staging access

Quick reference for reaching the JACKPOT staging environment, who has
access, what the endpoints are, and how to redeploy.

## Endpoints

| Endpoint | URL |
|---|---|
| API (TLS) | `https://api.staging.jackpot.example.org` |
| Health check | `https://api.staging.jackpot.example.org/health` |
| OpenAPI | `https://api.staging.jackpot.example.org/openapi.json` |
| Frontend | `https://staging.jackpot.example.org` *(Month 2+)* |

The staging hostnames above are placeholders. Update them here and in
`helm/jackpot-api/values-staging.yaml` once the DNS records are cut.

## GCP project

| | |
|---|---|
| Project ID | `gotero3-acdp-488517` |
| Region | `us-central1` |
| Backups region | `us-east1` |
| GKE cluster | `jackpot-staging-gke` |
| Cloud SQL instance | `jackpot-staging-db` |
| Artifact Registry | `us-central1-docker.pkg.dev/gotero3-acdp-488517/jackpot` |
| Namespace | `jackpot` |

## Who has access

| Role | Principal | Granted via |
|---|---|---|
| Project Owner | `gotero3@asu.edu` | Manual — bootstrap account |
| GitHub Actions deploy | `jackpot-staging-deploy@...` SA | Workload Identity Federation (`gotero/jackpot-iac` repo) |
| Backend pod workload identity | `jackpot-api@...` SA | KSA `jackpot/jackpot-api` |
| Nextflow controllers | `jackpot-nextflow@...` SA | KSA `jackpot/jackpot-nextflow` |
| Scrubber GKE Jobs | `jackpot-scrubber@...` SA | KSA `jackpot/jackpot-scrubber` |

Add new human users at the project IAM level — never add them to the
deploy SA's impersonation set.

## First-time setup (local)

```bash
gcloud auth login
gcloud config set project gotero3-acdp-488517

# GKE credentials for kubectl / helm / k9s
gcloud container clusters get-credentials jackpot-staging-gke \
    --region us-central1
```

## Seeding secret values after `terraform apply`

After the staging Terraform is applied, the Secret Manager resources
exist but have no versions. Populate them with:

```bash
# Copy-paste from `terraform output secret_seed_commands` and replace
# REPLACE_ME with real values before running.

echo -n "$(openssl rand -hex 32)" | gcloud secrets versions add \
    jackpot-staging-secret-key --data-file=- --project=gotero3-acdp-488517

# DATABASE_URL format: postgresql://jackpot:<password>@<private-ip>:5432/jackpot_db
# Private IP comes from `terraform output cloudsql_private_ip`.
echo -n "postgresql://jackpot:<DB_PASSWORD>@<PRIVATE_IP>:5432/jackpot_db" | \
    gcloud secrets versions add jackpot-staging-database-url \
    --data-file=- --project=gotero3-acdp-488517

echo -n "<google-oauth-client-id>" | gcloud secrets versions add \
    jackpot-staging-google-oauth-client-id --data-file=- --project=gotero3-acdp-488517

echo -n "<google-oauth-client-secret>" | gcloud secrets versions add \
    jackpot-staging-google-oauth-client-secret --data-file=- --project=gotero3-acdp-488517

echo -n "<ncbi-api-key>" | gcloud secrets versions add \
    jackpot-staging-ncbi-api-key --data-file=- --project=gotero3-acdp-488517

echo -n "<gisaid-username>" | gcloud secrets versions add \
    jackpot-staging-gisaid-username --data-file=- --project=gotero3-acdp-488517

echo -n "<gisaid-password>" | gcloud secrets versions add \
    jackpot-staging-gisaid-password --data-file=- --project=gotero3-acdp-488517
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

1. **Push to `staging` branch of `jackpot-backend`** — triggers
   `.github/workflows/deploy-staging.yml`.
2. **Manual workflow dispatch** — GitHub Actions → `deploy-staging` →
   Run workflow → optionally pass `image_tag` input.
3. **Local** (emergency only):

   ```bash
   IMAGE=us-central1-docker.pkg.dev/gotero3-acdp-488517/jackpot/jackpot-api:$(git rev-parse --short HEAD)
   docker build -f Dockerfile.api -t "$IMAGE" .
   docker push "$IMAGE"

   kubectl create namespace jackpot --dry-run=client -o yaml | kubectl apply -f -

   helm upgrade --install jackpot-api ./helm/jackpot-api \
       --namespace jackpot \
       --values ./helm/jackpot-api/values-staging.yaml \
       --set image.tag="$(git rev-parse --short HEAD)" \
       --wait --timeout 10m
   ```

## Verifying a deploy

```bash
# Health
curl -s https://api.staging.jackpot.example.org/health | jq

# Full smoke test (from repo root)
JACKPOT_API_URL=https://api.staging.jackpot.example.org \
    ./scripts/staging_smoke_test.sh

# Smoke test with cluster-level checks
PROJECT_ID=gotero3-acdp-488517 \
    GKE_CLUSTER=jackpot-staging-gke \
    GKE_REGION=us-central1 \
    JACKPOT_API_URL=https://api.staging.jackpot.example.org \
    ./scripts/staging_smoke_test.sh --check-kube --check-buckets
```

## Tailing logs

```bash
# API logs
kubectl -n jackpot logs -f deploy/jackpot-api

# Alembic migration Job (most recent)
kubectl -n jackpot logs job/$(kubectl -n jackpot get jobs \
    -l component=migrations -o jsonpath='{.items[-1:].metadata.name}')

# Cloud Logging via gcloud
gcloud logging read 'resource.type="k8s_container" resource.labels.cluster_name="jackpot-staging-gke"' \
    --project=gotero3-acdp-488517 --limit=50 --format=json
```

## Database access

```bash
# From a Compute Engine VM or Cloud Shell in the same VPC
psql "postgresql://jackpot:<password>@<private-ip>:5432/jackpot_db"

# From laptop via Cloud SQL Auth Proxy
cloud-sql-proxy gotero3-acdp-488517:us-central1:jackpot-staging-db
# Then: psql "postgresql://jackpot:<password>@localhost:5432/jackpot_db"
```

## Rolling back

```bash
# Show release history
helm -n jackpot history jackpot-api

# Roll back to previous revision (runs alembic pre-upgrade hook on the
# OLD image — be careful if the schema delta isn't reversible)
helm -n jackpot rollback jackpot-api <REVISION>
```

If a migration needs to be reversed, prefer PITR over `alembic downgrade`
(see `docs/production_runbook.md` → Disaster Recovery).

## Shutting down to save cost

This is a staging environment — it's expected to be live for active
development. If you genuinely need to pause it overnight, scale to zero:

```bash
# Zero out the API Deployment
kubectl -n jackpot scale deploy/jackpot-api --replicas=0

# Stop the Cloud SQL instance (saves ~75% — restart takes ~2 minutes)
gcloud sql instances patch jackpot-staging-db --activation-policy=NEVER

# Resume:
gcloud sql instances patch jackpot-staging-db --activation-policy=ALWAYS
kubectl -n jackpot scale deploy/jackpot-api --replicas=2
```

`terraform destroy` is NOT the right way to pause — it drops the Cloud
SQL instance, GKE cluster, and all buckets. Use the commands above.
