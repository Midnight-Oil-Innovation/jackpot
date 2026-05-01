#!/usr/bin/env bash
set -euo pipefail

# Run alembic from backend/ where alembic.ini lives and db/migrations resolves
cd /app/backend
/opt/venv/bin/alembic upgrade head

# Run uvicorn from /app where the backend package is importable
cd /app
exec /opt/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
