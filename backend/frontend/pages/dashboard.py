"""
Personal dashboard — three panels: recent samples, pending access
requests, active pipeline runs.

Every API call is wrapped in ``_safe_call`` so a router that is not yet
online (notifications, pipelines under construction) degrades to a
labelled empty state rather than a stack trace. The same pattern is
reused by the other researcher pages.
"""

from __future__ import annotations

import streamlit as st

from frontend.components.badges import (
    render_badge,
    run_status_badge,
    scrub_badge,
    sharing_badge,
    tier_badge,
)
from frontend.lib.api import ApiError, get_client
from frontend.lib.session import current_user, my_user_id

PAGE_TITLE = "Dashboard"
RECENT_LIMIT = 10


def _safe_call(label: str, fn, *args, **kwargs):
    """Run ``fn`` and surface errors as a Streamlit banner, not a crash."""
    try:
        return fn(*args, **kwargs)
    except ApiError as exc:
        if exc.status_code in (404, 501) or exc.code in ("NOT_IMPLEMENTED", "NETWORK"):
            st.info(f"{label}: endpoint not yet available — {exc.message}")
        else:
            st.error(f"{label}: {exc.message}")
        return None


def _render_recent_samples(client) -> None:
    st.subheader("Recent samples")
    uid = my_user_id()
    if uid is None:
        st.caption("Sign in to see your samples.")
        return
    data = _safe_call(
        "Recent samples",
        client.get,
        "/api/v1/samples/",
        params={
            "owner_id": uid,
            "per_page": RECENT_LIMIT,
            "sort_by": "ingest_timestamp",
            "sort_dir": "desc",
        },
    )
    rows = (data or {}).get("results", []) if isinstance(data, dict) else (data or [])
    if not rows:
        st.caption("No samples yet — upload from the **Upload samples** page.")
        return
    for row in rows[:RECENT_LIMIT]:
        cols = st.columns([3, 2, 2, 2])
        cols[0].markdown(f"**{row.get('sample_id') or '—'}** · {row.get('organism_name') or '—'}")
        with cols[1]:
            render_badge(tier_badge(row.get("quality_status")))
        with cols[2]:
            render_badge(sharing_badge(row.get("sharing_level")))
        with cols[3]:
            render_badge(scrub_badge(row.get("scrub_status")))


def _render_pending_access(client) -> None:
    st.subheader("Pending access requests")
    data = _safe_call(
        "Access requests",
        client.get,
        "/api/v1/sample-access/requests",
        params={"requester_id": "me", "status": "PENDING"},
    )
    rows = data if isinstance(data, list) else (data or {}).get("results", [])
    if not rows:
        st.caption("No pending access requests.")
        return
    for row in rows[:RECENT_LIMIT]:
        cols = st.columns([3, 2, 3])
        cols[0].markdown(f"Request **#{row.get('id')}** on sample {row.get('sample_id')}")
        cols[1].markdown(f"Status: **{row.get('status')}**")
        cols[2].caption(f"Auto-approves: {row.get('auto_approve_after') or 'not scheduled'}")


def _render_active_runs(client) -> None:
    st.subheader("Active pipeline runs")
    uid = my_user_id()
    if uid is None:
        return
    data = _safe_call(
        "Pipeline runs",
        client.get,
        "/api/v1/pipelines/",
        params={"user_id": uid, "per_page": RECENT_LIMIT},
    )
    rows = (data or {}).get("results", []) if isinstance(data, dict) else (data or [])
    if not rows:
        st.caption("No active runs.")
        return
    for row in rows[:RECENT_LIMIT]:
        cols = st.columns([3, 2, 3])
        cols[0].markdown(f"**{row.get('pipeline_name')}** · run `{row.get('run_id')}`")
        with cols[1]:
            render_badge(run_status_badge(row.get("status")))
        cols[2].caption(
            f"Samples: {len(row.get('sample_ids') or [])} · "
            f"launched {row.get('launched_at') or '—'}"
        )


def render() -> None:
    st.title(PAGE_TITLE)

    me = current_user()
    if not me:
        st.warning(
            "Unable to reach the JACKPOT API. Start the backend, then "
            "refresh — the dashboard pulls live data only."
        )
        return

    st.caption(f"Welcome back, {me.get('name') or me.get('email')}.")
    client = get_client()

    left, right = st.columns(2)
    with left:
        _render_recent_samples(client)
        st.divider()
        _render_active_runs(client)
    with right:
        _render_pending_access(client)


render()
