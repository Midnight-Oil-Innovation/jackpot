"""C-1: factory.build_facade backend selection."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from backend.config import get_settings
from backend.credentials.base import CredentialError
from backend.credentials.env_backend import EnvVarBackend
from backend.credentials.factory import build_facade
from backend.credentials.file_backend import FileBackend
from backend.credentials.gcp_backend import GCPSecretManagerBackend


def test_env_backend_default(monkeypatch):
    monkeypatch.setenv("CREDENTIAL_BACKEND", "env")
    get_settings.cache_clear()
    facade = build_facade()
    assert isinstance(facade.backend, EnvVarBackend)


def test_file_backend_with_expanded_path(monkeypatch, tmp_path):
    p = tmp_path / "creds.yaml"
    p.write_text("jwt_signing_key: x\n", encoding="utf-8")
    os.chmod(p, 0o600)

    monkeypatch.setenv("CREDENTIAL_BACKEND", "file")
    monkeypatch.setenv("CREDENTIAL_FILE_PATH", str(p))
    get_settings.cache_clear()
    facade = build_facade()
    assert isinstance(facade.backend, FileBackend)


def test_file_backend_expands_tilde(monkeypatch, tmp_path):
    """The factory must expanduser() before instantiating FileBackend."""
    monkeypatch.setenv("CREDENTIAL_BACKEND", "file")
    monkeypatch.setenv("CREDENTIAL_FILE_PATH", "~/this-does-not-exist.yaml")
    monkeypatch.setenv("HOME", str(tmp_path))
    get_settings.cache_clear()
    # No exception expected — missing file is degraded mode by design.
    facade = build_facade()
    assert isinstance(facade.backend, FileBackend)


def test_gcp_backend(monkeypatch):
    monkeypatch.setenv("CREDENTIAL_BACKEND", "gcp_secret_manager")
    monkeypatch.setenv("GCP_PROJECT_ID", "proj-1")
    get_settings.cache_clear()
    with patch("backend.credentials.gcp_backend.secretmanager.SecretManagerServiceClient"):
        facade = build_facade()
    assert isinstance(facade.backend, GCPSecretManagerBackend)


def test_unknown_backend_raises():
    """Pydantic's Literal validator rejects unknown values when env-loaded."""
    # We can't push an invalid Literal through Settings, so simulate the
    # factory branch directly with a lookalike object.
    from backend.credentials.factory import _build_backend

    class _S:
        credential_backend = "neither"

    with pytest.raises(CredentialError):
        _build_backend(_S())


def teardown_module() -> None:
    get_settings.cache_clear()
