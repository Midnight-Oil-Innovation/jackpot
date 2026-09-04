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


def resolve_backend_type(settings) -> StorageBackendType:
    """Which backend a given Settings selects. Pure; takes the config.

    Split from get_backend_type() so callers holding a Settings — notably
    the credential predicates in backend/credentials/registry.py — ask the
    same question instead of re-deriving it. Four independent copies of
    this predicate is what B-STORAGE-LOCAL-FALLTHROUGH was.
    """
    match settings.storage_backend:
        case "local":
            return StorageBackendType.LOCAL
        case "minio" | "s3":
            return StorageBackendType.S3
        case "gcs":
            return StorageBackendType.GCS_VIA_S3
        case "gcs_native":
            return StorageBackendType.GCS_NATIVE
        case _:
            # Unset: config predates STORAGE_BACKEND. Infer, as before.
            return (
                StorageBackendType.S3
                if settings.storage_endpoint
                else StorageBackendType.GCS_VIA_S3
            )


def get_backend_type() -> StorageBackendType:
    """Which kind of backend this deployment is configured for.

    The single home for that question. It used to be answered
    independently here, in get_uri_prefix() and in the factory, all three
    by inferring from whether storage_endpoint was empty — which is how a
    local install ended up with a GCS client AND gs:// provenance
    (B-STORAGE-LOCAL-FALLTHROUGH). Callers ask this; nobody re-derives it.
    """
    return resolve_backend_type(get_settings())
