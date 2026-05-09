# `backend/federation/` — Federation Package

**Owner:** core platform
**Status:** Track 1 in progress (Level 1 — Month 2-3); Track 2 hooks scaffolded.

## The two-track plan

JACKPOT federation gets built **and** scaffolded for AIS-flavored augmentation in parallel. The same package houses both. No separate "research" branch, no "v2 someday" hand-wave — Track 2 is structured TODOs and protocol stubs that ship next to the working code, so when collaborators land, they have a place to plug in.

| Track | What it is | Where it lives in this package | Status |
|---|---|---|---|
| **Track 1 — Build** | Working federation across L1 / L2 / L3 using current JACKPOT primitives (JWT, presigned URLs, `can_access_sample()`). | `client.py`, `push.py`, `access.py`, `models.py` | L1 in progress; L2/L3 stubs structured but not wired |
| **Track 2 — Scaffold for AIS** | Extension points where AIS-flavored augmentation slots in later. Defined as `Protocol`s with no-op default impls so Track 1 ships unchanged. | `_ais_hooks.py` | Hook surface defined; concrete impls deferred to collaboration |

## Track 1 — what gets built

Three levels, in order of `jackpot_architecture.md` §22:

### Level 1 — Query federation (Month 2-3)

`FederationClient.query()` takes a search filter, fans it out to every `federated_instances` row with `federation_enabled=True`, calls each partner's `GET /api/v1/samples/` with the federation API key, returns a unified `FederationQueryResult` that is DISCOVERABLE-equivalent (organism, date, country/state, source_type, quality_tier — no clinical metadata, no file URLs). Results cached 30 minutes.

### Level 2 — De-identified hub push (Year 2 early)

`FederationPushJob` runs nightly. Identifies samples where `surveillance_relevant=True`, `sharing_level >= min_sharing_level_for_federation`, `quality_status >= ANALYZABLE`. Builds a `FederationPushPayload` (FASTA presigned URL 24h + typing + AMR + lineage + organism + date + country/state + sector + quality_tier). POSTs to the hub. Hub creates records with `external_source=spoke_url`, `ingest_method=federation`. Raw FASTQ and PII never leave the spoke.

### Level 3 — Bidirectional sharing (Year 2 late)

`FederationAccessGateway` handles cross-instance access requests. Researcher at Org B finds a sample at Org A via Level 1 search, requests access via the existing `sample_access` workflow. Org A Lab Director approves through the same UI as internal requests. On approval: presigned URLs issued, Org B's JACKPOT pulls files via background copy job, scrubber runs on import, sample retains `external_source` + `originating_lab` attribution.

## Track 2 — what gets scaffolded

`_ais_hooks.py` defines five extension points, each tied to a specific AIS doc section. Track 1 ships with `NullAISFederationHooks` — every method returns "no-op safe default." Track 2 work replaces this with concrete implementations that live in `backend/immune/net/federation_hooks.py` and import from sibling immune-platform modules.

| Hook | AIS doc ref | Track 2 impl imports from | Expertise needed |
|---|---|---|---|
| `secure_aggregate(results)` | §1.6 inter-instance signaling | `backend/immune/sec/cs_cyber_federated.py` | applied cryptography (secure-aggregation protocols, DP budget composition) |
| `attest_partner(instance)` | §1.7 attribution & deception | `backend/immune/sec/` (attestation primitives — new) | TEE / remote attestation, trusted-hardware deployments |
| `detect_anomalous_traffic(query, partner)` | §1.3 innate immunity | `backend/immune/algorithms/featurizers/`, `backend/immune/redteam/attack_federation.py` | AIS theory + adversarial ML (diversity-based detection, attack-pattern recognition) |
| `threshold_approve(action, partner_set)` | §1.8 tolerance / regulation | `backend/immune/sec/` (threshold-crypto primitives — new) | applied cryptography (FROST / BLS / DKG) |
| `validate_push_payload(payload, target)` | §1.8 tolerance ("don't attack self") | `backend/immune/sec/refusal.py`, `backend/immune/sec/parsers_safe.py` | platform-internal — payload-anomaly heuristics |

## Mapping to existing roadmap items

| Source | Item | Lives in |
|---|---|---|
| `todo.md` | B-FED-1 (federation) | All three Track 1 levels |
| `jackpot_session_summary_and_backlog.md` | Q5 (federation architecture) | `models.py` `FederatedInstance` shape |
| `jackpot_immune_collaboration_scaffolding.md` §3.2 | diversity featurizers | (Track 2) `_ais_hooks.py` `detect_anomalous_traffic` consumes these |
| `jackpot_immune_collaboration_scaffolding.md` §5.2 | combinatorial-search FL | (Track 2) `_ais_hooks.py` `secure_aggregate` consumes this |
| `jackpot_immune_collaboration_scaffolding.md` §6.2 | refusal + asymmetric trust | (Track 2) `_ais_hooks.py` `validate_push_payload` consumes these |
| `jackpot_immune_collaboration_scaffolding.md` §8.2 | redteam adversarial tests | Tests Track 1 federation under attack scenarios |
| Federal-grade security doc | Capability 6 (threshold crypto) | (Track 2) `_ais_hooks.py` `threshold_approve` |
| `Jackpot_AIS.md` §1.3, §1.6, §1.7, §1.8 | innate / signaling / attribution / tolerance | Mapped one-to-one onto the five hooks |

## Relationship to `backend/immune/`

This package is **Track 1** — federation that ships now using current JACKPOT primitives (JWT, presigned URLs, the existing `can_access_sample()` permission model). `backend/immune/` is **Track 2** — the AIS-augmented overlays scheduled per the immune-collaboration scaffolding plan.

The seam between the two tracks is the `AISFederationHooks` Protocol defined in `_ais_hooks.py`. Track 1 ships with `NullAISFederationHooks` (no-op default). Track 2 work delivers concrete hook implementations in `backend/immune/net/federation_hooks.py` that import from sibling immune-scaffold modules:

```
Track 2 hook impl                          Imports from
─────────────────────────────────────────  ─────────────────────────────────────────
backend/immune/net/federation_hooks.py     backend/immune/sec/cs_cyber_federated.py
                                           backend/immune/sec/refusal.py
                                           backend/immune/sec/parsers_safe.py
                                           backend/immune/algorithms/featurizers/
                                           backend/immune/redteam/attack_federation.py
```

When the immune scaffold modules are in place, the federation router (later deliverable) wires the right hook implementation in via dependency injection. **No changes required to `client.py` / `push.py` / `access.py`.** Direction of dependency is one-way: `backend/federation/` never imports from `backend/immune/`; `backend/immune/net/federation_hooks.py` imports the Protocol from `backend/federation/_ais_hooks.py`.

## How to extend

When the AIS layer is ready (concrete implementations of the hook Protocol in `backend/immune/net/federation_hooks.py`), wire it in via the constructor:

```python
from backend.federation import FederationClient
from backend.immune.net.federation_hooks import RealAISFederationHooks  # Track 2

# Track 1 deployment (default):
client = FederationClient()  # uses NullAISFederationHooks, ships now

# Track 2 deployment:
client = FederationClient(hooks=RealAISFederationHooks(...))  # AIS-augmented
```

No changes to `client.py` / `push.py` / `access.py`. The hooks are the seam.

## Tests

`tests/federation/` mirrors this layout:
- `test_models.py` — shape and serialization
- `test_client_l1.py` — fanout, cache, error handling, hook invocation order
- `test_push_l2.py` — payload composition, identification of qualifying samples
- `test_access_l3.py` — cross-instance approval flow
- `test_ais_hooks.py` — null impl is no-op, hook protocol shape

`NullAISFederationHooks` is the test fixture for everything in Track 1.
