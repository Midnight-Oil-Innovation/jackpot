"""End-to-end tests for `jackpot init` Click commands.

The pure inference logic is tested in `schema/tests/test_detector.py`;
this file tests the Click wrapping (flag parsing, prompt loop, output
shape).
"""

from __future__ import annotations

import json

from click.testing import CliRunner

from jackpot.cli.init import init


class TestDetectExplicitScenario:
    """`jackpot init detect --scenario X` short-circuits the prompts."""

    def test_explicit_scenario_skips_prompts(self, runner: CliRunner) -> None:
        result = runner.invoke(init, ["detect", "--scenario", "T"])
        assert result.exit_code == 0, result.output
        assert "Selected scenario:" in result.output
        assert "Code:        T" in result.output
        assert "Tribal-sovereignty" in result.output
        # No detector-rationale block when --scenario short-circuits.
        assert "Detector rationale:" not in result.output

    def test_explicit_scenario_lowercase_normalised(self, runner: CliRunner) -> None:
        result = runner.invoke(init, ["detect", "--scenario", "t"])
        assert result.exit_code == 0
        assert "Code:        T" in result.output

    def test_unknown_scenario_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(init, ["detect", "--scenario", "Z"])
        assert result.exit_code != 0
        assert "Unknown" in result.output


class TestDetectNonInteractiveRequiresScenario:
    def test_non_interactive_without_scenario_fails(self, runner: CliRunner) -> None:
        result = runner.invoke(init, ["detect", "--non-interactive"])
        assert result.exit_code != 0
        assert "--scenario" in result.output

    def test_non_interactive_with_scenario_succeeds(self, runner: CliRunner) -> None:
        result = runner.invoke(init, ["detect", "--non-interactive", "--scenario", "F"])
        assert result.exit_code == 0
        assert "Code:        F" in result.output


class TestDetectInteractiveAccept:
    """Walk through the 5 prompts, accept the proposal."""

    def test_full_question_flow_accept_proposal(self, runner: CliRunner) -> None:
        # Answers: Tribal / laptop / off / DLP / Google → T
        # Then 'y' to accept the proposal.
        result = runner.invoke(
            init,
            ["detect"],
            input="t\n1\nn\nd\ng\ny\n",
        )
        assert result.exit_code == 0, result.output
        assert "Detector proposes:" in result.output
        assert "Scenario T" in result.output
        assert "Selected scenario:" in result.output
        assert "Code:        T" in result.output

    def test_invalid_answer_re_prompts(self, runner: CliRunner) -> None:
        # First answer 'z' is invalid → re-ask. Then 'a' is valid.
        result = runner.invoke(
            init,
            ["detect"],
            input="z\na\n1\nn\no\nm\ny\n",
        )
        assert result.exit_code == 0
        assert "Invalid choice" in result.output
        assert "Code:        A" in result.output


class TestDetectInteractiveOverride:
    """Operator rejects the detector's proposal and picks another scenario."""

    def test_override_after_proposal(self, runner: CliRunner) -> None:
        # Answers: laptop scenario → A proposed.
        # Then 'n' to override, then 'B' to pick something else.
        result = runner.invoke(
            init,
            ["detect"],
            input="a\n1\nn\no\nm\nn\nB\n",
        )
        assert result.exit_code == 0, result.output
        assert "Code:        B" in result.output
        assert "operator overrode the detector's proposal" in result.output


class TestScenarioInfo:
    def test_scenario_info_human_readable(self, runner: CliRunner) -> None:
        result = runner.invoke(init, ["scenario-info", "A"])
        assert result.exit_code == 0
        assert "Scenario A" in result.output
        assert "Defaults:" in result.output
        # Spot-check a few field names from the model.
        assert "deletion_on_request" in result.output
        assert "federation_role" in result.output

    def test_scenario_info_json(self, runner: CliRunner) -> None:
        result = runner.invoke(init, ["scenario-info", "T", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["code"] == "T"
        assert payload["defaults"]["deletion_on_request"] is True
        assert payload["defaults"]["auto_publish_to_insdc"] is False
        assert payload["defaults"]["care_principles_enforced"] is True

    def test_scenario_info_unknown_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(init, ["scenario-info", "X"])
        assert result.exit_code != 0
        assert "Unknown scenario" in result.output


class TestRegistrationInRootCli:
    """Confirm `jackpot init` wired into the top-level CLI."""

    def test_init_listed_in_help(self, runner: CliRunner) -> None:
        from jackpot.cli.main import cli

        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "init" in result.output

    def test_init_subcommand_help_shows_detect(self, runner: CliRunner) -> None:
        from jackpot.cli.main import cli

        result = runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0
        assert "detect" in result.output
        assert "scenario-info" in result.output
