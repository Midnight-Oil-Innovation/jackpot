import json
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    env: str = "local"
    database_url: str = "postgresql://jackpot:jackpot@localhost:5432/jackpot_db"
    storage_endpoint: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: str | None = None
    storage_bucket_sequences: str = "jackpot-sequences"
    storage_bucket_raw: str = "jackpot-raw"
    storage_bucket_staging: str = "jackpot-staging"
    storage_bucket_datasets: str = "jackpot-datasets"
    storage_bucket_submissions: str = "jackpot-submissions"
    gcp_project_id: str = ""
    dlp_enabled: bool = False
    secret_key: str = "dev-secret-key-change-in-prod"
    mock_user_email: str = "admin@example.org"
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_url: str = "postmessage"
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

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: object) -> list[str]:
        # Critical Rule 53: list-typed Settings fields must accept JSON
        # arrays, comma-separated strings, empty strings, and real lists.
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
                    raise ValueError(f"cors_origins looks like JSON but won't parse: {e}") from e
            return [item.strip() for item in s.split(",") if item.strip()]
        raise ValueError(f"cors_origins must be str or list, got {type(v).__name__}")

    class Config:
        env_file = ".env.local"

    def validate_for_production(self) -> None:
        if self.env == "gcp":
            required = [
                ("google_oauth_client_id", self.google_oauth_client_id),
                ("google_oauth_client_secret", self.google_oauth_client_secret),
                ("gcp_project_id", self.gcp_project_id),
                ("secret_key", self.secret_key),
            ]
            if missing := [n for n, v in required if not v]:
                raise RuntimeError(f"Missing required config: {missing}")
            if self.secret_key == "dev-secret-key-change-in-prod":
                raise RuntimeError(
                    "SECRET_KEY is still set to the default dev value. "
                    "Set a secure random key before deploying to production."
                )


@lru_cache
def get_settings() -> Settings:
    return Settings()
