# JACKPOT × CDC Data Modernization × STLT Public Health
## Overview, Architectural Alignment, and Adoption Plan

**Status:** Working session synthesis · 2026-04-28
**Scope:** What CDC's Data Modernization Initiative (DMI) and North Star Architecture were trying to achieve, why they're in limbo, and how JACKPOT can serve State, Tribal, Local, and Territorial (STLT) Public Health Agencies — with extra weight on Tribal sovereignty as the most architecturally consequential of the four.

---

## 0. Executive summary

Three things to internalize before reading the rest:

1. **CDC's North Star Architecture is in limbo, not dead.** Funding for the broader Data Modernization Initiative was paused in October 2025 (Wave 2 Implementation Center applications halted), but the underlying technical vision — cloud-native, FHIR-aligned, TEFCA-compatible, "blueprint not platform" with local data control — was sound and is broadly endorsed by the STLT public health community. The pause is political and budgetary, not architectural. Whatever rebuild eventually happens will likely follow the same shape, possibly led by a different agency or coalition.

2. **JACKPOT is structurally well-positioned to be a North-Star-aligned platform.** Pathogen-genomics is a small slice of public-health-data overall, but the architectural choices already made — cloud-native, multi-tenant-capable, schema-driven, AGPL-3.0 with a clear governance story, six install scenarios — match what STLT agencies were promised by DMI. Specifically: JACKPOT's Scenarios A (laptop), C (multi-lab agency), and E (federation) directly map to the STLT-facing tiers North Star described.

3. **Tribal sovereignty is the highest-leverage and lowest-cost differentiator.** None of the peer platforms in `jackpot_pathoplexus_loculus_overview.md` (Loculus, Pathogenwatch, EnteroBase, NCBI PD, BV-BRC, Solu, RT-MetA, GISAID) are designed for Indigenous Data Sovereignty (IDSov) compliance. Adopting the **CARE Principles** (Collective benefit, Authority to control, Responsibility, Ethics) explicitly, and offering a Tribal-deployment scenario with air-gappable architecture and Tribally-controlled governance, would put JACKPOT in a category of one. The work is mostly governance and config, not net-new engineering — except for one architectural piece: **deletion-on-request that actually removes the data, not just hides it**, which has implications for the existing immutable-pipeline-results model.

The headline recommendations that fall out:

- **Adopt CARE Principles formally** in `governance/care-principles-and-tribal-data-sovereignty.md`. Pair with FAIR. Build a Tribal-deployment guide (Scenario T = sovereignty-aware variant of A or E).
- **Map JACKPOT install scenarios to STLT tier model.** Scenario C = state/territorial health departments, Scenario A or B = local/county labs, Scenario T = Tribal authorities. Each gets a tailored deploy guide.
- **Build a TEFCA / FHIR ingest path** as a future option. Most STLT data exchange is moving toward FHIR via QHINs. Pathogen genomics isn't the leading edge of this, but JACKPOT being able to consume FHIR `MolecularSequence` resources and emit FHIR `Specimen` references is table-stakes for North-Star-aligned operation.
- **Adopt the "Front Door" pattern** but in JACKPOT's narrower scope: a single ingest endpoint that auto-routes (signed URL, URI, FHIR, SRA, CSV) is already there. Document it as the "single-entry-point for genomic data into a public health agency" — that framing matters for grant narratives.
- **Implement true delete-on-request for sovereignty compliance.** Schema needs a `deletion_status` column and the immutable `pipeline_results` rows need to gain a soft-delete-then-vacuum lifecycle that preserves audit trail without retaining sensitive data. This is the one architectural change that *adds* engineering work.
- **Federation tier 0 = Tribal Epidemiology Center (TEC) liaison pattern.** TECs are HIPAA-recognized public health authorities serving 574 Tribes and 9.7 million AI/AN people. A JACKPOT instance at a TEC + JACKPOT instances at member Tribes = canonical Scenario E federation, but with Tribally-controlled aggregation rules.
- **Don't compete with NBS, eCR, or AIMS.** These are case-reporting, electronic case-reporting, and lab-data-routing systems that operate at a different layer. JACKPOT is downstream of them — sample-and-sequence-centric, not case-centric. Position JACKPOT as the genomics layer that *integrates with* NBS / eCR / AIMS, not as a replacement.

The rest of this document develops each of these.

---

## 1. CDC Data Modernization Initiative — what it was, what it became, where it stands

### 1.1 The origin story (2018–2020)

DMI was launched in 2020 by CDC, with antecedents going back to 2018. The vision was "to move from siloed and brittle public health data systems to connected, resilient, adaptable and sustainable 'response-ready' systems" capable of delivering real-time, high-quality information on infectious and non-infectious threats. The pandemic exposed exactly the problems DMI was designed to fix:

- Multiple point-to-point submissions from providers
- Older technology and incompatible formats across jurisdictions
- Fax machines still in routine use for case reporting in 2020
- Public health systems that "couldn't tap into" healthcare interoperability networks at scale during COVID-19

CDC's initial congressional allocation was approximately $1 billion across emergency funding (CARES Act $500M, FY21 $50M, ARP Act $500M). The Data: Elemental to Health Campaign estimated true modernization would require at least $7.84 billion over five years at the STLT level alone, with additional CDC-level needs on top.

### 1.2 The five DMI priority areas

DMI's 2022 strategic roadmap settled on five priorities:

| # | Priority | What it means in practice |
|---|---|---|
| 1 | **Building the right foundation** | Cloud-based infrastructure, common data platforms (EDAV, eventually One CDC Data Platform), shared building blocks rather than per-program data silos. |
| 2 | **Accelerating data into action** | Real-time / near-real-time exchange via FHIR, eCR, ELR, syndromic surveillance, vital records. |
| 3 | **Developing a state-of-the-art workforce** | Funding and training for data modernization leads at every jurisdiction; informatics and bioinformatics fellowships. |
| 4 | **Supporting and extending partnerships** | STLT relationships, healthcare/HIE/QHIN integrations, ASTHO/NACCHO/PHAB collaboration. |
| 5 | **Managing change and governance** | The hard part — getting the federal-state-tribal-local governance model right. |

### 1.3 The North Star Architecture — the blueprint

North Star Architecture was DMI's technical centerpiece, formally introduced at HIMSS 2022 by ONC's Micky Tripathi. The framing was deliberate:

> "For these reasons, the DMI is designing a cloud-based data ecosystem called the North Star Architecture. The goal is to connect federal, state, and local health department information systems and make them interoperable. The CDC will govern the cloud environment to protect the state and local governments' control of data, while the ONC's Trusted Exchange Framework and Common Agreement will help promote information exchange."

Key architectural commitments:

#### 1.3a "Blueprint, not platform"

CDC was explicit that North Star is a *common framework* — not a single piece of software CDC builds and runs. "It will be made of flexible, interoperable, and secure digital tools that can be used by CDC and public health partners at state, tribal, local, and territorial (STLT) levels. These digital tools will provide different levels of support, from guidance to complete solutions, to meet STLTs and CDC programs where they are today." This was a hard-won lesson from prior CDC efforts (NEDSS Base System, BioSense, etc.) that tried to be one-size-fits-all and ended up neither.

#### 1.3b Tiered support levels

> "Meets people where they are: It offers different options and levels of support, depending on the needs and abilities of our partners."

This is the model for everything that follows. STLT partners range from a single epidemiologist in a rural county to the New York State Department of Health with a multi-million-dollar IT budget. North Star explicitly committed to *not* forcing them all into one tier.

#### 1.3c The "CDC Front Door"

A single-entry-point for data coming into CDC, replacing the legacy point-to-point submission patchwork. The Front Door concept was about reducing friction for STLT submitters — submit once, route everywhere internal to CDC.

#### 1.3d Local data control

A core commitment that the cloud platform would not absorb data from STLT submitters into a federal-controlled lake. "The intent, he explained, is to provide the benefits of a common cloud platform while preserving state and local control of data and data use."

#### 1.3e Interoperability via TEFCA + FHIR

The technical interoperability stack: TEFCA (Trusted Exchange Framework and Common Agreement) for the policy + agreements layer, FHIR for the data structure layer. "TEFCA guides how different, individual systems connect to share information consistently – without having to come up with their own approaches and rules for doing so. FHIR offers specifications that give data structure and make information available to support the needs of public health officials and their many partners. And the North Star Architecture shows where everyone is going together."

### 1.4 What got built before things slowed down

Real progress happened — DMI was not vapor:

- **EDAV (Enterprise Data, Analytics, and Visualization)**: a cloud-based platform that "saved more than $6.5M dollars in infrastructure investments that would have been made to build smaller versions of data silos" within its first year.
- **Electronic Case Reporting (eCR)**: "More than 170 conditions can be reported using eCR, up from only 20 at the beginning of 2020."
- **NBS modernization**: ongoing, multi-phase rebuild of NEDSS Base System, the integrated information system used by ~100 STLT jurisdictions. "CDC is redesigning the National Electronic Disease Surveillance System Base System (NBS) to meet current and future needs and strengthen state, local, territorial, and tribal (STLT) surveillance infrastructure."
- **TEFCA public health Standard Operating Procedure**: published 2024, defining how public health agencies (PHAs) participate as authorized queriers and recipients in TEFCA exchanges.
- **One CDC Data Platform (1CDP)** + **RREDI (Response Ready Enterprise Data Integration)**: the operational realization of EDAV at full agency scale.
- **Implementation Center Program (IC Program)**: launched 2024 with $255M from PHIG (Public Health Infrastructure Grant), with three implementation centers (CRISP Shared Services, Guidehouse, Mathematica) supporting 34 PHAs in Wave 1, with Wave 2 planned for 2025.

### 1.5 Where things stand (October 2025 onward)

The Implementation Center Program was the canary. "The National Partners received formal written guidance from CDC to pause all IC Program-related work, which includes all ongoing Wave 1 activities and accepting Wave 2 applications. As a result, the deadline of October 17, 2025, for Wave 2 applications is currently suspended, and the duration of this pause is unknown."

The pause is broader than just IC funding. As of FY26 budget negotiations, "Public Health data modernization, RREDI, and CFA are each necessary components of the CDC's public health data strategy, and each must be funded separately and robustly" — but the requested funding levels ($340M annually for DMI, $55M for 1CDP, $100M for the Center for Forecasting and Outbreak Analytics) are subject to FY26 LHHS appropriations bill outcomes that have repeatedly stalled.

The infrastructure that was built (EDAV, eCR, parts of NBS modernization) continues to operate, but the broader architectural rollout — connecting STLT systems into the North Star framework — has slowed dramatically. Many STLT data modernization leads, hired with DMI funds, are facing position uncertainty.

### 1.6 What remains useful from North Star regardless of CDC's status

Even if CDC never resumes the rollout, the *architectural pattern* North Star encoded is broadly correct. Independent platforms aligned with that pattern can fill gaps, and several of those gaps are exactly what JACKPOT is positioned to fill in the genomics layer. The remainder of this document develops which specific North Star commitments JACKPOT should adopt and how STLT-shaped operators benefit.

---

## 2. The STLT public health landscape

Before mapping JACKPOT to STLT, it helps to be precise about what STLT actually means — the four populations differ dramatically in size, technical capacity, governance, and funding.

### 2.1 The four constituencies

| Tier | Count | Typical size | Funding model | Genomics capacity |
|---|---|---|---|---|
| **State** | 50 + DC | 100s to 1000s of staff; multi-million $ IT budgets | CDC cooperative agreements (ELC, PHIG, PHEP), state appropriations, federal pass-through | Most have some sequencing capacity; ~25 have mature pathogen-genomics programs |
| **Territorial** | 5 (PR, USVI, Guam, AS, CNMI) + 3 Freely Associated States (Marshall Islands, Micronesia, Palau) | Small, often sub-state-level capacity | CDC + DOI Insular Affairs + territorial appropriations | Mostly send-out; very few have in-house sequencing |
| **Local** | ~3,000 (county + city + region) | 1 epi to a couple hundred staff; budgets vary 10000x | Local appropriations + state pass-through + federal grants | Few have in-house sequencing; most depend on state lab |
| **Tribal** | 574 federally-recognized Tribes + 41 Urban Indian Organizations + 12 Tribal Epidemiology Centers (TECs) | Highly variable; some Tribes have <500 members, some >300,000 | IHS, CDC TECPHI, Tribal funds | Almost no in-house sequencing; data-sovereignty concerns dominate |

Approximate totals:

- **Tribal**: "Together, the TECs offer services to 574 Tribes, 41 UIOs, and 9.7 million American Indian and Alaska Native (AI/AN) people nationwide"
- **Local**: ~3,000 LHDs nationwide (city + county + multi-county)
- **State**: 50 + DC = 51 STAHs (state and territorial agency heads)
- **Territorial + Freely Associated States**: 8

### 2.2 The "Big Cities Health Coalition" sub-segment

About 30 of the largest local health departments (Houston, LA County, NYC, Chicago, etc.) have capabilities exceeding many states. They're "local" politically but "state-class" technically. Several already run in-house sequencing.

### 2.3 The Tribal landscape requires more nuance

For everything else in this document, "Tribal" is treated as a single tier — but the reality is much more layered.

#### 2.3a Tribal sovereignty is foundational, not optional

"Tribal Public Health Authority is inherent and includes disease surveillance". Tribes are sovereign nations with treaty relationships to the US federal government. Their public health authority does not derive from federal or state delegation — it is inherent. Any system serving Tribal health must respect that.

#### 2.3b Tribal Epidemiology Centers (TECs)

"TECs are public health authorities. Permanently reauthorized in 2010, the Indian Health Care Improvement Act (IHCIA) designated TECs as public health authorities. As public health authorities, TECs can access data, including protected health information, held by the US Department of Health and Human Services for various public health activities."

There are 12 TECs, each serving an IHS administrative area. They are HIPAA-recognized public health authorities — meaning they have legal standing to receive PHI for public health purposes. This is the equivalent of a state health department's authority, and crucial for any platform planning to share or aggregate Tribal data. TECs work in partnership with Tribes, Urban Indian Organizations (UIOs), and Tribal communities, and are funded by IHS plus TECPHI (CDC's Tribal Epidemiology Centers Public Health Infrastructure cooperative agreement, ~$6.8M/year through 2026).

The 12 TECs:

1. Alaska Native TEC (Alaska Native Tribal Health Consortium)
2. Albuquerque Area Southwest Tribal Epi Center (AASTEC)
3. California Rural Indian Health Board / Karuk Tribe TEC
4. Great Lakes Inter-Tribal Epidemiology Center
5. Great Plains TEC (Great Plains Tribal Chairmen's Health Board)
6. Inter Tribal Council of Arizona (ITCA) TEC
7. Northwest TEC (Northwest Portland Area Indian Health Board)
8. Oklahoma Area TEC (Southern Plains Tribal Health Board)
9. Rocky Mountain Tribal Epi Center
10. Seattle Indian Health Board / Urban Indian Health Institute
11. United South and Eastern Tribes (USET) TEC
12. Northern Plains Tribal Epi Center (NPTEC)

Plus a Network Coordinating Center.

#### 2.3c CARE Principles for Indigenous Data Governance

The **CARE Principles** are the canonical framework for Indigenous Data Sovereignty. Where FAIR (Findable, Accessible, Interoperable, Reusable) is *data-centric*, CARE is *people-and-purpose-centric*:

| Letter | Principle | What it means in practice |
|---|---|---|
| **C** | **Collective Benefit** | Data ecosystems shall be designed and function in ways that enable Indigenous peoples to derive benefit from the data |
| **A** | **Authority to Control** | Indigenous peoples' rights and interests in Indigenous data must be recognized and their authority to control such data be empowered |
| **R** | **Responsibility** | Those working with Indigenous data have a responsibility to share how those data are used to support Indigenous peoples' self-determination and collective benefit |
| **E** | **Ethics** | Indigenous peoples' rights and wellbeing should be the primary concern at all stages of the data life cycle and across the data ecosystem |

"The CARE Principles are people– and purpose-oriented, reflecting the crucial role of data in advancing innovation, governance, and self-determination among Indigenous Peoples. The Principles complement the existing data-centric approach represented in the 'FAIR Guiding Principles for scientific data management and stewardship' (Findable, Accessible, Interoperable, Reusable). The CARE Principles build upon earlier work by the Te Mana Raraunga Maori Data Sovereignty Network, US Indigenous Data Sovereignty Network, Maiam nayri Wingara Aboriginal and Torres Strait Islander Data Sovereignty Collective, and numerous Indigenous Peoples, nations, and communities. The goal is that stewards and other users of Indigenous data will 'Be FAIR and CARE.'"

The CARE Principles were developed by the International Indigenous Data Sovereignty Interest Group within the Research Data Alliance — the same standards body that gave the world FAIR. They're not a fringe perspective; they're the converged international Indigenous-led standard.

#### 2.3d The data sovereignty operational definition

Indigenous data sovereignty is the right of a nation to govern the collection, ownership, and application of its own data. In genomics, this gets concrete fast:

- **Collection**: Who decides what gets sequenced? Tribal IRBs.
- **Ownership**: Who holds the genomic data? In some Tribal protocols, the Tribe holds original consent and authorizes specific uses, including the right to revoke.
- **Application**: For what purposes can the data be used? Tribal research codes increasingly specify approved uses with explicit reservation of rights.
- **Deletion**: When the Tribe withdraws consent, what happens to derivative analyses, pipeline results, public databases? This is the hard one.

JACKPOT's existing immutable-pipeline-results model — designed for provenance and reproducibility — is in direct tension with the deletion-on-request requirement of CARE-aligned data governance. Section 7 develops the architectural answer.

### 2.4 Cross-cutting: the genomics capacity gradient

Cross-cutting all four tiers is genomics capacity, which varies wildly:

| Capacity tier | Description | Examples |
|---|---|---|
| **Sequencer-in-house, full bioinformatics team** | State labs with mature programs; ~25 states + a handful of large LHDs | NYDOH Wadsworth, CA-DPH, MN-MDH, Houston Health |
| **Sequencer-in-house, limited bioinformatics** | Has hardware but relies on external pipelines; many states + a few LHDs | Most states with new ELC-funded sequencers |
| **Send-out, but interpret results** | No in-house wet lab; receives FASTQ/results and acts | Most LHDs + Territories |
| **Receive epidemiology summaries only** | No genomic data handling at all | Most LHDs + most Tribes (but see TEC discussion) |

JACKPOT's architecture should serve all four — and the lower-capacity tiers might be the bigger market. Most existing genomics platforms (Pathogenwatch, EnteroBase, BV-BRC) only really serve the top two tiers.

---

## 3. Where North Star and JACKPOT align

JACKPOT was designed independently of North Star, but the architectural choices already made line up surprisingly well. Going through North Star's commitments one by one:

### 3.1 "Blueprint, not platform" → JACKPOT is software, not a deployment

JACKPOT (post-pivot) is a software package that operators deploy themselves, with `Midnight-Oil-Innovation/jackpot` as the canonical reference and `jackpot init` as the install-time bootstrap. This matches North Star's "different levels of support" model — JACKPOT just instantiates it for the genomics layer. ✅ **Already aligned.**

### 3.2 Tiered support levels → JACKPOT's six install scenarios

JACKPOT's scenarios A–F directly encode tiered deployment capability:

| Scenario | North Star equivalent | STLT use case |
|---|---|---|
| **A — Single academic lab on laptop** | Lowest-capacity STLT tier with local data control | Tribal authority with sovereignty constraints; small LHD |
| **B — Single org on cloud** | Mid-tier STLT with cloud literacy | Mid-sized state, larger LHD |
| **C — Multi-lab agency** | State or large local agency operating multiple labs | NYDOH-shaped state health departments |
| **D — Hosted multi-tenant SaaS** | Implementation-Center-style hosted offering | Where TECs serving multiple Tribes might land |
| **E — Federation member** | Cross-jurisdictional sharing without central control | TEC-Tribe federation; multi-state outbreak response |
| **F — CI test** | (not applicable) | (internal) |

✅ **Already aligned.** The mapping suggests Scenario T (Tribal-deployment variant of A or E with extra sovereignty controls) is worth adding explicitly — see Section 6.

### 3.3 "CDC Front Door" → JACKPOT's six ingest paths

North Star's Front Door reduces friction for STLT submitters. JACKPOT's six ingest paths (signed URL, URI registration, SRA/accession import, workspace promotion, CSV batch, Globus deposit-first) achieve the equivalent at the genomics layer. Add a seventh — FHIR `MolecularSequence` ingest (Section 5) — and JACKPOT becomes the canonical "single entry point for genomic data into a public health agency." ✅ **Mostly aligned; FHIR ingest is the gap.**

### 3.4 Local data control → JACKPOT's deployment model

> "The intent... is to provide the benefits of a common cloud platform while preserving state and local control of data and data use."

JACKPOT goes further than North Star promised: not just a *common cloud platform with local control* but also *local deployment options* (Scenario A laptop, Scenario E federation). For Tribal authorities specifically, this is non-negotiable. ✅ **Already aligned, exceeds North Star.**

### 3.5 Interoperability via TEFCA + FHIR → JACKPOT has a gap

This is where JACKPOT lags. JACKPOT speaks LinkML for schema, custom REST for API, HL7-adjacent formats (PHA4GE templates) for some metadata. It does *not* speak FHIR natively, and it has no TEFCA story.

The honest positioning here:

- **Pathogen genomics is not the leading edge of FHIR uptake.** eCR and ELR are. FHIR `MolecularSequence` resource exists but is not widely deployed in public-health workflows yet.
- **However, North-Star-aligned operation will eventually require FHIR.** State health departments running TEFCA-connected eCR pipelines will expect any genomics platform to consume FHIR-shaped sample/specimen references.
- **JACKPOT can choose timing.** Adding a FHIR ingest path *today* is premature. Adding it in Year 2 when there's pressure from one or two operators is right-sized.

Recommended stance: declare FHIR support as a roadmap item (Year 2 or based on demand), and make sure JACKPOT's data model translates cleanly to FHIR `MolecularSequence` and `Specimen` resources when that day comes. The LinkML schema makes this much easier than Loculus's per-organism YAML approach. ⚠️ **Gap, but right-sized to defer.**

### 3.6 Workforce / training alignment → opportunity

DMI Priority 3 was workforce development. APHL has been the primary delivery vehicle — "The Public Health Laboratory Fellowship Program: an APHL-CDC Initiative prepares scientists for careers in public health laboratory science. It is open to recent graduates with a bachelor's degree or higher, and offers a Bioinformatics and Molecular Epidemiology focus area."

JACKPOT can plug into this. Specifically, the APHL Bioinformatics Fellowship Program produces bioinformaticians who graduate looking for platforms to work on. A well-documented JACKPOT, with good developer onboarding, could become the platform that newly-trained public-health bioinformaticians know how to use. This is a market entry strategy with a 12–18-month payoff. ✅ **Opportunity to align.**

### 3.7 What JACKPOT does that North Star didn't promise

A few JACKPOT differentiators that *exceed* North Star expectations:

- **Two PII gates at ingest** (NCBI SRA Human Scrubber + GCP DLP) — North Star didn't address genomic-specific PII.
- **AGPL-3.0 with explicit governance docs** — North Star promised local control via cloud configuration, not via license.
- **Multi-deployment-target architecture** — North Star expected most operators to use a CDC-hosted service; JACKPOT designs for self-hosting from day one.
- **Pathogen genomics specialization** — North Star is broad; JACKPOT is narrow but deep.

These differentiators matter most for the *Tribal* case where federally-hosted infrastructure is structurally unappealing.

---

## 4. Where North Star is silent and JACKPOT can lead

Three areas where North Star didn't go but JACKPOT could:

### 4.1 Indigenous Data Sovereignty (CARE Principles)

North Star uses "STLT" as a four-letter acronym uniformly. In practice, the T (Tribal) was sometimes treated as a special case of L (Local) — which it definitely is not. Tribes are sovereign nations.

There's no evidence in the public North Star materials that CARE Principles were formally adopted as a design constraint. By contrast:

- **NIH** has explicit Indigenous data governance guidance for genomic research grants.
- **Tribal IRBs** routinely require CARE-aligned data handling.
- **NPAIHB and similar Tribal organizations** have published their own data sovereignty policies.
- **Some states** (Washington, New Mexico, Arizona, Oklahoma, etc.) have inter-governmental agreements with Tribes that go beyond what North Star contemplates.

JACKPOT formally adopting CARE Principles + designing for Tribal-deployment scenarios is a *category-of-one* differentiator in pathogen genomics. None of Loculus, Pathogenwatch, EnteroBase, NCBI PD, BV-BRC, Solu, RT-MetA, or GISAID does this.

### 4.2 Air-gappable / sovereignty-preserving deployment

North Star assumed cloud connectivity. CARE-aligned and IDSov-aligned deployments often require:

- Data never leaves Tribal infrastructure (or only leaves with explicit per-export approval)
- No third-party cloud dependencies the Tribe cannot independently audit
- Optional connectivity to upstream peers (TEC, state, CDC) at the Tribe's discretion
- True deletion when consent is withdrawn

This shape — local-first with controlled federation — is RT-MetA's territory (per the Pathoplexus/Loculus overview's Section 16.7) and also Scenario A/E in JACKPOT's existing roadmap. The gap is making it *explicit* in spec.md and the deploy guides as **Scenario T**.

### 4.3 Genomics-specific data flows

North Star is mostly about case data, lab data, vital records, immunization. Pathogen genomics is mentioned in passing, often as "we'll figure out genomics later" or "FHIR `MolecularSequence` exists." There's no genomic-specific architecture in North Star equivalent to the level of detail given to eCR, ELR, NBS, and immunization registries.

This is actually fine — it means the genomics layer hasn't been pre-claimed by a federal-led design that would constrain JACKPOT. JACKPOT can lead here, then propose alignment when (if) North Star resumes.

---

## 5. TEFCA, FHIR, and the question of integration timing

### 5.1 The high-altitude picture

TEFCA is the policy + agreements framework. "TEFCA addresses [siloed data systems] by facilitating real-time health information data exchange between PHAs and their partners. Through TEFCA, PHAs can access real-time critical health data, such as electronic case reporting (eCR), immunization reporting, syndromic surveillance, and lab reports."

QHINs (Qualified Health Information Networks) are the network operators that have signed the Common Agreement. As of 2025 there are about a dozen QHINs operational.

PHAs (Public Health Agencies) participate as *exchange purpose actors* — they can query for data under explicitly enumerated public-health exchange purposes (Level 1 = general public health; Level 2 = ECR or ELR specifically). "A TEFCA query is the act of asking for information through the TEFCA exchange. While eligible PHAs may initiate queries for data for any allowable public health purpose ('Level 1' public health purpose queries), they may also choose to define their queries under the narrower ECR or ELR sub-purposes (defined as 'Level 2' public health queries)."

### 5.2 Where genomics fits in TEFCA — and doesn't

The TEFCA Public Health Exchange Purpose currently focuses on case reporting and case investigation. "It identifies the initial use case that will be supported in the public health exchange purpose (case reporting and case investigation)."

Genomic data exchange is *not* a TEFCA initial use case. It's plausibly in scope for future iterations, but not today.

So what does JACKPOT actually need from TEFCA?

- **Probably not direct TEFCA participation.** JACKPOT is genomics-layer, not case-reporting-layer.
- **But** STLT operators running JACKPOT will be receiving eCR via TEFCA. Linking a specimen referenced in an eCR to a genome sequenced and analyzed in JACKPOT requires JACKPOT to consume FHIR `Specimen` and `MolecularSequence` resources.
- **And** JACKPOT can usefully *emit* FHIR resources back into the operator's record systems — when a sequence is processed, emit a FHIR `Observation` with `MolecularSequence` reference back into the operator's eCR-receiving system.

### 5.3 FHIR resources that matter for JACKPOT

The relevant FHIR R5 resources:

| FHIR resource | Where JACKPOT uses it |
|---|---|
| `Patient` | NEVER — JACKPOT doesn't store patient identifiers |
| `Specimen` | Inbound — link a JACKPOT sample to an upstream specimen reference from eCR/ELR |
| `Substance` | Inbound for some bacterial culture isolates |
| `Observation` (lab result) | Inbound from ELR; outbound for sequence-derived results |
| `MolecularSequence` | Both directions — the canonical FHIR shape for genomic data |
| `Organization` | Inbound — link sequencing labs and PHAs |
| `Practitioner` | NEVER — JACKPOT users are not patient-care practitioners in the FHIR sense |
| `Provenance` | Outbound — emit pipeline-result provenance |

Note the deliberate "NEVER" rows. JACKPOT doesn't process patient-level PHI by design (that's the metadata DLP gate's job — block samples that have PHI in them). Adopting FHIR shouldn't change that posture; if anything, it reinforces it.

### 5.4 Recommended timing

- **Now (Year 1):** Document JACKPOT's data model in FHIR-translatable terms. The LinkML schema gives us enough abstraction that this is documentation work, not engineering.
- **Year 2 if pressure mounts:** Build a `backend/routers/fhir.py` that consumes inbound FHIR `Specimen` and `MolecularSequence` and emits outbound `Observation` and `Provenance` for completed pipelines.
- **Year 2+ if a TEFCA-participating operator adopts JACKPOT:** Help them build the bridge from their TEFCA-receiving infrastructure to JACKPOT. This is operator-side integration work that JACKPOT just needs to *enable*.

The key thing is **don't build TEFCA/FHIR support speculatively**. The implementation cost is real and the window of relevance for STLT operators is 2–3 years out for genomics specifically.

---

## 6. STLT-tailored deployment model — JACKPOT install scenarios mapped to operators

This is the practical synthesis. The existing six-scenario model from spec.md needs one addition (Scenario T) and explicit mappings.

### 6.1 The seven scenarios (proposed)

| Scenario | Operator type | Existing? |
|---|---|---|
| **A** | Single academic lab on a laptop | Existing |
| **B** | Single org on cloud (GCP/AWS/Azure) | Existing |
| **C** | Multi-lab agency (e.g. state health dept) | Existing |
| **D** | Hosted multi-tenant SaaS | Existing |
| **E** | Federation member | Existing |
| **F** | CI / e2e test harness | Existing |
| **T** | **Tribal-sovereignty deployment** (variant of A or E) | **New — proposed** |

Scenario T isn't a separate codebase — it's a deployment posture with a different defaults profile and a different governance/install guide. Specifically:

- All data resides on Tribally-controlled infrastructure
- Cloud DLP and cloud-only features either disabled or configurable per Tribal policy
- Audit log includes CARE-Principle-tagged events (consent grant, consent withdrawal, derivation)
- Federation enabled if-and-only-if the Tribe's policy allows
- Soft-delete + true-delete flow defaults to "true delete" rather than "soft delete with retention"
- Install guide specifically authored with Tribal IT staff in mind

### 6.2 STLT-tier deploy guides

Each STLT tier gets a tailored markdown guide in `docs/deploy/stlt/`:

```text
docs/deploy/stlt/
├── state-health-department.md      Scenario C usually; sometimes B for smaller states
├── territorial-health-agency.md    Scenario B; Freely Associated States may need A
├── local-health-department.md      Scenario A or B; Big Cities Health Coalition: C
├── tribal-authority.md             Scenario T
└── tribal-epidemiology-center.md   Scenario E (federation hub for member Tribes)
```

Each guide covers:

1. Why this scenario fits this operator type
2. Install steps (pointer to `jackpot init` + scenario-specific config)
3. Governance and data-handling defaults
4. Federation options (who you can peer with, on whose terms)
5. Funding sources to pay for it (ELC, PHIG, IHS TECPHI, ARP, etc.)
6. Workforce considerations (do you have a bioinformatician? if not, here's what JACKPOT does for you out of the box)
7. Common pitfalls and how to avoid them

### 6.3 Funding-source-aware install profiles

A useful pattern from CDC's own grant-management work: each install scenario has a "what funding pays for this" cheat sheet. Examples:

- **Scenario A** (laptop): No cloud cost. Hardware + a bioinformatician-day's worth of install effort. Often paid out of operational budget, not grants.
- **Scenario B** (single-org cloud): GCP/AWS/Azure cost ~$200–800/month + occasional pipeline batch costs. Often paid out of ELC IT line items or PHIG.
- **Scenario C** (multi-lab agency): GCP/AWS cost scales with usage; commonly $1000–10000/month all-in for a state health dept. Funded via state IT or PHIG.
- **Scenario T** (Tribal): TECPHI, IHS direct funding, or Tribally-appropriated funds. Costs vary widely; some Tribes choose Scenario A laptop precisely because it has no recurring cost.

This matters because grant-writing public-health staff need to know what budget category to put JACKPOT into.

---

## 7. Architectural implications of Tribal sovereignty (the one place that adds engineering work)

Most of the STLT alignment in this document is documentation, governance, or config work. There's exactly one architectural change that adds real engineering:

### 7.1 The deletion-on-request requirement

CARE Principle "Authority to Control" implies: when a Tribe withdraws consent for data use, the data must actually leave the system. Not be hidden, not be flagged as deleted — actually removed.

This is in tension with JACKPOT's existing immutable-pipeline-results model:

- Samples in the `samples` table are mutable (pre-pipeline) and audit-logged
- `pipeline_results` rows are immutable, append-only, JSONB blobs preserving every pipeline run
- File URIs in GCS or operator storage are referenced from those rows
- Audit log preserves all state changes

For a normal sample, immutability is a feature — you can prove what was true at any point in time, reproducibility is preserved, the audit trail is complete. For a sovereignty-withdrawn sample, immutability is a violation.

### 7.2 The architectural answer: tombstone-and-vacuum

The pattern that satisfies both:

1. **`deletion_status` column on `samples`** — enum: `ACTIVE | DELETION_REQUESTED | TOMBSTONED | VACUUMED`
2. **`pipeline_results` rows for tombstoned samples are sealed but readable** — until the vacuum step
3. **Tombstone marks all derivative rows** — when a sample is tombstoned, every `pipeline_results` row, every cached file, every dataset that included the sample is marked
4. **Vacuum step actually deletes** — a periodic background job (configurable cadence per operator policy; for Scenario T defaults to 24 hours) physically removes:
    - The sample row's sequence URIs
    - The actual files in storage (GCS object delete, MinIO delete, etc.)
    - All `pipeline_results.result_data` JSONB content for that sample
    - All cached intermediate artifacts in the work bucket
5. **Audit log preserves the *fact* of deletion, not the deleted content** — operator can prove a sample was once present and was deleted on request, but cannot reconstruct the data

### 7.3 The challenge: federation-aware deletion

If a sample was federated to a peer JACKPOT instance under a sharing agreement, the tombstone needs to propagate. This is where it gets harder:

- Peer instances must honor the deletion request
- Peer instances must confirm deletion to the originating instance
- If a peer fails to delete, the originating instance must be able to record the failure and surface it to the operator

The Tribal authority's options when a peer doesn't delete: legal recourse, removal of future sharing, public disclosure of non-compliance. The platform's job is to make non-compliance impossible to hide.

**Implementation pattern**:

- Federated sharing agreement explicitly includes deletion-propagation as a required term
- Tombstone events are pushed to all peers known to have received the data
- Peers acknowledge deletion via signed receipt
- The originating instance maintains a deletion-receipt log
- If a peer doesn't acknowledge within an SLA, the originating instance flags it

### 7.4 The challenge: derivative analysis

If a sample contributed to a cluster computation (e.g., a cgMLST cluster including 50 samples, one of which is now tombstoned), what happens to the cluster?

Three options:

1. **Recompute** — re-run the clustering excluding the tombstoned sample. Cluster ID may shift, but the cluster is honest. Default for Scenario T.
2. **Generalize** — note in the cluster metadata that it included a sample that has been withdrawn. Don't recompute; surface the asterisk. Less honest but cheaper.
3. **Mark for reanalysis** — flag the cluster as stale, recompute on next scheduled cluster job. Compromise option.

Recommendation: recompute (option 1) by default for Scenario T; configurable for other scenarios.

### 7.5 What about samples already published to NCBI/GenBank?

This is the genuinely hard case. Once a sample is published to NCBI under an open-access license, the platform cannot retract it from NCBI. The Tribal authority needs to be aware of this *before* sharing.

Implementation pattern:

- Scenario T defaults to "no auto-publish; explicit per-sample approval required"
- Pre-publish review checklist includes a CARE-Principle confirmation
- Publication URIs are recorded; deletion-on-request can mark them as "data was published; cannot be retracted from external party"
- A "previously-published" tag persists even after vacuum, so the system can be honest about what's still in the wild

This is the failure mode that Tribal authorities most need to be protected from. Auto-INSDC submission (recommendation B-LOC-1 in the Pathoplexus/Loculus overview) is *not* compatible with Scenario T defaults. That's a tension to flag in the deploy guide.

---

## 8. The TEC federation pattern — Scenario E concretized for Tribal contexts

Federation is the most architecturally interesting JACKPOT feature for STLT operators, and TECs are the canonical use case.

### 8.1 The pattern

A Tribal Epidemiology Center serving N member Tribes runs a JACKPOT instance. Each member Tribe optionally runs its own JACKPOT instance (Scenario T). Federation between Tribe and TEC is governed by a Tribally-controlled data-sharing agreement.

Architecturally:

```text
Tribe A (Scenario T) ──┐
                       │
Tribe B (Scenario T) ──┼──→  TEC (Scenario E hub)  ──→ optional CDC peering
                       │                               (only if all member
Tribe C (Scenario A) ──┘                                Tribes' agreements
                                                        permit)
```

### 8.2 What the TEC instance does

- Aggregates data from member Tribes per per-Tribe sharing agreements
- Computes cross-Tribe cluster analyses (with member Tribes' consent)
- Provides public-health-authority view (HIPAA-recognized) for IHS, state health departments, CDC reporting
- Optionally peers with other TECs for multi-region outbreak investigation
- Honors deletion requests propagated from member Tribes

### 8.3 What the Tribe instance does

- Holds Tribal sample data on Tribal infrastructure
- Pushes specific samples to the TEC instance per Tribal IRB approval
- Maintains the Tribe's own pipeline results, dashboards, reports
- Tribe-specific governance, including the right to revoke any prior sharing

### 8.4 Why this matters

This pattern is specifically called for in Indigenous data governance literature. Right now, no genomics platform implements it. JACKPOT being the first would be:

- A real public-health benefit (TECs are chronically under-resourced for bioinformatics)
- A category-of-one differentiator for grant proposals
- A natural fit for IHS TECPHI and ELC funding lines

### 8.5 Proof-point candidates

Three TECs that would be especially good early adopters based on existing genomics-curiosity signals (this would need to be validated by direct outreach):

| TEC | Why fit |
|---|---|
| **Northwest TEC** (NPAIHB) | Strong existing data-sovereignty work, IHS Portland Area pilot project for racial misclassification correction shows technical sophistication |
| **AASTEC** (Albuquerque Area) | Public records of bioinformatics interest; Southwest geographic coverage |
| **ITCA TEC** (Inter Tribal Council of Arizona) | Phoenix/Tucson coverage; strong epidemiologic capacity already |

Of these, NPAIHB is probably the best opening conversation given their existing data-modernization work.

---

## 9. JACKPOT positioning relative to NBS, eCR, AIMS, and existing public-health systems

This is where it's important to be honest about scope — JACKPOT is *not* a CDC-replacement, and shouldn't be positioned as one.

### 9.1 The layer cake

```text
┌─────────────────────────────────────────────────────────────┐
│  CASE-LEVEL EPIDEMIOLOGY                                    │
│  NBS, MAVEN, Trisano (state-specific)                       │
│  Receives: case reports, lab results, demographic data      │
│  Owns: the case as the epidemiologic unit                   │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ ECR/ELR via TEFCA
                            │
┌─────────────────────────────────────────────────────────────┐
│  ELECTRONIC CASE REPORTING / LAB REPORTING ROUTING          │
│  eCR via APHL AIMS, ELR via state systems                   │
│  Routes structured FHIR/HL7 messages from healthcare to PHA │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ HL7 / FHIR
                            │
┌─────────────────────────────────────────────────────────────┐
│  PUBLIC HEALTH LABORATORY OPERATIONAL SYSTEMS               │
│  LIMS (LabWare, STARLIMS, etc.)                             │
│  Owns: the specimen as the operational unit                 │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ specimen → sequencing
                            │
┌─────────────────────────────────────────────────────────────┐
│  ★ JACKPOT ★                                                │
│  Pathogen genomics platform                                 │
│  Owns: the sample (specimen + sequencing run + analyses)    │
│  Provides: typing, AMR, phylogeny, outbreak detection       │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ pipeline results
                            │
┌─────────────────────────────────────────────────────────────┐
│  DOWNSTREAM REPOSITORIES + ANALYSIS                         │
│  NCBI Pathogen Detection, GISAID/ENA, Pathoplexus,          │
│  Pathogenwatch, Nextstrain, GenSpectrum                     │
└─────────────────────────────────────────────────────────────┘
```

JACKPOT lives between the LIMS layer and the downstream-analysis layer. It is *fed by* the LIMS and *feeds* the downstream platforms.

### 9.2 What this means for STLT operators

For a state running NBS, JACKPOT is *not* a replacement. JACKPOT consumes specimen references that originated upstream (often via FHIR `Specimen` resources) and emits sequence-derived analyses that get linked back to the case in NBS.

The integration pattern:

```text
NBS case ←──── linked by specimen ID ────→ JACKPOT sample
                                              │
                                              ├── pipeline_results
                                              ├── cluster ID (NCBI PD or local)
                                              └── AMR profile
```

This makes JACKPOT a *complement* to NBS, not a competitor. State epidemiologists keep working in NBS for case management; JACKPOT serves the bioinformatics-and-genomics layer; results flow back into the case via specimen-ID joins.

### 9.3 Don't try to do what AIMS does

APHL's AIMS Platform is a message-routing infrastructure for laboratory data exchange — eCR routing, ELR routing, specimen tracking, IZ Gateway for immunizations. "The pandemic taught that rapid scale-up in response to emergencies is only sustainable when paired with a platform that can agilely connect public health systems and healthcare providers across the country. Enter the AIMS Platform."

AIMS is not a JACKPOT competitor — it's a peer system at a different layer. JACKPOT *receives* messages routed via AIMS (lab reports indicating new specimens for sequencing) and emits messages back (sequence results). AIMS has been operating at scale for years and has the public-health-laboratory community's trust. Build to integrate, not to replace.

### 9.4 The APHL relationship matters

APHL is the de facto national coordinator for public health laboratories. They run the AIMS Platform, host the AMD National Bioinformatics Platform initiative, train bioinformaticians via the Public Health Laboratory Fellowship Program, and represent state public health labs in policy. "OAMD is developing the AMD National Bioinformatics Platform to bridge the gap between pathogen genomics and genomic epidemiology by developing a cloud-based computational platform for sharing, analyzing and storing NGS data and related metadata."

Two notes here:

1. **The AMD National Bioinformatics Platform is something to be aware of.** It's CDC-OAMD-funded, APHL-led, and could either be a partner or a peer-platform overlap with JACKPOT. Worth a fact-finding conversation.
2. **APHL Communities of Practice** are forums where bioinformaticians from state labs share patterns. JACKPOT presence in those CoPs would build awareness.

---

## 10. Funding-source map — what pays for STLT-deployed JACKPOT

A practical concern. Operators choosing JACKPOT need to know what budget category to put it in. The major lines:

| Funding source | Eligibility | Typical use | JACKPOT fit |
|---|---|---|---|
| **ELC (Epidemiology and Laboratory Capacity)** | States, large LHDs, territories | Lab capacity, surveillance, staff | ✅ Direct fit for state-deployed JACKPOT |
| **PHIG (Public Health Infrastructure Grant)** | All STLT | Foundational capabilities, IT infrastructure | ✅ Direct fit; the IC Program (paused) was PHIG-funded |
| **PHEP (Public Health Emergency Preparedness)** | State + LHD | Preparedness exercises, response systems | ⚠️ Possible for response-readiness framing |
| **DMI cooperative agreements** | All STLT | Data modernization specifically | ✅ Currently in limbo but historically the most direct fit |
| **TECPHI (Tribal Epi Center PH Infrastructure)** | TECs | Public health capacity, data systems | ✅ Direct fit for TEC-deployed JACKPOT (Scenario E) |
| **IHS direct service / Self-Determination Act 638** | Tribal authorities | Healthcare and public health for Tribal members | ✅ Possible for Tribe-deployed JACKPOT (Scenario T) |
| **ARP (American Rescue Plan)** | All STLT | Pandemic response, lasting through ~2025 | ⚠️ Sunsetting; some allocations remain |
| **Wellcome / Gates / Sloan / philanthropic** | Any | Open source infrastructure | ⚠️ Possible for non-US deployments or open-source maintenance |
| **State / Territorial / Tribal own funds** | Self | Anything they want | ✅ The cleanest path; depends on appropriations |

This map should go in the deploy guides for each STLT tier (Section 6.2).

---

## 11. Top actionable takeaways

If only seven things land out of this document:

1. **Adopt CARE Principles formally.** Write `governance/care-principles-and-tribal-data-sovereignty.md`. Pair with FAIR. This is governance work, not engineering.

2. **Add Scenario T (Tribal-sovereignty deployment).** Variant of A or E with sovereignty-aware defaults. New deploy guide in `docs/deploy/stlt/tribal-authority.md`. Update spec.md scenarios list.

3. **Implement true delete-on-request.** Tombstone-and-vacuum lifecycle. The one piece of architectural engineering that genuinely adds work. Probably a session of design work + 2–3 sessions of implementation. Phase: P0c (multi-tenancy middleware) is the right home, since tenant-aware deletion overlaps with multi-tenancy.

4. **Build the STLT deploy guides.** Five tailored markdown guides under `docs/deploy/stlt/`. Documentation work. Phase: P0d alongside the rest of the install-guide reorganization.

5. **Reach out to NPAIHB / Northwest TEC** about a Scenario T pilot. They have the data-modernization sophistication to be a credible early-adopter Tribal Epidemiology Center. One email + one call.

6. **Position JACKPOT alongside, not against, NBS / eCR / AIMS.** Document the layer cake (Section 9.1). Make sure spec.md and grant narratives reflect this. JACKPOT integrates with these systems; it does not replace them.

7. **Defer FHIR / TEFCA support to Year 2.** Don't build speculatively. Document the data model in FHIR-translatable terms now (LinkML makes this cheap). Build actual FHIR ingest/emit when an operator asks for it.

---

## 12. Concrete backlog items for `todo.md`

These slot into Phase 26 alongside the Pathoplexus/Loculus items, with prefix `B-STLT-` for STLT-tier specific items, `B-CARE-` for Tribal-sovereignty items, `B-DMI-` for North-Star-alignment items.

```text
[ ] B-CARE-1   Adopt CARE Principles formally. Write
               governance/care-principles-and-tribal-data-sovereignty.md
               documenting JACKPOT's commitment to Collective Benefit,
               Authority to Control, Responsibility, and Ethics.
               Pair with FAIR adoption. Effort: 4-6 hours of writing.
               Phase: P0d (alongside B-GOV-1).

[ ] B-CARE-2   Add Scenario T (Tribal-sovereignty deployment) to spec.md
               scenarios list. Variant of A or E with sovereignty-aware
               defaults. Effort: 1 session (spec edit + docs).
               Phase: P0e.

[ ] B-CARE-3   Implement true delete-on-request via tombstone-and-vacuum
               lifecycle. Adds samples.deletion_status column
               (ACTIVE | DELETION_REQUESTED | TOMBSTONED | VACUUMED).
               Background job removes file URIs, GCS objects,
               pipeline_results JSONB content, cached artifacts.
               Audit log preserves the fact of deletion, not content.
               Effort: 1 session design + 2-3 sessions implementation.
               Phase: P0c (multi-tenancy middleware).

[ ] B-CARE-4   Federation-aware deletion propagation. Tombstone events
               pushed to peers; signed receipts; SLA tracking; non-
               compliance flagging. Effort: 1 week. Phase: Year 2,
               with Scenario E federation work.

[ ] B-CARE-5   Pre-publish review checklist with CARE-Principle
               confirmation. Scenario T defaults to no-auto-publish;
               explicit per-sample approval required. "Previously
               published" tag persists past vacuum.
               Effort: 1-2 sessions. Phase: with B-CARE-3.

[ ] B-CARE-6   Reach out to NPAIHB / Northwest TEC about Scenario T
               pilot. Effort: 1 email + 1 call. Phase: now.

[ ] B-STLT-1   Build five STLT deploy guides under docs/deploy/stlt/:
               state-health-department.md, territorial-health-agency.md,
               local-health-department.md, tribal-authority.md,
               tribal-epidemiology-center.md. Each covers fit,
               install, governance, federation, funding, workforce,
               pitfalls. Effort: 1 session per guide. Phase: P0d.

[ ] B-STLT-2   Add layer-cake diagram (Section 9.1 of overview) to
               spec.md positioning JACKPOT relative to NBS / eCR /
               LIMS / downstream repositories. Effort: 1 session.
               Phase: any.

[ ] B-STLT-3   Add funding-source map (Section 10 of overview) to
               STLT deploy guides — what budget category to use for
               JACKPOT in each STLT tier. Effort: 1 session.
               Phase: with B-STLT-1.

[ ] B-DMI-1    Document JACKPOT's data model in FHIR-translatable terms.
               Map LinkML schema entities to FHIR resources (Specimen,
               MolecularSequence, Observation, Provenance). Doc only;
               no implementation. Effort: 2 sessions. Phase: any.

[ ] B-DMI-2    Build backend/routers/fhir.py for FHIR Specimen +
               MolecularSequence ingest, Observation + Provenance
               emit. Effort: 1-2 weeks. Phase: Year 2, gated on
               operator demand.

[ ] B-DMI-3    Document the "JACKPOT as single-entry-point for
               genomic data into a public health agency" framing
               in spec.md. Pairs with the existing six-ingest-paths
               documentation. Effort: half a session. Phase: any.

[ ] B-DMI-4    APHL Communities of Practice engagement — propose a
               JACKPOT presentation at the AMD CoP or Bioinformatics
               and Molecular Epidemiology fellowship cohort.
               Effort: 1 email + 1 talk preparation. Phase: any.

[ ] B-DMI-5    Investigate APHL AMD National Bioinformatics Platform
               for partner-vs-peer relationship. Could be parallel
               to JACKPOT, could be complementary, could share
               components. Effort: 1 fact-finding call.
               Phase: opportunistic.
```

That's 13 new backlog items: `B-CARE-1` through `B-CARE-6` (6), `B-STLT-1` through `B-STLT-3` (3), `B-DMI-1` through `B-DMI-5` (5). Wait — that's 14. Let me recount: 6 + 3 + 5 = 14. ✓

These should be added to Phase 26 of `todo.md` as a new sub-group K (or as a separate Phase 27 if you prefer). They're orthogonal to the A–J groups (which are platform-source-grouped), so a new K group fits cleanly:

> #### K. CDC DMI / North Star / STLT alignment (overview Sections 11-12 of `jackpot_cdc_dmi_stlt_overview.md`)

---

## 13. Cross-references

| Topic | Where developed |
|---|---|
| Pathoplexus / Loculus comparative analysis | `jackpot_pathoplexus_loculus_overview.md` |
| Existing six-scenario model | spec.md §1 (post-pivot blockquote) |
| AGPL-3.0 license rationale | `jackpot_pathoplexus_loculus_overview.md` §3 |
| Two PII gates (HRRT + DLP) | `jackpot_pathoplexus_loculus_overview.md` §9 |
| WHO/IPSN attribute alignment | `Next-Generation_Biosurveillance_and_Genomic_Epidemiology.md` (project knowledge) |
| Critical Rule 55 (operator-agnostic production code) | `CLAUDE.md` Critical Rule 55 |

---

## 14. Glossary

| Term | Definition |
|---|---|
| **AIMS** | APHL Informatics Messaging Services — message-routing platform for public health laboratory data exchange |
| **AMD** | Advanced Molecular Detection — CDC initiative to integrate NGS, epidemiology, and bioinformatics for public health action |
| **APHL** | Association of Public Health Laboratories — national coordinator for state and local public health labs |
| **CARE Principles** | Indigenous Data Governance: Collective Benefit, Authority to Control, Responsibility, Ethics |
| **DMI** | CDC's Data Modernization Initiative (launched 2020) |
| **eCR** | Electronic Case Reporting — automated case reports from healthcare to public health |
| **EDAV** | CDC's Enterprise Data, Analytics, and Visualization platform |
| **ELC** | Epidemiology and Laboratory Capacity cooperative agreement (CDC funding to STLT) |
| **ELR** | Electronic Laboratory Reporting — automated lab results from clinical labs to public health |
| **FHIR** | Fast Healthcare Interoperability Resources (HL7 standard) |
| **HIPAA** | Health Insurance Portability and Accountability Act; defines public health authority access to PHI |
| **HIE** | Health Information Exchange (organization or network) |
| **IDSov** | Indigenous Data Sovereignty |
| **IHS** | Indian Health Service (US federal agency) |
| **LHD** | Local Health Department |
| **MolecularSequence** | FHIR resource type for genomic/molecular sequence data |
| **NBS** | NEDSS Base System — CDC-developed integrated information system for STLT case surveillance |
| **NEDSS** | National Electronic Disease Surveillance System (older umbrella) |
| **NPAIHB** | Northwest Portland Area Indian Health Board |
| **ONC** | Office of the National Coordinator for Health IT (HHS); now part of ASTP |
| **PHA** | Public Health Agency / Authority |
| **PHIG** | Public Health Infrastructure Grant (CDC funding to STLT) |
| **QHIN** | Qualified Health Information Network (TEFCA participant tier) |
| **RREDI** | Response Ready Enterprise Data Integration (CDC platform; component of 1CDP) |
| **STLT** | State, Tribal, Local, and Territorial (public health) |
| **TEC** | Tribal Epidemiology Center; 12 nationwide |
| **TECPHI** | Tribal Epidemiology Centers Public Health Infrastructure (CDC cooperative agreement) |
| **TEFCA** | Trusted Exchange Framework and Common Agreement (ONC/ASTP-led) |
| **UIO** | Urban Indian Organization |
| **1CDP** | One CDC Data Platform |

---

*End of overview. Companion document to `jackpot_pathoplexus_loculus_overview.md` (peer-platform comparative analysis). Together they cover the two main strategic axes for JACKPOT: technical alignment with the open-source pathogen-genomics ecosystem (Pathoplexus/Loculus + 8 peer platforms) and operational alignment with the US public-health-data ecosystem (CDC DMI + STLT operators).*
