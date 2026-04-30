output "sequences" {
  description = "Raw + scrubbed FASTQ/FASTA storage."
  value       = google_storage_bucket.sequences.name
}

output "references" {
  description = "Reference genomes and BED files."
  value       = google_storage_bucket.references.name
}

output "results" {
  description = "Pipeline output bucket."
  value       = google_storage_bucket.results.name
}

output "staging" {
  description = "Temporary pre-scrub upload bucket."
  value       = google_storage_bucket.staging.name
}

output "work" {
  description = "Nextflow/Cromwell work directory bucket. Ephemeral — no versioning."
  value       = google_storage_bucket.work.name
}

output "backups" {
  description = "Weekly Cloud SQL dumps + disaster recovery. WORM-locked."
  value       = google_storage_bucket.backups.name
}

output "portal_exports" {
  description = "Portal submission bundles (NCBI, GISAID) prior to upload."
  value       = google_storage_bucket.portal_exports.name
}

output "all_buckets" {
  description = "Map of purpose -> bucket name. Used by IAM bindings."
  value = {
    sequences      = google_storage_bucket.sequences.name
    references     = google_storage_bucket.references.name
    results        = google_storage_bucket.results.name
    staging        = google_storage_bucket.staging.name
    work           = google_storage_bucket.work.name
    backups        = google_storage_bucket.backups.name
    portal_exports = google_storage_bucket.portal_exports.name
  }
}
