"""Phase P0h H-5 — ``jackpot doctor slurm`` CLI tests.

The doctor command pairs the local-filesystem validation predicate
(``backend.pipeline_config.profile_validation``) with optional
cluster-side ``sinfo`` and ``srun`` probes. Tests exercise both
paths: the API-host-only flow (no --check-cluster), and the cluster
flow with subprocess.run mocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from jackpot.cli.main import cli

# ─────────────────── local-only path ───────────────────


def test_doctor_slurm_clean_workdir_exits_zero(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["doctor", "slurm", "--work-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output


def test_doctor_slurm_missing_workdir_exits_two(tmp_path: Path):
    missing = tmp_path / "does-not-exist"
    runner = CliRunner()
    result = runner.invoke(cli, ["doctor", "slurm", "--work-dir", str(missing)])
    assert result.exit_code == 2, result.output
    assert "MISSING" in result.output


def test_doctor_slurm_readonly_workdir_exits_one(tmp_path: Path):
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)
    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "slurm", "--work-dir", str(ro)])
        assert result.exit_code == 1, result.output
        assert "NOT_WRITABLE" in result.output
    finally:
        ro.chmod(0o700)


def test_doctor_slurm_remote_uri_exits_zero():
    runner = CliRunner()
    result = runner.invoke(cli, ["doctor", "slurm", "--work-dir", "gs://j/runs"])
    assert result.exit_code == 0, result.output
    assert "REMOTE_SCHEME" in result.output


# ─────────────────── --check-cluster path ───────────────────


def _fake_run(returncode: int, stdout: str = "", stderr: str = ""):
    """Build a subprocess.CompletedProcess-like object for the mock."""

    class _FakeCompleted:
        def __init__(self) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    return _FakeCompleted()


def test_doctor_slurm_check_cluster_happy_path(tmp_path: Path):
    """sinfo returns rows + srun stat echoes the work_dir → exit 0."""
    work_dir = str(tmp_path)

    def _run_side_effect(cmd, **kwargs):
        if cmd[0] == "sinfo":
            return _fake_run(0, stdout="compute up infinite 4 idle node[01-04]\n")
        if cmd[0] == "srun":
            # The doctor uses `stat -c '%n' <work_dir>` so stdout
            # echoes the work_dir.
            return _fake_run(0, stdout=work_dir)
        return _fake_run(1, stderr="unexpected cmd")

    with (
        patch("jackpot.cli.doctor.shutil.which", return_value="/usr/bin/x"),
        patch("jackpot.cli.doctor.subprocess.run", side_effect=_run_side_effect),
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "doctor",
                "slurm",
                "--work-dir",
                work_dir,
                "--account",
                "lab-2026",
                "--partition",
                "compute",
                "--check-cluster",
            ],
        )
    assert result.exit_code == 0, result.output


def test_doctor_slurm_check_cluster_sinfo_missing_exits_two(tmp_path: Path):
    """If sinfo isn't on PATH, doctor reports SINFO_NOT_INSTALLED and
    exits 2 because we can't validate the cluster at all."""
    with patch("jackpot.cli.doctor.shutil.which", return_value=None):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "doctor",
                "slurm",
                "--work-dir",
                str(tmp_path),
                "--check-cluster",
            ],
        )
    assert result.exit_code == 2, result.output
    assert "SINFO_NOT_INSTALLED" in result.output


def test_doctor_slurm_check_cluster_srun_failure_exits_two(tmp_path: Path):
    """sinfo succeeds, srun stat returns non-zero → workdir not visible
    from compute node → exit 2."""
    work_dir = str(tmp_path)

    def _run_side_effect(cmd, **kwargs):
        if cmd[0] == "sinfo":
            return _fake_run(0, stdout="compute up infinite 4 idle node[01]\n")
        if cmd[0] == "srun":
            return _fake_run(1, stderr="stat: cannot stat '/nope': No such file")
        return _fake_run(1)

    with (
        patch("jackpot.cli.doctor.shutil.which", return_value="/usr/bin/x"),
        patch("jackpot.cli.doctor.subprocess.run", side_effect=_run_side_effect),
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "doctor",
                "slurm",
                "--work-dir",
                work_dir,
                "--check-cluster",
            ],
        )
    assert result.exit_code == 2, result.output
    assert "SRUN_FAILED" in result.output


def test_doctor_slurm_check_cluster_skips_srun_when_sinfo_blocks(tmp_path: Path):
    """sinfo failing is a blocking error; doctor should not bother
    running srun afterwards (would just be noise)."""
    work_dir = str(tmp_path)
    calls: list[str] = []

    def _run_side_effect(cmd, **kwargs):
        calls.append(cmd[0])
        if cmd[0] == "sinfo":
            return _fake_run(1, stderr="slurm_load_partitions: Connection refused")
        return _fake_run(0, stdout=work_dir)

    with (
        patch("jackpot.cli.doctor.shutil.which", return_value="/usr/bin/x"),
        patch("jackpot.cli.doctor.subprocess.run", side_effect=_run_side_effect),
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "doctor",
                "slurm",
                "--work-dir",
                work_dir,
                "--check-cluster",
            ],
        )
    assert result.exit_code == 2, result.output
    assert "SINFO_FAILED" in result.output
    assert "srun" not in calls
