"""WDL engine launcher (B-BYOP-5c).

Implements the BYOP engine-launcher interface for WDL pipelines
(`docs/byop_and_eukaryotic_design.md` §3.3). The design doc supports
both Cromwell (heavyweight, full features) and miniwdl (lightweight,
simpler) as launcher backends, operator-selected via the
``JACKPOT_WDL_BACKEND`` env var:

- ``miniwdl`` (default) — ``miniwdl run <wdl> --input <inputs.json>
  --dir <work_dir>``. Pure-Python CLI, zero infrastructure; the same
  binary §5.3a already uses for the sandbox dry-run.
- ``cromwell`` — ``cromwell run <wdl> --inputs <inputs.json>``. No
  work-dir flag: Cromwell's execution root is server-side config, out
  of scope for this launcher.

WDL has no weblog mechanism — Cromwell's metadata API is polled and
miniwdl's structured logs are parsed (§3.3), so ``LaunchSpec`` fields
that are Nextflow-specific (``config_path``, ``profiles``,
``weblog_url``, ``resume``) are ignored here.
"""

from __future__ import annotations

# Engine choice: miniwdl is the default backend — the design doc assumes no
# Cromwell server ("miniwdl (lightweight, simpler)") and §5.3a's dry-run
# already standardises on the miniwdl CLI, which runs with zero infrastructure.
import os
import subprocess  # nosec B404 — fixed-argv WDL engine invocation, no shell

from backend.services.launchers import LaunchResult, LaunchSpec

WDL_BACKEND_ENV = "JACKPOT_WDL_BACKEND"
DEFAULT_WDL_BACKEND = "miniwdl"

__all__ = ["WdlLauncher"]


class WdlLauncher:
    """Runs a WDL pipeline synchronously via subprocess."""

    engine_type = "wdl"

    @staticmethod
    def _backend() -> str:
        backend = os.environ.get(WDL_BACKEND_ENV, DEFAULT_WDL_BACKEND).strip().lower()
        if backend not in ("miniwdl", "cromwell"):
            raise ValueError(f"{WDL_BACKEND_ENV} must be 'miniwdl' or 'cromwell', got {backend!r}")
        return backend

    def build_command(self, spec: LaunchSpec) -> list[str]:
        """Exact argv for the configured WDL engine from a :class:`LaunchSpec`.

        ``spec.pipeline_uri`` is the ``.wdl`` entrypoint path,
        ``spec.params_file`` the ``inputs.json`` populated from the
        manifest, ``spec.work_dir`` the JACKPOT-managed run directory.
        """
        if not spec.pipeline_uri or not spec.pipeline_uri.strip():
            raise ValueError("WDL entrypoint path (pipeline_uri) is required")
        if self._backend() == "cromwell":
            cmd = ["cromwell", "run", spec.pipeline_uri]
            if spec.params_file:
                cmd += ["--inputs", spec.params_file]
            return cmd
        cmd = ["miniwdl", "run", spec.pipeline_uri]
        if spec.params_file:
            cmd += ["--input", spec.params_file]
        cmd += ["--dir", spec.work_dir]
        return cmd

    def launch(self, spec: LaunchSpec) -> LaunchResult:
        """Run the WDL engine; non-zero exit and missing binary both
        surface as ``success=False`` results, never as swallowed
        exceptions. stderr is included in ``error`` on failure."""
        cmd = self.build_command(spec)
        binary = cmd[0]
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
                error=f"{binary} binary not found on PATH",
            )
        success = proc.returncode == 0
        error = None
        if not success:
            error = f"{binary} exited with code {proc.returncode}"
            if proc.stderr:
                error += f": {proc.stderr.strip()}"
        return LaunchResult(
            success=success,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            error=error,
        )


launcher = WdlLauncher()
