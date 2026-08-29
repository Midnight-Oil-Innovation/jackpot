.PHONY: status guardrails test lint

status:
	@uv run python scripts/gen_status.py

guardrails:
	@uv run python scripts/check_docs.py
	@uv run python scripts/check_backlog.py
	@uv run python scripts/check_migration_heads.py
# Mirrors .github/workflows/guardrails.yml: Python deps are the enforcing
# gate, wrapped tools are report-only. Without --report this target enforced
# wrapped tools too, so `make guardrails` was red locally while CI was green.
	@uv run python scripts/verify_licenses.py --skip-wrapped-tools
	@uv run python scripts/verify_licenses.py --skip-python --report

test:
	@uv run pytest tests/ schema/tests/ cli/tests/

lint:
	@uv run ruff check .
