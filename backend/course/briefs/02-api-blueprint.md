# Module 2: The API Blueprint

### Teaching Arc
- **Metaphor:** A city's 311 service — one phone number, but when you call, you're routed to the exact department (roads, permits, sanitation) that handles your request. FastAPI is the 311 switchboard; routers are the departments.
- **Opening hook:** "The JACKPOT API has 20 different URL paths — one for samples, one for auth, one for GISAID export, etc. How does one Python file keep all of that organized without becoming chaos?"
- **Key insight:** FastAPI organizes code into "routers" — each router owns a group of related URLs and lives in its own file. The main.py file is just the switchboard that connects them all.
- **"Why should I care?":** When you ask AI to "add an endpoint that returns all wastewater samples," you need to say "add a GET route to the samples router" — not "add it to main.py." Knowing the router structure tells you exactly where to put new code.

### Code Snippets (pre-extracted)

**File: backend/main.py (lines 1-103) — key selections:**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import (
    auth, billing, gisaid, ingest, labs,
    ncbi_submissions, organizations, pipelines,
    projects, samples, users,
    # ... 9 more routers
)

app = FastAPI(
    title="JACKPOT API",
    description="JACKPOT pathogen genomics platform.",
    version=__version__,
    lifespan=lifespan,
)

app.include_router(samples.router)
app.include_router(auth.router)
app.include_router(gisaid.router)
# ... 17 more routers

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**File: backend/routers/gisaid.py (lines 44-50) — a real implemented router:**
```python
@router.post("/export/{lab_id}")
def export_gisaid_csv(
    lab_id: int,
    sample_ids: list[int],
    pathogen: str,
    request: Request,
) -> StreamingResponse:
```

**File: backend/middleware.py (lines 1-13):**
```python
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

**File: backend/pagination.py (lines 35-68):**
```python
def paginate(
    query: str,
    params: dict | None,
    page: int,
    per_page: int,
    sort_by: str,
    sort_dir: str,
) -> tuple[list[dict], int]:
    if sort_dir.lower() not in {"asc", "desc"}:
        sort_dir = "desc"
    if sort_by not in ALLOWED_SORT_COLUMNS:
        sort_by = "created_at"
    offset = (page - 1) * per_page
    count_query = f"SELECT COUNT(*) AS total FROM ({query}) AS _count_subquery"
    count_result = execute_query(count_query, params)
    total = count_result[0]["total"] if count_result else 0
    paged_query = f"{query} ORDER BY {sort_by} {sort_dir.upper()} LIMIT :_limit OFFSET :_offset"
    paged_params = {**(params or {}), "_limit": per_page, "_offset": offset}
    results = execute_query(paged_query, paged_params)
    return results, total
```

### Interactive Elements

- [x] **Code↔English translation** — middleware.py: show how every request gets a UUID stamped on it, why that matters for debugging
- [x] **Code↔English translation** — gisaid.py router signature: show how FastAPI reads path params, body, and request automatically
- [x] **Group chat animation** — actors: Browser, RequestIDMiddleware, CORS Middleware, Router (samples), Handler function, Database. Messages: Browser sends GET /api/v1/samples → Middleware stamps request_id → CORS checks origin → Router matches URL → Handler runs query → Response flows back with X-Request-ID header
- [x] **Quiz** — 3 questions:
  1. "A user reports an error. Support asks for the 'request ID.' Where does that come from?" (RequestIDMiddleware generates a UUID for every request)
  2. "You want to add a 'download all samples as CSV' feature. Where in the codebase would the new code live?" (a new route in backend/routers/samples.py)
  3. "The frontend at localhost:4200 is getting CORS errors. Where in the code is this configured?" (CORSMiddleware in main.py)
- [x] **Pattern cards** — show the 5 categories of routers: Identity (auth, users, tokens), Organization (orgs, labs, projects), Samples (samples, ingest, sample_access), Submissions (gisaid, ncbi, dataharmonizer), Platform Admin (billing, domain_whitelist, sequencing_labs)
- [x] **Glossary tooltips** — API, router, endpoint, middleware, CORS, path parameter, request ID, UUID, HTTP verb (GET/POST), StreamingResponse

### Reference Files to Read
- `references/interactive-elements.md` → "Group Chat Animation", "Code ↔ English Translation Blocks", "Multiple-Choice Quizzes", "Pattern/Feature Cards", "Glossary Tooltips"
- `references/content-philosophy.md` → full file
- `references/gotchas.md` → full file

### Connections
- **Previous module:** "The Living Stack" — showed the 4 Docker services; this module zooms into the API service
- **Next module:** "Auth & Identity" — zooms into the auth router specifically, the most security-critical piece
- **Tone/style notes:** Accent vermillion (#D94F30). Module 2 uses --color-bg-warm (#F5F0E8).
