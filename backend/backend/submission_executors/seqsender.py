# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Seqsender subprocess executor for backend submissions.

This module wraps CDCgov/seqsender (https://github.com/CDCgov/seqsender)
as an async subprocess. Seqsender is not on PyPI; it ships as a Python
script with a shell wrapper (``seqsender-kickoff``). The api Dockerfile
clones it to ``/opt/seqsender``; ``Settings.seqsender_binary_path`` lets
operators override.

The CLI shape used here (verified against upstream README):

    seqsender-kickoff submit \\
        --submission_dir <package_dir> \\
        --config_file    <credential-injected-yaml> \\
        --submission_name <stable-name> \\
        --biosample --sra --genbank \\
        [--test]

Exit codes: 0 = success; 1 = any failure. stdout = progress; stderr =
``Error: ...`` lines.

ENA / Webin is NOT supported by Seqsender. The :func:`write_seqsender_config`
helper raises ``ValueError`` for non-NCBI repos so the executor cannot
silently dispatch ENA submissions to a tool that can't process them.
The lifecycle gate in :func:`backend.jobs.execute_submission` rejects
ENA earlier with a user-facing error message.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from backend.credentials import credentials


@dataclass
class SeqsenderRunResult:
    """Outcome of a single Seqsender subprocess invocation."""

    exit_code: int
    stdout_bytes: bytes
    stderr_bytes: bytes
    wall_time_seconds: float
    timed_out: bool
    invocation_command: list[str] = field(default_factory=list)


# ── config generation ─────────────────────────────────────────────────


def write_seqsender_config(
    *,
    submission_id: int,
    target_repo: str,
    spuid_namespace: str = "jackpot",
) -> tuple[Path, list[str]]:
    """Write a credential-bearing Seqsender config to a private temp file.

    Returns ``(config_path, credential_values)``.

    The path is in the system temp directory (NOT inside the package or
    working directory) so neither Seqsender's stdout / stderr nor a
    routine working-dir tarball captures it. The file is mode 0600.

    The caller is responsible for deleting the file in a ``finally``
    block. ``credential_values`` is the list of credential string values
    injected into the YAML; the caller passes it to
    :mod:`backend.submission_executors.redaction` before writing the log.

    Raises:
        ValueError: ``target_repo`` is not ``"NCBI"``. Seqsender does
            not support ENA / DDBJ / GISAID-without-extra-tooling, so
            we refuse here rather than emitting an unrunnable config.
        backend.credentials.CredentialNotFoundError: a required
            credential is missing.
    """
    if target_repo.upper() != "NCBI":
        raise ValueError(
            f"Backend execution via Seqsender is only implemented for NCBI; "
            f"got target_repo={target_repo!r}."
        )

    username = credentials.get("ncbi_submission_username")
    password = credentials.get("ncbi_submission_password")
    config_data = {
        # Schema verified against CDCgov/seqsender test_data configs.
        "Submission": {
            "NCBI": {
                "Username": username,
                "Password": password,
                "Spuid_Namespace": spuid_namespace,
            },
        },
    }
    credential_values = [username, password]

    fd, path = tempfile.mkstemp(suffix=".yaml", prefix=f"seqsender_config_{submission_id}_")
    try:
        os.write(fd, yaml.safe_dump(config_data).encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(path, 0o600)

    return Path(path), credential_values


# ── subprocess wrapper ────────────────────────────────────────────────


def _build_invocation_command(
    *,
    binary_path: str,
    submission_dir: Path,
    config_path: Path,
    submission_name: str,
    test_mode: bool,
) -> list[str]:
    """Construct the Seqsender argv. Pure function — no I/O."""
    cmd = [
        binary_path,
        "submit",
        "--submission_dir",
        str(submission_dir),
        "--config_file",
        str(config_path),
        "--submission_name",
        submission_name,
        # NCBI sub-databases. The config file controls which are populated;
        # passing all three flags lets Seqsender dispatch to whichever the
        # package contains. The submission package generator (I-2) writes
        # biosample.tsv + sra.tsv for NCBI targets.
        "--biosample",
        "--sra",
        "--genbank",
    ]
    if test_mode:
        # Routes to NCBI's FTP test area instead of production.
        cmd.append("--test")
    return cmd


async def run_seqsender(
    *,
    working_dir: Path,
    config_path: Path,
    package_dir: Path,
    target_repo: str,
    binary_path: str,
    timeout_seconds: int,
    test_mode: bool = False,
    submission_name: str | None = None,
) -> SeqsenderRunResult:
    """Spawn Seqsender as an async subprocess. Capture stdout/stderr.

    The subprocess's CWD is ``working_dir`` so any artefacts Seqsender
    writes for non-config purposes land inside the per-execution scratch
    space (preserved on failure for diagnostics, deleted on success).

    On timeout, kills the process and returns ``timed_out=True`` with
    whatever output was captured before the kill.

    Does NOT redact, write logs, or transition state — that is the
    job-function's responsibility. Keeping this pure makes it easy to
    test in isolation.
    """
    if target_repo.upper() != "NCBI":
        raise ValueError(
            f"run_seqsender invoked with non-NCBI target_repo={target_repo!r}. "
            f"The execute_submission gate should have rejected this earlier."
        )
    cmd = _build_invocation_command(
        binary_path=binary_path,
        submission_dir=package_dir,
        config_path=config_path,
        submission_name=submission_name or f"jackpot-{int(time.time())}",
        test_mode=test_mode,
    )

    started = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(working_dir),
    )

    timed_out = False
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_seconds
        )
        exit_code = proc.returncode if proc.returncode is not None else -1
    except TimeoutError:
        timed_out = True
        proc.kill()
        # Drain pipes after the kill so we don't lose buffered output.
        try:
            stdout_bytes, stderr_bytes = await proc.communicate()
        except Exception:
            stdout_bytes = b""
            stderr_bytes = b""
        exit_code = proc.returncode if proc.returncode is not None else -1

    wall_time = time.monotonic() - started
    return SeqsenderRunResult(
        exit_code=exit_code,
        stdout_bytes=stdout_bytes,
        stderr_bytes=stderr_bytes,
        wall_time_seconds=wall_time,
        timed_out=timed_out,
        invocation_command=list(cmd),
    )


# ── log assembly ──────────────────────────────────────────────────────


def redact_command_for_logging(command: list[str], config_path: Path) -> list[str]:
    """Replace the credential-bearing config path in the logged invocation
    with the literal string ``<credential-config-redacted>``. All other
    argv entries pass through unchanged."""
    target = str(config_path)
    return ["<credential-config-redacted>" if arg == target else arg for arg in command]


def build_execution_log(
    *,
    submission_id: int,
    attempt: int,
    target_repo: str,
    executor_backend: str,
    invocation_command: list[str],
    working_dir: Path,
    config_path: Path,
    queued_at: datetime | None,
    started_at: datetime,
    completed_at: datetime,
    exit_code: int,
    timed_out: bool,
    wall_time_seconds: float,
    stdout_redacted: str,
    stderr_redacted: str,
) -> bytes:
    """Compose the structured log file content. UTF-8 bytes."""
    redacted_command = redact_command_for_logging(invocation_command, config_path)
    queued_iso = queued_at.isoformat() if queued_at is not None else "(unknown)"
    parts = [
        "═══ JACKPOT execution log ═══",
        f"Submission ID:      {submission_id}",
        f"Attempt:            {attempt}",
        f"Target repository:  {target_repo}",
        f"Executor backend:   {executor_backend}",
        f"Invocation:         {' '.join(redacted_command)}",
        f"Working directory:  {working_dir}",
        f"Config file:        {config_path} (deleted after run)",
        f"Queued at:          {queued_iso}",
        f"Started at:         {started_at.isoformat()}",
        f"Completed at:       {completed_at.isoformat()}",
        "",
        "═══ stdout ═══",
        stdout_redacted,
        "",
        "═══ stderr ═══",
        stderr_redacted,
        "",
        "═══ footer ═══",
        f"Exit code:          {exit_code}",
        f"Timed out:          {timed_out}",
        f"Wall time (s):      {wall_time_seconds:.2f}",
    ]
    return "\n".join(parts).encode("utf-8")
