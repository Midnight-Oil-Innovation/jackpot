variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "Region for the Artifact Registry repository."
  type        = string
}

variable "environment" {
  description = "Environment name (staging, production). Drives resource naming."
  type        = string
}

variable "repository_id" {
  description = "Artifact Registry repository ID. Conventional value is `jackpot`."
  type        = string
  default     = "jackpot"
}

variable "labels" {
  description = "Labels applied to the repository."
  type        = map(string)
  default     = {}
}
