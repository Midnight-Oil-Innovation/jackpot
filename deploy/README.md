# jackpot-iac

Infrastructure-as-code for the JACKPOT pathogen genomics platform. Contains
Terraform modules, Helm charts, CI workflows, and operational scripts that
stand up and maintain a JACKPOT environment on GCP.

## Layout

```
terraform/
  modules/
    network/              VPC, subnet, Cloud Router, Cloud NAT, PSC for Cloud SQL
    cloud-sql/            Cloud SQL Postgres 16, private IP, PITR, daily backups
    gke/                  GKE cluster + 3 node pools (api/workspace/scrubber)
    gcs-buckets/          The 7 JACKPOT buckets + versioning/lock/lifecycle
    artifact-registry/    Docker repo for backend images
    iam/                  Service accounts + IAM bindings, Workload Identity
    secrets/              Secret Manager entries (metadata only — no values)
  staging/                Thin wrapper that calls every module with staging vars
  production/             Month 3 — same shape, different vars (currently stub)
helm/
  jackpot-api/            Backend Deployment, Service, ConfigMap, migration Job
.github/workflows/
  deploy-staging.yml      Build → push → migrate → helm upgrade (on push staging)
scripts/
  bootstrap_project.sh    One-time GCP setup: APIs, state bucket, deploy SA, WIF
  staging_smoke_test.sh   Post-deploy smoke test
docs/
  staging_access.md       How to reach staging, who has access, how to redeploy
  production_runbook.md   Month 3 stub
```

## Canonical naming

All project IDs, regions, bucket names, service account emails, and labels
come from [`../jackpot-backend/docs/gcp_context.md`](../jackpot-backend/docs/gcp_context.md).
Terraform variables mirror that document — update the doc first when naming
changes, then mirror in `terraform.tfvars`.

## One-time bootstrap

Before `terraform apply` can run, the GCP project needs APIs enabled, a
Terraform state bucket, and a deploy service account. Run:

```bash
./scripts/bootstrap_project.sh <your-gcp-project-id> us-central1 staging <your-github-org>
```

See the script for details. It is idempotent and safe to re-run.

## Standard workflow

```bash
cd terraform/staging
terraform init      # reads backend config from backend.tf
terraform plan      # review
terraform apply     # creates real resources — costs money
```

After apply, populate secret values:

```bash
echo -n "$(openssl rand -hex 32)" | gcloud secrets versions add \
    jackpot-staging-secret-key --data-file=- --project=<your-gcp-project-id>
```

See `docs/staging_access.md` for the full secret-seeding checklist and
endpoint URLs.

## Environments

Operators configure their per-environment GCP projects via the
`staging` and `production` GitHub Actions environment vars
(`GCP_PROJECT_ID`, `GCP_REGION`, etc.). See
`docs/deploy/production-deploy.md` for the production approval gate
runbook and `docs/staging_access.md` for the staging variant.
