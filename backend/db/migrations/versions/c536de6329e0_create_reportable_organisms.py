"""create_reportable_organisms

Revision ID: c536de6329e0
Revises: 3f18545e3844
Create Date: 2026-04-10 22:50:05.298971

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c536de6329e0"  # pragma: allowlist secret
down_revision: str | None = "3f18545e3844"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS reportable_organisms (
            id             SERIAL PRIMARY KEY,
            organism_name  TEXT NOT NULL UNIQUE,
            is_active      BOOLEAN NOT NULL DEFAULT TRUE,
            added_by_id    INTEGER REFERENCES users(id),
            notes          TEXT,
            created_at     TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_reportable_organisms_name
            ON reportable_organisms(organism_name)
            WHERE is_active = TRUE;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS reportable_organisms;")
