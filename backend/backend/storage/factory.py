# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-present Glen Otero
"""Factory for instantiating storage backends per lifecycle bucket.

JACKPOT uses five lifecycle buckets (raw, staging, sequences, datasets,
submissions). Each one is a separate StorageBackend instance pointing at
a different bucket name. They all share the same underlying credentials
and endpoint.
"""

from __future__ import annotations

import os
from functools import cache

from backend.config import get_settings
from backend.storage.base import StorageBackend
from backend.storage.s3 import S3StorageBackend
from backend.storage.settings import JackpotBucket, get_bucket_name


@cache
def get_storage_backend(bucket: JackpotBucket = JackpotBucket.STAGING) -> StorageBackend:
    """Return a StorageBackend pointing at the named lifecycle bucket.

    Cached per-bucket so subsequent calls return the same instance.
    """
    settings = get_settings()
    bucket_name = get_bucket_name(bucket)

    if settings.storage_endpoint:
        # S3-compatible (MinIO, AWS S3, Ceph RGW, etc.)
        return S3StorageBackend(
            bucket_name=bucket_name,
            region="us-east-1",
            endpoint_url=settings.storage_endpoint,
            access_key=settings.storage_access_key,
            secret_key=settings.storage_secret_key,
            use_path_style=True,
            backend_name="s3",
        )

    # GCS via S3-compatible HMAC credentials
    return S3StorageBackend(
        bucket_name=bucket_name,
        region="auto",
        endpoint_url="https://storage.googleapis.com",
        access_key=os.environ.get("GCS_HMAC_ACCESS_KEY"),
        secret_key=os.environ.get("GCS_HMAC_SECRET"),
        use_path_style=False,
        backend_name="gcs",
    )


def clear_cache() -> None:
    """Clear the backend cache. Useful for tests that change config."""
    get_storage_backend.cache_clear()
