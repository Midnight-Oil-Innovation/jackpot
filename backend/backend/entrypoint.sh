#!/usr/bin/env bash
set -euo pipefail

/opt/venv/bin/alembic upgrade head
exec /opt/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
