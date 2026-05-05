"""C-1: CredentialCache TTL, invalidation, backend-class isolation."""

from __future__ import annotations

import time

import pytest

from backend.credentials.base import CredentialNotFoundError
from backend.credentials.cache import CredentialCache


def test_hit_returns_value_without_calling_fetch():
    cache = CredentialCache(ttl_seconds=60)
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return "v1"

    v, hit = cache.get_or_compute("Backend", "k", fetch)
    assert v == "v1"
    assert hit is False
    assert calls["n"] == 1

    v, hit = cache.get_or_compute("Backend", "k", fetch)
    assert v == "v1"
    assert hit is True
    assert calls["n"] == 1


def test_expiry_triggers_refetch(monkeypatch):
    cache = CredentialCache(ttl_seconds=10)
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return f"v{calls['n']}"

    fake_time = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_time[0])

    cache.get_or_compute("Backend", "k", fetch)
    fake_time[0] = 1005.0
    v, hit = cache.get_or_compute("Backend", "k", fetch)
    assert hit is True
    assert v == "v1"

    fake_time[0] = 1011.0  # past TTL
    v, hit = cache.get_or_compute("Backend", "k", fetch)
    assert hit is False
    assert v == "v2"


def test_invalidate_removes_entry():
    cache = CredentialCache(ttl_seconds=60)
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return "v"

    cache.get_or_compute("Backend", "k", fetch)
    cache.invalidate("k")
    cache.get_or_compute("Backend", "k", fetch)
    assert calls["n"] == 2


def test_invalidate_all_clears_everything():
    cache = CredentialCache(ttl_seconds=60)
    cache.get_or_compute("B", "a", lambda: "1")
    cache.get_or_compute("B", "b", lambda: "2")
    cache.invalidate_all()
    n = {"i": 0}

    def fetch():
        n["i"] += 1
        return "X"

    cache.get_or_compute("B", "a", fetch)
    cache.get_or_compute("B", "b", fetch)
    assert n["i"] == 2


def test_cache_key_includes_backend_class_name():
    """Swapping backends must not return the prior backend's value."""
    cache = CredentialCache(ttl_seconds=60)
    cache.get_or_compute("EnvVarBackend", "k", lambda: "env-value")
    v, hit = cache.get_or_compute("FileBackend", "k", lambda: "file-value")
    assert hit is False
    assert v == "file-value"


def test_negative_results_not_cached():
    """A miss followed by a successful fetch returns the new value."""
    cache = CredentialCache(ttl_seconds=60)

    state = {"set": False}

    def fetch():
        if state["set"]:
            return "now-set"
        raise CredentialNotFoundError("nope")

    with pytest.raises(CredentialNotFoundError):
        cache.get_or_compute("B", "k", fetch)

    state["set"] = True
    v, hit = cache.get_or_compute("B", "k", fetch)
    assert hit is False
    assert v == "now-set"


def test_invalidate_removes_entries_across_backends():
    cache = CredentialCache(ttl_seconds=60)
    cache.get_or_compute("A", "k", lambda: "a")
    cache.get_or_compute("B", "k", lambda: "b")
    cache.invalidate("k")
    n = {"i": 0}

    def fetch():
        n["i"] += 1
        return "fresh"

    cache.get_or_compute("A", "k", fetch)
    cache.get_or_compute("B", "k", fetch)
    assert n["i"] == 2


def test_constructor_rejects_negative_ttl():
    with pytest.raises(ValueError):
        CredentialCache(ttl_seconds=-1)


def test_zero_ttl_disables_caching():
    """ttl=0 means every read is a miss because expires_at == now."""
    cache = CredentialCache(ttl_seconds=0)
    n = {"i": 0}

    def fetch():
        n["i"] += 1
        return f"v{n['i']}"

    cache.get_or_compute("B", "k", fetch)
    cache.get_or_compute("B", "k", fetch)
    assert n["i"] == 2
