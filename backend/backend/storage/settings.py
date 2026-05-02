# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Storage settings shim.

This module exists to bridge JACKPOT's existing config (backend.config) with
the new storage abstraction. It does NOT introduce new env vars - it reads
the existing storage_* settings already in use.
"""

from __future__ import annotations

import enum

from backend.config import get_settings


class StorageBackendType(str, enum.Enum):
    """Which kind of storage backend the configured endpoint represents.

    Inferred from existing config:
    - storage_endpoint set       -> S3-compatible (MinIO, AWS S3, Ceph, etc.)
    - storage_endpoint not set   -> GCS via S3-compatible HMAC creds
    - reserved for future        -> LOCAL, native GCS
    """

    S3 = "s3"
    GCS_VIA_S3 = "gcs_via_s3"
    GCS_NATIVE = "gcs_native"
    LOCAL = "local"


class JackpotBucket(str, enum.Enum):
    """The five lifecycle buckets JACKPOT uses."""

    RAW = "raw"
    STAGING = "staging"
    SEQUENCES = "sequences"
    DATASETS = "datasets"
    SUBMISSIONS = "submissions"


def get_bucket_name(bucket: JackpotBucket) -> str:
    """Return the configured bucket name for a given lifecycle bucket."""
    settings = get_settings()
    mapping = {
        JackpotBucket.RAW: settings.storage_bucket_raw,
        JackpotBucket.STAGING: settings.storage_bucket_staging,
        JackpotBucket.SEQUENCES: settings.storage_bucket_sequences,
        JackpotBucket.DATASETS: settings.storage_bucket_datasets,
        JackpotBucket.SUBMISSIONS: settings.storage_bucket_submissions,
    }
    return mapping[bucket]


def get_backend_type() -> StorageBackendType:
    """Infer which kind of backend we're talking to from existing config."""
    settings = get_settings()
    if settings.storage_endpoint:
        return StorageBackendType.S3
    return StorageBackendType.GCS_VIA_S3


def get_uri_prefix() -> str:
    """Return 's3' or 'gs' based on configured backend."""
    settings = get_settings()
    return "s3" if settings.storage_endpoint else "gs"
