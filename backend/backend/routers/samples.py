import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from backend import deletion
from backend.audit import AuditActions, log_audit
from backend.auth.guards import (
    get_current_user,
    permits,
    require_capability,
)
from backend.authz.principal import load_principal
from backend.authz.visibility import sample_list_clause
from backend.database import execute_query, execute_write, get_db_dep
from backend.dlp_scanner import get_scannable_fields
from backend.pagination import paginate
from backend.responses import success, success_list
from backend.storage import StorageError, generate_presigned_url
from backend.validator import (
    compute_quality_status,
    compute_surveillance_relevant,
    validate_sample,
)

router = APIRouter(prefix="/api/v1/samples", tags=["samples"])
logger = logging.getLogger(__name__)


# Columns clients MAY NOT set directly via PATCH. These are either system-
# computed (quality_status, surveillance_relevant, scrub_status, epiweeks)
# or change-of-custody events that need their own endpoint (owner_id,
# lab_id, project_id, sharing_level transitions, NCBI accessions, etc.).
_LOCKED_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "quality_status",
        "surveillance_relevant",
        "scrub_status",
        "pii_scan_status",
        "mmwr_week",
        "mmwr_year",
        "iso_week",
        "iso_year",
        "ingest_timestamp",
        "ingest_method",
        "is_archived",
        "deletion_status",
        "deletion_requested_at",
        "deletion_requested_by_user_id",
        "deletion_reason",
        "tombstoned_at",
        "vacuumed_at",
        "vacuum_retry_at",
        "deleted_at",
        "deleted_by_id",
        "owner_id",
        "lab_id",
        "project_id",
        "biosample_accession",
        "sra_accession",
        "genbank_accession",
        "gisaid_accession",
        "bioproject_accession",
        "ncbi_submission_status",
        "ncbi_submitted_at",
        "gisaid_submission_status",
        "gisaid_submitted_at",
        "pango_lineage",
        "pango_lineage_version",
        "nextstrain_clade",
        "nextclade_qc_score",
        "nextclade_version",
        "vadr_status",
        "vadr_alerts",
        "mlst_scheme",
        "mlst_sequence_type",
        "amrfinder_genes",
        "card_aro_terms",
        "assembly_method",
        "coverage_depth",
        "genome_completeness",
        "fastq_r1_uri",
        "fastq_r2_uri",
        "raw_fastq_uri",
        "consensus_fasta_uri",
        "assembly_uri",
    }
)

# Columns clients MAY patch — whitelist mirrors the metadata-editable
# portion of the samples table.
_EDITABLE_FIELDS: frozenset[str] = frozenset(
    {
        "sample_id",
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
        "date_sequenced",
        "collection_facility",
        "purpose_for_collection",
        "collection_location_country",
        "collection_location_state",
        "collection_location_county",
        "collection_location_zipcode",
        "geo_lat",
        "geo_lon",
        "ct_value",
        "other_testing_performed",
        "lab_of_other_testing",
        "intermediary_clinical_lab",
        "pi_name",
        "grant_number",
        "contact_other",
        "comments",
        "sharing_level",
        "sector",
        "organism_name",
        "source_type",
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
        "vaccination_status",
        "clinical_outcome",
        "underlying_conditions",
        # Animal
        "wildlife_subject_id",
        "companion_subject_id",
        "livestock_subject_id",
        "livestock_products",
        "distribution_scale",
        "antibiotic_use",
        "location_type",
        "vaccine_status_against_pathogen",
        "symptomatic",
        # Vector
        "vector_species",
        "vector_host_species",
        # Wastewater
        "wwtp_name",
        "sample_location_zipcode",
        "county_names",
        "population_served",
        "sample_type_ww",
        "sample_matrix",
        "pretreatment",
        "concentration_method",
        "flow_rate_mgd",
        "sample_collect_time",
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


def _get_sample(sample_id: int, conn) -> dict | None:
    rows = execute_query(
        "SELECT * FROM samples WHERE id = :id AND is_archived = FALSE "
        "AND deletion_status NOT IN ('TOMBSTONED', 'VACUUMED') LIMIT 1",
        {"id": sample_id},
        conn=conn,
    )
    return rows[0] if rows else None


def _get_sample_files(sample_id: int, conn) -> list[dict]:
    return execute_query(
        "SELECT * FROM sample_files WHERE sample_id_fk = :sid AND is_archived = FALSE "
        "ORDER BY id ASC",
        {"sid": sample_id},
        conn=conn,
    )


def _require_readable(user: dict, sample: dict | None) -> dict:
    """Raise 404 if missing, 403 if denied. Returns the sample row.

    M2-B2: the decision is ``sample:read_detail`` at Sample scope. The fetch
    stays ahead of the guard so the 404 answers survive unchanged — an
    archived or tombstoned sample is not found rather than forbidden, which
    ``_get_sample``'s filter, not the authorization model, decides.
    """
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found.")
    require_capability("sample:read_detail")(user, sample_id=sample["id"])
    return sample


def _build_sample_filters(
    *,
    vis_clause: str,
    vis_params: dict,
    organism_name: str | None,
    source_type: str | None,
    sector: str | None,
    quality_status: str | None,
    scrub_status: str | None,
    sharing_level: str | None,
    lab_id: int | None,
    project_id: int | None,
    owner_id: int | None,
    date_from: str | None,
    date_to: str | None,
    surveillance_relevant: bool | None,
    has_broken_files: bool | None,
) -> tuple[list[str], dict]:
    """Build the WHERE-clause fragments + bind params for list_samples'
    optional filters, layered on top of the base visibility clause."""
    where: list[str] = [
        "s.is_archived = FALSE",
        "s.deletion_status NOT IN ('TOMBSTONED', 'VACUUMED')",
        vis_clause,
    ]
    params: dict = dict(vis_params)

    if organism_name:
        where.append("s.organism_name = :organism_name")
        params["organism_name"] = organism_name
    if source_type:
        where.append("s.source_type = :source_type")
        params["source_type"] = source_type
    if sector:
        where.append("s.sector = :sector")
        params["sector"] = sector
    if quality_status:
        where.append("s.quality_status = :quality_status")
        params["quality_status"] = quality_status
    if scrub_status:
        where.append("s.scrub_status = :scrub_status")
        params["scrub_status"] = scrub_status
    if sharing_level:
        where.append("s.sharing_level = :sharing_level")
        params["sharing_level"] = sharing_level
    if lab_id is not None:
        where.append("s.lab_id = :lab_id")
        params["lab_id"] = lab_id
    if project_id is not None:
        where.append("s.project_id = :project_id")
        params["project_id"] = project_id
    if owner_id is not None:
        where.append("s.owner_id = :owner_id")
        params["owner_id"] = owner_id
    if date_from:
        where.append("s.date_collected >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where.append("s.date_collected <= :date_to")
        params["date_to"] = date_to
    if surveillance_relevant is not None:
        where.append("s.surveillance_relevant = :surveillance_relevant")
        params["surveillance_relevant"] = surveillance_relevant
    if has_broken_files:
        # Phase P0f F-10: include only samples that have at least one
        # sample_files row in BROKEN state. EXISTS keeps the join lazy.
        where.append(
            "EXISTS (SELECT 1 FROM sample_files sf "
            "WHERE sf.sample_id_fk = s.id "
            "AND sf.storage_state = 'BROKEN' "
            "AND sf.is_archived = FALSE)"
        )

    return where, params


@router.get("/")
def list_samples(
    request: Request,
    organism_name: str | None = None,
    source_type: str | None = None,
    sector: str | None = None,
    quality_status: str | None = None,
    scrub_status: str | None = None,
    sharing_level: str | None = None,
    lab_id: int | None = None,
    project_id: int | None = None,
    owner_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    surveillance_relevant: bool | None = None,
    has_broken_files: bool | None = None,
    select_all: bool = False,
    page: int = 1,
    per_page: int = Query(50, ge=1, le=500),
    sort_by: str = "ingest_timestamp",
    sort_dir: str = "desc",
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)

    # M2-B7: the list filter is now compiled from the same grants and policies
    # permit() reads, rather than permissions.py's hand-written ladder. The
    # samples JOIN labs below is not decoration — a sample's scope is derived
    # from its lineage (ADR 0015) and the org segment comes from labs.
    vis_clause, vis_params = sample_list_clause(load_principal(user["id"]))
    where, params = _build_sample_filters(
        vis_clause=vis_clause,
        vis_params=vis_params,
        organism_name=organism_name,
        source_type=source_type,
        sector=sector,
        quality_status=quality_status,
        scrub_status=scrub_status,
        sharing_level=sharing_level,
        lab_id=lab_id,
        project_id=project_id,
        owner_id=owner_id,
        date_from=date_from,
        date_to=date_to,
        surveillance_relevant=surveillance_relevant,
        has_broken_files=has_broken_files,
    )

    where_sql = " AND ".join(where)

    if select_all:
        rows = execute_query(
            f"SELECT s.id FROM samples s JOIN labs l ON l.id = s.lab_id WHERE {where_sql}",
            params,
            conn=db,
        )
        ids = [r["id"] for r in rows]
        return success(data={"ids": ids, "count": len(ids)})

    base_query = f"SELECT s.* FROM samples s JOIN labs l ON l.id = s.lab_id WHERE {where_sql}"
    results, total = paginate(
        base_query,
        params,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return success_list(
        data=[_serialise(r) for r in results],
        page=page,
        per_page=per_page,
        total=total,
    )


@router.get("/{sample_id}")
def get_sample(
    sample_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sample = _require_readable(user, _get_sample(sample_id, db))
    files = _get_sample_files(sample_id, db)
    out = _serialise(sample)
    out["files"] = [_serialise(f) for f in files]
    return success(data=out)


def _require_sample_writable(user: dict, sample: dict) -> None:
    """Writes require ``sample:update`` at the sample's scope.

    M2-B2. The three legacy rungs are all preserved by the preset mapping
    rather than by branches here: Platform Admin holds it instance-wide, Lab
    Collaborator and Bioinformatics User hold it through ``lab_member_rw``,
    and ``lab_member_ro`` (Lab Reader) deliberately does not list it. The
    single 403 replaces two differently-worded ones; the distinction was
    never actionable and telling a caller which rung they failed on is a
    membership disclosure.
    """
    require_capability("sample:update")(user, sample_id=sample["id"])


async def _parse_sample_update_body(request: Request) -> dict:
    """Parse and validate a PATCH body into an editable-fields update dict.
    Raises HTTPException on invalid JSON, locked-field attempts, or an
    empty update."""
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid JSON body: {exc}") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Body must be a JSON object.")

    # Reject attempts to touch locked fields outright — preserves immutability
    # of system-computed state and channels privileged changes through their
    # dedicated endpoints.
    locked_attempted = sorted(k for k in body if k in _LOCKED_FIELDS)
    if locked_attempted:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Fields {locked_attempted} cannot be updated via PATCH. "
                "quality_status and surveillance_relevant are recomputed "
                "automatically; other fields have dedicated endpoints."
            ),
        )

    updates = {k: v for k, v in body.items() if v is not None and k in _EDITABLE_FIELDS}
    if not updates:
        raise HTTPException(status_code=422, detail="No updatable fields provided.")
    return updates


def _recompute_sample_derived_fields(sample_id: int, merged: dict, updated: dict, db) -> dict:
    """Recompute quality_status/surveillance_relevant from the post-update
    row and write them. We pull the full sample shape so the validator sees
    all required-for-tier fields. Falls back to `updated` if the recompute
    write returns no row."""
    validation = validate_sample(merged)
    new_quality = compute_quality_status(validation)

    reportable_rows = execute_query(
        "SELECT organism_name FROM reportable_organisms WHERE is_active = TRUE",
        conn=db,
    )
    reportable = {r["organism_name"] for r in reportable_rows}
    new_surveillance = compute_surveillance_relevant(
        merged.get("organism_name", ""),
        merged.get("target_organisms"),
        reportable,
    )

    recompute = execute_write(
        "UPDATE samples SET quality_status = :q, surveillance_relevant = :s "
        "WHERE id = :_id RETURNING *",
        {"q": new_quality, "s": new_surveillance, "_id": sample_id},
        conn=db,
    )
    return recompute[0] if recompute else updated


@router.patch("/{sample_id}")
async def update_sample(
    sample_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sample = _get_sample(sample_id, db)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found.")

    _require_sample_writable(user, sample)
    updates = await _parse_sample_update_body(request)

    # Critical Rule 43's other way off PII_DETECTED: "the submitter fixes the
    # flagged fields". Editing any DLP-scanned field returns the sample to
    # PENDING so run_pii_scan_job re-decides it. Without this a flagged sample
    # is stuck behind a Lab Director even after the offending text is gone,
    # because nothing else moves a row back into the job's queue.
    rescan = bool(updates.keys() & get_scannable_fields()) and (
        sample.get("pii_scan_status") == "PII_DETECTED"
    )

    set_fragments = [f"{k} = :{k}" for k in sorted(updates)]
    if rescan:
        set_fragments.append("pii_scan_status = 'PENDING'")
    query = f"UPDATE samples SET {', '.join(set_fragments)} WHERE id = :_id RETURNING *"
    params = {**updates, "_id": sample_id}
    rows = execute_write(query, params, conn=db)
    updated = rows[0]

    # Recompute derived fields from the post-update row. We pull the full
    # sample shape so the validator sees all required-for-tier fields.
    merged = {**sample, **updates}
    final = _recompute_sample_derived_fields(sample_id, merged, updated, db)

    log_audit(
        action=AuditActions.UPDATE_SAMPLE,
        actor_id=user["id"],
        resource_type="sample",
        resource_id=str(sample_id),
        before=_serialise(sample),
        after=_serialise(final),
        metadata={
            "fields": sorted(updates.keys()),
            # An edit that returns a flagged sample to the scan queue is the
            # one PATCH that changes what the sample is allowed to do.
            **({"pii_rescan_requeued": True} if rescan else {}),
        },
        db_conn=db,
    )
    return success(data=_serialise(final))


@router.delete("/{sample_id}")
def archive_sample(
    sample_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sample = _get_sample(sample_id, db)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found.")

    # sample:archive sits in the lab_lead and instance_administrator presets
    # only — the same two roles the director-or-admin branch admitted.
    require_capability("sample:archive")(user, sample_id=sample_id)

    rows = execute_write(
        "UPDATE samples SET is_archived = TRUE, deleted_at = NOW(), "
        "deleted_by_id = :uid WHERE id = :_id RETURNING *",
        {"uid": user["id"], "_id": sample_id},
        conn=db,
    )
    archived = rows[0] if rows else sample

    log_audit(
        action=AuditActions.ARCHIVE_SAMPLE,
        actor_id=user["id"],
        resource_type="sample",
        resource_id=str(sample_id),
        before=_serialise(sample),
        after=_serialise(archived),
        metadata=None,
        db_conn=db,
    )
    return success(data={"id": sample_id, "is_archived": True})


@router.get("/{sample_id}/files")
def list_sample_files(
    sample_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sample = _require_readable(user, _get_sample(sample_id, db))
    files = _get_sample_files(sample["id"], db)
    return success(data=[_serialise(f) for f in files])


def _parse_uri(uri: str) -> tuple[str, str]:
    """Split 'gs://bucket/key' or 's3://bucket/key' into (bucket, key)."""
    for prefix in ("gs://", "s3://"):
        if uri.startswith(prefix):
            rest = uri[len(prefix) :]
            if "/" not in rest:
                raise ValueError(f"URI missing key portion: {uri}")
            bucket, key = rest.split("/", 1)
            return bucket, key
    raise ValueError(f"Unsupported URI scheme: {uri}")


@router.get("/{sample_id}/download")
def download_sample(
    sample_id: int,
    request: Request,
    file_type: str = Query(
        "fastq_r1",
        description="Which convenience URI to sign: fastq_r1, fastq_r2, "
        "raw_fastq, consensus_fasta, or assembly.",
    ),
    ttl: int = Query(3600, ge=60, le=86400),
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sample = _require_readable(user, _get_sample(sample_id, db))

    column_map = {
        "fastq_r1": "fastq_r1_uri",
        "fastq_r2": "fastq_r2_uri",
        "raw_fastq": "raw_fastq_uri",
        "consensus_fasta": "consensus_fasta_uri",
        "assembly": "assembly_uri",
    }
    if file_type not in column_map:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown file_type '{file_type}'. Allowed: {sorted(column_map.keys())}.",
        )

    # M2-DROP-PRE slice 2: the narrower pre-scrub restriction now has a verb.
    # sample:read_unscrubbed sits INSIDE sample:read_detail — the route has
    # already required that above — so this is a second, narrower check on the
    # same resource rather than an alternative to the first.
    #
    # The platform-admin arm of the legacy branch is deliberately NOT carried
    # over. §8.2's Instance Administrator holds no content-read verb, and
    # admitting it to *pre-scrub* content while barring it from post-scrub
    # detail is incoherent. An operator who needs raw reads holds Lab Lead at
    # the lab, which is where the data actually lives.
    if file_type == "raw_fastq":
        require_capability("sample:read_unscrubbed")(user, sample_id=sample_id)

    uri = sample.get(column_map[file_type])
    if not uri:
        raise HTTPException(
            status_code=404,
            detail=f"No {file_type} file registered for this sample.",
        )

    try:
        bucket, key = _parse_uri(uri)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        url = generate_presigned_url(bucket, key, ttl_seconds=ttl)
    except StorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return success(data={"url": url, "expires_in": ttl, "file_type": file_type})


# ── Sovereignty deletion lifecycle (B-CARE-3a..3g) ──────────────────────────
# Authorization per sovereignty design §10; state machine + effects live in
# backend/deletion.py. Tombstoned/vacuumed rows are invisible to the normal
# sample surfaces, so these endpoints fetch without the visibility filter.


class DeletionRequestBody(BaseModel):
    reason: str


class ApproveDeletionBody(BaseModel):
    platform_admin_self_approve: bool = False


class VacuumNowBody(BaseModel):
    justification: str


class RetractionRequestBody(BaseModel):
    repository: str
    accession: str | None = None
    retraction_protocol: str | None = None


def _get_sample_any_or_404(sample_id: int, db) -> dict:
    sample = deletion.get_sample_any_state(sample_id, db)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found.")
    return sample


@router.post("/{sample_id}/request-deletion")
def request_sample_deletion(
    sample_id: int,
    payload: DeletionRequestBody,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sample = _get_sample_any_or_404(sample_id, db)
    # M3: the §10 "platform admin, owner, or lab member" ladder became a
    # capability. Ownership survives as LADDER_POLICIES' owner_id rung for
    # deletion:request specifically — M3 claimed that in this comment before
    # the rung existed, and a rung for a different verb does nothing, because
    # _matches compares capability by equality. §5.3's ownership row now
    # enumerates every verb the rung carries and a test holds it to that.
    require_capability("deletion:request")(user, sample_id=sample_id)
    row = deletion.request_deletion(sample, user, payload.reason, db)
    return success(data=_serialise(row))


@router.post("/{sample_id}/cancel-deletion")
def cancel_sample_deletion(
    sample_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sample = _get_sample_any_or_404(sample_id, db)
    if sample.get("deletion_requested_by_user_id") != user["id"]:
        # Cancelling someone else's request is an approval-authority act. It
        # takes deletion:approve without the separation-of-duties condition:
        # the DENY keys on the caller BEING the requester, and this branch
        # runs only when they are not, so it cannot fire here.
        require_capability("deletion:approve")(user, sample_id=sample_id)
    row = deletion.cancel_deletion(sample, user, db)
    return success(data=_serialise(row))


@router.post("/{sample_id}/approve-deletion")
def approve_sample_deletion(
    sample_id: int,
    request: Request,
    payload: ApproveDeletionBody | None = None,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sample = _get_sample_any_or_404(sample_id, db)
    # The flag is a REQUEST, not the decision. §6.2-1b's escape is for a
    # Platform Admin; taking payload.platform_admin_self_approve at face value
    # made the separation-of-duties DENY liftable by anyone who set it, which
    # is the opposite of what an audited escape means. What the caller asked
    # for is ANDed with what they actually hold.
    self_approve = bool(payload and payload.platform_admin_self_approve) and permits(
        user, "deletion:self_approve", sample_id=sample_id
    )
    # M3: separation of duties is now deletion.separation_of_duties, a DENY
    # policy (§6.2-1b), so the approver-differs-from-requester rule is decided
    # by permit() rather than re-derived here. The self-approve flag travels as
    # a Context condition because that is what the policy reads — passing it
    # only to approve_deletion would leave the guard denying a call the route
    # then went on to allow.
    require_capability("deletion:approve")(
        user,
        sample_id=sample_id,
        conditions={"platform_admin_self_approve": self_approve},
    )
    row = deletion.approve_deletion(sample, user, db, self_approve=self_approve)
    return success(data=_serialise(row))


@router.post("/{sample_id}/reverse-tombstone")
def reverse_sample_tombstone(
    sample_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    # M2-DROP-PRE slice 2. Operational, not consent: reversing a tombstone
    # unmakes a purge that has not happened yet, and the sample is still whole.
    # Kept separate from deletion:vacuum so a deployment can hand the execute
    # half to an authority without the undo half (§8.3's shape); nobody holds
    # them apart today.
    # 404 before the guard: sample_resource raises for an unknown id and the
    # guard turns that into 403, which would report "not allowed" for a sample
    # that does not exist. Same ordering as deletion-report.
    sample = _get_sample_any_or_404(sample_id, db)
    require_capability("deletion:reverse_tombstone")(user, sample_id=sample_id)
    row = deletion.reverse_tombstone(sample, user, db)
    return success(data=_serialise(row))


@router.post("/{sample_id}/vacuum-now")
def vacuum_sample_now(
    sample_id: int,
    payload: VacuumNowBody,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    # M2-DROP-PRE slice 2. Executes a decision the consent authority already
    # made — the sample is TOMBSTONED before this route will touch it — which
    # is why it sits with the operational admin and not behind deletion:approve.
    sample = _get_sample_any_or_404(sample_id, db)
    require_capability("deletion:vacuum")(user, sample_id=sample_id)
    if not payload.justification.strip():
        raise HTTPException(status_code=422, detail="A justification is required.")
    row = deletion.vacuum_sample(
        sample, user["id"], db, trigger="vacuum-now", justification=payload.justification
    )
    return success(data=_serialise(row))


@router.get("/{sample_id}/deletion-report")
def sample_deletion_report(
    sample_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sample = _get_sample_any_or_404(sample_id, db)
    # M2-DROP-PRE slice 2. _require_lab_tie's three rungs — platform admin,
    # owner, lab member — become one capability: the admin and member rungs
    # are grants (§8.2 puts deletion:read_report in the Instance Administrator
    # preset and in all three lab presets), and ownership is LADDER_POLICIES'
    # owner_id rung, added alongside this route.
    #
    # The admin KEEPS this route where it loses the raw-FASTQ one above. The
    # report is lifecycle state, erasure evidence and an audit trail — a
    # governance record, not sample content — which is the same line audit:read
    # already sits on.
    require_capability("deletion:read_report")(user, sample_id=sample_id)
    return success(data=deletion.deletion_report(sample, db))


@router.post("/{sample_id}/retraction-requests", status_code=201)
def create_retraction_request(
    sample_id: int,
    payload: RetractionRequestBody,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sample = _get_sample_any_or_404(sample_id, db)
    # M2-DROP-PRE slice 2. Its own verb rather than a reuse of
    # submission:approve: retraction is the deletion plane reaching outward
    # (B-CARE-3g), and one verb for both would hand repository-retraction to
    # every future preset that gains submission approval for submission
    # reasons. The platform-admin arm is not carried over — asking a
    # repository to withdraw a published record is the consent act §8.2's note
    # keeps away from the operational admin, the same call M3 made for
    # deletion:approve.
    require_capability("submission:retract")(user, sample_id=sample_id)
    row = deletion.record_retraction_request(
        sample,
        user,
        db,
        repository=payload.repository,
        accession=payload.accession,
        retraction_protocol=payload.retraction_protocol,
    )
    return success(data=_serialise(row), status_code=201)
