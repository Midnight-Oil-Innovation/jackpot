# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Declarative registry of credentials JACKPOT reads.

Adding a new credential is a two-step change: declare it here, then call
`credentials.get("<key>")` at the read site. The registry drives:

- Startup validation (`validate_required()`)
- EnvVarBackend's legacy-name fallback (`legacy_env_names`)
- Diagnostic enumeration (`list_keys()`)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.config import Settings


@dataclass(frozen=True)
class CredentialSpec:
    """Declarative description of a credential the system reads.

    `key`: canonical identifier used by callers (e.g., 'jwt_signing_key').
    `description`: short string for diagnostic and audit messages.
    `legacy_env_names`: env var names checked by EnvVarBackend as a
        backward-compat fallback after the canonical JACKPOT_CRED_* lookup.
    `required_predicate`: callable taking a Settings instance and returning
        True if this credential is required for the current configuration.
        For unconditionally required credentials, use `lambda _settings: True`.
    """

    key: str
    description: str
    legacy_env_names: tuple[str, ...] = field(default_factory=tuple)
    required_predicate: Callable[[Settings], bool] = field(default=lambda _settings: False)


def _uses_gcs_hmac(settings: Settings) -> bool:
    """True when this deployment reaches GCS over the S3-compatible API.

    That path needs static HMAC keys: botocore has no GCP credential
    provider, so boto3 falls back to the AWS chain and resolves nothing on
    a Workload Identity pod. storage_backend="gcs_native" uses ADC instead
    and needs none of this.

    Imported inside the function because backend.storage's package __init__
    pulls in the factory, which imports this module.
    """
    from backend.storage.settings import StorageBackendType, resolve_backend_type

    return resolve_backend_type(settings) is StorageBackendType.GCS_VIA_S3 and settings.env == "gcp"


# Storage-backend selection is no longer inferred from whether
# `storage_endpoint` is set. get_backend_type() in
# backend/storage/settings.py reads Settings.storage_backend and the
# factory dispatches on it, so the predicates below key off that same
# field. The one backend still unwired is the native GCS client — see
# B-STORAGE-DEAD-BACKENDS.
REQUIRED_CREDENTIALS: tuple[CredentialSpec, ...] = (
    CredentialSpec(
        key="jwt_signing_key",
        description="JWT HS256 signing key for session and OAuth state tokens.",
        legacy_env_names=("JACKPOT_SECRET_KEY", "SECRET_KEY"),
        required_predicate=lambda _s: True,
    ),
    CredentialSpec(
        key="google_oauth_client_secret",
        description="Google OAuth client secret for the OAuth login flow.",
        legacy_env_names=(
            "JACKPOT_GOOGLE_OAUTH_CLIENT_SECRET",
            "GOOGLE_OAUTH_CLIENT_SECRET",
        ),
        # Only required in production-like deployments; local dev uses the
        # mock-user shortcut and never hits the OAuth code path.
        required_predicate=lambda s: s.env == "gcp",
    ),
    CredentialSpec(
        key="s3_storage_secret_key",
        description="S3/MinIO secret access key for object storage.",
        legacy_env_names=("JACKPOT_STORAGE_SECRET_KEY", "STORAGE_SECRET_KEY"),
        required_predicate=lambda s: bool(s.storage_endpoint),
    ),
    CredentialSpec(
        key="gcs_hmac_access_key",
        description="HMAC access key for S3-compatible access to GCS buckets.",
        legacy_env_names=("GCS_HMAC_ACCESS_KEY",),
        required_predicate=lambda s: _uses_gcs_hmac(s),
    ),
    CredentialSpec(
        key="gcs_hmac_secret",
        description="HMAC secret for S3-compatible access to GCS buckets.",
        legacy_env_names=("GCS_HMAC_SECRET",),
        required_predicate=lambda s: _uses_gcs_hmac(s),
    ),
    CredentialSpec(
        key="local_storage_presign_secret",
        description="HMAC signing secret for presigned URLs in the local "
        "filesystem storage backend.",
        legacy_env_names=("JACKPOT_PRESIGN_SECRET",),
        # Flipped 2026-09-04 (B-STORAGE-LOCAL-FALLTHROUGH): the factory
        # now builds LocalFSStorageBackend when storage_backend == "local",
        # and that backend refuses a secret shorter than 32 chars, so a
        # misconfigured deployment should fail at startup rather than on
        # the first presigned URL.
        required_predicate=lambda s: s.storage_backend == "local",
    ),
    # I-3a: backend-driven submission execution credentials. Required
    # only when the operator opts in via Settings.allow_backend_submission
    # AND lists the matching repo in Settings.backend_submission_repos.
    # I-3b consumes these via credentials.get(...) inside the Seqsender
    # subprocess invocation. Predicates intentionally skip startup-time
    # enforcement when the repo isn't in the opt-in list, so an operator
    # can run NCBI-only without setting ENA credentials.
    CredentialSpec(
        key="ncbi_submission_username",
        description="NCBI submitter account username for backend execution "
        "targeting NCBI repositories.",
        legacy_env_names=(
            "JACKPOT_NCBI_SUBMISSION_USERNAME",
            "NCBI_SUBMISSION_USERNAME",
        ),
        required_predicate=lambda s: (
            s.allow_backend_submission and "ncbi" in s.backend_submission_repos
        ),
    ),
    CredentialSpec(
        key="ncbi_submission_password",
        description="NCBI submitter account password for backend execution "
        "targeting NCBI repositories.",
        legacy_env_names=(
            "JACKPOT_NCBI_SUBMISSION_PASSWORD",
            "NCBI_SUBMISSION_PASSWORD",
        ),
        required_predicate=lambda s: (
            s.allow_backend_submission and "ncbi" in s.backend_submission_repos
        ),
    ),
    CredentialSpec(
        key="ena_webin_username",
        description="ENA Webin submission username (e.g., 'Webin-12345').",
        legacy_env_names=(
            "JACKPOT_ENA_WEBIN_USERNAME",
            "ENA_WEBIN_USERNAME",
        ),
        required_predicate=lambda s: (
            s.allow_backend_submission and "ena" in s.backend_submission_repos
        ),
    ),
    CredentialSpec(
        key="ena_webin_password",
        description="ENA Webin submission password.",
        legacy_env_names=(
            "JACKPOT_ENA_WEBIN_PASSWORD",
            "ENA_WEBIN_PASSWORD",
        ),
        required_predicate=lambda s: (
            s.allow_backend_submission and "ena" in s.backend_submission_repos
        ),
    ),
)


_BY_KEY: dict[str, CredentialSpec] = {spec.key: spec for spec in REQUIRED_CREDENTIALS}


def get_spec(key: str) -> CredentialSpec | None:
    """Return the registered spec for `key`, or None if unregistered."""
    return _BY_KEY.get(key)
