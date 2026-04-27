"""rename adhs_medsis_id to external_case_id

Revision ID: 8e963caa3d13
Revises: c1bd67369a7c
Create Date: 2026-04-26

Renames the human-sample case-management identifier column from the
operator-specific name `adhs_medsis_id` to the operator-neutral
`external_case_id`. The column semantics, type, and nullability are
unchanged.

The schema YAML at schema/schema/jackpot_schema.yaml has been updated
to match. The Pydantic models at backend/models_generated.py have been
regenerated. Backend code and tests that reference the old name are
updated in companion changes (Phase 3 — tests, Phase 4 — backend code).

This is a non-idempotent column rename. Re-running on an
already-renamed DB will fail because the source column no longer
exists. That is acceptable for an Alembic migration — Alembic tracks
applied revisions and will not re-run.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "8e963caa3d13"
down_revision: str | None = "c1bd67369a7c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("samples", "adhs_medsis_id", new_column_name="external_case_id")


def downgrade() -> None:
    op.alter_column("samples", "external_case_id", new_column_name="adhs_medsis_id")
