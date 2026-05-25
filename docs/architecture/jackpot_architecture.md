# JACKPOT — Pathogen Genomics Platform
## Architecture & Developer Reference

**Version:** 5.0
**Working title:** JACKPOT
**Replaces:** jackpot_architecture_v4.md entirely
**Audience:** Glen Otero — personal developer reference and extended CLAUDE.md
**Last updated:** 2026-04-10
**Companion documents:**

- `docs/CLAUDE.md` — Claude Code context file (read at start of every claude session)
- `jackpot_session_summary_and_backlog.md` — design decisions and backlog
- `jackpot_schema.yaml` — LinkML schema source of truth
- `jackpot_implementation` — Detailed dev startup sequence

---

## Table of Contents

1. [What JACKPOT Is](#1-what-jackpot-is)
2. [Architecture Philosophy](#2-architecture-philosophy)
3. [Tech Stack](#3-tech-stack)
4. [Repository Structure and Git](#4-repository-structure-and-git)
5. [Python Environment — uv and pixi](#5-python-environment)
6. [Code Quality — Pre-commit and CI](#6-code-quality)
7. [Permission System](#7-permission-system)
8. [Authentication](#8-authentication)
9. [System Architecture Overview](#9-system-architecture-overview)
10. [Data Model — Tables and Relationships](#10-data-model)
11. [Schema — LinkML v4.4](#11-schema)
12. [Metadata Quality Tiers](#12-metadata-quality-tiers)
13. [Data Governance and Access Control](#13-data-governance-and-access-control)
14. [Data Lifecycle — Scrubbing and Deletion](#14-data-lifecycle)
15. [Ingest Methods](#15-ingest-methods)
16. [Dataset Model](#16-dataset-model)
17. [Pipeline Architecture](#17-pipeline-architecture)
18. [Workspace — JupyterHub and SDK](#18-workspace)
19. [GCP Production Architecture](#19-gcp-production-architecture)
20. [Local Development Environment](#20-local-development-environment)
21. [Standards and FAIR Compliance](#21-standards-and-fair-compliance)
22. [External Integrations](#22-external-integrations)
23. [Federation Architecture](#23-federation-architecture)
24. [Documentation Strategy](#24-documentation-strategy)
25. [Testing Framework](#25-testing-framework)
26. [Development Roadmap](#26-development-roadmap)
27. [APGAP Migration Guide](#27-apgap-migration-guide)
28. [Critical Rules Quick Reference](#28-critical-rules-quick-reference)

---

## 1. What JACKPOT Is

JACKPOT is the migration-compatible successor to APGAP — a pathogen genomics platform
for genomic epidemiology, bioinformatics analysis, and public health research. It shares
APGAP's organizational hierarchy, six roles, Google OAuth flow, analytical dataset
and archive request patterns, but fixes every known APGAP problem.

**What APGAP got wrong and how JACKPOT fixes it:**

| APGAP Problem | JACKPOT Solution |
|---|---|
| EAV anti-pattern — ad-hoc key/value tag system, no type enforcement | LinkML v4.4 schema: typed columns, controlled vocabularies, tier-aware validation |
| Binary DRAFT/PRIMARY gate causing metadata backlog | Three-tier quality system (PRELIMINARY/ANALYZABLE/SUBMITTABLE) — partial records are immediately usable |
| No controlled vocabulary for organisms, biospecs, locations | Enums generated from LinkML schema, enforced at ingest |
| No date normalization — strings in Value table | `DATE` column + `DatePrecisionEnum` (YEAR/MONTH/FULL) |
| No type enforcement — age fields contain "THIRTY FIVE" | `INTEGER`, `FLOAT`, typed enums at column level |
| Duplicate keys possible — no unique constraint per (file, key) | Column-per-field makes this impossible by definition |
| "Required" advisory only — CSVImportHandler logs warning and imports anyway | Tier system enforces completeness at ANALYZABLE and SUBMITTABLE thresholds |
| Only GUI upload | GUI + DataHarmonizer + batch CSV + signed URL + URI + SRA accession + Globus |
| No billing visibility | GCP Billing API per-lab and platform-wide via resourceLabels on Batch jobs |
| No pipeline launcher | Nextflow + GCP Batch + pipeline zoo + BYOP + pipeline telemetry |
| Human reads not scrubbed | SRA-human-scrubber on every ingest path (FASTA and SRA imports auto-skip) |
| No personal API tokens | Personal token model with scoped permissions, 1-year default lifetime |
| No NCBI/GISAID submission | TOSTADAS for NCBI, GISAID EpiCoV export implemented |
| No AMR reporting | hAMRonization-compatible amr_results table, tb-profiler integration |
| No lineage classification | Pangolin + Nextclade auto-run after viralrecon |
| No workspace | JupyterHub on GKE with jackpot-sdk and three researcher profiles |
| Clunky Vertex AI Workbench integration | JupyterHub with context injection and idle culling |

**Scale goal:** Dozens of samples now → thousands → pandemic-response readiness at a
public health agency. Every architectural decision has a clean upgrade path.

---

## 2. Architecture Philosophy

**Schema first.** The LinkML schema exists before the first router is written. DB tables,
API validation models, and DataHarmonizer templates are generated from it. There is no
path to ingest a sample without going through the validator.

**Standards as infrastructure.** GenEpiO, NCBI BioSample, PHA4GE, MIxS, GA4GH DUO/DRS,
LOINC, SNOMED CT, NWSS, MMWR epiweek — these are the vocabulary that makes data
exchangeable with ADHS, CDC, NCBI, and GISAID without manual curation.

**Migration-first design.** Every table name, role name, and FK relationship accepts APGAP
data via `scripts/migrate_from_apgap.py`. The `PermissionGroups` enum values are identical
strings. An APGAP user's Google account works in JACKPOT without re-registration.

**PostgreSQL all the way.** The operational database is PostgreSQL everywhere — local Docker
and production Cloud SQL. Alembic manages all migrations. The transition is a connection
string change. BigQuery is NOT the operational database — it is a separate analytics
warehouse populated by a periodic ETL job from Cloud SQL, used for surveillance dashboards
and population-level reporting only. The FastAPI API never queries BigQuery directly.

**No Celery, no Redis as a task broker.** Every APGAP Celery use case is replaced by a
GCP-native equivalent. Redis (Cloud Memorystore) is used for one thing only: shared
external search result cache across API replicas.

**Build only what doesn't exist.** JACKPOT is FastAPI + PostgreSQL + GCS done correctly.
Not Arvados. Not Gen3. Those are Year 2+ migration targets.

**Pandemic-readiness as a hard constraint.** Schema handles novel unknown pathogens without
changes. Every long-running operation has a defined status machine that surfaces failures.
BigQuery partitioning and clustering are correct from day one for when the analytics
warehouse is activated.

---

## 3. Tech Stack

| Layer | Local Dev | GCP Production |
|---|---|---|
| Backend API | FastAPI + Python 3.11 (uv) | Cloud Run (same container) |
| Analyst UI | Streamlit | Cloud Run (same container) |
| Operational database | PostgreSQL 16 (Docker) | Cloud SQL PostgreSQL 16 |
| Analytics warehouse | — | BigQuery (Month 3+, ETL from Cloud SQL) |
| Schema migrations | Alembic | Alembic (same) |
| File storage | MinIO | GCS |
| Schema modeling | LinkML v4.4 | — |
| Metadata entry | DataHarmonizer (offline browser) | — |
| Auth | Google OAuth 2.0 + JWT httponly cookies | Same |
| RBAC | Six-role FastAPI middleware | Same |
| Ingest gate | SRA-human-scrubber | GKE Jobs (scrubber-pool, spot) |
| Pipeline executor | `PIPELINE_EXECUTOR=local` | GCP Batch (Nextflow controller on GKE api-pool) |
| Workspace | Disabled (`WORKSPACE_ENABLED=false`) | JupyterHub on GKE workspace-pool |
| Background jobs | APScheduler in-process | Cloud Scheduler → HTTP trigger |
| External search cache | In-memory dict | Cloud Memorystore Redis |
| Python env | uv (app) + pixi (bioinformatics tools) | — |
| Containerization | Docker + Docker Compose | GKE |
| CI | GitHub Actions | — |

**Frontend migration path:** Streamlit is the prototype UI. React + shadcn/ui + TanStack
Query is the migration target when Streamlit becomes a genuine blocker (signal: writing
more `st.components.v1.html()` than `st.dataframe()`). FastAPI backend is frontend-agnostic
— the migration is purely a frontend concern.

---

## 4. Repository Structure and Git

### 4.1 Five repositories

```
~/ASU/jackpot/
├── jackpot-backend/       # FastAPI API + Alembic + tests (primary codebase)
│   └── schema/            # git submodule → jackpot-schema
│   └── setup/             # bootstrap.sh, write_files.py, write_files_2.py
├── jackpot-frontend/      # Streamlit UI
│   └── schema/            # git submodule → jackpot-schema
├── jackpot-schema/        # LinkML schema YAML + generated artifacts
├── jackpot-iac/           # Terraform (GCP)
└── jackpot-cli/           # CLI tool (Year 1, later)
```

`jackpot-schema` is a git submodule inside both `jackpot-backend` and `jackpot-frontend`.
Both repos always reference the same schema version via a commit pointer.

### 4.2 Branching strategy

```
main           → production (Cloud Run / GKE deployment target)
development    → staging
feature/*      → working branches
hotfix/*       → emergency production fixes
```

Never commit directly to `main`. Work on `feature/` branches, open PR to `development`,
merge to `main` when ready to deploy.

### 4.3 Global git config

```bash
git config --global user.name "Glen Otero"
git config --global core.editor "nvim"
git config --global pull.rebase true
git config --global push.autoSetupRemote true
git config --global rerere.enabled true
git config --global alias.st      "status -sb"
git config --global alias.lg      "log --oneline --graph --decorate --all"
git config --global alias.undo    "reset --soft HEAD~1"
git config --global alias.aliases "config --get-regexp alias"
git config --global alias.schema-update "submodule update --remote schema"
```

### 4.4 Schema submodule workflow

```bash
# After any schema change:
cd ~/ASU/jackpot/jackpot-schema
git add -A && git commit -m "feat: description" && git push origin main

# Update both consumers:
cd ~/ASU/jackpot/jackpot-backend
git schema-update && git add schema && git commit -m "chore: update schema submodule"

cd ~/ASU/jackpot/jackpot-frontend
git schema-update && git add schema && git commit -m "chore: update schema submodule"
```

### 4.5 First-run setup (corrected complete sequence)

Prerequisites: uv installed, pixi installed, SSH key linked to `gotero` GitHub, four
private repos created (jackpot-backend, jackpot-frontend, jackpot-schema, jackpot-iac).

```bash
# 1. Bootstrap dirs, environments, dependencies
cd ~/ASU/jackpot
chmod +x jackpot-backend/setup/bootstrap.sh
./jackpot-backend/setup/bootstrap.sh

# 2. Write application files
cd jackpot-backend
uv run python setup/write_files.py
uv run python setup/write_files_2.py

# 3. Push jackpot-schema FIRST (submodule needs remote commits)
cd ~/ASU/jackpot/jackpot-schema
cp ~/path/to/jackpot_schema_v4_4.yaml schema/schema/jackpot_schema.yaml
git add -A && git commit -m "feat: add jackpot_schema v4.4" && git push -u origin main

# 4. Wire submodule in jackpot-backend
cd ~/ASU/jackpot/jackpot-backend
git submodule add git@github.com:gotero/jackpot-schema.git schema
git submodule update --init
ls schema/schema/    # verify: jackpot_schema.yaml visible
git add .gitmodules schema && git commit -m "chore: add jackpot-schema submodule"

# 5. Generate schema artifacts
uv run gen-pydantic schema/schema/jackpot_schema.yaml > backend/models_generated.py
uv run gen-json-schema schema/schema/jackpot_schema.yaml > schema/schema/jackpot_schema.json

# 6. Push all repos
cd ~/ASU/jackpot/jackpot-backend && git push -u origin main
cd ~/ASU/jackpot/jackpot-frontend
git submodule add git@github.com:gotero/jackpot-schema.git schema
git submodule update --init && git add .gitmodules schema
git commit -m "chore: add jackpot-schema submodule" && git push -u origin main
cd ~/ASU/jackpot/jackpot-iac && git push -u origin main

# 7. Start services and verify
cd ~/ASU/jackpot/jackpot-backend
docker compose up -d
sleep 5
curl http://localhost:8000/health
# {"status":"ok","version":"5.0.0","project":"JACKPOT"}
uv run alembic upgrade head
uv run pytest
```

**Important notes:**
- `schema/schema/jackpot_schema.yaml` — double `schema/` because submodule mounts at
  `schema/` and the YAML lives at `schema/` inside that repo.
- The `.git` file inside `schema/` is intentional (gitdir pointer) — never delete it.
- `uv run` always uses `.venv` with Python 3.11 — ignore the system Python 3.12 in prompt.
- `sed -i ''` fails on macOS — use Python pathlib one-liners for in-place edits.

### 4.6 Schema artifact generator reference

| Artifact | Command (from jackpot-backend/) |
|---|---|
| Pydantic v2 models | `uv run gen-pydantic schema/schema/jackpot_schema.yaml > backend/models_generated.py` |
| JSON Schema | `uv run gen-json-schema schema/schema/jackpot_schema.yaml > schema/schema/jackpot_schema.json` |
| BigQuery DDL | `uv run gen-sqla schema/schema/jackpot_schema.yaml --dialect bigquery > db/bigquery_schema.sql` |
| Markdown docs | `uv run gen-markdown schema/schema/jackpot_schema.yaml > docs/schema.md` |
| Validate YAML | `python3 -c "import yaml; yaml.safe_load(open('schema/schema/jackpot_schema.yaml'))"` |

---

## 5. Python Environment

### uv (app dependencies)

uv replaces pyenv + virtualenv + pip. Never activate the venv manually — use `uv run`.

```bash
uv run uvicorn backend.main:app --reload   # run dev server
uv run pytest                              # run tests
uv run alembic upgrade head               # run migrations
uv run pre-commit run --all-files         # run hooks
uv add fastapi                            # add dependency
uv add --dev pytest                       # add dev dependency
```

The project pins Python 3.11 via `.python-version`. `uv run python --version` always
shows 3.11.x — this is what matters. Ignore the system Python 3.12 in the prompt.

### pixi (bioinformatics tools)

pixi manages conda-forge compiled binaries that pip cannot install.

```bash
cd ~/ASU/jackpot/jackpot-biotools
pixi add --channel conda-forge --channel bioconda \
    nextflow multiqc samtools fastp pangolin nextclade \
    ncbi-amrfinderplus mlst vadr
pixi run nextflow -version
```

---

## 6. Code Quality

### Pre-commit hooks

**File: `.pre-commit-config.yaml`** (no mypy — intentional decision)

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: [--baseline, .secrets.baseline]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-toml
      - id: check-merge-conflict
      - id: no-commit-to-branch
        args: [--branch, main]
```

```bash
uv run pre-commit install
uv run detect-secrets scan > .secrets.baseline
uv run pre-commit run --all-files
```

### CI pipeline (`.github/workflows/test.yml`)

On every push/PR to `main` or `development`:
1. Checkout with `submodules: true` (critical — initializes jackpot-schema submodule)
2. Install uv + `uv sync --frozen`
3. Run pre-commit hooks
4. Run Alembic migrations against a postgres:16 service container
5. Run pytest with coverage
6. Upload coverage to Codecov

**ruff config (in `pyproject.toml`):**

```toml
[tool.ruff]
line-length    = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]
```

---

## 7. Permission System

Role names are **identical strings** to APGAP's `PermissionGroups` enum. Do not rename —
the migration script depends on these exact strings. The rename `lab_admin → lab_director`
and `org_admin → platform_admin` was applied in Alembic migration `a7fd1fcccb77` (column
`is_lab_admin → is_lab_director` on `lab_membership`).

```python
class PermissionGroups(str, Enum):
    PLATFORM_ADMIN      = "Platform Admin"
    LAB_DIRECTOR        = "Lab Director"
    LAB_COLLABORATOR    = "Lab Collaborator"
    LAB_READER          = "Lab Reader"
    BIOINFORMATICS_USER = "Bioinformatics User"
    DATA_ANALYST        = "Data Analyst"
```

### Role capabilities

| Capability | Platform Admin | Lab Director | Lab Collaborator | Lab Reader | Bioinfo User | Data Analyst |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Create/delete orgs and labs | ✅ | | | | | |
| Invite/remove lab members | ✅ | ✅ | | | | |
| Upload sequences + metadata | ✅ | ✅ | ✅ | | ✅ | |
| Edit metadata | ✅ | ✅ | ✅ | | ✅ | |
| View sequences (own lab) | ✅ | ✅ | ✅ | ✅ | ✅ | |
| View sequences (DISCOVERABLE) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Launch pipelines | ✅ | ✅ | ✅ | | ✅ | |
| Create/manage datasets | ✅ | ✅ | ✅ | | ✅ | |
| Approve access requests | ✅ | ✅ | | | | |
| Submit to NCBI/GISAID | ✅ | ✅ | ✅ | | ✅ | |
| Manage sequencing lab list | ✅ | | | | | |
| Request new sequencing lab | | ✅ | ✅ | | ✅ | |
| View billing (own lab) | | ✅ | | | | |
| View billing (all) | ✅ | | | | | |
| Approve scrub skip | ✅ | ✅ | | | | |
| Approve deletion requests | ✅ | ✅ (non-surveillance) | | | | |

**Key constraints:**
- `Platform Admin` and `Data Analyst` cannot be assigned to labs or projects.
- A user can be `Lab Director` in Lab A and `Lab Collaborator` in Lab B simultaneously.
- `Lab Director` maps to `is_lab_director = TRUE` on `lab_membership`.

### Permission cascade

```
1. Authenticated?                                  No  → 401
2. Platform Admin?                                 Yes → ALLOW ALL
3. Has permission via lab_membership role?         Yes → ALLOW (role-dependent)
4. Has permission via project_membership role?     Yes → ALLOW (role-dependent)
                                                   No  → 403
```

For sample access specifically, see `can_access_sample()` and `can_see_sample()` in
Section 13.

---

## 8. Authentication

### Google OAuth flow

```
Production:
  User → GET /auth/login → redirect to Google
  Google → POST /auth/callback?code=... → exchange code → verify email domain
  → look up user record → issue JWT httponly cookies → redirect to UI

Local dev (ENV=local):
  Mock user from settings.mock_user_email — no OAuth roundtrip
  Always authenticated as Platform Admin
```

### Auth rules (identical to APGAP)

1. Email domain must be in `domain_whitelist` table.
2. Platform Admin must create user record before first login — no self-signup.
3. JWT stored as httponly cookies (`access` 15-min TTL, `refresh` 7-day TTL).
4. JavaScript never sees the tokens.

### Personal API tokens

Long-lived tokens for CLI/SDK/scripts. Default 1-year lifetime. Scoped — separate tokens
per use case (laptop, Sol HPC, collaborator). SHA-256 hash stored; raw token shown once.
Revocable by owner or Platform Admin. Max lifetime configurable per org via
`organizations.max_token_lifetime_days`.

### Signed upload URLs

GCS signed URLs for direct browser/CLI upload to GCS, bypassing the API server. Default
4-hour lifetime, single-use per file. Script requests new URL for remaining files if batch
exceeds 4 hours.

---

## 9. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    USERS (Google Accounts)                      │
│  Platform Admins │ Lab Directors │ Bioinformaticians │ Analysts │
└──────────┬───────────────────────────────┬─────────────────────┘
           │                               │
           ▼                               ▼
┌──────────────────────────┐  ┌────────────────────────────┐
│   FastAPI Backend        │  │   Streamlit UI             │
│   /api/v1/*              │◄─│   (Cloud Run / localhost)  │
│   (Cloud Run / GKE)      │  └────────────────────────────┘
│                          │
│  Google OAuth + JWT      │  ┌────────────────────────────┐
│  6-role RBAC cascade     │  │  DataHarmonizer            │
│  Tier-aware validator    │  │  (offline browser app)     │
│  file_detector.py        │  └────────────────────────────┘
│  Audit logger            │
│  APScheduler / jobs.py   │
└───────┬──────────┬───────┘
        │          │
   ┌────▼────┐ ┌───▼──────────────────┐
   │Cloud SQL│ │  GCS Buckets         │
   │(prod)   │ │  jackpot-sequences/  │
   │PostgreSQL│ │  jackpot-staging/    │
   │(local)  │ │  jackpot-results/    │
   └─────────┘ │  jackpot-work/       │
               └──────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
  ┌────────────┐  ┌──────────────┐  ┌────────────────┐
  │ GCP Batch  │  │  GKE Jobs    │  │  JupyterHub    │
  │ (Nextflow  │  │  (Scrubber)  │  │  (workspace-   │
  │  pipelines)│  │              │  │   pool)        │
  └────────────┘  └──────────────┘  └────────────────┘
```

**BigQuery** (not shown) is a separate analytics warehouse populated by a periodic ETL
job from Cloud SQL. Used for surveillance dashboards and population-level reporting.
The FastAPI API never queries BigQuery.

---

## 10. Data Model

### Table inventory

**Organizational hierarchy:**

| Table | Purpose |
|---|---|
| `organizations` | Top-level institutions (ASU, ADHS, CDC). Has oversight_access, sharing_level policy, federation settings. |
| `labs` | Research labs within an org. Linked to sequencing facilities via join table. |
| `projects` | Named sample collections within a lab. Optional at ingest. |
| `permission_groups` | Lookup table for the six role names. |
| `lab_membership` | User↔Lab with role; `is_lab_director` boolean. |
| `project_membership` | User↔Project with role. |
| `domain_whitelist` | Allowed email domains for registration. |

**Users and auth:**

| Table | Purpose |
|---|---|
| `users` | Core user record. `is_platform_admin`, `is_data_analyst`, `globus_identity_id`. |
| `personal_tokens` | SHA-256 hashed API tokens. Scoped, expirable. |
| `audit_log` | Immutable append-only. Never UPDATE or DELETE. |

**Samples and files:**

| Table | Purpose |
|---|---|
| `samples` | Core sample record. All fields from LinkML schema. `quality_status`, `sharing_level`, `surveillance_relevant`, `scrub_status`. |
| `sample_files` | Canonical per-file registry. Handles multi-lane, multi-chunk, paired/single. |
| `sample_associations` | Directed cross-sample linkage (e.g. wastewater↔clinical isolate). |
| `metadata_tags` | Lab-specific extension fields not in core schema. Typed key-value. |
| `deleted_samples` | Immutable tombstone. Preserved after hard delete. |

**Sequencing facilities:**

| Table | Purpose |
|---|---|
| `sequencing_labs` | Physical sequencing facilities. DB-managed controlled vocabulary — NOT a static enum. `globus_identity_id`, `filename_pattern` JSONB. |
| `sequencing_lab_assignments` | Join table: sequencing_lab_id ↔ lab_id. One facility may serve multiple JACKPOT labs. Used for Globus deposit-first notification routing. |
| `sequencing_lab_requests` | Lab Director → Platform Admin approval for new facilities. |

**Governance and access:**

| Table | Purpose |
|---|---|
| `sample_access_requests` | Access request lifecycle (PENDING/APPROVED/DENIED/EXPIRED). 90-day passive approval. |
| `sample_scrub_override_requests` | Skip-scrubber requests. PENDING_APPROVAL → 48h auto-deny if unanswered. |
| `deletion_requests` | Staged deletion workflow with approver chain. |
| `reportable_organisms` | ADHS mandatory reportable communicable diseases. Drives `surveillance_relevant` default. |
| `reference_genomes` | Platform-managed reference genome registry. Lab-shared GCS volume. |

**Datasets:**

| Table | Purpose |
|---|---|
| `datasets` | Named sample collections. `scope` (personal/project/global), `sharing_level`. Reference-based — no file copying. |
| `dataset_samples` | Join table: dataset_id ↔ sample_id. Many-to-many. |
| `dataset_access_requests` | Cross-lab dataset access requests with DUO code enforcement. |

**Pipelines:**

| Table | Purpose |
|---|---|
| `pipeline_catalog` | Zoo pipelines and BYOP registrations. `tier` (zoo/lab/project). |
| `pipeline_runs` | Per-run record. `work_dir` (GCS path for -resume), `status`, `run_id` (UUID). |
| `pipeline_tasks` | Per-task records from Nextflow -weblog. |
| `pipeline_events` | Raw Nextflow events. |
| `pipeline_restarts` | Resume history. |
| `pipeline_results` | Structured metrics JSONB per run. |
| `pipeline_files` | Output file registry per run. `presigned_url` generated on demand. |
| `project_pipelines` | Project-pinned custom pipelines. |
| `lab_pipelines` | Lab-promoted custom pipelines. |

**AMR and typing:**

| Table | Purpose |
|---|---|
| `amr_results` | hAMRonization-compatible AMR results. All organisms including TB. |
| `typing_results` | MLST, cgMLST, wgMLST. Covers Salmonella, E. coli, and others. `hiercc_levels` JSONB. |
| `tb_typing_results` | TB-specific: lineage, spoligotype, MIRU-VNTR, WHO drug susceptibility JSONB. |

**Submissions:**

| Table | Purpose |
|---|---|
| `ncbi_submissions` | NCBI BioSample/SRA/GenBank submission tracking via TOSTADAS. |
| `archive_requests` | Formal archive/deletion lifecycle. Requester provides justification. |

**Notifications:**

| Table | Purpose |
|---|---|
| `notifications` | In-app notification queue per user. |
| `assistant_queries` | LLM assistant interaction log (Year 2). |

**Federation (Year 2):**

| Table | Purpose |
|---|---|
| `federated_instances` | Registered trusted JACKPOT deployments. `trust_level`, `api_key_secret_name`. |

### Key relationships

```
Organization
  └─ Lab (org_id FK)
      └─ Project (lab_id FK)
          └─ Sample (project_id FK, optional)
      └─ sample (lab_id FK — project is optional at ingest)
      └─ lab_membership (user ↔ lab ↔ role)
      └─ sequencing_lab_assignments (lab ↔ sequencing_lab)

Sample
  └─ sample_files (sample_id FK — per-file registry)
  └─ sample_associations (source/target sample_id FK)
  └─ amr_results (sample_id FK)
  └─ typing_results (sample_id FK)
  └─ dataset_samples (sample ↔ dataset)
  └─ pipeline_runs (sample_id FK — via launch context)
```

### Key schema decisions

**Soft deactivation tracking** on orgs, labs, users:
`is_active`, `deactivated_at`, `deactivated_by` — never hard-delete these records.

**Dynamic PATCH pattern** throughout:
Use `model_dump(exclude_none=True)` to build update dict — never overwrite fields
not present in the PATCH request body.

**PostgreSQL RETURNING clause** on all INSERT/UPDATE:
Single round-trip create/update — no SELECT needed to return the created resource.

**Audit log** is append-only. Never UPDATE or DELETE audit_log rows. This is a CLIA
requirement and a forensic guarantee.

---

## 11. Schema — LinkML v4.4

### Version history

| Version | Key additions |
|---|---|
| v4.0 | Initial consolidated schema. APGAP-compatible hierarchy. 13 sample types, 62 organisms. |
| v4.1 | Full ontology anchoring: GenEpiO, MIxS, PHA4GH, NWSS, GA4GH DUO/DRS, LOINC, SNOMED CT, ENVO, OBI, ELR. DataHarmonizer and TOSTADAS compatibility. |
| v4.2 | 22 additions: `case_id` on BaseSample, `case_source_system`, `sector`+SectorEnum, `surveillance_relevant`+override fields, `target_organisms` (metagenomics), `quality_status`+QualityStatusEnum, `date_collected_precision`+DatePrecisionEnum, `read_type`+ReadTypeEnum, `assembly_type`+AssemblyTypeEnum+MAG QC fields, `originating_lab`, `submitting_lab`, `data_generator`, `ena_accession`, `data_use_terms`+DataUseTermsEnum (GA4GH DUO), embargo fields, turnaround timestamps. |
| v4.3 | Globus fields: `users.globus_identity_id`, `users.globus_identity_linked_at`, `sequencing_labs.globus_identity_id`, `sequencing_labs.globus_staging_path`, `sequencing_labs.filename_pattern`. `samples.basespace_run_id` stub. |
| v4.4 | Current. TB typing schema (`tb_typing_results`), federation fields on organizations, `federated_instances` class, dataset reference model (datasets + dataset_samples replacing old gcs_bucket-per-dataset model). |

### Key design decisions

**sequencing_lab is a DB-managed controlled vocabulary**, not a static enum. Validated
against the `sequencing_labs` table at ingest. Platform Admin registers facilities.
Lab Directors request additions. See Section 22 (External Integrations).

**date_collected accepts partial dates.** `DatePrecisionEnum` (YEAR/MONTH/FULL) allows
year-only ("2025") and month-only ("2025-03") inputs. Tier system accounts for precision
in completeness scoring.

**surveillance_relevant is organism-driven by default.** `reportable_organisms` table
provides defaults from the ADHS mandatory reportable communicable diseases list.
Metagenomics: `target_organisms` list used; untargeted metagenomics defaults TRUE
conservatively; post-pipeline recompute promotes but never demotes.

**Override model:** TRUE→FALSE requires governance board approval.
FALSE→TRUE is self-declared with `SurveillanceOverrideCategoryEnum` reason.

**FASTA-only uploads auto-skip scrubber.** `file_detector.py` detects FASTA-only
uploads and sets `scrub_status=SKIPPED`, `skip_reason=no_raw_reads`. No Lab Director
approval needed — SYSTEM logs the reason.

### Schema update workflow

```bash
# 1. Edit schema
cd ~/ASU/jackpot/jackpot-schema
nvim schema/schema/jackpot_schema.yaml

# 2. Validate
python3 -c "import yaml; yaml.safe_load(open('schema/schema/jackpot_schema.yaml')); print('OK')"

# 3. Commit and push
git add -A && git commit -m "feat: description" && git push origin main

# 4. Update submodule pointer in backend
cd ~/ASU/jackpot/jackpot-backend
git schema-update && git add schema && git commit -m "chore: update schema submodule"

# 5. Regenerate artifacts
uv run gen-pydantic schema/schema/jackpot_schema.yaml > backend/models_generated.py
uv run gen-json-schema schema/schema/jackpot_schema.yaml > schema/schema/jackpot_schema.json

# 6. Write Alembic migration if DB structure changed
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head

# 7. Run tests
uv run pytest
```

---

## 12. Metadata Quality Tiers

Two orthogonal tier concepts exist on every sample simultaneously. They are independent.

### Quality tiers (quality_status) — what the sample IS

Computed automatically by `validator.py` from field completeness. Rises only — never
falls. Replaces APGAP's binary DRAFT/PRIMARY gate that caused the metadata backlog.

| Tier | `quality_status` | Required fields (~) | What it unlocks |
|---|---|---|---|
| 1 | PRELIMINARY | ~15: organism, date, source_type, sector, country | Visible in lab, pipelines can launch, lab-level access |
| 2 | ANALYZABLE | ~20: + collection_facility, host details, read_type, sequencing_lab | Can join datasets, indexed in external search |
| 3 | SUBMITTABLE | ~35: all NCBI/GISAID required fields, VADR passed | NCBI BioSample/SRA submission, GISAID export |

### Sharing/access levels (sharing_level) — who can SEE the sample

Set by the submitting researcher and org policy. Controlled by `can_see_sample()` and
`can_access_sample()` — two distinct permission checks with different restrictiveness.

| Level | Catalog visibility | File/full metadata access |
|---|---|---|
| PRIVATE | Owner + Lab Director only | Owner + Lab Director only |
| LAB | All lab members | All lab members |
| DISCOVERABLE | All authenticated users (safe subset only) | Must submit access request |
| PUBLIC | All authenticated users | All authenticated users |

**DISCOVERABLE safe subset** (visible before access granted): organism, date_collected,
collection_location_country/state, source_type, sector, quality_status. Clinical fields
masked until access approved.

### Access permission cascade (can_access_sample)

```
1. Platform Admin?                        → ALLOW
2. Lab member of owning lab?              → ALLOW (per sharing_level ≥ LAB)
3. sharing_level = PUBLIC?                → ALLOW
4. ADHS oversight authority?              → ALLOW if surveillance_relevant=TRUE only
5. Approved access request holder?        → ALLOW
                                          → DENY (403)
```

ADHS oversight is scoped to `surveillance_relevant=TRUE` samples only. Academic private
research on non-reportable organisms is excluded. Oversight authority derives from
`organizations.has_oversight_access=TRUE` + the user's platform admin or lab director role
in that org — not from `is_platform_admin` globally.

### Org profiles

| Org type | `default_sharing_level` | `has_oversight_access` |
|---|---|---|
| ADHS | LAB | TRUE |
| Academic (ASU) | PRIVATE | FALSE |
| Partner PH | LAB | FALSE |

---

## 13. Data Governance and Access Control

### Access request lifecycle

90-day passive approval. Background job checks for expired requests nightly.

```
Researcher submits access request
  → Lab Director notified immediately
  → 75-day warning notification to Lab Director
  → 7-day warning notification to Lab Director
  → Auto-approve on day 90 if no decision (passive approval)
  → Researcher notified at each stage
```

Access requests expire after 90 days from approval. Researcher must re-request.

### Dataset promotion lifecycle

Personal dataset (PRIVATE, My Work)
  → Project dataset (LAB, Project page): Lab Director approval (14-day passive)
  → Global dataset: per-lab Lab Director approval + Platform Admin final gate
    + cross-org Platform Admin for cross-org datasets

### Org-level policy fields (organizations table)

| Field | Default | Purpose |
|---|---|---|
| `has_oversight_access` | FALSE | Grants ADHS-style oversight access to surveillance_relevant samples |
| `default_sharing_level` | LAB | Sharing level applied to new samples from this org |
| `access_request_grace_days` | 90 | Days before passive approval |
| `access_requests_enabled` | TRUE | Can disable for orgs that auto-approve everything |
| `access_policy_note` | NULL | Human-readable policy note shown to requesters |
| `max_token_lifetime_days` | 365 | Cap on personal token lifetime for this org |
| `min_sharing_level_for_federation` | LAB | Min level for samples to flow to federation hub |
| `federation_enabled` | FALSE | Whether this org participates in federation (Year 2) |

---

## 14. Data Lifecycle — Scrubbing and Deletion

### Scrubber skip governance

Scrubber runs on ALL samples by default regardless of source type. FASTA-only and SRA
imports are the only automatic exceptions.

```
scrub_status states:
  PENDING           → queued, files not downloadable, pipelines cannot launch
  IN_PROGRESS       → scrubber GKE Job running
  COMPLETE          → files downloadable, pipelines can launch
  FAILED            → scrubber failed, Lab Director notified
  PENDING_APPROVAL  → someone requested skip; awaiting Lab Director decision
  SKIPPED           → auto-skip (FASTA-only or SRA import) or Lab Director approved
```

**Skip request flow:**
Any user requests scrubber skip on any sample
  → `scrub_status = PENDING_APPROVAL`
  → Lab Director notified
  → Lab Director approves or denies within 48 hours
  → Auto-deny after 48 hours if no decision (conservative default)

**Automatic exceptions (no Lab Director approval needed):**
- FASTA-only uploads detected by `file_detector.py` → `skip_reason = no_raw_reads`
- SRA-imported samples → `skip_reason = sra_imported` (NCBI already processed)

**Bulk upload concurrency control:**
When many samples arrive simultaneously via Globus batch, scrubber jobs are queued via
`run_scrubber_queue_job()` in `backend/jobs.py` (APScheduler locally, Cloud Scheduler in
GKE). Up to `SCRUBBER_MAX_CONCURRENT` (default=10) jobs run simultaneously.

### Staged deletion lifecycle

| Action | Who requests | Who approves | Reversible |
|---|---|---|---|
| Archive sample | Lab Director | None | Yes |
| Erroneous upload removal (≤72h) | Submitting user | Lab Director | Yes (90 days) |
| Soft-delete (non-surveillance) | Lab Director | Platform Admin | Yes (90 days) |
| Soft-delete (surveillance_relevant) | Lab Director | PA + Governance Board | Yes (90 days) |
| Hard-delete | Platform Admin | Governance Board + 2nd PA | No |

72-hour fast-path: UI shows countdown. User can self-serve within 72 hours of ingest.
Tombstone record: immutable, permanent, cannot be deleted. Pipeline results and audit
records preserved after any deletion.

---

## 15. Ingest Methods

### Core principle: researchers enter samples, not files

One sample = one row in the metadata form/CSV. File association is automatic via
`file_detector.py` — the only place filename logic lives. Never parse filenames in routers.

### File detection and pairing (file_detector.py)

Handles: standard R1/R2, numeric 1/2, forward/reverse, multi-lane Illumina
(`L001_R1_001`), nanopore chunks (`barcode01_0.fq.gz`).

Supported FASTQ extensions: `.fastq`, `.fq` + `.gz`/`.bz2`
Supported FASTA extensions: `.fasta`, `.fa`, `.fna` + `.gz`

### Five ingest methods

**1. GUI upload** — researcher drops files in browser. `file_detector.py` groups into
samples and presents confirmation view. One metadata form row per detected sample group.

**2. Batch CSV** — files column is semicolon-separated within a single cell:
`AZ-001_R1.fastq.gz;AZ-001_R2.fastq.gz`. One row per sample. Old template formats
handled by `harmonizer.py` column mapping.

**3. Signed URL direct-to-GCS** — `POST /api/v1/ingest/signed-url` issues GCS signed
URL. Browser/curl uploads directly to GCS for large files, bypassing API server.
`POST /api/v1/ingest/signed-url/{id}/complete` confirms receipt. Default 4-hour URL TTL.

**4. URI/accession registration** — `POST /api/v1/ingest/uri` for gs://, s3://, https://
with optional server-side copy. `POST /api/v1/ingest/accession` for NCBI/ENA accessions:
E-utilities metadata fetch → background GKE fasterq-dump job → `sra://` URI in
`fastq_r1_uri` resolved by pipeline executor on compute node.

**5. Globus deposit-first** — external sequencing labs or researchers transfer FASTQs to
`jackpot-staging/{org_slug}/{lab_slug}/incoming/` via Globus. Globus Flow fires webhook
→ `POST /api/v1/ingest/globus-callback` → `file_detector.py` groups files (using
`sequencing_labs.filename_pattern` for known facilities) → draft records created →
lab members notified to complete metadata. See Section 22.

### DataHarmonizer tiered templates

Three template tiers: T1 (~15 cols), T2 (~20), T3 (~35). Combined templates:
"Tier 1 — Human Clinical", "Tier 2 — Wastewater", etc. Template version embedded in CSV.
`surveillance_relevant` is read-only in templates (computed server-side). MAG fields
excluded (pipeline output, not user-entered). Old templates handled by harmonizer column
mapping — missing fields get defaults + validation warning.

### Ingest pipeline sequence (every method)

```
Files received (any method)
  → file_detector.py: group files into samples
  → harmonizer.py: map columns to schema fields
  → validator.py: tier-aware validation → compute quality_status
  → compute_surveillance_relevant(): org reportable_organisms lookup
  → compute_epiweeks(): MMWR + ISO week from date_collected
  → Write samples + sample_files records (PostgreSQL RETURNING)
  → scrub_status = PENDING (ALL sample types; FASTA/SRA auto-skip)
  → log_audit(): CREATE_SAMPLE action
  → Submit scrubber GKE Job (via queue if bulk)
  → Notify lab members if Globus deposit
```

---

## 16. Dataset Model

### Core design: reference-based, never copy FASTQs

A dataset is a named collection of `sample_id` references. Pipelines launched against a
dataset read directly from `jackpot-sequences/{org_slug}/{lab_slug}/{sample_id}/` via the
API service account. No intermediate copy, no duplication, no storage cost.

```
datasets               → name, scope, sharing_level, created_by, lab_id, project_id
dataset_samples        → dataset_id, sample_id, added_at, added_by
```

### Three dataset tiers

**Tier 1 — Internal dataset (My Work / Project):**
Named collection of sample_id references. Pipelines read from source paths. No copy ever.

**Tier 2 — Published dataset snapshot:**
At promotion to global scope, a frozen snapshot is written to
`gs://jackpot-results/datasets/{dataset_id}/`:
- `metadata_snapshot_{timestamp}.csv` — frozen metadata export
- `manifest_{timestamp}.json` — list of GCS URIs + checksums
- `README.md` — citation, data use terms, attribution

Files are not copied — their canonical GCS URIs are recorded in the manifest.
This is what researchers cite in papers. GISAID-sourced samples: metadata-only
(redistribution prohibited by terms of use).

**Tier 3 — External collaborator access:**
Time-limited presigned URL package (JSON manifest, default 30-day expiry). Collaborator
downloads directly from GCS without JACKPOT auth. No file copy at rest.

**Open governance question (defer to implementation):** Whether to copy FASTA (not FASTQ)
of published global datasets as a permanent scientific record. FASTAs are 1–5 MB each.
Preserves reproducibility if source sample is later deleted.

### Dataset promotion workflow

```
Personal (PRIVATE, My Work)
  → Project (LAB, Project page): Lab Director approval, 14-day passive
  → Global (global catalog): per-lab Lab Director + Platform Admin final gate
    + cross-org Platform Admin for cross-org datasets
```

Each stage logged in audit_log. Governance tab on dataset page shows approval timeline.

---

## 17. Pipeline Architecture

### Pipeline zoo and BYOP

Three tiers of pipeline availability:

```
Pipeline catalog (zoo) — Platform Admin curated
  ← Promotion by Platform Admin (formal requirements: nextflow_schema.json,
    public stable repo, documented parameters)
Lab pipelines — Lab-wide availability
  ← Promotion by Lab Director from project pipeline
Project pipelines (BYOP) — Project-scoped
  ← Registered by Bioinformatics User or Lab Director via GitHub/GitLab URL
    + revision + parameter schema. Auto-detects nextflow_schema.json for nf-core.
```

**Initial zoo catalog (Month 2):**
GHRU assembly, nf-core/viralrecon, nf-core/mag, nf-core/taxprofiler,
nf-core/funcscan, tb-profiler.

**Pipeline compatibility checks:**
- Soft warning (yellow, overridable with one click, override logged)
- Hard block (red, explains missing requirement — e.g. missing assembly for AMR)
- No graying out — all pipelines are always clickable

### Nextflow GCP Batch execution model

Mac (or GKE api-pool) is the Nextflow controller. Tasks run on GCP Batch VMs.

**Key decisions:**
- Per-run GCS work directory: `gs://jackpot-work/{run_id}/work/`
  Stored in `pipeline_runs.work_dir`. Required for `-resume`. Two runs must NEVER
  share a workDir prefix. (Critical Rule 25)
- Config is generated per-run — never a static file. `backend/pipeline_config.py`
  generates the config string with run_id, API URL, weblog URL, pipeline token.
  (Critical Rule 26)
- `resourceLabels` on every GCP Batch job: `jackpot_run_id`, `jackpot_lab`,
  `jackpot_pipeline`. Required for cost attribution and billing dashboard. (Critical Rule 27)
- Spot instances (`google.batch.spot=true`) — ~90% cost saving. Safe because
  `-resume` recovers from preemptions automatically.
- Apple Silicon: prefer `PIPELINE_EXECUTOR=gcp_batch`. Many bioinformatics containers
  are x86-only. GCP Batch VMs are x86 by default. (Critical Rule 29)
- Weblog callback requires publicly reachable URL when using gcp_batch. Use
  `cloudflared tunnel` for local dev testing — never commit tunnel URLs.
- `jackpot-work` bucket has 90-day lifecycle rule. Never manually delete work dirs —
  breaks -resume for in-flight runs.

  **Result registration:**
  Pipeline's final step calls `POST /api/v1/pipelines/{run_id}/results` via curl.
  Added in JACKPOT pipeline wrapper, not in upstream nf-core pipelines.

### Pipeline telemetry tables

Nextflow `-weblog` POSTs events to `POST /api/v1/pipelines/events` (no auth —
`run_id` in path acts as bearer).

| Table | Purpose |
|---|---|
| `pipeline_runs` | Per-run record: status, work_dir, pipeline_token, start/end time |
| `pipeline_tasks` | Per-task: name, status, container, CPU/RAM/duration |
| `pipeline_events` | Raw Nextflow JSON events (submitted/started/completed/failed) |
| `pipeline_restarts` | Resume history: new run_id, previous run_id, resume timestamp |
| `pipeline_results` | Structured metrics JSONB per run |
| `pipeline_files` | Output file registry: URI, file_type, presigned URL on demand |

**Four-tab monitoring UI (pipelines.py):**
Overview → Tasks → Events → Files.
Resume button triggers `POST /api/v1/pipelines/{run_id}/resume`.

### Pipeline result storage

Two-tier:
- Structured metrics in `pipeline_results.metrics` JSONB
- Raw files in GCS `jackpot-results/{run_id}/` registered in `pipeline_files`

MultiQC report served via presigned URL in an iframe. Microreact export available from
datasets that include samples from the run. AMR and typing results from pipelines
populate `amr_results` and `typing_results` / `tb_typing_results` tables.

---

## 18. Workspace — JupyterHub and SDK

### JupyterHub on GKE

Deployed via Helm chart on `workspace-pool` node pool. Shared Google OAuth with JACKPOT.
Context injection: when user clicks "Open in Workspace" from a project page, pod starts
with `JACKPOT_API_URL`, `JACKPOT_API_TOKEN`, `JACKPOT_PROJECT_ID`, `JACKPOT_LAB_ID` preset.

**Three spawner profiles:**

| Profile | Resources | Idle cull | Contents |
|---|---|---|---|
| Analyst | 2 CPU / 8GB | 1 hour | Python + R + jackpot-sdk |
| Bioinformatician | 4 CPU / 16GB | 2 hours | JupyterLab + terminal + Nextflow + samtools + bcftools + jackpot-sdk |
| Developer | 4 CPU / 16GB | Longer | VS Code Server + full stack + jackpot-sdk |

**One pod per user** regardless of project count. Context switches via env var update
when "Open in Workspace" is clicked from a different project. Named_server feature
allows max 2 concurrent pods per user if genuinely needed.

**Package management:**
- Python: `pip install` for session, `~/requirements.txt` for persistence.
  Startup script installs from requirements.txt on pod launch.
- Bioinformatics tools: conda/mamba in Bioinformatician profile. Named conda
  environments on PVC persist across sessions.
- R: `install.packages()` / pak. `~/renv.lock` on PVC, restored via
  `renv::restore()` at pod startup.
- Custom lab image: Lab Director requests, Platform Admin builds and registers.
  Appears as additional spawner profile for that lab.

  **Cold start mitigation:**
  Scale-to-zero workspace-pool causes 3–5 min cold starts after inactivity.
  Mitigations: (1) placeholder CronJob keeps one node warm 8am–8pm AZ time.
  (2) Pre-cached node image reduces cold start to ~60–90 sec.

  **Local dev:** `WORKSPACE_ENABLED=false` returns 503. Minikube is added in Month 2
  specifically and only for JupyterHub workspace testing — the full stack is never
  migrated to minikube. (Critical Rule 28)

### jackpot-sdk (Python)

Pre-installed in all workspace pods. Thin wrapper around the REST API.

```python
from jackpot import Session

session = Session()  # reads env vars injected by JupyterHub context

# Core modules:
session.samples.list(organism="Salmonella enterica", quality_status="ANALYZABLE")
session.samples.get("AZ-2026-001")
session.samples.register_from_workspace("/home/jovyan/outputs/assembly.fasta")

session.pipelines.list()
session.pipelines.launch("viralrecon", sample_ids=["AZ-001", "AZ-002"])

session.datasets.create("Q1 SARS-CoV-2", sample_ids=["AZ-001", "AZ-002"])
session.datasets.list()

session.sra.fetch("SRR12345678")   # download to personal PVC
session.references.download("GCF_009858895.2")  # to /ref/ volume
```

R equivalent package follows the same structure.

### jackpot-cli (Year 1, later)

Fifth repo. Thin wrapper around the REST API (~300–400 lines). 1-year API token stored
in `~/.jackpot/config`.

```bash
jackpot auth login
jackpot upload --r1 ... --r2 ... --organism ... --project 42
jackpot upload-dir /data/ --metadata-csv metadata.csv --project 42
jackpot upload-globus --source-endpoint asu-sol --source-path /scratch/ --project 42
jackpot samples list --project 42 --status PENDING
jackpot pipelines launch --pipeline viralrecon --project 42
```

---

## 19. GCP Production Architecture

### Database

**Cloud SQL PostgreSQL 16.** Alembic manages migrations. The transition from local
Docker PostgreSQL to Cloud SQL is a `DATABASE_URL` connection string change — nothing
else. Three backup layers:

1. Automated daily backups (7-day retention, managed by Cloud SQL)
2. Point-in-time recovery (PITR) — always enabled, never disable (Critical Rule 35)
3. Weekly export to `gs://jackpot-backups/` (Object Lock WORM, different region)

After any database restore: always run `uv run alembic upgrade head` before starting
the API. (Critical Rule 36)

### Object storage

All GCS buckets defined in `jackpot-iac` Terraform. Never configure GCS in the GCP
console. (Critical Rule 37)

| Bucket | Contents | Versioning | Notes |
|---|---|---|---|
| `jackpot-sequences` | Scrubbed FASTQs and FASTAs | Enabled | Primary sequence archive |
| `jackpot-staging` | Globus incoming files | Disabled | Temporary — moves after scrub |
| `jackpot-results` | Pipeline outputs, dataset snapshots | Disabled | Regenerable |
| `jackpot-work` | Nextflow work dirs | NEVER enable | Would fight 90-day lifecycle rule (Critical Rule 38) |
| `jackpot-backups` | Cloud SQL exports | Object Lock WORM | Different region, 90-day lifecycle |

**GCS bucket path structure:**

```
jackpot-sequences/{org_slug}/{lab_slug}/{sample_id}/
jackpot-staging/{org_slug}/{lab_slug}/incoming/
jackpot-results/{run_id}/
jackpot-results/datasets/{dataset_id}/
jackpot-work/{run_id}/work/
```

Lab storage path created implicitly at first ingest — no Terraform per lab required.
Project storage does not exist as a GCS path — projects are a DB concept only.

### GKE node pools

Pipeline task compute runs on GCP Batch entirely outside GKE. GKE runs only lightweight
controller processes.

| Pool | Machine | Scaling | Spot | Purpose |
|---|---|---|---|---|
| `api-pool` | n2-standard-4 (4CPU/16GB) | min=2, max=6, never zero | No | FastAPI, Streamlit, Nextflow controllers |
| `workspace-pool` | n2-standard-8 (8CPU/32GB) | min=0, max=10, scale-to-zero | No | JupyterHub user pods (interactive, no preemption) |
| `scrubber-pool` | n2-highmem-4 (4CPU/32GB) | min=0, max=20, scale-to-zero | Yes | SRA Human Scrubber GKE Jobs (restartable) |

Pipeline compute runs on GCP Batch — never submit pipeline tasks as GKE pods.
(Critical Rule 30)

### Background jobs

APScheduler in-process locally (`SCHEDULER_ENABLED=true`). In GKE,
`SCHEDULER_ENABLED=false` — Cloud Scheduler fires HTTP requests to job trigger endpoints.
This prevents N replicas each running the same job N times simultaneously.

| Job | Trigger | Action |
|---|---|---|
| `run_scrubber_queue_job()` | Every 60s | Promote up to SCRUBBER_MAX_CONCURRENT scrubbers from PENDING to IN_PROGRESS |
| `run_access_request_expiry_job()` | Nightly | Auto-approve requests at day 90; send 75-day and 7-day warnings |
| `run_scrub_skip_auto_deny_job()` | Hourly | Auto-deny PENDING_APPROVAL scrub skips after 48 hours |
| `run_erroneous_upload_expiry_job()` | Hourly | Auto-expire erroneous upload window after 72 hours |
| `run_federation_push_job()` | Nightly (Year 2) | Push de-identified surveillance data to hub instance |

### Caching

Redis (Cloud Memorystore) used for one thing only: shared external search result cache
across API replicas. `backend/cache.py` abstraction:

```python
# Routes to in-memory dict (local) or Redis (GKE) based on SEARCH_CACHE_BACKEND
cache_get(key: str) -> str | None
cache_set(key: str, value: str, ttl: int = 1800) -> None
cache_delete(key: str) -> None
```

No Celery. No Redis as task broker or result backend. (Critical Rule 34)

### Environment variables — local vs production

| Variable | Local value | GKE value | Purpose |
|---|---|---|---|
| `DATABASE_URL` | `postgresql://jackpot:jackpot@localhost:5432/jackpot` | Cloud SQL connection string | DB connection |
| `ENV` | `local` | `gcp` | Enables mock auth, disables prod validations |
| `STORAGE_BACKEND` | `minio` | `gcs` | Storage routing |
| `STORAGE_ENDPOINT` | `http://localhost:9000` | (not set) | MinIO endpoint |
| `SCHEDULER_ENABLED` | `true` | `false` | APScheduler vs Cloud Scheduler |
| `PIPELINE_EXECUTOR` | `local` | `gcp_batch` | Nextflow execution target |
| `WORKSPACE_ENABLED` | `false` | `true` | JupyterHub activation |
| `SCRUBBER_MAX_CONCURRENT` | `10` | `10` | Bulk scrubber queue throttle |
| `SCRUBBER_QUEUE_INTERVAL_SECONDS` | `60` | `60` | Queue poll interval |
| `SEARCH_CACHE_BACKEND` | `memory` | `redis` | External search cache |
| `REDIS_URL` | (not set) | Cloud Memorystore private IP | Redis connection |
| `SEARCH_CACHE_TTL_SECONDS` | `1800` | `1800` | Search result TTL |
| `ASSISTANT_ENABLED` | `false` | `false` | LLM assistant (Year 2) |
| `FEDERATION_ENABLED` | `false` | `false` | Federation (Year 2) |

### Disaster recovery scenarios

Five documented scenarios in `jackpot-iac/docs/disaster-recovery.md`:

| Scenario | Recovery method | RTO |
|---|---|---|
| Accidental row deletion | PITR or GCS versioning | 30 min |
| Bad migration | PITR to pre-migration timestamp | 1–2 hours |
| Cloud SQL instance failure | Restore from daily backup | 2–4 hours |
| Regional GCP outage | Promote replica, redeploy from IaC | 4–8 hours |
| GCS data loss | Object versioning or SQL export restore | Varies |

---

## 20. Local Development Environment

### Docker Compose stack

Four services always running during development:

| Service | Port | Purpose |
|---|---|---|
| `postgres` | 5432 | PostgreSQL 16 |
| `minio` | 9000 (API), 9001 (console) | S3-compatible object storage |
| `api` | 8000 | FastAPI (`uv run uvicorn --reload`) |
| `ui` | 8501 | Streamlit |

```bash
# Start all services
docker compose up -d

# Verify health
curl http://localhost:8000/health

# Check API docs
open http://localhost:8000/docs

# MinIO console (inspect staged files)
open http://localhost:9001   # minioadmin / minioadmin

# Verify DB migration state
uv run alembic current

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=backend --cov-report=term-missing
```

### Role switching in local dev

The mock user (ENV=local) is always Platform Admin by default. To test other roles,
temporarily modify the mock user's `is_platform_admin=false` in the database and add
a `lab_membership` row with the desired role. Revert after testing.

### Minikube (Month 2 only — JupyterHub testing)

```bash
minikube start --driver=docker --cpus=4 --memory=4096
minikube addons enable ingress
minikube addons enable gcp-auth
# Deploy JupyterHub via Helm chart
# minikube tunnel connects JupyterHub pods to Docker Compose API
```

Minikube is for JupyterHub workspace testing only. The full application stack
stays on Docker Compose. (Critical Rule 28)

---

## 21. Standards and FAIR Compliance

Every field in the JACKPOT schema maps to a standard where one exists.

| Standard | Role in JACKPOT |
|---|---|
| GenEpiO | Collection date, sequencing platform, geographic location, host age, protocol URIs |
| NCBI BioSample | organism, strain, isolate, serotype, host_sex, host_age, collected_by, isolation_source |
| PHA4GE | DataHarmonizer template conventions; schema structural conventions |
| MIxS / MIMS / MIMARKS | env_broad_scale, env_local_scale, env_medium, wastewater fields |
| ENVO | Ontology terms for MIxS environmental context fields |
| GA4GH DUO | Machine-readable data use restrictions on datasets (data_use_terms field) |
| GA4GH DRS | `drs://` URI scheme in fastq_r1_uri / fastq_r2_uri for future DRS endpoint |
| Phenopackets | HumanSample maps to Phenopacket Individual + Disease elements |
| LOINC | Lab test codes on HumanSample |
| SNOMED CT | Clinical finding codes on HumanSample |
| ELR (HL7 v2.5.1) | organism_name→OBX-5, date_collected→OBR-7, case_id→PID-3 |
| NWSS | Full CDC National Wastewater Surveillance System field set in WastewaterSample |
| MMWR epiweek | mmwr_year + mmwr_week computed at ingest via epiweeks library |
| Pango lineage | pango_lineage auto-populated post-Pangolin |
| Nextstrain clades | nextstrain_clade auto-populated post-Nextclade |
| hAMRonization | amr_results table format; enables cross-tool AMR result comparison |
| WHO TB catalogue | TB drug susceptibility JSONB; grade 1–5 per drug |
| TOSTADAS | portal_to_tostadas.py converts JACKPOT metadata to NCBI submission package |

### FAIR compliance status and roadmap

| Principle | Status | Timeline |
|---|---|---|
| F1 — Globally unique, persistent identifiers | 🔶 Designed | Month 1 — sample_id + persistent URI pattern in schema |
| F2 — Rich metadata | ✅ | Schema v4.4 with ontology anchoring |
| F3 — Metadata indexed in searchable resource | 🔶 | Month 1 — search endpoint implementation |
| F4 — Identifier in metadata | ✅ | sample_id is the identifier field |
| A1 — Retrievable by identifier via open protocol | 🔶 | Month 1 — REST API |
| A1.2 — Auth/authorization where needed | ✅ | Google OAuth + RBAC working |
| A2 — Metadata accessible after data deletion | 🔶 | Month 2 — tombstone table + soft-delete |
| I1 — Machine-readable knowledge representation | ❌ | Month 3 — JSON-LD endpoint |
| I2 — FAIR vocabularies | ✅ | GenEpiO, NCBI, MIxS, ENVO, LOINC, SNOMED CT |
| I3 — Qualified cross-references | 🔶 | Month 1 — sample_associations table |
| R1 — Richly described | ✅ | Every field has description, unit, validation rule |
| R1.1 — Data usage license | 🔶 | Month 2 — DUO codes on datasets |
| R1.2 — Detailed provenance | 🔶 | Month 3 — PipelineProvenance + pipeline_runs |
| R1.3 — Community standards | ✅ | PHA4GE, MIxS, NWSS, TOSTADAS |
| GA4GH DRS endpoints | ❌ | Year 2 — interoperability with Terra, AnVIL |

---

## 22. External Integrations

### Sequencing lab registration

`sequencing_lab` is validated against the `sequencing_labs` table — not a static enum.
Platform Admin registers physical sequencing facilities. Three registration paths:

1. Platform Admin registers directly via admin interface
2. Lab Director requests addition → Platform Admin approves via notification
3. Unknown Globus depositor arrives → Platform Admin gets notification → one-click create

Fields: `name`, `display_name`, `lab_type` (clinical/academic/commercial/public_health),
`contact_email`, `globus_identity_id`, `globus_staging_path`, `filename_pattern` JSONB,
`is_active`.

Linked to JACKPOT labs via `sequencing_lab_assignments` join table (not a direct FK on
`labs`). One facility may serve multiple labs. (Critical Rule 21)

### Globus integration (deposit-first, Option 2)

University holds Globus subscription. Research Computing installs Globus Connect Server v5.
Two collections:

- **Staging collection**: `gs://jackpot-staging/{org_slug}/{lab_slug}/incoming/`
  Write-only for external parties. Read-write for lab members.
- **Results collection**: `gs://jackpot-results/` read-only. Allows lab members to
  pull pipeline outputs to Sol HPC via Globus.

  **Deposit-first flow:**
```
External lab initiates Globus transfer
  → FASTQs land in staging collection
  → Globus Flow fires webhook → POST /api/v1/ingest/globus-callback
  → file_detector.py groups files (using sequencing_labs.filename_pattern)
  → Draft records: scrub_status=PENDING, ingest_method=globus, quality_status=PRELIMINARY
  → Lab members notified: "17 files detected — 8 samples grouped. Complete metadata."
  → Researcher completes metadata in notification-driven form
  → Ingest gate pipeline triggers (scrubber runs on all)
```

**Identity models for external sequencing labs:**
- Institutional identity: lab authenticates via own university SSO
- Client credential: Platform Admin creates scoped credential for commercial labs

**User Globus identity linking:** "Link Globus identity" button during onboarding
initiates Globus Auth OAuth flow. `users.globus_identity_id` stores UUID.

### BaseSpace integration (three-stage transition)

Stage 0: Labs export SampleSheet CSV from BaseSpace, import via CSV ingest path.
`harmonizer.py` has BaseSpace SampleSheet as a recognized mapping config.

Stage 1: Lab configures BaseSpace to push completed runs to JACKPOT staging collection
via Globus. Deposit-first webhook handles. No workstation download needed.

Stage 2 (future): JACKPOT optionally pulls run metadata from BaseSpace API to pre-populate
draft records. `BaseSpaceAPIClient` stub class in codebase, wired to real API when
BaseSpace OAuth integration is built. `samples.basespace_run_id` field preserved.

**Illumina filename convention (file_detector.py handles this natively):**
`{SampleName}_S{SampleNumber}_L{Lane}_R{Read}_001.fastq.gz`

### External database search

Researchers search NCBI SRA, GenBank, ENA, and GISAID from within JACKPOT via a second
mode on the search page. JACKPOT backend proxies queries server-side.

`GET /api/v1/external-search/` — accepts database selection + query params, returns
paginated results. Results cached for 30 minutes via `backend/cache.py`.

Actions on results: Import stub to JACKPOT, Add to dataset (reference without importing
files), Open in source database.

**GISAID special case:** requires encrypted credentials in `organizations` table.
Attribution reminder shown before import. GISAID samples imported with
`data_use_terms=controlled_access`, `sharing_level=LAB` by default — can never be PUBLIC.
`gisaid_accession` always stored and visible for attribution.

### NCBI submission (TOSTADAS)

`scripts/portal_to_tostadas.py` converts JACKPOT metadata to TOSTADAS `config.yaml`.
Tier 3 (SUBMITTABLE) required. VADR must pass before submission for viral genomes.
`POST /api/v1/ncbi-submissions/` tracks submission status.

### GISAID export (implemented)

`GET /api/v1/gisaid/export` maps JACKPOT fields to GISAID EpiCoV column names.
`gisaid_export.py` router is fully implemented. Frontend stub needs building.

---

## 23. Federation Architecture

Three progressive levels — each independently useful. `FEDERATION_ENABLED=false`
until Year 2.

### Level 1 — Query federation (Month 2–3)

Registered JACKPOT instances appear as queryable sources alongside NCBI/ENA.

**`federated_instances` table:**
`instance_name`, `org_name`, `instance_url`, `api_key_secret_name` (GCP Secret Manager),
`trust_level` (query/share/full), `min_sharing_level_for_federation`, `is_active`.

Search toggle "Include federated instances" queries partner via `GET /api/v1/samples/`
using federation API key (separate from user JWT). Results are DISCOVERABLE-equivalent:
organism, date, country/state, source_type, quality_tier. No clinical metadata, no files.
Results cached 30 minutes.

Actions on federated results: import stub, open in source, request data sharing (triggers
Level 2 workflow).

### Level 2 — De-identified hub push (Year 2, early)

Hub-and-spoke model. Spoke instances push surveillance data nightly.

**What is shared upward:**
FASTA consensus sequences (presigned URL, 24h), typing results (MLST/cgMLST/HierCC/TB
lineage), AMR profiles (hAMRonization), lineage/clade, organism, date_collected,
country/state, source_type, sector, quality_tier, surveillance_relevant flag.

**What stays local:**
Raw FASTQ, host_age, host_sex, adhs_medsis_id, case_id, collection_facility, host_disease
details, PII fields, access request history.

`push_to_hub_job()` identifies qualifying samples: `surveillance_relevant=TRUE`,
`sharing_level ≥ min_sharing_level_for_federation`, `quality_status ≥ ANALYZABLE`.
Hub creates records with `external_source=spoke_url`, `ingest_method=federation`.

### Level 3 — Bidirectional sharing (Year 2, late)

Cross-instance access requests. Researcher at Org B finds samples at Org A via Level 1
search, requests access. Org A Lab Director approves via same UI as internal requests.
On approval: presigned URLs issued to Org B → background copy job pulls FASTQs →
imported sample retains `external_source` + `originating_lab` attribution. Scrubber runs
on import. Org A can revoke federation key at any time.

### New org-level federation fields

`min_sharing_level_for_federation`, `federation_enabled`, `hub_instance_url`,
`federation_role` (hub/spoke/peer).

---

## 24. Documentation Strategy

Four-layer strategy maintained continuously:

**Layer 1: `docs/CLAUDE.md`** — Claude Code context file. Updated in the same commit as
the code change that motivates it. Read at the start of every Claude Code session.
Contains: current schema version, established patterns, 38 Critical Rules, test baseline,
what's implemented vs stubbed. This is the primary developer context file.

**Layer 2: `jackpot_architecture_v5.md`** (this document) — Updated when major
architectural decisions are made. Not every session. Saved to `docs/` in the repo.

**Layer 3: OpenAPI autodocs** — FastAPI generates interactive docs at `/docs` (Swagger UI)
and `/redoc` automatically from router docstrings and Pydantic models. Write good
docstrings on all router functions. Zero extra effort required.

**Layer 4: `docs/user_guide/`** — One markdown file per major feature area, written from
the researcher's perspective, written alongside feature implementation. This is the source
material for the Year 2 LLM assistant — assistant quality depends entirely on
documentation quality. Defer = poorer assistant.

**`CHANGELOG.md`** at repo root: one line per completed feature, one line per breaking
change.

**Session summary** (`jackpot_session_summary_and_backlog.md`): Design decisions and
backlog. Maintained across chat sessions. Version bumped at end of each session.

---

## 25. Testing Framework

### Setup

```bash
uv add --dev pytest pytest-asyncio pytest-cov testcontainers "moto[s3]" \
    respx factory-boy hypothesis freezegun
```

### Current baseline

- **95 tests, 63.96% coverage** (last verified baseline)
- CI enforces minimum 60% coverage

### Test files

| File | Covers |
|---|---|
| `tests/conftest.py` | testcontainers PostgreSQL; `override_settings` fixture with `reset_engine` |
| `tests/test_validator.py` | Required fields, enums, dates, ranges, Hypothesis fuzz, tier computation |
| `tests/test_epiweek.py` | MMWR and ISO week computation |
| `tests/test_permissions.py` | All six role combinations |
| `tests/test_samples_api.py` | Health check; stub router smoke tests |
| `tests/test_file_detector.py` | All extensions, all naming conventions, multi-lane, nanopore |
| `tests/test_gisaid_export.py` | GISAID column completeness; 400 on empty sample list |
| `tests/test_tostadas_converter.py` | BioSample package by source type; geo_loc_name construction |

### Key testing patterns

`testcontainers` spins up a real PostgreSQL 16 container for each test session.
`override_settings` fixture monkeypatches env vars and calls `get_settings.cache_clear()`
before and after each test — essential for isolating the lru_cache on Settings.
`reset_engine()` disposes the SQLAlchemy engine pool between tests that change
DATABASE_URL.

### Running tests

```bash
uv run pytest                                  # all tests
uv run pytest tests/test_validator.py -v       # specific file, verbose
uv run pytest -k "test_tier"                   # keyword filter
uv run pytest --cov=backend --cov-report=term-missing  # with coverage
uv run pytest --hypothesis-seed=0              # deterministic fuzz tests
```

---

## 26. Development Roadmap

### Month 1 — Core data layer (current focus)

**Already implemented:**
- Bootstrap scripts (bootstrap.sh, write_files.py, write_files_2.py)
- Pre-commit hooks, GitHub Actions CI
- Core backend modules: permissions, config, database, logging, middleware,
  audit, epiweek, file_detector, storage, pagination, main.py
- Auth router (full), GISAID router (full)
- Organizations, labs, projects, users routers (full)
- Domain whitelist, sequencing_labs, tokens, dataharmonizer routers (full)
- Validator, harmonizer modules
- All Streamlit page stubs
- Test suite: 95 tests, 63.96% coverage

**Next (Claude Code sessions):**

- [ ] `POST /api/v1/ingest/upload` — multipart form, tier-aware validate, FASTA-only
      scrub-skip, compute surveillance_relevant, file_detector pairing, stage to MinIO,
      epiweek compute, write samples + sample_files, log audit
- [ ] `POST /api/v1/ingest/signed-url` — issues GCS signed URL, complete endpoint
- [ ] `POST /api/v1/ingest/uri` — validates accessibility, records URI, optional server-side copy
- [ ] `POST /api/v1/ingest/accession` — NCBI E-utilities fetch, background fasterq-dump
- [ ] `POST /api/v1/ingest/csv` — harmonize, bulk tier-aware validate
- [ ] `GET /api/v1/samples/` — search with can_see_sample(), all filters, bulk-select compatible
- [ ] `GET/PATCH /api/v1/samples/{sample_id}` — with can_access_sample()
- [ ] `can_access_sample()` and `can_see_sample()` in guards.py
- [ ] Scrub override request workflow (PENDING_APPROVAL, 48h auto-deny, FASTA auto-skip)
- [ ] Sample access request endpoints + background job
- [ ] Alembic migration for v4.2 columns + new tables
- [ ] Update validator.py for tier-aware validation and surveillance_relevant logic
- [ ] `GET /api/v1/external-search/` with cache.py abstraction
- [ ] `backend/cache.py` — memory/redis abstraction
- [ ] Upload page Streamlit UI (drag-and-drop, metadata form, tier badge, confirmation)
- [ ] Search page Streamlit UI (filters, bulk select, external database mode)
- [ ] Personal dashboard
- [ ] Lab page and Project page (six tabs)

**Month 1 checkpoint:** Upload a sample. Run a search. Retrieve it. Verify epiweek,
sequencing lab validation, audit log, quality tier, scrub queue.

### Month 2 — Pipelines, workspace, access control UI

- [ ] Pipeline schema tables (Alembic migration)
- [ ] Pipeline launch endpoint — POST /api/v1/pipelines/launch with GCP Batch
- [ ] Pipeline event ingestion — POST /api/v1/pipelines/events (Nextflow -weblog target)
- [ ] Pipeline monitoring endpoints + four-tab UI
- [ ] Pipeline -resume endpoint
- [ ] BYOP registration (project_pipelines, lab_pipelines)
- [ ] Pipeline promotion (project → lab → zoo)
- [ ] Seed pipeline zoo (6 initial pipelines)
- [ ] Pipeline config generator (`backend/pipeline_config.py`)
- [ ] `scripts/test_batch.nf` minimal test pipeline
- [ ] Deploy JupyterHub on GKE via Helm chart
- [ ] Local minikube workspace environment for testing
- [ ] Dataset management endpoints
- [ ] Access request workflow UI
- [ ] Archive request workflow UI
- [ ] Notifications system
- [ ] GCP Cost labels on all Batch jobs
- [ ] Real Google OAuth (ENV=gcp)
- [ ] `jackpot-work` GCS bucket with 90-day lifecycle rule

**Month 2 checkpoint:** End-to-end: upload → scrubber → search → launch viralrecon
→ view results → open workspace → analyze in notebook.

### Month 3 — Submissions, analytics, public deployment

- [ ] NCBI BioSample/SRA submission via TOSTADAS (full endpoint)
- [ ] GISAID export frontend (stub → UI)
- [ ] DataHarmonizer tiered template generator
- [ ] Globus integration (deposit-first webhook + identity linking)
- [ ] External database search (NCBI/ENA/GISAID proxy)
- [ ] JSON-LD endpoint for FAIR I1
- [ ] Cloud SQL production setup + PITR + backups (jackpot-iac)
- [ ] GKE production cluster (three node pools, jackpot-iac)
- [ ] Cloud Run deployment + Streamlit
- [ ] Billing dashboard
- [ ] BigQuery ETL pipeline from Cloud SQL (analytics warehouse activation)
- [ ] APGAP data migration (`scripts/migrate_from_apgap.py` run in production)
- [ ] Partner onboarding flow (ADHS demo)

**Month 3 checkpoint:** End-to-end ADHS demo: upload via Globus → viralrecon → MultiQC
→ TOSTADAS NCBI submission → accession returned → GISAID export.

### Year 2

- [ ] React frontend migration (trigger: Streamlit becomes a blocker)
- [ ] jackpot-cli (fifth repo)
- [ ] Phylocanvas tree viewer (phylogenetic_trees table)
- [ ] Phylogenomics dashboard (Nextstrain/Auspice embedded)
- [ ] Hub-and-spoke federation (Level 1 query, then Level 2 push)
- [ ] EnteroBase federation (Warwick for Salmonella/E. coli; DSMZ for TB)
- [ ] JupyterHub Sol HPC batchspawner (ASU-specific)
- [ ] Visual pipeline builder (Data-flo adaptor model reference)
- [ ] Metagenomic orchestration layer (chain mag + taxprofiler + funcscan)
- [ ] LLM support assistant Level 1 (documentation RAG, pgvector in Cloud SQL)
- [ ] LLM support assistant Level 2 (tool-augmented RAG for data-specific questions)
- [ ] GA4GH DRS endpoints for file access

---

## 27. APGAP Migration Guide

### Why the migration is clean

The organizational hierarchy, six roles, Google OAuth flow, analytical dataset and
archive request patterns all map 1:1. The `PermissionGroups` enum string values are
identical. An APGAP user's Google account works in JACKPOT without re-registration.

The hard work is the EAV → typed column transformation: APGAP stores all metadata as
`(Key, Value)` string pairs in the `MetadataTag` system. `migrate_from_apgap.py` reads
APGAP's PostgreSQL, normalizes the key/value tags (organism name normalization is the
hardest part — dozens of variations like "COVID19", "SARS-COV-2", "SARS CoV 2" all
referring to the same organism), maps to JACKPOT typed columns, and creates sample
records at PRELIMINARY (Tier 1). Labs then complete metadata via JACKPOT UI.

### APGAP → JACKPOT field mapping (key fields)

| APGAP Key | JACKPOT field |
|---|---|
| `SAMPLE ID` | `sample_id` |
| `PATHOGEN/ORGANISM NAME` | `organism_name` (normalized to OrganismNameEnum) |
| `TYPE OF EXPERIMENT` | `type_of_experiment` |
| `DATE COLLECTED` | `date_collected` |
| `DATE SEQUENCED` | `date_sequenced` |
| `SEQUENCING LAB (ORIGINATING LAB)` | `sequencing_lab` |
| `COLLECTION FACILITY` | `collection_facility` |
| `SOURCE LOCATION COUNTRY` | `collection_location_country` |
| `SOURCE LOCATION STATE` | `collection_location_state` |
| `ADHS ISSUED ID` | `adhs_medsis_id` |
| `BIOSPECIMEN TYPE` | `biospecimen_type` |
| `REASON FOR SAMPLE COLLECTION` | `reason_for_collection` |
| `SEX` | `host_sex` |
| `AGE (YEARS)` | `host_age` |
| `HOST SPECIES` | `host_species` |
| `DISEASE` | `host_disease` |
| `SOURCE TYPE` | `source_type` (drives sample subclass) |

~95% of APGAP fields have direct JACKPOT equivalents. Remaining 5% are JACKPOT additions
that will be NULL on migrated records at Tier 1.

### Three-phase migration plan

**Phase 1:** JACKPOT becomes the new upload front door. New samples go into JACKPOT.
APGAP stays running for existing data.

**Phase 2:** Run `migrate_from_apgap.py` against APGAP's live PostgreSQL. Always
`--dry-run` first. Records land at PRELIMINARY.

**Phase 3:** Political/organizational decision — APGAP archive-mode (read-only),
eventually off.

```bash
# Dry run first — always
APGAP_DB_URL=postgresql://user:pass@host:5432/apgap_db \
    uv run python scripts/migrate_from_apgap.py --dry-run

# Real migration
APGAP_DB_URL=postgresql://user:pass@host:5432/apgap_db \
    uv run python scripts/migrate_from_apgap.py
```

---

## 28. Critical Rules Quick Reference

Full rules with rationale live in `docs/CLAUDE.md`. This is a summary of the rules
with architectural implications.

### Code patterns (established in routers)

| Rule | Pattern |
|---|---|
| 13 | `from jose import jwt` — not `import jwt` (different library) |
| 14 | Lazy engine pattern — `_engine` is None until first call to `get_engine()` |
| 15 | Stub router pattern — all unimplemented routers return 501, never raise ImportError |
| 16 | Dynamic PATCH via `model_dump(exclude_none=True)` — never overwrite fields not in request |
| 17 | PostgreSQL RETURNING clause on all INSERT/UPDATE — single round-trip |
| 18 | Soft deactivation: `is_active`, `deactivated_at`, `deactivated_by` on orgs/labs/users |

### Data integrity rules

| Rule | Rule |
|---|---|
| 19 | `sequencing_lab` validated against `sequencing_labs` DB table, never a static enum |
| 20 | `file_detector.py` is the only place filename/pairing logic lives — never in routers |
| 21 | `sequencing_labs` linked to `labs` via `sequencing_lab_assignments` join table, not direct FK |

### Pipeline execution rules

| Rule | Rule |
|---|---|
| 25 | Isolated workDir per pipeline run — `gs://jackpot-work/{run_id}/work/` — two runs must never share a prefix |
| 26 | Nextflow config generated per-run by launch endpoint — never a static file |
| 27 | `resourceLabels` required on every GCP Batch job: `jackpot_run_id`, `jackpot_lab`, `jackpot_pipeline` |
| 28 | Minikube is for JupyterHub workspace testing only — full stack stays on Docker Compose |
| 29 | Prefer `PIPELINE_EXECUTOR=gcp_batch` on Apple Silicon — bioinformatics containers are x86-only |
| 30 | Pipeline compute runs on GCP Batch — never submit pipeline tasks as GKE pods |
| 31 | Bulk scrubber submissions go through DB queue in jobs.py — never submit all at once |
| 32 | Scrubber GKE Jobs run on spot nodes (scrubber-pool is preemptible) |

### Infrastructure rules

| Rule | Rule |
|---|---|
| 33 | No per-pod in-memory cache for shared data — use cache.py abstraction (Redis in GKE) |
| 34 | No Celery, no Redis as task broker or result backend |
| 35 | Never disable Cloud SQL PITR |
| 36 | Always run `uv run alembic upgrade head` after any database restore |
| 37 | Never configure GCS buckets manually in the GCP console — Terraform only |
| 38 | Never enable object versioning on `jackpot-work` bucket — fights 90-day lifecycle rule |


---

## 29. Diagram Reference

All diagrams are standalone self-contained HTML files — no internet connection
required after the initial download. Open any file directly in a browser.
Store all files in the same directory as this document (`~/ASU/jackpot/docs/`).

### Architecture & Governance

Built during the April 2026 design sessions. Interactive — click elements to
explore flows, cascade steps, and tier details.

| File | What it shows |
|---|---|
| `jackpot_dataset_model.html` | APGAP physical-copy model vs JACKPOT reference-based three-tier design. Click flow steps and tier cards. |
| `jackpot_metadata_tiers.html` | Quality tiers (PRELIMINARY/ANALYZABLE/SUBMITTABLE) and sharing levels (PRIVATE/LAB/DISCOVERABLE/PUBLIC) as two orthogonal axes. Click the 3×4 matrix to highlight intersections. |
| `jackpot_access_control.html` | `can_access_sample()` and `can_see_sample()` cascade. Select a user type, click ▶ Run check to step through each gate with ALLOW/DENY verdict. |
| `jackpot_data_lifecycle.html` | Scrubber state machine + staged deletion lifecycle. Click any state or stage to expand transitions and approval chain. |
| `jackpot_federation_architecture.html` | Three progressive federation levels (query, hub push, bidirectional). Click each level button to reveal. |

### APGAP Comparison Series

Four-figure series tracing the argument from APGAP's broken EAV model through
to the JACKPOT solution and migration map. Light-themed static diagrams.

| File | What it shows |
|---|---|
| `jackpot_vs_apgap_data_model.html` | APGAP's EAV chain: File → FileMetadataTag → MetadataTag → Key/Value rows. 35+ rows to read one sample, zero type constraints. |
| `jackpot_vs_apgap_fragility.html` | Seven failure modes with real APGAP examples: no controlled vocab, no date normalisation, no type enforcement, duplicate keys, no referential integrity, advisory-only required fields, and the DRAFT backlog. |
| `jackpot_vs_apgap_jackpot_schema_model.html` | JACKPOT's solution: BaseSample typed columns, source-type subclasses (HumanSample, WastewaterSample + 9 more), three-tier quality system replacing the binary DRAFT gate. |
| `jackpot_vs_apgap_migration_map.html` | Full APGAP → JACKPOT migration map: what carries over unchanged, what requires ETL, what is new in JACKPOT. |

### Platform Architecture Mental Models

Seven mental models covering JACKPOT's architecture from schema pipeline through
API layer. Built during the March–April 2026 design sessions.

| File | What it shows |
|---|---|
| `jackpot_schema_pipeline.html` | How the LinkML YAML becomes everything else: Pydantic models, JSON Schema, SQL DDL, and Markdown docs via the generator commands. Full artifact dependency tree. |
| `jackpot_tech_stack.html` | Full technology stack with local vs. production environment mapping, tool-by-tool role descriptions, and the request lifecycle from browser to database and back. |
| `jackpot_ingest_walkthrough.html` | End-to-end ingest pipeline: file upload → `file_detector.py` → `harmonizer.py` → `validator.py` → database write → scrubber queue. All five ingest methods covered. |
| `jackpot_ui_layer.html` | Streamlit frontend architecture: page modules, component organisation, session state, and mock auth vs real OAuth routing. |
| `jackpot_routers_endpoints.html` | Full router inventory: implemented vs. stubbed, HTTP methods and paths, stub pattern (501 responses), and permission guard cascade. |
| `jackpot_api_and_fastapi.html` | FastAPI internals: ASGI lifecycle, request → middleware → router → handler → response chain, OpenAPI doc generation, dependency injection for auth guards. |
| `jackpot_eav_vs_typed_columns.html` | Direct side-by-side comparison of APGAP's EAV pattern vs JACKPOT's typed column approach with concrete before/after examples. |

### Developer Reference

Python fundamentals and developer tooling diagrams. All use real JACKPOT code
as examples throughout.

| File | What it shows |
|---|---|
| `jackpot_dictionaries.html` | What a Python dict is, the filing cabinet analogy, three creation patterns, and every dict operation used in JACKPOT including `model_dump`, `dict(zip(cols, row))`, and `.get()`. |
| `jackpot_functions_type_hints.html` | Anatomy of a function, the three parameter kinds, type hints table covering every syntax in JACKPOT, and four real signatures dissected: `validate_sample`, `execute_query`, `harmonize_row`, `upload_fileobj`. |
| `jackpot_decorators.html` | How Python decorators work — `@router.get()`, `@pytest.fixture`, `@cache`, `@contextmanager`. Before/after syntax, stacking decorators, every decorator used in JACKPOT. |
| `jackpot_classes_and_instances.html` | Class vs. instance, blueprint analogy, anatomy of a class, dot notation table, `@dataclass`, and the inheritance trees used in JACKPOT (`BaseSettings → Settings`, `HTTPException`, etc.). |
| `jackpot_exception_handling.html` | `try / except / finally`, `raise HTTPException`, when to raise vs. return, exception chaining, and every error-handling pattern in JACKPOT's routers and database layer. |
| `jackpot_sql_basics.html` | Spreadsheet analogy, eight key tables with FK relationships, SELECT / INSERT / UPDATE / RETURNING patterns, `:params` rule, JOIN syntax. |
| `jackpot_testing_with_pytest.html` | What a test is, the `assert` statement, pytest output, the fixture chain (`postgres_container → test_db_url → override_settings → client`), coverage visualisation, four key test patterns. |
| `jackpot_github_ci_pipeline.html` | Pre-commit hook flow, CI triggers, the six workflow steps annotated, reading GitHub's ✓/✗/● badges, diagnosing failures, three-tier branch strategy. |
| `jackpot_environment_variables_and_configuration.html` | `pydantic-settings`, the `Settings` class, `get_settings()` with `@cache`, the `override_settings` fixture, and every env var grouped by local vs. production value. |
| `jackpot_data_standards_explorer.html` | Interactive mapping of PHA4GE, GA4GH, FAIR, MIxS, NCBI BioSample, GISAID, MMWR, and NWSS to specific JACKPOT schema fields. |
| `jackpot_directory_structure.html` | Three-layer diagram: `~/ASU/jackpot/` workspace → four git repos → contents of `jackpot-backend/`. Submodule doubling and `git schema-update` alias workflow. |
| `jackpot_backend_directory_contents.html` | Every file inside `backend/` — top-level modules, `auth/` package, full `routers/` listing. Gray = written by `write_files.py`. Amber = Session 2 additions to be written. |
