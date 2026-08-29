"""Manifest-only (engine-less) launcher (B-BYOP-5d).

Implements the BYOP engine-launcher interface for manifest-wrapped
script pipelines (`docs/byop_and_eukaryotic_design.md` §3.4). Unlike
the Nextflow/Snakemake/WDL launchers there is no workflow engine —
the pipeline definition ships a pre-rendered command sequence (the
manifest) and this launcher runs those commands directly, in order,
with structured exit-code reporting. No engine binary is ever
invoked; the only subprocess use is executing the manifest's own
commands, which is exactly what §3.4 defines this engine to do.

The command sequence rides in :class:`ManifestLaunchSpec.commands`
(a ``LaunchSpec`` subclass — the shared launcher call shape stays
``launch(spec)`` so callers never branch on launcher type). Each
entry is one pre-rendered command string, split with :mod:`shlex`
and run without a shell. Execution stops at the first failing
command; failures surface as ``success=False`` results, never as
swallowed exceptions. A missing, empty, or malformed manifest raises
:class:`ManifestError` before any command runs.
"""

from __future__ import annotations

import shlex
import subprocess  # nosec B404 — fixed-argv manifest commands, no shell
from dataclasses import dataclass, field

from backend.services.launchers import LaunchResult, LaunchSpec


class ManifestError(ValueError):
    """Raised when the manifest command sequence is missing or malformed."""


@dataclass(frozen=True)
class ManifestLaunchSpec(LaunchSpec):
    """LaunchSpec carrying the pre-rendered manifest command sequence."""

    commands: list[str] = field(default_factory=list)


class ManifestLauncher:
    """Runs a manifest pipeline's command sequence, no engine involved."""

    engine_type = "manifest"

    def build_command(self, spec: LaunchSpec) -> list[str]:
        """Return the validated command sequence, in manifest order.

        For engine launchers this is one argv; for the engine-less
        manifest launcher the unit of execution is the whole sequence,
        so each list element is one pre-rendered command string.
        """
        commands = getattr(spec, "commands", None)
        if not commands:
            raise ManifestError(
                "manifest command sequence is missing or empty — "
                "manifest pipelines must supply at least one command"
            )
        for i, cmd in enumerate(commands):
            if not isinstance(cmd, str) or not cmd.strip():
                raise ManifestError(
                    f"manifest command {i} is malformed: expected a non-empty string, got {cmd!r}"
                )
            try:
                argv = shlex.split(cmd)
            except ValueError as exc:
                raise ManifestError(f"manifest command {i} is malformed: {exc}") from exc
            if not argv:
                raise ManifestError(f"manifest command {i} is malformed: parses to no argv")
        return list(commands)

    def launch(self, spec: LaunchSpec) -> LaunchResult:
        """Run the manifest commands in order, stopping at first failure.

        Non-zero exits and missing executables both surface as
        ``success=False`` results, never as swallowed exceptions.
        """
        commands = self.build_command(spec)
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        for i, cmd in enumerate(commands):
            argv = shlex.split(cmd)
            try:
                proc = subprocess.run(  # noqa: S603  # nosec B603
                    argv,
                    capture_output=True,
                    text=True,
                    check=False,
                    cwd=spec.work_dir,
                )
            except FileNotFoundError:
                return LaunchResult(
                    success=False,
                    exit_code=None,
                    stdout="".join(stdout_parts),
                    stderr="".join(stderr_parts),
                    error=f"manifest command {i}: executable not found: {argv[0]}",
                )
            stdout_parts.append(proc.stdout)
            stderr_parts.append(proc.stderr)
            if proc.returncode != 0:
                return LaunchResult(
                    success=False,
                    exit_code=proc.returncode,
                    stdout="".join(stdout_parts),
                    stderr="".join(stderr_parts),
                    error=f"manifest command {i} exited with code {proc.returncode}",
                )
        return LaunchResult(
            success=True,
            exit_code=0,
            stdout="".join(stdout_parts),
            stderr="".join(stderr_parts),
            error=None,
        )


launcher = ManifestLauncher()
