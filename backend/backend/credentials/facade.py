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
        return self._backend

    def get(self, key: str) -> str:
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
        try:
            return self.get(key)
        except CredentialNotFoundError:
            return None

    def list_keys(self) -> list[str]:
        return self._backend.list_keys()

    def invalidate(self, key: str) -> None:
        self._cache.invalidate(key)

    def invalidate_all(self) -> None:
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
