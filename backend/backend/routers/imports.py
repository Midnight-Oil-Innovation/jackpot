# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Import-session router for the I-1 spreadsheet importer wizard.

Six endpoints in total:

- POST   /api/v1/imports/sessions/         — create (multipart upload)
- GET    /api/v1/imports/sessions/         — list user's in-progress
- GET    /api/v1/imports/sessions/{id}     — fetch one
- PATCH  /api/v1/imports/sessions/{id}     — update with state invalidation
- POST   /api/v1/imports/sessions/{id}/import — execute import
- DELETE /api/v1/imports/sessions/{id}     — abandon

Per Critical Rule 24, every response uses the envelope helpers from
``backend/responses.py``. RBAC: each session is owned by exactly one
user; cross-user access returns 404 (not 403) so we don't leak the
existence of other users' sessions.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from backend.auth.guards import get_current_user, require_capability
from backend.database import get_db_dep
from backend.imports import (
    abandon_session,
    compute_diff,
    compute_preview,
    create_import_session,
    execute_import,
    get_session_for_user,
    list_user_sessions,
    parse_spreadsheet,
    update_import_session,
)
from backend.responses import success

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])
logger = logging.getLogger(__name__)


_VALID_FORMATS: frozenset[str] = frozenset({"xlsx", "csv", "tsv"})


class _PatchSessionBody(BaseModel):
    """Partial-update body for PATCH /sessions/{id}.

    Mirrors the patchable fields in :mod:`backend.imports`. Each field
    is optional; only those present in the request are updated.
    """

    selected_sheet: str | None = None
    column_mapping: dict | None = None
    value_mapping: dict | None = None
    file_reference_pattern: dict | None = None
    current_step: int | None = None


def _lab_guard(user: dict, lab_id: int, capability: str) -> None:
    """Confirm the caller may act on this lab (M2-B2).

    ``sample:create`` for every step that leads to writing samples,
    ``sample:read`` for the one that only reads a session. Narrower than the
    membership test it replaced — a Lab Reader is a member but holds no
    ``sample:create``, and staging an import is the first step of creating
    samples.

    Re-checked on each step rather than trusted from session-creation time:
    the owner filter in ``backend.imports`` answers "is this yours", not "may
    you still act on that lab", and membership can be revoked in between.
    """
    require_capability(capability)(user, lab_id=lab_id)


@router.post("/sessions/", status_code=201)
async def create_session(
    request: Request,
    lab_id: int = Form(...),
    file: UploadFile = File(...),  # noqa: B008
    db=Depends(get_db_dep),  # noqa: B008
):
    """Create a new wizard session and parse the uploaded file's metadata."""
    user = get_current_user(request)
    _lab_guard(user, lab_id, "sample:create")

    file_name = file.filename or "uploaded.xlsx"
    suffix = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
    if suffix not in _VALID_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=(f"Unsupported file extension {suffix!r}. Allowed: {sorted(_VALID_FORMATS)}."),
        )

    file_bytes = await file.read()
    session = create_import_session(
        user_id=user["id"],
        lab_id=lab_id,
        file_bytes=file_bytes,
        file_name=file_name,
        file_format=suffix,
        conn=db,
    )

    # Parse once at upload time so the wizard can render the sheet
    # picker without re-fetching bytes. Parse failures roll back the
    # row at request boundary via the FastAPI dep.
    try:
        meta = parse_spreadsheet(file_bytes, suffix)
    except HTTPException:
        # The session row exists; the user can retry by abandoning it.
        # Re-raise so the caller sees the parse error.
        raise

    payload = dict(session)
    payload["spreadsheet_meta"] = {
        "sheets": meta.sheets,
        "columns_by_sheet": meta.columns_by_sheet,
        "sample_values_by_sheet": meta.sample_values_by_sheet,
        "row_counts_by_sheet": meta.row_counts_by_sheet,
    }
    return success(data=payload, status_code=201)


@router.get("/sessions/")
def list_sessions(
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    return success(data=list_user_sessions(user["id"], db))


@router.get("/sessions/{session_id}")
def get_session(
    session_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    session = get_session_for_user(session_id, user["id"], db)
    _lab_guard(user, session["lab_id"], "sample:read")
    return success(data=session)


@router.patch("/sessions/{session_id}")
async def patch_session(
    session_id: int,
    request: Request,
    body: _PatchSessionBody,
    compute: str | None = Query(
        None,
        description=(
            "Optional post-update computation to run: 'preview' to refresh "
            "preview_results, 'diff' to refresh diff_results."
        ),
    ),
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    _lab_guard(user, get_session_for_user(session_id, user["id"], db)["lab_id"], "sample:create")
    fields = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    session = update_import_session(
        session_id=session_id,
        user_id=user["id"],
        fields=fields,
        conn=db,
    )
    if compute == "preview":
        compute_preview(session, db)
        session = get_session_for_user(session_id, user["id"], db)
    elif compute == "diff":
        compute_diff(session, db)
        session = get_session_for_user(session_id, user["id"], db)
    return success(data=session)


@router.post("/sessions/{session_id}/import")
def import_session(
    session_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    _lab_guard(user, get_session_for_user(session_id, user["id"], db)["lab_id"], "sample:create")
    return success(
        data=execute_import(session_id=session_id, user_id=user["id"], conn=db),
        status_code=201,
    )


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    _lab_guard(user, get_session_for_user(session_id, user["id"], db)["lab_id"], "sample:create")
    return success(data=abandon_session(session_id, user["id"], db))
