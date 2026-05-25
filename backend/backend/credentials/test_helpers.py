# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Test-only helpers. Production code MUST NOT import from this module.

The InMemoryBackend lets test fixtures populate credentials directly:

    from backend.credentials.test_helpers import InMemoryBackend
    backend = InMemoryBackend({"jwt_signing_key": "test-key"})
    backend.set("google_oauth_client_secret", "GOCSPX-test")
"""

from __future__ import annotations

from backend.credentials.base import CredentialBackend, CredentialNotFoundError


class InMemoryBackend(CredentialBackend):
    """A backend backed by a plain dict. Tests can populate it directly."""

    def __init__(self, initial: dict[str, str] | None = None) -> None:
        self._data: dict[str, str] = dict(initial or {})

    def get(self, key: str) -> str:
        if key not in self._data:
            raise CredentialNotFoundError(f"Credential '{key}' not present in InMemoryBackend")
        return self._data[key]

    def list_keys(self) -> list[str]:
        return list(self._data.keys())

    def set(self, key: str, value: str) -> None:
        """Test-only convenience to populate the backend."""
        self._data[key] = value

    def remove(self, key: str) -> None:
        """Test-only convenience to delete a credential."""
        self._data.pop(key, None)
