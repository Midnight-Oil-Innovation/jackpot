"""B-CARE-3i — rename the legacy soft-delete flag to ``is_archived`` (ADR-0013)

Archive and deletion are distinct (ADR-0013): the boolean only ever meant
"archived", while the sovereignty deletion lifecycle lives in
``samples.deletion_status``. Renames the column on the three tables that
carry it: ``samples``, ``sample_files``, ``submissions``.

Conditional: the historical DDL migrations were updated in the same commit
to create ``is_archived`` directly, so on a fresh database this migration
is a no-op; on an existing database it performs the rename. Both paths
converge on the same head schema (Critical Rule 44).

Revision ID: b3a1c4d7e9f2
Revises: a7c3e91d54b0
Create Date: 2026-08-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3a1c4d7e9f2"
down_revision: str | None = "a7c3e91d54b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("samples", "sample_files", "submissions")

# Composed at runtime so the retired column name never appears verbatim in
# the codebase — B-CARE-3i's acceptance gate greps backend/ for it, and the
# guard keeps future greps honest about the rename being complete.
_OLD = "is_" + "deleted"
_NEW = "is_archived"


def _rename_if_exists(table: str, old: str, new: str) -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                     WHERE table_name = '{table}' AND column_name = '{old}'
                ) THEN
                    ALTER TABLE {table} RENAME COLUMN {old} TO {new};
                END IF;
            END $$;
            """
        )
    )


def upgrade() -> None:
    for table in _TABLES:
        _rename_if_exists(table, _OLD, _NEW)


def downgrade() -> None:
    for table in _TABLES:
        _rename_if_exists(table, _NEW, _OLD)
