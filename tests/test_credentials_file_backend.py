"""C-1: FileBackend YAML load, permissions, malformed input, layering."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.credentials.base import CredentialError, CredentialNotFoundError
from backend.credentials.file_backend import FileBackend


def _write_secure(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o600)


def test_successful_yaml_read(tmp_path):
    p = tmp_path / "creds.yaml"
    _write_secure(p, "jwt_signing_key: abc123\n")
    assert FileBackend(path=str(p)).get("jwt_signing_key") == "abc123"


def test_missing_file_get_raises_not_found(tmp_path):
    p = tmp_path / "missing.yaml"
    backend = FileBackend(path=str(p))  # no error
    with pytest.raises(CredentialNotFoundError):
        backend.get("jwt_signing_key")


def test_insecure_permissions_constructor_raises(tmp_path):
    p = tmp_path / "creds.yaml"
    p.write_text("jwt_signing_key: x\n", encoding="utf-8")
    os.chmod(p, 0o644)
    with pytest.raises(CredentialError) as ei:
        FileBackend(path=str(p))
    assert "chmod 600" in str(ei.value)


def test_malformed_yaml_raises(tmp_path):
    p = tmp_path / "creds.yaml"
    _write_secure(p, "this: is: not: valid yaml\n  at: all\n - mixed\n")
    with pytest.raises(CredentialError):
        FileBackend(path=str(p)).get("jwt_signing_key")


def test_top_level_must_be_mapping(tmp_path):
    p = tmp_path / "creds.yaml"
    _write_secure(p, "- a\n- b\n")
    with pytest.raises(CredentialError):
        FileBackend(path=str(p)).get("jwt_signing_key")


def test_list_keys(tmp_path):
    p = tmp_path / "creds.yaml"
    _write_secure(p, "jwt_signing_key: a\nother_key: b\n")
    keys = set(FileBackend(path=str(p)).list_keys())
    assert keys == {"jwt_signing_key", "other_key"}


def test_file_contents_not_cached_at_backend(tmp_path):
    """A second get() after the file mutates reflects the new value.

    The cache lives at the facade layer, not at the backend. Write a
    value, read it back, mutate the file, read again, expect new value.
    """
    p = tmp_path / "creds.yaml"
    _write_secure(p, "jwt_signing_key: first\n")
    backend = FileBackend(path=str(p))
    assert backend.get("jwt_signing_key") == "first"
    _write_secure(p, "jwt_signing_key: second\n")
    assert backend.get("jwt_signing_key") == "second"


def test_missing_key_raises_not_found(tmp_path):
    p = tmp_path / "creds.yaml"
    _write_secure(p, "other_key: present\n")
    with pytest.raises(CredentialNotFoundError):
        FileBackend(path=str(p)).get("jwt_signing_key")
