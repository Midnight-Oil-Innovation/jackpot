"""add transport columns to federated_instances

Revision ID: 2daeecbe082d
Revises: c871b28bbdab
Create Date: 2026-07-07 17:18:30.317631

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2daeecbe082d"
down_revision: str | None = "c871b28bbdab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "federated_instances",
        sa.Column("transport_type", sa.Text(), nullable=False, server_default="HTTPS"),
    )
    op.create_check_constraint(
        "ck_federated_instances_transport_type",
        "federated_instances",
        "transport_type IN ('HTTPS', 'DTN', 'SNEAKERNET', 'LORA')",
    )
    op.add_column(
        "federated_instances",
        sa.Column("transport_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_federated_instances_transport_type", "federated_instances", type_="check"
    )
    op.drop_column("federated_instances", "transport_config")
    op.drop_column("federated_instances", "transport_type")
