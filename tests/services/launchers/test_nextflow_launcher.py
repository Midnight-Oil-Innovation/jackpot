"""Hermetic tests for the B-BYOP-5a Nextflow engine launcher.

All subprocess calls are mocked — real Nextflow is never invoked.
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

from backend.services.launchers import EngineLauncher, LaunchResult, LaunchSpec
from backend.services.launchers.nextflow_launcher import NextflowLauncher, launcher

FULL_SPEC = LaunchSpec(
    pipeline_uri="https://github.com/example/pipe",
    work_dir="/data/jackpot/runs/run-1/work",
    config_path="/data/jackpot/runs/run-1/jackpot_run.config",
    profiles=["docker", "test"],
    params_file="/data/jackpot/runs/run-1/params.json",
    weblog_url="http://api:8000/api/v1/pipelines/events",
)


def _completed(returncode: int, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["nextflow"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_module_level_launcher_conforms_to_protocol():
    assert isinstance(launcher, NextflowLauncher)
    assert isinstance(launcher, EngineLauncher)
    assert launcher.engine_type == "nextflow"


def test_command_construction_full_spec():
    assert launcher.build_command(FULL_SPEC) == [
        "nextflow",
        "run",
        "https://github.com/example/pipe",
        "-c",
        "/data/jackpot/runs/run-1/jackpot_run.config",
        "-w",
        "/data/jackpot/runs/run-1/work",
        "-resume",
        "-profile",
        "docker,test",
        "-params-file",
        "/data/jackpot/runs/run-1/params.json",
        "-with-weblog",
        "http://api:8000/api/v1/pipelines/events",
    ]


def test_command_construction_minimal_spec_omits_optional_flags():
    spec = LaunchSpec(pipeline_uri="uri", work_dir="/w", resume=False)
    assert launcher.build_command(spec) == ["nextflow", "run", "uri", "-w", "/w"]


def test_resume_enabled_by_default():
    spec = LaunchSpec(pipeline_uri="uri", work_dir="/w")
    assert "-resume" in launcher.build_command(spec)


def test_launch_happy_path_success():
    with patch(
        "backend.services.launchers.nextflow_launcher.subprocess.run",
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
        "backend.services.launchers.nextflow_launcher.subprocess.run",
        return_value=_completed(1, stdout="", stderr="boom"),
    ):
        result = launcher.launch(FULL_SPEC)
    assert result.success is False
    assert result.exit_code == 1
    assert result.stderr == "boom"
    assert result.error == "nextflow exited with code 1"


def test_launch_binary_not_found_is_failure_result():
    with patch(
        "backend.services.launchers.nextflow_launcher.subprocess.run",
        side_effect=FileNotFoundError("nextflow"),
    ):
        result = launcher.launch(FULL_SPEC)
    assert result.success is False
    assert result.exit_code is None
    assert result.error == "nextflow binary not found on PATH"
