# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Submission router for I-2.

Thin shell over :mod:`backend.submissions` and
:mod:`backend.submission_packages`. Each endpoint:

- Resolves the calling user, applies lab-scoped RBAC.
- Delegates to the business-logic module.
- Wraps the return value in the standard envelope per Critical Rule 24.
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from backend.auth.guards import (
    get_current_user,
    permits,
    require_capability,
)
from backend.config import get_settings
from backend.credentials import credentials
from backend.credentials.base import CredentialNotFoundError
from backend.database import get_db_dep
from backend.responses import error, success, success_list
from backend.submission_packages import generate_package
from backend.submissions import (
    AccessionEntry,
    add_samples_to_submission,
    create_submission,
    get_submission,
    list_submissions,
    mark_execution_queued,
    mark_execution_retried,
    mark_rejected,
    mark_submitted,
    parse_accessions_tsv,
    register_accessions,
    remove_samples_from_submission,
    soft_delete_submission,
    update_submission,
    validate_submission_readiness,
    withdraw_submission,
)

router = APIRouter(prefix="/api/v1/submissions", tags=["submissions"])
logger = logging.getLogger(__name__)


# ── pydantic bodies ───────────────────────────────────────────────


class _CreateBody(BaseModel):
    lab_id: int
    target_repository: str
    title: str
    description: str | None = None
    sample_ids: list[int]
    bioproject_accession: str | None = None
    release_date: date | None = None


class _PatchBody(BaseModel):
    title: str | None = None
    description: str | None = None
    release_date: date | None = None
    bioproject_accession: str | None = None
    target_repository: str | None = None


class _SamplesBody(BaseModel):
    sample_ids: list[int]


class _RejectBody(BaseModel):
    reason: str


class _WithdrawBody(BaseModel):
    reason: str


class _GenerateBody(BaseModel):
    copy_files: bool = False


class _AccessionsBody(BaseModel):
    """Inline JSON form of an accessions registration. The ``/upload``
    endpoint accepts a TSV file as an alternative."""

    accessions: list[dict]


# ── helpers ───────────────────────────────────────────────────────


def _ensure_lab_access(user: dict, lab_id: int, capability: str) -> None:
    """The submission's lab, and the verb this route needs (M2-B4).

    The platform-admin branch is gone: an instance-scoped grant contains every
    lab path (ADR 0015), so the admin passes on the same rung as everyone else.
    """
    require_capability(capability)(user, lab_id=lab_id)


def _ensure_can_read(user: dict, submission: dict) -> None:
    """Reads take ``sample:read`` at the submission's lab, per the map — a
    submission is a view onto samples, and every lab preset holds it."""
    _ensure_lab_access(user, submission["lab_id"], "sample:read")


def _ensure_can_prepare(user: dict, submission: dict) -> None:
    """Building and editing: ``submission:prepare`` (§4.5).

    Replaces "the creator, or a lab director, or an admin". The creator rung
    is subsumed rather than dropped: creating a submission already requires
    ``submission:prepare`` at that lab, so anyone who could have created one
    holds the verb that now lets them edit it. What changes is that a creator
    who has since lost the capability stops being able to edit — which is the
    point of checking a capability rather than a stored user id.
    """
    _ensure_lab_access(user, submission["lab_id"], "submission:prepare")


def _ensure_can_approve(user: dict, submission: dict) -> None:
    """Publishing and its consequences: ``submission:approve`` (§4.5).

    This is the separation the batch exists for, and it is a real narrowing.
    The old check let a submission's *creator* mark it submitted, execute it,
    or register accessions — the same person who built the package could send
    it. ``submission:approve`` sits in ``lab_lead`` and nowhere else, so those
    six routes now need a Lab Lead. §8.2's Lab Member RW note already said as
    much: "can run pipelines but not approve submissions or access requests."
    """
    _ensure_lab_access(user, submission["lab_id"], "submission:approve")


# ── endpoints ─────────────────────────────────────────────────────


@router.post("/", status_code=201)
def create_submission_endpoint(
    request: Request,
    body: _CreateBody,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    _ensure_lab_access(user, body.lab_id, "submission:prepare")
    sub = create_submission(
        user_id=user["id"],
        lab_id=body.lab_id,
        target_repository=body.target_repository,
        title=body.title,
        description=body.description,
        sample_ids=body.sample_ids,
        bioproject_accession=body.bioproject_accession,
        release_date=body.release_date,
        conn=db,
    )
    return success(data=sub, status_code=201)


@router.get("/")
def list_submissions_endpoint(
    request: Request,
    lab_id: int | None = None,
    status: str | None = None,
    target_repository: str | None = None,
    page: int = 1,
    per_page: int = Query(50, ge=1, le=500),
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    if lab_id is not None:
        _ensure_lab_access(user, lab_id, "sample:read")
    elif not permits(user, "sample:read"):
        # Unfiltered means every lab, so it takes the capability at the
        # instance root rather than the is_platform_admin flag, which has
        # authorized nothing since M2-B1.
        # Non-admins must be scoped to their labs explicitly. We could
        # implement a "show all my labs" flow but the simpler v1
        # contract is "ask for a lab_id."
        raise HTTPException(
            status_code=400,
            detail="Provide ?lab_id=… (or call as Platform Admin to see all).",
        )
    rows, total = list_submissions(
        lab_id=lab_id,
        status=status,
        target_repository=target_repository,
        page=page,
        per_page=per_page,
        conn=db,
    )
    return success_list(data=rows, page=page, per_page=per_page, total=total)


@router.get("/{submission_id}")
def get_submission_endpoint(
    submission_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sub = get_submission(submission_id, db)
    _ensure_can_read(user, sub)
    return success(data=sub)


@router.patch("/{submission_id}")
def patch_submission_endpoint(
    submission_id: int,
    request: Request,
    body: _PatchBody,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sub = get_submission(submission_id, db)
    _ensure_can_prepare(user, sub)
    fields = body.model_dump(exclude_none=True)
    return success(
        data=update_submission(
            submission_id=submission_id,
            actor_id=user["id"],
            fields=fields,
            conn=db,
        )
    )


@router.delete("/{submission_id}")
def delete_submission_endpoint(
    submission_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sub = get_submission(submission_id, db)
    _ensure_can_prepare(user, sub)
    return success(
        data=soft_delete_submission(submission_id=submission_id, actor_id=user["id"], conn=db)
    )


@router.post("/{submission_id}/samples")
def add_samples_endpoint(
    submission_id: int,
    request: Request,
    body: _SamplesBody,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sub = get_submission(submission_id, db)
    _ensure_can_prepare(user, sub)
    inserted = add_samples_to_submission(
        submission_id=submission_id,
        sample_ids=body.sample_ids,
        actor_id=user["id"],
        conn=db,
    )
    return success(data={"added": len(inserted), "rows": inserted})


@router.delete("/{submission_id}/samples")
def remove_samples_endpoint(
    submission_id: int,
    request: Request,
    body: _SamplesBody,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sub = get_submission(submission_id, db)
    _ensure_can_prepare(user, sub)
    removed = remove_samples_from_submission(
        submission_id=submission_id,
        sample_ids=body.sample_ids,
        actor_id=user["id"],
        conn=db,
    )
    return success(data={"removed": removed})


@router.post("/{submission_id}/validate")
def validate_endpoint(
    submission_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sub = get_submission(submission_id, db)
    # submission:prepare, not sample:read: the map groups validate with the
    # build routes because it answers "is this package ready to send", which
    # is a question only the person assembling it needs. A narrowing from the
    # read check that was here before.
    _ensure_can_prepare(user, sub)
    result = validate_submission_readiness(submission_id, db)
    return success(
        data={
            "valid": result.valid,
            "per_sample": [
                {"sample_id": v.sample_id, "issues": v.issues} for v in result.per_sample
            ],
        }
    )


@router.post("/{submission_id}/generate")
def generate_endpoint(
    submission_id: int,
    request: Request,
    body: _GenerateBody,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sub = get_submission(submission_id, db)
    _ensure_can_prepare(user, sub)
    path = generate_package(
        submission_id=submission_id,
        actor_id=user["id"],
        copy_files=body.copy_files,
        conn=db,
    )
    return success(data={"package_path": path})


@router.post("/{submission_id}/mark-submitted")
def mark_submitted_endpoint(
    submission_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sub = get_submission(submission_id, db)
    _ensure_can_approve(user, sub)
    return success(data=mark_submitted(submission_id=submission_id, actor_id=user["id"], conn=db))


@router.post("/{submission_id}/register-accessions")
async def register_accessions_endpoint(
    submission_id: int,
    request: Request,
    file: UploadFile | None = File(None),  # noqa: B008
    db=Depends(get_db_dep),  # noqa: B008
):
    """Accept either a TSV upload or a JSON body of accession entries."""
    user = get_current_user(request)
    sub = get_submission(submission_id, db)
    _ensure_can_approve(user, sub)

    entries: list[AccessionEntry]
    if file is not None and file.filename:
        text = (await file.read()).decode("utf-8")
        entries = parse_accessions_tsv(text)
    else:
        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid JSON body: {exc}") from exc
        if not isinstance(body, dict) or "accessions" not in body:
            return error(
                "VALIDATION_ERROR",
                "Provide an 'accessions' array or upload a TSV file.",
                status_code=422,
            )
        entries = [AccessionEntry(**e) for e in body["accessions"]]

    return success(
        data=register_accessions(
            submission_id=submission_id,
            accessions=entries,
            actor_id=user["id"],
            conn=db,
        )
    )


@router.post("/{submission_id}/mark-rejected")
def mark_rejected_endpoint(
    submission_id: int,
    request: Request,
    body: _RejectBody,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sub = get_submission(submission_id, db)
    _ensure_can_approve(user, sub)
    return success(
        data=mark_rejected(
            submission_id=submission_id,
            reason=body.reason,
            actor_id=user["id"],
            conn=db,
        )
    )


@router.post("/{submission_id}/withdraw")
def withdraw_endpoint(
    submission_id: int,
    request: Request,
    body: _WithdrawBody,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    sub = get_submission(submission_id, db)
    _ensure_can_approve(user, sub)
    return success(
        data=withdraw_submission(
            submission_id=submission_id,
            reason=body.reason,
            actor_id=user["id"],
            conn=db,
        )
    )


# ── I-3c: backend execution endpoints ─────────────────────────────


class _ExecuteBody(BaseModel):
    """Optional body for /execute. ``executor_backend`` is forward-compat
    for future executors; v1 only ships ``"seqsender_subprocess"``."""

    executor_backend: str | None = None


# Repo-name normalisation: the column ``target_repository`` stores
# ``NCBI`` / ``ENA`` / ``GISAID_*`` / ``DDBJ``; the C-1 settings list
# ``backend_submission_repos`` contains lowercase ``"ncbi"`` / ``"ena"``.
# This map normalises in one place so both halves agree.
_REPO_TO_SETTINGS_KEY: dict[str, str] = {
    "NCBI": "ncbi",
    "ENA": "ena",
    "GISAID_EPICOV": "gisaid",
    "GISAID_EPIFLU": "gisaid",
    "GISAID_EPIPOX": "gisaid",
    "DDBJ": "ddbj",
}

_SUPPORTED_BACKEND_REPOS: frozenset[str] = frozenset({"ncbi", "ena"})

_CREDENTIAL_KEYS_BY_REPO: dict[str, tuple[str, ...]] = {
    "ncbi": ("ncbi_submission_username", "ncbi_submission_password"),
    "ena": ("ena_webin_username", "ena_webin_password"),
}


def _check_credentials_for_repo(repo: str) -> None:
    """Raise HTTPException(400) if any credential required for the
    target repo is missing from the configured backend.

    Reads via the C-1 abstraction; CredentialNotFoundError becomes a 400
    naming the missing keys so the operator can fix env vars / the
    credential file / Secret Manager.
    """
    keys = _CREDENTIAL_KEYS_BY_REPO.get(repo, ())
    missing: list[str] = []
    for key in keys:
        try:
            credentials.get(key)
        except CredentialNotFoundError:
            missing.append(key)
    if missing:
        first_upper = missing[0].upper()
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "MISSING_CREDENTIALS",
                "message": (
                    f"Backend execution requires credentials for repo "
                    f"'{repo}'. Missing: {', '.join(missing)}. "
                    f"Configure via JACKPOT_CRED_{first_upper} (and the "
                    f"matching credential backend) before retrying."
                ),
                "missing_keys": missing,
            },
        )


def _enforce_execution_gates(
    sub: dict,
    *,
    allowed_statuses: frozenset[str],
) -> tuple[str, str]:
    """Run the shared pre-flight checks for /execute and /retry-execution.

    Returns ``(target_repo_raw, settings_repo_key)`` so the caller can
    forward both forms (uppercase column form for the SDK; lowercase
    for credential lookups) without re-deriving them.

    Raises HTTPException with the specific I-3c error codes:
      - BACKEND_EXECUTION_DISABLED (409)
      - REPO_NOT_ENABLED (409)
      - REPO_NOT_SUPPORTED (409)
      - INVALID_STATE (409)
      - MISSING_CREDENTIALS (400)
    """
    settings = get_settings()

    if not settings.allow_backend_submission:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "BACKEND_EXECUTION_DISABLED",
                "message": (
                    "Backend execution is disabled in this deployment. "
                    "Set allow_backend_submission=True and configure "
                    "backend_submission_repos to enable. See documentation."
                ),
            },
        )

    target_repo_raw = (sub.get("target_repository") or "").strip()
    settings_key = _REPO_TO_SETTINGS_KEY.get(target_repo_raw.upper(), "")
    enabled = list(settings.backend_submission_repos)

    if settings_key and settings_key not in enabled:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "REPO_NOT_ENABLED",
                "message": (
                    f"Backend execution for repo '{target_repo_raw}' is "
                    f"not enabled in this deployment. Configured repos: "
                    f"{enabled or '(none)'}."
                ),
            },
        )

    if not settings_key or settings_key not in _SUPPORTED_BACKEND_REPOS:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "REPO_NOT_SUPPORTED",
                "message": (
                    f"Backend execution is not supported for repo "
                    f"'{target_repo_raw}'. Supported in v1: ncbi, ena. "
                    f"Use the manual package workflow for this repo."
                ),
            },
        )

    status = sub.get("status")
    if status not in allowed_statuses:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "INVALID_STATE",
                "message": (
                    f"Cannot execute submission in status '{status}'. "
                    f"Submission must be in one of: "
                    f"{sorted(allowed_statuses)}."
                ),
            },
        )

    _check_credentials_for_repo(settings_key)
    return target_repo_raw, settings_key


def _schedule_execution_job(submission_id: int, attempt: int) -> None:
    """Hand the submission to the APScheduler instance for backend
    execution. ``attempt`` makes the job ID unique across retries.

    Imported lazily to avoid a circular import (``backend.main`` imports
    routers and routers would import the scheduler back from main).
    """
    from backend.jobs import execute_submission
    from backend.main import scheduler

    scheduler.add_job(
        execute_submission,
        args=[submission_id],
        id=f"execute_submission_{submission_id}_attempt_{attempt}",
        replace_existing=False,
    )


@router.post("/{submission_id}/execute", status_code=202)
def execute_endpoint(
    submission_id: int,
    request: Request,
    body: _ExecuteBody | None = None,
    db=Depends(get_db_dep),  # noqa: B008
):
    """Queue a generated submission for backend execution.

    Pre-flight gates (in order):
      1. Permission (existing RBAC).
      2. ``allow_backend_submission`` is True.
      3. Submission's repo is in ``backend_submission_repos``.
      4. Submission's repo is in v1's supported set (``ncbi``, ``ena``).
      5. Submission status is READY_TO_SUBMIT (the codebase's name for
         what the spec called GENERATED — the state set by
         ``mark_package_generated``).
      6. Required credentials are configured.

    On all gates passing: transition to EXECUTING via
    ``mark_execution_queued`` and queue the APScheduler job.
    """
    user = get_current_user(request)
    sub = get_submission(submission_id, db)
    _ensure_can_approve(user, sub)
    _enforce_execution_gates(sub, allowed_statuses=frozenset({"READY_TO_SUBMIT"}))

    executor_backend = (body.executor_backend if body else None) or "seqsender_subprocess"
    updated = mark_execution_queued(
        submission_id=submission_id,
        executor_backend=executor_backend,
        actor_id=user["id"],
        conn=db,
    )
    _schedule_execution_job(submission_id, attempt=updated["execution_attempt_count"])
    return success(data=updated, status_code=202)


@router.post("/{submission_id}/retry-execution", status_code=202)
def retry_execution_endpoint(
    submission_id: int,
    request: Request,
    body: _ExecuteBody | None = None,
    db=Depends(get_db_dep),  # noqa: B008
):
    """Re-queue a failed or interrupted submission for backend execution.

    Same gates as ``/execute`` except the status check accepts
    ``EXECUTION_FAILED`` and ``EXECUTION_INTERRUPTED``.
    """
    user = get_current_user(request)
    sub = get_submission(submission_id, db)
    _ensure_can_approve(user, sub)
    _enforce_execution_gates(
        sub,
        allowed_statuses=frozenset({"EXECUTION_FAILED", "EXECUTION_INTERRUPTED"}),
    )

    executor_backend = (body.executor_backend if body else None) or "seqsender_subprocess"
    updated = mark_execution_retried(
        submission_id=submission_id,
        executor_backend=executor_backend,
        actor_id=user["id"],
        conn=db,
    )
    _schedule_execution_job(submission_id, attempt=updated["execution_attempt_count"])
    return success(data=updated, status_code=202)


@router.get("/{submission_id}/execution-logs")
def execution_logs_endpoint(
    submission_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    """Return per-attempt execution-log entries for the submission.

    Each entry carries the canonical ``log_uri``, a presigned-or-equivalent
    ``log_view_url`` suitable for click-through, and best-effort
    timestamps drawn from audit events for the matching attempt. The
    audit lookups are best-effort because ``execute_submission`` emits
    them outside the request scope; if they're absent or hard to match,
    the corresponding fields are ``None`` rather than blocking the
    response.
    """
    user = get_current_user(request)
    sub = get_submission(submission_id, db)
    _ensure_can_read(user, sub)

    log_uris = sub.get("execution_log_uris") or []
    entries: list[dict] = []
    for index, raw_uri in enumerate(log_uris):
        attempt = index + 1
        entries.append(
            {
                "attempt": attempt,
                "log_uri": raw_uri,
                "log_view_url": _execution_log_view_url(raw_uri),
                "started_at": None,
                "completed_at": None,
                "exit_status": None,
            }
        )

    return success(
        data={
            "submission_id": submission_id,
            "entries": entries,
        }
    )


def _execution_log_view_url(uri: str) -> str:
    """Translate a stored log URI into a click-through URL.

    For cloud-backed URIs (``s3://`` / ``gs://``) we delegate to the
    storage abstraction's presigned-URL helper. For ``file://`` URIs
    (single-node deployments) we return the raw URI; the existing
    backend file-serving routes treat ``file://`` paths as
    backend-served already, and the operator-facing log viewer in the
    Streamlit page falls back to displaying the path with a hint when
    a presign isn't available.

    Wrapping presign generation in this helper keeps any future
    cloud-bucket changes localised — callers don't have to inspect
    schemes themselves.
    """
    from urllib.parse import urlparse

    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    if scheme in ("s3", "gs"):
        from backend.storage import generate_presigned_url

        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        try:
            return generate_presigned_url(bucket, key, ttl_seconds=3600)
        except Exception as exc:  # noqa: BLE001 — best-effort
            logger.warning(
                "execution-logs: presign failed for %s: %s; returning raw URI",
                uri,
                exc,
            )
    return uri
