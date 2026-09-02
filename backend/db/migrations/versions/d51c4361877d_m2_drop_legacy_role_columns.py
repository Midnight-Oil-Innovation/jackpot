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

  ``user:manage``    -> instance_administrator only at Instance scope. Held
                       by ``lab_lead`` too, but only ever at a LAB scope.
  ``anomaly:review`` -> surveillance_officer only, and no lab preset holds it.

**Both queries pin ``scope_ref = 'instance://self'``, including the analyst
one.** That is not redundant belt-and-braces on the second: the columns were
GLOBAL flags, and ``surveillance_officer`` is an Instance-scope preset, so a
lab-scoped ``anomaly:review`` — which no preset issues today, but a direct
grant could — must NOT reconstruct as a deployment-wide data analyst.
Dropping the predicate would widen the reconstruction, and widening is the
direction that turns a downgrade into a privilege grant.

Deliberately NOT ``sample:read_surveillance``: both Instance presets hold
it, so it cannot tell them apart. That is the same trap slice 8's first
test fell into.

What downgrade cannot restore is a flag set on a user who was never
reseeded — one written before M2-B1 and never translated. Per
``access_model.md`` §10 that population is empty by construction (greenfield,
no installed base), and the reseed's own pre-flight guard counted the
exceptions when it ran.

Nor does it survive going further back: at least three earlier revisions
(``b2f47c1a9e30``, ``e5b3f27a91c4``, ``f9c3e60b7d18``) delete grant rows by
``source`` in their own downgrades, so downgrading past one of those and then
past this one reconstructs nothing. The reversibility claimed here is for THIS
step, not for the chain.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d51c4361877d"
down_revision: str | None = "a7f1c30d54b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INSTANCE_SCOPE = "instance://self"

#: Legacy column -> the capability that reconstructs it, and only it.
#:
#: See the module docstring for why these two and not ``sample:read_surveillance``.
RECONSTRUCT_FROM = (
    ("is_platform_admin", "user:manage"),
    ("is_data_analyst", "anomaly:review"),
)

_ADD_COLUMN = "ALTER TABLE users ADD COLUMN IF NOT EXISTS {column} BOOLEAN NOT NULL DEFAULT FALSE"

#: The reconstruction predicate.
#:
#: Deliberately the same shape as ``principal._CAPABILITY_HOLDERS_SQL``, which
#: is the reviewed answer to "who holds capability C at scope S". The first
#: version of this statement omitted three of its predicates, and each omission
#: was a widening in the direction this file's own docstring warns about:
#:
#:   ``not_after``  — an EXPIRED grant would have restored the flag.
#:   ``conditions`` — a CONDITIONAL grant would have restored an
#:                    unconditional, deployment-wide boolean.
#:   ``is_active``  — a deactivated user would have come back flagged.
#:
#: ``sync_instance_preset`` issues with ``not_after=None`` and no conditions,
#: so no preset produces such a grant today. That is the same "no preset issues
#: one today" posture that was judged insufficient for scope, and it is
#: insufficient here for the same reason: a direct grant can, and widening a
#: downgrade is how a schema rollback becomes a privilege grant (Rule 73 —
#: assert the direction).
#:
#: ``SET = EXISTS(...)`` rather than ``SET TRUE ... WHERE EXISTS``: with
#: ``ADD COLUMN IF NOT EXISTS`` the column may already hold stale values, and
#: only-ever-setting-TRUE accumulates instead of restoring. This form is
#: idempotent whatever the column held.
_RECONSTRUCT_SQL = """
    UPDATE users u SET {column} = EXISTS (
        SELECT 1 FROM authz_capability_grants g
        WHERE g.principal_id = u.id::text
          AND g.capability = :cap
          AND g.scope_ref = :scope
          AND g.conditions = CAST('{{}}' AS JSONB)
          AND (g.not_after IS NULL OR g.not_after > NOW())
          AND u.is_active = TRUE
    )
"""


def reconstruct(bind) -> None:
    """Re-add the legacy columns and rebuild them from the grants.

    The whole of ``downgrade()``, exported so the test exercises this rather
    than a copy. The DDL belongs inside it for the same reason the UPDATE
    does: a test that pastes ``BOOLEAN NOT NULL DEFAULT FALSE`` stops noticing
    when the column type changes here.
    """
    for column, capability in RECONSTRUCT_FROM:
        bind.execute(sa.text(_ADD_COLUMN.format(column=column)))
        bind.execute(
            sa.text(_RECONSTRUCT_SQL.format(column=column)),
            {"cap": capability, "scope": INSTANCE_SCOPE},
        )


def upgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_platform_admin")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_data_analyst")


def downgrade() -> None:
    reconstruct(op.get_bind())
