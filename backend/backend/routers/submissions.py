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
    get_user_lab_membership,
)
from backend.database import get_db_dep
from backend.responses import error, success, success_list
from backend.submission_packages import generate_package
from backend.submissions import (
    AccessionEntry,
    add_samples_to_submission,
    create_submission,
    get_submission,
    list_submissions,
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


def _ensure_lab_access(user: dict, lab_id: int) -> None:
    if user.get("is_platform_admin"):
        return
    if not get_user_lab_membership(user["id"], lab_id):
        raise HTTPException(
            status_code=403,
            detail="Lab membership required to access this submission.",
        )


def _ensure_can_read(user: dict, submission: dict) -> None:
    _ensure_lab_access(user, submission["lab_id"])


def _ensure_can_write(user: dict, submission: dict) -> None:
    """Writes are allowed for the creator and for lab directors."""
    if user.get("is_platform_admin"):
        return
    if submission["created_by_user_id"] == user["id"]:
        return
    member = get_user_lab_membership(user["id"], submission["lab_id"])
    if member and member.get("is_lab_director"):
        return
    raise HTTPException(
        status_code=403,
        detail="Only the submission's creator or a lab director can modify it.",
    )


# ── endpoints ─────────────────────────────────────────────────────


@router.post("/", status_code=201)
def create_submission_endpoint(
    request: Request,
    body: _CreateBody,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    _ensure_lab_access(user, body.lab_id)
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
        _ensure_lab_access(user, lab_id)
    elif not user.get("is_platform_admin"):
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
    _ensure_can_write(user, sub)
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
    _ensure_can_write(user, sub)
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
    _ensure_can_write(user, sub)
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
    _ensure_can_write(user, sub)
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
    _ensure_can_read(user, sub)
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
    _ensure_can_write(user, sub)
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
    _ensure_can_write(user, sub)
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
    _ensure_can_write(user, sub)

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
    _ensure_can_write(user, sub)
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
    _ensure_can_write(user, sub)
    return success(
        data=withdraw_submission(
            submission_id=submission_id,
            reason=body.reason,
            actor_id=user["id"],
            conn=db,
        )
    )
