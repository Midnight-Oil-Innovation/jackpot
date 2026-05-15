Good question. Let me actually map the Biodesign Institute properly rather than working from memory — there are a lot of centers and the lineup shifts.Here's the full map. The Biodesign Institute currently has 17 active centers; about half of them have at least one researcher whose work intersects JACKPOT, and three of them are *deep* intersects you should know about. Most striking finding: there are already two existing Biodesign collaborations that are essentially JACKPOT-shaped projects.

Note up front: **Ni Trieu is in SCAI, not Biodesign** — but since the previous thread covered her and you said "include researchers already mentioned," I've put her at the end with that flag.

------

## At-a-glance map: Biodesign centers × JACKPOT aspects

| Center                                   | Director             | Genomics pipelines | Metadata / standards | Wastewater / One Health | AMR / typing | Phylogenetics / lineages | Security / privacy | Anomaly / outbreak | Education / training |
| ---------------------------------------- | -------------------- | ------------------ | -------------------- | ----------------------- | ------------ | ------------------------ | ------------------ | ------------------ | -------------------- |
| **Biocomputing, Security and Society**   | Forrest              | —                  | —                    | ✓ (via Lee)             | —            | —                        | ★★★                | ★★                 | —                    |
| **Environmental Health Engineering**     | Halden               | ✓                  | ★★★                  | ★★★                     | —            | ★★                       | —                  | ★                  | —                    |
| **Fundamental and Applied Microbiomics** | Garcia-Pichel        | ★★★                | ★★                   | ★★★                     | —            | ★★                       | —                  | ★★                 | —                    |
| **Personalized Diagnostics** (Piper)     | LaBaer               | ✓                  | ✓                    | —                       | —            | —                        | —                  | —                  | —                    |
| **Mechanisms of Evolution**              | Lynch                | ✓                  | —                    | —                       | ✓            | ★★                       | —                  | ✓                  | —                    |
| **Health Through Microbiomes**           | Krajmalnik-Brown     | ✓                  | —                    | ✓                       | ★ (gut AMR)  | —                        | —                  | —                  | —                    |
| **Bioelectronics and Biosensors**        | Hihath               | —                  | —                    | ✓ (upstream)            | —            | —                        | —                  | —                  | —                    |
| **Pathfinder Center**                    | Hartwell (Nobel '01) | —                  | —                    | —                       | —            | —                        | —                  | —                  | ★★                   |
| **Swette Environmental Biotechnology**   | Rittmann             | —                  | —                    | ✓ (process)             | —            | —                        | —                  | —                  | —                    |

`★★★` = already running a JACKPOT-shaped project; `★★` = direct overlap; `★` = adjacent. Other Biodesign centers (Applied Structural Discovery, Bioenergetics, Biomaterials, Molecular Design, Neurodegenerative, Single Molecule Biophysics, SM3) don't materially intersect JACKPOT.

------

## Existing Biodesign collaborations that are already JACKPOT-shaped

This is the headline. You're not pitching into a vacuum on multiple axes:

1. **Driver, Ahsan, Piske, Lee, Forrest, Halden, Trieu** — *"Encrypted data-sharing for preserving privacy in wastewater-based epidemiology"*, *Sci Total Environ*, Aug 2024. NSF CICI grant 2021–2024. **JACKPOT's privacy/federation pillar in published form.** Already covered in prior thread.
2. **Halden + Scotch + Varsani** — $1.5M NIH grant to build "an early warning system for flu outbreaks" with a multi-dimensional viral databank that cross-references human/plant/animal viruses. From 2019. **JACKPOT's metadata + One Health pillar in execution form.**
3. **Lim** (with the Arizona COVID-19 Genomics Union) — sequenced 100,000+ COVID-19 genomes in collaboration with three Phoenix hospitals, ADHS, and other Arizona institutions. **JACKPOT's exact operating model — except as a one-pathogen, one-pandemic, one-state effort.**
4. **Lee + Lynch** (Salmonella mutation rate work, 2023) — JACKPOT-relevant because foodborne pathogen evolution is exactly what AMR/typing pipelines feed.
5. **Scotch's NSF PIPP Phase II "ESCAPE" Center** (Berry PI, 2024–2031) — *Environmental Surveillance for Assessing Pathogen Emergence*. This is a multi-million-dollar, multi-year center focused on environmental pathogen surveillance. **JACKPOT's One Health surveillance + anomaly-detection pillar at federally-funded scale.**

If you stop reading here, the takeaway is: there are at least three faculty (Scotch, Varsani, and the already-known Halden+Forrest+Lee triad) who are running funded programs that JACKPOT is the natural infrastructure for.

------

## Tier 1: Strongest fits

### Matthew Scotch — Environmental Health Engineering (Assistant Director); Biomedical Informatics, College of Health Solutions

**This is the single biggest find I didn't have in the prior thread.** Scotch is essentially building JACKPOT-shaped infrastructure already, just one virus family at a time and without the metadata schema that JACKPOT enforces.

What he actually does:

- Genomic epidemiology and bioinformatics of RNA viruses, primary focus influenza A
- Phylodynamics — Bayesian inference of when/where variants spread
- **Built ZooPhy** (2019): an open-access bioinformatics pipeline for virus phylogeography and surveillance. JACKPOT is the next-generation platform for what ZooPhy was prototyping.
- **NIH/NIAID R01AI164481**: "advancing genomic epidemiology by enrichment of virus sequence metadata." This grant title is *literally one sentence away from JACKPOT's value proposition*.
- NSF PIPP Phase II ESCAPE Center (2024–2031): environmental surveillance for pathogen emergence
- Visiting Professorial Fellow at the Kirby Institute, UNSW Sydney — international ties
- 22,000-genome SARS-CoV-2 phylodynamics study with Mayo Clinic Laboratories

JACKPOT aspects he'd care about: metadata enrichment, schema-first design, NCBI/GISAID submission integration, phylodynamic pipeline outputs, wastewater virus genomics, federated data, the audit trail for surveillance data provenance.

What might *not* land: the bacterial isolate side (bactopia, Grandeur, mycosnp) — he's RNA viruses, not bacteria. But that's complementary, not conflicting.

### Arvind Varsani — Fundamental and Applied Microbiomics; Mechanisms of Evolution; School of Life Sciences

The standards body member. Varsani is on the **Executive Committee of the International Committee on Taxonomy of Viruses (ICTV)** — the volunteer organization that defines the official nomenclature for every virus species on Earth. JACKPOT's controlled vocabularies for organisms ultimately trace back to standards he's helped author.

What he actually does:

- Molecular virology across ecosystems — plants, animals, tropics to Antarctica
- Wastewater virus discovery (canine parvovirus, picornavirus diversity, polio surveillance)
- Built **Cenote-Taker**, a bioinformatics pipeline for automated annotation of circular DNA virus genomes (this is exactly the kind of tool that would ship as a JACKPOT pipeline parser)
- Long-running collaborator with Halden and Scotch on the wastewater virome
- Penguin virology, ICTV virus taxonomy, viral evolution

JACKPOT aspects he'd care about: schema enums for organism taxonomy (he literally writes this standard), pipeline integration for novel virus annotation, One Health framing (his entire career embodies this), pathogen reference databases, GenBank/RefSeq integration.

What might not land: he's pure discovery virology, less interested in the public health workflow / RBAC / audit pieces. But the One Health framing is a strong sell.

### Efrem Lim — Fundamental and Applied Microbiomics; PI of the Center for Viral Genomics; School of Life Sciences

The "we already do JACKPOT but as a labor-intensive Excel spreadsheet" researcher. Lim ran the Arizona COVID-19 Genomics Union through the entire pandemic, sequencing thousands of genomes per week, integrating with three Phoenix-area hospitals (Valleywise, Phoenix Children's, Dignity Health) and ADHS, doing wastewater + clinical + community surveillance simultaneously.

What he actually does:

- Statewide SARS-CoV-2 genomic surveillance (40,000+ genomes through ACGU)
- Identified the first B.1.243.1 (E484K) variant of interest in Arizona
- Wastewater + clinical co-surveillance for variant tracking (the Fontenele et al. 2021 paper)
- Predicted Omicron-class antigenic shift before Omicron emerged
- Human virome research broadly

JACKPOT aspects he'd care about: literally everything operational. ACGU is JACKPOT-without-the-platform. The argument to him is "you've been building this manually for four years; here's what it looks like as a real platform." High-value conversation because he has the *use case*, not just academic interest.

What might not land: he's busy. He's been running this at full burn since 2020. The ask has to be "use this," not "help me build it."

------

## Tier 2: Natural collaborators

### Joshua LaBaer — Personalized Diagnostics (Director); also Executive Director of the entire Biodesign Institute

Important less for technical mapping than for institutional positioning. LaBaer ran ASU's COVID-19 saliva testing program (a million+ tests, FDA emergency authorization, $6M state contract for 20-minute rapid testing). He's the Biodesign Institute's executive director.

What he does technically: predictive biomarker discovery, NAPPA protein arrays, machine learning for human disease classification. Less direct technical overlap with JACKPOT.

What he matters for: he's the person who can get JACKPOT institutional weight if Biodesign decides to back it. His COVID program was *exactly* the kind of public-health-facing operation JACKPOT is designed to scale. If Biodesign wanted a flagship platform for the next pandemic, JACKPOT could be it, and LaBaer is the gatekeeper.

### Reed Cartwright — Mechanisms of Evolution; School of Life Sciences

Phylogenetics software developer. Builds tools for de novo mutation detection from related individuals/cells using next-gen sequencing, plus sequence simulation, alignment, and population genetics analysis software.

JACKPOT aspects: phylogenetic pipeline outputs, mutation rate estimation, software engineering for genomics tools (he ships and maintains real software, which is rarer than you'd think among academics). Collaborates with Melissa Wilson on population genetics.

What would land: the pipeline parser architecture, phylogenetic output formats, sequence simulation as a tool for testing JACKPOT pipelines. Cartwright is a software builder, not a workflow architect — natural collaborator on parser development.

### Michael Lynch — Mechanisms of Evolution (Director); NAS member

The big-picture evolutionary biologist. Population genomics, mutation/drift/recombination at gene/genome/cell/phenotype scales. Less direct JACKPOT fit, more "would care about JACKPOT producing data he could analyze." Lynch's lab outputs are tools and theory; he'd see JACKPOT as upstream infrastructure.

What would land: the immutable append-only `pipeline_results` design, standardized evolutionary metrics, AMR-emergence-as-evolution framings (the immune phases you've been planning). His joint work with Heewook Lee on Salmonella mutation rates is the most direct touchpoint.

### Rosa Krajmalnik-Brown — Health Through Microbiomes (Director)

Gut microbiome and bioremediation. The intersection with JACKPOT is via two things: (1) gut microbiome as an AMR reservoir — hAMRonization-aligned outputs from gut microbiome sequencing fit JACKPOT's `amr_results` table cleanly; (2) wastewater microbiology and bioremediation — she's bridge-territory between Halden (chemicals/wastewater engineering) and Lim/Varsani (virology).

What would land: the metagenomic pipelines (nf-core/mag, taxprofiler), AMR detection, environmental sample handling. Less interested in clinical surveillance workflow.

------

## Tier 3: Peripheral or adjacent

### Ferran Garcia-Pichel — Fundamental and Applied Microbiomics (Director)

Cyanobacteria, microbial mat ecosystems, biological soil crusts. Direct JACKPOT fit is low — he's environmental microbiology of natural systems, not pathogen surveillance — but he's the center director that houses Lim and Varsani, so worth keeping in mind for institutional support.

### Joshua Hihath — Bioelectronics and Biosensors (Director)

Sensor systems for biomarker detection. JACKPOT lives downstream of a sequencer, but Hihath builds the upstream end — point-of-care detection devices, breath/molecular sensors. The intersection is "if Hihath's sensors output enrichable metadata, does JACKPOT ingest it?" Long chain, but worth a one-line note in any pitch.

### Lee Hartwell — Pathfinder Center (Director, 2001 Nobel laureate)

Education and middle-school teacher development. The intersection is the JACKPOT `course/` pillar in your monorepo plan. If you ever want JACKPOT to be a *teaching platform* for public health workforce training, Hartwell is the person at Biodesign who thinks about that full-time. Not a technical collaborator; a curriculum/pedagogy partner.

### Bruce Rittmann — Swette Center for Environmental Biotechnology

Wastewater treatment microbial process engineering. Adjacent to Halden but oriented toward the engineering of wastewater treatment, not the surveillance of pathogens in wastewater. Probably not a primary collaborator, but useful to know exists.

------

## Outside Biodesign but in our threads

### Ni Trieu — SCAI (not Biodesign), Department of Computer Science and Engineering

Already covered in detail in the prior thread. Applied cryptography, private set intersection, secure multi-party computation. Co-author on the wastewater encryption paper with Forrest/Lee/Halden/Driver. Even though she's not Biodesign-affiliated, that paper *is* a Biodesign collaboration in everything but her line of the affiliation block. The privacy/federation pillar of JACKPOT runs straight through her work.

------

## What this means for JACKPOT

The honest summary: there are roughly **6 Biodesign researchers** (Forrest, Lee, Halden, Scotch, Varsani, Lim) whose current funded research is a direct intersect with JACKPOT, plus **2 institutional gatekeepers** (LaBaer, Garcia-Pichel) who could open or close institutional doors, plus **3 natural collaborators** (Cartwright, Lynch, Krajmalnik-Brown) whose work touches JACKPOT outputs but isn't the same project.

The Scotch finding is the new headline. He's running an NIH R01 explicitly on virus metadata enrichment for genomic epidemiology — that's the elevator pitch for JACKPOT's tier-aware schema, just rendered as a research grant. Plus he's part of an $11M+ NSF PIPP Phase II center for environmental pathogen surveillance running until 2031. If you want one new conversation on top of the Forrest/Trieu/Lee/Halden thread you already started, **Matthew Scotch** is the highest-yield first phone call.

Want me to dig deeper into any specific researcher, lay out specific JACKPOT pillars they'd contribute to in a more concrete plan, or pull together the funding landscape across these labs (active grants, expiring soon, etc.)?



Good call — there's a lot of ASU outside Biodesign that touches JACKPOT. Let me do this systematically across the relevant schools.There's substantial JACKPOT-relevant work outside Biodesign, especially when you pull on the SCAI cryptography thread Trieu is part of. Here's the systematic map.

------

## At-a-glance map: ASU units (outside Biodesign) × JACKPOT aspects

| Unit                                               | Key faculty                          | Crypto / privacy | Bioinformatics / pop gen | AMR / typing | Vector / One Health | Phylo / outbreak modeling | Data governance / law | Education |
| -------------------------------------------------- | ------------------------------------ | ---------------- | ------------------------ | ------------ | ------------------- | ------------------------- | --------------------- | --------- |
| **SCAI — Cryptography & Security cluster**         | Trieu, Weng, Kinsy, Kim, Ahn, Ozmen  | ★★★              | —                        | —            | —                   | —                         | ★                     | —         |
| **SOLS — Population & evolutionary genomics**      | Jensen, Pfeifer, M. Wilson           | —                | ★★★                      | ★            | —                   | ★★                        | —                     | ★         |
| **Center for Evolution and Medicine (SOLS)**       | Huijben, Paaijmans, Aktipis          | —                | ★★                       | ★★★          | ★★★                 | ★★                        | —                     | —         |
| **CHS — Biomedical Informatics**                   | Scotch (joint), Grando, Murcko, Dinu | ★★★ (Grando)     | ★★                       | —            | —                   | ★★ (Scotch)               | ★★★                   | ★         |
| **CHS — IDPPR Translational Team**                 | Sklar, LoVecchio (clinical)          | —                | —                        | —            | ✓                   | ✓                         | —                     | —         |
| **MCMSC (Simon A. Levin Center)**                  | Crook (dir), Castillo-Chavez, Milner | —                | —                        | ★            | ★★                  | ★★★                       | —                     | ★★        |
| **Sandra Day O'Connor College of Law**             | Hodge (CPHLP director)               | ★                | —                        | —            | —                   | —                         | ★★★                   | —         |
| **School for the Future of Innovation in Society** | Farooque (governance)                | —                | —                        | —            | —                   | —                         | ★★                    | —         |

`★★★` = direct overlap with currently funded JACKPOT-shaped work; `★★` = adjacent, natural collaborator; `★` = relevant on one specific axis.

------

## Existing cross-unit collaborations that already look like JACKPOT pieces

This is the same headline finding as last time, just expanded:

1. **Driver, Ahsan, Piske, Lee, Forrest, Halden, Trieu** — encrypted wastewater epidemiology paper. Bridges Biodesign EHE + Biodesign BSS + **SCAI cryptography**. NSF CICI 2021–2024.
2. **Schrom, Kinzig, Forrest, Graham, Levin, Bergstrom, Castillo-Chavez, ..., Huijben, Maley, Moses, ...** — *Mathematical Biosciences* August 2023, "Resilience of evolved immune systems to inform the design of resilient computer systems." Bridges Biodesign BSS + **MCMSC + Center for Evolution and Medicine (SOLS)**. The bio-immunity-as-cybersecurity framing is exactly the immune phases you've been planning.
3. **Paaijmans + Huijben + collaborators** — published on *"Mosquitoes as a feasible sentinel group for anti-malarial resistance surveillance by Next Generation Sequencing of Plasmodium falciparum."* Vector → AMR sequencing → public health surveillance pipeline. **JACKPOT's One Health AMR pillar in field-deployed form.** CDC-funded.
4. **Grando + Lee (Preston, ASU) + Murcko + collaborators** — *NIH NIDA SHARES grant 2023–2028,* building open-source FHIR Consent Labeling & Redaction Service (`asushares/cds` on GitHub) for granular patient data sharing. **JACKPOT's RBAC + audit + governance pillar in HIPAA-compliant form.**

------

## Tier 1: Strongest fits

### Cryptography & secure computation cluster — SCAI (the Trieu universe)

You already know Trieu. The cluster around her is bigger than I covered in the prior thread:

- **Ni Trieu** (already covered) — Private set intersection, secure two-party / multi-party computation. Co-author on the wastewater encryption paper. The federation/privacy pillar runs straight through her work.
- **Chenkai Weng** — Assistant Professor, applied cryptography. Zero-knowledge proofs and privacy-enhancing techniques. Different cryptographic primitives than Trieu (ZK vs PSI), so they're complementary rather than overlapping.
- **Michel A. Kinsy** — Associate Professor, runs the **Adaptive & Secure Computing Systems (ASCS) Laboratory**, member of the **Secure, Trusted, and Assured Microelectronics (STAM) Center**. Works on **fully homomorphic encryption** for privacy-preserving ML, hardware acceleration of HE operations, post-quantum cryptography. His group has 2025 papers on FHE-friendly ML activation functions and a benchmarking study of open-source HE libraries (SECRYPT 2025). For JACKPOT's federated computation use case — letting labs ask "do you have a sample with this signature?" without disclosing what the signature is — this is the heavy-machinery side. PSI for set queries, FHE for arithmetic on encrypted data.
- **Hokeun Kim** — Assistant Professor, secure IoT, cloud security, safety-critical cyber-physical systems. Adjacent to JACKPOT's deployment scenarios (especially the laptop and federation-member tiers).
- **Gail-Joon Ahn** — Professor, **Director of the Center for Cybersecurity and Trusted Foundations (CTF)**. Information security and privacy management. The institutional gatekeeper if JACKPOT wants formal cybersecurity review or threat-modeling rigor on its RBAC.
- **Habiba Farrukh / Z. Berkay Celik–trained Ozmen** — Assistant Professor, formal methods + applied cryptography for secure cyber-physical systems.

JACKPOT touchpoints: federation across institutions, encrypted "do you have this sample?" queries (PSI), homomorphic computation on encrypted metadata, formal verification of the audit log, HE-friendly cluster signature comparison.

### Adela Grando — College of Health Solutions, Biomedical Informatics

The single biggest non-Biodesign find. **Grando is to clinical data governance what JACKPOT is to genomic surveillance — and she's already shipping the open-source infrastructure.**

What she actually does:

- Professor in Biomedical Informatics, FAMIA and FACMI fellow
- **PI of NIH NIDA SHARES (Substance use HeAlth REcord Sharing)** — funded 2023–2028, building granular electronic consent technology
- **Open-source SHARES FHIR Consent Labeling & Redaction Service** at `github.com/asushares/cds` — implements CDS Hooks request/response protocol, queries FHIR backends for Consent documents, returns FHIR ActCodes describing content sensitivity. This is exactly the architecture pattern JACKPOT's data governance layer would benefit from.
- HL7 Information Sensitivity Policy Value Set work — surveying physicians on the 45 sensitive-data categories
- Patient-controlled data sharing for behavioral health, substance use, mental health
- AZ Blockchain Applied Research Center (2020–2023)
- ML for Type 1 diabetes prediction with Mayo Clinic Arizona

JACKPOT touchpoints: granular access control (the six-role RBAC could be modeled as FHIR Consent ActCodes), audit trail design, federated consent management, data sensitivity labeling. Her HL7 work directly maps to JACKPOT's metadata sensitivity tiers — there's almost certainly a layered consent model that drops into the existing schema.

### Jeffrey Jensen — School of Life Sciences, AAAS Fellow 2025

**The serious population genetics theorist for viral evolution.** NIH-MIRA-funded principal investigator, theoretical and statistical methods for inferring population history and natural selection from sequencing data, applications from viruses to nonhuman primates.

His SARS-CoV-2 paper is titled *"Mutational meltdown: Can we push SARS CoV-2 off an evolutionary cliff?"* — which is the kind of high-leverage analysis JACKPOT's pipeline outputs would feed. He's the analyst layer above the lineage-classification layer.

JACKPOT touchpoints: the immutable append-only `pipeline_results` design is built for the kind of longitudinal evolutionary inference his lab does. The methods his lab develops are exactly what would be applied to JACKPOT outputs by surveillance epidemiologists.

### Silvie Huijben & Krijn Paaijmans — Center for Evolution and Medicine, School of Life Sciences

**The malaria/AMR/vector pair.** They run adjacent labs at CEM, collaborate constantly, and their joint research is the canonical JACKPOT One Health AMR use case.

**Huijben:**

- Antimalarial resistance management, insecticide resistance evolution
- Evolutionary medicine framing of AMR
- Field + lab + mathematical modeling

**Paaijmans:**

- Disease ecology of malaria and Zika
- Vector control, mosquito surveillance
- Head of the Entomology Platform at the Manhiça Health Research Centre in Mozambique
- **CDC-funded for vector surveillance**
- **Published on "Mosquitoes as a feasible sentinel group for anti-malarial resistance surveillance by Next Generation Sequencing of Plasmodium falciparum"**

That last paper is the use case JACKPOT enables: mosquitoes-as-samples → NGS → AMR detection → public health response. It's a vector-source organism (sector="vector"), a Plasmodium falciparum genome (organism="Plasmodium falciparum"), an AMR-focused pipeline output (`amr_results`), tied to a Mozambique field site (collection_location). JACKPOT's schema is designed for exactly this submission.

JACKPOT touchpoints: vector sector, AMR results table, field-deployed sample workflow, international (Mozambique → ASU → CDC) data flow. Paaijmans's CDC funding plus international fieldwork is the federated-deployment scenario in operational form.

### James G. Hodge Jr. — Sandra Day O'Connor College of Law

**The legal infrastructure expert for public health data.** Director of the **Center for Public Health Law and Policy** at ASU Law. Director of the **Network for Public Health Law - Western Region Office.** Authored the **Model State Public Health Privacy Act (MSPHPA)** for the CDC.

His Washington State Department of Health study assessed the legal framework for public health data sharing — exactly the question JACKPOT raises every time it federates a sample query across jurisdictions. He's also collaborated with the **Johns Hopkins Center for Health Security**.

JACKPOT touchpoints: public health surveillance legal authority, HIPAA / state law navigation for federated genomics, the Model State Public Health Privacy Act as a reference for JACKPOT's audit trail and data sensitivity defaults, IRB and data-use-agreement templates for JACKPOT federation deployments. Not a technical collaborator; the legal scaffolding partner. Critical if JACKPOT ever wants to pitch as the platform for the next pandemic.

------

## Tier 2: Natural collaborators

### Susanne Pfeifer — School of Life Sciences

Primate population genomics with bacteriophage genomics on the side. **Phage Hunters CURE** — undergraduate course-based research experience producing peer-reviewed publications on bacteriophage genomic diversity. The phage angle is directly relevant for JACKPOT's AMR side, since phages are anti-microbial agents and phage therapy is increasingly part of clinical AMR response. Her CURE pipeline is a model for JACKPOT's own `course/` pillar.

### Melissa Wilson — School of Life Sciences

Sex chromosome evolution, computational biology, sex-aware genomic analysis. **Listed as co-author on the Fontenele et al. 2021 SARS-CoV-2 wastewater paper** — so she's already in the JACKPOT-adjacent collaboration network. Her HPC and bioinformatics infrastructure expertise is a natural complement to JACKPOT's pipeline architecture.

### Carlos Castillo-Chavez — MCMSC, Mathematical Biology

Regents Professor, founding director of MCMSC. Mathematical epidemiology, SIR/SIRS variants, vector-borne disease, dengue/Zika/Ebola/TB modeling. Less hands-on now (Sharon Crook is the current director) but the senior figure for ASU mathematical epidemiology. The Schrom et al. 2023 paper places him in direct collaboration with Forrest and Huijben on bio-immunity / cybersecurity framings — same intellectual neighborhood as your immune-phases plan.

JACKPOT touchpoints: outbreak forecasting from JACKPOT outputs, R0 estimation pipelines, anomaly-detection layer for cluster emergence.

### Sharon Crook — School of Mathematical and Statistical Sciences, MCMSC Director

Current MCMSC director. Computational neuroscience by background but in the chair that runs the cross-disciplinary modeling center. Institutional gatekeeper for any JACKPOT mathematical-modeling collaboration.

### Anita Murcko & Valentin Dinu — College of Health Solutions, Biomedical Informatics

Murcko is the **CHIR (Center for Health Information and Research) Senior Faculty Advisor** and Grando's frequent co-author on the SHARES/My Data Choices papers. Dinu is Associate Professor in Biomedical Informatics. The clinical-informatics-adjacent collaborators around Grando.

### David Sklar & Frank LoVecchio — College of Health Solutions, IDPPR Translational Team

Clinical / emergency-medicine connectors. Sklar is professor of health care delivery and senior advisor in health policy. LoVecchio is research director at **Valleywise Health** (the public hospital in Phoenix that's already an Efrem Lim ACGU collaborator). Not technical contributors but the bridge between JACKPOT and clinical operations.

### Mahmud Farooque — School for the Future of Innovation in Society

Associate Director of **Consortium for Science, Policy & Outcomes**, AAAS Fellow 2025. Participatory technology assessment — the methodology for engaging stakeholders in social appraisal of emerging technology. If JACKPOT ever wants to do real public engagement around what surveillance data can and cannot be used for, Farooque is the methodologist.

------

## Tier 3: Adjacent or institutional

- **Kenro Kusumi** — Senior Vice Provost, Dean of The College of Liberal Arts and Sciences, AAAS Fellow 2025. Genome biologist, sequenced threatened tortoise genomes for conservation. Institutional gravity at college-dean level rather than direct technical fit.
- **ASU Sol Center / HPC group** — JACKPOT spec already mentions Sol HPC integration. The systems administrators here are the people who'd actually run JACKPOT at scale on ASU compute.
- **Center for Cybersecurity and Trusted Foundations (CTF)** — Ahn's center, listed under SCAI cluster above.
- **ASU Center for Evolution and Medicine** — homes Huijben, Paaijmans, Aktipis, others. Worth treating as an institutional partner unit; it's a cleaner fit for JACKPOT than parts of Biodesign that don't intersect.

------

## What this means relative to Biodesign

The Biodesign list was about **sample producers and pathogen biologists** — the people generating data that flows into JACKPOT.

This off-Biodesign list is about **data infrastructure consumers and theorists** — the people who'd analyze, secure, govern, model, or legally underwrite JACKPOT's outputs:

- SCAI cryptography cluster: secures the federation layer
- CHS Biomedical Informatics (Grando): provides the consent and access-control architecture
- SOLS population genetics (Jensen, Pfeifer, Wilson): consumes the pipeline outputs for inference
- CEM (Huijben, Paaijmans): the One Health AMR use case in field deployment
- MCMSC (Crook, Castillo-Chavez): mathematical surveillance and outbreak forecasting on top of JACKPOT data
- ASU Law (Hodge): the legal infrastructure for cross-jurisdictional public health data sharing

If you wanted to write a JACKPOT-as-ASU-flagship-platform proposal, this is the cross-college coalition. The two-call sequence is:

1. **Matthew Scotch** at CHS/Biodesign EHE — the technical coalition lead, since he already has the genomic-epi-with-metadata R01 and the NSF PIPP center.
2. **Adela Grando** at CHS Biomedical Informatics — the data-governance coalition lead, since she has the open-source FHIR consent infrastructure and the NIDA-funded program through 2028.

After that, Hodge (legal), Kinsy (HE/cryptography for federation beyond Trieu's PSI), Paaijmans (the CDC-funded vector AMR field site), and Jensen (the population genomics analytical layer) round out the coalition.

Want me to dig deeper into any of these (particularly the active grants — there's likely real money on the table for someone proposing infrastructure that connects Scotch's R01 + Grando's NIDA + Paaijmans's CDC funding), or pull together specific JACKPOT pillars and assign which subsets of these collaborators each pillar would attract?
