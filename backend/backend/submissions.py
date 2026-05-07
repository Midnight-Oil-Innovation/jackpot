# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Submission lifecycle business logic for I-2.

Encapsulates the state machine described in the I-2 design notes:

    DRAFT  →  READY_TO_SUBMIT  →  SUBMITTED  →
        ACCEPTED / PARTIAL_SUCCESS / REJECTED  →
            EMBARGOED  →  RELEASED
                                      WITHDRAWN  (any post-SUBMITTED state)

Each transition is gated, audited, and may emit a notification.
Per Critical Rule 4 every status change writes ``log_audit``. Per
Critical Rule 24 the router layer wraps return values in the standard
response envelope.

The router (``backend/routers/submissions.py``) is a thin shell over
this module so the CLI can call the same functions directly without
HTTP round-trips.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException

from backend.audit import AuditActions, log_audit
from backend.database import execute_query, execute_write
from backend.notifications import NotificationEvents, create_notification

logger = logging.getLogger(__name__)


# ── lifecycle constants ────────────────────────────────────────────

VALID_REPOSITORIES: frozenset[str] = frozenset(
    {"NCBI", "GISAID_EPICOV", "GISAID_EPIFLU", "GISAID_EPIPOX", "ENA", "DDBJ"}
)

# Status set kept here so tests + router can validate without going to
# the DB CHECK constraint.
#
# I-3a added EXECUTING / EXECUTION_FAILED / EXECUTION_INTERRUPTED for
# backend-driven submission execution. EXECUTING is the in-flight state
# entered by ``mark_execution_queued``; EXECUTION_FAILED is set when
# Seqsender returns non-zero (I-3b); EXECUTION_INTERRUPTED is set by
# the lifespan recovery hook when an API restart abandons an in-flight
# subprocess (Critical Rule 60).
VALID_STATUSES: frozenset[str] = frozenset(
    {
        "DRAFT",
        "READY_TO_SUBMIT",
        "SUBMITTED",
        "PARTIAL_SUCCESS",
        "ACCEPTED",
        "REJECTED",
        "EMBARGOED",
        "RELEASED",
        "WITHDRAWN",
        "FAILED",
        # I-3a backend-execution states
        "EXECUTING",
        "EXECUTION_FAILED",
        "EXECUTION_INTERRUPTED",
    }
)

# Statuses for which the samples list is locked. Once the package has
# been generated we no longer let users add or remove samples — the
# whole point of the READY_TO_SUBMIT state is to capture an immutable
# snapshot the operator can hand to Seqsender.
_SAMPLES_LOCKED_STATUSES: frozenset[str] = frozenset(VALID_STATUSES - {"DRAFT"})

# Statuses that allow the user to withdraw the submission after the fact.
# I-3a: also reachable from EXECUTION_FAILED and EXECUTION_INTERRUPTED so
# the operator can give up on a failed backend execution. NOT reachable
# from EXECUTING — withdrawing while a subprocess is running would leave
# the executor mid-flight; we require the user to wait for completion or
# failure first.
_POST_SUBMITTED_STATUSES: frozenset[str] = frozenset(
    {
        "SUBMITTED",
        "PARTIAL_SUCCESS",
        "ACCEPTED",
        "EMBARGOED",
        "RELEASED",
        "REJECTED",
        # I-3a
        "EXECUTION_FAILED",
        "EXECUTION_INTERRUPTED",
    }
)

# Statuses from which a backend execution can be (re)queued. The initial
# queue happens from READY_TO_SUBMIT; retries from the two failure
# states. EXECUTING is intentionally excluded — re-queuing while in
# flight would race the existing subprocess.
_EXECUTION_QUEUEABLE_STATUSES: frozenset[str] = frozenset({"READY_TO_SUBMIT"})
_EXECUTION_RETRYABLE_STATUSES: frozenset[str] = frozenset(
    {"EXECUTION_FAILED", "EXECUTION_INTERRUPTED"}
)


# ── small dataclasses ─────────────────────────────────────────────


@dataclass(frozen=True)
class AccessionEntry:
    """A single line from an accessions registration file."""

    sample_id: str
    biosample: str | None = None
    sra: str | None = None
    genbank: str | None = None
    gisaid: str | None = None
    ena: str | None = None
    ddbj: str | None = None
    rejection_reason: str | None = None

    @property
    def has_any_accession(self) -> bool:
        return any(
            getattr(self, k) for k in ("biosample", "sra", "genbank", "gisaid", "ena", "ddbj")
        )


@dataclass(frozen=True)
class SampleValidationIssue:
    sample_id: str
    issues: list[str]


@dataclass(frozen=True)
class SubmissionValidationResult:
    valid: bool
    per_sample: list[SampleValidationIssue]


# ── helpers ────────────────────────────────────────────────────────


def _serialise(row: dict) -> dict:
    out = dict(row)
    for k, v in out.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
    return out


def _require_status(submission: dict, allowed: frozenset[str]) -> None:
    """Raise 422 if the submission is not in one of ``allowed`` states."""
    status = submission.get("status")
    if status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Submission is in status {status!r}; this action requires "
                f"one of {sorted(allowed)}."
            ),
        )


def _require_repository(repository: str) -> None:
    if repository not in VALID_REPOSITORIES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid target_repository {repository!r}; "
                f"must be one of {sorted(VALID_REPOSITORIES)}."
            ),
        )


def _get_submission(submission_id: int, conn) -> dict | None:
    rows = execute_query(
        "SELECT * FROM submissions WHERE id = :id AND is_deleted = FALSE LIMIT 1",
        {"id": submission_id},
        conn=conn,
    )
    return rows[0] if rows else None


def _require_submission(submission_id: int, conn) -> dict:
    sub = _get_submission(submission_id, conn)
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found.")
    return sub


def _audit(
    action: str,
    *,
    actor_id: int | None,
    submission_id: int,
    before: dict | None,
    after: dict | None,
    db,
) -> None:
    log_audit(
        action=action,
        actor_id=actor_id,
        resource_type="submission",
        resource_id=str(submission_id),
        before=before,
        after=after,
        metadata=None,
        db_conn=db,
    )


# ── core: create / read / update / list ───────────────────────────


def create_submission(
    *,
    user_id: int,
    lab_id: int,
    target_repository: str,
    title: str,
    sample_ids: list[int],
    description: str | None = None,
    bioproject_accession: str | None = None,
    release_date: date | None = None,
    conn,
) -> dict:
    """Create a new DRAFT submission with the given samples attached.

    The DRAFT state allows further sample add/remove and field edits.
    Use ``generate_package`` to transition to READY_TO_SUBMIT.
    """
    _require_repository(target_repository)
    if not title or not title.strip():
        raise HTTPException(status_code=422, detail="title is required.")
    if not sample_ids:
        raise HTTPException(status_code=422, detail="At least one sample is required.")

    rows = execute_write(
        """
        INSERT INTO submissions (
            created_by_user_id, lab_id, target_repository,
            title, description, status,
            bioproject_accession, release_date
        ) VALUES (
            :uid, :lab, :repo, :title, :desc, 'DRAFT',
            :bioproj, :rel
        )
        RETURNING *
        """,
        {
            "uid": user_id,
            "lab": lab_id,
            "repo": target_repository,
            "title": title.strip(),
            "desc": description,
            "bioproj": bioproject_accession,
            "rel": release_date,
        },
        conn=conn,
    )
    submission = rows[0]

    add_samples_to_submission(
        submission_id=submission["id"],
        sample_ids=sample_ids,
        actor_id=user_id,
        conn=conn,
        _audit_first_add=False,  # bundle into the create audit
    )

    _audit(
        AuditActions.SUBMISSION_CREATED,
        actor_id=user_id,
        submission_id=submission["id"],
        before=None,
        after={
            "target_repository": target_repository,
            "title": title,
            "sample_count": len(sample_ids),
        },
        db=conn,
    )
    return _serialise(submission)


def get_submission(submission_id: int, conn) -> dict:
    """Return a single submission row plus its ``samples`` list.

    Raises ``HTTPException(404)`` when the row is missing or marked
    deleted. The ``samples`` field is populated via
    :func:`list_submission_samples` so callers don't have to issue a
    second query.
    """
    sub = _require_submission(submission_id, conn)
    sub["samples"] = list_submission_samples(submission_id, conn)
    return _serialise(sub)


def list_submissions(
    *,
    lab_id: int | None = None,
    status: str | None = None,
    target_repository: str | None = None,
    page: int = 1,
    per_page: int = 50,
    conn,
) -> tuple[list[dict], int]:
    """Return one page of submissions plus the total count for pagination.

    All filters are optional. ``status`` is validated against
    :data:`VALID_STATUSES` (422 on unknown); ``target_repository`` is
    validated against :data:`VALID_REPOSITORIES`. Results are ordered
    ``created_at DESC`` so the most recent shows first. ``is_deleted``
    rows are always excluded.
    """
    where = ["is_deleted = FALSE"]
    params: dict[str, Any] = {}
    if lab_id is not None:
        where.append("lab_id = :lab_id")
        params["lab_id"] = lab_id
    if status is not None:
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=422, detail=f"Invalid status {status!r}.")
        where.append("status = :status")
        params["status"] = status
    if target_repository is not None:
        _require_repository(target_repository)
        where.append("target_repository = :repo")
        params["repo"] = target_repository

    where_sql = " AND ".join(where)
    offset = (page - 1) * per_page
    rows = execute_query(
        f"""
        SELECT * FROM submissions
         WHERE {where_sql}
         ORDER BY created_at DESC
         LIMIT :_limit OFFSET :_offset
        """,
        {**params, "_limit": per_page, "_offset": offset},
        conn=conn,
    )
    count_rows = execute_query(
        f"SELECT COUNT(*) AS total FROM submissions WHERE {where_sql}",
        params,
        conn=conn,
    )
    total = count_rows[0]["total"] if count_rows else 0
    return [_serialise(r) for r in rows], total


_PATCHABLE_FIELDS_DRAFT: frozenset[str] = frozenset(
    {"title", "description", "release_date", "bioproject_accession", "target_repository"}
)
_PATCHABLE_FIELDS_POST_DRAFT: frozenset[str] = frozenset({"description", "release_date"})


def update_submission(
    *,
    submission_id: int,
    actor_id: int | None,
    fields: dict[str, Any],
    conn,
) -> dict:
    """Apply a partial update to a submission's editable fields.

    Field whitelist is status-dependent: ``DRAFT`` allows
    :data:`_PATCHABLE_FIELDS_DRAFT` (title, description, release_date,
    bioproject_accession, target_repository); post-DRAFT submissions
    only allow :data:`_PATCHABLE_FIELDS_POST_DRAFT` (description,
    release_date) so already-shipped packages can't be retroactively
    rewritten. Any field outside the allowed set raises 422.
    Empty patches are no-ops. Per Critical Rule 39, the SQL UPDATE is
    built from the supplied keys only.
    """
    sub = _require_submission(submission_id, conn)
    allowed = _PATCHABLE_FIELDS_DRAFT if sub["status"] == "DRAFT" else _PATCHABLE_FIELDS_POST_DRAFT
    bad = sorted(k for k in fields if k not in allowed)
    if bad:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot patch fields {bad} in status {sub['status']!r}.",
        )
    if "target_repository" in fields:
        _require_repository(fields["target_repository"])

    sets = []
    params: dict[str, Any] = {"id": submission_id}
    for k, v in fields.items():
        sets.append(f"{k} = :{k}")
        params[k] = v
    if not sets:
        return _serialise(sub)

    rows = execute_write(
        f"UPDATE submissions SET {', '.join(sets)} WHERE id = :id RETURNING *",
        params,
        conn=conn,
    )
    return _serialise(rows[0])


def soft_delete_submission(*, submission_id: int, actor_id: int | None, conn) -> dict:
    """Mark a ``DRAFT`` submission ``is_deleted = TRUE``.

    Refuses with 422 outside ``DRAFT`` — once a submission has moved
    past DRAFT, the row is part of an audit trail and must be
    withdrawn (:func:`withdraw_submission`) rather than deleted.
    """
    sub = _require_submission(submission_id, conn)
    if sub["status"] != "DRAFT":
        raise HTTPException(
            status_code=422,
            detail=f"Can only delete DRAFT submissions; this one is {sub['status']!r}.",
        )
    rows = execute_write(
        "UPDATE submissions SET is_deleted = TRUE WHERE id = :id RETURNING *",
        {"id": submission_id},
        conn=conn,
    )
    return _serialise(rows[0])


# ── samples ───────────────────────────────────────────────────────


def list_submission_samples(submission_id: int, conn) -> list[dict]:
    """Return rows from ``submission_samples`` joined to ``samples``.

    Each entry includes the per-submission columns (per_sample_status,
    per-repository accessions, rejection reason) plus a few useful
    sample-level columns (sample_id, organism_name, quality_status,
    scrub_status, sharing_level) so the UI can render a sample list
    without a second query. Sorted by ``submission_samples.id ASC``
    so the order is stable.
    """
    rows = execute_query(
        """
        SELECT ss.*, s.sample_id, s.organism_name, s.quality_status,
               s.scrub_status, s.sharing_level
          FROM submission_samples ss
          JOIN samples s ON s.id = ss.sample_id_fk
         WHERE ss.submission_id = :id
         ORDER BY ss.id ASC
        """,
        {"id": submission_id},
        conn=conn,
    )
    return [_serialise(r) for r in rows]


def add_samples_to_submission(
    *,
    submission_id: int,
    sample_ids: list[int],
    actor_id: int | None,
    conn,
    _audit_first_add: bool = True,
) -> list[dict]:
    """Insert new ``submission_samples`` rows for the given sample ids.

    Refuses with 422 outside ``DRAFT`` (samples list locks once the
    package is generated). Idempotent: ``ON CONFLICT DO NOTHING``
    silently skips sample ids that are already attached. Returns the
    list of newly-inserted rows (excluding skipped duplicates) so the
    caller can audit-log only what changed. Audits as
    ``SUBMISSION_SAMPLES_ADDED`` when at least one row was inserted.
    """
    sub = _require_submission(submission_id, conn)
    if sub["status"] != "DRAFT":
        raise HTTPException(
            status_code=422,
            detail=(f"Can only add samples in DRAFT status; this submission is {sub['status']!r}."),
        )

    inserted: list[dict] = []
    for sid in sample_ids:
        # ON CONFLICT DO NOTHING keeps the call idempotent.
        rows = execute_write(
            """
            INSERT INTO submission_samples (submission_id, sample_id_fk, per_sample_status)
            VALUES (:sub, :sid, 'PENDING')
            ON CONFLICT (submission_id, sample_id_fk) DO NOTHING
            RETURNING *
            """,
            {"sub": submission_id, "sid": sid},
            conn=conn,
        )
        if rows:
            inserted.append(_serialise(rows[0]))

    if _audit_first_add and inserted:
        _audit(
            AuditActions.SUBMISSION_SAMPLES_ADDED,
            actor_id=actor_id,
            submission_id=submission_id,
            before=None,
            after={"added_count": len(inserted), "sample_ids": sample_ids},
            db=conn,
        )
    return inserted


def remove_samples_from_submission(
    *,
    submission_id: int,
    sample_ids: list[int],
    actor_id: int | None,
    conn,
) -> int:
    """Delete ``submission_samples`` rows for the given sample ids.

    Refuses with 422 outside ``DRAFT``. Returns the count of rows
    actually deleted (sample ids not in the submission are silently
    skipped). Audits as ``SUBMISSION_SAMPLES_REMOVED`` when at least
    one row was removed.
    """
    sub = _require_submission(submission_id, conn)
    if sub["status"] != "DRAFT":
        raise HTTPException(
            status_code=422,
            detail=(
                f"Can only remove samples in DRAFT status; this submission is {sub['status']!r}."
            ),
        )
    rows = execute_write(
        """
        DELETE FROM submission_samples
         WHERE submission_id = :sub
           AND sample_id_fk = ANY(:ids)
         RETURNING id
        """,
        {"sub": submission_id, "ids": sample_ids},
        conn=conn,
    )
    if rows:
        _audit(
            AuditActions.SUBMISSION_SAMPLES_REMOVED,
            actor_id=actor_id,
            submission_id=submission_id,
            before=None,
            after={"removed_count": len(rows), "sample_ids": sample_ids},
            db=conn,
        )
    return len(rows)


# ── readiness validation ──────────────────────────────────────────


# Per-repository required fields the user must populate before a
# package can be generated. Kept conservative for v1 — the package
# generators surface richer per-row validation when they actually
# build the TSVs.
_REPOSITORY_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "NCBI": (
        "sample_id",
        "organism_name",
        "collection_location_country",
        "date_collected",
        "source_type",
    ),
    "GISAID_EPICOV": (
        "sample_id",
        "organism_name",
        "collection_location_country",
        "date_collected",
    ),
    "GISAID_EPIFLU": (
        "sample_id",
        "organism_name",
        "collection_location_country",
        "date_collected",
    ),
    "GISAID_EPIPOX": (
        "sample_id",
        "organism_name",
        "collection_location_country",
        "date_collected",
    ),
    "ENA": (
        "sample_id",
        "organism_name",
        "collection_location_country",
        "date_collected",
    ),
    "DDBJ": (
        "sample_id",
        "organism_name",
        "collection_location_country",
        "date_collected",
    ),
}


def validate_submission_readiness(submission_id: int, conn) -> SubmissionValidationResult:
    """Return per-sample validation issues; the caller decides what to do.

    Does NOT mutate the submission. The router calls this for the
    /validate endpoint; ``generate_package`` calls it again as a
    pre-flight check before transitioning state.
    """
    sub = _require_submission(submission_id, conn)
    repo = sub["target_repository"]
    required = _REPOSITORY_REQUIRED_FIELDS.get(repo, ())

    rows = execute_query(
        """
        SELECT s.* FROM samples s
          JOIN submission_samples ss ON ss.sample_id_fk = s.id
         WHERE ss.submission_id = :id
           AND s.is_deleted = FALSE
        """,
        {"id": submission_id},
        conn=conn,
    )

    per_sample: list[SampleValidationIssue] = []
    for row in rows:
        missing = [f for f in required if not row.get(f)]
        if missing:
            per_sample.append(
                SampleValidationIssue(
                    sample_id=row.get("sample_id") or str(row.get("id")),
                    issues=[f"missing required field: {f}" for f in missing],
                )
            )

    _audit(
        AuditActions.SUBMISSION_VALIDATED,
        actor_id=None,
        submission_id=submission_id,
        before=None,
        after={
            "passing_samples": len(rows) - len(per_sample),
            "failing_samples": len(per_sample),
        },
        db=conn,
    )
    return SubmissionValidationResult(valid=not per_sample, per_sample=per_sample)


# ── state transitions ─────────────────────────────────────────────


def mark_package_generated(
    *,
    submission_id: int,
    package_path: str,
    actor_id: int | None,
    conn,
) -> dict:
    """Record the generated package path and transition to READY_TO_SUBMIT.

    Called by ``generate_package`` in :mod:`backend.submission_packages`
    after the directory is written. Kept as a separate function so
    tests can exercise the state transition independently of the
    actual file-system work.
    """
    sub = _require_submission(submission_id, conn)
    _require_status(sub, frozenset({"DRAFT", "READY_TO_SUBMIT"}))
    rows = execute_write(
        """
        UPDATE submissions
           SET status = 'READY_TO_SUBMIT',
               package_path = :pkg,
               package_generated_at = NOW()
         WHERE id = :id
         RETURNING *
        """,
        {"pkg": package_path, "id": submission_id},
        conn=conn,
    )
    updated = rows[0]
    _audit(
        AuditActions.SUBMISSION_GENERATED,
        actor_id=actor_id,
        submission_id=submission_id,
        before={"status": sub["status"]},
        after={"status": "READY_TO_SUBMIT", "package_path": package_path},
        db=conn,
    )
    create_notification(
        recipient_id=updated["created_by_user_id"],
        event_type=NotificationEvents.SUBMISSION_PACKAGE_READY,
        title=f"Submission package ready: {updated['title']}",
        body=(
            f"Package generated at {package_path}. Run Seqsender on a "
            f"stable host using your own credentials, then return to "
            f"JACKPOT and click 'Mark as Submitted'."
        ),
        resource_type="submission",
        resource_id=str(submission_id),
        action_url=f"/submissions/{submission_id}",
        db_conn=conn,
    )
    return _serialise(updated)


def mark_submitted(*, submission_id: int, actor_id: int | None, conn) -> dict:
    """Transition ``READY_TO_SUBMIT`` → ``SUBMITTED``.

    The operator calls this after handing the generated package to
    Seqsender (or the equivalent uploader for the target repository)
    and observing that the submission was accepted into the registry's
    intake queue. Stamps ``submitted_at = NOW()``. Audits as
    ``SUBMISSION_MARKED_SUBMITTED``. Refuses (422) outside
    ``READY_TO_SUBMIT``.
    """
    sub = _require_submission(submission_id, conn)
    _require_status(sub, frozenset({"READY_TO_SUBMIT"}))
    rows = execute_write(
        """
        UPDATE submissions
           SET status = 'SUBMITTED', submitted_at = NOW()
         WHERE id = :id
         RETURNING *
        """,
        {"id": submission_id},
        conn=conn,
    )
    _audit(
        AuditActions.SUBMISSION_MARKED_SUBMITTED,
        actor_id=actor_id,
        submission_id=submission_id,
        before={"status": "READY_TO_SUBMIT"},
        after={"status": "SUBMITTED"},
        db=conn,
    )
    return _serialise(rows[0])


def parse_accessions_tsv(text: str) -> list[AccessionEntry]:
    """Parse the user-supplied accessions.tsv into typed entries.

    Format (tab-delimited, hyphen `-` for not-applicable):

        sample_id  biosample  sra  genbank  gisaid  ena  ddbj  rejection_reason
    """
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    fieldnames = reader.fieldnames or []
    if not fieldnames or "sample_id" not in fieldnames:
        raise HTTPException(
            status_code=422,
            detail="Accessions file must have a 'sample_id' column.",
        )

    def _normalise(v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return None if v in ("", "-") else v

    entries: list[AccessionEntry] = []
    for row in reader:
        sid = _normalise(row.get("sample_id"))
        if not sid:
            continue
        entries.append(
            AccessionEntry(
                sample_id=sid,
                biosample=_normalise(row.get("biosample")),
                sra=_normalise(row.get("sra")),
                genbank=_normalise(row.get("genbank")),
                gisaid=_normalise(row.get("gisaid")),
                ena=_normalise(row.get("ena")),
                ddbj=_normalise(row.get("ddbj")),
                rejection_reason=_normalise(row.get("rejection_reason")),
            )
        )
    if not entries:
        raise HTTPException(status_code=422, detail="No accession rows parsed.")
    return entries


def register_accessions(
    *,
    submission_id: int,
    accessions: list[AccessionEntry],
    actor_id: int | None,
    conn,
) -> dict:
    """Apply accession assignments and transition status accordingly.

    The new status is one of:

    - ``ACCEPTED`` — every entry has at least one accession.
    - ``PARTIAL_SUCCESS`` — some entries got accessions, others have
      rejection_reason set.
    - ``EMBARGOED`` — fully accepted, but ``release_date`` is in the
      future. Daily APScheduler job promotes to ``RELEASED`` later.
    - ``RELEASED`` — fully accepted with ``release_date`` in the past
      or null. Skips EMBARGOED.
    """
    sub = _require_submission(submission_id, conn)
    _require_status(sub, frozenset({"SUBMITTED", "PARTIAL_SUCCESS"}))

    accepted_count = 0
    rejected_count = 0
    for entry in accessions:
        # Look up the sample row by user-facing sample_id within the
        # submission. Cross-submission registration is rejected.
        rows = execute_query(
            """
            SELECT ss.id, ss.sample_id_fk, s.sample_id
              FROM submission_samples ss
              JOIN samples s ON s.id = ss.sample_id_fk
             WHERE ss.submission_id = :sub
               AND s.sample_id = :sid
            """,
            {"sub": submission_id, "sid": entry.sample_id},
            conn=conn,
        )
        if not rows:
            logger.warning(
                "register_accessions: sample %s not in submission %s; skipping",
                entry.sample_id,
                submission_id,
            )
            continue
        ss_id = rows[0]["id"]
        sample_id_fk = rows[0]["sample_id_fk"]
        is_accepted = entry.has_any_accession and not entry.rejection_reason
        new_status = "ACCEPTED" if is_accepted else "REJECTED"
        if is_accepted:
            accepted_count += 1
        else:
            rejected_count += 1

        execute_write(
            """
            UPDATE submission_samples
               SET per_sample_status = :ps,
                   biosample_accession = COALESCE(:biosample, biosample_accession),
                   sra_accession = COALESCE(:sra, sra_accession),
                   genbank_accession = COALESCE(:genbank, genbank_accession),
                   gisaid_accession = COALESCE(:gisaid, gisaid_accession),
                   ena_accession = COALESCE(:ena, ena_accession),
                   ddbj_accession = COALESCE(:ddbj, ddbj_accession),
                   per_sample_rejection_reason = COALESCE(:reason, per_sample_rejection_reason)
             WHERE id = :id
            """,
            {
                "id": ss_id,
                "ps": new_status,
                "biosample": entry.biosample,
                "sra": entry.sra,
                "genbank": entry.genbank,
                "gisaid": entry.gisaid,
                "ena": entry.ena,
                "ddbj": entry.ddbj,
                "reason": entry.rejection_reason,
            },
            conn=conn,
        )

        # Mirror the accession columns onto the sample row for fast
        # lookup in existing UI views. Critical Rule 58 keeps
        # sample_files as the dedup primitive; the samples-row
        # accession columns are convenience fields that already
        # existed before I-2.
        execute_write(
            """
            UPDATE samples
               SET biosample_accession = COALESCE(:biosample, biosample_accession),
                   sra_accession = COALESCE(:sra, sra_accession),
                   genbank_accession = COALESCE(:genbank, genbank_accession),
                   gisaid_accession = COALESCE(:gisaid, gisaid_accession)
             WHERE id = :sid
            """,
            {
                "sid": sample_id_fk,
                "biosample": entry.biosample,
                "sra": entry.sra,
                "genbank": entry.genbank,
                "gisaid": entry.gisaid,
            },
            conn=conn,
        )

    # Decide the new submission status based on per-sample counts.
    if rejected_count and accepted_count:
        new_status = "PARTIAL_SUCCESS"
        notif_event = NotificationEvents.SUBMISSION_PARTIAL_SUCCESS
    elif rejected_count and not accepted_count:
        new_status = "REJECTED"
        notif_event = NotificationEvents.SUBMISSION_REJECTED
    else:
        # Fully accepted. Embargo decision based on release_date.
        rd = sub.get("release_date")
        if rd and isinstance(rd, date) and rd > datetime.now(UTC).date():
            new_status = "EMBARGOED"
            notif_event = NotificationEvents.SUBMISSION_ACCEPTED
        else:
            new_status = "RELEASED"
            notif_event = NotificationEvents.SUBMISSION_RELEASED

    rows = execute_write(
        """
        UPDATE submissions
           SET status = :st,
               accepted_at = COALESCE(accepted_at, NOW())
         WHERE id = :id
         RETURNING *
        """,
        {"id": submission_id, "st": new_status},
        conn=conn,
    )
    updated = rows[0]
    _audit(
        AuditActions.SUBMISSION_REGISTERED_ACCESSIONS,
        actor_id=actor_id,
        submission_id=submission_id,
        before={"status": sub["status"]},
        after={
            "status": new_status,
            "accepted": accepted_count,
            "rejected": rejected_count,
        },
        db=conn,
    )
    create_notification(
        recipient_id=updated["created_by_user_id"],
        event_type=notif_event,
        title=f"Submission update: {updated['title']}",
        body=(f"Status is now {new_status}. {accepted_count} accepted, {rejected_count} rejected."),
        resource_type="submission",
        resource_id=str(submission_id),
        action_url=f"/submissions/{submission_id}",
        db_conn=conn,
    )
    return _serialise(updated)


def mark_rejected(
    *,
    submission_id: int,
    reason: str,
    actor_id: int | None,
    conn,
) -> dict:
    """Transition ``SUBMITTED`` → ``REJECTED`` with a free-text reason.

    Use when the registry returned a fully-rejected response (none of
    the samples received accessions). When some accessions came back
    and others didn't, prefer :func:`register_accessions` which
    transitions to ``PARTIAL_SUCCESS`` with the per-sample detail.
    ``reason`` must be non-empty (422 otherwise). Audits as
    ``SUBMISSION_MARKED_REJECTED`` and notifies the creator.
    """
    sub = _require_submission(submission_id, conn)
    _require_status(sub, frozenset({"SUBMITTED"}))
    if not reason or not reason.strip():
        raise HTTPException(status_code=422, detail="reason is required.")
    rows = execute_write(
        """
        UPDATE submissions
           SET status = 'REJECTED', rejection_reason = :reason
         WHERE id = :id
         RETURNING *
        """,
        {"id": submission_id, "reason": reason.strip()},
        conn=conn,
    )
    _audit(
        AuditActions.SUBMISSION_MARKED_REJECTED,
        actor_id=actor_id,
        submission_id=submission_id,
        before={"status": "SUBMITTED"},
        after={"status": "REJECTED", "reason": reason},
        db=conn,
    )
    create_notification(
        recipient_id=rows[0]["created_by_user_id"],
        event_type=NotificationEvents.SUBMISSION_REJECTED,
        title=f"Submission rejected: {rows[0]['title']}",
        body=reason,
        resource_type="submission",
        resource_id=str(submission_id),
        action_url=f"/submissions/{submission_id}",
        db_conn=conn,
    )
    return _serialise(rows[0])


def withdraw_submission(
    *,
    submission_id: int,
    reason: str,
    actor_id: int | None,
    conn,
) -> dict:
    """Transition any post-``SUBMITTED`` non-``EXECUTING`` state → ``WITHDRAWN``.

    Allowed source states are :data:`_POST_SUBMITTED_STATUSES`
    (``SUBMITTED``, ``PARTIAL_SUCCESS``, ``ACCEPTED``, ``EMBARGOED``,
    ``RELEASED``, ``REJECTED``, plus the I-3a execution-failure
    states). ``EXECUTING`` is intentionally refused with a 409 and a
    pointed message because withdrawing while a Seqsender subprocess
    is in flight would leave the executor mid-flight; the user must
    wait for completion or failure first. ``reason`` must be non-empty
    (422 otherwise). Audits as ``SUBMISSION_WITHDRAWN`` and notifies
    the creator.
    """
    sub = _require_submission(submission_id, conn)
    # I-3a: special-case EXECUTING with a clearer error message before the
    # generic _require_status check fires. Without this branch the user
    # gets the verbose "must be one of [...]" listing instead of an
    # explanation of what to do.
    if sub.get("status") == "EXECUTING":
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot withdraw a submission while backend execution is "
                "in progress. Wait for it to complete or fail; then "
                "withdraw."
            ),
        )
    _require_status(sub, _POST_SUBMITTED_STATUSES)
    if not reason or not reason.strip():
        raise HTTPException(status_code=422, detail="reason is required.")
    rows = execute_write(
        """
        UPDATE submissions
           SET status = 'WITHDRAWN', withdrawal_reason = :reason
         WHERE id = :id
         RETURNING *
        """,
        {"id": submission_id, "reason": reason.strip()},
        conn=conn,
    )
    _audit(
        AuditActions.SUBMISSION_WITHDRAWN,
        actor_id=actor_id,
        submission_id=submission_id,
        before={"status": sub["status"]},
        after={"status": "WITHDRAWN", "reason": reason},
        db=conn,
    )
    create_notification(
        recipient_id=rows[0]["created_by_user_id"],
        event_type=NotificationEvents.SUBMISSION_WITHDRAWN,
        title=f"Submission withdrawn: {rows[0]['title']}",
        body=reason,
        resource_type="submission",
        resource_id=str(submission_id),
        action_url=f"/submissions/{submission_id}",
        db_conn=conn,
    )
    return _serialise(rows[0])


# ── I-3a: backend-driven execution transitions ────────────────────
#
# These functions implement the state-machine seams for backend
# execution. None of them invoke a subprocess — that lives in I-3b.
# The lifespan recovery hook (``recover_interrupted_executions``) is
# the only one called from outside test code in I-3a.


def mark_execution_queued(
    *,
    submission_id: int,
    executor_backend: str,
    actor_id: int | None,
    conn,
) -> dict:
    """Transition READY_TO_SUBMIT → EXECUTING.

    Stamps ``execution_started_at = NOW()``, sets ``executor_backend``,
    increments ``execution_attempt_count`` from 0 to 1.

    Emits ``SUBMISSION_BACKEND_EXECUTION_QUEUED`` audit and
    ``SUBMISSION_EXECUTION_QUEUED`` notification.
    """
    sub = _require_submission(submission_id, conn)
    _require_status(sub, _EXECUTION_QUEUEABLE_STATUSES)
    rows = execute_write(
        """
        UPDATE submissions
           SET status = 'EXECUTING',
               execution_started_at = NOW(),
               execution_completed_at = NULL,
               execution_error_message = NULL,
               execution_attempt_count = execution_attempt_count + 1,
               executor_backend = :exec
         WHERE id = :id
         RETURNING *
        """,
        {"id": submission_id, "exec": executor_backend},
        conn=conn,
    )
    updated = rows[0]
    _audit(
        AuditActions.SUBMISSION_BACKEND_EXECUTION_QUEUED,
        actor_id=actor_id,
        submission_id=submission_id,
        before={"status": sub["status"]},
        after={
            "status": "EXECUTING",
            "executor_backend": executor_backend,
            "attempt": updated["execution_attempt_count"],
        },
        db=conn,
    )
    create_notification(
        recipient_id=updated["created_by_user_id"],
        event_type=NotificationEvents.SUBMISSION_EXECUTION_QUEUED,
        title=f"Submission queued for backend execution: {updated['title']}",
        body=(
            f"Attempt {updated['execution_attempt_count']} via "
            f"{executor_backend}. You'll be notified on completion or "
            f"failure."
        ),
        resource_type="submission",
        resource_id=str(submission_id),
        action_url=f"/submissions/{submission_id}",
        db_conn=conn,
    )
    return _serialise(updated)


def mark_execution_retried(
    *,
    submission_id: int,
    executor_backend: str,
    actor_id: int | None,
    conn,
) -> dict:
    """Transition EXECUTION_FAILED|EXECUTION_INTERRUPTED → EXECUTING.

    Resets ``execution_started_at = NOW()``, clears the prior
    ``execution_error_message``, increments ``execution_attempt_count``.
    Preserves ``execution_log_uris`` (multiple attempts accumulate log
    URIs in the array; I-3b appends, never overwrites).
    """
    sub = _require_submission(submission_id, conn)
    _require_status(sub, _EXECUTION_RETRYABLE_STATUSES)
    previous_status = sub["status"]
    rows = execute_write(
        """
        UPDATE submissions
           SET status = 'EXECUTING',
               execution_started_at = NOW(),
               execution_completed_at = NULL,
               execution_error_message = NULL,
               execution_attempt_count = execution_attempt_count + 1,
               executor_backend = :exec
         WHERE id = :id
         RETURNING *
        """,
        {"id": submission_id, "exec": executor_backend},
        conn=conn,
    )
    updated = rows[0]
    _audit(
        AuditActions.SUBMISSION_BACKEND_EXECUTION_RETRY_QUEUED,
        actor_id=actor_id,
        submission_id=submission_id,
        before={"status": previous_status},
        after={
            "status": "EXECUTING",
            "executor_backend": executor_backend,
            "attempt": updated["execution_attempt_count"],
            "previous_status": previous_status,
        },
        db=conn,
    )
    create_notification(
        recipient_id=updated["created_by_user_id"],
        event_type=NotificationEvents.SUBMISSION_EXECUTION_QUEUED,
        title=f"Submission retry queued: {updated['title']}",
        body=(
            f"Retry attempt {updated['execution_attempt_count']} via "
            f"{executor_backend} (previous status: {previous_status})."
        ),
        resource_type="submission",
        resource_id=str(submission_id),
        action_url=f"/submissions/{submission_id}",
        db_conn=conn,
    )
    return _serialise(updated)


def mark_execution_completed(
    *,
    submission_id: int,
    actor_id: int | None = None,
    conn,
) -> dict:
    """Transition EXECUTING → SUBMITTED on successful execution.

    I-3b calls this from the executor's success path. The full
    accession-registration flow stays separate (``register_accessions``)
    — Seqsender's stdout doesn't always carry per-sample accessions, so
    we only mark the submission as SUBMITTED here and let the existing
    accession registration codepath fill in the per-sample accessions
    when the operator (or the executor) provides them.
    """
    sub = _require_submission(submission_id, conn)
    _require_status(sub, frozenset({"EXECUTING"}))
    rows = execute_write(
        """
        UPDATE submissions
           SET status = 'SUBMITTED',
               submitted_at = COALESCE(submitted_at, NOW()),
               execution_completed_at = NOW()
         WHERE id = :id
         RETURNING *
        """,
        {"id": submission_id},
        conn=conn,
    )
    updated = rows[0]
    _audit(
        AuditActions.SUBMISSION_BACKEND_EXECUTION_COMPLETED,
        actor_id=actor_id,
        submission_id=submission_id,
        before={"status": "EXECUTING"},
        after={
            "status": "SUBMITTED",
            "attempt": updated["execution_attempt_count"],
        },
        db=conn,
    )
    create_notification(
        recipient_id=updated["created_by_user_id"],
        event_type=NotificationEvents.SUBMISSION_EXECUTION_COMPLETED,
        title=f"Submission executed successfully: {updated['title']}",
        body=(
            f"Backend execution completed on attempt "
            f"{updated['execution_attempt_count']}. Awaiting per-sample "
            f"accession registration."
        ),
        resource_type="submission",
        resource_id=str(submission_id),
        action_url=f"/submissions/{submission_id}",
        db_conn=conn,
    )
    return _serialise(updated)


def mark_execution_failed(
    *,
    submission_id: int,
    error_message: str,
    log_uri: str | None = None,
    actor_id: int | None = None,
    conn,
) -> dict:
    """Transition EXECUTING → EXECUTION_FAILED.

    Stamps ``execution_completed_at = NOW()``, populates
    ``execution_error_message``. If ``log_uri`` is provided, appends to
    ``execution_log_uris`` JSONB array.
    """
    sub = _require_submission(submission_id, conn)
    _require_status(sub, frozenset({"EXECUTING"}))
    if not error_message or not error_message.strip():
        raise HTTPException(status_code=422, detail="error_message is required.")
    if log_uri:
        # to_jsonb(:uri) alone fails with "could not determine polymorphic
        # type because input has type unknown" because psycopg2 ships
        # bare parameter values as unknowns. Wrap with CAST(... AS text)
        # so Postgres can resolve the polymorphic to_jsonb() variant.
        # The shorter ::text postfix syntax is parsed as a SQLAlchemy
        # named-bind by `:uri::text` and breaks at execute time.
        update_sql = """
            UPDATE submissions
               SET status = 'EXECUTION_FAILED',
                   execution_completed_at = NOW(),
                   execution_error_message = :msg,
                   execution_log_uris =
                       execution_log_uris || to_jsonb(CAST(:uri AS text))
             WHERE id = :id
             RETURNING *
        """
        params = {
            "id": submission_id,
            "msg": error_message.strip(),
            "uri": log_uri,
        }
    else:
        update_sql = """
            UPDATE submissions
               SET status = 'EXECUTION_FAILED',
                   execution_completed_at = NOW(),
                   execution_error_message = :msg
             WHERE id = :id
             RETURNING *
        """
        params = {"id": submission_id, "msg": error_message.strip()}
    rows = execute_write(update_sql, params, conn=conn)
    updated = rows[0]
    _audit(
        AuditActions.SUBMISSION_BACKEND_EXECUTION_FAILED,
        actor_id=actor_id,
        submission_id=submission_id,
        before={"status": "EXECUTING"},
        after={
            "status": "EXECUTION_FAILED",
            "error_message": error_message.strip(),
            "log_uri": log_uri,
            "attempt": updated["execution_attempt_count"],
        },
        db=conn,
    )
    create_notification(
        recipient_id=updated["created_by_user_id"],
        event_type=NotificationEvents.SUBMISSION_EXECUTION_FAILED,
        title=f"Submission execution failed: {updated['title']}",
        body=error_message.strip(),
        resource_type="submission",
        resource_id=str(submission_id),
        action_url=f"/submissions/{submission_id}",
        db_conn=conn,
    )
    return _serialise(updated)


def mark_execution_interrupted(
    *,
    submission_id: int,
    error_message: str = "API restart detected during execution",
    actor_id: int | None = None,
    conn,
) -> dict:
    """Transition EXECUTING → EXECUTION_INTERRUPTED.

    Called by ``recover_interrupted_executions`` during lifespan startup.
    Distinct from ``mark_execution_failed`` because the cause is
    environmental (Critical Rule 60) rather than submission-specific.
    """
    sub = _require_submission(submission_id, conn)
    _require_status(sub, frozenset({"EXECUTING"}))
    rows = execute_write(
        """
        UPDATE submissions
           SET status = 'EXECUTION_INTERRUPTED',
               execution_completed_at = NOW(),
               execution_error_message = :msg
         WHERE id = :id
         RETURNING *
        """,
        {"id": submission_id, "msg": error_message},
        conn=conn,
    )
    updated = rows[0]
    _audit(
        AuditActions.SUBMISSION_BACKEND_EXECUTION_INTERRUPTED,
        actor_id=actor_id,
        submission_id=submission_id,
        before={"status": "EXECUTING"},
        after={
            "status": "EXECUTION_INTERRUPTED",
            "error_message": error_message,
            "attempt": updated["execution_attempt_count"],
        },
        db=conn,
    )
    create_notification(
        recipient_id=updated["created_by_user_id"],
        event_type=NotificationEvents.SUBMISSION_EXECUTION_INTERRUPTED,
        title=f"Submission execution interrupted: {updated['title']}",
        body=error_message,
        resource_type="submission",
        resource_id=str(submission_id),
        action_url=f"/submissions/{submission_id}",
        db_conn=conn,
    )
    return _serialise(updated)


def recover_interrupted_executions(conn) -> dict[str, int]:
    """Find every submission in EXECUTING and move it to
    EXECUTION_INTERRUPTED. Called from the FastAPI lifespan startup so a
    restart while a Seqsender subprocess was running doesn't leave the
    DB row in a state nothing can transition out of.

    Returns a counter dict ``{"recovered": <n>}`` for the lifespan code
    to log.
    """
    rows = execute_query(
        """
        SELECT id FROM submissions
         WHERE status = 'EXECUTING' AND is_deleted = FALSE
        """,
        conn=conn,
    )
    recovered = 0
    for row in rows:
        try:
            mark_execution_interrupted(
                submission_id=row["id"],
                actor_id=None,
                conn=conn,
            )
            recovered += 1
        except HTTPException:
            # Another path already moved this row out of EXECUTING (e.g.
            # a concurrent retry). Idempotent skip — count only the
            # rows we actually transitioned.
            logger.debug(
                "recover_interrupted_executions: submission %s no longer EXECUTING; skipping",
                row["id"],
            )
    return {"recovered": recovered}


__all__ = [
    "VALID_REPOSITORIES",
    "VALID_STATUSES",
    "AccessionEntry",
    "SampleValidationIssue",
    "SubmissionValidationResult",
    "add_samples_to_submission",
    "create_submission",
    "get_submission",
    "list_submission_samples",
    "list_submissions",
    "mark_execution_completed",
    "mark_execution_failed",
    "mark_execution_interrupted",
    "mark_execution_queued",
    "mark_execution_retried",
    "mark_package_generated",
    "mark_rejected",
    "mark_submitted",
    "parse_accessions_tsv",
    "recover_interrupted_executions",
    "register_accessions",
    "remove_samples_from_submission",
    "soft_delete_submission",
    "update_submission",
    "validate_submission_readiness",
    "withdraw_submission",
]
