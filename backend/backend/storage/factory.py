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
from backend.storage.gcs import GCSStorageBackend
from backend.storage.local import LocalFSStorageBackend
from backend.storage.s3 import S3StorageBackend
from backend.storage.settings import (
    JackpotBucket,
    StorageBackendType,
    get_backend_type,
    get_bucket_name,
)


@cache
def get_storage_backend(bucket: JackpotBucket = JackpotBucket.STAGING) -> StorageBackend:
    """Return a StorageBackend pointing at the named lifecycle bucket.

    Cached per-bucket so subsequent calls return the same instance.
    """
    settings = get_settings()
    bucket_name = get_bucket_name(bucket)

    # get_backend_type() is the only place that answers "which backend";
    # it handles both the named choice and the legacy inference for a
    # config predating STORAGE_BACKEND.
    kind = get_backend_type()

    if kind is StorageBackendType.LOCAL:
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

    if kind is StorageBackendType.S3:
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

    if kind is StorageBackendType.GCS_NATIVE:
        # The only path that can authenticate with Application Default
        # Credentials, i.e. Workload Identity on GKE. botocore ships no GCP
        # credential provider, so the HMAC path below cannot do ADC no
        # matter what is configured; it needs static keys.
        if not settings.gcp_project_id:
            raise StorageError(
                "storage_backend is 'gcs_native' but gcp_project_id is not set. "
                "ADC needs a project to resolve against.",
                backend="gcs",
            )
        return GCSStorageBackend(bucket_name=bucket_name, project=settings.gcp_project_id)

    # GCS over the S3-compatible HMAC API. get_optional, not get, so a
    # misconfigured deployment surfaces at the first storage call rather
    # than at import. Note this path REQUIRES HMAC keys: boto3 falls back
    # to the AWS credential chain, which resolves nothing on a GKE pod
    # using Workload Identity. Use storage_backend="gcs_native" for ADC.
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
