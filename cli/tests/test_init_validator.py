"""Tests for `jackpot.init.validator` + the bootstrap/validate CLI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from jackpot.cli.init import init
from jackpot.init.validator import (
    check_bootstrap_preconditions,
    check_health,
    parse_api_url_from_env_local,
)

# ── parse_api_url_from_env_local ───────────────────────────────────────


class TestParseApiUrl:
    def test_reads_jackpot_api_url(self, tmp_path: Path):
        env_local = tmp_path / ".env.local"
        env_local.write_text(
            "# Header comment\nJACKPOT_API_URL=https://api.example.org\nOTHER_VAR=ignored\n"
        )
        assert parse_api_url_from_env_local(env_local) == "https://api.example.org"

    def test_falls_back_to_localhost_when_unset(self, tmp_path: Path):
        env_local = tmp_path / ".env.local"
        env_local.write_text("OTHER_VAR=x\n")
        assert parse_api_url_from_env_local(env_local) == "http://localhost:8000"

    def test_strips_quotes(self, tmp_path: Path):
        env_local = tmp_path / ".env.local"
        env_local.write_text('JACKPOT_API_URL="https://api.example.org"\n')
        assert parse_api_url_from_env_local(env_local) == "https://api.example.org"

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="does not exist"):
            parse_api_url_from_env_local(tmp_path / "missing.env")

    def test_ignores_comments_and_blank_lines(self, tmp_path: Path):
        env_local = tmp_path / ".env.local"
        env_local.write_text(
            "\n"
            "# a comment with JACKPOT_API_URL=fake-url-in-comment\n"
            "JACKPOT_API_URL=https://real.example.org\n"
        )
        assert parse_api_url_from_env_local(env_local) == "https://real.example.org"


# ── check_health (with stubbed http_get + sleep + now) ────────────────


class _FakeResponse:
    def __init__(self, status_code: int, body: dict | None = None, raise_json=False):
        self.status_code = status_code
        self._body = body or {}
        self._raise_json = raise_json

    def json(self):
        if self._raise_json:
            raise ValueError("not JSON")
        return self._body


class _Clock:
    """Drives the validator's `now` callable forward by a fixed step
    each call. Combined with a stubbed sleep that does nothing, makes
    the polling loop testable in <1ms."""

    def __init__(self, step: float = 1.0):
        self.t = 0.0
        self.step = step

    def __call__(self) -> float:
        self.t += self.step
        return self.t


class TestCheckHealth:
    def test_ok_on_first_response(self):
        result = check_health(
            "http://api",
            timeout_seconds=10,
            http_get=lambda url, timeout: _FakeResponse(
                200, {"status": "ok", "database": "connected", "version": "5.0.0"}
            ),
            sleep=lambda _: None,
            now=_Clock(step=1.0),
        )
        assert result.ok
        assert "5.0.0" in result.detail

    def test_eventually_ok(self):
        # First two probes return 503; third returns 200.
        responses = iter(
            [
                _FakeResponse(503),
                _FakeResponse(503),
                _FakeResponse(200, {"status": "ok", "database": "connected"}),
            ]
        )

        result = check_health(
            "http://api",
            timeout_seconds=10,
            http_get=lambda url, timeout: next(responses),
            sleep=lambda _: None,
            now=_Clock(step=1.0),
        )
        assert result.ok

    def test_database_unavailable_keeps_polling_until_timeout(self):
        result = check_health(
            "http://api",
            timeout_seconds=2,
            http_get=lambda url, timeout: _FakeResponse(
                200, {"status": "unavailable", "database": "unavailable"}
            ),
            sleep=lambda _: None,
            now=_Clock(step=1.0),
        )
        assert not result.ok
        assert "timed out" in result.detail

    def test_connection_error_loops_until_timeout(self):
        def _raises(url, timeout):
            raise ConnectionError("nope")

        result = check_health(
            "http://api",
            timeout_seconds=2,
            http_get=_raises,
            sleep=lambda _: None,
            now=_Clock(step=1.0),
        )
        assert not result.ok
        assert "connection failed" in result.detail

    def test_non_json_body_keeps_polling(self):
        result = check_health(
            "http://api",
            timeout_seconds=2,
            http_get=lambda url, timeout: _FakeResponse(200, body={}, raise_json=True),
            sleep=lambda _: None,
            now=_Clock(step=1.0),
        )
        assert not result.ok
        assert "non-JSON" in result.detail


# ── check_bootstrap_preconditions ──────────────────────────────────────


class TestPreconditions:
    def test_all_files_present(self, tmp_path: Path):
        for rel in (
            "jackpot.toml",
            ".env.local",
            "seed.sql",
            "secrets/jwt_signing_key.txt",
        ):
            full = tmp_path / rel
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text("x")
        result = check_bootstrap_preconditions(tmp_path)
        assert result.ok
        assert result.missing == ()

    def test_missing_files_listed(self, tmp_path: Path):
        # Only jackpot.toml present.
        (tmp_path / "jackpot.toml").write_text("x")
        result = check_bootstrap_preconditions(tmp_path)
        assert not result.ok
        assert ".env.local" in result.missing
        assert "seed.sql" in result.missing
        assert "secrets/jwt_signing_key.txt" in result.missing


# ── CLI: validate subcommand ───────────────────────────────────────────


class TestValidateCli:
    def test_validate_requires_existing_instance(self, runner: CliRunner, tmp_path: Path):
        result = runner.invoke(
            init,
            [
                "validate",
                "--instance",
                "missing",
                "--instances-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code != 0
        assert "does not exist" in result.output

    def test_validate_uses_api_url_override(self, runner: CliRunner, tmp_path: Path):
        instance_dir = tmp_path / "v"
        instance_dir.mkdir()
        (instance_dir / ".env.local").write_text("JACKPOT_API_URL=http://from-env\n")

        with patch("jackpot.init.validator.check_health") as mock_check:
            mock_check.return_value = type(
                "R", (), {"ok": True, "detail": "ok", "elapsed_seconds": 1.0}
            )()
            result = runner.invoke(
                init,
                [
                    "validate",
                    "--instance",
                    "v",
                    "--instances-dir",
                    str(tmp_path),
                    "--api-url",
                    "http://override",
                ],
            )
        assert result.exit_code == 0
        # check_health called with the override URL, not the env-file URL.
        called_url = mock_check.call_args[0][0]
        assert called_url == "http://override"

    def test_validate_aborts_on_health_failure(self, runner: CliRunner, tmp_path: Path):
        instance_dir = tmp_path / "v"
        instance_dir.mkdir()
        (instance_dir / ".env.local").write_text("JACKPOT_API_URL=http://api\n")

        with patch("jackpot.init.validator.check_health") as mock_check:
            mock_check.return_value = type(
                "R",
                (),
                {"ok": False, "detail": "timed out", "elapsed_seconds": 60.0},
            )()
            result = runner.invoke(
                init,
                [
                    "validate",
                    "--instance",
                    "v",
                    "--instances-dir",
                    str(tmp_path),
                ],
            )
        assert result.exit_code != 0
        assert "timed out" in result.output


# ── CLI: bootstrap subcommand ──────────────────────────────────────────


class TestBootstrapCli:
    def _seed_instance(self, tmp_path: Path, name: str) -> Path:
        """Create a minimal instance directory that passes preconditions."""
        instance_dir = tmp_path / name
        (instance_dir / "secrets").mkdir(parents=True)
        (instance_dir / "jackpot.toml").write_text('[scenario]\ncode = "F"\nname = "CI"\n')
        (instance_dir / ".env.local").write_text(
            "JACKPOT_API_URL=http://localhost:8000\nDATABASE_URL=postgresql://j:j@localhost/j\n"
        )
        (instance_dir / "seed.sql").write_text("-- empty\n")
        (instance_dir / "secrets" / "jwt_signing_key.txt").write_text("deadbeef" * 8 + "\n")
        return instance_dir

    def test_bootstrap_refuses_committed_ci(self, runner: CliRunner, tmp_path: Path):
        # Seed instances/ci/ so the existence check passes; the
        # Rule 56 check should fire next.
        ci_dir = tmp_path / "ci"
        ci_dir.mkdir()
        (ci_dir / "jackpot.toml").write_text('[scenario]\ncode = "F"\nname = "CI"\n')
        result = runner.invoke(
            init,
            [
                "bootstrap",
                "--instance",
                "ci",
                "--instances-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code != 0
        assert "Critical Rule 56" in result.output

    def test_bootstrap_aborts_on_missing_preconditions(self, runner: CliRunner, tmp_path: Path):
        # Empty instance dir — all preconditions will fail.
        instance_dir = tmp_path / "incomplete"
        instance_dir.mkdir()
        (instance_dir / "jackpot.toml").write_text('[scenario]\ncode = "F"\n')
        result = runner.invoke(
            init,
            [
                "bootstrap",
                "--instance",
                "incomplete",
                "--instances-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code != 0
        assert "Missing required files" in result.output

    def test_bootstrap_skip_all_with_full_skip_flags(self, runner: CliRunner, tmp_path: Path):
        # When all three skip flags are passed, bootstrap is just a
        # precondition check + announce — useful for verifying the
        # files are in place without touching the DB or API.
        self._seed_instance(tmp_path, "ok")
        result = runner.invoke(
            init,
            [
                "bootstrap",
                "--instance",
                "ok",
                "--instances-dir",
                str(tmp_path),
                "--skip-alembic",
                "--skip-seed",
                "--skip-validate",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "[skipped]  alembic upgrade head" in result.output
        assert "[skipped]  apply seed.sql" in result.output
        assert "[skipped]  /health smoke test" in result.output
        assert "Bootstrap complete." in result.output

    def test_bootstrap_aborts_when_database_url_missing(self, runner: CliRunner, tmp_path: Path):
        instance_dir = self._seed_instance(tmp_path, "no-db")
        # Wipe DATABASE_URL from the env file.
        (instance_dir / ".env.local").write_text("JACKPOT_API_URL=http://localhost:8000\n")
        result = runner.invoke(
            init,
            [
                "bootstrap",
                "--instance",
                "no-db",
                "--instances-dir",
                str(tmp_path),
                "--skip-alembic",
                "--skip-validate",
            ],
        )
        assert result.exit_code != 0
        assert "DATABASE_URL not set" in result.output
