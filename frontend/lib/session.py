"""
Session helpers — fetch current user + resolve "me" shortcuts.

Streamlit re-runs the whole script on every interaction. Cache the
``/users/me`` lookup in ``st.session_state`` so navigating between pages
does not fire a fresh request for every re-render. The cache key is the
client's base_url so role switches across environments still invalidate.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from frontend.lib.api import ApiError, get_client


def current_user(force_refresh: bool = False) -> dict[str, Any] | None:
    """Resolve the logged-in user once per Streamlit session.

    Returns ``None`` if the server is unreachable or the session is
    anonymous — pages decide how to render that case (login prompt vs.
    empty state).
    """
    cache_key = "_jackpot_me"
    if not force_refresh and cache_key in st.session_state:
        return st.session_state[cache_key]

    try:
        me = get_client().get("/api/v1/users/me")
    except ApiError:
        st.session_state[cache_key] = None
        return None

    st.session_state[cache_key] = me
    return me


def my_user_id() -> int | None:
    me = current_user()
    return me["id"] if me else None


def clear_session_cache() -> None:
    for k in ("_jackpot_me",):
        st.session_state.pop(k, None)
