"""
ScenarioDefaults — Pydantic model for the install-time config of a JACKPOT
deployment. One instance per scenario (A through F + T); the `jackpot init`
CLI selects one and writes its values into instances/<name>/.

The defaults are the most-restrictive-safe choice for each scenario:
- Production scenarios (B, C, D) default to OAuth + DLP + cloud storage
- Tribal scenarios (T) default to deletion-on-request + no-auto-publish
  + federation OFF (CARE Principles: see
  governance/care-principles-and-tribal-data-sovereignty.md)
- CI (F) defaults to mock auth + filesystem storage + scheduler off
- Laptop (A) is the least restrictive — single-user dev convenience

Operators override defaults via `jackpot init` prompts. Any field listed
in `secret_field_names` flows through instances/<name>/secrets/ (0600
perms, gitignored) rather than .env.local.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

# Schema version of the ScenarioDefaults model itself. Bumped when the
# field set changes in a way `jackpot init reconfigure` needs to migrate.
# Decision 9 in the design lockdown.
CURRENT_SCHEMA_VERSION = "1.0"


ScenarioCode = Literal["A", "B", "C", "D", "E", "F", "T"]
ComposeProfile = Literal["laptop", "single-org", "multi-tenant", "ci", "tribal"]
StorageBackend = Literal["local", "minio", "gcs", "s3"]
PipelineExecutor = Literal["local", "gcp_batch", "aws_batch", "k8s_jobs"]
AuthMethod = Literal["mock", "oauth", "sso"]
OAuthProvider = Literal["google", "okta", "auth0"]
DatabaseEngine = Literal["postgres-local", "cloud-sql", "rds-postgres"]
FederationRole = Literal["off", "member", "hub"]


# Names of fields that hold or generate SECRET values. These flow through
# instances/<name>/secrets/ (with 0600 perms) rather than .env.local.
# Per Decision 5 + Decision 7: secrets are NEVER slurped from `gh api`
# and are preserved by default on rerun unless --regenerate-secrets is
# explicitly passed.
SECRET_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "secret_key",
        "google_oauth_client_secret",
        "ncbi_api_key",
        "jackpot_api_token",
        "federation_private_key",
    }
)


class ScenarioDefaults(BaseModel):
    """The install-time config defaults for one scenario.

    Every field has a default that's safe for the named scenario. Operators
    override by typing different values at the `jackpot init` prompts;
    overrides land in instances/<name>/jackpot.toml's `[operator]` block.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # — Identity (required at install time, no scenario default; B.2.3
    #   `configure` prompts for these) —
    host_organization_name: str = Field(
        default="",
        description=(
            "The deploying operator's display name. Required for all "
            "real deploys; defaults to placeholder for laptop / CI."
        ),
    )
    host_organization_email: str = Field(
        default="",
        description="The operator's contact email for audit-log attribution.",
    )
    deployment_url: str = Field(
        default="",
        description=(
            "The public-facing URL of the JACKPOT API "
            "(e.g. https://api.your-jackpot-instance.org). "
            "Empty for laptop / CI."
        ),
    )
    cors_origins: list[str] = Field(
        default_factory=list,
        description="Whitelist of frontend origins the API will accept CORS from.",
    )

    # — Backend behaviour —
    deletion_on_request: bool = False
    """CARE Authority-to-Control: tombstone-and-vacuum on consent withdrawal."""

    auto_publish_to_insdc: bool = False
    """Auto-submit approved samples to NCBI/INSDC. Forbidden for Scenario T."""

    federation_enabled: bool = False
    """Federation router available."""

    dlp_enabled: bool = False
    """Cloud DLP scanner runs on every metadata write."""

    scheduler_enabled: bool = True
    """Background APScheduler jobs (scrubber queue, access-request expiry)."""

    care_principles_enforced: bool = False
    """Adds extra CARE-tagged audit-log events (consent grant, withdrawal,
    derivation). On for Scenario T."""

    consent_workflow_enabled: bool = False
    """UI flow for consent grant + withdrawal at sample creation."""

    # — Compose / Helm shape —
    compose_profile: ComposeProfile = "laptop"
    """Selects which compose services run (Decision 2: docker-compose
    `profiles:` keys map to this)."""

    replica_count: int = 1
    """Number of API pod replicas (Helm chart only; ignored for laptop)."""

    storage_backend: StorageBackend = "local"
    """Object-storage flavour the backend talks to."""

    pipeline_executor: PipelineExecutor = "local"
    """Where Nextflow runs."""

    # — Auth shape —
    auth_method: AuthMethod = "mock"
    oauth_provider: OAuthProvider | None = None
    """`google` for Scenarios B/C/T; `okta` or `auth0` for Scenario D;
    None for mock."""

    # — Database —
    database_engine: DatabaseEngine = "postgres-local"
    database_pitr_enabled: bool = False
    database_backup_retention_days: int = 0

    # — Federation —
    federation_role: FederationRole = "off"
    federation_peers: list[str] = Field(
        default_factory=list,
        description="Initial peer list (URLs); operator adds real peers later via admin UI.",
    )

    # — Buckets (operator-overridable; defaults follow `jackpot-<env>-*`
    #   convention) —
    bucket_sequences: str = "jackpot-sequences"
    bucket_raw: str = "jackpot-raw"
    bucket_staging: str = "jackpot-staging"
    bucket_datasets: str = "jackpot-datasets"
    bucket_submissions: str = "jackpot-submissions"
    bucket_work: str = "jackpot-work"
    bucket_results: str = "jackpot-results"

    # — Rate limiting (sane defaults; see backend.config.Settings for the
    #   live values) —
    rate_limit_enabled: bool = True
    rate_limit_auth: str = "5/minute"
    rate_limit_ingest: str = "60/minute"

    # — Class-level metadata used by versioning + the registry —
    schema_version: ClassVar[str] = CURRENT_SCHEMA_VERSION

    @property
    def secret_field_names(self) -> frozenset[str]:
        """Field names whose values must flow through instances/<name>/secrets/.

        Static for now (defined at module level); a future ScenarioDefaults
        subclass could extend it if a scenario adds scenario-specific
        secrets (e.g. consent_workflow_signing_key for Scenario T)."""
        return SECRET_FIELD_NAMES


class Scenario(BaseModel):
    """A named install scenario — couples the code (A/B/C/D/E/F/T) with
    its default ScenarioDefaults and a human-readable name + description.
    The detector returns one of these."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: ScenarioCode
    name: str
    description: str
    defaults: ScenarioDefaults


# ── 7-scenario registry ──────────────────────────────────────────────────

SCENARIO_A = Scenario(
    code="A",
    name="Single laptop / academic dev",
    description=(
        "Single bioinformatician on a laptop. Docker Compose stack, no "
        "cloud dependencies, mock auth, MinIO storage, local Nextflow."
    ),
    defaults=ScenarioDefaults(
        host_organization_name="Local Dev Lab",
        host_organization_email="dev@example.org",
        deployment_url="http://localhost:8000",
        cors_origins=["http://localhost:8501"],
        compose_profile="laptop",
        replica_count=1,
        storage_backend="minio",
        pipeline_executor="local",
        auth_method="mock",
        oauth_provider=None,
        database_engine="postgres-local",
        database_pitr_enabled=False,
        scheduler_enabled=True,
        federation_role="off",
    ),
)

SCENARIO_B = Scenario(
    code="B",
    name="Single organisation on cloud",
    description=(
        "A single public-health org running on GCP/AWS/Azure. OAuth, "
        "managed Postgres, GCS storage, GCP Batch for pipelines, DLP on."
    ),
    defaults=ScenarioDefaults(
        compose_profile="single-org",
        replica_count=2,
        storage_backend="gcs",
        pipeline_executor="gcp_batch",
        auth_method="oauth",
        oauth_provider="google",
        database_engine="cloud-sql",
        database_pitr_enabled=True,
        database_backup_retention_days=14,
        dlp_enabled=True,
        scheduler_enabled=True,
        federation_role="off",
    ),
)

SCENARIO_C = Scenario(
    code="C",
    name="Multi-lab agency",
    description=(
        "Multi-lab agency (typical state health department, Big Cities "
        "Health Coalition member). Same posture as B with more replicas, "
        "longer backup retention, multiple seeded labs."
    ),
    defaults=ScenarioDefaults(
        compose_profile="single-org",
        replica_count=3,
        storage_backend="gcs",
        pipeline_executor="gcp_batch",
        auth_method="oauth",
        oauth_provider="google",
        database_engine="cloud-sql",
        database_pitr_enabled=True,
        database_backup_retention_days=30,
        dlp_enabled=True,
        scheduler_enabled=True,
        federation_role="off",
    ),
)

SCENARIO_D = Scenario(
    code="D",
    name="Hosted multi-tenant SaaS",
    description=(
        "Hosted SaaS provider serving multiple tenants. SSO auth, "
        "multi-tenancy middleware enabled, billing module on. Gated on "
        "P0c multi-tenancy schema before bootstrap is complete."
    ),
    defaults=ScenarioDefaults(
        compose_profile="multi-tenant",
        replica_count=5,
        storage_backend="gcs",
        pipeline_executor="gcp_batch",
        auth_method="sso",
        oauth_provider=None,
        database_engine="cloud-sql",
        database_pitr_enabled=True,
        database_backup_retention_days=30,
        dlp_enabled=True,
        scheduler_enabled=True,
        federation_role="off",
    ),
)

SCENARIO_E = Scenario(
    code="E",
    name="Federation member",
    description=(
        "JACKPOT instance that peers with other JACKPOT instances. Same "
        "shape as B/C plus federation router on. Generates an ed25519 "
        "keypair at install time (Decision 5)."
    ),
    defaults=ScenarioDefaults(
        compose_profile="single-org",
        replica_count=2,
        storage_backend="gcs",
        pipeline_executor="gcp_batch",
        auth_method="oauth",
        oauth_provider="google",
        database_engine="cloud-sql",
        database_pitr_enabled=True,
        database_backup_retention_days=14,
        dlp_enabled=True,
        scheduler_enabled=True,
        federation_role="member",
        federation_enabled=True,
    ),
)

SCENARIO_F = Scenario(
    code="F",
    name="CI / e2e test harness",
    description=(
        "Synthetic test environment. Mock auth, filesystem storage, no "
        "DLP, no NCBI/GISAID, no federation, no scheduler. The "
        "instances/ci/ directory is committed (Critical Rule 56)."
    ),
    defaults=ScenarioDefaults(
        host_organization_name="CI Test Organization",
        host_organization_email="ci@example.org",
        deployment_url="http://localhost:8000",
        cors_origins=["http://localhost:8501"],
        compose_profile="ci",
        replica_count=1,
        storage_backend="local",
        pipeline_executor="local",
        auth_method="mock",
        oauth_provider=None,
        database_engine="postgres-local",
        database_pitr_enabled=False,
        scheduler_enabled=False,
        federation_role="off",
        dlp_enabled=False,
    ),
)

SCENARIO_T = Scenario(
    code="T",
    name="Tribal-sovereignty deployment",
    description=(
        "Tribal nation, Tribal Epidemiology Center, or Indigenous-data-"
        "sovereignty deployment. CARE Principles enforced: "
        "deletion-on-request ON, auto-publish OFF, federation OFF by "
        "default, consent workflow ON. "
        "See governance/care-principles-and-tribal-data-sovereignty.md."
    ),
    defaults=ScenarioDefaults(
        compose_profile="tribal",
        replica_count=1,
        storage_backend="local",
        pipeline_executor="local",
        auth_method="oauth",
        oauth_provider="google",
        database_engine="postgres-local",
        database_pitr_enabled=True,
        database_backup_retention_days=30,
        dlp_enabled=True,
        scheduler_enabled=True,
        federation_role="off",
        federation_enabled=False,
        deletion_on_request=True,
        auto_publish_to_insdc=False,
        care_principles_enforced=True,
        consent_workflow_enabled=True,
    ),
)


ALL_SCENARIOS: tuple[Scenario, ...] = (
    SCENARIO_A,
    SCENARIO_B,
    SCENARIO_C,
    SCENARIO_D,
    SCENARIO_E,
    SCENARIO_F,
    SCENARIO_T,
)


SCENARIO_REGISTRY: dict[ScenarioCode, Scenario] = {s.code: s for s in ALL_SCENARIOS}


def get_scenario(code: str) -> Scenario:
    """Look up a scenario by code (`A`, `B`, ..., `T`).

    Raises KeyError on unknown code. Codes are upper-case single letters.
    """
    code_upper = code.strip().upper()
    if code_upper not in SCENARIO_REGISTRY:
        valid = ", ".join(sorted(SCENARIO_REGISTRY))
        raise KeyError(f"Unknown scenario {code!r}. Valid codes: {valid}")
    return SCENARIO_REGISTRY[code_upper]  # type: ignore[index]
