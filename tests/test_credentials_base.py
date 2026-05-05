"""C-1: error class hierarchy and registry shape."""

from __future__ import annotations

from backend.credentials.base import (
    CredentialBackend,
    CredentialError,
    CredentialNotFoundError,
)
from backend.credentials.registry import REQUIRED_CREDENTIALS, CredentialSpec, get_spec


def test_not_found_is_credential_error_subclass() -> None:
    assert issubclass(CredentialNotFoundError, CredentialError)


def test_credential_backend_is_abstract() -> None:
    # Cannot instantiate the base class directly.
    try:
        CredentialBackend()  # type: ignore[abstract]
    except TypeError:
        return
    raise AssertionError("CredentialBackend should be abstract")


def test_required_credentials_registry_shape() -> None:
    keys = [spec.key for spec in REQUIRED_CREDENTIALS]
    # C-1 baseline (6) + I-3a backend-execution credentials (4).
    assert keys == [
        "jwt_signing_key",
        "google_oauth_client_secret",
        "s3_storage_secret_key",
        "gcs_hmac_access_key",
        "gcs_hmac_secret",
        "local_storage_presign_secret",
        "ncbi_submission_username",
        "ncbi_submission_password",
        "ena_webin_username",
        "ena_webin_password",
    ]


def test_credential_specs_are_frozen_dataclasses() -> None:
    spec = REQUIRED_CREDENTIALS[0]
    assert isinstance(spec, CredentialSpec)
    try:
        spec.key = "x"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("CredentialSpec should be frozen")


def test_legacy_env_names_are_tuples() -> None:
    for spec in REQUIRED_CREDENTIALS:
        assert isinstance(spec.legacy_env_names, tuple), spec.key


def test_get_spec_known_and_unknown() -> None:
    assert get_spec("jwt_signing_key") is not None
    assert get_spec("unknown_credential") is None
