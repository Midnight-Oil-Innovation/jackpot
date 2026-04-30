# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-present Glen Otero
"""Contract tests applied to every storage backend.

Each backend implementation should pass all of these tests. New backends
added in the future must be added to the parametrize list.
"""

from __future__ import annotations

import io
import secrets
from datetime import timedelta

import pytest

from backend.storage.base import PresignMethod, StorageBackend
from backend.storage.exceptions import StorageObjectNotFoundError
from backend.storage.gcs import GCSStorageBackend
from backend.storage.local import LocalFSStorageBackend
from backend.storage.s3 import S3StorageBackend


@pytest.fixture
def local_backend(tmp_path) -> LocalFSStorageBackend:
    return LocalFSStorageBackend(
        root_path=str(tmp_path),
        presign_secret=secrets.token_hex(32),
        public_url_base="https://example.org/files",
    )


@pytest.fixture
def s3_backend(minio_endpoint: str, minio_bucket: str) -> S3StorageBackend:
    return S3StorageBackend(
        bucket_name=minio_bucket,
        region="us-east-1",
        endpoint_url=minio_endpoint,
        access_key="minioadmin",
        secret_key="minioadmin",
        use_path_style=True,
        backend_name="minio",
    )


@pytest.fixture
def gcs_backend(gcs_bucket: tuple[str, str, str]) -> GCSStorageBackend:
    bucket_name, project, endpoint = gcs_bucket
    return GCSStorageBackend(
        bucket_name=bucket_name,
        project=project,
        api_endpoint=endpoint,
    )


BACKEND_FIXTURES = ["local_backend", "s3_backend", "gcs_backend"]


@pytest.mark.parametrize("backend_fixture", BACKEND_FIXTURES)
class TestStorageBackendContract:
    def _backend(self, request, name: str) -> StorageBackend:
        return request.getfixturevalue(name)

    def test_health_check(self, request, backend_fixture: str) -> None:
        backend = self._backend(request, backend_fixture)
        assert backend.health_check() is True

    def test_upload_then_download(self, request, backend_fixture: str) -> None:
        backend = self._backend(request, backend_fixture)
        key = "samples/test.txt"
        payload = b"hello jackpot"

        result = backend.upload(key, io.BytesIO(payload), content_type="text/plain")
        assert result.key == key
        assert result.size == len(payload)
        assert result.uri

        sink = io.BytesIO()
        download = backend.download(key, sink)
        assert download.size == len(payload)
        assert sink.getvalue() == payload

    def test_exists_true_then_false_after_delete(self, request, backend_fixture: str) -> None:
        backend = self._backend(request, backend_fixture)
        key = "samples/exists-then-not.txt"
        backend.upload(key, io.BytesIO(b"x"))
        assert backend.exists(key) is True
        backend.delete(key)
        assert backend.exists(key) is False

    def test_exists_returns_false_for_missing(self, request, backend_fixture: str) -> None:
        backend = self._backend(request, backend_fixture)
        assert backend.exists("definitely/not/here.txt") is False

    def test_download_missing_raises(self, request, backend_fixture: str) -> None:
        backend = self._backend(request, backend_fixture)
        sink = io.BytesIO()
        with pytest.raises(StorageObjectNotFoundError):
            backend.download("missing/key.txt", sink)

    def test_stat_returns_metadata(self, request, backend_fixture: str) -> None:
        backend = self._backend(request, backend_fixture)
        key = "samples/stat.txt"
        backend.upload(key, io.BytesIO(b"abc"), content_type="text/plain")
        obj = backend.stat(key)
        assert obj.key == key
        assert obj.size == 3

    def test_stat_missing_raises(self, request, backend_fixture: str) -> None:
        backend = self._backend(request, backend_fixture)
        with pytest.raises(StorageObjectNotFoundError):
            backend.stat("missing/key.txt")

    def test_delete_is_idempotent(self, request, backend_fixture: str) -> None:
        backend = self._backend(request, backend_fixture)
        backend.delete("never/existed.txt")
        backend.delete("never/existed.txt")

    def test_list_objects_with_prefix(self, request, backend_fixture: str) -> None:
        backend = self._backend(request, backend_fixture)
        backend.upload("a/one.txt", io.BytesIO(b"1"))
        backend.upload("a/two.txt", io.BytesIO(b"22"))
        backend.upload("b/three.txt", io.BytesIO(b"333"))

        a_keys = sorted(o.key for o in backend.list_objects(prefix="a/"))
        assert a_keys == ["a/one.txt", "a/two.txt"]

        b_keys = sorted(o.key for o in backend.list_objects(prefix="b/"))
        assert b_keys == ["b/three.txt"]

    def test_get_uri_formats(self, request, backend_fixture: str) -> None:
        backend = self._backend(request, backend_fixture)
        uri = backend.get_uri("some/key.txt")
        assert "some/key.txt" in uri or "some" in uri

    def test_presign_get_returns_url(self, request, backend_fixture: str) -> None:
        backend = self._backend(request, backend_fixture)
        if backend_fixture == "gcs_backend":
            pytest.skip(
                "fake-gcs-server uses AnonymousCredentials which cannot sign URLs; "
                "presign is exercised against real GCS in deployment tests."
            )
        backend.upload("presign/test.txt", io.BytesIO(b"data"))
        url = backend.presign_url("presign/test.txt", timedelta(minutes=5), PresignMethod.GET)
        assert url.startswith("http")
