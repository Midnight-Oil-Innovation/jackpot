"""
tests/conftest.py
~~~~~~~~~~~~~~~~~
Shared fixtures for jackpot-cli tests.

Tests use pytest-httpx to mock API calls — no real network traffic.
"""
import pytest
from click.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    """Click test runner with isolated filesystem."""
    return CliRunner()


@pytest.fixture
def mock_config(tmp_path, monkeypatch):
    """
    Patch the config directory to use a temp path.
    Provides a pre-configured profile with a fake API token.
    """
    import toml

    config_dir  = tmp_path / ".jackpot"
    config_file = config_dir / "config.toml"
    config_dir.mkdir()
    config_file.write_text(toml.dumps({
        "default": {
            "api_url":       "http://testserver",
            "token":         "jk_test_abc123",
            "token_expires": "2099-01-01T00:00:00Z",
        }
    }))

    monkeypatch.setattr("jackpot.cli.config.CONFIG_DIR",  config_dir)
    monkeypatch.setattr("jackpot.cli.config.CONFIG_FILE", config_file)

    return {"api_url": "http://testserver", "token": "jk_test_abc123"}


@pytest.fixture
def api_url(mock_config) -> str:
    return mock_config["api_url"]
