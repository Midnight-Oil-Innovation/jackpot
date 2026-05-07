# Smoke test fixtures (E-1)

Synthetic, deterministic, single-organism (SARS-CoV-2) fixtures for the
30-minute smoke section of `docs/e2e_uat_plan.md`. These are committed
to the repo because they are entirely synthetic — no PII, no real lab
data, no real BioSample identifiers.

## Contents

- `metadata.csv` — three-row metadata sheet matching the JACKPOT
  schema's column names directly. Used for the DataHarmonizer-CSV
  ingest path of the smoke flow.
- `metadata_xlsx.csv` — same three rows in a CSV the operator converts
  to `.xlsx` locally (we do not commit binary spreadsheets so diffs
  remain readable). Convert with `libreoffice --headless --convert-to
  xlsx metadata_xlsx.csv` or open the CSV in Numbers / Excel and save
  as `metadata.xlsx`. Used for the I-1 spreadsheet importer wizard
  flow.
- `smoke_expected_outputs.md` — what a successful smoke run produces
  (file-state DB rows, pipeline_results JSONB shape, submission package
  contents).

## viralrecon test FASTQs

The viralrecon `test` profile pulls its FASTQs directly from
`nf-core/test-datasets`. The smoke test does not bundle these; the
operator either:

- Lets `nextflow run nf-core/viralrecon -profile test` fetch them on
  demand (recommended for the actual pipeline-run portion of the
  smoke test), or
- Pre-stages them to a local path and registers `file://` URIs through
  JACKPOT (the launch-handoff portion exercises this path without
  actually running viralrecon).

Sample IDs in `metadata.csv` are intentionally namespaced with
`E1-SMOKE-NNN` so `tests/e2e/scripts/reset_environment.sh` can scrub
them cleanly between runs without touching unrelated dev data.
