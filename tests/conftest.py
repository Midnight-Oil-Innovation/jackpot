import os
import subprocess
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from testcontainers.postgres import PostgresContainer

from backend.config import get_settings
from backend.credentials import _reset_backend, _set_backend
from backend.credentials.test_helpers import InMemoryBackend
from backend.database import reset_engine
from backend.main import app

# Backend directory holds alembic.ini and db/migrations/. Resolved from
# this file's path so the suite runs from any cwd in the workspace.
_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16") as pg:
        yield pg


@pytest.fixture(scope="session")
def test_db_url(postgres_container):
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session", autouse=True)
def initialize_test_db(test_db_url):
    env = os.environ.copy()
    env["DATABASE_URL"] = test_db_url
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        env=env,
        cwd=_BACKEND_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("Alembic upgrade failed: " + result.stdout + result.stderr)

    yield


@pytest.fixture(autouse=True)
def override_settings(test_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", test_db_url)
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("MOCK_USER_EMAIL", "admin@example.org")
    monkeypatch.setenv("STORAGE_ENDPOINT", "http://localhost:9000")
    monkeypatch.setenv("STORAGE_ACCESS_KEY", "minioadmin")
    # Legacy env name resolves through EnvVarBackend's legacy_env_names
    # fallback to the canonical credential key 's3_storage_secret_key'.
    monkeypatch.setenv("STORAGE_SECRET_KEY", "minioadmin")
    # JWT signing key is now always required. Tests use a fixed value via
    # the canonical JACKPOT_CRED_* env so EnvVarBackend resolves it under
    # the default test config.
    monkeypatch.setenv("JACKPOT_CRED_JWT_SIGNING_KEY", "test-jwt-signing-key")
    # OAuth client secret: pre-C-1 tests relied on Settings.google_oauth_client_secret
    # defaulting to an empty string so that hitting /auth/google/login during
    # rate-limit tests would proceed to a 4xx response from Google. With the
    # credential layer, an empty value is treated as not set and raises;
    # provide a non-empty placeholder so Google still rejects the bogus code
    # but the credential read itself succeeds.
    monkeypatch.setenv("JACKPOT_CRED_GOOGLE_OAUTH_CLIENT_SECRET", "test-oauth-secret")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    get_settings.cache_clear()
    _reset_backend()
    reset_engine()  # ← force engine rebuild with test URL
    # The slowapi limiter was constructed at import time with the original
    # rate_limit_enabled value. Re-evaluate it now so test runs aren't
    # tripping the live 5/minute auth gate after a few login attempts.
    from backend.rate_limit import limiter

    limiter.enabled = get_settings().rate_limit_enabled
    yield
    get_settings.cache_clear()
    _reset_backend()
    reset_engine()


@pytest.fixture
def fake_credentials():
    """In-memory credential backend for tests.

    Populate with `fake_credentials.set('key', 'value')`. The fixture
    swaps the active credential backend and restores it afterwards.
    """
    backend = InMemoryBackend()
    _set_backend(backend)
    yield backend
    _reset_backend()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


@pytest.fixture
def valid_human_sample():
    return {
        "sample_id": "EXAMPLE-TEST-001",
        "organism_name": "Severe acute respiratory syndrome coronavirus 2",
        "source_type": "Human",
        "date_collected": "2026-01-15",
        "date_sequenced": "2026-01-17",
        "collection_location_country": "United States",
        "collection_location_state": "California",
        "sequencing_platform": "Illumina",
        "sequencing_lab": "Example Lab",
        "type_of_experiment": "WGS",
        "library_preparation_method": "ARTIC",
        "nucleic_acid_extraction_method": ["QIAamp DSP Viral RNA"],
        "sequencing_protocol": "https://www.protocols.io/view/artic-v4-1",
        "collection_facility": "Example Hospital",
        "purpose_for_collection": ["clinical"],
        "sharing_level": "PRIVATE",
        "sector": "clinical",
        "scrub_status": "PENDING",
        "pii_scan_status": "PENDING",
        "ingest_method": "gui",
        "fastq_r1_uri": "gs://jackpot-sequences/example/EXAMPLE-TEST-001/R1.fastq.gz",
        "external_case_id": "CASE-2026-001",
        "biospecimen_type": "nasopharyngeal_swab",
        "reason_for_collection": ["clinical"],
        "host_disease": ["covid-19"],
        "project_id": "1",
        "lab_id": "1",
    }
