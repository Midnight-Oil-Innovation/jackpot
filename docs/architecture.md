> **Status:** Canonical — system architecture v6.0 (post-Cluster-A).

# JACKPOT Architecture

**Version:** 6.0
**Last updated:** 2026-05-15
**Audience:** Glen Otero — personal developer reference and operator-facing architecture documentation
**Replaces:** `jackpot_architecture.md` v5.0 (2026-04-10), `JACKPOT_Architecture_Synthesis_May_2026.md`, and `Core_Technical_Pillars_copy.md`

**Companion documents:**

- `docs/CLAUDE.md` — Claude Code context file (read at the start of every Claude Code session)
- `docs/spec.md` — operational spec (current as-built state, deployment topology, and active priorities)
- `docs/todo.md` — phase tracking and backlog
- `docs/federation.md` — federation architecture detail
- `docs/wastewater.md` — wastewater surveillance design
- `docs/architecture_diagrams.html` — platform architecture and ingest pipeline diagrams
- `schema/schema/jackpot_schema.yaml` — LinkML schema source of truth

---

## Executive summary

JACKPOT is an operator-agnostic pathogen genomics and sample management platform for next-generation biosurveillance. Its scope spans genomic epidemiology, bioinformatics analysis, federated learning over public-health datasets, homomorphic-encryption-enabled wastewater federated computation, and public-health research at scales from a single researcher's laptop through an agency datacenter.

The platform is **laptop-first, not cloud-first**. Cloud is the upgrade path, not the assumed path. The default `jackpot init` targets self-hosted commodity infrastructure. The default storage assumption is that the operator already has storage. The default executor is local Nextflow with a clear path to Slurm, HPC clusters, or cloud-burst. Cloud-native features (GKE, Cloud DLP, Workload Identity Federation) are scenario-specific configurations, not the baseline.

Four deployment scenarios cover the architectural surface — self-hosted commodity (A), HPC (B), single-org cloud (C), and CI test (D). Multi-organization hosted-SaaS, federation membership, and Indigenous data sovereignty are runtime configurations applied on top of these scenarios rather than separate install paths. Federated learning capabilities (NVIDIA FLARE, PyTorch, ONNX) are installed by default in every deployment; the cryptographic infrastructure for homomorphic federated computation (TenSEAL, OpenFHE) is similarly present. Whether these capabilities are exercised depends on peer configuration, not on install-time choices.

The architectural pattern most distinctive to JACKPOT is its tiered metadata quality model — `PRELIMINARY / ANALYZABLE / SUBMITTABLE` — which makes metadata completeness a first-class queryable property. This pattern is endorsed by WHO's *Guiding principles for pathogen genome data sharing* (Principle 3), the WHO Attributes document for genomic data-sharing platforms (Section 2.6), and the PHA4GE SARS-CoV-2 contextual data standard (Griffiths et al. 2022). The pattern is detailed in §11.

---

## Table of contents

1. [What JACKPOT is](#1-what-jackpot-is)
2. [Architecture philosophy](#2-architecture-philosophy)
3. [Deployment scenarios](#3-deployment-scenarios)
4. [Tech stack](#4-tech-stack)
5. [Repository structure and distribution](#5-repository-structure-and-distribution)
6. [The `jackpot init` CLI and container runtimes](#6-the-jackpot-init-cli-and-container-runtimes)
7. [Permission and authentication](#7-permission-and-authentication)
8. [System architecture overview](#8-system-architecture-overview)
9. [Data model](#9-data-model)
10. [File references and storage model](#10-file-references-and-storage-model)
11. [Metadata quality tiers](#11-metadata-quality-tiers)
12. [Data governance and access control](#12-data-governance-and-access-control)
13. [Data lifecycle — scrubbing and deletion](#13-data-lifecycle--scrubbing-and-deletion)
14. [Ingest methods](#14-ingest-methods)
15. [Dataset model](#15-dataset-model)
16. [Pipeline architecture](#16-pipeline-architecture)
17. [Workspace — JupyterHub and SDK](#17-workspace--jupyterhub-and-sdk)
18. [Standards and FAIR compliance](#18-standards-and-fair-compliance)
19. [External integrations](#19-external-integrations)
20. [Federation architecture](#20-federation-architecture)
21. [Open-source adoptions](#21-open-source-adoptions)
22. [Data sovereignty and governance](#22-data-sovereignty-and-governance)
23. [Testing framework](#23-testing-framework)
24. [Development roadmap](#24-development-roadmap)
25. [Documentation strategy](#25-documentation-strategy)
26. [Critical Rules quick reference](#26-critical-rules-quick-reference)
27. [Diagram reference](#27-diagram-reference)
28. [Companion documents and references](#28-companion-documents-and-references)

---

## 1. What JACKPOT is

### 1.1 Vision — next-generation biosurveillance

JACKPOT is a proactive, real-time, pathogen-agnostic platform for next-generation biosurveillance and genomic epidemiology. It is designed to support the shift away from reactive, disease-specific testing (e.g., PCR for a known pathogen) toward universal detection through metagenomic shotgun sequencing, with the ability to identify "Disease X" — an as-yet-unknown pathogen — before clinical symptoms manifest at population scale.

The platform's core technical pillars:

- **Widespread Metagenomic Monitoring (WMGM).** Prioritize metagenomic shotgun sequencing across clinical, environmental, and One Health sample sources. The schema treats samples from clinical isolates, wastewater, veterinary, agricultural, and wildlife sources as first-class peers rather than as edge cases.
- **Nucleic Acid Observatories (NAO).** Integrate automated environmental monitoring of waterways and wastewater to detect emerging pathogens at the sewershed level. The wastewater schema module (`docs/wastewater.md`) treats wastewater sites as persistent `MonitoringSite` entities with population denominators and catchment geometry, enabling continuous community-level surveillance signal.
- **Edge computation and compression.** For field-portable sequencing in low-bandwidth settings, the platform's data model supports AI-driven basecalling and variant detection at the edge with the data-to-transmit minimized to consensus genomes and metadata.
- **Delay-tolerant networking compatibility.** The federation infrastructure supports file-based transports (Google Drive, SyftBox) in addition to standard network protocols, enabling FL participation from intermittent-connectivity environments. This is achieved through the `syft-flwr` integration pattern when needed; the primary transport for production federation is standard HTTPS.

### 1.2 Scale goal and WHO 11 Attributes alignment

JACKPOT scales from a single researcher running a laptop deployment through dozens of samples in a small lab, through thousands of samples in a single-org cloud deployment, through pandemic-response readiness at multi-lab agencies and federated multi-org consortia. Every architectural decision has an upgrade path that does not require re-deployment — same codebase, additional configuration.

The platform is designed to satisfy WHO's eleven attributes for pathogen genomic data-sharing platforms (PGDSPs), as articulated in *Attributes and principles of genomic data-sharing platforms supporting surveillance of pathogens with epidemic and pandemic potential* (WHO). Status alignment is detailed in §18; in summary, JACKPOT's design directly implements the structural commitments those attributes require: tier-aware curation (Attribute 6), defined minimum metadata with optional extensions (Attribute 4), interoperable controlled vocabularies (Attribute 9), traceable submission methods (Attribute 5), and federation-compatible architecture for cross-jurisdictional collaboration (Attribute 11).

---

## 2. Architecture philosophy

### 2.1 Laptop-first, not cloud-first

The most important architectural commitment in JACKPOT's design: **the platform is a laptop and on-prem-server platform that also scales to cloud and federation.** Not the other way around.

This is more than positioning. It cascades through nearly every architectural decision below. The default `jackpot init` flow targets a laptop or single Linux server. The default storage assumption is "the operator already has storage." The default executor is local Nextflow with a clear path to Slurm. The default auth is simple (mock user for development, with OAuth/LDAP/SAML as configured upgrades). Cloud-native features (GKE, Cloud DLP, Workload Identity Federation) become scenario-specific configurations, not the baseline.

This positioning is what makes JACKPOT credible to WHO IPSN's equity story and to university research-computing audiences — both of which are far larger early-adopter pools than "state public health agencies with cloud programs." It also matches what individual researchers, small labs, and educational deployments actually need: something that runs on the hardware they already have, with the auth their institution already uses, against the data they already control.

### 2.2 Schema-first

The LinkML schema (`schema/schema/jackpot_schema.yaml`) exists before the first router is written. Database tables, API validation models, and DataHarmonizer templates are generated from it. There is no path to ingest a sample without going through the validator.

The reasons:

- **One source of truth.** The schema is the canonical contract between data producers (researchers, sequencing labs, instruments) and data consumers (analytical pipelines, federation peers, downstream platforms). Drift between these layers is eliminated by generation, not by review.
- **Vocabulary anchoring.** Controlled vocabularies for organism, biospec type, location, sector, and host species are defined in the schema and propagate to all consumers. Pathogen names use NCBI Taxonomy; geographic locations use ISO-3166-2 codes; epidemiological context uses GenEpiO terms; environmental features use ENVO terms.
- **Tier-aware validation.** The schema knows which fields are required for each completeness tier (PRELIMINARY / ANALYZABLE / SUBMITTABLE). The validator enforces tier transitions at ingest time. No "advisory required" semantics that get bypassed by data-importer code — the schema is enforced.
- **Reproducibility.** External consumers of JACKPOT data can verify that incoming records conform to the same schema JACKPOT itself uses. Schema artifacts (Pydantic models, LinkML output, JSON Schemas, TSV templates) are bundled into the SDK so that external code can validate against the same source of truth.

### 2.3 Resilience and privacy pillars

JACKPOT operates effectively across the full range from well-resourced cloud deployments through network-denied environments (conflict zones, rural sites, intermittent connectivity). Several architectural commitments enable this:

- **Delay-tolerant networking compatibility.** Federation transports support file-based exchange (Google Drive, SyftBox via `syft-flwr`) in addition to standard network protocols. This enables federation participation from environments where consistent network reachability cannot be assumed.
- **Federated query architecture.** A federated query system, compatible with GA4GH standards (Beacon v2, `/service-info`), allows multi-jurisdictional analysis without exposing raw sequencing data. See §20.
- **Zero-trust security model.** Authentication and authorization are applied at every layer of the data lifecycle — from the field sequencer through the cloud repository. RBAC is enforced in middleware, not just in route handlers. Audit logging captures every state-changing operation with before/after diffs.
- **Normalized data model.** A `MonitoringSite` entity stores persistent site metadata (location, population, capacity, geometry) and individual sample records reference it via foreign key. This reduces storage overhead and avoids the data integrity hazards of repeated free-text site labels at repeated sampling locations.

### 2.4 Peacetime utility

A critical requirement for long-term funding and sustainability: JACKPOT provides routine value during non-pandemic periods, not only during emergency response. The platform supports:

- **Routine clinical surveillance.** Seasonal influenza, UTI sequencing, tuberculosis (TB) diagnostics, and respiratory pathogen panel surveillance.
- **Antimicrobial resistance (AMR) tracking.** Integration of phenotypic susceptibility data with genotypic AMR analysis (via `hAMRonization`-compatible output and `tb-profiler` integration). Year-round value to hospital antimicrobial stewardship programs and agricultural agencies.
- **Wastewater monitoring at routine cadence.** Aquascope SARS-CoV-2 surveillance, plus PHES-ODM-aligned wastewater data exchange for EU/Canadian collaboration.
- **Extended secondary uses.** Early cancer screening signal, precision medicine monitoring, and One Health surveillance integration during inter-outbreak periods.

This is not an afterthought to the design — it is built into the schema (One Health sectors as first-class peers), into the pipeline architecture (multiple pipeline families for different routine workloads), and into the federation model (continuous low-volume sharing is the steady state, not the exception).

---

## 3. Deployment scenarios

JACKPOT's deployment surface is described by four scenarios. Each represents a meaningfully different `jackpot init` configuration path. Within each scenario, several runtime configurations adjust behavior — multi-tenancy at the lab or org level, federation participation, sovereignty policy, persistence model — without requiring re-installation or a different scenario label.

### 3.1 The four scenarios

| Scenario | Description | Compute target | Container runtime | Typical operator |
|---|---|---|---|---|
| **A** | Self-hosted commodity infrastructure | Local Nextflow; optional Slurm or cloud-burst profiles | Docker (default), Apptainer (Linux site policy) | Single user, lab IT, PI, or agency platform team |
| **B** | HPC | Slurm/PBS cluster | Apptainer (forced by HPC policy) | University RC team or institutional HPC operations |
| **C** | Single-org cloud | GKE / EKS / AKS — cloud-native | Docker images via cloud orchestrator | Org IT or cloud operations |
| **D** | CI test | Local containers | Docker | n/a — CI automation |

Two terms used consistently throughout this document:

- **Multi-tenancy** — a technical property of the deployment, meaning the same running instance isolates multiple distinct entities. The tenant boundary is at the **lab level** for multi-lab deployments and at the **org level** for multi-org deployments.
- **Tenant boundary** — the level at which isolation is enforced (lab-level or org-level). All four scenarios support both lab-level and org-level multi-tenancy; the configuration is set at install time and at runtime via the multi-tenancy middleware (which is always present and default-on).

### 3.2 A — Self-hosted commodity infrastructure

The most flexible scenario. Covers the full range from a single user running JACKPOT on a laptop through an agency datacenter running it across several Linux servers. The shared property is **commodity infrastructure** — standard servers, not HPC clusters, not cloud-managed Kubernetes.

What `jackpot init` for Scenario A asks:

1. **OS detection.** macOS or Linux. Determines available container runtimes and service orchestration options.
2. **Persistence model.** Ephemeral (start/stop manually, laptop-style) or persistent (systemd-managed, auto-start on boot). macOS is ephemeral-only in the current version; persistent macOS via launchd is a deferred future enhancement.
3. **Container runtime.** Docker Desktop (macOS, auto-selected) or Docker / Apptainer (Linux, asked).
4. **Auth.** Mock user (dev), username/password (small lab), Google OAuth (Workspace shops), or LDAP/SAML (institutional).
5. **Storage.** Local filesystem, MinIO container, existing S3-compatible endpoint, or GCS bucket.
6. **Compute executor profile defaults.** Default is `local` (Nextflow on the API server). Slurm and cloud-burst profiles are configurable post-install via `jackpot profiles add ...`.
7. **Multi-tenancy.** Single-lab single-org (default), multi-lab single-org (university or multi-lab agency), or multi-org (consortium or SaaS-style).

The combinatorial range this covers:

- macOS laptop, single user, ephemeral — the simplest case
- Linux laptop, single user, ephemeral — same as above but with Linux runtime options
- Linux laptop, single user, persistent with systemd — a dev laptop that hosts JACKPOT for the user's own work, auto-starting at boot
- Linux server, lab IT, persistent — small lab with one server, default install
- Multi-server Linux, agency platform team, persistent, multi-lab — a state health agency or multi-lab consortium running JACKPOT on several servers
- Any of the above with multi-org tenancy enabled — a hosted-SaaS-style deployment serving multiple organizations on one platform

Scenario A is the default first-time install. It is what every developer, interested lab, and academic adopter encounters first.

### 3.3 B — HPC

University research-computing and institutional HPC environments. The differentiating property is that the infrastructure forces specific choices:

- **Apptainer required.** Docker is forbidden on most HPC environments by site policy. Apptainer is the container runtime.
- **Slurm/PBS submission.** The whole point of an HPC deployment is to dispatch compute to the cluster. The default execution profile is Slurm submission.
- **Institutional storage.** Lustre, GPFS, or Ceph mounted as a filesystem path. JACKPOT does not run its own object storage in this scenario; data lives on the institutional shared filesystem.
- **LDAP/SAML auth.** Universities use single sign-on. Username/password and OAuth are not realistic for HPC operators.

What `jackpot init` for Scenario B asks differs from A in:

- No question about persistence (always persistent on the cluster login node)
- No question about container runtime (Apptainer always)
- Slurm-specific configuration: account, partition, QoS, shared filesystem path, scratch directory pattern
- Auth defaults to LDAP/SAML

Operator persona is the RC team. Documentation tone assumes the operator runs Slurm clusters and asks "what JACKPOT-specific config goes alongside what we already have?"

### 3.4 C — Single-org cloud

Cloud-native deployments using Kubernetes orchestration. The differentiating property is that the operator wants to use cloud-managed services and elastic scaling rather than self-hosted commodity infrastructure.

- **Kubernetes orchestration.** GKE, EKS, or AKS. Helm-managed services.
- **Cloud-native compute executor.** GCP Batch, AWS Batch, Cloud Run, or Kubernetes Jobs.
- **Cloud-native storage.** GCS, S3, Azure Blob Storage with cloud-native lifecycle management.
- **Cloud-native auth.** Workload Identity Federation, IAM-bound service accounts, plus user-facing auth via the cloud's IdP.

What `jackpot init` for Scenario C asks:

- Cloud provider (GCP, AWS, Azure)
- Cluster identifier and region
- Default execution profile (Batch / Cloud Run / k8s Jobs)
- Storage bucket
- Auth IdP

Operator persona is org IT or cloud operations. Documentation tone assumes familiarity with k8s, cloud-native patterns, and IaC tools (Terraform).

### 3.5 D — CI test

Automated testing environment. Minimal infrastructure, ephemeral, no real workloads. The differentiating property is that everything is mocked or local — no external dependencies, no real federation peers, no real cloud services.

- Local containers, Docker
- Ephemeral lifecycle (one test run, then destroyed)
- Mock auth (single test user with all roles)
- In-memory or temp-disk storage
- Local-only Nextflow execution
- ML stack (PyTorch, FLARE, ONNX) optional — installed only for tests that exercise them

Scenario D doesn't have an interactive `jackpot init` flow. Configuration is generated programmatically by the test harness.

### 3.6 What does NOT appear as a separate scenario

Several deployment patterns that operators might consider "their scenario" are runtime configurations of A, B, or C rather than separate scenarios:

- **Hosted SaaS / multi-org tenancy.** A operator running JACKPOT to serve multiple customer organizations. This is Scenario A (or C) with multi-org tenancy enabled in the multi-tenancy middleware. Same install path; different runtime configuration.
- **Federation member.** A deployment that participates in cross-deployment federation. Federation services are present in every install (see §20). Activation happens when peers are added post-install via `jackpot peers add ...`. Same install path; different post-install configuration.
- **Indigenous data sovereignty / CARE-aligned governance.** A deployment that enforces CARE-Principle data governance, sovereignty over sensitive datasets, residency requirements, and revocable consent. This is a runtime policy configuration applicable to any scenario. See §22.

A tribal college running JACKPOT for genomics coursework picks Scenario A. A Tribal Nation health department running JACKPOT with CARE enforcement also picks Scenario A and configures sovereignty policies post-install. A state public health lab running JACKPOT to host data for multiple municipal labs picks Scenario A with multi-tenancy at the lab level. A consortium of state labs sharing data via federation picks Scenario A (or whichever infrastructure matches them) and configures peers post-install.

The architectural commitment is: **scenarios describe install-time infrastructure configurations; everything else is runtime policy.**

### 3.7 Bulletproof vs production-hardened vs future

Within the four scenarios, maturity differs across deployment shapes:

- **Bulletproof from day one** — A (laptop through small server), D (CI). These are tested continuously, work for new operators with minimal hand-holding, and have the most polished documentation.
- **Production-hardened** — A (multi-server / agency scale), B (HPC), C (cloud). These work but require more operator expertise. Documentation is more reference-oriented; assumes the operator has run similar infrastructure before.
- **Stable but emerging** — Multi-org tenancy, federation participation, sovereignty policy enforcement. These are real architectural commitments with implementation in progress. Specific capability maturity tracked in §24 and `docs/todo.md`.

---

## 4. Tech stack

The platform stack, by layer:

**Languages and runtime.** Python 3.12 throughout. Bash for operational scripts and `jackpot init` plumbing. Nextflow DSL2 for pipeline workflows.

**API framework.** FastAPI (current) with Pydantic v2 for request/response validation. Async route handlers; synchronous DB operations via SQLAlchemy 2 with explicit transaction management.

**Database.** PostgreSQL 16 as the metadata database. Alembic for schema migrations. PostgreSQL is the right choice across the deployment range — works on laptop (Docker Compose), single server, cluster (with appropriate sizing), and cloud (Cloud SQL / RDS / Azure Database for PostgreSQL).

**Pipeline orchestrator.** Nextflow with `nf-core` compatibility. Pipelines live in `pipelines/` directory in the monorepo and are cloned at runtime by Nextflow. Execution profile abstraction (see §16) decouples pipeline definitions from execution targets.

**Object storage.** MinIO for self-hosted scenarios (Scenario A); GCS / S3 / Azure Blob for cloud (Scenario C); institutional Lustre / GPFS for HPC (Scenario B). Storage is referenced via `file_references` with `FileStorageState` enum (see §10).

**Authentication.** Google OAuth + JWT cookies as one option among several. Username/password, LDAP/SAML, and mock-user modes are first-class peers. Auth backend is pluggable, configured at `jackpot init` time.

**Frontend.** Streamlit researcher portal (in-platform), running as a Docker container in Scenarios A/C/D and as an Apptainer instance in Scenario B. A `jackpot-cli` Python SDK provides programmatic access for notebooks, scripts, and BYOP (bring-your-own-pipeline) development.

**Workspace (in scenarios C and B).** JupyterHub on GKE (Scenario C) or on the institutional HPC (Scenario B). Three researcher Hub profiles: lightweight (CPU only), GPU-enabled, and large-memory.

**ML stack — installed by default in every deployment.** PyTorch (CPU or CUDA, auto-detected via `nvidia-smi` at install). NVIDIA FLARE for federated learning. ONNX and ONNX Runtime for model interchange. scikit-learn for classical machine learning. These are core dependencies, not optional installs.

**Privacy and federation primitives.** TenSEAL or OpenFHE for homomorphic encryption workloads (specifically cryptWWDB). NVIDIA FLARE handles differential privacy, secure aggregation, private set intersection, and homomorphic encryption for FL workloads. PySyft is available as an alternate framework for specific MPC workloads where FLARE's primitives are insufficient.

**Background jobs.** APScheduler for in-process scheduled jobs (e.g., periodic file verification, scrubber queue management). Works across all scenarios from laptop to cloud. For multi-pod deployments in Scenario C, APScheduler is configured with leader election or disabled in favor of a Kubernetes CronJob.

**Schema modeling and code generation.** LinkML v4.4 as the schema source of truth. The schema generates Pydantic models, JSON Schemas, DataHarmonizer templates (TSV), and DB DDL.

**Standards and ontologies.** NCBI Taxonomy for organisms; ENVO for environmental features; GenEpiO for epidemiological context; ISO 3166 for countries; UBERON and OBI for biological samples; SNOMED-CT for clinical fields where applicable; DUO (Data Use Ontology) for consent tags; PHIN VADS vocabularies (snapshot before the November 30, 2026 sunset) for surveillance-specific terms.

**Submission targets.** TOSTADAS pipeline for NCBI/GenBank submission. seqsender for NCBI SRA submission. GISAID EpiCoV format for influenza/SARS-CoV-2 submission. PHA4GE-aligned export for international compatibility.

---

## 5. Repository structure and distribution

### 5.1 Monorepo layout

The canonical JACKPOT repository is `Midnight-Oil-Innovation/jackpot` on GitHub, AGPL-3.0 licensed. The monorepo holds:

```
jackpot/
├── backend/                # FastAPI app, SQLAlchemy models, business logic
├── frontend/               # Streamlit researcher portal
├── cli/                    # jackpot CLI (init, up, down, doctor, etc.)
│   └── jackpot/sdk/        # jackpot-sdk Python library (importable)
├── schema/                 # LinkML schema and reference data
│   └── jackpot_scenarios/  # Scenario detector and per-scenario config templates
├── pipelines/              # Nextflow pipeline definitions
├── nf/                     # Legacy Nextflow modules (being migrated to pipelines/)
├── deploy/                 # Docker Compose, Helm charts, systemd unit templates
├── tests/                  # Test harness, fixtures, CI workflows
├── docs/                   # Architecture, spec, runbooks, ADRs
└── pyproject.toml          # Workspace root for uv
```

All Python packages within the monorepo are managed by `uv` as a single workspace. The root `pyproject.toml` declares the workspace and per-package `pyproject.toml` files declare individual package dependencies.

### 5.2 Three Python distribution artifacts

JACKPOT produces three distinct distribution artifacts from the monorepo, all sharing the same version tied to releases:

| Path | Package | Distribution | Audience |
|---|---|---|---|
| `cli/` | **`jackpot`** | PyPI (`pipx install jackpot`) + Bioconda (`conda install -c bioconda jackpot`) | Anyone deploying or running JACKPOT |
| `cli/jackpot/sdk/` | **`jackpot-sdk`** | PyPI (`pip install jackpot-sdk`) | Developers writing notebooks, scripts, BYOPs, internal Streamlit pages |
| `backend/` | Docker image on GHCR | `ghcr.io/midnight-oil-innovation/jackpot-backend:vX.Y.Z` | Pulled at runtime by `jackpot up` |
| `frontend/` | Docker image on GHCR | `ghcr.io/midnight-oil-innovation/jackpot-frontend:vX.Y.Z` | Pulled at runtime |
| `schema/` | Bundled into `jackpot` and `jackpot-sdk` | n/a (yet) | Internal |
| `pipelines/` | Cloned at runtime from monorepo | Pulled by Nextflow | Pipeline executor |
| `deploy/` | Bundled inside `jackpot` CLI as package data | Embedded | Operators |

Distribution principles:

- **`jackpot` is the installer/CLI**, not the backend. It is small, pure-Python, ships templates and CLI logic. It pulls Docker / Apptainer images, generates configurations, and orchestrates services. It does not contain FastAPI or SQLAlchemy.
- **`jackpot-sdk` is a separate top-level package.** `jackpot` has an optional dependency on it (`pip install jackpot[sdk]`). This avoids dragging the SDK into every `jackpot init` install for operators who only run the platform without doing notebook work.
- **The backend never gets pip-installed by users.** It is exclusively a container image. Inside the monorepo it has a `pyproject.toml` for development purposes; it is not released to PyPI.
- **`jackpot-schema` is deferred** until there is demonstrated external need. Schema artifacts (Pydantic models, LinkML output, JSON Schemas, TSV templates) ship inside the SDK for now and can be promoted to a standalone package if ELIXIR, Pathoplexus, or a federation member asks for it.

The version-locking story: `jackpot v1.4.2` knows it expects `jackpot-backend:1.4.2`, `jackpot-frontend:1.4.2`, and `jackpot-sdk==1.4.2`. The CLI refuses to use mismatched components and prints a clear upgrade path.

### 5.3 Branching strategy

The repository uses a three-tier branching model:

- **`development`** — integration branch. All PRs land here after review and CI. Always working but not always release-ready.
- **`staging`** — pre-release branch. Fast-forward merged from `development` when ready to deploy to staging. Triggers staging deployment via GitHub Actions.
- **`main`** — release branch. Fast-forward merged from `staging` when staging has been validated. Tagged releases happen here.

Feature work happens on feature branches off `development`, merged back via PR with squash-and-delete. The `jackpot-worktree` and `jackpot-finish` shell functions (see `scripts_jackpot/coding_scripts_howto.md`) automate the worktree lifecycle.

### 5.4 Python environment

The monorepo uses `uv` for Python package management. Workspace dependencies are declared in the root `pyproject.toml` and resolved against `uv.lock`. Both files are committed.

For bioinformatics tools that don't fit cleanly into the Python ecosystem (BWA, samtools, bcftools, GATK, etc.), `pixi` is used as a parallel environment manager. Pipeline containers use bioconda-packaged tools; the operator-side environment uses `pixi` for any CLI bioinformatics utilities that JACKPOT itself shells out to.

Pyright-LSP is configured for type-checking with `typeCheckingMode: "basic"` (via `pyrightconfig.json` in the repo root). Stricter modes are aspirational; basic mode is enforced.

### 5.5 Code quality

Pre-commit hooks enforce:

- `ruff check --fix` — linting and import sorting
- `ruff format` — code formatting
- `yamllint` — YAML schema files
- `nf-core lint` — Nextflow pipeline definitions
- `mypy` (basic) — type checking on critical paths

CI pipeline (`.github/workflows/test.yml`) runs:

- All pre-commit checks
- pytest with coverage threshold (>85%)
- Schema validation (LinkML → Pydantic generation roundtrip)
- Container image build verification
- Helm chart lint (when applicable)

The `gac` shell function provides a single-step lint-format-commit workflow (see `coding_scripts_howto.md`).

---

## 6. The `jackpot init` CLI and container runtimes

### 6.1 `jackpot init` as the centerpiece

`jackpot init` is the most important user-facing tool in the platform. It is what turns the operator-agnostic codebase into a per-operator deployment. The architecture of `jackpot init` reflects the architectural commitments in §3:

- One interactive flow handles all four scenarios via OS detection plus a small number of policy questions
- Federation is not asked at install time — federation services are installed by default and activated by adding peers post-install
- ML stack (PyTorch, FLARE, ONNX) is installed by default; no developer-vs-operator role discrepancy
- Sovereignty is not asked at install time — it is a post-install runtime policy configuration

### 6.2 The interactive flow

```
$ pipx install jackpot
$ jackpot init

Welcome to JACKPOT. Let's set up your deployment.

[Infrastructure detection]
Detected OS: macOS (or Linux)
Detected GPU: nvidia-smi found / not found
Detected available memory: <X> GB

[Scenario]
  1) A — Self-hosted commodity infrastructure (default)
  2) B — HPC (Slurm/Apptainer/institutional storage)
  3) C — Single-org cloud (GKE/EKS/AKS)
  4) D — CI test (automated; not interactive)
  Pick: 1

[Persistence model]
  1) Ephemeral — start/stop manually, no auto-start at boot
  2) Persistent — systemd-managed, auto-start at boot, restart on failure
  Pick: 1
  (note: macOS supports ephemeral only for now)

[Container runtime]
  Detected: macOS — Docker Desktop selected (no other option)
  (or for Linux:)
  1) Docker
  2) Apptainer
  Pick: 1

[Auth]
  1) Mock user (single user, dev only)
  2) Username/password (small lab, simple)
  3) Google OAuth (Workspace shop)
  4) LDAP/SAML (institutional)
  Pick: 2

[Storage backend]
  1) Local filesystem (~/.jackpot/data/)
  2) MinIO container
  3) Existing S3-compatible (provide endpoint)
  4) GCS bucket
  5) Institutional shared filesystem (Lustre/GPFS path)
  Pick: 2

[Compute executor]
  Default profile: local (Nextflow on this server)
  (Additional profiles configurable post-install via `jackpot profiles add`)

[Multi-tenancy]
  1) Single-lab single-org (default for laptops, dev installs)
  2) Multi-lab single-org (university, agency, multi-lab consortium)
  3) Multi-org (consortium of organizations, hosted SaaS)
  Pick: 1

[PyTorch CUDA]
  Detected: nvidia-smi found / not found
  Installing: pytorch-cuda (or pytorch CPU-only)

[Federation services]
  Federation services are installed by default in every deployment.
  Activate by adding peers later via `jackpot peers add`.

[Confirmation]
Configuration saved to ~/.jackpot/config.yaml
Run `jackpot up` to start JACKPOT.
Run `jackpot doctor` to verify the deployment.
```

### 6.3 Generated configuration bundle

Each scenario produces a different bundle of files under `~/.jackpot/`:

```
~/.jackpot/
├── config.yaml                    # operator's config
├── docker-compose.yml             # if container_runtime=docker
├── systemd/                       # if persistence=persistent
│   ├── jackpot-postgres.service
│   ├── jackpot-minio.service
│   ├── jackpot-backend.service
│   └── jackpot-frontend.service
├── nextflow/
│   ├── local.config               # always — default profile
│   ├── slurm-default.config       # if Slurm profile added
│   └── gcp-batch.config           # if cloud-burst profile added
├── data/                          # if storage=local
└── work/                          # JACKPOT_WORK_DIR
```

### 6.4 CLI commands

| Command | Purpose |
|---|---|
| `jackpot init` | Interactive setup; generates config + bundle |
| `jackpot up` | Start all services using configured runtime |
| `jackpot down` | Stop all services |
| `jackpot logs [service]` | Tail logs |
| `jackpot ps` | Show service status |
| `jackpot doctor` | Health-check every component, runtime-aware |
| `jackpot upgrade` | Pull matching versions of backend/frontend, run migrations |
| `jackpot images export/import` | Pre-stage container images for air-gapped install |
| `jackpot files promote` | Change storage state of a file_reference |
| `jackpot profiles list/add/edit` | Manage execution profiles |
| `jackpot peers list/add/remove` | Manage federation peers |
| `jackpot policy enable/disable/list` | Manage runtime policies (sovereignty, residency, etc.) |
| `jackpot backup/restore` | Database + managed-storage backups |

### 6.5 Container runtimes — Docker and Apptainer

The `jackpot` CLI supports two container runtimes, selected at `jackpot init` time and configured in `~/.jackpot/config.yaml`:

| Runtime | Default for | Service orchestration |
|---|---|---|
| Docker | Scenario A on macOS (always); Scenario A on Linux (default); Scenario C (cloud) | `docker compose` (or k8s for Scenario C) |
| Apptainer | Scenario A on Linux when site policy forbids Docker; Scenario B (HPC, required) | systemd unit files invoking `apptainer instance` |

Container runtime principles:

1. **Same OCI images for both runtimes.** Container images on GHCR work natively with Docker (`docker pull`) and Apptainer (`apptainer pull docker://ghcr.io/...`). No separate image builds.
2. **systemd as the common service manager on Linux.** Whether services run under Docker or Apptainer on Linux, the wrapper is a systemd unit. This makes start/stop/restart/status uniform regardless of runtime. macOS uses Docker Compose directly (no systemd).
3. **Pre-staging support for air-gapped deployments.** `jackpot images export` and `jackpot images import` produce a portable bundle (tar of OCI images for Docker, tar of SIF files for Apptainer) that can be moved into an air-gapped environment.
4. **Host-installed Postgres/MinIO as alternatives.** For Scenario B especially, the RC team often runs Postgres for other things. `jackpot init --use-existing-postgres postgres://...` skips the containerized Postgres and records a connection string. Same for `--use-existing-object-storage` pointing at institutional MinIO/S3/Ceph.
5. **`jackpot doctor` is runtime-aware.** It verifies the configured runtime is installed with correct permissions, can reach configured cluster endpoints, can pull from GHCR (or has pre-staged images), and that data directories have correct ownership.

Apptainer-specific operational concerns (PGDATA permissions running as invoking user, no Docker network bridging, SIF storage on shared filesystem) are handled by systemd unit templates rather than being left as operator homework.

---

## 7. Permission and authentication

### 7.1 Six-role RBAC model

JACKPOT uses a six-role RBAC model with permissions cascading through the organizational hierarchy (org → lab → user):

| Role | Authority scope | Typical assignment |
|---|---|---|
| **Platform Admin** | Cross-org platform management | Operator IT team (Scenario C, multi-org A) |
| **Org Admin** | Single org full administration | Lab director, agency platform team |
| **Lab Director (PI)** | Single lab — full authority over lab data and members | Principal investigator |
| **Lab Member** | Single lab — read/write own data, read lab-shared data | Lab researcher, postdoc, student |
| **Org Researcher** | Cross-lab read access to discoverable data within org | Cross-lab collaborator, agency analyst |
| **External** | Public-data-only access | External user via API token; unauthenticated public endpoints |

Permission rules:

- A user belongs to one org and zero-or-more labs within that org
- Lab membership grants read/write to that lab's data per the lab's policy
- The Lab Director (PI) is the access authority for their lab — approving cross-lab access requests, designating discoverable data, etc.
- The Org Admin is the access authority for cross-lab patterns within their org
- Platform Admins exist only in multi-org deployments

### 7.2 Authentication

Authentication backends are configured at `jackpot init` time:

- **Mock user** — for development. Single user with all roles. Not for production.
- **Username/password** — for small labs. Internal user table with hashed passwords. Suitable for labs with <50 users.
- **Google OAuth** — for Workspace shops. JWT cookie flow. Standard production option for cloud deployments.
- **LDAP/SAML** — for institutional deployments. Standard production option for HPC and large org deployments.

All four backends issue JWT cookies with consistent claims. The JWT refresh endpoint is on the roadmap (currently noted as missing in §8's architecture diagram).

### 7.3 Personal API tokens

Independent of the primary auth flow, JACKPOT supports per-user personal API tokens for programmatic access (SDK, scripts, BYOP development). Tokens are scoped:

- Per-token role: typically equal to or less than the user's overall role
- Per-token expiration: default 1 year; user-configurable
- Per-token lab restriction: limit to a specific lab if the user belongs to multiple

Token revocation is immediate. Tokens are stored hashed; the cleartext is shown once at creation.

### 7.4 Signed upload URLs

For ingest workflows that bypass the API server (rsync/rclone direct to S3, browser-side upload via signed URL), JACKPOT issues short-lived signed URLs scoped to a specific sample ingest. URLs expire in 15 minutes by default; configurable per-endpoint.

---

## 8. System architecture overview

The platform follows a five-layer architecture. See `docs/architecture_diagrams.html` SVG 1 for the visual.

### 8.1 The five layers

**Layer 1 — User interfaces.** Streamlit researcher portal (browser-based; runs as a container in Scenarios A/C and as Apptainer instance in B). `jackpot-cli` Python SDK for programmatic access. Both consume the same API.

**Layer 2 — FastAPI backend.** Middleware for request IDs and CORS. Auth layer for Google OAuth / JWT cookies / LDAP / personal tokens with 6-role RBAC enforced in `guards.py`. 21 routers organized by domain (orgs, labs, users, domains, tokens, ingest, samples, pipelines, datasets, federation, etc.).

**Layer 3 — Business logic.** Validator (tier-aware, source-type-aware). File detector (paired-end, multi-lane merging, nanopore chunks, content sniffing for file type). Epiweek computation (MMWR and ISO). Harmonizer (CSV mapping configurations). Audit logging (before/after state).

**Layer 4 — Storage.** PostgreSQL 16 (Cloud SQL in C, containerized in A, host-installed available in all scenarios). MinIO → GCS / S3 for object storage. APScheduler in-process for background jobs (with leader election in C). Seed data (controlled vocabularies, reportable organism lists, demo labs and pathogens for development).

**Layer 5 — External integrations.** Pipeline execution (Nextflow + GCP Batch, or Slurm, or local). Submission targets (NCBI, GISAID, NWSS). Auth providers (Google, institutional IdPs). Pipeline ecosystem (Seqera for advanced features, optional).

### 8.2 Local development environment

For Scenario A (and for Scenario D CI):

- `jackpot up` brings up the full stack via Docker Compose (or systemd if persistent)
- All services run on `localhost` with predictable ports
- The Streamlit UI is accessible at `http://localhost:8501`
- The API is accessible at `http://localhost:8000`
- Hot-reload is enabled for backend (uvicorn `--reload`) and frontend (Streamlit auto-reload)
- Mock auth supports rapid iteration; role switching available via `jackpot dev role <role>`

### 8.3 GCP production architecture (Scenario C example)

For Scenario C on GCP:

**Database.** Cloud SQL for PostgreSQL 16. Highly-available regional configuration for production. Alembic migrations run via init container before backend deployment.

**Object storage.** GCS with separate buckets for staging (`<project>-staging`), permanent sequences (`<project>-sequences`), and pipeline work (`<project>-work`). Lifecycle policies on staging (auto-delete after 30 days), versioning on permanent sequences.

**GKE node pools.** Default pool for API/frontend (small nodes, autoscaling). GPU pool for JupyterHub if configured. Pipeline execution typically dispatched to GCP Batch rather than running in-cluster, avoiding node-pool sizing complexity for compute-heavy pipelines.

**Background jobs.** APScheduler with PostgreSQL-backed leader election when running multiple backend pods. Alternative: disable APScheduler in cluster, use Kubernetes CronJobs.

**Caching.** Redis (optional, single-replica) for session caching and rate limiting. Not required; gracefully degraded when absent.

**Environment variables.** Local and production environments differ in: storage backend (MinIO vs GCS), auth IdP (mock vs Google OAuth), DLP enabled (false vs true), executor profile (local vs gcp-batch). All via `~/.jackpot/config.yaml`.

**Disaster recovery.** Database backups via Cloud SQL automated backups + point-in-time recovery. Object storage via GCS versioning. Configuration via `jackpot backup`. Recovery via `jackpot restore`.

---

## 9. Data model

### 9.1 Table inventory

Core tables (organized by domain):

**Identity and access.**
- `organizations` — top-level org records
- `labs` — labs within an org
- `users` — user records, with org and lab memberships
- `personal_tokens` — issued API tokens
- `audit_log` — append-only state-change log

**Samples and files.**
- `samples` — core sample record (with `quality_status`, `sharing_level`, `surveillance_relevant`)
- `sample_files` — file references with `FileStorageState` (see §10)
- `sample_metadata_extensions` — JSONB for vocab fields not in the canonical schema
- `monitoring_sites` — persistent site metadata for wastewater and environmental sampling
- `vector_collections` — arthropod and vector sample records

**Datasets and submission.**
- `datasets` — analytical dataset collections with `tier` (private / lab / discoverable / public)
- `dataset_samples` — many-to-many between datasets and samples
- `submissions` — outbound submission packages (NCBI, GISAID, NWSS)
- `submission_files` — file artifacts associated with submissions

**Pipelines.**
- `pipeline_catalog` — registered pipelines and their schemas
- `pipeline_runs` — execution records
- `pipeline_results` — typed result records per pipeline type
- `pipeline_telemetry` — runtime metrics, cost, duration, retry counts
- `execution_profiles` — operator-configured execution targets (local, Slurm, cloud, etc.)
- `pipeline_default_profile` — per-pipeline default profile

**Federation.**
- `federated_instances` — peer records (URLs, roles, policies)
- `federation_jobs` — multi-round federated computations (FL rounds, cryptWWDB queries)
- `federation_tags` — soft grouping for federation membership

**Sovereignty and policy.**
- `policy_grants` — runtime policy enablement records
- `consent_revocations` — revocable consent tracking
- `data_residency_rules` — operator-configured residency requirements

Approximate scale: ~40 tables for the core platform, plus ~10 more for federation, sovereignty, and pipeline-result-specific tables.

### 9.2 Key relationships

- A sample belongs to a lab (FK) and has zero-or-more file references
- A sample's lab determines its access control via the RBAC cascade
- A sample's `quality_status` and `sharing_level` are computed at ingest and recomputed on update
- A monitoring_site is referenced by all samples collected from that site
- A pipeline run references one sample (or a sample-set) and produces one result of typed schema
- A federation peer is identified by base URL and is tagged with one or more federation tags

### 9.3 Key schema decisions

- **Column-per-field for canonical metadata.** Typed columns, controlled vocabularies, no key-value sprawl.
- **JSONB extensions for non-canonical fields.** When a submitter has metadata that doesn't fit the canonical schema, it goes into `sample_metadata_extensions` as JSONB with the original field name. Available for full-text search; not type-enforced.
- **Date with precision.** `collection_date` is a `DATE` column with a parallel `collection_date_precision` enum (`YEAR / MONTH / FULL`). Supports partial dates without losing precision.
- **Integer for numeric metadata.** `host_age`, `population_served`, and similar numeric fields use `INTEGER` or `FLOAT`. Non-numeric input is rejected at ingest, not silently converted.
- **Immutable, append-only pipeline_results.** A pipeline result for a sample never updates; reprocessing creates a new result row. The history is preserved.
- **`audit_log` writes are mandatory and transactional.** Every state change writes an audit log entry in the same DB transaction. If the audit write fails, the state change rolls back. No silent gaps.
- **Surveillance relevance computed, not declared.** `surveillance_relevant` is computed from the sample's organism against the `reportable_organisms` table. Demotions (TRUE → FALSE) require governance board review.

### 9.4 LinkML v4.4 schema design

The schema lives in `schema/schema/jackpot_schema.yaml`. It is the source of truth for:

- DB DDL via LinkML-to-SQL generation
- Pydantic models via LinkML-to-Pydantic generation
- DataHarmonizer TSV templates per source-type
- JSON Schema for API request/response validation

Schema design decisions:

- **Source-type subclasses.** `Sample` is the base class; `ClinicalSample`, `WastewaterSample`, `VeterinarySample`, `EnvironmentalSample`, `VectorSample`, and `MetagenomicSample` are subclasses. Per-subclass required fields are encoded as tier-aware tier rules.
- **Ontology anchoring.** Slots carry `slot_uri` annotations linking to NCBI Taxonomy, ENVO, GenEpiO, UBERON, OBI, SNOMED-CT. This makes JACKPOT data interoperable with FAIR consumers.
- **Multivalued slots for multi-source data.** Some fields (e.g., `county_names`, `citation_request`) are multivalued to support real-world cases (multi-county sewersheds, multi-institution citations).
- **Per-sector validation.** A wastewater sample has different required fields than a clinical sample. Tier rules are per-subclass.

Schema versions are tagged: v4.4 is current. Updates require PR review and migration script generation.

---

## 10. File references and storage model

### 10.1 JACKPOT is a metadata database, not a storage system

A central design commitment: **JACKPOT is a metadata database that knows how to find and run pipelines on data, not a storage system that holds the data.** Storage is something the operator already has — institutional Lustre/GPFS for HPC, a GCS bucket for cloud, MinIO container for local — and JACKPOT references files in place rather than always copying them.

This pattern matters at scale. Petabytes of nanopore reads on an operator's GCS bucket should be queryable and pipeline-targetable by JACKPOT without paying egress to re-copy them.

### 10.2 The file_references model

The schema:

```
samples              sample_files
─────────            ─────────────
sample_id            sample_id (FK)
metadata             role (R1/R2/etc)
                     content_hash         ← logical key (SHA-256)
                     head64k_hash         ← cheap fingerprint
                     tail64k_hash         ← cheap fingerprint
                     size_bytes
                     storage_state        ← enum
                     primary_uri
                     alternate_uris       ← multivalued
                     first_seen_at
                     last_verified_at
                     retention_policy
                     original_uri         ← for MIRRORED
                     staged_for_run_id    ← for STAGED
```

### 10.3 FileStorageState enum

| State | Meaning | Lifecycle owned by |
|---|---|---|
| `EXTERNAL` | URI not under JACKPOT control | Operator / user |
| `MANAGED` | Under JACKPOT storage control | JACKPOT |
| `MIRRORED` | Managed copy backed by external original | JACKPOT (with origin tracking) |
| `STAGED` | Temporary copy for a specific pipeline run; auto-cleaned | JACKPOT |
| `BROKEN` | External file no longer accessible (terminal) | n/a |

### 10.4 Behavioral defaults

- **Ingest defaults to `EXTERNAL`.** Pointing JACKPOT at a file path or URI registers it; no copy occurs.
- **Pipeline outputs default to `MANAGED`.** When a pipeline produces results, JACKPOT owns those.
- **Pipeline inputs stay in their existing state.** Running a pipeline doesn't take ownership of input data.
- **Cheap fingerprint at ingest, full SHA-256 lazily.** Size + first-64KB hash + last-64KB hash for dedup-during-ingest. Full hash queued as a background job.
- **Periodic verification of EXTERNAL files.** A background job re-stats them and updates `last_verified_at`, marking `BROKEN` if missing.
- **Pre-pipeline-launch verification.** Before any pipeline run, verify all input files are accessible. Fail fast, not mid-run.
- **Explicit promotion.** `jackpot files promote --to managed` for users who want JACKPOT to take ownership of a file.

### 10.5 Scenario-specific behavior

| Scenario | Default file storage |
|---|---|
| A — laptop | Files in user project dirs, registered as `EXTERNAL`. MinIO optional; `~/.jackpot/data/` for managed storage. |
| A — single lab on Linux server | Files on lab NAS or shared drive, `EXTERNAL`. Pipelines on local Slurm see the same paths, zero copies. |
| A — multi-server agency | Files on agency datacenter storage or agency cloud bucket, `EXTERNAL`. |
| B — HPC | Files on Lustre/GPFS, `EXTERNAL`. Pipelines on cluster see the same paths, zero copies. JACKPOT does not run its own object storage; uses institutional storage. |
| C — cloud-native | Files in GCS/S3 buckets, `EXTERNAL` referencing the operator's bucket. Pipelines on Batch read in place. |
| Cloud-burst from A | Input file `STAGED` to GCS for the duration of the run, cleaned up after. One copy, lifecycle-managed. |
| SRA-imported | URI scheme `sra://SRR12345`. Zero permanent copies; `fasterq-dump` runs on compute node. |

### 10.6 The MonitoringSite entity

For wastewater and environmental surveillance, JACKPOT introduces a `MonitoringSite` entity that stores persistent site metadata: WWTP name, geographic coordinates, population served, catchment polygon, WWTP capacity, NWSS sewershed ID. Individual `WastewaterSample` records reference the site via foreign key.

This pattern avoids the data integrity hazards of repeated free-text site labels at the same physical location. It also enables federation-friendly site discovery (a federation query "which sites have you sampled?" returns site references, not sample-by-sample location metadata). Detail in `docs/wastewater.md`.

---

## 11. Metadata quality tiers

JACKPOT treats metadata completeness as a first-class, queryable property of each sample. The `quality_status` field on `samples` takes one of three values — **PRELIMINARY**, **ANALYZABLE**, **SUBMITTABLE** — computed by the validator at ingest and recomputed when metadata is updated. The three tiers describe what the sample *is* (how complete its metadata is), distinct from `sharing_level` which describes who can see it.

This design follows three explicit recommendations in the international pathogen genomics governance literature:

**WHO Guiding Principle 3 — High-quality, reproducible data.** The 2022 WHO *Guiding principles for pathogen genome data sharing* acknowledges the operational reality that public health labs work under: *"In emergencies, however, there is a trade-off between the time needed to attain very high-quality data and the ability to share data rapidly. In some cases, it may be appropriate to share lower quality data (clearly marked as 'preliminary/not fully quality controlled' or similar), with the understanding that preliminary data need to be easily identifiable."* JACKPOT's `quality_status` field makes this identification machine-readable rather than relying on submitter convention.

**WHO Attributes 2.6 — Data curation.** The WHO Attributes document for genomic data-sharing platforms describes two acceptable approaches to handling incomplete or preliminary data: filter it out, or *"provide all data annotated with quality control methods and results. The latter would allow users to mask or select data and reuse it according to their needs."* JACKPOT implements the annotate-and-keep approach — incomplete records remain in the system, marked with their tier, available for use cases that can tolerate the completeness level (protocol optimization, tool validation, real-time outbreak signals).

**PHA4GE empirical precedent.** The PHA4GE SARS-CoV-2 contextual data standard (Griffiths et al. 2022) demarcated metadata fields as required, recommended, or optional — a tiered structure that PHA4GE's working group identified as "important in increasing use" of the standard. JACKPOT's three-tier design extends this precedent: PRELIMINARY corresponds to minimum required fields present, ANALYZABLE adds the fields needed for analytical pipelines, SUBMITTABLE adds the fields needed for downstream submission to INSDC, GISAID, or peer platforms.

### 11.1 The three tiers

| Tier | What it requires | What you can do with it |
|---|---|---|
| **PRELIMINARY** | Minimum required fields per sample subclass: `sample_id`, `organism`, `collection_date`, `country`, `submitting_lab`, `sample_type`, `surveillance_relevant` (computed). | Browse, discover, attribute. Run protocol-optimization or tool-validation workflows that tolerate incompleteness. Flag for follow-up curation. |
| **ANALYZABLE** | PRELIMINARY + analytically-required fields: `biospec_type`, `sequencing_strategy`, `sequencing_instrument`, `host_species` (for clinical), `concentration_units` (for wastewater), etc. | Run analytical pipelines: variant calling, lineage assignment, AMR profiling. Generate analytical datasets. |
| **SUBMITTABLE** | ANALYZABLE + submission-required fields: `collection_method`, `host_age_bin`, `host_sex`, `clinical_outcome` (where applicable), full provenance chain. | Submit to NCBI/GISAID/NWSS. Cite in publications. Include in formal surveillance reports. |

Tier transitions are recomputed automatically when metadata is updated. A sample can move PRELIMINARY → ANALYZABLE → SUBMITTABLE over its lifecycle as the submitting lab enriches the metadata; it can also move backward if a curation review identifies a problem, though backward transitions trigger a notification to the data submitter.

The practical consequence: a researcher uploads a partially-known sample immediately (PRELIMINARY), runs analytical pipelines as soon as the necessary fields are in (ANALYZABLE), and submits to external repositories once curation is complete (SUBMITTABLE) — all without re-creating the record. Metadata is always improving rather than gated behind a binary draft/published threshold.

### 11.2 Sharing levels — orthogonal to quality tier

The `sharing_level` field is a separate property that describes who can see a sample:

| Sharing level | Who can see it |
|---|---|
| `PRIVATE` | Only the submitting user and the user's lab |
| `LAB` | All members of the submitting lab |
| `DISCOVERABLE` | All authenticated users in the org can see a *safe subset* of the metadata (organism, collection date, country/state, source type, sector, quality status) — enough to know the sample exists; full metadata and files require a sample access request through the access control flow |
| `PUBLIC` | All users including external/unauthenticated |

A sample can be PRELIMINARY + PRIVATE (lab just uploaded it, still fixing metadata) or SUBMITTABLE + PUBLIC (fully curated, openly accessible) or any combination. Tier and sharing are orthogonal.

### 11.3 Access permission cascade

The `can_access_sample(user, sample)` function applies a cascade:

1. If sample is `PUBLIC`, return True
2. If sample is `DISCOVERABLE` and user is authenticated, return True for the safe subset, False for full data without an approved access request
3. If sample is `LAB`, return True if user is in the submitting lab
4. If sample is `PRIVATE`, return True only for the submitting user

This cascade is implemented in `guards.py` and enforced in every API endpoint that returns sample data.

### 11.4 Org profiles

Per-org profiles can override default tier requirements:

- A clinical org may require additional fields (clinical outcome, hospital admission status) at the SUBMITTABLE tier
- A wastewater org may require additional fields (flow rate, sampling method) at the ANALYZABLE tier
- A research org may relax some normally-required fields for archival data without external submission

Org profiles are configured by Org Admins via the policy UI. The default profile (no overrides) is suitable for most operators.

---

## 12. Data governance and access control

### 12.1 Access request lifecycle

When a user wants access to a `DISCOVERABLE` sample beyond the safe subset:

1. User submits an access request specifying: which samples, requested fields, purpose, requested duration, attestation of usage policies
2. The submitting lab's Lab Director receives a notification
3. Lab Director approves, denies, or asks for additional information
4. If approved, an access grant is created with: expiration date, granted fields scope, purpose-of-use record
5. The grant is logged in audit_log and visible to both parties
6. When the grant expires, access automatically reverts

### 12.2 Dataset promotion lifecycle

Datasets (collections of samples for analytical or submission purposes) progress through tiers:

- `PRIVATE` — only the dataset creator
- `LAB` — shared with the lab
- `DISCOVERABLE` — visible to org with safe subset
- `PUBLIC` — fully public

Each transition requires explicit action by the dataset owner (or an Admin), and triggers re-validation that all member samples have at least the matching `sharing_level`.

### 12.3 Org-level policy fields

The `organizations` table includes governance policy fields:

- `default_sample_sharing_level` — what new samples default to in this org
- `default_dataset_tier` — what new datasets default to
- `requires_pi_approval_for_public_promotion` — whether Lab Director must approve before a sample becomes PUBLIC
- `requires_governance_board_review` — for `surveillance_relevant` TRUE → FALSE demotions
- `data_residency_jurisdiction` — for sovereignty enforcement (see §22)
- `consent_revocation_propagation` — whether revoked consent triggers federation peer notification
- `audit_retention_days` — how long audit logs are retained

---

## 13. Data lifecycle — scrubbing and deletion

### 13.1 Scrubbing — genomic and metadata PII gates at ingest

JACKPOT implements two PII protection gates at ingest, applied before any sample's data is permanently stored:

**Genomic PII gate.** The NCBI SRA Human Scrubber (HRRT) removes human reads from raw FASTQ files. JACKPOT runs HRRT as a Nextflow pipeline (`nf/ingest_scrubber.nf`) over a six-state lifecycle: `PENDING / IN_PROGRESS / COMPLETE / FAILED / SKIPPED / PENDING_APPROVAL`. The scrubber is concurrency-controlled (default `SCRUBBER_MAX_CONCURRENT=10` to manage cluster load). FASTA-only and SRA-import ingests automatically skip the scrubber (no human reads possible).

This implements WHO Principle 3's directive that *"human genomic data that may inadvertently be included in raw reads should be removed before submission to or release of the sequence on public databases."* No other pathogen genomic data-sharing platform in the surveyed landscape ships an integrated human read removal step.

**Skip governance.** When the scrubber would take longer than 48 hours, governance review is required. The 48-hour threshold protects against the case where a single very-large sample blocks the entire ingest queue.

**Metadata PII gate.** The GCP Cloud DLP scanner (`backend/backend/dlp_scanner.py`) runs on free-text metadata fields and blocks samples containing PII/PHI before storage. Standard `FIELD_EXCEPTIONS` allow known-good PII (e.g., `pi_name` is a researcher name, not patient PII). The scanner is disabled (`DLP_ENABLED=false`) for local development to avoid the GCP Cloud DLP API dependency. In production deployments, DLP is on by default.

### 13.2 Staged deletion lifecycle

Sample deletion is staged, not immediate:

1. User requests sample deletion (via UI or API)
2. Sample's `deletion_status` is set to `MARKED_FOR_DELETION`, with `marked_at` timestamp
3. The sample becomes invisible in queries (UI filters it out by default)
4. After the org's `deletion_grace_period` (default 7 days), a vacuum background job:
   - Deletes object storage files (the file_reference rows remain with `storage_state=BROKEN`)
   - Scrubs JSONB metadata extensions
   - Audit log entry recorded
   - Sample row tombstoned (kept for referential integrity but with PII removed)
5. After `audit_retention_days`, the tombstone row is purged

This pattern allows reversal during the grace period (e.g., if deletion was a mistake), preserves audit history, and ensures genuine data destruction for sovereignty and compliance.

---

## 14. Ingest methods

### 14.1 Researchers enter samples, not files

The core ingest design principle: researchers describe samples through metadata; the files come along as part of that description. The platform's primary unit is the `sample`, not the `file`.

### 14.2 File detection and pairing

The `file_detector.py` module (the sole owner of file-type logic per Critical Rule 20) handles:

- Paired-end FASTQ detection (R1/R2 matching)
- Multi-lane merging (when one sample produces multiple lane FASTQs)
- Nanopore chunk detection (multiple barcode files for one sample)
- Content sniffing for file type (reads 1-16 bytes to detect actual format, rejects FASTQ uploaded with `.fasta` extension if content is actually FASTA)
- gzip/BGZF transparent handling

This is one place in the codebase where file-type logic lives. Other modules call `file_detector.validate_file_type(...)`, never re-implement.

### 14.3 The six ingest methods

| Method | Use case | Path |
|---|---|---|
| GUI drag-and-drop | Small samples, occasional uploads | `POST /api/v1/ingest/upload` with multipart form data |
| CSV batch + rsync/rclone | Bulk laboratory submission | `POST /api/v1/ingest/csv` with CSV manifest; files copied separately via rsync/rclone with signed credentials |
| Presigned URL | Direct browser-to-storage for medium files | `POST /api/v1/ingest/presign` returns S3 URL; client uploads directly; client confirms with `POST /api/v1/ingest/confirm` |
| URI registration | Cloud-native, no copy | `POST /api/v1/ingest/register` with `gs://`, `s3://`, or `https://` URI; zero copy |
| SRA accession | External database pull | `POST /api/v1/ingest/sra` with SRR accession; `fasterq-dump` runs on compute |
| Globus deposit-first | Bulk academic transfers | Globus collection registered; metadata catalog populated; samples reference Globus URIs |

Different operators use different methods. A laptop deployment for an individual researcher mostly uses GUI drag-and-drop. An agency with many submitting labs mostly uses CSV batch. A multi-institution research consortium might use Globus.

### 14.4 DataHarmonizer tiered templates

For batch CSV ingest, JACKPOT generates DataHarmonizer-compatible templates per source-type with three completeness levels:

- T1 template: PRELIMINARY-required fields only
- T2 template: ANALYZABLE-required fields
- T3 template: SUBMITTABLE-required fields

Submitters use the appropriate template for their workflow. DataHarmonizer (browser-based, offline-capable) validates the CSV against the template before upload, catching errors at entry time rather than at server-side ingest.

### 14.5 The ingest pipeline sequence

Every ingest method follows the same downstream sequence (see `docs/architecture_diagrams.html` SVG 2 for visualization):

1. **Lab upload** via one of the six methods
2. **`file_detector.py`** classifies file types, pairs paired-end reads, merges multi-lane
3. **`validate_sample()`** runs schema validation, computes `quality_status` (PRELIMINARY / ANALYZABLE / SUBMITTABLE)
4. **`compute_epiweeks()`** and **`compute_surveillance_relevant()`** populate derived fields
5. **Single database transaction** containing INSERT INTO samples, audit_log entry, and staging-file write. If audit write fails, sample INSERT rolls back.
6. **`201 Created`** response with `{sample_id, quality_status, surveillance_relevant, jackpot_uri}`
7. **PII gates run asynchronously** (scrubber for genomic, DLP for metadata) and block downstream processing if they fail
8. **Pipeline auto-trigger** for samples that qualify for default pipelines (e.g., a SARS-CoV-2 sample auto-runs viralrecon if the org's policy enables it)

---

## 15. Dataset model

### 15.1 Reference-based, never copy FASTQs

A dataset is a curated collection of samples for analytical or submission purposes. The schema:

```
datasets              dataset_samples
─────────             ───────────────
dataset_id            dataset_id (FK)
name                  sample_id (FK)
tier                  added_at
description           added_by
created_by            notes
created_at
updated_at
```

Datasets reference samples by ID. They never copy sample data. Promoting a sample to a higher sharing tier does not duplicate it in any dataset — the dataset's view of the sample is updated automatically.

### 15.2 Three dataset tiers

Matching the sample sharing levels:

- `PRIVATE` — only the dataset creator
- `LAB` — shared with the lab
- `DISCOVERABLE` — visible to org, with sample-level safe subset
- `PUBLIC` — fully public

### 15.3 Dataset promotion workflow

A dataset can be promoted (e.g., PRIVATE → LAB → DISCOVERABLE → PUBLIC) by the creator or by an Admin. Each promotion:

- Validates that all member samples have at least the matching `sharing_level`
- Triggers an audit log entry
- Notifies the relevant authority (Lab Director for LAB → DISCOVERABLE, Org Admin for DISCOVERABLE → PUBLIC if `requires_pi_approval_for_public_promotion` is true)
- Updates the dataset's effective access for downstream consumers

---

## 16. Pipeline architecture

### 16.1 Pipeline zoo and BYOP

JACKPOT supports a curated pipeline catalog plus "bring your own pipeline" (BYOP) for advanced operators:

**Curated pipeline zoo** — pipelines maintained by JACKPOT for common workflows:
- `viralrecon` (SARS-CoV-2, influenza, RSV variants)
- `MIRA-NF` (multi-flu/coronavirus IRMA-based)
- `PHoeNIx` (AMR/HAI bacterial typing)
- `MycoSNP-NF` (fungal, especially *Candida auris*)
- `Aquascope` (wastewater SARS-CoV-2 with NWSS alignment)
- `TOSTADAS` (NCBI submission preparation)
- `ingest_scrubber` (HRRT human read removal)

**BYOP** — operators can register Nextflow pipelines via the pipeline catalog API. Pipeline definitions specify: input schema, output schema, container requirements, execution profile constraints. Once registered, BYOP pipelines participate in JACKPOT's launch/status/telemetry machinery identically to zoo pipelines.

### 16.2 Execution profiles as first-class concept

Execution profiles are how JACKPOT decouples pipeline definitions from execution targets. The model:

```
[deployment time]
operator configures one or more execution profiles in jackpot config
  - "local"        : Nextflow on the API server, Docker
  - "slurm-mylab"  : Submit to lab Slurm queue, Apptainer
  - "slurm-univ"   : Submit to university cluster, Apptainer, lab account
  - "gcp-batch"    : Burst to GCP Batch (cloud burst)

[launch time]
user picks a profile when launching a pipeline run
or accepts the per-pipeline default
```

This translates directly to Nextflow's `-profile` flag plus JACKPOT-aware metadata (which Slurm account to charge, which scratch directory, which container engine, which work directory).

Per-scenario install-time defaults:

| Scenario | Default profile |
|---|---|
| A (commodity) | `local` |
| B (HPC) | Slurm (cluster-specific, configured at init) |
| C (cloud) | Cloud-native (Batch / Cloud Run / Kubernetes Jobs, configured at init) |
| D (CI) | `local` |

All scenarios support multiple profiles. A Scenario A laptop can submit jobs to a Slurm cluster by configuring a Slurm profile post-install via `jackpot profiles add slurm-mylab ...`. A Scenario C cloud deployment can fall back to local execution for small jobs by adding a `local` profile.

Implementation pieces:

- `execution_profiles` table — keyed by name, with executor type, container engine, work directory, account/partition/QoS for Slurm, project/region for cloud Batch, etc.
- `pipeline_default_profile` table — per-pipeline default profile selection (e.g., quick QC pipelines default to `local`, large variant-calling pipelines default to the cluster)
- `nextflow.config` generation at launch time — when a run is launched, the pipeline launcher generates a profile-specific `nextflow.config` snippet from a template using the chosen profile's parameters
- `JACKPOT_WORK_DIR` as a first-class peer to object storage — points at a shared filesystem path; configured per-profile

Cost surfacing for cloud profiles: before launching a run on `gcp-batch` or similar, JACKPOT computes an estimated cost based on the pipeline's typical resource usage and the operator's configured rate. The launch UI shows: "this run will use approximately $X in compute." This is a real product feature; surprise cloud bills kill platform adoption.

### 16.3 Nextflow execution model

JACKPOT integrates Nextflow as the pipeline orchestrator. The execution sequence:

1. User triggers a pipeline run via UI or API
2. JACKPOT validates that the sample(s) have appropriate `quality_status` for the pipeline's requirements
3. JACKPOT verifies all input files are accessible (per `file_references` state)
4. The pipeline launcher generates a `nextflow.config` from the chosen execution profile
5. Nextflow runs (in-process for `local`, submitted to the cluster for `slurm`, etc.)
6. Nextflow's weblog sends progress events to JACKPOT's `/api/v1/pipelines/weblog` endpoint
7. JACKPOT records pipeline state transitions in `pipeline_runs` and telemetry in `pipeline_telemetry`
8. On completion, the pipeline result loader parses output files and writes typed result records to `pipeline_results`

The weblog receiver follows a never-raises pattern — it always returns 200, even on internal error, to avoid blocking Nextflow on JACKPOT-side issues. Internal errors are logged and surface in the operations UI.

### 16.4 Pipeline telemetry tables

Telemetry captures the full lifecycle of every pipeline run:

- `pipeline_runs` — top-level run record (sample(s), pipeline, profile, status, start/end times)
- `pipeline_telemetry` — per-task metrics (cpu time, memory peak, retry count, cost estimate)
- `pipeline_results` — typed result records per pipeline type (one schema per pipeline)

The `pipeline_results` table is immutable and append-only. Reprocessing creates a new row; the original is never overwritten.

### 16.5 Pipeline result storage

Pipeline results follow per-pipeline typed schemas. Examples:

- `viralrecon` result: `consensus_sequence_url`, `n_reads`, `n_mapped_reads`, `pango_lineage`, `nextstrain_clade`, `coverage_mean`, `coverage_median`
- `PHoeNIx` result: `mlst_scheme`, `mlst_st`, `amr_genes` (multivalued), `virulence_genes` (multivalued), `species_id`
- `Aquascope` result: `variant_proportions` (JSONB), `coverage_target`, `quality_pass`

Result schemas are vendored into the backend (`backend/pipeline_schemas.py`) — no `sys.path` hack to import from the `pipelines/` directory, and the `Dockerfile.api` does not need to `COPY pipelines/` (Rule 54). This pattern was established when JACKPOT moved from external-submodule pipeline definitions to monorepo pipelines.

---

## 17. Workspace — JupyterHub and SDK

### 17.1 JupyterHub on GKE / HPC

For Scenarios B and C (and optionally for multi-user Scenario A deployments), JACKPOT deploys JupyterHub as a researcher workspace:

- Hub deployed via Helm chart
- Three pre-configured profiles: lightweight (CPU only), GPU-enabled, large-memory
- Idle culling: automatically stops inactive notebook servers after a configurable timeout (default 1 hour)
- Context injection: JupyterHub auth provides the JACKPOT user's API token to the notebook environment, so notebooks can use `jackpot-sdk` without re-authenticating
- Storage: per-user persistent volume + read-only mount of org/lab shared data

JupyterHub is deferred for single-user Scenario A deployments where it adds complexity without proportional benefit.

### 17.2 jackpot-sdk (Python)

The `jackpot-sdk` package provides Python access to JACKPOT:

```python
from jackpot_sdk import JackpotClient

client = JackpotClient(base_url="http://localhost:8000", api_token="...")

# List samples
samples = client.samples.list(quality_status="ANALYZABLE")

# Get sample details
sample = client.samples.get("EX-12345")

# Launch a pipeline
run = client.pipelines.launch(
    pipeline="viralrecon",
    samples=["EX-12345", "EX-12346"],
    profile="slurm-mylab",
)

# Stream results
for result in client.pipelines.results(run.run_id):
    print(result.consensus_sequence_url)
```

The SDK is `jackpot-sdk` on PyPI; users install it independently of the platform install (`pip install jackpot-sdk`). It is also bundled into the JupyterHub notebook image so users can `import jackpot_sdk` without separate install.

### 17.3 jackpot-cli (Year 1, later)

A dedicated CLI for users (separate from the `jackpot` install/operations CLI) is on the roadmap. It would provide:

- `jackpot samples list / get / submit`
- `jackpot pipelines launch / status / results`
- `jackpot datasets create / promote / submit`
- `jackpot search` for cross-cutting queries

This is Year 1 work; for now, the SDK serves these use cases.

---

## 18. Standards and FAIR compliance

### 18.1 Standards inventory

JACKPOT implements or interoperates with:

- **LinkML v4.4** — schema modeling
- **NCBI Taxonomy** — pathogen and host species
- **ENVO** — environmental features
- **GenEpiO** — epidemiological context
- **UBERON / OBI** — biological samples
- **SNOMED-CT** — clinical terms (where applicable)
- **ISO 3166-2** — geographic locations
- **PHIN VADS** — surveillance-specific vocabularies (snapshot before Nov 30, 2026 sunset)
- **NWSS** — wastewater surveillance reporting
- **PHA4GE** — pathogen genomics contextual data standards
- **GA4GH** — federation interoperability (Beacon v2, `/service-info`, DRS URIs)
- **DUO** — data use ontology for consent tags
- **PHES-ODM** — pathogen and health emergency surveillance open data model (EU/Canadian)
- **MIxS** — minimum information about a metagenomic sample (informs schema design)

### 18.2 FAIR compliance status and roadmap

| FAIR | Status | Notes |
|---|---|---|
| **F**indable | ✅ Met | Persistent IDs for samples and datasets; `/service-info` endpoint; DRS-style URI scheme; Beacon v2 endpoint planned (Year 2+) |
| **A**ccessible | ✅ Met | Open API; AGPL-3.0 platform; data access via API token; signed URLs for direct download |
| **I**nteroperable | ✅ Met (with continuing work) | LinkML schema with ontology anchoring; controlled vocabularies; PHA4GE alignment; PHES-ODM bridge (in progress) |
| **R**eusable | ✅ Met | License metadata per sample (`data_use_terms`); DUO tags; citation requests on every sample |

### 18.3 WHO 11 Attributes alignment

The WHO Attributes document (*Attributes and principles of genomic data-sharing platforms supporting surveillance of pathogens with epidemic and pandemic potential*) defines 11 attributes for PGDSPs. JACKPOT's status:

| # | Attribute | JACKPOT status | Evidence |
|---|---|---|---|
| 1 | Capacity development | ✅ Met | Operator-agnostic by design; `jackpot init` allows small labs to deploy; four deployment scenarios from laptop to cloud |
| 2 | Collaboration and cooperation | 🔶 Partial | Open-source AGPL-3.0 invites contributions; three-level federation architecture; governance/board docs in progress |
| 3 | High-quality, reproducible data | ✅ Met | Tier-aware validation (PRELIMINARY/ANALYZABLE/SUBMITTABLE) marks lower-quality data per WHO guidance; SRA Human Scrubber removes human reads pre-storage per WHO §3; content-sniffing file detection |
| 4 | Defined data scope | ✅ Met | Minimum metadata defined (sample, sequencing, attribution); optional fields for epidemic / One Health context; schema is the source of truth |
| 5 | Submission methods | ✅ Met | Six ingest paths (GUI / CSV+rsync / presigned / URI / SRA / Globus) covering small to bulk to limited-connectivity |
| 6 | Data curation | ✅ Met | Tier-aware validation; explicit annotation rather than filter-out; genomic and metadata PII gates at ingest; submission verification |
| 7 | Attribution and credit | 🔶 Partial | `originating_lab`, `submitting_lab`, `data_generator`, `citation_request` fields in schema; auto-Acknowledgments block at export is in progress |
| 8 | Data sharing tiers | ✅ Met | OPEN/RESTRICTED dual-track in schema; DUO codes; sharing levels (PRIVATE/LAB/DISCOVERABLE/PUBLIC) |
| 9 | Interoperability | ✅ Met | Full ontology anchoring; TOSTADAS NCBI broker; planned LAPIS compatibility; hAMRonization output |
| 10 | Trustworthiness and ease of use | 🔶 Partial | Six low-friction ingest paths; content-sniffing prevents silent failure; trust portal in progress |
| 11 | Transparency | 🔶 Partial | Public technical docs; audit log; governance / board / COI docs in progress |

Matrix summary: 7 Met, 4 Partial, 0 Gap. The four Partials are all on the active roadmap.

---

## 19. External integrations

### 19.1 Sequencing lab registration

External sequencing service providers can be registered as labs within JACKPOT, enabling them to submit samples on behalf of clients. The submission goes through the standard ingest flow with the submitting lab being the sequencing service provider, and `originating_lab` being the client lab.

### 19.2 Globus integration (deposit-first)

For bulk academic transfers (10+ TB), JACKPOT supports Globus collections as the storage backend. The workflow:

1. Client deposits files into the agreed-upon Globus collection
2. Client submits a metadata-only manifest to JACKPOT
3. JACKPOT registers samples with `file_references` pointing at the Globus collection
4. Pipelines that need the files retrieve them via Globus during execution

### 19.3 BaseSpace integration (three-stage transition)

For labs using Illumina BaseSpace:

- Stage 1 (in progress): manual export from BaseSpace, ingest via CSV batch
- Stage 2: BaseSpace App that automates the export
- Stage 3: Direct BaseSpace API integration with `POST /api/v1/ingest/basespace`

### 19.4 External database search

For users interested in samples that may exist in external databases (NCBI Pathogen Detection, GenBank, GISAID), JACKPOT provides a federated search API that queries external sources and returns hits with provenance.

### 19.5 NCBI submission (TOSTADAS)

NCBI/GenBank submission uses the TOSTADAS pipeline:

- Validates metadata against NCBI BioSample requirements
- Generates submission XML
- Submits via NCBI submission portal
- Tracks accession numbers in `submissions` table

### 19.6 GISAID export

GISAID EpiCoV/EpiFlu format export is implemented. The user selects samples, JACKPOT generates the export package, and the user manually uploads to GISAID (GISAID's API is not publicly available for automated submission).

---

## 20. Federation architecture

JACKPOT's federation architecture enables multi-deployment collaboration: cross-deployment queries, federated learning rounds, and cryptographic federated computation. The full design lives in `docs/federation.md`; this section provides the architectural summary.

### 20.1 Three federation levels (L1 / L2 / L3)

JACKPOT supports three federation patterns at increasing complexity:

- **L1 — Query federation.** A querying deployment fans a query across peer deployments; each peer responds with results (or a count, or a privacy-preserving aggregate); the querying deployment aggregates. Supports cryptWWDB's encrypted-query pattern with added policy-checker and `data_source_lab` role.
- **L2 — Hub coordination.** A coordinator (hub) distributes computation across participants. The original use case is one-shot push (e.g., NWSS upstream reporting). L2 has been extended to support multi-round federated learning, where the hub orchestrates rounds of model parameter distribution, local training, and aggregation.
- **L3 — Bidirectional sharing.** Peer-to-peer cross-deployment sample access with policy enforcement. Year 2 work.

### 20.2 Bilateral mesh trust model

Federation in v1 uses bilateral mesh, not named federation groups:

- A `federated_instances` table holds peer records (URL, role, API key reference, policy fields)
- Trust is established out-of-band: operators exchange URLs and credentials by email/Signal/in-person
- Each operator runs `jackpot peers add --base-url X --api-key Y` to write a peer record
- Federation membership is emergent from peer relationships, not declared via a "federation" object
- `federation_tags` (multivalued) allow soft grouping: "all peers tagged `pnw_wastewater_consortium`" can be addressed as a logical federation without requiring a `federations` table

### 20.3 Federation services always installed

Per the `jackpot init` design, federation services are present in every deployment regardless of whether federation is actively in use:

- The federation router (`backend/backend/routers/federation.py`) is in the API surface
- `federated_instances`, `federation_jobs`, and `federation_tags` tables exist
- AIS federation hooks are installed (with `NullAISFederationHooks` as the default Track 1 implementation)
- L2 round-orchestration scaffolding is present
- The cryptWWDB policy checker module is installed

A deployment that never adds a peer simply has these services dormant. A deployment that later adds peers activates federation without re-installation. See §6.1 — federation is not asked at `jackpot init` time.

### 20.4 Federated learning workload

JACKPOT supports FL as a first-class workload via the L2 multi-round pattern:

- **FL substrate: NVIDIA FLARE.** Selected as the primary FL substrate based on its production maturity, built-in privacy primitives (DP, HE, secure aggregation, PSI), healthcare deployment track record, and the unified Flower+PySyft-equivalent stack it provides in a single framework.
- **ML framework: PyTorch.** Primary. scikit-learn for classical ML.
- **Model interchange: ONNX.** For Hugging Face imports and cross-system deployment.
- **Round orchestration.** `federation_jobs` tracks multi-round federated computations: rounds, participants, status, current model checkpoint reference. The hub coordinates rounds; participants execute local training; the hub aggregates.
- **Per-round cohort selection.** An FL round can target a subset of peers (e.g., 8 of 30 federated peers participate in this round); the cohort is captured per-round.
- **Secure aggregation.** FLARE's built-in secure aggregation filters apply at the hub during model update collection.

### 20.5 cryptWWDB workload (sibling to FL, not a subtype)

cryptWWDB — encrypted wastewater federated computation per Driver et al. 2024 — is supported as a sibling workload to FL, using different infrastructure:

- **HE library: TenSEAL or OpenFHE** (separate from FLARE). TenSEAL is what Driver et al. used; OpenFHE is a more recent alternative.
- **Three roles** in cryptWWDB: querying municipality, data-source municipality, and `data_source_lab` (a fourth federation role added for this workload).
- **Policy checker module** sits between the federation router and the HE compute backend, enforcing access controls and detecting repeated queries.
- **Encrypted operand routing.** The federation router handles opaque ciphertext payloads, routing them between municipalities and the Lab without parsing or filtering contents.

FL and cryptWWDB share JACKPOT's federation hook surface but use different infrastructure stacks. They are not parent-child; they are siblings, both supported as privacy-preserving federation workloads.

---

## 21. Open-source adoptions

JACKPOT adopts external open-source components where they fill capability gaps. Adoption decisions are based on: capability match, license compatibility with AGPL-3.0, maintenance status, and ecosystem alignment.

### 21.1 Prioritized adoption list

| Item | Source | License | Status | Justification |
|---|---|---|---|---|
| **seqsender** | CDC | Apache-2.0 | Adopt — Phase P0i | NCBI/GISAID submission with real working code |
| **MIRA-NF pipeline** | CDC | Apache-2.0 | Adopt — Phase P0i | Flu/SARS/RSV via IRMA — major use case |
| **PHoeNIx pipeline** | CDC | Apache-2.0 | Adopt — Phase P0i | AMR/HAI bacteria — high-value for state PHL deployments |
| **MycoSNP-NF pipeline** | CDC | Apache-2.0 | Adopt — Phase P0m | Fungal (*C. auris*) — emerging surveillance need |
| **Aquascope pipeline** | CDC | Apache-2.0 | Adopt — Phase P0m | Wastewater SARS-CoV-2 with NWSS alignment |
| **Tostadas pipeline** | CDC | Apache-2.0 | Adopt — Phase P0m | NCBI/GISAID submission via Liftoff/VADR/Bakta |
| **MicrobeTrace** | CDC | Apache-2.0 | Adopt — Phase P0m | Browser-based outbreak visualization (iframe embed) |
| **PHIN VADS vocabularies** | CDC | Data | **Phase P0i — urgent** | **Sunsets November 30, 2026; pull vocabularies as schema reference data before then** |
| **PHES-ODM data model** | Big-Life-Lab | MIT | Adopt — Phase P0m | Wastewater alignment for EU/Canadian deployments |
| **GA4GH `/service-info`** | GA4GH | Apache-2.0 spec | Adopt — Phase P0i | Cheapest federation win — makes JACKPOT discoverable |
| **DRS-style URI conventions** | GA4GH | Apache-2.0 spec | Adopt — Phase P0i | Already 80% there; formalize as standard |
| **Sapporo-WES spike** | DDBJ | Apache-2.0 | Evaluate — Phase P0m (2-week spike) | Alternative to bespoke pipeline orchestration |
| **Wave (self-hosted)** | Seqera | AGPL-3.0 | Adopt — Phase P0l | Container provisioning for pipelines; AGPL-on-AGPL clean |
| **MultiQC** | Seqera | GPL-3.0 | Already in nf-core | Already used transitively |
| **Crypt4GH support** | GA4GH | Apache-2.0 spec | Year 2+ | For scenarios with sensitive data at rest |
| **Beacon v2 endpoint** | GA4GH | Apache-2.0 spec | Year 2+ | For federation scenarios |
| **TESSy AMR record-format export** | ECDC | Spec | Year 2+ | EU bridge for European deployments |
| **NCBI SRA Human Scrubber (HRRT)** | NCBI | Public domain | Shipped | Already integrated as `ingest_scrubber.nf` |

### 21.2 PHIN VADS — urgency note

PHIN VADS (Public Health Information Network Vocabulary Access and Distribution System) sunsets November 30, 2026. JACKPOT must pull the vocabularies into the schema submodule as static reference data **before that date**. This is on the critical path for any deployments that rely on PHIN VADS-anchored surveillance terms.

---

## 22. Data sovereignty and governance

### 22.1 Sovereignty as runtime policy

JACKPOT supports CARE-aligned governance, residency enforcement, revocable consent, and other sovereignty enforcement primitives — but as **runtime policy configurations**, not as a separate deployment scenario.

This is a deliberate architectural choice. A tribal college running JACKPOT for genomics coursework picks Scenario A and doesn't configure sovereignty policies. A Tribal Nation health department running JACKPOT under CARE Principles also picks Scenario A and configures sovereignty policies post-install. The platform code is the same; the runtime configuration differs.

The same pattern applies to other governance contexts: EU EHDS compliance, US healthcare HIPAA-strict, and similar regulatory regimes. Each can be expressed as a runtime policy configuration applied to any scenario.

### 22.2 Available capabilities

The following capabilities are present in the platform and configurable for sovereignty-aware deployments:

**Data residency enforcement.** Operators configure residency rules (e.g., "samples from this lab cannot leave this jurisdiction"). The federation router enforces residency at every outbound query; the storage layer enforces residency at file replication.

**Revocable consent.** Samples can carry consent metadata (`data_use_terms`, `consent_status`) that supports revocation. When consent is revoked, JACKPOT can propagate the revocation to federation peers as a deletion request with a signed receipt expected back.

**No-auto-publish defaults.** Per-org configuration to require explicit per-sample approval before any sample's `sharing_level` can advance to PUBLIC. Combined with the `requires_pi_approval_for_public_promotion` org policy field.

**Federation policy restrictions.** Per-peer policy fields control what data flows where: minimum sharing level for federation, allowed query types, allowed source-types, allowed sectors.

**Audit visibility.** The audit log captures every access, every state change, every federation interaction. Sovereignty-aware deployments can expose this audit to the data-originating authority (the Tribe, the regulated entity, etc.) via a dedicated audit portal.

**Pre-publish review checklist.** Before any sample's `sharing_level` advances to PUBLIC, an optional reviewer checklist can be configured (e.g., CARE-Principle confirmation, governance board approval).

**Per-org policy enablement.** Each capability is independently configurable per-org via the policy UI or `jackpot policy enable ...` CLI. Policies can be combined.

### 22.3 Configuration mechanism

For v1, sovereignty policies are configured via concrete admin actions:

```bash
jackpot policy enable residency --org <org_id> --jurisdiction <jurisdiction>
jackpot policy enable revocable-consent --org <org_id>
jackpot policy enable no-auto-publish --org <org_id>
jackpot policy enable audit-portal --org <org_id> --audience <data_authority>
```

Each policy enables a specific enforcement primitive. The Org Admin (or Platform Admin in multi-org deployments) is the authority for policy enablement.

### 22.4 Future direction — named policy profiles

A longer-term direction is to support named policy profiles that bundle defaults and enforcement primitives:

```bash
jackpot policy apply --profile care-indigenous
jackpot policy apply --profile ehds-eu
jackpot policy apply --profile hipaa-strict
```

Each profile would be a named bundle of policies appropriate for a specific governance regime. This is post-v1 work; for now, individual policy enablement covers the same ground at finer granularity.

### 22.5 Implementation status

Sovereignty enforcement primitives are tracked in the backlog as `B-CARE-3`, `B-CARE-4`, `B-CARE-5`, and related items. Implementation status varies per primitive:

- Audit log: shipped
- Per-org policy fields in schema: shipped
- Residency enforcement: in design (B-CARE-3)
- Revocable consent propagation: in design (B-CARE-4)
- Pre-publish review checklist: in design (B-CARE-5)
- Audit portal: planned

See `docs/todo.md` for current status.

### 22.6 Authority model

For v1, the authority for sovereignty configuration is the Org Admin (or Platform Admin in multi-org deployments). Collective decision-making patterns — where a council or governance body has approval rights that override the operator — are out of scope for v1 and may be a future enhancement if a real coalition partnership requires them.

JACKPOT enforces decisions made by configured authorities. It does not model the authority structure itself; that lives in operator-side governance documents and operator-side review processes.

### 22.7 Transport as runtime policy

JACKPOT supports network-denied and store-and-forward operation — intermittent connectivity, opportunistic satellite backhaul, and fully air-gapped sites — but as a **runtime transport-policy configuration**, not as a separate deployment scenario. This is the same architectural pattern as sovereignty (§22.1): a rural clinic and a well-connected reference lab pick the same scenario (A, B, or C) and install the same platform code; they differ only in the transport configured per federation peer. §2.3 commits the platform to operating across the full connectivity range; this subsection describes the mechanism that delivers on that commitment.

The unit of transport policy is the **peer**, not the deployment. A single deployment routinely reaches different peers by different means: HTTPS to a regional hub while a link is up, signed sneakernet bundles to a sister clinic across a valley with no shared network. Transport therefore lives on each `federated_instances` row, alongside the existing role and policy fields (§20.2), rather than as a global instance setting.

**Available transports.** The `transport_type` column on `federated_instances` selects how this instance reaches a given peer:

- **HTTPS** (default) — synchronous request/response over TCP. The only transport that supports L1 live query federation (§20.1); a peer reachable only by store-and-forward cannot answer a live fan-out and is queried instead against the last synced snapshot.
- **DTN** — delay-tolerant networking via the IETF Bundle Protocol (RFC 9171). Store-and-forward; supports L2 push and L3 pull with bundled payloads, not live query. Experimental.
- **SNEAKERNET** — manual courier of signed bundles on physical media. Store-and-forward with unbounded latency; always available as a fallback and as the disaster-recovery backstop when no network path exists. Never auto-selected.
- **LORA** — low-bandwidth Meshtastic/LoRa mesh for alert-class payloads only (case detections, sample-status changes), not full sample transfer. Experimental.

`transport_type` is enforced by a TEXT + CHECK constraint rather than a PostgreSQL ENUM. The transport value set is expected to grow as new radios and protocols are adopted, and a CHECK constraint admits new values through a transactional constraint swap, unlike `ALTER TYPE ... ADD VALUE`. This deliberately diverges from the sibling `role` column, whose federation-role values are a closed set and are modeled as an ENUM (see migration `85d92864ed38`). A companion `transport_config` JSONB column carries transport-specific settings — DTN endpoint identifiers and bundle lifetime, LoRa channel and broker, sneakernet bundle-store path — and is empty for HTTPS peers.

**Relationship to the three federation levels.** Transport policy composes with the federation levels of §20.1 rather than replacing them. The three levels differ in their reachability assumptions, and network-denied mode affects each differently:

- **L1 query** is inherently online. Over any store-and-forward transport it degrades to snapshot search over locally-held synced data; there is no such thing as a sneakernet live query.
- **L2 hub push** is the opportunistic-flush path — the field-deployment case where a site accumulates qualifying de-identified samples and flushes them upstream when a link appears. Its payload references sample bytes; in store-and-forward mode that reference must be a bundled artifact rather than a presigned URL that assumes the source stays reachable.
- **L3 access pull** sources approved sample files from a presigned URL when online, or from an imported signed bundle when couriered.

The delay-tolerant and file-based federation transports named in §2.3 (Google Drive, SyftBox) are the same mechanism viewed from the transport layer: file-based exchange is store-and-forward transport, and the `transport_type`/`transport_config` fields are how a deployment declares it per peer.

**Air-gapped operation.** A deployment can be configured to make no outbound network calls at all, exchanging data exclusively through signed sneakernet bundles. In this mode every peer is SNEAKERNET, live query is unavailable platform-wide, and bundle import is gated by signature verification against the operator's trust store before ingest. This is the strongest form of the transport policy and is appropriate for sites operating under physical-seizure risk or political sensitivity.

**Configuration mechanism.** Transport is set when a peer is registered or updated:

```bash
jackpot peers add --base-url <url> --api-key <ref> --transport https
jackpot peers add --bundle-store <path> --transport sneakernet
jackpot peers set-transport --peer <peer_id> --transport dtn --config <json>
```

The HTTPS default means existing peer records and existing deployments are unaffected: a peer added without a transport flag is an HTTPS peer and behaves exactly as before this capability existed.

**Implementation status.** The schema foundation is shipped: `federated_instances.transport_type` (TEXT + CHECK) and `transport_config` (JSONB), mirrored on the `FederatedInstance` model, in migration `2daeecbe082d`. The store-and-forward transports themselves are staged: HTTPS is the current federation behavior; SNEAKERNET bundle export/import is near-term Track 1 work; DTN and LoRa are experimental Track 2, gated behind environment flags. The per-peer transport dispatch point and the L2 push payload's reference-vs-bundle fork are wired when the L2/L3 federation IO is built (see `docs/todo.md`, Phase 29). Full transport design lives in `docs/federation.md` and the Phase 29 rural / network-denied work.

---


## 23. Testing framework

### 23.1 Setup

Testing infrastructure:

- pytest as the test runner
- Test DB: SQLite in-memory for unit tests; PostgreSQL container for integration tests
- Fixtures: per-module sample data, mock auth, mock GCS/S3
- Coverage: `pytest-cov` with `>85%` threshold gate in CI

### 23.2 Current baseline

As of late April 2026: 549 tests, ~87.56% coverage. Test counts and coverage are updated in `spec.md` after each session.

### 23.3 Test files

Organization:

- `tests/test_routers/*.py` — per-router endpoint tests
- `tests/test_business_logic/*.py` — validator, file detector, computers
- `tests/test_schema/*.py` — schema validation, LinkML generation roundtrip
- `tests/test_pipelines/*.py` — pipeline launcher, weblog receiver, result loader
- `tests/test_federation/*.py` — federation router, peer management
- `tests/integration/*.py` — full-stack tests with Postgres + MinIO

### 23.4 Key testing patterns

- **Each test is in its own DB transaction**, rolled back at the end
- **No network calls in unit tests** — external services are mocked
- **Integration tests run in CI on a dedicated containerized environment**
- **Schema changes require migration tests** that exercise both old and new schemas

### 23.5 Running tests

```bash
# Quick unit-test pass
pytest tests/test_routers tests/test_business_logic

# Full pass with integration
pytest tests/

# Coverage report
pytest --cov=backend --cov-report=term-missing
```

---

## 24. Development roadmap

### 24.1 Current state — Month 1 and Month 2

Month 1 (data layer) completed: schema v4.4 shipped, core routers (orgs/labs/users/samples/datasets/pipelines) in production, six ingest methods implemented, scrubber pipeline integrated, six-role RBAC enforced via guards.  <!-- drift-ok -->

Month 2 (pipelines, workspace, access control) completed: pipeline catalog with viralrecon + MIRA-NF + PHoeNIx, telemetry tables, JupyterHub on GKE (Scenario C), sample_access router for cross-lab access requests, dataset promotion lifecycle.

### 24.2 The May 2026 reframing — sequencing

The May 2026 architectural reframing landed several new commitments that shape Month 3-6 sequencing:

**Phase P0c — Multi-tenancy middleware (Month 3).** Multi-tenancy middleware default-on, per-lab and per-org isolation. Forced by the realization that any scenario can be multi-tenant, not just specific scenarios.

**Phase P0e — `jackpot init` CLI (Month 3).** The CLI itself: interactive init flow with the simplified questions documented in §6, per-scenario bundle generation (Docker Compose vs systemd), `jackpot up/down/logs/ps/doctor`, both Docker and Apptainer runtime support, initial PyPI release.

**Phase P0f — File references redesign (Month 3-4).** Schema and ingest changes for in-place data registration. `file_references` (extending `sample_files`) with content-hash logical key, `FileStorageState` enum, cheap fingerprint + lazy SHA-256 background job, periodic verification, updated ingest API for path/URI-first registration, `jackpot files promote` CLI command, UI surfacing of storage state.

**Phase P0g — Execution profile model (Month 3-4).** Schema and orchestration changes for per-run executor selection. `execution_profiles` table, per-pipeline default profile, `nextflow.config` generation from profiles, `JACKPOT_WORK_DIR` as first-class peer to object storage, profile UI for launching pipelines.

**Phase P0h — Slurm executor support (Month 3-4).** Pairs with P0g. Slurm executor profile templates, Singularity/Apptainer image manifest support in pipeline zoo, weblog reachability documentation for cluster→API, end-to-end smoke test on a real Slurm cluster.

**Phase P0i — Open-source adoptions: pipelines and tools (Month 3-4).** seqsender as pip dependency for NCBI/GISAID submission, MIRA-NF and PHoeNIx pipelines added to zoo, GA4GH `/service-info` endpoint, DRS-style URI scheme formalized, PHIN VADS vocabulary pull (urgent: Nov 30 2026 sunset).

**Phase P0j — Apptainer-first deployment for Scenario B (Month 4).** Building on P0e. systemd-unit-file route, host-installed-Postgres/MinIO option, air-gapped image pre-staging, cluster-side configuration.

**Phase P0k — HPC deployment end-to-end (Month 4-5).** Bringing Scenario B to production-readiness: multi-tenancy middleware live, LDAP/SAML auth path, Slurm cluster integration tested with a real university partner, RC team operator documentation, reference deployment.

**Phase P0l — Scenario C hardening and GCP production (Month 5-6).** Cloud production deployments. Builds on existing Month 3 GCP work: multi-tenant cloud deployments, Cloud DLP integration as scenario-specific feature, cloud-burst executor profile, WIF and IaC cleanup.

**Phase P0m — Remaining pipeline adoptions (Month 4-5, parallel).** MycoSNP-NF, Aquascope, Tostadas, MicrobeTrace, PHES-ODM alignment. Largely parallel to deployment work.

**Federation Stage 1 (Month 4-6, expanded scope).** FL substrate (NVIDIA FLARE) integration, cryptWWDB Stage 1 with `data_source_lab` role and policy checker (B-CWB-FED-1, B-CWB-POLICY-1), FL round orchestration, model artifact store, L1 query federation, L2 hub coordination for FL. Expanded scope (~8-10 weeks vs originally-scoped 4-6) because FL and cryptWWDB both need infrastructure in v1.

**Future — Year 2+.** L3 bidirectional federation, TESSy export, Beacon v2 endpoint, Crypt4GH support, named policy profile framework, collective decision-making sovereignty pattern.

### 24.3 What stays the same

A lot of existing architecture stays — these decisions are right and won't change:

- FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 — solid, scales from laptop to cloud
- PostgreSQL as metadata database — works across all scenarios
- Nextflow as pipeline orchestrator — works with every executor that matters
- 21 routers and their conventions in `spec.md` — all scenario-agnostic
- Critical Rule 20 (`file_detector.py` is sole owner of file type logic)
- Pipeline_results immutable/append-only model
- Weblog receiver never-raises pattern
- Google OAuth + JWT — stays as one auth option among several
- DLP scanner with `DLP_ENABLED=false` bypass for local development
- Six-role RBAC model — extended with multi-tenancy in P0c

### 24.4 What changes in the existing roadmap

A few items in the previous roadmap revise as a consequence of the May 2026 reframing:

1. **GCP production deployment changes framing from "primary deployment target" to "Scenario C hardening."** On-prem (Scenario A and B) is the primary deployment story; cloud is the scaling-up story.
2. **APScheduler remains the right choice** — works in all scenarios from laptop to cloud, no Celery/Redis needed. The "disable with >1 GKE pod" caveat in the architecture diagram becomes a Scenario C concern (leader election at scale).
3. **The pipelines module (was `jackpot-nf` submodule, now `pipelines/`)** stays as a directory in the monorepo. Nextflow doesn't need it as a separate repo.
4. **The schema module stays as a directory in the monorepo.** PHIN VADS vocabularies, PHES-ODM mappings, and HL7 v2.5.1 ELR mappings live as reference data here.
5. **JupyterHub deferral to Month 3 still makes sense**, but JupyterHub is mostly a Scenario B/C feature — laptop and single-lab deployments don't need it. Deploy when Scenario B goes live.
6. **Streamlit researcher pages are scenario-agnostic** and ship in the backend container. They become relatively more important as the laptop-first messaging takes hold.
7. **Backlog item 57 (post-submission warning for edits to NCBI/GISAID-submitted samples)** integrates cleanly with the file_references redesign — both are about lifecycle management after data is "frozen" by external commitment.

---

## 25. Documentation strategy

JACKPOT documentation is structured in tiers to serve different audiences:

**Tier 1 — Strategic and external-facing.** Vision, audience-targeting, why-JACKPOT-exists. Lives in `docs/strategic-vision.md`, `README.md`. For partners, funders, and external collaborators.

**Tier 2 — Operator-facing.** How to install, configure, and operate JACKPOT. Lives in `docs/deployment/*.md`, `docs/runbooks/*.md`. For operators (lab IT, agency platform teams, university RC teams, cloud operations).

**Tier 3 — Architecture and developer-facing.** This document, `docs/spec.md`, `docs/federation.md`, `docs/wastewater.md`, `docs/CLAUDE.md`. For developers, architects, and detailed analysis of design decisions.

**Tier 4 — Archived and historical.** Files in `docs/archived/` preserve content that has been superseded but retains historical value. These files are not active documentation; they exist for traceability.

The documentation roadmap includes consolidating fragmented documents (Cluster work in progress) and eventually deploying a MkDocs Material site once the repository is open-sourced.

---

## 26. Critical Rules quick reference

JACKPOT has accumulated a set of operational rules captured in `docs/CLAUDE.md`. These are the architectural-relevance subset:

| # | Rule | Where it applies |
|---|---|---|
| 20 | `file_detector.py` is the sole owner of file type logic | All ingest paths |
| 52 | Alembic baseline pattern: `db/SCHEMA.sql` is the migration baseline; no bootstrap Job in Helm | Schema migrations |
| 53 | Pydantic-settings multi-form validator pattern (`cors_origins` uses `NoDecode` + `field_validator`) | Backend settings |
| 54 | Vendor pipeline schemas into `backend/pipeline_schemas.py` — no `sys.path` hack, no `COPY pipelines/` in `Dockerfile.api` | Pipeline result loading |
| 55 | Drift-resistant configs: parameterize or remove fallbacks; document baseline SHA | All config templates |
| 65 | Drift-resistant merge scripts: idempotent, structural anchors, pre-flight diff, `.new` files first | Delta application scripts |
| 68 | Session prompt template: Operating Rules, Role, Session Task, Acceptance Criteria, Out of Scope, Closing Steps | All Claude Code session prompts |
| 69 | SNP thresholds for surveillance reportable_organisms: per-pathogen, configurable | `reportable_organisms` table |

See `docs/CLAUDE.md` for the full rule list (currently 54+ rules).

---

## 27. Diagram reference

Visual architecture diagrams are maintained as standalone SVG content in `docs/architecture_diagrams.html`:

- **SVG 1: Platform architecture** — Five-layer architecture diagram showing User Interfaces / FastAPI Backend / Business Logic / Storage / External Integrations with cross-cutting concerns highlighted (transaction isolation, schema-first pipeline, JWT refresh missing, APScheduler scaling concerns).
- **SVG 2: Ingest pipeline data flow** — Six-stage data flow from lab upload through file_detector to validate_sample to compute_epiweeks/compute_surveillance_relevant to the single database transaction containing INSERT + audit + stage_file.

The HTML file is self-contained and renders in any modern browser. Print to PDF for a static export.

Additional diagrams in `docs/diagrams/`:

- Data model entity-relationship diagram (planned)
- Federation level taxonomy diagram (planned)
- Sovereignty policy enablement workflow (planned)

---

## 28. Companion documents and references

### 28.1 In-repo cross-references

- `docs/CLAUDE.md` — Claude Code context, critical rules, project conventions
- `docs/spec.md` — operational spec, current as-built state
- `docs/todo.md` — phase tracking and backlog
- `docs/federation.md` — federation architecture detail
- `docs/wastewater.md` — wastewater surveillance design
- `docs/architecture_diagrams.html` — visual architecture references
- `schema/schema/jackpot_schema.yaml` — schema source of truth

### 28.2 Foundational academic sources

The platform's architectural commitments are anchored in published guidance:

**Pathogen genomic data sharing.**
- WHO. *Guiding principles for pathogen genome data sharing.* Geneva: World Health Organization; 2022.
- WHO. *Attributes and principles of genomic data-sharing platforms supporting surveillance of pathogens with epidemic and pandemic potential.* Geneva: World Health Organization.

**Tiered metadata standards.**
- Griffiths E, et al. *PHA4GE SARS-CoV-2 contextual data standard.* 2022.
- National Academies of Sciences, Engineering, and Medicine. *Accelerating the Use of Pathogen Genomics and Metagenomics in Public Health: Proceedings of a Workshop.* 2025.

**Metagenomic surveillance and nucleic acid observatories.**
- The Nucleic Acid Observatory Consortium. *A Global Nucleic Acid Observatory for Biodefense and Planetary Health.* arXiv:2108.02678. 2021. Cited by: 21.
- Kalantar KL, et al. *IDseq — An open source cloud-based pipeline and analysis service for metagenomic pathogen detection and monitoring.* GigaScience. 2020;9(10). doi:10.1093/gigascience/giaa111. Cited by: 404.

**Federated data ecosystems and genomic federation.**
- Beyvers S, Hochmuth J, Brehm L, Hansen M, Goesmann A, Förster F. *Towards FAIR and federated Data Ecosystems for interdisciplinary Research.* arXiv:2504.20298. 2025. Cited by: 3.
- Thorogood A, Rehm HL, Goodhand P, Page AJH, Joly Y, Baudis M, et al. *International federation of genomic medicine databases using GA4GH standards.* Cell Genomics. 2021;1(2):100032. doi:10.1016/j.xgen.2021.100032.

**Federated learning frameworks and benchmarks.**
- Roth HR, et al. *NVIDIA FLARE: Federated Learning from Simulation to Real-World.* arXiv:2210.13291. 2022.
- Riedel et al. *FL framework comparison.* 2024. (Per the 9-paper review; full citation in `docs/spec.md` deltas.)

**cryptWWDB and privacy-preserving federated computation.**
- Driver et al. *cryptWWDB: A privacy-preserving cross-municipal wastewater database.* 2024.

**Pathogen genomic surveillance — operational context.**
- Struelens et al. *Real-time genomic surveillance for enhanced control of infectious diseases and antimicrobial resistance.* Frontiers in Science. 2024. doi:10.3389/fsci.2024.1298248.
- Djordjevic et al. *AMR resistome profiling from sewage.* Nature Reviews Genetics. 2024.
- Hendriksen et al. *Global sewage AMR metagenomics.* Nature Communications. 2019.
- Munk et al. *Sewage from 101 countries.* Nature Communications. 2022.

### 28.3 Similar frameworks and emerging concepts

Several frameworks share design space with JACKPOT and inform architectural decisions:

- **Pathoplexus** — a recently developed stand-alone primary repository for pathogen genomic data. JACKPOT borrows the governance-as-code pattern (public Statutes, Values, COI, Executive Board).
- **Loculus** — a pathogen genomic data-sharing platform with binary required-or-not metadata fields. JACKPOT's three-tier completeness model differs explicitly to support real-world surveillance workflows.
- **GenSpectrum / LAPIS** — a sequence search and analysis platform. JACKPOT plans LAPIS compatibility for federation interoperability.
- **GA4GH Federated Ecosystem** — the Global Alliance for Genomics and Health's federation standards (Beacon, DRS, WES). JACKPOT implements GA4GH-compatible endpoints.
- **PHA4GE** — community-driven guidance on wastewater and environmental surveillance methods. JACKPOT's wastewater schema is PHA4GE-aligned.
- **Data Mesh and Data Space principles** — architectural patterns for federated data ecosystems that preserve domain-specific control while facilitating integration through standardized interfaces. JACKPOT's three-level federation reflects these principles.

---

*End of architecture document.*
