"""redesign_notifications

Revision ID: 3f18545e3844
Revises: 655903cf2603
Create Date: 2026-04-10 20:52:18.879685

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f18545e3844"
down_revision: str | None = "655903cf2603"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE notifications
            RENAME COLUMN user_id TO recipient_id;
        ALTER TABLE notifications
            RENAME COLUMN type TO event_type;
        ALTER TABLE notifications
            RENAME COLUMN link TO action_url;
        ALTER TABLE notifications
            ADD COLUMN resource_type TEXT,
            ADD COLUMN resource_id   TEXT;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE notifications
            DROP COLUMN resource_type,
            DROP COLUMN resource_id;
        ALTER TABLE notifications
            RENAME COLUMN recipient_id TO user_id;
        ALTER TABLE notifications
            RENAME COLUMN event_type TO type;
        ALTER TABLE notifications
            RENAME COLUMN action_url TO link;
    """)
