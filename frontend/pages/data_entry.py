"""
Guided metadata entry — used to complete Globus-imported samples and to
edit existing samples.

PATCH target: ``/api/v1/samples/{id}``. The backend whitelists which
fields can be patched (``_EDITABLE_FIELDS`` in ``samples.py``); this
page matches that whitelist so the server never has to reject a field
the UI put in front of the user.

Post-submission edit warning
----------------------------

If the sample has ``ncbi_submission_status`` or ``gisaid_submission_status``
set to anything other than ``NOT_SUBMITTED``, a modal explains that
editing those specific NCBI/GISAID-facing fields creates a discrepancy
between JACKPOT and the external database. The modal returns a confirm
flag stored in ``st.session_state['data_entry.ack_submitted']`` so the
save only fires after explicit acknowledgement.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import streamlit as st

from frontend.components.badges import (
    SHARING_LEVELS,
    render_badge,
    sharing_badge,
    storage_state_badge,
    tier_badge,
)
from frontend.lib.api import ApiError, get_client

PAGE_TITLE = "Metadata entry"
SS_DRAFT = "data_entry.draft"
SS_ACK = "data_entry.ack_submitted"
SS_LAST_SAVE = "data_entry.last_autosave"

NCBI_GISAID_SENSITIVE_FIELDS = (
    "organism_name",
    "collection_location_country",
    "collection_location_state",
    "date_collected",
    "host_species",
    "isolation_source",
    "bioproject_accession",
    "biosample_accession",
)


def _init_state() -> None:
    st.session_state.setdefault(SS_DRAFT, {})
    st.session_state.setdefault(SS_ACK, False)
    st.session_state.setdefault(SS_LAST_SAVE, None)


def _fetch_sample(client, sample_id: int) -> dict | None:
    try:
        return client.get(f"/api/v1/samples/{sample_id}")
    except ApiError as exc:
        st.error(f"Load failed: {exc.message}")
        return None


def _was_submitted(sample: dict) -> bool:
    for k in ("ncbi_submission_status", "gisaid_submission_status"):
        status = sample.get(k)
        if status and status != "NOT_SUBMITTED":
            return True
    return False


def _submitted_warning(draft: dict, original: dict) -> bool:
    """Return True if the user is editing any NCBI/GISAID-sensitive field."""
    for key in NCBI_GISAID_SENSITIVE_FIELDS:
        if key in draft and draft[key] != original.get(key):
            return True
    return False


def _autosave_draft() -> None:
    now = datetime.utcnow().isoformat()
    st.session_state[SS_LAST_SAVE] = now
    # "Auto-save" is local-only: the draft lives in st.session_state
    # until the user hits Save. Persisting drafts to the server is a
    # Month 3 feature gated on backlog item 57.


def _format_relative(iso: str | None) -> str:
    """Phase P0f F-10: short relative time for verification timestamps."""
    if not iso:
        return "—"
    try:
        ts = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - ts
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def _render_files_section(sample: dict) -> None:
    """Phase P0f F-10: surface storage_state for each file on the sample.

    A small inline section beneath the header badges showing one row
    per ``sample_files`` entry with its filename, storage_state badge,
    and last_verified_at relative time. Click on a BROKEN row routes
    the user to the broken-files admin view for remediation.
    """
    files = sample.get("files") or []
    if not files:
        return
    with st.expander(f"Files ({len(files)})", expanded=False):
        header = st.columns([3, 1.4, 1.4, 1])
        header[0].caption("**File**")
        header[1].caption("**Storage**")
        header[2].caption("**Last verified**")
        header[3].caption("")
        for f in files:
            row = st.columns([3, 1.4, 1.4, 1])
            uri = f.get("uri") or f.get("filename") or "—"
            truncated = uri if len(uri) <= 60 else "…" + uri[-59:]
            row[0].markdown(f"`{truncated}`", help=uri)
            with row[1]:
                render_badge(storage_state_badge(f.get("storage_state")))
            row[2].caption(_format_relative(f.get("last_verified_at")))
            if f.get("storage_state") == "BROKEN":
                if row[3].button("Fix", key=f"de.fix.{f['id']}"):
                    st.switch_page("pages/broken_files.py")


def _render_form(sample: dict) -> dict:
    draft = st.session_state[SS_DRAFT]

    cols = st.columns(2)
    draft["sample_id"] = cols[0].text_input(
        "Sample ID", value=sample.get("sample_id") or "", key="de.sample_id"
    )
    draft["organism_name"] = cols[1].text_input(
        "Organism", value=sample.get("organism_name") or "", key="de.organism"
    )

    cols = st.columns(3)
    draft["source_type"] = cols[0].text_input(
        "Source type", value=sample.get("source_type") or "", key="de.source_type"
    )
    sharing_default = sample.get("sharing_level") or "PRIVATE"
    draft["sharing_level"] = cols[1].selectbox(
        "Sharing level",
        SHARING_LEVELS,
        index=SHARING_LEVELS.index(sharing_default) if sharing_default in SHARING_LEVELS else 0,
        key="de.sharing",
    )
    draft["sector"] = cols[2].text_input(
        "Sector", value=sample.get("sector") or "", key="de.sector"
    )

    cols = st.columns(3)
    draft["date_collected"] = cols[0].text_input(
        "Date collected (YYYY or YYYY-MM or YYYY-MM-DD)",
        value=sample.get("date_collected") or "",
        key="de.date_coll",
    )
    draft["date_sequenced"] = cols[1].text_input(
        "Date sequenced", value=sample.get("date_sequenced") or "", key="de.date_seq"
    )
    draft["collection_location_country"] = cols[2].text_input(
        "Country",
        value=sample.get("collection_location_country") or "",
        key="de.country",
    )

    cols = st.columns(3)
    draft["collection_location_state"] = cols[0].text_input(
        "State",
        value=sample.get("collection_location_state") or "",
        key="de.state",
    )
    draft["sequencing_platform"] = cols[1].text_input(
        "Platform", value=sample.get("sequencing_platform") or "", key="de.platform"
    )
    draft["sequencing_lab"] = cols[2].text_input(
        "Sequencing lab", value=sample.get("sequencing_lab") or "", key="de.seq_lab"
    )

    draft["host_species"] = st.text_input(
        "Host species (required for Human/Animal)",
        value=sample.get("host_species") or "",
        key="de.host_species",
    )
    draft["isolation_source"] = st.text_input(
        "Isolation source",
        value=sample.get("isolation_source") or "",
        key="de.isolation_source",
    )
    draft["comments"] = st.text_area(
        "Comments", value=sample.get("comments") or "", height=90, key="de.comments"
    )

    return draft


def _submit(client, sample_id: int, draft: dict, original: dict) -> None:
    # Only send fields the user actually changed — stale defaults would
    # fail the server's _EDITABLE_FIELDS whitelist noisily.
    changed = {k: v for k, v in draft.items() if v != original.get(k) and v != ""}
    if not changed:
        st.info("Nothing to save — no fields changed.")
        return
    try:
        with st.spinner("Saving…"):
            updated = client.patch(f"/api/v1/samples/{sample_id}", json_body=changed)
    except ApiError as exc:
        st.error(f"Save failed: {exc.message}")
        return
    st.success(f"Saved sample **{updated.get('sample_id')}**.")
    st.session_state[SS_DRAFT] = {}
    st.session_state[SS_ACK] = False


def render() -> None:
    _init_state()
    st.title(PAGE_TITLE)

    client = get_client()
    sample_id = st.number_input("Sample ID to edit", min_value=1, step=1, key="de.load_sample_id")
    if not sample_id:
        st.info("Pick a sample ID to load.")
        return

    sample = _fetch_sample(client, int(sample_id))
    if not sample:
        return

    cols = st.columns([1, 1, 2])
    with cols[0]:
        render_badge(tier_badge(sample.get("quality_status")))
    with cols[1]:
        render_badge(sharing_badge(sample.get("sharing_level")))
    cols[2].caption(
        f"ingest: {sample.get('ingest_timestamp') or '—'} · "
        f"scrub: {sample.get('scrub_status') or '—'}"
    )

    _render_files_section(sample)

    draft = _render_form(sample)
    _autosave_draft()
    st.caption(f"Draft auto-saved locally at {st.session_state[SS_LAST_SAVE] or '—'}")

    submitted_elsewhere = _was_submitted(sample)
    needs_ack = submitted_elsewhere and _submitted_warning(draft, sample)

    if needs_ack and not st.session_state[SS_ACK]:
        st.warning(
            "This sample has been submitted to NCBI/GISAID. Editing these "
            "fields will create a discrepancy between JACKPOT and the "
            "external database."
        )
        if st.button("I understand — continue"):
            st.session_state[SS_ACK] = True
            st.rerun()
        return

    if st.button("Save changes", type="primary"):
        _submit(client, int(sample_id), draft, sample)
        # Give Streamlit a moment so the success banner is visible before
        # a follow-up click re-runs the script.
        time.sleep(0.1)


render()
