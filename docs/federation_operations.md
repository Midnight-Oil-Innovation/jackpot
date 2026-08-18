> **Status:** Canonical — operator-facing federation reference.

# Federation Operations

**Document type:** Operator-facing reference for federation deployment.
**Audience:** federation deployment operators, coalition collaborators evaluating peer-to-peer JACKPOT federation, security reviewers auditing the cryptWWDB-readiness story.
**Status:** Track 1 (single-key HE baseline) policy framework. Track 2 (multi-key HE) pathway documented as a forward-looking commitment, not a shipped feature.
**Backlog item:** B-CWB-DOC-1 (Federation/Privacy/Crypto Scaffolds section of `todo.md`).

---

## 1. Overview

This document is the operator-facing reference for running JACKPOT federation across two or more deployment instances. It is policy- and threat-model-oriented; it intentionally does **not** prescribe per-deployment configuration values, runbooks, or step-by-step procedures. Those live in deployment-specific operator guides.

Three orthogonal questions an operator confronts when standing up a federation peer:

1. **Trust model** — what cryptographic and procedural assumptions does the federation rely on, and what attacks remain unmitigated under the baseline configuration? (Section 2)
2. **Operational hygiene** — how are federation API keys managed, rotated, and revoked? How is a partner's identity verified before traffic is exchanged? (Sections 5 and 6)
3. **Policy injection** — where in the codebase do per-deployment policy choices land, and what is the safe default when an operator does not configure them? (Section 7)

JACKPOT's federation package answers (1) and (2) at the platform level and exposes (3) as a hook protocol — `AISFederationHooks` (federation) and `AISPrivacyHooks` (privacy) — so that operators and downstream research collaborators can swap policy implementations via dependency injection without forking the federation code path.

### 1.1 Conceptual anchors

JACKPOT separates the working federation that ships now ("Track 1") from the AIS-augmented overlays that will ship later as Track 2 work lands. The seam between the two tracks is a small set of `Protocol` interfaces with `Null` default implementations; Track 1 code is identical regardless of whether Track 2 hooks have been wired in.

Cross-references:

- `docs/immune_platform.md` Part 2 §§22-29 (post-Cluster-B merge; was `docs/jackpot_immune_collaboration_scaffolding.md`) — the canonical description of the Track 1 / Track 2 seam pattern, including the rule that Track 1 packages never import from `backend/backend/immune/`.
- `backend/backend/federation/README.md` and `backend/backend/privacy/README.md` — package-level documentation of the hook surfaces and their AIS-doc cross-references.
- `docs/architecture.md` v6.0 §20 (post-Cluster-A merge; was `docs/architecture/jackpot_architecture.md` §23) — the three-level federation architecture (query / hub-push / bidirectional) and the qualifying-sample gates for Level 2 push.

### 1.2 cryptWWDB-readiness framing

cryptWWDB is the encrypted wastewater data-sharing framework defined in Driver et al. 2024 (full citation in Section 2.1). JACKPOT's federation, privacy, and crypto packages are designed so that cryptWWDB can land as a Track 2 overlay on top of the existing primitives — concretely, as a homomorphic-encryption backend that satisfies the `AISPrivacyHooks.he_compute(encrypted_inputs, op, key_ref)` Protocol entry point. This document captures the policy assumptions an operator inherits when running the baseline Track 1 configuration in advance of that Track 2 work.

### 1.3 Strategic alignment

JACKPOT's federation architecture aligns with two strategic frameworks:

1. **Struelens et al. 2024** (Frontiers in Science) — six recommendations for real-time pathogen genomic surveillance: (i) universal access to real-time WGS data; (ii) integration of diagnostic microbiology, clinical, and epidemiological data; (iii) cross-sectorial One Health collaborations; (iv) international method/nomenclature harmonization; (v) FAIR-compliant responsible data sharing; (vi) research on WGS-based surveillance methods. JACKPOT Stage 1 addresses (i) and (v); (ii)–(iii) are operator-side integrations out of scope for current phase; (iv) and (vi) are coalition activities.

2. **WHO 2022-2032 strategy** — five objectives for global genomic surveillance: tool access, workforce, data utility, connectivity, readiness. JACKPOT's operator-agnostic design directly serves Objective 4 (interoperable connectivity across human/animal/environmental sectors) and Objective 5 (warm-started flexible infrastructure for surge events). The WHO target of 7-day turnaround from event/pathogen detection to genomic sequencing is encoded as a non-functional requirement in `spec.md`.

---

## 2.0 Non-collusion specification (per Driver et al. 2024)

The cryptWWDB threat model defines non-collusion with two distinct properties
that JACKPOT's federation router and policy checker must preserve:

1. **Symmetric municipality-to-municipality non-collusion.** Muni B does not
   want Muni A to know their wastewater test results, and vice versa. Neither
   municipality may see the other's plaintext input data nor any intermediate
   computation that would leak it.

2. **Asymmetric lab non-collusion.** The third-party laboratory (the HE compute
   party) is not allowed to see plaintext OR results. The lab performs
   computation on ciphertext only, with the encrypted output returned to the
   query originator (Muni A) for decryption. Muni B's flow data is encrypted
   under Muni A's public key by Muni B and is never accessible to the lab
   except as ciphertext.

This specification matters for code review: any data flow where the lab gains
access to plaintext, OR where one municipality could infer the other's
plaintext from observable outputs, violates the threat model.

### 2.1 Source

> Driver, E. M., Ahsan, M., Piske, M., Lee, J., Forrest, S., Halden, R. U., & Trieu, C. (2024). Encrypted data-sharing for preserving privacy in wastewater-based epidemiology. *Science of the Total Environment*, **940**, 173315. NSF CICI award 2115075.

The relevant section is **§4 (Threat model and trust assumptions)**. The framework requires that the computation party not collude with either of the data-producing parties; under that requirement, the single-key HE construction preserves each data producer's inputs against a passive observer between parties.

### 2.2 The three parties

JACKPOT instantiates Driver et al.'s three-party model as three distinct `FederatedInstance` roles in the federation registry:

| Driver et al. role | JACKPOT `FederationRole` | What the party holds | What the party computes |
|---|---|---|---|
| **Muni A** — data producer | `peer` (data-holding municipality) | `samples`, `pipeline_results` for its own catchment | local QC; submits encrypted concentration inputs to the Lab |
| **Muni B** — data producer | `peer` (data-holding municipality) | `samples`, `pipeline_results` for its own catchment | local QC; submits encrypted concentration inputs to the Lab |
| **Lab** — computation party | `data_source_lab` (B-CWB-FED-1) | no `samples` of its own; produces `pipeline_results` via `X-Pipeline-Token` auth | the encrypted mass-balance / aggregation computation across both munis' inputs |

The `data_source_lab` role is the schema-level marker of this asymmetry. It is added by `B-CWB-FED-1` (FED-D in `todo.md`) and is the predicate the `FederationClient` uses to distinguish data-holding peers from the computation party at query time.

### 2.3 What single-key HE protects against

Under the Driver et al. 2024 single-key construction, an honest-but-curious **passive observer between any two parties** (network adversary, log-scraping bystander, compromised TLS terminator on the wire) cannot recover the cleartext concentration inputs from the encrypted payloads in transit. The HE ciphertexts are semantically secure against this attacker.

This is the protection JACKPOT inherits when an operator configures the `AISPrivacyHooks.he_compute` hook to a single-key HE backend (the `B-IMMUNE-HE-1` Track 2 work product in Phase IM-4 of `todo.md`).

### 2.4 What single-key HE does NOT protect against

The single-key construction does **not** protect against collusion between the computation party (Lab) and either data producer (Muni A or Muni B). Concretely:

- If **Muni A and the Lab collude**, they together hold the decryption key (or can reconstruct it from the Lab's view of the protocol), and they can decrypt Muni B's encrypted inputs. The reverse holds symmetrically for Muni B and the Lab.
- This is the **single-secret-key decryption attack** explicitly called out in Driver et al. 2024 §4 as a limitation of the baseline construction.

The threat is not theoretical — it is a structural property of any single-key HE deployment where the computation party holds the key. Operators must understand it before running federation against any peer the Lab might plausibly have an institutional or operational relationship with.

### 2.5 Why this is acceptable as a baseline

Real-world trust relationships among public-health partners are asymmetric. The typical Driver et al. deployment scenario is two municipal wastewater districts (Muni A, Muni B) routing data to a single regional academic laboratory (the Lab) for joint analysis. In that scenario:

- The municipalities have no institutional relationship with each other that would lead them to collude with the Lab against each other; they are administratively separate and, in most cases, do not know each other's operational details.
- The Lab has a research integrity stake in not compromising the protocol and is bound by data-use agreements, IRB constraints, and (where applicable) NSF/NIH grant terms.
- Both municipalities have stronger reasons to trust the Lab than they have to trust each other directly — which is precisely why the Lab is the computation party.

The three-party non-collusion assumption is acceptable in this asymmetric-trust setting. It is not acceptable in symmetric-trust or adversarial-peer settings where the parties have reasons to attempt active decryption of each other's inputs.

### 2.6 What changes when this assumption breaks

The assumption breaks (and operators must move to the multi-key pathway in Section 4) when **any** of the following becomes true for a given federation:

1. The Lab role is filled by a party with an institutional or financial relationship with one of the data producers that makes collusion plausible.
2. A regulator, IRB, ethics committee, or grant condition requires cryptographic — not procedural — separation between the data producers' inputs and the Lab's view.
3. The federation expands beyond the two-data-producer / one-lab topology to a setting where the computation party rotates or is itself federated (then the single-key model has no natural placement of the secret).
4. The federation is used for a data class where single-input recovery would be a meaningful privacy breach beyond the wastewater concentration case (e.g., individual-level rather than catchment-level inputs).

When any of these holds, the baseline configuration is no longer acceptable and the multi-key HE pathway in Section 4 becomes a deployment prerequisite, not a future enhancement.

---

## 3. Jurisdictional alignment patterns (per Tangaro et al. 2026)

Tangaro et al. 2026 (Frontiers in Genetics) identify three architectural archetypes for public-genomic-data infrastructure, which are not mutually exclusive — operators may layer them as a hybrid.

| Archetype | Examples | Sovereignty model | JACKPOT scenario fit |
|---|---|---|---|
| **Centralized archive** | EGA, dbGaP, JGA | Data leaves jurisdiction of origin; central DAC mediates access | Scenarios D, F |
| **Cloud-native platform** | AnVIL, Genomics England TRE | Compute moves to data; data stays in single cloud or TRE | Scenarios B, D |
| **Federated network** | GDI, FEGA, GA4GH Beacons | Data remains at origin; queries route to nodes | Scenarios C, E |

The paper's central finding is operationally significant: the central challenge is no longer building individual platforms, but aligning heterogeneous regulatory interpretations, metadata models, and trust frameworks across jurisdictions.

### 3.1 Hybrid layering

A researcher may discover a dataset through a centralized Beacon (centralized metadata), obtain authorization via a national federated governance node (federated governance), and execute the analysis on a cloud-hosted Secure Processing Environment (cloud-native compute). JACKPOT's federation Stage 1 currently assumes a single federated-network archetype; the `federated_instances` schema should not preclude hybrid layering in future phases.

### 3.2 Phase of normative latency

Tangaro et al. document a current "phase of normative latency": the EHDS Regulation entered into force in 2025, but provisions for secondary use of genomic and clinical-trial data are subject to phased implementation. During the transitional period, cross-border genomic data sharing within the EU continues to rely primarily on national GDPR-based frameworks, which vary across Member States — some require ethics-committee approval for each secondary use, whereas others accept a single broad-consent instrument. JACKPOT operators in EU jurisdictions should expect to handle this heterogeneity until full EHDS applicability lands.

### 3.3 Standards alignment

GA4GH Passports + Data Use Ontology (DUO) form the emerging standard for machine-readable governance: Passports bundle digitally signed assertions (institutional affiliation, ethics approval, prior authorization) into a portable credential; DUO translates consent clauses into structured, queryable terms. JACKPOT's `AISFederationHooks.threshold_approve` Track 2 implementation targets this substrate (see `B-FED-GOV-1` in `todo.md`).

---

## 4. Multi-key HE pathway

The eliminator for the Section 2.4 collusion attack is a multi-key homomorphic-encryption construction in which **each federation entity holds its own secret key** and decryption requires the joint participation of every key-holding party. There is no single party that ever holds enough key material to decrypt unilaterally; Muni-A-and-Lab collusion no longer suffices because Muni B's key is also required.

### 4.1 Source

> López-Alt, A., Tromer, E., & Vaikuntanathan, V. (2012). On-the-fly multiparty computation on the cloud via multikey fully homomorphic encryption. In *Proceedings of the 44th Annual ACM Symposium on Theory of Computing (STOC '12)*, pp. 1219–1234.

The López-Alt et al. construction generalizes fully homomorphic encryption to a setting where ciphertexts encrypted under different keys can be jointly evaluated, with the resulting ciphertext decryptable only by joint participation of the contributing parties. Subsequent work (Mukherjee & Wichs, Chen–Chillotti–Song, and others) has reduced the round complexity and bandwidth costs; the cryptographic landscape is mature enough for production work as of 2026.

### 4.2 Same Protocol surface, different backend

The migration from single-key to multi-key HE in JACKPOT is **not** an API change at the federation or privacy package boundary. Both backends satisfy the same `AISPrivacyHooks.he_compute(encrypted_inputs, op, key_ref)` Protocol method. The signature is identical; the implementing class behind the hook changes. From the Track 1 federation code's perspective, the swap is a single constructor argument.

The concrete migration work is tracked as:

- **`B-IMMUNE-HE-1`** (Phase IM-4) — single-key HE backend implementation per Driver et al. 2024. Inherits the Section 2.4 collusion attack as a known limitation.
- **`B-IMMUNE-HE-2`** (Phase IM-4) — multi-key HE extension per López-Alt et al. 2012. Mitigates the Muni-A-and-Lab collusion risk identified in Driver et al. 2024 §4 by eliminating the single-secret-key decryption attack. Same `backend/backend/immune/sec/he_backend.py` interface as `B-IMMUNE-HE-1`; different crypto backend.

Both items live in Phase IM-4 ("Tracked, Not Scheduled") of `todo.md`. The scheduling trigger for `B-IMMUNE-HE-2` is defined in the backlog item itself and reproduced here as policy.

### 4.3 Trigger for switching from single-key to multi-key

The switch is triggered by **the first non-trivial production deployment of the cryptWWDB-track**, where "non-trivial" means any of:

- A deployment that is no longer purely a research collaboration scaffold — i.e., it begins to inform public-health decisions, regulatory reporting, or operational response.
- A deployment that adds a third or further data-producing party to the topology, breaking the symmetric two-muni assumption that makes the single-key collusion risk easiest to manage procedurally.
- A deployment for which any of the Section 2.6 break conditions becomes true.

Until the trigger fires, the single-key backend (`B-IMMUNE-HE-1`) is the supported configuration and the three-party non-collusion assumption from Section 2 is the operative trust model. After the trigger fires, the multi-key backend (`B-IMMUNE-HE-2`) becomes a deployment prerequisite and operators MUST switch before the next production data exchange.

### 4.4 What multi-key HE does not do

Multi-key HE eliminates the **decryption** collusion attack from Section 2.4. It does not eliminate:

- **Output channel attacks** — if the joint computation's output is itself sensitive (e.g., reveals a single muni's inputs through small-cell counts or selection effects), differential privacy on the output stream (`AISPrivacyHooks.dp_noise`) is still required.
- **Coordinated participation refusal** — multi-key HE requires every party to participate in decryption; a single party can deny service by refusing to participate. This is a usability / governance trade, not a confidentiality break.
- **Active adversaries** — the López-Alt et al. construction is secure against semi-honest adversaries; deployment in a malicious-adversary model requires additional zero-knowledge proofs or maliciously-secure variants. Operators should treat the multi-key backend as a semi-honest construction unless the specific Track 2 implementation is documented as maliciously secure.

Operators who require any of the above protections beyond what multi-key HE provides must layer them explicitly via the other `AISPrivacyHooks` entry points (Section 7).

---

## 5. Federation-key rotation policy

JACKPOT federation peers authenticate to one another using federation API keys, separate from end-user JWTs. The policy framework below is operator-facing — it states what is decided, where the decision is recorded, and who has authority to make and execute the decision. It does not state recommended values; those are deployment-specific.

### 5.1 Where federation keys live

Federation API keys are stored in **Google Secret Manager** (production) or the operator's chosen secret backend (other deployment targets). The `FederatedInstance.api_key_secret_name` field in the federation registry is a **reference** to the secret, not the secret value itself. Plaintext keys are never persisted in the database, in configuration files, or in version control.

Consequently, key rotation is a Secret Manager operation; the `federated_instances` row only changes when the **reference name** changes. In a dual-key rotation window (Section 5.3), two reference names temporarily resolve to the new and old keys until the old key is revoked.

### 5.2 Rotation cadence

The recommended rotation cadence has three triggers; the operator chooses the maximum-allowed interval against the strictest trigger applicable to their deployment:

| Trigger | Recommendation |
|---|---|
| **Calendar** | Rotate at least annually. Deployments with higher exposure (sovereignty-runtime-policy enabled, multi-tenant, or cloud-hosted) should rotate semi-annually. |
| **Personnel change** | Rotate on departure or role change of any individual with credential access at either peer. |
| **Incident** | Rotate immediately on any credible suspicion of credential exposure (lost laptop, leaked log, compromised CI runner, compromised secrets backend). Treat suspicion as exposure; do not wait for proof. |

The calendar trigger is the floor; personnel and incident triggers are unconditional overrides.

### 5.3 No-downtime rotation procedure

The supported procedure is a dual-key window with explicit revocation, executed jointly by the maintainers of the two peers:

1. **Generate the new key** at the peer that will accept inbound traffic with it. Store under a new secret name.
2. **Distribute the new key reference** to the peer that will present it. Update the corresponding `federated_instances` row at the presenting peer to reference the new secret name.
3. **Open the dual-key window.** Both old and new keys are accepted by the receiving peer simultaneously. Duration: short — minutes to hours, not days. The window exists to absorb in-flight requests and partner-side propagation delays, not to defer rotation completion.
4. **Switch the presenting peer to the new key.** All outbound federation traffic now uses the new key.
5. **Verify** by inspecting the receiving peer's federation request logs: confirm that the new key is in use and the old key is no longer presented.
6. **Revoke the old key** at the receiving peer. Update the secret backend to delete or disable the old secret.
7. **Close the dual-key window.** The receiving peer now accepts only the new key. The rotation is complete.

This procedure has no downtime if both peers execute steps in order and the dual-key window is correctly sized. Steps 1, 2, and 6 are the failure points to test in any rehearsal — they are the operations that can leave the federation in a broken state if executed out of order.

### 5.4 Rotation authority

Authority to rotate the federation key of a given peer is held by **the maintainer(s) of that peer's instance**. The federation does not have a central coordinator with cross-instance rotation authority; each peer is sovereign over its own keys.

Rotation requires bilateral coordination: the peer rotating its key and the peer that will accept the rotated key must agree on the dual-key window timing. There is no protocol-level mechanism that enforces this coordination — it is operator-to-operator coordination through whatever channel the peers use (typically email, shared incident tracker, or a coalition-level coordination group).

For multi-peer rotations (rare; usually only on coalition-wide incident response), each peer pair rotates independently. There is no "rotate everywhere atomically" primitive.

### 5.5 Out of scope for this policy

The following decisions are deployment-specific and not specified by this document:

- Key length, algorithm, or generation procedure beyond what the secret backend enforces.
- Specific Secret Manager configuration (replication, encryption-at-rest backend, audit-log destination).
- The communication channel for coordinating rotations between peers.
- Post-rotation testing procedures specific to the federation workload mix.

---

## 6. Partner attestation flow

Before issuing any federation request to a peer, the local JACKPOT instance verifies that the peer is the entity it claims to be. The flow is staged: Track 1 ships with a no-op stub; Track 2 lands real attestation when TEE-based deployments come online.

### 6.1 The `attest_partner` hook

The federation client calls `AISFederationHooks.attest_partner(instance: FederatedInstance) -> bool` before issuing any federation query, push, or access request. The hook signature is the Track 1 / Track 2 seam: a Boolean return signals "trust this partner for this operation."

In Track 1 — the configuration that ships today — the default hook implementation is `NullAISFederationHooks.attest_partner`, which **always returns `True`**. Track 1 federation operates without cryptographic partner attestation; the operator's trust in a peer is established procedurally through the secret-distribution process in Section 5.

The Null default is documented in `backend/backend/federation/_ais_hooks.py` and `backend/backend/federation/README.md` (the hook → AIS doc → Track 2 impl mapping table). The default is intentional: Track 1 must ship a working federation in the absence of TEE infrastructure, and "always trust the configured partner" is the only semantically sensible default that preserves Track 1's no-AIS deployment story.

### 6.2 What Track 1 attestation actually consists of

In the absence of a real `attest_partner` implementation, operator-level partner attestation in Track 1 consists of:

- **Out-of-band identity verification** at federation registration time. Before adding a `federated_instances` row, the operator confirms the peer's identity through a trusted channel — known maintainer, established coalition relationship, signed legal agreement, regulatory registration record.
- **Secret-based authentication on each request.** Possession of the federation API key (Section 5) is the cryptographic proof of identity at request time. This proves the key was issued to the peer; it does not prove the peer's hardware, software stack, or current operational state has not been compromised since the key was issued.
- **Log review** for anomalous request patterns. The `detect_anomalous_traffic` hook is the Track 2 seam for automating this; in Track 1 it is operator review of federation request logs.

Operators must be explicit with themselves and with their coalition that this is the level of attestation in effect. Track 1 federation should not be marketed or documented to data contributors as offering cryptographic partner attestation.

### 6.3 What Track 2 attestation will add

When Track 2 attestation lands (the AIS doc §1.7 hook position; impl module `backend/backend/immune/sec/` per the federation README), the `attest_partner` implementation will verify TEE attestation evidence presented by the peer. The expected flow:

1. The peer presents a remote-attestation quote signed by its TEE provider (e.g., Intel SGX, AMD SEV-SNP, AWS Nitro Enclaves, Google Confidential VMs).
2. The local instance validates the quote against the TEE provider's attestation service and a locally-pinned policy: acceptable TEE providers, acceptable image hashes, acceptable signing keys, freshness window.
3. The local instance optionally cross-references the peer's signed identity claims (organization, role, certificate chain) against the coalition's identity ledger.
4. On any validation failure, the hook returns `False` and the federation client refuses the request, logging the failure for operator review.

Track 2 attestation guarantees that the peer is running a known-good software image inside a known-good TEE at the time of the request. It does not guarantee:

- That the peer's data is correct or unbiased.
- That the peer will not misuse the data it legitimately receives via the federation.
- That the TEE provider itself has not been compromised at a level below the attestation primitive.

Track 2 attestation is a confidentiality and integrity boundary on the peer's compute environment. It is not a policy or behavior boundary; those remain the responsibility of the data-sharing agreements and out-of-band governance documents the coalition operates under.

### 6.4 Operator decision points

When Track 2 attestation lands, the operator chooses (per deployment):

- **Attestation level** — `none` (Track 1 default, `NullAISFederationHooks`), `manual` (operator reviews evidence per onboarding), or `TEE` (cryptographic verification on every request).
- **Pinned policy** — which TEE providers, image hashes, signing keys, and freshness windows are acceptable.
- **Failure mode** — hard-fail (refuse the request, log) or soft-fail (allow the request, emit a warning, downgrade to a more restrictive sharing level). Hard-fail is the recommended default.

These appear in the Section 7 table as the `attest_partner` row.

---

## 7. AIS-hook policy points

The two AIS-hook protocols — `AISFederationHooks` and `AISPrivacyHooks` — are the explicit operator policy injection points in the federation system. Each hook is a decision the operator makes per deployment; the table below names the hook, the decision, where the configuration is recorded, and what happens if the operator does nothing.

A safe default ("not enabled" or "passthrough") is the value that runs Track 1 federation correctly without any AIS-augmented overlay. Operators who require stronger guarantees must explicitly configure the corresponding hook.

| Hook | What operator configures | Where config lives | Default if not configured |
|---|---|---|---|
| `dp_noise` | Default ε (epsilon) for differential-privacy noise on query outputs; per-query-type sensitivity bounds | settings / env | `NullAISPrivacyHooks.dp_noise` returns input unchanged (no noise added) |
| `track_dp_budget` | Per-requester DP budget cap; budget reset cadence; over-budget behavior (refuse / warn) | settings | no enforcement (`NullAISPrivacyHooks.track_dp_budget` returns `float('inf')`) |
| `he_compute` | HE backend selection (single-key per `B-IMMUNE-HE-1` vs multi-key per `B-IMMUNE-HE-2` / `CRY-A`); key management binding | settings | not enabled (`NullAISPrivacyHooks.he_compute` raises `NotImplementedError`) |
| `secure_aggregate` | Aggregation mode for federated query results (plaintext vs cryptographic secure aggregation); aggregation protocol parameters | settings | plaintext (`NullAISFederationHooks.secure_aggregate` returns results unchanged) |
| `attest_partner` | Attestation level (`none` / `manual` / `TEE`); pinned-policy bundle if TEE; failure mode | settings | none (`NullAISFederationHooks.attest_partner` always returns `True`) |
| `threshold_approve` | Threshold M-of-N for sensitive federation actions; which actions require quorum; quorum-key source | settings | not enabled (`NullAISFederationHooks.threshold_approve` always returns `True`, i.e., single-admin approval suffices) |

Additional hooks present in the codebase but not yet operator-facing policy points (deferred until Track 2 lands the corresponding overlays):

- `AISFederationHooks.detect_anomalous_traffic` — Null default returns `False` (no anomaly).
- `AISFederationHooks.validate_push_payload` — Null default returns `True`.
- `AISPrivacyHooks.fl_aggregate`, `AISPrivacyHooks.mpc_protocol` — Null default raises `NotImplementedError`; no Track 1 fallback.
- `AISPrivacyHooks.synthetic_substitute` — Null default returns the input dataset unchanged.

`AISCryptoHooks` is pending the CRY-A scaffold (Federation/Privacy/Crypto Scaffolds section of `todo.md`); its policy points (HE backend selection at the crypto layer, threshold signing via FROST / BLS / DKG, TEE attestation evidence verification, key-rotation policy enforcement) will be added to this table when CRY-A ships.

### 7.1 Configuration discipline

Per the Track 1 / Track 2 seam pattern, **switching a hook from its Null default to a concrete implementation is a constructor argument**, not a code edit to the federation or privacy packages. The operator's deployment-bootstrap code is the one place where the choice of hook implementation is made. Examples of where this lands in practice:

- The `jackpot init` CLI (`docs/architecture/jackpot-init-cli.md`) bakes the operator's hook choices into the per-deployment settings file.
- The FastAPI dependency-injection layer (`backend/backend/main.py` and the router-level `Depends(...)` factories) is where the concrete `AIS*Hooks` instance is constructed and passed into the federation / privacy classes.
- Deployment-specific overrides live in environment variables consumed by the settings module; they should never live in code paths that ship in the binary.

This discipline is what makes the safe defaults safe: the federation code path is identical regardless of which hooks are wired, so the only way to weaken the security posture is to **explicitly** choose a hook implementation that does so.

---

## 8. Source-of-truth navigation

The documents below ground the policies in this file. Operators reviewing or extending federation behavior should read them alongside this document.

### 8.1 In-repo references

All references in this section are verified present on disk in the `b-cwb-doc-1` branch.

| Document | Path | Why an operator reads it |
|---|---|---|
| AIS theoretical anchor | `docs/immune_platform.md` Part 1 §§1.3-1.8 (post-Cluster-B merge; was `docs/Jackpot_AIS.md`) | The §1.3 / §1.4 / §1.6 / §1.7 / §1.8 hook positions that the federation and privacy READMEs map their `AISFederationHooks` and `AISPrivacyHooks` Protocol entries onto. Read this for the AIS framing that grounds every hook in Section 7. |
| Immune-platform vision and roadmap | `docs/immune_platform.md` (post-Cluster-B merge; was `docs/jackpot_immune_platform_plan.md`) | §6.2.2 (Pillar III federation plan) and §10.5 (`TrustEngine` spec) are the canonical references for Phase IM-4 federation work and for the multi-key HE future direction tracked here as `B-IMMUNE-HE-2`. |
| Immune-platform collaboration scaffolding | `docs/immune_platform.md` Part 2 §§22-29 (post-Cluster-B merge; was `docs/jackpot_immune_collaboration_scaffolding.md`) | Canonical description of the Track 1 / Track 2 seam pattern; the ratio between shipped engineering and deliberately-open research questions; the eleven critiques the federation scaffold is responding to. |
| Architecture & developer reference | `docs/architecture.md` v6.0 (post-Cluster-A merge; was `docs/architecture/jackpot_architecture.md`) | §20 ("Federation Architecture") is the three-level federation reference and the source of the qualifying-sample gates (`surveillance_relevant=TRUE`, `sharing_level ≥ min_sharing_level_for_federation`, `quality_status ≥ ANALYZABLE`) for Level 2 hub push. (Was §23 pre-merge.) |
| Federation package README | `backend/backend/federation/README.md` | The FED-A scaffold: package layout, `AISFederationHooks` Protocol, hook → AIS doc cross-reference table, Track 2 impl module map. |
| Privacy package README | `backend/backend/privacy/README.md` | The PRV-A scaffold: package layout, `AISPrivacyHooks` Protocol, the six hook positions and their AIS doc cross-references, the explicit note that TEE attestation is a crypto-layer (not privacy-layer) hook. |

### 8.2 Backlog cross-references

For navigation back into `todo.md`:

- `B-CWB-DOC-1` — this document. Federation/Privacy/Crypto Scaffolds section, FED-B subsection.
- `B-CWB-FED-1` — `data_source_lab` `FederationRole` enum value (FED-D).
- `B-IMMUNE-HE-1` — single-key HE backend implementation (Phase IM-4, Tracked, Not Scheduled).
- `B-IMMUNE-HE-2` — multi-key HE extension per López-Alt et al. 2012 (Phase IM-4, Tracked, Not Scheduled).
- `B-CWB-MB-1` and `B-CWB-MB-2` — mass-balance computation modules; the Tier-1 plaintext workload that the single-key HE backend will later encrypt.
- `CRY-A` scaffold — `AISCryptoHooks` Protocol seam (Federation/Privacy/Crypto Scaffolds section; pending).
