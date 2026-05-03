"""Tests for `jackpot.init.writers` — the file-emitter library."""

from __future__ import annotations

from pathlib import Path

import pytest
import toml
import yaml
from jackpot_scenarios import get_scenario
from jackpot_scenarios.scenarios import CURRENT_SCHEMA_VERSION

from jackpot.init.writers import (
    is_secret_path,
    render_env_local,
    render_jackpot_toml,
    render_readme_md,
    render_seed_sql,
    render_values_local_yaml,
    write_instance,
    write_with_idempotency_check,
)

# ── is_secret_path ──────────────────────────────────────────────────────


class TestIsSecretPath:
    def test_anything_under_secrets_dir(self):
        assert is_secret_path(Path("instances/foo/secrets/anything.txt"))

    def test_known_filename_at_any_depth(self):
        assert is_secret_path(Path("anywhere/jwt_signing_key.txt"))
        assert is_secret_path(Path("federation_private_key.pem"))
        assert is_secret_path(Path("oauth_client_secret.txt"))

    def test_non_secret_files(self):
        assert not is_secret_path(Path("instances/foo/jackpot.toml"))
        assert not is_secret_path(Path("instances/foo/.env.local"))
        assert not is_secret_path(Path("instances/foo/values.local.yaml"))


# ── write_with_idempotency_check ────────────────────────────────────────


class TestIdempotencyCheck:
    def test_writes_new_file(self, tmp_path: Path):
        target = tmp_path / "new.txt"
        assert write_with_idempotency_check(target, "hello") is True
        assert target.read_text() == "hello"

    def test_overwrites_existing_non_secret_by_default(self, tmp_path: Path):
        target = tmp_path / "x.txt"
        target.write_text("old")
        assert write_with_idempotency_check(target, "new") is True
        assert target.read_text() == "new"

    def test_preserves_existing_non_secret_with_flag(self, tmp_path: Path):
        target = tmp_path / "x.txt"
        target.write_text("old")
        assert write_with_idempotency_check(target, "new", overwrite_non_secrets=False) is False
        assert target.read_text() == "old"

    def test_preserves_existing_secret_by_default(self, tmp_path: Path):
        target = tmp_path / "secrets" / "jwt_signing_key.txt"
        target.parent.mkdir(parents=True)
        target.write_text("ORIGINAL_SECRET")
        assert write_with_idempotency_check(target, "NEW_SECRET") is False
        assert target.read_text() == "ORIGINAL_SECRET"

    def test_overwrites_secret_with_regenerate_flag(self, tmp_path: Path):
        target = tmp_path / "secrets" / "jwt_signing_key.txt"
        target.parent.mkdir(parents=True)
        target.write_text("ORIGINAL")
        assert write_with_idempotency_check(target, "NEW", regenerate_secrets=True) is True
        assert target.read_text() == "NEW"

    def test_secret_files_get_0600_perms(self, tmp_path: Path):
        target = tmp_path / "secrets" / "jwt_signing_key.txt"
        write_with_idempotency_check(target, "x")
        mode = target.stat().st_mode & 0o777
        assert mode == 0o600


# ── render_jackpot_toml ─────────────────────────────────────────────────


class TestJackpotToml:
    def test_round_trip_via_toml_loader(self):
        scenario = get_scenario("T")
        rendered = render_jackpot_toml(
            scenario=scenario,
            operator_overrides={
                "host_organization_name": "Example Tribal HD",
                "host_organization_email": "admin@tribal.example.org",
                "deployment_url": "https://api.example.org",
                "cors_origins": ["https://api.example.org"],
            },
            instance_name="tribal",
        )
        parsed = toml.loads(rendered)
        assert parsed["meta"]["schema_version"] == CURRENT_SCHEMA_VERSION
        assert parsed["meta"]["instance_name"] == "tribal"
        assert parsed["scenario"]["code"] == "T"
        assert parsed["operator"]["host_organization_name"] == "Example Tribal HD"
        assert parsed["defaults"]["deletion_on_request"] is True

    def test_secrets_excluded_from_operator_block(self):
        scenario = get_scenario("B")
        rendered = render_jackpot_toml(
            scenario=scenario,
            operator_overrides={
                "host_organization_name": "Example Org",
                "ncbi_api_key": "shouldnotappear",  # secret — filtered
                "secret_key": "alsoshouldnotappear",
            },
            instance_name="staging",
        )
        parsed = toml.loads(rendered)
        assert "ncbi_api_key" not in parsed["operator"]
        assert "secret_key" not in parsed["operator"]
        assert "shouldnotappear" not in rendered

    def test_empty_overrides_omitted(self):
        scenario = get_scenario("A")
        rendered = render_jackpot_toml(
            scenario=scenario,
            operator_overrides={
                "host_organization_name": "",
                "deployment_url": None,
                "cors_origins": [],
            },
            instance_name="local",
        )
        parsed = toml.loads(rendered)
        assert parsed["operator"] == {}


# ── render_env_local ────────────────────────────────────────────────────


class TestEnvLocal:
    def test_compose_profiles_set(self):
        scenario = get_scenario("T")
        text = render_env_local(
            scenario=scenario,
            operator_overrides={},
            instance_dir=Path("instances/tribal"),
        )
        assert "COMPOSE_PROFILES=tribal" in text

    def test_dlp_off_for_ci(self):
        scenario = get_scenario("F")
        text = render_env_local(
            scenario=scenario,
            operator_overrides={},
            instance_dir=Path("instances/ci-local"),
        )
        assert "DLP_ENABLED=false" in text
        assert "SCHEDULER_ENABLED=false" in text

    def test_operator_overrides_applied(self):
        scenario = get_scenario("B")
        text = render_env_local(
            scenario=scenario,
            operator_overrides={
                "host_organization_name": "Example Org",
                "deployment_url": "https://api.example.org",
                "cors_origins": ["https://app.example.org"],
            },
            instance_dir=Path("instances/staging"),
        )
        assert "HOST_ORGANIZATION_NAME=Example Org" in text
        assert "JACKPOT_API_URL=https://api.example.org" in text
        assert "CORS_ORIGINS=https://app.example.org" in text

    def test_secret_placeholders_documented(self):
        scenario = get_scenario("B")
        text = render_env_local(
            scenario=scenario,
            operator_overrides={},
            instance_dir=Path("instances/staging"),
        )
        # Secrets are referenced as placeholders (not as values) so
        # operators see what they need to provide separately.
        assert "SECRET_KEY" in text
        assert "secrets/jwt_signing_key.txt" in text


# ── render_values_local_yaml ────────────────────────────────────────────


class TestValuesLocalYaml:
    def test_parses_as_yaml(self):
        scenario = get_scenario("B")
        text = render_values_local_yaml(
            scenario=scenario,
            operator_overrides={
                "deployment_url": "https://api.example.org",
                "cors_origins": ["https://app.example.org"],
            },
        )
        # Strip header comment block so yaml.safe_load gets clean yaml.
        body = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
        parsed = yaml.safe_load(body)
        assert parsed["replicaCount"] == 2
        assert parsed["env"]["JACKPOT_API_URL"] == "https://api.example.org"
        assert parsed["env"]["DLP_ENABLED"] == "true"
        assert parsed["buckets"]["STORAGE_BUCKET_SEQUENCES"] == "jackpot-sequences"

    def test_replica_count_matches_scenario(self):
        for code, expected_replicas in (
            ("A", 1),
            ("B", 2),
            ("C", 3),
            ("D", 5),
            ("E", 2),
            ("F", 1),
            ("T", 1),
        ):
            scenario = get_scenario(code)
            text = render_values_local_yaml(scenario=scenario, operator_overrides={})
            body = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
            parsed = yaml.safe_load(body)
            assert parsed["replicaCount"] == expected_replicas, code


# ── render_seed_sql ─────────────────────────────────────────────────────


class TestSeedSql:
    def test_idempotent_org_rename(self):
        scenario = get_scenario("B")
        sql = render_seed_sql(
            scenario=scenario,
            operator_overrides={
                "host_organization_name": "Example Hospital",
            },
            instance_dir=Path("instances/staging"),
        )
        # WHERE matches OLD or NEW — re-running on already-renamed DB
        # is a no-op.
        assert "WHERE display_name = 'Example Org' OR display_name = 'Example Hospital'" in sql

    def test_user_email_rename(self):
        scenario = get_scenario("B")
        sql = render_seed_sql(
            scenario=scenario,
            operator_overrides={
                "host_organization_email": "admin@hospital.example.org",
            },
            instance_dir=Path("instances/staging"),
        )
        assert "WHERE email = 'admin@example.org' OR email = 'admin@hospital.example.org'" in sql

    def test_sql_quote_escaped(self):
        # Operator name with a literal apostrophe — must be doubled.
        scenario = get_scenario("B")
        sql = render_seed_sql(
            scenario=scenario,
            operator_overrides={
                "host_organization_name": "St. Mary's Hospital",
            },
            instance_dir=Path("instances/staging"),
        )
        assert "'St. Mary''s Hospital'" in sql

    def test_no_overrides_emits_explanatory_no_op(self):
        scenario = get_scenario("A")
        sql = render_seed_sql(
            scenario=scenario,
            operator_overrides={},
            instance_dir=Path("instances/local"),
        )
        assert "No operator-specific identity values provided" in sql
        # Header comment mentions "UPDATE" but no actual UPDATE statement
        # should be emitted when overrides are empty.
        assert "UPDATE organizations" not in sql
        assert "UPDATE users" not in sql


# ── render_readme_md ────────────────────────────────────────────────────


class TestReadmeMd:
    def test_includes_scenario_metadata(self):
        scenario = get_scenario("T")
        readme = render_readme_md(scenario=scenario, instance_name="tribal")
        assert "Tribal-sovereignty" in readme
        assert "tribal" in readme
        assert "jackpot init bootstrap --instance tribal" in readme


# ── write_instance (orchestration) ──────────────────────────────────────


class TestWriteInstance:
    def test_writes_all_five_files(self, tmp_path: Path):
        scenario = get_scenario("B")
        instance_dir = tmp_path / "staging"
        written = write_instance(
            scenario=scenario,
            operator_overrides={
                "host_organization_name": "Example Org",
                "host_organization_email": "admin@example.org",
                "deployment_url": "https://api.example.org",
            },
            instance_dir=instance_dir,
        )
        assert all(written.values()), written
        assert (instance_dir / "jackpot.toml").exists()
        assert (instance_dir / ".env.local").exists()
        assert (instance_dir / "values.local.yaml").exists()
        assert (instance_dir / "seed.sql").exists()
        assert (instance_dir / "README.md").exists()
        # Secrets dir is created (empty until B.2.4 runs).
        assert (instance_dir / "secrets").is_dir()

    def test_secrets_dir_has_0700_perms(self, tmp_path: Path):
        scenario = get_scenario("B")
        instance_dir = tmp_path / "staging"
        write_instance(
            scenario=scenario,
            operator_overrides={"host_organization_name": "X"},
            instance_dir=instance_dir,
        )
        secrets_dir = instance_dir / "secrets"
        mode = secrets_dir.stat().st_mode & 0o777
        assert mode == 0o700

    def test_rerun_preserves_secrets_overwrites_non_secrets(self, tmp_path: Path):
        scenario = get_scenario("B")
        instance_dir = tmp_path / "staging"
        write_instance(
            scenario=scenario,
            operator_overrides={"host_organization_name": "First Run"},
            instance_dir=instance_dir,
        )
        # Plant a fake secret file before re-running.
        secret_file = instance_dir / "secrets" / "jwt_signing_key.txt"
        secret_file.write_text("ORIGINAL_KEY")

        written = write_instance(
            scenario=scenario,
            operator_overrides={"host_organization_name": "Second Run"},
            instance_dir=instance_dir,
        )
        # All non-secret files were rewritten.
        assert all(written.values())
        # Secret file is intact.
        assert secret_file.read_text() == "ORIGINAL_KEY"
        # New operator value reached the new TOML.
        assert "Second Run" in (instance_dir / "jackpot.toml").read_text()

    def test_rerun_with_no_overwrite_preserves_non_secrets(self, tmp_path: Path):
        scenario = get_scenario("B")
        instance_dir = tmp_path / "staging"
        write_instance(
            scenario=scenario,
            operator_overrides={"host_organization_name": "First"},
            instance_dir=instance_dir,
        )
        # Operator hand-edited the TOML.
        toml_file = instance_dir / "jackpot.toml"
        original_text = toml_file.read_text()
        toml_file.write_text(original_text + "\n# operator hand-edit\n")

        written = write_instance(
            scenario=scenario,
            operator_overrides={"host_organization_name": "Second"},
            instance_dir=instance_dir,
            overwrite_non_secrets=False,
        )
        # All files report "preserved" (False).
        assert all(v is False for v in written.values())
        # Hand-edit survived.
        assert "# operator hand-edit" in toml_file.read_text()


# ── Lightweight cross-scenario writability sanity ──────────────────────


@pytest.mark.parametrize("code", ["A", "B", "C", "D", "E", "F", "T"])
def test_every_scenario_writes_cleanly(tmp_path: Path, code: str):
    """Each of the 7 scenarios produces a complete instance directory
    with no exceptions and parseable TOML/YAML output."""
    scenario = get_scenario(code)
    instance_dir = tmp_path / code.lower()
    written = write_instance(
        scenario=scenario,
        operator_overrides={
            "host_organization_name": f"Test Org {code}",
            "host_organization_email": f"admin-{code}@example.org",
            "deployment_url": f"https://api.{code}.example.org",
        },
        instance_dir=instance_dir,
    )
    assert all(written.values())

    parsed = toml.loads((instance_dir / "jackpot.toml").read_text())
    assert parsed["scenario"]["code"] == code

    body = "\n".join(
        line
        for line in (instance_dir / "values.local.yaml").read_text().splitlines()
        if not line.startswith("#")
    )
    yaml.safe_load(body)  # raises if malformed
