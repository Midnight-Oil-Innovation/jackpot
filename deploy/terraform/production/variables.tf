variable "project_id" {
  description = "GCP project ID for the JACKPOT production environment."
  type        = string
}

variable "region" {
  description = "Primary GCP region."
  type        = string
  default     = "us-central1"
}

variable "backups_region" {
  description = "Region for the backups bucket — must differ from the primary region."
  type        = string
  default     = "us-east1"
}

variable "environment" {
  description = "Environment name used to prefix resources."
  type        = string
  default     = "production"
}

variable "db_password" {
  description = "Initial password for the jackpot DB user. Rotate via `gcloud sql users set-password` after apply."
  type        = string
  sensitive   = true
}

variable "master_authorized_networks" {
  description = "CIDRs allowed to reach the GKE public control-plane endpoint."
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  default = []
}

variable "deletion_protection" {
  description = "Block `terraform destroy` from removing billable/stateful resources (Cloud SQL, GKE)."
  type        = bool
  default     = true
}

# Larger instance sizes for production. Overrides module defaults.
variable "cloud_sql_tier" {
  description = "Cloud SQL machine tier for production."
  type        = string
  default     = "db-custom-2-7680"
}

variable "cloud_sql_disk_size_gb" {
  description = "Cloud SQL disk size for production."
  type        = number
  default     = 100
}
