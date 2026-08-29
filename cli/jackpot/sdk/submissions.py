"""
jackpot.sdk.submissions
~~~~~~~~~~~~~~~~~~~~~~~
SubmissionsModule — manage submissions to NCBI / GISAID / ENA / DDBJ.

Accessed via ``session.submissions``::

    sub = session.submissions.create(
        title="MA-2026-W12",
        target_repository="NCBI",
        lab_id=1,
        sample_ids=[101, 102, 103],
    )
    session.submissions.add_samples(sub["id"], [104])
    session.submissions.validate(sub["id"])
    session.submissions.generate(sub["id"])
    session.submissions.execute(sub["id"])  # I-3c — backend execution

The 13 lifecycle methods mirror the I-2 router endpoints. The 3
I-3c additions (``execute``, ``retry_execution``, ``execution_logs``)
talk to the I-3b backend executor via the I-3c REST surface.
"""

from __future__ import annotations

from jackpot.core.client import JACKPOTClient


class SubmissionsModule:
    """SDK module for the full submission lifecycle.

    Constructed eagerly by :class:`jackpot.sdk.session.Session`. All
    methods return parsed dicts unwrapped from the standard JACKPOT
    response envelope; on errors the underlying client raises typed
    :mod:`jackpot.core.exceptions` (``ConflictError`` for 409,
    ``NotFoundError`` for 404, etc.).
    """

    _BASE = "/api/v1/submissions"

    def __init__(self, client: JACKPOTClient) -> None:
        self._client = client

    # ── create / read / update / delete ────────────────────────────

    def create(
        self,
        *,
        title: str,
        target_repository: str,
        lab_id: int,
        sample_ids: list[int],
        description: str | None = None,
        bioproject_accession: str | None = None,
        release_date: str | None = None,
    ) -> dict:
        """Create a DRAFT submission. Returns the new row."""
        body: dict = {
            "title": title,
            "target_repository": target_repository,
            "lab_id": lab_id,
            "sample_ids": sample_ids,
        }
        if description is not None:
            body["description"] = description
        if bioproject_accession is not None:
            body["bioproject_accession"] = bioproject_accession
        if release_date is not None:
            body["release_date"] = release_date
        result = self._client.post(f"{self._BASE}/", json=body)
        return result if isinstance(result, dict) else {}

    def list(
        self,
        *,
        lab_id: int | None = None,
        status: str | None = None,
        target_repository: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> list[dict]:
        """List submissions. Returns the rows array (pagination metadata
        is dropped — call the REST endpoint directly if you need it)."""
        params: dict = {"page": page, "per_page": per_page}
        if lab_id is not None:
            params["lab_id"] = lab_id
        if status is not None:
            params["status"] = status
        if target_repository is not None:
            params["target_repository"] = target_repository
        body = self._client.get(f"{self._BASE}/", params=params)
        if isinstance(body, list):
            return body
        return body.get("data", body) if isinstance(body, dict) else []

    def get(self, submission_id: int) -> dict:
        """Retrieve a single submission with attached samples."""
        result = self._client.get(f"{self._BASE}/{submission_id}")
        return result if isinstance(result, dict) else {}

    def update(self, submission_id: int, **fields) -> dict:
        """Patch updatable fields on a submission. Server-side rules
        decide which fields are mutable in which states (e.g. target
        repository locks once the package is generated)."""
        result = self._client.patch(f"{self._BASE}/{submission_id}", json=fields)
        return result if isinstance(result, dict) else {}

    def delete(self, submission_id: int) -> dict:
        """Soft-delete the submission (marks ``is_archived=TRUE``)."""
        result = self._client.delete(f"{self._BASE}/{submission_id}")
        return result if isinstance(result, dict) else {}

    # ── samples + validation + package ────────────────────────────

    def add_samples(self, submission_id: int, sample_ids: list[int]) -> dict:
        result = self._client.post(
            f"{self._BASE}/{submission_id}/samples",
            json={"sample_ids": sample_ids},
        )
        return result if isinstance(result, dict) else {}

    def remove_samples(self, submission_id: int, sample_ids: list[int]) -> dict:
        # The router's DELETE accepts a JSON body listing sample IDs.
        # ``JACKPOTClient.delete`` doesn't take a body in v1 — fall back
        # to an explicit httpx request through the session client. The
        # number of bulk-removal call sites is tiny so a direct httpx
        # request keeps the SDK shape unchanged for everyone else.
        import httpx

        response = httpx.request(
            "DELETE",
            f"{self._client.api_url}{self._BASE}/{submission_id}/samples",
            json={"sample_ids": sample_ids},
            headers={
                "Authorization": self._client._headers["Authorization"],
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
        )
        result = self._client._unwrap(response)
        return result if isinstance(result, dict) else {}

    def validate(self, submission_id: int) -> dict:
        result = self._client.post(f"{self._BASE}/{submission_id}/validate")
        return result if isinstance(result, dict) else {}

    def generate(self, submission_id: int, *, copy_files: bool = False) -> dict:
        result = self._client.post(
            f"{self._BASE}/{submission_id}/generate",
            json={"copy_files": copy_files},
        )
        return result if isinstance(result, dict) else {}

    def mark_submitted(self, submission_id: int) -> dict:
        result = self._client.post(f"{self._BASE}/{submission_id}/mark-submitted")
        return result if isinstance(result, dict) else {}

    def register_accessions(
        self,
        submission_id: int,
        accessions: list[dict],
    ) -> dict:
        """Record accessions returned by the repository. Inline JSON
        form; pass an ``AccessionEntry``-shaped dict per sample."""
        result = self._client.post(
            f"{self._BASE}/{submission_id}/register-accessions",
            json={"accessions": accessions},
        )
        return result if isinstance(result, dict) else {}

    def mark_rejected(self, submission_id: int, reason: str) -> dict:
        result = self._client.post(
            f"{self._BASE}/{submission_id}/mark-rejected",
            json={"reason": reason},
        )
        return result if isinstance(result, dict) else {}

    def withdraw(self, submission_id: int, reason: str) -> dict:
        result = self._client.post(
            f"{self._BASE}/{submission_id}/withdraw",
            json={"reason": reason},
        )
        return result if isinstance(result, dict) else {}

    # ── I-3c: backend execution ───────────────────────────────────

    def execute(self, submission_id: int) -> dict:
        """Queue a generated submission for backend execution.

        Returns the updated row with ``status=EXECUTING``. Raises
        :class:`ConflictError` on a 409 from the pre-flight gates
        (``BACKEND_EXECUTION_DISABLED``, ``REPO_NOT_ENABLED``,
        ``REPO_NOT_SUPPORTED``, ``INVALID_STATE``); the exception's
        ``message`` carries the operator-friendly explanation. Raises
        :class:`JACKPOTError` on a 400 ``MISSING_CREDENTIALS``.
        """
        result = self._client.post(f"{self._BASE}/{submission_id}/execute")
        return result if isinstance(result, dict) else {}

    def retry_execution(self, submission_id: int) -> dict:
        """Re-queue a submission in EXECUTION_FAILED or
        EXECUTION_INTERRUPTED state. Same error semantics as
        :meth:`execute` except ``INVALID_STATE`` covers different states."""
        result = self._client.post(f"{self._BASE}/{submission_id}/retry-execution")
        return result if isinstance(result, dict) else {}

    def execution_logs(self, submission_id: int) -> list[dict]:
        """Return the list of per-attempt execution-log entries.

        Empty list when no executions have been attempted. Each entry:
        ``{"attempt", "log_uri", "log_view_url", "started_at",
        "completed_at", "exit_status"}``.
        """
        body = self._client.get(f"{self._BASE}/{submission_id}/execution-logs")
        # Server returns ``{"submission_id": ..., "entries": [...]}``;
        # the entries array is the useful surface for callers.
        if isinstance(body, dict):
            return list(body.get("entries", []))
        return []
