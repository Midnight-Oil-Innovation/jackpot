# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Override the workspace-root autouse fixtures for pure-router unit tests.

The router tests under this directory use FastAPI dependency overrides
plus an in-memory SQLite engine; they do not need the Postgres
testcontainer or the alembic upgrade that the parent ``tests/conftest.py``
runs as session-scoped autouse fixtures. We no-op both here so the suite
runs without Docker and without DB setup overhead (mirrors the pattern
in ``tests/wastewater/conftest.py``).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(scope="session", autouse=True)
def initialize_test_db() -> Iterator[None]:
    yield


@pytest.fixture(autouse=True)
def override_settings() -> Iterator[None]:
    yield


@pytest.fixture
def authz_grants(monkeypatch):
    """Run the real authorization engine against stubbed database lookups.

    The router tests here use in-memory SQLite and never start Postgres, so
    ``load_principal`` and the scope resolvers — the only parts of the guard
    that touch a database — are stubbed. Everything else is the production
    path: the real ``permit()``, the real ``LADDER_POLICIES``. That matters
    for BYOP, where the registrant rung is an attribute-policy; a fake
    ``_may_manage`` would have asserted the test's copy of the rule rather
    than the rule.

    Usage: ``authz_grants(user_id, [("pipeline:register_custom", scope)])``.
    Call it once per test with every principal the test drives.
    """
    from backend.auth import guards
    from backend.authz import CapabilityGrant, Principal, PrincipalKind, scope_uri

    issued: dict[str, list[tuple[str, str]]] = {}

    def _load(user_id, **kwargs):
        return Principal(
            kind=PrincipalKind.HUMAN,
            id=str(user_id),
            on_behalf_of=None,
            grants=[
                CapabilityGrant(capability=c, scope_ref=s) for c, s in issued.get(str(user_id), [])
            ],
        )

    monkeypatch.setattr(guards, "load_principal", _load)
    monkeypatch.setattr(guards, "lab_resource_scope", lambda lid, **kw: scope_uri(org=1, lab=lid))
    monkeypatch.setattr(
        guards,
        "project_resource_scope",
        lambda pid, **kw: scope_uri(org=1, lab=1, project=pid),
    )

    def _grant(user_id, grants):
        issued[str(user_id)] = list(grants)

    _grant.scope_uri = scope_uri
    return _grant
