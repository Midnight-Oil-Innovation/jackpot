output "repository_id" {
  description = "Repository ID (short name)."
  value       = google_artifact_registry_repository.docker.repository_id
}

output "repository_name" {
  description = "Full resource name of the repository."
  value       = google_artifact_registry_repository.docker.name
}

output "docker_host" {
  description = "Hostname for `docker push`/`docker pull` (e.g. us-central1-docker.pkg.dev)."
  value       = "${var.region}-docker.pkg.dev"
}

output "docker_repo_url" {
  description = "Fully qualified repository URL: <region>-docker.pkg.dev/<project>/<repo>."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}"
}
