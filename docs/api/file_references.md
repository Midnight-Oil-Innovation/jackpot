> **Status:** Reference — developer reference for the file-references HTTP endpoints (Phase P0f).

# File References API Reference

This document is the developer reference for the JACKPOT HTTP endpoints
that register, inspect, modify, and verify file references introduced in
Phase P0f. Audience: pipeline-automation authors, notebook authors,
SDK consumers, BYOP authors, and federation peer maintainers.

For the conceptual guide — what storage states mean, when JACKPOT
copies, what to do when a file goes `BROKEN` — see
[`docs/file_references.md`](../file_references.md). This document
assumes you have read that one (or are comfortable inferring the
state model from the field reference below) and focuses on the wire
shape of each endpoint.

## Storage states (one-line reference)

A `sample_files` row carries a `storage_state` drawn from a fixed
five-value enum. Full semantics live in
[`docs/file_references.md`](../file_references.md#the-five-storage-states).

| State | Lifecycle owner |
|---|---|
| `EXTERNAL` | The caller. Default for any registration that does not request a copy. |
| `MANAGED` | JACKPOT. Set when a caller requests ownership at ingest, when a pipeline produces an output, or after a successful `promote --to managed`. |
| `MIRRORED` | JACKPOT, with origin tracking. Set after a successful `promote --to mirrored`. |
| `STAGED` | JACKPOT. Set internally when a pipeline run stages an input across a compute boundary; auto-cleaned. Not user-requestable at ingest. |
| `BROKEN` | n/a. A terminal state reached when verification fails. |

The accepted values for `storage_intent` at ingest time are `EXTERNAL`,
`MANAGED`, and `MIRRORED`. `STAGED` and `BROKEN` are internal lifecycle
states; passing them in a request body returns `422`.

## Authentication

All file-reference endpoints require a bearer token in the
`Authorization` header:

```
Authorization: Bearer <token>
```

Tokens are issued through `POST /api/v1/tokens` and managed through
the user-settings UI. For interactive sessions, a session cookie is
honoured equivalently. Endpoint-by-endpoint authorization (project
membership, lab role) is described inline.

## Response envelope

Every endpoint returns the standard JACKPOT envelope.

### Success

```json
{
  "success": true,
  "data": { /* endpoint-specific shape */ }
}
```

### Success with non-fatal advisories

```json
{
  "success": true,
  "data": { /* endpoint-specific shape */ },
  "warnings": [
    "Human-readable advisory string."
  ]
}
```

The `warnings` array is omitted when there are no advisories. It is
distinct from `error` — a response with `warnings` is still a success.

### Paginated success

```json
{
  "success": true,
  "data": [ /* list of items */ ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 137,
    "pages": 3
  }
}
```

### Error

```json
{
  "success": false,
  "error": {
    "code": "FILE_UNREACHABLE",
    "message": "Unable to read file at file:///srv/seq/missing.fastq.gz: ...",
    "detail": { /* code-specific extras */ }
  }
}
```

The HTTP status code matches the severity (4xx for caller errors,
5xx for server errors). The `error.code` is the stable machine-readable
identifier; clients should branch on `code`, not on the message string.

## Error codes

| Code | HTTP | Meaning | Endpoints |
|---|---|---|---|
| `VALIDATION_ERROR` | 422 | Request body or sample metadata failed schema or business-rule validation. The `error.detail` object contains per-field error lists. | `register`, `upload`, `csv` |
| `INVALID_STORAGE_INTENT` | 422 | `storage_intent` value is not one of `EXTERNAL` / `MANAGED` / `MIRRORED`. | `register`, `csv`, `promote` |
| `FILE_UNREACHABLE` | 400 | A URI provided at registration cannot be read by the JACKPOT service user. The `error.detail` carries `uri`, `underlying_error`, and a `suggestion` string. | `register`, `upload` (when fingerprinting fails) |
| `FILE_NOT_FOUND` | 404 | No `sample_files` row exists with the given `file_id`. | `GET /files/{id}`, `promote`, `verify` |
| `INSUFFICIENT_PERMISSIONS` | 403 | Caller lacks rights to view or modify the file's owning sample (project membership / lab role). | `GET /files/{id}`, `promote`, `verify`, list endpoints |
| `BROKEN_INPUTS` | 400 | Pipeline launch refused because one or more input files are `BROKEN`. The `error.detail.broken_files` array lists the offending `sample_files` ids and URIs. | `POST /pipelines/launch` (cross-reference; documented in the pipelines API reference) |

## Endpoints — overview

| Method | Path | Status | Purpose |
|---|---|---|---|
| POST | `/api/v1/ingest/register` | Implemented | Register one sample with one or more files at given URIs; no bytes uploaded. |
| POST | `/api/v1/ingest/upload` | Implemented (updated) | Upload bytes; the row is always `MANAGED`. |
| POST | `/api/v1/ingest/csv` | Implemented (updated) | Bulk register from a CSV; per-row `storage_intent`. |
| POST | `/api/v1/ingest/globus` | Implemented (updated) | Globus deposit-first webhook; resulting registrations are always `EXTERNAL`. |
| POST | `/api/v1/files/{file_id}/promote` | Planned (F-9) | Change a row's `storage_state`; copy runs as a background job. |
| GET | `/api/v1/files/{file_id}` | Planned (F-10 / follow-on) | Retrieve one `sample_files` row plus referencing samples. |
| GET | `/api/v1/files/` | Planned (F-10 / follow-on) | Paginated list with filters: `storage_state`, `broken_only`, `project_id`. |
| POST | `/api/v1/files/{file_id}/verify` | Planned (F-10 / follow-on) | Force re-verification of a single file. |

"Implemented" means the endpoint is live on `development`. "Planned"
means the spec is locked but the endpoint is not yet wired up; the
contract below is what the implementation will satisfy.

---

## POST /api/v1/ingest/register

**Status:** Implemented (P0f F-6).
**Auth:** Bearer token. Caller must have access to the target project.

Register a sample plus one or more files at known URIs. No file bytes
are uploaded — JACKPOT records the URI, computes a cheap fingerprint
(size + first 64 KB SHA-256 + last 64 KB SHA-256), and either creates
a fresh `sample_files` row or links to an existing row whose
fingerprint matches.

This is the canonical endpoint for "register a file that lives at a
path I already know." Use `/api/v1/ingest/upload` instead when you
want JACKPOT to take ownership of bytes you are uploading directly.

### Request body

```json
{
  "sample_metadata": {
    "sample_id": "EX-2026-001",
    "source_type": "human",
    "case_id": "CASE-2026-001",
    "date_collected": "2026-04-15",
    "organism_name": "SARS-CoV-2",
    "sequencing_lab": "Example Sequencing Lab"
  },
  "files": [
    {
      "role": "R1",
      "uri": "file:///srv/seq/runs/240501/sample01_R1.fastq.gz",
      "storage_intent": "EXTERNAL"
    },
    {
      "role": "R2",
      "uri": "file:///srv/seq/runs/240501/sample01_R2.fastq.gz",
      "storage_intent": "EXTERNAL"
    }
  ]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `sample_metadata` | object | yes | Sample fields validated against the LinkML schema. Required keys depend on `source_type` and the operator's configured tier. At minimum `sample_id`, `source_type`, and `date_collected` must be present. |
| `files` | array | yes | One or more file specs. Must be non-empty. |
| `files[].role` | string | yes | One of `R1`, `R2`, `LONG_READ`, `ASSEMBLY`, `OTHER`. |
| `files[].uri` | string | yes | A URI the JACKPOT service user can read. Schemes accepted: `file://`, `gs://`, `s3://`, `sra://`, `https://`. |
| `files[].storage_intent` | string | no | One of `EXTERNAL`, `MANAGED`, `MIRRORED`. Defaults to `EXTERNAL` when omitted or empty. |

### Response (success)

```json
{
  "success": true,
  "data": {
    "sample_id": "EX-2026-001",
    "id": 4217,
    "quality_status": "PASS",
    "surveillance_relevant": true,
    "files": [
      {
        "sample_files_id": 9001,
        "uri": "file:///srv/seq/runs/240501/sample01_R1.fastq.gz",
        "storage_state": "EXTERNAL",
        "deduplicated": false
      },
      {
        "sample_files_id": 9002,
        "uri": "file:///srv/seq/runs/240501/sample01_R2.fastq.gz",
        "storage_state": "EXTERNAL",
        "deduplicated": false
      }
    ]
  }
}
```

HTTP status: `201 Created`.

`deduplicated` is `true` when the cheap fingerprint matched an existing
row; in that case the URI is appended to that row's `alternate_uris`
and no new `sample_files` row was created. `storage_state` reflects the
state actually applied to the row — for a dedup hit, the existing row's
state is preserved (it is **not** transitioned to the requested intent;
see [Dedup and storage intent](#dedup-and-storage-intent) below).

### Response (errors)

| HTTP | Code | When |
|---|---|---|
| 422 | `VALIDATION_ERROR` | Sample metadata fails LinkML or business-rule validation. `detail` carries `errors`, `warnings`, `tier2_missing`, `tier3_missing`. |
| 422 | `INVALID_STORAGE_INTENT` | A `storage_intent` is not in `EXTERNAL` / `MANAGED` / `MIRRORED`. |
| 400 | `FILE_UNREACHABLE` | A URI cannot be read. Whole request rolls back — no sample row is created. |
| 422 | (generic) | `files` is empty, `role` is invalid, etc. |

### Side effects

- One new `samples` row.
- Per file: either one new `sample_files` row, or `alternate_uris`
  appended on an existing row.
- `audit_log` entries: one `CREATE_SAMPLE`, plus one of
  `REGISTER_FILE` / `DEDUP_FILE` per file.
- The full SHA-256 hash is **not** computed inline. The
  `compute_full_content_hash` background job (~5 min cadence) picks
  up rows with `content_hash IS NULL`.

### Dedup and storage intent

When the cheap fingerprint of a registered URI matches an existing
`sample_files` row, the existing row is reused — its `storage_state`
is **not** transitioned to honour the new request. Concretely:

- A request with `storage_intent=MANAGED` against content that already
  exists as an `EXTERNAL` row results in the existing `EXTERNAL` row
  being linked to the new sample. The row stays `EXTERNAL`.
- The new URI is appended to `alternate_uris` if it differs from the
  row's primary `uri`.
- If you want JACKPOT to take ownership of an already-registered file,
  use [`POST /api/v1/files/{file_id}/promote`](#post-apiv1filesfile_idpromote)
  after registration.

This protects callers' explicit storage-state choices from being
overwritten by a later registration that happened to match.

### Examples

**curl:**

```bash
curl -X POST https://jackpot.example.org/api/v1/ingest/register \
  -H "Authorization: Bearer $JACKPOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sample_metadata": {
      "sample_id": "EX-2026-001",
      "source_type": "human",
      "case_id": "CASE-2026-001",
      "date_collected": "2026-04-15",
      "organism_name": "SARS-CoV-2",
      "sequencing_lab": "Example Sequencing Lab"
    },
    "files": [
      {"role": "R1", "uri": "gs://lab-runs/240501/sample01_R1.fastq.gz"},
      {"role": "R2", "uri": "gs://lab-runs/240501/sample01_R2.fastq.gz"}
    ]
  }'
```

**Python (requests):**

```python
import os
import requests

resp = requests.post(
    "https://jackpot.example.org/api/v1/ingest/register",
    headers={"Authorization": f"Bearer {os.environ['JACKPOT_TOKEN']}"},
    json={
        "sample_metadata": {
            "sample_id": "EX-2026-001",
            "source_type": "human",
            "case_id": "CASE-2026-001",
            "date_collected": "2026-04-15",
            "organism_name": "SARS-CoV-2",
            "sequencing_lab": "Example Sequencing Lab",
        },
        "files": [
            {"role": "R1", "uri": "gs://lab-runs/240501/sample01_R1.fastq.gz"},
            {"role": "R2", "uri": "gs://lab-runs/240501/sample01_R2.fastq.gz"},
        ],
    },
    timeout=30,
)
resp.raise_for_status()
body = resp.json()
print(body["data"]["sample_id"], body["data"]["files"])
```

A typed `client.ingest.register(...)` SDK method is not yet available;
use the HTTP form above.

---

## POST /api/v1/files/{file_id}/promote

**Status:** Planned (P0f F-9).
**Auth:** Bearer token. Caller must have write access to the file's
owning sample.

Transition a `sample_files` row's `storage_state` and, if the
transition requires a copy, schedule the copy as a background job. The
endpoint returns immediately with `202 Accepted` and a job identifier
the caller can poll.

Valid transitions:

- `EXTERNAL` → `MANAGED` (copy then update)
- `EXTERNAL` → `MIRRORED` (copy then update; original URI tracked)
- `MIRRORED` → `MANAGED` (drop origin tracking; original may be retired)

Other transitions (e.g. `MANAGED` → `EXTERNAL`) are rejected with
`422`.

### Path parameters

| Name | Type | Description |
|---|---|---|
| `file_id` | integer | The `sample_files.id` to promote. |

### Request body

```json
{
  "to": "MANAGED",
  "retention_policy": "STANDARD"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `to` | string | yes | Target state. One of `MANAGED`, `MIRRORED`. |
| `retention_policy` | string | no | One of `STANDARD`, `LONG_TERM`, `EPHEMERAL`. Defaults to `STANDARD`. |

### Response (success)

```json
{
  "success": true,
  "data": {
    "file_id": 9001,
    "from_state": "EXTERNAL",
    "to_state": "MANAGED",
    "job_id": "promote-9001-26b41e",
    "retention_policy": "STANDARD",
    "status": "QUEUED"
  }
}
```

HTTP status: `202 Accepted`.

`status` follows the standard background-job lifecycle:
`QUEUED` → `RUNNING` → `COMPLETED` / `FAILED`. The `storage_state`
on the row remains the source value until the copy completes; it
flips to the target state in the same transaction that records job
completion.

### Response (errors)

| HTTP | Code | When |
|---|---|---|
| 404 | `FILE_NOT_FOUND` | No `sample_files` row with `id = file_id`. |
| 403 | `INSUFFICIENT_PERMISSIONS` | Caller cannot modify this file's owning sample. |
| 422 | `INVALID_STORAGE_INTENT` | `to` is not `MANAGED` or `MIRRORED`, or the requested transition is not allowed from the current state. |
| 422 | `VALIDATION_ERROR` | `retention_policy` invalid. |

### Side effects

- One background copy job scheduled in the APScheduler queue.
- One `audit_log` entry with action `PROMOTE_FILE`, recording the
  source state, target state, and job id.
- On job success: `storage_state` updated; for `MIRRORED`, the
  original URI is recorded as `original_uri`; for `MANAGED`, a follow-up
  audit entry records the completion.
- On job failure: `storage_state` is unchanged; the audit entry
  records the failure and surfaces it via the notifications system.

### Examples

**curl:**

```bash
curl -X POST https://jackpot.example.org/api/v1/files/9001/promote \
  -H "Authorization: Bearer $JACKPOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to": "MANAGED", "retention_policy": "STANDARD"}'
```

SDK method not yet available; use the HTTP form above. The CLI command
`jackpot files promote --sample EX-2026-001 --role R1 --to managed`
will route through this endpoint once F-9 lands.

---

## GET /api/v1/files/{file_id}

**Status:** Planned (P0f follow-on).
**Auth:** Bearer token. Caller must be able to see the file's owning
sample (project membership or platform-admin scope).

Retrieve a single `sample_files` row plus the list of samples that
reference it.

### Path parameters

| Name | Type | Description |
|---|---|---|
| `file_id` | integer | The `sample_files.id` to retrieve. |

### Response (success)

```json
{
  "success": true,
  "data": {
    "id": 9001,
    "uri": "gs://lab-runs/240501/sample01_R1.fastq.gz",
    "alternate_uris": [
      "file:///srv/seq/runs/240501/sample01_R1.fastq.gz"
    ],
    "filename": "sample01_R1.fastq.gz",
    "file_type": "fastq",
    "file_size_bytes": 524288000,
    "head64k_hash": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    "tail64k_hash": "ef797c8118f02dfb649607dd5d3f8c7623048c9c063d532cc95c5ed7a898a64f",
    "content_hash": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
    "storage_state": "EXTERNAL",
    "library_layout": "PAIRED",
    "read_direction": "R1",
    "first_seen_at": "2026-04-16T14:21:09Z",
    "last_verified_at": "2026-05-03T02:11:33Z",
    "last_verification_status": "OK",
    "retention_policy": "STANDARD",
    "original_uri": null,
    "staged_for_run_id": null,
    "ingest_method": "register",
    "samples": [
      {
        "sample_id": "EX-2026-001",
        "id": 4217,
        "role": "R1",
        "project_id": 12,
        "lab_id": 3
      }
    ]
  }
}
```

HTTP status: `200 OK`.

The `samples` array carries one entry per sample that references this
file (multiple entries on shared-content rows; see
[`docs/file_references.md`](../file_references.md#when-the-same-file-shows-up-twice)).

### Response (errors)

| HTTP | Code | When |
|---|---|---|
| 404 | `FILE_NOT_FOUND` | No row with the given `file_id`, or the row is soft-deleted. |
| 403 | `INSUFFICIENT_PERMISSIONS` | Caller cannot see any sample referencing this file. |

### Side effects

None — read-only.

### Examples

**curl:**

```bash
curl -H "Authorization: Bearer $JACKPOT_TOKEN" \
  https://jackpot.example.org/api/v1/files/9001
```

---

## GET /api/v1/files/

**Status:** Planned (P0f follow-on).
**Auth:** Bearer token. Results are scoped to files referenced by
samples the caller can see.

List `sample_files` rows with optional filters and standard
pagination. The intended uses are operator dashboards (find every
`BROKEN` file in the deployment) and project-scoped listings.

### Query parameters

| Name | Type | Description |
|---|---|---|
| `storage_state` | string | Filter to one `storage_state` value. Repeat the parameter to OR multiple values: `?storage_state=EXTERNAL&storage_state=MIRRORED`. |
| `broken_only` | boolean | Shorthand for `storage_state=BROKEN`. Default `false`. |
| `project_id` | integer | Restrict to files referenced by samples in the given project. |
| `page` | integer | 1-based page index. Default `1`. |
| `per_page` | integer | Page size (max `200`). Default `50`. |
| `sort_by` | string | One of `first_seen_at`, `last_verified_at`, `file_size_bytes`. Default `first_seen_at`. |
| `sort_dir` | string | `asc` or `desc`. Default `desc`. |

### Response (success)

```json
{
  "success": true,
  "data": [
    {
      "id": 9001,
      "uri": "gs://lab-runs/240501/sample01_R1.fastq.gz",
      "filename": "sample01_R1.fastq.gz",
      "file_type": "fastq",
      "file_size_bytes": 524288000,
      "storage_state": "EXTERNAL",
      "last_verified_at": "2026-05-03T02:11:33Z",
      "last_verification_status": "OK",
      "sample_count": 1,
      "project_ids": [12]
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 137,
    "pages": 3
  }
}
```

HTTP status: `200 OK`.

The list shape is a digest, not the full row. Use
[`GET /api/v1/files/{file_id}`](#get-apiv1filesfile_id) for the full
row including `alternate_uris`, hashes, and the per-sample reference
list.

### Response (errors)

| HTTP | Code | When |
|---|---|---|
| 422 | `VALIDATION_ERROR` | Invalid filter value (e.g. `storage_state=UNKNOWN`). |
| 403 | `INSUFFICIENT_PERMISSIONS` | `project_id` filter targets a project the caller cannot see. |

### Side effects

None — read-only.

### Examples

Find every `BROKEN` file across the deployment (platform admin):

```bash
curl -H "Authorization: Bearer $JACKPOT_TOKEN" \
  "https://jackpot.example.org/api/v1/files/?broken_only=true&per_page=200"
```

List `EXTERNAL` files in a single project, oldest first:

```bash
curl -H "Authorization: Bearer $JACKPOT_TOKEN" \
  "https://jackpot.example.org/api/v1/files/?project_id=12&storage_state=EXTERNAL&sort_dir=asc"
```

---

## POST /api/v1/files/{file_id}/verify

**Status:** Planned (P0f follow-on).
**Auth:** Bearer token. Caller must be able to see the file's owning
sample.

Force a synchronous re-verification of a single file. Use this when a
user has just put a missing file back and wants to clear the `BROKEN`
state without waiting for the daily verification job.

The check uses the same logic as the `verify_file_references`
background job: stat (`file://`), HEAD (`gs://`, `s3://`, `https://`),
or metadata lookup (`sra://`). Verification reads only metadata — no
fingerprint recomputation, no full hash.

### Path parameters

| Name | Type | Description |
|---|---|---|
| `file_id` | integer | The `sample_files.id` to verify. |

### Request body

None.

### Response (success)

```json
{
  "success": true,
  "data": {
    "file_id": 9001,
    "uri": "gs://lab-runs/240501/sample01_R1.fastq.gz",
    "storage_state": "EXTERNAL",
    "last_verification_status": "OK",
    "last_verified_at": "2026-05-03T15:42:01Z"
  }
}
```

HTTP status: `200 OK`.

`last_verification_status` is one of `OK`, `MISSING`, `SIZE_CHANGED`,
or `READ_ERROR`. When the check fails (`MISSING` or `SIZE_CHANGED`),
the row's `storage_state` transitions to `BROKEN` in the same
transaction; this response shows the post-verification state, so a
freshly-broken file returns `storage_state = BROKEN` and
`last_verification_status = MISSING` (or similar).

When the check passes against a row that was previously `BROKEN`, the
row clears back to its prior non-terminal state (`EXTERNAL` or
`MIRRORED`) and the response reflects the cleared state.

### Response (errors)

| HTTP | Code | When |
|---|---|---|
| 404 | `FILE_NOT_FOUND` | No row with the given `file_id`. |
| 403 | `INSUFFICIENT_PERMISSIONS` | Caller cannot see any sample referencing this file. |
| 422 | `VALIDATION_ERROR` | The file is in a state where verify is not meaningful (e.g. `STAGED`). |

### Side effects

- The row's `last_verified_at` and `last_verification_status` are
  updated unconditionally (success or failure).
- On a failed check, the row's `storage_state` is set to `BROKEN`
  and one `audit_log` entry with action `MARK_FILE_BROKEN` is
  written. Notifications are emitted to the file's owning project.
- On a check that clears a previous `BROKEN` row, the row's
  `storage_state` returns to its non-terminal value and one
  `audit_log` entry records the recovery.

### Examples

**curl:**

```bash
curl -X POST -H "Authorization: Bearer $JACKPOT_TOKEN" \
  https://jackpot.example.org/api/v1/files/9001/verify
```

SDK method not yet available.

---

## Updates to existing endpoints

P0f changes the contract of three existing ingest endpoints. None of
the changes are breaking for clients that ignore unknown response
fields; the additions are described here for completeness.

### POST /api/v1/ingest/upload

**Status:** Implemented. Updated in P0f F-6.

Behaviour change: the response now includes `storage_state` on each
file, and the value is always `MANAGED` because `/upload` always stages
the bytes you uploaded into JACKPOT-controlled storage. There is no
opt-out — if you want `EXTERNAL`, use `/api/v1/ingest/register`
against an externally-hosted URI instead.

Response data shape (abridged):

```json
{
  "success": true,
  "data": {
    "id": 4218,
    "sample_id": "EX-2026-002",
    "files": [
      {
        "id": 9003,
        "uri": "gs://jackpot-managed/staging/EX-2026-002/sample02_R1.fastq.gz",
        "filename": "sample02_R1.fastq.gz",
        "storage_state": "MANAGED",
        "ingest_method": "gui"
      }
    ]
  }
}
```

### POST /api/v1/ingest/csv

**Status:** Implemented. Updated in P0f F-6.

Behaviour change:

- An optional `storage_intent` column is honoured per row. Accepted
  values: `EXTERNAL`, `MANAGED`, `MIRRORED`. Empty cells default to
  `EXTERNAL`.
- When the column is absent from the CSV header altogether, the
  response carries an envelope-level `warnings` entry advising that
  every row defaulted to `EXTERNAL`. This is informational, not an
  error — the import still succeeds.

Response data shape (abridged):

```json
{
  "success": true,
  "data": {
    "success": 12,
    "failed": 0,
    "errors": [],
    "created_ids": [4220, 4221, 4222]
  },
  "warnings": [
    "storage_intent column missing from CSV. Files registered with the default storage_state='EXTERNAL' (no copy made) per Critical Rule 57. To request copies, add a storage_intent column with value 'MANAGED' (or 'MIRRORED') for the relevant rows. See docs/file_references.md."
  ]
}
```

When the column is present, `warnings` is omitted from the envelope.

### POST /api/v1/ingest/globus

**Status:** Implemented. Updated in P0f F-6.

Behaviour change: files registered through the Globus deposit-first
flow are always `EXTERNAL`. JACKPOT records the Globus access URI and
references the file in place. This is a clarification of existing
behaviour — earlier versions did not surface the `storage_state` for
Globus-registered files, but they were already `EXTERNAL` in practice.

The endpoint itself has no new request fields. The downstream
`sample_files` rows created when the recipient lab director follows
the deposit notification through to `/upload` or `/register` carry
`storage_state = EXTERNAL`; if the lab director wants ownership, they
explicitly pass `storage_intent: "MANAGED"` at that step.

---

## Cross-references

- [`spec.md`](../../spec.md) — Phase P0f Specification (canonical
  design source).
- [`docs/file_references.md`](../file_references.md) — operator-facing
  guide to the storage-state model.
- Pipeline launch behaviour around `BROKEN` inputs is documented with
  the pipelines API; the `BROKEN_INPUTS` error originates from
  `POST /api/v1/pipelines/launch`, not from the file-reference
  endpoints themselves.

## Versioning

P0f introduces these endpoints under `/api/v1/`. Breaking changes —
removing fields, changing field types, renaming codes — would land
under a new prefix. Additive changes (new optional fields, new error
codes for new failure modes) may land in `/api/v1/` and are described
in the `learnings.md` changelog when they ship.
