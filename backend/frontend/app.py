"""
JACKPOT Streamlit entrypoint.

Run with ``uv run streamlit run frontend/app.py``. Streamlit auto-loads
every file in ``frontend/pages/`` as a sidebar page, so this entrypoint
is intentionally minimal — it only renders the landing splash and
surfaces the current user (if the API is reachable).

The researcher pages are the only ones shipped now; admin pages
(``lab_director``, ``platform_admin``, ``archive_requests``, ``billing``)
are deferred to Month 3 and intentionally absent from the
``pages/`` directory.
"""

from __future__ import annotations

import streamlit as st

from frontend.lib.session import current_user


def main() -> None:
    st.set_page_config(
        page_title="JACKPOT",
        page_icon="🧬",
        layout="wide",
    )

    me = current_user()
    st.title("JACKPOT")
    if me:
        st.caption(f"Signed in as **{me.get('name') or me.get('email')}**")
    else:
        st.warning(
            "API unreachable — start the backend (`uv run uvicorn backend.main:app`) "
            "and refresh. The Streamlit pages only render live data."
        )

    st.markdown(
        "Pick a page from the sidebar:\n\n"
        "- **Dashboard** — your recent samples, access requests, pipeline runs\n"
        "- **Search samples** — full filter + bulk select + action bar\n"
        "- **My samples** — samples you own\n"
        "- **Upload samples** — drag-and-drop ingest with tier preview\n"
        "- **Metadata entry** — edit an existing sample's metadata\n"
        "- **Datasets** — analytical datasets (Month 3 placeholder)\n"
        "- **Pipelines** — launch + monitor + resume\n"
        "- **Access requests** — request + review access\n"
        "- **Notifications** — inbox (Month 3 placeholder)"
    )


if __name__ == "__main__":
    main()
else:
    main()
