variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "Primary region for the VPC subnet, router, and NAT."
  type        = string
}

variable "environment" {
  description = "Environment name (staging, production). Drives resource naming."
  type        = string
}

variable "subnet_cidr" {
  description = "Primary IPv4 CIDR range for the GKE nodes subnet."
  type        = string
  default     = "10.10.0.0/20"
}

variable "pods_cidr" {
  description = "Secondary IPv4 range for GKE pods (VPC-native alias IPs)."
  type        = string
  default     = "10.20.0.0/14"
}

variable "services_cidr" {
  description = "Secondary IPv4 range for GKE services (VPC-native alias IPs)."
  type        = string
  default     = "10.24.0.0/20"
}

variable "psc_prefix_length" {
  description = "Prefix length for the Private Service Connect range reserved for Cloud SQL peering."
  type        = number
  default     = 24
}

variable "labels" {
  description = "Labels applied to labelable network resources."
  type        = map(string)
  default     = {}
}
