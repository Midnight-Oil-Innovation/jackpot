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
