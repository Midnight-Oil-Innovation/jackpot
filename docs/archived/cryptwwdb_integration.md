> **Status:** Superseded — archived (directory convention). Historical; do not cite as current.

# cryptWWDB Integration

Architectural mapping of the cryptWWDB encrypted wastewater-based-epidemiology framework (Driver et al. 2024, *Sci Total Environ* 940:173315, NSF 2115075) onto JACKPOT's integration surface as of `development` HEAD (2026-05-12).

---

## 1. Overview

This document is the source-of-truth for how the cryptWWDB framework maps onto JACKPOT's architecture and what is required — schema, federation, doc, plaintext computation, crypto scaffold, and homomorphic-encryption (HE) backend — for JACKPOT to be a credible production substrate for the framework. It tracks the integration-readiness state at `development` HEAD and is updated as backlog items ship.

**Audience.**

- **Collaborators on the cryptWWDB integration thread** — primarily R.U. Halden and the Driver/Trieu paper authors. The "where can JACKPOT host the cryptWWDB framework today, and what is still needed?" question.
- **Operators deploying the cryptWWDB-track** — Scenario E (federation member) and Scenario C (multi-lab agency) operators wiring up the wastewater overlay. The "what knobs and roles do I configure?" question.
- **Future JACKPOT maintainers** — the "why is the AIS-hook seam pre-allocated for HE, and what shape does the cryptWWDB framework expect on the other side of it?" question.

**Cross-references.**

- [`docs/Jackpot_AIS.md`](Jackpot_AIS.md) — AIS-hook design and the Track 1 / Track 2 seam pattern that gives this integration its shape.
- [`docs/jackpot_immune_collaboration_scaffolding.md`](jackpot_immune_collaboration_scaffolding.md) — Track 1 default-implementations + Track 2 paper-author-collaboration deliverables pattern.
- [`docs/jackpot_immune_platform_plan.md`](jackpot_immune_platform_plan.md) — Phase IM-4 details, including §6.2.2 (single-key HE) and §10.5 (multi-key HE) where the cryptWWDB HE backend lands.
- [`docs/federation_operations.md`](federation_operations.md) — §2 covers the three-party non-collusion assumption in full; §3 covers the multi-key pathway; §4 covers federation-key rotation.
- `todo.md` § cryptWWDB Integration Track — the backlog that this doc cross-references.

---

## 2. The cryptWWDB protocol

cryptWWDB (Driver, Ahsan, Piske, Lee, Forrest, Halden, Trieu — *Sci Total Environ* 2024, NSF 2115075) is a privacy-preserving wastewater-based-epidemiology (WBE) framework that computes the standard mass-balance equation over data the participating municipalities never share in the clear. The framework is target-agnostic — the paper exercises it against heroin and 6-acetylmorphine, but the same math runs for SARS-CoV-2, opioids, indicator chemicals, or any other quantitative wastewater target.

**Use Case 1 — segment mass-load.** For two sampling points in a shared sewershed (one upstream, one downstream), compute the mass-load contribution of the segment between them:

```
MassLoad = (Q_down · C_down) − (Q_up · C_up)
```

where `Q_*` are volumetric flow rates and `C_*` are pathogen or chemical concentrations. cryptWWDB evaluates the equation over RLWE-encrypted operands so neither municipality observes the other's flow or concentration, and the lab performing the computation observes neither.

**Use Case 2 — time-aware variant.** The per-sample mass load is evaluated at two timestamps and the difference is reported, exposing temporal change in the segment's contribution without revealing the individual values at either timestamp. Same math, applied twice and then subtracted.

**Three-party model.** The protocol has three distinct roles:

| Role | What they hold | What they learn |
|---|---|---|
| **Muni A** | Upstream flow + concentration `(Q_up, C_up)` | Only the final mass-load result (and only if authorized to receive it) |
| **Muni B** | Downstream flow + concentration `(Q_down, C_down)` | Same as Muni A |
| **Lab** | The ciphertexts and the HE evaluation key | Nothing about the operands; produces the result ciphertext |

The Lab is computationally privileged but data-blind. The municipalities are data-rich but learn nothing of each other's measurements. None of the three parties holds enough state alone to recover any private input.

**Backend.** Driver et al. 2024 use TenSEAL (Microsoft SEAL underneath) with the CKKS scheme — approximate-arithmetic HE well-suited to fixed-point quantities like flow and concentration. The protocol is single-key: one keypair encrypts all operands, decryption is performed by the key-holder once the result ciphertext is delivered.

**Three-party non-collusion assumption.** The protocol's security argument is that single-key HE protects each pair of parties against the third *as long as no two of them collude*. The case that breaks single-key HE is collusion between the Lab and either Muni — the Lab has the ciphertexts, a Muni has the secret key, together they decrypt the other Muni's inputs. This assumption is explicit in Driver et al. 2024 §4 and is the trigger for the multi-key-HE follow-on (Lopez-Alt et al. 2012). Full treatment of what single-key HE does and does not protect against, what changes when the assumption breaks, and the operator-side configuration discipline for keeping the three-party split honest is in [`docs/federation_operations.md`](federation_operations.md) §2.

---

## 3. JACKPOT integration surface

Six concrete deliverables are required for JACKPOT to host cryptWWDB as a Track 2 overlay. Status reflects `development` HEAD as of 2026-05-12.

| Backlog item | What it ships | Status (2026-05-12) |
|---|---|---|
| **B-CWB-SCHEMA-1 … B-CWB-SCHEMA-5** (Phase 24.5) | Five schema additions: `wastewater_upstream_of` / `wastewater_downstream_of` values on `sample_associations.association_type`; `wastewater_target_concentration` typed result row for non-SARS-CoV-2 quantitative targets; time-varying population fields (`population_served_weekday/weekend` + `sample_population_estimate` typed table); `fecal_normalization_results` typed table; per-target `excretion_factors` + `in_sewer_degradation_factors` lookup tables. | Tracked, blocked on P0b ship |
| **B-CWB-FED-1** (bundles with FED-D) | `data_source_lab` value on the `FederationRole` enum, matching the three-party model's distinct Lab role — a peer that produces `pipeline_results` via `X-Pipeline-Token` auth but holds no `samples` of its own. | Tracked, not yet merged (may merge before or after FED-D in parallel) |
| **B-CWB-DOC-1** (bundled into FED-B) | [`docs/federation_operations.md`](federation_operations.md) — three-party non-collusion assumption, multi-key HE pathway, federation-key rotation, partner attestation, AIS-hook policy points. | ✅ Shipped (`1eab572`, PR #49) |
| **B-CWB-MB-1** | `backend/backend/wastewater/mass_balance.py` — Tier 1 plaintext mass-balance module (`compute_mass_load` Use Case 1, `compute_time_aware_mass_load` Use Case 2, unit conversions, non-detect handling per Hornung & Reed 1990, negative-mass-balance handling per Bowes 2023b / Tempe 2023a). The function-level interface that the Track 2 HE backend delegates to. | ✅ Interface-only shipped (`d78b240`, PR #50). Full DB wiring (`load_inputs_from_db`) remains a `NotImplementedError` stub pending `B-CWB-SCHEMA-2` + `B-CWB-SCHEMA-1` in P0b. 48 tests, 100% module coverage. |
| **CRY-A** | `backend/backend/crypto/_ais_hooks.py` — `AISCryptoHooks` Protocol seam (HE backend selection, threshold signing, TEE attestation, key rotation policy) + `NullAISCryptoHooks` Track 1 default + filesystem keystore + Ed25519 signing primitives. The seam the cryptWWDB HE backend plugs into. | ✅ Shipped (`03ce48c`, PR #52) |
| **B-IMMUNE-HE-1** (Phase IM-4) | Track 2 HE backend at `backend/backend/immune/sec/he_backend.py` — concrete `AISCryptoHooks` implementation for Use Cases 1 & 2 over RLWE-encrypted operands (TenSEAL / CKKS), plus the memory-cell-match query type from the immune plan §6.2.2. Single-key threat model. | Tracked, Not Scheduled — coalition deliverable with the paper authors |

The two HE backend `Operation` enum values needed for cryptWWDB are already declared on the `AISCryptoHooks` Protocol surface shipped with CRY-A:

```python
class HEOperation(StrEnum):
    ADDITION = "addition"
    MULTIPLICATION = "multiplication"
    MASS_BALANCE = "mass_balance"                   # cryptWWDB Use Case 1
    TIME_AWARE_MASS_BALANCE = "time_aware_mass_balance"  # cryptWWDB Use Case 2
    MEMORY_CELL_MATCH = "memory_cell_match"
```

— see `backend/backend/crypto/_ais_hooks.py`. The Protocol-level commitment to these operations is what lets the schema work, the plaintext module, and the eventual HE backend all be developed against the same interface without retrofit.

---

## 4. Integration sequence

Three stages, each gated on the prior. Stage A is mostly complete; Stage B closes the cryptWWDB-readiness milestone; Stage C is the coalition deliverable with the paper authors.

### Stage A — Architectural readiness

What `development` already has in place to host the framework:

- ✅ AIS-hook seam pattern documented (`Jackpot_AIS.md`, `jackpot_immune_collaboration_scaffolding.md`).
- ✅ Track 1 / Track 2 split with concrete Track 2 implementation sites pre-allocated (`backend/backend/immune/sec/he_backend.py` reserved for the cryptWWDB HE backend).
- ✅ Plaintext mass-balance module (`B-CWB-MB-1` interface-only) — the function-level reference the encrypted variant stays bit-for-bit faithful to.
- ✅ Crypto scaffold (`CRY-A`) — `AISCryptoHooks` Protocol with `MASS_BALANCE` and `TIME_AWARE_MASS_BALANCE` operations declared, `NullAISCryptoHooks` refuse-by-default Track 1 default, filesystem keystore + Ed25519 signing primitives.
- ✅ Federation-operations documentation (`B-CWB-DOC-1`) — three-party non-collusion assumption codified in [`docs/federation_operations.md`](federation_operations.md) §2.

Still pending in Stage A:

- ⏳ `B-CWB-FED-1` — `data_source_lab` `FederationRole` enum value (bundles with FED-D). Required to model the cryptWWDB Lab as a distinct peer role.
- ⏳ FED-B / FED-C / FED-E — the rest of the Federation Track 1 wire-up (schema migration, tests, router, `main.py` wiring). The cryptWWDB-track inherits these.

### Stage B — cryptWWDB-readiness ("ready to collaborate")

What lands post-P0b to close the milestone in which JACKPOT can credibly host the cryptWWDB framework as a Track 2 overlay:

1. **`B-CWB-SCHEMA-1` and `B-CWB-SCHEMA-2` ship with P0b** — at minimum. `wastewater_upstream_of` / `wastewater_downstream_of` on `sample_associations.association_type` and the `wastewater_target_concentration` typed result row are the architectural-demonstration minimum. `B-CWB-SCHEMA-3` through `B-CWB-SCHEMA-5` (time-varying population, fecal normalization, excretion / degradation factors) are production-maturity additions but not blockers.
2. **`B-CWB-MB-1` full DB wiring** — replace `load_inputs_from_db`'s `NotImplementedError` stub with a real SQLAlchemy implementation against the post-P0b schema. The plaintext computation is in place; this unblocks single-instance demonstration over real data.
3. **`B-CWB-MB-2` QC + trigger work** — non-detect handling with MDL substitution, negative-mass-balance handling, error-bar propagation, weekly / rolling averages, percent-change calculations, population-threshold trigger points that aggregate adjacent catchments when minimums aren't met. Per Driver et al. 2024 Table 2.
4. **`B-WW-1` lineage-abundance dashboard already shipped** (`f177712`, PR #51) — provides the visible wastewater story end-to-end independent of cryptWWDB; the mass-balance dashboard layer slots in next to it.

At the end of Stage B, JACKPOT is a credible production substrate for cryptWWDB: schemas in place, plaintext reference computation running over real data, federation roles wired, crypto scaffold seam exposed. The framework can be demonstrated end-to-end in plaintext mode, and the HE work has a complete interface to delegate to.

Effort estimate from current `development`: roughly 4–6 weeks of focused work if it is the only sprint thread.

### Stage C — HE backend implementation (Phase IM-4)

The coalition deliverable with the paper authors. Not maintainer-solo work in advance.

- **`B-IMMUNE-HE-1`** — Concrete `AISCryptoHooks` implementation at `backend/backend/immune/sec/he_backend.py` for `HEOperation.MASS_BALANCE` and `HEOperation.TIME_AWARE_MASS_BALANCE`. TenSEAL / CKKS backend per the paper, single-key threat model per Driver et al. 2024 §4. Plugs the `B-CWB-MB-1` plaintext interface in as the bit-for-bit reference under encryption. Also covers the immune-plan §6.2.2 memory-cell-match query type as the second concrete operation. Reference: immune-plan §6.2.2, §10.5; Driver et al. 2024.
- **`B-IMMUNE-HE-2`** — Multi-key HE follow-on per Lopez-Alt et al. 2012. Each federation entity holds its own secret key; result decryption requires participation from all key-holding parties via joint computation. Mitigates the Lab + Muni collusion risk explicitly identified in Driver et al. 2024 §4. Same `he_backend.py` interface, different crypto backend. Triggered when single-key deployment proves the operational model and the stronger threat model becomes required (likely with first non-trivial production deployment of the cryptWWDB-track).

Both items remain "Tracked, Not Scheduled" because the natural sequence is: ship Stage B → demonstrate the plaintext story to the paper authors → schedule the HE-backend work as a coalition sprint.

---

## 5. License compatibility

JACKPOT is AGPL-3.0 (see `LICENSE`). The cryptWWDB framework as published depends on:

| Component | License | Compatible with AGPL-3.0 consumer? |
|---|---|---|
| TenSEAL (OpenMined) | Apache License 2.0 | ✅ Yes — Apache-2.0 is a permissive license; AGPL-3.0 may incorporate Apache-2.0 code (the FSF lists Apache-2.0 as compatible with GPL-3.0 / AGPL-3.0). |
| Microsoft SEAL | MIT License | ✅ Yes — MIT is a permissive license with attribution; AGPL-3.0 may incorporate MIT code without restriction. |

The AGPL-3.0 obligations flow outward from JACKPOT: a network-service operator who modifies the cryptWWDB-track integration code in JACKPOT must publish those modifications under AGPL-3.0 to users of the service. The TenSEAL and SEAL libraries themselves remain under their original licenses; AGPL-3.0 does not relicense them. Attribution requirements for both libraries are honored in the standard way (preserved license headers, mention in `NOTICE` once they become runtime dependencies).

No additional license obligations are introduced by the cryptWWDB protocol itself — it is a research framework, not a licensed product. The NSF grant (2115075) funded the framework's development but does not constrain downstream re-implementation.

---

## 6. Threat model

The cryptWWDB framework's security argument rests on **single-key HE under a three-party non-collusion assumption**: a single key encrypts both municipalities' operands and decrypts the result; security holds as long as no two of (Muni A, Muni B, Lab) collude. The protected pairings are *Muni A vs Muni B* (the Lab learns nothing about either party's operands because it sees only ciphertexts) and *each Muni vs the Lab* (the Lab cannot decrypt because it does not hold the secret key). The case the assumption forbids is the Lab colluding with the key-holding Muni — together they hold both ciphertexts and key and can decrypt the other Muni's inputs. This is why the multi-key follow-on (Lopez-Alt et al. 2012, `B-IMMUNE-HE-2`) is on the roadmap: it removes the single-key decryption attack by requiring every key-holding party to participate in decryption.

The full treatment — what single-key HE protects against, what it does not, what changes when the assumption breaks, and the operator-side configuration discipline for keeping the three-party split honest in federation operations — is in [`docs/federation_operations.md`](federation_operations.md) §2.

---

## 7. References

**Driver, A., Ahsan, A., Piske, M., Lee, K., Forrest, S., Halden, R.U., Trieu, N.H.** (2024). Encrypted data-sharing for preserving privacy in wastewater-based epidemiology. *Science of the Total Environment*, 940, 173315. https://doi.org/10.1016/j.scitotenv.2024.173315. Funded by NSF award 2115075. — The cryptWWDB framework, three-party non-collusion threat model, Use Cases 1 and 2, TenSEAL / CKKS instantiation.

**López-Alt, A., Tromer, E., Vaikuntanathan, V.** (2012). On-the-fly multiparty computation on the cloud via multikey fully homomorphic encryption. In *Proceedings of the 44th Annual ACM Symposium on Theory of Computing* (STOC '12), pp. 1219–1234. https://doi.org/10.1145/2213977.2214086. — The multi-key HE construction that lets each federation entity hold its own secret key; the basis for `B-IMMUNE-HE-2`.

**Brakerski, Z., Vaikuntanathan, V.** (2011). Fully homomorphic encryption from Ring-LWE and security for key dependent messages. In *Advances in Cryptology — CRYPTO 2011*, Lecture Notes in Computer Science vol. 6841, pp. 505–524. Springer. https://doi.org/10.1007/978-3-642-22792-6_29. — The RLWE foundation underneath the BFV / CKKS / TFHE schemes used by SEAL and TenSEAL.

**Kim, M.** (2021). Toward a homomorphic-encryption query layer for federated genomic surveillance. (Cited in `docs/jackpot_immune_platform_plan.md` §6.2.2 as the HE-query-layer reference for the JACKPOT immune-platform design.) — The design template for the `B-IMMUNE-HE-1` HE query layer that the cryptWWDB Use Case 1 and Use Case 2 operations land inside.

**Hornung, R.W., Reed, L.D.** (1990). Estimation of average concentration in the presence of nondetectable values. *Applied Occupational and Environmental Hygiene*, 5(1), 46–51. — The LOD/2 substitution rule used by `compute_mass_load` for non-detect handling.

**Bowes, D.A.** et al. (2023b) and **Tempe, A.** et al. (2023a). — Negative-mass-balance handling conventions (negative → MDL or non-detect substitution), implemented as the `negative_handling` keyword in `backend/backend/wastewater/mass_balance.py`.

**Choi, P.M.** et al. (2018). Wastewater-based population biomarkers. — Time-varying population estimate methodology underlying `B-CWB-SCHEMA-3`'s `sample_population_estimate` typed table.

**Feng, S.** et al. (2021) and **Zuccato, E.** et al. (2008) and **Hart, O.E., Halden, R.U.** (2020). — Source references for the fecal-normalization (`B-CWB-SCHEMA-4`) and excretion / in-sewer-degradation factor (`B-CWB-SCHEMA-5`) lookup tables.
