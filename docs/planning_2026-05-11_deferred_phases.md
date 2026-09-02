> **Status:** Reference — preserved planning snapshot; not a statement of current project state.

# Deferred planning — Phases 26 (adoption), 29–35, and the ML/OBS/WW/EPY schema items

**Provenance.** Extracted verbatim from `todo.md` at git tag
`planning/2026-05-11-round4-phase35` (commit `912697c`, 2026-05-11). That commit
lived on a local-only branch that was never pushed, never opened as a PR, and
never merged. It was found on 2026-09-01 during a branch cleanup; **99 of its
item IDs existed nowhere else in the repository.** The branch is gone; the
commit is preserved under that tag, plus two sibling tags whose content this
one strictly contains:

| Tag | Commit |
|---|---|
| `planning/2026-05-11-round4-phase35` | `912697c` — this document's source |
| `planning/2026-05-11-round3-defect-fixes` | `4c23a02` |
| `planning/2026-05-11-ml-federation-additions` | `44abbd5` |

**What this is and is not.** It is a snapshot of intent from 2026-05-11, kept
because the reasoning is expensive to reconstruct — license-compatibility
analysis for epydemix/WhiteLabRt against AGPL-3.0, the Rt-method comparison
plan behind DEC-16, the wastewater defect-fix pass that produced DEC-11..14.
It is **not** current, **not** reviewed against anything that shipped since,
and **not** actionable as written. Everything here predates P0b (Schema v5.0),
P0e, P0f, and the access-model redesign, so schema item numbering, phase
numbering, and "must land with P0b" claims are all stale. Several referenced
documents have since been archived or renamed.

Six phase-level entries in `active_backlog.yaml` point here at status
`tracked_not_scheduled`. Those entries are the scheduling surface; this file is
the detail behind them. Per Critical Rule 70, treat every integration claim
below as a claim — grep before building on it.

**Sections below, in source order:** the FIX-3 staging bug; the DEC-2..14
architectural decisions with the ML / Health-Observatory / wastewater /
epidemiological-forecasting schema additions; Phase 26's B-* adoption items
(including B-EPY-1/2, B-WLR-1, B-RTEVAL-1); and Phases 29–35 in full.

---

## Active P0 bugs (over-claimed in Phase 0, must be fixed)

These two bugs are listed under Phase 0's "P0-1 through P0-16 all completed" line as `audit/notification transaction cohesion` and `execute_query conn param` — but inspection of the current code shows the fixes did not actually land. Same over-claim pattern as the JWT refresh endpoint (over-claimed in Phase 0, resolved 2026-05-05 in P1 PR #22). Block Phase IM-1 (called out as prerequisites in the Phase IM-1 prerequisites list) and degrade transactional correctness everywhere else.

- [ ] **FIX-1** `log_audit()` and `create_notification()` accept `db_conn` but do not forward it to `execute_write()`. Audit and notification writes auto-commit in separate transactions from the operations they audit. Silent audit gap possible on write failure — if the parent operation rolls back, the audit row stays committed. Fix: thread `db_conn` through `execute_write(..., conn=db_conn)` in both helpers; add transaction-rollback test verifying that an audit row does NOT exist if the parent operation rolls back. Update the Phase 0 entry to drop the misleading completion claim. (1 session)

- [ ] **FIX-2** `_handle_workflow_complete()` in the pipelines router calls `execute_query(..., conn=conn)` but `execute_query()` signature does not accept a `conn=` keyword argument. Will raise `TypeError` when Nextflow posts `workflow.complete` — pipeline completion events will crash the router. Either add `conn=` to `execute_query()` signature (mirror `execute_write()`) or remove the `conn=conn` at the call site. Add a regression test simulating the `workflow.complete` POST. Update the Phase 0 entry. (0.5 session)

- [ ] **FIX-3** Verify the `jackpot-api-config` ConfigMap in the staging GKE cluster contains the JSON-array form of `CORS_ORIGINS` (not a bare comma-separated string). Q-10 closed the validator-side fix and Session 5 applied a tactical ConfigMap fix; this is a 15-minute spot-check to confirm the deployed ConfigMap is still in the expected shape after subsequent Helm upgrades. Fix path if drift detected: `kubectl -n jackpot delete configmap jackpot-api-config && gh workflow run deploy-staging.yml`. (15 min)

---

## Performance and cleanup follow-ups (from /ultrareview Batch D)

These items are from the /ultrareview pass and are real but not blocker-level. They ship as smaller PRs incrementally, opportunistically, after R-1 + R-2 + R-3 land.


### Architectural decisions required for ML/Observatory schema additions (2026-05-11)

Schema design depends on resolving these decisions first. Each is a Glen-owned design call, not an implementation task. ML-1..4 and OBS-1..4 are blocked until the relevant DEC items below are resolved.

- [ ] **DEC-1** Choose foundation model for the eventual embedding pipeline (Nucleotide Transformer 2.5B, Evo / Evo 2 7B+, HyenaDNA, DNABERT-2, or ESM-2). Affects whether `embeddings.embedding` column supports multiple dimensionalities or just one. Recommendation: Nucleotide Transformer first; if multiple foundation models will be in flight, `embeddings` needs an FK to `model_artifacts` for dimensionality lookup.

- [ ] **DEC-2** Choose model serialization format for `model_artifacts.artifact_uri` contents — ONNX (portable, may break on some architectures), TorchScript (PyTorch-only), or pickle (fragile). Recommendation: ONNX with TorchScript fallback per model. Documented as operator policy; no direct schema impact.

- [ ] **DEC-3** Choose federation aggregator hosting model for FML work: designated cell, rotating role across cells, or neutral third party. Affects whether `federated_instances.role` enum needs an `aggregator` value distinct from `hub`.

- [ ] **DEC-4** Confirm pgvector extension availability on the Cloud SQL Postgres 16 instance and decide whether `embeddings.embedding` is a pgvector column or a JSONB float array. Alternative: separate vector store (Chroma, pgvector-as-separate-Postgres). Recommendation: pgvector on Cloud SQL if available; fall back to JSONB array with functional index for cosine similarity if not.

- [ ] **DEC-5** Decide whether bulk milk H5N1 samples extend the existing `Food` source type or get a new `DairySample` subclass under `EnvironmentalSample`. Affects scope of OBS-1 schema item.

- [ ] **DEC-6** Decide whether `external_data_sources` is per-operator (RBAC-scoped, `operator_id` FK) or shared globally. Per-operator is more flexible (Arizona NOAA stations differ from Mozambique stations); shared is simpler. Recommendation: per-operator.

- [ ] **DEC-7** Decide whether ASU-specific demo code (Tempe Open Data fetcher, Valley fever LSTM result type, Maricopa-specific examples) lives in (a) a new `jackpot-demos` repo, (b) a new `jackpot-asu` repo, or (c) the core monorepo behind feature flags. Recommendation: (a) `jackpot-demos` repo to keep core operator-agnostic per Critical Rule 55.

- [ ] **DEC-8** Decide whether federation summary statistics from FML work are stored as typed tables (`federation_lineage_frequencies`, `federation_amr_distributions`, `federation_embedding_centroids`) or as a single JSONB-blob table. Typed is more queryable; JSONB is more flexible for future stat types. Recommendation: typed tables for the three named summary types, JSONB column on each for future extensions.

### Schema additions for ML/modeling infrastructure (must land with P0b)

These tables enable the ML pipeline work in Phase 29 and the Federated ML Analytics work in Phase 30. Splitting them into a later migration creates the same double-migrate operator churn that B-BYOP-9 / B-EUK-1 avoid. All ML schema items depend on the relevant DEC items above being resolved.

- [ ] **ML-1** Add `model_artifacts` table: `id` (UUID PK), `model_family_id` (UUID, groups versions of the same conceptual model), `version` (semver string), `training_data_hash` (SHA-256 of training corpus + featurization config), `training_pipeline_run_id` (FK to `pipeline_runs`), `validation_metrics` (JSONB), `artifact_uri` (GCS/MinIO path), `status` enum (`active` / `deprecated` / `retired`), `replacement_model_id` (nullable FK to self), `created_at`. Immutable append-only — new rows for retraining; old rows never updated. (1 session, P0b — depends on DEC-1, DEC-2)

- [ ] **ML-2** Add `model_evaluations` table: `id`, `model_id` (FK to `model_artifacts`), `evaluation_dataset_id` (FK to `datasets` or content-hashed external dataset ID), `metrics` (JSONB), `evaluated_at`. Append-only. Each row records one evaluation against one held-out dataset; multiple rows per model expected over time. (0.5 session, P0b — bundle with ML-1)

- [ ] **ML-3** Add `inference_runs` table: `id`, `model_id` (FK to `model_artifacts`), `input_data_query` (JSONB description of the sample-set scored), `output_pipeline_results_ids` (UUID array of `pipeline_results` rows produced), `run_at`, `run_by_user_id`. Append-only. (0.5 session, P0b — bundle with ML-1)

- [ ] **ML-4** Add `embeddings` table: `id`, `sample_id` (FK to `samples`), `model_id` (FK to `model_artifacts`), `embedding` (pgvector or JSONB float array per DEC-4), `created_at`. Plus enable the `pgvector` PostgreSQL extension via Alembic migration if DEC-4 chooses pgvector. Index on `(sample_id, model_id)` for lookup; vector similarity index per pgvector docs. (1 session, P0b — depends on DEC-1, DEC-4)

### Schema additions for Health Observatory use cases (must land with P0b)

These items extend the existing schema to support the four ASU Health Observatory project areas surfaced by Engelthaler / Sunenshine / Lant (H5N1 statewide surveillance consortium, Valley fever genomic + environmental integration, measles outbreak tracking, multi-pathogen Tempe wastewater) plus the external-context-data integration pattern needed for any of these to work alongside non-genomic public health data sources. All four bundle into a single migration cycle.

- [ ] **OBS-1** Add dairy bulk milk sample support per DEC-5 outcome. If new `DairySample` subclass: under `EnvironmentalSample` with fields `herd_size_head` (integer), `processing_status` enum (`raw` / `pasteurized` / `commingled`), `storage_temperature_c` (float), `collection_point` enum (`bulk_tank` / `pipeline` / `silo`). If extending `Food` source type: same fields but on a `FoodSample` subclass for dairy products. Update `validator.py` for new required-field rules. Needed for H5N1 statewide surveillance consortium dairy sampling. (1-2 sessions, P0b — depends on DEC-5)

- [ ] **OBS-2** Add air filter sampling protocol fields on `AirSample`: `filter_type` enum (`polycarbonate` / `polysulfone` / `glass_fiber` / `cellulose_ester` / `other`), `sampling_duration_hours` (float, required), `flow_volume_m3` (float, derived from `airflow_rate_m3_s × sampling_duration_hours × 3600` or independently measured), `post_collection_processing` enum (`fungal_culture` / `direct_dna_extraction` / `pcr_only` / `other`). Critical fix: make `pm25_ug_m3` and `pm10_ug_m3` conditionally required — required when `post_collection_processing` is not `fungal_culture`; optional when it is `fungal_culture` (Coccidioides air filter surveillance often does not measure PM concentrations). Update `validator.py` for the conditional rule. Needed for the Valley fever Coccidioides air sampling integration. (1 session, P0b)

- [ ] **OBS-3** Add `external_data_sources` table per DEC-6: `id` (UUID PK), `source_name` (text), `base_url` (text), `identifier_pattern` (regex or template — e.g. `https://www.ncei.noaa.gov/access/services/data/v1?stations={station_id}`), `license` (text), `allowed_use` enum (`public` / `controlled` / `internal`), `operator_id` (FK if per-operator per DEC-6, otherwise NULL), `contact_email`, `last_validated_at`, `created_at`. Plus a `sample_external_context` join table: `id`, `sample_id` (FK), `external_data_source_id` (FK), `external_identifier` (text — NOAA station ID, ASIIS lot number, etc.), `valid_from`, `valid_to`. Designed so sample-anchored analyses can join to external context (weather, land use, vaccination registry) at query time without ingesting bulk external data. (1-2 sessions, P0b — depends on DEC-6)

- [ ] **OBS-4** ICTV-aligned virus taxonomy refactor. Confirm scope from Varsani collaboration framing before committing. Adds new fields to `OrganismName` records: `ictv_taxonomy_id` (text), `ictv_realm`, `ictv_kingdom`, `ictv_phylum`, `ictv_class`, `ictv_order`, `ictv_family`, `ictv_genus`, `ictv_species`. Source: ICTV Master Species List (latest release). Validate at ingest against the controlled vocabulary. Varsani is on the ICTV Executive Committee — this schema item is intentionally aligned with his domain authority. (1-2 sessions, P0b — confirm scope before commit)

### Architectural decision: wastewater module refactor (RESOLVED 2026-05-11)

- [x] **DEC-10** **RESOLVED 2026-05-11 — refactor approach selected.** The existing v4.4 single-class `WastewaterSample` will be refactored (not extended additively) to add a `site_id` FK to a new persistent `WastewaterCollectionSite` entity, with site-level fields (`wwtp_name`, `nwss_sewershed_id`, `sample_location_zipcode`, `county_names`, `population_served`) migrating to the site entity. Per-target qPCR fields (`pcr_target`, `pcr_gene_target`, `pcr_gene_target_ref`, `pcr_type`, `quant_stan_type`, `stan_ref`, `lod_ref`, `inhibition_method`, `num_no_target_control`) move from `WastewaterSample` to a new `WastewaterTargetResult` per-target table. Migration WW-11 backfills site rows from denormalized fields and creates one initial `WastewaterTargetResult` per existing `WastewaterSample` from current `pcr_target_*` values. Rationale: the denormalization is a genuine architectural bug — Tempe's multi-pathogen panel and any multi-target ddPCR workflow can't fit the current model. API consumers of v4.4 `WastewaterSample` will need an upgrade path; documented in v5.0 release notes (DOC-12).

- [ ] **DEC-11** Typed table vs `pipeline_results` JSONB result-type pattern for wastewater metagenomic results. JACKPOT's general pattern is `pipeline_results` JSONB with parser-defined typed schemas. Precedent for typed tables exists (clinical `amr_results`, `tb_typing_results`, `typing_results`). WW-4 currently proposes a typed `WastewaterMetagenomicProfile` table. Decision: keep as typed table (justified by query patterns — wastewater dashboards filter by integron type, plasmid replicon family, ARG class, MAG count, which would be slow against JSONB) vs migrate to a typed result_type within `pipeline_results`. Recommendation: typed table (WW-4 as currently specified). Document the rationale in v5.0 release notes (DOC-12) so future contributors don't second-guess.

- [ ] **DEC-12** v5.0 scope decision. Phase 24.5 now bundles: sovereignty deletion (B-CARE-3 schema), BYOP (B-BYOP-9/9b), eukaryotic pathogens (B-EUK-1/2/3), ML/modeling (ML-1..4), Health Observatory (OBS-1..4), wastewater module (WW-1..12), and epidemiological forecasting (EPY-S1..S3 — added 2026-05-11). That's ~28 schema changes spanning multiple domains. Options: (a) ship all as v5.0 (mega-release, one P0b migration cycle, maximum operator churn at one time); (b) split into v5.0 (original BYOP/EUK/sovereignty scope, ~8 schema changes) and v5.1 (ML/OBS/WW/EPY, ~20 schema changes, ships ~1 quarter later); (c) split by domain into v5.0 (BYOP/EUK/sovereignty), v5.1 (ML/OBS/EPY), v5.2 (WW). EPY-S items belong in v5.1 since EPY-S1 has a real FK to ML-1's `model_artifacts` and the forecasting pipelines depend on OBS-3 `external_data_sources` for epydemix-data registration. Recommendation: (b) two-release split is the sweet spot — one big breaking change for operators rather than one mega-change. WW work has high consumer-code refactor cost (WW-2a) which is cleaner to land as its own release window.

- [ ] **DEC-13** B-XXX adoption-item verification process. The 9 new wastewater adoption items in Phase 26 (B-PIGX-1, B-AQUASCOPE-1, B-WEPP-1, B-WMON-1, B-WASTPAN-1, B-ENCYC-1, B-RESPIPE-1, B-DPCR-1, B-PROBE-1) cite specific projects/papers from the 2026-05-10 LeapSpace literature review. They have NOT been individually verified for: current GitHub URL, active maintenance status, license compatibility with AGPL-3.0, and whether the comparator JACKPOT pipeline still exists in the form claimed. Decision: define a single per-item verification template (`docs/adoption_verification_template.md`) that captures URL, license, last-commit date, maintainer responsiveness, and license-compatibility outcome BEFORE any of these items moves out of "Tracked, Not Scheduled" status. Applies retroactively to all 34 existing Phase 26 B-XXX items as well.

- [ ] **DEC-14** Existing `wastewater_lineage_abundance` Freyja result rows. The current JACKPOT schema lands Freyja outputs into a typed result_type called `wastewater_lineage_abundance` (referenced by existing B-WW-1 Phase 26 item). After WW-3 adds `WastewaterTargetResult` with variant deconvolution fields, existing Freyja data could be: (a) migrated into `WastewaterTargetResult` rows (one TargetResult per detected lineage), (b) kept as parallel `wastewater_lineage_abundance` typed result alongside the new model, (c) deprecated with a sunset window. Affects WW-11 migration step plan. Recommendation: (a) migrate during WW-11 — each existing `wastewater_lineage_abundance` row becomes one `WastewaterTargetResult` row per detected lineage with `variant_detection_method = freyja`. Atomically replaces the result_type with the new typed table representation.

- [x] **DEC-15** **RESOLVED 2026-05-11 — native Streamlit reimplementation selected.** Phase 35 EPY-13 implements epyScenario UX as a JACKPOT-native Streamlit page under `frontend/pages/forecasting/scenario_explorer.py` rather than embedding scenario.epydemix.org via iframe. Rationale: works offline, integrates with JACKPOT's 6-role RBAC and audit, queries JACKPOT-derived case counts directly without round-tripping through Epistorm services, renders results using JACKPOT's existing chart conventions. Trade-off: operator-side maintenance burden for the UX, accepted because the underlying epydemix Python library does the heavy lifting — the Streamlit page is mostly parameter-collection + chart-rendering. The wireframe gate (EPY-10) keeps UX scope controlled before implementation (EPY-13).

- [ ] **DEC-16** Default Rt estimation method for Phase 35 EPY-3 pipeline — **WhiteLabRt** (MIT, two-step Bayesian back-calculation + spatial flux per Milando/White 2021), **ern** (Public Health Agency of Canada, GPL-3.0, supports both case-count and wastewater inputs), **EpiNow2** (LSHTM epiforecasts, MIT, well-established but heavier), or **epydemix-ABC-derived** (extract Rt trajectory from calibrated epydemix model). Resolved by B-WLR-1 comparison spike using Epistorm's RtEval benchmark on Massachusetts COVID 2020 + Arizona Coccidioides + wastewater-derived case-count proxies. EPY-3 implements method-registry pattern so any method can be plugged in regardless of which is the platform default. Decision documented in `docs/rt-method-comparison.md` (B-WLR-1 deliverable).

### Schema additions for wastewater surveillance module (must land with P0b)

These items execute the DEC-10 refactor plus add the population normalization biomarkers, hydraulic covariates, process-control tracking, and metagenomic profile typing that the v4.4 wastewater model lacks. All bundle into a single P0b migration cycle. Source comparative analysis: external WBE schema draft uploaded 2026-05-11 against JACKPOT v4.4 wastewater coverage; literature review in `wastewater_analaysis.md` (LeapSpace 2026-05-10). Reference standards: NWSS data dictionary, PHA4GE contextual data spec, WHO Tricycle protocol, ENVO ontology, MIxS environmental packages.

- [ ] **WW-1** Add `wastewater_collection_sites` table — persistent sampling-location entity, 1:N with `samples` (when `source_type = 'Wastewater'`). Columns: `site_id` (UUID PK), `owning_lab_id` (FK to `labs`, required — site participates in JACKPOT's existing 6-role RBAC via the owning lab; organization derives from `labs.organization_id`), `site_name` (text, required), `site_type` enum value from `WastewaterSiteTypeEnum` (per WW-9), `latitude` / `longitude` (float, WGS84, required), `geo_precision` enum (`exact` / `centroid_of_catchment` / `jittered_500m`), `served_county_fips` (multivalued text, FIPS 5-digit — preserves the multi-county info that v4.4 `WastewaterSample.county_names` could hold), `state` (text — follow JACKPOT's existing convention for state codes, US-states controlled vocab per SCH-1 when country = 'US'), `country` (text — follow JACKPOT's existing convention for country codes; confirm at implementation time whether alpha-2 or alpha-3 matches current schema; document choice in WW-9 enum reconciliation), `population_served` (integer), `catchment_area_km2` (float), `catchment_description` (text), `sewershed_id` (text — utility-defined or NWSS sewershed polygon identifier), `sewer_system_type` enum (`separate_sanitary` / `combined` / `open_drain` / `decentralized`), `treatment_plant_name`, `treatment_plant_capacity_mgd`, `industrial_input_fraction` (float, 0-1), `one_health_sector` (text, controlled vocabulary value matching existing `SectorEnum` permissible values — not an FK, since enums are referenced by value), `known_upstream_sources` (multivalued text), `nwss_site_id`, `operating_authority`, `date_established`, `is_active` (boolean), `notes`, `created_at` (timestamp), `created_by_user_id` (FK to `users`), `updated_at` (timestamp). (1-2 sessions, P0b — depends on DEC-10)

- [ ] **WW-2** Refactor existing `WastewaterSample` per DEC-10: add `site_id` FK to `WastewaterCollectionSite` (required), remove denormalized site fields (`wwtp_name`, `nwss_sewershed_id`, `sample_location_zipcode`, `county_names`, `population_served`), remove per-target qPCR fields (`pcr_target`, `pcr_gene_target`, `pcr_gene_target_ref`, `pcr_type`, `quant_stan_type`, `stan_ref`, `lod_ref`, `inhibition_method`, `num_no_target_control`) — these move to WW-3's `WastewaterTargetResult`. Retain on `WastewaterSample`: `sample_type`, `sample_matrix`, `pretreatment`, `concentration_method`, `flow_rate_mgd`, `sample_collect_time`, `pasteurized`, `env_broad_scale`, `env_local_scale`, `env_medium`. Plus all v5.0-new additions from WW-5/6/7/8 below. (1 session, P0b — depends on WW-1, WW-3, WW-11 migration)

- [ ] **WW-2a** Consumer code refactor for the WW-2 schema change. The dropped `WastewaterSample` fields (`wwtp_name`, `nwss_sewershed_id`, `sample_location_zipcode`, `county_names`, `population_served`, `pcr_target`, `pcr_gene_target`, `pcr_gene_target_ref`, `pcr_type`, `quant_stan_type`, `stan_ref`, `lod_ref`, `inhibition_method`, `num_no_target_control`) are read by multiple production modules. This item tracks the consumer-side refactor that must land in the same PR as WW-2 (otherwise the API breaks for wastewater consumers). Affected modules to audit and refactor: (a) `backend/backend/validator.py` — drop required-field checks for moved fields, add new checks per WW-12; (b) `backend/backend/pipeline_results_loader.py` — update any code reading `samples.pcr_target_*` to read from `wastewater_target_results` instead; (c) `backend/backend/routers/samples.py` and `backend/backend/routers/ingest.py` — update response shapes and request validation; (d) jackpot-nf parsers that emit `wastewater_lineage_abundance` rows — coordinate with DEC-14 migration plan; (e) Streamlit pages under `frontend/pages/` that display wastewater sample metadata (currently denormalized) — refactor to JOIN against `wastewater_collection_sites`; (f) jackpot-cli `jackpot samples` commands when source_type=Wastewater — update display fields; (g) test fixtures with hardcoded `wwtp_name`/`pcr_target` values in `tests/` — rewrite against new model. Add an end-to-end test that exercises the full ingest → result → display flow with multi-target panels. Coverage gate: ≥95% on the wastewater-touching modules after refactor. (2-3 sessions, P0b — bundle with WW-2 and WW-11)

- [ ] **WW-3** Add `wastewater_target_results` table — per-target qPCR/ddPCR result rows, 1:N with `samples` (when `source_type = 'Wastewater'`). Columns: `result_id` (UUID PK), `sample_id` (FK to `samples.sample_id`, required), `target_name` (text, required), `target_gene`, `target_organism`, `target_category` enum (required — `respiratory_virus` / `enteric_virus` / `enteric_bacteria` / `amr_gene` / `amr_mutation` / `fecal_indicator` / `population_biomarker` / `process_control`), `assay_method` enum (required — `qPCR` / `ddPCR` / `RT-qPCR` / `RT-ddPCR`), `concentration_gc_l` (float), `concentration_gc_g` (float), `log10_concentration`, `normalized_concentration`, `ct_value`, `lod_gc_l`, `loq_gc_l`, `below_lod` (boolean), `detected` (boolean, required), `variant_lineage`, `variant_detection_method` enum (`mutation_specific_qpcr` / `amplicon_sequencing` / `metagenomic_deconvolution` / `freyja` / `pigx_sars_cov_2` / `wepp_phylogenetic_placement` / `aquascope`), `variant_proportion` (float 0-1), `replicate_count` (integer), `replicate_agreement` enum (`all_positive` / `all_negative` / `mixed`), `inhibition_controlled` (boolean), `analysis_date` (date), `notes`, `created_at` (timestamp, append-only), `created_by_user_id` (FK to `users`). Append-only — re-running an assay creates a new row, never UPDATEs an existing one (matches pattern of `pipeline_results`). (1-2 sessions, P0b — depends on WW-1, DEC-10)

- [ ] **WW-4** Add `wastewater_metagenomic_profiles` table — typed entity for untargeted shotgun metagenomic results, 1:N with `samples` (when `source_type = 'Wastewater'`). Design rationale (per DEC-11): typed table chosen over a `pipeline_results` JSONB result_type because dashboards filter by integron type, plasmid replicon family, ARG class, and MAG count — all of which would be slow against JSONB. Precedent for typed tables exists in JACKPOT for clinical AMR (`amr_results`) and TB typing (`tb_typing_results`). Columns: `profile_id` (UUID PK), `sample_id` (FK to `samples.sample_id`, required), `pipeline_run_id` (FK to `pipeline_runs.run_id` — the metagenomic Nextflow run that produced this profile; matches existing JACKPOT pipeline-results provenance pattern), `sequencing_platform` enum, `read_type` enum (`short_read` / `long_read` / `hybrid`), `total_reads` (integer), `total_bases_gb` (float), `host_reads_removed_pct` (float), `taxonomic_profiler` (text — Kraken2/MetaPhlAn4/mOTUs3/Centrifuge), `taxonomic_profile_path` (text — GCS/MinIO URI), `species_richness` (integer), `shannon_diversity` (float), `amr_profiler` (text — AMRFinderPlus/CARD-RGI/ResFinder/ABRicate), `amr_database`, `amr_database_version`, `amr_profile_path` (text — hAMRonization-compatible output URI), `total_arg_types_detected` (integer), `total_arg_classes_detected` (integer), `arg_reads_per_million` (float), `mge_profiler` (text — PlasmidFinder/mobileOG-db), `integron_types_detected` (multivalued text — class 1/2/3), `plasmid_replicon_types` (multivalued text — IncF/IncHI2/IncX3 etc.), `num_mags_recovered` (integer), `num_high_quality_mags` (integer — MIMAG: >90% complete, <5% contamination), `assembler` (text — metaSPAdes/MEGAHIT/metaFlye), `binner` (text — MetaBAT2/CONCOCT/SemiBin/vRhyme), `pipeline_name`, `pipeline_version`, `analysis_date` (date), `notes`, `created_at` (timestamp, append-only), `created_by_user_id` (FK to `users`). Append-only — re-running metagenomic analysis creates a new row. (1-2 sessions, P0b — depends on WW-1, DEC-11)

- [ ] **WW-5** Add hydraulic + environmental covariate fields to refactored `WastewaterSample`: `water_temperature_c` (float), `ph` (float, 0-14), `conductivity_us_cm` (float), `turbidity_ntu` (float), `tss_mg_l` (total suspended solids, float), `bod_mg_l` (biochemical oxygen demand, float), `ammonia_mg_l` (float — secondary population biomarker), `rainfall_48h_mm` (float — 48-hour antecedent rainfall in catchment; critical confounder for combined sewer systems; sourced via `external_data_sources` OBS-3 / NOAA station linkage). (0.5 session, P0b — bundle with WW-2)

- [ ] **WW-6** Add population normalization biomarker fields to refactored `WastewaterSample`: `pmmov_gc_l` (Pepper mild mottle virus, NWSS-adopted human fecal strength biomarker), `crassphage_gc_l` (alternative human fecal biomarker). Both float, gene copies per liter. Used as denominators in `WastewaterTargetResult.normalized_concentration`. (0.25 session, P0b — bundle with WW-2)

- [ ] **WW-7** Add process control + recovery efficiency fields to refactored `WastewaterSample`: `process_control_organism` (text — BCoV/MHV/Phi6/CrAssphage/PMMoV), `recovery_efficiency_pct` (float, 0-100), `inhibition_detected` (boolean — supplements existing `inhibition_method`). Critical for distinguishing "pathogen not present" from "method failed to recover." (0.5 session, P0b — bundle with WW-2)

- [ ] **WW-8** Add chain-of-custody fields to refactored `WastewaterSample`: `collected_by` (text — operator/individual), `shipped_date`, `received_date`, `processing_lab` (text — distinct from `originating_lab` which is the sequencing lab), `storage_conditions` enum (`4C_within_24h` / `frozen_minus_80C` / `frozen_minus_20C` / `ambient` / `other`). (0.5 session, P0b — bundle with WW-2)

- [ ] **WW-9** Add new wastewater-specific enums and reconcile with existing JACKPOT enums. (1) **`WastewaterSiteTypeEnum`** (NEW enum) — `wastewater_treatment_plant`, `pump_station`, `manhole`, `building_level`, `combined_sewer_overflow`, `stormwater_outfall`, `surface_water`, `agricultural_runoff`, `aquaculture_effluent`, `slaughterhouse_effluent`, `septage`, `open_drain`, `other`. ENVO meanings annotated where they exist. Used by `wastewater_collection_sites.site_type`. (2) **Existing `WastewaterSampleTypeEnum`** (EXTEND in place) — keep existing `grab` / `composite_24hr_flow_weighted` / `composite_24hr_time_weighted` / `other` values; add new values `composite_other`, `passive_moore_swab`, `passive_trap`, `settled_solids`, `biofilm_swab`. No renaming of existing values. No new enum class — extend the existing one. (3) **`WastewaterTreatmentStageEnum`** (NEW enum) — `influent_raw`, `post_primary`, `post_secondary`, `post_tertiary`, `effluent_final`, `biosolids`, `reclaimed_water`, `not_applicable`. Distinct from existing `sample_matrix` (`SampleMatrixEnum`) which describes physical state. Both can be set independently on a sample. (4) **Existing `ConcentrationMethodEnum`** (EXTEND in place, NO renames) — existing has `ceres_nanotrap`, `membrane_filtration_MgCl2`, `ultrafiltration`, `polyethylene_glycol_precipitation`, `ultracentrifugation`, `other`. Add new values `electronegative_filtration`, `skimmed_milk_flocculation`, `adsorption_extraction`, `magnetic_bead_capture`, `no_concentration`. **Do NOT rename `polyethylene_glycol_precipitation` to `peg_precipitation`** — Postgres enum renames break existing rows and there's no SQL-level alias mechanism. Any code/UI shortening to `PEG` is a display-layer concern, not a schema change. If a future v5.x release wants the shorter name, do it as an explicit value migration (ALTER TYPE...RENAME VALUE in Postgres ≥10) with a same-PR audit of all readers. (0.5 session, P0b — bundle with WW-1/WW-2)

- [ ] **WW-10** Update `SourceTypeEnum` and `SectorEnum` for wastewater-One-Health bridging cases. Existing `SourceTypeEnum` has `Wastewater` and `Water` — keep both. Add `AgriculturalRunoff` and `AquacultureEffluent` as new values (or model these via `WastewaterCollectionSite.site_type` only — RESOLVED 2026-05-11: model via site_type only, don't add new source-type values; site_type carries the One Health bridging granularity). For existing `SectorEnum`: no changes needed (current values `clinical` / `veterinary` / `agricultural` / `environmental` / `wastewater` / `wildlife` / `research` cover all proposed `OneHealthSectorEnum` cases). `WastewaterCollectionSite.one_health_sector` references `SectorEnum`, not a new enum. (0.25 session, P0b — bundle with WW-9)

- [ ] **WW-11** Hand-write Alembic migration (per Critical Rule 2 — no `--autogenerate`) executing the WW refactor. Steps: (a) create `wastewater_collection_sites` table with all WW-1 columns; (b) **site deduplication step** — for each existing `samples` row where `source_type = 'Wastewater'`, compute a site identity key = (`wwtp_name`, `nwss_sewershed_id`, `coalesce(sample_location_zipcode, '')`). GROUP BY this key. For each group, INSERT one `wastewater_collection_sites` row from the group's denormalized fields. Resolve owning_lab_id from the modal `samples.lab` value in the group; if multiple labs share a site, pick the earliest-created sample's lab and log a WARN in migration output for manual reconciliation; (c) **county_names handling** — populate `wastewater_collection_sites.served_county_fips` (multivalued) from the FULL `samples.county_names` array (passing through a name-to-FIPS lookup table for any non-FIPS entries), NOT just the first value. Preserves the multi-county info v4.4 carried; (d) add `site_id` FK column to `samples`, populate by matching the site-identity key per row; (e) create `wastewater_target_results` table per WW-3; (f) for each existing wastewater sample, INSERT a `wastewater_target_results` row copying current `pcr_target`, `pcr_gene_target`, `pcr_type`, `quant_stan_type`, `stan_ref`, `lod_ref`, `inhibition_method`, `num_no_target_control` values. Most other fields will be NULL — that's expected (the existing schema didn't capture them); (g) **`wastewater_lineage_abundance` migration per DEC-14** — for each existing typed result row of result_type `wastewater_lineage_abundance`, INSERT one `wastewater_target_results` row per detected lineage with `variant_detection_method = freyja`, `variant_lineage` and `variant_proportion` populated from the Freyja output, `target_organism = 'SARS-CoV-2'` (or whatever the original Freyja run targeted), `target_category = 'respiratory_virus'`. Mark old `wastewater_lineage_abundance` rows as migrated (add a `migrated_to_target_result_id` column or drop after verification); (h) create `wastewater_metagenomic_profiles` table per WW-4 (empty — populated by Phase 34 parsers WW-13..17); (i) add WW-5/6/7/8 covariate/normalization/process-control/chain-of-custody columns to `samples`; (j) drop the denormalized site fields and per-target qPCR fields from `samples`. **Reversibility caveat:** down-migration restores site denormalization and the single `pcr_target` field — but the new WW-5/6/7/8 covariate/biomarker/process-control/chain-of-custody fields, the multivalued `served_county_fips`, the metagenomic profile rows, and any post-migration multi-target panels CANNOT be reconstructed in the v4.4 schema. Down-migration is therefore lossy by design and must emit a clear WARN listing the data being dropped. Document the lossy down-mig in `docs/migrations/ww-refactor-rollback.md`. Add end-to-end migration test against a 100-sample fixture including: multi-sample-per-site cases, multi-county samples, samples with existing `wastewater_lineage_abundance` Freyja results, and samples without any PCR data. Round-trip test (up-migrate → down-migrate → up-migrate again) must pass for all data that survives the lossy down-mig. (3-4 sessions, P0b — depends on DEC-14)

- [ ] **WW-12** Update `validator.py` for new conditional-required logic on the refactored model. (a) `recovery_efficiency_pct` required when `process_control_organism` is non-null. This is a same-row check, fits existing validator pattern. (b) `flow_volume_l` derivable from `flow_rate_mgd × sample_collect_duration` for composite samples — emit a tier-2 completeness check rather than a hard requirement. Same-row check. (c) **Cross-table validation for PMMoV recommendation** — `pmmov_gc_l` on `samples` is recommended (not required) when any associated `wastewater_target_results` row has `target_category` ∈ {`respiratory_virus`, `enteric_virus`}. This requires reading from a SECOND table at validation time. Current `validator.py` operates on a single sample dict; this cross-table check needs to land as a post-ingest async validator step (APScheduler job) that runs after target results are written, OR as an explicit application-layer call after both sample and target results land in the same transaction. Recommendation: same-transaction app-layer call from the ingest router after target_results insert, with the warning surfaced via the existing `notifications` table. (d) `rainfall_48h_mm` auto-population from `external_data_sources` (OBS-3) — lives in a new service module `backend/backend/wastewater/context_autopop.py`, called from the ingest router AFTER `wastewater_collection_sites` row is identified for the sample. NOAA station lookup is synchronous-with-timeout (default 2s) at ingest; on timeout or API failure, sample lands with `rainfall_48h_mm = NULL` and a notification queues a retry job. Update existing `BASE_REQUIRED` / tier-1 / tier-2 / tier-3 validator logic. (1-2 sessions, P0b — bundle with WW-2; cross-table validator step adds ~0.5 session)

### Schema additions for epidemiological forecasting (must land with P0b, v5.1 per DEC-12)

These items support Phase 35 — Epidemic Modeling and Forecasting — implementation. Bundling into P0b avoids double-migrate operator churn (same rationale as the BYOP/EUK and ML/OBS/WW bundles). All three items are append-only, integrate with JACKPOT's 6-role RBAC via `owning_lab_id`, and reuse live FK targets from rounds-1-3 schema items (ML-1 `model_artifacts`, OBS-3 `external_data_sources`). Source comparative analysis: EPISTORM software stack research 2026-05-11; literature anchored to Gozzi et al. 2025 *PLoS Comp Bio* (epydemix), Litvinova et al. 2025 medRxiv (Epistorm-Mix), Li & White 2021 *PLoS Comp Bio* (WhiteLabRt back-calculation).

- [ ] **EPY-S1** Add `scenario_interventions` table — specifies intervention sets for forward scenario projection in Phase 35 EPY-2. Columns: `id` (UUID PK), `owning_lab_id` (FK to `labs`, required — participates in 6-role RBAC), `name` (text, required — operator-meaningful label like "Schools close 2024-09-01"), `region` (text — epydemix population_name string, e.g. `United_States`, `Arizona`), `model_artifact_id` (FK to `model_artifacts.id` from ML-1, nullable — references the calibrated model the intervention applies to; null permitted for baseline-only interventions), `intervention_layer` enum (`home` / `work` / `school` / `community` / `all` — which contact-matrix layer the intervention modifies, per epydemix Tutorial 3 `add_interventions(layer=...)` semantics), `intervention_type` enum (`reduction_factor` / `parameter_override` / `compartment_override`), `start_date` (date, required), `end_date` (date, required), `reduction_factor` (float 0-1, nullable — for `reduction_factor` type), `parameter_overrides` (JSONB, nullable — for `parameter_override` type), `description` (text), `created_at` (timestamp, append-only — new rows for revisions, never UPDATE), `created_by_user_id` (FK to `users`), `notes`. (1 session, P0b — bundles with ML-1)

- [ ] **EPY-S2** Add `epidemic_forecasts` typed result table — typed entity for forward-projection trajectories produced by Phase 35 EPY-2 simulation pipeline. Matches the typed-table precedent set per DEC-11 (typed tables justified when query patterns require structured filters; here: filter by region, by intervention set, by model). Columns: `id` (UUID PK), `pipeline_run_id` (FK to `pipeline_runs.id` — existing provenance pattern), `inference_run_id` (FK to `inference_runs.id` from ML-3, nullable — null permitted for ad-hoc simulations outside the ML-3-tracked workflow), `owning_lab_id` (FK to `labs`, required — RBAC), `region` (text — epydemix population_name), `model_artifact_id` (FK to `model_artifacts.id` from ML-1, nullable — null permitted for non-calibrated simulations), `model_name` (text — SIR/SEIR/custom; redundant with model_artifact for non-null cases, required for the null case), `contacts_source` (text — `mistry_2021` / `prem_2021` / `prem_2017` / `litvinova_2025`), `intervention_set_id` (FK to `scenario_interventions.id`, nullable — null for baseline projections without interventions), `start_date` (date), `end_date` (date), `n_simulations` (integer — number of stochastic realizations), `trajectory_quantiles_path` (text — GCS/MinIO URI to CSV of per-compartment-per-date quantile values), `posterior_summary` (JSONB — calibrated parameter summary if calibration was upstream; nullable), `forecast_type` enum (`scenario_projection` / `short_term_forecast` / `retrospective_fit`), `analysis_date` (date), `notes`, `created_at` (timestamp, append-only), `created_by_user_id` (FK to `users`). Append-only — re-running creates a new row. (1 session, P0b — bundles with ML-1/ML-3)

- [ ] **EPY-S3** Add `rt_estimates` typed result table — typed entity for time-varying reproduction number estimates produced by Phase 35 EPY-3 Rt estimation pipeline. Supports multiple estimation methods via the method-registry pattern so method-vs-method comparison is queryable. Columns: `id` (UUID PK), `pipeline_run_id` (FK to `pipeline_runs.id`), `inference_run_id` (FK to `inference_runs.id` from ML-3, nullable), `owning_lab_id` (FK to `labs`, required — RBAC), `region` (text — political/admin region OR `wastewater_collection_site` UUID-as-string from WW-1 when source is wastewater concentration), `wastewater_site_id` (FK to `wastewater_collection_sites.site_id` from WW-1, nullable — populated when source_data_type is wastewater-based), `method` enum (`whitelab_back_calc` / `whitelab_spatial_flux` / `ern` / `epinow2` / `epiestim` / `epydemix_abc_derived` / `other` — extensible registry per B-WLR-1 outcome), `method_version` (text — package version string), `source_data_type` enum (`case_counts` / `hospitalizations` / `deaths` / `wastewater_concentration` / `wastewater_target_results` / `other`), `pathogen` (text — controlled vocabulary value from existing `OrganismNameEnum` where applicable, otherwise freeform), `period_start` (date), `period_end` (date), `rt_trajectory_path` (text — GCS/MinIO URI to CSV of date, rt_median, rt_lower_95ci, rt_upper_95ci), `diagnostics` (JSONB — convergence metrics, prior sensitivity, etc.), `analysis_date` (date), `notes`, `created_at` (timestamp, append-only), `created_by_user_id` (FK to `users`). Append-only — re-running estimation creates a new row. (1 session, P0b — bundles with ML-1/ML-3 and WW-1)


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

- [ ] **B-LOC-FED-1** Adopt Loculus group-based ownership pattern as an intra-instance refinement to FED-A's org-level federation controls.  Groups own sequences, users belong to multiple groups, groups can have federation policies independent of the parent organization. Lands as part of FED-D schema migration (or follows it). Reference: overview §12.3b. (1-2 sessions, with FED-D or after)

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
- [ ] **B-RTMA-3** Adopt RT-MetA's untargeted metagenomics framework as a JACKPOT pipeline-zoo entry, paired with nf-core/taxprofiler. When scoping clinical-mNGS scoring on top of taxprofiler outputs, also review HPD-Kit's NPA/NPAS scoring methodology (Que et al. 2025, `10.3389/fcimb.2025.1580165`) for the case-vs-control normalized-abundance approach — methodology only, do not vendor (Chinese database hosting + R-heavy post-processing make HPD-Kit unsuitable for JACKPOT integration). (4-6 weeks, Year 2+)

### J. GISAID-derived (overview §16.8)

- [ ] **B-GISAID-1** When exporting a dataset, auto-generate a structured Acknowledgments block citing each originating lab, sample IDs, and submission dates. Format aligned with Nature/PHA4GE recommended citation conventions. (1-2 sessions, any)

### K. 2026-05-09 strategic assessment — wholesale & build candidates

- [ ] **B-MPAS-1** Vendor MPAS / `CDCgov/tick_surveillance` pipeline as jackpot-nf submodule. Apache-2.0+CC0, Nextflow DSL2 nf-core layout. Adds wrapper.nf + parser.py + new `vector_amplicon_results` result type. Closes the vector-borne tick amplicon coverage gap (Borrelia/Babesia/Anaplasma/Ehrlichia from Ixodes ticks). Maintenance signal modest (23 commits, 3 stars/forks); confirm with 30-min spike before committing. (1 session, Phase 25 stretch / Month 3) `[2026-05-09 assessment Tier A]`
- [ ] **B-VRK-1** Build JACKPOT-native ONT-only bacterial outbreak Nextflow pipeline based on Vereecke et al. JCM 2025 protocol (`10.1128/jcm.00664-25`). NO upstream repo exists — paper provides validated recipe (dorado sup@v5.0.0 + error correction + bacterial polish → Flye → pyMLST cgMLST). Validate against PRJNA1255637. New `cgmlst_outbreak_results` result type. **Hard-blocked on GPU infra decision** (dorado is GPU-required; JACKPOT GCP Batch is x86 CPU). (4-6 pipeline sessions + 1-2 GPU-infra sessions = 5-8 total, Phase 26 / Year 2) `[2026-05-09 assessment Tier B-build]`

### L. 2026-05-09 strategic assessment — companion-tool integrations (BYO model)

- [ ] **B-PAREX-1** PaREx companion-tool wrapper for P. aeruginosa resistome analysis. Source: `https://github.com/ARPBIGIDISBA/PaREx`. **License: CC-BY-NC-SA 4.0 — incompatible with AGPL-3.0 vendoring**, so BYO-only model. Operator installs PaREx separately under academic-use terms; JACKPOT contributes Nextflow wrapper + CSV parser + new `pseudomonas_resistome_results` result type. Covers 221 chromosomal genes + PDC analyzer + OprD integrity, fills mutation-driven AMR gap that hAMRonization-normalized pipelines miss. Opt-in via `PAREX_ENABLED=true`, organism-gated to P. aeruginosa. (1-1.5 sessions, Phase 26 opt-in) `[2026-05-09 assessment Tier C-companion]`

### M. 2026-05-09 strategic assessment — pattern-only adoptions

- [ ] **B-DUO-1** Weekly genomic-epi notebook scaffolding pattern. Source: CoVaRR-NET Duotang (RMarkdown/Quarto) → port to Python (Jupyter/Streamlit) per JACKPOT's Python+Bash stance. Parameterized organism/date-range/lab notebook template at `templates/weekly_genomic_epi.ipynb`, calls JACKPOT API for sample retrieval + lineage abundance pull, HTML output for stakeholder reports. APScheduler-driven render schedule. (1.5 sessions, any) `[2026-05-09 assessment Tier C-pattern]`
- [ ] **B-MARTI-1** Real-time progressive analysis UX pattern for ONT pipelines. Source patterns: MARTi (MIT) + MMonitor. Add WebSocket endpoint at `/api/v1/pipelines/{run_id}/progressive`, "emit-while-running" Nextflow process annotation, Streamlit auto-refresh on sample detail page during RUNNING state, "live" indicator on samples table. Architecturally distinct from JACKPOT's current finalize-then-parse model — requires parallel progressive-results channel. (2 sessions infra + 1 session per progressive-aware pipeline retrofit, Phase 26+) `[2026-05-09 assessment Tier C-pattern]`
- [ ] **B-WW-1** Wastewater lineage-abundance dashboard. Source patterns: NICD-Wastewater-Genomics + andersen-lab/sd_ww_processing (Freyja-based). JACKPOT already lands Freyja outputs in `wastewater_lineage_abundance` result type — this adds the operator-facing visualization layer. Streamlit page with stacked-area lineage trajectories per sampling site, project/lab-membership filters, PNG/PDF export. (1.5 sessions, any) `[2026-05-09 assessment Tier C-pattern]`
- [ ] **B-NFTHEIA-1** Comparison spike: `theiagen/nf-theia` Nextflow plugin vs `nf-jackpot`. Both target file-tracking/reporting but with different scope (nf-theia adds multi-cloud storage abstraction + per-process JSON reports). Read source, write `docs/nf-theia-vs-nf-jackpot.md` feature comparison, selectively port useful features. (0.5 session, opportunistic) `[2026-05-09 assessment Tier C-pattern]`

### N. 2026-05-11 strategic assessment — WBE-specific tool adoption items

Source: literature review `wastewater_analaysis.md` (LeapSpace 2026-05-10) cross-referenced against Phase 26's existing 34 B-XXX items. None of these were previously tracked. All depend on Phase 24.5 WW-1..WW-12 schema refactor landing first so they have typed tables to write into.

- [ ] **B-PIGX-1** PiGx SARS-CoV-2 pipeline adoption (Schumann et al. 2022, *Sci Total Environ*). Wastewater-specific lineage deconvolution + variant calling pipeline; complements Freyja with a different deconvolution approach. Source: `https://github.com/BIMSBbioinfo/pigx_sars-cov-2`. License check before vendor decision. Compare output schema with existing `wastewater_lineage_abundance` result type — likely lands as alternate deconvolution method recorded in `WastewaterTargetResult.variant_detection_method = pigx_sars_cov_2`. (1.5-2 sessions, Phase 26; depends on Phase 24.5 WW schema) `[2026-05-11 assessment Tier C-pattern]`

- [ ] **B-AQUASCOPE-1** Aquascope wastewater lineage/variant tracking. Source: vetting needed — confirm GitHub URL and license before vendor decision. Comparator alongside Freyja and PiGx; Phase 26 item is the comparison spike, not full vendor. Write `docs/wastewater-deconvolution-comparison.md` covering Freyja vs PiGx vs Aquascope vs WEPP across accuracy, lineage resolution, runtime, dependency cleanliness. (1 session for comparison spike, Phase 26) `[2026-05-11 assessment Tier C-pattern]`

- [ ] **B-WEPP-1** WEPP phylogenetic placement adoption (Gangwar et al. 2026, *PLoS Comp Bio*). Achieves near-haplotype resolution in wastewater — meaningful differentiator vs. abundance-only methods. Vendor as a Nextflow process under jackpot-nf; output lands in `WastewaterTargetResult.variant_detection_method = wepp_phylogenetic_placement` + companion typed result table for placement uncertainty. License check before vendor. (2-3 sessions, Phase 26; depends on Phase 24.5 WW schema) `[2026-05-11 assessment Tier C-pattern]`

- [ ] **B-WMON-1** watermonitor metatranscriptomic workflow (https://github.com/waterpt/watermonitor). AI-enhanced metatranscriptomic analysis for rapid pathogenic virus + bacteria detection. Per literature review: high accuracy/speed, reproducible, widely cited. License check; compare with nf-core/taxprofiler and existing JACKPOT zoo coverage. Adoption decision contingent on whether watermonitor adds beyond nf-core/taxprofiler + nf-core/mag combination already in zoo. (1 session for comparison spike, Phase 26) `[2026-05-11 assessment Tier C-pattern]`

- [ ] **B-WASTPAN-1** WastPan (Finland) national WBE system — reference architecture analysis, NOT a tool to vendor. Per Sarekoski et al. 2024 and the literature review: WastPan covers 40% of Finland with validated protocols for viruses + bacteria + fungi + parasites + AMR genes. Write `docs/wastpan-reference-architecture.md` covering operational patterns transferable to JACKPOT operators (sampling cadence, multi-pathogen panel composition, integration with national health authorities). Companion to existing B-WW-ADV-1 wet-side advisory documentation. (1-1.5 sessions, Phase 26 reference docs) `[2026-05-11 assessment Tier C-reference]`

- [ ] **B-ENCYC-1** Encyclopaedia Cloacae (EU4S) platform analysis — reference platform comparison, NOT direct adoption. Per literature review: EU Wastewater Observatory digital platform with global pathogen catalogue + geospatial analytics. Write `docs/encyc-cloacae-comparison.md` covering geospatial analytics features potentially worth adopting in JACKPOT's wastewater dashboard (Phase 34 WW-19+). Cross-reference with Phase 26 B-PW-X Pathogenwatch geospatial features. (1 session, Phase 26 reference docs) `[2026-05-11 assessment Tier C-reference]`

- [ ] **B-RESPIPE-1** ResPipe vs nf-core/funcscan comparison spike for wastewater AMR profiling (Pereira et al. 2020, *Microbiome*). ResPipe is specifically designed for shotgun metagenomic AMR profiling; nf-core/funcscan is already in the zoo. Per literature review and Djordjevic et al. 2024, wastewater resistome profiling has specific requirements (hAMRonization compatibility, integron typing, plasmid replicon detection) that nf-core/funcscan may not optimally cover. Write `docs/respipe-vs-funcscan.md`; if ResPipe wins, vendor as a wastewater-specific AMR profiler that writes to `WastewaterMetagenomicProfile`. (1 session comparison + optional 2-3 sessions vendor, Phase 26; depends on Phase 24.5 WW schema if vendored) `[2026-05-11 assessment Tier C-comparison]`

- [ ] **B-DPCR-1** Multiplex digital PCR (dPCR) workflow adoption pattern (Malla et al. 2024, *Sci Total Environ*: 5-plex; Tiwari et al. 2022 review). Digital PCR offers improved accuracy and inhibitor resistance vs. qPCR for wastewater matrices. Pattern adoption: ensure `WastewaterTargetResult.assay_method = RT-ddPCR` / `ddPCR` is well-supported, parser handles multiplex-panel instrument outputs (Bio-Rad QX600, Stilla Naica, etc.). Add a `wastewater_dpcr_multiplex` typed result type if instrument-export parsing needs structured intermediate. (1-2 sessions, Phase 26; depends on Phase 24.5 WW schema) `[2026-05-11 assessment Tier C-pattern]`

- [ ] **B-PROBE-1** Probe-capture enrichment workflow pattern for low-abundance / emerging wastewater viruses (Kantor & Jiang 2024, *Environ Sci Technol*; Li et al. 2022, *Microbiol Spectr*). Hybrid-capture sequencing improves sensitivity for emerging viruses where untargeted metagenomics misses signal. Adoption: document the enrichment-aware pipeline pattern in `docs/wastewater-probe-capture.md`; mark `WastewaterMetagenomicProfile.notes` with capture method (Twist Comprehensive Viral Research Panel, Agilent SureSelect, etc.); ensure pipeline parsers handle enriched-library QC distinct from untargeted shotgun. (1-1.5 sessions, Phase 26 reference + pattern) `[2026-05-11 assessment Tier C-pattern]`

### O. 2026-05-11 strategic assessment — EPISTORM software stack + Rt estimation tooling

Source: research session 2026-05-11 covering EPISTORM's epydemix + epydemix-data + epyScenario + EpyForecast (Gozzi et al. 2025 *PLoS Comp Bio*) and Boston University's WhiteLabRt (Milando 2024 CRAN, Li & White 2021 *PLoS Comp Bio*). All four items support Phase 35 implementation. License compatibility verified: GPL-3.0 (epydemix, epydemix-data) and MIT (WhiteLabRt) are both compatible with JACKPOT's AGPL-3.0 in combined-work distribution. Per DEC-13, each item below has the verification template completion (`docs/adoption_verification_template.md`) as a precondition before moving out of "Tracked, Not Scheduled" status.

- [ ] **B-EPY-1** Adoption decision and integration spike for **epydemix** Python package — stochastic compartmental epidemic modeling (SIR/SEIR/custom) with built-in Approximate Bayesian Computation (ABC) calibration via rejection / budget-constrained / SMC. Source: `https://github.com/epistorm/epydemix`. License: GPL-3.0. Install: `pip install epydemix` or `conda install -c conda-forge epydemix`. Active maintenance (PLoS Comp Bio paper Nov 2025; v1.x stable). Per DEC-13, complete `docs/adoption_verification_template.md` covering URL, last-commit date, maintainer responsiveness, license-compatibility outcome. **Decision (2026-05-11): adopt — integrate as a Nextflow process for batch calibration + simulation runs via Phase 35 EPY-1/EPY-2; import as library for Streamlit page real-time scenario exploration in EPY-13.** Vendoring not needed; PyPI/conda-forge install is sufficient. EPY-1 calibration pipeline specializes ML-10 generic training-pipeline pattern with epydemix as the engine. (Adoption spike: 0.5 session for verification template; Phase 26 — depends on Phase 24.5 EPY-S2 schema landing) `[2026-05-11 assessment Tier A]`

- [ ] **B-EPY-2** Adoption decision for **epydemix-data** dataset — population age distributions + age-stratified contact matrices for 400+ locations worldwide. Contact sources: mistry_2021, prem_2021, prem_2017, litvinova_2025 (Epistorm-Mix). Source: `https://github.com/epistorm/epydemix-data`, latest v1.1.0 (Feb 2026). License: GPL-3.0. Dataset is read-only reference material (~50-100MB cached for global; ~10MB for US-only subset). Per DEC-13, complete adoption verification template. **Decision (2026-05-11): adopt — cache locally + version-pin to v1.1.0 + register in OBS-3 `external_data_sources` table per DEC-6 (per-operator) at `jackpot init` bootstrap time**. Phase 35 EPY-7 handles cache infrastructure; EPY-8 handles JACKPOT-to-epydemix region-name mapping. Per epydemix-data README §License, using contact matrices REQUIRES citing the relevant research paper for each data source (mistry_2021 → *Nat Commun* 2021; prem_2021 → *PLoS Comp Bio* 2021; prem_2017 → *PLoS Comp Bio* 2017; litvinova_2025 → medRxiv 2025.11.20.25340662). This citation requirement is a Phase 35 EPY-19 documentation deliverable. (0.25 session for adoption template; Phase 26 — depends on Phase 24.5 OBS-3 + Phase 35 EPY-7) `[2026-05-11 assessment Tier A]`

- [ ] **B-WLR-1** Comparison spike: **WhiteLabRt** (Milando/White lab, MIT license) vs **ern** (Public Health Agency of Canada, GPL-3.0) vs **EpiNow2** (LSHTM epiforecasts group, MIT). All three estimate Rt from case counts; ern and (recently) EpiNow2 also support wastewater concentrations. Use Epistorm's **RtEval** benchmark framework (`https://github.com/epistorm/RtEval`) per B-RTEVAL-1 to run all three against a common test panel: Massachusetts COVID 2020 (per Gozzi et al. 2025 Tutorial 7) + Arizona Coccidioides + wastewater-derived case-count proxies from existing JACKPOT `wastewater_lineage_abundance` data. Per DEC-13, complete adoption verification template for whichever methods are vendored. Write `docs/rt-method-comparison.md` covering accuracy, runtime, container build difficulty, support for non-COVID pathogens, and operator-friendliness. **Resolves DEC-16** (default Rt estimation method). Spike NOT a vendor commitment — Phase 35 EPY-3 implements a method-registry pattern so any method can be plugged in regardless of which is platform default. (1.5-2 sessions, Phase 26 — depends on Phase 24.5 EPY-S3 schema landing + B-RTEVAL-1 fixture vendor) `[2026-05-11 assessment Tier C-comparison]`

- [ ] **B-RTEVAL-1** Adoption decision for **RtEval** (`https://github.com/epistorm/RtEval`) as a benchmark fixture / test infrastructure component, NOT as a runtime dependency. R-based, evaluates Rt estimation methods against simulated and real data. Source: Epistorm Rt Collabathon (2024). Per DEC-13, complete adoption verification template. **Decision (2026-05-11): adopt as test infrastructure** — vendored into `tests/fixtures/rt_benchmark/` for the Massachusetts 2020 COVID backtest case in Phase 35 EPY-16 + as the methodology backing B-WLR-1 comparison spike. Integrates with Phase 32 TEST-7 (backtest/replay tests) — RtEval benchmark scenarios feed the backtest harness. Not run in CI (too expensive); run on-demand as part of Phase 35 release-gate testing. (0.5 session adoption + 1-2 sessions integration in Phase 35, Phase 26) `[2026-05-11 assessment Tier C-test-infrastructure]`

### Items intentionally NOT added (from 2026-05-09 assessment Tier D)

The following projects from the 2026-05-09 assessment were considered and rejected. Recording here so future sessions don't re-litigate:

- **Theiagen `mercury`** — overlaps with existing TOSTADAS NCBI/GISAID submission integration.
- **Theiagen `tbp-parser`** — overlaps with existing tb-profiler parser in jackpot-nf.
- **Theiagen full WDL workflows wholesale** — duplicates existing zoo coverage; blocks on Cromwell stack.
- **TAXAPRO** — subsumed by nf-core/taxprofiler.
- **HAVoC** — subsumed by viralrecon.
- **VarFind** — JACKPOT already has fixture-based parser tests with real pipeline outputs.
- **Cluster-Tracker / transmission-cluster pattern** — already covered by `B-EB-2` (JACKPOT-HC hierarchical clustering) + `B-SOLU-2` (continuous surveillance cluster computation) + `B-NCBI-3` (mint cluster accessions). No new item needed.
- **eDNAFlow, metaGOflow, SIMON, News-EDS, VA COVID-19 NLP** — out of scope (environmental biodiversity, marine, generic ML, news NLP, VHA EHR-specific).
- **Jovian wholesale Year 1** — deferred to Year 2 once Snakemake adapter lands. AGPLv3 license is a positive Year 2 signal; tracked as a Year 2 backlog item, not Phase 26.

### Phase 26 quick-win priority order (from overview §16.9)

If grabbing low-effort high-ROI items between sprints:

1. **B-PW-1** Speciator (1 session) — bacterial species ID is foundational
2. **B-PW-2** MLST/cgMLST (1-2 sessions) — closes a major bacterial gap
3. **B-PW-3** AMR libraries vendored (1 session) — curated reference data
4. **B-MPAS-1** MPAS / tick_surveillance vendor (1 session) — closes vector-borne amplicon gap, well-scoped Tier A
5. **B-GS-2** URL-encoded query state (1-2 sessions) — shareable views
6. **B-GISAID-1** Auto-Acknowledgments on export (1-2 sessions) — submission-incentive loop
7. **B-WW-1** Wastewater lineage-abundance dashboard (1.5 sessions) — leverages existing Freyja outputs in result schema
8. **B-NFTHEIA-1** nf-theia comparison spike (0.5 session) — opportunistic plugin improvement

---


## Phase 29 — ML/Modeling Infrastructure (Tracked, Not Scheduled)

**Source:** Strategy session 2026-05-11. Phased rollout designed to deploy classical anomaly detection without GPU dependency (Phase A in plan), then foundation-model-based detection (Phase B), then domain-adaptive fine-tuning (Phase C). All items here are Phase A and Phase B engineering items; Phase C–D items live in Year 2 Federation extensions below.

**Dependencies:** P0b ships ML-1 through ML-4 schema. DEC-1 through DEC-4 resolved. `pgvector` extension enabled on Cloud SQL if DEC-4 chooses pgvector.

**Architectural framing:** ML pipelines are a new pipeline category alongside bioinformatics. Same Nextflow infrastructure, same `pipeline_results` pattern. Embedding pipeline is offline batch (NOT on ingest hot path) so embedding-on-ingest does not block Scenario A (laptop) or Scenario F (CI test) deployments lacking GPU. Drift monitoring is deliberately premature for first-deployment phase; gates on having models in production long enough to actually drift.

### Nextflow pipelines

- [ ] **ML-5** Embedding pipeline (offline batch). Pulls recently-ingested samples lacking embeddings, runs the chosen foundation model from DEC-1, writes results to `embeddings` table via parser ML-12. Scheduled via APScheduler at configurable cadence (default daily). CPU-feasible for small scale via ONNX runtime if DEC-2 = ONNX; GPU-required for production scale. (3-4 sessions)

- [ ] **ML-6** Batch anomaly scan pipeline using foundation-model embeddings. Scheduled APScheduler job or Nextflow workflow. Queries samples scored in the last window, scores them via active Isolation Forest model (from `model_artifacts`), writes anomaly scores to `pipeline_results` and high-confidence anomalies to `notifications`. (2-3 sessions)

- [ ] **ML-7** Lineage growth anomaly pipeline. Daily multinomial logistic regression (MLR) or hierarchical Bayesian fit on lineage frequencies over the last 28 days. Flags lineages with growth coefficient exceeding configurable threshold. Uses numpyro for hierarchical Bayesian variant (FML-4 below extends this to federated form). Writes to `notifications`. (2 sessions)

- [ ] **ML-8** AMR fingerprint anomaly pipeline. Isolation Forest on hAMRonization output vectors. Flags samples in unusual regions of the AMR fingerprint feature space. (2 sessions)

- [ ] **ML-9** UShER placement outlier scoring pipeline. Runs on every sample at ingest (UShER is fast — 0.5-2 seconds per sample). Writes parsimony scores and placement uncertainty to `pipeline_results`. Downstream scheduled job flags high-parsimony samples as potential novel lineages. (2 sessions)

- [ ] **ML-10** Generic ML training pipeline. Nextflow workflow that takes a training-dataset reference, runs training, validates against held-out data, writes a new row to `model_artifacts` with training_data_hash, validation_metrics, artifact_uri. Used by ML-6, ML-7, ML-8 for periodic retraining. (3-4 sessions)

- [ ] **ML-11** Drift monitoring pipeline. Scheduled `alibi-detect`-based job comparing current embedding/lineage/AMR distributions to training-time distributions. Triggers retraining workflow when drift exceeds threshold. **Premature until models have been in production for several months**; track but do not schedule until ML-6/7/8 have been live for ≥3 months. (2 sessions, deferred-until-prerequisite)

### Pipeline parsers

- [ ] **ML-12** Parser for embedding pipeline output → `embeddings` table writes. Validates embedding dimensionality matches `model_artifacts` metadata. (1 session)

- [ ] **ML-13** Parser for anomaly detection pipelines (ML-6, ML-7, ML-8) → `pipeline_results` rows plus `notifications` rows for high-confidence anomalies. (1-2 sessions)

- [ ] **ML-14** Parser for ML training pipeline output (ML-10) → `model_artifacts` row registration plus initial `model_evaluations` row from held-out validation. (1 session)

### API + UI + CLI surfaces

- [ ] **ML-15** API router `backend/backend/routers/models.py` for `/api/v1/models/` — CRUD on `model_artifacts`, GET evaluations, model lifecycle transitions (active → deprecated → retired). Platform Admin only for register/retire; read-only for analysts. (2 sessions)

- [ ] **ML-16** API router extension for `/api/v1/anomalies/` — list current anomalies aggregated across all detectors, drill-down by detector, drill-down by sample. (1-2 sessions)

- [ ] **ML-17** Streamlit page: Model Registry (`frontend/pages/model_registry.py`) — browse `model_artifacts`, view evaluations, see deployment status, trigger retraining (Platform Admin only). (2 sessions)

- [ ] **ML-18** Streamlit page: Anomaly Dashboard (`frontend/pages/anomaly_dashboard.py`) — aggregated alerts from all detectors (ML-6/7/8/9), filtering by detector, sample, lineage, AMR pattern; drill-down to sample detail. Overlaps with Phase IM-1's "Anomaly Triage" page; one page may serve both. (2-3 sessions; coordinate with `B-IMMUNE-UI-1`)

- [ ] **ML-19** jackpot-cli commands: `jackpot models list`, `jackpot models register`, `jackpot models retire <id>`, `jackpot anomalies recent`, `jackpot anomalies sample <id>`. (1 session)

### Phase 29 effort summary

Total estimated: ~22-28 sessions across pipelines, parsers, API, UI, and CLI. Ships in stages — ML-5/ML-12 first (embedding offline infrastructure), then anomaly detectors ML-6/7/8/9 + parser ML-13 + UI ML-18, then training + registry ML-10/ML-14/ML-15/ML-17, finally drift monitoring ML-11 once enough live production data exists.

---

## Phase 30 — Federated ML Analytics (Tracked, Not Scheduled)

**Source:** Strategy session 2026-05-11 federation collaborative learning plan, Layer 1 (federated summary statistics). Built on top of the existing Federation/Privacy/Crypto scaffolds (FED-A landed 2026-05-08; FED-B/C/D/E + PRV-A + CRY-A pending) — does NOT replace them. **FML-X codes** are used (Federated Machine Learning) to distinguish from FED-A..E (federation substrate) and B-FED-1 (Pathoplexus adoption in Phase 26).

**Dependencies:** FED-B/C/D/E wire-up complete (federation router + tests + migration + main.py wiring). PRV-A privacy scaffold landed. Phase 29 ML pipelines operational. DEC-3, DEC-8 resolved.

**Architectural framing — three layers:**

- **Layer 1 (this phase):** Federated summary statistics — centroids, lineage frequencies, AMR fingerprint distributions, hierarchical Bayesian MLR. No FL framework needed. Rides on the existing FED-A `secure_aggregate` hook for confidentiality.
- **Layer 2 (Year 2 stretch):** True federated learning via Flower with LoRA adapters. Implemented as Track 2 concrete impl of PRV-A's `fl_aggregate` hook in `backend/backend/immune/sec/`. See Year 2 Federation extensions section below.
- **Layer 3 (Year 2 stretch):** Differential privacy via Opacus, secure aggregation (Bonawitz), TEEs. Implemented as Track 2 concrete impl of PRV-A's `dp_noise`, `track_dp_budget`, `he_compute`, `mpc_protocol` hooks. See Year 2 Federation extensions section below.

The PSI track (Trieu / `osu-crypto` adoption from collaboration discussions) is complementary, not replaced by FML-X work.

### Layer 1 schema (extends Phase 24.5 / P0b)

- [ ] **FML-1** Add three federation summary statistics tables per DEC-8 outcome: `federation_lineage_frequencies` (federation_id, lineage, period_start, period_end, count, frequency, contributing_cell_count, extension_data JSONB), `federation_amr_distributions` (federation_id, amr_gene, resistance_phenotype, period_start, period_end, count, distribution_stats JSONB, extension_data JSONB), `federation_embedding_centroids` (federation_id, model_id, period_start, period_end, centroid_vector, covariance_matrix, sample_count, extension_data JSONB). All append-only — each federation round generates new rows. (1-2 sessions, P0b — bundle with ML-1..4 if FED-D ships first; otherwise post-P0b mini-migration)

### Layer 1 services

- [ ] **FML-2** Summary stats publisher service (APScheduler job per cell). Computes lineage frequencies, AMR distributions, embedding centroids over a configurable window (default 7 days). Pushes to federation coordinator via `FederationPushJob` (extends existing push.py pattern from FED-A). (3-4 sessions)

- [ ] **FML-3** Federation coordinator service. Receives summary stats from member cells via the existing FED-B router endpoints, aggregates into federation-level statistics, writes to FML-1 tables, pushes federation-level results back to members. Aggregator hosting per DEC-3 (designated cell, rotating role, or third party). (4-5 sessions)

- [ ] **FML-4** Federation hierarchical Bayesian modeling code for lineage growth coefficients. Uses numpyro or PyMC meta-analysis pattern: per-cell coefficients aggregated into global posterior with cell-specific deviations. Extends ML-7's lineage growth model into federated form. (3-4 sessions)

- [ ] **FML-5** Federation audit trail extension to existing `audit_log`. Every summary stat exchange logged with cryptographic verification of the partner's signature. Reuses FED-A `attest_partner` hook. (1-2 sessions)

### Layer 1 API + UI

- [ ] **FML-6** API router extension for `/api/v1/federation/analytics/` — endpoints for publishing summary stats, retrieving federation-level aggregates, requesting federated lineage growth analysis. Federation API key auth for peer-to-peer endpoints; JWT for analyst-facing retrieve endpoints. (2-3 sessions)

- [ ] **FML-7** Streamlit page: Federation Analytics Dashboard (`frontend/pages/federation_analytics.py`) — member cells, exchange history, current federation-level lineage frequencies and AMR distributions, federation-vs-local divergence indicators. (2-3 sessions)

### Phase 30 effort summary

Total estimated: ~16-22 sessions. Ships incrementally: schema FML-1 → publisher FML-2 → coordinator FML-3 → API/UI FML-6/7 → hierarchical Bayes FML-4 → audit FML-5.

---

## Phase 31 — Demo + Benchmark Infrastructure (Tracked, Not Scheduled)

**Source:** Strategy session 2026-05-11 COVID-19 public demo plan and Sol cluster federation simulation feasibility analysis. Demo dataset is Arizona-scoped SARS-CoV-2 surveillance window 2021-01 through 2023-12, partitioned into simulated cells for federation testing.

**Dependencies:** Phase 29 ML pipelines operational for the ML-based components of the demo. Phase 30 federation analytics for the federation simulation. Sol allocation confirmed (DEC-9 below).

**ASU/operator-agnostic split:** Per DEC-7, ASU-specific demo code (Tempe fetcher, Maricopa-specific examples) lives in a separate `jackpot-demos` repo by default. CDC/NWSS/NCBI/NHSN fetchers stay in core because they are operator-agnostic public-data sources.

### Architectural decision

- [ ] **DEC-9** Confirm Sol cluster allocation: ~18K CPU-hours + 5-10K GPU-hours for 4-cell federation simulation over 2-3 days, ~400GB storage. Verify CHE availability and GPU queue wait times. Alternative: GCP-only simulation using preemptible nodes.

### Data ingest scripts

- [ ] **DEMO-1** `fetch_demo_data.py` — pulls NWSS metric data, NWSS concentration data, HHS legacy hospital data (frozen May 2024), NHSN HRD current hospital data, NCBI Virus SARS-CoV-2 metadata, all scoped to Arizona, via sodapy Socrata client. **Delivered in chat 2026-05-11; needs integration into `jackpot-demos` repo with tests and documentation.** (1 session)

- [ ] **DEMO-2** NCBI Datasets CLI wrapper for FASTA sequence retrieval. Pulls actual SARS-CoV-2 sequences from NCBI Virus matching the metadata fetched in DEMO-1, scoped to Arizona for the demo window. (1-2 sessions)

- [ ] **DEMO-3** Tempe Open Data fetcher (ArcGIS REST API). Pulls Tempe's publicly-published wastewater feeds (SARS-CoV-2, influenza, RSV, mpox, norovirus, opioids). ASU-specific; lives in `jackpot-demos/asu/` per DEC-7. (1-2 sessions)

- [ ] **DEMO-4** COVID-19 Forecast Hub data fetcher (reichlab/covid19-forecast-hub or successor repo). Pulls historical forecast submissions for benchmarking JACKPOT forecasts against the community. (1 session)

- [ ] **DEMO-5** CoV-Spectrum LAPIS API fetcher. Pulls lineage frequency time series for cross-validation against JACKPOT-internal lineage assignments. (1 session)

### Demo dataset construction

- [ ] **DEMO-6** Arizona-scoped SARS-CoV-2 sequence corpus (2021-01 through 2023-06). Pango-lineage-tagged via Pangolin or Nextclade. Pre-staged in `test-fixtures` GCS bucket. (2 sessions)

- [ ] **DEMO-7** Stitched hospitalization time series across HHS legacy + NHSN HRD methodology change (the May 2024 transition). Documented reconciliation approach. (1 session)

- [ ] **DEMO-8** Held-out evaluation period dataset (2023-07 through 2023-12). Used for forecast evaluation; not exposed to training. (0.5 session)

- [ ] **DEMO-9** Partitioned datasets for federation simulation. Two partition schemes: geographic (Census region) and lab-effect (synthetic sampling profile differences). Each scheme produces 4 cell-scoped subsets. (1-2 sessions)

### Sol federation simulation infrastructure

- [ ] **DEMO-10** JACKPOT Apptainer (.sif) container builds for FastAPI, PostgreSQL 16, MinIO. Built for Sol's container environment. CI workflow target to keep them current. (2-3 sessions)

- [ ] **DEMO-11** SLURM submission script for federation simulation. Single allocation, multi-node cell instantiation, hostname-based cell IDs, scratch-directory data isolation per cell. **Delivered in chat 2026-05-11; needs polish, error handling, and a teardown script.** (1-2 sessions)

- [ ] **DEMO-12** Linux `tc` (netem) WAN simulation wrapper script for cell containers. Configures 80ms ± 10ms latency, 0.01% loss, 1 Gbps cap per cell interface to simulate realistic federation conditions. (1 session)

- [ ] **DEMO-13** Globus DTN integration for inter-cell data movement on Sol — uses Sol's Globus endpoint as the transport layer. More realistic than direct TCP and matches production federation transport. (2 sessions)

- [ ] **DEMO-14** Compute budget request to ASU Research Computing for the federation simulation. Per DEC-9 outcome. (operator decision, half-session)

### Phase 31 effort summary

Total estimated: ~15-20 sessions across fetchers, dataset construction, and Sol infrastructure. Demo dataset construction (DEMO-6/7/8/9) is the longest pole; Sol infrastructure (DEMO-10..13) requires Sol allocation confirmation first.

---

## Phase 32 — Testing Infrastructure for ML/Federation/Statistical Models (Tracked, Not Scheduled)

**Source:** Strategy session 2026-05-11 testing discussion. Statistical and ML models need different testing strategies than the existing JACKPOT test suite (which is mostly unit + integration). Property-based tests for invariants, backtest/replay for time-aware models, sensitivity analysis for calibration, content-hashed benchmark datasets for reproducibility.

**Dependencies:** Phase 29 ML pipelines exist (to test). Existing pytest infrastructure unchanged — these add on top.

### Test data generators

- [ ] **TEST-1** Custom SIR generator with known parameters. Takes (N, R0, gamma, T_max, seed), produces daily case count time series. Used for R(t) backtest in TEST-8. (1 session)

- [ ] **TEST-2** FAVITES wrapper. Nextflow-wrapped Moshiri FAVITES, takes (transmission_rate, recovery_rate, mutation_rate, sample_fraction, seed), produces transmission trees + simulated sequences + sample metadata. Tests joint epi-phylo models. (3-4 sessions — FAVITES has nontrivial dependencies)

- [ ] **TEST-3** Dawg wrapper (Cartwright). Sequence-evolution-only simulator for synthetic FASTA data with biologically accurate indel models. Lighter-weight than FAVITES for tests that only need sequences. (2 sessions)

- [ ] **TEST-4** Schema-constrained metadata generator. Generates valid sample metadata using JACKPOT controlled vocabularies (Faker for identifier-like fields; constrained sampling from enums for the rest). Drop-in fixture for tests that need arbitrary valid sample metadata. (1-2 sessions)

- [ ] **TEST-5** Hypothesis property-test data infrastructure. Strategies (in Hypothesis sense) for each JACKPOT data type. Foundation for the property-based test suite TEST-6. (2 sessions)

### Test types

- [ ] **TEST-6** Property-based test suite using Hypothesis for invariants: probability sums to 1, SIR conservation laws, non-negativity of counts, deterministic reproducibility with seeds, monotonicity properties of lineage growth coefficients. (2-3 sessions)

- [ ] **TEST-7** Backtest / replay tests for time-aware anomaly detection. Historical data replayed in chronological order; no time leakage enforced via `WHERE created_at <= replay_timestamp` predicate. Tests that the detector flags known historical events (Omicron emergence, Delta wave, etc.) at the right time. (3-4 sessions)

- [ ] **TEST-8** Sensitivity analysis + calibration recovery tests for epi models. Forward-simulate from known parameters, verify fitted model recovers them within acceptable error bounds. Boundary tests (R0 = 0 → no outbreak; R0 = ∞ → full attack rate). (2-3 sessions)

- [ ] **TEST-9** Model evaluation gate tests for ML training pipeline (ML-10). Load model + versioned test dataset, assert metrics exceed documented thresholds. Becomes release gate for any model promotion in Phase 29's model lifecycle. (1-2 sessions)

### Benchmark fixtures

- [ ] **TEST-10** `test-fixtures` GCS bucket setup with versioned datasets and strict access controls. Each dataset content-hashed. Read-only for CI; write requires Platform Admin. (1 session)

- [ ] **TEST-11** Content-hashed benchmark dataset registration via `model_evaluations.evaluation_dataset_id` — the dataset hash IS the reference. Reproducibility guarantee: evaluating the same model against the same hash yields the same metrics. (1 session)

- [ ] **TEST-12** CI subset configuration. Stripped-down (small N, short T) version of the test suite runs per commit; full evaluation suite runs nightly. CI runner config in `.github/workflows/nightly-ml-tests.yml`. (1 session)

### Phase 32 effort summary

Total estimated: ~20-26 sessions. TEST-1/4/5/6 are the foundation; TEST-7/8/9 are the substantive new test types; TEST-10/11/12 are the infrastructure. Generators TEST-2/3 are heavier-lift but enable joint epi-phylo testing.

---

## Phase 33 — Outreach Documents — ASU Coalition Drafts (Tracked, Action-Pending)

**Source:** ASU coalition strategy sessions 2026-04-23 through 2026-05-11. After researcher mapping across School of Technology for Public Health, Health Observatory, Decision Theater, Center for Evolution and Medicine, College of Health Solutions, SBHSE, and Shufeldt School of Medicine, a sequenced outreach plan emerged with Health Observatory promoted to earliest contact (Engelthaler will recognize JACKPOT immediately — TGen North director, 30 years pathogen genomics, 175+ papers).

**Outreach sequence (revised 2026-05-11):**

1. Engelthaler / Sunenshine / Lant at Health Observatory (earliest contact)
2. Marc Adams at School of Technology for Public Health (lower-stakes operational contact)
3. Paaijmans Mozambique vector AMR deployment (highest-value first deployment)
4. Pathak at STPH (with Adams + Health Observatory references)
5. Scotch, Grando, LaBaer (CHS/Biodesign coalition members)
6. Decision Theater operational contacts (Jin/Wei) for Valley fever LSTM extension
7. Senior figures (Laubichler, Buetow, Yudell, Gabriel) after operational momentum is visible

### Health Observatory introductions (write first)

- [ ] **DOC-1** David Engelthaler intro document — TGen North director, Health Observatory Executive Director, 30 years pathogen genomics, 175+ papers. Lead-in: JACKPOT's NWSS compliance + dual PII gating + One Health schema + first-class wastewater module (Phase 24.5 WW-1..WW-12 + Phase 34 WW-13..WW-26 — multi-pathogen panels, persistent site entity, hAMRonization-anchored resistome with integron sentinel tracking) align with his stated mission. Show schema sufficiency analysis for H5N1 statewide consortium, Valley fever integration, and Tempe multi-pathogen wastewater panel. Reference Southwest One Health Symposium as natural venue.

- [ ] **DOC-2** Rebecca Sunenshine intro document — Health Observatory Medical Director, former Maricopa County DPH CMO, CDC EIS 2006, published on coccidioidomycosis. Lead-in: JACKPOT supports measles outbreak tracking, H5N1 case linkage (including dairy bulk milk via OBS-1), Coccidioides surveillance (including air-filter sampling protocol via OBS-2), and community-level wastewater surveillance (Phase 24.5 wastewater module) — all areas in her published portfolio. Coccidioides angle most resonant for direct work; wastewater opens broader community-health framing.

- [ ] **DOC-3** Tim Lant intro document — Health Observatory Director of Data Analytics, former BARDA Director of Division of Analytic Decision Support, led H7N9/Ebola/Zika forecasting. Lead-in: Phase 29/30 ML and federation work + Phase 35 epidemic modeling and forecasting directly relevant to his portfolio. Forecasting is his core BARDA-era domain. Two distinct angles: (1) Phase 29 ML-7/ML-8 anomaly detection on wastewater target data per McLeod et al. 2026 outlier-detection-in-dPCR pattern; (2) Phase 35 EPY-3 Rt estimation from wastewater concentration via WhiteLabRt / ern (back-calculation method), with cross-link in EPY-15 overlaying Rt on the wastewater dashboard (WW-23/WW-24); plus EPY-1/EPY-2 epydemix calibration + scenario projection for H5N1 / measles / Coccidioides forecasting at the Arizona statewide scale he'd own. JACKPOT is operationally compatible with EPISTORM ($17.5M CDC Insight Net center) which uses the same epydemix stack — direct alignment with his interest in the federal forecasting ecosystem.

### STPH introductions

- [ ] **DOC-4** Marc Adams intro document — STPH interim MPH program director / assistant dean of education. Lead-in: JACKPOT maps to seven STPH courses (TPH551 Public Health Technologies, TPH552 Systems Design, TPH550 Data Science, TPH554 AI/ML, TPH557 Ethics/Policy/Law, TPH556 Entrepreneurship, TPH593/TPH580 Applied Project/Practicum). Lower-stakes operational first contact at STPH.

- [ ] **DOC-5** Jyotishman Pathak intro document — STPH founding Dean, from Weill Cornell biomedical informatics, ACMI Fellow, founded Iris OB Health, published book on genomic and clinical data sharing. Lead-in: JACKPOT's FAIR compliance + ontology anchoring + multi-tenancy architecture matches his data-sharing thought leadership. Send AFTER Adams meeting and Health Observatory contact.

### Decision Theater introductions

- [ ] **DOC-6** Xing Jin or Fang Wei intro document — operational contacts on the Jin/Wei/Kandala/Umesh/Steele/Galgiani/Laubichler 2025 *Lancet Regional Health–Americas* Valley fever LSTM paper. Lead-in: JACKPOT can extend the LSTM model from case-count-only to strain-resolved forecasting (Coccidioides genomic data IS in JACKPOT's schema by ASU/ADHS request). Send before approaching Laubichler.

- [ ] **DOC-7** Manfred Laubichler intro document — Decision Theater Director, Global Futures Professor, School of Complex Adaptive Systems. Lead-in: federation simulation on Sol + JACKPOT's One Health framing aligns with the Global Biosocial Complexity Initiative. Send AFTER Jin/Wei operational contact establishes precedent.

### Coalition technical allies (revisions to prior drafts)

- [ ] **DOC-8** Revised Stephanie Forrest intro with explicit GenProg OSS reference (squareslab/genprog-code). Update from prior draft to recognize her as a Tier 1 OSS author with her own algorithms. Mention Driver et al. 2024 encrypted wastewater paper. Bio-immunity/cybersecurity framing maps to Phase IM-* immune platform work.

- [ ] **DOC-9** Revised Ni Trieu intro with explicit osu-crypto references (MultipartyPSI, BaRK-OPRF, SpOT-PSI). Update from prior draft to recognize Tier 1 OSS author status. Mention Amazon Research Award March 2026. PSI track is complementary to FML-X federation work.

- [ ] **DOC-10** Revised Arvind Varsani intro reframed as Cenote-Taker 3 contributor (not lead author) — Mtisza is the lead. Position: ICTV Executive Committee member, microbiomics, ASU-Halden-Scotch flu collaboration. Schema OBS-4 (ICTV taxonomy refactor) speaks to his ICTV role.

- [ ] **DOC-11** Matthew Scotch intro document — EHE Asst Director / CHS Biomedical Informatics. Highest-leverage technical ally. Author of ZooPhy, NIH R01AI164481, NSF PIPP Phase II ESCAPE Center 2024-2031. Phase 29 ML + Phase 30 federation work + ESCAPE Center mission align tightly.

### Platform documentation (write after schema/code lands)

- [ ] **DOC-12** Schema v5.0 release notes covering all new tables (ML-1..4, OBS-1..4, FML-1, FED-D additions) and additions (sovereignty deletion columns, BYOP, eukaryotic). Single document for the v5.0 release.

- [ ] **DOC-13** ML pipeline operator guide (training, registration, evaluation, deployment, retirement). Covers Phase 29 ML pipelines + ML-10 training workflow + ML-15 model registry.

- [ ] **DOC-14** Federation Layer 1 deployment guide (FML-2/3 publisher and coordinator deployment, federation key management, summary stats configuration). Builds on existing federation deployment docs from FED-A/B/C/D/E.

- [ ] **DOC-15** Sol federation simulation reproducibility guide (DEMO-10..14 Apptainer builds, SLURM scripts, tc commands, Globus integration, dataset hashes). Companion to Phase 31 demo materials.

- [ ] **DOC-16** Sam Scarpino intro document — Director of AI + Life Sciences at Northeastern University Network Science Institute, External Faculty at Santa Fe Institute since 2020, Co-PI on EPISTORM ($17.5M CDC Insight Net center, 2023-2028), former VP Pathogen Surveillance at Rockefeller Foundation, co-founder of Global.health. Lead-in: JACKPOT integrates the EPISTORM software stack (epydemix + epydemix-data + epyScenario + EpyForecast) per Phase 35; direct architectural alignment with stated EPISTORM mission of integrating wastewater + pathogen genomic + mobility data into operationally relevant forecasting models. Reference his stated work on "AI-Enhanced Wastewater Metagenomics" (Grand Challenges 2024-25), "Pathogen Detection through Aircraft and WES" (Gates 2025-26), federated learning for cross-jurisdictional wastewater surveillance. Pitch: not a deployment ask but architecture review + co-development conversation, particularly on Phase 30 FML federation aggregator hosting (DEC-3), Phase 35 EPY-6 anomaly detection on Rt deviations, and potential upstream PR opportunity (NWSS adapter for epydemix, JACKPOT-format ingest helper). Highest-probability productive SFI-adjacent conversation per 2026-05-11 strategic assessment.

- [ ] **DOC-17** Lauren Ancel Meyers intro document — Cooley Professor of Integrative Biology and Statistics at UT Austin, SFI External Faculty (~25 years), leads the $27.5M CDC Outbreak Analytics and Disease Modeling Center (sister Insight Net center to EPISTORM). Pioneer of network epidemiology applied to outbreak forecasting; designed Austin's COVID staged alert system. Lead-in: JACKPOT provides operational substrate for the kind of network-epi modeling her UT center publishes, with Phase 30 federation extending to multi-jurisdictional collaboration. Best approached via Scarpino intro (DOC-16) since the two CDC Insight Net centers coordinate; uncoordinated outreach risks them comparing notes. Pitch frame: comparison of Arizona Health Observatory (Engelthaler/Sunenshine/Lant) to her Texas Outbreak Analytics center — natural ground for collaboration on multi-state forecasting at the federal Insight Net scale. Send AFTER DOC-16 lands and Scarpino indicates whether he wants to make the introduction.

- [ ] **DOC-18** Cris Moore intro document — SFI Resident Faculty since 2012, physicist/computer scientist working at the phase-transitions-in-statistical-inference boundary. Methodological collaborator, not domain collaborator. Lead-in: Phase 29 ML-6/ML-7/ML-8 anomaly detection across phylogenetic + epidemic + AMR fingerprint signals — his work on phase transitions and message-passing approaches for recurrent-state epidemic models (Shrestha/Scarpino/Moore Phys Rev E 2015; Allard/Moore/Scarpino/Althouse/Hébert-Dufresne SIAM Review 2023) is directly applicable to the statistical regime where these detectors transition from useless to useful. Bonus: Cris is actually in residence in Santa Fe, so in-person coffee is feasible (unlike Scarpino at Northeastern and Meyers at UT Austin). Frame: 45-minute in-person conversation about anomaly detection statistical foundations — no asks beyond his read on the architecture.

### Phase 33 effort summary

Total estimated: ~11-15 sessions for the 11 outreach drafts (~1 session each, some half-session for the revisions) plus ~4 sessions for the platform documentation. Outreach drafts are bursty work; group them in 2-3 batched sessions per cluster (Health Observatory, STPH, Decision Theater, Coalition).

---

## Phase 34 — Wastewater Surveillance Module: Pipelines, Parsers, UI (Tracked, Not Scheduled)

**Source:** Strategy session 2026-05-11 round 2 — comparative analysis of external WBE schema draft (uploaded 2026-05-11) and literature review `wastewater_analaysis.md` (LeapSpace 2026-05-10) against JACKPOT v4.4 wastewater coverage. The Phase 24.5 WW-1..WW-12 schema refactor lands the entities; this phase lands the pipelines, parsers, API endpoints, and UI surfaces that exercise them.

**Dependencies:** Phase 24.5 WW-1..WW-12 schema items shipped via P0b. Existing `wastewater_lineage_abundance` Freyja result type unchanged — Phase 34 work is additive on top of it. Existing B-WW-1 in Phase 26 (Streamlit Freyja dashboard) remains valid as a separate Tier C-pattern adoption; WW-19 below extends and supersedes its scope.

**Architectural framing:** Wastewater is now a first-class One Health data stream with its own three-entity hierarchy (`wastewater_collection_sites` → `samples` (when source_type=Wastewater) → {`wastewater_target_results`, `wastewater_metagenomic_profiles`}). All new pipeline parsers (WW-13..17) write via `pipeline_results_loader.py` — matching the existing parser→loader pattern in jackpot-nf and the architecture pattern documented in `jackpot_architecture.md` (parsers never talk to the database directly). Wastewater-specific UI lives under `frontend/pages/wastewater/` as a sub-namespace.

### Pipelines and parsers (Nextflow + jackpot-nf)

- [ ] **WW-13** Multi-target qPCR/ddPCR result parser. Takes instrument exports (Bio-Rad QX600 CSV, Applied Biosystems QuantStudio, Stilla Naica, generic CSV with documented column mapping). Validates against `WastewaterTargetResult` Pydantic shape, writes via existing `pipeline_results_loader` pattern. Supports both single-target and multiplex-panel exports. Variant-deconvolution-aware: detects mutation-specific qPCR exports and populates `variant_detection_method = mutation_specific_qpcr`. (2-3 sessions, Phase 34 — depends on WW-3)

- [ ] **WW-14** Wastewater AMR resistome Nextflow pipeline. Wraps either nf-core/funcscan (default) OR ResPipe (if B-RESPIPE-1 comparison spike concludes ResPipe is superior for wastewater). The funcscan-vs-ResPipe vendor choice is itself a follow-on decision after B-RESPIPE-1 lands — track explicitly as a DEC at that time rather than implicitly in this WW item. Wastewater-specific configuration regardless of vendor: hAMRonization-mandatory output (matches Phase 26 B-NCBI-2 mandate), integron typing via IntegronFinder, plasmid replicon typing via PlasmidFinder. Writes to `wastewater_metagenomic_profiles.amr_profile_path`, `integron_types_detected`, `plasmid_replicon_types` via parser WW-15. (3-4 sessions if funcscan, 5-6 if ResPipe vendor needed first, Phase 34 — depends on WW-4, B-RESPIPE-1 comparison outcome)

- [ ] **WW-15** hAMRonization-normalized wastewater AMR parser. Takes hAMRonization-compatible output from WW-14, writes structured ARG-type / class-detected / RPM rows to `WastewaterMetagenomicProfile`. Mirror of existing clinical-AMR parser pattern but writes to wastewater profile table, not the existing clinical `amr_results` table. (1-2 sessions, Phase 34 — depends on WW-4, WW-14)

- [ ] **WW-16** MGE inventory parser. Takes IntegronFinder + PlasmidFinder + (optional) mobileOG-db outputs, writes integron and plasmid replicon multivalued fields on `WastewaterMetagenomicProfile`. Class 1 integron prevalence is the Djordjevic-flagged sentinel for anthropogenic AMR pollution. (1 session, Phase 34 — depends on WW-4)

- [ ] **WW-17** MAG quality summary parser. Takes CheckM2 / GTDB-Tk / MIMAG-compliant output from metagenomic assembly + binning step (metaSPAdes/MEGAHIT/metaFlye + MetaBAT2/CONCOCT/SemiBin), writes num_mags_recovered + num_high_quality_mags + assembler + binner fields to `WastewaterMetagenomicProfile`. (1 session, Phase 34 — depends on WW-4)

- [ ] **WW-18** Wastewater variant deconvolution chain — orchestrates Freyja + (per B-WEPP-1 outcome) WEPP + (per B-PIGX-1 outcome) PiGx SARS-CoV-2 + (per B-AQUASCOPE-1 outcome) Aquascope across the same input samples; writes per-method variant proportion rows to `WastewaterTargetResult` with distinct `variant_detection_method` values so method-vs-method comparison is queryable. (2-3 sessions, Phase 34 — depends on WW-3 + Phase 26 B-WEPP-1 / B-PIGX-1 / B-AQUASCOPE-1 outcomes)

### API endpoints

- [ ] **WW-19** API router `backend/backend/routers/wastewater.py` for `/api/v1/wastewater/sites/` — CRUD on `wastewater_collection_sites`. RBAC follows JACKPOT's existing 6-role pattern via `owning_lab_id` (WW-1): Lab Director and Researcher roles within the owning lab can create/edit sites in that lab's scope; Lab Analyst can read; Platform Admin can manage cross-lab. Implementation pattern matches existing `samples` router authorization. Plus `GET /api/v1/wastewater/sites/{site_id}/samples` for site-scoped sample listing, gated by the same RBAC. (1-2 sessions, Phase 34)

- [ ] **WW-20** API router extension for `/api/v1/wastewater/targets/` — list `wastewater_target_results` rows with filters on `sample_id`, `target_organism`, `target_category`, `variant_lineage`, `variant_detection_method`. RBAC: same as sample-detail visibility (lab membership + sharing_level). Time-series endpoint `GET /api/v1/wastewater/sites/{site_id}/targets/timeseries` returns concentration trajectories per target with the same lab/site-scoped authorization. (1-2 sessions, Phase 34)

- [ ] **WW-21** API router extension for `/api/v1/wastewater/metagenomic/` — list and retrieve `wastewater_metagenomic_profiles` rows; per-profile drill-down into AMR profile path, integrons, plasmid replicons, MAG quality. RBAC: same as sample-detail visibility (lab membership + sharing_level on the parent sample). (1 session, Phase 34)

### Streamlit UI surfaces

- [ ] **WW-22** Streamlit page: WastewaterCollectionSite registry + map view (`frontend/pages/wastewater/sites.py`). Folium or Plotly map of sites colored by `site_type` or `one_health_sector`, with site-level summary panels (population served, last sample date, target panel breadth). Replaces the per-site filter that B-WW-1 currently bolts onto the existing lineage dashboard. (2-3 sessions, Phase 34 — supersedes part of B-WW-1's site-filter logic)

- [ ] **WW-23** Streamlit page: qPCR target time series (`frontend/pages/wastewater/targets.py`). Per-site, per-target concentration trajectories (gc/L and PMMoV-normalized) with multi-target overlays, log-scale toggle, lod/loq markers, rainfall overlay from `external_data_sources` (OBS-3) when available. (2-3 sessions, Phase 34)

- [ ] **WW-24** Streamlit page: lineage abundance dashboard (`frontend/pages/wastewater/lineages.py`). Extends and replaces B-WW-1's scope: stacked-area lineage trajectories per site (existing Freyja-based) plus method-comparison view (Freyja vs WEPP vs PiGx vs Aquascope per WW-18). PNG/PDF export. When this page ships, the same PR closes B-WW-1 in Phase 26 as superseded. (2-3 sessions, Phase 34 — supersedes B-WW-1)

- [ ] **WW-25** Streamlit page: resistome dashboard (`frontend/pages/wastewater/resistome.py`). Per-site / per-time-window views of total ARG types detected, ARG-class breakdown, class-1-integron prevalence (Djordjevic sentinel), plasmid replicon family tracking (IncF / IncHI2 / IncX3 emergence). (2-3 sessions, Phase 34 — depends on WW-15, WW-16)

### CLI surfaces

- [ ] **WW-26** jackpot-cli commands: `jackpot ww sites list`, `jackpot ww sites register`, `jackpot ww samples for-site <site_id>`, `jackpot ww targets recent --target-organism <name>`, `jackpot ww resistome site <site_id>`, `jackpot ww ingest-qpcr <csv_file> --site-id <site_id>`. (1-2 sessions, Phase 34)

### Phase 34 effort summary

Total estimated: ~20-30 sessions across parsers (WW-13..17), Nextflow pipelines (WW-14, WW-18), API endpoints (WW-19..21), Streamlit UI (WW-22..25), and CLI (WW-26). Phase ships incrementally: WW-13 multi-target qPCR parser is the highest-immediate-value standalone item (works on day 1 of post-P0b schema). WW-22 site registry page is the operator-onboarding gate. WW-24 lineage dashboard supersedes existing B-WW-1 and should be coordinated as a single PR with B-WW-1's owner.

---

## Phase 35 — Epidemic Modeling and Forecasting (Tracked, Not Scheduled)

**Source:** Strategy session 2026-05-11. Integrates the EPISTORM software stack (epydemix, epydemix-data, epyScenario, EpyForecast — Vespignani / Scarpino group at Northeastern, CDC Insight Net center) plus WhiteLabRt for Rt estimation (Laura White lab, Boston University). Schema items live in Phase 24.5 (EPY-S1, EPY-S2, EPY-S3); implementation work lives here as EPY-X items.

**Dependencies:** Phase 24.5 EPY-S1/S2/S3 schema items shipped via P0b (v5.1 per DEC-12). Phase 24.5 ML-1 `model_artifacts`, ML-3 `inference_runs`, OBS-3 `external_data_sources`, WW-1 `wastewater_collection_sites` all shipped — Phase 35 references all four as live FK targets. Phase 29 ML-10 generic training pipeline must ship before EPY-1 (EPY-1 specializes ML-10's pattern with epydemix as engine). Phase 32 TEST-6/TEST-7/TEST-8 testing infrastructure must ship before EPY-16/EPY-17/EPY-18 (Phase 35 tests integrate with Phase 32 harnesses). Phase 34 WW-23/WW-24 must ship before EPY-15 wastewater cross-link. Phase 26 B-EPY-1/B-EPY-2/B-WLR-1/B-RTEVAL-1 adoption verification templates completed before scheduling (per DEC-13). DEC-16 (default Rt method) resolved by B-WLR-1 comparison spike — default value remains configurable post-decision via method-registry pattern in EPY-3.

**Architectural framing:** Two distinct epidemic-modeling capabilities, both first-class:

1. **Compartmental epidemic modeling via epydemix** — stochastic SIR/SEIR/custom models with ABC calibration against JACKPOT-derived case counts; forward scenario projection under intervention assumptions. EPY-1 calibration pipeline specializes Phase 29 ML-10 generic training-pipeline pattern with epydemix as the engine, writing posterior summaries to `model_artifacts` (ML-1) + diagnostics to `model_evaluations` (ML-2) + provenance to `inference_runs` (ML-3). EPY-2 simulation pipeline writes to `epidemic_forecasts` (EPY-S2). Long-running (hour-scale for ABC-SMC, minute-scale for simulation), async-job pattern matching JACKPOT's existing long-running pipeline conventions.
2. **Rt estimation via method-registry** — pluggable Rt estimators (WhiteLabRt default subject to B-WLR-1 outcome resolving DEC-16; ern, EpiNow2, EpiEstim alternates) wrapped uniformly as Nextflow processes (EPY-3), each writing to `rt_estimates` typed result table (EPY-S3). Method-registry pattern means operators can swap defaults without code changes.

**epyScenario integration approach (DEC-15 RESOLVED 2026-05-11):** JACKPOT-native Streamlit reimplementation under `frontend/pages/forecasting/` rather than iframe embed to scenario.epydemix.org. Reuses the epydemix Python library directly; renders results inline using JACKPOT's existing chart conventions; works offline; integrates with RBAC/audit; queries JACKPOT-derived case counts directly without round-tripping through Epistorm services. EPY-10 (wireframe) + EPY-13 (implementation).

**EpyForecast desktop app integration:** Out of scope for backend integration (downloadable binary distributed from epi-pop.org). Phase 35 ships a one-directional export workflow: JACKPOT-derived case counts → CSV format → manual import into EpyForecast desktop. EPY-22 deferred until an operator explicitly asks; format-investigation prereq.

**License + multi-arch note:** epydemix is GPL-3.0, WhiteLabRt is MIT, both compatible with AGPL-3.0 in combined-work distribution. AGPL-3.0 source-availability extends to combined work — operator deployment guide (EPY-20) covers this. WhiteLabRt uses STAN via rstan; STAN binaries are architecture-specific (x86_64 vs ARM64). Container image for EPY-3 must be multi-arch built; pre-build STAN compilation into the image at build time, not runtime (rstan compilation takes 10-30 minutes per fresh build).

**Conceptual distinction from existing Phase 29 ML work:** Phase 29 ML-7 (lineage growth anomaly) fits multinomial logistic regression on lineage frequencies (relative growth). Phase 35 EPY-3 fits Rt from case counts (absolute transmissibility). Both are time-series inference on epi data but address different questions. Phase 29 ML-6/ML-7/ML-8 anomaly detection can consume Phase 35 EPY-3 Rt estimates as additional input features — natural integration point, not duplication.

### Nextflow pipelines (calibration + simulation + Rt)

- [ ] **EPY-1** epydemix calibration Nextflow pipeline (`pipelines/epydemix_calibration/main.nf`). Specializes Phase 29 ML-10 generic training-pipeline pattern with epydemix as the engine. Input: target time series (case counts / hospitalizations / deaths from JACKPOT samples aggregated by epiweek) + prior distributions YAML + model specification YAML + region (epydemix population_name via EPY-8 mapping). Calls `epydemix.calibration.ABCSampler` with `ABC-SMC` algorithm per Gozzi et al. 2025 Tutorial 4. Output: posterior samples (HDF5 or Parquet), fitted parameter point estimates JSON, calibration diagnostics JSON. **Compute reality: ABC-SMC is hour-scale for non-trivial models** — uses JACKPOT's existing long-running async-job pattern (status polling, not synchronous request/response). Default ABC-SMC budget: 1000 simulations × 10 SMC generations = ~10K runs; configurable. On completion, registers a new row in `model_artifacts` (ML-1) with `artifact_uri` pointing to the posterior HDF5 + model spec YAML, `validation_metrics` containing ABC convergence diagnostics, plus a `model_evaluations` (ML-2) row with calibration loss metrics, plus an `inference_runs` (ML-3) row tracking the calibration run. (3-4 sessions, Phase 35 — depends on EPY-S1 + EPY-S2 + ML-1 + ML-3 + ML-10 + B-EPY-1)

- [ ] **EPY-2** epydemix forward simulation / scenario projection Nextflow pipeline (`pipelines/epydemix_simulation/main.nf`). Input: calibrated parameter set (from EPY-1 output via `model_artifact_id` lookup OR freeform JSON for ad-hoc runs) + intervention set (from `scenario_interventions` row EPY-S1) + region. Runs `model.run_simulations(Nsim=100, ...)` with intervention specs converted to `add_interventions(...)` calls per epydemix Tutorial 3. Output: per-compartment quantile trajectories CSV (date, compartment, quantile, value), per-realization full trajectories if requested, simulation metadata JSON. Lighter compute than calibration — minute-scale per run. Written via parser EPY-5 to `epidemic_forecasts` typed result table (EPY-S2). (2-3 sessions, Phase 35 — depends on EPY-S1 + EPY-S2 + ML-1 + B-EPY-1)

- [ ] **EPY-3** Rt estimation Nextflow pipeline with method-registry pattern (`pipelines/rt_estimation/main.nf`). Input: case count time series (from JACKPOT samples aggregated by epiweek) OR wastewater concentration time series (from `wastewater_target_results` WW-3 with `target_category = respiratory_virus` or `enteric_virus`, OR from existing `wastewater_lineage_abundance` rows pre-WW-11-migration) + serial interval parameters + method name. Method registry initially supports `whitelab_back_calc`, `whitelab_spatial_flux` (per WhiteLabRt); extensible by registering new Nextflow process aliases for `ern`, `epinow2`, etc. Default method per DEC-16 resolution via B-WLR-1. **Container build strategy:** custom Docker image `jackpot/rt-estimation:1.0` based on `rocker/r-ver:4.3` with rstan + WhiteLabRt + ern + EpiNow2 pre-installed at image build time, multi-arch built (linux/amd64 + linux/arm64). Output written via parser EPY-6 to `rt_estimates` typed result table (EPY-S3). (3-4 sessions Nextflow + 1-2 sessions container build = 4-6 total, Phase 35 — depends on EPY-S3 + B-WLR-1 + DEC-16)

### Parsers

- [ ] **EPY-4** Parser for epydemix calibration output (`backend/backend/parsers/epydemix_calibration_parser.py`). Validates epydemix `Results.get_posterior()` / `Results.get_diagnostics()` outputs against Pydantic models; writes structured posterior summary JSON to GCS/MinIO; registers `model_artifacts` (ML-1) + `model_evaluations` (ML-2) + `inference_runs` (ML-3) rows per EPY-1's specialization of the ML-10 pattern. Append-only — re-running calibration creates a new posterior + new ML-1 row, never UPDATEs an existing one. (1-1.5 sessions, Phase 35 — depends on EPY-1 + ML-1 + ML-2 + ML-3)

- [ ] **EPY-5** Parser for epydemix simulation output (`backend/backend/parsers/epydemix_simulation_parser.py`). Validates `Results.get_quantiles_compartments()` CSV against expected columns (date, compartment, quantile, value); writes through `pipeline_results_loader` to `epidemic_forecasts` (EPY-S2) rows. (1 session, Phase 35 — depends on EPY-2 + EPY-S2)

- [ ] **EPY-6** Parser for WhiteLabRt / ern / EpiNow2 output (`backend/backend/parsers/rt_estimation_parser.py`). Method-aware parser that handles each library's output convention (WhiteLabRt: `summarize_rt(fit)` returns date + median + CI; ern: `ern::estimate_R()` returns similar shape; EpiNow2: `epinow2::epinow()` returns nested list). Writes to `rt_estimates` rows (EPY-S3). When `source_data_type = wastewater_concentration`, populates `wastewater_site_id` FK to WW-1's `wastewater_collection_sites`. (1.5-2 sessions, Phase 35 — depends on EPY-3 + EPY-S3 + WW-1)

### Service / infrastructure

- [ ] **EPY-7** epydemix-data local cache infrastructure + OBS-3 registration. `scripts/cache_epydemix_data.py` clones the GitHub repo at version-pinned tag (v1.1.0 per B-EPY-2), verifies checksum against tag commit SHA, writes to a configurable cache directory (default `~/.cache/jackpot/epydemix-data/`). `jackpot init` invokes this during operator bootstrap for the operator's relevant region subset AND registers an `external_data_sources` (OBS-3) row per DEC-6 (per-operator) with `source_name = 'epydemix-data'`, `base_url = 'https://github.com/epistorm/epydemix-data'`, `license = 'GPL-3.0'`, `allowed_use = 'public'`, version-pinned to v1.1.0. (1-1.5 sessions, Phase 35 — depends on OBS-3 + B-EPY-2)

- [ ] **EPY-8** Location name mapping between JACKPOT region fields and epydemix `population_name` strings. epydemix uses underscored names like `"United_States"`, `"Arizona"`, `"Maricopa_County"`. JACKPOT samples have `country` / `state` / `county_names` (multivalued) fields. Mapping module `backend/backend/services/region_mapping.py` provides `jackpot_to_epydemix(country, state, county_names) -> str` with validation against `epydemix-data/locations.csv` (loaded from EPY-7 cache). Returns first valid match in resolution order: county > state > country. Errors loudly when no match exists. Reused by EPY-1/EPY-2/EPY-3 for all forecasting work. (1 session, Phase 35 — depends on EPY-7)

### API endpoints

- [ ] **EPY-9** API router `backend/backend/routers/forecasting.py` for `/api/v1/forecasting/`. Endpoints: `POST /calibrations` (kick off EPY-1 calibration job — async via existing long-running-pipeline pattern, creates `inference_runs` ML-3 row, returns job_id), `GET /calibrations/{job_id}` (status + posterior summary + linked `model_artifacts` ML-1 row), `POST /scenarios` (kick off EPY-2 simulation, creates new `scenario_interventions` EPY-S1 row if intervention spec provided inline), `GET /scenarios/{forecast_id}` (retrieve `epidemic_forecasts` EPY-S2 row + linked trajectory), `POST /rt-estimates` (kick off EPY-3 Rt estimation), `GET /rt-estimates/{estimate_id}` (retrieve `rt_estimates` EPY-S3 row + linked trajectory), `GET /rt-estimates?region={r}&method={m}&pathogen={p}` (filtered list). RBAC: same as `samples` router authorization — lab membership + sharing_level on the underlying data, scoped by `owning_lab_id` on EPY-S1/S2/S3 rows. (2-3 sessions, Phase 35 — depends on EPY-1/2/3 + EPY-S1/S2/S3 + ML-3)

### Streamlit UI

- [ ] **EPY-10** UX wireframe for scenario explorer page. Single design document `docs/ui/scenario-explorer-wireframe.md` covering: parameter input mode (form vs YAML upload), intervention specification UI (date range + layer + reduction factor, writes to EPY-S1 `scenario_interventions`), output rendering (quantile fan charts, intervention vs baseline overlay, region selector with EPY-8 epydemix-name autocomplete), workflow integration (load existing calibrated model via `model_artifact_id` FK to ML-1 → specify interventions → run via EPY-9 → view → save scenario as new EPY-S1 row). NOT implementation — design only. Required as gate before EPY-13. (1 session, Phase 35 — design-only)

- [ ] **EPY-11** Streamlit page: Calibration kickoff and posterior visualization (`frontend/pages/forecasting/calibration.py`). UI for kicking off EPY-1 calibration jobs: region selector (with EPY-8 epydemix-data location-name autocomplete), target data type (case counts vs hospitalizations vs deaths) + JACKPOT data range picker, prior specification (5-7 parameters with sensible defaults per Gozzi et al. 2025 Tutorial 4 priors), ABC budget configuration, job status polling via EPY-9 GET endpoints, posterior distribution plots (corner plots via `epydemix.visualization.plot_posterior_distribution_2d`), parameter point-estimate display, "model artifact registered" confirmation (writes to ML-1 via EPY-4 happens server-side). Visible from the Model Registry page (Phase 29 ML-17) once ML-17 ships — calibrated epydemix models are first-class model artifacts. (2-3 sessions, Phase 35 — depends on EPY-9 + ML-1)

- [ ] **EPY-12** Streamlit page: Rt dashboard (`frontend/pages/forecasting/rt_dashboard.py`). Per-region Rt trajectory plots with credible-interval bands (data from `rt_estimates` EPY-S3 via EPY-9 GET), multi-method overlay (showing all methods that have been run for a given region+source+pathogen — useful as B-WLR-1 progresses and DEC-16 stabilizes), source-data type filter (case counts vs wastewater), pathogen filter, PNG/PDF export with citation block per EPY-19. Cross-link from the Sample Detail page to "Estimate Rt for this pathogen+region" pre-fills the EPY-9 kickoff form. (2 sessions, Phase 35 — depends on EPY-9 + EPY-10 wireframe gate)

- [ ] **EPY-13** Streamlit page: Scenario explorer (`frontend/pages/forecasting/scenario_explorer.py`). Per EPY-10 wireframe. Full implementation of: load a calibrated model (from EPY-11 output OR by selecting a `model_artifacts` ML-1 row), specify interventions via UI (writes new row to `scenario_interventions` EPY-S1), run forward simulation via EPY-9 POST `/scenarios`, render quantile fan charts from `epidemic_forecasts` EPY-S2, save scenario for reuse. **This is the JACKPOT-native replacement for scenario.epydemix.org per DEC-15 RESOLVED 2026-05-11.** (3-4 sessions, Phase 35 — depends on EPY-9 + EPY-10 wireframe gate + ML-1)

### CLI

- [ ] **EPY-14** jackpot-cli commands: `jackpot forecast calibrate --region <name> --target <type> --start <date> --end <date>` (kick off EPY-1), `jackpot forecast scenario --model-id <ml1_uuid> --interventions <yaml> --horizon <days>` (kick off EPY-2), `jackpot forecast rt --region <r> --method <m> --pathogen <p> --source <s>` (kick off EPY-3), `jackpot forecast list --type {calibrations|scenarios|rt}` (list runs), `jackpot forecast show <id>` (retrieve detail), `jackpot data download epydemix --version v1.1.0` (invoke EPY-7 cache), `jackpot data list epydemix-locations` (show available region names). (1-2 sessions, Phase 35 — depends on EPY-9)

### Cross-links to existing JACKPOT features

- [ ] **EPY-15** Cross-link: extend Phase 34 wastewater dashboards with Rt overlay panels. (a) WW-23 qPCR target time series page (`frontend/pages/wastewater/targets.py`) gains an optional Rt-overlay toggle — when toggled on for a site+target combination, fetches `rt_estimates` EPY-S3 rows where `wastewater_site_id` matches and `pathogen` matches the target's organism, renders Rt trajectory on a second y-axis. (b) WW-24 lineage abundance dashboard (`frontend/pages/wastewater/lineages.py`) gains a "View Rt for this site" button → navigates to EPY-12 dashboard pre-filtered to that site. (c) From EPY-12 Rt dashboard, "View concentration time series" reverse cross-link → WW-23 pre-filtered. (1-2 sessions, Phase 35 — depends on EPY-12 + WW-23 + WW-24)

### Testing infrastructure

- [ ] **EPY-16** Massachusetts 2020 COVID backtest fixture integrated with Phase 32 TEST-7 backtest/replay harness. Per Gozzi et al. 2025 *PLoS Comp Bio* §case study, calibrate epydemix SEIR to MA weekly COVID deaths Q1-Q2 2020 (data source: `https://raw.githubusercontent.com/epistorm/epydemix/main/tutorials/data/massachusetts_data/MA_deaths.csv`). Compare posterior to published parameter estimates. Becomes release-gate test for EPY-1: changes to ABC implementation must reproduce within published-paper tolerance. Fixture stored in `tests/fixtures/epydemix_backtest/` (small enough to commit). Reuses TEST-7's no-time-leakage predicate (`WHERE created_at <= replay_timestamp`) so the backtest can run as part of the TEST-7 chronological-replay suite. (1-2 sessions, Phase 35 — depends on EPY-1 + Phase 32 TEST-7)

- [ ] **EPY-17** Hypothesis property tests for ABC calibration invariants, registered with Phase 32 TEST-6 Hypothesis suite. Properties: posterior samples are within prior support; posterior is centered closer to truth than prior for synthetic data with known parameters (Gozzi et al. 2025 §example 2 pattern); ABC-SMC convergence (effective sample size grows across generations); deterministic reproducibility with fixed seed. Reuses TEST-8 calibration-recovery harness for the "centered closer to truth" property. (1-2 sessions, Phase 35 — depends on EPY-1 + Phase 32 TEST-6 + TEST-8)

- [ ] **EPY-18** Resource-budgeting tests for calibration timeouts. EPY-1 must respect a configurable wall-clock budget; tests verify timeout enforcement, partial-result preservation on timeout, and that posterior summary marks "incomplete convergence" when budget exhausted before SMC generations finish. (1 session, Phase 35 — depends on EPY-1)

### Documentation

- [ ] **EPY-19** Citation requirements documentation (`docs/forecasting/citation-requirements.md`). Per epydemix-data README §License (B-EPY-2), using contact matrices requires citing the relevant source paper. Document covers: mistry_2021 → *Nat Commun* 2021; prem_2021 → *PLoS Comp Bio* 2021; prem_2017 → *PLoS Comp Bio* 2017; litvinova_2025 → medRxiv 2025.11.20.25340662. Plus epydemix itself: Gozzi et al. 2025 *PLoS Comp Bio* 21(11):e1013735. JACKPOT auto-attaches citation block to any forecast result exported as PNG/PDF (implementation hook in EPY-12, EPY-13). (0.5 session, Phase 35)

- [ ] **EPY-20** Operator deployment guide for forecasting pipelines (`docs/deploy/forecasting-stack.md`). Covers: epydemix-data cache setup via EPY-7, OBS-3 registration step at `jackpot init`, Rt estimation container deployment (multi-arch ARM64 + x86_64), ABC-SMC compute budget guidance per region size, AGPL-3.0 + GPL-3.0 combined-work source-availability requirements for distributed operator deployments, Phase 35 dependency on Phase 29 ML-10 + Phase 32 TEST-6/7/8 + Phase 34 WW-23/24 being deployed. (1.5 sessions, Phase 35 — depends on EPY-7 + EPY-3)

- [ ] **EPY-21** User guide for scenario explorer page (`docs/ui/scenario-explorer-user-guide.md`). Walks through: load calibrated model from EPY-11 / Model Registry (ML-17), specify school-closure intervention, run forward projection, compare to no-intervention baseline, save scenario for reuse. Screenshots of the EPY-13 page. (1 session, Phase 35 — depends on EPY-13)

### Deferred until requested

- [ ] **EPY-22** EpyForecast desktop app export workflow. Investigation prereq: confirm what file format the EpyForecast desktop app imports (download installer from epi-pop.org, examine import UI). If reasonable format (CSV with documented schema), implement `jackpot export forecast-input --target epyforecast` CLI command + workflow doc. **Deferred until an operator explicitly asks** — out-of-scope for Phase 35 initial release. (Investigation: 0.5 session; implementation if proceeds: 0.5-1 session; doc: 0.5 session)

### Phase 35 effort summary

Total estimated: ~30-40 sessions across pipelines (EPY-1/2/3), parsers (EPY-4/5/6), service infrastructure (EPY-7/8), API (EPY-9), UI (EPY-10/11/12/13), CLI (EPY-14), cross-links (EPY-15), testing (EPY-16/17/18), docs (EPY-19/20/21), and the deferred EpyForecast item (EPY-22). Phase ships incrementally: EPY-3 Rt estimation is the highest-immediate-value standalone item once the container image is built (EPY-3 + EPY-6 + EPY-12 + EPY-9 partial = minimal Rt MVP). epydemix calibration + simulation (EPY-1 + EPY-2 + parsers + scenario explorer EPY-13) is the larger second deliverable. Phase 35 is gated on Phase 24.5 EPY-S1/S2/S3 schema landing in P0b (v5.1), Phase 29 ML-10 generic training pipeline shipping (for EPY-1 specialization), Phase 32 TEST-6/7/8 testing infrastructure shipping (for EPY-16/17), and Phase 34 WW-23/24 shipping (for EPY-15 cross-link). Implementation cannot start until those prerequisites land.

---

## Year 2 Federation extensions (Track 2 implementations of existing PRV-A / CRY-A hooks)

**Source:** Strategy session 2026-05-11 federation/FL plan, Layers 2 and 3.

These are **not new infrastructure** — they are concrete Track 2 implementations of hooks already defined in the existing PRV-A (Privacy scaffold) and CRY-A (Crypto scaffold) work landed/planned 2026-05-08. They live in `backend/backend/immune/sec/` per the existing Track 1 / Track 2 framing. The Track 1 / Track 2 architectural separation means the substrate (FED-A/PRV-A/CRY-A) ships first as null-hook scaffolds; these Y2 items swap in concrete AIS-aware implementations via dependency injection without changing any Track 1 code.

### Federated learning (Layer 2)

- [ ] **FML-Y2-1** Concrete Track 2 implementation of PRV-A's `fl_aggregate(local_updates)` hook in `backend/backend/immune/sec/fl_aggregate.py`. Uses Flower (`flwr`) as the FL framework. Per-cell client + coordinator-side server. Reuses existing FED-A `secure_aggregate` hook for confidentiality. (8-10 sessions — large effort)

- [ ] **FML-Y2-2** LoRA adapter management via `peft` library. Versioning, storage, lifecycle for low-rank adapters trained per cell and federation-wide. Adapters stored in `model_artifacts` with new `model_family` enum value (`lora_adapter`). (3-4 sessions)

- [ ] **FML-Y2-3** Flower training round orchestration via Nextflow — wraps Flower rounds in existing Nextflow pattern so they appear in `pipeline_runs` with full audit trail. (3-4 sessions)

- [ ] **FML-Y2-4** Byzantine-robust aggregation method selection — Krum, Trimmed Mean, Median, Bulyan, FLTrust. Pluggable behind `fl_aggregate` hook. (2-3 sessions)

### Differential privacy (Layer 3 — DP)

- [ ] **FML-Y2-5** Concrete Track 2 implementation of PRV-A's `dp_noise(query_result, sensitivity)` hook using Opacus for DP-SGD. Privacy budget accounting via `track_dp_budget` hook. (4-5 sessions)

### Secure aggregation and TEE (Layer 3 — cryptographic)

- [ ] **FML-Y2-6** Concrete Track 2 implementation of secure aggregation protocol (Bonawitz et al. 2017). Supported natively by Flower; this item wires it through PRV-A's hook surface. (3-4 sessions)

- [ ] **FML-Y2-7** TEE-hosted aggregator using GCP Confidential Computing. Implements CRY-A's TEE attestation evidence verification hook. Operator-optional. (4-5 sessions)

### Foundation model fine-tuning (Phase C-D of the ML plan)

- [ ] **FML-Y2-8** Domain-adaptive pretraining of foundation model on accumulated JACKPOT corpus (Phase C). Federated form uses FML-Y2-1 + FML-Y2-2. Centralized form runs as a single ML-10 training pipeline run. (large effort, research-engineering boundary)

- [ ] **FML-Y2-9** Task-specific fine-tuning (Phase C) for lineage classification or AMR-from-sequence prediction. Builds on FML-Y2-8 pretrained model. (large effort)

- [ ] **FML-Y2-10** Joint epi-phylo anomaly detection (Phase D). Research-stage, not engineering. Track as research item.

### Deferred decisions related to Year 2

- [ ] **DEF-2** Presidio DLP scanner backend for Scenario A laptop deployments. Same pattern as PRV-A's `dlp.py` (GCP Cloud DLP) but operator-side, for laptop/single-org deployments without GCP. Deferred per userMemories. (Y2 stretch)

---

## Phase IM-1 through IM-6 — Immune Platform Backlog (Tracked, Not Scheduled)

**Source:** This section consolidates backlog content from three documents that previously carried duplicate item lists with three different ID schemes:

- `jackpot_immune_platform_plan.md` §14 (the original "Phase 26-31" backlog with sequential numeric IDs `B-001` through `B-049`)
- `jackpot_immune_collaboration_scaffolding_copy.md` §9.1, §9.2, §9.3 (Phase 26-collab scaffolding items, originally without IDs)
- `jackpot_detection_landscape.md` §6 (24 component-tier adoption items in mnemonic-ID format)

The consolidation rationale, full mapping of source IDs to canonical IDs, and overlap-merge decisions are documented in `backlog_consolidation_report.md`.

**Phase numbering note:** The immune-plan called these phases 26-31. Every one of those numbers collides with an existing `todo.md` phase (Phase 26 = Pathoplexus comparative; Phase 27 = CDC DMI / STLT; Phase 28 = Eukaryotic pipelines). To disambiguate without renumbering existing work, the immune-platform phases are renamed `IM-1` through `IM-6`. Sub-phase `IM-N-collab` items interleave the collaboration-scaffolding work within the corresponding main phase per scaffolding §9.1.

**Total effort estimate (Phase IM-1..IM-6):** ~31 weeks (~7 months full-time, ~14 months half-time alongside the active P0d–P5 sprint).

---

## Phase IM-1 — Immune Platform: Bio-AIS MVP + Academy Module 9 (Tracked, Not Scheduled)

**Source:** `jackpot_immune_platform_plan.md` §14.2 (Phase 26 in immune-plan numbering, renamed `IM-1` to avoid collision with existing `todo.md` Phase 26 = Pathoplexus comparative). Details in immune-plan §4 (Pillar I), §10.1 (module specs). Estimated effort: ~6 weeks.

**Goal:** First end-to-end NSA detector firing on real samples, plus the corresponding Academy module 9. By end of phase: a submitted sample runs through `jackpot-amand`, lands a row in `dca_priority_scores`, surfaces in the Triage UI, and is auditable end-to-end. A student completing module 9 has working starter code that compiles and runs.

**Prerequisites (existing P0 bugs that must be fixed before IM-1 starts):**
- Audit transaction-participation bug — `log_audit()` and `create_notification()` must forward `db_conn` to `execute_write()` (tracked in `jackpot_session_summary_and_backlog.md`)
- `_handle_workflow_complete()` `conn=` TypeError — Nextflow `workflow.complete` events must not crash the pipelines router
- Validator `BASE_REQUIRED` tier split — Glen-owned domain decision; defines what Tier-1 PRELIMINARY samples must contain

### A. Schema, NSA substrate, immune-bio core (~3 weeks)

- [ ] **B-IMMUNE-SCHEMA-1** Schema v6.0 stub — Alembic migration adding `detectors`, `detector_activations`, `dca_priority_scores`, `memory_cells` tables. Initial landing is empty migration with table definitions but no business logic, behind a feature flag (`IMMUNE_PILLAR_I_ENABLED=false`). Forces schema design conversation early. `[quick-win — land alongside current P0d sprint]`. (1-2 sessions, P0d or after)  <!-- drift-ok: preserved 2026-05-11 planning text; v6.0 was an aspiration, not a shipped version -->

- [ ] **B-IMMUNE-NSA-1** Implement `backend/immune/algorithms/nsa.py` — shared Negative Selection Algorithm substrate. Used by both bio-AIS (Pillar I) and cyber-AIS (Pillar V); same code, different feature spaces. Reference: `jackpot_immune_platform_plan.md` §3.1, §9.4. (3-4 sessions)

- [ ] **B-IMMUNE-FEAT-1** Implement `backend/immune/algorithms/features.py` — k-mer featurizer for Pillar I, API-call featurizer stub for Pillar V. Plus a featurizer registry pattern (`backend/immune/algorithms/featurizers/__init__.py` per `jackpot_immune_collaboration_scaffolding_copy.md` §3.2.1) so the AIS-theory collaborator can plug in alternative featurizers (k-mer, ESM-small, ESM-large, DNABERT-v2) without touching core code. (2-3 sessions; the registry is what makes this collaboration-friendly per the scaffolding doc)

- [ ] **B-AMAND-1** Adopt AMAnD (Price & Russell, *Frontiers in Public Health* 2023) as the canonical metagenome anomaly detector. Implementation has two layers: `backend/immune/bio/amand.py` (the bio-NSA module wrapping AMAnD's DeepSVDD model into JACKPOT's substrate) AND `pipelines/immune/amand.nf` (the Nextflow process for reproducible scans). Document the baseline-curation workflow ("what is normal for this operator's deployment context") in the Pillar IV training materials (`B-ACADEMY-9`). Detection landscape §2.c.1; immune-plan §10.1 + §13. (3 sessions pipeline-zoo + 2 weeks for the baseline-curation tooling, pipeline-zoo work + Pillar I)

- [ ] **B-IMMUNE-API-1** Implement `backend/routers/immune_bio.py` — FastAPI surface for Pillar I. Endpoints: `GET /api/v1/immune/triage` (DCA-priority queue), `GET /api/v1/immune/detectors/` (active detectors), `GET /api/v1/immune/dca/{sample_id}` (per-sample priority breakdown). Reference: immune-plan §10.1.1. (2-3 sessions)

- [ ] **B-LICENSE-1** Create `scripts/verify_licenses.py` — license compliance script. Validates that every wrapped OSS tool's license is documented in `THIRD_PARTY_LICENSES.md` and is AGPL-3.0-compatible. Runs in CI. Required before any wrapped-tool integration. `[quick-win — needed regardless of immune work]`. (1 session)

- [ ] **B-IMMUNE-UI-1** Streamlit page — "Anomaly Triage" — lists DCA-priority samples (DCA fusion stub returning genomic-only score is fine for MVP; full DCA lands in Phase IM-2). New `frontend/pages/anomaly_triage.py`. (1-2 sessions)

- [ ] **B-IMMUNE-TESTS-1** Test coverage for new code in IM-1.A. Target: 86%+ overall coverage maintained, no regression. (across the items above)

### B. Detection-landscape Pillar I pipeline-zoo entries (parallel with IM-1.A)

- [ ] **B-TAXTRIAGE-1** Adopt `nf-core/taxtriage` (Merritt et al., *Bioinformatics* 2026) into JACKPOT pipeline zoo as the canonical untargeted pathogen-discovery workflow. Pipeline-zoo spec file + integration with `pipeline_results_loader.py` for the pathogen-candidate output schema. Detection landscape §2.a.2. (2-3 sessions, pipeline-zoo work)

- [ ] **B-NFUNO-1** Adopt nf-UnO (Guzman-Cole & Huang, *Bioinformatics* 2025) as the cohort co-assembly pipeline for outbreak novel-pathogen investigations. Wire to the dataset/cohort selection UI; outputs feed `pipeline_results`. Detection landscape §2.a.3. (2 sessions, pipeline-zoo work, after `B-TAXTRIAGE-1`)

- [ ] **B-DEEPAC-1** Add DeePaC (Bartoszewicz et al. 2020) pathogenicity scoring as a post-classification step in the TaxTriage pipeline-zoo entry. Output a per-sequence pathogenicity score field on `pipeline_results` JSONB. Detection landscape §2.b.1. (1-2 sessions, after `B-TAXTRIAGE-1`)

- [ ] **B-MLM-1** Adopt MLM (Baugher et al., *JHU APL Technical Digest* 2025) as the unmapped-read threat-characterization stage. Wire into the TaxTriage pipeline output (post-DeePaC) for tiered threat-class assignment. Detection landscape §2.b.2. (2 sessions, after `B-TAXTRIAGE-1` + `B-DEEPAC-1`)

- [ ] **B-CGMSI-1** Add cgMSI (Zhu et al., *BMC Bioinformatics* 2023) to pipeline zoo as the nanopore strain-level detection tool. Pairs with MARTi (`B-MARTI-1`) for the real-time analysis layer. Detection landscape §2.a.5. (1-2 sessions, pipeline-zoo work)

- [ ] **B-INSAFLU-1** Evaluate INSaFLU-TELEVIR (Santos et al., *Genome Medicine* 2024) for adoption: viral mNGS pipeline (TELEVIR module) into pipeline zoo; INSaFLU REST API patterns as prior art for the LAPIS-compat work (`B-LAPIS-1`). Decide whether to adopt the TELEVIR pipeline directly or fork+adapt. AGPL-licensed — clean for JACKPOT. Detection landscape §2.a.4. (1 session study + 2 sessions adoption, Year 2)

- [ ] **B-KOMB-1** Study KOMB/KombOver (Balaji et al. 2022; Sapoval et al. 2024) for the community-shift detection layer of Pillar I. Pairs with `B-AMAND-1` (per-sample anomaly) for two complementary signals. Detection landscape §2.c.3. (1-2 weeks study, with `B-AMAND-1`)

### C. Phase IM-1-collab — Foundational scaffolding (interleaved with IM-1.A)

- [ ] **B-COLLAB-DIVERSITY-1** Implement `cli/jackpot_init/diversity_profile.py` — randomized init with depth guard. Each operator's `jackpot init` produces a different detector configuration drawn from a diversity-aware distribution; prevents the federation-wide monoculture problem. With depth guard so that diversity doesn't override sensible parameter ranges. Reference: `jackpot_immune_collaboration_scaffolding_copy.md` §3.2.2. (1 day, IM-1-collab)

- [ ] **B-COLLAB-SBOM-1** Create `scripts/generate_sbom.py` (CycloneDX SBOM generator) + `.github/workflows/supply_chain.yml` (CI supply-chain gate). Generates SBOM for every release; CI fails if any wrapped dependency has CVEs above policy threshold. Required before any wrapped-tool integration. Reference: scaffolding §4.2.1, §4.2.2. (3 days, IM-1-collab)

- [ ] **B-COLLAB-PARSERS-1** Implement `backend/immune/sec/parsers_safe.py` — safe deserialization helpers (re-exports `pickle.load`, `yaml.unsafe_load`, `eval` as functions that raise so accidental imports become loud errors). Add Critical Rule N to `CLAUDE.md` documenting the policy: never use unsafe deserialization on external data. Required before any wrapped-tool parsing. `[quick-win — land alongside current sprint]`. Reference: scaffolding §4.2.3, §9.3. (1 day, IM-1-collab)

- [ ] **B-COLLAB-SIGSTORE-1** Set up `infra/sigstore/` — Cosign-signed container images + key management. One-time keypair generation; private key + password in GitHub Actions secrets; public key in repo for transparency. Cosign verification policy gates production deployment. Reference: scaffolding §4.2.4. (2 days, IM-1-collab)

- [ ] **B-COLLAB-FRAMING-1** Land `course/modules/_meta/ais_framing.md` — Module 0 explaining why JACKPOT exists, AIS framing as the organizing principle, what makes the platform different. Module 0 sits before Module 1 in the curriculum sequence. `[quick-win — independent of any other work]`. Reference: scaffolding §9.3 QW-9. (0.5 day, IM-1-collab)

### D. Academy Module 9 (parallel with IM-1.A and IM-1.B)

- [ ] **B-ACADEMY-STUB-1** Land `course/modules/09-negative-selection-in-practice/` as a stub with starter code, even if production `jackpot-amand` doesn't exist yet. Students learn NSA against a stub initially; promoted to full content in `B-ACADEMY-9`. `[quick-win — land in current sprint]`. Reference: immune-plan §14.4 QW-2. (1 session, IM-1)

- [ ] **B-ACADEMY-9** Full content for `course/modules/09-negative-selection-in-practice/`: README, notebook, starter code, auto-grader, upstream pointer. Covers NSA theory, AMAnD walkthrough, baseline curation workflow. Replaces `B-ACADEMY-STUB-1` once `B-AMAND-1` lands. Reference: immune-plan §10.1, §7. (3-4 sessions)

### E. Synthetic data corpus

- [ ] **B-SYNTH-DATA-1** Create `course/data/synthetic/` — synthetic-data corpus generated from public references via reproducible recipes. Useful for tests, Outbreak cases, module exercises. Generate at least 3 starter datasets (viral, bacterial, eukaryotic). `[quick-win — independent]`. Reference: immune-plan §14.4 QW-5. (2-3 sessions)

### Phase IM-1 success criterion

A submitted sample runs through `jackpot-amand`, produces a row in `dca_priority_scores`, surfaces in the Anomaly Triage UI, is auditable end-to-end via the audit log, and a contributor can complete `course/modules/09-...` with starter code that compiles and runs.

---

## Phase IM-2 — Immune Platform: Multi-Modal Danger Fusion + DCA in Practice (Tracked, Not Scheduled)

**Source:** `jackpot_immune_platform_plan.md` §14.2 Phase 27, renamed `IM-2`. Details in immune-plan §4.3 (multi-modal danger signals — the differentiator), §10.2 (BioDendriticCell). Estimated effort: ~5 weeks.

**Goal:** Multi-modal context fusion lights up. A high-priority sample with confirmed wastewater + clinical concordance shows top of triage queue with explainable contributions. This is the differentiator that distinguishes JACKPOT's Pillar I from a pure-genomics anomaly detector.

### A. DCA implementation and danger signals (~3 weeks)

- [ ] **B-IMMUNE-DCA-1** Implement `backend/immune/bio/dca_bio.py` — full BioDendriticCell engine. Fuses genomic anomaly score (from `B-AMAND-1`) with multi-modal danger signals (wastewater, clinical, environmental, animal). Produces `dca_priority_scores` rows with explainable contributions per Patel 2021. Reference: immune-plan §10.2. (4-5 sessions)

- [ ] **B-IMMUNE-SCHEMA-2** Pydantic models in `backend/schemas/immune_bio.py` — DangerSignal, DcaPriorityScore, MultiModalContext. Wire to API surface from `B-IMMUNE-API-1`. (1-2 sessions)

- [ ] **B-IMMUNE-WW-1** Wastewater signal ingestion adapter — at least one feed (NWSS or local STAB). Polls feed periodically; produces `DangerSignal` rows tagged `wastewater_concordance`. Reference: immune-plan §4.3. (3-4 sessions)

- [ ] **B-IMMUNE-CLIN-1** Clinical signal ingestion ELR adapter stub. Real ELR integration is bigger (`B-CDC-1` in landscape governance work); stub for now. Stub accepts hand-curated ELR-like JSON for testing. (2-3 sessions)

- [ ] **B-IMMUNE-OH-1** One-Health adapter — animal/environmental sample classes wired into DCA. Existing schema already supports the sectors (wildlife, livestock, soil, surface, food, produce, vectors); this item wires them as DangerSignal feeds for the bio-DCA. (2-3 sessions)

- [ ] **B-IMMUNE-UI-2** Streamlit page — DCA breakdown view. Per-sample priority score with explainable contributions visualized (Patel 2021 explainability framework). Shows the genomic-anomaly score, each multi-modal danger signal's contribution, and the fused DCA priority. New `frontend/pages/dca_breakdown.py`. (2-3 sessions, after `B-IMMUNE-DCA-1`)

### B. Danger-signal pipeline-zoo entries (parallel)

- [ ] **B-EIOS-1** Document the EIOS signal-feed integration pattern for JACKPOT operators. Define the JSON-schema for incoming EIOS events and how they appear in the audit log and bio-anomaly correlation. No code yet — this is documentation work; full implementation is folded into `B-IMMUNE-DCA-1`. Detection landscape §2.f.1. (1 session documentation)

- [ ] **B-MARTI-1** [REAFFIRM — already in todo.md Phase 26] Add MARTi to pipeline zoo with real-time WebSocket updates. Pillar I real-time arm; pairs with `B-CGMSI-1`. Detection landscape §2.a.6.

- [ ] **B-REALTIME-1** Document and implement the JACKPOT real-time-analysis story: MARTi (`B-MARTI-1`) for nanopore metagenomics, NanoCore (`B-NANOC-1`) for nanopore outbreak typing, PathoLive (study) for Illumina real-time pathogen ID. Wire to WebSocket-driven UI updates so operators see results as the sequencer runs. Detection landscape §2.m. (3-4 sessions for the umbrella integration, after `B-MARTI-1` + `B-NANOC-1`)

- [ ] **B-GRUMB-1** Study GRUMB (Aminu et al., *Bioinformatics* 2025) for the environmental metagenomics + risk-scoring layer of Pillar I. Decide: adopt directly, fork+adapt, or build alternative. Detection landscape §2.b.3. (2-3 weeks study, when Pillar I env extension begins, Year 2+)

- [ ] **B-CRISPR-EBX-1** Study CRISPR-eBx (Durán-Vinet et al., *Trends in Biotechnology* 2025) as the canonical CRISPR-Dx environmental biosurveillance integration pattern for Pillar I extension to eDNA. Detection landscape §2.l.1. (1-2 weeks study, Pillar I env extension, Year 2+)

### C. Phase IM-2-collab — Defensive scaffolding

- [ ] **B-COLLAB-ROTATE-1** Implement `backend/immune/sec/rotation.py` — JWT key rotation, schema-version negotiation, RBAC-policy versioning. Ships dynamic-defense posture: keys/RBAC/schema rotate over time, not fixed forever. Depends on JWT infrastructure being stable (`P1` complete). Reference: scaffolding §5. (3 days, IM-2-collab)

- [ ] **B-COLLAB-MUTATE-1** Implement `backend/middleware/api_surface_mutation.py` — randomized API URL prefixes per deployment instance. Different operators see different URL spaces; reduces blanket-attack effectiveness. Reference: scaffolding §5. (2 days, IM-2-collab)

- [ ] **B-COLLAB-REFUSAL-1** Implement `backend/immune/sec/refusal.py` + middleware. Refusal-to-serve middleware that gates ingest based on declared deployment context. Initially with explicit allow-list (whitelist of OK-to-serve contexts); deny-list is more dangerous and waits for governance maturity. Reference: scaffolding §6 (Misuse and governance). (3 days, IM-2-collab)

- [ ] **B-COLLAB-DUR-1** Land `docs/dual_use_review.md` + `dual_use_review_queue` table. Dual-Use Research of Concern (DURC) review queue for samples flagged by `B-SOC-1`. Lists guidance, escalation paths, governance-board contact. Reference: scaffolding §6. (1 day, IM-2-collab; depends on `B-SOC-1` from IM-5)

- [ ] **B-COLLAB-REDTEAM-1** Implement `backend/immune/redteam/` skeleton + `cli.py` + first concrete attack (`amand_baseline_drift_attack.py`). The "redteam track" lets operators run adversarial test suites against their own deployment. Reference: scaffolding §8. (3 days, IM-2-collab; depends on `B-AMAND-1` existing from IM-1)

- [ ] **B-COLLAB-REDTEAM-2** Implement `backend/immune/redteam/data_representativeness.py` — checks for representativeness in baseline data (e.g., the AMAnD baseline is representative across the operator's actual sample distribution). Reference: scaffolding §8. (1 day, IM-2-collab; independent)

- [ ] **B-COLLAB-CI-1** Add `.github/workflows/redteam.yml` and `.github/workflows/diversity_check.yml` to CI. Redteam runs nightly; diversity check runs on every PR touching detectors. Reference: scaffolding §8, §3.2.6. (1 day, IM-2-collab; depends on `B-COLLAB-REDTEAM-1` skeleton)

### D. Outbreak: Field Edition — first three cases

- [ ] **B-OUTBREAK-1** Outbreak: Field Edition cases 1-3. Single-player narrative-puzzle progression introducing the platform. Cases use `jackpot-amand` baseline scans. Cases 1-3 covered: a foodborne outbreak with classic pathogen, a respiratory outbreak with novel agent, a wastewater early-signal scenario. Reference: immune-plan §8.2. (3-4 sessions per case = ~10 sessions total; IM-2)

### E. Academy Module 10

- [ ] **B-ACADEMY-10** Full content for `course/modules/10-dca-in-practice/`: README, notebook, starter code, auto-grader, upstream pointer. Covers DCA theory, multi-modal fusion walkthrough, danger-signal interpretation. Reference: immune-plan §7. (3-4 sessions, after `B-IMMUNE-DCA-1`)

### F. Tests + integration

- [ ] **B-IMMUNE-TESTS-2** Tests + integration tests with realistic synthetic multi-modal data. End-to-end test: synthetic wastewater spike + concurrent clinical signal → top-of-triage placement with explainable contributions. (across IM-2 items)

### Phase IM-2 success criterion

A high-priority sample with confirmed wastewater+clinical concordance shows top of the Anomaly Triage queue with the per-signal contributions visualized in the DCA breakdown view. A new contributor can complete Module 10 against the live `jackpot-immune-bio` API.

---

## Phase IM-3 — Immune Platform: Memory + Clonal Selection (Tracked, Not Scheduled)

**Source:** `jackpot_immune_platform_plan.md` §14.2 Phase 28, renamed `IM-3`. Details in immune-plan §3.2 (Clonal Selection theory), §10.3 (ClonalSelectionEngine spec). Estimated effort: ~5 weeks.

**Goal:** The platform learns from confirmed anomalies. Analyst-confirmed anomaly creates a new high-affinity detector; subsequent matching sample short-circuits via the memory cell with sub-second recall.

### A. Clonal selection + memory cells (~3 weeks)

- [ ] **B-IMMUNE-CS-1** Implement `backend/immune/bio/cs_bio.py` — full ClonalSelectionEngine. Takes confirmed anomalies (analyst-labeled), clones the corresponding detector, mutates with hypermutation rate proportional to confidence, retains high-affinity offspring. Reference: immune-plan §10.3. (4-5 sessions)

- [ ] **B-IMMUNE-MEM-1** Memory-cell promotion logic — high-affinity confirmed detectors are promoted to the `memory_cells` table. Memory cells short-circuit downstream samples that match (sub-second recall). Reference: immune-plan §3.6 (innate immune memory / trained immunity). (2-3 sessions)

- [ ] **B-IMMUNE-UI-3** Streamlit page — Analyst Review Queue. Surfaces uncertain detections (DCA-priority below confirmed-threshold but above noise-threshold) for human analyst review. Analyst marks confirmed/false-positive; confirmed feeds clonal selection (`B-IMMUNE-CS-1`). Reference: immune-plan §10.3 (Liu 2023 human-in-the-loop). (2 sessions)

### B. AMR memory and recombination

- [ ] **B-AMR-MEMORY-1** Implement `jackpot-amrmemory` — wraps amr.watch (API), AMRFinderPlus (CLI), abricate (CLI). Confirmed AMR signatures populate AMR-specific memory cells. Reference: immune-plan §13 OSS table; pairs with `B-NCBI-2` (hAMRonization) for canonical output format. (3-4 sessions)

- [ ] **B-RECOMB-1** Adopt OpenRecombinHunt (Alfonsi et al., *J. Mol. Biol.* 2026) as `jackpot-recombhunt` — viral-recombination-detection pipeline-zoo entry. Wired to a periodic-scan workflow that runs on JACKPOT's public viral datasets; results feed clonal-selection signal in `B-IMMUNE-CS-1`. Detection landscape §2.e.5; immune-plan §10.4. (2 sessions, IM-3)

### C. Outbreak Case 4

- [ ] **B-OUTBREAK-2** Outbreak: Field Edition case 4 — AMR puzzle. Uses `jackpot-amrmemory` to track an AMR-gene transmission cluster across multiple sample submissions. Player must identify the introducing event from the clonal-selection-derived memory-cell history. Reference: immune-plan §8.2. (3-4 sessions, IM-3)

### Phase IM-3 success criterion

Analyst confirms an anomaly → new high-affinity detector enters memory pool → subsequent matching sample triggers sub-second memory-cell recall (visible in audit log + Triage UI). AMR signatures populate AMR-specific memory; recombinant detection feeds back into clonal selection.

---

## Phase IM-4 — Immune Platform: Federation as Immune Network (Tracked, Not Scheduled)

**Source:** `jackpot_immune_platform_plan.md` §14.2 Phase 29, renamed `IM-4`. Details in immune-plan §6 (Pillar III), §10.5 (TrustEngine spec). Estimated effort: ~6 weeks.

**Goal:** Cross-tenant immune-network with trust scoring and encrypted queries. Two JACKPOT instances on one network share a confirmed memory cell after cross-instance confirmation, and run a homomorphic-encrypted query without raw data leaving either side.

### A. Federation infrastructure (~4 weeks)

- [ ] **B-IMMUNE-FED-SCHEMA-1** `backend/models/immune.py` — federation tables: `federation_members`, `trust_scores`, `cyber_assessments`. Includes the federation-trust schema sketch (immune-plan §14.4 QW-6) as the initial schema landing. (2-3 sessions; subsumes the `[quick-win]` from §14.4)

- [ ] **B-IMMUNE-TRUST-1** Implement `backend/immune/net/trust.py` — TrustEngine. Computes trust scores per federation member based on submission quality, false-positive rate, behavioral consistency. Trust scores gate which federation operations a member can participate in. Reference: immune-plan §6.2.1, §10.5. (4-5 sessions)

- [ ] **B-IMMUNE-REP-1** Implement `backend/immune/net/repertoire.py` — AntibodyRepertoire publish/subscribe. Federation members publish their detector repertoire (anonymized); other members subscribe to synthesize a global repertoire view. Reference: immune-plan §6.3. (3-4 sessions)

- [ ] **B-IMMUNE-MEMSYNC-1** Implement `backend/immune/net/memory_sync.py` — federation memory cell synchronization with cross-member confirmation thresholds. A memory cell only promotes to the global pool after N independent member confirmations. Reference: immune-plan §6.2. (3-4 sessions)

- [ ] **B-IMMUNE-HE-1** Implement `backend/immune/net/query_he.py` — homomorphic-encryption query layer (Kim 2021). Start with one well-defined query type (e.g., "do you have a memory cell matching this signature?"); expand later. Lands inside the existing `B-CRY-1` crypto-scaffold pattern. Reference: immune-plan §6.2.2, §10.5. (1-2 weeks; significant work)

- [ ] **B-IMMUNE-DP-1** Implement differential-privacy aggregator for shared signals. Lands inside the existing `B-PRV-1` privacy-scaffold pattern. Federation-wide aggregations (member counts, signal frequencies) computed with formal DP guarantees. Reference: immune-plan §6.2.3. (1 week)

- [ ] **B-FED-PILLARIII-1** Decide FL framework for Pillar III. Use FedTADBench (Liu et al. 2022) to benchmark DataSHIELD-class vs FedAdapt-CAD vs FedMI on representative anomaly-detection workloads. Pick based on benchmark + mature-tooling tradeoff. Detection landscape §2.i.1. (2 weeks benchmarking + 1 week documentation)

### B. Federation outbreak case + WILDFIRE skeleton

- [ ] **B-OUTBREAK-3** Outbreak: Field Edition case 8 — federation-required capstone. Player must coordinate with another JACKPOT instance to identify a transmission cluster spanning two operators. Demonstrates the federation primitives end-to-end. (4-5 sessions, IM-4)

- [ ] **B-WILDFIRE-1** WILDFIRE skeleton — multiplayer engine, cell management, mole/adversarial-cell mechanics. The platform-on-platform game where players coordinate as JACKPOT instances. First skeleton; full missions land in IM-6. Reference: immune-plan §8.3. (1-2 weeks for skeleton)

### C. Phase IM-4-collab — Federation defensive scaffolding

- [ ] **B-COLLAB-DIVERSITY-2** Implement `backend/immune/net/diversity.py` + `diversity_cli.py` — federation diversity index. Computes a quantitative diversity score across federation member detectors; CI gate (`B-COLLAB-CI-1`) fails if diversity drops below threshold. Reference: scaffolding §3.2.3, §3.2.4. (2 days, IM-4-collab)

- [ ] **B-COLLAB-ATRUST-1** Implement `backend/immune/net/asymmetric_trust.py` — asymmetric trust between federation members. Member A may trust member B at level 3 while member B trusts member A at level 1. With input validation. Reference: scaffolding §6 (asymmetric-power awareness). (2 days, IM-4-collab; depends on `B-IMMUNE-TRUST-1`)

- [ ] **B-COLLAB-REDTEAM-3** Implement `backend/immune/redteam/attack_federation.py` — adversarial test suite for federation. Simulates malicious member submitting poisoned signals; tests detection. Reference: scaffolding §8. (3 days, IM-4-collab; depends on federation existing)

### Phase IM-4 success criterion

Two JACKPOT instances on one network can: (1) share a confirmed memory cell after cross-instance confirmation; (2) run a homomorphic-encrypted query without raw data leaving either side; (3) compute federation-wide diversity and refuse operations when diversity drops; (4) complete Outbreak case 8 in 2-player coordination mode.

---

## Phase IM-5 — Immune Platform: Cyber-AIS for Platform Self-Defense (Tracked, Not Scheduled)

**Source:** `jackpot_immune_platform_plan.md` §14.2 Phase 30, renamed `IM-5`. Details in immune-plan §5 (Pillar II), §10.4 (CyberNSA spec). Estimated effort: ~5 weeks.

**Goal:** Pillar II live. Same NSA substrate, different threat surface. A simulated insider-threat scenario (a researcher account suddenly enumerating all samples) raises a high-priority `cyber_assessments` row within 60 seconds. Sample submission with adversarial perturbation gets flagged by `poisondetect`.

### A. Cyber-AIS implementation (~3 weeks)

- [ ] **B-IMMUNE-CYBER-1** Implement `backend/immune/sec/nsa_cyber.py` — CyberNSA. Uses the same `B-IMMUNE-NSA-1` substrate, but trained on API-call featurizers from `B-IMMUNE-FEAT-1`. Reference: immune-plan §10.4. (4-5 sessions)

- [ ] **B-IMMUNE-TELEM-1** Implement `backend/middleware/api_telemetry.py` — captures `ApiCallEvent` rows. Every API call produces a telemetry event with featurizable attributes (endpoint, user, time-of-day, request size, response code, latency). Feeds the cyber-NSA. (2-3 sessions)

- [ ] **B-IMMUNE-CYBER-DCA-1** Implement `backend/immune/sec/dca_cyber.py` — context-aware threat fusion. Like the bio-side DCA but for security threats. Multi-modal danger signals: failed-auth attempts, unusual query patterns, off-hours access, geographic anomalies. (3-4 sessions)

- [ ] **B-IMMUNE-POISON-1** Implement `backend/immune/sec/poisondetect.py` — sample-poisoning detection. Scans submitted samples for adversarial perturbation patterns (Tavella 2022 inspired). Flags suspect samples for analyst review before they enter the bio-AIS training data. Reference: immune-plan §5.3.1. (3-4 sessions)

- [ ] **B-IMMUNE-OPSEC-1** Implement `backend/immune/sec/opsec.py` — query OPSEC monitoring. Detects when an operator's federation-mode query patterns leak information about their data (e.g., narrowing query specificity over time). Reference: immune-plan §5.3.2. (2-3 sessions)

- [ ] **B-SOC-1** Adopt SeqScreen + BLiSS as a combined sequence-of-concern (SoC) screening layer at ingest. Lands as `backend/immune/sec/screening.py`. Initially run-and-flag (no blocking); annotate samples with SoC-screen-flag and append to audit log. Evaluate gating policy after 6 months of false-positive/negative data. Detection landscape §2.h; immune-plan §5.3.4. (3-4 sessions for initial run-and-flag pipeline; 6 months data collection; 1-2 sessions for gating policy)

### B. UI + audit chain

- [ ] **B-IMMUNE-UI-4** Insider-threat dashboard — Streamlit page for platform admin. Shows recent `cyber_assessments` rows, threat tier, suspected user/account, recommended action. (2 sessions)

- [ ] **B-AUDIT-CHAIN-1** Audit hash chain — close the existing P0 audit-bug fix AND extend with crypto chain. Each audit-log row chains via SHA-256 hash to its predecessor; tampering becomes immediately detectable. Reference: immune-plan §5.4. (3-4 sessions; partially blocked by P0 audit-bug fix)

### C. Academy Module 13

- [ ] **B-ACADEMY-13** Full content for `course/modules/13-cyberbiosecurity/`. Covers cyber-AIS theory, the dual-AIS architecture (bio + cyber), poisoning attack/defense, OPSEC. Reference: immune-plan §7. (3-4 sessions)

### D. Phase IM-5-collab — Federated cyber-AIS

- [ ] **B-COLLAB-CYBER-FED-1** Implement `backend/immune/sec/cs_cyber_federated.py` — federated clonal selection for cyber-AIS. Threat detectors learned at one instance can propagate (under trust constraints) to others. Reference: scaffolding §5. (4 days, IM-5-collab; depends on Phase IM-4 federation landing)

### Phase IM-5 success criterion

A simulated insider-threat scenario (researcher account enumerating all samples) triggers a high-priority `cyber_assessments` row within 60 seconds. Sample submission with adversarial perturbation gets flagged by `poisondetect` before entering the bio-AIS training data. Audit log tampering is detectable via the hash chain. SoC screening produces flags on synthetic-DNA-screen-positive submissions.

---

## Phase IM-6 — Immune Platform: Game/Academy Full Integration (Tracked, Not Scheduled)

**Source:** `jackpot_immune_platform_plan.md` §14.2 Phase 31, renamed `IM-6`. Details in immune-plan §7 (Academy), §8 (Outbreak + WILDFIRE). Estimated effort: ~4 weeks.

**Goal:** All five pillars operational; training/gaming feedback loop closed. A new contributor can clone the repo, run `jackpot init --profile academy`, complete module 9, ship a PR to `jackpot-amand`, get it merged, and see their detector activate on a real sample.

### A. Outbreak: Field Edition full progression

- [ ] **B-OUTBREAK-4** Outbreak: Field Edition cases 5-8 (full progression). Cases 5-7 cover increasingly complex scenarios (zoonotic spillover, AMR cluster, environmental persistence). Case 8 is already covered by `B-OUTBREAK-3` (federation capstone). Reference: immune-plan §8.2. (3-4 sessions per case)

### B. WILDFIRE missions

- [ ] **B-WILDFIRE-2** WILDFIRE missions 1-6 fully implemented (the original "Stop the Plague" arc). Multi-player mode building on the `B-WILDFIRE-1` skeleton. Reference: immune-plan §8.3. (2-3 weeks)

### C. Game-to-platform feedback loop

- [ ] **B-GAME-LABEL-1** Game submissions feed clonal-selection labeling pipeline. Player decisions in Outbreak cases that match real anomaly-detection scenarios become training data for `B-IMMUNE-CS-1`. Reference: immune-plan §8.4. (1 week)

### D. Academy completion

- [ ] **B-ACADEMY-OTHER-1** Academy modules 11, 12, 14, 15, 16 — full content. Modules cover federation theory, clonal selection deep-dive, cyberbiosecurity case studies, dual-AIS architecture, future research directions. Reference: immune-plan §7. (4-5 weeks total across all modules)

### E. Init profiles + public release

- [ ] **B-INIT-PROFILES-1** `jackpot init --profile academy` and `jackpot init --profile game` profiles. Each profile bootstraps a JACKPOT instance pre-configured for the role (academy = read-only, game = WILDFIRE host). Reference: immune-plan §8.5. (1 week)

- [ ] **B-ACADEMY-TENANT-1** Public read-only academy tenant — deploy alongside production. Anyone can register, complete modules, see live (sanitized) detector activation. Reference: immune-plan §7.4. (1-2 weeks)

- [ ] **B-RELEASE-1** First public release announcement / paper draft kickoff. Press release, blog post, manuscript skeleton for a *Bioinformatics* or similar venue. Reference: immune-plan §15.4. (1 week)

### Phase IM-6 success criterion

A new contributor: (1) clones repo, (2) runs `jackpot init --profile academy`, (3) completes module 9, (4) ships a PR to `jackpot-amand`, (5) sees the PR merged, (6) sees their contributed detector activate on a real sample. Public Academy tenant is live and registering external students.

---

## Wet-Side Advisory Track (Tracked, Independent of Phase IM-* Sequencing)

**Source:** `jackpot_immune_collaboration_scaffolding_copy.md` §9.2. The wet-side advisor's critique ("you don't understand the wet-side enough") doesn't have a software handle; the substitute action is to formalize the wet-side advisory role.

- [ ] **B-WW-ADV-1** Add `docs/wetside_advisory.md` documenting current assumptions about wastewater sampling cadence, sample preservation, sequencing-prep failure modes, and known limitations of the input pipeline. Reference: scaffolding §9.2. (1 day; can land any time; ID disambiguates from existing `B-WW-1` wastewater pipeline-zoo work)

- [ ] **B-WW-ADV-2** Pre-register questions for the wet-side advisor's group (sampling cadence, preservation, false-positive failure modes specific to NWSS feeds) and resolve them in `docs/decisions/`. Reference: scaffolding §9.2. (2-3 sessions; depends on advisor identification)

(The wet-side-advisor *role* — adding a named individual or panel from the wet-lab community to `GOVERNANCE.md` — is folded into `B-GOV-1` per the consolidation report §5.1.)

---

## Pipeline Zoo Additions from Detection Landscape (Tracked, Not Scheduled)

**Source:** `jackpot_detection_landscape.md` §6. Eight items that are pipeline-zoo additions strengthening JACKPOT's outbreak-genomics and surveillance capabilities, but not specific to any Immune Platform pillar. They land independently of Phase IM-* sequencing whenever pipeline-zoo work happens.

### A. Bacterial-aware variant callers (4 items)

- [ ] **B-CNPRO-1** Adopt CNproScan (Jugas et al., *Genomics* 2021) as a bacterial CNV pipeline-zoo entry. GC-bias-aware, circular-genome-aware. Wire to `pipeline_results` loader. Useful especially for AMR-gene copy-number variation, which generic CNV callers miss. Detection landscape §2.d.1. (1-2 sessions)

- [ ] **B-PROSV-1** Adopt ProcaryaSV (Jugas & Vitkova, *BMC Bioinformatics* 2024) as the bacterial SV pipeline-zoo entry. Pairs with `B-CNPRO-1` for full bacterial CNV+SV coverage. Detection landscape §2.d.2. (1-2 sessions, with `B-CNPRO-1`)

- [ ] **B-SNIPG-1** Add SNiPgenie (Farrell et al., *Access Microbiology* 2025) as an alternative SNP-calling pipeline-zoo entry to bactopia for cases where bactopia is overkill (single-organism outbreak; not the full bactopia workflow). Detection landscape §2.d.3. (1 session)

- [ ] **B-SKA2-1** Add SKA2 (Derelle et al., *Genome Research* 2024) as the rapid-triage variant-calling pipeline-zoo entry. Recommended workflow: SKA2 for first-pass cluster identification across all samples, then SNiPgenie + bactopia for the focal cluster. Detection landscape §2.d.4. (1 session, with `B-SNIPG-1`)

### B. Specialty surveillance pipelines (4 items)

- [ ] **B-NANOC-1** Adopt NanoCore (Fuchs et al., *mSystems* 2024) as the canonical Nanopore-aware core-genome outbreak-tracking pipeline. Pairs with bactopia (already shipped) for Illumina-only workflows; NanoCore handles the mixed-sequencer federation case. Detection landscape §2.e.1. (2 sessions)

- [ ] **B-PFHAP-1** Adopt Pf-HaploAtlas (Lee et al., *Bioinformatics* 2024) as the malaria-specific pipeline-zoo entry. Self-hostable; outputs feed `pipeline_results` JSONB. Document the schema mapping for haplotype data. Detection landscape §2.e.2. (2-3 sessions)

- [ ] **B-PYMLST-1** Adopt pyMLST as the custom-cgMLST-scheme pipeline-zoo entry. Default schema source is pubMLST; operators can build custom schemes for non-standard organisms. Detection landscape §2.e.3. (1-2 sessions)

- [ ] **B-AMRO-1** Adopt AMRomics (Le et al., *BMC Genomics* 2024) as the population-scale AMR-surveillance pipeline-zoo entry. Pairs with `B-NCBI-2` (hAMRonization output mandate) for clean cross-pipeline comparability. Detection landscape §2.e.4. (2-3 sessions, with `B-NCBI-2`)

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
