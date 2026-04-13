# Module 6: The Supporting Cast

### Teaching Arc
- **Metaphor:** A stage production's behind-the-scenes crew — the file detector is the prop master who organizes equipment by name convention; background jobs are the cleanup crew who work after the show; notifications are the stage manager paging actors; GISAID/NCBI export is the press kit department that reformats content for outside audiences.
- **Opening hook:** "The API has 20 routers, but some of the most interesting work happens outside of any request — on a timer, in response to events, or when a researcher clicks 'Export to GISAID.'"
- **Key insight:** Not all important logic runs during a web request. Background jobs handle tasks too slow for a request (scrubbing, auto-approvals). Notifications decouple "something happened" from "tell someone." Export scripts reformat data for external audiences without changing the source.
- **"Why should I care?":** When a researcher says "I never got notified when my pipeline finished," you need to know that notifications are a separate system — and failures in notifications are intentionally swallowed so they can't break the main action. When "auto-approve isn't working," you'd look at background jobs, not the API.

### Code Snippets (pre-extracted)

**File: backend/file_detector.py (lines 46-68) — paired file detection:**
```python
PAIRED_PATTERNS: list[re.Pattern] = [
    re.compile(
        rf"^(?P<prefix>.+?)_(?P<lane>L\d+)_(?P<dir>R[12])(?:_\d+)?{FASTQ_EXT}$", re.IGNORECASE
    ),
    re.compile(rf"^(?P<prefix>.+?)_(?P<dir>R[12])(?:_\d+)?{FASTQ_EXT}$", re.IGNORECASE),
    re.compile(rf"^(?P<prefix>.+?)_(?P<dir>[12]){FASTQ_EXT}$"),
    re.compile(rf"^(?P<prefix>.+?)_(?P<dir>forward|reverse){FASTQ_EXT}$", re.IGNORECASE),
]

DIRECTION_MAP: dict[str, str] = {
    "r1": "R1", "1": "R1", "forward": "R1",
    "r2": "R2", "2": "R2", "reverse": "R2",
}
```

**File: backend/jobs.py (full file):**
```python
async def run_scrubber_queue_job() -> None:
    """
    Auto-deny scrub override requests pending for > 48 hours.
    Conservative default: if Lab Director doesn't decide, scrubber runs.
    """
    logger.info("run_scrubber_queue_job: not yet implemented")

async def run_access_request_job() -> None:
    """
    Auto-approve access requests where auto_approve_after <= NOW().
    Send 75-day warnings, 7-day expiry warnings, expire granted access.
    """
    logger.info("run_access_request_job: not yet implemented")
```

**File: backend/main.py (lines 40-58) — scheduler wiring:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    get_settings().validate_for_production()
    if get_settings().scheduler_enabled:
        scheduler.add_job(
            run_scrubber_queue_job,
            "interval",
            hours=1,
            id="scrub_override_auto_deny",
        )
        scheduler.add_job(
            run_access_request_job,
            "interval",
            hours=1,
            id="access_request_auto_approve",
        )
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown()
```

**File: backend/notifications.py (lines 37-77) — fire-and-forget:**
```python
def create_notification(
    recipient_id: int,
    event_type: str,
    title: str,
    body: str,
    resource_type: str,
    resource_id: str,
    action_url: str | None,
    db_conn,
) -> None:
    """
    Write a notification record synchronously within the caller's transaction.
    Failures are logged and swallowed — a notification failure must never
    roll back the triggering action.
    """
    try:
        execute_write(
            "INSERT INTO notifications ...",
            {...},
        )
    except Exception as exc:
        logger.error("Notification write failed", exc_info=exc, ...)
```

**File: scripts/portal_to_tostadas.py (lines 18-68) — NCBI export:**
```python
BIOSAMPLE_FIELD_MAP: dict[str, str] = {
    "organism_name": "organism",
    "date_collected": "collection_date",
    "collection_location_country": "geo_loc_name",
    "host_species": "host",
    "host_age": "host_age",
    "sequencing_platform": "sequencing_platform",
    "pango_lineage": "lineage",
}

def convert_sample(sample: dict) -> dict:
    biosample: dict = {}
    for portal_field, ncbi_attr in BIOSAMPLE_FIELD_MAP.items():
        val = sample.get(portal_field)
        if val:
            biosample[ncbi_attr] = str(val)
    country = sample.get("collection_location_country", "")
    state = sample.get("collection_location_state", "")
    biosample["geo_loc_name"] = f"{country}: {state}" if state else country
    biosample["package"] = SOURCE_TYPE_PACKAGE.get(sample.get("source_type", ""), "Generic.1.0")
    return {
        "sample_name": sample["sample_id"],
        "bioproject": sample.get("bioproject_accession", ""),
        "biosample_attrs": biosample,
        "fastq_r1": sample["fastq_r1_uri"],
    }
```

### Interactive Elements

- [x] **Code↔English translation** — file_detector.py PAIRED_PATTERNS: explain how regex patterns detect R1/R2 pairs from filenames like "sample_L001_R1_001.fastq.gz"
- [x] **Code↔English translation** — notifications.py create_notification: explain why exceptions are swallowed (fire-and-forget pattern — a notification failure must never break the main action)
- [x] **Group chat animation** — actors: Pipeline Completion Event, Notifications Service, User Inbox, Background Job Scheduler, Scrubber. Scenario: a pipeline completes → notification created → user sees "Pipeline complete" in inbox. Separately: overnight job runs → finds scrub override pending 50 hours → auto-denies it → notification sent to Lab Director.
- [x] **Quiz** — 3 questions:
  1. "A researcher uploads files named 'sample_forward.fastq.gz' and 'sample_reverse.fastq.gz'. Will the file detector pair them as R1/R2?" (yes — 'forward' maps to R1 and 'reverse' maps to R2 via DIRECTION_MAP)
  2. "A notification write fails. Does the sample ingest also fail?" (no — the exception is caught and logged; the notification failure is intentionally swallowed)
  3. "A batch of samples needs to be submitted to NCBI. The script maps 'organism_name' to what NCBI field?" (portal_to_tostadas.py maps organism_name → 'organism', matching NCBI BioSample attribute names)
- [x] **Drag-and-drop matching** — match these background jobs to their trigger: run_scrubber_queue_job (scrub override pending >48h), run_access_request_job (auto_approve_after <= NOW()). Also match notification events: PIPELINE_COMPLETE, ACCESS_REQUEST_APPROVED, GLOBUS_FILES_ARRIVED to their actors.
- [x] **Glossary tooltips** — regex, background job, scheduler, fire-and-forget, TOSTADAS, BioSample, paired-end sequencing, R1/R2, FASTQ, lifespan context manager

### Reference Files to Read
- `references/interactive-elements.md` → "Group Chat Animation", "Drag-and-Drop Matching", "Code ↔ English Translation Blocks", "Multiple-Choice Quizzes", "Glossary Tooltips"
- `references/content-philosophy.md` → full file
- `references/gotchas.md` → full file

### Connections
- **Previous module:** "Data Layer" — showed databases and storage; this module shows the processes that happen around and after data storage
- **Next module:** None — this is the final module
- **Tone/style notes:** Accent vermillion (#D94F30). Module 6 uses --color-bg-warm (#F5F0E8). End the module with a "You now understand the whole backend" summary callout.
