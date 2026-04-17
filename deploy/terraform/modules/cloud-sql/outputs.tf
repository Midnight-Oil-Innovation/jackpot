output "instance_name" {
  description = "Name of the Cloud SQL instance."
  value       = google_sql_database_instance.this.name
}

output "connection_name" {
  description = "Connection name used by the Cloud SQL proxy and sqlalchemy+cloud-sql-python-connector."
  value       = google_sql_database_instance.this.connection_name
}

output "private_ip_address" {
  description = "Private IP address of the Cloud SQL instance. Pods in the VPC connect directly to this."
  value       = google_sql_database_instance.this.private_ip_address
}

output "database_name" {
  description = "Name of the application database."
  value       = google_sql_database.app.name
}

output "database_user" {
  description = "Name of the application DB user."
  value       = google_sql_user.app.name
}
