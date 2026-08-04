> **Status:** Superseded — archived (directory convention). Historical; do not cite as current.

# Domain reference notes

Standalone facts and citations synthesized across the chat. Not decision documents — these are reference notes to keep handy for future grant writing, conversations, and platform documentation. Cross-referenced with the actual JACKPOT source-of-truth design documents where applicable.

## JACKPOT source-of-truth design documents

The actual anchor documents in the repo (referenced throughout the other 8 docs in this set):

| Document | Role |
|---|---|
| `spec.md` | Build spec, scenario definitions (A laptop / B single-org cloud / C multi-lab agency / D SaaS / E federation member / F CI / T tribal-sovereignty), architectural layer cake |
| `todo.md` | Backlog (active sprint + tracked-not-scheduled phases) |
| `jackpot_session_summary_and_backlog.md` | Session history + retrospective |
| `Jackpot_AIS.md` | Artificial Immune System theoretical anchor; defines Track 1 / Track 2 seam pattern |
| `jackpot_immune_platform_plan.md` | Five-pillar Immune Platform plan (Pillars I bio-AIS / II cyber-AIS / III federation / IV academy / V cross-cutting) |
| `jackpot_immune_collaboration_scaffolding.md` | Operational scaffolding for external research collaborators |
| `jackpot_detection_landscape.md` | 24 component-tier adoption items from AMAnD/TaxTriage/MARTi/cgMSI/INSaFLU ecosystem |
| `jackpot_byop_and_eukaryotic_design.md` | Multi-engine BYOP + 8 eukaryotic pathogen groups |
| `jackpot_pathoplexus_loculus_overview.md` | Comparative analysis with open-source pathogen-genomics ecosystem |
| `jackpot_cdc_dmi_stlt_overview.md` | CDC DMI / North Star / STLT + CARE Principles |
| `jackpot_architecture.md` | System architecture, including the §22 federation 3-gate qualification logic |
| `docs/architecture/sovereignty-compliant-deletion.md` | Phase 24.5 design lockdown (PR #20, merged Session 21) |
| `docs/e2e_uat_plan.md` | E-1 laptop UAT plan, 6-role RBAC walkthrough (Session 21) |

When in doubt about what's tracked, these are the sources. The chat introduced new material that doesn't reference these documents and uses competing prefix conventions — see `backlog-reconciliation.md` for the chat-to-real mapping.

## EPISTORM and CDC Insight Net

EPISTORM (Center for Epidemic Modeling and Outbreak Analysis through the use of Real-time Data) is one of two CDC Insight Net flagship modeling centers (2023-2028). The other is at UT Austin.

| Center | Lead institution | PI | Award | Note |
|---|---|---|---|---|
| EPISTORM | Northeastern University | Vespignani; Scarpino Co-PI | $17.5M | AI + Life Sciences focus |
| UT Outbreak Analytics + Disease Modeling | UT Austin | Lauren Ancel Meyers | $27.5M | Sister center, larger budget, broader scope |

Both centers coordinate. Outreach to one is visible to the other.

Other EPISTORM faculty: Alessandro Vespignani (Director), David Lazer, Matteo Chinazzi, Mauricio Santillana. Scarpino is the operationally-relevant contact for JACKPOT given his pathogen-surveillance domain.

## Sam Scarpino — active grants in JACKPOT footprint

Per public records as of late 2025:

- **AI-Enhanced Wastewater Metagenomics** (Grand Challenges 2024-25). Directly overlaps `B-WW-1` + IM-2 `B-IMMUNE-WW-1` + the prospective Phase 35 epi-modeling work.
- **Pathogen Detection through Aircraft and WES** (Gates 2025-26). Aircraft wastewater + wastewater epidemiological surveillance.
- **AI-enabled Measles Forecasting** (Gates 2024-25). Maps to potential Phase 35 epydemix simulation use cases.

Career arc: Rockefeller Foundation VP Pathogen Surveillance (departed 2023) → co-founded Global.health → Northeastern (current) + SFI External Faculty since 2020. Methodological strengths: Bayesian inference for epidemics, message-passing in epidemic models (Shrestha/Scarpino/Moore 2015 Phys Rev E), federated learning for surveillance.

## SFI structural facts

- **Not a deployment target.** No labs, no IT infrastructure. Workshop-driven, methodological, theoretical.
- **External Faculty vs Resident Faculty distinction.** External Faculty are affiliated researchers who visit periodically. Resident Faculty live in Santa Fe.
- **Right engagement format for JACKPOT.** 2027 workshop on federated genomic surveillance methods, co-organized with Scarpino, JACKPOT as one of multiple platforms presented. Peer-review and theoretical-grounding venue, not pitch venue.

## WhiteLabRt method details

Two-step Bayesian back-calculation (Li 2021):
- Reconstructs infection time series from reported case time series, accounting for delay distributions (incubation, reporting delay).
- Estimates Rt from reconstructed infections via renewal equation.
- STAN-based; Bayesian uncertainty quantification.

Spatial Rt with state flux (Zhou 2021):
- Joint estimation across connected spatial units.
- Explicit between-unit flux terms account for cross-jurisdictional spread.
- Useful for federation use cases.

Both methods MIT-licensed via WhiteLabRt R package on CRAN. Chad Milando at Boston University Laura White lab maintains. `summRt` is a companion package for summary outputs. `linelistBayes` (Milando) is a line-list-flavored alternative.

## AMAnD (the canonical anomaly detector)

Price & Russell 2023 *Frontiers in Public Health*. DeepSVDD model for metagenome anomaly detection. The canonical reference for `B-AMAND-1` in Phase IM-1.A. Wrapped by JACKPOT as both `backend/immune/bio/amand.py` (bio-NSA module) and `pipelines/immune/amand.nf` (Nextflow process for reproducible scans).

This is what the immune platform actually uses for anomaly detection — not the Nucleotide Transformer / Evo / HyenaDNA / DNABERT-2 / ESM-2 foundation models the chat discussed. The featurizer registry pattern (`B-IMMUNE-FEAT-1`) leaves room for foundation models as plug-in alternatives without core code changes.

## epydemix-data citation requirements

The four data sources in epydemix-data, citation mandatory per upstream README:

| Source key | Citation | Coverage |
|---|---|---|
| `mistry_2021` | Mistry D, Litvinova M, Pastore y Piontti A, et al. (2021). Inferring high-resolution human mixing patterns for disease modeling. *Nature Communications* 12:323. | ~150 countries, age-stratified |
| `prem_2021` | Prem K, Zandvoort K, Klepac P, et al. (2021). Projecting contact matrices in 177 geographical regions: An update and comparison with empirical data for the COVID-19 era. *PLOS Computational Biology* 17(7):e1009098. | 177 regions, stratified by setting (home/work/school/other) |
| `prem_2017` | Prem K, Cook AR, Jit M. (2017). Projecting social contact matrices in 152 countries using contact surveys and demographic data. *PLOS Computational Biology* 13(9):e1005697. | 152 countries, baseline for back-compat |
| `litvinova_2025` | Litvinova M et al. (2025). US contact matrices stratified by sex and race/ethnicity. | US only |

If Phase 35 ships, citation tracking is part of the implementation per `B-LICENSE-1`-style compliance.

## JACKPOT dual-PII-gate architecture

Two distinct PII gates at ingest, both shipped:

**Gate 1: NCBI SRA Human Scrubber (HRRT).** Genomic-level PII. Removes human reads from raw sequencing data before any further processing. Implemented as `ingest_scrubber.nf` Nextflow process. 6-state lifecycle: PENDING / IN_PROGRESS / COMPLETE / FAILED / SKIPPED / PENDING_APPROVAL. 48h skip governance (operator review required if skip persists beyond 48h). `SCRUBBER_MAX_CONCURRENT=10` rate-limit. Aligns with WHO/IPSN attribute 6.

**Gate 2: GCP Cloud DLP.** Metadata-level PII. Scans free-text fields for PERSON_NAME, EMAIL_ADDRESS, US_SSN, etc. before metadata is exposed to query layer. Implemented as `dlp_scanner.py`. FLAGGED samples stored but blocked from queries/pipelines/export until reviewed. `DLP_ENABLED=false` local dev bypass. Field exceptions for expected PII (e.g. `pi_name` excluded from PERSON_NAME detection).

This is consolidated into `backend/backend/privacy/` (PRV-A scaffold, merged Session 21 PR #39) as part of the Track 1 / Track 2 seam architecture — the `scrubber.py` and `dlp.py` modules in privacy package, with AIS hook seams for future DP, FL, HE, MPC, synthetic-substitute overlays.

**Loculus has neither. Pathoplexus has neither.** This is a genuine differentiation and the main "compliance-grade platform" claim.

## Decision Theater key citations

The Jin et al. 2025 *Lancet Regional Health–Americas* Valley fever LSTM paper:

**Jin X, Wei F, Kandala SS, Umesh T, Steele K, Galgiani JN, Laubichler MD. (2025). Time series forecasting of Valley fever infection in Maricopa County, AZ using LSTM. *The Lancet Regional Health – Americas* 43:101010.**

This is the operational anchor for Galgiani + Laubichler + Sunenshine intersection. JACKPOT's strain-resolved Coccidioides forecasting would be a direct extension. Authorship overlap potential for a JACKPOT-extension paper. Operational contacts: Jin and Wei (Decision Theater); methodological contact: Galgiani (Valley Fever COE); institutional contact: Laubichler (DT Director + SCAS).

Older but methodologically relevant: **Bettencourt LM, Ribeiro RM, Chowell G, Lant T, Castillo-Chavez C. (2007). Towards real time epidemiology: data assimilation, modeling and anomaly detection of health surveillance data streams. NSF Workshop on Intelligence and Security Informatics.** Tim Lant authorship — the prospective epi-modeling Rt estimation work maps to this 2007 anomaly-detection framing.

## STPH curriculum map

The seven JACKPOT-relevant MS courses in the School of Technology for Public Health:

- **TPH551** Public Health Technologies — JACKPOT is a public health technology. Direct case study.
- **TPH552** Systems Design and Engineering for Public Health — JACKPOT's schema-first, multi-tier validation, immutable audit, federation design. Textbook case study.
- **TPH550** Data Science for Public Health — JACKPOT generates the data; schema/quality model is the data-science scaffolding.
- **TPH554** AI/ML in Public Health — Phase IM-1 + IM-2 work lives here. Plus epi modeling if pursued.
- **TPH557** Public Health Technology Ethics, Policy and Law — RBAC, consent, dual PII gating, audit, federated privacy. Grando + Hodge intersection. CARE Principles (Phase 27).
- **TPH556** Public Health Technology Entrepreneurship, Innovation and Leadership — the AGPL-3 open-source-to-deployment story.
- **TPH593 / TPH580** Applied Project / Practicum — JACKPOT has a near-infinite backlog of real scoped deployable work.

Marc Adams is the practical contact (assistant dean of education, interim MPH program director). Pathak is the founding Dean (Weill Cornell biomedical informatics background).

## Public COVID-19 data Socrata endpoints map

| Endpoint | Description | Filter pattern |
|---|---|---|
| `data.cdc.gov/resource/2ew6-ywp6` | NWSS metric data | `wwtp_jurisdiction='Arizona'` |
| `data.cdc.gov/resource/g653-rqe2` | NWSS concentration data (raw) | `wwtp_jurisdiction='Arizona'` |
| `healthdata.gov/resource/g62h-syeh` | HHS historical hospital data (through Apr 2024) | `state='AZ'` |
| `data.cdc.gov/resource/ua7e-t2fy` | NHSN HRD current (Nov 2024 onward) | `jurisdiction='AZ'` |
| `data.cdc.gov/resource/mpgq-jmmr` | NHSN HRD preliminary (most recent week) | `jurisdiction='AZ'` |
| `ncbi.nlm.nih.gov/genomes/VirusVariation/vvsearch2/` | NCBI Virus SARS-CoV-2 metadata | `USAState_s:"Arizona"` |
| `data.tempe.gov/api/feed/dcat-us/1.1.json` | Tempe Open Data catalog (search for "wastewater") | n/a |

Sodapy Python client pattern: `client = Socrata("data.cdc.gov", None)` for anonymous (rate-limited but workable for demos). Get a Socrata app token for higher-volume access.

## Pathoplexus / Loculus comparative facts

Per `jackpot_pathoplexus_loculus_overview.md`:

- **Pathoplexus** is the open-data initiative (data + governance). **Loculus** is the underlying platform.
- 8 peer platforms analyzed alongside: GenSpectrum/LAPIS, Pathogenwatch, EnteroBase, NCBI Pathogen Detection, BV-BRC, Solu, RT-MetA, GISAID.
- Phase 26 in `todo.md` contains 34 B-XXX adoption items grouped A-J by source platform (Tracked Not Scheduled).
- The chat-invented "subsections N and O" (9 wastewater items + 4 EPY items) are not part of the real Phase 26.

## Federation scaffolding source documents

The Track 1 / Track 2 seam pattern (the architectural innovation that the chat partially reinvented):

- **`Jackpot_AIS.md`** §1.6 inter-instance signaling, §1.7 attribution & deception, §1.8 tolerance / regulation — the conceptual basis for the five `AISFederationHooks` Protocol entries.
- **`jackpot_immune_collaboration_scaffolding.md`** §3.2 — the dependency-injection seam pattern.
- **`jackpot_immune_platform_plan.md`** §6 (Pillar III), §10.5 (TrustEngine spec).
- **`jackpot_architecture.md`** §22 — three-gate federation push qualification logic (surveillance_relevant, sharing_level ≥ minimum, quality_status ≥ ANALYZABLE).

The FED-A scaffold (`backend/backend/federation/`) implements this pattern in code. The future `backend/backend/immune/` Track 2 overlays will plug in via the five Protocol entry points without modifying Track 1 code.

## Sol cluster details (for future reference)

The chat's Sol cluster federation simulation isn't relevant for Glen's laptop-Scenario-A demo target, but the facts are still useful reference for future grant-funded work:

- 178 nodes, 18K AMD EPYC 7713 cores; 60 GPU nodes (224 A100 80GB + 12 A30 24GB).
- 200Gb/s HDR InfiniBand between nodes.
- 4PB BeeGFS scratch; 2PB PowerScale.
- SLURM scheduler; Apptainer containers; Open OnDemand web portal; dedicated DTN with Globus.
- Split across two datacenters 4 miles apart with high-speed firewalls (real cross-DC latency).
- CHE (compute-hour equivalent) pricing framework; status for Glen's allocation needs verification with Research Computing before any large run.

## Cross-reference matrix for navigation

| If you want | Look at |
|---|---|
| What's actually committed and tracked | `todo.md` + `jackpot_session_summary_and_backlog.md` |
| Why the immune platform is designed the way it is | `Jackpot_AIS.md` + `jackpot_immune_platform_plan.md` |
| How external collaborators plug in | `jackpot_immune_collaboration_scaffolding.md` |
| Pipeline-zoo adoption rationale | `jackpot_detection_landscape.md` |
| Sovereignty / CARE / STLT context | `jackpot_cdc_dmi_stlt_overview.md` + `docs/architecture/sovereignty-compliant-deletion.md` |
| Federation architecture (Track 1 + Track 2 seam) | `backend/backend/federation/README.md` + `Jackpot_AIS.md` |
| Open-source pathogen-genomics ecosystem | `jackpot_pathoplexus_loculus_overview.md` |
| BYOP and eukaryotic pathogen support | `jackpot_byop_and_eukaryotic_design.md` |
| E-1 laptop UAT execution | `docs/e2e_uat_plan.md` + `tests/e2e/scripts/` |

These are the actual entry points. The chat's 9 summary docs (this set) are background context informed by these, not substitutes for them.
