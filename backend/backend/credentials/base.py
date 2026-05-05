# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Credential backend abstract base and exception hierarchy."""

from __future__ import annotations

from abc import ABC, abstractmethod


class CredentialError(Exception):
    """Base class for credential-system failures.

    Raised for: insecure file permissions, malformed YAML, unknown backend,
    GCP API errors, missing config required to construct a backend, etc.
    """


class CredentialNotFoundError(CredentialError):
    """Raised when a requested credential is not present in the backend.

    `get_optional()` swallows this and returns None; `get()` re-raises.
    Other CredentialError subclasses are NOT swallowed by `get_optional()`.
    """


class CredentialBackend(ABC):
    """Abstract credential source. Implementations must be safe to share
    across threads — facades cache values per-process and may call from
    multiple call sites concurrently."""

    @abstractmethod
    def get(self, key: str) -> str:
        """Return the credential value for `key` as a string.

        Raises:
            CredentialNotFoundError: key is not present.
            CredentialError: any other failure (permission denied, malformed
                store, network error, etc.).
        """

    @abstractmethod
    def list_keys(self) -> list[str]:
        """Return the list of credential keys currently set in this backend.

        Used for diagnostics. Implementations may scope this to known keys
        rather than enumerating an unbounded namespace.
        """
