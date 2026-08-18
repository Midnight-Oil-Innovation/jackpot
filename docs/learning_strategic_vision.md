> **Status:** Reference - JACKPOT Learn strategic vision.

# JACKPOT Learn — Strategic Vision

**Version:** 0.2 (Cluster B merge integration applied 2026-05-16)
**Status:** Pre-implementation scoping. Queued behind P0e (`jackpot init` CLI). Real work begins after P0e ships. Cross-references and scenario letters updated to align with the Cluster A architecture merge (May 2026).
**Audience:** The maintainer; future Academy/games contributors; partnership conversations with APHL, CDC CSELS, WHO IPSN, university partners, and Indigenous data sovereignty authorities.
**Working name:** "JACKPOT Learn" is a placeholder for the umbrella educational platform that hosts all four faces. Final name TBD.
**Companion docs:** `docs/immune_platform.md` (the strategic vision + implementation plan that frames Learn as Pillar IV/V); `docs/learning_curriculum_design.md` (the content + catalog companion to this vision); `docs/architecture.md` v6.0 (the canonical architecture reference).

---

## 0. Why this doc exists

JACKPOT has an emerging "fifth pillar" — the workforce/training layer — that has been sketched in fragments across what are now `docs/archived/jackpot_ais_legacy.md` (the earliest four-faces / Academy / sustainability sketch, archived as superseded by the Cluster B merge), `docs/immune_platform.md` (the consolidated immune-platform plan, which carries the Pillar IV Academy and Pillar V Gaming strategic content in §§7-8), and the original collaboration scaffolding §7 Forrest framing (now folded into `docs/immune_platform.md` Part 2). The fragments were written at different times under different framings (sometimes as a single "Academy", sometimes as four games, sometimes as a Forrest-framing meta-module).

This document consolidates those fragments into one coherent vision and — per the design instruction — **designs the shared spine first**, so the four faces don't end up as four parallel projects that drift apart.

The companion deliverable is `docs/learning_curriculum_design.md`, which goes from this vision into concrete content: module catalog, case catalogs, season arcs, and the production pipeline.

---

## 1. The thesis (one paragraph)

**JACKPOT Learn is the educational platform layer of JACKPOT — four learner-facing experiences (Academy, Field Edition, SENTINEL, WILDFIRE) running on a single shared spine, designed so that workforce development *is* platform infrastructure rather than marketing copy bolted onto it. Every face uses real JACKPOT as its substrate; every learner contribution is reusable upstream; every credential is cryptographically verifiable; and the whole thing stays AGPL-3.0 so the equity-mission audience (WHO IPSN, LMIC labs, Tribal authorities, small state PHAs) never gets gated by license.**

That single sentence is the load-bearing claim. Everything below either justifies it, operationalizes it, or constrains it.

---

## 2. The integration thesis — workforce IS the platform

Stephanie Forrest's framing for the Biodesign Center, quoted in `docs/immune_platform.md` §18.5 (the collaboration scaffolding integration, originally from the standalone scaffolding doc):

> Translating insights between computer science and biology, with a focus on understanding and mitigating malicious behavior in complex systems.

And her warning, paraphrased: technologists "isolated from those who actually use or are affected by it on a daily basis" build the wrong tooling.

JACKPOT Learn operationalizes that warning into a structural commitment:

1. **The curriculum teaches AIS by being it.** Students don't read about negative selection — they implement a tiny NSA detector against synthetic data, then watch their detector get promoted into the production `jackpot-amand` module.
2. **Student work generates labeled data.** Module exercises produce labeled anomalies that train the production clonal-selection loop. Wrong answers in Field Edition / SENTINEL / WILDFIRE become adversarial training data for the immune system.
3. **Module completions are immune memory.** The Academy runs on a tenant; student contributions are versioned, attributable, and reusable.

Each of those is a real, measurable architectural commitment, not a slogan. Together they're why Academy lives in the same monorepo as the platform code rather than as a separate teaching project.

The implication for the platform's pillar ordering is the inversion that landed in the immune-platform plan:

> The vision doc lists five pillars: Bio-AIS, Cyber-AIS, Federation Immune Network, Academy, Outbreak/WILDFIRE. Numerically, Academy is fourth. Operationally, it's zeroth.

JACKPOT Learn is pillar zero. The rest is what the people pillar zero produces actually operate.

---

## 3. The four faces, mapped

The four-faces framing was originally sketched in what is now `docs/archived/jackpot_ais_legacy.md` Part 4 and has since been developed in `docs/immune_platform.md` §§7-8. Restating with sharper edges:

| Face | Energy | Audience | One-line product description | What you walk away with |
|---|---|---|---|---|
| **Academy** | Disciplined, structured | Learners (UG, grad, professional) | Self-paced + cohort genomic-surveillance curriculum running on a real JACKPOT tenant | Signed micro-credentials, portfolio of merged PRs, track completion JWT |
| **Field Edition** | Solo, contemplative, cinematic | Self-directed practitioners; recruiting funnel | Single-player narrative case catalog with high production values | A "huh, I could actually do this job" moment; first signed badge |
| **SENTINEL** | Cooperative, urgent, optimistic | Team-builders, classroom cohorts, real PH workforce training | *Pandemic*-the-board-game energy with real bioinformatics; 3–7 players per cell | Crisis-cooperation experience that maps directly to outbreak response |
| **WILDFIRE** | Competitive, pulpy, espionage | Long-game cell players, ARG fans, federation stress-test community | Multiplayer federated espionage with adversarial AI, OPSEC scoring, attribution puzzles | Real federation OPSEC literacy; community status; eventually paper-cited capstones |

Together they cover the four corners of the player-energy space (solo/team, cooperative/competitive, structured/emergent) and all reuse the same engine: synthetic data, JACKPOT tenants, modern tooling, mission framework. That's the spine.

A learner can start anywhere and progress to anywhere else. A typical adoption arc:

```
Field Edition (try alone, get hooked)
      │
      ▼
Academy Track A — Defenders (structured learning, first credentials)
      │
      ▼
SENTINEL (apply skills in a team)
      │
      ├──► WILDFIRE (compete, stress-test, contribute adversarial cases)
      │
      ▼
Academy Track B — Builders (extend the platform, merged PRs)
      │
      ▼
Academy Track C — Architects (own a module, co-author paper)
```

Most learners stop somewhere along that arc. That's fine. Every stopping point has its own legitimate value.

---

## 4. The shared spine

This is the part where designing-spine-first matters. If we ship four faces with four bespoke engines we end up with four maintenance burdens and no compounding value. If we ship four surfaces over one spine, every spine improvement lifts all four faces.

### 4.1 Ten spine elements

| # | Spine element | Why it's shared | Where it lives in the monorepo |
|---|---|---|---|
| 1 | **Real JACKPOT as substrate** | Every face runs against a real JACKPOT instance, not a sim. No fake bioinformatics, ever. | `backend/`, `pipelines/`, `schema/` (unchanged) |
| 2 | **Synthetic data generator** | One `wgsim` / `badread` / `ART` pipeline produces all sample data with known-anomaly recipes for answer keys. | `course/data/` + a `pipelines/synthdata/` Nextflow workflow |
| 3 | **Scenario YAML format** | A single canonical schema for "what does this case/mission/episode look like" — used by all four faces. | `course/schema/scenario.yaml` (LinkML, like the rest of JACKPOT's schemas) |
| 4 | **Six-stage pedagogical pattern** | Motivation → Exploration → Concept → Implement → Evaluate → Contribute. Every learning artifact across all four faces follows it. | `course/PEDAGOGY.md` |
| 5 | **Tenant-per-face deployment** | Each face is a JACKPOT tenant. Same code, different config. Lets us reuse multi-tenancy work for free. | `deploy/learn/<face>/` |
| 6 | **Signed credentials** | One JWT/Sigstore badge format across all four faces. Version-pinned to the JACKPOT commit they were earned against. | `backend/credentials/` (new module, post-P0e) |
| 7 | **Mission framework** | Engine that loads a scenario YAML, sets up the tenant, evaluates submissions, awards credentials. Used by Academy assessments AND Field Edition cases AND SENTINEL missions AND WILDFIRE episodes. | `backend/missions/` (new module) |
| 8 | **Contributor PR model** | One pattern: PR a scenario YAML + answer key + assets to `cases/<face>/season_N/episode_M/` and get reviewed. Same across all faces. | `cases/` at repo root |
| 9 | **Governance inheritance** | The educational platform inherits JACKPOT's `governance/` directory wholesale. CARE Principles, COI policy, data-residency commitments all apply. | `governance/learn-addendum.md` |
| 10 | **AGPL applies uniformly** | All four faces are AGPL-3.0. Case content is CC-BY-SA. No tier paywalls cases or modules behind closed licenses. | `LICENSE`, `LICENSE-cases.md` |

The combination of these ten elements is the spine. Everything else is surface.

### 4.2 What each face adds *on top* of the spine

| Face | Spine-on-top additions |
|---|---|
| **Academy** | Module-renderer UI (Streamlit + JupyterHub link-out), assessment.py auto-grader, cohort scheduler, instructor dashboard |
| **Field Edition** | Narrative wrapper UI, cinematic transitions, single-player save state, "next case" recommender |
| **SENTINEL** | Real-time cooperative UI (WebSockets), cell management, shared map, mission-clock orchestration, role-aware view filters |
| **WILDFIRE** | Real-time competitive UI, OPSEC scoring engine, federation-poisoning mechanics, leaderboards, ARG layer infrastructure, live-ops dashboard |

The volume of "additions on top" goes up from Academy to WILDFIRE. That's the right direction — it matches the recommended build order (Academy and Field Edition can ship in pure Streamlit; SENTINEL and WILDFIRE need a separate React app for real-time multiplayer).

### 4.3 The architectural-deferral discipline

A repeated mistake worth pre-empting: every face has a tempting reason to demand a new backend feature. The spine discipline is "if a face needs something, it goes into the spine first or it doesn't ship." That keeps the four faces honest as surfaces over one platform, rather than four projects competing for the same maintainer's attention.

Concretely:

- WILDFIRE wants federation poisoning → that's a federation-layer feature, lives in `backend/federation/`
- SENTINEL wants role-aware view filters → that's a multi-tenancy feature, lives in `backend/middleware/`
- Academy wants an instructor dashboard → that's an RBAC + reporting feature, lives in `backend/routers/`

The face-specific code is UI/UX glue, not new platform capability.

---

## 5. Differentiators

There's a fair amount of public-health workforce training out there. JACKPOT Learn needs to be honest about where it overlaps and where it doesn't.

### 5.1 Vs. APHL / CDC CSELS / PGCoE conventional training

These programs are excellent but structurally:

- Time-limited fellowships (e.g., APHL-CDC Bioinformatics Fellowship: 10 cohorts, 66 fellows over 2014–2023 per `Accelerating the Use of Pathogen Genomics and Metagenomics in Public Health`)
- Cohort-paced, not self-paced
- Use whatever tools the fellows' host lab uses, not a shared platform
- Credentials are program-completion certificates, not stackable + portable

JACKPOT Learn is a complement, not a replacement. The pitch to CSELS/APHL is: *"Run your existing fellowship on our platform. The fellows leave with portfolios that include merged PRs to a real surveillance platform used by labs. Your program becomes more competitive for recruiting because the training output is visible and portable."*

### 5.2 Vs. Software / Data Carpentry, Galaxy Training Network, nf-core training, EMBL-EBI Train Online

These are excellent for general bioinformatics literacy:

- Generic (Linux / Python / R / workflows / specific tools)
- Not coupled to a specific surveillance platform
- Don't produce "real platform contributions"
- Don't address the cybersecurity / OPSEC / federation literacy gap

JACKPOT Learn slots downstream of them. Recommended sequence in the Academy: "Take a Carpentry / Galaxy / nf-core intro first, then come here for the applied-to-public-health-surveillance specialization."

This is also a partnership angle — we don't compete; we're the next mile.

### 5.3 Vs. serious-games and CTFs (Foldit, EteRNA, EyeWire, picoCTF, etc.)

Existence proof — science-game-as-real-engagement is documented in the legacy sketch (`docs/archived/jackpot_ais_legacy.md` Part 1). Foldit and EteRNA got peer-reviewed papers. EyeWire mapped neurons. picoCTF trained tens of thousands of security students.

The differentiator is the *category combination*:

- Foldit/EteRNA generate science but don't credential learners
- CTFs credential learners but don't generate science
- Plague Inc. has 160M players but generates neither science nor credentialed learners

**JACKPOT Learn does all three at once: credentialed learners + real platform contributions + adversarial training data for a production surveillance system.** That's the category-of-one claim, and it's defensible because the platform-as-classroom architecture is what makes the loop close.

### 5.4 Vs. commercial platforms

Solu, Galaxy Project commercial offerings, BaseSpace, Biomage. All of them have training material; none of them has the four-faces / open-contribution / signed-credentials shape. AGPL is also a meaningful differentiator here — university partners and Tribal authorities can adopt without procurement friction.

---

## 6. Strategic positioning

The plan needs landing pads. Each face has different ones.

### 6.1 WHO IPSN equity story

IPSN's vision (from the slide deck): *"Every country has equitable access to sustained capacity for genomic sequencing and analytics."* Their workforce-development pillar is real and underfunded.

Field Edition + the Academy's on-prem-first deployment story is a direct hit. A pathogen genomics fellow in Kenya, Vietnam, or Bolivia can `pipx install jackpot` on a laptop, run the curriculum, and earn portable credentials without their ministry signing a Google Cloud contract.

The pitch: "Be IPSN's reference training platform. AGPL means no licensing friction. Local-first means no connectivity dependency. Signed credentials means a fellow in Nairobi can prove competency to anyone in the world."

### 6.2 APHL workforce development

APHL has a longstanding mandate to support state public-health labs. The PGCoE Massachusetts modular-training pattern (cited in the National Academies workshop proceedings) is exactly the shape we're proposing. The pitch: "We did the engineering. You bring the cohort and the curriculum-content review."

### 6.3 CDC CSELS / North Star Data Academy

CDC's Data Academy already exists and ran 1,170 learners through 15 instructor-led trainings in a recent year. It's a workforce-training muscle that's already moving. The pitch: "Plug the genomic-surveillance specialization into Data Academy as an external offering. Our content; your CDC credential overlay."

### 6.4 University R1 capstone programs

Pre-existing infrastructure: ASU SBHSE / IMPACT MS / BME Capstone (per `School of Technology for Public Health copy.md`), Stanford Biodesign, similar elsewhere. Capstone teams already pay industry partners to host capstone projects. JACKPOT Learn becomes a high-quality capstone host.

### 6.5 Forrest / Biodesign academic partnership

Per `docs/immune_platform.md` §15.4 — collaborative grants with Biodesign use ASU-as-lead + Linux Prophet as subaward. The Academy modules become the teaching material for whichever Biodesign course aligns. The empirical-evaluation paper ("Are JACKPOT Academy graduates better prepared?") is a natural co-authored output.

### 6.6 Tribal authority training (NPAIHB, TECs)

This is small-dollar but category-of-one. A CARE-Principles-aligned Academy is *the* deliverable Tribal authorities would adopt. No other pathogen-genomics training platform addresses this. Partnership conversation has to start with listening — `B-CARE-6` in `todo.md` already tracks NPAIHB outreach.

### 6.7 LMIC partnerships (Wellcome, Gates, Rockefeller, CEPI)

The LMIC version of the equity story. A pre-built training platform with on-prem deployment, signed credentials, and an existing curriculum is a credible Gates Foundation / Wellcome / CEPI grant proposal. Tied to the IPSN partnership above.

---

## 7. Sustainability fit

This is the load-bearing answer to "how does JACKPOT Learn make money without breaking the equity story."

The tier model from the legacy sketch (`docs/archived/jackpot_ais_legacy.md` "Sustainability model") — restated with cleaner edges:

| Tier | Audience | Pricing posture | What's included |
|---|---|---|---|
| **Free** | Individual learners, LMIC labs, sovereign deployments | $0 | All Academy modules; all Field Edition cases (current season delayed by one week); local single-player SENTINEL; observer access to WILDFIRE |
| **Cell** | Curious enthusiasts, small teams who want competitive play | Modest subscription | Cloud-hosted tenant, real-time mission drops, federation membership for SENTINEL/WILDFIRE play, leaderboard placement |
| **Edu** | Universities, training programs, individual instructors | Per-cohort or per-seat license | Classroom pack, instructor dashboard, custom-mission authoring tools, scheduled live ops, LMS integration (LTI 1.3) |
| **Partner** | Public-health agencies, federal sponsors, IPSN, foundation-funded LMIC programs | Enterprise / framework agreement | All of the above + co-developed curriculum, branded deployment, accreditation/credential overlays, dedicated maintainer time |

All revenue after costs flows back into platform development. AGPL forever. Free tier is uncapped — there's no "after 30 days you have to pay" gate. The Cell tier is real-money but exists primarily for the small fraction of enthusiasts who *want* the live, social experience.

The economic model assumes the Partner tier carries the platform. Cell + Edu cover marketing and community. Free is the equity story and the recruiting funnel.

### 7.1 What this is NOT

- It is not a paywall over the curriculum
- It is not a paywall over signed credentials
- It is not a paywall over case content
- It is not a paywall over the synthetic data generator

It IS a paywall over: hosted compute, live-ops staff time, instructor dashboards, custom curriculum development, branded deployments. Things that consume actual maintainer or operator time per customer.

---

## 8. Build sequence

The legacy sketch (`docs/archived/jackpot_ais_legacy.md`) recommended SENTINEL first. The reasoning in that doc is sound: easiest grant sell, most replayable, best federation showcase, most credible as real workforce training. But that recommendation pre-dates the spine framing.

With the spine framing, the recommended sequence shifts slightly:

### Phase 1 — Spine (after P0e ships)

Before any face ships, the ten spine elements have to be at v0.1. Roughly 6–9 months of part-time work or 3 months of dedicated work.

```
1. Real JACKPOT tenants for Learn          (already exists; needs tenant template)
2. Synthetic data generator                (Nextflow workflow + answer-key recorder)
3. Scenario YAML format                    (LinkML schema + validator)
4. Six-stage pedagogical pattern           (PEDAGOGY.md + module template)
5. Tenant-per-face deployment              (Helm overlays per face)
6. Signed credentials                      (JWT issuer + Sigstore bundle)
7. Mission framework                       (FastAPI router + evaluator)
8. Contributor PR model                    (cases/ structure + CONTRIBUTING-cases.md)
9. Governance inheritance                  (governance/learn-addendum.md)
10. AGPL applies uniformly                 (no work; existing LICENSE covers it)
```

### Phase 2 — Academy v0.1 + Field Edition Cases 1–3

Run in parallel after spine v0.1 lands. Both are Streamlit-only, no real-time required.

- Academy: 4 modules from Track A (Defenders), one full assessment loop, badge issuance, instructor view
- Field Edition: 3 cases with full narrative wrappers, save state, "next case" recommender

The pitch by month 12 from start: "Try Field Edition right now. If you like it, you can keep going in the Academy."

### Phase 3 — SENTINEL v0.1

This is where the React app comes in. Build `sentinel/` as a separate frontend that talks to the existing FastAPI backend (per the recommended Option 2 in `docs/archived/jackpot_ais_legacy.md`).

Single season (S1: Patient Zero), classroom cohort beta. Target: one paying Edu-tier partner (APHL workshop? university semester pilot?).

### Phase 4 — WILDFIRE v0.1

Build on the SENTINEL React app — different game logic, same engine. Single competitive season (S1 with adversarial mechanics). Target: a research-community beta of ~10 cells.

### Phase 5 — Subsequent seasons + Academy Tracks B & C

By this point the platform is real, the community is growing, and we have evidence about which faces deserve more investment. Sequel-season cadence is one season per face every 6–9 months.

The whole thing is realistically an 18–24 month arc from "P0e ships" to "all four faces have v0.1 in the wild." That fits the existing roadmap horizon and doesn't require a heroic effort.

---

## 9. What we won't build

Stating the negative explicitly because each of these has been a temptation in past discussions:

1. **A generic LMS.** Moodle, Canvas, Open edX exist. We don't compete with them. We *integrate* with them via LTI 1.3 (Edu tier).
2. **A licensure body.** We issue micro-credentials. We do not issue ABMM or ABMLI or equivalent licensure. We *partner* with bodies that do.
3. **Wet-lab gating.** Per the legacy sketch's reframe (`docs/archived/jackpot_ais_legacy.md`) — the wet-lab "Reference Standard" kit is optional and entirely free at the individual level. Wet-lab tier is funded by institutions, never by the player.
4. **A general-purpose game platform.** The four faces are public-health-surveillance-specific. We're not building Plague Inc.; we're using Plague-Inc.-like mechanics in service of credentialed learning.
5. **Closed-content / paywalled curriculum.** All cases and modules ship AGPL / CC-BY-SA. Revenue is on hosted operations, not on content.
6. **A GISAID for training data.** Every learner contribution is openly licensed back to the platform. No data sequestration.
7. **Real-time scoring against ongoing outbreaks.** Live ops uses synthetic data with delayed-real-data inputs where appropriate. We never gamify a real epidemic in real time. Ethics + safety floor.
8. **AI-content firehose.** LLM-generated case content goes through human-author review before going live. No auto-generated season drops.

---

## 10. Success criteria

What does "this worked" look like?

### 10.1 12-month signals (post-P0e + spine work)

- Spine v0.1 shipped: scenario YAML schema, synthetic data generator, credential issuer, mission framework all working end-to-end
- Academy v0.1 with 4 modules from Track A, one cohort of ≥10 learners completed
- Field Edition v0.1 with 3 cases, ≥100 distinct players completed at least Case 1
- At least one paying Edu-tier partner (a university or training program)
- At least one external contributor PR merged for a case or module

### 10.2 24-month signals

- SENTINEL v0.1 in classroom beta at ≥3 institutions
- ≥30 Academy modules across Tracks A and B
- ≥12 Field Edition cases
- A workforce-empirical-evaluation manuscript submitted (the Academy paper from `docs/immune_platform.md` §15.3)
- APHL or CDC CSELS expressed interest in Partner-tier framework

### 10.3 36-month signals

- WILDFIRE v0.1 with ≥10 cells running
- ≥3 Partner-tier deployments (state PHA + university + LMIC equivalent)
- Academy Track C with ≥5 named module Architects
- ≥3 peer-reviewed papers citing JACKPOT Learn outputs
- A Tribal authority deployment of the Academy (Scenario A with sovereignty-aligned runtime policies enabled and CARE compliance verified — see `docs/architecture.md` §22)
- The Academy generates a recognizable career path: "I trained in JACKPOT Learn" is something a hire writes on their resume

---

## 11. Risks

Honest list of what could go wrong:

| Risk | Severity | Mitigation |
|---|---|---|
| **Live-ops volunteer burnout** | High — the doc explicitly mentions weekly story beats. One person doing live ops indefinitely doesn't scale. | Build live-ops responsibility into Partner-tier contracts. No partner = no real-time season; pre-recorded async-style cases instead. |
| **Synthetic data plausibility** | Medium — learners and players can tell when bioinformatics tools give "tutorial outputs" vs. real-feeling ones. | Synthetic data generated from real reference genomes via `wgsim`/`badread`/`ART` with realistic error profiles. Answer keys but believable noise. |
| **Real-time UI scaling** | Medium — Streamlit can't do multiplayer real-time; React/WebSockets work but are infra to maintain. | The phasing in §8 explicitly defers real-time UI until Phase 3 (SENTINEL). Don't build it speculatively. |
| **Credential portability** | Medium — signed JWTs are great in theory; in practice, employers need easy verification UX. | OIDC + a public verification web page from day one. LTI 1.3 for LMS integration as Edu-tier feature. |
| **Cases adjacent to ongoing outbreaks** | High — gamifying a real, ongoing pandemic is an ethics violation. | Editorial moratorium policy on cases that map to active outbreaks. 12-month cooling-off period; sensitivity review before publication. |
| **Adversarial content drift** | Medium — WILDFIRE community could push into edgelord territory if unmoderated. | Code of Conduct from day one; case licensing terms require non-harmful framing; live-ops can pull cases. |
| **AGPL-vs-derivative-license tension on cases** | Low — cases are content, not code. | Cases are CC-BY-SA, code is AGPL; documented clearly in `LICENSE-cases.md`. Resolves any ambiguity. |
| **Forrest framing tied to one researcher** | Medium — Forrest's lab is a partnership, not a dependency. If the partnership doesn't materialize, the framing should still hold. | The integration thesis works without Forrest specifically. Cite the framing's origin; the framing's substance is JACKPOT-internal. |
| **The Cell tier doesn't generate enough revenue to justify hosting costs** | Medium — typical small-niche-subscription failure mode. | Cell tier is *not* the revenue engine. Partner tier is. Cell tier is a community/marketing surface. Price it to roughly break even on hosting, not to fund development. |
| **Case content becomes stale faster than we can replace it** | High — every season needs fresh cases; the maintenance treadmill is the dominant long-run cost. | Open contributor model (PR-driven case authoring) is mandatory, not optional. Community generates ≥50% of cases by Year 2 or the model fails. |

---

## 12. Open questions

Things that need answers before real implementation but don't need them now:

1. **Should JACKPOT Learn have a separate brand or be just JACKPOT?** Same monorepo, same governance, but is it `learn.jackpot.example` or `jackpot.example/academy`? Branding affects partnership conversations.
2. **LTI 1.3 vs SCORM vs neither for LMS integration?** Edu-tier feature, but which standard is more aligned with university IT teams in 2026?
3. **What's the canon policy across faces?** Does a pathogen in Field Edition Case 02 exist in the WILDFIRE S2 canon? If yes, who owns continuity? If no, do we explicitly disclaim it?
4. **Should Academy modules support multiple languages from day one?** WHO IPSN positioning strongly suggests yes — but translation is real work. English-first with i18n affordances vs. multilingual-from-day-one is a real cost decision.
5. **What's the relationship between JACKPOT Learn and Anthropic-style "skills"?** The `SKILL.md` pattern in the existing course directory hints at a convergence. Worth deciding before module count scales.
6. **What's the relationship to existing CTF infrastructure (CTFd, picoCTF)?** Could we reuse their scoreboard infra for WILDFIRE rather than building it?
7. **Are credentials chain-of-trust to anything?** A "JACKPOT Defender Level 1" badge from a self-issued JWT is real, but a "JACKPOT Defender Level 1" badge co-signed by APHL is realer.

---

## 13. The pitch in three sentences

> JACKPOT Learn is the educational platform layer of JACKPOT — four learner-facing experiences (structured Academy, solo Field Edition, cooperative SENTINEL, competitive WILDFIRE) running on one shared spine of real JACKPOT tenants, synthetic data, signed credentials, and an open-contribution mission framework. Every learner contribution flows back into the production surveillance platform, every credential is cryptographically verifiable, and the whole thing stays AGPL so the WHO-IPSN equity audience never gets gated by license. We don't compete with APHL, CDC CSELS, or Software Carpentry — we make all of them more effective by being the platform their fellows train on.

---

## Appendix A — Cross-references

| Question | Where to look |
|---|---|
| What does a learner actually do in each face? | `jackpot_learn_curriculum_design.md` §3, §4, §5, §6 |
| What modules are in the Academy? | `jackpot_learn_curriculum_design.md` §3 |
| What cases are in Field Edition? | `jackpot_learn_curriculum_design.md` §4 |
| What seasons are in SENTINEL? | `jackpot_learn_curriculum_design.md` §5 |
| What seasons are in WILDFIRE? | `jackpot_learn_curriculum_design.md` §6 |
| Why workforce-as-platform? | This doc §2 |
| Why these four faces and not others? | This doc §3, `docs/archived/jackpot_ais_legacy.md` Parts 3–4 (legacy sketch), `docs/immune_platform.md` §§7-8 (current framing) |
| How does this make money? | This doc §7 |
| When does this ship? | This doc §8 |
| What partnerships matter? | This doc §6 |
| Original Forrest framing | `docs/immune_platform.md` §18.5 (was: standalone collaboration scaffolding §7, now merged in) |
| Original four-faces sketch | `docs/archived/jackpot_ais_legacy.md` Part 4 (Quick Reference) |
| Original Academy curriculum | `docs/immune_platform.md` §7 (Pillar IV — Training as First-Class Citizen) |
| Original privacy-preserving track | `docs/archived/jackpot_ais_legacy.md` "Module Lineup" section |

---

## Appendix B — Provenance

This document synthesizes:

- `docs/archived/jackpot_ais_legacy.md` (was `Jackpot_AIS copy.md`) — Parts 1–8, especially the four-faces framing in Part 4 and the costing/agency pitches in Parts 8–9
- `docs/immune_platform.md` (was `jackpot_immune_platform_plan copy.md`) — §7 (Academy as pillar IV) and §8 (Gaming as pillar V)
- `docs/immune_platform.md` Part 2 (was `jackpot_immune_collaboration_scaffolding_orig copy.md` §7) — the Forrest framing meta-module
- `jackpot_strategic_vision_may_2026 copy.md` — adopter-segment analysis and peacetime-utility framing
- `docs/platform_landscape.md` — Pathoplexus governance pattern, AGPL strategic asset rationale, sustainability-funding archetypes
- `Attributesential.pdf` — WHO/IPSN Attribute 12 (Sustainability) framework
- `North_Star_CDCSummit_092723.pdf` — CDC Data Academy precedent
- `Accelerating the Use of Pathogen Genomics and Metagenomics in Public Health (2025).pdf` — APHL-CDC Bioinformatics Fellowship benchmarks, PGCoE modular-training pattern

This is design synthesis, not new claims. Anywhere this document goes beyond the source material is flagged with an open question in §12.
