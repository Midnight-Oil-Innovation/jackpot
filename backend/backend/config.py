import json
import os
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    env: str = "local"
    database_url: str = "postgresql://jackpot:jackpot@localhost:5432/jackpot_db"
    # Which backend get_storage_backend() builds. None means "infer from
    # storage_endpoint", the pre-2026-09-04 behaviour, kept so a config
    # that never names a backend keeps working. That inference is what
    # produced B-STORAGE-LOCAL-FALLTHROUGH: an empty endpoint was read as
    # "therefore GCS", so an operator asking for local filesystem storage
    # got a client pointed at storage.googleapis.com. Name the backend.
    storage_backend: Literal["local", "minio", "gcs", "s3"] | None = None
    storage_endpoint: str | None = None
    storage_access_key: str | None = None
    # Required when storage_backend == "local". No default on purpose:
    # a wrong guess here writes an operator's data somewhere they did not
    # choose, which is the failure this whole item is about.
    local_storage_root: str = ""
    # Base URL presigned local-storage URLs are built against. Falls back
    # to jackpot_api_url when unset.
    local_storage_public_url_base: str = ""
    storage_bucket_sequences: str = "jackpot-sequences"
    storage_bucket_raw: str = "jackpot-raw"
    storage_bucket_staging: str = "jackpot-staging"
    storage_bucket_datasets: str = "jackpot-datasets"
    storage_bucket_submissions: str = "jackpot-submissions"
    gcp_project_id: str = ""
    dlp_enabled: bool = False
    mock_user_email: str = "admin@example.org"
    google_oauth_client_id: str = ""
    google_oauth_redirect_url: str = "postmessage"

    # C-1: pluggable credential infrastructure. Sensitive string values
    # (signing keys, OAuth client secrets, storage HMAC secrets, presign
    # secrets) are read via backend.credentials, not from Settings fields.
    # The four fields below configure which backend backs that abstraction.
    credential_backend: Literal["env", "file", "gcp_secret_manager"] = "env"
    credential_file_path: str = "~/.config/jackpot/credentials.yaml"
    credential_gcp_secret_prefix: str = "jackpot-cred-"
    credential_cache_ttl_seconds: int = 300
    # Operator identity, published by GET /service-info (P0i). Blank by
    # design: the neutral defaults live at the single read site in
    # main.py:service_info, which is the only place that can survive an
    # env var set to the empty string. service_id must be a reverse-domain
    # string unique to the deployment.
    host_organization_name: str = ""
    service_id: str = ""
    host_organization_url: str = ""
    service_contact_url: str = ""
    ncbi_api_key: str = ""
    jackpot_api_token: str = ""
    scheduler_enabled: bool = True
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:8501",
        "http://localhost:4200",
    ]
    pipeline_executor: str = "local"
    jackpot_api_url: str = "http://localhost:8000"
    work_bucket: str = "jackpot-work"
    results_bucket: str = "jackpot-results"
    # P0g G-4: per-deployment default work dir for runs whose chosen
    # execution profile does not override `work_dir` (and the legacy
    # GCP-Batch fallback path, which still uses `work_bucket`). Tilde
    # is expanded eagerly so downstream code can pass the value to
    # filesystem APIs without re-expanding. Cloud URIs (gs://, s3://)
    # pass through untouched. Override via the JACKPOT_WORK_DIR env.
    work_dir: str = Field(
        default="~/.jackpot/work/",
        validation_alias="JACKPOT_WORK_DIR",
    )
    gcp_region: str = "us-central1"
    rate_limit_enabled: bool = True
    rate_limit_auth: str = "5/minute"
    rate_limit_ingest: str = "60/minute"

    # Phase P0f F-4: full-content-hash background job
    full_hash_interval_seconds: int = 300
    full_hash_max_seconds_per_tick: int = 1800
    compute_sra_full_hash: bool = False
    skip_remote_full_hash: bool = False

    # Phase P0f F-5: verify_file_references background job
    verification_interval_seconds: int = 86400  # 24 hours
    verification_files_per_tick: int = 100
    verification_consecutive_failures_to_break: int = 3
    verification_re_fingerprint: bool = False

    # I-1 spreadsheet importer wizard
    import_session_ttl_hours: int = 24
    import_session_max_file_size_mb: int = 10
    import_session_max_per_user: int = 5
    import_session_cleanup_interval_seconds: int = 3600  # hourly

    # I-2 submission package generation
    # submissions_output_root has no default — operators must set the
    # filesystem (or gs://) path where packages are written. Examples:
    #   /var/jackpot/submissions
    #   gs://jackpot-managed/submissions
    submissions_output_root: str = ""
    submission_package_link_files: bool = True
    submission_max_samples_per_package: int = 1000
    embargo_release_check_hour: int = 0  # midnight UTC daily run

    # Phase P0f F-9: promote_file_storage one-shot job
    # managed_storage_root has no default — operators must set it at
    # deployment time. Failure to configure surfaces at job execution
    # time as a clear error rather than silently dropping bytes into
    # the wrong location. Examples:
    #   gs://jackpot-managed
    #   s3://jackpot-managed
    #   file:///srv/jackpot/managed
    managed_storage_root: str = ""
    promote_chunk_size_mb: int = 8
    promote_max_seconds_per_job: int = 3600
    promote_verify_hash: bool = True

    # I-3a: backend-driven submission execution. Off by default — flipping
    # this to True opts the deployment in to the I-3b/c surface (REST,
    # CLI, UI). When False, package-only flow is the only path operators
    # see, and the four NCBI/ENA credentials below are not required at
    # startup.
    allow_backend_submission: bool = False
    # Operator-declared list of repo identifiers eligible for backend
    # execution. Valid values in v1: "ncbi", "ena". Other values are
    # silently ignored by the credential predicates so a stray entry
    # cannot block startup; runtime path will check repo eligibility.
    backend_submission_repos: Annotated[list[str], NoDecode] = []

    # P1: refresh-token rotation. ``access_token_lifetime_seconds`` and
    # ``refresh_token_lifetime_seconds`` mirror the constants previously
    # hard-coded in backend/auth/oauth.py (15 minutes / 7 days). Keeping
    # the same numeric defaults preserves today's behavior; making them
    # Settings fields lets operators tune the access-token blast radius
    # vs. UX trade-off without code changes.
    access_token_lifetime_seconds: int = 900
    refresh_token_lifetime_seconds: int = 604800
    # Daily sweep cadence for the cleanup_old_refresh_tokens job, plus
    # how long revoked rows stick around before purge. 30 days is long
    # enough for forensic queries on a recently-detected replay event,
    # short enough that the table doesn't grow unboundedly.
    refresh_token_cleanup_interval_seconds: int = 86400
    refresh_token_retention_after_revoke_seconds: int = 2592000

    # P0h H-4: sidecar Nextflow log poller.
    # Cadence at which ``backend.log_poller.poll_cluster_run_logs``
    # tails ``<work_dir>/runs/<run_id>/.nextflow.log`` for active
    # cluster runs and synthesises workflow-state transitions when
    # the weblog can't reach the API. 30 seconds matches the H-4 spec
    # and is fast enough that a 5-minute pipeline lands its
    # COMPLETED/FAILED state-shift inside the same business minute.
    log_poller_interval_seconds: int = 30
    # B-CARE-3c vacuum cadence: retention window between tombstone and
    # vacuum (operator policy, design doc §6; 30-day default) and the
    # scheduled-job interval (daily).
    vacuum_retention_seconds: int = 2592000
    vacuum_job_interval_seconds: int = 86400

    # B-CARE-4 federation deletion propagation (design doc §9).
    # SLA within which peers must acknowledge tombstone events (vacuum
    # events auto-flag at 2× this value). 24h default; Scenario T
    # operators set 3600 (1h) per §9.
    federation_propagation_sla_seconds: int = 86400
    # Non-compliance policy: alert_only | suspend_on_n | hard_fail.
    federation_noncompliance_policy: str = "alert_only"
    federation_suspend_after_n_failures: int = 3
    federation_propagation_job_interval_seconds: int = 300
    # Ed25519 event-signing key (backend.crypto). Events are enqueued
    # unsigned and delivery is withheld until the key is configured.
    federation_signing_key_id: str = "federation-signing"
    federation_keystore_backend: str = "filesystem"

    # P0h H-6: pre-launch Slurm reachability check.
    # Refines F-8: when a launch's resolved profile is SLURM, fire
    # ``sinfo -h`` on the API host before queueing the run so a downed
    # cluster fails fast at submit time instead of after a 15-minute
    # Slurm-client timeout. Result is cached per (account, partition)
    # for ``slurm_reachability_cache_seconds`` so a 50-sample bulk
    # launch doesn't spawn 50 subprocesses.
    #
    # Tests opt out via ``slurm_reachability_check_enabled = False`` so
    # the existing SLURM-profile launch suite isn't tied to having
    # Slurm client tools on the runner.
    slurm_reachability_check_enabled: bool = True
    slurm_reachability_cache_seconds: int = 60
    slurm_reachability_timeout_seconds: int = 10

    # Privacy
    # B-IMMUNE-DP-1: default ε for the federation-wide DP aggregator
    # (backend.immune.sec.dp_aggregator). Operators override per-deployment
    # via the DP_EPSILON env var; callers may override per-call. Smaller
    # values give stronger privacy at the cost of more noise.
    dp_epsilon: float = 1.0

    # I-3b: Seqsender subprocess execution.
    # Hard wall-time cap on a single Seqsender invocation. Above this
    # the executor kills the subprocess and transitions the submission
    # to EXECUTION_FAILED with a timeout error message.
    execution_timeout_seconds: int = 3600
    # Root scratch directory under which each execution gets a private
    # `submission_{id}_attempt_{n}` subdirectory. Preserved on failure
    # for diagnostic inspection; deleted on success. bandit B108 flags
    # the hardcoded /tmp default — the actual mitigation is that
    # jobs.py._execute_submission_locked chmods each subdirectory 0700
    # right after creation, so other local users can't read another
    # lab's diagnostics. Operators may still override this path.
    execution_working_dir_root: str = "/tmp/jackpot-executions"  # nosec B108
    # Path to the Seqsender entry-point script. Default matches the
    # CDCgov/seqsender shell wrapper installed at the conventional
    # location in our api Dockerfile (/opt/seqsender/seqsender-kickoff).
    # Operators with a different install layout override this setting.
    seqsender_binary_path: str = "/opt/seqsender/seqsender-kickoff"

    @field_validator("work_dir")
    @classmethod
    def _expand_work_dir(cls, v: str) -> str:
        # P0g G-4: tilde expansion happens once at Settings load.
        # gs://, s3://, file://, and absolute paths pass through.
        if v.startswith("~"):
            return os.path.expanduser(v)
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: object) -> list[str]:
        # Critical Rule 53: list-typed Settings fields must accept JSON
        # arrays, comma-separated strings, empty strings, and real lists.
        return cls._parse_str_list(v, field_name="cors_origins")

    @field_validator("backend_submission_repos", mode="before")
    @classmethod
    def _parse_backend_submission_repos(cls, v: object) -> list[str]:
        # Critical Rule 53. I-3a opt-in repo list; same JSON / CSV /
        # empty-string / real-list shape as cors_origins.
        return cls._parse_str_list(v, field_name="backend_submission_repos")

    @staticmethod
    def _parse_str_list(v: object, *, field_name: str) -> list[str]:
        if v is None or v == "":
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):
                try:
                    return json.loads(s)
                except json.JSONDecodeError as e:
                    raise ValueError(f"{field_name} looks like JSON but won't parse: {e}") from e
            return [item.strip() for item in s.split(",") if item.strip()]
        raise ValueError(f"{field_name} must be str or list, got {type(v).__name__}")

    class Config:
        env_file = ".env.local"

    def validate_for_production(self) -> None:
        # C-1: secret-key validation moved to backend.credentials. This
        # method now only checks non-credential production requirements.
        if self.env == "gcp":
            required = [
                ("google_oauth_client_id", self.google_oauth_client_id),
                ("gcp_project_id", self.gcp_project_id),
                # GET /service-info falls back to a shared example id when
                # this is unset, which is fine for local and CI but would
                # have every real deployment advertise the same GA4GH
                # identity to its federation peers.
                ("service_id", self.service_id),
            ]
            if missing := [n for n, v in required if not v]:
                raise RuntimeError(f"Missing required config: {missing}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
