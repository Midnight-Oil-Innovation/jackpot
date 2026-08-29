"""Hermetic tests for the B-BYOP-5c WDL engine launcher.

All subprocess calls are mocked — no real WDL engine is invoked.
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from backend.services.launchers import EngineLauncher, LaunchResult, LaunchSpec
from backend.services.launchers.wdl_launcher import WdlLauncher, launcher

FULL_SPEC = LaunchSpec(
    pipeline_uri="/pipelines/variant_call/workflow.wdl",
    work_dir="/data/jackpot/runs/run-1/work",
    params_file="/data/jackpot/runs/run-1/inputs.json",
)


def _completed(returncode: int, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["miniwdl"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_module_level_launcher_conforms_to_protocol():
    assert isinstance(launcher, WdlLauncher)
    assert isinstance(launcher, EngineLauncher)
    assert launcher.engine_type == "wdl"


def test_command_construction_miniwdl_default(monkeypatch):
    monkeypatch.delenv("JACKPOT_WDL_BACKEND", raising=False)
    assert launcher.build_command(FULL_SPEC) == [
        "miniwdl",
        "run",
        "/pipelines/variant_call/workflow.wdl",
        "--input",
        "/data/jackpot/runs/run-1/inputs.json",
        "--dir",
        "/data/jackpot/runs/run-1/work",
    ]


def test_command_construction_miniwdl_without_inputs(monkeypatch):
    monkeypatch.delenv("JACKPOT_WDL_BACKEND", raising=False)
    spec = LaunchSpec(pipeline_uri="wf.wdl", work_dir="/w")
    assert launcher.build_command(spec) == ["miniwdl", "run", "wf.wdl", "--dir", "/w"]


def test_command_construction_cromwell_backend(monkeypatch):
    monkeypatch.setenv("JACKPOT_WDL_BACKEND", "cromwell")
    assert launcher.build_command(FULL_SPEC) == [
        "cromwell",
        "run",
        "/pipelines/variant_call/workflow.wdl",
        "--inputs",
        "/data/jackpot/runs/run-1/inputs.json",
    ]


def test_unknown_backend_raises(monkeypatch):
    monkeypatch.setenv("JACKPOT_WDL_BACKEND", "toil")
    with pytest.raises(ValueError, match="JACKPOT_WDL_BACKEND"):
        launcher.build_command(FULL_SPEC)


def test_missing_wdl_path_raises_before_subprocess(monkeypatch):
    monkeypatch.delenv("JACKPOT_WDL_BACKEND", raising=False)
    spec = LaunchSpec(pipeline_uri="   ", work_dir="/w")
    with (
        patch("backend.services.launchers.wdl_launcher.subprocess.run") as run_mock,
        pytest.raises(ValueError, match="pipeline_uri"),
    ):
        launcher.launch(spec)
    run_mock.assert_not_called()


def test_launch_happy_path_success(monkeypatch):
    monkeypatch.delenv("JACKPOT_WDL_BACKEND", raising=False)
    with patch(
        "backend.services.launchers.wdl_launcher.subprocess.run",
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


def test_launch_nonzero_exit_is_failure_with_stderr_in_error(monkeypatch):
    monkeypatch.delenv("JACKPOT_WDL_BACKEND", raising=False)
    with patch(
        "backend.services.launchers.wdl_launcher.subprocess.run",
        return_value=_completed(1, stdout="", stderr="task failed: OOM"),
    ):
        result = launcher.launch(FULL_SPEC)
    assert result.success is False
    assert result.exit_code == 1
    assert result.stderr == "task failed: OOM"
    assert result.error == "miniwdl exited with code 1: task failed: OOM"


def test_launch_binary_not_found_is_failure_result(monkeypatch):
    monkeypatch.delenv("JACKPOT_WDL_BACKEND", raising=False)
    with patch(
        "backend.services.launchers.wdl_launcher.subprocess.run",
        side_effect=FileNotFoundError("miniwdl"),
    ):
        result = launcher.launch(FULL_SPEC)
    assert result.success is False
    assert result.exit_code is None
    assert result.error == "miniwdl binary not found on PATH"
