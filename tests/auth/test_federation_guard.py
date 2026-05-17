# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""FED-E: X-JACKPOT-Federation-Key auth guard tests.

Covers the shared guard in ``backend.auth.guards``:

  * ``authenticate_federation_peer`` — header → instance row or None
  * ``require_federation_peer`` — same, but raises 401 on failure

End-to-end peer-to-peer auth is also exercised by
``tests/test_federation_router_api.py``; these tests pin the guard's
contract directly so changes to it surface independently of the router.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers
from starlette.requests import Request

from backend.auth.guards import (
    FEDERATION_KEY_HEADER,
    authenticate_federation_peer,
    require_federation_peer,
)
from backend.credentials import _reset_backend, _set_backend
from backend.credentials.test_helpers import InMemoryBackend
from backend.database import execute_write

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_request(headers: dict[str, str] | None = None) -> Request:
    """Construct a minimal Starlette Request from header dict."""
    header_list = [
        (k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/federation/push",
        "headers": header_list,
        "query_string": b"",
    }
    request = Request(scope)
    # Starlette caches headers lazily; force materialisation so the dict
    # mirrors what the guard reads.
    assert isinstance(request.headers, Headers)
    return request


def _register_instance(
    *,
    name: str,
    api_key_secret_name: str,
    federation_enabled: bool = True,
) -> dict:
    rows = execute_write(
        """
        INSERT INTO federated_instances
            (name, base_url, role, federation_enabled,
             min_sharing_level_for_federation, api_key_secret_name)
        VALUES
            (:name, :base_url, CAST('peer' AS federation_role),
             :enabled, 'DISCOVERABLE', :secret_name)
        RETURNING *
        """,
        {
            "name": name,
            "base_url": f"https://{name}.example.test/",
            "enabled": federation_enabled,
            "secret_name": api_key_secret_name,
        },
    )
    return rows[0]


def _cleanup_instances() -> None:
    execute_write("DELETE FROM federated_instances")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fed_credentials():
    backend = InMemoryBackend()
    _set_backend(backend)
    yield backend
    _reset_backend()


@pytest.fixture(autouse=True)
def _isolate_instances():
    _cleanup_instances()
    yield
    _cleanup_instances()


# ---------------------------------------------------------------------------
# authenticate_federation_peer
# ---------------------------------------------------------------------------


def test_authenticate_returns_row_for_valid_key(fed_credentials):
    fed_credentials.set("fed/peer/key", "peer-secret")
    peer = _register_instance(name="peer", api_key_secret_name="fed/peer/key")

    request = _build_request({FEDERATION_KEY_HEADER: "peer-secret"})
    row = authenticate_federation_peer(request)

    assert row is not None
    assert row["id"] == peer["id"]
    assert row["name"] == "peer"


def test_authenticate_returns_none_when_header_missing(fed_credentials):
    fed_credentials.set("fed/peer/key", "peer-secret")
    _register_instance(name="peer", api_key_secret_name="fed/peer/key")

    request = _build_request({})
    assert authenticate_federation_peer(request) is None


def test_authenticate_returns_none_for_wrong_key(fed_credentials):
    fed_credentials.set("fed/peer/key", "peer-secret")
    _register_instance(name="peer", api_key_secret_name="fed/peer/key")

    request = _build_request({FEDERATION_KEY_HEADER: "wrong-secret"})
    assert authenticate_federation_peer(request) is None


def test_authenticate_skips_disabled_instances(fed_credentials):
    """A disabled partner cannot authenticate even with the correct key."""
    fed_credentials.set("fed/peer/key", "peer-secret")
    _register_instance(
        name="peer",
        api_key_secret_name="fed/peer/key",
        federation_enabled=False,
    )

    request = _build_request({FEDERATION_KEY_HEADER: "peer-secret"})
    assert authenticate_federation_peer(request) is None


def test_authenticate_skips_instances_with_missing_secret(fed_credentials):
    """A row pointing at a non-existent secret is skipped, not crashed on."""
    _register_instance(name="orphan", api_key_secret_name="fed/orphan/missing")

    request = _build_request({FEDERATION_KEY_HEADER: "any-value"})
    assert authenticate_federation_peer(request) is None


def test_authenticate_matches_correct_instance_among_many(fed_credentials):
    """With multiple enabled partners, the matching row is returned."""
    fed_credentials.set("fed/a/key", "a-secret")
    fed_credentials.set("fed/b/key", "b-secret")
    fed_credentials.set("fed/c/key", "c-secret")
    _register_instance(name="a", api_key_secret_name="fed/a/key")
    b_peer = _register_instance(name="b", api_key_secret_name="fed/b/key")
    _register_instance(name="c", api_key_secret_name="fed/c/key")

    request = _build_request({FEDERATION_KEY_HEADER: "b-secret"})
    row = authenticate_federation_peer(request)

    assert row is not None
    assert row["id"] == b_peer["id"]
    assert row["name"] == "b"


# ---------------------------------------------------------------------------
# require_federation_peer
# ---------------------------------------------------------------------------


def test_require_returns_row_on_match(fed_credentials):
    fed_credentials.set("fed/peer/key", "peer-secret")
    peer = _register_instance(name="peer", api_key_secret_name="fed/peer/key")

    request = _build_request({FEDERATION_KEY_HEADER: "peer-secret"})
    row = require_federation_peer(request)

    assert row["id"] == peer["id"]


def test_require_raises_401_when_header_missing(fed_credentials):
    request = _build_request({})

    with pytest.raises(HTTPException) as exc_info:
        require_federation_peer(request)

    assert exc_info.value.status_code == 401
    assert "federation key" in exc_info.value.detail.lower()


def test_require_raises_401_for_wrong_key(fed_credentials):
    fed_credentials.set("fed/peer/key", "peer-secret")
    _register_instance(name="peer", api_key_secret_name="fed/peer/key")

    request = _build_request({FEDERATION_KEY_HEADER: "wrong-secret"})

    with pytest.raises(HTTPException) as exc_info:
        require_federation_peer(request)

    assert exc_info.value.status_code == 401
