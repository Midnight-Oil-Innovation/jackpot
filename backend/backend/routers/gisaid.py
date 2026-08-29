import csv
import io
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.auth.guards import get_current_user, require_capability
from backend.database import execute_query

router = APIRouter(prefix="/api/v1/gisaid", tags=["gisaid"])

# The row-building logic below is SARS-CoV-2 (EpiCoV) specific — hardcoded
# "Type": "betacoronavirus" and the "hCoV-19/" virus-name prefix. Influenza
# (EpiFlu) and Mpox (EpiPox) need distinct column sets and Type values;
# until that's implemented, reject them explicitly rather than silently
# mislabeling their export as SARS-CoV-2 data. Tracked as I-2-followup-A,
# matching the same minimal-scaffold-first phasing used by
# backend.submission_packages for the newer I-2 package-generation flow.
_SUPPORTED_PATHOGENS: frozenset[str] = frozenset({"SARS-CoV-2"})

GISAID_SARS_COV2_COLUMNS: list[str] = [
    "Virus name",
    "Type",
    "Passage details/history",
    "Collection date",
    "Location",
    "Additional location information",
    "Host",
    "Additional host information",
    "Gender",
    "Patient age",
    "Patient status",
    "Specimen source",
    "Outbreak",
    "Last vaccinated",
    "Treatment",
    "Sequencing technology",
    "Assembly method",
    "Coverage",
    "Originating lab",
    "Address",
    "Sample ID given by the originating laboratory",
    "Submitting lab",
    "Address_submitting",
    "Sample ID given by the submitting laboratory",
    "Authors",
    "Submitter",
    "GISAID Accession ID",
]


@router.post("/export/{lab_id}")
def export_gisaid_csv(
    lab_id: int,
    sample_ids: list[int],
    pathogen: str,
    request: Request,
) -> StreamingResponse:
    """
    Generate a GISAID-compatible CSV for the specified samples.

    Currently implements SARS-CoV-2 (EpiCoV) only. Influenza (EpiFlu) and
    Mpox (EpiPox) require distinct column sets and are not yet
    implemented — requesting them returns 501 rather than a CSV
    mislabeled as SARS-CoV-2 data.
    """
    if not sample_ids:
        raise HTTPException(status_code=400, detail="No sample IDs provided.")
    user = get_current_user(request)
    require_capability("sample:read_detail")(user, lab_id=lab_id)
    if pathogen not in _SUPPORTED_PATHOGENS:
        raise HTTPException(
            status_code=501,
            detail=(
                f"GISAID export for pathogen {pathogen!r} is not yet implemented. "
                f"Currently supported: {sorted(_SUPPORTED_PATHOGENS)}."
            ),
        )

    placeholders = ",".join(f":id_{i}" for i in range(len(sample_ids)))
    params = {f"id_{i}": sid for i, sid in enumerate(sample_ids)}
    params["lab_id"] = lab_id

    samples = execute_query(
        f"""
        SELECT s.*, u.email AS owner_email, l.display_name AS lab_name
        FROM samples s
        JOIN users u ON u.id = s.owner_id
        JOIN labs l  ON l.id = s.lab_id
        WHERE s.id IN ({placeholders})
          AND s.lab_id = :lab_id AND s.is_deleted = FALSE
        """,
        params,
    )
    if not samples:
        raise HTTPException(status_code=404, detail="No samples found.")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=GISAID_SARS_COV2_COLUMNS, extrasaction="ignore")
    writer.writeheader()

    for s in samples:
        row = {
            "Virus name": (
                f"hCoV-19/{s.get('collection_location_country', '').replace(' ', '_')}/"
                f"{s['sample_id']}/{str(s['date_collected'])[:4]}"
            ),
            "Type": "betacoronavirus",
            "Passage details/history": "Original",
            "Collection date": str(s.get("date_collected", "")),
            "Location": (
                f"North America / {s.get('collection_location_country', '')} / "
                f"{s.get('collection_location_state', '')}"
            ),
            "Additional location information": s.get("collection_location_county", ""),
            "Host": "Human" if s["source_type"] == "Human" else s.get("host_species", ""),
            "Gender": s.get("host_sex", "unknown"),
            "Patient age": s.get("host_age", ""),
            "Patient status": s.get("clinical_outcome", "unknown"),
            "Specimen source": s.get("sequencing_protocol", ""),
            "Last vaccinated": s.get("vaccination_status", ""),
            "Sequencing technology": s.get("sequencing_platform", ""),
            "Assembly method": s.get("assembly_method", ""),
            "Coverage": s.get("coverage_depth", ""),
            "Originating lab": s.get("lab_name", ""),
            "Sample ID given by the originating laboratory": s["sample_id"],
            "Submitting lab": s.get("lab_name", ""),
            "Sample ID given by the submitting laboratory": s["sample_id"],
            "Submitter": s.get("owner_email", ""),
            "GISAID Accession ID": s.get("gisaid_accession", ""),
        }
        writer.writerow(row)

    output.seek(0)
    filename = f"gisaid_{pathogen}_{datetime.now().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
