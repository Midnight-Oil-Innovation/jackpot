# JACKPOT Governance & Standards Alignment

## How JACKPOT maps to WHO/IPSN, WHO Guiding Principles, GA4GH, CDC North Star, and FAIR/CARE

**Status:** Working synthesis · 2026-05-09 · v1.1 (Cluster F consistency updates applied 2026-05-16)
**Scope:** Maps JACKPOT's current architecture and roadmap to five governance/standards frameworks: WHO/IPSN's 12 essential attributes for pathogen genomic data-sharing platforms (PGDSPs), WHO's 13 guiding principles for pathogen genome data sharing, GA4GH's interoperability standards (DUO, DRS, Phenopackets, Beacon), CDC's North Star Architecture for STLT (State, Tribal, Local, Territorial) public health partners, and the FAIR + CARE data principles. Companion document to `docs/architecture.md` v6.0 (the canonical architecture reference, post-Cluster-A merge) and `docs/platform_landscape.md` (the platform-tier landscape, post-Cluster-E consistency pass).

---

## 0. Executive summary

This document is the alignment view: where does JACKPOT stand against the five external frameworks that operators (and JACKPOT itself) will be evaluated against?

**Headline finding:** JACKPOT is in good shape on the technical attributes (Infrastructure & Security, Data Submission, Data Curation, Data Provenance, Interoperability, Analytical & Reporting) — these are mostly ✅ Met or 🔶 Partial-with-clear-roadmap. The gaps cluster on the **governance, transparency, sustainability, and benefits-sharing** attributes — the document-work that Pathoplexus has shipped and JACKPOT hasn't (yet). The single highest-leverage piece of work is therefore the `governance/` directory (`B-GOV-1`), which closes ~5 attribute gaps simultaneously with a few hours of writing.

**Five top action items derived from this analysis (all already in the consolidated backlog):**

1. **`B-GOV-1`** — Create `governance/` directory with charter, COI, jurisdiction, benefits-sharing, grievance procedure, shutdown/portability plan, advisory-board scaffold. **Closes WHO/IPSN attributes 1, 2, 10, 12 + WHO Guiding Principles 11, 12, 13.** *3-5 hours of writing. Phase: P0d.*

2. **`B-PPX-1`** — Per-sample OPEN/RESTRICTED radio button on Streamlit upload page. Schema already supports it (`data_use_terms`, `embargo_release_date`, `citation_request`). **Closes WHO/IPSN attribute 8 (Access) and 10 (Data Use & Benefits Sharing) gaps; activates WHO Guiding Principle 8 ("As open as possible…").** *Half a session. Phase: any.*

3. **`B-NCBI-2`** — hAMRonization output mandate for all AMR pipelines in the zoo. **Closes WHO/IPSN attribute 9 (Interoperability) and 11 (Analytical & Reporting Capabilities) AMR-side gaps.** *1 session per pipeline. Phase: pipeline-zoo work.*

4. **`B-FDP-1`** — FAIR Data Pipeline provenance audit and gap-closure. **Drives FAIR R1.2 from 🔶 to ✅; strengthens WHO/IPSN attribute 7 (Data Provenance).** *1 week audit + 1-2 weeks implementation. Phase: when FAIR R1.2 is on deck.*

5. **`B-GISAID-1`** — Auto-Acknowledgments block on dataset export. **Activates WHO Guiding Principle 6 (Acknowledgement & intellectual credit) at the export-time UX layer.** *1-2 sessions. Phase: any.*

The rest of this document is the detailed alignment work: matrices in Section 1, then per-framework prose in Sections 2-6 covering only the rows that are 🔶 or ❌ (✅ rows are self-explanatory from the matrix and don't need prose). Section 7 consolidates the action items.

---

## 1. Alignment matrices

This section is the matrix-first view per `userPreferences` style. Every row is a requirement from one of the five frameworks; every cell records JACKPOT's current status with one-line evidence.

**Status legend:**

- **✅ Met** — feature or property is shipped in production code or schema; no open work needed for compliance.
- **🔶 Partial** — partially shipped; clear roadmap item or active work; gap is well-understood.
- **❌ Gap** — not addressed yet; on the backlog or surfaced here as a new item.
- **➖ N/A** — requirement doesn't apply to JACKPOT's operating model (rare; explained inline).

### 1.1 WHO/IPSN 12 essential attributes (PGDSP framework)

Source: WHO *Essential attributes of pathogen genomic data-sharing platforms* (Attributesential.pdf), 2025. Twelve attributes organized as Sections 2.1 through 2.12 of that document.

| # | Attribute | JACKPOT status | Evidence (one line) |
|---|---|---|---|
| 1 | **Governance** | 🔶 Partial | Single-owner project under Midnight-Oil-Innovation; AGPL-3.0; no published charter, COI policy, or advisory board yet — `B-GOV-1` closes this. |
| 2 | **Transparency** | 🔶 Partial | Public spec.md + architecture.md + assessment.md + this document; immutable audit log on every state change; governance docs missing — `B-GOV-1`. |
| 3 | **Infrastructure & Security** | ✅ Met | GCP Workload Identity Federation; encrypted in-transit (TLS) and at-rest (Cloud SQL CMEK + GCS); secrets in Secret Manager; private VPC + Cloud SQL; six-state scrubber lifecycle; Cloud DLP for metadata; six-role RBAC. |
| 4 | **Data Scope** | ✅ Met | Pathogen-agnostic schema (LinkML v4.4); One Health sectors (human/wildlife/livestock/wastewater/water/air/soil/surface/food/produce/vectors); metagenomic support; ADHS reportable-organism integration. |
| 5 | **Data Submission** | ✅ Met | Six ingest paths (signed URL, URI registration, SRA accession, workspace promotion, CSV batch, Globus deposit-first); tier-aware validation (PRELIMINARY/ANALYZABLE/SUBMITTABLE); DataHarmonizer templates; CSV harmonizer for legacy formats. |
| 6 | **Data Curation** | ✅ Met | NCBI SRA Human Scrubber (genomic PII gate, 6-state lifecycle, skip governance); GCP Cloud DLP (metadata PII gate); content-sniffing file detection (Critical Rule 20); tier semantics surface incomplete metadata. |
| 7 | **Data Provenance** | 🔶 Partial | Audit log on every state change; immutable append-only `pipeline_results`; `PipelineProvenance` table (FAIR R1.2 Month 3); persistent identifiers; gap on input-data version tracking and execution-environment snapshot — `B-FDP-1`. |
| 8 | **Access** | 🔶 Partial | Sharing levels (PRIVATE/LAB/DISCOVERABLE/PUBLIC); `can_access_sample` permission cascade; access request lifecycle with 90-day passive approval; per-sample OPEN/RESTRICTED at submission UI is not wired (schema supports it) — `B-PPX-1`. |
| 9 | **Interoperability** | ✅ Met | LinkML schema with full ontology anchoring (PHA4GE, GenEpiO, NCBI BioSample, MIxS, ENVO, GA4GH DUO/DRS, LOINC, SNOMED CT, ELR, NWSS); TOSTADAS for NCBI; planned LAPIS-compat (Year 2); hAMRonization (in-flight via `B-NCBI-2`). |
| 10 | **Data Use & Benefits Sharing** | 🔶 Partial | GA4GH DUO codes per dataset; `embargo_release_date`; `citation_request`; per-sample data-use-terms UI not wired (`B-PPX-1`); benefits-sharing framework doc missing (`B-GOV-1`); auto-Acknowledgments at export missing (`B-GISAID-1`). |
| 11 | **Analytical & Reporting Capabilities** | 🔶 Partial | Pipeline zoo (12+ entries: viralrecon, bactopia, mycosnp, tb-profiler, etc.); Streamlit dashboards; planned LAPIS-compat (`B-LAPIS-1`); planned hAMRonization output mandate (`B-NCBI-2`); planned NCBI BigQuery JOIN (`B-NCBI-1`). |
| 12 | **Sustainability** | 🔶 Partial | Open-source AGPL-3.0; operator-agnostic by design (`jackpot init`); multi-deployment-target architecture (four scenarios A-D per the May 2026 Cluster A merge, with federation/multi-tenancy/sovereignty as runtime configurations layered on top); single-maintainer dependency is the active risk; sustainability section of `governance/` doc missing — `B-GOV-1`. |

**Matrix summary:** 4 ✅ Met, 8 🔶 Partial, 0 ❌ Gap, 0 ➖ N/A. The eight Partials are all on the active roadmap; five of them are addressed by `B-GOV-1` alone.

### 1.2 WHO guiding principles (13 principles for pathogen genome data sharing)

Source: WHO *Guiding principles for pathogen genome data sharing* (`WHO_guiding_principles_for_pathogen_genome_data_sharing.pdf`), 2022.

| # | Principle | JACKPOT status | Evidence (one line) |
|---|---|---|---|
| 1 | **Capacity development** | ✅ Met | Operator-agnostic by design; `jackpot init` allows small labs to deploy; four deployment scenarios (A self-hosted commodity / B HPC / C single-org cloud / D CI), with Scenario A explicitly targeting minimal infrastructure from a researcher's laptop through agency multi-server. |
| 2 | **Collaboration and cooperation** | 🔶 Partial | Open-source AGPL-3.0 invites contributions; federation architecture (3-level) supports cross-institution collaboration; collaboration framework doc missing — `B-GOV-1`. |
| 3 | **High-quality, reproducible data** | ✅ Met | Tier-aware validation (PRELIMINARY/ANALYZABLE/SUBMITTABLE) explicitly marks lower-quality data per WHO guidance; SRA Human Scrubber removes human reads pre-storage per WHO §3 ("human genomic data should be removed before submission"); content-sniffing file detection. |
| 4 | **Global and regional representativeness** | ➖ N/A | Operator-agnostic — JACKPOT itself doesn't gate participation by geography; representativeness is determined by which operators deploy it. The architectural commitment is "any operator anywhere can run JACKPOT." |
| 5 | **Timeliness** | ✅ Met | Tier-aware ingest accepts incomplete metadata (PRELIMINARY) immediately; pipelines launch without waiting for full metadata; six ingest paths optimize for different speed regimes (Globus deposit-first for bulk, signed URL for direct, accession for SRA pull). |
| 6 | **Acknowledgement and intellectual credit** | 🔶 Partial | `originating_lab`, `submitting_lab`, `data_generator`, `citation_request` fields in schema; auto-Acknowledgments block at export is missing — `B-GISAID-1`. |
| 7 | **Equity in benefits** | 🔶 Partial | DUO codes support equitable-access framing; per-sample data-use-terms UI not wired (`B-PPX-1`); benefits-sharing framework doc missing (`B-GOV-1`). |
| 8 | **As open as possible and as closed as necessary** | 🔶 Partial | OPEN/RESTRICTED dual-track supported in schema (`data_use_terms` enum); UI radio button at submission not wired — `B-PPX-1`. |
| 9 | **Interoperability and relevance for decision-makers** | ✅ Met | Full ontology anchoring; TOSTADAS NCBI broker; planned LAPIS-compat; hAMRonization output (`B-NCBI-2`); NCBI BigQuery JOIN (`B-NCBI-1`). |
| 10 | **Trustworthiness and ease of use** | 🔶 Partial | Six ingest paths with low-friction options (drag-and-drop, CSV batch, Globus deposit-first); content-sniffing prevents silent failure; trust portal doc missing — `B-SOLU-3`. |
| 11 | **Transparency** | 🔶 Partial | Public technical docs (`spec.md`, `architecture.md`); audit log; governance / board / COI docs missing — `B-GOV-1`. |
| 12 | **Consistency with applicable law and ethical regulations** | 🔶 Partial | GCP DLP filters PHI/PII at ingest; data-residency commitments are operator-controlled (per `min_sharing_level_for_federation`); jurisdiction & data-residency doc missing — `B-GOV-1`. |
| 13 | **Compliance and enforcement** | 🔶 Partial | Audit log + immutable provenance support compliance investigation; user code-of-practice + grievance procedure docs missing — `B-GOV-1`. |

**Matrix summary:** 4 ✅ Met, 8 🔶 Partial, 0 ❌ Gap, 1 ➖ N/A. Same pattern as 1.1 — `B-GOV-1` closes the bulk of governance-doc gaps simultaneously.

### 1.3 GA4GH standards alignment

Source: Global Alliance for Genomics & Health (GA4GH) standards portfolio.

| Standard | Function | JACKPOT status | Evidence (one line) |
|---|---|---|---|
| **DUO (Data Use Ontology)** | Machine-readable data-use restrictions | ✅ Met | `samples.data_use_terms` field + `DataUseTermsEnum`; per-dataset DUO codes; UI radio at submission pending (`B-PPX-1`). |
| **DRS (Data Repository Service)** | Standardized data-access URIs across repositories | 🔶 Partial | `drs://` URI scheme accepted in `fastq_r1_uri` / `fastq_r2_uri`; DRS endpoint itself not implemented (Year 2 — interoperability with Terra, AnVIL). |
| **Phenopackets** | Standardized clinical phenotype + disease + biosample model | 🔶 Partial | `HumanSample` maps to Phenopacket Individual + Disease elements per schema (slot URIs); native Phenopacket export not implemented. |
| **Beacon** | Federated query protocol for genomic data discovery | ❌ Gap | Not addressed; the closest analog is JACKPOT's planned Federation Level 1 query API (see Section 4 below). |
| **htsget** | Streaming protocol for genomic data | ➖ N/A | JACKPOT serves files via signed URLs and DRS-compatible URIs; htsget streaming layer is out of scope for now. |
| **CRAM/BAM/VCF + index conventions** | Standard file formats | ✅ Met | `file_detector.py` content-sniffing handles BGZF (used by BAM/CRAM), gzip, plain text; BCF/VCF/BAM/CRAM in `_ROADMAP_TYPES`. |
| **Workflow Execution Service (WES)** | Standardized pipeline execution API | ❌ Gap | JACKPOT uses Nextflow + GCP Batch directly, not a WES-compliant API; WES adapter would be a multi-week piece of work. |
| **GA4GH Service Info** | Standardized service-discovery metadata | ❌ Gap | JACKPOT's `/health` endpoint is JACKPOT-native, not GA4GH Service Info-compliant; one session of work to add the spec'd fields. |

**Matrix summary:** 2 ✅ Met, 2 🔶 Partial, 3 ❌ Gap, 1 ➖ N/A. Beacon and WES are the two consequential gaps; both are Year 2+. Service Info is a small win available any time.

### 1.4 CDC North Star Architecture (STLT alignment)

Source: *Blueprint for Success: CDC's North Star Architecture* (`North_Star_CDCSummit_092723.pdf`). Five core principles + ecosystem components.

| Element | Description | JACKPOT status | Evidence (one line) |
|---|---|---|---|
| **Principle 1: Reduce burden and friction** | Flexible, standardized, replicable tools | ✅ Met | LinkML schema generates DataHarmonizer templates; six low-friction ingest paths; tier-aware validation accepts partial submissions; `jackpot init` for one-command operator bootstrap. |
| **Principle 2: Increase interoperability** | Secure cloud environments + standards | ✅ Met | Full ontology stack (PHA4GE/GenEpiO/MIxS/ENVO/GA4GH/LOINC/SNOMED/ELR/NWSS); GCP-native; standards-based brokering (TOSTADAS, planned LAPIS); HL7 v2.5.1 ELR mappings on `HumanSample`. |
| **Principle 3: Remove siloes** | End-to-end public health approaches | 🔶 Partial | One Health sectors in single platform; surveillance_relevant computation routes reportable organisms to ADHS-style oversight; cross-org dataset sharing model. STLT-CDC ReportStream / DEX integration not implemented. |
| **Principle 4: Get relevant data quickly** | Range of support to STLT partners | 🔶 Partial | Tier-aware ingest enables immediate value from PRELIMINARY data; planned NCBI Pathogen Detection BigQuery JOIN (`B-NCBI-1`) for cross-platform context; CDC ReportStream / AIMS direct integration not implemented. |
| **Principle 5: Be responsive** | User-centric design and development | 🔶 Partial | Six ingest paths optimize for different operator workflows; Streamlit UI iterates quickly; Lab Director / Platform Admin / Governance Board roles map to STLT realities; user-research framework not formalized. |
| **Component: STLT Workspaces (private)** | STLT operator-controlled environments | ✅ Met | Operator-agnostic deployment model — STLT operators get their own JACKPOT instance with full data sovereignty; `min_sharing_level_for_federation` controls outbound flow. |
| **Component: Shared Analytics Platform** | Cross-STLT analytics | 🔶 Partial | JACKPOT federation Level 2 (hub push) is the analog; `federated_instances` table; planned BigQuery analytics layer. |
| **Component: PH Digital Marketplace** | Modular tools and turn-key applications | 🔶 Partial | Pipeline zoo + BYOP; modular operator-agnostic codebase invites integrators; `jackpot-cli` SDK; not yet packaged as a marketplace. |
| **Component: Data Transport / DEX** | Bi-directional public-health data movement by CDC and partners | ❌ Gap | JACKPOT can broker to NCBI (TOSTADAS) and GISAID (EpiCoV) but no native CDC ReportStream / DEX / AIMS integration. |
| **Component: Enterprise Data Catalog** | Findable, FAIR-aligned dataset catalog | 🔶 Partial | Sample search; planned dataset catalog (Month 2); FAIR F3 (metadata indexed in searchable resource) on roadmap. |

**Matrix summary:** 3 ✅ Met, 6 🔶 Partial, 1 ❌ Gap, 0 ➖ N/A. The CDC ReportStream / DEX / AIMS gap is the consequential one for any STLT operator considering JACKPOT.

### 1.5 FAIR + CARE principles

FAIR source: Wilkinson et al., *Sci. Data* 2016. CARE source: Carroll et al., *Data Science Journal* 2020. The FAIR table here is a refresh of the FAIR scorecard already in `docs/architecture.md` v6.0 §18 (Standards and FAIR compliance, post-Cluster-A merge).

#### 1.5.1 FAIR

| Principle | JACKPOT status | Evidence (one line) |
|---|---|---|
| **F1 — Globally unique, persistent identifiers** | 🔶 Partial | `sample_id` is the identifier; `JKPT-` prefixed cluster accessions planned (`B-NCBI-3`); persistent URI pattern in schema. |
| **F2 — Rich metadata** | ✅ Met | LinkML v4.4 schema with full ontology anchoring; tier-aware validation surfaces metadata gaps. |
| **F3 — Metadata indexed in searchable resource** | 🔶 Partial | Sample search router; planned dataset catalog (Month 2); LAPIS-compat (Year 2). |
| **F4 — Identifier in metadata** | ✅ Met | `sample_id` is the identifier and is required on every record. |
| **A1 — Retrievable by identifier via open protocol** | 🔶 Partial | REST API + GCS signed URLs + DRS URIs; full DRS endpoint Year 2. |
| **A1.2 — Authentication and authorization** | ✅ Met | Google OAuth + JWT; six-role RBAC; per-sample access cascade; personal API tokens. |
| **A2 — Metadata accessible after data deletion** | 🔶 Partial | Tombstone records (immutable, permanent) in schema; staged deletion lifecycle; pipeline_results preserved after sample deletion. |
| **I1 — Machine-readable knowledge representation** | ❌ Gap | JSON-LD endpoint planned (Month 3); LinkML supports `gen-jsonld` for serialization. |
| **I2 — FAIR vocabularies** | ✅ Met | GenEpiO, NCBI BioSample, MIxS, ENVO, LOINC, SNOMED CT, GA4GH DUO/DRS — all anchored in schema slot URIs. |
| **I3 — Qualified cross-references** | 🔶 Partial | `sample_associations` table for cross-sample linkage; `case_id` + `case_source_system` for clinical linkage; cross-references to NCBI/GISAID accessions. |
| **R1 — Richly described** | ✅ Met | Every schema field has description, range, validation rule, ontology anchor where applicable. |
| **R1.1 — Data usage license** | 🔶 Partial | DUO codes per dataset; UI radio at submission pending (`B-PPX-1`). |
| **R1.2 — Detailed provenance** | 🔶 Partial | `PipelineProvenance` + `pipeline_runs`; gap on input-data version tracking, execution-environment snapshot — `B-FDP-1`. |
| **R1.3 — Community standards** | ✅ Met | PHA4GE, MIxS, NWSS, TOSTADAS, hAMRonization (in-flight). |

**FAIR matrix summary:** 7 ✅ Met, 6 🔶 Partial, 1 ❌ Gap. JSON-LD endpoint (I1) is the only outright gap.

#### 1.5.2 CARE (Indigenous data principles)

The CARE principles (Collective benefit, Authority to control, Responsibility, Ethics) are increasingly cited alongside FAIR for genomic data, particularly when Indigenous or LMIC populations are sampled. JACKPOT's One Health scope means this is genuinely relevant.

| Principle | JACKPOT status | Evidence (one line) |
|---|---|---|
| **C — Collective benefit** | 🔶 Partial | DUO codes support collective-benefit framing; benefits-sharing framework doc missing — `B-GOV-1`. Per-sample OPEN/RESTRICTED at submission UI not wired — `B-PPX-1`. |
| **A — Authority to control** | 🔶 Partial | Per-org policies (`has_oversight_access`, `default_sharing_level`); `min_sharing_level_for_federation`; sample-level sharing controls; data-residency commitments are operator-controlled but not formally documented — `B-GOV-1`. |
| **R — Responsibility** | 🔶 Partial | Audit log; access request workflow with passive 90-day approval; user code-of-practice doc missing — `B-GOV-1`. |
| **E — Ethics** | 🔶 Partial | DLP scanning; SRA Human Scrubber; sharing levels; ethical-regulations consistency commitment doc missing — `B-GOV-1`. |

**CARE matrix summary:** 0 ✅, 4 🔶, 0 ❌. All four resolve via `B-GOV-1` plus `B-PPX-1`.

---

## 2. WHO/IPSN essential attributes — detailed prose for partials and gaps

This section gives prose detail only for the eight 🔶 Partial rows in matrix 1.1. The four ✅ Met rows are self-explanatory from the matrix; their evidence is concrete enough not to need elaboration. The detailed prose below is operator-facing — it describes the gap, the fix, and what compliance actually looks like once the fix lands.

### 2.1 Attribute 1 — Governance (🔶 Partial)

**WHO requirement (paraphrased):** The platform has a governance structure with publicly available terms of reference; a multi-stakeholder body oversees decisions; conflict-of-interest policies are in place; the platform is independent from any single state actor.

**JACKPOT current state.** Single-owner project (Midnight-Oil-Innovation, the maintainer Glen). AGPL-3.0 license positions the project against captured-by-a-single-operator outcomes. No published charter, COI, or advisory-board roster yet. Federation architecture (3-level) is the technical answer to "no single operator controls the data," but the governance scaffolding around the project itself is documentation work that hasn't shipped.

**Fix path.** `B-GOV-1` — create `governance/` directory with seven docs as designed in `docs/platform_landscape.md` Section 13.1c (re-stated here for completeness):

- `charter.md` — what JACKPOT is, what it's for, what it commits to
- `coi-policy.md` — disclosure rules for the maintainer, future contributors, and any advisory board members
- `jurisdiction-and-data-residency.md` — where Midnight-Oil-Innovation is incorporated; what laws apply to the project itself; commitments to operator data residency
- `benefits-sharing-framework.md` — how operators using JACKPOT share benefits (citations, collaborations, data-back-to-source)
- `access-grievance-procedure.md` — how to raise concerns about access decisions
- `platform-shutdown-data-portability-plan.md` — what happens if the maintainer stops maintaining JACKPOT (this is the document that distinguishes a credible public-good project from vaporware)
- `advisory-board.md` — forward-looking; how the project will add governance plurality as it grows

**What compliance looks like once fixed.** Public docs at `Midnight-Oil-Innovation/jackpot/governance/`; cited from the README; explicit advisory-board roster (even if it starts as "soliciting members"); committed conflict-of-interest disclosures.

### 2.2 Attribute 2 — Transparency (🔶 Partial)

**WHO requirement.** Terms and conditions are publicly available; governance procedures (boards, committees, terms of reference) are publicly available; the platform's functioning aligns with stated principles.

**JACKPOT current state.** Public technical docs (`spec.md`, `architecture.md`, `assessment.md`, this document); AGPL-3.0 license; audit log on every state change. The transparency *of the technical design* is strong; the transparency *of the governance* is weak because the governance docs don't yet exist.

**Fix path.** Same as 2.1 — `B-GOV-1` covers most of it. Additionally: ensure the README links prominently to the `governance/` directory; consider a top-level `/about` or `/governance` page on any deployed JACKPOT instance that surfaces operator-specific governance metadata.

### 2.3 Attribute 7 — Data Provenance (🔶 Partial)

**WHO requirement.** Provenance metadata is captured for every data submission and analysis result; provenance is queryable; data lineage from raw sample through final analysis is preserved.

**JACKPOT current state.** Strong on the *event-trail* side: audit log on every state change with `before`, `after`, `actor_id`, `metadata`; immutable append-only `pipeline_results` so every pipeline run is a queryable historical record. Persistent identifiers (`sample_id`) make samples traceable. *Weak on the deeper provenance side*: input-data version tracking is partial (the `input_sample_ids` field on pipeline runs captures *which* samples but not their *version at the time*); execution-environment snapshot is weak (just GKE pod info, not full container-image-digest + dependency-pinning); parameter immutability is convention-not-enforced.

**Fix path.** `B-FDP-1` — audit JACKPOT's `PipelineProvenance` + `pipeline_runs` against the FAIR Data Pipeline metadata model (per `docs/platform_landscape.md` §5.4.3). Strengthen the schema to close the highest-value gaps:

- Capture `input_sample_versions` alongside `input_sample_ids` (the sample-level audit-log timestamp at the moment the pipeline was launched).
- Capture `container_image_digest` (not just `container_image_tag` — tags are mutable, digests aren't).
- Pin `parameter_snapshot` as immutable JSONB at run-launch time; never updateable.
- Add `host_environment` JSONB (kernel, libc, GCP zone) — nice-to-have for full reproducibility.

**What compliance looks like once fixed.** "Re-run sample SAM-001 through pipeline P at the exact code revision and inputs that ran on 2026-04-15" should be a single SQL-driven query that returns enough metadata to actually reproduce the run.

### 2.4 Attribute 8 — Access (🔶 Partial)

**WHO requirement.** Access policies are clear and machine-readable; data submitters can specify access conditions; users can request access through documented procedures; audit trail of access decisions exists.

**JACKPOT current state.** Sharing levels (PRIVATE/LAB/DISCOVERABLE/PUBLIC) at the sample level + dataset level; `can_access_sample` permission cascade encodes the policy; access request lifecycle with 90-day passive approval is documented and audit-logged. The gap is the *submission-time UX*: the schema supports per-sample data-use-terms (DUO codes + embargo + citation request) but the Streamlit upload page doesn't yet expose these as a radio button or form fields. So submitters can't currently specify access conditions in the easy path.

**Fix path.** `B-PPX-1` — wire the Streamlit upload page to the existing schema fields. Half a session of work; everything else is already in place.

### 2.5 Attribute 10 — Data Use & Benefits Sharing (🔶 Partial)

**WHO requirement.** A user code of practice defines rights and responsibilities; a data licence specifies what users can do; compliance mechanisms are in place; a benefits-sharing framework defines stakeholders and benefit categories.

**JACKPOT current state.** GA4GH DUO codes per dataset (machine-readable license); audit log supports compliance investigation; AGPL-3.0 covers the *code* license. *Missing*: user code of practice (where is it written down?); benefits-sharing framework (how do operators-using-JACKPOT share benefits with originating labs/communities?); auto-Acknowledgments at export time (current state: submitters' `originating_lab` etc. is captured but not auto-emitted on dataset export).

**Fix path.** Three items, all already in the backlog:

- `B-GOV-1` (governance dir) includes `benefits-sharing-framework.md` and the user code of practice.
- `B-PPX-1` activates per-sample data-use-terms at the submission UI.
- `B-GISAID-1` adds auto-Acknowledgments block on dataset export — when a researcher exports a dataset, an attribution block is auto-generated citing originating labs, sample IDs, and submission dates.

### 2.6 Attribute 11 — Analytical & Reporting Capabilities (🔶 Partial)

**WHO requirement.** The platform supports standardized analyses; analytical tools are reproducible; reports are exportable in standard formats; cross-platform comparability is enabled by standardized output formats.

**JACKPOT current state.** Pipeline zoo with 12+ entries (viralrecon, bactopia, mycosnp, tb-profiler, walkercreek, Cecret, Grandeur, fetchngs, mag, taxprofiler, pathogensurveillance, BYOP); Streamlit dashboards; Pangolin + Nextclade auto-run for viral lineage; tb-profiler for TB drug susceptibility. The reporting side is mostly Streamlit-rendered HTML; export to standard formats is per-pipeline. Cross-platform comparability gap is at the AMR-pipeline level: currently each pipeline emits its own AMR format.

**Fix path.** Three items:

- `B-NCBI-2` — hAMRonization output mandate for all AMR pipelines. Standard format; cross-tool comparison becomes free.
- `B-NCBI-1` — NCBI Pathogen Detection BigQuery JOIN. Adds national-cluster outbreak context as a queryable enrichment.
- `B-LAPIS-1` — LAPIS-compatible REST endpoint for viral data. Year 2; lets any GenSpectrum-compatible client query JACKPOT.

### 2.7 Attribute 12 — Sustainability (🔶 Partial)

**WHO requirement.** A funding model is in place; the platform has a multi-year operational plan; key-person risk is mitigated; data and code preservation is guaranteed if the platform is wound down.

**JACKPOT current state.** Open-source AGPL-3.0 with operator-agnostic deployment means the platform can survive any single operator (including Midnight-Oil-Innovation) deciding to walk away; the code stays in the public repo; operators can fork. The active risk is single-maintainer (the assessment doc is explicit about this).

**Fix path.** Two pieces, both partly documentation:

- `B-GOV-1` includes `platform-shutdown-data-portability-plan.md` — this is the document that operationalizes "what happens if the maintainer stops maintaining."
- Multi-year operational plan: not in scope for B-GOV-1 specifically, but can be added as a section in the charter. Funding model is operator-by-operator (each operator funds their own deployment) plus self-funded core development; this can be made explicit.

What compliance looks like long-term: an advisory board with multiple maintainers, a documented succession plan, and a public commitment that all data and code remain accessible if any single contributor exits.

---

## 3. WHO guiding principles — detailed prose for partials and gaps

This section gives prose detail only for the eight 🔶 Partial rows in matrix 1.2. The four ✅ Met rows and the one ➖ N/A row are self-explanatory.

### 3.1 Principle 2 — Collaboration and cooperation (🔶 Partial)

**WHO text.** Promote collaboration and cooperation between submitting laboratories and analyzing scientists; develop local analysis capacity in countries.

**JACKPOT alignment.** Open-source + multi-deployment-target architecture is the technical answer. Federation Level 2-3 (hub-and-spoke / bidirectional) is the cross-instance-collaboration mechanism. Capacity-development for local analysis: Scenario A (self-hosted commodity, laptop case) is the explicit answer for low-infrastructure deployments; the JupyterHub integration plan (Month 3 scope) supports local researcher analysis without needing remote compute.

**Gap.** No published collaboration framework — what does it mean for an operator using JACKPOT to "collaborate" with another operator? `B-GOV-1` (specifically `benefits-sharing-framework.md`) covers this.

### 3.2 Principle 6 — Acknowledgement and intellectual credit (🔶 Partial)

**WHO text.** All contributing labs (and originating labs for clinical samples) should be acknowledged in presentations and publications.

**JACKPOT alignment.** Schema captures the origin chain: `originating_lab`, `submitting_lab`, `data_generator`, plus `citation_request` (free-text suggestion from the submitter for how they want to be cited).

**Gap.** Acknowledgments don't auto-emit at export time. A researcher exporting a dataset gets the data + metadata but no auto-generated attribution block.

**Fix.** `B-GISAID-1` — generate a structured Acknowledgments block at dataset export time, formatted to Nature/PHA4GE recommended citation conventions. Cites each originating lab, sample IDs, submission dates. Lifts directly from GISAID's one credible UX feature (the auto-citation block on every download); decoupled from GISAID's broader governance issues.

### 3.3 Principle 7 — Equity in benefits (🔶 Partial)

**WHO text.** Data sharing should contribute to equitable access to health technologies.

**JACKPOT alignment.** DUO codes support equitable-access framing; the `RU` (Research Use) and `NPU` (Not-for-profit Use) DUO terms can be applied per dataset. `data_use_terms` enum supports equity-related restrictions.

**Gap.** Per-sample data-use-terms not surfaced in the submission UI (`B-PPX-1`); benefits-sharing framework doc missing (`B-GOV-1`).

### 3.4 Principle 8 — As open as possible and as closed as necessary (🔶 Partial)

**WHO text.** Pathogen genome data should be made available in a timely manner on publicly accessible platforms; OPEN access where submitters don't reserve rights, RESTRICTED with embargoed-access where they do.

**JACKPOT alignment.** Schema dual-track is fully supported (`data_use_terms` enum has OPEN, RESTRICTED, EMBARGOED, etc.). Embargo countdown via `embargo_release_date` field. Citation request for RESTRICTED-with-attribution.

**Gap.** Submission UI radio button not wired (`B-PPX-1`).

### 3.5 Principle 10 — Trustworthiness and ease of use (🔶 Partial)

**WHO text.** Develop and sustain trust among providers, platforms, and users; prioritize ease of submission.

**JACKPOT alignment.** Six low-friction ingest paths; tier-aware validation accepts incomplete submissions (no "rejected because metadata not perfect" failure mode); content-sniffing prevents silent file-type failures; staged deletion with 72h fast-path lets users self-correct quickly.

**Gap.** Trust portal — Solu-style explicit documentation of "here's what we do for security, data residency, encryption, audit, deletion lifecycle." Missing.

**Fix.** `B-SOLU-3` — `docs/trust.md` (later promoted to a `trust.jackpot.health` subdomain) documenting security practices, data residency, encryption-at-rest/in-transit, audit log, DLP scanning, scrubber, deletion lifecycle. 4-6 hours of writing. Pairs with `B-GOV-1`.

### 3.6 Principle 11 — Transparency (🔶 Partial)

Same fix as Attribute 2 above (§2.2). `B-GOV-1` is the load-bearing item.

### 3.7 Principle 12 — Consistency with applicable law (🔶 Partial)

**WHO text.** Platform operates consistently with national/international laws, regulations, ethical norms.

**JACKPOT alignment.** GCP DLP filters PHI/PII at ingest (HIPAA-adjacent posture); data-residency commitments enforced by GCP region selection at deployment; per-org `min_sharing_level_for_federation` controls outbound data flow.

**Gap.** No published `jurisdiction-and-data-residency.md` doc explaining: where Midnight-Oil-Innovation is incorporated; what laws apply to the project itself; commitments to operators about data residency; how to handle subpoenas / discovery requests.

**Fix.** `B-GOV-1` covers it.

### 3.8 Principle 13 — Compliance and enforcement (🔶 Partial)

**WHO text.** Compliance mechanisms must exist; sanctions for breaches must be defined; awareness of breach instances supports trustworthiness.

**JACKPOT alignment.** Audit log + immutable provenance support compliance investigation; audit-log-rollover prevention via `execute_write(conn=db)` transactional pattern means audit records can't silently fail.

**Gap.** User code of practice + grievance procedure docs missing.

**Fix.** `B-GOV-1` (`access-grievance-procedure.md` + reference to user code of practice in `charter.md`).

---

## 4. GA4GH standards — detailed prose for partials and gaps

This section covers the four 🔶 Partial / ❌ Gap rows from matrix 1.3 that warrant elaboration.

### 4.1 DRS (Data Repository Service) — 🔶 Partial

**GA4GH spec.** Standardized REST API for retrieving data objects by ID; URI scheme `drs://` for cross-platform references; access methods include signed URLs, byte-range requests, and direct passthrough.

**JACKPOT current state.** `drs://` URI scheme accepted in `fastq_r1_uri` / `fastq_r2_uri`. The scheme is recognized by the resolver; pipeline executors can resolve `drs://` URIs to actual paths at compute-node time.

**Gap.** No JACKPOT-side DRS endpoint that returns DRS-compliant JSON for a JACKPOT-hosted object. So an external GA4GH-DRS-aware client (Terra, AnVIL, Galaxy) can't fetch JACKPOT-hosted data via DRS — they'd need JACKPOT's native API instead.

**Fix path.** Year 2 — implement `GET /ga4gh/drs/v1/objects/{object_id}` returning DRS-compliant JSON; integrate with Cloud Storage signed-URL generation for the actual data fetch. Effort: 1-2 weeks.

### 4.2 Phenopackets — 🔶 Partial

**GA4GH spec.** Phenopackets v2 is a standardized JSON schema for clinical phenotype + disease + biosample + medication + interpretation data. Designed for genomic-medicine interoperability.

**JACKPOT current state.** `HumanSample` schema fields map to Phenopacket Individual + Disease elements per LinkML slot URIs. So semantically the data is there.

**Gap.** No native Phenopacket export endpoint — researchers can't fetch a `HumanSample` as a valid Phenopacket JSON document.

**Fix path.** Year 2 — `GET /api/v1/samples/{id}/phenopacket` returns a Phenopackets v2-compliant JSON for `HumanSample` records. Effort: 1 week given the slot URIs are already mapped. Worth doing alongside the DRS endpoint as a "GA4GH interop sprint."

### 4.3 Beacon — ❌ Gap

**GA4GH spec.** Beacon is a federated query protocol where any participating platform exposes a `/beacon/query` endpoint that responds yes/no (or counts) to "do you have data matching X?" queries — without requiring users to first authenticate or browse the platform.

**JACKPOT current state.** No Beacon endpoint. The closest analog is the planned Federation Level 1 query API (`GET /api/v1/samples/?federation=true`), which is JACKPOT-native rather than Beacon-compliant.

**Fix path.** This is a strategic decision tied to `B-SL-1` (Sample Locator FHIR architecture decision in `docs/platform_landscape.md` §5.3.1). Two paths:

- **Spec-compliant federation** — implement Beacon v2 endpoints alongside FHIR; JACKPOT instances become discoverable from any GA4GH/Beacon-aware tool.
- **JACKPOT-native** — keep the federation API JACKPOT-specific; Beacon support deferred indefinitely.

Recommend: align with the B-SL-1 decision. If FHIR-compatible federation is chosen, add Beacon as a secondary spec-compliance goal in the same architectural sprint.

### 4.4 WES (Workflow Execution Service) — ❌ Gap

**GA4GH spec.** Standardized REST API for submitting and monitoring workflow executions across compute backends.

**JACKPOT current state.** Nextflow + GCP Batch directly. Pipeline launch via `POST /api/v1/pipelines/{name}/launch`; status polling via JACKPOT-native API.

**Fix path.** WES adapter is a multi-week piece of work that would let JACKPOT instances act as a WES backend for tools like Galaxy or Cromwell-WES clients. Year 2+ priority. Worth deferring until federation is real and federated pipeline execution becomes a use case.

### 4.5 GA4GH Service Info — ❌ Gap (small)

**GA4GH spec.** Standardized `/service-info` endpoint returning service identity, type, organization, contact, version, environment.

**JACKPOT current state.** `/health` returns JACKPOT-specific JSON.

**Fix path.** One session — add `GET /ga4gh/service-info` returning the spec'd fields. Cheap win; useful for ecosystem discoverability.

---

## 5. CDC North Star Architecture — detailed prose for partials and gaps

This section covers the six 🔶 Partial rows + one ❌ Gap row from matrix 1.4. The CDC North Star is the framework most relevant to STLT operators (Arizona DHS, similar agencies) considering JACKPOT, so the prose here is operator-facing.

### 5.1 Principle 3 — Remove siloes (🔶 Partial)

**CDC ask.** End-to-end public-health approaches; data flow seamlessly between systems.

**JACKPOT alignment.** Strong on the One-Health-in-one-platform side: human / wildlife / livestock / wastewater / environmental sectors all live in one schema; surveillance_relevant routing surfaces reportable organisms to oversight without silo'ing them in a separate system.

**Gap.** No native integration with CDC ReportStream, AIMS (Association of Public Health Laboratories' messaging), or DEX (Data Exchange Hub). For an STLT operator, this means JACKPOT data flows out via NCBI (TOSTADAS) or GISAID (EpiCoV) but not directly into the CDC pipeline.

**Fix path.** Multi-week piece of work; not on the active backlog yet but worth tracking as a Tier-2 STLT-operator-driven priority. Specifically: CDC ReportStream uses HL7 v2.5.1 ELR for case reporting (which JACKPOT's schema already maps to per `architecture.md` §21). The gap is the *transport layer* — ReportStream uses HTTPS POST with their auth model; building a CDC-aware exporter is feasible.

### 5.2 Principle 4 — Get relevant data quickly (🔶 Partial)

**CDC ask.** Range of support to STLT partners; data available for decision-making in time scales relevant to public-health response.

**JACKPOT alignment.** Tier-aware ingest delivers immediate value from PRELIMINARY data (no waiting for "complete" metadata before pipelines can run); planned NCBI BigQuery JOIN (`B-NCBI-1`) brings cross-platform context in a single query.

**Gap.** No native CDC ReportStream / AIMS direct flow (same as 5.1). Specifically: when JACKPOT detects a surveillance-relevant case, it doesn't auto-flow to CDC's ReportStream pipeline.

**Fix path.** Same as 5.1.

### 5.3 Principle 5 — Be responsive (🔶 Partial)

**CDC ask.** User-centric design and development; iterate based on operator feedback.

**JACKPOT alignment.** Six ingest paths optimize for different operator workflows; Streamlit UI iterates quickly; six-role RBAC maps to STLT realities (Lab Director, Researcher, Domain Specialist, Platform Admin, Org Admin, Visitor).

**Gap.** No formalized user-research framework. STLT-operator feedback collection mechanism is informal.

**Fix path.** Lighter-weight than 5.1/5.2 — establishing a feedback loop with deployed operators is documentation + process work. Tracks naturally with the `governance/` work; could be a section in `charter.md`.

### 5.4 Component — Shared Analytics Platform (🔶 Partial)

**CDC architecture.** A shared analytics environment where multiple STLTs can collaboratively analyze public-health data without each running their own infrastructure.

**JACKPOT alignment.** Federation Level 2 (hub-and-spoke push) is the analog. `federated_instances` table; planned BigQuery analytics layer that periodically pulls from operational DBs for population-level dashboards.

**Gap.** Federation isn't yet operational; BigQuery analytics layer is partial; no cross-STLT shared-analytics deployment exists yet.

**Fix path.** Federation Level 1 implementation is the active work. Once two JACKPOT instances are deployed at different STLTs, the shared-analytics use case becomes real — and the architecture supports it (per `architecture.md` §23). Year 2.

### 5.5 Component — PH Digital Marketplace (🔶 Partial)

**CDC architecture.** Modular tools and turn-key applications that STLTs can adopt without full custom builds.

**JACKPOT alignment.** Pipeline zoo + BYOP (Bring Your Own Pipeline) is the technical analog — STLT operators can adopt the curated catalog or add their own. Operator-agnostic codebase + `jackpot init` makes adoption possible without forking. `jackpot-cli` SDK is the integration surface.

**Gap.** Not yet packaged as a marketplace — there's no `jackpot.health/marketplace` or equivalent listing where operators can browse community-contributed pipelines, dashboards, or schema extensions.

**Fix path.** Long-term; tracks with the broader open-source-community-building work. The technical foundation is in place (pipelines are containers + spec files; dashboards are Streamlit pages; schema extensions are LinkML imports). A marketplace UI is mostly listing-and-discovery work.

### 5.6 Component — Enterprise Data Catalog (🔶 Partial)

**CDC architecture.** Findable, FAIR-aligned dataset catalog spanning STLT-owned and CDC-owned data.

**JACKPOT alignment.** Sample search router; planned dataset catalog (Month 2). Per FAIR scorecard, F3 (metadata indexed in searchable resource) is on the active roadmap.

**Fix path.** This is on the in-flight roadmap (Month 2 work in `spec.md`).

### 5.7 Component — Data Transport / DEX (❌ Gap)

**CDC architecture.** Bi-directional public-health data movement by CDC and partners through standardized APIs.

**JACKPOT alignment.** Outbound: TOSTADAS for NCBI; EpiCoV for GISAID. Inbound: SRA accession import via `POST /api/v1/ingest/accession`. None of these are CDC ReportStream / DEX / AIMS native.

**Fix path.** The single most consequential STLT-operator gap. ReportStream is the most critical piece (it's the live CDC ELR pipeline); AIMS and DEX layer on top. Specifically what JACKPOT needs:

- A `cdc_reportstream` exporter pipeline that periodically pushes surveillance-relevant cases to ReportStream's HTTPS endpoint.
- The ELR mappings already exist in the schema (`organism_name → OBX-5`, `date_collected → OBR-7`, `case_id → PID-3`).
- Auth via ReportStream's account model; data validation per their HL7 v2.5.1 schema.

This is a significant piece of work (multi-week). Suggested backlog item:

```text
[ ] B-CDC-1   Implement CDC ReportStream exporter for STLT operators.
              Periodic push of surveillance-relevant case data formatted
              as HL7 v2.5.1 ELR per ReportStream schema. Auth via
              ReportStream account model. Effort: 3-4 weeks. Phase: Year 2,
              when first STLT operator (e.g. ADHS) deploys.
```

---

## 6. FAIR + CARE — detailed prose for partials and gaps

This section covers only the most consequential partials and the one outright gap from matrix 1.5.

### 6.1 FAIR I1 — Machine-readable knowledge representation (❌ Gap)

**FAIR ask.** Metadata is represented in a machine-readable knowledge representation language (RDF, JSON-LD, OWL).

**JACKPOT current state.** LinkML is the source of truth; LinkML supports `gen-jsonld` for serialization. No JSON-LD endpoint yet exposes JACKPOT records as JSON-LD.

**Fix path.** Month 3 per existing FAIR scorecard. Add `Accept: application/ld+json` content-negotiation on key endpoints (`/api/v1/samples/{id}`, `/api/v1/datasets/{id}`); render via `gen-jsonld`. Effort: 1 session.

### 6.2 FAIR R1.2 — Detailed provenance (🔶 Partial)

Same fix as Attribute 7 in §2.3 above. `B-FDP-1` covers it.

### 6.3 CARE-C — Collective benefit (🔶 Partial)

**CARE ask.** Data ecosystems are designed and function in ways that enable Indigenous Peoples (or, by extension, the originating community) to derive benefit from data.

**JACKPOT alignment.** Schema supports the framing (DUO codes, citation_request, embargo, originating_lab metadata). But the *operationalization* — explicit policies on how operators using JACKPOT must share benefits with originating communities — is documentation work that hasn't shipped.

**Fix.** `B-GOV-1` — specifically `benefits-sharing-framework.md` — should be written with CARE principles in mind, not just FAIR. The two are complementary; FAIR addresses findability/accessibility/interoperability/reusability, CARE addresses the human/community context within which that data movement happens.

### 6.4 CARE-A — Authority to control (🔶 Partial)

Same fix as Attribute 8 in §2.4 above (`B-PPX-1`) plus `B-GOV-1` (`jurisdiction-and-data-residency.md`).

### 6.5 CARE-R — Responsibility (🔶 Partial)

**CARE ask.** Those working with Indigenous data have a responsibility to share how data are used to support self-determination and collective benefit.

**JACKPOT alignment.** Audit log; access request workflow; user code-of-practice doc missing.

**Fix.** `B-GOV-1`.

### 6.6 CARE-E — Ethics (🔶 Partial)

**CARE ask.** Indigenous Peoples' rights and wellbeing should be the primary concern at all stages of the data lifecycle.

**JACKPOT alignment.** Operationalized partly through DLP scanning (PHI/PII protection), Human Scrubber (genomic PII), per-sample access controls. Ethics commitment doc missing.

**Fix.** `B-GOV-1` — explicit commitment in `charter.md` to consistency with FAIR + CARE and with applicable ethical-research norms.

---

## 7. Consolidated action items

This section pulls every backlog item referenced above into one list, deduplicated, with the framework gaps each item closes. Use this as the authoritative input to `todo.md` for governance/standards-alignment work.

```text
[ ] B-GOV-1   Create governance/ directory with charter.md, coi-policy.md,
              jurisdiction-and-data-residency.md,
              benefits-sharing-framework.md,
              access-grievance-procedure.md,
              platform-shutdown-data-portability-plan.md,
              advisory-board.md.
              Modeled on Pathoplexus governance docs.
              Closes WHO/IPSN attributes 1, 2, 10, 12;
              WHO Guiding Principles 2, 7, 8, 11, 12, 13;
              CARE C, A, R, E.
              Effort: 3-5 hours of writing. Phase: P0d.

[ ] B-PPX-1   Adopt per-sample OPEN/RESTRICTED radio button on Streamlit
              upload page. Schema already supports it; just wire UI.
              Closes WHO/IPSN attributes 8, 10;
              WHO Guiding Principles 7, 8;
              CARE A.
              Effort: half a session. Phase: any.

[ ] B-FDP-1   Audit JACKPOT's PipelineProvenance + pipeline_runs against
              the FAIR Data Pipeline metadata model. Strengthen schema
              for input-data version tracking, container-image-digest,
              parameter-snapshot immutability, host_environment.
              Closes WHO/IPSN attribute 7; FAIR R1.2.
              Effort: 1 week audit + 1-2 weeks implementation.
              Phase: when FAIR R1.2 is on deck.

[ ] B-NCBI-2  hAMRonization output mandate for all AMR pipelines in
              the zoo.
              Closes WHO/IPSN attributes 9, 11.
              Effort: 1 session per pipeline.
              Phase: pipeline-zoo work.

[ ] B-NCBI-1  BigQuery JOIN for NCBI Pathogen Detection — surface PDS#
              cluster IDs and MicroBIGG-E AMR results in samples table.
              Closes WHO/IPSN attribute 11; CDC North Star Principle 4.
              Effort: 2 sessions. Phase: post-staging-cutover.

[ ] B-LAPIS-1 Expose LAPIS-compatible REST endpoint for JACKPOT viral
              data.
              Closes WHO/IPSN attributes 9, 11.
              Effort: 1-2 weeks. Phase: Year 2.

[ ] B-GISAID-1 When exporting a dataset, auto-generate a structured
               Acknowledgments block citing each originating lab,
               sample IDs, and submission dates.
               Closes WHO/IPSN attribute 10; WHO Guiding Principle 6.
               Effort: 1-2 sessions. Phase: any.

[ ] B-SOLU-3  Add docs/trust.md (later promoted to trust.jackpot.health
              subdomain) documenting security practices, data residency,
              encryption-at-rest/in-transit, audit log, DLP scanning,
              scrubber, deletion lifecycle.
              Closes WHO Guiding Principle 10.
              Effort: 4-6 hours of writing. Phase: with B-GOV-1.

[ ] B-CDC-1   Implement CDC ReportStream exporter for STLT operators.
              Periodic push of surveillance-relevant case data formatted
              as HL7 v2.5.1 ELR per ReportStream schema.
              Closes CDC North Star Principles 3, 4, Component DEX.
              Effort: 3-4 weeks. Phase: Year 2,
              when first STLT operator deploys.

[ ] B-DRS-1   Implement GA4GH DRS-compliant endpoint
              GET /ga4gh/drs/v1/objects/{object_id}.
              Integrate with Cloud Storage signed-URL generation.
              Closes GA4GH DRS gap; FAIR A1.
              Effort: 1-2 weeks. Phase: Year 2.

[ ] B-PHENO-1 Implement Phenopackets v2 export for HumanSample records:
              GET /api/v1/samples/{id}/phenopacket.
              Closes GA4GH Phenopackets gap.
              Effort: 1 week. Phase: Year 2 (alongside B-DRS-1).

[ ] B-SVCINFO-1 Add GET /ga4gh/service-info endpoint returning standardized
                service identity / type / organization / contact / version.
                Closes GA4GH Service Info gap.
                Effort: 1 session. Phase: any.

[ ] B-JSONLD-1 Add JSON-LD content-negotiation on key endpoints
               (samples, datasets) using LinkML gen-jsonld.
               Closes FAIR I1.
               Effort: 1 session. Phase: Month 3 (matches FAIR scorecard).

[ ] B-NCBI-3  Mint stable JACKPOT cluster accessions (JKPT-prefixed,
              versioned) for any cgMLST/SNP cluster computed by the
              platform. Persist tree representations in newick + JSON.
              Closes FAIR F1 partial.
              Effort: 1 week. Phase: Year 2 (with cgMLST clustering work).

[ ] B-BEACON-1 Decision item: implement GA4GH Beacon v2 endpoint
               alongside Federation Level 1 query API, OR keep
               JACKPOT-native and defer Beacon. Tied to B-SL-1
               architecture decision in docs/platform_landscape.md §5.3.1.
               Closes GA4GH Beacon gap (if implemented).
               Effort: 1 week if implemented. Phase: Year 2.

[ ] B-WES-1   Decision item: implement GA4GH WES adapter for JACKPOT
               pipeline execution. Year 2+ priority; defer until
               federated pipeline execution is a real use case.
               Closes GA4GH WES gap (if implemented).
               Effort: 3-4 weeks if implemented. Phase: Year 2+.
```

---

## 8. Cross-references

For full architectural context behind each alignment claim:

| Topic | Reference |
|---|---|
| JACKPOT data governance and access control | `docs/architecture.md` v6.0 §13 (post-Cluster-A merge) |
| Schema standards mapping (PHA4GE/GenEpiO/etc.) | `docs/architecture.md` v6.0 §18 (post-Cluster-A merge) |
| FAIR scorecard | `docs/architecture.md` v6.0 §18 (post-Cluster-A merge) |
| Federation architecture (3 levels) | `docs/architecture.md` v6.0 §20 + `docs/federation.md` (Cluster C output) |
| Two-PII-gate (scrubber + DLP) | `docs/platform_landscape.md` §10 |
| Pathoplexus governance template | `docs/platform_landscape.md` §16.2 |
| CDST privacy-preserving typing (Year 2 federation primitive) | `docs/platform_landscape.md` §5.5.1 |
| Sample Locator FHIR pattern (Federation Level 1 model) | `docs/platform_landscape.md` §5.3.1 |

---

*End of governance alignment v1.2 (Cluster E cross-reference cleanup). Pairs with `docs/platform_landscape.md` (the renamed-and-Cluster-E-updated platform landscape doc) and `docs/deploy/gcp.md` (the renamed-and-relocated GCP deployment guide).*
