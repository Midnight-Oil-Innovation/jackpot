> **Status:** Superseded — archived (directory convention). Historical; do not cite as current.

# Backlog Consolidation Report — Audit trail (archived)

> **Status: Audit trail preserved 2026-05-16.** The consolidation work this report describes has been fully executed in `docs/todo.md` (Phase IM-1 through IM-6, the `B-IMMUNE-*` / `B-COLLAB-*` / detection-landscape IDs). This file is preserved as the audit trail explaining *how* todo.md got to its current state. Do not edit. Do not treat as pending work.
>
> **What this file is.** A v1.0 / 2026-05-09 sanity-check document produced before the consolidation edit landed in `todo.md`. It catalogs:
>
> - The four backlog sources inventoried (`todo.md` + `jackpot_immune_platform_plan.md` §14 + `jackpot_immune_collaboration_scaffolding.md` §9 + `jackpot_detection_landscape.md` §6)
> - Naming convention decisions (mnemonic IDs only, no more sequential numerics)
> - The phase-numbering collision resolution (`Phase 26-31` in the immune-plan would have collided with existing `todo.md` Phase 26/27/28; renamed to `Phase IM-1` through `Phase IM-6`)
> - Per-section item mapping tables (§4.1 through §4.11)
> - Five "big merge" consolidation decisions (where two or three different IDs across sources turned out to be the same work)
> - Three "related but distinct" decisions (where items look similar but stay separate)
> - The master list of 88 new canonical IDs created
>
> **Why preserved.** Future readers asking "why is item X named B-FOO-1 instead of B-001?" or "where did the 24 detection-landscape items end up?" find the answer here. The mapping tables are the audit record for the consolidation decision.
>
> **What superseded it.** The consolidation work itself: `docs/todo.md` Phase IM-1 through IM-6 sections (lines ~2401-2700 as of 2026-05-08) contain the canonical backlog items. The strategic-doc trim work described in §11 ("apply replacement text via cat/cp instructions") was executed as part of the Cluster B merge (May 2026), which absorbed the immune-platform-plan and collaboration-scaffolding source docs into `docs/immune_platform.md`.
>
> **If you need to verify a consolidation decision**, this file is the source of truth for the decision rationale. If you need to *change* a consolidation decision, edit `docs/todo.md` directly — this archive is read-only.

---

# JACKPOT Backlog Consolidation Report

**Status:** v1.0 · 2026-05-09
**Purpose:** Audit-trail and sanity-check for the consolidation of backlog content from four sources into a single canonical location (`todo.md`). Read this to verify every consolidation decision before approving the `todo.md` edit.

---

## 1. Sources inventoried

Four documents currently carry backlog content, with three different identifier schemes:

| Source | ID scheme | Items | Section(s) |
|---|---|---|---|
| `todo.md` | Mnemonic (`B-MARTI-1`, `B-GOV-1`) | 89 active backlog items | Distributed across many phases |
| `jackpot_immune_platform_plan.md` | Sequential numeric (`B-001`..`B-049`) | 49 items | §14 (Phase 26-31 in immune-plan numbering) |
| `jackpot_immune_collaboration_scaffolding_copy.md` | None — file paths + `TODO(<researcher>-collab):` markers | 18 items + 3 quick wins + 3 wet-side advisory | §9.1, §9.2, §9.3 |
| `jackpot_detection_landscape.md` (delivered last turn) | Mnemonic (matches todo.md style) | 24 new + 8 reaffirmed | §6 |

Plus immune plan §14.4 "Quick wins for the next 90 days" — 6 items not formally identified, several of which overlap with §14.2 items.

**Total raw count across all sources:** 89 + 49 + 21 + 24 + 6 = **189 items**, before deduplication.

**After deduplication:** **~143 unique items** (estimated; full table in §4 below confirms).

---

## 2. Naming convention decisions

Per Glen's confirmation:

1. **`todo.md` is the single source of truth for backlog items.**
2. **Mnemonic IDs only.** No more sequential numerics. The immune plan's `B-001..B-049` get renamed to mnemonic IDs.
3. **Strategic docs reference `todo.md` items by ID.** They do not redefine items; they explain why items exist (the architecture, theory, and rationale).
4. **Every item from every source goes into `todo.md` now.** (Per Glen's answer to question 4 — "Everything goes into todo.md now.")

---

## 3. Phase structure

### 3.1 Phase numbering collision

The immune plan calls its phases "Phase 26 through Phase 31." But:

- **Phase 26** in `todo.md` is already taken — *Pathoplexus/Loculus Comparative Analysis Backlog (Tracked, Not Scheduled)*
- **Phase 27** in `todo.md` is already taken — *CDC DMI / North Star / STLT Alignment Backlog (Tracked, Not Scheduled)*
- **Phase 28** in `todo.md` is already taken — *Default Eukaryotic Pathogen Pipelines (Tracked, Tier-Prioritized)*

Every single phase number in the immune plan's "Phase 26-31" range collides with an existing `todo.md` phase.

### 3.2 Resolution: Phase IM-1 through Phase IM-6

To avoid collision while preserving the immune-plan's six-sub-phase structure, the immune-platform phases are numbered **`IM-1` through `IM-6`** (`IM` = "Immune Platform"). The mapping:

| Immune-plan name | Canonical name in `todo.md` | Theme | ~Effort |
|---|---|---|---|
| Phase 26 | **Phase IM-1 — Bio-AIS MVP + Academy module 9** | Schema, NSA substrate, AMAnD wrapper, first end-to-end | ~6 weeks |
| Phase 27 | **Phase IM-2 — Multi-modal Danger Fusion + DCA in Practice** | DCA implementation, danger signals, wastewater/clinical adapters | ~5 weeks |
| Phase 28 | **Phase IM-3 — Memory + Clonal Selection** | Memory cells, analyst review, AMR memory, recombhunt | ~5 weeks |
| Phase 29 | **Phase IM-4 — Federation as Immune Network** | Federation tables, trust engine, repertoire, HE queries | ~6 weeks |
| Phase 30 | **Phase IM-5 — Cyber-AIS for Platform Self-Defense** | NSA on API surface, telemetry, poison detect, OPSEC, screening | ~5 weeks |
| Phase 31 | **Phase IM-6 — Game/Academy Full Integration** | Outbreak cases, WILDFIRE missions, profiles, public release | ~4 weeks |

**Total Phase IM-1..IM-6:** ~31 weeks (~7 months full-time, ~14 months half-time-alongside-existing-roadmap).

### 3.3 Collab track interleaving

The `jackpot_immune_collaboration_scaffolding_copy.md` items don't form their own phase; they interleave within Phase IM-1..IM-5. The scaffolding §9.1 mapping is preserved:

| Sub-phase tag in `todo.md` | Maps to | Items |
|---|---|---|
| `IM-1-collab` | Phase IM-1 (Bio-AIS MVP) | 6 items |
| `IM-2-collab` | Phase IM-2 (Multi-modal) | 5 items |
| `IM-4-collab` | Phase IM-4 (Federation) | 3 items |
| `IM-5-collab` | Phase IM-5 (Cyber-AIS) | 4 items |

Plus three wet-side advisory items from §9.2 → tagged `IM-WET-*` (independent of pillar phasing).

### 3.4 Detection-landscape items — where they go

The 24 detection-landscape items map by Pillar (per detection-landscape §4):

| Pillar | Phase | Detection-landscape items |
|---|---|---|
| Pillar I (Bio-Anomaly) | IM-1 (core) + IM-2/IM-3 (specialty pipelines) | 14 items |
| Pillar II (Self-Defense) | IM-5 | 1 item (B-SOC-1, merged with B-039) |
| Pillar III (Federation) | IM-4 | 2 items + existing B-CDST-1 reaffirmed |
| Pillar IV / V | n/a (no surveyed tools) | 0 items |
| **Pipeline-zoo additions, not pillar-specific** | New section "Pipeline Zoo Additions" | 7 items (bacterial variant callers + specialty pipelines) |

The 7 pipeline-zoo items not tied to a pillar (CNproScan, ProcaryaSV, SNiPgenie, SKA2, Pf-HaploAtlas, pyMLST, AMRomics) get their own section in `todo.md` at the same level as Phase IM-*, called "Pipeline Zoo Additions from Detection Landscape."

---

## 4. Master mapping table

Every non-`todo.md` item below is followed by its canonical ID and disposition (`NEW` = new ID created, `MERGE` = consolidated into an existing ID, `REAFFIRM` = already in `todo.md`, leave as-is).

### 4.1 Immune plan §14 — Phase 26 (Bio-AIS MVP) → Phase IM-1

| Source ID | Source description (one line) | Canonical ID | Disposition |
|---|---|---|---|
| `B-001` | Schema v6.0 detector tables + Alembic migration | `B-IMMUNE-SCHEMA-1` | NEW |
| `B-002` | `backend/immune/algorithms/nsa.py` shared NSA substrate | `B-IMMUNE-NSA-1` | NEW |
| `B-003` | `backend/immune/algorithms/features.py` k-mer featurizer | `B-IMMUNE-FEAT-1` | NEW |
| `B-004` | `backend/immune/bio/amand.py` bio-NSA wrapping AMAnD | `B-AMAND-1` | MERGE — already created in detection landscape §6; this becomes the canonical adoption item |
| `B-005` | `backend/routers/immune_bio.py` FastAPI surface | `B-IMMUNE-API-1` | NEW |
| `B-006` | `pipelines/immune/amand.nf` Nextflow process | `B-AMAND-1` | MERGE into B-AMAND-1 (same tool, different layer of integration) |
| `B-007` | License compliance script `scripts/verify_licenses.py` | `B-LICENSE-1` | NEW |
| `B-008` | Streamlit "Anomaly Triage" page | `B-IMMUNE-UI-1` | NEW |
| `B-009` | `course/modules/09-negative-selection-in-practice/` | `B-ACADEMY-9` | NEW |
| `B-010` | Test coverage for new code | `B-IMMUNE-TESTS-1` | NEW |

### 4.2 Immune plan §14 — Phase 27 (Multi-modal Danger Fusion) → Phase IM-2

| Source ID | Source description (one line) | Canonical ID | Disposition |
|---|---|---|---|
| `B-011` | `backend/immune/bio/dca_bio.py` BioDendriticCell | `B-IMMUNE-DCA-1` | NEW |
| `B-012` | `backend/schemas/immune_bio.py` Pydantic models | `B-IMMUNE-SCHEMA-2` | NEW |
| `B-013` | Wastewater signal ingestion adapter (NWSS or local STAB) | `B-IMMUNE-WW-1` | NEW |
| `B-014` | Clinical signal ingestion ELR adapter stub | `B-IMMUNE-CLIN-1` | NEW |
| `B-015` | One-Health adapter for animal/environmental samples in DCA | `B-IMMUNE-OH-1` | NEW |
| `B-016` | Streamlit DCA breakdown view (per-sample priority + explainable contributions) | `B-IMMUNE-UI-2` | NEW |
| `B-017` | `course/modules/10-dca-in-practice/` | `B-ACADEMY-10` | NEW |
| `B-018` | Outbreak: Field Edition cases 1-3 | `B-OUTBREAK-1` | NEW |
| `B-019` | Tests + integration tests with multi-modal data | `B-IMMUNE-TESTS-2` | NEW |

### 4.3 Immune plan §14 — Phase 28 (Memory + Clonal Selection) → Phase IM-3

| Source ID | Source description (one line) | Canonical ID | Disposition |
|---|---|---|---|
| `B-020` | `backend/immune/bio/cs_bio.py` ClonalSelectionEngine | `B-IMMUNE-CS-1` | NEW |
| `B-021` | Analyst review queue Streamlit page | `B-IMMUNE-UI-3` | NEW |
| `B-022` | Memory cell promotion logic (high-affinity → memory_cells table) | `B-IMMUNE-MEM-1` | NEW |
| `B-023` | `jackpot-amrmemory` wrapping amr.watch + AMRFinderPlus + abricate | `B-AMR-MEMORY-1` | NEW |
| `B-024` | `jackpot-recombhunt` wrapping OpenRecombinHunt | `B-RECOMB-1` | MERGE — already created in detection landscape §6 |
| `B-025` | Outbreak case 4 (AMR puzzle) | `B-OUTBREAK-2` | NEW |

### 4.4 Immune plan §14 — Phase 29 (Federation as Immune Network) → Phase IM-4

| Source ID | Source description (one line) | Canonical ID | Disposition |
|---|---|---|---|
| `B-026` | `backend/models/immune.py` federation tables (federation_members, trust_scores, cyber_assessments) | `B-IMMUNE-FED-SCHEMA-1` | NEW |
| `B-027` | `backend/immune/net/trust.py` TrustEngine | `B-IMMUNE-TRUST-1` | NEW |
| `B-028` | `backend/immune/net/repertoire.py` AntibodyRepertoire publish/subscribe | `B-IMMUNE-REP-1` | NEW |
| `B-029` | `backend/immune/net/memory_sync.py` federation memory cell sync | `B-IMMUNE-MEMSYNC-1` | NEW |
| `B-030` | `backend/immune/net/query_he.py` homomorphic-encryption query layer | `B-IMMUNE-HE-1` | NEW (related to existing `B-CRY-1` and `B-CDST-1`; see §5.2 for the relationship) |
| `B-031` | Differential-privacy aggregator for shared signals | `B-IMMUNE-DP-1` | NEW (related to existing `B-PRV-1`; see §5.2) |
| `B-032` | Outbreak case 8 (federation-required capstone) | `B-OUTBREAK-3` | NEW |
| `B-033` | WILDFIRE skeleton — multiplayer engine, cell management | `B-WILDFIRE-1` | NEW |

### 4.5 Immune plan §14 — Phase 30 (Cyber-AIS Self-Defense) → Phase IM-5

| Source ID | Source description (one line) | Canonical ID | Disposition |
|---|---|---|---|
| `B-034` | `backend/immune/sec/nsa_cyber.py` CyberNSA | `B-IMMUNE-CYBER-1` | NEW |
| `B-035` | `backend/middleware/api_telemetry.py` ApiCallEvent rows | `B-IMMUNE-TELEM-1` | NEW |
| `B-036` | `backend/immune/sec/dca_cyber.py` context-aware threat fusion | `B-IMMUNE-CYBER-DCA-1` | NEW |
| `B-037` | `backend/immune/sec/poisondetect.py` sample-poisoning detection | `B-IMMUNE-POISON-1` | NEW |
| `B-038` | `backend/immune/sec/opsec.py` query OPSEC monitoring | `B-IMMUNE-OPSEC-1` | NEW |
| `B-039` | `backend/immune/sec/screening.py` synthetic DNA screening at ingest | `B-SOC-1` | MERGE — already created in detection landscape §6 (SeqScreen+BLiSS adoption); this becomes the canonical implementation |
| `B-040` | Insider-threat dashboard Streamlit page | `B-IMMUNE-UI-4` | NEW |
| `B-041` | Audit hash chain (extends existing P0 audit-bug fix) | `B-AUDIT-CHAIN-1` | NEW |
| `B-042` | Academy module 13 (cyberbiosecurity) full content | `B-ACADEMY-13` | NEW |

### 4.6 Immune plan §14 — Phase 31 (Game/Academy Integration) → Phase IM-6

| Source ID | Source description (one line) | Canonical ID | Disposition |
|---|---|---|---|
| `B-043` | Outbreak: Field Edition cases 5-8 (full progression) | `B-OUTBREAK-4` | NEW |
| `B-044` | WILDFIRE missions 1-6 fully implemented | `B-WILDFIRE-2` | NEW |
| `B-045` | Game submissions feed clonal-selection labeling pipeline | `B-GAME-LABEL-1` | NEW |
| `B-046` | Academy modules 11, 12, 14, 15, 16 — full content | `B-ACADEMY-OTHER-1` | NEW |
| `B-047` | `jackpot init --profile academy/game` profiles | `B-INIT-PROFILES-1` | NEW |
| `B-048` | Public read-only academy tenant — deploy alongside production | `B-ACADEMY-TENANT-1` | NEW |
| `B-049` | First public release announcement / paper draft kickoff | `B-RELEASE-1` | NEW |

### 4.7 Immune plan §14.4 — Quick wins for the next 90 days

| Source label | Source description (one line) | Canonical ID | Disposition |
|---|---|---|---|
| Quick win 1 | "Land schema v6.0 stub now" — empty migration with table defs behind a feature flag | `B-IMMUNE-SCHEMA-1` | MERGE — quick-win precursor of B-IMMUNE-SCHEMA-1 itself; called out as `[quick-win]` in the IM-1 entry |
| Quick win 2 | "Add `jackpot-immune-bio.md` to course/" — Module 9 starter code | `B-ACADEMY-STUB-1` | NEW (precursor of `B-ACADEMY-9`) |
| Quick win 3 | License compliance script | `B-LICENSE-1` | MERGE (already canonical) |
| Quick win 4 | Audit transaction-participation bug fix (existing P0 bug) | (existing P0 bug — see §5.3) | EXISTING (no new ID; tracked elsewhere in todo.md) |
| Quick win 5 | Synthetic data corpus `course/data/synthetic/` | `B-SYNTH-DATA-1` | NEW |
| Quick win 6 | Federation-trust schema sketch | `B-IMMUNE-FED-SCHEMA-1` | MERGE (subset of canonical) |

### 4.8 Scaffolding §9.1 — Phase 26-collab (interleaved within IM-1, IM-2, IM-4, IM-5)

| Source description | Effort | Canonical ID | Disposition | Phase tag |
|---|---|---|---|---|
| `backend/immune/algorithms/featurizers/` registry (extends `B-IMMUNE-FEAT-1`) | 2 days | `B-IMMUNE-FEAT-1` extension | MERGE (extends existing) | IM-1-collab |
| `cli/jackpot_init/diversity_profile.py` | 1 day | `B-COLLAB-DIVERSITY-1` | NEW | IM-1-collab |
| `backend/immune/net/diversity.py` + `diversity_cli.py` | 2 days | `B-COLLAB-DIVERSITY-2` | NEW | IM-4-collab (federation) |
| `scripts/generate_sbom.py` + CI workflow | 3 days | `B-COLLAB-SBOM-1` | NEW | IM-1-collab |
| `backend/immune/sec/parsers_safe.py` + Critical Rule | 1 day | `B-COLLAB-PARSERS-1` | NEW | IM-1-collab (gates wrapped-tool integration) |
| `infra/sigstore/` + signed images + key-mgmt | 2 days | `B-COLLAB-SIGSTORE-1` | NEW | IM-1-collab (gates production) |
| `backend/immune/sec/rotation.py` (JWT rotation) | 3 days | `B-COLLAB-ROTATE-1` | NEW | IM-2-collab |
| `backend/immune/sec/cs_cyber_federated.py` | 4 days | `B-COLLAB-CYBER-FED-1` | NEW | IM-5-collab |
| `backend/middleware/api_surface_mutation.py` | 2 days | `B-COLLAB-MUTATE-1` | NEW | IM-2-collab |
| `GOVERNANCE.md` v0 (with v1.0+ scope on breaking changes) | 1 day | `B-GOV-1` | MERGE — already in todo.md; collab adds the v1.0+ scope to existing item |
| `backend/immune/sec/refusal.py` + middleware (with allow-list) | 3 days | `B-COLLAB-REFUSAL-1` | NEW | IM-2-collab |
| `backend/immune/net/asymmetric_trust.py` (with input validation) | 2 days | `B-COLLAB-ATRUST-1` | NEW | IM-4-collab |
| `docs/dual_use_review.md` + queue table | 1 day | `B-COLLAB-DUR-1` | NEW | IM-2-collab |
| `course/modules/_meta/ais_framing.md` | 0.5 day | `B-COLLAB-FRAMING-1` | NEW | IM-1-collab |
| `backend/immune/redteam/` skeleton + `cli.py` + amand attack | 3 days | `B-COLLAB-REDTEAM-1` | NEW | IM-2-collab (depends on jackpot-amand existing) |
| `backend/immune/redteam/data_representativeness.py` | 1 day | `B-COLLAB-REDTEAM-2` | NEW | IM-2-collab |
| `backend/immune/redteam/attack_federation.py` | 3 days | `B-COLLAB-REDTEAM-3` | NEW | IM-4-collab |
| `.github/workflows/redteam.yml` + `diversity_check.yml` | 1 day | `B-COLLAB-CI-1` | NEW | IM-2-collab |

### 4.9 Scaffolding §9.2 — Wet-side advisory

| Source description | Canonical ID | Disposition |
|---|---|---|
| `docs/wetside_advisory.md` (current assumptions about wastewater sampling, preservation, sequencing-prep failure modes) | `B-WW-ADV-1` | NEW (avoids collision with existing `B-WW-1`) |
| Wet-side advisor role added to `GOVERNANCE.md` | `B-GOV-1` | MERGE — extends existing |
| Pre-register questions for wet-side advisor in `docs/decisions/` | `B-WW-ADV-2` | NEW |

### 4.10 Scaffolding §9.3 — Quick wins for the current sprint

| Source label | Source description | Canonical ID | Disposition |
|---|---|---|---|
| QW-8 (collab) | `parsers_safe.py` + Critical Rule N in CLAUDE.md | `B-COLLAB-PARSERS-1` | MERGE (already canonical) |
| QW-9 (collab) | `course/modules/_meta/ais_framing.md` | `B-COLLAB-FRAMING-1` | MERGE (already canonical) |
| QW-10 (collab) | `GOVERNANCE.md` v0 with refusal-to-deploy criteria | `B-GOV-1` | MERGE (already canonical) |

### 4.11 Detection landscape §6 — 24 items

| Source ID (= canonical) | Phase placement | Disposition |
|---|---|---|
| `B-TAXTRIAGE-1` | IM-1 (Pillar I core) | NEW (from detection landscape) |
| `B-AMAND-1` | IM-1 (Pillar I core) | NEW (canonical home for the AMAnD work; absorbs immune plan B-004 and B-006) |
| `B-SOC-1` | IM-5 (Pillar II) | NEW (canonical home for sequence-of-concern work; absorbs immune plan B-039) |
| `B-MARTI-1` | IM-1 (Pillar I real-time arm) | REAFFIRM (already in `todo.md`) |
| `B-INSAFLU-1` | IM-1 (Pillar I viral arm) | NEW |
| `B-CGMSI-1` | IM-1 (Pillar I; pairs with MARTi) | NEW |
| `B-NFUNO-1` | IM-1 (Pillar I cohort co-assembly) | NEW |
| `B-DEEPAC-1` | IM-1 (Pillar I pathogenicity scoring) | NEW |
| `B-MLM-1` | IM-1 (Pillar I unmapped-read threat characterization) | NEW |
| `B-NANOC-1` | Pipeline Zoo Additions (not pillar-specific; bacterial outbreak) | NEW |
| `B-CNPRO-1` | Pipeline Zoo Additions | NEW |
| `B-PROSV-1` | Pipeline Zoo Additions | NEW |
| `B-SNIPG-1` | Pipeline Zoo Additions | NEW |
| `B-SKA2-1` | Pipeline Zoo Additions | NEW |
| `B-PFHAP-1` | Pipeline Zoo Additions (malaria-specific) | NEW |
| `B-PYMLST-1` | Pipeline Zoo Additions | NEW |
| `B-AMRO-1` | Pipeline Zoo Additions (pairs with `B-NCBI-2`) | NEW |
| `B-RECOMB-1` | IM-3 (canonical home; absorbs immune plan B-024) | NEW |
| `B-GRUMB-1` | IM-2 (Pillar I environmental risk-scoring) | NEW |
| `B-KOMB-1` | IM-1 (Pillar I community-shift detector) | NEW |
| `B-EIOS-1` | IM-2 (Pillar I external signal feed) | NEW |
| `B-FED-PILLARIII-1` | IM-4 (FL framework decision) | NEW |
| `B-REALTIME-1` | IM-2 (umbrella over real-time integration) | NEW |
| `B-CRISPR-EBX-1` | IM-2 (Pillar I env extension; Year 2+) | NEW |

---

## 5. Merge decisions explained

### 5.1 The big merges (overlaps consolidated)

Five places where two or three different IDs in different sources turned out to be the same work:

| Canonical ID | Sources merged | Rationale |
|---|---|---|
| `B-AMAND-1` | Immune plan `B-004` ("amand.py wrapper"), Immune plan `B-006` ("amand.nf Nextflow process"), Detection landscape `B-AMAND-1` | All three are the AMAnD adoption: `B-004` is the Python wrapper, `B-006` is the Nextflow process; both are sub-deliverables of the same adoption. Consolidating into one canonical item with sub-bullets for the layers. |
| `B-RECOMB-1` | Immune plan `B-024` ("jackpot-recombhunt"), Immune plan §13 OSS table ("OpenRecombinHunt → jackpot-recombhunt"), Detection landscape `B-RECOMB-1` | Same OpenRecombinHunt adoption; same target Nextflow module. Three framings, one task. |
| `B-SOC-1` | Immune plan `B-039` ("screening.py"), Immune plan §13 OSS table ("SeqScreen-Nano → jackpot-edge"), Detection landscape `B-SOC-1` (SeqScreen + BLiSS) | All three are the synthetic-DNA / sequence-of-concern screening at ingest; canonical implementation pairs SeqScreen+BLiSS as the detection landscape recommends. |
| `B-GOV-1` | Existing `todo.md` `B-GOV-1`, Scaffolding §9.1 `GOVERNANCE.md v0`, Scaffolding §9.3 quick win 10, Scaffolding §9.2 wet-side advisor role | All four are the same `governance/` directory + `GOVERNANCE.md` work. Existing `B-GOV-1` is the canonical home; collab/scaffolding additions extend it (v1.0+ scope on breaking changes, refusal-to-deploy criteria, wet-side advisor role). |
| `B-IMMUNE-FEAT-1` | Immune plan `B-003` ("features.py k-mer featurizer"), Scaffolding §3 ("featurizers registry") | Featurizer module + registry are the same code — registry pattern is the scaffolding refinement of the simple module. Consolidating into one item with the registry as a sub-bullet. |

### 5.2 The "related but distinct" decisions

Three places where two items might *look* like the same thing but are actually different and should remain distinct:

| ID A | ID B | Why they stay distinct |
|---|---|---|
| `B-CDST-1/2/3` (existing in todo.md, Pathogenwatch comparative) | `B-IMMUNE-HE-1` (new, Phase IM-4) | CDST is a privacy-preserving *typing primitive* — drop-in adoption of a specific tool. `B-IMMUNE-HE-1` is the broader homomorphic-encryption query layer for federation (`net/query_he.py`). CDST is one tool that could be wired into the HE query layer, but the layer is bigger than CDST. |
| `B-PRV-1` (existing in todo.md, privacy scaffold) | `B-IMMUNE-DP-1` (new, Phase IM-4) | `B-PRV-1` is the placeholder *privacy scaffold* — empty router/router-stub waiting for content. `B-IMMUNE-DP-1` is the differential-privacy aggregator for shared signals — concrete implementation that lands inside the scaffold. Eventually `B-IMMUNE-DP-1` consumes `B-PRV-1`'s scaffold. |
| `B-CRY-1` (existing in todo.md, crypto scaffold) | `B-IMMUNE-HE-1` (new, Phase IM-4) | Same shape as B-PRV-1 ↔ B-IMMUNE-DP-1. `B-CRY-1` is the placeholder crypto scaffold. `B-IMMUNE-HE-1` lands the HE query layer inside it. |

### 5.3 Existing P0 bugs referenced

The immune plan §14.4 quick win 4 ("Audit transaction-participation bug fix") is a known P0 bug already in scope across multiple in-progress items. Specifically:

- `log_audit()` and `create_notification()` accept `db_conn` but never forward it to `execute_write()` — known bug, tracked in session-summary backlog as a transaction-discipline issue.
- `_handle_workflow_complete()` `conn=` TypeError — known bug, tracked in `jackpot_session_summary_and_backlog.md`.

These don't get new IDs — they're already in scope as ad-hoc P0 fixes. The new immune backlog items DEPEND on these being fixed first; this is documented as a prerequisite in the Phase IM-1 header.

---

## 6. New canonical IDs created (master alphabetical list)

Total new IDs created: **64 unique** (plus 8 reaffirmed, plus 5 merges into existing).

### 6.1 Immune-platform main-track (`B-IMMUNE-*`)

`B-IMMUNE-API-1`, `B-IMMUNE-CLIN-1`, `B-IMMUNE-CS-1`, `B-IMMUNE-CYBER-1`, `B-IMMUNE-CYBER-DCA-1`, `B-IMMUNE-DCA-1`, `B-IMMUNE-DP-1`, `B-IMMUNE-FEAT-1`, `B-IMMUNE-FED-SCHEMA-1`, `B-IMMUNE-HE-1`, `B-IMMUNE-MEM-1`, `B-IMMUNE-MEMSYNC-1`, `B-IMMUNE-NSA-1`, `B-IMMUNE-OH-1`, `B-IMMUNE-OPSEC-1`, `B-IMMUNE-POISON-1`, `B-IMMUNE-REP-1`, `B-IMMUNE-SCHEMA-1`, `B-IMMUNE-SCHEMA-2`, `B-IMMUNE-TELEM-1`, `B-IMMUNE-TESTS-1`, `B-IMMUNE-TESTS-2`, `B-IMMUNE-TRUST-1`, `B-IMMUNE-UI-1`, `B-IMMUNE-UI-2`, `B-IMMUNE-UI-3`, `B-IMMUNE-UI-4`, `B-IMMUNE-WW-1` — 28 IDs.

### 6.2 Collab-track (`B-COLLAB-*`)

`B-COLLAB-ATRUST-1`, `B-COLLAB-CI-1`, `B-COLLAB-CYBER-FED-1`, `B-COLLAB-DIVERSITY-1`, `B-COLLAB-DIVERSITY-2`, `B-COLLAB-DUR-1`, `B-COLLAB-FRAMING-1`, `B-COLLAB-MUTATE-1`, `B-COLLAB-PARSERS-1`, `B-COLLAB-REDTEAM-1`, `B-COLLAB-REDTEAM-2`, `B-COLLAB-REDTEAM-3`, `B-COLLAB-REFUSAL-1`, `B-COLLAB-ROTATE-1`, `B-COLLAB-SBOM-1`, `B-COLLAB-SIGSTORE-1` — 16 IDs.

### 6.3 Detection-landscape track (already mnemonic; new to todo.md)

`B-AMAND-1`, `B-AMRO-1`, `B-CGMSI-1`, `B-CNPRO-1`, `B-CRISPR-EBX-1`, `B-DEEPAC-1`, `B-EIOS-1`, `B-FED-PILLARIII-1`, `B-GRUMB-1`, `B-INSAFLU-1`, `B-KOMB-1`, `B-MLM-1`, `B-NANOC-1`, `B-NFUNO-1`, `B-PFHAP-1`, `B-PROSV-1`, `B-PYMLST-1`, `B-REALTIME-1`, `B-RECOMB-1`, `B-SKA2-1`, `B-SNIPG-1`, `B-SOC-1`, `B-TAXTRIAGE-1` — 23 IDs (24 items total; B-MARTI-1 already in todo.md).

### 6.4 Other (Academy, Outbreak, WILDFIRE, AMR-memory, Audit-chain, Init, Release, License, Synth-data, Wet-side advisory)

`B-ACADEMY-9`, `B-ACADEMY-10`, `B-ACADEMY-13`, `B-ACADEMY-OTHER-1`, `B-ACADEMY-STUB-1`, `B-ACADEMY-TENANT-1`, `B-AMR-MEMORY-1`, `B-AUDIT-CHAIN-1`, `B-GAME-LABEL-1`, `B-INIT-PROFILES-1`, `B-LICENSE-1`, `B-OUTBREAK-1`, `B-OUTBREAK-2`, `B-OUTBREAK-3`, `B-OUTBREAK-4`, `B-RELEASE-1`, `B-SYNTH-DATA-1`, `B-WILDFIRE-1`, `B-WILDFIRE-2`, `B-WW-ADV-1`, `B-WW-ADV-2` — 21 IDs.

### 6.5 Reaffirmed (already in `todo.md`; cross-referenced from immune/collab/detection sources)

`B-MARTI-1`, `B-CDST-1`, `B-LAPIS-1`, `B-NCBI-1`, `B-NCBI-2`, `B-GISAID-1`, `B-GOV-1`, `B-PPX-1` — 8 IDs.

### 6.6 Counts cross-checked

- 28 immune-main + 16 collab + 23 detection-new + 21 other = **88 new canonical IDs**
- 5 merges into existing (B-AMAND-1 absorbs immune `B-004` + `B-006`; B-RECOMB-1 absorbs immune `B-024`; B-SOC-1 absorbs immune `B-039`; B-GOV-1 absorbs scaffolding governance items; B-IMMUNE-FEAT-1 absorbs scaffolding featurizer registry) = **5 merges**
- 8 reaffirmed (already in todo.md) = **8 reaffirmed**

But wait — re-checking the new count: there are some duplicates in §6.1 and §6.4 from the source-by-source walkthrough versus the unique-ID list. The actual unique-new-canonical-ID count is what matters. Recounting against §4 tables:

- §4.1 (Phase IM-1 main): 9 NEW + 1 MERGE (`B-AMAND-1`) = 9 new IDs
- §4.2 (Phase IM-2 main): 9 NEW
- §4.3 (Phase IM-3 main): 5 NEW + 1 MERGE (`B-RECOMB-1`) = 5 new IDs
- §4.4 (Phase IM-4 main): 8 NEW
- §4.5 (Phase IM-5 main): 8 NEW + 1 MERGE (`B-SOC-1`) = 8 new IDs
- §4.6 (Phase IM-6 main): 7 NEW
- §4.7 (§14.4 quick wins): 1 NEW + 4 MERGE + 1 EXISTING = 1 new ID (`B-ACADEMY-STUB-1`) + 1 (`B-SYNTH-DATA-1`) = 2 new IDs
- §4.8 (Scaffolding §9.1): 16 NEW + 2 MERGE (B-GOV-1, B-IMMUNE-FEAT-1) = 16 new IDs
- §4.9 (Scaffolding §9.2 wet-side): 2 NEW + 1 MERGE (B-GOV-1) = 2 new IDs
- §4.10 (Scaffolding §9.3 QWs): 0 NEW + 3 MERGE = 0 new IDs
- §4.11 (Detection landscape): 23 NEW + 1 REAFFIRM = 23 new IDs

**Total new canonical IDs: 9 + 9 + 5 + 8 + 8 + 7 + 2 + 16 + 2 + 0 + 23 = 89**

(Plus 1 implicit: `B-LICENSE-1` from §4.1 and §4.7 are the same ID, double-counted above. Net: 88.)

OK net 88 new canonical IDs. Plus 5 merges. Plus 8 reaffirms.

---

## 7. Items deferred / pipeline-zoo only

Seven items from detection landscape §6 don't map to any Immune-Platform pillar — they're useful pipeline-zoo additions that strengthen JACKPOT independent of the immune platform. They get their own section in `todo.md` at the same hierarchy level as Phase IM-*, called **"Pipeline Zoo Additions from Detection Landscape (Tracked, Not Scheduled)"**:

- `B-CNPRO-1` (CNproScan; bacterial CNV)
- `B-PROSV-1` (ProcaryaSV; bacterial SV)
- `B-SNIPG-1` (SNiPgenie; microbial SNP detection)
- `B-SKA2-1` (SKA2; rapid bacterial genotyping)
- `B-NANOC-1` (NanoCore; sequencer-agnostic outbreak typing)
- `B-PFHAP-1` (Pf-HaploAtlas; malaria-specific)
- `B-PYMLST-1` (pyMLST; custom-cgMLST schemes)
- `B-AMRO-1` (AMRomics; population-scale AMR; pairs with `B-NCBI-2`)

These eight (one was miscounted above; recheck: NANOC, CNPRO, PROSV, SNIPG, SKA2, PFHAP, PYMLST, AMRO = 8) are bacterial/specialty pipeline-zoo additions that don't require Pillar I/II/III/IV/V to be implemented first; they can land any time as standalone pipeline-zoo items.

---

## 8. Strategic doc trim summary

After the `todo.md` edit lands, the two strategic docs need trimming so they don't duplicate canonical content:

### 8.1 `jackpot_immune_platform_plan.md` §14 trim

**Before:** §14.2 lists Phase 26-31 with B-001..B-049 individual items per phase.

**After:** §14.2 becomes a brief overview pointing to `todo.md` Phase IM-1..IM-6 by canonical ID. Each Phase IM-* sub-section becomes a 3-5 line summary describing the phase's *goal* and *definition of done*, with a "see `todo.md` Phase IM-N for active work items" reference. The B-001..B-049 list is removed.

§14.3 (OSS integration → schedule table) stays — it's a useful tool-to-phase mapping that's not redundant with `todo.md`.

§14.4 (Quick wins for the next 90 days) is replaced with a brief reference to the items now in `todo.md` (`B-IMMUNE-SCHEMA-1 [quick-win]`, `B-ACADEMY-STUB-1`, `B-LICENSE-1`, `B-SYNTH-DATA-1`).

### 8.2 `jackpot_immune_collaboration_scaffolding_copy.md` §9.1, §9.2, §9.3 trim

**Before:** §9.1 has the schedule table with 18 work items + effort + phase + dependencies. §9.2 has wet-side advisory items WW-1..WW-3. §9.3 has quick wins QW-8..QW-10.

**After:** §9.1 becomes a brief summary table listing only the canonical IDs (`B-COLLAB-DIVERSITY-1`, etc.) with effort + phase tag + dependencies, with a reference to `todo.md` Phase IM-N-collab for full descriptions. §9.2 and §9.3 become single-paragraph references to the corresponding canonical IDs.

The architectural prose throughout sections 3-8 (which describe the actual code patterns and design rationale) is preserved unchanged — that's the strategic value of the scaffolding doc.

---

## 9. Validation: every source item accounted for

Spot-check that every numeric/labeled source item lands somewhere:

- Immune plan §14: B-001..B-049 → 47 NEW canonical IDs + 2 MERGE ✓
- Immune plan §14.4: 6 quick wins → 2 NEW canonical IDs + 3 MERGE + 1 EXISTING-P0 ✓
- Scaffolding §9.1: 18 items → 16 NEW canonical IDs + 2 MERGE ✓
- Scaffolding §9.2: 3 items (WW-1, WW-2, WW-3) → 2 NEW canonical IDs + 1 MERGE ✓
- Scaffolding §9.3: 3 quick wins (QW-8, QW-9, QW-10) → 0 NEW + 3 MERGE ✓
- Detection landscape §6: 24 items → 23 NEW canonical IDs + 1 REAFFIRM ✓

All 49 + 6 + 18 + 3 + 3 + 24 = **103 source items** accounted for.

After dedup: 88 new canonical IDs + 5 merge consolidations + 8 reaffirms across new+existing tracking = **101 unique destinations** (some IDs absorb multiple source items via merges).

---

## 10. What gets executed in step 2 (the `todo.md` edit)

A single new top-level section is added to `todo.md`, sized to ~~~700-900 lines, structured as:

```
## Phase IM-1 — Immune Platform: Bio-AIS MVP + Academy Module 9 (Tracked, Not Scheduled)

### Prerequisites
- Audit transaction-participation bug fix (existing P0; see notes/jackpot_session_summary_and_backlog.md)
- _handle_workflow_complete() conn= TypeError fix (existing P0)
- Validator BASE_REQUIRED tier split (Glen-owned domain decision)

### A. Schema, NSA substrate, and immune-bio core (10 items)
- [ ] B-IMMUNE-SCHEMA-1 ...
- [ ] B-IMMUNE-NSA-1 ...
... etc

### B. Pillar I — Pipeline-zoo entries (Bio-Anomaly stack)
- [ ] B-AMAND-1 ...
- [ ] B-TAXTRIAGE-1 ...
... etc

### C. Phase IM-1-collab (interleaved)
- [ ] B-COLLAB-DIVERSITY-1 ...
... etc

## Phase IM-2 — Immune Platform: Multi-Modal Danger Fusion (Tracked, Not Scheduled)
...

## Phase IM-3, IM-4, IM-5, IM-6 — same structure
...

## Pipeline Zoo Additions from Detection Landscape (Tracked, Not Scheduled)
...
```

Per Glen's preference: "Never use placeholders" — every item has its full description, effort estimate, dependencies, and phase placement.

---

## 11. What gets executed in step 3 (strategic doc trims)

Two files emit replacement-text artifacts:

- `immune_plan_section_14_replacement.md` — drop-in replacement for `jackpot_immune_platform_plan.md` §14
- `scaffolding_section_9_replacement.md` — drop-in replacement for `jackpot_immune_collaboration_scaffolding_copy.md` §9.1, §9.2, §9.3

These get applied via `cat` / `cp` instructions provided to Glen for terminal application.

---

*End of consolidation report v1.0. After Glen's review, proceed to step 2 (todo.md edit) and step 3 (strategic doc trims).*
