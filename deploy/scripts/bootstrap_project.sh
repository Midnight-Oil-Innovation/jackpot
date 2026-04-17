#!/usr/bin/env bash
# One-time GCP project bootstrap for jackpot-iac.
#
# Run this BEFORE `terraform init` in any terraform/<env>/ directory.
# Idempotent — safe to re-run.
#
# What it does:
#   1. Verifies gcloud is installed and authenticated.
#   2. Sets the active project.
#   3. Enables all GCP APIs Terraform will call.
#   4. Creates the Terraform state bucket (with versioning + uniform access).
#   5. Creates the deploy service account (used by GitHub Actions via WIF).
#   6. Creates the Workload Identity Federation pool + provider for GitHub.
#
# Usage:
#   ./scripts/bootstrap_project.sh <project-id> <region> <environment>
#
# Example:
#   ./scripts/bootstrap_project.sh gotero3-acdp-488517 us-central1 staging

set -euo pipefail

if [[ $# -lt 3 ]]; then
    echo "Usage: $0 <project-id> <region> <environment>" >&2
    echo "Example: $0 gotero3-acdp-488517 us-central1 staging" >&2
    exit 1
fi

PROJECT_ID="$1"
REGION="$2"
ENVIRONMENT="$3"

TF_STATE_BUCKET="jackpot-${ENVIRONMENT}-tfstate"
DEPLOY_SA="jackpot-${ENVIRONMENT}-deploy"
DEPLOY_SA_EMAIL="${DEPLOY_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
WIF_POOL="jackpot-${ENVIRONMENT}-gh-pool"
WIF_PROVIDER="github"

# ── 1. Preflight ──────────────────────────────────────────────────────────────
command -v gcloud >/dev/null || { echo "gcloud not found — install the Cloud SDK"; exit 1; }
command -v gsutil >/dev/null || { echo "gsutil not found — install the Cloud SDK"; exit 1; }

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
if [[ -z "$ACTIVE_ACCOUNT" ]]; then
    echo "No active gcloud account. Run: gcloud auth login" >&2
    exit 1
fi
echo "Active account: $ACTIVE_ACCOUNT"
echo "Target project: $PROJECT_ID"
echo "Environment:    $ENVIRONMENT"
echo "Region:         $REGION"
echo

# ── 2. Activate project ───────────────────────────────────────────────────────
gcloud config set project "$PROJECT_ID" >/dev/null

# ── 3. Enable required APIs ───────────────────────────────────────────────────
REQUIRED_APIS=(
    compute.googleapis.com
    container.googleapis.com
    sqladmin.googleapis.com
    servicenetworking.googleapis.com
    secretmanager.googleapis.com
    artifactregistry.googleapis.com
    cloudresourcemanager.googleapis.com
    iam.googleapis.com
    iamcredentials.googleapis.com
    storage.googleapis.com
    batch.googleapis.com
    cloudscheduler.googleapis.com
    cloudbuild.googleapis.com
    logging.googleapis.com
    monitoring.googleapis.com
    sts.googleapis.com
)

echo "Enabling ${#REQUIRED_APIS[@]} APIs (this can take 1–2 min)…"
gcloud services enable "${REQUIRED_APIS[@]}" --project="$PROJECT_ID"
echo "APIs enabled."
echo

# ── 4. Terraform state bucket ─────────────────────────────────────────────────
if gsutil ls -b "gs://${TF_STATE_BUCKET}" >/dev/null 2>&1; then
    echo "State bucket gs://${TF_STATE_BUCKET} already exists."
else
    echo "Creating state bucket gs://${TF_STATE_BUCKET}…"
    gsutil mb -p "$PROJECT_ID" -l "$REGION" -b on "gs://${TF_STATE_BUCKET}"
    gsutil versioning set on "gs://${TF_STATE_BUCKET}"
    gsutil label ch -l "env:${ENVIRONMENT}" -l "project_name:jackpot" "gs://${TF_STATE_BUCKET}"
fi
echo

# ── 5. Deploy service account ─────────────────────────────────────────────────
if gcloud iam service-accounts describe "$DEPLOY_SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "Deploy SA ${DEPLOY_SA_EMAIL} already exists."
else
    echo "Creating deploy SA ${DEPLOY_SA_EMAIL}…"
    gcloud iam service-accounts create "$DEPLOY_SA" \
        --project="$PROJECT_ID" \
        --display-name="JACKPOT ${ENVIRONMENT} deploy SA" \
        --description="Used by GitHub Actions to run Terraform and deploy Helm charts"
fi

echo "Granting roles to ${DEPLOY_SA_EMAIL}…"
DEPLOY_ROLES=(
    roles/editor
    roles/iam.securityAdmin
    roles/secretmanager.admin
    roles/artifactregistry.admin
    roles/container.admin
    roles/cloudsql.admin
    roles/storage.admin
    roles/resourcemanager.projectIamAdmin
)
for role in "${DEPLOY_ROLES[@]}"; do
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${DEPLOY_SA_EMAIL}" \
        --role="$role" \
        --condition=None \
        --quiet >/dev/null
done
echo "Roles bound."
echo

# ── 6. Workload Identity Federation for GitHub Actions ────────────────────────
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

if gcloud iam workload-identity-pools describe "$WIF_POOL" \
        --project="$PROJECT_ID" --location=global >/dev/null 2>&1; then
    echo "WIF pool ${WIF_POOL} already exists."
else
    echo "Creating WIF pool ${WIF_POOL}…"
    gcloud iam workload-identity-pools create "$WIF_POOL" \
        --project="$PROJECT_ID" \
        --location=global \
        --display-name="JACKPOT ${ENVIRONMENT} GitHub pool"
fi

if gcloud iam workload-identity-pools providers describe "$WIF_PROVIDER" \
        --project="$PROJECT_ID" \
        --location=global \
        --workload-identity-pool="$WIF_POOL" >/dev/null 2>&1; then
    echo "WIF provider ${WIF_PROVIDER} already exists."
else
    echo "Creating WIF provider ${WIF_PROVIDER}…"
    gcloud iam workload-identity-pools providers create-oidc "$WIF_PROVIDER" \
        --project="$PROJECT_ID" \
        --location=global \
        --workload-identity-pool="$WIF_POOL" \
        --display-name="GitHub OIDC" \
        --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
        --attribute-condition="assertion.repository_owner == 'linuxprophet'" \
        --issuer-uri="https://token.actions.githubusercontent.com"
fi

echo
echo "Bootstrap complete."
echo
cat <<EOF
Next steps:

  1. Edit terraform/${ENVIRONMENT}/terraform.tfvars (copy from *.example):

       project_id  = "${PROJECT_ID}"
       region      = "${REGION}"
       environment = "${ENVIRONMENT}"

  2. Grant WIF impersonation to the GitHub repo (replace <owner>/<repo>):

       gcloud iam service-accounts add-iam-policy-binding ${DEPLOY_SA_EMAIL} \\
         --role=roles/iam.workloadIdentityUser \\
         --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/attribute.repository/<owner>/<repo>" \\
         --project=${PROJECT_ID}

  3. Put these into GitHub Actions repo variables:

       GCP_WORKLOAD_IDENTITY_PROVIDER = projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/providers/${WIF_PROVIDER}
       GCP_DEPLOY_SA                  = ${DEPLOY_SA_EMAIL}
       GCP_PROJECT_ID                 = ${PROJECT_ID}
       GCP_REGION                     = ${REGION}

  4. cd terraform/${ENVIRONMENT}/ && terraform init && terraform plan
EOF
