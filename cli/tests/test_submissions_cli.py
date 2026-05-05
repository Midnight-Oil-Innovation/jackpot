# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""I-3c: ``jackpot submissions`` CLI command tests.

CLI commands are thin shells over :class:`SubmissionsModule`. We mock
the module's HTTP client (``JACKPOTClient``) so the assertions land on
the URL/method/body the SDK chose, plus the operator-facing output that
the CLI prints.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from jackpot.cli.main import cli
from jackpot.core.exceptions import ConflictError, JACKPOTError, NotFoundError


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _stub_credentials(monkeypatch):
    """Bypass the ConfigError raised when ~/.jackpot/config.toml is absent."""
    from jackpot.cli import submissions as submissions_mod

    monkeypatch.setattr(
        submissions_mod, "get_client_credentials", lambda: ("http://test", "tok")
    )


def _patched_client():
    """Return a context manager that swaps the SDK's HTTP client."""
    fake = MagicMock()
    return patch("jackpot.cli.submissions.JACKPOTClient", return_value=fake), fake


# ── Help / group surface ─────────────────────────────────────────────


def test_submissions_help_lists_all_commands(runner):
    result = runner.invoke(cli, ["submissions", "--help"])
    assert result.exit_code == 0
    for cmd in (
        "create",
        "list",
        "show",
        "update",
        "delete",
        "add-samples",
        "remove-samples",
        "validate",
        "generate",
        "mark-submitted",
        "register-accessions",
        "mark-rejected",
        "withdraw",
        "execute",
        "retry-execution",
        "execution-logs",
    ):
        assert cmd in result.output, f"missing {cmd!r} in submissions --help"


# ── create ───────────────────────────────────────────────────────────


def test_create_calls_post(runner, monkeypatch):
    _stub_credentials(monkeypatch)
    cm, fake = _patched_client()
    fake.post.return_value = {
        "id": 42,
        "title": "TEST",
        "status": "DRAFT",
        "target_repository": "NCBI",
    }
    with cm:
        result = runner.invoke(
            cli,
            [
                "submissions",
                "create",
                "--title",
                "TEST",
                "--target-repo",
                "ncbi",
                "--lab-id",
                "1",
                "--samples",
                "1,2,3",
            ],
        )
    assert result.exit_code == 0, result.output
    fake.post.assert_called_once()
    args, kwargs = fake.post.call_args
    assert args[0] == "/api/v1/submissions/"
    assert kwargs["json"]["target_repository"] == "NCBI"
    assert kwargs["json"]["sample_ids"] == [1, 2, 3]
    assert "Created submission 42" in result.output


def test_create_rejects_invalid_sample_id(runner, monkeypatch):
    _stub_credentials(monkeypatch)
    cm, _ = _patched_client()
    with cm:
        result = runner.invoke(
            cli,
            [
                "submissions",
                "create",
                "--title",
                "X",
                "--target-repo",
                "ncbi",
                "--lab-id",
                "1",
                "--samples",
                "not-an-int",
            ],
        )
    assert result.exit_code != 0
    assert "Invalid sample ID" in result.output


# ── list ─────────────────────────────────────────────────────────────


def test_list_renders_table(runner, monkeypatch):
    _stub_credentials(monkeypatch)
    cm, fake = _patched_client()
    fake.get.return_value = [
        {
            "id": 1,
            "title": "X",
            "target_repository": "NCBI",
            "status": "DRAFT",
            "sample_count": 2,
            "created_at": "2026-05-01T00:00:00Z",
        }
    ]
    with cm:
        result = runner.invoke(cli, ["submissions", "list", "--lab-id", "1"])
    assert result.exit_code == 0, result.output
    assert "X" in result.output
    assert "NCBI" in result.output


def test_list_json_output(runner, monkeypatch):
    _stub_credentials(monkeypatch)
    cm, fake = _patched_client()
    fake.get.return_value = [{"id": 1, "title": "X"}]
    with cm:
        result = runner.invoke(cli, ["submissions", "list", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed == [{"id": 1, "title": "X"}]


# ── show ─────────────────────────────────────────────────────────────


def test_show_pretty(runner, monkeypatch):
    _stub_credentials(monkeypatch)
    cm, fake = _patched_client()
    fake.get.return_value = {
        "id": 42,
        "title": "T",
        "target_repository": "NCBI",
        "status": "READY_TO_SUBMIT",
        "execution_attempt_count": 0,
    }
    with cm:
        result = runner.invoke(cli, ["submissions", "show", "42"])
    assert result.exit_code == 0
    assert "READY_TO_SUBMIT" in result.output
    assert "42" in result.output


# ── execute / retry-execution ────────────────────────────────────────


def test_execute_happy_path(runner, monkeypatch):
    _stub_credentials(monkeypatch)
    cm, fake = _patched_client()
    fake.post.return_value = {
        "id": 42,
        "status": "EXECUTING",
        "execution_attempt_count": 1,
    }
    with cm:
        result = runner.invoke(cli, ["submissions", "execute", "42"])
    assert result.exit_code == 0, result.output
    fake.post.assert_called_once_with("/api/v1/submissions/42/execute")
    assert "queued for backend execution" in result.output
    assert "EXECUTING" in result.output


def test_execute_handles_backend_disabled(runner, monkeypatch):
    """The 409 BACKEND_EXECUTION_DISABLED comes back as ConflictError;
    the CLI surfaces the operator-facing message and exits non-zero."""
    _stub_credentials(monkeypatch)
    cm, fake = _patched_client()
    fake.post.side_effect = ConflictError(
        "Backend execution is disabled in this deployment. ...",
        status_code=409,
    )
    with cm:
        result = runner.invoke(cli, ["submissions", "execute", "42"])
    assert result.exit_code != 0
    assert "Execute submission failed" in result.output
    assert "disabled" in result.output


def test_execute_handles_missing_credentials(runner, monkeypatch):
    """400 MISSING_CREDENTIALS comes back as JACKPOTError."""
    _stub_credentials(monkeypatch)
    cm, fake = _patched_client()
    fake.post.side_effect = JACKPOTError(
        "Backend execution requires credentials for repo 'ncbi'. "
        "Missing: ncbi_submission_password.",
        status_code=400,
    )
    with cm:
        result = runner.invoke(cli, ["submissions", "execute", "42"])
    assert result.exit_code != 0
    assert "Missing" in result.output


def test_retry_execution_happy_path(runner, monkeypatch):
    _stub_credentials(monkeypatch)
    cm, fake = _patched_client()
    fake.post.return_value = {
        "id": 42,
        "status": "EXECUTING",
        "execution_attempt_count": 2,
    }
    with cm:
        result = runner.invoke(cli, ["submissions", "retry-execution", "42"])
    assert result.exit_code == 0, result.output
    fake.post.assert_called_once_with("/api/v1/submissions/42/retry-execution")
    assert "re-queued" in result.output


# ── execution-logs ───────────────────────────────────────────────────


def test_execution_logs_empty(runner, monkeypatch):
    _stub_credentials(monkeypatch)
    cm, fake = _patched_client()
    fake.get.return_value = {"submission_id": 42, "entries": []}
    with cm:
        result = runner.invoke(cli, ["submissions", "execution-logs", "42"])
    assert result.exit_code == 0
    assert "No execution attempts yet" in result.output


def test_execution_logs_pretty(runner, monkeypatch):
    _stub_credentials(monkeypatch)
    cm, fake = _patched_client()
    fake.get.return_value = {
        "submission_id": 42,
        "entries": [
            {
                "attempt": 1,
                "log_uri": "s3://x/a.log",
                "log_view_url": "https://signed/a.log",
                "exit_status": "failed",
            },
            {
                "attempt": 2,
                "log_uri": "s3://x/b.log",
                "log_view_url": "https://signed/b.log",
                "exit_status": "completed",
            },
        ],
    }
    with cm:
        result = runner.invoke(cli, ["submissions", "execution-logs", "42"])
    assert result.exit_code == 0
    assert "Attempt 1" in result.output
    assert "Attempt 2" in result.output
    assert "https://signed/a.log" in result.output


def test_execution_logs_json_output(runner, monkeypatch):
    _stub_credentials(monkeypatch)
    cm, fake = _patched_client()
    fake.get.return_value = {
        "submission_id": 42,
        "entries": [{"attempt": 1, "log_uri": "x"}],
    }
    with cm:
        result = runner.invoke(
            cli, ["submissions", "execution-logs", "42", "--json"]
        )
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed == [{"attempt": 1, "log_uri": "x"}]


# ── delete with --yes confirmation ──────────────────────────────────


def test_delete_with_yes(runner, monkeypatch):
    _stub_credentials(monkeypatch)
    cm, fake = _patched_client()
    fake.delete.return_value = {}
    with cm:
        result = runner.invoke(cli, ["submissions", "delete", "42", "--yes"])
    assert result.exit_code == 0
    fake.delete.assert_called_once_with("/api/v1/submissions/42")


def test_delete_without_yes_aborts_on_no(runner, monkeypatch):
    _stub_credentials(monkeypatch)
    cm, fake = _patched_client()
    with cm:
        result = runner.invoke(cli, ["submissions", "delete", "42"], input="n\n")
    assert result.exit_code == 0
    assert "Aborted" in result.output
    fake.delete.assert_not_called()


# ── 404 NotFoundError handling ──────────────────────────────────────


def test_show_handles_not_found(runner, monkeypatch):
    _stub_credentials(monkeypatch)
    cm, fake = _patched_client()
    fake.get.side_effect = NotFoundError("Not found", status_code=404)
    with cm:
        result = runner.invoke(cli, ["submissions", "show", "9999999"])
    assert result.exit_code != 0
    assert "submission not found" in result.output
