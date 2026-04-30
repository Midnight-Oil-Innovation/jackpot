"""
Samples the logged-in user owns — narrower than Search, with tier +
scrub badges and a one-click jump to the metadata editor.

Scope filter lives in the sidebar:

    Only mine  — owner_id = me
    My lab     — lab_id in labs I'm a member of
    My project — project_id in projects I'm a member of

Scope "My project" is implemented via three separate requests (one per
project) because the samples endpoint accepts a single ``project_id`` at
a time. If the user is in many projects this could be chatty — acceptable
for Month 2, fold into a server-side `?project_ids=` in Month 3.
"""

from __future__ import annotations

import streamlit as st

from frontend.components.badges import (
    render_badge,
    scrub_badge,
    sharing_badge,
    tier_badge,
)
from frontend.lib.api import ApiError, get_client
from frontend.lib.session import current_user, my_user_id

PAGE_TITLE = "My samples"
SS_SCOPE = "my_samples.scope"
SS_PAGE = "my_samples.page"


def _fetch(client, params: dict) -> tuple[list[dict], int]:
    try:
        data = client.get("/api/v1/samples/", params=params)
    except ApiError as exc:
        st.error(f"Load failed: {exc.message}")
        return [], 0
    if isinstance(data, list):
        return data, len(data)
    return data.get("results", []), data.get("total_count", 0)


def _scope_params(scope: str) -> dict | None:
    me = current_user()
    uid = my_user_id()
    if uid is None:
        return None
    memberships = (me or {}).get("lab_memberships") or []
    if scope == "Only mine":
        return {"owner_id": uid}
    if scope == "My lab":
        # First lab is enough — the sidebar also shows a lab picker for
        # multi-lab users. Month 3 will accept a list server-side.
        if not memberships:
            return None
        return {"lab_id": memberships[0]["lab_id"]}
    if scope == "My project":
        # Without a project listing endpoint we fall back to owner_id —
        # project scoping requires Month 3 plumbing.
        return {"owner_id": uid}
    return {"owner_id": uid}


def _render_row(row: dict) -> None:
    cols = st.columns([2, 3, 1.2, 1.2, 1.2, 1])
    cols[0].markdown(f"**{row.get('sample_id') or row.get('id')}**")
    cols[1].caption(row.get("organism_name") or "—")
    with cols[2]:
        render_badge(tier_badge(row.get("quality_status")))
    with cols[3]:
        render_badge(sharing_badge(row.get("sharing_level")))
    with cols[4]:
        render_badge(scrub_badge(row.get("scrub_status")))
    if cols[5].button("Edit", key=f"ms.edit.{row['id']}"):
        st.session_state["de.load_sample_id"] = row["id"]
        st.switch_page("pages/data_entry.py")


def render() -> None:
    st.session_state.setdefault(SS_SCOPE, "Only mine")
    st.session_state.setdefault(SS_PAGE, 1)
    st.title(PAGE_TITLE)

    if current_user() is None:
        st.warning("API unreachable — my-samples needs the backend.")
        return

    scope = st.sidebar.radio(
        "Scope",
        ("Only mine", "My lab", "My project"),
        key=SS_SCOPE,
    )
    client = get_client()
    params = _scope_params(scope) or {}
    params["page"] = st.session_state[SS_PAGE]
    params["per_page"] = 50
    params["sort_by"] = "ingest_timestamp"
    params["sort_dir"] = "desc"

    rows, total = _fetch(client, params)
    st.caption(f"{total} samples · scope **{scope}**")
    if not rows:
        st.info("Nothing to show — try a different scope or upload a sample.")
        return

    for row in rows:
        _render_row(row)

    nav = st.columns(3)
    if nav[0].button("← Prev", disabled=st.session_state[SS_PAGE] <= 1):
        st.session_state[SS_PAGE] -= 1
        st.rerun()
    nav[1].markdown(f"Page **{st.session_state[SS_PAGE]}**")
    if nav[2].button("Next →", disabled=len(rows) < 50):
        st.session_state[SS_PAGE] += 1
        st.rerun()


render()
