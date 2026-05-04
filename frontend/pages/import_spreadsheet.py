"""
Spreadsheet importer wizard (I-1).

API-driven wizard backed by /api/v1/imports/sessions/. The backend
session is the source of truth for wizard progress; this page only
holds ephemeral UI state (radio selections, in-flight typed values)
in ``st.session_state``.

Wizard steps:

    1. Upload  →  2. Sheet picker  →  3. Column mapping  →
    4. Value normalization  →  5. File reference pattern  →
    6. Preview  →  7. Diff (re-import only)  →  8. Import

Sessions live for 24 hours server-side. Closing the browser at any
step is fine; the resume view appears on the landing page when an
in-progress session exists.

See spec.md and docs/CLAUDE.md Critical Rules 22, 24, 57, 58.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from frontend.lib.api import ApiError, get_client
from frontend.lib.session import current_user

PAGE_TITLE = "Import spreadsheet"
SS_SESSION_ID = "import.session_id"


def _fetch_session(client, sid: int) -> dict | None:
    try:
        return client.get(f"/api/v1/imports/sessions/{sid}")
    except ApiError as exc:
        if exc.status_code in (404, 410):
            st.session_state.pop(SS_SESSION_ID, None)
            st.warning(f"Session no longer available: {exc.message}")
            return None
        st.error(f"Could not load session: {exc.message}")
        return None


def _patch_session(client, sid: int, fields: dict, *, compute: str | None = None) -> dict | None:
    params = {"compute": compute} if compute else None
    try:
        return client.patch(f"/api/v1/imports/sessions/{sid}", json_body=fields)
    except ApiError as exc:
        st.error(f"Update failed: {exc.message}")
        return None
    finally:
        # ApiClient.patch doesn't accept params; the compute hook is
        # done as a follow-up GET via _fetch_session in the caller.
        del params


def _list_in_progress(client) -> list[dict]:
    try:
        return client.get("/api/v1/imports/sessions/") or []
    except ApiError as exc:
        st.error(f"Could not list sessions: {exc.message}")
        return []


def _list_mappings(client) -> list[dict]:
    try:
        out = client.get("/api/v1/import_mappings/")
        if isinstance(out, dict):
            return out.get("data") or []
        return out or []
    except ApiError:
        return []


# ── steps ──────────────────────────────────────────────────────────


def _render_resume_or_new(client, in_progress: list[dict]) -> None:
    st.subheader("Resume or start new")
    for s in in_progress:
        cols = st.columns([3, 1, 1, 1])
        cols[0].markdown(
            f"**{s.get('file_name')}** — step {s.get('current_step')} / 8 · "
            f"started {s.get('created_at')}"
        )
        if cols[1].button("Resume", key=f"resume.{s['id']}"):
            st.session_state[SS_SESSION_ID] = s["id"]
            st.rerun()
        if cols[2].button("Abandon", key=f"abandon.{s['id']}"):
            try:
                client.delete(f"/api/v1/imports/sessions/{s['id']}")
            except ApiError as exc:
                st.error(f"Abandon failed: {exc.message}")
            st.rerun()
    st.divider()
    if st.button("Start a new import", type="primary"):
        st.session_state["import.show_new_upload"] = True
        st.rerun()


def _render_upload(client) -> None:
    st.subheader("Step 1 — Upload your spreadsheet")
    st.caption("Supported: .xlsx, .csv, .tsv. Max size 10 MB.")
    me = current_user() or {}
    memberships = me.get("lab_memberships") or []
    lab_options = [
        (m["lab_id"], m.get("lab_name") or f"Lab {m['lab_id']}") for m in memberships
    ] or [(1, "Lab 1")]
    lab_choice = st.selectbox(
        "Target lab",
        lab_options,
        format_func=lambda opt: opt[1],
        key="import.upload.lab",
    )
    upload = st.file_uploader("Spreadsheet", type=["xlsx", "csv", "tsv"], key="import.upload.file")
    if upload and st.button("Upload and continue", type="primary"):
        try:
            data = client.post(
                "/api/v1/imports/sessions/",
                data={"lab_id": str(lab_choice[0])},
                files={"file": (upload.name, upload.getvalue(), upload.type)},
            )
        except ApiError as exc:
            st.error(f"Upload failed: {exc.message}")
            return
        st.session_state[SS_SESSION_ID] = data["id"]
        st.session_state.pop("import.show_new_upload", None)
        st.success(f"Created session {data['id']}.")
        st.rerun()


def _render_sheet_picker(client, session: dict, meta: dict) -> None:
    st.subheader("Step 2 — Pick a sheet")
    sheets = meta.get("sheets") or ["__single__"]
    if len(sheets) <= 1 or sheets == ["__single__"]:
        st.info("Single sheet detected — skipping picker.")
        if st.button("Next", type="primary"):
            _patch_session(
                client,
                session["id"],
                {"selected_sheet": sheets[0], "current_step": 3},
            )
            st.rerun()
        return
    pick = st.selectbox("Sheet", sheets, key="import.sheet")
    if st.button("Next", type="primary"):
        _patch_session(client, session["id"], {"selected_sheet": pick, "current_step": 3})
        st.rerun()


def _confidence_badge(confidence: float) -> str:
    if confidence >= 0.95:
        color = "#bbf7d0"
        fg = "#14532d"
    elif confidence >= 0.85:
        color = "#fde68a"
        fg = "#854d0e"
    else:
        color = "#fecaca"
        fg = "#7f1d1d"
    label = f"{int(confidence * 100)}%"
    return (
        f"<span style='display:inline-block;padding:1px 8px;border-radius:8px;"
        f"background:{color};color:{fg};font-size:0.72rem'>{label}</span>"
    )


def _render_column_mapping(client, session: dict, meta: dict) -> None:
    st.subheader("Step 3 — Map your columns to JACKPOT fields")
    sheet = session.get("selected_sheet") or (meta.get("sheets") or ["__single__"])[0]
    spreadsheet_cols = (meta.get("columns_by_sheet") or {}).get(sheet) or []

    # Auto-suggest at first render only (when column_mapping is empty).
    suggestions: dict[str, dict[str, Any]] = {}
    if not session.get("column_mapping"):
        try:
            from backend.harmonizer import suggest_column_mapping  # noqa: PLC0415

            raw = suggest_column_mapping(spreadsheet_cols)
            for col, sug in raw.items():
                suggestions[col] = {
                    "target": sug.target,
                    "confidence": sug.confidence,
                    "reason": sug.reason,
                }
        except Exception:  # noqa: BLE001
            pass

    existing = session.get("column_mapping") or {}
    target_options = ["(skip)"] + sorted(
        list(
            set(
                list(existing.values()) + [s["target"] for s in suggestions.values() if s["target"]]
            )
        )
        or [
            "sample_id",
            "date_collected",
            "source_type",
            "organism_name",
            "collection_location_country",
            "collection_location_state",
            "host_species",
            "host_age",
            "host_sex",
            "isolation_source",
            "biospecimen_type",
            "sequencing_platform",
            "sequencing_lab",
            "type_of_experiment",
            "library_preparation_method",
            "external_case_id",
        ]
    )

    new_mapping: dict[str, str] = {}
    for col in spreadsheet_cols:
        sug = suggestions.get(col)
        existing_target = existing.get(col)
        default = existing_target or (sug["target"] if sug and sug["target"] else "(skip)")
        index = target_options.index(default) if default in target_options else 0
        cols = st.columns([3, 3, 1.2])
        cols[0].markdown(f"`{col}`")
        choice = cols[1].selectbox(
            f"Map {col!r} to",
            target_options,
            index=index,
            key=f"import.colmap.{session['id']}.{col}",
            label_visibility="collapsed",
        )
        if sug and sug["target"]:
            cols[2].markdown(_confidence_badge(sug["confidence"]), unsafe_allow_html=True)
        if choice and choice != "(skip)":
            new_mapping[col] = choice

    if st.button("Accept mapping and continue", type="primary"):
        if "sample_id" not in new_mapping.values():
            st.error("`sample_id` is required. Map at least one column to it.")
            return
        _patch_session(
            client,
            session["id"],
            {"column_mapping": new_mapping, "current_step": 4},
        )
        st.rerun()


def _render_value_mapping(client, session: dict) -> None:
    st.subheader("Step 4 — Normalize values (optional)")
    st.caption(
        "Translate free-text values to JACKPOT enums. v1 supports manual "
        "mapping; auto-suggestions for known enums (e.g. source_type) "
        "land in v1.5."
    )
    if st.button("Skip value mapping", type="primary"):
        _patch_session(client, session["id"], {"value_mapping": {}, "current_step": 5})
        st.rerun()


def _render_file_reference(client, session: dict, meta: dict) -> None:
    st.subheader("Step 5 — File references")
    sheet = session.get("selected_sheet") or (meta.get("sheets") or ["__single__"])[0]
    cols_in_sheet = (meta.get("columns_by_sheet") or {}).get(sheet) or []

    # Naive auto-inference. If we see r1_path / r2_path or similar,
    # pre-select path_columns. Per design notes the inference is
    # surfaced with a warning — never silently applied.
    inferred = None
    lower = {c.lower(): c for c in cols_in_sheet}
    if "r1_path" in lower or "fastq r1" in lower:
        inferred = ("path_columns", lower.get("r1_path") or lower.get("fastq r1"))
    if inferred is not None:
        st.warning(
            f"Auto-inferred from column names: ``path_columns`` "
            f"(R1 column: ``{inferred[1]}``). Please verify before continuing."
        )

    pattern_type = st.radio(
        "Pattern",
        ("path_columns", "filename_convention", "none"),
        index=("path_columns", "filename_convention", "none").index(
            inferred[0] if inferred else "none"
        ),
        key=f"import.filepat.type.{session['id']}",
    )
    config: dict[str, Any] = {}
    if pattern_type == "path_columns":
        config["r1_column"] = st.selectbox(
            "R1 column",
            cols_in_sheet,
            index=cols_in_sheet.index(inferred[1])
            if inferred and inferred[1] in cols_in_sheet
            else 0,
            key=f"import.filepat.r1.{session['id']}",
        )
        config["r2_column"] = st.selectbox(
            "R2 column (optional)",
            ["(none)"] + cols_in_sheet,
            key=f"import.filepat.r2.{session['id']}",
        )
        if config["r2_column"] == "(none)":
            config["r2_column"] = None
    elif pattern_type == "filename_convention":
        config["template"] = st.text_input(
            "Filename template",
            value="{sample_id}_R1.fastq.gz",
            key=f"import.filepat.template.{session['id']}",
        )
        config["sample_id_column"] = "sample_id"

    storage_intent = st.selectbox(
        "Storage intent",
        ("EXTERNAL", "MANAGED", "MIRRORED"),
        key=f"import.filepat.intent.{session['id']}",
        help="EXTERNAL is the default per Critical Rule 57 — no copies are made.",
    )

    if st.button("Continue to preview", type="primary"):
        _patch_session(
            client,
            session["id"],
            {
                "file_reference_pattern": {
                    "type": pattern_type,
                    "config": config,
                    "storage_intent": storage_intent,
                },
                "current_step": 6,
            },
        )
        st.rerun()


def _render_preview(client, session: dict) -> None:
    st.subheader("Step 6 — Preview")
    if not session.get("preview_results"):
        if st.button("Compute preview", type="primary"):
            try:
                client.patch(
                    f"/api/v1/imports/sessions/{session['id']}?compute=preview",
                    json_body={},
                )
            except ApiError as exc:
                st.error(f"Preview failed: {exc.message}")
                return
            st.rerun()
        return
    pr = session["preview_results"]
    cols = st.columns(3)
    cols[0].metric("Total rows", pr.get("total_rows", 0))
    cols[1].metric("Sampled", pr.get("sample_size", 0))
    valid = sum(1 for r in pr.get("rows") or [] if r.get("valid"))
    cols[2].metric("Valid in preview", valid)

    if pr.get("row_cap_hit"):
        st.warning("Spreadsheet exceeds 10,000 rows. Only the first 10,000 will be imported in v1.")

    for row in pr.get("rows") or []:
        with st.expander(
            f"Row {row['row']} — sample_id={row.get('sample_id') or '—'} · "
            f"{'valid' if row['valid'] else 'INVALID'}"
        ):
            if row.get("errors"):
                st.error("Errors: " + "; ".join(row["errors"]))
            if row.get("warnings"):
                st.warning("Warnings: " + "; ".join(row["warnings"]))
            st.json(row)

    next_step = st.columns(2)
    if next_step[0].button("Show diff against existing JACKPOT"):
        try:
            client.patch(
                f"/api/v1/imports/sessions/{session['id']}?compute=diff",
                json_body={},
            )
        except ApiError as exc:
            st.error(f"Diff failed: {exc.message}")
            return
        st.rerun()
    if next_step[1].button("Skip diff and import", type="primary"):
        _patch_session(client, session["id"], {"current_step": 8})
        st.rerun()


def _render_diff(client, session: dict) -> None:
    st.subheader("Step 7 — Diff against existing samples")
    diff = session.get("diff_results")
    if not diff:
        st.info("Diff not yet computed. Click below to run.")
        if st.button("Compute diff", type="primary"):
            try:
                client.patch(
                    f"/api/v1/imports/sessions/{session['id']}?compute=diff",
                    json_body={},
                )
            except ApiError as exc:
                st.error(f"Diff failed: {exc.message}")
                return
            st.rerun()
        return

    cols = st.columns(3)
    cols[0].metric("New", len(diff.get("new") or []))
    cols[1].metric("Changed", len(diff.get("changed") or []))
    cols[2].metric("Unchanged", len(diff.get("unchanged") or []))

    if diff.get("changed"):
        st.markdown("### Changes detected")
        for entry in diff["changed"]:
            with st.expander(f"Sample {entry['sample_id']}"):
                for field, vals in entry["changes"].items():
                    st.write(
                        f"- **{field}** — current: `{vals['current']}` → "
                        f"incoming: `{vals['incoming']}`"
                    )

    if st.button("Continue to import", type="primary"):
        _patch_session(client, session["id"], {"current_step": 8})
        st.rerun()


def _render_import(client, session: dict) -> None:
    st.subheader("Step 8 — Import")
    if session.get("status") == "imported":
        st.success("Import complete.")
        _render_save_mapping(client, session)
        return
    if st.button("Submit import", type="primary"):
        try:
            result = client.post(f"/api/v1/imports/sessions/{session['id']}/import")
        except ApiError as exc:
            st.error(f"Import failed: {exc.message}")
            return
        # ApiClient unwraps "data" — the wizard's execute_import body
        # is the run_csv_ingest envelope.
        st.success(
            f"Imported {result.get('data', {}).get('success', 0)} sample(s); "
            f"{result.get('data', {}).get('failed', 0)} failed."
        )
        st.rerun()


def _render_save_mapping(client, session: dict) -> None:
    st.markdown("### Save this column mapping for next time?")
    name = st.text_input("Mapping name", placeholder="e.g. Sequencing Center weekly batch")
    description = st.text_area("Description (optional)", height=70)
    if st.button("Save mapping") and name:
        try:
            client.post(
                "/api/v1/import_mappings/",
                json_body={
                    "lab_id": session["lab_id"],
                    "display_name": name,
                    "description": description or None,
                    "column_mapping": session.get("column_mapping") or {},
                    "file_reference_pattern": session.get("file_reference_pattern") or {},
                },
            )
            st.success("Saved.")
        except ApiError as exc:
            st.error(f"Save failed: {exc.message}")


# ── entrypoint ─────────────────────────────────────────────────────


def render() -> None:
    st.title(PAGE_TITLE)
    if current_user() is None:
        st.warning("API unreachable — start the backend and refresh.")
        return

    client = get_client()

    if SS_SESSION_ID not in st.session_state:
        in_progress = _list_in_progress(client)
        if in_progress and not st.session_state.get("import.show_new_upload"):
            _render_resume_or_new(client, in_progress)
            return
        _render_upload(client)
        return

    sid = st.session_state[SS_SESSION_ID]
    session = _fetch_session(client, sid)
    if session is None:
        return

    # Load spreadsheet metadata if present (created at upload time).
    meta = session.get("spreadsheet_meta") or {}

    step = session.get("current_step") or 1
    cols = st.columns([4, 1])
    cols[0].caption(f"Session **{session['id']}** · file `{session.get('file_name')}`")
    if cols[1].button("Abandon"):
        import contextlib  # noqa: PLC0415

        with contextlib.suppress(ApiError):
            client.delete(f"/api/v1/imports/sessions/{session['id']}")
        st.session_state.pop(SS_SESSION_ID, None)
        st.rerun()

    progress = (step - 1) / 7
    st.progress(min(progress, 1.0), text=f"Step {step} / 8")

    if step == 1:
        _render_upload(client)
    elif step == 2:
        _render_sheet_picker(client, session, meta)
    elif step == 3:
        _render_column_mapping(client, session, meta)
    elif step == 4:
        _render_value_mapping(client, session)
    elif step == 5:
        _render_file_reference(client, session, meta)
    elif step == 6:
        _render_preview(client, session)
    elif step == 7:
        _render_diff(client, session)
    elif step == 8:
        _render_import(client, session)


render()
