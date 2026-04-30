locals {
  name_prefix = "jackpot-${var.environment}"

  secret_full_names = { for s in var.secret_names : s => "${local.name_prefix}-${s}" }

  accessor_bindings = flatten([
    for secret in var.secret_names : [
      for email in var.accessors : {
        secret = secret
        email  = email
      }
    ]
  ])
}

resource "google_secret_manager_secret" "this" {
  for_each = local.secret_full_names

  project   = var.project_id
  secret_id = each.value

  labels = merge(var.labels, { purpose = each.key })

  replication {
    dynamic "auto" {
      for_each = var.region == null ? [1] : []
      content {}
    }

    dynamic "user_managed" {
      for_each = var.region == null ? [] : [1]
      content {
        replicas {
          location = var.region
        }
      }
    }
  }
}

resource "google_secret_manager_secret_iam_member" "accessor" {
  for_each = { for b in local.accessor_bindings : "${b.secret}--${b.email}" => b }

  project   = var.project_id
  secret_id = google_secret_manager_secret.this[each.value.secret].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value.email}"
}
