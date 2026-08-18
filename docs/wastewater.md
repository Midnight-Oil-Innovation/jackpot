> **Status:** Canonical — wastewater surveillance schema.

# Wastewater

JACKPOT treats wastewater surveillance as a first-class data stream alongside clinical isolates, with its own schema requirements, its own normalization model, and its own coalition story. Wastewater samples represent a community rather than an individual — they're the cheapest population-level signal in pathogen surveillance, and the only one that doesn't require active patient encounters.

The current state is concrete and modest. Freyja outputs land in the existing `wastewater_lineage_abundance` result type via the Phase 14 metagenomic parsers. The immediate next step is **B-WW-1** — a Streamlit dashboard on top of these outputs — which is unblocked and ready to schedule at ~1.5 sessions of work. After that, a wastewater signal ingestion adapter (**B-IMMUNE-WW-1**) sits in Phase IM-2 (Tracked, Not Scheduled) and bridges wastewater into the multi-modal danger fusion path of the immune platform.

The forward-looking work is more ambitious. A four-class schema design — `WastewaterCollectionSite`, `WastewaterSample`, `WastewaterTargetResult`, `WastewaterMetagenomicProfile` — has been drafted (v0.1.0, 2026-05-10) to handle the metadata richness that wastewater requires but the current schema doesn't capture: catchment geometry, fecal-strength normalization, target-by-target qPCR results, untargeted metagenomic profiles, recovery efficiency from process controls. None of that is in the real backlog yet. If it becomes a priority, the path is: anchor doc → Phase 24.5 schema items → P0b migration → implementation phasing — comparable in scope to the immune platform plan.

This doc covers the full wastewater story: motivation, current state, the forward-looking schema design, the implementation path, and coalition framing. The broader open-source wastewater analysis software landscape lives in a sibling reference doc, `docs/wastewater_software_landscape.md`. The cryptWWDB integration path lives separately in `docs/cryptwwdb_integration.md` (per the cryptWWDB track in `todo.md`).

## §1. Motivation: why wastewater is a first-class data stream

Wastewater surveillance emerged from the COVID-19 pandemic as one of the most cost-effective, population-representative tools for pathogen detection. The literature review across seven papers establishes that wastewater is not an afterthought for One Health platforms — it's a first-class data stream with unique metadata requirements that differ fundamentally from clinical isolates.

Key findings driving this schema design:

- **Struelens et al. (2024):** Wastewater metagenomic analysis provides community-level pathogen prevalence, AMR resistome profiles, and early warning of variant emergence. After SARS-CoV-2 success, the field is harmonizing approaches for multi-pathogen surveillance (EU-WISH consortium).
- **Djordjevic et al. (2024):** Wastewater and sewage are critical reservoirs for AMR gene transmission. Metagenomic analysis of urban sewage reveals local sanitation and healthcare conditions correlate with AMR determinant profiles. Class 1 integrons are key sentinels for anthropogenic AMR pollution.
- **Hendriksen et al. (2019) / Munk et al. (2022):** Global sewage resistome mapping across 100+ countries demonstrates wastewater metagenomics as an economically and ethically acceptable approach to population-level AMR surveillance.
- **Black et al. (2020):** Wastewater samples don't fit the standard case → sample → sequence hierarchy because they lack an individual "case." The schema must accommodate community-level signal with catchment-based denominators.

## §2. Why wastewater samples differ from clinical isolates

Clinical isolate samples have a clear subject: one patient, one pathogen, one host species. Wastewater breaks this model in several ways:

| Dimension | Clinical Isolate | Wastewater Sample |
|---|---|---|
| Subject | Individual patient | Community/catchment |
| Host species | Single known host | Mixed (human + animal + environmental) |
| Denominator | Case count | Population served × flow rate |
| Pathogen count | Usually one per culture | Entire community resistome/virome |
| Temporal signal | Point-in-time (symptom onset) | Integrated over hours-days (composite) |
| Privacy concern | High (identifiable patient) | Low (aggregated community signal) |
| Normalization | Per-patient | Per-capita via fecal biomarkers (PMMoV, CrAssphage) |

These differences mean wastewater needs its own entity hierarchy rather than being shoehorned into the clinical sample model.

## §3. Current state in JACKPOT

### §3.1 What exists today — Freyja outputs

JACKPOT already lands Freyja outputs into the `wastewater_lineage_abundance` result type via the Phase 14 metagenomic parsers. Freyja is the SARS-CoV-2 lineage-deconvolution tool (Karthikeyan et al. 2022) that produces fractional lineage abundances from mixed wastewater samples. The result type captures lineage labels, fractional abundances, R² fit quality, and coverage metrics.

This is the seed of the wastewater story. Everything downstream builds on these existing rows.

### §3.2 What's tracked in the backlog

Three wastewater-touching items, in differently-positioned phases:

- **`B-WW-1` Wastewater lineage-abundance dashboard.** Future backlog (currently unblocked, ready to schedule). Sources: NICD-Wastewater-Genomics + andersen-lab/sd_ww_processing (both Freyja-based). The operator-facing visualization layer on top of existing `wastewater_lineage_abundance` Freyja outputs. Streamlit page with stacked-area lineage trajectories per sampling site, project/lab-membership filters, PNG/PDF export. **1.5 sessions.** Tagged Tier C-pattern in the 2026-05-09 open-source data-sharing platform survey.

- **`B-IMMUNE-WW-1` Wastewater signal ingestion adapter** (Phase IM-2, Tracked Not Scheduled). Adapter for at least one feed (NWSS or local STAB). Polls feed periodically; produces `DangerSignal` rows tagged `wastewater_concordance` for the BioDendriticCell engine's multi-modal fusion. 3-4 sessions. **This is the wastewater-meets-anomaly-detection cross-link.** Sits inside Phase IM-2 because it's part of multi-modal danger fusion, not just a wastewater visualization.

- **`B-WW-ADV-1` Wet-side advisory doc** at `docs/wetside_advisory.md`. 1 day. Documents current assumptions about wastewater sampling cadence, sample preservation, sequencing-prep failure modes, known limitations of the input pipeline. Reference: `jackpot_immune_collaboration_scaffolding.md` §9.2.

- **`B-WW-ADV-2` Pre-register questions for the wet-side advisor's group.** 2-3 sessions, depends on advisor identification.

The naming convention `B-WW-1` exists; the `B-IMMUNE-WW-1` and `B-WW-ADV-1` IDs disambiguate. The chat-invented `WW-1..12` numbering would collide with `B-WW-1` if naively merged — translation to net-new IDs (`B-WW-MODULE-1..12` perhaps) would be needed.

## §4. The forward-looking schema design (v0.1.0)

This section describes the wastewater module schema design — what `wastewater.yaml` could become if the larger refactor is pursued. **As of 2026-05-10 this is a draft for review.** None of these classes exist in the live schema yet. The schema source-of-truth is `jackpot_schema.yaml` and `jackpot_wastewater_schema.yaml`.

### §4.1 Schema architecture overview

The wastewater module adds four new classes that integrate with JACKPOT's existing core entities:

```
┌─────────────────────────────────┐
│   WastewaterCollectionSite      │  ← Persistent location entity
│   (the "where")                 │     Many samples per site over time
└───────────┬─────────────────────┘
            │ 1:N
            ▼
┌─────────────────────────────────┐
│   WastewaterSample              │  ← Single collection event
│   (the "when" + "how")          │     Links to core BioSample
└───────┬───────────┬─────────────┘
        │ 1:N       │ 1:N
        ▼           ▼
┌───────────────┐ ┌──────────────────────────────┐
│ Wastewater    │ │ WastewaterMetagenomicProfile  │
│ TargetResult  │ │ (untargeted resistome/virome) │
│ (qPCR/ddPCR)  │ └──────────┬─────────────────────┘
└───────────────┘            │
                             │ links to
                             ▼
                    ┌─────────────────────┐
                    │ JACKPOT Core:       │
                    │ SequencingRun       │
                    │ AnalysisResult      │
                    │ AMRProfile          │
                    └─────────────────────┘
```

### §4.2 Integration points with core JACKPOT

The wastewater module connects to the existing schema at these surfaces:

1. **`WastewaterSample.sample_id`** → Cross-references `BioSample.sample_id` in the core schema. The core `BioSample` entity should have a `sample_source_type` enum that includes `wastewater`, triggering the platform to look for the extended wastewater metadata.

2. **`WastewaterSample.sequencing_run_ids`** → Links to core `SequencingRun` entities for both targeted amplicon and shotgun metagenomic runs.

3. **`WastewaterMetagenomicProfile.sequencing_run_id`** → Direct FK to the core `SequencingRun` that produced the metagenomic data.

4. **`WastewaterSample.analysis_ids`** → Links to core `AnalysisResult` entities for AMR profiling, phylogenetic placement, etc.

### §4.3 Core schema additions needed

To fully integrate this module, the core JACKPOT schema needs these minimal additions:

```yaml
# In core sample schema, add to SampleSourceTypeEnum:
enums:
  SampleSourceTypeEnum:
    permissible_values:
      # ... existing values ...
      wastewater:
        description: Wastewater or sewage sample (community-level signal)
      surface_water:
        description: River, lake, or estuary sample
      agricultural_runoff:
        description: Agricultural drainage sample
      aquaculture_effluent:
        description: Aquaculture facility effluent

# In core sample schema, add to OneHealthSectorEnum:
  OneHealthSectorEnum:
    permissible_values:
      human_clinical:
        description: Clinical sample from human patient
      human_community:
        description: Community-level human signal (e.g., wastewater)
      animal_livestock:
        description: Food-producing animal sample
      animal_companion:
        description: Companion animal sample
      animal_wildlife:
        description: Wildlife or synanthropic animal sample
      environment_water:
        description: Water environment (wastewater, surface water, groundwater)
      environment_soil:
        description: Soil environment
      environment_air:
        description: Air/aerosol environment
      food:
        description: Food product sample
      agriculture:
        description: Agricultural setting (crop, irrigation, manure)
```

### §4.4 Class-by-class design rationale

#### §4.4.1 WastewaterCollectionSite

**Purpose:** Represents a persistent sampling location. Decoupled from individual samples because the same WWTP or manhole gets sampled repeatedly across a longitudinal surveillance program.

**Key design decisions:**

- **`population_served`** is the most critical field. Without it, you can't normalize pathogen concentrations to per-capita estimates — and unnormalized wastewater data is nearly uninterpretable across sites. Marked as `recommended` rather than `required` because it may not be known precisely for all sites (especially manholes or upstream points).

- **`industrial_input_fraction`** captures the One Health relevance of industrial contributors. Djordjevic et al. emphasize that biocides, heavy metals, and pharmaceutical residues from industrial sources create co-selection pressure for AMR. A site receiving 40% industrial flow will have a fundamentally different resistome profile than a purely residential catchment.

- **`known_upstream_sources`** is a multivalued free-text field for now. Future versions should formalize this as a linked entity (e.g., `UpstreamContributor` with type, distance, and estimated flow contribution). Hospitals, pharmaceutical manufacturing, and livestock operations are the highest-priority upstream sources to track per the literature.

- **`nwss_site_id`** enables direct compatibility with CDC's National Wastewater Surveillance System. Even if JACKPOT doesn't participate in NWSS initially, having this field means results can be cross-referenced later.

- **`site_type` enum** covers the full One Health spectrum: not just municipal WWTPs but also agricultural runoff, aquaculture effluent, slaughterhouse wastewater, and open drains (critical for LMIC settings per Djordjevic et al.).

#### §4.4.2 WastewaterSample

**Purpose:** Represents a single collection event with all the physical, chemical, and logistical context needed to interpret downstream results.

**Key design decisions:**

- **Hydraulic/environmental measurements** (`flow_rate_mgd`, `water_temperature_c`, `ph`, `turbidity_ntu`, `rainfall_48h_mm`) are essential covariates. Flow rate is the primary normalization denominator. Rainfall matters enormously in combined sewer systems where stormwater dilutes the fecal signal. Temperature affects pathogen degradation rates.

- **`concentration_method`** and **`extraction_method`** directly affect recovery efficiency and therefore apparent pathogen concentrations. The wastewater surveillance field has learned (painfully) that method differences can introduce 10-100x variation between labs. Capturing these enables method-aware comparisons.

- **`process_control_organism`** and **`recovery_efficiency_pct`** enable matrix spike recovery correction. Without this, you can't distinguish "the pathogen isn't there" from "our method didn't recover it." BCoV, MHV, and Phi6 are common viral surrogates; PMMoV and CrAssphage serve double duty as endogenous population biomarkers.

- **`pmmov_gc_l`** (Pepper mild mottle virus) is the emerging consensus fecal strength biomarker adopted by NWSS. By storing it at the sample level, any downstream target concentration can be normalized post-hoc.

- **`qc_status`** with explicit `preliminary` value aligns with WHO Principle 3 — share data rapidly but clearly mark quality status.

#### §4.4.3 WastewaterTargetResult

**Purpose:** Represents a single qPCR/ddPCR target measurement. This is the workhorse entity for targeted surveillance where you're asking "how much of pathogen X is in this sample?"

**Key design decisions:**

- **One row per target per sample.** A single wastewater sample might be assayed for SARS-CoV-2 N1, SARS-CoV-2 N2, Influenza A, Norovirus GII, blaNDM-1, mcr-1, and intI1 — that's seven `WastewaterTargetResult` rows for one `WastewaterSample`.

- **`target_category` enum** enables dashboard-level filtering without parsing gene names. Distinguishing "respiratory_virus" from "amr_gene" from "population_biomarker" lets the UI present relevant panels.

- **Variant deconvolution fields** (`variant_lineage`, `variant_proportion`, `variant_detection_method`) support tools like Freyja that estimate variant proportions from mixed wastewater signal. This was one of the most impactful applications during COVID-19 and is directly extensible to other viruses.

- **`detected` boolean** is required even when quantification fails. Presence/absence data from near-LOD samples is still epidemiologically useful.

- **Both `concentration_gc_l` and `concentration_gc_g`** are included because liquid-phase and solids-phase samples use different units, and some labs report both.

#### §4.4.4 WastewaterMetagenomicProfile

**Purpose:** Summary results from untargeted shotgun metagenomic sequencing. This is the entity that captures the broad resistome, taxonomic composition, and MGE inventory that targeted qPCR can't see.

**Key design decisions:**

- **`amr_profiler` + `amr_database` + `amr_database_version`** are separate fields because the same tool (e.g., ABRicate) can use different databases (CARD, ResFinder, NCBI). The database version matters enormously — running the same reads against CARD v3.2 vs v3.3 can produce different gene calls.

- **`amr_profile_path`** should point to a hAMRonization-compatible output file. This is the bridge to JACKPOT's planned AMR analysis module and ensures interoperability with the broader PHA4GE ecosystem.

- **`arg_reads_per_million`** is the simplest cross-sample normalization metric. More sophisticated approaches exist (e.g., RPKM per gene, coverage-based abundance), but RPM is universally calculable and comparable.

- **`integron_types_detected`** and **`plasmid_replicon_types`** are explicitly called out because Djordjevic et al. make a compelling case that class 1 integrons and specific plasmid types (IncHI2, IncX3, IncF) are the primary vehicles for CRR (complex resistance region) mobilization across Enterobacteriaceae. Tracking these at the metagenomic level provides early warning of emerging resistance plasmid spread.

- **MAG quality fields** follow MIMAG standards. The advent of long-read metagenomics (metaFlye, etc.) is enabling recovery of complete plasmid sequences from wastewater for the first time — a capability Djordjevic et al. highlight as previously impossible with short reads.

### §4.5 NWSS compatibility mapping

For sites participating in CDC's National Wastewater Surveillance System, the following field mappings apply:

| NWSS Field | JACKPOT Field | Notes |
|---|---|---|
| `sample_id` | `WastewaterSample.nwss_sample_id` | CDC-assigned |
| `wwtp_name` | `WastewaterCollectionSite.site_name` | |
| `wwtp_id` | `WastewaterCollectionSite.nwss_site_id` | |
| `population_served` | `WastewaterCollectionSite.population_served` | |
| `sample_collect_date` | `WastewaterSample.collection_date` | |
| `sample_type` | `WastewaterSample.collection_method` + `sample_matrix` | NWSS combines these |
| `flow_rate` | `WastewaterSample.flow_rate_mgd` | Units may differ |
| `concentration_method` | `WastewaterSample.concentration_method` | |
| `pcr_target` | `WastewaterTargetResult.target_name` | |
| `pcr_target_units` | Inferred from `concentration_gc_l` vs `concentration_gc_g` | |
| `pcr_target_avg_conc` | `WastewaterTargetResult.concentration_gc_l` | |
| `normalization_ref` | `WastewaterSample.pmmov_gc_l` | NWSS uses PMMoV |

### §4.6 WHO Tricycle protocol compatibility

The WHO Tricycle protocol specifies ESBL-producing *E. coli* as the indicator organism for One Health AMR surveillance across human, animal, and environmental sectors. For the environmental sector, the protocol recommends sampling at WWTP influent points.

This schema supports Tricycle-compatible environmental sampling through:

- **`WastewaterCollectionSite.site_type = wastewater_treatment_plant`** with **`WastewaterSample.treatment_stage = influent_raw`** matches the Tricycle environmental sampling specification.
- **`WastewaterTargetResult`** can capture ESBL-specific qPCR targets (e.g., blaCTX-M group-specific assays).
- **`WastewaterMetagenomicProfile`** captures the broader resistome context that Djordjevic et al. argue is essential — the Tricycle protocol's restriction to ESBL *E. coli* alone may miss critical plasmid-mediated resistance dynamics.

### §4.7 Sequencing density and timeliness metrics

Struelens et al. (2024, Figure 5) establish that the public health utility of genomic surveillance data is a function of both sampling density and timeliness. For wastewater, these metrics should be tracked at the `WastewaterCollectionSite` level:

| Metric | Definition | Target (from Rockefeller Framework) |
|---|---|---|
| Sampling frequency | Collections per week per site | 2-3x/week for WWTP, 1x/week for upstream |
| Turnaround: collection → qPCR result | Calendar days | 3-5 days |
| Turnaround: collection → sequence upload | Calendar days | 10 days |
| Turnaround: collection → variant deconvolution | Calendar days | 7-14 days |
| Geographic coverage | % of state population covered by active sites | >50% |

These are not schema fields but should be computed as dashboard KPIs from the `collection_date`, `analysis_date`, and site population data.

### §4.8 Future extensions

Things explicitly deferred from v0.1.0 that should be addressed in subsequent versions:

1. **`UpstreamContributor` entity** — Formalize the relationship between collection sites and known upstream sources (hospitals, farms, industrial facilities). This is the bridge to full One Health source attribution.

2. **`WastewaterTimeseriesSummary`** — Pre-computed trend metrics (7-day rolling average, week-over-week change, trend classification) for dashboard consumption without requiring full re-query of all target results.

3. **Spatial/GIS integration** — Sewershed polygon geometries stored as GeoJSON or linked to external shapefiles. Enables map-based visualization of wastewater signals overlaid with clinical case data.

4. **Multi-site composite** — Some surveillance programs pool samples from multiple upstream sites before analysis. The schema doesn't currently model this "sample of samples" relationship.

5. **Cost tracking** — Per-sample and per-analysis cost fields to support the cost-effectiveness evaluations that Struelens et al. emphasize are needed to build the business case for sustained wastewater surveillance funding.

6. **Environmental AMR risk scoring** — Computed fields that combine ARG abundance, MGE presence, and environmental context into risk scores per the framework proposed by Liguori et al. (2022) for standardized AMR monitoring in water environments.

## §5. Implementation path forward

### §5.1 Net-new schema work (Level 2 refactor)

The forward-looking schema in §4 describes a substantial refactor where `wastewater_samples` becomes a first-class entity model rather than just a result type:

- **Sites as first-class entities** with their own lifecycle. Sites get unique IDs at the operator level; samples reference site_id as FK. `wastewater_sites` table with `population_served`, `sewershed_geojson`, treatment plant info, `owning_lab_id` for RBAC.
- **Sample event as a thin wrapper** linking site + collection metadata. `wastewater_samples` table with `site_id` FK, `collection_datetime`, `collection_method` enum (grab / composite / auto-sampler), volume, transport conditions.
- **Per-target result rows** rather than a flat result blob. `wastewater_target_results` table with `sample_id` FK, `target_pathogen_id` FK, `assay_type` enum, `detection_status` enum, concentration with confidence intervals, normalization target (PMMoV / crAssphage / flow-normalized / none).
- **Metagenomic profiles separately** from lineage deconvolution. `wastewater_metagenomic_profiles` for Lim-style metagenomic deconvolution work. `wastewater_lineage_deconvolution_results` as typed evolution of the existing `wastewater_lineage_abundance` result type, with explicit fields for tool (Freyja / cojac / lcs), tool version, reference barcode version, lineage fractions JSONB.

Plus enums, indexes, RBAC integration, audit forwarding (the existing `log_audit` / `create_notification` pattern), pgvector embeddings for metagenomic profile similarity, the migration script with site dedupe + county_names array preservation + Freyja-data migration to typed table.

**None of that is in todo.md.** If it becomes a real priority, it's a substantial design effort — comparable in scope to the immune platform plan. The starting point would be a `jackpot_wastewater_module_design.md` anchor document analogous to `jackpot_immune_platform_plan.md`, then the schema items get committed in Phase 24.5 alongside the existing sovereignty + BYOP/eukaryotic lockdowns (so they all land in the P0b migration), then implementation items get phased.

The three critique-loop iterations (RBAC defect → consumer-code defect → migration-correctness defects) on the wastewater design are useful design-thinking that informs whoever writes the anchor doc. But the items themselves aren't tracked.

### §5.2 Demo paths for Scenario A (laptop case)

Two viable demo levels, depending on appetite:

**Level 1 — Ship `B-WW-1`.** 1.5 sessions. Wastewater lineage-abundance dashboard on existing Freyja outputs. Demo question: "Show me SARS-CoV-2 lineage trajectories for Tempe / Maricopa County over the last N months." Visualizable, real data (NWSS-fetched via Socrata API or Tempe Open Data via ArcGIS), no schema changes, no new pipelines.

**Level 2 — Ship `B-WW-1` + add net-new module design + first slice.** Many sessions. Anchor doc + Phase 24.5 schema items + initial implementation. Demo extends to multi-pathogen panel (flu A/B, RSV, mpox, norovirus from Tempe data) with site-anchored longitudinal views, target-specific concentration time series with confidence intervals, normalization-target awareness.

**Recommendation: ship Level 1, defer Level 2 design effort behind the immune platform and federation roadmap.** The reason: `B-WW-1` is small, unblocked, and demoable in under a week of focused work. It validates the wastewater story to coalition members (Halden, Lim, Scotch, Lant) without committing to the larger refactor. If Level 1 shipping triggers real coalition movement, that's the signal to invest in Level 2. If it doesn't, Level 1 stands on its own as a useful platform feature.

### §5.3 The 9 chat-invented adoption items — actual reconciliation

Earlier chat content included a "Phase 26 subsection N" with 9 wastewater-platform adoption items (B-PIGX, B-AQUASCOPE, B-WEPP, B-WMON, B-WASTPAN, B-ENCYC, B-RESPIPE, B-DPCR, B-PROBE). None of these are in the real backlog.

The real Phase 26 (Pathoplexus/Loculus comparative, Tracked Not Scheduled) has 34 items grouped A-J by source platform — Pathoplexus/Loculus, Pathogenwatch, EnteroBase, NCBI Pathogen Detection, BV-BRC, GISAID, GenSpectrum/LAPIS, Solu, RT-MetA. The wastewater adoption items would be subsection K-N or a new Phase 26 sub-bucket if added.

Each would go through `DEC-13`-style verification (URL, commit hash, license check) before commitment per the documented `B-XXX` adoption process — but `DEC-13` itself was a chat-invented decision item that doesn't formally exist in todo.md (the actual practice is documented at the top of Phase 26 in todo.md).

For the catalog of upstream wastewater platforms that could be evaluated (watermonitor, WastPan, Encyclopaedia Cloacae, PiGx SARS-CoV-2, Aquascope, WEPP, ResPipe, etc.), see `docs/wastewater_software_landscape.md`.

## §6. Coalition cross-references

Wastewater is the most coalition-ready of the three priorities currently in play. The reasons:

1. **Halden / Lim / Scotch axis is already published.** Fontenele et al. 2021 *bioRxiv* "High-throughput sequencing of SARS-CoV-2 in wastewater provides insights into circulating variants" — coauthors include Halden, Scotch, Varsani, Lim. The collaboration pattern is established.
2. **Existing infrastructure is real.** `wastewater_lineage_abundance` result type ships now. `B-WW-1` builds on it directly.
3. **City of Tempe is a tangible demonstration site.** ASU campus catchment, substance-use panel, ArcGIS-published data, no access-control friction.
4. **Cross-link to IM-2 anomaly detection is natural.** `B-IMMUNE-WW-1` makes wastewater a multi-modal danger signal feeding into bio-AIS triage.

The fast path: ship `B-WW-1` first; demo to Halden / Lim / Scotch; based on signal, decide whether to invest design effort in the Level 2 module or push the demo into the IM-2 multi-modal fusion narrative.

The cryptWWDB coalition track (Halden + Trieu + Forrest + Driver et al.) is treated separately — see `docs/cryptwwdb_integration.md` for the encrypted-mass-balance computation path that builds directly on Driver et al. 2024.

## §7. Cross-references to other JACKPOT docs

The wastewater story touches several existing JACKPOT documents:

- **`jackpot_architecture.md`** — system architecture; `wastewater_lineage_abundance` result type is part of the existing pipeline_results schema.
- **`jackpot_immune_platform_plan.md`** §4.3 — wastewater as one of the multi-modal danger signals for IM-2.
- **`jackpot_immune_collaboration_scaffolding.md`** §9.2 — the wet-side advisory doc requirement.
- **`jackpot_detection_landscape.md`** §6 — pipeline-zoo entries including AMAnD, TaxTriage. None of these are wastewater-specific but AMAnD is metagenome-applicable.
- **`docs/cryptwwdb_integration.md`** — encrypted-mass-balance computation per Driver et al. 2024.
- **`docs/federation.md`** — federated wastewater queries via the L1 query federation primitive; `B-IMMUNE-HE-1` for HE-protected mass-balance across municipalities.
- **`docs/wastewater_software_landscape.md`** — catalog of open-source wastewater analysis platforms (watermonitor, WastPan, Encyclopaedia Cloacae, etc.), bioinformatics methodologies, sequencing strategies, and current limitations in the open-source landscape.

There is no `jackpot_wastewater_module_design.md` yet. If Level 2 becomes a priority, that's the anchor doc that needs writing first.
