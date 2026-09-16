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
  description = <<-EOT
    CIDRs allowed to reach the GKE public control-plane endpoint.

    Empty authorises no external network. That is the module's behaviour as of
    the fail-closed change — see modules/gke/main.tf for why it takes two
    fields rather than one.

    Deploying from GitHub-hosted runners needs an entry here: their egress IPs
    are dynamic, so either authorise the ranges you accept, or move the deploy
    onto Connect Gateway / a self-hosted runner. Accepting anything now means
    writing 0.0.0.0/0 explicitly, where a reviewer and a plan diff both see it.

    This also governs break-glass access: `kubectl` and `helm` from an
    operator's laptop go through the same endpoint, including the Rule 49
    rollback for a wedged release. See deploy/docs/staging_access.md.
  EOT
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
