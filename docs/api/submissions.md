# Submissions API Reference

This document is the developer reference for the JACKPOT HTTP endpoints
under `/api/v1/submissions/` introduced in Phase I-2 (with I-3a/b/c
adding optional backend execution). Audience: SDK and CLI authors,
submission-automation script writers, frontend integrators.

For the conceptual guide — what each lifecycle state means, when JACKPOT
generates a package versus running Seqsender for you, why credentials
are deliberately out-of-band in v1 — see the **Phase I-2 Specification —
Submissions** section in [`spec.md`](../../spec.md). This document
assumes familiarity with that section and focuses on wire shapes.

## Lifecycle states (one-line reference)

A submission row carries a `status` drawn from the `VALID_STATUSES`
enum. Full transition rules live in
[`spec.md`](../../spec.md#phase-i-2-specification--submissions).

| State | Reachable via |
|---|---|
| `DRAFT` | Initial state on `POST /` |
| `READY_TO_SUBMIT` | `POST /{id}/generate` |
| `SUBMITTED` | `POST /{id}/mark-submitted` |
| `ACCEPTED` / `PARTIAL_SUCCESS` | `POST /{id}/register-accessions` (success / partial) |
| `REJECTED` | `POST /{id}/register-accessions` (all rejected) or `POST /{id}/mark-rejected` |
| `EMBARGOED` | `PATCH /{id}` setting `release_date` after acceptance |
| `RELEASED` | `release_embargoed_submissions` daily job |
| `WITHDRAWN` | `POST /{id}/withdraw` |
| `FAILED` | Terminal; surfaced by the package generator on unrecoverable error |
| `EXECUTING` (I-3a) | `POST /{id}/execute` |
| `EXECUTION_FAILED` (I-3a) | Seqsender subprocess returned non-zero |
| `EXECUTION_INTERRUPTED` (I-3a) | API restart abandoned an in-flight subprocess |

## Authentication and authorization

All endpoints require a bearer token in the `Authorization` header:

```
Authorization: Bearer <token>
```

For interactive sessions the session cookie is honoured equivalently.
The router resolves the calling user via `get_current_user()` and then
applies the lab-scoped checks described per endpoint:

- **Read access:** lab membership for the submission's `lab_id`, or
  `is_platform_admin`.
- **Write access:** the submission's creator, a Lab Director on the
  submission's lab, or `is_platform_admin`.
- **Backend execution (I-3a/b/c):** Lab Director only, plus the
  `allow_backend_submission`/`backend_submission_repos` lab settings,
  plus configured C-1 credentials.

Cross-user list scopes are filtered to the caller's labs unless
Platform Admin.

## Response envelope

Every endpoint uses the JACKPOT standard envelope (Critical Rule 24).
See [`docs/api/file_references.md`](file_references.md#response-envelope)
for the canonical shape; the same `success` / `success_list` / `error`
helpers (in `backend/responses.py`) are used here.

## Error codes

| Code | HTTP | Meaning | Endpoints |
|---|---|---|---|
| `VALIDATION_ERROR` | 422 | Body fails schema validation. | All write endpoints. |
| `INVALID_REPOSITORY` | 422 | `target_repository` not in `NCBI` / `GISAID_EPICOV` / `GISAID_EPIFLU` / `GISAID_EPIPOX` / `ENA` / `DDBJ`. | Create, patch. |
| `INVALID_STATUS_TRANSITION` | 409 | Action not allowed from the current status (e.g. `mark-submitted` outside `READY_TO_SUBMIT`). | All transition endpoints. |
| `SAMPLES_LOCKED` | 409 | Samples list is locked because the submission is past `DRAFT`. | `POST/DELETE /{id}/samples`. |
| `NOT_FOUND` | 404 | No submission row with that id, or row belongs to a lab the caller cannot see. | All `/{id}` paths. |
| `ACCESS_DENIED` | 403 | Caller lacks read or write rights. | All `/{id}` paths. |
| `BACKEND_SUBMISSION_DISABLED` | 400 | Lab does not have `allow_backend_submission=true` for the target repo. | I-3 execute / retry. |
| `NO_CREDENTIALS_CONFIGURED` | 400 | One or more required credentials missing for the target repo. `error.detail.missing_keys` lists them. | I-3 execute / retry. |
| `EXECUTION_IN_FLIGHT` | 409 | Cannot retry while another subprocess is `EXECUTING`. | I-3 retry. |
| `INTERNAL_ERROR` | 500 | Unexpected exception. | All endpoints. |

## Endpoints — overview

| Method | Path | Status | Purpose |
|---|---|---|---|
| POST | `/api/v1/submissions/` | Implemented (I-2) | Create a new submission in `DRAFT`. |
| GET | `/api/v1/submissions/` | Implemented (I-2) | Paginated list of visible submissions, optionally filtered. |
| GET | `/api/v1/submissions/{id}` | Implemented (I-2) | Get a single submission. |
| PATCH | `/api/v1/submissions/{id}` | Implemented (I-2) | Partial update of editable fields. |
| DELETE | `/api/v1/submissions/{id}` | Implemented (I-2) | Soft-delete (only allowed in `DRAFT`). |
| POST | `/api/v1/submissions/{id}/samples` | Implemented (I-2) | Add samples to a `DRAFT` submission. |
| DELETE | `/api/v1/submissions/{id}/samples` | Implemented (I-2) | Remove samples from a `DRAFT` submission. |
| POST | `/api/v1/submissions/{id}/validate` | Implemented (I-2) | Run readiness checks; report per-sample issues. |
| POST | `/api/v1/submissions/{id}/generate` | Implemented (I-2) | Generate Seqsender-compatible package on disk. |
| POST | `/api/v1/submissions/{id}/mark-submitted` | Implemented (I-2) | Mark `SUBMITTED` after operator handed package to Seqsender. |
| POST | `/api/v1/submissions/{id}/register-accessions` | Implemented (I-2) | TSV upload or JSON of returned accessions; transitions to `ACCEPTED` / `PARTIAL_SUCCESS` / `REJECTED`. |
| POST | `/api/v1/submissions/{id}/mark-rejected` | Implemented (I-2) | Mark fully rejected with reason. |
| POST | `/api/v1/submissions/{id}/withdraw` | Implemented (I-2) | Withdraw with reason; allowed from any post-`DRAFT` non-`EXECUTING` state. |
| POST | `/api/v1/submissions/{id}/execute` | Implemented (I-3a) | Queue backend Seqsender execution. Returns 202. |
| POST | `/api/v1/submissions/{id}/retry-execution` | Implemented (I-3a) | Retry from `EXECUTION_FAILED` or `EXECUTION_INTERRUPTED`. Returns 202. |
| GET | `/api/v1/submissions/{id}/execution-logs` | Implemented (I-3b) | Signed URL to view the most recent execution log. |

---

## POST /api/v1/submissions/

**Status:** Implemented (I-2).
**Auth:** Bearer token. Caller must have lab membership.

Create a new submission row in `DRAFT` status with an optional initial
sample list.

### Request body

```json
{
  "lab_id": 7,
  "target_repository": "NCBI",
  "title": "Q1 2026 Salmonella batch",
  "description": "Isolates from outbreak EX-2026-001.",
  "sample_ids": [4217, 4218, 4219],
  "bioproject_accession": "PRJNA123456",
  "release_date": "2026-09-01"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `lab_id` | int | yes | FK labs(id). Caller must be a member or Platform Admin. |
| `target_repository` | string | yes | One of `NCBI`, `GISAID_EPICOV`, `GISAID_EPIFLU`, `GISAID_EPIPOX`, `ENA`, `DDBJ`. |
| `title` | string | yes | Human-readable title. |
| `description` | string | no | Free-text. |
| `sample_ids` | array<int> | yes | Initial sample list. May be empty. Must be visible to the caller. |
| `bioproject_accession` | string | no | NCBI BioProject accession; required for NCBI before generation. |
| `release_date` | date (YYYY-MM-DD) | no | Embargo end-date. Required to elect `EMBARGOED` status post-acceptance. |

### Response (success)

```json
{
  "success": true,
  "data": {
    "id": 42,
    "lab_id": 7,
    "target_repository": "NCBI",
    "status": "DRAFT",
    "title": "Q1 2026 Salmonella batch",
    "description": "Isolates from outbreak EX-2026-001.",
    "bioproject_accession": "PRJNA123456",
    "release_date": "2026-09-01",
    "created_by_user_id": 17,
    "created_at": "2026-05-06T18:00:00Z",
    "updated_at": "2026-05-06T18:00:00Z"
  }
}
```

HTTP status: `201 Created`.

### Side effects

- One new `submissions` row.
- N new `submission_samples` rows (one per `sample_ids`).
- `audit_log` entry: `SUBMISSION_CREATED`.

---

## GET /api/v1/submissions/

**Status:** Implemented (I-2).
**Auth:** Bearer token. Non-admins must pass `?lab_id=…`.

### Query parameters

| Param | Type | Default | Description |
|---|---|---|---|
| `lab_id` | int | none | Filter to one lab. Required for non-admins. |
| `status` | string | none | Filter to one status. |
| `target_repository` | string | none | Filter to one repository. |
| `page` | int | 1 | 1-indexed page. |
| `per_page` | int | 50 (max 500) | Items per page. |

### Response

Standard paginated envelope (see
[`docs/api/file_references.md`](file_references.md#paginated-success)).

### Side effects

None.

---

## GET /api/v1/submissions/{id}

**Status:** Implemented (I-2).
**Auth:** Read access required.

Fetch a single submission row. The `submission_samples` array is
returned alongside.

### Response

Single-resource envelope, `data` shaped like the create response with
`samples: [{...}]` appended.

### Side effects

None.

---

## PATCH /api/v1/submissions/{id}

**Status:** Implemented (I-2).
**Auth:** Write access required.

Partial update via `model_dump(exclude_none=True)` (Critical Rule 39).
Only `title`, `description`, `release_date`, `bioproject_accession`,
`target_repository` are patchable. Status changes happen via the
dedicated transition endpoints.

### Request body

```json
{
  "title": "Q1 2026 Salmonella batch (revised)",
  "release_date": "2026-12-01"
}
```

### Side effects

- Row UPDATE with the supplied fields.
- `audit_log` entry: `SUBMISSION_UPDATED`.

---

## DELETE /api/v1/submissions/{id}

**Status:** Implemented (I-2).
**Auth:** Write access required.

Soft-delete via `is_deleted = true`. Only allowed in `DRAFT`.

### Side effects

- `is_deleted = true` UPDATE.
- `audit_log` entry: `SUBMISSION_DELETED`.

---

## POST/DELETE /api/v1/submissions/{id}/samples

**Status:** Implemented (I-2).
**Auth:** Write access required.

Add or remove samples. Only allowed in `DRAFT`. Returns `409
SAMPLES_LOCKED` outside `DRAFT`.

### Request body (both methods)

```json
{
  "sample_ids": [4220, 4221]
}
```

### Side effects

- `submission_samples` rows added or removed (DELETE rolls back any
  previously-set per-sample accessions for those samples).
- `audit_log` entry: `SUBMISSION_SAMPLES_ADDED` /
  `SUBMISSION_SAMPLES_REMOVED`.

---

## POST /api/v1/submissions/{id}/validate

**Status:** Implemented (I-2).
**Auth:** Read access required.

Compute readiness without changing state. Returns per-sample issues
plus an aggregate `valid` boolean.

### Response

```json
{
  "success": true,
  "data": {
    "valid": false,
    "per_sample": [
      {"sample_id": 4217, "issues": []},
      {"sample_id": 4218, "issues": ["host_age missing for human source_type"]}
    ]
  }
}
```

### Side effects

None.

---

## POST /api/v1/submissions/{id}/generate

**Status:** Implemented (I-2).
**Auth:** Write access required.

Run the package generator and transition to `READY_TO_SUBMIT`. Writes
the package directory at `<submission_packages_dir>/<submission_id>/`.
Refuses if validation reports `valid=false`.

### Request body

```json
{ "copy_files": false }
```

| Field | Type | Default | Description |
|---|---|---|---|
| `copy_files` | bool | false | When `true`, copy referenced files into the package; when `false`, symlink (`file://`) or reference (`gs://`). Slower but produces a portable package. |

### Response

```json
{
  "success": true,
  "data": {"package_path": "/var/jackpot/submission_packages/42/"}
}
```

### Side effects

- Package directory written.
- Row UPDATE: `status='READY_TO_SUBMIT'`, `package_path`, `package_generated_at`.
- `audit_log` entry: `SUBMISSION_PACKAGE_GENERATED`.

---

## POST /api/v1/submissions/{id}/mark-submitted

**Status:** Implemented (I-2).
**Auth:** Write access required.

Operator confirms they ran Seqsender (or equivalent) against the
generated package. Transitions `READY_TO_SUBMIT` → `SUBMITTED`.

### Side effects

- Row UPDATE: `status='SUBMITTED'`, `submitted_at=NOW()`.
- `audit_log` entry: `SUBMISSION_MARKED_SUBMITTED`.

---

## POST /api/v1/submissions/{id}/register-accessions

**Status:** Implemented (I-2).
**Auth:** Write access required.

Ingest per-sample accessions returned by the registry. Accepts EITHER
a TSV file upload (`multipart/form-data` with `file=` field) OR a JSON
body with an `accessions` array. The TSV format expects a header row
matching the relevant accession columns (`sample_id`,
`biosample_accession`, `sra_accession`, etc.).

### JSON body shape

```json
{
  "accessions": [
    {"sample_id": 4217, "biosample_accession": "SAMN12345678", "sra_accession": "SRR99887766"},
    {"sample_id": 4218, "per_sample_status": "REJECTED", "per_sample_rejection_reason": "Failed contamination check"}
  ]
}
```

### Response

```json
{
  "success": true,
  "data": {
    "id": 42,
    "status": "PARTIAL_SUCCESS",
    "accepted_count": 1,
    "rejected_count": 1
  }
}
```

Status transitions: all-accepted → `ACCEPTED`; mixed → `PARTIAL_SUCCESS`;
all-rejected → `REJECTED`.

### Side effects

- `submission_samples` rows UPDATE with per-sample accessions and
  `per_sample_status`.
- `submissions.status` UPDATE; `accepted_at` set when transitioning to
  `ACCEPTED` or `PARTIAL_SUCCESS`.
- `audit_log` entry: `SUBMISSION_ACCESSIONS_REGISTERED`.

---

## POST /api/v1/submissions/{id}/mark-rejected

**Status:** Implemented (I-2).
**Auth:** Write access required.

Mark a `SUBMITTED` submission as fully `REJECTED` with a reason.

### Request body

```json
{ "reason": "All samples failed BioSample validation." }
```

### Side effects

- Row UPDATE: `status='REJECTED'`, `rejection_reason`.
- `audit_log` entry: `SUBMISSION_REJECTED`.

---

## POST /api/v1/submissions/{id}/withdraw

**Status:** Implemented (I-2).
**Auth:** Write access required (Lab Director or creator).

Withdraw a submission with a reason. Allowed from any post-`SUBMITTED`
state EXCEPT `EXECUTING` (the in-flight subprocess must complete or
fail before withdrawal).

### Request body

```json
{ "reason": "Per HHS guidance, withdrawing pending re-review." }
```

### Side effects

- Row UPDATE: `status='WITHDRAWN'`, `withdrawal_reason`.
- `audit_log` entry: `SUBMISSION_WITHDRAWN`.

---

## POST /api/v1/submissions/{id}/execute (I-3a)

**Status:** Implemented (I-3a).
**Auth:** Write access required, plus Lab Director.

Queue backend Seqsender execution. Refuses when:

- The lab does not have `allow_backend_submission=true`
  (`400 BACKEND_SUBMISSION_DISABLED`).
- The repo is not in the lab's `backend_submission_repos`
  (`400 BACKEND_SUBMISSION_DISABLED`).
- One or more required credentials are missing per
  `backend/credentials/registry.py` (`400 NO_CREDENTIALS_CONFIGURED`,
  `error.detail.missing_keys` lists them).
- The submission is not in `READY_TO_SUBMIT`
  (`409 INVALID_STATUS_TRANSITION`).

### Request body

```json
{ "executor_backend": "seqsender_subprocess" }
```

`executor_backend` is forward-compat; v1 only ships `seqsender_subprocess`.

### Response

HTTP `202 Accepted`. The subprocess runs asynchronously; clients poll
`GET /{id}` to observe transitions.

### Side effects

- Row UPDATE: `status='EXECUTING'`.
- APScheduler job scheduled to run the Seqsender subprocess.
- `audit_log` entry: `SUBMISSION_EXECUTION_QUEUED`.

---

## POST /api/v1/submissions/{id}/retry-execution (I-3a)

**Status:** Implemented (I-3a).
**Auth:** Same as `/execute`.

Re-queue execution from `EXECUTION_FAILED` or `EXECUTION_INTERRUPTED`.
Refuses with `409 EXECUTION_IN_FLIGHT` if status is `EXECUTING`.

### Side effects

- Row UPDATE: `status='EXECUTING'`.
- New APScheduler job; previous attempt's logs are retained for the
  `execution-logs` endpoint.
- `audit_log` entry: `SUBMISSION_EXECUTION_RETRIED`.

---

## GET /api/v1/submissions/{id}/execution-logs (I-3b)

**Status:** Implemented (I-3b).
**Auth:** Read access required.

Returns a short-lived signed URL to view the most recent execution
log file.

### Response

```json
{
  "success": true,
  "data": {
    "view_url": "https://storage.googleapis.com/jackpot-results-prod/submissions/42/exec-3.log?...",
    "expires_at": "2026-05-06T19:00:00Z",
    "attempt": 3
  }
}
```

### Side effects

None (read-only).

---

## Daily release-embargoed-submissions job

Not an HTTP endpoint per se but worth documenting alongside the API:
`backend/jobs.py::release_embargoed_submissions` runs once per day at
midnight UTC. It scans for `status='EMBARGOED'` rows where
`release_date <= CURRENT_DATE` and transitions each to `RELEASED`.
Operators can trigger it manually via
`POST /api/v1/admin/jobs/release_embargoed_submissions/run`
(Platform Admin only, see Critical Rule 22).
