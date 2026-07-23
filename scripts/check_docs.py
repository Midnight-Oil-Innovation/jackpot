#!/usr/bin/env python3
"""Documentation drift guard for JACKPOT.

Enforces, over the docs tree:

  1. Header presence   Every tracked .md declares a Status class in its first lines.
  2. History exemption History-class docs and anything under docs/archived/ are
                       exempt from the drift and denylist checks.
  3. Numeric drift     Tracked facts either must not be hardcoded (mode="forbid")
                       or must match the canonical STATUS value (mode="pin").
  4. Archived hygiene  Files under archived/ must be Superseded or History, never
                       Canonical or Reference.
  5. Denylist tripwire Seeded superseded phrases (scenario 7-vs-4, NSA-as-substrate)
                       fail the build wherever they appear in a non-exempt doc.

Header conventions recognized (put one near the top of the file):

  Markdown:  > **Status:** Canonical — ...        (Canonical | Reference | History | Superseded)
  YAML/txt:  # status: reference

Suppress a single line that legitimately trips a check by ending it with `drift-ok`
(in a comment or inline), e.g.  `... migrated from schema v4.4 to v5.0  <!-- drift-ok -->`.

Usage:
  python scripts/check_docs.py [--docs-dir docs] [--status-file docs/STATUS.md]

Exit code 0 when clean, 1 when any violation is found. Stdlib only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ----------------------------------------------------------------------------- config

STATUS_CLASSES = {"canonical", "reference", "history", "superseded"}
ARCHIVED_ALLOWED = {"superseded", "history"}
EXEMPT_SUBDIR = "archived"  # relative to docs-dir; also drift-exempt
HEADER_SCAN_LINES = 15
SUPPRESS_MARKER = "drift-ok"

# Header parsers: markdown blockquote form and comment form.
HEADER_PATTERNS = (
    re.compile(r"^\s*>\s*\*\*status:\*\*\s*([A-Za-z]+)", re.IGNORECASE),
    re.compile(r"^\s*(?:#|<!--)\s*status:\s*([A-Za-z]+)", re.IGNORECASE),
)

# Tracked facts. mode="forbid": any match in a non-exempt doc is a violation
# (these must never be hardcoded; reference STATUS instead). mode="pin": a match
# is a violation only if it disagrees with the canonical value in STATUS.
TRACKED_FACTS = (
    {
        "name": "test_count",
        "regex": re.compile(r"\b\d{2,}\s+tests?\s+(?:passing|passed)\b", re.IGNORECASE),
        "mode": "forbid",
        "message": "hardcoded test-count baseline; reference the STATUS block instead",
    },
    {
        "name": "python_version",
        "regex": re.compile(r"\bPython\s+3\.(\d+)\b"),
        "mode": "pin",
        "status_key": "python_version",  # STATUS value like "3.12"
        "normalize_doc": lambda m: f"3.{m.group(1)}",
        "normalize_status": lambda v: v.strip(),
        "message": "Python version disagrees with STATUS",
    },
    {
        "name": "schema_version",
        "regex": re.compile(r"\b[Ss]chema\s+v(\d+\.\d+)\b"),
        "mode": "pin",
        "status_key": "schema_version",  # STATUS value like "v5.0"
        "normalize_doc": lambda m: m.group(1),
        "normalize_status": lambda v: v.strip().lstrip("vV"),
        "message": "schema version disagrees with STATUS",
    },
    # Enable if you want coverage pinned too. Left off by default because the CI
    # floor (a constant) and current coverage (a variable) are easily confused.
    # {"name": "coverage", "regex": re.compile(r"\b\d{1,3}(?:\.\d+)?%\s+coverage\b"),
    #  "mode": "forbid", "message": "hardcoded coverage; reference STATUS"},
)

# Superseded-claim tripwire. Extend as new supersessions land.
DENYLIST = (
    {
        "regex": re.compile(r"\b(?:seven|7)\s+install\s+scenarios\b", re.IGNORECASE),
        "message": (
            "superseded: the scenario taxonomy is four (A/B/C/D); runtime configs are not scenarios"
        ),
    },
    {
        "regex": re.compile(r"NSA\s+as\s+the\s+shared\s+bio", re.IGNORECASE),
        "message": (
            "superseded: NSA is cyber-only; removed from the bio detection path per the redesign"
        ),
    },
    {
        "regex": re.compile(
            r"foundation[- ]model\s+embeddings\s+(?:are\s+)?rejected", re.IGNORECASE
        ),
        "message": "superseded: FM-embedding AD is the engine per the redesign",
    },
)

# ----------------------------------------------------------------------------- helpers


class Violation:
    __slots__ = ("path", "line", "message")

    def __init__(self, path: str, line: int | None, message: str) -> None:
        self.path = path
        self.line = line
        self.message = message

    def __str__(self) -> str:
        loc = f"{self.path}:{self.line}" if self.line else self.path
        return f"  {loc}: {self.message}"


def load_status(status_file: Path) -> dict[str, str] | None:
    if not status_file.exists():
        return None
    values: dict[str, str] = {}
    kv = re.compile(r"^([a-z_]+):\s*(.+?)\s*$")
    for raw in status_file.read_text(encoding="utf-8").splitlines():
        m = kv.match(raw.strip())
        if m:
            values[m.group(1)] = m.group(2)
    return values


def parse_header_class(path: Path) -> str | None:
    with path.open(encoding="utf-8", errors="replace") as fh:
        for _ in range(HEADER_SCAN_LINES):
            line = fh.readline()
            if not line:
                break
            for pat in HEADER_PATTERNS:
                m = pat.match(line)
                if m:
                    cls = m.group(1).lower()
                    return cls if cls in STATUS_CLASSES else None
    return None


def check_drift(path: Path, status: dict[str, str] | None) -> list[Violation]:
    out: list[Violation] = []
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if SUPPRESS_MARKER in line:
            continue
        for fact in TRACKED_FACTS:
            m = fact["regex"].search(line)
            if not m:
                continue
            if fact["mode"] == "forbid":
                out.append(Violation(str(path), i, f'{fact["message"]} ("{m.group(0).strip()}")'))
            elif fact["mode"] == "pin":
                if status is None:
                    continue  # STATUS not present yet; skip pin checks
                canonical = status.get(fact["status_key"])
                if canonical is None:
                    continue
                doc_val = fact["normalize_doc"](m)
                status_val = fact["normalize_status"](canonical)
                if doc_val != status_val:
                    out.append(
                        Violation(
                            str(path),
                            i,
                            f'{fact["message"]}: found "{m.group(0).strip()}", '
                            f"STATUS says {canonical}",
                        )
                    )
        for entry in DENYLIST:
            m = entry["regex"].search(line)
            if m:
                out.append(Violation(str(path), i, f'{entry["message"]} ("{m.group(0).strip()}")'))
    return out


# ----------------------------------------------------------------------------- main


def run(docs_dir: Path, status_file: Path) -> list[Violation]:
    status = load_status(status_file)
    violations: list[Violation] = []

    if status is None:
        print(f"note: {status_file} not found; pin-mode checks (python/schema version) skipped.\n")

    for md in sorted(docs_dir.rglob("*.md")):
        rel = md.relative_to(docs_dir)
        in_archived = rel.parts and rel.parts[0] == EXEMPT_SUBDIR

        cls = parse_header_class(md)
        if cls is None:
            violations.append(
                Violation(
                    str(md),
                    None,
                    "missing Status header (Canonical | Reference | History | Superseded)",
                )
            )
            continue  # no class => cannot judge exemption; header fix comes first

        if in_archived and cls not in ARCHIVED_ALLOWED:
            violations.append(
                Violation(
                    str(md), None, f"archived file must be Superseded or History, not {cls.title()}"
                )
            )

        exempt = in_archived or cls == "history"
        if not exempt:
            violations.extend(check_drift(md, status))

    return violations


def main() -> int:
    ap = argparse.ArgumentParser(description="JACKPOT documentation drift guard")
    ap.add_argument("--docs-dir", default="docs", type=Path)
    ap.add_argument("--status-file", default=Path("docs/STATUS.md"), type=Path)
    args = ap.parse_args()

    if not args.docs_dir.is_dir():
        print(f"error: docs dir not found: {args.docs_dir}", file=sys.stderr)
        return 2

    violations = run(args.docs_dir, args.status_file)

    if violations:
        print(f"Documentation guard: {len(violations)} violation(s)\n")
        for v in violations:
            print(v)
        print("\nFix the headers, reference the STATUS block for tracked numbers, or")
        print(f"suppress a legitimate line with a trailing `{SUPPRESS_MARKER}` marker.")
        return 1

    print("Documentation guard: clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
