variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "Primary region for non-backup buckets."
  type        = string
}

variable "backups_region" {
  description = "Region for the backups bucket — must differ from the primary region."
  type        = string
  default     = "us-east1"
}

variable "environment" {
  description = "Environment name (staging, production). Drives bucket naming: jackpot-<env>-<purpose>."
  type        = string
}

variable "work_lifecycle_days" {
  description = "Age in days at which jackpot-work objects are deleted."
  type        = number
  default     = 90
}

variable "backups_lifecycle_days" {
  description = "Age in days at which jackpot-backups objects become deletable (also used for Object Lock retention)."
  type        = number
  default     = 90
}

variable "labels" {
  description = "Labels applied to every bucket. `purpose` is merged in per bucket."
  type        = map(string)
  default     = {}
}
