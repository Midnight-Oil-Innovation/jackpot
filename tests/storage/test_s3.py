# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""S3 / MinIO-specific tests."""

from __future__ import annotations

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
