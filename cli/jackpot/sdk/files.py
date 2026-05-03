"""
jackpot.sdk.files
~~~~~~~~~~~~~~~~~
FilesModule — read and modify the file_references registry.

Phase P0f F-9. Mirrors the HTTP surface of ``/api/v1/files/`` so SDK
consumers can list, fetch, promote, and verify files without writing
URL-construction code. The module is a thin wrapper — no business
logic; the backend is the source of truth for transitions and access
control.

Accessed via ``session.files``.
"""

from __future__ import annotations

from jackpot.core.client import JACKPOTClient


class FilesModule:
    """SDK module for file_references operations."""

    def __init__(self, client: JACKPOTClient) -> None:
        self._client = client

    def get(self, file_id: int) -> dict:
        """Return the full ``sample_files`` row plus referencing samples.

        Wraps ``GET /api/v1/files/{file_id}``.
        """
        result = self._client.get(f"/api/v1/files/{file_id}")
        return result if isinstance(result, dict) else {}

    def list(
        self,
        *,
        storage_state: str | None = None,
        sample_id: int | None = None,
        project_id: int | None = None,
        page: int = 1,
        per_page: int = 50,
        sort_by: str = "first_seen_at",
        sort_dir: str = "desc",
    ) -> list[dict]:
        """Paginated, filterable list. Wraps ``GET /api/v1/files/``.

        ``storage_state`` accepts one of ``EXTERNAL`` / ``MANAGED`` /
        ``MIRRORED`` / ``STAGED`` / ``BROKEN``. ``sample_id`` is the
        integer ``samples.id`` (not the human-facing ``sample_id``
        string). The full envelope is unwrapped to the data array; the
        caller can re-call to flip pages.
        """
        params: dict = {
            "page": page,
            "per_page": per_page,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
        }
        if storage_state is not None:
            params["storage_state"] = storage_state
        if sample_id is not None:
            params["sample_id"] = sample_id
        if project_id is not None:
            params["project_id"] = project_id
        result = self._client.get("/api/v1/files/", params=params)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            data = result.get("data", [])
            return data if isinstance(data, list) else []
        return []

    def promote(
        self,
        file_id: int,
        to: str,
        *,
        retention_policy: str = "STANDARD",
    ) -> dict:
        """Schedule a promote job. Wraps ``POST /api/v1/files/{id}/promote``.

        Returns the 202-Accepted job descriptor with ``job_id``,
        ``current_state``, ``target_state``, and ``estimated_seconds``.
        Use :meth:`get_job` to poll for completion.
        """
        body = {"to": to.upper(), "retention_policy": retention_policy.upper()}
        result = self._client.post(f"/api/v1/files/{file_id}/promote", json=body)
        return result if isinstance(result, dict) else {}

    def get_job(self, job_id: str) -> dict:
        """Look up a promote job's status. Wraps ``GET /api/v1/files/jobs/{id}``.

        Returns ``{"status": ..., ...}`` while the job is in the
        in-memory tracker. The endpoint returns 404 (raised as
        :class:`NotFoundError` by the underlying client) when the job
        is unknown to the API instance.
        """
        result = self._client.get(f"/api/v1/files/jobs/{job_id}")
        return result if isinstance(result, dict) else {}

    def verify(self, file_id: int) -> dict:
        """Force a synchronous re-verify. Wraps ``POST /api/v1/files/{id}/verify``.

        Returns the post-verify row snapshot (``storage_state``,
        ``last_verification_status``, ``last_verified_at``).
        """
        result = self._client.post(f"/api/v1/files/{file_id}/verify", json={})
        return result if isinstance(result, dict) else {}
