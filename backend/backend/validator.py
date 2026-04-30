"""
JACKPOT LinkML validator.

Validates sample metadata dicts against jackpot_schema v4.4.
Returns a ValidationResult with valid flag, tier, field-level errors,
warnings, and per-tier missing field lists.

All ingest paths (GUI upload, CSV batch, signed URL) call validate_sample()
before writing any record to the database.

Tier system:
  Tier 1 PRELIMINARY  — BASE_REQUIRED fields present. Hard errors if absent.
                         Sample ingested immediately; pipelines can launch.
  Tier 2 ANALYZABLE   — TIER2_REQUIRED fields present + month-or-better date.
                         Eligible for time-series, epiweek, external indexing.
  Tier 3 SUBMITTABLE  — TIER3_REQUIRED fields present (any date precision).
                         NCBI BioSample/SRA and GISAID submission enabled.

A sample can be SUBMITTABLE but not ANALYZABLE (year-only date + all fields).
This is by design: NCBI/GISAID accept YYYY dates; epiweeks require day/month.
"""

from dataclasses import dataclass, field
from datetime import date

from jackpot_schema import SCHEMA_YAML_PATH as SCHEMA_PATH

# ── Tier 1 (PRELIMINARY) — hard errors if absent ──────────────────────────
# Minimum to identify the sample, its pathogen, its origin, and its
# sequencing technology. sector is excluded — auto-derived from source_type
# at ingest (see SECTOR_FROM_SOURCE_TYPE below).
BASE_REQUIRED = [
    "sample_id",
    "organism_name",
    "source_type",
    "date_collected",
    "collection_location_country",
    "sequencing_platform",
    "type_of_experiment",
]

# ── Tier 2 (ANALYZABLE) — stored in tier2_missing, not hard errors ────────
# Required for epidemiological analysis, pipeline routing, and external
# database indexing. Missing fields are tracked in tier2_missing; ingest
# proceeds at PRELIMINARY.
TIER2_REQUIRED = [
    "sequencing_lab",
    "collection_facility",
    "library_preparation_method",
    "nucleic_acid_extraction_method",
    "date_sequenced",
    "collection_location_state",
]

# ── Tier 3 (SUBMITTABLE) — stored in tier3_missing, not hard errors ───────
# Required for NCBI BioSample/SRA and GISAID submission. Missing fields are
# tracked in tier3_missing; ingest proceeds at PRELIMINARY or ANALYZABLE.
TIER3_REQUIRED = [
    "sequencing_protocol",
    "purpose_for_collection",
    "originating_lab",
    "submitting_lab",
    "collection_location_county",
]

# Human-specific additional Tier 3 fields
TIER3_REQUIRED_HUMAN = [
    "host_age",
    "host_sex",
]

# ── Sector auto-derivation ─────────────────────────────────────────────────
# sector is derived from source_type at ingest. Researchers only need to
# explicitly supply sector when it cannot be inferred — specifically
# sector = "research" for non-surveillance samples. If a researcher supplies
# a valid sector it overrides the auto-derived value.
SECTOR_FROM_SOURCE_TYPE: dict[str, str] = {
    "Human": "clinical",
    "Wildlife": "wildlife",
    "CompanionAnimal": "veterinary",
    "Livestock": "veterinary",
    "Vector": "vector",
    "Wastewater": "wastewater",
    "Water": "environmental",
    "Air": "environmental",
    "Soil": "environmental",
    "Surface": "environmental",
    "Food": "agricultural",
    "ProduceAg": "agricultural",
}

# ── Source-type-specific Tier 1 required fields ───────────────────────────
SOURCE_REQUIRED: dict[str, list[str]] = {
    "Human": ["external_case_id", "biospecimen_type", "reason_for_collection", "host_disease"],
    "Wildlife": ["host_species", "biospecimen_type", "host_disease"],
    "CompanionAnimal": ["host_species", "biospecimen_type", "host_disease"],
    "Livestock": ["host_species", "biospecimen_type", "livestock_products", "host_disease"],
    "Vector": ["vector_species", "biospecimen_type"],
    "Wastewater": [
        "population_served",
        "sample_type",
        "sample_matrix",
        "pretreatment",
        "concentration_method",
        "flow_rate_mgd",
    ],
    "Water": ["water_temperature_c", "turbidity_ntu", "ph", "salinity_ppm"],
    "Air": ["air_source", "airflow_rate_m3_s", "pm25_ug_m3", "pm10_ug_m3"],
    "Soil": ["soil_site_type", "sample_depth_cm"],
    "Surface": ["indoor_space", "indoor_surface", "surface_material"],
    "Food": ["food_location_type", "food_product_type"],
    "ProduceAg": ["plant_species", "produce_water_source", "near_animal_agriculture"],
    "Isolate": [],  # No source-type-specific required fields
}

# Recommended (non-required) fields that produce warnings when absent
RECOMMENDED: list[str] = [
    "strain",
    "sequencing_instrument",
    "coverage_depth",
    "genome_completeness",
]

# Valid enum values — mirror the schema enums, loaded once at import time
VALID_SHARING_LEVELS = {"PRIVATE", "LAB", "DISCOVERABLE", "PUBLIC"}
VALID_SCRUB_STATUSES = {"PENDING", "IN_PROGRESS", "COMPLETE", "FAILED", "SKIPPED"}
VALID_PII_STATUSES = {"PENDING", "COMPLETE", "PII_DETECTED", "FAILED"}
VALID_INGEST_METHODS = {"gui", "csv", "rsync", "curl", "globus"}
VALID_SOURCE_TYPES = set(SOURCE_REQUIRED.keys())
VALID_PLATFORMS = {
    "Illumina",
    "Oxford_Nanopore",
    "PacBio",
    "Ion_Torrent",
    "Other",
}
VALID_EXPERIMENT_TYPES = {
    "WGS",
    "WES",
    "RNAseq",
    "shotgun_DNA_sequencing",
    "amplicon_sequencing",
    "targeted_sequencing",
}
VALID_VADR_STATUSES = {"PASS", "FAIL", "SKIP", "PENDING"}

# Mirrors SectorEnum in jackpot_schema.yaml
VALID_SECTORS = {
    "clinical",
    "veterinary",
    "agricultural",
    "environmental",
    "wastewater",
    "wildlife",
    "vector",
    "research",
}


@dataclass
class ValidationResult:
    valid: bool
    tier: int = 1  # 1=PRELIMINARY  2=ANALYZABLE  3=SUBMITTABLE
    sector: str = ""  # derived or supplied sector value
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    tier2_missing: list[str] = field(default_factory=list)
    tier3_missing: list[str] = field(default_factory=list)


def _is_absent(val: object) -> bool:
    """Return True if a field value is missing or empty."""
    if val is None:
        return True
    if isinstance(val, str) and not val.strip():
        return True
    return bool(isinstance(val, list) and not val)


def validate_sample(data: dict) -> ValidationResult:
    """
    Validate a sample metadata dict against the JACKPOT schema.
    Returns a fully populated ValidationResult.

    errors       → ingest rejected; user must fix before re-submitting.
    warnings     → ingest proceeds; user notified, no action required.
    tier2_missing → fields needed to reach ANALYZABLE.
    tier3_missing → fields needed to reach SUBMITTABLE.
    tier         → highest tier achieved (1, 2, or 3).
    sector       → auto-derived or user-supplied sector value.
    """
    errors: list[str] = []
    warnings: list[str] = []
    tier2_missing: list[str] = []
    tier3_missing: list[str] = []

    # ── Tier 1: base required fields ──────────────────────────────────────
    for field_name in BASE_REQUIRED:
        if _is_absent(data.get(field_name)):
            errors.append(f"Missing required field: {field_name}")

    # ── Sector: auto-derive from source_type; allow explicit override ─────
    source_type = data.get("source_type", "")
    supplied_sector = data.get("sector", "")
    derived_sector = SECTOR_FROM_SOURCE_TYPE.get(source_type, "")

    if supplied_sector:
        if supplied_sector not in VALID_SECTORS:
            errors.append(
                f"Invalid sector '{supplied_sector}'. Must be one of: {sorted(VALID_SECTORS)}"
            )
        sector = supplied_sector
    else:
        sector = derived_sector  # empty string if source_type not yet validated

    # ── Enum validation ───────────────────────────────────────────────────
    if source_type and source_type not in VALID_SOURCE_TYPES:
        errors.append(
            f"Invalid source_type '{source_type}'. Must be one of: {sorted(VALID_SOURCE_TYPES)}"
        )

    platform = data.get("sequencing_platform", "")
    if platform and platform not in VALID_PLATFORMS:
        errors.append(
            f"Invalid sequencing_platform '{platform}'. Must be one of: {sorted(VALID_PLATFORMS)}"
        )

    exp_type = data.get("type_of_experiment", "")
    if exp_type and exp_type not in VALID_EXPERIMENT_TYPES:
        errors.append(
            f"Invalid type_of_experiment '{exp_type}'. "
            f"Must be one of: {sorted(VALID_EXPERIMENT_TYPES)}"
        )

    sharing = data.get("sharing_level")
    if sharing is not None and sharing not in VALID_SHARING_LEVELS:
        errors.append(
            f"Invalid sharing_level '{sharing}'. Must be one of: {sorted(VALID_SHARING_LEVELS)}"
        )

    vadr = data.get("vadr_status", "")
    if vadr and vadr not in VALID_VADR_STATUSES:
        errors.append(
            f"Invalid vadr_status '{vadr}'. Must be one of: {sorted(VALID_VADR_STATUSES)}"
        )

    # ── Date validation ───────────────────────────────────────────────────
    raw_date = data.get("date_collected")
    if raw_date:
        try:
            if isinstance(raw_date, str):
                collected = date.fromisoformat(raw_date)
            elif isinstance(raw_date, date):
                collected = raw_date
            else:
                raise ValueError("not a date")
            if collected > date.today():
                errors.append("date_collected cannot be in the future.")
            elif (date.today() - collected).days > 365 * 5:
                warnings.append(
                    "date_collected is more than 5 years in the past — "
                    "please verify this is correct."
                )
        except ValueError:
            errors.append(f"date_collected '{raw_date}' is not a valid ISO 8601 date (YYYY-MM-DD).")

    raw_seq_date = data.get("date_sequenced")
    if raw_seq_date and raw_date:
        try:
            seq_date = (
                date.fromisoformat(raw_seq_date) if isinstance(raw_seq_date, str) else raw_seq_date
            )
            if not isinstance(seq_date, date):
                raise ValueError
            if seq_date > date.today():
                errors.append("date_sequenced cannot be in the future.")
            coll = date.fromisoformat(raw_date) if isinstance(raw_date, str) else raw_date
            if seq_date < coll:
                errors.append("date_sequenced cannot be before date_collected.")
        except ValueError:
            errors.append(f"date_sequenced '{raw_seq_date}' is not a valid ISO 8601 date.")

    # ── Tier 1: source-type-specific required fields ───────────────────────
    if source_type in SOURCE_REQUIRED:
        for field_name in SOURCE_REQUIRED[source_type]:
            if _is_absent(data.get(field_name)):
                errors.append(f"Missing required field for {source_type} samples: {field_name}")

    # ── Numeric range checks ──────────────────────────────────────────────
    numeric_ranges: dict[str, tuple[float, float]] = {
        "host_age": (0, 120),
        "ct_value": (0, 50),
        "ph": (0, 14),
        "soil_ph": (0, 14),
        "turbidity_ntu": (0, 4000),
        "genome_completeness": (0, 100),
        "nextclade_qc_score": (0, 100),
    }
    for field_name, (lo, hi) in numeric_ranges.items():
        val = data.get(field_name)
        if val is not None:
            try:
                fval = float(val)
                if not (lo <= fval <= hi):
                    if field_name == "turbidity_ntu" and fval > 4000:
                        warnings.append(
                            f"turbidity_ntu={fval} is above 4000 NTU — "
                            "please confirm (possible decimal error)."
                        )
                    else:
                        errors.append(
                            f"{field_name}={fval} is outside expected range [{lo}, {hi}]."
                        )
            except (TypeError, ValueError):
                errors.append(f"{field_name} must be numeric, got '{val}'.")

    # ── URI scheme check ──────────────────────────────────────────────────
    for uri_field in ("fastq_r1_uri", "fastq_r2_uri", "consensus_fasta_uri"):
        uri = data.get(uri_field)
        if uri and not (
            uri.startswith("gs://") or uri.startswith("s3://") or uri.startswith("drs://")
        ):
            warnings.append(
                f"{uri_field} '{uri}' does not use a recognised URI scheme "
                "(expected gs://, s3://, or drs://)."
            )

    # ── Tier 2: ANALYZABLE missing fields ─────────────────────────────────
    for field_name in TIER2_REQUIRED:
        if _is_absent(data.get(field_name)):
            tier2_missing.append(field_name)

    # ── Tier 3: SUBMITTABLE missing fields ────────────────────────────────
    t3_check = list(TIER3_REQUIRED)
    if source_type == "Human":
        t3_check.extend(TIER3_REQUIRED_HUMAN)
    for field_name in t3_check:
        if _is_absent(data.get(field_name)):
            tier3_missing.append(field_name)

    # ── Recommended fields ────────────────────────────────────────────────
    for field_name in RECOMMENDED:
        if _is_absent(data.get(field_name)):
            warnings.append(
                f"Recommended field '{field_name}' is missing. "
                "Consider providing it for better data quality."
            )

    # ── Compute tier ──────────────────────────────────────────────────────
    # Tier 3 (SUBMITTABLE): no hard errors, all tier2+tier3 fields present.
    #   No date precision constraint — NCBI/GISAID accept YYYY, YYYY-MM, YYYY-MM-DD.
    # Tier 2 (ANALYZABLE): no hard errors, all tier2 fields present,
    #   date precision must be month or day (not year-only).
    # Tier 1 (PRELIMINARY): any hard errors, or tier2 fields missing.
    precision = data.get("date_collected_precision", "day")
    if not errors:
        if not tier2_missing and not tier3_missing:
            tier = 3
        elif not tier2_missing and precision != "year":
            tier = 2
        else:
            tier = 1
    else:
        tier = 1

    return ValidationResult(
        valid=len(errors) == 0,
        tier=tier,
        sector=sector,
        errors=errors,
        warnings=warnings,
        tier2_missing=tier2_missing,
        tier3_missing=tier3_missing,
    )


def compute_quality_status(validation_result: ValidationResult) -> str:
    """
    Convert a ValidationResult tier to a quality_status string.
    Called at ingest after validate_sample() — never called directly in routers.

    Tier priority: SUBMITTABLE > ANALYZABLE > PRELIMINARY.

    SUBMITTABLE has no date precision constraint — NCBI BioSample and GISAID
    both accept year-only, month-only, and day-precision collection dates.
    SUBMITTABLE gates on field presence only.

    ANALYZABLE requires month-or-better date precision for time-series
    analytics and MMWR epiweek computation.

    A sample can be SUBMITTABLE but not ANALYZABLE (e.g., year-only date
    with all other fields present). This is by design.
    """
    if validation_result.tier == 3:
        return "SUBMITTABLE"
    if validation_result.tier == 2:
        return "ANALYZABLE"
    return "PRELIMINARY"


def compute_surveillance_relevant(
    organism_name: str,
    target_organisms: list[str] | None,
    reportable_organisms: set[str],
) -> bool:
    """
    Compute surveillance_relevant from organism name and reportable set.
    Called at ingest — never called directly in routers.

    Rules:
    - If organism_name is in reportable_organisms → True
    - If organism_name is 'metagenome' and any target_organism is
      reportable → True
    - If organism_name is 'metagenome' and target_organisms is empty
      → True (conservative default for untargeted metagenomics)
    - Otherwise → False
    """
    if organism_name in reportable_organisms:
        return True

    if organism_name == "metagenome":
        if not target_organisms:
            return True  # conservative default
        return any(t in reportable_organisms for t in target_organisms)

    return False
