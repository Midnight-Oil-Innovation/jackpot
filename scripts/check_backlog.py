#!/usr/bin/env python3
"""Backlog consistency guard for JACKPOT.

`active_backlog.yaml` is canonical for what to work on next, so a wrong status
there is not a bookkeeping nit — it hides work. On 2026-08-28 a single stale
entry (`P0b` still `tracked_not_scheduled` seven weeks after it merged) held
`P0c` blocked, which held `B-CARE-3` blocked, which held `B-CARE-3i` blocked:
the whole sovereignty chain pinned by one unflipped status. That was the fifth
instance of the same failure in one session.

Docs already have `check_docs.py`. This is the backlog's equivalent, and it is
the `jackpot_backlog_check.py` the file header used to promise.

Checks:

  1. Schema        Required fields present; status drawn from the vocabulary;
                   ids unique.
  2. Graph         Every `depends_on` names a real entry; no dependency cycles.
  3. Stale blocked A `blocked` entry whose dependencies have ALL shipped is on
                   the frontier and mislabelled. This is the P0c failure.
  4. Stale external `blocked_by_external` naming an entry that has since
                   shipped. This is the B-EUK-3 / B-BYOP-9 failure.
  5. Blocked on nothing
                   `blocked` with neither unmet dependencies nor an external
                   blocker — blocked by assertion only.

  6. Git evidence (ADVISORY — reported, does not fail)
                   A non-shipped entry whose id opens a merged commit subject.
                   Advisory because the signal is suggestive, not conclusive.

**What checks 1-5 cannot do.** They verify the file against itself. The
2026-08-28 failure was the file disagreeing with *reality*: `P0c` was
`blocked` on `P0b`, and `P0b` was `tracked_not_scheduled` — a graph that is
perfectly self-consistent and entirely wrong. Running checks 1-5 against the
pre-reconciliation backlog reports clean. Check 6 exists because of that gap,
and it does flag `P0b` there; it is advisory because subject-line matching
also picks up "P0c stub" and design commits, and a noisy gate is a gate people
learn to bypass.

Usage:
  python scripts/check_backlog.py [--backlog active_backlog.yaml] [--no-git]

Exit 0 when clean, 1 on any hard violation. Stdlib plus PyYAML.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

STATUS_VALUES = {
    "shipped",
    "open",
    "blocked",
    "blocked_external",
    "tracked_not_scheduled",
}

REQUIRED_FIELDS = ("id", "title", "status", "phase")

# A blocker that explicitly disclaims itself, e.g. "none - re-scope if ...".
_NO_BLOCKER = re.compile(r"^\s*(none|n/?a|-)\b", re.IGNORECASE)


class Violation:
    __slots__ = ("entry_id", "message")

    def __init__(self, entry_id: str, message: str) -> None:
        self.entry_id = entry_id
        self.message = message

    def __str__(self) -> str:
        return f"  {self.entry_id}: {self.message}"


def load_entries(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [e for v in data.values() if isinstance(v, list) for e in v if isinstance(e, dict)]


def _has_blocker_text(entry: dict) -> bool:
    text = (entry.get("blocked_by_external") or "").strip()
    return bool(text) and not _NO_BLOCKER.match(text)


def find_cycles(entries: list[dict]) -> list[list[str]]:
    """Dependency cycles, via iterative depth-first search."""
    # Entries missing an id are reported by the schema check; skip them here
    # rather than crashing, so one malformed entry doesn't hide every other
    # violation in the file.
    deps = {e["id"]: list(e.get("depends_on") or []) for e in entries if e.get("id")}
    cycles: list[list[str]] = []
    seen: set[str] = set()

    for root in deps:
        if root in seen:
            continue
        stack = [(root, [root])]
        while stack:
            node, path = stack.pop()
            for dep in deps.get(node, []):
                if dep == root and len(path) > 1:
                    cycles.append([*path, dep])
                elif dep in deps and dep not in path:
                    stack.append((dep, [*path, dep]))
            seen.add(node)
    return cycles


def check(entries: list[dict]) -> list[Violation]:
    out: list[Violation] = []

    # 1. Schema.
    seen_ids: set[str] = set()
    for i, entry in enumerate(entries):
        eid = entry.get("id") or f"<entry #{i}>"
        for field in REQUIRED_FIELDS:
            if not entry.get(field):
                out.append(Violation(eid, f"missing required field {field!r}"))
        status = entry.get("status")
        if status and status not in STATUS_VALUES:
            out.append(
                Violation(
                    eid, f"unknown status {status!r}; expected one of {sorted(STATUS_VALUES)}"
                )
            )
        if entry.get("id"):
            if entry["id"] in seen_ids:
                out.append(Violation(eid, "duplicate id"))
            seen_ids.add(entry["id"])

    ids = {e["id"] for e in entries if e.get("id")}
    shipped = {e["id"] for e in entries if e.get("status") == "shipped" and e.get("id")}

    # 2. Graph.
    for entry in entries:
        for dep in entry.get("depends_on") or []:
            if dep not in ids:
                out.append(
                    Violation(entry.get("id", "?"), f"depends_on names unknown entry {dep!r}")
                )
    for cycle in find_cycles(entries):
        out.append(Violation(cycle[0], "dependency cycle: " + " -> ".join(cycle)))

    for entry in entries:
        eid = entry.get("id", "?")
        status = entry.get("status")
        deps = entry.get("depends_on") or []
        unmet = [d for d in deps if d not in shipped]

        # 3. Blocked, but every dependency has shipped.
        if status == "blocked" and deps and not unmet:
            out.append(
                Violation(
                    eid,
                    "status is 'blocked' but every dependency has shipped "
                    f"({', '.join(deps)}) — this is on the frontier; set it to 'open'",
                )
            )

        # 4. An external blocker that names an entry which has since shipped.
        blocker = (entry.get("blocked_by_external") or "").strip()
        if blocker and status in {"blocked", "blocked_external", "tracked_not_scheduled"}:
            for shipped_id in sorted(shipped):
                if re.search(rf"(?<![\w-]){re.escape(shipped_id)}(?![\w-])", blocker):
                    out.append(
                        Violation(
                            eid,
                            f"blocked_by_external names {shipped_id!r}, which has shipped — "
                            "re-point the blocker or change the status",
                        )
                    )

        # 5. Blocked by assertion only.
        if status == "blocked" and not deps and not _has_blocker_text(entry):
            out.append(
                Violation(eid, "status is 'blocked' with no depends_on and no blocked_by_external")
            )

    return out


#: Conventional-commit prefix: type, optional (scope), optional !, colon.
#: A fact about the repo's commit convention, not about any one entry.
_CC_PREFIX = r"(?:\w+(?:\([^)]*\))?!?:\s*)?"


def _evidence_pattern(eid: str) -> re.Pattern[str]:
    """Subjects that suggest ``eid`` shipped. Anchored: use with ``.match``.

    ``(?![\\w-])`` rather than ``\b``: a word boundary sits between "P" and
    "-", so ``M2-DROP\b`` matches inside ``M2-DROP-PRE``. This repo has at
    least three such parent/child pairs — M2-DROP, B-CWB-MB-1, M2-B2 — each
    shipped weeks apart from its child. Check 4 spells the same boundary.

    Known and deliberate misses, recorded so nobody "fixes" them into false
    positives:

    * **Bundled ids.** ``feat(db): FED-D — ... + B-CWB-FED-1 ...`` fires for
      the first id only, and this history really does bundle. Matching a
      non-leading id is what re-admits "(P0c stub)" — the noise this check was
      narrowed to exclude — so the second id stays out of reach.
    * **Reverts.** ``Revert "feat(authz): M2-DROP — ..."`` does not match, and
      should not: a revert is not evidence of shipping.
    """
    eid_re = rf"{re.escape(eid)}(?![\w-])"
    return re.compile(rf"(?:{_CC_PREFIX}{eid_re}|.*\bmark {eid_re} shipped\b)", re.IGNORECASE)


def git_evidence_advisories(entries: list[dict], ref: str = "HEAD") -> list[Violation]:
    """Non-shipped entries whose id opens a merged commit subject.

    Deliberately narrow: the id must start the subject (the repo's older
    release-commit shape, e.g. "P0b (Schema v5.0): ...") or start the subject
    body after a conventional-commit prefix ("feat(authz): M2-DROP — ..."), or
    the subject must say "mark <id> shipped". A bare mention ANYWHERE matches
    things like "P0c stub" and the commit that first added the entry, which is
    noise — so the prefix is the only thing allowed to precede the id.

    The prefix clause was added 2026-09-02 after this check silently stopped
    working. It required the id to open the subject, the repo adopted
    conventional commits, and by then ZERO of the last 40 subjects started
    with a bare id — so the one check written because the file can disagree
    with reality could no longer fire. M2-DROP was the case that exposed it:
    merged as "feat(authz): M2-DROP — drop the legacy role columns", still
    marked open, and unflagged.

    Returns advisories, never hard violations — see the module docstring.
    """
    try:
        proc = subprocess.run(
            ["git", "log", "--format=%h%x1f%s", ref],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []  # no git, or no such ref: skip silently, this is advisory

    commits = [line.split("\x1f", 1) for line in proc.stdout.splitlines() if "\x1f" in line]
    out: list[Violation] = []
    for entry in entries:
        eid = entry.get("id")
        if not eid or len(eid) < 3 or entry.get("status") == "shipped":
            continue
        pattern = _evidence_pattern(eid)
        for sha, subject in commits:
            if pattern.match(subject):
                out.append(
                    Violation(
                        eid,
                        f"status is {entry.get('status')!r} but {sha} reads "
                        f"{subject[:60]!r} — confirm it has not already shipped",
                    )
                )
                break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="JACKPOT backlog consistency guard")
    ap.add_argument("--backlog", default=Path("active_backlog.yaml"), type=Path)
    ap.add_argument(
        "--no-git",
        action="store_true",
        help="skip the advisory git-evidence pass (check 6)",
    )
    ap.add_argument("paths", nargs="*", type=Path, help="ignored; lets pre-commit pass filenames")
    args = ap.parse_args()

    if not args.backlog.is_file():
        print(f"error: backlog not found: {args.backlog}", file=sys.stderr)
        return 2

    entries = load_entries(args.backlog)
    if not entries:
        print(f"error: no entries parsed from {args.backlog}", file=sys.stderr)
        return 2

    advisories = [] if args.no_git else git_evidence_advisories(entries)
    if advisories:
        print(f"Backlog guard: {len(advisories)} advisory (not failing)\n")
        for a in advisories:
            print(a)
        print()

    violations = check(entries)
    if violations:
        print(f"Backlog guard: {len(violations)} violation(s) across {len(entries)} entries\n")
        for v in violations:
            print(v)
        print("\nA status here decides what gets worked on next. Fix the status, or")
        print("re-point the blocker at what is actually outstanding.")
        return 1

    print(f"Backlog guard: clean ({len(entries)} entries).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
