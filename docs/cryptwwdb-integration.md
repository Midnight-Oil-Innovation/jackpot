# cryptWWDB integration — JACKPOT extension readiness

A technical readiness assessment of how JACKPOT's wastewater + federation architecture is positioned to host **cryptWWDB** as a Track 2 extension. Written for Driver, Ahsan, Piske, Lee, Forrest, Halden, Trieu (NSF 2115075, Driver et al. 2024 *Sci Total Environ* 940:173315).

## Context

JACKPOT (Midnight-Oil-Innovation/jackpot, AGPL-3.0) is an operator-agnostic open-source pathogen genomics platform with first-class wastewater support. Active development since March 2026, ~1700 tests, deployed across six scenarios from laptop to federation. Two architectural choices made independently of cryptWWDB turn out to align with the paper's framework in unusually direct ways:

1. **JACKPOT's federation layer is Track 1 / Track 2 by design.** Each federation primitive (`FederationClient`, `FederationPushJob`, `FederationAccessGateway`) ships with a Track 1 implementation using current primitives plus a `_ais_hooks.py` Protocol seam where AIS-augmented overlays plug in via dependency injection. Track 1 code never imports from Track 2; the seam is one-way.
2. **JACKPOT already has an `he_compute` AIS hook.** The privacy scaffold (`backend/backend/privacy/`, merged 2026-05-08 as PRV-A) defines `AISPrivacyHooks.he_compute(encrypted_inputs, op)` as one of six Protocol entry points, with the Track 2 implementation site pre-allocated at `backend/backend/immune/sec/he_backend.py`.

The combination means cryptWWDB doesn't need a JACKPOT rewrite to become a production framework. It needs (a) wastewater roadmap Level 1 to ship, (b) the federation scaffold to complete, (c) a concrete implementation of `he_compute` against the cryptWWDB mass-balance use cases, and (d) a small number of net-new schema and operational additions detailed below.

## The architectural fit at a glance

| cryptWWDB component | JACKPOT primitive | Status |
|---|---|---|
| Muni A / Muni B (data-holding entities) | JACKPOT instance, `federated_instances` row, `FederationRole` enum (hub/spoke/peer) | FED-A scaffold landed; FED-D schema migration pending |
| Third-party Laboratory (data producer + computation site) | JACKPOT instance with pipeline-token-authenticated `pipeline_results` writes; potential new `data_source_lab` federation role | Pipeline-token auth exists; lab role is net-new |
| Computation coordinator (policy checker) | `FederationClient` + AIS hooks: `attest_partner`, `detect_anomalous_traffic`, `threshold_approve`, `validate_push_payload` | All five hooks defined in FED-A; `NullAISFederationHooks` default is the no-op baseline |
| Public key (pk), evaluation key (evk) distribution | `backend/backend/crypto/` (CRY-A, pending) — `keys.py` + key-rotation policy | CRY-A scaffold pending, mirrors FED-A pattern |
| Encrypted plaintext → ciphertext encryption (RLWE-based, TenSEAL) | `AISPrivacyHooks.he_compute(encrypted_inputs, op)` Protocol entry point, Track 2 impl at `backend/backend/immune/sec/he_backend.py` | Hook signature defined; Track 2 impl not yet started (`B-IMMUNE-HE-1`, Phase IM-4, Tracked Not Scheduled) |
| Mass-load formula `(Q1·C1) − (Q2·C2)` over encrypted operands | Concrete query implementation within `he_backend.py` | Net-new |
| Q1, Q2 (municipality wastewater flow data) | `WastewaterSample.flow_rate_mgd` (LinkML schema) | Schema-aligned, ships today |
| C1, C2 (target chemical concentrations) | `wastewater_lineage_abundance` result type (Freyja-shaped) or new concentration result type | Result-type extension needed for non-lineage concentration data |
| Upstream / downstream sewershed relationship | `sample_associations` table (directed cross-sample linkage); `association_type` enum extension | Table exists; new enum value `wastewater_upstream_of` is net-new |
| Time component (Use Case 2) | `WastewaterSample.collection_datetime` + ciphertext-ciphertext equality check in `he_backend.py` | Schema-aligned; equality-check implementation is net-new |
| Repeated-query / access-control checks | `detect_anomalous_traffic` + `threshold_approve` AIS hooks + standard JACKPOT RBAC | Hook signatures defined; concrete policy is operator-configurable |
| Three-party non-collusion assumption | Architectural; documented as a federation operating constraint | Constraint statement net-new in `docs/federation_operations.md` |
| Multi-key HE extension (Lopez-Alt et al. 2012) | Follow-on `B-IMMUNE-HE-2` after `B-IMMUNE-HE-1` ships | Future direction; same seam, multi-key crypto backend |

The match is unusually clean because the AIS hook architecture (designed against the `Jackpot_AIS.md` immune-system framing) anticipated exactly the secure-computation extensibility that cryptWWDB requires. The five `AISFederationHooks` and six `AISPrivacyHooks` Protocol entry points form a complete primitive set for plugging cryptographic overlays into the federation surface.

## What's in place today (shipping or merged)

- **`WastewaterSample` LinkML class** (`jackpot_schema.yaml:1065-1198`). NWSS-aligned per APGAP `wastewater_sample.xlsx` and cdc.gov/nwss/reporting.html. Site fields (`wwtp_name`, `nwss_sewershed_id`, `county_names` multivalued, `population_served`, `flow_rate_mgd`); collection-event fields (`sample_type`, `sample_matrix`, `pretreatment`, `concentration_method`, `sample_collect_time`); 10 PCR/quantification fields including `pcr_target` (already supports `sars-cov-2`, `influenza-a`, `mpox`, `hMPXV Clade I`); MIxS ENVO terms (`env_broad_scale`, `env_local_scale`, `env_medium`).
- **`wastewater_lineage_abundance` result type** (`spec.md:1653`). Populated by the Freyja parser via Cecret / viralrecon pipelines. Goes through `POST /api/v1/pipelines/{run_id}/results/wastewater_lineage_abundance` with token auth, written to typed table + `pipeline_results.metrics` JSONB in the same transaction. Append-only — re-running produces new rows, never updates.
- **`sample_associations` table** (`jackpot_architecture.md:544, 629`). Directed cross-sample linkage; the existing design note explicitly cites "wastewater↔clinical isolate" as the motivating use case.
- **FED-A federation scaffold** (`backend/backend/federation/`, merged 2026-05-08). Three federation levels (L1 query federation via `FederationClient`, L2 hub push via `FederationPushJob`, L3 bidirectional access via `FederationAccessGateway`) plus the five `AISFederationHooks` Protocol entry points: `secure_aggregate`, `attest_partner`, `detect_anomalous_traffic`, `threshold_approve`, `validate_push_payload`. Operator-agnostic verified — no proper names in scaffold code.
- **PRV-A privacy scaffold** (`backend/backend/privacy/`, merged 2026-05-08 as PR #39). Six `AISPrivacyHooks` Protocol entry points: `dp_noise`, `track_dp_budget`, `fl_aggregate`, **`he_compute(encrypted_inputs, op)`**, `mpc_protocol`, `synthetic_substitute`. Consolidates existing HRRT scrubber and GCP Cloud DLP under a unified privacy surface.
- **Dual PII-gate architecture.** NCBI SRA Human Scrubber (HRRT) for genomic-level PII at ingest; GCP Cloud DLP for metadata-level PII before query exposure. Aligns with WHO/IPSN attribute 6.

## What's near-term in the JACKPOT roadmap

- **`B-WW-1` Wastewater lineage-abundance dashboard** (1.5 sessions, unblocked). Streamlit page with stacked-area lineage trajectories per sampling site, project/lab-membership filters, PNG/PDF export. Source patterns: NICD-Wastewater-Genomics + andersen-lab/sd_ww_processing. Leverages the existing Freyja output schema. Listed as Phase 26 quick-win #7.
- **FED-B/C/D/E federation completion** (~4 sessions, active sprint candidate). Federation router (FED-B), tests with ≥95% coverage (FED-C), schema migration adding `federated_instances` table (FED-D), router wiring in `main.py` + federation-key guard in `auth/guards.py` (FED-E). Completes the L1/L2/L3 federation Track 1 path.
- **CRY-A crypto scaffold** (active sprint candidate, ~1000 lines, 1 PR). Mirrors FED-A and PRV-A patterns. Files: `keys.py` (key management abstraction over PKCS#11 / Secret Manager / file-system keystores), `signing.py` (Sigstore/cosign artifact-signing interface), `crypt4gh.py` (per-file encryption for ingest/egress, GA4GH standard), `_ais_hooks.py` (`AISCryptoHooks` Protocol seam — HE backend selection, threshold signing FROST/BLS/DKG, TEE attestation, key-rotation policy).
- **`B-IMMUNE-WW-1` Wastewater signal ingestion adapter** (Phase IM-2, 3-4 sessions, Tracked Not Scheduled). Polls at least one feed (NWSS or local STAB); produces `DangerSignal` rows tagged `wastewater_concordance` for the BioDendriticCell multi-modal fusion engine.
- **`B-WW-ADV-1` Wet-side advisory doc** (1 day). Documents current assumptions about wastewater sampling cadence, preservation, sequencing-prep failure modes.

When the items above ship, JACKPOT will be operationally ready to host the cryptWWDB framework as a Track 2 overlay. The remaining gaps are well-bounded and listed below.

## What's net-new in JACKPOT design for cryptWWDB readiness

### Required additions

1. **`association_type` enum value: `wastewater_upstream_of`** (small schema addition). cryptWWDB requires the platform to know that Muni B's sample is upstream of Muni A's sample. Existing `sample_associations` table supports directed linkage; only the enum value is missing. ~0.5 day.

2. **Mass-balance computation as a JACKPOT operation** (new module). `backend/backend/wastewater/mass_balance.py` with two tiers: Tier 1, plaintext computation against `WastewaterSample.flow_rate_mgd` + concentration data for single-instance or already-shared cases; Tier 2, the federated-encrypted variant that delegates to `AISPrivacyHooks.he_compute`. Tier 1 is plain Python and ships first; Tier 2 is the cryptWWDB integration point. ~1-2 sessions for Tier 1; Tier 2 implementation is the `B-IMMUNE-HE-1` work below.

3. **Concentration / quantification result type for non-SARS-CoV-2 targets** (schema addition, ~2-3 sessions). The current `wastewater_lineage_abundance` is Freyja-shaped (lineage fractions for SARS-CoV-2). cryptWWDB's C1 and C2 are concentrations of arbitrary target chemicals — heroin, 6-acetylmorphine in the paper, but the framework is target-agnostic. Two options: (a) extend `wastewater_lineage_abundance` with a `target_pathogen` + `concentration` field; (b) add a new `wastewater_target_concentration` result type. Option (b) follows the existing pattern of typed result types per analysis kind. Listed in the wastewater roadmap as Net-new gap 1; cryptWWDB is one strong motivating use case for it.

4. **`B-IMMUNE-HE-1` scoped to wastewater mass-balance as first concrete query type** (Phase IM-4 work, currently Tracked Not Scheduled). The item is currently spec'd as "one well-defined query type to start (e.g., 'do you have a memory cell matching this signature?')" — that "for example" is the slot where wastewater mass balance becomes the first concrete query. Concrete implementation at `backend/backend/immune/sec/he_backend.py` covering: (a) Use Case 1 — `(Q1·C1) − (Q2·C2)` over RLWE-encrypted operands using TenSEAL; (b) Use Case 2 — temporal equality check (ciphertext-ciphertext); (c) Use Case 2-time-efficient — plaintext-ciphertext check delegated to Muni B. Estimated 1-2 weeks per the existing item description.

5. **Federation role for "data-producing laboratory"** (small federation extension). cryptWWDB's three-party model (Muni A, Muni B, Lab) has the Lab as distinct from the data-holding municipalities. Options: (a) add `data_source_lab` value to `FederationRole` enum; (b) keep current `peer` role and distinguish via a `produces_samples=False, produces_results=True` flag pair. Either is a small extension to `backend/backend/federation/models.py`. ~0.5 day.

6. **`docs/federation_operations.md` — three-party non-collusion assumption documented** (1 day). The paper's principal limitation (Section 4) is that Muni A and the Lab must not collude — if they do, Muni A's secret key can decrypt everything. JACKPOT must document this as an operator constraint, with the multi-key HE pathway flagged as the future mitigation.

### Recommended additions (improve cryptWWDB applicability)

7. **`B-IMMUNE-HE-2` Multi-key HE support** (post `B-IMMUNE-HE-1`). Implements Lopez-Alt et al. 2012 multi-key HE so that decryption requires participation from all key-holding parties. Eliminates the Muni-A-and-Lab collusion risk explicitly identified in the paper. Same `he_backend.py` interface, different crypto backend.

8. **Population / fecal-indicator / excretion / degradation hooks** (Table 2 of paper). Each is a small schema or computation extension:
   - Population: `WastewaterSample.population_served` exists (constant). Quasi-constant (weekday/weekend) and unique daily values (wastewater population biomarkers per Choi et al. 2018) are net-new.
   - Fecal indicators: `pcr_target` already supports PMMoV, Bacteroides HF183. A dedicated normalization workflow is net-new.
   - Excretion factors: `WastewaterSample` extension or per-target lookup table.
   - Degradation factors: per-target lookup table per Hart & Halden 2020.
   - Each is a 1-2 session item.

9. **Quality-control and trigger-point computations** (Table 2 of paper). Negative-mass-balance handling, MDL-substitution for non-detects, error-bar propagation, weekly/rolling averages, percent-change calculations. These extend the mass-balance module from item 2 above. ~1 week of cumulative work.

### Total effort estimate for cryptWWDB readiness

- Required items 1-6: ~3-4 weeks once the active-sprint federation completion and CRY-A scaffold ship.
- Recommended items 7-9: another ~3-4 weeks if pursued for production maturity.
- The `B-IMMUNE-HE-1` item (Phase IM-4) is the largest single piece; the paper's TenSEAL-based reference implementation is the natural starting point.

## Collaboration model — Track 1 / Track 2 seam

The Track 1 / Track 2 pattern is the mechanism for collaboration without forking. Track 1 (the federation, privacy, and crypto packages now on `development`) uses current JACKPOT primitives — JWT, presigned URLs, existing `can_access_sample()` permission model, HRRT, DLP. Every Track 1 class accepts a `hooks=` argument that defaults to a `Null<X>Hooks` no-op. Track 2 swaps in concrete implementations via the same constructor argument, with implementations landing under `backend/backend/immune/`. The direction of import is one-way: Track 1 never imports from Track 2.

For cryptWWDB specifically, the integration path is:

1. Concrete implementation of `AISPrivacyHooks.he_compute` at `backend/backend/immune/sec/he_backend.py` wrapping the cryptWWDB protocol (RLWE-based HE via TenSEAL, the mass-balance formula, the temporal equality variants).
2. Concrete implementation of `AISFederationHooks.attest_partner`, `detect_anomalous_traffic`, and `threshold_approve` reflecting the cryptWWDB policy-checker semantics.
3. JACKPOT's wastewater service constructs `FederationClient(hooks=AISFederationHooks(...))` and `PrivacyManager(hooks=AISPrivacyHooks(...))` instead of the null defaults. No Track 1 code changes.

Code from a collaborating research group can land entirely under `backend/backend/immune/` — a clearly bounded namespace, separately license-tagged if needed, separately versioned, and removable without breaking the rest of the platform. The operator-agnostic policy applies to Track 2 the same as Track 1: structural descriptors over proper names in code and docs.

## Strategic framing

The NSF 2115075 work was funded through 2024 and produced a peer-reviewed framework with a working reference implementation. cryptWWDB as published demonstrates the algorithm; cryptWWDB integrated into a multi-tenant operator-deployed platform demonstrates the framework in production with audit, RBAC, multi-pathogen, and ICTV-aligned schema. JACKPOT is positioned to be that platform substrate.

The integration story aligns with several stated public-health-data-sharing concerns the paper raises: the paper notes that ~8% of NWSS records are collected before the wastewater treatment plant, and that data-sharing friction between communities is one of the main barriers to expanding community-level surveillance. JACKPOT's federation L1/L2/L3 model plus the cryptWWDB overlay addresses exactly that friction — neighborhood-level commingling across municipal boundaries with cryptographic privacy guarantees.

License compatibility is clean. JACKPOT is AGPL-3.0. The published cryptWWDB Python implementation uses TenSEAL (Apache 2.0) and SEAL (MIT) under the hood — both compatible with AGPL-3.0 redistribution.

## Discussion topics

Specific items where collaborator input would shape the design:

1. **Lab role in federation.** Is `data_source_lab` a distinct `FederationRole` value or a flag on `peer`? The paper's three-party model implies role-distinct; JACKPOT's federation currently treats all peers symmetrically.
2. **Coordinator implementation site.** The paper's "policy checker" is a logical role; in JACKPOT it could land as additional methods on `FederationClient` or as a standalone `FederationCoordinator` class. Either fits the AIS-hooks pattern.
3. **First query type vs. multiple query types under `he_compute`.** The current `B-IMMUNE-HE-1` description says "one well-defined query type to start." Wastewater mass balance (with the Use Case 2 time variant) is one type. Are there other priority queries (population-normalized mass loads, percent-change time-series) that should land alongside?
4. **Multi-key HE timing.** Lopez-Alt et al. 2012 multi-key HE is the explicit mitigation for the Muni-A-and-Lab collusion risk. Does it land as `B-IMMUNE-HE-2` (after single-key HE proves out in production) or earlier (in parallel with `B-IMMUNE-HE-1` because the production deployment needs the stronger threat model)?
5. **PSI as complementary track.** Trieu's other work (osu-crypto: MultipartyPSI, BaRK-OPRF, SpOT-PSI) is query-time-privacy via PSI rather than computation-time-privacy via HE. PSI fits the same Track 2 seam — the `AISFederationHooks.secure_aggregate` hook could accept a PSI implementation just as cleanly as an HE one. Is there interest in PSI as a parallel JACKPOT extension?
6. **NSF follow-on funding shape.** With cryptWWDB as published prior art and JACKPOT as the production substrate, what's the natural shape of a follow-on grant? Possibilities: production-hardening grant (NSF CICI again, NIH NIBIB, BARDA); biosurveillance integration grant; multi-site deployment grant.

## Source-of-truth navigation

For collaborators new to JACKPOT:

| Topic | File |
|---|---|
| Theoretical anchor (AIS framing) | `Jackpot_AIS.md` |
| Immune Platform plan (Phases IM-1..IM-6) | `jackpot_immune_platform_plan.md` |
| Track 1 / Track 2 seam pattern | `jackpot_immune_collaboration_scaffolding.md` |
| System architecture | `jackpot_architecture.md` (§22 covers federation 3-gate qualification logic) |
| `WastewaterSample` schema | `jackpot_schema.yaml:1065-1198` |
| `wastewater_lineage_abundance` result type | `spec.md:1653` |
| FED-A federation scaffold | `backend/backend/federation/README.md` |
| PRV-A privacy scaffold (incl. `he_compute` hook) | `backend/backend/privacy/README.md` |
| `B-IMMUNE-HE-1` item (HE query layer) | `todo.md:2439` |
| `B-WW-1` wastewater dashboard item | `todo.md:1240` |

Source code: github.com/Midnight-Oil-Innovation/jackpot (AGPL-3.0).

## Acknowledgment

cryptWWDB is the work of Driver, Ahsan, Piske, Lee, Forrest, Halden, and Trieu, funded by NSF award 2115075. The framework described in Driver et al. 2024 *Sci Total Environ* 940:173315 is the foundational reference for the HE integration path described above. Any production integration in JACKPOT would carry forward the citation and acknowledge the originating grant.
