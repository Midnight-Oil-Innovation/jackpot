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


# Four install-time infrastructure shapes. Federation, multi-org tenancy and
# CARE/sovereignty are NOT scenarios — architecture.md 3.6: "scenarios
# describe install-time infrastructure configurations; everything else is
# runtime policy". They were registry D, E and T until 2026-09-03; see
# B-SCENARIO-TAXONOMY-SPLIT.
ScenarioCode = Literal["A", "B", "C", "D"]
ComposeProfile = Literal["laptop", "single-org", "hpc", "ci"]
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
    name="Self-hosted commodity infrastructure",
    description=(
        "Standard servers, not HPC and not managed Kubernetes. Spans a "
        "single bioinformatician on a laptop through an agency datacenter "
        "running JACKPOT across several Linux servers — scale is a replica "
        "setting, not a different scenario (architecture.md 3.2)."
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
    name="HPC cluster",
    description=(
        "University or institutional HPC. Apptainer rather than Docker — "
        "forced by cluster policy, not a preference (architecture.md 3.1) — "
        "institutional Lustre/GPFS storage rather than object storage, and "
        "Slurm/PBS for execution. Operated by an RC team."
    ),
    defaults=ScenarioDefaults(
        host_organization_name="Research Computing",
        host_organization_email="rc@example.org",
        deployment_url="http://localhost:8000",
        cors_origins=["http://localhost:8501"],
        compose_profile="hpc",
        replica_count=1,
        # Institutional parallel filesystem, mounted. Not object storage:
        # an HPC operator has Lustre or GPFS and no S3 endpoint.
        storage_backend="local",
        # The install-time default only. Any scenario can add executor
        # profiles post-install (architecture.md 1058), which is how a
        # laptop reaches a Slurm cluster.
        pipeline_executor="local",
        auth_method="oauth",
        oauth_provider="okta",
        database_engine="postgres-local",
        database_pitr_enabled=False,
        database_backup_retention_days=30,
        scheduler_enabled=True,
        federation_role="off",
    ),
)

SCENARIO_C = Scenario(
    code="C",
    name="Single-organisation cloud",
    description=(
        "Cloud-native Kubernetes (GKE/EKS/AKS) run by an org's IT or cloud "
        "operations team. Object storage, managed Postgres, cloud IdP. "
        "Multi-org tenancy is a runtime configuration of this scenario, not "
        "a separate one (architecture.md 3.6)."
    ),
    defaults=ScenarioDefaults(
        host_organization_name="Example Organization",
        host_organization_email="admin@example.org",
        deployment_url="https://jackpot.example.org",
        cors_origins=["https://jackpot.example.org"],
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

SCENARIO_D = Scenario(
    code="D",
    name="CI / e2e test harness",
    description=(
        "Not an operator-facing install: configuration is generated "
        "programmatically by the test harness rather than through the "
        "interactive jackpot init flow (architecture.md 3.5). Local "
        "containers, filesystem storage, mock auth, no cloud dependency."
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
        # No scheduler, no DLP: the harness drives jobs itself.
        scheduler_enabled=False,
        dlp_enabled=False,
        federation_role="off",
    ),
)


#: What the pre-2026-09-03 letters became. No compatibility shim — per
#: access_model.md 10 there is no installed base — but the retired letters
#: are still in committed docs and in instances/ci/README.md, so a person
#: who types one deserves the answer rather than "unknown scenario".
RETIRED_SCENARIO_CODES: dict[str, str] = {
    "E": (
        "E (Federation member) is not a scenario. Federation services ship in "
        "every install; add peers post-install with `jackpot peers add`. "
        "Install the infrastructure shape that matches you (A, B or C)."
    ),
    "F": "F (CI test harness) is now D.",
    "T": (
        "T (Tribal sovereignty) is not a scenario. CARE enforcement, "
        "deletion-on-request and consent workflow are runtime policy on any "
        "scenario — usually A. See architecture.md 22."
    ),
}


def retired_code_hint(code: str) -> str | None:
    """Explain a retired scenario letter, or None if it was never one."""
    return RETIRED_SCENARIO_CODES.get(code.strip().upper())


ALL_SCENARIOS: tuple[Scenario, ...] = (
    SCENARIO_A,
    SCENARIO_B,
    SCENARIO_C,
    SCENARIO_D,
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
