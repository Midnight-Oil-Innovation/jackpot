"""rename otero seed lab to outpost

Revision ID: e5315db18d40
Revises: dc1d08fa8c41
Create Date: 2026-04-24 22:38:53.139282

UI-B: the local-dev seed lab is "Otero Outpost", not "Otero Lab".
Update both the JACKPOT lab row and the linked sequencing-lab row.
Idempotent — only renames when the old name is still present so it's
safe to re-run on environments that already adopted the new name.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e5315db18d40"
down_revision: str | None = "dc1d08fa8c41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE sequencing_labs SET name = 'Otero Outpost' WHERE name = 'Otero Lab'")
    op.execute("UPDATE labs SET display_name = 'Otero Outpost' WHERE display_name = 'Otero Lab'")


def downgrade() -> None:
    op.execute("UPDATE labs SET display_name = 'Otero Lab' WHERE display_name = 'Otero Outpost'")
    op.execute("UPDATE sequencing_labs SET name = 'Otero Lab' WHERE name = 'Otero Outpost'")
