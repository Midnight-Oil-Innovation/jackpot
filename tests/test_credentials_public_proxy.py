"""C-1: public `credentials` proxy and lifecycle helpers.

These cover the thin proxy methods in backend.credentials.__init__ plus
the invalidate / list_keys / get_optional facade methods.
"""

from __future__ import annotations

from backend.credentials import (
    CredentialError,
    CredentialNotFoundError,
    _reset_backend,
    _set_backend,
    credentials,
)
from backend.credentials.test_helpers import InMemoryBackend


def test_proxy_get_via_singleton():
    backend = InMemoryBackend({"jwt_signing_key": "v1"})
    _set_backend(backend)
    try:
        assert credentials.get("jwt_signing_key") == "v1"
    finally:
        _reset_backend()


def test_proxy_get_optional_returns_none(fake_credentials):
    assert credentials.get_optional("not_set") is None


def test_proxy_get_optional_returns_value(fake_credentials):
    fake_credentials.set("k", "v")
    assert credentials.get_optional("k") == "v"


def test_proxy_list_keys(fake_credentials):
    fake_credentials.set("a", "1")
    fake_credentials.set("b", "2")
    assert set(credentials.list_keys()) == {"a", "b"}


def test_proxy_invalidate(fake_credentials):
    fake_credentials.set("k", "v1")
    assert credentials.get("k") == "v1"
    fake_credentials.set("k", "v2")
    # Cached value still observed until invalidated.
    assert credentials.get("k") == "v1"
    credentials.invalidate("k")
    assert credentials.get("k") == "v2"


def test_proxy_invalidate_all(fake_credentials):
    fake_credentials.set("a", "1")
    fake_credentials.set("b", "2")
    credentials.get("a")
    credentials.get("b")
    fake_credentials.set("a", "1-new")
    fake_credentials.set("b", "2-new")
    credentials.invalidate_all()
    assert credentials.get("a") == "1-new"
    assert credentials.get("b") == "2-new"


def test_test_helpers_set_and_remove():
    backend = InMemoryBackend()
    backend.set("k", "v")
    assert backend.get("k") == "v"
    backend.remove("k")
    try:
        backend.get("k")
    except CredentialNotFoundError:
        return
    raise AssertionError("expected CredentialNotFoundError after remove()")


def test_credential_error_module_export():
    """CredentialError is part of the public module namespace."""
    assert issubclass(CredentialNotFoundError, CredentialError)
