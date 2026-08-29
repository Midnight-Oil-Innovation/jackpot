"""Nextflow engine launcher (B-BYOP-5a).

Hardens the existing Nextflow invocation path into a pluggable BYOP
launcher (`docs/byop_and_eukaryotic_design.md` §3.1). Per-run config
generation stays in ``backend.pipeline_config`` (Critical Rule 26) —
this module only builds and runs the ``nextflow run`` command line:

- ``-c <config_path>`` — the per-run rendered ``jackpot_run.config``
- ``-w <work_dir>`` — JACKPOT-managed work directory (Critical Rule 25)
- ``-resume`` — enabled by default per §3.1
- ``-profile a,b`` — comma-joined when profiles are given
- ``-params-file <path>`` — when a params file is given
- ``-with-weblog <url>`` — auto-injected weblog per §3.1 (the doc's
  "-weblog flag"; Nextflow's actual flag name is ``-with-weblog``),
  pointing at ``/api/v1/pipelines/events``
"""

from __future__ import annotations

import subprocess  # nosec B404 — fixed-argv nextflow invocation, no shell

from backend.services.launchers import LaunchResult, LaunchSpec

NEXTFLOW_BINARY = "nextflow"


class NextflowLauncher:
    """Runs a Nextflow pipeline synchronously via subprocess."""

    engine_type = "nextflow"

    def build_command(self, spec: LaunchSpec) -> list[str]:
        """Exact argv for ``nextflow run`` from a :class:`LaunchSpec`."""
        cmd = [NEXTFLOW_BINARY, "run", spec.pipeline_uri]
        if spec.config_path:
            cmd += ["-c", spec.config_path]
        cmd += ["-w", spec.work_dir]
        if spec.resume:
            cmd.append("-resume")
        if spec.profiles:
            cmd += ["-profile", ",".join(spec.profiles)]
        if spec.params_file:
            cmd += ["-params-file", spec.params_file]
        if spec.weblog_url:
            cmd += ["-with-weblog", spec.weblog_url]
        return cmd

    def launch(self, spec: LaunchSpec) -> LaunchResult:
        """Run Nextflow; non-zero exit and missing binary both surface
        as ``success=False`` results, never as swallowed exceptions."""
        cmd = self.build_command(spec)
        try:
            proc = subprocess.run(  # noqa: S603  # nosec B603
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return LaunchResult(
                success=False,
                exit_code=None,
                stdout="",
                stderr="",
                error=f"{NEXTFLOW_BINARY} binary not found on PATH",
            )
        success = proc.returncode == 0
        return LaunchResult(
            success=success,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            error=None if success else f"nextflow exited with code {proc.returncode}",
        )


launcher = NextflowLauncher()
