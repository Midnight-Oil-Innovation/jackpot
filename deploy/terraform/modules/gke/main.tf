locals {
  name_prefix  = "jackpot-${var.environment}"
  cluster_name = "${local.name_prefix}-gke"
}

resource "google_container_cluster" "this" {
  project  = var.project_id
  name     = local.cluster_name
  location = var.region

  network    = var.network_self_link
  subnetwork = var.subnet_self_link

  remove_default_node_pool = true
  initial_node_count       = 1
  deletion_protection      = var.deletion_protection

  release_channel {
    channel = var.release_channel
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = var.pods_secondary_range_name
    services_secondary_range_name = var.services_secondary_range_name
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = var.master_ipv4_cidr_block
  }

  dynamic "master_authorized_networks_config" {
    for_each = length(var.master_authorized_networks) > 0 ? [1] : []
    content {
      dynamic "cidr_blocks" {
        for_each = var.master_authorized_networks
        content {
          cidr_block   = cidr_blocks.value.cidr_block
          display_name = cidr_blocks.value.display_name
        }
      }
    }
  }

  addons_config {
    http_load_balancing {
      disabled = false
    }
    horizontal_pod_autoscaling {
      disabled = false
    }
  }

  logging_service    = "logging.googleapis.com/kubernetes"
  monitoring_service = "monitoring.googleapis.com/kubernetes"

  resource_labels = var.labels
}

resource "google_container_node_pool" "api" {
  project    = var.project_id
  name       = "api-pool"
  location   = var.region
  cluster    = google_container_cluster.this.name
  node_count = var.api_pool.min_nodes

  autoscaling {
    min_node_count = var.api_pool.min_nodes
    max_node_count = var.api_pool.max_nodes
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type = var.api_pool.machine_type
    disk_size_gb = var.api_pool.disk_size_gb
    disk_type    = "pd-balanced"
    image_type   = "COS_CONTAINERD"
    labels       = merge(var.labels, { pool = "api" })

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }
}

resource "google_container_node_pool" "workspace" {
  project  = var.project_id
  name     = "workspace-pool"
  location = var.region
  cluster  = google_container_cluster.this.name

  autoscaling {
    min_node_count = var.workspace_pool.min_nodes
    max_node_count = var.workspace_pool.max_nodes
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type = var.workspace_pool.machine_type
    disk_size_gb = var.workspace_pool.disk_size_gb
    disk_type    = "pd-balanced"
    image_type   = "COS_CONTAINERD"
    labels       = merge(var.labels, { pool = "workspace" })

    taint {
      key    = "workload"
      value  = "workspace"
      effect = "NO_SCHEDULE"
    }

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }
}

resource "google_container_node_pool" "scrubber" {
  project  = var.project_id
  name     = "scrubber-pool"
  location = var.region
  cluster  = google_container_cluster.this.name

  autoscaling {
    min_node_count = var.scrubber_pool.min_nodes
    max_node_count = var.scrubber_pool.max_nodes
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type = var.scrubber_pool.machine_type
    disk_size_gb = var.scrubber_pool.disk_size_gb
    disk_type    = "pd-balanced"
    image_type   = "COS_CONTAINERD"
    spot         = var.scrubber_pool.spot
    labels       = merge(var.labels, { pool = "scrubber" })

    taint {
      key    = "workload"
      value  = "scrubber"
      effect = "NO_SCHEDULE"
    }

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }
}
