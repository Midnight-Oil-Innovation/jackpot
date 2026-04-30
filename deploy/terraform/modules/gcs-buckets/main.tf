locals {
  name_prefix = "jackpot-${var.environment}"
}

resource "google_storage_bucket" "sequences" {
  project                     = var.project_id
  name                        = "${local.name_prefix}-sequences"
  location                    = var.region
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  labels = merge(var.labels, { purpose = "sequences" })
}

resource "google_storage_bucket" "references" {
  project                     = var.project_id
  name                        = "${local.name_prefix}-references"
  location                    = var.region
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  labels = merge(var.labels, { purpose = "references" })
}

resource "google_storage_bucket" "results" {
  project                     = var.project_id
  name                        = "${local.name_prefix}-results"
  location                    = var.region
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  labels = merge(var.labels, { purpose = "results" })
}

resource "google_storage_bucket" "staging" {
  project                     = var.project_id
  name                        = "${local.name_prefix}-staging"
  location                    = var.region
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }

  labels = merge(var.labels, { purpose = "staging" })
}

resource "google_storage_bucket" "work" {
  project                     = var.project_id
  name                        = "${local.name_prefix}-work"
  location                    = var.region
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  lifecycle_rule {
    condition {
      age = var.work_lifecycle_days
    }
    action {
      type = "Delete"
    }
  }

  labels = merge(var.labels, { purpose = "work" })
}

resource "google_storage_bucket" "backups" {
  project                     = var.project_id
  name                        = "${local.name_prefix}-backups"
  location                    = var.backups_region
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  retention_policy {
    retention_period = var.backups_lifecycle_days * 86400
    is_locked        = false
  }

  lifecycle_rule {
    condition {
      age = var.backups_lifecycle_days
    }
    action {
      type = "Delete"
    }
  }

  labels = merge(var.labels, { purpose = "backups" })
}

resource "google_storage_bucket" "portal_exports" {
  project                     = var.project_id
  name                        = "${local.name_prefix}-portal-exports"
  location                    = var.region
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  lifecycle_rule {
    condition {
      age = 180
    }
    action {
      type = "Delete"
    }
  }

  labels = merge(var.labels, { purpose = "portal-exports" })
}
