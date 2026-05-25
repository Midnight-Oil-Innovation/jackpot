"""
Tier + sharing + status badges — single source of truth for colours.

Every page that renders a tier ("PRELIMINARY" etc.) or sharing level
("PUBLIC" etc.) goes through these helpers. Keeping the palette here
means a React migration only has to port one file rather than hunt for
hex codes across pages. The component layer uses ``st.markdown`` with
inline HTML because Streamlit does not expose a native pill widget.
"""

from __future__ import annotations

import streamlit as st

# Order matters: used by ``st.selectbox`` filters to preserve the
# canonical ordering instead of sorting alphabetically.
QUALITY_TIERS: tuple[str, ...] = ("PRELIMINARY", "ANALYZABLE", "SUBMITTABLE")
SHARING_LEVELS: tuple[str, ...] = ("PRIVATE", "LAB", "DISCOVERABLE", "PUBLIC")
SCRUB_STATUSES: tuple[str, ...] = (
    "PENDING",
    "IN_PROGRESS",
    "COMPLETE",
    "FAILED",
    "SKIPPED",
)
# Phase P0f F-10: storage_state values surfaced on the sample detail
# page and the broken-files admin view. Order is the lifecycle order
# (EXTERNAL → MANAGED → MIRRORED → STAGED, with BROKEN as the terminal
# failure state).
STORAGE_STATES: tuple[str, ...] = (
    "EXTERNAL",
    "MANAGED",
    "MIRRORED",
    "STAGED",
    "BROKEN",
)

_TIER_COLORS: dict[str, tuple[str, str]] = {
    "PRELIMINARY": ("#7f1d1d", "#fecaca"),  # red-900 on red-200
    "ANALYZABLE": ("#854d0e", "#fde68a"),  # amber-900 on amber-200
    "SUBMITTABLE": ("#14532d", "#bbf7d0"),  # green-900 on green-200
}

_SHARING_COLORS: dict[str, tuple[str, str]] = {
    "PRIVATE": ("#1f2937", "#e5e7eb"),  # gray-800 on gray-200
    "LAB": ("#1e3a8a", "#bfdbfe"),  # blue-900 on blue-200
    "DISCOVERABLE": ("#5b21b6", "#ddd6fe"),  # purple-900 on purple-200
    "PUBLIC": ("#0f766e", "#99f6e4"),  # teal-700 on teal-200
}

_SCRUB_COLORS: dict[str, tuple[str, str]] = {
    "PENDING": ("#92400e", "#fde68a"),
    "IN_PROGRESS": ("#1e3a8a", "#bfdbfe"),
    "COMPLETE": ("#14532d", "#bbf7d0"),
    "FAILED": ("#7f1d1d", "#fecaca"),
    "SKIPPED": ("#1f2937", "#e5e7eb"),
}

_STORAGE_STATE_COLORS: dict[str, tuple[str, str]] = {
    # Phase P0f F-10. Neutral gray for the no-copy default; green for
    # JACKPOT-owned bytes; blue for managed-with-origin; amber for the
    # transient run-staging state; red for the terminal BROKEN state.
    "EXTERNAL": ("#1f2937", "#e5e7eb"),  # gray-800 on gray-200
    "MANAGED": ("#14532d", "#bbf7d0"),  # green-900 on green-200
    "MIRRORED": ("#1e3a8a", "#bfdbfe"),  # blue-900 on blue-200
    "STAGED": ("#92400e", "#fde68a"),  # amber-900 on amber-200
    "BROKEN": ("#7f1d1d", "#fecaca"),  # red-900 on red-200
}

_STORAGE_STATE_LABELS: dict[str, str] = {
    "EXTERNAL": "External",
    "MANAGED": "Managed",
    "MIRRORED": "Mirrored",
    "STAGED": "Staged",
    "BROKEN": "Broken",
}

_RUN_STATUS_COLORS: dict[str, tuple[str, str]] = {
    "PENDING": ("#1f2937", "#e5e7eb"),
    "QUEUED": ("#92400e", "#fde68a"),
    "RUNNING": ("#1e3a8a", "#bfdbfe"),
    "SUCCEEDED": ("#14532d", "#bbf7d0"),
    "COMPLETED": ("#14532d", "#bbf7d0"),
    "FAILED": ("#7f1d1d", "#fecaca"),
    "CANCELED": ("#1f2937", "#e5e7eb"),
}


def _pill(label: str, fg: str, bg: str) -> str:
    return (
        f"<span style='display:inline-block;padding:2px 10px;border-radius:999px;"
        f"background:{bg};color:{fg};font-size:0.78rem;font-weight:600;"
        f"font-family:-apple-system,system-ui,sans-serif;letter-spacing:0.02em'>"
        f"{label}</span>"
    )


def tier_badge(tier: str | None) -> str:
    if not tier:
        return _pill("UNSCORED", "#1f2937", "#e5e7eb")
    fg, bg = _TIER_COLORS.get(tier, ("#1f2937", "#e5e7eb"))
    return _pill(tier, fg, bg)


def sharing_badge(level: str | None) -> str:
    if not level:
        return _pill("—", "#1f2937", "#e5e7eb")
    fg, bg = _SHARING_COLORS.get(level, ("#1f2937", "#e5e7eb"))
    return _pill(level, fg, bg)


def scrub_badge(status: str | None) -> str:
    if not status:
        return _pill("—", "#1f2937", "#e5e7eb")
    fg, bg = _SCRUB_COLORS.get(status, ("#1f2937", "#e5e7eb"))
    return _pill(status, fg, bg)


def run_status_badge(status: str | None) -> str:
    if not status:
        return _pill("—", "#1f2937", "#e5e7eb")
    fg, bg = _RUN_STATUS_COLORS.get(status, ("#1f2937", "#e5e7eb"))
    return _pill(status, fg, bg)


def storage_state_badge(state: str | None) -> str:
    """Render a storage_state pill for the sample detail and broken-files views.

    Phase P0f F-10. Maps ``EXTERNAL`` / ``MANAGED`` / ``MIRRORED`` /
    ``STAGED`` / ``BROKEN`` to the canonical colour for that state and
    the human-readable label. Unknown states fall back to the neutral
    gray pill so a future schema addition does not crash the UI.
    """
    if not state:
        return _pill("—", "#1f2937", "#e5e7eb")
    fg, bg = _STORAGE_STATE_COLORS.get(state, ("#1f2937", "#e5e7eb"))
    label = _STORAGE_STATE_LABELS.get(state, state.title())
    return _pill(label, fg, bg)


def render_badge(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)
