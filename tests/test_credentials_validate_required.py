"""C-1: facade.validate_required against the registry's predicates."""

from __future__ import annotations

import pytest

from backend.config import Settings
from backend.credentials.facade import CredentialFacade
from backend.credentials.test_helpers import InMemoryBackend


def _facade(backend: InMemoryBackend, **settings_overrides) -> CredentialFacade:
    base = {
        "env": "local",
        "storage_endpoint": "http://localhost:9000",
        "credential_cache_ttl_seconds": 0,
    }
    base.update(settings_overrides)
    settings = Settings(**base)
    return CredentialFacade(backend=backend, settings=settings)


def test_all_required_present_no_raise():
    backend = InMemoryBackend(
        {
            "jwt_signing_key": "x",
            "s3_storage_secret_key": "y",
        }
    )
    _facade(backend).validate_required()  # no raise


def test_one_missing_raises_with_key_in_message():
    backend = InMemoryBackend({"s3_storage_secret_key": "y"})
    facade = _facade(backend)
    with pytest.raises(RuntimeError) as ei:
        facade.validate_required()
    assert "jwt_signing_key" in str(ei.value)


def test_multiple_missing_listed():
    backend = InMemoryBackend()
    facade = _facade(backend)
    with pytest.raises(RuntimeError) as ei:
        facade.validate_required()
    msg = str(ei.value)
    assert "jwt_signing_key" in msg
    assert "s3_storage_secret_key" in msg


def test_s3_secret_not_required_without_storage_endpoint():
    backend = InMemoryBackend({"jwt_signing_key": "x"})
    facade = _facade(backend, storage_endpoint=None, env="local")
    facade.validate_required()  # no raise


def test_gcs_hmac_required_in_gcp_without_endpoint():
    backend = InMemoryBackend({"jwt_signing_key": "x"})
    facade = _facade(
        backend,
        env="gcp",
        storage_endpoint=None,
        google_oauth_client_id="cid",
    )
    with pytest.raises(RuntimeError) as ei:
        facade.validate_required()
    msg = str(ei.value)
    assert "gcs_hmac_access_key" in msg
    assert "gcs_hmac_secret" in msg
    assert "google_oauth_client_secret" in msg


def test_gcs_hmac_not_required_when_endpoint_set():
    backend = InMemoryBackend({"jwt_signing_key": "x", "s3_storage_secret_key": "y"})
    facade = _facade(backend, env="gcp", storage_endpoint="http://minio:9000")
    # google_oauth_client_secret is still required in env=gcp, so we add it
    backend.set("google_oauth_client_secret", "GOCSPX-test")
    facade.validate_required()  # no raise


def test_local_storage_presign_secret_not_required():
    backend = InMemoryBackend({"jwt_signing_key": "x", "s3_storage_secret_key": "y"})
    facade = _facade(backend)
    facade.validate_required()  # no raise even though presign_secret missing


def test_error_mentions_configured_backend():
    backend = InMemoryBackend()
    facade = _facade(backend)
    with pytest.raises(RuntimeError) as ei:
        facade.validate_required()
    # Default credential_backend is 'env'.
    assert "'env'" in str(ei.value)
