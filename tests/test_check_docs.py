"""Regression checks for scripts/check_docs.py target selection.

The full-scan path used `docs_dir.rglob("*.md")`, a filesystem walk, so any
untracked or gitignored markdown sitting in docs/ (the 2 MB docs/docs.md bundle
some clones carry) produced a phantom "missing Status header" violation that
differed per developer. These tests fail if the walk comes back.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_docs.py"
_spec = importlib.util.spec_from_file_location("check_docs", _SCRIPT)
assert _spec and _spec.loader
check_docs = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = check_docs
_spec.loader.exec_module(check_docs)


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.org"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def test_untracked_and_ignored_markdown_is_skipped(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "tracked.md").write_text("> **Status:** Reference — x\n")
    (docs / "untracked.md").write_text("no header\n")
    (docs / "bundle.md").write_text("no header\n")
    (tmp_path / ".gitignore").write_text("docs/bundle.md\n")
    subprocess.run(["git", "add", "docs/tracked.md", ".gitignore"], cwd=tmp_path, check=True)

    monkeypatch.chdir(tmp_path)
    found = {p.name for p in check_docs.tracked_markdown(Path("docs"))}

    assert found == {"tracked.md"}


def test_falls_back_to_walk_outside_a_git_repo(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("x\n")
    (docs / "b.md").write_text("x\n")

    monkeypatch.chdir(tmp_path)
    # git ls-files exits non-zero outside a work tree; the guard must still run.
    found = {p.name for p in check_docs.tracked_markdown(Path("docs"))}

    assert found == {"a.md", "b.md"}


def test_root_level_markdown_is_in_scope(tmp_path, monkeypatch):
    """Root-level docs were exempt until 2026-08-28.

    scripts/check_docs.py scanned docs/ only, so spec.md drifted four months
    with three contradictory test baselines and a section instructing agents to
    violate Critical Rule 46, and README.md carried the superseded
    seven-scenario claim the denylist exists to catch. Neither was visible to
    the guard. This fails if root markdown falls out of scope again.
    """
    _init_repo(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "tracked.md").write_text("> **Status:** Reference — x\n")
    (tmp_path / "README.md").write_text("> **Status:** Canonical — x\n")
    (tmp_path / "CLAUDE.md").write_text("> **Status:** Canonical — x\n")
    nested = tmp_path / "backend"
    nested.mkdir()
    (nested / "README.md").write_text("no header, and not our business\n")
    subprocess.run(
        ["git", "add", "docs/tracked.md", "README.md", "CLAUDE.md", "backend/README.md"],
        cwd=tmp_path,
        check=True,
    )

    monkeypatch.chdir(tmp_path)
    found = {str(p) for p in check_docs.tracked_markdown(Path("docs"))}

    assert found == {"docs/tracked.md", "README.md", "CLAUDE.md"}


def test_markdown_beside_source_stays_out_of_scope(tmp_path, monkeypatch):
    """backend/README.md documents code, not project state.

    Demanding a Status header on every markdown file in the tree would block
    commits without catching drift, so in_scope() covers docs/ plus the repo
    root and nothing else.
    """
    docs = tmp_path / "docs"
    (docs / "archived").mkdir(parents=True)
    nested = tmp_path / "backend"
    nested.mkdir()
    for rel in ("docs/a.md", "docs/archived/old.md", "root.md", "backend/inner.md"):
        (tmp_path / rel).write_text("x\n")

    monkeypatch.chdir(tmp_path)
    scoped = {
        rel
        for rel in ("docs/a.md", "docs/archived/old.md", "root.md", "backend/inner.md")
        if check_docs.in_scope(Path(rel), Path("docs"))
    }

    assert scoped == {"docs/a.md", "docs/archived/old.md", "root.md"}


def test_root_doc_is_checked_for_drift_not_silently_skipped(tmp_path, monkeypatch):
    """The pre-2026-08-28 code hit `continue` on relative_to() failure.

    A root-level doc therefore passed the guard no matter what it said. This
    asserts a denylisted claim in a root doc is actually reported.
    """
    _init_repo(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text(
        "> **Status:** Canonical — x\n\nJACKPOT supports seven install scenarios.\n"
    )
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)

    monkeypatch.chdir(tmp_path)
    violations = check_docs.run(Path("docs"), Path("docs/STATUS.md"))

    assert [v for v in violations if "README.md" in v.path and "superseded" in v.message]


# ── guarding the guard ──────────────────────────────────────────────────────
#
# Both tests below exist because a check that stops checking is silent: its
# output is identical to a pass. Same pair as tests/authz/test_condition_registry.py's
# `test_the_router_scan_actually_finds_something` / `test_the_registry_does_not_rot`,
# and added here after check_backlog.py's git-evidence check was found to have
# silently stopped matching anything at all (Critical Rule 74).


#: A STATUS that disagrees with every pinned example, so `pin` facts fire too.
#: A pin fact only produces a violation when the doc and STATUS differ, so a
#: canary run against the real STATUS would assert nothing for two of three.
_MISMATCHED_STATUS = {"python_version": "9.9", "schema_version": "v9.9"}


@pytest.mark.parametrize(
    "entry",
    (*check_docs.DENYLIST, *check_docs.TRACKED_FACTS),
    ids=lambda e: e.get("name") or e["message"][:30],
)
def test_every_pattern_still_fires_through_the_guard(entry, tmp_path):
    """Each pattern's example must trip `check_drift`, not merely match its regex.

    The seam matters, and the first version of this test got it wrong. Asserting
    ``entry["regex"].search(entry["example"])`` proves the regex object still
    works — but the guard can go silent without any regex changing. Rewiring
    ``for entry in DENYLIST`` to ``for entry in []`` left twelve such canaries
    green while the denylist stopped being consulted at all, which is exactly
    the failure Critical Rule 74 is about, committed inside the implementation
    of Rule 74. Going through ``check_drift`` covers both the pattern and the
    wiring.

    Not covered, and deliberately: a ``normalize_doc``/``normalize_status``
    pair that silently agrees would make a `pin` fact unable to fire while
    still matching. Catching that needs an agreeing-and-disagreeing example
    pair per fact, which is past the point Rule 74's own "not mutation
    testing" paragraph concedes.
    """
    doc = tmp_path / "d.md"
    doc.write_text(entry["example"] + "\n")

    assert check_docs.check_drift(doc, _MISMATCHED_STATUS), (
        f"{entry['example']!r} no longer trips the guard — the tripwire is "
        "disarmed and the repo would look clean either way"
    )


def test_the_markdown_scan_actually_finds_something():
    """The file walk, against the real repo.

    Every check in this module iterates whatever `tracked_markdown` returns.
    If that returned an empty list — a git invocation change, a moved docs
    dir — the guard would report clean over nothing.
    """
    found = check_docs.tracked_markdown(REPO_ROOT / "docs")

    assert found, "tracked_markdown found no files; the walk is broken"
    names = {p.name for p in found}
    assert "architecture.md" in names, sorted(names)[:20]
