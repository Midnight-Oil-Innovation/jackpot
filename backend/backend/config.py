from functools import lru_cache

from pydantic_settings import BaseSettings


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
    mock_user_email: str = "gotero@linuxprophet.com"
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_url: str = "postmessage"
    adhs_organization_name: str = "ADHS"
    ncbi_api_key: str = ""
    jackpot_api_token: str = ""
    scheduler_enabled: bool = True
    cors_origins: list[str] = ["http://localhost:8501", "http://localhost:4200"]

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
