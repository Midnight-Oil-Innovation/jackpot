"""
Analytical datasets — Month 2 placeholder.

The datasets router is a 5-line stub; the full implementation (list,
create-from-selection, export to CSV / BCO / sample manifest, Microreact
link) is Month 3 scope. This page renders the UX scaffolding so the
navigation stays coherent and bookmarks survive the Month 3 cutover.

Selection pickup: if the Search page stashed IDs under
``search.selected_ids``, show them here as a "ready to save as dataset"
preview with a disabled button. Once ``POST /api/v1/datasets/`` lands,
only the button body has to change.
"""

from __future__ import annotations

import streamlit as st

from frontend.lib.api import ApiError, get_client

PAGE_TITLE = "Datasets"


def _fetch_datasets(client) -> list[dict]:
    try:
        data = client.get("/api/v1/datasets/")
    except ApiError as exc:
        if exc.status_code in (404, 501):
            return []
        st.error(f"Datasets endpoint returned {exc.status_code}: {exc.message}")
        return []
    if isinstance(data, list):
        return data
    return data.get("results", []) if isinstance(data, dict) else []


def render() -> None:
    st.title(PAGE_TITLE)
    st.info(
        "Datasets are part of Month 3 scope. This page renders the layout "
        "now so the researcher flow (Search → selection → dataset) keeps "
        "its place; endpoints wire up when the datasets router ships."
    )

    client = get_client()
    rows = _fetch_datasets(client)

    selected = st.session_state.get("search.selected_ids") or set()
    with st.expander(f"Selected from Search · {len(selected)} samples", expanded=bool(selected)):
        if not selected:
            st.caption(
                "Make a selection on **Search samples** — the IDs travel here via session_state."
            )
        else:
            st.write(sorted(selected)[:100])
            st.text_input("Dataset name", key="datasets.new_name")
            st.button(
                "Create dataset",
                disabled=True,
                help="Wires up when POST /api/v1/datasets/ ships.",
                key="datasets.create_btn",
            )

    st.divider()
    st.subheader("Your datasets")
    if not rows:
        st.caption("No datasets yet — none will load until the Month 3 router is live.")
        return
    for r in rows:
        cols = st.columns([3, 2, 2])
        cols[0].markdown(f"**{r.get('display_name') or r.get('name')}**")
        cols[1].caption(f"{r.get('sample_count', '?')} samples")
        cols[2].caption(r.get("updated_at") or "")


render()
