output "network_id" {
  description = "Full resource ID of the VPC network."
  value       = google_compute_network.vpc.id
}

output "network_name" {
  description = "Name of the VPC network."
  value       = google_compute_network.vpc.name
}

output "network_self_link" {
  description = "Self-link of the VPC network."
  value       = google_compute_network.vpc.self_link
}

output "subnet_id" {
  description = "Full resource ID of the GKE subnet."
  value       = google_compute_subnetwork.gke.id
}

output "subnet_name" {
  description = "Name of the GKE subnet."
  value       = google_compute_subnetwork.gke.name
}

output "subnet_self_link" {
  description = "Self-link of the GKE subnet."
  value       = google_compute_subnetwork.gke.self_link
}

output "pods_secondary_range_name" {
  description = "Name of the secondary range for GKE pods."
  value       = google_compute_subnetwork.gke.secondary_ip_range[0].range_name
}

output "services_secondary_range_name" {
  description = "Name of the secondary range for GKE services."
  value       = google_compute_subnetwork.gke.secondary_ip_range[1].range_name
}

output "psc_connection" {
  description = "Service networking connection — used by Cloud SQL private IP."
  value       = google_service_networking_connection.psc.network
}
