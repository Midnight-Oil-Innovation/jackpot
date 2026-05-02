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

# GitHub-org-style alphanumeric + hyphen, no leading hyphen, no slashes,
# no parent-directory traversal. Mirrors the validation in
# deploy/scripts/bootstrap_project.sh — operators see the same shape
# rules at the CLI and the deploy layer.
import re as _re
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

_INSTANCE_NAME_RE = _re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _validate_instance_name(instance_name: str) -> str:
    """Reject instance names that would escape `instances/` via path
    trickery, contain shell-metacharacters, or shadow special dotfiles.

    Returns the normalised name (currently identity — no normalisation
    is applied so the on-disk directory matches the operator's typed
    value exactly).
    """
    if not instance_name or not _INSTANCE_NAME_RE.match(instance_name):
        raise click.UsageError(
            f"Invalid --instance-name {instance_name!r}. Must match "
            r"`[A-Za-z0-9][A-Za-z0-9_-]*` (alphanumeric + dash/underscore, "
            "no leading dash). Path traversal characters (`/`, `\\`, `..`, "
            "leading `.`) are rejected to keep all instance writes inside "
            "the instances/ directory."
        )
    return instance_name


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

    resolved_instance_name = _validate_instance_name(
        instance_name or _DEFAULT_INSTANCE_NAME[scenario_code_upper]
    )

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


# ── secrets subcommand ─────────────────────────────────────────────────


def _read_jackpot_toml_scenario(instance_dir: Path) -> str:
    """Look up the scenario code from instances/<name>/jackpot.toml."""
    import toml

    toml_path = instance_dir / "jackpot.toml"
    if not toml_path.exists():
        raise click.UsageError(
            f"No jackpot.toml found at {toml_path}. Run "
            "`jackpot init configure --scenario <X> --instance-name "
            f"{instance_dir.name}` first."
        )
    parsed = toml.loads(toml_path.read_text())
    code = parsed.get("scenario", {}).get("code")
    if not code:
        raise click.UsageError(f"jackpot.toml at {toml_path} has no [scenario].code")
    return code


@init.command("secrets")
@click.option(
    "--instance",
    "instance_name",
    type=str,
    required=True,
    help="Instance name (matches `instances/<name>/` directory).",
)
@click.option(
    "--instances-dir",
    "instances_dir_str",
    type=str,
    default="instances",
    help="Parent directory for per-instance configs.",
)
@click.option(
    "--regenerate-secrets",
    is_flag=True,
    default=False,
    help=(
        "Rotate existing secrets. Prompts per-secret before "
        "overwriting. WARNING: regenerating a JWT signing key in "
        "production invalidates every issued token."
    ),
)
@click.option(
    "--non-interactive",
    is_flag=True,
    default=False,
    help=(
        "Do not prompt for OAuth client secret or rotation confirms. "
        "OAuth scenarios will leave the OAuth secret file blank — the "
        "operator populates it out-of-band."
    ),
)
def secrets_cmd(
    instance_name: str,
    instances_dir_str: str,
    regenerate_secrets: bool,
    non_interactive: bool,
) -> None:
    """Generate per-instance secrets (JWT signing key, federation
    keypair, OAuth client secret)."""
    from jackpot_scenarios.scenarios import SCENARIO_REGISTRY

    from jackpot.init.secrets import assert_secret_path_invariant, populate_secrets

    instance_dir = Path(instances_dir_str) / _validate_instance_name(instance_name)
    if not instance_dir.exists():
        raise click.UsageError(
            f"Instance directory {instance_dir} does not exist. "
            "Run `jackpot init configure` first."
        )

    scenario_code = _read_jackpot_toml_scenario(instance_dir)
    if scenario_code not in SCENARIO_REGISTRY:
        raise click.UsageError(
            f"jackpot.toml references unknown scenario {scenario_code!r}. "
            f"Valid: {', '.join(sorted(SCENARIO_REGISTRY))}"
        )
    scenario = SCENARIO_REGISTRY[scenario_code]  # type: ignore[index]

    # Critical Rule 56: refuse to overwrite committed instances/ci/.
    if instance_name == "ci" and scenario.code == "F":
        raise click.UsageError(
            "Refusing to write secrets into committed instances/ci/ "
            "(Critical Rule 56). Use --instance-name ci-local for "
            "local CI reproduction."
        )

    def _confirm_overwrite(path: Path) -> bool:
        if non_interactive:
            return False  # never silently rotate in non-interactive mode
        return click.confirm(
            f"  Regenerate {path}? Existing value will be lost.",
            default=False,
        )

    def _oauth_provider() -> str | None:
        if non_interactive:
            return None
        click.echo()
        click.secho(
            "OAuth client secret prompt:",
            bold=True,
        )
        click.echo("  This scenario uses OAuth/SSO. Paste the client secret from your")
        click.echo("  OAuth provider's console (Google Cloud Console / Okta / etc.).")
        click.echo("  Press Enter to skip and populate this file by hand later.")
        value = click.prompt(
            "  OAuth client secret",
            default="",
            show_default=False,
            type=str,
            hide_input=True,
        )
        return value if value else None

    click.echo()
    click.secho(
        f"Populating secrets for instance {instance_name!r} "
        f"(scenario {scenario.code} — {scenario.name})",
        bold=True,
    )

    records = populate_secrets(
        scenario=scenario,
        instance_dir=instance_dir,
        regenerate_secrets=regenerate_secrets,
        confirm_overwrite=_confirm_overwrite,
        oauth_secret_provider=_oauth_provider,
    )

    # Hard invariant — all writes go inside the secrets/ subtree.
    assert_secret_path_invariant(records)

    click.echo()
    click.secho("Secret outcomes:", bold=True)
    for rec in records:
        try:
            display_path = rec.path.relative_to(instance_dir.parent)
        except ValueError:
            display_path = rec.path
        click.echo(f"  [{rec.action:24s}] {display_path}")

    click.echo()
    click.echo(
        "Next: `jackpot init bootstrap --instance " f"{instance_name}` to apply alembic + seed.sql."
    )


# ── bootstrap + validate subcommands ───────────────────────────────────


@init.command("validate")
@click.option(
    "--instance",
    "instance_name",
    type=str,
    required=True,
    help="Instance name (matches `instances/<name>/` directory).",
)
@click.option(
    "--instances-dir",
    "instances_dir_str",
    type=str,
    default="instances",
    help="Parent directory for per-instance configs.",
)
@click.option(
    "--api-url",
    "api_url_override",
    type=str,
    default=None,
    help="Override the JACKPOT_API_URL from .env.local (e.g. for local port-forward).",
)
@click.option(
    "--timeout",
    "timeout_seconds",
    type=int,
    default=60,
    help="Maximum seconds to poll /health before giving up.",
)
def validate_cmd(
    instance_name: str,
    instances_dir_str: str,
    api_url_override: str | None,
    timeout_seconds: int,
) -> None:
    """Smoke-test a running JACKPOT stack — polls /health until 200."""
    from jackpot.init.validator import (
        check_health,
        parse_api_url_from_env_local,
    )

    instance_dir = Path(instances_dir_str) / _validate_instance_name(instance_name)
    if not instance_dir.exists():
        raise click.UsageError(
            f"Instance directory {instance_dir} does not exist. "
            "Run `jackpot init configure` first."
        )

    api_url = api_url_override or parse_api_url_from_env_local(instance_dir / ".env.local")

    click.echo()
    click.secho(f"Validating instance {instance_name!r}", bold=True)
    click.echo(f"  API URL:  {api_url}")
    click.echo(f"  Timeout:  {timeout_seconds}s")
    click.echo("  Polling /health...")

    result = check_health(api_url, timeout_seconds=timeout_seconds)

    click.echo()
    if result.ok:
        click.secho(f"  ✓ {result.detail}", fg="green", bold=True)
    else:
        click.secho(f"  ✗ {result.detail}", fg="red", bold=True)
        raise click.Abort()


@init.command("bootstrap")
@click.option(
    "--instance",
    "instance_name",
    type=str,
    required=True,
    help="Instance name (matches `instances/<name>/` directory).",
)
@click.option(
    "--instances-dir",
    "instances_dir_str",
    type=str,
    default="instances",
    help="Parent directory for per-instance configs.",
)
@click.option(
    "--skip-alembic",
    is_flag=True,
    default=False,
    help="Skip the alembic upgrade step (for environments where the DB is already migrated).",
)
@click.option(
    "--skip-seed",
    is_flag=True,
    default=False,
    help="Skip applying seed.sql (for environments where seeds were applied out-of-band).",
)
@click.option(
    "--skip-validate",
    is_flag=True,
    default=False,
    help="Skip the post-bootstrap /health smoke test (for headless CI runs).",
)
@click.option(
    "--alembic-cmd",
    "alembic_cmd",
    type=str,
    default="alembic upgrade head",
    help="Override the alembic command (e.g. for kubectl exec wrapping).",
)
@click.option(
    "--psql-cmd",
    "psql_cmd",
    type=str,
    default="psql",
    help="Override the psql binary (e.g. /opt/homebrew/bin/psql).",
)
def bootstrap_cmd(
    instance_name: str,
    instances_dir_str: str,
    skip_alembic: bool,
    skip_seed: bool,
    skip_validate: bool,
    alembic_cmd: str,
    psql_cmd: str,
) -> None:
    """Apply alembic migrations + seed.sql + smoke-test the running stack.

    Reads DATABASE_URL from instances/<name>/.env.local. Does NOT start
    Docker; assumes the stack is already up. Run `docker compose up -d`
    in a separate shell first (compose profiles are set in .env.local
    so `docker compose up -d` picks them up automatically).
    """
    import shlex
    import subprocess

    from jackpot.init.validator import (
        check_bootstrap_preconditions,
        check_health,
        parse_api_url_from_env_local,
    )

    instance_dir = Path(instances_dir_str) / _validate_instance_name(instance_name)
    if not instance_dir.exists():
        raise click.UsageError(
            f"Instance directory {instance_dir} does not exist. "
            "Run `jackpot init configure` first."
        )

    # Critical Rule 56: refuse to apply seeds onto the committed CI dir.
    # (instances/ci/ ships with synthetic seed data; bootstrap there is
    # a developer mistake.)
    if instance_name == "ci":
        raise click.UsageError(
            "Refusing to bootstrap committed instances/ci/ directory "
            "(Critical Rule 56). Use --instance ci-local for local CI "
            "reproduction."
        )

    pre = check_bootstrap_preconditions(instance_dir)
    if not pre.ok:
        click.secho("Missing required files:", fg="red", bold=True)
        for rel in pre.missing:
            click.echo(f"  - {instance_dir / rel}")
        click.echo()
        click.echo(
            "Run `jackpot init configure --instance-name "
            f"{instance_name}` and "
            f"`jackpot init secrets --instance {instance_name}` first."
        )
        raise click.Abort()

    env_local = instance_dir / ".env.local"
    api_url = parse_api_url_from_env_local(env_local)

    click.echo()
    click.secho(f"Bootstrapping instance {instance_name!r}", bold=True)
    click.echo(f"  Instance dir: {instance_dir}")
    click.echo(f"  API URL:      {api_url}")
    click.echo()

    # 1. Alembic upgrade head.
    if skip_alembic:
        click.echo("  [skipped]  alembic upgrade head")
    else:
        click.echo(f"  [running]  {alembic_cmd}")
        # PATH comes from the calling shell first, NEVER from .env.local
        # — `env_vars` is loaded last so a malicious or accidental
        # `PATH=` line in .env.local CANNOT override the binary lookup
        # for `alembic` itself.
        env_vars = _load_env_local(env_local)
        env_vars.pop("PATH", None)
        env_vars["PATH"] = _path_env()
        result = subprocess.run(
            shlex.split(alembic_cmd),
            cwd=Path.cwd() / "backend"
            if (Path.cwd() / "backend" / "alembic.ini").exists()
            else Path.cwd(),
            env=env_vars,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            click.secho(
                f"  ✗ alembic failed (exit {result.returncode}):",
                fg="red",
            )
            click.echo(result.stdout)
            click.echo(result.stderr)
            raise click.Abort()
        click.secho("  ✓ alembic upgrade head", fg="green")

    # 2. Apply seed.sql via psql.
    if skip_seed:
        click.echo("  [skipped]  apply seed.sql")
    else:
        seed_path = instance_dir / "seed.sql"
        env_vars = _load_env_local(env_local)
        database_url = env_vars.get("DATABASE_URL", "")
        if not database_url:
            click.secho(
                "  ✗ DATABASE_URL not set in .env.local; cannot apply seed.sql",
                fg="red",
            )
            raise click.Abort()
        click.echo(f"  [running]  {psql_cmd} -f {seed_path}")
        # Same env-hygiene rule as alembic above: PATH from the calling
        # shell, not from .env.local. Otherwise a .env.local with
        # `PATH=/tmp/evil:/usr/bin` would intercept which `psql` runs.
        psql_env = _load_env_local(env_local)
        psql_env.pop("PATH", None)
        psql_env["PATH"] = _path_env()
        result = subprocess.run(
            [psql_cmd, "-f", str(seed_path), database_url],
            env=psql_env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            click.secho(
                f"  ✗ psql failed (exit {result.returncode}):",
                fg="red",
            )
            click.echo(result.stdout)
            click.echo(result.stderr)
            raise click.Abort()
        click.secho("  ✓ seed.sql applied", fg="green")

    # 3. Validate (poll /health).
    if skip_validate:
        click.echo("  [skipped]  /health smoke test")
    else:
        click.echo(f"  [running]  poll {api_url}/health")
        result = check_health(api_url, timeout_seconds=60)
        if result.ok:
            click.secho(f"  ✓ {result.detail}", fg="green")
        else:
            click.secho(f"  ✗ {result.detail}", fg="red")
            raise click.Abort()

    click.echo()
    click.secho("Bootstrap complete.", bold=True, fg="green")


def _load_env_local(env_local_path: Path) -> dict[str, str]:
    """Parse `.env.local` into a dict. Used by bootstrap to forward
    DATABASE_URL etc. to alembic + psql subprocesses."""
    env: dict[str, str] = {}
    for line in env_local_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _path_env() -> str:
    """Return the system PATH so subprocesses can find binaries."""
    import os

    return os.environ.get("PATH", "")
