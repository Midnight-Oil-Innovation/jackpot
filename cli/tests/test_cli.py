"""
tests/test_cli.py
~~~~~~~~~~~~~~~~~
Smoke tests for CLI commands.
Verifies help text, error handling, and basic invocation.
"""
import pytest
from click.testing import CliRunner

from jackpot.cli.main import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestCLIHelp:
    """Verify help text renders without errors."""

    def test_root_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "JACKPOT" in result.output

    def test_config_help(self, runner):
        result = runner.invoke(cli, ["config", "--help"])
        assert result.exit_code == 0

    def test_auth_help(self, runner):
        result = runner.invoke(cli, ["auth", "--help"])
        assert result.exit_code == 0

    def test_upload_help(self, runner):
        result = runner.invoke(cli, ["upload", "--help"])
        assert result.exit_code == 0

    def test_upload_dir_help(self, runner):
        result = runner.invoke(cli, ["upload-dir", "--help"])
        assert result.exit_code == 0

    def test_upload_globus_help(self, runner):
        result = runner.invoke(cli, ["upload-globus", "--help"])
        assert result.exit_code == 0

    def test_samples_help(self, runner):
        result = runner.invoke(cli, ["samples", "--help"])
        assert result.exit_code == 0

    def test_pipelines_help(self, runner):
        result = runner.invoke(cli, ["pipelines", "--help"])
        assert result.exit_code == 0


class TestConfigSet:
    def test_config_set_writes_file(self, runner, tmp_path, monkeypatch):
        from jackpot.cli import config as cfg_module
        config_dir  = tmp_path / ".jackpot"
        config_file = config_dir / "config.toml"
        monkeypatch.setattr(cfg_module, "CONFIG_DIR",  config_dir)
        monkeypatch.setattr(cfg_module, "CONFIG_FILE", config_file)

        result = runner.invoke(cli, [
            "config", "set",
            "--api-url", "http://localhost:8000",
        ])
        assert result.exit_code == 0
        assert config_file.exists()

        import toml
        raw = toml.loads(config_file.read_text())
        assert raw["default"]["api_url"] == "http://localhost:8000"


class TestAuthStatus:
    def test_auth_status_not_configured(self, runner, tmp_path, monkeypatch):
        """Should exit non-zero when no config is present."""
        from jackpot.cli import config as cfg_module
        monkeypatch.setattr(
            cfg_module, "CONFIG_FILE", tmp_path / "nonexistent.toml"
        )
        result = runner.invoke(cli, ["auth", "status"])
        assert result.exit_code != 0

    def test_auth_status_configured(self, runner, mock_config):
        result = runner.invoke(cli, ["auth", "status"])
        # May fail when hitting the API check but should show config
        assert "http://testserver" in result.output


class TestUploadDirDryRun:
    def test_dry_run_no_files(self, runner, tmp_path):
        result = runner.invoke(cli, [
            "upload-dir", str(tmp_path), "--dry-run",
        ])
        # Should exit non-zero when no files found
        assert result.exit_code != 0
        assert "No files" in result.output

    def test_dry_run_detects_paired_files(self, runner, tmp_path):
        # Create fake paired FASTQ files
        (tmp_path / "AZ-001_R1.fastq.gz").write_bytes(b"fake")
        (tmp_path / "AZ-001_R2.fastq.gz").write_bytes(b"fake")
        (tmp_path / "AZ-002_R1.fastq.gz").write_bytes(b"fake")
        (tmp_path / "AZ-002_R2.fastq.gz").write_bytes(b"fake")

        result = runner.invoke(cli, [
            "upload-dir", str(tmp_path), "--dry-run",
        ])
        assert "2 samples" in result.output or "AZ-001" in result.output
        assert result.exit_code == 0
