# `backend/privacy/` — Privacy Package

**Owner:** core platform
**Status:** Track 1 in progress (consolidation of existing prod privacy primitives); Track 2 hooks scaffolded.

## The two-track plan

JACKPOT privacy primitives ship now using existing operational code (HRRT scrubber, Cloud DLP, host_age_range / location coarsening). Track 2 — AIS-augmented overlays (DP, FL, HE, MPC, synthetic substitute) — is structured TODOs and `Protocol` stubs that ship next to the working code, so when crypto/AIS collaborators land, they have a place to plug in.

| Track | What it is | Where it lives in this package | Status |
|---|---|---|---|
| **Track 1 — Build** | Working privacy primitives using current JACKPOT operational code: coarsening at output boundary, HRRT scrubber orchestration, GCP DLP scanning, DP budget ledger placeholder. | `coarsening.py`, `scrubber.py`, `dlp.py`, `budget.py` | Wraps existing prod code; no callsite migration in this PR |
| **Track 2 — Scaffold for AIS** | Extension points where AIS-flavored overlays slot in later. Defined as `Protocol`s with no-op default impls so Track 1 ships unchanged. | `_ais_hooks.py` | Hook surface defined; concrete impls deferred to collaboration |

## Track 1 — what gets built

Four modules consolidating the privacy primitives JACKPOT already operates, plus a budget anchor for Track 2. Unlike the federation package's three sequential levels, privacy primitives are independent boundary points each running at a distinct stage of the data lifecycle.

### `coarsening.py` — output-boundary generalization

Wraps the existing `host_age_range`, location, and date generalization helpers. Applied at API output boundary (search responses, federation push payloads, export artifacts). Preserves k-anonymity at the configured granularity (per-tenant policy: age bin width, location level, date bucket).

The `synthetic_substitute` hook activates when a result set falls below the configured k threshold and the tenant policy enables synthetic padding — Track 1 default returns the records unchanged; Track 2 pads with synthetic surrogates preserving distributional properties.

### `scrubber.py` — HRRT scrubber orchestration interface

Python-side orchestrator for `ingest_scrubber.nf`. Submission, state polling, the 6-state lifecycle (PENDING / IN_PROGRESS / COMPLETE / FAILED / SKIPPED / PENDING_APPROVAL), 48h skip governance, `SCRUBBER_MAX_CONCURRENT=10` concurrency control. Delegates Nextflow invocation to the existing pipeline launcher.

### `dlp.py` — GCP Cloud DLP scanner

Wraps the existing `dlp_scanner.py` — dynamic free-text field discovery, `FIELD_EXCEPTIONS` for fields where PII is expected by schema design, LIKELY threshold for findings, `DLP_ENABLED=false` bypass for local dev and laptop deployment.

### `budget.py` — DP budget ledger

Append-only ledger for differential-privacy expenditures. Track 1 records every (requester, query, epsilon) tuple but Null hooks return infinity for remaining budget — no enforcement until Track 2. Primary anchor for the `dp_noise` and `track_dp_budget` hooks.

## Track 2 — what gets scaffolded

`_ais_hooks.py` defines six extension points, each tied to a specific AIS doc section. Track 1 ships with `NullAISPrivacyHooks` — passthrough hooks (`dp_noise`, `synthetic_substitute`) return the input unchanged; `track_dp_budget` returns `float('inf')` (unlimited budget); Track-2-only hooks (`fl_aggregate`, `he_compute`, `mpc_protocol`) raise `NotImplementedError`.

| Hook | AIS doc ref | Track 2 impl imports from | Expertise needed |
|---|---|---|---|
| `dp_noise(query_result, sensitivity, epsilon)` | §1.4 adaptive immunity (memory) | `backend/immune/sec/dp_layer.py` (new) | applied cryptography + statistics (calibrated DP mechanisms, Gaussian/Laplace noise, composition theorems) |
| `track_dp_budget(requester_id, epsilon_spent)` | §1.8 tolerance / regulation | `backend/immune/sec/dp_budget.py` (new) | DP accountant theory (RDP / zCDP / advanced composition) |
| `fl_aggregate(local_updates, schema)` | §1.6 inter-instance signaling | `backend/immune/sec/cs_cyber_federated.py` (extends existing) | applied cryptography (Bonawitz-class secure aggregation) + AIS theory (clonal-selection-as-FL framing) |
| `he_compute(encrypted_inputs, op, key_ref)` | §1.4 adaptive immunity (state-bearing computation) | `backend/immune/sec/he_backend.py` (new) | applied cryptography (CKKS / BGV / TFHE selection per workload) |
| `mpc_protocol(parties, computation_spec)` | §1.6 inter-instance signaling | `backend/immune/sec/mpc_backend.py` (new) | applied cryptography (SPDZ / GMW / Yao protocol families) |
| `synthetic_substitute(real_dataset, fidelity_target)` | §1.5 diversity layer (N-variant surrogates) | `backend/immune/algorithms/featurizers/` (extends existing) | AIS theory + statistics (diversity index design, fidelity vs. privacy trade-off) |

TEE-native compute is **not** a privacy hook — TEE attestation is a crypto primitive scheduled for `backend/crypto/_ais_hooks.py` as `tee_attest_quote`. Privacy hooks call the crypto attestation hook when a TEE backend is configured.

## Mapping to existing roadmap items

| Source | Item | Lives in |
|---|---|---|
| `todo.md` Federation/Privacy/Crypto Scaffolds section | PRV-A | This package |
| `jackpot_session_summary_and_backlog.md` v3.5 | Sessions 17–22 (operator-agnostic genericization, Track 1+2 plan locked) | Two-track structure, naming conventions |
| `Jackpot_AIS.md` Part 3 Capability 1 | Native Federated Learning Plane | (Track 2) `_ais_hooks.py` `fl_aggregate` |
| `Jackpot_AIS.md` Part 3 Capability 2 | Differential Privacy Output Layer | `budget.py` (Track 1) + (Track 2) `dp_noise`, `track_dp_budget` |
| `Jackpot_AIS.md` Part 3 Capability 3 | Homomorphic Encryption for Outsourced Compute | (Track 2) `_ais_hooks.py` `he_compute` |
| `Jackpot_AIS.md` Part 3 Capability 4 | Secure Multi-Party Computation Plane | (Track 2) `_ais_hooks.py` `mpc_protocol` |
| `Jackpot_AIS.md` curriculum PP-3 / Part 3 ~L2167 | DP-synthetic data generation | (Track 2) `_ais_hooks.py` `synthetic_substitute` |
| `Jackpot_AIS.md` §1.4, §1.5, §1.6, §1.8 | adaptive / diversity / signaling / tolerance | Mapped one-to-one onto the six hooks |
| `jackpot_immune_collaboration_scaffolding.md` §3 | diversity featurizers | (Track 2) `synthetic_substitute` consumes the featurizer registry |
| `jackpot_pathoplexus_loculus_overview.md` §16 | Two PII gates differentiator (HRRT + DLP) | `scrubber.py` + `dlp.py` Track 1 wrappers |

## Relationship to `backend/immune/`

This package is **Track 1** — privacy primitives that ship now using existing operational code (HRRT scrubber pipeline, Cloud DLP, k-anonymity coarsening helpers). `backend/immune/` is **Track 2** — the AIS-augmented overlays scheduled per the immune-collaboration scaffolding plan.

The seam between the two tracks is the `AISPrivacyHooks` Protocol defined in `_ais_hooks.py`. Track 1 ships with `NullAISPrivacyHooks`. Track 2 work delivers concrete hook implementations in `backend/immune/sec/privacy_hooks.py` that import from sibling immune-scaffold modules.

The Track 2 hook implementation at `backend/immune/sec/privacy_hooks.py` imports from:

- `backend/immune/sec/dp_layer.py` — DP noise mechanisms
- `backend/immune/sec/dp_budget.py` — RDP/zCDP budget accountant
- `backend/immune/sec/cs_cyber_federated.py` — secure aggregation for FL (extends existing)
- `backend/immune/sec/he_backend.py` — homomorphic encryption backend
- `backend/immune/sec/mpc_backend.py` — multi-party computation backend
- `backend/immune/algorithms/featurizers/` — synthetic-substitute generators (extends existing)

When the immune scaffold modules land, the dependency-injection seam is wired in via constructor: each Track 1 class accepts `hooks=` defaulting to `NullAISPrivacyHooks`. **No changes required to `coarsening.py` / `scrubber.py` / `dlp.py` / `budget.py`.** Direction of dependency is one-way: `backend/privacy/` never imports from `backend/immune/`; `backend/immune/sec/privacy_hooks.py` imports the Protocol from `backend/privacy/_ais_hooks.py`.

## How to extend

When the AIS layer is ready (concrete implementations of the hook Protocol in `backend/immune/sec/privacy_hooks.py`), wire it in via the constructor:

```python
from backend.privacy import DPBudgetLedger
from backend.immune.sec.privacy_hooks import RealAISPrivacyHooks  # Track 2

# Track 1 deployment (default):
ledger = DPBudgetLedger()  # uses NullAISPrivacyHooks, no enforcement

# Track 2 deployment:
ledger = DPBudgetLedger(hooks=RealAISPrivacyHooks(...))  # AIS-augmented
```

No changes to the Track 1 modules. The hooks are the seam.

## Tests

`tests/privacy/` mirrors this layout:

- `test_coarsening.py` — wrap-and-delegate, k-threshold synthetic-substitute hook invocation, default policy, age/location/date helpers
- `test_scrubber.py` — 6-state lifecycle transitions, 48h skip TTL, concurrency cap, `expire_stale_skip_requests` reaper
- `test_dlp.py` — wrap-and-delegate, `DLP_ENABLED=false` bypass, `FIELD_EXCEPTIONS` handling, runtime field-exception registration
- `test_budget.py` — ledger append, per-requester filtering, hook invocation order (`dp_noise` then `track_dp_budget` then append)
- `test_ais_hooks.py` — `NullAISPrivacyHooks` satisfies the `AISPrivacyHooks` Protocol, raise/passthrough/identity behaviors

`NullAISPrivacyHooks` is the test fixture for everything in Track 1.
