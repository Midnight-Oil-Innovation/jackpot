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
import backend.storage.gcs as gcs_mod
from backend.config import Settings
from backend.storage.exceptions import StorageError
from backend.storage.gcs import GCSStorageBackend
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


def test_local_without_a_configured_root_fails_loudly():
    """Silence is what made the original bug expensive.

    An operator who selects local storage and configures no root must get
    an error naming the setting, not a surprise default under the CWD.
    Pinned to StorageError specifically: a bare `Exception` would also pass
    on an ImportError or a signature change, which is not what this asserts.
    """
    with pytest.raises(StorageError, match="local_storage_root"):
        _backend_for(storage_backend="local", local_storage_root="")


class TestUriProvenance:
    """The same predicate lived in three places; only the factory was fixed.

    `get_uri_prefix()` inferred `gs` from an empty `storage_endpoint`, so a
    local install wrote bytes to disk and recorded
    `gs://jackpot-staging/<key>` against the sample — wrong provenance
    persisted to the database, which is worse than a wrong client. For a
    sovereignty deployment it claims data sits in Google's cloud when it
    never left the building.

    Critical Rule 73: the fix is one resolver the call sites share, not a
    third copy that happens to agree today.
    """

    def test_local_storage_never_reports_a_cloud_uri(self, tmp_path):
        backend = _backend_for(storage_backend="local", local_storage_root=str(tmp_path))
        uri = backend.get_uri("some/key.fastq.gz")
        assert uri.startswith("file://"), uri
        assert "gs://" not in uri and "s3://" not in uri

    def test_gcs_backend_reports_gs_not_s3(self):
        """S3StorageBackend serves GCS via HMAC, but the URI must say gs://.

        It hardcoded s3:// regardless of backend_name, disagreeing with the
        get_uri_prefix() that call sites actually used — a third answer to
        the same question.
        """
        backend = _backend_for(storage_backend="gcs")
        assert backend.get_uri("k").startswith("gs://")

    def test_s3_backend_reports_s3(self):
        backend = _backend_for(storage_backend="minio", storage_endpoint="http://minio:9000")
        assert backend.get_uri("k").startswith("s3://")


class TestNativeGcsBackend:
    """B-STORAGE-DEAD-BACKENDS — wired, not deleted, and here is the reason.

    The S3-over-HMAC path cannot authenticate with Application Default
    Credentials. `botocore` ships no GCP credential provider at all: with
    no keys, boto3 resolves the AWS chain (AWS_* env, ~/.aws, IMDS) and
    finds nothing on a GKE pod using Workload Identity. So that path
    *requires* long-lived static HMAC keys.

    `docs/architecture.md:199` names Workload Identity Federation as the
    cloud-native auth model for Scenario C, and GCSStorageBackend —
    `google.cloud.storage`, already a declared dependency — is the only
    backend that can honour it. That is a reason beyond symmetry, which is
    what the entry asked for before wiring rather than deleting.
    """

    def test_gcs_native_selects_the_google_client(self):
        with patch.object(gcs_mod, "gcs_module") as fake_gcs:
            backend = _backend_for(storage_backend="gcs_native", gcp_project_id="proj")
            assert isinstance(backend, GCSStorageBackend)
        fake_gcs.Client.assert_called_once_with(project="proj")

    def test_gcs_native_requires_a_project(self):
        """ADC needs a project; failing at construction beats failing on
        the first upload with a Google-side error."""
        with (
            patch.object(gcs_mod, "gcs_module"),
            pytest.raises(StorageError, match="gcp_project_id"),
        ):
            _backend_for(storage_backend="gcs_native", gcp_project_id="")

    def test_gcs_native_needs_no_hmac_credentials(self):
        """The point of the native path: no static keys.

        The HMAC credentials stay required for storage_backend='gcs', which
        genuinely cannot work without them.
        """
        from backend.credentials.registry import REQUIRED_CREDENTIALS

        hmac_specs = [c for c in REQUIRED_CREDENTIALS if c.key.startswith("gcs_hmac")]
        assert hmac_specs, "expected gcs_hmac_* credential specs"
        for spec in hmac_specs:
            assert not spec.required_predicate(
                Settings(storage_backend="gcs_native", env="gcp", storage_endpoint=None)
            ), f"{spec.key} must not be required on the native path"
            assert spec.required_predicate(
                Settings(storage_backend="gcs", env="gcp", storage_endpoint=None)
            ), f"{spec.key} must stay required on the HMAC path"
            # Behaviour change worth pinning: the old predicate keyed off
            # `not storage_endpoint`, so an explicit gcs backend with an
            # endpoint set was told it needed no keys. It does.
            assert spec.required_predicate(
                Settings(storage_backend="gcs", env="gcp", storage_endpoint="http://x:9000")
            ), f"{spec.key} must be required for an explicit gcs backend"

    def test_gcs_native_reports_gs_uris(self):
        with patch.object(gcs_mod, "gcs_module"):
            backend = _backend_for(storage_backend="gcs_native", gcp_project_id="proj")
        assert backend.get_uri("k").startswith("gs://")
