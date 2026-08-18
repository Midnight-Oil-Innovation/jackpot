#!/usr/bin/env python3
r"""stamp_status_headers.py — add the doc-guard Status header to docs/ files.

Three tiers of certainty, and the script only auto-writes the first two:

  Tier 1  mechanical      docs/archived/** -> Superseded ; logs -> History
  Tier 2  canonical map   anchors named in domain_reference.md -> Canonical
  Tier 3  NEEDS-DECISION   everything else, INCLUDING known-stale anchors

Tier 3 is deliberate. A script must not decide Canonical vs Reference for a live
doc, because a wrong Canonical header tells the guard (and every future reader) a
stale file is authoritative — the exact drift the guard exists to catch. Those get
a NEEDS-DECISION placeholder header and a report line; you resolve them by hand.

The header is inserted as the first line, as a blockquote the guard recognizes:
    > **Status:** Canonical — <one-line reason>

Idempotent: a file that already has a Status header is left untouched and reported
as "has-header". Run with --apply to write; default is a dry-run report.

Usage:
  python scripts/stamp_status_headers.py                 # dry run: show the plan
  python scripts/stamp_status_headers.py --apply         # write Tier 1 + Tier 2
  python scripts/stamp_status_headers.py --apply --stamp-needs-decision
      # also write NEEDS-DECISION placeholders so the guard stops erroring while
      # you work through them (each still fails your review, not the guard)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DOCS = Path("docs")
HEADER_RE = re.compile(r"^\s*>\s*\*\*Status:\*\*", re.IGNORECASE)

# --- Tier 2: canonical anchors, sourced from domain_reference.md -------------
# These are named as source-of-truth anchor documents. Paths are relative to docs/.
CANONICAL = {
    "domain_reference.md": "source-of-truth map for the doc set",
    "architecture.md": "system architecture v6.0 (post-Cluster-A)",
    "platform_landscape.md": "OSS pathogen-genomics comparative landscape",
    "strategic_vision.md": "strategic synthesis (CDC DMI / North Star / STLT)",
    "governance_alignment.md": "WHO / GA4GH / FAIR+CARE alignment matrices",
    "federation.md": "federation architecture (3 levels)",
    "federation_operations.md": "operator-facing federation reference",
    "wastewater.md": "wastewater surveillance schema",
    "wastewater_software_landscape.md": "wastewater OSS comparative landscape",
    "byop_and_eukaryotic_design.md": "multi-engine BYOP + eukaryotic design",
    "e2e_uat_plan.md": "E-1 laptop UAT plan, 6-role RBAC",
    "deploy/gcp.md": "GCP deployment guide (post-Cluster-F)",
    "architecture/sovereignty-compliant-deletion.md": "Phase 24.5 design lockdown (PR #20)",
    "immune_detection_core_redesign.md": "frozen detection-core redesign spec",
}

# --- Tier 1b: History logs (append-only records, not authoritative refs) -----
HISTORY = {
    "learnings.md": "append-only learnings log",
    "jackpot_session_summary_and_backlog.md": "session history + retrospective",
}

# --- Tier 3 flags: anchors your own notes mark as stale ----------------------
# Named in the anchor list BUT domain_reference / the redesign flag them as
# describing the pre-redesign architecture. The script refuses to auto-canonize
# these; you decide Canonical-with-caveat vs Superseded.
KNOWN_STALE = {
    "immune_platform.md": "anchor list calls it canonical, BUT flagged as pre-redesign; "
    "superseded in part by immune_detection_core_redesign.md",
    "detection_landscape.md": "anchor list calls it canonical, BUT flagged as pre-redesign; "
    "reconcile against immune_detection_core_redesign.md",
}


def classify(rel: str) -> tuple[str, str]:
    """Return (status, reason). status in {Superseded, History, Canonical, NEEDS-DECISION}."""
    if rel.startswith("archived/"):
        return "Superseded", "archived (directory convention)"
    if rel in KNOWN_STALE:
        return "NEEDS-DECISION", KNOWN_STALE[rel]
    if rel in HISTORY:
        return "History", HISTORY[rel]
    if rel in CANONICAL:
        return "Canonical", CANONICAL[rel]
    return "NEEDS-DECISION", "not in the canonical map; classify by hand"


def has_header(path: Path) -> bool:
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            return bool(HEADER_RE.match(line))
    except OSError:
        return False
    return False


def header_line(status: str, reason: str) -> str:
    if status == "Superseded":
        return f"> **Status:** Superseded — {reason}. Historical; do not cite as current."
    if status == "History":
        return f"> **Status:** History — {reason}. Point-in-time record."
    if status == "Canonical":
        return f"> **Status:** Canonical — {reason}."
    return (
        f"> **Status:** NEEDS-DECISION — {reason}. "
        f"Replace with Canonical | Reference | History | Superseded."
    )


def insert_header(path: Path, line: str) -> None:
    original = path.read_text(encoding="utf-8", errors="replace")
    path.write_text(line + "\n\n" + original, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write headers (default: dry run)")
    ap.add_argument(
        "--stamp-needs-decision",
        action="store_true",
        help="also write NEEDS-DECISION placeholders (still need your review)",
    )
    ap.add_argument("--docs", type=Path, default=DOCS)
    args = ap.parse_args()

    if not args.docs.is_dir():
        print(f"error: {args.docs} not found", file=sys.stderr)
        return 2

    tiers: dict[str, list[str]] = {
        "Canonical": [],
        "Superseded": [],
        "History": [],
        "NEEDS-DECISION": [],
        "has-header": [],
    }
    wrote = 0
    for path in sorted(args.docs.rglob("*.md")):
        rel = str(path.relative_to(args.docs))
        if has_header(path):
            tiers["has-header"].append(rel)
            continue
        status, reason = classify(rel)
        tiers[status].append(f"{rel}  ({reason})")
        should_write = args.apply and (status != "NEEDS-DECISION" or args.stamp_needs_decision)
        if should_write:
            insert_header(path, header_line(status, reason))
            wrote += 1

    for tier in ("Canonical", "History", "Superseded", "NEEDS-DECISION", "has-header"):
        rows = tiers[tier]
        print(f"\n=== {tier} ({len(rows)}) ===")
        for r in rows:
            print(f"  {r}")

    mode = "WROTE" if args.apply else "DRY RUN (use --apply to write)"
    print(f"\n{mode}. {wrote} header(s) written.")
    if tiers["NEEDS-DECISION"]:
        print(f"\n{len(tiers['NEEDS-DECISION'])} file(s) need a human decision. For each, pick a")
        print("status and set the header by hand. The two known-stale anchors")
        print("(immune_platform.md, detection_landscape.md) are the ones to think about.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
