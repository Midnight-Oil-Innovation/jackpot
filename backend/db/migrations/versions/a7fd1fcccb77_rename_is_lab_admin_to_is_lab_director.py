"""rename_is_lab_admin_to_is_lab_director

Revision ID: a7fd1fcccb77
Revises:
Create Date: 2026-04-06 23:03:24.934290

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7fd1fcccb77"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Idempotent: only rename if is_lab_admin still exists.
    # init.sql already uses is_lab_director, so a fresh DB won't need this.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'lab_membership'
                AND column_name = 'is_lab_admin'
            ) THEN
                ALTER TABLE lab_membership
                RENAME COLUMN is_lab_admin TO is_lab_director;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'lab_membership'
                AND column_name = 'is_lab_director'
            ) THEN
                ALTER TABLE lab_membership
                RENAME COLUMN is_lab_director TO is_lab_admin;
            END IF;
        END
        $$;
    """)
