"""
JACKPOT template generator.

Generates tier-aware CSV metadata templates from the LinkML-generated JSON Schema.
Single source of truth: jackpot_schema.SCHEMA_JSON_PATH (workspace package).

Usage:
    API:  GET /api/v1/templates/?source_type=human&tier=ANALYZABLE&format=csv
    CLI:  jackpot templates generate --source-type human --tier ANALYZABLE
    SDK:  session.templates.generate(source_type="human", tier="ANALYZABLE")

Design doc: docs/jackpot_template_system_design.md
"""

import csv
import io
import json
from enum import Enum

from jackpot_schema import SCHEMA_JSON_PATH as SCHEMA_PATH

# ── Tier enum ─────────────────────────────────────────────────────────────


class TemplateTier(str, Enum):
    """Target quality tier. Controls which columns are included."""

    PRELIMINARY = "PRELIMINARY"
    ANALYZABLE = "ANALYZABLE"
    SUBMITTABLE = "SUBMITTABLE"


# ── Source-type to schema class mapping ───────────────────────────────────

SOURCE_TYPE_CLASS: dict[str, str] = {
    "human": "HumanSample",
    "companion_animal": "CompanionAnimalSample",
    "wildlife": "WildlifeHostSample",
    "vector": "VectorSample",
    "livestock": "LivestockSample",
    "produce": "ProduceSample",
    "food": "FoodSample",
    "surface": "SurfaceSample",
    "soil": "SoilSample",
    "water": "WaterSample",
    "wastewater": "WastewaterSample",
    "air": "AirSample",
}


# ── Fields that are system-computed (never shown in templates) ────────────

SYSTEM_COMPUTED: set[str] = {
    "quality_status",
    "surveillance_relevant",
    "surveillance_relevant_override",
    "surveillance_override_pending",
    "scrub_status",
    "pii_scan_status",
    "ingest_method",
    "sharing_level",
    "mmwr_year",
    "mmwr_week",
    "iso_year",
    "iso_week",
    "date_collected_precision",
    "jackpot_uri",
    "created_at",
    "updated_at",
    "created_by",
    "updated_by",
    "fastq_r1_uri",
    "fastq_r2_uri",
    "assembly_uri",
    "pango_lineage",
    "pango_lineage_version",
    "pango_conflict",
    "nextstrain_clade",
    "nextclade_qc_overall",
    "nextclade_version",
    "vadr_status",
    "vadr_alerts",
    "biosample_accession",
    "sra_accession",
    "genbank_accession",
    "gisaid_accession",
    "bioproject_accession",
    "card_aro_terms",
    "amrfinder_genes",
    "owner",
    "lab",
    "project",
}

# ── Tier field requirements ───────────────────────────────────────────────
# Mirrors compute_quality_status() in validator.py.
# SUBMITTABLE has NO date precision constraint — NCBI and GISAID accept
# year-only, month-only, and day-precision collection dates.

PRELIMINARY_FIELDS: list[str] = [
    "sample_id",
    "organism_name",
    "source_type",
    "type_of_experiment",
    "nucleic_acid_extraction_method",
    "library_preparation_method",
    "sequencing_protocol",
    "sequencing_platform",
    "sequencing_lab",
    "date_collected",
    "date_sequenced",
    "collection_facility",
    "purpose_for_collection",
    "collection_location_country",
    "sector",
]

ANALYZABLE_FIELDS: list[str] = [
    "collection_location_state",
]

SUBMITTABLE_FIELDS: list[str] = [
    "originating_lab",
    "submitting_lab",
    "collection_location_state",
    "collection_location_county",
]

SUBMITTABLE_HUMAN_ONLY: list[str] = [
    "host_age",
    "host_sex",
]

# ── Metagenomics overlay fields ───────────────────────────────────────────

METAGENOMICS_FIELDS: list[str] = [
    "target_organisms",
    "assembly_type",
    "mag_completeness_pct",
    "mag_contamination_pct",
    "mag_strain_heterogeneity",
]

# ── Example data per source type ──────────────────────────────────────────
# Pre-filled example row for row 5 of the CSV template.

BASE_EXAMPLE: dict[str, str] = {
    "sample_id": "EXAMPLE-2026-001",
    "organism_name": "Salmonella enterica",
    "source_type": "Human",
    "type_of_experiment": "WGS",
    "nucleic_acid_extraction_method": "magnetic bead",
    "library_preparation_method": "Bead-Linked Transposome Tagmentation",
    "sequencing_protocol": "https://dx.doi.org/10.17504/protocols.io.example",
    "sequencing_platform": "Illumina",
    "sequencing_lab": "Example Sequencing Lab",
    "date_collected": "2026-04-01",
    "date_sequenced": "2026-04-05",
    "collection_facility": "Example Hospital",
    "purpose_for_collection": "diagnostic",
    "collection_location_country": "USA",
    "collection_location_state": "California",
    "collection_location_county": "San Diego",
    "sector": "clinical",
    "originating_lab": "Example Clinical Lab",
    "submitting_lab": "Example Sequencing Lab",
}

SOURCE_TYPE_EXAMPLES: dict[str, dict[str, str]] = {
    "human": {
        "external_case_id": "12345LMNO",
        "biospecimen_type": "nasopharyngeal swab",
        "reason_for_collection": "clinical",
        "host_age": "45",
        "host_sex": "Male",
        "host_species": "Homo sapiens",
        "disease": "salmonella gastroenteritis",
        "isolation_source": "stool",
    },
    "wastewater": {
        "source_type": "Wastewater",
        "sector": "wastewater",
        "organism_name": "SARS-CoV-2",
        "collection_facility": "Example WWTP",
        "purpose_for_collection": "surveillance",
    },
    "soil": {
        "source_type": "Soil",
        "sector": "environmental",
        "organism_name": "Coccidioides immitis",
        "collection_facility": "Example Field Station",
        "purpose_for_collection": "research",
    },
}

METAGENOMICS_EXAMPLE: dict[str, str] = {
    "organism_name": "metagenome",
    "type_of_experiment": "shotgun_DNA_sequencing",
    "target_organisms": "SARS-CoV-2;Influenza A virus",
    "assembly_type": "mag",
    "mag_completeness_pct": "95.2",
    "mag_contamination_pct": "1.3",
    "mag_strain_heterogeneity": "0.0",
}


# ── Helpers ────────────────────────────────────────────────────────────────


def _load_schema() -> dict:
    """Load the generated JSON Schema."""
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def _get_enum_values(schema: dict, ref: str) -> list[str]:
    """Extract enum values from a $ref pointing to a $defs entry."""
    def_name = ref.split("/")[-1]
    definition = schema.get("$defs", {}).get(def_name, {})
    return definition.get("enum", [])


def _snake_to_label(name: str) -> str:
    """Convert snake_case to Title Case label."""
    return name.replace("_", " ").title()


def _classify_field_tier(field_name: str, source_type: str) -> str:
    """
    Determine which tier requires this field.
    Returns: "REQUIRED", "ANALYZABLE", "SUBMITTABLE", or "OPTIONAL".
    """
    if field_name in PRELIMINARY_FIELDS:
        return "REQUIRED"

    if field_name in ANALYZABLE_FIELDS:
        return "ANALYZABLE"

    if field_name in SUBMITTABLE_FIELDS:
        return "SUBMITTABLE"

    if field_name in SUBMITTABLE_HUMAN_ONLY:
        if source_type == "human":
            return "SUBMITTABLE"
        return "OPTIONAL"

    return "OPTIONAL"


def _build_validation_hint(field_name: str, fdef: dict, schema: dict) -> str:
    """Build a validation hint string for row 4 of the CSV."""
    if "$ref" in fdef:
        vals = _get_enum_values(schema, fdef["$ref"])
        if vals:
            shown = vals[:5]
            hint = " | ".join(shown)
            if len(vals) > 5:
                hint += f" | ... ({len(vals)} total)"
            return hint

    if "date" in field_name:
        return "YYYY-MM-DD (ISO 8601). YYYY-MM and YYYY also accepted."

    item_type = fdef.get("type", "string")
    if item_type == "integer":
        return "integer"
    if item_type == "number":
        return "decimal number"
    if item_type == "boolean":
        return "true | false"
    if item_type == "array":
        return "semicolon-separated list"

    return "free text"


# ── Core generation logic ─────────────────────────────────────────────────


def _build_field_list(
    schema: dict,
    source_type: str,
    tier: TemplateTier,
    metagenomics: bool = False,
) -> list[dict]:
    """
    Build the ordered list of fields for a template.

    Returns list of dicts with keys:
        field_name, label, tier_tag, description, type,
        enum_values, section, validation_hint
    """
    defs = schema.get("$defs", {})

    # BaseSample is called "Sample" in the generated JSON Schema
    base_class = "Sample"
    base_props = defs.get(base_class, {}).get("properties", {})

    class_name = SOURCE_TYPE_CLASS.get(source_type, base_class)
    subclass_props = defs.get(class_name, {}).get("properties", {})
    subclass_required = set(defs.get(class_name, {}).get("required", []))

    fields: list[dict] = []
    seen: set[str] = set()

    def _add_field(fname: str, fdef: dict, section: str, force_tier: str | None = None) -> None:
        if fname in seen or fname in SYSTEM_COMPUTED:
            return
        # MAG fields only appear when metagenomics overlay is active
        if fname in METAGENOMICS_FIELDS and not metagenomics:
            return
        seen.add(fname)

        tier_tag = force_tier or _classify_field_tier(fname, source_type)

        # Filter by requested tier: PRELIMINARY templates exclude
        # ANALYZABLE/SUBMITTABLE-only fields. ANALYZABLE templates
        # exclude SUBMITTABLE-only fields. SUBMITTABLE templates
        # include everything.
        skip = (tier == TemplateTier.PRELIMINARY and tier_tag in ("ANALYZABLE", "SUBMITTABLE")) or (
            tier == TemplateTier.ANALYZABLE and tier_tag == "SUBMITTABLE"
        )
        if skip:
            return

        enum_values = None
        if "$ref" in fdef:
            enum_values = _get_enum_values(schema, fdef["$ref"])

        fields.append(
            {
                "field_name": fname,
                "label": _snake_to_label(fname),
                "tier_tag": tier_tag,
                "description": fdef.get("description", ""),
                "type": fdef.get("type", "string"),
                "enum_values": enum_values,
                "section": section,
                "validation_hint": _build_validation_hint(fname, fdef, schema),
            }
        )

    # 1. BaseSample fields (common to all source types)
    for fname, fdef in base_props.items():
        _add_field(fname, fdef, "base")

    # 2. Source-type-specific fields
    for fname, fdef in subclass_props.items():
        # Determine if this is required for the source type
        force_tier = None
        if fname in subclass_required and fname not in PRELIMINARY_FIELDS:
            force_tier = "REQUIRED"
        _add_field(fname, fdef, "source_type_specific", force_tier)

    # 3. Metagenomics overlay fields
    if metagenomics:
        for fname in METAGENOMICS_FIELDS:
            if fname in base_props:
                _add_field(fname, base_props[fname], "metagenomics_overlay")
            elif fname in subclass_props:
                _add_field(fname, subclass_props[fname], "metagenomics_overlay")
            elif fname not in seen:
                # MAG field not in schema — create synthetic definition
                _add_field(
                    fname,
                    {"type": "number", "description": f"MAG QC metric: {fname}"},
                    "metagenomics_overlay",
                )
    return fields


def _build_example_row(fields: list[dict], source_type: str, metagenomics: bool) -> list[str]:
    """Merge BASE_EXAMPLE with source-type and metagenomics overlays, then
    project onto the template's field order."""
    example: dict = {}
    example.update(BASE_EXAMPLE)
    if source_type in SOURCE_TYPE_EXAMPLES:
        example.update(SOURCE_TYPE_EXAMPLES[source_type])
    if metagenomics:
        example.update(METAGENOMICS_EXAMPLE)
    return [example.get(f["field_name"], "") for f in fields]


def generate_csv_template(
    source_type: str,
    tier: TemplateTier = TemplateTier.ANALYZABLE,
    metagenomics: bool = False,
) -> str:
    """
    Generate a CSV template string.

    Row 1: JACKPOT field names (snake_case — what the API and harmonizer expect)
    Row 2: Human-readable labels
    Row 3: Tier requirement tag (REQUIRED | ANALYZABLE | SUBMITTABLE | OPTIONAL)
    Row 4: Validation hint (enum values, date format, etc.)
    Row 5: Example data row (pre-filled)
    Row 6+: Empty rows for user data
    """
    schema = _load_schema()
    fields = _build_field_list(schema, source_type, tier, metagenomics)

    if not fields:
        return ""

    output = io.StringIO()
    writer = csv.writer(output)

    # Row 1: Field names (snake_case)
    writer.writerow([f["field_name"] for f in fields])

    # Row 2: Human-readable labels
    writer.writerow([f["label"] for f in fields])

    # Row 3: Tier tags
    writer.writerow([f["tier_tag"] for f in fields])

    # Row 4: Validation hints
    writer.writerow([f["validation_hint"] for f in fields])

    # Row 5: Example row
    writer.writerow(_build_example_row(fields, source_type, metagenomics))

    # Rows 6-15: Empty data rows
    empty_row = ["" for _ in fields]
    for _ in range(10):
        writer.writerow(empty_row)

    return output.getvalue()


def generate_companion_enums_json(
    source_type: str,
    tier: TemplateTier = TemplateTier.ANALYZABLE,
    metagenomics: bool = False,
) -> dict:
    """
    Generate a dict of all enum values for fields in the template.
    Labs can use this for their own validation scripts or LIMS integration.
    """
    schema = _load_schema()
    fields = _build_field_list(schema, source_type, tier, metagenomics)

    enums: dict[str, dict] = {}
    for f in fields:
        if f["enum_values"]:
            enums[f["field_name"]] = {
                "label": f["label"],
                "values": f["enum_values"],
                "required_at_tier": f["tier_tag"],
            }

    return enums
