# Module 5: Data Layer

### Teaching Arc
- **Metaphor:** A hospital's records system — patient charts live in filing cabinets (PostgreSQL), while X-ray films and MRI scans live in a separate archive room (object storage). The cabinets store structured records; the archive stores large files. They're different systems because they solve different problems.
- **Opening hook:** "When a sample is validated and accepted, it needs to be stored in two completely different places — its metadata goes into a database, and its genome files go into object storage. Why two systems instead of one?"
- **Key insight:** Databases are great at searching, filtering, and joining structured data (rows and columns). Object storage is great at holding large files cheaply. JACKPOT uses both because each is the right tool for its job.
- **"Why should I care?":** When something is "not showing up in the dashboard," it could be missing from the database (metadata problem) or the files could be in the wrong bucket (storage problem). Two different places to look.

### Code Snippets (pre-extracted)

**File: backend/database.py (lines 36-56) — the connection pattern:**
```python
@contextmanager
def get_db():
    _, session_local = _get_engine()
    db: Session = session_local()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def execute_query(query: str, params: dict | None = None) -> list[dict]:
    with get_db() as db:
        result = db.execute(text(query), params or {})
        if result.returns_rows:
            cols = result.keys()
            return [dict(zip(cols, row, strict=False)) for row in result.fetchall()]
        return []
```

**File: backend/database.py (lines 59-82) — write with transaction sharing:**
```python
def execute_write(
    query: str,
    params: dict | None = None,
    conn=None,
) -> list[dict]:
    """
    Execute a write query. Returns rows if RETURNING clause is present.
    Pass conn to participate in an existing transaction — the caller is
    responsible for commit/rollback. Omit conn to use an auto-committed
    internal transaction.
    """
    if conn is not None:
        result = conn.execute(text(query), params or {})
        if result.returns_rows:
            cols = result.keys()
            return [dict(zip(cols, row, strict=False)) for row in result.fetchall()]
        return []
    with get_db() as db:
        result = db.execute(text(query), params or {})
        ...
```

**File: backend/audit.py (lines 53-89) — append-only audit log:**
```python
def log_audit(
    action: str,
    actor_id: int | None,
    resource_type: str,
    resource_id: str,
    before: dict | None,
    after: dict | None,
    metadata: dict | None,
    db_conn,
) -> None:
    """Write immutable audit record. Failures are logged, never raised."""
    try:
        execute_write(
            """
            INSERT INTO audit_log
                (action, actor_id, resource_type, resource_id,
                 before_state, after_state, metadata)
            VALUES
                (:action, :actor_id, :resource_type, :resource_id,
                 :before::jsonb, :after::jsonb, :metadata::jsonb)
            """,
            ...
        )
    except Exception as exc:
        logger.error("Audit log write failed", exc_info=exc, ...)
```

**File: backend/storage.py (lines 37-49 and 73-84) — staging and presigned URLs:**
```python
def stage_file(fileobj, destination_key: str) -> str:
    """Upload a file to the staging bucket. Returns the URI."""
    settings = get_settings()
    bucket = settings.storage_bucket_staging
    try:
        _get_client().upload_fileobj(fileobj, bucket, destination_key)
    except ClientError as e:
        raise StorageError(...) from e
    prefix = "s3" if settings.storage_endpoint else "gs"
    return f"{prefix}://{bucket}/{destination_key}"


def generate_presigned_url(bucket: str, key: str, ttl_seconds: int = 3600) -> str:
    """Generate a presigned download URL."""
    try:
        return _get_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=ttl_seconds,
        )
    except ClientError as e:
        raise StorageError(...) from e
```

**File: db/init.sql (lines 113-130) — audit log table:**
```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id     INTEGER REFERENCES users(id),
    action      TEXT NOT NULL,
    resource    TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    detail      JSONB,
    ip_address  TEXT,
    request_id  TEXT
);
-- CLIA-aware — append-only; never UPDATE or DELETE rows here
```

**Five storage buckets from config.py:**
```
jackpot-raw        — original uploaded files before PII scrubbing (30-day lifecycle)
jackpot-staging    — files in transit during ingest
jackpot-sequences  — scrubbed, approved genome files (permanent)
jackpot-datasets   — analytical dataset exports
jackpot-submissions — formatted NCBI/GISAID submission packages
```

### Interactive Elements

- [x] **Code↔English translation** — database.py get_db context manager: explain connection pooling, commit/rollback, why the finally block matters
- [x] **Code↔English translation** — audit.py log_audit: explain why failures are caught and logged (not raised) — a notification failure must never roll back a sample write
- [x] **Data flow animation** — actors: Validated Sample, execute_write, PostgreSQL, File Upload, Storage Client, MinIO/GCS. Steps: (1) Sample metadata → execute_write called → (2) DB transaction opened → (3) INSERT INTO samples → (4) audit INSERT in same transaction → (5) COMMIT → (6) FASTQ file separately uploaded to staging bucket → (7) Storage returns gs:// URI → (8) URI stored in samples.fastq_r1_uri column
- [x] **Architecture diagram** — 5 storage buckets with clickable descriptions. jackpot-raw (pre-scrub, 30-day delete), jackpot-staging (in-transit), jackpot-sequences (permanent scrubbed), jackpot-datasets (exports), jackpot-submissions (NCBI/GISAID packages)
- [x] **Quiz** — 3 questions:
  1. "A researcher deleted a sample. Compliance needs to prove who deleted it and when. Where does that record live?" (audit_log table — append-only, never deleted)
  2. "A genome file's URI starts with 'gs://jackpot-raw/...'. Is this the permanent location?" (no — jackpot-raw is deleted after 30 days; permanent files are in jackpot-sequences after scrubbing)
  3. "execute_write is called with conn=None vs conn=db. What is the difference?" (conn=None auto-commits its own transaction; conn=db participates in the caller's transaction so both writes commit or roll back together)
- [x] **Pattern cards** — 5 buckets with icons and descriptions (as above)
- [x] **Glossary tooltips** — connection pool, transaction, rollback, ACID, object storage, presigned URL, JSONB, BIGSERIAL, context manager, CLIA

### Reference Files to Read
- `references/interactive-elements.md` → "Message Flow / Data Flow Animation", "Interactive Architecture Diagram", "Code ↔ English Translation Blocks", "Multiple-Choice Quizzes", "Pattern/Feature Cards", "Glossary Tooltips"
- `references/content-philosophy.md` → full file
- `references/gotchas.md` → full file

### Connections
- **Previous module:** "The Ingest Engine" — showed validation and enrichment; this module shows where data lands after ingest succeeds
- **Next module:** "The Supporting Cast" — shows file pairing, background jobs, notifications, GISAID/NCBI export
- **Tone/style notes:** Accent vermillion (#D94F30). Module 5 uses --color-bg (#FAF7F2). Local dev uses MinIO (S3-compatible); production uses Google Cloud Storage. The storage.py client is boto3 in both cases (boto3 can talk to GCS via HMAC keys).
