# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Business logic for the I-1 spreadsheet importer wizard.

The router layer (``backend/routers/imports.py``) is a thin shell over
this module. Every wizard step is a function here so the CLI's
``jackpot import run`` can drive the same logic non-interactively
without going through HTTP.

See ``spec.md`` Phase P0f Specification (file_references model) and
``docs/CLAUDE.md`` Critical Rules 22 (lab_id from the start), 24
(response envelopes), 57 (no copy on ingest, default EXTERNAL), 58
(sample_files is the dedup primitive).
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import UTC
from typing import Any

from fastapi import HTTPException

from backend.config import get_settings
from backend.database import execute_query, execute_write

# Wizard step indexes are kept here as constants so the router and
# tests can refer to them without magic numbers.
STEP_UPLOAD = 1
STEP_SHEET_PICKER = 2
STEP_COLUMN_MAPPING = 3
STEP_VALUE_MAPPING = 4
STEP_FILE_REFERENCE = 5
STEP_PREVIEW = 6
STEP_DIFF = 7
STEP_IMPORT = 8

# State-invalidation rule. When a field at index N is updated, fields
# whose entries are >= N have their cached results cleared and
# current_step is reset to N. The frontend doesn't have to remember
# this dependency graph; the backend enforces it.
_FIELD_TO_STEP: dict[str, int] = {
    "selected_sheet": STEP_SHEET_PICKER,
    "column_mapping": STEP_COLUMN_MAPPING,
    "value_mapping": STEP_VALUE_MAPPING,
    "file_reference_pattern": STEP_FILE_REFERENCE,
}
_DOWNSTREAM_CACHED_FIELDS = ("preview_results", "diff_results")

# Hard cap per design notes. v1 imports the first 10,000 rows and
# surfaces a warning above that.
MAX_ROWS_PER_IMPORT: int = 10_000


@dataclass(frozen=True)
class SpreadsheetMeta:
    """Lightweight description of an uploaded spreadsheet.

    Returned by :func:`parse_spreadsheet` and embedded in the import
    session at upload time so the wizard can render the sheet picker
    (step 2) and column mapping (step 3) without re-parsing the bytes
    on every page render.
    """

    sheets: list[str]
    columns_by_sheet: dict[str, list[str]]
    sample_values_by_sheet: dict[str, dict[str, list[str]]]
    row_counts_by_sheet: dict[str, int]


# ── parse_spreadsheet ──────────────────────────────────────────────


def parse_spreadsheet(file_bytes: bytes, file_format: str) -> SpreadsheetMeta:
    """Parse an uploaded spreadsheet's metadata without persisting anything.

    Returns the list of sheets (always ``["__single__"]`` for csv/tsv),
    the column names for each sheet, and up to 5 sample values per
    column to seed the wizard's value-normalization step.

    Raises:
        HTTPException(400): the file is empty, malformed, or contains
            no data rows.
    """
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File is empty.")

    fmt = file_format.lower()
    if fmt == "xlsx":
        return _parse_xlsx(file_bytes)
    if fmt in ("csv", "tsv"):
        return _parse_csv_like(file_bytes, delimiter="," if fmt == "csv" else "\t")
    raise HTTPException(status_code=400, detail=f"Unsupported file_format: {file_format!r}")


def _parse_xlsx_sheet(ws: Any) -> tuple[list[str], dict[str, list[str]], int]:
    """Extract header columns, up-to-5 sample values per column, and row count."""
    rows = ws.iter_rows(values_only=True)
    try:
        header = next(rows)
    except StopIteration:
        return [], {}, 0

    cols = [str(c) if c is not None else "" for c in header]
    cols = [c for c in cols if c]  # drop trailing empty header cells
    samples: dict[str, list[str]] = {c: [] for c in cols}
    count = 0
    for row in rows:
        if row is None or all(c is None for c in row):
            continue
        for idx, val in enumerate(row):
            if idx >= len(cols):
                break
            if val is None:
                continue
            col = cols[idx]
            if len(samples[col]) < 5 and str(val) not in samples[col]:
                samples[col].append(str(val))
        count += 1
    return cols, samples, count


def _parse_xlsx(file_bytes: bytes) -> SpreadsheetMeta:
    # openpyxl is heavy; import lazily so the module-level import
    # cost stays predictable for callers that don't actually parse.
    from openpyxl import load_workbook  # noqa: PLC0415

    try:
        wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse xlsx: {exc}") from exc

    # read_only workbooks keep the underlying zip/file open until closed;
    # close in a finally so repeated parses don't leak file descriptors.
    try:
        sheets = wb.sheetnames
        if not sheets:
            raise HTTPException(status_code=400, detail="Workbook has no sheets.")

        columns_by_sheet: dict[str, list[str]] = {}
        sample_values_by_sheet: dict[str, dict[str, list[str]]] = {}
        row_counts_by_sheet: dict[str, int] = {}

        for name in sheets:
            cols, samples, count = _parse_xlsx_sheet(wb[name])
            columns_by_sheet[name] = cols
            sample_values_by_sheet[name] = samples
            row_counts_by_sheet[name] = count

        return SpreadsheetMeta(
            sheets=sheets,
            columns_by_sheet=columns_by_sheet,
            sample_values_by_sheet=sample_values_by_sheet,
            row_counts_by_sheet=row_counts_by_sheet,
        )
    finally:
        wb.close()


def _collect_csv_samples(
    reader: csv.DictReader, cols: list[str]
) -> tuple[dict[str, list[str]], int]:
    """Collect up-to-5 sample values per column and the total row count."""
    samples: dict[str, list[str]] = {c: [] for c in cols}
    count = 0
    for row in reader:
        for c in cols:
            v = row.get(c)
            if v and len(samples[c]) < 5 and v not in samples[c]:
                samples[c].append(v)
        count += 1
    return samples, count


def _parse_csv_like(file_bytes: bytes, delimiter: str) -> SpreadsheetMeta:
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"File must be UTF-8 encoded: {exc}") from exc

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    cols = [c for c in (reader.fieldnames or []) if c]
    if not cols:
        raise HTTPException(status_code=400, detail="No header row detected.")

    samples, count = _collect_csv_samples(reader, cols)

    sentinel = "__single__"
    return SpreadsheetMeta(
        sheets=[sentinel],
        columns_by_sheet={sentinel: cols},
        sample_values_by_sheet={sentinel: samples},
        row_counts_by_sheet={sentinel: count},
    )


# ── session lifecycle ──────────────────────────────────────────────


def create_import_session(
    *,
    user_id: int,
    lab_id: int,
    file_bytes: bytes,
    file_name: str,
    file_format: str,
    conn,
) -> dict:
    """Create a new wizard session and persist the uploaded file bytes.

    Per design notes the file content lives in a ``BYTEA`` column
    (capped at 10 MB by the migration's CHECK constraint and
    re-checked here to surface a clean 400 instead of a database
    integrity error).

    Enforces the per-user concurrent-session cap so an abandoned
    upload doesn't sit in the queue forever — the user must finish or
    abandon an existing session before starting a new one.
    """
    settings = get_settings()
    cap = (settings.import_session_max_file_size_mb or 10) * 1024 * 1024
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="File is empty.")
    if len(file_bytes) > cap:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum {settings.import_session_max_file_size_mb} MB.",
        )

    fmt = file_format.lower()
    if fmt not in ("xlsx", "csv", "tsv"):
        raise HTTPException(status_code=400, detail=f"Unsupported file_format: {file_format!r}")

    # Per-user limit on concurrent in-progress sessions.
    existing = execute_query(
        """
        SELECT id, file_name, current_step, created_at, expires_at
          FROM import_sessions
         WHERE created_by_user_id = :uid
           AND status = 'in_progress'
           AND expires_at > NOW()
         ORDER BY created_at DESC
        """,
        {"uid": user_id},
        conn=conn,
    )
    max_per_user = settings.import_session_max_per_user or 5
    if len(existing) >= max_per_user:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    f"You already have {len(existing)} in-progress import "
                    f"sessions (limit {max_per_user}). Abandon or finish one "
                    "before starting another."
                ),
                "existing": [_serialise(r) for r in existing],
            },
        )

    rows = execute_write(
        """
        INSERT INTO import_sessions (
            created_by_user_id, lab_id, file_name, file_format,
            file_bytes, file_size_bytes, current_step, status
        ) VALUES (
            :uid, :lab, :fn, :fmt,
            :bytes, :sz, :step, 'in_progress'
        ) RETURNING id, created_by_user_id, lab_id, file_name, file_format,
                   file_size_bytes, selected_sheet, column_mapping,
                   value_mapping, file_reference_pattern, preview_results,
                   diff_results, current_step, status, created_at,
                   updated_at, expires_at
        """,
        {
            "uid": user_id,
            "lab": lab_id,
            "fn": file_name,
            "fmt": fmt,
            "bytes": file_bytes,
            "sz": len(file_bytes),
            "step": STEP_UPLOAD,
        },
        conn=conn,
    )
    return _serialise(rows[0])


def list_user_sessions(user_id: int, conn) -> list[dict]:
    """The caller's in-progress sessions, in labs they may still read.

    M2-B7 adds the second half. Ownership alone was the whole filter, which
    kept listing a session after the user lost access to its lab — the same
    gap the per-step guard closes for the routes that act on one. Rows live at
    lab level and carry no sample, so the filter is ``lab_list_clause``.
    """
    from backend.authz.principal import load_principal
    from backend.authz.visibility import lab_list_clause

    vis, params = lab_list_clause(load_principal(user_id), "sample:read")
    rows = execute_query(
        f"""
        SELECT ims.id, ims.file_name, ims.file_format, ims.lab_id,
               ims.current_step, ims.status,
               ims.created_at, ims.updated_at, ims.expires_at
          FROM import_sessions ims
          JOIN labs l ON l.id = ims.lab_id
         WHERE ims.created_by_user_id = :uid
           AND ims.status = 'in_progress'
           AND ims.expires_at > NOW()
           AND {vis}
         ORDER BY ims.created_at DESC
        """,  # noqa: S608 — vis is compiled by the authz layer, not interpolated input
        {**params, "uid": user_id},
        conn=conn,
    )
    return [_serialise(r) for r in rows]


def get_session_for_user(session_id: int, user_id: int, conn) -> dict:
    """Fetch a session, enforcing RBAC + TTL.

    Raises:
        HTTPException(404): session does not exist or belongs to a
            different user. We use 404 rather than 403 for cross-user
            access so the response doesn't leak the existence of other
            users' sessions.
        HTTPException(410): session belongs to the caller but has
            expired. The caller is told explicitly so the UI can
            offer to start a new import.
    """
    rows = execute_query(
        """
        SELECT id, created_by_user_id, lab_id, file_name, file_format,
               file_size_bytes, selected_sheet, column_mapping,
               value_mapping, file_reference_pattern, preview_results,
               diff_results, current_step, status, created_at,
               updated_at, expires_at
          FROM import_sessions
         WHERE id = :id
        """,
        {"id": session_id},
        conn=conn,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Session not found.")
    row = rows[0]
    if row["created_by_user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Session not found.")
    # Compare in Python — execute_query already returned the row.
    expires_at = row["expires_at"]
    from datetime import datetime  # noqa: PLC0415

    now = datetime.now(UTC)
    if expires_at and expires_at < now:
        raise HTTPException(
            status_code=410, detail="Session has expired. Please start a new import."
        )
    return _serialise(row)


_PATCHABLE_FIELDS: frozenset[str] = frozenset(
    {
        "selected_sheet",
        "column_mapping",
        "value_mapping",
        "file_reference_pattern",
        "current_step",
    }
)


def _build_patch_updates(
    session_id: int, fields: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    """Build the SQL ``SET`` clauses + bound params for a patch.

    ``key`` is always drawn from ``fields``, which ``update_import_session``
    has already validated against ``_PATCHABLE_FIELDS`` before this is
    called — the interpolated column names are never user-supplied text.
    """
    sets: list[str] = []
    params: dict[str, Any] = {"id": session_id}
    for key, value in fields.items():
        if key == "current_step":
            sets.append("current_step = :current_step")
            params["current_step"] = int(value)
            continue
        if key in ("column_mapping", "value_mapping", "file_reference_pattern"):
            sets.append(f"{key} = CAST(:{key} AS JSONB)")
            params[key] = json.dumps(value) if value is not None else None
            continue
        sets.append(f"{key} = :{key}")
        params[key] = value
    return sets, params


def _apply_invalidation_rules(
    sets: list[str], params: dict[str, Any], fields: dict[str, Any]
) -> None:
    """Append downstream-cache-clear + step-rewind clauses, mutating in place.

    Compute the earliest wizard step affected by this patch and, if any,
    clear the cached results from later steps and rewind ``current_step``
    unless the caller explicitly bumped it past the changed step already.
    """
    affected_steps = [_FIELD_TO_STEP[k] for k in fields if k in _FIELD_TO_STEP]
    earliest = min(affected_steps) if affected_steps else None
    if earliest is None:
        return

    for cached in _DOWNSTREAM_CACHED_FIELDS:
        sets.append(f"{cached} = NULL")
    explicit_step = fields.get("current_step")
    if explicit_step is None or explicit_step < earliest:
        sets.append("current_step = :_invalidation_step")
        params["_invalidation_step"] = earliest


def update_import_session(
    *,
    session_id: int,
    user_id: int,
    fields: dict[str, Any],
    conn,
) -> dict:
    """Apply a partial update to a session, enforcing state invalidation.

    When an earlier-step field changes, the cached results from later
    steps are cleared and ``current_step`` is rewound to the changed
    step. The frontend doesn't have to track this dependency graph.
    """
    # Validate and load.
    session = get_session_for_user(session_id, user_id, conn)

    bad_fields = sorted(k for k in fields if k not in _PATCHABLE_FIELDS)
    if bad_fields:
        raise HTTPException(status_code=422, detail=f"Cannot patch fields: {bad_fields}")
    if not fields:
        return session

    sets, params = _build_patch_updates(session_id, fields)
    _apply_invalidation_rules(sets, params, fields)

    rows = execute_write(
        f"""
        UPDATE import_sessions
           SET {", ".join(sets)}
         WHERE id = :id
         RETURNING id, created_by_user_id, lab_id, file_name, file_format,
                   file_size_bytes, selected_sheet, column_mapping,
                   value_mapping, file_reference_pattern, preview_results,
                   diff_results, current_step, status, created_at,
                   updated_at, expires_at
        """,
        params,
        conn=conn,
    )
    return _serialise(rows[0])


def abandon_session(session_id: int, user_id: int, conn) -> dict:
    """Mark a session ``abandoned``. The cleanup job removes the row later."""
    # RBAC + existence check.
    get_session_for_user(session_id, user_id, conn)
    rows = execute_write(
        """
        UPDATE import_sessions
           SET status = 'abandoned'
         WHERE id = :id
         RETURNING id, status
        """,
        {"id": session_id},
        conn=conn,
    )
    return _serialise(rows[0])


# ── preview / diff / convert / execute ──────────────────────────────


def _row_iter_from_xlsx(
    file_bytes: bytes, selected_sheet: str | None
) -> tuple[list[str], list[dict[str, str]]]:
    from openpyxl import load_workbook  # noqa: PLC0415

    wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    # read_only workbooks hold the underlying file open; close in a
    # finally so repeated wizard steps don't leak file descriptors.
    try:
        sheet_name = selected_sheet or wb.sheetnames[0]
        ws = wb[sheet_name]
        iter_rows = ws.iter_rows(values_only=True)
        try:
            header = next(iter_rows)
        except StopIteration:
            return [], []
        cols = [str(c) if c is not None else "" for c in header]
        cols = [c for c in cols if c]
        rows_out: list[dict[str, str]] = []
        for raw in iter_rows:
            if raw is None or all(c is None for c in raw):
                continue
            entry: dict[str, str] = {}
            for idx, c in enumerate(cols):
                if idx < len(raw) and raw[idx] is not None:
                    entry[c] = str(raw[idx])
                else:
                    entry[c] = ""
            rows_out.append(entry)
            if len(rows_out) >= MAX_ROWS_PER_IMPORT:
                break
        return cols, rows_out
    finally:
        wb.close()


def _row_iter_from_csv_like(
    file_bytes: bytes, delimiter: str
) -> tuple[list[str], list[dict[str, str]]]:
    text = file_bytes.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    cols = [c for c in (reader.fieldnames or []) if c]
    rows_out: list[dict[str, str]] = []
    for raw in reader:
        rows_out.append({c: (raw.get(c) or "") for c in cols})
        if len(rows_out) >= MAX_ROWS_PER_IMPORT:
            break
    return cols, rows_out


def _row_iter_from_session(session: dict, conn) -> tuple[list[str], list[dict[str, str]]]:
    """Yield the user's spreadsheet rows back out of the session.

    Re-parses the stored bytes; the wizard only kept the file once at
    upload. Honors the ``selected_sheet`` field for multi-sheet xlsx
    workbooks.
    """
    rows = execute_query(
        "SELECT file_bytes, file_format, selected_sheet FROM import_sessions WHERE id = :id",
        {"id": session["id"]},
        conn=conn,
    )
    blob = rows[0]
    file_bytes = bytes(blob["file_bytes"])
    fmt = blob["file_format"].lower()

    if fmt == "xlsx":
        return _row_iter_from_xlsx(file_bytes, blob["selected_sheet"])

    delimiter = "," if fmt == "csv" else "\t"
    return _row_iter_from_csv_like(file_bytes, delimiter)


def _apply_row_mappings(
    raw_row: dict[str, str],
    column_mapping: dict[str, str],
    value_mapping: dict[str, dict[str, str]] | None,
) -> dict[str, str]:
    """Translate a single source row into JACKPOT field names + values."""
    out: dict[str, str] = {}
    for src_col, raw_val in raw_row.items():
        target = column_mapping.get(src_col)
        if not target:
            continue
        v = raw_val
        if value_mapping and target in value_mapping:
            v = value_mapping[target].get(raw_val, raw_val)
        out[target] = v
    return out


def _files_from_path_columns(raw_row: dict[str, str], cfg: dict[str, Any]) -> str:
    parts = []
    for col in (cfg.get("r1_column"), cfg.get("r2_column")):
        if col and raw_row.get(col):
            parts.append(raw_row[col])
    for extra in cfg.get("extra_columns") or []:
        if raw_row.get(extra):
            parts.append(raw_row[extra])
    return ";".join(parts)


def _files_from_filename_convention(raw_row: dict[str, str], cfg: dict[str, Any]) -> str:
    sample_id = raw_row.get(cfg.get("sample_id_column", "sample_id"), "")
    template = cfg.get("template") or "{sample_id}_R1.fastq.gz"
    # Naive substitution; the template is operator-supplied so a
    # full-fledged template engine isn't worth the dependency.
    return template.replace("{sample_id}", sample_id)


def _files_column_for_row(
    raw_row: dict[str, str],
    pattern: dict[str, Any] | None,
) -> str:
    """Build the semicolon-delimited ``files`` column the CSV ingest expects."""
    if not pattern:
        return ""
    ptype = pattern.get("type")
    cfg = pattern.get("config", {}) or {}
    if ptype == "path_columns":
        return _files_from_path_columns(raw_row, cfg)
    if ptype == "filename_convention":
        return _files_from_filename_convention(raw_row, cfg)
    return ""


def _build_output_columns(
    src_cols: list[str], column_mapping: dict[str, str], pattern: dict[str, Any]
) -> list[str]:
    """JACKPOT target columns plus the synthetic ``files``/``storage_intent`` columns.

    Preserves source-column insertion order so the CSV is deterministic.
    """
    targets: list[str] = []
    seen: set[str] = set()
    for col in src_cols:
        target = column_mapping.get(col)
        if target and target not in seen:
            targets.append(target)
            seen.add(target)

    out_cols = targets + ["files"]
    if (pattern.get("storage_intent") or "").upper() in (
        "EXTERNAL",
        "MANAGED",
        "MIRRORED",
    ):
        out_cols.append("storage_intent")
    return out_cols


def convert_to_csv(session: dict, conn) -> str:
    """Render the wizard's mapped data as a JACKPOT-format CSV string."""
    column_mapping = session.get("column_mapping") or {}
    value_mapping = session.get("value_mapping") or {}
    pattern = session.get("file_reference_pattern") or {}

    if not column_mapping:
        raise HTTPException(
            status_code=422,
            detail="column_mapping is required before converting the session.",
        )

    src_cols, rows = _row_iter_from_session(session, conn)
    out_cols = _build_output_columns(src_cols, column_mapping, pattern)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=out_cols, extrasaction="ignore")
    writer.writeheader()

    for raw in rows:
        mapped = _apply_row_mappings(raw, column_mapping, value_mapping)
        mapped["files"] = _files_column_for_row(raw, pattern)
        if "storage_intent" in out_cols:
            mapped["storage_intent"] = pattern.get("storage_intent", "EXTERNAL")
        writer.writerow(mapped)
    return buf.getvalue()


def compute_preview(session: dict, conn, sample_size: int = 20) -> dict:
    """Run the validator across the first N mapped rows.

    Cached on the session row so re-renders of step 6 don't re-parse
    the spreadsheet.
    """
    from backend.validator import validate_sample  # noqa: PLC0415

    column_mapping = session.get("column_mapping") or {}
    value_mapping = session.get("value_mapping") or {}
    if not column_mapping:
        raise HTTPException(status_code=422, detail="column_mapping is required before preview.")

    _src_cols, rows = _row_iter_from_session(session, conn)
    truncated = rows[:sample_size]
    results: list[dict] = []
    for idx, raw in enumerate(truncated, start=1):
        mapped = _apply_row_mappings(raw, column_mapping, value_mapping)
        validation = validate_sample(mapped)
        results.append(
            {
                "row": idx,
                "sample_id": mapped.get("sample_id"),
                "valid": validation.valid,
                "tier": validation.tier,
                "errors": validation.errors,
                "warnings": validation.warnings,
                "tier2_missing": validation.tier2_missing,
                "tier3_missing": validation.tier3_missing,
            }
        )
    payload = {
        "sample_size": sample_size,
        "total_rows": len(rows),
        "rows": results,
        "truncated": len(rows) > sample_size,
        "row_cap_hit": len(rows) >= MAX_ROWS_PER_IMPORT,
    }
    execute_write(
        "UPDATE import_sessions SET preview_results = CAST(:p AS JSONB), "
        "current_step = :step WHERE id = :id",
        {"p": json.dumps(payload), "step": STEP_PREVIEW, "id": session["id"]},
        conn=conn,
    )
    return payload


def compute_diff(session: dict, conn) -> dict:
    """Diff the mapped rows against existing samples by sample_id."""
    column_mapping = session.get("column_mapping") or {}
    value_mapping = session.get("value_mapping") or {}
    if not column_mapping:
        raise HTTPException(status_code=422, detail="column_mapping is required before diff.")

    _src_cols, rows = _row_iter_from_session(session, conn)
    by_sample_id = _map_rows_by_sample_id(rows, column_mapping, value_mapping)

    if not by_sample_id:
        payload = {"new": [], "changed": [], "unchanged": [], "total": 0}
        return _persist_diff_results(session["id"], payload, conn)

    existing_rows = execute_query(
        "SELECT sample_id, organism_name, source_type, sector "
        "FROM samples WHERE sample_id = ANY(:ids) AND is_archived = FALSE",
        {"ids": list(by_sample_id)},
        conn=conn,
    )
    existing = {r["sample_id"]: r for r in existing_rows}

    payload = _classify_sample_diffs(by_sample_id, existing)
    return _persist_diff_results(session["id"], payload, conn)


def _map_rows_by_sample_id(
    rows: list[dict[str, str]],
    column_mapping: dict[str, str],
    value_mapping: dict[str, dict[str, str]] | None,
) -> dict[str, dict[str, str]]:
    by_sample_id: dict[str, dict[str, str]] = {}
    for raw in rows:
        mapped = _apply_row_mappings(raw, column_mapping, value_mapping)
        sid = mapped.get("sample_id")
        if sid:
            by_sample_id[sid] = mapped
    return by_sample_id


def _classify_sample_diffs(
    by_sample_id: dict[str, dict[str, str]], existing: dict[str, dict]
) -> dict:
    new_list: list[str] = []
    changed: list[dict] = []
    unchanged: list[str] = []
    diff_fields = ("organism_name", "source_type", "sector")
    for sid, mapped in by_sample_id.items():
        if sid not in existing:
            new_list.append(sid)
            continue
        cur = existing[sid]
        delta = {}
        for f in diff_fields:
            new_val = mapped.get(f)
            cur_val = cur.get(f)
            if new_val and new_val != cur_val:
                delta[f] = {"current": cur_val, "incoming": new_val}
        if delta:
            changed.append({"sample_id": sid, "changes": delta})
        else:
            unchanged.append(sid)

    return {
        "new": new_list,
        "changed": changed,
        "unchanged": unchanged,
        "total": len(by_sample_id),
    }


def _persist_diff_results(session_id: int, payload: dict, conn) -> dict:
    execute_write(
        "UPDATE import_sessions SET diff_results = CAST(:d AS JSONB), "
        "current_step = :step WHERE id = :id",
        {"d": json.dumps(payload), "step": STEP_DIFF, "id": session_id},
        conn=conn,
    )
    return payload


def execute_import(
    *,
    session_id: int,
    user_id: int,
    conn,
) -> dict:
    """Convert the session to a JACKPOT CSV and run it through the existing pipe.

    Calls :func:`backend.routers.ingest.run_csv_ingest` (the callable
    core extracted from ``POST /api/v1/ingest/csv``) so I-1 doesn't
    rebuild the row-level ingestion logic. Marks the session
    ``imported`` on success.
    """
    session = get_session_for_user(session_id, user_id, conn)
    csv_str = convert_to_csv(session, conn)

    # Lazy import to avoid the ingest router pulling backend.imports
    # back through its own import graph.
    from backend.routers.ingest import run_csv_ingest  # noqa: PLC0415

    user_row = execute_query(
        "SELECT id, email, name, is_platform_admin, is_data_analyst, "
        "is_active, organization_id FROM users WHERE id = :uid LIMIT 1",
        {"uid": user_id},
        conn=conn,
    )
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found.")

    result = run_csv_ingest(
        csv_text=csv_str,
        user=user_row[0],
        db=conn,
    )

    execute_write(
        "UPDATE import_sessions SET status = 'imported', current_step = :step WHERE id = :id",
        {"id": session_id, "step": STEP_IMPORT},
        conn=conn,
    )
    return result


# ── helpers ─────────────────────────────────────────────────────────


def _serialise(row: dict) -> dict:
    """Make a row JSON-friendly for the response envelope."""
    out = dict(row)
    for k, v in out.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        elif isinstance(v, bytes | bytearray | memoryview):
            # File bytes never go on the wire — they're huge and the
            # frontend doesn't need them. The router returns metadata
            # only; the bytes stay server-side.
            out[k] = None
    return out


__all__ = [
    "MAX_ROWS_PER_IMPORT",
    "STEP_COLUMN_MAPPING",
    "STEP_DIFF",
    "STEP_FILE_REFERENCE",
    "STEP_IMPORT",
    "STEP_PREVIEW",
    "STEP_SHEET_PICKER",
    "STEP_UPLOAD",
    "STEP_VALUE_MAPPING",
    "SpreadsheetMeta",
    "abandon_session",
    "compute_diff",
    "compute_preview",
    "convert_to_csv",
    "create_import_session",
    "execute_import",
    "get_session_for_user",
    "list_user_sessions",
    "parse_spreadsheet",
    "update_import_session",
]
