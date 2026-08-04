> **Status:** Canonical — strategic synthesis (CDC DMI / North Star / STLT).

# JACKPOT — Strategic Vision Summary

**Document type:** Standalone strategic synthesis — the elevator-pitch view that lives alongside the canonical reference docs
**Version:** 2.0 (Cluster F restructure 2026-05-16; was v1.0 of 2026-05-09)
**Last updated:** 2026-05-16
**Author:** Glen Otero (gotero@linuxprophet.com), assembled with Claude
**Audience:** Glen + future contributors first; written so a partner lab, grant reviewer, or RC team could follow along without prior context
**Status:** Living strategic summary. Architectural detail lives in the canonical reference docs (see Document Map below); this doc is the strategic narrative arc that ties them together.

---

## Document map — what this doc is and isn't

This is the **strategic summary** for JACKPOT. It exists to give a reader the strategic arc in one sitting without making them read 4,000-line architecture docs. It carries the **three theses**, the **strategic positioning content** (adopter segments, peacetime utility, CDC DMI/STLT/Tribal alignment, publication/partnership pipeline), and the **strategic differentiators** (sovereignty as category-of-one, on-prem-first as positioning).

It does **not** carry the architectural detail. Per the May 2026 Cluster F restructure, sections that previously duplicated content from the canonical reference docs were collapsed to brief summaries with explicit pointers. The canonical references:

| Topic | Canonical reference |
|---|---|
| Platform architecture, deployment scenarios, `jackpot init`, distribution packages, execution profiles | `docs/architecture.md` v6.0 (post-Cluster-A merge) |
| Immune Platform vision, five pillars, dual-AIS thesis, Phase 26+ roadmap | `docs/immune_platform.md` (post-Cluster-B merge) |
| Component-tier adoption catalog (~85 OSS tools across 14 categories) | `docs/detection_landscape.md` |
| Platform-tier comparative landscape (Loculus, Pathogenwatch, etc.) | `docs/platform_landscape.md` (post-Cluster-E consistency pass) |
| JACKPOT Learn — Academy, Field Edition, SENTINEL, WILDFIRE | `docs/learning_strategic_vision.md` + `docs/learning_curriculum_design.md` |
| Federation architecture (3 levels) | `docs/federation.md` + `docs/federation_operations.md` |
| Wastewater-based epidemiology | `docs/wastewater.md` + `docs/wastewater_software_landscape.md` |
| Governance / standards alignment (WHO, GA4GH, North Star, FAIR+CARE) | `docs/governance_alignment.md` (Cluster F sibling) |
| GCP deployment guide | `docs/deploy/gcp.md` (Cluster F sibling, was `sovereign_portal_delta.md`) |
| Operational spec / current state | `docs/spec.md` |
| Backlog / roadmap detail | `docs/todo.md` |

**Companion document:** `jackpot_status_and_roadmap_may_2026.md` (concrete accomplishments, current blockers, sequencing of work in flight).

---

## Table of contents

1. [Executive summary — the platform thesis](#1-executive-summary--the-platform-thesis)
2. [Architectural positioning — on-prem-first, cloud as upgrade](#2-architectural-positioning--on-prem-first-cloud-as-upgrade)
3. [Strategic alignment — CDC DMI / North Star / STLT](#3-strategic-alignment--cdc-dmi--north-star--stlt)
4. [Indigenous data sovereignty as category-of-one differentiator](#4-indigenous-data-sovereignty-as-category-of-one-differentiator)
5. [The Immune Platform vision — strategic frame](#5-the-immune-platform-vision--strategic-frame)
6. [JACKPOT Learn as platform infrastructure — strategic frame](#6-jackpot-learn-as-platform-infrastructure--strategic-frame)
7. [Differentiators vs peer platforms — strategic frame](#7-differentiators-vs-peer-platforms--strategic-frame)
8. [Strategic positioning — who adopts JACKPOT and why](#8-strategic-positioning--who-adopts-jackpot-and-why)
9. [Publication and partnership pipeline](#9-publication-and-partnership-pipeline)

---

## 1. Executive summary — the platform thesis

JACKPOT is an open-source, AGPL-3.0, operator-agnostic pathogen genomics platform under `Midnight-Oil-Innovation/jackpot`. The platform is built around three balanced theses:

**Thesis 1 — Operator agnosticism.** JACKPOT runs anywhere a pathogen-genomics lab works, from a researcher's laptop to a federated multi-agency cloud deployment. The same codebase, the same schema, the same routers; different deployment scenarios bootstrap different operator configurations via `jackpot init`. This is not "cloud platform that also runs locally" — it is "laptop and on-prem-server platform that also scales to cloud and federation."

**Thesis 2 — The dual-AIS architecture (Phase 26+).** The same family of bio-inspired algorithms that detect anomalous pathogen genomes can also detect anomalous platform behavior. JACKPOT is designed to run both simultaneously, sharing a single algorithmic substrate. This closes the loop on Stephanie Forrest's 1994 negative-selection algorithm — invented for cybersecurity, adapted to biology, brought back to defend a biology platform.

**Thesis 3 — Workforce-as-platform-infrastructure (Phase 26+).** Public-health workforce capacity is the rate-limiting factor in pandemic preparedness, not tooling. JACKPOT Academy and the Outbreak / SENTINEL / WILDFIRE games are not deliverables on top of a platform — they are platform infrastructure that produces the operators, contributors, and adversarial training data that the rest of the system needs.

The platform's capability set: two PII gates at ingest (NCBI SRA Human Scrubber for genomic PII, GCP Cloud DLP for metadata PII), four deployment scenarios (A self-hosted commodity / B HPC / C single-org cloud / D CI test) with federation, multi-tenancy, and Indigenous data sovereignty as runtime configurations layered on top, three distribution packages, two container runtimes (Docker and Apptainer as first-class), federated query architecture compatible with GA4GH standards, and CARE-Principle-aware runtime policy capabilities. Year-round peacetime utility for AMR, TB, flu, and seasonal diagnostic workloads. AGPL-3.0 with operator-agnostic codebase and clear governance.

No platform in the comparative landscape — Pathoplexus / Loculus, GenSpectrum / LAPIS, Pathogenwatch, EnteroBase, NCBI Pathogen Detection, BV-BRC, Solu, RT-MetA, GISAID, IDseq, IRIDA-ARIES, amr.watch, SeqScreen-Nano, HPD-Kit — combines this set of capabilities. Most do none of them.

---

## 2. Architectural positioning — on-prem-first, cloud as upgrade

The most important architectural posture decision: **JACKPOT is not a cloud platform that also runs locally. It's a laptop and on-prem-server platform that also scales to cloud and federation. Cloud is the upgrade path, not the assumed path.**

This positioning is strategic, not just technical:

1. **The WHO IPSN equity story.** Most countries doing pathogen genomics are not running on Google Kubernetes. They're running on a laptop, a single Linux server, or an institutional cluster. JACKPOT speaks their language because the default `jackpot init` flow targets exactly those environments. The platform-tier landscape doc (`docs/platform_landscape.md` §10) documents that JACKPOT's two-PII-gate architecture aligns with WHO IPSN attribute 6 — most peer platforms align with zero or one.

2. **University research-computing teams.** The people who actually deploy bioinformatics platforms at scale outside major federal agencies. Their environment is Slurm, Apptainer, shared filesystems, and LDAP. Scenario B (HPC) is built for them. The execution-profile model (per-pipeline-run executor selection) eliminates the deployment-time decision-making that breaks most "cloud-first" platforms in an HPC context.

The architectural detail backing this positioning — the four deployment scenarios with their compute targets and trust boundaries, the three distribution packages (`jackpot-cli` / `jackpot-server` / `jackpot-pipelines`), the Docker-and-Apptainer-as-first-class runtime parity, the file-reference model with storage state, the per-pipeline-run execution profile selection, and the `jackpot init` bootstrap CLI — is all in `docs/architecture.md` v6.0 §§2-8. Read that doc for the implementation specifics; this section just frames why the architectural choices are strategic differentiators.

The README's lead now reads: *"JACKPOT runs on your laptop. It also scales to your university's HPC cluster. Same codebase. Cloud examples follow."* That sentence is the platform thesis in one line.

---

## 3. Strategic alignment — CDC DMI / North Star / STLT

### 3.1 Where DMI stands

CDC's Data Modernization Initiative was launched in 2020 with a roughly $1B initial congressional allocation. The vision was sound: cloud-native, FHIR-aligned, TEFCA-compatible, "blueprint not platform" with local data control. The pandemic exposed exactly the problems DMI was designed to fix — point-to-point submissions from providers, incompatible formats, fax machines still in routine use for case reporting in 2020.

**Funding for the broader DMI was paused in October 2025** (Wave 2 Implementation Center applications halted), but the underlying technical vision is broadly endorsed by the STLT public health community. **The pause is political and budgetary, not architectural.** Whatever rebuild eventually happens will likely follow the same shape, possibly led by a different agency or coalition.

This matters for JACKPOT positioning: the technical decisions JACKPOT has already made — cloud-native option, multi-tenant-capable, schema-driven, AGPL-3.0 with clear governance, multiple install scenarios — match what STLT agencies were promised by DMI. JACKPOT's Scenarios A (self-hosted commodity, with variants from laptop through multi-lab agency) and C (single-org cloud) directly map to the STLT-facing tiers North Star described. Federation membership is available to any of A/B/C as a runtime configuration.

### 3.2 The "Front Door" pattern

DMI's "CDC Front Door" was meant to be a single ingest endpoint that auto-routed inbound data. JACKPOT already has the genomics-narrow-scope version: a single ingest endpoint that auto-routes based on input type (signed URL, URI, FHIR, SRA, CSV). Document this as the "single-entry-point for genomic data into a public health agency" — that framing matters for grant narratives.

### 3.3 TEFCA / FHIR — Year 2+

TEFCA is the policy + agreements framework for inter-organizational health data exchange. As of 2025 there are about a dozen QHINs (Qualified Health Information Networks) operational. Public Health Agencies participate as "exchange purpose actors" and can query for data under explicitly enumerated public-health exchange purposes.

**Genomic data exchange is not a TEFCA initial use case.** The TEFCA Public Health Exchange Purpose currently focuses on case reporting and case investigation. Plausibly in scope for future iterations, but not today.

What JACKPOT actually needs from TEFCA:

- **Probably not direct TEFCA participation.** JACKPOT is genomics-layer, not case-reporting-layer.
- **But** STLT operators running JACKPOT will be receiving eCR via TEFCA. Linking a specimen referenced in an eCR to a genome sequenced and analyzed in JACKPOT requires JACKPOT to consume FHIR `Specimen` and `MolecularSequence` resources.
- **And** JACKPOT can usefully *emit* FHIR resources back into the operator's record systems — when a sequence is processed, emit a FHIR `Observation` with `MolecularSequence` reference.

The FHIR resources that matter, with explicit "NEVER" rows:

| FHIR resource | JACKPOT use |
|---|---|
| `Patient` | NEVER — JACKPOT doesn't store patient identifiers |
| `Specimen` | Inbound — link a JACKPOT sample to an upstream specimen reference from eCR/ELR |
| `Substance` | Inbound for some bacterial culture isolates |
| `Observation` (lab result) | Inbound from ELR; outbound for sequence-derived results |
| `MolecularSequence` | Both directions — the canonical FHIR shape for genomic data |
| `Organization` | Inbound — link sequencing labs and PHAs |
| `Practitioner` | NEVER — JACKPOT users are not patient-care practitioners in the FHIR sense |
| `Provenance` | Outbound — emit pipeline-result provenance |

JACKPOT doesn't process patient-level PHI by design — that's the metadata DLP gate's job. Adopting FHIR shouldn't change that posture; if anything, it reinforces it.

**Recommended timing:**

- **Now (Year 1):** Document JACKPOT's data model in FHIR-translatable terms. The LinkML schema gives us enough abstraction that this is documentation work, not engineering.
- **Year 2 if pressure mounts:** Build `backend/routers/fhir.py` that consumes inbound FHIR `Specimen` and `MolecularSequence` and emits outbound `Observation` and `Provenance` for completed pipelines.
- **Year 2+ if a TEFCA-participating operator adopts JACKPOT:** Help them build the bridge from their TEFCA-receiving infrastructure to JACKPOT.

**Don't build TEFCA/FHIR support speculatively.** The implementation cost is real and the window of relevance for STLT operators is 2–3 years out for genomics specifically.

### 3.4 What JACKPOT does NOT compete with

- **NBS** (case reporting), **eCR** (electronic case reporting), **AIMS** (lab-data routing) all operate at a layer JACKPOT does not occupy
- JACKPOT is **downstream** of them — sample-and-sequence-centric, not case-centric
- Position JACKPOT as the genomics layer that *integrates with* NBS / eCR / AIMS, not a replacement

---

## 4. Indigenous data sovereignty as category-of-one differentiator

This is the highest-leverage and lowest-cost strategic differentiator JACKPOT has access to.

### 4.1 The structural opportunity

CDC's North Star uses "STLT" as a four-letter acronym uniformly. In practice, the **T** (Tribal) was sometimes treated as a special case of **L** (Local) — which it definitely is not. **Tribes are sovereign nations.**

There's no evidence in the public North Star materials that **CARE Principles** (Collective benefit, Authority to control, Responsibility, Ethics) were formally adopted as a design constraint. By contrast:

- **NIH** has explicit Indigenous data governance guidance for genomic research grants
- **Tribal IRBs** routinely require CARE-aligned data handling
- **Some states** (Washington, New Mexico, Arizona, Oklahoma, etc.) have inter-governmental agreements with Tribes that go beyond what North Star contemplates

**JACKPOT formally adopting CARE Principles + designing for sovereignty-aligned runtime policy capabilities is a category-of-one differentiator in pathogen genomics.** None of Loculus, Pathogenwatch, EnteroBase, NCBI PD, BV-BRC, Solu, RT-MetA, or GISAID does this.

### 4.2 What it means architecturally — sovereignty as runtime policy

Per the May 2026 Cluster A architecture merge, **Indigenous data sovereignty is a runtime configuration, not a separate deployment scenario.** This was a deliberate reframing from the earlier "Scenario T" design. The reasoning, in brief:

- Sovereignty-aligned capabilities (deletion-on-request via tombstone-and-vacuum, no-auto-publish defaults, federation policy restrictions, audit visibility, residency enforcement, revocable consent) are *enforcement primitives* available to every JACKPOT deployment
- Whether they're *enabled* depends on per-org policy, not on the install scenario
- A Tribal college running JACKPOT for genomics coursework picks Scenario A and does not configure sovereignty policies. A Tribal Nation health department running JACKPOT under CARE Principles also picks Scenario A and configures sovereignty policies via `jackpot policy enable ...`. Both are Scenario A; the policy stance differentiates them.

The architectural detail (the `samples.deletion_status` state machine, the audit_log event types, the tombstone-and-vacuum lifecycle, the configurable vacuum cadence) is in `docs/architecture.md` v6.0 §22 (Sovereignty as runtime policy). Most of the work is governance and config, not net-new engineering. **One architectural piece does require real work:** deletion-on-request that actually removes the data, not just hides it.

### 4.3 Federation pattern — Tribal Epidemiology Center pattern

TECs are HIPAA-recognized public health authorities serving 574 Tribes and 9.7 million AI/AN people. **A JACKPOT instance at a TEC + JACKPOT instances at member Tribes = canonical federation participation, but with Tribally-controlled aggregation rules per runtime sovereignty configuration.**

This is the right shape for federated analysis where the "self/non-self" boundaries are politically meaningful, not just operationally convenient.

### 4.4 The three areas where North Star is silent and JACKPOT can lead

1. **Indigenous Data Sovereignty (CARE Principles).** Adopt formally in `governance/care-principles-and-indigenous-data-sovereignty.md`. Pair with FAIR. Ship a Tribal-deployment guide.
2. **Sovereignty-preserving deployment.** Air-gappable local-first with runtime-controlled federation; aligns with RT-MetA's territory and JACKPOT's existing scenario architecture.
3. **Genomics-specific data flows.** North Star is mostly about case data, lab data, vital records, immunization. The genomics layer hasn't been pre-claimed by a federal-led design that would constrain JACKPOT.

The Phase 24.5 design lockdown gates P0b (Schema v5.0) — the implementation lands in P0c alongside multi-tenancy middleware.

---

## 5. The Immune Platform vision — strategic frame

The Immune Platform is JACKPOT's Phase 26+ roadmap. The dual-AIS architecture (Thesis 2) and workforce-as-platform-infrastructure (Thesis 3) both land here.

**Strategic frame:** the Immune Platform takes the operator-agnostic genomics platform JACKPOT is today and adds five pillars that together make it the most complete public-health biosurveillance platform on the planet. The pillars are not separate products — they share a single algorithmic substrate (the AIS family), a single schema, a single deployment model.

The five pillars:

- **Pillar I — Bio-Anomaly Detection Stack** (`jackpot-immune-bio`). Negative Selection Algorithm + Dendritic Cell Algorithm + AMAnD-as-NSA + multi-modal danger fusion. The genomics anomaly detector.
- **Pillar II — Platform Self-Defense AIS** (`jackpot-immune-sec`). The same NSA substrate, retargeted to detect anomalous platform behavior. Cyberbiosecurity defense built from the same code as bio-anomaly detection.
- **Pillar III — Federation as Immune Network** (`jackpot-immune-net`). Federation members as B-cell colonies; cross-cell confirmation as co-stimulation; trust calibration as autoimmunity prevention. NVIDIA FLARE as the FL substrate, with TenSEAL/OpenFHE as HE siblings for the cryptWWDB workload.
- **Pillar IV — Training as First-Class Citizen.** JACKPOT Academy. Workforce capacity as platform infrastructure. Module 9 (Negative selection in practice) students implement detectors that get PR'd into the production `jackpot-amand` module.
- **Pillar V — Gaming as First-Class Citizen.** Outbreak: Field Edition (solo narrative), SENTINEL (cooperative cell-based), OPERATION: WILDFIRE (competitive ARG-flavored). Game players generate adversarial training data; game mechanics stress-test federation trust dynamics.

The full strategic vision plus implementation plan, schema extensions, OSS integration strategy, threat model integration, implementation roadmap (Phases IM-1 through IM-6), research/partnership/publication pipeline, and component adoption strategy is in `docs/immune_platform.md` (post-Cluster-B merge — 4,175 lines spanning three parts).

The component-tier survey of ~85 open-source detection tools that the pillars adopt from is in `docs/detection_landscape.md`. The training and gaming docs are `docs/learning_strategic_vision.md` and `docs/learning_curriculum_design.md`.

This section is the strategic frame; read those four docs for the operational detail.

---

## 6. JACKPOT Learn as platform infrastructure — strategic frame

Pillar IV (Training) and Pillar V (Gaming) together form **JACKPOT Learn** — the educational platform layer that hosts four learner-facing experiences (Academy, Field Edition, SENTINEL, WILDFIRE) running on a single shared spine.

**Strategic frame:** workforce IS the platform. The same insight that drives Thesis 3 — public-health workforce capacity is the rate-limiting factor in pandemic preparedness — operationalizes into a structural commitment:

1. The curriculum teaches AIS by being it (students don't read about negative selection; they implement an NSA detector that gets PR'd into the production `jackpot-amand` module)
2. Student work generates labeled data (module exercises produce labeled anomalies that train the production clonal-selection loop; wrong answers in Field Edition / SENTINEL / WILDFIRE become adversarial training data)
3. Module completions are immune memory (the Academy runs on a tenant; student contributions are versioned, attributable, reusable)

The strategic positioning matters: most pathogen-genomics platforms treat training as a separate help-desk activity. JACKPOT treats training as platform infrastructure — same monorepo, same schema, same governance, same AGPL. This is what makes the WHO IPSN equity story credible (a deployable platform with built-in workforce capacity) and what makes the Forrest-Biodesign partnership coherent (the curriculum teaches the AIS framework Forrest's lab studies).

The full strategic vision is in `docs/learning_strategic_vision.md` (the why and what). The catalog, module specs, case progressions, and season arcs are in `docs/learning_curriculum_design.md` (the how).

This section is the strategic frame; read those two docs plus `docs/immune_platform.md` §§7-8 (which redirect to the learn docs) for the full picture.

---

## 7. Differentiators vs peer platforms — strategic frame

JACKPOT competes with (or is positioned alongside) about two dozen pathogen-genomics platforms. The detailed comparative analysis lives in `docs/platform_landscape.md` (post-Cluster-E consistency pass) — 23 platforms surveyed across architecture, data scope, license posture, deployment model, governance, federation capability, and audience fit.

**Strategic frame:** the platforms cluster into three groups, and JACKPOT's positioning is distinctive in each comparison:

**Vs. Pathoplexus / Loculus / GenSpectrum / LAPIS** (the open-source-platform peer group): JACKPOT brings two PII gates instead of one, federation as runtime configuration instead of single-tenant assumption, AIS-as-organizing-principle vs Pathoplexus's open-data-as-organizing-principle, and the operator-agnostic-from-the-ground-up codebase vs Loculus's single-tenant codebase that other operators have to fork.

**Vs. Pathogenwatch / EnteroBase / NCBI Pathogen Detection / BV-BRC** (the curated-database peer group): JACKPOT is a *platform* for running and federating those workflows, not a curated database. The peer-platform docs note "JACKPOT is one of 23 platform-tier peers"; this is the architectural position.

**Vs. Solu / RT-MetA / GISAID / IDseq** (the commercial / hosted peer group): JACKPOT's AGPL-3.0 + on-prem-first architecture is the equity story those platforms can't tell. RT-MetA's territory (sovereignty-preserving deployment) overlaps; JACKPOT's CARE-Principles + sovereignty-as-runtime-policy framing is the strategic moat.

The single most important framing from the comparative landscape, captured in `docs/platform_landscape.md` §19: **no other platform combines operator-agnosticism, two PII gates, federation, sovereignty-aware runtime policies, and a workforce/education infrastructure layer.** Most peers do one. A few do two. None do all four.

---

## 8. Strategic positioning — who adopts JACKPOT and why

### 8.1 Adopter segments

**The spreadsheet-refugee market.** Labs currently tracking samples in shared Excel files or LIMS spreadsheets with no genomics integration. JACKPOT's Scenario A (self-hosted commodity, laptop case) is the path of least resistance — `pipx install jackpot && jackpot init`, pick "laptop," and within an hour they have a real database, a real schema, real pipelines, and real ingest. This is the largest under-served segment and the one most reachable by the Academy's Practitioner tier.

**WHO IPSN equity story.** Most countries doing pathogen genomics are not running on Google Kubernetes. They're running on a laptop, a single Linux server, or an institutional cluster. The on-prem-first architecture and Apptainer support speak directly to LMIC partners. JACKPOT's two PII gates align with WHO IPSN attribute 6 (most peer platforms align with zero or one).

**University research-computing teams.** RC/HPC teams deploy bioinformatics platforms at scale outside major federal agencies. Their environment is Slurm, Apptainer, shared filesystems, and LDAP. Scenario B (HPC) is built for them. The execution-profile model (per-pipeline-run executor selection) eliminates the deployment-time decision-making that breaks most "cloud-first" platforms in an HPC context.

**State public health labs (post-DMI).** STLT operators were promised a North-Star-aligned platform. JACKPOT's Scenario A (multi-server / agency variant) and Scenario C (single-org cloud), plus federation as a runtime configuration and a TEFCA/FHIR Year 2+ option, give them the architectural shape they were expecting. The "Front Door" pattern in JACKPOT's narrower scope is already here.

**Tribal authorities and Tribal Epidemiology Centers.** A category-of-one differentiator. CARE-Principle-aligned, sovereignty-as-runtime-policy capabilities, Tribally-controlled aggregation rules. The work is mostly governance and config plus the one architectural piece (deletion-on-request) — meaningful but not enormous. The political-architectural alignment is the moat.

**Federation members (Year 2+).** The FED-A scaffold is the foundation. Real federation use cases include cross-state outbreak investigation, cross-border AMR surveillance (US/Mexico/Canada via PulseNet successor), cross-institutional university collaboration, and public-health-to-One-Health linkage (clinical + veterinary + environmental).

### 8.2 The "peacetime utility" requirement

A critical requirement for long-term funding is ensuring the platform provides routine value during non-pandemic periods:

- **Routine clinical support** — seasonal influenza, UTI sequencing, tuberculosis (TB) diagnostics
- **Antimicrobial resistance (AMR)** — phenotypic susceptibility data and genotypic AMR tracking provide year-round value to hospitals and agricultural agencies
- **Extended health insights** — secondary use in early cancer screening or precision medicine monitoring during peacetime

JACKPOT's pipeline zoo (MIRA-NF, PHoeNIx, MycoSNP-NF, Aquascope, Tostadas, MicrobeTrace adoption in P0i) covers the peacetime use cases that justify continuous operation.

### 8.3 What JACKPOT does NOT do

Saying yes to the right scope is half the battle; saying no to the wrong scope is the other half:

- **Not a case-reporting platform** — NBS / eCR / AIMS occupy that layer
- **Not a LIMS** — JACKPOT integrates with LIMS, doesn't replace them
- **Not a primary repository in the GISAID sense** — JACKPOT can submit to NCBI / GISAID / ENA / DDBJ via Seqsender; it doesn't aim to replace them
- **Not a clinical decision support system** — JACKPOT is for surveillance and research, not patient care
- **Not directly TEFCA-participating** — Year 2+ option for FHIR ingest/emit, gated on operator demand

---

## 9. Publication and partnership pipeline

### 9.1 Differentiator papers (two, in balance)

1. ***JACKPOT: a federated artificial immune system for pathogen genomic surveillance and cyberbiosecurity.*** Methods venue — *Nature Methods* / *Genome Biology* / *PLOS Computational Biology*.
2. ***JACKPOT Academy: workforce-as-platform-infrastructure for public health bioinformatics.*** Workforce venue — *Frontiers in Public Health* / *PLOS Comp Bio Education*.

Both papers' seed material is in `docs/immune_platform.md` (post-Cluster-B merge, was `jackpot_immune_platform_plan.md`). The Academy paper is uniquely shippable — workforce/training papers in the genomics-education space are rare and the field is hungry for them.

### 9.2 Partnership angles

- **Biodesign collaboration target (primary).** Identified in `docs/immune_platform.md` §16.0 as the primary partnership lane (the ASU Biodesign Center for Biocomputing, Security and Society — Forrest / Trieu / Lee / Halden).
- **WHO IPSN.** The two-PII-gate architecture and on-prem-first deployment story align directly with IPSN's stated priorities.
- **Tribal Epidemiology Centers.** TECs are HIPAA-recognized public health authorities serving 574 Tribes and 9.7 million AI/AN people. A reference deployment at one TEC + one or two member Tribes — running Scenario A with sovereignty-aligned runtime policies enabled — would establish the federation pattern.
- **University RC teams.** Partner with one institutional RC team for a Scenario B (HPC) reference deployment. Their feedback hardens the Apptainer-first / systemd-unit-file path, the LDAP/SAML auth path, and the Slurm executor profile templates.
- **CDC operating divisions.** Even in DMI's funding pause, individual operating divisions (NCEZID, OPHDST) have ongoing needs. CDC's open-source pipelines (seqsender, MIRA-NF, PHoeNIx, MycoSNP-NF, Aquascope, Tostadas, MicrobeTrace) are all Apache-2.0; JACKPOT's adoption sequence in P0i picks them up directly.

### 9.3 Open-source adoptions, prioritized

| Item | Source | License | Phase | Justification |
|---|---|---|---|---|
| **seqsender** | CDC | Apache-2.0 | P0i (Month 3) | Replace placeholder NCBI/GISAID submission with real working code |
| **MIRA-NF pipeline** | CDC | Apache-2.0 | P0i (Month 3) | Flu/SARS/RSV via IRMA |
| **PHoeNIx pipeline** | CDC | Apache-2.0 | P0i (Month 3) | AMR/HAI bacteria — high-value for state PHL deployments |
| **MycoSNP-NF pipeline** | CDC | Apache-2.0 | P0m (Month 4) | Fungal (C. auris) — emerging surveillance need |
| **Aquascope pipeline** | CDC | Apache-2.0 | P0m (Month 4) | Wastewater SARS-CoV-2 with NWSS alignment |
| **Tostadas pipeline** | CDC | Apache-2.0 | P0m (Month 4) | NCBI/GISAID submission via Liftoff/VADR/Bakta |
| **MicrobeTrace** | CDC | Apache-2.0 | P0m (Month 4) | Browser-based outbreak visualization |
| **PHIN VADS vocabularies** | CDC | n/a (data) | **Month 3 — urgent** | PHIN VADS sunsets Nov 30, 2026; pull as schema reference data BEFORE then |
| **PHES-ODM data model** | Big-Life-Lab | MIT | P0m (Month 4) | Wastewater alignment for EU/Canadian deployments |
| **GA4GH `/service-info` endpoint** | GA4GH | Apache-2.0 spec | P0i (Month 3) | One afternoon's work, makes JACKPOT discoverable |
| **DRS-style URI conventions** | GA4GH | Apache-2.0 spec | P0i (Month 3) | Already 80% there; formalize as standard |
| **Sapporo-WES spike** | DDBJ | Apache-2.0 | Month 4 (2-week spike) | Evaluate as alternative to bespoke pipeline orchestration |
| **Wave (self-hosted)** | Seqera | AGPL-3.0 | Month 5 | Container provisioning; AGPL-on-AGPL clean |
| **Crypt4GH support** | GA4GH | Apache-2.0 spec | Month 6+ | For Scenarios A (multi-org variant) / C with sensitive data at rest |
| **Beacon v2 endpoint** | GA4GH | Apache-2.0 spec | Month 6+ | For federation participation |
| **TESSy AMR record-format export** | ECDC | n/a (spec) | Month 6+ | EU bridge for European federation deployments |
| **NCBI SRA Human Scrubber (HRRT)** | NCBI | Public domain | Already in JACKPOT | Already integrated as `ingest_scrubber.nf` |

---

*End of strategic vision summary v2.0. The strategic narrative arc is preserved; the architectural and implementation detail lives in the canonical reference docs listed in the Document Map at the top of this file. The 90-day-window content from the v1.0 §14 was stripped in the Cluster F restructure (the window had elapsed; current sprint priorities live in `docs/todo.md` and `jackpot_status_and_roadmap_may_2026.md`).*
