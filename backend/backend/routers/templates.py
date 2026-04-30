"""
JACKPOT template generation endpoints.

No auth required — templates are schema structure, not data.
Labs can download templates before they have a JACKPOT account.

Design doc: docs/jackpot_template_system_design.md
"""

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse

from backend.template_generator import (
    SOURCE_TYPE_CLASS,
    TemplateTier,
    generate_companion_enums_json,
    generate_csv_template,
)

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.get("/")
def get_template(
    source_type: str = Query(  # noqa: B008
        ...,
        description="One Health source type",
        enum=list(SOURCE_TYPE_CLASS.keys()),
    ),
    tier: TemplateTier = Query(  # noqa: B008
        TemplateTier.ANALYZABLE,
        description="Target quality tier — controls which columns are included",
    ),
    metagenomics: bool = Query(  # noqa: B008
        False,
        description="Include metagenomics overlay fields (target_organisms, MAG QC)",
    ),
    format: str = Query(  # noqa: B008
        "csv",
        description="Output format: csv or xlsx (xlsx = Month 2)",
        enum=["csv", "xlsx"],
    ),
):
    """
    Generate a metadata template for a given source type and quality tier.

    The template is generated dynamically from the JACKPOT LinkML schema.
    Column names match the API field names exactly — no harmonizer needed.

    Tier behavior:
    - PRELIMINARY: Only columns required for minimum viable ingest (~15 cols)
    - ANALYZABLE: Adds geographic and date precision fields (~20 cols)
    - SUBMITTABLE: All fields needed for NCBI/GISAID submission (~30+ cols)

    Metagenomics overlay adds: target_organisms, assembly_type,
    mag_completeness_pct, mag_contamination_pct, mag_strain_heterogeneity.
    """
    if format == "xlsx":
        return JSONResponse(
            status_code=501,
            content={"detail": "XLSX generation not yet implemented. Use format=csv."},
        )

    csv_content = generate_csv_template(source_type, tier, metagenomics)
    meta_suffix = "_metagenomics" if metagenomics else ""
    filename = f"jackpot_template_{source_type}_{tier.value.lower()}{meta_suffix}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/enums")
def get_template_enums(
    source_type: str = Query(  # noqa: B008
        ...,
        description="One Health source type",
        enum=list(SOURCE_TYPE_CLASS.keys()),
    ),
    tier: TemplateTier = Query(  # noqa: B008
        TemplateTier.ANALYZABLE,
        description="Target quality tier",
    ),
    metagenomics: bool = Query(  # noqa: B008
        False,
        description="Include metagenomics overlay fields",
    ),
):
    """
    Return all enum values for fields in the template.

    Labs can use this JSON for LIMS integration, custom validation scripts,
    or building their own intake forms.
    """
    enums = generate_companion_enums_json(source_type, tier, metagenomics)
    return enums


@router.get("/source-types")
def list_source_types():
    """List all available source types and their schema class names."""
    return {
        "source_types": [
            {
                "key": key,
                "class_name": class_name,
                "label": key.replace("_", " ").title(),
            }
            for key, class_name in SOURCE_TYPE_CLASS.items()
        ]
    }
