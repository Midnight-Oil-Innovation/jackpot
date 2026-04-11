"""redesign_audit_log

Revision ID: 655903cf2603
Revises: 1de94c16e612
Create Date: 2026-04-10 20:47:05.298224

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "655903cf2603"
down_revision: str | None = "1de94c16e612"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE audit_log
            RENAME COLUMN user_id TO actor_id;
        ALTER TABLE audit_log
            RENAME COLUMN resource TO resource_type;
        ALTER TABLE audit_log
            ADD COLUMN before_state JSONB,
            ADD COLUMN after_state  JSONB,
            ADD COLUMN metadata     JSONB;
        ALTER TABLE audit_log
            DROP COLUMN detail,
            DROP COLUMN ip_address,
            DROP COLUMN request_id;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE audit_log
            ADD COLUMN detail     JSONB,
            ADD COLUMN ip_address TEXT,
            ADD COLUMN request_id TEXT;
        ALTER TABLE audit_log
            DROP COLUMN before_state,
            DROP COLUMN after_state,
            DROP COLUMN metadata;
        ALTER TABLE audit_log
            RENAME COLUMN actor_id TO user_id;
        ALTER TABLE audit_log
            RENAME COLUMN resource_type TO resource;
    """)
