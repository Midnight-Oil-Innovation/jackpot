"""M2-DROP: drop users.is_platform_admin and users.is_data_analyst.

Revision ID: d51c4361877d
Revises: a7f1c30d54b9
Create Date: 2026-09-02

The end of the APGAP boolean roles. Since M2-B1 nothing has *decided* on
either column — authorization is ``permit()`` over the grants in
``authz_capability_grants`` — and M2-DROP-PRE slices 1-8 retired every
reader. What remained was writes keeping the columns in step for
``reseed()``'s benefit, and those go with this migration.

**Scope.** This drops the two boolean columns and nothing else.
``access_model.md`` §10.1 also lists "the six-value APGAP permission-group
enum on ``lab_membership`` rows", which is NOT dropped here and is not a
Postgres enum: ``permission_groups`` is a table, ``lab_membership`` carries
an FK to it, and it is the live input to ``sync_membership_grants`` and to
dev-login's lab roles. Critical Rule 1 also declares those six names sacred.
Retiring it is its own reader-retirement campaign (``B-PERMGROUPS-DROP``),
not a rider on an irreversible migration — which is precisely the mistake
the M2 entry's own notes record.

**On reversibility.** Dropping a column is normally one-way, but these two
are *derivable*: the grants the columns were translated into are still
there, so ``downgrade()`` re-adds the columns and reconstructs their values
from ``authz_capability_grants``. The reconstruction keys on a capability
that is unique to each Instance preset at the instance root:

  ``user:manage``    -> instance_administrator only. Held by ``lab_lead``
                       too, but only ever at a LAB scope, and the WHERE
                       clause pins ``scope_ref = 'instance://self'``.
  ``anomaly:review`` -> surveillance_officer only, at any scope.

Deliberately NOT ``sample:read_surveillance``: both Instance presets hold
it, so it cannot tell them apart. That is the same trap slice 8's first
test fell into.

What downgrade cannot restore is a flag that was set on a user who was
never reseeded — i.e. one written before M2-B1 and never translated. Per
``access_model.md`` §10 that population is empty by construction
(greenfield, no installed base), and the reseed's own pre-flight guard
counted the exceptions when it ran.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d51c4361877d"
down_revision: str | None = "a7f1c30d54b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INSTANCE_SCOPE = "instance://self"


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS is_platform_admin"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS is_data_analyst"))


def downgrade() -> None:
    op.execute(
        sa.text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
            "is_platform_admin BOOLEAN NOT NULL DEFAULT FALSE"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
            "is_data_analyst BOOLEAN NOT NULL DEFAULT FALSE"
        )
    )
    # Reconstruct from the grants the columns were translated into. See the
    # module docstring for why these two capabilities and not others.
    op.execute(
        sa.text(
            """
            UPDATE users u SET is_platform_admin = TRUE
            WHERE EXISTS (
                SELECT 1 FROM authz_capability_grants g
                WHERE g.principal_id = u.id::text
                  AND g.capability = 'user:manage'
                  AND g.scope_ref = :scope
            )
            """
        ).bindparams(scope=INSTANCE_SCOPE)
    )
    op.execute(
        sa.text(
            """
            UPDATE users u SET is_data_analyst = TRUE
            WHERE EXISTS (
                SELECT 1 FROM authz_capability_grants g
                WHERE g.principal_id = u.id::text
                  AND g.capability = 'anomaly:review'
                  AND g.scope_ref = :scope
            )
            """
        ).bindparams(scope=INSTANCE_SCOPE)
    )
