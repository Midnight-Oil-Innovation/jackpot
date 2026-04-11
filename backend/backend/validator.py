"""
JACKPOT LinkML validator.

Validates sample metadata dicts against jackpot_schema v4.1.
Returns a ValidationResult with valid flag, field-level errors, and warnings.

All ingest paths (GUI upload, CSV batch, signed URL) call validate_sample()
before writing any record to the database.
"""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# Schema path — relative to where the API process runs (jackpot-backend/)
SCHEMA_PATH = Path("schema/schema/jackpot_schema.yaml")

# Required fields for every sample regardless of source_type
BASE_REQUIRED = [
    "sample_id",
    "organism_name",
    "source_type",
    "sector",
    "date_collected",
    "collection_location_country",
    "sequencing_platform",
    "sequencing_lab",
    "type_of_experiment",
    "library_preparation_method",
    "sequencing_protocol",
    "collection_facility",
    "purpose_for_collection",
]

# Additional required fields per source_type
SOURCE_REQUIRED: dict[str, list[str]] = {
    "Human": ["adhs_medsis_id", "biospecimen_type", "reason_for_collection", "host_disease"],
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
}

# Recommended (non-required) fields that produce warnings when absent
RECOMMENDED: list[str] = [
    "collection_location_state",
    "strain",
    "sequencing_instrument",
    "coverage_depth",
    "genome_completeness",
]

# Valid enum values loaded once at import time
# These mirror OrganismNameEnum, SequencingPlatformEnum, SharingLevelEnum,
# ExperimentTypeEnum, ScrubStatusEnum, PIIScanStatusEnum from the schema.
# Keeping them here avoids a full LinkML parse on every request.
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

VALID_SECTORS = {
    "clinical",
    "wastewater",
    "wildlife",
    "livestock",
    "companion_animal",
    "vector",
    "environmental",
    "food",
    "research",
}


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_sample(data: dict) -> ValidationResult:
    """
    Validate a sample metadata dict against the JACKPOT schema.
    Returns ValidationResult(valid, errors, warnings).

    Errors  → ingest is rejected; user must fix before re-submitting.
    Warnings → ingest proceeds; user is notified but no action required.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ── Base required fields ──────────────────────────────────────────────
    for field_name in BASE_REQUIRED:
        val = data.get(field_name)
        if val is None or (isinstance(val, str | list) and not val):
            errors.append(f"Missing required field: {field_name}")

    # ── Enum validation ───────────────────────────────────────────────────
    source_type = data.get("source_type", "")
    if source_type and source_type not in VALID_SOURCE_TYPES:
        errors.append(
            f"Invalid source_type '{source_type}'. Must be one of: {sorted(VALID_SOURCE_TYPES)}"
        )

    sector = data.get("sector", "")
    if sector and sector not in VALID_SECTORS:
        errors.append(f"Invalid sector '{sector}'. Must be one of: {sorted(VALID_SECTORS)}")

    source_type = data.get("source_type", "")
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

    sharing = data.get("sharing_level", "")
    if sharing not in VALID_SHARING_LEVELS:
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

    # ── Source-type-specific required fields ──────────────────────────────
    if source_type in SOURCE_REQUIRED:
        for field_name in SOURCE_REQUIRED[source_type]:
            val = data.get(field_name)
            if val is None or (isinstance(val, str | list) and not val):
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

    # ── Recommended fields ────────────────────────────────────────────────
    for field_name in RECOMMENDED:
        val = data.get(field_name)
        if val is None or (isinstance(val, str) and not val):
            warnings.append(
                f"Recommended field '{field_name}' is missing. "
                "Consider providing it for better data quality."
            )

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def compute_quality_status(data: dict, validation_result: ValidationResult) -> str:
    """
    Compute the quality tier string from a validated sample dict.
    Called at ingest after validate_sample() — never called directly in routers.

    Tier 1 — PRELIMINARY: minimum viable metadata, immediately ingestible.
    Tier 2 — ANALYZABLE: date to month precision, geographic fields present.
    Tier 3 — SUBMITTABLE: all NCBI BioSample / GISAID fields present.
    """
    if not validation_result.valid:
        return "PRELIMINARY"

    # Tier 3 — all submission fields present
    tier3_fields = [
        "originating_lab",
        "submitting_lab",
        "collection_location_state",
        "collection_location_county",
        "host_age",
        "host_sex",
    ]
    if all(data.get(f) for f in tier3_fields):
        return "SUBMITTABLE"

    # Tier 2 — date to at least month precision and geographic fields
    tier2_fields = [
        "collection_location_state",
    ]
    precision = data.get("date_collected_precision", "day")
    if precision != "year" and all(data.get(f) for f in tier2_fields):
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
