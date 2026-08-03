#!/usr/bin/env python3
"""scripts/check_migration_heads.py — fail if the Alembic chain has forked.

Two migrations claiming the same down_revision is the detectable damage from two
parallel migrations landing at once. Pure text parsing: no database, no alembic
import, no environment needed, so it runs anywhere including CI.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

VERSIONS = Path("backend/db/migrations/versions")
PAT = re.compile(r"^down_revision(?:\s*:\s*[^=]+)?\s*=\s*(?:['\"]([0-9a-fA-F]+)['\"]|None)", re.M)


def main() -> int:
    if not VERSIONS.is_dir():
        print(f"note: {VERSIONS} not found; skipping")
        return 0
    downs: list[tuple[str, str]] = []
    for f in sorted(VERSIONS.glob("*.py")):
        m = PAT.search(f.read_text(encoding="utf-8", errors="replace"))
        if m:
            downs.append((m.group(1) or "ROOT", f.name))
    counts = Counter(d for d, _ in downs)
    forks = {
        d: [n for dd, n in downs if dd == d] for d, c in counts.items() if c > 1 and d != "ROOT"
    }
    roots = [n for d, n in downs if d == "ROOT"]
    if forks:
        print("FAIL: forked Alembic chain (parallel migrations landed):")
        for d, files in forks.items():
            print(f"  down_revision={d} claimed by: {', '.join(files)}")
        print("Fix: rebase one migration onto the other's revision, then re-run.")
        return 1
    if len(roots) > 1:
        print(f"FAIL: {len(roots)} root migrations: {', '.join(roots)}")
        return 1
    print(f"OK: single linear chain ({len(downs)} migrations).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
