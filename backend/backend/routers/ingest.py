import contextlib
import csv
import io
import json
import logging
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from backend.audit import AuditActions, log_audit
from backend.auth.guards import get_current_user, require_platform_admin
from backend.config import get_settings
from backend.database import execute_query, execute_write, get_db_dep
from backend.epiweek import compute_epiweeks
from backend.file_detector import (
    FileDetectorError,
    detect_files,
    get_convenience_uris,
    get_file_type,
    validate_file_type,
)
from backend.notifications import NotificationEvents, create_notification
from backend.rate_limit import limiter
from backend.responses import success
from backend.storage import StorageError, stage_file
from backend.validator import (
    compute_quality_status,
    compute_surveillance_relevant,
    validate_sample,
)

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])
logger = logging.getLogger(__name__)
_INGEST_LIMIT = get_settings().rate_limit_ingest


# Whitelist of columns the ingest pipeline may INSERT into the samples table.
# Guards against unexpected keys slipping in from client metadata. Columns
# are taken from the Alembic baseline migration plus subsequent revisions
# (sector, surveillance_relevant, quality_status, target_organisms,
# date_collected_precision, etc.). See db/SCHEMA.sql for a snapshot.
_SAMPLE_COLUMNS: frozenset[str] = frozenset(
    {
        "sample_id",
        "lab_id",
        "project_id",
        "owner_id",
        "source_type",
        "organism_name",
        "strain",
        "isolate",
        "serotype",
        "target_organisms",
        "type_of_experiment",
        "nucleic_acid_extraction_method",
        "library_preparation_method",
        "sequencing_protocol",
        "sequencing_platform",
        "sequencing_instrument",
        "sequencing_lab",
        "date_collected",
        "date_collected_precision",
        "date_sequenced",
        "collection_facility",
        "purpose_for_collection",
        "collection_location_country",
        "collection_location_state",
        "collection_location_county",
        "collection_location_zipcode",
        "geo_lat",
        "geo_lon",
        "mmwr_year",
        "mmwr_week",
        "iso_year",
        "iso_week",
        "sharing_level",
        "sector",
        "surveillance_relevant",
        "quality_status",
        "scrub_status",
        "pii_scan_status",
        "ingest_method",
        "fastq_r1_uri",
        "fastq_r2_uri",
        "raw_fastq_uri",
        "consensus_fasta_uri",
        "pi_name",
        "grant_number",
        "contact_other",
        "comments",
        # Human
        "external_case_id",
        "case_id",
        "biospecimen_type",
        "reason_for_collection",
        "host_sex",
        "host_age",
        "host_age_unit",
        "host_species",
        "host_disease",
        "isolation_source",
        # Animal
        "wildlife_subject_id",
        "companion_subject_id",
        "livestock_subject_id",
        "livestock_products",
        # Vector
        "vector_species",
        "vector_host_species",
        # Wastewater
        "wwtp_name",
        "population_served",
        "sample_type_ww",
        "sample_matrix",
        "pretreatment",
        "concentration_method",
        "flow_rate_mgd",
        # Water
        "water_temperature_c",
        "turbidity_ntu",
        "ph",
        "salinity_ppm",
        # Air
        "air_source",
        "airflow_rate_m3_s",
        "pm25_ug_m3",
        "pm10_ug_m3",
        # Soil
        "soil_site_type",
        "sample_depth_cm",
        # Surface
        "indoor_space",
        "indoor_surface",
        "surface_material",
        # Food / Produce
        "food_location_type",
        "food_product_type",
        "plant_species",
        "produce_water_source",
        "near_animal_agriculture",
        # Submission
        "originating_lab",
        "submitting_lab",
        "data_generator",
    }
)


def _serialise(row: dict) -> dict:
    out = dict(row)
    for k, v in out.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
    return out


def _get_reportable_organisms(conn) -> set[str]:
    rows = execute_query(
        "SELECT organism_name FROM reportable_organisms WHERE is_active = TRUE",
        conn=conn,
    )
    return {r["organism_name"] for r in rows}


def _check_sequencing_lab(name: str, conn) -> None:
    if not name:
        raise HTTPException(
            status_code=422,
            detail="sequencing_lab is required.",
        )
    rows = execute_query(
        "SELECT 1 FROM sequencing_labs WHERE name = :n AND is_active = TRUE LIMIT 1",
        {"n": name},
        conn=conn,
    )
    if not rows:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown sequencing lab '{name}'. Ask your Lab Director to "
                "request approval via POST /api/v1/sequencing-labs/requests "
                "before ingesting samples from this facility."
            ),
        )


_INT_COLUMNS = {"lab_id", "project_id", "owner_id", "host_age", "population_served"}


def _coerce_types(payload: dict) -> dict:
    out = dict(payload)
    for col in _INT_COLUMNS:
        if col in out and isinstance(out[col], str) and out[col].strip():
            with contextlib.suppress(ValueError):
                out[col] = int(out[col])
    return out


def _insert_sample(payload: dict, conn) -> dict:
    payload = _coerce_types(payload)
    filtered = {k: v for k, v in payload.items() if v is not None and k in _SAMPLE_COLUMNS}
    cols = sorted(filtered.keys())
    if "sample_id" not in filtered:
        raise HTTPException(status_code=422, detail="sample_id is required.")
    placeholders = [f":{c}" for c in cols]
    query = (
        f"INSERT INTO samples ({', '.join(cols)}) VALUES ({', '.join(placeholders)}) RETURNING *"
    )
    rows = execute_write(query, filtered, conn=conn)
    return rows[0]


def _insert_sample_files(
    sample_id_fk: int,
    detected,
    uri_map: dict[str, str],
    size_map: dict[str, int],
    scrub_status: str,
    ingest_method: str,
    conn,
) -> list[dict]:
    inserted: list[dict] = []
    for f in detected.files:
        row = execute_write(
            """
            INSERT INTO sample_files
                (sample_id_fk, uri, filename, file_size_bytes, file_type,
                 library_layout, read_direction, lane, chunk_index,
                 scrub_status, ingest_method)
            VALUES
                (:sid, :uri, :fn, :sz, :ft, :ll, :rd, :ln, :ci, :ss, :im)
            RETURNING *
            """,
            {
                "sid": sample_id_fk,
                "uri": uri_map[f.filename],
                "fn": f.filename,
                "sz": size_map.get(f.filename),
                "ft": f.file_type,
                "ll": f.library_layout,
                "rd": f.read_direction,
                "ln": f.lane,
                "ci": f.chunk_index,
                "ss": scrub_status,
                "im": ingest_method,
            },
            conn=conn,
        )
        inserted.append(row[0])
    return inserted


def _ingest_one(
    metadata: dict,
    uri_map: dict[str, str],
    size_map: dict[str, int],
    user: dict,
    db,
    ingest_method: str,
) -> tuple[dict, list[dict]]:
    """
    Shared ingest core: validate, detect, INSERT sample + sample_files, audit.
    Raises HTTPException on validation / sequencing_lab errors.
    """
    validation = validate_sample(metadata)
    if not validation.valid:
        raise HTTPException(
            status_code=422,
            detail={
                "errors": validation.errors,
                "warnings": validation.warnings,
                "tier2_missing": validation.tier2_missing,
                "tier3_missing": validation.tier3_missing,
            },
        )

    _check_sequencing_lab(metadata.get("sequencing_lab", ""), db)

    raw_date = metadata["date_collected"]
    collected = date.fromisoformat(raw_date) if isinstance(raw_date, str) else raw_date
    precision = metadata.get("date_collected_precision", "day")
    epi = compute_epiweeks(collected, precision)

    detected = detect_files(list(uri_map.keys()))
    fastq_r1_uri, fastq_r2_uri = get_convenience_uris(detected, uri_map)

    file_types = [get_file_type(fn) for fn in uri_map]
    scrub_status = "PENDING" if "FASTQ" in file_types else "SKIPPED"

    quality_status = compute_quality_status(validation)
    reportable = _get_reportable_organisms(db)
    surveillance_relevant = compute_surveillance_relevant(
        metadata.get("organism_name", ""),
        metadata.get("target_organisms"),
        reportable,
    )

    payload = dict(metadata)
    payload["owner_id"] = user["id"]
    payload.update(epi)
    payload["sector"] = validation.sector or payload.get("sector")
    payload["surveillance_relevant"] = surveillance_relevant
    payload["quality_status"] = quality_status
    payload["scrub_status"] = scrub_status
    payload.setdefault("pii_scan_status", "PENDING")
    payload["ingest_method"] = ingest_method
    payload.setdefault("sharing_level", "PRIVATE")
    payload["fastq_r1_uri"] = fastq_r1_uri
    payload["fastq_r2_uri"] = fastq_r2_uri

    sample = _insert_sample(payload, db)
    inserted_files = _insert_sample_files(
        sample["id"], detected, uri_map, size_map, scrub_status, ingest_method, db
    )

    log_audit(
        action=AuditActions.CREATE_SAMPLE,
        actor_id=user["id"],
        resource_type="sample",
        resource_id=str(sample["id"]),
        before=None,
        after=_serialise(sample),
        metadata={"ingest_method": ingest_method, "tier": validation.tier},
        db_conn=db,
    )
    return sample, inserted_files


@router.get("/")
def list_ingest() -> dict:
    """Ingest router is POST-only — this endpoint documents available paths."""
    return {
        "endpoints": [
            "POST /api/v1/ingest/upload",
            "POST /api/v1/ingest/csv",
            "POST /api/v1/ingest/globus",
        ],
    }


@router.post("/upload", status_code=201)
@limiter.limit(_INGEST_LIMIT)
async def upload(
    request: Request,
    metadata: str = Form(...),
    fastq_r1: UploadFile = File(...),  # noqa: B008
    fastq_r2: UploadFile | None = File(None),  # noqa: B008
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid metadata JSON: {exc}") from exc
    if not isinstance(meta, dict):
        raise HTTPException(status_code=422, detail="metadata must be a JSON object.")

    sample_id = meta.get("sample_id")
    if not sample_id:
        raise HTTPException(status_code=422, detail="metadata.sample_id is required.")

    uploads: list[UploadFile] = [fastq_r1]
    if fastq_r2 is not None and fastq_r2.filename:
        uploads.append(fastq_r2)

    uri_map: dict[str, str] = {}
    size_map: dict[str, int] = {}
    for up in uploads:
        filename = up.filename
        if not filename:
            raise HTTPException(status_code=422, detail="Uploaded file is missing a filename.")
        data = await up.read()
        # Critical Rule 11: file content vs extension validation lives only
        # in file_detector. Write the bytes to a temp file with the original
        # name so validate_file_type() can sniff content + check extension
        # before we stage anything to object storage.
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / filename
            tmp_path.write_bytes(data)
            try:
                validate_file_type(tmp_path)
            except FileDetectorError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        key = f"staging/{sample_id}/{filename}"
        try:
            uri = stage_file(io.BytesIO(data), key)
        except StorageError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        uri_map[filename] = uri
        size_map[filename] = len(data)

    sample, files = _ingest_one(meta, uri_map, size_map, user, db, "gui")
    out = _serialise(sample)
    out["files"] = [_serialise(f) for f in files]
    return success(data=out, status_code=201)


def _split_files_column(value: str) -> list[str]:
    return [p.strip() for p in value.split(";") if p.strip()]


def _parse_list_field(value: str) -> list[str]:
    # Accept JSON array or semicolon-delimited string
    value = value.strip()
    if not value:
        return []
    if value.startswith("["):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(v) for v in parsed]
        except json.JSONDecodeError:
            pass
    return _split_files_column(value)


_CSV_LIST_FIELDS = {
    "nucleic_acid_extraction_method",
    "purpose_for_collection",
    "target_organisms",
    "reason_for_collection",
    "host_disease",
    "livestock_products",
    "pretreatment",
    "produce_water_source",
}

_CSV_INT_FIELDS = {"lab_id", "project_id", "host_age", "population_served"}
_CSV_FLOAT_FIELDS = {
    "geo_lat",
    "geo_lon",
    "water_temperature_c",
    "turbidity_ntu",
    "ph",
    "salinity_ppm",
    "flow_rate_mgd",
    "airflow_rate_m3_s",
    "pm25_ug_m3",
    "pm10_ug_m3",
}


def _coerce_csv_row(row: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, raw in row.items():
        if raw is None or raw == "":
            continue
        key = k.strip()
        if key in _CSV_LIST_FIELDS:
            out[key] = _parse_list_field(raw)
        elif key in _CSV_INT_FIELDS:
            try:
                out[key] = int(raw)
            except ValueError:
                out[key] = raw
        elif key in _CSV_FLOAT_FIELDS:
            try:
                out[key] = float(raw)
            except ValueError:
                out[key] = raw
        else:
            out[key] = raw
    return out


@router.post("/csv")
@limiter.limit(_INGEST_LIMIT)
async def ingest_csv(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"CSV must be UTF-8 encoded: {exc}") from exc

    reader = csv.DictReader(io.StringIO(text))
    successes = 0
    failures = 0
    errors: list[dict] = []
    created_ids: list[int] = []

    for idx, raw_row in enumerate(reader, start=1):
        try:
            metadata = _coerce_csv_row(raw_row)
            filenames = _split_files_column(metadata.pop("files", "") or "")
            if not filenames:
                raise HTTPException(status_code=422, detail="Row missing 'files' column.")
            sample_id = metadata.get("sample_id", f"row-{idx}")
            uri_map = {fn: f"gs://jackpot-staging/{sample_id}/{fn}" for fn in filenames}
            size_map = {fn: 0 for fn in filenames}
            sample, _files = _ingest_one(metadata, uri_map, size_map, user, db, "csv")
            successes += 1
            created_ids.append(sample["id"])
        except HTTPException as exc:
            failures += 1
            errors.append(
                {
                    "row": idx,
                    "sample_id": raw_row.get("sample_id"),
                    "detail": exc.detail,
                }
            )
        except Exception as exc:
            logger.exception("CSV row %s failed", idx)
            failures += 1
            errors.append(
                {
                    "row": idx,
                    "sample_id": raw_row.get("sample_id"),
                    "detail": str(exc),
                }
            )

    return success(
        data={
            "success": successes,
            "failed": failures,
            "errors": errors,
            "created_ids": created_ids,
        },
    )


@router.post("/globus")
@limiter.limit(_INGEST_LIMIT)
async def ingest_globus(
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    """
    Globus deposit-first webhook. Platform Admin only.

    Records files deposited by a sequencing facility and notifies the
    Lab Directors assigned to that facility so they can submit metadata.
    No sample rows are created here — only notifications — because
    metadata is not yet known at deposit time.
    """
    user = get_current_user(request)
    require_platform_admin(user)

    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid JSON body: {exc}") from exc

    sequencing_lab_name = body.get("sequencing_lab")
    files = body.get("files", [])
    if not sequencing_lab_name:
        raise HTTPException(status_code=422, detail="sequencing_lab is required.")
    if not isinstance(files, list) or not files:
        raise HTTPException(status_code=422, detail="files must be a non-empty list.")

    lab_rows = execute_query(
        "SELECT id FROM sequencing_labs WHERE name = :n AND is_active = TRUE LIMIT 1",
        {"n": sequencing_lab_name},
        conn=db,
    )
    if not lab_rows:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown sequencing lab '{sequencing_lab_name}'. "
                "Register it via POST /api/v1/sequencing-labs first."
            ),
        )
    seq_lab_id = lab_rows[0]["id"]

    # Find assigned JACKPOT labs and their directors
    assigned = execute_query(
        """
        SELECT lm.user_id, sla.lab_id
        FROM sequencing_lab_assignments sla
        JOIN lab_membership lm ON lm.lab_id = sla.lab_id
        WHERE sla.sequencing_lab_id = :sid AND lm.is_lab_director = TRUE
        """,
        {"sid": seq_lab_id},
        conn=db,
    )

    file_count = len(files)
    for director in assigned:
        create_notification(
            recipient_id=director["user_id"],
            event_type=NotificationEvents.GLOBUS_FILES_ARRIVED,
            title=f"{file_count} file(s) arrived from {sequencing_lab_name}",
            body=(
                f"{file_count} file(s) were deposited via Globus from "
                f"{sequencing_lab_name}. Provide metadata to complete ingest."
            ),
            resource_type="sequencing_lab",
            resource_id=str(seq_lab_id),
            action_url="/ingest/pending",
            db_conn=db,
        )

    log_audit(
        action=AuditActions.CREATE_SAMPLE,
        actor_id=user["id"],
        resource_type="globus_deposit",
        resource_id=str(seq_lab_id),
        before=None,
        after={"file_count": file_count, "sequencing_lab": sequencing_lab_name},
        metadata={"ingest_method": "globus", "file_count": file_count},
        db_conn=db,
    )

    return success(
        data={
            "file_count": file_count,
            "sequencing_lab_id": seq_lab_id,
            "directors_notified": len(assigned),
        },
    )
