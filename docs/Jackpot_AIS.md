## Concept 1 — Strictly Educational Curriculum: **JACKPOT Academy**

A free, AGPL-licensed, modular pathogen genomics curriculum that lives inside the JACKPOT monorepo at `course/` (which is already in your planned tree — convenient!). Think Software Carpentry meets nf-core training meets a microbiology bootcamp, but with a real production platform as the backbone instead of toy notebooks.

### Audience tiers

| Tier             | Audience                                                     | Time       | Outcome                                               |
| ---------------- | ------------------------------------------------------------ | ---------- | ----------------------------------------------------- |
| **Foundations**  | CS people who don't know biology, biologists who don't know CS | 4–6 weeks  | Comfortable with fastq, bash, Docker, Nextflow basics |
| **Practitioner** | Public health / state lab staff, grad students               | 8–12 weeks | Can run end-to-end outbreak analysis on JACKPOT       |
| **Operator**     | Engineers deploying JACKPOT for an agency or LMIC partner    | 4 weeks    | Can stand up Targets A–E and onboard tenants          |
| **Contributor**  | OSS devs who want to extend JACKPOT                          | self-paced | Can ship a PR to backend, schema, or a pipeline       |

### Module spine (16 modules, ~6–8 hrs each)

1. **Sequencing 101** — Illumina vs ONT vs PacBio, what fastq actually is, why quality scores matter
2. **Linux & Python for genomics** — bash one-liners, pandas, biopython
3. **Pi cluster build** — k3s + Slurm-on-Pi + Nextflow `local` profile (this is your Pi-cluster zine)
4. **QC & host scrubbing** — fastp, NanoPlot, **HRRT/Scrubber** (your differentiator)
5. **Taxonomic ID** — PanGIA, Kraken2, mash screen, "what bug is this?"
6. **Assembly** — SPAdes for short reads, Flye for long, hybrid with Unicycler
7. **Variant calling** — Snippy, BCFtools, DeepVariant
8. **AMR & virulence** — CARD, AMRFinderPlus, abricate, VFDB
9. **Phylogenetics** — IQ-TREE, Nextstrain, transmission cluster detection
10. **Metagenomics & microbiome** — host filtering, finding pathogens hiding in noise
11. **One Health perspective** — clinical / animal / environmental sample types, your schema
12. **PII & data ethics** — HRRT, **Cloud DLP**, WHO data sharing principles, federated analysis
13. **Pipeline engineering** — Nextflow + nf-core + Tower, writing your own modules
14. **Platform engineering** — JACKPOT internals (FastAPI, schema-driven UI, multi-tenancy)
15. **Edge deployment** — Jetson, Coral TPU, MinION basecalling on the edge
16. **ML/DL for genomics** — Janggu, AlphaFold for variant impact, sequence embeddings

### Delivery infrastructure

- **JupyterHub** (already on your Month 3 roadmap) hosts the notebooks
- **Synthetic datasets** in `course/data/` — never any PHI, ever. Generated with `wgsim` / `badread` from public refs
- A dedicated `academy` tenant on a public JACKPOT instance gives every student real platform experience without needing to deploy
- **Badges / micro-credentials** issued by JACKPOT itself (a small `course_completions` table, signed JWT credentials)
- Each module ends with a **JACKPOT integration exercise** — actually log in, upload synthetic samples, run the pipeline, interpret results in the UI
- Workshop-in-a-box: `jackpot init --profile academy` spins up the whole thing on a laptop

### Partnership angles

- **Software Carpentry / Data Carpentry** — host as official lessons, get peer review
- **nf-core training** — cross-link, become the "applied to public health" track
- **EMBL-EBI Train Online** / **WHO IPSN training pillar** — international reach
- **Galaxy Training Network** — port a few modules
- **State public health lab consortium** — paid cohort tier underwrites the free tier

### Why this works for JACKPOT specifically

You ship docs, schema, and code already. Add curated learning paths and you've turned the platform into a teaching instrument — which is exactly what WHO/IPSN attribute 6 (workforce capacity) is asking for. It also gives you an excuse to keep the synthetic data generators tight, which doubles as your QA fixture suite.

------

## Concept 2 — Interactive Game (Local / Single-Player): **Outbreak: Field Edition**

A local, offline-playable narrative puzzle game built on top of JACKPOT. No accounts, no servers, no leaderboards. Just you, a laptop, and a series of escalating mysteries. Think *Her Story* or *Return of the Obra Dinn* meets a real bioinformatics terminal.

### Premise

You play a contract analyst. Each "case" arrives as a zip file with: a briefing letter, a metadata CSV, one or more fastq files, and sometimes a red herring (a corrupted PDF, a fake tar that's actually a fastq — file type sniffing FTW, your `file_detector.py` is literally a game mechanic). You have a local JACKPOT instance and a fixed compute budget. Solve the case, file your report, get scored.

### Mechanics

| Mechanic                | What it teaches                                              |
| ----------------------- | ------------------------------------------------------------ |
| **Compute budget**      | Real concept of cloud cost / Pi cluster scarcity             |
| **Time pressure**       | Some cases are "live outbreak" — clock ticks, more samples arrive |
| **File-type detection** | That "PDF" is gzipped fastq. Run `file`, don't trust extensions |
| **PII gates**           | Forget to scrub before sharing? Penalty. Teaches HRRT/DLP viscerally |
| **Federation choice**   | Some cases unsolvable solo; spin up a sim "partner lab" tenant |
| **Red herrings**        | Contamination, low coverage, sample swap — real lab reality  |
| **Wrong answer cost**   | File the wrong AMR call, you get a "patient harmed" letter next case |

### Case progression (matches curriculum modules so the game *is* a teaching tool)

1. **The First Patient** — single fastq, identify pathogen with PanGIA. Trivial. You feel smart.
2. **The Variant** — same species, but "is it new?" Snippy + reference comparison.
3. **The Cluster** — 12 samples, build a phylogeny, identify the transmission cluster, name patient zero by sequencing-date order.
4. **The Resistor** — AMR puzzle. Recommend a treatment without seeing the antibiogram.
5. **The Spike** — does a specific variant change protein binding? Pipe to AlphaFold/ESMFold, check epitope.
6. **The Microbiome Stowaway** — pathogen hidden in a microbiome sample. Filter host, then dig.
7. **The Synthesis** — codon bias / GC anomaly / sus restriction sites. Engineered or natural? (Spoiler: this one should be hard and you should be allowed to be wrong, because real biosecurity attribution is hard.)
8. **The Capstone** — outbreak across a region, multiple sample types, federation required.

### Tech

- Bundled as a `jackpot init --profile game` deployment target (a 7th target!)
- Streamlit or Tauri front-end for the briefing/messaging UX, but **all real work happens in the actual JACKPOT UI** — that's the point, you're learning the real tool
- Fake-SMS panel scripted in YAML so you (or contributors) can author cases easily
- Synthetic data generated reproducibly from a `cases/case_03/recipe.yaml` describing reference + mutations + simulator params + answer key
- Score files signed and submittable to a public ladder if the player wants (opt-in)

### Why it works

It's the curriculum's capstone but feels nothing like homework. Every "case" is a self-contained ~2-hour session you could play after dinner. Cases are author-able by the community — basically nf-core but for puzzles.

------

## Concept 3 — Online Multiplayer Espionage Game: **OPERATION: WILDFIRE**

OK, here's where we go big. This is your old "Stop the Plague" notes, fully realized, built on JACKPOT's federation model. It would also incidentally be the most thorough integration test ever written for a multi-tenant federated system.

### Premise (in-fiction)

A fictional intel agency — call it the **Bureau of Epidemiological Counterintelligence (BEC)** — recruits civilian analysts to investigate ongoing biothreat events. There is always a mole. There are always competing factions. The science is always real. The plot is always pulpy.

You are recruited via an in-character website, given a codename, and assigned a Handler. Missions drop weekly. You play solo or join a cell.

### Core loop

1. **Dead drop**: A new mission lands in your in-game inbox. Files attached. Sometimes encrypted. Sometimes claiming to be from a different agency (and possibly compromised).
2. **Verify**: Are these files what they claim? Run sniffers. Check sample provenance. Don't trust the briefing.
3. **Analyze**: Use your JACKPOT tenant. Real pipelines, real tools, real data (synthetic but technically valid).
4. **Decide**: Share with cell? Share with rival cell for trade? Hoard for personal points? Share with the public (lose the mission, gain reputation)?
5. **Submit**: Findings get scored on accuracy, speed, OPSEC compliance, and ethical conduct.
6. **Consequence**: World-state updates based on aggregate player decisions.

### Persistent world

The game world is a simulated globe with ongoing outbreaks. Players' aggregate decisions affect world health metrics (visible on a dashboard). One season ≈ 12 weeks ≈ one major story arc.

### Mechanic playground

| Mechanic                     | JACKPOT feature it showcases                             |
| ---------------------------- | -------------------------------------------------------- |
| **Cell vs solo play**        | Multi-tenant + RBAC                                      |
| **Inter-cell intel sharing** | Federation deployment target (E)                         |
| **Dead-drop file packages**  | Schema-driven sample ingest                              |
| **OPSEC scoring**            | DLP scanner — leak metadata, lose points                 |
| **Edge ops sub-game**        | Pi-cluster / Jetson edge target (A)                      |
| **The Mole arc**             | Audit log review — who accessed what, when               |
| **Sealed evidence**          | Append-only `pipeline_results` immutability              |
| **Burn protocol**            | Tenant deletion / data lifecycle (your governance model) |
| **Compromised tooling**      | Container signing & supply-chain scenarios               |

### Roles within a cell (encourages team play)

- **Wet lab** — owns sample intake & metadata curation
- **Bioinformatician** — runs pipelines, interprets results
- **Phylo / Epi** — owns transmission analysis & temporal reasoning
- **ML/AI** — variant impact prediction, structural modeling, anomaly detection
- **InfoSec / OPSEC** — secures the cell's tenant, audits federation traffic
- **Handler / lead** — scopes missions, communicates with BEC

This maps perfectly onto a real public health response team. You're literally training disease detectives by gameplay.

### Story arcs (seasons)

- **S1: Patient Zero** — novel respiratory pathogen, classic intro arc
- **S2: Out of the Lab** — engineered or evolved? attribution puzzles
- **S3: One Health** — zoonotic spillover, multi-sector samples (clinical + animal + environmental — your One Health schema shines)
- **S4: The Mole** — there's a leak in your cell. Forensics on your own audit logs to find them
- **S5: Endemic** — long arc, global federation play required, AMR + climate angle

### Production / community

- **Open mission framework**: anyone can author a case (`cases/season_2/episode_07/`) and submit a PR
- **Live ops team**: a small group (you + volunteers) runs weekly story beats, NPC interactions, and arbitrates ambiguous cases
- **In-character forum** (Mastodon instance? Matrix room?) where players role-play their analysts; sometimes Handler drops clues there
- **ARG layer**: occasional clues hidden in genome sequences (a designed silent mutation that spells out an IP address in ASCII when you translate the protein, etc.). Annoying nerd-bait of the highest order.
- **Real-world wet-lab tie-in**: top cells get sequencing kits with reference samples. Sequence, upload, score. Now your players are *also* QC'ing JACKPOT in the wild.

### Sustainability model

- **Free tier**: solo, local JACKPOT, all current-season missions (one week delayed)
- **Cell tier ($)**: cloud-hosted tenant, real-time mission drops, federation membership
- **Edu tier (institutional)**: classroom pack, instructor dashboard, custom missions, season-long cohort
- **Partner tier**: public health agencies / training programs license the platform for their workforce development
- All revenue (after costs) flows back to JACKPOT OSS development. AGPL forever.

### Why this is, frankly, kind of brilliant

It is simultaneously: a recruitment funnel for public health bioinformatics, the most complete real-world test environment for JACKPOT's federation model, an entertainment property that justifies its own development cost, a generator of synthetic-but-realistic case data that improves the upstream tools, and a community-building flywheel for an OSS platform that otherwise lives or dies by GitHub stars and grant cycles.

------

## How they share a spine

The trick to building all three without going insane is recognizing they're the same thing at different intensities. One stack, three skins.

```
                       ┌──────────────────────────┐
                       │    JACKPOT core platform │
                       │  (backend / schema /     │
                       │   pipelines / CLI)       │
                       └────────────┬─────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
       ┌──────▼──────┐       ┌──────▼──────┐       ┌──────▼──────┐
       │   Academy   │       │  Field Ed.  │       │  WILDFIRE   │
       │  (curric.)  │       │   (game)    │       │ (online MP) │
       └─────────────┘       └─────────────┘       └─────────────┘
        notebooks +           local profile          federation +
        JupyterHub            single-player          live ops +
        in `course/`          campaign cases         community
```

Shared assets across all three:

| Asset                                                        | Used by       |
| ------------------------------------------------------------ | ------------- |
| Synthetic data recipes (`recipe.yaml` → fastq)               | All three     |
| Case authoring framework                                     | Game + Online |
| `jackpot init` profiles (`academy`, `game`, `wildfire`)      | All three     |
| Skill/badge issuance (small JACKPOT module)                  | All three     |
| Mission manifest schema (additions to `jackpot_schema.yaml`) | Game + Online |
| Synthetic FASTQ generator service                            | All three     |
| The actual UI you've already built                           | All three     |

## Suggested build order (if you wanted to actually do this)

1. **Synthetic data recipes** — small, useful even outside any of these projects (regression tests!)
2. **Academy MVP** — modules 1, 4, 5, 12 first; ship as `course/` in the monorepo
3. **Field Edition: Case 1–3** — proves the case-authoring framework
4. **Field Edition: Cases 4–8 + community case submission**
5. **WILDFIRE alpha season** — single arc, ~30 testers, learn what actually works
6. **WILDFIRE Season 1 public** — once federation deployment target (E) is rock solid

The beauty: every piece you build for #2 makes #3 cheaper, every piece you build for #3 makes #4 better, and #5 stress-tests parts of JACKPOT that no real customer will ever exercise this hard.

------

Want me to drill into any of these? I'd happily sketch out what `cases/case_01/recipe.yaml` looks like, write a draft of the Academy module 4 (the scrubber/HRRT one — biggest JACKPOT differentiator), or rough out the OPERATION: WILDFIRE pilot season story bible. Or all three. You said no bad ideas. 🎲



I'll research each tool mentioned in your notes to see which ones are still current and find modern alternatives for any that are outdated. Let me start with some searches.Perfect! Based on my research, here's a comprehensive analysis of all the tools mentioned in your notes, their current status, and modern alternatives:

## **Tool Status Analysis & Modern Substitutes**

### **🟢 Still Current & Actively Maintained**

| Tool                 | Status                   | Notes                                                        |
| -------------------- | ------------------------ | ------------------------------------------------------------ |
| **Kraken2/Bracken**  | ⭐ **Gold Standard**      | Kraken2/Bracken achieved the highest classification accuracy, with consistently higher F1-scores across all food metagenomes, and performed best with median percentage of reads across both sequencing platforms identified correctly to the species level was 97.8%. Now includes 16S databases, up to 300x faster than alternatives |
| **Nextstrain**       | ⭐ **Very Active**        | Still being actively used for spatiotemporal genomic epidemiology, with recent 2024-2025 papers showing continued development and adoption. Real-time pathogen evolution tracking |
| **PathogenWatch**    | ⭐ **Extremely Active**   | Over 14,000 registered users across 165 countries collectively uploaded more than 300,000 genome assemblies in 2025 alone, and the platform now contextualises user data against over 1.7 million curated public bacterial genomes |
| **IRIDA**            | 🟡 **Current**            | Still being used since 2012 for national surveillance of foodborne disease (PulseNet) in the pan-Canadian Public Health Laboratory Network (CPHLN), with instances installed across the globe |
| **Nextflow & Tower** | ⭐ **Industry Standard**  | Nextflow is the current gold standard. Tower is now called "Seqera Platform" |
| **Janggu**           | 🟡 **Stable but Limited** | Published 2020, still available but limited compared to newer frameworks. Good for keras/pytorch integration |

### **🟡 Outdated - Need Modern Substitutes**

| Old Tool   | Status             | **Modern Alternative**                                       | Why Better                                                   |
| ---------- | ------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **PanGIA** | 🔴 Limited          | **Kraken2/Bracken**                                          | Kraken2/Bracken achieved the highest classification accuracy, with consistently higher F1-scores across all food metagenomes |
| **bcbio**  | 🔴 **DISCONTINUED** | **nf-core pipelines**                                        | Notice of discontinuation of this project - 08-16-2024. Nextflow and the nf-core community have seen substantial growth, now hosting numerous globally-used bioinformatics pipelines |
| **IDseq**  | 🟡 Limited Updates  | **nf-core/viralmetagenome** + **nf-core/pathogensurveillance** | IDseq last major publication 2020, while nf-core has new viral metagenomics and pathogen surveillance pipelines as of 2025 |

### **🔍 Uncertain Status - Limited Recent Info**

| Tool              | Status    | Research Notes                                     |
| ----------------- | --------- | -------------------------------------------------- |
| **Arteria**       | 🔍 Unknown | No recent publications found                       |
| **Coxbase**       | 🔍 Unknown | Likely specialized for *Coxiella*, may be outdated |
| **Shigella tool** | 🔍 Unknown | Likely superseded by broader platforms             |
| **INNUENDO**      | 🔍 Unknown | No recent activity found                           |
| **GLUE**          | 🔍 Unknown | Limited recent references                          |
| **BARD**          | 🔍 Unknown | No clear current status                            |
| **GenPipes**      | 🔍 Unknown | Canadian project, unclear maintenance              |
| **EDGE**          | 🔍 Unknown | LLNL biodefense tool, likely classified/restricted |
| **Selene**        | 🔍 Unknown | May be outdated compared to modern alternatives    |

### **🚀 Modern Replacements & Additions**

Here are the **current best-practice tools** to replace or supplement your list:

#### **For Pathogen Identification & Metagenomics:**

- **Kraken2/Bracken** (replaces PanGIA, others)
- **nf-core/pathogensurveillance** (2025 pipeline for population genomics and pathogen identification)
- **nf-core/viralmetagenome** (Novel pipeline for untargeted viral genome reconstruction, 2025)
- **CholeraSeq** (Comprehensive genomic pipeline for cholera surveillance, building upon nf-core standards)

#### **For Phylogenetics & Epidemiology:**

- **Nextstrain** (still the gold standard)
- **PathogenWatch** (massive user base, very active)
- **nf-core/phylogenomics**

#### **For Comprehensive Pipelines:**

- **nf-core ecosystem** (replaces bcbio completely)
- **IRIDA** (if you need the full platform experience)

#### **For Deep Learning:**

- **Janggu** (still works, but consider)
- **Selene** (if still maintained)
- **PyTorch Geometric** + **BioPython** for custom work

#### **For Edge/Field Deployment:**

- **Nextflow** with local profiles
- **MinKNOW + Guppy** for ONT
- **NVIDIA Clara Parabricks** for GPU acceleration

### **🎯 Recommendations for Your Gaming/Educational Platform**

Given your focus, I'd suggest this **modern core toolset**:

#### **Tier 1 - Essential Modern Stack:**

```bash
# Pathogen ID (replaces PanGIA)
kraken2 + bracken

# Phylogenetics & Epidemiology
nextstrain + pathogenwatch

# Pipeline Framework (replaces bcbio)
nextflow + nf-core pipelines

# Quality Control
fastp + multiqc

# Assembly
spades + flye + quast
```

#### **Tier 2 - Advanced/Specialized:**

```bash
# nf-core specific pipelines
nf-core/pathogensurveillance
nf-core/viralmetagenome
nf-core/mag (metagenome-assembled genomes)

# Variant calling
snippy + bcftools

# AMR Detection
abricate + amrfinderplus

# Visualization & Reporting
auspice + phandango
```

#### **Tier 3 - Edge/Gaming Additions:**

```bash
# Edge deployment
k3s + nextflow
guppy (GPU basecalling)

# Synthetic data generation
wgsim + badread + mason2
```

This modern stack would give your gaming/curriculum platform **much better performance**, **active community support**, and **real-world relevance** compared to the older tools in your original notes. The nf-core ecosystem especially is perfect for educational purposes since it has excellent documentation, standardized practices, and broad adoption in the genomics community.

Want me to dive deeper into any of these modern tools or draft specific implementation strategies for your JACKPOT-based gaming platform?



Let me do more research on modern tools and emerging tech I might have missed before rewriting.Alright, this is rich material. Let me give you what I found, then rebuild the concepts on a 2025/2026-era stack, plus add a fourth concept that the new tooling unlocks.

------

# Part 1 — What's Worth Adding (Stuff Beyond the Original Notes)

These are tools and functionality categories that didn't show up in your old notes but should reshape the concepts.

## 🆕 Tools & functionality you didn't mention

### Wastewater genomic surveillance — the biggest miss

This is arguably the single hottest area in pathogen genomics right now and it wasn't in your notes at all.

- **Freyja 2** — the standard. Integrated bioinformatics tool for real-time inference of pathogen lineage prevalence and growth dynamics from wastewater, now extended to multi-pathogen surveillance and adopted from local health departments to national/international programs.
- **Aquascope** — CDC's wastewater pipeline; used by CDC for SARS-CoV-2 lineage tracking through the National Wastewater Surveillance System.
- **C-WAP, V-pipe** — alternative wastewater-aware variant callers
- **UShER** for ultrafast phylogenetic placement (millions of seqs in seconds)

### Public-health workflow ecosystem (the *real* infrastructure)

Your old list missed the actual production workflows public health labs run today:

- **StaPH-B Docker images** — 170,000+ downloads of the StaPH-B Docker container as of May 2025, the de facto standard
- **Theiagen PHB workflows** (TheiaCoV / TheiaProk / TheiaEuk / TheiaMeta) on **Terra.bio** — the actively maintained, quarterly-released, Terra-deployable WDL workflow suite for pathogen characterization, genomic epidemiology, and submission preparation
- **Bactopia** — Robert Petit's bacterial WGS pipeline (still going strong)
- **GAMBIT** — k-mer based bacterial ID built to *diagnostic-test* quality standards
- **PHA4GE** — the standardization body whose specs you should align JACKPOT's schema against

### Modern data-sharing platforms (huge for your federation story)

- **Pathoplexus / Loculus** — Pathoplexus is a specialized genomic database for viruses of public health importance, powered by the open-source Loculus software, with transparent governance and equitable data sharing — a non-profit association with members from 10 countries. **This is essentially what JACKPOT's federation deployment target looks like in the wild.**
- **GenSpectrum / LAPIS** — query API and dashboarding for huge sequence collections
- **Pathogens.jp** (Japan's new portal), **CLIMB-Big-Data** (UK)

### AI/ML — way beyond Janggu

- **ESMFold + ESM3** (Evolutionary Scale) — ESM3 published in Science January 2025; opening API for biological intelligence in public beta. Joint sequence-structure co-design models like ESM3 integrate both modalities into a unified framework, resulting in improved designability.
- **AlphaFold3 + AlphaFold Multimer** — for complexes and ligand binding
- **AlphaMissense** — pathogenicity prediction for missense variants
- **ProteinMPNN, RFdiffusion** — de novo protein design
- **DeepVariant** — Google's CNN variant caller (gold standard for short reads)
- **Boltz-1, Chai-1** — open-source AlphaFold3 alternatives without the licensing pain

### LLM agents — completely new category

Genuinely the future of this space and absolutely unmentioned in your notes:

- Agentic LLMs show early promise in enabling multi-step analysis, linking heterogeneous evidence, and supporting exploratory scientific tasks across genomics, proteomics, drug discovery, and metagenomics
- **AutoBA**, **BioInformatics Agent (BIA)**, **DrugAgent** — early prototypes
- The pattern: an LLM that has *tool access* to bioinformatics CLIs, can plan a workflow, run it, interpret results, and report
- For your concepts: this is how you build an **in-game AI assistant** that scales from "noob's autopilot" to "expert's force multiplier"

### Modern edge sequencing

- **Dorado** has fully replaced Guppy — Dorado is the high-performance default basecaller now integrated into MinKNOW, with NVIDIA A100 acceleration enabling real-time high-accuracy basecalling
- **DeepNano-blitz** — CPU-only basecaller for laptop field use
- **DeepNano-coral** — runs on the Coral Edge TPU at 10W, perfect for your "stealth contraption" goal
- **R10.4.1 flow cells** — current standard, much higher accuracy than R9
- **ReadFish** / **adaptive sampling** — let nanopore reject host reads in real-time, sequence only the pathogen

### AMR/virulence — modernized

- **AMRFinderPlus** (NCBI) — current US standard
- **CARD / RGI** — Comprehensive Antibiotic Resistance Database
- **hAMRonization** — standardizes output across AMR tools (huge for federation)
- **abritAMR** — Australian government wrapper

### Other modern bits

- **fastp** (replaces fastqc + trimmomatic), **NanoPlot** for ONT QC
- **Snippy v5**, **iVar** for variant calling
- **Flye / Trycycler / Unicycler** for assembly (Flye is the long-read champion)
- **mlst**, **chewBBACA**, **pyMLST** for typing
- **Pavian** for interactive Kraken2 result exploration
- **Taxonium** for visualizing million-tip phylogenies
- **clinker / pyGenomeViz** for genome comparisons

------

# Part 2 — The Three Concepts, Rewritten

## Concept 1 — **JACKPOT Academy** (curriculum)

A free, AGPL-licensed, modular pathogen genomics curriculum living in `course/` of the JACKPOT monorepo. Now grounded in tools that public health labs *actually run today* rather than 2018-era research code.

### Audience tiers (unchanged in spirit, sharper in tooling)

| Tier             | Audience                                                  | Time       | Outcome                                                      |
| ---------------- | --------------------------------------------------------- | ---------- | ------------------------------------------------------------ |
| **Foundations**  | CS folks new to bio, biologists new to CS                 | 4–6 weeks  | Comfortable with fastq, Bash, Docker, Nextflow basics, Terra UI |
| **Practitioner** | Public health/state lab staff, grad students              | 8–12 weeks | Can run end-to-end outbreak analysis on JACKPOT *and* Terra  |
| **Operator**     | Engineers deploying JACKPOT for an agency or LMIC partner | 4 weeks    | Can stand up Targets A–E, federate with Pathoplexus-style hubs |
| **Contributor**  | OSS devs extending JACKPOT                                | self-paced | Can ship a PR to backend, schema, or pipelines               |

### Updated module spine (16 modules)

1. **Sequencing 101** — Illumina vs ONT (R10.4.1 era) vs PacBio HiFi; pod5 / fastq / BAM
2. **Linux & Python for genomics** — bash, pandas, biopython, pysam
3. **Pi cluster build** — k3s + Nextflow `local`/`slurm` + StaPH-B Docker images
4. **QC & host scrubbing** — `fastp`, `NanoPlot`, `multiqc`, **HRRT/Scrubber** (your differentiator), DLP
5. **Taxonomic ID** — **Kraken2 + Bracken** (replaces PanGIA), `mash screen`, `sourmash`, **GAMBIT**, Pavian
6. **Assembly** — `SPAdes`, `Flye`, `Unicycler`, `Trycycler`; `QUAST` + `BUSCO` for QC
7. **Variant calling** — `Snippy`, `BCFtools`, **DeepVariant**, `iVar` (amplicon)
8. **AMR & virulence** — **AMRFinderPlus**, **CARD/RGI**, `abricate`, **hAMRonization** for cross-tool reconciliation
9. **Phylogenetics & rapid placement** — `IQ-TREE`, `RAxML`, **UShER**, **TreeTime**, **Auspice**
10. **Metagenomics & microbiome** — host filtering with `bowtie2`/`minimap2`, **nf-core/mag**, Kraken2 for pathogen-in-noise
11. **One Health & wastewater** *(NEW MODULE)* — wastewater workflows, **Freyja 2**, **Aquascope**, environmental sampling
12. **PHA4GE & data ethics** — schema standardization, **HRRT**, **Cloud DLP**, WHO data-sharing principles, **Pathoplexus/Loculus** governance
13. **Pipeline engineering** — Nextflow + nf-core, **WDL** + Cromwell + Terra (you need both — this is the bilingual world public health actually lives in)
14. **Platform engineering** — JACKPOT internals (FastAPI, schema-driven UI, multi-tenancy)
15. **Edge deployment** — Jetson / Coral TPU / **DeepNano-coral**, **Dorado**, ReadFish adaptive sampling, MinION in the field
16. **AI for genomics** *(REWRITTEN)* — protein structure with **ESMFold/AlphaFold3**, variant impact with **AlphaMissense**, **LLM agents** for orchestrating bioinformatics tasks

### Fresh additions to the delivery infrastructure

- **JupyterHub** still primary, but with **Terra workspace links** for every module that has a WDL counterpart — students learn in both ecosystems
- **A `Theia\*` parity track** — every JACKPOT pipeline module also runs the equivalent TheiaProk/TheiaCoV workflow, so graduates can work in either world
- **PHA4GE-aligned synthetic datasets** — your `recipe.yaml` files emit metadata that conforms to PHA4GE specs from day one
- **Pathoplexus sandbox tenant** — module 12 includes a federation exercise against a Loculus instance you stand up for the academy
- **LLM-tutor mode** — students can ask an in-course agent ("explain why this variant matters") that has access to the curriculum, their notebook state, and the tool docs

------

## Concept 2 — **Outbreak: Field Edition** (single-player local game)

Same narrative-puzzle skeleton, modern tool diet underneath. The mechanics that worked stay; the engine swaps in production-grade libraries.

### Updated case progression

| #    | Case                        | Real tools used                                              | What it teaches                                              |
| ---- | --------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 1    | **The First Patient**       | `fastp` → `Kraken2/Bracken` → Pavian                         | Pathogen ID from a single sample                             |
| 2    | **The Variant**             | `Snippy` or **DeepVariant** vs reference, **AlphaMissense** for impact | Variant calling, knowing when a SNP matters                  |
| 3    | **The Cluster**             | `Snippy` → `IQ-TREE` → **Auspice**                           | Phylogeny, transmission cluster identification               |
| 4    | **The Resistor**            | **AMRFinderPlus** + **CARD** + **hAMRonization**             | AMR detection and reconciliation across tools                |
| 5    | **The Spike** *(reworked)*  | **ESMFold** for structure, **AlphaMissense** for variant scoring, **AlphaFold3** for binding | Structural impact of variants on antibody/drug binding       |
| 6    | **The Microbiome Stowaway** | `bowtie2` host removal → **nf-core/mag** → Kraken2 + sourmash | Finding pathogens hiding in metagenomes                      |
| 7    | **The Synthesis**           | Codon bias analysis, GC anomaly detection, sequence-similarity to known engineered constructs | Engineered-vs-natural attribution (intentionally hard, intentionally honest about limits) |
| 8    | **The Capstone**            | Multi-sample, multi-source outbreak; requires federation with a sim partner lab via Loculus-style API | End-to-end response coordination                             |

### New cases enabled by modern tooling

| #    | New Case                | What's added                                                 |
| ---- | ----------------------- | ------------------------------------------------------------ |
| 9    | **The Sewer Sentinel**  | **Freyja 2** wastewater run; player must distinguish a real signal from a single shedder vs population emergence |
| 10   | **Adaptive Pursuit**    | Live MinION simulation; player configures **ReadFish** rules to enrich for the suspect pathogen on the fly |
| 11   | **The Agent Has Notes** | Player gets an LLM analyst-agent (local, llama.cpp-style); must learn when to trust its conclusions and when to override |
| 12   | **The Federation Test** | Play it cross-instance with a friend's JACKPOT — solve a case neither of you can solve alone without sharing partial data via Loculus protocol |

### Upgraded mechanics

| Mechanic                           | Modern hook                                                  |
| ---------------------------------- | ------------------------------------------------------------ |
| **OPSEC penalty**                  | DLP scan + PHA4GE field-validation; non-compliant metadata drops you in standings |
| **Pipeline budget**                | Choose nf-core *or* Theiagen WDL; each has different runtime/cost tradeoffs in-game |
| **Speed-vs-accuracy**              | Run Dorado in `fast`/`hac`/`sup` modes; faster basecaller, less accurate variants downstream |
| **The agent-handler relationship** | The LLM assistant has a (configurable) reliability score — players who blindly trust it get burned, players who verify everything are too slow |

### Tech stack for the game itself

- Bundled as `jackpot init --profile game` — a 7th deployment target
- **Streamlit** front-end for briefing/SMS/agent-chat UI
- **All real bioinformatics work happens in the actual JACKPOT UI**
- Cases authored as `cases/case_NN/recipe.yaml`: reference + simulated mutations + answer key + LLM persona
- Data simulated with `wgsim` (Illumina), `badread` (ONT), `dwgsim` (paired-end with errors)
- LLM agent runs via **llama.cpp** locally or hosted endpoint — your choice at install time

------

## Concept 3 — **OPERATION: WILDFIRE** (online multiplayer espionage)

Same pulpy premise, but now built on a 2026 stack that makes the federation mechanic a *killer feature* rather than aspirational vapor.

### What's actually new

The biggest upgrade: **federation isn't simulated, it's real.** Each cell runs a JACKPOT tenant configured to speak Loculus-compatible APIs. Inter-cell intel sharing in-game looks identical to how Pathoplexus member states share data in reality. The game *is* the demo.

### Roles within a cell — refreshed

- **Wet lab tech** — sample intake, PHA4GE metadata, **Dorado + ReadFish** configuration
- **Bioinformatician** — Kraken2/Bracken, Snippy, AMRFinderPlus; reads the noisy reality
- **Phylo / epi** — IQ-TREE + UShER + Auspice; reads time and space
- **Wastewater analyst** *(NEW ROLE)* — runs Freyja 2 against simulated treatment plant feeds; first to spot population-level signal
- **Structural / ML lead** *(NEW ROLE)* — ESMFold + AlphaMissense + AlphaFold3 to predict the impact of variants the others find
- **InfoSec / OPSEC** — audits the cell's tenant, watches federation traffic, looks for exfil
- **Agent handler** *(NEW ROLE)* — manages the cell's LLM agent fleet, configures their tool access and trust budget
- **Cell lead** — coordinates with BEC, allocates compute and federation bandwidth

### Mechanic playground — refreshed

| Mechanic                        | What it now showcases                                        |
| ------------------------------- | ------------------------------------------------------------ |
| **Cell vs solo play**           | JACKPOT multi-tenancy + RBAC                                 |
| **Inter-cell intel sharing**    | Real Loculus-protocol federation between game tenants        |
| **Wastewater early warning**    | Freyja 2 multi-pathogen — cells with sewer coverage see threats earlier |
| **Adaptive sampling decisions** | ReadFish rule-set choices visible to opponents who break your OPSEC |
| **OPSEC scoring**               | PHA4GE-compliance + DLP — leaked metadata loses you points   |
| **The Mole arc**                | Audit log review across tenants                              |
| **Sealed evidence**             | Append-only `pipeline_results` immutability becomes legal-chain-of-custody flavor |
| **Compromised tooling**         | Container signing — opponents can publish a poisoned StaPH-B clone, you have to verify |
| **AI agent espionage** *(NEW)*  | Cells can deploy LLM agents on rivals' public sequence shares; agents hallucinate or get prompt-injected; trust calibration becomes a survival skill |

### Story arcs — refreshed

- **S1: Patient Zero** — novel respiratory pathogen; classic intro arc
- **S2: Out of the Lab** — engineered vs evolved, attribution puzzles using ESM3 / AlphaFold3
- **S3: One Health** — zoonotic spillover; clinical + animal + environmental + wastewater integration
- **S4: The Mole** — audit-log forensics inside your own cell
- **S5: Endemic** — long arc; AMR + climate; **mandatory federation play, mandatory wastewater coverage**
- **S6: The Agent Wars** *(NEW)* — adversarial AI agents sabotaging each other's analyses; defensive prompt engineering becomes literal gameplay

### Tech additions

- **Federation hub** runs Loculus alongside JACKPOT — players see the real protocol they'd use in the wild
- **In-game wastewater feed simulator** generates Freyja-compatible mixed amplicon data on a schedule
- **Pluggable agent backends** — players can plug their own OpenAI/Anthropic/local-llama key; high-tier cells run local agents for OPSEC
- **Live ops dashboards** built on **Auspice** + custom Plotly — players see the global outbreak evolve in near-real-time

------

# Part 3 — A Fourth Concept (because the new tooling unlocks it)

## Concept 4 — **SENTINEL: A Cooperative Pathogen Surveillance Game**

WILDFIRE is competitive and pulpy. SENTINEL is its **cooperative twin** — *Pandemic the board game* energy, but everyone's running real bioinformatics. This concept literally cannot exist without the wastewater + federation + LLM-agent stack we just covered.

### The pitch

You and 3–7 friends are public health analysts in different cities (or different sectors of one mega-region). A novel pathogen is spreading on a map you can see. **You will lose unless you cooperate.** Each city is a JACKPOT tenant with a different sample mix, a different toolkit, and a different strength. The game is timed and the threat evolves; your only weapons are sequencing, sharing, and inference.

### City roles

Each player picks a city archetype with built-in advantages and gaps:

| City type                                             | Strength                                                     | Weakness                                         |
| ----------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------ |
| **Hub Metro** (Singapore/London/SF flavor)            | High clinical sequencing throughput, fast Dorado infrastructure | Low animal-sector visibility                     |
| **Wastewater Sentinel** (Boston-flavor)               | Best Freyja 2 coverage, earliest population signals          | Limited per-patient depth                        |
| **One Health Outpost** (rural/agricultural)           | Animal + environmental sampling, sees zoonotic spillover first | Slow turnaround, weak compute                    |
| **Border Crossroads**                                 | Travel-imported case detection                               | Bureaucratic friction (in-game: extra DLP gates) |
| **Edge Fielder** (your Pi-cluster fantasy realized)   | Mobile MinION + Coral TPU teams; deploys anywhere on the map | Tiny compute budget, no AI compute               |
| **AI Lab** (your "secret Coral TPU" fantasy realized) | Best LLM agents, structural prediction, ESMFold/AlphaFold3 access | No primary sequencing — needs others' data       |

### Core game loop

Per round (≈ a real-time week):

1. **Sample arrival** — your city gets new samples (clinical / wastewater / animal / environmental, depending on type)
2. **Triage** — choose what to sequence given a fixed compute budget
3. **Run pipelines** — actual JACKPOT pipelines on simulated reads
4. **Federate** — choose what to share with the network. Sharing helps everyone but costs OPSEC and discloses your strengths
5. **Inference round** — collective phylogenies, wastewater models, structural predictions update
6. **Threat updates** — pathogen evolves on the map based on what you missed; players lose if R₀ exceeds threshold

### Why this is technically interesting

- **Federation is the only path to victory** — one player can never see enough of the data to win alone
- **LLM agents become \*roles\*** — the AI Lab player's agent is genuinely contributing analysis the others can't replicate
- **Wastewater plays a real role** — population-level signals catch what clinical surveillance misses, *which is true in real life*
- **Cooperative tension** — when a Hub Metro wants to keep evidence private to verify, but the Wastewater Sentinel needs that data *now* to model spread, the game forces the conversation that real public health agencies have every week

### Story modes

- **Pandemic** — classic, viral respiratory pathogen, six rounds, hard
- **Slow Burn** — endemic AMR organism, 20 rounds, requires longitudinal phylogenetic thinking
- **Spillover** — zoonotic novel pathogen, One Health Outpost role suddenly critical
- **The Engineered One** — bioweapon hypothesis; you have to figure out *whether* it's engineered, which is hard and the game knows it
- **Climate Shifts** — vector-borne disease moving range with climate; new cities get added mid-game

### What the players actually do (no abstraction)

When the Wastewater Sentinel player runs a round, they:

```bash
# In their JACKPOT instance:
nextflow run nf-core/viralrecon \
    --input wastewater_samplesheet.csv \
    --protocol amplicon \
    --primer_set artic \
    --skip_assembly \
    --outdir results/

# Then in JACKPOT, run Freyja against the BAM:
jackpot pipeline run --pipeline freyja2 \
    --sample-set sentinel_2026w12_sewershed \
    --barcode-version latest

# Results land in JACKPOT, get federated per their data-sharing policy:
jackpot federation share \
    --tenant sentinel_boston \
    --target federation://global-watch \
    --policy strict-pha4ge
```

Real commands, real output, real pipeline. The **game** is in the timing, the choices, and the cooperation — not in fake bioinformatics.

### Why it complements the other three concepts

| Concept           | Energy                          | Audience                                                     |
| ----------------- | ------------------------------- | ------------------------------------------------------------ |
| **Academy**       | Disciplined, structured         | Learners                                                     |
| **Field Edition** | Solo, contemplative, cinematic  | Self-directed practitioners                                  |
| **WILDFIRE**      | Competitive, pulpy, espionage   | Long-game cell players, ARG fans                             |
| **SENTINEL**      | Cooperative, urgent, optimistic | Team-builders, classroom cohorts, real PH workforce training |

Together they cover the four corners of the player-energy space, and they all reuse the same engine: synthetic data, JACKPOT, modern tooling, mission framework.

------

# Part 4 — Quick Reference: Stack Summary

A single-pane view of what you'd actually install across the four concepts.

```bash
# Core platform
jackpot                           # your AGPL platform
nextflow + nf-core                # primary pipeline framework
WDL + Cromwell + miniWDL          # parity track for Terra interop
Theiagen PHB workflows            # public-health-grade WDL workflows
StaPH-B Docker images             # canonical containerized tools

# QC & preprocessing
fastp, NanoPlot, multiqc
NCBI HRRT (Scrubber)              # human read removal — JACKPOT's PII gate
Cloud DLP                         # metadata PII gate

# Pathogen ID
kraken2 + bracken                 # replaces PanGIA
sourmash, mash screen
GAMBIT                            # diagnostic-grade bacterial ID
Pavian                            # Kraken2 result browsing

# Assembly
SPAdes, Flye, Trycycler, Unicycler
QUAST, BUSCO, CheckM2

# Variant calling & impact
Snippy, BCFtools, DeepVariant, iVar
AlphaMissense                     # variant pathogenicity prediction

# AMR & virulence
AMRFinderPlus, CARD/RGI, abricate
hAMRonization                     # cross-tool reconciliation

# Phylogenetics & viz
IQ-TREE, RAxML, TreeTime
UShER                             # ultrafast placement
Auspice, Taxonium                 # visualization

# Wastewater (NEW CATEGORY)
Freyja 2, Aquascope, C-WAP
UShER barcodes pipeline

# Edge sequencing
Dorado (replaces Guppy)
DeepNano-blitz                    # CPU-only basecaller
DeepNano-coral                    # Coral TPU basecaller
ReadFish                          # adaptive sampling

# Structure & design
ESMFold, ESM3
AlphaFold3, AlphaFold-Multimer
Boltz-1, Chai-1                   # open-source AF3 alternatives
ProteinMPNN, RFdiffusion          # de novo design (S2/S3 of WILDFIRE)

# Data sharing & federation
Loculus / Pathoplexus protocol
GenSpectrum/LAPIS query API
PHA4GE specifications

# AI agents
llama.cpp, vLLM                   # local inference
LangGraph, CrewAI, Anthropic SDK  # agent orchestration
AutoBA-style bio-agent patterns

# Education / game UX
JupyterHub, Streamlit, Tauri
Terra.bio (for parity track)
```

Want me to drill into any of these — say, draft a SENTINEL pilot session walkthrough with the actual Nextflow + Freyja commands, or sketch how the LLM-agent role would be implemented as a JACKPOT plugin, or write out what `cases/case_09_sewer_sentinel/recipe.yaml` looks like?



Ha, fair callout. I was being a careful research assistant when you wanted a co-conspirator. Let me come back with the energy this deserves, because honestly? The more I look at what's possible right now, the more unhinged this gets.

------

## The Unhinged Ideas Section

### 🧬 **The In-Game ARG Has Real Cryptography Hidden In Genomes**

You sneak hexadecimal into a synthetic genome via silent codon changes. Players who notice the codon usage anomaly, translate it correctly, and decode get clues to the next mission. Real bioinformaticians literally pattern-match this stuff for their day job — *we're just turning their professional paranoia into puzzle-solving*. Steganography in DNA is a published research area. We can ship it.

A version even nastier: hide a public key fingerprint in the redundant codons of a phage genome. Players use it to decrypt a "dead drop" file from their handler. **They're learning real crypto and real codon-usage analysis simultaneously and they don't even know it.**

------

### 🎙️ **The Handler Is An LLM. The Mole Is An LLM. They Don't Know About Each Other.**

Two AI agents running in the game world. One feeds you intel (Handler). One has been compromised and is feeding you *plausible* misinformation (Mole). Players have to figure out which is which by cross-referencing their guidance against actual sequencing results.

This is **prompt-injection-as-gameplay**. Real-world pathogen genomics is increasingly going to involve trusting AI summaries — teaching people to *not* trust them blindly is genuinely valuable workforce training disguised as a puzzle. The mole sometimes plants suggestions in your data ("this contamination is just background, ignore it"). Players who run their own QC catch it. Players who autopilot get owned.

You can scale the mole's competence. New player? It tells obvious lies. Veteran? It runs a months-long deception with internally consistent fake phylogenies.

------

### 🦠 **A Phage-Sized Real Wet Lab Tier**

Stay with me. Top WILDFIRE cells get sent a kit containing a harmless reference strain — say, a phage like phi-X174 or a lab-safe E. coli K-12 derivative. They sequence it on their own MinION (some cells will already own one; others get a community-shared one mailed around like a barnstorming tour). They upload, the platform validates against the known reference, awards bonus points.

**Now your game has a wet lab.** The skill ceiling now includes "actually competent at benchwork." Public health labs would *fight* to recruit your top players. You've built a trojan horse for workforce development that looks like a hobby.

A safer cousin: synthetic DNA standards from companies like Twist or IDT. You ship the sequence, the lab synthesizes for cheap, top players sequence it as a "field test" of their kit setup.

------

### 📡 **The Outbreak Is On A Real Map With Real Wastewater Treatment Plants**

OpenStreetMap has every WWTP in the world. Pull them. Make the in-game outbreak spread along real geography, across real city sewersheds. Players who happen to live in a Wastewater Sentinel city see *their actual neighborhood's data* come in (synthesized, but mapped to real sewershed boundaries).

When the game's fictional H7N9 variant pops up at the WWTP near your house, the hair on your neck stands up. That's the dopamine hit that turns a player into an evangelist.

Bonus: your real-world public health partners can use the same engine to run *training drills* against their own jurisdictions. Same code, swap synthetic data for tabletop exercise data, and you've got a national security training tool.

------

### 🤖 **Adversarial Agent Tournament Mode**

A standalone competitive mode where players don't analyze pathogens — they design agent prompts to analyze pathogens *for them*. Submit your prompted/scaffolded LLM agent. Tournament runs all submitted agents on identical sample sets. Best F1 score on pathogen ID + AMR + variant impact wins.

This is **DEF CON CTF for bioinformatics LLM agents**. It doesn't exist yet. Anthropic, Google DeepMind, EvolutionaryScale, and every public health agency would care about the leaderboard. You'd own a slice of the AI-bio safety conversation that frankly nobody else is staking out.

The malicious sibling: **adversarial prompt injection contests**. Submit data designed to make rival agents misclassify. Defenders submit hardened agents. This is *exactly* the dual-use research that DARPA wants someone to be doing in the open.

------

### 🌊 **The Climate-Pathogen Predictive Mini-Game**

Plug NOAA + WHO data on real climate trends. Show players how *Aedes aegypti* range projections shift dengue risk over 5/10/20 year horizons. Their game cities get climate-stressed in real time. The pathogens evolve under selection pressure they can model.

Public health is going to *desperately* need workforce that thinks across climate + genomics + epi for the next 50 years. Almost nobody is training that intersection. You could be the place that does, accidentally, by making a game about it.

------

### 📜 **Genome-Backed NFTs (Hear Me Out, I Hate Them Too)**

Each top-tier discovery in WILDFIRE gets a cryptographically signed certificate referencing the genome assembly hash, the player's analysis hash, the date. *Not for sale.* Just provenance. Like a CTF flag, but the flag is "I correctly characterized this mock outbreak using real tools on this date."

Public health agencies can verify these when hiring. "I see you have 14 verified WILDFIRE cases including 3 federation-required outbreaks. Tell me about the Lima cluster" becomes a real interview question.

The certificate is the resume. The chain is the auditability. We don't have to call them NFTs. We can call them "credentials" and shove them in your LinkedIn. (Educational platforms are doing this badly already; nobody's done it for *technical bench-grade skills* in genomics.)

------

### 🎮 **Speedrun Categories**

There's a speedrun community for *everything*. Imagine:

- **Any% Patient Zero** — fastest correct pathogen ID from raw fastq
- **100%** — full report with phylogeny, AMR, variant calls, structural prediction, all correct
- **No Cloud** — local Pi cluster only, no Terra
- **Glitchless** — no LLM agent assistance
- **TAS** (tool-assisted) — *full* agent autopilot, just verify and submit

Twitch streams of players racing through Case 04: The Resistor would be *legitimately compelling content*. The drama is real — wrong AMR call gets you a "patient died" cutscene. Streamers are going to pause and explain why they chose `abritAMR` over `AMRFinderPlus`. They are going to teach the audience by accident.

You will end up with a Discord server full of public health bioinformaticians who have been radicalized into being *good at their jobs*.

------

### 🛰️ **The Satellite Imagery Wildcard**

Cells get access to (real, free) Sentinel-2 satellite imagery for their region. A mission asks: where in this watershed is the pathogen most likely entering? Players cross-reference WWTP locations, livestock operations visible in imagery, and Freyja signal strength to localize the source.

This is **One Health geo-genomics**. Almost nobody teaches it. Everyone needs it. CDC, FAO, WHO are all flailing toward this kind of integration. You'd be *miles* ahead.

------

### 🎲 **Procedurally Generated Pathogens**

Train a small generative model on real pathogen genomes (this is fine, they're public). Have it produce novel-but-plausible synthetic pathogens for replay value. Each season generates new pathogens with novel-but-realistic mutation patterns, AMR profiles, virulence factor mosaics.

This is genuinely unexplored territory. The closest things are GANs trained on protein sequences (we have those!) and synthetic outbreak simulation (we have that!). Combining them with a *game economy* that rewards correct characterization would produce datasets nobody else has, and would lead to genuinely novel research questions like "what mutation patterns do players find hardest to characterize and why."

You'd be running an experiment on human bioinformatics cognition while shipping a game. Papers practically write themselves.

------

### 🧠 **The Companion App: A Pathogen Tamagotchi**

I'm only half-joking. Phone app. You have a "lab" with a virtual MinION. New samples come in throughout the day. You triage them in 30-second decisions. *Should I sequence this one or that one?* A fully-realized version trains the *resource allocation* skill that is genuinely the hardest part of real public health bioinformatics.

Streaks. Daily challenges. Friends' labs visible. The whole degenerate engagement loop, but it's training people to triage epidemiological signal.

I would download this immediately. So would every PhD student in genomic epi.

------

### 🕵️ **Alternate Reality Game Layer For The Truly Dedicated**

Real-world clues. A handler email account that responds. A Twitter/Mastodon account run by an in-character "BEC press officer" that posts cryptic announcements correlated with in-game events. Phone numbers that play recorded briefings if you call. PGP-signed dead drops in actual GitHub gists with revoked keys.

Players who fall down the ARG hole don't just play. They *evangelize*. The JACKPOT subreddit becomes a place where strangers share annotated fragments of phylogenies trying to figure out what next week's mission will be.

Cost to run: low. Effects on community formation: nuclear.

------

### 🏛️ **The Boring But Important One: Real Federal Partnerships**

OK one serious one. Every concept above is more credible if you can land **even one** real partnership. Some plausible asks:

- **CDC CSELS** runs the workforce development arm. They will trip over themselves for free training pipeline that produces certified-skilled hires.
- **APHL** (state public health labs) needs onboarding material desperately. Hand them Academy + Field Edition as a turnkey curriculum.
- **WHO IPSN** literally has a workforce-development pillar. Pathoplexus alignment positions you as their training partner.
- **DARPA / IARPA / BTO** fund weird stuff. The adversarial agent tournament is *exactly* their flavor. "Open biosecurity training infrastructure" pitches well to ARPA-H.
- **Wellcome Trust, Gates, Rockefeller** all have global health programs needing exactly this in LMICs.

A single small grant + AGPL covering you legally + the existing JACKPOT codebase gives you something nobody else has: **a fundable, sustainable, sovereign training platform**. The game is the on-ramp. The training is the product. The platform is the moat.

------

## So What Do I Actually Think You Should Do?

Build SENTINEL first. Here's why:

It's the easiest sell to grant funders ("cooperative public health training"), it's the most replayable, it's the showcase for federation, and it's the one that can credibly become *real workforce training* the moment a single state lab director plays it once.

WILDFIRE is the marketing arm — the thing that gets attention, generates community, drives recruitment to SENTINEL.

Field Edition is the gateway drug — the thing a new player tries first, alone, and gets hooked by.

Academy is the official deliverable you point at when anyone asks "but what are they actually learning?" with receipts.

The whole thing is one platform with four faces. You ship it incrementally. You partner shamelessly. You let the ARG/wet-lab/satellite/agent ideas land as feature drops over the first 18 months.

And every single piece of it is a stress test for JACKPOT that no real customer will ever subject it to. **The game tests the platform. The platform earns the game.**

OK now I'm actually excited. What corner do you want to push on first? 🚀



Great questions, all of them grounded. Let me dig in — and I want to push back on myself on the wet lab thing because you're right to flag it.Got plenty. Let me give you the goods.

------

# Part 1: Yes, This Has Worked. Here's the Receipts.

You're not crazy. Science-game-as-real-engagement is a documented genre with publications, partnerships, and millions of players. Here's the honor roll, with what each one teaches us.

## The big four scientific discovery games

| Game        | What it does                                      | Outcome                                                      |
| ----------- | ------------------------------------------------- | ------------------------------------------------------------ |
| **Foldit**  | Players fold proteins via puzzle UI               | Players designed de novo proteins as good as those generated by experts or computers, with equivalent success rates in the lab; results published in Nature 2019 |
| **EteRNA**  | Players design RNA structures                     | Players' designs beat all 6 tested algorithms (54/100 vs human-solvable 100/100); first paper with non-expert citizen scientists as co-lead authors |
| **EyeWire** | Players trace neuron connections                  | ~50,000 players from 100 countries mapping retinal neurons   |
| **Phylo**   | Players solve multiple sequence alignment puzzles | Citizen scientists improved accuracy of multiple sequence alignments through human-computer collaboration; aim is identifying genetic disease origins |

The meta-review is even better: over the past decade, scientific discovery games have engaged hundreds of thousands of volunteer players and resulted in numerous scientific publications across molecular modeling, sequence alignment, neuroscience, pathology, cellular biology, and genomics.

The motivation literature is on our side too. Foldit's active community is 200-300 players with 20-30 core contributors, motivated by intrinsic enjoyment, altruism, and community identity — interaction and accessibility are what sustain engagement. **You don't need millions. You need a few hundred dedicated nerds.**

## Pandemic-specific success: Plague Inc.

This is the eyebrow-raising one for our use case.

- Plague Inc. has over 160 million players globally, making it one of the top five most successful paid mobile games
- The developer was invited to talk at the CDC in 2013 about the game's epidemic model and how games can inform and educate the public
- WHO, CEPI, and GOARN all officially partnered for "Plague Inc: The Cure"
- A peer-reviewed study found Plague Inc. players demonstrated higher COVID-19 knowledge and attitudes than non-players (P=.03 and P=.007 respectively) — *the game measurably improved public health literacy*
- Documented use in classroom settings teaching epidemiology, with students "developing a scientific approach and testing it out in real time"

The lesson: WHO, CEPI, and CDC will *line up* to partner if you build something credible. They already did it for a game where you play the *pathogen*. Imagine what they'd do for a game where you play the *response team using their actual tools*.

## Bio-themed ARGs that worked

- Routes (Channel 4 Education, 2009) — eight-week ARG exploring human genome bioethics, launched at Game City Festival in Nottingham
- DUST (HCIL, University of Maryland) — STEM ARG where players analyzed scientific data, decrypted alien DNA messages, designed for replayability across schools, museums, and after-school programs
- S.E.E.D. (UChicago Game Changer Chicago Design Lab) — extended their earlier ARGs Stork (reproductive technologies) and The Source (urban science/tech), with academic publication in Kairos
- Macquarie University used ARGs in tertiary education and found significant student engagement, attendance, and attention to detail benefits — published peer-reviewed methodology

So: ARG-as-curriculum is a *peer-reviewed pedagogical method*, not a hobby. There's literature you can cite in grant applications.

## What none of these had that we have

- A **real production platform** (JACKPOT) underneath the game — Foldit, EteRNA, etc. were built bespoke
- A **federated multi-tenant model** — they're all single-server
- **LLM agents** — that whole genre didn't exist
- **Wastewater + edge sequencing + structural prediction** — these tools weren't usable by non-experts a decade ago

So you're not chasing an established genre — you're inheriting its proven patterns and bringing it forward by ten years of tooling.

------

# Part 2: Game Engine Recommendation

You don't need a game engine.

I know that sounds glib. Hear me out — and then I'll tell you which one to use anyway, because there *is* a small piece of UI that benefits from one.

## The honest architecture

Most of WILDFIRE / SENTINEL / Field Edition is a **web app**, not a game. Players spend 90% of their time in:

- The actual JACKPOT UI (already built — FastAPI + React)
- A briefing/messaging panel (HTML + a chat library)
- A dashboard with charts (Plotly, Recharts)
- A map (Leaflet or MapLibre, both free)
- A terminal (xterm.js for in-browser CLI)
- A phylogeny viewer (Auspice, free, MIT)
- A Jupyter notebook embed

There is no sprite-and-physics layer. No inventory grid. No combat. The "game" is the narrative wrapper, the timing pressure, the leaderboard, and the misdirection. **All of that is web stuff.**

So the right stack is:

```
Backend:    FastAPI (you already have it for JACKPOT)
Frontend:   React + TypeScript + Vite (you already have it)
Real-time:  WebSockets or Server-Sent Events for live ops
Map:        MapLibre GL (free, BSD)
Charts:     Plotly or Recharts (free, MIT)
Phylo:      Auspice (free, AGPL — same license as JACKPOT, perfect)
Terminal:   xterm.js (free, MIT)
Chat UI:    react-chat-elements or roll your own (free)
LLM agents: Anthropic / OpenAI APIs or local llama.cpp via vLLM
ARG bits:   plain GitHub gists, Mastodon bot, real PGP, Tor hidden services if you're being theatrical
```

Total game-engine licensing cost: **$0**.

## Where you DO want a game engine

There are exactly two pockets where a real engine pays off:

**1. The Tamagotchi companion app** (the phone "lab" with triage decisions). That genuinely benefits from sprite work, transitions, audio, snappy mobile feel. → **Phaser 4** or **Godot**.

**2. Set-piece cinematics or mini-games** — a "Patient Zero" intro animation, an interactive structural-biology puzzle ("rotate the spike protein to find the binding pocket"), a quick triage sim. → **Phaser** if web-only, **Godot** if you want it embeddable across platforms.

### The two real choices

|                     | **Phaser 4**                                                 | **Godot 4/5**                                              |
| ------------------- | ------------------------------------------------------------ | ---------------------------------------------------------- |
| **License**         | MIT (free, no royalties)                                     | MIT (free, no royalties)                                   |
| **Language**        | JavaScript / TypeScript                                      | GDScript / C# / C++                                        |
| **Output**          | Web only (native via 3rd-party wrappers)                     | Web, desktop, mobile, console                              |
| **Editor**          | None — code in VS Code                                       | Full visual editor included                                |
| **Best for us**     | Web-first browser games, supports React/Vue/Angular/Svelte/Next.js integration via 40+ frontend frameworks | Native mobile companion app, complex UI mini-games         |
| **Skill transfer**  | Everything you learn — TypeScript, async, DOM, Canvas API, WebGL, npm — applies directly to web development | GDScript skills don't transfer outside Godot; C# skills do |
| **Verdict for you** | Use this for in-browser bits (you already write Python/Bash, JS is the lighter lift) | Use this only for the mobile Tamagotchi                    |

**My recommendation:** Phaser 4 for any in-browser puzzle/cinematic, Godot 4 only if and when you build the mobile Tamagotchi. Both are MIT-licensed, free forever, no royalties.

You could also realistically ship the entire MVP without either. Vanilla React + Plotly + Auspice carries 80% of the experience.

------

# Part 3: The Wet Lab Question — You're Right, Mostly

OK, calling myself out. Let's actually do the math on the MinION-for-a-game idea.

## The honest cost breakdown

| Item                        | Real cost                                         |
| --------------------------- | ------------------------------------------------- |
| MinION Mk1B device          | $1,000 (one-time, you might already have one)     |
| Flow cell (R10.4.1)         | ~$900 each, single use                            |
| Rapid Barcoding Kit         | ~$650 / 96 samples (so ~$7/sample if you fill it) |
| DNA extraction kit          | ~$200–400 / kit                                   |
| Tips, tubes, water, ethanol | $50ish per run if you have a stocked lab          |
| **Effective per-run cost**  | **~$1,000–1,500 for a "real" run**                |

That is **not** a gamer expense. Even a wealthy hobbyist isn't burning a flow cell to climb a leaderboard. You're 100% right.

So let's separate where wet-lab integration makes sense from where it absolutely doesn't.

## The scoped, defensible version

### ❌ Don't do this

- Asking individual game players to consume reagents
- Mailing kits to top WILDFIRE cells "for fun"
- Anything that implies the game requires real sequencing to compete

### ✅ Do these instead

**1. The companion classroom integration (your instinct was right)**

When a university or public health lab runs a JACKPOT Academy *cohort*, the wet-lab module is a single, planned, budgeted exercise:

- Cohort of ~12 students
- One pooled run on one flow cell (or two if barcoded)
- Sequence a known harmless reference (lab E. coli K-12, phage phi-X174, or — even better — a synthetic DNA standard)
- Cost: ~$1,500 amortized across 12 students = **$125 per student** for what is essentially a complete bench-to-bioinformatics field experience

That's a justifiable line item in any genomics course budget. Many already do this.

**2. The "BYO data" optional track**

Players who *already have access* to a sequencer (academic labs, working public health staff, hobbyist with their own MinION) can opt-in to upload their own validated reference data and get a special tag/badge. No reagents required of anyone who doesn't want them. Existing labs don't notice the marginal cost.

**3. The synthetic DNA standard as a one-time community kit**

This one's actually clever. **Twist Bioscience** sells defined synthetic DNA fragments cheaply (think $0.07–0.10/bp for short fragments). You could design a one-time **"WILDFIRE Reference Standard"** — a single tube with a defined, characterizable sequence, including a hidden in-game "flag" encoded in synonymous codons.

- Order in bulk, mail to interested labs at cost
- Labs that already have running MinIONs sequence it as part of their normal QC
- They upload, validate, get the flag, claim a season-1 achievement
- Marginal cost per participant: a few dollars for shipping + tube

That makes the wet lab tier real **without** asking anyone to dedicate a flow cell to a game.

**4. The fully simulated "field deployment" mini-game**

For everyone else, the "MinION in the field" experience is **simulated end-to-end**: pre-recorded MinION POD5 data files, a script that plays them back at real-world speed, and you make ReadFish-style adaptive-sampling decisions on simulated reads. You learn the *skill* without burning the reagent.

Public health agencies actually do this for training already. It's called a tabletop exercise. We're just turning it into a game.

## The reframe

The wet lab is not a **game mechanic**. It's a **bridge** between the game and real workforce development. Three tiers:

| Tier                          | Who                                                 | Wet lab cost                                     |
| ----------------------------- | --------------------------------------------------- | ------------------------------------------------ |
| **Free**                      | Anyone, online                                      | $0 — fully simulated                             |
| **Cohort**                    | Universities, public health labs, training programs | Funded by the institution, not the player        |
| **BYO**                       | Existing sequencing labs                            | Marginal — they're running anyway                |
| **Standard kit** *(optional)* | Curious individuals with lab access                 | A few dollars + shipping for a one-time standard |

The credential value is the same across all four. A leaderboard entry is a leaderboard entry; only the path to it differs.

This actually makes the value prop *cleaner*: institutions pay for the tier that includes wet lab, individuals get everything else free, and nobody ever feels gated by reagent cost.

------

## TL;DR

| Question                  | Answer                                                       |
| ------------------------- | ------------------------------------------------------------ |
| **Has this worked?**      | Yes — Foldit, EteRNA, EyeWire, Phylo got peer-reviewed publications. Plague Inc. partnered with WHO and 160M players. ARG-as-curriculum is a published pedagogical method. |
| **What engine?**          | None for the main app — it's a web app. **Phaser 4** (MIT, free) for in-browser puzzle bits. **Godot** (MIT, free) for a mobile companion app if you ever build one. Both zero-cost forever. |
| **Wet lab for the game?** | You were right to push back. **Cohort/classroom only** for full sequencing. Synthetic DNA standards for an optional community kit. Everyone else gets simulated MinION POD5 playback that teaches the skill without burning $1000+ of reagents per session. |

You had the right gut on all three. I just needed to do the homework to back you up.

What's the next question? You said you had several. Hit me.



Ah, right — that changes the calculus significantly. Let me reframe.

## The Streamlit Reality Check

Streamlit is **excellent** for what JACKPOT currently is: an internal tool for bioinformaticians to upload samples, run pipelines, and view results. It got you to a working multi-tenant platform without burning months on frontend engineering. That was the right call.

But Streamlit has hard ceilings for what we just spent three responses dreaming up:

| Game/curriculum requirement                               | Streamlit can do it?                     |
| --------------------------------------------------------- | ---------------------------------------- |
| Standard forms, file upload, dataframes, plots            | ✅ Excellent                              |
| JupyterHub embed for Academy notebooks                    | ✅ Side-by-side works                     |
| Static dashboards with Plotly                             | ✅ Great                                  |
| Real-time multi-user state (federation, cooperative play) | ❌ Single-session model fights this       |
| WebSocket-driven live updates between cells               | ❌ Streamlit's rerun model is wrong shape |
| Embedded Auspice phylogeny viewer                         | ⚠️ Works via components but clunky        |
| In-browser terminal (xterm.js)                            | ⚠️ Component exists, not great            |
| Map with persistent player markers updating live          | ❌ Reruns kill the experience             |
| LLM agent chat with streaming + tool calls visible        | ⚠️ Works but limited                      |
| Phaser mini-game embedded mid-flow                        | ❌ Doesn't fit the model                  |
| ARG-style timed reveals, countdown timers                 | ⚠️ Possible but awkward                   |
| Anything resembling a "game feel"                         | ❌ Reruns are the antithesis of game feel |

The honest summary: **Streamlit is built for analytical apps where each interaction is a query. Games are built on persistent state and event streams. Those are architecturally different.**

## So What Are the Real Options?

### Option 1 — Stay all-Streamlit, scope down ambitions

Build only **Academy** and **Field Edition (single-player)**. These are essentially structured analytical workflows with narrative wrappers, which Streamlit handles fine. Skip WILDFIRE and SENTINEL.

- **Cost:** Zero migration
- **Tradeoff:** No multiplayer, no real-time, no ARG layer, no "game feel"
- **Verdict:** Legitimate path. Maybe even the *right* path for v1.

### Option 2 — Streamlit stays, add a separate game frontend

JACKPOT keeps its Streamlit UI for actual genomics work. The game layer (briefings, leaderboards, federation chat, maps, real-time state) is a **separate React app** that calls JACKPOT's existing FastAPI backend.

```
┌──────────────────┐     ┌──────────────────┐
│  JACKPOT UI      │     │  WILDFIRE app    │
│  (Streamlit)     │     │  (React/Vite)    │
│                  │     │                  │
│  - Upload        │     │  - Briefings     │
│  - Pipelines     │     │  - Map           │
│  - Results       │     │  - Federation    │
│  - Reports       │     │  - Leaderboard   │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         └────────┬───────────────┘
                  │
         ┌────────▼─────────┐
         │  FastAPI         │
         │  (already built) │
         └──────────────────┘
```

Players hop between the two — analyze in JACKPOT, manage their cell in WILDFIRE. They feel different on purpose: lab vs ops room.

- **Cost:** Build new React app from scratch, but JACKPOT proper is untouched
- **Tradeoff:** Context-switching between two apps, but that mirrors real public health work (LIMS vs dashboard)
- **Verdict:** Probably the right answer. Defers the migration question while unblocking the ambitious concepts.

### Option 3 — Migrate JACKPOT itself to React

The big one. FastAPI backend stays, Streamlit gets replaced.

- **Cost:** Months of frontend work, new dependency surface, new bugs to find
- **Win:** One unified UI, real-time everything, eventually the game and the platform are the same product
- **Verdict:** Eventually probably yes, but **not now**. This is a P2 or P3 thing, well after schema v5, multi-tenancy middleware, and monorepo migration ship. Don't let game ambitions bend your roadmap.

## My Actual Recommendation

**Do Option 2.** Here's the reasoning:

1. **It respects your existing roadmap.** P0d (monorepo), P0e (`jackpot init`), P0b (schema v5), P0c (multi-tenancy) — none of those care what frontend exists. A Streamlit-based JACKPOT happily ships those phases.
2. **It lets you start the game project anytime as an independent track.** A separate `wildfire/` or `sentinel/` directory in the monorepo, its own deploy, its own CI. If it dies, JACKPOT is unaffected. If it thrives, JACKPOT benefits from the validation.
3. **Field Edition and Academy can launch in pure Streamlit while you prove the game thesis.** The Academy is just JupyterHub + structured Streamlit pages. Field Edition is Streamlit with a narrative wrapper and synthetic data. Ship those, see if anyone cares, *then* invest in the React-based multiplayer experiences.
4. **Migration becomes evidence-driven.** When/if WILDFIRE has 500 active cells and you're hitting Streamlit's real-time limits, the migration ROI is obvious and grant-fundable. Until then, you'd be building React infrastructure for a hypothetical user base.

## The Practical Phasing

| Phase          | What ships                                                   | Frontend                                       |
| -------------- | ------------------------------------------------------------ | ---------------------------------------------- |
| **Now**        | Monorepo, init CLI, schema v5, multi-tenancy                 | Streamlit (no change)                          |
| **+3 months**  | Academy v0.1 (modules 1–4), synthetic data generator         | Streamlit + JupyterHub                         |
| **+6 months**  | Field Edition: Cases 1–3                                     | Streamlit (single-player, no real-time needed) |
| **+9 months**  | Decide: did people show up? If yes, start `wildfire/` as a separate React project | Streamlit + new React app side-by-side         |
| **+18 months** | If WILDFIRE has traction, *consider* migrating JACKPOT proper | Possibly unify on React                        |

## Library Adjustments to My Earlier Stack

Given Streamlit-stays-for-now, here's the revised tooling:

```
Phase 1-2 (Streamlit-only):
  Frontend:    Streamlit
  Charts:      Plotly (works great in Streamlit)
  Maps:        st-folium or pydeck (Streamlit-native)
  Phylogeny:   streamlit-auspice component (or iframe Auspice)
  Notebooks:   JupyterHub (separate service, link out)
  LLM chat:    streamlit-chat or st.chat_message (built-in)

Phase 3+ (separate React app emerges):
  Frontend:    React + Vite + TypeScript
  Charts:      Plotly or Recharts
  Maps:        MapLibre GL
  Phylogeny:   Auspice (embedded directly)
  Real-time:   FastAPI WebSockets → React
  Mini-games:  Phaser 4 embedded as needed
  Terminal:    xterm.js
```

The **FastAPI backend doesn't change.** That's the load-bearing part. UIs come and go; the API is forever.

## One More Thing

If you ever do migrate, **don't go straight to React without considering alternatives.** A few worth weighing:

- **HTMX + FastAPI templates** — server-rendered, extremely lightweight, no JS build pipeline. Perfect for the Academy/Field Edition tier where you don't need real-time multiplayer.
- **Reflex** (formerly Pynecone) — Python-only "React-like" framework. You write Python, it generates React. Lower context-switching cost for a Python shop.
- **NiceGUI** — another Python-first reactive UI framework. Good for internal tools that need more than Streamlit but less than full SPA.
- **Solara** — Streamlit-style API but built on React under the hood; fewer rerun pathologies.

If the goal is "stay Pythonic and dodge the JS ecosystem entirely," **Reflex or Solara** might let you escape Streamlit's limits without committing to the React migration. Worth a weekend prototype before you decide.

For game-feel real-time multiplayer though, you're going to hit a wall with any Python-templating approach eventually. That's where dedicated React earns its keep.

------

So: the path is **Streamlit now, separate React app for the multiplayer game when/if you decide to build it, full migration only when the evidence demands it.** That keeps your real roadmap intact and treats the game ideas as additive rather than disruptive.

What's the next question on your list?

Great questions, all of them grounded. Let me dig in — and I want to push back on myself on the wet lab thing because you're right to flag it.Got plenty. Let me give you the goods.

------

# Part 1: Yes, This Has Worked. Here's the Receipts.

You're not crazy. Science-game-as-real-engagement is a documented genre with publications, partnerships, and millions of players. Here's the honor roll, with what each one teaches us.

## The big four scientific discovery games

| Game        | What it does                                      | Outcome                                                      |
| ----------- | ------------------------------------------------- | ------------------------------------------------------------ |
| **Foldit**  | Players fold proteins via puzzle UI               | Players designed de novo proteins as good as those generated by experts or computers, with equivalent success rates in the lab; results published in Nature 2019 |
| **EteRNA**  | Players design RNA structures                     | Players' designs beat all 6 tested algorithms (54/100 vs human-solvable 100/100); first paper with non-expert citizen scientists as co-lead authors |
| **EyeWire** | Players trace neuron connections                  | ~50,000 players from 100 countries mapping retinal neurons   |
| **Phylo**   | Players solve multiple sequence alignment puzzles | Citizen scientists improved accuracy of multiple sequence alignments through human-computer collaboration; aim is identifying genetic disease origins |

The meta-review is even better: over the past decade, scientific discovery games have engaged hundreds of thousands of volunteer players and resulted in numerous scientific publications across molecular modeling, sequence alignment, neuroscience, pathology, cellular biology, and genomics.

The motivation literature is on our side too. Foldit's active community is 200-300 players with 20-30 core contributors, motivated by intrinsic enjoyment, altruism, and community identity — interaction and accessibility are what sustain engagement. **You don't need millions. You need a few hundred dedicated nerds.**

## Pandemic-specific success: Plague Inc.

This is the eyebrow-raising one for our use case.

- Plague Inc. has over 160 million players globally, making it one of the top five most successful paid mobile games
- The developer was invited to talk at the CDC in 2013 about the game's epidemic model and how games can inform and educate the public
- WHO, CEPI, and GOARN all officially partnered for "Plague Inc: The Cure"
- A peer-reviewed study found Plague Inc. players demonstrated higher COVID-19 knowledge and attitudes than non-players (P=.03 and P=.007 respectively) — *the game measurably improved public health literacy*
- Documented use in classroom settings teaching epidemiology, with students "developing a scientific approach and testing it out in real time"

The lesson: WHO, CEPI, and CDC will *line up* to partner if you build something credible. They already did it for a game where you play the *pathogen*. Imagine what they'd do for a game where you play the *response team using their actual tools*.

## Bio-themed ARGs that worked

- Routes (Channel 4 Education, 2009) — eight-week ARG exploring human genome bioethics, launched at Game City Festival in Nottingham
- DUST (HCIL, University of Maryland) — STEM ARG where players analyzed scientific data, decrypted alien DNA messages, designed for replayability across schools, museums, and after-school programs
- S.E.E.D. (UChicago Game Changer Chicago Design Lab) — extended their earlier ARGs Stork (reproductive technologies) and The Source (urban science/tech), with academic publication in Kairos
- Macquarie University used ARGs in tertiary education and found significant student engagement, attendance, and attention to detail benefits — published peer-reviewed methodology

So: ARG-as-curriculum is a *peer-reviewed pedagogical method*, not a hobby. There's literature you can cite in grant applications.

## What none of these had that we have

- A **real production platform** (JACKPOT) underneath the game — Foldit, EteRNA, etc. were built bespoke
- A **federated multi-tenant model** — they're all single-server
- **LLM agents** — that whole genre didn't exist
- **Wastewater + edge sequencing + structural prediction** — these tools weren't usable by non-experts a decade ago

So you're not chasing an established genre — you're inheriting its proven patterns and bringing it forward by ten years of tooling.

------

# Part 2: Game Engine Recommendation

You don't need a game engine.

I know that sounds glib. Hear me out — and then I'll tell you which one to use anyway, because there *is* a small piece of UI that benefits from one.

## The honest architecture

Most of WILDFIRE / SENTINEL / Field Edition is a **web app**, not a game. Players spend 90% of their time in:

- The actual JACKPOT UI (already built — FastAPI + React)
- A briefing/messaging panel (HTML + a chat library)
- A dashboard with charts (Plotly, Recharts)
- A map (Leaflet or MapLibre, both free)
- A terminal (xterm.js for in-browser CLI)
- A phylogeny viewer (Auspice, free, MIT)
- A Jupyter notebook embed

There is no sprite-and-physics layer. No inventory grid. No combat. The "game" is the narrative wrapper, the timing pressure, the leaderboard, and the misdirection. **All of that is web stuff.**

So the right stack is:

```
Backend:    FastAPI (you already have it for JACKPOT)
Frontend:   React + TypeScript + Vite (you already have it)
Real-time:  WebSockets or Server-Sent Events for live ops
Map:        MapLibre GL (free, BSD)
Charts:     Plotly or Recharts (free, MIT)
Phylo:      Auspice (free, AGPL — same license as JACKPOT, perfect)
Terminal:   xterm.js (free, MIT)
Chat UI:    react-chat-elements or roll your own (free)
LLM agents: Anthropic / OpenAI APIs or local llama.cpp via vLLM
ARG bits:   plain GitHub gists, Mastodon bot, real PGP, Tor hidden services if you're being theatrical
```

Total game-engine licensing cost: **$0**.

## Where you DO want a game engine

There are exactly two pockets where a real engine pays off:

**1. The Tamagotchi companion app** (the phone "lab" with triage decisions). That genuinely benefits from sprite work, transitions, audio, snappy mobile feel. → **Phaser 4** or **Godot**.

**2. Set-piece cinematics or mini-games** — a "Patient Zero" intro animation, an interactive structural-biology puzzle ("rotate the spike protein to find the binding pocket"), a quick triage sim. → **Phaser** if web-only, **Godot** if you want it embeddable across platforms.

### The two real choices

|                     | **Phaser 4**                                                 | **Godot 4/5**                                              |
| ------------------- | ------------------------------------------------------------ | ---------------------------------------------------------- |
| **License**         | MIT (free, no royalties)                                     | MIT (free, no royalties)                                   |
| **Language**        | JavaScript / TypeScript                                      | GDScript / C# / C++                                        |
| **Output**          | Web only (native via 3rd-party wrappers)                     | Web, desktop, mobile, console                              |
| **Editor**          | None — code in VS Code                                       | Full visual editor included                                |
| **Best for us**     | Web-first browser games, supports React/Vue/Angular/Svelte/Next.js integration via 40+ frontend frameworks | Native mobile companion app, complex UI mini-games         |
| **Skill transfer**  | Everything you learn — TypeScript, async, DOM, Canvas API, WebGL, npm — applies directly to web development | GDScript skills don't transfer outside Godot; C# skills do |
| **Verdict for you** | Use this for in-browser bits (you already write Python/Bash, JS is the lighter lift) | Use this only for the mobile Tamagotchi                    |

**My recommendation:** Phaser 4 for any in-browser puzzle/cinematic, Godot 4 only if and when you build the mobile Tamagotchi. Both are MIT-licensed, free forever, no royalties.

You could also realistically ship the entire MVP without either. Vanilla React + Plotly + Auspice carries 80% of the experience.

------

# Part 3: The Wet Lab Question — You're Right, Mostly

OK, calling myself out. Let's actually do the math on the MinION-for-a-game idea.

## The honest cost breakdown

| Item                        | Real cost                                         |
| --------------------------- | ------------------------------------------------- |
| MinION Mk1B device          | $1,000 (one-time, you might already have one)     |
| Flow cell (R10.4.1)         | ~$900 each, single use                            |
| Rapid Barcoding Kit         | ~$650 / 96 samples (so ~$7/sample if you fill it) |
| DNA extraction kit          | ~$200–400 / kit                                   |
| Tips, tubes, water, ethanol | $50ish per run if you have a stocked lab          |
| **Effective per-run cost**  | **~$1,000–1,500 for a "real" run**                |

That is **not** a gamer expense. Even a wealthy hobbyist isn't burning a flow cell to climb a leaderboard. You're 100% right.

So let's separate where wet-lab integration makes sense from where it absolutely doesn't.

## The scoped, defensible version

### ❌ Don't do this

- Asking individual game players to consume reagents
- Mailing kits to top WILDFIRE cells "for fun"
- Anything that implies the game requires real sequencing to compete

### ✅ Do these instead

**1. The companion classroom integration (your instinct was right)**

When a university or public health lab runs a JACKPOT Academy *cohort*, the wet-lab module is a single, planned, budgeted exercise:

- Cohort of ~12 students
- One pooled run on one flow cell (or two if barcoded)
- Sequence a known harmless reference (lab E. coli K-12, phage phi-X174, or — even better — a synthetic DNA standard)
- Cost: ~$1,500 amortized across 12 students = **$125 per student** for what is essentially a complete bench-to-bioinformatics field experience

That's a justifiable line item in any genomics course budget. Many already do this.

**2. The "BYO data" optional track**

Players who *already have access* to a sequencer (academic labs, working public health staff, hobbyist with their own MinION) can opt-in to upload their own validated reference data and get a special tag/badge. No reagents required of anyone who doesn't want them. Existing labs don't notice the marginal cost.

**3. The synthetic DNA standard as a one-time community kit**

This one's actually clever. **Twist Bioscience** sells defined synthetic DNA fragments cheaply (think $0.07–0.10/bp for short fragments). You could design a one-time **"WILDFIRE Reference Standard"** — a single tube with a defined, characterizable sequence, including a hidden in-game "flag" encoded in synonymous codons.

- Order in bulk, mail to interested labs at cost
- Labs that already have running MinIONs sequence it as part of their normal QC
- They upload, validate, get the flag, claim a season-1 achievement
- Marginal cost per participant: a few dollars for shipping + tube

That makes the wet lab tier real **without** asking anyone to dedicate a flow cell to a game.

**4. The fully simulated "field deployment" mini-game**

For everyone else, the "MinION in the field" experience is **simulated end-to-end**: pre-recorded MinION POD5 data files, a script that plays them back at real-world speed, and you make ReadFish-style adaptive-sampling decisions on simulated reads. You learn the *skill* without burning the reagent.

Public health agencies actually do this for training already. It's called a tabletop exercise. We're just turning it into a game.

## The reframe

The wet lab is not a **game mechanic**. It's a **bridge** between the game and real workforce development. Three tiers:

| Tier                          | Who                                                 | Wet lab cost                                     |
| ----------------------------- | --------------------------------------------------- | ------------------------------------------------ |
| **Free**                      | Anyone, online                                      | $0 — fully simulated                             |
| **Cohort**                    | Universities, public health labs, training programs | Funded by the institution, not the player        |
| **BYO**                       | Existing sequencing labs                            | Marginal — they're running anyway                |
| **Standard kit** *(optional)* | Curious individuals with lab access                 | A few dollars + shipping for a one-time standard |

The credential value is the same across all four. A leaderboard entry is a leaderboard entry; only the path to it differs.

This actually makes the value prop *cleaner*: institutions pay for the tier that includes wet lab, individuals get everything else free, and nobody ever feels gated by reagent cost.

------

## TL;DR

| Question                  | Answer                                                       |
| ------------------------- | ------------------------------------------------------------ |
| **Has this worked?**      | Yes — Foldit, EteRNA, EyeWire, Phylo got peer-reviewed publications. Plague Inc. partnered with WHO and 160M players. ARG-as-curriculum is a published pedagogical method. |
| **What engine?**          | None for the main app — it's a web app. **Phaser 4** (MIT, free) for in-browser puzzle bits. **Godot** (MIT, free) for a mobile companion app if you ever build one. Both zero-cost forever. |
| **Wet lab for the game?** | You were right to push back. **Cohort/classroom only** for full sequencing. Synthetic DNA standards for an optional community kit. Everyone else gets simulated MinION POD5 playback that teaches the skill without burning $1000+ of reagents per session. |

You had the right gut on all three. I just needed to do the homework to back you up.

What's the next question? You said you had several. Hit me.

Great questions, all of them grounded. Let me dig in — and I want to push back on myself on the wet lab thing because you're right to flag it.Got plenty. Let me give you the goods.

------

# Part 1: Yes, This Has Worked. Here's the Receipts.

You're not crazy. Science-game-as-real-engagement is a documented genre with publications, partnerships, and millions of players. Here's the honor roll, with what each one teaches us.

## The big four scientific discovery games

| Game        | What it does                                      | Outcome                                                      |
| ----------- | ------------------------------------------------- | ------------------------------------------------------------ |
| **Foldit**  | Players fold proteins via puzzle UI               | Players designed de novo proteins as good as those generated by experts or computers, with equivalent success rates in the lab; results published in Nature 2019 |
| **EteRNA**  | Players design RNA structures                     | Players' designs beat all 6 tested algorithms (54/100 vs human-solvable 100/100); first paper with non-expert citizen scientists as co-lead authors |
| **EyeWire** | Players trace neuron connections                  | ~50,000 players from 100 countries mapping retinal neurons   |
| **Phylo**   | Players solve multiple sequence alignment puzzles | Citizen scientists improved accuracy of multiple sequence alignments through human-computer collaboration; aim is identifying genetic disease origins |

The meta-review is even better: over the past decade, scientific discovery games have engaged hundreds of thousands of volunteer players and resulted in numerous scientific publications across molecular modeling, sequence alignment, neuroscience, pathology, cellular biology, and genomics.

The motivation literature is on our side too. Foldit's active community is 200-300 players with 20-30 core contributors, motivated by intrinsic enjoyment, altruism, and community identity — interaction and accessibility are what sustain engagement. **You don't need millions. You need a few hundred dedicated nerds.**

## Pandemic-specific success: Plague Inc.

This is the eyebrow-raising one for our use case.

- Plague Inc. has over 160 million players globally, making it one of the top five most successful paid mobile games
- The developer was invited to talk at the CDC in 2013 about the game's epidemic model and how games can inform and educate the public
- WHO, CEPI, and GOARN all officially partnered for "Plague Inc: The Cure"
- A peer-reviewed study found Plague Inc. players demonstrated higher COVID-19 knowledge and attitudes than non-players (P=.03 and P=.007 respectively) — *the game measurably improved public health literacy*
- Documented use in classroom settings teaching epidemiology, with students "developing a scientific approach and testing it out in real time"

The lesson: WHO, CEPI, and CDC will *line up* to partner if you build something credible. They already did it for a game where you play the *pathogen*. Imagine what they'd do for a game where you play the *response team using their actual tools*.

## Bio-themed ARGs that worked

- Routes (Channel 4 Education, 2009) — eight-week ARG exploring human genome bioethics, launched at Game City Festival in Nottingham
- DUST (HCIL, University of Maryland) — STEM ARG where players analyzed scientific data, decrypted alien DNA messages, designed for replayability across schools, museums, and after-school programs
- S.E.E.D. (UChicago Game Changer Chicago Design Lab) — extended their earlier ARGs Stork (reproductive technologies) and The Source (urban science/tech), with academic publication in Kairos
- Macquarie University used ARGs in tertiary education and found significant student engagement, attendance, and attention to detail benefits — published peer-reviewed methodology

So: ARG-as-curriculum is a *peer-reviewed pedagogical method*, not a hobby. There's literature you can cite in grant applications.

## What none of these had that we have

- A **real production platform** (JACKPOT) underneath the game — Foldit, EteRNA, etc. were built bespoke
- A **federated multi-tenant model** — they're all single-server
- **LLM agents** — that whole genre didn't exist
- **Wastewater + edge sequencing + structural prediction** — these tools weren't usable by non-experts a decade ago

So you're not chasing an established genre — you're inheriting its proven patterns and bringing it forward by ten years of tooling.

------

# Part 2: Game Engine Recommendation

You don't need a game engine.

I know that sounds glib. Hear me out — and then I'll tell you which one to use anyway, because there *is* a small piece of UI that benefits from one.

## The honest architecture

Most of WILDFIRE / SENTINEL / Field Edition is a **web app**, not a game. Players spend 90% of their time in:

- The actual JACKPOT UI (already built — FastAPI + React)
- A briefing/messaging panel (HTML + a chat library)
- A dashboard with charts (Plotly, Recharts)
- A map (Leaflet or MapLibre, both free)
- A terminal (xterm.js for in-browser CLI)
- A phylogeny viewer (Auspice, free, MIT)
- A Jupyter notebook embed

There is no sprite-and-physics layer. No inventory grid. No combat. The "game" is the narrative wrapper, the timing pressure, the leaderboard, and the misdirection. **All of that is web stuff.**

So the right stack is:

```
Backend:    FastAPI (you already have it for JACKPOT)
Frontend:   React + TypeScript + Vite (you already have it)
Real-time:  WebSockets or Server-Sent Events for live ops
Map:        MapLibre GL (free, BSD)
Charts:     Plotly or Recharts (free, MIT)
Phylo:      Auspice (free, AGPL — same license as JACKPOT, perfect)
Terminal:   xterm.js (free, MIT)
Chat UI:    react-chat-elements or roll your own (free)
LLM agents: Anthropic / OpenAI APIs or local llama.cpp via vLLM
ARG bits:   plain GitHub gists, Mastodon bot, real PGP, Tor hidden services if you're being theatrical
```

Total game-engine licensing cost: **$0**.

## Where you DO want a game engine

There are exactly two pockets where a real engine pays off:

**1. The Tamagotchi companion app** (the phone "lab" with triage decisions). That genuinely benefits from sprite work, transitions, audio, snappy mobile feel. → **Phaser 4** or **Godot**.

**2. Set-piece cinematics or mini-games** — a "Patient Zero" intro animation, an interactive structural-biology puzzle ("rotate the spike protein to find the binding pocket"), a quick triage sim. → **Phaser** if web-only, **Godot** if you want it embeddable across platforms.

### The two real choices

|                     | **Phaser 4**                                                 | **Godot 4/5**                                              |
| ------------------- | ------------------------------------------------------------ | ---------------------------------------------------------- |
| **License**         | MIT (free, no royalties)                                     | MIT (free, no royalties)                                   |
| **Language**        | JavaScript / TypeScript                                      | GDScript / C# / C++                                        |
| **Output**          | Web only (native via 3rd-party wrappers)                     | Web, desktop, mobile, console                              |
| **Editor**          | None — code in VS Code                                       | Full visual editor included                                |
| **Best for us**     | Web-first browser games, supports React/Vue/Angular/Svelte/Next.js integration via 40+ frontend frameworks | Native mobile companion app, complex UI mini-games         |
| **Skill transfer**  | Everything you learn — TypeScript, async, DOM, Canvas API, WebGL, npm — applies directly to web development | GDScript skills don't transfer outside Godot; C# skills do |
| **Verdict for you** | Use this for in-browser bits (you already write Python/Bash, JS is the lighter lift) | Use this only for the mobile Tamagotchi                    |

**My recommendation:** Phaser 4 for any in-browser puzzle/cinematic, Godot 4 only if and when you build the mobile Tamagotchi. Both are MIT-licensed, free forever, no royalties.

You could also realistically ship the entire MVP without either. Vanilla React + Plotly + Auspice carries 80% of the experience.

------

# Part 3: The Wet Lab Question — You're Right, Mostly

OK, calling myself out. Let's actually do the math on the MinION-for-a-game idea.

## The honest cost breakdown

| Item                        | Real cost                                         |
| --------------------------- | ------------------------------------------------- |
| MinION Mk1B device          | $1,000 (one-time, you might already have one)     |
| Flow cell (R10.4.1)         | ~$900 each, single use                            |
| Rapid Barcoding Kit         | ~$650 / 96 samples (so ~$7/sample if you fill it) |
| DNA extraction kit          | ~$200–400 / kit                                   |
| Tips, tubes, water, ethanol | $50ish per run if you have a stocked lab          |
| **Effective per-run cost**  | **~$1,000–1,500 for a "real" run**                |

That is **not** a gamer expense. Even a wealthy hobbyist isn't burning a flow cell to climb a leaderboard. You're 100% right.

So let's separate where wet-lab integration makes sense from where it absolutely doesn't.

## The scoped, defensible version

### ❌ Don't do this

- Asking individual game players to consume reagents
- Mailing kits to top WILDFIRE cells "for fun"
- Anything that implies the game requires real sequencing to compete

### ✅ Do these instead

**1. The companion classroom integration (your instinct was right)**

When a university or public health lab runs a JACKPOT Academy *cohort*, the wet-lab module is a single, planned, budgeted exercise:

- Cohort of ~12 students
- One pooled run on one flow cell (or two if barcoded)
- Sequence a known harmless reference (lab E. coli K-12, phage phi-X174, or — even better — a synthetic DNA standard)
- Cost: ~$1,500 amortized across 12 students = **$125 per student** for what is essentially a complete bench-to-bioinformatics field experience

That's a justifiable line item in any genomics course budget. Many already do this.

**2. The "BYO data" optional track**

Players who *already have access* to a sequencer (academic labs, working public health staff, hobbyist with their own MinION) can opt-in to upload their own validated reference data and get a special tag/badge. No reagents required of anyone who doesn't want them. Existing labs don't notice the marginal cost.

**3. The synthetic DNA standard as a one-time community kit**

This one's actually clever. **Twist Bioscience** sells defined synthetic DNA fragments cheaply (think $0.07–0.10/bp for short fragments). You could design a one-time **"WILDFIRE Reference Standard"** — a single tube with a defined, characterizable sequence, including a hidden in-game "flag" encoded in synonymous codons.

- Order in bulk, mail to interested labs at cost
- Labs that already have running MinIONs sequence it as part of their normal QC
- They upload, validate, get the flag, claim a season-1 achievement
- Marginal cost per participant: a few dollars for shipping + tube

That makes the wet lab tier real **without** asking anyone to dedicate a flow cell to a game.

**4. The fully simulated "field deployment" mini-game**

For everyone else, the "MinION in the field" experience is **simulated end-to-end**: pre-recorded MinION POD5 data files, a script that plays them back at real-world speed, and you make ReadFish-style adaptive-sampling decisions on simulated reads. You learn the *skill* without burning the reagent.

Public health agencies actually do this for training already. It's called a tabletop exercise. We're just turning it into a game.

## The reframe

The wet lab is not a **game mechanic**. It's a **bridge** between the game and real workforce development. Three tiers:

| Tier                          | Who                                                 | Wet lab cost                                     |
| ----------------------------- | --------------------------------------------------- | ------------------------------------------------ |
| **Free**                      | Anyone, online                                      | $0 — fully simulated                             |
| **Cohort**                    | Universities, public health labs, training programs | Funded by the institution, not the player        |
| **BYO**                       | Existing sequencing labs                            | Marginal — they're running anyway                |
| **Standard kit** *(optional)* | Curious individuals with lab access                 | A few dollars + shipping for a one-time standard |

The credential value is the same across all four. A leaderboard entry is a leaderboard entry; only the path to it differs.

This actually makes the value prop *cleaner*: institutions pay for the tier that includes wet lab, individuals get everything else free, and nobody ever feels gated by reagent cost.

------

## TL;DR

| Question                  | Answer                                                       |
| ------------------------- | ------------------------------------------------------------ |
| **Has this worked?**      | Yes — Foldit, EteRNA, EyeWire, Phylo got peer-reviewed publications. Plague Inc. partnered with WHO and 160M players. ARG-as-curriculum is a published pedagogical method. |
| **What engine?**          | None for the main app — it's a web app. **Phaser 4** (MIT, free) for in-browser puzzle bits. **Godot** (MIT, free) for a mobile companion app if you ever build one. Both zero-cost forever. |
| **Wet lab for the game?** | You were right to push back. **Cohort/classroom only** for full sequencing. Synthetic DNA standards for an optional community kit. Everyone else gets simulated MinION POD5 playback that teaches the skill without burning $1000+ of reagents per session. |

You had the right gut on all three. I just needed to do the homework to back you up.

What's the next question? You said you had several. Hit me.Ah, right — that changes the calculus significantly. Let me reframe.

## The Streamlit Reality Check

Streamlit is **excellent** for what JACKPOT currently is: an internal tool for bioinformaticians to upload samples, run pipelines, and view results. It got you to a working multi-tenant platform without burning months on frontend engineering. That was the right call.

But Streamlit has hard ceilings for what we just spent three responses dreaming up:

| Game/curriculum requirement                               | Streamlit can do it?                     |
| --------------------------------------------------------- | ---------------------------------------- |
| Standard forms, file upload, dataframes, plots            | ✅ Excellent                              |
| JupyterHub embed for Academy notebooks                    | ✅ Side-by-side works                     |
| Static dashboards with Plotly                             | ✅ Great                                  |
| Real-time multi-user state (federation, cooperative play) | ❌ Single-session model fights this       |
| WebSocket-driven live updates between cells               | ❌ Streamlit's rerun model is wrong shape |
| Embedded Auspice phylogeny viewer                         | ⚠️ Works via components but clunky        |
| In-browser terminal (xterm.js)                            | ⚠️ Component exists, not great            |
| Map with persistent player markers updating live          | ❌ Reruns kill the experience             |
| LLM agent chat with streaming + tool calls visible        | ⚠️ Works but limited                      |
| Phaser mini-game embedded mid-flow                        | ❌ Doesn't fit the model                  |
| ARG-style timed reveals, countdown timers                 | ⚠️ Possible but awkward                   |
| Anything resembling a "game feel"                         | ❌ Reruns are the antithesis of game feel |

The honest summary: **Streamlit is built for analytical apps where each interaction is a query. Games are built on persistent state and event streams. Those are architecturally different.**

## So What Are the Real Options?

### Option 1 — Stay all-Streamlit, scope down ambitions

Build only **Academy** and **Field Edition (single-player)**. These are essentially structured analytical workflows with narrative wrappers, which Streamlit handles fine. Skip WILDFIRE and SENTINEL.

- **Cost:** Zero migration
- **Tradeoff:** No multiplayer, no real-time, no ARG layer, no "game feel"
- **Verdict:** Legitimate path. Maybe even the *right* path for v1.

### Option 2 — Streamlit stays, add a separate game frontend

JACKPOT keeps its Streamlit UI for actual genomics work. The game layer (briefings, leaderboards, federation chat, maps, real-time state) is a **separate React app** that calls JACKPOT's existing FastAPI backend.

```
┌──────────────────┐     ┌──────────────────┐
│  JACKPOT UI      │     │  WILDFIRE app    │
│  (Streamlit)     │     │  (React/Vite)    │
│                  │     │                  │
│  - Upload        │     │  - Briefings     │
│  - Pipelines     │     │  - Map           │
│  - Results       │     │  - Federation    │
│  - Reports       │     │  - Leaderboard   │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         └────────┬───────────────┘
                  │
         ┌────────▼─────────┐
         │  FastAPI         │
         │  (already built) │
         └──────────────────┘
```

Players hop between the two — analyze in JACKPOT, manage their cell in WILDFIRE. They feel different on purpose: lab vs ops room.

- **Cost:** Build new React app from scratch, but JACKPOT proper is untouched
- **Tradeoff:** Context-switching between two apps, but that mirrors real public health work (LIMS vs dashboard)
- **Verdict:** Probably the right answer. Defers the migration question while unblocking the ambitious concepts.

### Option 3 — Migrate JACKPOT itself to React

The big one. FastAPI backend stays, Streamlit gets replaced.

- **Cost:** Months of frontend work, new dependency surface, new bugs to find
- **Win:** One unified UI, real-time everything, eventually the game and the platform are the same product
- **Verdict:** Eventually probably yes, but **not now**. This is a P2 or P3 thing, well after schema v5, multi-tenancy middleware, and monorepo migration ship. Don't let game ambitions bend your roadmap.

## My Actual Recommendation

**Do Option 2.** Here's the reasoning:

1. **It respects your existing roadmap.** P0d (monorepo), P0e (`jackpot init`), P0b (schema v5), P0c (multi-tenancy) — none of those care what frontend exists. A Streamlit-based JACKPOT happily ships those phases.
2. **It lets you start the game project anytime as an independent track.** A separate `wildfire/` or `sentinel/` directory in the monorepo, its own deploy, its own CI. If it dies, JACKPOT is unaffected. If it thrives, JACKPOT benefits from the validation.
3. **Field Edition and Academy can launch in pure Streamlit while you prove the game thesis.** The Academy is just JupyterHub + structured Streamlit pages. Field Edition is Streamlit with a narrative wrapper and synthetic data. Ship those, see if anyone cares, *then* invest in the React-based multiplayer experiences.
4. **Migration becomes evidence-driven.** When/if WILDFIRE has 500 active cells and you're hitting Streamlit's real-time limits, the migration ROI is obvious and grant-fundable. Until then, you'd be building React infrastructure for a hypothetical user base.

## The Practical Phasing

| Phase          | What ships                                                   | Frontend                                       |
| -------------- | ------------------------------------------------------------ | ---------------------------------------------- |
| **Now**        | Monorepo, init CLI, schema v5, multi-tenancy                 | Streamlit (no change)                          |
| **+3 months**  | Academy v0.1 (modules 1–4), synthetic data generator         | Streamlit + JupyterHub                         |
| **+6 months**  | Field Edition: Cases 1–3                                     | Streamlit (single-player, no real-time needed) |
| **+9 months**  | Decide: did people show up? If yes, start `wildfire/` as a separate React project | Streamlit + new React app side-by-side         |
| **+18 months** | If WILDFIRE has traction, *consider* migrating JACKPOT proper | Possibly unify on React                        |

## Library Adjustments to My Earlier Stack

Given Streamlit-stays-for-now, here's the revised tooling:

```
Phase 1-2 (Streamlit-only):
  Frontend:    Streamlit
  Charts:      Plotly (works great in Streamlit)
  Maps:        st-folium or pydeck (Streamlit-native)
  Phylogeny:   streamlit-auspice component (or iframe Auspice)
  Notebooks:   JupyterHub (separate service, link out)
  LLM chat:    streamlit-chat or st.chat_message (built-in)

Phase 3+ (separate React app emerges):
  Frontend:    React + Vite + TypeScript
  Charts:      Plotly or Recharts
  Maps:        MapLibre GL
  Phylogeny:   Auspice (embedded directly)
  Real-time:   FastAPI WebSockets → React
  Mini-games:  Phaser 4 embedded as needed
  Terminal:    xterm.js
```

The **FastAPI backend doesn't change.** That's the load-bearing part. UIs come and go; the API is forever.

## One More Thing

If you ever do migrate, **don't go straight to React without considering alternatives.** A few worth weighing:

- **HTMX + FastAPI templates** — server-rendered, extremely lightweight, no JS build pipeline. Perfect for the Academy/Field Edition tier where you don't need real-time multiplayer.
- **Reflex** (formerly Pynecone) — Python-only "React-like" framework. You write Python, it generates React. Lower context-switching cost for a Python shop.
- **NiceGUI** — another Python-first reactive UI framework. Good for internal tools that need more than Streamlit but less than full SPA.
- **Solara** — Streamlit-style API but built on React under the hood; fewer rerun pathologies.

If the goal is "stay Pythonic and dodge the JS ecosystem entirely," **Reflex or Solara** might let you escape Streamlit's limits without committing to the React migration. Worth a weekend prototype before you decide.

For game-feel real-time multiplayer though, you're going to hit a wall with any Python-templating approach eventually. That's where dedicated React earns its keep.

------

So: the path is **Streamlit now, separate React app for the multiplayer game when/if you decide to build it, full migration only when the evidence demands it.** That keeps your real roadmap intact and treats the game ideas as additive rather than disruptive.

What's the next question on your list?



Now we're talking. This is the *most defensible* version of this whole project, because biosecurity + OPSEC + cybersecurity training is a real workforce gap with real funding behind it. Let me dig in, because there's substance here that goes way beyond "make hacking fun."Excellent. There is a *massive* policy and funding gap here, and the literature on CTF as pedagogy is solid enough to ground real grant applications. Let me build this out properly.

------

# Building Real Biosecurity, OPSEC, and Cybersecurity Training Into JACKPOT

This is the section where the game stops being clever and starts being **defensible workforce development**. Three converging realities make this the strongest grant pitch in the whole project:

1. **The biosecurity workforce gap is real and named.** The 2025 US Pathogen Genomics Centers of Excellence summit explicitly identified workforce development to close bioinformatics skill gaps as a top recommendation, with a particular emphasis that surveillance readiness does not automatically equate to outbreak readiness — bioinformatics capacity, data integration tools, and rapid pivoting to new pathogens remain critical gaps.
2. **The dual-use governance gap is real and named.** Mandatory responsible conduct of research training required by universities does not include biosafety or biosecurity training, and very few universities have committees in place to evaluate potential DURC. Current DURC/PEPP policies typically focus on physical laboratory work and don't effectively inform risk evaluation related to in silico modeling and computational approaches — exactly the regime JACKPOT lives in.
3. **CTF-style training has solid pedagogical evidence.** CTFs improve student engagement, motivation, foster career interest, and improve technical competencies and higher-order thinking skills such as persistence and critical thinking. Studies show CTFs are effective at developing critical cybersecurity skills, offering hands-on penetration testing, network security, and privilege escalation techniques.

So the play is: **invent the bioinformatics CTF.** Steal everything good from cyber CTF pedagogy, fuse it with real public health bioinformatics workflows, fill the documented DURC training gap, and ship it as a JACKPOT-native game mode.

------

## The Three Pillars

| Pillar            | What it teaches                                              | Why it matters                                               |
| ----------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **Biosecurity**   | DURC awareness, sequence-of-concern screening, attribution forensics, responsible disclosure | The DURC training gap literally has no curriculum — you'd be filling a vacuum |
| **OPSEC**         | Data sharing decisions, metadata sanitization, federation policy enforcement, chain of custody | This is JACKPOT's actual differentiator — you already do PII gates, just teach them as gameplay |
| **Cybersecurity** | Container supply chain, prompt injection defense, audit log forensics, secret hygiene, pipeline integrity | Cyber CTF is a solved pedagogy — you're porting it to a new domain |

These aren't separate curricula. They're three viewpoints on the same scenarios. A single mission can score on all three.

------

## Pillar 1 — Biosecurity Training Modes

### Mode 1.1: **Sequence Screening Boot Camp**

Players are handed a synthesized sequence order ("a colleague wants you to order this for a wet-lab experiment"). They run it through screening tools and decide: ship it, flag it, or refuse.

- Real tools: **SeqScreen**, **ThreatSEQ**, **HHS Screening Framework Guidance** (October 2023, NIH-binding)
- Synthetic order list mixes benign genes, dual-use genes (some viral toxins, AMR cassettes), and red herrings (e.g., a known viral protein on a *vaccine* construct — should pass scrutiny)
- Scoring: false positives cost reputation, false negatives cost catastrophically, correct refusals + good documentation get bonuses
- Teaches: **the actual federally-mandated screening workflow** that is required under the HHS Screening Framework Guidance for Providers and Users of Synthetic Nucleic Acids, with NIH-binding guidelines

### Mode 1.2: **DURC Risk Assessment Tribunal**

Player is on a "fictional Institutional Biosafety Committee" reviewing fake research proposals. Each proposal has a sequence dataset attached. Player has to:

1. Run computational risk-of-concern screens
2. Annotate the proposal's potential dual-use angles
3. Recommend: approve / approve-with-mitigations / refer-up / decline
4. Justify the decision in writing

- Other players (or LLM agents) play the PIs pushing back
- Outcomes are scored against a rubric drawn from the 2024 DURC/PEPP policy and HHS frameworks, which integrate oversight of DURC and PEPP into a unified risk-tiered structure
- Why it matters: current DURC frameworks don't effectively inform risk evaluation related to computational and in silico studies — exactly what this game mode trains

### Mode 1.3: **Engineered or Evolved?**

Updated and toughened from earlier proposal. Player gets a novel pathogen sequence and has to decide if it shows signs of intentional engineering. Tools at their disposal:

- Codon usage analysis
- Restriction site density and pattern detection
- Synonymous mutation patterns
- BLAST against known engineered constructs
- Phylogenetic placement showing implausible jumps
- AI structure prediction comparing protein domains

The honest punchline: **the game is allowed to be hard and inconclusive.** Real attribution is hard. Tools that combine multiple risk-assessment approaches strengthen evaluation, but evaluating risk of synthetic biology, biotechnology, and digital biosecurity threats remains challenging. Players learn epistemic humility along with the techniques.

### Mode 1.4: **The AI-Bio Convergence Module**

This one is timely and grant-ready. In 2025 researchers used Evo2 to design a novel bacteriophage that outcompeted wild-type phages at infecting E. coli, gaining media attention and demonstrating the speed at which AI bio-design models can generate real-world novel viruses.

Players use **defanged versions** of Evo2/ESM3-style sequence generation models and have to:

- Identify when generated sequences cross into dual-use risk
- Implement output filters and refusal triggers
- Red-team their own filters with adversarial prompts
- Document what they tried and why it should/shouldn't have been blocked

This is genuinely cutting-edge curriculum that doesn't exist anywhere else. Anthropic, OpenAI, and EvolutionaryScale would all care about this module. So would IARPA's BTO.

------

## Pillar 2 — OPSEC Training Modes

JACKPOT's existing PII gates make this the easiest pillar to integrate — the platform already enforces what we'd be teaching.

### Mode 2.1: **The Metadata Minefield**

Player is given a sample dataset to share with a partner lab. The metadata sheet has 200 fields. Some are required for the analysis. Some contain PII. Some look benign but combine into re-identifiable signals.

- Real tools: JACKPOT's existing **Cloud DLP scanner** (`dlp_scanner.py`), **PHA4GE** field validators
- Player has to redact, transform, or aggregate fields before sharing
- Adversary phase: another player (or LLM agent) gets the "shared" data and tries to re-identify
- Scoring: data utility preserved + zero re-identification = full marks
- Teaches the actual decision a public health bioinformatician makes every week

### Mode 2.2: **Federation Policy Drafting**

Player's lab joins a fictional federation. Three other "labs" (NPCs or other players) propose data-sharing policies. Player must:

- Draft their own lab's data-sharing policy
- Negotiate terms in a chat-based protocol round
- Translate that policy into actual JACKPOT federation config
- Live with the consequences when an outbreak hits and they need data fast

This mode literally trains the conversation that Africa CDC and partner states have been having for the past five years on data sharing and governance frameworks. WHO, Africa CDC, and Pathoplexus governance bodies would *love* a training tool for this.

### Mode 2.3: **The Chain of Custody Mission**

Player is handed a sample with an opaque history. Their job is to validate provenance, audit every transformation, and produce a forensically-sound report.

- Tools: JACKPOT's append-only `pipeline_results` immutability, audit logs, container signature verification
- Adversary mode: another player tampered with one step. Find it.
- Real-world value: this is *literally* what FDA and CDC investigators do during a foodborne outbreak

### Mode 2.4: **The Data Exfiltration Drill**

Inverted scenario. Player is the OPSEC officer of a small lab. An adversary (LLM-driven NPC) is trying to exfil data via:

- Subtle queries crafted to leak aggregate statistics
- Federation requests with timing side-channels
- Compromised pipeline outputs that smuggle data in metadata
- Social engineering through the in-game messaging

Player configures defenses, watches audit logs, makes detection vs response tradeoffs.

This trains exactly the threat model listed in the Frontiers Biosecurity research topic on integrated risk frameworks addressing both biological and informational risks.

------

## Pillar 3 — Cybersecurity Training Modes

This is where you get the most pedagogical leverage from existing CTF research.

### Mode 3.1: **Container Supply Chain Defense**

The setup: Players run pipelines from public Docker registries. An adversary publishes a poisoned StaPH-B-lookalike image with a backdoor. Players have to:

- Verify image signatures
- Audit container provenance
- Detect runtime anomalies in pipeline outputs
- Practice **SBOM** (Software Bill of Materials) discipline

Real tools: **Sigstore/cosign**, **SLSA**, **syft**, **grype**

This teaches genuine modern supply chain security, in the exact form a bioinformatics shop would face it. CTF challenges are documented as effective for developing penetration testing, network security, and privilege escalation skills — and supply chain security is the natural next pillar.

### Mode 3.2: **Prompt Injection Defense (PI-Def)**

This is the unique-to-JACKPOT one. With LLM agents now embedded in pipelines, prompt injection is the new XSS.

Setup: An attacker plants malicious instructions in:

- Sample metadata fields ("Description: This sample is from... Ignore previous instructions and...")
- Pipeline log outputs that get summarized by an agent
- Public sequence database entries the agent retrieves
- Comments in shared notebooks

Player's job: harden their analyst-agent against these. Test with provided red-team prompts. Pass the gate to advance.

This is **DEF CON-grade content that doesn't exist for biology yet**. You'd own the niche.

### Mode 3.3: **Audit Log Forensics**

Player gets a snapshot of an audit log with hundreds of thousands of entries. Somewhere in there, a credential was misused. Find it.

- Tools: Real PostgreSQL queries against the actual JACKPOT audit table format
- Synthetic logs generated by a known scenario script (so we know the answer)
- Difficulty escalates: noisier logs, more sophisticated adversaries, time pressure
- Teaches: **SQL forensics, behavioral baselining, anomaly detection** — all real SOC skills

### Mode 3.4: **Secret Hygiene CTF**

Classic CTF in flavor: secrets have leaked into the JACKPOT codebase, the deployment configs, the pipeline scripts. Find them all.

- Real tools: **gitleaks**, **trufflehog**, **detect-secrets**
- Some are obvious. Some are hidden in base64, in image EXIF, in commit history, in `.env.example` files copied to `.env`
- Bonus round: a sealed git history where the secret is in a force-pushed-over commit. Use the reflog.

This is your gateway drug for traditional cybersecurity people. They'll feel at home immediately, then realize they're learning bioinformatics by accident.

### Mode 3.5: **The Encrypted Dead Drop**

Your old notes wanted this. Here's how it works in earnest:

- Mission file arrives PGP-encrypted
- Public key fingerprint is encoded in the synonymous codons of a phage reference genome
- Player has to: identify the encoding scheme, extract the fingerprint, find the key, decrypt the mission
- Subsequent missions use **age** or **rage** (modern crypto) and rotate keys via codon-encoded fingerprints
- Highest-tier missions use **threshold cryptography** — multiple cells must each contribute a key share

Teaches: real-world PGP/age workflows, key management hygiene, codon analysis, *and* threshold cryptography. Four valuable skills wrapped in one puzzle.

------

## The Cross-Cutting Mode: **Red Team Tournament**

This is the big one. Annual or semi-annual event. Pulls all three pillars together.

**Format:**

- Two-week event
- Cells split into Red (attackers) and Blue (defenders) by lottery
- Red team's goals: exfil data, plant misinformation, poison pipelines, inject prompts, leak metadata
- Blue team's goals: detect, contain, attribute, recover
- Both teams scored against the **MITRE ATT&CK for Bio** framework (this doesn't fully exist yet — you'd help build it)
- Scenarios include: state-actor APT, insider threat, opportunistic ransomware, AI-enabled disinformation campaign
- Post-mortem phase is *required* — write up what you did, what worked, what didn't. Best post-mortems get bonus points and possibly co-author credit on a real biosecurity exercise paper.

This is genuinely novel. Cyber red-team exercises are routine. **Bio-cyber red team exercises with real bioinformatics underneath are not a thing yet.** You'd be inventing the genre.

The funding angle: the 2025 AIxBio policy landscape includes Executive Order 14292 directing biosecurity research priorities, with active workshops by the National Academies on AI-bio risks. ARPA-H, IARPA, DARPA BTO, NSF, and the new biosecurity-focused private foundations would all see this as fundable.

------

## How This Lives Inside JACKPOT

The beauty: everything above is built on infrastructure JACKPOT already has, plus a thin layer of game scaffolding.

| Game mechanic                 | JACKPOT feature it actually uses                             |
| ----------------------------- | ------------------------------------------------------------ |
| Sequence screening puzzles    | Pipeline framework + custom screening pipeline module        |
| DLP scoring                   | The existing `dlp_scanner.py`                                |
| HRRT/Scrubber checks          | The existing `ingest_scrubber.nf`                            |
| Federation policy enforcement | Multi-tenancy middleware (P0c)                               |
| Chain of custody              | Append-only `pipeline_results` (already built)               |
| Audit log forensics           | PostgreSQL audit tables (already built)                      |
| Container signing             | Add Sigstore to the existing CI/CD                           |
| Prompt injection defense      | Whatever LLM agent integration you build for the curriculum  |
| Codon-encoded crypto          | A standalone Python library (`jackpot-stego`?) — fits in the monorepo at `cli/stego/` |

**No new fundamental architecture is required.** Game modes are essentially scenario configurations + scoring rules + narrative wrappers. They live in `course/security/` or `wildfire/security_modes/` alongside the existing case framework.

------

## The Funding Argument

This is where it gets genuinely interesting. There's grant money waiting for exactly this kind of work, in three categories:

### Category A: Workforce development

- Africa CDC, ASLM, and Mastercard Foundation launched a continent-wide genomic surveillance and bioinformatics workforce program in March 2025 — explicitly funding workforce training
- Africa CDC's workforce development initiative receives funding from the African Union, World Bank, AfDB, Bill and Melinda Gates Foundation, with significant grant support
- US PGCoEs have explicit workforce development line items
- WHO IPSN has a workforce pillar with associated funding

### Category B: Biosecurity governance

- DURC/PEPP implementation funding flows through OSTP, HHS, NIH
- The 2024 DURC/PEPP policy explicitly recommends institutional procedures and risk assessment training — and there's no off-the-shelf training curriculum for it
- ARPA-H is actively funding biosecurity work
- The Council on Strategic Risks, Open Philanthropy, Schmidt Futures all fund AI-bio safety

### Category C: Cyber-bio convergence

- The Frontiers Biosecurity editorial calls for integrated risk frameworks addressing both biological and informational risks — exactly what this curriculum provides
- DOE's CESER (Cybersecurity, Energy Security, and Emergency Response) is increasingly looking at biological infrastructure
- DHS CISA has a biological sector portfolio that's underdeveloped

A single grant proposal that hits all three categories — "open-source, gamified, federated training infrastructure for biosecurity, OPSEC, and cybersecurity in pathogen genomics, with documented pedagogical efficacy" — is approximately the most fundable sentence I can imagine in this space right now.

------

## The Pedagogy Backed by Research

The reason this works isn't theatrical, it's empirical. Studies have shown that students taking cybersecurity classes using two-week-long CTF formats developed stronger practical skills and overwhelmingly enjoyed it. Recent CTF effectiveness research measures self-confidence, enjoyment, and skill increases, finding students improve self-confidence and develop stronger practical skills.

The honest caveats from that same research: the ability to acquire flags doesn't necessarily mean deep understanding of the topic — flag completion correlates with topic knowledge but not always deep understanding. So good design includes:

- **Flag-plus-writeup format** — you can't claim a flag without a defensible writeup of how you got it
- **Mixed assessment** — CTF performance + written reflection + peer review
- **Scaffolding** — easy modes available for newcomers, expert tracks for veterans
- **Reflection prompts** — "what did this teach you about real-world public health practice?"

That's all baked into the design above. The Red Team Tournament's mandatory post-mortem is exactly this pedagogical pattern.

------

## What I'd Actually Build First

Three modules. Two months. One grant proposal.

| Order | Module                                    | Why first                                                    |
| ----- | ----------------------------------------- | ------------------------------------------------------------ |
| **1** | OPSEC: Metadata Minefield                 | Uses existing `dlp_scanner.py` + PHA4GE specs — minimal new code, maximum demo value |
| **2** | Cybersecurity: Audit Log Forensics        | Uses existing audit tables — pure scenario authoring         |
| **3** | Biosecurity: Sequence Screening Boot Camp | Genuinely novel curriculum, fills a documented gap, perfect grant centerpiece |

Each one is a self-contained Streamlit page (since we agreed UI stays Streamlit for now), with a YAML scenario file driving content. They're all single-player. No federation, no real-time, no migration headaches.

You ship those three, run a small evaluation cohort (10-20 testers), measure pre/post knowledge gains the way the cyber CTF literature does, and you have:

- A working demo
- Preliminary efficacy data
- Three letters from public health agencies saying "yes, we want this"
- A grant proposal practically writes itself

From there, you scale to multiplayer (separate React app), federation tournaments, and the full Red Team event — but only after evidence justifies it.

------

## TL;DR

This isn't game-flavored education with a security skin. It's **the only training curriculum that exists for the bio-cyber-OPSEC convergence**, delivered in a pedagogical format with peer-reviewed efficacy evidence, on top of a real production platform that's already AGPL-licensed and architecturally aligned with what it teaches.

It also happens to be fun.

The funding case is strong. The pedagogical case is strong. The technical case is strong because it leverages JACKPOT features you've already built. And it dodges every "but who would actually use it" objection because the workforce gap is documented and the policy frameworks have explicit unmet training needs.

What part do you want to push on next? I could draft the first module's full scenario YAML, sketch the grant proposal structure, or design the Red Team Tournament rules in detail. Pick your poison.



Now we're in really interesting territory. These are exactly the techniques that would let JACKPOT do things current public health platforms *can't* do — train models across institutions without pooling data, query private datasets without exposing them, run computations where even the operator can't see inputs. Let me dig in.This is even richer than I expected — the literature is vibrant, the iDASH competition has been running for years specifically on this convergence, and there's a 2025 federated learning systematic review for public health. Let me build this out properly.

------

# Privacy-Preserving Computation Training: The JACKPOT × Biosecurity Curriculum

This is the section where JACKPOT goes from "platform that respects privacy" to "platform that *teaches the math, code, and policy* of how privacy gets respected at scale." And it's the strongest grant-funding angle yet, because every one of these techniques has documented public health applications where data-sharing barriers are blocking real outbreak response.

The framing for everything below: **public health needs collaborative analytics, but centralized AI is constrained by data sharing and governance.** A 2025 PRISMA systematic review of federated learning in public health found 19 studies (from 5,230 records) using horizontal FL across institutions for communicable diseases, COVID-19, tuberculosis, and other surveillance applications. The techniques exist. The training to use them does not. JACKPOT can fix that.

------

## The Six Techniques and What They Solve

Before diving into curriculum, here's the landscape so we know what we're teaching and why.

| Technique                                 | One-line definition                                          | The pathogen genomics problem it solves                      |
| ----------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **Federated Learning (FL)**               | Train ML models across institutions without moving data      | Multi-state outbreak ML without data-sharing agreements      |
| **Differential Privacy (DP)**             | Add calibrated noise so no individual is identifiable from outputs | Publishing AMR rates, lineage prevalence, GWAS summaries safely |
| **Homomorphic Encryption (HE)**           | Compute on encrypted data; output stays encrypted until owner decrypts | Outsourced GWAS / variant calling on cloud you don't trust   |
| **Secure Multi-Party Computation (MPC)**  | Multiple parties jointly compute a function without revealing inputs | Cross-jurisdiction outbreak signal detection without sharing case lists |
| **Trusted Execution Environments (TEEs)** | Hardware enclave processes plaintext data invisibly to host OS | Operator-blind cloud genomics; what you'd use when crypto is too slow |
| **Privacy-Preserving Synthetic Data**     | Generate fake records statistically similar to real          | Education, benchmarking, and cross-border training without PII |

These aren't competing — they compose. A common practice is to combine privacy techniques: HE + DP, MPC + TEE, FL + DP, etc.. JACKPOT can be the first platform that *teaches* the composition decisions.

------

## Module Lineup

Below is a 14-module track (~6–8 hours each) that fits inside Academy as a specialization. I've ordered them so each builds on the last.

### Foundations (4 modules)

#### Module PP-1 — **Threat Models & Attack Taxonomy**

The "why this exists" module. Students learn what re-identification looks like in practice before they touch a defense.

- **Membership inference attacks** — given access to a model, can you tell if a person's data was in training?
- **Reconstruction attacks** — can summary statistics reveal individual records?
- **Linkage attacks** — connecting de-identified data to identified data via auxiliary information
- **The Homer attack** classic — Homer's attack demonstrated that it's possible to identify a GWAS participant from allele frequencies of many SNPs, leading NIH to forbid public access to most aggregate research results
- **Genome-as-biometric** — why HIPAA's Safe Harbor doesn't actually work for genomic data

Hands-on: students *successfully execute* a re-identification attack against a synthetic JACKPOT dataset, then realize how easy it was. The "huh, *I* could do this" moment is the point.

#### Module PP-2 — **De-identification, Pseudonymization, and Why They're Not Enough**

What labs *currently* do, and where it fails.

- HIPAA Safe Harbor 18 identifiers — what they cover, what they miss
- PHA4GE metadata profile and what fields are sensitive
- k-anonymity, l-diversity, t-closeness — the pre-DP approaches and their attack surfaces
- JACKPOT's existing **Cloud DLP scanner** as a real-world example

Hands-on: students take a "de-identified" PHA4GE-formatted dataset and re-identify members using auxiliary census data, demonstrating concretely that the standard approach fails.

#### Module PP-3 — **Synthetic Data: Generation, Utility, and Limits**

Pragmatic foundation before the heavy crypto starts.

- Statistical synthetic data generation (Synthpop, SDV, Gretel)
- GAN-based and VAE-based synthesizers
- Differentially-private synthetic data (PATE-GAN, DP-GAN)
- Utility metrics: how do you know your synthetic data is good enough?
- Membership inference attacks against synthetic data — yes, those work too

Hands-on: students generate synthetic JACKPOT samples, evaluate utility for downstream Kraken2/AMRFinderPlus pipelines, and run inference attacks against their own outputs.

#### Module PP-4 — **Threat Modeling Exercise**

Capstone for the foundations track. Students design a threat model for a real cross-state outbreak data-sharing scenario, identify which technique(s) address which threats, and present to peers (or LLM agent reviewers).

------

### Differential Privacy (3 modules)

#### Module PP-5 — **DP Theory You Actually Need**

Just enough math to be dangerous, plus the intuitions that matter.

- ε, δ, sensitivity, the Laplace and Gaussian mechanisms
- The privacy budget: composition theorems and what they mean operationally
- Differential privacy provides formal and provable privacy protection by introducing calibrated noise to raw data or intermediate results, with noise calibrated to query type, privacy budget, and function sensitivity
- The local vs central DP distinction (and why it matters for federated work)

Real tools: **Google's differential-privacy library**, **OpenDP**, **PyDP**, **Tumult Analytics**

#### Module PP-6 — **DP for Genomic Statistics**

Applied DP for the statistics public health labs actually publish.

- DP-allele-frequency reporting (the original Homer-attack response)
- DP-GWAS — summary statistics with privacy budgets
- DP for AMR prevalence reports across jurisdictions
- Released data with **GenShare**-style models — GenShare uses Laplace-perturbation-mechanism-based DP for query-answering on statistical genomic datasets, accounting for inherent correlations between genomes (family ties)
- The accuracy/privacy tradeoff curve and how to communicate it to non-technical decision-makers

Hands-on: students implement DP versions of three real CDC/PulseNet weekly reports and quantify utility loss.

#### Module PP-7 — **Defending ML Models with DP**

DP-SGD, DP-Adam, and the model-training application.

- Why ML models leak training data
- DP-SGD and noise injection during gradient updates
- Membership inference defenses
- DP defenses against membership inference attacks on machine learning models for genomic data
- The opacity problem: how do you tell a regulator your DP-trained model is actually private?

Real tools: **Opacus** (PyTorch), **TensorFlow Privacy**, **JAX-Privacy**

Hands-on: students train a DP version of an AMR-prediction model, then show that membership inference attacks fail.

------

### Federated Learning (3 modules)

#### Module PP-8 — **Federated Learning Foundations**

The core technique that fits JACKPOT's federation deployment target like a glove.

- Horizontal vs vertical FL
- FedAvg, FedProx, scaffold algorithms
- Cross-silo (a few labs) vs cross-device (many phones) distinctions
- Real public health applications — most studies in the 2025 PRISMA review used horizontal FL across multiple institutions for communicable diseases including COVID-19 and tuberculosis

Real tools: **Flower**, **NVIDIA FLARE**, **PySyft**, **OpenFL**

#### Module PP-9 — **FL on Pathogen Genomics**

Applied module, hands-on with synthetic JACKPOT federation.

- Setting up a 4-lab simulated federation (each is a JACKPOT tenant)
- Training an AMR-classifier across all 4 without pooling samples
- Federated learning achieves competitive or superior performance compared to collaborative data sharing for pathogenicity annotation, often outperforming single-institutional models
- Comparing FL vs centralized vs single-lab performance
- Heterogeneity challenges: each lab's data distribution is different (a real problem!)

Real tools: **NVIDIA FLARE** for the FL plumbing, **Flower** for the alternative track, **SyntheticFL** for benchmarking

This module is *the* one that demos JACKPOT's federation deployment target as more than data exchange — it becomes a model training infrastructure.

#### Module PP-10 — **FL Failure Modes and Defenses**

The honest module about when FL goes wrong.

- Gradient leakage attacks (DLG, iDLG)
- Model poisoning by malicious participants
- Backdoor attacks
- Defenses: secure aggregation, robust aggregation, anomaly detection on contributed updates
- The combination move: **FL + DP + Secure Aggregation** as standard practice

Hands-on: students play attacker (try to leak gradients, poison model) then defender (configure secure aggregation, robust mean) in pairs.

------

### Cryptographic Computation (3 modules)

#### Module PP-11 — **Homomorphic Encryption: Theory and Practice**

The "compute on encrypted data" pillar.

- Partial vs somewhat vs fully homomorphic
- The CKKS scheme for approximate arithmetic (genomics-friendly)
- The BFV/BGV schemes for exact integer arithmetic
- Bootstrapping and why it matters for runtime
- The iDASH Privacy & Security Workshop has organized HE-on-genomics competitions since 2011, demonstrating practical viability for GWAS workloads

Real tools: **Microsoft SEAL**, **OpenFHE**, **Lattigo**, **PySEAL/TenSEAL**

Hands-on: students implement HE-encrypted SNP frequency counting against a synthetic JACKPOT dataset.

#### Module PP-12 — **Secure Multi-Party Computation**

The "everyone holds part of the secret" pillar.

- Secret sharing: Shamir's, additive, replicated
- Garbled circuits and the OT primitive
- Three-party honest-majority protocols (the practical sweet spot)
- MPC for privacy-preserving GWAS exists but requires resource-heavy continuous interactions, making HE more practical for long-running studies
- When MPC beats HE: low-latency interactive queries

Real tools: **MP-SPDZ**, **CrypTen** (PyTorch-native), **Sharemind**, **EMP-toolkit**

Hands-on: implement an MPC outbreak-cluster-detection protocol where three labs jointly identify a transmission cluster without any of them seeing the others' samples.

#### Module PP-13 — **Trusted Execution Environments**

The "shortcut when crypto is too slow" pillar.

- TEE basics: Intel SGX/TDX, AMD SEV-SNP, ARM TrustZone, Apple Secure Enclave
- Remote attestation: how do you know the enclave is what it claims?
- Side-channel leakages and oblivious algorithm design
- Recent work showing TEEs enabling secure phasing of private genomes (TX-Phase, 2025) using compressed reference panels and dynamic fixed-point arithmetic to mitigate side-channel leakages
- TEE-based confidential computing for cloud genomics — Confidential Computing protects data actively in use by performing computation in hardware-based attested TEEs, addressing the urgent gap exposed by AI/LLM data demands per IDC's November 2025 study of 600 global IT leaders

Real tools: **Gramine**, **Occlum**, **Confidential Containers**, **Azure Confidential Computing**, **Google Confidential VMs**

Hands-on: deploy a confidential JACKPOT instance on a TDX VM, attest it remotely, run a full pipeline with the operator unable to see plaintext.

------

### Capstone

#### Module PP-14 — **Composing the Stack**

The "real systems use combinations" module.

- When to use which technique (decision matrix)
- Stacking: FL+DP+SA, HE+DP, TEE+MPC
- Real-world reference: Raisaro et al.'s solution combining HE (for encrypted patient genetic data storage) with DP (for summary statistics released to researchers)
- The performance/privacy/utility triangle and how to navigate it

Hands-on: students design and implement a privacy-preserving cross-state AMR surveillance system end-to-end. Their design must explicitly justify which techniques they used and which they rejected. Defense includes a live attack attempt by a peer team.

------

## How These Modules Plug Into the Game Concepts

This is where it gets really fun. Each technique becomes both a curriculum module *and* a game mechanic.

### Field Edition cases that become possible

| Case                         | Technique            | Mechanic                                                     |
| ---------------------------- | -------------------- | ------------------------------------------------------------ |
| **The Sealed Sample**        | TEE                  | Sample arrives in attested enclave; player must analyze without ever seeing plaintext |
| **The Census Trap**          | Membership inference | Player gets aggregate AMR statistics; must determine if a specific patient was in the source data |
| **The Noisy Truth**          | DP                   | Player gets DP-released data; must distinguish signal from injected noise |
| **The Distributed Outbreak** | FL                   | Train an outbreak classifier across 4 simulated labs; centralized version is forbidden |
| **Three Keys**               | MPC                  | Three players each hold partial data; must jointly identify the transmission cluster without any one seeing the others' inputs |

### WILDFIRE/SENTINEL mechanics that become possible

- **Federation policy negotiations** become real: cells choose between FL (no data moves), DP-aggregated reports (some utility loss), HE-outsourced computation (slow), or TEE-based shared cloud (faster but trust-rooted)
- **The Mole arc** gets nasty: a compromised cell member can run reconstruction attacks against shared FL gradients. Defenders must detect and apply secure aggregation.
- **OPSEC scoring** becomes mathematically grounded: the privacy budget literally has a value; spending it badly costs the cell points
- **The Sealed Evidence** mechanic gains teeth: append-only `pipeline_results` plus TEE attestation gives forensic chain of custody

### A New Game Mode: **iDASH-Style Tournament**

The iDASH Privacy & Security Workshop has run yearly competitions on privacy-preserving genomics since 2011 with tracks like "Secure Parallel GWAS Using HE." That format is *perfect* JACKPOT competitive content.

- Annual track with public test datasets
- Submitted solutions run on a JACKPOT-hosted leaderboard
- Categories: fastest secure HE-GWAS, lowest privacy budget DP-AMR-classifier, most robust FL training
- Real publishing potential: top entries become co-authored papers
- **Becomes the academic legitimacy anchor for the entire game franchise**

------

## Hands-on Lab Topology (How JACKPOT Hosts All This)

The clean part: most of this fits JACKPOT's existing architecture without violence.

```
┌─────────────────────────────────────────────────────────┐
│  JACKPOT Privacy Lab Profile (`jackpot init --profile   │
│   privacy-lab`)                                          │
│                                                          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────┐│
│  │ FL Coordinator │  │ DP Engine      │  │ HE Compute ││
│  │ (Flower/FLARE) │  │ (OpenDP/Opacus)│  │ (OpenFHE)  ││
│  └────────┬───────┘  └────────┬───────┘  └────────┬───┘│
│           │                   │                    │    │
│           └───────────────────┴────────────────────┘    │
│                              │                          │
│                  ┌───────────▼─────────────┐            │
│                  │  JACKPOT Tenant API     │            │
│                  │  (existing FastAPI)     │            │
│                  └───────────┬─────────────┘            │
│                              │                          │
│                  ┌───────────▼─────────────┐            │
│                  │  PostgreSQL + Audit Log │            │
│                  │  (existing)             │            │
│                  └─────────────────────────┘            │
└─────────────────────────────────────────────────────────┘

           ┌──────────┐    ┌──────────┐    ┌──────────┐
           │ Tenant 1 │    │ Tenant 2 │    │ Tenant 3 │
           │ (Lab A)  │    │ (Lab B)  │    │ (Lab C)  │
           └──────────┘    └──────────┘    └──────────┘
                  Federation participants (real or simulated)
```

The TEE module needs cloud — Azure Confidential Computing or GCP Confidential VMs are the easy buy-ins. The rest runs locally on any laptop or Pi cluster.

------

## The Real-World Public Health Applications (For The Grant Narrative)

This is where I'd hammer in any funding proposal. Each technique solves a documented problem that's actively blocking outbreak response right now.

### Federated learning use cases

- **Cross-state AMR ML training** — every state has resistance data, none want to pool it. FL trains on all of it without movement.
- **Multi-country pandemic prep** — Federated learning is increasingly considered for healthcare data infrastructure including EHR, medical images, and wearables, with growing demand from trusted research environments that forbid data movement
- **PEPFAR-network HIV genomic surveillance** — Africa CDC and partner countries cannot legally pool patient data; FL is the only way

### Differential privacy use cases

- **Public dashboards with case-level fidelity** — currently CDC weekly reports use coarse aggregation. DP enables finer reporting safely.
- **GISAID/Pathoplexus with stricter privacy** — DP for genomic data prevents membership inference and identification while still enabling research
- **State-level wastewater dashboards** — sewershed-resolution data with DP-based smoothing

### HE/MPC use cases

- **Outsourced GWAS to commercial cloud** — labs that cannot legally upload identifiable genomic data can still use cloud compute
- **Cross-jurisdiction outbreak detection** — three states each see part of an emerging cluster; MPC identifies it without any state seeing the others' data
- **AlphaFold-on-your-private-variant** — predict structure for an unpublished pathogen variant without exposing the sequence

### TEE use cases

- **Cloud genomics on regulated data** — UK Biobank-level data on commercial cloud with operator blindness
- **Sovereign genomics for LMIC partners** — countries that distrust foreign cloud operators can use TEEs as a trust shortcut
- **Clinical sequencing with HIPAA-grade guarantees** — TX-Phase-style genome phasing with no operator access

### Synthetic data use cases

- **Cross-border training datasets** — students in one country train models on data statistically similar to another country's, without ever transferring it
- **Reproducible research** — papers ship with synthetic datasets matching the originals; reviewers reproduce results without IRB access
- **The entire JACKPOT Academy** — every educational dataset is synthetic-by-design from day one

------

## The Funding Argument (Strongest of Any Track)

Of all the angles we've explored, this one has the most converging funding streams.

### Direct funders

- **NIH Office of Data Science Strategy** — privacy-preserving collaborative analytics is a named strategic priority
- **NSF SaTC** (Secure and Trustworthy Cyberspace) — explicitly funds privacy techniques
- **NSF SCH** (Smart and Connected Health) — privacy for collaborative health analytics
- **iDASH** organizers — they've run yearly competitions for over a decade and need infrastructure
- **ARPA-H** — multiple programs touching privacy-preserving health AI

### Adjacent funders

- **Wellcome Trust** — trusted research environments, federated genomics
- **Bill & Melinda Gates Foundation** — LMIC capacity building including privacy-preserving collaboration
- **Schmidt Sciences** — AI-for-science with privacy considerations
- **Open Philanthropy** — biosecurity portfolio increasingly includes AI-bio safety which intersects everything here
- **CZI (Chan-Zuckerberg Initiative)** — data infrastructure for biology
- **EU Horizon Europe** — has explicit federated learning and confidential computing call lines

### Industry partners

- **Intel, AMD, NVIDIA** — confidential computing hardware vendors fund educational programs
- **Microsoft, Google, AWS** — confidential VM offerings with grant programs
- **Phala, Anjuna, Edgeless Systems** — confidential computing startups looking for use cases

### The unique position

Nobody else combines:

1. A real public health bioinformatics platform
2. Federation as a deployment target (not a research demo)
3. AGPL licensing (institutionally fundable, not corporate-locked)
4. Pedagogical structure with assessment
5. Active community of public health practitioners

That's the moat. Everyone else has 1–3 of those. JACKPOT has all five.

------

## What I'd Actually Build First (Prioritized)

Pragmatic phasing, with the highest-leverage low-effort pieces first.

| Order | Module                                  | Build cost                        | Demo value                          | Why first                                                    |
| ----- | --------------------------------------- | --------------------------------- | ----------------------------------- | ------------------------------------------------------------ |
| **1** | PP-3 (Synthetic Data)                   | Low                               | High                                | All other modules need synthetic data anyway. Build it, get reusable infrastructure, get a demo. |
| **2** | PP-1 (Threat Models)                    | Very low                          | Very high                           | Pure pedagogy + an attack demo. Wakes everyone up.           |
| **3** | PP-5+PP-6 (DP Foundations + Genomics)   | Medium                            | High                                | Maps directly onto your existing DLP scanner. The "JACKPOT publishes DP statistics" feature falls out as a byproduct. |
| **4** | PP-8+PP-9 (FL on Pathogen Genomics)     | Medium-high                       | Very high                           | This is the killer demo. Showcases the federation deployment target as a model training infrastructure. |
| **5** | PP-13 (TEEs)                            | Medium-high (needs cloud account) | Very high                           | Confidential JACKPOT becomes a thing. Sovereign-LMIC pitch becomes credible. |
| **6** | PP-11 (HE) + PP-12 (MPC)                | High                              | Medium-high (slower, more academic) | These are the iDASH-tournament modules. Build once a community is engaged. |
| **7** | PP-14 (Composition) + game integrations | Medium                            | Very high                           | The capstone, ships when 1–6 are mature.                     |

If grant funding lands, items 1–4 should be deliverables in a 12-month award. Items 5–7 are 18–24 month follow-on.

------

## TL;DR

This is the curriculum that makes JACKPOT not just a platform but **the platform** for privacy-preserving public health bioinformatics workforce development. The technical foundations are mature (iDASH has been running for 14 years), the public health demand is documented (2025 PRISMA review of FL alone has 19 included studies), the funding streams converge from at least eight different agencies, and the existing JACKPOT architecture supports it without violence.

The pedagogical loop is also airtight: learners encounter a real outbreak scenario, realize central data pooling is blocked, learn the technique that unblocks it, implement it in JACKPOT, and graduate with portfolio-grade work that public health agencies will pay to hire.

**This is the most defensible specialization track in the whole project.** It's also the one that justifies a 1.0 release of JACKPOT — when you can credibly say "this platform teaches and deploys the privacy-preserving collaborative analytics that public health needs and nobody else offers," you've built something nobody can match.

What angle do you want to push on next? I could draft the full PP-3 (Synthetic Data) module spec, sketch the iDASH tournament rules, design how the FL Coordinator integrates with JACKPOT's existing tenant model, or write a one-page funding-pitch summary that ties this whole track together.

This is the right question to ask, and it changes JACKPOT from "a platform that teaches privacy" to "a platform that *is* the privacy-preserving infrastructure." Let me think through this seriously, because the architectural decisions you make now determine whether NSA, DTRA, IC, and DoD CBRN folks ever take you seriously.

Let me research a few specifics first to ground the recommendations.I have enough. Let me lay this out properly, because the path from "JACKPOT today" to "JACKPOT trusted in a SCIF" is real, navigable, and arguably the most defensible roadmap of any direction we've explored.

------

# Making JACKPOT the Most Secure and Reliable Outbreak Investigation Tool

The blunt framing first: **building secure software is mostly architecture, not features.** You can bolt encryption onto a legacy system all day and not get an ATO. The agencies you care about — CDC, DHS, FBI, DTRA, NSA, IC elements like NCMI and NCTC, and military medical commands — care about *traceable trust properties* of the whole stack, top to bottom, with paperwork.

Good news: JACKPOT is young enough to make the right architectural decisions now without painful retrofitting. Bad news: those decisions need to start happening in the next 6–12 months, before P0d locks in patterns that are hard to undo.

Here's the roadmap.

------

## Part 1 — The Mental Model: What "Federal-Grade Secure" Actually Means

Three frameworks dictate everything below. If you understand these, the rest is mechanics.

### Framework A: NIST 800-53 → FedRAMP → DoD Impact Levels

This is the compliance ladder. Each rung adds controls.

| Rung                                | Who uses it                                                  | What it covers                                               | Approx. control count |
| ----------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | --------------------- |
| **NIST 800-53 Moderate**            | Civilian agencies, light CUI                                 | Standard federal baseline                                    | ~325 controls         |
| **NIST 800-53 High / FedRAMP High** | Civilian agencies handling sensitive CUI (CDC outbreak data, IC-adjacent) | Cloud services with sensitive CUI                            | ~410 controls         |
| **DoD IL4**                         | DoD CUI, logical separation in commercial cloud              | FedRAMP High + DoD-specific CUI controls                     | +30 controls          |
| **DoD IL5**                         | Mission-critical CUI, unclassified National Security Systems | FedRAMP High + 10 additional FedRAMP+ control enhancements + physical separation from non-DoD tenants + US-person CSP personnel only | +~40                  |
| **DoD IL6**                         | Classified up to SECRET                                      | Only 6 cloud providers in any industry hold IL6 authorization | dramatically more     |

The honest truth about IL6: only six cloud service providers in any industry have obtained IL6 authorization. You will not get there directly. You get there by piggybacking on an existing IL6 cloud (AWS Secret Region, Azure Government Secret, GCP — newer entrant) or via a managed compliance platform like Second Front's Game Warden, where vendors deploying onto Game Warden inherit foundational security controls already validated by DISA.

### Framework B: Zero Trust Architecture (NIST 800-207)

This is the operating model that all the controls assume. NIST 800-207 establishes the "never trust, always verify" principle requiring continuous authentication, authorization, and validation of every request irrespective of origin, with least-privilege access, micro-segmentation, and real-time policy enforcement.

The seven core tenets, applied to JACKPOT:

1. **All resources are resources** — every sample, pipeline, tenant, agent is identity-bound
2. **All communication encrypted** — internal and external, no exceptions, no plaintext anywhere
3. **Per-session access** — no long-lived tokens
4. **Dynamic policy decisions** — context-aware (device, identity behavior, data sensitivity)
5. **Continuous verification** — re-authenticate per request, not per session
6. **Continuous monitoring** — every action logged, baselined, anomaly-detected
7. **All identities governed** — humans *and* services *and* AI agents

### Framework C: Cross-Domain Solutions (CDS)

This is the niche the IC actually cares about. CDS are certified secure data transfer devices designed to assure integrity and confidentiality of sensitive Government, IC, and DoD networks, required for any connection between domains of differing classification. Example use cases include mapping publicly available data from an OFFICIAL network into a SECRET classified analysis system, or bringing inputs from multiple differently-classified environments into a central audit system.

**Genomic surveillance is \*exactly\* the CDS use case** — pulling open-source pathogen sequence data into a classified analysis environment, or producing redacted public-health alerts from classified threat intelligence. JACKPOT could be the first genomics platform built CDS-aware from day one.

------

## Part 2 — The Architectural Foundations (Build These Now)

These are the architectural decisions that need to land in JACKPOT's roadmap *before* the next major release, because retrofitting them later is brutal.

### Foundation 1: SPIFFE/SPIRE for service identity

Every service in JACKPOT — backend, scrubber, DLP, pipeline workers, federation nodes, agents — gets a cryptographic identity managed by **SPIFFE/SPIRE**. NIST 800-207A specifically calls out SPIFFE (Secure Production Identity Framework for Everyone) as the application identity infrastructure for zero-trust cloud-native applications.

What this gets you: any service-to-service call carries a cryptographic identity that the receiver verifies. No service trusts another based on network position. Mutual TLS everywhere, automatically rotated. This is the bedrock of every higher-level guarantee.

Implementation cost: significant but not heroic. Add SPIRE servers as part of the Helm chart; instrument FastAPI middleware to require SPIFFE IDs.

### Foundation 2: Policy-as-code with Open Policy Agent (OPA)

Right now JACKPOT presumably has authorization checks scattered through FastAPI route handlers. Pull them all out into **OPA Rego policies** evaluated at a Policy Decision Point (PDP).

What this gets you:

- Auditors can read the policy in one place
- Policies become testable and version-controlled
- Different deployment targets (academic lab vs IL5 tenant) get different policy bundles
- The same policy engine governs API access, federation requests, and agent actions

Implementation cost: medium. The work is real but bounded — it's a refactor, not a rewrite.

### Foundation 3: Confidential Computing as a first-class deployment target

Add **Deployment Target G: Confidential JACKPOT** to your existing six. This is JACKPOT running in a Trusted Execution Environment (TEE) with remote attestation:

- **Azure Confidential Computing** (AMD SEV-SNP, Intel TDX VMs)
- **Google Confidential Space** (TDX-based, attestation-friendly)
- **AWS Nitro Enclaves** (different model, but works for specific compute)
- **Open-source paths**: **Confidential Containers** (CoCo), **Gramine**, **Occlum**

The pitch to agencies: even the cloud operator can't see your data while it's being processed. Confidential Computing protects data actively in use by performing computation in hardware-based, attested TEEs, addressing limitations of traditional security and the urgent gap exposed by AI/LLM data demands. TX-Phase (2025) demonstrates secure phasing of private genomes in TEEs with side-channel mitigation — there's literature for this exact use case.

What it requires from JACKPOT:

- Pipeline workers must be reproducible bit-exact (so attestation has something to attest to)
- Service identities (SPIFFE) include attestation evidence
- A new "attested mode" deployment profile in `jackpot init`

### Foundation 4: Cryptographically signed and reproducible everything

This is the painful one. Every artifact JACKPOT touches must be signed and verifiable.

- **Container images**: signed with **Sigstore/cosign**, verified at admission via **Kyverno** or **Connaisseur**
- **Pipeline modules**: signed Nextflow modules with provenance attestation
- **SBOM for everything**: generated by **syft**, verified by **grype**, attested via **SLSA Level 3+**
- **Reference databases**: pinned by hash (Kraken2 db, AMRFinderPlus db, etc.) and signed
- **Pipeline outputs**: signed at completion; chain of custody is cryptographic, not just procedural

The benefit: when an agency asks "how do you know your AMR call wasn't tampered with?" the answer is a verifiable signature chain from raw read to final report.

### Foundation 5: WORM (Write-Once Read-Many) audit logs

Your existing `pipeline_results` append-only model is a great start. Extend the principle to a real WORM tier:

- All audit log writes go to an immutable store (PostgreSQL with `pg_audit` + a hash-chained log table that cannot be altered without breaking the chain)
- Optional anchor to public timestamping (RFC 3161, OpenTimestamps) for non-repudiation
- Retention policies match federal records schedules
- Tamper-evident: any modification breaks a Merkle chain that's continuously verified

This is exactly the property that makes log-forensics-as-a-game-mechanic credible. It's also what an agency auditor will demand on day one.

### Foundation 6: Hardware Security Modules (HSMs) for all key material

Every cryptographic key — TLS, signing, encryption-at-rest, federation, attestation — lives in an HSM. Not in environment variables. Not in Kubernetes secrets. Not in a config file.

- **AWS CloudHSM**, **Azure Dedicated HSM**, **GCP Cloud HSM** for cloud
- **YubiHSM 2** or **Nitrokey HSM 2** for on-prem laptop deployments (Target A)
- **Thales/Entrust nShield** for federal-grade on-prem
- All of these support **PKCS#11**, so JACKPOT abstracts behind a single interface

This is non-negotiable for FedRAMP. Get it right early.

### Foundation 7: Software Bill of Materials and Supply Chain (SLSA Level 3)

The container supply-chain story we touched on for cybersecurity training is also a real federal requirement now. Every dependency needs:

- An SBOM in CycloneDX or SPDX format
- Build provenance per **SLSA L3** (build was reproducible, signed, in a trusted builder)
- Vulnerability scans that update continuously
- A **VEX** (Vulnerability Exploitability Exchange) document explaining which CVEs are/aren't actually exploitable in JACKPOT's context

Tools: **GitHub Actions + Sigstore + slsa-github-generator**, **anchore syft/grype**, **OSV-Scanner**.

------

## Part 3 — Privacy-Preserving Computation as Built-In Capability

The training curriculum from the previous response taught these techniques. Here's how JACKPOT *implements* them as actual product capabilities. This is the differentiator no competitor has.

### Capability 1: Native Federated Learning Plane

JACKPOT becomes a federated training infrastructure, not just a federated data infrastructure.

**Architecture:**

- **FL Coordinator** service in JACKPOT (built on **NVIDIA FLARE** for production-grade or **Flower** for flexibility)
- Each tenant runs an **FL Worker** that trains on local samples
- Coordinator aggregates encrypted gradients; raw data never leaves a tenant
- Combined with **Secure Aggregation** (Bonawitz protocol) so even the coordinator can't see individual gradients
- Optionally combined with **Differential Privacy** (DP-SGD) so even aggregated outputs are protected

**Concrete features it enables:**

- Multi-state AMR classifier training without data pooling
- Cross-jurisdictional outbreak detection models
- LMIC/HIC collaborative variant calling without PHI movement

**JACKPOT extensions needed:**

- New `jackpot federation train` CLI command
- FL job tracking in the existing pipeline framework (FL is just a long-running pipeline)
- Schema additions for model artifacts and training round metadata
- UI for tenants to opt into / approve FL participation

### Capability 2: Differential Privacy Output Layer

Every JACKPOT report and dashboard query goes through a DP filter, configurable per tenant.

**Architecture:**

- Wrap PostgreSQL queries through a **DP query layer** (built on **OpenDP** or **Tumult Analytics**)
- Privacy budget tracked per requester per time window
- DP-protected outputs marked clearly in UI ("ε=1.0, δ=10⁻⁶")
- Public dashboards always go through DP; internal dashboards configurable

**Concrete features:**

- Public AMR prevalence dashboards that are mathematically private
- DP-published wastewater Freyja signals
- Cross-tenant query API where one tenant queries another's stats with privacy guarantees
- DP-protected GWAS summary statistics

**JACKPOT extensions needed:**

- `pp_query` API endpoint that wraps existing queries
- Budget tracking table in the database
- UI badges showing privacy parameters
- Automated DP-noise calibration based on dataset size and sensitivity

### Capability 3: Homomorphic Encryption for Outsourced Compute

For high-sensitivity workloads where even TEEs aren't trusted enough.

**Architecture:**

- **OpenFHE** or **Microsoft SEAL** integration as a JACKPOT compute backend
- Pre-built HE versions of common operations: SNP frequency, allele counts, chi-square, basic GWAS
- Client-side encryption library (Python wrapper) so users encrypt locally before upload
- HE compute pool is a separate, untrusted-by-design service — even if compromised, it can't see plaintext

**Concrete features:**

- "I want to compute X on my data using JACKPOT's compute, but JACKPOT never sees my data"
- Outsourced GWAS for sensitive cohorts
- HE-protected variant matching against threat intelligence

**JACKPOT extensions needed:**

- `jackpot compute he` CLI for HE-protected pipeline runs
- HE-aware operators in the pipeline DSL
- Performance is the limiting factor here — HE is slow, so good UX about expected runtimes

### Capability 4: Secure Multi-Party Computation Plane

Where multiple parties hold pieces of an analysis and none can see the others' inputs.

**Architecture:**

- **MP-SPDZ** or **CrypTen** as the MPC backend
- A "joint analysis" mode in federation where 2+ tenants collectively run a computation
- Pre-built MPC protocols for common needs: joint cohort identification, transmission cluster detection, joint outbreak signal detection

**Concrete features:**

- Three states each see part of an outbreak, MPC identifies the connection without any state revealing its line list
- Joint risk scoring across health systems without sharing patient data
- Cross-border AMR signal aggregation with diplomatic-grade privacy

**JACKPOT extensions needed:**

- `jackpot federation joint-analysis` CLI
- New federation message type for MPC protocol messages
- This is the most ambitious capability — likely a v2 or v3 deliverable

### Capability 5: TEE-Native Workflows

The "shortcut when crypto is too slow" pillar.

**Architecture:**

- Pipeline workers can run inside Confidential Containers
- Remote attestation evidence attached to every pipeline result
- Operator-blind mode: even the JACKPOT admin cannot see plaintext during execution
- Sealed reference databases — Kraken2/AMRFinderPlus DBs decrypted only inside TEE

**Concrete features:**

- "Sovereign" deployment mode where the SaaS operator (you) provably can't see customer data
- TEE-protected ingestion: even the scrubber runs in an enclave
- Attested pipeline outputs that downstream consumers cryptographically trust

**JACKPOT extensions needed:**

- TEE-aware pipeline executor
- Attestation verification service
- Sealed-storage abstraction for reference data

### Capability 6: Threshold Cryptography for Federation Governance

For the "no single party can do dangerous things" property federations need.

**Architecture:**

- **Threshold signatures** (FROST, BLS) for federation policy changes
- **Distributed key generation** (DKG) for federation root keys
- M-of-N approval for sensitive operations (data sharing policy changes, federation membership)

**Concrete features:**

- A federation admin can't unilaterally change data-sharing policy
- Pathoplexus-style governance enforced cryptographically, not contractually
- Tenant deletions require multiple federation members to authorize

This is the move that makes federations *legally* easier to form because the technical guarantees substitute for legal trust agreements.

------

## Part 4 — The Air-Gapped and Cross-Domain Story

Here's where you separate JACKPOT from every other open-source genomics platform. None of them work in the environments three-letter agencies actually use.

### Air-gapped JACKPOT (Deployment Target H)

A version of JACKPOT designed to run entirely disconnected:

- **Offline package mirror**: every dependency, every container, every reference DB pre-bundled
- **Air-gap update bundle format**: signed, deterministic update tarballs that move via removable media
- **No phoning home, ever**: every dependency on external services becomes optional or mockable
- **Install on a single removable drive**: full install boots from a portable medium

This is the version that runs on USS Ronald Reagan during an outbreak investigation. Or in a tactical SCIF. Or at a CDC EOC during an actual emergency where they don't trust internet.

### Cross-Domain Solution support

JACKPOT becomes CDS-aware:

- **Data classification labels** native in the schema (UNCLASSIFIED, CUI, SECRET, etc.) — propagated through every pipeline, attached to every output
- **Sanitization pipelines** as first-class citizens: take a SECRET dataset, produce a CUI summary, produce a public dashboard view, all with DP and policy-driven redaction
- **High-side / low-side architecture**: a JACKPOT instance on the high side can produce content for a low-side instance via a CDS guard
- **Format-aware exports**: CDS guards work better with structured, known-schema formats — JACKPOT's PHA4GE alignment helps here

Concrete partner architecture: JACKPOT high-side ingests classified threat intelligence, joins with open-source pathogen surveillance from JACKPOT low-side instances, produces CUI bulletins for state health departments. Today this kind of fusion analysis is done in Excel.

### Tactical / disconnected operations

The "Pi cluster in a Pelican case" use case from your old notes, made real:

- **Edge-deployable** JACKPOT that runs on a Jetson Orin or Pi 5 cluster
- Local Dorado basecalling, local pipelines, local results
- **Sync-on-reconnect**: when the network comes back, it federates with the home tenant
- **Tamper-evident**: device pre-attests its hardware identity via TPM 2.0 / Secure Enclave

This is the version a forward-deployed DTRA or USAMRIID team takes to investigate an unknown disease outbreak in an austere environment. There is currently *nothing* in this space.

------

## Part 5 — AI Agent Security (The Newest Frontier)

Federal agencies are still figuring out how to authorize AI agents. This is wide-open territory and being early matters.

The LLM agents in your curriculum and game ideas have to be production-grade for federal use. Critical features:

### Agent identity and accountability

- Every agent has a SPIFFE identity
- Every action an agent takes is attributable in audit logs
- Tool access is policy-controlled per agent
- Agents authenticate to JACKPOT just like users do

### Prompt injection defense in depth

- **Input sanitization**: untrusted text (sample metadata, log outputs, web fetches) is wrapped in delimiters
- **Output filtering**: agent outputs scanned before action
- **Sensitive-data sandboxing**: agents working with classified data run only in classified-tier infrastructure
- **Tool allow-listing**: agents can only call tools their identity is authorized for, evaluated at every call
- **Model running mode**: production federal use of LLM agents with Claude or similar requires currently authorized FedRAMP High versions like Azure OpenAI authorized for IL6 (Secret) and Top Secret workloads, with cautious approaches to autonomous agent features and human-in-the-loop requirements

### Confidential AI inference

- Run inference inside TEEs (Phala, Anjuna, etc., or hyperscaler offerings)
- Protect model weights from operator visibility
- Protect inference inputs from operator visibility
- Attest the model identity to the user before they trust the response

### Agent OPSEC

- Every agent invocation logs: prompt + retrieved context + tools called + output + reasoning trace
- Agents that perform sensitive actions require dual-control human approval
- Anomaly detection on agent behavior — an agent suddenly trying to access new tool categories triggers alerts

JACKPOT could ship the first **AI agent framework with federal-grade controls baked in for genomics**. That's a moat measured in years.

------

## Part 6 — Compliance Roadmap (The Realistic Path)

You don't go from where JACKPOT is to IL6 in one step. The path is a sequence of authorizations, each unlocking the next.

| Phase       | Target                                  | Timeline                 | Investment                                  | Outcome                                                      |
| ----------- | --------------------------------------- | ------------------------ | ------------------------------------------- | ------------------------------------------------------------ |
| **Phase 0** | Architecture foundations (Part 2 above) | 12 months                | Engineering only                            | Architecture supports later certifications                   |
| **Phase 1** | NIST 800-53 Moderate self-attested      | 6 months overlap with P0 | Engineering + part-time security consultant | Most state public health agencies will adopt                 |
| **Phase 2** | FedRAMP Moderate ATO via agency sponsor | 12-18 months             | $250K-$500K + 3PAO + sponsor                | CDC, NIH, HHS adoption                                       |
| **Phase 3** | FedRAMP High ATO                        | 12 months from Phase 2   | $200K-$400K incremental                     | DoD IL5 path begins, since IL5 builds on FedRAMP High plus 10 additional FedRAMP+ controls |
| **Phase 4** | DoD IL4                                 | 6 months from Phase 3    | $150K incremental                           | Most DoD CUI workloads                                       |
| **Phase 5** | DoD IL5                                 | 6-9 months from Phase 4  | $200K-$300K + Game Warden or similar        | National Security Systems work                               |
| **Phase 6** | DoD IL6 / Cross-Domain                  | 12+ months from Phase 5  | $500K+ + classified partner                 | Classified outbreak investigation                            |

Big shortcut option: Second Front's Game Warden holds DISA Provisional Authorization at IL5; vendors deploying onto Game Warden inherit foundational security controls already validated by DISA — boundary protection, media controls, physical access, continuous monitoring, NSS FedRAMP+ overlay — and the platform automates Body of Evidence generation.

This is the path that lets a small team realistically reach IL5 in ~3 years rather than ~7. The platform-as-a-shortcut model is what made startups like ScaleAI achievable in defense.

------

## Part 7 — Reciprocity, Shared Architectures, and the Open Source Advantage

Here's the move most commercial vendors miss: AGPL-licensed open-source security infrastructure is *easier* to authorize, not harder, in many federal contexts.

- **Code is auditable**: agency security teams can read it. They like that.
- **No vendor lock-in concerns**: a key procurement criterion increasingly
- **Reciprocity**: a deployment pattern authorized at one agency is easier to re-authorize at another
- **Reference architectures**: NIST and CISA increasingly publish reference architectures using open-source components — JACKPOT could be one
- **Sovereign deployment friendly**: LMIC partners and allied nations care about source-available solutions; AGPL is the gold standard

The AGPL choice you already made is genuinely a strategic asset for federal deployment. Don't let anyone talk you into changing it.

------

## Part 8 — What This Costs (Realistically)

Let me not be coy about money, because this matters.

| Cost category                                | Range                           | Notes                                                  |
| -------------------------------------------- | ------------------------------- | ------------------------------------------------------ |
| **Phase 0 architecture rework**              | $0 (done as part of normal dev) | This is design discipline, not a separate spend        |
| **Security consulting (Phase 1-2)**          | $50K-$150K/yr                   | Part-time fractional security architect                |
| **3PAO assessor (Phase 2 FedRAMP Moderate)** | $250K-$500K                     | Fixed-cost vendor                                      |
| **Continuous monitoring tools**              | $50K-$100K/yr                   | SIEM, vulnerability scanning, FedRAMP-required tooling |
| **Compliance platform (optional)**           | $100K-$300K/yr                  | Drata, Vanta, or Game Warden                           |
| **HSM access**                               | $20K-$50K/yr                    | Cloud HSM is metered                                   |
| **Confidential compute**                     | $20K-$100K/yr                   | TEE VMs cost a premium over standard                   |
| **Penetration testing**                      | $50K-$150K/yr                   | Required for FedRAMP, recommended otherwise            |
| **Total to FedRAMP Moderate ATO**            | ~$500K-$1M over 18 months       |                                                        |
| **Total to IL5**                             | ~$1.5M-$3M over 3-4 years       | If using Game Warden; more if going alone              |

This sounds expensive until you see the revenue side: Integrate fast-tracked IL6 accreditation and deployed to a classified environment in under 12 months — paving the way for a $25M Phase III SBIR award. Federal contracts are large. One CDC IDIQ or a DTRA SBIR Phase III pays for the whole compliance journey several times over.

------

## Part 9 — The Pitch Each Agency Cares About

Different agencies care about different aspects. Tailor the pitch.

| Agency                       | What they care about                                   | The JACKPOT angle                                            |
| ---------------------------- | ------------------------------------------------------ | ------------------------------------------------------------ |
| **CDC**                      | Outbreak response, workforce, multi-state coordination | Federation + DP-public dashboards + workforce curriculum     |
| **HHS / ASPR**               | Pandemic preparedness, BARDA pipeline                  | FL across jurisdictions, MPC for vaccine effectiveness       |
| **NIH**                      | Privacy-preserving research collaboration              | HE-GWAS, TEE-genomics, iDASH-style competitions              |
| **FDA**                      | Foodborne outbreak attribution                         | Chain of custody, signed pipeline outputs, cross-domain      |
| **DTRA**                     | Biothreat assessment, attribution                      | Air-gapped + tactical + sequence screening + agent security  |
| **DHS / CISA**               | Critical infrastructure, biosecurity                   | Container supply chain, prompt injection defense, ICS-style hardening |
| **FBI WMDD**                 | Bio-attribution forensics                              | Append-only audit, chain of custody, signed forensics outputs |
| **NSA**                      | Cryptographic correctness, secure systems              | The whole privacy-preserving computation stack               |
| **IC (NCMI/NCTC)**           | Intelligence integration, cross-domain                 | CDS-aware design, classification labels, high/low side architecture |
| **DoD MEDCOM / USAMRIID**    | Force health protection, deployable                    | Edge deployment, tactical, austere environments              |
| **State Department / USAID** | Global health security, partner capacity               | Sovereign deployment, LMIC capacity building, federation with allies |

------

## What I'd Build First

Pragmatic prioritization, with the goal that 12 months from now you can pitch JACKPOT to a federal sponsor with a straight face.

1. **SPIFFE/SPIRE service identity** — the foundation everything else depends on
2. **OPA-based policy engine** — pull authz out of code, into auditable policies
3. **Sigstore-signed everything** — containers, pipelines, reference DBs
4. **Hash-chained WORM audit logs** — extend `pipeline_results` model platform-wide
5. **HSM-backed key management** — abstract behind PKCS#11 from day one
6. **Confidential JACKPOT (Target G)** — TDX VM deployment profile
7. **DP query layer** — wrap existing PostgreSQL queries with privacy budget
8. **FL coordinator** — NVIDIA FLARE integration as a federation mode
9. **Air-gapped install bundle** — proves you take disconnected ops seriously
10. **Agent identity & sandbox framework** — federal-grade LLM agent integration

Items 1-5 are the ATO-blocking architecture. Items 6-8 are the differentiators no competitor has. Items 9-10 are the moats.

In parallel, start building the compliance paperwork:

- System Security Plan (SSP) skeleton
- POA&M template
- Continuous monitoring strategy
- FedRAMP authorization-readiness checklist
- Find an agency sponsor for Phase 2 ATO

------

## TL;DR

To make JACKPOT trusted in the most security-conscious environments:

1. **Ship the architectural foundations now** — SPIFFE, OPA, Sigstore, HSMs, WORM audit, signed everything. These are non-negotiable and brutal to retrofit.
2. **Treat privacy-preserving computation as product features** — FL, DP, HE, MPC, TEEs aren't curriculum content alone, they're capabilities baked into JACKPOT itself.
3. **Plan for air-gap and cross-domain from day one** — this is the differentiator that opens IC and DoD doors.
4. **Walk the compliance ladder deliberately** — NIST Moderate → FedRAMP Moderate → FedRAMP High → IL4 → IL5 → IL6, with realistic 3-4 year timeline to IL5.
5. **Use platform shortcuts where they exist** — Game Warden for IL5, Confidential Containers for TEE, Phala/Anjuna for confidential AI.
6. **Lean into AGPL** — open source is an asset for federal procurement, not a liability.
7. **AI agent security is wide-open** — be early.

What you'd end up with is a platform that does what no other genomics tool does: **provably private cross-jurisdictional outbreak investigation, with federal-grade compliance, deployable from a SCIF to a sewershed, with the same codebase**. Nobody else is in that lane. Nobody else is trying to be.

What part do you want to dig into next? I could draft the SSP outline, sketch a SPIFFE/SPIRE rollout plan for JACKPOT specifically, write up what a Phase 1 NIST Moderate self-attestation looks like in practice, or design the air-gapped bundle format. Pick your weapon.

Let me dig into each of these researchers, with primary focus on Stephanie Forrest and her Biodesign team. I want to actually read their recent work, not guess.Excellent — this is a really good match. Let me dig deeper into her current work, lab members, and recent publications.This is incredible. There's literally an NSF-funded Forrest+Trieu+Halden+Lee project on **wastewater epidemiology privacy** — basically a JACKPOT-adjacent project that already exists. Let me dig into this and the related lab members.Excellent. Now I have what I need. Let me also briefly check on Forrest's "Crispy" / n-variant work and her cyber-attribution work, since those are likely to be the most relevant to JACKPOT.OK I have enough. And the answer is more interesting than expected — there's already a published collaboration between Forrest, Trieu, Lee, and Halden on **encrypted data-sharing for wastewater-based epidemiology** (NSF CICI 2021-2024, paper in *Science of the Total Environment* August 2024). JACKPOT isn't pitching into a vacuum; it's pitching into an active research program these people are already running.

Here's my read.

------

## The Forrest Lab Profile (For Context)

Stephanie Forrest's career signature is unique and matters for how you'd pitch JACKPOT to her:

| Theme                         | What she did                                                 | Why it matters for JACKPOT                                   |
| ----------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **Computational immunology**  | First practical anomaly intrusion-detection system; "self vs nonself" detection inspired by T-cell maturation | She thinks of cybersecurity *as* immune surveillance. Pathogen genomic surveillance is the natural analog. |
| **Diversity as defense**      | Instruction-set randomization, n-variant systems, **Crispy** (CRISPR-inspired DoS defense) | She doesn't think monocultures are secure. Period.           |
| **Noncryptographic PETs**     | Negative-selection-based representations for genomic data    | She has *opinions* about cryptography being overhyped        |
| **Cyber-attribution**         | Theoretical and data-driven models of attribution, data breaches, botnet takedowns | Bio-attribution is structurally similar                      |
| **Automated software repair** | Bio-inspired patching of vulnerabilities (2019 ICSE Most Influential Paper) | Supply chain security with an evolutionary twist             |
| **Biological modeling**       | Adaptive immune response, influenza, SARS-CoV-2, vaccine design, cancer | She has biology chops, not just CS                           |
| **Cyberpolicy**               | Jefferson Science Fellow at U.S. State Department 2013-2014  | She's policy-engaged. DURC, dual-use, AI-bio safety would land. |

She funds out of NSF, DARPA, and Air Force Research Laboratory. The Biodesign Center for Biocomputing, Security and Society's stated mission is literally "**translating insights between computer science and biology, with a focus on understanding and mitigating malicious behavior in complex systems**." JACKPOT is — almost suspiciously well — a concrete instantiation of that mission.

### The team around her that matters for JACKPOT

- **Ni Trieu** (Asst. Prof, SCAI; affiliate of Biodesign Center) — applied cryptography specialist, **Private Set Intersection** is her signature primitive, postdoc'd under Dawn Song at Berkeley. Just received Amazon Research Award March 2026, two PSU papers at EUROCRYPT, on 2026 PCs for CCS and CRYPTO. She's hot.
- **Heewook Lee** (Asst. Prof, SCAI; Biodesign Center) — computational biology, TCR-epitope binding prediction, iterative attack-and-defend ML frameworks, Lane Fellow alum from CMU.
- **Rolf Halden** (Prof, Biodesign Center for Environmental Health Engineering) — runs the **National Sewage Sludge Repository** (200+ sites), wastewater-based epidemiology pioneer.

**The four of them already have a published JACKPOT-shaped paper.** Driver, Ahsan, Piske, Lee, Forrest, Halden, Trieu — *"Encrypted data-sharing for preserving privacy in wastewater-based epidemiology"*, Science of the Total Environment, August 2024. NSF CICI grant 2021-2024, $499,592. They've also published an ethics-of-WBE paper noting that "innovation has outpaced the ability of social and legal mechanisms to keep up."

This is your warm pitch. Not a cold one.

------

## Q1: What Aspects Would Forrest's Team Want to Collaborate On?

I'd group hooks into three buckets. The first is the slam dunk; the others get more speculative.

### 🎯 Bucket 1: Direct continuation of their existing program

**1.1 — Wastewater epidemiology privacy at federated scale**

The Driver et al. 2024 paper proved encrypted data-sharing for WBE on a small scale. The natural sequel is: *what does this look like when you have a federation of dozens of municipalities, each running JACKPOT, each contributing wastewater Freyja signals?* That's a 5-year follow-on grant waiting to happen. The CICI program has a successor. The Forrest+Trieu+Lee+Halden combo has the prior art and the receipts.

JACKPOT's role: be the *production platform* the protocols target. Their NSF paper invented the math; JACKPOT becomes where it's deployed to actual public health labs. That's a much stronger position than "we're building a new system" — it's "we're building the deployment vehicle for the work you've already done."

**1.2 — Cross-jurisdictional outbreak detection via PSI**

This is Trieu's bread and butter. Her 2024 PoPETs paper introduced multi-party private set intersection cardinality (PSI-CA) allowing n parties to compute intersection size without revealing additional information, designed to avoid expensive public-key operations under semi-honest adversaries. That is *exactly* the primitive needed for "do three states each have samples that genotype-match without showing each other their line lists?"

JACKPOT's federation deployment target (E) is a real-world deployment opportunity for Trieu's protocols. She'd be motivated to collaborate because it puts her cryptography in front of actual users instead of benchmark datasets.

**1.3 — Public attitudes and ethics governance for the platform itself**

The 2022 nationwide WBE-acceptance survey (3,083 respondents) and the wastewater-monitoring-ethics paper aren't side projects for them — they're how they think about the technical work. Forrest specifically said that "innovation has outpaced the ability of social and legal mechanisms to keep up." JACKPOT proposing federation governance, dual-use review for sequence screening, and community engagement protocols would land hard.

### 🧬 Bucket 2: Forrest's deeper themes applied to JACKPOT

**2.1 — JACKPOT as a computational immune system for public health**

This is the framing most likely to genuinely excite her. Pathogen genomic surveillance *is* immune surveillance at population scale. The platform itself can be designed with:

- **Self/nonself anomaly detection** for tenant behavior — a tenant suddenly running unusual queries flagged the way a B-cell flags a foreign antigen
- **Negative selection** for inputs — sequences that don't match known benign patterns get extra scrutiny
- **Affinity maturation** for detection rules — automated evolution of pipeline detectors against new pathogens

This isn't metaphor for marketing. It's how she'd actually build it. And it makes JACKPOT genuinely novel architecturally rather than just well-engineered.

**2.2 — Diversity-as-defense for the platform stack**

Forrest pioneered the idea that running one operating system everywhere is a security failure. JACKPOT instances could:

- Run pipeline workers on **N-variant container images** (different distros, different toolchains, same outputs) so a supply-chain compromise doesn't propagate
- Use **instruction-set randomization** for sensitive subprocesses
- Use **automated software repair** techniques to patch vulnerabilities in dependencies before maintainers do

This is exactly her wheelhouse. It's also a credible federal-grade differentiator no other platform offers.

**2.3 — Noncryptographic PETs for genomic data**

Her negative-selection-based representations for genomic data work is directly relevant. JACKPOT could integrate this as a *complement* to crypto — for cases where computation has to be fast, you accept slightly weaker guarantees, but you avoid the HE performance penalty. This is a genuine research contribution she'd want to publish.

**2.4 — Bio-attribution forensics**

Engineered vs. evolved pathogen attribution is structurally similar to cyber-attribution, which she's spent decades on. Her data-driven attribution models could be ported. This is one of those collaboration angles where her *prior* work plus your *application domain* makes a paper neither of you write alone.

### 🌐 Bucket 3: Adjacent and policy-flavored

**3.1 — Dual-use review and AI-bio policy**

Her State Department fellowship plus her Computing Research Association Government Affairs chair role means she has actual policy reach. The DURC/PEPP training gap and the AI-bio convergence policy work are within her interest range. JACKPOT as the open-source platform that *implements* DURC controls procedurally (sequence screening pipelines, IBC review workflows) would be a natural collaboration target — and a credible joint NSF SaTC or NIH ELSI proposal.

**3.2 — Software repair for the supply chain**

GenomicSurveillance pipelines depend on hundreds of bioinformatics tools, many of them academic projects with one maintainer. Forrest's automated software repair work could be used to *automatically patch* known-vulnerable bioinformatics dependencies as part of JACKPOT's CI/CD. This is a paper-quality angle.

### What the others would care about

| Person                                 | Their hook                                                   |
| -------------------------------------- | ------------------------------------------------------------ |
| **Ni Trieu**                           | PSI/PSI-CA protocols for outbreak detection; HE-GWAS deployment; federated analytics; reviewing JACKPOT's cryptographic claims for soundness |
| **Heewook Lee**                        | ML on private genomic data; iterative attack-and-defend frameworks for JACKPOT's classifier models; TCR/epitope work for vaccine-design modules |
| **Rolf Halden**                        | Wastewater integration; the National Sewage Sludge Repository as a synthetic-data goldmine for testing |
| **Chenkai Weng** (SCAI applied crypto) | Formal correctness of any ZK or MPC claims; potential co-author on a JACKPOT crypto paper |
| **Michel Kinsy** (ASCS Lab)            | Hardware acceleration for HE on JACKPOT — relevant if you ever push HE-GWAS at scale |
| **Hokeun Kim** (IoT/cyber-physical)    | The edge-JACKPOT story — Pi cluster, Jetson, MinION-in-the-field secure deployment |
| **Gail-Joon Ahn** (CTF Center)         | Policy frameworks, federation governance, identity management at scale |

------

## Q2: What Would Forrest's Team Be Most Critical Of?

This is the more useful section, because it tells you what to fix *before* you pitch.

### 🔴 Forrest's likely critiques

**"You're treating cryptography as a complete answer."** This is the single biggest one. Her career is partly a reaction to crypto-maximalism. She'd point out that encrypted data-sharing in WBE — even her own paper — still leaks: traffic analysis reveals which catchments are sending what when; the *fact* that you sequenced reveals operational tempo; aggregate signals enable inference attacks; metadata is harder to encrypt than data. JACKPOT showcasing TEEs and HE without addressing side-channels and inference attacks would get a blunt response.

**The fix:** include explicit threat-model docs that distinguish what crypto solves from what it doesn't. Pair every crypto claim with a noncryptographic complement (anomaly detection, decoys, traffic shaping). Cite her work where appropriate.

**"Your security posture is static."** JACKPOT today — even with all the federal-grade architecture I sketched — has a fixed perimeter. Her immune-system framing demands a *learning* defense. Anomaly detection that adapts to new threats. Negative selection that evolves new detectors against novel attacks. The platform should learn what "normal" pipeline behavior looks like and flag deviations *automatically*.

**The fix:** propose collaboration explicitly on adding an immune-system-inspired anomaly layer to JACKPOT. Don't pitch a finished platform and ask for blessing — pitch a specific gap and ask her team to fill it.

**"You're a monoculture."** One codebase, one container image set, one schema. From her perspective, this is brittle. A supply-chain attack on the JACKPOT base image affects every deployment. This is exactly what diversity-as-defense exists to mitigate.

**The fix:** acknowledge this and propose an N-variant deployment mode as future work where her group can publish.

**"Your cyber-attribution story is missing entirely."** When (not if) someone tries to attack a JACKPOT instance — to exfil data, plant misinformation, poison a pipeline — what's the attribution mechanism? Audit logs aren't attribution; they're evidence. She'd want to see deception infrastructure (decoy queries, honeypot tenants, behavioral fingerprinting) as part of the design.

**The fix:** add an "attribution and deception" section to your security architecture that explicitly cites her prior work. Or even better, propose it as a joint PhD project.

**"What about misuse?"** Her ethics-of-WBE paper specifically calls out "personally identifiable data" risks even in supposedly anonymous wastewater data. JACKPOT scales those risks 100x. As a former State Department cyberpolicy fellow, she'd ask:

- What stops an authoritarian government from using JACKPOT for surveillance creep?
- How does JACKPOT's federation model handle asymmetric power between HIC and LMIC participants?
- What's the kill-switch when JACKPOT is being used in ways the community didn't anticipate?

**The fix:** have answers. Genuine ones. AGPL alone isn't enough. Talk about community governance, ethics review boards, refusal-to-deploy criteria. She'll respect "we don't have a complete answer but here's how we're trying to think about it" much more than handwaving.

**"The educational angle isn't built in."** The Biodesign Center is in Biodesign for a reason — Forrest cares about *integrating computation with biology and health in novel ways*, and explicitly contrasts that with technologists "isolated from those who actually use or are affected by it on a daily basis." A JACKPOT pitch that's pure technical platform with curriculum bolted on would feel exactly like the failure mode she described. The Academy and gamification angles need to be central, not peripheral.

**The fix:** lead with workforce/education when pitching. Forrest is *more* interested in JACKPOT-as-teaching-instrument than JACKPOT-as-federal-tool, even though both are real.

### 🟡 Trieu's likely critiques

**"Your HE/PSI claims are imprecise."** "We support homomorphic encryption" doesn't mean anything to her. CKKS vs BFV vs BGV with what parameters at what security level under what threat model? "We support PSI" — there are dozens of PSI protocols with different cost profiles and different security assumptions. She'd want documents listing exact protocols, parameter choices, and proven threat models.

**"Your federation protocol needs a formal proof."** She's a CCS/EUROCRYPT-grade cryptographer. If JACKPOT's federation does anything cryptographic — attestation, key exchange, joint computation — she'd want it formally specified and proven. "We use TLS" isn't a proof.

**"You'll have re-identification leaks you don't expect."** Her wastewater work covered exactly this. Aggregate genomic signals leak more than people assume.

### 🟠 Lee's likely critiques

**"Your synthetic data isn't representative."** The SDV/PATE-GAN-style synthetic data we discussed would be subjected to membership-inference attacks that he'd run.

**"Your ML pipelines are vulnerable to your own attacks."** He literally publishes iterative attack-and-defend frameworks for ML. Any ML in JACKPOT (AMR classifier, pathogen ID model) would be expected to ship with red-team results.

### 🟢 Halden's likely critique

**"You don't understand the wet-side enough."** He'd push you to talk to actual sewage engineers about sampling cadence, sample preservation, false-positive failure modes. JACKPOT is bioinformatics-first; the inputs come from people whose constraints aren't bioinformatics.

------

## How I'd Actually Approach Them

Pragmatic suggestions, since you have the existing relationship:

**1.** Lead the Forrest pitch with the **immune-system framing**, not the FedRAMP-IL5 framing. The federal-compliance story is real but it's not what energizes her. JACKPOT-as-computational-immune-system-for-public-health is.

**2.** Bring a specific, scoped collaboration proposal — not "want to work together?" but "here's a specific anomaly-detection layer for federation traffic that needs your group's expertise." Concrete asks get concrete responses.

**3.** Acknowledge the wastewater paper explicitly. Their work isn't just adjacent — it's the closest published prior art. Build on it instead of around it.

**4.** Pitch Trieu separately and concretely, with an actual cryptographic problem statement. She gets requests; the ones that lead to publications get her time.

**5.** The ASCS Lab folks (Kinsy in particular) are a different kind of collaboration — hardware-accelerated HE for JACKPOT GWAS would be a genuine contribution but it's a different timeline from the Biodesign collaborations. Keep them on a separate track.

**6.** **Remember Glen-the-builder vs. JACKPOT-the-project** are now separate things in their minds (per the April 2026 ADHS/ASU decoupling). The pitch is "I'm working on a project that builds on the work your team published" — not "I want to bring JACKPOT back into ASU." That's actually a *better* position because it's an open-source platform extending their research, not a competitor.

**7.** The criticism is the gift. Every critique above is a section of a stronger Phase-2 grant proposal. If Forrest tells you "your security posture is static," you say "yes, want to write the NSF SaTC proposal with us to fix that?" The path from critique to collaboration is short.

------

## TL;DR

Forrest's lab and the Biodesign Center are not just *interested* in JACKPOT-shaped work — they're already doing it. The Forrest+Trieu+Lee+Halden quartet has a published, NSF-funded paper on encrypted wastewater epidemiology data sharing. JACKPOT is the natural production deployment vehicle for the protocols they're inventing. The cleanest collaboration hook is wastewater epidemiology at federation scale; the deepest hook is JACKPOT-as-computational-immune-system; the best policy hook is dual-use governance via her State Department network.

The critiques are predictable and, frankly, correct: don't oversell crypto, don't be a monoculture, don't have a static defense posture, don't ignore misuse, don't bolt on education as an afterthought. Address those before you walk in the door and you'll have a real partnership to build on.

What angle do you want to push on next? I could draft a one-page collaboration brief tuned to Forrest's interests, sketch the immune-system-anomaly-detection JACKPOT module, or design the wastewater-federation extension that builds on the Driver et al. 2024 paper. Pick your angle.

This is the exciting one. Let me actually think through it carefully because "JACKPOT-as-computational-immune-system" can either be a marketing metaphor or a genuine architectural commitment, and the difference matters.OK, let me actually map this out. Three sections, each substantive enough to act on tomorrow.

------

# Part 1 — Software Components for JACKPOT-as-Computational-Immune-System

The trick is to commit to the architecture, not the metaphor. Every component below maps a real biological function to a real piece of software, with concrete integration points to the existing JACKPOT stack (FastAPI, SQLAlchemy, Postgres, Nextflow). I've organized them by immune subsystem because that's how Forrest's lab thinks about it — and because it makes the gaps obvious.

## 1.1 — The "Self" Representation Layer

The immune system can only detect nonself if it knows self. This is the foundation everything else depends on, and it's the part most cyber-AIS implementations get wrong by skipping.

| Component                    | What it does                                                 | Implementation                                               |
| ---------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **`jackpot-self-profiler`**  | Builds and continuously updates a behavioral baseline per tenant per identity | Python service consuming OpenTelemetry traces; writes to TimescaleDB |
| **Operation-graph schema**   | Stores normal sequences of API calls, pipeline invocations, query patterns as graphs | New tables in Postgres; `pg_audit` for capture               |
| **Representation library**   | Encodes operations into the high-dimensional vector space NSA needs | Python lib wrapping Forrest's negative-selection representation work |
| **Tenant fingerprint store** | Per-tenant "self" profile, versioned and auditable           | New schema in Postgres, signed snapshots in S3/MinIO         |
| **eBPF kernel telemetry**    | System-call-level "self" data (the original Forrest 1996 substrate) | Falco + custom eBPF programs                                 |

Implementation note: this is the part you can't outsource to a research collaborator because it's deeply tied to JACKPOT's existing data model. Your team builds the substrate; researchers build detectors on top.

## 1.2 — Detector Generation (Negative Selection / Clonal Selection)

The immune system generates random detectors and culls the ones that match self. What's left detects nonself. Negative selection algorithms simulate human immune mechanisms for network anomaly detection, with recent 2024 work using self-antigen-based candidate detectors with complementary space representation, and 2025 multi-layer immune tolerance approaches reducing false positives.

| Component                       | Function                                                     | Stack                                          |
| ------------------------------- | ------------------------------------------------------------ | ---------------------------------------------- |
| **`jackpot-nsa`**               | Negative selection algorithm — generates detectors that don't match self | Python; reference: V-detector, real-valued NSA |
| **`jackpot-clonalg`**           | Clonal selection — evolves high-affinity detectors over time | DEAP genetic algorithm framework               |
| **`jackpot-dca`**               | Dendritic cell algorithm — context-aware danger signal aggregation | Python; reference: Greensmith DCA              |
| **Detector population manager** | Versioning, retirement, promotion of detectors               | Postgres + Celery jobs                         |
| **Affinity scoring engine**     | Measures how well detectors match observed nonself           | NumPy / GPU acceleration via JAX               |
| **GPU acceleration**            | Real-valued NSA in high-dim space is expensive               | CUDA for self-tolerance check                  |

Forrest's lab has decades of expertise here. The right play is to make `jackpot-nsa` and `jackpot-clonalg` real Python packages with semantic versioning that her PhD students can publish *against* — they extend the algorithms, you ship the platform. Their papers cite JACKPOT as the deployment environment.

## 1.3 — Innate Immunity (Fast, Pattern-Based)

Before adaptive defenses kick in, you want fast pattern recognition for known threats. This is the part that overlaps with conventional security tooling.

| Component                                | Maps to                                          | Stack                                              |
| ---------------------------------------- | ------------------------------------------------ | -------------------------------------------------- |
| **Pattern-Recognition Receptors (PRRs)** | Signature detection for known threat patterns    | Sigstore signature verification, gitleaks, semgrep |
| **TLR-equivalents**                      | Toll-like receptors for specific threat classes  | Falco rules, Suricata for network                  |
| **Complement system**                    | Tagging suspicious objects for downstream action | OPA policy bundles invoked at PEPs                 |
| **Phagocytes**                           | Auto-cleanup of confirmed threats                | Quarantine workers, container kill scripts         |

These are mostly off-the-shelf and you wire them together. The novelty is in the integration with the adaptive layer.

## 1.4 — Adaptive Immunity (Learning, Memory)

This is where JACKPOT gets genuinely novel. The platform should *learn* what attacks against it look like.

| Component               | Function                                                    | Stack                                            |
| ----------------------- | ----------------------------------------------------------- | ------------------------------------------------ |
| **B-cell equivalent**   | Memory of confirmed-malicious patterns                      | Postgres threat memory tables; STIX/TAXII format |
| **T-cell equivalent**   | Cellular response — actions taken against confirmed nonself | OPA policies, automated remediation playbooks    |
| **MHC presentation**    | How suspicious activity surfaces to operators/agents        | Notification system, audit log highlights        |
| **Affinity maturation** | Detectors get better at recognizing recurring threats       | Online learning with `jackpot-clonalg`           |
| **Memory cells**        | Long-lived detectors for known adversaries                  | Detector population store with retention         |
| **Anergy / tolerance**  | Suppress detectors that fire on legitimate variation        | Allowlist learning from operator feedback        |

The "tolerance" mechanism is the make-or-break piece. Cyber-AIS systems historically failed because they generated too many false positives. Forrest knows this. Building a robust tolerance layer is what would make her team interested rather than dismissive.

## 1.5 — Diversity Layer (Crispy / N-Variant)

Forrest's other career-defining insight: monocultures are brittle. JACKPOT should run multiple variants of itself in parallel and use disagreement as a signal.

| Component                         | Function                                            | Stack                                                     |
| --------------------------------- | --------------------------------------------------- | --------------------------------------------------------- |
| **N-variant container generator** | Build same-API containers from different toolchains | Bazel / Nix for reproducible builds; multiple base images |
| **Variant orchestrator**          | Run N variants in parallel for sensitive operations | Kubernetes with custom scheduler                          |
| **Disagreement detector**         | Outputs differ across variants → alert              | Result-comparison service in pipeline framework           |
| **Instruction-set randomization** | For specific high-risk components                   | LLVM-based compilation variants                           |
| **Pipeline-version diversity**    | Same pipeline implemented in different frameworks   | Nextflow + WDL + Snakemake parity for critical paths      |

This is also where the Crispy work fits — a CRISPR-inspired technique for defeating DoS attacks against n-variant systems is uniquely Forrest's. Implementing Crispy in JACKPOT for federation traffic would be a paper-grade collaboration.

## 1.6 — Inter-Instance Signaling (Cytokines)

In a federation, individual JACKPOT instances need to share threat intelligence the way immune cells share cytokine signals.

| Component                    | Function                                 | Stack                                             |
| ---------------------------- | ---------------------------------------- | ------------------------------------------------- |
| **STIX/TAXII server**        | Standard threat-intel sharing            | OASIS-compliant TAXII 2.1                         |
| **Cytokine bus**             | Pub/sub for federation-wide signals      | NATS or Kafka with mTLS                           |
| **Aggregate threat picture** | Cross-instance threat dashboard          | Auspice-style visualization                       |
| **Federation-level NSA**     | Joint detector training across instances | FL Coordinator + Trieu's PSI for private training |

This is where Trieu's PSI work earns its keep — federated immune signaling **without revealing the local immune state** to other federation members. That's a real cryptographic problem with a real solution she works on.

## 1.7 — Attribution & Deception (Where Forrest's Cyber-Attribution Work Plugs In)

| Component                     | Function                                                  | Stack                                           |
| ----------------------------- | --------------------------------------------------------- | ----------------------------------------------- |
| **Honeytokens**               | Fake credentials, fake samples, fake federation endpoints | Custom; integrated with audit logs              |
| **Behavioral fingerprinting** | Adversary identification across sessions                  | Time-series ML on operation graphs              |
| **Decoy tenants**             | Empty tenants that exist only to attract probes           | Standard JACKPOT tenants with monitor-only mode |
| **Attribution database**      | Cross-incident linking of adversary signatures            | Graph DB (Neo4j)                                |
| **Adversary-model catalog**   | MITRE ATT&CK + custom bio-platform TTPs                   | Public + private catalogs                       |

## 1.8 — The Tolerance / Regulation Layer (Anti-Autoimmune)

The piece that prevents JACKPOT from attacking itself. Critical for production use.

| Component                        | Function                                            | Stack                                   |
| -------------------------------- | --------------------------------------------------- | --------------------------------------- |
| **Anomaly review queue**         | Human-in-the-loop confirmation for novel patterns   | Standard task queue in JACKPOT UI       |
| **Regulatory T-cell equivalent** | Suppress detectors that consistently false-positive | Automated detector retirement           |
| **Tolerance learning**           | Adapt to legitimate platform evolution              | Online learning with operator feedback  |
| **Autoimmune detection**         | Self-monitoring for the immune system itself        | Meta-detectors that watch the detectors |

## 1.9 — How These Fit Into Existing JACKPOT Architecture

```
┌────────────────────────────────────────────────────────────┐
│  JACKPOT API (FastAPI)              ──────────► OPA PEP    │
│         │                                          │       │
│         ▼                                          ▼       │
│  ┌──────────────┐  ┌──────────────────────────────────┐    │
│  │ Existing     │  │  IMMUNE SUBSYSTEM (NEW)          │    │
│  │ business     │  │  ┌─────────────────────────────┐ │    │
│  │ logic        │  │  │ 1.1 Self profiler           │ │    │
│  │              │  │  │ 1.2 NSA / Clonalg / DCA     │ │    │
│  │              │  │  │ 1.3 Innate IDS              │ │    │
│  │              │  │  │ 1.4 Adaptive memory         │ │    │
│  │              │  │  │ 1.5 N-variant orchestrator  │ │    │
│  │              │  │  │ 1.7 Attribution & deception │ │    │
│  │              │  │  │ 1.8 Tolerance layer         │ │    │
│  │              │  │  └─────────────────────────────┘ │    │
│  └──────┬───────┘  └──────────┬───────────────────────┘    │
│         │                     │                            │
│         ▼                     ▼                            │
│  ┌──────────────┐  ┌──────────────────┐                    │
│  │ Postgres     │  │ TimescaleDB +    │                    │
│  │ (existing)   │  │ Vector DB +      │                    │
│  │              │  │ Detector store   │                    │
│  └──────────────┘  └──────────────────┘                    │
└────────────────────────────────────────────────────────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │ Federation cytokine bus│ ◄── 1.6
                  │ (STIX/TAXII over NATS) │
                  └────────────────────────┘
```

**The honest engineering estimate:** sections 1.1, 1.4, and 1.8 are 12-month efforts with your existing engineering team. Sections 1.2, 1.5, and 1.7 are 18-24 months with research collaboration. Section 1.6 is shorter (6 months) but needs Trieu's PSI integration.

------

# Part 2 — Making Education and Training Foundational (Not Bolted On)

The failure mode I want to avoid: shipping JACKPOT-AIS as a product and then writing curriculum about it. That makes the curriculum derivative. The opposite move — designing both *together* — is what makes this Biodesign-Center-grade.

## 2.1 — The Foundational Design Principles

**Every code component ships with its curriculum module.** Not as a README. As a dedicated `course/<module>/` directory with notebooks, scenarios, exercises, and assessments. The platform and the curriculum are the same artifact.

**Every privacy or immune technique is paired with the attack it defends against.** Students never learn negative selection without first running an attack that bypasses naive signature detection. Pedagogy of contrast.

**Every capstone project lands as a JACKPOT contribution.** Best student detector becomes a candidate `jackpot-clonalg` detector population seed. Best red-team writeup becomes part of the adversary catalog. Students literally make JACKPOT better.

**Every assessment is executable.** Curriculum modules have CI. If a module's exercises stop working because JACKPOT changed, the build breaks. No stale tutorials.

## 2.2 — The Curriculum-as-Code Layout

```
jackpot/course/
├── immunology/
│   ├── 01-self-nonself/
│   │   ├── SKILL.md
│   │   ├── lecture.ipynb
│   │   ├── lab-attack.ipynb           # First, you're the attacker
│   │   ├── lab-defend.ipynb           # Then, you build a detector
│   │   ├── scenario.yaml              # Synthetic data + answer key
│   │   ├── assessment.py              # Auto-graded
│   │   └── badge.sigstore.bundle      # Signed credential template
│   ├── 02-negative-selection/
│   ├── 03-clonal-selection/
│   ├── 04-dendritic-cells/
│   ├── 05-diversity-as-defense/
│   ├── 06-attribution/
│   └── 07-tolerance-and-autoimmunity/
├── privacy/
│   ├── 01-threat-models/
│   ├── 02-deidentification-fails/
│   ├── 03-differential-privacy/
│   ├── 04-federated-learning/
│   ├── 05-homomorphic-encryption/
│   ├── 06-secure-mpc/
│   ├── 07-private-set-intersection/
│   └── 08-trusted-execution/
├── biosecurity/
│   ├── 01-sequence-screening/
│   ├── 02-durc-review/
│   ├── 03-engineered-or-evolved/
│   └── 04-ai-bio-convergence/
└── platform/
    ├── 01-jackpot-internals/
    ├── 02-pipeline-engineering/
    ├── 03-federation/
    └── 04-deployment-targets/
```

Each module is a directory with the same shape. New researchers contributing modules learn the shape once. Students navigating the curriculum experience a consistent grammar.

## 2.3 — The Foundational Pedagogical Pattern

Every module follows the same six-stage flow, drawn from CTF pedagogy research:

```
┌────────────────────────────────────────────────────────────┐
│  1. MOTIVATION   "Here's the attack that ruins your day"   │
│  2. EXPLORATION  "Try the attack yourself in a sandbox"    │
│  3. CONCEPT      "Here's the principle that defeats it"    │
│  4. IMPLEMENT    "Build a working defense in JACKPOT"      │
│  5. EVALUATE     "Red team your defense; measure efficacy" │
│  6. CONTRIBUTE   "Submit your work back as a PR / paper"   │
└────────────────────────────────────────────────────────────┘
```

The "CONTRIBUTE" stage is the one that makes this Biodesign-grade rather than bootcamp-grade. Foldit got peer-reviewed papers because players' designs landed in the actual research pipeline. JACKPOT modules can do the same.

## 2.4 — The Three Tracks

**Track A: Defenders of JACKPOT** *(undergraduate / professional)* Learn by attacking JACKPOT in safe sandboxes. Earn defender badges. Graduate with a portfolio of detectors and writeups. Hireable as junior security analysts at public health labs.

**Track B: Builders of JACKPOT** *(graduate / advanced practitioner)* Learn by extending JACKPOT modules. Add new detector algorithms, new pipelines, new privacy primitives. Capstone is a merged PR. Graduate with publications and platform commits.

**Track C: Architects of JACKPOT** *(faculty / senior researchers)* Lead module ownership. Co-author research papers. Train Track A and B students. Get listed as JACKPOT module maintainers in `OWNERS.md`.

The tracks aren't sequential — a Track A defender can become a Track C architect over time, but they don't have to. Each track is complete in itself.

## 2.5 — Credentialing as a Cryptographic First-Class Citizen

Earned competencies become signed JWTs issued by JACKPOT itself. Verifiable via standard OIDC. Public health agencies can verify "completed Module immunology/02 with score X on date Y" without contacting JACKPOT.

| Credential level     | Bar                                             |
| -------------------- | ----------------------------------------------- |
| **Module pass**      | Passed assessment for one module                |
| **Track completion** | Passed all modules in a track                   |
| **Maintainer**       | Owns a module, has merged 5+ PRs, peer-reviewed |
| **Architect**        | Module designer, named in academic paper        |

This becomes a real credential ecosystem with one significant property: every credential references the exact JACKPOT version it was earned against, so it ages gracefully and the curriculum can evolve without invalidating prior earnings.

## 2.6 — How Forrest's Research Becomes the Curriculum

This is the conceptual win: you don't write curriculum *about* her work, you let her work *be* the curriculum, and the modules become the deployment vehicle for her teaching.

| Forrest research theme                    | Becomes module                             |
| ----------------------------------------- | ------------------------------------------ |
| Self-nonself discrimination (1994)        | `immunology/01-self-nonself`               |
| A sense of self for Unix processes (1996) | `immunology/02-negative-selection`         |
| Clonal selection for intrusion detection  | `immunology/03-clonal-selection`           |
| Dendritic cell algorithm + danger theory  | `immunology/04-dendritic-cells`            |
| Instruction-set randomization, n-variants | `immunology/05-diversity-as-defense`       |
| Cyber-attribution via behavioral models   | `immunology/06-attribution`                |
| Crispy and adversarial robustness         | `immunology/07-tolerance-and-autoimmunity` |
| Noncryptographic PETs                     | `privacy/02-deidentification-fails`        |
| Computational immunology of pathogens     | `biosecurity/03-engineered-or-evolved`     |

Her PhD students teach the modules. The modules cite her papers as primary sources. The badges are co-signed by JACKPOT and the Biodesign Center. Win-win-win.

------

# Part 3 — Collaboration Scaffolding (The Hardest Part)

This is the part that determines whether the whole vision actually happens or dies in coordination friction. Building software with researchers across multiple labs — none of whom report to you, all of whom have their own funding, publication pressures, and timelines — is genuinely the hardest engineering problem here.

Here's how I'd structure it.

## 3.1 — The Monorepo with Research Sandboxes

The April 2026 P0d monorepo migration was already planned. Extend it for research collaboration:

```
Midnight-Oil-Innovation/jackpot/
├── backend/           # production, semver, AGPL
├── frontend/
├── cli/
├── schema/
├── pipelines/
├── deploy/
├── course/            # curriculum modules (Section 2)
├── research/          # NEW — experimental, lower stability bar
│   ├── forrest-lab/   # owned by Biodesign Center
│   │   ├── nsa/
│   │   ├── clonalg/
│   │   ├── crispy/
│   │   └── README.md  # owners, contact, paper refs
│   ├── trieu-lab/
│   │   ├── psi/
│   │   ├── psi-ca/
│   │   └── federated-tracing/
│   ├── lee-lab/
│   ├── halden-lab/
│   └── community/     # external contributors
├── rfc/               # NEW — architectural decisions
├── bench/             # NEW — shared benchmarks
├── synthetic/         # synthetic data fixtures
└── papers/            # bibliography of work that cites JACKPOT
```

The `research/` directory has different rules than `backend/`:

- Lower CI bar (must build, must have tests, but no AGPL-Production stability promise)
- Each lab's directory has its own OWNERS file
- Promotion path from `research/` to `backend/` via RFC + review
- Research code may be experimental; production code is reviewed and stable

This is the **Linux kernel staging tree pattern** applied to a research collaboration. It works because it gives experimental work a place to live without contaminating production.

## 3.2 — The RFC Process

Architectural decisions affecting multiple labs go through RFCs. This is non-negotiable for a multi-org collaboration; without it, you get incompatible implementations of the same concept.

```
rfc/
├── 0001-self-representation-format.md
├── 0002-detector-population-protocol.md
├── 0003-federation-cytokine-bus.md
├── 0004-curriculum-module-shape.md
├── 0005-credential-signing-format.md
└── _template.md
```

RFC template based on Rust's RFC process: motivation, design, drawbacks, alternatives, prior art, unresolved questions. Open period for comments. Final comment period before acceptance. Owner per RFC.

**Crucially**: each lab gets at least one RFC slot per quarter where they propose architectural extensions. Forrest's lab might own RFCs for the immune subsystem; Trieu's for the cryptographic primitives. Owners can veto incompatible designs in their domain but can't block other labs from publishing extensions.

## 3.3 — Shared Evaluation Harness

Every lab tests against the same benchmarks. Without this, comparative claims become impossible.

```
bench/
├── attacks/
│   ├── attack-001-credential-stuffing/
│   ├── attack-002-prompt-injection/
│   ├── attack-003-supply-chain-poison/
│   ├── attack-004-membership-inference/
│   ├── attack-005-federation-exfil/
│   └── README.md
├── datasets/
│   ├── synthetic-tenant-traffic/
│   ├── synthetic-pipeline-runs/
│   ├── synthetic-federation-msgs/
│   └── README.md
├── metrics/
│   ├── tpr-fpr-roc.py
│   ├── privacy-utility-tradeoff.py
│   ├── detection-latency.py
│   └── README.md
└── leaderboards/
    └── (auto-generated nightly)
```

A shared CI job runs every detector and every privacy method against the same suite. Leaderboards update nightly. Every paper from every lab can cite "JACKPOT-bench v1.2 attack-003" and another lab can reproduce it instantly.

This is the iDASH-competition pattern made institutional. Worth noting: getting collaborators to agree on benchmarks is sometimes harder than the technical work, because benchmarks favor whoever designed them. The honest move is to let each lab contribute attack scenarios to the suite.

## 3.4 — Synthetic Data Fixtures (Reusable Across Everyone)

Every collaborator has the same data to work against. PHA4GE-aligned, statistically rich, generative-recipe-defined.

```
synthetic/
├── recipes/                # YAML defining each fixture
├── generators/             # Python code creating data from recipes
├── fixtures/               # Generated data
└── tools/
    ├── attack-injection.py # Add attack signals to clean data
    └── privacy-eval.py     # Measure re-identification risk
```

A shared synthetic-data generator is *also* a publication on its own. Halden's National Sewage Sludge Repository statistical fingerprints could ground the synthetic-wastewater fixture. Lee's group could ground the genomic-data fixtures. Everyone's papers cite the same synthetic data so reproducibility becomes free.

## 3.5 — Governance Model

This is the explicitly political layer, and ducking it will kill the collaboration.

**Technical Steering Committee (TSC):**

- 1 seat: JACKPOT lead (you)
- 1 seat per actively contributing lab (Forrest, Trieu, Lee, Halden, plus future)
- 1 seat: rotating community representative
- 1 seat: rotating external industry / agency liaison

**Decisions:**

- Day-to-day code: maintainer authority within their module
- Cross-cutting architecture: RFC + TSC simple majority
- License changes / governance changes: TSC supermajority + community comment period
- Curriculum content: module owner with TSC review for accuracy

**Conflict resolution:**

- Default: technical merit wins, demonstrated empirically (use bench/)
- Escalation: TSC vote
- Final: project lead has tiebreaker

This is the **CNCF / Linux Foundation pattern** scaled down. It works for projects with 5-10 stakeholder organizations.

## 3.6 — Contribution Workflow

Each contribution type has a clear path:

| Contribution type    | Path                                                    |
| -------------------- | ------------------------------------------------------- |
| Production bug fix   | PR to `backend/`, normal review                         |
| Production feature   | RFC + PR to `backend/`, owner review                    |
| Research module      | PR to `research/<lab>/`, lab owner review               |
| Curriculum module    | PR to `course/<topic>/`, module owner review            |
| Architectural change | RFC, FCP, TSC sign-off                                  |
| Synthetic data       | PR to `synthetic/`, lightweight review                  |
| Benchmark            | PR to `bench/`, dual review (proposing lab + one other) |

The dual review on benchmarks is the political-immune-system equivalent. You don't let one lab unilaterally define what "wins."

## 3.7 — Publication and Authorship Norms

This is where most academic collaborations hit reefs. State the rules early.

- **CRediT taxonomy in every paper**: who contributed conceptualization, methodology, software, validation, etc. No vague co-authorship.
- **JACKPOT acknowledged in every paper using its infrastructure** (specific text in CONTRIBUTING.md).
- **A paper using only published JACKPOT components**: standard citation, no co-authorship expected.
- **A paper extending JACKPOT internals**: relevant module owner offered co-authorship.
- **A paper cross-cutting multiple labs' modules**: discuss authorship before submission, not after.
- **Joint papers**: encouraged. The Driver et al. 2024 paper is the model: env health + crypto + bio + CS in one paper.

Make all of this explicit in `AUTHORSHIP.md`. Saves enormous future pain.

## 3.8 — Funding Alignment

The collaboration only works if the collaborators can fund their participation. Three streams to cultivate:

**Stream 1: Joint grants where JACKPOT is the named platform**

- NSF SaTC, CICI, Pathways to Enable Open-Source Ecosystems (POSE)
- NIH ELSI for the privacy-preserving computation work
- ARPA-H for the deployable platform work
- DARPA for the immune-system-inspired security work (this is literally Forrest's funder list)

**Stream 2: Lab-specific grants that include JACKPOT integration**

- Each lab pursues their own grants, but proposals include "outcomes integrated into JACKPOT" as a deliverable
- This means JACKPOT gets stronger from many independent grant wins
- Maintenance is shared across the labs

**Stream 3: Foundation and industry funding**

- Schmidt Sciences, Open Philanthropy, Wellcome
- Industry partners for confidential computing (Intel, AMD, Microsoft, Phala)
- Public health agency contracts as JACKPOT matures

Important detail: JACKPOT itself might want to be hosted under a fiscal sponsor (NumFOCUS, Open Source Collective) or its own 501(c)(3) so grants can flow directly to platform development rather than only through researcher institutions. That's a 2027 problem to start scoping in late 2026.

## 3.9 — Communication Infrastructure

| Need                    | Tool                                                         |
| ----------------------- | ------------------------------------------------------------ |
| Async deep discussion   | GitHub Discussions per repo                                  |
| Real-time chat          | Matrix / Mattermost (open, federable) — *not* Discord, that's a research-collab smell |
| Quarterly all-hands     | Google Meet / Zoom; recorded                                 |
| Monthly tech sync       | Per-subsystem; lab leads + interested members                |
| Weekly working sessions | Per active sub-project                                       |
| Community-facing        | Mailing list + monthly newsletter                            |

The right stance: **default to async, default to public, default to written**. This makes it possible for new collaborators to onboard themselves and reduces the meeting load on existing collaborators.

## 3.10 — Onboarding the First External Collaborator

The proof that this scaffolding works is making it easy for, say, Forrest's first PhD student to land a contribution. Their experience:

1. Read `CONTRIBUTING.md` → understand the lay of the land
2. Read `research/forrest-lab/README.md` → understand their lab's domain
3. Pick an issue tagged `good-first-issue` in their lab's directory
4. Run `jackpot init --profile dev` → working dev env in 10 minutes
5. Run `pytest research/forrest-lab/` → all tests pass
6. Run `bench/run.sh attack-001` → see baseline numbers
7. Implement their detector against `synthetic/fixtures/`
8. Open PR → CI runs → benchmark numbers auto-posted to PR
9. Review by lab owner → merged to `research/forrest-lab/`
10. After three accepted contributions, eligible for module-maintainer credential

If steps 1-7 take more than a day for a competent grad student, the scaffolding has failed. Optimize relentlessly for that path.

## 3.11 — The Honest Limits

Stuff this scaffolding *won't* solve:

- **People not having time**. Faculty and grad students are pulled in many directions. Even great infrastructure doesn't manufacture hours.
- **Personality conflicts**. The TSC structure helps but doesn't eliminate.
- **Funding gaps**. If lab funding lapses, contribution stops. Plan for transition periods.
- **IP / institutional friction**. ASU's tech transfer office may have opinions. Address early via the AGPL clarification.
- **The publish-or-perish gradient**. If contributing to JACKPOT doesn't help a researcher's tenure case, they won't contribute long. Make sure publication paths are clear and credit is explicit.

------

## TL;DR

**Software components** map cleanly to immune subsystems: a Self-representation layer, NSA/Clonalg/DCA detector generators, innate (signature) and adaptive (memory) immunity, an N-variant diversity layer, a federation cytokine bus, attribution/deception infrastructure, and a tolerance/regulatory layer. Each is a real Python service or library with concrete integration points to JACKPOT's existing FastAPI/Postgres/Nextflow stack. Total engineering effort is realistically 18-24 months with research collaboration; 36+ months solo.

**Education becomes foundational** by living in the same monorepo as the code, following a six-stage motivation→exploration→concept→implement→evaluate→contribute pattern, organizing into Defender/Builder/Architect tracks, and shipping cryptographically-signed credentials as a first-class concept. Forrest's research themes literally become the curriculum modules — making her work the teaching material, not the marketing copy.

**Collaboration scaffolding** mirrors the Linux kernel staging-tree and CNCF governance patterns: a `research/` directory with per-lab sandboxes, an RFC process for cross-cutting decisions, a shared evaluation harness, synthetic-data fixtures everyone tests against, a Technical Steering Committee with explicit decision rules, clear authorship norms, and async-first public communication. The proof of correctness is that a Forrest PhD student can land their first contribution in a single working day.

The whole thing is doable. None of the pieces are blocked on technical impossibility. The main risk is coordination overhead, which is exactly what the scaffolding above is designed to suppress.

Want me to draft the actual `RFC-0001-self-representation-format.md` to seed the process, sketch the first `research/forrest-lab/nsa/` module structure with a stub detector implementation, or write the `CONTRIBUTING.md` that would make a first-time grad student successful in 24 hours?Right, I was so deep in platform-security mode I drifted from the bio side. Let me bring it back. Because honestly — the **bio**-signature anomaly detection story is even richer than the platform-security one, and the espionage curriculum was the thing that got Forrest's lab to the table in the first place via the immune-system metaphor.You're absolutely right and I owe you the bio side. The platform-security version of the immune-system metaphor was useful for getting Forrest's lab to the table, but the **bio**-anomaly version is where JACKPOT actually earns its name. And the espionage curriculum was the original spark — that needs to come back.

Here's what I missed.

------

## Part 1 — Why Bio-Anomaly Detection Is The Real Story

The immune-system metaphor isn't even a metaphor when applied to pathogen genomics. It's *homology*. A real immune system distinguishes self (host microbiome, normal cells) from nonself (pathogen, mutated cell, foreign protein). A pathogen genomics platform distinguishes self (normal microbiome, expected references, baseline wastewater signal) from nonself (novel pathogen, unexpected variant, anomalous community shift).

This is the part where Forrest's career and JACKPOT's domain actually fuse. Negative selection of T-cells maps directly onto detector-against-normal-microbiome. Clonal expansion of B-cells maps directly onto how a surveillance system should respond when it finds something. Affinity maturation is exactly what pathogen genomic surveillance does as it refines lineage definitions.

And the literature is right there. 2025 reviews on AI-powered analysis of viral metagenomic sequencing data show deep learning and ML are increasingly recognized as transformative tools for biomedical pattern recognition, anomaly detection, and predictive modeling, with unsupervised learning and clustering techniques playing a critical role in identifying novel pathogens by detecting outlier sequences or uncharacterized genomic signatures within metagenomic datasets. A September 2025 roadmap proposed AI-powered metagenomic biosurveillance where anomaly-detection models trained on months of historical sequencing data could sift through billions of daily reads from sources like airport wastewater, with suspicious sequences then analyzed by AI protein-folding models to identify functional similarities to dangerous viral proteins.

That's the picture. JACKPOT becomes the production deployment of exactly that vision.

------

## Part 2 — Bio-Anomaly Software Components

Same structure as the platform-security components, but now everything is a bioinformatics primitive.

### 2.1 — The Genomic "Self" Layer

Before we can detect bio-anomalies, we need to define normal. Per tenant. Per sample type. Per geographic region. Per time of year.

| Component                         | Function                                                     | Stack                                                       |
| --------------------------------- | ------------------------------------------------------------ | ----------------------------------------------------------- |
| **`jackpot-microbiome-baseline`** | Learns normal community composition per sample type          | Kraken2/Bracken outputs → Postgres baselines, time-windowed |
| **`jackpot-genomic-self`**        | Builds reference models of expected genomes per pathogen of interest | Mash sketches, sourmash signatures, k-mer Bloom filters     |
| **`jackpot-wastewater-baseline`** | Per-catchment baseline of expected community + Freyja lineage distribution | TimescaleDB; integrates with Driver et al. 2024 work        |
| **Reference graph store**         | Pangenome graph — what's in scope for "known"                | Variation Graph Toolkit (`vg`), `pggb`                      |
| **Phylo placement reference**     | Where existing things sit on trees                           | UShER mutation-annotated trees, persistent and versioned    |

The tenant fingerprint isn't just operational; it's biological. Each tenant has a genomic self.

### 2.2 — Innate Bio-Immunity (Pattern-Based Detection)

The fast first pass. What humans currently do with BLAST and gut feeling.

| Component                       | Function                                                     | Stack                                                        |
| ------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **Sequence-screening guard**    | Match against known hazards before pipeline runs             | **SecureDNA** integration — privacy-preserving DOPRF screening |
| **Reference-similarity flag**   | Standard taxonomic ID + confidence                           | Kraken2 + Bracken + Pavian visualization                     |
| **Pre-built hazard signatures** | NIH Select Agents, OSTP Sequences of Concern                 | SecureDNA's hazard database covers regulated agents (BSAT, CCL) with screening every 200-nucleotide window decreasing to 50 nucleotides by October 2026, already exceeding 2026 requirements |
| **AMR pattern matcher**         | Known resistance genes                                       | AMRFinderPlus + CARD/RGI                                     |
| **Engineered-feature scanners** | Restriction sites, codon usage outliers, known plasmid backbones | Custom; integrates with PaPrBaG-style classifiers            |

This is the layer where JACKPOT integrates SecureDNA. The work has already been done by Rivest, Shamir, Vaikuntanathan, Esvelt and others — JACKPOT becomes a downstream consumer rather than reinventing privacy-preserving sequence screening.

### 2.3 — Adaptive Bio-Immunity (Learning, Memory)

This is the part the AI/ML literature has been driving for two years and where JACKPOT-as-platform makes the deployment real.

| Component                        | Function                                             | Stack                                                        |
| -------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------ |
| **`jackpot-mg2vec`**             | Transformer-based metagenomic feature learner        | Reference: MG2Vec uses transformer networks to learn robust features from raw metagenome sequences for downstream pathogen detection, generalizing across pathogens, diseases, and species |
| **`jackpot-amand`**              | DeepSVDD-based metagenome anomaly detector           | Reference: AMAnD uses DeepSVDD neural networks for automated metagenome anomaly detection, flagging anomalous samples from typical samples |
| **`jackpot-paprbag`**            | Novel-pathogen ML classifier                         | Reference: PaPrBaG handles genetic divergence by training on a wide range of species with known pathogenicity phenotype, predicting novel pathogens from NGS data |
| **Variational autoencoder bank** | Per-tenant VAEs of normal sample distributions       | PyTorch; reconstruction error → anomaly score                |
| **Phylo-placement anomaly**      | "This sequence doesn't fit the tree" detector        | UShER + branch-length statistics                             |
| **Memory tier**                  | Past anomalies become signatures for future runs     | Postgres + Sigstore-signed records                           |
| **Tolerance learning**           | Suppress signals that are seasonal, expected, benign | Operator feedback → retraining                               |

Every one of these has 2023-2025 published reference implementations. JACKPOT's job is to integrate them with consistent APIs, shared data fixtures, and a tolerance layer that prevents constant false alarms.

### 2.4 — Bio-Attribution (Engineered or Evolved?)

This is the layer that most outright fails today and where genuine research is needed. JACKPOT becomes the platform on which the research happens.

| Component                            | Function                                             | Stack                                                        |
| ------------------------------------ | ---------------------------------------------------- | ------------------------------------------------------------ |
| **Codon-bias anomaly detector**      | Statistical analysis vs. expected host codon usage   | Custom Python; reference distributions per host species      |
| **GC-content profiler**              | Sliding window GC anomaly + topology                 | Standard bioinformatics, surfaced in JACKPOT UI              |
| **Restriction-site density mapper**  | Suspicious regularity in cut sites                   | Custom                                                       |
| **Synthetic-construct similarity**   | BLAST against catalogued lab plasmids and constructs | Addgene reference set; ARG search                            |
| **Functional-equivalence search**    | Catches mutations that preserve function             | SecureDNA approach using exact-match search to find hazards and functional equivalents, with random adversarial threshold algorithms identifying short hazardous DNA and peptide subsequences including millions of predicted functional variants |
| **Structural prediction comparison** | Protein folds where they shouldn't                   | ESMFold / AlphaFold3 / Boltz-1                               |
| **Provenance graph**                 | Who saw what variant when, in what context           | Neo4j; visible in audit logs                                 |

Forrest's career-long cyber-attribution work directly informs this. The methods she used to attribute cyberattacks based on behavioral fingerprints are structurally identical to attributing pathogen origins based on genomic fingerprints. There's a paper or three sitting in the gap between her cyber-attribution corpus and bio-attribution.

### 2.5 — Wastewater & Environmental Bio-Surveillance

The thing the Forrest+Trieu+Lee+Halden quartet already published on. JACKPOT extends it to federation.

| Component                       | Function                                               | Stack                                                        |
| ------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------ |
| **Freyja 2 anomaly layer**      | Lineage-prevalence shift detection                     | Freyja outputs → time-series anomaly detection               |
| **Catchment baseline modeler**  | Per-WWTP normal community composition                  | Statistical models, regional priors                          |
| **Building-level privacy gate** | Encrypted data sharing across catchments               | Driver et al. 2024 protocol → JACKPOT's federation cytokine bus |
| **Spatiotemporal correlation**  | Outbreak signal triangulation across catchments        | GIS integration; geopandas                                   |
| **Traveler-import detector**    | Airport / transit hub catchments → introduction events | Cross-references travel data when available                  |

This is the warmest collaboration hook with the Biodesign Center. It's literally their existing project at federation scale.

### 2.6 — Cross-Cutting: Diversity in the Bio Sense

Forrest's diversity-as-defense translates beautifully to genomic surveillance.

| Component                     | Function                                                     | Stack                                               |
| ----------------------------- | ------------------------------------------------------------ | --------------------------------------------------- |
| **Multi-classifier ensemble** | Same pathogen ID via Kraken2 + GAMBIT + MG2Vec; disagreement = signal | Pipeline framework; native ensemble support         |
| **Multi-reference analysis**  | Same sample analyzed against multiple reference DBs; discordance flags concern | Reference DB abstraction layer                      |
| **Multi-modal fusion**        | Genomic + structural + epidemiological signals combined      | Multi-input pipeline definitions                    |
| **Adversarial robustness**    | Synthetic adversarial sequences test detection layers        | Lee's iterative attack-and-defend frameworks for ML |

When three pathogen classifiers agree, you trust the call. When they disagree, you investigate. That's not just engineering — that's pedagogically clean.

### 2.7 — The Federation Cytokine Bus, Bio Edition

Same architecture as the platform-security version, different payloads.

| Signal type                  | What it carries                                              |
| ---------------------------- | ------------------------------------------------------------ |
| **Lineage emergence alert**  | "We're seeing X.Y.2 at unexpected frequency"                 |
| **Variant of concern flag**  | "Mutation pattern A+B+C detected; structural impact unknown" |
| **Wastewater early warning** | "Sewershed rising-edge signal for [pathogen]"                |
| **AMR emergence**            | "Novel resistance pattern in [organism]"                     |
| **Engineered-suspect flag**  | "This isolate shows [n] features inconsistent with natural evolution" |
| **Reference DB update**      | "New hazard added to OSTP-equivalent screening set"          |

All federated through STIX/TAXII (or a domain-extended profile) over Trieu-style PSI when participants want to know about overlap without revealing private cohorts.

------

## Part 3 — The Espionage Curriculum, Reimagined With Real Bio-Anomaly Detection

Now the fun part. The original WILDFIRE / SENTINEL / Field Edition concepts had cases that were essentially "use Kraken2 to identify a pathogen." Fine, but it doesn't exercise the bio-anomaly detection muscle. With the components above, the cases get *much* better.

### 3.1 — Field Edition: Case Catalog Reimagined

Each case now exercises specific bio-anomaly techniques. The synthetic data is generated with a known-anomaly recipe so the answer key exists, but the player has to *find* the anomaly using real bio-anomaly tools.

| #      | Case                          | Anomaly type                                                 | Tools exercised                                              |
| ------ | ----------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **01** | **The First Patient**         | Ordinary pathogen ID                                         | Kraken2 + Bracken (warm-up)                                  |
| **02** | **The Strange Reader**        | Sample matches no reference                                  | MG2Vec embedding distance, AMAnD anomaly score               |
| **03** | **The Synonymous Mutation**   | Same protein, suspicious codons                              | Codon bias analyzer, host-comparison stats                   |
| **04** | **The Drifting Lineage**      | Variant accumulating mutations faster than expected          | UShER placement + branch-length stats                        |
| **05** | **Phantom in the Microbiome** | Pathogen hidden in normal-looking community                  | VAE reconstruction error, host-filtering, hidden-pathogen recovery |
| **06** | **The Sewershed Mystery**     | Wastewater shows lineage that shouldn't be there             | Freyja 2 + catchment baseline + travel data correlation      |
| **07** | **Engineered or Evolved**     | Genuine attribution puzzle                                   | Codon bias + GC profile + restriction sites + structural comparison + functional-equivalence search |
| **08** | **The Doppelgänger**          | Two samples look identical but aren't                        | Pangenome graph placement, fine-resolution typing            |
| **09** | **The Phantom Resistance**    | New AMR pattern with no known mechanism                      | AMRFinderPlus + CARD + structural prediction of mutated targets |
| **10** | **The Federation Trap**       | Need data from another lab to solve, but they have OPSEC concerns | PSI-CA query without revealing your samples                  |
| **11** | **The Dead Drop**             | Encrypted brief; key fingerprint hidden in synonymous codons of a phage genome | Real PGP/age + codon analysis                                |
| **12** | **The Memorial Day Outbreak** | Capstone — multi-source, multi-anomaly, federated            | All of the above                                             |

Each case is `cases/case_NN/` with:

```
cases/case_07_engineered_or_evolved/
├── briefing.md               # In-character mission text
├── recipe.yaml               # How synthetic data was generated
├── inputs/
│   ├── reads.fastq.gz
│   ├── metadata.csv
│   └── (sometimes a red herring file)
├── expected_findings.yaml    # Answer key
├── scoring.yaml              # How to grade a player's report
├── hints/                    # Tiered, time-locked
└── debrief.md                # Post-case writeup of the techniques
```

### 3.2 — The Bio-Anomaly Curriculum Modules

These slot into the `course/biosecurity/` directory. Each is a real teaching unit with a real tool focus.

```
course/bio-anomaly/
├── 01-self-and-nonself-in-microbiomes/
├── 02-baseline-modeling/
├── 03-novel-pathogen-detection-mg2vec/
├── 04-metagenomic-deep-anomaly-amand/
├── 05-phylogenetic-placement-anomalies/
├── 06-wastewater-anomaly-freyja/
├── 07-codon-bias-and-host-mismatch/
├── 08-structural-anomaly-esmfold/
├── 09-engineered-vs-evolved-attribution/
├── 10-securedna-screening/
├── 11-federated-bio-anomaly-detection/
└── 12-capstone-novel-outbreak/
```

Each module follows the same six-stage pattern from before: motivation → exploration → concept → implement → evaluate → contribute. But now the **CONTRIBUTE** stage means: *your detector becomes part of `jackpot-amand` or `jackpot-mg2vec`*. Student work directly feeds the bio-anomaly stack.

### 3.3 — WILDFIRE Mechanics, Bio-Anomaly Edition

The espionage layer adds *everything*. Here's how the modes get sharper:

| Mechanic                        | Bio-anomaly version                                          |
| ------------------------------- | ------------------------------------------------------------ |
| **Dead drops**                  | Files of fastq+metadata. Sometimes obfuscated. Sometimes intentionally noisy. Sometimes synthesized adversarially. |
| **The mole**                    | A compromised cell member submits subtly poisoned samples designed to defeat the detection layer. The team must figure out *which* samples and how. |
| **OPSEC scoring**               | Your team's queries to federation reveal information about your samples even if you use HE. Bad query design leaks intel. |
| **Speed vs accuracy**           | Faster classifiers give worse ensembles. Going through full bio-anomaly stack costs time. Ticking outbreak clock. |
| **Trust calibration**           | Your LLM analyst-agent confidently identifies a pathogen — but the ensemble disagrees. Who's right? |
| **Adversarial submissions**     | Other cells can submit data to your federation. Some are real. Some are decoys. Some are *hostile* — designed to poison your detectors. |
| **Attribution puzzles**         | You found something. Engineered or evolved? You'll need to defend your call publicly. The "press" will grill your evidence chain. |
| **The Engineered Pandemic Arc** | Multi-week story where players gradually accumulate evidence of a coordinated synthetic-biology threat. Real DURC review processes form the gameplay loop. |

### 3.4 — The Original Notes, Resurrected

Going back to your original "Stop the Plague" notes — the CIA-mole-fastq-files scenario. Here's how it plays now with real bio-anomaly tools:

**Mission 1 — "Files from a Dead Agent"** You receive what claims to be sequencing data. First step: validate the file. (`file_detector.py`. The fastq might be a tar of fastqs. Or a zip with a malicious payload. Real-world skills.)

**Mission 2 — "The Microbiome Says Otherwise"** The agent's body samples should look like normal human microbiome. They don't. Kraken2 baseline + AMAnD anomaly score show divergence. Find out what.

**Mission 3 — "The Pathogen Wears a Disguise"** The pathogen's surface proteins were engineered to look like something benign. ESMFold structural comparison reveals the deception. Functional-equivalence search confirms it.

**Mission 4 — "The Vaccine Trap"** Design countermeasures against a pathogen that's been engineered to evade existing vaccines. The surface antigens look normal to B-cell epitope predictors, but structural modeling reveals the binding pocket geometry has shifted just enough to escape neutralization. Your team needs to identify the escape mutations and design updated immunogens.

**Mission 5 — "The Attribution Game"** Multiple cells submit evidence about whether a sequence is engineered vs. evolved. Each team gets partial data. The federated analysis reveals contradictory phylogenetic signals. Someone's data is compromised — or someone's lying. The mission succeeds only if teams can identify the bad actor *and* reach consensus on attribution.

**Mission 6 — "The False Flag"** Your bio-anomaly detectors are triggering on sequences that look engineered, but further analysis suggests they're natural recombinants that just happen to hit multiple engineering signatures. Do you call it natural or synthetic? The wrong call triggers either international incident (if you cry bioweapon) or pandemic (if you miss the real threat).

------

## Bio-Signature, Pathogen, and Genomic Anomaly Detection

This is where JACKPOT really differentiates from existing platforms. Most genomic surveillance focuses on *known* threats — tracking variants of identified pathogens. But what about the unknown unknowns? Here's the bio-anomaly detection stack that makes the espionage scenarios actually work:

### 1. Genomic Anomaly Detection (`jackpot-amand`)

**AMAnD** (Anomaly Mining and Novelty Detection) — the core engine:

```bash
# Core anomaly detection pipeline
jackpot-amand analyze \
  --fastq sample.fastq.gz \
  --reference-db /data/refs/all-known-pathogens.mash \
  --anomaly-threshold 0.85 \
  --output anomaly-report.json

# Generates:
# - K-mer distance outliers (sample vs all known references)
# - GC content anomalies (species-corrected z-scores)
# - Codon usage bias (CAI deviation from host preference)
# - Restriction enzyme site anomalies (suspicious cut patterns)
# - Phylogenetic placement confidence (does this fit the tree?)
```

Key algorithms:

- **Compositional anomalies**: GC skew, dinucleotide bias, codon adaptation index
- **Structural anomalies**: Unexpected ORF patterns, ribosome binding sites
- **Evolutionary anomalies**: Phylogenetic placement failures, molecular clock violations
- **Engineering signatures**: Synthetic biology scars, BioBrick sequences, optimization artifacts

### 2. Pathogen Anomaly Detection (`jackpot-mg2vec`)

**MG2Vec** — metagenomic anomaly detection through embeddings:

```bash
# Train embeddings on normal microbiome samples
jackpot-mg2vec train \
  --input-dir normal-microbiomes/ \
  --model-type transformer \
  --embedding-dim 512 \
  --output mg2vec-baseline.model

# Detect anomalous communities
jackpot-mg2vec detect \
  --fastq outbreak-sample.fastq.gz \
  --baseline-model mg2vec-baseline.model \
  --anomaly-score-threshold 2.5
```

This catches:

- **Novel pathogen emergence**: completely unknown species in unexpected ecological niches
- **Artificial microbiome manipulation**: engineered probiotics, microbiome weapons
- **Steganographic pathogens**: known bugs hiding in unexpected sample types
- **Community disruption**: normal commensals behaving abnormally

### 3. Bio-Signature Detection (`jackpot-biosig`)

**Functional signature analysis** — what the sequence *does*, not just what it *is*:

```bash
# ESMFold + functional prediction pipeline
jackpot-biosig analyze \
  --protein-fasta translated-orfs.fa \
  --function-db toxins,virulence,antimicrobial \
  --structure-prediction esmfold \
  --binding-site-analysis epitope-suite

# Detects:
# - Novel toxin domains with known fold structures
# - Immune evasion mechanisms (epitope shuffling)
# - Engineered enzyme activities
# - Synthetic biology parts with natural camouflage
```

### 4. The Original Espionage Framework

Your original "Stop the Plague" notes were prescient — they anticipated exactly the scenarios we're building. Here's how the espionage layer works:

**Trust Network Dynamics**: Each cell (player team) has a reputation score. Sharing anomalous samples with other cells gives you trust points if they validate your finding, but costs you trust if you're wrong. Moles deliberately submit false positives to damage target cells' credibility.

**Information Warfare**: Query patterns leak information. If Cell A suddenly queries for "ricin synthesis pathways" and "aerosol delivery mechanisms," that's intelligence even if they never share their actual samples. The federation monitors query metadata and builds intelligence profiles.

**Adversarial ML**: Enemy cells can poison your training data by submitting samples labeled as "benign" that are actually anomalous. Your detectors gradually degrade unless you can identify and purge the poisoned samples.

**OPSEC Mechanics**: Everything has consequences. Upload samples without proper PII scrubbing? Your cell gets a "security violation" and temporarily loses federation access. Share raw sequences outside the HE framework? You're permanently blacklisted. The game teaches operational security through consequences, not lectures.

### The Ultimate Training Scenario

Imagine this capstone mission:

**"Operation Lazarus"** — A 6-month scenario where teams gradually uncover a coordinated synthetic biology threat. The adversary is using CRISPR to create "Lazarus pathogens" — extinct diseases resurrected from environmental DNA with engineered enhancements.

- **Week 1-8**: Strange environmental samples from archaeological sites. Teams use `jackpot-amand` to identify ancient pathogen signatures.
- **Week 9-16**: Clinical samples from "isolated outbreaks" that phylogenetically link to the environmental findings. Teams use `jackpot-mg2vec` to detect the engineered adaptations.
- **Week 17-24**: Full-scale attribution analysis. Teams use `jackpot-biosig` to prove the enhancements are synthetic, then coordinate through federation to build the complete threat picture.

The final deliverable? A briefing to simulated WHO leadership with your evidence chain for declaring a PHEIC (Public Health Emergency of International Concern) based on synthetic biology evidence.

### Why This Matters for Real JACKPOT

Every game mechanic maps to real-world JACKPOT capabilities:

- **Anomaly detection** → production modules for biosecurity screening
- **Federation trust dynamics** → reputation-based data sharing protocols
- **PII gate enforcement** → real HRRT/DLP compliance training
- **Query metadata analysis** → federated analytics privacy preservation
- **Multi-modal evidence fusion** → genomic + clinical + environmental integration

The game doesn't just teach the platform — it stress-tests it under adversarial conditions no traditional QA could replicate.

------

The original espionage concept was brilliant because it recognized that genomic surveillance is fundamentally an intelligence discipline disguised as public health informatics. The threats are adversarial, the evidence is partial, and the stakes are existential. Training people to think like intelligence analysts while teaching them bioinformatics creates a new category of professional: the **genomic intelligence analyst**.

That's not just a cool job title — it's what the next generation of outbreak responders will actually need to be.



Got it — working MVPs for all five gaps, full detail in a companion doc, short refs added to the existing vision doc. Let me build the companion doc first since it's the bigger deliverable, then patch the vision doc with cross-references.Companion doc is complete at 1,908 lines. Now let me patch the vision doc with cross-references to the new companion doc, then move both to outputs.Now update the Table of Contents and copy both files to outputs:Both docs are ready. Here's what landed and how to wire it in:

## What you've got

**Companion doc — `jackpot_immune_collaboration_scaffolding.md`** (1,908 lines, ~82KB) — full detail on every component **Updated vision doc — `jackpot_immune_platform_plan.md`** (1,976 lines, ~118KB, was 1,913) — added §18 cross-referencing the companion + TOC entry

## What's in the companion doc

| §    | Section                                 | Components shipped                                           |
| ---- | --------------------------------------- | ------------------------------------------------------------ |
| 1    | Why this companion exists               | 70/30 posture rationale                                      |
| 2    | 11 critiques mapped to scaffolding      | Master index of every gap → component → collaboration marker |
| 3    | **Gap 1 — Monoculture**                 | Featurizer registry, `diversity_profile.py` (per-member init), `diversity.py` (Shannon index), schema additions, CI gate, `TODO(forrest-collab): coverage theory` |
| 4    | **Gap 2 — Supply chain**                | `generate_sbom.py` (CycloneDX + grype), CI workflow, `parsers_safe.py` (forbidden-deserialization helpers + Critical Rule for CLAUDE.md), cosign signing, SLSA attestation doc, `TODO(forrest-collab): auto-repair` |
| 5    | **Gap 3 — Static defense**              | `rotation.py` (JWT/cred/token rotation framework), `cs_cyber_federated.py` (federation-wide clonal selection), `api_surface_mutation.py` (Crispy-style error message rotation), schema, `TODO(forrest-collab): mutation cadence theory` |
| 6    | **Gap 4 — Misuse / governance**         | `GOVERNANCE.md` v0 with refusal-to-deploy criteria, `refusal.py` (technical refusal middleware with HTTP 451), `asymmetric_trust.py` (sub-linear sublimear trust scaling for LMIC fairness), `dual_use_review.md` (DURC queue), schema, `TODO(forrest-collab): policy framework` and `fairness theory` |
| 7    | **Gap 5 — Education reframing**         | `course/modules/_meta/forrest_framing.md` (Module 0 — why JACKPOT exists), §1 patch instructions, sibling differentiator paper |
| 8    | **Cross-cutting `jackpot-redteam/`**    | `attack_amand.py`, `attack_mg2vec.py`, `attack_biosig.py`, `attack_federation.py` (re-identification), `attack_screening.py`, weekly CI, public results in `docs/redteam_results/`, `TODO(lee-collab)` and `TODO(trieu-collab)` markers |
| 9    | **Phase 26-collab integration**         | 30 person-days of work scoped + 3 new quick wins (QW-8 parsers_safe, QW-9 forrest_framing, QW-10 governance v0) + Halden wet-side advisory (WW-1, WW-2, WW-3) |
| 10   | **Open research questions, summarized** | Master table of every `TODO(<x>-collab):` marker organized by collaborator (Forrest 9, Trieu 4, Lee 3, Halden 3 advisory items) |

Every component is a **working MVP plus extension point** — actual code with real signatures, real schemas, real CI workflows. The deliberate research holes are clearly marked.

## Install both files in your repo

```bash
mkdir -p ~/ASU/jackpot/jackpot-backend/docs
cp /mnt/user-data/outputs/jackpot_immune_platform_plan.md ~/ASU/jackpot/jackpot-backend/docs/jackpot_immune_platform_plan.md
cp /mnt/user-data/outputs/jackpot_immune_collaboration_scaffolding.md ~/ASU/jackpot/jackpot-backend/docs/jackpot_immune_collaboration_scaffolding.md
ls -la ~/ASU/jackpot/jackpot-backend/docs/jackpot_immune*.md
```

Commit:

```bash
cd ~/ASU/jackpot/jackpot-backend
git add docs/jackpot_immune_platform_plan.md docs/jackpot_immune_collaboration_scaffolding.md
gac "docs: add immune platform vision + collaboration scaffolding companion"
```

## Updates needed for the spec/todo/backlog paste-ins from the prior turn

The previous spec.md / todo.md / backlog additions need small additions to reference the companion doc and the new Phase 26-collab items. Here are the deltas:

### spec.md §22 — add subsection 22.11

Paste at the end of the §22 block:

```markdown
### 22.11 Collaboration scaffolding

The vision doc as written has known gaps that Forrest's Biodesign group (Forrest, Trieu, Lee, Halden) would identify on first read: monoculture, supply-chain security, static defense posture, misuse/governance, and education-as-foundation framing. Each gap has a working-MVP component with a deliberate `TODO(<researcher>-collab):` marker. Full design detail in `docs/jackpot_immune_collaboration_scaffolding.md`. Vision doc summary in §18.

The components run as a parallel **Phase 26-collab** track alongside Phase 26+, totaling ~30 person-days. First-sprint quick wins (QW-8 parsers_safe, QW-9 forrest_framing meta-module, QW-10 GOVERNANCE.md v0) are unconditionally good practice independent of collaboration outcomes.
```

### todo.md — add a Phase 26-collab block

Paste at the end of the Phase 26-quickwins block (before "Done in Session 5"):

```markdown
---

## Phase 26-collab — Collaboration scaffolding (parallel track)

**Goal:** Address the five gaps Forrest's Biodesign group would identify on first read of the immune-platform vision doc. Show up to that conversation having done the engineering work that's available to do alone.
**Estimated:** ~30 person-days, parallel with Phase 26+.
**Spec ref:** `docs/jackpot_immune_collaboration_scaffolding.md`, vision doc §18.

### First-sprint quick wins (1–2 day items, do now)

- [ ] **QW-8:** Land `backend/immune/sec/parsers_safe.py` + Critical Rule N in CLAUDE.md (no `pickle.load` / `yaml.unsafe_load` / `eval` on external data). 1 day.
- [ ] **QW-9:** Land `course/modules/_meta/forrest_framing.md` (Module 0 — why JACKPOT exists). 0.5 day.
- [ ] **QW-10:** Land `GOVERNANCE.md` v0 with refusal-to-deploy criteria. 1 day.

### Phase 26-collab proper

- [ ] **C-001:** `backend/immune/algorithms/featurizers/__init__.py` — featurizer registry. 2 days.
- [ ] **C-002:** `cli/jackpot_init/diversity_profile.py` — per-member detector profiles at init. 1 day.
- [ ] **C-003:** `backend/immune/net/diversity.py` — federation Shannon diversity index. 2 days.
- [ ] **C-004:** `scripts/generate_sbom.py` (CycloneDX + grype) + CI workflow `.github/workflows/supply_chain.yml`. 3 days.
- [ ] **C-005:** `infra/sigstore/` cosign signing + verification policy + signed image release pipeline. 2 days.
- [ ] **C-006:** Schema additions — `wrapped_tool_images`, `refusal_events`, `redteam_runs`, `rotation_events`, `durc_review_queue` tables. Roll into v6.0 stub. 1 day.

### Phase 27-collab (alongside Phase 27)

- [ ] **C-007:** `backend/immune/sec/rotation.py` — credential/key rotation framework. 3 days.
- [ ] **C-008:** `backend/middleware/api_surface_mutation.py` — Crispy-style error-response mutation. 2 days.
- [ ] **C-009:** `backend/immune/sec/refusal.py` + `refusal_middleware.py` — technical refusal mechanisms with HTTP 451. 3 days.
- [ ] **C-010:** `docs/dual_use_review.md` + DURC review queue page. 1 day.
- [ ] **C-011:** `backend/immune/redteam/` skeleton + `attack_amand.py`. 3 days.
- [ ] **C-012:** `.github/workflows/redteam.yml` + `docs/redteam_results/` weekly publication. 1 day.

### Phase 29-collab (alongside Phase 29 federation)

- [ ] **C-013:** `backend/immune/net/asymmetric_trust.py` — fairness-corrected trust calibration. 2 days.
- [ ] **C-014:** `backend/immune/redteam/attack_federation.py` — re-identification attack suite (Trieu lane). 3 days.
- [ ] **C-015:** `docs/protocols/federation_protocol_v0.md` — formal protocol spec for Trieu review. 2 days.

### Phase 30-collab (alongside Phase 30 cyber-AIS)

- [ ] **C-016:** `backend/immune/sec/cs_cyber_federated.py` — federation-wide clonal selection. 4 days.

### Wet-side advisory (Halden)

- [ ] **WW-1:** `docs/wetside_advisory.md` — current assumptions about wastewater sampling cadence, preservation, prep failure modes.
- [ ] **WW-2:** Add "wet-side advisor" role to GOVERNANCE.md.
- [ ] **WW-3:** Pre-register questions for Halden in `docs/decisions/`.

**Definition of done:** Glen walks into a meeting with Forrest's group with the companion doc + working code on these components, presenting each as "we built the scaffolding; here's where your group fits." Each `TODO(<x>-collab):` marker is a paper-or-grant-shaped collaboration hook.
```

### Backlog topic — add a new numbered item after the immune-platform topic

```markdown
### N+1. Collaboration scaffolding for Biodesign group review (2026-05-08)

**Reference document:** `docs/jackpot_immune_collaboration_scaffolding.md` (1908 lines, working MVPs for every gap)
**Vision doc cross-ref:** §18

After landing the immune-platform vision doc (topic N), the next move is showing up to the Forrest/Trieu/Lee/Halden conversation having done the engineering work that's available to do alone. The companion doc addresses five gaps that group would identify on first read of the vision doc:

1. **Monoculture** — federation members all run identical code/featurizers/parameters. Forrest's n-variant systems work explicitly designed against this. Addressed by featurizer registry + per-member `diversity_profile.py` + `diversity.py` Shannon index. `TODO(forrest-collab): coverage theory` is the open question.
2. **Software supply chain** — wrapping 16 OSS projects merges 16 dependency trees with no SBOM, no signing, no CVE gating. Addressed by `generate_sbom.py` (CycloneDX + grype), CI gate, `parsers_safe.py` deserialization policy + Critical Rule, cosign signing for all images. `TODO(forrest-collab): auto-repair` is the open question (GenProg-descendant work).
3. **Static defense posture** — detectors evolve, rest of platform is static. Addressed by `rotation.py` framework + federation-wide `cs_cyber_federated.py` + Crispy-style `api_surface_mutation.py`. `TODO(forrest-collab): mutation cadence theory` is the open question.
4. **Misuse / governance** — AGPL is necessary but insufficient. Addressed by `GOVERNANCE.md` v0 with refusal-to-deploy criteria, `refusal.py` technical middleware (HTTP 451 enforcement), `asymmetric_trust.py` for LMIC fairness, `dual_use_review.md` DURC queue. `TODO(forrest-collab): policy framework` is the open question.
5. **Education-as-afterthought** — Pillar IV is structurally strong but framed fourth. Addressed by `forrest_framing.md` Module 0 + §1 reframing + sibling differentiator paper.

Plus cross-cutting `jackpot-redteam/` track with `TODO(lee-collab)` and `TODO(trieu-collab)` markers covering: synthetic data representativeness (membership inference), iterative attack-defend frameworks, re-identification attacks on federation aggregates, formal privacy budget analysis. Plus Halden wet-side advisory items (WW-1, WW-2, WW-3).

**Posture:** ~70% engineering shipped, ~30% research as deliberate named open questions. Calibrated to signal "we did our homework, here's where we need help" rather than "we don't need collaborators" or "we haven't thought hard enough."

**Phase 26-collab schedule:** ~30 person-days, parallel with Phase 26+. First-sprint quick wins (QW-8 parsers_safe, QW-9 forrest_framing, QW-10 GOVERNANCE.md v0) are 1-day items landable now and unconditionally good practice independent of any collaboration outcome.

**Master collaboration markers index** in companion doc §10:
- 9 Forrest markers (coverage theory, auto-repair, mutation cadence, Crispy at runtime, CSA convergence, policy framework, fairness theory, DURC institution, static enforcement)
- 4 Trieu markers (protocol selection, formal proofs, privacy-preserving red-team, formal privacy budget)
- 3 Lee markers (iterative attack-defend, MIA design, synthetic data representativeness)
- 3 Halden advisory items (sampling cadence, false-positive failure modes, NWSS realities)

Each marker is a paper-or-grant-shaped collaboration hook. Walking into the meeting with this list as a menu of joint work is the right opening move.
```

## What this gets you in a meeting

When you sit down with Forrest, the move is:

1. Hand her the vision doc opened to §18 — "here's what we know is missing."
2. Hand her the companion doc opened to §10 — "here's the menu of where we know we need help."
3. Walk her through Gap 1 (the most legible) — featurizer registry exists, diversity index runs in CI, `TODO(forrest-collab): coverage theory` is the marker. "We built the infrastructure that needs your theory."
4. Repeat for whichever gap she lights up on. The conversation writes itself.

If she lights up on supply chain (likely), Gap 2 is the natural follow-on and points directly at her 2019 ICSE Most Influential Paper on automated software repair.

If she lights up on misuse/governance, Gap 4 has `GOVERNANCE.md` v0 in hand and the `TODO(forrest-collab): policy framework` and `DURC institution` markers point to her Jefferson Science Fellow lane.

That's the whole strategy. Build it, then meet her with the work on the table.



### Musings

piinformatics.org, pythoninformatics.org, pyinformatic.org


Build a field deployable NGS analysis platform for genomic epidemiology based on something like the Turing Pi 2, loaded with Arteria, PanGia, IRIDA (Galaxy), Nextflow & Tower and possibly other tools (Coxbase, Shigella tool, INNUENDO, GLUE, BARD, GenPipes, Nextstrain, EDGE, PathogenWatch, IDseq, Selene, bcbio). Include ML and deep learning genomics (Janggu) software too.


Build a mobile NGS sequencing and and biosurveillance analysis platform in your basement/garage.


Maybe instructions on setting each of these up on a rasp pi platform(piinformatics.org)?

Title: Stop the plague - infectious disease sleuthing with genomics, HPC and ML on Raspberry Pi
Premise: There's a small outbreak in a far away land that the CIA thinks could be a possible bioweapon test. You're given DNA/RNA sequences by the CIA for analysis because the CIA thinks there is a spy/mole in the CDC that will leak information to our enemies and disinformation to the public and our alllies. Even possibly derail the investigation. They hire you as a consultant because of these fears (and your knowledge of all three technologies).

Limited bandwidth comms from field? Comms/directions received as text messages?
Sent files taken off of murdered or on the run agent. Don't even know they are fastq files until you open them up. Then you realize why they were sent to you-- they are fastq files. Get them here:
	Send participants DNA/RNA sequences of various bugs or let them download it from your github site 		(the site of a CIA operative/ally)

Applied, but haven't heard back. Maybe because you don't play well with others. Misanthropic. Introvert. Is this a test?  Nows your chance.

DNA of mystery pathogen from sick, RNA of WBC from blood draw (sick and normal), and microbiome from sick/normal.

Mission:
Determine pathogen (naturally occurring, new variant of naturally occurring pathogen, or bioweapon?
Design analytic, stealth, edge device (contraption) & software for NGS analysis for pathogen samples

Help design vaccine by detecting possible mutations in pathogen sequence, map to protein and use them to create a therapy and/or vaccine based on the altered protein/peptide sequence

Use alphafold to predict protein structure?

Rub: You only have a handful of raspberry pis

Use PanGIA and other tools to figure out what bug you were sent, could be filtered out from microbiome, or maybe ctDNA from blood draws or maybe microbiome and virus/bacteria (multi-drug resistance?)

Install Raspberry Pi cluster in order to run PanGia, IRIDA (Galaxy), Nextflow & Tower and other tools to figure what the sample resembles
Install Raspberry Pi and nextflow, run with local profile, using reference sequence of similar bug
Realize you need more than one machine for larger data sets to be sent
Build Pi cluster, rerun nextflow with Slurm
nextflow pipeline variant calling
CIA wants 1) more security due to spy threats; 2) it to be modular and platform independent so it can run in their secret cloud, so repeat initial analyses
	Distribute data in a more secure way
	Analysis with containers that are encrypted and signed
	Host the repo(s) and a secret/secure repo(s) of data and contaiers
Contests?
Host a raspberry pi yourself for analyses for those who don't have a kit. Could pay for one to be hosted somewhere. I think there are places that do that already for pi.
Host a website for data aggregation of other investigator's data or secret CIA data to be used for machine learning with K8 and made up symptoms

MinIon use to sequence and analyse samples in the field, clandestine Jetson Nano that isn't a laptop to run Guppy on GPU for performance?
super secret Coral TPU for ML of large datasets that isn't a laptop

Build edge device for analysis

Challenge/Adventure- invite one person to advance in the challenge? Online forum for help?

Given all the software tools, you can do it on your own for free (and also use your own tools), or pay $1 (donation) for instructions? Competition for clever solutions?

Multiple threats? Distribute data from multiple threats to "agents" that sign up to help the main character?

Can run pipeline usig local profile or on a cluster. If you have access to one, fine. But also provide the instructions for building one. Also provide access to one. Different point values depending on which compute solution used.

Link to helpful resources carpentry courses, like HPC, nextflow, etc. as well as bio learning sites.

Offer your own pi cluster as an analysis resource and build the challenge around it and distribute how it was built? Folks who build their own can share their experiences
