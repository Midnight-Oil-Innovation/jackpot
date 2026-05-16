# Wastewater roadmap

The chat went deep on a "wastewater module refactor" (chat-named `WW-1..12` schema + `WW-13..26` implementation + Phase 34 + Phase 26 subsection N + DEC-10..14). None of that is in the real backlog. What IS in the real backlog is more modest: a Freyja-output dashboard, a wastewater signal ingestion adapter under IM-2, and an advisory doc. This is the reconciled path.

## What exists today

JACKPOT already lands Freyja outputs into the `wastewater_lineage_abundance` result type via the Phase 14 metagenomic parsers. Freyja is the SARS-CoV-2 lineage-deconvolution tool (Karthikeyan et al. 2022) that produces fractional lineage abundances from mixed wastewater samples. The result type captures lineage labels, fractional abundances, R² fit quality, and coverage metrics.

This is the seed of the wastewater story. Everything downstream builds on these existing rows.

## What's tracked in todo.md

Three wastewater-touching items, all in differently-positioned phases:

- **`B-WW-1` Wastewater lineage-abundance dashboard.** Future backlog (currently unblocked, ready to schedule). Sources: NICD-Wastewater-Genomics + andersen-lab/sd_ww_processing (both Freyja-based). The operator-facing visualization layer on top of existing `wastewater_lineage_abundance` Freyja outputs. Streamlit page with stacked-area lineage trajectories per sampling site, project/lab-membership filters, PNG/PDF export. **1.5 sessions.** Tagged Tier C-pattern in the 2026-05-09 open-source data-sharing platform survey.

- **`B-IMMUNE-WW-1` Wastewater signal ingestion adapter** (Phase IM-2, Tracked Not Scheduled). Adapter for at least one feed (NWSS or local STAB). Polls feed periodically; produces `DangerSignal` rows tagged `wastewater_concordance` for the BioDendriticCell engine's multi-modal fusion. 3-4 sessions. **This is the wastewater-meets-anomaly-detection cross-link.** Sits inside Phase IM-2 because it's part of multi-modal danger fusion, not just a wastewater visualization.

- **`B-WW-ADV-1` Wet-side advisory doc** at `docs/wetside_advisory.md`. 1 day. Documents current assumptions about wastewater sampling cadence, sample preservation, sequencing-prep failure modes, known limitations of the input pipeline. Reference: `jackpot_immune_collaboration_scaffolding.md` §9.2.

- **`B-WW-ADV-2` Pre-register questions for the wet-side advisor's group.** 2-3 sessions, depends on advisor identification.

The naming convention `B-WW-1` exists; the `B-IMMUNE-WW-1` and `B-WW-ADV-1` IDs disambiguate. The chat's `WW-1..12` numbering would collide with `B-WW-1` if naively merged — translation to net-new IDs (`B-WW-MODULE-1..12` perhaps) would be needed.

## What's net-new if pursued

The chat designed a much larger wastewater module — a refactor where `wastewater_samples` becomes a first-class entity model rather than just a result type. The design:

- **Sites as first-class entities** with their own lifecycle. Sites get unique IDs at the operator level; samples reference site_id as FK. `wastewater_sites` table with `population_served`, `sewershed_geojson`, treatment plant info, `owning_lab_id` for RBAC.
- **Sample event as a thin wrapper** linking site + collection metadata. `wastewater_samples` table with `site_id` FK, `collection_datetime`, `collection_method` enum (grab / composite / auto-sampler), volume, transport conditions.
- **Per-target result rows** rather than a flat result blob. `wastewater_target_results` table with `sample_id` FK, `target_pathogen_id` FK, `assay_type` enum, `detection_status` enum, concentration with confidence intervals, normalization target (PMMoV / crAssphage / flow-normalized / none).
- **Metagenomic profiles separately** from lineage deconvolution. `wastewater_metagenomic_profiles` for Lim-style metagenomic deconvolution work. `wastewater_lineage_deconvolution_results` as typed evolution of the existing `wastewater_lineage_abundance` result type, with explicit fields for tool (Freyja / cojac / lcs), tool version, reference barcode version, lineage fractions JSONB.

Plus enums, indexes, RBAC integration, audit forwarding (the existing `log_audit` / `create_notification` pattern), pgvector embeddings for metagenomic profile similarity, the migration script with site dedupe + county_names array preservation + Freyja-data migration to typed table.

**None of that is in todo.md.** If it becomes a real priority, it's a substantial design effort — comparable in scope to the immune platform plan. The starting point would be a `jackpot_wastewater_module_design.md` anchor document analogous to `jackpot_immune_platform_plan.md`, then the schema items get committed in Phase 24.5 alongside the existing sovereignty + BYOP/eukaryotic lockdowns (so they all land in the P0b migration), then implementation items get phased.

The chat's three critique-loop iterations (RBAC defect → consumer-code defect → migration-correctness defects) on the wastewater design are useful design-thinking that informs whoever writes the anchor doc. But the items themselves aren't tracked.

## Demo path for laptop Scenario A

Two viable demo levels, depending on appetite:

**Level 1 — Ship `B-WW-1`.** 1.5 sessions. Wastewater lineage-abundance dashboard on existing Freyja outputs. Demo question: "Show me SARS-CoV-2 lineage trajectories for Tempe / Maricopa County over the last N months." Visualizable, real data (NWSS-fetched via Socrata API or Tempe Open Data via ArcGIS), no schema changes, no new pipelines.

**Level 2 — Ship `B-WW-1` + add net-new module design + first slice.** Many sessions. Anchor doc + Phase 24.5 schema items + initial implementation. Demo extends to multi-pathogen panel (flu A/B, RSV, mpox, norovirus from Tempe data) with site-anchored longitudinal views, target-specific concentration time series with confidence intervals, normalization-target awareness.

**Recommendation: ship Level 1, defer Level 2 design effort behind the immune platform and federation roadmap.** The reason: `B-WW-1` is small, unblocked, and demoable in under a week of focused work. It validates the wastewater story to coalition members (Halden, Lim, Scotch, Lant) without committing to the larger refactor. If Level 1 shipping triggers real coalition movement, that's the signal to invest in Level 2. If it doesn't, Level 1 stands on its own as a useful platform feature.

## The 9 B-XXX adoption items from chat — actual reconciliation

The chat included "Phase 26 subsection N" with 9 wastewater-platform adoption items (B-PIGX, B-AQUASCOPE, B-WEPP, B-WMON, B-WASTPAN, B-ENCYC, B-RESPIPE, B-DPCR, B-PROBE). None of these are in the real backlog.

The real Phase 26 (Pathoplexus/Loculus comparative, Tracked Not Scheduled) has 34 items grouped A-J by source platform — Pathoplexus/Loculus, Pathogenwatch, EnteroBase, NCBI Pathogen Detection, BV-BRC, GISAID, GenSpectrum/LAPIS, Solu, RT-MetA. The wastewater adoption items would be subsection K-N or a new Phase 26 sub-bucket if added.

Each would go through `DEC-13`-style verification (URL, commit hash, license check) before commitment per the documented `B-XXX` adoption process — but `DEC-13` itself was a chat-invented decision item that doesn't formally exist in todo.md (the actual practice is documented at the top of Phase 26 in todo.md).

## Cross-references that already exist

The wastewater roadmap touches several existing JACKPOT documents:

- **`jackpot_architecture.md`** — system architecture; `wastewater_lineage_abundance` result type is part of the existing pipeline_results schema.
- **`jackpot_immune_platform_plan.md`** §4.3 — wastewater as one of the multi-modal danger signals for IM-2.
- **`jackpot_immune_collaboration_scaffolding.md`** §9.2 — the wet-side advisory doc requirement.
- **`jackpot_detection_landscape.md`** §6 — pipeline-zoo entries including AMAnD, TaxTriage. None of these are wastewater-specific but AMAnD is metagenome-applicable.

There is no `jackpot_wastewater_module_design.md` yet. If Level 2 becomes a priority, that's the anchor doc that needs writing first.

## Strategic framing

Wastewater is the most coalition-ready of the three priorities Glen named. The reasons:

1. **Halden / Lim / Scotch axis is already published.** Fontenele et al. 2021 *bioRxiv* "High-throughput sequencing of SARS-CoV-2 in wastewater provides insights into circulating variants" — coauthors include Halden, Scotch, Varsani, Lim. The collaboration pattern is established.
2. **Existing infrastructure is real.** `wastewater_lineage_abundance` result type ships now. `B-WW-1` builds on it directly.
3. **City of Tempe is a tangible demonstration site.** ASU campus catchment, substance-use panel, ArcGIS-published data, no access-control friction.
4. **Cross-link to IM-2 anomaly detection is natural.** `B-IMMUNE-WW-1` makes wastewater a multi-modal danger signal feeding into bio-AIS triage.

The fast path: ship `B-WW-1` first; demo to Halden / Lim / Scotch; based on signal, decide whether to invest design effort in the Level 2 module or push the demo into the IM-2 multi-modal fusion narrative.
