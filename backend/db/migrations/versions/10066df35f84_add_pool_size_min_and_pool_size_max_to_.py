"""add pool_size_min and pool_size_max to vector samples

Revision ID: 10066df35f84  # pragma: allowlist secret
Revises: c536de6329e0
Create Date: 2026-04-15 22:03:13.944206

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "10066df35f84"  # pragma: allowlist secret
down_revision: str | None = "c536de6329e0"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("samples", sa.Column("pool_size_min", sa.Integer(), nullable=True))
    op.add_column("samples", sa.Column("pool_size_max", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("samples", "pool_size_max")
    op.drop_column("samples", "pool_size_min")
