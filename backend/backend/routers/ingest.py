import contextlib
import csv
import hashlib
import io
import json
import logging
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from backend.audit import AuditActions, log_audit
from backend.auth.guards import get_current_user, require_capability
from backend.config import get_settings
from backend.database import execute_query, execute_write, get_db_dep
from backend.epiweek import compute_epiweeks
from backend.file_detector import (
    FileDetectorError,
    detect_files,
    get_convenience_uris,
    validate_file_type,
)
from backend.file_fingerprint import FINGERPRINT_CHUNK_SIZE
from backend.ingest_files import VALID_STORAGE_INTENTS, register_file
from backend.notifications import NotificationEvents, create_notification
from backend.rate_limit import limiter
from backend.responses import success
from backend.storage import StorageError, stage_file
from backend.validator import (
    compute_quality_status,
    compute_scrub_status,
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


def _cheap_fingerprint_bytes(data: bytes) -> tuple[int, str, str]:
    """Compute the cheap fingerprint from in-memory bytes.

    Mirrors :func:`backend.file_fingerprint.cheap_fingerprint` but skips
    the URI-resolution layer for the ``/upload`` path where the bytes
    are already in hand. Phase P0f F-6.
    """
    size = len(data)
    if size == 0:
        empty = hashlib.sha256(b"").hexdigest()
        return (0, empty, empty)
    if size < 2 * FINGERPRINT_CHUNK_SIZE:
        digest = hashlib.sha256(data).hexdigest()
        return (size, digest, digest)
    head = hashlib.sha256(data[:FINGERPRINT_CHUNK_SIZE]).hexdigest()
    tail = hashlib.sha256(data[-FINGERPRINT_CHUNK_SIZE:]).hexdigest()
    return (size, head, tail)


def _insert_sample_files(
    sample_id_fk: int,
    detected,
    uri_map: dict[str, str],
    size_map: dict[str, int],
    scrub_status: str,
    ingest_method: str,
    storage_intent: str,
    conn,
    fingerprint_map: dict[str, tuple[int, str, str]] | None = None,
) -> list[dict]:
    """Insert one ``sample_files`` row per detected file.

    Phase P0f F-6: populates cheap-fingerprint columns and
    ``storage_state`` per file. ``storage_intent`` is the user-facing
    intent (``EXTERNAL`` / ``MANAGED`` / ``MIRRORED``); it lands directly
    on the row as ``storage_state``. ``fingerprint_map`` lets callers
    pass precomputed fingerprints for files whose bytes they already
    have in memory (e.g. ``/upload``).
    """
    inserted: list[dict] = []
    fingerprint_map = fingerprint_map or {}
    for f in detected.files:
        fp = fingerprint_map.get(f.filename)
        size = fp[0] if fp else size_map.get(f.filename)
        head_hash = fp[1] if fp else None
        tail_hash = fp[2] if fp else None
        row = execute_write(
            """
            INSERT INTO sample_files
                (sample_id_fk, uri, filename,
                 file_size_bytes, head64k_hash, tail64k_hash,
                 file_type, library_layout, read_direction, lane, chunk_index,
                 storage_state, scrub_status, ingest_method)
            VALUES
                (:sid, :uri, :fn,
                 :sz, :hh, :th,
                 :ft, :ll, :rd, :ln, :ci,
                 CAST(:state AS file_storage_state), :ss, :im)
            RETURNING *
            """,
            {
                "sid": sample_id_fk,
                "uri": uri_map[f.filename],
                "fn": f.filename,
                "sz": size,
                "hh": head_hash,
                "th": tail_hash,
                "ft": f.file_type,
                "ll": f.library_layout,
                "rd": f.read_direction,
                "ln": f.lane,
                "ci": f.chunk_index,
                "state": storage_intent,
                "ss": scrub_status,
                "im": ingest_method,
            },
            conn=conn,
        )
        inserted.append(row[0])
    return inserted


def _require_sample_create(user: dict, metadata: dict) -> None:
    """Gate an ingest on ``sample:create`` at the target lab (M2-B2).

    ``samples.lab_id`` is NOT NULL and comes from the caller's own metadata,
    which until now nothing checked — an authenticated user could ingest into
    any lab in the deployment. This closes that.

    A missing ``lab_id`` falls through deliberately: ``validate_sample`` and
    the NOT NULL constraint already reject it, and a 422 naming the missing
    field is a better answer than a 403 on a scope that was never named.
    """
    lab_id = metadata.get("lab_id")
    if lab_id is None:
        return
    try:
        lab_id = int(lab_id)
    except (TypeError, ValueError):
        return  # not a lab id at all — the validator's 422 is the right answer
    require_capability("sample:create")(user, lab_id=lab_id)


def _ingest_one(
    metadata: dict,
    uri_map: dict[str, str],
    size_map: dict[str, int],
    user: dict,
    db,
    ingest_method: str,
    *,
    storage_intent: str = "EXTERNAL",
    fingerprint_map: dict[str, tuple[int, str, str]] | None = None,
) -> tuple[dict, list[dict]]:
    """
    Shared ingest core: validate, detect, INSERT sample + sample_files, audit.
    Raises HTTPException on validation / sequencing_lab errors.

    Phase P0f F-6: ``storage_intent`` is the user-facing intent to apply
    to every ``sample_files`` row created here (``EXTERNAL`` /
    ``MANAGED`` / ``MIRRORED``). Default ``EXTERNAL`` per Critical Rule
    57. ``fingerprint_map`` lets callers pass precomputed cheap
    fingerprints for files whose bytes they already have in memory.
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

    # Critical Rule 18: file-type-driven scrub decision moved to
    # validator.py in P0e E.1.
    scrub_status = compute_scrub_status(uri_map)

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
        sample["id"],
        detected,
        uri_map,
        size_map,
        scrub_status,
        ingest_method,
        storage_intent,
        db,
        fingerprint_map=fingerprint_map,
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
            "POST /api/v1/ingest/register",
        ],
    }


# Phase P0f F-6 — request body for the new path-based registration
# endpoint. Pydantic does request-shape validation; storage_intent
# vocabulary checks happen up-front in register_paths and again inside
# register_file as a defence in depth.


class _RegisterFileSpec(BaseModel):
    role: str
    uri: str
    storage_intent: str | None = None  # default EXTERNAL applied server-side


class _RegisterRequest(BaseModel):
    sample_metadata: dict
    files: list[_RegisterFileSpec]


# R-1 #2: SSRF + local-file-read defence at the /register entry point.
# /register's URI flows into cheap_fingerprint(), which dereferences
# http(s) via httpx and bare-paths/file:// via the local filesystem. An
# authenticated user could otherwise (a) probe internal infrastructure
# (cloud metadata service, internal admin endpoints), or (b) read
# arbitrary local files. JACKPOT's storage model (Critical Rule 57:
# EXTERNAL by default; file references only) needs gs://, s3://, sra://
# but not http(s) or bare paths.
#
# file:// is allowed only in non-production deployments (settings.env ==
# "local") so the F-6 local-dev workflow keeps working; production sees
# a strict allowlist. This is the brief's option (b) — a non-production
# gate, not a silent bypass.
_REGISTER_ALLOWED_URI_SCHEMES: frozenset[str] = frozenset({"gs", "s3", "sra"})
_REGISTER_LOCAL_DEV_URI_SCHEMES: frozenset[str] = frozenset({"file"})


def _validate_register_uri_scheme(uri: str) -> None:
    """Reject /register URIs whose scheme is not in the allowlist.

    Logs the attempted scheme server-side for forensics; the 400 reply
    lists only the supported schemes (no echo of what the user tried).
    """
    settings = get_settings()
    parsed_scheme = uri.split("://", 1)[0].lower() if "://" in uri else ""
    if parsed_scheme in _REGISTER_ALLOWED_URI_SCHEMES:
        return
    if settings.env == "local" and parsed_scheme in _REGISTER_LOCAL_DEV_URI_SCHEMES:
        return
    logger.warning(
        "register_paths: rejected URI scheme=%r (env=%r)",
        parsed_scheme or "<bare>",
        settings.env,
    )
    raise HTTPException(
        status_code=400,
        detail=(
            "Unsupported URI scheme. JACKPOT supports gs://, s3://, and sra:// for file references."
        ),
    )


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

    # Before any byte is staged: an unauthorized ingest should not leave
    # files in object storage.
    _require_sample_create(user, meta)

    uploads: list[UploadFile] = [fastq_r1]
    if fastq_r2 is not None and fastq_r2.filename:
        uploads.append(fastq_r2)

    uri_map: dict[str, str] = {}
    size_map: dict[str, int] = {}
    fingerprint_map: dict[str, tuple[int, str, str]] = {}
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
        # Phase P0f F-6: compute the cheap fingerprint from the bytes in
        # hand. cheap_fingerprint(uri) on the staged URI would round-trip
        # through object storage; the bytes are identical so we skip it.
        fingerprint_map[filename] = _cheap_fingerprint_bytes(data)
        key = f"staging/{sample_id}/{filename}"
        try:
            uri = stage_file(io.BytesIO(data), key)
        except StorageError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        uri_map[filename] = uri
        size_map[filename] = len(data)

    # /upload always stages bytes into JACKPOT-managed storage.
    # TODO(P0f F-9): when a fresh upload cheap-fingerprint-matches an
    # existing MANAGED row, register_file dedups by reusing it; the
    # newly-staged file at gs://staging/... becomes orphaned. A future
    # cleanup job sweeps the staging bucket — we do not delete inline
    # because operators may run append-only buckets by policy.
    sample, files = _ingest_one(
        meta,
        uri_map,
        size_map,
        user,
        db,
        "gui",
        storage_intent="MANAGED",
        fingerprint_map=fingerprint_map,
    )
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


_CSV_STORAGE_INTENT_MISSING_WARNING = (
    "storage_intent column missing from CSV. Files registered with the "
    "default storage_state='EXTERNAL' (no copy made) per Critical Rule "
    "57. To request copies, add a storage_intent column with value "
    "'MANAGED' (or 'MIRRORED') for the relevant rows. See "
    "docs/file_references.md."
)


def run_csv_ingest(*, csv_text: str, user: dict, db) -> dict:
    """Process a CSV string through the standard ingest pipeline.

    I-1 extracted this as a standalone callable so the importer wizard
    (``backend/imports.py::execute_import``) can submit a CSV without
    going through HTTP. The HTTP endpoint :func:`ingest_csv` delegates
    here. Returns the envelope-shaped result dict (``data`` plus
    optional ``warnings``); callers re-wrap as needed.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = reader.fieldnames or []
    storage_intent_column_present = "storage_intent" in fieldnames
    successes = 0
    failures = 0
    errors: list[dict] = []
    created_ids: list[int] = []
    # M2-B2: authorize each row's target lab, memoized. A CSV is usually one
    # lab repeated N times, and the guard costs two queries (principal + lab
    # scope) — without this a 1000-row upload adds 2000 of them. Denials are
    # cached as well as approvals: an upload aimed entirely at a lab the
    # caller cannot write to is the case most likely to be adversarial, and
    # a success-only memo would re-run the guard on every one of its rows.
    lab_decisions: dict[object, HTTPException | None] = {}

    for idx, raw_row in enumerate(reader, start=1):
        try:
            metadata = _coerce_csv_row(raw_row)
            # Per row, not per file: a CSV may span labs, and a row the
            # caller may not write to fails as that row's error while the
            # rest of the upload proceeds — the same shape every other
            # per-row validation failure has.
            row_lab = metadata.get("lab_id")
            if row_lab not in lab_decisions:
                try:
                    _require_sample_create(user, metadata)
                    lab_decisions[row_lab] = None
                except HTTPException as denial:
                    lab_decisions[row_lab] = denial
            cached_denial = lab_decisions[row_lab]
            if cached_denial is not None:
                raise cached_denial
            filenames = _split_files_column(metadata.pop("files", "") or "")
            if not filenames:
                raise HTTPException(status_code=422, detail="Row missing 'files' column.")
            # Phase P0f F-6: per-row storage intent. Default EXTERNAL per
            # Critical Rule 57; STAGED/BROKEN are internal lifecycle
            # states and rejected here. Missing column → EXTERNAL plus
            # an envelope-level warning surfaced below.
            row_intent = (metadata.pop("storage_intent", None) or "EXTERNAL").strip().upper()
            if row_intent == "":
                row_intent = "EXTERNAL"
            if row_intent not in VALID_STORAGE_INTENTS:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Invalid storage_intent {row_intent!r}; "
                        f"must be one of {sorted(VALID_STORAGE_INTENTS)}."
                    ),
                )
            sample_id = metadata.get("sample_id", f"row-{idx}")
            uri_map = {fn: f"gs://jackpot-staging/{sample_id}/{fn}" for fn in filenames}
            size_map = {fn: 0 for fn in filenames}
            sample, _files = _ingest_one(
                metadata,
                uri_map,
                size_map,
                user,
                db,
                "csv",
                storage_intent=row_intent,
            )
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

    warnings: list[str] = []
    if not storage_intent_column_present:
        warnings.append(_CSV_STORAGE_INTENT_MISSING_WARNING)

    return {
        "data": {
            "success": successes,
            "failed": failures,
            "errors": errors,
            "created_ids": created_ids,
        },
        "warnings": warnings or None,
    }


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

    result = run_csv_ingest(csv_text=text, user=user, db=db)
    return success(data=result["data"], warnings=result["warnings"])


def _validate_register_payload(payload: "_RegisterRequest") -> list[str]:
    """Non-empty check, URI scheme validation, storage_intent validation.

    Raises HTTPException on any invalid input. Returns the resolved
    storage_intent for each file, in request order.
    """
    if not payload.files:
        raise HTTPException(status_code=422, detail="files must be a non-empty list.")

    # R-1 #2: validate every URI scheme up-front before any DB row is
    # written. Any rejected scheme aborts the entire request — partial
    # registrations would leave the sample row half-created.
    for spec in payload.files:
        _validate_register_uri_scheme(spec.uri)

    # Up-front validation of every file's storage_intent so we don't
    # half-create a sample before discovering an invalid value mid-loop.
    resolved_intents: list[str] = []
    for spec in payload.files:
        intent = (spec.storage_intent or "EXTERNAL").strip().upper()
        if intent == "":
            intent = "EXTERNAL"
        if intent not in VALID_STORAGE_INTENTS:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid storage_intent {intent!r}; "
                    f"must be one of {sorted(VALID_STORAGE_INTENTS)}."
                ),
            )
        resolved_intents.append(intent)

    return resolved_intents


def _build_sample_record(payload: "_RegisterRequest", user: dict, db: Any) -> tuple[dict, Any]:
    """Metadata validation, sequencing_lab check, epiweek + tier + convenience
    URI computation. Raises HTTPException on invalid metadata. Returns
    (record, validation) — quality_status/surveillance_relevant are already
    embedded in ``record`` and come back out via the inserted row's
    RETURNING * (Critical Rule 40), so they aren't threaded separately."""
    metadata = dict(payload.sample_metadata)
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

    quality_status = compute_quality_status(validation)
    reportable = _get_reportable_organisms(db)
    surveillance_relevant = compute_surveillance_relevant(
        metadata.get("organism_name", ""),
        metadata.get("target_organisms"),
        reportable,
    )

    # Convenience URIs (samples.fastq_r1_uri is NOT NULL): the first
    # R1/R2 file in the request fills in the legacy columns. Long-read
    # / assembly-only registrations satisfy the constraint with the
    # first file's URI as a placeholder.
    fastq_r1_uri = next((s.uri for s in payload.files if s.role == "R1"), None)
    fastq_r2_uri = next((s.uri for s in payload.files if s.role == "R2"), None)
    if fastq_r1_uri is None:
        fastq_r1_uri = payload.files[0].uri

    record = dict(metadata)
    record["owner_id"] = user["id"]
    record.update(epi)
    record["sector"] = validation.sector or record.get("sector")
    record["surveillance_relevant"] = surveillance_relevant
    record["quality_status"] = quality_status
    record.setdefault("scrub_status", "PENDING")
    record.setdefault("pii_scan_status", "PENDING")
    record["ingest_method"] = "register"
    record.setdefault("sharing_level", "PRIVATE")
    record["fastq_r1_uri"] = fastq_r1_uri
    if fastq_r2_uri is not None:
        record["fastq_r2_uri"] = fastq_r2_uri

    return record, validation


def _register_files_for_sample(
    payload: "_RegisterRequest",
    resolved_intents: list[str],
    sample: dict,
    user: dict,
    db: Any,
) -> list[dict]:
    """Register every file against the sample, auditing each. Raises
    HTTPException (400 FILE_UNREACHABLE / 422) on any registration failure —
    the caller's transaction rolls back the whole sample on raise."""
    registered_files: list[dict] = []
    current_spec = None
    try:
        for spec, intent in zip(payload.files, resolved_intents, strict=True):
            current_spec = spec
            sf_id, was_dedup = register_file(
                spec.uri,
                intent,
                sample["id"],
                spec.role,
                conn=db,
                ingest_method="register",
            )
            registered_files.append(
                {
                    "sample_files_id": sf_id,
                    "uri": spec.uri,
                    "storage_state": intent,
                    "deduplicated": was_dedup,
                }
            )
            log_audit(
                action=(AuditActions.DEDUP_FILE if was_dedup else AuditActions.REGISTER_FILE),
                actor_id=user["id"],
                resource_type="sample_files",
                resource_id=str(sf_id),
                before=None,
                after={
                    "uri": spec.uri,
                    "storage_state": intent,
                    "sample_id_fk": sample["id"],
                },
                metadata={"ingest_method": "register", "role": spec.role},
                db_conn=db,
            )
    except (FileNotFoundError, PermissionError, OSError, BotoCoreError, ClientError) as exc:
        # Phase P0f F-6: roll back the entire sample registration if
        # any file is unreachable — partial success is worse than clean
        # failure for an ingest API. gs://-/s3:// fingerprinting raises
        # botocore ClientError/BotoCoreError (not OSError) for a missing,
        # forbidden, or unreachable object, so those map to 400 too. The
        # transaction is owned by get_db_dep; raising here triggers
        # rollback in the dep cleanup.
        bad_uri = current_spec.uri if current_spec else "<unknown>"
        raise HTTPException(
            status_code=400,
            detail={
                "code": "FILE_UNREACHABLE",
                "message": f"Unable to read file at {bad_uri}: {exc}",
                "detail": {
                    "uri": bad_uri,
                    "underlying_error": f"{type(exc).__name__}: {exc}",
                    "suggestion": (
                        "Check that the JACKPOT service user can read this "
                        "path, or upload via /api/v1/ingest/upload instead."
                    ),
                },
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return registered_files


@router.post("/register", status_code=201)
@limiter.limit(_INGEST_LIMIT)
async def register_paths(
    request: Request,
    payload: _RegisterRequest,
    db=Depends(get_db_dep),  # noqa: B008
):
    """Register a sample with one or more files at given URIs.

    Phase P0f F-6. No file bytes are uploaded — JACKPOT registers
    metadata pointing at file paths/URIs the operator has already
    placed. Per Critical Rule 57 the default ``storage_state`` is
    ``EXTERNAL``; ``MANAGED`` and ``MIRRORED`` are accepted intents but
    the actual byte-copy is owned by F-9 (``promote``) and only the
    ``storage_state`` flag is set here. See ``spec.md`` Phase P0f
    Specification, Critical Rules 57 (no copy on ingest) and 58
    (sample_files is the dedup primitive).
    """
    user = get_current_user(request)

    _require_sample_create(user, payload.sample_metadata)
    resolved_intents = _validate_register_payload(payload)
    record, validation = _build_sample_record(payload, user, db)

    sample = _insert_sample(record, db)
    log_audit(
        action=AuditActions.CREATE_SAMPLE,
        actor_id=user["id"],
        resource_type="sample",
        resource_id=str(sample["id"]),
        before=None,
        after=_serialise(sample),
        metadata={"ingest_method": "register", "tier": validation.tier},
        db_conn=db,
    )

    registered_files = _register_files_for_sample(payload, resolved_intents, sample, user, db)

    return success(
        data={
            "sample_id": sample["sample_id"],
            "id": sample["id"],
            "quality_status": sample["quality_status"],
            "surveillance_relevant": sample["surveillance_relevant"],
            "files": registered_files,
        },
        status_code=201,
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

    Phase P0f F-6: when metadata arrives later (the lab director
    follows the notification through to the ingest UI), the actual
    sample_files registration flows through ``register_file`` via
    ``/upload`` or ``/register``. Files registered from a Globus
    deposit are always ``EXTERNAL`` — JACKPOT references the file at
    its Globus access endpoint rather than copying. The cheap
    fingerprint of a Globus URI translates to its underlying HTTPS
    access form (covered by the ``http(s)://`` branch of
    ``cheap_fingerprint``).
    """
    user = get_current_user(request)
    # deposit:record, not sample:create — this endpoint creates no samples
    # (see the docstring); it records a deposit and notifies directors.
    require_capability("deposit:record")(user)

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
