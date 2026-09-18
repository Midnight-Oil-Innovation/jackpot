# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""The lifespan shuts the scheduler down even when the app fails."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

import backend.main
from backend.config import get_settings
from backend.main import app, lifespan


async def test_scheduler_is_shut_down_when_the_app_raises(monkeypatch) -> None:
    """An exception escaping the app body must not skip scheduler.shutdown().

    Without the try/finally the shutdown call is a bare trailing statement:
    the exception propagates straight past it, the process keeps a live
    AsyncIOScheduler, and its jobs go on firing against a half-torn-down
    application.
    """
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    # get_settings is lru_cached and the autouse override_settings fixture
    # re-warms it before the test body runs, so the setenv above is inert
    # without this -- the lifespan would read the default True and register
    # all eleven jobs against the Mock.
    get_settings.cache_clear()
    fake = Mock()
    fake.running = True
    monkeypatch.setattr(backend.main, "scheduler", fake)

    with pytest.raises(RuntimeError, match="boom"):
        async with lifespan(app):
            raise RuntimeError("boom")

    # Load-bearing, and the anti-vacuity guard too: `fake` is reachable only
    # through the monkeypatch, so a lapsed patch leaves the real scheduler --
    # not started under SCHEDULER_ENABLED=false, hence `running` False and
    # shutdown correctly skipped -- and this assertion is the only thing that
    # would notice. pytest.raises alone passes either way.
    fake.shutdown.assert_called_once_with()
