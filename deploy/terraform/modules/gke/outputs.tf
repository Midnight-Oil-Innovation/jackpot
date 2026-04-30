output "cluster_name" {
  description = "Name of the GKE cluster."
  value       = google_container_cluster.this.name
}

output "cluster_endpoint" {
  description = "Control-plane endpoint."
  value       = google_container_cluster.this.endpoint
  sensitive   = true
}

output "cluster_ca_certificate" {
  description = "Base64-encoded CA certificate for the cluster."
  value       = google_container_cluster.this.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "cluster_location" {
  description = "Location of the cluster (region for regional clusters)."
  value       = google_container_cluster.this.location
}

output "workload_identity_pool" {
  description = "Workload Identity pool attached to the cluster."
  value       = "${var.project_id}.svc.id.goog"
}
