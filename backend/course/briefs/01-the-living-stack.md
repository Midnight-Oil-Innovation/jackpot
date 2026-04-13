# Module 1: The Living Stack

### Teaching Arc
- **Metaphor:** A newsroom with specialized desks — the wire desk (database), photo desk (storage), reporters (API), and the editor (Streamlit UI). Each does one thing; together they publish the story.
- **Opening hook:** "When you open the JACKPOT portal and log in, four separate programs wake up to serve you — and they all run inside tiny isolated containers on your computer."
- **Key insight:** Modern web apps aren't one program — they're an orchestra of specialized services that each do one job and talk to each other over a network.
- **"Why should I care?":** When something breaks, knowing which service is responsible tells you exactly where to look. When you ask AI to "fix the login bug," knowing it lives in the API container (not the database or UI) gets you a precise fix instead of a vague one.

### Code Snippets (pre-extracted)

**File: docker-compose.yml (lines 1-60)**
```yaml
services:

  postgres:
    image: postgres:16
    container_name: jackpot_postgres
    environment:
      POSTGRES_USER:     jackpot
      POSTGRES_PASSWORD: jackpot
      POSTGRES_DB:       jackpot_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql

  minio:
    image: minio/minio:latest
    container_name: jackpot_minio
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"

  api:
    container_name: jackpot_api
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
    command: /opt/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

  ui:
    container_name: jackpot_ui
    ports:
      - "8501:8501"
    depends_on:
      - api
    command: /opt/venv/bin/streamlit run app.py
```

**File: backend/main.py (lines 106-113)**
```python
@app.get("/health")
def health() -> dict:
    try:
        execute_query("SELECT 1")
        db_status = "connected"
    except Exception:
        db_status = "unavailable"
    return {"status": "ok", "version": __version__, "project": "JACKPOT", "database": db_status}
```

**File: backend/config.py (lines 6-50)**
```python
class Settings(BaseSettings):
    env: str = "local"
    database_url: str = "postgresql://jackpot:jackpot@localhost:5432/jackpot_db"
    storage_endpoint: str | None = None
    storage_bucket_sequences: str = "jackpot-sequences"
    storage_bucket_raw: str = "jackpot-raw"
    storage_bucket_staging: str = "jackpot-staging"
    storage_bucket_datasets: str = "jackpot-datasets"
    storage_bucket_submissions: str = "jackpot-submissions"
    secret_key: str = "dev-secret-key-change-in-prod"
    mock_user_email: str = "gotero@linuxprophet.com"
    google_oauth_client_id: str = ""
    scheduler_enabled: bool = True

    class Config:
        env_file = ".env.local"

    def validate_for_production(self) -> None:
        if self.env == "gcp":
            required = [
                ("google_oauth_client_id", self.google_oauth_client_id),
                ("secret_key", self.secret_key),
            ]
            if missing := [n for n, v in required if not v]:
                raise RuntimeError(f"Missing required config: {missing}")
            if self.secret_key == "dev-secret-key-change-in-prod":
                raise RuntimeError(
                    "SECRET_KEY is still set to the default dev value."
                )

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### Interactive Elements

- [x] **Code↔English translation** — docker-compose.yml snippet showing services and ports
- [x] **Data flow animation** — actors: Browser, Streamlit UI (port 8501), FastAPI (port 8000), PostgreSQL (port 5432), MinIO Storage (port 9000). Steps: user opens browser → hits Streamlit → Streamlit calls API → API queries Postgres → API reads files from MinIO → response flows back
- [x] **Architecture diagram** — 4 services with clickable descriptions: Postgres ("stores all metadata"), MinIO ("stores genome files"), API ("serves all business logic"), Streamlit UI ("the researcher's dashboard")
- [x] **Quiz** — 3 scenario questions:
  1. "A researcher says 'I uploaded my samples but the list isn't showing.' Which service would you look at first?" (API)
  2. "The genome files are loading slowly. Which service handles file downloads?" (MinIO/storage)
  3. "You want to add a new required metadata field. Which service enforces that rule?" (API/validator)
- [x] **Glossary tooltips** — container, port, Docker, service, health check, environment variable, volume, lru_cache

### Reference Files to Read
- `references/interactive-elements.md` → "Message Flow / Data Flow Animation", "Interactive Architecture Diagram", "Multiple-Choice Quizzes", "Code ↔ English Translation Blocks", "Glossary Tooltips"
- `references/content-philosophy.md` → full file
- `references/gotchas.md` → full file

### Connections
- **Previous module:** None — this is the opening module
- **Next module:** "The API Blueprint" — zooms into the API service specifically, showing how FastAPI structures 20 endpoints
- **Tone/style notes:** Accent color is vermillion (#D94F30). Course title is "JACKPOT Backend: How a Public Health API Works". Modules alternate bg: odd modules use --color-bg (#FAF7F2), even use --color-bg-warm (#F5F0E8). Module 1 uses --color-bg.
