"""End-to-end `jackpot init` tests — one per scenario.

For each of the 7 scenarios this file:
1. Runs `configure --non-interactive` to write the 5 instance files
2. Runs `secrets --non-interactive` to populate `secrets/`
3. Verifies the written content reflects the scenario's defaults
4. Runs `bootstrap` with all skip-flags set to confirm preconditions pass

We do NOT bring up Docker or Postgres here — that's the integration
job for the runtime CI workflow. These tests verify the CLI
orchestration is correct + the artifacts are well-formed.

Plus: a contract test that the committed `instances/ci/` matches what
scenario F would currently produce — guards against drift between the
canonical CI fixture and the registry defaults.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import toml
import yaml
from click.testing import CliRunner
from jackpot_scenarios import get_scenario

from jackpot.cli.init import init

# Repo root, derived from this test file's location. Used by the
# committed-CI-fixture contract test.
_REPO_ROOT = Path(__file__).resolve().parents[2]


SCENARIOS_AND_DEFAULT_INSTANCE_NAMES = (
    ("A", "test-a"),
    ("B", "test-b"),
    ("C", "test-c"),
    ("D", "test-d"),
    ("E", "test-e"),
    ("F", "test-f"),
    ("T", "test-t"),
)


def _run_configure(runner: CliRunner, tmp_path: Path, scenario: str, instance_name: str):
    return runner.invoke(
        init,
        [
            "configure",
            "--scenario",
            scenario,
            "--instance-name",
            instance_name,
            "--instances-dir",
            str(tmp_path),
            "--non-interactive",
            "--no-gh",
        ],
    )


def _run_secrets(runner: CliRunner, tmp_path: Path, instance_name: str):
    return runner.invoke(
        init,
        [
            "secrets",
            "--instance",
            instance_name,
            "--instances-dir",
            str(tmp_path),
            "--non-interactive",
        ],
    )


def _run_bootstrap_dry(runner: CliRunner, tmp_path: Path, instance_name: str):
    """Bootstrap with all execution skip-flags — exercises only the
    precondition check + announce. No DB / API contact."""
    return runner.invoke(
        init,
        [
            "bootstrap",
            "--instance",
            instance_name,
            "--instances-dir",
            str(tmp_path),
            "--skip-alembic",
            "--skip-seed",
            "--skip-validate",
        ],
    )


# ── per-scenario e2e ────────────────────────────────────────────────────


@pytest.mark.parametrize("scenario_code, instance_name", SCENARIOS_AND_DEFAULT_INSTANCE_NAMES)
def test_e2e_configure_secrets_bootstrap(
    runner: CliRunner,
    tmp_path: Path,
    scenario_code: str,
    instance_name: str,
):
    """Walk every scenario through configure → secrets → bootstrap (dry).
    All three subcommands must exit 0; the resulting instance dir must
    pass the precondition check."""
    cfg = _run_configure(runner, tmp_path, scenario_code, instance_name)
    assert cfg.exit_code == 0, f"configure failed for {scenario_code}: {cfg.output}"

    secrets = _run_secrets(runner, tmp_path, instance_name)
    assert secrets.exit_code == 0, f"secrets failed for {scenario_code}: {secrets.output}"

    bootstrap = _run_bootstrap_dry(runner, tmp_path, instance_name)
    assert bootstrap.exit_code == 0, (
        f"bootstrap precondition check failed for {scenario_code}: {bootstrap.output}"
    )
    assert "Bootstrap complete." in bootstrap.output


@pytest.mark.parametrize("scenario_code, instance_name", SCENARIOS_AND_DEFAULT_INSTANCE_NAMES)
def test_e2e_jackpot_toml_round_trips(
    runner: CliRunner,
    tmp_path: Path,
    scenario_code: str,
    instance_name: str,
):
    """The generated jackpot.toml parses cleanly and records the
    scenario code that was passed to configure."""
    _run_configure(runner, tmp_path, scenario_code, instance_name)
    parsed = toml.loads((tmp_path / instance_name / "jackpot.toml").read_text())
    assert parsed["scenario"]["code"] == scenario_code


@pytest.mark.parametrize("scenario_code, instance_name", SCENARIOS_AND_DEFAULT_INSTANCE_NAMES)
def test_e2e_env_local_has_compose_profile(
    runner: CliRunner,
    tmp_path: Path,
    scenario_code: str,
    instance_name: str,
):
    """COMPOSE_PROFILES is the docker-compose contract — every
    scenario must emit one."""
    _run_configure(runner, tmp_path, scenario_code, instance_name)
    env_text = (tmp_path / instance_name / ".env.local").read_text()
    assert "COMPOSE_PROFILES=" in env_text
    expected_profile = get_scenario(scenario_code).defaults.compose_profile
    assert f"COMPOSE_PROFILES={expected_profile}" in env_text


@pytest.mark.parametrize("scenario_code, instance_name", SCENARIOS_AND_DEFAULT_INSTANCE_NAMES)
def test_e2e_values_local_yaml_parses(
    runner: CliRunner,
    tmp_path: Path,
    scenario_code: str,
    instance_name: str,
):
    """Helm values overlay must be valid YAML for any scenario."""
    _run_configure(runner, tmp_path, scenario_code, instance_name)
    text = (tmp_path / instance_name / "values.local.yaml").read_text()
    body = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
    parsed = yaml.safe_load(body)
    assert parsed["replicaCount"] == get_scenario(scenario_code).defaults.replica_count


# ── secret presence per scenario ────────────────────────────────────────


@pytest.mark.parametrize("scenario_code, instance_name", SCENARIOS_AND_DEFAULT_INSTANCE_NAMES)
def test_e2e_jwt_signing_key_present(
    runner: CliRunner,
    tmp_path: Path,
    scenario_code: str,
    instance_name: str,
):
    """Every scenario gets a JWT signing key (every backend needs one
    for token issuance)."""
    _run_configure(runner, tmp_path, scenario_code, instance_name)
    _run_secrets(runner, tmp_path, instance_name)
    jwt_path = tmp_path / instance_name / "secrets" / "jwt_signing_key.txt"
    assert jwt_path.exists()
    # 64-char hex + newline = 65 bytes.
    assert len(jwt_path.read_text().strip()) == 64


@pytest.mark.parametrize(
    "scenario_code, expects_keypair",
    [
        ("A", False),
        ("B", False),
        ("C", False),
        ("D", False),
        ("E", True),
        ("F", False),
        ("T", True),
    ],
)
def test_e2e_federation_keypair_only_for_e_and_t(
    runner: CliRunner,
    tmp_path: Path,
    scenario_code: str,
    expects_keypair: bool,
):
    instance_name = f"test-{scenario_code.lower()}"
    _run_configure(runner, tmp_path, scenario_code, instance_name)
    _run_secrets(runner, tmp_path, instance_name)
    priv = tmp_path / instance_name / "secrets" / "federation_private_key.pem"
    pub = tmp_path / instance_name / "secrets" / "federation_public_key.pem"
    assert priv.exists() is expects_keypair
    assert pub.exists() is expects_keypair


# ── committed instances/ci/ contract test ──────────────────────────────


class TestCommittedCiFixture:
    """The committed `instances/ci/` directory MUST stay in sync with
    what `jackpot init configure --scenario F` would produce. If a
    contributor changes scenario F defaults without regenerating
    `instances/ci/`, this test catches the drift.

    Critical Rule 56: the committed CI fixture is the contract CI runs
    against. Drift between it and the registry defaults breaks both
    sides.
    """

    def test_committed_ci_jackpot_toml_has_scenario_f(self):
        ci_toml = _REPO_ROOT / "instances" / "ci" / "jackpot.toml"
        if not ci_toml.exists():
            pytest.skip("instances/ci/jackpot.toml not present in this checkout")
        parsed = toml.loads(ci_toml.read_text())
        assert parsed["scenario"]["code"] == "F"
        assert parsed["meta"]["instance_name"] == "ci"

    def test_committed_ci_uses_synthetic_identity(self):
        """Critical Rule 56: zero real operator identity values."""
        ci_toml = _REPO_ROOT / "instances" / "ci" / "jackpot.toml"
        if not ci_toml.exists():
            pytest.skip("instances/ci/jackpot.toml not present in this checkout")
        parsed = toml.loads(ci_toml.read_text())
        # The synthetic CI identity values match the F scenario's
        # baked-in defaults.
        defaults = parsed["defaults"]
        assert defaults["host_organization_name"] == "CI Test Organization"
        assert defaults["host_organization_email"] == "ci@example.org"
        assert defaults["deployment_url"] == "http://localhost:8000"

    def test_committed_ci_env_local_has_compose_profile_ci(self):
        env_local = _REPO_ROOT / "instances" / "ci" / ".env.local"
        if not env_local.exists():
            pytest.skip("instances/ci/.env.local not present in this checkout")
        assert "COMPOSE_PROFILES=ci" in env_local.read_text()

    def test_committed_ci_jwt_signing_key_present_and_64_hex(self):
        jwt_path = _REPO_ROOT / "instances" / "ci" / "secrets" / "jwt_signing_key.txt"
        if not jwt_path.exists():
            pytest.skip("instances/ci/secrets/jwt_signing_key.txt not present")
        key = jwt_path.read_text().strip()
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_committed_ci_no_federation_keys(self):
        """Scenario F doesn't need federation; the committed fixture
        must not ship a private federation key."""
        for forbidden in (
            "federation_private_key.pem",
            "federation_public_key.pem",
            "oauth_client_secret.txt",
        ):
            path = _REPO_ROOT / "instances" / "ci" / "secrets" / forbidden
            assert not path.exists(), (
                f"Critical Rule 56 violation: instances/ci/secrets/{forbidden} "
                "exists; scenario F should never have this file."
            )

    def test_committed_ci_no_real_operator_strings_anywhere(self):
        """Belt-and-suspenders: scan every committed CI file for known
        operator-specific strings."""
        forbidden_strings = (
            "gotero@linuxprophet",
            "gotero3@asu",
            "linuxprophet",
            "Example Lab Alpha",
            "Example Lab Beta",
            "Example Lab Gamma",
            "gotero3-acdp-488517",
            "Example Lab Delta",
        )
        ci_dir = _REPO_ROOT / "instances" / "ci"
        if not ci_dir.exists():
            pytest.skip("instances/ci/ not present in this checkout")
        for path in ci_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                content = path.read_text()
            except UnicodeDecodeError:
                continue
            for forbidden in forbidden_strings:
                assert forbidden not in content, (
                    f"Critical Rule 56 violation: {path} contains "
                    f"operator-specific string {forbidden!r}"
                )


# ── Idempotency at the CLI boundary ─────────────────────────────────────


def test_e2e_configure_then_configure_again_overwrites_non_secrets(
    runner: CliRunner, tmp_path: Path
):
    _run_configure(runner, tmp_path, "B", "rerun")
    _run_secrets(runner, tmp_path, "rerun")
    jwt_first = (tmp_path / "rerun" / "secrets" / "jwt_signing_key.txt").read_text()

    # Mutate jackpot.toml to confirm rerun overwrites it.
    toml_path = tmp_path / "rerun" / "jackpot.toml"
    toml_path.write_text(toml_path.read_text() + "\n# operator note\n")

    result = _run_configure(runner, tmp_path, "B", "rerun")
    assert result.exit_code == 0

    # toml was overwritten (default behavior).
    assert "# operator note" not in toml_path.read_text()

    # Secret was preserved.
    jwt_second = (tmp_path / "rerun" / "secrets" / "jwt_signing_key.txt").read_text()
    assert jwt_first == jwt_second


def test_e2e_secrets_rerun_with_regenerate_non_interactive_preserves(
    runner: CliRunner, tmp_path: Path
):
    """Decision 7: --regenerate-secrets in non-interactive mode never
    silently rotates. The confirm callback returns False; secrets
    survive."""
    _run_configure(runner, tmp_path, "E", "rotate-test")
    _run_secrets(runner, tmp_path, "rotate-test")
    priv_first = (tmp_path / "rotate-test" / "secrets" / "federation_private_key.pem").read_bytes()

    result = runner.invoke(
        init,
        [
            "secrets",
            "--instance",
            "rotate-test",
            "--instances-dir",
            str(tmp_path),
            "--non-interactive",
            "--regenerate-secrets",
        ],
    )
    assert result.exit_code == 0
    priv_second = (tmp_path / "rotate-test" / "secrets" / "federation_private_key.pem").read_bytes()
    assert priv_first == priv_second
