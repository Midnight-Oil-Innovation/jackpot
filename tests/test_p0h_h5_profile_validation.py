"""Phase P0h H-5 — execution-profile work_dir validation predicate.

Tests the local-filesystem half of the H-5 check: stat the path,
verify it's a directory, probe writability via mkstemp. The cluster-
side check (sinfo + srun) is exercised separately in cli/tests for
``jackpot doctor slurm``.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from backend.pipeline_config.profile_validation import (
    ValidationFinding,
    has_blocking_findings,
    validate_work_dir_locally,
)


def _codes(findings: list[ValidationFinding]) -> list[str]:
    return [f.code for f in findings]


def test_validate_clean_directory_returns_empty(tmp_path: Path):
    findings = validate_work_dir_locally(str(tmp_path))
    assert findings == []
    assert not has_blocking_findings(findings)


def test_validate_missing_path_returns_missing_error(tmp_path: Path):
    missing = tmp_path / "nonexistent"
    findings = validate_work_dir_locally(str(missing))
    assert _codes(findings) == ["MISSING"]
    assert findings[0].severity == "error"
    assert has_blocking_findings(findings)


def test_validate_file_not_directory_returns_not_a_directory(tmp_path: Path):
    fpath = tmp_path / "not_a_dir.txt"
    fpath.write_text("hello", encoding="utf-8")
    findings = validate_work_dir_locally(str(fpath))
    assert _codes(findings) == ["NOT_A_DIRECTORY"]
    assert has_blocking_findings(findings)


def test_validate_readonly_directory_warns(tmp_path: Path):
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(stat.S_IRUSR | stat.S_IXUSR)  # 0o500: read+exec, no write
    try:
        findings = validate_work_dir_locally(str(ro))
        assert _codes(findings) == ["NOT_WRITABLE"]
        assert findings[0].severity == "warning"
        # warnings alone are not blocking — has_blocking_findings is False.
        assert not has_blocking_findings(findings)
    finally:
        # Restore mode so pytest's tmp_path cleanup can rmtree.
        ro.chmod(0o700)


def test_validate_empty_string_returns_empty_error():
    findings = validate_work_dir_locally("")
    assert _codes(findings) == ["EMPTY"]
    assert has_blocking_findings(findings)


def test_validate_whitespace_only_returns_empty_error():
    findings = validate_work_dir_locally("   \t\n  ")
    assert _codes(findings) == ["EMPTY"]


def test_validate_file_scheme_strips_prefix(tmp_path: Path):
    findings = validate_work_dir_locally(f"file://{tmp_path}")
    assert findings == []


def test_validate_gs_uri_short_circuits_to_info():
    findings = validate_work_dir_locally("gs://jackpot-work/runs")
    assert _codes(findings) == ["REMOTE_SCHEME"]
    assert findings[0].severity == "info"
    assert not has_blocking_findings(findings)


def test_validate_s3_uri_short_circuits_to_info():
    findings = validate_work_dir_locally("s3://jackpot-work/runs")
    assert _codes(findings) == ["REMOTE_SCHEME"]


def test_validate_az_uri_short_circuits_to_info():
    findings = validate_work_dir_locally("az://jackpot-work/runs")
    assert _codes(findings) == ["REMOTE_SCHEME"]


def test_validate_tilde_expanded(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    sub = tmp_path / "work"
    sub.mkdir()
    findings = validate_work_dir_locally("~/work")
    assert findings == []


def test_validate_writability_failure_carries_os_error_message(tmp_path: Path):
    """The NOT_WRITABLE finding should include the underlying exception
    class name so an operator reading the message can tell whether
    they're hitting a permission denial vs. a quota issue vs. a
    read-only filesystem."""
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)
    try:
        findings = validate_work_dir_locally(str(ro))
        assert findings, "expected NOT_WRITABLE finding"
        msg = findings[0].message
        assert "PermissionError" in msg or "OSError" in msg
    finally:
        ro.chmod(0o700)


def test_has_blocking_findings_true_for_any_error():
    findings = [
        ValidationFinding("warning", "X", "x"),
        ValidationFinding("info", "Y", "y"),
        ValidationFinding("error", "Z", "z"),
    ]
    assert has_blocking_findings(findings)


def test_has_blocking_findings_false_for_warning_only():
    findings = [
        ValidationFinding("warning", "X", "x"),
        ValidationFinding("info", "Y", "y"),
    ]
    assert not has_blocking_findings(findings)


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses chmod 0o500")
def test_readonly_check_skipped_for_root():
    """Sentinel — the readonly-directory test relies on chmod
    enforcement, which root bypasses on POSIX. CI runs as non-root;
    this test exists so the suite explicitly documents the
    assumption."""
    pass
