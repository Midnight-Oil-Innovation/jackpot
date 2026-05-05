# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Factory for constructing the singleton CredentialFacade from settings."""

from __future__ import annotations

from pathlib import Path

from backend.config import get_settings
from backend.credentials.base import CredentialBackend, CredentialError
from backend.credentials.facade import CredentialFacade


def _build_backend(settings) -> CredentialBackend:
    backend_name = settings.credential_backend
    if backend_name == "env":
        from backend.credentials.env_backend import EnvVarBackend

        return EnvVarBackend()
    if backend_name == "file":
        from backend.credentials.file_backend import FileBackend

        path = str(Path(settings.credential_file_path).expanduser())
        return FileBackend(path=path)
    if backend_name == "gcp_secret_manager":
        from backend.credentials.gcp_backend import GCPSecretManagerBackend

        return GCPSecretManagerBackend(
            project_id=settings.gcp_project_id,
            secret_prefix=settings.credential_gcp_secret_prefix,
        )
    raise CredentialError(
        f"Unknown credential backend: '{backend_name}'. "
        f"Valid options: 'env', 'file', 'gcp_secret_manager'."
    )


def build_facade() -> CredentialFacade:
    settings = get_settings()
    backend = _build_backend(settings)
    return CredentialFacade(backend=backend, settings=settings)
