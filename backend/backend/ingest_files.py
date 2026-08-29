# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Shared file registration logic for all ingest paths.

Phase P0f F-6. Used by ``/api/v1/ingest/upload``, ``/csv``, ``/globus``,
and the new ``/register`` endpoint. Centralizes cheap fingerprint +
dedup + ``sample_files`` row creation so all four ingest paths have
identical behaviour.

See ``spec.md`` Phase P0f Specification, Critical Rules 57 (no copy on
ingest, default ``EXTERNAL``) and 58 (``sample_files`` is the dedup
primitive — content hash, not URI, is the logical key).
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from backend.database import execute_query, execute_write
from backend.file_detector import get_file_type
from backend.file_fingerprint import cheap_fingerprint

# User-facing storage intents accepted at registration time.
# ``STAGED`` and ``BROKEN`` are internal lifecycle states managed by
# the verification job and pipeline staging — they are never a valid
# *intent* a caller can request.
VALID_STORAGE_INTENTS: frozenset[str] = frozenset({"EXTERNAL", "MANAGED", "MIRRORED"})

# read_direction values accepted on sample_files via register_file.
VALID_ROLES: frozenset[str] = frozenset({"R1", "R2", "LONG_READ", "ASSEMBLY", "OTHER"})


def _filename_from_uri(uri: str) -> str:
    parsed = urlparse(uri)
    path = parsed.path if parsed.scheme else uri
    name = os.path.basename(path) or uri
    return name


def register_file(
    uri: str,
    storage_intent: str,
    sample_id_fk: int,
    role: str,
    *,
    conn,
    ingest_method: str = "register",
    precomputed_fingerprint: tuple[int, str, str] | None = None,
    library_layout: str | None = None,
    lane: str | None = None,
    chunk_index: int | None = None,
) -> tuple[int, bool]:
    """Register a file by URI. Returns ``(sample_files_id, was_dedup)``.

    Computes the cheap fingerprint (or accepts a precomputed one when
    the caller already has the bytes in hand — e.g. ``/upload``), checks
    for an existing ``sample_files`` row with matching
    ``(file_size_bytes, head64k_hash, tail64k_hash)``, and either:

    - Reuses the existing row, appending ``uri`` to ``alternate_uris``
      if not already present (returns its id with ``was_dedup=True``).
    - Inserts a new ``sample_files`` row with the requested
      ``storage_state`` (returns the new id with ``was_dedup=False``).

    Per Critical Rule 58 this is the dedup primitive. Per Critical Rule
    57 the caller is responsible for choosing ``storage_intent`` —
    ``EXTERNAL`` is the system-wide default for new ingest paths.

    Raises:
        ValueError: ``storage_intent`` not in :data:`VALID_STORAGE_INTENTS`
            or ``role`` not in :data:`VALID_ROLES`.
        FileNotFoundError, PermissionError, OSError: URI unreachable
            (caller surfaces ``FILE_UNREACHABLE``).
    """
    if storage_intent not in VALID_STORAGE_INTENTS:
        raise ValueError(
            f"Invalid storage_intent {storage_intent!r}; "
            f"must be one of {sorted(VALID_STORAGE_INTENTS)}."
        )
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role {role!r}; must be one of {sorted(VALID_ROLES)}.")

    if precomputed_fingerprint is not None:
        size_bytes, head_hash, tail_hash = precomputed_fingerprint
    else:
        size_bytes, head_hash, tail_hash = cheap_fingerprint(uri)

    # TODO(P0c): when multi-tenancy lands, scope this lookup to the
    # caller's tenant.
    existing = execute_query(
        """
        SELECT id, uri, alternate_uris
          FROM sample_files
         WHERE file_size_bytes = :sz
           AND head64k_hash = :hh
           AND tail64k_hash = :th
           AND is_archived = FALSE
         ORDER BY id ASC
         LIMIT 1
        """,
        {"sz": size_bytes, "hh": head_hash, "th": tail_hash},
        conn=conn,
    )

    if existing:
        row = existing[0]
        existing_id = row["id"]
        existing_primary = row["uri"]
        existing_alts = row["alternate_uris"] or []
        if uri != existing_primary and uri not in existing_alts:
            execute_write(
                """
                UPDATE sample_files
                   SET alternate_uris = array_append(alternate_uris, :u)
                 WHERE id = :id
                """,
                {"u": uri, "id": existing_id},
                conn=conn,
            )
        return (existing_id, True)

    # New file: insert. file-type detection delegated to file_detector
    # per Critical Rule 20 — never reimplement extension parsing here.
    filename = _filename_from_uri(uri)
    file_type = get_file_type(filename)

    if library_layout is None:
        library_layout = "PAIRED" if role in ("R1", "R2") else "UNPAIRED"

    rows = execute_write(
        """
        INSERT INTO sample_files (
            sample_id_fk, uri, filename,
            file_size_bytes, head64k_hash, tail64k_hash,
            file_type, library_layout, read_direction,
            lane, chunk_index,
            storage_state, first_seen_at,
            scrub_status, pii_scan_status, ingest_method
        ) VALUES (
            :sid, :uri, :fn,
            :sz, :hh, :th,
            :ft, :ll, :rd,
            :ln, :ci,
            CAST(:ss AS file_storage_state), NOW(),
            'PENDING', 'PENDING', :im
        )
        RETURNING id
        """,
        {
            "sid": sample_id_fk,
            "uri": uri,
            "fn": filename,
            "sz": size_bytes,
            "hh": head_hash,
            "th": tail_hash,
            "ft": file_type,
            "ll": library_layout,
            "rd": role,
            "ln": lane,
            "ci": chunk_index,
            "ss": storage_intent,
            "im": ingest_method,
        },
        conn=conn,
    )
    return (rows[0]["id"], False)


__all__ = [
    "VALID_ROLES",
    "VALID_STORAGE_INTENTS",
    "register_file",
]
