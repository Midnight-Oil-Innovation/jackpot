variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "environment" {
  description = "Environment name (staging, production). Drives secret naming: jackpot-<env>-<name>."
  type        = string
}

variable "region" {
  description = "Region to pin secret replicas to. Set to null for automatic replication."
  type        = string
  default     = null
}

variable "secret_names" {
  description = "List of secret short names (without environment prefix). Each becomes jackpot-<env>-<name>. Names double as the env-var key (upper-cased, dashes → underscores) so the deploy pipeline can map secret → env var mechanically."
  type        = list(string)
  default = [
    "secret-key",
    "database-url",
    "google-oauth-client-id",
    "google-oauth-client-secret",
    "ncbi-api-key",
    "gisaid-username",
    "gisaid-password",
  ]
}

variable "labels" {
  description = "Labels applied to every secret."
  type        = map(string)
  default     = {}
}

variable "accessors" {
  description = "Service account emails granted roles/secretmanager.secretAccessor on every secret. Bucket-level + project-level bindings live in the iam module; this keeps the scope tight to the specific secrets."
  type        = list(string)
  default     = []
}
