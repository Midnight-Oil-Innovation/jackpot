import contextlib

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer

from backend.config import get_settings
from backend.database import reset_engine
from backend.main import app


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16") as pg:
        yield pg


@pytest.fixture(scope="session")
def test_db_url(postgres_container):
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session", autouse=True)
def initialize_test_db(test_db_url):
    engine = create_engine(test_db_url)
    with open("db/init.sql") as f:
        sql = f.read()
    with engine.connect() as conn:
        for stmt in sql.split(";"):
            s = stmt.strip()
            if s:
                with contextlib.suppress(Exception):
                    conn.execute(text(s))
        conn.commit()
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def override_settings(test_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", test_db_url)
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("MOCK_USER_EMAIL", "gotero@linuxprophet.com")
    monkeypatch.setenv("STORAGE_ENDPOINT", "http://localhost:9000")
    monkeypatch.setenv("STORAGE_ACCESS_KEY", "minioadmin")
    monkeypatch.setenv("STORAGE_SECRET_KEY", "minioadmin")
    get_settings.cache_clear()
    reset_engine()  # ← force engine rebuild with test URL
    yield
    get_settings.cache_clear()
    reset_engine()


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
        "sample_id": "AZ-TEST-001",
        "organism_name": "Severe acute respiratory syndrome coronavirus 2",
        "source_type": "Human",
        "date_collected": "2026-01-15",
        "date_sequenced": "2026-01-17",
        "collection_location_country": "United States",
        "collection_location_state": "Arizona",
        "sequencing_platform": "Illumina",
        "sequencing_lab": "Otero Lab",
        "type_of_experiment": "WGS",
        "library_preparation_method": "ARTIC",
        "nucleic_acid_extraction_method": ["QIAamp DSP Viral RNA"],
        "sequencing_protocol": "https://www.protocols.io/view/artic-v4-1",
        "collection_facility": "Mayo Clinic Phoenix",
        "purpose_for_collection": ["clinical"],
        "sharing_level": "PRIVATE",
        "sector": "clinical",
        "scrub_status": "PENDING",
        "pii_scan_status": "PENDING",
        "ingest_method": "gui",
        "fastq_r1_uri": "gs://jackpot-sequences/asu/otero/AZ-TEST-001/R1.fastq.gz",
        "adhs_medsis_id": "ADHS-2026-001",
        "biospecimen_type": "nasopharyngeal_swab",
        "reason_for_collection": ["clinical"],
        "host_disease": ["covid-19"],
        "project_id": "1",
        "lab_id": "1",
    }
