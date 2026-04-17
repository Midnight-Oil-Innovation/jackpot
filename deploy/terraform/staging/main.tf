locals {
  labels = {
    env          = var.environment
    project_name = "jackpot"
  }
}

module "network" {
  source = "../modules/network"

  project_id  = var.project_id
  region      = var.region
  environment = var.environment
  labels      = local.labels
}

module "cloud_sql" {
  source = "../modules/cloud-sql"

  project_id          = var.project_id
  region              = var.region
  environment         = var.environment
  network_id          = module.network.network_id
  psc_connection      = module.network.psc_connection
  database_password   = var.db_password
  deletion_protection = var.deletion_protection
  labels              = local.labels
}

module "artifact_registry" {
  source = "../modules/artifact-registry"

  project_id  = var.project_id
  region      = var.region
  environment = var.environment
  labels      = local.labels
}

module "buckets" {
  source = "../modules/gcs-buckets"

  project_id     = var.project_id
  region         = var.region
  backups_region = var.backups_region
  environment    = var.environment
  labels         = local.labels
}

module "gke" {
  source = "../modules/gke"

  project_id                    = var.project_id
  region                        = var.region
  environment                   = var.environment
  network_self_link             = module.network.network_self_link
  subnet_self_link              = module.network.subnet_self_link
  pods_secondary_range_name     = module.network.pods_secondary_range_name
  services_secondary_range_name = module.network.services_secondary_range_name
  master_authorized_networks    = var.master_authorized_networks
  deletion_protection           = var.deletion_protection
  labels                        = local.labels
}

module "iam" {
  source = "../modules/iam"

  project_id               = var.project_id
  environment              = var.environment
  buckets                  = module.buckets.all_buckets
  artifact_repository_name = module.artifact_registry.repository_name
}
