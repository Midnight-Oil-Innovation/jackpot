# Production runbook — Month 3 stub

This runbook is a placeholder. Fill it in when the production project ID
is assigned, the first `terraform apply` runs against production, and
the first real users are onboarded.

Sections to author (using `docs/staging_access.md` as the template):

## 1. Endpoints and access
- Production URLs
- Access principals (who, via which role, granted how)

## 2. Bootstrap checklist
- `scripts/bootstrap_project.sh <prod-project-id> us-central1 production`
- Uncomment the module blocks in `terraform/production/main.tf` and `outputs.tf`
- Fill in `terraform/production/terraform.tfvars`
- `terraform init && terraform plan && terraform apply`
- Seed Secret Manager with production credentials
- Populate `master_authorized_networks` in tfvars (office CIDR, GH Actions NAT)

## 3. Deploy pipeline
- Clone `deploy-staging.yml` → `deploy-production.yml`
- Trigger on push to `main` (not `staging`)
- Require manual approval via `environment: production`
- Point at production cluster + Artifact Registry

## 4. Disaster recovery
- Cloud SQL point-in-time recovery — tested playbook with example commands
- Bad migration rollback — PITR vs `alembic downgrade` decision tree
- Full instance loss — restore from automated backup
- Bucket data loss — GCS object versioning recovery
- Regional outage — cross-region replica promotion (once enabled)

See `docs/CLAUDE.md` → "Disaster Recovery and Backup Architecture" in
jackpot-backend for the architectural contract these playbooks must
honor.

## 5. Observability
- Cloud Logging filters for the API, migration Jobs, scrubber, Nextflow
- Alert policies: 5xx rate, p95 latency, scrubber queue depth, Cloud SQL
  CPU, GKE node-pool saturation
- Error budget and on-call rotation

## 6. Cost guardrails
- Monthly budget + 50/80/100% alerts
- Per-lab billing dashboard (GCP Billing → labels: `env`, `project_name`,
  `jackpot_run_id`, `jackpot_lab`, `jackpot_pipeline`)

## 7. Secret rotation policy
- Rotation cadence per secret type
- Who rotates, how to update, how to roll pods forward

## 8. User onboarding
- How a new researcher gets added to a lab
- Expected Google OAuth flow
- Support channels
