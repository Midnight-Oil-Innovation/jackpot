#!/usr/bin/env python3
r"""verify_licenses_assistant.py — fetch upstream LICENSE files for review.

For each row you point it at, it fetches the tool's own LICENSE file from the
URL you supply, extracts the SPDX identifier if the file declares one, and prints
a compact report. It DOES NOT modify docs/THIRD_PARTY_LICENSES.md, and it does
not decide what the license is. You decide, then you update the row.

The whole reason B-LICENSE-1 exists is that third-party summaries (blogs, READMEs,
package indexes) have been wrong about licenses at least once in this project's
history (alibi-detect, verified 2026-06). An auto-updating script would defeat the
guardrail by re-introducing the same failure mode at machine speed. So this
prints; you read; you update the row; you re-run the gate.

Usage:
  python scripts/verify_licenses_assistant.py --config scripts/license_sources.yaml
  python scripts/verify_licenses_assistant.py --row METAGENE-1 --url https://.../LICENSE
  python scripts/verify_licenses_assistant.py --config scripts/license_sources.yaml \
      --only "METAGENE-1,SeqScreen"

Stdlib only. Uses urllib for fetches.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

# SPDX identifiers we recognize inline in a LICENSE file's first ~200 lines.
# Order matters: match specific before generic (e.g. AGPL before GPL).
SPDX_CANDIDATES = [
    (
        "AGPL-3.0-or-later",
        r"\bGNU\s+AFFERO\s+GENERAL\s+PUBLIC\s+LICENSE.*Version\s+3.*or\s+(?:any\s+)?later",
    ),
    ("AGPL-3.0", r"\bGNU\s+AFFERO\s+GENERAL\s+PUBLIC\s+LICENSE.*Version\s+3"),
    ("GPL-3.0-or-later", r"\bGNU\s+GENERAL\s+PUBLIC\s+LICENSE.*Version\s+3.*or\s+(?:any\s+)?later"),
    ("GPL-3.0", r"\bGNU\s+GENERAL\s+PUBLIC\s+LICENSE.*Version\s+3"),
    ("GPL-2.0-or-later", r"\bGNU\s+GENERAL\s+PUBLIC\s+LICENSE.*Version\s+2.*or\s+(?:any\s+)?later"),
    ("GPL-2.0", r"\bGNU\s+GENERAL\s+PUBLIC\s+LICENSE.*Version\s+2"),
    ("LGPL-3.0", r"\bGNU\s+LESSER\s+GENERAL\s+PUBLIC\s+LICENSE.*Version\s+3"),
    ("LGPL-2.1", r"\bGNU\s+LESSER\s+GENERAL\s+PUBLIC\s+LICENSE.*Version\s+2\.1"),
    ("Apache-2.0", r"\bApache\s+License.*Version\s+2\.0"),
    ("MPL-2.0", r"\bMozilla\s+Public\s+License\s+Version\s+2\.0"),
    ("BSD-3-Clause", r"\bRedistributions.*binary\s+form.*name\s+of\s+the.*may\s+not\s+be\s+used"),
    ("BSD-2-Clause", r"\bRedistribution\s+and\s+use\s+in\s+source\s+and\s+binary\s+forms"),
    ("MIT", r"\bPermission\s+is\s+hereby\s+granted.*free\s+of\s+charge"),
    ("ISC", r"\bPermission\s+to\s+use,\s+copy,\s+modify,\s+and/or\s+distribute"),
    ("BSL-1.1", r"\bBusiness\s+Source\s+License\s+1\.1"),
    ("SSPL-1.0", r"\bServer\s+Side\s+Public\s+License"),
    ("Elastic-2.0", r"\bElastic\s+License\s+2\.0"),
    ("CC0-1.0", r"\bCC0\s+1\.0"),
    ("Unlicense", r"\bThis\s+is\s+free\s+and\s+unencumbered\s+software"),
]


@dataclass
class Row:
    name: str
    url: str
    notes: str = ""


@dataclass
class Result:
    row: Row
    status: str  # "ok", "http_error", "no_license_text", "ambiguous"
    fetched_url: str = ""
    detected: list[str] = field(default_factory=list)
    excerpt: str = ""
    error: str = ""


def fetch(url: str, timeout: int = 15) -> tuple[str, str]:
    """Return (final_url, body). Raises on network error."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "JACKPOT-license-assistant/1.0 (see docs/THIRD_PARTY_LICENSES.md)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.geturl(), resp.read().decode("utf-8", errors="replace")


def detect_licenses(text: str) -> list[str]:
    """Return SPDX identifiers whose signature appears in the first ~200 lines.
    Deduplicated, order-preserved (specific-before-generic order)."""
    head = "\n".join(text.splitlines()[:200])
    hits: list[str] = []
    seen: set[str] = set()
    for spdx, pattern in SPDX_CANDIDATES:
        if re.search(pattern, head, re.IGNORECASE | re.DOTALL) and spdx not in seen:
            hits.append(spdx)
            seen.add(spdx)
    # If we detected a family-generic hit (e.g. GPL-3.0) alongside its more-specific
    # variant (GPL-3.0-or-later), drop the generic. Same for Affero and BSD.
    for specific, generic in [
        ("AGPL-3.0-or-later", "AGPL-3.0"),
        ("GPL-3.0-or-later", "GPL-3.0"),
        ("GPL-2.0-or-later", "GPL-2.0"),
        ("BSD-3-Clause", "BSD-2-Clause"),
    ]:
        if specific in hits and generic in hits:
            hits.remove(generic)
    return hits


def excerpt(text: str, max_chars: int = 400) -> str:
    """A short, informative slice from the head of the LICENSE file."""
    body = text.strip()
    return body[:max_chars] + ("..." if len(body) > max_chars else "")


def check_row(row: Row) -> Result:
    try:
        final_url, body = fetch(row.url)
    except urllib.error.HTTPError as e:
        return Result(row, "http_error", error=f"HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        return Result(row, "http_error", error=f"URL error: {e.reason}")
    except Exception as e:  # noqa: BLE001
        return Result(row, "http_error", error=f"{type(e).__name__}: {e}")
    detected = detect_licenses(body)
    if not detected:
        return Result(row, "no_license_text", fetched_url=final_url, excerpt=excerpt(body))
    status = "ok" if len(detected) == 1 else "ambiguous"
    return Result(row, status, fetched_url=final_url, detected=detected, excerpt=excerpt(body))


def load_config(path: Path) -> list[Row]:
    """Minimal YAML-ish parser (indented `- name:`/`url:` blocks). Stdlib only, so no
    dependency on PyYAML; the file is small and hand-curated."""
    rows: list[Row] = []
    current: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("- "):
            if current.get("name"):
                rows.append(Row(current["name"], current.get("url", ""), current.get("notes", "")))
            current = {}
            body = line[2:].strip()
            if body.startswith("name:"):
                current["name"] = body.split(":", 1)[1].strip()
        elif ":" in line:
            key, _, val = line.strip().partition(":")
            current[key.strip()] = val.strip()
    if current.get("name"):
        rows.append(Row(current["name"], current.get("url", ""), current.get("notes", "")))
    return [r for r in rows if r.url]


def print_report(results: list[Result]) -> None:
    for r in results:
        print(f"\n=== {r.row.name} ===")
        if r.row.notes:
            print(f"  note: {r.row.notes}")
        print(f"  fetched: {r.fetched_url or r.row.url}")
        if r.status == "http_error":
            print(f"  FAIL: {r.error}")
            print("  action: open the URL in a browser and copy the SPDX ID by hand.")
            continue
        if r.status == "no_license_text":
            print("  WARN: no SPDX license signature detected in the first 200 lines.")
            print("  excerpt:")
            for line in r.excerpt.splitlines()[:8]:
                print(f"    | {line}")
            print("  action: this may be a landing page, not the raw LICENSE. Refine the URL.")
            continue
        if r.status == "ambiguous":
            print(f"  AMBIGUOUS: multiple signatures detected: {', '.join(r.detected)}")
            print("  action: read the file yourself; the header comment usually names")
            print("          the intended one.")
            continue
        print(f"  detected: {r.detected[0]}")
        print("  suggested row update:")
        today = time.strftime("%Y-%m-%d")
        print(
            f"    | {r.row.name} | {r.detected[0]} | (fill scope) | "
            f"verified {today} against {r.fetched_url} |"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch upstream LICENSE files for review.")
    ap.add_argument(
        "--config", type=Path, help="YAML file listing rows to verify (see license_sources.yaml)"
    )
    ap.add_argument("--row", help="single row name (use with --url)")
    ap.add_argument("--url", help="LICENSE URL for --row mode")
    ap.add_argument("--only", help="comma-separated row names to check from --config")
    ap.add_argument(
        "--pause", type=float, default=1.0, help="seconds to wait between fetches (be polite)"
    )
    args = ap.parse_args()

    if args.row and args.url:
        rows = [Row(args.row, args.url)]
    elif args.config:
        rows = load_config(args.config)
        if args.only:
            wanted = {n.strip() for n in args.only.split(",")}
            rows = [r for r in rows if r.name in wanted]
    else:
        ap.error("provide --config or (--row and --url)")

    results: list[Result] = []
    for i, row in enumerate(rows):
        print(f"[{i + 1}/{len(rows)}] fetching {row.name}...", file=sys.stderr)
        results.append(check_row(row))
        if i + 1 < len(rows):
            time.sleep(args.pause)

    print_report(results)

    # Exit status: 0 = every row detected exactly one SPDX; 1 = anything that
    # needs human attention. Non-zero is a nudge, not a failure of the gate itself.
    return 0 if all(r.status == "ok" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
