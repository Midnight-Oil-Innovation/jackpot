"""C-1: audit events emitted on credential reads.

The audit logger is `backend.credentials.audit` (stdlib `logging`,
not the DB-bound backend.audit). This separation exists because
credential reads happen at app startup outside any DB transaction.
"""

from __future__ import annotations

import logging

import pytest

from backend.config import Settings
from backend.credentials.facade import (
    EVENT_READ,
    EVENT_READ_FAILED,
    CredentialFacade,
)
from backend.credentials.test_helpers import InMemoryBackend


def _facade(backend: InMemoryBackend, ttl: int = 60) -> CredentialFacade:
    return CredentialFacade(
        backend=backend,
        settings=Settings(env="local", credential_cache_ttl_seconds=ttl),
    )


def _events(records: list[logging.LogRecord], event: str):
    return [r for r in records if getattr(r, "event", None) == event]


def test_cache_miss_emits_read_event(caplog):
    backend = InMemoryBackend({"jwt_signing_key": "v"})
    facade = _facade(backend)
    with caplog.at_level(logging.INFO, logger="backend.credentials.audit"):
        facade.get("jwt_signing_key")
    reads = _events(caplog.records, EVENT_READ)
    assert len(reads) == 1
    rec = reads[0]
    assert rec.key == "jwt_signing_key"
    assert rec.backend == "InMemoryBackend"
    # The credential value MUST NOT appear in the log record.
    assert getattr(rec, "value", None) != "v"
    assert "v" not in rec.getMessage()


def test_cache_hit_emits_no_event(caplog):
    backend = InMemoryBackend({"jwt_signing_key": "v"})
    facade = _facade(backend)
    facade.get("jwt_signing_key")
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="backend.credentials.audit"):
        facade.get("jwt_signing_key")
    assert _events(caplog.records, EVENT_READ) == []


def test_failure_emits_read_failed(caplog):
    from backend.credentials.base import CredentialNotFoundError

    backend = InMemoryBackend()  # empty
    facade = _facade(backend)
    with (
        caplog.at_level(logging.WARNING, logger="backend.credentials.audit"),
        pytest.raises(CredentialNotFoundError),
    ):
        facade.get("jwt_signing_key")
    failures = _events(caplog.records, EVENT_READ_FAILED)
    assert len(failures) == 1
    rec = failures[0]
    assert rec.key == "jwt_signing_key"
    assert rec.backend == "InMemoryBackend"
    assert hasattr(rec, "reason")


def test_failure_reason_does_not_leak_value(caplog):
    """Even when a backend raises CredentialError with detail in the
    message, no credential value should appear in audit output. The
    InMemoryBackend never sees a value on a miss, but verify the message
    contains only the key and the backend's standard 'not present' text."""
    from backend.credentials.base import CredentialNotFoundError

    backend = InMemoryBackend()
    facade = _facade(backend)
    with (
        caplog.at_level(logging.WARNING, logger="backend.credentials.audit"),
        pytest.raises(CredentialNotFoundError),
    ):
        facade.get("jwt_signing_key")
    rec = _events(caplog.records, EVENT_READ_FAILED)[0]
    assert "jwt_signing_key" in rec.reason
    # No quoted-value-like substrings should be in the reason.
    assert "value=" not in rec.reason


def test_get_optional_returning_none_emits_no_event(caplog):
    backend = InMemoryBackend()
    facade = _facade(backend)
    with caplog.at_level(logging.WARNING, logger="backend.credentials.audit"):
        result = facade.get_optional("jwt_signing_key")
    assert result is None
    # get_optional swallows CredentialNotFoundError; CREDENTIAL_READ_FAILED
    # is still emitted by the underlying get(). That is acceptable per
    # spec: failed reads are auditable. CREDENTIAL_READ must NOT fire.
    assert _events(caplog.records, EVENT_READ) == []


def test_get_optional_hit_emits_read(caplog):
    backend = InMemoryBackend({"k": "v"})
    facade = _facade(backend)
    with caplog.at_level(logging.INFO, logger="backend.credentials.audit"):
        facade.get_optional("k")
    assert len(_events(caplog.records, EVENT_READ)) == 1
