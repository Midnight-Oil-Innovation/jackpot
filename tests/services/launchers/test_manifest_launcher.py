"""Hermetic tests for the B-BYOP-5d manifest-only (engine-less) launcher.

All subprocess calls are mocked — no manifest command is ever run.
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from backend.services.launchers import EngineLauncher, LaunchResult, LaunchSpec
from backend.services.launchers.manifest_launcher import (
    ManifestError,
    ManifestLauncher,
    ManifestLaunchSpec,
    launcher,
)

SPEC = ManifestLaunchSpec(
    pipeline_uri="https://github.com/example/script-pipe",
    work_dir="/data/jackpot/runs/run-1/work",
    commands=[
        "bash run.sh --sample-id S1 --out results/",
        "python summarize.py results/",
    ],
)


def _completed(argv, returncode: int, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(
        args=argv, returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_module_level_launcher_conforms_to_protocol():
    assert isinstance(launcher, ManifestLauncher)
    assert isinstance(launcher, EngineLauncher)
    assert launcher.engine_type == "manifest"


def test_build_command_returns_sequence_in_order():
    assert launcher.build_command(SPEC) == [
        "bash run.sh --sample-id S1 --out results/",
        "python summarize.py results/",
    ]


def test_launch_happy_path_runs_all_commands_in_order():
    with patch(
        "backend.services.launchers.manifest_launcher.subprocess.run",
        side_effect=lambda argv, **kw: _completed(argv, 0, stdout=f"ran {argv[0]}\n"),
    ) as run_mock:
        result = launcher.launch(SPEC)
    assert result == LaunchResult(
        success=True,
        exit_code=0,
        stdout="ran bash\nran python\n",
        stderr="",
        error=None,
    )
    called_argvs = [call.args[0] for call in run_mock.call_args_list]
    assert called_argvs == [
        ["bash", "run.sh", "--sample-id", "S1", "--out", "results/"],
        ["python", "summarize.py", "results/"],
    ]
    for call in run_mock.call_args_list:
        assert call.kwargs == {
            "capture_output": True,
            "text": True,
            "check": False,
            "cwd": SPEC.work_dir,
        }


def test_empty_manifest_raises():
    spec = ManifestLaunchSpec(pipeline_uri="uri", work_dir="/w", commands=[])
    with pytest.raises(ManifestError, match="missing or empty"):
        launcher.launch(spec)


def test_missing_manifest_raises():
    # A plain LaunchSpec has no commands at all — treated as absent.
    spec = LaunchSpec(pipeline_uri="uri", work_dir="/w")
    with pytest.raises(ManifestError, match="missing or empty"):
        launcher.launch(spec)


def test_none_manifest_raises():
    spec = ManifestLaunchSpec(pipeline_uri="uri", work_dir="/w", commands=None)  # type: ignore[arg-type]
    with pytest.raises(ManifestError, match="missing or empty"):
        launcher.launch(spec)


def test_malformed_non_string_entry_raises():
    spec = ManifestLaunchSpec(
        pipeline_uri="uri",
        work_dir="/w",
        commands=["bash run.sh", 42],  # type: ignore[list-item]
    )
    with pytest.raises(ManifestError, match="command 1 is malformed"):
        launcher.launch(spec)


def test_malformed_blank_entry_raises():
    spec = ManifestLaunchSpec(pipeline_uri="uri", work_dir="/w", commands=["   "])
    with pytest.raises(ManifestError, match="command 0 is malformed"):
        launcher.launch(spec)


def test_malformed_unbalanced_quote_raises():
    spec = ManifestLaunchSpec(pipeline_uri="uri", work_dir="/w", commands=['bash "run.sh'])
    with pytest.raises(ManifestError, match="command 0 is malformed"):
        launcher.launch(spec)


def test_validation_runs_before_any_execution():
    spec = ManifestLaunchSpec(pipeline_uri="uri", work_dir="/w", commands=["ok", ""])
    with (
        patch("backend.services.launchers.manifest_launcher.subprocess.run") as run_mock,
        pytest.raises(ManifestError),
    ):
        launcher.launch(spec)
    run_mock.assert_not_called()


def test_launch_stops_at_first_failing_command():
    def fake_run(argv, **kw):
        if argv[0] == "bash":
            return _completed(argv, 1, stdout="partial\n", stderr="boom\n")
        raise AssertionError("second command must not run after a failure")

    with patch(
        "backend.services.launchers.manifest_launcher.subprocess.run",
        side_effect=fake_run,
    ) as run_mock:
        result = launcher.launch(SPEC)
    assert result.success is False
    assert result.exit_code == 1
    assert result.stdout == "partial\n"
    assert result.stderr == "boom\n"
    assert result.error == "manifest command 0 exited with code 1"
    assert run_mock.call_count == 1


def test_launch_executable_not_found_is_failure_result():
    with patch(
        "backend.services.launchers.manifest_launcher.subprocess.run",
        side_effect=FileNotFoundError("bash"),
    ):
        result = launcher.launch(SPEC)
    assert result.success is False
    assert result.exit_code is None
    assert result.error == "manifest command 0: executable not found: bash"
