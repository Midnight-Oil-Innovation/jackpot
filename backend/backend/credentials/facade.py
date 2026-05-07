# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""CredentialFacade — wraps a CredentialBackend with caching, audit, and
registry-driven startup validation.

The facade is the object that public callers actually talk to via the
`credentials` proxy in `backend.credentials.__init__`. The split keeps
the public proxy free of business logic and lets tests construct a
facade directly with an InMemoryBackend.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.credentials.base import (
    CredentialBackend,
    CredentialError,
    CredentialNotFoundError,
)
from backend.credentials.cache import CredentialCache
from backend.credentials.registry import REQUIRED_CREDENTIALS

if TYPE_CHECKING:
    from backend.config import Settings


# Audit events for credential reads. These do NOT go through backend.audit
# because credential reads happen outside any DB transaction (startup
# validation, request-time JWT decode, etc.). The DB-bound log_audit()
# helper requires a session. A dedicated stdlib logger keeps the audit
# trail intact in stdout/stderr-aggregated logs.
_audit_logger = logging.getLogger("backend.credentials.audit")

EVENT_READ = "CREDENTIAL_READ"
EVENT_READ_FAILED = "CREDENTIAL_READ_FAILED"


class CredentialFacade:
    def __init__(self, backend: CredentialBackend, settings: Settings) -> None:
        self._backend = backend
        self._settings = settings
        self._cache = CredentialCache(ttl_seconds=settings.credential_cache_ttl_seconds)

    @property
    def backend(self) -> CredentialBackend:
        """Return the underlying backend; useful for tests and diagnostics."""
        return self._backend

    def get(self, key: str) -> str:
        """Read a credential by name through the configured backend.

        Hits the facade's TTL'd cache first; on miss, delegates to
        ``self._backend.get(key)`` and emits a ``CREDENTIAL_READ`` audit
        event to the ``backend.credentials.audit`` stdlib logger.
        Failures emit ``CREDENTIAL_READ_FAILED`` with the backend's
        diagnostic reason. Per Critical Rule 62, all credential reads
        must go through this method (or :meth:`get_optional`).

        Args:
            key: Lowercase credential name as registered in
                :data:`backend.credentials.registry.REQUIRED_CREDENTIALS`.

        Returns:
            The credential value as a string.

        Raises:
            CredentialNotFoundError: The backend does not have a value
                for ``key``. Use :meth:`get_optional` if a missing
                credential is acceptable to the caller.
            CredentialError: The backend errored while fetching (e.g.
                a GCP Secret Manager API failure or a permission
                error). Audited as ``CREDENTIAL_READ_FAILED``.
        """
        backend_class_name = type(self._backend).__name__

        def _fetch() -> str:
            return self._backend.get(key)

        try:
            value, was_hit = self._cache.get_or_compute(backend_class_name, key, _fetch)
        except CredentialError as exc:
            _audit_logger.warning(
                EVENT_READ_FAILED,
                extra={
                    "event": EVENT_READ_FAILED,
                    "key": key,
                    "backend": backend_class_name,
                    "reason": str(exc),
                },
            )
            raise

        if not was_hit:
            _audit_logger.info(
                EVENT_READ,
                extra={
                    "event": EVENT_READ,
                    "key": key,
                    "backend": backend_class_name,
                },
            )
        return value

    def get_optional(self, key: str) -> str | None:
        """Read a credential, returning ``None`` if it is not configured.

        Wraps :meth:`get` and converts ``CredentialNotFoundError`` into
        a ``None`` return. Other backend errors (auth failure, network
        failure) still propagate as ``CredentialError`` so the caller
        can distinguish "not set" from "broken."

        Args:
            key: Lowercase credential name as registered in
                :data:`backend.credentials.registry.REQUIRED_CREDENTIALS`.

        Returns:
            The credential value, or ``None`` if the backend has no
            entry for ``key``.

        Raises:
            CredentialError: The backend errored while fetching.
        """
        try:
            return self.get(key)
        except CredentialNotFoundError:
            return None

    def list_keys(self) -> list[str]:
        """Return the keys the backend can currently produce.

        For ``EnvBackend`` this is the set of registered credential keys
        whose corresponding env var is set; for ``FileBackend`` it is
        the YAML file's top-level keys; for
        ``GCPSecretManagerBackend`` it is the secrets in the project
        whose name starts with ``credential_gcp_secret_prefix``. The
        return value never contains credential VALUES — only names —
        so it is safe to log for diagnostics.
        """
        return self._backend.list_keys()

    def invalidate(self, key: str) -> None:
        """Drop the cached value for ``key`` so the next read re-fetches.

        Use after a backend-side rotation that should not wait for the
        TTL to expire (e.g. NCBI portal password change).
        """
        self._cache.invalidate(key)

    def invalidate_all(self) -> None:
        """Drop every cached credential so the next reads re-fetch.

        Heavier hammer than :meth:`invalidate`; used after a
        rotation that touched many credentials at once or for tests
        that want a clean cache between cases.
        """
        self._cache.invalidate_all()

    def validate_required(self) -> None:
        """Verify every required credential is readable.

        Raises:
            RuntimeError: if any required credential is missing. The
                message lists every missing key with its diagnostic detail.
        """
        missing: list[tuple[str, str]] = []
        for spec in REQUIRED_CREDENTIALS:
            if not spec.required_predicate(self._settings):
                continue
            try:
                self.get(spec.key)
            except CredentialNotFoundError as exc:
                missing.append((spec.key, str(exc)))
        if missing:
            details = "\n".join(f"  - {k}: {msg}" for k, msg in missing)
            raise RuntimeError(
                f"Missing required credentials:\n{details}\n"
                f"Configure them via the "
                f"'{self._settings.credential_backend}' backend."
            )
