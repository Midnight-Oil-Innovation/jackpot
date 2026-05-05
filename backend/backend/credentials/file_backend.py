# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""YAML-file credential backend.

The file is a flat top-level mapping of `key: value`. Nested structures
and key prefixes are not supported in v1.

File-permission policy: any group or world bit set causes the constructor
to fail-closed with a clear chmod hint. If the file does not exist, the
backend instantiates fine in degraded mode (every `get()` raises
CredentialNotFoundError) so that startup validation can produce the right
error message rather than the constructor blowing up first.

The backend re-parses the YAML on every read so downstream cache
invalidation reflects file edits without process restart of the cache.
Process restart is still required for the backend itself if the file is
created where it did not previously exist (constructor caches the
permissions check).
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from backend.credentials.base import (
    CredentialBackend,
    CredentialError,
    CredentialNotFoundError,
)


class FileBackend(CredentialBackend):
    """Credential backend that reads a flat YAML mapping from disk."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        if self._path.exists():
            self._enforce_secure_permissions()

    def _enforce_secure_permissions(self) -> None:
        mode = os.stat(self._path).st_mode & 0o777
        if mode & 0o077:
            raise CredentialError(
                f"Credential file '{self._path}' has insecure permissions "
                f"(mode {mode:04o}). Run: chmod 600 '{self._path}'"
            )

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            with open(self._path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise CredentialError(f"Could not parse credential file '{self._path}': {exc}") from exc
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise CredentialError(
                f"Credential file '{self._path}' must contain a top-level "
                f"mapping; got {type(data).__name__}."
            )
        return {str(k): str(v) for k, v in data.items()}

    def get(self, key: str) -> str:
        data = self._load()
        if key not in data:
            raise CredentialNotFoundError(f"Credential '{key}' not found in file '{self._path}'")
        return data[key]

    def list_keys(self) -> list[str]:
        return list(self._load().keys())
