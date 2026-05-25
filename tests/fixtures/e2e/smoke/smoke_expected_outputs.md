# Smoke test — expected outputs

What a successful 30-minute smoke run produces. Reference for
`tests/e2e/scripts/verify_smoke_outputs.py` and for human eyeballs.

## After the DataHarmonizer-CSV ingest (smoke step 5)

Three rows in `samples` with `sample_id` values
`E1-SMOKE-001`, `E1-SMOKE-002`, `E1-SMOKE-003`. Each row carries
`organism_name = 'Severe acute respiratory syndrome coronavirus 2'`,
`sharing_level = 'PRIVATE'`, `lab_id = 1` (Example Lab), and a
`quality_status` populated by the validator (the smoke fixture is
clean enough to land at the highest configured tier; verify the value
is non-NULL).

## After the I-1 spreadsheet importer ingest (smoke step 6)

Three more rows in `samples` with `sample_id` values
`E1-SMOKE-XLSX-001` through `E1-SMOKE-XLSX-003`. The importer's column
names diverge from JACKPOT's schema (e.g. "Sample ID" → `sample_id`),
so the wizard's auto-suggest step must rewrite the headers before the
preview validates clean. Confidence scores on the suggested mapping
are non-zero for every column the wizard rewrites.

## After file registration (smoke step 7)

For each sample row, two `sample_files` rows (R1 + R2 paired-end FASTQ
references) with:

- `storage_state = 'EXTERNAL'`
- `uri` starts with `file://`
- `cheap_fingerprint` populated (from F-3, computed at register-time)

Within the F-4 cadence (default 5-minute interval, see
`full_hash_interval_seconds`) or after a manual trigger via
`tests/e2e/scripts/trigger_jobs.py compute_full_content_hash`,
`content_hash` is also populated.

## After pipeline launch (smoke step 9)

One row in `pipeline_runs` with:

- `pipeline_name = 'viralrecon'`
- `status = 'QUEUED'` immediately after launch
- `work_dir` and `result_uri` populated
- a config file at the path printed by the launch response (or under
  `<work_dir>/runs/<run_id>/jackpot_run.config` for the profile path)

If the operator has Nextflow installed and runs the rendered config to
completion, the pipeline transitions to `RUNNING` then `SUCCESS` and
`pipeline_results` rows appear. If not, the smoke test halts at QUEUED
with a documented config render — that is still a valid smoke pass for
the launch-handoff portion.

## Successful viralrecon test-profile outputs (when actually run)

Per `nf-core/viralrecon` test-profile documentation, a clean run on
the bundled test FASTQs produces:

- A consensus FASTA per sample (length around 29,800 bases for
  SARS-CoV-2; any value within ~29,000–30,000 is reasonable for the
  viralrecon test set)
- A VADR annotation directory per sample with a `*.pass.list`
  containing every sample (the test FASTQs are designed to pass)
- A variants VCF per sample with a small handful of called variants
- A coverage TSV with per-base depth statistics

The `pipeline_results` JSONB columns reference these outputs via the
keys defined in `shared/schemas/RESULT_SCHEMAS['viralrecon']` (see
`backend/backend/pipeline_schemas/`).

## After submission package generation (smoke step 11)

A new directory under `settings.submissions_output_root` named
`submission_<id>/` containing:

- `biosample.tsv` — three rows (one per sample) plus header
- `sra.tsv` — three rows
- `files/` — symlinks pointing back to the registered FASTQ URIs
- `seqsender_config.yaml` — parses without error; mentions the NCBI
  repository
- `README.md` — names the target repository as NCBI and lists the
  three sample identifiers

`submissions.state` transitions from `DRAFT` to `READY_TO_SUBMIT`
once the package is generated.

## After mark-submitted (smoke step 12)

`submissions.state` transitions to `SUBMITTED`. An audit log row
appears with `action = 'SUBMISSION_MARKED_SUBMITTED'` (or whatever the
canonical action constant is at HEAD; the I-2 docs in
`docs/api/submissions.md` are the authoritative reference).
