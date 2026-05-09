# JACKPOT — To-Do List

**Last updated:** 2026-05-08 (federation Track 1 + Track 2-seam scaffold landed; regen_schema in-repo with whitespace normalization; gac pre-fix step)
**Baseline:** **1591 tests passing, 2 skipped** (verified 2026-05-06 via `uv run pytest --no-cov -q` against `r3-doc-and-tracking-hygiene` based at `2609a1f`). Coverage 87.85% per PR #28 closeout (re-measure with `uv run pytest --cov` if needed; CI threshold 80%). PR #28 (P0g G-3+G-4) reported 1527 passing post-merge; subsequent R-1 security fixes (PR #31) brought the count to its current state.
**Sessions 21+ deliverables:** PR #21 (P0g G-1+G-2: `ExecutionProfile` + `PipelineDefaultProfile` schema + migration with `default-local` seed; merged 2026-05-04 at `a682788`). PR #22 (P1: `/api/v1/auth/refresh` endpoint with single-use rotation, `refresh_tokens` table, replay detection with bulk-revoke, rotation-aware login/logout, daily cleanup job, six error codes; merged 2026-05-05 at `ba03143` — closes the I-track entirely). PR #23 (docs: bundle refresh to v4.0 covering Session 20 I-track close). PR #25 (chore: pin ruff at 0.11.6 across pre-commit, backend, cli, uv.lock — permanent fix for the recurring CI ruff-version mismatch that bit PRs #21 and #22 on first runs). PR #26 (docs: governance README + coi-disclosures stub on top of the 8 substantive governance docs already on origin from `f46f7ee`; merged 2026-05-05 at `2dbb839` along with an accidentally-bundled Sessions 21+ doc refresh that came along from local development state). PR #27 (docs: post-Session-21 housekeeping — `uv run pre-commit` prefix, **Critical Rule 61** worktree+branch verification, spec.md §4.1 fix #5 resolution; merged at `c7df002`). PR #28 (P0g G-3+G-4: profile templates + `nextflow.config` renderer + `pipeline_config/` package refactor + 35 new tests; merged at `544c98c` — 1527 tests, 87.85% coverage). PR #29 (docs: defer Phase 24.5 external collaborator review per option β / scope c — NPAIHB/Northwest TEC/B-CARE-6 references stripped from `todo.md` + session summary + `cdc_dmi_stlt` overview). **This session (2026-05-08):** Federation Track 1 + Track 2-seam scaffold landed at `backend/backend/federation/` (FED-A — `models.py`, `client.py`, `push.py`, `access.py`, `_ais_hooks.py` Protocol seam, README; operator-agnostic). `scripts/regen_schema.py` moved into the repo with trailing-whitespace normalization for both Python and JSON outputs (T-1). `.pre-commit-config.yaml` `schema-regen-check` hook added, fires only on schema YAML changes (T-2). `gac()` zsh function pre-fix step added (T-3, personal config in `~/.zshrc`). Federation router + tests + migration (FED-B/C/D/E) plus privacy and crypto scaffold counterparts (PRV-A, CRY-A) tracked in the new "Federation / Privacy / Crypto Scaffolds" section below. See Sessions 21+ entries in `jackpot_session_summary_and_backlog.md` and the recovery saga learnings in `learnings.md` ("Worktree contamination — Sessions 20-21" entry).
**Active sprint:** Next phase is the maintainer's call. With I-track + P0g G-1 through G-4 + P1 + R-1/R-2/R-3 closeout done, the natural candidates are: (a) **Phase P0g G-5** (profiles CRUD endpoints — operators can use the renderer/resolver from PR #28 but can't manage profiles via API yet; closing this gap unblocks the legacy GCP-Batch path deletion); (b) **Phase 24.5 design lockdown (solo, option β)** — finalize sovereignty-deletion design without external review since collaborator review was deferred 2026-05-05; once locked, P0b unblocks; (c) **Performance and cleanup follow-ups from /ultrareview Batch D** — see the dedicated section below; (d) **Phase 24.7 / P0f BYOP infrastructure** for B-BYOP-1 through B-BYOP-10; (e) **Federation wire-up (FED-B/C/D/E)** — schema migration, tests, router, and `main.py` wiring on top of the FED-A scaffold delivered 2026-05-08; (f) **Privacy scaffold (PRV-A)** at `backend/backend/privacy/` — same pattern as FED-A with FL/DP/HE/MPC AIS hook seams; (g) **Crypto scaffold (CRY-A)** at `backend/backend/crypto/` — same pattern with HE/threshold/attestation AIS hook seams. Architectural sequence remains: Phase 24.5 (sovereignty + BYOP design lockdown) → P0f (BYOP infrastructure) → P0b (Schema v5.0) → P0c (multi-tenancy middleware + sovereignty deletion) → P1 broader auth-architecture review (rest of P1 — session-management UI, refresh-token-family tracking, etc.) → P2+. The Federation/Privacy/Crypto scaffold work is ahead-of-schedule relative to B-FED-1 / B-PRV-1 / B-CRY-1 — see "Federation / Privacy / Crypto Scaffolds" section below.


**Priority shift (2026-04-28):** With CARE Principles, STLT alignment, and DMI/North Star analysis in scope, several items that were "Year 2 stretch" deserve to land *during* P0d (governance docs, deploy guide reorganization, layer-cake framing) because P0d is already touching exactly those files. The architectural design for delete-on-request (B-CARE-3) is now **Phase 24.5** — must lock in *before* P0b schema work to avoid retrofit.

**Phasing decision for BYOP and eukaryotic pipelines (2026-04-29):** The 25 backlog items from `jackpot_byop_and_eukaryotic_design.md` are NOT homogeneously deferrable to a single late phase. They split three ways: (1) **schema items move to P0b** alongside the existing Schema v5.0 work — otherwise we migrate twice. The 4 schema items (B-BYOP-9, B-EUK-1, B-EUK-2, B-EUK-3) are now bundled into Phase 24.5's design-lockdown deliverables. (2) **BYOP infrastructure (10 items) gets a new P0f phase** between P0e and P0b/c, because eukaryotic pipelines need BYOP to land first, and BYOP can't wait for P1. (3) **Default eukaryotic pipelines + parsers + dashboards (11 items) stay in Phase 28** but are internally tier-prioritized: Tier 1 (Plasmodium, Crypto/Giardia) ships first.

Phase 21 UI triage stays where it is — Session 5 debt, ship-blocker, not displaceable.

Instructions for Claude Code: Work through items in order within each phase.
Check off each item only after `uv run pytest` passes. Never skip an item —
if blocked, note the blocker in `docs/review_log.md` and move to the next
unblocked item.

---

## Current state (verified end of Session 5)

**Backend — Month 1 + most of Month 2 complete:**

- **Fully implemented routers:** `auth`, `gisaid`, `organizations`, `labs`
  (including `lab_membership`), `projects`, `users`, `domain_whitelist`,
  `sequencing_labs`, `tokens`, `dataharmonizer`, `ingest` (upload, csv,
  globus), `samples` (list, get, update, archive, files, download),
  `pipelines` (launch, events, monitor, results, resume, BYOP,
  promotion — 10 endpoints), `sample_access`, `templates`.
- **Backend modules:** `validator`, `file_detector`, `harmonizer`,
  `epiweek`, `audit`, `permissions`, `dlp_scanner`,
  `pipeline_results_loader`, `pipeline_config`, `template_generator`,
  `notifications`, `responses`, `pagination`, `storage`, `config`,
  `database`, `middleware`, `logging`, `version`.
- **jackpot-nf:** 11 pipeline parsers (viral, bacterial, metagenomic),
  nf-jackpot plugin, shared result schemas, hamronization normalizer.
- **Test suite:** 477 tests passing, 86.99% coverage as of Session S
  complete. Session 5 added staging infra changes without net-new test
  coverage.
- **Local Docker Compose stack:** running cleanly — `api`, `postgres`,
  `minio`, `minio_init`, `ui` all green. `/health` returns DB-connected.
- **GCP staging:** deployed Session 5, API live, `/health` green
  in-cluster. 6 known quirks from Session 5 debugging documented in
  `docs/staging_access.md`.

**Frontend — scaffold complete, renders, authenticates:**

- Streamlit pages live in `jackpot-backend/frontend/` (not the separate
  `jackpot-frontend` repo, which is a vestigial stub).
- All 9 researcher pages exist: `dashboard`, `search`, `upload`,
  `data_entry`, `my_samples`, `datasets`, `access_requests`,
  `notifications`, `pipelines`. Admin pages (`lab_director`,
  `platform_admin`, `archive_requests`, `billing`) intentionally
  deferred to Month 3.
- Landing page renders at `http://localhost:8501`. Sidebar shows all 9
  pages. Mock auth works end-to-end — `current_user()` returns the
  seeded admin user with lab memberships.
- **Unknown:** individual page render behavior. Phase 21 UI-B through
  UI-F walks every page to find out.

---

## Out-of-band housekeeping

- **2026-04-24** — Renamed JACKPOT organisation "host academic operator" → "Example Org"
  via migration `c1bd67369a7c`. Same migration renames the
  `sequencing_labs.organization` denormalised text and the
  `domain_whitelist` row. Seed snapshot updated in `db/SCHEMA.sql`.
  Pattern documented in `docs/learnings.md`.

- **2026-04-26 to 2026-04-28** — Cleanup A through J: removed institutional
  operator-specific references
  from the codebase to align with the operator-agnostic principle (Critical
  Rule 55). Production code now knows nothing about any specific operator;
  only the eventual `jackpot init` bootstrap step learns operator names at
  install time.

  | Letter | Scope                              | Commit    | Notes |
  |--------|------------------------------------|-----------|-------|
  | A      | docs cleanup                        | `68e3565` | jackpot-backend |
  | B      | schema rename `adhs_medsis_id` → `external_case_id` | `667aaaf` | + submodule `8416e28` |
  | C      | HTML course content                 | `b804e76` | + submodule `684a0c4` |
  | D      | test fixture data                   | `d51e39d` | jackpot-backend |
  | E      | straggler test fixtures             | `c29fa42` | jackpot-backend |
  | F      | seed scripts genericized            | `771cbc8` | + new migration `00b4bd99ddee` |
  | G      | submodule schema-update scripts     | (no-op)   | already clean from prior work |
  | H      | misc files + 2 deletions            | `83f9f28` | deleted `CLAUDE_addition.md`, `rewrite_validator.py` |
  | I      | nf/ test fixtures (AZ-* → EX-*)     | `a9a2a94` | + submodule `f11e719` |
  | J      | Streamlit frontend                  | (no-op)   | grep matches were all 'banner' false positives |

  Net result: the codebase is operator-agnostic. The next phase, P0d, is
  the monorepo migration to `Midnight-Oil-Innovation/jackpot`.

- **2026-05-04 to 2026-05-05** — Sessions 21+ deliverables shipped:

  | PR  | Title                                                                                                        | Merged at  | Type    |
  |-----|---|---|---|
  | #21 | P0g G-1+G-2: execution profiles foundation (schema + migration)                                              | `a682788`  | feature |
  | #22 | P1: Auth refresh endpoint with single-use refresh-token rotation                                             | `ba03143`  | feature |
  | #23 | docs: bump session backlog to v4.0 covering Session 20 (I-track complete)                                    | (squashed) | docs    |
  | #25 | chore: pin ruff at 0.11.6 across pre-commit, member pyproject.tomls, and uv.lock                             | (squashed) | chore   |

  - **PR #21 (P0g G-1+G-2)** — schema foundation for execution profiles per Critical Rule 59 (per-run executor selection). Adds `ExecutionProfile` + `PipelineDefaultProfile` LinkML classes, `ExecutorTypeEnum` (7 values) and `ContainerEngineEnum` (4 values) enums, regenerated Pydantic v2 models, Alembic migration `bac8dbb11c0b` chained after I-3a head with partial unique index for "at most one default", FK cascade, CHECK constraints, and `default-local` seed (PL/pgSQL guard on user existence with `ON CONFLICT (name) DO NOTHING`). 32 tests added (20 schema + 8 migration + 4 seed). Foundation for G-3 through G-11 which can run in parallel after this lands.

  - **PR #22 (P1)** — full auth refresh + rotation work. Closes I-track entirely (was the last open item from Phase 22 review item 12 / spec.md §13 fix #5). New `/api/v1/auth/refresh` endpoint with single-use rotation, `refresh_tokens` table, replay detection, six error codes, rotation-aware login/logout, daily cleanup APScheduler job, three new audit-action constants. 31 tests across 5 files. See Phase P1 entry below for full details.

  - **PR #23 (docs)** — bundle refresh of `docs/jackpot_session_summary_and_backlog.md` from v3.2 → v4.0 covering all four Session 20 I-track PRs (C-1 / I-3a / I-3b / I-3c) plus the I-track-complete milestone. Pure docs change, auto-merged.

  - **PR #25 (chore: ruff pin)** — permanent fix for the recurring "format-clean-locally, fail-on-CI" loop that bit PR #21 and PR #22 on first runs. Aligns ruff version across all three sources of truth: `.pre-commit-config.yaml` (already at `v0.11.6`), `backend/pyproject.toml` (was `==0.4.4`, now `==0.11.6`), `cli/pyproject.toml` (was `>=0.4.0`, now `==0.11.6`), `uv.lock` (was `0.4.4`, regenerated to `0.11.6`). Plus new `docs/CLAUDE.md` section documenting the three-source pin and the post-bump ritual. Note that the documented ritual uses bare `pre-commit clean` etc. — should be `uv run pre-commit clean` for environments where pre-commit isn't on global PATH (small follow-up; see "Post-Sessions-21+ housekeeping" below).

  - **Recovery saga** (Sessions 20-21): Severe worktree contamination during parallel-track execution. P1 work ended up in a stash labeled "phase-24.5: WIP across branches before rebase" because P1's agent was working in the main clone (which had been switched to phase-24-5 branch) instead of in a dedicated p1 worktree. Recovery required: (1) creating a fresh `~/Projects/jackpot-p1` worktree, (2) extracting only the truly-pure-P1 files via `git checkout 'stash@{0}' -- <pathspec>` (skipping the contaminated schema files which contained both P0g and P1 additions), (3) discovering the agent had skipped the `RefreshToken` LinkML class entirely (only added the migration), (4) committing what was extracted, (5) resuming a fresh agent in the new worktree to add the LinkML class + write tests + open PR. Logged in `learnings.md` "Worktree contamination — Sessions 20-21" entry. Going-forward mitigation: every Claude Code session in a worktree starts with a verification ritual that asserts `pwd` matches the expected worktree path AND `git branch --show-current` matches the expected branch; refuse to proceed if either fails.

  - **PR-numbering note:** there were transient duplicates during the chore PR work — a `chore/pin-ruff-version` branch (eventually empty, PR #24 closed) and a `chore/pin-ruff-version2` branch (had the actual fix, became PR #25). The "2" suffix is cosmetic but the canonical PR is #25.

---

### Post-monorepo housekeeping (surfaced during F-2 prep)

The P0f F-2 implementation in Session 15 surfaced multiple gaps from
the monorepo migration. None blocked F-2 from landing, but they
accumulate. Worth a coordinated cleanup pass before P0f F-3 starts.

- [x] **Establish branching workflow for the monorepo.** Resolved
      2026-05-03 via PR #4: option (c) — long-lived `development`
      integration branch. Feature PRs target `development`; release
      PRs go `development` → `main`; `staging` branch push triggers
      the GCP staging deploy (`.github/workflows/deploy-staging.yml`,
      unchanged). Documented in `docs/CLAUDE.md` "Current Baseline";
      `.github/workflows/test.yml` updated so PRs to `development`
      trigger CI. The interim option (a) used for PRs #1 and #4 is
      called out as historical in CLAUDE.md.
- [ ] **Add `slowapi` to backend runtime deps.** Currently imported in
      `backend/main.py` but missing from `backend/pyproject.toml`.
      Manually installed during F-2; needs to be declared.
- [ ] **Add dev deps to backend.** `pytest-cov`, `pytest-asyncio`,
      `testcontainers[postgres]`, `hypothesis`, `pytest-httpx` were
      manually installed in the api container during F-2 to get tests
      running. They belong in `backend/[dependency-groups.dev]`
      (or equivalent uv-supported form) and the Dockerfile should
      `uv sync --dev` for the api image.
- [ ] **Decide: lean prod image AND dev image, or always include
      dev deps?** Either `Dockerfile.api` builds two variants
      (`api-prod`, `api-dev`) or accepts the larger dev image
      everywhere. Document the choice.
- [ ] **Mount `/var/run/docker.sock` into api service** in
      `docker-compose.yml` so testcontainers-based tests can run
      inside the container. Currently host-side `uv run pytest` is the
      only working path; in-container tests fail with
      `docker.errors.DockerException` for every test that needs a
      live Postgres fixture.
- [ ] **Document `COMPOSE_PROFILES=laptop` requirement.** Add to README
      and `docs/jackpot_local_dev_setup_guide_macos.md` — without it,
      `docker compose up` returns `services: {}` and the next person
      hits the same wall.
- [ ] **Make `backend/alembic.ini` use `%(here)s/db/migrations`.**
      Currently the relative `script_location = db/migrations` only
      resolves correctly when alembic runs from `backend/`. Adding
      `%(here)s` makes invocations work from any cwd.
- [ ] **Clean up the broken `.venv` symlink at `/app/.venv`** inside
      the api container. Different from `/opt/venv` which is the real
      venv; the broken symlink trips `uv pip install` from the
      container's WORKDIR.
- [ ] **Resolve schema mount path inconsistency.** `ui` service mounts
      schema at `/app/schema`, `api` mounts at `/schema`. Pick one
      canonical path so streamlit and api can use the same import
      logic.
- [ ] **Audit `Dockerfile.api` and `Dockerfile.ui` for Apptainer
      compatibility.** Required for scenario C where Docker isn't
      allowed on the cluster. UID assumptions, root-write paths,
      Docker-socket assumptions all need flagging or fixing. (Pairs
      with the broader Apptainer support work in Phase P0e of the
      jackpot init CLI.)

---

### Post-Sessions-21+ housekeeping (surfaced 2026-05-04 to 2026-05-05)

The P1 + P0g G-1+G-2 + ruff-pin work surfaced these small follow-up items. None block any feature work but they accumulate; worth a coordinated cleanup pass before the next sprint kicks off in earnest.

- [ ] **Fix `uv run pre-commit` prefix in CLAUDE.md ruff section.** The "ruff version is pinned across three sources of truth" section added in PR #25 documents the post-bump ritual as bare `pre-commit clean` etc. — but pre-commit isn't on global PATH in this environment (lives inside the uv environment, same shape as ruff). Should be `uv run pre-commit clean`, `uv run pre-commit install --install-hooks`, `uv sync`. Tiny one-liner docs PR.

- [x] **`scripts/regen_schema.py` in-repo with whitespace normalization (T-1).** Closed 2026-05-08. Script moved from sibling-only `/Users/glen/Projects/scripts_jackpot/regen_schema.py` to in-repo `scripts/regen_schema.py` for CI / pre-commit reachability. Added trailing-whitespace stripping per line on both the Pydantic output (`backend/backend/models_generated.py`) and the JSON Schema output (`schema/schema/jackpot_schema.json`) so `--check` mode no longer false-positives on whitespace-only drift between fresh regen and the pre-commit-normalized committed copy. Plus 8 ruff lint fixes (E501 ×6, N806, SIM103, UP015, F541 ×3) — script is now ruff-clean. Sibling copy retained as dev-time tooling for cross-repo work.

- [x] **`.pre-commit-config.yaml` `schema-regen-check` hook (T-2).** Closed 2026-05-08. New `local` hook that runs `python3 scripts/regen_schema.py --check --quiet` whenever `schema/schema/jackpot_schema.yaml` is staged. Catches drift between the LinkML source and the committed `models_generated.py` / `jackpot_schema.json` artifacts before commit. Idempotent — safe to run on every pre-commit invocation since it short-circuits when the YAML wasn't touched.

- [x] **Update `gac` zsh function (T-3).** Closed 2026-05-08; updated function in Glen's `~/.zshrc`. Adds a pre-fix step that runs `uv run ruff check --fix --exit-zero` + `uv run ruff format` BEFORE pre-commit, so the "files were modified by this hook" failure mode no longer fires on auto-fixable issues. Pre-commit then runs as a verification pass against already-fixed code. Fallback branch (direct `ruff` if pre-commit unavailable) retained from the original. Lives in `~/.zshrc`, not the repo — Glen-side change, but the canonical version is worth folding into `docs/dev_workflow.md` so other contributors can pick it up.

- [ ] **GitHub branch protection setup.** Now that CI tests are stable across the I-track + P0g + P1, add the test-suite check as a required status check on `main` and `development` in GitHub Settings. Belt-and-suspenders against accidentally-merged broken builds.

- [ ] **Spec.md follow-up: drop the ⚠️ note from §13 fix #5** since P1 (PR #22) shipped the explicit refresh endpoint. Tiny docs PR; fold into the next docs-shaped one.

- [ ] **Drop stale stashes from `git stash list`.** Recovery saga left a pile of leftover stashes from earlier parallel sessions (P0g WIP / I-2 WIP / session-summary WIP / housekeeping-WIP-pre-f4 / etc.). All confirmed obsolete in Session 21 cleanup; can drop with a batch loop. Glen-side, no PR needed.

- [ ] **Audit and delete obsolete local feature branches.** `p0f-f8-pre-launch-verification` and others may still be present locally. Quick `git branch --merged development | grep -v development | xargs git branch -d` after each merge would keep this hygienic.

- [x] **Recovery saga learnings — add verification ritual to all worktree-based Claude Code sessions.** First thing every parallel-track session should run is a guard that asserts `pwd` matches the expected worktree path AND `git branch --show-current` matches the expected branch; refuse to proceed if either fails. Prevents the cross-tree contamination that happened in Sessions 20-21. Logged in `learnings.md`; codified as **Critical Rule 61** in `docs/CLAUDE.md` (PR #27, commit `c7df002`).

- [x] **Fix `uv run pre-commit` prefix in CLAUDE.md ruff section.** Closed in PR #27 (`c7df002`) along with Critical Rule 61.

- [x] **Spec.md follow-up: drop the ⚠️ note from §13 fix #5.** Closed in PR #27 (`c7df002`).

---

## Performance and cleanup follow-ups (from /ultrareview Batch D)

These items are from the /ultrareview pass and are real but not blocker-level. They ship as smaller PRs incrementally, opportunistically, after R-1 + R-2 + R-3 land.

### Architectural follow-ups (deserve their own work-item specs)

- [ ] **Item #8** — pipeline_default_profile.pipeline_id UUID vs pipeline_catalog.id SERIAL mismatch (profile_resolver.py:35-38). Step 3 of the Rule-59 5-step resolution chain is dead code until a follow-up migration lands. Needs schema migration; deserves a small work-item spec. Track and ship before considering P0g complete.
- [ ] **Item #12 (register_accessions N+1)** — submissions.py:739-810. 3N queries per accession entry. Looks small but could surface concurrency issues with the submission state machine. Worth a focused work-item spec, not a one-line PR.
- [ ] **Item #13 (cache TTL/LRU strategy)** — credentials/cache.py:26 + harmonizer.py:34. Both have unbounded dicts with no TTL or LRU. Needs a small design decision (which strategy, what bounds) before implementation.

### Performance: N+1 query patterns (small PRs each)

- [ ] **Item #12 partial** — jobs.py:203-208 — per-row director lookup in _send_approve_warnings. Batch the lookup.
- [ ] **Item #12 partial** — submissions.py:432-445 — per-sample INSERT … ON CONFLICT loop in add_samples_to_submission. Use bulk insert.
- [ ] **Item #12 partial** — pipeline_results_loader.py:314-322 — per-sample SELECT id in manifest loop. Batch.
- [ ] **Item #12 partial** — jobs.py:132-174, 284-311, 327-346 — unbounded per-row UPDATE loops in _auto_approve_due_requests, _expire_grants, _moot_public_sample_requests. Add LIMIT / batch updates.

### Performance: unbounded loads / table scans (small PRs each)

- [ ] **Item #13** — jobs.py:449 — _select_rows_to_hash has no LIMIT. Add bound.
- [ ] **Item #13** — jobs.py:1048-1057 — full-file BytesIO accumulation for GS/S3 destinations. Multi-GB OOM risk. Stream instead.

### Simplicity (small PRs)

- [ ] **Item #16** — _ensure_lab_access triplicated across submissions/import_mappings/imports routers. Move to shared auth utility.
- [ ] **Item #17** — Collapse near-identical state-machine transitions in submissions.py (mark_execution_queued/_retried, mark_package_generated/mark_submitted) behind a _transition_status(...) helper. ~150 lines saved.
- [ ] **Item #18** — Delete pipeline_config/batch_submitter.py. No-op stub never shipped.
- [ ] **Item #19** — Drop submission_executors/__init__.py re-export layer. No callers.
- [ ] **Item #20** — Drop _Credentials proxy in credentials/__init__.py and pipeline_config/__init__.py re-export shim. Unused indirection.
- [ ] **Item #21** — gcp_batch.config.j2:13 hardcodes us-central1 as fallback region. Rule 55 borderline; pick: parameterize or remove fallback.
- [ ] **Item #24** — Inline two-line wrappers (_row_to_profile, _ensure_can_read, _promote_file_storage_wrapper).

### Security (small PRs)

- [ ] **Item #22** — f"…{vis_clause}" SQL splicing in routers/files.py::_load_file_row_for_user. Latent injection risk. Refactor to parameterized.
- [ ] **Item #23** — facade.py:62-68 logs str(exc) from credential errors. GCP exceptions can embed secret resource names. Trim before logging.

### Documentation note (informational, not action)

- [ ] **Item #26** — credentials/ uses 3 coordinator modules (factory + facade + registry) vs storage/'s 1. Deliberate per session summary, not a violation, but flagged for future reviewers. Already documented in spec.md credentials section after R-3.

# Performance and cleanup follow-ups (from /ultrareview Batch D)

Batch D of the May 2026 /ultrareview pass — items that aren't blockers
(R-1 PR #31 closed those) and aren't doc/tracking hygiene (R-3 closes
findings #9, #10, #11, #25) and aren't the GISAID/ENA test/dedup pile
(R-2 closes #5, #15). What's left: 14 items, mostly performance,
small refactors, and minor cleanups, traceable to the original
/ultrareview output by finding number.

The descriptions below are stubs to be populated from the original
/ultrareview output. Each item is left unchecked with its finding
number for traceability. When a follow-up PR addresses an item, fill
in a one-line description, mark the box, and reference the PR.

- [ ] **Finding #8** — *(populate from /ultrareview output; left as a
      tracking placeholder with the original line reference)*
- [ ] **Finding #12** — *(populate from /ultrareview output)*
- [ ] **Finding #13** — *(populate from /ultrareview output)*
- [ ] **Finding #14** — *(populate from /ultrareview output)*
- [ ] **Finding #16** — *(populate from /ultrareview output)*
- [ ] **Finding #17** — *(populate from /ultrareview output)*
- [ ] **Finding #18** — *(populate from /ultrareview output)*
- [ ] **Finding #19** — *(populate from /ultrareview output)*
- [ ] **Finding #20** — *(populate from /ultrareview output)*
- [ ] **Finding #21** — *(populate from /ultrareview output)*
- [ ] **Finding #22** — *(populate from /ultrareview output)*
- [ ] **Finding #23** — *(populate from /ultrareview output)*
- [ ] **Finding #24** — *(populate from /ultrareview output)*
- [ ] **Finding #26** — *(populate from /ultrareview output)*

These can be batched into one or more cleanup PRs after the next
feature track ships, or interleaved as small ones whenever convenient.
None of them blocks the development → main release.

---

## Phase 0 — Pre-Session Fixes (COMPLETE)

These were the blocking bugs resolved before any router session began.

- [x] **P0-1 through P0-16** — all completed. Summary: conftest Alembic
  migrations, auth settings isolation, JWT refresh endpoint *(see note*),
  audit/notification transaction cohesion, execute_query conn param,
  JWT type claim validation, /health 503 on DB down, APScheduler job
  intervals, tier-specific validator BASE_REQUIRED, Isolate source
  type, validator docstring v4.1→v4.4, configurable CORS origins.
  - *Note:* Phase 22 review (item 12) surfaced that the "JWT refresh
    endpoint" line was over-claimed: the refresh-token cookie IS
    issued at login but no `POST /api/v1/auth/refresh` route was ever
    written. Browser-cookie clients work fine without it; CLI/SDK
    clients that want explicit refresh would need the route.
    **P0e C.5 decision: defer the explicit-refresh endpoint to P1**
    alongside the broader auth-architecture review (refresh-token
    rotation, refresh-token revocation list, etc.). Spec.md §13 fix #5
    now carries a ⚠️ note documenting the gap.
  - **RESOLVED 2026-05-05 in P1 (PR #22, commit `ba03143`):** the
    explicit `POST /api/v1/auth/refresh` endpoint shipped with
    single-use refresh-token rotation, server-side `refresh_tokens`
    table tracking JTIs, replay detection (rotated-token reuse triggers
    bulk revocation of the user's active tokens), six distinct error
    codes (`MISSING_REFRESH_TOKEN`, `INVALID_REFRESH_TOKEN`,
    `WRONG_TOKEN_TYPE`, `TOKEN_NOT_TRACKED`, `TOKEN_REVOKED`,
    `TOKEN_REPLAY_DETECTED`), rotation-aware login/logout endpoints,
    and a daily APScheduler cleanup job. The ⚠️ note in spec.md §13
    can be removed in a follow-up docs pass. Remaining P1 broader
    auth-architecture work (session-management UI, refresh-token-family
    tracking for advanced breach detection, cross-device session
    detection, configurable token lifetimes per-user/per-role, MFA,
    new auth providers) stays deferred to a future P1.5 or folded into
    P0c.

## Phase 1 — Session A: organizations router (COMPLETE)

- [x] A-1 through A-7 — POST / GET / GET{id} / PATCH / DELETE, tests,
  commit.

## Phase 2 — Session B: labs + lab_membership router (COMPLETE)

- [x] B-1 through B-11 — CRUD on labs, full membership lifecycle
  (add / change role / remove), tests, commit.

## Phase 3 — Session C: users router (COMPLETE)

- [x] C-1 through C-7 — `/me`, CRUD, self-update guardrails, Platform
  Admin override, tests, commit.

## Phase 4 — Session D: domain_whitelist router (COMPLETE)

- [x] D-1 through D-5 — domain whitelist CRUD + tests.

## Phase 5 — Session E: sequencing_labs router (COMPLETE)

- [x] E-1 through E-8 — CRUD + assignments to labs + tests.

## Phase 6 — Session F: tokens router (COMPLETE)

- [x] F-1 through F-6 — API token CRUD with bcrypt hashing, project
  name filter, tests.

## Phase 7 — Session G: ingest router (COMPLETE)

- [x] G-1 through G-5 — upload, csv, globus endpoints. Full ingest
  pipeline: validate → epiweek → scrub_status → surveillance_relevant
  → quality_status → stage files → sample + sample_files writes in one
  transaction → audit.

## Phase 8 — Session H: samples router (COMPLETE)

- [x] H-1 through H-8 — list with full filter surface and `select_all`,
  get, update (with locked-field protection), archive, files, download
  with presigned URLs.

## Phase 9 — Month 1 Stretch Goals

- [x] S-1: projects router — full, with `?name=` filter for CLI
- [x] S-2: dataharmonizer router — full, 94% coverage
- [ ] S-3: Full test suite regression check + merge development → main
  - `uv run pytest` all passing, coverage ≥ 60%
  - Currently only blocked by developer choosing to tag and merge;
    Month 1 itself is feature-complete.

## Phase 11 — Session I: jackpot-nf plugin + result registration (COMPLETE)

- [x] I-1 through I-7 — jackpot-nf repo created, register_client,
  Pydantic schemas, `POST /api/v1/pipelines/{run_id}/results/{result_type}`
  endpoint, hAMRonization normalizer, tests.

## Phase 12 — Session J: Viral pipeline parsers (COMPLETE)

- [x] J-1 through J-6 — Cecret (pangolin, nextclade, freyja, consensus),
  viralrecon (consensus, pangolin, nextclade, variants, wastewater),
  walkercreek (irma, consensus). 79/79 tests passing.

## Phase 13 — Session K: Bacterial isolate parsers (COMPLETE)

- [x] K-1 through K-6 — bactopia (amr, mlst, assembly, annotation),
  Grandeur (amr, mlst, kraken2, blast), mycosnp-nf (snippy, tree,
  typing), tb-profiler (lineage, drug_resistance). Tests + commit.

## Phase 14 — Session L: Metagenomic parsers (COMPLETE)

- [x] L-1 through L-4 — nf-core/mag (checkm2, gtdbtk, bin_registry),
  nf-core/taxprofiler (kraken2, bracken, diamond). Tests + commit.

## Phase 15 — Session M: pathogensurveillance + shared parsers (COMPLETE)

- [x] M-1 through M-5 — pathogensurveillance parser (v1.1.0 pinned),
  shared AMR normalization validator, parser version matrix, end-to-end
  integration test framework.

## Phase 16 — Session N: pipelines router (COMPLETE)

- [x] N-1 through N-9 — launch with compatibility check, events
  weblog receiver, monitoring (run detail, tasks, events), resume for
  FAILED runs, BYOP registration skeleton, pipeline promotion workflow.

## Phase 17 — Session O: sample_access router (COMPLETE)

- [x] O-1 through O-8 — access request CRUD, approve/deny workflow,
  `can_access_sample()` integration with grants, background expiry job.

## Phase 18 — Session P: Streamlit researcher pages (COMPLETE)

- [x] P-1 through P-11 — all 9 researcher pages implemented in
  `jackpot-backend/frontend/pages/`: dashboard, search, upload,
  data_entry, my_samples, datasets, access_requests, notifications,
  pipelines. Plus smoke tests for page imports.

- [x] **UI plumbing verified (early 2026-04-19):**
  - `frontend/app.py` exists and renders
  - `frontend/lib/session.py` + `frontend/lib/api.py` wire mock auth
  - `frontend/components/` and `frontend/lib/` packages present
  - Docker Compose `ui` service works after fixes in Phase 20
    UI-plumbing block
  - Landing page shows "Signed in as the maintainer" with the seeded
    platform admin user
  - Sidebar lists all 9 pages

---

## Phase 19 — Session Q: GCP staging environment (MOSTLY COMPLETE)

- [x] **Q-1: jackpot-iac Terraform for staging** — network, Cloud SQL,
  GKE (3 node pools), 7 GCS buckets, Artifact Registry, IAM (3 GSAs +
  Workload Identity bindings). Commit `e15f40e`.
- [x] **Q-2: Secret Manager entries** — `SECRET_KEY`, `DATABASE_URL`,
  `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`,
  `NCBI_API_KEY`. Commit `6131563`.
- [x] **Q-3: GitHub Actions deployment pipeline** — WIF → build → push
  → helm upgrade (migrations as pre-upgrade hook). Commit `ab755ca`.
  Session 5 added: split checkout, PAT `insteadOf` submodule auth,
  in-cluster port-forward smoke test.
- [x] **Q-4: Deploy jackpot-backend to staging** — deployed Session 5,
  API live, `/health` returns `{"status":"ok","database":"connected"}`,
  Alembic head at `c536de6329e0`, 2/2 pods Ready.
- [ ] **Q-5: End-to-end pipeline test on staging** — Cecret (or
  viralrecon) full stack. **Blocked on:** P3.1 (test_batch.nf minimal
  harness) + UI-B/C for driving the flow. See Phase 24.
- [x] **Q-6: Staging smoke test suite** — `scripts/staging_smoke_test.sh`
  exists, runs in CI, currently uses `kubectl port-forward` (tactical
  Session 5 fix).
- [x] **Q-7: Document staging access** — `docs/staging_access.md`
  exists in `jackpot-iac/docs/`. Updated Session 5 with bootstrap Job
  YAML, troubleshooting runbook, cost controls.
- [ ] **Q-8: Commit and tag `month-2-complete`** — blocked on Q-5 and
  the permanent fixes in Phase 20.

---

## Phase 20 — Session 5 Debt

Tactical fixes from the first staging deploy + Streamlit UI debugging
are in place, but the permanent fixes aren't. These land the cleanup
before a second environment (staging-clone, production) is attempted,
and before any teammate tries to run the stack locally.

### UI-plumbing — DONE (2026-04-19 early AM)

Completed inline during Streamlit debug session. Recorded here for the
next developer who might otherwise re-encounter the same six bugs:

- [x] **Dockerfile.ui layout fix** — `COPY frontend/ .` (flattens)
      replaced with `COPY frontend/ ./frontend/` (preserves package);
      `CMD` path updated to `frontend/app.py`.
- [x] **docker-compose.yml mount fix** — `./frontend:/app` (overrode
      image layout) replaced with `./frontend:/app/frontend`; schema
      mount moved to `/app/schema`.
- [x] **docker-compose.yml command override removed** — explicit
      `command:` directive was still pointing at the old flattened
      `app.py` path; removed so image CMD takes over.
- [x] **PYTHONPATH=/app added to ui service env** — Streamlit runs
      with `sys.path[0]` set to `/app/frontend/` so the `frontend`
      package couldn't resolve its own absolute imports without `/app`
      also on the path.
- [x] **API_BASE_URL read by ApiClient** — `frontend/lib/api.py` now
      reads `API_BASE_URL` as a fallback after `JACKPOT_API_URL`
      (compose was setting the former, client only read the latter).
- [x] **MOCK_USER_EMAIL already set on api service** — confirmed line
      78 of `docker-compose.yml`. Both ui and api containers get the
      env var; the X-Mock-User-Email header round-trip works.

### Q-9: Alembic baseline migration ✅ CLOSED

Baseline revision: **`5adf11b77c19`** (`baseline schema from init.sql`).

- [x] Added Alembic revision `5adf11b77c19` containing the full v4.1
      DDL from the former `db/init.sql` as a single `op.execute()`.
- [x] Chained `a7fd1fcccb77` after it
      (`down_revision = "5adf11b77c19"`).
- [x] Set `down_revision = None` on the new baseline.
- [x] Verified `alembic upgrade head` against a fresh empty DB:
      `docker compose down -v && docker compose up -d` → api container
      runs `alembic upgrade head` via `backend/entrypoint.sh` →
      `/health` returns `{"status":"ok","database":"connected"}`.
      Round-trip `downgrade base` + `upgrade head` rebuilds cleanly.
- [x] Renamed `db/init.sql` → `db/SCHEMA.sql` (read-only reference
      snapshot with header). Removed Postgres entrypoint mount from
      `docker-compose.yml`.
- [x] Added Critical Rule 52 to `docs/CLAUDE.md`. Amended Rule 44 to
      drop the bootstrap-Job/Q-9-pending caveats.
- [x] Documented cut-over path in `docs/staging_access.md §6`:
      one-time `kubectl exec ... alembic stamp 5adf11b77c19` for
      environments deployed pre-Q-9.
- [x] `tests/conftest.py` no longer loads init.sql — runs only
      `alembic upgrade head`, exercising the same path as production.
- [x] 549 tests passing, 87.56% coverage (above ≥477 / ≥86.99% baseline).

### Q-10: cors_origins validator in `backend/config.py` ✅ CLOSED

Validator + 11 unit tests in `tests/test_config.py`. Pydantic-settings
bumped to `>=2.3.0,<3` (resolved 2.14.0) so `NoDecode` is importable.

- [x] Applied `Annotated[list[str], NoDecode]` + `field_validator(mode="before")`
      to `cors_origins` in `backend/config.py`. Accepts JSON arrays,
      comma-separated strings, empty strings, `None`, and real lists;
      raises `ValueError` with a helpful message on malformed JSON.
- [x] Bumped `pydantic-settings>=2.3.0,<3` in `pyproject.toml`
      (was `==2.2.1`). `uv lock` regenerated.
- [x] Reverted `jackpot-iac/helm/jackpot-api/values-staging.yaml` line
      24 CORS_ORIGINS to plain comma-separated form.
- [x] Added Critical Rule 53 to `docs/CLAUDE.md`. Amended Rule 45 to
      drop the cors-specific Q-10 backlog caveat (mirrors Q-9's
      Rule 44 ↔ Rule 52 split).
- [x] 560 tests passing, 87.62% coverage (was 549/87.56% baseline —
      +11 new config tests, no regressions).
- [x] Compose smoke: api boots cleanly with both CSV
      (`http://localhost:8501,http://localhost:4200`) and JSON-array
      (`'["http://localhost:8501","http://localhost:4200"]'`) forms;
      `/health` returns `{"status":"ok","database":"connected"}`.

### Q-11: Remove `sys.path` hack from `pipelines.py` ✅ CLOSED

Vendored `nf/shared/schemas/` → `backend/pipeline_schemas/` (10-file
package, identical layout — preserves diff-ability with the nf side).

- [x] Picked Option B (layout-preserving vendor) — `backend/pipeline_schemas/`
      is a package mirroring `nf/shared/schemas/` file-for-file, not a
      flattened single module. Easier upstream-diff. Provenance noted
      in the package `__init__.py` docstring.
- [x] `backend/routers/pipelines.py` now does
      `from backend.pipeline_schemas import RESULT_SCHEMAS`. Deleted
      the `_NF_ROOT` block, the `sys.path.insert`, and the late
      `from shared.schemas import …`. `import sys` removed (no other
      usage); `Path` retained (used elsewhere).
- [x] `Dockerfile.api` no longer has `COPY nf/`. New `.dockerignore`
      at repo root excludes `nf/` (and other build-context bloat) so
      the API image is smaller and won't accidentally regress.
- [x] Critical Rule 54 added; Rule 46 amended to drop the Q-11 caveat
      and reflect the new boundary (mirrors Q-9/Q-10 split pattern).
- [x] Verified `from backend.routers import pipelines` succeeds with
      `nf/` absent from disk (mv nf nf.bak simulation).
- [x] Verified docker build succeeds with `nf/` excluded; image's
      `/app/` no longer contains `nf/`; `from backend.pipeline_schemas
      import RESULT_SCHEMAS` works inside the container (9 schemas).
- [x] `docker compose down && up -d --build` brings stack up clean;
      `/health` → `{"status":"ok","database":"connected"}`.
- [x] `jackpot-nf` submodule unchanged (SHA `a45fb13`).
- [x] 560 tests passing, 88.34% coverage (was 560/87.62% — coverage
      ticked up because the vendored schemas count toward the
      measured surface).

### Q-12: Terraform-owned DATABASE_URL Secret

- [ ] Wire `terraform/modules/secrets/` to construct `DATABASE_URL`
      from Cloud SQL module outputs (`private_ip`, port, db name) +
      password Secret reference.
- [ ] Eliminates the hand-populated Secret that caused the `/jackpot`
      vs `/jackpot_db` drift in Session 5.

### Q-13: Rotate staging DB password

- [ ] Run the rotation (password visible in chat during Session 5
      debugging — staging only, low blast radius):

```bash
NEW_PASS=$(openssl rand -base64 24 | tr -d '=+/')
gcloud sql users set-password jackpot \
    --instance=jackpot-staging-db \
    --password="$NEW_PASS" \
    --project=jackpot-staging-project
gcloud secrets versions add jackpot-staging-database-url \
    --project=jackpot-staging-project \
    --data-file=- \
    <<< "postgresql://jackpot:${NEW_PASS}@10.188.230.3:5432/jackpot_db"
cd ~/jackpot/jackpot-iac
gh workflow run deploy-staging.yml --ref staging
```

### Q-14: Public Ingress + DNS + managed cert for staging

- [ ] Terraform additions: GKE Ingress (or `LoadBalancer` Service),
      Cloud DNS record, managed SSL cert.
- [ ] Update `JACKPOT_API_URL`, `CORS_ORIGINS`,
      `GOOGLE_OAUTH_REDIRECT_URL` in `values-staging.yaml` to real URL.
- [ ] Flip `scripts/staging_smoke_test.sh` back to hitting real URL
      instead of `localhost:8080` port-forward.
- [ ] **Unblocks:** end-to-end Google OAuth testing, Q-5 (staging E2E
      pipeline test with real weblog callbacks).

### Q-15: Helm upgrade hardening

- [ ] Option A: add `--atomic` to the workflow's `helm upgrade` —
      auto-rolls-back on failure, keeps release clean, but loses debug
      evidence on timeout.
- [ ] Option B: add a pre-upgrade step that detects `pending-*` status
      and rolls back automatically.
- [ ] Manual recovery command if stuck:
      `helm -n jackpot rollback jackpot-api <last-good-rev>`

### Q-16: Bump GitHub Actions to Node 24

- [ ] Either set `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` at the
      workflow `env:` level, or upgrade actions when `@v5` versions
      are available.
- [ ] Every workflow run currently warns Node 20 is deprecated as of
      2026-09-16.

### Q-17: Update CLAUDE.md with Session 5 lessons

- [ ] Add Critical Rules 42-47 from `claude_md_rules_addendum.md`:
  - Rule 42: Alembic must reach head from empty DB
  - Rule 43: list-typed settings need multi-form validators
  - Rule 44: `nf/` submodule must be importable or wrapped
  - Rule 45: Never paste across secret types (prefix check)
  - Rule 46: `yaml.safe_load` is not a GitHub Actions validator
  - Rule 47: Helm `--wait` timeouts wedge at `pending-*`

### Q-18: Fix misleading "API unreachable" banner in `frontend/app.py`

- [ ] `current_user()` in `frontend/lib/session.py` returns `None` for
      both auth failures and network failures. The landing page in
      `frontend/app.py` shows "API unreachable" for both cases. Fix
      the distinction:
  - Option A: change `ApiClient` to raise different exceptions for
    network vs. auth; let `app.py` render different banners.
  - Option B: probe `/health` first in `app.py`; show "API unreachable"
    only if that fails, otherwise show "Not signed in."
- [ ] **Estimated effort:** 15 minutes with fresh eyes.

---

## Phase 21 — UI Page Triage

The Streamlit shell is green. What remains is walking every page to
see which render cleanly against the running backend vs. which break.
Do these in order — each builds on earlier ones.

### UI-A: Landing page smoke (COMPLETE)

- [x] Hit http://localhost:8501 → landing page renders
- [x] Sidebar shows all 9 pages
- [x] Auth probe via `current_user()` returns the maintainer (platform
      admin, Example Lab director)

### UI-B: Upload page ✅ CONTRACT VERIFIED (2026-04-24) — browser walk still owed

Reframed to backend-contract + page-code review (no headless-browser
tooling in session). Detailed report: `docs/learnings.md` "UI-B —
Upload page triage". Two real backend bugs found and fixed at root.

- [x] **Backend ingest contract**: happy + 4 error scenarios verified
      via curl against the live local stack. Envelope shape matches
      `frontend/lib/api.py` expectations.
- [x] **Bug fix 1 — `validate_file_type()` was never called on
      upload.** Now invoked in `backend/routers/ingest.py:upload()`
      via tempfile, with `FileDetectorError` → 400. CSV-named-fasta
      and gzipped-CSV-named-fastq.gz now rejected with human messages.
      Regression: `test_upload_rejects_csv_renamed_to_fasta`,
      `test_upload_rejects_gzipped_csv_renamed_to_fastq_gz`.
- [x] **Bug fix 2 — HTTPException-based errors bypassed the JACKPOT
      envelope.** Added global `HTTPException` and
      `RequestValidationError` handlers in `backend/main.py` that
      normalise every error to `{"success": false, "error": {...}}`.
      Also fixed `dataharmonizer.py` raw `JSONResponse({"detail": ...})`
      → `responses.error()`. Regression:
      `test_validation_error_uses_jackpot_envelope`,
      `test_string_detail_http_exception_uses_envelope`.
- [x] **Page-code review**: `upload.py` + `api.py` confirmed to parse
      the new envelope correctly. Every error path → `ApiError.message`
      → `st.error("Upload failed: ...")`. No paths produce raw JSON
      dumps post-fix.
- [x] **Seed rename**: "Example Lab" → "Example Lab" via Alembic
      migration `e5315db18d40`. `db/SCHEMA.sql` snapshot updated.
- [x] **564 tests passing, 88.22% coverage** (was 560/87.62%; +4
      regression tests, no skips).
- [ ] **Browser walkthrough still owed** — needs a human at the
      keyboard to confirm rendering. Steps to click through (matches
      contract walkthrough): valid upload → error scenarios 7/8/9.
      Step 6 (missing host_age) doesn't trigger as the task assumed
      — host_age is optional in the current validator; product-owner
      decision needed if it should be required for Human samples.
- [ ] **Recommend opening UI-B2** for missing form fields:
      sequencing-lab + project dropdowns, sector auto-derive, host
      species/age/sex, isolation source, organism autocomplete,
      year-only date tolerance UI. Current page is an MVP scaffold.

### UI-C: Search page

- [ ] Filter by the sample uploaded in UI-B (organism, collection date).
- [ ] Expected: the sample appears in the result list with tier badge
      and quality_status.
- [ ] Verify bulk-select mechanic works.

### UI-D: Sample detail page

- [ ] Click into the sample from search results.
- [ ] Verify all metadata visible, file list shows the uploaded file,
      download link generates a presigned URL.
- [ ] PATCH a metadata field → expect `quality_status` recomputation.
- [ ] PATCH a locked field (e.g. `quality_status`) → expect rejection.

### UI-E: Dashboard page

- [ ] Recent samples list should include the UI-B upload.
- [ ] Quick actions (Upload / Search / New Dataset) navigate correctly.

### UI-F: My Samples, Access Requests, Notifications, Datasets, Pipelines

- [ ] Click each in turn. Log which render cleanly vs. which show
      error banners vs. which are "Month 3 placeholder" by design.
- [ ] Build a per-page bug list before scheduling fixes. Some pages
      may call endpoints that don't exist yet (e.g. `notifications`
      router is deferred to Month 3).

### UI-G: End-of-Phase-21 commit

- [ ] `gac "feat(ui): Phase 21 page triage complete — see review_log.md"`
- [ ] Update `docs/review_log.md` with the per-page status.

---

## Phase 21.5 — Interstitial During-P0d Quick Wins

**Status (2026-05-01):** all items below COMPLETE. Phase 21.5 docs landed during P0d execution (commit `2d340af docs(p0d): Phase 21.5 quick-wins — STLT guides, FHIR mapping, README, spec edits` plus `f46f7ee docs(p0d): governance/ directory — 8 charter + policy documents`).

**Why this phase existed:** P0d was already touching the docs tree, the repo structure, the README, and the directory layout. These items were pure-documentation or near-pure-documentation work that rode along naturally with the monorepo migration. Doing them as part of P0d was more efficient than scheduling them as separate phases — the alternative was reopening the same files later. None added engineering scope; they all added clarity / governance / grant-narrative quality.

The items below are kept for historical record with checkboxes marked. Order was rough effort ascending.

### B-DMI-3: "Single-entry-point" framing in spec.md

- [x] Add a short subsection to spec.md §1 (or §3 depending on where the ingest-paths description lives now) documenting JACKPOT's six ingest paths as "the single entry point for genomic data into a public health agency." (Landed in spec.md §1.1 in P0d.)
- [x] Effort: half a session, ~30 min of writing.

### B-STLT-2: Layer-cake diagram in spec.md

- [x] Add the layer-cake diagram from `jackpot_cdc_dmi_stlt_overview.md` §9.1 to spec.md. (Landed in spec.md §3.0 in P0d.)
- [x] Frame as "JACKPOT integrates with these systems; it does not replace them."
- [x] Effort: 1 session.

### B-GOV-1 + B-CARE-1: Governance directory with CARE Principles

Combined — same act of writing.

- [x] Create `governance/` directory at repo root with:
  - [x] `charter.md`
  - [x] `coi-policy.md`
  - [x] `jurisdiction-and-data-residency.md`
  - [x] `benefits-sharing-framework.md`
  - [x] `access-grievance-procedure.md`
  - [x] `platform-shutdown-data-portability-plan.md`
  - [x] `advisory-board.md`
  - [x] `care-principles-and-tribal-data-sovereignty.md`
- [x] Link from README.md and from spec.md.
- [x] Effort: 1 session of writing.

### B-CARE-2: Add Scenario T to spec.md scenarios list

- [x] Update spec.md §1 scenarios table from 6 entries to 7 — added **T (Tribal-sovereignty deployment)** in the §1 pivot blockquote.
- [x] Brief mention in CLAUDE.md project header. (Bumped from "6 install scenarios" to "7" with the T variant called out.)
- [x] Effort: half a session.

### B-DMI-1: FHIR-translatable data model documentation

- [x] Add `docs/fhir-mapping.md` documenting how JACKPOT's LinkML schema entities map to FHIR R5 resources. (Landed in P0d.)
- [x] Pure documentation; no implementation. Sets up `B-DMI-2` (actual FHIR ingest router) for Year 2.
- [x] Effort: 2 sessions of writing.

### B-STLT-1: Five STLT deploy guides under `docs/deploy/stlt/`

- [x] `state-health-department.md`
- [x] `territorial-health-agency.md`
- [x] `local-health-department.md`
- [x] `tribal-authority.md`
- [x] `tribal-epidemiology-center.md`

- [x] Effort: 5 sessions total — landed in P0d alongside the monorepo work.

### B-STLT-3: Funding-source map in deploy guides

- [x] Funding-source map from `jackpot_cdc_dmi_stlt_overview.md` §10 included in each STLT deploy guide.
- [x] Effort: rolled into B-STLT-1.

### Phase 21.5 success criterion

By the time P0d is otherwise complete:

- [x] `governance/` directory exists with all 8 markdown files
- [x] spec.md has Scenario T, layer-cake diagram, single-entry-point framing
- [x] `docs/deploy/stlt/` has all 5 STLT deploy guides
- [x] `docs/fhir-mapping.md` documents FHIR-translatable schema
- [x] CLAUDE.md mentions Scenario T in the project header
- [x] README.md links to governance/ directory

If any of these slip past P0d, that's fine — they're not gating. But if you're touching docs anyway during P0d, you should be touching these.

---

## Phase 21.6 — P0d.1 Post-Execution Cleanup (COMPLETE 2026-05-01)

Four structural follow-ups surfaced AFTER P0d's `p0d-complete` tag landed (commit `d32f40a`) but before the local dev stack actually ran. None were caught by P0d's own success criteria — those covered tests-pass and /ultrareview-clean and gh-archive-done, but didn't include "`docker compose up` brings the full stack up." Documented in detail in `learnings.md` ("P0d.1 — Post-execution cleanup" entry) and `jackpot_session_summary_and_backlog.md` Session 12.

Items, all complete:

- [x] **docker-compose.yml moved from `backend/` to monorepo root.** P0d's filter-repo carried it along with backend's other root-level files; relative paths broke in the new layout.
- [x] **Dockerfile.api and Dockerfile.ui rewritten for workspace-aware paths.** Now copy full uv workspace (root pyproject + all member directories) before `uv sync --frozen` so workspace resolution sees all member metadata.
- [x] **entrypoint.sh updated for new layout.** `cd /app/backend` before alembic (script_location=db/migrations), `cd /app` before uvicorn (backend.main:app import).
- [x] **Frontend canonicalization.** P0d's design kept canonical Streamlit at `backend/frontend/`; chat-side analysis incorrectly deleted it as a "stale shadow" (commit `5dd4806`). Recovery: filter-repo merge of archived gotero/jackpot-frontend brought in a half-finished uv-init stub (not useful); canonical files restored from `5dd4806^` and relocated to `frontend/` at monorepo root (more aligned with P0d's "each component at top level" intent than its actual `backend/frontend/` placement).
- [x] **`p0d-validated` tag added** at the commit where the stack genuinely runs end-to-end. `p0d-complete` kept at d32f40a for historical record.
- [x] **End-to-end smoke validated:** API healthy with all 17 alembic migrations applied, Streamlit on 8501 with 9 researcher pages, /health returns 200, 55 OpenAPI paths registered.

**Lessons folded back into learnings.md:**

- "Shadows that aren't shadows" — always `git ls-files <canonical-path>` before deleting apparent duplicates
- `backend/backend/` for uv workspaces is a standard layout, not an anti-pattern
- git filter-repo `--to-subdirectory-filter` wraps structure, doesn't flatten it
- Docker workspace pattern: copy full workspace (root pyproject + all members) before `uv sync`
- Compose file location matters in monorepo migrations — should be at root
- `gotero/jackpot-frontend` was a uv-init stub; the canonical streamlit lived inside `jackpot-backend`
- Future structural-migration phases should include "fresh-clone smoke test" in the success criteria, not just unit-test pass

---

## Phase 22 — Periodic Review Checkpoint (COMPLETE 2026-05-01)

Four-agent parallel review (Critical Rules, spec drift, coverage, TODOs)
followed by four sequential security/deploy commits. Findings synthesized
into `docs/review_log.md` (commit `8cbb993`) — that file is the canonical
output and carries the 19-item action list. Session 13 in
`jackpot_session_summary_and_backlog.md` and the Phase 22 entry in
`learnings.md` carry the play-by-play.

Named deliverables, all done:

- [x] **SEC-1: Tighten CORS methods/headers in `backend/backend/main.py`** —
      replaced `allow_methods=["*"]` / `allow_headers=["*"]` with explicit
      lists. Commit `cea62b6`.
- [x] **SEC-2: Add rate limiting** — `slowapi==0.1.9` on
      `/api/v1/auth/google/login` (5/min) and `/api/v1/ingest/{upload,csv,globus}`
      (60/min); env-tunable; envelope-conforming 429 handler; 3 new tests.
      Commit `a1ed4ab`.
- [x] **DEPLOY-1: Document staging→production gate** — new
      `.github/workflows/deploy-production.yml` declaring
      `environment: name: production` (Required Reviewers configured in
      GitHub UI, per-instance); workflow_dispatch only with mandatory
      `image_tag` + `reason` inputs; runbook at
      `docs/deploy/production-deploy.md`. Commit `f7680ea`.
- [x] **DEPLOY-2: PITR restore drill procedure** —
      `docs/deploy/pitr-restore-drill.md` with permissions, 6-step drill,
      explicit pass criteria, cleanup. README.md gained an "Operations
      runbooks" index. Live drill execution deferred to per-instance
      go-live (procedure-only here). Commit `6d35d20`.

Action items deferred to later phases (numbered per `docs/review_log.md`):

- **P0e (next sprint) absorbs:**
  - 5: ~~Fix coverage docs~~ — RESOLVED post-Phase-22 by commit `863fd18` once
    the real measurement bug was identified (the framing was wrong, not the docs).
  - 6: ~~Change `--cov=backend` → `--cov=backend/backend`~~ — RESOLVED post-Phase-22
    by commit `863fd18` with the correct fix (`--cov` bare + explicit
    `--cov-config=pyproject.toml` + `source_pkgs = ["backend"]`).
  - 7: Remove 9 stale CLI TODO comments
  - 8: Wire 3 SDK methods (`Sample.download_fastq`, `SamplesModule.search/get`)
    — backend endpoints already live
  - 9: Fix CLI Rule 55 (Glen-introduced) — `cli/jackpot/cli/upload.py:442,474,478,485`,
    `cli/jackpot/cli/main.py:25,47`, remove dead `ADHS_ORGANIZATION_NAME` from Helm values
  - 10: Stub routers return 501 instead of 200 (datasets, notifications,
    archive_requests, saved_searches, billing, dataset_access, ncbi_submissions)
  - 11: Fix 5 inherited Rule 55 CRITICAL violations (`backend/setup/write_files*.py`,
    baseline migration `5adf11b77c19`, `Chart.yaml`, `bootstrap_project.sh`) — these
    block any non-Glen operator deploys. Also fold in the 6 inherited Rule 55
    violations in `deploy/helm/jackpot-api/values-staging.yaml` (project ID, SA
    email, `JACKPOT_API_URL`, `CORS_ORIGINS`, dead `ADHS_ORGANIZATION_NAME`)
    flagged by UR pass-3 — `jackpot init` is the natural operator-bootstrap
    point for all of these.
  - 12: ~~Implement `POST /api/v1/auth/refresh` OR remove the spec claim that it exists~~ — **RESOLVED 2026-05-05 in P1 (PR #22, commit `ba03143`)** with full rotation, replay detection, and `refresh_tokens` server-side table.
  - 13: Resolve `backend/backend/storage/*.py` SPDX `Apache-2.0` vs project AGPL-3.0
    (needs human decision on whether storage module was adapted from Apache source)
  - 14: Update spec — drop the 60% coverage claim conflict (post-fix: real coverage
    is 84%, threshold restored to 80%); update §10 frontend path; close Q-10/Q-11;
    update §3 `STORAGE_BACKEND` to `STORAGE_ENDPOINT`
  - 15 (revised): Close the 4 real coverage gaps surfaced by the post-Phase-22
    measurement fix — `harmonizer.py` 0% (no tests), `routers/gisaid.py` 43%
    (~17 missing stmts in lines 57-116), `routers/templates.py` 53% (~9 missing
    stmts in lines 58-68, 97-104), `dlp_scanner.py` 71% (~34 missing stmts).
    Estimate: ~20 targeted tests, not the ~100 we previously planned. Lifts
    coverage from 84% → ~90% if all four gaps close.
  - 16: Implement `jackpot auth login` OAuth flow + backend `/auth/cli-login-url`
  - 18: Move Rule 18 violation in `ingest.py:288` (FASTA scrub_status logic) into
    `validator.py.ValidationResult` (lighter than expected — was tagged "Phase 24
    refactor" but fits naturally with P0e's CLI-touches-ingest work)
  - **B-FED-1** (NEW, deferred from P0e): central CA infrastructure for
    federation peer authentication. P0e ships local ed25519 keypair generation
    only — operators share public keys out-of-band. Deferred trigger: when
    JACKPOT federation network exceeds ~5 instances OR when a peer revocation
    event becomes operationally necessary. Federation protocol designed to
    support BOTH local-keypair AND CA-cert auth modes simultaneously, so
    Scenario T instances (which retain local-keypair regardless for sovereignty
    reasons) can continue to federate with CA-using peers. Phase placement: P1
    or later, depending on federation network growth.

- **Month 3 / Phase 24+:**
  - 17: Build out 7 stub routers (datasets, notifications, archive_requests,
    saved_searches, billing, dataset_access, ncbi_submissions)

- **CI track (separate from feature phases):**
  - 19: Investigate testcontainers DinD reliability if integration tests are
    erroring silently in CI

---

## Phase 23 — Minimal Nextflow Test Pipeline

### P3.1 — `scripts/test_batch.nf`

- [ ] Build a 20-line Nextflow pipeline: echo a string, write a tiny
      result file, exit.
- [ ] Configure with `-weblog http://localhost:8000/api/v1/pipelines/events`
      for local dev, the public URL (from Q-14) for staging.
- [ ] Run against local stack: verify the pipelines router receives
      events, registers a run, transitions state correctly.
- [ ] Smallest-possible exerciser of the weblog receiver and pipeline
      state machine. Worth having before viralrecon or any nf-core
      pipeline is attempted.

---

## Phase 24 — End-to-end Pipeline Test on Staging (closes Q-5)

**Depends on:** Q-9 (Alembic baseline), Q-14 (public URL), P3.1 (test
harness), UI-B (Upload page working), UI-F pipelines-page entry.

- [ ] Pick viralrecon as the first real pipeline test (better-documented
      than Cecret as an nf-core pipeline).
- [ ] Upload a test SARS-CoV-2 sample via the UI.
- [ ] Launch viralrecon via the pipelines page.
- [ ] Verify the full chain: sample uploaded → staged → scrubbed →
      pipeline launched → events received → results registered →
      `pangolin_results` + `nextclade_results` tables populated →
      MultiQC report viewable in the UI.
- [ ] Document the full run in `docs/staging_e2e_test.md`.
- [ ] Tag: `git tag -a month-2-complete -m "Month 2 complete: pipelines + parsers + sample_access + Streamlit + GCP staging + E2E verified"`

---

## Phase 24.5 — Architectural Design Lockdown Before P0b Schema Work

**Why this phase exists:** P0b will land Schema v5.0 (instances/tenants/federated_peers). If P0b ships without thinking through these architectural decisions, the schema will need to be retrofitted later — meaning another migration, another data-handling review, another round of operator-deploy churn. Two distinct architectural gates must be locked in before P0b touches the schema:

1. **Sovereignty-compliant deletion** (CARE Principle "Authority to Control" requires withdrawn-consent data to actually leave the system, not just get soft-deleted)
2. **BYOP + eukaryotic schema additions** (the BYOP `byop_pipelines` table and `pipeline_results` FK additions, plus the eukaryotic OrganismNameEnum/samples-column/8-pipeline-result-table additions, all need to land *with* P0b — otherwise they require a second schema migration cycle)

This is a **design + schema-spec phase**. Implementation of the deletion logic lands in P0c. Implementation of BYOP infrastructure lands in P0f. Implementation of eukaryotic pipelines lands in Phase 28. But the schema decisions for all three land here.

### Design tasks

- [ ] **B-CARE-3-DESIGN**: Write `docs/architecture/sovereignty-compliant-deletion.md` covering:
  - [ ] `samples.deletion_status` enum: `ACTIVE | DELETION_REQUESTED | TOMBSTONED | VACUUMED`
  - [ ] State machine — who can request, who can approve, what triggers vacuum
  - [ ] Tombstone vs vacuum distinction — tombstone seals derivative rows, vacuum physically removes content
  - [ ] What gets vacuumed: file URIs in samples, GCS/MinIO objects, `pipeline_results.result_data` JSONB, cached intermediate artifacts, dataset memberships
  - [ ] What survives vacuum: audit log records of *what happened* (sample existed, was tombstoned at T1, vacuumed at T2 by user U), but NOT the deleted content itself
  - [ ] Vacuum cadence: configurable per operator policy; Scenario T defaults to 24 hours; other scenarios may default to 30 days
  - [ ] Derivative-analysis policy: cluster recompute (Scenario T default) vs cluster-with-asterisk (other scenarios) vs mark-stale-and-recompute-on-schedule
  - [ ] Already-published handling: pre-publish CARE confirmation checklist; "previously published" tag persists past vacuum; cannot retract from external party but system is honest about what's still in the wild
  - [ ] Federation propagation requirements (deferred to B-CARE-4 implementation): tombstone events pushed to peers, signed receipts, SLA, non-compliance flagging
  - [ ] Auth model: who can request deletion (sample submitter? lab director? platform admin?), who must approve (defaults: lab director for own-lab samples; platform admin for cross-lab; Tribal authority designee for Scenario T)
  - [ ] Edge cases: deletion during pipeline run (cancel pipeline?), deletion during pending submission to NCBI (block submission), deletion of sample that's part of an active outbreak investigation (require override)

- [ ] **Schema constraints from this design** that P0b must honor:
  - [ ] `samples.deletion_status` column with the 4-value enum
  - [ ] `samples.deletion_requested_at`, `deletion_requested_by_user_id`, `deletion_reason` columns
  - [ ] `samples.tombstoned_at`, `vacuumed_at` timestamp columns
  - [ ] `audit_log.event_type` enum extension: `sample_deletion_requested`, `sample_tombstoned`, `sample_vacuumed`
  - [ ] `pipeline_results` rows need a `tombstoned` boolean (cheaper than chasing every JSONB blob to mark it)
  - [ ] Foreign key from `pipeline_results.sample_id` should NOT cascade-delete on sample deletion (we want to keep tombstone records; the actual JSONB content is what gets vacuumed)

- [ ] **Implementation handoff to P0c**: docs/architecture/sovereignty-compliant-deletion.md is the spec for the implementation work in P0c. Tagged in P0c work as `B-CARE-3` (the actual implementation, after schema is in place).

### Schema additions for BYOP + eukaryotic pathogen support (must land with P0b)

These are not separate design work — the design exists in `jackpot_byop_and_eukaryotic_design.md`. They are **schema migration items** that must land in the same P0b migration cycle as the sovereignty additions and the existing v5.0 plan. Splitting them into a later migration creates double-migrate operator churn.

- [ ] **B-BYOP-9** Add `byop_pipelines` table per `jackpot_byop_and_eukaryotic_design.md` §7. Includes 27 columns covering manifest content, source type, lifecycle status, validation/sandbox logs, license, citation, cost estimate. Plus 4 new enums: `PipelineEngineEnum`, `PipelineSourceTypeEnum`, `PipelineStatusEnum`, `DataTypeEnum`. (1 session, P0b)

- [ ] **B-BYOP-9b** Add `byop_pipeline_id` and `byop_pipeline_version` foreign-key columns to existing `pipeline_results` table. (Half session, P0b — bundle with B-BYOP-9.)

- [ ] **B-EUK-1** Add ~25 OrganismNameEnum values for eukaryotic pathogens per `jackpot_byop_and_eukaryotic_design.md` §12.1: 6 *Plasmodium*, 6 *Leishmania*, 5 *Trypanosoma*, 5 *Schistosoma*, 7 STH, 3 filarial, 4 protozoa (*Crypto*/*Giardia*), 3 *Toxo*/*Entamoeba*. Plus new `ParasiteDevelopmentalStageEnum` and `SamplePreservationMethodEnum`. Plus new `samples` columns: `parasite_developmental_stage`, `sample_preservation_method`, `parasitemia_percent`, `multiplicity_of_infection`, `coinfection_organisms`. (1 session, P0b)

- [ ] **B-EUK-2** Add 8 new pipeline-result tables per `jackpot_byop_and_eukaryotic_design.md` §12.3: `plasmodium_drug_resistance_results`, `leishmania_typing_results`, `trypanosoma_typing_results`, `schistosoma_typing_results`, `helminth_drug_resistance_results`, `filarial_typing_results`, `cryptogiardia_typing_results`, `toxo_entamoeba_typing_results`. Plus supporting enums: `TcDTUEnum`, `GiardiaAssemblageEnum`, `ToxoClonalLineageEnum`, `EhVsEdEnum`, `WolbachiaStatusEnum`, `ResistanceCallEnum`. (1-2 sessions, P0b)

- [ ] **B-EUK-3** Update `validator.py` for eukaryotic-aware tier rules: new tier-2 fields (developmental stage, preservation method), new tier-3 fields (parasitemia, MOI, coinfection). Update `compute_surveillance_relevant()` to include eukaryotic pathogens by default. (1 session, P0b — bundle with B-EUK-1.)

### Phase 24.5 success criterion

- [ ] `docs/architecture/sovereignty-compliant-deletion.md` exists, is reviewable
- [ ] P0b schema design has accommodated the sovereignty columns + enum extensions (sovereignty block above)
- [ ] P0b schema design has accommodated `byop_pipelines` table, `pipeline_results` FK, eukaryotic OrganismNameEnum additions, eukaryotic samples columns, 8 eukaryotic pipeline-result tables, and supporting enums (BYOP/eukaryotic block above)
- [ ] Implementation tasks are queued: `B-CARE-3` for P0c (sovereignty deletion), `B-BYOP-1` through `B-BYOP-10` for P0f (BYOP infrastructure), `B-EUK-PLAS-*` through `B-EUK-TOXO-*` for Phase 28 (default eukaryotic pipelines)

**Effort:** 1 session for the sovereignty design doc + 1-2 sessions for the BYOP + eukaryotic schema migration work + half a session of P0b integration discussion. Total: 3-4 sessions for Phase 24.5.

**Phase placement justification:** All these schema decisions must be locked before P0b touches the schema. Doing them now means P0b is one migration, not three. Implementation work for the deletion logic, BYOP infrastructure, and default eukaryotic pipelines all happens in later phases (P0c, P0f, Phase 28 respectively) — but the *schema* lands in P0b alongside the existing v5.0 work.

---

## Phase 24.7 — P0f BYOP Infrastructure

**Why this phase exists:** BYOP (Bring Your Own Pipeline) infrastructure is the prerequisite for shipping default eukaryotic pathogen pipelines (Phase 28) AND for any operator wanting to register a custom workflow. It can't wait for P1 because eukaryotic coverage depends on it. It can't land in P0b because that's schema-only. P0f sits between P0e (where `jackpot init` becomes real and operator config is structured) and P0b/c (multi-tenancy schema + middleware), so BYOP allowed-registries / allowed-licenses / sandbox-resource-limits are install-time questions that `jackpot init` can prompt for.

**Source:** `jackpot_byop_and_eukaryotic_design.md` Part I (Sections 1-10). Schema migration items already covered in Phase 24.5 (B-BYOP-9, B-BYOP-9b).

**Phase placement justification:** P0e finishes the install-CLI work (operator config gets structured). P0f adds BYOP infrastructure that uses that operator config. Then P0b/c handles multi-tenancy schema + middleware. Then P1 handles operator-type configurability of the now-real BYOP system.

### N. BYOP architecture (overview §1-10 of `jackpot_byop_and_eukaryotic_design.md`)

```text
[ ] B-BYOP-1   Implement jackpot-pipeline.yaml manifest schema. Create
               schema/byop-pipeline-manifest.schema.json. Document under
               docs/byop/manifest.md. Specifies the 9-section YAML format:
               api_version, kind, metadata, engine, applicability,
               resources, reference_data, containers, inputs, outputs,
               permissions, cost. (1-2 sessions, P0f start)

[ ] B-BYOP-2   Implement backend/services/byop_validator.py — Stage 1
               static validation. Per-engine syntax checks (nextflow
               inspect, snakemake --lint, miniwdl check, bash -n / python
               -c), container resolution (registry reachability, tag
               existence, digest verification), reference data resolution
               (HTTP HEAD + checksum), license compatibility (SPDX
               against operator allowlist), permissions sanity (egress
               allowlist, GPU availability, internet_required vs
               Scenario T policy). (3-4 sessions, P0f)

[ ] B-BYOP-3   Implement backend/services/byop_sandbox.py — Stage 2
               sandbox dry-run with isolation. Per-engine dry-run
               mechanic: nextflow -stub-run, snakemake -n,
               miniwdl --task-only-resources, manifest engine via
               JACKPOT_DRY_RUN=1 env var with 60s fallback timeout.
               Kubernetes-namespace isolation for cloud, Docker-network
               isolation for local. Egress restricted to operator
               allowlist. 5-minute hard timeout. 2 CPU / 4 GB RAM /
               10 GB storage cap. Synthetic test inputs from
               backend/test_data/byop_sandbox/. (1 week, P0f — most
               complex item in the phase)

[ ] B-BYOP-4   Implement backend/routers/byop.py — full CRUD API.
               POST /api/v1/byop/pipelines (register), GET (list),
               GET /{id} (detail), PATCH /{id}, POST /{id}/revalidate,
               POST /{id}/deactivate, DELETE /{id} (move to ARCHIVED),
               GET /{id}/manifest, GET /{id}/validation,
               GET /api/v1/byop/manifest-schema,
               GET /api/v1/byop/test-data. Existing
               /api/v1/pipelines/launch accepts byop_pipeline_id
               alongside pipeline_zoo_id. (2-3 sessions, P0f)

[ ] B-BYOP-5   Implement engine launchers — 4 sub-items in parallel.
               (a) backend/services/nextflow_launcher.py — harden
                   existing path, auto-inject -weblog, enable -resume
                   with JACKPOT-managed work directory.
               (b) backend/services/snakemake_launcher.py — new.
                   Read Snakefile, resolve singularity:/container:/
                   conda: directives, wrap with event-streaming script
                   that polls --report JSON every 30s.
               (c) backend/services/wdl_launcher.py — new. Support
                   both Cromwell (heavyweight) and miniwdl (lightweight)
                   via JACKPOT_WDL_BACKEND. Populate inputs.json from
                   manifest. Poll Cromwell metadata API or parse
                   miniwdl structured logs.
               (d) backend/services/manifest_launcher.py — new.
                   Docker run wrapper for the manifest engine. Single
                   container, single command, structured timing and
                   exit-code event emission.
               (2-3 sessions per launcher = 1.5-2 weeks total, P0f)

[ ] B-BYOP-6   Implement backend/services/byop_quarterly_revalidation.py
               background job. Re-runs Stage 1 + Stage 2 against
               registered pipelines on configurable cadence (default
               90 days) to catch silently-broken upstream containers
               or moved Git refs. Failed re-validation transitions
               pipeline to DEACTIVATED with notification. (1 session, P0f)

[ ] B-BYOP-7   Implement Streamlit BYOP registration wizard (new page).
               6-step wizard: source type → source details → manifest
               preview → validation status (live updates via polling)
               → sandbox status → activated. Per-source-type forms
               (public Git, private Git with deploy key gen, tarball
               upload, Docker image). (2-3 sessions, P0f)

[ ] B-BYOP-8   Implement Streamlit BYOP catalog tab on the Pipelines
               page. List registered BYOP pipelines with status badges,
               filter by engine/organism/status, link to detail view.
               Sample-detail-page launch dropdown shows BYOP pipelines
               whose applicability.organism_names matches the sample's
               organism. (1-2 sessions, P0f)

[ ] B-BYOP-10  Implement BYOP telemetry — aggregated success rate,
               walltime, peak memory, cost per run for each registered
               pipeline. Auto-deactivate pipelines whose success rate
               drops below operator-configured threshold (default 50%)
               with platform admin notification. (1-2 sessions, P0f)
```

### Phase 24.7 / P0f success criterion

- [ ] All 4 engine types (Nextflow, Snakemake, WDL, manifest) can register a pipeline through the API
- [ ] Two-stage validation gates work end-to-end on a real test pipeline per engine
- [ ] Streamlit registration wizard works for all 4 source types
- [ ] BYOP catalog tab shows registered pipelines correctly
- [ ] At least one example BYOP pipeline per engine type is documented and tested
- [ ] Quarterly revalidation job runs on schedule
- [ ] Telemetry surface in catalog UI

**Total effort:** ~3-4 weeks of full-time engineering work, parallelizable across 2-3 contributors.

---

## Phase 25 — Month 3 Stretch Goals (Tracked, Not Scheduled)

- [ ] Streamlit admin pages: `lab_director.py`, `platform_admin.py`,
      `archive_requests.py`, `billing.py`
- [ ] JupyterHub workspace with all three profiles (Analyst,
      Bioinformatician, Developer)
- [ ] BYOP full wire-up: fetch `nextflow_schema.json` from registered
      repo, validate, enable launching — *largely superseded by Phase 24.7 / P0f (BYOP infrastructure with multi-engine support, manifest schema, two-stage validation). This Phase 25 stretch goal becomes "remaining UI polish" once P0f lands.*
- [ ] GCP production deployment
- [ ] `ncbi_submissions` router (TOSTADAS integration) — *see also `B-LOC-1` Phase 26 (lift Loculus `ena-submission/` as the ENA broker, AGPL-3.0 → AGPL-3.0 frictionless)*
- [ ] `datasets` router (table exists, router stub)
- [ ] `archive_requests` router
- [ ] `saved_searches` router
- [ ] `notifications` router (full — currently placeholder in UI)
- [ ] Remaining parsers if any pipelines were deferred
- [ ] External database search (`/api/v1/external-search/` — NCBI, ENA,
      GISAID proxy) — *see also `B-EB-3` Phase 26 (daily SRA auto-scan pipeline pattern from EnteroBase, complementary to one-shot search)*
- [ ] Re-enable detect-secrets in pre-commit
- [ ] Playwright end-to-end UI tests
- [ ] US-states controlled vocabulary for `collection_location_state`
- [ ] Retire `jackpot-frontend` repo (vestigial stub — real UI lives
      in `jackpot-backend/frontend/`)

## Phase 26 — Pathoplexus/Loculus Comparative Analysis Backlog (Tracked, Not Scheduled)

**Source:** `jackpot_pathoplexus_loculus_overview.md` (April 2026 working session). Cross-references to overview document sections in parentheses. Full effort and phase metadata for each item lives in overview Section 16.10. Items refining or decomposing existing Phase 25 / Year 2 entries are marked `[refines #X]`.

### A. Loculus code adoption (overview §11 A1-A6, §12.1a)

- [ ] **B-LOC-1** Lift Loculus `ena-submission/` as JACKPOT ENA broker. AGPL-3.0 → AGPL-3.0. (1-2 sessions, P0d or after)
- [ ] **B-LOC-2** Lift Loculus `ingest/Snakefile` clean-room as `pipelines/insdc-ingest/`. NCBI Datasets CLI based. (2-3 sessions, P0d)
- [ ] **B-LOC-3** Add `backend/routers/preprocessing.py` implementing the Loculus `/extract-unprocessed-data` and `/submit-processed-data` HTTP contract. (2-3 sessions, P1)
- [ ] **B-LOC-4** Update `ValidationResult` to Loculus structured error/warning schema (FieldRef, ProcessingIssue, validator_version). (1 session, any)
- [ ] **B-LOC-5** Switch CSV ingest to NDJSON streaming (memory O(N) → O(1)). (1 session, any)
- [ ] **B-LOC-6** Add `validator_version` and reprocessing background job. Modeled on Loculus `pipelineVersion` auto-promotion. (1-2 sessions, with B-LOC-3)
- [ ] **B-LOC-7** Add `jackpot submit/revise/revoke` CLI commands modeled on Loculus `cli/`. (2 sessions, P0e)

### B. NCBI integrations (overview §12.0, §16.4)

- [ ] **B-NCBI-1** BigQuery JOIN for NCBI Pathogen Detection — surface PDS# cluster IDs and MicroBIGG-E AMR results in samples table. (2 sessions, post-staging-cutover)
- [ ] **B-NCBI-2** hAMRonization output mandate for all AMR pipelines in the zoo. (1 session per pipeline, pipeline zoo work)
- [ ] **B-NCBI-3** Mint stable JACKPOT cluster accessions (JKPT-prefixed, versioned) for any cgMLST/SNP cluster. Persist tree representations in newick + JSON. (1 week, Year 2 with cgMLST clustering)

### C. Governance & Pathoplexus UI patterns (overview §12.1)

- [ ] **B-GOV-1** Create `governance/` directory with charter.md, coi-policy.md, jurisdiction-and-data-residency.md, benefits-sharing-framework.md, access-grievance-procedure.md, platform-shutdown-data-portability-plan.md, advisory-board.md. Modeled on Pathoplexus governance docs. (3-5 hours of writing, P0d alongside monorepo)
- [ ] **B-PPX-1** Adopt per-sample OPEN/RESTRICTED radio button on Streamlit upload page. Schema already supports it; just wire UI. (half a session, any)

### D. Pathogenwatch (overview §12.2a, §16.2)

- [ ] **B-PWATCH-1** Pathogenwatch results-pull for bacterial samples (Salmonella, Klebsiella, Mtb, Neisseria). Push assembly via API, pull cgMLST/MLST/AMR/SNP-tree results back into pipeline_results. (3-4 sessions, Year 2)
- [ ] **B-PW-1** Add `pathogenwatch-oss/speciator` as Level-1 pipeline-zoo entry — Mash-based species ID. (1 session, any pipeline-zoo work)
- [ ] **B-PW-2** Add `pathogenwatch-oss/mlst` as Level-1 zoo entry — MLST/cgMLST per-pathogen schemes. (1-2 sessions, any pipeline-zoo work)
- [ ] **B-PW-3** Vendor `pathogenwatch-oss/amr-libraries` as JACKPOT reference data under `reference-data/amr-libraries/`. (1 session, P0d)
- [ ] **B-PW-4** Add seroba (pneumococcus), vista (cholera), inctyper (plasmid Inc) as zoo entries when relevant pathogens come into scope. (1 session each)
- [ ] **B-PW-5** Phylocanvas + Leaflet + metadata-table tri-pane for collection visualizations. (1-2 weeks, Year 2 React migration) `[refines Phase 25 / Year 2 #5]`
- [ ] **B-PW-6** Add `/priority-pathogens` dashboard page mapping WHO BPPL 2024 to JACKPOT's organism enum. (1 session, any)

### E. GenSpectrum / LAPIS (overview §12.2c, §16.1)

- [ ] **B-LAPIS-1** Expose LAPIS-compatible REST endpoint for JACKPOT viral data. (1-2 weeks, Year 2)
- [ ] **B-GS-1** Embed GenSpectrum `dashboard-components` for viral variant tracking when JACKPOT migrates from Streamlit to React. AGPL-3.0 → AGPL-3.0. (3-5 sessions, Year 2 post-Streamlit migration)
- [ ] **B-GS-2** Make all JACKPOT search/filter/dashboard state URL-encoded via `st.query_params`, so any view is shareable. (1-2 sessions across all Streamlit pages, any)

### F. EnteroBase (overview §12.2b, §16.3)

- [ ] **B-EBASE-1** EnteroBase HierCC pull for Salmonella and E. coli. (2-3 sessions, Year 2) `[refines Phase 25 / Year 2 #6 — lightweight pull path]`
- [ ] **B-EB-2** Implement native hierarchical clustering codes (JACKPOT-HC) for any cgMLST-typed bacterial sample. 11 distance thresholds matching EnteroBase HierCC. (2-3 weeks, Year 2) `[native-computation companion to #6; basis for federation]`
- [ ] **B-EB-3** Add `pipelines/insdc-daily-scan/` — daily Snakemake job that scans NCBI SRA for new sequences matching the operator's organism enum, auto-ingests via B-LOC-2. Operator-opt-in. (1 week, Year 2) `[continuous-scan companion to Month 1 #4]`

### G. BV-BRC (overview §16.5)

- [ ] **B-BVBRC-1** Add a fast-track queue lane for jobs <30s (BLAST, single-genome typing) separate from the long-running pipeline lane. Modeled on BV-BRC's two-tier queue. (2-3 sessions, when scale demands it — Year 2+)
- [ ] **B-BVBRC-2** Add explicit "publish" ceremony when transitioning sample from DISCOVERABLE to PUBLIC — generates citation block, mints persistent identifier, snapshots metadata. (1-2 sessions, any)

### H. Solu (overview §16.6)

- [ ] **B-SOLU-1** Design a "rapid triage" pipeline that runs species ID + AMR + nearest-neighbour phylogeny in <5 minutes for single-sample uploads. "Is this an outbreak strain we've seen?" — yes/no plus context. (2-3 weeks, Year 2)
- [ ] **B-SOLU-2** Add a continuous-surveillance background job that re-runs cluster computation on all samples of an organism when new samples arrive. Updates `samples.cluster_id`; preserves immutable historical pipeline_results. (1 week, Year 2)
- [ ] **B-SOLU-3** Add `docs/trust.md` (later promoted to `trust.jackpot.health` subdomain) documenting security practices, data residency, encryption, audit log, DLP, scrubber, deletion lifecycle. (4-6 hours of writing, with B-GOV-1)

### I. RT-MetA (overview §12.3, §16.7)

- [ ] **B-RTMA-1** Reach out to the RT-MetA team about collaboration on offline-capable architecture. They're IPSN-funded and explicitly looking for collaborators. (1 email + one call, now)
- [ ] **B-RTMA-2** Design offline-first mode for Scenario A — SQLite-only backend, optional sync-when-online to a parent instance, conflict-resolution policy. (2-3 weeks design + more for implementation, Year 2) `[architectural companion to Phase 25 / Year 2 #7 hub-and-spoke federation]`
- [ ] **B-RTMA-3** Adopt RT-MetA's untargeted metagenomics framework as a JACKPOT pipeline-zoo entry, paired with nf-core/taxprofiler. (4-6 weeks, Year 2+)

### J. GISAID-derived (overview §16.8)

- [ ] **B-GISAID-1** When exporting a dataset, auto-generate a structured Acknowledgments block citing each originating lab, sample IDs, and submission dates. Format aligned with Nature/PHA4GE recommended citation conventions. (1-2 sessions, any)

### Phase 26 quick-win priority order (from overview §16.9)

If grabbing low-effort high-ROI items between sprints:

1. **B-PW-1** Speciator (1 session) — bacterial species ID is foundational
2. **B-PW-2** MLST/cgMLST (1-2 sessions) — closes a major bacterial gap
3. **B-PW-3** AMR libraries vendored (1 session) — curated reference data
4. **B-GS-2** URL-encoded query state (1-2 sessions) — shareable views
5. **B-GISAID-1** Auto-Acknowledgments on export (1-2 sessions) — submission-incentive loop

---

## Phase P0f — File references redesign

The mental-model shift: JACKPOT is a metadata database that knows where
data lives, not a storage system that holds it. Pointing JACKPOT at a
file path or URI registers the file; it does **not** copy. This phase
adds the `file_references` table, the `FileStorageState` enum, the
cheap-fingerprint + lazy-SHA-256 dedup model, the periodic verification
job, and the API/UI surfaces that make storage state explicit to users.

Pairs with P0g (execution profiles) — together they unlock scenario B
+ Slurm and scenario C without any FASTQ duplication.

**Critical Rule precedent:** Critical Rule 20 (`file_detector.py` is
the sole owner of file type and naming logic) stays. This phase does
not introduce parallel file-type logic anywhere; `file_detector.py` is
called once per file_reference at registration.

### F-1: Schema design — `FileStorageState` enum + `SampleFile` extensions (COMPLETE 2026-05-03)

**Design shift (locked in during F-2 prep, recorded in Critical Rule 58):**
the existing `sample_files` table is extended in place. There is no parallel
`file_references` class — `SampleFile` (uri-keyed) is the dedup primitive,
`content_hash` is the logical key. File role is encoded by the existing
`read_direction` + `library_layout` + `paired_file_id` fields; no `role`
enum is introduced (would create two sources of truth).

- [x] Add `FileStorageState` enum to `schema/schema/jackpot_schema.yaml`
      with values: `EXTERNAL`, `MANAGED`, `MIRRORED`, `STAGED`, `BROKEN`.
- [x] Extend `SampleFile` class with 12 new slots: `content_hash`,
      `head64k_hash`, `tail64k_hash`, `storage_state` (default
      `EXTERNAL`), `alternate_uris` (multivalued), `first_seen_at`,
      `last_verified_at`, `last_verification_status`, `retention_policy`
      (default `STANDARD`), `original_uri` (MIRRORED only),
      `staged_for_run_id` (STAGED only), `updated_at` (DB-trigger
      maintained). Existing slots untouched.
- [x] Regenerate `backend/backend/models_generated.py` (Pydantic v2);
      apply boolean-keyword + trailing-newline patch per Rule 20.
- [x] Verify `from backend.models_generated import SampleFile,
      FileStorageState` works in api container; all 5 enum values and
      12 new fields present.
- [x] Test suite still 891 passing, 1 skipped, 0 failed.
- [x] Merged via PR #1 (squash commit `4504c21`).
- [ ] Defer: `samples.fastq_r1_uri`/`fastq_r2_uri`/`long_read_uri`/
      `assembly_uri` deprecation — moved to a follow-up after F-3 lands
      and the convenience columns can be safely repointed.
- [ ] Defer: `schema/schema/templates/` TSV/Excel template regeneration
      — not required for F-1; will be revisited if F-6 changes the
      user-facing CSV columns.

### F-2: Alembic migration (COMPLETE 2026-05-02)

Shipped as `34382b7b82c6_add_file_references.py` extending the existing
`sample_files` table rather than creating a new `file_references` table
(see F-1 design-shift note). Critical Rules 57-60 added in the same
phase to lock in the dedup-primitive + EXTERNAL-default model.

- [x] New revision `34382b7b82c6_add_file_references` chained after
      `00b4bd99ddee`.
- [x] Add `file_storage_state` ENUM type and 12 new columns on
      `sample_files`: `content_hash`, `head64k_hash`, `tail64k_hash`,
      `storage_state`, `alternate_uris`, `first_seen_at`,
      `last_verified_at`, `last_verification_status`, `retention_policy`,
      `original_uri`, `staged_for_run_id`, `updated_at`.
- [x] UNIQUE partial index on `content_hash` (where non-null);
      composite fingerprint index on `(file_size_bytes, head64k_hash,
      tail64k_hash)` for the pre-content-hash dedup path; verification
      hot-path index on `(storage_state, last_verified_at)` for
      EXTERNAL/MIRRORED.
- [x] CHECK constraints: managed/staged require `file_size_bytes`;
      mirrored requires `original_uri`; staged requires
      `staged_for_run_id`; retention_policy is one of STANDARD,
      LONG_TERM, EPHEMERAL.
- [x] `updated_at` BEFORE-UPDATE trigger.
- [x] Backfill: `head64k_hash` and `tail64k_hash` seeded from existing
      `md5` for legacy rows.
- [x] `alembic upgrade head` and `downgrade -1` both round-trip cleanly.
- [ ] Defer: staging-clone test — pending the staging environment work
      from Phase 19 / Q-5.

### F-3: Cheap fingerprint at ingest

- [ ] New module `backend/file_fingerprint.py` with function
      `cheap_fingerprint(uri) -> tuple[int, str, str]` returning
      `(size_bytes, head64k_sha256, tail64k_sha256)`.
- [ ] Implementation reads the first 64 KB and last 64 KB only — for
      `file://` paths via `os.open`/`os.pread`, for `gs://` and `s3://`
      via Range requests through `backend/storage.py`, for `sra://` by
      delegating to NCBI metadata API rather than downloading.
- [ ] Handle gzip/BGZF transparently — fingerprint compressed bytes,
      not decompressed content (cheaper, content-hash-stable as long
      as compression is deterministic).
- [ ] Wire into `backend/ingest/upload.py`,
      `backend/ingest/csv.py`, `backend/ingest/globus.py` to compute
      fingerprint at registration time, store on the `file_references`
      row, and check for an existing row with the same fingerprint
      before INSERTing a new one.
- [ ] Dedup behavior: if fingerprint matches an existing row, link the
      new `sample_files` row to the existing `file_reference` and
      append the new URI to `alternate_uris` if different.

### F-4: Background job — full SHA-256

- [ ] New APScheduler job `compute_full_content_hash` that scans for
      `file_references` rows with `content_hash IS NULL` and computes
      the full SHA-256, updating the row and reconciling any
      fingerprint-collision dedup that cheap fingerprinting missed.
- [ ] Streaming hash for large files — never `.read()` the whole thing
      into memory; use 8 MB buffers.
- [ ] Throttle: max one file at a time, max 30 minutes per run; pick
      up where it left off on next tick.
- [ ] Job interval: every 5 minutes in production, configurable via
      `Settings.full_hash_interval_seconds`.
- [ ] Job is no-op for `EXTERNAL` files on slow networks if the
      operator sets `Settings.skip_remote_full_hash=true` (scenario B
      with cluster-mounted storage).

### F-5: Periodic verification job

- [ ] New APScheduler job `verify_file_references` that re-stats every
      `EXTERNAL` and `MIRRORED` file_reference, updating
      `last_verified_at` and `last_verification_status`.
- [ ] If file is missing or unreadable, transition state to `BROKEN`
      and `log_audit()` the transition.
- [ ] If file is present but size has changed, transition to `BROKEN`
      and emit a notification — content under the URI changed
      out-of-band, samples may be referencing different data than
      registered.
- [ ] Job interval: every 24 hours by default, configurable.
- [ ] Skip `MANAGED` and `STAGED` files (JACKPOT owns them, no
      external drift possible).
- [ ] Skip `BROKEN` files (terminal state until operator intervention).

### F-6: Update ingest API — `EXTERNAL` is the default

- [ ] `backend/ingest/upload.py`: keep current upload-and-stage path
      for browser uploads (laptop scenario A small files), but mark
      result as `MANAGED` since the user explicitly uploaded.
- [ ] `backend/ingest/csv.py`: when CSV row contains a URI or path,
      register as `EXTERNAL` by default. Add column `storage_intent`
      to the CSV template — values `EXTERNAL` (default), `MANAGED`
      (operator wants JACKPOT to copy), `MIRRORED` (copy but track
      origin).
- [ ] `backend/ingest/globus.py`: register as `EXTERNAL` referencing
      the Globus collection URI. Pipeline staging will pull data via
      Globus on demand.
- [ ] New endpoint `POST /api/v1/ingest/register` for the path-only
      registration flow — no file upload, just metadata + URI(s).
- [ ] Update `backend/responses.py` to include `storage_state` in the
      ingest success response so users see "registered" vs "uploaded"
      explicitly.

### F-7: Update `pipeline_results_loader.py` for output ownership

- [ ] Pipeline outputs default to `MANAGED` — the pipeline produced
      them under JACKPOT-controlled paths, JACKPOT owns the lifecycle.
- [ ] Pipeline inputs are not transitioned by running a pipeline — an
      `EXTERNAL` input file remains `EXTERNAL` after a pipeline run
      reads it.
- [ ] When a pipeline emits a derived file that should be linked to a
      sample (e.g., trimmed FASTQ, assembly), create a new
      `file_reference` row with `storage_state=MANAGED` and a new
      `sample_files` row with the appropriate role.
- [ ] Maintain Critical Rule: `pipeline_results` rows remain immutable
      and append-only — every run gets a new INSERT.

### F-8: Pre-pipeline-launch verification

> **Design shift (vs. original draft):** F-8 is a fast *read* of the
> verification job's last-known state, not a synchronous re-stat at
> launch time. Per-file network round-trips (HEAD/stat/metadata-fetch)
> would push 100ms × N file latency onto every launch and make batch
> launches unusable. Instead, F-5 (`verify_file_references`) is the
> source of truth for `sample_files.storage_state`, and F-8 trusts it.
> Operators wanting stronger guarantees can shorten
> `Settings.verification_interval_seconds` or trigger
> `POST /api/v1/admin/jobs/verify_file_references/run` before a critical
> launch.

- [x] In `backend/routers/pipelines.py` `POST /launch`, after sample
      resolution and access checks, query `sample_files` for any row
      with `storage_state='BROKEN'` belonging to a requested sample.
- [x] If any are `BROKEN`, refuse the launch with `400 BROKEN_INPUTS`
      and surface a `broken_files` list (`sample_files_id`,
      `sample_id`, `uri`, `last_verification_status`) plus a
      `suggestion` field telling the user how to unblock.
- [x] Add `BROKEN_INPUTS` to the standard error codes table in
      `docs/CLAUDE.md` and the F-8 detail to `spec.md`.
- [x] Integration test: pipeline launch refuses to start with a
      `BROKEN` input.

### F-9: `jackpot files promote` CLI command

- [ ] Add subcommand under the `jackpot` CLI (lives in `cli/jackpot/`)
      that calls a new endpoint `POST /api/v1/files/{file_ref_id}/promote`.
- [ ] Promotion modes: `--to managed` (copy to JACKPOT-owned storage,
      transition state), `--to mirrored` (copy but keep external
      reference), `--from staged --to managed` (preserve a STAGED
      file beyond run end).
- [ ] Bulk variant: `jackpot files promote --project <id> --to managed`
      promotes every file referenced by samples in the project.
- [ ] Backend endpoint kicks off a background job for the actual copy;
      returns 202 Accepted with a job ID for status polling.

### F-10: UI surfacing of storage state

- [ ] In `frontend/pages/my_samples.py` and the search results table,
      add a column showing storage state with color coding —
      `EXTERNAL` (gray), `MANAGED` (green), `MIRRORED` (blue),
      `STAGED` (yellow), `BROKEN` (red).
- [ ] On the sample detail page, show the full file_reference for each
      sample_file: state, primary URI, alternate URIs, content hash,
      last verified timestamp, and a "Promote to managed" button when
      applicable.
- [ ] On ingest pages (`upload.py`, `data_entry.py`), show a banner
      explaining "JACKPOT will register this file in place — it will
      not be moved or copied. To make a managed copy, set Storage
      Intent to Managed."
- [ ] Broken files surface a prominent banner with options: re-locate
      (provide a new URI), re-upload, or mark the sample inactive.

### F-11: Tests

- [ ] Unit tests for `cheap_fingerprint()` covering local files, gzip,
      BGZF, gcs:// (mocked), s3:// (mocked), sra:// (mocked).
- [ ] Unit tests for the dedup path — same fingerprint produces one
      `file_reference` row referenced by multiple samples.
- [ ] Integration tests for the ingest endpoints covering all three
      storage intents.
- [ ] Integration test for the verification job marking a file
      `BROKEN` when it disappears from disk between registrations.
- [ ] Integration test for pipeline-launch refusing to launch with a
      `BROKEN` input.
- [ ] End-to-end test in `tests/e2e/` that registers an `EXTERNAL`
      file, runs a fixture pipeline against it, and verifies no copy
      was made (file_reference still `EXTERNAL`, only the output is
      `MANAGED`).
- [ ] Verify all 477 existing tests still pass; add new tests to keep
      coverage above 86.99%.

### F-12: Docs

- [ ] Add `docs/file_references.md` explaining the storage-state model
      to operators and end users.
- [ ] Update `spec.md` API conventions section with the new
      `/api/v1/ingest/register` and `/api/v1/files/{id}/promote`
      endpoints.
- [ ] Add CLAUDE.md Critical Rule: "JACKPOT does not copy data on
      ingest. The default storage_state is `EXTERNAL`. Copies happen
      only via explicit `MANAGED` intent at ingest, via pipeline
      output materialization, via `jackpot files promote`, or via
      pipeline staging (which is auto-cleaned)."
- [ ] Update `local_test_checklist.md` with file-reference verification
      steps.

---

## Phase P0g — Execution profiles

Executor selection becomes a per-pipeline-run choice driven by
operator-configured profiles, not a deployment-time decision. The same
JACKPOT instance can submit one run to local Nextflow, the next to a
Slurm cluster, the next to GCP Batch — all using the same pipeline
definitions in the zoo.

This phase ships the schema, the profile templates, the
`nextflow.config` generation, the launch-time profile selection, and
the `JACKPOT_WORK_DIR` abstraction. The actual Slurm-specific work
lands in P0h; this phase makes that work possible.

### G-1: Schema design — `execution_profiles` class (COMPLETE 2026-05-04)

Shipped in PR #21 (commit `a682788`).

- [x] Add `execution_profiles` class to
      `schema/schema/jackpot_schema.yaml` with fields: `profile_id`
      (UUID, PK), `name` (unique within deployment), `executor_type`
      (enum: `LOCAL`, `SLURM`, `PBS`, `LSF`, `GCP_BATCH`, `AWS_BATCH`,
      `KUBERNETES`), `container_engine` (enum: `DOCKER`, `APPTAINER`,
      `SINGULARITY`, `NONE`), `work_dir`, `config_overrides` (JSONB
      for executor-specific fields like Slurm account/partition/QOS,
      GCP project/region, K8s namespace), `is_default`, `created_by`,
      `created_at`, `active`.
- [x] Add `pipeline_default_profile` association class with fields:
      `pipeline_id` (FK to pipelines), `profile_id` (FK), `priority`
      (lower = preferred default if multiple match).
- [x] Update LinkML generation; verify Pydantic v2 models compile.

### G-2: Alembic migration (COMPLETE 2026-05-04)

Shipped as `bac8dbb11c0b_add_execution_profiles_and_.py` in PR #21
(commit `a682788`), chained after I-3a's head (`3644749bf4c6`).

- [x] New revision chained after I-3a head (P0f's revision was
      not chosen as the chain anchor — I-3a was the actual head at
      time of authoring).
- [x] Create `execution_profiles` table with `(name)` UNIQUE
      constraint at deployment scope.
- [x] Create `pipeline_default_profile` table with composite PK on
      `(pipeline_id, profile_id)` and FK cascade on profile delete.
- [x] Partial unique index `idx_execution_profiles_one_default`
      enforcing "at most one default" (`WHERE is_default = TRUE`).
- [x] CHECK constraints on `executor_type` and `container_engine`
      values matching the LinkML enums.
- [x] Seed migration: insert a `default-local` profile (strategy b —
      PL/pgSQL guard on user existence with `ON CONFLICT (name) DO
      NOTHING` for idempotency).
- [x] Verify `alembic upgrade head` from empty + downgrade.
- [x] 32 tests added (20 schema + 8 migration + 4 seed).

### G-3: Profile templates (COMPLETE 2026-05-05)

Shipped in PR #28 (commit `544c98c`).

- [x] New directory `backend/pipeline_config/profile_templates/` with
      Jinja2 templates for each executor type:
      - `local.config.j2`
      - `slurm.config.j2`
      - `pbs.config.j2`
      - `lsf.config.j2`
      - `gcp_batch.config.j2`
      - `aws_batch.config.j2`
      - `kubernetes.config.j2`
- [x] Each template renders a complete `nextflow.config` snippet
      using profile fields. Slurm template handles
      `account`/`partition`/`qos`/`time`/`memory` with sensible
      defaults that operator can override.
- [x] Container-engine-aware: when `container_engine=APPTAINER`, the
      rendered config sets `apptainer.enabled=true` and disables
      Docker; vice versa for `DOCKER`.
- [x] Templates pull common settings from
      `backend/pipeline_config/profile_templates/base.config.j2` so
      changes propagate.

### G-4: `nextflow.config` generation at launch (COMPLETE 2026-05-05)

Shipped in PR #28 (commit `544c98c`).

- [x] New module `backend/pipeline_config/profile_renderer.py` with
      function `render_nextflow_config(profile, pipeline, run_id) -> str`.
- [x] Renderer picks the right template based on
      `profile.executor_type`, fills in profile fields, layers
      pipeline-specific overrides, and writes the result to the run's
      work directory as `nextflow.config`.
- [x] Call site: launch endpoint in `routers/pipelines.py` calls the
      renderer after profile selection (via `profile_resolver.py`) and
      before the GCP-Batch / `nextflow run` invocation. Legacy
      GCP-Batch path preserved as fallback when
      `NoProfileAvailableError` raises; deletion is a follow-up after
      G-5 lands.
- [x] Generated configs stored alongside run logs for audit and
      reproducibility (extends Critical Rule 26).
- [x] 35 new tests added (17 renderer + 10 resolver + 8 launch
      integration). Cross-cutting integration tests landed at
      workspace-root `./tests/` since launch is multi-member.

### G-5: Per-pipeline default profile

- [ ] New endpoint `POST /api/v1/pipelines/{id}/default-profiles`
      to associate a profile as default for a pipeline.
- [ ] Resolution logic at launch: explicit profile in launch request
      wins, else pipeline's first matching default profile, else
      deployment's `is_default=true` profile, else error.
- [ ] Quick-fast pipelines (file detection, DLP scan, validation) get
      their default set to the deployment's `LOCAL` profile during
      seeding — they always run on the API server.
- [ ] Heavy pipelines (PHoeNIx, MIRA-NF, MycoSNP-NF, aquascope) have
      no default seeded; operator picks at launch or sets a default.

### G-6: `JACKPOT_WORK_DIR` abstraction

- [x] New `Settings.work_dir` field, peer to existing
      `Settings.storage_backend`. **(Shipped in PR #28; reads from
      `JACKPOT_WORK_DIR` env var.)** Default per scenario:
      - Scenario A: `~/.jackpot/work/`
      - Scenario B (Docker): `/srv/jackpot/work/`
      - Scenario B (Slurm): operator-provided shared filesystem
      - Scenario C: institutional shared filesystem path
      - Scenario D/E (cloud): `gs://<deployment>-jackpot-work/` or
        `s3://...`
- [x] All pipeline runs use `<work_dir>/runs/<run_id>/` as their work
      directory. Profile renderer reads `Settings.work_dir` and
      injects it into the generated `nextflow.config`. **(Shipped in
      PR #28.)**
- [ ] Work directory layout documented in `docs/work_directory.md` so
      operators understand what lives there and how to back up or
      clean it.
- [ ] Cleanup job: APScheduler task `cleanup_old_work_dirs` that
      removes `STAGED` files and entire run directories older than
      configurable retention (default 7 days, operator-configurable).

### G-7: Launch-time profile selection

- [x] Update `POST /api/v1/pipelines/{id}/launch` request body to
      accept optional `profile_name` (and `profile_id`) fields.
      **(Shipped in PR #28.)**
- [x] If omitted, resolve via the rules in G-5: pipeline's first
      matching default by priority, else deployment's default, else
      `400 NO_PROFILE_AVAILABLE`. **(Shipped in PR #28; G-5 default-
      profile association endpoint still pending.)**
- [x] If provided but the profile doesn't exist or isn't `active`,
      return `400 PROFILE_NOT_FOUND` with available profile names.
      **(Shipped in PR #28.)**
- [x] Audit action `LAUNCH_WITH_PROFILE` recorded on profile-driven
      launches. **(Shipped in PR #28.)**
- [ ] Update `frontend/pages/pipelines.py` launch UI to show a
      profile dropdown populated from `GET /api/v1/profiles/` —
      labeled with executor type and a friendly summary
      (e.g., "Slurm — mylab — apptainer"). **(Pending — depends on
      G-5 list endpoint.)**

### G-8: Cost estimation hooks for cloud profiles

- [ ] New module `backend/pipeline_config/cost_estimator.py` with a
      pluggable interface — `estimate_cost(profile, pipeline,
      sample_count) -> CostEstimate`.
- [ ] Implementations stub-only for non-cloud profiles (return
      `unknown`); concrete for `GCP_BATCH` using current Compute
      Engine + Cloud Storage pricing tables (refreshed weekly via a
      scheduled job, cached in DB).
- [ ] Launch UI shows estimate before confirmation when profile is
      cloud-based: "Estimated cost: $X (range $Y–$Z based on
      historical runs)".
- [ ] Logged on every launch for actuals-vs-estimate analysis later.

### G-9: `jackpot profiles` CLI commands

- [ ] `jackpot profiles list` — print configured profiles in a table.
- [ ] `jackpot profiles add` — interactive add of a new profile,
      prompting for executor type and the relevant fields.
- [ ] `jackpot profiles edit <name>` — update an existing profile.
- [ ] `jackpot profiles remove <name>` — soft-delete (`active=false`);
      refuses if any pipeline has it as default.
- [ ] `jackpot profiles test <name>` — submit a fixture
      single-process Nextflow job through the profile to verify it
      works end-to-end. Used by `jackpot doctor`.

### G-10: Tests

- [ ] Unit tests for the profile renderer covering each executor type
      against fixture profile data.
- [ ] Integration test: register a profile, launch a tiny pipeline
      against it, verify the generated `nextflow.config` matches
      expectations.
- [ ] Integration test for the resolution logic: explicit profile,
      pipeline default, deployment default, error cases.
- [ ] Integration test for the cleanup job — STAGED files older than
      retention disappear; MANAGED files do not.
- [ ] Coverage target: keep above 86.99%.

### G-11: Docs

- [ ] Add `docs/execution_profiles.md` explaining the profile model
      to operators with concrete examples for each executor type.
- [ ] Update `spec.md` with the new endpoints and config fields.
- [ ] Add CLAUDE.md Critical Rule: "Pipeline executor selection is
      per-run, not per-deployment. Profile resolution: explicit >
      pipeline-default > deployment-default > error."

---

## Phase P0h — Slurm executor support for scenario B (and C)

Single-lab on-prem deployments often have access to a Slurm queue —
either local on the same box, or on a department/university cluster.
This phase makes Slurm a peer of the local executor for scenario B,
and lays the cluster-side groundwork that scenario C (university
research-computing hosted) needs.

Builds on P0f (file_references — pipelines read inputs in place from
the shared filesystem) and P0g (execution profiles — Slurm is one
profile among several).

**Prerequisite for end-to-end test:** access to a real Slurm cluster.
A small institutional one or a stood-up scratch cluster on GCP/AWS
both work; CI can use a containerized SLURM (e.g., `giovtorres/slurm-
docker-cluster`) for unit-level testing.

### H-1: Slurm Nextflow config template (refines G-3)

- [ ] In `backend/pipeline_config/profile_templates/slurm.config.j2`,
      handle the full Slurm field set: `account`, `partition`, `qos`,
      `clusterOptions` (free-form sbatch flags), `time`, `memory`,
      `cpus`, and `queueSize` (max concurrent submissions).
- [ ] Default `process.executor='slurm'` and per-process `cpus` /
      `memory` / `time` from `pipeline_config/base.config.j2`,
      overridable per profile.
- [ ] Apptainer is the default container engine for Slurm profiles
      (university policy norm). Docker remains an option for lab-Slurm
      cases where the cluster allows it.

### H-2: Apptainer container engine support in pipeline zoo

- [ ] Audit each pipeline in `pipelines/` for Apptainer profile
      compatibility — most are already nf-core-standards and have it.
- [ ] For pipelines that don't, add an `apptainer` profile to their
      `nextflow.config` mirroring the existing `docker` profile but
      with `apptainer.enabled=true`, `apptainer.autoMounts=true`, and
      Apptainer-friendly cache directory.
- [ ] Document the per-pipeline container-image inventory: which OCI
      images each pipeline pulls, so operators can pre-stage SIF files
      for air-gapped clusters.
- [ ] Add a manifest file `pipelines/<name>/apptainer_images.txt` per
      pipeline listing the required OCI image references — fed to
      `jackpot images export` for pre-staging.

### H-3: Account / partition / QOS handling

- [ ] Profile fields for Slurm carry `account`, `partition`, `qos`,
      and `clusterOptions` — all optional, all rendered as `sbatch`
      flags in the generated config when present.
- [ ] For multi-tenant scenario C: the profile holds the *default*
      account, but a per-launch override field `launch_account` lets a
      lab member charge a specific grant. P0c multi-tenancy middleware
      validates the override against the user's lab memberships.
- [ ] CLAUDE.md note: profile account defaults are written by the
      operator; per-launch overrides are validated against user's lab
      memberships, never trusted blindly.

### H-4: Weblog reachability for cluster-submitted runs

- [ ] Document in `docs/slurm_executor.md` the network requirement:
      compute nodes need outbound HTTP access to the JACKPOT API's
      `/api/v1/pipelines/events` endpoint.
- [ ] If outbound is blocked (common for scenario C), provide the
      polling fallback: a sidecar process on the API server polls
      `<work_dir>/runs/<run_id>/.nextflow.log` over the shared
      filesystem and emits synthetic weblog events.
- [ ] Sidecar implementation: `backend/pipelines/log_poller.py` as an
      APScheduler job, runs every 30 seconds for active cluster runs,
      tails the log and matches Nextflow's known event patterns.
- [ ] Receiver tolerates duplicate events (idempotent on
      `(run_id, task_id, status)` tuple) so weblog and poller can
      coexist for redundancy.

### H-5: Shared-filesystem JACKPOT_WORK_DIR for cluster execution

- [ ] In Slurm profiles, `work_dir` must be a path visible to both
      the API server and the compute nodes. Profile validation at
      `jackpot profiles add/edit` time stats the path locally and
      warns if it doesn't exist or isn't writable.
- [ ] `jackpot doctor` for Slurm profiles: submits a tiny `srun
      --pty hostname` against the configured account/partition,
      verifies the work directory is reachable from the compute node.
- [ ] Document scenarios where the API server's view of the
      filesystem differs from the cluster's (NFS mount paths, etc.)
      and how to align them via Nextflow's `process.scratch` and
      `process.stageInMode`.

### H-6: Pre-pipeline-launch Slurm reachability check

- [ ] Refines F-8: when launch profile is Slurm, additionally verify
      the cluster is reachable — `sinfo` returns 0 within 10 seconds.
- [ ] If unreachable, fail the launch with a clear error and a
      pointer to `jackpot doctor`.
- [ ] Cache reachability for 60 seconds to avoid hammering `sinfo` on
      bulk launches.

### H-7: GCP Batch executor profile (stretch goal)

- [ ] Implement `GCP_BATCH` profile template under G-3 if not yet
      done.
- [ ] Required profile fields: `gcp_project`, `gcp_region`,
      `gcp_service_account`, `gcs_bucket` (for staging), `machine_type`.
- [ ] Cloud-burst-from-scenario-B story: when a Slurm queue is
      backed up, operator can switch a launch to the `gcp-batch`
      profile manually. Auto-burst (queue-depth-triggered) is
      explicitly out of scope for this phase.
- [ ] Input staging: F-7 STAGED file_references with `gs://`
      `primary_uri`, materialized at launch by copying from local
      paths to GCS, cleaned up after run completion.
- [ ] Cost estimation hook from G-8 wired up for this profile.
- [ ] Stretch — defer if other H items run long; track in Phase 25.

### H-8: End-to-end smoke test on a real Slurm cluster

- [ ] Stand up a test cluster (options: small institutional partner,
      `giovtorres/slurm-docker-cluster` in CI for hermetic testing,
      or a one-day GCP cluster via Slurm-on-GCP for full end-to-end).
- [ ] Test scenarios:
      1. Single-sample MIRA-NF run, Apptainer engine, weblog over
         HTTP — verify run completes, weblog events arrive, results
         loaded.
      2. Same with weblog blocked, poller path active — verify
         results still loaded via log polling.
      3. 10-sample batch via PHoeNIx, verifying queueSize throttling.
      4. Failure case: input file_reference becomes BROKEN
         mid-run — verify graceful failure and clear error to user.
- [ ] Document the test cluster setup in `docs/test_cluster.md` so
      anyone can reproduce.

### H-9: Tests

- [ ] Unit tests for the Slurm profile rendering covering all field
      combinations.
- [ ] Mocked-Slurm integration tests that capture the rendered
      `sbatch` command line and verify expected flags.
- [ ] CI matrix entry for the containerized Slurm cluster — run a
      hermetic end-to-end pipeline test on every PR that touches
      `backend/pipeline_config/` or `pipelines/`.
- [ ] Coverage target: keep above 86.99%.

### H-10: Docs

- [ ] Add `docs/slurm_executor.md` covering profile setup, network
      requirements, Apptainer pre-staging, weblog vs poller, and
      common cluster-policy gotchas.
- [ ] Add `docs/cloud_burst.md` for the GCP Batch path (if H-7
      lands).
- [ ] Update README scenario B section to show "Lab with Slurm
      cluster" as the second example after laptop, before any cloud
      example.
- [ ] Add CLAUDE.md Critical Rule: "Cluster-bound runs must work
      whether or not compute nodes can reach the API. The weblog
      receiver is best-effort; the log poller is the source of truth
      when reachability is in doubt."

---

## Phase P1 — Auth refresh endpoint with single-use rotation (COMPLETE 2026-05-05)

Shipped in PR #22 (commit `ba03143`). Closes the gap surfaced in Phase 22 review item 12 / spec.md §13 fix #5: the refresh-token cookie was issued at login but no `POST /api/v1/auth/refresh` route existed for explicit rotation. Browser-cookie clients worked fine without it; CLI/SDK clients couldn't refresh without re-authenticating end-to-end.

**Source recovery saga:** P1 went through significant worktree contamination during execution (Sessions 20-21 — see `learnings.md`). Final state on development is clean; recovery learnings logged.

### What landed

- [x] **`refresh_tokens` LinkML class + table** with seven fields: `jti` (PK), `user_id` (FK users, ON DELETE CASCADE), `issued_at`, `expires_at`, `revoked_at`, `revoked_reason` (with CHECK constraint: `rotated | logout | admin_revoke | replay_detected`), `replaced_by_jti`. Indexes: PK on jti, on user_id, partial on expires_at WHERE revoked_at IS NULL.
- [x] **`POST /api/v1/auth/refresh` endpoint** — accepts refresh token from `refresh` cookie (priority) or JSON body (`refresh_token` field). Six distinct error codes: `MISSING_REFRESH_TOKEN` / `INVALID_REFRESH_TOKEN` / `WRONG_TOKEN_TYPE` / `TOKEN_NOT_TRACKED` / `TOKEN_REVOKED` / `TOKEN_REPLAY_DETECTED`. Issues new access + refresh JWTs, marks old refresh as `revoked_reason=rotated` with `replaced_by_jti=<new>`.
- [x] **Replay detection** — when a refresh token marked `revoked_reason=rotated` is presented again, treats it as an attack indicator and bulk-revokes all of the user's currently-active refresh tokens (defense in depth). Emits `AUTH_TOKEN_REPLAY_DETECTED` audit event.
- [x] **Modified `POST /google/login`** — registers issued refresh-token JTIs in the table at login. Multiple logins by the same user create multiple rows (no implicit invalidation; that's deferred to v2).
- [x] **Modified `POST /logout`** — revokes the current refresh token in the table with reason `logout` before clearing cookies. Best-effort: logout still succeeds with missing/malformed/expired cookie.
- [x] **Settings additions** in `backend/backend/config.py`: `access_token_lifetime_seconds=900` (15min), `refresh_token_lifetime_seconds=604800` (7d), `refresh_token_cleanup_interval_seconds=86400` (daily), `refresh_token_retention_after_revoke_seconds=2592000` (30d).
- [x] **APScheduler job** `cleanup_old_refresh_tokens` — daily cleanup purging revoked-and-old + expired-and-old rows past the retention cutoff. Active rows untouched.
- [x] **Audit-action constants** added: `AUTH_TOKEN_REFRESHED`, `AUTH_TOKEN_REPLAY_DETECTED`, `AUTH_LOGOUT`. Reserved `AUTH_TOKEN_REVOKED_BY_ADMIN` for future admin-revoke functionality.
- [x] **31 P1 tests** across 5 test files: `test_p1_migration.py`, `test_p1_refresh_endpoint.py` (success path + all 6 error paths), `test_p1_login_registers_token.py`, `test_p1_logout_revokes_token.py`, `test_p1_cleanup_job.py`.

### What's deferred (broader auth-architecture work)

The "broader auth-architecture review" mentioned in P0e C.5 is intentionally not bundled into P1 — it's a design conversation rather than a single PR. Could become P1.5 or fold into P0c. Items deferred:

- [ ] **Session-management UI** — "see my active sessions, revoke a specific one". The `refresh_tokens` table now exists to support this; just needs the surface.
- [ ] **Refresh-token-family tracking** — industry-standard advanced pattern for breach detection across rotation chains. Not needed for v1; the bulk-revoke-on-replay approach is sufficient as a first defense.
- [ ] **Cross-device session detection / anomaly detection** — flag refresh attempts from new IPs or geolocations.
- [ ] **Configurable token lifetimes per-user or per-role** — global `Settings` only in v1.
- [ ] **Token introspection endpoint** (`POST /api/v1/auth/introspect`) — not needed for the refresh flow itself.
- [ ] **Multi-factor authentication** — not auth-architecture work proper.
- [ ] **New auth providers** (OIDC, SAML) — Google OAuth only in v1 still.
- [ ] **API-token rotation** (`routers/tokens.py` API-key flow) — separate from auth tokens; not touched in P1.
- [ ] **B-FED-1**: central CA infrastructure for federation peer authentication. Per P0e C.5 deferral, gates on federation network growth. Phase placement: P1 or later. **Federation Track 1 + Track 2-seam scaffold (FED-A) landed ahead of schedule 2026-05-08** at `backend/backend/federation/`; B-FED-1 reduces to the central CA integration overlay on top of FED-B/C/D/E (router / tests / migration / wiring — see "Federation / Privacy / Crypto Scaffolds" section below).

### Phase P1 success criterion

- [x] PR #22 merged into development at `ba03143`
- [x] All P1 tests pass; CI green across Backend + workspace, CLI, Pipelines parser jobs
- [x] No regressions in I-track behavior
- [x] Audit log records refresh / replay / logout events
- [x] Spec.md ⚠️ note on §13 fix #5 can be removed in a follow-up docs pass

---

## Federation / Privacy / Crypto Scaffolds (Track 1 + Track 2-seam) — NEW 2026-05-08

**Source:** Strategic framing locked this session: build federation, privacy, and encryption Track 1 implementations while in parallel scaffolding the AIS-augmented Track 2 hook seams so future research-collaboration work can plug in via dependency injection rather than forking each module. Anchor docs: `Jackpot_AIS.md` and `jackpot_immune_collaboration_scaffolding.md`.

**Architectural pattern:** two parallel namespaces under `backend/backend/`:

- `backend/backend/federation/`, `backend/backend/privacy/`, `backend/backend/crypto/` — Track 1, ships now using current JACKPOT primitives (JWT, presigned URLs, existing `can_access_sample()` permission model, existing scrubber, existing DLP)
- `backend/backend/immune/` — Track 2, AIS-augmented overlays scheduled per `jackpot_immune_collaboration_scaffolding.md`. Concrete implementations of the Protocol seams in each Track 1 package's `_ais_hooks.py` module

The seam between tracks is dependency injection. Every Track 1 class accepts a `hooks=` argument defaulting to a `Null<X>Hooks` no-op. Track 2 swaps in concrete implementations via the same constructor argument — **no code changes required to Track 1 modules when Track 2 lands.** Direction of import is one-way: Track 1 packages never import from `backend/backend/immune/`.

This work is **ahead-of-schedule** relative to B-FED-1 / B-PRV-1 / B-CRY-1 in the post-P0h future-phases pipeline. The scaffold lands the package surfaces now so the official phases reduce to wire-up + immune-overlay work when they schedule.

**Operator-agnostic policy:** no proper names anywhere in scaffold code, docs, or commit messages. When generating from `Jackpot_AIS.md` or `jackpot_immune_collaboration_scaffolding.md`, replace collaborator-name references (`TODO(forrest-collab)`, "Forrest's lane", etc.) with structural descriptors (`TODO(immune-algorithms-collab)`, "AIS-theoretic expertise"). Eponymous protocol names like "Bonawitz protocol" → "secure aggregation protocol" with the technical concept preserved. Standard cryptographic abbreviations (FROST, BLS, DKG) stay. The cleanup script `scripts_jackpot/audit_proper_names.py` (sibling to repo) verifies a directory is clean before committing.

### FED-A: Federation scaffold (COMPLETE 2026-05-08)

- [x] **`backend/backend/federation/` package landed.** Seven files:
    - `__init__.py` — public API exports
    - `README.md` — Track 1/2 plan, hook→AIS-doc mapping, integration with `backend/backend/immune/`
    - `models.py` — Pydantic v2 models: `FederatedInstance`, `FederationRole` enum (hub/spoke/peer), `FederationQuery`, `FederationQueryResult`, `FederationPushPayload`, `FederationAccessRequest`
    - `client.py` — `FederationClient` for Level 1 query federation. Concrete async fanout via `httpx`, per-partner attestation hook, anomaly-detection hook, secure-aggregate wrap on results. Async context manager.
    - `push.py` — `FederationPushJob` for Level 2 hub push. Qualification logic concrete (3 gates from `jackpot_architecture.md` §22: surveillance_relevant, sharing_level ≥ minimum, quality_status ≥ ANALYZABLE); IO stubbed via `NotImplementedError`. Payload schema enforces the negative list (no host_age, no FASTQ, no PII) by NEVER reading those fields.
    - `access.py` — `FederationAccessGateway` for Level 3 bidirectional access. Outbound + inbound integration shapes concrete; reuses existing internal `sample_access` workflow for approval. IO stubbed.
    - `_ais_hooks.py` — `AISFederationHooks` Protocol (`@runtime_checkable`) with five hooks plus `NullAISFederationHooks` no-op default. Each hook documented with AIS doc section reference, Track 2 impl module location, and expertise area needed.
- [x] **Five `AISFederationHooks` Protocol entry points:**

| Hook | AIS doc ref | Track 2 impl module |
|---|---|---|
| `secure_aggregate(results, partner_set)` | §1.6 inter-instance signaling | `backend/backend/immune/net/federation_hooks.py` ← `backend/backend/immune/sec/cs_cyber_federated.py` |
| `attest_partner(instance)` | §1.7 attribution & deception | ← `backend/backend/immune/sec/` (attestation primitives, new module) |
| `detect_anomalous_traffic(query, partner)` | §1.3 innate immunity | ← `backend/backend/immune/algorithms/featurizers/`, `backend/backend/immune/redteam/attack_federation.py` |
| `threshold_approve(action, partner_set)` | §1.8 tolerance / regulation | ← `backend/backend/immune/sec/` (threshold-crypto primitives, new module) |
| `validate_push_payload(payload, target)` | §1.8 tolerance ("don't attack self") | ← `backend/backend/immune/sec/refusal.py`, `backend/backend/immune/sec/parsers_safe.py` |

- [x] **Operator-agnostic verified.** Zero proper names in package. All hook docstrings describe Track 2 impl by location + expertise area, never by collaborator name. Eponymous protocol names genericized.
- [x] **Smoke tests pass.** `NullAISFederationHooks` satisfies `AISFederationHooks` Protocol via `runtime_checkable`. All three Track 1 classes (`FederationClient`, `FederationPushJob`, `FederationAccessGateway`) construct with default null hooks. `FederationPushJob.is_qualifying_sample()` correctly returns True/False across 5 boundary cases.

### FED-D: Schema migration (PENDING)

- [ ] **`federated_instances` table.** Columns per `models.py` `FederatedInstance` shape: `id` (UUID PK), `name`, `base_url`, `role` (enum: hub / spoke / peer), `federation_enabled` (default false), `min_sharing_level_for_federation` (default `'DISCOVERABLE'`), `hub_instance_url` (nullable), `api_key_secret_name`, `last_seen_at` (nullable), `created_at`, `updated_at`.
- [ ] **New columns on `organizations`:** `min_sharing_level_for_federation`, `federation_enabled`, `hub_instance_url`, `federation_role`.
- [ ] **Workflow:** LinkML schema YAML edits first → `uv run python scripts/regen_schema.py` → Alembic autogenerate → manual cleanup. Branch: `b1-federation-schema-migration`.

### FED-C: Tests (PENDING)

- [ ] **`tests/federation/` test files:**
    - `test_models.py` — Pydantic v2 shape and serialization round-trip
    - `test_client_l1.py` — `FederationClient` async fanout, hook invocation order, partner attestation rejection, anomaly detection rejection. Use `respx` to mock partner HTTP.
    - `test_push_l2.py` — qualification logic (port the 5 smoke-test cases from FED-A delivery), payload composition, negative-list enforcement
    - `test_access_l3.py` — outbound + inbound shapes, `NotImplementedError` raises where appropriate
    - `test_ais_hooks.py` — `NullAISFederationHooks` satisfies Protocol, all five hooks return safe defaults
- [ ] **Coverage target:** ≥95% on every module in `backend/backend/federation/`. Branch: `b2-federation-tests`.

### FED-B: Federation router (PENDING)

- [ ] **`backend/backend/routers/federation.py`** exposing the package via:
    - `GET /api/v1/federation/instances` — list registered partners (Platform Admin only)
    - `POST /api/v1/federation/instances` — register a partner (Platform Admin only)
    - `POST /api/v1/federation/search` — broadcast L1 query to enabled partners
    - `POST /api/v1/federation/push` — receive an inbound L2 payload (peer instance only)
    - `POST /api/v1/federation/access-requests` — receive an inbound L3 access request (peer instance only)
- [ ] **Auth:** federation API keys via `X-JACKPOT-Federation-Key` header for peer-to-peer endpoints (validated against `federated_instances.api_key_secret_name` via Secret Manager); standard JWT + `require_platform_admin` for the admin-facing list/register endpoints. Branch: `b3-federation-router`.

### FED-E: Wire router into `main.py` (PENDING)

- [ ] **Register the FED-B router in `backend/backend/main.py`.**
- [ ] **Add federation-key guard to `backend/backend/auth/guards.py`** if not validated inline. Branch: `b4-federation-wiring`.

### PRV-A: Privacy scaffold (PENDING — same pattern as FED-A)

- [ ] **`backend/backend/privacy/` package** mirroring federation's shape:
    - `__init__.py`, `README.md`, `_ais_hooks.py` (Track 2 seam: `AISPrivacyHooks` Protocol + `NullAISPrivacyHooks` no-op default)
    - `coarsening.py` — Track 1: consolidates `host_age_range` and similar generalization-based privacy primitives that already ship
    - `scrubber.py` — Track 1: HRRT (NCBI SRA Human Scrubber) integration interface, wraps the existing Nextflow scrub workflow
    - `dlp.py` — Track 1: consolidates `dlp_scanner.py` GCP Cloud DLP integration
    - `budget.py` — placeholder for DP budget tracking (Track 2 anchor)
- [ ] **`AISPrivacyHooks` Protocol surface (refine in-session against AIS doc):**

| Hook | AIS doc ref | Track 2 impl module |
|---|---|---|
| `dp_noise(query_result, sensitivity)` | §1.4 adaptive immunity | `backend/backend/immune/sec/cs_cyber_federated.py` |
| `track_dp_budget(requester, epsilon)` | §1.8 tolerance / regulation | `backend/backend/immune/sec/` (DP budget accountant, new) |
| `fl_aggregate(local_updates)` | §1.6 inter-instance signaling | `backend/backend/immune/sec/cs_cyber_federated.py` |
| `he_compute(encrypted_inputs, op)` | §1.4 adaptive immunity | `backend/backend/immune/sec/he_backend.py` (new) |
| `mpc_protocol(parties, computation)` | §1.6 inter-instance signaling | `backend/backend/immune/sec/mpc_backend.py` (new) |
| `synthetic_substitute(real_dataset)` | §1.5 diversity layer | `backend/backend/immune/algorithms/featurizers/` |

- [ ] **Estimated:** ~1000 lines, 7 files, 1 PR. Branch: `privacy-scaffold-track1-track2-seam`.

### CRY-A: Crypto scaffold (PENDING — same pattern as FED-A)

- [ ] **`backend/backend/crypto/` package** mirroring federation's shape:
    - `__init__.py`, `README.md`, `_ais_hooks.py` (Track 2 seam: `AISCryptoHooks` Protocol + `NullAISCryptoHooks` no-op default)
    - `keys.py` — Track 1: key management abstraction over PKCS#11 / Secret Manager / file-system keystores
    - `signing.py` — Track 1: Sigstore/cosign artifact-signing interface
    - `crypt4gh.py` — Track 1: per-file encryption for ingest/egress (Crypt4GH GA4GH standard)
- [ ] **`AISCryptoHooks` Protocol entry points (refine in-session):** HE backend selection, threshold signing (FROST/BLS/DKG), TEE attestation evidence verification, key-rotation policy enforcement.
- [ ] **Estimated:** ~1000 lines, 7 files, 1 PR. Branch: `crypto-scaffold-track1-track2-seam`.

### Future B-FED-1 / B-PRV-1 / B-CRY-1 relationship

- **B-FED-1** (in Phase P1 deferred items above) reduces to central CA integration overlay on top of FED-A scaffold + FED-B/C/D/E wire-up.
- **B-PRV-1** (privacy hardening — DP enforcement, FL coordinator, DLP rule expansion) reduces to concrete impl of `AISPrivacyHooks` Protocol via `backend/backend/immune/sec/` once PRV-A scaffold lands.
- **B-CRY-1** (encryption hardening — Crypt4GH ingest, threshold-signed governance actions, TEE attestation for federation peers) reduces to concrete impl of `AISCryptoHooks` Protocol via `backend/backend/immune/sec/` once CRY-A scaffold lands.

### Phase Scaffolds success criterion

- [x] FED-A scaffold landed with operator-agnostic verification
- [ ] At least one of {FED-B/C/D/E wire-up, PRV-A, CRY-A} merged before the next /ultrareview pass
- [ ] All five `AISFederationHooks` Protocol entry points still satisfied by `NullAISFederationHooks` after any future refactors (verifiable via `tests/federation/test_ais_hooks.py` once FED-C lands)

---

## Phase 27 — CDC DMI / North Star / STLT Alignment Backlog (Tracked, Not Scheduled)

**Source:** `jackpot_cdc_dmi_stlt_overview.md` (April 2026 working session). This is parallel to Phase 26 — different lens. Where Phase 26 covers "things lifted from open-source peer platforms" (Loculus, Pathogenwatch, etc.), Phase 27 covers "things adapted from US public-health-data ecosystem" (CDC DMI, North Star Architecture, STLT operator needs, CARE Principles for Indigenous Data Sovereignty). 14 items total across 3 groups.

**Already moved to other phases:**

- `B-DMI-3`, `B-STLT-2`, `B-GOV-1` (combined with `B-CARE-1`), `B-CARE-2`, `B-DMI-1`, `B-STLT-1`, `B-STLT-3` are in **Phase 21.5** (Interstitial During-P0d Quick Wins) since they ride along with monorepo / docs work
- `B-CARE-3-DESIGN` is in **Phase 24.5** (Architectural Design Lockdown) since it gates P0b schema work

The items below are the ones that don't fit those interstitial buckets — implementation items, larger work, or pure outreach.

### K. Tribal sovereignty / CARE Principles (overview §11-12 of `jackpot_cdc_dmi_stlt_overview.md`)

- [ ] **B-CARE-3** (implementation) Implement true delete-on-request via tombstone-and-vacuum lifecycle per the design from Phase 24.5. Code: `samples.deletion_status` enum migration, tombstone-marking logic, vacuum background job, audit log integration, GCS/MinIO object deletion, JSONB content scrubbing. (2-3 sessions, **P0c — multi-tenancy middleware**)
- [ ] **B-CARE-4** Federation-aware deletion propagation. Tombstone events pushed to peers; signed receipts; SLA tracking; non-compliance flagging. Depends on B-CARE-3 + Scenario E federation work. (1 week, Year 2)
- [ ] **B-CARE-5** Pre-publish review checklist with CARE-Principle confirmation. Scenario T defaults to no-auto-publish; explicit per-sample approval required. "Previously published" tag persists past vacuum. (1-2 sessions, with B-CARE-3 implementation in P0c)

### L. STLT-tier alignment (overview §6, §10 of `jackpot_cdc_dmi_stlt_overview.md`)

(Most STLT items are in Phase 21.5 — they're documentation that rides along with P0d. The implementation-shape items below are separate.)

- [ ] **B-STLT-4** (NEW) Build a **scenario detector** in `schema/jackpot_scenarios/detector.py` that asks 4-5 operator-type questions (operator type, deployment target, federation, PII handling, optional auth override) and deterministically maps to scenarios A–F+T. The scenario registry + detector live in the shared `jackpot_scenarios` package (sibling of `jackpot_schema/`) so backend, CLI, and CI workflows all import the canonical logic. CLI consumes via `cli/jackpot/init/`. (1-2 sessions, **P0e** with `jackpot init` work) — design decisions LOCKED 2026-05-01, see `docs/architecture/jackpot-init-cli.md`.

### M. CDC DMI / North Star alignment (overview §3-5 of `jackpot_cdc_dmi_stlt_overview.md`)

- [ ] **B-DMI-2** Build `backend/routers/fhir.py` for FHIR `Specimen` + `MolecularSequence` ingest, `Observation` + `Provenance` emit. Gated on operator demand — don't build speculatively. (1-2 weeks, Year 2)

### Phase 27 quick-win priority order

The highest-leverage items have *already moved* to Phase 21.5 (governance docs, layer-cake, deploy guides) and Phase 24.5 (sovereignty design). What's left in Phase 27 proper is a mix of larger implementation work and outreach. The one item worth doing soonest:


The rest is implementation work that gates on P0b/c/e or Year 2.

---

## Deferred — revisit later

- **Phase 24.5 external collaborator review** — Deferred 2026-05-05 (timing). Phase 24.5 design lockdown will proceed solo (option β); external review of the locked design may resume later as a follow-up iteration if material feedback comes in. The CARE-Principles commitment in `governance/care-principles-and-tribal-data-sovereignty.md` is unchanged; only the active outreach effort is paused.

---

## Phase 28 — Default Eukaryotic Pathogen Pipelines (Tracked, Tier-Prioritized)

**Source:** `jackpot_byop_and_eukaryotic_design.md` Part II (Sections 11-16). Schema work for these pipelines already in Phase 24.5 (B-EUK-1, B-EUK-2, B-EUK-3). BYOP infrastructure required to register them as zoo entries already in Phase 24.7 / P0f. This phase is the actual pipeline implementations + parsers + dashboards.

**11 implementation items** organized into **3 tier-prioritized groups** by global disease burden, surveillance utility, and community tooling availability. Each pipeline ships with its parser; dashboards group two pathogen groups per page.

**All pipelines:** AGPL-3.0, hosted under `Midnight-Oil-Innovation/jackpot-pipelines-eukaryotic` (single repo, one subdirectory per pipeline), registered as Level-1 zoo entries via P0f BYOP infrastructure.

### Phase 28 Tier 1 — ship first (highest priority)

Highest global disease burden + most active surveillance community + largest existing tooling base. Builds JACKPOT credibility for global infectious disease surveillance work.

```text
[ ] B-EUK-PLAS-1  jackpot-plasmodium-typer pipeline (Nextflow). Drug
                  resistance loci genotyping (pfk13, pfdhfr, pfdhps,
                  pfcrt, pfmdr1) + HRP2/HRP3 deletion detection +
                  lineage assignment. Wraps bcftools for SNP calling
                  against PlasmoDB references. (1-2 weeks, post-P0f)

[ ] B-EUK-CRYP-1  jackpot-cryptogiardia-typer pipeline (Nextflow).
                  GP60 subtyping for Cryptosporidium (gold-standard
                  outbreak typing) + Giardia assemblage assignment +
                  WGS SNP outbreak clustering. US-relevant for
                  waterborne outbreak surveillance. Smallest eukaryotic
                  genome → fastest pipeline. (1-2 weeks, post-P0f)

[ ] B-EUK-PARSE-T1  Parsers for Tier 1 pipelines:
                    plasmodium_drug_resistance_results parser,
                    cryptogiardia_typing_results parser. Follow
                    existing pattern in backend/parsers/.
                    (1 session per parser, post-P0f)

[ ] B-EUK-DASH-T1   Streamlit dashboard pages for Tier 1:
                    Malaria dashboard (drug resistance prevalence by
                    region/year, pfk13 SNP frequency, HRP deletion
                    prevalence, MOI distribution),
                    Crypto/Giardia dashboard (outbreak cluster map,
                    GP60 subtype trends, assemblage distribution).
                    (2-3 sessions per dashboard, post-pipelines)
```

### Phase 28 Tier 2

Medium-priority pathogens with significant disease burden but less active surveillance community or smaller existing tooling base.

```text
[ ] B-EUK-LEIS-1  jackpot-leishmania-typer pipeline (Nextflow).
                  Species discrimination + MLST + drug resistance
                  (antimony, miltefosine, paromomycin). Maps against
                  TriTrypDB references. (1-2 weeks, post-Tier-1)

[ ] B-EUK-TRYP-1  jackpot-trypanosoma-dtu-caller pipeline (Nextflow).
                  DTU assignment for T. cruzi (TcI through TcVI) +
                  drug resistance for T. brucei spp. Handles the
                  high heterozygosity / aneuploidy of T. cruzi.
                  (1-2 weeks, post-Tier-1)

[ ] B-EUK-SCHI-1  jackpot-schistosoma-barcode pipeline (Snakemake —
                  first non-Nextflow default pipeline, exercises P0f
                  Snakemake launcher). cox1/nad1/ITS markers +
                  hybrid detection (S. haematobium × S. bovis).
                  (1 week, post-Tier-1)

[ ] B-EUK-PARSE-T2  Parsers for Tier 2 pipelines:
                    leishmania_typing_results,
                    trypanosoma_typing_results,
                    schistosoma_typing_results.
                    (1 session per parser, with each pipeline)

[ ] B-EUK-DASH-T2   Streamlit dashboard pages for Tier 2:
                    Leishmania dashboard (species distribution, drug
                    resistance trends, HIV co-infection cases),
                    Trypanosoma dashboard (DTU geographic distribution,
                    treatment-outcome correlation),
                    Schistosoma dashboard (hybrid detection map, PZQ
                    resistance, cox1 haplotype trees).
                    (2-3 sessions per dashboard, post-pipelines)
```

### Phase 28 Tier 3

Lower-priority for sequencing-based surveillance (most STH and filarial work is amplicon/PCR rather than WGS), but completes the eukaryotic coverage picture.

```text
[ ] B-EUK-STH-1   jackpot-sth-nemabiome pipeline (Nextflow). Wraps
                  existing nemabiome amplicon analysis from Tasmania.
                  Species ID + β-tubulin codon 167/198/200 SNPs
                  (benzimidazole resistance markers). (3-5 sessions,
                  post-Tier-2)

[ ] B-EUK-STH-2   jackpot-sth-wgs pipeline (Nextflow). WGS-based SNP +
                  resistance + population structure for soil-
                  transmitted helminths. For labs with WGS rather
                  than amplicon capacity. (1-2 weeks, post-Tier-2)

[ ] B-EUK-FILA-1  jackpot-filarial-typer pipeline (Nextflow). Species
                  ID (W. bancrofti, B. malayi, B. timori) + Wolbachia
                  endosymbiont status (basis for doxycycline therapy)
                  + ivermectin resistance. (1-2 weeks, post-Tier-2)

[ ] B-EUK-TOXO-1  jackpot-toxo-entamoeba-typer pipeline (Nextflow).
                  Toxoplasma 15-marker MLST + clonal lineage
                  assignment (Type I/II/III + atypical) +
                  Entamoeba histolytica vs E. dispar discrimination
                  (most "histolytica" in microscopy is dispar — no
                  treatment needed). (1 week, post-Tier-2)

[ ] B-EUK-PLAS-2  jackpot-plasmodium-mippy pipeline (Nextflow). Wraps
                  existing mippy for amplicon-based malaria surveillance.
                  For labs running amplicon panels rather than WGS.
                  (3-5 sessions, post-Tier-2)

[ ] B-EUK-PARSE-T3  Parsers for Tier 3 pipelines:
                    helminth_drug_resistance_results,
                    filarial_typing_results,
                    toxo_entamoeba_typing_results.
                    (1 session per parser, with each pipeline)

[ ] B-EUK-DASH-T3   Streamlit dashboard pages for Tier 3:
                    STH dashboard (β-tubulin SNP prevalence, species
                    map),
                    Filarial dashboard (elimination program tracking,
                    ivermectin resistance, Wolbachia status),
                    Toxo/Entamoeba dashboard (lineage geographic
                    distribution, E. histolytica vs E. dispar
                    differential).
                    (2-3 sessions per dashboard, post-pipelines)
```

### Phase 28 success criterion

- [ ] All 10 default eukaryotic pipelines registered as Level-1 zoo entries via P0f BYOP infrastructure
- [ ] All 8 dashboard pages live in Streamlit researcher view
- [ ] All 8 pipeline-result tables receiving data from real pipeline runs
- [ ] At least one end-to-end test sample per pathogen group with verified results
- [ ] Documentation under `docs/pipelines/eukaryotic/` describing each pipeline

**Total effort:** ~10-15 weeks if sequential, ~4-6 weeks if parallelized across 3 contributors. Each pipeline is genuinely independent work.

**Phase placement justification:** Cannot start until P0f (BYOP infrastructure) is real, since these pipelines register *via* BYOP. Schema is ready in P0b. Internal tier-priority orders the actual implementation order based on global health impact and tooling availability.

---

## Done in Session 5 (2026-04-17 evening — 2026-04-19 early AM)

**First staging deploy to GKE** — 10 root causes diagnosed and fixed:

- `jackpot-nf` pushed to GitHub (was only on local Mac).
- `.gitmodules` URL fixed (filesystem path → GitHub URL).
- `submodules: recursive` + PAT `insteadOf` injection in workflow.
- `Dockerfile.api` updated to `COPY nf/`.
- `cors_origins` ConfigMap format tactical fix (JSON-array string).
- `DATABASE_URL` Secret corrected (`/jackpot` → `/jackpot_db`).
- `CROSS_REPO_PAT` restored (had been overwritten with a Google OAuth
  client secret).
- Helm release unstuck from `pending-upgrade` via manual rollback.
- Smoke test rewired to use `kubectl port-forward`.
- Bootstrap Job written for fresh-DB init.sql + alembic stamp flow.

**Streamlit UI local** — 6 chained bugs diagnosed and fixed:

- `Dockerfile.ui` `COPY frontend/ .` was flattening the layout.
- `docker-compose.yml` `./frontend:/app` mount was overriding the image
  layout with the flattened form.
- `docker-compose.yml` `command:` directive was overriding the image
  CMD with the old `app.py` path.
- Streamlit's `sys.path[0]` is the script dir, so `/app/frontend/` was
  on the path but not `/app/` — `PYTHONPATH=/app` fixed it.
- `ApiClient` in `frontend/lib/api.py` was reading `JACKPOT_API_URL`
  but compose was setting `API_BASE_URL` — added as fallback.
- `MOCK_USER_EMAIL` was already on the api service (line 78 of
  compose) but a first-pass diagnostic missed it — resulted in a
  momentary duplicate-key error after my patch attempt.

All permanent fixes for these are tracked in Phase 20 Q-9 through Q-18.

---

## Notes for the next session

**Fresh morning, 5 minutes first:** verify local development is in sync with origin and the post-merge state holds:

```bash
cd ~/Projects/jackpot
git switch development
git pull --ff-only
git log --oneline -5      # should show the four most recent merges from Sessions 21+
uv sync                   # picks up the ruff 0.11.6 pin from PR #25
uv run pre-commit clean
uv run pre-commit install --install-hooks
uv run ruff --version     # should print: ruff 0.11.6
uv run pytest --no-cov -q --tb=short    # baseline confirmation
```

If anything diverges from the expected state, debug before starting feature work.

**Active sprint candidates (maintainer's call):**

1. **Phase P0g G-5** (profiles CRUD endpoints) — operators can use the renderer/resolver from PR #28 but can't manage profiles via API yet. CRUD closes that gap and unblocks the legacy GCP-Batch path deletion in `pipeline_config/legacy.py`. Concrete short-feedback-loop continuation of P0g.

2. **Phase 24.5 design lockdown (solo, option β)** — The maintainer finalizes the sovereignty-deletion design without external review (collaborator review deferred 2026-05-05 — timing). Once locked, P0b unblocks. Mix of design and writing work. Probably 1-2 sessions.

3. **Performance and cleanup follow-ups from /ultrareview Batch D** (14 items above) — none block any feature work; can be one batched cleanup PR or interleaved as smaller ones.

4. **Phase 24.7 / P0f BYOP infrastructure** — heavier lift; B-BYOP-1 through B-BYOP-10. Gates on `jackpot init` shape (P0e is done) but not blocked otherwise.

5. **P0f file references continuation** — F-3+ if F-2 was the last shipped. Independent of P0g/P1 work; can run in parallel with the chosen primary track.

6. **Small housekeeping pile** — most items in "Post-Sessions-21+ housekeeping" closed by PR #27; remaining items (gac zsh, branch protection, stale stashes, obsolete branches) can fold into one cleanup PR. ~30-60 min total.

My suggestion (informational, not prescriptive): Phase 24.5 design lockdown next if you want to unblock P0b on the strategic critical path, or P0g G-5 if you want to continue the P0g momentum. Batch D and the housekeeping pile interleave whenever convenient.

**Worktree workflow lesson from Sessions 20-21:** if you start parallel-track sessions, use `git worktree add` per branch and never `git switch` inside a worktree. First message of every Claude Code session in a worktree should run the verification ritual:

```bash
EXPECTED_WORKTREE="$HOME/Projects/jackpot-<branch>"
EXPECTED_BRANCH="<branch-name>"
[ "$(pwd -P)" = "$EXPECTED_WORKTREE" ] || { echo "FATAL: wrong cwd ($(pwd -P)). Stop." >&2; exit 1; }
[ "$(git branch --show-current)" = "$EXPECTED_BRANCH" ] || { echo "FATAL: wrong branch ($(git branch --show-current)). Stop." >&2; exit 1; }
echo "Worktree + branch verified."
```

Refuse to proceed if either assertion fails. Cheapest possible insurance against the contamination we hit.

**Older notes preserved (still relevant for ongoing work):**

- **Before any GCP deploy to a new environment:** run `local_test_checklist.md` top to bottom. Specifically Part 1 step 5 (Alembic from empty DB) — if that fails, Q-9 hasn't landed and you need the bootstrap Job workaround.

- **For the Month 1 human-testable demo:** Phase 21 IS the demo. Once UI-B through UI-D are green, you can show "upload a sample → find it in search → view its details" in a browser. That's the full Month 1 scope.

- **For production readiness:** Q-9 (Alembic baseline) is the most important unblock. It makes every fresh deploy honest and eliminates the bootstrap Job dependency.

- **For closing Month 2:** Q-5 (staging E2E pipeline test) gates the `month-2-complete` tag. Phases 20, 21, 23, and 24 are the ordered critical path to get there.
