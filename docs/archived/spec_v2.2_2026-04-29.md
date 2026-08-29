> **Status:** History — JACKPOT platform specification as of v2.2 (2026-04-29).
> Superseded 2026-08-28. Architecture moved to `docs/architecture.md`; decisions
> split into `docs/adr/`; glossary to `CONTEXT.md`; open work to
> `active_backlog.yaml`; completed ledger to `todo.md`. Retained for history only —
> every status claim below is stale and several contradict the live Critical Rules.

# JACKPOT — Project Specification

**Version:** 2.2
**Last updated:** 2026-04-29 (post-BYOP and eukaryotic pipelines design session)
**Status:** Month 1 + most of Month 2 complete — Phase 21 UI page triage closing out, P0d monorepo migration starting now. Pivot to independence + AGPL-3.0 + multi-deployment-target architecture decided April 2026; cleanup phases (6.1–11) complete. Three architectural design documents now drive the post-P0d roadmap: `jackpot_pathoplexus_loculus_overview.md` (peer-platform adoption — Phase 26), `jackpot_cdc_dmi_stlt_overview.md` (US public-health-data ecosystem alignment — Phase 27), `byop_and_eukaryotic_design.md` (BYOP infrastructure for P0f, eukaryotic pathogen pipelines for Phase 28).
**Audience:** Claude Code autonomous agent + the maintainer

---

## 1. Project Goal

>
> - **A** Self-hosted commodity infrastructure (laptop through agency datacenter; ephemeral or persistent; single-lab, multi-lab, or multi-org)
> - **B** HPC (Apptainer + Slurm + institutional storage + LDAP/SAML)
> - **C** Single-org cloud (GKE/EKS/AKS, cloud-native)
> - **D** CI / e2e test harness
>
> Federation membership, hosted-SaaS multi-org tenancy, Indigenous data sovereignty (CARE-aligned governance), and network-denied / store-and-forward transport are runtime configurations applied to scenarios A/B/C — not separate install scenarios. See `docs/architecture.md` §3 for scenario detail, §22 for sovereignty-as-runtime-policy, and §22.7 for transport-as-runtime-policy.
>
>
> **Phase chain:** Phase 21 (UI close-out) → P0d (monorepo migration, in progress) → P0e (jackpot init CLI) → Phase 24.5 (architectural design lockdown — sovereignty deletion + BYOP/eukaryotic schema decisions before P0b) → P0f (BYOP infrastructure — Phase 24.7 in todo.md) → P0b (Schema v5.0 with all 24.5 lockdowns + instances/tenants/federated_peers) → P0c (multi-tenancy middleware + sovereignty deletion implementation) → P1–P5 (operator-type configurability, federation, governance, reference deployments, new-needs integration). Tracked-but-not-scheduled: Phase 25 (Month 3 stretch — admin UI, JupyterHub, GCP prod), Phase 26 (Pathoplexus/Loculus 34-item adoption backlog), Phase 27 (CDC DMI / STLT / CARE 14-item alignment backlog), Phase 28 (10 default eukaryotic pipelines + parsers + dashboards, internally tier-prioritized).
>
> **Source-of-truth design documents:**
>
> - `jackpot_pathoplexus_loculus_overview.md` — comparative analysis between JACKPOT and the open-source pathogen-genomics ecosystem (Pathoplexus/Loculus + 8 peer platforms). Drives Phase 26.
> - `jackpot_cdc_dmi_stlt_overview.md` — alignment with US public-health-data ecosystem (CDC DMI / North Star Architecture, STLT operators, CARE Principles for Indigenous data sovereignty). Drives Phase 27 and the sovereignty-aligned runtime policy capabilities described in `docs/architecture.md` §22.
> - `byop_and_eukaryotic_design.md` — multi-engine BYOP architecture (Nextflow + Snakemake + WDL + manifest-wrapped scripts) with two-stage validation gating, plus full-parity eukaryotic pathogen support across 8 pathogen groups. Drives P0f and Phase 28.

Build **JACKPOT** — a pathogen genomics platform for genomic epidemiology, bioinformatics analysis, and public-health research.

The platform enables public health labs to:

- Ingest raw sequencing data (FASTQ, FASTA) with structured metadata
- Validate metadata against a tiered quality model (PRELIMINARY / ANALYZABLE / SUBMITTABLE)
- Scrub human reads from sequencing data before analysis
- Launch bioinformatics pipelines (nf-core, GHRU) against their samples
- Export data to GISAID, NCBI BioSample/SRA, and TOSTADAS
- Search, filter, and analyze samples across the platform
- Control data access with a fine-grained sharing and governance model

### 1.1 Single entry point for genomic data into a public-health agency

JACKPOT exposes a small, fixed set of ingest paths and treats them as
**the single entry point for genomic data into a public-health agency**.
This is JACKPOT's narrowing of the CDC North Star Architecture's "CDC
Front Door" pattern to the genomics domain — instead of every
sequencing lab inventing its own routing into the agency's data
estate, every operator has the same six paths in:

1. **GUI single upload** — Streamlit researcher upload page
2. **CSV batch ingest** — schema-validated CSV with semicolon-
   delimited file references per sample (`POST /api/v1/ingest/csv`)
3. **Globus endpoint sync** — operator-configured Globus collection
4. **API direct upload** — `POST /api/v1/ingest/upload` with signed
   URL handoff to the operator's storage backend
5. **CLI/SDK programmatic ingest** — the `jackpot` CLI and SDK at
   `cli/`
6. **External-repo import** — SRA / ENA pull via `pipelines/insdc-
   ingest/` (Phase 26 backlog item B-LOC-2)

All six paths converge at the same gate: `validator.py` →
`epiweek.py` → `dlp_scanner.py` → `file_detector.py` → `storage.py`
write → audit log entry. The operator gets one place to enforce
policy, one audit surface, and one schema to keep current. Grant
narratives that reference North Star alignment can point at this
section.

### 1.2 Alignment with WHO Global Genomic Surveillance Strategy 2022-2032

The WHO strategy defines five objectives that JACKPOT's deployment scenarios
serve. Each scenario advances a subset of objectives:

| Scenario | Description | Obj. 1 (tools) | Obj. 2 (workforce) | Obj. 3 (data utility) | Obj. 4 (connectivity) | Obj. 5 (readiness) |
|---|---|---|---|---|---|---|
| A | Self-hosted commodity (laptop through agency, ephemeral or persistent, single-lab to multi-org) | ✓ | ✓ | ✓ | ✓ | ✓ |
| B | HPC (Apptainer + Slurm + institutional storage) | ✓ | ✓ | ✓ | • | ✓ |
| C | Single-org cloud (GKE/EKS/AKS) | ✓ | ✓ | ✓ | • | ✓ |
| D | CI test | | | | | |

✓ = primary mode; • = partial / context-dependent

Scenario A's range from a single-user laptop through a multi-lab agency datacenter means it collectively serves all five WHO objectives — different configurations within A advance different objectives. Federation participation (Obj. 4 connectivity) is a runtime configuration available to A, B, and C; it is the primary operating mode for some A deployments and a context-dependent capability for B and C.

**Non-functional requirement: 7-day turnaround.** The WHO strategy defines
"timely" as triggering genomic sequencing within seven days of event or
pathogen detection. JACKPOT's pipeline orchestration (ingest → scrub → DLP →
analysis → result publication) must support end-to-end latency under this
target when deployed for surge-event use. The 6-state lifecycle of
`ingest_scrubber.nf` and the `SCRUBBER_MAX_CONCURRENT=10` concurrency setting
are dimensioned for this target.

---

## 2. Current Baseline (post-P0e — May 2026)

- **904+ tests passing, 84%+ coverage** (workspace-wide: backend +
  schema + cli)
- CI threshold: 80% — must never fall below this. (The post-P0d 39%
  number we briefly carried was a pytest-cov misconfiguration; see
  `docs/learnings.md` "Coverage measurement bug" entry.)
- The `jackpot init` CLI (P0e) bootstraps any of the 4 install
  scenarios (A/B/C/D) from `git clone` to running stack in under 10 minutes —
  see `docs/install/quickstart.md`.
- Health check local: `curl http://localhost:8000/health` →
  `{"status":"ok","version":"5.0.0","project":"JACKPOT","database":"connected"}`
- Health check staging (in-cluster via port-forward): same response
- All 27 database tables loaded in PostgreSQL via Alembic migrations
- `development` and `main` branches track together; `staging` branch is the
  deploy trigger for GCP
- All 21 routers registered in `main.py`; 14 are fully implemented (see
  Section 4.2); the rest are stubs for Month 2/3
- Seed data loaded: 75 reportable organisms, 3 sequencing labs
- GCP staging live at project `jackpot-staging-project`, region `us-central1`
- Streamlit UI renders locally at `http://localhost:8501` with all 9
  researcher pages in the sidebar and mock auth working

---

## 3. Architecture Constraints

These constraints are non-negotiable. Every implementation must respect them.

### 3.0 Layer-cake positioning — JACKPOT integrates, does not replace

```text
┌─────────────────────────────────────────────────────────────┐
│  CASE-LEVEL EPIDEMIOLOGY                                    │
│  NBS, MAVEN, Trisano (state-specific)                       │
│  Receives: case reports, lab results, demographic data      │
│  Owns: the case as the epidemiologic unit                   │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ ECR/ELR via TEFCA
                            │
┌─────────────────────────────────────────────────────────────┐
│  ELECTRONIC CASE REPORTING / LAB REPORTING ROUTING          │
│  Routes structured FHIR/HL7 messages from healthcare to PHA │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ HL7 / FHIR
                            │
┌─────────────────────────────────────────────────────────────┐
│  PUBLIC HEALTH LABORATORY OPERATIONAL SYSTEMS               │
│  LIMS (LabWare, STARLIMS, etc.)                             │
│  Owns: the specimen as the operational unit                 │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ specimen → sequencing
                            │
┌─────────────────────────────────────────────────────────────┐
│  ★ JACKPOT ★                                                │
│  Pathogen genomics platform                                 │
│  Owns: the sample (specimen + sequencing run + analyses)    │
│  Provides: typing, AMR, phylogeny, outbreak detection       │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ pipeline results
                            │
┌─────────────────────────────────────────────────────────────┐
│  DOWNSTREAM REPOSITORIES + ANALYSIS                         │
│  NCBI Pathogen Detection, GISAID/ENA, Pathoplexus,          │
│  Pathogenwatch, Nextstrain, GenSpectrum                     │
└─────────────────────────────────────────────────────────────┘
```

JACKPOT lives between the LIMS layer and the downstream-analysis
layer. It is **fed by** the LIMS and **feeds** the downstream
platforms. JACKPOT integrates with NBS, eCR, AIMS, and the rest of
the public-health-data stack; it does not try to absorb any of their
scope. See `docs/jackpot_cdc_dmi_stlt_overview.md §9` for the
a peer system at a different layer (not a competitor).

### Language and Tools

- Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2
- `uv run` for all Python commands — never `pip`, never activate venv
- `gac "type: description"` for all commits (runs ruff fix/format then commits)

### Database

- PostgreSQL (local dev via Docker Compose) / Cloud SQL PostgreSQL (production)
- All schema changes go through Alembic migrations — `db/SCHEMA.sql` is
  a read-only reference snapshot, never the source of truth
- After any schema change: regenerate `backend/models_generated.py` with
  `gen-pydantic --pydantic-version 2` then apply the boolean keyword patch
  (Critical Rule 20)
- `alembic upgrade head` reaches the full schema from an empty database
  via the baseline migration `5adf11b77c19` (Critical Rules 44 + 52,
  Q-9 closed).

### API

- All routes prefixed `/api/v1/` — set in the router's `prefix`, not in `main.py`
- All responses use `backend/responses.py` helpers: `success()`, `success_list()`,
  `success_message()`, `error()`
- All list endpoints use `backend/pagination.py` — never raw OFFSET/LIMIT
- All state-changing endpoints call `log_audit()` from `backend/audit.py`
- All PATCH endpoints use `model_dump(exclude_none=True)` for partial updates
- All INSERT/UPDATE use PostgreSQL `RETURNING *` — never SELECT after write

### Authentication

- `get_current_user` / `require_platform_admin` / `require_lab_director` /
  `require_lab_access` from `backend/auth/guards.py`
- `from jose import jwt` — never `import jwt` (package is `python-jose`)
- Local dev: mock user via `MOCK_USER_EMAIL` in `docker-compose.yml` — set
  on **both** the `api` and `ui` services (the UI ships
  `X-Mock-User-Email` as a parity header, but the actual identity lookup
  happens on the API by reading `MOCK_USER_EMAIL` from its environment)

### Storage

- All GCS/MinIO operations go through `backend/storage.py` — routers never
  call boto3 directly
- Local dev: MinIO via `STORAGE_ENDPOINT=http://minio:9000` (the
  storage factory auto-selects S3-compatible mode when an endpoint is
  set); production: GCS via leaving `STORAGE_ENDPOINT` unset (factory
  defaults to GCS). The earlier `STORAGE_BACKEND` env var was a
  documentation fiction never consumed by `config.py` — the actual
  switch is `storage_endpoint` set vs unset.

### Business Logic Constraints

  (see Critical Rule 1)
- `sequencing_lab` validated at runtime against `sequencing_labs` DB table
  — not a static enum
- `surveillance_relevant` computed only by `compute_surveillance_relevant()`
  in `validator.py`
- `quality_status` computed only by `compute_quality_status()` in `validator.py`
- Epiweeks computed only by `compute_epiweeks()` in `epiweek.py` — called at
  ingest, never by user
- File parsing lives only in `backend/file_detector.py` — nowhere else
- `scrub_status = SKIPPED` set only in validator.py (FASTA-only auto-skip)
  or scrub override workflow
- One CSV row = one sample — files semicolon-delimited in a single cell
- `external_case_id` required for HumanSample only
- `active` column for orgs/labs; `is_active` for all other tables
- Background jobs use APScheduler (local) / Cloud Scheduler (production) —
  no Celery, no Redis as task broker

### Database Dependency Injection

- Routers use `get_db_dep()` with `Depends()` for database access
- All writes share one transaction via `conn` parameter:
  `execute_write(..., conn=db)`, `log_audit(..., db_conn=db)`,
  `create_notification(..., db_conn=db)`

### Configuration — list-typed settings

- **NEW (Session 5 lesson):** `list[str]` Settings fields need explicit
  `Annotated[list[str], NoDecode]` + `field_validator` to accept JSON arrays,
  comma-separated strings, and empty strings. pydantic-settings otherwise
  tries to JSON-parse every env-var string value. See Critical Rule 43
  (Phase 20 Q-10 on the todo) and the code pattern in Section 9.

### Cross-repo imports — `nf/shared`

- **NEW (Session 5 lesson):** `backend/routers/pipelines.py` imports
  `RESULT_SCHEMAS` from the `jackpot-nf` submodule via
  `sys.path.insert(0, str(_NF_ROOT))`. This is fragile — any tool that
  imports the router without `nf/` available crashes. Permanent fix (Phase
  20 Q-11) is to move the schemas into the backend package. Until then,
  every image that runs the API must `COPY nf/ ./nf/`. See Critical Rule 44.

### Architectural design lockdowns gating P0b

Two design documents must be locked in before P0b touches the schema:
`docs/architecture/sovereignty-compliant-deletion.md` (sovereignty-
compliant deletion design — Phase 24.5) and
`docs/byop_and_eukaryotic_design.md` (multi-engine BYOP
infrastructure plus full-parity eukaryotic pathogen support — Phase
24.5 schema scope and Phase 24.7 / P0f-BYOP behavior scope). P0b's
migration plan must accommodate every column, enum, table, and
constraint enumerated in §12 of the sovereignty design and §§7 + 12 of
the BYOP/eukaryotic design.

---

## 4. What's Built — Month 1 + Month 2 Status

### 4.1 Pre-Session Fixes (COMPLETE — all 16 items)

These blocking bugs were resolved before any router session began:

1. ✅ `tests/conftest.py` Alembic migrations — `initialize_test_db` now
   runs `alembic upgrade head`.
2. ✅ `routers/auth.py` module-level settings — moved inside function scope.
3. ✅ `valid_human_sample` fixture — "Example Lab" references fixed.
4. ✅ `active` vs `is_active` — CLAUDE.md note added; routers follow the
   convention (orgs/labs use `active`, everything else `is_active`).
5. ✅ JWT refresh endpoint — `POST /api/v1/auth/refresh` shipped in PR #22 (P1, commit ba03143) with single-use rotation, replay detection, refresh_tokens table, and daily cleanup. Closes the P0e C.5 deferral and the Phase 22 review gap.
6. ✅ Full test suite — passing, coverage ≥ 80% (post-P0e).
7. ✅ `log_audit()` `db_conn` forwarding — transactional cohesion.
8. ✅ `create_notification()` `db_conn` forwarding — same.
9. ✅ `execute_query()` `conn=` parameter added.
10. ✅ JWT type-claim validation in `guards.py`.
11. ✅ `/health` returns 503 when DB unavailable.
12. ✅ APScheduler job intervals/IDs corrected.
13. ✅ Validator `BASE_REQUIRED` split into tier-specific lists.
14. ✅ `Isolate` source type added to validator.
15. ✅ Validator docstring v4.1 → v4.4.
16. ✅ CORS origins configurable via `settings.cors_origins` in `main.py`.

### 4.2 Router Sessions A–H (COMPLETE)

| Session | Router                          | Status          | Notes                                            |
|---------|---------------------------------|-----------------|--------------------------------------------------|
| A       | `organizations`                 | ✅ Complete     | 7 endpoints + tests                              |
| B       | `labs` + `lab_membership`       | ✅ Complete     | 9 endpoints, full membership lifecycle           |
| C       | `users`                         | ✅ Complete     | `/me`, CRUD, self-update guardrails              |
| D       | `domain_whitelist`              | ✅ Complete     | 3 endpoints + tests                              |
| E       | `sequencing_labs`               | ✅ Complete     | 6 endpoints, assignments to JACKPOT labs         |
| F       | `tokens`                        | ✅ Complete     | bcrypt token hashing, project-name filter on projects |
| G       | `ingest`                        | ✅ Complete     | 3 endpoints: upload, csv, globus                 |
| H       | `samples`                       | ✅ Complete     | 6 endpoints: list, get, update, archive, files, download |

### 4.3 Additional Month 1 Work (COMPLETE)

- ✅ `projects` router (stub → full) — with `?name=` filter for CLI
- ✅ `dataharmonizer` router (stub → full) — 94% coverage
- ✅ JWT refresh endpoint
- ✅ `tests/conftest.py` improvements — no more `contextlib.suppress`

### 4.4 Month 2 — Sessions I–Q Status

| Session | Work                                 | Status       | Notes                                            |
|---------|--------------------------------------|--------------|--------------------------------------------------|
| I       | jackpot-nf plugin + result router    | ✅ Complete  | Result registration endpoint live                |
| J       | Viral pipeline parsers               | ✅ Complete  | Cecret, viralrecon, walkercreek — 79 tests       |
| K       | Bacterial isolate parsers            | ✅ Complete  | bactopia, Grandeur, mycosnp-nf, tb-profiler      |
| L       | Metagenomic parsers                  | ✅ Complete  | nf-core/mag, nf-core/taxprofiler                 |
| M       | pathogensurveillance + shared        | ✅ Complete  | Version pinned 1.1.0, cross-parser AMR validator |
| N       | pipelines router                     | ✅ Complete  | 10 endpoints: launch, events, monitor, resume, BYOP, promotion |
| O       | sample_access router                 | ✅ Complete  | Request/approve/deny, grants, expiry job         |
| P       | Streamlit researcher pages           | 🟡 Partial   | All 9 pages built; rendering verified (UI-A); UI-B→UI-F triage pending |
| Q       | GCP staging environment              | 🟡 Partial   | Q-1 through Q-4, Q-6, Q-7 done; Q-5 (E2E pipeline test) and Q-8 (tag) blocked on Phase 20 debt |

**Net new Month 2 modules:**

- `backend/dlp_scanner.py` — Cloud DLP metadata PII scanner, hard-gate for
  `scrub_status` lifecycle
- `backend/pipeline_results_loader.py` — Python-side translator for
  nf-iridanext weblog payloads → typed result tables (Option C unchanged
  plugin + loader)
- `backend/pipeline_config.py` — per-run Nextflow config generator
- `backend/template_generator.py` + `routers/templates.py` — schema-driven
  CSV template generator
- `backend/notifications.py` — in-band notification helper (full router
  deferred to Month 3)

---

## 5. Router Specifications

> These specifications document **what was built** in Sessions A–H. They
> remain the authoritative reference for endpoint behavior — any future
> change must preserve these semantics or explicitly update this section.

### Session A — organizations

**Endpoints:**

- `GET /api/v1/organizations/` — paginated list (Platform Admin only)
- `POST /api/v1/organizations/` — create org (Platform Admin only)
- `GET /api/v1/organizations/{id}` — get org (Platform Admin or org member)
- `PATCH /api/v1/organizations/{id}` — partial update (Platform Admin only)
- `DELETE /api/v1/organizations/{id}` — soft delete, set `active=False` (Platform Admin only)

**Key rules:**

- Use `active` column (not `is_active`) for orgs
- `log_audit()` on all writes with `CREATE_ORG` / `UPDATE_ORG` actions
- Partial update via `model_dump(exclude_none=True)`

**Tests:** CRUD round-trip, role enforcement (non-admin gets 403), pagination,
soft delete.

---
---

## Phase P0f Specification — File references

> **Status:** Specification — implementation tracked in `todo.md` Phase P0f.
> Lands schema, endpoints, and modules required for in-place file
> registration with content-hash deduplication.

### Schema additions

New enum `file_storage_state` in `schema/schema/jackpot_schema.yaml`:

| Value | Meaning | Lifecycle owner |
|---|---|---|
| `EXTERNAL` | URI not under JACKPOT control (default for ingest) | Operator/user |
| `MANAGED` | JACKPOT-owned storage; full lifecycle | JACKPOT |
| `MIRRORED` | Managed copy backed by external original | JACKPOT (with origin tracking) |
| `STAGED` | Temp copy for a specific pipeline run; auto-cleaned | JACKPOT |
| `BROKEN` | External file no longer accessible (terminal) | n/a |

**Existing `sample_files` table extended with P0f columns:**

| Column | Type | Notes |
|---|---|---|
| `content_hash` | VARCHAR(64) | SHA-256 hex; UNIQUE when non-null; nullable until full hash computed |
| `head64k_hash` | VARCHAR(64) | Cheap fingerprint piece (first 64 KB) |
| `tail64k_hash` | VARCHAR(64) | Cheap fingerprint piece (last 64 KB) |
| `storage_state` | file_storage_state | NOT NULL DEFAULT 'EXTERNAL' |
| `alternate_uris` | TEXT[] | Same content at multiple URIs |
| `first_seen_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| `last_verified_at` | TIMESTAMPTZ | Updated by verification job |
| `last_verification_status` | VARCHAR(32) | OK, MISSING, SIZE_CHANGED, READ_ERROR |
| `retention_policy` | VARCHAR(32) | STANDARD, LONG_TERM, EPHEMERAL |
| `original_uri` | TEXT | For MIRRORED — the external source |
| `staged_for_run_id` | UUID | For STAGED — the pipeline run that owns it |
| `updated_at` | TIMESTAMPTZ | NOT NULL, maintained by trigger |

Existing columns (`uri`, `raw_uri`, `filename`, `file_size_bytes`,
`md5`, `file_type`, `library_layout`, `read_direction`, `lane`,
`chunk_index`, `paired_file_id`, `scrub_status`, `pii_scan_status`,
`ingest_method`, `ingest_timestamp`, `is_deleted`, `deleted_at`)
are unchanged. P0f does not introduce a separate `file_references`
table; the existing `sample_files` serves the dedup-primitive role
with the new columns.

Deprecated columns on `samples` (kept for one release with backfill
trigger): `fastq_r1_uri`, `fastq_r2_uri`, `long_read_uri`, `assembly_uri`.

### New endpoints

**POST `/api/v1/ingest/register`** — Path/URI-only registration. No file
upload body; metadata + URI(s) only. Authenticated users may register
files into projects they have access to.

Request body:

```json
{
  "sample_metadata": {...},
  "files": [
    {"role": "R1", "uri": "file:///srv/seq/runs/240501/sample01_R1.fastq.gz",
     "storage_intent": "EXTERNAL"},
    {"role": "R2", "uri": "file:///srv/seq/runs/240501/sample01_R2.fastq.gz",
     "storage_intent": "EXTERNAL"}
  ]
}
```

`storage_intent` values: `EXTERNAL` (default), `MANAGED`, `MIRRORED`.

Response: standard `success` envelope with the registered sample plus
`sample_files` summaries (one per file).

**POST `/api/v1/files/{file_id}/promote`** — Change storage state.
Body: `{"to": "MANAGED" | "MIRRORED", "retention_policy": "..."}`.
Returns 202 Accepted with a job ID; copy runs as a background job.

**GET `/api/v1/files/{file_id}`** — Retrieve a sample_files row and
the samples that reference it.

**GET `/api/v1/files/`** — Paginated list with filters: `storage_state`,
`broken_only`, `project_id`. Standard pagination convention.

**POST `/api/v1/files/{file_id}/verify`** — Force re-verification of
a single file. Useful from the UI when a user has just put a missing
file back.

### New modules

**`backend/file_fingerprint.py`** —
`cheap_fingerprint(uri) -> tuple[int, str, str]`
returning `(size_bytes, head64k_sha256, tail64k_sha256)`. Reads only
the first and last 64 KB. Implementations per scheme: `file://` via
`os.open`/`os.pread`; `gs://` and `s3://` via Range requests through
`backend/storage.py`; `sra://` via NCBI metadata API. Treats gzip/BGZF
content transparently — fingerprints compressed bytes, not decompressed.

**`backend/file_references.py`** — CRUD operations and dedup logic.
`register_file(uri, storage_intent, conn) -> SampleFile`. Checks for
existing rows with matching cheap fingerprint before INSERT; appends
to `alternate_uris` on dedup hit. All writes accept `conn=db` to
participate in caller transactions.

**`backend/jobs/file_jobs.py`** — Two new APScheduler jobs:

- `compute_full_content_hash` — finds rows with `content_hash IS NULL`,
  streams full SHA-256 in 8 MB buffers, reconciles fingerprint
  collisions. Default interval 5 min; configurable via
  `Settings.full_hash_interval_seconds`. Honors
  `Settings.skip_remote_full_hash` for slow networks.
- `verify_file_references` — re-stats `EXTERNAL` and `MIRRORED` rows,
  updates `last_verified_at` and `last_verification_status`.
  Transitions to `BROKEN` on missing or size-changed files, with
  `log_audit()` and notification emit. Default interval 24 hours.

### Key rules

- `EXTERNAL` is the default storage_state for any registered file.
- `file_detector.py` remains the sole owner of file-type and naming
  logic; `file_fingerprint.py` adds hashing only — never duplicates
  file-type detection.
- Pipeline outputs default to `MANAGED`; pipeline inputs are not
  state-transitioned by running a pipeline.
- `pipeline_results` rows remain immutable and append-only — file
  references attached to results are new `sample_files` rows, not
  mutations of input rows.
- Pre-launch verification reads `sample_files.storage_state` for every
  input row of every requested sample and refuses the launch with
  `400 BROKEN_INPUTS` if any row is in `BROKEN` state. This is a fast
  read of the verification job's last-known state — not a re-stat at
  launch time. Stronger guarantees come from operator-tunable knobs:
  shorten `Settings.verification_interval_seconds` or trigger
  `POST /api/v1/admin/jobs/verify_file_references/run` before a
  critical launch. The error response includes a `broken_files` list
  (with `sample_files_id`, `sample_id`, `uri`,
  `last_verification_status`) and a `suggestion` field telling the
  user how to unblock.
- All writes participate in caller transaction via `conn` parameter
  (matches existing `execute_write` and `log_audit` conventions).
- Audit actions added: `REGISTER_FILE`, `DEDUP_FILE`, `PROMOTE_FILE`,
  `VERIFY_FILE_FAILED`, `MARK_FILE_BROKEN`.
- New error code `FILE_UNREACHABLE` (HTTP 400) — returned by
  `/api/v1/ingest/register` when a URI cannot be read (and by any
  future ingest path that does an at-ingest cheap fingerprint).
- The success envelope (`backend/responses.py::success`) gains an
  optional top-level `warnings` array carrying non-fatal advisories.
  Used by `/api/v1/ingest/csv` to surface the EXTERNAL-by-default
  behavior change when the `storage_intent` column is absent.
- See Critical Rules 57 (no copy on ingest) and 58 (sample_files is
  the dedup primitive).

### Tests

- Unit tests for `cheap_fingerprint()` covering local files, gzip, BGZF,
  mocked `gs://`, mocked `s3://`, mocked `sra://`.
- Unit tests for the dedup path: same fingerprint produces one
  `sample_files` row referenced by multiple samples.
- Integration tests for both ingest paths (`/api/v1/ingest/csv` and
  the new `/api/v1/ingest/register`) covering all three storage intents.
- Integration test for `verify_file_references` marking a file
  `BROKEN` when it disappears from disk.
- Integration test for pipeline launch refusing to start with a
  `BROKEN` input.
- End-to-end test in `tests/e2e/`: register `EXTERNAL`, run a fixture
  pipeline, verify the input file is still `EXTERNAL` and only outputs
  are `MANAGED`.

---

## Phase P0g Specification — Execution profiles

> **Status:** Specification — implementation tracked in `todo.md` Phase P0g.
> Pipeline executor selection becomes a per-run choice driven by
> operator-configured profiles. Pairs with P0f (file references) to
> unlock scenarios B + Slurm and C.

### Schema additions

New class `execution_profiles`:

| Field | Type | Notes |
|---|---|---|
| `profile_id` | UUID | PK |
| `name` | string | UNIQUE within deployment |
| `executor_type` | enum | `LOCAL`, `SLURM`, `PBS`, `LSF`, `GCP_BATCH`, `AWS_BATCH`, `KUBERNETES` |
| `container_engine` | enum | `DOCKER`, `APPTAINER`, `SINGULARITY`, `NONE` |
| `work_dir` | string | Path or `gs://` / `s3://` URI for work directory |
| `config_overrides` | JSON | Executor-specific fields (account/partition/QOS/project/region/etc.) |
| `is_default` | boolean | At most one row may have `is_default=true` |
| `created_by_id` | integer | FK users |
| `created_at` | datetime | NOT NULL |
| `active` | boolean | Soft delete via `active=false` |

New association class `pipeline_default_profile`:

| Field | Type | Notes |
|---|---|---|
| `pipeline_id` | UUID | FK pipelines |
| `profile_id` | UUID | FK execution_profiles |
| `priority` | integer | Lower = preferred when multiple match |

UNIQUE constraint: `(pipeline_id, profile_id)`.

### New endpoints

**GET `/api/v1/profiles/`** — Paginated list of execution_profiles
visible to the requesting user. All authenticated users may list;
only Platform Admin or the operator may create.

**POST `/api/v1/profiles/`** — Create a new profile (Platform Admin
only). Body shape mirrors the schema fields.

**GET `/api/v1/profiles/{profile_id}`** — Get a single profile.

**PATCH `/api/v1/profiles/{profile_id}`** — Update (Platform Admin
only). Partial update via `model_dump(exclude_none=True)`.

**DELETE `/api/v1/profiles/{profile_id}`** — Soft delete via
`active=false`. Refused if any pipeline still has it as a default;
the response lists the blocking pipelines.

**POST `/api/v1/profiles/{profile_id}/test`** — Submit a fixture
single-process Nextflow job through the profile to verify end-to-end
reachability. Used by `jackpot doctor` and the UI's "Test connection"
button. Returns 202 with a job ID.

**POST `/api/v1/pipelines/{pipeline_id}/default-profiles`** —
Associate a profile as default for a pipeline.
Body: `{"profile_id": "...", "priority": 1}`.

**Updated** `POST /api/v1/pipelines/{pipeline_id}/launch`: now accepts
optional `profile_name` (or `profile_id`) in the request body. If
omitted, resolution order is:

1. Pipeline's first matching default profile by priority.
2. Deployment's `is_default=true` profile.
3. Error `400 NO_PROFILE_AVAILABLE` listing configured profiles.

If `profile_name` is provided but the profile is missing or inactive,
return `400 PROFILE_NOT_FOUND` with the list of available names.

### New modules

**`backend/pipeline_config/profile_renderer.py`** —
`render_nextflow_config(profile, pipeline, run_id) -> str`. Selects the
right Jinja2 template based on `profile.executor_type`, layers in
profile fields and pipeline-specific overrides, returns the full
`nextflow.config` body. The launch endpoint writes this to
`<work_dir>/runs/<run_id>/jackpot_run.config` and passes
`-c jackpot_run.config` to Nextflow.

**`backend/pipeline_config/profile_templates/`** — One Jinja2 template
per executor type:

profile_templates/
├── base.config.j2          # shared settings (process defaults, plugins)
├── local.config.j2
├── slurm.config.j2
├── pbs.config.j2
├── lsf.config.j2
├── gcp_batch.config.j2
├── aws_batch.config.j2
└── kubernetes.config.j2

Each template extends `base.config.j2` and renders the executor-specific
block. Container-engine-aware: when `container_engine=APPTAINER`, the
rendered config sets `apptainer.enabled=true` and disables Docker; vice
versa for `DOCKER`.

**`backend/pipeline_config/cost_estimator.py`** —
`estimate_cost(profile, pipeline, sample_count) -> CostEstimate`.
Pluggable backend; stub for non-cloud profiles, concrete for
`GCP_BATCH` using cached pricing tables refreshed weekly via a new
APScheduler job `refresh_gcp_pricing`. Logged on every launch for
actuals-vs-estimate analysis.

**`backend/jobs/work_dir_jobs.py`** —
`cleanup_old_work_dirs` APScheduler job. Removes `STAGED` files and
entire run directories older than configurable retention (default 7
days). Honors a per-profile retention override.

### Key rules

- `Settings.work_dir` is the default `JACKPOT_WORK_DIR` for runs that
  don't override via profile. Default per scenario:
  - Scenario A (laptop / single-server): `~/.jackpot/work/`
  - Scenario A (multi-server / agency, Docker): `/srv/jackpot/work/`
  - Scenario B (HPC, Slurm): operator-provided shared filesystem path (Lustre/GPFS)
  - Scenario C (cloud-native): `gs://<deployment>-jackpot-work/` or `s3://...`
- Quick-fast pipelines (file_detector smoke runs, DLP scans, validation)
  default to the deployment's `LOCAL` profile during seeding — they
  always run on the API server.
- Heavy pipelines (PHoeNIx, MIRA-NF, MycoSNP-NF, aquascope) have no
  default seeded; operator picks at launch or sets a default.
- Generated `nextflow.config` snippets are stored alongside run logs at
  `<work_dir>/runs/<run_id>/jackpot_run.config` for audit and
  reproducibility (extends Critical Rule 26).
- Audit actions added: `CREATE_PROFILE`, `UPDATE_PROFILE`,
  `DELETE_PROFILE`, `LAUNCH_WITH_PROFILE`.
- See Critical Rule 59 (executor selection is per-run).

### Tests

- Unit tests for the profile renderer covering each executor type
  against fixture profile data; snapshot testing of rendered config.
- Integration test: register profile → launch tiny pipeline →
  verify generated `jackpot_run.config` matches expectations.
- Integration test for the resolution logic (explicit > pipeline
  default > deployment default > error).
- Integration test for `cleanup_old_work_dirs` — `STAGED` files older
  than retention disappear; `MANAGED` files do not.
- Mocked-Slurm and mocked-GCP-Batch tests verifying generated configs
  contain the right executor-specific fields.

---
## Federation Track 1 + Track 2-seam Scaffold (FED-A through FED-E)

**Status:** FED-A merged 2026-05-08. FED-B through FED-E pending.
**Lives at:** `backend/backend/federation/`
**Ahead of:** B-FED-1 (central CA federation peer authentication) in the
future-phases list — FED-A lands the package surface so B-FED-1 reduces
to router + tests + migration + central CA integration on top.

### Two-track architectural pattern

Two parallel namespaces under `backend/backend/`:

- `backend/backend/federation/` — Track 1, ships now using current JACKPOT
  primitives (JWT, presigned URLs, the existing `can_access_sample()`
  permission model)
- `backend/backend/immune/` — Track 2, AIS-augmented overlays scheduled
  per `jackpot_immune_collaboration_scaffolding.md`. Concrete implementations
  of the Protocol seams in each Track 1 package's `_ais_hooks.py` module.

The seam between tracks is dependency injection. Every Track 1 class accepts
a `hooks=` argument defaulting to `Null<X>Hooks` (no-op). Track 2 swaps in
concrete implementations via the same constructor argument. **No code
changes required to Track 1 modules when Track 2 lands.**

Direction of dependency is one-way: `backend/backend/federation/` never
imports from `backend/backend/immune/`. The reverse is fine — Track 2's
`backend/backend/immune/net/federation_hooks.py` will import the
`AISFederationHooks` Protocol from `backend/backend/federation/_ais_hooks.py`
and the AIS primitives from sibling immune-platform modules.

This same pattern applies to `backend/backend/privacy/` (PRV-A, pending) and
`backend/backend/crypto/` (CRY-A, pending).

### Federation Levels (per `jackpot_architecture.md` §22)

| Level | Description | Track 1 Status |
|---|---|---|
| L1 — Query federation | DISCOVERABLE-equivalent metadata search across registered partners. No clinical metadata, no file URLs, 30-min cache. | ✅ Concrete in `client.py` |
| L2 — De-identified hub push | Spoke instances push surveillance data nightly. FASTA presigned URL + typing + AMR + lineage + organism + date + country/state. Raw FASTQ and PII never leave the spoke. | Logic concrete in `push.py` (3 qualification gates); IO stubbed via `NotImplementedError` |
| L3 — Bidirectional sharing | Cross-instance access requests. Reuses the existing internal `sample_access` workflow for approval. Files copied via presigned URL on approval. | Integration shape concrete in `access.py`; IO stubbed |

### `AISFederationHooks` Protocol surface

Five hooks, each tied to a specific AIS doc section and a Track 2 impl
location under `backend/backend/immune/`. Track 1 ships with
`NullAISFederationHooks` providing no-op safe defaults for every hook.

| Hook | AIS doc ref | Track 2 impl module |
|---|---|---|
| `secure_aggregate(results, partner_set)` | §1.6 inter-instance signaling | `backend/backend/immune/net/federation_hooks.py` ← `backend/backend/immune/sec/cs_cyber_federated.py` |
| `attest_partner(instance)` | §1.7 attribution & deception | `backend/backend/immune/net/federation_hooks.py` ← `backend/backend/immune/sec/` (attestation primitives, new) |
| `detect_anomalous_traffic(query, partner)` | §1.3 innate immunity | `backend/backend/immune/net/federation_hooks.py` ← `backend/backend/immune/algorithms/featurizers/`, `backend/backend/immune/redteam/attack_federation.py` |
| `threshold_approve(action, partner_set)` | §1.8 tolerance / regulation | `backend/backend/immune/net/federation_hooks.py` ← `backend/backend/immune/sec/` (threshold-crypto primitives, new) |
| `validate_push_payload(payload, target)` | §1.8 tolerance ("don't attack self") | `backend/backend/immune/net/federation_hooks.py` ← `backend/backend/immune/sec/refusal.py`, `backend/backend/immune/sec/parsers_safe.py` |

### Operator-agnostic policy

No proper names in code, docs, or commit messages. When generating from
strategic vision docs (`Jackpot_AIS.md`,
`jackpot_immune_collaboration_scaffolding.md`):

- Replace `TODO(forrest-collab)` markers with `TODO(immune-algorithms-collab)` keyed on directory location and expertise area
- Replace prose like "Forrest's lane" / "Trieu's bread and butter" / "Lee-specific hooks" with structural descriptions ("AIS-theoretic expertise", "applied cryptography", "adversarial security testing")
- Keep technical-paper citations by their conventional name; protocol names like FROST/BLS/DKG are abbreviations and stay; eponymous protocol names like "Bonawitz protocol" should be genericized to "secure aggregation protocol" with the technical concept preserved

The cleanup script `scripts_jackpot/audit_proper_names.py` (sibling to repo)
verifies a directory tree is clean before committing.

### FED-B — Federation router

`backend/backend/routers/federation.py` exposing the package via
`/api/v1/federation/*`:

- `GET /api/v1/federation/instances` — list registered partners (Platform Admin only)
- `POST /api/v1/federation/instances` — register a partner (Platform Admin only)
- `POST /api/v1/federation/search` — broadcast L1 query to enabled partners
- `POST /api/v1/federation/push` — receive an inbound L2 payload (peer instance only)
- `POST /api/v1/federation/access-requests` — receive an inbound L3 access request (peer instance only)

Auth: federation API keys via `X-JACKPOT-Federation-Key` header for
peer-to-peer endpoints; standard JWT for the admin-facing list/register
endpoints.

### FED-C — Tests

`tests/federation/`:

- `test_models.py` — Pydantic v2 shape and serialization round-trip
- `test_client_l1.py` — `FederationClient` async fanout, hook invocation order, partner attestation rejection, anomaly detection rejection. Use `respx` to mock partner HTTP.
- `test_push_l2.py` — qualification logic (port the smoke test cases from FED-A delivery), payload composition, negative-list enforcement
- `test_access_l3.py` — outbound + inbound shapes, `NotImplementedError` raises where appropriate
- `test_ais_hooks.py` — `NullAISFederationHooks` satisfies `AISFederationHooks` Protocol, all five hooks return safe defaults

Coverage target: 95%+ on every module in `backend/backend/federation/`.

### FED-D — Schema migration

LinkML schema YAML edits first (canonical source of truth), then
`uv run python scripts/regen_schema.py`, then Alembic autogenerate plus
manual cleanup.

New table:
- `federated_instances` (columns per `models.py` `FederatedInstance` shape:
  id, name, base_url, role, federation_enabled, min_sharing_level_for_federation,
  hub_instance_url, api_key_secret_name, last_seen_at, created_at, updated_at)

New columns on `organizations`:
- `min_sharing_level_for_federation` (default `'DISCOVERABLE'`)
- `federation_enabled` (default `false`)
- `hub_instance_url` (nullable)
- `federation_role` (enum: `hub`, `spoke`, `peer`, nullable)

### FED-E — Wiring

Register the FED-B router in `backend/backend/main.py`. Update
`backend/backend/auth/guards.py` if a federation-key guard is needed
(otherwise the router can validate keys inline).

### Pending expansion: PRV-A and CRY-A

Same scaffold pattern at `backend/backend/privacy/` and `backend/backend/crypto/`:

- **PRV-A** — `coarsening.py` (consolidates host_age_range and similar generalization), `scrubber.py` (HRRT integration interface), `dlp.py` (consolidates `dlp_scanner.py`), `budget.py` (placeholder for DP budget tracking — Track 2 anchor); `_ais_hooks.py` defines `AISPrivacyHooks` Protocol with hooks for FL aggregation, DP noise injection, DP budget tracking, HE compute, MPC protocols, synthetic-data substitution.

- **CRY-A** — `keys.py` (key management abstraction over PKCS#11), `signing.py` (Sigstore/cosign artifact signing interface), `crypt4gh.py` (per-file encryption for ingest/egress); `_ais_hooks.py` defines `AISCryptoHooks` Protocol with hooks for HE backend selection, threshold signing (FROST/BLS/DKG), TEE attestation evidence verification.

Each scaffold is roughly 1000 lines, 7 files, 1 PR. Each adds five Track 2
hook seams with the same `Null<X>Hooks` no-op default pattern.


## Phase P0h Specification — Slurm executor support

> **Status (2026-05-12):** Six of ten H-blocks merged in Session 21
> (PRs #35 H-1, #36 H-2, #37 H-3, #38 H-4, #40 H-5, #41 H-6, #42
> H-10); H-9 tests interleaved per-PR throughout. H-7 (GCP Batch
> staging) and H-8 (real-cluster smoke test) deferred to Phase 25
> with named dependencies. See `todo.md` Phase P0h for the merged-vs-
> deferred breakdown.
> Builds on P0g profile model; makes Slurm a peer of the local executor
> for scenarios A (multi-server with Slurm profile) and B (HPC) without
> code duplication.
>
> **Operator-facing surface:** `docs/slurm_executor.md` is the
> canonical guide (profile setup, network requirements, Apptainer
> pre-staging, weblog vs. log poller redundancy, `jackpot doctor`,
> common cluster-policy gotchas).
> **Pipeline-zoo Apptainer pre-staging:** `docs/pipeline_apptainer_audit.md`
> documents the per-pipeline OCI-image manifest format
> (`pipelines/pipelines/<name>/apptainer_images.txt`) consumed by the
> future `jackpot images audit` / `jackpot images export` CLI.

### Schema additions

None of its own — uses `execution_profiles` from P0g. Slurm-specific
fields live in the `config_overrides` JSON column:

```json
{
  "account": "mylab-2026",
  "partition": "compute",
  "qos": "normal",
  "time": "24:00:00",
  "default_memory": "8 GB",
  "default_cpus": 4,
  "queueSize": 50,
  "clusterOptions": "--nodes=1 --exclusive",
  "scratch_dir": "/scratch/$USER/jackpot",
  "weblog_reachable": false
}
```

### New endpoints

None of its own — extends the launch flow from P0g.

### New modules

**`backend/pipelines/log_poller.py`** — Fallback for cluster runs where
compute nodes can't reach the API. Tails
`<work_dir>/runs/<run_id>/.nextflow.log` on the shared filesystem,
parses Nextflow's known event patterns, emits synthetic weblog events
to the same handler the HTTP receiver uses. Started as an APScheduler
job per active cluster run; polls every 30 seconds. Idempotent on
`(run_id, task_id, status)` so it can coexist with HTTP weblog.

**`backend/pipelines/cluster_health.py`** —
`check_slurm_reachable(profile) -> ReachabilityResult`. Runs `sinfo`
with a 10-second timeout. Cached for 60 seconds to avoid hammering
the cluster on bulk launches. Called by the pre-launch check (extends
P0f's input-verification step).

**`pipelines/<name>/apptainer_images.txt`** — One per pipeline in the
zoo. Lists the OCI image references the pipeline pulls, used by
`jackpot images export` to pre-stage SIF files for air-gapped clusters.

### Updated modules

**`backend/pipeline_config/profile_templates/slurm.config.j2`** —
Renders the full Slurm field set: `account`, `partition`, `qos`,
`clusterOptions`, `time`, `default_memory`, `default_cpus`,
`queueSize`. Apptainer is the default container engine for Slurm
profiles (university policy norm). When the profile has
`weblog_reachable=false`, the template omits the `weblog` directive
from the generated config — the log poller is the source of truth.

**`backend/pipelines/launch.py`** — Pre-launch verification extended:
when launch profile is Slurm, additionally call
`check_slurm_reachable()` and refuse with a clear error if the
cluster is unreachable. For multi-tenant launches, validate optional
`launch_account` override against the user's lab memberships
(P0c multi-tenancy guard).

**Pipeline definitions in `pipelines/`** — Audit each for an
`apptainer` profile; add where missing. Most are nf-core-standards and
already have one.
## Federation Track 1 + Track 2-seam Scaffold (FED-A through FED-E)

**Status:** FED-A merged 2026-05-08. FED-B through FED-E pending.
**Lives at:** `backend/backend/federation/`
**Ahead of:** B-FED-1 (central CA federation peer authentication) in the
future-phases list — FED-A lands the package surface so B-FED-1 reduces
to router + tests + migration + central CA integration on top.

### Two-track architectural pattern

Two parallel namespaces under `backend/backend/`:

- `backend/backend/federation/` — Track 1, ships now using current JACKPOT
  primitives (JWT, presigned URLs, the existing `can_access_sample()`
  permission model)
- `backend/backend/immune/` — Track 2, AIS-augmented overlays scheduled
  per `jackpot_immune_collaboration_scaffolding.md`. Concrete implementations
  of the Protocol seams in each Track 1 package's `_ais_hooks.py` module.

The seam between tracks is dependency injection. Every Track 1 class accepts
a `hooks=` argument defaulting to `Null<X>Hooks` (no-op). Track 2 swaps in
concrete implementations via the same constructor argument. **No code
changes required to Track 1 modules when Track 2 lands.**

Direction of dependency is one-way: `backend/backend/federation/` never
imports from `backend/backend/immune/`. The reverse is fine — Track 2's
`backend/backend/immune/net/federation_hooks.py` will import the
`AISFederationHooks` Protocol from `backend/backend/federation/_ais_hooks.py`
and the AIS primitives from sibling immune-platform modules.

This same pattern applies to `backend/backend/privacy/` (PRV-A, pending) and
`backend/backend/crypto/` (CRY-A, pending).

### Federation Levels (per `jackpot_architecture.md` §22)

| Level | Description | Track 1 Status |
|---|---|---|
| L1 — Query federation | DISCOVERABLE-equivalent metadata search across registered partners. No clinical metadata, no file URLs, 30-min cache. | ✅ Concrete in `client.py` |
| L2 — De-identified hub push | Spoke instances push surveillance data nightly. FASTA presigned URL + typing + AMR + lineage + organism + date + country/state. Raw FASTQ and PII never leave the spoke. | Logic concrete in `push.py` (3 qualification gates); IO stubbed via `NotImplementedError` |
| L3 — Bidirectional sharing | Cross-instance access requests. Reuses the existing internal `sample_access` workflow for approval. Files copied via presigned URL on approval. | Integration shape concrete in `access.py`; IO stubbed |

### `AISFederationHooks` Protocol surface

Five hooks, each tied to a specific AIS doc section and a Track 2 impl
location under `backend/backend/immune/`. Track 1 ships with
`NullAISFederationHooks` providing no-op safe defaults for every hook.

| Hook | AIS doc ref | Track 2 impl module |
|---|---|---|
| `secure_aggregate(results, partner_set)` | §1.6 inter-instance signaling | `backend/backend/immune/net/federation_hooks.py` ← `backend/backend/immune/sec/cs_cyber_federated.py` |
| `attest_partner(instance)` | §1.7 attribution & deception | `backend/backend/immune/net/federation_hooks.py` ← `backend/backend/immune/sec/` (attestation primitives, new) |
| `detect_anomalous_traffic(query, partner)` | §1.3 innate immunity | `backend/backend/immune/net/federation_hooks.py` ← `backend/backend/immune/algorithms/featurizers/`, `backend/backend/immune/redteam/attack_federation.py` |
| `threshold_approve(action, partner_set)` | §1.8 tolerance / regulation | `backend/backend/immune/net/federation_hooks.py` ← `backend/backend/immune/sec/` (threshold-crypto primitives, new) |
| `validate_push_payload(payload, target)` | §1.8 tolerance ("don't attack self") | `backend/backend/immune/net/federation_hooks.py` ← `backend/backend/immune/sec/refusal.py`, `backend/backend/immune/sec/parsers_safe.py` |

### Operator-agnostic policy

No proper names in code, docs, or commit messages. When generating from
strategic vision docs (`Jackpot_AIS.md`,
`jackpot_immune_collaboration_scaffolding.md`):

- Replace `TODO(forrest-collab)` markers with `TODO(immune-algorithms-collab)` keyed on directory location and expertise area
- Replace prose like "Forrest's lane" / "Trieu's bread and butter" / "Lee-specific hooks" with structural descriptions ("AIS-theoretic expertise", "applied cryptography", "adversarial security testing")
- Keep technical-paper citations by their conventional name; protocol names like FROST/BLS/DKG are abbreviations and stay; eponymous protocol names like "Bonawitz protocol" should be genericized to "secure aggregation protocol" with the technical concept preserved

The cleanup script `scripts_jackpot/audit_proper_names.py` (sibling to repo)
verifies a directory tree is clean before committing.

### FED-B — Federation router

`backend/backend/routers/federation.py` exposing the package via
`/api/v1/federation/*`:

- `GET /api/v1/federation/instances` — list registered partners (Platform Admin only)
- `POST /api/v1/federation/instances` — register a partner (Platform Admin only)
- `POST /api/v1/federation/search` — broadcast L1 query to enabled partners
- `POST /api/v1/federation/push` — receive an inbound L2 payload (peer instance only)
- `POST /api/v1/federation/access-requests` — receive an inbound L3 access request (peer instance only)

Auth: federation API keys via `X-JACKPOT-Federation-Key` header for
peer-to-peer endpoints; standard JWT for the admin-facing list/register
endpoints.

### FED-C — Tests

`tests/federation/`:

- `test_models.py` — Pydantic v2 shape and serialization round-trip
- `test_client_l1.py` — `FederationClient` async fanout, hook invocation order, partner attestation rejection, anomaly detection rejection. Use `respx` to mock partner HTTP.
- `test_push_l2.py` — qualification logic (port the smoke test cases from FED-A delivery), payload composition, negative-list enforcement
- `test_access_l3.py` — outbound + inbound shapes, `NotImplementedError` raises where appropriate
- `test_ais_hooks.py` — `NullAISFederationHooks` satisfies `AISFederationHooks` Protocol, all five hooks return safe defaults

Coverage target: 95%+ on every module in `backend/backend/federation/`.

### FED-D — Schema migration

LinkML schema YAML edits first (canonical source of truth), then
`uv run python scripts/regen_schema.py`, then Alembic autogenerate plus
manual cleanup.

New table:
- `federated_instances` (columns per `models.py` `FederatedInstance` shape:
  id, name, base_url, role, federation_enabled, min_sharing_level_for_federation,
  hub_instance_url, api_key_secret_name, last_seen_at, created_at, updated_at)

New columns on `organizations`:
- `min_sharing_level_for_federation` (default `'DISCOVERABLE'`)
- `federation_enabled` (default `false`)
- `hub_instance_url` (nullable)
- `federation_role` (enum: `hub`, `spoke`, `peer`, nullable)

### FED-E — Wiring

Register the FED-B router in `backend/backend/main.py`. Update
`backend/backend/auth/guards.py` if a federation-key guard is needed
(otherwise the router can validate keys inline).

### Pending expansion: PRV-A and CRY-A

Same scaffold pattern at `backend/backend/privacy/` and `backend/backend/crypto/`:

- **PRV-A** — `coarsening.py` (consolidates host_age_range and similar generalization), `scrubber.py` (HRRT integration interface), `dlp.py` (consolidates `dlp_scanner.py`), `budget.py` (placeholder for DP budget tracking — Track 2 anchor); `_ais_hooks.py` defines `AISPrivacyHooks` Protocol with hooks for FL aggregation, DP noise injection, DP budget tracking, HE compute, MPC protocols, synthetic-data substitution.

- **CRY-A** — `keys.py` (key management abstraction over PKCS#11), `signing.py` (Sigstore/cosign artifact signing interface), `crypt4gh.py` (per-file encryption for ingest/egress); `_ais_hooks.py` defines `AISCryptoHooks` Protocol with hooks for HE backend selection, threshold signing (FROST/BLS/DKG), TEE attestation evidence verification.

Each scaffold is roughly 1000 lines, 7 files, 1 PR. Each adds five Track 2
hook seams with the same `Null<X>Hooks` no-op default pattern.
### Key rules

- Cluster-bound runs must work whether or not compute nodes can reach
  the API. The HTTP weblog receiver remains best-effort and never
  raises on errors. The log poller is the source of truth when
  `weblog_reachable=false` in the profile.
- Per-launch `launch_account` override (for grant accounting in
  scenario B HPC deployments) is validated against the user's lab
  memberships, never trusted from the request body alone.
- Apptainer is the default container engine for Slurm profiles. Docker
  remains an option for lab-Slurm cases where the cluster allows it.
- Compute-side scratch and stage directories use Nextflow's
  `process.scratch=true` plus shared-filesystem `process.stageInMode`
  to avoid copies between control plane and compute plane.
- Audit actions added: `LAUNCH_TO_CLUSTER`, `CLUSTER_UNREACHABLE`,
  `LOG_POLLER_STARTED`, `LOG_POLLER_FAILED`.
- See Critical Rule 60 (cluster runs work without API reachability).

### Tests

- Unit tests for the Slurm profile renderer covering all field
  combinations and the `weblog_reachable=false` branch.
- Mocked-Slurm integration tests capturing the rendered `sbatch`
  command line and verifying expected flags.
- Unit tests for the log poller against fixture `.nextflow.log`
  files.
- CI matrix entry running a hermetic end-to-end pipeline test against
  `giovtorres/slurm-docker-cluster` on every PR that touches
  `backend/pipeline_config/` or `pipelines/`.
- Manual end-to-end smoke tests against a real Slurm cluster covering:
  weblog-reachable run, weblog-blocked run with poller, 10-sample
  batch with queueSize throttling, and a mid-run BROKEN-input failure.

---

## Phase I-2 Specification — Submissions

> **Status:** Shipped (Session 19, PR-merged into `development`).
> First-class submissions tracking and Seqsender-compatible package
> generation. v1 deliberately excludes credential management — JACKPOT
> generates the package, the operator runs Seqsender (or DDBJ /
> GISAID-equivalent tools) themselves with their own credentials. I-3
> adds optional backend-driven execution on top of this foundation.
> Implementation lives in `backend/backend/submissions.py` (state-machine
> business logic) and `backend/backend/routers/submissions.py` (thin
> HTTP shell). The CLI (`cli/jackpot/cli/submissions.py`) and SDK
> (`cli/jackpot/sdk/submissions.py`) call the service module directly.

### State machine

The submission lifecycle is a 13-state machine encoded in
`submissions.py`'s `VALID_STATUSES` constant:

```
DRAFT
  ↓ (mark_package_generated — writes package_path + package_generated_at)
READY_TO_SUBMIT
  ↓ (mark_submitted — sets submitted_at)
SUBMITTED
  ↓ (register_accessions — TSV ingest, sets per-sample accessions)
  ├→ ACCEPTED          (all samples accepted)
  ├→ PARTIAL_SUCCESS   (some samples rejected)
  └→ REJECTED          (all samples rejected, mark_rejected)
ACCEPTED / PARTIAL_SUCCESS
  ↓ (release_date set + EMBARGOED elected by operator)
EMBARGOED
  ↓ (release_embargoed_submissions daily job at midnight UTC)
RELEASED
```

Plus side-paths:

- **`WITHDRAWN`** — reachable from any post-`DRAFT` state via
  `withdraw_submission`. The samples list is locked; the row is kept
  for audit history.
- **`FAILED`** — terminal failure surfaced when package generation or
  validation reports an unrecoverable error. Operator must withdraw
  and create a new submission.

I-3a backend-execution states (used only when `allow_backend_submission`
is set on the lab and `backend_submission_repos` includes the target):

- **`EXECUTING`** — set by `mark_execution_queued` when the
  Seqsender subprocess starts. Withdrawal is intentionally blocked from
  this state to avoid mid-flight executor races.
- **`EXECUTION_FAILED`** — Seqsender returned non-zero (I-3b);
  reachable via `mark_execution_retried` for retry.
- **`EXECUTION_INTERRUPTED`** — set by the lifespan recovery hook
  (Critical Rule 60 cluster-bound runs pattern, applied here at the
  process-supervision layer) when an API restart abandons an in-flight
  subprocess.

The set `_POST_SUBMITTED_STATUSES` defines the withdraw-allowed states
(`SUBMITTED`, `PARTIAL_SUCCESS`, `ACCEPTED`, `EMBARGOED`, `RELEASED`,
`REJECTED`, plus the two execution-failure states). The set
`_SAMPLES_LOCKED_STATUSES` covers everything except `DRAFT` —
`add_samples_to_submission` and `remove_samples_from_submission`
refuse outside of `DRAFT`.

### Schema

`submissions` table:

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL | PK |
| `created_by_user_id` | INTEGER | FK users(id) |
| `lab_id` | INTEGER | FK labs(id) |
| `target_repository` | VARCHAR(32) | One of `NCBI`, `GISAID_EPICOV`, `GISAID_EPIFLU`, `GISAID_EPIPOX`, `ENA`, `DDBJ` |
| `title` | TEXT | Required |
| `description` | TEXT | Optional |
| `status` | VARCHAR(32) | Default `DRAFT`; CHECK against `VALID_STATUSES` |
| `bioproject_accession` | TEXT | NCBI-only; supplied by operator before submission |
| `release_date` | DATE | Optional embargo end-date |
| `package_path` | TEXT | URI of generated package |
| `package_generated_at` | TIMESTAMPTZ | Set by `mark_package_generated` |
| `submitted_at` | TIMESTAMPTZ | Set by `mark_submitted` |
| `accepted_at` | TIMESTAMPTZ | Set by `register_accessions` when status moves to `ACCEPTED` or `PARTIAL_SUCCESS` |
| `rejection_reason` | TEXT | Free-text reason for `REJECTED` status |
| `withdrawal_reason` | TEXT | Free-text reason for `WITHDRAWN` status |
| `created_at` | TIMESTAMPTZ | Default `NOW()` |
| `updated_at` | TIMESTAMPTZ | Default `NOW()`, bumped by writes |
| `is_deleted` | BOOLEAN | Soft-delete flag; default FALSE |

Indexes: `submissions_lab_status_idx` `(lab_id, status) WHERE is_deleted = FALSE`,
`submissions_creator_idx` `(created_by_user_id) WHERE is_deleted = FALSE`.

`submission_samples` table:

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL | PK |
| `submission_id` | BIGINT | FK submissions(id) ON DELETE CASCADE |
| `sample_id_fk` | INTEGER | FK samples(id) |
| `per_sample_status` | VARCHAR(16) | One of `PENDING`, `ACCEPTED`, `REJECTED` |
| `biosample_accession` | TEXT | Returned by NCBI BioSample registration |
| `sra_accession` | TEXT | Returned by NCBI SRA registration |
| `genbank_accession` | TEXT | Returned by NCBI GenBank registration |
| `gisaid_accession` | TEXT | Returned by GISAID after acceptance |
| `ena_accession` | TEXT | Returned by ENA after acceptance |
| `ddbj_accession` | TEXT | Returned by DDBJ after acceptance |
| `per_sample_rejection_reason` | TEXT | Per-sample rejection reason |
| `created_at` / `updated_at` | TIMESTAMPTZ | Standard |

UNIQUE constraint: `(submission_id, sample_id_fk)`.

### Transition rules

Each transition is gated, audited (Critical Rule 4), and may emit a
notification (the `NotificationEvents` constants are documented in
`docs/CLAUDE.md` Notification System section).

| From | To | Function | Actor permission | Audit action |
|---|---|---|---|---|
| `DRAFT` | `READY_TO_SUBMIT` | `mark_package_generated` | Lab Collaborator+ | `SUBMISSION_PACKAGE_GENERATED` |
| `READY_TO_SUBMIT` | `SUBMITTED` | `mark_submitted` | Lab Collaborator+ | `SUBMISSION_MARKED_SUBMITTED` |
| `SUBMITTED` | `ACCEPTED` / `PARTIAL_SUCCESS` / `REJECTED` | `register_accessions` (or `mark_rejected`) | Lab Collaborator+ | `SUBMISSION_ACCESSIONS_REGISTERED` / `SUBMISSION_REJECTED` |
| `ACCEPTED` / `PARTIAL_SUCCESS` | `EMBARGOED` | `update_submission` (operator sets `release_date`) | Lab Director | `SUBMISSION_UPDATED` |
| `EMBARGOED` | `RELEASED` | `release_embargoed_submissions` daily job | system | `SUBMISSION_RELEASED` |
| post-`SUBMITTED` (excl. `EXECUTING`) | `WITHDRAWN` | `withdraw_submission` | Lab Director | `SUBMISSION_WITHDRAWN` |
| `READY_TO_SUBMIT` | `EXECUTING` | `mark_execution_queued` (I-3a) | Lab Director | `SUBMISSION_EXECUTION_QUEUED` |
| `EXECUTION_FAILED` / `EXECUTION_INTERRUPTED` | `EXECUTING` | `mark_execution_retried` (I-3a) | Lab Director | `SUBMISSION_EXECUTION_RETRIED` |
| `EXECUTING` | `ACCEPTED` / `PARTIAL_SUCCESS` / `REJECTED` | `mark_execution_completed` (I-3b) | system | `SUBMISSION_EXECUTION_COMPLETED` |
| `EXECUTING` | `EXECUTION_FAILED` | `mark_execution_failed` (I-3b) | system | `SUBMISSION_EXECUTION_FAILED` |
| `EXECUTING` | `EXECUTION_INTERRUPTED` | `recover_interrupted_executions` (lifespan hook, I-3b) | system | `SUBMISSION_EXECUTION_INTERRUPTED` |

### Endpoints

All routes are under `/api/v1/submissions/`. See
`docs/api/submissions.md` for full request/response shapes.

- `POST /` — create submission (DRAFT)
- `GET /` — list submissions visible to the user (paginated)
- `GET /{id}` — get a single submission
- `PATCH /{id}` — partial update (Critical Rule 39 pattern)
- `DELETE /{id}` — soft delete (only allowed in `DRAFT`)
- `POST /{id}/samples` / `DELETE /{id}/samples/{sample_id}` — sample list management (locked outside `DRAFT`)
- `POST /{id}/validate` — readiness check (per-sample issues + per-submission errors)
- `POST /{id}/generate` — generate package on disk; transitions to `READY_TO_SUBMIT`
- `POST /{id}/submitted` — mark as `SUBMITTED` after operator handed package to Seqsender
- `POST /{id}/accessions` — TSV ingest of per-sample accessions
- `POST /{id}/rejected` — mark fully rejected with reason
- `POST /{id}/withdraw` — withdraw with reason
- `POST /{id}/execute` (I-3a) — gated on `allow_backend_submission`; queues backend execution
- `POST /{id}/retry` (I-3a) — retry from `EXECUTION_FAILED` / `EXECUTION_INTERRUPTED`
- `GET /{id}/logs` (I-3b) — view execution log via signed URL

### Package generation handoff

JACKPOT v1 does NOT execute submissions on the backend by default
(Session 18 decision). The package generator writes a Seqsender-
compatible directory (or DDBJ / GISAID-equivalent for non-NCBI
targets) under `<submission_packages_dir>/<submission_id>/`. The
generated `seqsender_config.yaml` references the operator's own
credentials by environment-variable name — JACKPOT never holds
NCBI/GISAID/ENA secrets in v1, sidestepping the Scenario A
laptop-case connectivity-and-IP-rotation problem entirely. The operator
runs `seqsender submit ./<submission_id>/` from a stable host.

The opt-in path to backend execution (I-3) is gated by:

1. `allow_backend_submission=true` on the lab (Lab Director consent), and
2. `backend_submission_repos` listing the specific repos the operator
   trusts JACKPOT to call (subset of `VALID_REPOSITORIES`), and
3. The C-1 credential infrastructure (Phase C-1 below) configured for
   each enabled repo's required credentials per
   `backend/credentials/registry.py`'s `REQUIRED_CREDENTIALS`.

If any of those preconditions are missing, `POST /{id}/execute`
returns `400 NO_CREDENTIALS_CONFIGURED` (or `400 BACKEND_SUBMISSION_DISABLED`)
and the operator falls back to manual Seqsender execution against
the still-existing package.

### Daily release-embargoed-submissions job

`backend/jobs.py::release_embargoed_submissions` runs once per day at
midnight UTC (cron `hour=0, minute=0`, registered alongside the
existing `run_access_request_job`). It scans for `status=EMBARGOED`
rows where `release_date <= CURRENT_DATE`, transitions each to
`RELEASED`, writes the `SUBMISSION_RELEASED` audit event, and
notifies the creator. Idempotent — re-running on the same day is a
no-op for already-released submissions because the WHERE clause
excludes them.

### Audit actions added by I-2 + I-3

- `SUBMISSION_CREATED`
- `SUBMISSION_UPDATED`
- `SUBMISSION_DELETED`
- `SUBMISSION_PACKAGE_GENERATED`
- `SUBMISSION_MARKED_SUBMITTED`
- `SUBMISSION_ACCESSIONS_REGISTERED`
- `SUBMISSION_REJECTED`
- `SUBMISSION_WITHDRAWN`
- `SUBMISSION_RELEASED`
- `SUBMISSION_SAMPLES_ADDED` / `SUBMISSION_SAMPLES_REMOVED`
- `SUBMISSION_EXECUTION_QUEUED` (I-3a)
- `SUBMISSION_EXECUTION_RETRIED` (I-3a)
- `SUBMISSION_EXECUTION_COMPLETED` (I-3b)
- `SUBMISSION_EXECUTION_FAILED` (I-3b)
- `SUBMISSION_EXECUTION_INTERRUPTED` (I-3b)

### Tests

Tests live at `tests/test_submissions_router.py`,
`tests/test_submission_packages.py`, and the per-repo generator suites
(`tests/test_submission_packages_ena.py` etc.). Coverage targets
include every state-machine transition and every refusal path, the
TSV accession-ingest parser including malformed input, the
embargo-release job idempotency, and the I-3a backend-execution gates.

---

## Phase C-1 Specification — Pluggable credential infrastructure

> **Status:** Shipped (Session 20, PR-merged into `development`).
> Pluggable credential layer behind a single `CredentialFacade` so
> consuming code (submissions, future LLM features, federation API
> keys) reads credentials by name without knowing where they come
> from. v1 ships three backends: env vars (default, works
> everywhere), file-based YAML (config-management-friendly), GCP
> Secret Manager (cloud deployments). AWS Secrets Manager, Azure
> Key Vault, and OS keychain backends are future work, gated on
> demand. See Critical Rule 62 in `docs/CLAUDE.md`.

### Architecture

```
caller (router / job / submission service)
    │
    ▼
backend.credentials.credentials       ← public proxy (lazy-init facade)
    │
    ▼
CredentialFacade                       ← cache + audit + registry
    │
    ▼
CredentialBackend (one of)             ← interface
    ├─ EnvBackend          — os.environ lookup
    ├─ FileBackend         — YAML at credential_file_path
    └─ GCPSecretManagerBackend — google-cloud-secret-manager client
```

The facade is the single entry point. It wraps the chosen backend
with a TTL'd cache (`credential_cache_ttl_seconds`, default 300),
emits structured audit logs (`CREDENTIAL_READ` / `CREDENTIAL_READ_FAILED`)
to the `backend.credentials.audit` stdlib logger (NOT the DB-bound
`log_audit` — credential reads happen outside any DB transaction),
and validates required credentials at startup against
`REQUIRED_CREDENTIALS` from `backend/credentials/registry.py`.

### Settings

In `backend/config.py`:

| Field | Type | Default | Description |
|---|---|---|---|
| `credential_backend` | `Literal["env", "file", "gcp_secret_manager"]` | `"env"` | Which backend `CredentialFactory` constructs |
| `credential_file_path` | `str` | `"~/.config/jackpot/credentials.yaml"` | Path used by `FileBackend` |
| `credential_gcp_secret_prefix` | `str` | `"jackpot-cred-"` | Secret-name prefix in GCP Secret Manager |
| `credential_cache_ttl_seconds` | `int` | `300` | Cache TTL on the facade |

### Backends

**`EnvBackend`** — `os.environ.get(key)`. Default for Scenarios A
(commodity self-hosted) and D (CI). Zero new infrastructure; operator
sets env vars in `.env.local` / `docker-compose.yml` / Helm values.
Best for single-operator deployments and CI.

**`FileBackend`** — reads a YAML file at `credential_file_path` whose
top-level keys are credential names. File mode must be 0600 (the
backend refuses to read otherwise). Best for config-management-
friendly multi-host deployments without a cloud secret store.

**`GCPSecretManagerBackend`** — fetches from GCP Secret Manager with
secret name `{credential_gcp_secret_prefix}{key}`. Requires
`google-cloud-secret-manager` (already in the dependency tree for
Scenario C cloud). Best for GCP-native deployments where IAM-gated
secret access matters.

### Public surface

`backend.credentials.credentials` is a module-level proxy that
lazily constructs the facade on first access (via `CredentialFactory`
which inspects `Settings.credential_backend`). Three call shapes:

```python
from backend.credentials import credentials

api_key = credentials.get("ncbi_api_key")              # raises if missing
optional_token = credentials.get_optional("github_token")  # returns None if missing
keys = credentials.list_keys()                          # for diagnostics
```

`get` and `get_optional` are documented in
`backend/credentials/facade.py`. `list_keys` is implementation-
defined per backend (`EnvBackend.list_keys` returns the union of env
vars matching the registry's known keys; `FileBackend` returns the
file's keys; `GCPSecretManagerBackend` lists secrets matching the
prefix).

### Migration path for existing credential reads

C-1 migrated three call sites already in production:

- **Globus** — `globus_client_id` / `globus_client_secret` /
  `globus_endpoint_id` previously read from `Settings`; now read via
  `credentials.get(...)`.
- **Cloud storage** (GCS / MinIO / S3) — service-account credentials
  previously bootstrapped via `google.auth.default()` paths; now the
  facade routes through `GCPSecretManagerBackend` when
  `credential_backend = "gcp_secret_manager"`. Local dev still uses
  ADC by default since `EnvBackend` doesn't shadow auth.
- **JWT signing key** — formerly `Settings.secret_key`; now
  `credentials.get("jwt_secret_key")`. Production validation in
  `Settings.validate_for_production()` was simplified accordingly
  (the secret-key check moved to credential validation at startup).

Future credential reads (NCBI / ENA / GISAID for I-3, federation
peer keys for B-FED-1, LLM API keys for assistant) MUST go through
`backend.credentials` — never via `Settings` or direct `os.environ`
lookups. This is **Critical Rule 62**.

### Credential registry

`backend/credentials/registry.py` defines `REQUIRED_CREDENTIALS` as
a list of `CredentialSpec(key, required_predicate, description,
example)` records. `required_predicate` is a `Settings`-typed
callable returning `True` only when that credential is required for
the current configuration. Examples:

- `globus_client_id` is required only when
  `settings.globus_enabled` is `True`.
- `ncbi_api_key` is required only when
  `settings.allow_backend_submission` is `True` AND
  `"NCBI" in settings.backend_submission_repos`.
- `jwt_secret_key` is always required.

`facade.validate_required()` walks the registry, calls each
predicate against the live settings, and raises `RuntimeError`
listing the missing keys if any required credential is unreachable.
The lifespan handler in `main.py` calls this at startup so a
mis-configured deployment fails fast at boot rather than at first
request.

### Future backends

- **AWS Secrets Manager** — stub interface in place; activates when
  `credential_backend = "aws_secrets_manager"`. Scenario C on AWS
  (EKS-hosted) is the trigger.
- **Azure Key Vault** — same pattern; gated on Azure-hosted
  scenarios.
- **OS keychain** — macOS Keychain / Windows Credential Manager /
  freedesktop Secret Service for Scenario A laptop-case operators who
  don't want plaintext env vars or YAML files.

Each new backend implements `CredentialBackend` and registers with
`CredentialFactory`. No consumer code changes when a new backend is
added.

### Tests

Tests at `backend/backend/credentials/test_helpers.py` provide an
`InMemoryBackend` for unit tests and a fixture that constructs a
facade against it. End-to-end tests cover the three v1 backends
against fixture YAML / monkeypatched env / mocked GCP client. The
factory's settings-driven dispatch is covered with a settings-builder
parametrize. The startup-validation failure mode is covered by
constructing a facade with deliberately-missing required credentials
and asserting `validate_required()` raises with the expected key list.

---

### Session B — labs + lab_membership

**Endpoints:**

- `GET /api/v1/labs/` — paginated list (Platform Admin sees all; others see their labs)
- `POST /api/v1/labs/` — create lab under an org (Platform Admin only)
- `GET /api/v1/labs/{id}` — get lab detail (lab member or Platform Admin)
- `PATCH /api/v1/labs/{id}` — partial update (Lab Director or Platform Admin)
- `DELETE /api/v1/labs/{id}` — soft delete `active=False` (Platform Admin only)
- `GET /api/v1/labs/{id}/members` — list members (Lab Director or Platform Admin)
- `POST /api/v1/labs/{id}/members` — add member (Lab Director or Platform Admin)
- `PATCH /api/v1/labs/{id}/members/{user_id}` — change role (Lab Director or Platform Admin)
- `DELETE /api/v1/labs/{id}/members/{user_id}` — remove member (Lab Director or Platform Admin)

**Key rules:**

- Use `active` column (not `is_active`) for labs
- `is_lab_director` flag on `lab_membership` — not a separate permission check
- Membership changes: `ADD_LAB_MEMBER`, `REMOVE_LAB_MEMBER`, `CHANGE_MEMBER_ROLE`
  audit actions
- `sequencing_lab_assignments` join table links sequencing facilities to
  JACKPOT labs

**Tests:** Role enforcement at every tier, membership lifecycle, soft delete.

---

### Session C — users

**Endpoints:**

- `GET /api/v1/users/` — list users (Platform Admin only)
- `GET /api/v1/users/me` — current user profile (any authenticated user)
- `GET /api/v1/users/{id}` — get user (Platform Admin or same user)
- `PATCH /api/v1/users/{id}` — partial update (Platform Admin or same user)
- `DELETE /api/v1/users/{id}` — deactivate `is_active=False` (Platform Admin only)

**Tests:** Self-service vs admin access, deactivation, pagination.

---

### Session D — domain_whitelist

**Endpoints:**

- `GET /api/v1/domain-whitelist/` — list whitelisted domains (Platform Admin)
- `POST /api/v1/domain-whitelist/` — add domain (Platform Admin)
- `DELETE /api/v1/domain-whitelist/{id}` — remove domain (Platform Admin)

**Purpose:** Controls which email domains can self-register via Google OAuth.

**Tests:** Add/remove domain, non-admin 403.

---

### Session E — sequencing_labs

**Endpoints:**

- `GET /api/v1/sequencing-labs/` — list all sequencing labs (any authenticated user)
- `POST /api/v1/sequencing-labs/` — create lab (Platform Admin only)
- `GET /api/v1/sequencing-labs/{id}` — get detail (any authenticated)
- `PATCH /api/v1/sequencing-labs/{id}` — update (Platform Admin only)
- `POST /api/v1/sequencing-labs/{id}/assign/{lab_id}` — assign to JACKPOT lab (Platform Admin)
- `DELETE /api/v1/sequencing-labs/{id}/assign/{lab_id}` — unassign (Platform Admin)

**Purpose:** Validates `sequencing_lab` field at ingest; drives Globus arrival
notifications.

**Tests:** CRUD, assignment workflow, list returns seed data (Example Reference Lab,
LabCorp, Example Lab).

---

### Session F — tokens

**Endpoints:**

- `GET /api/v1/tokens/` — list my tokens (authenticated user)
- `POST /api/v1/tokens/` — create token (authenticated user)
- `DELETE /api/v1/tokens/{id}` — revoke token (owner or Platform Admin)

**Key rules:**

- Tokens store `default_lab_id` and `default_project_id` for CLI convenience
- `GET /api/v1/projects/` must support `?name=` filter (needed by CLI project lookup)
- Token value shown once at creation — stored as hash in DB

**Tests:** Create/revoke, project name lookup, token isolation between users.

---

### Session G — ingest

**Endpoints:**

- `POST /api/v1/ingest/upload` — GUI/API file + metadata upload
- `POST /api/v1/ingest/csv` — CSV bulk metadata upload (files staged separately)
- `POST /api/v1/ingest/globus` — Globus deposit-first webhook (Platform Admin / system)

**Key rules — read every one before changing anything here:**

- `sequencing_lab` validated against `sequencing_labs` DB table — return
  422 with request workflow message if unknown
- `external_case_id` required for `source_type == "Human"` only
- `file_detector.py` is the only place filename/pairing logic lives
- `compute_epiweeks(date_collected, precision)` called before every DB
  write — precision from validator
- `scrub_status = PENDING` on all new samples with raw reads; `SKIPPED`
  only via validator (FASTA-only) or override workflow
- `compute_surveillance_relevant()` and `compute_quality_status()` called
  from validator — never in router directly
- `log_audit(CREATE_SAMPLE, ...)` on every successful ingest
- One CSV row = one sample; `files` column is semicolon-delimited
- `dlp_scanner.py` scans all free-text fields (when `DLP_ENABLED=true`)
- `epiweek` computed at ingest, written to DB

**Tests:** Valid human upload (Tier 1, 2, 3), FASTA-only auto-skip, unknown
sequencing lab 422, missing external_case_id 422, file detection for R1/R2
pairs, multi-lane, nanopore.

---

### Session H — samples

**Endpoints:**

- `GET /api/v1/samples/` — paginated list with full filter surface (authenticated, access-controlled)
- `GET /api/v1/samples/{id}` — get sample detail (access-controlled via `can_access_sample()`)
- `PATCH /api/v1/samples/{id}` — partial metadata update (Lab Collaborator+, own lab only)
- `DELETE /api/v1/samples/{id}` — soft delete / archive (Lab Director or Platform Admin)
- `GET /api/v1/samples/{id}/files` — list associated files
- `GET /api/v1/samples/{id}/download` — presigned download URL

**Key rules:**

- `can_access_sample()` enforces: Platform Admin → lab member → PUBLIC →
  host-operator oversight (surveillance_relevant only) → approved request
- `?select_all=true` returns IDs only (no pagination) for bulk select
- Filters: `organism_name`, `source_type`, `sector`, `quality_status`,
  `scrub_status`, `sharing_level`, `lab_id`, `project_id`, `date_collected`
  range, `surveillance_relevant`
- `log_audit(UPDATE_SAMPLE / ARCHIVE_SAMPLE)` on writes
- Partial update via `model_dump(exclude_none=True)` — never overwrite
  quality_status or surveillance_relevant directly

**Tests:** Role-based access, filter combinations, bulk select, download URL
generation, unauthorized access 403.

---

## 6. Test Requirements

Every router session must produce a `tests/test_{router}_api.py` file with:

- Full CRUD round-trip test
- Role enforcement: one test per unauthorized role (Platform Admin protected
  → Lab Director gets 403; Lab-level protected → Lab Reader gets 403)
- Pagination test for list endpoints
- At least one error case (404 on missing resource, 409 on duplicate)
- Edge case specific to the router (e.g., ingest: unknown sequencing lab → 422)

Coverage must stay ≥ 80% after every session. Run
`uv run pytest --cov=backend --cov-report=term-missing` and check.

---

## 7. Verification

After every router session, verify:

```bash
# Tests pass and coverage holds
uv run pytest
# Expected: current baseline is 477 tests passing, 86.99% coverage drift-ok

# Health check still green
curl http://localhost:8000/health
# Expected: {"status":"ok","version":"5.0.0","project":"JACKPOT","database":"connected"}

# New endpoints reachable
curl -s http://localhost:8000/api/v1/{router}/ | python3 -m json.tool
# Expected: JSON response (not 404, not 500)

# Audit log populated on writes
psql postgresql://jackpot:jackpot@localhost:5432/jackpot_db \
  -c "SELECT action, resource_type, created_at FROM audit_log ORDER BY id DESC LIMIT 5;"

# No coverage regression
uv run pytest --cov=backend --cov-fail-under=60
```

**Before any GCP deploy to a new environment** (staging-clone, production):
run `docs/local_test_checklist.md` top to bottom. Part 1 step 5 (Alembic
from an empty DB) is the canonical sanity check — Q-9 closed the gap so
this should now pass without any bootstrap Job.

---

## 8. Month 2 — Sessions I–Q (Reference Specifications)

> These specifications document the pipeline/parser/infrastructure work
> built in Sessions I–Q. Most items are complete (see Section 4.4 status
> table); a few remain partial.

### Session I — jackpot-nf plugin contract + result registration

**Repo structure:**
`jackpot-nf` lives in a new 5th repo at `~/jackpot/jackpot-nf`, added
as a git submodule to `jackpot-backend` at `nf/`. Layout:

```
jackpot-nf/
├── plugins/nf-jackpot/       # Nextflow plugin — generic weblog/workdir handling
├── pipelines/                # Per-pipeline wrappers (populated Sessions J-M)
├── shared/
│   ├── jackpot_register_client.py   # HTTP client used by all parsers
│   ├── hamronization_normalizer.py  # AMR normalization wrapper
│   └── schemas/                      # Pydantic result payload schemas
├── tests/fixtures/           # Real pipeline output samples per pipeline
├── pyproject.toml
└── README.md
```

**Parser contract:**
Every pipeline parser implements this signature:

```python
def parse(output_dir: Path, run_metadata: RunMetadata) -> list[ParsedResult]:
    """
    Parse a pipeline's output directory into a list of typed results.
    Each ParsedResult has a result_type (str) and payload (dict matching
    the appropriate Pydantic schema in shared/schemas/).
    """
```

`ParsedResult.result_type` maps one-to-one to the endpoint path segment:
`amr_results`, `typing_results`, `tb_typing_results`, `pangolin_results`,
`nextclade_results`, `assembly_qc`, `mag_qc`, `taxonomic_profile`,
`wastewater_lineage_abundance`.

**Registration protocol:**

1. Pipeline wrapper runs upstream pipeline (Cecret, bactopia, etc.)
2. Wrapper calls `parse(output_dir)` on the corresponding parser
3. For each `ParsedResult`, wrapper calls
   `jackpot_register_client.register_result(result_type, payload)`
4. Client POSTs to `/api/v1/pipelines/{run_id}/results/{result_type}` with
   `pipeline_token` header
5. Server validates payload against Pydantic schema for that result_type
6. Server writes to the typed table AND updates `pipeline_results.metrics`
   JSONB in the same transaction

**Endpoint:**

- `POST /api/v1/pipelines/{run_id}/results/{result_type}` — register one
  typed result
  - Auth: `X-Pipeline-Token` header must match `pipeline_runs.pipeline_token`
  - Body: JSON payload matching the Pydantic schema for `result_type`
  - Returns: `{"status": "registered", "result_id": N}`
  - 401 if token mismatch, 404 if run_id unknown, 422 if payload schema
    invalid, 409 on duplicate (same run_id + result_type + sample_id)

**Version pinning:**

- New column: `pipeline_catalog.parser_version` — semver string, bumped
  when parser changes
- New column: `pipeline_runs.parser_version_used` — snapshot at run launch
- Each parser declares `SUPPORTED_PIPELINE_VERSIONS: list[str]`
  (e.g. `["3.6", "3.7", "3.66"]`)
- Wrapper validates pipeline version at run start, emits warning to
  `pipeline_events` if unsupported, continues anyway (doesn't hard-block)

**Shared utilities:**

- `jackpot_register_client.py`: single method
  `register_result(result_type, payload) → dict`; retries 5xx with
  exponential backoff (3 attempts); reads `JACKPOT_API_URL`,
  `JACKPOT_RUN_ID`, `JACKPOT_PIPELINE_TOKEN` from env
- `hamronization_normalizer.py`: wraps `hAMRonization` tool; input raw AMR
  file + tool name (`amrfinderplus`, `resfinder`, `rgi`); output list of
  `AMRResult` objects in canonical format; used by bactopia, Grandeur,
  pathogensurveillance

**Key rules:**

- Parsers never talk to the database directly — always via
  `jackpot_register_client`
- Result payloads are immutable — re-running a pipeline creates a new
  run_id with new results, never updates
- `log_audit()` on result registration with `REGISTER_PIPELINE_RESULT` action
- Schema import from `backend/models_generated.py` is the canonical source
  — parsers never define their own field lists

**Tests:**
Valid registration with correct token succeeds, wrong token returns 401,
invalid payload returns 422, duplicate returns 409, parser version mismatch
emits warning event but does not block.

---

### Session J — Viral pipeline parsers (Cecret, viralrecon, walkercreek)

**Pipelines:** `UPHL-BioNGS/Cecret`, `nf-core/viralrecon`, `UPHL-BioNGS/walkercreek`

**Result types produced:**

| Pipeline    | Output files parsed                                          | Target tables                                                |
|-------------|--------------------------------------------------------------|--------------------------------------------------------------|
| Cecret      | `pangolin/lineage_report.csv`, `nextclade/nextclade.tsv`, `freyja/aggregated-freyja.tsv`, `consensus/*.consensus.fa` | `pangolin_results`, `nextclade_results`, `wastewater_lineage_abundance`, `sample_files` |
| viralrecon  | `*.consensus.fa`, pangolin output, nextclade output, iVar variants | same as Cecret + `pipeline_results.metrics` for variants     |
| walkercreek | IRMA per-segment FASTAs, IRMA typing summary                 | `typing_results` (subtype, clade), `sample_files` (per-segment FASTA) |

**Key rules:**

- Cecret and viralrecon share pangolin and nextclade parsers via
  `jackpot-nf/shared/parsers/`
- Freyja output populates `wastewater_lineage_abundance` with one row per
  lineage per sample
- walkercreek outputs multiple FASTAs per sample (one per flu segment) —
  register all to `sample_files` with `file_subtype=segment_N`
- Supported version ranges declared in each parser's `SUPPORTED_PIPELINE_VERSIONS`

**Tests:**
Fixture-based — each parser has a real pipeline output in
`tests/fixtures/<pipeline>/` and a unit test that parses it and validates
the emitted payload list against Pydantic schemas.

---

### Session K — Bacterial isolate parsers (bactopia, Grandeur, mycosnp, tb-profiler)

**Pipelines:** `bactopia/bactopia`, `UPHL-BioNGS/Grandeur`,
`UPHL-BioNGS/mycosnp-nf`, `tb-profiler`

**Result types produced:**

| Pipeline    | Output parsed                                                | Target tables                                                |
|-------------|--------------------------------------------------------------|--------------------------------------------------------------|
| bactopia    | AMRFinderPlus TSV, MLST, QUAST assembly metrics, Bakta/Prokka GFF | `amr_results`, `typing_results`, `assembly_qc`, `sample_files` |
| Grandeur    | AMRFinderPlus, MLST, Kraken2 species ID, BLAST               | `amr_results`, `typing_results`, `taxonomic_profile`, `pipeline_results.metrics` |
| mycosnp-nf  | Snippy variants, SNP tree Newick, fungal typing              | `pipeline_results.metrics`, `sample_files`, `typing_results` |
| tb-profiler | Lineage JSON, drug resistance JSON                           | `tb_typing_results`                                          |

**Key rules:**

- All AMR output routes through `hamronization_normalizer.py` — produces
  canonical `AMRResult` regardless of source tool
- tb-profiler drug resistance also writes a mirror row to `amr_results`
  with `reference_database=WHO_catalogue` so TB appears in platform-wide
  AMR searches
- Grandeur and bactopia share the MLST parser and the AMRFinderPlus parser
  via `shared/`
- MAG-like single-organism isolates from Grandeur's Kraken2 output populate
  `taxonomic_profile` with only the top hit (not a full ranked list)

**Tests:** Fixture-based per parser.

---

### Session L — Metagenomic parsers (nf-core/mag, nf-core/taxprofiler)

**Pipelines:** `nf-core/mag`, `nf-core/taxprofiler`

**Result types produced:**

| Pipeline            | Output parsed                                         | Target tables                                                |
|---------------------|-------------------------------------------------------|--------------------------------------------------------------|
| nf-core/mag         | CheckM2 MAG quality, GTDB-Tk taxonomy, MAG bin FASTAs | `mag_qc`, `taxonomic_profile`, `sample_associations` (one-to-many MAG bins) |
| nf-core/taxprofiler | Kraken2 report, Bracken abundance, DIAMOND profile    | `taxonomic_profile`, `pipeline_results.metrics`              |

**Key rules:**

- nf-core/mag produces **one sample → many MAGs**. Each MAG bin is
  registered as a derived sample via `sample_associations` with
  `association_type=mag_bin`. The MAG sample inherits metadata from the
  parent metagenomic sample.
- `mag_qc` has one row per MAG bin with
  completeness/contamination/strain_heterogeneity/bin_size_bp
- Taxprofiler Kraken2 parser is shared with Grandeur's Kraken2 parser where
  possible
- GTDB-Tk taxonomy writes to `taxonomic_profile` with full lineage string

**Tests:** Fixture-based per parser.

---

### Session M — pathogensurveillance parser + shared validators

**Pipeline:** `nf-core/pathogensurveillance` pinned at version 1.1.0.

**Result types produced:**

| Output parsed                 | Target table                                                 |
|-------------------------------|--------------------------------------------------------------|
| sendsketch identification     | `taxonomic_profile`                                          |
| AMRFinderPlus → hAMRonization | `amr_results`                                                |
| MLST                          | `typing_results`                                             |
| core gene phylogeny Newick    | `sample_files` (file_subtype=core_tree)                      |
| BUSCO phylogeny Newick        | `sample_files` (file_subtype=busco_tree)                     |
| SNP phylogeny Newick          | `sample_files` (file_subtype=snp_tree)                       |
| graphtyper VCF                | `pipeline_results.metrics` (variant count, filtered count)   |
| Interactive HTML report       | `sample_files` (file_subtype=report, served via presigned URL) |

**Key rules:**

- Version pinned at 1.1.0 — any other version emits a `pipeline_events` warning
- Pipeline auto-selects reference genome per sample — parser captures
  selected reference ID in `pipeline_results.metrics.reference_selection`
  for reproducibility
- HTML report served via presigned URL in iframe from `pipelines.py` page
- Shared AMR normalization validator runs across bactopia, Grandeur, and
  pathogensurveillance output — flags when underlying tools produce
  divergent canonical AMRResult output

**Tests:**
Fixture-based parser tests + cross-pipeline AMR normalization comparison
test (runs all three AMR-producing parsers against matched inputs,
verifies canonical output is equivalent).

---

### Session N — pipelines router

**Endpoints:**

- `POST /api/v1/pipelines/launch` — launch a pipeline run
- `POST /api/v1/pipelines/events` — Nextflow weblog callback (no user auth,
  `pipeline_token` header required)
- `GET /api/v1/pipelines/{run_id}` — full run detail + recent events + task summary
- `GET /api/v1/pipelines/{run_id}/tasks` — paginated task list
- `GET /api/v1/pipelines/{run_id}/events` — paginated raw events
- `POST /api/v1/pipelines/{run_id}/resume` — resume a FAILED run
- `POST /api/v1/pipelines/custom` — BYOP registration skeleton (202 pending verification)
- `POST /api/v1/pipelines/{id}/promote` — promote pipeline project→lab
  (Lab Director) or lab→zoo (Platform Admin)
- `POST /api/v1/pipelines/{run_id}/results/{result_type}` — typed result
  registration (defined in Session I)

**Launch request body:**

```json
{
  "pipeline_id": 5,
  "sample_ids": ["sample_abc123", "sample_def456"],
  "parameters": {"profile": "illumina", "primer_set": "ncov_V5.3.2"},
  "project_id": 12,
  "override_soft_warnings": false
}
```

**Launch flow:**

1. `compute_pipeline_compatibility(pipeline_id, sample_ids)` returns
   `{soft_warnings: [], hard_blocks: []}`
2. Hard block → 422 with specific reason (e.g. "Pipeline requires assembly
   but sample has only raw reads")
3. Soft warnings without `override_soft_warnings=true` → 202 with warnings list
4. Otherwise proceed: generate per-run config via `pipeline_config.py`,
   create `pipeline_runs` row with status=QUEUED, submit to GCP Batch,
   return `{run_id, status}`
5. `resourceLabels` on GCP Batch job: `jackpot_run_id`, `jackpot_lab`,
   `jackpot_pipeline`
6. `log_audit()` with `CREATE_PIPELINE_RUN`

**Events callback:**

- No user JWT auth — `pipeline_token` in header must match
  `pipeline_runs.pipeline_token`
- Body: raw Nextflow weblog JSON
- Writes to `pipeline_events` (raw) and `pipeline_tasks` (parsed)
- Updates `pipeline_runs.status` on workflow-level events (started /
  completed / failed)

**Resume flow:**

- Source run must be in FAILED state (400 otherwise)
- Creates new `pipeline_runs` row with new `run_id`
- `pipeline_restarts` row links new_run_id ↔ previous_run_id with resume
  timestamp
- Reuses original `work_dir` for Nextflow `-resume`
- `log_audit()` with `RESUME_PIPELINE_RUN`

**BYOP skeleton:**

- Body: `{github_url, revision, parameter_schema_json}`
- Month 2: validates JSON shape only, writes `project_pipelines` row with
  `status=UNVERIFIED`, returns 202
- Month 3 adds: fetch `nextflow_schema.json` from repo, validate, enable launching

**Promotion:**

- project→lab: Lab Director only; writes `lab_pipelines` row with
  `promoted_by=user_id`, `promoted_at=NOW()`, `source_project_id`
- lab→zoo: Platform Admin only; updates `pipeline_catalog` tier, logs with
  `promoted_from=lab_id`
- `log_audit()` with `PROMOTE_PIPELINE`

**Key rules:**

- Pipeline compatibility never grays out options — always clickable,
  warnings/blocks explain why (Critical Rule: "no graying out")
- Per-run `work_dir` is mandatory and unique — two runs must never share a
  workDir prefix (Critical Rule 25)
- Config generated fresh per-run, never a static file (Critical Rule 26)
- `resourceLabels` required on all Batch jobs for cost attribution (Critical Rule 27)

**Tests:**
Launch with valid samples succeeds, hard block returns 422, soft warning
returns 202 then override proceeds, events callback with valid token writes
row, resume of non-FAILED run returns 400, promotion role enforcement.

---

### Session O — sample_access router

**Endpoints:**

- `POST /api/v1/sample_access/requests` — request access to a DISCOVERABLE sample
- `GET /api/v1/sample_access/requests` — list requests (scoped by role)
- `POST /api/v1/sample_access/requests/{id}/approve` — approve (Lab Director
  or Platform Admin)
- `POST /api/v1/sample_access/requests/{id}/deny` — deny (Lab Director or
  Platform Admin)

**Request body:**

```json
{
  "sample_id": "sample_abc123",
  "justification": "Need full metadata for outbreak investigation",
  "requested_duration_days": 90
}
```

**Request flow:**

1. Sample must be `sharing_level=DISCOVERABLE` (PRIVATE/LAB return 403 —
   researchers contact Lab Director directly for those)
2. Creates `sample_access_requests` row: `status=PENDING`,
   `auto_approve_after=NOW+7d`, `requester_id`, `justification`,
   `requested_duration_days`
3. Notifies Lab Director of owning lab via `create_notification()`
4. Returns 201 with `request_id`
5. `log_audit()` with `REQUEST_SAMPLE_ACCESS`

**List filters:**

- `?status=PENDING|APPROVED|DENIED|AUTO_APPROVED|EXPIRED`
- `?lab_id=N` (owning lab — Lab Director view)
- `?requester_id=me` (my requests)
- Lab Directors see all pending for their labs; Platform Admin sees all;
  requesters see only their own

**Approve flow:**

- Sets `status=APPROVED`, `approved_by=user_id`, `approved_at=NOW`
- `access_expires_at = NOW + requested_duration_days`
- Creates `sample_access_grants` row linking requester to sample
- Notifies requester
- `log_audit()` with `APPROVE_SAMPLE_ACCESS`

**Deny flow:**

- Sets `status=DENIED`, `denied_by=user_id`, `denial_reason`
- Notifies requester
- `log_audit()` with `DENY_SAMPLE_ACCESS`

**guards.py update:**
`can_access_sample()` now checks for active grant in `sample_access_grants`:

```python
def can_access_sample(user_id: int, sample_id: str, db) -> bool:
    # existing lab/project membership checks first...
    # then check for active grant
    grant = execute_query(
        "SELECT 1 FROM sample_access_grants "
        "WHERE user_id = :uid AND sample_id = :sid "
        "AND access_expires_at > NOW() LIMIT 1",
        {"uid": user_id, "sid": sample_id},
        conn=db,
    )
    return bool(grant)
```

**Background job (`run_access_request_job()` in `backend/jobs.py`):**
Runs nightly at 2:00 AM (per P0-12):

- Auto-approve requests where `auto_approve_after <= NOW()` and status
  still PENDING → status=AUTO_APPROVED, grant created
- Send 75-day warning where `auto_approve_after - 15 days` bracket matched
- Send 7-day warning where `access_expires_at - 7 days` bracket matched
- Expire grants where `access_expires_at <= NOW()`
- Mark requests MOOT where sample is now `sharing_level=PUBLIC`

**Key rules:**

- DISCOVERABLE samples show a **safe metadata subset** to all authenticated
  users (organism, date, country/state, source_type, sector, quality_status).
  Clinical fields stay masked until grant is approved.
- Grant expiry is absolute — no auto-renewal. Requester re-submits if still needed.
- Denial is final for the current request but not permanent — requester
  can re-apply after 30 days
- `log_audit()` on every state transition

**Tests:**
Request on DISCOVERABLE succeeds, request on PRIVATE returns 403, approve
creates grant, `can_access_sample()` returns True after grant,
`can_access_sample()` returns False after expiry, auto-approve past
deadline triggers correctly, 7-day expiry warning sent, denial blocks access.

---

### Session P — Streamlit researcher pages

**Scope:** Researcher-facing pages only. Admin pages (`lab_director.py`,
`platform_admin.py`, `archive_requests.py`, `billing.py`) deferred to Month 3.

**Pages implemented** (all live in `frontend/pages/`):

| Page                 | Purpose                                                      | Key API calls                                                |
|----------------------|--------------------------------------------------------------|--------------------------------------------------------------|
| `dashboard.py`       | Personal landing: recent samples, pending access requests, active pipeline runs | `GET /samples/?owner=me`, `/sample_access/requests?requester_id=me`, `/pipelines/?user_id=me` |
| `search.py`          | Sample search with full filter sidebar, bulk select, action bar | `GET /samples/` with filter params                           |
| `upload.py`          | Drag-and-drop ingest UI with live tier indicator and scrubber skip request | `POST /ingest/upload`                                        |
| `data_entry.py`      | Guided metadata entry + post-submission edit warning         | `PATCH /samples/{id}`                                        |
| `my_samples.py`      | User's owned samples with tier badges and scrub_status       | `GET /samples/?owner=me`                                     |
| `datasets.py`        | Analytical dataset list + creation from selection            | `GET /datasets/`, `POST /datasets/`                          |
| `access_requests.py` | Tabs: my requests / incoming (Lab Director view)             | `GET/POST /sample_access/requests`                           |
| `notifications.py`   | Notification inbox                                           | `GET /notifications/` (router stub — Month 3 full)           |
| `pipelines.py`       | Pipeline launcher + 4-tab monitoring view (Overview/Tasks/Events/Files) + resume + MultiQC iframe | `POST /pipelines/launch`, `GET /pipelines/{run_id}*`         |

**Frontend conventions:**

- All API calls go through a single `frontend/lib/api.py` client
  (`ApiClient` class) with cookie-based auth
- Session state keys prefixed by page: `search.selected_ids`,
  `upload.draft_metadata`, etc.
- Navigation via `st.sidebar` with page list auto-generated from
  `frontend/pages/` directory
- Tier badge component in `frontend/components/badges.py` — renders
  PRELIMINARY/ANALYZABLE/SUBMITTABLE and PRIVATE/LAB/DISCOVERABLE/PUBLIC
  with consistent colors across all pages
- No business logic in pages — all logic stays in backend routers
  (Streamlit is presentation only)
- Forms use `st.form` with server-side validation via API response, not
  client-side

**Post-submission edit warning (data_entry.py):**
When a sample has `ncbi_submission_status != NOT_SUBMITTED` or
`gisaid_submission_status != NOT_SUBMITTED`, editing these fields triggers
a warning modal before save:

- `organism_name`, `collection_location_country`,
  `collection_location_state`, `date_collected`, `host_species`,
  `isolation_source`, `bioproject_accession`, `biosample_accession`

Modal text: "This sample has been submitted to NCBI/GISAID. Editing these
fields will create a discrepancy between JACKPOT and the external database.
Continue?"

**Key rules:**

- Pages are stateless between sessions — use `st.session_state` only for
  current-session UI state
- Loading states: every API call shows `st.spinner` or progress bar
- Error handling: API error responses render as `st.error` with the server's
  error message, never as raw exception
- All list pages use server-side pagination — never load all rows at once

**Tests:**
Smoke tests only in Month 2 — each page imports cleanly, renders without
errors with mocked API responses. Full Playwright end-to-end testing
deferred to Month 3.

---

### Session Q — GCP staging environment

**Scope:** Staging only. Production deferred to Month 3. See Section 9 for
the full as-built topology and cost profile.

**Infrastructure (Terraform in `deploy/terraform/staging/`):**

| Resource                       | Config                                                       |
|--------------------------------|--------------------------------------------------------------|
| Cloud SQL Postgres 16          | Smallest tier (`db-custom-1-3840` as deployed), daily backups, PITR 7 days, private IP only |
| GKE cluster                    | Regional, 3 node pools: `api-pool` (min=1, n2-standard-4), `workspace-pool` (min=0, n2-standard-8), `scrubber-pool` (min=0, n2-highmem-4, spot) |
| GCS buckets (all us-central1)  | `jackpot-staging-raw`, `-sequences`, `-work`, `-results`, `-datasets`, `-submissions`, `-backups` |
| Lifecycle rules                | 90-day delete on `-work`, 365-day Coldline transition on `-sequences`/`-results` |
| Secrets Manager                | SECRET_KEY, Google OAuth client/secret, NCBI API key, GISAID credentials — all fresh, not reused from local |
| Artifact Registry              | Docker image repo for `jackpot-api`, `jackpot-ui`, `jackpot-scrubber` |
| resourceLabels (all resources) | `env=staging`, `project=jackpot`                             |

**Deployment pipeline:**

- Trigger: push to `staging` branch on jackpot-backend
- Steps: build image → push to Artifact Registry → `helm upgrade`
  api/ui/scrubber deployments → `alembic upgrade head` against Cloud SQL →
  run staging smoke test
- Staging uses separate image tags (`staging-<sha>`) from production

**Seed data:**
Alembic migrations produce schema; `scripts/seed_staging.py` loads orgs,
labs, sequencing_labs, reportable_organisms, pipeline_catalog. No real
sample data — staging is for E2E verification only.

**End-to-end test (currently blocked — Q-5 on the backlog):**
Run Cecret or viralrecon against a SARS-CoV-2 test sample through the full
stack:

1. Upload sample via staging API
2. Scrubber runs in `scrubber-pool`
3. Launch pipeline via `POST /pipelines/launch`
4. Nextflow controller in `api-pool` submits GCP Batch jobs
5. Weblog events flow back to `POST /pipelines/events`
6. Wrapper registers typed results via
   `POST /pipelines/{run_id}/results/{result_type}`
7. Verify `pangolin_results` and `nextclade_results` tables populated
8. MultiQC iframe renders in Streamlit `pipelines.py`

Documented in `docs/staging_e2e_test.md` once run.

**Smoke test script:**
`scripts/staging_smoke_test.sh` hits every endpoint, verifies auth flow,
confirms one pipeline runs successfully. Red/green output. Run after every
staging deploy. Currently uses `kubectl port-forward` as a tactical
workaround until public Ingress lands (Phase 20 Q-14).

**Access control:**
`deploy/docs/staging_access.md` documents who has access
(the project owner + designated reviewers), how to reach staging URLs, how to redeploy, how to
read Cloud Logging.

**Key rules:**

- Staging is **not** a production mirror — it uses synthetic data only
- Staging URLs never appear in `.env.local` or committed config — they're
  in Secrets Manager only
- Staging database can be wiped and reseeded at any time — no real samples in it
- Any pattern that works in staging must be verified in Critical Rules
  before proceeding to Month 3 production

**Tests:**
E2E smoke test (above) + Terraform plan/apply idempotency (running
`terraform apply` twice produces no changes the second time).

---

## 9. Session 5 — GCP Staging Deployment (as deployed 2026-04-17)

Everything below reflects the actual staging environment as it existed at
the end of Session 5. Architecture diagrams live at
`~/jackpot/docs/jackpot_gcp_staging_deployment.html`.

### 9.1 Project-level facts

- **GCP project:** `jackpot-staging-project`
- **Region:** `us-central1`
- **IaC owner:** `deploy/terraform/staging/`
- **Deploy trigger:** push to `staging` branch of jackpot-iac

### 9.2 Network & security

- **VPC:** `jackpot-staging-vpc` with Cloud NAT, Cloud Router, Private
  Service Connect for Cloud SQL
- **WIF pool:** `github-actions-pool` binds GitHub's OIDC token to
  `deploy-sa@...iam.gserviceaccount.com`
- **Service accounts (3):**
  - `deploy-sa` — CI deploy identity (build, push, helm)
  - `jackpot-api-sa` — bound to the K8s `jackpot-api` ServiceAccount via
    Workload Identity; grants GCS + Secret Manager read/write
  - `scrubber-sa` — DLP + scrubber-pool identity (not yet exercised)

### 9.3 Compute (GKE cluster `jackpot-staging-gke`)

| Pool              | Machine type     | Spot | Autoscale        | Currently running |
|-------------------|------------------|------|------------------|-------------------|
| `api-pool`        | n2-standard-4    | No   | min=1 max=3      | 2                 |
| `scrubber-pool`   | n2-highmem-4     | Yes  | min=0 max=3      | 0                 |
| `workspace-pool`  | n2-standard-8    | No   | min=0 max=2      | 0                 |

**Namespace `jackpot`** contains:

- Deployment `jackpot-api` (2/2 pods Ready, image tag `535dcdb`)
- Service `jackpot-api` (ClusterIP :80)
- ConfigMap `jackpot-api-config` (non-secret env vars)
- Secret `jackpot-api-secrets` (synced from Secret Manager every deploy)
- ServiceAccount `jackpot-api` (WI-bound to `jackpot-api-sa`)
- Helm release `jackpot-api` (rev 12, STATUS: deployed)

### 9.4 Managed services

- **Cloud SQL:** `jackpot-staging-db`, PostgreSQL 16, `db-custom-1-3840`,
  private IP `10.188.230.3`, database `jackpot_db`, Alembic head
  `c536de6329e0`
- **GCS buckets (7, all prefixed `jackpot-staging-`):** `sequences`,
  `staging`, `references`, `results`, `work`, `backups`, `portal-exports`
- **Artifact Registry:**
  `us-central1-docker.pkg.dev/jackpot-staging-project/jackpot/jackpot-api`
- **Secret Manager** (5 secrets): `jackpot-staging-secret-key`,
  `jackpot-staging-database-url`, `jackpot-staging-google-oauth-client-id`,
  `jackpot-staging-google-oauth-client-secret`, `jackpot-staging-ncbi-api-key`

### 9.5 GitHub Actions secrets

- **Fine-grained PAT `CROSS_REPO_PAT`** — Contents: Read on all three
  backend repos (jackpot-backend, jackpot-nf, jackpot-schema). This is how
  the workflow authenticates submodule clones. **Never paste a Google OAuth
  client secret (prefix `GOCSPX-`) into this — see Critical Rule 45.**
- **GCP_WIF_PROVIDER** (vars.) — full WIF provider resource name
- **GCP_DEPLOY_SA** (vars.) — deploy-sa email

### 9.6 Current access path

The staging API **has no public URL**. All current access is via
`kubectl port-forward svc/jackpot-api 8080:80`, then hitting
`http://localhost:8080`. The smoke test runs this way both on developer
laptops and on the GitHub Actions runner in CI. Public Ingress + DNS +
managed cert is Phase 20 Q-14 on the backlog.

Local DB access for debugging: `cloud-sql-proxy` against
`jackpot-staging-project:us-central1:jackpot-staging-db` on `127.0.0.1:5432`.

### 9.7 Known quirks / tactical fixes in place

These six fixes landed during the first deploy. Permanent fixes are
tracked in Phase 20 Q-9 through Q-17 on `todo.md`:

1. ~~**Bootstrap Job loads `db/init.sql` on first deploy.**~~ **Closed
   by Q-9.** The baseline Alembic migration `5adf11b77c19` now builds
   the schema from an empty DB; the bootstrap Job is gone.
2. **`cors_origins` env value is a JSON-array string in `values-staging.yaml`.**
   Pydantic-settings v2 otherwise tries to JSON-parse it. Permanent fix:
   `Annotated[list[str], NoDecode]` validator (Q-10).
3. **`Dockerfile.api` does `COPY nf/ ./nf/`.** `routers/pipelines.py`
   imports from `shared.schemas` via `sys.path.insert`. Permanent fix:
   move schemas into the backend package (Q-11).
4. **`DATABASE_URL` Secret is hand-edited.** Off-by-one like `/jackpot`
   vs `/jackpot_db` is trivially easy. Permanent fix: Terraform-owned
   Secret construction (Q-12).
5. **Smoke test uses `kubectl port-forward svc/jackpot-api 8080:80`.**
   Permanent fix: public Ingress (Q-14).
6. **Helm `--wait --timeout 10m` wedges at `pending-upgrade` on
   timeout.** Permanent fix: add `--atomic` or pre-upgrade cleanup (Q-15).

### 9.8 Cost profile (24/7 run-rate)

| Line item                                  | Monthly     |
|--------------------------------------------|-------------|
| GKE management (regional, no free tier)    | ~$73        |
| api-pool 2× n2-standard-4                  | ~$284       |
| Cloud SQL db-custom-1-3840 zonal           | ~$55        |
| GCS, Artifact Registry, Logging            | ~$10        |
| **Total**                                  | **~$420/mo**|

**Scale-down commands** (to pause the stack overnight):

```bash
# Scale api-pool to 0 (stops ~$284/mo of compute)
gcloud container clusters resize jackpot-staging-gke \
  --node-pool=api-pool --num-nodes=0 \
  --region=us-central1 --project=jackpot-staging-project

# Stop Cloud SQL (stops ~$55/mo but also halts PITR)
gcloud sql instances patch jackpot-staging-db \
  --activation-policy=NEVER --project=jackpot-staging-project
```

Reverse by setting api-pool to `--num-nodes=2` and Cloud SQL
`--activation-policy=ALWAYS`.

---

## 10. Streamlit UI — Local Environment (as deployed 2026-04-19)

### 10.1 Where the code lives

The Streamlit UI lives in `frontend/` at the repo root.

Layout:

```
frontend/
├── __init__.py
├── app.py                    # Streamlit entry point (landing + nav)
├── components/               # Shared widgets (tier badges, etc.)
│   ├── __init__.py
│   └── badges.py
├── lib/                      # Cross-page helpers
│   ├── __init__.py
│   ├── api.py                # ApiClient + ApiError (see Section 10.4)
│   └── session.py            # current_user(), my_user_id(), ...
└── pages/                    # Streamlit auto-loads each of these
    ├── __init__.py
    ├── dashboard.py
    ├── search.py
    ├── upload.py
    ├── data_entry.py
    ├── my_samples.py
    ├── datasets.py
    ├── access_requests.py
    ├── notifications.py
    └── pipelines.py
```

### 10.2 How to run it

```bash
cd ~/jackpot/jackpot-backend
docker compose up -d
# Open http://localhost:8501
```

Or standalone (no Docker):

```bash
cd ~/jackpot/jackpot-backend
uv run streamlit run frontend/app.py
```

The Docker Compose form is preferred for local dev — it runs everything
together: `api`, `postgres`, `minio`, `minio_init`, `ui`. All five should
report healthy via `docker compose ps`.

### 10.3 Docker/Compose contract (post-Session 5)

The `ui` service in `docker-compose.yml`:

```yaml
ui:
  build:
    context: .
    dockerfile: Dockerfile.ui
  container_name: jackpot_ui
  environment:
    API_BASE_URL:    http://api:8000
    ENV:             local
    MOCK_USER_EMAIL: admin@example.org
    PYTHONPATH:      /app                    # REQUIRED — see 10.5
  ports:
    - "8501:8501"
  volumes:
    - ./frontend:/app/frontend                # must mount as frontend/ subdir
    - ./schema:/app/schema
  depends_on:
    - api
```

`Dockerfile.ui`:

```dockerfile
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY frontend/ ./frontend/                    # preserve the package path
EXPOSE 8501
CMD ["/opt/venv/bin/streamlit", "run", "frontend/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
```

The `api` service (separately) must also set `MOCK_USER_EMAIL` — the UI
sends `X-Mock-User-Email` as a parity hint, but the actual identity lookup
happens server-side via `os.getenv("MOCK_USER_EMAIL")` on the API container.

### 10.4 ApiClient contract

`frontend/lib/api.py` exposes a single `ApiClient` class:

- Resolves `base_url` from (in order): explicit arg → `JACKPOT_API_URL` →
  `API_BASE_URL` → `http://localhost:8000`. **Both env-var names are
  supported.**
- Unwraps the standard response envelope: `{"success": true, "data": ...}`
  → returns `data`; `{"success": false, "error": {...}}` → raises `ApiError`.
- Network failures raise `ApiError(code="NETWORK", ...)`.
- Ships `X-Mock-User-Email` header when `MOCK_USER_EMAIL` is set in the
  environment.
- Shared singleton via `get_client()`; tests swap with `set_client()`.

Every page must go through this client. Pages never import `requests` or
`httpx` directly.

### 10.5 Six bugs fixed during Session 5 UI debug (for future reference)

These are recorded because they will re-occur the first time a teammate
runs the stack locally. All six were diagnosed and fixed in a single
debugging session:

1. **`Dockerfile.ui` `COPY frontend/ .` flattened the layout.** Replaced
   with `COPY frontend/ ./frontend/` so the `frontend` package name is
   preserved. CMD updated to `frontend/app.py`.
2. **Compose `volumes: - ./frontend:/app` overrode the image's layout**
   with the flattened form. Replaced with `./frontend:/app/frontend` and
   `./schema:/app/schema`.
3. **Compose `command:` directive overrode the image CMD.** Removed the
   `command:` line so the image's correct CMD takes over.
4. **Streamlit's `sys.path[0]` is the script directory**
   (`/app/frontend/`), so `from frontend.lib.session import current_user`
   failed because `/app` wasn't on the path. Added `PYTHONPATH=/app` to
   the `ui` service env.
5. **`ApiClient` only read `JACKPOT_API_URL`** but compose was setting
   `API_BASE_URL`. Added the latter as a fallback.
6. **Landing page shows "API unreachable"** even when the API is fine —
   `current_user()` returns `None` for both network and auth failures, and
   `app.py` conflates them. Fix is tracked as Phase 20 Q-18; not yet applied.

### 10.6 Auth in local dev

- `MOCK_USER_EMAIL=admin@example.org` on both `api` and `ui` services
- Streamlit sends the header; FastAPI's `get_current_user` looks up the env
  var and resolves it via the `users` table
- Seeded user record (ID 1): the maintainer, platform admin, Example Lab director
- Landing page should show "Signed in as the maintainer" once Q-18 lands; today
  it shows a misleading "API unreachable" banner even when auth is fine

---

## 11. Current Priorities — Active Sprint

These are the backlog items that must be burned down before the project
is in a clean, teammate-onboardable, production-ready state. All cross-referenced
to `todo.md`.

### 11.1 Phase 20 — Session 5 Debt

**Q-9 (P0):** ✅ Closed — baseline migration `5adf11b77c19` makes
`alembic upgrade head` work from an empty DB. Bootstrap Job retired.

**Q-10 (P0):** ✅ Closed — `cors_origins` validator with `NoDecode`
+ `field_validator` in `backend/config.py` lands; env var accepts
plain comma-separated, JSON, or empty.

**Q-11 (P0):** ✅ Closed — `sys.path` hack removed; `RESULT_SCHEMAS`
moved to `backend/backend/pipeline_schemas/` package (better than
spec'd: a package per-result-type, not a single flat file).
Architectural resolution recorded in `docs/learnings.md` (P0d entry).

**Q-12 (P1):** Terraform-owned `DATABASE_URL` Secret construction. Removes
the off-by-one failure mode.

**Q-13 (P1):** Rotate staging DB password (was visible in chat during
Session 5 debugging).

**Q-14 (P1):** Public Ingress + DNS + managed cert for staging. Unblocks
real Google OAuth flow testing and the staging E2E pipeline test (Q-5).

**Q-15 (P1):** `helm upgrade --atomic` or auto-rollback on failure. Prevents
stuck `pending-upgrade` states.

**Q-16 (P2):** Bump GitHub Actions to Node 24 (Node 20 deprecated
2026-09-16).

**Q-18 (P2):** Fix misleading "API unreachable" banner on Streamlit landing
page — distinguish network failure from auth failure.

### 11.2 Phase 21 — UI Page Triage

Walk each of the 9 Streamlit researcher pages. Log render behavior in
`docs/review_log.md`. Fix what breaks. Order:

- UI-A: Landing page — ✅ COMPLETE (renders, sidebar populates, auth works)
- UI-B: Upload page
- UI-C: Search page
- UI-D: Sample detail page
- UI-E: Dashboard page
- UI-F: My Samples, Access Requests, Notifications, Datasets, Pipelines

Once UI-B through UI-D are green, the Month 1 human-testable demo is
achievable: upload a sample → find it in search → view its detail, all
through the browser.

### 11.3 Phase 23 — Minimal Nextflow Test Pipeline

**P3.1:** `scripts/test_batch.nf` — 20-line pipeline that echoes a string,
writes a result file, exits. Configured with
`-weblog http://localhost:8000/api/v1/pipelines/events` locally, public URL
in staging. Smallest possible exerciser of the weblog receiver and pipeline
state machine. Worth having before viralrecon or any nf-core pipeline.

### 11.4 Phase 24 — End-to-end Pipeline Test on Staging

Closes Q-5. Depends on Q-9, Q-14, P3.1, UI-B, and UI-F pipelines page.
Full chain: upload → scrub → pipeline launch → weblog events → typed
result registration → UI-visible MultiQC report. Once green, tag
`month-2-complete`.

---

## 12. Reference Materials

### Architecture diagrams

All in `~/jackpot/docs/` unless noted:

- `jackpot_gcp_staging_deployment.html` — Infrastructure reference
  + mental model (layered with Session 5 callouts)
- `architecture.md` (v6.0) — consolidated architecture doc (replaces `jackpot_architecture_v5.md`, `JACKPOT_Architecture_Synthesis_May_2026.md`, and `Core_Technical_Pillars_copy.md` per the May 2026 Cluster A merge)
- `jackpot_session_summary_and_backlog.md` — design decisions + backlog,
  the running engineering log (v2.4 includes Phase 26 backlog)
- `jackpot_schema.yaml` — LinkML schema source of truth

### Comparative analysis and architectural design documents (April 2026)

These three documents are the source of truth for the post-P0d roadmap. Cross-referenced throughout `todo.md` for B-XXX backlog item provenance.

- **`jackpot_pathoplexus_loculus_overview.md`** (1,873 lines, 2026-04-28) — Comparative analysis between JACKPOT and the Pathoplexus/Loculus stack plus 8 peer platforms (GenSpectrum/LAPIS, Pathogenwatch, EnteroBase, NCBI Pathogen Detection on GCP, BV-BRC, Solu, RT-MetA, GISAID). Source of truth for: AGPL-3.0 license decision rationale (§3), peer-platform landscape (§4), JACKPOT vs Loculus architectural divergence (§6-10), two-PII-gate architecture documentation (§9), code adoption recommendations A1-A6 (§11), federation tiers (§12), Phase 26 backlog of 34 items grouped A-J by source platform (§16.10).

- **`jackpot_cdc_dmi_stlt_overview.md`** (816 lines, 2026-04-28) — Alignment with US public-health-data ecosystem. Source of truth for: CDC DMI history and North Star Architecture goals (§1), STLT public health landscape with extra weight on Indigenous data sovereignty (§2), CARE Principles formal adoption (§2.3c), four install scenarios with sovereignty-aligned runtime policy capabilities (§6 — per the Cluster A merge, sovereignty is a runtime policy applicable to any scenario rather than a separate Scenario T), tombstone-and-vacuum architectural pattern for sovereignty-compliant deletion (§7), Tribal Epidemiology Center federation pattern (§8), JACKPOT vs NBS/eCR/AIMS layer-cake (§9), funding-source map for STLT operators (§10), Phase 27 backlog of 14 items grouped K-M.

- **`byop_and_eukaryotic_design.md`** (1,456 lines, 2026-04-29) — Multi-engine BYOP infrastructure plus full-parity eukaryotic pathogen support. Source of truth for: four-engine BYOP architecture — Nextflow, Snakemake, WDL, manifest-wrapped scripts (§1-3), `jackpot-pipeline.yaml` manifest schema (§2), four source types — public/private Git, tarball upload, Docker image (§4), two-stage validation gating with sandbox dry-run isolation (§5), pipeline lifecycle state machine (§6), schema additions for `byop_pipelines` table and 8 eukaryotic pipeline-result tables (§7, §12), 8 default eukaryotic pathogen pipelines (§13), 25 backlog items split across Phase 24.5 schema lockdown (4 items), Phase 24.7 / P0f BYOP infrastructure (10 items), Phase 28 default eukaryotic pipelines + parsers + dashboards (11 items, internally tier-prioritized).

### Operational runbooks

- `docs/local_test_checklist.md` — pre-GCP-deploy
  validation (API + UI parts)
- `deploy/docs/staging_access.md` — staging access and troubleshooting
- `docs/CLAUDE.md` — 60 Critical Rules

### Code quality / CI

- `gac "type: description"` for all commits — runs ruff fix + format
- Pre-commit hooks: ruff (SIM102, E501, B008 among others)
- Test coverage threshold 80% enforced in CI (post-P0e baseline)
- GitHub Actions workflow `.github/workflows/deploy-staging.yml` triggers
  on push to `staging` branch

---

## 13. Open Questions / Decisions Log

### April 2026 — pivot decisions

- **License flipped Apache 2.0 → AGPL-3.0.** Strategic, not legal. Closes the SaaS loophole via §13. Joins the European public-health pathogen-genomics cluster (Loculus, GenSpectrum/LAPIS, SILO, dashboard-components — all AGPL-3.0). Anti-GISAID-capture stance. Unblocks direct code adoption from the entire Loculus stack. See `jackpot_pathoplexus_loculus_overview.md` Section 3 for the full rationale.
- **Multi-deployment-target architecture.** 4 install scenarios (A–D), reduced from 7 in the May 2026 Cluster A merge. Federation, multi-org tenancy, and Indigenous data sovereignty are runtime configurations applied to A/B/C rather than separate install scenarios. Production code is operator-agnostic; `jackpot init` (P0e) handles per-operator bootstrap.
- **Phasing post-Phase-11.** Phases 6.1–11 cosmetic genericization → P0d (monorepo migration) → P0e (install/CLI architecture) → Phase 24.5 (architectural design lockdown) → P0f (BYOP infrastructure) → P0b (Schema v5.0 — instances/tenants/federated_peers + BYOP/eukaryotic schema) → P0c (multi-tenancy middleware + sovereignty deletion) → P1–P5 (operator-type configurability, federation, governance, reference deployments, new-needs integration).
- **Don't replace existing ingest gates.** `file_detector.py`, `validator.py`, `dlp_scanner.py`, and the `sra-human-scrubber` Nextflow integration collectively constitute a more thorough ingest pipeline than anything in Loculus's preprocessing for JACKPOT's surveillance-focused operating model. The recommendation is to expose the Loculus pluggable preprocessing HTTP contract (`/extract-unprocessed-data`, `/submit-processed-data`) as an *opt-in* for sophisticated operators while keeping in-process validation as the default.
- **Sovereignty as runtime policy (May 2026, supersedes original Scenario T design).** Indigenous data sovereignty was originally framed as a separate deployment scenario (Scenario T as a variant of A or E). The May 2026 Cluster A merge reframed this: sovereignty-aware capabilities — deletion-on-request via tombstone-and-vacuum lifecycle, no auto-publish to NCBI/INSDC, federation policy restrictions, audit visibility, residency enforcement, revocable consent — are runtime policies that any deployment can configure post-install, rather than a dedicated scenario. A Tribal college running JACKPOT for genomics coursework picks Scenario A and does not configure sovereignty policies. A Tribal Nation health department running JACKPOT under CARE Principles also picks Scenario A and configures sovereignty policies via `jackpot policy enable ...`. CARE Principles compliance documented in `governance/care-principles-and-indigenous-data-sovereignty.md`. See `docs/architecture.md` §22 for the full design and `jackpot_cdc_dmi_stlt_overview.md` Section 6 for the original Scenario T design notes.
- **CARE Principles formally adopted** alongside FAIR. Indigenous Data Sovereignty (Collective Benefit, Authority to Control, Responsibility, Ethics) becomes a first-class design constraint for any deployment configured with sovereignty-aligned runtime policies. The platform's enforcement primitives (residency, revocable consent, no-auto-publish defaults, federation policy restrictions, audit portal) are available to all scenarios; per-org policy enablement determines which apply.
- **Layer-cake positioning.** JACKPOT is the genomics layer between LIMS and downstream analysis platforms (NCBI Pathogen Detection, Pathoplexus, Pathogenwatch, Nextstrain). It integrates with NBS/eCR/AIMS — does not replace them. See `jackpot_cdc_dmi_stlt_overview.md` Section 9.

### April 2026 — BYOP and eukaryotic pipelines decisions

- **BYOP supports four workflow engines:** Nextflow, Snakemake, WDL, and manifest-wrapped scripts (Bash/Python). The fourth engine is JACKPOT-specific — for users with a working script who don't want to learn a workflow language. Trades workflow-engine features (parallelization, resume, multi-container) for simplicity.
- **BYOP supports four source types:** public Git URL (with tag/branch/SHA), private Git with deploy keys (per-pipeline keys stored in operator's secret manager), uploaded tar.gz (max 500 MB compressed), Docker image with manifest path. Each source type has explicit constraints documented in §4 of the design doc.
- **Two-stage validation gating:** static checks (manifest schema, engine syntax, container/reference resolution, license, permissions) + sandbox dry-run (isolated namespace/network, 5-minute timeout, synthetic test inputs). Both must pass before pipeline activates. Re-validation runs quarterly to catch upstream rot. Static-only would let runtime bugs through; sandbox-only would miss easy structural problems; full Lab Director approval would discourage adoption. Two-stage is the right balance.
- **Full-parity eukaryotic pathogen support** across 8 pathogen groups (Plasmodium, Leishmania, Trypanosoma, Schistosoma, soil-transmitted helminths, filarial nematodes, Cryptosporidium/Giardia, Toxoplasma/Entamoeba). Includes 25 OrganismNameEnum additions, 8 dedicated pipeline-result tables, 10 default zoo pipelines, 8 dashboard pages, eukaryotic-aware tier-validation rules.
- **BYOP/eukaryotic phasing decision (2026-04-29).** The 25 backlog items split three ways rather than landing in one homogeneous phase: (1) **schema items (4) move to Phase 24.5** — must lock before P0b touches the schema, otherwise double-migrate. (2) **BYOP infrastructure (10) gets new P0f phase** between P0e and P0b/c — eukaryotic pipelines can't land without it, and P1 is too late. (3) **Default eukaryotic pipelines + parsers + dashboards (11) stay in Phase 28** but internally tier-prioritized: Tier 1 (Plasmodium, Crypto/Giardia) ships first.

### Carried over

- ~~When to retire `jackpot-frontend` repo?~~ Resolved: repo archived
  under P0d; UI consolidated into `frontend/` at the monorepo root.
- **Option A vs Option B for Q-11** (move schemas into backend vs vendor
  nf/shared). Leaning Option A.
- **`--atomic` vs custom pre-upgrade cleanup for Q-15.** `--atomic` loses
  debug evidence on timeout; cleanup keeps it. Either works; decision
  deferrable until Q-15 is actually touched.
- **First real pipeline for Q-5 E2E test.** viralrecon recommended over
  Cecret as better-documented nf-core reference.

---

*End of spec. For the rolling task list with check-boxes, see `todo.md`.*
