"""
BYOP pipeline registration wizard (B-BYOP-7).

Guides an operator through registering a Bring-Your-Own-Pipeline:
manifest upload, client-side schema validation with per-field feedback,
source details, and final registration against B-BYOP-4's router.

Stage 1 (static validation) and Stage 2 (sandbox dry-run) both run
server-side inside ``POST /api/v1/byop/pipelines`` — the router gates
atomically and exposes no standalone stage endpoints — so the commit
step surfaces per-stage results from that single call: a 422 with
``failed_checks`` is a Stage 1 failure, ``failed_steps`` is a Stage 2
sandbox failure, and a 201 carries ``validation_log`` (Stage 1) and
``sandbox_log`` (Stage 2) for review.

Uses ``httpx`` directly (per session spec) rather than ``ApiClient``
because the BYOP router returns plain FastAPI responses, not the
``backend/responses.py`` envelope — the structured 422 ``detail`` would
be flattened by the envelope unwrapping.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import streamlit as st
import yaml

from frontend.lib.api import get_client

PAGE_TITLE = "Register BYOP pipeline"
TOTAL_STEPS = 4
REGISTER_TIMEOUT_SEC = 630.0  # Stage 2 sandbox default hard timeout is 5 min

SS_STEP = "byop_reg.step"
SS_RAW = "byop_reg.manifest_raw"
SS_FILENAME = "byop_reg.filename"
SS_MANIFEST = "byop_reg.manifest"
SS_SOURCE = "byop_reg.source"
SS_RESULT = "byop_reg.result"
SS_STAGE_ERRORS = "byop_reg.stage_errors"

ENGINE_TYPES = {"nextflow", "snakemake", "wdl", "manifest"}
SOURCE_TYPES = ("git", "git_private", "tarball", "docker")
DATA_TYPES = {
    "paired_end_short_read",
    "single_end_short_read",
    "long_read",
    "assembly",
    "raw_signal",
    "metagenomic",
}


# ── schema validation (client-side, per design doc §2.1) ─────────────────


def _schema_check_rows(manifest: dict) -> list[dict[str, Any]]:
    """Per-field checks against the jackpot-pipeline.yaml shape (§2.1)."""

    def get(path: str) -> Any:
        node: Any = manifest
        for part in path.split("."):
            if not isinstance(node, dict):
                return None
            node = node.get(part)
        return node

    rows: list[dict[str, Any]] = []

    def check(field: str, expected: str, ok: bool) -> None:
        rows.append(
            {
                "field": field,
                "expected": expected,
                "provided": repr(get(field)),
                "result": "pass" if ok else "FAIL",
            }
        )

    check("api_version", "jackpot.io/v1", get("api_version") == "jackpot.io/v1")
    check("kind", "Pipeline", get("kind") == "Pipeline")

    name = get("metadata.name")
    check(
        "metadata.name",
        "lowercase-hyphen-only string",
        isinstance(name, str) and name != "" and name == name.lower() and " " not in name,
    )
    for field in ("metadata.display_name", "metadata.version", "metadata.description"):
        value = get(field)
        check(field, "non-empty string", isinstance(value, str) and value.strip() != "")
    authors = get("metadata.authors")
    check(
        "metadata.authors",
        "list with at least one entry having a name",
        isinstance(authors, list)
        and len(authors) >= 1
        and all(isinstance(a, dict) and a.get("name") for a in authors),
    )
    license_spdx = get("metadata.license")
    check(
        "metadata.license",
        "SPDX identifier string",
        isinstance(license_spdx, str) and license_spdx.strip() != "",
    )

    engine_type = get("engine.type")
    check("engine.type", f"one of {sorted(ENGINE_TYPES)}", engine_type in ENGINE_TYPES)
    for field in ("engine.version", "engine.entrypoint"):
        value = get(field)
        check(field, "non-empty string", isinstance(value, str) and value.strip() != "")

    for field in ("applicability.organism_names", "applicability.source_types"):
        value = get(field)
        check(field, "non-empty list", isinstance(value, list) and len(value) >= 1)
    data_types = get("applicability.data_types")
    check(
        "applicability.data_types",
        f"non-empty list from {sorted(DATA_TYPES)}",
        isinstance(data_types, list)
        and len(data_types) >= 1
        and all(d in DATA_TYPES for d in data_types),
    )

    for field in (
        "resources.cpu_min",
        "resources.memory_gb_min",
        "resources.storage_gb_estimate",
        "resources.walltime_minutes_estimate",
    ):
        value = get(field)
        check(field, "number", isinstance(value, int | float) and not isinstance(value, bool))
    for field in ("resources.gpu_required", "resources.internet_required"):
        check(field, "boolean", isinstance(get(field), bool))

    bundled = get("reference_data.bundled")
    check("reference_data.bundled", "boolean", isinstance(bundled, bool))
    if bundled is False:
        sources = get("reference_data.sources")
        check(
            "reference_data.sources",
            "non-empty list (required when bundled is false)",
            isinstance(sources, list) and len(sources) >= 1,
        )

    for field in (
        "outputs.results_directory",
        "outputs.results_schema",
        "outputs.primary_result_file",
        "outputs.pipeline_results_parser",
    ):
        value = get(field)
        check(field, "non-empty string", isinstance(value, str) and value.strip() != "")

    can_write = get("permissions.can_write_files_to")
    check(
        "permissions.can_write_files_to",
        "non-empty list",
        isinstance(can_write, list) and len(can_write) >= 1,
    )

    return rows


def _validate_manifest_schema(manifest: dict) -> list[str]:
    """All schema errors at once; empty list means the manifest shape is valid."""
    return [
        f"{row['field']}: expected {row['expected']}, got {row['provided']}"
        for row in _schema_check_rows(manifest)
        if row["result"] == "FAIL"
    ]


# ── backend call ──────────────────────────────────────────────────────────


def _commit_pipeline(manifest_yaml: str, source: dict, api_base: str) -> dict:
    """POST the registration; the router runs Stage 1 + Stage 2 server-side.

    Returns the created pipeline dict on success. Raises the httpx errors
    for the caller to render.
    """
    payload = {"manifest_yaml": manifest_yaml, **source}
    resp = httpx.post(
        f"{api_base}/api/v1/byop/pipelines",
        json=payload,
        timeout=REGISTER_TIMEOUT_SEC,
    )
    resp.raise_for_status()
    return resp.json()


def _stage_errors_from_detail(detail: Any) -> tuple[str, list[str]]:
    """Classify a 422 detail as a Stage 1 or Stage 2 failure."""
    if isinstance(detail, dict):
        if detail.get("failed_checks"):
            return "Stage 1 static validation failed", [
                f"{c.get('check_name')}: {c.get('message')}" for c in detail["failed_checks"]
            ]
        if detail.get("failed_steps"):
            outcome = detail.get("error", "SANDBOX_FAILED")
            return f"Stage 2 sandbox dry-run failed ({outcome})", [
                f"{s.get('step_name')}: {s.get('message')}" for s in detail["failed_steps"]
            ]
    return "Registration rejected", [str(detail)]


# ── wizard steps ──────────────────────────────────────────────────────────


def _init_state() -> None:
    st.session_state.setdefault(SS_STEP, 0)
    st.session_state.setdefault(SS_RAW, None)
    st.session_state.setdefault(SS_FILENAME, None)
    st.session_state.setdefault(SS_MANIFEST, None)
    st.session_state.setdefault(SS_SOURCE, {})
    st.session_state.setdefault(SS_RESULT, None)
    st.session_state.setdefault(SS_STAGE_ERRORS, None)


def _goto(step: int) -> None:
    st.session_state[SS_STEP] = step
    st.rerun()


def _back_button(to_step: int) -> None:
    if st.button("← Back"):
        _goto(to_step)


def _step_upload() -> None:
    st.subheader("Upload the pipeline manifest")
    st.write(
        "Every BYOP pipeline ships a `jackpot-pipeline.yaml` manifest. "
        "Upload it here (YAML or JSON)."
    )
    uploaded = st.file_uploader("jackpot-pipeline.yaml", type=["yaml", "yml", "json"])
    if uploaded is None:
        return
    raw = uploaded.getvalue().decode("utf-8", errors="replace")
    try:
        manifest = yaml.safe_load(raw)  # JSON is a YAML subset; one parser covers both
    except yaml.YAMLError as exc:
        st.error(f"File is not valid YAML/JSON: {exc}")
        return
    if not isinstance(manifest, dict):
        st.error("Manifest must be a mapping (top-level keys like `api_version`).")
        return
    st.session_state[SS_RAW] = raw
    st.session_state[SS_FILENAME] = uploaded.name
    st.session_state[SS_MANIFEST] = manifest
    st.success(f"Parsed `{uploaded.name}`.")
    if st.button("Continue to schema validation →"):
        _goto(1)


def _step_schema_validation() -> None:
    st.subheader("Schema validation")
    manifest = st.session_state[SS_MANIFEST]
    with st.expander("Parsed manifest", expanded=False):
        st.json(manifest)

    rows = _schema_check_rows(manifest)
    st.dataframe(rows, use_container_width=True)
    errors = _validate_manifest_schema(manifest)
    if errors:
        st.error(f"{len(errors)} schema check(s) failed — fix the manifest and re-upload:")
        for err in errors:
            st.write(f"- {err}")
        _back_button(0)
        return

    st.success("All schema checks passed.")
    col_back, col_next = st.columns(2)
    with col_back:
        _back_button(0)
    with col_next:
        if st.button("Continue to source details →"):
            _goto(2)


def _step_source_details() -> None:
    st.subheader("Source details")
    st.write("Where does JACKPOT fetch this pipeline from?")
    saved = st.session_state[SS_SOURCE]
    source_type = st.selectbox(
        "Source type",
        SOURCE_TYPES,
        index=SOURCE_TYPES.index(saved.get("source_type", "git")),
    )
    source: dict[str, Any] = {"source_type": source_type}
    if source_type in ("git", "git_private"):
        source["source_url"] = st.text_input("Git URL", value=saved.get("source_url", ""))
        source["source_ref"] = st.text_input(
            "Ref (tag preferred)", value=saved.get("source_ref", "")
        )
    elif source_type == "tarball":
        source["source_uploaded_uri"] = st.text_input(
            "Uploaded tarball URI", value=saved.get("source_uploaded_uri", "")
        )
        source["source_sha256"] = st.text_input(
            "Tarball sha256", value=saved.get("source_sha256", "")
        )
    else:  # docker
        source["source_url"] = st.text_input("Image reference", value=saved.get("source_url", ""))
        source["docker_digest"] = st.text_input(
            "Image digest (sha256:…)", value=saved.get("docker_digest", "")
        )
    st.session_state[SS_SOURCE] = source

    missing = [k for k, v in source.items() if k != "docker_digest" and not str(v).strip()]
    col_back, col_next = st.columns(2)
    with col_back:
        _back_button(1)
    with col_next:
        if st.button("Continue to review →"):
            if missing:
                st.error(f"Fill in: {', '.join(missing)}")
            else:
                _goto(3)


def _render_stage_results(result: dict) -> None:
    with st.expander("Stage 1 — static validation log", expanded=True):
        st.code(result.get("validation_log") or "(empty)")
    with st.expander("Stage 2 — sandbox dry-run log", expanded=True):
        st.code(result.get("sandbox_log") or "(empty)")


def _step_review_and_commit() -> None:
    st.subheader("Review & register")
    manifest = st.session_state[SS_MANIFEST]
    metadata = manifest.get("metadata") or {}
    engine = manifest.get("engine") or {}
    st.write(
        f"**{metadata.get('display_name')}** `{metadata.get('name')}` "
        f"v{metadata.get('version')} — engine `{engine.get('type')}`, "
        f"license `{metadata.get('license')}`"
    )
    st.write(f"Source: `{json.dumps(st.session_state[SS_SOURCE])}`")
    with st.expander("Full manifest", expanded=False):
        st.json(manifest)
    st.info(
        "Registering runs Stage 1 static validation and the Stage 2 sandbox "
        "dry-run server-side before anything is committed. The sandbox can "
        "take a few minutes."
    )

    result = st.session_state[SS_RESULT]
    if result is not None:
        st.success(
            f"Pipeline registered — byop_pipeline_id **{result.get('id')}**, "
            f"status `{result.get('pipeline_status')}`."
        )
        _render_stage_results(result)
        return

    stage_errors = st.session_state[SS_STAGE_ERRORS]
    if stage_errors is not None:
        title, messages = stage_errors
        st.error(title)
        for msg in messages:
            st.write(f"- {msg}")

    col_back, col_go = st.columns(2)
    with col_back:
        _back_button(2)
    with col_go:
        if not st.button("Register pipeline", type="primary"):
            return

    api_base = get_client().base_url  # same env-driven base URL as every page
    with st.spinner("Running Stage 1 validation and Stage 2 sandbox…"):
        try:
            created = _commit_pipeline(
                st.session_state[SS_RAW], st.session_state[SS_SOURCE], api_base
            )
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json().get("detail")
            except ValueError:
                detail = exc.response.text
            st.session_state[SS_STAGE_ERRORS] = _stage_errors_from_detail(detail)
            st.rerun()
        except httpx.RequestError as exc:
            st.session_state[SS_STAGE_ERRORS] = (
                "Could not reach the JACKPOT API",
                [f"Network error: {exc}"],
            )
            st.rerun()
        else:
            st.session_state[SS_RESULT] = created
            st.session_state[SS_STAGE_ERRORS] = None
            st.rerun()


_STEPS = [
    ("Upload manifest", _step_upload),
    ("Schema validation", _step_schema_validation),
    ("Source details", _step_source_details),
    ("Review & commit", _step_review_and_commit),
]


def render() -> None:
    st.title(PAGE_TITLE)
    _init_state()
    step = st.session_state[SS_STEP]
    st.progress(
        (step + 1) / TOTAL_STEPS, text=f"Step {step + 1} of {TOTAL_STEPS}: {_STEPS[step][0]}"
    )
    if st.session_state[SS_MANIFEST] is None and step > 0:
        st.session_state[SS_STEP] = 0
        step = 0
    _STEPS[step][1]()


render()
