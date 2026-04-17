output "api_sa_email" {
  description = "Service account email for the FastAPI backend pods."
  value       = google_service_account.api.email
}

output "scrubber_sa_email" {
  description = "Service account email for scrubber GKE Jobs."
  value       = google_service_account.scrubber.email
}

output "nextflow_sa_email" {
  description = "Service account email for Nextflow controllers."
  value       = google_service_account.nextflow.email
}

output "api_ksa_annotation" {
  description = "Value of the iam.gke.io/gcp-service-account annotation the jackpot-api KSA needs."
  value       = google_service_account.api.email
}

output "scrubber_ksa_annotation" {
  description = "Value of the iam.gke.io/gcp-service-account annotation the jackpot-scrubber KSA needs."
  value       = google_service_account.scrubber.email
}

output "nextflow_ksa_annotation" {
  description = "Value of the iam.gke.io/gcp-service-account annotation the jackpot-nextflow KSA needs."
  value       = google_service_account.nextflow.email
}
