resource "google_artifact_registry_repository" "docker" {
  project       = var.project_id
  location      = var.region
  repository_id = var.repository_id
  format        = "DOCKER"
  description   = "JACKPOT ${var.environment} backend + pipeline container images."

  labels = var.labels
}
