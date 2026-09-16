locals {
  name_prefix = "jackpot-${var.environment}"
}

resource "google_service_account" "api" {
  project      = var.project_id
  account_id   = "jackpot-api"
  display_name = "JACKPOT ${var.environment} API"
  description  = "Service account for the FastAPI backend pods (GSA bound to KSA via Workload Identity)."
}

resource "google_service_account" "scrubber" {
  project      = var.project_id
  account_id   = "jackpot-scrubber"
  display_name = "JACKPOT ${var.environment} scrubber"
  description  = "Service account for SRA Human Scrubber GKE Jobs."
}

resource "google_service_account" "nextflow" {
  project      = var.project_id
  account_id   = "jackpot-nextflow"
  display_name = "JACKPOT ${var.environment} Nextflow"
  description  = "Service account for Nextflow controller — submits GCP Batch jobs, reads/writes work bucket."
}

# ── Project-level roles ──────────────────────────────────────────────────────
resource "google_project_iam_member" "api_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_logging_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_monitoring_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_batch_admin" {
  project = var.project_id
  role    = "roles/batch.jobsEditor"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# ── actAs, scoped to the accounts a Batch job can run as ────────────────────
#
# These were project-level roles/iam.serviceAccountUser. Combined with
# roles/batch.jobsEditor above, that let a compromised API or Nextflow pod
# launch a Batch job running as ANY service account in the project — including
# the deploy account and Terraform's own. Submitting a Batch job needs actAs
# only on the account the job will run as, so the grants are bound to those
# accounts instead of to the project.
#
# Which account is that? It is not statically knowable from Terraform:
# gcp_batch.config.j2 emits batch.serviceAccountEmail only when an execution
# profile sets config_overrides.service_account, which is operator data in the
# execution_profiles table. Unset, GCP Batch falls back to the default compute
# account. So the bindings cover the plausible targets — this module's own
# accounts and the default compute account — and nothing else.
#
# Safe to narrow now precisely because it is not yet load-bearing:
# pipeline_config/batch_submitter.py::submit_to_batch is a stub that logs and
# returns a pseudo job id ("Session Q wires up the real gcloud Batch call"), so
# no actAs call is made today. Narrowing after Batch is wired would be a change
# with a live path under it; this one has none.
data "google_project" "this" {
  project_id = var.project_id
}

locals {
  # Accounts a Batch job might run as. Ordered for readability only.
  batch_runtime_accounts = {
    nextflow        = google_service_account.nextflow.email
    scrubber        = google_service_account.scrubber.email
    default_compute = "${data.google_project.this.number}-compute@developer.gserviceaccount.com"
  }
}

resource "google_service_account_iam_member" "api_acts_as" {
  for_each = local.batch_runtime_accounts

  service_account_id = "projects/${var.project_id}/serviceAccounts/${each.value}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "nextflow_batch_admin" {
  project = var.project_id
  role    = "roles/batch.jobsEditor"
  member  = "serviceAccount:${google_service_account.nextflow.email}"
}

resource "google_service_account_iam_member" "nextflow_acts_as" {
  for_each = local.batch_runtime_accounts

  service_account_id = "projects/${var.project_id}/serviceAccounts/${each.value}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.nextflow.email}"
}

resource "google_project_iam_member" "nextflow_logging_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.nextflow.email}"
}

resource "google_project_iam_member" "scrubber_logging_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.scrubber.email}"
}

# ── Bucket-level roles ───────────────────────────────────────────────────────
locals {
  api_rw_buckets = [
    var.buckets["sequences"],
    var.buckets["references"],
    var.buckets["results"],
    var.buckets["staging"],
    var.buckets["portal_exports"],
  ]

  nextflow_rw_buckets = [
    var.buckets["work"],
    var.buckets["sequences"],
    var.buckets["references"],
    var.buckets["results"],
  ]

  scrubber_read_buckets = [
    var.buckets["staging"],
  ]

  scrubber_write_buckets = [
    var.buckets["sequences"],
  ]
}

resource "google_storage_bucket_iam_member" "api_rw" {
  for_each = toset(local.api_rw_buckets)
  bucket   = each.value
  role     = "roles/storage.objectAdmin"
  member   = "serviceAccount:${google_service_account.api.email}"
}

resource "google_storage_bucket_iam_member" "nextflow_rw" {
  for_each = toset(local.nextflow_rw_buckets)
  bucket   = each.value
  role     = "roles/storage.objectAdmin"
  member   = "serviceAccount:${google_service_account.nextflow.email}"
}

resource "google_storage_bucket_iam_member" "scrubber_read" {
  for_each = toset(local.scrubber_read_buckets)
  bucket   = each.value
  role     = "roles/storage.objectViewer"
  member   = "serviceAccount:${google_service_account.scrubber.email}"
}

resource "google_storage_bucket_iam_member" "scrubber_write" {
  for_each = toset(local.scrubber_write_buckets)
  bucket   = each.value
  role     = "roles/storage.objectCreator"
  member   = "serviceAccount:${google_service_account.scrubber.email}"
}

# ── Artifact Registry read access (pull images at node startup) ──────────────
resource "google_artifact_registry_repository_iam_member" "api_reader" {
  project    = var.project_id
  location   = var.region
  repository = var.artifact_repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.api.email}"
}

resource "google_artifact_registry_repository_iam_member" "nextflow_reader" {
  project    = var.project_id
  location   = var.region
  repository = var.artifact_repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.nextflow.email}"
}

resource "google_artifact_registry_repository_iam_member" "scrubber_reader" {
  project    = var.project_id
  location   = var.region
  repository = var.artifact_repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.scrubber.email}"
}

# ── Workload Identity: KSA in GKE ↔ GSA ──────────────────────────────────────
resource "google_service_account_iam_member" "api_wi" {
  service_account_id = google_service_account.api.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.kubernetes_namespace}/${var.api_ksa_name}]"
}

resource "google_service_account_iam_member" "scrubber_wi" {
  service_account_id = google_service_account.scrubber.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.kubernetes_namespace}/${var.scrubber_ksa_name}]"
}

resource "google_service_account_iam_member" "nextflow_wi" {
  service_account_id = google_service_account.nextflow.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.kubernetes_namespace}/${var.nextflow_ksa_name}]"
}
