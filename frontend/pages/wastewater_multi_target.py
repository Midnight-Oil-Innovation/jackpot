"""
Multi-target wastewater concentration panel (B-WW-ADV-1).

Reads the ``wastewater_target_concentration`` result table (landed in
B-CWB-SCHEMA-2, migration c871b28bbdab) directly and renders SARS-CoV-2,
RSV, and Influenza A concentration time-series side-by-side in three
columns, one chart per target.

No backend endpoint exists for this table yet (and adding one is out of
scope for B-WW-ADV-1), so this page connects to PostgreSQL directly via
``DATABASE_URL`` — the same variable the backend's ``database.py`` reads.
The engine is cached with ``st.cache_resource`` so reruns reuse one pool.
"""

from __future__ import annotations

import os

import altair as alt
import pandas as pd
import sqlalchemy as sa
import streamlit as st

st.set_page_config(page_title="Multi-Target Panel", page_icon="🧬", layout="wide")

# Canonical target labels as written by the concentration loaders
# (NCBI-taxonomy-style names, matching the OrganismNameEnum convention).
TARGETS = ["SARS-CoV-2", "RSV", "Influenza A"]

# pragma: allowlist nextline secret
_DEFAULT_DB_URL = "postgresql://jackpot:jackpot@localhost:5432/jackpot_db"


@st.cache_resource
def _engine() -> sa.Engine:
    return sa.create_engine(os.environ.get("DATABASE_URL", _DEFAULT_DB_URL), pool_pre_ping=True)


@st.cache_data(ttl=300)
def _fetch_concentrations() -> pd.DataFrame:
    query = sa.text(
        """
        SELECT target, concentration, concentration_unit, below_lod,
               collection_timestamp, sample_id, run_id
        FROM wastewater_target_concentration
        WHERE target IN :targets
        ORDER BY collection_timestamp
        """
    ).bindparams(sa.bindparam("targets", expanding=True))
    with _engine().connect() as conn:
        return pd.read_sql(query, conn, params={"targets": TARGETS})


def _target_chart(df: pd.DataFrame, target: str) -> alt.Chart:
    unit = df["concentration_unit"].dropna().unique()
    unit_label = unit[0] if len(unit) == 1 else "mixed units"
    return (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X("collection_timestamp:T", title="Collection date"),
            y=alt.Y("concentration:Q", title=f"Concentration ({unit_label})"),
            tooltip=[
                "collection_timestamp:T",
                "concentration:Q",
                "concentration_unit:N",
                "below_lod:N",
                "sample_id:N",
            ],
        )
        .properties(title=target, height=320)
    )


def main() -> None:
    st.title("Multi-target wastewater panel")
    st.caption(
        "Side-by-side concentration signals from "
        "`wastewater_target_concentration` (B-CWB-SCHEMA-2)."
    )

    try:
        df = _fetch_concentrations()
    except sa.exc.SQLAlchemyError as exc:
        st.error(f"Database unreachable or table missing: {exc}")
        return

    cols = st.columns(3)
    for col, target in zip(cols, TARGETS, strict=True):
        with col:
            target_df = df[df["target"] == target]
            if target_df.empty:
                st.info(f"No {target} concentration rows yet.")
                continue
            st.altair_chart(_target_chart(target_df, target), use_container_width=True)
            n_lod = int(target_df["below_lod"].sum())
            st.caption(f"{len(target_df)} measurements · {n_lod} below LOD")


main()
