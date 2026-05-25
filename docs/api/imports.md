# Imports API Reference

This document is the developer reference for the JACKPOT HTTP endpoints
under `/api/v1/imports/` introduced in Phase I-1 (the spreadsheet
importer wizard). Audience: SDK and CLI authors, frontend wizard
implementers, integration script authors.

For the conceptual guide — what a wizard session is, how column-mapping
suggestions are computed, what the lifecycle states mean — see the
existing design docs and the `backend/imports.py` service module's
docstrings.

## Lifecycle (one-line reference)

A wizard session has a numeric `current_step` (1–6) and a TTL'd
lifetime — operators have a window to complete the wizard before the
backend reaps the row. Sessions are server-side; the browser holds
only the session id and the auth cookie. Resumability across IP and
device is by design.

| Step | Purpose |
|---|---|
| 1 | Sheet picker (Excel only) and parse-time metadata. |
| 2 | Column mapping (with auto-suggested mappings + confidence). |
| 3 | Per-import value mapping for enum-shaped columns. |
| 4 | File-reference inference (path-columns or filename-convention). |
| 5 | Preview (first 25 rows post-mapping). |
| 6 | Diff (which rows are inserts, updates, no-ops). |

Step 6 → Execute: `POST /sessions/{id}/import` performs the import
and transitions the session to a terminal state.

## Authentication and authorization

All endpoints require a bearer token (or session cookie) and a
`lab_id` for the create call. Each session is owned by exactly one
user; cross-user access returns **404, not 403**, to avoid leaking
the existence of other users' sessions.

| Action | Permission |
|---|---|
| Create session | Lab membership for the supplied `lab_id`, or Platform Admin. |
| Get / patch / delete session | Caller must be the session owner. |
| Execute import | Caller must be the session owner. |

## Response envelope

Every endpoint uses the JACKPOT standard envelope (Critical Rule 24).
See [`docs/api/file_references.md`](file_references.md#response-envelope)
for the canonical shape.

## Error codes

| Code | HTTP | Meaning | Endpoints |
|---|---|---|---|
| `VALIDATION_ERROR` | 422 | Body or parsed spreadsheet fails validation. | All. |
| `UNSUPPORTED_FILE_FORMAT` | 400 | File extension not in `xlsx` / `csv` / `tsv`. | Create. |
| `PARSE_FAILURE` | 422 | Spreadsheet could not be parsed (corrupt file, unreadable encoding). | Create. |
| `NOT_FOUND` | 404 | No session with that id, OR session owned by a different user. | All `/{id}` paths. |
| `INVALID_STEP` | 409 | PATCH attempts to advance past available data (e.g. value mapping before column mapping). | Patch. |
| `IMPORT_FAILED` | 500 | Execute encountered an unrecoverable error mid-write. Partial inserts roll back via the FastAPI dep transaction. | Execute. |

## Endpoints — overview

| Method | Path | Status | Purpose |
|---|---|---|---|
| POST | `/api/v1/imports/sessions/` | Implemented (I-1) | Create a new wizard session by uploading a spreadsheet. |
| GET | `/api/v1/imports/sessions/` | Implemented (I-1) | List the caller's in-progress sessions. |
| GET | `/api/v1/imports/sessions/{id}` | Implemented (I-1) | Fetch one session. |
| PATCH | `/api/v1/imports/sessions/{id}` | Implemented (I-1) | Partial update; can request `?compute=preview` or `?compute=diff` to refresh derived results. |
| POST | `/api/v1/imports/sessions/{id}/import` | Implemented (I-1) | Execute the import. Transitions the session to terminal. |
| DELETE | `/api/v1/imports/sessions/{id}` | Implemented (I-1) | Abandon the session. |

---

## POST /api/v1/imports/sessions/

**Status:** Implemented (I-1).
**Auth:** Bearer token. Caller must have lab membership.
**Content-Type:** `multipart/form-data`

Create a new wizard session and parse the uploaded file's metadata.
Returns the session row plus a `spreadsheet_meta` block summarising
sheets, columns, sample values, and row counts.

### Form fields

| Field | Type | Required | Description |
|---|---|---|---|
| `lab_id` | int (form field) | yes | Caller must be a member or Platform Admin. |
| `file` | UploadFile | yes | One spreadsheet. Allowed extensions: `xlsx`, `csv`, `tsv`. |

### Response (success)

```json
{
  "success": true,
  "data": {
    "id": 17,
    "user_id": 42,
    "lab_id": 7,
    "file_name": "samples_q1.xlsx",
    "file_format": "xlsx",
    "current_step": 1,
    "selected_sheet": null,
    "column_mapping": null,
    "value_mapping": null,
    "file_reference_pattern": null,
    "preview_results": null,
    "diff_results": null,
    "created_at": "2026-05-06T18:00:00Z",
    "expires_at": "2026-05-13T18:00:00Z",
    "spreadsheet_meta": {
      "sheets": ["Sheet1", "QC"],
      "columns_by_sheet": {
        "Sheet1": ["sample_id", "date_collected", "organism_name", "sequencing_lab"],
        "QC": ["sample_id", "depth_of_coverage"]
      },
      "sample_values_by_sheet": {
        "Sheet1": {"organism_name": ["SARS-CoV-2", "Salmonella enterica"]}
      },
      "row_counts_by_sheet": {"Sheet1": 132, "QC": 132}
    }
  }
}
```

HTTP status: `201 Created`.

### Response (errors)

| HTTP | Code | When |
|---|---|---|
| 400 | (generic) | Unsupported file extension. |
| 422 | `PARSE_FAILURE` | File bytes could not be parsed. |
| 403 | `INSUFFICIENT_PERMISSIONS` | Caller is not a lab member or Platform Admin. |

### Side effects

- One new `import_sessions` row.
- Spreadsheet bytes stored in the configured `import_uploads_dir` /
  bucket.
- `audit_log` entry: `IMPORT_SESSION_CREATED`.

---

## GET /api/v1/imports/sessions/

**Status:** Implemented (I-1).
**Auth:** Bearer token.

Returns the caller's non-expired, non-deleted sessions, ordered by
`created_at` descending.

### Response

Single-list envelope (`data` is an array of session rows; no
pagination — sessions per user are always small).

### Side effects

None.

---

## GET /api/v1/imports/sessions/{id}

**Status:** Implemented (I-1).
**Auth:** Owner only.

### Response

Single-resource envelope. `data` matches the create response without
the `spreadsheet_meta` block (request `compute=preview` or
`compute=diff` via PATCH to refresh derived results).

### Side effects

None.

---

## PATCH /api/v1/imports/sessions/{id}

**Status:** Implemented (I-1).
**Auth:** Owner only.

Partial update of the wizard's mutable fields. Setting any field
clears the downstream derived state (e.g. patching `column_mapping`
clears `preview_results` and `diff_results`).

### Query parameters

| Param | Default | Description |
|---|---|---|
| `compute` | (none) | `"preview"` to recompute `preview_results` after the patch; `"diff"` to recompute `diff_results`. Run AFTER the patch is applied. |

### Request body

```json
{
  "selected_sheet": "Sheet1",
  "column_mapping": {
    "Sample Name": "sample_id",
    "Date Collected": "date_collected",
    "Organism": "organism_name",
    "Lab": "sequencing_lab"
  },
  "value_mapping": {
    "organism_name": {"COVID": "SARS-CoV-2"}
  },
  "file_reference_pattern": {
    "type": "filename_convention",
    "pattern": "{sample_id}_R{1,2}.fastq.gz",
    "base_uri": "file:///srv/seq/runs/240501/"
  },
  "current_step": 5
}
```

| Field | Type | Description |
|---|---|---|
| `selected_sheet` | string | Sheet name (Excel only). |
| `column_mapping` | dict | Spreadsheet header → schema field. |
| `value_mapping` | dict | Per-import value-mapping table for enum-shaped columns. |
| `file_reference_pattern` | dict | Either `{"type": "path_columns", "columns": [...]}` or `{"type": "filename_convention", "pattern": "...", "base_uri": "..."}`. |
| `current_step` | int | 1–6. Setting too far ahead returns `409 INVALID_STEP`. |

### Side effects

- Row UPDATE with the supplied fields.
- Optional preview / diff computation on the same DB transaction.

---

## POST /api/v1/imports/sessions/{id}/import

**Status:** Implemented (I-1).
**Auth:** Owner only.

Execute the import: walk the spreadsheet, apply mappings, and write
samples plus their `sample_files` rows. Soft-fail validation surfaces
samples as `PRELIMINARY` tier with `validation_issues` populated, so
the import never aborts on per-sample data quality alone.

### Response

```json
{
  "success": true,
  "data": {
    "session_id": 17,
    "samples_inserted": 120,
    "samples_updated": 12,
    "samples_skipped": 0,
    "files_registered": 264,
    "files_deduplicated": 12,
    "validation_warnings": [
      {"sample_id": "EX-2026-005", "issues": ["host_age missing"]}
    ]
  }
}
```

HTTP status: `201 Created`.

### Side effects

- N new `samples` rows; M updated `samples` rows.
- File-reference rows added or linked per Critical Rule 58.
- `audit_log` entries: `IMPORT_EXECUTED` plus per-sample
  `CREATE_SAMPLE` / `UPDATE_SAMPLE` events.
- Session row marked terminal so subsequent PATCH/DELETE return
  `409`.

---

## DELETE /api/v1/imports/sessions/{id}

**Status:** Implemented (I-1).
**Auth:** Owner only.

Abandon the session and clean up the uploaded spreadsheet bytes.

### Side effects

- Session row marked deleted (soft-delete).
- Uploaded file bytes removed from `import_uploads_dir` / bucket.
- `audit_log` entry: `IMPORT_SESSION_ABANDONED`.

---

## File-reference inference patterns

Step 4 of the wizard supports two distinct ways to attach files to
samples. Pick whichever matches the operator's filesystem layout:

### Path columns

Use when the spreadsheet has explicit columns containing file URIs.

```json
{
  "type": "path_columns",
  "columns": ["fastq_r1_path", "fastq_r2_path"]
}
```

Each named column is treated as a URI. Empty cells yield no file
reference for that role.

### Filename convention

Use when files live in a known directory and follow a naming pattern.

```json
{
  "type": "filename_convention",
  "pattern": "{sample_id}_R{1,2}.fastq.gz",
  "base_uri": "file:///srv/seq/runs/240501/"
}
```

The `{sample_id}` placeholder substitutes the row's mapped `sample_id`
value. The `{1,2}` group enumerates: e.g. `EX-2026-001_R1.fastq.gz`
and `EX-2026-001_R2.fastq.gz`. Files that don't exist yield a
warning per row but do not fail the import.

## Notes on derived results

`preview_results` and `diff_results` are recomputed only when the
caller passes `?compute=preview` or `?compute=diff` to PATCH. Patches
that don't request recomputation leave the previous derived results
in place — clients should request recomputation after meaningful
changes (column or value mapping) before showing the user the
preview.
