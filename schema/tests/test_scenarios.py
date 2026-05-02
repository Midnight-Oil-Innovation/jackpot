"""Unit tests for jackpot_scenarios.scenarios — the 7-scenario registry."""

import pytest
from jackpot_scenarios import (
    ALL_SCENARIOS,
    SCENARIO_REGISTRY,
    ScenarioDefaults,
    get_scenario,
)
from jackpot_scenarios.scenarios import CURRENT_SCHEMA_VERSION, SECRET_FIELD_NAMES
from pydantic import ValidationError


class TestRegistryShape:
    def test_seven_scenarios_present(self):
        assert len(ALL_SCENARIOS) == 7
        assert {s.code for s in ALL_SCENARIOS} == {"A", "B", "C", "D", "E", "F", "T"}

    def test_registry_keyed_by_code(self):
        assert set(SCENARIO_REGISTRY) == {"A", "B", "C", "D", "E", "F", "T"}
        for code, scenario in SCENARIO_REGISTRY.items():
            assert scenario.code == code

    def test_get_scenario_by_uppercase_code(self):
        assert get_scenario("A").code == "A"
        assert get_scenario("T").code == "T"

    def test_get_scenario_normalises_case_and_whitespace(self):
        # Operators may type "t" or "  T  " — accept and normalise.
        assert get_scenario("t").code == "T"
        assert get_scenario("  a  ").code == "A"

    def test_get_scenario_unknown_raises_with_valid_codes_listed(self):
        with pytest.raises(KeyError, match="Valid codes:"):
            get_scenario("Z")


class TestScenarioCare:
    """Scenario T's defaults must satisfy CARE Principles by default —
    operator opts OUT, never opts IN."""

    def test_deletion_on_request_enabled(self):
        # CARE Authority-to-Control: tombstone-and-vacuum on consent withdrawal.
        assert get_scenario("T").defaults.deletion_on_request is True

    def test_auto_publish_to_insdc_disabled(self):
        # CARE Ethics: explicit per-sample approval, never auto-publish.
        assert get_scenario("T").defaults.auto_publish_to_insdc is False

    def test_federation_off_by_default(self):
        # CARE Collective Benefit: operator picks who they trust.
        assert get_scenario("T").defaults.federation_enabled is False
        assert get_scenario("T").defaults.federation_role == "off"

    def test_care_principles_enforcement_on(self):
        assert get_scenario("T").defaults.care_principles_enforced is True

    def test_consent_workflow_enabled(self):
        assert get_scenario("T").defaults.consent_workflow_enabled is True

    def test_dlp_enabled(self):
        # PII handling on by default for sovereignty deployments.
        assert get_scenario("T").defaults.dlp_enabled is True


class TestScenarioCi:
    """Scenario F (CI) must be runnable headless with no external deps."""

    def test_scheduler_off(self):
        assert get_scenario("F").defaults.scheduler_enabled is False

    def test_dlp_off(self):
        assert get_scenario("F").defaults.dlp_enabled is False

    def test_mock_auth(self):
        assert get_scenario("F").defaults.auth_method == "mock"
        assert get_scenario("F").defaults.oauth_provider is None

    def test_local_storage(self):
        # No MinIO or GCS dependency in CI.
        assert get_scenario("F").defaults.storage_backend == "local"

    def test_local_pipeline_executor(self):
        assert get_scenario("F").defaults.pipeline_executor == "local"

    def test_no_federation(self):
        assert get_scenario("F").defaults.federation_role == "off"

    def test_synthetic_identity_baked_in(self):
        # CI's identity is synthetic and committed (Critical Rule 56);
        # no real-operator identity should ever land in instances/ci/.
        defaults = get_scenario("F").defaults
        assert defaults.host_organization_name == "CI Test Organization"
        assert defaults.host_organization_email == "ci@example.org"


class TestScenarioCloudPosture:
    """Production-ish scenarios (B, C, D, E) share a baseline cloud
    posture — OAuth/SSO, managed Postgres, PITR on, DLP on."""

    @pytest.mark.parametrize("code", ["B", "C", "D", "E"])
    def test_managed_postgres(self, code):
        assert get_scenario(code).defaults.database_engine == "cloud-sql"

    @pytest.mark.parametrize("code", ["B", "C", "D", "E"])
    def test_pitr_enabled(self, code):
        assert get_scenario(code).defaults.database_pitr_enabled is True

    @pytest.mark.parametrize("code", ["B", "C", "D", "E"])
    def test_dlp_enabled(self, code):
        assert get_scenario(code).defaults.dlp_enabled is True

    @pytest.mark.parametrize("code", ["B", "C", "E"])
    def test_oauth_for_non_saas(self, code):
        # B/C/E use OAuth; D uses SSO.
        defaults = get_scenario(code).defaults
        assert defaults.auth_method == "oauth"
        assert defaults.oauth_provider == "google"

    def test_sso_for_saas(self):
        defaults = get_scenario("D").defaults
        assert defaults.auth_method == "sso"
        assert defaults.oauth_provider is None


class TestScenarioFederation:
    def test_only_e_has_federation_enabled_by_default(self):
        for scenario in ALL_SCENARIOS:
            if scenario.code == "E":
                assert scenario.defaults.federation_enabled is True
                assert scenario.defaults.federation_role == "member"
            else:
                assert scenario.defaults.federation_enabled is False


class TestScenarioImmutability:
    def test_scenario_defaults_frozen(self):
        defaults = get_scenario("A").defaults
        with pytest.raises(ValidationError):
            defaults.deletion_on_request = True  # type: ignore[misc]

    def test_scenario_frozen(self):
        scenario = get_scenario("A")
        with pytest.raises(ValidationError):
            scenario.code = "B"  # type: ignore[misc]


class TestSecretFieldClassification:
    def test_known_secret_fields(self):
        # Decision 5+7: these MUST flow through instances/<name>/secrets/.
        expected = {
            "secret_key",
            "google_oauth_client_secret",
            "ncbi_api_key",
            "jackpot_api_token",
            "federation_private_key",
        }
        assert expected == SECRET_FIELD_NAMES

    def test_secret_field_names_accessible_from_instance(self):
        defaults = get_scenario("B").defaults
        assert "secret_key" in defaults.secret_field_names
        assert "ncbi_api_key" in defaults.secret_field_names


class TestScenarioCodeStability:
    """The 7 scenario codes are part of the public contract — operators
    type them, CI uses them, the spec references them. Renaming or
    repurposing a code is a breaking change."""

    def test_code_to_name_mapping(self):
        names = {s.code: s.name for s in ALL_SCENARIOS}
        assert names["A"].startswith("Single laptop")
        assert names["B"].startswith("Single organisation")
        assert names["C"].startswith("Multi-lab")
        assert names["D"].startswith("Hosted multi-tenant")
        assert names["E"].startswith("Federation")
        assert names["F"].startswith("CI")
        assert names["T"].startswith("Tribal")


class TestSchemaVersion:
    def test_current_schema_version_is_string(self):
        # Decision 9: the version is a semver-like string for
        # `jackpot init reconfigure`'s migration plan.
        assert isinstance(CURRENT_SCHEMA_VERSION, str)
        assert "." in CURRENT_SCHEMA_VERSION

    def test_scenario_defaults_classvar_matches_module_constant(self):
        assert ScenarioDefaults.schema_version == CURRENT_SCHEMA_VERSION


class TestBucketDefaults:
    """Decision 4 + F4 finding: buckets are scenario-defaulted +
    operator-overridable. All 7 must be present on every scenario."""

    @pytest.mark.parametrize("code", ["A", "B", "C", "D", "E", "F", "T"])
    def test_all_seven_buckets_present(self, code):
        defaults = get_scenario(code).defaults
        for bucket_field in (
            "bucket_sequences",
            "bucket_raw",
            "bucket_staging",
            "bucket_datasets",
            "bucket_submissions",
            "bucket_work",
            "bucket_results",
        ):
            assert getattr(defaults, bucket_field), f"{code}.{bucket_field} is unset"


class TestExtraFieldsForbidden:
    """ScenarioDefaults uses `extra='forbid'` so adding a new field at
    one site must be added everywhere. Catches typos like
    `delete_on_request=True` (missing the `ion`)."""

    def test_typo_field_rejected(self):
        with pytest.raises(ValidationError):
            ScenarioDefaults(deletion_on_requesst=True)  # type: ignore[call-arg]
