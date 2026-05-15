# JACKPOT Wastewater Surveillance Schema — Design Document

**Module:** `wastewater.yaml`
**Version:** 0.1.0
**Status:** Draft for review
**Author:** Glen (ASU) + Claude synthesis from literature review
**Date:** 2026-05-10

---

## Motivation

Wastewater surveillance emerged from the COVID-19 pandemic as one of the most cost-effective, population-representative tools for pathogen detection. The literature review across seven papers establishes that wastewater is not an afterthought for One Health platforms — it's a first-class data stream with unique metadata requirements that differ fundamentally from clinical isolates.

Key findings driving this schema design:

- **Struelens et al. (2024):** Wastewater metagenomic analysis provides community-level pathogen prevalence, AMR resistome profiles, and early warning of variant emergence. After SARS-CoV-2 success, the field is harmonizing approaches for multi-pathogen surveillance (EU-WISH consortium).
- **Djordjevic et al. (2024):** Wastewater and sewage are critical reservoirs for AMR gene transmission. Metagenomic analysis of urban sewage reveals local sanitation and healthcare conditions correlate with AMR determinant profiles. Class 1 integrons are key sentinels for anthropogenic AMR pollution.
- **Hendriksen et al. (2019) / Munk et al. (2022):** Global sewage resistome mapping across 100+ countries demonstrates wastewater metagenomics as an economically and ethically acceptable approach to population-level AMR surveillance.
- **Black et al. (2020):** Wastewater samples don't fit the standard case → sample → sequence hierarchy because they lack an individual "case." The schema must accommodate community-level signal with catchment-based denominators.

---

## Why Wastewater Samples Are Different

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

---

## Schema Architecture

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
│ (qPCR/ddPCR) │ └──────────┬─────────────────────┘
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

### Integration Points with Core JACKPOT

The wastewater module connects to the existing schema at these surfaces:

1. **`WastewaterSample.sample_id`** → Cross-references `BioSample.sample_id` in the core schema. The core `BioSample` entity should have a `sample_source_type` enum that includes `wastewater`, triggering the platform to look for the extended wastewater metadata.

2. **`WastewaterSample.sequencing_run_ids`** → Links to core `SequencingRun` entities for both targeted amplicon and shotgun metagenomic runs.

3. **`WastewaterMetagenomicProfile.sequencing_run_id`** → Direct FK to the core `SequencingRun` that produced the metagenomic data.

4. **`WastewaterSample.analysis_ids`** → Links to core `AnalysisResult` entities for AMR profiling, phylogenetic placement, etc.

### Core Schema Additions Needed

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

---

## Class-by-Class Design Rationale

### WastewaterCollectionSite

**Purpose:** Represents a persistent sampling location. Decoupled from individual samples because the same WWTP or manhole gets sampled repeatedly across a longitudinal surveillance program.

**Key design decisions:**

- **`population_served`** is the most critical field. Without it, you can't normalize pathogen concentrations to per-capita estimates — and unnormalized wastewater data is nearly uninterpretable across sites. Marked as `recommended` rather than `required` because it may not be known precisely for all sites (especially manholes or upstream points).

- **`industrial_input_fraction`** captures the One Health relevance of industrial contributors. Djordjevic et al. emphasize that biocides, heavy metals, and pharmaceutical residues from industrial sources create co-selection pressure for AMR. A site receiving 40% industrial flow will have a fundamentally different resistome profile than a purely residential catchment.

- **`known_upstream_sources`** is a multivalued free-text field for now. Future versions should formalize this as a linked entity (e.g., `UpstreamContributor` with type, distance, and estimated flow contribution). Hospitals, pharmaceutical manufacturing, and livestock operations are the highest-priority upstream sources to track per the literature.

- **`nwss_site_id`** enables direct compatibility with CDC's National Wastewater Surveillance System. Even if JACKPOT doesn't participate in NWSS initially, having this field means results can be cross-referenced later.

- **`site_type` enum** covers the full One Health spectrum: not just municipal WWTPs but also agricultural runoff, aquaculture effluent, slaughterhouse wastewater, and open drains (critical for LMIC settings per Djordjevic et al.).

### WastewaterSample

**Purpose:** Represents a single collection event with all the physical, chemical, and logistical context needed to interpret downstream results.

**Key design decisions:**

- **Hydraulic/environmental measurements** (`flow_rate_mgd`, `water_temperature_c`, `ph`, `turbidity_ntu`, `rainfall_48h_mm`) are essential covariates. Flow rate is the primary normalization denominator. Rainfall matters enormously in combined sewer systems where stormwater dilutes the fecal signal. Temperature affects pathogen degradation rates.

- **`concentration_method`** and **`extraction_method`** directly affect recovery efficiency and therefore apparent pathogen concentrations. The wastewater surveillance field has learned (painfully) that method differences can introduce 10-100x variation between labs. Capturing these enables method-aware comparisons.

- **`process_control_organism`** and **`recovery_efficiency_pct`** enable matrix spike recovery correction. Without this, you can't distinguish "the pathogen isn't there" from "our method didn't recover it." BCoV, MHV, and Phi6 are common viral surrogates; PMMoV and CrAssphage serve double duty as endogenous population biomarkers.

- **`pmmov_gc_l`** (Pepper mild mottle virus) is the emerging consensus fecal strength biomarker adopted by NWSS. By storing it at the sample level, any downstream target concentration can be normalized post-hoc.

- **`qc_status`** with explicit `preliminary` value aligns with WHO Principle 3 — share data rapidly but clearly mark quality status.

### WastewaterTargetResult

**Purpose:** Represents a single qPCR/ddPCR target measurement. This is the workhorse entity for targeted surveillance where you're asking "how much of pathogen X is in this sample?"

**Key design decisions:**

- **One row per target per sample.** A single wastewater sample might be assayed for SARS-CoV-2 N1, SARS-CoV-2 N2, Influenza A, Norovirus GII, blaNDM-1, mcr-1, and intI1 — that's seven `WastewaterTargetResult` rows for one `WastewaterSample`.

- **`target_category` enum** enables dashboard-level filtering without parsing gene names. Distinguishing "respiratory_virus" from "amr_gene" from "population_biomarker" lets the UI present relevant panels.

- **Variant deconvolution fields** (`variant_lineage`, `variant_proportion`, `variant_detection_method`) support tools like Freyja that estimate variant proportions from mixed wastewater signal. This was one of the most impactful applications during COVID-19 and is directly extensible to other viruses.

- **`detected` boolean** is required even when quantification fails. Presence/absence data from near-LOD samples is still epidemiologically useful.

- **Both `concentration_gc_l` and `concentration_gc_g`** are included because liquid-phase and solids-phase samples use different units, and some labs report both.

### WastewaterMetagenomicProfile

**Purpose:** Summary results from untargeted shotgun metagenomic sequencing. This is the entity that captures the broad resistome, taxonomic composition, and MGE inventory that targeted qPCR can't see.

**Key design decisions:**

- **`amr_profiler` + `amr_database` + `amr_database_version`** are separate fields because the same tool (e.g., ABRicate) can use different databases (CARD, ResFinder, NCBI). The database version matters enormously — running the same reads against CARD v3.2 vs v3.3 can produce different gene calls.

- **`amr_profile_path`** should point to a hAMRonization-compatible output file. This is the bridge to JACKPOT's planned AMR analysis module and ensures interoperability with the broader PHA4GE ecosystem.

- **`arg_reads_per_million`** is the simplest cross-sample normalization metric. More sophisticated approaches exist (e.g., RPKM per gene, coverage-based abundance), but RPM is universally calculable and comparable.

- **`integron_types_detected`** and **`plasmid_replicon_types`** are explicitly called out because Djordjevic et al. make a compelling case that class 1 integrons and specific plasmid types (IncHI2, IncX3, IncF) are the primary vehicles for CRR (complex resistance region) mobilization across Enterobacteriaceae. Tracking these at the metagenomic level provides early warning of emerging resistance plasmid spread.

- **MAG quality fields** follow MIMAG standards. The advent of long-read metagenomics (metaFlye, etc.) is enabling recovery of complete plasmid sequences from wastewater for the first time — a capability Djordjevic et al. highlight as previously impossible with short reads.

---

## NWSS Compatibility Mapping

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

---

## WHO Tricycle Protocol Compatibility

The WHO Tricycle protocol specifies ESBL-producing *E. coli* as the indicator organism for One Health AMR surveillance across human, animal, and environmental sectors. For the environmental sector, the protocol recommends sampling at WWTP influent points.

This schema supports Tricycle-compatible environmental sampling through:

- **`WastewaterCollectionSite.site_type = wastewater_treatment_plant`** with **`WastewaterSample.treatment_stage = influent_raw`** matches the Tricycle environmental sampling specification.
- **`WastewaterTargetResult`** can capture ESBL-specific qPCR targets (e.g., blaCTX-M group-specific assays).
- **`WastewaterMetagenomicProfile`** captures the broader resistome context that Djordjevic et al. argue is essential — the Tricycle protocol's restriction to ESBL *E. coli* alone may miss critical plasmid-mediated resistance dynamics.

---

## Sequencing Density and Timeliness Metrics

Struelens et al. (2024, Figure 5) establish that the public health utility of genomic surveillance data is a function of both sampling density and timeliness. For wastewater, these metrics should be tracked at the `WastewaterCollectionSite` level:

| Metric | Definition | Target (from Rockefeller Framework) |
|---|---|---|
| Sampling frequency | Collections per week per site | 2-3x/week for WWTP, 1x/week for upstream |
| Turnaround: collection → qPCR result | Calendar days | 3-5 days |
| Turnaround: collection → sequence upload | Calendar days | 10 days |
| Turnaround: collection → variant deconvolution | Calendar days | 7-14 days |
| Geographic coverage | % of state population covered by active sites | >50% |

These are not schema fields but should be computed as dashboard KPIs from the `collection_date`, `analysis_date`, and site population data.

---

## Future Extensions

Things explicitly deferred from v0.1.0 that should be addressed in subsequent versions:

1. **`UpstreamContributor` entity** — Formalize the relationship between collection sites and known upstream sources (hospitals, farms, industrial facilities). This is the bridge to full One Health source attribution.

2. **`WastewaterTimeseriesSummary`** — Pre-computed trend metrics (7-day rolling average, week-over-week change, trend classification) for dashboard consumption without requiring full re-query of all target results.

3. **Spatial/GIS integration** — Sewershed polygon geometries stored as GeoJSON or linked to external shapefiles. Enables map-based visualization of wastewater signals overlaid with clinical case data.

4. **Multi-site composite** — Some surveillance programs pool samples from multiple upstream sites before analysis. The schema doesn't currently model this "sample of samples" relationship.

5. **Cost tracking** — Per-sample and per-analysis cost fields to support the cost-effectiveness evaluations that Struelens et al. emphasize are needed to build the business case for sustained wastewater surveillance funding.

6. **Environmental AMR risk scoring** — Computed fields that combine ARG abundance, MGE presence, and environmental context into risk scores per the framework proposed by Liguori et al. (2022) for standardized AMR monitoring in water environments.
