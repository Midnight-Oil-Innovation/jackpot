"""
Notification inbox — Month 2 placeholder.

The notifications router is a stub (Month 3 scope). This page assumes
the final endpoint will be ``GET /api/v1/notifications/`` and renders
whatever it returns. Until the router lands, users see an explanatory
banner and an empty list — no broken state, no exception.

When the router ships, the only change needed is removing the
placeholder banner; the render loop already handles the real envelope.
"""

from __future__ import annotations

import streamlit as st

from frontend.lib.api import ApiError, get_client

PAGE_TITLE = "Notifications"


def _fetch(client, params: dict) -> list[dict]:
    try:
        data = client.get("/api/v1/notifications/", params=params)
    except ApiError as exc:
        if exc.status_code in (404, 501):
            return []
        st.error(f"Notifications load failed: {exc.message}")
        return []
    if isinstance(data, list):
        return data
    return data.get("results", []) if isinstance(data, dict) else []


def _mark_all_read(client) -> None:
    try:
        client.post("/api/v1/notifications/mark_all_read")
        st.success("All notifications marked as read.")
    except ApiError as exc:
        st.warning(f"Mark-all-read not wired yet: {exc.message}")


def render() -> None:
    st.title(PAGE_TITLE)
    st.info(
        "Notifications router is a Month 3 feature. This page already speaks "
        "the expected envelope so it will light up the moment the endpoint ships."
    )
    client = get_client()

    cols = st.columns([1, 1, 3])
    only_unread = cols[0].toggle("Unread only", value=False, key="notif.only_unread")
    if cols[1].button("Mark all read"):
        _mark_all_read(client)

    params = {"unread": "true"} if only_unread else {}
    rows = _fetch(client, params)
    if not rows:
        st.caption("No notifications.")
        return
    for row in rows:
        unread = not row.get("read_at")
        badge = "🔵 " if unread else ""
        with st.container(border=True):
            st.markdown(f"{badge}**{row.get('title') or row.get('event_type')}**")
            st.caption(row.get("body") or "")
            if row.get("action_url"):
                st.link_button("Open", row["action_url"])


render()
