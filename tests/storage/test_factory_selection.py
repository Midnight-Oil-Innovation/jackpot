"""The storage selection matrix (B-STORAGE-LOCAL-FALLTHROUGH).

Which backend an operator gets was previously a property nobody could
see: `factory.py` inferred it from whether `storage_endpoint` was empty,
so `storage_backend="local"` — the ScenarioDefaults default, chosen by
the CI and tribal-sovereignty scenarios — produced an S3 client aimed at
https://storage.googleapis.com. Three defensible steps composed into an
install that reached for Google Cloud Storage when the operator asked for
a directory on disk.

These tests assert the mapping directly, so the composition can no longer
hide.
"""

from unittest.mock import patch

import pytest

import backend.storage.factory as factory
from backend.config import Settings
from backend.storage.local import LocalFSStorageBackend
from backend.storage.s3 import S3StorageBackend

PRESIGN = "x" * 64


def _backend_for(**overrides):
    """Build a backend from explicitly pinned settings.

    Every selection-relevant field is stated here rather than inherited
    from the environment: tests/conftest.py sets STORAGE_ENDPOINT for the
    whole session, so a bare Settings() silently reports S3 and the
    legacy-inference test passed for the wrong reason on the first run.
    A matrix test whose inputs come from ambient config tests the ambient
    config.
    """
    pinned = {
        "storage_backend": None,
        "storage_endpoint": None,
        "local_storage_root": "",
        "local_storage_public_url_base": "",
    }
    settings = Settings(**{**pinned, **overrides})
    with (
        patch.object(factory, "get_settings", lambda: settings),
        patch.object(factory.credentials, "get", lambda *a, **k: PRESIGN),
        patch.object(factory.credentials, "get_optional", lambda *a, **k: None),
    ):
        factory.clear_cache()
        try:
            return factory.get_storage_backend()
        finally:
            factory.clear_cache()


def test_local_selects_the_filesystem_backend(tmp_path):
    """The bug. Asking for local storage must not yield a cloud client."""
    backend = _backend_for(storage_backend="local", local_storage_root=str(tmp_path))
    assert isinstance(backend, LocalFSStorageBackend), (
        f"storage_backend='local' produced {type(backend).__name__}"
    )


def test_local_never_points_at_a_cloud_endpoint(tmp_path):
    """Pins the sovereignty case: no Google endpoint anywhere in the object."""
    backend = _backend_for(storage_backend="local", local_storage_root=str(tmp_path))
    blob = repr(vars(backend))
    assert "googleapis.com" not in blob
    assert "amazonaws.com" not in blob


@pytest.mark.parametrize(
    ("kwargs", "expected_name"),
    [
        ({"storage_backend": "minio", "storage_endpoint": "http://minio:9000"}, "s3"),
        ({"storage_backend": "s3", "storage_endpoint": "https://s3.example.org"}, "s3"),
        ({"storage_backend": "gcs"}, "gcs"),
    ],
)
def test_remote_backends_keep_their_existing_mapping(kwargs, expected_name):
    backend = _backend_for(**kwargs)
    assert isinstance(backend, S3StorageBackend)
    assert backend.backend_name == expected_name


def test_unset_backend_preserves_the_legacy_inference():
    """Deployments predating STORAGE_BACKEND must not change behaviour.

    Endpoint set means S3-compatible; endpoint empty means GCS via HMAC.
    That inference is exactly what caused the bug, so it survives only as
    a compatibility path for a config that never names a backend.
    """
    assert _backend_for(storage_endpoint="http://minio:9000").backend_name == "s3"
    assert _backend_for().backend_name == "gcs"


def test_local_without_a_configured_root_fails_loudly(monkeypatch):
    """Silence is what made the original bug expensive.

    An operator who selects local storage and configures no root must get
    an error naming the setting, not a surprise default under the CWD.
    """
    with pytest.raises(Exception) as exc:
        _backend_for(storage_backend="local", local_storage_root="")
    assert "local_storage_root" in str(exc.value)
