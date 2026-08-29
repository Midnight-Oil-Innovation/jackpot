"""One-shot splice: add BYOP Catalog tab to frontend/pages/pipelines.py (B-BYOP-8)."""

import pathlib

path = pathlib.Path("frontend/pages/pipelines.py")
src = path.read_text()

# --- splice 1: add "BYOP Catalog" to the tabs list ---
OLD_TABS = """    launch_tab, monitor_tab = st.tabs(["Launch", "Monitor"])"""
NEW_TABS = (
    '    launch_tab, monitor_tab, tab_byop_catalog = st.tabs(["Launch", "Monitor", "BYOP Catalog"])'
)
result = src.replace(OLD_TABS, NEW_TABS)
assert result.count(NEW_TABS) == 1, "tabs splice failed or was not unique"

# --- splice 2: insert the catalog renderer before render() ---
OLD_FUNC = "def render() -> None:"
NEW_FUNC = (
    '''# ── BYOP Catalog tab (B-BYOP-8) ──────────────────────────────────────


def _fmt_date(iso: str | None) -> str:
    """ISO timestamp -> YYYY-MM-DD, or an em dash when absent."""
    return iso[:10] if iso else "\\u2014"


def _render_byop_catalog(client) -> None:
    st.subheader("BYOP Catalog")
    try:
        pipelines = client.get("/api/v1/byop/pipelines") or []
    except ApiError as exc:
        st.error(f"Failed to load BYOP pipelines: {exc.message}")
        st.stop()

    if not pipelines:
        st.info("No BYOP pipelines registered yet.")
        return

    st.dataframe(
        [
            {
                "Name": p.get("display_name") or p.get("name"),
                "Status": p.get("pipeline_status"),
                "Last Revalidated": _fmt_date(p.get("last_validated_at")),
            }
            for p in pipelines
        ],
        use_container_width=True,
        hide_index=True,
    )

    admin = is_platform_admin()
    for p in pipelines:
        with st.expander(p.get("display_name") or p.get("name")):
            st.markdown(
                f"- **Status**: {p.get('pipeline_status')}\\n"
                f"- **Last revalidated**: {_fmt_date(p.get('last_validated_at'))}\\n"
                f"- **Version**: {p.get('version')}\\n"
                f"- **Engine**: {p.get('engine_type')} {p.get('engine_version')}\\n"
                f"- **Source**: {p.get('source_url') or p.get('source_uploaded_uri') or '\\u2014'}"
                f" ({p.get('source_type')})\\n"
                f"- **License**: {p.get('license_spdx')}\\n"
                f"- **Registered**: {_fmt_date(p.get('registered_at'))}"
            )
            if p.get("description"):
                st.caption(p["description"])
            if admin:
                col_deact, col_arch = st.columns(2)
                with col_deact:
                    if st.button("Deactivate", key=f"byop.deact.{p['id']}"):
                        try:
                            client.post(f"/api/v1/byop/pipelines/{p['id']}/deactivate")
                            st.success("Pipeline deactivated.")
                            st.rerun()
                        except ApiError as exc:
                            st.error(f"Deactivate failed: {exc.message}")
                with col_arch:
                    if st.button("Archive", key=f"byop.arch.{p['id']}"):
                        try:
                            client.post(f"/api/v1/byop/pipelines/{p['id']}/archive")
                            st.success("Pipeline archived.")
                            st.rerun()
                        except ApiError as exc:
                            st.error(f"Archive failed: {exc.message}")


'''
    + OLD_FUNC
)
result2 = result.replace(OLD_FUNC, NEW_FUNC)
assert result2.count("def _render_byop_catalog") == 1, "func splice failed or was not unique"

# --- splice 3: wire the tab body ---
OLD_BODY = """    with monitor_tab:
        _render_monitor(client)"""
NEW_BODY = (
    OLD_BODY
    + """
    with tab_byop_catalog:
        _render_byop_catalog(client)"""
)
result3 = result2.replace(OLD_BODY, NEW_BODY)
assert result3.count(NEW_BODY) == 1, "body splice failed or was not unique"

# --- splice 4: import the admin-role helper ---
OLD_IMPORT = "from frontend.lib.api import ApiError, get_client"
NEW_IMPORT = OLD_IMPORT + "\nfrom frontend.lib.session import is_platform_admin"
result4 = result3.replace(OLD_IMPORT, NEW_IMPORT)
assert result4.count(NEW_IMPORT) == 1, "import splice failed or was not unique"

path.write_text(result4)
print("Done.")
