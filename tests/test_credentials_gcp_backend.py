"""C-1: GCPSecretManagerBackend secret-name shape and exception mapping.

Tests are fully mocked. No GCP calls are made. The
test_credentials_gcp_backend_integration.py companion test runs against
a real GCP project when the operator opts in via env var.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from google.api_core import exceptions as gax_exceptions

from backend.credentials.base import CredentialError, CredentialNotFoundError
from backend.credentials.gcp_backend import GCPSecretManagerBackend


def _backend_with_mock_client():
    backend = GCPSecretManagerBackend(project_id="proj-1", secret_prefix="jackpot-cred-")
    mock_client = MagicMock()
    backend._client = mock_client  # bypass lazy construction
    return backend, mock_client


def test_secret_name_shape():
    backend, client = _backend_with_mock_client()
    response = MagicMock()
    response.payload.data = b"secret-value"
    client.access_secret_version.return_value = response

    backend.get("jwt_signing_key")

    client.access_secret_version.assert_called_once_with(
        name="projects/proj-1/secrets/jackpot-cred-jwt-signing-key/versions/latest"
    )


def test_returns_decoded_value():
    backend, client = _backend_with_mock_client()
    response = MagicMock()
    response.payload.data = b"the-secret"
    client.access_secret_version.return_value = response
    assert backend.get("jwt_signing_key") == "the-secret"


def test_not_found_mapped():
    backend, client = _backend_with_mock_client()
    client.access_secret_version.side_effect = gax_exceptions.NotFound("nope")
    with pytest.raises(CredentialNotFoundError):
        backend.get("jwt_signing_key")


def test_permission_denied_mapped_with_workload_identity_hint():
    backend, client = _backend_with_mock_client()
    client.access_secret_version.side_effect = gax_exceptions.PermissionDenied("denied")
    with pytest.raises(CredentialError) as ei:
        backend.get("jwt_signing_key")
    msg = str(ei.value)
    assert "Workload Identity" in msg
    assert "secretmanager.secretAccessor" in msg
    # Subclasses of CredentialError other than CredentialNotFoundError
    # must NOT be CredentialNotFoundError instances.
    assert not isinstance(ei.value, CredentialNotFoundError)


def test_other_google_api_error_mapped():
    backend, client = _backend_with_mock_client()
    client.access_secret_version.side_effect = gax_exceptions.ServiceUnavailable("503")
    with pytest.raises(CredentialError) as ei:
        backend.get("jwt_signing_key")
    assert not isinstance(ei.value, CredentialNotFoundError)


def test_list_keys_filters_by_prefix_and_reverses_dashes():
    backend, client = _backend_with_mock_client()
    s1 = MagicMock()
    s1.name = "projects/proj-1/secrets/jackpot-cred-jwt-signing-key"
    s2 = MagicMock()
    s2.name = "projects/proj-1/secrets/jackpot-cred-google-oauth-client-secret"
    s3 = MagicMock()
    s3.name = "projects/proj-1/secrets/some-other-secret"
    client.list_secrets.return_value = [s1, s2, s3]
    keys = backend.list_keys()
    assert "jwt_signing_key" in keys
    assert "google_oauth_client_secret" in keys
    assert all("some-other-secret" not in k for k in keys)


def test_list_keys_uses_correct_parent():
    backend, client = _backend_with_mock_client()
    client.list_secrets.return_value = []
    backend.list_keys()
    client.list_secrets.assert_called_once_with(parent="projects/proj-1")


def test_constructor_rejects_blank_project():
    with pytest.raises(CredentialError):
        GCPSecretManagerBackend(project_id="", secret_prefix="jackpot-cred-")


def test_lazy_client_construction():
    """Constructor should not actually call SecretManagerServiceClient()."""
    with patch(
        "backend.credentials.gcp_backend.secretmanager.SecretManagerServiceClient"
    ) as mock_cls:
        backend = GCPSecretManagerBackend(project_id="proj-1", secret_prefix="jackpot-cred-")
        mock_cls.assert_not_called()
        # First call constructs.
        response = MagicMock()
        response.payload.data = b"v"
        instance = mock_cls.return_value
        instance.access_secret_version.return_value = response
        backend.get("k")
        mock_cls.assert_called_once()
