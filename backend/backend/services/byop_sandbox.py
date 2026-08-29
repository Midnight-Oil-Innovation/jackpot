"""BYOP Stage 2 sandbox dry-run.

Implements `docs/byop_and_eukaryotic_design.md` §5.3 ("Stage 2 — sandbox
dry-run"). Runs after Stage 1 (`byop_validator.py`) passes. The candidate
manifest is exercised under an isolated substrate — a dedicated Kubernetes
namespace (``jackpot-byop-sandbox-<pipeline-id>``) on cloud deployments or a
dedicated Docker network (``jackpot-byop-<pipeline-id>``) on laptop/local
deployments (§5.3b) — and three runtime checks are performed that static
validation cannot cover:

1. the declared container image actually pulls,
2. the engine binary executes its per-engine dry-run command (§5.3a),
3. the synthetic test inputs in ``backend/test_data/byop_sandbox/`` bind
   into the sandbox correctly (§5.3c).

As in Stage 1, failures are values, not exceptions: each step returns a
`StepResult` and `run_sandbox` aggregates them into a `SandboxResult` whose
outcome mirrors §5.3e / §6 — pass, ``SANDBOX_FAILED``, or
``SANDBOX_TIMEOUT``. The captured ``sandbox_log`` is truncated to 10 KB
(§5.3e). The isolation substrate is always torn down, even when a mid-run
step fails.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "StepResult",
    "SandboxResult",
    "create_isolation",
    "teardown_isolation",
    "check_container_pull",
    "check_engine_dry_run",
    "check_reference_data_bind",
    "run_sandbox",
]

# §5.3b — isolation substrate naming patterns.
K8S_NAMESPACE_TEMPLATE = "jackpot-byop-sandbox-{pipeline_id}"
DOCKER_NETWORK_TEMPLATE = "jackpot-byop-{pipeline_id}"

# §5.3b — 5-minute hard wall-clock timeout, operator-configurable.
DEFAULT_TIMEOUT_SECONDS = 300
TIMEOUT_ENV_VAR = "JACKPOT_BYOP_SANDBOX_TIMEOUT_SECONDS"

# §5.3b — resource caps: the dry-run isn't supposed to do real work.
SANDBOX_CPU_LIMIT = "2"
SANDBOX_MEMORY_LIMIT = "4g"

# §5.3e — sandbox stdout/stderr truncated to 10 KB in the structured error.
SANDBOX_LOG_MAX_BYTES = 10 * 1024

# §5.3c — synthetic test inputs mounted into the dry-run sandbox.
TEST_DATA_DIR = Path("backend/test_data/byop_sandbox")

# §5.3a — dry-run mechanic per engine.
ENGINE_DRY_RUN_COMMANDS: dict[str, list[str]] = {
    "nextflow": [
        "nextflow",
        "run",
        "{entrypoint}",
        "-profile",
        "test",
        "--outdir",
        "{sandbox}",
        "-stub-run",
    ],
    "snakemake": [
        "snakemake",
        "--use-conda",
        "--use-singularity",
        "-n",
        "--cores",
        "1",
        "--config",
        "{test_inputs}",
    ],
    "wdl": [
        "miniwdl",
        "run",
        "--dir",
        "{sandbox}",
        "--input",
        "test_inputs.json",
        "--task-only-resources",
        "{entrypoint}",
    ],
    # Manifest-wrapped scripts run with JACKPOT_DRY_RUN=1 set; a 60-second
    # hard timeout applies as fallback if the script does not honor it.
    "manifest": ["{entrypoint}"],
}
MANIFEST_FALLBACK_TIMEOUT_SECONDS = 60

# §6 — Stage 2 terminal outcomes.
OUTCOME_PASSED = "SANDBOX_PASSED"
OUTCOME_FAILED = "SANDBOX_FAILED"
OUTCOME_TIMEOUT = "SANDBOX_TIMEOUT"


@dataclass
class StepResult:
    """Outcome of a single Stage 2 dry-run step."""

    step_name: str
    passed: bool
    message: str
    log: str = ""


@dataclass
class SandboxResult:
    """Aggregate Stage 2 outcome for one pipeline (§5.3e)."""

    pipeline_id: str
    outcome: str
    steps: list[StepResult] = field(default_factory=list)
    sandbox_log: str = ""


def sandbox_timeout_seconds() -> int:
    """Operator timeout from JACKPOT_BYOP_SANDBOX_TIMEOUT_SECONDS (§5.3b)."""
    raw = os.environ.get(TIMEOUT_ENV_VAR, "")
    try:
        return int(raw) if raw else DEFAULT_TIMEOUT_SECONDS
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def _truncate_log(text: str) -> str:
    """Truncate captured sandbox output to 10 KB (§5.3e)."""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= SANDBOX_LOG_MAX_BYTES:
        return text
    return encoded[:SANDBOX_LOG_MAX_BYTES].decode("utf-8", errors="replace")


def _run(cmd: list[str], timeout: int, env: dict[str, str] | None = None):
    """Shared subprocess wrapper — captures combined output, never raises
    on non-zero exit (`subprocess.TimeoutExpired` propagates to callers,
    which classify it as SANDBOX_TIMEOUT)."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        check=False,
    )


def create_isolation(pipeline_id: str, isolation: str, timeout: int) -> StepResult:
    """Create the isolation substrate (§5.3b).

    `isolation` is ``"kubernetes"`` (cloud) or ``"docker"`` (laptop/local).
    """
    if isolation == "kubernetes":
        name = K8S_NAMESPACE_TEMPLATE.format(pipeline_id=pipeline_id)
        cmd = ["kubectl", "create", "namespace", name]
    elif isolation == "docker":
        name = DOCKER_NETWORK_TEMPLATE.format(pipeline_id=pipeline_id)
        cmd = ["docker", "network", "create", "--internal", name]
    else:
        return StepResult(
            step_name="isolation_setup",
            passed=False,
            message=f"Unknown isolation substrate: {isolation!r} "
            "(expected 'kubernetes' or 'docker').",
        )
    proc = _run(cmd, timeout)
    if proc.returncode != 0:
        return StepResult(
            step_name="isolation_setup",
            passed=False,
            message=f"Failed to create {isolation} isolation {name!r}.",
            log=_truncate_log(proc.stdout + proc.stderr),
        )
    return StepResult(
        step_name="isolation_setup",
        passed=True,
        message=f"Created {isolation} isolation {name!r}.",
        log=_truncate_log(proc.stdout + proc.stderr),
    )


def teardown_isolation(pipeline_id: str, isolation: str, timeout: int) -> StepResult:
    """Tear down the isolation substrate. Always safe to call — a failed
    teardown is reported, never raised."""
    if isolation == "kubernetes":
        name = K8S_NAMESPACE_TEMPLATE.format(pipeline_id=pipeline_id)
        cmd = ["kubectl", "delete", "namespace", name, "--ignore-not-found"]
    else:
        name = DOCKER_NETWORK_TEMPLATE.format(pipeline_id=pipeline_id)
        cmd = ["docker", "network", "rm", name]
    try:
        proc = _run(cmd, timeout)
    except subprocess.TimeoutExpired:
        return StepResult(
            step_name="isolation_teardown",
            passed=False,
            message=f"Timed out tearing down {isolation} isolation {name!r}.",
        )
    return StepResult(
        step_name="isolation_teardown",
        passed=proc.returncode == 0,
        message=(
            f"Removed {isolation} isolation {name!r}."
            if proc.returncode == 0
            else f"Failed to remove {isolation} isolation {name!r}."
        ),
        log=_truncate_log(proc.stdout + proc.stderr),
    )


def _flag_like(value: str) -> bool:
    """True when a manifest-supplied value could smuggle an argv flag into
    a docker/kubectl command line (argument injection guard)."""
    return value.startswith("-")


def check_container_pull(image: str, timeout: int) -> StepResult:
    """Dry-run step 1 — the declared container image actually pulls."""
    if _flag_like(image):
        return StepResult(
            step_name="container_pull",
            passed=False,
            message=f"Rejected flag-like container image reference {image!r}.",
        )
    proc = _run(["docker", "pull", image], timeout)
    if proc.returncode != 0:
        return StepResult(
            step_name="container_pull",
            passed=False,
            message=f"Container image {image!r} could not be pulled.",
            log=_truncate_log(proc.stdout + proc.stderr),
        )
    return StepResult(
        step_name="container_pull",
        passed=True,
        message=f"Container image {image!r} pulled.",
        log=_truncate_log(proc.stdout + proc.stderr),
    )


def check_engine_dry_run(
    pipeline_id: str,
    image: str,
    engine_type: str,
    entrypoint: str,
    sandbox_dir: str,
    timeout: int,
) -> StepResult:
    """Dry-run step 2 — the engine binary executes its §5.3a dry-run command
    inside the pulled container, on the sandbox Docker network, under the
    §5.3b resource caps."""
    template = ENGINE_DRY_RUN_COMMANDS.get(engine_type)
    if template is None:
        return StepResult(
            step_name="engine_dry_run",
            passed=False,
            message=f"Unknown engine type: {engine_type!r}.",
        )
    if _flag_like(image) or _flag_like(entrypoint):
        return StepResult(
            step_name="engine_dry_run",
            passed=False,
            message="Rejected flag-like image or entrypoint value "
            f"(image={image!r}, entrypoint={entrypoint!r}).",
        )
    engine_cmd = [
        part.format(entrypoint=entrypoint, sandbox=sandbox_dir, test_inputs=sandbox_dir)
        for part in template
    ]
    network = DOCKER_NETWORK_TEMPLATE.format(pipeline_id=pipeline_id)
    cmd = [
        "docker",
        "run",
        "--rm",
        "--network",
        network,
        "--cpus",
        SANDBOX_CPU_LIMIT,
        "--memory",
        SANDBOX_MEMORY_LIMIT,
    ]
    effective_timeout = timeout
    if engine_type == "manifest":
        # §5.3a — script runs with JACKPOT_DRY_RUN=1; 60s fallback timeout.
        cmd += ["--env", "JACKPOT_DRY_RUN=1"]
        effective_timeout = min(timeout, MANIFEST_FALLBACK_TIMEOUT_SECONDS)
    cmd += [image, *engine_cmd]
    proc = _run(cmd, effective_timeout)
    if proc.returncode != 0:
        return StepResult(
            step_name="engine_dry_run",
            passed=False,
            message=f"Engine {engine_type!r} dry-run exited "
            f"{proc.returncode} (§5.3d requires exit code 0).",
            log=_truncate_log(proc.stdout + proc.stderr),
        )
    return StepResult(
        step_name="engine_dry_run",
        passed=True,
        message=f"Engine {engine_type!r} dry-run exited 0.",
        log=_truncate_log(proc.stdout + proc.stderr),
    )


def check_reference_data_bind(pipeline_id: str, image: str, timeout: int) -> StepResult:
    """Dry-run step 3 — the §5.3c synthetic test inputs mount into the
    sandbox and are readable from inside the container."""
    if _flag_like(image):
        return StepResult(
            step_name="reference_data_bind",
            passed=False,
            message=f"Rejected flag-like container image reference {image!r}.",
        )
    network = DOCKER_NETWORK_TEMPLATE.format(pipeline_id=pipeline_id)
    mount = f"{TEST_DATA_DIR.resolve()}:/jackpot/test_data:ro"
    proc = _run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            network,
            "--volume",
            mount,
            image,
            "ls",
            "/jackpot/test_data",
        ],
        timeout,
    )
    if proc.returncode != 0:
        return StepResult(
            step_name="reference_data_bind",
            passed=False,
            message="Test input mount did not bind or is not readable inside the container.",
            log=_truncate_log(proc.stdout + proc.stderr),
        )
    return StepResult(
        step_name="reference_data_bind",
        passed=True,
        message="Test inputs bound and readable inside the container.",
        log=_truncate_log(proc.stdout + proc.stderr),
    )


def run_sandbox(
    pipeline_id: str,
    image: str,
    engine_type: str,
    entrypoint: str,
    sandbox_dir: str,
    isolation: str = "docker",
    timeout: int | None = None,
) -> SandboxResult:
    """Stage 2 entry point (§5.3): run the full sandbox dry-run.

    Never raises on soft failures — a failed step, an isolation-setup
    failure, or a wall-clock timeout all come back as a `SandboxResult`
    with outcome ``SANDBOX_FAILED`` or ``SANDBOX_TIMEOUT`` (§5.3e / §6).
    The isolation substrate is torn down even when a mid-run step fails.
    """
    effective_timeout = timeout if timeout is not None else sandbox_timeout_seconds()
    steps: list[StepResult] = []

    setup = create_isolation(pipeline_id, isolation, effective_timeout)
    steps.append(setup)
    if not setup.passed:
        return SandboxResult(
            pipeline_id=pipeline_id,
            outcome=OUTCOME_FAILED,
            steps=steps,
            sandbox_log=_truncate_log(setup.log),
        )

    outcome = OUTCOME_PASSED
    try:
        for step_fn in (
            lambda: check_container_pull(image, effective_timeout),
            lambda: check_engine_dry_run(
                pipeline_id,
                image,
                engine_type,
                entrypoint,
                sandbox_dir,
                effective_timeout,
            ),
            lambda: check_reference_data_bind(pipeline_id, image, effective_timeout),
        ):
            step = step_fn()
            steps.append(step)
            if not step.passed:
                outcome = OUTCOME_FAILED
                break
    except subprocess.TimeoutExpired:
        outcome = OUTCOME_TIMEOUT
        steps.append(
            StepResult(
                step_name="timeout",
                passed=False,
                message=f"Sandbox exceeded the {effective_timeout}s "
                f"operator timeout ({TIMEOUT_ENV_VAR}).",
            )
        )
    finally:
        steps.append(teardown_isolation(pipeline_id, isolation, effective_timeout))

    return SandboxResult(
        pipeline_id=pipeline_id,
        outcome=outcome,
        steps=steps,
        sandbox_log=_truncate_log("\n".join(s.log for s in steps if s.log)),
    )
