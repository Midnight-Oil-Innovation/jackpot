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

import click
from jackpot_scenarios.scenarios import SCENARIO_REGISTRY

from jackpot.init.detector import prompt_for_scenario


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
