.PHONY: status guardrails test lint

status:
	@uv run python scripts/gen_status.py

guardrails:
	@uv run python scripts/check_docs.py
	@uv run python scripts/check_migration_heads.py
	@uv run python scripts/verify_licenses.py --skip-python

test:
	@uv run pytest tests/ schema/tests/ cli/tests/

lint:
	@uv run ruff check .
