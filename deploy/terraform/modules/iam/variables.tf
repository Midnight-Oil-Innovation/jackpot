variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "environment" {
  description = "Environment name (staging, production). Drives SA naming."
  type        = string
}

variable "buckets" {
  description = "Map of purpose -> bucket name, as output by the gcs-buckets module."
  type        = map(string)
}

variable "artifact_repository_name" {
  description = "Full Artifact Registry repository resource name."
  type        = string
}

variable "kubernetes_namespace" {
  description = "Kubernetes namespace where the backend pods run. Used for Workload Identity bindings."
  type        = string
  default     = "jackpot"
}

variable "api_ksa_name" {
  description = "Kubernetes ServiceAccount name for the API pods."
  type        = string
  default     = "jackpot-api"
}

variable "scrubber_ksa_name" {
  description = "Kubernetes ServiceAccount name for scrubber jobs."
  type        = string
  default     = "jackpot-scrubber"
}

variable "nextflow_ksa_name" {
  description = "Kubernetes ServiceAccount name for Nextflow controllers."
  type        = string
  default     = "jackpot-nextflow"
}
