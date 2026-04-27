# JACKPOT — Template System Design & APGAP Template Audit

**Document version:** 1.0
**Last updated:** 2026-04-15
**Author:** the maintainer
**Companion documents:**

- `jackpot_architecture.md` — Architecture & Developer Reference v5.0
- `jackpot_session_summary_and_backlog.md` — Session summary & backlog

---

## Table of Contents

1. [APGAP Template Audit](#1-apgap-template-audit)
2. [Failure Mode Catalog](#2-failure-mode-catalog)
3. [JACKPOT Template System Design](#3-jackpot-template-system-design)
4. [Template Generator Architecture](#4-template-generator-architecture)
5. [Tier Logic Reference](#5-tier-logic-reference)
6. [Metagenomics Support](#6-metagenomics-support)
7. [API, CLI, and SDK Interfaces](#7-api-cli-and-sdk-interfaces)
8. [XLSX Generation (Month 2)](#8-xlsx-generation-month-2)
9. [SPSP-Inspired Backlog Items](#9-spsp-inspired-backlog-items)
10. [Migration Path from APGAP Templates](#10-migration-path-from-apgap-templates)

---

## 1. APGAP Template Audit

### Files reviewed

| File | Type | Sheets | Columns | Data Rows | Data Validations |
|---|---|---|---|---|---|
| `all_sequences_template.xlsx` | Template | Metadata, Lists | 26 | 0 (empty) | None — no dropdown validation on Metadata sheet |
| `human_host_template.xlsx` | Template | Metadata, Lists | 36 | 0 (empty, 99 blank rows pre-allocated) | 22 data validations — dropdown lists, date pickers |
| `sequences_human_template.xlsx` | Template | Metadata, Lists | 36 | 0 | Not checked (superseded by updated human_host_template) |
| `human_host_metadata.xlsx` | Data dictionary | Human Host | 7 | 10 | N/A (documentation, not template) |
| `csv_template.xls` | Legacy template | csv_template | 36 | 0 | Unknown (`.xls` format) |
| `csv_template_pertussis.csv` | Template | (flat CSV) | 37 | 5 example rows | N/A (CSV has no validation) |
| `covid-19-example.csv` | Example data | (flat CSV) | 36 | 6 example rows | N/A |
| `Phase2-APGAP_Metadata_Requirements.xlsx` | Requirements doc | 19 sheets | varies | varies | N/A (documentation) |

### Updated findings — `human_host_template.xlsx` (latest version)

The updated `human_host_template.xlsx` is a **combined sequences + human host template** with 36 columns (columns A–Z are sequence metadata, columns AA–AJ are human host metadata). This is a significant improvement over the earlier two-file model (`all_sequences_template.xlsx` + separate `human_host_template.xlsx`) because it eliminates the need to join two files on Sample ID.

**Data validations present (22 total):**

| Column | Header | Validation Type | Source |
|---|---|---|---|
| B | Pathogen/organism name | List dropdown | Lists!$B$1:$B$4 (4 organisms) |
| C | FASTQ filename | List dropdown | Lists!$C$1:$C$8 (8 extensions) |
| D | Type of experiment | List dropdown | Lists!$D$1:$D$5 (5 types) |
| E | Nucleic acid extraction method | List dropdown | Lists!$E$1:$E$5 |
| F | Library preparation method | List dropdown | Lists!$F$1:$F$3 |
| G | Sequencing protocol | List dropdown | Lists!$G$1:$G$3 |
| H | Sequencing instrument | List dropdown | Lists!$H$1:$H$7 |
| I | Date Collected | Date picker | Min: 1900-01-01 |
| J | Date Sequenced | Date picker | Min: 1900-01-01 |
| L | Collection facility | List dropdown | Lists!$L$1:$L$4 (4 facilities) |
| M | Purpose for collection | List dropdown | Lists!$M$1:$M$5 |
| N | Source type | List dropdown | Lists!$N$1:$N$12 (12 types) |
| O | Source Location Country | List dropdown | Lists!$O$1:$O$14 (14 countries) |
| P | Source Location State | List dropdown | Lists!$P$1:$P$95 (95 states/provinces) |
| Q | Source Location County | List dropdown | Lists!$Q$1:$Q$15 (15 AZ counties) |
| U | Intermediary clinical lab name | List dropdown | Lists!$U$1:$U$2 |
| V | Other Testing Performed | List dropdown | Lists!$V$1:$V$2 |
| W | Ct value | List dropdown | Lists!$W$1:$W$2 (min/max labels) |
| AB | Biospecimen type | List dropdown | Lists!$AB$1:$AB$4 |
| AC | Reason for sample collection | List dropdown | Lists!$AC$1:$AC$2 |
| AD | Sex | List dropdown | Lists!$AD$1:$AD$6 |
| AH | Disease | List dropdown | Lists!$AH$1:$AH$2 |

**What improved from the earlier version:**

- Combined template (sequences + human host in one file) eliminates join complexity
- Excel data validation dropdowns on 22 of 36 columns
- Date picker validation on Date Collected and Date Sequenced columns
- Pre-allocated 99 blank rows with validation applied
- Source type dropdown includes all 12 One Health source types

**What is still wrong (see Failure Mode Catalog below):**

- Only 4 organisms in the dropdown (SARS-CoV-2, Influenza, Candida auris, Salmonella spp) — JACKPOT has 62
- Only 4 collection facilities — should be a DB-managed lookup, not static
- Only 14 countries in dropdown
- Only 15 state counties — missing example counties (the three most populated)
- Sex values include redundant entries: Male/Female/DSD AND M/F/DSD (6 values for 3 concepts)
- Ct value "validation" is just two cells containing the text "minimum value: 0" and "maximum value: 50" — not actual numeric validation
- `FASTQ filename` column (C) has file extension validation but not filename pattern validation
- Row 2 is still "REQUIRED"/"OPTIONAL" text — no tier awareness
- No example data row
- `Sequencing lab (originating lab)` (column K) has no data validation at all — free text
- Typo in Lists sheet: "llumina iSeq100" (missing the "I")

### Updated findings — `all_sequences_template.xlsx` (latest version)

The `all_sequences_template.xlsx` has 26 columns (sequence metadata only, no host data) with **no data validations on the Metadata sheet**. The Lists sheet has enum values in parallel columns but they are not wired to the Metadata sheet cells. This is the "base template" that other source-type templates build on, but without validation it provides no guardrails.

### Source type values in APGAP vs JACKPOT

| APGAP Source Type Value | JACKPOT SourceTypeEnum |
|---|---|
| human | Human |
| wildlife host | Wildlife |
| companion animal host | CompanionAnimal |
| livestock (ag animal) host | Livestock |
| vector | Vector |
| wastewater | Wastewater |
| water | Water |
| air | Air |
| soil | Soil |
| surface | Surface |
| food product | Food |
| ag produce | ProduceAg |
| *(not present)* | Other |

---

## 2. Failure Mode Catalog

Eight distinct failure modes identified across all APGAP templates:

### FM-1: Same field, different names across templates

The same conceptual field has different column header strings in different templates, breaking any parser that relies on name-based matching.

| Field Concept | COVID Template | Pertussis Template | Human Host Template |
|---|---|---|---|
| FASTQ file | `FASTQ filename` | `filename` | `FASTQ filename` |
| Age | `Age (years)` | `AGE (IN YEARS)` | `Age (years)` |
| External Case ID | `operator-issued ID (links with the external case-management system)` | `OPERATOR-ISSUED ID` | `operator-issued ID (links with the external case-management system)` |
| Contact | `Contact (if other than user uploading data)` | `CONTACT (OTHER THAN UPLOADED DATA)` | `Contact (if other than user uploading data)` |
| Source type | `Source type` | *(missing)* | `Source type` |

**JACKPOT fix:** Field names are `snake_case` identifiers generated from the LinkML schema. The template CSV row 1 uses these exact identifiers. The harmonizer maps legacy names for backward compatibility, but schema-generated templates use canonical names exclusively.

### FM-2: Column order varies between templates

Position-based parsing is impossible because the same field appears in different column positions across templates.

| Field | COVID Column | Pertussis Column |
|---|---|---|
| Sample ID | 0 | 1 |
| FASTQ filename | 2 | 0 |
| Sequencing protocol | 6 | 22 |
| Source Location Country | 14 | 12 |

**JACKPOT fix:** Templates are generated from the same ordered field list. Column order is always: BaseSample required → BaseSample optional → source-type-specific required → source-type-specific optional.

### FM-3: Duplicate and contradictory requirements sheets

The Phase2 requirements workbook has 19 sheets with six pairs of near-duplicates:

| Pair A | Pair B | Difference |
|---|---|---|
| Vectors (9 rows, 7 cols) | Vector (11 rows, 6 cols) | Different column count, different row count |
| Livestock Ag animal host (1006 rows, 28 cols) | Livestock (Ag Animal) host (13 rows, 6 cols) | 1006 vs 13 rows — appears to include data |
| Produce Ag (999 rows, 7 cols) | Ag Produce (14 rows, 6 cols) | Same pattern |
| Food-Product (11 rows, 7 cols) | Food product (11 rows, 6 cols) | Column count differs |
| Soil (14 rows, 6 cols) | Soil sample (999 rows, 27 cols) | 14 vs 999 rows |
| Water (11 rows, 6 cols) | Water sample (999 rows, 26 cols) | Same pattern |

Nobody knows which sheet in each pair is canonical.

**JACKPOT fix:** One LinkML YAML schema → one JSON Schema → one template generator. No hand-maintained requirements sheets.

### FM-4: Binary REQUIRED/OPTIONAL with no tier awareness

Row 2 of every template contains the literal text "REQUIRED" or "OPTIONAL" in every cell. There is no gradient — no way to indicate that a field is optional for basic ingest but required for GISAID submission, or required for dashboard analytics but not for initial upload. This is the root cause of APGAP's DRAFT backlog: labs that can't fill all 17 REQUIRED fields submit nothing, even though a partial record would be immediately useful.

**JACKPOT fix:** Three-tier quality system (PRELIMINARY → ANALYZABLE → SUBMITTABLE). Template row 3 uses four tags: `REQUIRED` (needed at Tier 1), `ANALYZABLE` (needed at Tier 2), `SUBMITTABLE` (needed at Tier 3), `OPTIONAL` (never blocks ingest or tier promotion).

### FM-5: Flat merged template with no section boundaries

The combined `human_host_template.xlsx` is 36 columns with no visual separation between sequence metadata (cols 1–26) and human host metadata (cols 27–36). Labs must scroll right to find host-specific fields, and there's no indication of which columns are common to all source types vs. specific to human samples.

**JACKPOT fix:** Template columns are ordered and labeled: `[BaseSample fields | source-type-specific fields]`. CSV row 2 provides human-readable labels. When XLSX generation is added (Month 2), section headers and color coding will visually separate the two regions.

### FM-6: Enum validation present but incomplete

The updated `human_host_template.xlsx` has 22 data validations, which is a significant improvement. However, enum lists are incomplete and in some cases inaccurate:

- Organism dropdown has only 4 values (SARS-CoV-2, Influenza, Candida auris, Salmonella spp). JACKPOT's `OrganismNameEnum` has 62 values plus `metagenome` and `novel pathogen`.
- Collection facility dropdown has only 4 values. This should be a DB-managed lookup, not a static list.
- Sex values include redundant entries (Male + M, Female + F, DSD + Differences of Sex Development = 6 values for 3 concepts).
- County dropdown has only 15 of the state's 15 counties but some names don't match standard spellings.
- Ct value "validation" is text labels ("minimum value: 0", "maximum value: 50"), not actual numeric range validation.
- Typo: "llumina iSeq100" (missing the "I" in Illumina).

**JACKPOT fix:** Enum values are generated from the LinkML schema. The companion `_enums.json` file provides the complete, current value set for every enum field. XLSX data validation dropdowns are generated programmatically from the same source.

### FM-7: No example data row

No template contains a pre-filled example row showing what correctly formatted data looks like. The COVID example CSV has data, but with problems: US-format dates ("12/1/25"), ALL CAPS values ("SONORA QUEST", "HONORHEALTH"), organism names that don't match NCBI Taxonomy ("COVID19" instead of "SARS-CoV-2" in the Disease field), and "EXAMPLE COUNTY" (with "COUNTY" appended).

**JACKPOT fix:** Template row 5 is always a pre-filled example row with correctly formatted values. ISO 8601 dates, NCBI Taxonomy organism names, controlled vocabulary values matching the schema enums exactly.

### FM-8: Hand-maintained, not generated

Every APGAP template is a manually created Excel file. When a field is added to the schema, someone must manually update every relevant template, every Lists sheet, and every example row. The inconsistencies in FM-1 through FM-7 are the inevitable result of this approach.

**JACKPOT fix:** Templates are generated artifacts from the LinkML schema. The generator script is the single source of truth. No hand-maintained template files exist in the repository.

---

## 3. JACKPOT Template System Design

### Core principle

**Templates are generated artifacts, not authored documents.** They come from the LinkML schema the same way Pydantic models, JSON Schema, and SQL DDL do — one source of truth, many outputs.

### The complexity reduction

APGAP had 19 hand-maintained sheets because each source type × data category was treated as a separate document. JACKPOT's inheritance model solves this:

- `BaseSample` has ~25 fields common to **all** source types
- Each source-type subclass adds only **5–15 unique fields**
- Metagenomics is handled as an **overlay** (additional MAG fields), not a separate source type

So instead of 19 monolithic flat spreadsheets, we have **one generator** that produces a right-sized CSV:

```
[BaseSample columns for target tier] + [source-type-specific columns] + [metagenomics overlay if requested]
```

### Two axes of template generation

Templates are generated along two orthogonal axes:

**Axis 1 — Source type** (determines which columns appear):

| Source Type | Schema Class | Unique Fields Added |
|---|---|---|
| human | HumanSample | external_case_id, biospecimen_type, host_age, host_sex, host_species, disease, isolation_source, isolate, reason_for_collection |
| companion_animal | CompanionAnimalSample | host_species, subject_id, breed, age_animal, sex_animal |
| wildlife | WildlifeHostSample | host_species, subject_id, capture_method |
| vector | VectorSample | vector_species, host_species, trap_type |
| livestock | LivestockSample | host_species, subject_id, herd_flock_id, production_system |
| produce | ProduceSample | plant_species, distribution_scale |
| food | FoodSample | food_location_type, food_product_type, storage_temperature |
| surface | SurfaceSample | indoor_space, indoor_surface, outdoor_surface |
| soil | SoilSample | soil_site_type, soil_depth_cm |
| water | WaterSample | water_source, water_temperature_c |
| wastewater | WastewaterSample | ~40 NWSS fields (sewershed, sample_matrix, pcr_target, etc.) |
| air | AirSample | air_source, airflow_rate |

**Axis 2 — Target tier** (determines which columns are included and how they're tagged):

| Tier | Columns Shown | Use Case |
|---|---|---|
| PRELIMINARY | ~15 BaseSample required fields + source-type required fields | "Get data in fast — I'll add details later" |
| ANALYZABLE | PRELIMINARY + geographic and date precision fields | "I want this on the dashboard" |
| SUBMITTABLE | All fields including NCBI/GISAID requirements + OPTIONAL fields | "I'm submitting to public repositories" |

### Metagenomics overlay

Metagenomics is **not a source type** — it's an experiment type that can apply to any source type. A wastewater metagenome, a soil metagenome, and a clinical metagenome all have different source-type fields but share the same metagenomic-specific fields. The template generator handles this with a `--metagenomics` flag:

```
jackpot templates generate --source-type wastewater --tier ANALYZABLE --metagenomics
```

This adds the metagenomics overlay fields to the template:

| Field | Description |
|---|---|
| `target_organisms` | Semicolon-separated list of target organisms (for targeted metagenomics) |
| `assembly_type` | `mag`, `sag`, `co_assembly`, or `isolate` |
| `mag_completeness_pct` | CheckM2 completeness (0–100) |
| `mag_contamination_pct` | CheckM2 contamination (0–100) |
| `mag_strain_heterogeneity` | CheckM2 strain heterogeneity score |

When `--metagenomics` is set, the generator also pre-fills `organism_name` with `metagenome` in the example row and sets `type_of_experiment` to `shotgun_DNA_sequencing`.

---

## 4. Template Generator Architecture

### New file: `backend/template_generator.py`

Single source of truth for all template generation. Reads the LinkML-generated JSON Schema and produces CSV templates dynamically.

### CSV structure (5 header rows + data)

```
Row 1: JACKPOT field names (snake_case — matches API, DB, and harmonizer)
Row 2: Human-readable labels
Row 3: Tier requirement tag (REQUIRED | ANALYZABLE | SUBMITTABLE | OPTIONAL)
Row 4: Validation hint (enum values, date format, numeric range, etc.)
Row 5: Pre-filled example data row
Row 6+: Empty data rows (user fills these in)
```

### Why 5 header rows?

- **Row 1 (field names):** The harmonizer and ingest API use these exact strings. Labs that use the generated template bypass the harmonizer entirely — zero column-name mapping needed.
- **Row 2 (labels):** Human-readable for labs that aren't comfortable with `snake_case`. Also serves as documentation.
- **Row 3 (tier tags):** Tells the lab exactly what level of completeness each field contributes to. A lab aiming for ANALYZABLE knows to fill everything tagged REQUIRED and ANALYZABLE.
- **Row 4 (validation hints):** Shows the first 5 enum values with total count, or the expected format (ISO 8601, integer, etc.). Labs can use this as inline documentation without switching to a separate data dictionary.
- **Row 5 (example):** A correctly formatted example row. Labs can see exactly what good data looks like.

### Companion output: `_enums.json`

For each template, an optional companion JSON file lists all enum values for every constrained field:

```json
{
  "organism_name": {
    "label": "Organism Name",
    "values": ["SARS-CoV-2", "Influenza A virus", "Salmonella enterica", "..."],
    "required_at_tier": "REQUIRED"
  },
  "source_type": {
    "label": "Source Type",
    "values": ["Human", "Wildlife", "CompanionAnimal", "..."],
    "required_at_tier": "REQUIRED"
  }
}
```

Labs can use this JSON for LIMS integration, custom validation scripts, or building their own intake forms.

---

## 5. Tier Logic Reference

The tiers describe what a sample is **capable of being used for**, not a strict linear ladder. SUBMITTABLE and ANALYZABLE are partially orthogonal — a sample can be SUBMITTABLE (all fields present for NCBI/GISAID) without being ANALYZABLE (which requires month-or-better date precision for time-series analytics). This is by design: a researcher with year-only collection dates but complete metadata should be able to submit to public repositories. This section is the canonical reference for template generation and must stay synchronized with `validator.py` and `compute_quality_status()`.

### Why SUBMITTABLE has no date precision constraint

NCBI BioSample explicitly accepts partial collection dates. Their documentation states that `collection_date` supports "DD-Mmm-YYYY", "Mmm-YYYY", and "YYYY" formats, plus ISO 8601 variants "YYYY-mm-dd" and "YYYY-mm". GISAID's EpiCoV database also accepts YYYY-MM and YYYY in the Collection date field. Neither repository requires day-level precision for submission. JACKPOT's SUBMITTABLE tier therefore checks **field presence**, not date precision.

Date precision only gates ANALYZABLE, where month-or-better resolution is needed for meaningful time-series charts and MMWR epiweek computation.

### Tier 1 — PRELIMINARY

**What it means:** Minimum viable metadata. The sample is immediately ingestible, searchable, and available for pipeline runs. May lack date precision, geographic detail, or full source-type fields.

**Required fields:**

| Field | Type | Notes |
|---|---|---|
| `sample_id` | string | Unique identifier provided by uploader |
| `organism_name` | OrganismNameEnum | NCBI Taxonomy name or `metagenome` |
| `source_type` | SourceTypeEnum | One Health source type |
| `type_of_experiment` | ExperimentTypeEnum | WGS, amplicon, shotgun, etc. |
| `nucleic_acid_extraction_method` | string | Free text (multivalued) |
| `library_preparation_method` | string | Free text |
| `sequencing_protocol` | string | URL or free text |
| `sequencing_platform` | SequencingPlatformEnum | Illumina, Oxford_Nanopore, PacBio, etc. |
| `sequencing_lab` | DB-managed lookup | Runtime validation against sequencing_labs table |
| `date_collected` | date | ISO 8601. Year-only precision (`YYYY-01-01`) is accepted at this tier |
| `date_sequenced` | date | ISO 8601 |
| `collection_facility` | string | Free text |
| `purpose_for_collection` | string | Free text |
| `collection_location_country` | string | Free text at Tier 1 and 2. INSDC-approved at Tier 3 |
| `sector` | SectorEnum | clinical, veterinary, agricultural, environmental, etc. |

**Date precision:** Year-only dates are accepted. `date_collected_precision` = `year` is valid. Epiweek computation is suppressed.

**What PRELIMINARY unlocks:** Basic search, pipeline runs, file storage, audit trail.

### Tier 2 — ANALYZABLE

**What it means:** Sufficient metadata for epidemiological analysis. The sample appears in time-series charts, geographic maps, and epiweek-stratified dashboards.

**Additional requirements beyond PRELIMINARY:**

| Field | Type | Notes |
|---|---|---|
| `collection_location_state` | string | State/province of sample collection |

**Date precision constraint:** `date_collected_precision` must be `month` or `day` (not `year`). A year-only date stays at PRELIMINARY even if `collection_location_state` is populated, because time-series analytics require at least month resolution.

**What ANALYZABLE unlocks:** Time-series charts (requires at least month precision), geographic aggregation by state, MMWR epiweek computation (month precision uses mid-month estimate with warning; day precision is exact).

### Tier 3 — SUBMITTABLE

**What it means:** All metadata fields required by NCBI BioSample, GISAID EpiCoV, and NWSS are present. The sample is ready for automated submission to public repositories.

**Additional field requirements beyond PRELIMINARY:**

| Field | Type | Notes |
|---|---|---|
| `originating_lab` | string | Lab that collected the original sample |
| `submitting_lab` | string | Lab that uploaded to JACKPOT |
| `collection_location_state` | string | State/province of sample collection |
| `collection_location_county` | string | County/district of collection |
| `host_age` | integer | **HumanSample only** — skipped for non-human source types |
| `host_sex` | string | **HumanSample only** — skipped for non-human source types |

**Date precision:** No additional constraint. NCBI accepts YYYY, YYYY-MM, and YYYY-MM-DD. GISAID accepts the same. A year-only sample with all other fields present is SUBMITTABLE.

**What SUBMITTABLE unlocks:** NCBI BioSample/SRA submission (via TOSTADAS), GISAID EpiCoV export, NWSS reporting (wastewater samples).

### The SUBMITTABLE + year-only scenario

A sample can be SUBMITTABLE but not ANALYZABLE. Example: a researcher has archived samples from 2019 where only the collection year is known, but all other metadata (originating lab, state, county, host demographics) are complete. This sample:

- Is SUBMITTABLE — all required fields present, NCBI/GISAID will accept year-only dates
- Is NOT ANALYZABLE — cannot appear in monthly time-series or epiweek charts (year resolution is too coarse)
- IS usable in pipelines — pipeline access is gated at PRELIMINARY, not ANALYZABLE

The `compute_quality_status()` function checks SUBMITTABLE first. If a sample meets SUBMITTABLE, it gets that label regardless of date precision. ANALYZABLE is only checked if the sample doesn't meet SUBMITTABLE.

### Tier decision tree (from `compute_quality_status()`)

```python
def compute_quality_status(data: dict, validation_result: ValidationResult) -> str:
    """
    Compute the quality tier from a validated sample dict.

    Tier priority: SUBMITTABLE > ANALYZABLE > PRELIMINARY.
    SUBMITTABLE is checked first because it has no date precision constraint —
    NCBI and GISAID accept year-only, month-only, and day-precision dates.
    ANALYZABLE requires month-or-better precision for time-series analytics.
    """
    if not validation_result.valid:
        return "PRELIMINARY"

    # Check Tier 3 — SUBMITTABLE (all submission fields present, any date precision)
    tier3_fields = [
        "originating_lab",
        "submitting_lab",
        "collection_location_state",
        "collection_location_county",
    ]
    # host_age and host_sex only required for HumanSample
    if data.get("source_type") == "Human":
        tier3_fields.extend(["host_age", "host_sex"])

    if all(data.get(f) for f in tier3_fields):
        return "SUBMITTABLE"

    # Check Tier 2 — ANALYZABLE (date precision + geographic fields)
    precision = data.get("date_collected_precision", "day")
    tier2_fields = ["collection_location_state"]
    if precision != "year" and all(data.get(f) for f in tier2_fields):
        return "ANALYZABLE"

    return "PRELIMINARY"
```

### Tier-to-template mapping summary

| Tier | Date Precision Required | Geographic Fields Required | Source-Type Fields Required | Labs Fields Required |
|---|---|---|---|---|
| PRELIMINARY | Year OK | Country only | None beyond BaseSample required | None |
| ANALYZABLE | Month or Day | Country + State | None beyond BaseSample required | None |
| SUBMITTABLE | Any (year, month, or day) | Country + State + County | host_age + host_sex (human only) | originating_lab + submitting_lab |

### Tier capability matrix

This matrix shows what each tier unlocks. A sample gets the **highest** tier it qualifies for.

| Capability | PRELIMINARY | ANALYZABLE | SUBMITTABLE |
|---|---|---|---|
| Stored in JACKPOT | Yes | Yes | Yes |
| Searchable | Yes | Yes | Yes |
| Pipeline runs (assembly, typing, AMR) | Yes | Yes | Yes |
| Time-series charts (monthly/weekly) | No | Yes | Yes (if month+ precision) |
| MMWR epiweek computation | No | Yes | Yes (if month+ precision) |
| Geographic aggregation by state | No | Yes | Yes |
| NCBI BioSample/SRA submission | No | No | Yes |
| GISAID EpiCoV export | No | No | Yes |
| NWSS reporting (wastewater) | No | No | Yes |

---

## 6. Metagenomics Support

### Why metagenomics is an overlay, not a source type

In the JACKPOT schema, `metagenome` is a value in `OrganismNameEnum`, not a value in `SourceTypeEnum`. A metagenomic sample still has a physical source — wastewater, soil, a human clinical specimen — and that source determines which source-type-specific fields are relevant. Metagenomics adds additional fields *on top of* whatever source type applies.

This means:

- A clinical metagenome = `source_type: Human` + `organism_name: metagenome`
- A wastewater metagenome = `source_type: Wastewater` + `organism_name: metagenome`
- A soil metagenome = `source_type: Soil` + `organism_name: metagenome`

### Metagenomics-specific schema fields

These fields exist on `BaseSample` and are relevant when `organism_name = metagenome`:

| Field | Type | Description |
|---|---|---|
| `target_organisms` | OrganismNameEnum[] | Pathogen(s) specifically targeted. Empty = untargeted metagenomics |
| `assembly_type` | AssemblyTypeEnum | `mag`, `sag`, `co_assembly`, or `isolate` |
| `mag_completeness_pct` | float | CheckM2 completeness (0–100). Only when `assembly_type` = mag/sag |
| `mag_contamination_pct` | float | CheckM2 contamination (0–100). Only when `assembly_type` = mag/sag |
| `mag_strain_heterogeneity` | float | CheckM2 strain heterogeneity |

### Surveillance relevance for metagenomics

The `compute_surveillance_relevant()` function has special handling:

- If `target_organisms` is populated: `surveillance_relevant = TRUE` if any target organism is in the `reportable_organisms` table
- If `target_organisms` is empty (untargeted): `surveillance_relevant = TRUE` conservatively (can be overridden by Lab Director via `untargeted_metagenome_research` override category)

### Template generator flag

```
GET /api/v1/templates/?source_type=wastewater&tier=ANALYZABLE&metagenomics=true
```

or CLI:

```bash
jackpot templates generate --source-type wastewater --tier ANALYZABLE --metagenomics
```

When `metagenomics=true`:

1. `target_organisms` column is added after `organism_name`
2. `assembly_type`, `mag_completeness_pct`, `mag_contamination_pct`, `mag_strain_heterogeneity` are added at the end
3. Example row pre-fills `organism_name` = `metagenome` and `type_of_experiment` = `shotgun_DNA_sequencing`

---

## 7. API, CLI, and SDK Interfaces

### API endpoint

```
GET /api/v1/templates/
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `source_type` | string (required) | — | One of: human, companion_animal, wildlife, vector, livestock, produce, food, surface, soil, water, wastewater, air |
| `tier` | string | ANALYZABLE | PRELIMINARY, ANALYZABLE, or SUBMITTABLE |
| `metagenomics` | boolean | false | Include metagenomics overlay fields |
| `format` | string | csv | csv or xlsx (xlsx = Month 2) |

```
GET /api/v1/templates/enums
```

Returns JSON with all enum values for the specified source_type and tier.

```
GET /api/v1/templates/source-types
```

Returns the list of available source types with their schema class names.

### CLI

```bash
# Generate a CSV template for human clinical samples at ANALYZABLE tier
jackpot templates generate --source-type human --tier ANALYZABLE

# Generate a SUBMITTABLE-ready template for wastewater metagenomics
jackpot templates generate --source-type wastewater --tier SUBMITTABLE --metagenomics

# Also download the companion enums JSON
jackpot templates generate --source-type human --tier SUBMITTABLE --with-enums

# List available source types
jackpot templates list-source-types
```

### SDK

```python
from jackpot import Session

session = Session()

# Generate and download a template
template_path = session.templates.generate(
    source_type="human",
    tier="ANALYZABLE",
    output="human_analyzable_template.csv",
)

# Get enum values for a template
enums = session.templates.enums(source_type="human", tier="ANALYZABLE")
print(enums["organism_name"]["values"][:5])
```

### No auth required

Template endpoints are public — no authentication needed. Templates contain only schema structure, not data. This allows labs to download templates before they even have a JACKPOT account.

---

## 8. XLSX Generation (Month 2)

Month 2 extension using `openpyxl`:

- **Color-coded tier columns:** Green = REQUIRED, Yellow = ANALYZABLE, Blue = SUBMITTABLE, Gray = OPTIONAL
- **Excel data validation dropdowns** for all enum fields, generated from the schema
- **Hidden "Enums" reference sheet** with complete value lists (replaces APGAP's Lists sheet)
- **Date format cells** with ISO 8601 custom format (`YYYY-MM-DD`)
- **Numeric validation** on integer and float fields (age, MAG percentages, Ct values)
- **Section headers** visually separating BaseSample fields from source-type-specific fields
- **Frozen header rows** (rows 1–4 frozen so they stay visible while scrolling data)
- **Auto-width columns** for readability

---

## 9. SPSP-Inspired Backlog Items

Prioritized per user direction. B-SPSP-4 and B-SPSP-7 are highest priority.

### Immediate (Month 1)

| ID | Feature | Scope | Dependencies |
|---|---|---|---|
| **B-SPSP-4** | Schema-driven CSV template generator | `backend/template_generator.py`, `backend/routers/templates.py`, CLI command | JSON Schema generated from LinkML (already available) |
| **B-SPSP-7** | XLSX template generator with data validation | Extension of B-SPSP-4 using openpyxl | B-SPSP-4 |

### Month 2–3

| ID | Feature | Scope | Dependencies |
|---|---|---|---|
| B-SPSP-1 | Dynamic query-based projects (live surveillance filters) | `saved_query` JSONB on projects table, scheduled re-evaluation | Search endpoint implementation |
| B-SPSP-2 | Per-lab quality dashboards with turnaround time tracking | BigQuery dashboard views | BigQuery ETL (Month 3+) |
| B-SPSP-3 | Automated surveillance report generation and push | APScheduler job or Cloud Scheduler HTTP trigger | `compute_surveillance_relevant()`, report template |

### Year 2+

| ID | Feature | Scope | Dependencies |
|---|---|---|---|
| B-SPSP-5 | Formal governance documentation template (CA/DTUA) | Documentation/legal — not code | Federation discussions |
| B-SPSP-6 | ELIXIR-style community engagement (PHA4GE, CDC AMD) | Strategy — not code | Ongoing |

---

## 10. Migration Path from APGAP Templates

Labs currently using APGAP templates can continue to upload using them. The `harmonizer.py` column mapping configs handle the translation:

| APGAP Column Name | JACKPOT Schema Field |
|---|---|
| `Sample ID` | `sample_id` |
| `Pathogen/organism name (or metagenomic)` | `organism_name` |
| `FASTQ filename` | *(handled by file_detector.py, not a metadata field)* |
| `Type of experiment` | `type_of_experiment` |
| `Nucleic acid extraction method` | `nucleic_acid_extraction_method` |
| `Nucleic acid library preparation method` | `library_preparation_method` |
| `Sequencing protocol` | `sequencing_protocol` |
| `Sequencing instrument make and model` | `sequencing_platform` |
| `Date Collected` | `date_collected` (date format normalized to ISO 8601) |
| `Date Sequenced` | `date_sequenced` (date format normalized to ISO 8601) |
| `Sequencing lab (originating lab)` | `sequencing_lab` |
| `Collection facility` | `collection_facility` |
| `Purpose for collection and sequencing` | `purpose_for_collection` |
| `Source type` | `source_type` (value mapping: "human" → "Human", etc.) |
| `Source Location Country` | `collection_location_country` |
| `Source Location State` | `collection_location_state` |
| `Source Location County` | `collection_location_county` |
| `Source Location City` | `collection_location_city` |
| `Source Location Zip` | `collection_location_zip` |
| `Source Location GPS` | `collection_location_gps` |
| `operator-issued ID (links with the external case-management system)` | `external_case_id` |
| `Biospecimen type` | `biospecimen_type` |
| `Reason for sample collection` | `reason_for_collection` |
| `Sex` | `host_sex` (value mapping: "Male"/"M" → "Male", etc.) |
| `Age (years)` | `host_age` |
| `Host species` | `host_species` |
| `Disease` | `disease` |
| `Isolation source` | `isolation_source` |
| `Isolate` | `isolate` |
| `IDs of any associated samples` | `associated_sample_ids` |

Fields missing from APGAP templates that JACKPOT requires at PRELIMINARY: `sector` (auto-inferred from `source_type` where unambiguous — e.g., Human → clinical, Wastewater → wastewater).

Fields present in APGAP templates that JACKPOT handles differently:

- `FASTQ filename` → Not a metadata column. File association happens via `file_detector.py` during upload.
- `Other Testing Performed` → `other_testing_performed` (multivalued)
- `Ct value` → `ct_value` (numeric)
- `Grant number` → `grant_number`
- `Contact` → `contact_email`
- `Intermediary clinical lab name` → `intermediary_lab`

Labs transitioning to JACKPOT should download the new schema-generated templates and stop using the APGAP Excel files. The harmonizer provides backward compatibility but not forward features (tier tags, validation hints, example rows).
