output "project_id" {
  value = var.project_id
}

output "region" {
  value = var.region
}

output "gke_cluster_name" {
  value = module.gke.cluster_name
}

output "gke_cluster_location" {
  value = module.gke.cluster_location
}

output "cloudsql_instance_name" {
  value = module.cloud_sql.instance_name
}

output "cloudsql_connection_name" {
  value = module.cloud_sql.connection_name
}

output "cloudsql_private_ip" {
  value     = module.cloud_sql.private_ip_address
  sensitive = true
}

output "database_name" {
  value = module.cloud_sql.database_name
}

output "database_user" {
  value = module.cloud_sql.database_user
}

output "docker_repo_url" {
  description = "Artifact Registry Docker URL — tag images as <this>/jackpot-api:<tag>."
  value       = module.artifact_registry.docker_repo_url
}

output "buckets" {
  description = "Map of purpose -> bucket name."
  value       = module.buckets.all_buckets
}

output "api_sa_email" {
  value = module.iam.api_sa_email
}

output "scrubber_sa_email" {
  value = module.iam.scrubber_sa_email
}

output "nextflow_sa_email" {
  value = module.iam.nextflow_sa_email
}
