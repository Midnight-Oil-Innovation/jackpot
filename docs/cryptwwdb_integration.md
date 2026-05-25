# cryptWWDB integration — JACKPOT architectural mapping

## Overview

This document maps the privacy-preserving wastewater epidemiology database framework cryptWWDB (Driver, Ahsan, Piske, Lee, Forrest, Halden, Trieu — *Science of the Total Environment* 940:173315, 2024; NSF award 2115075) onto JACKPOT's integration surface as of development HEAD. cryptWWDB is a homomorphic-encryption-based framework that lets two or more municipalities share wastewater concentration and flow data through a third-party laboratory and a computation coordinator without revealing per-site values to one another. The framework matters to JACKPOT because the platform already commits to operator-agnostic federation and a privacy seam (AIS hooks) into which an MPC/HE backend can plug; cryptWWDB is the first concrete query type that exercises that seam end to end. This file resolves the dangling `docs/cryptwwdb_integration.md` reference from `todo.md` item **B-CWB-DOC-2** and is the canonical entry point for the cryptWWDB workstream.

## cryptWWDB Framework Summary

- **Threat model.** Honest-but-curious municipalities and laboratory; non-collusion between the data-holding municipalities and the laboratory is a stated assumption. A coordinator (policy checker) gates queries and enforces access-rate limits. Multi-key HE (Lopez-Alt et al. 2012) is identified as the future mitigation when non-collusion cannot be guaranteed.
- **Cryptographic primitives.** RLWE-based homomorphic encryption (CKKS scheme via TenSEAL / Microsoft SEAL) for arithmetic over ciphertexts; the mass-balance use case requires addition and plaintext-by-ciphertext multiplication only. Threshold signing and TEE attestation are out of scope for the published reference implementation but are the obvious next layers.
- **Query interface.** Two reference queries: (1) mass-load `(Q1·C1) − (Q2·C2)` over encrypted flow `Q` and concentration `C` operands for one timestamp, (2) the same with a temporal equality check across two timestamps. Both yield ciphertexts that the data owner decrypts; intermediate parties never see plaintext.
- **Participation model.** Two data-holding municipalities (Muni A, Muni B) plus a third-party laboratory that produces concentration measurements plus a computation coordinator. Roles are role-distinct: the lab never holds samples, the municipalities never run pipelines, the coordinator never holds keys.
- **Data schema assumptions.** Per-sample flow rate, concentration of one or more target chemicals, sewershed upstream/downstream relationship, collection timestamp. The framework is target-agnostic — the paper demonstrates the approach with opioid biomarkers (heroin, 6-acetylmorphine) but the same scheme applies to pathogen RNA copies.
- **Key guarantees.** Correctness — the encrypted mass-balance is bit-for-bit faithful to the plaintext computation within CKKS approximation bounds. Privacy — neither municipality learns the other's `Q` or `C`, and the laboratory never learns either side's flow data. Operator non-collusion — the coordinator policy and the multi-key extension together prevent a single misbehaving operator from breaking confidentiality.
- **Operational scope.** Rate-limited access via the coordinator, per-query audit, key custody by the data-holding municipalities, and (in the multi-key extension) explicit participation certificates per query.

## JACKPOT Integration Surface

The table below maps each cryptWWDB concept to the JACKPOT module that hosts it today and the status of that hosting as of development HEAD (commit on `cryptwwdb-doc` branch, May 2026). Status values: `implemented` (lands in `development`, used at runtime), `scaffolded` (Protocol/seam defined, Track 1 null default in place, Track 2 implementation pending), `planned` (backlog item exists with concrete file plan), `not-started` (no backlog item yet).

| cryptWWDB Concept | JACKPOT Module | File | Status | Notes | Backlog Item |
|---|---|---|---|---|---|
| Privacy hook seam (AISHooks Protocol) | `backend.privacy`, `backend.crypto`, `backend.federation` | `backend/backend/privacy/_ais_hooks.py`, `backend/backend/crypto/_ais_hooks.py`, `backend/backend/federation/_ais_hooks.py` | implemented | Three Protocol surfaces shipped post-PRV-A/FED-A/CRY-A: six privacy hooks (incl. `he_compute`, `mpc_protocol`, `dp_noise`), four crypto hooks (`select_he_backend`, `threshold_sign`, `verify_tee_attestation`, `enforce_key_rotation_policy`), five federation hooks. | — |
| Null/no-op default implementation (NullHooks) | `backend.privacy`, `backend.crypto`, `backend.federation` | Same three `_ais_hooks.py` files | implemented | `NullAISPrivacyHooks`, `NullAISCryptoHooks`, `NullAISFederationHooks` ship as Track 1 defaults; cryptographically dangerous hooks (`threshold_sign`, `mpc_protocol`) refuse with `NotImplementedError` rather than silently degrade. | — |
| Federation partner model (FederatedPartner or equivalent) | `backend.federation` | `backend/backend/federation/models.py` (`FederationRole`, `FederatedInstance`) | implemented | `FederationRole.DATA_SOURCE_LAB` enum value already lands (B-CWB-FED-1) for the cryptWWDB three-party model. `FederatedInstance` Pydantic model + `federated_instances` table land in FED-A/FED-D. | B-CWB-FED-1 |
| Mass-balance / concentration normalisation | `backend.wastewater` | `backend/backend/wastewater/mass_balance.py` | implemented | Tier 1 plaintext reference implementation lands; computes `(Q1·C1) − (Q2·C2)` with unit-aware flow/concentration handling, LOD/2 non-detect substitution, and pluggable negative-mass-balance policy. Tier 2 HE variant delegates to `AISPrivacyHooks.he_compute`. | B-IMMUNE-HE-1 |
| Operator-agnostic query dispatch | `backend.federation` | `backend/backend/federation/client.py`, `push.py`, `access.py` | scaffolded | Three federation levels (L1 query, L2 hub push, L3 bidirectional access) wired through `FederationClient`/`FederationPushJob`/`FederationAccessGateway`; cross-site aggregate planning that drives cryptWWDB Use Case 1/2 across `data_source_lab` partners is net-new. | R-6 |
| Cryptographic record linkage / record de-identification | `backend.privacy`, `backend.crypto` | `backend/backend/privacy/dlp.py`, `scrubber.py`, `coarsening.py`; `backend/backend/crypto/crypt4gh.py` | scaffolded | HRRT genomic scrubber + GCP Cloud DLP metadata scanner + coarsening rules + Crypt4GH per-file encryption shipped; cryptographic commitment of audit-log entries and operator participation certificates are not yet wired. | R-4, R-5 |

## Required Additions

**R-1 — MPC/secret-sharing adapter behind AISHooks**
Add a concrete `mpc_protocol` implementation to a Track 2 `AISPrivacyHooks` backend under `backend/backend/immune/sec/mpc_backends.py` that wraps an MPC library (candidate: MP-SPDZ or a Python-native equivalent) so federated mass-load queries that cannot use single-key HE fall through to secret-sharing without leaking the operand boundary into Track 1 code. The natural home is `backend.privacy._ais_hooks.AISPrivacyHooks.mpc_protocol`, which today raises `NotImplementedError` in the null default.
Backlog: `B-IMMUNE-MPC-1` (TBD — propose at next backlog grooming)

**R-2 — cryptWWDB query schema validation**
Add a query-schema validator under `backend/backend/wastewater/query_schema.py` (and matching Pydantic models) that asserts the shape of a cryptWWDB-style federated query before it leaves the originating instance: at minimum the `(Q1, C1, Q2, C2, t)` tuple, declared units, sewershed-association identifier, and target identifier. The validator runs ahead of `FederationClient.query()` for any query whose `query_type == "mass_balance"`. This belongs in the `backend.wastewater` module so the schema lives alongside `mass_balance.py`.
Backlog: `B-CWB-QSV-1` (TBD)

**R-3 — Differential-privacy noise injection hook**
Add a Track 2 `AISPrivacyHooks.dp_noise` implementation that injects calibrated Gaussian/Laplace noise into mass-balance results before they leave the operator boundary, gated by the existing `track_dp_budget` hook so repeated queries deplete a per-partner budget. The natural home is `backend/backend/immune/sec/dp_backend.py` (Track 2) calling out from the existing `backend.privacy._ais_hooks.AISPrivacyHooks` Protocol entry point.
Backlog: `B-IMMUNE-DP-1`

**R-4 — Participation certificate / operator attestation**
Add a participation-certificate flow under `backend.federation`: each cryptWWDB query carries a short-lived certificate signed by the partner's key (FROST/BLS via `AISCryptoHooks.threshold_sign`) that asserts the partner's consent to participate in this specific query, with an `expires_at` and a query-hash binding. The natural home is `backend/backend/federation/participation.py` (net-new module) with verification wired through `AISFederationHooks.attest_partner`.
Backlog: `B-CWB-PCERT-1` (TBD)

**R-5 — Audit-log cryptographic commitment**
Extend `backend.audit` so each `audit_log` row carries a Merkle-tree hash chain (or signed-receipt equivalent) over the row's `(action, actor, resource, before, after, metadata, timestamp)` so an operator can prove non-tampering of the cryptWWDB query history to a downstream collaborator without revealing row contents. The natural home is a new column on the existing `audit_log` table plus a writer hook in `backend/backend/audit.py`, with the signing operation delegated to `AISCryptoHooks.threshold_sign`.
Backlog: `B-CWB-AUDIT-1` (TBD)

**R-6 — Cross-site aggregate query planner**
Add a planner under `backend/backend/federation/planner.py` that, given a cryptWWDB-shaped query and a directory of `data_source_lab` and data-holding partners, produces the per-partner subqueries, the encrypted-arithmetic plan, and the decryption-key holders for the result; today `FederationClient` dispatches one query to one partner. The planner is the natural place for the three-party (Muni A / Muni B / Lab) coordination logic that cryptWWDB requires.
Backlog: `B-CWB-PLAN-1` (TBD)

## Recommended Additions

**Rec-1 — Key-rotation lifecycle**
Operationalise the `AISCryptoHooks.enforce_key_rotation_policy` hook with a concrete rotation schedule (default 90 days for federation API keys, 180 days for HE evaluation keys, per-operator override), an `expiring_keys` admin view, and a one-shot `jackpot keys rotate` CLI subcommand. Today the null default returns `ALLOW` unconditionally; cryptWWDB participation should track rotation explicitly because the multi-key extension binds participants to specific key versions.
Backlog: `B-CRY-ROT-1` (TBD)

**Rec-2 — Synthetic-data regression test fixtures aligned to cryptWWDB schema**
Add a fixture generator under `backend/tests/fixtures/cryptwwdb_synthetic.py` that produces deterministic `(Q1, C1, Q2, C2, t)` tuples with known mass-balance outcomes, plus matching `WastewaterSample` + `wastewater_target_concentration` rows so the HE backend and the plaintext reference can be compared bit-for-bit in CI. Synthetic-only per Critical Rule 56 — no real operator data.
Backlog: `B-CWB-FIX-1` (TBD)

**Rec-3 — Federation dashboard privacy-budget indicator**
Extend the Streamlit federation dashboard (`frontend/pages/federation.py`, planned) with a per-partner privacy-budget bar driven by `AISPrivacyHooks.track_dp_budget` so operators can see in one place how much DP budget cryptWWDB queries have consumed for each `data_source_lab` partner, with the indicator turning red when the operator-configured threshold is crossed.
Backlog: `B-CWB-DASH-1` (TBD)

## Open Questions

- **MPC library choice (gates R-1).** MP-SPDZ has the most complete primitive set and a Python frontend but a heavyweight build; alternatives include Carbyne Stack, secretflow/SPU, and pure-Python `crypten`. The decision is constrained by deployability into JACKPOT's GCP Batch task images and into Scenario B (HPC + Apptainer) environments without a vendor-managed runtime.
- **NSF data-sharing agreement scope (gates R-2 and R-4).** The cryptWWDB published reference does not bundle a data-sharing agreement template; participating municipalities in JACKPOT need a model agreement covering query rate limits, audit-log retention, key custody, and breach notification before any production query can run. Resolving this depends on the NSF 2115075 follow-on conversation.
- **Operator key-custody model (gates R-4, Rec-1).** Does each `data_source_lab` partner custody its own evaluation key via GCP Secret Manager / PKCS#11 / OS keychain, or does a coordinator-side key escrow simplify the multi-key extension? The answer changes the `AISCryptoHooks.select_he_backend` signature and the rotation CLI surface.
- **Schema versioning strategy (gates R-2 and Rec-2).** When the `wastewater_target_concentration` result type and the `wastewater_upstream_of` association type land (B-CWB-SCHEMA-1, B-CWB-SCHEMA-2 in Phase 24.5), every existing cryptWWDB query carries a schema version. We need a published policy on how query producers and partners negotiate schema version compatibility — sticky-version per partner, latest-version-with-fallback, or a `negotiate_schema` federation handshake.
- **Coordinator placement (gates R-6).** Is the cryptWWDB coordinator a logical role implemented as additional methods on `FederationClient`, or a standalone `FederationCoordinator` deployment that data-holding partners point at? The first reuses existing auth/RBAC; the second matches the paper's three-party diagram more literally and supports multi-coordinator topologies.
- **Multi-key HE timing (gates R-1, R-6, Rec-1).** Lopez-Alt et al. 2012 multi-key HE removes the non-collusion assumption but is performance-heavy. Does it land alongside the first single-key implementation (`B-IMMUNE-HE-1`) or as a follow-on (`B-IMMUNE-HE-2`) once the single-key path is validated in production?

## References

[1] Driver, A., Ahsan, A., Piske, M., Lee, K., Forrest, S., Halden, R.U., Trieu, N.H. (2024). Encrypted data-sharing for preserving privacy in wastewater-based epidemiology. *Science of the Total Environment*, 940, 173315. https://doi.org/10.1016/j.scitotenv.2024.173315 — funded by NSF award 2115075.

[2] JACKPOT AIS design — `docs/immune_platform.md` Part 1 (post-Cluster-B merge; absorbed `docs/Jackpot_AIS.md`). AIS framing for the JACKPOT immune platform, including the `AISPrivacyHooks` / `AISCryptoHooks` / `AISFederationHooks` Protocol surfaces that host cryptWWDB integration.

[3] JACKPOT federation operations — `docs/federation_operations.md` (post-FED-A; B-CWB-DOC-1). Operator-facing reference for federation roles, the three federation levels, partner attestation, and the cryptWWDB three-party non-collusion assumption.

[4] JACKPOT immune platform plan — `docs/immune_platform.md` §15 (post-Cluster-B merge; absorbed `docs/jackpot_immune_platform_plan.md`). Phases IM-1..IM-6 including IM-4 where the cryptWWDB-specific HE backend (B-IMMUNE-HE-1) lands at `backend/backend/immune/sec/he_backend.py`.

[5] JACKPOT immune collaboration scaffolding — `docs/immune_platform.md` Part 2 §§22-29 (post-Cluster-B merge; absorbed `docs/jackpot_immune_collaboration_scaffolding.md`). Track 1 / Track 2 seam pattern that lets cryptWWDB collaborators land entirely under `backend/backend/immune/` without modifying Track 1 code.

[6] Lopez-Alt, A., Tromer, E., Vaikuntanathan, V. (2012). On-the-fly multiparty computation on the cloud via multikey fully homomorphic encryption. *Proceedings of the 44th ACM Symposium on Theory of Computing* (STOC '12), 1219–1234. The multi-key HE primitive that removes the non-collusion assumption when wired in via R-1.
