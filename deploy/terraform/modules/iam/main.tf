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

resource "google_project_iam_member" "api_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "nextflow_batch_admin" {
  project = var.project_id
  role    = "roles/batch.jobsEditor"
  member  = "serviceAccount:${google_service_account.nextflow.email}"
}

resource "google_project_iam_member" "nextflow_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.nextflow.email}"
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
