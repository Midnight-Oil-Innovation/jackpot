# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""sample_files-centric API surface for the P0f file_references model.

Phase P0f F-10. Hosts the read-side endpoints the Streamlit UI uses to
surface storage_state. F-9 will add the write-side ``promote`` endpoint
to this same router; F-10 keeps the surface focused on listing for now.

See ``spec.md`` Phase P0f Specification, Critical Rules 23 (pagination
via ``backend/pagination.py``), 24 (response envelopes via
``backend/responses.py``), 57 (no copy on ingest), 58 (sample_files is
the dedup primitive).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from backend.auth.guards import get_current_user
from backend.database import get_db_dep
from backend.pagination import paginate
from backend.permissions import visibility_sql_clause
from backend.responses import success_list

router = APIRouter(prefix="/api/v1/files", tags=["files"])


# Verification statuses written by ``verify_file_references`` (F-5).
# Listed here so the broken-files endpoint can validate the
# ``status_filter`` query parameter rather than passing arbitrary
# strings into the SQL.
_VERIFICATION_STATUSES: frozenset[str] = frozenset(
    {
        "MISSING",
        "MISSING_2",
        "MISSING_3",
        "READ_ERROR",
        "READ_ERROR_2",
        "READ_ERROR_3",
        "SIZE_CHANGED",
    }
)


def _serialise(row: dict) -> dict:
    out = dict(row)
    for k, v in out.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
    return out


@router.get("/broken")
def list_broken_files(
    request: Request,
    project_id: int | None = None,
    lab_id: int | None = None,
    status_filter: str | None = None,
    page: int = 1,
    per_page: int = Query(50, ge=1, le=500),
    sort_by: str = "last_verified_at",
    sort_dir: str = "desc",
    db=Depends(get_db_dep),  # noqa: B008
):
    """List ``sample_files`` rows in the ``BROKEN`` storage state.

    Phase P0f F-10. Powers the broken-files admin page. Lab access
    scoping uses the same ``visibility_sql_clause`` ladder as the
    samples list endpoint, so the user only sees broken files for
    samples they could otherwise see in /samples/.
    """
    user = get_current_user(request)

    vis_clause, vis_params = visibility_sql_clause(user)
    where: list[str] = [
        "sf.is_deleted = FALSE",
        "sf.storage_state = 'BROKEN'",
        "s.is_deleted = FALSE",
        vis_clause,
    ]
    params: dict = dict(vis_params)

    if project_id is not None:
        where.append("s.project_id = :project_id")
        params["project_id"] = project_id
    if lab_id is not None:
        where.append("s.lab_id = :lab_id")
        params["lab_id"] = lab_id
    if status_filter is not None:
        if status_filter not in _VERIFICATION_STATUSES:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid status_filter {status_filter!r}; must be one of "
                    f"{sorted(_VERIFICATION_STATUSES)}."
                ),
            )
        where.append("sf.last_verification_status = :status_filter")
        params["status_filter"] = status_filter

    where_sql = " AND ".join(where)
    base_query = f"""
        SELECT
            sf.id AS sample_files_id,
            sf.uri,
            sf.filename,
            sf.file_size_bytes,
            sf.last_verification_status,
            sf.last_verified_at,
            sf.first_seen_at,
            sf.storage_state,
            s.id AS sample_id_int,
            s.sample_id,
            s.lab_id,
            s.project_id
          FROM sample_files sf
          JOIN samples s ON s.id = sf.sample_id_fk
         WHERE {where_sql}
    """
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
