# Dockerfile strategy

How the JACKPOT container images are built, what each contains, and
when to use which. Surfaced from the post-monorepo housekeeping pass —
the previous state had multiple unsigned-off implicit choices.

## Image variants

JACKPOT ships two images out of `Dockerfile.api` and `Dockerfile.ui`
at the workspace root. Production deploys (scenarios B/C/D/E/T) use
the Helm chart at `deploy/helm/jackpot-api/` and pin specific tags;
local dev (scenario A) and CI (scenario F) use `docker-compose.yml`
which builds the images from the same Dockerfiles via `build:`.

| Image           | Source              | Used by                           | Contains                                  |
|-----------------|---------------------|-----------------------------------|-------------------------------------------|
| `jackpot_api`   | `Dockerfile.api`    | `api` service in compose; Helm    | FastAPI app + uv venv at `/opt/venv`      |
| `jackpot_ui`    | `Dockerfile.ui`     | `ui` service in compose           | Streamlit researcher UI + uv venv         |

Both images base on `python:3.11-slim` and use `uv` from
`ghcr.io/astral-sh/uv:latest` for dependency resolution.

## The lean-vs-include-dev question

`uv sync` has two relevant modes for a workspace member:

- `uv sync --frozen --no-dev` — installs only the runtime deps
  declared in `[project].dependencies`. Smallest image, but tests
  cannot run inside the container without a follow-up
  `uv pip install`.
- `uv sync --frozen --all-groups` — also installs
  `[dependency-groups.dev]` (pytest, testcontainers, hypothesis,
  ruff, mypy, etc.). Larger image, but the same image can run the
  test suite end-to-end without any post-build steps.

**JACKPOT chose `--all-groups` for `Dockerfile.api`** as of the
post-monorepo housekeeping pass + P0f F-3 (May 2026). `Dockerfile.ui`
stays on `--no-dev` because the UI image never runs tests.

The reasoning for including dev deps in the api image:

1. **Local dev (scenario A) and CI (scenario F) both run the test
   suite from inside the api container** once the docker socket is
   mounted (see `docker-compose.yml`). A lean image forces
   contributors to run tests from the host, which works but creates
   asymmetry between "tests as a developer runs them" and "tests as
   CI runs them" — a known source of flake.
2. **The Apple-Silicon path (`PIPELINE_EXECUTOR=local`) regularly
   needs an interactive shell into the api container** to debug
   bioinformatics container compatibility. Having pytest available
   in that shell is consistently useful.
3. **Production images are built and tagged separately** by the Helm
   chart pipeline (deploy/helm/jackpot-api/). The compose-built
   image is never deployed to GCP. Image size for laptop dev is
   measured in disk-on-the-developer's-laptop, not bandwidth in a
   pull.

If image size becomes a real constraint for laptop dev (currently
~600MB), the right fix is a multi-stage build that produces both
`api-prod` and `api-dev` tags from one Dockerfile rather than
flipping the choice. Don't optimize prematurely.

## How to add a new dependency

**Runtime dep** (used by the FastAPI app, the validator, the
ingest gate, etc.):

```bash
cd backend
uv add <package>
```

This appends to `backend/pyproject.toml`'s `[project].dependencies`
and updates the workspace `uv.lock`.

**Dev dep** (test, lint, dev tooling):

```bash
cd backend
uv add --dev <package>
```

This appends to `backend/pyproject.toml`'s `[dependency-groups.dev]`
and updates the workspace `uv.lock`. The api image picks it up on
next `docker compose build api`.

Same flow applies to `cli/` and `schema/` — `uv add` from inside
the workspace member directory.

After either, rebuild the image:

```bash
COMPOSE_PROFILES=laptop docker compose build api
COMPOSE_PROFILES=laptop docker compose up -d api
```

## Production-vs-laptop divergence

The Helm chart at `deploy/helm/jackpot-api/` may build a leaner
image for production where the test suite is irrelevant. That choice
is independent of this document and lives with the chart values.

For the avoidance of doubt: this document describes the
**compose-built laptop and CI image only**.
