"""R-1 #6 defense-in-depth — unique partial index on replaced_by_jti.

The primary fix for the refresh-token rotation race lives in the
router (``SELECT ... FOR UPDATE`` serialises rotations on the same
JTI). This migration adds a database-level constraint that catches a
race even if the application-level lock is bypassed: every active
``replaced_by_jti`` value must be unique, so two concurrent rotations
that both somehow tried to set the same ``replaced_by_jti`` would
fail at the database with a UniqueViolation rather than producing two
valid refresh chains.

Partial index because pre-rotation rows (and rotated rows whose
replacement was itself purged) carry NULL — those should not collide.

Revision ID: f5f4727258b8
Revises: 9b62dcbacaeb
Create Date: 2026-05-06 17:30:40.051176
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5f4727258b8"
down_revision: str | None = "9b62dcbacaeb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_refresh_tokens_replaced_by_jti",
        "refresh_tokens",
        ["replaced_by_jti"],
        unique=True,
        postgresql_where="replaced_by_jti IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index(
        "uq_refresh_tokens_replaced_by_jti",
        table_name="refresh_tokens",
    )
