> **Status:** Reference — pre-GCP local validation checklist.

# Local Test Checklist — Pre-GCP Validation

A comprehensive local-dev validation run. Execute top-to-bottom before any GCP
deployment or pipeline work. Catches most things that would blow up in CI/CD
or in the cluster.

Each step is a copy-paste-able command block with the expected outcome. If a
step fails, fix it before moving on — downstream steps assume earlier ones
passed.

---

## 0. Prerequisites

Confirm your shell is in the right place and submodules are populated.

```bash
cd ~/jackpot/jackpot-backend
pwd
git status
git submodule status
```

**Expected:**
- `pwd` → `/Users/glen/jackpot/jackpot-backend`
- `git status` → `On branch staging`, clean or with expected local changes
- `git submodule status` → two submodule lines (`schema` and `nf`), both with
  a hash at HEAD and not prefixed with `-` (absent) or `+` (out of sync)

If a submodule shows `-` (not initialised), run:

```bash
git submodule update --init --recursive
```

---

## 1. Clean slate Docker environment

Tear down any stale containers and volumes so the DB bootstraps fresh and
matches what a new GCP deploy would experience.

```bash
cd ~/jackpot/jackpot-backend
docker compose down -v
docker compose up -d --build
```

Wait ~30 seconds for services to initialise, then:

```bash
docker compose ps
```

**Expected:** Five services — `postgres`, `minio`, `minio_init`, `api`, `ui` —
all `running` or `exited` (minio_init exits after initialisation, which is
normal).

If any service is restarting, check its logs:

```bash
docker compose logs api --tail 50
docker compose logs postgres --tail 20
```

---

## 2. Health check with DB probe

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

**Expected:**

```json
{
    "status": "ok",
    "version": "5.0.0",
    "project": "JACKPOT",
    "database": "connected"
}
```

If `"database"` is missing or not `"connected"`, the `/health` endpoint's DB
probe isn't working. Check API logs for SQLAlchemy connection errors.

---

## 3. Pipelines router import — the `nf/shared` landmine

Tonight's biggest crash was `ModuleNotFoundError: No module named 'shared'`
from `backend/routers/pipelines.py`. Verify locally that the import works
and `RESULT_SCHEMAS` has real content.

```bash
docker compose exec api /opt/venv/bin/python -c \
    "from backend.routers import pipelines; \
     from shared.schemas import RESULT_SCHEMAS; \
     print('RESULT_SCHEMAS keys:', sorted(RESULT_SCHEMAS.keys()))"
```

**Expected:** A printed list of schema keys such as `['amr_results',
'assembly_qc', 'mag_qc', 'nextclade_results', 'pangolin_results', ...]`.

If `ModuleNotFoundError` appears, either `nf/` isn't in the image or the
`sys.path.insert` in `pipelines.py` isn't executing. Check the Dockerfile
includes `COPY nf/ ./nf/` and rebuild.

---

## 4. OpenAPI schema — every router registers cleanly

If any router has an import-time error, the OpenAPI generator will 500 even
if `/health` works.

```bash
curl -s http://localhost:8000/openapi.json | python3 -c \
    "import sys, json; d = json.load(sys.stdin); \
     print('OpenAPI version:', d['openapi']); \
     print('Title:', d['info']['title']); \
     print('Endpoint count:', len(d['paths'])); \
     print('Routers (inferred from tags):', \
           sorted({t['name'] for p in d['paths'].values() \
                   for op in p.values() if 'tags' in op \
                   for t in [{'name': tn} for tn in op['tags']]}))"
```

**Expected:** Endpoint count in the dozens (all 21 routers wired up), tags
list including `pipelines`, `samples`, `ingest`, `organizations`, `labs`,
`users`, `auth`, `gisaid`, etc.

---

## 5. Alembic from a completely empty database

This is the canonical Critical Rule 44 / Rule 52 sanity check: Alembic
must build the full schema from scratch with no helper SQL. Q-9 closed
the original gap with the baseline migration `5adf11b77c19`; this test
guards against regressions.

```bash
# Drop and recreate the DB inside the running postgres container
docker compose exec postgres psql -U jackpot -d postgres -c \
    "DROP DATABASE IF EXISTS jackpot_test_empty;"
docker compose exec postgres psql -U jackpot -d postgres -c \
    "CREATE DATABASE jackpot_test_empty;"

# Run alembic upgrade head against the new empty DB
docker compose exec -e DATABASE_URL=postgresql://jackpot:jackpot@postgres:5432/jackpot_test_empty \
    api /opt/venv/bin/alembic upgrade head
```

**Expected:** Alembic prints `Running upgrade  -> <rev>` for each migration
in the chain (starting at the baseline `5adf11b77c19`) and exits 0.

**If it fails with "relation does not exist"**, a new migration has
introduced a hidden dependency on prior schema state that's not in the
chain. Fix the offending migration to create what it needs — never
re-introduce a bootstrap Job.

**Cleanup:**

```bash
docker compose exec postgres psql -U jackpot -d postgres -c \
    "DROP DATABASE IF EXISTS jackpot_test_empty;"
```

---

## 6. Alembic `current` — ensure the primary DB is at head

```bash
docker compose exec api /opt/venv/bin/alembic current
```

**Expected:** Prints the current HEAD revision (e.g. `c536de6329e0 (head)`).

---

## 7. Full test suite

```bash
cd ~/jackpot/jackpot-backend
docker compose exec api /opt/venv/bin/pytest --tb=short -q
```

**Expected:** All tests pass. Coverage may drop because of the new pipelines
code; that's fine unless you've explicitly tightened the threshold.

If tests fail, compare to the last known green count (95 per session 4
notes). Failures from the pipelines router are worth triaging before
running a real pipeline.

---

## 8. Schema & model-generation round-trip

Validate that the LinkML schema still parses and `gen-pydantic` still
produces importable code. Catches schema drift that would break GCP's
build step.

```bash
cd ~/jackpot/jackpot-backend

# Validate schema YAML parses
python3 -c \
    "import yaml; yaml.safe_load(open('schema/schema/jackpot_schema.yaml')); \
     print('Schema YAML parses cleanly')"

# Regenerate Pydantic models to /tmp (do not overwrite the real file)
uv run gen-pydantic --pydantic-version 2 \
    schema/schema/jackpot_schema.yaml > /tmp/models_test.py

# Patch the True/False enum keyword bug (Critical Rule 20)
python3 << 'EOF'
from pathlib import Path
p = Path('/tmp/models_test.py')
s = p.read_text()
s = s.replace('\n    True = "True"',   '\n    true = "True"')
s = s.replace('\n    False = "False"', '\n    false = "False"')
p.write_text(s.rstrip('\n') + '\n')
print('Patched')
EOF

# Verify the patched file is importable
python3 -c \
    "import importlib.util; \
     spec = importlib.util.spec_from_file_location('m', '/tmp/models_test.py'); \
     mod = importlib.util.module_from_spec(spec); \
     spec.loader.exec_module(mod); \
     print('Generated models import cleanly')"

# Compare to the committed file — should be identical up to whitespace
diff -q /tmp/models_test.py backend/models_generated.py
```

**Expected:** All four commands print positive output. If `diff` reports
differences, the committed `models_generated.py` is stale — regenerate and
commit it.

---

## 9. Pipelines router smoke — `PIPELINE_EXECUTOR=local`

The pipelines router has 10 real endpoints, but `PIPELINE_EXECUTOR=local`
makes launch a no-op that returns a deterministic pseudo job ID. This
test exercises the router code paths without actually running Nextflow.

Skip this step unless you have authentication wired up locally (it
requires a logged-in user to hit protected endpoints). If you do:

```bash
# Get a JWT for a test user (exact command depends on your auth setup)
# Then hit the pipelines catalog:
TOKEN=<your-token>
curl -s -H "Authorization: Bearer $TOKEN" \
    http://localhost:8000/api/v1/pipelines/catalog | python3 -m json.tool
```

**Expected:** JSON list of registered pipelines.

If auth isn't wired locally, mark this as a known gap and move on — the
test suite in step 7 should cover the router logic.

---

## 10. Nextflow weblog integration — manual harness

A `scripts/test_batch.nf` pipeline doesn't exist yet (that's a backlog
item). Until it does, you can manually test the weblog endpoint path by
firing a synthetic event at it:

```bash
# Create a fake run_id and pipeline_token by launching a fake run,
# or insert a row directly (exact command depends on your auth setup).
# Then POST a synthetic Nextflow weblog event:

curl -X POST http://localhost:8000/api/v1/pipelines/events \
    -H "Content-Type: application/json" \
    -d '{
      "runId": "test-run-id",
      "runName": "test-run",
      "event": "started",
      "utcTime": "2026-04-17T23:00:00.000Z"
    }'
```

**Expected:** 200 if the run exists, 4xx if not. Either way, no 500 from
an unhandled exception inside the event handler.

---

## 11. Docker image build — simulates GCP CI build step

Build the API image locally exactly the way CI does, then spot-check it.

```bash
cd ~/jackpot/jackpot-backend
docker build -f Dockerfile.api -t jackpot-api:local-test .
```

**Expected:** Build succeeds. Final image ~200-250 MB.

Verify the image has `nf/` and all Python deps:

```bash
docker run --rm jackpot-api:local-test /opt/venv/bin/python -c \
    "import sys; sys.path.insert(0, '/app/nf'); \
     from shared.schemas import RESULT_SCHEMAS; \
     from backend.main import app; \
     print('Image OK —', len(app.routes), 'routes,', len(RESULT_SCHEMAS), 'schemas')"
```

**Expected:** Prints something like `Image OK — 147 routes, 9 schemas`.

---

## 12. Commit check — local branch matches remote

After all of the above passes:

```bash
cd ~/jackpot/jackpot-backend
git fetch origin
git status
git log origin/staging..HEAD --oneline
```

**Expected:** No unpushed commits unless you're intentionally working on
something. If there are unpushed commits that touch the Docker image or
the router graph, push them *before* running any GCP deploy.

---

## Exit criteria

Local validation is complete when:

- [ ] Health endpoint returns DB-connected (step 2)
- [ ] `RESULT_SCHEMAS` import works inside the container (step 3)
- [ ] OpenAPI serves cleanly (step 4)
- [ ] Alembic applies from an empty DB (step 5) **— if this fails, do not
      deploy to a fresh GCP environment without the bootstrap Job**
- [ ] Test suite passes (step 7)
- [ ] Schema generation round-trips cleanly (step 8)
- [ ] Docker image builds and its routes + schemas verify (step 11)
- [ ] Local branch is in sync with remote (step 12)

---

## When this passes, what's next

1. Decide whether to run a local Nextflow pipeline test. Without
   `scripts/test_batch.nf`, this means firing synthetic weblog events
   (step 10), not an actual pipeline run. Running viralrecon against the
   local stack requires Nextflow on your Mac + `PIPELINE_EXECUTOR=local`
   + manual invocation with `-weblog http://host.docker.internal:8000/...`.
2. If step 5 failed, land the Alembic baseline migration (todo.md item 2)
   before the next fresh GCP deploy.
3. If everything green, GCP deploys are safe to retry.
