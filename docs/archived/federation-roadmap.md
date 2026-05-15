# Federation roadmap
# Superseded 2026-05-14 by `docs/federation.md`. This file kept for history.

JACKPOT's federation architecture is built in three sibling layers: **federation primitives** (query federation, hub push, bidirectional access), **privacy primitives** (DP, FL aggregation, HE, MPC, synthetic substitution), and **crypto primitives** (key management, signing, threshold crypto, TEE attestation). Each layer is a Python package under `backend/backend/` that ships a Track 1 implementation using current JACKPOT primitives, plus a Track 2 AIS-augmented hook seam where collaborator overlays plug in via dependency injection without forking the package. This is the same pattern across all three layers — `_ais_hooks.py` defines a runtime-checkable Protocol, `Null<X>Hooks` provides the no-op default, and the package's Track 1 classes accept `hooks=` constructor arguments.

This doc supersedes the snapshot in `federation-design.md` by adding the privacy and crypto layers and the HE / MPC / DP detail. It covers the current state, the active-sprint work, the cryptWWDB-readiness sequence, and the full Phase IM-4 buildout where the AIS-augmented overlays land.

## Architectural shape

Three federation levels with distinct primitives:

| Level | Primitive | Track 1 class | Use cases |
|---|---|---|---|
| L1 query federation | Async fanout queries to enabled partners; result aggregation | `FederationClient` | Federated sample search, lineage-frequency meta-analysis, AMR fingerprint queries |
| L2 hub push | Qualified sample push to designated hub | `FederationPushJob` | NWSS-style upstream reporting, GISAID submission analogs |
| L3 bidirectional access | Peer-to-peer sample access requests | `FederationAccessGateway` | Outbreak investigation cross-jurisdiction access, federation memory cell promotion |

The L2 push qualification enforces three gates from `jackpot_architecture.md` §22: `surveillance_relevant`, `sharing_level ≥ minimum`, `quality_status ≥ ANALYZABLE`. The payload schema enforces the negative list (no `host_age`, no FASTQ, no PII) by never reading those fields — defensive design, not filter-after-the-fact.

## The three scaffolds and what they contain

**FED-A — federation scaffold** (merged 2026-05-08, on `development`). Package at `backend/backend/federation/`. Files: `models.py` (Pydantic v2 — `FederatedInstance`, `FederationRole` enum, `FederationQuery`, `FederationQueryResult`, `FederationPushPayload`, `FederationAccessRequest`), `client.py`, `push.py`, `access.py`, `_ais_hooks.py`, `README.md`. Implements the three federation levels with five AIS hook seams.

**PRV-A — privacy scaffold** (merged Session 21 as PR #39, on `development`). Package at `backend/backend/privacy/`. Mirrors FED-A pattern. Files: `coarsening.py` (host-age generalization and similar primitives that already ship), `scrubber.py` (HRRT wrapper), `dlp.py` (GCP Cloud DLP integration), `budget.py` (DP budget tracking placeholder), `_ais_hooks.py`, `README.md`. Six AIS hook seams covering DP, FL, HE, MPC, synthetic substitution.

**CRY-A — crypto scaffold** (PENDING, active sprint candidate). Package at `backend/backend/crypto/`. Same pattern. Files: `keys.py` (PKCS#11 / Secret Manager / file-system keystore abstraction), `signing.py` (Sigstore/cosign artifact signing), `crypt4gh.py` (per-file encryption for ingest/egress, GA4GH standard), `_ais_hooks.py`, `README.md`. AIS hook seams covering HE backend selection, threshold signing (FROST/BLS/DKG), TEE attestation evidence verification, key-rotation policy enforcement.

The three scaffolds are sibling packages — none imports from another. CRY-A's HE backend selection feeds PRV-A's `he_compute` hook implementation; PRV-A's federation aggregations feed FED-A's `secure_aggregate` hook; FED-A's federation-key auth uses CRY-A's key management. Integration is via dependency injection of concrete hook implementations at service-construction time, not via direct package coupling. This keeps the dependency graph one-directional and the seams clean.

## The AIS hook surface (federation + privacy + crypto)

The full surface of pluggable seams across all three scaffolds, with current implementation status:

| Hook | Scaffold | AIS doc ref | Track 2 module | Status |
|---|---|---|---|---|
| `secure_aggregate(results, partner_set)` | FED-A | §1.6 inter-instance signaling | `backend/backend/immune/sec/cs_cyber_federated.py` | Hook defined; Track 2 pending |
| `attest_partner(instance)` | FED-A | §1.7 attribution & deception | `backend/backend/immune/sec/` (attestation primitives) | Hook defined; Track 2 pending |
| `detect_anomalous_traffic(query, partner)` | FED-A | §1.3 innate immunity | `backend/backend/immune/algorithms/featurizers/` + `redteam/attack_federation.py` | Hook defined; Track 2 pending |
| `threshold_approve(action, partner_set)` | FED-A | §1.8 tolerance/regulation | `backend/backend/immune/sec/` (threshold-crypto primitives) | Hook defined; Track 2 pending |
| `validate_push_payload(payload, target)` | FED-A | §1.8 tolerance ("don't attack self") | `backend/backend/immune/sec/refusal.py`, `parsers_safe.py` | Hook defined; Track 2 pending |
| `dp_noise(query_result, sensitivity)` | PRV-A | §1.4 adaptive immunity | `backend/backend/immune/sec/cs_cyber_federated.py` | Hook defined; Track 2 pending |
| `track_dp_budget(requester, epsilon)` | PRV-A | §1.8 tolerance/regulation | `backend/backend/immune/sec/` (DP budget accountant) | Hook defined; Track 2 pending |
| `fl_aggregate(local_updates)` | PRV-A | §1.6 inter-instance signaling | `backend/backend/immune/sec/cs_cyber_federated.py` | Hook defined; Track 2 pending |
| `he_compute(encrypted_inputs, op)` | PRV-A | §1.4 adaptive immunity | `backend/backend/immune/sec/he_backend.py` (new) | Hook defined; Track 2 = `B-IMMUNE-HE-1` |
| `mpc_protocol(parties, computation)` | PRV-A | §1.6 inter-instance signaling | `backend/backend/immune/sec/mpc_backend.py` (new) | Hook defined; Track 2 pending |
| `synthetic_substitute(real_dataset)` | PRV-A | §1.5 diversity layer | `backend/backend/immune/algorithms/featurizers/` | Hook defined; Track 2 pending |
| HE backend selection | CRY-A | (TBD in scaffold) | `backend/backend/immune/sec/he_backend.py` (shared with PRV-A) | Scaffold pending |
| Threshold signing (FROST/BLS/DKG) | CRY-A | (TBD in scaffold) | `backend/backend/immune/sec/` (threshold primitives) | Scaffold pending |
| TEE attestation evidence | CRY-A | §1.7 attribution & deception | `backend/backend/immune/sec/` (attestation) | Scaffold pending |
| Key-rotation policy | CRY-A | §1.8 tolerance/regulation | (operator-configured) | Scaffold pending |

All Track 1 calls pass through `Null<X>Hooks` no-op defaults by default. Operators who don't enable Track 2 overlays get safe, do-nothing behavior — federation still works, just without the AIS-augmented safety properties. Operators who DO enable Track 2 (by constructing services with concrete `hooks=` arguments) get the full immune-system surface.

## HE — homomorphic encryption

**What it is.** Computation directly on ciphertext, producing encrypted results. JACKPOT uses RLWE-based HE (Brakerski & Vaikuntanathan 2011; Stehlé et al. 2009) for the quantum-resistance property; the reference implementation uses TenSEAL (Ayoub et al. 2021).

**Where it lives.** The `AISPrivacyHooks.he_compute(encrypted_inputs, op)` hook is the Track 1 seam in PRV-A. The Track 2 implementation lands at `backend/backend/immune/sec/he_backend.py`. The CRY-A scaffold's HE backend selection feeds into the same module — choice of single-key vs multi-key HE, choice of key sizes, choice of polynomial modulus degree.

**Concrete items.** Two tracked under Phase IM-4 (currently Tracked, Not Scheduled):

- **`B-IMMUNE-HE-1`** Single-key HE query layer at `backend/immune/net/query_he.py` (Kim 2021). First concrete query type: wastewater mass balance per Driver et al. 2024 — `(Q1·C1) − (Q2·C2)` over RLWE-encrypted operands, including the Use Case 2 temporal-equality variant. Second concrete query type: "do you have a memory cell matching this signature?" 1-2 weeks for memory-cell baseline plus 1-2 weeks for wastewater concrete.

- **`B-IMMUNE-HE-2`** Multi-key HE extension per Lopez-Alt et al. 2012. Each federation entity holds its own secret key; decryption requires participation from all key holders. Eliminates the collusion attack identified in Driver et al. 2024 §4. Same `he_backend.py` interface, different crypto backend. 2-3 weeks of significant crypto work; triggered when single-key HE proves the operational model.

**Use cases.** Federated mass-balance computation for wastewater epidemiology (the cryptWWDB application); memory-cell matching across federation peers without revealing the signature; future: federated lineage-frequency aggregation, federated AMR fingerprint similarity queries.

**Threat model.** Single-key HE leaks under Muni-A-and-Lab collusion. Multi-key HE eliminates that. The federation operations doc (`B-CWB-DOC-1`, pending) documents this assumption for operators.

## MPC — multi-party computation

**What it is.** Cryptographic protocols where multiple parties jointly compute a function over their private inputs while revealing only the output. Related to but distinct from HE — HE keeps inputs encrypted during computation; MPC keeps inputs distributed across parties during computation. PSI (private set intersection) is a specialized MPC primitive answering "do you have any of these items?" without revealing the items themselves.

**Where it lives.** The `AISPrivacyHooks.mpc_protocol(parties, computation)` hook is the Track 1 seam in PRV-A. Track 2 lands at `backend/backend/immune/sec/mpc_backend.py` (new module under IM-4).

**Concrete items.** None currently tracked as MPC-specific items in todo.md. The closest is the FedTADBench-driven framework decision:

- **`B-FED-PILLARIII-1`** (Phase IM-4) Decide FL framework for Pillar III via FedTADBench benchmark (Liu et al. 2022). Compares DataSHIELD-class vs FedAdapt-CAD vs FedMI vs Conclave-style MPC platforms on representative anomaly-detection workloads. 2 weeks benchmarking + 1 week documentation.

**Use cases.** Trieu's osu-crypto work (MultipartyPSI, BaRK-OPRF, SpOT-PSI) is the natural MPC contribution path — query-time privacy for "do you have a sample matching this signature?" queries. Federated trust score computation where multiple parties contribute without revealing inputs. Federated query joins where no single party sees the full join. Conclave-style multi-party analytics for federation-wide rollups.

**Relationship to HE.** Complementary, not redundant. HE answers "compute on my encrypted data"; MPC answers "compute jointly without sharing inputs." cryptWWDB Use Case 2-time-efficient already uses MPC-style delegation — Muni A sends encrypted time to Muni B, who performs plaintext-ciphertext comparison locally rather than the lab performing ciphertext-ciphertext comparison. Both fit under PRV-A's hooks; both could plug into the same Track 2 implementation.

## DP — differential privacy

**What it is.** Formal mathematical privacy guarantees via calibrated noise addition. A DP mechanism with privacy parameter ε bounds the probability that any individual's data affects the output. Practically: federation-wide aggregations get noise added; sensitivity analysis determines how much; per-requester budget tracking prevents repeated-query attacks.

**Where it lives.** Two PRV-A hooks: `dp_noise(query_result, sensitivity)` adds calibrated noise to query results; `track_dp_budget(requester, epsilon)` enforces per-requester budget limits. Track 2 implementations land in `backend/backend/immune/sec/`.

**Concrete items.** One tracked under Phase IM-4:

- **`B-IMMUNE-DP-1`** Differential-privacy aggregator for shared signals. Federation-wide aggregations (member counts, signal frequencies, lineage frequencies, AMR fingerprint distributions) computed with formal DP guarantees. Lands inside the existing `B-PRV-1` privacy-scaffold pattern. ~1 week.

Plus the related future-phase item:

- **`B-PRV-1`** (Phase P1 deferred) Privacy hardening — DP enforcement across all federation aggregation paths, FL coordinator with DP-SGD, DLP rule expansion. Reduces to concrete impl of `AISPrivacyHooks` Protocol via `backend/backend/immune/sec/` once PRV-A scaffold lands (which it has).

**Use cases.** Federation-wide aggregations protected by DP guarantees rather than just "negative list" defensive design. Per-requester budget tracking to prevent inference attacks via repeated queries. Disclosure protection for small-cell-size geospatial data — relevant for the wastewater building-level sampling concern raised in Driver et al. 2024 (the paper explicitly cites "fewer people contributing to a sample" as a privacy risk at sub-sewershed resolution).

**Tunable tradeoff.** DP buys formal privacy at the cost of utility degradation. ε too small → noisy results; ε too large → weak guarantees. Operator policy decision. `B-IMMUNE-DP-1` ships with a default ε and a policy mechanism for per-deployment override.

## The phased roadmap

### Stage 0 — Current state (on `development`)

- **FED-A scaffold** complete with all five `AISFederationHooks` defined.
- **PRV-A scaffold** complete with all six `AISPrivacyHooks` defined.
- Federation primitives operate via `NullAIS*Hooks` defaults — Track 1 functionality works without any Track 2 overlay.
- The HRRT scrubber and GCP Cloud DLP that already ship are consolidated under PRV-A's `scrubber.py` and `dlp.py`.

### Stage 1 — Scaffold completion (~4-6 weeks)

Active sprint candidates that close out the Track 1 surface:

- **FED-B** (federation router): `backend/backend/routers/federation.py` exposing `/api/v1/federation/{instances,search,push,access-requests}` endpoints. Federation API keys via `X-JACKPOT-Federation-Key` header; standard JWT + `require_platform_admin` for admin endpoints. **+ `B-CWB-DOC-1`** (`docs/federation_operations.md` covering non-collusion assumption + multi-key HE pathway).
- **FED-C** (federation tests): `tests/federation/` with ≥95% coverage on every module in `backend/backend/federation/`. Use `respx` to mock partner HTTP.
- **FED-D** (schema migration): `federated_instances` table per the `models.py` shape; new columns on `organizations`. **+ `B-CWB-FED-1`** (`data_source_lab` value in `FederationRole` enum).
- **FED-E** (wiring): Register FED-B router in `main.py`; add federation-key guard to `auth/guards.py`.
- **CRY-A scaffold**: `backend/backend/crypto/` package mirroring FED-A and PRV-A patterns. AIS hook seams for HE backend selection, threshold signing, TEE attestation, key rotation.

At end of Stage 1, all three scaffolds are complete on `development`. Track 1 federation works end-to-end with `Null<X>Hooks` defaults; Track 2 overlay sockets are all defined and ready to accept implementations.

### Stage 2 — cryptWWDB-readiness (~4-6 weeks)

Per `cryptwwdb-integration.md` and the merged backlog additions:

- **Phase 24.5 schema items** (`B-CWB-SCHEMA-1` through `B-CWB-SCHEMA-5`): upstream-of association_type enum, target-concentration result type, time-varying population fields, fecal-normalization table, excretion/degradation factor tables.
- **P0b ships** the cryptWWDB schema items alongside the existing v5.0 migration.
- **`B-CWB-MB-1`**: Tier 1 plaintext mass-balance computation module.
- **`B-WW-1`**: wastewater lineage-abundance Streamlit dashboard.
- **`B-CWB-DOC-1` and `B-CWB-FED-1`** ship with Stage 1 federation work.

At end of Stage 2, JACKPOT is "ready to collaborate" — drop-in ready to receive the cryptWWDB HE implementation as a Track 2 overlay at `backend/backend/immune/sec/he_backend.py`.

### Stage 3 — Full Phase IM-4 (Tracked, Not Scheduled, ~6 weeks)

The IM-4 buildout converts the Track 2 sockets to concrete implementations. Sequencing within IM-4:

| Item | Function | Effort |
|---|---|---|
| `B-IMMUNE-FED-SCHEMA-1` | Schema: `federation_members`, `trust_scores`, `cyber_assessments` tables | 2-3 sessions |
| `B-IMMUNE-TRUST-1` | TrustEngine — per-member trust scores from submission quality, FP rate, behavioral consistency | 4-5 sessions |
| `B-IMMUNE-REP-1` | AntibodyRepertoire publish/subscribe — anonymized detector repertoire shared across federation | 3-4 sessions |
| `B-IMMUNE-MEMSYNC-1` | Federation memory cell sync — cross-member confirmation thresholds before global promotion | 3-4 sessions |
| `B-IMMUNE-HE-1` | Single-key HE query layer — wastewater mass balance + memory cell match | 2-4 weeks |
| `B-IMMUNE-DP-1` | DP aggregator for shared signals | 1 week |
| `B-FED-PILLARIII-1` | FL framework decision via FedTADBench | 3 weeks |
| `B-IMMUNE-HE-2` | Multi-key HE extension per Lopez-Alt 2012 | 2-3 weeks |
| `B-COLLAB-DIVERSITY-2` | Federation diversity index with CI gate | 2 days |
| `B-COLLAB-ATRUST-1` | Asymmetric trust between federation members | 2 days |
| `B-COLLAB-REDTEAM-3` | Adversarial test suite for federation | 3 days |

Phase IM-4 success criterion: two JACKPOT instances on one network can (1) share a confirmed memory cell after cross-instance confirmation; (2) run a homomorphic-encrypted query without raw data leaving either side; (3) compute federation-wide diversity and refuse operations when diversity drops; (4) complete Outbreak case 8 in 2-player coordination mode.

## Sequencing and unresolved decisions

**The blocking chain.** Stage 1 (FED-B/C/D/E + CRY-A) is the active-sprint pick — it unblocks both Stage 2 and Stage 3. Stage 2 (cryptWWDB-readiness) requires P0b to ship the schema items. Stage 3 (Phase IM-4) is gated on coalition timing: pulling it forward from "Tracked, Not Scheduled" depends on Trieu/Forrest/Halden/Scarpino conversations and any follow-on grant funding.

**Decisions open for input.**

1. **MPC vs HE for cryptWWDB.** The paper uses single-key HE. JACKPOT supports both via separate hooks. Is there value in implementing MPC-based variants of the wastewater mass-balance query alongside HE, or stay HE-only for the first concrete implementation?
2. **DP default ε.** `B-IMMUNE-DP-1` needs a default ε. Literature-standard values range from 0.1 (strong) to 10 (weak). Operator policy decision; needs documentation in the federation operations doc.
3. **FL framework choice.** `B-FED-PILLARIII-1` is the methodology. DataSHIELD vs FedAdapt-CAD vs FedMI vs Conclave-style MPC. Decision depends on benchmark.
4. **Multi-key HE timing.** `B-IMMUNE-HE-2` could land in parallel with `B-IMMUNE-HE-1` (stronger threat model from day one) or after (single-key proves the operational model first). Recommendation: after, unless first production deployment specifically needs the collusion mitigation.
5. **CRY-A AIS hook surface.** The CRY-A scaffold's hook signatures are TBD per the spec at `todo.md` Federation/Privacy/Crypto Scaffolds section. Refining the surface against `Jackpot_AIS.md` is part of the CRY-A landing PR.

## Coalition cross-references

The roadmap maps to coalition conversations as follows:

- **Forrest (Biodesign BSS)** — the AIS framing across all five `AISFederationHooks` and six `AISPrivacyHooks`. `Jackpot_AIS.md` is the conceptual entry point.
- **Trieu (SCAI)** — PSI work feeds `AISPrivacyHooks.mpc_protocol` Track 2 implementation. `B-COLLAB-ATRUST-1` (asymmetric trust) is a natural collaboration point.
- **Halden (Biodesign EHE) + Driver et al.** — cryptWWDB integration via `AISPrivacyHooks.he_compute` Track 2. Sequence per `cryptwwdb-integration.md`.
- **Lee (SCAI + Biodesign)** — featurizer registry across `AISFederationHooks.detect_anomalous_traffic` and `AISPrivacyHooks.synthetic_substitute`. Maps to his TCR-Gen / catELMo attention-based embedding work.
- **Scarpino (EPISTORM)** — federated wastewater metagenomics overlay. Maps to `B-IMMUNE-FED-PILLARIII-1` FL framework decision plus the wastewater track.
- **Pathak (STPH)** — the privacy/crypto/federation curriculum mapping to TPH557 (Ethics, Policy, Law) plus TPH552 (Systems Design).

## Source-of-truth navigation

| Topic | File |
|---|---|
| Theoretical anchor | `Jackpot_AIS.md` |
| Track 1 / Track 2 seam pattern | `jackpot_immune_collaboration_scaffolding.md` §3.2 |
| Full IM-4 federation plan | `jackpot_immune_platform_plan.md` §6, §10.5 |
| Three-gate federation push qualification | `jackpot_architecture.md` §22 |
| FED-A scaffold | `backend/backend/federation/README.md` |
| PRV-A scaffold | `backend/backend/privacy/README.md` |
| FED-B/C/D/E pending items | `todo.md` Federation/Privacy/Crypto Scaffolds section |
| Phase IM-4 backlog | `todo.md` Phase IM-4 section |
| cryptWWDB integration path | `docs/cryptwwdb_integration.md` (per merge script) |
| Federation operations + non-collusion assumption | `docs/federation_operations.md` (pending via `B-CWB-DOC-1`) |
