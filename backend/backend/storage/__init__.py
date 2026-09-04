# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""JACKPOT storage layer.

Public API (preserved from pre-abstraction backend/storage.py):
    StorageError
    stage_file(fileobj, destination_key) -> str
    move_to_sequences(staging_key, sequences_key) -> str
    generate_presigned_url(bucket, key, ttl_seconds=3600) -> str
    generate_signed_upload_url(bucket, key, ttl_seconds=14400) -> str
    delete_file(bucket, key) -> None
    file_exists(bucket, key) -> bool

New API (recommended for new code):
    get_storage_backend(bucket=JackpotBucket.STAGING) -> StorageBackend
    JackpotBucket (RAW / STAGING / SEQUENCES / DATASETS / SUBMISSIONS)
    StorageBackend interface
    PresignMethod, UploadResult, DownloadResult, StorageObject
"""

from __future__ import annotations

import io
from datetime import timedelta
from typing import BinaryIO

from backend.storage.base import (
    DownloadResult,
    PresignMethod,
    StorageBackend,
    StorageObject,
    UploadResult,
)
from backend.storage.exceptions import (
    StorageBackendUnavailableError,
    StorageConfigurationError,
    StorageError,
    StorageObjectNotFoundError,
    StoragePermissionError,
)
from backend.storage.factory import clear_cache, get_storage_backend
from backend.storage.settings import (
    JackpotBucket,
    StorageBackendType,
    get_backend_type,
    get_bucket_name,
)


def _get_client():
    """Return a boto3 S3 client configured for the current storage backend.

    Backward-compatibility shim. Production code in pipeline_results_loader.py
    and tests still import this. The function preserves the exact behavior of
    the pre-abstraction backend.storage._get_client(): if storage_endpoint is
    set, returns an S3 client pointed at it; otherwise returns an S3 client
    pointed at GCS via HMAC credentials.
    """
    import boto3
    from botocore.client import Config as BotoConfig

    from backend.config import get_settings
    from backend.credentials import credentials

    settings = get_settings()
    if settings.storage_endpoint:
        return boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint,
            aws_access_key_id=settings.storage_access_key,
            aws_secret_access_key=credentials.get("s3_storage_secret_key"),
            config=BotoConfig(signature_version="s3v4"),
            region_name="us-east-1",
        )
    # get_optional so ambient/ADC credentials still work: None lets boto3
    # resolve credentials via its own chain instead of raising.
    return boto3.client(
        "s3",
        endpoint_url="https://storage.googleapis.com",
        aws_access_key_id=credentials.get_optional("gcs_hmac_access_key"),
        aws_secret_access_key=credentials.get_optional("gcs_hmac_secret"),
        config=BotoConfig(signature_version="s3v4"),
        region_name="auto",
    )


def stage_file(fileobj: BinaryIO, destination_key: str) -> str:
    """Upload a file to the staging bucket. Returns the URI.

    Backward-compatible wrapper around the storage abstraction.
    Preserves the exact signature and behavior of the pre-abstraction
    backend.storage.stage_file().
    """
    backend = get_storage_backend(JackpotBucket.STAGING)
    try:
        backend.upload(destination_key, fileobj)
    except StorageError:
        raise
    except Exception as exc:
        raise StorageError(
            f"Failed to stage file '{destination_key}' to staging bucket: {exc}"
        ) from exc
    return backend.get_uri(destination_key)


def move_to_sequences(staging_key: str, sequences_key: str) -> str:
    """Move a scrubbed file from the staging bucket to the sequences bucket.

    Reads the object from staging, writes it to sequences, then deletes
    from staging. This is a download + upload + delete rather than a
    server-side copy, because the abstraction targets multiple backends
    (some of which don't support cross-bucket server-side copy).

    Returns the destination URI.
    """
    src = get_storage_backend(JackpotBucket.STAGING)
    dst = get_storage_backend(JackpotBucket.SEQUENCES)

    buffer = io.BytesIO()
    try:
        src.download(staging_key, buffer)
        buffer.seek(0)
        dst.upload(sequences_key, buffer)
        src.delete(staging_key)
    except StorageError:
        raise
    except Exception as exc:
        raise StorageError(f"Failed to move '{staging_key}' to sequences: {exc}") from exc

    return dst.get_uri(sequences_key)


def _backend_for_bucket(bucket_name: str) -> StorageBackend:
    """Find the StorageBackend whose configured bucket matches the given name.

    Used by the legacy bucket-name-based functions (generate_presigned_url,
    delete_file, file_exists) which take a bucket name rather than a
    JackpotBucket enum.
    """
    for jb in JackpotBucket:
        if get_bucket_name(jb) == bucket_name:
            return get_storage_backend(jb)
    raise StorageError(f"Unknown bucket: {bucket_name}")


def generate_presigned_url(bucket: str, key: str, ttl_seconds: int = 3600) -> str:
    """Generate a presigned download URL."""
    try:
        return _backend_for_bucket(bucket).presign_url(
            key,
            expires_in=timedelta(seconds=ttl_seconds),
            method=PresignMethod.GET,
        )
    except StorageError:
        raise
    except Exception as exc:
        raise StorageError(f"Failed to generate presigned URL for '{key}': {exc}") from exc


def generate_signed_upload_url(bucket: str, key: str, ttl_seconds: int = 14400) -> str:
    """Generate a signed upload URL (4-hour default TTL)."""
    try:
        return _backend_for_bucket(bucket).presign_url(
            key,
            expires_in=timedelta(seconds=ttl_seconds),
            method=PresignMethod.PUT,
        )
    except StorageError:
        raise
    except Exception as exc:
        raise StorageError(f"Failed to generate signed upload URL for '{key}': {exc}") from exc


def delete_file(bucket: str, key: str) -> None:
    """Delete a file from a bucket."""
    try:
        _backend_for_bucket(bucket).delete(key)
    except StorageError:
        raise
    except Exception as exc:
        raise StorageError(f"Failed to delete '{key}' from bucket '{bucket}': {exc}") from exc


def file_exists(bucket: str, key: str) -> bool:
    """Check if a file exists without downloading it."""
    try:
        return _backend_for_bucket(bucket).exists(key)
    except StorageError:
        raise
    except Exception as exc:
        raise StorageError(
            f"Failed to check existence of '{key}' in bucket '{bucket}': {exc}"
        ) from exc


__all__ = [
    # Legacy public API (preserved)
    "StorageError",
    "_get_client",
    "stage_file",
    "move_to_sequences",
    "generate_presigned_url",
    "generate_signed_upload_url",
    "delete_file",
    "file_exists",
    # New abstraction interface
    "StorageBackend",
    "PresignMethod",
    "UploadResult",
    "DownloadResult",
    "StorageObject",
    # Buckets
    "JackpotBucket",
    "get_bucket_name",
    "get_backend_type",
    "StorageBackendType",
    # Factory
    "get_storage_backend",
    "clear_cache",
    # Additional exception types
    "StorageObjectNotFoundError",
    "StoragePermissionError",
    "StorageConfigurationError",
    "StorageBackendUnavailableError",
]
