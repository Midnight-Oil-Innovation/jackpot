# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Persistent column-mapping templates for the I-1 importer wizard.

Where ``import_sessions`` is short-lived per-import state, an
``import_mappings`` row is a long-lived reusable template. The wizard
offers to save the user's column_mapping + file_reference_pattern at
the end of a successful import; the saved row can be picked up by a
future import (web or CLI) instead of redoing the mapping work.

Standard CRUD per Critical Rule 24's envelope conventions. Lab-scoped
visibility: a user sees mappings for any lab they're a member of (plus
all labs if Platform Admin).
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from backend.auth.guards import get_current_user, require_capability
from backend.authz.principal import load_principal
from backend.authz.visibility import lab_list_clause
from backend.database import execute_query, execute_write, get_db_dep
from backend.responses import error, success, success_list

router = APIRouter(prefix="/api/v1/import_mappings", tags=["import_mappings"])
logger = logging.getLogger(__name__)


class _CreateBody(BaseModel):
    lab_id: int
    display_name: str
    description: str | None = None
    column_mapping: dict
    file_reference_pattern: dict | None = None


class _PatchBody(BaseModel):
    display_name: str | None = None
    description: str | None = None
    column_mapping: dict | None = None
    file_reference_pattern: dict | None = None
    is_active: bool | None = None


def _ensure_lab_access(user: dict, lab_id: int, capability: str) -> None:
    """M2-B4: the mapping's lab, and the verb the route needs.

    ``import:read`` for the two reads, ``import:manage`` for the three writes.
    The split is the whole reason those verbs are separate in §4.5; the
    membership test this replaces could not express it, so a Lab Reader who
    could see a mapping could also rewrite it.

    The platform-admin branch is gone: an instance-scoped grant contains every
    lab path (ADR 0015), so the admin passes on the same rung as everyone else.
    """
    require_capability(capability)(user, lab_id=lab_id)


def _serialise(row: dict) -> dict:
    out = dict(row)
    for k, v in out.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
    return out


@router.get("/")
def list_mappings(
    request: Request,
    lab_id: int | None = None,
    is_active: bool | None = None,
    page: int = 1,
    per_page: int = Query(50, ge=1, le=500),
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    # M2-B4: the same list filter the sample-plane lists use (M2-B7), at lab
    # level. Replaces both a platform-admin bypass and a hand-rolled
    # "labs I am a member of" subquery — an instance-scoped grant contains
    # every lab path, so the first is unnecessary, and the second could not
    # see an org-scoped grant at all.
    vis, params = lab_list_clause(load_principal(user["id"]), "import:read")
    where = [vis]
    if lab_id is not None:
        where.append("im.lab_id = :lab_id")
        params["lab_id"] = lab_id
    if is_active is not None:
        where.append("im.is_active = :is_active")
        params["is_active"] = is_active

    offset = (page - 1) * per_page
    rows = execute_query(
        f"""
        SELECT im.* FROM import_mappings im
          JOIN labs l ON l.id = im.lab_id
         WHERE {" AND ".join(where)}
         ORDER BY im.updated_at DESC
         LIMIT :_limit OFFSET :_offset
        """,
        {**params, "_limit": per_page, "_offset": offset},
        conn=db,
    )
    count_rows = execute_query(
        "SELECT COUNT(*) AS total FROM import_mappings im "
        "JOIN labs l ON l.id = im.lab_id "
        f"WHERE {' AND '.join(where)}",
        params,
        conn=db,
    )
    total = count_rows[0]["total"] if count_rows else 0
    return success_list(
        data=[_serialise(r) for r in rows],
        page=page,
        per_page=per_page,
        total=total,
    )


@router.get("/{mapping_id}")
def get_mapping(
    mapping_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    rows = execute_query(
        "SELECT * FROM import_mappings WHERE id = :id LIMIT 1",
        {"id": mapping_id},
        conn=db,
    )
    if not rows:
        return error("NOT_FOUND", f"Mapping {mapping_id} not found.", status_code=404)
    row = rows[0]
    _ensure_lab_access(user, row["lab_id"], "import:read")
    return success(data=_serialise(row))


@router.post("/", status_code=201)
def create_mapping(
    request: Request,
    body: _CreateBody,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    _ensure_lab_access(user, body.lab_id, "import:manage")
    rows = execute_write(
        """
        INSERT INTO import_mappings (
            lab_id, display_name, description,
            column_mapping, file_reference_pattern, created_by_user_id
        ) VALUES (
            :lab, :name, :desc,
            CAST(:cm AS JSONB), CAST(:fr AS JSONB), :uid
        )
        RETURNING *
        """,
        {
            "lab": body.lab_id,
            "name": body.display_name,
            "desc": body.description,
            "cm": json.dumps(body.column_mapping),
            "fr": json.dumps(body.file_reference_pattern or {}),
            "uid": user["id"],
        },
        conn=db,
    )
    return success(data=_serialise(rows[0]), status_code=201)


@router.patch("/{mapping_id}")
def patch_mapping(
    mapping_id: int,
    request: Request,
    body: _PatchBody,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    rows = execute_query(
        "SELECT * FROM import_mappings WHERE id = :id LIMIT 1",
        {"id": mapping_id},
        conn=db,
    )
    if not rows:
        return error("NOT_FOUND", f"Mapping {mapping_id} not found.", status_code=404)
    _ensure_lab_access(user, rows[0]["lab_id"], "import:manage")

    fields = body.model_dump(exclude_none=True)
    if not fields:
        return success(data=_serialise(rows[0]))

    sets: list[str] = []
    params: dict = {"id": mapping_id, "_lab": rows[0]["lab_id"]}
    for k, v in fields.items():
        if k in ("column_mapping", "file_reference_pattern"):
            sets.append(f"{k} = CAST(:{k} AS JSONB)")
            params[k] = json.dumps(v)
        else:
            sets.append(f"{k} = :{k}")
            params[k] = v

    # Scope the write to the lab we authorized against, so a concurrent
    # reassignment between the SELECT and UPDATE can't let this patch land
    # on a mapping the caller no longer has access to.
    updated = execute_write(
        f"UPDATE import_mappings SET {', '.join(sets)} "
        "WHERE id = :id AND lab_id = :_lab RETURNING *",
        params,
        conn=db,
    )
    if not updated:
        return error(
            "CONFLICT",
            f"Mapping {mapping_id} changed concurrently; retry.",
            status_code=409,
        )
    return success(data=_serialise(updated[0]))


@router.delete("/{mapping_id}")
def delete_mapping(
    mapping_id: int,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    """Soft-delete: flips ``is_active`` to FALSE."""
    user = get_current_user(request)
    rows = execute_query(
        "SELECT * FROM import_mappings WHERE id = :id LIMIT 1",
        {"id": mapping_id},
        conn=db,
    )
    if not rows:
        return error("NOT_FOUND", f"Mapping {mapping_id} not found.", status_code=404)
    _ensure_lab_access(user, rows[0]["lab_id"], "import:manage")
    execute_write(
        "UPDATE import_mappings SET is_active = FALSE WHERE id = :id AND lab_id = :_lab",
        {"id": mapping_id, "_lab": rows[0]["lab_id"]},
        conn=db,
    )
    return success(data={"id": mapping_id, "is_active": False})
