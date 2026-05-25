# JACKPOT — Strategic Vision Summary

**Document type:** Standalone strategic synthesis
**Version:** 1.0
**Last updated:** 2026-05-09
**Author:** Glen Otero (gotero@linuxprophet.com), assembled with Claude
**Audience:** Glen + future contributors first; written so a partner lab, grant reviewer, or RC team could follow along without prior context
**Companion document:** `jackpot_status_and_roadmap_may_2026.md` (concrete accomplishments, current blockers, sequencing of work in flight)
**Source synthesis:** `JACKPOT_Architecture_Synthesis___May_2026.md`, `jackpot_immune_platform_plan.md`, `jackpot_cdc_dmi_stlt_overview.md`, `jackpot_pathoplexus_loculus_overview.md`, `Remote_Health_Data_Mesh_Solutions.md`, `Core_Technical_Pillars.md`

---

## Table of contents

1. [Executive summary — the platform thesis](#1-executive-summary--the-platform-thesis)
2. [The single biggest reframing: on-prem-first, cloud as upgrade](#2-the-single-biggest-reframing-on-prem-first-cloud-as-upgrade)
3. [Eight deployment scenarios](#3-eight-deployment-scenarios)
4. [Three Python packages, two container runtimes](#4-three-python-packages-two-container-runtimes)
5. [File references and execution profiles](#5-file-references-and-execution-profiles)
6. [`jackpot init` as the centerpiece](#6-jackpot-init-as-the-centerpiece)
7. [CDC DMI / North Star / STLT alignment](#7-cdc-dmi--north-star--stlt-alignment)
8. [Tribal sovereignty as category-of-one differentiator](#8-tribal-sovereignty-as-category-of-one-differentiator)
9. [The Immune Platform vision (Phase 26+)](#9-the-immune-platform-vision-phase-26)
10. [JACKPOT Academy and games as platform infrastructure](#10-jackpot-academy-and-games-as-platform-infrastructure)
11. [Differentiators vs. peer platforms](#11-differentiators-vs-peer-platforms)
12. [Strategic positioning — who adopts JACKPOT and why](#12-strategic-positioning--who-adopts-jackpot-and-why)
13. [Publication and partnership pipeline](#13-publication-and-partnership-pipeline)
14. [What this means for the next 90 days](#14-what-this-means-for-the-next-90-days)

---

## 1. Executive summary — the platform thesis

JACKPOT is an open-source, AGPL-3.0, operator-agnostic pathogen genomics platform under `Midnight-Oil-Innovation/jackpot`. The platform is built around three balanced theses:

**Thesis 1 — Operator agnosticism.** JACKPOT runs anywhere a pathogen-genomics lab works, from a researcher's laptop to a federated multi-agency cloud deployment. The same codebase, the same schema, the same routers; different deployment scenarios bootstrap different operator configurations via `jackpot init`. This is not "cloud platform that also runs locally" — it is "laptop and on-prem-server platform that also scales to cloud and federation."

**Thesis 2 — The dual-AIS architecture (Phase 26+).** The same family of bio-inspired algorithms that detect anomalous pathogen genomes can also detect anomalous platform behavior. JACKPOT is designed to run both simultaneously, sharing a single algorithmic substrate. This closes the loop on Stephanie Forrest's 1994 negative-selection algorithm — invented for cybersecurity, adapted to biology, brought back to defend a biology platform.

**Thesis 3 — Workforce-as-platform-infrastructure (Phase 26+).** Public-health workforce capacity is the rate-limiting factor in pandemic preparedness, not tooling. JACKPOT Academy and the Outbreak / WILDFIRE games are not deliverables on top of a platform — they are platform infrastructure that produces the operators, contributors, and adversarial training data that the rest of the system needs.

Two PII gates at ingest, eight deployment scenarios, three distribution packages, two container runtimes, federated query architecture compatible with GA4GH standards, and CARE-Principle-aware Tribal-deployment scenario. Year-round peacetime utility for AMR, TB, flu, and seasonal diagnostic workloads. AGPL-3.0 with operator-agnostic codebase and clear governance.

No platform in the comparative landscape — Pathoplexus / Loculus, GenSpectrum / LAPIS, Pathogenwatch, EnteroBase, NCBI Pathogen Detection, BV-BRC, Solu, RT-MetA, GISAID, IDseq, IRIDA-ARIES, amr.watch, SeqScreen-Nano, HPD-Kit — combines this set of capabilities. Most do none of them.

---

## 2. The single biggest reframing: on-prem-first, cloud as upgrade

The most important shift in May 2026: **JACKPOT is not a cloud platform that also runs locally. It's a laptop and on-prem-server platform that also scales to cloud and federation. Cloud is the upgrade path, not the assumed path.**

This isn't just marketing. It cascades into nearly every architectural decision:

- The default `jackpot init` flow targets a laptop or single Linux server
- The default storage assumption is "the operator already has storage"
- The default executor is local Nextflow with a clear path to Slurm
- The default auth is simple (mock user, then optional OAuth/LDAP)
- Cloud-native features (GKE, Cloud DLP, Workload Identity Federation) become opt-in scenario configurations, not the baseline

This positioning is what makes JACKPOT credible to two audiences far larger than "state public health agencies with cloud programs":

1. **The WHO IPSN equity story** — most countries doing pathogen genomics are not running on Google Kubernetes. They're running on a laptop, a single Linux server, or an institutional cluster. JACKPOT speaks their language.
2. **University research-computing teams** — the people who actually deploy bioinformatics platforms at scale outside major federal agencies. Their environment is Slurm, Apptainer, shared filesystems, and LDAP.

The README's lead now reads: *"JACKPOT runs on your laptop. It also scales to your university's HPC cluster. Same codebase. Cloud examples follow."*

---

## 3. Eight deployment scenarios

The scenario list grew from six to eight in May 2026, with on-prem and university research-computing becoming first-class:

| Scenario | Description | Compute target | Operator | Trust boundary | Priority |
|---|---|---|---|---|---|
| **A** | Laptop | Local Docker | Single user | Self | Bulletproof |
| **B** | Single on-prem server | Local Docker / local Slurm / **(stretch) cloud burst** | Lab IT or PI | One lab | Bulletproof |
| **C** | University RC-hosted | Slurm/PBS HPC cluster + Apptainer | RC/HPC team | Per-lab within institution | Bulletproof |
| **D** | Single-org cloud | GKE/EKS/AKS | Org IT | One org | Production |
| **E** | Multi-lab agency | Agency cloud or datacenter | Agency platform team | Per-lab + surveillance mandate | Production |
| **F** | Hosted SaaS | Operator's cloud | External operator | Per-tenant | Production |
| **G** | Federation member | Variable | Federation node | Federation policies | Future |
| **H** | CI test | Local containers | n/a | n/a | Bulletproof |

A / B / C / H are bulletproof from day one — they're what every developer, every interested lab, and every academic adopter will hit first. D / E / F are production-hardened paths that share infrastructure. G is future state.

A separate **Scenario T** (Tribal, sovereignty-aware) is contemplated as a variant of A or E with CARE-Principle defaults baked in (no auto-publish, 24-hour vacuum cadence, Tribally-controlled aggregation). See Section 8.

---

## 4. Three Python packages, two container runtimes

### 4.1 Three distribution artifacts

The monorepo at `/Users/glen/Projects/jackpot/` produces three distinct distribution artifacts, all sharing the same version number tied to releases:

| Path | Package | Distribution | Audience |
|---|---|---|---|
| `cli/` | **`jackpot`** | PyPI (`pipx install jackpot`) + Bioconda (`conda install -c bioconda jackpot`) | Anyone deploying or running JACKPOT |
| `cli/jackpot/sdk/` | **`jackpot-sdk`** | PyPI (`pip install jackpot-sdk`) | Devs writing notebooks, scripts, BYOPs, internal Streamlit pages |
| `backend/` | Docker image on GHCR | `ghcr.io/midnight-oil-innovation/jackpot-backend:vX.Y.Z` | Pulled at runtime by `jackpot up` |
| `frontend/` | Docker image on GHCR | `ghcr.io/midnight-oil-innovation/jackpot-frontend:vX.Y.Z` | Same |
| `schema/` | Bundled into both `jackpot` and `jackpot-sdk` | n/a (yet) | Internal |
| `pipelines/` | Cloned at runtime from monorepo `pipelines/` | Pulled by Nextflow | Pipeline executor |
| `deploy/` | Bundled inside `jackpot` CLI as package data | Embedded | Operators |

A few points worth being explicit about:

- **`jackpot` is the installer/CLI**, not the backend. Small, pure-Python, ships templates and CLI logic. Pulls Docker/Apptainer images, generates configs, orchestrates services. Does **not** contain FastAPI or SQLAlchemy.
- **`jackpot-sdk` is a separate top-level package.** `jackpot` has an optional dependency on it (`pip install jackpot[sdk]`). Avoids dragging the SDK into every `jackpot init` install for operators who only run the platform.
- **The backend never gets pip-installed by users.** Exclusively a container image. Inside the monorepo it has a `pyproject.toml` for development; doesn't get released to PyPI.
- **`jackpot-schema` is deferred** until there's demonstrated external need. Schema artifacts (Pydantic models, LinkML output, JSON Schemas, TSV templates) ship inside the SDK for now.

The version-locking story: `jackpot v1.4.2` knows it expects `jackpot-backend:1.4.2`, `jackpot-frontend:1.4.2`, and `jackpot-sdk==1.4.2`. The CLI refuses to use mismatched components and prints a clear upgrade path.

### 4.2 Docker AND Apptainer as first-class runtimes

The `jackpot` CLI supports two container runtimes, selected at `jackpot init` time:

| Runtime | Default for | Service orchestration |
|---|---|---|
| **Docker** | macOS laptops (A), single lab Linux servers (B), most cloud (D/E/F) | `docker compose` |
| **Apptainer** | Linux servers in HPC-adjacent environments (B with Apptainer policy), university RC (C), air-gapped sites | systemd unit files invoking `apptainer instance` |

Implementation principles:

1. **Same OCI images, both runtimes.** Container images on GHCR work natively with Docker (`docker pull`) and Apptainer (`apptainer pull docker://ghcr.io/...`). No separate image builds.
2. **Systemd as the common service manager on Linux.** Whether services run under Docker or Apptainer on a Linux server, the wrapper is a systemd unit. Uniform start/stop/restart/status; aligns with how Linux sysadmins actually operate.
3. **Pre-staging support for air-gapped deployments.** `jackpot images export` and `jackpot images import` produce a portable bundle (tar of OCI images for Docker, tar of SIF files for Apptainer) that can be moved into an air-gapped environment.
4. **Allow host-installed Postgres/MinIO as alternatives.** For Scenario C especially, the RC team often already runs Postgres for other things. `jackpot init --use-existing-postgres postgres://...` skips the containerized Postgres and just records a connection string.
5. **`jackpot doctor` is runtime-aware.** Verifies the configured runtime is installed, has correct permissions, can reach configured Slurm/cluster endpoints, can pull from GHCR (or has pre-staged images).

The Apptainer-specific gotchas (PGDATA permissions running as invoking user, no Docker network so everything binds localhost, SIF storage on shared filesystem) get bundled into systemd unit templates rather than left as operator homework.

---

## 5. File references and execution profiles

Two schema-level reframings that change how the platform thinks about its job.

### 5.1 File references with storage state

The mental-model shift: **JACKPOT is a metadata database that knows how to find and run pipelines on data, not a storage system that holds your data.** Storage is something the operator already has.

The `FileStorageState` enum:

| State | Meaning | Lifecycle owned by |
|---|---|---|
| `EXTERNAL` | File at URI not under JACKPOT control | The operator/user |
| `MANAGED` | Under JACKPOT storage control | JACKPOT |
| `MIRRORED` | Managed copy backed by external original | JACKPOT (with origin tracking) |
| `STAGED` | Temporary copy for a specific pipeline run | JACKPOT (auto-cleanup) |
| `BROKEN` | External file no longer accessible | n/a (terminal) |

Behavioral defaults:

- **Ingest defaults to `EXTERNAL`.** Pointing JACKPOT at a file path or URI registers it; no copy occurs.
- **Pipeline outputs default to `MANAGED`.** When a pipeline produces results, JACKPOT owns those.
- **Pipeline inputs stay in their existing state.** Running a pipeline doesn't take ownership of the input data.
- **Cheap fingerprint at ingest, full SHA-256 lazily.** Size + first-64KB hash + last-64KB hash for dedup-during-ingest; full hash queued as a background job.
- **Periodic verification of `EXTERNAL` files.** A background job re-stats them and updates `last_verified_at`, marking `BROKEN` if missing.
- **Pre-pipeline-launch verification.** Before any pipeline run, verify all input files are accessible. Fail fast, not mid-run.
- **Explicit promotion.** `jackpot files promote --to managed` for users who want JACKPOT to take ownership.

The UI surfaces storage state plainly. Users always know whether JACKPOT owns this file or just references it.

For scenario-specific behavior:

- **Scenario A (laptop):** Files in user project dirs, registered as `EXTERNAL`. MinIO is optional or skipped entirely; `~/.jackpot/data/` for managed storage.
- **Scenario B (single lab):** Files on lab NAS or shared drive, `EXTERNAL`. Pipelines on local Slurm see same paths, zero copies.
- **Scenario C (university):** Files on Lustre/GPFS, `EXTERNAL`. Pipelines on cluster see same paths, zero copies. JACKPOT does not run its own object storage by default — uses institutional storage.
- **Scenario D/E (cloud):** Files in GCS/S3 buckets, `EXTERNAL` referencing the operator's bucket. Pipelines on Batch read in place.
- **Cloud burst from B:** Input file `STAGED` to GCS for the duration of the run, cleaned up after. One copy, lifecycle-managed.
- **SRA-imported:** `sra://SRR12345`. Zero permanent copies; `fasterq-dump` runs on compute node.

### 5.2 Execution profiles as a per-pipeline-run choice

Executor selection is not a deployment-time decision; it's a per-launch choice driven by configured profiles. This is the architectural unlock for Scenario B + Slurm and Scenario C.

The execution-profile model:

```text
[deployment-time]
operator configures one or more execution profiles in jackpot config
  - "local"        : Nextflow on the API server, Docker
  - "slurm-mylab"  : Submit to lab Slurm queue, Apptainer
  - "slurm-univ"   : Submit to university cluster, Apptainer, lab account
  - "gcp-batch"    : Burst to GCP Batch (stretch)

[launch-time]
user picks a profile when launching a pipeline run
or accepts the per-pipeline default
```

This translates directly to Nextflow's `-profile` flag plus JACKPOT-aware metadata (Slurm account to charge, scratch directory, container engine, work directory). The pipeline definitions in the zoo don't change — they're already nf-core-standards compatible. What changes is the JACKPOT-side machinery for storing profiles, surfacing them at launch time, and generating the right `nextflow.config` snippet.

A new `JACKPOT_WORK_DIR` abstraction sits as a first-class peer to MinIO/GCS, pointing at a shared filesystem path:

- Scenario A laptop: `~/.jackpot/work/`
- Scenario B with Slurm: `/srv/jackpot/work/`
- Scenario C: `/scratch/$USER/jackpot-work/` or a project directory

Cost surfacing is mandatory for cloud-burst profiles. Pre-launch estimate: *"this run will use approximately $X in compute."* Surprise GCP bills kill platform adoption.

---

## 6. `jackpot init` as the centerpiece

`jackpot init` is what turns the operator-agnostic codebase into a per-operator deployment. The interactive flow:

```bash
$ pipx install jackpot
$ jackpot init

Welcome to JACKPOT! Let's set up your deployment.

[Scenario]
  1) Laptop (single user, dev or scientific use)
  2) Single on-prem server (one lab)
  3) University research-computing hosted (multi-lab)
  4) Single-org cloud (GCP/AWS/Azure)
  5) Multi-lab agency
  6) Hosted SaaS (operator-as-service)
  Pick: 2

[Container runtime]
  1) Docker (default for laptops and most servers)
  2) Apptainer (HPC-adjacent, no Docker policy)
  Pick: 1

[Auth]
  1) Mock user (single user, dev only)
  2) Username/password (small lab, simple)
  3) Google OAuth (Google Workspace shop)
  4) LDAP/SAML (institutional)
  Pick: 2

[Storage backend]
  1) Local filesystem (~/.jackpot/data/)
  2) MinIO container
  3) Existing S3-compatible (provide endpoint)
  4) GCS bucket
  Pick: 2

[Compute executor]
  1) Local Nextflow on this server
  2) Local Slurm queue (this server runs Slurm)
  3) Remote Slurm cluster
  4) Multiple profiles (configure each)
  Pick: 4

[Profile 1 of N: Slurm cluster]
  Account: mylab-2026
  Partition: compute
  Container engine on cluster: apptainer
  Shared filesystem path: /shared/jackpot/work
  ...

[Optional cloud burst]
  Configure GCP Batch as a backup executor profile? (y/N): N

[Confirmation]
Configuration saved to ~/.jackpot/config.yaml
Run `jackpot up` to start JACKPOT.
Run `jackpot doctor` to verify the deployment.
```

Each scenario produces a different bundle of files under `~/.jackpot/`:

```text
~/.jackpot/
├── config.yaml                    # operator's config
├── docker-compose.yml             # if runtime=docker
├── systemd/                       # if runtime=apptainer
│   ├── jackpot-postgres.service
│   ├── jackpot-minio.service
│   ├── jackpot-backend.service
│   └── jackpot-frontend.service
├── nextflow/
│   ├── local.config
│   ├── slurm-default.config       # generated from operator answers
│   └── gcp-batch.config           # if configured
├── data/                          # if storage=local
└── work/                          # JACKPOT_WORK_DIR
```

The CLI commands:

| Command | Purpose |
|---|---|
| `jackpot init` | Interactive setup, generates config + bundle |
| `jackpot up` | Start all services using configured runtime |
| `jackpot down` | Stop all services |
| `jackpot logs [service]` | Tail logs |
| `jackpot ps` | Show service status |
| `jackpot doctor` | Health-check every component, runtime-aware |
| `jackpot upgrade` | Pull matching versions of backend/frontend, run migrations |
| `jackpot images export/import` | Pre-stage images for air-gapped install |
| `jackpot files promote` | Change storage state of a file_reference |
| `jackpot profiles list/add/edit` | Manage execution profiles |
| `jackpot backup/restore` | Database + managed-storage backups |

---

## 7. CDC DMI / North Star / STLT alignment

### 7.1 Where DMI stands

CDC's Data Modernization Initiative was launched in 2020 with a roughly $1B initial congressional allocation. The vision was sound: cloud-native, FHIR-aligned, TEFCA-compatible, "blueprint not platform" with local data control. The pandemic exposed exactly the problems DMI was designed to fix — point-to-point submissions from providers, incompatible formats, fax machines still in routine use for case reporting in 2020.

**Funding for the broader DMI was paused in October 2025** (Wave 2 Implementation Center applications halted), but the underlying technical vision is broadly endorsed by the STLT public health community. **The pause is political and budgetary, not architectural.** Whatever rebuild eventually happens will likely follow the same shape, possibly led by a different agency or coalition.

This matters for JACKPOT positioning: the technical decisions JACKPOT has already made — cloud-native option, multi-tenant-capable, schema-driven, AGPL-3.0 with clear governance, multiple install scenarios — match what STLT agencies were promised by DMI. JACKPOT's Scenarios A (laptop), C (multi-lab agency), and E (federation) directly map to the STLT-facing tiers North Star described.

### 7.2 The "Front Door" pattern

DMI's "CDC Front Door" was meant to be a single ingest endpoint that auto-routed inbound data. JACKPOT already has the genomics-narrow-scope version: a single ingest endpoint that auto-routes based on input type (signed URL, URI, FHIR, SRA, CSV). Document this as the "single-entry-point for genomic data into a public health agency" — that framing matters for grant narratives.

### 7.3 TEFCA / FHIR — Year 2+

TEFCA is the policy + agreements framework for inter-organizational health data exchange. As of 2025 there are about a dozen QHINs (Qualified Health Information Networks) operational. Public Health Agencies participate as "exchange purpose actors" and can query for data under explicitly enumerated public-health exchange purposes.

**Genomic data exchange is not a TEFCA initial use case.** The TEFCA Public Health Exchange Purpose currently focuses on case reporting and case investigation. Plausibly in scope for future iterations, but not today.

What JACKPOT actually needs from TEFCA:

- **Probably not direct TEFCA participation.** JACKPOT is genomics-layer, not case-reporting-layer.
- **But** STLT operators running JACKPOT will be receiving eCR via TEFCA. Linking a specimen referenced in an eCR to a genome sequenced and analyzed in JACKPOT requires JACKPOT to consume FHIR `Specimen` and `MolecularSequence` resources.
- **And** JACKPOT can usefully *emit* FHIR resources back into the operator's record systems — when a sequence is processed, emit a FHIR `Observation` with `MolecularSequence` reference.

The FHIR resources that matter, with explicit "NEVER" rows:

| FHIR resource | JACKPOT use |
|---|---|
| `Patient` | NEVER — JACKPOT doesn't store patient identifiers |
| `Specimen` | Inbound — link a JACKPOT sample to an upstream specimen reference from eCR/ELR |
| `Substance` | Inbound for some bacterial culture isolates |
| `Observation` (lab result) | Inbound from ELR; outbound for sequence-derived results |
| `MolecularSequence` | Both directions — the canonical FHIR shape for genomic data |
| `Organization` | Inbound — link sequencing labs and PHAs |
| `Practitioner` | NEVER — JACKPOT users are not patient-care practitioners in the FHIR sense |
| `Provenance` | Outbound — emit pipeline-result provenance |

JACKPOT doesn't process patient-level PHI by design — that's the metadata DLP gate's job. Adopting FHIR shouldn't change that posture; if anything, it reinforces it.

**Recommended timing:**

- **Now (Year 1):** Document JACKPOT's data model in FHIR-translatable terms. The LinkML schema gives us enough abstraction that this is documentation work, not engineering.
- **Year 2 if pressure mounts:** Build `backend/routers/fhir.py` that consumes inbound FHIR `Specimen` and `MolecularSequence` and emits outbound `Observation` and `Provenance` for completed pipelines.
- **Year 2+ if a TEFCA-participating operator adopts JACKPOT:** Help them build the bridge from their TEFCA-receiving infrastructure to JACKPOT.

**Don't build TEFCA/FHIR support speculatively.** The implementation cost is real and the window of relevance for STLT operators is 2–3 years out for genomics specifically.

### 7.4 What JACKPOT does NOT compete with

- **NBS** (case reporting), **eCR** (electronic case reporting), **AIMS** (lab-data routing) all operate at a layer JACKPOT does not occupy
- JACKPOT is **downstream** of them — sample-and-sequence-centric, not case-centric
- Position JACKPOT as the genomics layer that *integrates with* NBS / eCR / AIMS, not a replacement

---

## 8. Tribal sovereignty as category-of-one differentiator

This is the highest-leverage and lowest-cost strategic differentiator JACKPOT has access to.

### 8.1 The structural opportunity

CDC's North Star uses "STLT" as a four-letter acronym uniformly. In practice, the **T** (Tribal) was sometimes treated as a special case of **L** (Local) — which it definitely is not. **Tribes are sovereign nations.**

There's no evidence in the public North Star materials that **CARE Principles** (Collective benefit, Authority to control, Responsibility, Ethics) were formally adopted as a design constraint. By contrast:

- **NIH** has explicit Indigenous data governance guidance for genomic research grants
- **Tribal IRBs** routinely require CARE-aligned data handling
- **Some states** (Washington, New Mexico, Arizona, Oklahoma, etc.) have inter-governmental agreements with Tribes that go beyond what North Star contemplates

**JACKPOT formally adopting CARE Principles + designing for Tribal-deployment scenarios is a category-of-one differentiator in pathogen genomics.** None of Loculus, Pathogenwatch, EnteroBase, NCBI PD, BV-BRC, Solu, RT-MetA, or GISAID does this.

### 8.2 What it means architecturally

Most of the Tribal-sovereignty work is governance and config, not net-new engineering. **One architectural piece does require real work:** deletion-on-request that actually removes the data, not just hides it.

The schema additions (locked into Phase 24.5 design lockdown before P0b touches the schema):

- `samples.deletion_status` enum: `ACTIVE | DELETION_REQUESTED | TOMBSTONED | VACUUMED`
- `samples.deletion_requested_at`, `deletion_requested_by_user_id`, `deletion_reason`
- `samples.tombstoned_at`, `vacuumed_at`
- `audit_log.event_type` enum extension: `sample_deletion_requested`, `sample_tombstoned`, `sample_vacuumed`
- `pipeline_results` rows gain a `tombstoned` boolean
- FK from `pipeline_results.sample_id` does NOT cascade-delete on sample deletion (preserves audit trail)

The state machine: tombstone seals derivative rows, vacuum physically removes content. What gets vacuumed: file URIs in samples, GCS/MinIO objects, `pipeline_results.result_data` JSONB, cached intermediate artifacts, dataset memberships. What survives vacuum: audit log records of *what happened* (sample existed, was tombstoned at T1, vacuumed at T2 by user U), but NOT the deleted content itself.

Vacuum cadence is configurable per operator policy; **Scenario T defaults to 24 hours**, other scenarios may default to 30 days.

### 8.3 Federation tier 0 — Tribal Epidemiology Center pattern

TECs are HIPAA-recognized public health authorities serving 574 Tribes and 9.7 million AI/AN people. **A JACKPOT instance at a TEC + JACKPOT instances at member Tribes = canonical Scenario E federation, but with Tribally-controlled aggregation rules.**

This is the right shape for federated analysis where the "self/non-self" boundaries are politically meaningful, not just operationally convenient.

### 8.4 The three areas where North Star is silent and JACKPOT can lead

1. **Indigenous Data Sovereignty (CARE Principles).** Adopt formally in `governance/care-principles-and-tribal-data-sovereignty.md`. Pair with FAIR. Ship a Tribal-deployment guide.
2. **Air-gappable / sovereignty-preserving deployment.** Local-first with controlled federation; aligns with RT-MetA's territory and JACKPOT's existing Scenario A/E.
3. **Genomics-specific data flows.** North Star is mostly about case data, lab data, vital records, immunization. The genomics layer hasn't been pre-claimed by a federal-led design that would constrain JACKPOT.

The Phase 24.5 design lockdown gates P0b (Schema v5.0) — the implementation lands in P0c alongside multi-tenancy middleware.

---

## 9. The Immune Platform vision (Phase 26+)

### 9.1 Two theses

JACKPOT is already a credible operator-agnostic pathogen genomics platform. The Immune Platform vision lays out how it becomes the **most complete public health biosurveillance platform on the planet** by adopting an **artificial immune system (AIS) architecture** as its organizing principle, with **public health workforce capacity** as a co-equal first principle.

**Thesis 1 — The dual-AIS thesis (technical novelty):** The same family of bio-inspired algorithms that detect anomalous pathogen genomes can also detect anomalous platform behavior. JACKPOT runs both simultaneously, sharing a single algorithmic substrate.

**Thesis 2 — The workforce-as-platform-infrastructure thesis (workforce novelty):** Public-health workforce capacity is the rate-limiting factor in pandemic preparedness, not tooling. JACKPOT Academy and the Outbreak / WILDFIRE games are not deliverables on top of a platform — they are platform infrastructure that produces the operators, contributors, and adversarial training data that the rest of the system needs.

No platform in the comparative landscape combines either thesis with the other. Most do neither.

### 9.2 The five pillars

| Pillar | Subsystem | What it does |
|---|---|---|
| I | `jackpot-immune-bio` | Bio-anomaly detection — finds unknown pathogens, novel variants, recombinants, engineered sequences |
| II | `jackpot-immune-sec` | Platform self-defense — detects intrusions, poisoned inputs, malicious queries, insider threats |
| III | `jackpot-immune-net` | Federation as immune network — distributed memory, trust calibration, cross-cell signaling |
| IV | JACKPOT Academy | Workforce-as-platform-infrastructure — curriculum that teaches AIS by being it |
| V | Outbreak + WILDFIRE | Gaming-as-platform-infrastructure — adversarial co-training and platform stress-testing |

**Pillars IV and V are platform infrastructure, not decoration.** They appear last in the section ordering only because their value depends on the technical substrate of the first three. Game players generate adversarial training data for both bio-AIS and cyber-AIS detectors. Academy students extend the detector zoo as part of their coursework. Training and gaming are tightly coupled with the production immune system.

### 9.3 Why JACKPOT specifically

Three structural advantages JACKPOT already has:

1. **Operator-agnostic, multi-tenant, federated by design.** Eight deployment scenarios means we already think in "cells" of an immune network.
2. **Two PII gates already enforce immune-like self/non-self at ingest.** HRRT/Scrubber removes host genomic "self," Cloud DLP removes metadata "self." Conceptually thymus-style negative selection. We're already partway there.
3. **`course/` tree and game-able structure already in the monorepo plan.** Academy and Outbreak both fit naturally into the existing tree without architectural surgery.

### 9.4 The Forrest insight: AIS started as cybersecurity

Stephanie Forrest's seminal 1994 paper *Self-nonself discrimination in a computer* invented the negative selection algorithm for **computer security**. It was *later* adapted for biological problems. JACKPOT closes the loop: NSA was inspired by biology, used for cyber, and we use it again for both biology AND the cyber defense of a biology platform.

That symmetry is the technical thesis. It's also a beautiful story that grant reviewers will love.

### 9.5 The Track 1 / Track 2 architectural seam (already scaffolding)

The Immune Platform vision is not vaporware — it's scaffolding right now. The strategic decision in Session 22 (2026-05-08): build federation, privacy, and encryption Track 1 implementations now using current JACKPOT primitives, and in parallel scaffold the AIS-augmented Track 2 hook seams so future research-collaboration work plugs in via dependency injection rather than forking each module.

```text
backend/backend/
├── federation/         ← Track 1 (FED-A landed 2026-05-08)
│   ├── client.py       ← uses concrete httpx + JWT primitives
│   ├── push.py
│   ├── access.py
│   └── _ais_hooks.py   ← AISFederationHooks Protocol seam
├── privacy/            ← Track 1 (PRV-A pending)
├── crypto/             ← Track 1 (CRY-A pending)
└── immune/             ← Track 2 (Phase 26+)
    ├── algorithms/     ← shared NSA, DCA, clonal-selection substrate
    ├── bio/            ← Pillar I — anomaly detection
    ├── sec/            ← Pillar II — platform self-defense
    └── net/            ← Pillar III — federation as immune network
```

The seam between tracks is dependency injection. Every Track 1 class accepts a `hooks=` argument defaulting to a `Null<X>Hooks` no-op. Track 2 swaps in concrete implementations via the same constructor argument. **No code changes required to Track 1 modules when Track 2 lands.** Direction of import is one-way: Track 1 packages never import from `backend/backend/immune/`.

This is what makes the Immune Platform vision credible — the engineering scaffolding is already in flight ahead of the strategic phasing.

### 9.6 The Phase 26+ roadmap (post-P5)

| Phase | Goal | Effort |
|---|---|---|
| **26** | Bio-AIS MVP + Academy module 9 — first end-to-end NSA detector firing on real samples | ~6 weeks |
| **27** | Multi-modal danger fusion + DCA in practice — wastewater + clinical + genomic signal fusion | ~5 weeks |
| **28** | Memory + Clonal Selection — analyst-confirmed anomalies promote to memory cells | ~5 weeks |
| **29** | Federation as Immune Network — cross-tenant immune network with trust scoring and HE queries | ~6 weeks |
| **30** | Cyber-AIS for Platform Self-Defense — Pillar II live; same NSA, different threat surface | ~5 weeks |
| **31** | Game/Academy full integration — all five pillars operational; training/gaming feedback loop closed | ~4 weeks |

These run after the P0–P5 backbone. Items within a phase parallelize. A solo developer interleaves these with current P0d–P5 work — "parallel" here means *interleaved within phases*, not literally concurrent.

---

## 10. JACKPOT Academy and games as platform infrastructure

### 10.1 JACKPOT Academy (Pillar IV)

A free, AGPL-licensed, modular pathogen genomics curriculum that lives inside the JACKPOT monorepo at `course/`. Software Carpentry meets nf-core training meets a microbiology bootcamp, but with a real production platform as the backbone instead of toy notebooks.

**Audience tiers:**

| Tier | Audience | Time | Outcome |
|---|---|---|---|
| **Foundations** | CS people who don't know biology, biologists who don't know CS | 4–6 weeks | Comfortable with fastq, bash, Docker, Nextflow basics |
| **Practitioner** | Public health / state lab staff, grad students | 8–12 weeks | Can run end-to-end outbreak analysis on JACKPOT |
| **Operator** | Engineers deploying JACKPOT for an agency or LMIC partner | 4 weeks | Can stand up Scenarios A–E and onboard tenants |
| **Contributor** | OSS devs who want to extend JACKPOT | self-paced | Can ship a PR to backend, schema, or a pipeline |

**Module spine (16 modules, ~6–8 hrs each):**

1. Sequencing 101 — Illumina vs ONT vs PacBio, what fastq actually is, why quality scores matter
2. Linux & Python for genomics — bash one-liners, pandas, biopython
3. Pi cluster build — k3s + Slurm-on-Pi + Nextflow `local` profile
4. QC & host scrubbing — fastp, NanoPlot, **HRRT/Scrubber** (a JACKPOT differentiator)
5. Taxonomic ID — PanGIA, Kraken2, mash screen
6. Assembly — SPAdes for short reads, Flye for long, hybrid with Unicycler
7. Variant calling — Snippy, BCFtools, DeepVariant
8. AMR & virulence — CARD, AMRFinderPlus, abricate, VFDB
9. Phylogenetics — IQ-TREE, Nextstrain, transmission cluster detection
10. Metagenomics & microbiome — host filtering, finding pathogens hiding in noise
11. One Health perspective — clinical / animal / environmental sample types
12. PII & data ethics — HRRT, **Cloud DLP**, WHO data sharing principles, federated analysis
13. Pipeline engineering — Nextflow + nf-core + Tower, writing your own modules
14. Platform engineering — JACKPOT internals (FastAPI, schema-driven UI, multi-tenancy)
15. Edge deployment — Jetson, Coral TPU, MinION basecalling on the edge
16. ML/DL for genomics — Janggu, AlphaFold for variant impact, sequence embeddings

**Delivery infrastructure:**

- **JupyterHub** (already on the Month 3 roadmap) hosts the notebooks
- **Synthetic datasets** in `course/data/` — never any PHI, ever. Generated with `wgsim` / `badread` from public refs.
- A dedicated `academy` tenant on a public JACKPOT instance gives every student real platform experience without needing to deploy
- **Badges / micro-credentials** issued by JACKPOT itself (a small `course_completions` table, signed JWT credentials)
- Each module ends with a **JACKPOT integration exercise** — actually log in, upload synthetic samples, run the pipeline, interpret results in the UI
- Workshop-in-a-box: `jackpot init --profile academy` spins up the whole thing on a laptop

### 10.2 The games (Pillar V)

**Outbreak: Field Edition** — single-player narrative puzzle. Eight cases progressing from baseline scans (case 1) through an AMR puzzle (case 4) to a federation-required capstone (case 8).

**OPERATION: WILDFIRE** — multiplayer espionage / federated co-training. Cell management, mole / adversarial-cell mechanics, six missions implementing the original "Stop the Plague" arc.

The games are not decoration. They generate adversarial training data for both bio-AIS and cyber-AIS detectors:

- Game player tries to evade a detector → that's an adversarial example
- Game player tries to poison a federation peer → that's training data for `detect_anomalous_traffic`
- Game player tries to exfiltrate a sample → that's training data for the cyber-AIS NSA

The training/gaming/platform feedback loop closes in Phase 31 of the post-P5 roadmap. Game submissions feed the clonal-selection labeling pipeline; detector improvements show up in the next round of game cases; players generate new adversarial scenarios. The platform learns from being attacked by people who are explicitly trying to break it.

---

## 11. Differentiators vs. peer platforms

JACKPOT's positioning relative to the peer landscape (Pathoplexus / Loculus, GenSpectrum / LAPIS, Pathogenwatch, EnteroBase, NCBI Pathogen Detection, BV-BRC, Solu, RT-MetA, GISAID, IDseq, IRIDA-ARIES, amr.watch, SeqScreen-Nano, HPD-Kit):

| Differentiator | JACKPOT | Peer platforms |
|---|---|---|
| **Two PII gates at ingest** (HRRT for genomic + Cloud DLP for metadata) | Yes — `ingest_scrubber.nf` + `dlp_scanner.py` | Loculus has neither; most have one or zero |
| **Operator-agnostic codebase** (zero proper names in production code) | Yes — Cleanup A–J + `audit_proper_names.py` | Most platforms are tied to one operator |
| **Eight scenarios from laptop to federation** | Yes — A through H | Most platforms are single-deployment |
| **AGPL-3.0 with clear governance** | Yes — `Midnight-Oil-Innovation/jackpot` | Mixed; many MIT or proprietary |
| **CARE-Principle-aware Tribal deployment** | Yes — Scenario T, Phase 24.5 design lockdown | None of the peer platforms address this |
| **On-prem-first messaging** | Yes — laptop / RC cluster lead, cloud follows | Most are cloud-platform-first |
| **Peacetime utility** (AMR, TB, flu, UTI year-round) | Built into the pipeline zoo | Surveillance-only platforms struggle for routine use |
| **BYOP with multi-engine support** (Nextflow / Snakemake / WDL / manifest) | Phase 24.7 / P0f | Most platforms are single-engine |
| **Two-track architecture** (Track 1 ships now, Track 2 immune-overlay scaffolded) | Yes — FED-A landed | Not present anywhere in the peer landscape |
| **Workforce as platform infrastructure** (Academy + games) | Phase 26+ | Not present anywhere in the peer landscape |
| **Dual-AIS architecture** (bio + cyber, same algorithms) | Phase 26+ | Not present anywhere in the peer landscape |

The two-PII-gate ingest, the operator-agnostic codebase, the eight scenarios, the AGPL-3.0 governance, the CARE-aligned Tribal deployment, the on-prem-first messaging — these are real today or imminent. The Academy, games, and dual-AIS architecture are forward-looking but already scaffolded.

---

## 12. Strategic positioning — who adopts JACKPOT and why

### 12.1 Adopter segments

**The spreadsheet-refugee market.** Labs currently tracking samples in shared Excel files or LIMS spreadsheets with no genomics integration. JACKPOT's Scenario A/B is the path of least resistance — `pipx install jackpot && jackpot init`, pick "Laptop" or "Single on-prem server," and within an hour they have a real database, a real schema, real pipelines, and real ingest. This is the largest under-served segment and the one most reachable by the Academy's Practitioner tier.

**WHO IPSN equity story.** Most countries doing pathogen genomics are not running on Google Kubernetes. They're running on a laptop, a single Linux server, or an institutional cluster. The on-prem-first architecture and Apptainer support speak directly to LMIC partners. JACKPOT's two PII gates align with WHO IPSN attribute 6 (most peer platforms align with zero or one).

**University research-computing teams.** RC/HPC teams deploy bioinformatics platforms at scale outside major federal agencies. Their environment is Slurm, Apptainer, shared filesystems, and LDAP. Scenario C is built for them. The execution-profile model (per-pipeline-run executor selection) eliminates the deployment-time decision-making that breaks most "cloud-first" platforms in an HPC context.

**State public health labs (post-DMI).** STLT operators were promised a North-Star-aligned platform. JACKPOT's Scenarios C, E, and a TEFCA/FHIR Year 2+ option give them the architectural shape they were expecting. The "Front Door" pattern in JACKPOT's narrower scope is already here.

**Tribal authorities and Tribal Epidemiology Centers.** A category-of-one differentiator. CARE-Principle-aligned, Scenario T air-gappable architecture, Tribally-controlled aggregation rules. The work is mostly governance and config plus the one architectural piece (deletion-on-request) — meaningful but not enormous. The political-architectural alignment is the moat.

**Federation members (Year 2+).** The FED-A scaffold is the foundation. Real federation use cases include cross-state outbreak investigation, cross-border AMR surveillance (US/Mexico/Canada via PulseNet successor), cross-institutional university collaboration, and public-health-to-One-Health linkage (clinical + veterinary + environmental).

### 12.2 The "peacetime utility" requirement

A critical requirement for long-term funding is ensuring the platform provides routine value during non-pandemic periods:

- **Routine clinical support** — seasonal influenza, UTI sequencing, tuberculosis (TB) diagnostics
- **Antimicrobial resistance (AMR)** — phenotypic susceptibility data and genotypic AMR tracking provide year-round value to hospitals and agricultural agencies
- **Extended health insights** — secondary use in early cancer screening or precision medicine monitoring during peacetime

JACKPOT's pipeline zoo (MIRA-NF, PHoeNIx, MycoSNP-NF, Aquascope, Tostadas, MicrobeTrace adoption in P0i) covers the peacetime use cases that justify continuous operation.

### 12.3 What JACKPOT does NOT do

Saying yes to the right scope is half the battle; saying no to the wrong scope is the other half:

- **Not a case-reporting platform** — NBS / eCR / AIMS occupy that layer
- **Not a LIMS** — JACKPOT integrates with LIMS, doesn't replace them
- **Not a primary repository in the GISAID sense** — JACKPOT can submit to NCBI / GISAID / ENA / DDBJ via Seqsender; it doesn't aim to replace them
- **Not a clinical decision support system** — JACKPOT is for surveillance and research, not patient care
- **Not directly TEFCA-participating** — Year 2+ option for FHIR ingest/emit, gated on operator demand

---

## 13. Publication and partnership pipeline

### 13.1 Differentiator papers (two, in balance)

1. ***JACKPOT: a federated artificial immune system for pathogen genomic surveillance and cyberbiosecurity.*** Methods venue — *Nature Methods* / *Genome Biology* / *PLOS Computational Biology*.
2. ***JACKPOT Academy: workforce-as-platform-infrastructure for public health bioinformatics.*** Workforce venue — *Frontiers in Public Health* / *PLOS Comp Bio Education*.

Both papers' seed material is in `jackpot_immune_platform_plan.md`. The Academy paper is uniquely shippable — workforce/training papers in the genomics-education space are rare and the field is hungry for them.

### 13.2 Partnership angles

- **Biodesign collaboration target (primary).** Identified in `jackpot_immune_platform_plan.md` Section 15.0 as the primary partnership lane.
- **WHO IPSN.** The two-PII-gate architecture and on-prem-first deployment story align directly with IPSN's stated priorities.
- **Tribal Epidemiology Centers.** TECs are HIPAA-recognized public health authorities serving 574 Tribes and 9.7 million AI/AN people. A reference Scenario T deployment at one TEC + one or two member Tribes would establish the federation-tier-0 pattern.
- **University RC teams.** Partner with one institutional RC team for a Scenario C reference deployment. Their feedback hardens the Apptainer-first / systemd-unit-file path, the LDAP/SAML auth path, and the Slurm executor profile templates.
- **CDC operating divisions.** Even in DMI's funding pause, individual operating divisions (NCEZID, OPHDST) have ongoing needs. CDC's open-source pipelines (seqsender, MIRA-NF, PHoeNIx, MycoSNP-NF, Aquascope, Tostadas, MicrobeTrace) are all Apache-2.0; JACKPOT's adoption sequence in P0i picks them up directly.

### 13.3 Open-source adoptions, prioritized

| Item | Source | License | Phase | Justification |
|---|---|---|---|---|
| **seqsender** | CDC | Apache-2.0 | P0i (Month 3) | Replace placeholder NCBI/GISAID submission with real working code |
| **MIRA-NF pipeline** | CDC | Apache-2.0 | P0i (Month 3) | Flu/SARS/RSV via IRMA |
| **PHoeNIx pipeline** | CDC | Apache-2.0 | P0i (Month 3) | AMR/HAI bacteria — high-value for state PHL deployments |
| **MycoSNP-NF pipeline** | CDC | Apache-2.0 | P0m (Month 4) | Fungal (C. auris) — emerging surveillance need |
| **Aquascope pipeline** | CDC | Apache-2.0 | P0m (Month 4) | Wastewater SARS-CoV-2 with NWSS alignment |
| **Tostadas pipeline** | CDC | Apache-2.0 | P0m (Month 4) | NCBI/GISAID submission via Liftoff/VADR/Bakta |
| **MicrobeTrace** | CDC | Apache-2.0 | P0m (Month 4) | Browser-based outbreak visualization |
| **PHIN VADS vocabularies** | CDC | n/a (data) | **Month 3 — urgent** | PHIN VADS sunsets Nov 30, 2026; pull as schema reference data BEFORE then |
| **PHES-ODM data model** | Big-Life-Lab | MIT | P0m (Month 4) | Wastewater alignment for EU/Canadian deployments |
| **GA4GH `/service-info` endpoint** | GA4GH | Apache-2.0 spec | P0i (Month 3) | One afternoon's work, makes JACKPOT discoverable |
| **DRS-style URI conventions** | GA4GH | Apache-2.0 spec | P0i (Month 3) | Already 80% there; formalize as standard |
| **Sapporo-WES spike** | DDBJ | Apache-2.0 | Month 4 (2-week spike) | Evaluate as alternative to bespoke pipeline orchestration |
| **Wave (self-hosted)** | Seqera | AGPL-3.0 | Month 5 | Container provisioning; AGPL-on-AGPL clean |
| **Crypt4GH support** | GA4GH | Apache-2.0 spec | Month 6+ | For Scenarios D/E with sensitive data at rest |
| **Beacon v2 endpoint** | GA4GH | Apache-2.0 spec | Month 6+ | For federation Scenario G |
| **TESSy AMR record-format export** | ECDC | n/a (spec) | Month 6+ | EU bridge for Scenario E European deployments |
| **NCBI SRA Human Scrubber (HRRT)** | NCBI | Public domain | Already in JACKPOT | Already integrated as `ingest_scrubber.nf` |

---

## 14. What this means for the next 90 days

The strategic vision above is multi-year. The immediate sprint is much narrower.

### 14.1 Quick wins for the current P0d–P5 sprint

These are landings that move JACKPOT toward the Immune Platform vision without competing with current roadmap. 1–2 day items each that compound massively when Phase 26+ lands:

1. **Land the schema v6.0 stub now** — empty migration with table definitions but no business logic, behind a feature flag. Forces schema design conversation early.
2. **Add `jackpot-immune-bio.md` to `course/`** — the module 9 starter code, even if production `jackpot-amand` doesn't exist yet. Students can learn NSA against a stub.
3. **License compliance script** (`scripts/verify_licenses.py`) — needed regardless; un-blocks all wraps later.
4. **Audit transaction-participation bug fix** — already a known P0 bug; immune platform needs it; just fix it now.
5. **Synthetic data corpus** — `course/data/synthetic/` generated from public refs via reproducible recipes. Useful for tests, Outbreak cases, and module exercises.
6. **Federation-trust schema sketch** — Alembic stub for `federation_members` and `trust_scores`. Forces the data-model conversation early.

### 14.2 Strategic items in flight or next-up

These map directly to entries in the companion Status & Roadmap document:

- **Phase 24.5 design lockdown** (sovereignty deletion + BYOP + eukaryotic schema additions) — gates P0b
- **Phase 24.7 / P0f BYOP infrastructure** — gates Phase 28 default eukaryotic pipelines
- **PHIN VADS vocabulary pull** — must happen before November 30, 2026
- **GCP staging unblock** (CORS_ORIGINS ConfigMap + IAC-1 through IAC-5) — clears the path for Scenario D/E hardening
- **FED-B/C/D/E wire-up + PRV-A + CRY-A scaffolds** — keeps the Track 1 / Track 2 seam alive and ahead of formal phasing
- **Apptainer compatibility audit on Dockerfiles** — gates Scenario C work

### 14.3 The thing that isn't planned yet but should be

The largest open strategic question is **operator outreach**. The platform is increasingly ready; the deliberate adopter conversations are not. The companion Status & Roadmap document covers the technical sequencing thoroughly. A complementary "first three deployments" plan — one Scenario A reference (laptop / Practitioner-tier student), one Scenario C reference (university RC team), one Scenario T reference (TEC or member Tribe) — would establish the partnership pattern and produce real-world feedback before the Phase 26+ work begins.

That outreach plan is a logical follow-up document to this strategic vision summary, but it's outside the scope of "where we've been and where we're going" framing.

---

## Appendix A — Source documents referenced

| Source | Date | Role |
|---|---|---|
| `JACKPOT_Architecture_Synthesis___May_2026.md` | May 2026 | Source for §2–§6 (eight-scenario reframing, three-package distribution, Docker/Apptainer parity, file references, execution profiles, `jackpot init`) |
| `jackpot_cdc_dmi_stlt_overview.md` | April 2026 | Source for §7–§8 (CDC DMI / North Star / STLT / TEFCA-FHIR / Tribal sovereignty) |
| `jackpot_immune_platform_plan.md` | May 2026 | Source for §9–§10 (five pillars, dual-AIS thesis, workforce-as-platform-infrastructure, Phase 26+ roadmap) |
| `Jackpot_AIS.md` | (working session) | Source for §10 (Academy curriculum, audience tiers, module spine) |
| `jackpot_immune_collaboration_scaffolding.md` | (working session) | Source for §9.5 (Track 1 / Track 2 architectural seam) |
| `jackpot_pathoplexus_loculus_overview.md` | April 2026 | Source for §11 (peer-platform comparative analysis) |
| `Remote_Health_Data_Mesh_Solutions.md` | (working session) | Source context for §12 (network-denied environments, LMIC adopters) |
| `Core_Technical_Pillars.md` | (working session) | Source context for §12 (peacetime utility, NAO/WMGM, federated query architecture) |
| `docs/jackpot_session_summary_and_backlog.md` v3.3 | 2026-05-06 | Concrete delivery state, cross-referenced from companion document |
| `todo.md` | 2026-05-08 | Phase listings, sequencing, cross-referenced from companion document |
| `WHO_Global_genomic_surveillance_strategy.pdf` | (project knowledge) | WHO IPSN attributes referenced in §11 |
| `WHO_guiding_principles_for_pathogen_genome_data_sharing.pdf` | (project knowledge) | 11 WHO Attributes for genomic data-sharing platforms |
