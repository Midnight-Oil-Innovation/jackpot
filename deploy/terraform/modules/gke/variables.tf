variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "Region for the regional GKE cluster."
  type        = string
}

variable "environment" {
  description = "Environment name (staging, production). Drives resource naming."
  type        = string
}

variable "network_self_link" {
  description = "Self-link of the VPC network hosting the cluster."
  type        = string
}

variable "subnet_self_link" {
  description = "Self-link of the GKE subnet."
  type        = string
}

variable "pods_secondary_range_name" {
  description = "Name of the subnet secondary range for pod IPs."
  type        = string
}

variable "services_secondary_range_name" {
  description = "Name of the subnet secondary range for service IPs."
  type        = string
}

variable "master_ipv4_cidr_block" {
  description = "Private CIDR block for the GKE control plane."
  type        = string
  default     = "172.16.0.0/28"
}

variable "master_authorized_networks" {
  description = "CIDRs allowed to reach the GKE public control-plane endpoint."
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  default = []
}

variable "release_channel" {
  description = "GKE release channel (RAPID, REGULAR, STABLE)."
  type        = string
  default     = "REGULAR"
}

variable "api_pool" {
  description = "api-pool sizing and machine type."
  type = object({
    machine_type = string
    min_nodes    = number
    max_nodes    = number
    disk_size_gb = number
  })
  default = {
    machine_type = "n2-standard-4"
    min_nodes    = 1
    max_nodes    = 3
    disk_size_gb = 50
  }
}

variable "workspace_pool" {
  description = "workspace-pool sizing and machine type."
  type = object({
    machine_type = string
    min_nodes    = number
    max_nodes    = number
    disk_size_gb = number
  })
  default = {
    machine_type = "n2-standard-8"
    min_nodes    = 0
    max_nodes    = 2
    disk_size_gb = 100
  }
}

variable "scrubber_pool" {
  description = "scrubber-pool sizing, machine type, and spot flag."
  type = object({
    machine_type = string
    min_nodes    = number
    max_nodes    = number
    disk_size_gb = number
    spot         = bool
  })
  default = {
    machine_type = "n2-highmem-4"
    min_nodes    = 0
    max_nodes    = 3
    disk_size_gb = 100
    spot         = true
  }
}

variable "labels" {
  description = "Resource labels."
  type        = map(string)
  default     = {}
}

variable "deletion_protection" {
  description = "Block `terraform destroy` from removing the cluster."
  type        = bool
  default     = true
}
