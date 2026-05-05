# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""GCP Secret Manager credential backend.

Secret naming convention: `{secret_prefix}{key.replace('_','-')}`. With
the default prefix `jackpot-cred-` and key `jwt_signing_key`, the secret
name is `jackpot-cred-jwt-signing-key`.

Auth: ADC. Workload Identity bindings must include
`roles/secretmanager.secretAccessor` on each secret accessed.

Import-time policy: this module imports `google.cloud.secretmanager` at
module load. If the dependency is not installed, the backend is unusable
and the import fails with a clear error rather than failing later in an
unrelated request scope.
"""

from __future__ import annotations

from google.api_core import exceptions as gax_exceptions
from google.cloud import secretmanager

from backend.credentials.base import (
    CredentialBackend,
    CredentialError,
    CredentialNotFoundError,
)


def _secret_id(key: str) -> str:
    return key.replace("_", "-")


def _key_from_secret_id(secret_id: str, prefix: str) -> str:
    return secret_id[len(prefix) :].replace("-", "_") if secret_id.startswith(prefix) else ""


class GCPSecretManagerBackend(CredentialBackend):
    """Credential backend that reads from GCP Secret Manager via ADC."""

    def __init__(self, project_id: str, secret_prefix: str) -> None:
        if not project_id:
            raise CredentialError("GCPSecretManagerBackend requires a non-empty project_id.")
        self._project_id = project_id
        self._secret_prefix = secret_prefix
        self._client: secretmanager.SecretManagerServiceClient | None = None

    def _get_client(self) -> secretmanager.SecretManagerServiceClient:
        if self._client is None:
            self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    def _secret_resource_name(self, key: str) -> str:
        secret_id = f"{self._secret_prefix}{_secret_id(key)}"
        return f"projects/{self._project_id}/secrets/{secret_id}/versions/latest"

    def get(self, key: str) -> str:
        name = self._secret_resource_name(key)
        try:
            response = self._get_client().access_secret_version(name=name)
        except gax_exceptions.NotFound as exc:
            raise CredentialNotFoundError(
                f"Secret '{self._secret_prefix}{_secret_id(key)}' not found "
                f"in project '{self._project_id}'"
            ) from exc
        except gax_exceptions.PermissionDenied as exc:
            raise CredentialError(
                f"Permission denied accessing secret "
                f"'{self._secret_prefix}{_secret_id(key)}'. Verify Workload "
                f"Identity bindings include "
                f"'roles/secretmanager.secretAccessor'."
            ) from exc
        except gax_exceptions.GoogleAPICallError as exc:
            raise CredentialError(
                f"GCP error accessing secret '{self._secret_prefix}{_secret_id(key)}': {exc}"
            ) from exc
        return response.payload.data.decode("utf-8")

    def list_keys(self) -> list[str]:
        parent = f"projects/{self._project_id}"
        try:
            secrets = self._get_client().list_secrets(parent=parent)
        except gax_exceptions.GoogleAPICallError as exc:
            raise CredentialError(
                f"GCP error listing secrets in project '{self._project_id}': {exc}"
            ) from exc
        keys: list[str] = []
        for secret in secrets:
            secret_id = secret.name.rsplit("/", 1)[-1]
            if not secret_id.startswith(self._secret_prefix):
                continue
            keys.append(_key_from_secret_id(secret_id, self._secret_prefix))
        return keys
