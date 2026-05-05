# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Public credential API.

Use:
    from backend.credentials import credentials
    secret = credentials.get("jwt_signing_key")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.credentials.base import (
    CredentialBackend,
    CredentialError,
    CredentialNotFoundError,
)

if TYPE_CHECKING:
    from backend.credentials.facade import CredentialFacade

# The CredentialFacade is constructed lazily on first use. Tests can swap
# the backing implementation via _set_backend / _reset_backend.
_facade: CredentialFacade | None = None


def _get_facade() -> CredentialFacade:
    global _facade
    if _facade is None:
        from backend.credentials.factory import build_facade

        _facade = build_facade()
    return _facade


def _set_backend(backend: CredentialBackend) -> None:
    """Test-only. Replace the active backend with a custom implementation."""
    global _facade
    from backend.config import get_settings
    from backend.credentials.facade import CredentialFacade

    _facade = CredentialFacade(backend=backend, settings=get_settings())


def _reset_backend() -> None:
    """Test-only. Forget the cached facade so the next call rebuilds it."""
    global _facade
    _facade = None


class _Credentials:
    """Convenience proxy so callers can `from backend.credentials import credentials`
    and call `.get(...)` etc. without thinking about facade construction."""

    def get(self, key: str) -> str:
        return _get_facade().get(key)

    def get_optional(self, key: str) -> str | None:
        return _get_facade().get_optional(key)

    def list_keys(self) -> list[str]:
        return _get_facade().list_keys()

    def invalidate(self, key: str) -> None:
        return _get_facade().invalidate(key)

    def invalidate_all(self) -> None:
        return _get_facade().invalidate_all()

    def validate_required(self) -> None:
        return _get_facade().validate_required()


credentials = _Credentials()


__all__ = [
    "credentials",
    "CredentialBackend",
    "CredentialError",
    "CredentialNotFoundError",
]
