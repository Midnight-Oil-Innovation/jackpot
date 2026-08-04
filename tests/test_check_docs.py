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
