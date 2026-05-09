"""
jackpot.cli.doctor
~~~~~~~~~~~~~~~~~~
``jackpot doctor`` command group — pre-launch sanity checks for
execution profiles.

Commands:
  jackpot doctor slurm   — validate a Slurm profile's work_dir on the
                            API host and (optionally) verify the same
                            path is visible to compute nodes via srun.

Phase P0h H-5. The CLI is the operator-facing surface for the
``backend.pipeline_config.profile_validation`` predicate plus an
optional cluster-side reachability probe. ``jackpot doctor`` runs on
the API host (it stat's the local filesystem) and shells out to
``sinfo`` / ``srun --pty hostname`` against the operator-supplied
account / partition; no DB access is required.

When P0g G-5 ships profile CRUD HTTP endpoints, ``jackpot doctor
slurm`` will gain a ``--profile <name>`` form that fetches the row
via API and runs the same checks. Until then, the operator passes
the profile fields directly via flags.
"""

from __future__ import annotations

import shutil
import subprocess

# Backend lives in a sibling Python package; the validation predicate
# is the source of truth for the local-filesystem half of the check.
# Adding ``backend`` to the path is the project's pattern for cross-
# package imports from the CLI (see cli/tests/conftest.py for parity).
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

_BACKEND_PATH = (Path(__file__).resolve().parents[3] / "backend").as_posix()
if _BACKEND_PATH not in sys.path:
    sys.path.insert(0, _BACKEND_PATH)

from backend.pipeline_config.profile_validation import (  # noqa: E402
    ValidationFinding,
    has_blocking_findings,
    validate_work_dir_locally,
)

_console = Console()


@click.group()
def doctor() -> None:
    """Diagnose execution profiles before launch.

    \b
    Slurm profile validation:
      jackpot doctor slurm --work-dir /srv/jackpot/work
      jackpot doctor slurm --work-dir /scratch/jp --account lab-2026 \\
          --partition compute --check-cluster
    """


def _print_findings(findings: list[ValidationFinding], context: str) -> None:
    if not findings:
        _console.print(f"[green]✓[/green] {context}: no findings.")
        return
    table = Table(title=context, show_lines=False)
    table.add_column("severity", style="bold")
    table.add_column("code")
    table.add_column("message")
    for f in findings:
        colour = {
            "error": "red",
            "warning": "yellow",
            "info": "cyan",
        }.get(f.severity, "white")
        table.add_row(
            f"[{colour}]{f.severity.upper()}[/{colour}]",
            f.code,
            f.message,
        )
    _console.print(table)


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def _run_with_timeout(cmd: list[str], *, timeout: float) -> tuple[int, str, str]:
    """Run ``cmd`` capturing stdout / stderr; never raise on timeout.

    Returns ``(returncode, stdout, stderr)``. On timeout, returncode
    is set to a sentinel (-1) and stderr carries an explanatory note.
    """
    try:
        proc = subprocess.run(  # noqa: S603 — operator-supplied flags
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return -1, "", f"timed out after {timeout}s"
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()


def _check_sinfo(timeout: float) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    if _which("sinfo") is None:
        findings.append(
            ValidationFinding(
                severity="error",
                code="SINFO_NOT_INSTALLED",
                message=(
                    "sinfo is not on PATH. Install Slurm client tools or "
                    "run jackpot doctor on the cluster head node."
                ),
            )
        )
        return findings
    rc, stdout, stderr = _run_with_timeout(["sinfo", "-h"], timeout=timeout)
    if rc != 0:
        findings.append(
            ValidationFinding(
                severity="error",
                code="SINFO_FAILED",
                message=(f"sinfo exited {rc}. stderr: {stderr or '(empty)'}"),
            )
        )
    elif not stdout:
        findings.append(
            ValidationFinding(
                severity="warning",
                code="SINFO_EMPTY",
                message="sinfo returned no rows; cluster has no partitions?",
            )
        )
    return findings


def _check_srun_workdir(
    work_dir: str,
    *,
    account: str | None,
    partition: str | None,
    timeout: float,
) -> list[ValidationFinding]:
    """Submit a tiny ``srun`` to confirm a compute node sees the
    work_dir at the same path the API server sees it. Uses
    ``stat -c '%n'`` on the work_dir as the test command — it succeeds
    cheaply and produces a single line of output that proves the
    compute node resolved the path."""
    if _which("srun") is None:
        return [
            ValidationFinding(
                severity="error",
                code="SRUN_NOT_INSTALLED",
                message="srun is not on PATH; cannot test work_dir reachability.",
            )
        ]
    cmd = ["srun", "--time=1"]
    if account:
        cmd.append(f"--account={account}")
    if partition:
        cmd.append(f"--partition={partition}")
    cmd += ["stat", "-c", "%n", work_dir]
    rc, stdout, stderr = _run_with_timeout(cmd, timeout=timeout)
    if rc == 0 and stdout.strip().endswith(work_dir.rstrip("/")):
        return []
    if rc == -1:
        return [
            ValidationFinding(
                severity="error",
                code="SRUN_TIMEOUT",
                message=(
                    f"srun did not return within {timeout}s; cluster may be "
                    "saturated or the partition unreachable."
                ),
            )
        ]
    if rc != 0:
        return [
            ValidationFinding(
                severity="error",
                code="SRUN_FAILED",
                message=(
                    f"srun stat exited {rc}. work_dir is probably not "
                    f"visible to compute nodes. stderr: {stderr or '(empty)'}"
                ),
            )
        ]
    # rc == 0 but stdout did not echo the work_dir — unusual, surface as
    # a warning rather than silent pass.
    return [
        ValidationFinding(
            severity="warning",
            code="SRUN_UNEXPECTED_OUTPUT",
            message=f"srun returned 0 but output was unexpected: {stdout!r}",
        )
    ]


@doctor.command("slurm")
@click.option(
    "--work-dir",
    required=True,
    help="The profile's work_dir; must be visible to API + compute nodes.",
)
@click.option(
    "--account",
    default=None,
    help="Slurm account for the cluster-side --check-cluster probe.",
)
@click.option(
    "--partition",
    default=None,
    help="Slurm partition for the cluster-side --check-cluster probe.",
)
@click.option(
    "--check-cluster",
    is_flag=True,
    default=False,
    help="Also run sinfo + a tiny srun to verify cluster reachability.",
)
@click.option(
    "--timeout",
    default=10.0,
    show_default=True,
    type=float,
    help="Per-subprocess timeout in seconds for sinfo/srun.",
)
def doctor_slurm(
    work_dir: str,
    account: str | None,
    partition: str | None,
    check_cluster: bool,
    timeout: float,
) -> None:
    """Validate a Slurm profile's work_dir + (optionally) cluster
    reachability.

    Without ``--check-cluster``, only the API-host filesystem is
    probed. With ``--check-cluster``, the command additionally runs
    ``sinfo`` (cluster up?) and ``srun stat <work_dir>`` (work_dir
    visible from a compute node?) using the supplied account /
    partition.

    Exit codes:
      0  no findings or info-only (cloud URIs short-circuit here)
      1  warnings only (the profile is usable but the operator should
         see the warnings)
      2  blocking errors (don't ship the profile until fixed)
    """
    local = validate_work_dir_locally(work_dir)
    _print_findings(local, context=f"work_dir={work_dir} (API host)")

    cluster: list[ValidationFinding] = []
    if check_cluster:
        cluster.extend(_check_sinfo(timeout))
        # Don't bother with srun if sinfo already failed — they share
        # a Slurm config and the second failure would just be noise.
        if not has_blocking_findings(cluster):
            cluster.extend(
                _check_srun_workdir(
                    work_dir,
                    account=account,
                    partition=partition,
                    timeout=timeout,
                )
            )
        _print_findings(cluster, context="cluster reachability")

    combined = local + cluster
    if has_blocking_findings(combined):
        raise SystemExit(2)
    if any(f.severity == "warning" for f in combined):
        raise SystemExit(1)
    raise SystemExit(0)
