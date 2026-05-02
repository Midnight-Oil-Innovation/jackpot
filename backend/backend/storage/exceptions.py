# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Typed exceptions for the storage layer.

All storage backends raise these exception types instead of backend-specific
exceptions. This allows callers to handle storage errors uniformly regardless
of which backend is configured.
"""

from __future__ import annotations


class StorageError(Exception):
    """Base exception for all storage-related errors."""

    def __init__(self, message: str, *, key: str | None = None, backend: str | None = None) -> None:
        super().__init__(message)
        self.key = key
        self.backend = backend

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.backend:
            parts.append(f"backend={self.backend}")
        if self.key:
            parts.append(f"key={self.key}")
        return " | ".join(parts)


class StorageObjectNotFoundError(StorageError):
    """Raised when an operation references an object that does not exist."""


class StoragePermissionError(StorageError):
    """Raised when the storage backend rejects an operation due to permissions."""


class StorageConfigurationError(StorageError):
    """Raised when storage configuration is invalid or incomplete."""


class StorageBackendUnavailableError(StorageError):
    """Raised when the storage backend is unreachable.

    This is distinct from a permission error or a missing object - it means
    the underlying service itself could not be contacted.
    """
