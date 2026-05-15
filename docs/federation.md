# Federation

JACKPOT's federation system enables multiple JACKPOT instances — across labs, agencies, or jurisdictions — to share pathogen genomics data and queries without each instance giving up control of its own data or operating policies. Federation is implemented as **three sibling Python packages** at `backend/backend/federation/`, `backend/backend/privacy/`, and `backend/backend/crypto/`, each shipping a **Track 1** implementation using current JACKPOT primitives plus a **Track 2** AIS-augmented hook seam where collaborator overlays plug in via dependency injection without forking the package.

A **federation scaffold** is one of those three sibling packages. Each scaffold follows the same shape: a sibling `_ais_hooks.py` defines a `@runtime_checkable` Protocol for the augmentation surface; a `Null<X>Hooks` class provides the no-op default; the Track 1 classes (clients, jobs, gateways) accept `hooks=` constructor arguments so concrete implementations can be swapped in at service-construction time without code changes to the Track 1 classes themselves. The three scaffolds — federation, privacy, crypto — are sibling packages: none imports from another. Integration happens via the AIS hook surface, which keeps the dependency graph one-directional and the seams clean.

A **federation level** is one of three distinct integration patterns that JACKPOT instances use to interact: **L1 query federation** (async fanout of queries to enabled partners, with result aggregation), **L2 hub push** (qualified upstream reporting of samples to a designated hub), and **L3 bidirectional access** (peer-to-peer sample access requests). Each level has its own Track 1 class, its own set of AIS hooks, and its own use cases. An operator can enable any subset of L1/L2/L3 — they're independent capabilities.

**Current state (Stage 0, on `development`):** FED-A and PRV-A scaffolds are complete with all eleven `AISFederationHooks` + `AISPrivacyHooks` defined. Federation primitives operate via `Null<X>Hooks` defaults — Track 1 functionality works end-to-end without any Track 2 overlay. CRY-A scaffold is pending. Stage 1 (FED-B/C/D/E + CRY-A) is the active sprint candidate; Stages 2 and 3 cover cryptWWDB-readiness and the full Phase IM-4 buildout respectively.

## §1. Architectural shape

### §1.1 Three federation levels

| Level | Primitive | Track 1 class | Use cases |
|---|---|---|---|
| L1 query federation | Async fanout queries to enabled partners; result aggregation | `FederationClient` | Federated sample search, lineage-frequency meta-analysis, AMR fingerprint queries |
| L2 hub push | Qualified sample push to designated hub | `FederationPushJob` | NWSS-style upstream reporting, GISAID submission analogs |
| L3 bidirectional access | Peer-to-peer sample access requests | `FederationAccessGateway` | Outbreak investigation cross-jurisdiction access, federation memory cell promotion |

The L2 push qualification enforces three gates from `jackpot_architecture.md` §22: `surveillance_relevant`, `sharing_level ≥ minimum`, `quality_status ≥ ANALYZABLE`. The payload schema enforces the negative list (no `host_age`, no FASTQ, no PII) by never reading those fields — defensive design, not filter-after-the-fact.

### §1.2 The three sibling scaffolds

The federation system is built in three layers, each a Python package under `backend/backend/`:

- **Federation primitives** (`backend/backend/federation/`) — query federation, hub push, bidirectional access. Scaffold name: FED-A.
- **Privacy primitives** (`backend/backend/privacy/`) — DP, FL aggregation, HE, MPC, synthetic substitution. Scaffold name: PRV-A.
- **Crypto primitives** (`backend/backend/crypto/`) — key management, signing, threshold crypto, TEE attestation. Scaffold name: CRY-A.

The three scaffolds are sibling packages — none imports from another. CRY-A's HE backend selection feeds PRV-A's `he_compute` hook implementation; PRV-A's federation aggregations feed FED-A's `secure_aggregate` hook; FED-A's federation-key auth uses CRY-A's key management. Integration is via dependency injection of concrete hook implementations at service-construction time, not via direct package coupling. This keeps the dependency graph one-directional and the seams clean.

### §1.3 The Track 1 / Track 2 seam pattern

Each scaffold follows the same pattern across all three layers — `_ais_hooks.py` defines a runtime-checkable Protocol, `Null<X>Hooks` provides the no-op default, and the package's Track 1 classes accept `hooks=` constructor arguments. Track 1 ships now using current JACKPOT primitives; Track 2 AIS-augmented overlays plug in later via dependency injection without forking. This is the same pattern across all three layers.

The seam is the constructor argument. Track 1 deployment uses `Null<X>Hooks`, Track 2 deployment uses the real one:

```python
from research.ais.federation_hooks import RealAISFederationHooks
client = FederationClient(hooks=RealAISFederationHooks(...))
```

When the AIS work lands, you swap in a real implementation. No code changes to `client.py` / `push.py` / `access.py`.

## §2. The three scaffolds

### §2.1 FED-A — federation primitives

**Status:** Merged 2026-05-08 on `development`.

The package surface at `backend/backend/federation/`:

| File | Role |
|---|---|
| `__init__.py` | Public API exports |
| `README.md` | Track 1/2 plan, hook→AIS-doc mapping, integration with `backend/backend/immune/` |
| `models.py` | Pydantic v2 models: `FederatedInstance`, `FederationRole` enum (hub/spoke/peer), `FederationQuery`, `FederationQueryResult`, `FederationPushPayload`, `FederationAccessRequest` |
| `client.py` | `FederationClient` for Level 1 query federation. Async fanout via `httpx`, per-partner attestation hook, anomaly-detection hook, secure-aggregate wrap on results |
| `push.py` | `FederationPushJob` for Level 2 hub push. Three-gate qualification logic concrete (surveillance_relevant, sharing_level ≥ minimum, quality_status ≥ ANALYZABLE); IO stubbed via `NotImplementedError` |
| `access.py` | `FederationAccessGateway` for Level 3 bidirectional access. Reuses existing internal `sample_access` workflow for approval |
| `_ais_hooks.py` | `AISFederationHooks` Protocol (`@runtime_checkable`) with five hooks plus `NullAISFederationHooks` no-op default |

The five `AISFederationHooks` Protocol entry points (Track 2 plug-in seams):

| Hook | AIS doc ref | Track 2 impl module |
|---|---|---|
| `secure_aggregate(results, partner_set)` | §1.6 inter-instance signaling | `backend/backend/immune/sec/cs_cyber_federated.py` |
| `attest_partner(instance)` | §1.7 attribution & deception | `backend/backend/immune/sec/` (attestation primitives) |
| `detect_anomalous_traffic(query, partner)` | §1.3 innate immunity | `backend/backend/immune/algorithms/featurizers/` + `redteam/attack_federation.py` |
| `threshold_approve(action, partner_set)` | §1.8 tolerance / regulation | `backend/backend/immune/sec/` (threshold-crypto primitives) |
| `validate_push_payload(payload, target)` | §1.8 tolerance ("don't attack self") | `backend/backend/immune/sec/refusal.py`, `parsers_safe.py` |

This is the actual architectural innovation, and it's already shipped. The earlier chat content invented "FML-1..7" items that don't exist; the real plan is Track 1 scaffold (done) + Track 2 hook implementations (deferred to IM-4 Phase).

### §2.2 PRV-A — privacy primitives

**Status:** Merged Session 21 as PR #39, on `development`.

The package surface at `backend/backend/privacy/`. Mirrors FED-A pattern. Files: `coarsening.py` (host-age generalization and similar primitives that already ship), `scrubber.py` (HRRT wrapper), `dlp.py` (GCP Cloud DLP integration), `budget.py` (DP budget tracking placeholder), `_ais_hooks.py`, `README.md`.

Six AIS hook seams covering DP, FL, HE, MPC, synthetic substitution (see §3 for the full table).

The HRRT scrubber and GCP Cloud DLP that already ship are consolidated under PRV-A's `scrubber.py` and `dlp.py`.

### §2.3 CRY-A — crypto primitives

**Status:** PENDING, active sprint candidate.

The package surface at `backend/backend/crypto/`. Same pattern as FED-A and PRV-A. Files: `keys.py` (PKCS#11 / Secret Manager / file-system keystore abstraction), `signing.py` (Sigstore/cosign artifact signing), `crypt4gh.py` (per-file encryption for ingest/egress, GA4GH standard), `_ais_hooks.py`, `README.md`.

AIS hook seams covering HE backend selection, threshold signing (FROST/BLS/DKG), TEE attestation evidence verification, key-rotation policy enforcement.

## §3. The full AIS hook surface

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

## §4. Privacy and crypto primitives — deep dives

### §4.1 Homomorphic encryption (HE)

**What it is.** Computation directly on ciphertext, producing encrypted results. JACKPOT uses RLWE-based HE (Brakerski & Vaikuntanathan 2011; Stehlé et al. 2009) for the quantum-resistance property; the reference implementation uses TenSEAL (Ayoub et al. 2021).

**Where it lives.** The `AISPrivacyHooks.he_compute(encrypted_inputs, op)` hook is the Track 1 seam in PRV-A. The Track 2 implementation lands at `backend/backend/immune/sec/he_backend.py`. The CRY-A scaffold's HE backend selection feeds into the same module — choice of single-key vs multi-key HE, choice of key sizes, choice of polynomial modulus degree.

**Concrete items.** Two tracked under Phase IM-4 (currently Tracked, Not Scheduled):

- **`B-IMMUNE-HE-1`** Single-key HE query layer at `backend/immune/net/query_he.py` (Kim 2021). First concrete query type: wastewater mass balance per Driver et al. 2024 — `(Q1·C1) − (Q2·C2)` over RLWE-encrypted operands, including the Use Case 2 temporal-equality variant. Second concrete query type: "do you have a memory cell matching this signature?" 1-2 weeks for memory-cell baseline plus 1-2 weeks for wastewater concrete.

- **`B-IMMUNE-HE-2`** Multi-key HE extension per Lopez-Alt et al. 2012. Each federation entity holds its own secret key; decryption requires participation from all key holders. Eliminates the collusion attack identified in Driver et al. 2024 §4. Same `he_backend.py` interface, different crypto backend. 2-3 weeks of significant crypto work; triggered when single-key HE proves the operational model.

**Use cases.** Federated mass-balance computation for wastewater epidemiology (the cryptWWDB application); memory-cell matching across federation peers without revealing the signature; future: federated lineage-frequency aggregation, federated AMR fingerprint similarity queries.

**Threat model.** Single-key HE leaks under Muni-A-and-Lab collusion. Multi-key HE eliminates that. The federation operations doc (`B-CWB-DOC-1`, pending) documents this assumption for operators.

### §4.2 Multi-party computation (MPC)

**What it is.** Cryptographic protocols where multiple parties jointly compute a function over their private inputs while revealing only the output. Related to but distinct from HE — HE keeps inputs encrypted during computation; MPC keeps inputs distributed across parties during computation. PSI (private set intersection) is a specialized MPC primitive answering "do you have any of these items?" without revealing the items themselves.

**Where it lives.** The `AISPrivacyHooks.mpc_protocol(parties, computation)` hook is the Track 1 seam in PRV-A. Track 2 lands at `backend/backend/immune/sec/mpc_backend.py` (new module under IM-4).

**Concrete items.** None currently tracked as MPC-specific items in todo.md. The closest is the FedTADBench-driven framework decision:

- **`B-FED-PILLARIII-1`** (Phase IM-4) Decide FL framework for Pillar III via FedTADBench benchmark (Liu et al. 2022). Compares DataSHIELD-class vs FedAdapt-CAD vs FedMI vs Conclave-style MPC platforms on representative anomaly-detection workloads. 2 weeks benchmarking + 1 week documentation.

**Use cases.** Trieu's osu-crypto work (MultipartyPSI, BaRK-OPRF, SpOT-PSI) is the natural MPC contribution path — query-time privacy for "do you have a sample matching this signature?" queries. Federated trust score computation where multiple parties contribute without revealing inputs. Federated query joins where no single party sees the full join. Conclave-style multi-party analytics for federation-wide rollups.

**Relationship to HE.** Complementary, not redundant. HE answers "compute on my encrypted data"; MPC answers "compute jointly without sharing inputs." cryptWWDB Use Case 2-time-efficient already uses MPC-style delegation — Muni A sends encrypted time to Muni B, who performs plaintext-ciphertext comparison locally rather than the lab performing ciphertext-ciphertext comparison. Both fit under PRV-A's hooks; both could plug into the same Track 2 implementation.

### §4.3 Differential privacy (DP)

**What it is.** Formal mathematical privacy guarantees via calibrated noise addition. A DP mechanism with privacy parameter ε bounds the probability that any individual's data affects the output. Practically: federation-wide aggregations get noise added; sensitivity analysis determines how much; per-requester budget tracking prevents repeated-query attacks.

**Where it lives.** Two PRV-A hooks: `dp_noise(query_result, sensitivity)` adds calibrated noise to query results; `track_dp_budget(requester, epsilon)` enforces per-requester budget limits. Track 2 implementations land in `backend/backend/immune/sec/`.

**Concrete items.** One tracked under Phase IM-4:

- **`B-IMMUNE-DP-1`** Differential-privacy aggregator for shared signals. Federation-wide aggregations (member counts, signal frequencies, lineage frequencies, AMR fingerprint distributions) computed with formal DP guarantees. Lands inside the existing `B-PRV-1` privacy-scaffold pattern. ~1 week.

Plus the related future-phase item:

- **`B-PRV-1`** (Phase P1 deferred) Privacy hardening — DP enforcement across all federation aggregation paths, FL coordinator with DP-SGD, DLP rule expansion. Reduces to concrete impl of `AISPrivacyHooks` Protocol via `backend/backend/immune/sec/` once PRV-A scaffold lands (which it has).

**Use cases.** Federation-wide aggregations protected by DP guarantees rather than just "negative list" defensive design. Per-requester budget tracking to prevent inference attacks via repeated queries. Disclosure protection for small-cell-size geospatial data — relevant for the wastewater building-level sampling concern raised in Driver et al. 2024 (the paper explicitly cites "fewer people contributing to a sample" as a privacy risk at sub-sewershed resolution).

**Tunable tradeoff.** DP buys formal privacy at the cost of utility degradation. ε too small → noisy results; ε too large → weak guarantees. Operator policy decision. `B-IMMUNE-DP-1` ships with a default ε and a policy mechanism for per-deployment override.

## §5. The phased roadmap

### §5.1 Stage 0 — Current state (on `development`)

- **FED-A scaffold** complete with all five `AISFederationHooks` defined.
- **PRV-A scaffold** complete with all six `AISPrivacyHooks` defined.
- Federation primitives operate via `NullAIS*Hooks` defaults — Track 1 functionality works without any Track 2 overlay.
- The HRRT scrubber and GCP Cloud DLP that already ship are consolidated under PRV-A's `scrubber.py` and `dlp.py`.

### §5.2 Stage 1 — Scaffold completion (~4-6 weeks)

Active sprint candidates that close out the Track 1 surface. Four follow-on FED-* items, each roughly one session:

- **FED-D — schema migration.** `federated_instances` table per the `models.py` shape (columns: `id`, `name`, `base_url`, `role`, `federation_enabled`, `min_sharing_level_for_federation`, `hub_instance_url`, `api_key_secret_name`, `last_seen_at`, `created_at`, `updated_at`). New columns on `organizations`: `min_sharing_level_for_federation`, `federation_enabled`, `hub_instance_url`, `federation_role`. Workflow: LinkML schema YAML edits first → `uv run python scripts/regen_schema.py` → Alembic autogenerate → manual cleanup. Branch: `b1-federation-schema-migration`. **+ `B-CWB-FED-1`** (`data_source_lab` value in `FederationRole` enum).

- **FED-C — tests.** `tests/federation/` test files:
    - `test_models.py` — Pydantic v2 shape and serialization round-trip
    - `test_client_l1.py` — `FederationClient` async fanout, hook invocation order, partner attestation rejection, anomaly detection rejection. Use `respx` to mock partner HTTP.
    - `test_push_l2.py` — qualification logic (port the 5 smoke-test cases from FED-A delivery), payload composition, negative-list enforcement
    - `test_access_l3.py` — outbound + inbound shapes, `NotImplementedError` raises where appropriate
    - `test_ais_hooks.py` — `NullAISFederationHooks` satisfies Protocol, all five hooks return safe defaults

  Coverage target ≥95% on every module. Branch: `b2-federation-tests`.

- **FED-B — router.** `backend/backend/routers/federation.py` exposing:
    - `GET /api/v1/federation/instances` — list registered partners (Platform Admin only)
    - `POST /api/v1/federation/instances` — register a partner (Platform Admin only)
    - `POST /api/v1/federation/search` — broadcast L1 query to enabled partners
    - `POST /api/v1/federation/push` — receive an inbound L2 payload (peer-instance only)
    - `POST /api/v1/federation/access-requests` — receive an inbound L3 access request (peer-instance only)

  Auth: federation API keys via `X-JACKPOT-Federation-Key` header for peer-to-peer endpoints (validated against `federated_instances.api_key_secret_name` via Secret Manager); standard JWT + `require_platform_admin` for admin-facing list/register. Branch: `b3-federation-router`. **+ `B-CWB-DOC-1`** (`docs/federation_operations.md` covering non-collusion assumption + multi-key HE pathway).

- **FED-E — wire router into main.py.** Register the FED-B router; add federation-key guard to `backend/backend/auth/guards.py`. Branch: `b4-federation-wiring`.

- **CRY-A scaffold** — `backend/backend/crypto/` package mirroring FED-A and PRV-A patterns. AIS hook seams for HE backend selection, threshold signing, TEE attestation, key rotation.

At end of Stage 1, all three scaffolds are complete on `development`. Track 1 federation works end-to-end with `Null<X>Hooks` defaults; Track 2 overlay sockets are all defined and ready to accept implementations.

These four FED items are listed as candidates in the active-sprint set at top of `todo.md`. Sequentially they're roughly 4 sessions of focused work.

### §5.3 Stage 2 — cryptWWDB-readiness (~4-6 weeks)

Per `cryptwwdb-integration.md` and the merged backlog additions:

- **Phase 24.5 schema items** (`B-CWB-SCHEMA-1` through `B-CWB-SCHEMA-5`): upstream-of association_type enum, target-concentration result type, time-varying population fields, fecal-normalization table, excretion/degradation factor tables.
- **P0b ships** the cryptWWDB schema items alongside the existing v5.0 migration.
- **`B-CWB-MB-1`**: Tier 1 plaintext mass-balance computation module.
- **`B-WW-1`**: wastewater lineage-abundance Streamlit dashboard.
- **`B-CWB-DOC-1` and `B-CWB-FED-1`** ship with Stage 1 federation work.

At end of Stage 2, JACKPOT is "ready to collaborate" — drop-in ready to receive the cryptWWDB HE implementation as a Track 2 overlay at `backend/backend/immune/sec/he_backend.py`.

### §5.4 Stage 3 — Full Phase IM-4 (Tracked, Not Scheduled, ~6 weeks)

The chat's "true FL with Flower + LoRA" layer corresponds to Phase IM-4 (Federation as Immune Network) in `jackpot_immune_platform_plan.md`. Goal: cross-tenant immune-network with trust scoring and encrypted queries. Two JACKPOT instances on one network share a confirmed memory cell after cross-instance confirmation, and run a homomorphic-encrypted query without raw data leaving either side.

The IM-4 buildout converts the Track 2 sockets to concrete implementations. Sequencing within IM-4:

| Item | Function | Effort |
|---|---|---|
| `B-IMMUNE-FED-SCHEMA-1` | Schema: `federation_members`, `trust_scores`, `cyber_assessments` tables. Subsumes the `[quick-win]` federation-trust schema sketch from immune-plan §14.4 QW-6. | 2-3 sessions |
| `B-IMMUNE-TRUST-1` | TrustEngine at `backend/immune/net/trust.py`. Per-member trust scores from submission quality, false-positive rate, behavioral consistency. Trust scores gate which federation operations a member can participate in. Reference: immune-plan §6.2.1, §10.5. | 4-5 sessions |
| `B-IMMUNE-REP-1` | AntibodyRepertoire publish/subscribe at `backend/immune/net/repertoire.py`. Federation members publish anonymized detector repertoire; others subscribe to synthesize a global repertoire view. Reference: immune-plan §6.3. | 3-4 sessions |
| `B-IMMUNE-MEMSYNC-1` | Federation memory cell sync at `backend/immune/net/memory_sync.py`. Memory cell promotes to global pool only after N independent member confirmations. Reference: immune-plan §6.2. | 3-4 sessions |
| `B-IMMUNE-HE-1` | Single-key HE query layer — wastewater mass balance + memory cell match. Lands inside the existing `B-CRY-1` crypto-scaffold pattern. Reference: immune-plan §6.2.2, §10.5. | 2-4 weeks |
| `B-IMMUNE-DP-1` | DP aggregator for shared signals. Lands inside the existing `B-PRV-1` privacy-scaffold pattern. | 1 week |
| `B-FED-PILLARIII-1` | FL framework decision via FedTADBench. | 3 weeks |
| `B-IMMUNE-HE-2` | Multi-key HE extension per Lopez-Alt 2012. | 2-3 weeks |
| `B-COLLAB-DIVERSITY-2` | Federation diversity index at `backend/immune/net/diversity.py` + `diversity_cli.py`. CI gate fails if diversity drops below threshold. | 2 days |
| `B-COLLAB-ATRUST-1` | Asymmetric trust at `backend/immune/net/asymmetric_trust.py`. Member A may trust B at level 3 while B trusts A at level 1. **This is the natural Trieu collaboration point.** Depends on `B-IMMUNE-TRUST-1`. | 2 days |
| `B-COLLAB-REDTEAM-3` | Adversarial test suite at `backend/immune/redteam/attack_federation.py`. Simulates malicious member submitting poisoned signals. | 3 days |

### §5.5 Phase IM-4 success criteria

Phase IM-4 success criterion: two JACKPOT instances on one network can (1) share a confirmed memory cell after cross-instance confirmation; (2) run a homomorphic-encrypted query without raw data leaving either side; (3) compute federation-wide diversity and refuse operations when diversity drops; (4) complete Outbreak case 8 in 2-player coordination mode.

### §5.6 Forward references to other phases

Federation work also intersects with phases tracked in other docs:

- **Phase 27 — CDC DMI / North Star / STLT alignment backlog** (tracked, not scheduled) contains **B-CARE-4 Federation-aware deletion propagation**. Depends on B-CARE-3 + Scenario E federation work. Estimated 1 week, Year 2. The propagation primitive lives in `backend/backend/federation/` and uses the L3 `FederationAccessGateway` infrastructure to notify peers when an upstream sample is deleted.

## §6. Sequencing and unresolved decisions

**The blocking chain.** Stage 1 (FED-B/C/D/E + CRY-A) is the active-sprint pick — it unblocks both Stage 2 and Stage 3. Stage 2 (cryptWWDB-readiness) requires P0b to ship the schema items. Stage 3 (Phase IM-4) is gated on coalition timing: pulling it forward from "Tracked, Not Scheduled" depends on Trieu/Forrest/Halden/Scarpino conversations and any follow-on grant funding.

**Decisions open for input.**

1. **MPC vs HE for cryptWWDB.** The paper uses single-key HE. JACKPOT supports both via separate hooks. Is there value in implementing MPC-based variants of the wastewater mass-balance query alongside HE, or stay HE-only for the first concrete implementation?
2. **DP default ε.** `B-IMMUNE-DP-1` needs a default ε. Literature-standard values range from 0.1 (strong) to 10 (weak). Operator policy decision; needs documentation in the federation operations doc.
3. **FL framework choice.** `B-FED-PILLARIII-1` is the methodology. DataSHIELD vs FedAdapt-CAD vs FedMI vs Conclave-style MPC. Decision depends on benchmark. (See §8 paper-review delta for the substrate-vs-overlay refinement per Riedel et al. 2024.)
4. **Multi-key HE timing.** `B-IMMUNE-HE-2` could land in parallel with `B-IMMUNE-HE-1` (stronger threat model from day one) or after (single-key proves the operational model first). Recommendation: after, unless first production deployment specifically needs the collusion mitigation.
5. **CRY-A AIS hook surface.** The CRY-A scaffold's hook signatures are TBD per the spec at `todo.md` Federation/Privacy/Crypto Scaffolds section. Refining the surface against `Jackpot_AIS.md` is part of the CRY-A landing PR.

## §7. Coalition cross-references

The roadmap maps to coalition conversations as follows:

- **Forrest (Biodesign BSS)** — the AIS framing across all five `AISFederationHooks` and six `AISPrivacyHooks`. `Jackpot_AIS.md` is the conceptual entry point.
- **Trieu (SCAI)** — PSI work feeds `AISPrivacyHooks.mpc_protocol` Track 2 implementation. `B-COLLAB-ATRUST-1` (asymmetric trust) is a natural collaboration point. Also `AISFederationHooks.secure_aggregate` (Bonawitz/secure aggregation) and `AISFederationHooks.threshold_approve` (FROST/BLS/DKG).
- **Halden (Biodesign EHE) + Driver et al.** — cryptWWDB integration via `AISPrivacyHooks.he_compute` Track 2. Sequence per `cryptwwdb-integration.md`.
- **Lee (SCAI + Biodesign)** — featurizer registry across `AISFederationHooks.detect_anomalous_traffic` and `AISPrivacyHooks.synthetic_substitute`. Maps to his TCR-Gen / catELMo attention-based embedding work. Also TEE attestation.
- **Scarpino (EPISTORM)** — federated wastewater metagenomics overlay. Maps to `B-IMMUNE-FED-PILLARIII-1` FL framework decision plus the wastewater track.
- **Pathak (STPH)** — the privacy/crypto/federation curriculum mapping to TPH557 (Ethics, Policy, Law) plus TPH552 (Systems Design).

## §8. The honest framing for grant conversations

Four genuinely open challenges, surfaced for honesty with collaborators:

1. **Heterogeneity is the elephant in the room.** Even with FedProx and personalization layers, federated learning across deeply heterogeneous surveillance sites doesn't work as well as the FL literature suggests. The `B-FED-PILLARIII-1` FedTADBench-based framework selection acknowledges this empirically rather than picking a method by reputation.
2. **Gradient inversion is a real attack.** Geiping et al. 2020 and follow-ups show gradients can leak training samples. JACKPOT's pitch needs to be honest about this. The DP layer (`B-IMMUNE-DP-1`) provides formal guarantees; the `validate_push_payload` AIS hook provides defense-in-depth at the payload level.
3. **Byzantine threats.** Malicious or compromised cells. The `B-COLLAB-REDTEAM-3` adversarial test suite makes this explicit. Defense via Krum / Trimmed Mean / Median / Bulyan / FLTrust adds complexity; threat model for JACKPOT (state public health labs with trust relationships) is friendlier than general-public FL but not zero-threat.
4. **Evaluation in federated settings.** Each cell has different held-out data. Reported global metric depends on aggregation. JACKPOT will document the methodology choice in the federation operations runbook rather than pretending there's a clean answer.

**Updates from the 9-paper review (2026-05-13).** Several additions and refinements landed against the original open-challenges framing:

- **FL framework decision rescoped.** Per Riedel et al. 2024 (Int J Machine Learning & Cybernetics), `B-FED-PILLARIII-1` is now a two-stage decision: (1) general-purpose FL substrate selection from the Riedel et al. top-3 (Flower 84.75%, FLARE 80.5%, FederatedScope 78.75%); (2) healthcare-specific overlay (DataSHIELD vs FedAdapt-CAD) for the privacy/aggregation layer.
- **Governance substrate identified.** Per Tangaro et al. 2026 (Frontiers in Genetics), the GA4GH Passports + Data Use Ontology (DUO) substrate is the emerging standard for cross-jurisdictional federated governance. New entry **`B-FED-GOV-1`** tracks Passports + DUO integration as the substrate for `AISFederationHooks.threshold_approve` Track 2.
- **Policy-checker module surfaced.** Per Driver et al. 2024, the computation coordinator enforcing access controls and repeated-query detection is a discrete component, not an implicit responsibility of the federation router. New entry **`B-CWB-POLICY-1`** tracks a `policy_checker.py` module sitting between the router and HE compute backend.
- **Non-collusion specification refined.** Per Driver et al. 2024, the cryptWWDB non-collusion model is now documented with the explicit symmetric/asymmetric distinction (symmetric between municipalities, asymmetric toward the lab as compute party). This refinement lives in `docs/federation_operations.md`.

The four open challenges from §8 (heterogeneity, gradient inversion, Byzantine threats, evaluation) remain valid as-stated. The 9-paper review didn't displace any of them — it sharpened the specific items that address them.

## §9. Demo path for laptop Scenario A

The earlier chat content's "Sol cluster federation simulation" doesn't apply for a laptop demo. The laptop-feasible federation slice:

1. **FED-D + FED-C + FED-B + FED-E** land — federation router exists on `development`, schema migrated, tests passing.
2. **Two JACKPOT instances on one laptop** via Docker Compose, each running the API + Streamlit + Postgres + MinIO stack on different ports. Each is configured as a peer of the other in `federated_instances`.
3. **L1 query federation demo** — submit a query to instance A's `/api/v1/federation/search`; the FederationClient fans out to instance B; results aggregate. The `NullAISFederationHooks` no-op default means secure aggregation, attestation, anomaly detection, threshold approval, and payload validation are all bypassed for the demo — but the seam is visible.
4. **L2 hub push demo** — instance A as hub, instance B as spoke. Submit a sample on B with sharing_level set high enough; trigger the push; watch the qualification logic and negative-list enforcement on A's receiving endpoint.
5. **L3 bidirectional access demo** — instance A requests access to a sample on B via `/api/v1/federation/access-requests`; B's existing `sample_access` workflow handles the approval.

This is a credible federation architecture demo. It demonstrates the Track 1 / Track 2 seam pattern (the architectural innovation), shows the three federation levels working end-to-end, and is laptop-feasible without GCP staging. The Track 2 AIS overlays (HE, trust, memory sync, DP) are visibly absent — that's IM-4 work — but the Protocol seams are visible and the no-op defaults satisfy them.

The demo question: "Can two JACKPOT instances on one laptop demonstrate query federation, hub push, and bidirectional access end-to-end?" Answer: yes, once FED-B/C/D/E ship.

## §10. What's net-new (not tracked)

Three items from chat content not yet in the backlog:

- **Federation analytics dashboard** showing per-cell vs federation-aggregated lineage frequencies, AMR fingerprints, etc. Not in the existing plan. Would be net-new `B-FED-ANALYTICS-*` items.
- **Federated lineage growth meta-analysis** via hierarchical Bayesian. The chat's "Layer 1 federated summary statistics" pattern. Not in existing plan; conceptually fits L1 query federation + AIS `secure_aggregate` hook but the meta-analysis component is net-new.
- **Federated AMR fingerprint anomaly detection.** Not tracked. Net-new.

Each is plug-compatible with the FED-A scaffold via the AIS hook seams. Adding them is "add tracked items + wire to existing seams" rather than "redesign federation."

## §11. Source-of-truth navigation

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
