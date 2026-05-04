"""
Submissions — list view, create wizard, and detail view (I-2).

The list view shows all submissions in the user's lab with a status
badge. The create wizard walks through title → samples → configuration
→ validate → generate → "next steps" instruction page. The detail view
exposes lifecycle action buttons (Mark Submitted, Register Accessions,
Mark Rejected, Withdraw) appropriate to the current status.

Per Critical Rule 24 the page consumes the standard envelope via
``frontend.lib.api.ApiClient``. Per the I-2 architecture, JACKPOT
*generates the package*; the operator runs Seqsender themselves with
their own credentials. The post-generate instruction page is the most
important UX moment — it is the bridge between JACKPOT and Seqsender.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from frontend.components.badges import _pill, render_badge
from frontend.lib.api import ApiError, get_client
from frontend.lib.session import current_user

PAGE_TITLE = "Submissions"

SS_VIEW = "subs.view"  # "list" | "create" | "detail"
SS_DETAIL_ID = "subs.detail_id"
SS_CREATE_STEP = "subs.create.step"
SS_CREATE_DRAFT = "subs.create.draft"


_REPOSITORIES = ("NCBI", "GISAID_EPICOV", "GISAID_EPIFLU", "GISAID_EPIPOX", "ENA", "DDBJ")


_STATUS_COLORS: dict[str, tuple[str, str]] = {
    "DRAFT": ("#1f2937", "#e5e7eb"),
    "READY_TO_SUBMIT": ("#5b21b6", "#ddd6fe"),
    "SUBMITTED": ("#1e3a8a", "#bfdbfe"),
    "PARTIAL_SUCCESS": ("#854d0e", "#fde68a"),
    "ACCEPTED": ("#14532d", "#bbf7d0"),
    "REJECTED": ("#7f1d1d", "#fecaca"),
    "EMBARGOED": ("#92400e", "#fde68a"),
    "RELEASED": ("#0f766e", "#99f6e4"),
    "WITHDRAWN": ("#1f2937", "#e5e7eb"),
    "FAILED": ("#7f1d1d", "#fecaca"),
}


def _status_badge(status: str | None) -> str:
    if not status:
        return _pill("—", "#1f2937", "#e5e7eb")
    fg, bg = _STATUS_COLORS.get(status, ("#1f2937", "#e5e7eb"))
    return _pill(status, fg, bg)


def _init_state() -> None:
    st.session_state.setdefault(SS_VIEW, "list")
    st.session_state.setdefault(SS_DETAIL_ID, None)
    st.session_state.setdefault(SS_CREATE_STEP, 1)
    st.session_state.setdefault(SS_CREATE_DRAFT, {})


# ── list ──────────────────────────────────────────────────────────


def _render_list(client) -> None:
    me = current_user() or {}
    memberships = me.get("lab_memberships") or []
    lab_options = [
        (m["lab_id"], m.get("lab_name") or f"Lab {m['lab_id']}") for m in memberships
    ] or [(1, "Lab 1")]
    lab_choice = st.sidebar.selectbox(
        "Lab",
        lab_options,
        format_func=lambda opt: opt[1],
        key="subs.list.lab",
    )
    status_filter = st.sidebar.selectbox(
        "Status",
        ("",) + tuple(_STATUS_COLORS.keys()),
        key="subs.list.status",
    )

    cols = st.columns([3, 1])
    cols[0].subheader("Submissions")
    if cols[1].button("New submission", type="primary"):
        st.session_state[SS_VIEW] = "create"
        st.session_state[SS_CREATE_STEP] = 1
        st.session_state[SS_CREATE_DRAFT] = {}
        st.rerun()

    params: dict = {"lab_id": int(lab_choice[0])}
    if status_filter:
        params["status"] = status_filter

    try:
        body = client.get("/api/v1/submissions/", params=params)
    except ApiError as exc:
        st.error(f"Could not load submissions: {exc.message}")
        return
    rows = body if isinstance(body, list) else body.get("data", [])
    pagination = body.get("pagination") if isinstance(body, dict) else None
    total = (pagination or {}).get("total", len(rows))
    st.caption(f"{total} submission(s)")

    if not rows:
        st.info("No submissions yet — click 'New submission' to get started.")
        return

    header = st.columns([3, 1.4, 1.4, 1.2, 1, 1])
    header[0].markdown("**Title**")
    header[1].markdown("**Repository**")
    header[2].markdown("**Status**")
    header[3].markdown("**Samples**")
    header[4].markdown("**Created**")
    header[5].markdown("")
    for row in rows:
        cols = st.columns([3, 1.4, 1.4, 1.2, 1, 1])
        cols[0].markdown(f"`{row.get('title')}`")
        cols[1].caption(row.get("target_repository") or "—")
        with cols[2]:
            render_badge(_status_badge(row.get("status")))
        cols[3].caption(str(row.get("sample_count", "")))
        cols[4].caption((row.get("created_at") or "")[:10])
        if cols[5].button("Open", key=f"subs.list.open.{row['id']}"):
            st.session_state[SS_DETAIL_ID] = row["id"]
            st.session_state[SS_VIEW] = "detail"
            st.rerun()


# ── create wizard ─────────────────────────────────────────────────


def _render_create(client) -> None:
    me = current_user() or {}
    memberships = me.get("lab_memberships") or []
    lab_options = [
        (m["lab_id"], m.get("lab_name") or f"Lab {m['lab_id']}") for m in memberships
    ] or [(1, "Lab 1")]

    step = st.session_state[SS_CREATE_STEP]
    draft = st.session_state[SS_CREATE_DRAFT]

    cols = st.columns([4, 1])
    cols[0].caption(f"Create submission · step {step} / 5")
    if cols[1].button("Cancel"):
        st.session_state[SS_VIEW] = "list"
        st.rerun()
    st.progress(min((step - 1) / 4, 1.0))

    if step == 1:
        st.subheader("Step 1 — Title and target")
        draft["title"] = st.text_input("Title", value=draft.get("title", ""))
        draft["description"] = st.text_area(
            "Description (optional)",
            value=draft.get("description") or "",
            height=80,
        )
        lab_pick = st.selectbox(
            "Lab",
            lab_options,
            format_func=lambda opt: opt[1],
            key="subs.create.lab",
        )
        draft["lab_id"] = lab_pick[0] if lab_pick else 1
        draft["target_repository"] = st.selectbox(
            "Target repository",
            _REPOSITORIES,
            key="subs.create.repo",
        )
        draft["bioproject_accession"] = st.text_input(
            "Existing BioProject (optional)",
            value=draft.get("bioproject_accession") or "",
        )
        if st.button("Next", type="primary", disabled=not draft.get("title")):
            st.session_state[SS_CREATE_STEP] = 2
            st.rerun()
        return

    if step == 2:
        st.subheader("Step 2 — Pick samples")
        st.caption("Default filter shows SUBMITTABLE samples in your lab.")
        try:
            sample_body = client.get(
                "/api/v1/samples/",
                params={
                    "lab_id": draft.get("lab_id", 1),
                    "quality_status": "SUBMITTABLE",
                    "per_page": 200,
                },
            )
        except ApiError as exc:
            st.error(f"Sample lookup failed: {exc.message}")
            return
        samples = (
            sample_body if isinstance(sample_body, list) else sample_body.get("data", [])
        )
        selected: list[int] = list(draft.get("sample_ids", []))
        for s in samples:
            checked = st.checkbox(
                f"`{s.get('sample_id')}` · {s.get('organism_name') or '—'}",
                value=s["id"] in selected,
                key=f"subs.create.sample.{s['id']}",
            )
            if checked and s["id"] not in selected:
                selected.append(s["id"])
            elif not checked and s["id"] in selected:
                selected.remove(s["id"])
        draft["sample_ids"] = selected
        st.caption(f"{len(selected)} sample(s) selected")
        nav = st.columns(2)
        if nav[0].button("Back"):
            st.session_state[SS_CREATE_STEP] = 1
            st.rerun()
        if nav[1].button("Next", type="primary", disabled=not selected):
            st.session_state[SS_CREATE_STEP] = 3
            st.rerun()
        return

    if step == 3:
        st.subheader("Step 3 — Configuration")
        rd_default = draft.get("release_date")
        rd = st.date_input(
            "Embargo / release date (optional)",
            value=rd_default,
            key="subs.create.rd",
        )
        if isinstance(rd, date):
            draft["release_date"] = rd.isoformat()
        st.info(
            "Leave blank for immediate release on accession. Set a future "
            "date to embargo until that date."
        )
        nav = st.columns(2)
        if nav[0].button("Back"):
            st.session_state[SS_CREATE_STEP] = 2
            st.rerun()
        if nav[1].button("Next", type="primary"):
            st.session_state[SS_CREATE_STEP] = 4
            st.rerun()
        return

    if step == 4:
        st.subheader("Step 4 — Validate")
        sub_id = draft.get("submission_id")
        if not sub_id:
            try:
                created = client.post(
                    "/api/v1/submissions/",
                    json_body={
                        "lab_id": draft["lab_id"],
                        "target_repository": draft["target_repository"],
                        "title": draft["title"],
                        "description": draft.get("description"),
                        "sample_ids": draft["sample_ids"],
                        "bioproject_accession": draft.get("bioproject_accession"),
                        "release_date": draft.get("release_date"),
                    },
                )
            except ApiError as exc:
                st.error(f"Create failed: {exc.message}")
                return
            sub_id = created["id"]
            draft["submission_id"] = sub_id
        try:
            result = client.post(f"/api/v1/submissions/{sub_id}/validate")
        except ApiError as exc:
            st.error(f"Validation failed: {exc.message}")
            return
        if result.get("valid"):
            st.success("All samples pass readiness validation.")
        else:
            st.warning(
                f"{len(result.get('per_sample') or [])} sample(s) have issues."
            )
            for ps in result.get("per_sample") or []:
                with st.expander(ps["sample_id"]):
                    for issue in ps["issues"]:
                        st.write(f"- {issue}")
        nav = st.columns(2)
        if nav[0].button("Back"):
            st.session_state[SS_CREATE_STEP] = 3
            st.rerun()
        if nav[1].button(
            "Generate package",
            type="primary",
            disabled=not result.get("valid"),
        ):
            st.session_state[SS_CREATE_STEP] = 5
            st.rerun()
        return

    if step == 5:
        st.subheader("Step 5 — Generate")
        sub_id = draft.get("submission_id")
        if not sub_id:
            st.error("Internal error: submission_id missing.")
            return
        try:
            result = client.post(
                f"/api/v1/submissions/{sub_id}/generate",
                json_body={"copy_files": False},
            )
        except ApiError as exc:
            st.error(f"Package generation failed: {exc.message}")
            return
        path = result.get("package_path")
        st.success("Package generated.")
        _render_post_package_instructions(path, sub_id)
        if st.button("Open submission detail"):
            st.session_state[SS_DETAIL_ID] = sub_id
            st.session_state[SS_VIEW] = "detail"
            st.rerun()


def _render_post_package_instructions(path: str | None, sub_id: int) -> None:
    """Critical UX for I-2 v1 — the bridge between JACKPOT and Seqsender."""
    st.markdown("### Your submission package is ready")
    st.code(path or "(unknown)", language="text")
    st.markdown(
        f"""### Next steps

1. **Configure Seqsender** on a host with stable network connectivity.
   Laptop deployments may experience interruptions during long
   submissions; we recommend running Seqsender from a server.

2. **Set up your repository credentials:**

   - **NCBI:** Set up `~/.ncbirc` with your API key.
   - **GISAID:** Use `seqsender configure-gisaid` to enter your credentials.
   - **ENA:** Set Webin credentials in `~/.webin.txt`.

   JACKPOT does not store or transmit your repository credentials.

3. **Run Seqsender:**

   ```
   cd <package-path>
   seqsender submit --config seqsender_config.yaml
   ```

4. **When you receive accessions** (typically 24–72 hours for NCBI),
   register them with JACKPOT. From the submission detail page,
   click "Register accessions" and upload the TSV Seqsender returned.

5. **Mark as submitted** to track this submission in JACKPOT — click
   the button on the submission detail page (submission #{sub_id}).
"""
    )


# ── detail ────────────────────────────────────────────────────────


def _render_detail(client) -> None:
    sub_id = st.session_state.get(SS_DETAIL_ID)
    if not sub_id:
        st.error("No submission selected.")
        st.session_state[SS_VIEW] = "list"
        st.rerun()
        return

    if st.button("← Back to list"):
        st.session_state[SS_VIEW] = "list"
        st.rerun()

    try:
        sub = client.get(f"/api/v1/submissions/{sub_id}")
    except ApiError as exc:
        st.error(f"Could not load submission: {exc.message}")
        return

    cols = st.columns([3, 1])
    cols[0].markdown(f"### {sub['title']}")
    with cols[1]:
        render_badge(_status_badge(sub.get("status")))
    st.caption(
        f"{sub.get('target_repository')} · "
        f"created {(sub.get('created_at') or '')[:10]} · "
        f"package: {sub.get('package_path') or '(not generated yet)'}"
    )

    samples = sub.get("samples") or []
    st.markdown(f"#### Samples ({len(samples)})")
    for s in samples:
        cols = st.columns([2, 2, 1.4, 1.4, 1.4])
        cols[0].markdown(f"`{s.get('sample_id')}`")
        cols[1].caption(s.get("organism_name") or "—")
        cols[2].caption(f"per-sample: {s.get('per_sample_status')}")
        cols[3].caption(f"BioSample: {s.get('biosample_accession') or '—'}")
        cols[4].caption(f"GenBank: {s.get('genbank_accession') or '—'}")

    st.divider()
    _render_detail_actions(client, sub)


def _render_detail_actions(client, sub: dict) -> None:
    sid = sub["id"]
    status = sub.get("status")
    st.markdown("#### Actions")

    if status == "READY_TO_SUBMIT" and st.button("Mark as submitted", type="primary"):
        try:
            client.post(f"/api/v1/submissions/{sid}/mark-submitted")
            st.success("Marked as submitted.")
            st.rerun()
        except ApiError as exc:
            st.error(f"Mark submitted failed: {exc.message}")

    if status == "SUBMITTED":
        st.markdown("##### Register accessions")
        upload = st.file_uploader(
            "Accessions TSV", type=["tsv", "txt"], key=f"subs.detail.acc.{sid}"
        )
        cols = st.columns(2)
        if upload and cols[0].button("Upload accessions"):
            try:
                client.post(
                    f"/api/v1/submissions/{sid}/register-accessions",
                    files={"file": (upload.name, upload.getvalue(), upload.type)},
                )
                st.success("Accessions registered.")
                st.rerun()
            except ApiError as exc:
                st.error(f"Register accessions failed: {exc.message}")
        rejection_reason = st.text_input(
            "Rejection reason", key=f"subs.detail.reject.{sid}"
        )
        if cols[1].button("Mark rejected", disabled=not rejection_reason):
            try:
                client.post(
                    f"/api/v1/submissions/{sid}/mark-rejected",
                    json_body={"reason": rejection_reason},
                )
                st.success("Marked rejected.")
                st.rerun()
            except ApiError as exc:
                st.error(f"Mark rejected failed: {exc.message}")

    if status in (
        "SUBMITTED",
        "PARTIAL_SUCCESS",
        "ACCEPTED",
        "EMBARGOED",
        "RELEASED",
        "REJECTED",
    ):
        st.markdown("##### Withdraw")
        reason = st.text_input("Withdrawal reason", key=f"subs.detail.wdr.{sid}")
        if st.button("Withdraw", disabled=not reason):
            try:
                client.post(
                    f"/api/v1/submissions/{sid}/withdraw",
                    json_body={"reason": reason},
                )
                st.success("Withdrawn.")
                st.rerun()
            except ApiError as exc:
                st.error(f"Withdraw failed: {exc.message}")

    if status == "DRAFT":
        st.caption("DRAFT submission — finish the create wizard or delete.")
        if st.button("Delete (soft)"):
            try:
                client.delete(f"/api/v1/submissions/{sid}")
                st.success("Deleted.")
                st.session_state[SS_VIEW] = "list"
                st.rerun()
            except ApiError as exc:
                st.error(f"Delete failed: {exc.message}")


# ── entrypoint ────────────────────────────────────────────────────


def render() -> None:
    _init_state()
    st.title(PAGE_TITLE)
    if current_user() is None:
        st.warning("API unreachable — start the backend and refresh.")
        return

    client = get_client()
    view = st.session_state[SS_VIEW]
    if view == "create":
        _render_create(client)
    elif view == "detail":
        _render_detail(client)
    else:
        _render_list(client)


render()
