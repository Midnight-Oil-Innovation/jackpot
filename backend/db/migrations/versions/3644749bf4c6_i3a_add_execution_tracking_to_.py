"""i3a_add_execution_tracking_to_submissions

I-3a: foundation for backend-driven submission execution. Adds six
tracking columns to ``submissions`` plus a partial index on the new
``EXECUTING`` state, and extends the existing ``submissions_status_valid``
CHECK constraint to permit the three new states (``EXECUTING``,
``EXECUTION_FAILED``, ``EXECUTION_INTERRUPTED``).

The migration is data-safe: every new column is either nullable or has
a default that fits already-existing rows. No row mutations.

Revision ID: 3644749bf4c6
Revises:    2a1b3c4d5e6f
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3644749bf4c6"
down_revision = "2a1b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── new tracking columns ───────────────────────────────────────
    op.execute(
        sa.text("""
        ALTER TABLE submissions
            ADD COLUMN execution_started_at      TIMESTAMPTZ,
            ADD COLUMN execution_completed_at    TIMESTAMPTZ,
            ADD COLUMN execution_log_uris        JSONB
                NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN execution_error_message   TEXT,
            ADD COLUMN execution_attempt_count   INTEGER
                NOT NULL DEFAULT 0,
            ADD COLUMN executor_backend          TEXT;
    """)
    )

    # ── extend the status CHECK constraint with the three I-3a states ──
    # We drop and re-add because PostgreSQL does not support ALTER
    # CONSTRAINT with the new expression in-place. The submissions table
    # is small in v1 deployments; the rewrite is fast.
    op.execute(
        sa.text("""
        ALTER TABLE submissions
            DROP CONSTRAINT submissions_status_valid;
    """)
    )
    op.execute(
        sa.text("""
        ALTER TABLE submissions
            ADD CONSTRAINT submissions_status_valid CHECK (
                status IN (
                    'DRAFT', 'READY_TO_SUBMIT', 'SUBMITTED',
                    'PARTIAL_SUCCESS', 'ACCEPTED', 'REJECTED',
                    'EMBARGOED', 'RELEASED', 'WITHDRAWN', 'FAILED',
                    'EXECUTING', 'EXECUTION_FAILED',
                    'EXECUTION_INTERRUPTED'
                )
            );
    """)
    )

    # ── partial index for the lifespan recovery query ──────────────
    op.execute(
        sa.text("""
        CREATE INDEX idx_submissions_status_executing
            ON submissions (id)
         WHERE status = 'EXECUTING';
    """)
    )


def downgrade() -> None:
    # Order matters: drop the partial index before dropping the column
    # it depends on isn't required (it indexes id, not status), but we
    # drop everything I-3a added in reverse declaration order for
    # clarity.
    op.execute(sa.text("DROP INDEX IF EXISTS idx_submissions_status_executing;"))

    # Restore the pre-I-3a status CHECK constraint.
    op.execute(
        sa.text("""
        ALTER TABLE submissions
            DROP CONSTRAINT IF EXISTS submissions_status_valid;
    """)
    )
    op.execute(
        sa.text("""
        ALTER TABLE submissions
            ADD CONSTRAINT submissions_status_valid CHECK (
                status IN (
                    'DRAFT', 'READY_TO_SUBMIT', 'SUBMITTED',
                    'PARTIAL_SUCCESS', 'ACCEPTED', 'REJECTED',
                    'EMBARGOED', 'RELEASED', 'WITHDRAWN', 'FAILED'
                )
            );
    """)
    )

    op.execute(
        sa.text("""
        ALTER TABLE submissions
            DROP COLUMN IF EXISTS executor_backend,
            DROP COLUMN IF EXISTS execution_attempt_count,
            DROP COLUMN IF EXISTS execution_error_message,
            DROP COLUMN IF EXISTS execution_log_uris,
            DROP COLUMN IF EXISTS execution_completed_at,
            DROP COLUMN IF EXISTS execution_started_at;
    """)
    )
