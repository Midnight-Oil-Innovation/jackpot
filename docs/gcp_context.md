# JACKPOT GCP Context

## Projects
- Staging: jackpot-staging-project
- Production: <TBD — Month 3>

## Regions
- Primary: us-central1
- Backup/DR: us-east1

## GCS Bucket Naming Convention
- jackpot-<env>-<purpose>
- Example: jackpot-staging-sequences, jackpot-staging-work

## Artifact Registry
- Repo: us-central1-docker.pkg.dev/<project-id>/jackpot

## Secret Manager
- All secrets prefixed with `jackpot-<env>-` (e.g. jackpot-staging-secret-key)

## Service Accounts
- jackpot-api@<project-id>.iam.gserviceaccount.com
- jackpot-scrubber@<project-id>.iam.gserviceaccount.com
- jackpot-nextflow@<project-id>.iam.gserviceaccount.com
