"""rename_is_lab_admin_to_is_lab_director

Revision ID: a7fd1fcccb77
Revises:
Create Date: 2026-04-06 23:03:24.934290

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7fd1fcccb77"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "lab_membership",
        "is_lab_admin",
        new_column_name="is_lab_director",
    )


def downgrade() -> None:
    op.alter_column(
        "lab_membership",
        "is_lab_director",
        new_column_name="is_lab_admin",
    )
