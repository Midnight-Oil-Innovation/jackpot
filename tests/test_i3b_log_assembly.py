"""I-3b: execution log assembly + invocation-command redaction."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from backend.submission_executors.seqsender import (
    build_execution_log,
    redact_command_for_logging,
)

CONFIG_PATH = Path("/tmp/seqsender_config_42_abc.yaml")


def test_redact_command_replaces_config_path():
    cmd = [
        "/opt/seqsender/seqsender-kickoff",
        "submit",
        "--submission_dir",
        "/var/jackpot/submissions/sub_42",
        "--config_file",
        str(CONFIG_PATH),
        "--biosample",
    ]
    out = redact_command_for_logging(cmd, CONFIG_PATH)
    assert out[0] == "/opt/seqsender/seqsender-kickoff"
    assert out[1] == "submit"
    assert out[3] == "/var/jackpot/submissions/sub_42"
    # The config path is replaced; the surrounding --config_file flag is preserved.
    assert "--config_file" in out
    assert str(CONFIG_PATH) not in out
    assert "<credential-config-redacted>" in out


def test_redact_command_passes_through_when_path_absent():
    cmd = ["seqsender", "submit", "--biosample"]
    assert redact_command_for_logging(cmd, CONFIG_PATH) == cmd


def _make_log(**overrides) -> bytes:
    base = {
        "submission_id": 42,
        "attempt": 1,
        "target_repo": "NCBI",
        "executor_backend": "seqsender_subprocess",
        "invocation_command": [
            "/opt/seqsender/seqsender-kickoff",
            "submit",
            "--config_file",
            str(CONFIG_PATH),
        ],
        "working_dir": Path("/tmp/jackpot-executions/submission_42_attempt_1"),
        "config_path": CONFIG_PATH,
        "queued_at": datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC),
        "started_at": datetime(2026, 5, 4, 12, 0, 1, tzinfo=UTC),
        "completed_at": datetime(2026, 5, 4, 12, 0, 5, tzinfo=UTC),
        "exit_code": 0,
        "timed_out": False,
        "wall_time_seconds": 4.12,
        "stdout_redacted": "Connecting to NCBI FTP\nUploaded 12 samples",
        "stderr_redacted": "",
    }
    base.update(overrides)
    return build_execution_log(**base)


def test_log_includes_header_fields():
    log = _make_log().decode("utf-8")
    for needle in (
        "Submission ID:      42",
        "Attempt:            1",
        "Target repository:  NCBI",
        "Executor backend:   seqsender_subprocess",
        "Working directory:",
        "Queued at:",
        "Started at:",
        "Completed at:",
    ):
        assert needle in log, f"missing header field: {needle!r}"


def test_log_invocation_redacts_config_path():
    """The Invocation line in the header must not echo the config path
    (lest a copy-paste of the invocation become a reproduction of the
    credential exposure). The 'Config file:' line lower in the header
    intentionally shows the path for diagnostic context — the path
    itself is not sensitive, only its content was."""
    log = _make_log().decode("utf-8")
    invocation_line = next(line for line in log.splitlines() if line.startswith("Invocation:"))
    assert str(CONFIG_PATH) not in invocation_line
    assert "<credential-config-redacted>" in invocation_line


def test_log_includes_stdout_and_stderr_sections():
    log = _make_log(
        stdout_redacted="STDOUT-CONTENT",
        stderr_redacted="STDERR-CONTENT",
    ).decode("utf-8")
    assert "═══ stdout ═══" in log
    assert "STDOUT-CONTENT" in log
    assert "═══ stderr ═══" in log
    assert "STDERR-CONTENT" in log


def test_log_footer_has_outcome_fields():
    log = _make_log(exit_code=1, timed_out=False, wall_time_seconds=12.34).decode("utf-8")
    assert "Exit code:          1" in log
    assert "Timed out:          False" in log
    assert "Wall time (s):      12.34" in log


def test_log_handles_unknown_queued_at():
    """If the lifecycle didn't capture queued_at (legacy row), the log
    must still render — show '(unknown)' rather than crashing."""
    log = _make_log(queued_at=None).decode("utf-8")
    assert "Queued at:          (unknown)" in log


def test_log_returned_as_utf8_bytes():
    out = _make_log()
    assert isinstance(out, bytes)
    # Round-trip without raising — UTF-8 valid.
    out.decode("utf-8")


def test_log_handles_unicode_in_stdout():
    log = _make_log(stdout_redacted="zażółć gęślą").decode("utf-8")
    assert "zażółć" in log
