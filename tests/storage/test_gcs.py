# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""GCS-specific tests."""

from __future__ import annotations

from backend.storage.gcs import GCSStorageBackend


def test_gcs_uri_format(gcs_bucket: tuple[str, str, str]) -> None:
    bucket_name, project, endpoint = gcs_bucket
    backend = GCSStorageBackend(
        bucket_name=bucket_name,
        project=project,
        api_endpoint=endpoint,
    )
    assert backend.get_uri("a/b.txt") == f"gs://{bucket_name}/a/b.txt"
