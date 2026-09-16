"""unique pending access request per sample and requester

The router guards against a duplicate pending request with a SELECT before
the INSERT. Two concurrent requests from the same user both pass that check,
and nothing downstream stops them: the table has only a SERIAL primary key
and foreign keys, so the race writes a second PENDING row silently — no
error, no log, and a reviewer sees the same request twice.

A partial unique index makes the database the arbiter, which is the only
thing that can be. PENDING only: a user may legitimately request access
again after a previous request was DENIED or expired, so the constraint has
to exclude terminal states rather than cover the whole table.

If this migration fails with a unique-violation, the data already contains
duplicate PENDING rows and the right resolution is a judgement call — keep
the earliest and cancel the rest, or merge them — not something this
migration should decide silently.

Not CONCURRENTLY: that cannot run inside a transaction, and Alembic wraps
each migration in one. The table is small and this is pre-production; if it
ever needs to run against a live table of size, the index build wants its
own autocommit migration.

Revision ID: 64c8dda7c914
Revises: d51c4361877d
Create Date: 2026-09-16
"""

from alembic import op

revision = "64c8dda7c914"
down_revision = "d51c4361877d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS sample_access_requests_one_pending_uniq
            ON sample_access_requests (sample_id, requester_id)
            WHERE status = 'PENDING'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS sample_access_requests_one_pending_uniq")
