"""Tests for `jackpot.init.github_vars` — gh CLI detect-and-confirm."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

from jackpot.init.github_vars import (
    fetch_environment_variables,
    fetch_repo_variables,
    probe_gh,
)


class TestProbeGh:
    def test_gh_not_on_path(self):
        with patch("jackpot.init.github_vars.shutil.which", return_value=None):
            result = probe_gh()
        assert result.available is False
        assert "not found" in result.detail

    def test_gh_present_but_unauthed(self):
        with (
            patch(
                "jackpot.init.github_vars.shutil.which",
                return_value="/usr/local/bin/gh",
            ),
            patch(
                "jackpot.init.github_vars.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    args=["gh", "auth", "status"],
                    returncode=1,
                    stdout="",
                    stderr="not logged in",
                ),
            ),
        ):
            result = probe_gh()
        assert result.available is False
        assert "authenticated" in result.detail

    def test_gh_authed_with_repo_detected(self):
        # First subprocess call (`gh auth status`) returns 0;
        # second (`gh repo view --json nameWithOwner`) returns the slug.
        def fake_run(args, **kwargs):
            if args[:3] == ["gh", "auth", "status"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if args[:3] == ["gh", "repo", "view"]:
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout=json.dumps({"nameWithOwner": "Midnight-Oil-Innovation/jackpot"}),
                    stderr="",
                )
            raise AssertionError(f"unexpected subprocess call: {args}")

        with (
            patch(
                "jackpot.init.github_vars.shutil.which",
                return_value="/usr/local/bin/gh",
            ),
            patch(
                "jackpot.init.github_vars.subprocess.run",
                side_effect=fake_run,
            ),
        ):
            result = probe_gh()
        assert result.available is True
        assert result.repo_slug == "Midnight-Oil-Innovation/jackpot"

    def test_gh_authed_but_repo_detect_fails(self):
        def fake_run(args, **kwargs):
            if args[:3] == ["gh", "auth", "status"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            return subprocess.CompletedProcess(
                args=args, returncode=1, stdout="", stderr="not a repo"
            )

        with (
            patch(
                "jackpot.init.github_vars.shutil.which",
                return_value="/usr/local/bin/gh",
            ),
            patch(
                "jackpot.init.github_vars.subprocess.run",
                side_effect=fake_run,
            ),
        ):
            result = probe_gh()
        assert result.available is True
        assert result.repo_slug is None

    def test_subprocess_timeout_returns_unavailable(self):
        with (
            patch(
                "jackpot.init.github_vars.shutil.which",
                return_value="/usr/local/bin/gh",
            ),
            patch(
                "jackpot.init.github_vars.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="gh", timeout=10),
            ),
        ):
            result = probe_gh()
        assert result.available is False


class TestFetchRepoVariables:
    def test_returns_name_value_dict(self):
        payload = {
            "total_count": 2,
            "variables": [
                {"name": "GCP_PROJECT_ID", "value": "my-prod-proj"},
                {"name": "GCP_REGION", "value": "us-central1"},
            ],
        }
        with patch(
            "jackpot.init.github_vars.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            ),
        ):
            result = fetch_repo_variables("Midnight-Oil-Innovation/jackpot")
        assert result == {
            "GCP_PROJECT_ID": "my-prod-proj",
            "GCP_REGION": "us-central1",
        }

    def test_subprocess_failure_returns_empty_dict(self):
        with patch(
            "jackpot.init.github_vars.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="forbidden"
            ),
        ):
            result = fetch_repo_variables("any/slug")
        assert result == {}

    def test_invalid_json_returns_empty_dict(self):
        with patch(
            "jackpot.init.github_vars.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="not json", stderr=""
            ),
        ):
            result = fetch_repo_variables("any/slug")
        assert result == {}

    def test_subprocess_timeout_returns_empty_dict(self):
        with patch(
            "jackpot.init.github_vars.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="gh", timeout=15),
        ):
            result = fetch_repo_variables("any/slug")
        assert result == {}


class TestFetchEnvironmentVariables:
    def test_passes_environment_in_url(self):
        captured_args: list[list[str]] = []

        def fake_run(args, **kwargs):
            captured_args.append(args)
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps({"variables": []}),
                stderr="",
            )

        with patch("jackpot.init.github_vars.subprocess.run", side_effect=fake_run):
            fetch_environment_variables("o/r", "staging")

        assert any(
            "repos/o/r/environments/staging/variables" in arg
            for args in captured_args
            for arg in args
        )

    def test_returns_environment_scoped_values(self):
        payload = {
            "variables": [
                {"name": "STAGING_JACKPOT_API_URL", "value": "https://api.staging.example.org"},
            ]
        }
        with patch(
            "jackpot.init.github_vars.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(payload), stderr=""
            ),
        ):
            result = fetch_environment_variables("o/r", "staging")
        assert result == {"STAGING_JACKPOT_API_URL": "https://api.staging.example.org"}


class TestSecurityProperty:
    """The github_vars module MUST NOT have any code path that reads
    GitHub secrets. GitHub's API doesn't return secret values anyway,
    but the module's surface should reflect that — only `variables`
    endpoints are touched."""

    def test_no_secrets_fetcher_exported(self):
        from jackpot.init import github_vars

        # __all__ governs what callers can import. Any fetcher that
        # touched the secrets endpoint would have to live here.
        for exported_name in github_vars.__all__:
            assert "secret" not in exported_name.lower(), (
                f"{exported_name!r} should not be in __all__ — "
                "the github_vars module is variables-only by design."
            )

    def test_no_subprocess_call_references_secrets_endpoint(self):
        # Capture every subprocess.run call across both fetcher
        # functions and assert none of them target /actions/secrets.
        captured_args: list[list[str]] = []

        def fake_run(args, **kwargs):
            captured_args.append(args)
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps({"variables": []}),
                stderr="",
            )

        with patch("jackpot.init.github_vars.subprocess.run", side_effect=fake_run):
            fetch_repo_variables("o/r")
            fetch_environment_variables("o/r", "staging")

        for args in captured_args:
            for arg in args:
                assert "/actions/secrets" not in arg, f"Forbidden endpoint touched: {arg}"
