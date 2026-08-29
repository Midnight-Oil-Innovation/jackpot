"""Tests for BYOP Stage 2 sandbox dry-run (`byop_sandbox.py`, design §5.3).

All subprocess calls are mocked with `unittest.mock` — no Docker daemon or
Kubernetes cluster is required.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from backend.services import byop_sandbox as sbx

MODULE = "backend.services.byop_sandbox"


def _proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


ARGS = dict(
    pipeline_id="42",
    image="quay.io/example/pipe:1.0",
    engine_type="nextflow",
    entrypoint="main.nf",
    sandbox_dir="/tmp/sbx",
)


# ---------------------------------------------------------------- happy path


def test_run_sandbox_happy_path():
    with patch(f"{MODULE}._run", return_value=_proc(0, stdout="ok")) as run:
        result = sbx.run_sandbox(**ARGS)
    assert result.outcome == sbx.OUTCOME_PASSED
    assert result.pipeline_id == "42"
    names = [s.step_name for s in result.steps]
    assert names == [
        "isolation_setup",
        "container_pull",
        "engine_dry_run",
        "reference_data_bind",
        "isolation_teardown",
    ]
    assert all(s.passed for s in result.steps)
    assert "ok" in result.sandbox_log
    # docker isolation is the default substrate
    first_cmd = run.call_args_list[0].args[0]
    assert first_cmd[:3] == ["docker", "network", "create"]
    assert first_cmd[-1] == "jackpot-byop-42"


def test_run_sandbox_kubernetes_isolation():
    with patch(f"{MODULE}._run", return_value=_proc(0)) as run:
        result = sbx.run_sandbox(**ARGS, isolation="kubernetes")
    assert result.outcome == sbx.OUTCOME_PASSED
    first_cmd = run.call_args_list[0].args[0]
    assert first_cmd == ["kubectl", "create", "namespace", "jackpot-byop-sandbox-42"]
    last_cmd = run.call_args_list[-1].args[0]
    assert last_cmd[:3] == ["kubectl", "delete", "namespace"]


# ------------------------------------------------------- per-step functions


def test_check_container_pull_success():
    with patch(f"{MODULE}._run", return_value=_proc(0)) as run:
        step = sbx.check_container_pull("quay.io/x/y:1", 300)
    assert step.passed
    assert run.call_args.args[0] == ["docker", "pull", "quay.io/x/y:1"]


def test_check_container_pull_failure():
    with patch(f"{MODULE}._run", return_value=_proc(1, stderr="manifest unknown")):
        step = sbx.check_container_pull("quay.io/x/missing:1", 300)
    assert not step.passed
    assert "could not be pulled" in step.message
    assert "manifest unknown" in step.log


def test_check_engine_dry_run_builds_5_3a_command():
    with patch(f"{MODULE}._run", return_value=_proc(0)) as run:
        step = sbx.check_engine_dry_run("42", "img", "nextflow", "main.nf", "/sbx", 300)
    assert step.passed
    cmd = run.call_args.args[0]
    assert "-stub-run" in cmd and "main.nf" in cmd and "/sbx" in cmd
    assert "--network" in cmd and "jackpot-byop-42" in cmd
    assert cmd[cmd.index("--cpus") : cmd.index("--cpus") + 4] == [
        "--cpus",
        sbx.SANDBOX_CPU_LIMIT,
        "--memory",
        sbx.SANDBOX_MEMORY_LIMIT,
    ]


def test_check_engine_dry_run_binary_failure():
    with patch(f"{MODULE}._run", return_value=_proc(127, stderr="not found")):
        step = sbx.check_engine_dry_run("42", "img", "snakemake", "Snakefile", "/sbx", 300)
    assert not step.passed
    assert "exited 127" in step.message
    assert "not found" in step.log


def test_check_engine_dry_run_unknown_engine():
    with patch(f"{MODULE}._run") as run:
        step = sbx.check_engine_dry_run("42", "img", "cwl", "wf.cwl", "/sbx", 300)
    assert not step.passed
    assert "Unknown engine" in step.message
    run.assert_not_called()


def test_check_engine_dry_run_manifest_fallback_timeout():
    # §5.3a — manifest scripts get JACKPOT_DRY_RUN=1 and a 60s fallback cap.
    with patch(f"{MODULE}._run", return_value=_proc(0)) as run:
        step = sbx.check_engine_dry_run("42", "img", "manifest", "run.sh", "/sbx", 300)
    assert step.passed
    cmd, timeout = run.call_args.args[0], run.call_args.args[1]
    assert "JACKPOT_DRY_RUN=1" in cmd
    assert timeout == sbx.MANIFEST_FALLBACK_TIMEOUT_SECONDS


def test_check_reference_data_bind_success():
    with patch(f"{MODULE}._run", return_value=_proc(0, stdout="reads.fastq")) as run:
        step = sbx.check_reference_data_bind("42", "img", 300)
    assert step.passed
    cmd = run.call_args.args[0]
    assert "--volume" in cmd and any("byop_sandbox" in part for part in cmd)


def test_check_reference_data_bind_failure():
    with patch(f"{MODULE}._run", return_value=_proc(2, stderr="no such file")):
        step = sbx.check_reference_data_bind("42", "img", 300)
    assert not step.passed
    assert "did not bind" in step.message


# -------------------------------------------------- entry-point soft failures


def test_run_sandbox_container_pull_failure_encoded_not_raised():
    def fake_run(cmd, timeout, env=None):
        if cmd[:2] == ["docker", "pull"]:
            return _proc(1, stderr="pull denied")
        return _proc(0)

    with patch(f"{MODULE}._run", side_effect=fake_run):
        result = sbx.run_sandbox(**ARGS)
    assert result.outcome == sbx.OUTCOME_FAILED
    failed = [s for s in result.steps if not s.passed]
    assert [s.step_name for s in failed] == ["container_pull"]
    assert "pull denied" in result.sandbox_log


def test_run_sandbox_engine_binary_failure_encoded():
    def fake_run(cmd, timeout, env=None):
        if cmd[:2] == ["docker", "run"] and "--volume" not in cmd:
            return _proc(1, stderr="nextflow: command not found")
        return _proc(0)

    with patch(f"{MODULE}._run", side_effect=fake_run):
        result = sbx.run_sandbox(**ARGS)
    assert result.outcome == sbx.OUTCOME_FAILED
    assert any(s.step_name == "engine_dry_run" and not s.passed for s in result.steps)
    # bind step never ran — failure short-circuits
    assert "reference_data_bind" not in [s.step_name for s in result.steps]


def test_run_sandbox_reference_bind_failure_encoded():
    def fake_run(cmd, timeout, env=None):
        if "--volume" in cmd:
            return _proc(125, stderr="invalid mount config")
        return _proc(0)

    with patch(f"{MODULE}._run", side_effect=fake_run):
        result = sbx.run_sandbox(**ARGS)
    assert result.outcome == sbx.OUTCOME_FAILED
    assert any(s.step_name == "reference_data_bind" and not s.passed for s in result.steps)


def test_run_sandbox_isolation_setup_failure_returns_failed_result():
    def fake_run(cmd, timeout, env=None):
        if cmd[:3] == ["docker", "network", "create"]:
            return _proc(1, stderr="network exists")
        return _proc(0)

    with patch(f"{MODULE}._run", side_effect=fake_run):
        result = sbx.run_sandbox(**ARGS)
    assert result.outcome == sbx.OUTCOME_FAILED
    assert result.steps[0].step_name == "isolation_setup"
    assert not result.steps[0].passed
    assert "network exists" in result.sandbox_log


def test_run_sandbox_bad_isolation_substrate_fails_soft():
    result = sbx.run_sandbox(**ARGS, isolation="podman")
    assert result.outcome == sbx.OUTCOME_FAILED
    assert "Unknown isolation substrate" in result.steps[0].message


def test_run_sandbox_timeout_classified_sandbox_timeout():
    def fake_run(cmd, timeout, env=None):
        if cmd[:2] == ["docker", "pull"]:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
        return _proc(0)

    with patch(f"{MODULE}._run", side_effect=fake_run):
        result = sbx.run_sandbox(**ARGS)
    assert result.outcome == sbx.OUTCOME_TIMEOUT
    assert any(s.step_name == "timeout" for s in result.steps)


# ------------------------------------------------------- cleanup always runs


def test_cleanup_runs_on_midrun_failure():
    def fake_run(cmd, timeout, env=None):
        if cmd[:2] == ["docker", "pull"]:
            return _proc(1, stderr="boom")
        return _proc(0)

    with (
        patch(f"{MODULE}._run", side_effect=fake_run),
        patch(
            f"{MODULE}.teardown_isolation",
            wraps=sbx.teardown_isolation,
        ) as teardown,
    ):
        result = sbx.run_sandbox(**ARGS)
    teardown.assert_called_once_with("42", "docker", sbx.DEFAULT_TIMEOUT_SECONDS)
    assert result.steps[-1].step_name == "isolation_teardown"


def test_cleanup_runs_on_timeout():
    def fake_run(cmd, timeout, env=None):
        if cmd[:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
        return _proc(0)

    with (
        patch(f"{MODULE}._run", side_effect=fake_run),
        patch(f"{MODULE}.teardown_isolation", wraps=sbx.teardown_isolation) as teardown,
    ):
        result = sbx.run_sandbox(**ARGS)
    assert result.outcome == sbx.OUTCOME_TIMEOUT
    teardown.assert_called_once()


def test_teardown_isolation_failure_is_reported_not_raised():
    with patch(f"{MODULE}._run", return_value=_proc(1, stderr="in use")):
        step = sbx.teardown_isolation("42", "docker", 300)
    assert not step.passed
    assert "Failed to remove" in step.message


def test_teardown_isolation_timeout_is_soft():
    with patch(
        f"{MODULE}._run",
        side_effect=subprocess.TimeoutExpired(cmd=["docker"], timeout=300),
    ):
        step = sbx.teardown_isolation("42", "kubernetes", 300)
    assert not step.passed
    assert "Timed out" in step.message


# ------------------------------------------------------------- misc helpers


def test_sandbox_log_truncated_to_10kb():
    big = "x" * (sbx.SANDBOX_LOG_MAX_BYTES + 500)
    with patch(f"{MODULE}._run", return_value=_proc(0, stdout=big)):
        result = sbx.run_sandbox(**ARGS)
    assert len(result.sandbox_log.encode()) <= sbx.SANDBOX_LOG_MAX_BYTES


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("", sbx.DEFAULT_TIMEOUT_SECONDS), ("120", 120), ("junk", sbx.DEFAULT_TIMEOUT_SECONDS)],
)
def test_sandbox_timeout_seconds_env(raw, expected, monkeypatch):
    monkeypatch.setenv(sbx.TIMEOUT_ENV_VAR, raw)
    assert sbx.sandbox_timeout_seconds() == expected


def test_create_isolation_kubernetes_failure():
    with patch(f"{MODULE}._run", return_value=_proc(1, stderr="forbidden")):
        step = sbx.create_isolation("42", "kubernetes", 300)
    assert not step.passed
    assert "jackpot-byop-sandbox-42" in step.message


# ------------------------------------------------ argv injection guard


def test_flag_like_image_rejected_without_subprocess():
    with patch(f"{MODULE}._run") as run:
        pull = sbx.check_container_pull("--privileged", 300)
        engine = sbx.check_engine_dry_run("42", "--privileged", "nextflow", "main.nf", "/sbx", 300)
        bind = sbx.check_reference_data_bind("42", "--privileged", 300)
        entry = sbx.check_engine_dry_run("42", "img", "nextflow", "--bad-entry", "/sbx", 300)
    for step in (pull, engine, bind, entry):
        assert not step.passed
        assert "flag-like" in step.message
    run.assert_not_called()
