"""
jackpot.cli.config
~~~~~~~~~~~~~~~~~~
Manages ~/.jackpot/config.toml — the local CLI configuration file.

Config file format:

    [default]
    api_url = "https://api.your-jackpot-instance.org"
    token = "jk_live_..."
    token_expires = "2027-04-09T00:00:00Z"

    [dev]
    api_url = "http://localhost:8000"
    token = "jk_dev_..."
    token_expires = "2027-04-09T00:00:00Z"

The active profile is selected by JACKPOT_PROFILE env var (default: "default").
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import toml

from jackpot.core.exceptions import ConfigError, TokenExpiredError
from jackpot.core.private_file import write_private

CONFIG_DIR = Path.home() / ".jackpot"
CONFIG_FILE = CONFIG_DIR / "config.toml"

# Environment variable overrides — checked before reading the config file.
# These are pre-set in all JACKPOT workspace pods via context injection.
ENV_API_URL = "JACKPOT_API_URL"
ENV_TOKEN = "JACKPOT_API_TOKEN"
ENV_PROJECT_ID = "JACKPOT_PROJECT_ID"
ENV_LAB_ID = "JACKPOT_LAB_ID"
ENV_PROFILE = "JACKPOT_PROFILE"


def get_profile() -> str:
    return os.environ.get(ENV_PROFILE, "default")


def load_config(profile: str | None = None) -> dict:
    """
    Load configuration for the given profile.
    Environment variables take precedence over the config file.
    """
    profile = profile or get_profile()

    # Environment variable overrides (workspace pod context injection)
    env_api_url = os.environ.get(ENV_API_URL)
    env_token = os.environ.get(ENV_TOKEN)

    if env_api_url and env_token:
        return {
            "api_url": env_api_url,
            "token": env_token,
            "project_id": os.environ.get(ENV_PROJECT_ID),
            "lab_id": os.environ.get(ENV_LAB_ID),
            "source": "environment",
        }

    # Fall back to config file
    if not CONFIG_FILE.exists():
        raise ConfigError(
            "No JACKPOT configuration found.\n"
            "Run `jackpot config set --api-url <url>` and `jackpot auth login`.\n"
            "Or set JACKPOT_API_URL and JACKPOT_API_TOKEN environment variables."
        )

    raw = toml.loads(CONFIG_FILE.read_text())
    if profile not in raw:
        raise ConfigError(
            f"Profile '{profile}' not found in {CONFIG_FILE}.\n"
            f"Available profiles: {', '.join(raw.keys())}"
        )

    cfg = raw[profile]
    cfg["source"] = f"config:{profile}"
    return cfg


def get_client_credentials() -> tuple[str, str]:
    """
    Return (api_url, token) ready for JACKPOTClient construction.
    Raises ConfigError if config is missing.
    Raises TokenExpiredError if token has expired.
    """
    cfg = load_config()
    api_url = cfg.get("api_url")
    token = cfg.get("token")

    if not api_url or not token:
        raise ConfigError(
            "Incomplete configuration: api_url and token are required.\n"
            "Run `jackpot config set --api-url <url>` and `jackpot auth login`."
        )

    # Check token expiry if stored
    expires = cfg.get("token_expires")
    if expires:
        try:
            exp_dt = datetime.fromisoformat(expires)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=UTC)
            if datetime.now(UTC) > exp_dt:
                raise TokenExpiredError(
                    "Your JACKPOT API token has expired.\n"
                    "Run `jackpot auth login` to get a new one."
                )
        except ValueError:
            pass  # Malformed date — skip expiry check

    return api_url, token


def save_config(
    api_url: str,
    token: str,
    token_expires: str | None = None,
    profile: str | None = None,
) -> None:
    """Write or update a profile in the config file."""
    profile = profile or get_profile()
    CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    CONFIG_DIR.chmod(0o700)  # narrow it too if it predates the mode= above

    raw = {}
    if CONFIG_FILE.exists():
        raw = toml.loads(CONFIG_FILE.read_text())

    raw[profile] = {"api_url": api_url, "token": token}
    if token_expires:
        raw[profile]["token_expires"] = token_expires

    # The file holds an API token — never let it exist world-readable,
    # not even for the moment between write_text and chmod.
    write_private(CONFIG_FILE, toml.dumps(raw))


def show_config(profile: str | None = None) -> dict:
    """Return config for display — masks the token."""
    cfg = load_config(profile)
    if "token" in cfg and cfg["token"]:
        token = cfg["token"]
        cfg["token"] = token[:8] + "..." + token[-4:] if len(token) > 12 else "***"
    return cfg
