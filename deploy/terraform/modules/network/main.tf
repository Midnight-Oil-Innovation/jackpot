locals {
  name_prefix = "jackpot-${var.environment}"
}

resource "google_compute_network" "vpc" {
  project                 = var.project_id
  name                    = "${local.name_prefix}-vpc"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
  description             = "JACKPOT ${var.environment} VPC — private GKE + Cloud SQL via PSC."
}

resource "google_compute_subnetwork" "gke" {
  project                  = var.project_id
  name                     = "${local.name_prefix}-gke-subnet"
  region                   = var.region
  network                  = google_compute_network.vpc.id
  ip_cidr_range            = var.subnet_cidr
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "${local.name_prefix}-pods"
    ip_cidr_range = var.pods_cidr
  }

  secondary_ip_range {
    range_name    = "${local.name_prefix}-services"
    ip_cidr_range = var.services_cidr
  }
}

resource "google_compute_router" "router" {
  project = var.project_id
  name    = "${local.name_prefix}-router"
  region  = var.region
  network = google_compute_network.vpc.id
}

resource "google_compute_router_nat" "nat" {
  project                            = var.project_id
  name                               = "${local.name_prefix}-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

resource "google_compute_global_address" "psc_range" {
  project       = var.project_id
  name          = "${local.name_prefix}-psc-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = var.psc_prefix_length
  network       = google_compute_network.vpc.id
  description   = "Reserved range for Private Service Connect peering (Cloud SQL)."
}

resource "google_service_networking_connection" "psc" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.psc_range.name]
}
