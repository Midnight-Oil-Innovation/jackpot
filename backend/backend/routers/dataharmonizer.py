"""
DataHarmonizer router — template download + CSV validation.

The underlying generation and validation logic lives in
backend/template_generator.py and backend/validator.py; this router is
just the HTTP surface for the DataHarmonizer CLI/SDK flow.

No auth required for template downloads (schema structure is public).
Validation requires auth since callers upload sample metadata.
"""

import csv
import io

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile
from fastapi import File as FastAPIFile

from backend.auth.guards import get_current_user
from backend.responses import error
from backend.template_generator import (
    SOURCE_TYPE_CLASS,
    TemplateTier,
    generate_csv_template,
)
from backend.validator import validate_sample

router = APIRouter(prefix="/api/v1/dataharmonizer", tags=["dataharmonizer"])


@router.get("/templates/{source_type}/{tier}")
def download_template(source_type: str, tier: str, metagenomics: bool = False):
    """Download a CSV template for a source type + quality tier."""
    if source_type not in SOURCE_TYPE_CLASS:
        return error(
            code="UNKNOWN_SOURCE_TYPE",
            message=(
                f"Unknown source_type '{source_type}'. "
                f"Expected one of: {sorted(SOURCE_TYPE_CLASS.keys())}"
            ),
            status_code=400,
        )
    try:
        tier_enum = TemplateTier(tier.upper())
    except ValueError:
        return error(
            code="UNKNOWN_TIER",
            message=(f"Unknown tier '{tier}'. Expected one of: {[t.value for t in TemplateTier]}"),
            status_code=400,
        )

    csv_content = generate_csv_template(source_type, tier_enum, metagenomics)
    meta_suffix = "_metagenomics" if metagenomics else ""
    filename = f"jackpot_template_{source_type}_{tier_enum.value.lower()}{meta_suffix}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


_META_MARKERS: frozenset[str] = frozenset({"REQUIRED", "ANALYZABLE", "SUBMITTABLE", "OPTIONAL"})


def _find_data_start(rows: list[list[str]]) -> int:
    """Index of the first real data row, skipping labels/tier-tag/hint rows.

    Heuristic: within rows 2–4 (1-indexed), a row containing a known
    tier marker cell is a hint row, not data — data starts after it.
    """
    data_start = 1
    for i in range(1, min(len(rows), 5)):
        if any(cell.strip() in _META_MARKERS for cell in rows[i]):
            data_start = i + 1
    return data_start


def _row_to_record(header: list[str], row: list[str]) -> dict:
    """Zip one data row against the header, splitting comma-separated values."""
    record: dict = {}
    for key, val in zip(header, row, strict=False):
        val = val.strip()
        if not val:
            continue
        if "," in val and not val.startswith("gs://"):
            record[key] = [v.strip() for v in val.split(",") if v.strip()]
        else:
            record[key] = val
    return record


def _parse_csv_rows(raw: str) -> list[dict]:
    """Parse a DataHarmonizer CSV body.

    Row 1 is field names. Rows 2–4 (labels, tier tags, validation hints)
    are skipped when present — heuristic: if the value in the first column
    of row 2 is non-empty and matches a known header marker.
    """
    reader = csv.reader(io.StringIO(raw))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        return []
    header = rows[0]
    data_start = _find_data_start(rows)

    records: list[dict] = []
    for row in rows[data_start:]:
        record = _row_to_record(header, row)
        if record:
            records.append(record)
    return records


@router.post("/validate")
async def validate_csv(
    request: Request,
    file: UploadFile | None = FastAPIFile(default=None),  # noqa: B008
):
    """
    Validate a metadata CSV row-by-row.

    Accepts either a multipart form upload (``file`` field) or a raw
    CSV body (``text/csv``). Returns per-row validation results with
    tier, errors, warnings, and per-tier missing fields.
    """
    get_current_user(request)

    if file is not None:
        body_bytes = await file.read()
    else:
        body_bytes = await request.body()

    if not body_bytes:
        raise HTTPException(status_code=400, detail="Empty request body.")

    try:
        raw = body_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8.") from exc

    records = _parse_csv_rows(raw)
    if not records:
        raise HTTPException(status_code=400, detail="No data rows found.")

    results = []
    for idx, record in enumerate(records, start=1):
        result = validate_sample(record)
        results.append(
            {
                "row": idx,
                "sample_id": record.get("sample_id"),
                "valid": result.valid,
                "tier": result.tier,
                "sector": result.sector,
                "errors": result.errors,
                "warnings": result.warnings,
                "tier2_missing": result.tier2_missing,
                "tier3_missing": result.tier3_missing,
            }
        )

    return {
        "total_rows": len(results),
        "valid_rows": sum(1 for r in results if r["valid"]),
        "results": results,
    }
