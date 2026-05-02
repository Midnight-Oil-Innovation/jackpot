"""Security regression tests for `jackpot init`.

P0e ultrareview HIGH-1: --instance-name path traversal.
P0e ultrareview MEDIUM-1: psql + alembic env hygiene (PATH from
shell, not from .env.local).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from jackpot.cli.init import init

# ── Path traversal in --instance-name (HIGH-1) ─────────────────────────


@pytest.mark.parametrize(
    "bad_name",
    [
        "../escape",
        "../../etc/cron.d",
        "..",
        ".",
        ".hidden",
        "with/slash",
        "with\\backslash",
        "  leading-spaces",  # not stripped — strict regex
        "trailing-spaces  ",
        "-leading-dash",
        "with space",
        "name;with;semis",
        "$injected",
    ],
)
def test_configure_rejects_path_traversal_instance_name(
    runner: CliRunner, tmp_path: Path, bad_name: str
):
    result = runner.invoke(
        init,
        [
            "configure",
            "--scenario",
            "F",
            "--instance-name",
            bad_name,
            "--instances-dir",
            str(tmp_path),
            "--non-interactive",
            "--no-gh",
        ],
    )
    assert result.exit_code != 0, f"{bad_name!r} should be rejected"
    assert (
        "Invalid --instance-name" in result.output
    ), f"{bad_name!r} did not produce a validation error: {result.output}"


@pytest.mark.parametrize(
    "good_name",
    [
        "local",
        "ci-local",
        "production",
        "staging-2",
        "tribal_health_dept",
        "instance123",
        "A",
        "z9_a-b0",
    ],
)
def test_configure_accepts_well_formed_instance_name(
    runner: CliRunner, tmp_path: Path, good_name: str
):
    result = runner.invoke(
        init,
        [
            "configure",
            "--scenario",
            "F",
            "--instance-name",
            good_name,
            "--instances-dir",
            str(tmp_path),
            "--non-interactive",
            "--no-gh",
        ],
    )
    # `ci` is rejected separately by Critical Rule 56; everything else
    # in the parametrize set should configure cleanly.
    if good_name == "ci":
        assert result.exit_code != 0
    else:
        assert result.exit_code == 0, result.output


def test_secrets_rejects_path_traversal_instance_name(runner: CliRunner, tmp_path: Path):
    result = runner.invoke(
        init,
        [
            "secrets",
            "--instance",
            "../escape",
            "--instances-dir",
            str(tmp_path),
            "--non-interactive",
        ],
    )
    assert result.exit_code != 0
    assert "Invalid --instance-name" in result.output


def test_validate_rejects_path_traversal_instance_name(runner: CliRunner, tmp_path: Path):
    result = runner.invoke(
        init,
        [
            "validate",
            "--instance",
            "../escape",
            "--instances-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code != 0
    assert "Invalid --instance-name" in result.output


def test_bootstrap_rejects_path_traversal_instance_name(runner: CliRunner, tmp_path: Path):
    result = runner.invoke(
        init,
        [
            "bootstrap",
            "--instance",
            "../escape",
            "--instances-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code != 0
    assert "Invalid --instance-name" in result.output


# ── env-PATH hygiene in bootstrap (MEDIUM-1) ───────────────────────────


def _seed_instance_for_bootstrap(tmp_path: Path, name: str) -> Path:
    instance_dir = tmp_path / name
    (instance_dir / "secrets").mkdir(parents=True)
    (instance_dir / "jackpot.toml").write_text('[scenario]\ncode = "F"\nname = "CI"\n')
    (instance_dir / ".env.local").write_text(
        # An attacker-supplied .env.local with a malicious PATH AND a
        # legitimate DATABASE_URL.
        "PATH=/tmp/evil:/usr/bin\n"
        "JACKPOT_API_URL=http://localhost:8000\n"
        "DATABASE_URL=postgresql://j:j@localhost/j\n"
    )
    (instance_dir / "seed.sql").write_text("-- empty\n")
    (instance_dir / "secrets" / "jwt_signing_key.txt").write_text("deadbeef" * 8 + "\n")
    return instance_dir


def test_bootstrap_alembic_env_pathos_calling_shell_not_env_local(
    runner: CliRunner, tmp_path: Path
):
    """The malicious PATH=/tmp/evil in .env.local must NOT reach the
    alembic subprocess. Calling-shell PATH wins."""
    _seed_instance_for_bootstrap(tmp_path, "evil")

    captured_envs: list[dict] = []

    def fake_run(*args, **kwargs):
        captured_envs.append(kwargs.get("env") or {})
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with (
        patch("subprocess.run", side_effect=fake_run),
        patch("jackpot.init.validator.check_health") as mock_health,
    ):
        mock_health.return_value = type(
            "R", (), {"ok": True, "detail": "ok", "elapsed_seconds": 1.0}
        )()
        runner.invoke(
            init,
            [
                "bootstrap",
                "--instance",
                "evil",
                "--instances-dir",
                str(tmp_path),
            ],
        )

    # Both alembic + psql subprocesses should have run; the alembic env
    # is the first captured one.
    assert captured_envs, "no subprocesses were invoked"
    alembic_env = captured_envs[0]
    assert "PATH" in alembic_env
    assert (
        "/tmp/evil" not in alembic_env["PATH"]
    ), f"alembic PATH was poisoned by .env.local: {alembic_env['PATH']!r}"


def test_bootstrap_psql_env_pathos_calling_shell_not_env_local(runner: CliRunner, tmp_path: Path):
    """Same property for psql — its env must NOT inherit PATH from
    .env.local."""
    _seed_instance_for_bootstrap(tmp_path, "evil2")

    captured_envs: list[dict] = []

    def fake_run(*args, **kwargs):
        captured_envs.append(kwargs.get("env") or {})
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with (
        patch("subprocess.run", side_effect=fake_run),
        patch("jackpot.init.validator.check_health") as mock_health,
    ):
        mock_health.return_value = type(
            "R", (), {"ok": True, "detail": "ok", "elapsed_seconds": 1.0}
        )()
        runner.invoke(
            init,
            [
                "bootstrap",
                "--instance",
                "evil2",
                "--instances-dir",
                str(tmp_path),
            ],
        )

    # psql is the second subprocess (alembic ran first).
    assert len(captured_envs) >= 2, captured_envs
    psql_env = captured_envs[1]
    assert "PATH" in psql_env
    assert "/tmp/evil" not in psql_env["PATH"]
