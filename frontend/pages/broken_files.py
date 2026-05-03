"""
Broken files — operator triage view (Phase P0f F-10).

Lists every ``sample_files`` row whose ``storage_state`` has transitioned
to ``BROKEN`` (the verify_file_references job moves rows here when they
go missing or change size). The page is scoped via the same lab-access
ladder used by the samples list, so users only see broken files for
samples they could see in /samples/.

Click on a BROKEN badge in the actions column to open the remediation
dialog (re-locate, re-upload, or mark the parent sample inactive). The
re-locate flow uses POST /api/v1/ingest/register to register a new URI
for the same content; the existing row stays as BROKEN history while
the new URI lights up as the live row.
"""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from frontend.components.badges import (
    render_badge,
    storage_state_badge,
)
from frontend.lib.api import ApiError, get_client
from frontend.lib.session import current_user

PAGE_TITLE = "Broken files"
SS_PROJECT = "broken_files.project_id"
SS_LAB = "broken_files.lab_id"
SS_STATUS = "broken_files.status_filter"
SS_PAGE = "broken_files.page"
SS_DIALOG_TARGET = "broken_files.dialog_sample_files_id"

VERIFICATION_STATUSES: tuple[str, ...] = (
    "MISSING",
    "MISSING_2",
    "MISSING_3",
    "READ_ERROR",
    "READ_ERROR_2",
    "READ_ERROR_3",
    "SIZE_CHANGED",
)


def _init_state() -> None:
    st.session_state.setdefault(SS_PROJECT, 0)
    st.session_state.setdefault(SS_LAB, 0)
    st.session_state.setdefault(SS_STATUS, "")
    st.session_state.setdefault(SS_PAGE, 1)
    st.session_state.setdefault(SS_DIALOG_TARGET, None)


def _relative_time(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        ts = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    now = datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    delta = now - ts
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    days = seconds // 86400
    if days < 30:
        return f"{days}d ago"
    if days < 365:
        return f"{days // 30}mo ago"
    return f"{days // 365}y ago"


def _fetch(client, params: dict) -> tuple[list[dict], int, int]:
    try:
        body = client.get("/api/v1/files/broken", params=params)
    except ApiError as exc:
        st.error(f"Broken-files load failed: {exc.message}")
        return [], 0, 1
    # ApiClient returns the unwrapped envelope's data when present, but
    # paginated endpoints lose their pagination block in that path —
    # fetch the full envelope by going one level deeper if needed.
    rows = body if isinstance(body, list) else body.get("data", [])
    pagination = body.get("pagination") if isinstance(body, dict) else None
    total = (pagination or {}).get("total", len(rows))
    pages = max(1, (pagination or {}).get("pages", 1))
    return rows, total, pages


def _summary_line(rows: list[dict], total: int) -> str:
    if total == 0:
        return ""
    sample_ids = {r["sample_id"] for r in rows}
    lab_ids = {r["lab_id"] for r in rows}
    return (
        f"{total} broken file{'s' if total != 1 else ''} "
        f"across {len(sample_ids)} sample{'s' if len(sample_ids) != 1 else ''} "
        f"in {len(lab_ids)} lab{'s' if len(lab_ids) != 1 else ''} "
        "(this page)."
    )


def _open_dialog(sample_files_id: int) -> None:
    st.session_state[SS_DIALOG_TARGET] = sample_files_id


def _close_dialog() -> None:
    st.session_state[SS_DIALOG_TARGET] = None


def _render_remediation_dialog(client, row: dict) -> None:
    sf_id = row["sample_files_id"]
    sample_id_int = row["sample_id_int"]
    st.markdown(f"### Remediate broken file (id {sf_id})")
    st.caption(row.get("uri") or "—")
    cols = st.columns(2)
    cols[0].markdown(f"**Last verified:** {_relative_time(row.get('last_verified_at'))}")
    cols[1].markdown(f"**Status:** `{row.get('last_verification_status') or '—'}`")

    st.divider()

    # Re-locate: POST /api/v1/ingest/register with a new URI.
    new_uri = st.text_input(
        "New URI (re-locate)",
        key=f"broken.relocate_uri.{sf_id}",
        placeholder="file:///srv/seq/runs/240501/sample01_R1.fastq.gz",
        help=(
            "Provide a new URI for the same content. JACKPOT will "
            "register it via /api/v1/ingest/register. The cheap "
            "fingerprint must match the broken file for the system to "
            "treat it as the same content."
        ),
    )
    relocate_role = st.selectbox(
        "Role for new URI",
        ("R1", "R2", "LONG_READ", "ASSEMBLY", "OTHER"),
        key=f"broken.relocate_role.{sf_id}",
    )
    actions = st.columns(3)
    if actions[0].button("Re-locate", key=f"broken.relocate.{sf_id}", disabled=not new_uri):
        try:
            client.post(
                "/api/v1/ingest/register",
                json_body={
                    "sample_metadata": {"sample_id_int": sample_id_int},
                    "files": [{"role": relocate_role, "uri": new_uri}],
                },
            )
            st.success("Re-located. The new URI is registered.")
            _close_dialog()
            st.rerun()
        except ApiError as exc:
            st.error(f"Re-locate failed: {exc.message}")

    if actions[1].button("Re-upload", key=f"broken.reupload.{sf_id}"):
        st.session_state["upload.return_to_sample_id"] = sample_id_int
        st.switch_page("pages/upload.py")

    if actions[2].button(
        "Mark sample inactive", key=f"broken.deactivate.{sf_id}", type="secondary"
    ):
        try:
            client.patch(
                f"/api/v1/samples/{sample_id_int}",
                json_body={"is_active": False},
            )
            st.success("Sample marked inactive.")
            _close_dialog()
            st.rerun()
        except ApiError as exc:
            st.error(f"Mark inactive failed: {exc.message}")

    st.divider()
    if st.button("Close", key=f"broken.close.{sf_id}"):
        _close_dialog()
        st.rerun()


def _render_table(client, rows: list[dict]) -> None:
    header = st.columns([2, 4, 1.4, 1.4, 1.5])
    header[0].markdown("**Sample**")
    header[1].markdown("**File**")
    header[2].markdown("**Last verified**")
    header[3].markdown("**Status**")
    header[4].markdown("**Actions**")

    for row in rows:
        cols = st.columns([2, 4, 1.4, 1.4, 1.5])
        cols[0].markdown(f"`{row.get('sample_id')}`")
        uri = row.get("uri") or ""
        truncated = uri if len(uri) <= 64 else "…" + uri[-63:]
        cols[1].markdown(
            f"`{truncated}`",
            help=uri or None,
        )
        cols[2].caption(_relative_time(row.get("last_verified_at")))
        with cols[3]:
            render_badge(storage_state_badge(row.get("storage_state") or "BROKEN"))
        cols[4].caption(row.get("last_verification_status") or "—")
        if cols[4].button("Remediate", key=f"broken.open.{row['sample_files_id']}"):
            _open_dialog(row["sample_files_id"])


def render() -> None:
    _init_state()
    st.title(PAGE_TITLE)
    st.caption("Files that JACKPOT can no longer reach. Re-locate or re-upload to restore access.")

    if current_user() is None:
        st.warning("API unreachable — broken-files needs the backend.")
        return

    st.info(
        "JACKPOT periodically verifies external file references. When a "
        "file goes broken, JACKPOT can't read the URI anymore — perhaps "
        "the file was moved, deleted, or permissions changed. **Re-locate** "
        "(provide a new URI for the same content) or **re-upload** to "
        "restore access. Marking the sample inactive removes it from "
        "active listings without deleting the metadata."
    )

    client = get_client()

    # Filters live in the sidebar so the table area stays the focus.
    project_id = st.sidebar.number_input(
        "Project ID (0 = any)",
        min_value=0,
        value=int(st.session_state[SS_PROJECT]),
        step=1,
        key=SS_PROJECT,
    )
    lab_id = st.sidebar.number_input(
        "Lab ID (0 = any)",
        min_value=0,
        value=int(st.session_state[SS_LAB]),
        step=1,
        key=SS_LAB,
    )
    status_filter = st.sidebar.selectbox(
        "Verification status",
        ("",) + VERIFICATION_STATUSES,
        key=SS_STATUS,
    )

    params: dict = {
        "page": st.session_state[SS_PAGE],
        "per_page": 50,
        "sort_by": "last_verified_at",
        "sort_dir": "desc",
    }
    if project_id:
        params["project_id"] = int(project_id)
    if lab_id:
        params["lab_id"] = int(lab_id)
    if status_filter:
        params["status_filter"] = status_filter

    rows, total, pages = _fetch(client, params)

    if total == 0:
        st.success("✓ No broken files. All file references are healthy.")
        return

    st.caption(_summary_line(rows, total))
    _render_table(client, rows)

    # Remediation dialog (Streamlit ≥1.32 has st.dialog; we keep the
    # Streamlit-1.x portable path: render the form inline below the
    # table when a row is selected).
    target = st.session_state.get(SS_DIALOG_TARGET)
    if target is not None:
        target_row = next((r for r in rows if r["sample_files_id"] == target), None)
        if target_row is not None:
            with st.container(border=True):
                _render_remediation_dialog(client, target_row)

    nav = st.columns(3)
    if nav[0].button("← Prev", disabled=st.session_state[SS_PAGE] <= 1):
        st.session_state[SS_PAGE] = max(1, st.session_state[SS_PAGE] - 1)
        st.rerun()
    nav[1].markdown(f"Page **{st.session_state[SS_PAGE]}** / {pages}")
    if nav[2].button("Next →", disabled=st.session_state[SS_PAGE] >= pages):
        st.session_state[SS_PAGE] += 1
        st.rerun()


render()
