# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Factory for instantiating storage backends per lifecycle bucket.

JACKPOT uses five lifecycle buckets (raw, staging, sequences, datasets,
submissions). Each one is a separate StorageBackend instance pointing at
a different bucket name. They all share the same underlying credentials
and endpoint.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from backend.config import get_settings
from backend.credentials import credentials
from backend.storage.base import StorageBackend
from backend.storage.exceptions import StorageError
from backend.storage.local import LocalFSStorageBackend
from backend.storage.s3 import S3StorageBackend
from backend.storage.settings import JackpotBucket, get_bucket_name


@cache
def get_storage_backend(bucket: JackpotBucket = JackpotBucket.STAGING) -> StorageBackend:
    """Return a StorageBackend pointing at the named lifecycle bucket.

    Cached per-bucket so subsequent calls return the same instance.
    """
    settings = get_settings()
    bucket_name = get_bucket_name(bucket)

    # Explicit selection wins. `None` falls through to the legacy
    # inference below so a config predating STORAGE_BACKEND is unchanged.
    if settings.storage_backend == "local":
        if not settings.local_storage_root:
            raise StorageError(
                "storage_backend is 'local' but local_storage_root is not set. "
                "Set LOCAL_STORAGE_ROOT to the directory JACKPOT should own.",
                backend="local",
            )
        return LocalFSStorageBackend(
            root_path=str(Path(settings.local_storage_root).expanduser() / bucket_name),
            presign_secret=credentials.get("local_storage_presign_secret"),
            public_url_base=(settings.local_storage_public_url_base or settings.jackpot_api_url),
        )

    if settings.storage_backend in {"minio", "s3"} or (
        settings.storage_backend is None and settings.storage_endpoint
    ):
        # S3-compatible (MinIO, AWS S3, Ceph RGW, etc.)
        return S3StorageBackend(
            bucket_name=bucket_name,
            region="us-east-1",
            endpoint_url=settings.storage_endpoint,
            access_key=settings.storage_access_key,
            secret_key=credentials.get("s3_storage_secret_key"),
            use_path_style=True,
            backend_name="s3",
        )

    # storage_backend == "gcs", or unset with no endpoint configured.
    # GCS via S3-compatible HMAC credentials. Use get_optional so that a
    # deployment relying on ambient/ADC credentials (no HMAC keys set)
    # gets None here and lets boto3 resolve credentials itself, rather
    # than crashing with CredentialNotFoundError on the first storage call.
    return S3StorageBackend(
        bucket_name=bucket_name,
        region="auto",
        endpoint_url="https://storage.googleapis.com",
        access_key=credentials.get_optional("gcs_hmac_access_key"),
        secret_key=credentials.get_optional("gcs_hmac_secret"),
        use_path_style=False,
        backend_name="gcs",
    )


def clear_cache() -> None:
    """Clear the backend cache. Useful for tests that change config."""
    get_storage_backend.cache_clear()
