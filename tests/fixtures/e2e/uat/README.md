# UAT fixtures (E-1)

Comprehensive multi-role acceptance test fixtures for the UAT section
of `docs/e2e_uat_plan.md`. Two committed CSVs (synthetic, anonymised)
and a gitignored space for FASTQ data sourced locally.

## Hard rule on what goes in this directory

These fixtures are public domain or fully synthetic. Do not place
real lab data, real PII, or real PHI in this directory unless you
have cleared provenance and IRB obligations with your local ethics
review. The `.gitignore` rules under `tests/fixtures/e2e/uat/*.fastq*`
prevent accidental commits, but they do not prevent disclosure to
anyone with filesystem access to your laptop.

## Committed contents

- `tricky_metadata.csv` — synthetic sheet with non-canonical column
  names ("Sample ID", "Date Collected", "Hosp"), missing required
  fields on some rows, malformed dates, and `source_type` values that
  miss the controlled vocabulary. Drives the I-1 spreadsheet importer
  auto-suggest test (UAT cross-cutting section D).
- `realistic_metadata.csv` — synthetic but shape-realistic sheet that
  mimics what a real Arizona SARS-CoV-2 ingest looks like. Column
  names already match the JACKPOT schema (no auto-suggest exercise).
  Drives the smoke-style happy-path tests for non-Platform-Admin roles.
- `.gitkeep` — preserves this directory in the tree even when no
  FASTQs are staged locally.

## Gitignored: SARS-CoV-2 FASTQs

The UAT executes parts of viralrecon end-to-end, which requires real
paired-end FASTQs. Two acceptable sources:

1. **Public Arizona SARS-CoV-2 batch from SRA / GenBank**. Glen has a
   batch accessioned through APGAP that is now public-domain; copy
   the `.fastq.gz` files into `tests/fixtures/e2e/uat/sars-cov-2/`.
   Sample IDs in `realistic_metadata.csv` reference these by name.
2. **`nf-core/test-datasets` viralrecon set**. Same FASTQs the smoke
   test uses; copy them into `tests/fixtures/e2e/uat/sars-cov-2/`. The
   UAT is happy with this as a fallback if no public Arizona batch is
   handy.

The `.gitignore` excludes `*.fastq`, `*.fastq.gz`, `*.fq`, `*.fq.gz`,
`*.bam`, `*.cram`, and `sars-cov-2/` under this directory. New binary
formats: extend `.gitignore` before staging them.

## Why these are not in `tests/fixtures/e2e/smoke/`

The smoke fixtures are deterministic and tiny; the UAT fixtures are
realistic and larger. Mixing them into one directory would conflate
"this should pass on every laptop in 30 minutes" with "this exercises
the full role matrix and depends on operator-staged data." Different
.gitignore policies, different reviewer expectations.

## Schema notes for the realistic CSV

The realistic sheet declares `sequencing_lab = 'Example Lab'` so the
seed `sequencing_labs` row resolves without operator setup. If the
UAT tests against a different sequencing_lab name, edit the column
before running rather than mutating seed data.
