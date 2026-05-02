"""
jackpot.cli.init — `jackpot init` Click subcommand group.

This module defines the operator-facing CLI for the bootstrap flow.
Heavy lifting lives in `jackpot.init.*` modules (detector, writers,
secrets, validator). The CLI here is just the Click decorators +
flag parsing + orchestration.

Subcommand layout (see docs/architecture/jackpot-init-cli.md):

    jackpot init                 # default: detect → configure → bootstrap → validate
    jackpot init detect          # B-STLT-4: ask 5 questions, propose scenario
    jackpot init configure       # write instances/<name>/ files
    jackpot init bootstrap       # alembic upgrade head + apply seed.sql
    jackpot init validate        # /health smoke checks
    jackpot init reconfigure     # update existing instance
    jackpot init scenario-info   # print canonical defaults
"""

from __future__ import annotations

import json
from pathlib import Path

import click
from jackpot_scenarios.scenarios import SCENARIO_REGISTRY

from jackpot.init.detector import prompt_for_scenario
from jackpot.init.github_vars import (
    fetch_environment_variables,
    fetch_repo_variables,
    probe_gh,
)
from jackpot.init.writers import write_instance

# Map scenario codes to default instance-name suggestions. Operators
# override via --instance-name.
_DEFAULT_INSTANCE_NAME = {
    "A": "local",
    "B": "production",
    "C": "production",
    "D": "production",
    "E": "production",
    "F": "ci",
    "T": "tribal",
}

# Operator-identity fields the configure prompts ask for, in display
# order. Each maps to (env-var-name-in-github, prompt-label, default).
_OPERATOR_PROMPTS: tuple[tuple[str, str, str, str], ...] = (
    (
        "host_organization_name",
        "HOST_ORGANIZATION_NAME",
        "Your organisation's display name",
        "",
    ),
    (
        "host_organization_email",
        "HOST_ORGANIZATION_EMAIL",
        "Your contact email (audit-log attribution)",
        "",
    ),
    (
        "deployment_url",
        "JACKPOT_API_URL",
        "Public-facing API URL (e.g. https://api.jackpot.your-org.org)",
        "",
    ),
)


@click.group("init")
def init() -> None:
    """Bootstrap a JACKPOT instance for one of the 7 install scenarios."""


@init.command("detect")
@click.option(
    "--scenario",
    "scenario_code",
    type=str,
    default=None,
    help=(
        "Skip the detector questions and use this scenario directly " "(A | B | C | D | E | F | T)."
    ),
)
@click.option(
    "--non-interactive",
    is_flag=True,
    default=False,
    help=("Fail rather than prompt. Requires --scenario. Used by CI runners " "and shell scripts."),
)
def detect_cmd(scenario_code: str | None, non_interactive: bool) -> None:
    """Run the scenario detector. Prints the chosen scenario + rationale.

    No files are written. This is the planning step; pair with
    `jackpot init configure` to actually generate config.
    """
    result = prompt_for_scenario(
        explicit_code=scenario_code,
        non_interactive=non_interactive,
    )

    click.echo()
    click.secho("Selected scenario:", bold=True)
    click.echo(f"  Code:        {result.scenario.code}")
    click.echo(f"  Name:        {result.scenario.name}")
    click.echo(f"  Description: {result.scenario.description}")
    if result.detection is not None:
        click.echo()
        click.secho("Detector rationale:", bold=True)
        click.echo(f"  {result.detection.rationale}")
    if result.overridden:
        click.echo()
        click.secho("Note: operator overrode the detector's proposal.", fg="yellow")
    click.echo()
    click.echo(
        "Next: `jackpot init configure --scenario "
        f"{result.scenario.code}` to write instance config."
    )


@init.command("scenario-info")
@click.argument("code", required=True)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit machine-readable JSON (used by CI and tooling).",
)
def scenario_info_cmd(code: str, as_json: bool) -> None:
    """Print the canonical defaults for a named scenario.

    Used by humans (`jackpot init scenario-info T`) and by tooling
    (`jackpot init scenario-info T --json | jq '.defaults.deletion_on_request'`).
    """
    code_upper = code.strip().upper()
    if code_upper not in SCENARIO_REGISTRY:
        raise click.UsageError(
            f"Unknown scenario {code!r}. " f"Valid: {', '.join(sorted(SCENARIO_REGISTRY))}"
        )

    scenario = SCENARIO_REGISTRY[code_upper]  # type: ignore[index]

    if as_json:
        payload = {
            "code": scenario.code,
            "name": scenario.name,
            "description": scenario.description,
            "defaults": scenario.defaults.model_dump(),
        }
        click.echo(json.dumps(payload, indent=2, default=str))
        return

    click.secho(
        f"\nScenario {scenario.code} — {scenario.name}",
        bold=True,
    )
    click.echo()
    click.echo(f"  {scenario.description}")
    click.echo()
    click.secho("Defaults:", bold=True)
    for field, value in scenario.defaults.model_dump().items():
        click.echo(f"  {field:38s} = {value!r}")


def _gather_operator_overrides(
    *,
    scenario_code: str,
    instance_name: str,
    non_interactive: bool,
    use_gh_vars: bool,
) -> dict[str, object]:
    """Prompt the operator for identity values; if `gh` is available
    and `use_gh_vars=True`, present GitHub repo/env vars as defaults
    that the operator confirms or overrides.

    For Scenario F (CI) and `--non-interactive` runs, returns an empty
    dict — the scenario's hardcoded synthetic identity values become
    the runtime values without further prompting.
    """
    if scenario_code == "F" or non_interactive:
        return {}

    gh_values: dict[str, str] = {}
    if use_gh_vars:
        probe = probe_gh()
        if probe.available and probe.repo_slug:
            click.echo(click.style(f"  GitHub probe: {probe.detail}", fg="cyan"))
            # Repo-level vars first; then environment-scoped overrides.
            gh_values.update(fetch_repo_variables(probe.repo_slug))
            # Best-effort: environments named 'staging' / 'production'
            # mirror the typical operator setup.
            for env_name in ("staging", "production"):
                gh_values.update(fetch_environment_variables(probe.repo_slug, env_name))
        elif probe.available:
            click.echo(
                click.style(
                    f"  GitHub probe: {probe.detail} — skipping vars import",
                    fg="cyan",
                )
            )

    overrides: dict[str, object] = {}
    click.echo()
    click.secho("Operator identity prompts:", bold=True)
    for field_name, gh_var_name, label, fallback in _OPERATOR_PROMPTS:
        gh_value = gh_values.get(gh_var_name)
        if gh_value:
            click.echo(
                f"  Found in GitHub vars ({gh_var_name}): " f"{click.style(gh_value, fg='green')}"
            )
            if click.confirm(f"  Use this for {field_name}?", default=True):
                overrides[field_name] = gh_value
                continue
        typed = click.prompt(
            f"  {label}",
            default=fallback,
            show_default=bool(fallback),
            type=str,
        )
        if typed:
            overrides[field_name] = typed

    # CORS origins are derived from the deployment URL by default —
    # operators commonly want one entry, the same hostname their UI lives at.
    deployment_url = overrides.get("deployment_url")
    if deployment_url:
        derived_cors = str(deployment_url).rstrip("/")
        click.echo()
        click.echo(f"  Derived CORS origin from deployment URL: {derived_cors}")
        if click.confirm("  Use this single-origin CORS allowlist?", default=True):
            overrides["cors_origins"] = [derived_cors]
        else:
            cors_raw = click.prompt(
                "  Comma-separated CORS origins",
                default="",
                show_default=False,
                type=str,
            )
            if cors_raw:
                overrides["cors_origins"] = [o.strip() for o in cors_raw.split(",") if o.strip()]

    return overrides


@init.command("configure")
@click.option(
    "--scenario",
    "scenario_code",
    type=str,
    required=True,
    help="Scenario code (A | B | C | D | E | F | T). Use `jackpot init detect` first if unsure.",
)
@click.option(
    "--instance-name",
    "instance_name",
    type=str,
    default=None,
    help=(
        "Per-instance directory name. Defaults to a scenario-appropriate "
        "name (local / production / ci / tribal / etc.)."
    ),
)
@click.option(
    "--instances-dir",
    "instances_dir_str",
    type=str,
    default="instances",
    help="Parent directory for per-instance configs (default: instances/ at repo root).",
)
@click.option(
    "--no-gh",
    is_flag=True,
    default=False,
    help="Skip the GitHub-vars detect-and-confirm hybrid even if `gh` is available.",
)
@click.option(
    "--non-interactive",
    is_flag=True,
    default=False,
    help="Use scenario defaults without prompting. CI/scripted use.",
)
@click.option(
    "--no-overwrite-non-secrets",
    is_flag=True,
    default=False,
    help="Preserve existing files (used by `reconfigure` to avoid clobbering operator edits).",
)
def configure_cmd(
    scenario_code: str,
    instance_name: str | None,
    instances_dir_str: str,
    no_gh: bool,
    non_interactive: bool,
    no_overwrite_non_secrets: bool,
) -> None:
    """Generate per-instance config files for a scenario.

    Writes:
      instances/<name>/jackpot.toml
      instances/<name>/.env.local
      instances/<name>/values.local.yaml
      instances/<name>/seed.sql
      instances/<name>/README.md
      instances/<name>/secrets/   (empty; populated by `jackpot init secrets`)

    No DB changes; no `docker compose up`. Use `jackpot init bootstrap`
    after this completes to apply the generated config.
    """
    scenario_code_upper = scenario_code.strip().upper()
    if scenario_code_upper not in SCENARIO_REGISTRY:
        raise click.UsageError(
            f"Unknown --scenario {scenario_code!r}. "
            f"Valid: {', '.join(sorted(SCENARIO_REGISTRY))}"
        )
    scenario = SCENARIO_REGISTRY[scenario_code_upper]  # type: ignore[index]

    resolved_instance_name = instance_name or _DEFAULT_INSTANCE_NAME[scenario_code_upper]

    # Critical Rule 56: the committed instances/ci/ directory must NOT
    # be overwritten by jackpot init. Developers reproducing CI locally
    # use a different name (e.g. ci-local).
    if resolved_instance_name == "ci" and scenario.code == "F":
        raise click.UsageError(
            "Refusing to overwrite committed instances/ci/ "
            "(Critical Rule 56). Use --instance-name ci-local "
            "or any other name for local CI reproduction."
        )

    instance_dir = Path(instances_dir_str) / resolved_instance_name

    click.echo()
    click.secho(
        f"Configuring scenario {scenario.code} ({scenario.name}) "
        f"as instance {resolved_instance_name!r}",
        bold=True,
    )
    click.echo(f"  Output directory: {instance_dir}")
    click.echo()

    overrides = _gather_operator_overrides(
        scenario_code=scenario.code,
        instance_name=resolved_instance_name,
        non_interactive=non_interactive,
        use_gh_vars=not no_gh,
    )

    written = write_instance(
        scenario=scenario,
        operator_overrides=overrides,
        instance_dir=instance_dir,
        overwrite_non_secrets=not no_overwrite_non_secrets,
    )

    click.echo()
    click.secho("Wrote / preserved files:", bold=True)
    for filename, was_written in written.items():
        status = "wrote" if was_written else "preserved"
        click.echo(f"  [{status:9s}] {instance_dir / filename}")

    click.echo()
    click.echo(
        "Next: `jackpot init secrets --instance "
        f"{resolved_instance_name}` to generate JWT signing key + "
        "(if applicable) federation keypair."
    )
