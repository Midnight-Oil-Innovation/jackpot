"""
Sample search — full filter sidebar, bulk select, split action bar.

The selection set is stored under ``search.selected_ids`` in
``st.session_state`` so it survives pagination and filter changes (the
bulk select-all uses ``?select_all=true`` which returns IDs only, no
pagination — same contract the backend already implements).

External database search (NCBI/ENA/GISAID) is a Month 2 placeholder:
flip the toggle and you get an informational banner pointing at the
future ``/api/v1/external-search/`` endpoint. The toggle is wired now
so Month 3 only has to replace the placeholder body.
"""

from __future__ import annotations

import streamlit as st

from frontend.components.badges import (
    QUALITY_TIERS,
    SHARING_LEVELS,
    render_badge,
    scrub_badge,
    sharing_badge,
    tier_badge,
)
from frontend.lib.api import ApiError, get_client

PAGE_TITLE = "Search samples"
SS_SELECTED = "search.selected_ids"
SS_PAGE = "search.page"
SS_PER_PAGE = "search.per_page"
SS_EXTERNAL = "search.external"


SOURCE_TYPES = (
    "Human",
    "Animal",
    "Vector",
    "Wastewater",
    "Environmental",
    "Food",
    "Metagenomic",
)
SECTORS = ("clinical", "public_health", "research", "veterinary", "environmental")


def _init_state() -> None:
    st.session_state.setdefault(SS_SELECTED, set())
    st.session_state.setdefault(SS_PAGE, 1)
    st.session_state.setdefault(SS_PER_PAGE, 50)
    st.session_state.setdefault(SS_EXTERNAL, False)


def _render_sidebar() -> dict:
    st.sidebar.header("Filters")
    organism = st.sidebar.text_input("Organism name", key="search.organism")
    source_type = st.sidebar.selectbox(
        "Source type", ("",) + SOURCE_TYPES, key="search.source_type"
    )
    sector = st.sidebar.selectbox("Sector", ("",) + SECTORS, key="search.sector")
    quality = st.sidebar.selectbox("Quality tier", ("",) + QUALITY_TIERS, key="search.quality")
    sharing = st.sidebar.selectbox("Sharing level", ("",) + SHARING_LEVELS, key="search.sharing")
    lab = st.sidebar.number_input("Lab ID", min_value=0, value=0, step=1, key="search.lab_id")
    project = st.sidebar.number_input(
        "Project ID", min_value=0, value=0, step=1, key="search.project_id"
    )
    date_from = st.sidebar.date_input("Collected from", value=None, key="search.date_from")
    date_to = st.sidebar.date_input("Collected to", value=None, key="search.date_to")

    st.sidebar.divider()
    st.sidebar.toggle(
        "Include external databases (NCBI / ENA / GISAID)",
        key=SS_EXTERNAL,
        help="Month 2 placeholder — wires up when /api/v1/external-search/ lands.",
    )

    params: dict = {
        "page": st.session_state[SS_PAGE],
        "per_page": st.session_state[SS_PER_PAGE],
    }
    if organism:
        params["organism_name"] = organism
    if source_type:
        params["source_type"] = source_type
    if sector:
        params["sector"] = sector
    if quality:
        params["quality_status"] = quality
    if sharing:
        params["sharing_level"] = sharing
    if lab:
        params["lab_id"] = int(lab)
    if project:
        params["project_id"] = int(project)
    if date_from:
        params["date_from"] = str(date_from)
    if date_to:
        params["date_to"] = str(date_to)
    return params


def _fetch(client, params: dict) -> dict:
    try:
        data = client.get("/api/v1/samples/", params=params)
    except ApiError as exc:
        st.error(f"Search failed: {exc.message}")
        return {"results": [], "total_count": 0}
    if isinstance(data, list):
        return {"results": data, "total_count": len(data)}
    return data or {"results": [], "total_count": 0}


def _select_all(client, params: dict) -> None:
    """Select every row matching the current filters, ignoring pagination."""
    try:
        out = client.get(
            "/api/v1/samples/",
            params={
                **{k: v for k, v in params.items() if k not in ("page", "per_page")},
                "select_all": "true",
            },
        )
    except ApiError as exc:
        st.error(f"Select-all failed: {exc.message}")
        return
    ids = (out or {}).get("ids", [])
    st.session_state[SS_SELECTED] = set(ids)


def _render_action_bar() -> None:
    n = len(st.session_state[SS_SELECTED])
    if n == 0:
        st.caption("Select rows to enable actions.")
        return
    cols = st.columns(4)
    cols[0].button(
        f"Export CSV ({n})",
        use_container_width=True,
        disabled=True,
        help="Export flow lands in Session Q.",
    )
    cols[1].button(
        f"Launch pipeline ({n})",
        use_container_width=True,
        disabled=True,
        help="Use the **Pipelines** page — selection persists via session_state.",
    )
    cols[2].button(
        f"Add to dataset ({n})",
        use_container_width=True,
        disabled=True,
        help="Datasets router arrives in Month 3.",
    )
    cols[3].button(
        f"Request access ({n})",
        use_container_width=True,
        disabled=True,
        help="Fires bulk POST /sample-access/requests — wired in P-7.",
    )


def _render_row(row: dict) -> None:
    selected = st.session_state[SS_SELECTED]
    sid = row["id"]
    cols = st.columns([0.3, 2, 3, 1.5, 1.5, 1.5])
    checked = cols[0].checkbox(
        "",
        value=sid in selected,
        key=f"search.row.{sid}",
        label_visibility="collapsed",
    )
    if checked:
        selected.add(sid)
    else:
        selected.discard(sid)
    cols[1].markdown(f"**{row.get('sample_id') or sid}**")
    cols[2].caption(row.get("organism_name") or "—")
    with cols[3]:
        render_badge(tier_badge(row.get("quality_status")))
    with cols[4]:
        render_badge(sharing_badge(row.get("sharing_level")))
    with cols[5]:
        render_badge(scrub_badge(row.get("scrub_status")))


def render() -> None:
    _init_state()
    st.title(PAGE_TITLE)

    if st.session_state[SS_EXTERNAL]:
        st.info(
            "External database search (NCBI / ENA / GISAID) arrives in Month 3 "
            "via `/api/v1/external-search/`. The toggle is here so bookmarks and "
            "state plumbing work the day it ships."
        )

    client = get_client()
    params = _render_sidebar()
    page = st.session_state[SS_PAGE]

    top = st.container()
    with top:
        cols = st.columns([1, 1, 3])
        if cols[0].button("Select all matches", use_container_width=True):
            _select_all(client, params)
        if cols[1].button("Clear selection", use_container_width=True):
            st.session_state[SS_SELECTED] = set()
        cols[2].caption(f"Page {page} · {len(st.session_state[SS_SELECTED])} selected")

    body = _fetch(client, params)
    results = body.get("results", []) if isinstance(body, dict) else body
    total = body.get("total_count", len(results)) if isinstance(body, dict) else len(results)

    st.caption(f"{total} matching samples")
    if not results:
        st.info("No samples match — loosen the filters or clear them.")
        return

    for row in results:
        _render_row(row)

    st.divider()
    _render_action_bar()

    st.divider()
    nav = st.columns(4)
    if nav[0].button("← Prev", disabled=page <= 1):
        st.session_state[SS_PAGE] = max(1, page - 1)
        st.rerun()
    nav[1].markdown(f"Page **{page}**")
    if nav[2].button("Next →", disabled=len(results) < st.session_state[SS_PER_PAGE]):
        st.session_state[SS_PAGE] = page + 1
        st.rerun()


render()
