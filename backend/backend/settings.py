# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Convenience accessor for the live :class:`backend.config.Settings` instance.

JACKPOT's pydantic-settings layer lives in :mod:`backend.config`, which
exposes the :class:`Settings` model and an ``lru_cache``-wrapped
``get_settings()`` factory. Most call-sites that need a setting hit
``get_settings()`` directly. Modules that only need to read a handful of
values once at import time (e.g. ``backend.immune.sec.dp_aggregator``)
prefer the simpler ``from backend.settings import settings`` shape.

This module is a thin shim that resolves ``settings`` to the cached
``Settings`` instance so the upper-case attribute access expected by
external specs (``settings.DP_EPSILON``) maps onto the lower-case
pydantic field (``dp_epsilon``). Pydantic field names are lower-case
by convention; exposing both spellings here keeps the public Python
surface ergonomic without forking the underlying field naming.
"""

from __future__ import annotations

from typing import Any

from backend.config import Settings, get_settings


class _SettingsProxy:
    """Read-only proxy that exposes both lower- and upper-case attribute names.

    ``settings.DP_EPSILON`` and ``settings.dp_epsilon`` resolve to the same
    underlying pydantic field on the cached :class:`Settings` instance.
    Attribute lookup falls through to the wrapped instance so any other
    field (env, database_url, …) keeps working unchanged.
    """

    __slots__ = ("_inner",)

    def __init__(self, inner: Settings) -> None:
        object.__setattr__(self, "_inner", inner)

    def __getattr__(self, name: str) -> Any:
        inner = object.__getattribute__(self, "_inner")
        if hasattr(inner, name):
            return getattr(inner, name)
        lowered = name.lower()
        if hasattr(inner, lowered):
            return getattr(inner, lowered)
        raise AttributeError(name)


settings: Any = _SettingsProxy(get_settings())

__all__ = ["settings"]
