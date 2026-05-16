# cryptWWDB Integration

Architectural mapping of the cryptWWDB encrypted wastewater-based-epidemiology framework (Driver et al. 2024, *Sci Total Environ* 940:173315, NSF CICI award 2115075) onto JACKPOT's integration surface as of `development` HEAD (2026-05-16).

This document is the source-of-truth for how the cryptWWDB framework maps onto JACKPOT's architecture and what is required — schema, federation, plaintext computation, crypto scaffold, and homomorphic-encryption (HE) backend — for JACKPOT to be a credible production substrate for the framework. It tracks integration-readiness state at `development` HEAD and is updated as backlog items ship.

---

## Overview

cryptWWDB (Driver, Ahsan, Piske, Lee, Forrest, Halden, Trieu — *Sci Total Environ* 2024, 940:173315, NSF award **2115075**) is a privacy-preserving wastewater-based-epidemiology (WBE) framework that computes the standard mass-balance equation over data the participating municipalities never share in the clear. It belongs to the broader category of homomorphic-encryption applications to public-health surveillance: federated genomic and wastewater data sharing under regulatory and political constraints that block plaintext exchange. JACKPOT (Midnight-Oil-Innovation/jackpot, AGPL-3.0) is the target integration platform — a multi-deployment-target pathogen-genomics stack whose AIS-hook design (`docs/Jackpot_AIS.md`) and Track 1 / Track 2 seam pattern (`docs/jackpot_immune_collaboration_scaffolding.md`) pre-allocate the integration surface that cryptWWDB needs.

The integration is not a port of the cryptWWDB reference implementation. JACKPOT ships a plaintext reference computation (`backend/backend/wastewater/mass_balance.py`) that the encrypted variant remains bit-for-bit faithful to, an `AISCryptoHooks` Protocol (`backend/backend/crypto/_ais_hooks.py`) that the HE backend plugs into without forking the wastewater pipeline, and a `FederationRole.DATA_SOURCE_LAB` enum value (`backend/backend/federation/models.py`) that models the third-party Lab as a distinct peer type. The implementation work is partitioned across the cryptwwdb_track backlog items in `todo.md`; this document is what those items collectively converge on.

**Citation.** Driver, E. M., Ahsan, M., Piske, M., Lee, J., Forrest, S., Halden, R. U., & Trieu, C. (2024). Encrypted data-sharing for preserving privacy in wastewater-based epidemiology. *Science of the Total Environment*, **940**, 173315. <https://doi.org/10.1016/j.scitotenv.2024.173315>. Funded by NSF CICI award **2115075**.

**Audience.** Collaborators on the cryptWWDB integration thread (primarily R. U. Halden and the Driver / Trieu paper authors); operators deploying the cryptWWDB-track on Scenario E (federation member) or Scenario C (multi-lab agency) JACKPOT instances; and future JACKPOT maintainers who need to understand why the AIS-hook seam is pre-allocated for HE and what shape the cryptWWDB framework expects on the other side of it.

---

## cryptWWDB framework summary

cryptWWDB is a **target-agnostic** privacy-preserving framework: the paper exercises it against heroin and 6-acetylmorphine, but the same math runs for SARS-CoV-2, mpox, opioids, fecal indicator chemicals, or any other quantitative wastewater target. The framework's value is not the math (which is the standard wastewater mass-balance equation) but the **cryptographic protocol around the math** that lets two municipalities and a third-party lab compute the result without any party seeing the others' operands.

### Goals

cryptWWDB defines two concrete use cases:

- **Use Case 1 — segment mass-load.** For two sampling points in a shared sewershed (one upstream, one downstream), compute the per-sample mass-load contribution of the segment between them: `MassLoad = (Q_down · C_down) − (Q_up · C_up)`, where `Q_*` are volumetric flow rates and `C_*` are pathogen or chemical concentrations. The protocol evaluates the equation over RLWE-encrypted operands so neither municipality observes the other's flow or concentration, and the lab performing the computation observes neither.
- **Use Case 2 — time-aware variant.** The per-sample mass load is computed at two timestamps and the difference is reported, exposing temporal change in the segment's contribution without revealing the individual values at either timestamp. Same math, applied twice and then subtracted under encryption.

### Key cryptographic mechanisms

- **Ring-LWE-based homomorphic encryption (RLWE-HE).** The protocol is built on the CKKS scheme (Cheon-Kim-Kim-Song) — an approximate-arithmetic HE scheme well-suited to fixed-point quantities like volumetric flow (gallons/day) and concentration (ng/L or copies/mL). CKKS supports addition and multiplication of ciphertexts, which is the only algebra the mass-balance equation requires.
- **TenSEAL / Microsoft SEAL backend.** Driver et al. 2024 use TenSEAL (OpenMined's Python wrapper over Microsoft SEAL) for the reference implementation. TenSEAL is Apache-2.0; Microsoft SEAL is MIT. Both are license-compatible with JACKPOT's AGPL-3.0 consumer position.
- **Single-key construction.** One keypair encrypts all operands. Decryption is performed once by the key-holding municipality after the result ciphertext is returned. The simplicity is deliberate: it minimises operational complexity and avoids multi-party-decryption protocols at the cost of a stronger non-collusion assumption (see Threat model notes).
- **Differential privacy is NOT part of the framework as published.** Driver et al. 2024 do not inject DP noise; the privacy argument rests entirely on the HE construction and the non-collusion assumption. DP noise injection sits on JACKPOT's `AISPrivacyHooks.dp_noise` seam as a separate, layered defence that an operator can opt into independently of the cryptWWDB protocol.

### Three-party data model

The protocol operates on **site-level flow-weighted concentration signals**. Each data-producing party holds a pair `(Q, C)` per sample timepoint per sampling site:

| Role | What the party holds | What the party learns |
|---|---|---|
| **Muni A** (upstream) | `(Q_up, C_up)` per sample timepoint | Only the final mass-load result, and only if authorised to receive it |
| **Muni B** (downstream) | `(Q_down, C_down)` per sample timepoint | Same as Muni A |
| **Lab** (compute) | Ciphertexts and the HE evaluation key | Nothing about the operands; produces the result ciphertext only |

The Lab is computationally privileged but data-blind. The municipalities are data-rich but learn nothing about each other's measurements. None of the three parties holds enough state alone to recover any private input. This three-party split is the security-bearing structural choice of the framework — it is encoded in the JACKPOT federation registry as the distinct `DATA_SOURCE_LAB` role (`B-CWB-FED-1`, shipped 2026-05-12, commit `dbf34b0`).

---

## JACKPOT integration surface

cryptWWDB touches JACKPOT through a small, well-defined set of files. The integration is deliberately seam-based: cryptWWDB's HE backend is a Track 2 implementation of the `AISCryptoHooks` Protocol; the wastewater pipeline does not import from `backend/backend/immune/` and remains usable in plaintext mode regardless of whether the HE backend is wired in.

### `backend/backend/crypto/_ais_hooks.py`

The **primary cryptographic extension point**. Currently 232 lines; defines:

- `HEOperation` (StrEnum) — operations the HE backend supports. Already includes `MASS_BALANCE` (cryptWWDB Use Case 1) and `TIME_AWARE_MASS_BALANCE` (Use Case 2) values:

  ```python
  class HEOperation(StrEnum):
      ADDITION = "addition"
      MULTIPLICATION = "multiplication"
      MASS_BALANCE = "mass_balance"                          # cryptWWDB Use Case 1
      TIME_AWARE_MASS_BALANCE = "time_aware_mass_balance"    # cryptWWDB Use Case 2
      MEMORY_CELL_MATCH = "memory_cell_match"
  ```

- `AISCryptoHooks` (Protocol, `runtime_checkable`) — four hooks: `select_he_backend`, `threshold_sign`, `verify_tee_attestation`, `enforce_key_rotation_policy`. The first is the cryptWWDB integration's entry point; the other three support operator-side governance.
- `NullAISCryptoHooks` — Track 1 default. `select_he_backend` returns a single-key TenSEAL CKKS spec; `threshold_sign` raises `NotImplementedError`; `verify_tee_attestation` returns `verified=False`; `enforce_key_rotation_policy` returns `RotationAction.ALLOW`. The single-key TenSEAL CKKS default exactly matches the Driver et al. 2024 framework's expected backend.

Role in the integration: the cryptWWDB HE backend lands at `backend/backend/immune/sec/he_backend.py` as a concrete `AISCryptoHooks` implementation, swapped in via constructor dependency injection. The Protocol surface is stable; the Track 2 implementation does not require modifying `_ais_hooks.py`.

### `backend/backend/wastewater/mass_balance.py`

The **input data surface and plaintext reference computation**. Currently 426 lines, 100% module coverage across 48 tests (`tests/wastewater/test_mass_balance.py`), shipped 2026-05-10 in PR #50 (commit `d78b240`). Defines:

- `MassBalanceInputs` / `MassBalanceResult` dataclasses (frozen) — the function-level interface that both the plaintext computation and the eventual HE backend operate against.
- `FlowUnit`, `ConcentrationUnit`, `QualityFlag` (StrEnum) — units for flow rate (MGD, m³/day, L/day, L/s), concentration (ng/L, μg/L, mg/L, copies/mL, copies/L), and per-sample quality flagging.
- `compute_mass_load(inputs)` — Use Case 1 implementation. Returns `MassBalanceResult` with the segment mass-load and a tuple of `QualityFlag` values.
- `compute_time_aware_mass_load(inputs_t1, inputs_t2)` — Use Case 2 implementation, applied as the difference of two Use Case 1 results.
- Unit converters: `to_l_per_day`, `to_ng_per_l`, `to_copies_per_l`.
- Non-detect handling per Hornung & Reed 1990 (LOD/2 substitution).
- Negative-mass-balance handling per Bowes et al. 2023b / Tempe 2023a (`negative_handling="zero" | "mdl" | "raw"`).
- `load_inputs_from_db(...)` — currently `NotImplementedError` stub. The DB wiring is gated on `B-CWB-SCHEMA-1` (`wastewater_upstream_of` / `wastewater_downstream_of` association types) and `B-CWB-SCHEMA-2` (`wastewater_target_concentration` typed result row), both shipping with P0b.

Role in the integration: this is the **bit-for-bit reference** that the Track 2 HE backend's `MASS_BALANCE` and `TIME_AWARE_MASS_BALANCE` operations must agree with under plaintext probing. The shape of `MassBalanceInputs` is what gets encrypted on the way in, and the shape of `MassBalanceResult` is what gets returned as a result ciphertext.

### `backend/backend/federation/models.py`

The **federation topology surface**. Currently 196 lines. Defines the Pydantic v2 models used by the federation router, push job, and federation client. The cryptWWDB integration depends on two specifics:

- `FederationRole` enum (lines 22–41) — includes `DATA_SOURCE_LAB = "data_source_lab"` value (`B-CWB-FED-1`, shipped 2026-05-12, commit `dbf34b0`, PR #55). The docstring captures the cryptWWDB three-party model semantics: the Lab produces `pipeline_results` (concentration data) via `X-Pipeline-Token` auth but holds no `samples` of its own. `FederationClient` queryable predicates can filter data-holding peers from pipeline-producing labs by this role value.
- `FederatedInstance` — registry row per partner. `role: FederationRole` distinguishes Muni A / Muni B (`peer`) from the cryptWWDB Lab (`data_source_lab`). `api_key_secret_name` points at a Secret Manager entry — keys themselves are never stored in the DB.

Role in the integration: the cryptWWDB HE backend takes a `tuple[FederatedInstance, ...]` of parties to `select_he_backend`. The Lab is selected from this tuple by its `DATA_SOURCE_LAB` role; the data-producing municipalities are selected by `PEER` role. The role split is what lets `FederationClient` enforce the symmetric-non-collusion gates required by `docs/federation_operations.md` §2.

### `docs/federation_operations.md`

The **operational context**. 360 lines. Defines the three-party non-collusion assumption (§2), the multi-key HE pathway as future mitigation (§3), federation-key rotation policy (§4), partner attestation flow (§5), AIS-hook policy injection points (§7). Shipped 2026-05-08 as `B-CWB-DOC-1` (PR #49, commit `1eab572`). The cryptWWDB integration's policy assumptions and operator-side governance discipline live there; this document defers all policy specifics to it rather than restating them.

### Adjacent files (referenced, not currently modified by cryptWWDB)

- `backend/backend/crypto/keys.py` — `FilesystemKeystore`, `Pkcs11Keystore` (stubbed), `SecretManagerKeystore` (stubbed). Holds the HE keypair on the key-holding municipality's instance.
- `backend/backend/crypto/signing.py` — `Ed25519Signer`. Signs the result ciphertext on return from the Lab so the receiving municipality can attest provenance.
- `backend/backend/immune/sec/he_backend.py` — **reserved path** for the Track 2 HE backend (`B-IMMUNE-HE-1`). Does not exist on disk yet; landing it is out of scope for this document but is the file the integration surface delivers a contract to.

---

## Backlog capability mapping

The six concrete cryptWWDB capabilities map to JACKPOT touch-points and existing backlog items as follows. "Integration status" is one of `complete`, `partial`, `scaffold only`, `not started`. "Effort (sessions)" is calibrated against the maintainer's typical session size — one focused half-day each.

| Backlog ID | cryptWWDB capability | JACKPOT touch-point | Integration status | Effort (sessions) | Notes |
|---|---|---|---|---|---|
| B-CWB-MB-1 | Plaintext segment / time-aware mass-load reference computation (Use Cases 1 and 2) | `backend/backend/wastewater/mass_balance.py` — `compute_mass_load`, `compute_time_aware_mass_load`, `MassBalanceInputs`, `MassBalanceResult` | partial | 2 | Interface-only shipped (PR #50, `d78b240`). `load_inputs_from_db` stays `NotImplementedError` until `B-CWB-SCHEMA-1` and `B-CWB-SCHEMA-2` land in P0b. |
| B-IMMUNE-HE-1 | Single-key RLWE-HE evaluation of Use Cases 1 and 2 (TenSEAL / CKKS, encrypted site aggregation) | `backend/backend/immune/sec/he_backend.py` (reserved) — concrete `AISCryptoHooks` impl for `HEOperation.MASS_BALANCE` and `HEOperation.TIME_AWARE_MASS_BALANCE` | not started | 6 | Coalition deliverable with paper authors. Driver et al. 2024 §3–§4 reference implementation under encryption; bit-for-bit agreement with `B-CWB-MB-1` is the acceptance criterion. |
| B-CWB-FED-1 | Three-party-model role distinction (cross-jurisdiction query routing) | `backend/backend/federation/models.py` — `FederationRole.DATA_SOURCE_LAB`; plus the `federated_instances` table column | complete | 1 | Shipped 2026-05-12 (PR #55, `dbf34b0`). Distinguishes the cryptWWDB Lab from data-holding `PEER` instances; `FederationClient` predicates filter by role. |
| CRY-A | Key management — keystore loading, rotation policy, signing primitives, Protocol seam | `backend/backend/crypto/_ais_hooks.py` (Protocol surface + `NullAISCryptoHooks`); `backend/backend/crypto/keys.py` (`FilesystemKeystore`); `backend/backend/crypto/signing.py` (`Ed25519Signer`) | complete | 4 | Shipped 2026-05-12 (PR #52, `03ce48c`). Track 1 default refuses-by-default where no safe default exists; Track 2 implementations land at `backend/backend/immune/sec/`. |
| B-CWB-DOC-1 | Audit logging of federation operations — non-collusion policy, key rotation, partner attestation | `docs/federation_operations.md` (operator-facing policy); `backend/backend/federation/_ais_hooks.py` (`AISFederationHooks` Protocol) | complete | 2 | Shipped 2026-05-08 (PR #49, `1eab572`). Three-party non-collusion threat model in §2; multi-key pathway in §3; AIS-hook policy points in §7. |
| B-IMMUNE-HE-2 | Multi-key HE follow-on — privacy-budget accounting under collusion-resistant decryption | `backend/backend/immune/sec/he_backend.py` (multi-key backend); `backend/backend/privacy/budget.py` (DP-budget accountant, reserved) | not started | 8 | Lopez-Alt et al. 2012 multi-key construction; required when the single-key non-collusion assumption (Driver et al. 2024 §4) is no longer acceptable for the deployment topology. Triggered by the first non-trivial production deployment of the cryptWWDB-track. |

The two HE backend operation values needed for cryptWWDB are already declared on the `AISCryptoHooks` Protocol surface (`HEOperation.MASS_BALANCE`, `HEOperation.TIME_AWARE_MASS_BALANCE`); the Protocol-level commitment is what lets the schema work, the plaintext module, and the eventual HE backend all be developed against the same interface without retrofit.

---

## Data flow diagram

End-to-end flow from raw wastewater sample ingestion through the cryptWWDB privacy layer to a federated query response. Each arrow is labelled with the JACKPOT module responsible.

```text
                MUNI A (upstream)                              MUNI B (downstream)
        ───────────────────────────────                ───────────────────────────────
        raw influent sample @ t                        raw influent sample @ t
                │                                              │
                │ wastewater/ingest.py                          │ wastewater/ingest.py
                │   (flow + concentration logged)               │   (flow + concentration logged)
                ▼                                              ▼
        WastewaterSample row                            WastewaterSample row
        + wastewater_target_concentration               + wastewater_target_concentration
        (Q_up, C_up)                                    (Q_down, C_down)
                │                                              │
                │ wastewater/mass_balance.py                    │ wastewater/mass_balance.py
                │   load_inputs_from_db(...)                    │   load_inputs_from_db(...)
                │   → MassBalanceInputs                         │   → MassBalanceInputs
                ▼                                              ▼
        ┌───────────────────────────┐                  ┌───────────────────────────┐
        │ crypto/_ais_hooks.py      │                  │ crypto/_ais_hooks.py      │
        │   select_he_backend(      │                  │   select_he_backend(      │
        │     MASS_BALANCE, parties)│                  │     MASS_BALANCE, parties)│
        │ → HEBackendSpec(CKKS,     │                  │ → HEBackendSpec(CKKS,     │
        │   single_key)             │                  │   single_key)             │
        └─────────────┬─────────────┘                  └─────────────┬─────────────┘
                      │                                              │
                      │ immune/sec/he_backend.py (Track 2)            │ immune/sec/he_backend.py
                      │   encrypt((Q_up, C_up), pk)                   │   encrypt((Q_down, C_down), pk)
                      ▼                                              ▼
                ct_up = Enc(Q_up, C_up)                          ct_down = Enc(Q_down, C_down)
                      │                                              │
                      │ federation/client.py                          │ federation/client.py
                      │   POST /api/v1/federation/he-evaluate         │
                      └───────────────┬──────────────────────────────┘
                                      │
                                      ▼
                        ┌─────────────────────────────┐
                        │ LAB (data_source_lab role)   │
                        │ federation/models.py:        │
                        │   FederationRole.            │
                        │     DATA_SOURCE_LAB          │
                        │                              │
                        │ immune/sec/he_backend.py:    │
                        │   evaluate(                  │
                        │     HEOperation.MASS_BALANCE,│
                        │     ct_up, ct_down)          │
                        │ → ct_result =                │
                        │   ct_down * 1 − ct_up * 1    │
                        │   (under CKKS arithmetic)    │
                        └─────────────┬───────────────┘
                                      │
                                      │ federation/client.py
                                      │   200 OK with ct_result + Ed25519 sig
                                      ▼
                        ┌─────────────────────────────┐
                        │ ORIGINATING MUNI (key holder)│
                        │ crypto/signing.py:           │
                        │   Ed25519Signer.verify()     │
                        │ crypto/keys.py:              │
                        │   FilesystemKeystore.load_key│
                        │ immune/sec/he_backend.py:    │
                        │   decrypt(ct_result, sk)     │
                        │ → MassBalanceResult(         │
                        │     mass_load, quality_flags)│
                        └─────────────┬───────────────┘
                                      │
                                      │ wastewater/mass_balance.py
                                      │   QualityFlag taxonomy applied
                                      ▼
                        operator-facing dashboard
                        (frontend, B-WW-1)
```

The Lab arrow is the only path on which both ciphertexts traverse the same machine; that machine is data-blind by construction (no decryption key). The originating municipality is the only party that performs decryption; the result is signed by the Lab on return so provenance is attestable end-to-end.

---

## Gap analysis

What cryptWWDB requires that JACKPOT does not yet implement. Each item is what blocks the next stage of integration; the list is ordered roughly by the order in which the gaps must close.

- **No Track 2 HE backend at `backend/backend/immune/sec/he_backend.py`.** The file does not exist on disk. `B-IMMUNE-HE-1` (Phase IM-4, Tracked-Not-Scheduled) is the coalition-sprint item with the paper authors that lands it. Concretely required methods on the `AISCryptoHooks` impl: a working `select_he_backend` returning a TenSEAL CKKS spec wired against a real TenSEAL `Context`, plus an `evaluate(operation, *ciphertexts)` extension (currently not on the Protocol; would need to be added or surfaced via the operator's chosen invocation pattern). The current `HEBackendSpec` returned by `NullAISCryptoHooks` is a spec only — no actual CKKS context is constructed and no ciphertext arithmetic is wired up.
- **No DB wiring on `load_inputs_from_db` in `backend/backend/wastewater/mass_balance.py`.** The function currently raises `NotImplementedError`. The wiring blocks on `B-CWB-SCHEMA-1` (`wastewater_upstream_of` / `wastewater_downstream_of` values on `sample_associations.association_type` — the upstream/downstream relationship traversal predicate) and `B-CWB-SCHEMA-2` (`wastewater_target_concentration` typed result row — non-SARS-CoV-2 quantitative target storage). Both gate the P0b ship; until they merge, `compute_mass_load` and `compute_time_aware_mass_load` operate exclusively on inputs assembled by callers.
- **No Alembic migration for the cryptWWDB schema additions.** `B-CWB-SCHEMA-1` through `B-CWB-SCHEMA-5` are tracked in `todo.md` Phase 24.5 but no migration file exists under `backend/db/migrations/versions/`. Naming convention follows the existing pattern (`85d92864ed38_fed_d_federated_instances_and_b_cwb_fed_1_data_source_lab.py` is the precedent); the migration must land before P0b and must hand-write the `association_type` enum extension and the `wastewater_target_concentration` typed table because this codebase has no SQLAlchemy ORM (raw SQL via `text()` in `backend/backend/database.py`; `target_metadata=None` in `alembic/env.py`).
- **No `HEOperation.evaluate(operation, *ciphertexts)` method on the Protocol surface.** The current `AISCryptoHooks` Protocol declares `select_he_backend` which returns a spec, but the actual evaluation entry point — the call site that takes ciphertexts and an operation and returns a result ciphertext — is not yet exposed on the Protocol. Either the Protocol must grow an `evaluate` method or the invocation pattern must be operator-side via the `HEBackendSpec.backend_name` indirection plus a Track 2 backend registry. The shape of this call is what `B-IMMUNE-HE-1` will pin down with the paper authors during the coalition sprint.
- **No privacy-budget accountant at `backend/backend/privacy/budget.py`.** `B-IMMUNE-HE-2` (multi-key HE follow-on) and any DP-noise overlay both require a per-requester privacy-budget accountant. `backend/backend/privacy/` does not yet exist as a package; `PRV-A` is the scaffold item that lands it (`__init__.py`, `_ais_hooks.py`, `coarsening.py`, `scrubber.py`, `dlp.py`, `budget.py`). The `AISPrivacyHooks` Protocol surface (six hooks: `dp_noise`, `track_dp_budget`, `fl_aggregate`, `he_compute`, `mpc_protocol`, `synthetic_substitute`) is already partially designed in `docs/jackpot_immune_collaboration_scaffolding.md` but is not yet on disk.
- **No federation router endpoint for HE evaluation.** `FED-B` lands `POST /api/v1/federation/search`, `POST /api/v1/federation/push`, and `POST /api/v1/federation/access-requests`. None of these is a fit for the cryptWWDB Lab's HE-evaluation call: the request body is `(ct_up, ct_down, operation, parties)`, the auth model is `X-Pipeline-Token` (not the standard JWT or `X-JACKPOT-Federation-Key`), and the response is a signed result ciphertext rather than a JSON result row. A `POST /api/v1/federation/he-evaluate` endpoint with its own router and auth wiring is required and is currently not tracked as a backlog item — should be added as `B-CWB-FED-2` in `todo.md` cryptWWDB Integration Track when the HE-backend coalition sprint scopes.
- **No `B-CWB-MB-1` test coverage for the encrypted variant against the plaintext reference.** Once `B-IMMUNE-HE-1` lands, a property-based test that exercises both paths against the same inputs and asserts approximate-equal results (CKKS is approximate-arithmetic so exact equality is wrong) is required. The test sits under `tests/wastewater/test_mass_balance_he_equivalence.py`; the harness will need a TenSEAL fixture and a tolerance threshold derived from the CKKS scale parameter.
- **No `data_source_lab` role enforcement in the federation router.** `FederationRole.DATA_SOURCE_LAB` is on the model (PR #55) but the router is not yet shipped (`FED-B`). Once it ships, the cryptWWDB-specific routing logic — Lab peers receive HE-evaluation requests only, never Level 2 push payloads or Level 3 access requests — must be encoded as router-level predicates, not just policy comments.

---

## Threat model notes

The cryptWWDB framework's security argument rests on **single-key HE under a three-party non-collusion assumption**: a single CKKS keypair encrypts both municipalities' operands and decrypts the result; security holds as long as no two of (Muni A, Muni B, Lab) collude. The protected pairings are:

- *Muni A vs Muni B* — the Lab learns nothing about either party's operands because it sees only ciphertexts.
- *Each Muni vs the Lab* — the Lab cannot decrypt because it does not hold the secret key.

The case the assumption **forbids** is the Lab colluding with the key-holding Muni: together they hold both ciphertexts and the secret key, and can decrypt the other Muni's inputs. This is the explicit driver for the multi-key follow-on (`B-IMMUNE-HE-2`, Lopez-Alt et al. 2012) — multi-key HE removes the single-key decryption attack by requiring every key-holding party to participate in decryption.

### Mapping to JACKPOT trust boundaries

JACKPOT's existing trust boundaries are documented in `docs/federation_operations.md`. The cryptWWDB threat model maps to them as follows:

- **Federation partner authentication.** Partner instances authenticate via `X-JACKPOT-Federation-Key` (peer-to-peer) or `X-Pipeline-Token` (data-source-lab pipelines). The cryptWWDB Lab uses `X-Pipeline-Token` because the auth surface differs (no `samples` to push, only `pipeline_results` to deliver). The non-collusion assumption assumes each partner key is held distinctly by the party named in the federation registry; key compromise that puts two keys in one party's hands collapses the assumption.
- **AIS hook chain.** The `AISCryptoHooks` Protocol surface gives operators a single injection point to enforce key-rotation policy (`enforce_key_rotation_policy`) and key-management posture (`select_he_backend`'s `key_refs` field). Operators who deploy the cryptWWDB-track should configure `enforce_key_rotation_policy` to `RotationAction.ROTATE_FIRST` rather than the Track 1 default `ALLOW` for any key referenced by a `data_source_lab` peer — key reuse across many ciphertexts increases the attack surface for known-plaintext analysis under approximate-HE schemes.
- **TEE attestation.** The Lab's compute environment should be TEE-attested to mitigate the residual risk that an operator at the Lab tampers with the HE evaluator to leak intermediate ciphertexts. `verify_tee_attestation` is the operator-side seam; the Track 1 default returns `verified=False` which intentionally blocks cryptWWDB-track deployment until Track 2 attestation is wired in.

### Mismatches

- **JACKPOT's default `RotationAction.ALLOW` is too permissive for cryptWWDB.** Operators must override the `NullAISCryptoHooks` default for any cryptWWDB deployment. This is documented; it is not enforced at the code level. Consider adding a `data_source_lab`-aware guard in `enforce_key_rotation_policy` that defaults to `ROTATE_FIRST` when the operation is `HEOperation.MASS_BALANCE` or `HEOperation.TIME_AWARE_MASS_BALANCE`.
- **Single-key HE does not protect against malicious Lab tampering.** The Lab could substitute a result ciphertext for an attacker-chosen one. The Ed25519 signature on the return path is the integrity mitigation; TEE attestation is the stronger one. Operators in a high-trust deployment (e.g. one Lab serving two municipalities under shared sovereignty) can accept the residual risk; operators in a low-trust deployment should not deploy single-key cryptWWDB until `B-IMMUNE-HE-2` (multi-key) lands.

Full treatment of the three-party non-collusion assumption — what single-key HE protects against, what it does not, what changes when the assumption breaks, and the operator-side configuration discipline for keeping the three-party split honest in federation operations — is in `docs/federation_operations.md` §2.

---

## Operational runbook sketch

Numbered steps for a JACKPOT operator enabling cryptWWDB mode on a node. This is a sketch — the production runbook lives in the deployment-specific operator guide and the post-FED-B router wire-up. Use this as the integration checklist when scoping a cryptWWDB-track deployment.

1. **Set environment variables.** On the key-holding Muni's instance:

   ```bash
   export JACKPOT_CRYPTWWDB_ENABLED=true
   export JACKPOT_HE_BACKEND=tenseal-ckks-single-key
   export JACKPOT_HE_KEYSTORE_PATH=/var/lib/jackpot/he-keys
   export JACKPOT_HE_KEY_REF=cryptwwdb-muni-a-2026q2
   export JACKPOT_FEDERATION_LAB_INSTANCE_ID=<UUID of registered Lab>
   ```

   On the Lab's instance:

   ```bash
   export JACKPOT_CRYPTWWDB_ENABLED=true
   export JACKPOT_HE_BACKEND=tenseal-ckks-single-key
   export JACKPOT_PIPELINE_TOKEN_SECRET=<Secret Manager ref>
   ```

   On the non-key-holding Muni's instance: same as the key-holder, but with `JACKPOT_HE_KEY_REF` pointing at the key-holder's public-key material delivered out-of-band.

2. **Run the cryptWWDB schema migration.** Future task — does not yet exist as a backlog item. Naming follows the existing convention (`<slug>_b_cwb_schema_1_wastewater_upstream_of_associations.py`). Migration adds `wastewater_upstream_of` and `wastewater_downstream_of` values to the `sample_associations.association_type` enum and creates the `wastewater_target_concentration` typed result-row table. Track in `todo.md` Phase 24.5 as `B-CWB-MIGRATION-1` when scoping P0b.

3. **Instantiate the AIS hook subclass.** In your deployment-specific bootstrap (typically `deploy/<scenario>/bootstrap.py` or operator-side config), wire the cryptWWDB hook chain:

   ```python
   from backend.backend.crypto._ais_hooks import AISCryptoHooks
   from backend.backend.immune.sec.he_backend import CryptWWDBHooks  # B-IMMUNE-HE-1, future

   hooks: AISCryptoHooks = CryptWWDBHooks(
       backend_name="tenseal-ckks-single-key",
       key_ref=os.environ["JACKPOT_HE_KEY_REF"],
       lab_instance_id=os.environ["JACKPOT_FEDERATION_LAB_INSTANCE_ID"],
   )
   ```

   The `CryptWWDBHooks` class is the deliverable of `B-IMMUNE-HE-1` and does not yet exist on disk. Until it lands, deploying cryptWWDB-mode is a manual exercise of standing up the TenSEAL context out-of-band and pointing `JACKPOT_HE_BACKEND` at the resulting spec.

4. **Register the Lab peer.** Use the FED-B admin endpoints (also future, not yet shipped):

   ```bash
   curl -X POST https://your-jackpot/api/v1/federation/instances \
        -H "Authorization: Bearer <platform-admin-jwt>" \
        -H "Content-Type: application/json" \
        -d '{"name": "Arizona State University cryptWWDB Lab",
              "base_url": "https://cryptwwdb-lab.example.org",
              "role": "data_source_lab",
              "api_key_secret_name": "cryptwwdb-lab-pipeline-token-2026q2",
              "min_sharing_level_for_federation": "ANALYZABLE"}'
   ```

5. **Rotate the federation key.** Once registered, rotate the federation API key out-of-band per `docs/federation_operations.md` §4. Default rotation cadence: 90 days. The cryptWWDB HE keypair has its own rotation cadence — recommended every 30 days or 1M ciphertexts, whichever is sooner, set via `enforce_key_rotation_policy`'s operator override.

6. **Smoke-test the end-to-end path.** With both municipalities and the Lab registered, run one Use Case 1 request against synthetic inputs. The expected result is a `MassBalanceResult` with quality flags and a mass-load value matching the plaintext reference within the CKKS tolerance. If the result does not match, the bug is in the Track 2 HE backend, not the plaintext reference.

7. **Enable production traffic.** Once smoke-test passes, lift the `JACKPOT_CRYPTWWDB_DRY_RUN` flag (future env var; not yet implemented) to direct real Muni samples through the encrypted path. Until then, the plaintext path remains the operative one and the encrypted path is dark.

---

## References

### Primary

- **Driver, E. M., Ahsan, M., Piske, M., Lee, J., Forrest, S., Halden, R. U., & Trieu, C.** (2024). Encrypted data-sharing for preserving privacy in wastewater-based epidemiology. *Science of the Total Environment*, **940**, 173315. <https://doi.org/10.1016/j.scitotenv.2024.173315>. NSF CICI award **2115075**. — The cryptWWDB framework, three-party non-collusion threat model, Use Cases 1 and 2, TenSEAL / CKKS instantiation.
- **López-Alt, A., Tromer, E., Vaikuntanathan, V.** (2012). On-the-fly multiparty computation on the cloud via multikey fully homomorphic encryption. In *Proceedings of the 44th Annual ACM Symposium on Theory of Computing* (STOC '12), pp. 1219–1234. <https://doi.org/10.1145/2213977.2214086>. — The multi-key HE construction that lets each federation entity hold its own secret key; the basis for `B-IMMUNE-HE-2`.
- **Cheon, J. H., Kim, A., Kim, M., Song, Y.** (2017). Homomorphic encryption for arithmetic of approximate numbers. In *Advances in Cryptology — ASIACRYPT 2017*, Lecture Notes in Computer Science vol. 10624, pp. 409–437. Springer. <https://doi.org/10.1007/978-3-319-70694-8_15>. — The CKKS scheme, the approximate-arithmetic HE construction underneath the TenSEAL backend Driver et al. 2024 use.
- **Brakerski, Z., Vaikuntanathan, V.** (2011). Fully homomorphic encryption from Ring-LWE and security for key dependent messages. In *Advances in Cryptology — CRYPTO 2011*, Lecture Notes in Computer Science vol. 6841, pp. 505–524. Springer. <https://doi.org/10.1007/978-3-642-22792-6_29>. — The RLWE foundation underneath BFV / CKKS / TFHE.

### Methodological

- **Hornung, R. W., Reed, L. D.** (1990). Estimation of average concentration in the presence of nondetectable values. *Applied Occupational and Environmental Hygiene*, **5**(1), 46–51. — The LOD/2 substitution rule used by `compute_mass_load` for non-detect handling.
- **Bowes, D. A.** et al. (2023b) and **Tempe, A.** et al. (2023a). — Negative-mass-balance handling conventions (negative → MDL or non-detect substitution), implemented as the `negative_handling` keyword in `backend/backend/wastewater/mass_balance.py`.
- **Choi, P. M.** et al. (2018). Wastewater-based population biomarkers. — Time-varying population-estimate methodology underlying `B-CWB-SCHEMA-3`'s `sample_population_estimate` typed table.

### JACKPOT repo cross-references (verified to resolve)

- `docs/federation_operations.md` — Three-party non-collusion assumption (§2), multi-key HE pathway (§3), federation-key rotation policy (§4), partner attestation (§5), AIS-hook policy points (§7). Shipped 2026-05-08 as `B-CWB-DOC-1`.
- `docs/Jackpot_AIS.md` — The Adaptive Immune System hook-design canonical document. Defines the Track 1 / Track 2 seam pattern the cryptWWDB integration relies on. §1.4 (adaptive immunity), §1.7 (attribution & deception), §1.8 (tolerance / regulation) are the AIS-doc anchors for the four `AISCryptoHooks` hooks.
- `docs/jackpot_immune_platform_plan.md` — Phase IM-4 lands the Track 2 HE backend at `backend/backend/immune/sec/he_backend.py`. §6.2.2 (single-key HE) and §10.5 (multi-key HE) are the design anchors for `B-IMMUNE-HE-1` and `B-IMMUNE-HE-2`.
- `docs/jackpot_immune_collaboration_scaffolding.md` — Track 1 default-implementations + Track 2 paper-author-collaboration deliverables pattern; the rule that Track 1 packages never import from `backend/backend/immune/`.
- `backend/backend/wastewater/mass_balance.py` — Plaintext reference computation for cryptWWDB Use Cases 1 and 2; bit-for-bit reference the encrypted variant must agree with.
- `backend/backend/crypto/_ais_hooks.py` — `AISCryptoHooks` Protocol surface, `HEOperation` enum (with `MASS_BALANCE` and `TIME_AWARE_MASS_BALANCE` values), `NullAISCryptoHooks` Track 1 default.
- `backend/backend/federation/models.py` — `FederationRole.DATA_SOURCE_LAB` value (`B-CWB-FED-1`); `FederatedInstance` registry model.
- `todo.md` § cryptWWDB Integration Track — Backlog items this document tracks against (`B-CWB-MB-1`, `B-CWB-MB-2`, `B-CWB-SCHEMA-1` through `-5`, `B-CWB-FED-1`, `B-CWB-DOC-1`, `B-CWB-DOC-2`, `B-IMMUNE-HE-1`, `B-IMMUNE-HE-2`).
