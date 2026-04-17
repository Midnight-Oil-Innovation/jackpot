"""
Sample-access request console.

Two tabs:

- **My requests** — requester view. Filterable by status. Shows
  auto-approve countdown so the researcher knows when the 7-day window
  elapses.
- **Incoming** — Lab Director view. Lists PENDING requests against
  samples in labs where the caller is a director. Approve/deny land on
  ``POST /api/v1/sample-access/requests/{id}/{approve|deny}`` from
  Session O.

The Lab Director tab is suppressed entirely for users who are not in
any director role; this avoids a confusing empty view.
"""

from __future__ import annotations

import streamlit as st

from frontend.lib.api import ApiError, get_client
from frontend.lib.session import is_platform_admin, my_director_lab_ids

PAGE_TITLE = "Access requests"

STATUS_CHOICES = (
    "ALL",
    "PENDING",
    "APPROVED",
    "AUTO_APPROVED",
    "DENIED",
    "EXPIRED",
    "MOOT",
)


def _fetch(client, params: dict) -> list[dict]:
    try:
        data = client.get("/api/v1/sample-access/requests", params=params)
    except ApiError as exc:
        st.error(f"Access request load failed: {exc.message}")
        return []
    if isinstance(data, list):
        return data
    return data.get("results", []) if isinstance(data, dict) else []


def _render_my_tab(client) -> None:
    status = st.selectbox("Status", STATUS_CHOICES, key="ar.my.status")
    params: dict = {"requester_id": "me"}
    if status != "ALL":
        params["status"] = status
    rows = _fetch(client, params)
    if not rows:
        st.caption("No requests match.")
        return
    for row in rows:
        with st.container(border=True):
            cols = st.columns([3, 2, 3])
            cols[0].markdown(f"Request **#{row.get('id')}** · sample `{row.get('sample_id')}`")
            cols[1].markdown(f"Status: **{row.get('status')}**")
            cols[2].caption(
                f"Requested {row.get('requested_at') or '—'} · "
                f"auto-approve {row.get('auto_approve_after') or '—'}"
            )
            if row.get("justification"):
                st.caption(row["justification"])


def _approve(client, req_id: int, duration_days: int) -> None:
    try:
        client.post(
            f"/api/v1/sample-access/requests/{req_id}/approve",
            json_body={"requested_duration_days": duration_days},
        )
        st.success(f"Approved #{req_id} for {duration_days} days.")
    except ApiError as exc:
        st.error(f"Approve failed: {exc.message}")


def _deny(client, req_id: int, reason: str) -> None:
    try:
        client.post(
            f"/api/v1/sample-access/requests/{req_id}/deny",
            json_body={"denial_reason": reason or None},
        )
        st.success(f"Denied #{req_id}.")
    except ApiError as exc:
        st.error(f"Deny failed: {exc.message}")


def _render_incoming_tab(client) -> None:
    lab_ids = my_director_lab_ids()
    admin = is_platform_admin()
    if not lab_ids and not admin:
        st.info("Not a Lab Director — nothing to review here.")
        return
    if admin and not lab_ids:
        st.caption("Platform Admin view: showing all labs.")
        rows = _fetch(client, {"status": "PENDING"})
    else:
        rows = []
        for lid in lab_ids:
            rows.extend(_fetch(client, {"status": "PENDING", "lab_id": lid}))
    if not rows:
        st.success("No incoming requests.")
        return
    seen = set()
    for row in rows:
        rid = row.get("id")
        if rid in seen:
            continue
        seen.add(rid)
        with st.container(border=True):
            st.markdown(
                f"Request **#{rid}** on sample `{row.get('sample_id')}` from "
                f"user `{row.get('requester_id')}`"
            )
            if row.get("justification"):
                st.caption(row["justification"])
            cols = st.columns([2, 2, 3])
            days = cols[0].number_input(
                "Grant duration (days)",
                min_value=1,
                max_value=365,
                value=int(row.get("requested_duration_days") or 90),
                step=1,
                key=f"ar.days.{rid}",
            )
            if cols[1].button("Approve", key=f"ar.appr.{rid}"):
                _approve(client, int(rid), int(days))
                st.rerun()
            reason = cols[2].text_input("Denial reason (optional)", key=f"ar.reason.{rid}")
            if cols[2].button("Deny", key=f"ar.deny.{rid}"):
                _deny(client, int(rid), reason)
                st.rerun()


def render() -> None:
    st.title(PAGE_TITLE)
    client = get_client()

    tab_mine, tab_incoming = st.tabs(["My requests", "Incoming (Lab Director)"])
    with tab_mine:
        _render_my_tab(client)
    with tab_incoming:
        _render_incoming_tab(client)


render()
