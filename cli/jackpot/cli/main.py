"""
jackpot.cli.main
~~~~~~~~~~~~~~~~
JACKPOT CLI entry point.

Registered as `jackpot` console script via pyproject.toml.
All commands are defined in submodules and registered here.
"""

import click

from jackpot.cli.auth import auth
from jackpot.cli.pipelines import pipelines
from jackpot.cli.samples import samples
from jackpot.cli.upload import upload, upload_dir, upload_globus


@click.group()
@click.version_option(package_name="jackpot")
def cli() -> None:
    """JACKPOT — pathogen genomics platform CLI.

    \b
    Quick start:
      jackpot config set --api-url https://api.jackpot.adhs.az.gov
      jackpot auth login
      jackpot upload --r1 sample_R1.fastq.gz --r2 sample_R2.fastq.gz --project 42
    """


# ── Config commands ─────────────────────────────────────────────────────────


@cli.group()
def config() -> None:
    """Manage local JACKPOT configuration (~/.jackpot/config.toml)."""


@config.command("set")
@click.option("--api-url", required=True, help="JACKPOT API base URL")
@click.option("--profile", default="default", help="Config profile name")
def config_set(api_url: str, profile: str) -> None:
    """Set the API URL for a config profile.

    \b
    Example:
      jackpot config set --api-url https://api.jackpot.adhs.az.gov
    """
    import toml

    from jackpot.cli.config import CONFIG_DIR, CONFIG_FILE

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.chmod(0o700)

    raw = {}
    if CONFIG_FILE.exists():
        raw = toml.loads(CONFIG_FILE.read_text())

    existing = raw.get(profile, {})
    existing["api_url"] = api_url
    raw[profile] = existing

    CONFIG_FILE.write_text(toml.dumps(raw))
    CONFIG_FILE.chmod(0o600)

    click.echo(f"Set api_url for profile '{profile}': {api_url}")
    click.echo(f"Config saved to {CONFIG_FILE}")
    if "token" not in existing:
        click.echo("Run `jackpot auth login` to authenticate.")


@config.command("show")
@click.option("--profile", default=None, help="Profile to show")
def config_show(profile: str | None) -> None:
    """Show current configuration (token is masked)."""
    from rich import print as rprint

    from jackpot.cli.config import show_config

    try:
        cfg = show_config(profile)
        rprint(cfg)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


# ── Register subcommand groups ───────────────────────────────────────────────

cli.add_command(auth)
cli.add_command(samples)
cli.add_command(pipelines)

# Upload commands are top-level (not grouped) for ergonomics
cli.add_command(upload)
cli.add_command(upload_dir)
cli.add_command(upload_globus)


if __name__ == "__main__":
    cli()
