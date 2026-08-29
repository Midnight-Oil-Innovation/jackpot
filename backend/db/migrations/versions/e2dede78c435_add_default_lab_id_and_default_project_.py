"""add default_lab_id and default_project_id to personal_tokens

Revision ID: e2dede78c435
Revises: 919759af99a1
Create Date: 2026-04-16 22:39:30.617318

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2dede78c435"
down_revision: str | None = "919759af99a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "personal_tokens",
        sa.Column(
            "default_lab_id",
            sa.Integer(),
            sa.ForeignKey("labs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "personal_tokens",
        sa.Column(
            "default_project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("personal_tokens", "default_project_id")
    op.drop_column("personal_tokens", "default_lab_id")
