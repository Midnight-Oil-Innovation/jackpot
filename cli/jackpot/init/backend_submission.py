"""I-3c: ``jackpot init`` prompt for backend-submission settings.

Runs as part of the ``configure`` flow. Per-scenario behaviour:

  - Scenario A (laptop): no prompt; default off.
  - Scenario F (CI): no prompt; default off — CI runs synthetic data
    against fakes, never against a real repository.
  - Scenarios B / C / D / E / T (server / cloud / federation / tribal):
    prompt the operator. Default to enabled with NCBI selected; ENA is
    opt-in.

Returns a dict suitable for merging into ``operator_overrides`` in
:func:`jackpot.cli.cli.init._gather_operator_overrides`. The keys
``allow_backend_submission`` and ``backend_submission_repos`` then
flow through :func:`jackpot.init.writers.render_env_local` as
``ALLOW_BACKEND_SUBMISSION`` and ``BACKEND_SUBMISSION_REPOS`` env
vars in the generated ``.env.local``.

The wizard prints a closing reminder listing the credential env-var
names the operator needs to set out-of-band — this is the bridge
between the wizard and the C-1 credential abstraction. JACKPOT does
not collect or store the credentials themselves; the operator
configures them via the C-1 backend (env, file, or GCP Secret
Manager) before triggering the first execution.
"""

from __future__ import annotations

import click
from jackpot_scenarios.scenarios import Scenario

# Scenarios where backend execution is never prompted. The default is
# off and stays off.
_NO_PROMPT_SCENARIOS: frozenset[str] = frozenset({"A", "F"})


def prompt_for_backend_submission(
    scenario: Scenario,
    *,
    non_interactive: bool = False,
) -> dict[str, object]:
    """Run the backend-submission prompts; return overrides dict.

    For ``--non-interactive`` runs (and for the no-prompt scenarios)
    the function returns the safe-off defaults without printing
    anything: ``{"allow_backend_submission": False, "backend_submission_repos": []}``.
    """
    if non_interactive or scenario.code in _NO_PROMPT_SCENARIOS:
        return {
            "allow_backend_submission": False,
            "backend_submission_repos": [],
        }

    click.echo()
    click.secho("─── Backend submission ───", bold=True)
    click.echo(
        "JACKPOT can run NCBI submissions on the backend automatically "
        "after package generation. This requires submitter credentials "
        "configured out-of-band (env vars, credential file, or GCP "
        "Secret Manager). When disabled, all submissions go through "
        "the manual package-then-Seqsender workflow."
    )
    if not click.confirm("Enable backend submission?", default=True):
        return {
            "allow_backend_submission": False,
            "backend_submission_repos": [],
        }

    click.echo()
    click.echo("Which repositories should be enabled for backend execution?")
    click.echo("  (NCBI is most commonly enabled; ENA optional.)")
    enable_ncbi = click.confirm("  NCBI?", default=True)
    enable_ena = click.confirm("  ENA?", default=False)
    repos: list[str] = []
    if enable_ncbi:
        repos.append("ncbi")
    if enable_ena:
        repos.append("ena")
    if not repos:
        click.secho(
            "  No repositories selected — disabling backend submission.",
            fg="yellow",
            err=True,
        )
        return {
            "allow_backend_submission": False,
            "backend_submission_repos": [],
        }

    _print_credential_reminder(repos)
    return {
        "allow_backend_submission": True,
        "backend_submission_repos": repos,
    }


def _print_credential_reminder(repos: list[str]) -> None:
    """Tell the operator which credentials they need to set in their
    C-1 credential backend before triggering the first execution.

    The wizard never collects credentials directly — they live in the
    operator's chosen backend (env, file, GCP Secret Manager). The
    matching ``JACKPOT_CRED_*`` env-var names are the canonical lookup
    keys; the legacy ``NCBI_*`` / ``ENA_*`` env-var names also work
    via the C-1 EnvVarBackend's legacy fallback.
    """
    click.echo()
    click.secho(f"Backend submission enabled for: {', '.join(repos)}", fg="green")
    click.echo("Configure credentials before triggering execution:")
    for repo in repos:
        if repo == "ncbi":
            click.echo("  - JACKPOT_CRED_NCBI_SUBMISSION_USERNAME")
            click.echo("  - JACKPOT_CRED_NCBI_SUBMISSION_PASSWORD")
        elif repo == "ena":
            click.echo("  - JACKPOT_CRED_ENA_WEBIN_USERNAME")
            click.echo("  - JACKPOT_CRED_ENA_WEBIN_PASSWORD")
    click.echo(
        "(Or set the equivalent in your credential backend: file YAML "
        "or GCP Secret Manager. See docs/credentials/.)"
    )


__all__ = ["prompt_for_backend_submission"]
