"""
Sample ingest page — drag-and-drop FASTQ upload + metadata form.

Posts to ``POST /api/v1/ingest/upload`` which expects multipart with two
keys: ``metadata`` (JSON string) and ``fastq_r1`` (+ optional
``fastq_r2``). The backend runs the full validator + DLP scanner + file
detector chain, so this page only has to gather fields and relay the
files — business logic belongs server-side.

Live tier indicator
-------------------

Tier is computed by the backend validator (SUBMITTABLE / ANALYZABLE /
PRELIMINARY) and returned on the upload response. This page shows a
"best guess" pre-submission badge by looking at whether the most
commonly required fields are present; the authoritative tier lands on
the response screen after the validator runs.
"""

from __future__ import annotations

import io
import json

import streamlit as st

from frontend.components.badges import (
    SHARING_LEVELS,
    render_badge,
    scrub_badge,
    sharing_badge,
    tier_badge,
)
from frontend.lib.api import ApiError, get_client

PAGE_TITLE = "Upload samples"
SS_DRAFT = "upload.draft_metadata"
SS_LAST_RESULT = "upload.last_result"

SOURCE_TYPES = ("Human", "Animal", "Vector", "Wastewater", "Environmental")


def _guess_tier(meta: dict) -> str:
    """Cheap pre-submission estimate — not authoritative."""
    need_any = ("sample_id", "organism_name", "source_type", "date_collected")
    need_submittable = (
        "sequencing_platform",
        "sequencing_lab",
        "collection_location_country",
        "fastq_r1_uri",
    )
    if not all(meta.get(k) for k in need_any):
        return "PRELIMINARY"
    if all(meta.get(k) for k in need_submittable):
        return "SUBMITTABLE"
    return "ANALYZABLE"


def _init_state() -> None:
    st.session_state.setdefault(SS_DRAFT, {})


def _render_scrub_skip_section(meta: dict) -> None:
    with st.expander("Request scrubber skip"):
        st.caption(
            "Skip the PII scrubber only for FASTA-only submissions or when "
            "your Lab Director has pre-approved an exemption. This queues "
            "the request — Lab Director review required before scrub_status "
            "flips to SKIPPED."
        )
        reason = st.text_area("Justification (≥ 20 chars)", key="upload.skip_reason", height=90)
        if st.button("Submit skip request", disabled=len(reason.strip()) < 20):
            meta["_scrub_skip_request"] = reason.strip()
            st.success("Skip request attached — submit the upload to send it.")


def _render_response(result: dict) -> None:
    st.success(f"Sample **{result.get('sample_id')}** accepted (id={result.get('id')}).")
    cols = st.columns(3)
    with cols[0]:
        render_badge(tier_badge(result.get("quality_status")))
    with cols[1]:
        render_badge(sharing_badge(result.get("sharing_level")))
    with cols[2]:
        render_badge(scrub_badge(result.get("scrub_status")))
    with st.expander("Full validator response"):
        st.json(result)


def render() -> None:
    _init_state()
    st.title(PAGE_TITLE)
    st.caption(
        "Drop FASTQ files and fill in metadata — the server validator "
        "produces the tier, runs the DLP scan, and queues scrubber work."
    )
    client = get_client()

    with st.form("upload_form", clear_on_submit=False):
        cols = st.columns(2)
        sample_id = cols[0].text_input("Sample ID *", key="upload.sample_id")
        organism = cols[1].text_input("Organism name *", key="upload.organism")

        cols = st.columns(3)
        source_type = cols[0].selectbox("Source type *", SOURCE_TYPES, key="upload.source_type")
        sharing = cols[1].selectbox("Sharing level", SHARING_LEVELS, key="upload.sharing")
        sector = cols[2].selectbox(
            "Sector",
            ("", "clinical", "public_health", "research", "veterinary", "environmental"),
            key="upload.sector",
        )

        cols = st.columns(3)
        date_collected = cols[0].date_input("Date collected", value=None, key="upload.date_coll")
        date_sequenced = cols[1].date_input("Date sequenced", value=None, key="upload.date_seq")
        country = cols[2].text_input("Collection country", key="upload.country")

        cols = st.columns(3)
        platform = cols[0].text_input("Sequencing platform", key="upload.platform")
        seq_lab = cols[1].text_input("Sequencing lab", key="upload.seq_lab")
        coll_facility = cols[2].text_input("Collection facility", key="upload.coll_facility")

        cols = st.columns(2)
        lab_id = cols[0].number_input("Lab ID", min_value=0, step=1, key="upload.lab_id")
        project_id = cols[1].number_input(
            "Project ID", min_value=0, step=1, key="upload.project_id"
        )

        st.markdown("### Files")
        fastq_r1 = st.file_uploader("FASTQ R1 *", type=["fastq", "fq", "gz"], key="upload.fastq_r1")
        fastq_r2 = st.file_uploader(
            "FASTQ R2 (optional)", type=["fastq", "fq", "gz"], key="upload.fastq_r2"
        )

        if fastq_r1 and fastq_r2:
            st.caption(f"Paired run detected: `{fastq_r1.name}` + `{fastq_r2.name}`.")
        elif fastq_r1:
            st.caption(f"Single-end run: `{fastq_r1.name}`.")

        meta_preview = {
            "sample_id": sample_id,
            "organism_name": organism,
            "source_type": source_type,
            "sharing_level": sharing,
            "sector": sector or None,
            "date_collected": str(date_collected) if date_collected else None,
            "date_sequenced": str(date_sequenced) if date_sequenced else None,
            "collection_location_country": country,
            "sequencing_platform": platform,
            "sequencing_lab": seq_lab,
            "collection_facility": coll_facility,
            "lab_id": int(lab_id) if lab_id else None,
            "project_id": int(project_id) if project_id else None,
            "fastq_r1_uri": fastq_r1.name if fastq_r1 else None,
        }

        st.markdown("**Estimated tier** (server re-computes on submit):")
        render_badge(tier_badge(_guess_tier(meta_preview)))

        submitted = st.form_submit_button("Upload sample", type="primary")

    _render_scrub_skip_section(meta_preview)

    if submitted:
        if not (sample_id and organism and source_type and fastq_r1):
            st.error("sample_id, organism, source_type, and FASTQ R1 are required.")
            return
        meta = {k: v for k, v in meta_preview.items() if v not in (None, "")}
        files = {
            "fastq_r1": (fastq_r1.name, io.BytesIO(fastq_r1.getvalue()), "application/gzip"),
        }
        if fastq_r2 is not None:
            files["fastq_r2"] = (
                fastq_r2.name,
                io.BytesIO(fastq_r2.getvalue()),
                "application/gzip",
            )
        data = {"metadata": json.dumps(meta)}
        try:
            with st.spinner("Uploading — staging, validating, scanning…"):
                result = client.post("/api/v1/ingest/upload", files=files, data=data)
        except ApiError as exc:
            st.error(f"Upload failed: {exc.message}")
            return
        st.session_state[SS_LAST_RESULT] = result
        _render_response(result)
        return

    last = st.session_state.get(SS_LAST_RESULT)
    if last:
        with st.expander("Last upload result"):
            _render_response(last)


render()
