"""End-to-end tests for `jackpot init` Click commands.

The pure inference logic is tested in `schema/tests/test_detector.py`;
this file tests the Click wrapping (flag parsing, prompt loop, output
shape).
"""

from __future__ import annotations

import json

import pytest
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

    def test_init_subcommand_help_shows_all_commands(self, runner: CliRunner) -> None:
        from jackpot.cli.main import cli

        result = runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0
        for subcommand in ("detect", "scenario-info", "configure"):
            assert subcommand in result.output


class TestConfigureNonInteractive:
    """`jackpot init configure --scenario X --non-interactive` writes
    the 5 instance files using only scenario defaults."""

    def test_configure_writes_instance_dir(self, runner: CliRunner, tmp_path) -> None:
        result = runner.invoke(
            init,
            [
                "configure",
                "--scenario",
                "F",
                "--instance-name",
                "ci-local",
                "--instances-dir",
                str(tmp_path),
                "--non-interactive",
                "--no-gh",
            ],
        )
        assert result.exit_code == 0, result.output
        instance_dir = tmp_path / "ci-local"
        for filename in (
            "jackpot.toml",
            ".env.local",
            "values.local.yaml",
            "seed.sql",
            "README.md",
        ):
            assert (instance_dir / filename).exists(), filename

    def test_configure_refuses_to_overwrite_committed_ci(self, runner: CliRunner, tmp_path) -> None:
        # Critical Rule 56: instances/ci/ ships in the repo with synthetic
        # values; jackpot init MUST refuse to clobber it.
        result = runner.invoke(
            init,
            [
                "configure",
                "--scenario",
                "F",
                "--instance-name",
                "ci",
                "--instances-dir",
                str(tmp_path),
                "--non-interactive",
                "--no-gh",
            ],
        )
        assert result.exit_code != 0
        assert "Critical Rule 56" in result.output

    def test_configure_unknown_scenario_rejected(self, runner: CliRunner, tmp_path) -> None:
        result = runner.invoke(
            init,
            [
                "configure",
                "--scenario",
                "Z",
                "--instances-dir",
                str(tmp_path),
                "--non-interactive",
                "--no-gh",
            ],
        )
        assert result.exit_code != 0
        assert "Unknown" in result.output


class TestConfigureInteractivePrompts:
    """Walk through the operator-identity prompts."""

    def test_configure_with_typed_operator_values(self, runner: CliRunner, tmp_path) -> None:
        # Inputs in order:
        #   org name, email, deployment URL, accept derived CORS,
        #   I-3c backend-submission: enable? NCBI? ENA?
        result = runner.invoke(
            init,
            [
                "configure",
                "--scenario",
                "B",
                "--instance-name",
                "staging",
                "--instances-dir",
                str(tmp_path),
                "--no-gh",
            ],
            input=(
                "Example Hospital\n"
                "admin@hospital.example.org\n"
                "https://api.hospital.example.org\n"
                "y\n"
                "y\n"
                "y\n"
                "n\n"
            ),
        )
        assert result.exit_code == 0, result.output
        toml_path = tmp_path / "staging" / "jackpot.toml"
        assert "Example Hospital" in toml_path.read_text()
        assert "admin@hospital.example.org" in toml_path.read_text()


class TestConfigureRerunsArePreservingByDefault:
    def test_rerun_overwrites_non_secrets_by_default(self, runner: CliRunner, tmp_path) -> None:
        # First run.
        runner.invoke(
            init,
            [
                "configure",
                "--scenario",
                "F",
                "--instance-name",
                "ci-local",
                "--instances-dir",
                str(tmp_path),
                "--non-interactive",
                "--no-gh",
            ],
        )
        # Plant a secret + a hand-edited TOML comment.
        secret_file = tmp_path / "ci-local" / "secrets" / "jwt_signing_key.txt"
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret_file.write_text("ORIGINAL")
        toml_file = tmp_path / "ci-local" / "jackpot.toml"
        toml_file.write_text(toml_file.read_text() + "\n# operator note\n")

        # Second run — default overwrite_non_secrets=True (operator note lost).
        runner.invoke(
            init,
            [
                "configure",
                "--scenario",
                "F",
                "--instance-name",
                "ci-local",
                "--instances-dir",
                str(tmp_path),
                "--non-interactive",
                "--no-gh",
            ],
        )
        assert secret_file.read_text() == "ORIGINAL"
        assert "# operator note" not in toml_file.read_text()

    def test_rerun_with_no_overwrite_preserves_everything(
        self, runner: CliRunner, tmp_path
    ) -> None:
        runner.invoke(
            init,
            [
                "configure",
                "--scenario",
                "F",
                "--instance-name",
                "ci-local",
                "--instances-dir",
                str(tmp_path),
                "--non-interactive",
                "--no-gh",
            ],
        )
        toml_file = tmp_path / "ci-local" / "jackpot.toml"
        toml_file.write_text(toml_file.read_text() + "\n# operator note\n")

        result = runner.invoke(
            init,
            [
                "configure",
                "--scenario",
                "F",
                "--instance-name",
                "ci-local",
                "--instances-dir",
                str(tmp_path),
                "--non-interactive",
                "--no-gh",
                "--no-overwrite-non-secrets",
            ],
        )
        assert result.exit_code == 0
        assert "# operator note" in toml_file.read_text()
        assert "preserved" in result.output


# ── scenario codes are never shown bare (B-SCENARIO-TAXONOMY-SPLIT) ────────


def test_scenario_help_names_every_code():
    """Bare letters look self-explanatory and are not.

    ADR-0002 assigns D to the CI harness; SCENARIO_REGISTRY assigns it to
    hosted multi-tenant SaaS. Both are valid input, so a reader of the
    canonical ADR can type a correct-looking code and install something
    else with no error. Until the taxonomy is settled, the names are what
    make that visible at the moment of choosing.
    """
    from jackpot_scenarios.scenarios import SCENARIO_REGISTRY

    from jackpot.cli.init import _scenario_choices

    rendered = _scenario_choices()
    for code, scenario in SCENARIO_REGISTRY.items():
        assert f"{code}={scenario.name}" in rendered, f"{code} shown without its name"


def test_scenario_help_is_derived_not_transcribed():
    """A hand-written list is what drifted. Adding a scenario must not
    require remembering to update the help text."""
    from jackpot_scenarios.scenarios import SCENARIO_REGISTRY

    from jackpot.cli.init import _scenario_choices

    assert _scenario_choices().count("=") == len(SCENARIO_REGISTRY)


@pytest.mark.parametrize("command", ["detect", "configure"])
def test_rendered_help_names_the_scenarios(runner: CliRunner, command: str):
    """Canary (Critical Rule 74), asserted on the surface a user sees.

    The tests above only inspect _scenario_choices(); if a help string went
    back to the bare "(A | B | C | D | E | F | T)" they would all still
    pass. This checks what click actually renders, which is where the
    ambiguity would reach an operator.
    """
    out = runner.invoke(init, [command, "--help"]).output
    assert "A | B | C | D" not in out, "a bare-letter scenario list is back in --help"
    assert "Hosted multi-tenant SaaS" in out, "D's real meaning is not shown"
