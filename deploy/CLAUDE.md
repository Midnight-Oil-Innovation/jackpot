# CLAUDE.md — deploy/

Infra reference for `deploy/`. Migrated out of the root `CLAUDE.md` on
2026-08-21 (doctor pass) — GKE autoscaling and disaster-recovery detail
only matters when touching infra, so it loads here instead of every
session.

---

## GKE Autoscaling Architecture

JACKPOT uses three separate GKE node pools, each tuned to its workload.
Pipeline compute runs on GCP Batch entirely outside GKE — GKE only runs
the lightweight Nextflow controller process. Never submit pipeline tasks
as GKE pods.

### Node pool summary

| Pool | Workload | Machine type | Min nodes | Max nodes | Spot? |
|---|---|---|---|---|---|
| `api-pool` | FastAPI, Streamlit, Nextflow controllers | n2-standard-4 (4CPU/16GB) | 2 | 6 | No — always on |
| `workspace-pool` | JupyterHub user pods | n2-standard-8 (8CPU/32GB) | 0 | 10 | No — user-interactive |
| `scrubber-pool` | SRA Human Scrubber GKE Jobs | n2-highmem-4 (4CPU/32GB) | 0 | 20 | Yes — restartable |

GCP Batch (not GKE) handles all Nextflow pipeline task compute. GKE only
runs the Nextflow process itself (~2CPU/4GB) in the api-pool.

### Autoscaling per workload

**API and frontend (api-pool)**
HPA based on CPU utilization — adds FastAPI/Streamlit pods across existing
api-pool nodes when load increases. Min replicas=2 for availability.
api-pool never scales to zero — always at least 2 nodes running.

**Workspace pods (workspace-pool)**
No pod-level autoscaling — each pod is personal to one researcher, sized
by their chosen profile. Scaling unit is nodes: cluster autoscaler adds
workspace-pool nodes as more pods are scheduled. Scale-to-zero when no
workspaces active. Placeholder pod (low-priority pause container) keeps
one node warm during business hours (8am–8pm UTC−8:00) via CronJob — prevents
3–5 minute cold starts for the first researcher of the day.

**Scrubber jobs (scrubber-pool)**
GKE Jobs (not Deployments) — one Job per scrubber invocation. Scale-to-zero
when no scrubbing in progress. Cluster autoscaler adds scrubber-pool nodes
as Jobs are submitted. Spot/preemptible nodes — scrubber is restartable
if preempted (sample stays IN_PROGRESS, job resubmitted).

**Scrubber concurrency limit (critical for bulk uploads)**
When a Globus deposit brings in 100 samples simultaneously, submitting 100
GKE Jobs at once would spike cost unpredictably. Instead, a scrubber job
queue in the database controls concurrency:

- All pending scrubber jobs enter the queue as scrub_status=PENDING
- `run_scrubber_queue_job()` in backend/jobs.py fires every minute
- Checks how many scrubber jobs are currently IN_PROGRESS
- If below the concurrency limit (default=10, configurable), promotes
  the next PENDING samples to IN_PROGRESS and submits their GKE Jobs
- Runs via APScheduler locally, Cloud Scheduler in production
- Concurrency limit configurable via SCRUBBER_MAX_CONCURRENT env var

### Workspace cold start mitigation

Scale-to-zero means the first workspace launch after inactivity waits for
node provisioning (~3–5 minutes without mitigation). Two mitigations:

1. **Placeholder pod (CronJob)**: low-priority pause container keeps one
   workspace-pool node warm 8am–8pm UTC−8:00. Evicted when a real workspace
   pod is scheduled. Defined in jackpot-iac as a Kubernetes CronJob.

2. **Pre-cached node image**: workspace-pool uses a custom node image with
   JupyterHub spawner container layers pre-cached. Reduces cold start from
   3–5 minutes to ~60–90 seconds. Defined in jackpot-iac node pool config.

### Cost controls

- **Workspace idle timeout**: 1hr (Analyst), 2hr (Bioinformatician), longer
  (Developer). Biggest single cost lever for JupyterHub.
- **Pipeline spot instances**: google.batch.spot=true in all Nextflow configs.
  ~90% cost saving. Safe because -resume recovers from preemptions.
- **Scrubber spot nodes**: scrubber-pool is preemptible. Scrubber is
  restartable — no data loss on preemption.
- **Max workspace pods per user**: JupyterHub named_server max=2.
- **GCP Budget alerts**: 50%/80%/100% of monthly budget. Defined in
  jackpot-iac. Not a hard cap — visibility only.
- **resourceLabels on all Batch jobs**: enables per-lab, per-pipeline cost
  breakdown in GCP Billing console.
- **90-day lifecycle rule on jackpot-work bucket**: deletes stale work dirs.

### IaC components (jackpot-iac)

All autoscaling configuration lives in jackpot-iac Terraform:
- Three node pool definitions with cluster autoscaler config
- HPA manifest for API and frontend deployments
- Workspace placeholder pod CronJob (8am–8pm UTC−8:00)
- Scrubber GKE Job template
- GCP Budget alert policies
- jackpot-work bucket with lifecycle rule

### New env vars

| Variable | Default | Description |
|---|---|---|
| `SCRUBBER_MAX_CONCURRENT` | `10` | Max simultaneous scrubber jobs |
| `SCRUBBER_QUEUE_INTERVAL_SECONDS` | `60` | How often queue job fires |

---


---

## Disaster Recovery and Backup Architecture

This section documents the backup strategy for every stateful component.
Understanding this is important when writing migrations, storage operations,
or anything that touches the database or GCS buckets.

### Cloud SQL (operational database) — most critical

Three layers of protection, all defined in jackpot-iac/terraform/cloudsql.tf:

**Automated daily backups** — full backup once per day during 2–4am UTC−8:00
maintenance window. Stored in GCS. 30-day retention. Costs a few dollars
per month at JACKPOT's scale.

**Point-in-time recovery (PITR)** — continuous transaction log shipping
to GCS. Enables recovery to any second within the last 7 days. This is
the most operationally useful feature. If a bad migration runs at 2pm,
restore to 1:59pm. Always enabled. Flag: --enable-point-in-time-recovery.

**Weekly SQL dump export** — Cloud Scheduler triggers a full SQL export
to gs://jackpot-backups/ every Sunday night. Independent recovery path
if Cloud SQL's built-in backup mechanism fails. jackpot-backups bucket
has Object Lock (WORM) — exports cannot be deleted or modified before
their 90-day retention expires. Protects against accidental deletion and
satisfies public health audit requirements.

**Cross-region replica** — deferred from prototype. Add when platform has
real production users. Enables promotion to primary if us-central1 has
an outage.

### GCS buckets — per-bucket policy

| Bucket | Versioning | Region | Object Lock | Notes |
|---|---|---|---|---|
| `jackpot-sequences` | Enabled | Standard | No | Irreplaceable raw FASTQs. Versioning allows recovery from accidental deletion. |
| `jackpot-references` | Enabled | Standard | No | Reference genomes. Write-once in practice. |
| `jackpot-results` | No | Standard | No | Pipeline outputs. Regenerable by re-running pipelines. |
| `jackpot-staging` | No | Standard | No | Temporary — files move to sequences after scrubbing. |
| `jackpot-work` | No | Standard | No | Nextflow work dirs. 90-day lifecycle rule. Versioning would fight lifecycle rule. |
| `jackpot-backups` | No | Different region | Yes (WORM) | Weekly SQL exports. Object Lock prevents tampering. 90-day lifecycle. |

**Never enable versioning on jackpot-work.** The combination of Nextflow
work directories (many large files) and versioning would accumulate
enormous storage costs and conflict with the 90-day lifecycle rule.

### GKE workspace PVCs (JupyterHub user data)

Each researcher's persistent volume claim contains notebooks, local data,
and conda environments. Protected via GCP Compute Engine scheduled
snapshots:

- Daily snapshot of each active workspace PVC
- 14-day snapshot retention
- Defined in jackpot-iac/terraform/snapshots.tf
- Idle PVCs (culled pods): snapshot on demand before deletion

If a researcher accidentally deletes a notebook: restore from the previous
day's PVC snapshot. Expected recovery time: 15 minutes.

### GKE cluster state

Not backed up separately — the git repository IS the backup. All cluster
state (Deployments, ConfigMaps, Services, HPA configs, CronJobs) is
defined in jackpot-iac Terraform and Kubernetes manifests. If the cluster
is destroyed, `terraform apply` + `kubectl apply` rebuild it from scratch.
Never configure cluster resources manually in the GCP console — always
use IaC so the git history is the authoritative record.

### Alembic migration history

Backed up by git. If the database is restored from a backup, run
`uv run alembic upgrade head` to bring the schema current. Never skip
this step after a database restore.

### Disaster recovery runbook (jackpot-iac/docs/disaster-recovery.md)

Five documented scenarios:

**Scenario 1 — Accidental row deletion (most common)**
Recovery: PITR or restore specific rows from daily backup.
GCS files: recover from object versioning on jackpot-sequences.
Expected RTO: 30 minutes.

**Scenario 2 — Bad Alembic migration corrupts data**
Recovery: PITR to the timestamp immediately before the migration ran.
After restore: fix the migration, test in dev, re-apply.
Expected RTO: 1–2 hours.

**Scenario 3 — Cloud SQL instance failure**
Recovery: restore from automated daily backup to new Cloud SQL instance.
Update DB_URL in GKE secrets. Redeploy API pods.
Expected RTO: 2–4 hours.

**Scenario 4 — Regional GCP outage (us-central1 unavailable)**
Recovery: promote Cloud SQL replica to primary (when replica is enabled).
Update DNS. Redeploy GKE cluster from jackpot-iac in backup region.
Expected RTO: 4–8 hours. Not fully automated in prototype.

**Scenario 5 — GCS bucket data loss**
Recovery: restore from object versioning (jackpot-sequences, jackpot-references)
or from weekly SQL export in jackpot-backups.
Expected RTO: varies by data volume.

### New IaC components (jackpot-iac/terraform/)

| File | What it defines |
|---|---|
| `cloudsql.tf` | Daily backups, PITR, 30-day retention, weekly export scheduler |
| `gcs.tf` | Versioning on sequences/references, Object Lock on backups, lifecycle rules |
| `snapshots.tf` | GKE PVC daily snapshot schedule, 14-day retention |
| `budgets.tf` | Already planned — budget alerts at 50%/80%/100% |

---
