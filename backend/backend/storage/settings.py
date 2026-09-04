# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Storage settings shim.

This module exists to bridge JACKPOT's existing config (backend.config) with
the new storage abstraction. It does NOT introduce new env vars - it reads
the existing storage_* settings already in use.
"""

from __future__ import annotations

import enum

from backend.config import Settings, get_settings


class StorageBackendType(str, enum.Enum):
    """Which storage backend a deployment is configured for.

    Selected by name via Settings.storage_backend and resolved by
    resolve_backend_type(). Endpoint-emptiness inference survives only as
    the legacy path for a config that predates that setting; it is not how
    a backend is chosen. All four members are reachable.
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


def resolve_backend_type(settings: Settings) -> StorageBackendType:
    """Which backend a given Settings selects. The single home for that
    question.

    It used to be answered independently in the factory, in
    get_uri_prefix(), in S3StorageBackend.get_uri() and in the gcs_hmac_*
    credential predicates — four copies, all inferring from whether
    storage_endpoint was empty, which is how a local install ended up with
    a GCS client AND gs:// provenance (B-STORAGE-LOCAL-FALLTHROUGH).

    Pure and takes the config, so callers holding a Settings — notably the
    credential predicates, which are handed one — ask rather than re-derive.
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
    """resolve_backend_type() against the process-wide Settings.

    Convenience for callers that do not already hold a Settings. Anything
    that does should call resolve_backend_type directly — going through
    here fetches the config a second time, which is how a test ended up
    needing to patch get_settings in two modules.
    """
    return resolve_backend_type(get_settings())
