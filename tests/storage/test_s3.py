# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""S3 / MinIO-specific tests."""

from __future__ import annotations

import io
from unittest.mock import Mock

import boto3.exceptions
import pytest
import s3transfer.exceptions
from botocore.exceptions import NoCredentialsError

from backend.storage.exceptions import StorageError
from backend.storage.s3 import S3StorageBackend


def test_s3_uri_format(minio_endpoint: str, minio_bucket: str) -> None:
    backend = S3StorageBackend(
        bucket_name=minio_bucket,
        region="us-east-1",
        endpoint_url=minio_endpoint,
        access_key="minioadmin",
        secret_key="minioadmin",
        use_path_style=True,
        backend_name="minio",
    )
    assert backend.get_uri("a/b.txt") == f"s3://{minio_bucket}/a/b.txt"


def _offline_backend() -> S3StorageBackend:
    """A backend whose client is never called for real — the transfers are stubbed."""
    return S3StorageBackend(
        bucket_name="jackpot-test",
        region="us-east-1",
        endpoint_url="http://127.0.0.1:1",
        access_key="k",
        secret_key="s",
        use_path_style=True,
        backend_name="minio",
    )


@pytest.mark.parametrize(
    ("transfer", "exc"),
    [
        # boto3's own wrappers. S3UploadFailedError descends from Boto3Error,
        # which shares no ancestor with BotoCoreError or ClientError.
        ("upload_fileobj", boto3.exceptions.S3UploadFailedError("multipart upload failed")),
        ("download_fileobj", boto3.exceptions.RetriesExceededError(OSError("reset"))),
        # s3transfer's, which are bare Exceptions. download.py raises this one
        # when a chunk fails past its retry budget mid-stream.
        ("upload_fileobj", s3transfer.exceptions.S3UploadFailedError("part failed")),
        ("download_fileobj", s3transfer.exceptions.RetriesExceededError(OSError("reset"))),
    ],
)
def test_managed_transfer_failures_surface_as_storage_errors(
    transfer: str, exc: BaseException, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Managed-transfer failures must still surface as StorageError.

    Both hierarchies on purpose: narrowing the catch to Boto3Error would still
    pass the boto3.* cases and fail the s3transfer.* ones.
    """
    backend = _offline_backend()
    monkeypatch.setattr(backend._client, transfer, Mock(side_effect=exc))

    with pytest.raises(StorageError) as excinfo:
        if transfer == "upload_fileobj":
            backend.upload("a/b.txt", io.BytesIO(b"payload"))
        else:
            backend.download("a/b.txt", io.BytesIO())

    # Load-bearing, not decoration: if the monkeypatch ever stops taking effect,
    # head_object reaches the dead endpoint and raises StorageBackendUnavailableError,
    # which is a StorageError — so pytest.raises above would pass on nothing.
    assert excinfo.value.__cause__ is exc


@pytest.mark.parametrize("method", ["exists", "delete", "stat", "list_objects"])
def test_credential_failure_surfaces_as_storage_error(
    method: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing or unusable credential must still surface as StorageError.

    NoCredentialsError is a BotoCoreError, which shares no ancestor with
    ClientError -- and these four methods caught only ClientError and
    EndpointConnectionError, so it escaped. upload/download were already
    covered by their positional catch, and presign_url/health_check name
    BotoCoreError outright.
    """
    backend = _offline_backend()
    exc = NoCredentialsError()

    if method == "list_objects":
        paginator = Mock()
        paginator.paginate.side_effect = exc
        monkeypatch.setattr(backend._client, "get_paginator", Mock(return_value=paginator))
    else:
        api = {"exists": "head_object", "delete": "delete_object", "stat": "head_object"}[method]
        monkeypatch.setattr(backend._client, api, Mock(side_effect=exc))

    with pytest.raises(StorageError) as excinfo:
        if method == "exists":
            backend.exists("a/b.txt")
        elif method == "delete":
            backend.delete("a/b.txt")
        elif method == "stat":
            backend.stat("a/b.txt")
        else:
            list(backend.list_objects())

    # Identity, and it is the anti-vacuity guard. All four methods fail on their
    # own against the dead endpoint, as StorageBackendUnavailableError -- itself
    # a StorageError, so pytest.raises alone would pass on the wrong failure.
    # `exc` is reachable only through the stub, so `is exc` holds only if the
    # stub fired.
    assert excinfo.value.__cause__ is exc

    # And plain StorageError, not the Unavailable subclass: a credential that
    # will not refresh is not a reachability problem, and pytest.raises accepts
    # any subclass, so nothing above pins which mapping ran.
    assert type(excinfo.value) is StorageError
