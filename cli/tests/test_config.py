"""
tests/test_config.py
~~~~~~~~~~~~~~~~~~~~
Tests for jackpot.cli.config — config file management.
"""
import pytest
import toml

from jackpot.cli.config import (
    get_client_credentials,
    load_config,
    save_config,
    show_config,
)
from jackpot.core.exceptions import ConfigError, TokenExpiredError


class TestLoadConfig:
    def test_loads_default_profile(self, mock_config):
        cfg = load_config()
        assert cfg["api_url"] == "http://testserver"
        assert cfg["token"] == "jk_test_abc123"

    def test_missing_config_raises_config_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "jackpot.cli.config.CONFIG_FILE", tmp_path / "nonexistent.toml"
        )
        with pytest.raises(ConfigError):
            load_config()

    def test_unknown_profile_raises_config_error(self, mock_config):
        with pytest.raises(ConfigError, match="Profile 'nonexistent'"):
            load_config(profile="nonexistent")

    def test_env_vars_take_precedence(self, monkeypatch):
        monkeypatch.setenv("JACKPOT_API_URL", "http://envserver")
        monkeypatch.setenv("JACKPOT_API_TOKEN", "env_token_xyz")
        cfg = load_config()
        assert cfg["api_url"] == "http://envserver"
        assert cfg["token"] == "env_token_xyz"
        assert cfg["source"] == "environment"


class TestGetClientCredentials:
    def test_returns_api_url_and_token(self, mock_config):
        api_url, token = get_client_credentials()
        assert api_url == "http://testserver"
        assert token == "jk_test_abc123"

    def test_expired_token_raises(self, mock_config, monkeypatch):
        from jackpot.cli.config import CONFIG_FILE
        import toml

        raw = toml.loads(CONFIG_FILE.read_text())
        raw["default"]["token_expires"] = "2000-01-01T00:00:00Z"  # past
        CONFIG_FILE.write_text(toml.dumps(raw))

        with pytest.raises(TokenExpiredError):
            get_client_credentials()


class TestSaveConfig:
    def test_saves_new_profile(self, mock_config, tmp_path, monkeypatch):
        from jackpot.cli import config as cfg_module
        monkeypatch.setattr(cfg_module, "CONFIG_DIR",  tmp_path / ".jackpot")
        monkeypatch.setattr(cfg_module, "CONFIG_FILE", tmp_path / ".jackpot" / "config.toml")

        save_config(
            api_url="http://newserver",
            token="new_token_abc",
            token_expires="2099-01-01T00:00:00Z",
            profile="test",
        )

        raw = toml.loads((tmp_path / ".jackpot" / "config.toml").read_text())
        assert raw["test"]["api_url"] == "http://newserver"
        assert raw["test"]["token"] == "new_token_abc"

    def test_config_file_has_restricted_permissions(self, mock_config, tmp_path, monkeypatch):
        import stat
        from jackpot.cli import config as cfg_module

        config_dir  = tmp_path / ".jackpot"
        config_file = config_dir / "config.toml"
        monkeypatch.setattr(cfg_module, "CONFIG_DIR",  config_dir)
        monkeypatch.setattr(cfg_module, "CONFIG_FILE", config_file)

        save_config(api_url="http://x", token="tok", profile="default")

        mode = config_file.stat().st_mode
        # Owner read/write only (0o600)
        assert not (mode & stat.S_IRGRP)
        assert not (mode & stat.S_IROTH)


class TestShowConfig:
    def test_masks_token(self, mock_config):
        cfg = show_config()
        assert "jk_test_abc123" not in cfg.get("token", "")
        assert "..." in cfg.get("token", "")
