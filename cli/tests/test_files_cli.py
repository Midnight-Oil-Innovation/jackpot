# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Tests for ``jackpot files`` CLI commands (Phase P0f F-9)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from jackpot.cli.main import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _stub_credentials(monkeypatch):
    """Bypass the ConfigError raised when ~/.jackpot/config.toml is absent."""
    from jackpot.cli import files as files_mod

    monkeypatch.setattr(files_mod, "get_client_credentials", lambda: ("http://test", "tok"))


# ── Help ────────────────────────────────────────────────────────────────


class TestFilesHelp:
    def test_files_help(self, runner):
        result = runner.invoke(cli, ["files", "--help"])
        assert result.exit_code == 0
        assert "promote" in result.output
        assert "verify" in result.output

    def test_promote_help(self, runner):
        result = runner.invoke(cli, ["files", "promote", "--help"])
        assert result.exit_code == 0
        assert "--file-id" in result.output
        assert "--sample" in result.output
        assert "--to" in result.output
        assert "--wait" in result.output


# ── promote ──────────────────────────────────────────────────────────────


class TestFilesPromote:
    def test_promote_with_file_id_no_wait(self, runner, monkeypatch):
        _stub_credentials(monkeypatch)
        fake_client = MagicMock()
        fake_client.post.return_value = {
            "file_id": 9001,
            "current_state": "EXTERNAL",
            "target_state": "MANAGED",
            "job_id": "promote_9001_2026",
            "estimated_seconds": 5,
            "status": "QUEUED",
        }
        with patch("jackpot.cli.files.JACKPOTClient", return_value=fake_client):
            result = runner.invoke(
                cli, ["files", "promote", "--file-id", "9001", "--to", "managed"]
            )
        assert result.exit_code == 0, result.output
        fake_client.post.assert_called_once_with(
            "/api/v1/files/9001/promote",
            json={"to": "MANAGED", "retention_policy": "STANDARD"},
        )
        assert "promote_9001_2026" in result.output
        assert "EXTERNAL" in result.output
        assert "MANAGED" in result.output

    def test_promote_requires_locator(self, runner, monkeypatch):
        _stub_credentials(monkeypatch)
        result = runner.invoke(cli, ["files", "promote", "--to", "managed"])
        assert result.exit_code != 0
        assert "Specify either --file-id or both --sample and --role" in result.output

    def test_promote_rejects_both_locator_forms(self, runner, monkeypatch):
        _stub_credentials(monkeypatch)
        result = runner.invoke(
            cli,
            [
                "files",
                "promote",
                "--file-id",
                "1",
                "--sample",
                "EX-2026-001",
                "--role",
                "R1",
                "--to",
                "managed",
            ],
        )
        assert result.exit_code != 0
        assert "OR --sample/--role" in result.output

    def test_promote_with_sample_role_resolves_via_lookup(self, runner, monkeypatch):
        _stub_credentials(monkeypatch)
        fake_client = MagicMock()

        def fake_get(path, params=None):
            if path == "/api/v1/samples/EX-2026-001":
                return {"id": 42, "sample_id": "EX-2026-001"}
            if path == "/api/v1/files/":
                return {
                    "data": [
                        {"id": 9001, "read_direction": "R1", "file_type": "fastq"},
                        {"id": 9002, "read_direction": "R2", "file_type": "fastq"},
                    ]
                }
            raise AssertionError(f"unexpected GET {path}")

        fake_client.get.side_effect = fake_get
        fake_client.post.return_value = {
            "file_id": 9001,
            "current_state": "EXTERNAL",
            "target_state": "MIRRORED",
            "job_id": "j",
            "estimated_seconds": 1,
        }
        with patch("jackpot.cli.files.JACKPOTClient", return_value=fake_client):
            result = runner.invoke(
                cli,
                [
                    "files",
                    "promote",
                    "--sample",
                    "EX-2026-001",
                    "--role",
                    "R1",
                    "--to",
                    "mirrored",
                ],
            )
        assert result.exit_code == 0, result.output
        # POSTed against the resolved id (R1 → file 9001)
        fake_client.post.assert_called_once_with(
            "/api/v1/files/9001/promote",
            json={"to": "MIRRORED", "retention_policy": "STANDARD"},
        )

    def test_promote_wait_polls_until_completed(self, runner, monkeypatch):
        _stub_credentials(monkeypatch)
        # Avoid wall-clock waits between polls.
        monkeypatch.setattr("jackpot.cli.files.time.sleep", lambda _s: None)

        fake_client = MagicMock()
        fake_client.post.return_value = {
            "file_id": 9001,
            "current_state": "EXTERNAL",
            "target_state": "MANAGED",
            "job_id": "promote_9001_xyz",
            "estimated_seconds": 1,
        }
        # First poll → RUNNING, second → COMPLETED
        fake_client.get.side_effect = [
            {"job_id": "promote_9001_xyz", "status": "RUNNING"},
            {
                "job_id": "promote_9001_xyz",
                "status": "COMPLETED",
                "outcome": "SUCCESS",
                "copied_bytes": 2048,
                "elapsed_seconds": 0.9,
            },
        ]
        with patch("jackpot.cli.files.JACKPOTClient", return_value=fake_client):
            result = runner.invoke(
                cli,
                [
                    "files",
                    "promote",
                    "--file-id",
                    "9001",
                    "--to",
                    "managed",
                    "--wait",
                    "--timeout",
                    "5",
                ],
            )
        assert result.exit_code == 0, result.output
        assert fake_client.get.call_count == 2
        assert "Promote complete" in result.output
        assert "2048 bytes" in result.output


# ── verify ──────────────────────────────────────────────────────────────


class TestFilesVerify:
    def test_verify_single_file(self, runner, monkeypatch):
        _stub_credentials(monkeypatch)
        fake_client = MagicMock()
        fake_client.post.return_value = {
            "file_id": 9001,
            "uri": "file:///srv/r1.fastq.gz",
            "storage_state": "EXTERNAL",
            "last_verification_status": "OK",
            "last_verified_at": "2026-05-03T12:00:00Z",
        }
        with patch("jackpot.cli.files.JACKPOTClient", return_value=fake_client):
            result = runner.invoke(cli, ["files", "verify", "--file-id", "9001"])
        assert result.exit_code == 0, result.output
        fake_client.post.assert_called_once_with("/api/v1/files/9001/verify")
        assert "9001" in result.output

    def test_verify_sample_iterates_files(self, runner, monkeypatch):
        _stub_credentials(monkeypatch)
        fake_client = MagicMock()

        def fake_get(path, params=None):
            if path == "/api/v1/samples/EX-2026-001":
                return {"id": 42}
            if path == "/api/v1/files/":
                return {"data": [{"id": 1}, {"id": 2}, {"id": 3}]}
            raise AssertionError(path)

        fake_client.get.side_effect = fake_get
        fake_client.post.return_value = {
            "file_id": 1,
            "uri": "u",
            "storage_state": "EXTERNAL",
            "last_verification_status": "OK",
            "last_verified_at": "now",
        }
        with patch("jackpot.cli.files.JACKPOTClient", return_value=fake_client):
            result = runner.invoke(cli, ["files", "verify", "--sample", "EX-2026-001"])
        assert result.exit_code == 0, result.output
        assert fake_client.post.call_count == 3

    def test_verify_requires_locator(self, runner, monkeypatch):
        _stub_credentials(monkeypatch)
        result = runner.invoke(cli, ["files", "verify"])
        assert result.exit_code != 0
        assert "Specify --file-id or --sample" in result.output


# ── list ────────────────────────────────────────────────────────────────


class TestFilesList:
    def test_list_with_filter_passes_params(self, runner, monkeypatch):
        _stub_credentials(monkeypatch)
        fake_client = MagicMock()
        fake_client.get.return_value = {
            "data": [
                {
                    "id": 1,
                    "filename": "a.fastq",
                    "file_size_bytes": 1024,
                    "storage_state": "EXTERNAL",
                    "last_verified_at": "2026-05-03T00:00:00Z",
                    "sample_id": "EX-2026-001",
                }
            ]
        }
        with patch("jackpot.cli.files.JACKPOTClient", return_value=fake_client):
            result = runner.invoke(
                cli,
                [
                    "files",
                    "list",
                    "--storage-state",
                    "EXTERNAL",
                    "--project",
                    "12",
                ],
            )
        assert result.exit_code == 0, result.output
        params = fake_client.get.call_args.kwargs.get("params") or {}
        assert params.get("storage_state") == "EXTERNAL"
        assert params.get("project_id") == 12
        assert "a.fastq" in result.output

    def test_list_empty_renders_no_files(self, runner, monkeypatch):
        _stub_credentials(monkeypatch)
        fake_client = MagicMock()
        fake_client.get.return_value = {"data": []}
        with patch("jackpot.cli.files.JACKPOTClient", return_value=fake_client):
            result = runner.invoke(cli, ["files", "list"])
        assert result.exit_code == 0, result.output
        assert "No files" in result.output


# ── get ─────────────────────────────────────────────────────────────────


class TestFilesGet:
    def test_get_renders_summary(self, runner, monkeypatch):
        _stub_credentials(monkeypatch)
        fake_client = MagicMock()
        fake_client.get.return_value = {
            "id": 9001,
            "filename": "r1.fastq.gz",
            "uri": "gs://lab/r1.fastq.gz",
            "alternate_uris": ["file:///srv/r1.fastq.gz"],
            "storage_state": "EXTERNAL",
            "samples": [{"sample_id": "EX-2026-001", "project_id": 12, "lab_id": 3}],
        }
        with patch("jackpot.cli.files.JACKPOTClient", return_value=fake_client):
            result = runner.invoke(cli, ["files", "get", "--file-id", "9001"])
        assert result.exit_code == 0, result.output
        assert "9001" in result.output
        assert "r1.fastq.gz" in result.output
        assert "EX-2026-001" in result.output

    def test_get_json_output(self, runner, monkeypatch):
        _stub_credentials(monkeypatch)
        fake_client = MagicMock()
        fake_client.get.return_value = {"id": 9001, "filename": "r1.fastq.gz"}
        with patch("jackpot.cli.files.JACKPOTClient", return_value=fake_client):
            result = runner.invoke(cli, ["files", "get", "--file-id", "9001", "--json"])
        assert result.exit_code == 0
        body = json.loads(result.output)
        assert body["id"] == 9001
