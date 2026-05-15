# Federation design

The chat's federation design is reconciled against the actual `backend/backend/federation/` Track 1 scaffold (FED-A, merged 2026-05-08) and the future Phase IM-4 (Federation as Immune Network, Tracked Not Scheduled).

## What's already landed

The federation foundation exists. FED-A scaffold merged 2026-05-08. Architecturally it implements the Track 1 / Track 2 seam pattern from `Jackpot_AIS.md` and `jackpot_immune_collaboration_scaffolding.md` §3.2 — Track 1 ships now using current JACKPOT primitives; Track 2 AIS-augmented overlays plug in later via dependency injection without forking.

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

Three federation levels with distinct primitives:

- **L1 (Query federation)** — `FederationClient` fanouts queries to enabled partners, aggregates results. The chat's "federated summary statistics" pattern fits here.
- **L2 (Hub push)** — `FederationPushJob` qualifies samples for push, composes payload enforcing the negative list (no `host_age`, no FASTQ, no PII), pushes to designated hub. Negative-list enforcement via never-reading-those-fields, not via filtering — defensive design.
- **L3 (Bidirectional access)** — `FederationAccessGateway` for peer-to-peer sample access requests, reusing the existing internal `sample_access` workflow.

The five `AISFederationHooks` Protocol entry points (Track 2 plug-in seams):

| Hook | AIS doc ref | Track 2 impl module |
|---|---|---|
| `secure_aggregate(results, partner_set)` | §1.6 inter-instance signaling | `backend/backend/immune/sec/cs_cyber_federated.py` |
| `attest_partner(instance)` | §1.7 attribution & deception | `backend/backend/immune/sec/` (attestation primitives) |
| `detect_anomalous_traffic(query, partner)` | §1.3 innate immunity | `backend/backend/immune/algorithms/featurizers/` + `redteam/attack_federation.py` |
| `threshold_approve(action, partner_set)` | §1.8 tolerance / regulation | `backend/backend/immune/sec/` (threshold-crypto primitives) |
| `validate_push_payload(payload, target)` | §1.8 tolerance ("don't attack self") | `backend/backend/immune/sec/refusal.py`, `parsers_safe.py` |

This is the actual architectural innovation, and it's already shipped. My chat content invented "FML-1..7" items that don't exist; the real plan is Track 1 scaffold (done) + Track 2 hook implementations (deferred to IM-4 Phase).

## What's pending — active sprint candidates

Four follow-on FED-* items, each roughly one session, that close out the L1/L2/L3 federation Track 1 path:

- **FED-D (Schema migration, PENDING)** — `federated_instances` table per the `models.py` shape (columns: `id`, `name`, `base_url`, `role`, `federation_enabled`, `min_sharing_level_for_federation`, `hub_instance_url`, `api_key_secret_name`, `last_seen_at`, `created_at`, `updated_at`). New columns on `organizations`. Branch: `b1-federation-schema-migration`.
- **FED-C (Tests, PENDING)** — `tests/federation/` test files. `test_models.py`, `test_client_l1.py` (use `respx` to mock partner HTTP), `test_push_l2.py` (port the 5 smoke-test cases from FED-A delivery), `test_access_l3.py`, `test_ais_hooks.py`. Coverage target ≥95% on every module. Branch: `b2-federation-tests`.
- **FED-B (Router, PENDING)** — `backend/backend/routers/federation.py` exposing:
  - `GET /api/v1/federation/instances` — list registered partners (Platform Admin only)
  - `POST /api/v1/federation/instances` — register a partner (Platform Admin only)
  - `POST /api/v1/federation/search` — broadcast L1 query to enabled partners
  - `POST /api/v1/federation/push` — receive an inbound L2 payload (peer-instance only)
  - `POST /api/v1/federation/access-requests` — receive an inbound L3 access request (peer-instance only)
  - Auth: federation API keys via `X-JACKPOT-Federation-Key` header for peer-to-peer endpoints; standard JWT + `require_platform_admin` for admin-facing list/register. Branch: `b3-federation-router`.
- **FED-E (Wire router into main.py, PENDING)** — Register the FED-B router; add federation-key guard to `backend/backend/auth/guards.py`. Branch: `b4-federation-wiring`.

These four are listed as candidates in the active-sprint set at top of `todo.md`. Sequentially they're roughly 4 sessions of focused work.

## Phase IM-4 — full federation (Tracked Not Scheduled)

The chat's "true FL with Flower + LoRA" layer corresponds to Phase IM-4 (Federation as Immune Network) in `jackpot_immune_platform_plan.md`. Goal: cross-tenant immune-network with trust scoring and encrypted queries. Two JACKPOT instances on one network share a confirmed memory cell after cross-instance confirmation, and run a homomorphic-encrypted query without raw data leaving either side.

Phase IM-4.A items (~4 weeks):

- **`B-IMMUNE-FED-SCHEMA-1`** Federation tables — `federation_members`, `trust_scores`, `cyber_assessments`. Subsumes the `[quick-win]` federation-trust schema sketch from immune-plan §14.4 QW-6. 2-3 sessions.
- **`B-IMMUNE-TRUST-1`** TrustEngine at `backend/immune/net/trust.py`. Computes trust scores per federation member based on submission quality, false-positive rate, behavioral consistency. Trust scores gate which federation operations a member can participate in. Reference: immune-plan §6.2.1, §10.5. 4-5 sessions.
- **`B-IMMUNE-REP-1`** AntibodyRepertoire publish/subscribe at `backend/immune/net/repertoire.py`. Federation members publish anonymized detector repertoire; others subscribe to synthesize a global repertoire view. Reference: immune-plan §6.3. 3-4 sessions.
- **`B-IMMUNE-MEMSYNC-1`** Federation memory cell synchronization at `backend/immune/net/memory_sync.py`. Memory cell promotes to global pool only after N independent member confirmations. Reference: immune-plan §6.2. 3-4 sessions.
- **`B-IMMUNE-HE-1`** Homomorphic-encryption query layer at `backend/immune/net/query_he.py` (Kim 2021). One well-defined query type to start ("do you have a memory cell matching this signature?"); expand later. Lands inside the existing `B-CRY-1` crypto-scaffold pattern. Reference: immune-plan §6.2.2, §10.5. 1-2 weeks; significant work.
- **`B-IMMUNE-DP-1`** Differential-privacy aggregator for shared signals. Lands inside the existing `B-PRV-1` privacy-scaffold pattern (PRV-A scaffold merged this session — see PR #39). Federation-wide aggregations computed with formal DP guarantees. 1 week.
- **`B-FED-PILLARIII-1`** Decide FL framework for Pillar III. Use FedTADBench (Liu et al. 2022) to benchmark DataSHIELD-class vs FedAdapt-CAD vs FedMI on representative anomaly-detection workloads. 2 weeks benchmarking + 1 week documentation.

Collaboration scaffolding (Phase IM-4-collab):

- **`B-COLLAB-DIVERSITY-2`** Federation diversity index at `backend/immune/net/diversity.py` + `diversity_cli.py`. CI gate fails if diversity drops below threshold. 2 days.
- **`B-COLLAB-ATRUST-1`** Asymmetric trust at `backend/immune/net/asymmetric_trust.py`. Member A may trust B at level 3 while B trusts A at level 1. **This is the natural Trieu collaboration point.** 2 days; depends on `B-IMMUNE-TRUST-1`.
- **`B-COLLAB-REDTEAM-3`** Adversarial test suite at `backend/immune/redteam/attack_federation.py`. Simulates malicious member submitting poisoned signals. 3 days.

## The honest framing for grant conversations

Four genuinely open challenges, surfaced for honesty with collaborators:

1. **Heterogeneity is the elephant in the room.** Even with FedProx and personalization layers, federated learning across deeply heterogeneous surveillance sites doesn't work as well as the FL literature suggests. The `B-FED-PILLARIII-1` FedTADBench-based framework selection acknowledges this empirically rather than picking a method by reputation.
2. **Gradient inversion is a real attack.** Geiping et al. 2020 and follow-ups show gradients can leak training samples. JACKPOT's pitch needs to be honest about this. The DP layer (`B-IMMUNE-DP-1`) provides formal guarantees; the `validate_push_payload` AIS hook provides defense-in-depth at the payload level.
3. **Byzantine threats.** Malicious or compromised cells. The `B-COLLAB-REDTEAM-3` adversarial test suite makes this explicit. Defense via Krum / Trimmed Mean / Median / Bulyan / FLTrust adds complexity; threat model for JACKPOT (state public health labs with trust relationships) is friendlier than general-public FL but not zero-threat.
4. **Evaluation in federated settings.** Each cell has different held-out data. Reported global metric depends on aggregation. JACKPOT will document the methodology choice in the federation operations runbook rather than pretending there's a clean answer.

## Demo path for laptop Scenario A

The chat's "Sol cluster federation simulation" doesn't apply for a laptop demo. The laptop-feasible federation slice:

1. **FED-D + FED-C + FED-B + FED-E** land — federation router exists on `development`, schema migrated, tests passing.
2. **Two JACKPOT instances on one laptop** via Docker Compose, each running the API + Streamlit + Postgres + MinIO stack on different ports. Each is configured as a peer of the other in `federated_instances`.
3. **L1 query federation demo** — submit a query to instance A's `/api/v1/federation/search`; the FederationClient fans out to instance B; results aggregate. The `NullAISFederationHooks` no-op default means secure aggregation, attestation, anomaly detection, threshold approval, and payload validation are all bypassed for the demo — but the seam is visible.
4. **L2 hub push demo** — instance A as hub, instance B as spoke. Submit a sample on B with sharing_level set high enough; trigger the push; watch the qualification logic and negative-list enforcement on A's receiving endpoint.
5. **L3 bidirectional access demo** — instance A requests access to a sample on B via `/api/v1/federation/access-requests`; B's existing `sample_access` workflow handles the approval.

This is a credible federation architecture demo. It demonstrates the Track 1 / Track 2 seam pattern (the architectural innovation), shows the three federation levels working end-to-end, and is laptop-feasible without GCP staging. The Track 2 AIS overlays (HE, trust, memory sync, DP) are visibly absent — that's IM-4 work — but the Protocol seams are visible and the no-op defaults satisfy them.

The demo question: "Can two JACKPOT instances on one laptop demonstrate query federation, hub push, and bidirectional access end-to-end?" Answer: yes, once FED-B/C/D/E ship.

## What's net-new from the chat that isn't tracked

- **Federation analytics dashboard** showing per-cell vs federation-aggregated lineage frequencies, AMR fingerprints, etc. Not in the existing plan. Would be net-new `B-FED-ANALYTICS-*` items.
- **Federated lineage growth meta-analysis** via hierarchical Bayesian. The chat's "Layer 1 federated summary statistics" pattern. Not in existing plan; conceptually fits L1 query federation + AIS `secure_aggregate` hook but the meta-analysis component is net-new.
- **Federated AMR fingerprint anomaly detection.** Not tracked. Net-new.

Each is plug-compatible with the FED-A scaffold via the AIS hook seams. Adding them is "add tracked items + wire to existing seams" rather than "redesign federation."
