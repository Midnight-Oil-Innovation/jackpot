> **Status:** Superseded — archived (directory convention). Historical; do not cite as current.

# JACKPOT — Status & Roadmap

**Document type:** Standalone retrospective + status + forward sequencing
**Version:** 1.0
**Last updated:** 2026-05-09
**Author:** Glen Otero (gotero@linuxprophet.com), assembled with Claude
**Audience:** Glen + future contributors first; written so a partner lab, grant reviewer, or RC team could follow along without prior context
**Companion document:** `jackpot_strategic_vision_may_2026.md` (architectural reframings, Immune Platform vision, CDC DMI/STLT/CARE alignment, peer-platform differentiators)
**Pointer:** For granular session-by-session detail, see `docs/jackpot_session_summary_and_backlog.md` v3.3. This document does not replace that one.

---

## Table of contents

1. [Where we started](#1-where-we-started)
2. [What we've accomplished](#2-what-weve-accomplished)
3. [Current state — the snapshot](#3-current-state--the-snapshot)
4. [Known blockers and open hygiene items](#4-known-blockers-and-open-hygiene-items)
5. [What's next — sequencing](#5-whats-next--sequencing)
6. [The wider backlog](#6-the-wider-backlog)
7. [How to read the roadmap](#7-how-to-read-the-roadmap)

---

## 1. Where we started

JACKPOT began back in March/April 2026 — building out routers one by one (Sessions A through Q), bolting on parsers for 11 different pipeline tools, getting a Streamlit frontend up, and standing up a GCP staging environment.

By the end of Month 1 (mid-April 2026) the platform had:

- 477 tests passing, 86.99% coverage
- 9 routers fully implemented (auth, organizations, labs, projects, users, domain_whitelist, sequencing_labs, tokens, dataharmonizer)
- Local Docker Compose stack running cleanly
- 9 researcher Streamlit pages rendering with mock auth
- A live `/health` endpoint on GCP staging

Two big things changed in late April 2026 that reshaped everything:

1. **The pivot to operator-agnostic.** April 26–28 — JACKPOT became a standalone, AGPL-3.0 platform under `Midnight-Oil-Innovation/jackpot`. Production code now knows nothing about any specific operator; only `jackpot init` learns operator names at install time.

2. **The strategic survey work.** Three back-to-back synthesis sessions in late April / early May 2026 produced foundational reference docs:
   - `jackpot_pathoplexus_loculus_overview.md` — comparative analysis vs. 8 peer platforms
   - `jackpot_cdc_dmi_stlt_overview.md` — alignment with CDC's Data Modernization Initiative and STLT public health (with Tribal sovereignty as a category-of-one differentiator)
   - `JACKPOT_Architecture_Synthesis___May_2026.md` — the on-prem-first reframing, eight scenarios, three Python packages, Docker + Apptainer as peers

These are the bedrock of where we are now.

---

## 2. What we've accomplished

Organized by area rather than session-by-session. For session-by-session detail, see `docs/jackpot_session_summary_and_backlog.md`.

### 2.1 Backend / API

**21 routers shipped or scaffolded:**

| Router | Status | Notes |
|---|---|---|
| `auth` | Complete | Google OAuth + JWT; **refresh-token rotation shipped in P1 / PR #22** |
| `organizations`, `labs`, `lab_membership` | Complete | Multi-tenant foundations |
| `projects`, `users`, `domain_whitelist` | Complete | |
| `sequencing_labs`, `tokens` | Complete | API tokens with bcrypt hashing |
| `dataharmonizer` | Complete | 94% coverage |
| `ingest` (upload, csv, globus) | Complete | Full pipeline: validate → epiweek → scrub_status → surveillance_relevant → quality_status → stage → write |
| `samples` | Complete | List with full filter surface, get, update, archive, files, presigned download |
| `pipelines` | Complete | 10 endpoints incl. launch, weblog events, monitor, results, resume, BYOP, promotion |
| `sample_access` | Complete | Request/approve/deny + grant expiry job |
| `templates` | Complete | |
| `submissions` (I-track) | Complete | Seqsender-compatible packages for NCBI / GISAID EpiCoV/EpiFlu/EpiPox / ENA / DDBJ |
| `imports`, `import_mappings` (I-track) | Complete | |
| `credentials` (I-track) | Complete | Per-provider credential management |
| `federation` | Scaffolded (FED-A) | Track 1 + Track 2-seam; router wire-up pending FED-B |
| `datasets`, `archive_requests`, `saved_searches`, `notifications` | Stretch goals (Phase 25) | Tables exist, routers stub or placeholder |

**Backend modules in production:**

`validator`, `file_detector`, `harmonizer`, `epiweek`, `audit`, `permissions`, `dlp_scanner`, `pipeline_results_loader`, `pipeline_config`, `template_generator`, `notifications`, `responses`, `pagination`, `storage`, `config`, `database`, `middleware`, `logging`, `version`.

### 2.2 Schema, migrations, and the BYOP / eukaryotic / sovereignty design queue

- Schema is LinkML-driven, generated to Pydantic v2 + JSON Schema + DDL via `scripts/regen_schema.py` (in-repo since 2026-05-08, with trailing-whitespace normalization for both Python and JSON outputs)
- Pre-commit hook `schema-regen-check` verifies generated artifacts are in sync with the YAML
- Alembic migrations chain cleanly from baseline `5adf11b77c19`
- **`ExecutionProfile` + `PipelineDefaultProfile` schema landed** (PR #21) — `ExecutorTypeEnum` (7 values), `ContainerEngineEnum` (4 values), partial unique index for "at most one default", FK cascade, CHECK constraints, `default-local` seed
- **Refresh-token table landed** (PR #22) — JTI tracking, replay detection, daily cleanup
- **Schema design lockdown (Phase 24.5) is queued before P0b** — sovereignty deletion (`samples.deletion_status` enum, tombstone-and-vacuum lifecycle), BYOP (`byop_pipelines` table + 4 enums), eukaryotic (~25 OrganismNameEnum values, 5 new samples columns, 8 new pipeline-result tables) all need to land in the same P0b migration cycle to avoid double migrations

### 2.3 Pipelines and parsers

**11 pipeline parsers shipping today:** Cecret, viralrecon, walkercreek (viral); bactopia, Grandeur, mycosnp-nf, tb-profiler (bacterial); nf-core/mag, nf-core/taxprofiler (metagenomic); pathogensurveillance v1.1.0 (pinned), shared AMR via hAMRonization.

**Pipeline infrastructure:**

- `nf-jackpot` Nextflow plugin and `register_client` for result registration
- `POST /api/v1/pipelines/{run_id}/results/{result_type}` registration endpoint
- Two-tier storage in `pipeline_results`: immutable append-only JSONB rows + canonical `samples` field updates for 18 schema-mapped columns
- Weblog receiver follows the never-raises pattern (Nextflow doesn't retry on HTTP 500)
- BYOP registration skeleton (full BYOP infrastructure scheduled in Phase 24.7 / P0f's successor)

### 2.4 PII gates — the structural differentiator

JACKPOT enforces two PII gates at ingest. No peer platform does both.

**Gate 1: NCBI SRA Human Scrubber (HRRT) for genomic PII** — `ingest_scrubber.nf` with a 6-state lifecycle (PENDING / IN_PROGRESS / COMPLETE / FAILED / SKIPPED / PENDING_APPROVAL), 48h skip governance, `SCRUBBER_MAX_CONCURRENT=10`. Aligns with WHO IPSN attribute 6.

**Gate 2: GCP Cloud DLP for metadata PII** — `dlp_scanner.py` with dynamic free-text field discovery, `FIELD_EXCEPTIONS` for expected PII, `LIKELY` threshold, `DLP_ENABLED=false` local bypass for laptop/dev. The DLP scanner now treats the local bypass as Scenario A/B's default rather than an escape hatch.

### 2.5 Frontend (Streamlit)

- All 9 researcher pages exist: `dashboard`, `search`, `upload`, `data_entry`, `my_samples`, `datasets`, `access_requests`, `notifications`, `pipelines`
- Frontend lives in `frontend/` inside the monorepo (the `jackpot-frontend` repo is vestigial and slated for retirement)
- Lands at `http://localhost:8501` with sidebar showing all 9 pages
- Mock auth works end-to-end via `current_user()`
- Admin pages (`lab_director`, `platform_admin`, `archive_requests`, `billing`) are intentionally deferred to Month 3 stretch goals

### 2.6 Infrastructure

**Local development:**

- Docker Compose stack with `api`, `postgres`, `minio`, `minio_init`, `ui` services
- `COMPOSE_PROFILES=laptop` for laptop scenario
- `uv` workspace at monorepo root managing backend, CLI, and pipelines
- `gac` zsh alias for lint → format → commit (with pre-fix step added 2026-05-08)

**GCP staging (deployed Session 5):**

- Terraform/Helm IaC; GKE with Workload Identity Federation
- Cloud SQL Postgres, 7 GCS buckets, Artifact Registry
- 3 GSAs with WIF bindings
- API live, `/health` returns `{"status":"ok","database":"connected"}`
- Alembic head verified at `c536de6329e0`
- Secret Manager: `SECRET_KEY`, `DATABASE_URL`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `NCBI_API_KEY`
- GitHub Actions deploy pipeline (WIF → build → push → helm upgrade with migrations as pre-upgrade hook)

### 2.7 Operator-agnostic genericization (Cleanup A–J, P0d)

| Phase | Scope | Commit |
|---|---|---|
| A | Docs cleanup | `68e3565` |
| B | Schema rename `adhs_medsis_id` → `external_case_id` | `667aaaf` |
| C | HTML course content | `b804e76` |
| D | Test fixture data | `d51e39d` |
| E | Straggler test fixtures | `c29fa42` |
| F | Seed scripts genericized | `771cbc8` |
| G | Submodule schema-update scripts | (no-op, already clean) |
| H | Misc files + 2 deletions | `83f9f28` |
| I | Pipeline test fixtures (AZ-* → EX-*) | `a9a2a94` |
| J | Streamlit frontend | (no-op, all matches were 'banner' false positives) |

**P0d Monorepo migration (complete 2026-05-01):** Five repos (`jackpot-backend`, `jackpot-schema`, `jackpot-nf`, `jackpot-cli`, `jackpot-iac`) consolidated into `Midnight-Oil-Innovation/jackpot` via `git filter-repo` preserving history. New tree: `backend/`, `frontend/`, `cli/`, `schema/`, `course/`, `pipelines/`, `deploy/`, `tests/`, `docs/`. Single `uv` workspace at root.

### 2.8 `jackpot init` CLI (P0e — complete 2026-05-02)

- Interactive scenario detector at `schema/jackpot_scenarios/detector.py` with 4–5 operator-type questions
- Scenario registry shared across backend, CLI, and CI
- Per-scenario bundle generation (docker-compose for Scenarios A/D/E/F; systemd unit templates for Apptainer-based Scenario C)
- `~/.jackpot/config.yaml` as the operator's source of truth
- Design decisions locked in `docs/architecture/jackpot-init-cli.md`

### 2.9 File references redesign (P0f — complete 2026-05-04)

The mental-model shift from "JACKPOT stores your data" to "JACKPOT is a metadata database that knows how to find data wherever it lives."

**What landed across F-1 through F-12:**

- New `file_references` table with content-hash logical key
- `FileStorageState` enum: `EXTERNAL` / `MANAGED` / `MIRRORED` / `STAGED` / `BROKEN`
- Cheap fingerprint at ingest (size + first-64KB hash + last-64KB hash); full SHA-256 lazily as a background job
- Periodic verification of `EXTERNAL` files; auto-mark as `BROKEN` if missing
- Pre-pipeline-launch verification — fail fast, not mid-run
- `jackpot files promote` CLI command for explicit ownership transfer
- UI surfacing of storage state on every file
- Cross-cutting integration tests covering register-EXTERNAL → verify-broken → launch-refused → re-locate → launch-succeeds, plus cross-scheme dedup, F-9 promote failure recovery, and permission-boundary scoping

### 2.10 Adoption-driving features (the I-track — complete 2026-05-04)

The "I-track" was four items identified as JACKPOT's adoption drivers — the things a state public health lab or university RC team would actually need on day one.

- **I-1 (credentials):** Per-provider credential management with cache (TTL/LRU strategy still open as a Batch D follow-up)
- **I-2 (submission packages):** Seqsender-compatible packages for NCBI / GISAID EpiCoV/EpiFlu/EpiPox / ENA / DDBJ; first-class submissions table; 10+ state machine; embargo support via daily release job; link-first file handling. JACKPOT does not hold repository credentials in v1 — users run Seqsender themselves on a stable host.
- **I-3 (imports):** External-database import (NCBI / GISAID / ENA / DDBJ) — sample metadata pulled into JACKPOT's schema with provenance tracking
- **C-1 (per-provider credential setup docs):** `docs/credentials/ncbi.md`, `docs/credentials/gisaid.md`, etc.

### 2.11 Code quality — the /ultrareview cycle

A six-reviewer `/ultrareview` pass on `development` (against `main`) on 2026-05-06 surfaced 26 findings ranked by severity: 5 blockers, 12 should-fix, 9 nice-to-have. Three review-fix work items shipped:

- **R-1 (PR #31):** Six security/correctness blockers fixed — template path traversal via `executor_type`, SSRF + LFI via `/register` URI scheme, three sync-I/O calls blocking the async event loop, hardcoded operator-specific GCP project ID (Critical Rule 55 violation), Groovy injection via Jinja2 with autoescape disabled, and a refresh-token rotation race. **81 new tests; coverage 87.94%.**
- **R-2 (PR #32):** Deduplicated three GISAID submission package generators behind a single `_generate_gisaid_package` helper; added test coverage for the five previously-untested generators (GISAID variants, ENA, DDBJ, dispatcher). **35 new tests; per-file coverage on `submission_packages.py` reached 100%.**
- **R-3 (PR #33):** Doc and tracking hygiene — 4 new entries in `docs/learnings.md`, new Submissions and Credentials sections in `spec.md`, new `docs/api/` files (537 + 336 + 266 lines), `todo.md` reconciled, **Critical Rule 62** added (Critical Rule 61 was already shipped via PR #27 for worktree branch verification), 15 new docstrings on public functions.

The cycle revealed a meta-lesson: parallel Claude Code sessions sharing a single repo are unsafe in practice. Four cross-session contamination incidents collectively absorbed more time than sequential execution would have. **Default is now single Claude Code session per repo;** worktrees are an explicit escape hatch with deliberate setup.

### 2.12 Federation / Privacy / Crypto scaffolds (FED-A complete 2026-05-08)

The strategic decision this session: build federation, privacy, and encryption Track 1 implementations now using current JACKPOT primitives (JWT, presigned URLs, existing `can_access_sample()` permission model, existing scrubber, existing DLP) — and in parallel scaffold the AIS-augmented Track 2 hook seams so future research-collaboration work can plug in via dependency injection rather than forking each module.

**Architectural pattern:** two parallel namespaces under `backend/backend/`:

- `backend/backend/federation/`, `backend/backend/privacy/`, `backend/backend/crypto/` — Track 1, ships now
- `backend/backend/immune/` — Track 2, AIS-augmented overlays scheduled per `jackpot_immune_collaboration_scaffolding.md`. Concrete implementations of the Protocol seams in each Track 1 package's `_ais_hooks.py` module

The seam between tracks is dependency injection. Every Track 1 class accepts a `hooks=` argument defaulting to a `Null<X>Hooks` no-op. Track 2 swaps in concrete implementations via the same constructor argument. **No code changes required to Track 1 modules when Track 2 lands.** Direction of import is one-way: Track 1 packages never import from `backend/backend/immune/`.

**FED-A landed 2026-05-08** with seven files in `backend/backend/federation/`:

- `__init__.py` — public API exports
- `README.md` — Track 1/2 plan, hook→AIS-doc mapping
- `models.py` — Pydantic v2 models: `FederatedInstance`, `FederationRole` enum (hub/spoke/peer), `FederationQuery`, `FederationQueryResult`, `FederationPushPayload`, `FederationAccessRequest`
- `client.py` — `FederationClient` for Level 1 query federation; concrete async fanout via `httpx`, per-partner attestation hook, anomaly-detection hook, secure-aggregate wrap on results
- `push.py` — `FederationPushJob` for Level 2 hub push; qualification logic concrete (3 gates from `jackpot_architecture.md` §22: surveillance_relevant, sharing_level ≥ minimum, quality_status ≥ ANALYZABLE); IO stubbed
- `access.py` — `FederationAccessGateway` for Level 3 bidirectional access
- `_ais_hooks.py` — `AISFederationHooks` Protocol with five hooks plus `NullAISFederationHooks` no-op default

**Five `AISFederationHooks` Protocol entry points:**

| Hook | AIS doc reference | Track 2 impl module |
|---|---|---|
| `secure_aggregate(results, partner_set)` | §1.6 inter-instance signaling | `backend/backend/immune/net/federation_hooks.py` |
| `attest_partner(instance)` | §1.7 attribution & deception | `backend/backend/immune/sec/` (attestation primitives) |
| `detect_anomalous_traffic(query, partner)` | §1.3 innate immunity | `backend/backend/immune/algorithms/featurizers/` |
| `threshold_approve(action, partner_set)` | §1.8 tolerance / regulation | `backend/backend/immune/sec/` (threshold-crypto primitives) |
| `validate_push_payload(payload, target)` | §1.8 tolerance ("don't attack self") | `backend/backend/immune/sec/refusal.py` |

Operator-agnostic verified: zero proper names in package; all hook docstrings describe Track 2 impl by location + expertise area, never by collaborator name.

### 2.13 Numbers as of 2026-05-09

| Metric | Value |
|---|---|
| Tests passing | **1591 passing, 2 skipped** |
| Coverage | **87.85%** (87.94% post R-1) |
| CI threshold | 80% |
| Backend routers shipped | 21 |
| Pipeline parsers shipped | 11 |
| Streamlit researcher pages | 9 of 9 |
| PRs merged into `development` (Sessions 21+) | 9 substantive (P0g G-1+G-2, P1, R-1, R-2, R-3, P0g G-3+G-4, plus chore/docs) |
| Open feature track items | P0g G-5, FED-B/C/D/E wire-up, PRV-A, CRY-A, Phase 24.5 design, Phase 24.7 / P0f BYOP |

---

## 3. Current state — the snapshot

**Branch:** `development` is the integration branch; feature PRs target it; release PRs go `development` → `main`; `staging` branch push triggers GCP staging deploy.

**Active sprint:** Maintainer's call. With the I-track + P0g G-1 through G-4 + P1 + R-1/R-2/R-3 closeout done, the natural candidates for next session are:

1. **Phase P0g G-5** — profiles CRUD endpoints. Operators can use the renderer/resolver from PR #28 but can't manage profiles via API yet; closing this gap unblocks the legacy GCP-Batch path deletion.
2. **Phase 24.5 design lockdown (solo, option β)** — finalize sovereignty-deletion design without external review since collaborator review was deferred 2026-05-05; once locked, P0b unblocks.
3. **Performance and cleanup follow-ups from /ultrareview Batch D** — see `todo.md` Batch D section.
4. **Phase 24.7 / P0f BYOP infrastructure** for B-BYOP-1 through B-BYOP-10.
5. **Federation wire-up (FED-B/C/D/E)** — schema migration, tests, router, and `main.py` wiring on top of the FED-A scaffold.
6. **Privacy scaffold (PRV-A)** at `backend/backend/privacy/` — same pattern as FED-A with FL/DP/HE/MPC AIS hook seams.
7. **Crypto scaffold (CRY-A)** at `backend/backend/crypto/` — same pattern with HE/threshold/attestation AIS hook seams.

**Architectural sequence (locked):**

```text
Phase 24.5  (sovereignty + BYOP design lockdown)
    ↓
Phase 24.7 / P0f  (BYOP infrastructure)
    ↓
P0b  (Schema v5.0 — sovereignty + BYOP + eukaryotic in one migration)
    ↓
P0c  (multi-tenancy middleware + sovereignty deletion implementation)
    ↓
P1 broader auth-architecture review
    ↓
P2+
```

The Federation / Privacy / Crypto scaffold work is **ahead-of-schedule** relative to B-FED-1 / B-PRV-1 / B-CRY-1 in the post-P0h future-phases pipeline. The scaffold lands the package surfaces now so the official phases reduce to wire-up + immune-overlay work when they schedule.

---

## 4. Known blockers and open hygiene items

### Hard blockers

- **GCP staging Helm/ConfigMap CORS_ORIGINS issue.** The `jackpot-api-config` ConfigMap still contains the old `CORS_ORIGINS` string value rather than the JSON array required by pydantic-settings. Fix is one command pair — `kubectl -n jackpot delete configmap jackpot-api-config` followed by `gh workflow run deploy-staging.yml` to force the pre-install hook to recreate the ConfigMap with the corrected JSON array from `values-staging.yaml`.

- **IAC-1 through IAC-5 in `todo.md`.** These are blocking clean GCP deployments and will block scenario D/E work.

- **Q-5: End-to-end pipeline test on staging.** Cecret (or viralrecon) full stack. Blocked on Phase 23 (`test_batch.nf` minimal harness) + UI-B/C for driving the flow.

### P0 code bugs flagged but not yet fixed

- `log_audit()` and `create_notification()` accept `db_conn` but never forward it to `execute_write()` — audit/notification writes always auto-commit in separate transactions regardless of caller context.
- `_handle_workflow_complete()` calls `execute_query(..., conn=conn)` but `execute_query()` does not accept `conn=` — will throw `TypeError` on Nextflow `workflow.complete` events.
- Validator `BASE_REQUIRED` tier split is a domain design decision Glen needs to define personally (defines what constitutes a valid Tier-1 PRELIMINARY sample — core business logic).

### Post-monorepo housekeeping (surfaced during F-2)

- Add `slowapi` to backend runtime deps (currently imported but not declared)
- Add dev deps to backend (`pytest-cov`, `pytest-asyncio`, `testcontainers[postgres]`, `hypothesis`, `pytest-httpx` were manually installed during F-2)
- Decide: lean prod image AND dev image, or always include dev deps?
- Mount `/var/run/docker.sock` into api service so testcontainers-based tests can run inside the container
- Document `COMPOSE_PROFILES=laptop` requirement in README and macOS dev guide
- Make `backend/alembic.ini` use `%(here)s/db/migrations` so invocations work from any cwd
- Clean up the broken `.venv` symlink at `/app/.venv` in the api container
- Resolve schema mount path inconsistency (`ui` mounts at `/app/schema`, `api` mounts at `/schema`)
- Audit `Dockerfile.api` and `Dockerfile.ui` for Apptainer compatibility (UID assumptions, root-write paths, Docker-socket assumptions)

### Performance and cleanup (Batch D from /ultrareview)

These are from the `/ultrareview` pass — real but not blocker-level. Ship as smaller PRs incrementally.

**Architectural follow-ups (deserve their own work-item specs):**

- **#8** `pipeline_default_profile.pipeline_id` UUID vs `pipeline_catalog.id` SERIAL mismatch (`profile_resolver.py:35-38`). Step 3 of the Rule-59 5-step resolution chain is dead code until a follow-up migration lands.
- **#12** `register_accessions` N+1 (`submissions.py:739-810`). 3N queries per accession entry.
- **#13** Cache TTL/LRU strategy (`credentials/cache.py:26` + `harmonizer.py:34`). Both have unbounded dicts.

**Performance / N+1 (small PRs each):**

- `jobs.py:203-208` — per-row director lookup in `_send_approve_warnings`
- `submissions.py:432-445` — per-sample INSERT … ON CONFLICT loop
- `pipeline_results_loader.py:314-322` — per-sample SELECT in manifest loop
- `jobs.py:132-174, 284-311, 327-346` — unbounded per-row UPDATE loops
- `jobs.py:449` — `_select_rows_to_hash` has no LIMIT
- `jobs.py:1048-1057` — full-file BytesIO accumulation; multi-GB OOM risk

**Simplicity (small PRs each):**

- `_ensure_lab_access` triplicated across submissions/import_mappings/imports routers — move to shared auth utility
- Collapse near-identical state-machine transitions in `submissions.py` behind a `_transition_status(...)` helper (~150 lines saved)
- Delete `pipeline_config/batch_submitter.py` (no-op stub never shipped)
- Drop `submission_executors/__init__.py` re-export layer (no callers)
- Drop `_Credentials` proxy and re-export shims
- `gcp_batch.config.j2:13` hardcodes `us-central1` as fallback region — Critical Rule 55 borderline; parameterize or remove

**Security (small PRs each):**

- `f"…{vis_clause}"` SQL splicing in `routers/files.py::_load_file_row_for_user` — latent injection risk; refactor to parameterized
- `facade.py:62-68` logs `str(exc)` from credential errors — GCP exceptions can embed secret resource names; trim before logging

---

## 5. What's next — sequencing

This sequencing follows the architectural-synthesis plan from May 2026 plus the Phase 24.5 / 24.7 insertions. Items sit on top of the locked `Phase 24.5 → P0f → P0b → P0c → P1` backbone.

### 5.1 Immediate (next 2–4 weeks): Resolve current blockers and lay groundwork

1. **Resolve the GCP staging Helm/ConfigMap CORS_ORIGINS blocker.** One-shot fix.
2. **Resolve IAC-1 through IAC-5** in `todo.md`. Blocks clean GCP deployments and Scenario D/E work.
3. **Pull PHIN VADS vocabularies as static reference data into `schema/`.** PHIN VADS sunsets November 30, 2026 — this is one of those "do it now while it's still possible" items.
4. **Audit backend/frontend Dockerfiles for Apptainer compatibility.** UID assumptions, root-write paths, Docker-socket assumptions. Fix what's needed; document what stays Docker-only.
5. **The three P0 code bugs above** — audit/notification transaction-cohesion, `_handle_workflow_complete()` `conn=` parameter, validator `BASE_REQUIRED` tier split.

### 5.2 Phase 24.5 — Architectural Design Lockdown (1 session for design + 1–2 for schema migration work + half a session of P0b integration discussion = 3–4 sessions total)

**Why this phase exists:** P0b will land Schema v5.0 (instances/tenants/federated_peers). If P0b ships without thinking through these architectural decisions, the schema will need to be retrofitted later. Two distinct architectural gates must be locked in before P0b touches the schema:

1. **Sovereignty-compliant deletion** (CARE Principle "Authority to Control" requires withdrawn-consent data to actually leave the system, not just get soft-deleted)
2. **BYOP + eukaryotic schema additions** (the BYOP `byop_pipelines` table and `pipeline_results` FK additions, plus the eukaryotic OrganismNameEnum/samples-column/8-pipeline-result-table additions, all need to land *with* P0b)

**Deliverable:** `docs/architecture/sovereignty-compliant-deletion.md` covering:

- `samples.deletion_status` enum: `ACTIVE | DELETION_REQUESTED | TOMBSTONED | VACUUMED`
- State machine — who can request, who can approve, what triggers vacuum
- Tombstone vs vacuum distinction — tombstone seals derivative rows, vacuum physically removes content
- What gets vacuumed: file URIs in samples, GCS/MinIO objects, `pipeline_results.result_data` JSONB, cached intermediate artifacts, dataset memberships
- What survives vacuum: audit log records of *what happened* but NOT the deleted content itself
- Vacuum cadence: configurable per operator policy; Scenario T defaults to 24 hours; other scenarios may default to 30 days
- Derivative-analysis policy: cluster recompute (Scenario T default) vs cluster-with-asterisk (other scenarios) vs mark-stale-and-recompute-on-schedule
- Already-published handling: pre-publish CARE confirmation checklist; "previously published" tag persists past vacuum
- Federation propagation requirements (deferred to B-CARE-4 implementation): tombstone events pushed to peers, signed receipts, SLA, non-compliance flagging
- Auth model: who can request deletion; who must approve
- Edge cases: deletion during pipeline run, deletion during pending submission to NCBI, deletion of sample that's part of an active outbreak investigation

**Schema constraints from this design that P0b must honor:**

- `samples.deletion_status` column with the 4-value enum
- `samples.deletion_requested_at`, `deletion_requested_by_user_id`, `deletion_reason` columns
- `samples.tombstoned_at`, `vacuumed_at` timestamp columns
- `audit_log.event_type` enum extension: `sample_deletion_requested`, `sample_tombstoned`, `sample_vacuumed`
- `pipeline_results` rows need a `tombstoned` boolean
- Foreign key from `pipeline_results.sample_id` should NOT cascade-delete on sample deletion

### 5.3 Phase 24.7 / P0f — BYOP Infrastructure (~3–4 weeks, parallelizable across 2–3 contributors)

Source: `jackpot_byop_and_eukaryotic_design.md` Part I (Sections 1–10).

| Item | Scope | Effort |
|---|---|---|
| **B-BYOP-1** | `jackpot-pipeline.yaml` manifest schema (9 sections: api_version, kind, metadata, engine, applicability, resources, reference_data, containers, inputs, outputs, permissions, cost) | 1–2 sessions |
| **B-BYOP-2** | `byop_validator.py` Stage 1 static validation (per-engine syntax, container resolution, reference data resolution, license compatibility, permissions sanity) | 3–4 sessions |
| **B-BYOP-3** | `byop_sandbox.py` Stage 2 sandbox dry-run with isolation (per-engine dry-run mechanic, K8s/Docker isolation, egress allowlist, 5-min timeout, 2 CPU / 4 GB RAM) | 2 sessions |
| **B-BYOP-4** | `routers/byop.py` registration + lifecycle endpoints; existing `/api/v1/pipelines/launch` accepts `byop_pipeline_id` alongside `pipeline_zoo_id` | 2–3 sessions |
| **B-BYOP-5** | Engine launchers — Nextflow (harden existing), Snakemake (new), WDL (Cromwell + miniwdl), manifest engine | 1.5–2 weeks |
| **B-BYOP-6** | Quarterly revalidation background job | 1 session |
| **B-BYOP-7** | Streamlit BYOP registration wizard (6-step) | 2–3 sessions |
| **B-BYOP-8** | Streamlit BYOP catalog tab on Pipelines page | 1–2 sessions |
| **B-BYOP-10** | BYOP telemetry — success rate, walltime, peak memory, cost; auto-deactivate below threshold | 1–2 sessions |

### 5.4 Phase P0b — Schema v5.0 (post-Phase-24.5)

The big migration. Lands sovereignty additions, BYOP, eukaryotic, and the v5.0 plan in one pass to avoid double-migrate operator churn. The design work is all in Phase 24.5; P0b is the implementation.

### 5.5 Phase P0g — Execution Profiles (G-5+ remaining)

- **G-5:** Profiles CRUD endpoints (operators can use renderer/resolver from PR #28 but can't manage via API yet)
- **G-6 through G-11:** Per-pipeline default profile UI, profile-aware launch, cost surfacing for cloud-burst profiles, smoke tests

### 5.6 Phase P0c — Multi-tenancy Middleware + Sovereignty Deletion (2–3 sessions for B-CARE-3 + 1–2 for B-CARE-5)

- Multi-tenancy middleware enforcing per-lab data isolation
- **B-CARE-3 implementation:** True delete-on-request via tombstone-and-vacuum lifecycle per Phase 24.5 design
- **B-CARE-5:** Pre-publish review checklist with CARE-Principle confirmation. Scenario T defaults to no-auto-publish

### 5.7 Phase P0h — Slurm Executor Support for Scenario B (and C)

Pairs with P0g. Specific to making scenario B + Slurm work end-to-end:

- Slurm executor profile templates
- Singularity/Apptainer image manifest support in pipeline zoo
- Weblog reachability documentation for cluster→API
- End-to-end smoke test on a real Slurm cluster (can be a small institutional one)

### 5.8 Phase P0i — Open-Source Adoptions: Pipelines and Tools (Month 3–4)

Sequence the open-source adoptions concretely:

| Item | Source | License | Justification |
|---|---|---|---|
| **seqsender** | CDC | Apache-2.0 | Replace placeholder NCBI/GISAID submission with real working code |
| **MIRA-NF pipeline** | CDC | Apache-2.0 | Flu/SARS/RSV via IRMA — covers a major use case JACKPOT lacks today |
| **PHoeNIx pipeline** | CDC | Apache-2.0 | AMR/HAI bacteria — high-value for state PHL deployments |
| **GA4GH `/service-info` endpoint** | GA4GH | Apache-2.0 spec | Cheapest federation win — one afternoon's work |
| **DRS-style URI conventions** | GA4GH | Apache-2.0 spec | Already 80% there; formalize as standard |

### 5.9 Phase P0j — Apptainer-First Deployment for Scenario C (Month 4)

Building on P0e. The systemd-unit-file route, the host-installed-Postgres/MinIO option, the air-gapped image pre-staging, and the cluster-side configuration.

### 5.10 Phase P0k — University RC-Hosted Scenario C End-to-End (Month 4–5)

Bringing Scenario C to production-readiness:

- Multi-tenancy middleware live
- LDAP/SAML auth path
- Slurm cluster integration tested with a real university partner
- Documentation for RC team operators
- A reference deployment as proof-of-concept

### 5.11 Phase P0l — Scenario D/E Hardening and GCP Production (Month 5–6)

Cloud production deployments:

- Multi-tenant agency deployments
- Cloud DLP integration as Scenario D/E feature, not core
- Cloud-burst executor profile for Scenario B
- WIF and IaC cleanup completed

### 5.12 Phase P0m — Aquascope, MycoSNP, Tostadas, MicrobeTrace, PHES-ODM (Month 4–5, parallel to P0k/P0l)

| Item | Source | License | Notes |
|---|---|---|---|
| **MycoSNP-NF pipeline** | CDC | Apache-2.0 | Fungal (C. auris) — emerging surveillance need |
| **Aquascope pipeline** | CDC | Apache-2.0 | Wastewater SARS-CoV-2 with NWSS alignment, already schema-compatible |
| **Tostadas pipeline** | CDC | Apache-2.0 | NCBI/GISAID submission via Liftoff/VADR/Bakta |
| **MicrobeTrace** | CDC | Apache-2.0 | Browser-based outbreak visualization, embed as iframe |
| **PHES-ODM data model** | Big-Life-Lab | MIT | Wastewater alignment for EU/Canadian deployments |

### 5.13 Federation wire-up (FED-B / FED-C / FED-D / FED-E) and PRV-A / CRY-A scaffolds

In parallel to the P0 sequence above. Each is a small focused PR on top of the FED-A pattern.

- **FED-D:** `federated_instances` table; new columns on `organizations`. Branch: `b1-federation-schema-migration`.
- **FED-C:** Tests at `tests/federation/` covering models, L1 client, L2 push, L3 access, AIS hooks. ≥95% coverage target. Branch: `b2-federation-tests`.
- **FED-B:** `routers/federation.py` exposing list/register partners (Platform Admin), L1 search, L2 push receiver. Branch: `b3-federation-router`.
- **FED-E:** `main.py` wiring + integration tests against ephemeral peers. Branch: `b4-federation-wireup`.
- **PRV-A:** Privacy scaffold at `backend/backend/privacy/` with FL/DP/HE/MPC AIS hook seams. ~1000 lines, 7 files.
- **CRY-A:** Crypto scaffold at `backend/backend/crypto/` — `keys.py` (PKCS#11 / Secret Manager / file-system), `signing.py` (Sigstore/cosign), `crypt4gh.py` (per-file encryption). ~1000 lines, 7 files.

---

## 6. The wider backlog

### Phase 25 — Month 3 Stretch Goals (tracked, not scheduled)

- Streamlit admin pages: `lab_director.py`, `platform_admin.py`, `archive_requests.py`, `billing.py`
- JupyterHub workspace with all three profiles (Analyst, Bioinformatician, Developer) — primarily a Scenario C/D/E feature
- BYOP full wire-up — *largely superseded by Phase 24.7 / P0f*
- GCP production deployment
- `ncbi_submissions` router (TOSTADAS integration) — *see B-LOC-1 Phase 26*
- `datasets`, `archive_requests`, `saved_searches`, `notifications` routers (full)
- Re-enable detect-secrets in pre-commit
- Playwright end-to-end UI tests
- US-states controlled vocabulary for `collection_location_state`
- Retire `jackpot-frontend` repo

### Phase 26 — Pathoplexus/Loculus comparative analysis backlog

34 B-XXX adoption items grouped A–J by source platform from `jackpot_pathoplexus_loculus_overview.md`. Tracked, not scheduled.

### Phase 27 — CDC DMI / North Star / STLT alignment backlog

14 items across 3 groups. Most quick-wins have already moved to Phase 21.5 (interstitial during-P0d) and Phase 24.5 (sovereignty design). What remains in Phase 27 proper:

- **B-CARE-4** — Federation-aware deletion propagation. Depends on B-CARE-3 + Scenario E federation work. (1 week, Year 2)
- **B-DMI-2** — `backend/routers/fhir.py` for FHIR `Specimen` + `MolecularSequence` ingest, `Observation` + `Provenance` emit. Gated on operator demand — don't build speculatively. (1–2 weeks, Year 2)
- **B-STLT-4** — Scenario detector (already locked in `docs/architecture/jackpot-init-cli.md` and queued for P0e)

**Operational additions from 2026-05-09 open-source survey:**

- **B-DH-1** — CIDGOH/PHA4GE Mpox (MPXV) DataHarmonizer template (1 session, post-P0d)
- **B-CDST-1** — Coding-Sequence-Decentralized-Strain-Typing evaluation spike for *Salmonella enterica*, *Listeria monocytogenes*, *Escherichia coli* (2-week spike, post-Phase 28)

### Phase 28 — Default Eukaryotic Pathogen Pipelines (tier-prioritized)

The schema for these lands in P0b (via Phase 24.5 design). The pipelines ship in tiers:

- **Tier 1 (ship first):** *Plasmodium*, *Cryptosporidium* / *Giardia*
- **Tier 2:** *Leishmania*, *Trypanosoma*, *Schistosoma*
- **Tier 3:** STH, filarial, *Toxoplasma* / *Entamoeba*

### Beyond P0 — the strategic horizon

The Immune Platform vision (Phase 26+ of the Immune Platform Plan, separately numbered from `todo.md` Phase 26 above) lays out Phases 26–31 of post-P5 work: bio-AIS MVP, multi-modal danger fusion, memory + clonal selection, federation as immune network, cyber-AIS for platform self-defense, and game/Academy full integration. These run in series with each phase a coherent unit; items within a phase parallelize. Total ~31 weeks of work.

See the companion **strategic vision document** for the full picture of where this lands relative to peer platforms, the dual-AIS thesis, and the workforce-as-platform-infrastructure thesis.

---

## 7. How to read the roadmap

A few framing notes for anyone landing on this document cold:

**The roadmap is layered.** P0a–P0e are complete. P0f–P0m run May–October 2026. Phase 24.5 and 24.7 are insertions before P0b that lock in design decisions and BYOP infrastructure respectively. The Federation/Privacy/Crypto scaffold work runs in parallel and is ahead of its formal phase numbering.

**"Sessions" are units of work, not days.** A session is roughly 2–6 hours of focused work with Claude Code; a complex item might take 2–3 sessions, a simple one half a session.

**Scenario letters (A–H) come from the architecture synthesis** and replace the older 6-target vocabulary. See the strategic vision document for the full table.

**Critical Rule numbers** (61, 62, 55, 59, 20, etc.) reference `docs/CLAUDE.md`. They're hard rules established after specific failure modes; rule numbers grow as new ones are codified.

**The two-track architecture** (Track 1 = ships now using current primitives; Track 2 = AIS-augmented overlays plugged in via dependency injection) is the structural answer to "how do we build the immune-platform vision without forking every module." All Federation/Privacy/Crypto Track 1 work has Track 2 hook seams already.

**Operator-agnostic is non-negotiable.** Every PR is checked against `scripts_jackpot/audit_proper_names.py`. Eponymous protocol names get genericized to their technical concept (e.g., "Bonawitz protocol" → "secure aggregation protocol"); standard cryptographic abbreviations like FROST, BLS, DKG stay.

**When in doubt, the source-of-truth ordering is:** `docs/CLAUDE.md` Critical Rules → `spec.md` → `todo.md` → `docs/jackpot_session_summary_and_backlog.md`. This document and the strategic vision companion sit above all of those for "where are we going" framing, and below them for "what's actually happening right now."
