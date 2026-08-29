"""M2 cutover: reseed APGAP roles into capability grants, then remove the legacy role storage.

Staged here (outside the live ``db/migrations/versions`` chain) per the
ACCESS-SEED scope: written and tested ahead of the M2 cutover PR, which
moves this file into the live chain and re-points ``down_revision`` at
the then-current head. Reads-then-removes in one upgrade so there is
never a dual-authoritative window (access_model.md §10.2).

Revision ID: b7e2c9a4f1d3
Revises: d8f3b6c1a2e4
"""

from sqlalchemy import text

from alembic import op
from backend.authz.reseed import reseed

# revision identifiers, used by Alembic.
revision: str = "b7e2c9a4f1d3"
down_revision: str | None = "d8f3b6c1a2e4"
branch_labels = None
depends_on = None

# Raw-SQL migration; JACKPOT has no ORM metadata (CLAUDE.md Critical Rule 2).
target_metadata = None


def upgrade() -> None:
    # Uniqueness arbiter for the reseed's ON CONFLICT DO NOTHING inserts.
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "authz_capability_grants_principal_capability_scope_uniq "
            "ON authz_capability_grants (principal_id, capability, scope_ref)"
        )
    )

    # Reads-then-drops: reseed MUST run before any legacy column/type removal.
    reseed(op.get_bind())

    op.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS is_platform_admin"))
    op.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS is_data_analyst"))
    op.execute(text("ALTER TABLE lab_membership DROP COLUMN IF EXISTS permission_group_id"))
    op.execute(text("DROP TABLE IF EXISTS permission_groups CASCADE"))
    op.execute(text("DROP TYPE IF EXISTS permissiongroups"))


def downgrade() -> None:
    raise NotImplementedError("reseed migration is irreversible")
