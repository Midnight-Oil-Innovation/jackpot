"""Snakemake engine launcher (B-BYOP-5b).

Implements the BYOP engine-launcher interface for Snakemake pipelines
(`docs/byop_and_eukaryotic_design.md` §3.2). Mirrors the Nextflow
launcher's shape (B-BYOP-5a) but invokes ``snakemake``:

- ``--snakefile <uri>`` — the pipeline's ``Snakefile`` entry point
- ``--directory <work_dir>`` — JACKPOT-managed work directory
- ``--configfile <path>`` — the pipeline's ``config.yaml`` (§3.2:
  "Configuration is config.yaml")
- ``--rerun-incomplete --keep-going`` — resume, enabled by default
  per §3.2 ("Resume via --rerun-incomplete --keep-going")

Snakemake has no native weblog (§3.2) — ``spec.weblog_url`` is ignored
here; event emission is the wrapping poller's job, not the command
line's. ``spec.profiles`` and ``spec.params_file`` are Nextflow-shaped
fields the design doc does not name for Snakemake, so they are ignored
rather than mapped speculatively.
"""

from __future__ import annotations

import subprocess  # nosec B404 — fixed-argv snakemake invocation, no shell

from backend.services.launchers import LaunchResult, LaunchSpec

SNAKEMAKE_BINARY = "snakemake"


class SnakemakeLauncher:
    """Runs a Snakemake pipeline synchronously via subprocess."""

    engine_type = "snakemake"

    def build_command(self, spec: LaunchSpec) -> list[str]:
        """Exact argv for ``snakemake`` from a :class:`LaunchSpec`."""
        cmd = [SNAKEMAKE_BINARY, "--snakefile", spec.pipeline_uri]
        if spec.config_path:
            cmd += ["--configfile", spec.config_path]
        cmd += ["--directory", spec.work_dir]
        if spec.resume:
            cmd += ["--rerun-incomplete", "--keep-going"]
        return cmd

    def launch(self, spec: LaunchSpec) -> LaunchResult:
        """Run Snakemake; non-zero exit and missing binary both surface
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
                error=f"{SNAKEMAKE_BINARY} binary not found on PATH",
            )
        success = proc.returncode == 0
        return LaunchResult(
            success=success,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            error=None if success else f"snakemake exited with code {proc.returncode}",
        )


launcher = SnakemakeLauncher()
