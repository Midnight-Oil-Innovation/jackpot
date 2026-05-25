"""
Wastewater lineage-abundance dashboard (B-WW-1).

Pulls Freyja-shaped ``wastewater_lineage_abundance`` rows from
``GET /api/v1/wastewater/lineage-abundance`` and renders a stacked-area
time-series per sampling site, with sidebar filters for date range,
site, and lineage. Summary panel + collapsible sample table below the
chart.

Empty/error states follow the same pattern as ``dashboard.py``:
``_safe_call`` wraps every API hit, and missing data shows a friendly
banner rather than a stack trace.
"""

from __future__ import annotations

from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from frontend.lib.api import ApiError, get_client
from frontend.lib.session import current_user

PAGE_TITLE = "Wastewater lineage abundance"
SS_DATE_FROM = "ww.date_from"
SS_DATE_TO = "ww.date_to"
SS_SITES = "ww.sites"
SS_TOP_N = "ww.top_n"
SS_LINEAGES = "ww.lineages"


def _safe_call(label: str, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ApiError as exc:
        if exc.status_code in (404, 501) or exc.code in ("NOT_IMPLEMENTED", "NETWORK"):
            st.info(f"{label}: endpoint not yet available — {exc.message}")
        else:
            st.error(f"{label}: {exc.message}")
        return None


def _init_state() -> None:
    today = date.today()
    st.session_state.setdefault(SS_DATE_FROM, today - timedelta(days=30))
    st.session_state.setdefault(SS_DATE_TO, today)
    st.session_state.setdefault(SS_SITES, [])
    st.session_state.setdefault(SS_TOP_N, 5)
    st.session_state.setdefault(SS_LINEAGES, [])


def _render_date_and_site_filters(available_sites: list[str]) -> dict:
    st.sidebar.header("Filters")
    date_from = st.sidebar.date_input(
        "Collected from", value=st.session_state[SS_DATE_FROM], key=SS_DATE_FROM
    )
    date_to = st.sidebar.date_input(
        "Collected to", value=st.session_state[SS_DATE_TO], key=SS_DATE_TO
    )
    sites = st.sidebar.multiselect(
        "Sampling site(s)",
        options=available_sites,
        default=st.session_state[SS_SITES] or available_sites,
        key=SS_SITES,
        help="WWTP name from the underlying WastewaterSample row.",
    )
    return {"date_from": date_from, "date_to": date_to, "sites": sites}


def _render_lineage_filters(available_lineages: list[str]) -> dict:
    st.sidebar.divider()
    top_n = st.sidebar.number_input(
        "Top-N lineages (auto-pick)",
        min_value=1,
        max_value=20,
        value=int(st.session_state[SS_TOP_N]),
        step=1,
        key=SS_TOP_N,
        help=(
            "Sorts lineages by mean abundance across the selected window "
            "and shows the top N. Ignored if explicit lineages are picked."
        ),
    )
    lineages = st.sidebar.multiselect(
        "Or pick explicit lineage(s)",
        options=available_lineages,
        default=[ln for ln in st.session_state[SS_LINEAGES] if ln in available_lineages],
        key=SS_LINEAGES,
    )
    return {"top_n": int(top_n), "lineages": list(lineages)}


def _fetch_sites(client) -> list[str]:
    data = _safe_call("Wastewater sites", client.get, "/api/v1/wastewater/sites")
    if not data:
        return []
    return [s for s in data if s]


def _fetch_rows(client, filters: dict) -> list[dict]:
    base_params: dict = {
        "date_from": filters["date_from"].isoformat() if filters["date_from"] else None,
        "date_to": filters["date_to"].isoformat() if filters["date_to"] else None,
    }
    # The endpoint accepts one site at a time; loop and concat so the
    # multiselect can drive a Site A + Site B union. With one site
    # selected this collapses to a single call.
    sites = filters["sites"] or [None]
    rows: list[dict] = []
    for site in sites:
        call_params = dict(base_params)
        if site:
            call_params["site"] = site
        data = _safe_call(
            "Wastewater lineage abundance",
            client.get,
            "/api/v1/wastewater/lineage-abundance",
            params={k: v for k, v in call_params.items() if v is not None},
        )
        if isinstance(data, list):
            rows.extend(data)
    return rows


def _select_lineages(df: pd.DataFrame, lineage_filters: dict) -> list[str]:
    if lineage_filters["lineages"]:
        return [ln for ln in lineage_filters["lineages"] if ln in set(df["lineage"])]
    means = df.groupby("lineage")["abundance"].mean().sort_values(ascending=False)
    return means.head(lineage_filters["top_n"]).index.tolist()


def _render_chart(df: pd.DataFrame, sites: list[str], date_from: date, date_to: date) -> None:
    if df.empty:
        st.info("No lineages match the current filter selection.")
        return
    site_label = ", ".join(sites) if sites else "all sites"
    chart = (
        alt.Chart(df.assign(date_collected=pd.to_datetime(df["date_collected"])))
        .mark_area(opacity=0.85)
        .encode(
            x=alt.X("date_collected:T", title="Collection date"),
            y=alt.Y(
                "sum(abundance):Q",
                stack="normalize",
                axis=alt.Axis(format="%"),
                title="Fraction",
            ),
            color=alt.Color("lineage:N", title="Lineage"),
            tooltip=[
                alt.Tooltip("sample_id:N", title="Sample"),
                alt.Tooltip("date_collected:T", title="Collected"),
                alt.Tooltip("lineage:N", title="Lineage"),
                alt.Tooltip("abundance:Q", format=".3f", title="Fraction"),
                alt.Tooltip("site:N", title="Site"),
            ],
        )
        .properties(
            title=f"Lineage abundance — {site_label} ({date_from} → {date_to})",
            height=420,
        )
    )
    st.altair_chart(chart, use_container_width=True)


def _render_summary(df: pd.DataFrame, date_from: date, date_to: date) -> None:
    sample_count = df["sample_id"].nunique()
    lineage_count = df["lineage"].nunique()
    means = df.groupby("lineage")["abundance"].mean().sort_values(ascending=False)
    top_lineage = means.index[0] if not means.empty else "—"
    top_frac = float(means.iloc[0]) if not means.empty else 0.0

    cols = st.columns(4)
    cols[0].metric("Samples in window", sample_count)
    cols[1].metric("Distinct lineages", lineage_count)
    cols[2].metric("Most abundant", top_lineage, f"{top_frac:.1%} mean")
    cols[3].metric("Date range", f"{date_from} → {date_to}")


def _render_sample_table(df: pd.DataFrame) -> None:
    with st.expander("Underlying wastewater samples"):
        per_sample = (
            df.groupby(["sample_id", "date_collected", "site"])
            .agg(lineage_count=("lineage", "nunique"))
            .reset_index()
            .sort_values(["date_collected", "sample_id"])
        )
        st.dataframe(per_sample, use_container_width=True, hide_index=True)


def render() -> None:
    st.title(PAGE_TITLE)
    me = current_user()
    if not me:
        st.warning(
            "Unable to reach the JACKPOT API. Start the backend, then "
            "refresh — the dashboard pulls live data only."
        )
        return

    _init_state()
    client = get_client()

    available_sites = _fetch_sites(client)
    site_filters = _render_date_and_site_filters(available_sites)

    if not available_sites:
        st.info(
            "No wastewater samples are visible to your account. Load demo "
            "data with `uv run python3 backend/scripts/seed_wastewater_demo.py` "
            "or upload wastewater samples first."
        )
        # Render the lineage panel with no options so the sidebar layout
        # is stable across empty / populated states.
        _render_lineage_filters([])
        return

    rows = _fetch_rows(client, site_filters)
    available_lineages = sorted({ln for r in rows if (ln := r.get("lineage"))})
    lineage_filters = _render_lineage_filters(available_lineages)

    if not rows:
        st.info(
            "No wastewater samples in the selected window. Adjust filters or "
            "check that seed data has been loaded."
        )
        return

    df = pd.DataFrame(rows)
    keep = _select_lineages(df, lineage_filters)
    df_top = df[df["lineage"].isin(keep)]

    _render_summary(df, site_filters["date_from"], site_filters["date_to"])
    st.divider()
    _render_chart(
        df_top,
        site_filters["sites"],
        site_filters["date_from"],
        site_filters["date_to"],
    )
    _render_sample_table(df)


render()
