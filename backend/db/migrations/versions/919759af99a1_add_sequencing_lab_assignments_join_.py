"""add sequencing_lab_assignments join table

Revision ID: 919759af99a1
Revises: 10066df35f84
Create Date: 2026-04-16 22:30:08.705081

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "919759af99a1"
down_revision: str | None = "10066df35f84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sequencing_lab_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "sequencing_lab_id",
            sa.Integer(),
            sa.ForeignKey("sequencing_labs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lab_id",
            sa.Integer(),
            sa.ForeignKey("labs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("sequencing_lab_id", "lab_id", name="uq_seq_lab_assignment"),
    )


def downgrade() -> None:
    op.drop_table("sequencing_lab_assignments")
