"""Checks for scripts/check_backlog.py.

`active_backlog.yaml` decides what gets worked on next, so a stale status there
hides work rather than merely looking untidy. On 2026-08-28 one unflipped entry
(`P0b`, still `tracked_not_scheduled` seven weeks after merging) held `P0c`
blocked, which held `B-CARE-3` and `B-CARE-3i` blocked.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_backlog.py"
_spec = importlib.util.spec_from_file_location("check_backlog", _SCRIPT)
assert _spec and _spec.loader
check_backlog = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = check_backlog
_spec.loader.exec_module(check_backlog)


def entry(eid: str, status: str, **kw) -> dict:
    base = {"id": eid, "title": f"title for {eid}", "status": status, "phase": "test_phase"}
    base.update(kw)
    return base


def messages(entries: list[dict]) -> str:
    return "\n".join(str(v) for v in check_backlog.check(entries))


# ── the real backlog stays clean ───────────────────────────────────────────


def test_the_live_backlog_passes():
    path = Path(__file__).resolve().parent.parent / "active_backlog.yaml"
    entries = check_backlog.load_entries(path)
    assert len(entries) > 50, "parsed too few entries — did the file shape change?"
    assert check_backlog.check(entries) == []


# ── 1. schema ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("field", ["id", "title", "status", "phase"])
def test_missing_required_field_is_reported(field):
    e = entry("A-1", "open")
    del e[field]
    assert f"missing required field {field!r}" in messages([e])


def test_unknown_status_is_reported():
    assert "unknown status" in messages([entry("A-1", "in_progress")])


def test_duplicate_id_is_reported():
    assert "duplicate id" in messages([entry("A-1", "open"), entry("A-1", "shipped")])


# ── 2. graph ───────────────────────────────────────────────────────────────


def test_dangling_dependency_is_reported():
    out = messages([entry("A-1", "blocked", depends_on=["NOPE"])])
    assert "depends_on names unknown entry 'NOPE'" in out


def test_dependency_cycle_is_reported():
    out = messages(
        [
            entry("A-1", "blocked", depends_on=["A-2"]),
            entry("A-2", "blocked", depends_on=["A-1"]),
        ]
    )
    assert "dependency cycle" in out


def test_long_dependency_chain_is_not_a_cycle():
    out = messages(
        [
            entry("A-1", "shipped"),
            entry("A-2", "blocked", depends_on=["A-1"]),
            entry("A-3", "blocked", depends_on=["A-2"]),
            entry("A-4", "blocked", depends_on=["A-3"]),
        ]
    )
    assert "dependency cycle" not in out


# ── 3. the P0c failure ─────────────────────────────────────────────────────


def test_blocked_with_all_dependencies_shipped_is_reported():
    """The 2026-08-28 failure, once P0b was correctly marked shipped."""
    out = messages([entry("P0b", "shipped"), entry("P0c", "blocked", depends_on=["P0b"])])
    assert "every dependency has shipped" in out
    assert "P0c" in out


def test_blocked_with_one_unmet_dependency_is_fine():
    out = messages(
        [
            entry("A-1", "shipped"),
            entry("A-2", "open"),
            entry("A-3", "blocked", depends_on=["A-1", "A-2"]),
        ]
    )
    assert out == ""


# ── 4. the B-EUK-3 / B-BYOP-9 failure ──────────────────────────────────────


def test_external_blocker_naming_a_shipped_entry_is_reported():
    out = messages(
        [
            entry("P0b", "shipped"),
            entry(
                "B-EUK-3",
                "blocked_external",
                blocked_by_external="P0b (schema v5.0 migration window)",
            ),
        ]
    )
    assert "which has shipped" in out and "B-EUK-3" in out


def test_external_blocker_naming_an_unshipped_entry_is_fine():
    out = messages(
        [
            entry("P0c", "open"),
            entry("B-CARE-3", "blocked_external", blocked_by_external="P0c (multi-tenancy)"),
        ]
    )
    assert out == ""


def test_substring_of_a_shipped_id_does_not_false_positive():
    """'P0b' must not match inside 'P0b-followup'."""
    out = messages(
        [
            entry("P0b", "shipped"),
            entry("X-1", "blocked_external", blocked_by_external="waiting on P0b-followup work"),
        ]
    )
    assert out == ""


# ── 5. blocked by assertion only ───────────────────────────────────────────


def test_blocked_with_no_reason_is_reported():
    out = messages([entry("A-1", "blocked")])
    assert "no depends_on and no blocked_by_external" in out


def test_blocker_text_that_disclaims_itself_still_counts_as_no_reason():
    out = messages([entry("A-1", "blocked", blocked_by_external="none - re-scope later")])
    assert "no depends_on and no blocked_by_external" in out


# ── 6. the advisory pass, and the limitation it exists for ─────────────────


def test_internal_checks_cannot_catch_a_file_that_disagrees_with_reality():
    """Documents the gap that motivated the advisory pass.

    Before the 2026-08-28 reconciliation, P0c was `blocked` on P0b and P0b was
    `tracked_not_scheduled`. That graph is perfectly self-consistent and
    entirely wrong — checks 1-5 report clean. Nothing inside the file can tell
    you P0b had merged seven weeks earlier.
    """
    entries = [
        entry("P0b", "tracked_not_scheduled"),
        entry("P0c", "blocked", depends_on=["P0b"]),
    ]
    assert check_backlog.check(entries) == []


def test_advisory_flags_a_non_shipped_entry_that_opens_a_commit_subject(tmp_path, monkeypatch):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.org"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "f.txt").write_text("x\n")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "P0b (Schema v5.0): sovereignty deletion, BYOP"],
        cwd=tmp_path,
        check=True,
    )

    monkeypatch.chdir(tmp_path)
    advisories = check_backlog.git_evidence_advisories([entry("P0b", "tracked_not_scheduled")])

    assert len(advisories) == 1
    assert "confirm it has not already shipped" in str(advisories[0])


def test_advisory_ignores_a_bare_mention(tmp_path, monkeypatch):
    """'P0c stub' must not be read as 'P0c shipped'."""
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.org"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "f.txt").write_text("x\n")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "feat(p0h-h3): per-launch Slurm override (P0c stub)"],
        cwd=tmp_path,
        check=True,
    )

    monkeypatch.chdir(tmp_path)
    assert check_backlog.git_evidence_advisories([entry("P0c", "blocked")]) == []


def test_advisory_is_silent_outside_a_git_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert check_backlog.git_evidence_advisories([entry("P0b", "open")], ref="no-such-ref") == []


# ── shape ──────────────────────────────────────────────────────────────────


def test_entries_are_parsed_from_every_top_level_list(tmp_path):
    path = tmp_path / "b.yaml"
    path.write_text(
        yaml.safe_dump({"meta": {"version": 1}, "sessions": [entry("A-1", "open")]}),
        encoding="utf-8",
    )
    parsed = check_backlog.load_entries(path)
    assert [e["id"] for e in parsed] == ["A-1"]
