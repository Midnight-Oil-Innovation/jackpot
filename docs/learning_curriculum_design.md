> **Status:** Reference - JACKPOT Learn curriculum design.

# JACKPOT Learn — Content & Curriculum Design

**Version:** 0.2 (Cluster B merge integration applied 2026-05-16)
**Status:** Pre-implementation scoping. Companion to `docs/learning_strategic_vision.md`. Queued behind P0e (`jackpot init` CLI) and the spine work described in the strategic vision doc.
**Companion docs:** `docs/learning_strategic_vision.md` (the strategic-vision twin); `docs/immune_platform.md` (the parent immune-platform plan that frames Learn as Pillars IV/V); `docs/architecture.md` v6.0 (the canonical architecture reference, including the four scenarios A/B/C/D).

**Version:** 0.1 (design sketch)
**Status:** Companion to `jackpot_learn_strategic_vision.md`. Pre-implementation design; queued behind P0e.
**Audience:** The maintainer; future Academy module authors; Field Edition / SENTINEL / WILDFIRE case authors; instructor partners.

---

## 0. How to read this doc

This is the concrete-content companion to the strategic vision doc. The vision answers *what* and *why*. This one answers *what does the learner actually do*. Cross-references to the vision are marked `[V§X]`.

The doc is long. The structure mirrors the four faces themselves, with shared infrastructure pulled into the front:

1. Foundational pedagogical pattern (the spine of all four faces)
2. Module 0 — Forrest's "why JACKPOT exists" framing (everyone reads this first)
3. **Academy** — structured modules, tracks, assessments, credentials
4. **Field Edition** — solo cinematic case catalog
5. **SENTINEL** — cooperative cell-based season arcs
6. **WILDFIRE** — competitive ARG-flavored campaigns
7. Shared production assets (synthetic data, scenario YAML, live-ops tooling)
8. Contributor model (how community grows the catalog)
9. Live ops model (cadence, GMs, sustainability)
10. Credentialing and portability
11. Cross-face progression paths
12. Open content-design questions

---

## 1. Foundational pedagogical pattern

The single shared learning loop across all four faces, drawn from CTF pedagogy research and the immune-system pedagogy-of-contrast principle:

```text
┌────────────────────────────────────────────────────────────┐
│  1. MOTIVATION   "Here's the attack that ruins your day"   │
│  2. EXPLORATION  "Try the attack yourself in a sandbox"    │
│  3. CONCEPT      "Here's the principle that defeats it"    │
│  4. IMPLEMENT    "Build a working defense in JACKPOT"      │
│  5. EVALUATE     "Red team your defense; measure efficacy" │
│  6. CONTRIBUTE   "Submit your work back as a PR / paper"   │
└────────────────────────────────────────────────────────────┘
```

This applies across all four faces — Academy modules, Field Edition cases, SENTINEL missions, WILDFIRE episodes — though the surface and pacing differ.

### 1.1 Why six stages and not three

The expedient version is "Motivation → Concept → Implement." That's what most tutorials do. The expanded version separates:

- **Motivation from Exploration** — you have to *try and fail* before the concept makes sense
- **Concept from Implement** — knowing the principle isn't the same as building the thing
- **Implement from Evaluate** — most learners stop at "it works on the demo input" — Evaluate is where they red-team their own work
- **Evaluate from Contribute** — Evaluate is private; Contribute is public and attribution-preserving

The Contribute stage is what makes JACKPOT Learn Biodesign-grade rather than bootcamp-grade. Foldit got peer-reviewed papers because players' designs landed in the actual research pipeline. JACKPOT modules and cases can do the same.

### 1.2 Per-module artifact checklist

Every Academy module follows the same directory shape so that contributors learn it once:

```text
course/<stream>/<module>/
├── SKILL.md                 # the module's contract
├── lecture.ipynb            # readable explanation
├── lab-attack.ipynb         # student plays the attacker first
├── lab-defend.ipynb         # then builds the detector
├── scenario.yaml            # synthetic data + answer key (canonical format)
├── assessment.py            # auto-grader
├── badge.sigstore.bundle    # signed credential template
└── README.md                # one-paragraph student-facing summary
```

Field Edition cases, SENTINEL missions, and WILDFIRE episodes use the same `scenario.yaml` schema and the same synthetic data pipeline, but skip the `lecture.ipynb` and `assessment.py` — their pedagogy is embedded in narrative rather than instructor explanation.

### 1.3 The `SKILL.md` contract

Borrowed from Anthropic's skill format. Each module's `SKILL.md` declares:

```markdown
# <Module Title>

**Stream:** innate / adaptive / privacy / biosecurity / platform / federation
**Track:** A (Defender) / B (Builder) / C (Architect)
**Prereqs:** <module IDs>
**Time:** <hours>
**JACKPOT version pinned:** <git SHA at time of last review>

## Learning outcomes
By the end of this module, the learner can:
- ...

## What's in the upstream JACKPOT codebase
- backend/path/to/relevant/module
- pipelines/path/to/relevant/pipeline

## What the learner contributes back (Contribute stage)
- ...
```

Standardizing the contract is what lets external contributors propose modules without inventing a new format each time.

---

## 2. Module 0 — Why JACKPOT exists, why you're here

Every learner sees this first, regardless of which face they came in through. Reproducing the text in full from `docs/immune_platform.md` §18.5 (originally from the collaboration scaffolding §7.2.1, now merged into immune_platform.md), lightly adjusted for the four-face context:

```markdown
# Module 0 — Why JACKPOT exists, and why you're here

## The integration thesis

JACKPOT is not a product that happens to have a curriculum. It is a workforce
development platform that happens to also do pathogen genomic surveillance.

This framing comes from Stephanie Forrest's articulation of the Biodesign
Center mission: "translating insights between computer science and biology,
with a focus on understanding and mitigating malicious behavior in complex
systems," and her explicit warning against technologists "isolated from those
who actually use or are affected by it on a daily basis."

JACKPOT Learn exists because:

1. Public health workforce capacity is the rate-limiting factor in pandemic
   preparedness, more so than tooling.
2. Tooling built without the workforce in mind is built wrong.
3. The fastest way to make sure JACKPOT is the right tooling is to make sure
   people learning genomic surveillance learn it ON JACKPOT.

## What this means for you, the learner

- You are not learning ABOUT JACKPOT. You are learning genomic surveillance,
  and JACKPOT is the lab.
- Your module exercises produce code that gets PR'd to the production
  platform.
- Your wrong answers in Field Edition / SENTINEL / WILDFIRE generate
  adversarial training data for the production immune system.
- You graduate with a public, attribution-preserved record of your
  contributions to a real platform used by real public-health labs.

## The four faces

You're entering JACKPOT Learn through one of four doors:

- The **Academy** is structured learning. Disciplined. You leave with
  credentials and merged PRs.
- **Field Edition** is solo narrative. Cinematic. You leave with the "huh,
  I could actually do this job" moment.
- **SENTINEL** is cooperative. You and 3–7 teammates fight an outbreak.
  You leave knowing what crisis-cooperation feels like.
- **WILDFIRE** is competitive. You join a cell. You compete against other
  cells in a federated espionage scenario. You leave with real OPSEC
  literacy.

You can start anywhere. You can move between faces. The credentials carry
across.

Now go pick a door.
```

---

## 3. Academy curriculum

### 3.1 Three tracks, defined

| Track | Audience | Bar to enter | Bar to complete |
|---|---|---|---|
| **A — Defenders** | UG students, lab technicians, professionals new to bioinformatics | Module 0 read | All modules in the Innate + Adaptive streams; one capstone red-team writeup |
| **B — Builders** | Grad students, advanced practitioners, working bioinformaticians | Track A complete OR equivalent demonstrated | All Innate + Adaptive + Privacy modules; one merged PR to JACKPOT |
| **C — Architects** | Faculty, senior researchers, module owners | Track B complete + invitation | Ownership of a module; ≥5 merged PRs to JACKPOT; named in academic paper |

Tracks aren't strictly sequential — a working bioinformatician with a PhD can skip Track A and start in Track B. But the credential chain still requires the lower-track bar (the Track A modules' assessments) to be demonstrated.

### 3.2 Streams and modules

Six streams, each a thematic bundle of modules. Module counts are 0.1-version-of-the-curriculum targets; the catalog will grow.

#### Stream 1 — Innate Immunity (5 modules, mostly Track A)

| # | Title | AIS analog | Hands-on tools |
|---|---|---|---|
| 1 | Sequencing 101 | The "PAMPs" we're built to recognize | FASTQ inspection, quality scores |
| 2 | Linux & Python for genomics | Tooling | bash, pandas, biopython |
| 3 | QC, host scrubbing & file detection | Skin and mucus — PAMP recognition + self-filtration | fastp, NanoPlot, HRRT, `file_detector.py` walkthrough |
| 4 | Taxonomic ID | First-pass recognition | PanGIA, Kraken2, mash screen |
| 5 | Anomaly score basics | Detector calibration | A tiny NSA detector against synthetic data |

#### Stream 2 — Adaptive Immunity (5 modules, mostly Track A/B)

| # | Title | AIS analog | Hands-on tools |
|---|---|---|---|
| 6 | Assembly & variant calling | Antibody affinity maturation | SPAdes, Flye, Snippy, BCFtools |
| 7 | AMR & virulence | Memory cells | CARD, AMRFinderPlus, abricate, VFDB; `jackpot-amrmemory` |
| 8 | Phylogenetics & clusters | Clonal selection | iqtree, Nextclade, UShER, cgMLST |
| 9 | Negative selection in practice | Detector training | Custom detector implementation; targets `backend/immune/bio/amand.py` |
| 10 | Dendritic-cell signals (DCA) | Multi-modal integration | Multi-pipeline result fusion; targets `backend/immune/bio/dca_bio.py` |

#### Stream 3 — Privacy-Preserving Computation (14 modules, originally sketched in the legacy doc `docs/archived/jackpot_ais_legacy.md`, mostly Track B)

Pre-existing module lineup, restated:

**Foundations (4):**
| # | Title |
|---|---|
| PP-1 | Threat Models & Attack Taxonomy |
| PP-2 | De-identification, Pseudonymization, and Why They're Not Enough |
| PP-3 | Synthetic Data: Generation, Utility, and Limits |
| PP-4 | Threat Modeling Exercise (capstone for foundations) |

**Differential Privacy (3):**
| # | Title |
|---|---|
| PP-5 | DP Theory You Actually Need |
| PP-6 | DP Mechanisms in Practice |
| PP-7 | Composition and Budgets |

**Federated Learning (2):**
| # | Title |
|---|---|
| PP-8 | FL Architecture and Aggregation |
| PP-9 | Adversarial Robustness in FL |

**Cryptographic Computation (3):**
| # | Title |
|---|---|
| PP-10 | Homomorphic Encryption (CKKS, BFV, BGV) |
| PP-11 | Secure Multi-Party Computation |
| PP-12 | Private Set Intersection |

**Hardware Trust + Composition (2):**
| # | Title |
|---|---|
| PP-13 | Trusted Execution Environments |
| PP-14 | Composing Privacy Techniques (Capstone) |

#### Stream 4 — Biosecurity (4 modules, Track B/C)

| # | Title |
|---|---|
| BS-1 | Sequence Screening Fundamentals (SeqScreen, FunSoCs) |
| BS-2 | DURC Review |
| BS-3 | Engineered or Evolved? — Attribution Forensics |
| BS-4 | AI-Bio Convergence — Risks and Defenses |

#### Stream 5 — Platform (4 modules, Track B/C)

| # | Title |
|---|---|
| PLAT-1 | JACKPOT Internals — Architecture Walkthrough |
| PLAT-2 | Pipeline Engineering (Nextflow / Snakemake / WDL / BYOP) |
| PLAT-3 | Multi-Tenancy and RBAC |
| PLAT-4 | Deployment Targets — the four scenarios A/B/C/D and the runtime configurations (federation, multi-tenancy, sovereignty) layered on top (per `docs/architecture.md` §3) |

#### Stream 6 — Federation (4 modules, Track B/C)

| # | Title |
|---|---|
| FED-1 | Federation Concepts and the Three Levels |
| FED-2 | Privacy-Preserving Federated Queries |
| FED-3 | Federated Immune Memory (cross-tenant clonal selection) |
| FED-4 | Federation OPSEC (capstone — companion to the WILDFIRE OPSEC mechanics) |

**Total modules for v1 of the Academy: 36.** Plenty for 2 years of cohorts before the maintenance treadmill becomes a problem.

### 3.3 Cohort patterns

Four shapes the Academy supports out of the box:

| Cohort shape | Pace | Time per learner | Best for |
|---|---|---|---|
| **Self-paced async** | Whenever | Variable | Solo learners, LMIC fellows on intermittent connectivity, anyone evaluating before committing |
| **8-week live cohort** | One module per week | ~8 hours/week | Professional development cohorts, APHL-style fellowships |
| **University semester** | 2–3 modules per week | ~5 hours/week | Graduate elective, capstone-aligned |
| **Institutional partner cohort** | Custom | Per agreement | Partner-tier engagements (state PHA staff, IPSN regional capacity-building) |

The same module assets (notebooks, scenario, assessment, badge) work across all four cohort shapes. The only difference is the orchestration layer (cohort scheduler, instructor dashboard, communication channel).

### 3.4 Assessment philosophy

Three layers of assessment per module:

1. **Auto-graded notebook checkpoints** — does the code run, do the values match expected ranges. Pass/fail.
2. **Auto-graded scenario evaluation** — does the student's detector / classifier / query achieve a target metric against the held-out synthetic data. Quantitative score.
3. **Red-team writeup** — written reflection on what the student would do differently, where the failure modes are. Human-reviewed (instructor for cohort; peer for async).

Layer 3 is what separates module pass from credentialed competency. An auto-grader can't catch "the student got the right answer for the wrong reason." Peer review can.

### 3.5 Credentialing — signed JWTs

Every successful module pass issues a signed JWT, version-pinned to the JACKPOT commit at the time of issuance. Pseudo-format:

```json
{
  "iss": "https://learn.jackpot.example/issuer",
  "sub": "<learner-id>",
  "credential": "module-pass",
  "module": "stream-1/04-taxonomic-id",
  "jackpot_version": "abc123def456",
  "assessment_score": 0.91,
  "issued_at": "2026-09-12T14:23:00Z",
  "valid_against_version": "abc123def456",
  "still_valid_against": ["def456abc789", "789def456abc"]
}
```

The `still_valid_against` field is the gracefully-aging part: if a later JACKPOT version made breaking changes to the module's APIs, the credential is still verifiably-earned, but new modules built against the newer version may require re-attestation.

Aggregate credentials (track completion, maintainer status, architect status) are signed compositions of module-pass credentials.

OIDC discovery endpoint at `/.well-known/openid-configuration` so any third party can verify a credential without contacting JACKPOT Learn directly. This is what makes the credentials portable.

---

## 4. Field Edition — solo case catalog

Single-player narrative loop. No accounts required for the local-only "anonymous play" mode; account-linked play unlocks credential issuance.

### 4.1 Per-case structure

```text
1. Briefing      — 1–2 minutes. Setting, who you are, what's happening.
2. The Lab       — 10–60 minutes. The actual bioinformatics work.
3. Analysis      — 5–30 minutes. Make a call. Submit a report.
4. Reflection    — 2–5 minutes. What did the case actually test? What
                   would you do differently?
5. Reveal        — 1 minute. The answer key, presented cinematically.
```

The Reflection stage is what makes Field Edition pedagogically respectable rather than just gameified bioinformatics. Without Reflection, the player gets a score and moves on. With it, they internalize the principle.

### 4.2 Case catalog — v1 (12 cases)

The 8 cases sketched in the legacy doc (`docs/archived/jackpot_ais_legacy.md` Part 3 — also reflected in `docs/immune_platform.md` §8.2.3 as the AIS-mapped case progression) + 4 new cases to round out the catalog:

| # | Title | Anomaly type | Tools exercised | Stream affinity |
|---|---|---|---|---|
| 01 | The First Patient | Ordinary pathogen ID | Kraken2 + Bracken | Innate (warm-up) |
| 02 | The Strange Reader | Sample matches no reference | MG2Vec embedding distance, AMAnD anomaly score | Adaptive |
| 03 | The Synonymous Mutation | Same protein, suspicious codons | Codon bias analyzer, host-comparison stats | Biosecurity |
| 04 | The Drifting Lineage | Variant accumulating mutations faster than expected | UShER placement + branch-length stats | Adaptive |
| 05 | The Quiet Outbreak | Wastewater rising edge before clinical signal | Freyja 2, sewershed deconvolution | Federation |
| 06 | The Borrowed Genome | AMR cassette from unexpected donor | hAMRonization, HGT detection | Adaptive |
| 07 | The Friendly Neighbor | A peer cell submits subtly poisoned data | Federation OPSEC, trust calibration | Federation |
| 08 | The Engineered Question | Engineered or evolved? Attribution puzzle | ESM3 / AlphaFold3 surface analysis, SeqScreen | Biosecurity |
| 09 | *(new)* The Vanishing Variant | A lineage that should be there isn't | Allele-frequency stats, sampling bias | Privacy/Stats |
| 10 | *(new)* The Mole's Trail | Audit log forensics from a "leaked" tenant | Audit-log inspection, attribution | Platform |
| 11 | *(new)* The Tribal Sample | Sovereign-data handling decision | CARE Principles application, deletion-on-request | Governance |
| 12 | *(new)* The Endemic Pressure | Long-arc AMR + climate scenario | Multi-pipeline integration, time-series viz | Capstone |

Each case has a `scenario.yaml` and a Streamlit narrative wrapper. The synthetic data is reproducible from the scenario YAML — anyone can regenerate the dataset locally and verify the answer key.

### 4.3 Case licensing

Cases are CC-BY-SA. Anyone can fork, translate, adapt; the adaptation has to stay CC-BY-SA and attribute the original. This is what enables the open contributor model in §8 without sacrificing the LMIC translation pathway.

### 4.4 Sequel-case cadence

After v1's 12 cases, target one new case every 4–6 weeks. With community contributions (per §8), the cadence can go faster without burning out the maintainer.

---

## 5. SENTINEL — cooperative cell-based gameplay

The cooperative twin of WILDFIRE. *Pandemic*-the-board-game energy with real bioinformatics. Per the legacy sketch (`docs/archived/jackpot_ais_legacy.md`): this is the recommended first game build because it's the most credible as real workforce training.

### 5.1 Cell structure

3–7 players per cell. Each player has a role; roles complement each other:

| Role | Game ability | Real-world analog |
|---|---|---|
| **Laboratorian** | Best sample prep skills; runs QC pipelines fastest; sees raw read metrics in detail | Bench scientist |
| **Bioinformatician** | Runs analytical pipelines; assembles/variant-calls; reads alignments | Genomic-epi staff bioinformatician |
| **Epidemiologist** | Sees map-level data; can request samples from specific locales; interprets context | State epi |
| **Coordinator** | Sees all teammates' views; coordinates federation queries; speaks for the cell at briefings | Lab director / response coordinator |
| **Public-comms** (5+ player cells) | Drafts public-facing risk assessments; loses points for misleading statements | PIO |
| **Privacy officer** (6+ player cells) | Reviews data-sharing requests; manages DP budget | Compliance / IRB liaison |
| **Sovereignty steward** (7+ player cells) | Handles Tribal/jurisdictional data with CARE-aware rules | Tribal IRB designee / data-residency officer |

Roles are not strict — a 3-player cell distributes responsibilities. But the role-aware view filters are what make the cooperative-information-asymmetry game work: nobody has the full picture.

### 5.2 Season arcs — v1 (5 seasons)

| Season | Title | Premise | Length | Mandatory mechanics |
|---|---|---|---|---|
| **S1** | Patient Zero | Novel respiratory pathogen, classic intro arc | 6 missions, ~6 weeks | Basic ID, simple federation |
| **S2** | Out of the Lab | Engineered vs evolved attribution puzzle | 8 missions, ~8 weeks | Attribution, SeqScreen |
| **S3** | One Health | Zoonotic spillover; clinical + animal + environmental + wastewater integration | 10 missions, ~10 weeks | Multi-sample-type schema, Freyja |
| **S4** | The Mole | Audit-log forensics inside your own cell — one teammate is compromised | 6 missions, ~6 weeks | Audit-log inspection, trust calibration |
| **S5** | Endemic | Long arc; AMR + climate; mandatory federation play | 12 missions, ~12 weeks | Multi-cell federation; year-round AMR tracking |

Each season ships with a season-arc storyline plus per-mission goals. Missions have a real-time clock (the outbreak is evolving), which is what creates the *Pandemic*-board-game pressure.

### 5.3 Per-mission structure

Each mission has the same shape, similar to Field Edition's case structure but oriented around team coordination:

```text
1. Briefing       — Whole cell. 5–10 min. Mission goal + new constraints.
2. Asymmetric brief — Per-role. 2 min each. Role-specific intel.
3. Coordination   — 15–30 min. Cell decides division of labor + comm plan.
4. Execution      — 60–180 min. Each player does their work; federation
                    queries flow through the Coordinator.
5. Synthesis      — 15–30 min. Cell assembles a unified call.
6. Submit         — A single report goes to the live-ops scoring system.
7. Debrief        — 20 min. Reveal + cell self-critique.
```

Real-time clock runs through stages 3–6 with a hard deadline. Late submissions are scored but penalized — same as real outbreak response.

### 5.4 Cooperative information-asymmetry mechanics

This is the load-bearing game design. Each role sees a subset of the data — and only the data they could realistically have access to in their real-world role. The Bioinformatician sees alignments and variant calls but not epi context. The Epidemiologist sees the map and case counts but not raw reads. The Coordinator sees aggregated views but not raw data from any single role.

To solve the mission they have to *talk*. The talking has to be efficient (the clock is ticking) and accurate (misinformation between roles costs the cell).

This is the part that maps directly to real PH workforce training. The hard part of an outbreak isn't reading a phylogeny — it's communicating findings across roles with different vocabularies under time pressure.

### 5.5 Classroom variants

Three deployment shapes for Edu-tier:

| Variant | Shape | Best for |
|---|---|---|
| **Single classroom** | 1 cell = 1 class | Small grad seminar, professional development workshop |
| **Multi-classroom federation** | Multiple cells = multiple classes, federation play between them | Multi-institution program (e.g. a PGCoE network exercise) |
| **Live tournament mode** | Multiple cells in a time-boxed competitive league | Conference workshop, hackathon, capstone showcase |

The federation variant is the most pedagogically valuable — students experience real federation OPSEC against people they don't know.

---

## 6. WILDFIRE — competitive ARG-flavored campaign

The competitive twin of SENTINEL. Espionage-flavored. Long-running cells, ARG layer, real adversarial federation play.

### 6.1 What "competitive" means here

Cells compete for:

- **Story-arc progress** — first cell to solve a season's central mystery
- **Attribution accuracy** — points for correctly identifying anomalies; deductions for false positives
- **OPSEC** — points for *not* leaking your own samples/queries to opponents
- **Federation reputation** — running average of how much your peer cells trust your submissions

The opponent isn't really the other cells — it's the game state itself. But the leaderboard creates the social pressure that makes the game stick.

### 6.2 Season arcs — v1 (6 seasons)

| Season | Title | Premise | Mandatory mechanics |
|---|---|---|---|
| **S1** | Patient Zero | Novel respiratory pathogen; intro to cell mechanics | Basic ID, OPSEC scoring |
| **S2** | Out of the Lab | Engineered vs evolved; attribution via ESM3 / AlphaFold3 | Attribution puzzle, signed-pipeline verification |
| **S3** | One Health | Zoonotic spillover; clinical + animal + environmental | Multi-sample-type federation |
| **S4** | The Mole | A compromised cell submits subtly poisoned samples | Trust calibration, adversarial-submission detection |
| **S5** | Endemic | Long arc; AMR + climate; **mandatory federation, mandatory wastewater coverage** | Full federation play |
| **S6** | The Agent Wars | Adversarial AI agents sabotaging each other's analyses; defensive prompt engineering as gameplay | LLM-agent integration, prompt-injection literacy |

S6 is the most genuinely novel — no existing game or training program covers prompt-injection defense as a hands-on competency.

### 6.3 Competitive mechanics

From the legacy sketch (`docs/archived/jackpot_ais_legacy.md` Part 3; also reflected in `docs/immune_platform.md` §8.3.3 as the AIS-mapped mechanics), restated:

| Mechanic | What it teaches |
|---|---|
| **Dead drops** | fastq+metadata files; sometimes obfuscated, sometimes adversarial | File-type defense, NSA detector calibration |
| **The mole** | A compromised cell submits subtly poisoned samples; the team must figure out which and how | Trust calibration, poison detection |
| **OPSEC scoring** | Your queries to federation reveal info about your samples; bad query design leaks intel | Federation OPSEC literacy |
| **Speed vs accuracy** | Faster classifiers give worse ensembles; full bio-anomaly stack costs time; outbreak clock ticks | Detector affinity vs context |
| **Trust calibration** | Your LLM analyst-agent confidently IDs a pathogen — but the ensemble disagrees; who's right? | Detector affinity vs context |
| **Adversarial submissions** | Other cells can submit data to your federation; some real, some decoys, some hostile | Adversarial training data |
| **Attribution puzzles** | Engineered or evolved? | Structural prediction, sequence forensics |
| **Sealed evidence** | Append-only `pipeline_results` immutability becomes legal-chain-of-custody flavor | Audit-log discipline |
| **Compromised tooling** | Opponents can publish a poisoned StaPH-B clone; you have to verify | Container-signing literacy |

### 6.4 The ARG layer

Annoying-nerd-bait of the highest order, per the original sketch:

- Occasional clues hidden in genome sequences (a designed silent mutation that spells out an IP address in ASCII when you translate the protein)
- Cross-puzzle clues that require federation cooperation across cells
- Live-ops dropping in-character messages on a Mastodon instance
- Rare wet-lab tie-ins (the optional Twist Bioscience reference standard) where physical kits unlock season achievements

The ARG layer is what makes WILDFIRE *fun* in the way that Foldit and EteRNA were fun. It's also entirely skippable for players who just want the bioinformatics game.

### 6.5 Cross-pollination back to other faces

The WILDFIRE community generates the highest volume of adversarial test cases. After a WILDFIRE season ends:

- Every poisoned-submission scenario that worked becomes a Field Edition case
- Every novel attribution puzzle becomes an Academy assessment
- Every OPSEC-failure pattern becomes a SENTINEL mission

WILDFIRE is the *generator*; the other three faces are the curators. This is what makes the four-face system compound rather than just coexist.

---

## 7. Shared production assets

The shared spine elements that all four faces consume, with concrete artifacts named.

### 7.1 Synthetic data generator

A single Nextflow workflow at `pipelines/synthdata/` that consumes a `scenario.yaml` and produces:

- FASTQ files (Illumina-style, Nanopore-style, or both — configurable per scenario)
- Metadata files (PHA4GE-formatted, optionally with intentional "noise" for cases that test data-hygiene skills)
- Answer-key JSON (private; consumed by the assessment evaluator, not shipped to learners)
- Reference checksums (so learners can verify their dataset is the canonical one)

Generation tools: `wgsim` (Illumina short reads), `badread` (Nanopore long reads), `ART` (Illumina alternative), `dwgsim` (paired-end with errors), `polyester` (RNA-seq). All are open-source. Reference genomes are public.

### 7.2 Scenario YAML format

The single canonical format that all four faces consume. Sketch:

```yaml
scenario_id: stream-2/09-negative-selection
title: "The Strange Reader"
abstract: "A sample with no taxonomic match. What is it?"
face: field-edition          # or: academy / sentinel / wildfire
stream: adaptive
prereqs:
  - stream-1/04-taxonomic-id
synthdata:
  reference_genomes:
    - NC_045512.2              # SARS-CoV-2 (decoy)
    - GCF_000819615.1          # something more unusual (target)
  read_count: 1_000_000
  platform: illumina_paired
  error_profile: HiSeq2500
  contamination:
    target_pct: 5.0
    decoy_pct: 95.0
metadata:
  collection_date: 2026-03-14
  geo_loc_name: synthetic
  intentional_pii_noise: false
expected_pipeline_results:
  taxprofiler:
    kraken2_top_hit_classification: "Unclassified"
    expected_anomaly_score: ">0.7"
answer_key:
  correct_identification: "GCF_000819615.1"
  anomaly_type: "novel-pathogen"
  scoring_rubric:
    - { criterion: "identified_anomaly", points: 50 }
    - { criterion: "used_embedding_distance", points: 30 }
    - { criterion: "documented_reasoning", points: 20 }
narrative:
  briefing: "..."
  reveal: "..."
license: CC-BY-SA-4.0
contributors:
  - github: someone
```

The format is LinkML-defined (like JACKPOT's other schemas), validated at PR time, and consumed by:

- The synthetic data generator (synthdata block)
- The assessment evaluator (expected_pipeline_results + answer_key blocks)
- The narrative wrapper UI (narrative block)
- The credential issuer (after submission scoring)

One format. Four consumers. That's the spine working.

### 7.3 Reference standard kit (optional wet-lab tie-in)

Per the legacy sketch's reframe (`docs/archived/jackpot_ais_legacy.md`): a one-time community kit, not a recurring revenue line. Twist Bioscience synthetic-DNA fragment with a hidden in-game "flag" encoded in synonymous codons. Mailed at cost to learners who have access to a sequencer and want the optional wet-lab achievement.

Marginal cost per participant: a few dollars + shipping. No reagents required of anyone who doesn't want them.

### 7.4 Live-ops tooling

A small set of internal admin tools:

| Tool | Purpose |
|---|---|
| **Case-authoring CLI** | `jackpot learn case new --face sentinel --season S2 --episode 03` scaffolds a scenario YAML |
| **Scenario validator** | Lints a scenario YAML against the LinkML schema; runs the synthetic data generator in dry-run mode |
| **Live-ops dashboard** | Shows cell activity, mission completion, leaderboards (per face) |
| **Editorial release tool** | Marks a scenario as "released" — moves it from `cases/staging/` to `cases/live/`, triggers credential issuer updates |
| **Crisis-rollback tool** | Pulls a case from live status if it turns out to be problematic (ethics, technical bug, real-world adjacency) |

All five are FastAPI + small Streamlit dashboards. No new tech needed.

### 7.5 Federation hub for cross-tenant games

SENTINEL multi-classroom federation and all WILDFIRE play need a federation hub instance. Reuses the existing FED-A/B/C/D/E federation work — the games are just opinionated tenants on the same federation.

The hub itself has live-ops affordances the standard federation doesn't: a "current season state" view, GM-controlled events, scenario-progress visualization.

---

## 8. The contributor model

Open mission framework: anyone can author a case via PR. Same shape regardless of which face.

### 8.1 Repo layout

```text
cases/
├── academy/
│   ├── stream-1-innate/
│   │   ├── 01-sequencing-101/
│   │   ├── 02-linux-python-genomics/
│   │   └── ...
│   ├── stream-2-adaptive/
│   ├── stream-3-privacy/
│   ├── stream-4-biosecurity/
│   ├── stream-5-platform/
│   └── stream-6-federation/
├── field-edition/
│   ├── 01-the-first-patient/
│   ├── 02-the-strange-reader/
│   └── ...
├── sentinel/
│   ├── S1-patient-zero/
│   │   ├── 01-arrival/
│   │   ├── 02-the-clinic/
│   │   └── ...
│   └── S2-out-of-the-lab/
├── wildfire/
│   ├── S1-patient-zero/
│   └── ...
└── CONTRIBUTING-cases.md
```

Each leaf directory has the same shape: `scenario.yaml`, `assessment.py` (Academy only), narrative assets, contributor README.

### 8.2 Review process

A case PR is reviewed against four criteria:

1. **Scenario YAML validates** — automatic CI check
2. **Synthetic data generates successfully** — automatic CI check
3. **Answer key is correct** — automated by running the canonical reference pipeline against the generated data
4. **Editorial review** — human reviewer checks narrative coherence, ethics, real-world adjacency, sensitivity

Items 1–3 are mechanical. Item 4 is what protects the platform from drift. Editorial reviewers are recruited from the Track C Architects.

### 8.3 Attribution

Every merged case keeps the contributor as the author in git history. Credentials issued against that case mention the case ID, which transitively credits the author. Architects-track participants get a named entry in `OWNERS.md`.

### 8.4 Case licensing carve-outs

Cases are CC-BY-SA-4.0 by default. Two exceptions to consider:

- **Partner-tier custom cases** — a paying Partner may want their custom case kept private to their cohort. Acceptable; their custom case lives in their tenant's private namespace, not in the public repo.
- **Sensitive cases (Tribal data, ongoing outbreaks)** — may be held in private review for an extended period. The Editorial reviewers and the relevant Tribal authority designees decide release timing.

---

## 9. Live ops model

The maintenance treadmill that's most likely to break the model if mismanaged.

### 9.1 Cadence

| Face | Content cadence | Live-ops touch points |
|---|---|---|
| **Academy** | New modules at 1 per 6–8 weeks; new cohort sessions on partner schedule | Cohort kickoff + weekly office hours during a cohort |
| **Field Edition** | New cases at 1 per 4–6 weeks | None — entirely async |
| **SENTINEL** | New mission per active season per week | Weekly mission-drop + debrief; GM presence in-cell for crisis missions |
| **WILDFIRE** | New episode per active season per week + ARG drops | Daily-ish; live arbitration of ambiguous cases; in-character community presence |

WILDFIRE is the most live-ops-intensive. That's why §11 of the vision doc explicitly ties live-ops staffing to the Partner tier — no partner, no real-time season.

### 9.2 GM model

Volunteer GMs are necessary for sustainability. Recruiting pipeline:

```
Field Edition completion → Academy Track A → SENTINEL playthrough →
WILDFIRE participation → GM apprenticeship → GM
```

GM apprenticeship is structured: shadow a live GM through one season, then run a small cohort under supervision, then run independently. GMs get the Architects-track credential.

### 9.3 Burnout mitigation

The doc explicitly mentions "small group runs weekly story beats." That doesn't scale. Three structural mitigations:

1. **Most content is pre-recorded.** Live-ops is reserved for the moments that demand presence (debriefs, ambiguous-call arbitration, ARG drops).
2. **The community generates ≥50% of cases by Year 2.** Maintainer reviews; community writes.
3. **Partner-tier engagements include scheduled live-ops slots.** A partner's cohort gets a real live GM for the duration of their cohort. Outside that, things run async.

---

## 10. Credentialing and portability

Already touched on in §3.5; expanding here.

### 10.1 Credential types

| Level | Bar | Scope |
|---|---|---|
| **Module pass** | Passed assessment for one module | Single module |
| **Case completion** | Solved a Field Edition case | Single case |
| **Mission completion** | Played a SENTINEL/WILDFIRE mission to a passing standard | Single mission |
| **Season completion** | All missions in a season | Season-wide |
| **Track completion** | All modules in a track | Academy track-wide |
| **Maintainer** | Owns a module, ≥5 merged PRs, peer-reviewed contributions | Module ownership |
| **Architect** | Module designer, named in academic paper, recruited GM trainees | Platform-wide named role |

### 10.2 Verification

Public OIDC discovery + verification UX at `/verify`. Drop a JWT, get a human-readable summary: "Verified — this credential was issued by JACKPOT Learn on 2026-09-12 to learner ID xyz for module stream-1/04, version-pinned to commit abc123. Still valid against current commit def456."

Easy enough that an employer reviewing a CV can verify in 10 seconds.

### 10.3 LMS integration (Edu tier)

LTI 1.3 makes Academy modules embeddable in Canvas, Moodle, Blackboard, Open edX. Decision deferred per the vision doc's open question 2 — but the API surface should be future-proof.

### 10.4 Co-signing (Partner tier)

A Partner can co-sign credentials issued to their cohort. The resulting JWT has both the JACKPOT Learn issuer and the Partner issuer as signers. APHL-co-signed Academy credentials carry more weight than self-issued ones.

This is the path to APHL/CDC CSELS/WHO IPSN credential overlays without re-architecting anything.

---

## 11. Cross-face progression paths

What does a typical learner journey look like?

### 11.1 The Defender path (UG / professional new-to-bioinformatics)

```
1. Module 0 (the framing meta-module)
2. Field Edition Case 01 (free trial)
3. Academy Stream 1 (Innate; 5 modules, ~30 hours)
4. Academy Stream 2 (Adaptive; 5 modules, ~40 hours)
5. SENTINEL S1 in a classroom cohort (cooperative practice)
6. Field Edition Cases 02–06 (apply skills solo)
7. Track A capstone red-team writeup
   ──── earns "Defender Track Completion" credential ────
8. (optional) WILDFIRE S1 — first competitive experience
9. (optional) GM apprenticeship
```

Realistic timeline: 9–12 months part-time, or one semester full-time.

### 11.2 The Builder path (grad student / advanced practitioner)

```
1. Skim Module 0 + Stream 1
2. Pass Stream 2 (Adaptive) assessments
3. Stream 3 (Privacy) — the heavy lift; 14 modules over a semester
4. Stream 4 (Biosecurity) + Stream 5 (Platform)
5. SENTINEL S3 (One Health) — applied integration
6. Submit a Builder PR to a JACKPOT module
   ──── earns "Builder Track Completion" credential ────
7. WILDFIRE S5 (Endemic) — long-arc federation
8. (optional) Author a new case via PR
```

Realistic timeline: 12–18 months. Maps cleanly to a master's thesis or a postdoc training year.

### 11.3 The Architect path (faculty / senior researcher)

```
1. Demonstrate Track B equivalent
2. Propose a new module via RFC process
3. Own that module — design, author, maintain
4. Recruit Track A/B learners through your module
5. Co-author the JACKPOT Academy paper or a methods paper using the module
   ──── earns "Architect" named role in OWNERS.md ────
6. Train apprentice GMs
7. Sit on the editorial board for case review
```

This is a long-term commitment. Most architects are also academic-grant PIs with research teams; the architect role is part of their academic identity.

### 11.4 The Sovereign path (Tribal authority / IPSN regional fellow)

```
1. Module 0 read locally (offline-capable)
2. Field Edition Cases 01 + 11 (The Tribal Sample) — establishes the
   CARE-aware framing
3. Academy Stream 1 + 2 (Innate + Adaptive) on local JACKPOT install
4. Optional: federation-aware modules in Stream 6 only if/when the
   sovereign authority decides to participate in federation
5. Sovereign-issued credentials co-signed by the Tribal authority or
   IPSN regional office
```

The Sovereign path's distinguishing feature is that the credential is co-signed by the sovereign authority, not by JACKPOT Learn alone. CARE-aware by construction.

---

## 12. Open content-design questions

Questions that need answers when implementation starts but don't need them now:

1. **Who owns the canon?** Does Field Edition Case 02's strange-reader pathogen exist in WILDFIRE S2's canon? Worth an editorial-board decision before season planning.
2. **Real-pathogen vs fictional-pathogen policy.** When does a case use a real reference genome (educational realism) vs. a wholly fictional one (clean-canon)? Default to real-reference + synthetic-mutations; flag exceptions.
3. **Cases adjacent to ongoing outbreaks.** Moratorium policy: how long after a real-world outbreak ends before we can ship a case loosely inspired by it? 12 months minimum, sensitivity review required.
4. **Adversarial-content vetting.** WILDFIRE's S6 (Agent Wars) and S4 (The Mole) both have intentional adversarial elements. Editorial pre-publication checklist needed.
5. **IP carve-outs.** University partners may want their student-authored cases to remain attributable. The default attribution model handles this, but co-author universities may want explicit acknowledgement language in the credential. Worth a Partner-tier contract template.
6. **Sensitivity review for biosecurity stream.** Stream 4 (Biosecurity) deliberately teaches DURC review and engineered/evolved attribution. Some of the techniques have dual-use concerns. The Bio-AIS work in JACKPOT-immune-platform already addresses some of this — Academy needs to inherit the same review discipline.
7. **Localization / translation strategy.** English-first vs. multilingual-from-day-one. Cost is real; deferring isn't free either.
8. **Accessibility.** Screen-reader compatibility for the narrative UI; alt-text on all generated visualizations; keyboard-navigation throughout. Not blocking for v0.1 but mandatory for Partner-tier.
9. **AI-assisted case authoring.** LLM-assisted scenario drafting is tempting and saves real time, but introduces hallucination risk and bio-content drift. Policy: LLM-assisted drafts allowed; human author + human reviewer required; no fully autonomous case generation.
10. **Case half-life.** When does a case become "too old to keep live"? Tool versions change, anomaly-detection state-of-the-art moves. Suggest a 24-month review cycle on every case; cases that fail review go to an "archival" tier (still readable, no fresh credentials).

---

## Appendix A — Asset inventory for v0.1

What's the actual deliverable list when "Phase 1 — Spine" lands and "Phase 2 — Academy v0.1 + Field Edition Cases 1–3" follows?

```text
Spine deliverables (Phase 1)
─────────────────────────────────
course/PEDAGOGY.md                                           (1 doc)
course/schema/scenario.yaml.linkml                           (1 schema)
pipelines/synthdata/main.nf + helpers                        (1 Nextflow workflow)
backend/missions/ (FastAPI router + evaluator)               (1 module)
backend/credentials/ (JWT issuer + Sigstore bundling)        (1 module)
deploy/learn/<academy|field|sentinel|wildfire>/values.yaml   (4 Helm overlays)
cases/ directory + CONTRIBUTING-cases.md                     (1 doc + structure)
governance/learn-addendum.md                                 (1 doc)
LICENSE-cases.md                                             (1 doc)
verify/ frontend (Streamlit page; OIDC verifier)             (1 page)

Academy v0.1 (Phase 2a)
─────────────────────────────────
4 modules from Stream 1 (Innate)
  - 01-sequencing-101
  - 02-linux-python-genomics
  - 03-qc-host-scrubbing
  - 04-taxonomic-id
Streamlit module-renderer UI
JupyterHub link-out
Cohort scheduler v0.1 (minimal)
Instructor dashboard v0.1 (minimal)

Field Edition v0.1 (Phase 2b)
─────────────────────────────────
3 cases
  - 01-the-first-patient
  - 02-the-strange-reader
  - 03-the-synonymous-mutation
Streamlit narrative wrapper
Save-state local file
"Next case" recommender (rule-based, not ML)

Total estimated effort
─────────────────────────────────
Phase 1 spine: 3–4 months focused, 6–9 months part-time
Phase 2a + 2b: 3 months focused, 4–6 months part-time
v0.1 in the wild: ~9–12 months from P0e ship date
```

---

## Appendix B — What's deliberately NOT in v0.1

To prevent scope creep:

- No SENTINEL or WILDFIRE in v0.1 (those are Phase 3 and Phase 4)
- No LTI 1.3 integration (Edu-tier feature; deferred)
- No co-signing infrastructure (Partner-tier feature; deferred)
- No multilingual support beyond English (deferred; affordances only)
- No mobile-native UI (Streamlit is web; mobile is a long-term consideration)
- No LLM-assisted case authoring tools (deferred; manual authoring only at first)
- No graded peer review system (peer review happens via GitHub PRs at first)
- No commercial credential overlays (APHL/CSELS co-signing comes when there's a partner)
- No social features in the Academy proper (no in-platform chat; out-of-platform community channels)
- No Wet-lab Reference Standard kit (Phase 4 or later; community signal-driven)

The principle: every face's v0.1 should be opinionated but minimal. Compound expansion comes from community contribution, not from speculative pre-building.

---

## Appendix C — Provenance

This document synthesizes:

- `docs/archived/jackpot_ais_legacy.md` (was `Jackpot_AIS copy.md`) — Parts 2–4 (the four-faces sketch, the case catalog, the sustainability model, the cooperative-game design)
- `docs/immune_platform.md` §§7-8 — current framing of Pillar IV (Academy) and Pillar V (Gaming), including the AIS-mapped curriculum and case progression tables
- `jackpot_immune_platform_plan copy.md` — §7 (Academy as pillar IV, the 16-module curriculum, partnership angles) and §8 (Gaming as pillar V)
- `jackpot_immune_collaboration_scaffolding_orig copy.md` — §7 (the Forrest framing meta-module reproduced in §2)
- `jackpot_learn_strategic_vision.md` — the companion vision doc (referenced throughout)

The 14-module privacy-preserving track in §3.2 stream 3 is reproduced verbatim from `Jackpot_AIS copy.md`'s "Module Lineup" section.

The 5-season SENTINEL arc in §5.2 and 6-season WILDFIRE arc in §6.2 are taken from `Jackpot_AIS copy.md` Part 3.

New material (not directly in the source documents but introduced in this design):

- The six-stream Academy organization with explicit module counts (Streams 1, 2, 4, 5, 6; Stream 3 is pre-existing)
- The seven role-types for SENTINEL cells (Laboratorian / Bioinformatician / Epidemiologist / Coordinator / Public-comms / Privacy officer / Sovereignty steward)
- Cases 09–12 of Field Edition (The Vanishing Variant, The Mole's Trail, The Tribal Sample, The Endemic Pressure)
- The four cross-face progression paths in §11
- The asset-inventory and not-in-v0.1 lists in Appendices A and B
- The contributor-model directory layout in §8.1
- The live-ops cadence table in §9.1
- The credential-types table in §10.1

Anywhere this document goes beyond the source material is open for revision when implementation starts.
