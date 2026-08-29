"""Hermetic tests for the B-BYOP-5b Snakemake engine launcher.

All subprocess calls are mocked — real Snakemake is never invoked.
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

from backend.services.launchers import EngineLauncher, LaunchResult, LaunchSpec
from backend.services.launchers.snakemake_launcher import SnakemakeLauncher, launcher

FULL_SPEC = LaunchSpec(
    pipeline_uri="/data/jackpot/pipelines/pipe/Snakefile",
    work_dir="/data/jackpot/runs/run-1/work",
    config_path="/data/jackpot/runs/run-1/config.yaml",
    profiles=["docker", "test"],
    params_file="/data/jackpot/runs/run-1/params.json",
    weblog_url="http://api:8000/api/v1/pipelines/events",
)


def _completed(returncode: int, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["snakemake"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_module_level_launcher_conforms_to_protocol():
    assert isinstance(launcher, SnakemakeLauncher)
    assert isinstance(launcher, EngineLauncher)
    assert launcher.engine_type == "snakemake"


def test_command_construction_full_spec():
    assert launcher.build_command(FULL_SPEC) == [
        "snakemake",
        "--snakefile",
        "/data/jackpot/pipelines/pipe/Snakefile",
        "--configfile",
        "/data/jackpot/runs/run-1/config.yaml",
        "--directory",
        "/data/jackpot/runs/run-1/work",
        "--rerun-incomplete",
        "--keep-going",
    ]


def test_command_construction_minimal_spec_omits_optional_flags():
    spec = LaunchSpec(pipeline_uri="Snakefile", work_dir="/w", resume=False)
    assert launcher.build_command(spec) == [
        "snakemake",
        "--snakefile",
        "Snakefile",
        "--directory",
        "/w",
    ]


def test_resume_flags_enabled_by_default():
    spec = LaunchSpec(pipeline_uri="Snakefile", work_dir="/w")
    cmd = launcher.build_command(spec)
    assert "--rerun-incomplete" in cmd
    assert "--keep-going" in cmd


def test_no_weblog_flag_for_snakemake():
    # §3.2: Snakemake has no native weblog — events come from the poller.
    cmd = launcher.build_command(FULL_SPEC)
    assert FULL_SPEC.weblog_url not in cmd


def test_launch_happy_path_success():
    with patch(
        "backend.services.launchers.snakemake_launcher.subprocess.run",
        return_value=_completed(0, stdout="run ok", stderr=""),
    ) as run_mock:
        result = launcher.launch(FULL_SPEC)
    assert result == LaunchResult(success=True, exit_code=0, stdout="run ok", stderr="", error=None)
    run_mock.assert_called_once_with(
        launcher.build_command(FULL_SPEC),
        capture_output=True,
        text=True,
        check=False,
    )


def test_launch_nonzero_exit_is_failure():
    with patch(
        "backend.services.launchers.snakemake_launcher.subprocess.run",
        return_value=_completed(1, stdout="", stderr="MissingInputException: boom"),
    ):
        result = launcher.launch(FULL_SPEC)
    assert result.success is False
    assert result.exit_code == 1
    assert result.stderr == "MissingInputException: boom"
    assert result.error == "snakemake exited with code 1"


def test_launch_binary_not_found_is_failure_result():
    with patch(
        "backend.services.launchers.snakemake_launcher.subprocess.run",
        side_effect=FileNotFoundError("snakemake"),
    ):
        result = launcher.launch(FULL_SPEC)
    assert result.success is False
    assert result.exit_code is None
    assert result.error == "snakemake binary not found on PATH"
