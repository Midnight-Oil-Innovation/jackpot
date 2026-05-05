import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    env: str = "local"
    database_url: str = "postgresql://jackpot:jackpot@localhost:5432/jackpot_db"
    storage_endpoint: str | None = None
    storage_access_key: str | None = None
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
    host_organization_name: str = ""
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

    # I-3b: Seqsender subprocess execution.
    # Hard wall-time cap on a single Seqsender invocation. Above this
    # the executor kills the subprocess and transitions the submission
    # to EXECUTION_FAILED with a timeout error message.
    execution_timeout_seconds: int = 3600
    # Root scratch directory under which each execution gets a private
    # `submission_{id}_attempt_{n}` subdirectory. Preserved on failure
    # for diagnostic inspection; deleted on success.
    execution_working_dir_root: str = "/tmp/jackpot-executions"
    # Path to the Seqsender entry-point script. Default matches the
    # CDCgov/seqsender shell wrapper installed at the conventional
    # location in our api Dockerfile (/opt/seqsender/seqsender-kickoff).
    # Operators with a different install layout override this setting.
    seqsender_binary_path: str = "/opt/seqsender/seqsender-kickoff"

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
            ]
            if missing := [n for n, v in required if not v]:
                raise RuntimeError(f"Missing required config: {missing}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
