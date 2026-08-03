# Deploy

Infrastructure-as-code and deployment tooling for the JACKPOT pathogen genomics
platform: Terraform modules, Helm charts, and operational scripts that stand up
and maintain a JACKPOT environment on GCP.

This directory is operator-agnostic per Critical Rule 55. Real project IDs,
regions, resource names, and service account emails are supplied at deploy time
and are never committed here.

## Layout

Paths below are rooted at `deploy/`. CI workflows live at the repo root under
`.github/workflows/`, not in this directory.

```
terraform/
  modules/
    network/             VPC, subnet, Cloud Router, Cloud NAT, PSC for Cloud SQL
    cloud-sql/           Cloud SQL Postgres 16, private IP, PITR, daily backups
    gke/                 GKE cluster and 3 node pools (api/workspace/scrubber)
    gcs-buckets/         The 7 JACKPOT buckets plus versioning/lock/lifecycle
    artifact-registry/   Docker repo for backend images
    iam/                 Service accounts, IAM bindings, Workload Identity
    secrets/             Secret Manager entries (metadata only, no values)
  staging/               Thin wrapper that calls every module with staging vars
  production/            Same shape, different vars
helm/
  jackpot-api/           Backend Deployment, Service, ConfigMap, migration Job
scripts/
  bootstrap_project.sh   One-time GCP setup: APIs, state bucket, deploy SA, WIF
  staging_smoke_test.sh  Post-deploy smoke test
docs/
  staging_access.md      How to reach staging, who has access, how to redeploy
  production_runbook.md  Production operations runbook
  .env.staging.example   Local-dev env var template
```

## CI

The deploy pipeline is defined at the repo root:

- `.github/workflows/deploy-staging.yml`: build, push, migrate, helm upgrade,
  triggered on push to the `staging` branch.
- `.github/workflows/deploy-production.yml`: production deploy behind an
  approval gate.

Both authenticate to GCP via Workload Identity Federation and read
operator-specific identifiers from environment-scoped GitHub Actions vars.

## Operator naming

Real project IDs, regions, bucket names, and service account emails are not
stored in this repo. They come from the operator's `jackpot init` configuration
and from the `staging` and `production` GitHub Actions environment vars
(`GCP_PROJECT_ID`, `GCP_REGION`, `GCP_CLUSTER_NAME`, `GCP_NAMESPACE`,
`GCP_SECRET_PREFIX`, and the Workload Identity settings). Terraform reads them
from a gitignored `terraform.tfvars` or from `-var` flags at apply time. Nothing
operator-specific belongs in a tracked file; update the deploy-time inputs, not
a checked-in doc.

## One-time bootstrap

Before `terraform apply` can run, the GCP project needs APIs enabled, a
Terraform state bucket, and a deploy service account. Run:

```bash
./deploy/scripts/bootstrap_project.sh <your-gcp-project-id> us-central1 staging <your-github-org>
```

See the script for details. It is idempotent and safe to re-run.

## Standard workflow (staging)

```bash
cd deploy/terraform/staging
terraform init      # reads backend config from backend.tf
terraform plan      # review
terraform apply     # creates real resources, costs money
```

After apply, seed the Secret Manager values (full checklist in
`deploy/docs/staging_access.md`):

```bash
echo -n "$(openssl rand -hex 32)" | gcloud secrets versions add \
    jackpot-staging-secret-key --data-file=- --project=<your-gcp-project-id>
```

## Runbooks

- Staging access, redeploy, and troubleshooting: `deploy/docs/staging_access.md`
- Production approval gate and deploy: `docs/deploy/production-deploy.md`
- Point-in-time restore drill: `docs/deploy/pitr-restore-drill.md`
