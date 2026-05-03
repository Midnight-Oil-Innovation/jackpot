"""
Click-prompts wrapper around `jackpot_scenarios.detector`.

The pure inference logic lives in `schema/jackpot_scenarios/detector.py`
(reusable, testable without Click). This module provides the operator-
facing UX: 5 prompts (operator type / target / federation / PII / auth),
then a confirm step on the inferred scenario.
"""

from __future__ import annotations

from dataclasses import dataclass

import click
from jackpot_scenarios.detector import (
    DetectionResult,
    DetectorAnswers,
    infer_scenario,
)
from jackpot_scenarios.scenarios import SCENARIO_REGISTRY, Scenario, ScenarioCode


@dataclass(frozen=True)
class PromptResult:
    """What `prompt_for_scenario` returns: the chosen scenario plus a
    record of how the operator got there (auto-inferred vs explicit
    --scenario flag vs operator-overridden the inferred answer)."""

    scenario: Scenario
    detection: DetectionResult | None  # None when --scenario flag short-circuits
    overridden: bool  # True when operator chose a different code than detector inferred


_OPERATOR_TYPE_PROMPT = """\

Question 1 — Operator type
  [a] Academic researcher / single bioinformatician
  [b] Single public-health organization (no federation, no SaaS)
  [c] Multi-lab agency (state health department, city public health)
  [d] Hosted SaaS provider serving multiple tenants
  [e] Federation member (peers with other JACKPOT instances)
  [f] CI / automated test environment
  [t] Tribal nation, Tribal Epidemiology Center, or Indigenous-data-
      sovereignty deployment
"""

_TARGET_PROMPT = """\

Question 2 — Deployment target
  [1] Laptop / on-prem (Docker Compose; no cloud)
  [2] Cloud single-org (GCP/AWS/Azure managed)
  [3] Cloud multi-tenant (Kubernetes-native, multi-region)
"""

_FEDERATION_PROMPT = """\

Question 3 — Federation participation
  [n] Off — this instance does not peer with others
  [m] Member — receives data from peers; may push data to peers
  [h] Hub — coordinates a federation; routes between members
"""

_PII_PROMPT = """\

Question 4 — PII handling defaults
  [d] Full DLP — Cloud DLP scanner runs on every metadata write
  [s] Scrubber-only — strip identifiers at ingest, no DLP scanning
  [o] Off — operator certifies they do not handle PII
"""

_AUTH_PROMPT = """\

Question 5 — Authentication method
  [g] Google OAuth (recommended for cloud deployments)
  [s] SSO (Okta, Auth0; production multi-tenant only)
  [m] Mock auth — single dev user (laptop / CI only)
"""


def _ask(
    text: str,
    *,
    valid: set[str],
    default: str | None = None,
) -> str:
    """Loop until the operator types one of the valid single-letter codes.

    Case-insensitive: matches against `valid` after lowercasing both
    sides, returns the value as it appears in `valid` (preserving case
    so callers can use uppercase scenario codes like 'A', 'B'...).

    Click's `prompt(type=click.Choice(...))` rejects on first invalid
    input; here we re-ask with the same prompt text, which is friendlier.
    """
    valid_by_lower = {v.lower(): v for v in valid}
    while True:
        click.echo(text)
        raw = click.prompt(
            "Choose",
            default=default,
            show_default=default is not None,
            type=str,
        )
        cleaned = raw.strip().lower()
        if cleaned in valid_by_lower:
            return valid_by_lower[cleaned]
        valid_list = ", ".join(sorted(valid))
        click.echo(click.style(f"  Invalid choice {raw!r}. Valid: {valid_list}", fg="red"))


def _gather_answers() -> DetectorAnswers:
    """Run the 5 prompts and return the answer set."""
    operator_type = _ask(_OPERATOR_TYPE_PROMPT, valid={"a", "b", "c", "d", "e", "f", "t"})
    deployment_target = _ask(_TARGET_PROMPT, valid={"1", "2", "3"})
    federation = _ask(_FEDERATION_PROMPT, valid={"n", "m", "h"}, default="n")
    pii_handling = _ask(_PII_PROMPT, valid={"d", "s", "o"}, default="d")
    auth_method = _ask(_AUTH_PROMPT, valid={"g", "s", "m"}, default="g")
    return DetectorAnswers(
        operator_type=operator_type,
        deployment_target=deployment_target,
        federation=federation,
        pii_handling=pii_handling,
        auth_method=auth_method,
    )


def prompt_for_scenario(
    *,
    explicit_code: str | None = None,
    non_interactive: bool = False,
) -> PromptResult:
    """Resolve which scenario the operator wants.

    1. If `explicit_code` is set (operator passed `--scenario X`), look it
       up directly and return; no prompts.
    2. Else if `non_interactive=True` without an explicit code, raise
       (CI / scripts must pass a code).
    3. Else run the 5-question detector, show the inferred scenario, ask
       the operator to confirm or override.
    """

    if explicit_code is not None:
        try:
            scenario = SCENARIO_REGISTRY[explicit_code.strip().upper()]  # type: ignore[index]
        except KeyError as e:
            raise click.UsageError(
                f"Unknown --scenario {explicit_code!r}. "
                f"Valid: {', '.join(sorted(SCENARIO_REGISTRY))}"
            ) from e
        return PromptResult(scenario=scenario, detection=None, overridden=False)

    if non_interactive:
        raise click.UsageError(
            "--non-interactive requires --scenario <CODE> (scenario detector needs prompts)."
        )

    answers = _gather_answers()
    detection = infer_scenario(answers, strict=False)

    click.echo()
    click.secho("Detector proposes: ", nl=False, bold=True)
    click.secho(
        f"Scenario {detection.scenario.code} — {detection.scenario.name}",
        fg="green",
        bold=True,
    )
    click.echo()
    click.echo(f"  {detection.scenario.description}")
    click.echo()
    if detection.conflicts:
        click.secho("  Detector noted conflicts:", fg="yellow")
        for conflict in detection.conflicts:
            click.echo(f"    • {conflict}")
        click.echo()

    if click.confirm("Use this scenario?", default=True):
        return PromptResult(
            scenario=detection.scenario,
            detection=detection,
            overridden=False,
        )

    # Operator wants to override — list options + accept their pick.
    click.echo()
    click.echo("Pick a different scenario:")
    for code in sorted(SCENARIO_REGISTRY):
        scenario = SCENARIO_REGISTRY[code]  # type: ignore[index]
        click.echo(f"  [{code}] {scenario.name}")
    chosen_code = _ask(
        "\nWhich scenario?",
        valid=set(SCENARIO_REGISTRY.keys()),
        default=detection.scenario.code,
    )
    overridden_scenario = SCENARIO_REGISTRY[chosen_code.upper()]  # type: ignore[index]
    return PromptResult(
        scenario=overridden_scenario,
        detection=detection,
        overridden=overridden_scenario.code != detection.scenario.code,
    )


__all__ = [
    "PromptResult",
    "prompt_for_scenario",
]


# Re-export the canonical type for callers that want to type-annotate.
_ScenarioCode = ScenarioCode  # noqa: F841 — keeps the type alias visible
