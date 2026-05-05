# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""TTL cache for credential reads.

The cache lives at the facade layer (one cache per CredentialFacade
instance, which is a per-process singleton). Cache keys include the
backend class name so swap-and-invalidate works cleanly in tests when a
backing implementation is exchanged for another.

Negative results (CredentialNotFoundError) are intentionally not cached:
when a credential is set after a previous lookup miss, the next read sees
the new value immediately.
"""

from __future__ import annotations

import time
from collections.abc import Callable


class CredentialCache:
    def __init__(self, ttl_seconds: int) -> None:
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must be >= 0")
        self._ttl_seconds = ttl_seconds
        self._entries: dict[tuple[str, str], tuple[str, float]] = {}

    def get_or_compute(
        self,
        backend_class_name: str,
        credential_key: str,
        fetch_fn: Callable[[], str],
    ) -> tuple[str, bool]:
        """Return (value, was_cache_hit).

        `fetch_fn` is called only on cache miss. Whatever it raises
        propagates to the caller; the cache stores nothing in that case.
        """
        cache_key = (backend_class_name, credential_key)
        now = time.monotonic()
        entry = self._entries.get(cache_key)
        if entry is not None:
            value, expires_at = entry
            if expires_at > now:
                return value, True
            # Expired — fall through to refetch.
            self._entries.pop(cache_key, None)

        value = fetch_fn()
        self._entries[cache_key] = (value, now + self._ttl_seconds)
        return value, False

    def invalidate(self, credential_key: str) -> None:
        """Remove all entries for `credential_key` regardless of backend."""
        to_remove = [k for k in self._entries if k[1] == credential_key]
        for k in to_remove:
            self._entries.pop(k, None)

    def invalidate_all(self) -> None:
        self._entries.clear()
