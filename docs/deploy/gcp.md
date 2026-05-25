# JACKPOT — Google Cloud Platform Deployment Guide

**Status:** v1.1 (Cluster F filename move and cross-reference updates applied 2026-05-16) · 2026-05-09 origin
**Path:** `docs/deploy/gcp.md` (was `sovereign_portal_delta.md`; renamed for clarity as part of the May 2026 Cluster F merge — the doc is the canonical JACKPOT-on-GCP deployment guide, not a "delta" against earlier exploratory docs)
**Supersedes:** `jackpot_gcp_setup_and_deploy_guide.md`, `jackpot_gcp_abridged_deploy_guide.md`, and `Guide_Deploying_a_Sovereign_Pathogen_Genomics_Portal_on_Google_Cloud_gemini.md` — three predecessor docs merged in May 2026. The "Sovereign Portal" framing from the third predecessor is preserved as §1.2 (architecture decision rationale) and §13 (optional Sovereign-Portal-derived components).

**Audience:** Operators standing up a JACKPOT instance on Google Cloud Platform from scratch. Assumes cloud basics (knows what a VM, Kubernetes pod, and database are; has used `gcloud` or comparable CLI before). Targets the production-hardened JACKPOT stack (GKE + Cloud SQL + Terraform + Helm + Workload Identity Federation + GitHub Actions CI/CD), with sidebars covering the alternative components considered from the Sovereign Portal exploration (Arvados, Gen3, Apache Superset, CILogon) and why each was retained or rejected.

**Estimated time:** 2–3 hours first time through. 30 minutes if you've done it before. Most of the time is waiting for Cloud SQL and GKE to provision.

**Estimated cost:** ~$420/month if left running 24/7. The `jackpot_pause.sh` script drops that to ~$80/month overnight. New GCP accounts get $300 free credit for 90 days — covers a full month of staging comfortably.

**What you'll have at the end:** a JACKPOT staging environment with a live `/health` endpoint on GKE, populated Cloud SQL PostgreSQL, Artifact Registry holding your Docker images, and GitHub Actions deploying to a `staging` branch. Same topology as `spec.md` Section 9.

---

## 0. What this guide supersedes (and how)

JACKPOT's deployment story used to live in three separate documents:

| Predecessor | Length | Role |
|---|---|---|
| `jackpot_gcp_setup_and_deploy_guide.md` | 821 lines | Long-form first-time-on-GCP walkthrough |
| `jackpot_gcp_abridged_deploy_guide.md` | 717 lines | Verify-then-create step-by-step for re-deploys |
| `Guide_Deploying_a_Sovereign_Pathogen_Genomics_Portal_on_Google_Cloud_gemini.md` | 1571 lines | Earlier exploratory architecture — Arvados + Gen3 + Apache Superset + CILogon stack |

This document merges all three. The first two are operationally accurate for the current JACKPOT stack and were the foundation. The third explored an alternative architecture that JACKPOT ultimately did not adopt (see §1.2 for the rationale), but contributed several useful framings — IAM bootstrap structure, CILogon as an alternative SSO path, Apache Superset evaluation, the `nf-core/fetchngs` ingest pattern, and an explicit "sovereign data ownership" framing that survives in JACKPOT's per-org governance design.

The result is one canonical guide. The three predecessors are retired; treat any reference to them as redirecting here.

**What's new vs. the predecessors:**

- **Architecture decision section (§1)** — explicit framing of *why* JACKPOT runs on GKE + Cloud SQL + Helm rather than Arvados + Gen3 + Apache Superset. This wasn't documented in any predecessor; the choice was implicit.
- **Optional enhancements (§13)** — Sovereign-Portal-derived components (CILogon SSO, Apache Superset analytics, nf-core/fetchngs pattern) presented as opt-in additions for operators who want them, rather than as the default stack.
- **Cleaner deploy-vs-verify split** — content from the long-form and abridged predecessors is consolidated into one set of steps, each marked as either FRESH-DEPLOY (run on first install) or VERIFY-OR-DEPLOY (idempotent; safe to re-run).

---

## 1. Architecture decision summary

This is the section that didn't exist in any predecessor. Read this before deploying anything — it explains the design space and the choice.

### 1.1 The actual JACKPOT stack on GCP

| Layer | Component | Why |
|---|---|---|
| **API runtime** | GKE (Google Kubernetes Engine) | Standard managed K8s; integrates with WIF for keyless auth; supports Helm; scales to zero with `jackpot_pause.sh`; covers the GA4GH-WES-eligible compute lane for free. |
| **Operational DB** | Cloud SQL PostgreSQL 16 | Managed Postgres; ACID transactions for audit log, access requests, federation; row-level locking; standard replication/backups. |
| **Analytics warehouse** | BigQuery | Periodic ETL from Cloud SQL; petabyte-scale dashboards; one-SQL-query JOIN with NCBI Pathogen Detection's public dataset (per `B-NCBI-1` in the backlog). |
| **Object storage** | GCS (Cloud Storage) | Raw FASTQs in `jackpot-raw` (30-day lifecycle); scrubbed FASTQs in `jackpot-sequences` (permanent); pipeline outputs in `jackpot-results`. |
| **Pipeline runtime** | Nextflow on GCP Batch | Standard public-health bioinformatics runtime; nf-core ecosystem compatibility; serverless dispatch. |
| **PII gates** | NCBI SRA Human Scrubber (Nextflow) + GCP Cloud DLP | Two-PII-gate architecture per `docs/platform_landscape.md` §10. WHO/IPSN attribute 6 compliance. |
| **Auth** | Google OAuth + JWT cookies | Standard; integrates with Domain Whitelist for org-controlled access. |
| **Frontend** | Streamlit (Month 1-2) → React (Year 2) | Streamlit lets a solo Python developer iterate fast in Month 1-2. React migration planned. |
| **CI/CD** | GitHub Actions + Workload Identity Federation | Keyless GCP auth from CI; no long-lived service-account keys. |
| **IaC** | Terraform | Industry-standard; the `jackpot-iac` repo holds the modules. |
| **Helm** | Charts in `jackpot-iac/helm/` | Standard K8s deployment templating. |
| **Secret management** | GCP Secret Manager | Database passwords, API keys, Google OAuth secrets. |

This is the merged-and-current stack. Sections 2-12 below cover deploying it.

### 1.2 What the Sovereign Portal guide proposed (and why JACKPOT didn't go there)

The earlier `Guide_Deploying_a_Sovereign_Pathogen_Genomics_Portal_on_Google_Cloud_gemini.md` proposed a different stack:

| Layer | Sovereign Portal proposal | JACKPOT's choice | Reason |
|---|---|---|---|
| **API runtime** | Cloud Run + Streamlit container | GKE | Cloud Run is fine for stateless services but limits long-running pipeline orchestration, scheduled jobs, and the multi-pod patterns JACKPOT needs. GKE is more operational overhead but lets JACKPOT keep all of API + scheduler + executor in one cluster with shared identity. |
| **Operational + analytics** | BigQuery as the operational DB | Cloud SQL operational + BigQuery analytics (separated) | BigQuery is wrong for transactional workloads (no row-level locking, no foreign keys, no ACID for audit log). The separation is one of JACKPOT's key architectural decisions per `docs/architecture.md` v6.0 §13 (post-Cluster-A merge; the assessment content was absorbed into the canonical architecture doc). |
| **Storage + lineage** | Arvados Keep + Crunch | GCS + JACKPOT's append-only `pipeline_results` JSONB | Arvados Keep is content-addressed which is genuinely good for provenance, but it's a major piece of infrastructure that adds operational complexity. JACKPOT's append-only `pipeline_results` table delivers the immutable-history property without the deployment overhead. |
| **Identity** | Gen3 Fence (CILogon-fronted) | Google OAuth + JWT directly | Gen3 Fence is a separate identity service to deploy and operate. JACKPOT uses Google OAuth directly, which is simpler. CILogon support is offered as an opt-in (see §13.1) for operators who want institutional SSO. |
| **Analytics dashboard** | Apache Superset | Streamlit dashboards (Month 1-2), BigQuery via SQL clients | Apache Superset is a separate auth domain and a separate access-control system. Streamlit keeps dashboards in the same Python codebase + same auth model as the rest of JACKPOT. Superset support is offered as an opt-in (see §13.2). |
| **Schema** | LinkML + GenEpiO | LinkML + full ontology stack (PHA4GE/GenEpiO/MIxS/NCBI/GA4GH/etc.) | Same foundation; JACKPOT's stack is broader. |
| **PII gates** | SRA-Human-Scrubber | SRA-Human-Scrubber + GCP Cloud DLP (metadata side) | Sovereign Portal proposed only the genomic-side scrubber. JACKPOT adds the metadata-side DLP scan, which is a meaningful WHO/IPSN attribute 6 improvement. |
| **Pipeline executor** | Nextflow on GCP Batch | Nextflow on GCP Batch | Identical. |
| **Public ingest** | nf-core/fetchngs from SRA | `POST /api/v1/ingest/accession` (currently E-utilities + fasterq-dump; planned migration to nf-core/fetchngs per `B-LOC-2` in `docs/platform_landscape.md` §17.1) | Convergent. |

**Net summary.** The Sovereign Portal guide explored "what if you stitch together Arvados + Gen3 + Superset for a sovereign pathogen platform on GCP?" The exploration produced useful conceptual artifacts (the data-sharing-with-sovereignty framing, the role hierarchy with Lab Director / Bioinformatician / Analyst, the SRA-Human-Scrubber-mandatory pattern), but the operational architecture — three independent platforms (Arvados, Gen3, Superset) each with their own deployment, auth, and access control — is heavier than what JACKPOT actually needs. JACKPOT chose the lighter integrated stack while keeping the conceptual framings.

The `governance/` directory work tracked in `jackpot_governance_alignment.md` §2.1 (`B-GOV-1`) is where the "sovereign data ownership" framing lives in the current JACKPOT design — operationalized through `min_sharing_level_for_federation`, the per-org policy fields, and the planned governance docs.

---

## 2. Prerequisites & local environment

You'll need:

- A Google account that can sign in to https://console.cloud.google.com
- A credit card (GCP won't charge unless you exceed free credits)
- A Mac M3 / Linux / WSL2 development environment with `bash`, `git`, `curl`
- Python 3.11+ (for any local development work)
- About 3 hours of wall time for the first deploy (most of it waiting)

### 2.1 Install the toolchain

```bash
# macOS (Homebrew)
brew install --cask google-cloud-sdk
brew install terraform
brew install kubernetes-cli
brew install helm
brew install gh                        # GitHub CLI
brew install --cask docker             # for local image builds

# Ubuntu/Debian
curl https://sdk.cloud.google.com | bash
exec -l $SHELL                         # reload shell
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt-get update && sudo apt-get install terraform
sudo snap install kubectl --classic
sudo snap install helm --classic
sudo apt install gh

# Verify (all should print versions, not errors)
gcloud --version
terraform -version
kubectl version --client
helm version
gh --version
```

### 2.2 Authenticate to Google Cloud

```bash
gcloud auth login
# Opens a browser window; sign in with the Google account you want to own this project

gcloud auth application-default login
# Same thing for Application Default Credentials (ADC)
# Used by Terraform, Python google-cloud-* libraries, etc.
```

You now have two credential sets that expire independently. `gcloud` itself uses one, ADC uses the other. Terraform uses ADC.

### 2.3 Authenticate to GitHub

```bash
gh auth login
# Walk through the prompts; pick HTTPS, authenticate with web flow
```

---

## 3. Create the GCP project (FRESH-DEPLOY) or verify it (VERIFY-OR-DEPLOY)

GCP projects are the top-level container for resources. One project per environment is the standard pattern.

### 3.1 Pick or create a project

```bash
# Pick something globally unique; this becomes part of resource URLs forever.
# Rules: 6-30 chars, lowercase + digits + hyphens, must start with letter.
export PROJECT_ID="jackpot-staging-$(whoami)"   # e.g. jackpot-staging-gotero
export BILLING_ACCOUNT_ID="01XXXX-XXXXXX-XXXXXX"   # find this in GCP Billing console
```

**FRESH DEPLOY:**

```bash
gcloud projects create "$PROJECT_ID" \
    --name="JACKPOT Staging" \
    --set-as-default

gcloud beta billing projects link "$PROJECT_ID" \
    --billing-account="$BILLING_ACCOUNT_ID"

# Confirm
gcloud config get-value project
gcloud beta billing projects describe "$PROJECT_ID"   # should show billingEnabled: true
```

**VERIFY-OR-DEPLOY:**

```bash
gcloud projects describe "$PROJECT_ID"
# If "PERMISSION_DENIED", either re-run `gcloud auth login` with the right account
# or have the project owner add your account as a member.

gcloud beta billing projects describe "$PROJECT_ID"
# Should show: billingEnabled: true
```

### 3.2 Set gcloud defaults

Saves typing `--project` and `--region` on every command:

```bash
gcloud config set project "$PROJECT_ID"
gcloud config set compute/region us-central1
gcloud config set compute/zone us-central1-a
```

Sanity check:

```bash
gcloud config list
# [compute]
# region = us-central1
# zone = us-central1-a
# [core]
# account = you@example.com
# project = jackpot-staging-...
```

---

## 4. Enable the APIs JACKPOT needs

GCP APIs are disabled by default; turn them on per project. JACKPOT uses about 16 services.

```bash
gcloud services enable \
    compute.googleapis.com \
    container.googleapis.com \
    sqladmin.googleapis.com \
    secretmanager.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    cloudscheduler.googleapis.com \
    cloudresourcemanager.googleapis.com \
    iam.googleapis.com \
    iamcredentials.googleapis.com \
    sts.googleapis.com \
    servicenetworking.googleapis.com \
    batch.googleapis.com \
    dlp.googleapis.com \
    logging.googleapis.com \
    monitoring.googleapis.com \
    --project="$PROJECT_ID"
```

This takes about 2 minutes. Verify:

```bash
gcloud services list --enabled --filter="name~'container|sql|secretmanager|batch|dlp'"
```

**What each one does:**

| API | Why JACKPOT needs it |
|---|---|
| `compute.googleapis.com` | VMs, disks, VPC networking — foundation for everything |
| `container.googleapis.com` | GKE (Google Kubernetes Engine) — the API runtime |
| `sqladmin.googleapis.com` | Cloud SQL (managed Postgres) — operational DB |
| `secretmanager.googleapis.com` | Secrets (DB password, OAuth secrets, API keys) |
| `artifactregistry.googleapis.com` | Private Docker image registry |
| `cloudbuild.googleapis.com` | Image builds (we use GitHub Actions instead, but the API must be enabled) |
| `cloudscheduler.googleapis.com` | Cron jobs in production (replaces APScheduler when scaled to multi-replica) |
| `cloudresourcemanager.googleapis.com` | Project + IAM management |
| `iam.googleapis.com` | Service accounts |
| `iamcredentials.googleapis.com` | Workload Identity Federation (GitHub → GCP keyless auth) |
| `sts.googleapis.com` | Token exchange (part of WIF) |
| `servicenetworking.googleapis.com` | Private Service Connect for Cloud SQL |
| `batch.googleapis.com` | GCP Batch — Nextflow pipeline compute |
| `dlp.googleapis.com` | Cloud DLP — metadata PII gate (`dlp_scanner.py`) |
| `logging.googleapis.com` | Cloud Logging — log aggregation |
| `monitoring.googleapis.com` | Cloud Monitoring — metrics + alerting |

---

## 5. Workload Identity Federation (WIF) for GitHub Actions

WIF lets GitHub Actions authenticate to GCP without long-lived service-account keys. GitHub's OIDC token gets exchanged for a short-lived GCP access token. **Never use downloaded service-account JSON keys** — WIF is the modern, secure path.

### 5.1 Verify if WIF already exists (VERIFY-OR-DEPLOY)

```bash
# Pool exists?
gcloud iam workload-identity-pools list --location=global \
    --filter="name:github-actions-pool" --project="$PROJECT_ID"

# Provider exists?
gcloud iam workload-identity-pools providers list \
    --workload-identity-pool=github-actions-pool \
    --location=global --project="$PROJECT_ID"
```

If both exist, skip to §5.3 to capture the resource name.

### 5.2 Create WIF (FRESH DEPLOY)

```bash
export PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
export GITHUB_ORG="YOUR_GITHUB_USERNAME_OR_ORG"   # e.g. Midnight-Oil-Innovation

# Create the pool
gcloud iam workload-identity-pools create github-actions-pool \
    --location=global \
    --display-name="GitHub Actions Pool" \
    --project="$PROJECT_ID"

# Create the provider (trusts GitHub's OIDC issuer)
gcloud iam workload-identity-pools providers create-oidc github-provider \
    --workload-identity-pool=github-actions-pool \
    --location=global \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --attribute-condition="assertion.repository_owner == '$GITHUB_ORG'" \
    --project="$PROJECT_ID"
```

**Note on the attribute-condition.** The `assertion.repository_owner == '$GITHUB_ORG'` condition is a critical security gate — without it, *any* GitHub repo could potentially exchange a token for GCP access. Lock this to your specific GitHub org or username.

### 5.3 Capture the WIF provider resource name

```bash
gcloud iam workload-identity-pools providers describe github-provider \
    --workload-identity-pool=github-actions-pool \
    --location=global \
    --project="$PROJECT_ID" \
    --format="value(name)"
# Output looks like:
# projects/123456789/locations/global/workloadIdentityPools/github-actions-pool/providers/github-provider
```

Copy this. You'll paste it into a GitHub secret in §9.

WIF is now set up but not yet bound to a service account — that comes in §6.

---

## 6. Service accounts and IAM bindings

### 6.1 Create the deploy service account (FRESH DEPLOY) or verify (VERIFY-OR-DEPLOY)

The `deploy-sa` service account is what GitHub Actions impersonates to deploy infrastructure and applications.

**VERIFY:**

```bash
gcloud iam service-accounts list \
    --filter="email~'deploy-sa@'" \
    --project="$PROJECT_ID"
```

If listed, skip to §6.2.

**FRESH DEPLOY:**

```bash
gcloud iam service-accounts create deploy-sa \
    --display-name="JACKPOT Deploy Service Account" \
    --project="$PROJECT_ID"

# Grant the permissions it needs
for role in \
    roles/container.developer \
    roles/cloudsql.client \
    roles/storage.admin \
    roles/artifactregistry.writer \
    roles/secretmanager.secretAccessor \
    roles/secretmanager.versionManager \
    roles/iam.serviceAccountUser \
    roles/compute.networkAdmin \
    roles/resourcemanager.projectIamAdmin
do
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:deploy-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="$role" \
        --condition=None
done
```

### 6.2 Bind WIF to the deploy SA

For each repo that should be allowed to authenticate as the deploy SA:

```bash
for repo in jackpot-iac jackpot-backend; do
    gcloud iam service-accounts add-iam-policy-binding \
        "deploy-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/iam.workloadIdentityUser" \
        --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/${GITHUB_ORG}/${repo}" \
        --project="$PROJECT_ID"
done

# Verify
gcloud iam service-accounts get-iam-policy \
    "deploy-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --project="$PROJECT_ID"
# Should list both repos under roles/iam.workloadIdentityUser
```

### 6.3 The runtime service account

JACKPOT API pods run as `jackpot-api@${PROJECT_ID}.iam.gserviceaccount.com`. This account is created automatically by Terraform in §7. You don't need to create it manually here.

---

## 7. Provision infrastructure with Terraform

The `jackpot-iac` repo contains Terraform modules that create the VPC, GKE cluster, Cloud SQL instance, GCS buckets, Artifact Registry, Secret Manager entries, and all associated IAM bindings.

### 7.1 Clone repos

```bash
mkdir -p ~/ASU/jackpot && cd ~/ASU/jackpot
gh repo clone "${GITHUB_ORG}/jackpot-backend"
gh repo clone "${GITHUB_ORG}/jackpot-iac"
gh repo clone "${GITHUB_ORG}/jackpot-nf"
gh repo clone "${GITHUB_ORG}/jackpot-schema"
```

(Note: monorepo migration to `Midnight-Oil-Innovation/jackpot` is tracked as P0d in `jackpot_session_summary_and_backlog.md`. After P0d lands, this becomes a single `gh repo clone Midnight-Oil-Innovation/jackpot`.)

### 7.2 Configure the Terraform backend

Terraform state needs a durable, shared home (not your laptop). Create a GCS bucket for it:

```bash
gcloud storage buckets create "gs://${PROJECT_ID}-tfstate" \
    --project="$PROJECT_ID" \
    --location=us-central1 \
    --uniform-bucket-level-access

# Versioning — state file is precious
gcloud storage buckets update "gs://${PROJECT_ID}-tfstate" --versioning
```

Edit `jackpot-iac/terraform/staging/backend.tf`:

```hcl
terraform {
  backend "gcs" {
    bucket = "jackpot-staging-USERNAME-tfstate"   # match your actual bucket name
    prefix = "staging"
  }
}
```

### 7.3 Set Terraform variables

In `jackpot-iac/terraform/staging/`, create `terraform.tfvars`:

```hcl
project_id        = "jackpot-staging-USERNAME"
region            = "us-central1"
environment       = "staging"
github_org        = "Midnight-Oil-Innovation"
cluster_name      = "jackpot-staging-gke"
sql_instance_name = "jackpot-staging-db"
sql_database      = "jackpot_db"
sql_user          = "jackpot"
```

`terraform.tfvars` is gitignored — it's local config, not committed.

### 7.4 Initialize and apply

```bash
cd ~/ASU/jackpot/jackpot-iac/terraform/staging

terraform init
# Downloads providers, configures GCS backend

terraform plan
# Shows ~60-80 resources: VPC + subnets + GKE + Cloud SQL + buckets + SAs + IAM bindings

terraform apply
# Type 'yes' when prompted; takes ~20-30 minutes:
#   - VPC + subnets:    ~30s
#   - Cloud SQL:        ~10-15 minutes (slowest)
#   - GKE cluster:      ~10-15 minutes
#   - Everything else:  parallel, ~1-2 minutes
```

While Terraform runs, grab coffee. **Don't Ctrl-C** — Terraform can recover from interruptions but leaves orphan resources if killed mid-provisioning.

### 7.5 Verify Terraform output

```bash
# GKE cluster
gcloud container clusters list --project="$PROJECT_ID"
# Expect: jackpot-staging-gke RUNNING

# Cloud SQL
gcloud sql instances list --project="$PROJECT_ID"
# Expect: jackpot-staging-db RUNNABLE

# Artifact Registry
gcloud artifacts repositories list --project="$PROJECT_ID"
# Expect: jackpot

# GCS buckets
gcloud storage buckets list --filter="name~jackpot-staging" --project="$PROJECT_ID"
# Expect 7 buckets: jackpot-staging-raw, -sequences, -results, -staging, -datasets, -reports, -tfstate

# Secrets
gcloud secrets list --project="$PROJECT_ID"
# Expect: jackpot-db-password, jackpot-google-oauth-client-id,
#         jackpot-google-oauth-client-secret, jackpot-jwt-secret, jackpot-dlp-config
```

---

## 8. Bootstrap the database schema

Cloud SQL comes up empty. `db/init.sql` doesn't run automatically — this is the Critical Rule 44 footgun. You either run a bootstrap Job (tactical) or wait for the baseline Alembic migration to land permanently.

### 8.1 Get GKE credentials

```bash
gcloud container clusters get-credentials jackpot-staging-gke \
    --region=us-central1 \
    --project="$PROJECT_ID"

kubectl get nodes
# Expect 1-3 nodes Ready
```

### 8.2 Apply the bootstrap Job

This Job runs the schema bootstrap inside the cluster, where it has access to Cloud SQL via the service account.

```bash
kubectl -n jackpot apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: jackpot-bootstrap-db
  namespace: jackpot
spec:
  backoffLimit: 1
  template:
    spec:
      restartPolicy: Never
      serviceAccountName: jackpot-api
      containers:
      - name: bootstrap
        image: us-central1-docker.pkg.dev/${PROJECT_ID}/jackpot/jackpot-api:latest
        command: ["/bin/bash", "-c"]
        args:
          - |
            set -e
            echo "Loading init.sql..."
            /opt/venv/bin/python -c "
            import os, psycopg
            from pathlib import Path
            url = os.environ['DATABASE_URL']
            sql = Path('db/init.sql').read_text()
            with psycopg.connect(url, autocommit=True) as conn:
                conn.execute(sql)
            "
            echo "Stamping Alembic at a7fd1fcccb77..."
            /opt/venv/bin/alembic stamp a7fd1fcccb77
            echo "Running upgrade to head..."
            /opt/venv/bin/alembic upgrade head
            echo "Done."
        envFrom:
        - secretRef:
            name: jackpot-api-secrets
        - configMapRef:
            name: jackpot-api-config
EOF

# Watch
kubectl -n jackpot logs -f job/jackpot-bootstrap-db

# Cleanup once complete
kubectl -n jackpot delete job jackpot-bootstrap-db
```

**Order of operations note.** Step 8 assumes the JACKPOT API Docker image has already been built and pushed to Artifact Registry. On a true fresh deploy, the order is: Terraform (§7) → GitHub Actions first deploy (§9-10, builds + pushes the image) → THEN bootstrap Job (§8). On re-deploys, the image already exists and bootstrap Job runs anytime.

---

## 9. GitHub Actions CI/CD setup

### 9.1 Cross-repo PAT for submodule checkout

JACKPOT's submodule structure (jackpot-backend pulling jackpot-schema and jackpot-nf) needs a personal access token for cross-repo reads in CI.

```bash
# Create a fine-grained PAT with read access to the relevant repos
# Path: https://github.com/settings/tokens?type=beta
# Scope: Repository access -> Selected repositories -> jackpot-* repos
# Permissions: Contents (read), Metadata (read)
# Save as github_pat_11... and pass it to gh secret set below
```

**Hygiene note.** PAT rotation is a recurring chore. If a PAT is ever exposed (committed to a public repo, pasted in a chat log), revoke and rotate immediately. The PAT-rotation footgun is documented in `jackpot_session_summary_and_backlog.md` — JACKPOT once accidentally exposed a fine-grained PAT mid-session and had to revoke and recreate all of them.

### 9.2 Set GitHub secrets

For each repo (`jackpot-iac`, `jackpot-backend`):

```bash
cd ~/ASU/jackpot/jackpot-iac

gh secret set CROSS_REPO_PAT
# Paste the fresh PAT when prompted

# WIF provider (the resource name captured in §5.3)
gh secret set GCP_WIF_PROVIDER --body "projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-actions-pool/providers/github-provider"

# Deploy SA email
gh secret set GCP_DEPLOY_SA --body "deploy-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Variables (non-secret)
gh variable set GCP_PROJECT_ID --body "${PROJECT_ID}"
gh variable set GCP_REGION --body "us-central1"

# Verify
gh secret list
gh variable list
```

Repeat for `jackpot-backend`.

---

## 10. First deploy

### 10.1 Push to staging branch

```bash
cd ~/ASU/jackpot/jackpot-backend

# Ensure submodules are current
git submodule update --init --recursive

# Make sure you're on the staging branch (creating it if needed)
git checkout staging 2>/dev/null || git checkout -b staging
git push -u origin staging
```

The `staging` branch push triggers `.github/workflows/deploy-staging.yml`, which:

1. Authenticates to GCP via WIF
2. Builds the Docker image
3. Pushes to Artifact Registry
4. Updates the Helm release

### 10.2 Watch the deploy

```bash
gh run watch
# Or open in browser
gh run view --web
```

If the deploy fails at "Authenticate to Google Cloud", check the WIF binding (§6.2) — usually the issue is the `principalSet` URI not matching your GitHub repo path.

If it fails at submodule checkout with 401, the `CROSS_REPO_PAT` secret has expired or is wrong scope.

If Helm release is stuck at `pending-upgrade`:

```bash
# Find the last "deployed" revision
helm history jackpot -n jackpot

# Roll back to that revision
helm rollback jackpot <REVISION_NUMBER> -n jackpot
```

### 10.3 Known footgun — CORS_ORIGINS ConfigMap

There's a documented blocker on first deploys: `jackpot-api-config` ConfigMap can carry an old `CORS_ORIGINS` string value rather than the JSON array required by pydantic-settings. Fix:

```bash
kubectl -n jackpot delete configmap jackpot-api-config
gh workflow run deploy-staging.yml
# Pre-install hook recreates ConfigMap with corrected JSON array from values-staging.yaml
```

---

## 11. Verify the deploy

```bash
# Pods healthy?
kubectl -n jackpot get pods
# Expect: jackpot-api-xxxx-yyyy   2/2   Running

# Port-forward and probe /health
kubectl -n jackpot port-forward svc/jackpot-api 8000:80 &
curl -s http://localhost:8000/health | jq

# Expected output:
# {
#   "status": "ok",
#   "version": "5.0.0",
#   "project": "JACKPOT",
#   "database": "connected"
# }

# Stop the port-forward
kill %1
```

If `database` shows `disconnected`, the Cloud SQL proxy or DATABASE_URL secret is wrong. Check:

```bash
kubectl -n jackpot logs -l app=jackpot-api -c cloud-sql-proxy
kubectl -n jackpot get secret jackpot-api-secrets -o yaml
```

---

## 12. Operational tasks

### 12.1 Pause / resume to save money overnight

```bash
# Pause (scales GKE to 0, stops Cloud SQL)
~/ASU/jackpot/jackpot-iac/scripts/jackpot_pause.sh

# Resume (starts Cloud SQL, scales GKE back up, verifies /health)
~/ASU/jackpot/jackpot-iac/scripts/jackpot_resume.sh
```

The pause script drops the daily run-rate from ~$420/month to ~$80/month. Use it overnight, on weekends, or during long quiet periods.

If you want to be even more aggressive about cost:

```bash
# Scale api-pool to 0 (stops ~$284/mo of compute)
gcloud container clusters resize jackpot-staging-gke --node-pool=api-pool --num-nodes=0 --region=us-central1

# Stop Cloud SQL (stops ~$55/mo but also halts PITR — point-in-time recovery)
gcloud sql instances patch jackpot-staging-db --activation-policy=NEVER
```

### 12.2 Watch costs

```bash
# Real-time GCP billing reports
open "https://console.cloud.google.com/billing/$BILLING_ACCOUNT_ID/reports?project=$PROJECT_ID"

# Quick CLI check of recent spend
gcloud billing accounts describe "billingAccounts/${BILLING_ACCOUNT_ID}"
```

For per-lab cost attribution (a planned feature), use `resourceLabels` on Batch jobs:

```bash
# Set when launching a Nextflow run
nextflow run pipeline -profile gcp -resourceLabels "lab_id=otero,project_id=salmonella2026"

# Query later via the Billing API
bq query --use_legacy_sql=false "
SELECT labels.value AS lab_id, SUM(cost) AS total_cost
FROM \`${PROJECT_ID}.billing_export.gcp_billing_export_v1_${BILLING_ACCOUNT_ID/-/_}\`
WHERE service.description = 'Compute Engine'
  AND labels.key = 'lab_id'
GROUP BY lab_id
"
```

### 12.3 Read logs

```bash
# API pod stdout/stderr (live tail)
kubectl -n jackpot logs -l app=jackpot-api -c api -f

# Last 100 lines from Cloud Logging
gcloud logging read "resource.type=k8s_container AND resource.labels.namespace_name=jackpot" \
    --limit=100 --format=json --project="$PROJECT_ID"

# Specific request-ID trace (the request_id middleware in JACKPOT logs this on every request)
gcloud logging read 'jsonPayload.request_id="abc-123-def"' \
    --limit=50 --project="$PROJECT_ID"
```

### 12.4 Connect to Cloud SQL from your laptop

```bash
# Install the Cloud SQL Auth Proxy
brew install cloud-sql-proxy
# or: download from https://github.com/GoogleCloudPlatform/cloud-sql-proxy/releases

# Start proxy in background
cloud-sql-proxy "${PROJECT_ID}:us-central1:jackpot-staging-db" --port 5432 &

# Get DB password from Secret Manager
DB_PASSWORD=$(gcloud secrets versions access latest --secret=jackpot-db-password --project="$PROJECT_ID")

# Connect via psql
PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p 5432 -U jackpot -d jackpot_db
```

### 12.5 Restore from backup

```bash
# List available backups
gcloud sql backups list --instance=jackpot-staging-db --project="$PROJECT_ID"

# Restore to a NEW instance (safer than in-place)
gcloud sql backups restore <BACKUP_ID> \
    --restore-instance=jackpot-staging-db-restored \
    --backup-instance=jackpot-staging-db \
    --project="$PROJECT_ID"

# Then update Secret Manager's DATABASE_URL to point at the new instance, redeploy, test,
# delete old instance.
```

---

## 13. Optional enhancements considered from the Sovereign Portal exploration

The earlier `Guide_Deploying_a_Sovereign_Pathogen_Genomics_Portal_on_Google_Cloud_gemini.md` proposed a different stack centered on Arvados + Gen3 + Apache Superset + CILogon. Section 1 documents why JACKPOT didn't adopt that stack wholesale. **However**, three pieces of that stack are worth offering as opt-in enhancements for operators who want them. This section provides setup pointers for each.

### 13.1 CILogon SSO (alternative to Google OAuth)

**When this is useful.** Operators in academic or research consortium contexts (NSF-funded, NIH-funded, NIH BTRIS, etc.) where users authenticate via institutional SSO rather than personal Google accounts. CILogon brokers SAML and OIDC across InCommon-federated institutions plus several social identity providers.

**Setup.**

1. Register your application at https://cilogon.org/oauth2/register. You'll get a `client_id` and `client_secret`.
2. Add CILogon as a secondary auth provider in JACKPOT. The current `auth/google.py` handles Google OAuth; the analogous `auth/cilogon.py` would handle CILogon. JACKPOT's existing OAuth2 flow can be parameterized — both Google and CILogon are OIDC providers.
3. Update environment config:

```bash
# Store CILogon credentials in Secret Manager
gcloud secrets create jackpot-cilogon-client-id --replication-policy=automatic --project="$PROJECT_ID"
echo -n "your-cilogon-client-id" | gcloud secrets versions add jackpot-cilogon-client-id --data-file=- --project="$PROJECT_ID"

gcloud secrets create jackpot-cilogon-client-secret --replication-policy=automatic --project="$PROJECT_ID"
echo -n "your-cilogon-client-secret" | gcloud secrets versions add jackpot-cilogon-client-secret --data-file=- --project="$PROJECT_ID"

# Update Helm values to mount these secrets and enable CILogon route
# values-staging.yaml:
#   auth:
#     providers:
#       google: {enabled: true}
#       cilogon: {enabled: true, idp: "https://cilogon.org"}
```

**Backlog item:**

```text
[ ] B-CILOGON-1  Add CILogon as a secondary OIDC provider alongside
                 Google OAuth. Parameterize the existing OAuth2 flow.
                 Useful for institutional / academic operator deployments.
                 Effort: 1 week. Phase: when first institutional operator
                 requests it.
```

### 13.2 Apache Superset analytics (alternative to Streamlit dashboards)

**When this is useful.** Operators with dedicated data analysts who want a self-service BI tool for ad-hoc exploration. Superset is a 100% open-source analytics platform that connects to BigQuery and lets analysts build dashboards without writing code.

**Trade-off.** Superset adds a separate auth domain and access-control system. For JACKPOT's default profile (small lab, single-organization), Streamlit dashboards in the same Python codebase are simpler. For bigger operators (large state DOH with a data-analytics team), Superset can be the right addition.

**Setup.**

```bash
# Deploy Superset on a small GCE VM (or its own GKE pod)
gcloud compute instances create superset-vm \
    --machine-type=e2-medium \
    --image-family=cos-stable \
    --image-project=cos-cloud \
    --metadata-from-file user-data=<(cat <<EOF
#cloud-config
runcmd:
  - docker run -d --name superset -p 8088:8088 apache/superset
  - sleep 30
  - docker exec superset superset fab create-admin --username admin --firstname Admin --lastname User --email admin@example.com --password admin
  - docker exec superset superset db upgrade
  - docker exec superset superset init
EOF
) \
    --zone=us-central1-a \
    --project="$PROJECT_ID"

# Configure BigQuery connection in Superset UI:
#   Connection string: bigquery://${PROJECT_ID}/jackpot_analytics
#   Auth: ADC via the GCE VM's service account
```

Then in the Superset UI: add a new database, point at BigQuery, build dashboards on top of the JACKPOT analytics warehouse tables.

**Backlog item:**

```text
[ ] B-SUPERSET-1  Add optional Apache Superset deployment as an analytics
                  layer for operators with dedicated analysts. Connect to
                  BigQuery analytics warehouse. Ship a starter dashboard
                  set (sample-counts, surveillance-relevant cases, AMR
                  trends).
                  Effort: 1 week. Phase: when first operator with
                  analytics team requests it.
```

### 13.3 nf-core/fetchngs ingest pattern

**Status: planned adoption (already in JACKPOT backlog as `B-LOC-2`).**

The Sovereign Portal guide proposed `nf-core/fetchngs` as the canonical SRA-import workflow. This is convergent with `B-LOC-2` in `docs/platform_landscape.md` §17.1, which lifts Loculus's `ingest/` Snakemake workflow (built on NCBI Datasets CLI) clean-room into `pipelines/insdc-ingest/`. Either NCBI Datasets CLI (Loculus's choice) or `nf-core/fetchngs` would be a reasonable migration target from the current E-utilities + fasterq-dump implementation.

The decision between NCBI Datasets CLI and `nf-core/fetchngs` is mostly preference:

- **NCBI Datasets CLI** delivers richer per-record metadata bundles (BioSample + assembly + protein in one zip).
- **nf-core/fetchngs** is more general-purpose (fetches from SRA, ENA, DDBJ, GEO) and integrates more naturally with Nextflow.

JACKPOT could pick either — the integration shape is the same.

### 13.4 Arvados Keep + Gen3 Fence (rejected — rationale documented)

The Sovereign Portal guide proposed Arvados Keep as the storage substrate and Gen3 Fence as the identity service. JACKPOT did not adopt either. The rationale (per §1.2 above):

- **Arvados Keep:** Content-addressed storage is genuinely good for provenance, but it's a major piece of infrastructure that adds operational complexity. JACKPOT's append-only `pipeline_results` JSONB rows + immutable audit log deliver the immutable-history property without the deployment overhead.
- **Gen3 Fence:** A separate identity service is heavier than Google OAuth + JWT. The CILogon path (§13.1) lets JACKPOT support institutional SSO without Gen3 Fence.

These remain rejected for the default JACKPOT stack. Operators who specifically need Arvados or Gen3 features should consider whether JACKPOT is the right fit for their deployment, or whether they want the Sovereign Portal's heavier stack.

---

## 14. Teardown

### 14.1 Pause to stop spending money

If you're keeping the project but not using it:

```bash
~/ASU/jackpot/jackpot-iac/scripts/jackpot_pause.sh
```

This drops costs to ~$80/month while preserving all state.

### 14.2 Delete resources, keep the project

If you're keeping the GCP project but tearing down JACKPOT specifically:

```bash
cd ~/ASU/jackpot/jackpot-iac/terraform/staging
terraform destroy
# Type 'yes' when prompted; takes ~15 minutes
```

This removes the GKE cluster, Cloud SQL instance, GCS buckets (after lifecycle rules expire), Artifact Registry, secrets, and IAM bindings. The Terraform state in `gs://${PROJECT_ID}-tfstate` is preserved.

### 14.3 Nuclear option — delete the project entirely

```bash
~/ASU/jackpot/jackpot-iac/scripts/jackpot_nuke_project.sh
# OR manually:
# gcloud projects delete "$PROJECT_ID"
```

The project is moved to a "pending deletion" state for 30 days. Within that window you can restore it with `gcloud projects undelete "$PROJECT_ID"`. After 30 days, the project and everything in it is gone forever.

---

## 15. Troubleshooting — common failure modes

### 15.1 "Error: Permission denied" when running gcloud

```bash
gcloud auth login        # log into the right account
gcloud auth application-default login   # refresh ADC
gcloud config get-value project    # verify the project context
```

### 15.2 Terraform apply hangs on Cloud SQL

Cloud SQL provisioning takes 10-15 minutes. If it's been longer, check the GCP console for the SQL instance state. Common issues: quota exceeded (try a different region), invalid `tier` value, or the `servicenetworking.googleapis.com` API not being enabled.

### 15.3 GitHub Actions workflow fails at "Authenticate to GCP"

The WIF binding is wrong. Check:

```bash
gcloud iam service-accounts get-iam-policy \
    "deploy-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --project="$PROJECT_ID"
```

The `principalSet://...` URIs should include your specific repos. If the binding looks right but auth still fails, check the WIF *attribute condition* — if you typoed the GitHub org name, the assertion check fails.

### 15.4 Workflow fails at submodule checkout with 401

The `CROSS_REPO_PAT` GitHub secret is missing, expired, or has wrong scope. Recreate:

```bash
# Generate a fresh PAT at:
# https://github.com/settings/tokens?type=beta
# Scope: Repository access -> Selected repositories -> jackpot-* repos
# Permissions: Contents (read), Metadata (read)

cd ~/ASU/jackpot/jackpot-iac
gh secret set CROSS_REPO_PAT
# Paste the new PAT
```

### 15.5 "Error: database 'jackpot_db' does not exist"

Cloud SQL was provisioned but the database name doesn't match. Either:

- Edit `terraform.tfvars` to set `sql_database = "jackpot_db"` and re-apply, OR
- Connect via Cloud SQL Auth Proxy (§12.4) and `CREATE DATABASE jackpot_db;`

### 15.6 Helm release stuck at `pending-upgrade`

```bash
# Find the last "deployed" revision
helm history jackpot -n jackpot

# Roll back
helm rollback jackpot <REVISION_NUMBER> -n jackpot
```

### 15.7 "quota exceeded" errors

Check `gcloud compute project-info describe` for current quotas. Common ones to bump on new projects: **CPUs in region** (default 24, JACKPOT staging needs ~8), **In-use IP addresses**, **Persistent Disk SSD** (default 500GB).

To request an increase: https://console.cloud.google.com/iam-admin/quotas

### 15.8 CORS_ORIGINS ConfigMap mismatch

(Documented in §10.3.) Delete and re-apply:

```bash
kubectl -n jackpot delete configmap jackpot-api-config
gh workflow run deploy-staging.yml
```

### 15.9 `--ff-only` merge fails when promoting staging → development

If you're trying to promote a staging branch back to development with `git merge --ff-only` and it fails, you have divergent commits on development. Either rebase staging onto development first, or accept a merge commit:

```bash
git checkout development
git merge --no-ff staging
git push origin development
```

---

## 16. Useful gcloud commands reference

```bash
# Project & billing
gcloud projects describe "$PROJECT_ID"
gcloud beta billing projects describe "$PROJECT_ID"
gcloud services list --enabled --project="$PROJECT_ID"

# GKE
gcloud container clusters describe jackpot-staging-gke --region=us-central1 --project="$PROJECT_ID"
gcloud container clusters get-credentials jackpot-staging-gke --region=us-central1 --project="$PROJECT_ID"
kubectl -n jackpot get all
kubectl -n jackpot logs -l app=jackpot-api -c api --tail=100

# Cloud SQL
gcloud sql instances describe jackpot-staging-db --project="$PROJECT_ID"
gcloud sql databases list --instance=jackpot-staging-db --project="$PROJECT_ID"
gcloud sql backups list --instance=jackpot-staging-db --project="$PROJECT_ID"

# Secret Manager
gcloud secrets list --project="$PROJECT_ID"
gcloud secrets versions access latest --secret=jackpot-db-password --project="$PROJECT_ID"

# Artifact Registry
gcloud artifacts repositories list --project="$PROJECT_ID"
gcloud artifacts docker images list us-central1-docker.pkg.dev/${PROJECT_ID}/jackpot --project="$PROJECT_ID"

# IAM
gcloud projects get-iam-policy "$PROJECT_ID"
gcloud iam service-accounts list --project="$PROJECT_ID"
gcloud iam workload-identity-pools providers list --workload-identity-pool=github-actions-pool --location=global --project="$PROJECT_ID"

# Logs (recent)
gcloud logging read "resource.type=k8s_container" --limit=50 --project="$PROJECT_ID"
```

---

## 17. What to do next

Once you have a running JACKPOT staging deployment, the natural next steps:

1. **Smoke-test ingest paths** — try uploading a sample via each of the six ingest paths (signed URL, URI registration, SRA accession import, workspace promotion, CSV batch, Globus deposit-first) per `docs/architecture.md` v6.0 §15 (post-Cluster-A merge).

2. **Run a smoke pipeline** — pick a small viral sample, run the viralrecon pipeline, verify `pipeline_results` is populated and the Streamlit UI shows lineage assignment.

3. **Wire the Streamlit UI** — port-forward to `http://localhost:8501` (per `spec.md` §10) and verify the researcher pages work end-to-end.

4. **Stand up the `governance/` directory** — per `B-GOV-1` in `jackpot_governance_alignment.md` §7. Document work, ~3-5 hours; closes 5+ WHO/IPSN attribute gaps.

5. **Plan the production deploy** — production is a separate GCP project with the same structure. The `jackpot-prod` topology adds: HA Cloud SQL, multi-AZ GKE, Cloud Armor + WAF, dedicated VPC peering for Globus, Cloud Scheduler replacing in-process APScheduler.

6. **Set up the federation Level 1 client** — once a second JACKPOT operator deploys, exercise the federation query API and confirm the cross-instance metadata search works as designed.

---

## 18. References

- `docs/architecture.md` v6.0 — full architectural reference, post-Cluster-A merge (was `jackpot_architecture.md`, 1862 lines; the v6.0 merged doc consolidates that with `JACKPOT_Architecture_Synthesis_May_2026.md` and `Core_Technical_Pillars.md`)
- `docs/platform_landscape.md` — comparative analysis vs. peer platforms (~2400 lines; post-Cluster-E consistency pass)
- `jackpot_governance_alignment.md` — alignment matrices for WHO/IPSN, GA4GH, FAIR/CARE, CDC North Star
- `spec.md` — current sprint specification + Session 5 GCP staging deployment notes (§9)
- `jackpot_session_summary_and_backlog.md` — running session log + backlog
- `todo.md` — active backlog
- WHO Global Genomic Surveillance Strategy (`WHO_Global_genomic_surveillance_strategy.pdf`)
- WHO Guiding Principles for Pathogen Genome Data Sharing (`WHO_guiding_principles_for_pathogen_genome_data_sharing.pdf`)
- WHO Essential Attributes of PGDSPs (`Attributesential.pdf`)
- CDC North Star Architecture (`North_Star_CDCSummit_092723.pdf`)

---

*End of GCP deployment guide v1.2 (Cluster E cross-reference cleanup). Pairs with `docs/platform_landscape.md` (the renamed-and-Cluster-E-updated platform landscape doc) and `docs/governance_alignment.md` (the renamed-and-Cluster-F-updated governance alignment matrix doc). Supersedes all three predecessor documents listed in §0.*
