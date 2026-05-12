# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Override the workspace-root autouse fixtures for pure-compute wastewater tests.

The mass-balance module is pure compute (no DB, no FastAPI). The parent
``tests/conftest.py`` spins up a Postgres testcontainer and runs alembic
migrations via ``initialize_test_db`` / ``override_settings`` autouse
fixtures. We override both with no-ops here so this directory's tests
run without Docker and without DB setup overhead.
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
