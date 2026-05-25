# JACKPOT Detection Landscape

## Bioinformatics Tools, ML/AI Components, and Detection Frameworks for Pathogen Surveillance

**Status:** Working synthesis · 2026-05-09 · v1.0 · supersedes 9 LeapSpace research files (see §0.2)
**Scope:** Component-tier survey of open-source bioinformatics tools, ML/AI models, anomaly detectors, federated learning frameworks, and detection algorithms relevant to pathogen genomic surveillance. Companion to `jackpot_platform_landscape.md` (which surveys *platform-tier* peers like Loculus, Pathoplexus, Pathogenwatch, etc.) and to `jackpot_immune_platform_plan.md` (which lays out the future Immune-Platform extension). Includes dual-track JACKPOT relevance evaluation: (a) current platform on the P0–P5 roadmap, and (b) JACKPOT extended per the Immune Platform plan.

---

## 0. Executive summary

### 0.1 Headline finding

This document is the *component-tier* twin of `jackpot_platform_landscape.md`. The platform doc surveys 23 platforms (Loculus, GenSpectrum, Pathogenwatch, etc.) — the systems against which JACKPOT is compared as a system. This document surveys ~85 open-source *components* — the pipelines, classifiers, anomaly detectors, variant callers, ML models, and frameworks that JACKPOT could integrate as pipeline-zoo entries, schema extensions, or AIS-pillar building blocks.

The two documents partition cleanly:

- **Platform-tier landscape** (`jackpot_platform_landscape.md`) — peers in the same architectural design space. JACKPOT is one of 23.
- **Component-tier landscape** (this document) — building blocks that any platform could incorporate. JACKPOT could integrate dozens of these.

The dual-track JACKPOT relevance evaluation surfaces three kinds of result on every tool:

1. **Gap-fillers for current JACKPOT** — components that close roadmap items the platform doesn't yet address (e.g., novel-pathogen metagenomic detection, structural-variant calling for bacterial genomes).
2. **Components for the Immune Platform extension** — tools that map to one of the five pillars in `jackpot_immune_platform_plan.md` (bio-anomaly stack, self-defense AIS, federation-as-immune-network, training, gaming).
3. **Already shipped** — tools JACKPOT already incorporates or whose function is covered by an existing JACKPOT module.

### 0.2 What this document supersedes

The following 9 LeapSpace research files are superseded by this synthesis. Treat any reference to them as redirecting here.

| Predecessor file | Tool count | Topic |
|---|---|---|
| `What_open_source_software_tools_focus_on_anomaly_detection_for_biosurveillance.md` | 15 | Anomaly detection across genomic, environmental, digital epidemiology |
| `What_open_source_software_tools_focus_on_MLAI_for_pathogen_detection.md` | 14 | ML/AI pathogen detection (DL classifiers, real-time pipelines, OSINT) |
| `What_open_source_tools_are_available_for_metagenomic_analysis_of_unknown_pathogens.md` | 11 | Metagenomic pipelines for novel/unknown pathogens |
| `What_role_does_federated_learning_play_in_biosurveillance_software.md` | conceptual + ~10 frameworks | FL frameworks, blockchain+FL, privacy-preserving aggregation |
| `Open_source_software_projects_focused_on_detecting_novel__unknown_pathogens_via_genome_analysis.md` | 8 | Novel-pathogen genome analysis tools |
| `What_open_source_software_projects_focus_on_AI_enabled_genomic_surveillance__novel_pathogen_detection__and_novel_pathoge.md` | ~25 | AI-enabled surveillance + immune-inspired algorithms (deep prose) |
| `What_open_source_software_tools_are_available_for_detection_of_genomic_anomalies_in_pathogen_genomes.md` | ~35 | SV/CNV/SNP variant callers + lineage tracking |
| `What_open_source_software_tools_focus_on_biosurveillance_and_biosecurity.md` | ~25 | Biosurveillance + biosecurity (sequence-of-concern screening) |
| `What_open_source_tools_use_artificial_immune_system_algorithms_to_detect_novel__emerging__and_unknown_pathogens.md` | mostly negative finding + ~5 | AIS algorithms (negative finding: no dedicated AIS pathogen tool) |

After dedup across overlapping coverage, this document covers **~85 unique tools** across **14 categories**.

### 0.3 Headline recommendations

Five highest-leverage adoption candidates surfaced by this analysis:

1. ★ **CDST** — drop-in privacy-preserving bacterial typing (already covered as `B-CDST-1/2/3` in `jackpot_platform_landscape.md` §5.5.1; reaffirmed here as the highest-priority component for federated outbreak detection).
2. ★ **AMAnD** (DeepSVDD metagenome anomaly detection) — direct fit for **Immune Platform Pillar I (`jackpot-immune-bio`)** as the metagenome-anomaly layer per `jackpot_immune_platform_plan.md` §4. Production-deployed; published; no current JACKPOT equivalent. New backlog `B-AMAND-1`.
3. ★ **TaxTriage** — Nextflow workflow combining read classification + de novo assembly to detect novel pathogens. Drop-in fit for JACKPOT's pipeline zoo as the canonical "untargeted pathogen discovery" entry. Closes a real gap in the current bacterial+viral pipeline coverage. New backlog `B-TAXTRIAGE-1`.
4. ★ **SeqScreen + BLiSS** — open-source sequence-of-concern (SoC) screening. Direct fit for **Immune Platform Pillar II (`jackpot-immune-sec`) §5.3.4** (synthetic DNA screening at ingest) and a novel biosecurity feature missing from every other genomic-surveillance platform in the landscape. New backlog `B-SOC-1`.
5. ★ **INSaFLU-TELEVIR** — open web-based viral metagenomic detection + routine genomic surveillance suite. Strong reference for the JACKPOT viral pipeline-zoo and useful for the LAPIS-compat Year-2 work. New backlog `B-INSAFLU-1`.

Beyond the top 5, **15+ additional B-XXX backlog items** are surfaced and consolidated in §6.

### 0.4 Coverage by category

| # | Category | Tool count | Highest-leverage tool(s) |
|---|---|---|---|
| a | Metagenomic pipelines for unknown/novel pathogens | 13 | TaxTriage, IDseq/CZID, nf-UnO, INSaFLU-TELEVIR |
| b | ML/AI pathogen classifiers | 11 | DeePaC, MLM, GRUMB, DCiPatho |
| c | Genomic anomaly detection | 5 | AMAnD, KOMB/KombOver |
| d | SV/CNV/SNP variant callers for pathogens | 18 | ProcaryaSV, CNproScan, SNiPgenie, SKA2 |
| e | Genomic surveillance platforms (component-level) | 13 | Solu, NanoCore, Pf-HaploAtlas, AMRomics, rMAP 2.0 |
| f | Event-based outbreak intelligence | 6 | EIOS, EPIWATCH, ProMED-mail |
| g | Disease-specific outbreak anomaly detection | 3 | Thailand malaria, Brazil Amazon, China hybrid |
| h | Biosecurity / sequence-of-concern screening | 2 | SeqScreen, BLiSS |
| i | Federated learning frameworks for biosurveillance | 6 | FedAdapt-CAD, FedTADBench, COLLAGENE |
| j | Privacy-preserving genomic computation | 4 | COLLAGENE, homomorphic encryption MK frameworks |
| k | Artificial Immune System tools | 4 | libtissue, NK-DCHS, ISIMD-ALNs (all non-genomic; gap documented) |
| l | Environmental biosurveillance | 5 | CRISPR-eBx, CAMERA, KBase |
| m | Real-time field/clinical metagenomics | 3 | MARTi, NanoCore (long-read) |
| n | Reporting / preprocessing utilities | 6 | sivirep, MicrobEx, MetaXplor, Krisp |

Total: **~85 unique tools** across 14 categories (some tools appear in multiple categories — counts above reflect primary-category placement).

### 0.5 Two cross-cutting findings

**Finding A — JACKPOT's current pipeline zoo is heavily viral- and bacterial-typing-focused; the unknown/novel pathogen detection layer is thin.**

JACKPOT's 12+ shipped pipelines (viralrecon, Cecret, walkercreek, bactopia, mycosnp, tb-profiler, nf-core/mag, taxprofiler, pathogensurveillance, etc.) cover known-pathogen viral and bacterial genomics very well. What's missing is the *untargeted* / *novel-pathogen* detection layer. Categories (a) and (b) of this document — metagenomic pipelines for unknown pathogens + ML/AI pathogen classifiers — are largely absent from JACKPOT today. The Immune Platform plan's Pillar I (`jackpot-immune-bio`) is the answer; this document identifies the specific components that pillar should integrate.

**Finding B — The AIS-tied tools surfaced in source doc 9 are negative findings, exactly as the LeapSpace synthesis concluded — but the negative finding *is* the strategic opening for the JACKPOT Immune Platform.**

Source doc 9 (`What_open_source_tools_use_artificial_immune_system_algorithms_to_detect_novel__emerging__and_unknown_pathogens.md`) concluded definitively: "There are currently no well-established, dedicated open source tools that specifically use artificial immune system (AIS) algorithms for the detection of novel, emerging, and unknown biological pathogens." `jackpot_immune_platform_plan.md` is precisely the dedicated open-source AIS tool that doesn't yet exist. Components like libtissue, NK-DCHS, ISIMD-ALNs, and pyPOCQuant — surfaced in source doc 9 but flagged as "not tailored for genomics" — become inputs to the Immune Platform plan, not gaps in current JACKPOT.

### 0.6 How to read the rest of this document

- **Section 1** is the master comparison matrix — every surveyed tool with abbreviated columns.
- **Section 2** (subsections 2.a–2.n) is the per-category catalog, with full matrices and prose for high-value rows.
- **Section 3** is the JACKPOT integration analysis for the *current* platform (P0–P5 roadmap, no Immune extension).
- **Section 4** is the JACKPOT integration analysis for the *Immune-Platform-extended* JACKPOT — which tools map to which pillar.
- **Section 5** is the consolidated priority queue — Tier 0 immediate / Tier 1 strategic studies / Tier 2 substantial / Tier 3 long-term.
- **Section 6** is the consolidated B-XXX backlog suitable for direct paste into `todo.md`.
- **Section 7** is references and cross-refs.

---

## 1. Master comparison matrix

Every surveyed tool, one row. Abbreviated columns; per-tool detail lives in §2.

**Status legend (relevance columns):**

- ✅ Already in JACKPOT (or functionally equivalent shipped)
- 🟢 Strong fit — high-priority adopt
- 🔵 Component for Immune Platform extension (mapped to Pillar I / II / III / IV / V)
- 🟡 Pattern reference / study target (no direct adoption planned)
- ⚪ Defer / monitor / out of scope
- ❌ Counter-position / explicitly rejected

The "JACKPOT-current" column evaluates fit to the current P0–P5 roadmap. The "JACKPOT-immune" column evaluates fit to the Immune-Platform-extended JACKPOT per `jackpot_immune_platform_plan.md`. Tools that close gaps in the current platform appear as 🟢 in JACKPOT-current; tools that map to an Immune Platform pillar appear with the pillar number in JACKPOT-immune.

| # | Tool | Category | Function (one line) | License | Maturity | JACKPOT-current | JACKPOT-immune |
|---|---|---|---|---|---|---|---|
| 1 | **AMAnD** | c (anomaly) | DeepSVDD one-class metagenome anomaly detection | OSS | Production | 🟢 Adopt — `B-AMAND-1` | 🔵 Pillar I core |
| 2 | **UltraSEQ** | c (anomaly) | Universal metagenomic classification + anomaly | OSS | Medium | 🟡 Pattern ref | 🔵 Pillar I |
| 3 | **MARTi** | m (real-time) | Real-time nanopore metagenomic surveillance | OSS | Production | 🟢 Adopt — `B-MARTI-1` | 🔵 Pillar I |
| 4 | **PhyloMagnet** | c (anomaly) | Gene-centric phylogenetic screening of meta-omics | OSS | Medium | 🟡 Pattern ref | 🔵 Pillar I (taxa-flagging layer) |
| 5 | **KOMB / KombOver** | c (anomaly) | k-core graph-based microbiome perturbation detection | OSS | Medium | 🟡 Study | 🔵 Pillar I (community-shift detector) |
| 6 | **EIOS** | f (event-based) | WHO open-source NLP/ML outbreak signal detection | OSS | Production | 🟡 Reference for ReportStream-class integration | 🔵 Pillar I (external signal feed) |
| 7 | **PADI-Web** | f (event-based) | Multilingual animal-disease event-based surveillance | OSS | Medium | 🟡 Reference for One-Health reach | 🔵 Pillar I |
| 8 | **News-EDS** | f (event-based) | ML-based news epidemic disease detection | OSS | Emerging | ⚪ Defer | 🔵 Pillar I (open-source signal feed) |
| 9 | **EPIWATCH** | f (event-based) | ML+NLP early-epidemic-signal detection from OSINT | OSS | Production | 🟡 Reference | 🔵 Pillar I |
| 10 | **Epitweetr** | f (event-based) | EU-CDC ML anomaly detection for outbreak signals | OSS | Production | 🟡 Reference | 🔵 Pillar I |
| 11 | **Thailand malaria AD** | g (disease-specific) | 9-algorithm anomaly detection ensemble, malaria | OSS | Medium | ⚪ Domain-specific | 🔵 Pillar I (ensemble pattern) |
| 12 | **Brazil Amazon malaria AD** | g (disease-specific) | ML detectors for outbreak onset/peaks | OSS | Medium | ⚪ Domain-specific | 🔵 Pillar I (ensemble pattern) |
| 13 | **China hybrid EWS** | g (disease-specific) | Hybrid SEIR + ML anomaly detection | OSS | Medium | ⚪ Domain-specific | 🔵 Pillar I (multi-signal pattern) |
| 14 | **MicrobEx** | n (utility) | NLP for microbiology culture concept extraction | OSS | Production | 🟡 Reference (clinical-text path) | ⚪ |
| 15 | **sivirep** | n (utility) | Epidemiological surveillance reporting (R, Epiverse) | OSS | Medium | 🟡 Pattern ref for reporting | ⚪ |
| 16 | **In-situ Turbidity** | l (environmental) | Sensor-data anomaly detection toolkit | OSS | Medium | ⚪ Out of scope | ⚪ |
| 17 | **HydroSignal** | l (environmental) | IoT environmental hydrology platform | OSS | Emerging | ⚪ Out of scope | ⚪ |
| 18 | **IDseq / CZID** | a (metagenomic) | Cloud open-source mNGS pathogen discovery | OSS | Production | 🟢 Reference platform — see §3.1 | 🔵 Pillar I (companion) |
| 19 | **DAMIAN** | a (metagenomic) | Functional metagenomic novel-pathogen detection | OSS | Medium | 🟡 Study | 🔵 Pillar I |
| 20 | **cgMSI** | a (metagenomic) | Strain-level nanopore MAP detection at low coverage | OSS | Medium | 🟢 Adopt — `B-CGMSI-1` | 🔵 Pillar I |
| 21 | **TaxTriage** | a (metagenomic) | Nextflow short+long-read pathogen detection | OSS | Production | 🟢 ★ Adopt — `B-TAXTRIAGE-1` | 🔵 Pillar I |
| 22 | **HPD-Kit** | a (metagenomic) | Open-source pathogen detection toolkit + web UI | OSS | Medium | 🟡 Study | 🔵 Pillar I |
| 23 | **Clin-mNGS** | a (metagenomic) | Snakemake clinical mNGS pipeline | OSS | Medium | 🟡 Pattern ref | 🔵 Pillar I |
| 24 | **PhytoPipe** | a (metagenomic) | Plant-pathogen RNA-seq pipeline | OSS | Medium | ⚪ One-Health adjacent | 🔵 Pillar I (plant-side) |
| 25 | **MetaGeneMiner** | a (metagenomic) | Targeted gene extraction from metagenomes | OSS | Medium | 🟡 Reference | ⚪ |
| 26 | **MetaFX** | a (metagenomic) | Reference-free feature extraction for ML | OSS | Medium | 🟡 Pattern ref | 🔵 Pillar I (feature primitive) |
| 27 | **PathoGFAIR** | a (metagenomic) | FAIR Galaxy nanopore pathogen workflows | OSS | Production | 🟡 Pattern ref | 🔵 Pillar I |
| 28 | **nf-UnO** | a (metagenomic) | Nextflow co-assembly novel-pathogen pipeline | OSS | Emerging | 🟢 Adopt — `B-NFUNO-1` | 🔵 Pillar I |
| 29 | **INSaFLU-TELEVIR** | a (metagenomic) | Viral mNGS detection + routine surveillance suite | OSS (AGPL) | Production | 🟢 ★ Adopt — `B-INSAFLU-1` | 🔵 Pillar I (viral side) |
| 30 | **DeePaC** | b (ML/AI) | CNN/LSTM predicting pathogenicity from raw DNA | OSS | Production | 🟢 Adopt — `B-DEEPAC-1` | 🔵 Pillar I (DL classifier) |
| 31 | **MLM** | b (ML/AI) | ML threat characterization (RF, Bayesian) for unmapped reads | OSS | Production | 🟢 Adopt — `B-MLM-1` | 🔵 Pillar I |
| 32 | **PathoLive** | b (ML/AI) | Real-time relevance-scored pathogen ID during sequencing | OSS | Medium | 🟡 Study | 🔵 Pillar I |
| 33 | **GRUMB** | b (ML/AI) | Genome-resolved metagenomic + ML pathogen-risk score | OSS | Emerging | 🟡 Study | 🔵 Pillar I (risk-scoring layer) |
| 34 | **AutoXAI4Omics** | b (ML/AI) | Explainable ML anomaly detection for food microbiomes | OSS | Emerging | 🟡 Study | 🔵 Pillar I (XAI primitive) |
| 35 | **MegaR** | b (ML/AI) | Interactive R package for metagenome ML model building | OSS | Medium | 🟡 Reference | ⚪ |
| 36 | **Plant ML detector** (Johnson 2023) | b (ML/AI) | Reference-free Random Forest disease detection (long reads) | OSS | Emerging | 🟡 Reference | 🔵 Pillar I (RF primitive) |
| 37 | **PlasticEnz** | b (ML/AI) | ProtBERT classifier for plastic-degrading enzymes | OSS | Emerging | ⚪ Out of scope | ⚪ |
| 38 | **DCiPatho** | b (ML/AI) | Deep cross-fusion network for pathogen identification | OSS | Emerging | 🟡 Study | 🔵 Pillar I (DL primitive) |
| 39 | **ExplaiNN** | b (ML/AI) | Interpretable neural networks for genomics | OSS | Production | 🟡 Reference | 🔵 Pillar I (XAI primitive) |
| 40 | **IDMIL** | b (ML/AI) | Alignment-free interpretable deep MIL for disease prediction | OSS | Medium | 🟡 Reference | 🔵 Pillar I |
| 41 | **EdeepVPP** | b (ML/AI) | Explainable deep viral genome prediction | OSS | Medium | 🟡 Reference | 🔵 Pillar I (viral DL) |
| 42 | **CINNAMON-GUI** | b (ML/AI) | CNN pap-smear / pathology image classification | OSS | Medium | ⚪ Out of scope | ⚪ |
| 43 | **FastPathology** | b (ML/AI) | Open-source DL platform for digital pathology | OSS | Production | ⚪ Out of scope | ⚪ |
| 44 | **VariantSpark** | b (ML/AI) | Cloud ML for genomic association at scale | OSS | Production | 🟡 Reference | ⚪ |
| 45 | **CNproScan** | d (variant) | CNV detection for bacterial genomes | OSS | Medium | 🟢 Adopt — `B-CNPRO-1` | ⚪ |
| 46 | **ProcaryaSV** | d (variant) | SV detection pipeline for bacterial short-read data | OSS | Medium | 🟢 Adopt — `B-PROSV-1` | ⚪ |
| 47 | **Manta** | d (variant) | SV caller (Illumina; widely used) | OSS | Production | 🟡 Available via pipelines | ⚪ |
| 48 | **CNVnator** | d (variant) | Read-depth CNV caller | OSS | Production | 🟡 Available via pipelines | ⚪ |
| 49 | **DELLY** | d (variant) | SV/CNV caller for short-read data | OSS | Production | 🟡 Available via pipelines | ⚪ |
| 50 | **LUMPY** | d (variant) | SV caller integrating multiple signals | OSS | Production | 🟡 Available via pipelines | ⚪ |
| 51 | **BreakDancer** | d (variant) | SV caller for paired-end reads | OSS | Production | 🟡 Available via pipelines | ⚪ |
| 52 | **SVABA** | d (variant) | Local-assembly SV detection | OSS | Production | 🟡 Available via pipelines | ⚪ |
| 53 | **Sniffles2** | d (variant) | Long-read SV caller (gold standard) | OSS | Production | 🟡 Available via pipelines | ⚪ |
| 54 | **cuteSV** | d (variant) | Long-read SV caller (consensus partner with Sniffles2) | OSS | Production | 🟡 Available via pipelines | ⚪ |
| 55 | **PBHoney** | d (variant) | PacBio-specific SV caller | OSS | Medium | 🟡 Available via pipelines | ⚪ |
| 56 | **TRsv** | d (variant) | Tandem-repeat SV/CNV/indel from long reads | OSS | Emerging | 🟡 Reference | ⚪ |
| 57 | **SENSV** | d (variant) | Nanopore-optimized SV at low depth | OSS | Medium | 🟡 Reference | ⚪ |
| 58 | **VizCNV** | d (variant) | CNV visualization + trio-aware interpretation | OSS | Medium | 🟡 Reference | ⚪ |
| 59 | **GATK-gCNV** | d (variant) | CNV detection from exome data | OSS | Production | ⚪ Exome — out of scope | ⚪ |
| 60 | **CNVkit** | d (variant) | CNV detection for NGS | OSS | Production | 🟡 Available via pipelines | ⚪ |
| 61 | **SNiPgenie** | d (variant) | Microbial WGS SNP detection | OSS | Production | 🟢 Adopt — `B-SNIPG-1` | ⚪ |
| 62 | **SKA2** | d (variant) | Split-k-mer bacterial genotyping | OSS | Production | 🟢 Adopt — `B-SKA2-1` | ⚪ |
| 63 | **Solu** | e (surv platform) | Real-time cloud bacterial surveillance (commercial) | Closed | Medium | (covered in landscape doc) | (covered in landscape doc) |
| 64 | **IRIDA-ARIES** | e (surv platform) | Italy One-Health genomic surveillance suite | OSS | Production | 🟡 Pattern ref | ⚪ |
| 65 | **Hygieia** | e (surv platform) | AI/ML pipeline for gene-disease association | OSS | Emerging | 🟡 Reference | ⚪ |
| 66 | **Machado** | e (surv platform) | Python genomics integration framework (Brazil) | OSS | Medium | 🟡 Pattern ref | ⚪ |
| 67 | **NanoCore** | e (surv platform) | Core-genome bacterial surveillance for Nanopore+Illumina | OSS | Production | 🟢 Adopt — `B-NANOC-1` | ⚪ |
| 68 | **Pf-HaploAtlas** | e (surv platform) | Open-source app for malaria genomic surveillance | OSS | Medium | 🟢 Adopt for malaria — `B-PFHAP-1` | ⚪ |
| 69 | **Pangolin** | e (surv platform) | SARS-CoV-2 lineage assignment | OSS | Production | ✅ Already shipped | ⚪ |
| 70 | **Nextstrain** | e (surv platform) | Pathogen evolution tracking + Auspice viz | OSS | Production | ✅ Available via pipelines | ⚪ |
| 71 | **PathoSPOT** | e (surv platform) | Outbreak tracing via WGS | OSS | Production | 🟡 Pattern ref for nosocomial | ⚪ |
| 72 | **pyMLST** | e (surv platform) | cgMLST bacterial clonality analysis | OSS | Production | 🟢 Adopt — `B-PYMLST-1` | ⚪ |
| 73 | **BacSeq** | e (surv platform) | Automated bacterial WGS pipeline | OSS | Medium | 🟡 Pattern ref | ⚪ |
| 74 | **AMRomics** | e (surv platform) | Scalable microbial-genome AMR surveillance | OSS | Medium | 🟢 Adopt — `B-AMRO-1` | ⚪ |
| 75 | **OpenRecombinHunt** | e (surv platform) | Viral recombination detection | OSS | Medium | 🟢 Adopt — `B-RECOMB-1` | ⚪ |
| 76 | **GenomeDepot** | e (surv platform) | Microbial comparative genomics platform | OSS | Medium | 🟡 Pattern ref | ⚪ |
| 77 | **rMAP 2.0** | e (surv platform) | WDL+Cromwell+Docker ESKAPEE workflow | OSS | Production | 🟡 Pattern ref for WDL | ⚪ |
| 78 | **ProMED-mail** | f (event-based) | Volunteer-curated outbreak reports | Free | Production | 🟡 Reference | 🔵 Pillar I (open-source signal) |
| 79 | **SeqScreen** | h (biosec) | Functional annotation for sequences of concern | OSS | Production | 🟢 ★ Adopt — `B-SOC-1` | 🔵 Pillar II §5.3.4 |
| 80 | **BLiSS** | h (biosec) | Best-match SoC screening | OSS | Medium | 🟢 ★ Adopt — `B-SOC-1` | 🔵 Pillar II §5.3.4 |
| 81 | **DataSHIELD/VANTAGE6/Armadillo** | i (FL) | (covered in landscape doc §5.2) | OSS | Production | (landscape doc) | 🔵 Pillar III |
| 82 | **FedAdapt-CAD** | i (FL) | FL framework with client-aware aggregation for AD | OSS | Emerging | 🟡 Study | 🔵 Pillar III |
| 83 | **FedMI** | i (FL) | Vertical FL for distributed-edge anomaly detection | OSS | Emerging | 🟡 Study | 🔵 Pillar III |
| 84 | **FedTADBench** | i (FL) | Benchmark suite for federated time-series AD | OSS | Medium | 🟡 Reference | 🔵 Pillar III |
| 85 | **Blockchain+FL frameworks** | i (FL) | Surveyed frameworks (Ouyang, Wang, etc.) | Various OSS | Emerging | ⚪ Defer | 🔵 Pillar III (audit-trail layer) |
| 86 | **COLLAGENE** | j (privacy) | Privacy-aware federated genomic analysis | OSS | Production | 🟡 Study — pairs with `B-DSH-1` | 🔵 Pillar III |
| 87 | **MK-Homomorphic-Encryption framework** (Namazi 2025) | j (privacy) | Multi-key homomorphic encryption for genomic computation | OSS | Emerging | 🟡 Reference | 🔵 Pillar III |
| 88 | **TEE-based genomic analysis framework** (Asvadishirehjini 2020) | j (privacy) | Trusted execution environments for genomic data | OSS | Emerging | ⚪ Defer | 🔵 Pillar III |
| 89 | **CRISPR-eBx** | l (environmental) | CRISPR-Dx for environmental DNA biosurveillance | OSS | Emerging | ⚪ Out of scope (now) | 🔵 Pillar I (env layer) |
| 90 | **CAMERA** | l (environmental) | Environmental metagenomics cyberinfrastructure | OSS | Production | 🟡 Pattern ref | ⚪ |
| 91 | **KBase** | l (environmental) | Open platform for microbial/metagenomic analysis | OSS | Production | 🟡 Reference | ⚪ |
| 92 | **LandScient_EWS** | l (environmental) | Open-source rainfall threshold landslide EWS | OSS | Medium | ⚪ Out of scope | ⚪ |
| 93 | **MetaXplor** | n (utility) | Interactive viral/microbial metagenomic data manager | OSS | Production | 🟡 Pattern ref | ⚪ |
| 94 | **Krisp** | n (utility) | CRISPR/primer diagnostic design from WGS | OSS | Medium | 🟡 Pattern ref | ⚪ |
| 95 | **TinselR** | n (utility) | R Shiny phylogenetic tree annotation | OSS | Emerging | 🟡 Pattern ref | ⚪ |
| 96 | **NDNET** | n (utility) | Anomaly+novelty detection unified framework | OSS | Emerging | ⚪ Defer | 🟡 Pillar I primitive |
| 97 | **MOLGENIS** | n (utility) | Secure genomics data management platform | OSS | Production | (covered in landscape doc §5.2.3) | (landscape doc) |
| 98 | **AnFiSA** | n (utility) | Open-source variant analysis platform | OSS | Production | 🟡 Reference | ⚪ |
| 99 | **libtissue** | k (AIS) | Distributed adaptive AIS for security/anomaly | OSS | Mature (security-domain) | ⚪ Not genomic | 🔵 Pillar II/III (substrate ref) |
| 100 | **NK-DCHS** | k (AIS) | Hybrid NK-cell + DC immune model for imbalanced AD | OSS | Emerging | ⚪ Not genomic | 🔵 Pillar II (algorithmic ref) |
| 101 | **ISIMD-ALNs** | k (AIS) | Immune-inspired malware detection (edge IoT) | OSS | Emerging | ⚪ Not genomic | 🔵 Pillar II (algorithmic ref) |
| 102 | **pyPOCQuant** | k (AIS) | POCT quantitative analysis (German group) | OSS | Production (POCT) | ⚪ Not genomic-discovery | 🔵 Pillar IV (training/POCT linkage) |
| 103 | **Galaxy@Sciensano** | e (surv platform) | Galaxy instance with custom microbial typing tools | OSS | Production | 🟡 Pattern ref | ⚪ |
| 104 | **VarFind** | n (utility) | NGS read simulation → mapping → variant calling | OSS | Emerging | 🟡 Reference for testing | ⚪ |

The exact tool count varies depending on how the deduplication of cross-listed tools is handled (MARTi, IDseq, PathoGFAIR, MARTi, Solu, KOMB/KombOver appear in multiple source docs), so the headline figure of "~85 unique tools" is rounded; the master matrix above lists ~104 entries because some tools that are cross-listed receive two rows (one per primary category placement). Section 2 deduplicates within categories.

---

## 2. Tool catalog by category

This section is the per-category catalog. Each subsection follows the same shape:

1. Brief intro — what's in the category, what makes them similar
2. Per-category matrix — tool / function / license / maturity / JACKPOT-current relevance / JACKPOT-immune relevance
3. Prose detail for the high-value rows only (✅ already shipped, 🟢 strong fit, or 🔵 mapped to an Immune Platform pillar). The 🟡 Reference / ⚪ Defer rows are self-explanatory from the matrix.

### 2.a Metagenomic pipelines for unknown/novel pathogens

This is the category most directly addressing the gap identified in Finding A (§0.5): JACKPOT's pipeline zoo is heavy on known-pathogen viral and bacterial genomics but thin on *untargeted* / *novel* pathogen detection. The 13 tools here all attempt unbiased mNGS — taking sequencing reads from a sample of unknown content and identifying pathogens (including ones not in any reference database) via combinations of read classification, de novo assembly, host filtering, and database-augmented inference.

| Tool | Function | License | Maturity | JACKPOT-current | JACKPOT-immune |
|---|---|---|---|---|---|
| **IDseq / CZID** | Cloud-based mNGS with host filtering, assembly, novelty detection | OSS (CZID Apache-2.0) | Production | 🟢 Reference platform — see §3.1 | 🔵 Pillar I (companion) |
| **TaxTriage** | Nextflow short+long-read classification + de novo assembly | OSS | Production (2026) | 🟢 ★ Adopt — `B-TAXTRIAGE-1` | 🔵 Pillar I |
| **nf-UnO** | Nextflow co-assembly outbreak novel-pathogen pipeline | OSS | Emerging (2025) | 🟢 Adopt — `B-NFUNO-1` | 🔵 Pillar I |
| **INSaFLU-TELEVIR** | Web-based viral mNGS + routine genomic surveillance suite | AGPL | Production | 🟢 ★ Adopt — `B-INSAFLU-1` | 🔵 Pillar I (viral side) |
| **cgMSI** | Strain-level nanopore MAP detection at low coverage | OSS | Medium | 🟢 Adopt — `B-CGMSI-1` | 🔵 Pillar I |
| **PathoGFAIR** | FAIR Galaxy-based nanopore pathogen workflows | OSS | Production | 🟡 Pattern ref | 🔵 Pillar I |
| **HPD-Kit** | Open-source toolkit + web UI for mNGS pathogen detection | OSS | Medium | 🟡 Study | 🔵 Pillar I |
| **DAMIAN** | Functional metagenomic novel-pathogen detection | OSS | Medium | 🟡 Study | 🔵 Pillar I |
| **Clin-mNGS** | Snakemake automated clinical mNGS pipeline | OSS | Medium | 🟡 Pattern ref | 🔵 Pillar I |
| **PhytoPipe** | Plant-pathogen RNA-seq pipeline (broad-host) | OSS | Medium | ⚪ One-Health adjacent | 🔵 Pillar I (plant-side) |
| **MetaGeneMiner** | Targeted gene extraction from metagenomes | OSS | Medium | 🟡 Reference | ⚪ |
| **MetaFX** | Reference-free feature extraction for metagenome ML | OSS | Medium | 🟡 Pattern ref | 🔵 Pillar I (feature primitive) |
| **MARTi** | Real-time nanopore metagenomic analysis (also category m) | OSS | Production | 🟢 Adopt — `B-MARTI-1` | 🔵 Pillar I |

#### 2.a.1 IDseq / CZID — reference platform for novel pathogen detection 🟢

IDseq (now CZ ID, run by the Chan Zuckerberg Initiative) is the most-cited open-source novel-pathogen detection pipeline in the source-doc literature. It is explicitly "designed with the specific intent of detecting novel pathogens" and was validated on synthetically evolved divergent viruses + early SARS-CoV-2 sequences. The architecture: cloud-based, host-filter → assembly → BLAST/DIAMOND alignment → background-subtracted novelty scoring → web UI.

JACKPOT's design relationship to IDseq is *complementary, not competitive*. IDseq is a hosted SaaS (you upload reads to CZ ID's cloud); JACKPOT is operator-agnostic infrastructure that can run mNGS pipelines locally on operator data. The more interesting integration question is "should JACKPOT's pipeline zoo include an IDseq-equivalent novel-pathogen detection workflow?" The answer per `B-TAXTRIAGE-1` is yes — but built on TaxTriage rather than CZ ID, since TaxTriage is a Nextflow workflow (drop-in fit for JACKPOT's pipeline executor), whereas IDseq is a hosted system. CZ ID stays as a *reference platform* for benchmarking and as a fallback hosted option for operators who don't want to run mNGS themselves.

#### 2.a.2 TaxTriage — drop-in novel-pathogen Nextflow workflow 🟢 ★

TaxTriage (Merritt et al., *Bioinformatics* 2026) is the highest-value adoption candidate in this category. It is a Nextflow workflow that combines read classification (Kraken2/Centrifuge), reference-mapping (Bowtie2), and de novo assembly (SPAdes/MEGAHIT) to detect putative pathogens — including novel agents — from short or long reads. It emits a structured pathogen-candidate report.

**Why this is the top candidate:**

- **Drop-in for JACKPOT's pipeline zoo.** JACKPOT's pipeline executor is Nextflow on GCP Batch. TaxTriage is Nextflow. Adoption is "add the spec file to the pipeline zoo" — a standard pattern that JACKPOT has shipped 12+ times for other pipelines.
- **Closes a real gap.** No current JACKPOT pipeline does untargeted novel-pathogen detection. The closest is `nf-core/taxprofiler` (already in the zoo) which does taxonomic profiling but not pathogen-candidate ranking with de novo assembly.
- **Production-published.** *Bioinformatics* 2026 release; has been benchmarked on real clinical mNGS datasets.

**Backlog:**

```text
[ ] B-TAXTRIAGE-1  Adopt nf-core/taxtriage (Merritt et al., Bioinformatics 2026)
                   into JACKPOT pipeline zoo as the canonical untargeted
                   pathogen-discovery workflow. Pipeline-zoo spec file +
                   integration with pipeline_results loader for the
                   pathogen-candidate output schema.
                   Effort: 2-3 sessions. Phase: pipeline-zoo work.
```

#### 2.a.3 nf-UnO — co-assembly novel-pathogen detection from outbreak read sets 🟢

nf-UnO (Guzman-Cole & Huang, *Bioinformatics* 2025) is a Nextflow co-assembly pipeline specifically for novel-pathogen detection across outbreak datasets. Rather than analyzing each sample independently, it co-assembles multiple samples to identify shared metagenome-assembled genomes (MAGs) representing the novel etiologic agent.

**Why this is high-value:**

- **Outbreak-investigation specialty.** When investigating an outbreak of unknown etiology (the classic "patients are sick, none of the standard tests work, what's the pathogen?" problem), single-sample detection often fails because the novel pathogen is at low abundance in any one sample. Co-assembly across the cohort dramatically improves recovery of the shared genome.
- **JACKPOT's case-cohort schema is the right substrate.** JACKPOT samples carry `case_id` linkage and can be grouped into outbreak cohorts via the dataset model. Running nf-UnO on a cohort is a natural workflow.
- **Complementary to TaxTriage.** TaxTriage works on individual samples; nf-UnO works on cohorts. Both belong in the pipeline zoo.

**Backlog:**

```text
[ ] B-NFUNO-1  Adopt nf-UnO (Guzman-Cole & Huang, Bioinformatics 2025) into
               JACKPOT pipeline zoo as the cohort co-assembly pipeline for
               outbreak novel-pathogen investigations. Wire to the dataset/
               cohort selection UI; outputs feed pipeline_results.
               Effort: 2 sessions. Phase: pipeline-zoo work, after B-TAXTRIAGE-1.
```

#### 2.a.4 INSaFLU-TELEVIR — viral metagenomic detection + surveillance suite 🟢 ★

INSaFLU-TELEVIR (Santos et al., *Genome Medicine* 2024) is an open AGPL web-based bioinformatics suite for viral metagenomic detection plus routine genomic surveillance. INSaFLU is the surveillance front-end (originally for influenza); TELEVIR is the metagenomic detection module added for SARS-CoV-2 era.

**Why this is high-value:**

- **AGPL-licensed.** Same license as JACKPOT — clean integration without licensing friction.
- **Closes the viral-mNGS gap.** TaxTriage covers untargeted detection broadly; INSaFLU-TELEVIR is viral-specialized and well-validated for viral metagenomics specifically.
- **Reference for the LAPIS-compat Year-2 work** (`B-LAPIS-1` in the platform landscape). INSaFLU's REST API and visualization patterns are useful prior art for the JACKPOT viral-data API surface.
- **Pillar I component.** Maps directly to the Immune Platform plan's Pillar I as the "viral signal" arm of the bio-anomaly stack.

**Backlog:**

```text
[ ] B-INSAFLU-1  Evaluate INSaFLU-TELEVIR for adoption: viral mNGS pipeline
                 (TELEVIR module) into JACKPOT pipeline zoo; INSaFLU REST
                 API patterns as prior art for the LAPIS-compat work
                 (B-LAPIS-1). Decide whether to adopt the TELEVIR pipeline
                 directly or fork+adapt.
                 Effort: 1 session study + 2 sessions adoption.
                 Phase: Year 2.
```

#### 2.a.5 cgMSI — strain-level nanopore detection at low coverage 🟢

cgMSI (Zhu et al., *BMC Bioinformatics* 2023) is an open-source MAP (Maximum A Posteriori) estimation tool for strain-level pathogen detection from nanopore metagenomic data. It works at extremely low coverage (≥1× per strain), which is the regime real field deployments operate in.

**Why this is high-value:**

- **Specifically targets the "novel strain within a known species" problem.** Many real surveillance failures aren't novel-species detection but novel-strain detection within a known species (e.g., a new SARS-CoV-2 variant of concern, a new C. auris clade). cgMSI is purpose-built for this.
- **Nanopore-native.** JACKPOT's design supports both Illumina and Nanopore reads; nanopore-specialized tools complement the predominantly-Illumina pipeline zoo.
- **Lightweight integration.** cgMSI is a single binary with a strain database; pipeline-zoo integration is simple.

**Backlog:**

```text
[ ] B-CGMSI-1  Add cgMSI (Zhu et al., 2023) to pipeline zoo as the
               nanopore strain-level detection tool. Pairs with MARTi
               (B-MARTI-1) which provides the real-time analysis layer.
               Effort: 1-2 sessions. Phase: pipeline-zoo work.
```

#### 2.a.6 MARTi — real-time nanopore metagenomic surveillance 🟢

MARTi (Peel et al., *Genome Research* 2025) is an open-source platform for real-time analysis and visualization of nanopore metagenomic samples. It performs ongoing read classification (Kraken2/Centrifuge/BLAST), AMR-gene detection, and an interactive web dashboard updating as the sequencer runs.

**Cross-references:** Also surfaced in §2.c as an anomaly-detection-capable tool and §2.m as a real-time analysis platform. Primary placement is here under metagenomic pipelines because the underlying function is metagenomic classification; the real-time / anomaly-detection facets are secondary.

**Why this is high-value:**

- **Field-deployment ready.** Designed for Nanopore MinION-based field surveillance — outbreak investigation, port-of-entry screening, environmental sampling.
- **Pairs naturally with cgMSI.** MARTi gives you "what's in this sample, in real time"; cgMSI gives you "which strain of the things I found." Both run on the same nanopore reads.
- **Pillar I component.** Real-time bio-anomaly detection at the field level is exactly what the Immune Platform plan envisions for low-resource deployments.

**Backlog:**

```text
[ ] B-MARTI-1  Add MARTi (Peel et al., Genome Research 2025) to pipeline
               zoo with real-time WebSocket updates to the JACKPOT UI.
               This is the "watch the run as it sequences" workflow,
               a demonstrably differentiator vs platforms that only
               accept post-run input.
               Effort: 2-3 sessions (real-time UI integration is the
               nontrivial part). Phase: post-staging-cutover.
```

---

### 2.b ML/AI pathogen classifiers

The 11 tools in this category apply machine learning — random forests, deep neural networks (CNNs/LSTMs), transformers, explainable AI — to the pathogen detection problem. They differ in *what* they classify (sequences, reads, k-mer features, environmental risk) and in *how interpretable* they are. The Immune Platform plan's Pillar I anticipates several of these as components.

| Tool | Function | License | Maturity | JACKPOT-current | JACKPOT-immune |
|---|---|---|---|---|---|
| **DeePaC** | CNN/LSTM predicting pathogenicity from raw DNA | OSS | Production | 🟢 Adopt — `B-DEEPAC-1` | 🔵 Pillar I (DL classifier) |
| **MLM** | ML threat characterization (RF, Bayesian) for unmapped reads | OSS | Production | 🟢 Adopt — `B-MLM-1` | 🔵 Pillar I |
| **GRUMB** | Genome-resolved metagenomic + ML pathogen-risk score | OSS | Emerging (2025) | 🟡 Study | 🔵 Pillar I (risk-scoring layer) |
| **PathoLive** | Real-time relevance-scored pathogen ID during sequencing | OSS | Medium | 🟡 Study | 🔵 Pillar I |
| **AutoXAI4Omics** | Explainable ML anomaly detection for food microbiomes | OSS | Emerging | 🟡 Study | 🔵 Pillar I (XAI primitive) |
| **MegaR** | Interactive R package for metagenome ML model building | OSS | Medium | 🟡 Reference | ⚪ |
| **Plant ML detector** (Johnson 2023) | Reference-free RF disease detection (long reads) | OSS | Emerging | 🟡 Reference | 🔵 Pillar I (RF primitive) |
| **DCiPatho** | Deep cross-fusion network for pathogen identification | OSS | Emerging | 🟡 Study | 🔵 Pillar I (DL primitive) |
| **ExplaiNN** | Interpretable neural networks for genomics | OSS | Production | 🟡 Reference | 🔵 Pillar I (XAI primitive) |
| **IDMIL** | Alignment-free interpretable deep MIL for disease prediction | OSS | Medium | 🟡 Reference | 🔵 Pillar I |
| **EdeepVPP** | Explainable deep viral genome prediction | OSS | Medium | 🟡 Reference | 🔵 Pillar I (viral DL) |

#### 2.b.1 DeePaC — predicting pathogenicity from raw DNA 🟢

DeePaC (Bartoszewicz et al., *Bioinformatics* 2020) uses reverse-complement-aware CNN/LSTM neural networks to predict pathogenic potential of novel DNA sequences. Input: raw reads (FASTA/FASTQ). Output: per-sequence pathogenicity score with class predictions (human-pathogenic, plant-pathogenic, animal-pathogenic, non-pathogenic).

**Why this is high-value:**

- **Closes a true gap.** Nothing in JACKPOT's current pipeline zoo predicts pathogenicity of *novel* sequences — i.e., sequences for which database alignment fails. DeePaC fills this exactly.
- **Pairs naturally with TaxTriage and MLM.** TaxTriage finds candidate novel agents → MLM characterizes threats among unmapped reads → DeePaC scores pathogenic potential. The three together form a full novel-pathogen-discovery pipeline.
- **Reverse-complement awareness is the right design choice.** DNA is double-stranded; treating forward/reverse as the same instance is biologically correct and reduces overfitting.

**Backlog:**

```text
[ ] B-DEEPAC-1  Add DeePaC pathogenicity scoring as a post-classification
                step in the TaxTriage pipeline-zoo entry. Output a
                per-sequence pathogenicity score field on
                pipeline_results JSONB.
                Effort: 1-2 sessions, after B-TAXTRIAGE-1.
                Phase: pipeline-zoo work.
```

#### 2.b.2 MLM — ML threat characterization for unmapped reads 🟢

MLM (Baugher et al., *JHU APL Technical Digest* 2025) is APL's open-source machine-learning system for threat characterization of unmapped metagenomic reads. It uses random-forest and Bayesian-network classifiers trained on labeled threat data (BSL classification, function predictions, similarity to known pathogens).

**Why this is high-value:**

- **Specifically targets the "what about the unmapped reads?" problem.** Standard mNGS pipelines discard reads that don't map to anything. MLM analyzes those discards — precisely where novel pathogens hide.
- **Complements DeePaC.** DeePaC scores per-sequence pathogenic potential. MLM classifies reads into threat tiers. They operate on similar data but produce different outputs; running both gives more confident calls.
- **From APL.** APL's threat-characterization work has direct biosecurity-domain credibility; the same lab built AMAnD (the headline anomaly-detection tool from §2.c).

**Backlog:**

```text
[ ] B-MLM-1  Adopt MLM (Baugher et al., 2025) into pipeline zoo as the
             unmapped-read threat-characterization stage. Wire into the
             TaxTriage pipeline output (post-DeePaC) for tiered
             threat-class assignment.
             Effort: 2 sessions. Phase: pipeline-zoo work, after
             B-TAXTRIAGE-1 + B-DEEPAC-1.
```

#### 2.b.3 GRUMB — genome-resolved metagenomic risk scoring 🟡 → 🟢 (immune)

GRUMB (Aminu et al., *Bioinformatics* 2025) integrates genome-resolved metagenomics (MAG recovery from environmental samples) with ML-based pathogen-risk scoring. Designed for urban microbiome surveillance — wastewater, transit-system samples, building-environment monitoring.

**Why this is "study now, adopt later":**

- The risk-scoring layer is novel and well-suited to the JACKPOT environmental sectors (wastewater, soil, surface, food, produce).
- But GRUMB is brand-new (2025); benchmarking against existing approaches is still early.
- The Immune Platform plan's Pillar I explicitly anticipates a risk-scoring layer over MAG recovery; GRUMB is the leading candidate when the time comes to implement that.

```text
[ ] B-GRUMB-1  Study GRUMB (Aminu et al., 2025) for the environmental
               metagenomics + risk-scoring layer of Pillar I. Decide:
               adopt directly, fork+adapt, or build alternative.
               Effort: 2-3 weeks study. Phase: when Pillar I implementation
               begins (Year 2+).
```

---

### 2.c Genomic anomaly detection

Just five tools but high-value ones — these are the closest existing analogues to what the Immune Platform plan's Pillar I aims to build natively. The tools here detect *anomalies* in genomic / metagenomic data: samples that are statistically unusual versus a baseline, regardless of whether the anomaly maps to a known pathogen.

| Tool | Function | License | Maturity | JACKPOT-current | JACKPOT-immune |
|---|---|---|---|---|---|
| **AMAnD** | DeepSVDD one-class metagenome anomaly detection | OSS | Production | 🟢 Adopt — `B-AMAND-1` | 🔵 Pillar I core |
| **UltraSEQ** | Universal metagenomic classification + anomaly | OSS | Medium | 🟡 Pattern ref | 🔵 Pillar I |
| **PhyloMagnet** | Gene-centric phylogenetic screening of meta-omics | OSS | Medium | 🟡 Pattern ref | 🔵 Pillar I |
| **KOMB / KombOver** | k-core graph-based microbiome perturbation detection | OSS | Medium | 🟡 Study | 🔵 Pillar I (community-shift detector) |
| **MARTi** | Real-time anomaly characterization (cross-listed) | OSS | Production | (see 2.a.6) | (see 2.a.6) |

#### 2.c.1 AMAnD — DeepSVDD metagenome anomaly detection 🟢 ★

AMAnD (Price & Russell, *Frontiers in Public Health* 2023) is the headline tool of this category. It uses Deep Support Vector Data Description (DeepSVDD) — a one-class neural network anomaly detector — to flag anomalous metagenomes. AMAnD is trained on a baseline of "normal" samples (e.g., healthy gut microbiomes) and flags samples that deviate. It explicitly handles novel anomalies — i.e., it doesn't require examples of "what bad looks like" to flag anomalous content.

**Why this is the highest-value adoption candidate in the entire category:**

- **Direct fit for Pillar I core.** The Immune Platform plan §4 describes a metagenome-anomaly layer almost identical to AMAnD's design (one-class deep learning on metagenome features, drift-aware retraining). AMAnD is the closest existing thing to that pillar.
- **No JACKPOT equivalent.** Nothing else in the pipeline zoo or roadmap covers metagenome anomaly detection with one-class learning. Adding AMAnD doesn't duplicate any shipped functionality.
- **From APL.** Same lab as MLM (§2.b.2); both are battle-tested in real biodefense contexts.
- **Production-deployed.** Published 2023; available on GitHub; used in respiratory + gut + synthetic-contamination biosurveillance contexts.

**Caveat:** AMAnD requires training data — a baseline of "normal" samples for the deployment context. For a small operator this is a meaningful operational burden. The Immune Platform plan addresses this via the JACKPOT Academy curriculum (Pillar IV) — operators are trained on baseline curation as part of the platform deployment process.

**Backlog:**

```text
[ ] B-AMAND-1  Adopt AMAnD (Price & Russell, 2023) as the canonical
               metagenome anomaly detector in JACKPOT. Initially as a
               pipeline-zoo entry; once Pillar I lands, as the core of
               jackpot-immune-bio. Document the baseline-curation workflow
               (what is "normal" for this operator's deployment context)
               in the Pillar IV training materials.
               Effort: 3 sessions pipeline-zoo + 2 weeks for the baseline-
               curation tooling. Phase: pipeline-zoo work + Pillar I.
```

#### 2.c.2 UltraSEQ — universal metagenomic classification with anomaly flagging 🟡 / 🔵

UltraSEQ (Gemler et al., *Microbiology Spectrum* 2023) is a "universal bioinformatic platform for information-based clinical metagenomics." It combines reference-based classification with information-theoretic anomaly flagging — sequences that don't fit known categories are flagged as candidates for further analysis.

**Why this is a Pattern Reference rather than direct adoption:**

- The information-theoretic approach is intellectually interesting and complementary to AMAnD's one-class deep-learning approach.
- But UltraSEQ overlaps significantly with TaxTriage in scope (universal classification) and AMAnD in function (anomaly flagging). Adding UltraSEQ alongside both would be redundant.
- Recommendation: study UltraSEQ's information-theoretic novelty score as a candidate enhancement to TaxTriage's classifier output. No standalone adoption needed.

#### 2.c.3 KOMB / KombOver — graph-based microbiome perturbation detection 🟡 → 🟢 (immune)

KOMB (Balaji et al., *CSBJ* 2022) and its successor KombOver (Sapoval et al., *PSB* 2024) detect microbial-community structural anomalies using k-core and K-Truss graph algorithms over read-overlap graphs. Output: a perturbation score for each sample relative to a reference cohort.

**Why this is "study now, candidate later":**

- KOMB/KombOver detects *community-level* anomalies — disruptions in the structure of the microbial community, not just presence of new species. This is a different and complementary signal from per-sample classification.
- The Immune Platform plan's Pillar I anticipates a community-shift layer; KOMB is a strong candidate for that role.
- But it's still emerging (2022/2024 publications); benchmarking is incomplete.

```text
[ ] B-KOMB-1  Study KOMB/KombOver for the community-shift detection
              layer of Pillar I. Pairs with AMAnD (per-sample anomaly)
              for two complementary signals.
              Effort: 1-2 weeks study. Phase: with B-AMAND-1.
```

---

### 2.d SV/CNV/SNP variant callers for pathogens

This is the largest category by tool count (18 tools) and the one with the most "available via pipelines, no separate adoption needed" entries. Variant calling is a mature technical area — the major open-source callers (Manta, DELLY, LUMPY, Sniffles2, cuteSV) ship as components inside countless Nextflow/Snakemake pipelines, including ones already in JACKPOT's zoo. The action is at the *bacterial-genome-specific* variant callers (which are a small but important subset) and the WGS-SNP detection tools that JACKPOT could adopt to broaden its outbreak-genomics capabilities.

| Tool | Function | License | Maturity | JACKPOT-current | JACKPOT-immune |
|---|---|---|---|---|---|
| **CNproScan** | CNV detection for bacterial genomes (GC-bias-aware) | OSS | Medium | 🟢 Adopt — `B-CNPRO-1` | ⚪ |
| **ProcaryaSV** | SV detection pipeline for bacterial short-read data | OSS | Medium | 🟢 Adopt — `B-PROSV-1` | ⚪ |
| **SNiPgenie** | Microbial WGS SNP detection | OSS | Production | 🟢 Adopt — `B-SNIPG-1` | ⚪ |
| **SKA2** | Split-k-mer bacterial genotyping; rapid variant calling | OSS | Production | 🟢 Adopt — `B-SKA2-1` | ⚪ |
| **Manta** | SV caller (Illumina; widely used) | OSS | Production | 🟡 Available via pipelines | ⚪ |
| **CNVnator** | Read-depth CNV caller | OSS | Production | 🟡 Available via pipelines | ⚪ |
| **DELLY** | SV/CNV caller for short-read data | OSS | Production | 🟡 Available via pipelines | ⚪ |
| **LUMPY** | SV caller integrating multiple signals | OSS | Production | 🟡 Available via pipelines | ⚪ |
| **BreakDancer** | SV caller for paired-end reads | OSS | Production | 🟡 Available via pipelines | ⚪ |
| **SVABA** | Local-assembly SV detection | OSS | Production | 🟡 Available via pipelines | ⚪ |
| **CNVkit** | CNV detection for NGS | OSS | Production | 🟡 Available via pipelines | ⚪ |
| **Sniffles2** | Long-read SV caller (gold standard) | OSS | Production | 🟡 Available via pipelines | ⚪ |
| **cuteSV** | Long-read SV caller (consensus partner with Sniffles2) | OSS | Production | 🟡 Available via pipelines | ⚪ |
| **PBHoney** | PacBio-specific SV caller | OSS | Medium | 🟡 Available via pipelines | ⚪ |
| **TRsv** | Tandem-repeat SV/CNV/indel from long reads | OSS | Emerging | 🟡 Reference | ⚪ |
| **SENSV** | Nanopore-optimized SV at low depth | OSS | Medium | 🟡 Reference | ⚪ |
| **VizCNV** | CNV visualization + trio-aware interpretation | OSS | Medium | 🟡 Reference | ⚪ |
| **GATK-gCNV** | CNV from exome (out of pathogen scope) | OSS | Production | ⚪ Out of scope | ⚪ |

#### 2.d.1 CNproScan — bacterial-aware CNV detection 🟢

CNproScan (Jugas et al., *Genomics* 2021) is a hybrid CNV detector built specifically for bacterial genomes. It accounts for two facts that generic CNV callers (CNVnator, CNVkit) get wrong on bacteria: (1) bacterial genomes are circular, and (2) GC-content bias varies markedly across bacterial taxa.

**Why this is high-value:**

- **No JACKPOT equivalent.** None of the bacterial-typing pipelines in the zoo (bactopia, mycosnp, tb-profiler) call CNVs. Bacterial CNV detection is a real but underserved use case (gene-copy variation drives AMR, virulence, host adaptation).
- **Drop-in.** CNproScan is a single tool; pipeline-zoo integration is straightforward.
- **Bacterial-typing-zoo-friendly.** Outputs JSON which maps cleanly to JACKPOT's pipeline_results JSONB schema.

**Backlog:**

```text
[ ] B-CNPRO-1  Adopt CNproScan (Jugas et al., 2021) as a bacterial CNV
               pipeline-zoo entry. Wire to pipeline_results loader.
               Useful especially for AMR-gene copy number variation,
               which generic CNV callers miss.
               Effort: 1-2 sessions. Phase: pipeline-zoo work.
```

#### 2.d.2 ProcaryaSV — bacterial SV pipeline 🟢

ProcaryaSV (Jugas & Vitkova, *BMC Bioinformatics* 2024) is a structural-variation detection pipeline specifically for bacterial short-read sequencing data. It's authored by the same group as CNproScan and shares the same bacterial-aware design philosophy.

**Why this is high-value:**

- **Same gap as CNproScan but for SVs.** Generic SV callers (Manta, DELLY) work on bacteria but lose accuracy on circular genomes and bacterial-specific features (insertion sequences, prophages, plasmid-mediated mobile elements).
- **Adopt alongside CNproScan.** Together they cover the bacterial CNV+SV space cleanly.

**Backlog:**

```text
[ ] B-PROSV-1  Adopt ProcaryaSV (Jugas & Vitkova, 2024) as the bacterial
               SV pipeline-zoo entry. Pairs with CNproScan (B-CNPRO-1)
               for full bacterial CNV+SV coverage.
               Effort: 1-2 sessions. Phase: pipeline-zoo work, with
               B-CNPRO-1.
```

#### 2.d.3 SNiPgenie — microbial WGS SNP detection 🟢

SNiPgenie (Farrell et al., *Access Microbiology* 2025) is an open-source microbial SNP-site detection tool optimized for WGS data. The novel bit: it's built around an iterative reference-update workflow — call SNPs, refine the reference with consensus, re-call. This gives sharper outbreak-cluster definition than single-pass callers.

**Why this is high-value:**

- **Outbreak genomics workflow alignment.** Bacterial outbreak investigation relies on cgMLST or wgSNP-based clustering; SNiPgenie produces inputs for both. JACKPOT's pipeline zoo currently relies on bactopia for SNP calling — adding SNiPgenie gives a second, simpler-to-deploy option.
- **Lightweight integration.** Single binary, well-documented.

**Backlog:**

```text
[ ] B-SNIPG-1  Add SNiPgenie (Farrell et al., 2025) as an alternative
               SNP-calling pipeline-zoo entry to bactopia for cases where
               bactopia is overkill (single-organism outbreak; not the
               full bactopia workflow).
               Effort: 1 session. Phase: pipeline-zoo work.
```

#### 2.d.4 SKA2 — split-k-mer bacterial genotyping 🟢

SKA2 (Derelle et al., *Genome Research* 2024) uses split k-mers for bacterial genotyping and rapid variant calling. It's optimized for speed at the cost of some sensitivity vs. full alignment-based methods — a useful trade-off when triaging large outbreak datasets.

**Why this is high-value:**

- **Speed.** SKA2 is dramatically faster than alignment-based callers; useful for "first-pass triage" of a large dataset before committing to deeper analysis.
- **Reference-free.** Split-k-mer comparisons don't require a perfect reference, which matters for novel/divergent strains.
- **Pairs with SNiPgenie.** SKA2 for triage → SNiPgenie for confirmed-outbreak deep-dive.

**Backlog:**

```text
[ ] B-SKA2-1  Add SKA2 (Derelle et al., 2024) as the rapid-triage
              variant-calling pipeline-zoo entry. Recommended workflow:
              SKA2 for first-pass cluster identification across all
              samples, then SNiPgenie + bactopia for the focal cluster.
              Effort: 1 session. Phase: pipeline-zoo work, with B-SNIPG-1.
```

---

### 2.e Genomic surveillance platforms (component-level)

This category overlaps with the *platform-tier* coverage in `jackpot_platform_landscape.md` — but at a different scope. The platform landscape doc surveys *systems* JACKPOT is in design-space competition with (Loculus, GenSpectrum, Pathogenwatch). The 13 entries here are *component-level* surveillance tools — narrower-scope pipelines or apps that solve specific outbreak-genomics problems and could be integrated by JACKPOT as pipeline-zoo entries or schema modules. Six are direct adoption candidates (🟢); the rest are pattern references.

| Tool | Function | License | Maturity | JACKPOT-current | JACKPOT-immune |
|---|---|---|---|---|---|
| **NanoCore** | Core-genome bacterial surveillance for Nanopore+Illumina | OSS | Production | 🟢 Adopt — `B-NANOC-1` | ⚪ |
| **Pf-HaploAtlas** | Open-source app for malaria genomic surveillance | OSS | Medium | 🟢 Adopt for malaria — `B-PFHAP-1` | ⚪ |
| **pyMLST** | cgMLST bacterial clonality analysis | OSS | Production | 🟢 Adopt — `B-PYMLST-1` | ⚪ |
| **AMRomics** | Scalable microbial-genome AMR surveillance | OSS | Medium | 🟢 Adopt — `B-AMRO-1` | ⚪ |
| **OpenRecombinHunt** | Viral recombination detection | OSS | Medium | 🟢 Adopt — `B-RECOMB-1` | ⚪ |
| **rMAP 2.0** | WDL+Cromwell+Docker ESKAPEE workflow | OSS | Production | 🟡 Pattern ref for WDL | ⚪ |
| **PathoSPOT** | Outbreak tracing via WGS | OSS | Production | 🟡 Pattern ref for nosocomial | ⚪ |
| **Pangolin** | SARS-CoV-2 lineage assignment | OSS | Production | ✅ Already shipped | ⚪ |
| **Nextstrain** | Pathogen evolution tracking + Auspice viz | OSS | Production | ✅ Available via pipelines | ⚪ |
| **IRIDA-ARIES** | Italy One-Health genomic surveillance suite | OSS | Production | 🟡 Pattern ref | ⚪ |
| **Hygieia** | AI/ML pipeline for gene-disease association | OSS | Emerging | 🟡 Reference | ⚪ |
| **Machado** | Python genomics integration framework (Brazil) | OSS | Medium | 🟡 Pattern ref | ⚪ |
| **BacSeq** | Automated bacterial WGS pipeline | OSS | Medium | 🟡 Pattern ref | ⚪ |
| **GenomeDepot** | Microbial comparative genomics platform | OSS | Medium | 🟡 Pattern ref | ⚪ |
| **Galaxy@Sciensano** | Galaxy instance with custom microbial typing tools | OSS | Production | 🟡 Pattern ref | ⚪ |

#### 2.e.1 NanoCore — core-genome surveillance for Nanopore+Illumina 🟢

NanoCore (Fuchs et al., *mSystems* 2024) is an open-source pipeline for core-genome-based bacterial outbreak detection in healthcare facilities, accepting both Nanopore and Illumina reads. Critical feature: it cleanly handles the Nanopore-Illumina hybrid case — same outbreak being tracked across labs using different sequencers.

**Why this is high-value:**

- **Sequencer-agnostic outbreak tracking.** Most cgMLST tools assume Illumina-style read quality. NanoCore explicitly handles Nanopore (lower per-base accuracy, longer reads) and produces comparable cluster definitions. For a federation of operators using mixed sequencer fleets, this matters.
- **Healthcare-facility focus aligns with JACKPOT's STLT operator profile.** State health labs running outbreak investigations on healthcare-associated infections are exactly the use case NanoCore was built for.
- **Production-validated.** Real outbreak deployments referenced in the publication.

**Backlog:**

```text
[ ] B-NANOC-1  Adopt NanoCore (Fuchs et al., mSystems 2024) as the
               canonical Nanopore-aware core-genome outbreak-tracking
               pipeline. Pairs with bactopia (already shipped) for
               Illumina-only workflows; NanoCore handles the mixed-
               sequencer federation case.
               Effort: 2 sessions. Phase: pipeline-zoo work.
```

#### 2.e.2 Pf-HaploAtlas — malaria genomic surveillance app 🟢

Pf-HaploAtlas (Lee et al., *Bioinformatics* 2024) is an open-source web app for *Plasmodium falciparum* genomic surveillance. It tracks haplotype diversity at drug-resistance loci globally and exposes this as a queryable atlas with timeline visualizations.

**Why this is high-value:**

- **Closes a real gap for any malaria-tracking operator.** No other pipeline in JACKPOT's zoo handles malaria. For operators in malaria-endemic regions (the very regions WHO/IPSN is targeting for capacity building), a malaria-specific pipeline-zoo entry is critical.
- **Concrete schema implications.** Pf-HaploAtlas's haplotype model is a useful prior art for any future JACKPOT schema extension to support eukaryotic-pathogen genomic surveillance more broadly.
- **Publicly hosted at malariagen.net.** JACKPOT can defer to the hosted version for operators that want it, or self-host the open-source backend.

**Backlog:**

```text
[ ] B-PFHAP-1  Adopt Pf-HaploAtlas (Lee et al., 2024) as the malaria-
               specific pipeline-zoo entry. Self-hostable; outputs feed
               pipeline_results JSONB. Document the schema mapping for
               haplotype data.
               Effort: 2-3 sessions. Phase: pipeline-zoo work.
```

#### 2.e.3 pyMLST — cgMLST bacterial clonality 🟢

pyMLST (Biguenet et al., *Microbial Genomics* 2023) is an open-source tool for assessing bacterial clonality using core genome MLST. Critical feature: it ships its own database management (you can build a custom cgMLST scheme for your organism) — useful when chewBBACA or PubMLST schemes don't cover the target species.

**Why this is high-value:**

- **Custom schema support.** JACKPOT operators often deal with non-standard organisms where the pre-built cgMLST schemes don't exist. pyMLST is the right tool for that case.
- **Lightweight.** Pure Python; easy to run inside a Nextflow process.
- **Good benchmark performance.** The publication shows comparable accuracy to chewBBACA on benchmark organisms with much faster runtimes.

**Backlog:**

```text
[ ] B-PYMLST-1  Adopt pyMLST as the custom-cgMLST-scheme pipeline-zoo
                entry. Default schema source is pubMLST; operators can
                build custom schemes for non-standard organisms.
                Effort: 1-2 sessions. Phase: pipeline-zoo work.
```

#### 2.e.4 AMRomics — scalable AMR surveillance 🟢

AMRomics (Le et al., *BMC Genomics* 2024) is a scalable workflow for AMR analysis across large microbial-genome collections. It coordinates AMR-gene detection (via a curated detection panel), resistance-phenotype prediction, and population-level resistance-trend computation across thousands-of-isolates datasets.

**Why this is high-value:**

- **AMR is a key JACKPOT differentiator.** The Immune Platform plan and the platform landscape both emphasize AMR surveillance as a core JACKPOT capability. AMRomics is one of the better open-source AMR surveillance pipelines in the literature.
- **Pairs with hAMRonization (`B-NCBI-2`).** AMRomics produces hAMRonization-compatible output, simplifying integration with the JACKPOT pipeline-result schema.
- **Scales.** Designed for thousands-of-isolates datasets; matches the kind of population-scale AMR analysis JACKPOT operators (state DOH labs) need.

**Backlog:**

```text
[ ] B-AMRO-1  Adopt AMRomics (Le et al., 2024) as the population-scale
              AMR-surveillance pipeline-zoo entry. Pairs with B-NCBI-2
              (hAMRonization output mandate) for clean cross-pipeline
              comparability.
              Effort: 2-3 sessions. Phase: pipeline-zoo work, with
              B-NCBI-2.
```

#### 2.e.5 OpenRecombinHunt — viral recombination detection 🟢

OpenRecombinHunt (Alfonsi et al., *J. Mol. Biol.* 2026) is an open-source tool for automatic detection of recombination in publicly-available viral sequences. It runs as a periodic-scan workflow against a reference set; flags candidate recombinants for downstream analysis.

**Why this is high-value:**

- **Genuine novel-event detection.** Viral recombinants drive variant emergence (XBB, KP.3, the entire SARS-CoV-2 recombinant alphabet). Automated recombinant detection is missing from JACKPOT's current pipeline zoo.
- **Pillar I-adjacent.** While not strictly an Immune Platform component (recombination detection is a viral-evolution signal, not a metagenome-anomaly signal), it pairs naturally with the bio-anomaly stack — recombinants are exactly the kind of "novel pathogen variant" Pillar I aims to surface.

**Backlog:**

```text
[ ] B-RECOMB-1  Adopt OpenRecombinHunt (Alfonsi et al., 2026) as the
                viral-recombination-detection pipeline-zoo entry. Wire
                to a periodic-scan workflow that runs on JACKPOT's
                public viral datasets.
                Effort: 2 sessions. Phase: pipeline-zoo work.
```

---

### 2.f Event-based outbreak intelligence

These six tools work on signals *outside* genomics — news streams, social media, ProMED reports, syndromic surveillance — to detect outbreak signals as early epidemic intelligence. None are genomics-native, but several are critical companion signals for the Immune Platform plan's Pillar I (which envisions multi-modal danger signals beyond just sequencing data).

| Tool | Function | License | Maturity | JACKPOT-current | JACKPOT-immune |
|---|---|---|---|---|---|
| **EIOS** | WHO open-source NLP/ML outbreak signal detection | OSS | Production | 🟡 Reference for ReportStream-class integration | 🔵 Pillar I (external signal feed) |
| **EPIWATCH** | ML+NLP early-epidemic-signal detection from OSINT | OSS | Production | 🟡 Reference | 🔵 Pillar I |
| **Epitweetr** | EU-CDC ML anomaly detection for outbreak signals | OSS | Production | 🟡 Reference | 🔵 Pillar I |
| **PADI-Web** | Multilingual animal-disease event-based surveillance | OSS | Medium | 🟡 Reference for One-Health reach | 🔵 Pillar I |
| **News-EDS** | ML-based news epidemic disease detection | OSS | Emerging | ⚪ Defer | 🔵 Pillar I (open-source signal feed) |
| **ProMED-mail** | Volunteer-curated outbreak reports | Free | Production | 🟡 Reference | 🔵 Pillar I (open-source signal) |

#### 2.f.1 EIOS — WHO Epidemic Intelligence from Open Sources 🟡 / 🔵

EIOS (Sallam et al., *J. Infect. Public Health* 2024; Williams et al., *BMC Public Health* 2025) is the WHO's flagship open-source NLP/ML platform for early outbreak signal detection from open-source intelligence (news, social media, official reports). The recent African-region evaluation (Williams 2025) showed strong detection performance for early epidemic signals in low-resource settings.

**Why this is a Pattern Reference + Pillar I component:**

- **Not a genomics tool — but the right reference for what an "external signal feed" looks like.** The Immune Platform plan's Pillar I (`jackpot-immune-bio`) §4.3 anticipates multi-modal danger signals — and EIOS is the canonical example of what such a signal feed looks like in production.
- **Operational workflow integration is the question, not architecture.** A JACKPOT operator that wants EIOS-style early-warning needs to subscribe to EIOS feeds and ingest signals; the JACKPOT side is "accept EIOS-format signals and route them into the bio-anomaly correlation engine." This is doable today via the dataset model + audit log; the gap is documentation, not code.

**Backlog:**

```text
[ ] B-EIOS-1  Document the EIOS signal-feed integration pattern for
              JACKPOT operators. Define the JSON-schema for incoming
              EIOS events and how they appear in JACKPOT's audit log
              and bio-anomaly correlation. No code yet — this is
              documentation work; full implementation is a Pillar I
              deliverable in Year 2+.
              Effort: 1 session documentation. Phase: pre-Pillar I.
```

#### 2.f.2 EPIWATCH — ML-powered open-source early-epidemic detection 🔵

EPIWATCH (UNSW + Kirby Institute) is an open-source AI-powered early-epidemic-signal-detection system. Multi-source: news, social media, ProMED, official reports. Used in monkeypox monitoring (Hutchinson et al., *Public Health* 2023) and broader emerging-infection surveillance.

**Why this is a Pillar I component candidate:**

- **Multilingual, global coverage.** Critical for the WHO/IPSN-aligned operator base (state DOH operators in any region).
- **Pairs with EIOS.** EIOS focuses on WHO-canonical signal-detection; EPIWATCH focuses on broader OSINT and emerging-pathogen specificity. Both feed the same Pillar I correlation engine.

The integration pattern is the same as for EIOS — JACKPOT operators ingest EPIWATCH signals as a feed; JACKPOT's bio-anomaly correlation surfaces samples concurrent with EPIWATCH-flagged events. No code changes needed today; document the pattern and pin specifics for Pillar I.

#### 2.f.3 ProMED-mail — volunteer-curated outbreak reports 🔵

ProMED-mail is the longest-running digital outbreak-reporting service. Free (not OSS in the strict sense — content licensed differently from code), but freely accessible feeds. Most major outbreak signals in the last 30 years went out on ProMED before any other channel.

**Why this is a Pillar I signal feed:**

- **Longest-running feed.** The most consequential signal source for emerging pathogens; any Immune Platform deployment needs to subscribe.
- **Already integrated into EIOS.** EIOS pulls ProMED among its sources, so technically EIOS-integration covers ProMED. But documenting ProMED as a first-class feed is good operator-education.

---

### 2.g Disease-specific outbreak anomaly detection

Three tools, all disease-specific and all operationally useful but architecturally distinct from anything JACKPOT does today. Inclusion here is not a "consider adopting these" recommendation — they're domain-specific tools with their own audiences. Inclusion is to surface the *ensemble pattern* common to all three: combining multiple anomaly-detection algorithms (ARIMA, EWMA, Isolation Forest, etc.) into an ensemble that calls outbreaks more reliably than any single algorithm.

| Tool | Function | License | Maturity | JACKPOT-current | JACKPOT-immune |
|---|---|---|---|---|---|
| **Thailand malaria AD** (Srimokla et al. 2024) | 9-algorithm anomaly detection ensemble for malaria EWS | OSS | Medium | ⚪ Domain-specific | 🔵 Pillar I (ensemble pattern) |
| **Brazil Amazon malaria AD** (Eze et al. 2023) | ML detectors for outbreak onset/peaks (endemic disease) | OSS | Medium | ⚪ Domain-specific | 🔵 Pillar I (ensemble pattern) |
| **China hybrid EWS** (Zhang et al. 2026) | Hybrid SEIR + ML anomaly detection for infectious disease | OSS | Medium | ⚪ Domain-specific | 🔵 Pillar I (multi-signal pattern) |

#### 2.g.1 The ensemble-detection pattern 🔵

What's common across all three: combining multiple anomaly-detection algorithms into an ensemble. The Thailand malaria EWS uses 9 algorithms (ARIMA, EWMA, CUSUM, Isolation Forest, LOF, OC-SVM, Autoencoder reconstruction error, etc.); Brazil Amazon uses several ML detectors; China's hybrid EWS combines SEIR mechanistic models with ML anomaly detectors for multi-signal fusion.

**Why this matters for the Immune Platform plan's Pillar I:**

- **Single anomaly algorithms have well-known failure modes.** ARIMA struggles with non-stationary signals; Isolation Forest struggles with low-dimensional data; one-class deep learning (AMAnD's approach) struggles when baseline is too small. Ensembles average out these weaknesses.
- **Pillar I §4.1 anticipates multiple detection layers.** AMAnD is one layer; the recommendation here is that the orchestration over multiple detectors should be designed as an ensemble from day one, drawing on the patterns shipped in these three production-deployed disease-specific systems.

No new backlog items per se — this is design guidance, not code adoption.

---

### 2.h Biosecurity / sequence-of-concern screening

Two tools, but high-leverage. This is a category JACKPOT *uniquely* addresses among the platforms surveyed in `jackpot_platform_landscape.md` — Loculus, Pathoplexus, Pathogenwatch don't do sequence-of-concern (SoC) screening at ingest. Adopting SeqScreen + BLiSS would make JACKPOT the first pathogen-genomics platform with native biosecurity-screening at the ingest gate.

| Tool | Function | License | Maturity | JACKPOT-current | JACKPOT-immune |
|---|---|---|---|---|---|
| **SeqScreen** | Functional annotation for sequences of concern | OSS | Production | 🟢 ★ Adopt — `B-SOC-1` | 🔵 Pillar II §5.3.4 |
| **BLiSS** | Best-match SoC screening | OSS | Medium | 🟢 ★ Adopt — `B-SOC-1` | 🔵 Pillar II §5.3.4 |

#### 2.h.1 SeqScreen — functional annotation for sequences of concern 🟢 ★

SeqScreen (Balaji et al., *Genome Biology* 2022; project at github.com/seqscreen/seqscreen) is an open-source tool for functional annotation of nucleotide sequences with a specific focus on identifying sequences of biosecurity concern. Output: per-sequence labels indicating whether the sequence encodes functions associated with select-agent organisms, virulence factors, toxin genes, etc.

**Why this is a top-5 adoption candidate:**

- **Direct fit for `jackpot-immune-sec` §5.3.4 (synthetic DNA screening at ingest).** The Immune Platform plan §5.3.4 explicitly calls out a synthetic-DNA-screening module at ingest; SeqScreen is the canonical open-source implementation of exactly this.
- **First-of-class feature.** Among the 23 platforms in the landscape, none ship SoC screening at ingest. Adopting SeqScreen makes JACKPOT visibly differentiated on biosecurity.
- **WHO/IPSN attribute alignment.** Strengthens WHO/IPSN attribute 6 (Data Curation) — the gate now screens for biosecurity-relevant content beyond just PII.
- **AGPL-friendly.** SeqScreen ships under an open license compatible with JACKPOT's AGPL.

**Operational caveat.** SoC screening is a sensitive operational area — false positives would block legitimate research data, false negatives would let threat-relevant sequences through. The screening must run alongside (not gate) ingest in initial deployment — i.e., flag, audit, alert, *but don't block*. After tuning, escalate to optional blocking based on operator policy.

#### 2.h.2 BLiSS — best-match SoC screening 🟢 ★

BLiSS (briefly described in the source-doc literature, Hoffmann et al. 2023 review) is a complementary best-match-based SoC screening tool. It uses the IGSC (International Gene Synthesis Consortium) regulated-pathogen sequence list to flag matches.

**Why this is high-value alongside SeqScreen:**

- **Complementary approaches.** SeqScreen is functional-annotation-based; BLiSS is sequence-similarity-based. Each catches what the other misses. Running both gives much more confident calls.
- **Industry-standard reference.** The IGSC list is what commercial gene-synthesis vendors use for their own SoC screening; using BLiSS aligns JACKPOT with that operational baseline.

#### 2.h.3 Combined backlog

```text
[ ] B-SOC-1  Adopt SeqScreen + BLiSS as a combined sequence-of-concern
             screening layer at ingest. Initially run-and-flag (no
             blocking); annotate samples with SoC-screen-flag and
             append to audit log. Evaluate gating policy after 6
             months of false-positive/negative data. Maps to Immune
             Platform Pillar II §5.3.4 (synthetic DNA screening at
             ingest).
             Effort: 3-4 sessions for initial run-and-flag pipeline;
             6 months data collection; 1-2 sessions for gating policy.
             Phase: ingest-pipeline work + Pillar II implementation.
```

This is the **single highest-leverage backlog item in the entire detection landscape** for differentiating JACKPOT from the rest of the platform landscape on biosecurity dimensions.

---

### 2.i Federated learning frameworks for biosurveillance

Six tools surveyed. The strategically important fact about this category: source doc 4 (`What_role_does_federated_learning_play_in_biosurveillance_software.md`) concludes that *no biosurveillance-specific federated learning system exists in the published literature*. What does exist is a portfolio of FL frameworks (some general-purpose, some genomic, some anomaly-detection-specific) that the JACKPOT Immune Platform plan's Pillar III could compose.

The DataSHIELD/VANTAGE6/MOLGENIS-Armadillo trio is already covered in `jackpot_platform_landscape.md` §5.2 — those are general-purpose federated-analysis frameworks for clinical+omics data. The new entries here are *anomaly-detection-specific* and *time-series-specific* FL frameworks.

| Tool | Function | License | Maturity | JACKPOT-current | JACKPOT-immune |
|---|---|---|---|---|---|
| **DataSHIELD/VANTAGE6/Armadillo** | (covered in landscape doc §5.2) | OSS | Production | (landscape doc) | 🔵 Pillar III |
| **FedAdapt-CAD** | FL framework with client-aware aggregation for AD | OSS | Emerging (2026) | 🟡 Study | 🔵 Pillar III |
| **FedMI** | Vertical FL for distributed-edge anomaly detection | OSS | Emerging (2025) | 🟡 Study | 🔵 Pillar III |
| **FedTADBench** | Benchmark suite for federated time-series AD | OSS | Medium (2022) | 🟡 Reference | 🔵 Pillar III |
| **Blockchain+FL frameworks** (Wang 2026 SLR; Ouyang 2021 COVID) | Surveyed frameworks for medical/public-health FL | Various OSS | Emerging | ⚪ Defer | 🔵 Pillar III (audit-trail layer) |
| **VAE-based FL malicious-update detection** (Gu & Yang 2021) | Conditional VAE for detecting malicious FL model updates | OSS | Emerging | ⚪ Defer | 🔵 Pillar II + III intersection |

#### 2.i.1 The pattern: FL framework selection for Pillar III is a deferred decision 🔵

The Immune Platform plan's Pillar III (`jackpot-immune-net`, federation as an immune network) has not yet committed to a specific FL framework. The leading candidates are DataSHIELD-class (mature, clinical-data-focused) versus newer anomaly-detection-specific frameworks (FedAdapt-CAD, FedMI). The right decision depends on what Pillar III actually needs from FL:

- If the goal is **federated trend analysis** (e.g., "average AMR-prevalence trend across all federation members"), DataSHIELD-class is the right tool.
- If the goal is **federated anomaly detection on local genomic streams** (the Pillar I + Pillar III intersection), FedAdapt-CAD or FedMI are better matches because they're designed for distributed-edge anomaly detection specifically.
- If the goal is **adversarial-resistant federated training** (relevant when federation members might submit poisoned updates), the VAE-based defenses described in Gu & Yang 2021 are the relevant primitives.

**No backlog yet.** This is a study-and-defer category; the actual FL-framework-selection decision should be made when Pillar III implementation begins (Year 2+).

#### 2.i.2 FedTADBench — benchmark for federated time-series anomaly detection 🟡 / 🔵

FedTADBench (Liu et al., 2022) is a benchmark suite for federated time-series anomaly detection. Not a framework to deploy, but a benchmark to *use* for the FL-framework-selection decision in 2.i.1.

**Why it matters:** When the time comes to choose between DataSHIELD vs FedAdapt-CAD vs FedMI for Pillar III, FedTADBench provides apples-to-apples comparison data. Run candidate frameworks against FedTADBench's reference workloads; pick based on results.

```text
[ ] B-FED-PILLARIII-1  Decide FL framework for Pillar III. Use FedTADBench
                       to benchmark DataSHIELD-class vs FedAdapt-CAD vs
                       FedMI on representative anomaly-detection workloads.
                       Pick based on benchmark + mature-tooling tradeoff.
                       Effort: 2 weeks benchmarking + 1 week documentation.
                       Phase: Pillar III implementation start (Year 2+).
```

---

### 2.j Privacy-preserving genomic computation

Four tools — all addressing a single problem: how to perform computation on genomic data without exposing the raw data. Four distinct architectures: federated learning (already covered in 2.i), homomorphic encryption, trusted execution environments (TEEs), and secure multi-party computation.

| Tool | Function | License | Maturity | JACKPOT-current | JACKPOT-immune |
|---|---|---|---|---|---|
| **COLLAGENE** | Privacy-aware federated genomic analysis | OSS | Production | 🟡 Study — pairs with `B-DSH-1` | 🔵 Pillar III |
| **Multi-key Homomorphic Encryption framework** (Namazi 2025) | MK-HE for genomic computation | OSS | Emerging | 🟡 Reference | 🔵 Pillar III |
| **TEE-based genomic analysis framework** (Asvadishirehjini 2020) | Trusted execution environments for genomic data | OSS | Emerging | ⚪ Defer | 🔵 Pillar III |
| **CDST** | (covered in landscape doc §5.5.1) | OSS | Production | (landscape doc — `B-CDST-1/2/3`) | 🔵 Pillar III |

#### 2.j.1 COLLAGENE — privacy-aware federated genomic analysis 🟡 / 🔵

COLLAGENE (Li et al., *Genome Biology* 2023) enables privacy-aware federated and collaborative genomic data analysis. Architecture: encrypted data flows + federated computation; specific support for population-genomics workloads (GWAS, association tests).

**Why it's a Pillar III component:**

- **Population-genomics-specific.** Most generic FL frameworks work on tabular health data; COLLAGENE is genomics-native and handles the specific cryptographic primitives needed for variant-data computation.
- **Pairs naturally with DataSHIELD adoption (`B-DSH-1` in the landscape doc).** DataSHIELD handles the federated-analysis architecture; COLLAGENE handles the cryptographic primitives for sensitive variant queries.

**No new backlog item.** The COLLAGENE study is folded into `B-FED-PILLARIII-1` (the FL framework decision in §2.i.1) and `B-DSH-1` (DataSHIELD adoption study from the landscape doc).

#### 2.j.2 The privacy primitives that aren't here 🔵

What's surveyed here is a small fraction of the privacy-preserving-computation toolkit relevant to JACKPOT's federation. Notable absences:

- **Differential privacy primitives** for shared signals (referenced in the Immune Platform plan §6.2.3 but not surveyed in any source doc).
- **Trusted Execution Environment primitives** beyond Asvadishirehjini's framework (Intel SGX, AMD SEV-SNP, AWS Nitro Enclaves all relevant).
- **Secure Multi-Party Computation libraries** beyond what COLLAGENE wraps.

These primitives become relevant when Pillar III implementation begins. For now, the strategic recommendation is: stay aware of the CDST adoption (`B-CDST-1/2/3` in the landscape doc) as the highest-priority privacy-preserving primitive; defer the rest.

---

### 2.k Artificial Immune System tools

This is the category that is the most strategically important *and* the smallest by tool count. Source doc 9's central finding bears repeating: **"There are currently no well-established, dedicated open source tools that specifically use artificial immune system (AIS) algorithms for the detection of novel, emerging, and unknown biological pathogens."** The four tools listed below are AIS implementations, but none of them target genomic pathogen detection — they target cybersecurity, IoT-malware detection, or POCT analysis.

The *strategic* implication is `jackpot_immune_platform_plan.md` itself. The negative finding from source doc 9 is the strategic opening: JACKPOT Immune Platform is positioned to be the dedicated open-source AIS pathogen-detection platform that doesn't yet exist.

| Tool | Function | License | Maturity | JACKPOT-current | JACKPOT-immune |
|---|---|---|---|---|---|
| **libtissue** | Distributed adaptive AIS for security/anomaly detection | OSS | Mature (security-domain) | ⚪ Not genomic | 🔵 Pillar II/III (substrate ref) |
| **NK-DCHS** | Hybrid Natural-Killer + Dendritic-Cell immune model for imbalanced AD | OSS | Emerging (2025) | ⚪ Not genomic | 🔵 Pillar II (algorithmic ref) |
| **ISIMD-ALNs** | Immune-inspired malware detection for edge-IoT | OSS | Emerging (2025) | ⚪ Not genomic | 🔵 Pillar II (algorithmic ref) |
| **pyPOCQuant** | POCT quantitative analysis (German group) | OSS | Production (POCT) | ⚪ Not genomic-discovery | 🔵 Pillar IV (training/POCT linkage) |

#### 2.k.1 libtissue — distributed AIS substrate 🔵

libtissue (Twycross & Aickelin, 2006) is the longest-running open-source AIS implementation. Originally built for cybersecurity intrusion detection; the architecture (distributed agent-based, Danger-Theory-inspired Dendritic Cell Algorithm primitives) has held up well.

**Why this matters for the Immune Platform plan:**

- **Substrate reference.** When the Immune Platform plan's Pillar II implementation begins (`jackpot-immune-sec`), libtissue's design is the canonical reference — agent-based, distributed, anomaly-driven, with explicit innate/adaptive separation.
- **Don't adopt directly — port the design pattern.** libtissue is implemented in C and was last updated long ago. The intellectual content (the architecture pattern) is what's valuable; reimplementation in Python on JACKPOT's substrate is the right approach.

#### 2.k.2 NK-DCHS — hybrid NK-cell + dendritic-cell anomaly detection 🔵

NK-DCHS (Deng et al., *Expert Systems with Applications* 2025) is a hybrid Natural-Killer-cell + Dendritic-Cell-System anomaly detection algorithm. The hybrid is interesting: it combines fast pattern-matching (NK-cell-like; reactive to known threats) with slower context-aware classification (DC-like; integrates multi-modal danger signals).

**Why this is a Pillar II algorithmic reference:**

- **Imbalanced-data performance.** NK-DCHS is benchmarked on imbalanced data — exactly the regime relevant for pathogen detection (one anomalous sample in thousands of normal ones).
- **Multi-modal danger signals.** Pillar I §4.3 explicitly anticipates multi-modal danger signals (genomic + temporal + environmental + epidemiological context). NK-DCHS is the closest published algorithm to that pattern.

#### 2.k.3 ISIMD-ALNs — immune-inspired malware detection 🔵

ISIMD-ALNs (Adhikari et al., 2025) is an immune-inspired malware detection system for edge-IoT cybersecurity. Specifically: it implements a Negative Selection Algorithm with Bloom-filter-augmented detector banks for low-resource (edge-device) malware detection.

**Why this is a Pillar II algorithmic reference:**

- **NSA + Bloom filters is a known-good pattern for low-resource detection.** Pillar II's adversarial-input detection should run efficiently on JACKPOT API pods (no GPU); this design pattern is the right starting point.
- **Cyberbiosecurity translation is real.** Many of the same primitives (negative selection, danger signals, immune memory) translate cleanly from cyber-malware to bio-anomaly detection. The Immune Platform plan §3 is built on exactly this premise.

#### 2.k.4 pyPOCQuant — POCT quantitative analysis 🔵

pyPOCQuant (Cattin Saporito et al., German group at TU Berlin) is a Python tool for quantitative analysis of point-of-care tests (POCT) — image-based readout of lateral-flow assays (LFAs) for SARS-CoV-2 and other pathogens.

**Why this fits Pillar IV (training/curriculum):**

- **Connects benchwork to bioinformatics.** Pillar IV (JACKPOT Academy) explicitly anticipates curriculum that bridges genomic surveillance and field/clinical lab work. pyPOCQuant is the reference for the "quantitative POCT analysis" module.
- **Open-source education resource.** pyPOCQuant ships with educational materials suitable for Academy curriculum integration.

#### 2.k.5 Strategic implication 🔵

The four AIS tools above are *components and references for the JACKPOT Immune Platform plan, not gap-fillers in current JACKPOT*. The strategic implication of source doc 9's negative finding is:

```text
[STRATEGIC]  The absence of a dedicated open-source AIS platform for
             novel-pathogen detection is the strategic opening for
             JACKPOT Immune Platform. The four AIS tools surveyed here
             are inputs (algorithmic references, design patterns) rather
             than gap-fillers. The Immune Platform plan's Pillars I-V
             are the concrete realization of "what an AIS-grounded
             pathogen-genomics platform looks like."
             Action: continue Immune Platform plan implementation
             (Year 2+ via Phase 26+ items).
```

No new backlog items in this category beyond the AIS-design references already absorbed into the Immune Platform plan itself.

---

### 2.l Environmental biosurveillance

Five tools spanning environmental DNA, environmental metagenomics, and IoT-environmental-sensor monitoring. Most are out-of-scope for current JACKPOT but become relevant when the Immune Platform plan's Pillar I extends to multi-modal environmental signals.

| Tool | Function | License | Maturity | JACKPOT-current | JACKPOT-immune |
|---|---|---|---|---|---|
| **CRISPR-eBx** | CRISPR-Dx for environmental DNA biosurveillance | OSS | Emerging | ⚪ Out of scope (now) | 🔵 Pillar I (env layer) |
| **CAMERA** | Environmental metagenomics cyberinfrastructure | OSS | Production | 🟡 Pattern ref | ⚪ |
| **KBase** | Open platform for microbial/metagenomic analysis (DOE) | OSS | Production | 🟡 Reference | ⚪ |
| **In-situ Turbidity Sensor AD Toolkit** | Sensor-data anomaly detection toolkit | OSS | Medium | ⚪ Out of scope | ⚪ |
| **HydroSignal** | IoT environmental hydrology platform | OSS | Emerging | ⚪ Out of scope | ⚪ |
| **LandScient_EWS** | Open-source rainfall threshold landslide EWS | OSS | Medium | ⚪ Out of scope | ⚪ |

#### 2.l.1 CRISPR-eBx — CRISPR-based environmental biosurveillance 🔵

CRISPR-eBx (Durán-Vinet et al., *Trends in Biotechnology* 2025) is a CRISPR-Dx-based environmental biosurveillance tool. Architecture: amplification-free CRISPR-Cas detection of environmental nucleic acids (eDNA/eRNA) for rapid pathogen surveillance in air, land, and water samples.

**Why this is a Pillar I extension candidate:**

- **eDNA/eRNA is a real signal modality** — wastewater surveillance, air sampling for respiratory pathogens, soil/water environmental monitoring. JACKPOT's One Health sectors (wastewater, water, air, soil, surface) are exactly the right substrate.
- **Year 2+ priority.** CRISPR-eBx is recent (2025), and the integration shape (point-of-detection + JACKPOT ingest) is non-trivial.

```text
[ ] B-CRISPR-EBX-1  Study CRISPR-eBx (Durán-Vinet et al., 2025) as the
                    canonical CRISPR-Dx environmental biosurveillance
                    integration pattern for Pillar I extension to eDNA.
                    Effort: 1-2 weeks study. Phase: Pillar I extension
                    (Year 2+).
```

---

### 2.m Real-time field/clinical metagenomics

Three tools, all about *real-time* analysis as the sequencer is running — not post-hoc batch analysis. The differentiator: outbreak response and field deployment care about results in hours, not days.

| Tool | Function | License | Maturity | JACKPOT-current | JACKPOT-immune |
|---|---|---|---|---|---|
| **MARTi** | Real-time nanopore metagenomic analysis (cross-listed) | OSS | Production | (see 2.a.6) | (see 2.a.6) |
| **NanoCore** | Core-genome bacterial surveillance Nanopore+Illumina (cross-listed) | OSS | Production | (see 2.e.1) | (see 2.e.1) |
| **PathoLive** | Real-time pathogen ID during Illumina sequencing (cross-listed) | OSS | Medium | (see 2.b table) | (see 2.b table) |

This category has no unique tools; it's a re-framing of MARTi (§2.a.6 / §2.c), NanoCore (§2.e.1), and PathoLive (§2.b table) as a temporal cluster. The three together form a comprehensive "while-the-run-is-running" analysis stack:

- **MARTi** for nanopore real-time metagenomic surveillance (broadest function);
- **NanoCore** for nanopore real-time outbreak typing (when the target is bacterial);
- **PathoLive** for Illumina real-time pathogen ID (when the platform is short-read).

The combined backlog `B-REALTIME-1` for the real-time integration story:

```text
[ ] B-REALTIME-1  Document and implement the JACKPOT real-time-analysis
                  story: MARTi (B-MARTI-1) for nanopore metagenomics,
                  NanoCore (B-NANOC-1) for nanopore outbreak typing,
                  PathoLive (study) for Illumina real-time pathogen ID.
                  Wire to WebSocket-driven UI updates so operators see
                  results as the sequencer runs.
                  Effort: 3-4 sessions for the umbrella integration
                  beyond the per-tool adoptions. Phase: post B-MARTI-1,
                  B-NANOC-1.
```

---

### 2.n Reporting / preprocessing utilities

Six tools that aren't core detection tools but are useful adjacent utilities — clinical-text NLP, epidemiological reporting, phylogenetic visualization, primer design, metagenomic data management, generic anomaly+novelty detection libraries.

| Tool | Function | License | Maturity | JACKPOT-current | JACKPOT-immune |
|---|---|---|---|---|---|
| **MicrobEx** | NLP for microbiology culture concept extraction | OSS | Production | 🟡 Reference (clinical-text path) | ⚪ |
| **sivirep** | Epidemiological surveillance reporting (R, Epiverse) | OSS | Medium | 🟡 Pattern ref for reporting | ⚪ |
| **MetaXplor** | Interactive viral/microbial metagenomic data manager | OSS | Production | 🟡 Pattern ref | ⚪ |
| **Krisp** | CRISPR/primer diagnostic design from WGS | OSS | Medium | 🟡 Pattern ref | ⚪ |
| **TinselR** | R Shiny phylogenetic tree annotation | OSS | Emerging | 🟡 Pattern ref | ⚪ |
| **NDNET** | Anomaly+novelty detection unified framework | OSS | Emerging | ⚪ Defer | 🟡 Pillar I primitive |
| **AnFiSA** | Open-source variant analysis platform | OSS | Production | 🟡 Reference | ⚪ |

#### 2.n.1 MicrobEx — clinical microbiology NLP 🟡

MicrobEx (Eickelberg et al., *JAMIA Open* 2022) is an open-source package for extracting microbiology culture concepts (organism identification, susceptibility) from clinical text. Architecture: rule-based + ontology-anchored NLP, validated against EHR microbiology notes.

**Why this is a Pattern Reference (not direct adoption):**

- **JACKPOT's `HumanSample` schema doesn't ingest free-text microbiology notes today.** Clinical-text NLP would be a meaningful schema extension if/when JACKPOT operators want to ingest the EHR-side of clinical microbiology data alongside sequencing data.
- **MicrobEx is the clear reference if that extension happens.** Mature, validated, ontology-anchored — exactly what JACKPOT would want.

#### 2.n.2 sivirep — Epiverse surveillance reporting 🟡

sivirep (Gómez-Millán et al., *SoftwareX* 2025) is the Epiverse epidemiological surveillance reporting toolkit. Auto-generates surveillance reports from line-list data; supports indicator computation, anomaly flagging, and standardized output formats.

**Why this is a Pattern Reference:**

- **JACKPOT's reporting story is currently Streamlit-driven and ad-hoc.** sivirep represents what a *standardized* reporting toolkit looks like — useful prior art for the dataset-export and report-generation features.
- **R-language; doesn't fit JACKPOT's Python core.** Direct adoption is unlikely; the reporting *patterns* (which indicators to compute, which output formats to support) are what's valuable.

#### 2.n.3 MetaXplor — interactive metagenomic data manager 🟡

MetaXplor (Sempéré et al., *GigaScience* 2021) is an interactive web tool for exploring viral/microbial metagenomic data — taxonomic profiling, environmental annotations, comparative views.

**Why this is a Pattern Reference:**

- The Streamlit dashboards JACKPOT has now cover similar ground; MetaXplor is more polished but stylistically different.
- Useful prior art for the React migration (Year 2 Streamlit → React frontend transition).

---

## 3. JACKPOT integration analysis — current platform (no Immune extension)

This section evaluates the surveyed tools strictly against current JACKPOT — i.e., the platform on the P0–P5 roadmap as documented in `spec.md` and `jackpot_session_summary_and_backlog.md`, with no Immune Platform extension. Section 4 covers the Immune-extended view.

### 3.1 Already-shipped equivalents (no adoption needed)

JACKPOT's pipeline zoo already covers significant overlap with several surveyed tools. These do *not* need adoption; the existing JACKPOT pipeline serves the function.

| Surveyed tool | Function | Already covered by | Notes |
|---|---|---|---|
| **Pangolin** | SARS-CoV-2 lineage assignment | viralrecon, Cecret in zoo | Pangolin runs as a step in viralrecon |
| **Nextstrain** | Pathogen evolution tracking | nf-core/pathogensurveillance | Nextstrain components run inside the larger pipeline |
| **Manta, DELLY, LUMPY, CNVnator, CNVkit, Sniffles2, cuteSV** | Standard SV/CNV callers | bactopia, mycosnp, etc. | These ship as steps inside larger pipelines; no separate adoption needed |
| **MOLGENIS, DataSHIELD, VANTAGE6** | Federated analysis frameworks | Covered in `jackpot_platform_landscape.md` §5.2 | Don't re-evaluate here |
| **Solu** | Real-time cloud bacterial surveillance | Covered in landscape doc Section 5 | JACKPOT *competes* with Solu, doesn't adopt from it |

### 3.2 Genuine gap-fillers — the 10 highest-value adoptions

These 10 tools fill specific gaps in the current JACKPOT pipeline zoo or schema. All are scoped as Nextflow pipeline-zoo additions (drop-in pattern; 1-3 sessions each). Listed in priority order:

1. **TaxTriage** — `B-TAXTRIAGE-1` — untargeted novel-pathogen detection (the headline gap)
2. **AMAnD** — `B-AMAND-1` — metagenome anomaly detection (no current equivalent)
3. **SeqScreen + BLiSS** — `B-SOC-1` — sequence-of-concern screening (first-of-class for the platform landscape)
4. **MARTi** — `B-MARTI-1` — real-time nanopore metagenomic analysis (field deployment differentiator)
5. **NanoCore** — `B-NANOC-1` — sequencer-agnostic core-genome outbreak tracking
6. **DeePaC** — `B-DEEPAC-1` — pathogenicity prediction from raw DNA
7. **MLM** — `B-MLM-1` — ML threat characterization for unmapped reads
8. **nf-UnO** — `B-NFUNO-1` — cohort co-assembly novel-pathogen pipeline
9. **INSaFLU-TELEVIR** — `B-INSAFLU-1` — viral mNGS + genomic surveillance suite (AGPL-friendly)
10. **AMRomics** — `B-AMRO-1` — population-scale AMR surveillance

These 10 are also the basis of **Tier 1** in the §5 priority queue.

### 3.3 Bacterial-specific variant-calling adoptions

A separate cluster — bacterial-aware variant callers (CNproScan, ProcaryaSV, SNiPgenie, SKA2). Adopting these alongside the existing bactopia/mycosnp/tb-profiler entries gives JACKPOT a stronger story for "rapid bacterial outbreak triage" — a workflow heavy state DOH operators actually use.

| Backlog | Tool | Function | Effort | Phase |
|---|---|---|---|---|
| `B-CNPRO-1` | CNproScan | Bacterial CNV (GC-aware, circular-genome-aware) | 1-2 sessions | Pipeline-zoo work |
| `B-PROSV-1` | ProcaryaSV | Bacterial SV (short-read) | 1-2 sessions | Pipeline-zoo work |
| `B-SNIPG-1` | SNiPgenie | Microbial WGS SNP detection | 1 session | Pipeline-zoo work |
| `B-SKA2-1` | SKA2 | Split-k-mer rapid bacterial genotyping | 1 session | Pipeline-zoo work |

### 3.4 Specialty surveillance pipelines

Three more adoptions that don't fit neatly into the §3.2 ten but are still real gap-fillers:

| Backlog | Tool | Function | Effort | Phase |
|---|---|---|---|---|
| `B-CGMSI-1` | cgMSI | Strain-level nanopore detection at low coverage | 1-2 sessions | Pipeline-zoo |
| `B-PFHAP-1` | Pf-HaploAtlas | Malaria genomic surveillance | 2-3 sessions | Pipeline-zoo |
| `B-PYMLST-1` | pyMLST | cgMLST custom-scheme support | 1-2 sessions | Pipeline-zoo |
| `B-RECOMB-1` | OpenRecombinHunt | Viral recombination detection | 2 sessions | Pipeline-zoo |

### 3.5 What's *not* worth adopting for current JACKPOT

These tools were surfaced in the source-doc literature but don't fit current JACKPOT. Inclusion here is to document the negative decision so future contributors don't re-evaluate them:

- **PlasticEnz, CINNAMON-GUI, FastPathology** — Out of scope (plastic enzymes, pap smears, digital pathology).
- **Clinical-microbiology NLP toolchain (MicrobEx)** — Schema-extension dependency; JACKPOT doesn't ingest free-text clinical notes today. If/when that schema extension happens, MicrobEx becomes the reference.
- **Disease-specific outbreak anomaly detection systems (Thailand malaria, Brazil Amazon, China hybrid)** — Useful as ensemble-pattern references for the Immune Platform, but not direct adoptions; each is purpose-built for its domain.
- **Environmental-sensor anomaly detection (In-situ Turbidity, HydroSignal, LandScient_EWS)** — Out of pathogen-genomics scope.
- **GATK-gCNV** — Exome-targeted; JACKPOT doesn't deal with exome sequencing.

### 3.6 Summary of current-JACKPOT adoptions

Adding up the adoptions across §3.2–§3.4:

| Category | Adoptions | Total session effort estimate |
|---|---|---|
| §3.2 Top 10 gap-fillers | 10 | ~24-30 sessions |
| §3.3 Bacterial variant callers | 4 | ~5-7 sessions |
| §3.4 Specialty pipelines | 4 | ~7-10 sessions |
| **Total** | **18 backlog items** | **~36-47 sessions** |

This is roughly 6-9 months of pipeline-zoo work distributed across the post-staging-cutover phase (i.e., spread over 2026 H2 and 2027). It is *substantial* but tractable. The §5 priority queue groups these by Tier so they can be sequenced sensibly.

---

## 4. JACKPOT integration analysis — Immune-Platform-extended

This section evaluates the same surveyed tools against `jackpot_immune_platform_plan.md` — i.e., a JACKPOT extended with the five-pillar Immune Platform architecture. The mapping is by Pillar.

### 4.1 Pillar I — Bio-Anomaly Detection Stack (`jackpot-immune-bio`)

**Pillar I goal (per §4 of the immune plan):** A multi-layer bio-anomaly detection stack that flags samples deviating from a curated baseline of "normal." Layers: per-sample anomaly, community-shift, taxa-flagging, multi-modal danger signals, drift-aware retraining.

**Tool selections per layer:**

| Layer | Tool selection | Backlog | Rationale |
|---|---|---|---|
| **Per-sample metagenome anomaly** | AMAnD | `B-AMAND-1` | DeepSVDD one-class; production-deployed at APL |
| **Community-shift anomaly** | KOMB / KombOver | `B-KOMB-1` | k-core graph-based; complementary to per-sample |
| **Taxa-level anomaly flagging** | PhyloMagnet | (study) | Gene-centric phylogenetic; flags unexpected taxa |
| **Untargeted novel-pathogen detection** | TaxTriage | `B-TAXTRIAGE-1` | Drop-in Nextflow; pairs with DeePaC + MLM downstream |
| **Pathogenicity scoring** | DeePaC | `B-DEEPAC-1` | CNN/LSTM raw-DNA pathogenicity prediction |
| **Threat characterization for unmapped reads** | MLM | `B-MLM-1` | RF + Bayesian; complements DeePaC |
| **Risk scoring for environmental MAGs** | GRUMB | `B-GRUMB-1` | Genome-resolved metagenomics + ML risk score |
| **Multi-modal external signal feed** | EIOS, EPIWATCH, ProMED | `B-EIOS-1` | Open-source intelligence as Pillar I context |
| **Real-time field detection** | MARTi + cgMSI | `B-MARTI-1`, `B-CGMSI-1` | Nanopore real-time + strain-level |
| **Viral recombinant detection** | OpenRecombinHunt | `B-RECOMB-1` | Periodic-scan recombinant detection |
| **Ensemble orchestration design** | Thailand/Brazil/China EWS patterns | (design ref) | Multi-algorithm ensembles for outbreak detection |

The cross-cutting recommendation: **AMAnD is the headline tool of Pillar I**. The other tools are layers around AMAnD's core anomaly-detection function. This simplifies the architectural conversation — start with AMAnD, then add layers.

### 4.2 Pillar II — Platform Self-Defense AIS (`jackpot-immune-sec`)

**Pillar II goal (per §5 of the immune plan):** AIS-grounded platform self-defense — adversarial-input detection, query OPSEC monitoring, insider-threat detection, synthetic DNA screening at ingest.

**Tool selections per defense:**

| Defense | Tool selection | Backlog | Rationale |
|---|---|---|---|
| **Synthetic DNA screening at ingest** | SeqScreen + BLiSS | `B-SOC-1` | Combined functional-annotation + best-match screening |
| **Adversarial input detection** | NK-DCHS algorithmic pattern | (Pillar II §5.3.1) | Hybrid NK + DC immune model |
| **Query OPSEC monitoring** | libtissue substrate ref | (Pillar II §5.3.2) | Distributed agent-based design |
| **Insider threat detection** | Hybrid AIS-DL pattern | (Pillar II §5.3.3) | Negative-selection-with-ML for low FPR |
| **Malicious FL update detection** | VAE-based detector (Gu & Yang 2021) | (Pillar II/III) | Conditional VAE for federated context |
| **Edge-resource constrained anomaly detection** | ISIMD-ALNs algorithmic pattern | (Pillar II §5.3.x) | NSA + Bloom filters for low-resource detection |

The cross-cutting recommendation: **SeqScreen + BLiSS is the highest-leverage *concrete* Pillar II item** because it's the only one in this column that's a directly-adopted external tool; the rest are algorithmic-pattern references that need implementation.

### 4.3 Pillar III — Federation as Immune Network (`jackpot-immune-net`)

**Pillar III goal (per §6 of the immune plan):** Federated computation across JACKPOT instances acting as an immune-network of distributed sensors.

**Tool selections per primitive:**

| Primitive | Tool selection | Backlog | Rationale |
|---|---|---|---|
| **General federated analysis framework** | DataSHIELD or FedAdapt-CAD or FedMI (TBD) | `B-FED-PILLARIII-1` | Decision tied to FedTADBench benchmarking |
| **Privacy-preserving genomic computation** | COLLAGENE | (study) | Genomics-native; pairs with B-DSH-1 |
| **Privacy-preserving primer for typing** | CDST | `B-CDST-1/2/3` (landscape doc) | Highest-priority privacy primitive |
| **Cryptographic primitives for sensitive queries** | MK-Homomorphic-Encryption (Namazi 2025) | (Pillar III) | When MK-HE matures |
| **Audit-trail for federated ops** | Blockchain+FL frameworks (Wang 2026 SLR) | (Pillar III) | Optional audit-trail layer |

The cross-cutting recommendation: **CDST is the fastest path to a real Pillar III primitive**, because it's the most mature privacy-preserving genomic-typing tool and fits cleanly with the existing JACKPOT federation architecture.

### 4.4 Pillar IV — Training (JACKPOT Academy)

**Pillar IV goal (per §7 of the immune plan):** A workforce-development curriculum aligned with the platform — operators don't just deploy JACKPOT, they learn the AIS framework that grounds it.

**Tool selections per curriculum module:**

| Module | Tool reference | Backlog | Rationale |
|---|---|---|---|
| **POCT linkage to bioinformatics** | pyPOCQuant | (Academy curriculum) | Quantitative POCT analysis as bridge module |
| **Anomaly-detection module** | AMAnD documentation | (curriculum) | Operators learn to curate baselines |
| **Federation primer** | DataSHIELD/COLLAGENE walkthroughs | (curriculum) | Foundations of federated genomics |

Backlog items here are curriculum-development tasks, not tool-adoption tasks. Folded into the Pillar IV implementation plan.

### 4.5 Pillar V — Gaming (Outbreak + WILDFIRE)

**Pillar V goal (per §8 of the immune plan):** Gamified outbreak-response training — Outbreak: Field Edition (single-player narrative puzzle); WILDFIRE (multi-player coordination simulation).

No surveyed tools map to Pillar V. Game development is its own thing.

### 4.6 Cross-pillar summary

| Pillar | Headline tool(s) | Total adoptions |
|---|---|---|
| I — Bio-Anomaly | AMAnD, TaxTriage, MARTi, DeePaC, MLM | 7 direct adoptions |
| II — Self-Defense | SeqScreen + BLiSS | 1 direct adoption + 4 algorithmic refs |
| III — Federation | CDST + (TBD FL framework) | 2 direct adoptions + 3 study items |
| IV — Training | pyPOCQuant + curriculum work | 0 tool adoptions; curriculum-led |
| V — Gaming | (none) | 0 |

**Strategic finding:** The Immune Platform plan has *concrete, named, ready-to-adopt tools* for Pillars I–III. The plan's strategic confidence is well-founded — the open-source landscape supplies the components.

---

## 5. Top adoption candidates priority queue

Tier-grouped recommendations for sequencing the adoptions across calendar time. Glen and contributors should treat Tier 0 as immediate, Tier 1 as imminent (next 2 quarters), Tier 2 as substantial (12-18 months), Tier 3 as long-term/conditional.

### 5.1 Tier 0 — Cheap immediate wins (adopt this quarter)

Single-session or two-session work that closes high-leverage gaps. Total: ~5-8 sessions.

| Order | Backlog | Tool | Effort | Why now |
|---|---|---|---|---|
| 1 | `B-SKA2-1` | SKA2 | 1 session | Speed differentiator for outbreak triage |
| 2 | `B-SNIPG-1` | SNiPgenie | 1 session | Lightweight alternative to bactopia |
| 3 | `B-PYMLST-1` | pyMLST | 1-2 sessions | Custom-cgMLST-scheme support |
| 4 | `B-CGMSI-1` | cgMSI | 1-2 sessions | Pairs with MARTi for nanopore strain typing |
| 5 | `B-EIOS-1` | EIOS integration docs | 1 session | Documentation only; no code change |

### 5.2 Tier 1 — Strategic adoptions (next 2 quarters; the headline 5+5)

The 5 headline recommendations from §0.3 plus 5 more that are equally important but not headline-grade. Total: ~25-35 sessions, distributed.

**The headline 5 (the high-visibility wins):**

| Order | Backlog | Tool | Effort | Headline rationale |
|---|---|---|---|---|
| 1 | `B-TAXTRIAGE-1` | TaxTriage | 2-3 sessions | Untargeted novel-pathogen detection — biggest gap |
| 2 | `B-AMAND-1` | AMAnD | 3 sessions + ongoing | Anomaly-detection layer for Pillar I core |
| 3 | `B-SOC-1` | SeqScreen + BLiSS | 3-4 sessions | Sequence-of-concern screening — first-of-class |
| 4 | `B-INSAFLU-1` | INSaFLU-TELEVIR | 1 session study + 2 sessions adoption | Viral mNGS suite; AGPL-aligned |
| 5 | `B-MARTI-1` | MARTi | 2-3 sessions | Real-time nanopore differentiator |

**The unhighlighted 5 (equal-priority but less headline-grade):**

| Order | Backlog | Tool | Effort | Rationale |
|---|---|---|---|---|
| 6 | `B-NANOC-1` | NanoCore | 2 sessions | Sequencer-agnostic outbreak tracking |
| 7 | `B-DEEPAC-1` | DeePaC | 1-2 sessions | Pathogenicity scoring from raw DNA |
| 8 | `B-MLM-1` | MLM | 2 sessions | Unmapped-read threat characterization |
| 9 | `B-NFUNO-1` | nf-UnO | 2 sessions | Cohort co-assembly novel-pathogen detection |
| 10 | `B-AMRO-1` | AMRomics | 2-3 sessions | Population-scale AMR surveillance |

### 5.3 Tier 2 — Substantial adoptions (12-18 months)

Tools that require a pillar implementation, schema extension, or non-trivial architectural decision. Total: variable.

| Backlog | Tool | Effort | Conditional on |
|---|---|---|---|
| `B-CDST-1/2/3` (landscape doc) | CDST | Multi-week | Privacy-preserving primitive for Pillar III |
| `B-CNPRO-1` + `B-PROSV-1` | CNproScan + ProcaryaSV | 3-4 sessions | Bacterial CNV/SV surveillance |
| `B-PFHAP-1` | Pf-HaploAtlas | 2-3 sessions | Malaria-region operator deployments |
| `B-RECOMB-1` | OpenRecombinHunt | 2 sessions | Periodic-scan workflow |
| `B-KOMB-1` | KOMB/KombOver | 1-2 weeks study + adoption | Pillar I community-shift layer |
| `B-FED-PILLARIII-1` | FL framework decision | 3-4 weeks | Pillar III implementation start |
| `B-REALTIME-1` | Real-time UI integration | 3-4 sessions | Post B-MARTI-1, B-NANOC-1 |

### 5.4 Tier 3 — Long-term / conditional

These adopt-or-not decisions become real only after specific platform extensions or specific operator demand surfaces.

| Backlog | Tool | Conditional on |
|---|---|---|
| `B-GRUMB-1` | GRUMB | Pillar I environmental layer implementation |
| `B-CRISPR-EBX-1` | CRISPR-eBx | Pillar I environmental signal extension |
| (clinical NLP path) | MicrobEx | EHR-clinical-text schema extension |

---

## 6. Consolidated B-XXX backlog

Copy-paste-ready for direct integration into `todo.md`. All items derived from this analysis (i.e., items that did *not* already exist in `todo.md` or in the predecessor `jackpot_pathoplexus_loculus_overview.md`).

```text
[ ] B-TAXTRIAGE-1  Adopt nf-core/taxtriage (Merritt et al., Bioinformatics 2026)
                   into JACKPOT pipeline zoo as the canonical untargeted
                   pathogen-discovery workflow. Pipeline-zoo spec file +
                   integration with pipeline_results loader for the
                   pathogen-candidate output schema.
                   Effort: 2-3 sessions. Phase: pipeline-zoo work.

[ ] B-AMAND-1  Adopt AMAnD (Price & Russell, 2023) as the canonical
               metagenome anomaly detector in JACKPOT. Initially as a
               pipeline-zoo entry; once Pillar I lands, as the core of
               jackpot-immune-bio. Document the baseline-curation workflow
               (what is "normal" for this operator's deployment context)
               in the Pillar IV training materials.
               Effort: 3 sessions pipeline-zoo + 2 weeks for the baseline-
               curation tooling. Phase: pipeline-zoo work + Pillar I.

[ ] B-SOC-1  Adopt SeqScreen + BLiSS as a combined sequence-of-concern
             screening layer at ingest. Initially run-and-flag (no
             blocking); annotate samples with SoC-screen-flag and
             append to audit log. Evaluate gating policy after 6
             months of false-positive/negative data. Maps to Immune
             Platform Pillar II §5.3.4 (synthetic DNA screening at
             ingest).
             Effort: 3-4 sessions for initial run-and-flag pipeline;
             6 months data collection; 1-2 sessions for gating policy.
             Phase: ingest-pipeline work + Pillar II implementation.

[ ] B-MARTI-1  Add MARTi (Peel et al., Genome Research 2025) to pipeline
               zoo with real-time WebSocket updates to the JACKPOT UI.
               This is the "watch the run as it sequences" workflow,
               a demonstrably differentiator vs platforms that only
               accept post-run input.
               Effort: 2-3 sessions (real-time UI integration is the
               nontrivial part). Phase: post-staging-cutover.

[ ] B-INSAFLU-1  Evaluate INSaFLU-TELEVIR for adoption: viral mNGS pipeline
                 (TELEVIR module) into JACKPOT pipeline zoo; INSaFLU REST
                 API patterns as prior art for the LAPIS-compat work
                 (B-LAPIS-1). Decide whether to adopt the TELEVIR pipeline
                 directly or fork+adapt.
                 Effort: 1 session study + 2 sessions adoption.
                 Phase: Year 2.

[ ] B-CGMSI-1  Add cgMSI (Zhu et al., 2023) to pipeline zoo as the
               nanopore strain-level detection tool. Pairs with MARTi
               (B-MARTI-1) which provides the real-time analysis layer.
               Effort: 1-2 sessions. Phase: pipeline-zoo work.

[ ] B-NFUNO-1  Adopt nf-UnO (Guzman-Cole & Huang, Bioinformatics 2025) into
               JACKPOT pipeline zoo as the cohort co-assembly pipeline for
               outbreak novel-pathogen investigations. Wire to the dataset/
               cohort selection UI; outputs feed pipeline_results.
               Effort: 2 sessions. Phase: pipeline-zoo work, after B-TAXTRIAGE-1.

[ ] B-DEEPAC-1  Add DeePaC pathogenicity scoring as a post-classification
                step in the TaxTriage pipeline-zoo entry. Output a
                per-sequence pathogenicity score field on
                pipeline_results JSONB.
                Effort: 1-2 sessions, after B-TAXTRIAGE-1.
                Phase: pipeline-zoo work.

[ ] B-MLM-1  Adopt MLM (Baugher et al., 2025) into pipeline zoo as the
             unmapped-read threat-characterization stage. Wire into the
             TaxTriage pipeline output (post-DeePaC) for tiered
             threat-class assignment.
             Effort: 2 sessions. Phase: pipeline-zoo work, after
             B-TAXTRIAGE-1 + B-DEEPAC-1.

[ ] B-CNPRO-1  Adopt CNproScan (Jugas et al., 2021) as a bacterial CNV
               pipeline-zoo entry. Wire to pipeline_results loader.
               Useful especially for AMR-gene copy number variation,
               which generic CNV callers miss.
               Effort: 1-2 sessions. Phase: pipeline-zoo work.

[ ] B-PROSV-1  Adopt ProcaryaSV (Jugas & Vitkova, 2024) as the bacterial
               SV pipeline-zoo entry. Pairs with CNproScan (B-CNPRO-1)
               for full bacterial CNV+SV coverage.
               Effort: 1-2 sessions. Phase: pipeline-zoo work, with
               B-CNPRO-1.

[ ] B-SNIPG-1  Add SNiPgenie (Farrell et al., 2025) as an alternative
               SNP-calling pipeline-zoo entry to bactopia for cases where
               bactopia is overkill (single-organism outbreak; not the
               full bactopia workflow).
               Effort: 1 session. Phase: pipeline-zoo work.

[ ] B-SKA2-1  Add SKA2 (Derelle et al., 2024) as the rapid-triage
              variant-calling pipeline-zoo entry. Recommended workflow:
              SKA2 for first-pass cluster identification across all
              samples, then SNiPgenie + bactopia for the focal cluster.
              Effort: 1 session. Phase: pipeline-zoo work, with B-SNIPG-1.

[ ] B-NANOC-1  Adopt NanoCore (Fuchs et al., mSystems 2024) as the
               canonical Nanopore-aware core-genome outbreak-tracking
               pipeline. Pairs with bactopia (already shipped) for
               Illumina-only workflows; NanoCore handles the mixed-
               sequencer federation case.
               Effort: 2 sessions. Phase: pipeline-zoo work.

[ ] B-PFHAP-1  Adopt Pf-HaploAtlas (Lee et al., 2024) as the malaria-
               specific pipeline-zoo entry. Self-hostable; outputs feed
               pipeline_results JSONB. Document the schema mapping for
               haplotype data.
               Effort: 2-3 sessions. Phase: pipeline-zoo work.

[ ] B-PYMLST-1  Adopt pyMLST as the custom-cgMLST-scheme pipeline-zoo
                entry. Default schema source is pubMLST; operators can
                build custom schemes for non-standard organisms.
                Effort: 1-2 sessions. Phase: pipeline-zoo work.

[ ] B-AMRO-1  Adopt AMRomics (Le et al., 2024) as the population-scale
              AMR-surveillance pipeline-zoo entry. Pairs with B-NCBI-2
              (hAMRonization output mandate) for clean cross-pipeline
              comparability.
              Effort: 2-3 sessions. Phase: pipeline-zoo work, with
              B-NCBI-2.

[ ] B-RECOMB-1  Adopt OpenRecombinHunt (Alfonsi et al., 2026) as the
                viral-recombination-detection pipeline-zoo entry. Wire
                to a periodic-scan workflow that runs on JACKPOT's
                public viral datasets.
                Effort: 2 sessions. Phase: pipeline-zoo work.

[ ] B-GRUMB-1  Study GRUMB (Aminu et al., 2025) for the environmental
               metagenomics + risk-scoring layer of Pillar I. Decide:
               adopt directly, fork+adapt, or build alternative.
               Effort: 2-3 weeks study. Phase: when Pillar I implementation
               begins (Year 2+).

[ ] B-KOMB-1  Study KOMB/KombOver for the community-shift detection
              layer of Pillar I. Pairs with AMAnD (per-sample anomaly)
              for two complementary signals.
              Effort: 1-2 weeks study. Phase: with B-AMAND-1.

[ ] B-EIOS-1  Document the EIOS signal-feed integration pattern for
              JACKPOT operators. Define the JSON-schema for incoming
              EIOS events and how they appear in JACKPOT's audit log
              and bio-anomaly correlation. No code yet — this is
              documentation work; full implementation is a Pillar I
              deliverable in Year 2+.
              Effort: 1 session documentation. Phase: pre-Pillar I.

[ ] B-FED-PILLARIII-1  Decide FL framework for Pillar III. Use FedTADBench
                       to benchmark DataSHIELD-class vs FedAdapt-CAD vs
                       FedMI on representative anomaly-detection workloads.
                       Pick based on benchmark + mature-tooling tradeoff.
                       Effort: 2 weeks benchmarking + 1 week documentation.
                       Phase: Pillar III implementation start (Year 2+).

[ ] B-REALTIME-1  Document and implement the JACKPOT real-time-analysis
                  story: MARTi (B-MARTI-1) for nanopore metagenomics,
                  NanoCore (B-NANOC-1) for nanopore outbreak typing,
                  PathoLive (study) for Illumina real-time pathogen ID.
                  Wire to WebSocket-driven UI updates so operators see
                  results as the sequencer runs.
                  Effort: 3-4 sessions for the umbrella integration
                  beyond the per-tool adoptions. Phase: post B-MARTI-1,
                  B-NANOC-1.

[ ] B-CRISPR-EBX-1  Study CRISPR-eBx (Durán-Vinet et al., 2025) as the
                    canonical CRISPR-Dx environmental biosurveillance
                    integration pattern for Pillar I extension to eDNA.
                    Effort: 1-2 weeks study. Phase: Pillar I extension
                    (Year 2+).
```

**Total new backlog items from this analysis: 24.**

Combined with the 16 backlog items in `jackpot_governance_alignment.md` §7 and the 5 cross-cutting recommendations in `jackpot_platform_landscape.md` §19, the active component-tier and governance-tier backlog is now ~45 items. Sequenced through the Tier 0/1/2/3 scheme in §5, this is 18-24 months of work distributed across pipeline-zoo, ingest-pipeline, Pillar implementation, and federation architecture phases.

---

## 7. Cross-references

For full architectural and design context behind each adoption claim above:

| Topic | Reference |
|---|---|
| Platform-tier comparison (Loculus, Pathoplexus, etc.) | `jackpot_platform_landscape.md` |
| WHO/IPSN, GA4GH, FAIR/CARE alignment | `jackpot_governance_alignment.md` |
| GCP deployment guide | `sovereign_portal_delta.md` |
| Immune Platform plan (Pillars I–V) | `jackpot_immune_platform_plan.md` |
| JACKPOT architecture full reference | `jackpot_architecture.md` |
| Active spec | `spec.md` |
| Running session log | `jackpot_session_summary_and_backlog.md` |
| Active backlog | `todo.md` |

### 7.1 LeapSpace source files (now superseded)

The following 9 files are superseded by this synthesis. References to them in code review or docs should redirect here:

1. `What_open_source_software_tools_focus_on_anomaly_detection_for_biosurveillance.md`
2. `What_open_source_software_tools_focus_on_MLAI_for_pathogen_detection.md`
3. `What_open_source_tools_are_available_for_metagenomic_analysis_of_unknown_pathogens.md`
4. `What_role_does_federated_learning_play_in_biosurveillance_software.md`
5. `Open_source_software_projects_focused_on_detecting_novel__unknown_pathogens_via_genome_analysis.md`
6. `What_open_source_software_projects_focus_on_AI_enabled_genomic_surveillance__novel_pathogen_detection__and_novel_pathoge.md`
7. `What_open_source_software_tools_are_available_for_detection_of_genomic_anomalies_in_pathogen_genomes.md`
8. `What_open_source_software_tools_focus_on_biosurveillance_and_biosecurity.md`
9. `What_open_source_tools_use_artificial_immune_system_algorithms_to_detect_novel__emerging__and_unknown_pathogens.md`

---

*End of detection landscape v1.0. Pairs with `jackpot_platform_landscape.md` (platform-tier), `jackpot_governance_alignment.md` (alignment matrices), `sovereign_portal_delta.md` (deployment guide), and `jackpot_immune_platform_plan.md` (Immune Platform Pillars I–V).*
