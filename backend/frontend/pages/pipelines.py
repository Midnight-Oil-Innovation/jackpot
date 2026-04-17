"""
Pipeline launcher + 4-tab monitor + resume + MultiQC iframe.

Launch dialog
-------------

``pipeline_catalog`` rows are not yet exposed by a dedicated endpoint,
so the launcher accepts a pipeline_id directly and rebuilds the
compatibility warnings from the launch response. When the catalog list
endpoint lands in Month 3, swap the number_input for a selectbox —
nothing else changes.

Monitor view
------------

One run is loaded at a time, addressed by ``run_id``. Four tabs:

- Overview — status, compatibility report, MultiQC embed
- Tasks — paginated pipeline_tasks list
- Events — paginated pipeline_events list
- Files — raw list of result URIs (stored on the run row)

Resume button is shown only for ``status == 'FAILED'`` and posts to
``POST /api/v1/pipelines/{run_id}/resume``.
"""

from __future__ import annotations

import streamlit as st

from frontend.components.badges import render_badge, run_status_badge
from frontend.lib.api import ApiError, get_client

PAGE_TITLE = "Pipelines"
SS_RUN_ID = "pipelines.run_id"


def _fetch_run(client, run_id: str) -> dict | None:
    try:
        return client.get(f"/api/v1/pipelines/{run_id}")
    except ApiError as exc:
        st.error(f"Run {run_id}: {exc.message}")
        return None


def _fetch_tasks(client, run_id: str, page: int) -> dict:
    try:
        return (
            client.get(
                f"/api/v1/pipelines/{run_id}/tasks",
                params={"page": page, "per_page": 50},
            )
            or {}
        )
    except ApiError as exc:
        st.error(f"Tasks: {exc.message}")
        return {}


def _fetch_events(client, run_id: str, page: int) -> dict:
    try:
        return (
            client.get(
                f"/api/v1/pipelines/{run_id}/events",
                params={"page": page, "per_page": 50},
            )
            or {}
        )
    except ApiError as exc:
        st.error(f"Events: {exc.message}")
        return {}


def _render_launch(client) -> None:
    st.subheader("Launch a run")
    with st.form("launch_form"):
        cols = st.columns(3)
        pipeline_id = cols[0].number_input("Pipeline ID", min_value=1, step=1, key="pl.pid")
        project_id = cols[1].number_input("Project ID", min_value=1, step=1, key="pl.proj")
        override = cols[2].checkbox("Override soft warnings", key="pl.override")

        sample_ids_raw = st.text_input(
            "Sample IDs (comma-separated)",
            key="pl.samples",
            help="External sample_id strings — not database row IDs.",
        )
        params_raw = st.text_area(
            "Parameters (JSON, optional)", key="pl.params", height=90, value="{}"
        )

        launch = st.form_submit_button("Launch", type="primary")

    if not launch:
        return
    sample_ids = [s.strip() for s in sample_ids_raw.split(",") if s.strip()]
    if not sample_ids:
        st.error("Enter at least one sample_id.")
        return

    import json

    try:
        parameters = json.loads(params_raw or "{}")
    except json.JSONDecodeError as exc:
        st.error(f"parameters must be JSON: {exc}")
        return

    body = {
        "pipeline_id": int(pipeline_id),
        "sample_ids": sample_ids,
        "project_id": int(project_id),
        "parameters": parameters,
        "override_soft_warnings": bool(override),
    }
    try:
        with st.spinner("Launching — compatibility check, work dir, Batch submit…"):
            result = client.post("/api/v1/pipelines/launch", json_body=body)
    except ApiError as exc:
        if exc.code == "SOFT_WARNINGS":
            st.warning("Soft warnings — tick **Override soft warnings** and resubmit to proceed.")
            st.caption(exc.message)
        else:
            st.error(f"Launch failed: {exc.message}")
        return
    rid = result.get("run_id")
    st.session_state[SS_RUN_ID] = rid
    st.success(f"Run launched: `{rid}`")


def _render_overview(run: dict) -> None:
    cols = st.columns([1, 3])
    with cols[0]:
        render_badge(run_status_badge(run.get("status")))
    cols[1].markdown(
        f"**{run.get('pipeline_name')}** v{run.get('pipeline_version')} · "
        f"launched {run.get('launched_at')} · completed {run.get('completed_at') or '—'}"
    )
    st.markdown(
        f"- **Samples**: {len(run.get('sample_ids') or [])}\n"
        f"- **Batch job**: `{run.get('gcp_batch_job_id') or '—'}`\n"
        f"- **Work dir**: `{run.get('work_dir') or '—'}`\n"
        f"- **Result URI**: `{run.get('result_uri') or '—'}`"
    )
    if run.get("status") == "FAILED":
        st.warning("Run failed — use the **Resume** button to retry from last checkpoint.")
    if run.get("multiqc_report_uri"):
        st.subheader("MultiQC report")
        st.components.v1.iframe(run["multiqc_report_uri"], height=720, scrolling=True)


def _render_tasks(tasks_data: dict) -> None:
    rows = tasks_data.get("results", [])
    if not rows:
        st.caption("No tasks yet.")
        return
    for t in rows:
        cols = st.columns([3, 1, 2, 2])
        cols[0].markdown(f"`{t.get('task_id') or t.get('native_id') or t.get('id')}`")
        with cols[1]:
            render_badge(run_status_badge(t.get("status")))
        cols[2].caption(t.get("process") or "")
        cols[3].caption(f"cpus={t.get('cpus')} mem={t.get('memory')}")


def _render_events(events_data: dict) -> None:
    rows = events_data.get("results", [])
    if not rows:
        st.caption("No events yet.")
        return
    for e in rows:
        st.caption(
            f"{e.get('received_at') or ''} · **{e.get('event_type') or ''}** · "
            f"run={e.get('run_id')}"
        )


def _render_files(run: dict) -> None:
    uris = {
        "Result root": run.get("result_uri"),
        "MultiQC report": run.get("multiqc_report_uri"),
        "Nextstrain JSON": run.get("nextstrain_json_uri"),
        "Work dir (ephemeral)": run.get("work_dir"),
    }
    for label, uri in uris.items():
        if uri:
            st.markdown(f"- **{label}** — `{uri}`")


def _render_resume(client, run: dict) -> None:
    if run.get("status") != "FAILED":
        return
    with st.expander("Resume failed run"):
        if st.button("Resume from last checkpoint", type="primary", key="pl.resume"):
            try:
                client.post(f"/api/v1/pipelines/{run.get('run_id')}/resume")
                st.success("Resume requested.")
            except ApiError as exc:
                st.error(f"Resume failed: {exc.message}")


def _render_monitor(client) -> None:
    st.subheader("Monitor a run")
    run_id = st.text_input(
        "Run ID", key="pl.monitor_rid", value=st.session_state.get(SS_RUN_ID) or ""
    )
    if not run_id:
        st.caption("Enter a run ID to load its status.")
        return
    run = _fetch_run(client, run_id)
    if not run:
        return

    tabs = st.tabs(["Overview", "Tasks", "Events", "Files"])
    with tabs[0]:
        _render_overview(run)
        _render_resume(client, run)
    with tabs[1]:
        _render_tasks(_fetch_tasks(client, run_id, 1))
    with tabs[2]:
        _render_events(_fetch_events(client, run_id, 1))
    with tabs[3]:
        _render_files(run)


def render() -> None:
    st.title(PAGE_TITLE)
    client = get_client()

    launch_tab, monitor_tab = st.tabs(["Launch", "Monitor"])
    with launch_tab:
        _render_launch(client)
    with monitor_tab:
        _render_monitor(client)


render()
