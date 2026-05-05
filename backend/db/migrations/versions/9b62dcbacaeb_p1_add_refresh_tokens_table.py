"""p1_add_refresh_tokens_table

P1: server-side tracking for issued refresh tokens. The new table is the
backing store for the ``POST /api/v1/auth/refresh`` endpoint's
single-use rotation invariant. Each row corresponds to one refresh JWT
identified by its ``jti`` claim; once used, the row's ``revoked_at`` is
stamped and ``replaced_by_jti`` points at the successor token. A reuse
of an already-rotated token is treated as a replay attempt and triggers
bulk revocation of all of the user's active tokens (handled in the
endpoint, not the migration).

Indexes:

* PK on ``jti`` — every lookup goes by JTI from the JWT payload.
* ``idx_refresh_tokens_user_id`` — supports the bulk-revoke-on-replay
  query and any future "list this user's active sessions" UI.
* ``idx_refresh_tokens_expires_active`` — partial index on
  ``expires_at`` filtered to ``revoked_at IS NULL``; lets the daily
  cleanup job sweep efficiently as the table grows.

Revision ID: 9b62dcbacaeb
Revises:    bac8dbb11c0b
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9b62dcbacaeb"
down_revision = "bac8dbb11c0b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text("""
        CREATE TABLE refresh_tokens (
            jti              TEXT PRIMARY KEY,
            user_id          INTEGER NOT NULL
                REFERENCES users(id) ON DELETE CASCADE,
            issued_at        TIMESTAMPTZ NOT NULL,
            expires_at       TIMESTAMPTZ NOT NULL,
            revoked_at       TIMESTAMPTZ,
            revoked_reason   TEXT,
            replaced_by_jti  TEXT,
            CONSTRAINT refresh_tokens_revoked_reason_valid CHECK (
                revoked_reason IS NULL OR
                revoked_reason IN (
                    'rotated', 'logout', 'admin_revoke', 'replay_detected'
                )
            )
        );
        """)
    )

    op.execute(
        sa.text("""
        CREATE INDEX idx_refresh_tokens_user_id
            ON refresh_tokens (user_id);
        """)
    )

    op.execute(
        sa.text("""
        CREATE INDEX idx_refresh_tokens_expires_active
            ON refresh_tokens (expires_at)
         WHERE revoked_at IS NULL;
        """)
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS idx_refresh_tokens_expires_active;"))
    op.execute(sa.text("DROP INDEX IF EXISTS idx_refresh_tokens_user_id;"))
    op.execute(sa.text("DROP TABLE IF EXISTS refresh_tokens;"))
