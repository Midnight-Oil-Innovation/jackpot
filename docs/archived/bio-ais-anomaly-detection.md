# Bio-AIS anomaly detection

The chat's ML/anomaly-detection design is reconciled against JACKPOT's existing Pillar I (bio-AIS) plan from `jackpot_immune_platform_plan.md` and the consolidated `B-IMMUNE-*` backlog under Phase IM-1.

## What's already designed and tracked

JACKPOT's anomaly-detection plan exists. It lives in Phase IM-1 ("Immune Platform: Bio-AIS MVP + Academy Module 9"), currently Tracked Not Scheduled. The design is more developed than my chat content assumed.

Core architectural primitives (Phase IM-1.A, all Tracked Not Scheduled):

- **`B-IMMUNE-SCHEMA-1`** Schema v6.0 stub. Alembic migration adding `detectors`, `detector_activations`, `dca_priority_scores`, `memory_cells` tables. Lands behind `IMMUNE_PILLAR_I_ENABLED=false` feature flag. Forces schema design conversation early. 1-2 sessions. **Quick-win flagged for landing alongside current sprint.**
- **`B-IMMUNE-NSA-1`** Negative Selection Algorithm substrate at `backend/immune/algorithms/nsa.py`. Shared between bio-AIS (Pillar I) and cyber-AIS (Pillar V) — same code, different feature spaces. 3-4 sessions.
- **`B-IMMUNE-FEAT-1`** Featurizer registry pattern at `backend/immune/algorithms/features.py` and `backend/immune/algorithms/featurizers/__init__.py`. k-mer featurizer for Pillar I, API-call featurizer stub for Pillar V. Registry pattern lets external collaborators (e.g. AIS-theory researchers) plug in alternative featurizers — k-mer, ESM-small, ESM-large, DNABERT-v2 — without touching core code. 2-3 sessions. **This is what makes the work collaboration-friendly per `jackpot_immune_collaboration_scaffolding.md` §3.2.1.**
- **`B-AMAND-1`** Adopt AMAnD (Price & Russell, *Frontiers in Public Health* 2023) as the canonical metagenome anomaly detector. Two layers: `backend/immune/bio/amand.py` (bio-NSA module wrapping AMAnD's DeepSVDD model into JACKPOT's NSA substrate) plus `pipelines/immune/amand.nf` (the Nextflow process for reproducible scans). Document the baseline-curation workflow ("what is normal for this operator's deployment context") in the Pillar IV training materials. 3 sessions for the pipeline + 2 weeks for the baseline-curation tooling.

API and UI surfaces:

- **`B-IMMUNE-API-1`** FastAPI surface at `backend/routers/immune_bio.py`. Endpoints: `GET /api/v1/immune/triage` (DCA-priority queue), `GET /api/v1/immune/detectors/` (active detectors), `GET /api/v1/immune/dca/{sample_id}` (per-sample priority breakdown). 2-3 sessions.
- **`B-IMMUNE-UI-1`** Streamlit page "Anomaly Triage" at `frontend/pages/anomaly_triage.py`. Lists DCA-priority samples. Full DCA fusion lands in IM-2. 1-2 sessions.

Pipeline-zoo expansion (Phase IM-1.B, parallel with IM-1.A):

- **`B-TAXTRIAGE-1`** Adopt `nf-core/taxtriage` (Merritt et al., *Bioinformatics* 2026) as canonical untargeted pathogen-discovery workflow. 2-3 sessions.
- **`B-NFUNO-1`** Adopt nf-UnO (Guzman-Cole & Huang, *Bioinformatics* 2025) as cohort co-assembly pipeline for outbreak novel-pathogen investigations. 2 sessions.
- **`B-DEEPAC-1`** DeePaC (Bartoszewicz et al. 2020) pathogenicity scoring as post-classification step in TaxTriage pipeline. 1-2 sessions.
- **`B-MLM-1`** MLM (Baugher et al., *JHU APL Technical Digest* 2025) as unmapped-read threat-characterization stage. 2 sessions.
- **`B-CGMSI-1`** cgMSI (Zhu et al., *BMC Bioinformatics* 2023) for nanopore strain-level detection. 1-2 sessions.
- **`B-INSAFLU-1`** Evaluate INSaFLU-TELEVIR (Santos et al., *Genome Medicine* 2024) for viral mNGS pipeline + LAPIS-compat prior art. 1 session study + 2 sessions adoption.
- **`B-KOMB-1`** Study KOMB/KombOver (Balaji et al. 2022; Sapoval et al. 2024) for community-shift detection. Pairs with `B-AMAND-1` for two complementary signals. 1-2 weeks study.

Collaboration scaffolding (Phase IM-1-collab, interleaved):

- **`B-COLLAB-DIVERSITY-1`** Randomized init with depth guard in `cli/jackpot_init/diversity_profile.py`. Each operator's `jackpot init` produces a different detector configuration drawn from a diversity-aware distribution; prevents federation-wide monoculture. 1 day.
- **`B-COLLAB-SBOM-1`** CycloneDX SBOM generator + CI supply-chain gate. 3 days.
- **`B-COLLAB-PARSERS-1`** Safe deserialization helpers at `backend/immune/sec/parsers_safe.py`. **Quick-win flagged.** 1 day.
- **`B-COLLAB-SIGSTORE-1`** Cosign-signed container images + key management. 2 days.
- **`B-COLLAB-FRAMING-1`** Module 0 (`course/modules/_meta/ais_framing.md`) explaining AIS framing as organizing principle. **Quick-win.** 0.5 day.

## The five anomaly types — reconciled

My chat content split "anomaly in pathogen genomes over time" into five types. The actual JACKPOT plan handles these via different combinations of the IM-1 primitives plus IM-2 multi-modal fusion:

| Anomaly type | Actual JACKPOT plan | Phase |
|---|---|---|
| Novel lineage emergence | `B-AMAND-1` (DeepSVDD on metagenomic embeddings) + `B-TAXTRIAGE-1` (untargeted discovery) | IM-1 |
| Lineage growth anomaly | Not directly in IM-1. Closest is `B-AMAND-1` over time. MLR / hierarchical Bayes on lineage frequencies would be net-new. | n/a |
| Convergent mutation / homoplasy | Not in IM-1. Phylogenetic detection (Augur, Treetime). Would be net-new. | n/a |
| Phylogenetic placement outliers | Not in IM-1. UShER parsimony + placement uncertainty. Would be net-new. | n/a |
| AMR fingerprint anomaly | Not directly in IM-1. Isolation Forest on hAMRonization vectors would be net-new. | n/a |

The chat's framing (foundation models like Nucleotide Transformer / Evo / HyenaDNA / DNABERT-2 / ESM-2) is design-thinking. The committed JACKPOT plan uses **AMAnD's DeepSVDD model** as the canonical metagenome anomaly detector, with the featurizer registry (`B-IMMUNE-FEAT-1`) leaving room for foundation-model embeddings as plug-in alternatives without core code changes. This is more conservative and more collaboration-friendly than the chat suggested.

## The DCA fusion (Phase IM-2)

Phase IM-2 layers multi-modal danger fusion on top. This is the differentiator that distinguishes JACKPOT's Pillar I from a pure-genomics anomaly detector:

- **`B-IMMUNE-DCA-1`** `backend/immune/bio/dca_bio.py` — full BioDendriticCell engine. Fuses genomic anomaly score from `B-AMAND-1` with multi-modal danger signals (wastewater, clinical, environmental, animal). Produces `dca_priority_scores` rows with explainable contributions per Patel 2021. 4-5 sessions.
- **`B-IMMUNE-SCHEMA-2`** Pydantic models for `DangerSignal`, `DcaPriorityScore`, `MultiModalContext`. 1-2 sessions.
- **`B-IMMUNE-WW-1`** Wastewater signal ingestion adapter (NWSS or local STAB feed). Produces `DangerSignal` rows tagged `wastewater_concordance`. 3-4 sessions. **This is the wastewater-meets-anomaly-detection cross-link.**

The success criterion for IM-2 is a high-priority sample with confirmed wastewater + clinical concordance surfacing at top of triage queue with per-signal explainable contributions. That's the lineage-resolved forecasting demo's anomaly-detection complement.

## What from the chat content is genuinely net-new

The committed JACKPOT plan doesn't include several anomaly-detection types the chat discussed. If those become priorities, they're net-new design work:

- **Lineage growth anomaly** via MLR or hierarchical Bayesian on lineage frequencies over time (the `evofr`-style approach).
- **AMR fingerprint anomaly** via Isolation Forest on hAMRonization output vectors.
- **UShER placement outlier scoring** at ingest, with parsimony + placement uncertainty fields on `pipeline_results`.
- **Foundation model embedding pipeline** as an alternative featurizer beyond k-mer (would plug into `B-IMMUNE-FEAT-1` registry).
- **Drift monitoring** with `alibi-detect`.

Each is a 2-5 session item, plug-compatible with the IM-1 substrate, none require schema changes beyond the existing `B-IMMUNE-SCHEMA-1` table set. Adding them is "add tracked items to IM-1.A or IM-1.B" rather than "redesign the platform."

## Phased rollout — reconciled

The chat's four-phase A/B/C/D rollout maps cleanly onto the actual phase chain:

| Chat Phase | Actual JACKPOT phase | What's involved |
|---|---|---|
| Phase A (weeks, no GPU) | IM-1.A + IM-1.B core | `B-IMMUNE-NSA-1` + `B-IMMUNE-FEAT-1` + `B-AMAND-1` + `B-IMMUNE-SCHEMA-1` + `B-TAXTRIAGE-1` |
| Phase B (months, GPU) | IM-1.B foundation models via featurizer registry | Add ESM-small / Nucleotide Transformer / etc. featurizers to `B-IMMUNE-FEAT-1` registry |
| Phase C (quarters, real ML) | IM-2 + IM-3 (multi-modal fusion + memory cells) | Phases IM-2 + IM-3 |
| Phase D (research) | Cross-pillar work and Pillar III federation | IM-4 |

## Demo path for laptop Scenario A

The fastest demoable bio-AIS slice on a laptop:

1. Land `B-IMMUNE-SCHEMA-1` (the empty migration with feature flag). Schema is visible but feature-gated off.
2. Land `B-COLLAB-PARSERS-1` (safe deserialization helpers — quick-win, 1 day).
3. Land `B-COLLAB-FRAMING-1` (Module 0 — quick-win, 0.5 day).
4. Land `B-AMAND-1` against a small synthetic-data corpus generated by `B-SYNTH-DATA-1` (also a quick-win, 2-3 sessions).
5. Land `B-IMMUNE-API-1` + `B-IMMUNE-UI-1` (Anomaly Triage page).

That's a vertical slice — ingest → AMAnD scan → DCA priority score row (stub fusion is fine for laptop demo) → Streamlit Triage UI — without requiring the full multi-modal fusion (IM-2), memory cells (IM-3), or federation (IM-4) to land first. Effort is roughly 2-3 weeks of focused work.

The demo question becomes: "Submit a synthetic sample on the laptop, watch it flow through AMAnD, see it surface in Anomaly Triage with a priority score." That's a credible bio-AIS demo for a coalition conversation with Forrest, even without IM-2/3/4 in place.

## What this maps to in the coalition

- **Forrest** — Pillar I bio-AIS work referencing `Jackpot_AIS.md` and the IM-1 plan. AMAnD-as-NSA is a natural conversation entry point.
- **Lee** — featurizer registry (`B-IMMUNE-FEAT-1`) maps to his catELMo/TCR-Gen attention-based embedding work.
- **Pathak (STPH)** — Module 9 academy work (`B-ACADEMY-9`) maps to STPH curriculum (TPH554 AI/ML in Public Health).
- **Scarpino** — AMAnD overlap with his wastewater metagenomics grant; cross-link via `B-IMMUNE-WW-1` (IM-2).
