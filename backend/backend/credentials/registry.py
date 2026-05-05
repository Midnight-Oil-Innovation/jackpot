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


# The factory's existing storage-backend selection is binary: if
# `storage_endpoint` is set, use S3-compatible (MinIO, AWS S3, MinIO under
# Docker Compose for local dev); otherwise use GCS via S3-compatible HMAC
# credentials (production GCP). The predicates below reflect that signal.
# When the storage factory grows additional backends (LocalFS, native GCS)
# the predicates are the right place to extend.
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
        required_predicate=lambda s: not bool(s.storage_endpoint) and s.env == "gcp",
    ),
    CredentialSpec(
        key="gcs_hmac_secret",
        description="HMAC secret for S3-compatible access to GCS buckets.",
        legacy_env_names=("GCS_HMAC_SECRET",),
        required_predicate=lambda s: not bool(s.storage_endpoint) and s.env == "gcp",
    ),
    CredentialSpec(
        key="local_storage_presign_secret",
        description="HMAC signing secret for presigned URLs in the local "
        "filesystem storage backend.",
        legacy_env_names=("JACKPOT_PRESIGN_SECRET",),
        # No factory branch instantiates LocalFSStorageBackend yet; flip this
        # to a real predicate when storage_factory grows that backend.
        required_predicate=lambda _s: False,
    ),
)


_BY_KEY: dict[str, CredentialSpec] = {spec.key: spec for spec in REQUIRED_CREDENTIALS}


def get_spec(key: str) -> CredentialSpec | None:
    """Return the registered spec for `key`, or None if unregistered."""
    return _BY_KEY.get(key)
