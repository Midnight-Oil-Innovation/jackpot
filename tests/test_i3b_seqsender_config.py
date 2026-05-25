"""I-3b: Seqsender config-file generation."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

import pytest
import yaml

from backend.credentials import _reset_backend, _set_backend
from backend.credentials.base import CredentialNotFoundError
from backend.credentials.test_helpers import InMemoryBackend
from backend.submission_executors.seqsender import write_seqsender_config


@pytest.fixture
def populated_credentials():
    backend = InMemoryBackend(
        {
            "ncbi_submission_username": "submitter@example.org",
            "ncbi_submission_password": "supersecret-ncbi",
        }
    )
    _set_backend(backend)
    yield backend
    _reset_backend()


def test_ncbi_config_has_username_password(populated_credentials):
    path, values = write_seqsender_config(submission_id=42, target_repo="NCBI")
    try:
        assert path.exists()
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        ncbi = data["Submission"]["NCBI"]
        assert ncbi["Username"] == "submitter@example.org"
        assert ncbi["Password"] == "supersecret-ncbi"
        assert ncbi["Spuid_Namespace"] == "jackpot"
    finally:
        path.unlink()


def test_returned_credential_values_match_actual_values(populated_credentials):
    path, values = write_seqsender_config(submission_id=42, target_repo="NCBI")
    try:
        assert "submitter@example.org" in values
        assert "supersecret-ncbi" in values
        assert len(values) == 2
    finally:
        path.unlink()


def test_config_file_mode_is_0600(populated_credentials):
    path, _ = write_seqsender_config(submission_id=42, target_repo="NCBI")
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
        assert mode == 0o600, f"expected 0o600, got {oct(mode)}"
    finally:
        path.unlink()


def test_config_path_is_outside_any_working_dir(populated_credentials):
    """The credential-bearing config must NOT be written inside the
    per-execution working directory. If it were, any routine working-dir
    tarball or upload would carry the credentials."""
    path, _ = write_seqsender_config(submission_id=42, target_repo="NCBI")
    try:
        system_temp = Path(tempfile.gettempdir()).resolve()
        assert system_temp in path.resolve().parents
    finally:
        path.unlink()


def test_config_filename_includes_submission_id(populated_credentials):
    """Diagnostic aid: if a config file ever does get left on disk, the
    submission id in the filename makes it easy to identify."""
    path, _ = write_seqsender_config(submission_id=99, target_repo="NCBI")
    try:
        assert "99" in path.name
    finally:
        path.unlink()


def test_target_repo_lowercase_accepted(populated_credentials):
    """The submissions table stores 'NCBI' uppercase, but the executor
    upcases before passing here. Defensive: accept either."""
    path, _ = write_seqsender_config(submission_id=42, target_repo="ncbi")
    try:
        assert path.exists()
    finally:
        path.unlink()


def test_unsupported_repo_raises_value_error(populated_credentials):
    for bad in ("ENA", "GISAID_EPICOV", "DDBJ", "totally-fake"):
        with pytest.raises(ValueError) as ei:
            write_seqsender_config(submission_id=42, target_repo=bad)
        assert "NCBI" in str(ei.value)


def test_missing_credential_propagates(populated_credentials):
    populated_credentials.remove("ncbi_submission_password")
    with pytest.raises(CredentialNotFoundError):
        write_seqsender_config(submission_id=42, target_repo="NCBI")


def test_yaml_is_well_formed(populated_credentials):
    path, _ = write_seqsender_config(submission_id=42, target_repo="NCBI")
    try:
        # Round-trip through yaml.safe_load — must not raise.
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "Submission" in data
    finally:
        path.unlink()
