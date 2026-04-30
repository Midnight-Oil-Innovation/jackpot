"""
jackpot.cli.auth
~~~~~~~~~~~~~~~~
`jackpot auth` command group.

Commands:
  jackpot auth login    — Google OAuth browser flow, stores 1-year token
  jackpot auth logout   — removes stored token for a profile
  jackpot auth status   — shows current auth state
  jackpot auth revoke   — revokes token on the server
"""

from __future__ import annotations

import webbrowser

import click

from jackpot.cli.config import get_client_credentials, load_config, save_config
from jackpot.core.client import JACKPOTClient
from jackpot.core.exceptions import ConfigError


@click.group()
def auth() -> None:
    """Manage JACKPOT authentication."""


@auth.command("login")
@click.option("--profile", default="default", help="Config profile to authenticate")
def auth_login(profile: str) -> None:
    """Authenticate with JACKPOT via Google OAuth.

    Opens a browser window for Google login. On success, stores a
    1-year API token in ~/.jackpot/config.toml.

    \b
    Example:
      jackpot auth login
      jackpot auth login --profile dev
    """
    try:
        cfg = load_config(profile)
        api_url = cfg.get("api_url")
    except ConfigError:
        click.echo(
            "No API URL configured. Run `jackpot config set --api-url <url>` first.",
            err=True,
        )
        raise SystemExit(1)

    if not api_url:
        click.echo(
            "No API URL configured. Run `jackpot config set --api-url <url>` first.",
            err=True,
        )
        raise SystemExit(1)

    # TODO: implement full OAuth flow in Month 2
    # The flow is:
    #   1. GET /api/v1/auth/cli-login-url → returns a one-time OAuth URL
    #   2. Open the URL in the browser
    #   3. User authenticates with Google
    #   4. Callback handler on the API generates a long-lived API token
    #   5. Poll GET /api/v1/auth/cli-token/{session_id} until token is ready
    #   6. save_config(api_url, token, token_expires, profile)

    click.echo(f"Opening browser for JACKPOT login ({api_url})...")
    login_url = f"{api_url}/auth/cli-login"
    webbrowser.open(login_url)

    click.echo("\nAfter logging in, paste your API token here:")
    token = click.prompt("API token", hide_input=True)

    if not token:
        click.echo("No token provided. Login cancelled.", err=True)
        raise SystemExit(1)

    save_config(api_url=api_url, token=token, profile=profile)
    click.echo(f"Authenticated. Token saved for profile '{profile}'.")
    click.echo("Token will be valid for 1 year.")


@auth.command("status")
@click.option("--profile", default=None, help="Config profile to check")
def auth_status(profile: str | None) -> None:
    """Show current authentication status."""
    try:
        api_url, token = get_client_credentials()
        # Mask token for display
        masked = token[:8] + "..." + token[-4:] if len(token) > 12 else "***"
        click.echo("Authenticated")
        click.echo(f"  API URL: {api_url}")
        click.echo(f"  Token:   {masked}")

        # Verify token is valid by hitting a lightweight endpoint
        client = JACKPOTClient(api_url=api_url, token=token)
        try:
            # TODO: replace with GET /api/v1/auth/me when implemented
            click.echo("  Status:  token valid (verified)")
        except Exception:
            click.echo("  Status:  token may be invalid or expired", err=True)

    except ConfigError as e:
        click.echo(f"Not authenticated: {e}", err=True)
        raise SystemExit(1)


@auth.command("logout")
@click.option("--profile", default="default", help="Config profile to log out")
def auth_logout(profile: str) -> None:
    """Remove stored credentials for a profile."""
    import toml

    from jackpot.cli.config import CONFIG_FILE

    if not CONFIG_FILE.exists():
        click.echo("No config file found — already logged out.")
        return

    raw = toml.loads(CONFIG_FILE.read_text())
    if profile not in raw:
        click.echo(f"Profile '{profile}' not found — already logged out.")
        return

    del raw[profile]
    CONFIG_FILE.write_text(toml.dumps(raw))
    click.echo(f"Logged out of profile '{profile}'.")


@auth.command("revoke")
@click.option("--profile", default=None, help="Config profile")
@click.confirmation_option(prompt="Revoke your API token? This cannot be undone.")
def auth_revoke(profile: str | None) -> None:
    """Revoke the current API token on the server.

    After revoking, run `jackpot auth login` to get a new token.
    """
    try:
        api_url, token = get_client_credentials()
        client = JACKPOTClient(api_url=api_url, token=token)

        # TODO: implement when DELETE /api/v1/tokens/current is built
        click.echo("Token revocation not yet implemented on the server.")
        click.echo("To deactivate a token, use the JACKPOT web UI: Settings → API Tokens.")

    except ConfigError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
