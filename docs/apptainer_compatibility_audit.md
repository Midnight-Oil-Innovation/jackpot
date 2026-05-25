# Apptainer Compatibility Audit (post-monorepo housekeeping)

Reviewed `Dockerfile.api` and `Dockerfile.ui` for Apptainer compatibility
per the Phase P0e/P0f Scenario B (HPC) requirement (university research-
computing operators where Docker is not allowed on the cluster; per
the May 2026 Cluster A merge, what was historically called "Scenario C
university RC-hosted" is now folded into Scenario B HPC, with single-org
cloud taking the C slot). This is
an **audit, not a fix** — results inform the actual Apptainer-support
work in the `jackpot init` CLI (P0e ongoing).

The audit covers the five categories most likely to break when a Docker
image is converted to a SIF (Singularity Image Format) and run via
`apptainer run` instead of `docker run`:

1. **USER directive** — Apptainer ignores it; the container runs as the
   invoking user, with that user's UID/GID inside the container.
2. **Root-write paths** — Apptainer mounts most of the filesystem
   read-only by default. Anything that writes outside the user's home
   or an explicit bind-mount fails.
3. **Docker socket** — `/var/run/docker.sock` is a Docker-specific
   IPC endpoint. Apptainer has no equivalent.
4. **Privileged ports** — Apptainer runs as user; ports < 1024 require
   capabilities the user doesn't have.
5. **PID-1 init signals** — Docker has tini-equivalent PID-1 signal
   forwarding; Apptainer's PID-1 model is different and well-behaved
   shutdown can't be assumed.

Key (column "Status"):

- ✅ — clean (no Docker-specific assumption found)
- ⚠️ — works in Docker but flags an Apptainer footgun; needs operator
  awareness or a runtime override
- ❌ — outright incompatible; needs a code/config fix before Scenario B HPC
  can run this image

---

## Dockerfile.api

```dockerfile
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY backend/ ./backend/
COPY cli/ ./cli/
COPY schema/ ./schema/
RUN uv sync --frozen --all-groups
RUN install -m 0755 backend/backend/entrypoint.sh /usr/local/bin/jackpot-entrypoint.sh
EXPOSE 8000
CMD ["/usr/local/bin/jackpot-entrypoint.sh"]
```

| Item              | Status | Notes                                                                                                                                                                                                                                                                                              |
|-------------------|--------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| USER directive    | ✅     | None set; container runs as root in Docker. Apptainer will ignore root and run as the invoking user — uvicorn binds to `0.0.0.0:8000` (non-privileged), so this is fine.                                                                                                                           |
| Root-write paths  | ⚠️     | `entrypoint.sh` does `cd /app/backend` and `alembic upgrade head`. Alembic doesn't write to `/app`, but **`/opt/venv` was built at image-build time and is read-only at runtime under Apptainer.** Any runtime `pip install` (none today, but worth flagging) would fail.                          |
| Root-write paths  | ⚠️     | The api process writes pytest cache, log files, and Nextflow temp dirs to the cwd if cwd is `/app`. Under Apptainer, `/app` is in the read-only image layer. Operator must bind-mount a writable scratch dir over `/app/.pytest_cache` or `cd` into `$HOME` before running tests inside the image. |
| Docker socket     | ❌     | `docker-compose.yml` mounts `/var/run/docker.sock` into this container so testcontainers can spawn sibling Postgres containers. **Apptainer has no docker daemon to talk to.** Scenario B HPC must use a bind-mounted live Postgres (or a SIF Postgres run as a sibling) — not testcontainers.         |
| Privileged ports  | ✅     | Only port 8000 is exposed (uvicorn). Above 1024.                                                                                                                                                                                                                                                   |
| PID-1 signals     | ⚠️     | `entrypoint.sh` does `exec uvicorn ...` so uvicorn becomes PID 1. Uvicorn handles SIGINT/SIGTERM correctly. Under Apptainer, signal forwarding goes through the Apptainer runtime — verified to work for SIGTERM-clean shutdown but worth a smoke test in the Apptainer Scenario B harness.        |

---

## Dockerfile.ui

```dockerfile
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY backend/ ./backend/
COPY cli/ ./cli/
COPY schema/ ./schema/
COPY frontend/ ./frontend/
RUN uv sync --frozen --no-dev
EXPOSE 8501
CMD ["/opt/venv/bin/streamlit", "run", "frontend/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

| Item              | Status | Notes                                                                                                                                                                                                                                                                                                                            |
|-------------------|--------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| USER directive    | ✅     | None set; runs as root in Docker, as invoking user in Apptainer. Streamlit is happy on either.                                                                                                                                                                                                                                   |
| Root-write paths  | ⚠️     | Streamlit writes session state to `~/.streamlit/` by default. Under Apptainer, `~` is the **invoking user's** home (not the image's `/root/`), which is writable, so this works without intervention. However, `/app/frontend/.streamlit/` (CWD-relative) would be read-only — operators should set `STREAMLIT_HOME=$HOME/.streamlit`. |
| Docker socket     | ✅     | UI doesn't touch the docker socket.                                                                                                                                                                                                                                                                                              |
| Privileged ports  | ✅     | Streamlit binds 8501 (above 1024). Fine.                                                                                                                                                                                                                                                                                         |
| PID-1 signals     | ✅     | Streamlit's `streamlit run` becomes PID 1; SIGTERM-clean shutdown is verified upstream. No cause for concern under Apptainer.                                                                                                                                                                                                    |

---

## UID/GID assumptions (cross-cutting)

Neither Dockerfile sets a UID explicitly, but both rely on `root` being
able to read `/opt/venv` and execute `/opt/venv/bin/uvicorn` /
`/opt/venv/bin/streamlit`. Apptainer maps the invoking user into the
container; that user can read `/opt/venv` because it was built world-
readable by `uv sync`. Verified safe on a smoke test against Apptainer
1.3.

A Scenario B HPC deployment that customizes the venv permissions (e.g. a
restrictive operator umask) could break this. The Apptainer-support
work in P0e should produce a definition file (`.def`) that explicitly
chmods `/opt/venv` to 0755 and sets `umask 022` before `uv sync`, as
defense in depth.

---

## Recommended fixes (prioritized)

1. **High — testcontainers and the docker socket.** Scenario B HPC needs a
   first-class "use a real Postgres bind-mount or sibling SIF" path
   that doesn't depend on the docker socket. The api image as-is
   cannot run integration tests under Apptainer. Concretely: add a
   `JACKPOT_DB_URL` override that the test harness reads when
   `INSIDE_APPTAINER=1`, and bind-mount a Postgres SIF or a host-
   running Postgres into the Apptainer instance. Pairs with
   `tests/conftest.py` `db_conn` fixture work.
2. **High — explicit Apptainer definition file.** Produce
   `deploy/apptainer/jackpot-api.def` that mirrors `Dockerfile.api`
   but adds a `%files` section binding writable scratch into
   `/app/.pytest_cache` and `/tmp/jackpot`, an `%environment` block
   setting `STREAMLIT_HOME=$HOME/.streamlit`, and a `%post` block
   that explicitly `chmod 0755 /opt/venv -R`. Lives next to the Helm
   chart at `deploy/helm/jackpot-api/` for parity.
3. **Medium — entrypoint cwd-write check.** `entrypoint.sh` should
   `mkdir -p "${JACKPOT_RUNTIME_DIR:-/tmp/jackpot}"` and `cd` into it
   before launching uvicorn, so any process that tries to write to
   cwd lands in a writable location. Same fix is harmless under
   Docker (where cwd is already writable).
4. **Medium — Streamlit home env var.** Set `STREAMLIT_HOME` in
   `Dockerfile.ui` to a path under `/tmp/jackpot-streamlit` (or
   `$HOME/.streamlit` if the env propagates) so that operators
   running the UI image under Apptainer don't have to know to set it.
5. **Low — drop USER directive lint.** Add a CI check that flags any
   future `USER` directive in either Dockerfile, since under
   Apptainer it is silently ignored. A misleading `USER nonroot`
   would suggest a security boundary that doesn't exist on scenario
   C deploys.

The Apptainer-support work itself happens in a separate session
(P0e CLI ongoing). This document only enumerates the gaps.
