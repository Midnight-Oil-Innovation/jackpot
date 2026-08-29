"""BYOP engine-launcher interface (B-BYOP-5).

One launcher per engine type (`docs/byop_and_eukaryotic_design.md` §3):
nextflow (5a), snakemake (5b), wdl (5c), manifest (5d). Each launcher
module exposes a module-level ``launcher`` instance implementing
:class:`EngineLauncher`; the launch dispatch selects by ``engine_type``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class LaunchSpec:
    """Engine-agnostic launch inputs.

    Fields mirror what the design doc names for Nextflow (§3.1):
    pipeline URI, per-run rendered config (Critical Rule 26), profiles,
    params file, JACKPOT-managed work directory, auto-injected weblog
    URL, and resume-on-by-default.
    """

    pipeline_uri: str
    work_dir: str
    config_path: str | None = None
    profiles: list[str] = field(default_factory=list)
    params_file: str | None = None
    weblog_url: str | None = None
    resume: bool = True


@dataclass(frozen=True)
class LaunchResult:
    """Outcome of one engine invocation.

    ``exit_code`` is ``None`` when the engine binary could not be
    executed at all (e.g. not on PATH). Non-zero exits set
    ``success=False`` and populate ``error`` — failures are never
    silently swallowed.
    """

    success: bool
    exit_code: int | None
    stdout: str
    stderr: str
    error: str | None = None


@runtime_checkable
class EngineLauncher(Protocol):
    """Contract every engine launcher implements."""

    engine_type: str

    def build_command(self, spec: LaunchSpec) -> list[str]:
        """Return the exact argv the launcher will execute."""
        ...

    def launch(self, spec: LaunchSpec) -> LaunchResult:
        """Run the engine synchronously and report the outcome."""
        ...
