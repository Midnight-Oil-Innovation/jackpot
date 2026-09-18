"""Issue the sample:pii_override grant to lab leads (Critical Rule 43).

``PRESET_GRANTS`` is a template, not a live view: the grants are rows, so a
capability added to a preset reaches nobody until something issues them.
Without this migration ``POST /api/v1/samples/{id}/pii-override`` would be
reachable by no principal on any existing deployment, and a flagged sample's
only way back would be the submitter editing the offending field — the half of
Rule 43 that shipped in #264.

Deliberately NOT ``reseed()``, unlike the precedent c4d81a06f2b7. That
migration ran before M2-DROP; ``reseed()`` still reads
``users.is_platform_admin``, so calling it at this point in the chain fails
with ``UndefinedColumn``. Its own docstring says as much. What is wanted here
is one verb for one group anyway, so this issues exactly that: an INSERT ...
SELECT over the same ``lab_membership`` JOIN ``permission_groups`` pair the
membership half of ``reseed()`` reads, ``ON CONFLICT DO NOTHING`` against
``authz_capability_grants_principal_capability_scope_uniq``. No deletes, no
other capability touched.

The group name and the capability are literals rather than reads of
``MEMBERSHIP_PRESETS`` / ``PRESET_GRANTS``: a migration must produce the same
rows in five years that it produces today, and a preset is editable. Only
``scope_uri`` is imported, because re-expressing the scope path in SQL would
be a second implementation of the one thing that decides containment.

The ``pii_scan_status`` column needs no DDL — it is ``TEXT NOT NULL DEFAULT
'PENDING'`` with no CHECK constraint, so the new ``OVERRIDDEN`` value is a
schema-layer change only.

Revision ID: cab9f75533cb
Revises: 64c8dda7c914
Create Date: 2026-09-18
"""

import logging
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from backend.authz.scope import scope_uri

revision: str = "cab9f75533cb"
down_revision: str | None = "64c8dda7c914"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.runtime.migration")

# Critical Rule 1: "Lab Director" is a sacred permission_groups value, and
# MEMBERSHIP_PRESETS maps it to the lab_lead preset this verb was added to.
_GROUP = "Lab Director"
_CAPABILITY = "sample:pii_override"
# Must match backend.authz.reseed.GRANT_SOURCE — preset-issued, so a later
# membership sync's delete-then-insert owns these rows rather than orphaning
# them. Written out so the migration does not import reseed at all.
_SOURCE = "reseed"

_INSERT = text(
    """
    INSERT INTO authz_capability_grants
        (principal_id, capability, scope_ref, source, not_after)
    VALUES (:principal_id, :capability, :scope_ref, :source, NULL)
    ON CONFLICT DO NOTHING
    """
)


def issue_grants(conn) -> int:
    """The upgrade body, taking its connection as an argument.

    Separated so a test can run it against a savepoint. Without that there is
    no way to observe this migration at all: ``b2f47c1a9e30`` earlier in the
    chain calls ``reseed()``, which reads ``PRESET_GRANTS`` live, so on a
    database built from empty the seeded Lab Director already holds every
    capability the preset lists — including this one — before this migration
    runs. A fresh install cannot distinguish "the migration works" from "the
    migration does nothing", which is exactly the shape Critical Rule 74 is
    about. Existing deployments, where ``b2f47c1a9e30`` ran against the older
    preset, are the ones that need these rows.
    """
    memberships = conn.execute(
        text(
            "SELECT lm.user_id, lm.lab_id, l.organization_id "
            "FROM lab_membership lm "
            "JOIN permission_groups pg ON pg.id = lm.permission_group_id "
            "JOIN labs l ON l.id = lm.lab_id "
            "WHERE pg.name = :group_name"
        ),
        {"group_name": _GROUP},
    ).fetchall()

    for user_id, lab_id, org_id in memberships:
        conn.execute(
            _INSERT,
            {
                "principal_id": str(user_id),
                "capability": _CAPABILITY,
                "scope_ref": scope_uri(org=org_id, lab=lab_id),
                "source": _SOURCE,
            },
        )

    logger.info(
        "%s: %d %r memberships read, one grant attempted each",
        _CAPABILITY,
        len(memberships),
        _GROUP,
    )
    return len(memberships)


def upgrade() -> None:
    issue_grants(op.get_bind())


def downgrade() -> None:
    """Revoke exactly the verb this migration introduced.

    Identifiable for the same reason c4d81a06f2b7's was: no earlier migration
    could have issued ``sample:pii_override`` because no preset listed it.

    Samples already moved to ``OVERRIDDEN`` are deliberately left alone. The
    decision was made and audited; reverting the grant withdraws the authority
    to make new ones, not the ones already taken.

    No scope_ref filter, unlike c4d81a06f2b7: that verb was granted once at
    instance scope, this one is lab-scoped and so has a distinct scope_ref per
    lab lead. The capability name alone identifies the rows.
    """
    op.get_bind().execute(
        text("DELETE FROM authz_capability_grants WHERE source = :src AND capability = :cap"),
        {"src": _SOURCE, "cap": _CAPABILITY},
    )
