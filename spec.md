# JACKPOT — Project Specification

**Version:** 2.0
**Last updated:** 2026-04-19 (post-Session 5 — staging deploy + Streamlit local debug)
**Status:** Month 1 + most of Month 2 complete — active sprint on Session 5 debt and UI page triage
**Audience:** Claude Code autonomous agent + the maintainer

---

## 1. Project Goal

Build **JACKPOT** — a pathogen genomics platform for genomic epidemiology,
bioinformatics, and public health research — for the host operator. JACKPOT is the successor to APGAP
(legacy single-institution platform). It must be APGAP-compatible: same org/lab/project/user
hierarchy, same PermissionGroups enum string values, same role semantics.

The platform enables public health labs to:

- Ingest raw sequencing data (FASTQ, FASTA) with structured metadata
- Validate metadata against a tiered quality model (PRELIMINARY / ANALYZABLE / SUBMITTABLE)
- Scrub human reads from sequencing data before analysis
- Launch bioinformatics pipelines (nf-core, GHRU) against their samples
- Export data to GISAID, NCBI BioSample/SRA, and TOSTADAS
- Search, filter, and analyze samples across the platform
- Control data access with a fine-grained sharing and governance model

---

## 2. Current Baseline (end of Session 5)

- **477 tests passing, 86.99% coverage** (baseline from Session S complete;
  Session 5 added staging infra changes without net-new test coverage)
- CI threshold: 60% — must never fall below this
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

### Language and Tools

- Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2
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
- Local dev: MinIO via `STORAGE_BACKEND=minio`; production: GCS via
  `STORAGE_BACKEND=gcs`

### Business Logic Constraints

- `PermissionGroups` enum values are sacred — must match APGAP exactly
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
5. ✅ JWT refresh endpoint — `POST /api/v1/auth/refresh` implemented.
6. ✅ Full test suite — passing, coverage ≥ 60%.
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

**Tests:** CRUD, assignment workflow, list returns seed data (Sonora Quest,
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

Coverage must stay ≥ 60% after every session. Run
`uv run pytest --cov=backend --cov-report=term-missing` and check.

---

## 7. Verification

After every router session, verify:

```bash
# Tests pass and coverage holds
uv run pytest
# Expected: current baseline is 477 tests passing, 86.99% coverage

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

**Pages implemented** (all live in `jackpot-backend/frontend/pages/`):

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

**Infrastructure (Terraform in `jackpot-iac/terraform/staging/`):**

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
`docs/staging_access.md` (in `jackpot-iac/docs/`) documents who has access
(Glen + 2 operator staff members), how to reach staging URLs, how to redeploy, how to
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
- **IaC owner:** `jackpot-iac/terraform/staging/`
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

The Streamlit UI lives **inside `jackpot-backend/frontend/`** — NOT in the
separate `jackpot-frontend` repo. The `jackpot-frontend` repo is a
vestigial stub; its `main.py` is literally
`print("Hello from jackpot-frontend!")`. Retiring it is a Month 3 item.

Layout:

```
jackpot-backend/frontend/
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

**Q-10 (P0):** `cors_origins` validator with `NoDecode` + `field_validator`
in `backend/config.py`. Lets env var be plain comma-separated again.

**Q-11 (P0):** Remove `sys.path` hack from `pipelines.py`. Move
`RESULT_SCHEMAS` into `backend/pipeline_schemas.py`. Can then drop
`COPY nf/` from `Dockerfile.api`.

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

**Q-17 (P2):** Add Session 5 lessons to CLAUDE.md Critical Rules 42-47.

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
  (APGAP-style) + mental model (layered with Session 5 callouts)
- `jackpot_architecture_v5.md` — 1,860-line architecture doc
- `jackpot_session_summary_and_backlog.md` — design decisions + backlog,
  the running engineering log
- `jackpot_schema.yaml` — LinkML schema source of truth

### Operational runbooks

- `jackpot-backend/docs/local_test_checklist.md` — pre-GCP-deploy
  validation (API + UI parts)
- `jackpot-iac/docs/staging_access.md` — staging access + bootstrap Job +
  troubleshooting
- `docs/CLAUDE.md` — 51 Critical Rules

### Code quality / CI

- `gac "type: description"` for all commits — runs ruff fix + format
- Pre-commit hooks: ruff (SIM102, E501, B008 among others)
- Test coverage threshold 60% enforced in CI
- GitHub Actions workflow `deploy-staging.yml` in `jackpot-iac/` triggers
  on push to `staging` branch

---

## 13. Open Questions / Decisions Log

- **When to retire `jackpot-frontend` repo?** Currently vestigial.
  Tracked as Month 3 stretch goal.
- **Option A vs Option B for Q-11** (move schemas into backend vs vendor
  nf/shared). Leaning Option A.
- **`--atomic` vs custom pre-upgrade cleanup for Q-15.** `--atomic` loses
  debug evidence on timeout; cleanup keeps it. Either works; decision
  deferrable until Q-15 is actually touched.
- **First real pipeline for Q-5 E2E test.** viralrecon recommended over
  Cecret as better-documented nf-core reference.

---

*End of spec. For the rolling task list with check-boxes, see `todo.md`.*
