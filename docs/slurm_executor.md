> **Status:** Reference — Slurm executor operator guide.

# Slurm executor — operator guide

JACKPOT runs pipelines on a Slurm cluster via the same launch surface
that drives a laptop or GCP Batch — the operator picks at deployment
time which executor an `execution_profile` targets, and the launch
endpoint renders a per-run `nextflow.config` for that target. This
document covers the operator-facing surface of the Slurm path: what
to put in a profile, how the API host and the cluster need to talk to
each other, how to pre-stage Apptainer images for an air-gapped
cluster, the weblog vs. log-poller redundancy story, and the cluster-
policy gotchas that bite scenario-C deployments hardest.

This document does NOT cover Scenario A in its laptop-case configuration (laptop, no cluster) or any
cloud-burst-to-GCP-Batch story (deferred — see Phase 25 in
`todo.md`). For the per-PR detail of the campaign that built this
surface, see PRs #35 (H-1, template), #36 (H-2, Apptainer
manifests), #37 (H-3, account override), #38 (H-4, log poller), #40
(H-5, `jackpot doctor`), and #41 (H-6, reachability gate).

## When to use the Slurm executor

The Slurm executor fits two install scenarios:

- **Scenario B (HPC)** — a single lab with its own Slurm queue (a head
  node + a few compute nodes). The API server runs on the same
  network and can usually reach compute nodes over HTTP; the lab's
  IT controls both sides.
- **Scenario B (HPC) at university RC** — a multi-lab agency or university research-
  computing deployment where the cluster is shared infrastructure.
  Compute nodes typically have no outbound HTTP; the API server
  reaches the cluster via a head-node SSH tunnel or a shared
  filesystem; account / partition / QOS values come from
  institutional policy.

The two scenarios share the executor template but differ in the
network and identity story. Scenario B (HPC) with a lab-internal cluster sets `weblog_reachable=true`
implicitly by virtue of the API host's network seeing the compute
nodes; the university RC variant runs primarily on the log poller (H-4) because the
weblog cannot deliver from inside the cluster.

## Profile setup

A Slurm profile is one row in `execution_profiles`. The required
fields are documented in Critical Rule 59 (executor selection). The
Slurm-specific knobs live in the `config_overrides` JSONB blob and
are documented in the template file at
`backend/backend/pipeline_config/profile_templates/slurm.config.j2`.

### Knobs the template reads

- `queue` — Slurm partition (`-p` flag). Default `'normal'`.
- `account` — `--account=<value>` flag emitted via `clusterOptions`.
  Optional. The lab's default ledger; per-launch overrides charge a
  specific grant (see "Per-launch account override" below).
- `qos` — `--qos=<value>` flag emitted via `clusterOptions`. Optional.
- `cluster_options` — free-form `sbatch` flags appended verbatim to
  `clusterOptions`. Use for institution-specific knobs the template
  doesn't model (`--gres=gpu:1`, `--exclusive`, etc.).
- `time` — per-process wall time default. Default `'1h'`.
- `memory` — per-process memory default. Optional. Format
  `'8 GB'` (Nextflow's MemoryUnit syntax).
- `cpus` — per-process CPU count default. Optional. Integer.
- `queue_size` — `executor.queueSize`. Caps the number of concurrent
  `sbatch` submissions Nextflow will hold open. Optional; defaults to
  Nextflow's built-in cap.
- `apptainer_cache_dir` — directory where Nextflow looks for and
  caches `.sif` images. Defaults to `<work_dir>/apptainer-cache` if
  unset; override when the cluster has a shared cache mount distinct
  from the run's per-launch work_dir.

### Required cross-executor fields

These come straight off the `execution_profiles` row, not the
`config_overrides` blob:

- `executor_type` — must be `'SLURM'`.
- `container_engine` — `'APPTAINER'` is the cluster default. Set
  `'DOCKER'` only on lab-Slurm clusters that allow it (uncommon in
  Scenario B HPC at university RC).
- `work_dir` — the per-run scratch root. **Must be a path visible
  identically to the API server and every compute node.** This is
  the H-5 invariant; `jackpot doctor slurm --check-cluster` is the
  test (see "Validating a profile" below).

### Example profile (Scenario B HPC, lab-internal cluster)

A profile for a lab with a small in-house Slurm queue:

```sql
INSERT INTO execution_profiles (
    name, executor_type, container_engine, work_dir,
    config_overrides, is_default, created_by_id, active
) VALUES (
    'lab-slurm',
    'SLURM',
    'APPTAINER',
    '/srv/jackpot/work',
    '{
        "queue": "compute",
        "time": "8h",
        "memory": "16 GB",
        "cpus": 4,
        "queue_size": 25
    }'::jsonb,
    TRUE,
    (SELECT id FROM users WHERE email = 'admin@your-org' LIMIT 1),
    TRUE
);
```

When `jackpot profiles add/edit` HTTP endpoints ship under P0g G-5,
the same fields will be settable through the REST API; today
profiles are managed via direct DB seed.

## Validating a profile

`jackpot doctor slurm` runs the H-5 validation predicate against an
operator-supplied set of profile fields. Two modes:

- **API host only** — `jackpot doctor slurm --work-dir /srv/jackpot/work`
  runs the local-filesystem checks: path exists, is a directory,
  is writable by the API user. Cloud URIs (`gs://`, `s3://`)
  short-circuit to info-only because the API host has no
  jurisdiction over remote object stores.
- **Cluster-side reachability** — `jackpot doctor slurm --work-dir
  /srv/jackpot/work --account lab-2026 --partition compute
  --check-cluster` additionally runs `sinfo` (cluster up?) and
  `srun --time=1 [...] stat -c '%n' <work_dir>` (work_dir visible
  from a compute node?) using the operator-supplied account /
  partition.

Exit codes:

- `0` — no findings, or info-only (cloud URI short-circuit)
- `1` — warnings only (the profile is usable but the operator
  should see the warnings)
- `2` — blocking errors (don't ship the profile until fixed)

Run `jackpot doctor slurm --help` for the full flag set and current
cluster-reachability timeout (default 10s).

## Network requirements

### API host → cluster head node

The API host needs to reach the cluster head node for two things:

1. The H-6 pre-launch reachability check (`sinfo -h`) — a
   10-second-timeout subprocess fired only when the resolved
   profile's executor is `SLURM`. Failure surfaces as **400
   `SLURM_UNREACHABLE`** with a pointer to `jackpot doctor`.
2. The H-5 cluster-side validation (`srun --time=1 stat
   <work_dir>`) — same path, only fires when an operator runs
   `jackpot doctor slurm --check-cluster`.

Both use the Slurm client tools (`sinfo`, `srun`); they must be on
the API host's `PATH`. There is no `slurm-rest` daemon dependency.

### Compute nodes → API host (the weblog story)

Nextflow's standard pattern is a `weblog` directive that POSTs trace
events from the compute node to a callback URL during execution.
JACKPOT injects this directive into every rendered `nextflow.config`,
pointing at `/api/v1/pipelines/events`. Whether the POSTs land
depends on the cluster's egress policy:

- **Scenario B HPC, lab-internal cluster** — compute nodes typically
  reach the API host's port 8000 over the lab network; the weblog
  works as designed.
- **Scenario B HPC, university research-computing** — compute nodes
  usually have no outbound HTTP. Weblog POSTs silently fail. The
  log poller is the redundancy mechanism.

### The log poller (H-4)

`backend.log_poller.poll_cluster_run_logs` is an APScheduler job
that fires every `settings.log_poller_interval_seconds` (default 30)
and tails `<work_dir>/runs/<run_id>/.nextflow.log` for every active
run. It synthesises workflow-state transitions (started, completed,
failed) from Nextflow's logger-prefixed lines and dispatches them
through the same `_handle_workflow_complete` codepath the weblog
receiver uses. Per-task accounting (`process.submitted`,
`process.completed`, etc.) remains a weblog-only concern; clusters
that need full task-level visibility have to relax outbound HTTP.

The two paths can coexist for redundancy. The receiver's
idempotency contract (Critical Rule 60) keeps state consistent:
`pipeline_runs.status` writes are idempotent, `pipeline_tasks`
upserts on `(run_id, task_id)`, and `pipeline_events` accepts
duplicate inserts. The poller's `poller_log_offset` advances
monotonically per run so a 50-MB log doesn't get rescanned every
30 seconds.

## Apptainer pre-staging (air-gapped clusters)

Most university clusters block egress to public container
registries. Each pipeline pulls many BioContainer images at run
time; if those pulls fail, the pipeline stalls on the first process
that needs an image.

JACKPOT ships an `apptainer_images.txt` manifest per pipeline
declaring the OCI image references the pipeline pulls when run
under `apptainer.enabled = true`. Operators pre-stage these into
the cluster's Apptainer cache before launching:

1. Read the manifest:
   `python -c "from pipelines.apptainer_manifest import load_manifest; print(load_manifest('viralrecon').images)"`
2. For nf-core pipelines, run `nf-core download <name>
   --container singularity --outdir <cache>` against an
   internet-connected host; copy the resulting `.sif` set into
   the cluster's Apptainer cache.
3. For non-nf-core pipelines (Cecret, Grandeur, mycosnp,
   bactopia, walkercreek, tb-profiler), pull each container
   declared in the upstream config to a `.sif` and copy into the
   cache.
4. Pull the JACKPOT register-process Python container
   (`docker.io/library/python:3.12-slim-bookworm`) — JACKPOT uses
   this for the per-run `REGISTER_RESULTS` process on every wrapper.
5. Set `config_overrides.apptainer_cache_dir` on the profile to
   point at the cache, so the rendered `apptainer { cacheDir = ... }`
   block resolves to the staged location at every launch.

`jackpot images audit <pipeline>` and `jackpot images export
<pipeline>` will automate steps 2-4 in a follow-up campaign — see
`docs/pipeline_apptainer_audit.md` for the current state.

## Per-launch account override (H-3)

`POST /api/v1/pipelines/launch` accepts an optional
`launch_account` field. When the resolved profile's executor is
`SLURM`, the value replaces `config_overrides.account` for that one
run only — the profile row is unchanged.

```json
POST /api/v1/pipelines/launch
{
  "pipeline_id": 42,
  "sample_ids": ["AZ-2026-001"],
  "project_id": 7,
  "profile_id": "abc...",
  "launch_account": "grant-NIH-R01-12345"
}
```

The override emits a separate `SLURM_LAUNCH_ACCOUNT_OVERRIDE` audit
row capturing actor + before (profile default) + after (override
value), so a security review can grep for overrides without joining
`audit_log` against `pipeline_runs.metadata`.

When P0c multi-tenancy middleware ships, the override will be
validated against the user's lab memberships before this PR ships
in production. Today the override is accepted verbatim with a
`# P0c stub` comment at the validation hook point. The audit row
is the current security boundary; a P0c-aware retroactive review
can flag overrides that would have been rejected.

`launch_account` is rejected with **400
`LAUNCH_ACCOUNT_NOT_APPLICABLE`** when the resolved profile is not
SLURM (or when the legacy GCP-Batch fallback path is taken because
no profile resolved). Single rejection signal so an operator who
passes a value that has no effect learns about it.

## Common cluster-policy gotchas

### NFS mount paths differ between API host and compute nodes

`work_dir` must resolve to the same physical bytes on the API host
and on every compute node. The H-5 cluster-side check (`srun stat
<work_dir>`) is the canary: if the compute node's `stat` succeeds
but reports a different path, you have an NFS automounter mismatch.

The fix is one of:

- Align mount paths so the same absolute path works on both sides
  (talk to your IT).
- Use Nextflow's `process.scratch` directive to copy inputs into a
  per-process scratch on the compute node before processing. Set
  this in `config_overrides.cluster_options` if the cluster has a
  scratch convention; otherwise let the cluster auto-mount default
  apply.
- Use `process.stageInMode = 'symlink'` (Nextflow default) for
  inputs that don't need byte-identical access, or
  `'copy'` for ones that do.

### Apptainer cache permissions

Apptainer's autoMounts behavior reads the image cache the user
running `srun` has access to. If the API user's shell account
isn't the same user who pulled the cache, Apptainer will silently
re-pull (and fail, on an air-gapped cluster). Use a shared cache
location and verify `srun -p <partition> apptainer ls
<cache>/<image>.sif` succeeds before launching pipelines.

### `--exclusive` masks queue_size

If the cluster policy includes `--exclusive` in your
`config_overrides.cluster_options`, every `sbatch` reserves an
entire node. `queue_size = 25` then means 25 concurrent nodes, not
25 concurrent processes. If your queue holds 8 nodes total, set
`queue_size` to 8 to avoid Nextflow stalling on
SubmissionFailures.

### `srun --time=1` budget

The H-5 `--check-cluster` mode submits a `--time=1` job to verify
work_dir reachability. Some clusters reject `--time=1` (single-
minute jobs) outright; if you get a quick rejection, raise to
`--time=00:02:00` and re-run. The doctor's `--timeout` flag is the
host-side budget for waiting on the `srun` to return; defaults to
10 seconds.

### `sinfo` returns rows but launch fails

The H-6 reachability check is a fast sanity probe — `sinfo` returns
0 within 10 seconds. It does NOT verify that the operator-supplied
account / partition / QOS combination is valid for the user. A
profile that passes `sinfo` can still queue runs that fail at
`sbatch` time with `Invalid account` or `Access/permission denied`
errors. Use `jackpot doctor slurm --check-cluster --account
<value> --partition <value>` to exercise the actual flag
combination before shipping the profile.

## Reset / recovery

- **A run is stuck PENDING for hours**: check the H-6 cache.
  Reachability state is cached for 60 seconds (default); if you
  restored the cluster mid-cache, the next launch will re-probe
  automatically. To force-clear, restart the API process or call
  `backend.pipeline_config.cluster_reachability.reset_cache()`
  via the local CLI.
- **A run is stuck RUNNING but the cluster shows it complete**:
  the log poller may be looking at a stale offset because the log
  file was rotated or truncated. The poller resets to offset 0 on
  detected shrink (logs a warning); if it didn't, manually update
  `pipeline_runs.poller_log_offset` to 0 for the affected `run_id`.
- **`jackpot doctor` reports `SINFO_NOT_INSTALLED`**: the API host
  doesn't have Slurm client tools on `PATH`. Either install them
  (`yum install slurm-client` on a CentOS API box) or run `jackpot
  doctor` directly on the cluster head node instead.

## Cross-references

- `backend/backend/pipeline_config/profile_templates/slurm.config.j2`
  — template; per-knob docs in the file's docstring
- `backend/backend/pipeline_config/profile_validation.py` — H-5
  validation predicate
- `backend/backend/pipeline_config/cluster_reachability.py` — H-6
  reachability probe + 60s cache
- `backend/backend/log_poller.py` — H-4 fallback poller
- `cli/jackpot/cli/doctor.py` — operator surface for H-5
- `pipelines/pipelines/<name>/apptainer_images.txt` — H-2 pre-
  staging manifests
- `docs/pipeline_apptainer_audit.md` — per-pipeline audit notes
- `docs/CLAUDE.md` — Critical Rules 25 (per-run work_dir), 26
  (config generated fresh per-run), 27 (resourceLabels), 59
  (executor selection per run), 60 (cluster-bound run reachability)
- `todo.md` lines 1697–1850 — full P0h spec
