# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Environment-variable credential backend.

For a registered credential `spec`, the lookup order is:

    1. JACKPOT_CRED_<KEY_UPPER>  (canonical, e.g. JACKPOT_CRED_JWT_SIGNING_KEY)
    2. each entry of spec.legacy_env_names, in declared order

The first non-empty value wins. An empty-string env var is treated as
"not set" so an accidentally-blank value does not satisfy a required
credential.

For unregistered keys (a credential read outside REQUIRED_CREDENTIALS),
only the canonical JACKPOT_CRED_<KEY_UPPER> form is checked; no legacy
fallback is available because legacy names exist only for known specs.
"""

from __future__ import annotations

import os

from backend.credentials.base import CredentialBackend, CredentialNotFoundError
from backend.credentials.registry import REQUIRED_CREDENTIALS, get_spec


def _canonical_env_var(key: str) -> str:
    return f"JACKPOT_CRED_{key.upper()}"


class EnvVarBackend(CredentialBackend):
    """Credential backend that reads from process environment variables."""

    def get(self, key: str) -> str:
        names = self._candidate_env_names(key)
        for name in names:
            value = os.environ.get(name)
            if value:
                return value
        tried = ", ".join(names)
        raise CredentialNotFoundError(
            f"Credential '{key}' not found in environment (tried: {tried})"
        )

    def list_keys(self) -> list[str]:
        present: list[str] = []
        for spec in REQUIRED_CREDENTIALS:
            for name in self._candidate_env_names(spec.key):
                if os.environ.get(name):
                    present.append(spec.key)
                    break
        return present

    def _candidate_env_names(self, key: str) -> list[str]:
        names = [_canonical_env_var(key)]
        spec = get_spec(key)
        if spec is not None:
            names.extend(spec.legacy_env_names)
        return names
