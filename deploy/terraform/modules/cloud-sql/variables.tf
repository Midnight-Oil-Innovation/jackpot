variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "Region for the Cloud SQL instance."
  type        = string
}

variable "environment" {
  description = "Environment name (staging, production). Drives resource naming."
  type        = string
}

variable "network_id" {
  description = "Full resource ID of the VPC network used for private IP."
  type        = string
}

variable "psc_connection" {
  description = "Service networking connection output from the network module. Ensures PSC peering exists before the instance is created."
  type        = string
}

variable "database_version" {
  description = "Cloud SQL version."
  type        = string
  default     = "POSTGRES_16"
}

variable "tier" {
  description = "Cloud SQL machine tier."
  type        = string
  default     = "db-custom-1-3840"
}

variable "disk_size_gb" {
  description = "Initial disk size in GB (auto-resize is enabled)."
  type        = number
  default     = 20
}

variable "disk_type" {
  description = "Disk type."
  type        = string
  default     = "PD_SSD"
}

variable "backup_retention_days" {
  description = "Number of daily backups to retain."
  type        = number
  default     = 30
}

variable "transaction_log_retention_days" {
  description = "PITR transaction log retention (1–7 days)."
  type        = number
  default     = 7
}

variable "maintenance_window_day" {
  description = "Day of week (1=Mon … 7=Sun) for the maintenance window."
  type        = number
  default     = 7
}

variable "maintenance_window_hour" {
  description = "Hour (0–23 UTC) for the maintenance window."
  type        = number
  default     = 9
}

variable "deletion_protection" {
  description = "Block `terraform destroy` from removing the instance."
  type        = bool
  default     = true
}

variable "database_name" {
  description = "Name of the application database to create inside the instance."
  type        = string
  default     = "jackpot_db"
}

variable "database_user" {
  description = "Name of the application DB user to create."
  type        = string
  default     = "jackpot"
}

variable "database_password" {
  description = "Initial password for the application DB user. Rotate via `gcloud sql users set-password` after apply."
  type        = string
  sensitive   = true
}

variable "labels" {
  description = "Labels applied to the Cloud SQL instance."
  type        = map(string)
  default     = {}
}
