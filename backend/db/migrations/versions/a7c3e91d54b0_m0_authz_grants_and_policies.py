"""M0 — authz capability grants and policy tables, dark (access_model.md §2.2, §2.5).

Hand-written raw SQL via text(); no ORM, no Alembic table helpers (§5.2
implementation note). Nothing reads these tables yet — the permit()
engine ships dark in M0 and DB-backed policy loading lands in M1+.

No priority column on authz_policies: deny-wins is absolute (§5.4),
ordering is irrelevant by design.

Revision ID: a7c3e91d54b0
Revises: 2daeecbe082d
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "a7c3e91d54b0"
down_revision: str | None = "2daeecbe082d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

target_metadata = None


def upgrade() -> None:
    op.execute(
        text(
            """
            CREATE TABLE authz_capability_grants (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                principal_id TEXT NOT NULL,
                capability TEXT NOT NULL,
                scope_ref TEXT NOT NULL,
                conditions JSONB NOT NULL DEFAULT '{}',
                source TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    op.execute(
        text(
            """
            CREATE TABLE authz_policies (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                effect TEXT NOT NULL CHECK (effect IN ('ALLOW','DENY')),
                capability TEXT NOT NULL,
                scope_ref TEXT NOT NULL,
                conditions JSONB NOT NULL DEFAULT '{}',
                description TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS authz_policies"))
    op.execute(text("DROP TABLE IF EXISTS authz_capability_grants"))
