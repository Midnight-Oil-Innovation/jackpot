> **Status:** Reference - comparative landscape of peer platforms.

# JACKPOT Platform Landscape

## Comparative Analysis: What We've Adopted, Why, and What's Next

**Status:** Working session synthesis · 2026-05-09 · v3.1 (Cluster E consistency updates applied 2026-05-16) · supersedes `jackpot_pathoplexus_loculus_overview.md`
**Scope:** Architectural relationship between JACKPOT and the broader pathogen-genomics platform ecosystem — extending the original 9-platform analysis (Loculus/Pathoplexus, GenSpectrum/LAPIS, Pathogenwatch, EnteroBase, NCBI Pathogen Detection, BV-BRC, Solu, RT-MetA, GISAID) to cover an additional ~14 federated analysis frameworks, federated search engines, data-sharing platforms, harmonization tools, and decentralized/privacy-preserving toolkits surfaced from the open-source landscape. Includes license analysis, code-level comparison of ingest pipelines, JACKPOT adoption decisions to date, and a prioritized "what's next" queue across all categories.

---

## 0. Executive summary

This document supersedes `jackpot_pathoplexus_loculus_overview.md`. The original 9-platform comparative matrix is preserved word-for-word, then extended in two directions:

1. **Categorical reorganization.** Where the previous version treated all peers as one undifferentiated "platform landscape," this version groups the now-23 entries into five categories: Genomic Surveillance Platforms, Federated Analysis Frameworks, Federated Search & Query Engines, Data Sharing & Harmonization Platforms, and Decentralized / Privacy-Preserving Tools. Each category has different design pressures, different relevance to JACKPOT, and different adoption pathways.

2. **Adoption audit + forward queue.** Two new sections (18 and 19) consolidate (a) what JACKPOT has actually adopted from this landscape and why, and (b) what's worth looking at next, ranked by ROI and effort.

Three things changed the strategic picture for JACKPOT in the original session that triggered this analysis, and they remain the load-bearing claims:

1. **JACKPOT is independent and operator-agnostic.** Production code knows nothing about Midnight-Oil-Innovation or any specific operator. Only the `jackpot init` bootstrap step does, and it learns operator names at install time.

2. **The license flipped from Apache 2.0 to AGPL-3.0.** This unlocks direct code adoption from the entire ETH-led / Swiss-public-health Loculus + GenSpectrum + LAPIS + SILO stack, all of which is AGPL-3.0. The "institutional legal review" blocker that previously gated any Loculus code lift has evaporated.

3. **The Loculus stack is the most directly relevant peer.** Loculus is the only other open-source software package designed for multi-operator deployment in the pathogen-genomics space. Pathoplexus is just one Loculus deployment with governance docs. JACKPOT and Loculus solve the same architectural problem with different choices.

The headline recommendations — preserved from the original analysis and still current — are:

- **Adopt the Loculus preprocessing HTTP contract** (`/extract-unprocessed-data` + `/submit-processed-data`) as JACKPOT's pluggability layer. Roughly 200 lines of new code; lets external contributors add organism-specific validators without forking the backend.
- **Lift Loculus's `ingest/` Snakemake workflow** clean-room into `pipelines/insdc-ingest/` for NCBI Datasets-CLI-based import. Replaces JACKPOT's stub `POST /ingest/accession` with a production-quality pipeline.
- **Steal the structured error/warning schema** for `ValidationResult`. Cleaner UI errors with both source-field and target-field references.
- **Federate with NCBI Pathogen Detection on BigQuery** in Month 3. JACKPOT runs on GCP; this is a one-SQL-query integration that adds national-cluster outbreak context for bacterial isolates.
- **Add a `governance/` directory** modeled on Pathoplexus's. Document-level work that satisfies WHO/IPSN attribute 1 (Governance) compliance.
- **Don't replace** JACKPOT's `file_detector.py`, `validator.py`, `dlp_scanner.py`, or the SRA-human-scrubber Nextflow integration. They collectively constitute a *better* ingest pipeline than Loculus's preprocessing for JACKPOT's surveillance-focused operating model.

The newly surfaced (non-genomic-surveillance-platform) tools add three further headline items:

- **Sample Locator (German Biobank Alliance)** is the closest existing implementation of the Level-1 federation pattern in JACKPOT's `spec.md`. Sixteen-plus European biobanks federate biosample metadata search via HL7 FHIR + CQL. Worth studying in detail before JACKPOT's federation layer goes live.
- **CDST (CoDing Sequence Typer)** demonstrates that decentralized, hash-based bacterial typing — non-identifying outputs that interoperate across labs — is achievable with low overhead. This is the privacy-preserving primitive JACKPOT's Year-2 federation needs.
- **Overture** is the second open-source genomic data-sharing platform after Loculus that targets multi-operator deployment. It deserves the same head-to-head depth that Loculus already received in this document, ideally in a follow-up session.

The rest of this document develops each of these in detail and integrates the supporting analysis.

---

## 1. Master comparison matrix

This is the single comparison table for the full landscape. The original document had separate matrices for pathogen scope, architecture, analysis capabilities, standards alignment, and governance — those remain in Section 6 below for the 9 surveillance platforms specifically. This top-of-document matrix is intentionally lower-resolution and broader-coverage: every tool in scope, in one place, sortable by category, with JACKPOT's adoption status as a final column.

### 1.1 All 23 tools at a glance

| # | Tool / Platform | Category | Function (one line) | License | Maturity | JACKPOT adoption status |
|---|---|---|---|---|---|---|
| 1 | **Loculus / Pathoplexus** | Genomic Surveillance Platform | Multi-operator pathogen-sequence database; preprocessing-pluggable; ETH/SIB-led | AGPL-3.0 | High | **Adopt patterns** (preprocessing HTTP contract, INSDC ingest, ENA broker, sequence versioning) |
| 2 | **GenSpectrum / LAPIS** | Genomic Surveillance Platform | Read-only viral surveillance dashboards over Loculus + INSDC; SILO Rust query engine | AGPL-3.0 | High | **Adopt selectively** (URL-encoded queries, dashboard-components for Year 2 React; skip SILO) |
| 3 | **Pathogenwatch** | Genomic Surveillance Platform | Bacterial cgMLST/MLST/AMR typing and outbreak visualization; CGPS/Wellcome Sanger | GPL-3.0 / mixed | High | **Adopt selectively** (speciator, mlst, amr-libraries as pipeline-zoo entries; Phylocanvas+Leaflet for Year 2) |
| 4 | **EnteroBase** | Genomic Surveillance Platform | Bacterial cgMLST + HierCC hierarchical clustering; Warwick (Achtman lab) | Academic / restricted | High | **Adopt selectively** (HierCC pattern; daily SRA scan opt-in) |
| 5 | **NCBI Pathogen Detection** | Genomic Surveillance Platform | NIH/NCBI bacterial WGS database; 1.3M+ isolates; on GCP via BigQuery | Public domain (US Gov work) | High | **Highest-ROI integration** (BigQuery JOIN, AMRFinderPlus pull, PDS# cluster system) |
| 6 | **BV-BRC** | Genomic Surveillance Platform | Broad pathogen comparative genomics workbench; UVA/NIAID | MIT (most components) | High | **Adopt patterns** (microservice queue at scale; explicit publish ceremony) |
| 7 | **Solu** | Genomic Surveillance Platform | Commercial closed-source rapid bacterial AMR + outbreak detection; HIPAA tenant isolation | Closed-source (commercial) | Medium | **Adopt patterns** (rapid-triage <5min pipeline; trust portal docs) |
| 8 | **RT-MetA** | Genomic Surveillance Platform | Brazilian IPSN-funded offline-capable untargeted metagenomics | Open (early-stage) | Emerging | **Engage** (collaboration on offline-first mode; untargeted metagenomics) |
| 9 | **GISAID** | Genomic Surveillance Platform | Closed-governance influenza/SARS-CoV-2 sequence sharing; the cautionary tale | Closed-source + DAA | High (deployed) | **Counter-position** (everything JACKPOT exists not to be); adopt only the auto-Acknowledgments pattern |
| 10 | **DataSHIELD / VisualSHIELD** | Federated Analysis Framework | Non-disclosive federated statistical analysis across sites; long-standing biomedical | Open-source (LGPL) | High | **Study** (architectural reference for Year 2 cross-instance aggregate queries) |
| 11 | **VANTAGE6** | Federated Analysis Framework | Federated learning infrastructure; multi-institution cancer-research deployments | Apache 2.0 | High | **Study** (Year 2+ for federated model training) |
| 12 | **MOLGENIS Armadillo** | Federated Analysis Framework | Lightweight DataSHIELD server; production deployments across European biobanks | LGPL-3.0 | High | **Defer** (only relevant if JACKPOT adopts DataSHIELD wholesale) |
| 13 | **LIT-FED-SEARCH** | Federated Search & Query Engine | OpenSearch-based federated biomedical repository search engine | Open-source | Emerging | **Pattern reference** (less mature than Sample Locator; secondary) |
| 14 | **Sample Locator (German Biobank Alliance)** | Federated Search & Query Engine | Real-time federated biosample metadata search; HL7 FHIR + CQL across 16+ biobanks | Open-source | High | **Highest-priority study** (closest existing model for JACKPOT Federation Level 1) |
| 15 | **Federated GMQL** | Federated Search & Query Engine | Federated genomic dataset query processing; auto-distributed computation | Open-source | Medium | **Pattern reference** (genomic-query-specific; may inform LAPIS-compat work) |
| 16 | **COMBAT-TB-NeoDB** | Federated Search & Query Engine | Graph-based integration for federated TB-genomics queries | Open-source | Medium | **Defer** (narrow domain — TB-specific) |
| 17 | **Cumulus** | Data Sharing & Harmonization Platform | FHIR-based federated EHR sharing; only aggregate data leaves institution | Open-source (Apache 2.0) | Medium | **Study** (when JACKPOT integrates clinical EHR linkage; FHIR pattern relevant) |
| 18 | **Overture** | Data Sharing & Harmonization Platform | Modular open-source genomics data platform; OICR-led | GPL-3.0 / mixed | Medium | **Highest-priority head-to-head** (alternative to Loculus; same multi-operator design space) |
| 19 | **FAIR Data Pipeline** | Data Sharing & Harmonization Platform | Provenance-driven scientific data management; traceable workflows | Open-source | Medium | **Study** (informs FAIR R1.2 detailed-provenance roadmap item) |
| 20 | **DataHarmonizer (Mpox package)** | Data Sharing & Harmonization Platform | Ontology-based pathogen metadata curation; PHA4GE-aligned templates | MIT | High | **Already adopted** (DataHarmonizer is JACKPOT's ingest UI; Mpox package is a worked example) |
| 21 | **CDST (CoDing Sequence Typer)** | Decentralized / Privacy-Preserving | Decentralized hash-based bacterial typing; non-identifying outputs interoperable across labs | Open-source | Emerging | **Highest-priority adopt** (drop-in primitive for federated bacterial outbreak detection) |
| 22 | **Alembic** | Decentralized / Privacy-Preserving | AI/NLP-driven structuring of heterogeneous biological metadata | Open-source | Emerging | **Defer** (potentially useful for legacy spreadsheet ingest; not on critical path) |
| 23 | **gcPathogen** | Vendor | gcPathogen (NMDC/CAS) static reference assets as pipeline-zoo inputs — downloadable cgMLST schema files (112 species) + ARG/VF/MGE reference sets | UNVERIFIED (download-bundle terms; chewBBACA GPL-3.0; CARD/VFDB own terms) | High | Scope: known-bacterial-isolate characterization only, not the METAGENE-1/DeepSVDD unknown core. Static NCBI-derived data only; do NOT call the nmdc.cn API from production (PRC-hosted: supply-chain/compliance liability under DARPA/BARDA/NSF posture + availability SPOF). Available to download:https://nmdc.cn/gcpathogen (NAR 2024, doi:10.1093/nar/gkad875); mirror locally, pin snapshot version. |
| 24 | **JACKPOT** *(reference row)* | Genomic Surveillance Platform (operator-agnostic) | Multi-deployment-target pathogen genomics platform with two-PII-gate ingest, tier-aware validation, four ingest endpoints, three-level federation; AGPL-3.0 | AGPL-3.0 | Active development | n/a — *this is JACKPOT* |

**How to read this table.** The "JACKPOT adoption status" column collapses three different relationships:

- **Adopt** — direct code or pattern adoption is in JACKPOT's roadmap (`todo.md` B-XXX items reference these).
- **Study** — the platform is an architectural reference; JACKPOT may converge toward similar patterns but no specific code-lift is planned.
- **Defer / Pattern reference** — surfaced for completeness; not on the critical path.
- **Counter-position** — JACKPOT explicitly exists in opposition to this approach (only GISAID).
- **Engage** — collaboration / partnership is the right shape, not adoption (RT-MetA).

The tools in rows 1–9 (Genomic Surveillance Platforms) are covered in depth in Section 6 below — those tables stay as the original document had them. Tools in rows 10–22 (the new categories) are detailed in subsections 5.2–5.5.

### 1.2 Capability presence by category

A second view of the same data, focused on what each tool actually does (not what JACKPOT wants from it). Helps when the question is "who else does X?"

| Capability | Genomic Surveillance Platforms | Federated Analysis Frameworks | Federated Search & Query Engines | Data Sharing & Harmonization Platforms | Decentralized / Privacy-Preserving Tools |
|---|---|---|---|---|---|
| **Sample-level data storage** | ✅ all 9 | ❌ — analyzes data in place | ❌ — searches metadata only | ✅ Cumulus (aggregate), Overture (full), DataHarmonizer (export-format) | ❌ — emits hashes/typings only |
| **Whole-genome sequencing pipelines** | ✅ Loculus, Pathogenwatch, EnteroBase, NCBI PD, BV-BRC, Solu, RT-MetA, JACKPOT | ❌ | ❌ | ❌ | CDST (typing only) |
| **Cross-site federated computation** | ⚠️ Loculus group model is the closest | ✅ DataSHIELD, VANTAGE6, MOLGENIS Armadillo | ✅ Federated GMQL, Sample Locator | ⚠️ Cumulus (aggregate-only) | ✅ CDST (hash exchange) |
| **Distributed metadata search** | Mostly local-only | ❌ | ✅ all 4 | ⚠️ Overture (multi-portal) | ❌ |
| **Privacy-preserving primitives** | ⚠️ JACKPOT (DLP + scrubber); others mostly absent | ✅ all 3 | ⚠️ varies | ⚠️ Cumulus aggregation, FAIR provenance | ✅ CDST hash typings |
| **Pathogen-genomics-specific** | ✅ all 9 | ❌ — domain-agnostic | ⚠️ COMBAT-TB-NeoDB only | ⚠️ DataHarmonizer (yes), others domain-agnostic | ✅ CDST |
| **AGPL-3.0 license alignment** | ✅ Loculus, GenSpectrum, JACKPOT | ❌ — mostly LGPL/Apache | ❌ — mostly Apache/MIT | ⚠️ Overture is GPL-3 | ❌ |
| **Production-deployed at scale** | ✅ NCBI PD (1.3M+ isolates), Pathogenwatch, GISAID, BV-BRC | ✅ DataSHIELD, VANTAGE6, MOLGENIS | ✅ Sample Locator (16+ biobanks) | ⚠️ Overture (varies by deployment) | ⚠️ CDST emerging |
| **Active multi-operator design** | ✅ Loculus, JACKPOT (others single-operator) | ✅ all 3 — that's the point | ✅ all 4 | ✅ Overture, Cumulus | ✅ CDST |

**Key takeaway from this view.** Five of the six "Active multi-operator design" rows in the existing surveillance-platform column are non-JACKPOT (Loculus only). But adding the four new categories surfaces 12 additional multi-operator-by-design tools, all of which are stronger reference points for JACKPOT's federation roadmap than anything in the original 9-platform set. **The original analysis under-weighted federated-analysis and federated-search infrastructure because it was scoped to surveillance platforms.** That blind spot is what the rest of Section 5 (and the new Section 19 priority queue) closes.

---

## 2. The JACKPOT pivot (context for everything that follows)

### 2.1 Independence


### 2.2 Multi-deployment-target by design

Where JACKPOT was previously GCP-only (single-deployment-target architecture), it's now meant to be deployable across four install scenarios (per the May 2026 Cluster A architecture merge), with federation, multi-tenancy, and Indigenous data sovereignty as runtime configurations layered on top:

| Scenario | Target | Status |
|---|---|---|
| **A** | Self-hosted commodity infrastructure (laptop through agency datacenter; ephemeral or persistent; single-lab, multi-lab, or multi-org) | First priority — designed in P0e |
| **B** | HPC (Apptainer + Slurm + institutional storage + LDAP/SAML) | After A |
| **C** | Single-org cloud (GKE/EKS/AKS, cloud-native) | After A |
| **D** | CI / e2e test harness | Covered by test-arch decisions |

Federation membership, hosted-SaaS multi-org tenancy, and Indigenous data sovereignty are runtime configurations applied to scenarios A/B/C — not separate install scenarios. See `docs/architecture.md` v6.0 §3 for scenario detail and §22 for the sovereignty-as-runtime-policy framing.

The architectural rule that drives all four (and the runtime configurations layered on top):

> Production code knows nothing about Midnight-Oil-Innovation, or any specific operator. Only the operator-bootstrap step does, and it learns those names at install time.

This is encoded as a smart-mode `jackpot init` CLI with three required prompts (`JACKPOT_ORG_NAME`, `JACKPOT_LAB_NAME`, `JACKPOT_ADMIN_EMAIL`) and sensible defaults for everything else.

### 2.3 License: AGPL-3.0

The decision to use AGPL-3.0 (over Apache 2.0 or MIT) is the most consequential choice in this session for the Loculus relationship. Section 5 unpacks the rationale.

### 2.4 Phasing

```text
NEXT (cleanup completion):
  Phase 6.1 → 11    Cosmetic genericization of operator-specific values

THEN (architectural rework):
  P0d               Monorepo migration to Midnight-Oil-Innovation/jackpot
  P0e               Install/CLI architecture (jackpot init, bootstrap layer)

THEN (continuing pivot roadmap):
  P0b               Schema v5.0 (instances/tenants/federated_peers tables)
  P0c               Multi-tenancy middleware
  P1–P5             Operator-type configurability, federation, governance,
                    reference deployments, new-needs integration
```

Most adoption recommendations in this document slot in either at P0d (monorepo time, when new directories like `pipelines/insdc-ingest/` and `governance/` get created) or post-P0e (when the install layer is real and federation becomes plausible).

---

## 3. The Loculus / Pathoplexus relationship

Two facts that shape everything:

### 3.1 Loculus is the software, Pathoplexus is *one* deployment

Loculus is a general-purpose software package for running pathogen-sequence databases, designed to be deployed by anyone — small public-health labs, consortia, or international databases. Pathoplexus is a non-profit consortium running *one specific Loculus instance* focused on viral surveillance. GenSpectrum runs another instance for influenza/RSV data.

The `pathoplexus/pathoplexus` GitHub repo is literally an *overlay* over the `loculus-project/loculus` monorepo:

> This repository is an overlay over the loculus monorepo. One can imagine this as the monorepo folder within this repository being copied on top of the loculus monorepo. Then the website image is built. Pathoplexus-specific files for the website are inherited from Loculus by default; bringing a file into scope means removing it from `monorepo/.gitignore`.

This pattern (configuration overlay on shared software) is the structural model for any future JACKPOT deployment by other operators.

### 3.2 The Loculus stack is uniformly AGPL-3.0

| Repository | License |
|---|---|
| `loculus-project/loculus` | **AGPL-3.0** |
| `GenSpectrum/LAPIS` | **AGPL-3.0** |
| `GenSpectrum/LAPIS-SILO` (Rust query engine) | **AGPL-3.0** |
| `GenSpectrum/dashboard-components` (embeddable widgets) | **AGPL-3.0** |
| `GenSpectrum/cov-spectrum-website` | GPL-3.0 |

This is no accident — the entire ETH/SIB/European public-health pathogen-genomics community has converged on strong copyleft. With JACKPOT now also AGPL-3.0, JACKPOT joins this license-compatible cluster, and direct code adoption becomes frictionless.

---

## 4. Why AGPL-3.0 (and not Apache 2.0 or MIT)

The license choice is strategic, not legal. **Funders rarely mandate which OSI-approved license to use.** What they mandate is *open access* (publications, sometimes data, sometimes software). The license patterns observed across the peer landscape are cultural, not contractual.

### 4.1 What AGPL closes that GPL and Apache/MIT don't

| License | If you modify and ship a binary | If you modify and run as SaaS | If you embed in proprietary product |
|---|---|---|---|
| **MIT / Apache 2.0** | No obligation to share | No obligation | Free to do |
| **GPL-3.0** | Must publish modifications | **Loophole** — no obligation | Must publish if combined |
| **AGPL-3.0** | Must publish | **Closed** — must publish | Must publish if combined |

The decisive feature is **AGPL §13**: network access counts as distribution. If you fork an AGPL project and run it as a closed SaaS, you must publish your modifications. With GPL or any permissive license, you don't — that's the "ASP loophole" that AGPL was specifically designed to plug.

### 4.2 Why this matters for pathogen genomics infrastructure

Pathogen sequence databases are fundamentally network services. Every other copyleft license (GPL, LGPL) was written before SaaS existed. For a project whose entire deployment model is "run an instance, serve users over HTTPS," GPL would let any well-resourced operator take the code, add proprietary outbreak-detection features, run it as a closed service, and never give anything back.

**That's literally the GISAID story.** Closed governance over open contributors' data, no accountability. The Loculus AGPL choice is the legal-mechanism encoding of "we are not building another GISAID."

### 4.3 Funder license expectations — the actual answer

#### Funders that mandate open access but *not* a specific software license

- **Wellcome Trust** — CC BY 4.0 for publications and data; for software, "open license" without specifying which. Pathogenwatch is GPL-3.0 not because Wellcome required it but because CGPS chose it.
- **Gates Foundation** — open access via Chronos / Gates Open Research. Software policy is "openly available" without prescriptive licensing.
- **NIH / NIAID / NCBI / NHGRI** — open access for publications; software encouraged to be open. NCBI's own software is essentially public domain (US Government work).
- **BBSRC / UKRI** — open data and open access; software is "encouraged to be open."
- **CDC OAMD** — open access expected; license unspecified.
- **ETH / SIB** — institutional support for open source, no license mandate.

#### Funders that have started preferring AGPL-style copyleft for infrastructure

- **EU Horizon Europe and European Commission** — increasingly recommend EUPL or AGPL for "digital public infrastructure" funded projects. Trend, not yet hard mandate.
- **Some philanthropic foundations** focused on public-good infrastructure (Sloan, certain Open Source Sustainability funders) explicitly prefer copyleft.
- **Digital Public Goods Alliance** (UN-aligned) — endorses any OSI-approved license but tracks copyleft adoption as a "public infrastructure" signal.

#### Funders that effectively prevent strong copyleft

- **DARPA / BARDA / DoD-adjacent** — typically require permissive licenses (Apache 2.0, MIT) so the work can be embedded in classified or commercial defense systems.
- **NIH/NIAID for some grant types** — when the deliverable might be commercialized into a therapeutic/diagnostic, permissive is preferred. BV-BRC's MIT license falls in this category.

### 4.4 The cultural/regional pattern

Putting the dots together explains the cluster JACKPOT is joining:

| Region / funder type | Typical license | Why |
|---|---|---|
| **ETH / Swiss / German / European public-health** (Loculus, GenSpectrum, LAPIS) | **AGPL-3.0** | Strong "digital public infrastructure" ethos; explicit anti-capture stance; influenced by EU sovereignty discourse |
| **UK Wellcome / Sanger** (Pathogenwatch) | GPL-3.0 | Copyleft-aligned but pre-AGPL-default era |
| **US NIH / NIAID** (BV-BRC) | **MIT** | Permissive default for embeddability in commercial diagnostics + therapeutics |
| **US NCBI / NLM** (Pathogen Detection) | Public domain | Required for US Government works |
| **VC-backed commercial** (Solu) | Closed-source | Standard commercial protection |
| **Closed national-controlled** (GISAID) | Closed-source + DAA | Defensive moat for the operator |

JACKPOT under AGPL-3.0 sits in the European-public-health cluster. This is the right philosophical home for a pathogen-genomics platform with a "public infrastructure" intent.

### 4.5 Implications for JACKPOT

The standard scary stories about AGPL almost all come from a *commercial* mindset (Google bans AGPL internally for proprietary-IP reasons that don't transfer to public-good projects). For JACKPOT specifically:

1. **Internal use is fine.** AGPL §13 only triggers when users *outside* your organization access the modified software over the network. Single-laptop and internal-org use don't trigger §13 obligations.
2. **Public-facing JACKPOT triggers §13.** Once external researchers log in, modifications must be published. That's *aligned with the public-good ethos* of the project anyway.
3. **No commercial conflict of interest.** JACKPOT isn't trying to be a closed product.
4. **Linking/embedding constraints.** JACKPOT's existing third-party dependencies (FastAPI, SQLAlchemy, Pydantic, etc.) are all AGPL-compatible. The only friction would be embedding JACKPOT code into proprietary downstream tools, which isn't a relevant use case.

The single biggest practical implication: **direct code adoption from Loculus is now unblocked.** Section 12 develops this in detail.

---

## 5. Platform & tool landscape

Section 6 is the heart of the comparative analysis. It's split into five categorical subsections covering the full now-23-tool landscape:

- **5.1 Genomic Surveillance Platforms** — the original 9-platform analysis from the prior version of this document, preserved verbatim. These are direct peers of JACKPOT in the surveillance-platform tier.
- **5.2 Federated Analysis Frameworks** — DataSHIELD, VANTAGE6, MOLGENIS Armadillo. Privacy-preserving cross-site computation patterns. Forward-looking for JACKPOT's federation Levels 2-3.
- **5.3 Federated Search & Query Engines** — LIT-FED-SEARCH, Sample Locator (GBA), Federated GMQL, COMBAT-TB-NeoDB. Cross-repository discovery patterns. Directly relevant to JACKPOT's Federation Level 1.
- **5.4 Data Sharing & Harmonization Platforms** — Cumulus, Overture, FAIR Data Pipeline, DataHarmonizer (Mpox package). Adjacent platforms in the same general design space; Overture in particular deserves a head-to-head with JACKPOT.
- **5.5 Decentralized / Privacy-Preserving Tools** — CDST, Alembic. Specialized primitives for non-identifying outputs.

The original prose framing of the 9-platform analysis follows below as Section 6.1.

### 5.1 Genomic Surveillance Platforms

Before getting into JACKPOT-vs-Loculus specifics, here's where the rest of the pathogen-genomics platform ecosystem sits as of April 2026.

#### 5.1.1 The 9 platforms in scope

| # | Platform | Org | First released | Funded by |
|---|---|---|---|---|
| 1 | **Loculus / Pathoplexus** | Loculus consortium (ETH/SIB/Broad/...) / Pathoplexus non-profit assn | Loculus pre-1.0 (active), PPX Aug 2024 | Pathoplexus: donations + Kanro $500K (2026); Loculus: ETH/SIB |
| 2 | **GenSpectrum + LAPIS** | ETH cEvo group + SIB | LAPIS 2022, GS dashboards 2023 | CDC OAMD, NIH/PDN |
| 3 | **Pathogenwatch** | CGPS / Wellcome Sanger | 2017 | Wellcome, NIHR, others |
| 4 | **EnteroBase** | Warwick (Achtman lab) | 2014 (major 2025 update) | BBSRC, Wellcome |
| 5 | **NCBI Pathogen Detection (on GCP)** | NIH / NCBI / NLM | 2014 (GCP layer 2023) | NIH |
| 6 | **BV-BRC** | UVA Biocomplexity Institute (NIAID) | 2019 (PATRIC+IRD+ViPR merger) | NIH/NIAID |
| 7 | **Solu** | Solu Healthcare Oy (Helsinki) | Product launch 2025 | Lifeline Ventures, $1.08M seed |
| 8 | **RT-MetA** | Brazilian IPSN-funded consortium | 2025 (early-stage) | WHO IPSN catalytic grant |
| 9 | **GISAID** *(incumbent, declining)* | Freunde von GISAID e.V. | 2008 | Various national subscriptions |

#### 5.1.2 Pathogen scope & data model

| Platform | Viral | Bacterial | Fungal | Metagenomics | Wastewater | Per-sample data-use terms | Submission model |
|---|---|---|---|---|---|---|---|
| **Loculus / Pathoplexus** | ✅ (PPX viruses only) | Possible | Possible | ❌ | ❌ | ✅ **OPEN/RESTRICTED dual-track** | Web + API |
| **GenSpectrum** | ✅ (SARS-CoV-2, flu A/B, RSV, H5N1, WNV) | ❌ | ❌ | ❌ | ✅ (via GS-Wastewater) | Read-only consumer | Pulls from Loculus + INSDC |
| **Pathogenwatch** | ✅ (limited; SARS-CoV-2) | ✅ (20+ cgMLST schemes — *Klebsiella*, *Salmonella*, *Neisseria*, *Strep*, *Mtb*, *Vibrio*, more) | ❌ | ❌ | ❌ | ❌ (single tier; private workspace then publish) | Web upload (FASTA/FASTQ) |
| **EnteroBase** | ❌ | ✅ (*Salmonella*, *E. coli*, *Yersinia*, *Clostridioides*, *Streptococcus*, *Helicobacter*, *Vibrio*) | ❌ | ❌ | ❌ | ❌ (auto-public from SRA) | Auto-scrape SRA daily + user upload |
| **NCBI Pathogen Detection** | ❌ | ✅ (1.3M+ isolates) | ❌ | ❌ | ❌ | ❌ (public) | NCBI BioSample/SRA |
| **BV-BRC** | ✅ (broad — flu, dengue, ebola, RSV, etc.) | ✅ (very broad) | Limited | ❌ | ❌ | ⚠️ (private workspace, then publish) | Web + CLI |
| **Solu** | ❌ | ✅ | ✅ | Limited | ❌ | ⚠️ (HIPAA tenant isolation, BAA available) | Browser FASTQ upload |
| **RT-MetA** | ✅ | ✅ | ✅ | ✅ **(untargeted)** | ❌ | N/A (decentralized) | Local — designed offline-capable |
| **GISAID** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ (gated single tier) | Web + EpiCoV upload |
| **JACKPOT** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (`data_use_terms` enum + embargo) | Web + API + Globus + cloud URI + SRA + workspace promotion + CSV |

#### 5.1.3 Architecture stack

| Platform | Backend | Frontend | DB | Search/API | Auth | Deploy | License |
|---|---|---|---|---|---|---|---|
| **Loculus** | **Kotlin** (Spring Boot) | TypeScript + Astro | PostgreSQL + LAPIS + SILO (Rust) | LAPIS REST + GraphQL | **Keycloak** | Helm/Kubernetes | **AGPL-3.0** |
| **GenSpectrum (LAPIS)** | Java/Kotlin | React | SILO (in-mem, Rust) | LAPIS REST | None for read | Docker | **AGPL-3.0** |
| **Pathogenwatch** | **Node.js** | React + Material Design | **MongoDB cluster** | Custom REST | Custom | Docker | OSS (varies) |
| **EnteroBase** | Python + Perl | Custom JS | PostgreSQL | Custom REST | Account-based | On-prem | OSS / academic |
| **NCBI Pathogen Detection** | Python + C++ pipeline | NCBI standard | **BigQuery + GCS** (public layer) | **BigQuery SQL** + FTP | Public read; gcloud for GCP | NIH-managed | Public domain |
| **BV-BRC** | **Perl + Python** microservices | React | Solr + PostgreSQL | REST + CLI (`p3-*` tools) | Account-based | NIAID-managed | MIT |
| **Solu** | Proprietary | Web | Proprietary | Proprietary REST | OAuth + RBAC | SaaS (US/EU regions) | **Closed-source** |
| **RT-MetA** | Python (Nextflow) | Limited UI | SQLite-class | Local | Local | **Offline-first** | Open (early-stage) |
| **GISAID** | Closed | Closed | Closed | Limited/gated | Account + DAA | Closed | **Closed-source** |
| **JACKPOT** | **Python 3.12 / FastAPI** | **Streamlit** (Month 2) → React (Year 2) | PostgreSQL | Custom REST + planned LAPIS-compat | Google OAuth + JWT | Helm/Kubernetes (cloud) + Docker Compose (local) | **AGPL-3.0** |

#### 5.1.4 Analysis capabilities

| Platform | Sequence versioning | Reference alignment | QC | Typing | Phylogeny | AMR | Visualization | Outbreak detection |
|---|---|---|---|---|---|---|---|---|
| **Loculus / Pathoplexus** | ✅ **(every edit tracked)** | ✅ Nextclade default | ✅ | Limited | ❌ (delegated to Nextstrain/GenSpectrum) | ❌ | Basic | ❌ |
| **GenSpectrum** | N/A (read-only) | ✅ | ✅ | ✅ Pangolin/Nextclade | ✅ via Nextstrain | Limited (HA flu) | ✅ embeddable widgets | Mutation prevalence |
| **Pathogenwatch** | ❌ | ✅ Speciator (Mash) | ✅ | ✅ MLST, cgMLST, Genotyphi, NG-MAST, PopPUNK, LIN codes, Kleborate, Kaptive, SISTR | ✅ SNP trees + cgMLST clustering | ✅ | ✅ Phylocanvas + Leaflet maps | ✅ cgMLST nearest-neighbour |
| **EnteroBase** | ❌ | ✅ assembly | ✅ | ✅ MLST, cgMLST, wgMLST, **HierCC** | ✅ ML and SNP trees | Limited | ✅ GrapeTree | ✅ via HierCC |
| **NCBI Pathogen Detection** | ❌ | ✅ | ✅ | ✅ wgMLST + single-linkage | ✅ **PDS# SNP cluster trees** | ✅ **AMRFinderPlus + MicroBIGG-E** | Browser-based | ✅ **PDS# accession system** |
| **BV-BRC** | Limited | ✅ multi-tool | ✅ | ✅ broad | ✅ | ✅ | ✅ | Limited |
| **Solu** | N/A (per-tenant) | ✅ | ✅ | ✅ taxonomy | ✅ | ✅ AMR genes | ✅ in-browser | ✅ **continuous, real-time** |
| **RT-MetA** | N/A | ✅ | ✅ | Untargeted | Limited | Limited | Local | Untargeted detection |
| **GISAID** | Limited | ✅ | ✅ | ✅ Pangolin | Via partners | ❌ | Basic | ❌ |
| **JACKPOT** | Append-only `pipeline_results` (immutable) | Via pipeline zoo | ✅ tier-aware + scrubber + DLP | Pipeline-zoo dependent | Pipeline-zoo dependent | Pipeline-zoo dependent | Streamlit + planned dashboards | Planned (Year 2) |

#### 5.1.5 Standards alignment & brokering

| Platform | INSDC auto-broker | GISAID broker | DataHarmonizer | PHA4GE | hAMRonization | GA4GH (DUO/DRS) | LinkML | LAPIS-compatible |
|---|---|---|---|---|---|---|---|---|
| **Loculus / Pathoplexus** | ✅ **Built-in `ena-submission`** | ❌ | Indirect | ✅ | ❌ | Partial | ❌ | ✅ |
| **GenSpectrum** | N/A | ❌ | N/A | ✅ | ❌ | ❌ | ❌ | ✅ (creator) |
| **Pathogenwatch** | ❌ | ❌ | ❌ | Partial | ❌ | ❌ | ❌ | ❌ |
| **EnteroBase** | Pulls from SRA | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **NCBI Pathogen Detection** | ✅ (it IS NCBI) | ❌ | ❌ | Partial | Indirect (uses AMRFinderPlus) | Partial | ❌ | ❌ |
| **BV-BRC** | Limited | ❌ | ❌ | Partial | Partial | ❌ | ❌ | ❌ |
| **Solu** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **RT-MetA** | TBD | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **GISAID** | ❌ | N/A | Partial | Partial | ❌ | ❌ | ❌ | ❌ |
| **JACKPOT (current)** | Planned (TOSTADAS) | Planned | ✅ | ✅ | Planned | ✅ DUO codes | ✅ **(rare here!)** | ❌ (could add) |

#### 5.1.6 Governance model

| Platform | Open governance docs | Multi-stakeholder board | Auditable change log | Sustainability funding | Independence from any single state |
|---|---|---|---|---|---|
| **Loculus** | ✅ | Maintainer-led | ✅ (git) | Mixed (institutional + grants) | ✅ |
| **Pathoplexus** | ✅ **Statutes + Values + 5-continent Executive Board** | ✅ | ✅ | Donations + Kanro grant — *fragile* | ✅ |
| **GenSpectrum** | Limited | Academic consortium | ✅ | CDC + NIH | Partial (USG funding) |
| **Pathogenwatch** | Limited | CGPS-internal | ✅ | Wellcome + NIHR | Partial (UK funding) |
| **EnteroBase** | Limited | Academic | ✅ | BBSRC + Wellcome | Partial (UK funding) |
| **NCBI Pathogen Detection** | ✅ public docs | NIH-internal | Limited | Federal appropriation | ❌ (US gov) |
| **BV-BRC** | ✅ public docs | NIAID-internal | Limited | Federal appropriation | ❌ (US gov) |
| **Solu** | ❌ commercial | Company board | Internal | Seed + revenue | ❌ commercial |
| **RT-MetA** | TBD | TBD | TBD | IPSN catalytic grant | ✅ |
| **GISAID** | ❌ **opaque** | Closed | ❌ | Subscriptions | ❌ (controversies) |
| **JACKPOT (current)** | Partial (spec.md only) | Single owner (the maintainer) | ✅ git + audit log | Self-funded / consultancy | ✅ |

The Pathoplexus governance pattern (public Statutes + Values + Executive Board roster + COI policy) is the model for what JACKPOT's `governance/` directory should look like — see Section 13 for details.

---

### 5.2 Federated Analysis Frameworks

These tools enable computation across multiple sites without sharing raw data — a different model from the original 9-platform set, which all assume centralized data storage. Their relevance to JACKPOT is forward-looking: the three-level federation architecture in `docs/architecture.md` v6.0 §20 (query / hub-push / bidirectional) is the consumer for these patterns.

#### 5.2.1 DataSHIELD / VisualSHIELD

**Function.** Privacy-preserving, non-disclosive statistical analysis across distributed datasets. Researchers run R commands against a *facade* — DataSHIELD enforces a non-disclosure policy on every result (e.g. no individual-level data leaks, summary statistics only above a minimum cell-size threshold). VisualSHIELD adds a Shiny-based UI that hides the R complexity for non-statistician users.

**Architecture.** Each contributing site runs a DataSHIELD server (typically Opal or Armadillo — see 5.2.3) holding the local dataset. A central client coordinates analyses, sending pre-defined commands to all sites and assembling non-disclosive aggregates back. Raw data never leaves the contributing site.

**License.** LGPL-3.0 for DataSHIELD core; client R packages permissively licensed. Server backends vary.

**Maturity.** High. Long-standing in clinical and genetic-epidemiology research; production deployments include the EU's GDPR-compliant cohort federations and the BBMRI biobank network. Documented in *Frontiers in Genetics* (Tomasoni 2024) for breast-cancer survival analysis.

**JACKPOT relevance.** **Architectural reference for Year 2 cross-instance aggregate queries.** When two JACKPOT instances need to compute "how many surveillance-relevant Salmonella samples in the last 30 days, by sector, across both labs?" without either side downloading the other's raw `samples` table, DataSHIELD's non-disclosure-policy-on-the-server pattern is the canonical approach. JACKPOT's `min_sharing_level_for_federation` org-level field (per `docs/architecture.md` v6.0 §13) is in the right spirit; DataSHIELD shows how to enforce that on aggregate-query outputs, not just raw row visibility.

**Adoption shape.** Not direct code lift — DataSHIELD assumes Opal or MOLGENIS Armadillo as the data backend (R-driven), not PostgreSQL + FastAPI. But the *non-disclosure-policy-on-aggregate-results* primitive is portable; JACKPOT could implement a Python-side equivalent that runs as part of the federation push job.

**Backlog item:**
```text
[ ] B-DSH-1   Year 2 — implement non-disclosure-policy enforcement on
              federation-aggregate query results, modeled on DataSHIELD's
              minimum-cell-size + summary-only output rules. Prevents
              individual-sample reidentification from federated counts.
              Effort: 1-2 weeks. Phase: Year 2 federation work.
```

#### 5.2.2 VANTAGE6

**Function.** Federated learning infrastructure for secure data exchange. Designed for multi-institution clinical research — most prominently used in cancer genomics consortia. Lets researchers train ML models (and run general computations) across sites without centralizing data.

**Architecture.** Three-tier: a central server coordinates tasks, "node" instances run at each contributing site, and a Python client lets researchers submit "algorithms" (Docker-containerized computations) that get distributed to nodes. Each node runs the algorithm on its local data, returns results to the server which aggregates. Modular — algorithms can be anything from simple counts to gradient updates for federated deep learning.

**License.** Apache 2.0. Multiple server, node, and algorithm-store packages (`vantage6-server`, `vantage6-node`, `vantage6-algorithm-store`).

**Maturity.** High. Production deployments at Maastricht, IKNL (Netherlands Comprehensive Cancer Organization), and several other European cancer-research consortia. Originally published in *AMIA Annual Symposium Proceedings* (Moncada-Torres 2020).

**JACKPOT relevance.** **Year 2+ for federated model training** — specifically, training pathogen-classification or AMR-prediction models across JACKPOT instances without centralizing sample data. Lower priority than DataSHIELD (5.2.1) for the simpler "aggregate query" federation use cases JACKPOT will hit first.

The architecture analogy is direct: VANTAGE6's `node` ≈ a JACKPOT instance running federation-mode; VANTAGE6's `server` ≈ JACKPOT's hub instance; VANTAGE6's `algorithm` ≈ a Nextflow pipeline or Python computation that's safe to run remotely. JACKPOT's `federated_instances` table with `trust_level` semantics maps cleanly onto VANTAGE6's node-trust model.

**Adoption shape.** Not direct code lift unless JACKPOT decides to bolt federated ML on top — at which point VANTAGE6 is the obvious choice over building from scratch. Apache 2.0 is fully compatible with AGPL-3.0 for incorporation.

**Backlog item:**
```text
[ ] B-V6-1    Year 2+ — evaluate VANTAGE6 as the federated-ML substrate for
              JACKPOT cross-instance model training (e.g. AMR predictors,
              outbreak-cluster detection). Decide: integrate VANTAGE6
              wholesale vs. minimal-viable federation push job.
              Effort: 1 week evaluation, multiple weeks if integrated.
              Phase: Year 2+.
```

#### 5.2.3 MOLGENIS Armadillo

**Function.** A lightweight server purpose-built for hosting DataSHIELD-based federated analysis. Produced by the MOLGENIS consortium (University of Groningen, Netherlands). Wraps DataSHIELD with a simpler deployment model than the heavier Opal stack.

**Architecture.** Java-based service (Spring) with R running as a child process (`Rserve`). Holds datasets in Parquet on disk; clients send DataSHIELD R commands; Armadillo enforces non-disclosure rules and returns aggregates. Designed for low-overhead deployments at smaller research sites where Opal would be overkill.

**License.** LGPL-3.0.

**Maturity.** High. Documented in *Bioinformatics* (Cadman 2025). Used in production across European biobank federations alongside Opal.

**JACKPOT relevance.** **Defer.** Armadillo is only relevant if JACKPOT adopts DataSHIELD wholesale as its federated-analysis substrate (which the recommendation in 5.2.1 deliberately doesn't suggest — JACKPOT's stack is FastAPI + PostgreSQL, not R + Parquet, and a Python-native non-disclosure policy is more naturally part of the federation push job than a separate server).

If, however, JACKPOT later decides it wants R-based statistical analysis as a first-class federation primitive — for example, to interoperate with the existing European biobank ecosystem — Armadillo is the right substrate to bolt in. It's lighter than Opal and integrates with the broader MOLGENIS stack which JACKPOT could converge with.

**Adoption shape.** Pattern reference, not adoption. No backlog item.

---

### 5.3 Federated Search & Query Engines

These systems allow searching or querying across distributed repositories — narrower scope than DataSHIELD/VANTAGE6 (which run general computation) but exactly the right fit for JACKPOT Federation Level 1 ("query federation") in `docs/architecture.md` v6.0 §20.

#### 5.3.1 Sample Locator (German Biobank Alliance)

**Function.** Real-time federated search for biosample metadata across European biobanks. A researcher types in inclusion/exclusion criteria (age, sex, disease, sample type, tissue, etc.), and the Sample Locator queries 16+ participating biobanks in parallel and returns aggregate counts of matching samples per site. The researcher can then reach out to the relevant biobank to negotiate access.

**Architecture.** Built on **HL7 FHIR + Clinical Quality Language (CQL)**. Each participating biobank exposes a FHIR endpoint with biosample resources. A central "broker" component fans out queries (translating the researcher's criteria into FHIR/CQL), receives per-site responses, and returns the federated aggregate. Critically: **only counts are returned, not sample-level data**. Privacy is preserved by the FHIR/CQL query semantics — the broker has no ability to extract individual records.

**License.** Open-source.

**Maturity.** High. **Actively deployed across 16+ German biobanks** as the primary cross-biobank discovery tool. Documented in *Computers in Biology and Medicine* (Engels 2024).

**JACKPOT relevance.** ★ **Highest-priority study target for JACKPOT federation.** This is the closest existing implementation of JACKPOT's planned Federation Level 1. The pattern is *exactly* what JACKPOT needs:

- Researcher in Lab A wants to find Salmonella samples elsewhere matching specific criteria
- Lab A's JACKPOT issues a federated query to Labs B, C, D
- Each of B, C, D's JACKPOT instances runs the query locally and returns aggregate counts (not raw rows)
- Lab A sees "Lab B: 17 matching samples; Lab C: 3 matching; Lab D: 0" — and can request data sharing if interested

The German Biobank Alliance has solved every adjacent problem: (a) FHIR-based interoperability (which JACKPOT could converge with for biosample resources, complementing the existing GA4GH DUO/DRS work), (b) cross-jurisdiction governance (each biobank retains control), (c) audit logging, (d) opt-in by site.

**Adoption shape.** Two paths:

- **Pattern adoption** — JACKPOT's existing Federation Level 1 query API (`GET /api/v1/samples/?federation=true`) is functionally analogous; the question is whether to make it FHIR-spec-compatible so the same client could query both JACKPOT instances and Sample-Locator-compliant biobanks.
- **Direct integration** — JACKPOT instances could expose a FHIR Sample resource adapter, making them queryable from the existing Sample Locator broker. Useful for European deployments.

**Backlog items:**
```text
[ ] B-SL-1    Study Sample Locator's FHIR + CQL approach in detail.
              Compare to JACKPOT's native federation Level 1 query API.
              Decide: FHIR-spec-compatible federation, or JACKPOT-native
              with optional FHIR adapter. Effort: 2-3 days reading +
              architecture decision. Phase: before Federation Level 1
              implementation.

[ ] B-SL-2    If FHIR-compatible chosen — implement a FHIR Sample
              resource adapter for JACKPOT, allowing Sample-Locator-
              compliant brokers to federate-query JACKPOT instances.
              Effort: 2-3 weeks. Phase: Year 2.
```

#### 5.3.2 LIT-FED-SEARCH

**Function.** Federated search across biomedical/public-health repositories using OpenSearch as the underlying engine. Designed to handle heterogeneous repositories with different schemas — a federated search workflow rather than a federated query semantic over a uniform schema.

**Architecture.** Built on OpenSearch with a workflow-engine layer that handles per-repository query translation, result deduplication, and ranking. More query-engine than data-federation primitive — assumes participating repositories already publish an OpenSearch-compatible index of metadata.

**License.** Open-source.

**Maturity.** Emerging. Documented in *Journal of Computational Science* (Katulski 2024). Newer than Sample Locator and more research-prototype than production-deployment.

**JACKPOT relevance.** **Pattern reference; secondary to Sample Locator.** Useful if JACKPOT's federation needs ever expand to "search across heterogeneous schemas" (e.g. queries that should also surface results from non-JACKPOT repositories with different metadata models). Not a fit for JACKPOT-to-JACKPOT federation, where the schema is uniform by definition.

**Adoption shape.** Defer. Pattern reference only.

#### 5.3.3 Federated GMQL

**Function.** Federated genomic dataset query engine — specifically designed for genomic interval queries (regions, intersections, distances) across distributed datasets. Automatically distributes the query to the right sites and aggregates results.

**Architecture.** Built on the Genomic Markup Query Language (GMQL), originally developed at Politecnico di Milano. Federation extends single-site GMQL with a distributed query optimizer that decides where to run sub-queries.

**License.** Open-source.

**Maturity.** Medium. Documented in *Briefings in Bioinformatics* (Canakoglu 2021). Actively used in genomics research; deployment scale less broadly documented than Sample Locator.

**JACKPOT relevance.** **Pattern reference for the LAPIS-compatibility work.** When JACKPOT eventually exposes a LAPIS-compatible REST endpoint (`B-LAPIS-1` in the existing backlog) and federation-grade query distribution becomes interesting, Federated GMQL is the relevant prior art for "auto-distribute genomic queries across sites." LAPIS itself isn't federated; combining LAPIS-compat with a Federated-GMQL-style distribution layer is a Year-2+ idea.

**Adoption shape.** Pattern reference; no immediate code-lift.

#### 5.3.4 COMBAT-TB-NeoDB

**Function.** Graph-based integration of multiple biological databases to support complex federated queries for tuberculosis research. Uses Neo4j to model the relationships between strains, drug-resistance markers, host metadata, and clinical outcomes — letting researchers ask cross-database questions that are awkward in relational SQL.

**Architecture.** Neo4j graph database holding cross-references between TB-specific resources (TB-Profiler, GOA Mtb, etc.). Federation here means cross-database not cross-site — the queries are graph traversals across heterogeneous data sources, not queries to multiple TB-NeoDB instances at different institutions.

**License.** Open-source.

**Maturity.** Medium; narrow domain. Documented in *Bioinformatics* (Lose 2020).

**JACKPOT relevance.** **Defer — narrow domain.** TB-specific. JACKPOT's TB support (`tb_typing_results` table per `docs/architecture.md` v6.0 §10) covers spoligotyping, MIRU-VNTR, lineage, and WHO drug-susceptibility cataloging — that's the JACKPOT-side work. If JACKPOT ever needs deep cross-database TB querying, COMBAT-TB-NeoDB is a target to integrate with as an external resource (similar to how `B-PWATCH-1` integrates with Pathogenwatch).

**Adoption shape.** External-resource integration target, not adoption. No immediate backlog item.

---

### 5.4 Data Sharing & Harmonization Platforms

These are platforms focused on the *interoperability* layer — controlled access, schema harmonization, infrastructure for secure sharing — rather than on running computations or distributing queries. Closer in scope to JACKPOT itself; some are direct alternatives or complements.

#### 5.4.1 Cumulus

**Function.** Federated electronic health record (EHR) data sharing using the Bulk FHIR API. Designed to let multi-institution research consortia run analyses across hospital EHR data without each institution shipping raw records to a central site. Aggregate results leave the institution; raw data stays.

**Architecture.** Each participating institution exposes a Bulk FHIR endpoint over its EHR. A Cumulus library at the central site issues Bulk FHIR queries, the institutional FHIR server runs the query locally, and *only aggregate output* (typically counts or summary statistics) is returned. AI-integration features layer on top: Cumulus hooks into LLM pipelines for tasks like clinical note summarization at the institutional site.

**License.** Open-source (Apache 2.0).

**Maturity.** Medium. Documented in *JAMIA* (McMurry 2024). Deployed at SMART Health IT consortium and several Boston-area hospitals.

**JACKPOT relevance.** **Study — when JACKPOT integrates clinical EHR linkage.** JACKPOT's `HumanSample` already has hooks for clinical linkage (`case_id`, `case_source_system`, `adhs_id` for MEDSIS) but no live FHIR/EHR integration. When that integration becomes real — typically when an STLT operator deploys JACKPOT alongside their EHR — Cumulus's Bulk FHIR aggregation pattern is the canonical reference. Especially relevant for: "I want the case-mapping enrichment but I cannot ship hospital records into JACKPOT."

The architectural analogy is precise. Cumulus is to "EHR + FHIR" what JACKPOT's federation layer is to "JACKPOT + JACKPOT" — only aggregates leave the institution; raw data stays. The Bulk FHIR query semantics are well-developed (and HIPAA-compatible by construction since they enforce aggregate-only output at the EHR side).

**Adoption shape.** Not adoption — JACKPOT is the genomics platform, not the EHR. But Cumulus is the *consumer* JACKPOT data should be queryable from when STLT operators want to link genomic surveillance to clinical EHR. Future-direction; not on the critical path.

**Backlog item:**
```text
[ ] B-CUM-1   Year 2+ — when JACKPOT integrates with STLT EHR systems,
              evaluate exposing JACKPOT's HumanSample as a Bulk-FHIR-
              compatible resource for Cumulus federation. Allows EHR
              + genomic linkage analytics without shipping records into
              JACKPOT. Effort: 2-3 weeks. Phase: Year 2+.
```

#### 5.4.2 Overture

**Function.** Open-source modular genomics data platform from OICR (Ontario Institute for Cancer Research). Provides building blocks — submission services, file management, search, identity — for operators who want to stand up large-scale genomic data-sharing systems. Used as the substrate for several CCDC and Canadian genomics initiatives, including parts of the VirusSeq Data Portal infrastructure.

**Architecture.** Microservices stack: SONG (metadata submission), SCORE (file management), Maestro (search indexing), Ego (identity & auth), Arranger (faceted search UI), Stage (frontend skeleton). Operators pick the modules they need.

**License.** GPL-3.0 (most components). Confirmed in OICR's repos.

**Maturity.** Medium. Documented in *GigaScience* (Shiell 2025). Production deployments at several Canadian initiatives (VirusSeq, ICGC ARGO, CFMM, AMR-Net).

**JACKPOT relevance.** ★ **Highest-priority head-to-head comparison.** Overture is the *second* open-source genomic data platform (after Loculus) explicitly designed for multi-operator deployment in the same general design space as JACKPOT. The original `jackpot_pathoplexus_loculus_overview.md` went deep on Loculus because Loculus is the closest peer; Overture deserves the same depth.

Likely to surface differences worth understanding:

- **Microservices vs. monolith.** Overture is a federation of independently-deployable services (SONG, SCORE, Maestro, Ego, Arranger, Stage). JACKPOT is a monolithic FastAPI backend + a thin Streamlit/eventually-React frontend. Overture's pattern scales out better at large operators; JACKPOT's pattern has lower operational overhead at small operators.
- **Search backend.** Overture uses Elasticsearch via Maestro/Arranger. JACKPOT uses PostgreSQL with the LAPIS-compat plan as a Year-2 add. Different scale assumptions.
- **Identity model.** Overture uses Ego (Keycloak-similar) as a separate identity service. JACKPOT uses Google OAuth + JWT directly. Trade-off: JACKPOT's path is simpler; Ego is more pluggable for federated identity.
- **License.** Both GPL-3-family copyleft, so direct adoption is friction-free.

**Adoption shape.** A focused head-to-head session in the same shape as the original Loculus comparison. **High value, not yet done.** Outputs: a comparable architectural-divergence analysis (similar to Section 7 of this document), specific code-adoption recommendations, and likely a couple of backlog items.

**Backlog item:**
```text
[ ] B-OVR-1   Run a JACKPOT-vs-Overture head-to-head analysis modeled on
              the existing Loculus comparison (Sections 7-12 of this
              document). Outputs: architectural divergence assessment,
              identified code-adoption candidates from SONG/SCORE/Maestro,
              specific backlog items. Effort: 1 working session.
              Phase: any. Place placeholder for now.
```

#### 5.4.3 FAIR Data Pipeline

**Function.** Provenance-driven scientific data management system. Tracks every input, output, code version, and parameter for any computational analysis — making the full data lineage queryable and auditable. Built originally for COVID-19 epidemiological model reproducibility.

**Architecture.** A registry service (Python + Django) plus client libraries (Python, R, Julia, C++, Fortran, JavaScript). Researchers register data products, code versions, and run parameters; queries return the full dependency graph.

**License.** Open-source.

**Maturity.** Medium. Documented in *Philosophical Transactions of the Royal Society A* (Mitchell 2022). Deployed for multiple UK and Scottish epidemiology models.

**JACKPOT relevance.** **Study — directly informs FAIR R1.2 detailed-provenance roadmap.** JACKPOT's FAIR scorecard (per `docs/architecture.md` v6.0 §18) lists R1.2 (Detailed provenance) as 🔶 / Month 3 — "PipelineProvenance + pipeline_runs". The FAIR Data Pipeline is a concrete reference implementation that's broader than what JACKPOT currently scopes. Specifically:

- JACKPOT's `pipeline_results` is immutable + append-only — that's good for provenance but only for pipeline outputs.
- FAIR Data Pipeline tracks **every** code version, **every** input dataset version, **every** parameter, plus the user, machine, and dependencies. That's deeper provenance than JACKPOT currently captures (pipeline-version + tool-version, mostly).

**Adoption shape.** Not direct code lift — FAIR Data Pipeline is a heavyweight registry service with its own model. But the *what to capture* is portable. Specifically, JACKPOT's `PipelineProvenance` table (per the schema) could be extended to capture: input-data versions (already partial via `pipeline_results.input_sample_ids`), parameter snapshots (already in `pipeline_runs.parameters` JSONB), code version (partial via Nextflow `revision` field), execution environment (currently weak — just the GKE pod info).

**Backlog item:**
```text
[ ] B-FDP-1   Audit JACKPOT's PipelineProvenance + pipeline_runs against
              the FAIR Data Pipeline metadata model. Identify gaps in:
              (a) input-data version tracking, (b) execution-environment
              snapshot, (c) parameter immutability. Strengthen the schema
              to close the highest-value gaps. Effort: 1 week schema
              audit + 1-2 weeks implementation. Phase: when FAIR R1.2
              moves from 🔶 to ✅ on the FAIR scorecard.
```

#### 5.4.4 DataHarmonizer (Mpox package)

**Function.** Open-source ontology-based data curation toolkit for pathogen surveillance metadata. Web-based form interface that runs entirely in-browser (no backend required); validates per a JSON schema; exports CSV/TSV. The Mpox-specific package (`mpox_dataharmonizer`) is one of several PHA4GE-curated worked examples (alongside SARS-CoV-2, influenza, AMR, etc.).

**Architecture.** JavaScript + Vanilla DOM. Reads a JSON Schema, generates a tabular spreadsheet UI (Handsontable), validates inline, exports CSV.

**License.** MIT. Maintained by Centre for Infectious Disease Genomics and One Health (CIDGOH) at Simon Fraser University, with PHA4GE community contributions.

**Maturity.** High. Production-deployed in several public-health pipelines including JACKPOT itself. Documented in *Microbial Genomics* (Griffiths 2026) for the Mpox package specifically.

**JACKPOT relevance.** **Already adopted.** JACKPOT generates DataHarmonizer-compatible templates from its LinkML schema (per `docs/architecture.md` v6.0 §11) — three template tiers (T1/T2/T3), source-type-specific combined templates, embedded version markers. The Mpox package is one of several upstream examples JACKPOT learned from.

The Mpox-package paper surfaces a **per-pathogen contextual specification** pattern — schema-versioned per pathogen, with curation guidance per organism. The UX appeal is real: a lab analyst filling out only Salmonella forms sees only Salmonella-relevant fields rather than a wide monolith with most columns greyed out. **Decision (2026-05): adopt per-pathogen as a generated *view* layer over the monolith, NOT as a schema decomposition.** JACKPOT's schema stays monolithic — one schema covering all source types and organisms via discriminators — because that monolith is what makes JACKPOT's differentiators (CARE/sovereignty slots, tier×sharing axis, federation disclosure annotations) *structural*: those are cross-cutting horizontal concerns that must hold uniformly over the entire field space. Per-pathogen templates are generated views (an organism-discriminator filter over the monolith that hides irrelevant slots at entry time without deleting them), so every view inherits the governance slots and cannot drop them. The rejected alternative — factoring the monolith into independently-versioned per-pathogen specs (the CIDGOH `is_a` core+extension pattern) — would turn each structural governance guarantee into a per-template invariant to audit, and adopting upstream specs wholesale would mean new fields arriving on CIDGOH's release schedule without JACKPOT governance annotations. The view approach delivers the entry-UX win at zero governance cost.

**Adoption shape.** Already largely adopted. Extension: per-pathogen template *views* generated from the monolith (see decision above) — entry-UX improvement, no schema change.

**Backlog item:**
```text
[ ] B-DH-1    Add per-pathogen DataHarmonizer template *projections* over
              the existing monolithic schema. Generated-view layer, NOT a
              schema refactor: extend the T1/T2/T3 template generator with an
              organism filter that emits one DataHarmonizer JSON template per
              pathogen from the same LinkML schema. Governance slots
              (CARE/sovereignty, tier×sharing, federation disclosure) stay
              core in the monolith and are inherited by every view. First
              template: Mpox, to validate the projection mechanism end to end.
              REJECTED (do not re-litigate): factoring the monolith into
              independently-versioned per-pathogen specs — sacrifices the
              cross-cutting governance guarantees that are JACKPOT's
              differentiators for a commodity UX win the view layer already
              delivers. Effort: 1-2 sessions. Phase: any time DataHarmonizer
              template work is touched.
```

#### 5.4.5 BioGenome Portal (out of scope — biodiversity cataloging)

**Function.** Web portal for organizing and displaying biodiversity genomics metadata (guigolab/biogenome-portal, CRG Barcelona). Catalogs eukaryotic species' genome-sequencing progress against target lists, tracks INSDC submission status, and presents data on a taxonomic tree plus a geographic map. Production instances back the Earth Biogenome Project, ERGA, and the Catalan Initiative.

**License / stack.** MIT. Python Flask + uWSGI backend, MongoDB store, Vue.js SPA, docker-compose. Fully divergent from JACKPOT's FastAPI / PostgreSQL / SQLAlchemy / Streamlit / Helm stack — no clean code-adoption path.

**Maturity.** Peer-reviewed (NAR Genomics & Bioinformatics, Mar 2025; DOI 10.1093/nargab/lqaf020). Maintained through v3.3.1 (Jul 2025), but single-maintainer and ~6 stars — low durability.

**JACKPOT relevance.** Out of scope for surveillance. Same data-portal category as Overture (§5.4.2) but biodiversity-scope: no pathogen detection, SoC screening, AMR, federated query, or PII gating. Not a competitor and not an integration candidate. One reusable idea only — its INSDC import-by-BioProject-accession pattern (import everything under a BioProject umbrella, then re-sync on a schedule), captured as a UX enhancement on the external-search backlog item. Evaluated and rejected for adoption 2026-06-16.

---

### 5.5 Decentralized / Privacy-Preserving Tools

These tools provide privacy-preserving or decentralized processing primitives — narrower than the federated-analysis frameworks in 5.2, but with stronger privacy guarantees because they emit non-identifying outputs by construction.

#### 5.5.1 CDST (CoDing Sequence Typer)

**Function.** Decentralized, privacy-preserving bacterial genomic typing. Takes a bacterial genome assembly as input and emits a hash-based representation that's both fast to compute and non-identifying — the hash is enough to detect that two isolates are very similar, without exposing the underlying sequence.

**Architecture.** Reads coding sequences from an assembly, computes a deterministic hash per CDS using a defined algorithm, emits a JSON typing record. Two labs running CDST on the same isolate produce identical hash records; close-but-not-identical isolates produce many-shared-hashes records. The hash representation is interoperable across labs by construction.

**License.** Open-source.

**Maturity.** Emerging. Documented in *Microbial Genomics* (Li 2025). Newer than Pathogenwatch's typing tools but with stronger interoperability guarantees.

**JACKPOT relevance.** ★ **Highest-priority adopt for federated bacterial outbreak detection.** This is the privacy-preserving primitive JACKPOT's Year-2 federation layer needs. The use case:

- Lab A has a Salmonella outbreak; isolates are sequenced and hash-typed via CDST; the hashes go into `samples.cdst_hash`.
- Lab B has unrelated Salmonella surveillance with their own CDST hashes.
- Federation Level 1 query: "show me any Lab B isolates whose CDST hashes overlap with Lab A's outbreak isolates by ≥ N hashes."
- Lab B returns count + minimal metadata; *no raw sequences are exchanged*.
- If a match is found, Lab A can request data sharing with the specific governance ceremony (existing dataset_access_requests workflow).

This is *better* than the Loculus-style group-ownership model for cross-instance outbreak detection because (a) no raw data exchanged at all in the discovery phase, (b) the typing is deterministic so cross-instance comparison is well-defined, (c) the hashes can be shared more permissively than raw sequences (they're already non-identifying).

**Adoption shape.** Direct integration as a JACKPOT pipeline-zoo entry, plus a `cdst_hashes` field on bacterial samples. Federation layer queries CDST overlap as a primary signal.

**Backlog items:**
```text
[ ] B-CDST-1  Add CDST as a Level-1 pipeline-zoo entry — produces hash-
              based typing for every bacterial isolate. Effort: 1-2
              sessions. Phase: bacterial pipeline-zoo work.

[ ] B-CDST-2  Add cdst_hashes JSONB field to samples table; populate
              from B-CDST-1 pipeline output. Effort: 1 session
              (Alembic migration + pipeline_results_loader.py). Phase:
              with B-CDST-1.

[ ] B-CDST-3  Implement federation-layer CDST-hash-overlap query: given
              query hashes from peer instance, return count of local
              samples with N-or-more shared hashes (no metadata, no
              IDs). Privacy-preserving primitive for outbreak detection.
              Effort: 1 week. Phase: Year 2 federation Level 1.
```

#### 5.5.2 Alembic

**Function.** AI-powered conversion of heterogeneous biological metadata into structured, searchable formats. Uses LLMs and rule-based transforms to take messy spreadsheet/CSV/PDF metadata and produce schema-conformant records — useful for legacy data ingestion.

**Architecture.** Python pipeline orchestrating LLM calls (configurable backend) plus deterministic post-processing. Schema-aware: takes a target LinkML or JSON Schema as input and tries to produce records that validate against it.

**License.** Open-source.

**Maturity.** Emerging. Documented in *Vavilovskii Zhurnal Genetiki i Selektsii* (Bezdvornykh 2026) — a 2026 publication.

**JACKPOT relevance.** **Defer.** Potentially useful for ingesting legacy spreadsheets that don't conform to JACKPOT's LinkML schema or any known PHA4GE template — labs sometimes hand over metadata in idiosyncratic CSVs or even PDFs from older systems. JACKPOT's `harmonizer.py` already does deterministic column-mapping for known templates; Alembic-style LLM-driven conversion would extend this to "anything structured-ish, however weird."

But it's not on the critical path. The four highest-volume legacy formats (legacy-platform CSV, BaseSpace CSV, Globus deposit naming patterns, NCBI BioSample) are already handled by `harmonizer.py` + `file_detector.py`. The remaining long tail of weirdly-shaped legacy spreadsheets is small enough that manual cleanup is cheaper than building the LLM pipeline today.

**Adoption shape.** Defer; revisit if legacy-data ingestion becomes a regular workflow. Pattern reference for now.

---

## 6. Where JACKPOT sits in the matrix

### 6.1 JACKPOT just changed rows

JACKPOT is structurally a *software package* designed to power multiple deployments — same row as Loculus.

The Pathoplexus-as-overlay-on-Loculus pattern is now the directly applicable reference for how `Midnight-Oil-Innovation/jackpot` could be deployed by other operators with overlay configs.

### 6.2 Defensible differentiators (keep these)

These are things JACKPOT does that almost nobody else in the matrix does — keep them in the spec.

1. **LinkML schema as the source of truth.** None of the peers use LinkML this aggressively. EnteroBase, BV-BRC, and PD all have schemas, but ad-hoc; PHA4GE templates are LinkML-adjacent but not full pipelines. **Keep this — it's a moat.**
2. **GA4GH DUO codes at the dataset level.** Nobody else (except partial NCBI) implements DUO. Pathoplexus has dual-track but not DUO codes. Loculus has nothing yet.
3. **Cloud DLP scanning of free-text metadata.** Nobody else does this. Section 10 develops the two-PII-gate story.
4. **NCBI SRA Human Scrubber integration for genomic PII.** Loculus has no equivalent; this aligns directly with WHO/IPSN attribute 6 (Data curation).
5. **Pipeline-results as immutable, append-only versioned rows.** Loculus tracks sequence versions but not pipeline-result versions; nobody else really does this.
6. **Pathogen-agnostic + One-Health source-types** (human, wildlife, livestock, wastewater, soil, surface, food, vectors). Most peers are single-host or bacteria/virus split.
7. **Six distinct ingest paths** (signed URL, URI registration, SRA/accession import, workspace promotion, CSV batch, Globus deposit-first). Loculus has web/API + INSDC ingest; nobody else has this breadth.
8. **Tier-aware metadata validation.** None of the peers track partial-completeness explicitly.
9. **Cloud-native URI registration without local transit.** `gs://`, `s3://`, `https://` URIs registered without copying. Important for petabyte data sets.

### 6.3 Gaps vs the field (close these)

Ordered by ROI:

| Gap | Who has it | Effort to adopt | ROI |
|---|---|---|---|
| **Sequence versioning** (every edit tracked, not just metadata audit) | Loculus | Medium (DB schema + immutable history) | High |
| **Per-sample data-use terms** (OPEN vs RESTRICTED with embargo) at submission UI | Pathoplexus / Loculus | Low — schema supports it; just wire UI | **Very high** |
| **Auto-INSDC broker** that fires on submission for OPEN samples | Loculus `ena-submission` | Medium (Python adoption) | High |
| **LAPIS-compatible API endpoint** for querying viral sequences | GenSpectrum | Medium-High | Medium (Year 2) |
| **PDS# SNP cluster pull from NCBI** for outbreak context | NCBI PD on BigQuery | **Low** (already on GCP) | **Very high** |
| **AMRFinderPlus + MicroBIGG-E pull** | NCBI PD on BigQuery | **Low** (BigQuery JOIN) | **Very high** |
| **cgMLST nearest-neighbour clustering** for bacterial outbreak detection | Pathogenwatch / EnteroBase | High (build or proxy) | High for bacterial scope |
| **Hierarchical clustering codes** (HierCC, LIN codes) | EnteroBase, Pathogenwatch | Medium-High | Medium (bacterial-specific) |
| **Real-time/continuous surveillance** (delta-driven re-analysis) | Solu | Medium | Medium-High |
| **Untargeted metagenomics** workflow | RT-MetA | Medium | Medium |
| **Embeddable LAPIS-style widgets** in Streamlit dashboard | GenSpectrum | Medium | Medium |
| **Public governance documents** (charter, COI, jurisdiction) | Pathoplexus | **Trivial** (document work) | High (WHO/IPSN attribute compliance) |
| **Documented benefits-sharing framework** | Pathoplexus | Trivial-Medium | High (PABS-readiness) |
| **Pluggable preprocessing pipeline** | Loculus | Medium (~200 lines) | **Very high** |

The "very high" items in the table are the priorities for Sections 12 and 12.

---

## 7. JACKPOT vs Loculus: architectural divergence

Now we drop into the head-to-head comparison, which is where most of the practical recommendations land.

### 7.1 The architectural divergence in one sentence

> **Loculus separates "store the bytes" from "make sense of the bytes."** JACKPOT does both at upload time, in the same FastAPI request, before responding.

Both are valid choices for different operating regimes. Section 10 develops the trade-offs.

### 7.2 Vocabulary mismatch (read this first — it explains a lot)

Loculus and JACKPOT use the words "ingest," "preprocessing," and "CLI" for *very different things*. Once mapped, the comparison gets clearer.

| Word | Loculus means... | JACKPOT means... |
|---|---|---|
| **Ingest** | Pulling data **FROM** external sources (NCBI/GenBank/ENA via NCBI Datasets CLI) **INTO** Loculus, by a Snakemake workflow that calls Loculus's own submission API. Unidirectional: external → internal. | Receiving sample uploads **FROM** users **INTO** JACKPOT through any of 6 paths: signed URL, URI registration, SRA/accession import, workspace promotion, CSV batch, Globus deposit-first. |
| **Preprocessing** | A **separate, pluggable, versioned process** that pulls user-submitted *unprocessed* data from the backend over HTTP, validates/parses/aligns/QCs it, and pushes processed data back. Per-organism. Distinct codebase, distinct deployment. | Doesn't really exist as a separate concept. The closest equivalent is `validator.py` + `file_detector.py` + `dlp_scanner.py` + the `sra-human-scrubber` Nextflow process, all running inside the FastAPI app or as Nextflow steps tied to the upload path. |
| **CLI** | The submission/admin command-line tool used by submitters to upload sequences and groups. | A handful of `setup/write_files*.py` and `scripts/seed_*.py` operator-bootstrap scripts (which P0e is replacing with a real `jackpot` CLI). |

The mapping that actually matters: **JACKPOT's `validator.py` + `file_detector.py` + `dlp_scanner.py` + `ingest_scrubber.nf` ↔ Loculus's `preprocessing/` service.**

Loculus's `ingest/` ↔ JACKPOT's *future* "import from NCBI/ENA" feature — currently only a stub via the SRA accession import path; Loculus has a real Snakemake-based pull-from-INSDC pipeline.

### 7.3 Loculus's two-step model

```text
User uploads → Backend stores raw → Backend says "OK accepted, status=pending"
                                       │
                                       ▼
        Preprocessing pipeline polls "/extract-unprocessed-data"
                                       │
                                       ▼
                Pipeline aligns, validates, QCs, annotates
                                       │
                                       ▼
        Pipeline POSTs to "/submit-processed-data" with errors/warnings
                                       │
                                       ▼
        Backend stores processed result + makes it queryable via LAPIS
```

**Implication:** The backend never "knows" how to validate any specific organism. Adding a new pathogen = writing a new preprocessing pipeline image. Backend stays organism-agnostic.

### 7.4 JACKPOT's one-step model

```text
User uploads → ingest.py router synchronously calls:
                  file_detector.validate_file_type()
                  validator.validate_metadata(tier-aware)
                  harmonizer.map_csv_columns()
                  dlp_scanner.scan() (if DLP_ENABLED)
                → Persist sample row → enqueue scrubber job
                → Return 201 with ValidationResult

Background:
  scrubber Nextflow process (sra-human-scrubber) runs on raw FASTQ
    → updates samples.scrub_status: PENDING → IN_PROGRESS → COMPLETE
    → promotes files from jackpot-raw to jackpot-sequences bucket
    → unblocks downstream pipelines
```

**Implication:** Validation happens before the user's HTTP request returns, so they get immediate feedback. Organism-specific validation logic lives in the backend — adding a new pathogen means changing backend code.

---

## 8. Loculus repo layout (what's actually in those directories)

Verified against the live repo at `loculus-project/loculus`:

```text
loculus/
├── backend/                    Kotlin (Spring Boot). Stateless REST API.
│                               Knows nothing about pathogen-specific
│                               validation, file types, or alignment logic.
│                               25.6% of repo by code volume.
│
├── preprocessing/
│   ├── specification.md        The HTTP contract between backend and ANY
│   │                           preprocessing pipeline. 192 lines, very clean.
│   ├── dummy/                  Reference Python pipeline that does no
│   │                           processing — useful as a template for new
│   │                           pipelines.
│   └── nextclade/              The "real" pipeline used by Pathoplexus
│       └── src/loculus_preprocessing/
│           ├── prepro.py                     Main entry point; pull/process/push loop
│           ├── backend.py                    HTTP client to Loculus backend
│           ├── datasets.py                   Nextclade dataset management
│           ├── processing_functions.py       Field-by-field validators
│           ├── config.py                     Per-organism config loader
│           └── ...                           (Python, AGPL-3.0)
│
├── ingest/                     Snakemake workflow that pulls from external
│   ├── Snakefile               INSDC sources (NCBI Datasets CLI, ENA) and
│   ├── scripts/                pushes into Loculus via the submission API.
│   │   ├── group_segments.py   Multi-segment handling (e.g. flu)
│   │   ├── filter.py           QC filtering before submission
│   │   └── ...
│   └── (Python + Snakemake; runs as a separate batch job, periodically)
│
├── ena-submission/             Snakemake + Python broker that pushes Loculus
│   └── ...                     sequences OUT to ENA. Reverse direction of ingest.
│
├── cli/                        Python CLI for submitters. AGPL-3.0.
│   └── ...                     Auth, group management, sequence submission,
│                               revision, revocation, approval flows.
│
├── loculus-silo/               Rust LAPIS query engine. C++ 18, AGPL-3.0.
│
├── website/                    TypeScript + Astro. 43.7% of repo by code volume.
│
├── kubernetes/                 Helm charts for k8s deployment.
│
├── keycloak/                   Authentication theme + realm config.
│
└── architecture_docs/          Architecture documentation.
```

Languages: TypeScript 43.7%, Python 25.8%, Kotlin 25.6%, Astro 2.4%, Go Template 1.0%, PLpgSQL 0.7%. **The Python pieces are in `preprocessing/`, `ingest/`, `ena-submission/`, and `cli/` — these are the directly-adoptable parts for JACKPOT.**

### 8.1 Loculus's preprocessing HTTP contract (the key pattern)

From `preprocessing/specification.md`:

The pipeline is a separate program that communicates with the backend via two HTTP endpoints:

#### `POST /extract-unprocessed-data?numberOfSequenceEntries={N}&pipelineVersion={V}`

Returns up to N unprocessed entries as **NDJSON** (one JSON object per line). Each line:

```json
{
    "accession": 1,
    "version": 1,
    "data": {
        "metadata": {"...": "..."},
        "unalignedNucleotideSequences": {"...": "..."},
        "files": {"...": "..."}
    },
    "submitter": "insdc_ingest_user",
    "submissionId": "...",
    "groupId": 0,
    "submittedAt": 0
}
```

If the pipeline version is below the current version, the backend returns 422.

#### `POST /submit-processed-data?pipelineVersion={V}`

Pipeline POSTs back NDJSON with processed data:

```json
{
    "accession": 1,
    "version": 1,
    "errors": [...],
    "warnings": [...],
    "data": {
        "metadata": {"...": "..."},
        "unalignedNucleotideSequences": {"...": "..."},
        "alignedNucleotideSequences": {"...": "..."},
        "nucleotideInsertions": {"...": "..."},
        "alignedAminoAcidSequences": {"...": "..."},
        "aminoAcidInsertions": {"...": "..."},
        "sequenceNameToFastaId": {"...": "..."},
        "files": {"...": "..."}
    }
}
```

Errors and warnings have a structured schema:

```json
{
    "unprocessedFields": [{"type": "Metadata", "name": "country"}],
    "processedFields": [{"type": "Metadata", "name": "geo_loc_name"}],
    "message": "Country code 'XYZ' is not a valid ISO-3166 country code."
}
```

This dual-field-ref structure (source unprocessed → target processed) is what enables nuanced UI errors. JACKPOT's `ValidationResult` should adopt this.

### 8.2 Reprocessing semantics

From the spec:

> The backend accepts processed data from pipelines that have the current or newer version. It will automatically switch to a newer pipeline version if the newer version has successfully processed all sequences that had also been successfully processed by the current version.

This is the elegant part. You deploy a new pipeline version side-by-side, it processes everything in the background, and once it's caught up, the backend atomically promotes it. No downtime, no data loss, no inconsistent intermediate state.

---

## 9. JACKPOT current state (the ingest pipeline in detail)

```text
jackpot-backend/
├── backend/
│   ├── routers/
│   │   └── ingest.py           FastAPI router. POSTs:
│   │                             /api/v1/ingest/signed-url
│   │                             /api/v1/ingest/uri
│   │                             /api/v1/ingest/accession (SRA/ENA)
│   │                             /api/v1/ingest/csv (bulk batch)
│   │                             /api/v1/ingest/globus-callback (webhook)
│   │                             + workspace promotion via SDK
│   │                           Calls validator.py, file_detector.py,
│   │                           dlp_scanner.py, harmonizer.py inline.
│   │                           Enqueues scrubber job for raw FASTQs.
│   │
│   ├── file_detector.py        Critical Rule 20 — sole owner of file type
│   │                           and naming-convention logic.
│   │                             - get_file_type() (extension-based)
│   │                             - validate_file_type() (content-sniffing,
│   │                               reads 1-16 bytes, gzip/BGZF transparent)
│   │                             - SUPPORTED_TYPES, _ROADMAP_TYPES
│   │                             - _EXTENSION_MAP, _CONTENT_SIGNATURES
│   │                             - FileDetectorError on mismatch
│   │                           Handles: standard R1/R2, numeric 1/2,
│   │                           forward/reverse, multi-lane Illumina
│   │                           (L001_R1_001), nanopore chunks (barcode01_0).
│   │
│   ├── validator.py            Tier-aware metadata validation.
│   │                             - ValidationResult{tier, tier2_missing,
│   │                                                tier3_missing}
│   │                             - compute_surveillance_relevant()
│   │                             - date precision handling
│   │                             - FASTA-only auto-skip
│   │
│   ├── harmonizer.py           Maps inbound CSV columns → schema fields
│   │                           via mapping configs (PHA4GE, NCBI, etc.)
│   │
│   ├── dlp_scanner.py          GCP Cloud DLP — METADATA PII GATE.
│   │                             - dynamic field discovery from JSON Schema
│   │                             - hard block-and-warn FLAGGED samples
│   │                             - DLP_ENABLED=false bypass for local dev
│   │                             - FIELD_EXCEPTIONS (pi_name excluded
│   │                               from PERSON_NAME)
│   │                             - LIKELY likelihood threshold
│   │                             - _redact_matched_text() for audit logging
│   │
│   ├── jobs.py                 Background job orchestration:
│   │                             - run_scrubber_queue_job()
│   │                             - APScheduler locally,
│   │                               Cloud Scheduler in GKE
│   │                             - SCRUBBER_MAX_CONCURRENT (default=10)
│   │
│   └── pipeline_results_loader.py   Immutable append-only pipeline_results
│                                JSONB rows + 18-column samples updates.
│                                Two-tier storage with type coercion.
│
└── nf/
    └── ingest_scrubber.nf      Nextflow process — GENOMIC PII GATE.
                                  container: ncbi/sra-human-scrubber:latest
                                  binary:    scrub_human_data
                                  Runs on every raw FASTQ at ingest.
                                  6-state lifecycle (PENDING → IN_PROGRESS →
                                  COMPLETE / FAILED / SKIPPED /
                                  PENDING_APPROVAL).
                                  Skip governance: any user can request,
                                  Lab Director approves within 48h or
                                  auto-deny. Auto-skip for FASTA-only
                                  (no_raw_reads) and SRA-imported
                                  (sra_imported) samples.
```

The two-PII-gate architecture is one of JACKPOT's strongest differentiators — section 10 develops it.

---

## 10. The two-PII-gate story (what Loculus doesn't have)

JACKPOT has *two* distinct PII gates at ingest time, solving different problems:

| Gate | What it catches | Tool | Where it runs |
|---|---|---|---|
| **Genomic PII** | Human DNA reads contaminating non-human pathogen samples | NCBI SRA Human Scrubber (a.k.a. HRRT, Human Read Removal Tool) | Nextflow process, GKE Job |
| **Metadata PII** | Free-text PHI/PII (names, MRNs, etc.) leaking into metadata fields | GCP Cloud DLP via `dlp_scanner.py` | In-process at ingest |

Both gates run before storage, both block downstream pipelines on failure, and both have skip governance.

### 10.1 The SRA Human Scrubber lifecycle

```text
scrub_status states:
  PENDING            queued, files not downloadable, pipelines blocked
  IN_PROGRESS        scrubber GKE Job running
  COMPLETE           files downloadable, pipelines can launch
  FAILED             Lab Director notified
  PENDING_APPROVAL   user requested skip; Lab Director must approve in 48h
  SKIPPED            auto-skip (FASTA-only, SRA-import) or LD-approved skip
```

Auto-skip rules:
- **FASTA-only uploads**: `skip_reason = no_raw_reads` (nothing to scrub)
- **SRA-imported samples**: `skip_reason = sra_imported` (NCBI already scrubbed upstream)

Skip governance: any user can request skip; Lab Director must approve within 48h or auto-deny (conservative default — never silently bypass). 48-hour timer is enforced by background job.

Concurrency control: `run_scrubber_queue_job()` in `backend/jobs.py` limits to `SCRUBBER_MAX_CONCURRENT=10` simultaneous jobs. Important for Globus batch arrivals where 100s of samples can land at once.

Bucket isolation: raw FASTQs land in `jackpot-raw` (30-day lifecycle); only `COMPLETE` samples get promoted to `jackpot-sequences` (permanent).

Pipeline gating: pipelines literally cannot launch until `scrub_status = COMPLETE` — enforced in the pipelines router.

### 10.2 The Nextflow process

```nextflow
process SCRUB_HUMAN_DATA {
    container 'ncbi/sra-human-scrubber:latest'
    label 'process_medium'

    input:
    path raw_fastq

    output:
    path "clean_${raw_fastq.baseName}.fastq.gz"

    script:
    """
    # Scrub human reads using NCBI tool
    scrub_human_data --input ${raw_fastq} --output clean_${raw_fastq.baseName}.fastq.gz
    """
}

process REGISTER_METADATA {
    input:
    val sample_id
    path clean_fastq

    script:
    """
    python3 register_to_bq.py --sample ${sample_id} --uri gs://${params.bucket}/sequences/${clean_fastq}
    """
}

workflow {
    main:
        fastqs = channel.fromPath("gs://${params.staging_bucket}/*.fastq.gz")
        SCRUB_HUMAN_DATA(fastqs)
        REGISTER_METADATA(params.sample_id, SCRUB_HUMAN_DATA.out)
}
```

### 10.3 Loculus has neither gate

To be precise:

- **Loculus has no built-in host-read removal.** Pathoplexus relies on submitter discipline plus the fact that their `ingest/` workflow pulls from INSDC, which is *supposed to* be already-scrubbed upstream. The Loculus model would treat host-read removal as a step in a preprocessing pipeline, but no shipped Loculus pipeline implements it.
- **Loculus has no metadata PII scanning.** No GCP DLP integration, no field-by-field free-text screening.

This is a *real* JACKPOT differentiator that maps directly onto **WHO/IPSN attribute 6 (Data curation)**, which explicitly calls for "host-read removal from raw data." JACKPOT scoring "Very strong" on that attribute is largely *because* of the scrubber integration.

### 10.4 How both gates fit into Loculus's preprocessing model

If JACKPOT adopts the Loculus pluggable-preprocessing pattern (recommendation A1 in Section 12), the scrubber and DLP scan naturally fit as preprocessing-pipeline steps:

```text
Sample uploaded
  → Backend stores raw + status=PENDING
  → DLP scan pipeline polls /extract-unprocessed-data
       → if PII detected, returns errors[]
       → otherwise returns processed metadata clean
  → Scrubber pipeline polls /extract-unprocessed-data filtered for raw FASTQ
       → runs sra-human-scrubber on the FASTQ files
       → returns processed sample with clean_fastq URIs +
         scrub_status=COMPLETE (or errors if scrubbing failed)
  → Backend promotes files from jackpot-raw to jackpot-sequences
  → Sample available for downstream pipelines
```

Skip governance and the state machine still live in the backend (where they belong, since they're policy not analysis). The scrubber itself becomes a swappable Loculus-compatible preprocessing pipeline — meaning a future operator could replace `sra-human-scrubber` with a more aggressive host-depletion tool (KrakenUniq, hostile, etc.) without touching backend code.

**The recommendation isn't "build a scrubber" — JACKPOT already has one. It's "factor the scrubber out as a Loculus-compatible preprocessing pipeline so other operators can swap in different host-removal tools."**

---

## 11. Side-by-side comparison: where each is better

### 11.1 Where Loculus is structurally better

| Aspect | Loculus | JACKPOT current | Why it matters |
|---|---|---|---|
| **Pluggability** | Any language can write a pipeline. Loculus ships Python references; could be Rust/Go/whatever. | All validation logic must be Python in the FastAPI app. | If JACKPOT wants community-contributed organism validators, this is gold. Anyone can fork the Nextclade pipeline and ship a new one without touching backend. |
| **Versioning of validation logic** | Pipeline version is a first-class field (`pipelineVersion`). Backend tracks which records were processed by which version. Auto-rolls forward when new version processes everything. | No equivalent. ValidationResult has no version tag; if validator.py logic changes, prior validations are silently incoherent with new ones. | Reprocessing semantics. When you update a validator, you can re-run the new one on old samples in the background and switch over atomically. |
| **NDJSON streaming over HTTP** | `/extract-unprocessed-data` and `/submit-processed-data` use NDJSON. One JSON object per line. Streamable, memory-efficient. | All current ingest paths use single-record JSON or CSV files. Bulk ingest reads CSV in memory. | Matters for million-record batches. Less for individual user uploads. |
| **Structured error/warning schema** | `{unprocessedFields, processedFields, message}` — errors carry source AND target field references. | Pydantic ValidationError or ad-hoc dict. Errors typically only point to source field. | UI quality. Loculus can highlight "this *output* field is bad because of *that input* field." |
| **Stateless backend** | Backend has no domain knowledge of pathogens. Adding mpox is a config change + new pipeline image. | Adding a pathogen requires touching `OrganismNameEnum`, `validator.py`, possibly `surveillance_relevant_organisms`. | Operator-extensibility. Deployer can add organisms without forking JACKPOT itself. |
| **Reference dummy implementation** | `preprocessing/dummy/` exists explicitly so contributors can fork it. | No equivalent reference implementation. | Onboarding contributors. |
| **NCBI Datasets CLI integration** | `ingest/` workflow uses `ncbi-datasets-cli` to pull genome/sequence packages from NCBI in a structured, schema-aware way. | JACKPOT uses E-utilities + fasterq-dump, more brittle. | Reliability and richer metadata. NCBI Datasets returns a complete BioSample + assembly + protein bundle in one zip. |

### 11.2 Where JACKPOT is structurally better

| Aspect | JACKPOT | Loculus | Why it matters |
|---|---|---|---|
| **Tier-aware metadata validation** | `ValidationResult{tier, tier2_missing, tier3_missing}` — accept partial submissions and tell user what they need to upgrade tier. | No equivalent. Each field is required-or-not, no "good enough for now, fill in later" semantics. | Real-world surveillance accepts incomplete data. Loculus would either reject or accept silently — JACKPOT explicitly tracks completeness. |
| **Content-sniffing file detection** | `file_detector.validate_file_type()` reads 1-16 bytes, handles gzip/BGZF transparently, rejects FASTQ uploaded with `.fastq.gz` if it's actually a FASTA. Critical Rule 20: *one* place for this logic. | Submitter is trusted to label files correctly. Errors surface much later in preprocessing pipeline. | Earlier failure = better UX + cheaper compute. |
| **6 distinct ingest paths** | signed-URL, URI registration (gs://, s3://, https://), SRA/accession, workspace promotion, CSV batch, Globus deposit-first. | Web upload + API upload + INSDC ingest workflow. No equivalent for cloud URI registration without local transit, no Globus, no workspace promotion. | Different operator scenarios need different paths. |
| **Cloud-native URI registration** | `POST /api/v1/ingest/uri` registers a `gs://`, `s3://`, or `https://` URI without copying. Optional server-side copy job. | Always copies into Loculus's S3 bucket. | Petabyte data sets. Petabytes of ONT reads on a lab's GCS bucket can be registered without paying egress. |
| **Genomic PII gate (SRA Human Scrubber)** | Full Nextflow integration with 6-state lifecycle, skip governance, concurrency control, bucket isolation, pipeline gating. | No equivalent. | WHO/IPSN attribute 6 compliance + accidental-human-DNA-republishing prevention. |
| **Metadata PII gate (GCP DLP)** | `dlp_scanner.py` runs Cloud DLP on free-text fields, blocks samples with PII/PHI before storage. `DLP_ENABLED=false` for local dev. | No equivalent. Pathoplexus relies on submitter discipline. | Public-health data has PII/PHI risk. |
| **Surveillance-relevance computation** | `compute_surveillance_relevant()` + override workflow + governance board path for TRUE→FALSE demotions. | No equivalent — every sequence is treated equivalently. | Reportable-organism workflows. Real differentiator. |
| **Per-pipeline result schemas (downstream)** | `pipeline_results_loader.py` has typed schemas for each of 11 pipelines. Immutable append-only history. | Loculus only stores preprocessing output, no downstream pipeline result history. | JACKPOT is doing more — sample manager + pipeline orchestrator + result store. |
| **Tier-aware bulk validation in CSV ingest** | One call validates the whole CSV row-by-row with tier per row. | N/A — Loculus has no CSV path. | Bulk laboratory submission workflows. |

### 11.3 Where they're solving genuinely different problems

| Aspect | Loculus | JACKPOT |
|---|---|---|
| **Primary unit** | Sequence (FASTA-first; FASTQ is rare) | Sample (FASTQ + FASTA + metadata as a unit) |
| **Submission lifecycle** | Submit → preprocess → review/edit → release → revise/revoke | Upload → tier-validate → DLP-scan → scrubber → store → run pipelines → store results |
| **Federation primitive** | Sequence with provenance | Sample with sharing_level + data_use_terms + audit log |
| **Update model** | Sequence versioning (every edit is a new version of the same accession) | Sample is mutable for pre-pipeline edits, audit-logged; pipeline_results are immutable append-only |
| **Search backend** | LAPIS over SILO (Rust in-memory) | Postgres via FastAPI router with filters |
| **Read scale target** | Million+ sequences, sub-second LAPIS queries | Hundreds of thousands of samples, complex filter combinations |

### 11.4 Net summary

> **JACKPOT's existing ingest gates — `file_detector.py` (file-type sniffing), `validator.py` (tier-aware metadata), `dlp_scanner.py` (metadata PII), AND the SRA-human-scrubber Nextflow integration (genomic PII) — collectively constitute a more thorough ingest pipeline than anything in Loculus's preprocessing for the multi-source-type, sample-centric, surveillance-focused operating model JACKPOT serves. Don't replace any of them.**

> **What's missing from JACKPOT is Loculus's *pluggability layer*** — the HTTP contract that lets operators add their own organism-specific validators (and swap host-removal tools, swap PII scanners) without forking the backend. That's the highest-leverage adoption candidate.

> **What's also missing is a real INSDC import workflow.** The current `POST /ingest/accession` is a stub by Loculus standards. Lifting Loculus's `ingest/Snakefile` clean-room into `pipelines/insdc-ingest/` gets JACKPOT a production-quality NCBI-Datasets-CLI-based importer for free.

---

## 12. Code adoption recommendations

These are ordered by ROI and aligned with the post-Phase-11 / post-P0d / post-P0e roadmap.

### A1. Steal Loculus's preprocessing HTTP contract (highest-leverage)

**Status: Adopt — Year 1 / post-P0e**

Don't switch to a separate-service architecture overnight. But **expose the same `/extract-unprocessed-data` and `/submit-processed-data` HTTP endpoints right alongside the current in-process validation.** Operators can either rely on the in-process default validators OR plug in their own pipeline that calls those endpoints. JACKPOT keeps default behavior; sophisticated operators get extensibility.

This is the **single biggest architectural lift available**, and it's surprisingly cheap because the contract is already defined: `preprocessing/specification.md` is 192 lines and you can copy the schema directly.

Sketch of `backend/routers/preprocessing.py`:

```python
"""
Loculus-compatible preprocessing pipeline interface.

Allows external preprocessing pipelines (per-organism validators, alignment,
clade calling, host-read removal, metadata PII scanning) to pull unprocessed
JACKPOT samples and push back processed data with errors/warnings. Modeled
directly on the Loculus preprocessing specification
(preprocessing/specification.md, AGPL-3.0).
"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.auth.guards import require_preprocessing_pipeline
from backend.db import get_db
from backend.models import Sample

router = APIRouter(prefix="/api/v1/preprocessing", tags=["preprocessing"])


@router.post("/extract-unprocessed-data")
async def extract_unprocessed_data(
    number_of_sequence_entries: Annotated[int, Query(ge=1, le=10_000)],
    pipeline_version: Annotated[int, Query(ge=1)],
    organism: Annotated[str, Query()],
    db: Session = Depends(get_db),
    user=Depends(require_preprocessing_pipeline),
):
    """Pull up to N unprocessed sample-entries as NDJSON.

    Mirrors Loculus contract:
    https://github.com/loculus-project/loculus/blob/main/preprocessing/specification.md
    """
    if pipeline_version < _current_pipeline_version_for(organism):
        raise HTTPException(
            status_code=422,
            detail=f"Pipeline version {pipeline_version} is outdated.",
        )

    samples = (
        db.query(Sample)
        .filter(Sample.organism_name == organism)
        .filter(Sample.preprocessing_status == "PENDING")
        .limit(number_of_sequence_entries)
        .all()
    )

    def stream_ndjson():
        for sample in samples:
            yield _sample_to_unprocessed_ndjson_line(sample) + "\n"

    return StreamingResponse(
        stream_ndjson(),
        media_type="application/x-ndjson",
    )


@router.post("/submit-processed-data")
async def submit_processed_data(
    pipeline_version: Annotated[int, Query(ge=1)],
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_preprocessing_pipeline),
):
    """Accept processed data + errors/warnings as NDJSON.

    Each line is a sample-entry result; backend persists processed metadata,
    aligned/translated sequences, errors, and warnings.
    """
    async for line in request.stream():
        if not line.strip():
            continue
        result = _parse_processed_ndjson_line(line)
        _persist_processed_result(db, result, pipeline_version)
    db.commit()
    return {"accepted": True}


def _current_pipeline_version_for(organism: str) -> int:
    """Return the current pipeline version for an organism."""
    # Lookup from organism config or DB
    raise NotImplementedError("Stub — wire to organism config in P1")


def _sample_to_unprocessed_ndjson_line(sample: Sample) -> str:
    """Render a Sample as a Loculus-spec unprocessed JSON line."""
    raise NotImplementedError("Stub — Phase TBD")


def _parse_processed_ndjson_line(line: bytes) -> dict:
    """Parse an NDJSON line into the processed-data shape."""
    raise NotImplementedError("Stub — Phase TBD")


def _persist_processed_result(db: Session, result: dict, version: int) -> None:
    """Persist processed metadata + sequences + errors/warnings."""
    raise NotImplementedError("Stub — Phase TBD")
```

A researcher running mpox surveillance can then write a `jackpot-preprocessing-mpox` Docker image, point it at their JACKPOT instance, and have it process every mpox sample with their custom logic. Same operator can also choose not to deploy any pipeline and just use in-process validation. **This is the federation-friendly way.**

### A2. Steal Loculus's structured error/warning schema for `ValidationResult`

**Status: Adopt — Year 1 / can land in any Claude Code session**

JACKPOT's current `ValidationResult` should adopt Loculus's two-fields error model. This is a strict superset of what JACKPOT does today, plus the dual-field-ref structure makes UI errors way better.

```python
"""
Loculus-compatible structured error/warning schema for JACKPOT
ValidationResult. Adopted from
https://github.com/loculus-project/loculus/blob/main/preprocessing/specification.md
"""
from typing import Literal
from pydantic import BaseModel


class FieldRef(BaseModel):
    """Reference to a field in unprocessed or processed data."""

    type: Literal["Metadata", "NucleotideSequence"]
    name: str


class ProcessingIssue(BaseModel):
    """A single error or warning emitted by validation.

    The unprocessedFields field(s) specify the source of the error — which
    field of the user's input caused it. The processedFields field(s)
    specify which processed-output fields are affected. Either may be empty
    if the error is general.
    """

    unprocessed_fields: list[FieldRef] = []
    processed_fields: list[FieldRef] = []
    message: str


class ValidationResult(BaseModel):
    """Result of validating a sample submission.

    Backwards-compatible superset of JACKPOT's prior ValidationResult.
    Adds structured errors/warnings; preserves tier semantics; adds
    validator_version for reprocessing semantics (see A5).
    """

    tier: int
    tier2_missing: list[str] = []
    tier3_missing: list[str] = []
    errors: list[ProcessingIssue] = []
    warnings: list[ProcessingIssue] = []
    surveillance_relevant: bool | None = None
    validator_version: int = 1
```

### A3. Adopt Loculus's `ingest/` Snakemake workflow as JACKPOT's INSDC import path

**Status: Adopt — P0d (when monorepo restructure happens) or just after**

JACKPOT's current `POST /api/v1/ingest/accession` uses E-utilities + fasterq-dump and runs as a backend background job. Loculus's `ingest/` is a standalone Snakemake workflow that does the same job better:

- Uses NCBI Datasets CLI (richer metadata bundles than E-utilities)
- Handles segmented genomes natively (`group_segments.py`)
- Has dedicated filtering steps before submission
- Separates "fetch" from "submit" cleanly
- Resumable via Snakemake's checkpoint system

**Concrete plan:** under the new monorepo's `pipelines/` directory, add `pipelines/insdc-ingest/` which is a clean-room reuse of Loculus's `ingest/Snakefile` adapted to JACKPOT's submission API. AGPL-3.0 → AGPL-3.0, no friction.

### A4. NDJSON streaming for CSV batch ingest

**Status: Adopt — Year 1 / Claude Code session**

When `POST /api/v1/ingest/csv` accepts a 100k-row CSV, currently it loads all rows in memory before validating. Switch to NDJSON streaming and validate row-by-row. Memory drops from O(N) to O(1). Loculus's spec is the cleanest reference implementation around.

### A5. Pipeline versioning for validation logic

**Status: Adopt — pairs with A1**

Right now if you change `validator.py`, prior `ValidationResult`s become stale. Add a `validator_version` integer to `ValidationResult` (already in the A2 schema above) and bump it whenever validator logic changes meaningfully. Background job re-validates with new version. Auto-promotes the version once everything is reprocessed. Modeled on Loculus's `pipelineVersion`.

### A6. Adopt the Loculus CLI patterns for `jackpot submit`

**Status: Adopt — P0e**

When P0e adds the real `jackpot` CLI (`jackpot init`, `jackpot bootstrap`, etc.), include `jackpot submit`, `jackpot revise`, `jackpot revoke` modeled on Loculus's `cli/` patterns. Same auth flow, same NDJSON-over-HTTP submission, same group/lab semantics.

This is much smaller scope than A1/A3 — just patterns to mimic, not code to lift. Loculus CLI is Python AGPL-3.0 so direct adoption is also fine if the patterns map cleanly to JACKPOT's auth model.

### What NOT to adopt

#### N1. Don't switch to fully external preprocessing as the *default*

Loculus's separate-service preprocessing is great for pluggability but **bad for UX on small deployments.** A laptop user (Scenario A laptop case) doing a single sample upload doesn't want to wait 30 seconds for the preprocessing pipeline to poll, process, and push back. Keep in-process validation as the default. Add the HTTP endpoints (A1) as an opt-in for sophisticated deployments.

#### N2. Don't drop tier-aware validation in favor of Loculus's binary required-or-not model

Tier-aware is genuinely better for real-world surveillance. Loculus's model assumes data submission is a careful curated act; JACKPOT recognizes that lab workflows submit incomplete data routinely.

#### N3. Don't replace `file_detector.py`

Loculus has nothing equivalent. JACKPOT's content-sniffing is a real differentiator. Keep Critical Rule 20.

#### N4. Don't replace `dlp_scanner.py`

Loculus has nothing equivalent. PHI/PII risk is real for the operator profiles JACKPOT is targeting.

#### N5. Don't replace the SRA Human Scrubber integration

Loculus has nothing equivalent. WHO/IPSN attribute 6 compliance + the full lifecycle (skip governance, concurrency control, bucket isolation, pipeline gating) is real architecture work that took effort to build. Refactor it as a Loculus-compatible preprocessing pipeline (per A1) — but don't remove it.

---

## 13. Federation & integration tiers

These are concrete wires-and-pipes JACKPOT could build to interoperate with the rest of the ecosystem, ranked by "do this now" → "year 2."

### Tier 0 — Month 3 (basically free)

#### 0a. NCBI Pathogen Detection BigQuery JOIN

Since JACKPOT runs on GCP with a BigQuery analytics warehouse, you can JOIN your data with NCBI's public tables in one SQL query. No API, no copy, no ETL. The four public tables:

```text
ncbi-pathogen-detect.pdbrowser.isolates              # 1.3M+ bacterial isolates
ncbi-pathogen-detect.pdbrowser.isolate_exceptions    # QC failures
ncbi-pathogen-detect.pdbrowser.microbigge            # 20M+ AMRFinderPlus rows
ncbi-pathogen-detect.pdbrowser.bioproject_hierarchy  # BioProject parent/child
```

Plus the GCS buckets `gs://ncbi-pathogen-assemblies` and `gs://ncbi-pathogen-proteins`.

A "Compare to NCBI" feature in the dashboard could be one parameterized SQL query:

```sql
-- For a JACKPOT bacterial sample, find the NCBI SNP cluster (PDS#) it most
-- closely matches by AMR profile, plus its national-cluster size and KPC %.
SELECT
  jackpot.sample_id,
  ncbi.erd_group,
  ncbi.PDS_acc                                AS ncbi_snp_cluster,
  COUNT(DISTINCT ncbi.target_acc)             AS cluster_size,
  ROUND(SUM(CASE WHEN EXISTS(
    SELECT 1 FROM UNNEST(ncbi.AMR_genotypes) g
    WHERE g.element LIKE 'blaKPC%') THEN 1 ELSE 0 END)
    / COUNT(*) * 100, 1)                      AS pct_kpc
FROM `<jackpot-project>.jackpot.samples` AS jackpot
JOIN `ncbi-pathogen-detect.pdbrowser.isolates` AS ncbi
  ON jackpot.organism_name = ncbi.scientific_name
 AND ARRAY_TO_STRING(jackpot.amr_genes, ',') LIKE '%' || ncbi.AMR_genotypes_core[OFFSET(0)].element || '%'
WHERE jackpot.organism_name IN ('Salmonella enterica', 'Escherichia coli', 'Klebsiella pneumoniae')
GROUP BY jackpot.sample_id, ncbi.erd_group, ncbi.PDS_acc
ORDER BY cluster_size DESC
LIMIT 50;
```

This is the highest-ROI integration in the entire matrix. Pull the PDS# cluster IDs into a column on `samples`, surface in researcher dashboard, and you've added national outbreak context for bacterial isolates with **a single query**.

#### 0b. AMRFinderPlus harmonization layer

Every JACKPOT bacterial pipeline that detects AMR should **emit hAMRonization-format JSON** alongside its native output. PHA4GE has converged on this. Wraps any AMR tool — abricate, AMRFinderPlus, RGI, ResFinder, staramr, etc. — in a unified schema.

Example pattern in a Nextflow process for AMRFinderPlus:

```bash
amrfinder -n contigs.fasta -o amr_raw.tsv --threads 8
hamronize amrfinderplus amr_raw.tsv \
    --format tsv \
    --output amr_hamronized.tsv \
    --analysis_software_version "$(amrfinder --version)" \
    --reference_database_version "$(amrfinder --database_version)" \
    --input_file_name "${sample_id}"
```

Then `pipeline_results_loader.py` indexes the harmonized TSV into a `samples.amr_genes_harmonized` JSONB column. Cross-platform comparison across all AMR pipelines gets free.

The hAMRonization workflow currently runs and standardizes output from: **abricate, AMRFinderPlus, ariba, Groot, RGI (+ RGI BWT for metagenomes), staramr, resfams, ResFinder/PointFinder, sraX, DeepARG, CSSTAR, AMRplusplus, SRST2, KmerResistance**.

### Tier 1 — Month 3 / early Year 2

#### 1a. Lift the Loculus `ena-submission` module wholesale

The `ena-submission` directory in the Loculus repo is Python and AGPL-3.0. With JACKPOT now also AGPL-3.0, this is **directly adoptable** as JACKPOT's ENA broker. Replaces JACKPOT's planned but unbuilt ENA-broker work.

#### 1b. Adopt Loculus per-sample data-use terms UI pattern

Schema already supports it (`data_use_terms`, `embargo_release_date`, `citation_request`). Streamlit upload page just needs a radio button: `OPEN | RESTRICTED until <date>` and the auto-INSDC trigger when OPEN is selected. Maybe an afternoon of work.

#### 1c. Pathoplexus-style governance-as-code

This is the most overlooked thing. Pathoplexus committed governance docs to GitHub — Statutes, Values, Executive Board roster, COI policy. WHO/IPSN's 2025 11-attribute framework explicitly requires this. JACKPOT should add a `governance/` directory at the repo root:

```text
governance/
├── charter.md
├── coi-policy.md
├── jurisdiction-and-data-residency.md
├── benefits-sharing-framework.md
├── access-grievance-procedure.md
├── platform-shutdown-data-portability-plan.md
└── advisory-board.md
```

With Midnight-Oil-Innovation as the legal entity, you can adopt these immediately — no committee politics, no contract triangles. Trivial engineering effort. **Major credibility lift** for any IPSN/WHO/PABS conversation.

### Tier 2 — Year 2

#### 2a. Pathogenwatch results-pull

For bacterial samples (Salmonella, Klebsiella, Mtb, Neisseria, etc.), upload to Pathogenwatch via API and pull the cgMLST cluster ID, MLST, AMR predictions, and SNP-tree URL back into the JACKPOT `pipeline_results` table. JACKPOT becomes a *compositor* of community-curated typing rather than reimplementing it.

#### 2b. EnteroBase HierCC alignment

For Salmonella and E. coli specifically — push assemblies, pull HierCC hierarchical cluster codes back. These are the bacterial-pathogen equivalent of Pangolin lineages and the public-health community uses them.

#### 2c. LAPIS-compatible JACKPOT viral query API

Once the viral side is mature, expose a LAPIS-compatible REST endpoint. This means **any tool that already speaks to GenSpectrum can query JACKPOT viral data with no client changes**. That's the network effect Pathoplexus is betting on.

### Tier 3 — speculative / Year 2+

#### 3a. RT-MetA collaboration on offline-capable metagenomics

The Brazil project's offline-capable design is the right shape for field-deployable surveillance (rural settings, intermittent connectivity). Email the team — they're IPSN-funded and explicitly looking for collaborators.

#### 3b. Federated-results-tier with another JACKPOT instance

Once federation as a runtime configuration is real (on Scenario A, B, or C) and a second operator deploys, the federation tier in `docs/spec.md` gets exercised. Loculus's group-based ownership model (groups own sequences, users belong to multiple groups) is the closest pattern.

---

## 14. Integration with JACKPOT's roadmap

How each adoption recommendation slots into the existing post-Phase-11 / P0d / P0e / P0b–P0c / P1–P5 sequence:

### During Phase 6.1 → 11 (cosmetic cleanup)

Nothing from this document blocks Phase 6.1–11. These are operator-name-genericization phases that need to land before the architectural rework anyway. If anything, finishing them surfaces every place that touches operator data — useful inventory for the bootstrap CLI.

### During P0d (monorepo migration)

When the six legacy `gotero/*` repos collapse into `Midnight-Oil-Innovation/jackpot`, add three new top-level directories:

| New directory | Purpose | Source |
|---|---|---|
| `pipelines/insdc-ingest/` | NCBI Datasets CLI Snakemake import workflow (A3) | Clean-room from `loculus-project/loculus/ingest/` |
| `governance/` | WHO/IPSN-attribute-1-compliant governance docs (1c) | Modeled on Pathoplexus governance |
| `preprocessing-examples/` | Reference pipelines for A1 (when implemented) — empty placeholder for now | TBD |

Update README.md to link to these.

### During P0e (install/CLI architecture)

The `jackpot init` work in P0e is the right moment for **A6** (Loculus-pattern submitter CLI commands). Add `jackpot submit`, `jackpot revise`, `jackpot revoke` alongside `jackpot init`, `jackpot bootstrap`, `jackpot upgrade`, `jackpot dev`, `jackpot seed`.

The submitter-CLI patterns from Loculus are well-tested — copy auth flow, NDJSON-over-HTTP submission, group/lab semantics.

### During P0b (Schema v5.0)

Schema v5.0 already adds `instances`/`tenants`/`federated_peers` tables. Add at the same time:

- `preprocessing_pipelines` table — tracks deployed pipeline versions per organism
- `samples.preprocessing_status` enum — `PENDING | IN_PROGRESS | PROCESSED | ERROR`
- `samples.preprocessing_pipeline_version` int
- Migration from existing `validator.py` runs to `preprocessing_status = PROCESSED, validator_version = 1`

This is ~200 lines of Alembic migration plus a bit of model code.

### During P1 (operator-type configurability)

Land **A1** (preprocessing HTTP contract) here. Operators choosing which preprocessing pipelines to deploy (or whether to use defaults) is fundamentally an operator-configurability decision. Include the `/extract-unprocessed-data` and `/submit-processed-data` endpoints from Section 12.

Ship the in-process validators as the default for Scenario A (laptop case) — they keep latency low and don't require a separate pipeline service. Cloud and multi-tenant scenarios (Scenario C, or Scenario A in multi-org/SaaS-style configuration) can opt into external pipelines.

### Concrete to-do items to add to `todo.md`

> **Note:** This is a partial list covering Sections 12-13 only (14 items). The **complete consolidated list of all 34 backlog items** — including the 20 from Section 17's other-8-platforms analysis — lives in Section 17.10. For copy-paste into `todo.md`, use that one.

```text
[ ] B-LOC-1   Lift Loculus ena-submission/ as JACKPOT ENA broker.
              AGPL-3.0 → AGPL-3.0 frictionless. Effort: 1-2 sessions.
              Phase: P0d or after.

[ ] B-LOC-2   Lift Loculus ingest/Snakefile clean-room as
              pipelines/insdc-ingest/. NCBI Datasets CLI based.
              Effort: 2-3 sessions. Phase: P0d.

[ ] B-LOC-3   Add backend/routers/preprocessing.py implementing the
              Loculus /extract-unprocessed-data and /submit-processed-data
              HTTP contract. Effort: 2-3 sessions.
              Phase: P1.

[ ] B-LOC-4   Update ValidationResult to Loculus structured error/warning
              schema (FieldRef, ProcessingIssue, validator_version).
              Effort: 1 session. Phase: any.

[ ] B-LOC-5   Switch CSV ingest to NDJSON streaming (memory O(N) → O(1)).
              Effort: 1 session. Phase: any.

[ ] B-LOC-6   Add validator_version and reprocessing background job.
              Modeled on Loculus pipelineVersion auto-promotion.
              Effort: 1-2 sessions. Phase: with B-LOC-3.

[ ] B-LOC-7   Add jackpot submit/revise/revoke CLI commands modeled on
              Loculus cli/. Effort: 2 sessions. Phase: P0e.

[ ] B-NCBI-1  BigQuery JOIN for NCBI Pathogen Detection — surface PDS#
              cluster IDs and MicroBIGG-E AMR results in samples table.
              Effort: 2 sessions. Phase: post-staging-cutover.

[ ] B-NCBI-2  hAMRonization output mandate for all AMR pipelines in
              the zoo. Effort: 1 session per pipeline.
              Phase: pipeline zoo work.

[ ] B-GOV-1   Create governance/ directory with charter.md, coi-policy.md,
              jurisdiction-and-data-residency.md,
              benefits-sharing-framework.md, access-grievance-procedure.md,
              platform-shutdown-data-portability-plan.md, advisory-board.md.
              Modeled on Pathoplexus governance docs. Effort: 3-5 hours
              of writing. Phase: P0d (committed alongside monorepo).

[ ] B-PWATCH-1 Pathogenwatch results-pull for bacterial samples (Salmonella,
              Klebsiella, Mtb, Neisseria). Push assembly via API, pull
              cgMLST/MLST/AMR/SNP-tree results back into pipeline_results.
              Effort: 3-4 sessions. Phase: Year 2.

[ ] B-EBASE-1 EnteroBase HierCC pull for Salmonella and E. coli.
              Effort: 2-3 sessions. Phase: Year 2.

[ ] B-LAPIS-1 Expose LAPIS-compatible REST endpoint for JACKPOT viral data.
              Effort: 1-2 weeks. Phase: Year 2.

[ ] B-PPX-1   Adopt per-sample OPEN/RESTRICTED radio button on Streamlit
              upload page. Schema already supports it; just wire UI.
              Effort: half a session. Phase: any.
```

---

## 15. Top actionable takeaways

If only five things land out of this document:

1. **NCBI Pathogen Detection on BigQuery is the highest-ROI integration in the entire matrix.** JACKPOT runs on GCP. One SQL query gets bacterial outbreak context. Schedule for Month 3 — `B-NCBI-1` in `todo.md`.

2. **Adopt the Loculus per-sample OPEN/RESTRICTED submission pattern (`B-PPX-1`).** The schema already supports it; only the Streamlit upload UI needs the radio button. Maybe an afternoon of work, tied directly to the `data_use_terms` enum already in the schema.

3. **Mandate hAMRonization output from every AMR pipeline-zoo entry (`B-NCBI-2`).** This is the PHA4GE/IPSN-aligned standard. Costs almost nothing in the Nextflow processes; makes cross-pipeline AMR comparison and downstream MicroBIGG-E joins free.

4. **Add a `governance/` directory and start filling it (`B-GOV-1`).** Document-work, not engineering work. WHO/IPSN attribute 1 compliance. Pathoplexus's governance docs are the template. Trivial effort, major credibility lift.

5. **Land the Loculus preprocessing HTTP contract (`B-LOC-3`) at P1.** The single biggest architectural lift available. ~200 lines of new code. Lets external contributors add organism-specific validators, host-removal tools, and PII scanners without forking JACKPOT's backend. Also positions JACKPOT in the same software-extensibility tier as Loculus — important for any future federation conversation.

---

## 16. Appendix

### 16.1 Verified license-by-platform table

| Platform | License | Notes |
|---|---|---|
| **Loculus** (`loculus-project/loculus`) | **AGPL-3.0** | Confirmed in repo LICENSE |
| **GenSpectrum LAPIS** (`GenSpectrum/LAPIS`) | **AGPL-3.0** | Confirmed |
| **GenSpectrum LAPIS-SILO** (Rust query engine) | **AGPL-3.0** | Confirmed in org listing |
| **GenSpectrum dashboard-components** (embeddable widgets) | **AGPL-3.0** | Confirmed |
| **GenSpectrum cov-spectrum-website** | GPL-3.0 | Slightly weaker than the engine |
| **Pathogenwatch pipeline** (CGPS) | **GPL-3.0** | Confirmed in their FAQ |
| **Pathogenwatch components** (`pathogenwatch-oss/*`) | Mixed OSS — varies per repo | Need to check each (`mlst`, `speciator`, `vista`, `inctyper`, `amr-search`, etc.) |
| **EnteroBase** | Academic / restricted | Code not fully open; service is free |
| **NCBI Pathogen Detection** | **Public domain** (US Gov work) | NCBI software broadly is |
| **BV-BRC components** (`BV-BRC/*`) | **MIT** (most components) | Confirmed in repo listing — Perl + Python + Node.js, all MIT |
| **Solu** | **Closed-source commercial** | $1.08M Lifeline Ventures, BAA-capable |
| **RT-MetA** | Open (likely MIT or similar — early-stage) | Need to verify |
| **GISAID** | **Closed-source** + Database Access Agreement | The thing everyone's reacting to |
| **JACKPOT (now)** | **AGPL-3.0** | Newly switched from Apache 2.0 in this session |

### 16.2 Pathoplexus governance docs as a template

Pathoplexus publishes:

- **Statutes** — formal incorporation document for the non-profit association. Defines membership, voting rights, board composition, dissolution procedures.
- **Values** — what the project commits to (open, transparent, equitable).
- **Executive Board roster** — five members from North America, South America, Africa, Asia, Europe.
- **Scientific Advisory Boards** — domain experts.

For Midnight-Oil-Innovation/jackpot, the equivalent docs are simpler because it's a single-owner project for now:

```text
governance/
├── charter.md                      Why JACKPOT exists, what it's for
├── coi-policy.md                   Conflict-of-interest disclosure
├── jurisdiction-and-data-residency.md
│                                   Where the project is hosted, applicable
│                                   law, data-residency commitments
├── benefits-sharing-framework.md   How operators using JACKPOT share
│                                   benefits (citations, collaborations,
│                                   data-back-to-source)
├── access-grievance-procedure.md   How to raise concerns about access
│                                   decisions or governance
├── platform-shutdown-data-portability-plan.md
│                                   What happens if the maintainer / Midnight-Oil
│                                   stops maintaining JACKPOT — guarantee
│                                   that data and code stay accessible
└── advisory-board.md               Forward-looking: how the project will
                                    add governance plurality as it grows
```

The platform-shutdown-data-portability plan is the one that actually distinguishes a credible public-good project from vaporware. Pathoplexus implicitly has this through Loculus open-sourcing; JACKPOT can make it explicit.

### 16.3 Glossary

| Term | Definition |
|---|---|
| **AGPL-3.0** | GNU Affero General Public License v3.0. Strong copyleft license that closes the SaaS loophole — network access counts as distribution. |
| **CARD** | Comprehensive Antibiotic Resistance Database. Used by RGI. |
| **cgMLST** | Core genome multi-locus sequence typing. Standard bacterial typing method. |
| **DSI** | Digital Sequence Information. Pathogen genomic data as data, governed under PABS. |
| **DUO** | Data Use Ontology (GA4GH). Standardized codes for data-access conditions. |
| **HierCC** | Hierarchical Clustering of cgMLST. EnteroBase's bacterial outbreak detection method. |
| **HRRT** | Human Read Removal Tool. Shorthand for NCBI's SRA Human Scrubber. |
| **IPSN** | International Pathogen Surveillance Network. WHO-coordinated, 350+ partners across 100+ countries. |
| **LAPIS** | Lightweight API for Sequences. GenSpectrum's REST API for pathogen sequence queries. |
| **LinkML** | Linked Data Modeling Language. JACKPOT's source-of-truth schema language. |
| **NDJSON** | Newline-delimited JSON. One JSON object per line. Streamable. |
| **PABS** | Pathogen Access and Benefit-Sharing. Annex of WHO Pandemic Agreement (2025). |
| **PDS#** | Pathogen Detection SNP-cluster accession. NCBI's outbreak-cluster identifier. |
| **PHA4GE** | Public Health Alliance for Genomic Epidemiology. Standards body. |
| **SILO** | Loculus's Rust in-memory database engine (LAPIS backend). |
| **WGS** | Whole-genome sequencing. |

### 16.4 Cross-references to past work

| Topic | Where it was first developed |
|---|---|
| Original platform-comparison matrix (state-deployment framing) | `Open source alternatives to Jackpot` chat (2026-04-28) |
| Original pivot announcement (independence + AGPL-3.0 + multi-deployment) | This session, first message after `jackpot_session_summary_and_backlog.md` upload |
| Original Loculus repo audit (architecture, languages, license) | This session, thread B fetches |
| Two-PII-gate architecture (scrubber + DLP) | `docs/architecture.md` v6.0 (post-Cluster-A merge) — see also `docs/spec.md` for the operational detail |
| Pluggable preprocessing recommendation (A1) | This session, first version of comparison |
| Other-8-platforms recommendations (Section 17) | This session, follow-up to thread B |

---

## 17. What to lift from the other 8 platforms

Sections 2-15 went deep on the JACKPOT-Loculus relationship because they're structural twins — both open-source software packages designed for multi-operator deployment in pathogen genomics. The remaining question is what's worth lifting from the other peer platforms in Section 5's matrix.

This section goes platform by platform, surfacing only ideas that *aren't* already covered by recommendations in Sections 12-13 and that fit JACKPOT's multi-deployment design. For each I flag effort and phase placement, then synthesize at the end.

### 17.1 GenSpectrum + LAPIS

#### 17.1a SILO-style in-memory query engine for hot-path queries — *probably skip*

The reason GenSpectrum can serve 20M requests in 10 days with median 1ms response time is SILO, their custom Rust in-memory database. JACKPOT's PostgreSQL backend will hit a wall well before that scale, but **probably not in JACKPOT's actual operating range** (hundreds of thousands of samples per instance, not millions). Skip unless you ever target federation-scale queries.

#### 17.1b Dashboard-components — *adopt for Year 2 frontend*

`GenSpectrum/dashboard-components` is a TypeScript library of embeddable widgets for variant tracking, mutation prevalence, and lineage breakdown. AGPL-3.0. Directly droppable into a future React-based JACKPOT frontend.

```text
[ ] B-GS-1   Embed GenSpectrum dashboard-components for viral variant
             tracking when JACKPOT migrates from Streamlit to React.
             AGPL-3.0 → AGPL-3.0. Effort: 3-5 sessions.
             Phase: Year 2 (post-Streamlit migration).
```

#### 17.1c URL-encoded queries (everything is a shareable URL) — *adopt now, very cheap*

GenSpectrum's killer UX feature: every dashboard view is a URL. Copy-paste it to a colleague, they see the same filtered/aggregated/visualized state. JACKPOT's Streamlit doesn't do this — `st.query_params` is supported but underused.

```text
[ ] B-GS-2   Make all JACKPOT search/filter/dashboard state URL-encoded
             via st.query_params, so any view is shareable. Effort: 1-2
             sessions, scattered across all Streamlit pages. Phase: any.
```

#### 17.1d Public read-only LAPIS endpoint as a community good — *Year 2 strategic move*

GenSpectrum runs a free, anonymous, no-auth LAPIS endpoint at `lapis.cov-spectrum.org`. Anyone can query SARS-CoV-2 sequences via simple URL, get JSON/CSV/TSV back. Built community goodwill. JACKPOT doing the same (read-only, anonymous, public-data-only) for whatever pathogens its instances host would be a meaningful "we're not GISAID" signal. Pairs naturally with B-LAPIS-1 from Section 14.

### 17.2 Pathogenwatch

#### 17.2a Per-pathogen typing tools as pipeline-zoo entries — *high-priority adopt*

This is the biggest find. `pathogenwatch-oss/*` has a stack of well-maintained, single-purpose Docker containers, each released under OSS license:

| Tool | Purpose | License | Pipeline-zoo fit |
|---|---|---|---|
| `pathogenwatch-oss/speciator` | Mash-based species ID against curated reference library | OSS | **Yes — core building block** |
| `pathogenwatch-oss/mlst` | MLST/cgMLST/ngMAST/Pasteur scheme assignment via hash + BLAST | OSS | **Yes** |
| `pathogenwatch-oss/vista` | *V. cholerae* genotyping | OSS | Yes for cholera |
| `pathogenwatch-oss/amr-search` | AMR detection against curated library | OSS | Yes |
| `pathogenwatch-oss/amr-libraries` | Curated AMR library data (S. aureus, N. gonorrhoeae, etc.) | OSS | **Yes — drop in as reference data** |
| `pathogenwatch-oss/inctyper` | Plasmid Inc-typing | OSS | Yes for plasmid surveillance |
| `pathogenwatch-oss/seroba` | *S. pneumoniae* serotyping | OSS | Yes for pneumococcal surveillance |
| `pathogenwatch-oss/hclink` | Hash-based linking | OSS | Useful infrastructure |

Each container takes FASTA on stdin, emits JSON on stdout. Drop-in fit for JACKPOT's pipeline zoo as Level-1 entries (curated launch catalog).

```text
[ ] B-PW-1   Add pathogenwatch-oss/speciator as a Level-1 pipeline-zoo
             entry — Mash-based species ID. Effort: 1 session. Phase: any
             pipeline-zoo work.

[ ] B-PW-2   Add pathogenwatch-oss/mlst as Level-1 zoo entry — MLST/cgMLST
             per-pathogen schemes. Effort: 1-2 sessions. Phase: same.

[ ] B-PW-3   Vendor pathogenwatch-oss/amr-libraries as JACKPOT reference
             data under reference-data/amr-libraries/. Effort: 1 session.
             Phase: P0d.

[ ] B-PW-4   Add seroba (pneumococcus), vista (cholera), inctyper
             (plasmid Inc) as zoo entries when relevant pathogens come
             into scope. Effort: 1 session each.
```

The first two alone would close two of the biggest gaps in JACKPOT's bacterial pipeline coverage that we identified in the matrix.

#### 17.2b Phylocanvas + Leaflet integration pattern — *adopt for dashboards*

Pathogenwatch's collection-view UX integrates a phylogenetic tree (Phylocanvas) with an interactive map (Leaflet) and a metadata table. Click a leaf in the tree → highlight in map + table. Click a country in the map → highlight in tree + filter table. Bidirectional, fast.

JACKPOT's current Streamlit pages don't have this. When you migrate to React, the Phylocanvas + Leaflet combo is the canonical pattern.

```text
[ ] B-PW-5   Phylocanvas + Leaflet + metadata-table tri-pane for
             collection visualizations. Effort: 1-2 weeks. Phase: Year 2
             React migration.
```

#### 17.2c WHO bacterial priority pathogens dedicated section — *quick win*

Pathogenwatch has a dedicated landing page for the WHO Bacterial Priority Pathogens List (BPPL 2024). For each priority pathogen, it shows: number of public genomes, available typing schemes, AMR landscape, recent outbreaks. JACKPOT could add the same — surfacing how the platform supports each WHO priority pathogen. Aligns with WHO/IPSN attribute 4 (Data scope).

```text
[ ] B-PW-6   Add a /priority-pathogens dashboard page that maps WHO BPPL
             2024 to JACKPOT's organism enum, showing samples count,
             supported typing schemes, AMR support per pathogen.
             Effort: 1 session. Phase: any.
```

### 17.3 EnteroBase

#### 17.3a HierCC hierarchical clustering codes — *adopt for bacterial outbreak detection*

This was already in the prior doc as `B-EBASE-1` (results-pull). The deeper architectural idea is the **HierCC concept itself** — hierarchical cluster codes that nest at multiple SNP-distance thresholds (HC0, HC2, HC5, HC10, HC20, HC50, HC100, HC200, HC400, HC900, HC2000) so two isolates' codes immediately tell you their genetic relatedness scale.

Two implementation paths:

- **Lightweight:** Pull HierCC codes from EnteroBase's API for samples that match their species coverage, store in `samples.entero_hiercc_codes`. (This is `B-EBASE-1`.)
- **Native:** Compute JACKPOT's own hierarchical cluster codes for any cgMLST-typed sample. Way more work but means JACKPOT becomes useful for pathogens EnteroBase doesn't cover.

```text
[ ] B-EB-2   Implement native hierarchical clustering codes (JACKPOT-HC)
             for any cgMLST-typed bacterial sample. Use 11 distance
             thresholds matching EnteroBase HierCC. Effort: 2-3 weeks.
             Phase: Year 2.
```

The native path is also the basis for federation — two JACKPOT instances can compare HC2 codes to detect cross-instance outbreaks without sharing raw sequences.

#### 17.3b Daily SRA auto-scrape pipeline — *Year 2 stretch goal*

EnteroBase scans NCBI SRA daily for newly published bacterial sequencing data, auto-ingests anything matching their species list. This is *opt-in for the operator* — Pathoplexus-style INSDC ingest but daily and continuous instead of one-shot.

JACKPOT could offer this as a `pipelines/insdc-daily-scan/` pipeline that operators turn on for their organisms of interest.

```text
[ ] B-EB-3   Add pipelines/insdc-daily-scan/ — daily Snakemake job that
             scans NCBI SRA for new sequences matching the operator's
             organism enum, auto-ingests via the same INSDC import
             workflow as B-LOC-2. Operator-opt-in.
             Effort: 1 week. Phase: Year 2.
```

#### 17.3c GrapeTree — *probably skip; covered by Phylocanvas*

EnteroBase's GrapeTree visualization is good but Pathogenwatch's Phylocanvas is more general-purpose and has broader community adoption. Pick one — go Phylocanvas (B-PW-5).

### 17.4 NCBI Pathogen Detection (on GCP)

#### 17.4a BigQuery JOIN — *already covered as B-NCBI-1*

Tier 0 in Section 13, top-5 takeaway in Section 15. No change.

#### 17.4b PDS# SNP-cluster accession system — *adopt for outbreak identifiers*

Beyond the BigQuery JOIN, the architectural idea worth lifting is the **versioned outbreak cluster accession system itself**. Every NCBI SNP cluster gets a stable `PDS#######.version` ID, the version increments on changes, and trees are stored alongside in `.newick`, `.pdf`, `.asn` formats.

JACKPOT should mint analogous accessions for clusters it computes locally — `JKPT#######.version` or similar. Stable, citeable, versioned. Lets a researcher reference "outbreak JKPT00000123.7 in our paper" with the same persistence guarantee as a BioSample accession.

```text
[ ] B-NCBI-3 Mint stable JACKPOT cluster accessions (JKPT-prefixed,
             versioned) for any cgMLST/SNP cluster computed by the
             platform. Persist tree representations in newick + JSON.
             Effort: 1 week. Phase: Year 2 (with cgMLST clustering work).
```

#### 17.4c Daily reprocessing cadence — *good ops pattern*

NCBI Pathogen Detection re-runs the entire clustering pipeline daily as new data arrives. JACKPOT's current model is per-sample pipeline runs on user trigger — fine for now, but at scale you'd want daily background reprocessing too. Modeled on the same pattern as Loculus's auto-promote-on-version-complete (recommendation A1/A5 in Section 12).

### 17.5 BV-BRC

#### 17.5a Async job queue at proven scale — *adopt patterns, not code*

BV-BRC has run **650K+ jobs averaging 19,716/month** since 2019. That's serious throughput. They use a microservice architecture with explicit async computation:

- Service registry (each analysis service is its own microservice)
- Job queue with priority lanes (fast-track for short jobs like single BLAST)
- Async execution with status polling
- Fault isolation (one service down ≠ platform down)

JACKPOT's current `pipeline_runs` table + Nextflow weblog is on the right track but lighter weight. Worth studying BV-BRC's pattern for when JACKPOT hits scale.

The codebase is MIT-licensed (most components) so direct lifts are AGPL-compatible. But the value here is *patterns* not code:

```text
[ ] B-BVBRC-1 Add a fast-track queue lane for jobs <30s (BLAST,
              single-genome typing) separate from the long-running
              pipeline lane. Modeled on BV-BRC's two-tier queue.
              Effort: 2-3 sessions. Phase: when scale demands it
              (Year 2+).
```

#### 17.5b Private-workspace-then-publish lifecycle — *worth comparing to JACKPOT's model*

BV-BRC users work in a private workspace, can selectively share with collaborators, then "publish" to make data public + citable. JACKPOT has `sharing_level` (PRIVATE, LAB, DISCOVERABLE, PUBLIC) but the *publish* step is implicit — there's no explicit ceremony around making something public-and-citable.

Loculus does this better than BV-BRC actually (group-owned sequences with explicit release). But BV-BRC's *workspace* concept (user's working area, separate from organizational sharing) is cleaner than JACKPOT's current draft-state model.

```text
[ ] B-BVBRC-2 Add explicit "publish" ceremony when transitioning sample
              from DISCOVERABLE to PUBLIC — generates citation block,
              mints persistent identifier, snapshots metadata.
              Effort: 1-2 sessions. Phase: any.
```

#### 17.5c Comparative-genomics tooling — *probably skip*

BV-BRC has a deep stack of comparative genomics tools (subsystems, protein families, metabolic models). Most of these are PATRIC-legacy bacterial work. Not really JACKPOT's lane — JACKPOT is a sample manager + surveillance platform, not a comparative-genomics workbench. Let researchers go to BV-BRC for that.

#### 17.5d CLIv16-style `p3-*` tool family — *pattern reference for `jackpot` CLI*

BV-BRC has a family of `p3-*` command-line tools (`p3-all-genomes`, `p3-get-genome-data`, `p3-submit`, etc.) that compose Unix-style. This is a good pattern reference for the `jackpot` CLI being built in P0e — alongside `jackpot init`, `jackpot bootstrap`, etc., consider a `jackpot-*` family pattern for advanced ops:

```bash
jackpot-all-samples --organism "Salmonella enterica" | jackpot-submit-to-ncbi
jackpot-find-cluster --pds JKPT00000123.7 | jackpot-export --format auspice
```

Each composable, each Unix-pipeable.

### 17.6 Solu

#### 17.6a "FASTQ in, outbreak intel out, in minutes" UX — *aspirational benchmark*

Solu's headline: drop a FASTQ in the browser, get species ID + AMR + phylogeny + outbreak detection in minutes. JACKPOT's path to results is currently slower (upload → scrub → pipeline launch → MultiQC → result viewing).

The architectural question: *should JACKPOT have a "fast-lane" path?* For a Lab Director investigating a suspected outbreak in their hospital, "FASTQ now → answer now" is the workflow that matters. Background scrubbing + slow pipelines are wrong for that use case.

```text
[ ] B-SOLU-1 Design a "rapid triage" pipeline that runs species ID +
             AMR + nearest-neighbour phylogeny in <5 minutes for
             single-sample uploads. Skip MultiQC and other reporting.
             Result is "is this an outbreak strain we've seen?" — yes/no
             plus context. Effort: 2-3 weeks. Phase: Year 2.
```

This is genuinely missing from JACKPOT's pipeline zoo and from Loculus.

#### 17.6b Continuous-surveillance / delta-driven reanalysis — *Year 2 architecture*

Solu's other differentiator: when new samples arrive, it re-runs analysis on existing samples to update phylogeny/clusters, not just analyzing the new ones in isolation. This is the *continuous* in "continuous surveillance."

JACKPOT's `pipeline_results_loader.py` is immutable + append-only, which is good for provenance but means each run is a snapshot. Adding a delta-driven reanalysis layer means: "every time a Salmonella sample lands, re-run the cgMLST clustering across all Salmonella in this lab, update the cluster IDs for everything, post-hoc."

```text
[ ] B-SOLU-2 Add a continuous-surveillance background job that
             re-runs cluster computation on all samples of an organism
             when new samples arrive. Updates samples.cluster_id;
             preserves immutable historical pipeline_results.
             Effort: 1 week. Phase: Year 2.
```

#### 17.6c Trust portal pattern — *adopt for governance/security marketing*

Solu publishes a trust portal at `solugenomics.trust.site` with HIPAA, ISO 27001, SOC 2-style attestations + their security practices in detail. **This is what credible public-health-data platforms look like in 2026.** JACKPOT should have a `trust.jackpot.health` (or similar) page eventually, even if it just documents what's been hardened so far. Pairs naturally with the `governance/` directory work (B-GOV-1).

```text
[ ] B-SOLU-3 Add docs/trust.md (later promoted to trust.jackpot.health
             subdomain) documenting security practices, data residency,
             encryption-at-rest/in-transit, audit log, DLP scanning,
             scrubber, deletion lifecycle. Effort: 4-6 hours of writing.
             Phase: with B-GOV-1.
```

### 17.7 RT-MetA (Brazil, IPSN-funded)

#### 17.7a Offline-capable ingest path — *strategic adopt for field deployments*

RT-MetA's defining feature: works without internet, syncs when online. Designed for rural / LMIC settings where connectivity is intermittent. **This is genuinely missing from every other platform on the list.**

For JACKPOT, offline-capable means:

- Local-first SQLite mode (alongside Postgres for cloud)
- Background sync to a parent JACKPOT instance when online
- Conflict-resolution policy for sync collisions
- Reduced-functionality mode that skips DLP/cloud-only features

This dovetails with Scenario A in its laptop-case configuration — already in the JACKPOT roadmap. RT-MetA is the proof-point that this works in practice for surveillance.

```text
[ ] B-RTMA-1 Reach out to the RT-MetA team about collaboration on
             offline-capable architecture. They're IPSN-funded and
             explicitly looking for collaborators. Effort: 1 email +
             one call. Phase: now.

[ ] B-RTMA-2 Design offline-first mode for Scenario A (laptop case) — SQLite-only
             backend, optional sync-when-online to a parent instance,
             conflict-resolution policy. Effort: 2-3 weeks design,
             more for implementation. Phase: Year 2.
```

#### 17.7b Untargeted metagenomic surveillance — *long-term differentiator*

RT-MetA does *untargeted* metagenomic surveillance — sequence everything in a sample, detect anything pathogenic, no organism-list needed. JACKPOT's current model is targeted (you upload a sample of organism X, run organism-X pipelines).

The untargeted path is much harder (taxonomic classification across all-of-life, false-positive control, reference databases) but is where pathogen surveillance is heading. nf-core/taxprofiler is in JACKPOT's pipeline zoo plan; combining that with RT-MetA's framework would put JACKPOT on the front edge of this trend.

```text
[ ] B-RTMA-3 Year 2+ — adopt RT-MetA's untargeted metagenomics
             framework as a JACKPOT pipeline-zoo entry, paired with
             nf-core/taxprofiler. Effort: 4-6 weeks. Phase: Year 2+.
```

### 17.8 GISAID — the cautionary tale

The cautionary tale, not the model. Three things to learn-from-by-not-emulating:

#### 17.8a NEGATIVE: opaque governance — *the entire point of `governance/` directory*

GISAID's lack of public governance docs is what makes it possible to capriciously cut off Nextstrain (Oct 2025), CoV-Spectrum (Dec 2025), outbreak.info, and various researchers without recourse. Every governance attribute we already recommended (Section 13 of the overview) exists *because* GISAID demonstrated what happens when these don't exist.

#### 17.8b NEGATIVE: closed source — *the entire point of AGPL-3.0*

GISAID's closed source is what makes it un-auditable, un-forkable, and un-replaceable. JACKPOT's AGPL-3.0 stance exists in opposition to this.

#### 17.8c POSITIVE — Acknowledgments / attribution model — *worth adopting*

The one thing GISAID does well: when you use GISAID data, the platform generates a structured Acknowledgments block citing each contributing lab. Encourages submission because submitters get cited. JACKPOT could do the same — when a researcher exports a dataset, auto-generate a citation block with all originating labs, sample IDs, dates of submission.

```text
[ ] B-GISAID-1 When exporting a dataset, auto-generate a structured
               Acknowledgments block citing each originating lab,
               sample IDs, and submission dates. Format aligned with
               Nature/PHA4GE recommended citation conventions.
               Effort: 1-2 sessions. Phase: any.
```

This reinforces the "submit to JACKPOT, get credit" loop that's core to a sustainable surveillance platform.

### 17.9 Synthesis: which to actually do

Sorting by ROI and effort:

#### Top 5 — high-value, low-effort, do soon

1. **`B-PW-1` Speciator** as pipeline-zoo entry. Bacterial species ID is foundational, the tool is mature, drop-in. *1 session.*
2. **`B-PW-2` MLST/cgMLST** as pipeline-zoo entries. Closes a major bacterial gap. *1-2 sessions.*
3. **`B-PW-3` AMR libraries** vendored as reference data. Curated, maintained, well-tested. *1 session.*
4. **`B-GS-2` URL-encoded query state** in Streamlit. Shareable views. *1-2 sessions.*
5. **`B-GISAID-1` Auto-Acknowledgments** on dataset export. Reinforces submission incentive. *1-2 sessions.*

#### Strategic — bigger lifts but high differentiation

6. **`B-RTMA-1` + `B-RTMA-2` Offline-capable architecture.** Aligns with Scenario A in its laptop-case configuration, opens LMIC market, partners with an IPSN-funded peer. *Email now, design Year 2.*
7. **`B-SOLU-1` Rapid triage pipeline.** "FASTQ in, outbreak intel in <5 minutes" is a real workflow gap. *Year 2.*
8. **`B-SOLU-2` Continuous-surveillance reanalysis.** Architectural — re-run clustering on new arrivals. *Year 2.*
9. **`B-EB-2` Native HierCC.** Federation-ready clustering codes. *Year 2.*
10. **`B-NCBI-3` JKPT-prefix cluster accessions.** Citeable, versioned outbreak IDs. *Year 2.*

#### Year 2 frontend / dashboard

11. **`B-GS-1` Embed dashboard-components** for viral variant tracking when you migrate to React.
12. **`B-PW-5` Phylocanvas + Leaflet tri-pane** for collection visualizations.
13. **`B-PW-6` Priority-pathogens landing page** mapped to WHO BPPL 2024.

#### Operational / governance

14. **`B-SOLU-3` Trust portal docs** (`docs/trust.md`).
15. **`B-BVBRC-2` Explicit publish ceremony** with citation generation.

#### Probably skip

- GenSpectrum SILO Rust engine (overkill for JACKPOT's scale)
- BV-BRC comparative-genomics stack (different lane)
- EnteroBase GrapeTree (Phylocanvas is the better choice)

### 17.10 Complete consolidated backlog for `todo.md`

This subsection is the **single canonical list** of every backlog item generated during this analysis — **34 items total**, drawn from Sections 12 (A1-A6 Loculus code-adoption), 12 (federation tiers), 13 (roadmap), and 16 (other-8-platforms). It supersedes the partial list at the end of Section 14, which covered only the Loculus / NCBI / governance subset.

Items are grouped by source platform / pattern. For ROI/priority ranking, see Section 15 (top 5 from across all sections) and Section 17.9 (synthesis ranking specifically for the other-8-platforms items). Copy directly into `todo.md` as a single block, or pull groups individually.

#### A. Loculus code adoption (Section 12 A1-A6, Section 13.1a)

```text
[ ] B-LOC-1   Lift Loculus ena-submission/ as JACKPOT ENA broker.
              AGPL-3.0 → AGPL-3.0 frictionless. Effort: 1-2 sessions.
              Phase: P0d or after.

[ ] B-LOC-2   Lift Loculus ingest/Snakefile clean-room as
              pipelines/insdc-ingest/. NCBI Datasets CLI based.
              Effort: 2-3 sessions. Phase: P0d.

[ ] B-LOC-3   Add backend/routers/preprocessing.py implementing the
              Loculus /extract-unprocessed-data and
              /submit-processed-data HTTP contract.
              Effort: 2-3 sessions. Phase: P1.

[ ] B-LOC-4   Update ValidationResult to Loculus structured error/warning
              schema (FieldRef, ProcessingIssue, validator_version).
              Effort: 1 session. Phase: any.

[ ] B-LOC-5   Switch CSV ingest to NDJSON streaming
              (memory O(N) → O(1)). Effort: 1 session. Phase: any.

[ ] B-LOC-6   Add validator_version and reprocessing background job.
              Modeled on Loculus pipelineVersion auto-promotion.
              Effort: 1-2 sessions. Phase: with B-LOC-3.

[ ] B-LOC-7   Add jackpot submit/revise/revoke CLI commands modeled on
              Loculus cli/. Effort: 2 sessions. Phase: P0e.
```

#### B. NCBI integrations (Sections 13.0, 16.4)

```text
[ ] B-NCBI-1  BigQuery JOIN for NCBI Pathogen Detection — surface PDS#
              cluster IDs and MicroBIGG-E AMR results in samples table.
              Effort: 2 sessions. Phase: post-staging-cutover.

[ ] B-NCBI-2  hAMRonization output mandate for all AMR pipelines in
              the zoo. Effort: 1 session per pipeline.
              Phase: pipeline zoo work.

[ ] B-NCBI-3  Mint stable JACKPOT cluster accessions (JKPT-prefixed,
              versioned) for any cgMLST/SNP cluster computed by the
              platform. Persist tree representations in newick + JSON.
              Effort: 1 week. Phase: Year 2 (with cgMLST clustering work).
```

#### C. Governance & Pathoplexus UI patterns (Section 13.1)

```text
[ ] B-GOV-1   Create governance/ directory with charter.md,
              coi-policy.md, jurisdiction-and-data-residency.md,
              benefits-sharing-framework.md,
              access-grievance-procedure.md,
              platform-shutdown-data-portability-plan.md,
              advisory-board.md. Modeled on Pathoplexus governance docs.
              Effort: 3-5 hours of writing.
              Phase: P0d (committed alongside monorepo).

[ ] B-PPX-1   Adopt per-sample OPEN/RESTRICTED radio button on Streamlit
              upload page. Schema already supports it; just wire UI.
              Effort: half a session. Phase: any.
```

#### D. Pathogenwatch (Sections 13.2a, 16.2)

```text
[ ] B-PWATCH-1 Pathogenwatch results-pull for bacterial samples
               (Salmonella, Klebsiella, Mtb, Neisseria). Push assembly
               via API, pull cgMLST/MLST/AMR/SNP-tree results back into
               pipeline_results. Effort: 3-4 sessions. Phase: Year 2.

[ ] B-PW-1    Add pathogenwatch-oss/speciator as a Level-1 pipeline-zoo
              entry — Mash-based species ID. Effort: 1 session.
              Phase: any pipeline-zoo work.

[ ] B-PW-2    Add pathogenwatch-oss/mlst as Level-1 zoo entry —
              MLST/cgMLST per-pathogen schemes. Effort: 1-2 sessions.
              Phase: any pipeline-zoo work.

[ ] B-PW-3    Vendor pathogenwatch-oss/amr-libraries as JACKPOT
              reference data under reference-data/amr-libraries/.
              Effort: 1 session. Phase: P0d.

[ ] B-PW-4    Add seroba (pneumococcus), vista (cholera), inctyper
              (plasmid Inc) as zoo entries when relevant pathogens come
              into scope. Effort: 1 session each.

[ ] B-PW-5    Phylocanvas + Leaflet + metadata-table tri-pane for
              collection visualizations. Effort: 1-2 weeks.
              Phase: Year 2 React migration.

[ ] B-PW-6    Add /priority-pathogens dashboard page mapping WHO BPPL
              2024 to JACKPOT's organism enum. Effort: 1 session.
              Phase: any.
```

#### E. GenSpectrum / LAPIS (Sections 13.2c, 16.1)

```text
[ ] B-LAPIS-1 Expose LAPIS-compatible REST endpoint for JACKPOT viral
              data. Effort: 1-2 weeks. Phase: Year 2.

[ ] B-GS-1    Embed GenSpectrum dashboard-components for viral variant
              tracking when JACKPOT migrates from Streamlit to React.
              AGPL-3.0 → AGPL-3.0. Effort: 3-5 sessions.
              Phase: Year 2 (post-Streamlit migration).

[ ] B-GS-2    Make all JACKPOT search/filter/dashboard state URL-encoded
              via st.query_params, so any view is shareable.
              Effort: 1-2 sessions, scattered across all Streamlit pages.
              Phase: any.
```

#### F. EnteroBase (Sections 13.2b, 16.3)

```text
[ ] B-EBASE-1 EnteroBase HierCC pull for Salmonella and E. coli.
              Effort: 2-3 sessions. Phase: Year 2.

[ ] B-EB-2    Implement native hierarchical clustering codes (JACKPOT-HC)
              for any cgMLST-typed bacterial sample. Use 11 distance
              thresholds matching EnteroBase HierCC.
              Effort: 2-3 weeks. Phase: Year 2.

[ ] B-EB-3    Add pipelines/insdc-daily-scan/ — daily Snakemake job that
              scans NCBI SRA for new sequences matching the operator's
              organism enum, auto-ingests via the same INSDC import
              workflow as B-LOC-2. Operator-opt-in.
              Effort: 1 week. Phase: Year 2.
```

#### G. BV-BRC (Section 17.5)

```text
[ ] B-BVBRC-1 Add a fast-track queue lane for jobs <30s (BLAST,
              single-genome typing) separate from the long-running
              pipeline lane. Modeled on BV-BRC's two-tier queue.
              Effort: 2-3 sessions. Phase: when scale demands it
              (Year 2+).

[ ] B-BVBRC-2 Add explicit "publish" ceremony when transitioning sample
              from DISCOVERABLE to PUBLIC — generates citation block,
              mints persistent identifier, snapshots metadata.
              Effort: 1-2 sessions. Phase: any.
```

#### H. Solu (Section 17.6)

```text
[ ] B-SOLU-1  Design a "rapid triage" pipeline that runs species ID +
              AMR + nearest-neighbour phylogeny in <5 minutes for
              single-sample uploads. Result is "is this an outbreak
              strain we've seen?" — yes/no plus context.
              Effort: 2-3 weeks. Phase: Year 2.

[ ] B-SOLU-2  Add a continuous-surveillance background job that re-runs
              cluster computation on all samples of an organism when new
              samples arrive. Updates samples.cluster_id; preserves
              immutable historical pipeline_results.
              Effort: 1 week. Phase: Year 2.

[ ] B-SOLU-3  Add docs/trust.md (later promoted to trust.jackpot.health
              subdomain) documenting security practices, data residency,
              encryption-at-rest/in-transit, audit log, DLP scanning,
              scrubber, deletion lifecycle.
              Effort: 4-6 hours of writing. Phase: with B-GOV-1.
```

#### I. RT-MetA (Sections 13.3, 16.7)

```text
[ ] B-RTMA-1  Reach out to the RT-MetA team about collaboration on
              offline-capable architecture. They're IPSN-funded and
              explicitly looking for collaborators.
              Effort: 1 email + one call. Phase: now.

[ ] B-RTMA-2  Design offline-first mode for Scenario A (laptop case) — SQLite-only
              backend, optional sync-when-online to a parent instance,
              conflict-resolution policy.
              Effort: 2-3 weeks design, more for implementation.
              Phase: Year 2.

[ ] B-RTMA-3  Year 2+ — adopt RT-MetA's untargeted metagenomics
              framework as a JACKPOT pipeline-zoo entry, paired with
              nf-core/taxprofiler. Effort: 4-6 weeks. Phase: Year 2+.
```

#### J. GISAID-derived (Section 17.8)

```text
[ ] B-GISAID-1 When exporting a dataset, auto-generate a structured
               Acknowledgments block citing each originating lab,
               sample IDs, and submission dates. Format aligned with
               Nature/PHA4GE recommended citation conventions.
               Effort: 1-2 sessions. Phase: any.
```

---

*End of overview. Review and tell me if anything's missing or wants more depth.*
## 18. What JACKPOT has adopted, and why

This section consolidates JACKPOT's adoption decisions across the full now-23-tool landscape. It complements Section 6 ("Where JACKPOT sits in the matrix") which positions JACKPOT *against* the field; this section traces what's *in* JACKPOT and which prior art each piece came from.

The format is grouped by adoption category (Already shipped / Adopted as patterns / Specifically rejected) and within each, by source.

### 18.1 Already shipped (in production code or schema)

These are concrete artifacts in the JACKPOT codebase or schema that came from this landscape. They're "done" in the sense that the engineering work is committed, not in the sense that they're feature-complete.

| Adoption | Source / inspiration | Where in JACKPOT | Why |
|---|---|---|---|
| **LinkML schema as source of truth** | NMDC, PHA4GE, MIxS conventions; LinkML as a community standard | `jackpot-schema/schema/jackpot_schema.yaml` (v4.4) | None of the 9 surveillance-platform peers use LinkML this aggressively. Schema-first eliminates the drift between DB tables, API validators, DataHarmonizer templates, and Pydantic models. (See Section 5.1's matrix — JACKPOT is the only "✅" in the LinkML column.) |
| **DataHarmonizer for tiered metadata templates** | DataHarmonizer (Mpox package, §5.4.4) | `harmonizer.py`, generated T1/T2/T3 templates per source-type | DataHarmonizer is the de-facto PHA4GE template-entry tool. JACKPOT generates DataHarmonizer-compatible JSON Schema from LinkML; users get an offline-capable browser-based metadata entry UI for free. |
| **NCBI SRA Human Scrubber (genomic PII gate)** | NCBI tool; alignment with WHO Guiding Principle 3 ("human genomic data should be removed before submission") | `nf/ingest_scrubber.nf`, six-state lifecycle in `samples.scrub_status`, skip governance, concurrency control | None of Loculus, GenSpectrum, Pathogenwatch, or BV-BRC have an integrated host-read removal step. This is one of JACKPOT's strongest WHO/IPSN attribute 6 (Data curation) compliance moves. |
| **GCP Cloud DLP (metadata PII gate)** | GCP-native; conceptually inspired by HIPAA-compliance patterns at clinical data platforms | `dlp_scanner.py`, `DLP_ENABLED` toggle, `FIELD_EXCEPTIONS` for known-good PII (e.g. `pi_name`) | No equivalent in any of the 9 surveillance peers. WHO/IPSN attribute 6 again — the metadata-side analog of the genomic PII gate. |
| **GA4GH DUO codes** | GA4GH Data Use Ontology | `samples.data_use_terms` field + `DataUseTermsEnum` (per `docs/architecture.md` v6.0 §11) | Loculus has dual-track (OPEN / RESTRICTED) but not DUO codes. NCBI has partial DUO. JACKPOT is one of the few platforms with full machine-readable data-use restrictions on every dataset. |
| **GA4GH DRS URI scheme** | GA4GH Data Repository Service | Not adopted. `drs://` was recognised by `validator.py` with no client able to dereference it, and rejected on 2026-09-03 (B-DRS-URI-1) | Interoperability with Terra, AnVIL and DRS-aware tools remains desirable, but the scheme returns alongside a real backend rather than ahead of one. |
| **PHA4GE / GenEpiO / NCBI BioSample / MIxS / ENVO / LOINC / SNOMED CT / ELR / NWSS / hAMRonization mappings** | PHA4GE consortium (umbrella); each underlying ontology directly | LinkML schema slot URIs throughout `jackpot_schema.yaml` | Schema-first ontology anchoring is JACKPOT's interoperability foundation. WHO/IPSN attribute 9 (Interoperability) compliance lives here. |
| **CDC TOSTADAS for NCBI brokering** | CDC TOSTADAS toolkit | `portal_to_tostadas.py` converts JACKPOT metadata to NCBI submission package | NCBI's structured submission flow is fiddly; TOSTADAS is the maintained tool of record. JACKPOT wraps it rather than re-implementing the wire format. |
| **GISAID EpiCoV/EpiFlu/EpiPox export** | GISAID's submission spec | Export pipelines per organism family | Practical interop. Adopted *despite* GISAID's broader governance problems (per Section 17.8's GISAID cautionary tale) — operators need to submit there until Pathoplexus or similar reaches feature parity. |
| **MMWR + ISO epiweek computation at ingest** | CDC MMWR convention; ISO 8601 | `compute_epiweeks()` runs in every ingest path; `mmwr_year`, `mmwr_week`, `iso_year`, `iso_week` columns | CDC-aligned reporting needs MMWR; international contexts use ISO. JACKPOT computes both at ingest so downstream queries don't have to. |
| **Pangolin + Nextclade auto-run after viralrecon** | Pango Lineages project (CoV-Lineages.org); Nextstrain's Nextclade | viralrecon pipeline-zoo entry auto-populates `pango_lineage` and `nextstrain_clade` | Lineage classification is essentially a public-good substrate; JACKPOT delegates to the canonical tools rather than reimplementing. |
| **Nextflow + GCP Batch for pipeline execution** | Sequera Labs' Nextflow + GCP-native batch service | `pipeline_runs` orchestration; GKE-based pipeline executor pods | Standard public-health bioinformatics pipeline runtime. Compatible with nf-core ecosystem (~150+ existing community workflows). |
| **Three-tier quality model (PRELIMINARY / ANALYZABLE / SUBMITTABLE)** | New design decision (no direct prior art) | `samples.quality_status` enum + tier-aware validator | Real-world surveillance accepts incomplete data routinely. Loculus has binary required-or-not; JACKPOT explicitly tracks completeness as a first-class field. (See Section 11 — this is one of the differentiators.) |
| **Sharing levels (PRIVATE / LAB / DISCOVERABLE / PUBLIC)** | New design decision informed by GISAID's non-DAA-but-tiered concept | `samples.sharing_level` enum + `can_access_sample()` permission cascade | Maps to how public health agencies actually share — academic private data, lab-internal data, agency-discoverable, fully public. (See `docs/architecture.md` v6.0 §13.) |
| **Three-level federation architecture (designed; Level 1 partial)** | Hub-and-spoke + bidirectional patterns from broader open data work | `federated_instances` table, `min_sharing_level_for_federation`, three progressive levels per `docs/architecture.md` v6.0 §20 (and `docs/federation.md` for the architecture detail) | Pathoplexus has group-based sequence ownership but not multi-instance federation. NCBI Pathogen Detection is a single-operator hub. JACKPOT's three-level design is novel for the surveillance-platform tier. |
| **AGPL-3.0 license** | Loculus / GenSpectrum / LAPIS / SILO precedent; aligned with European public-health digital-public-infrastructure ethos | `LICENSE` at repo root | This is a *cluster* membership decision more than a code-adoption decision. Section 4.4 details the cultural pattern. |

### 18.2 Adopted as patterns (architectural inspiration, not direct code-lift)

These are decisions where JACKPOT has converged on a pattern from this landscape but built its own implementation rather than adopting upstream code directly. Most are still in-progress on the roadmap.

| Pattern | Source | Where in JACKPOT roadmap | Why pattern-not-code-lift |
|---|---|---|---|
| **Pathoplexus governance-as-code** | Pathoplexus repo's public Statutes / Values / COI / Executive Board | `governance/` directory plan (B-GOV-1; Section 13) | Governance docs are operator-specific text, not code. Pattern is what transfers. |
| **Loculus pluggability HTTP contract** | Loculus `preprocessing/specification.md` | B-LOC-3 — `backend/routers/preprocessing.py` for P1 | Direct *code* lift from Kotlin → Python isn't free, but the contract is a 192-line spec that maps cleanly to FastAPI. (See Section 12, recommendation A1.) |
| **Loculus structured error/warning schema** | Loculus `ProcessingIssue` shape | B-LOC-4 — update JACKPOT's `ValidationResult` (Section 12, recommendation A2) | Schema-level pattern adoption; clean Pydantic translation. |
| **Loculus pipeline versioning + auto-promote** | Loculus `pipelineVersion` semantics | B-LOC-6 — JACKPOT `validator_version` + reprocessing job | Algorithm pattern; JACKPOT's reprocessing background job structure is its own. |
| **Loculus per-sample data-use-terms (OPEN/RESTRICTED) at submission** | Pathoplexus's submission UI | B-PPX-1 — Streamlit upload page radio button (Section 13, Tier 1) | Pure UI work; JACKPOT's schema (`data_use_terms`, `embargo_release_date`, `citation_request`) already supports it. |
| **NCBI Pathogen Detection BigQuery JOIN** | NCBI public BigQuery dataset | B-NCBI-1 — single SQL query for cluster context (Section 13, Tier 0) | One-query integration. The pattern is "federate via BigQuery JOIN," not "import a library." |
| **NCBI PD's PDS# stable cluster accession system** | NCBI accession pattern | B-NCBI-3 — JACKPOT mints `JKPT#######.version` accessions (Section 17.4b) | Adopting the *concept* of stable, versioned outbreak-cluster IDs. |
| **hAMRonization output mandate** | PHA4GE community standard | B-NCBI-2 — every AMR pipeline-zoo entry emits hAMRonization-format JSON | Standard adoption + per-pipeline implementation work. |
| **EnteroBase HierCC concept (eventually native)** | EnteroBase's hierarchical clustering | B-EB-2 — JACKPOT-HC at 11 distance thresholds (Section 17.3a) | Algorithm pattern; JACKPOT could implement it natively without depending on EnteroBase's Salmonella/E.coli scope. |
| **BV-BRC fast-track queue lane** | BV-BRC's two-tier job-queue architecture | B-BVBRC-1 — `<30s` jobs separate from long-running pipelines (Section 17.5a) | Queue-design pattern; JACKPOT's APScheduler/Cloud Scheduler stack is its own. |
| **Solu rapid-triage pipeline shape** | Solu's "FASTQ in, intel out, in <5 minutes" UX | B-SOLU-1 — rapid-triage pipeline (Section 17.6a) | UX target + pipeline-architecture pattern. |
| **Solu trust portal pattern** | Solu's `solugenomics.trust.site` | B-SOLU-3 — `docs/trust.md` for JACKPOT (Section 17.6c) | Documentation pattern; ties to the `governance/` directory work (B-GOV-1). |
| **Pathogenwatch typing-tools-as-containers** | `pathogenwatch-oss/*` Docker images | B-PW-1 through B-PW-4 — speciator, mlst, seroba, vista, inctyper as zoo entries (Section 17.2a) | Direct integration as pipeline-zoo entries; the upstream containers are mature. (Adoption-as-pattern because JACKPOT's pipeline-zoo entry shape is its own.) |
| **Sample Locator FHIR + CQL federation** | German Biobank Alliance (Section 5.3.1) | B-SL-1, B-SL-2 — study + optional FHIR adapter | Pattern study before JACKPOT Federation Level 1 implementation. |
| **CDST hash-based privacy-preserving typing** | Section 5.5.1 | B-CDST-1, B-CDST-2, B-CDST-3 — pipeline + storage + federation overlap query | This is the only direct-adoption candidate from the new (5.2-5.5) categories that's a pipeline-zoo entry, not a pattern study. |
| **Three-level federation hub model** | Hub-and-spoke patterns generally; influenced by GISAID's central-hub *anti-pattern* | `federated_instances` + `federation_role` (hub/spoke/peer) per `docs/architecture.md` v6.0 §20 (and `docs/federation.md` for the architecture detail) | JACKPOT's design positions explicitly *against* single-hub central-database models like GISAID and *for* peer federations like Pathoplexus's group model. |

### 18.3 Specifically rejected / counter-positioned

These are choices in the landscape that JACKPOT has explicitly declined.

| Choice | Why rejected |
|---|---|
| **GISAID closed-source DAA model** | The entire `governance/` directory work plus the AGPL-3.0 license choice exist in opposition to GISAID's opacity. JACKPOT under AGPL-3.0 can't be turned into "another GISAID" by any operator — §13 of the AGPL closes the SaaS loophole. (Section 4 develops this in detail.) |
| **GenSpectrum SILO Rust in-memory query engine** | Overkill for JACKPOT's operating range (hundreds of thousands of samples per instance, not millions). PostgreSQL + planned LAPIS-compat is the right tier of complexity. (Section 17.1a.) |
| **Apache Superset / Looker for analytics** | Sovereign Portal guide proposes Apache Superset; JACKPOT uses Streamlit dashboards on top of BigQuery. Reasoning: Streamlit keeps everything in one Python codebase with one auth model. Superset adds a separate auth and access-control system. (See `sovereign_portal_delta.md` for the head-to-head.) |
| **Arvados Keep + Gen3 Fence (Sovereign Portal pattern)** | Sovereign Portal guide proposes these as the storage + identity substrate; JACKPOT uses GCS + Cloud SQL + Google OAuth + JWT. Reasoning: Arvados/Gen3 add operational overhead (multiple services to deploy, separate identity service) without solving a problem JACKPOT actually has. JACKPOT's ingest endpoints and tier-aware validation are deeper than what Arvados Keep models naturally; JACKPOT's permission cascade is more nuanced than what Gen3 Fence's project-level access provides. (See `sovereign_portal_delta.md`.) |
| **Loculus separate-service preprocessing as default** | Architectural — Loculus's pull/poll preprocessing is great for pluggability but bad for laptop-deployment UX (Scenario A laptop case). JACKPOT keeps in-process validation as default; the HTTP contract (Section 12, A1) is opt-in for sophisticated deployments. (Section 12, recommendation N1.) |
| **Loculus binary required-or-not validation** | JACKPOT's tier-aware validation (PRELIMINARY/ANALYZABLE/SUBMITTABLE) is genuinely better for real-world surveillance where labs submit incomplete data routinely. (Section 12, recommendation N2.) |
| **EnteroBase GrapeTree visualization** | Pathogenwatch's Phylocanvas is more general-purpose with broader community adoption. Pick one — pick Phylocanvas. (Section 17.3c.) |
| **BV-BRC comparative-genomics workbench** | Different lane. JACKPOT is sample manager + pipeline orchestrator + result store, not comparative-genomics workbench. Researchers go to BV-BRC for that. (Section 17.5c.) |
| **MOLGENIS Armadillo as the federated-analysis substrate** | Only relevant if JACKPOT adopts DataSHIELD wholesale, which Section 5.2.1 deliberately doesn't suggest. JACKPOT's stack is Python + PostgreSQL, not R + Parquet. (Section 5.2.3.) |
| **Pure central-hub federation models** | JACKPOT's `federation_role` includes `peer`, not just `hub` and `spoke`. The architectural commitment is that peer-to-peer federation must be possible without a central operator. This blocks the GISAID failure mode. |

### 18.4 Cross-references to the WHO/IPSN attributes

A separate view of the same adoption decisions, organized by which WHO/IPSN essential attribute (the 12 attributes in `Attributesential.pdf`) each shipped feature contributes to. This is the alignment view; full per-attribute analysis lives in `docs/governance_alignment.md`.

| WHO/IPSN attribute | Shipped JACKPOT features that contribute |
|---|---|
| **1. Governance** | AGPL-3.0 license; `governance/` directory plan (B-GOV-1) |
| **2. Transparency** | Public spec.md + architecture.md; immutable audit log; `governance/` plan |
| **3. Infrastructure & Security** | Two-PII-gate (scrubber + DLP); GCP Workload Identity Federation; encrypted transit/at-rest; secret manager |
| **4. Data Scope** | One Health sectors (human/wildlife/livestock/wastewater/water/air/soil/surface/food/produce/vectors); pathogen-agnostic schema; metagenomic support |
| **5. Data Submission** | Four ingest endpoints; tier-aware validation; DataHarmonizer; CSV harmonizer for legacy formats |
| **6. Data Curation** | NCBI SRA Human Scrubber + skip governance; GCP Cloud DLP for metadata PII; tier semantics; content-sniffing file detection |
| **7. Data Provenance** | Audit log on every state change; immutable append-only `pipeline_results`; `PipelineProvenance`; persistent identifiers |
| **8. Access** | Sharing levels (PRIVATE/LAB/DISCOVERABLE/PUBLIC); `can_access_sample` permission cascade; Lab Director / Platform Admin / Governance Board roles; access request lifecycle |
| **9. Interoperability** | LinkML schema with ontology anchoring (PHA4GE/GenEpiO/MIxS/NCBI/GA4GH DUO/DRS/LOINC/SNOMED/ENVO/NWSS); TOSTADAS; planned LAPIS-compat |
| **10. Data Use & Benefits Sharing** | GA4GH DUO codes per dataset; `embargo_release_date`; `citation_request`; per-sample OPEN/RESTRICTED (B-PPX-1); auto-Acknowledgments (B-GISAID-1); `benefits-sharing-framework.md` plan |
| **11. Analytical & Reporting** | Pipeline zoo (12+ entries); Streamlit dashboards; planned BigQuery analytics layer; planned LAPIS-compat |
| **12. Sustainability** | Open-source (AGPL-3.0); operator-agnostic by design; `jackpot init` bootstrap; multi-deployment-target architecture |

---

## 19. What's worth looking at next

This section is the priority queue across the full now-23-tool landscape, ranked by ROI and effort. It complements the existing roadmap (Sections 13-15) and the per-platform recommendations in Section 17 — those go deep on each platform individually; this section is the cross-cutting "what to do next" view.

### 19.1 Tier 0 — Immediate / next-session opportunities

These are pieces of work where the path is clear, the effort is low, and the ROI is high. None block the active P0d → P0e → P0b → P0c sequence; all could be picked up in any open Claude Code session.

1. **Sample Locator (GBA) FHIR + CQL pattern study** (B-SL-1). Two days of reading + an architecture decision: is JACKPOT's Federation Level 1 query API going to be FHIR-compatible, or JACKPOT-native with an optional FHIR adapter? This decision should land *before* the Federation Level 1 implementation work itself. **Section 5.3.1.**

2. **CDST pipeline-zoo entry** (B-CDST-1, B-CDST-2). Adding the CoDing Sequence Typer as a Level-1 pipeline for bacterial isolates costs 1-2 sessions and delivers a privacy-preserving primitive that JACKPOT's Year-2 federation needs anyway. Even before federation goes live, the hashes are a useful per-sample fingerprint for outbreak detection within a single instance. **Section 5.5.1.**

3. **Pathogenwatch typing tools** (B-PW-1, B-PW-2, B-PW-3). Speciator (Mash species ID), MLST/cgMLST, and the AMR libraries — three drop-in containers, each 1 session of integration work. Closes the bacterial-pipeline-coverage gap surfaced in the Section 6.3 matrix. **Section 17.2a.**

4. **`governance/` directory** (B-GOV-1). Document-work, ~3-5 hours of writing. Charter, COI policy, jurisdiction-and-data-residency, benefits-sharing-framework, access-grievance-procedure, platform-shutdown-data-portability-plan, advisory-board. WHO/IPSN attribute 1 compliance + major credibility lift for any IPSN/WHO/PABS conversation. **Section 13.1c.**

5. **Per-sample OPEN/RESTRICTED radio button** (B-PPX-1). Schema already supports it (`data_use_terms`, `embargo_release_date`, `citation_request`). Streamlit upload page just needs the radio. ~Half a session. **Section 13.1b.**

### 19.2 Tier 1 — High-value strategic studies (sessions, not days)

These are deeper analyses or pattern studies that would inform major roadmap decisions. Each is approximately one working session.

1. **JACKPOT vs Overture head-to-head** (B-OVR-1). Run the same shape of analysis as the existing Loculus comparison (Sections 7-12 of this document). Overture is the *only* other open-source genomic data platform with an active multi-operator design. Expected outputs: architectural-divergence assessment, identified code-adoption candidates from SONG/SCORE/Maestro, specific backlog items. **High-value, not-yet-done.** **Section 5.4.2.**

2. **DataSHIELD non-disclosure-policy primitive** (B-DSH-1). Year 2 architecture work but the design study should land sooner. JACKPOT's federation Level 1 query needs to return aggregates without leaking individual rows; DataSHIELD's minimum-cell-size + summary-only output rules are the canonical reference. **Section 5.2.1.**

3. **FAIR Data Pipeline provenance audit** (B-FDP-1). Compare JACKPOT's `PipelineProvenance` + `pipeline_runs` to the FAIR Data Pipeline metadata model. Identify gaps in input-data version tracking, execution-environment snapshot, parameter immutability. Drives R1.2 from 🔶 to ✅ on the FAIR scorecard. **Section 5.4.3.**

4. **Per-pathogen DataHarmonizer template views** (B-DH-1). Generate per-pathogen template *projections* over the monolithic schema (organism filter in the existing T1/T2/T3 generator) for an entry-UX win, with governance slots inherited structurally. Schema-decomposition into independently-versioned per-pathogen specs was considered and **rejected** — it would scatter JACKPOT's cross-cutting governance guarantees across organism boundaries. **Section 5.4.4.**

### 19.3 Tier 2 — Strategic / Year 2 implementations

Substantial implementation work, but already well-understood from the prior analysis. These are the items that will likely move from "planned" to "active" in Year 2.

1. **CDST federation-overlap query** (B-CDST-3). Once CDST hashes are populated (B-CDST-1, B-CDST-2), the federation-layer query is a natural follow-on — privacy-preserving outbreak detection across instances without raw-sequence sharing. ~1 week implementation work after the foundation. **Section 5.5.1.**

2. **Sample Locator FHIR adapter** (B-SL-2). If the B-SL-1 architecture decision picks FHIR-compatible federation, implement the FHIR Sample resource adapter so JACKPOT instances can be queried from the existing GBA Sample Locator broker. Useful for European deployments. ~2-3 weeks. **Section 5.3.1.**

3. **Pathogenwatch results-pull** (B-PWATCH-1). Push assembly via Pathogenwatch API, pull cgMLST/MLST/AMR/SNP-tree results back into `pipeline_results`. JACKPOT becomes a *compositor* of community-curated typing rather than reimplementing it for every pathogen. ~3-4 sessions. **Section 13.2a.**

4. **Native HierCC implementation** (B-EB-2). Compute JACKPOT's own hierarchical cluster codes (JACKPOT-HC) for any cgMLST-typed bacterial sample at 11 distance thresholds matching EnteroBase. Federation-ready clustering codes. ~2-3 weeks. **Section 17.3a.**

5. **NCBI Pathogen Detection BigQuery JOIN** (B-NCBI-1). PDS# cluster IDs and MicroBIGG-E AMR results surfaced in `samples` table via single parameterized SQL query. ~2 sessions. Highest-ROI integration once GCP staging is stable. **Section 13.0a.**

### 19.4 Tier 3 — Long-term / monitor

Items that are surfaced for completeness but aren't on the active critical path. Revisit annually.

1. **VANTAGE6 federated learning evaluation** (B-V6-1). Year 2+ when federated ML becomes a real priority (e.g. AMR predictors, outbreak-cluster detection trained across instances). Decide: integrate VANTAGE6 wholesale vs. minimal-viable extension of JACKPOT's federation push job. **Section 5.2.2.**

2. **Cumulus Bulk FHIR adapter for HumanSample** (B-CUM-1). Year 2+ when JACKPOT integrates with STLT EHR systems. Allows EHR + genomic linkage analytics without shipping records into JACKPOT. **Section 5.4.1.**

3. **MOLGENIS Armadillo / DataSHIELD wholesale adoption.** Defer indefinitely. Only relevant if JACKPOT decides to pivot to R-based federated stats as a first-class primitive. Currently the design says no. **Section 5.2.3.**

4. **LIT-FED-SEARCH / Federated GMQL / COMBAT-TB-NeoDB.** Pattern references only; defer indefinitely. Surfaced for landscape completeness. **Sections 5.3.2 / 5.3.3 / 5.3.4.**

5. **Alembic for legacy-format ingestion.** Defer until legacy-data ingestion becomes a regular workflow. JACKPOT's existing `harmonizer.py` covers the high-volume cases. **Section 5.5.2.**

### 19.5 Cross-cutting recommendations

These are themes that emerge from the now-broader landscape view, rather than per-tool action items.

**A. Federation should converge on FHIR for cross-platform interop.** Sample Locator (5.3.1), Cumulus (5.4.1), and the German Biobank Alliance's broader infrastructure all use FHIR as the federation lingua franca. JACKPOT's current `federated_instances` design is JACKPOT-native, which is fine for JACKPOT-to-JACKPOT but locks out cross-platform interop. The B-SL-1 architecture decision (5.3.1) is the right gate — make this decision deliberately rather than by default.

**B. Privacy-preserving primitives should be considered first-class, not bolt-ons.** The new categories surface a clear pattern: tools that emit non-identifying outputs by construction (CDST hash typings, DataSHIELD aggregates, Cumulus aggregate-only EHR) are stronger privacy primitives than role-based access control on raw rows. JACKPOT's two-PII-gate (scrubber + DLP) is a strong ingest-side primitive; the federation side currently relies on `min_sharing_level_for_federation` which is access control, not privacy preservation. Adopting CDST (B-CDST-*) is the first step in the right direction.

**C. Multi-operator-by-design is a smaller club than the original landscape suggested.** Of the original 9 surveillance platforms, only Loculus and JACKPOT are explicitly multi-operator-by-design. But the new categories surface 12 more multi-operator tools — DataSHIELD, VANTAGE6, MOLGENIS Armadillo, Sample Locator, Federated GMQL, COMBAT-TB-NeoDB, Cumulus, Overture, FAIR Data Pipeline, DataHarmonizer ecosystem, CDST, Alembic. The pattern is: **multi-operator design is much more common in adjacent infrastructure than it is in the headline genomic-surveillance-platform tier.** JACKPOT joining this broader cluster means looking outside the surveillance-platform peer group for federation patterns.

**D. The "what JACKPOT looks like vs. peers" matrix shifts dramatically with the broader landscape.** The original Section 6.2 table positions JACKPOT against 9 peers; updating to 22 makes JACKPOT's differentiators look different. Some prior moats (LinkML schema-first, GA4GH DUO, two-PII-gate, no-copy URI registration) are even more distinctive in the broader view because none of the federated-analysis or federated-search tools cover those layers. But some Loculus-cluster decisions (sequence versioning, pluggable preprocessing) become *standard infrastructure* rather than differentiators when set against tools like FAIR Data Pipeline that have been doing similar things in adjacent domains for years. The sustainable JACKPOT differentiators are at the **public-health-surveillance-data-with-privacy-preservation intersection**, not at the data-management-platform layer.

**E. `governance/` directory + WHO/IPSN attribute alignment is the single highest-credibility-lift document set.** B-GOV-1 plus the alignment work in `docs/governance_alignment.md` is the documentation that will move JACKPOT from "open-source platform" to "credible IPSN/PABS-conversation-ready platform." Document work, not engineering work; ROI is significant.

---

*End of v3.0 expanded landscape. Review and tell me if anything's missing or wants more depth.*
