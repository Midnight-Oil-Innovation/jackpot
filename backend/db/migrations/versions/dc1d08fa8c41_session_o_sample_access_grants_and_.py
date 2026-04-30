"""session_o_sample_access_grants_and_request_extensions

Revision ID: dc1d08fa8c41
Revises: cea9c08543ee
Create Date: 2026-04-17 10:47:55.368354

Session O: sample_access router (request → approve/deny → grant lifecycle).

Extends sample_access_requests with the columns the new endpoint needs
(justification, requested_duration_days, auto_approve_after, approver/
denier identity + timestamps, and a last_warning_sent_at marker the
nightly job uses to avoid double-firing the 75-day / 7-day notifications).

Creates sample_access_grants — the table can_access_sample() consults
to authorise reads. A grant is the durable artefact of an APPROVED
request and carries the absolute access_expires_at; revocation is a
boolean so historical grants stay queryable for audit.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "dc1d08fa8c41"
down_revision: str | None = "cea9c08543ee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE sample_access_requests
            ADD COLUMN IF NOT EXISTS justification           TEXT,
            ADD COLUMN IF NOT EXISTS requested_duration_days INTEGER,
            ADD COLUMN IF NOT EXISTS auto_approve_after      TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS access_expires_at       TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS approved_by_id          INTEGER REFERENCES users(id),
            ADD COLUMN IF NOT EXISTS approved_at             TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS denied_by_id            INTEGER REFERENCES users(id),
            ADD COLUMN IF NOT EXISTS denied_at               TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS last_warning_sent_at    TIMESTAMPTZ
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS sample_access_requests_status_idx "
        "ON sample_access_requests (status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS sample_access_requests_sample_idx "
        "ON sample_access_requests (sample_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS sample_access_requests_requester_idx "
        "ON sample_access_requests (requester_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sample_access_grants (
            id                 BIGSERIAL PRIMARY KEY,
            sample_id          INTEGER NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
            requester_id       INTEGER NOT NULL REFERENCES users(id),
            request_id         INTEGER REFERENCES sample_access_requests(id) ON DELETE SET NULL,
            granted_by_id      INTEGER REFERENCES users(id),
            granted_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            access_expires_at  TIMESTAMPTZ,
            revoked            BOOLEAN NOT NULL DEFAULT FALSE,
            revoked_at         TIMESTAMPTZ,
            revoked_by_id      INTEGER REFERENCES users(id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS sample_access_grants_lookup_idx "
        "ON sample_access_grants (requester_id, sample_id) "
        "WHERE revoked = FALSE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS sample_access_grants_expiry_idx "
        "ON sample_access_grants (access_expires_at) "
        "WHERE revoked = FALSE"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS sample_access_grants_expiry_idx")
    op.execute("DROP INDEX IF EXISTS sample_access_grants_lookup_idx")
    op.execute("DROP TABLE IF EXISTS sample_access_grants")

    op.execute("DROP INDEX IF EXISTS sample_access_requests_requester_idx")
    op.execute("DROP INDEX IF EXISTS sample_access_requests_sample_idx")
    op.execute("DROP INDEX IF EXISTS sample_access_requests_status_idx")

    op.execute(
        """
        ALTER TABLE sample_access_requests
            DROP COLUMN IF EXISTS last_warning_sent_at,
            DROP COLUMN IF EXISTS denied_at,
            DROP COLUMN IF EXISTS denied_by_id,
            DROP COLUMN IF EXISTS approved_at,
            DROP COLUMN IF EXISTS approved_by_id,
            DROP COLUMN IF EXISTS access_expires_at,
            DROP COLUMN IF EXISTS auto_approve_after,
            DROP COLUMN IF EXISTS requested_duration_days,
            DROP COLUMN IF EXISTS justification
        """
    )
