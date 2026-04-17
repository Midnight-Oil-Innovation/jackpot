output "secret_ids" {
  description = "Map of short-name -> full Secret Manager secret ID (projects/<num>/secrets/<full-name>)."
  value       = { for k, s in google_secret_manager_secret.this : k => s.id }
}

output "secret_names" {
  description = "Map of short-name -> secret name (jackpot-<env>-<short>). These are the names passed to `gcloud secrets versions add`."
  value       = { for k, s in google_secret_manager_secret.this : k => s.secret_id }
}

output "seed_commands" {
  description = "Copy-paste gcloud commands to add placeholder values for every secret. Replace the value expression before running in production."
  value = [
    for k, s in google_secret_manager_secret.this :
    "echo -n 'REPLACE_ME' | gcloud secrets versions add ${s.secret_id} --data-file=- --project=${var.project_id}"
  ]
}
