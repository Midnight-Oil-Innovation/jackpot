"""Issue user:manage to Lab Leads at their own lab scope.

``PRESET_GRANTS`` is a template, not a live view: the grants are rows, so a
capability added to a preset reaches nobody until a reseed runs. This one
restores something M2 removed by accident — the four ``/labs/{id}/members``
routes moved from ``require_lab_director(user, lab_id)`` to
``require_capability("user:manage")`` at Lab scope while no lab preset held
that verb, so every existing deployment's Lab Directors are currently locked
out of the roster of the lab they direct.

Scoped, not global: ``reseed()`` issues preset capabilities at
``lab://<their lab>``, and the routes that administer users at large ask for
``user:manage`` with no scope argument, which resolves to the instance root. A
lab grant does not contain the root.

Purely additive: ``reseed()`` INSERTs with ``ON CONFLICT DO NOTHING`` against
``(principal_id, capability, scope_ref)``, so it issues the one missing row per
Lab Director and touches nothing else.

Revision ID: a7f1c30d54b9
Revises: e5b3f27a91c4
Create Date: 2026-09-01
"""

import logging
import os
from collections.abc import Sequence

from alembic import op

from backend.authz.reseed import ReseedPreflightError, preflight_counts, reseed

revision: str = "a7f1c30d54b9"
down_revision: str | None = "e5b3f27a91c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.runtime.migration")

_OVERRIDE_ENV = "JACKPOT_RESEED_ACCEPT_DATA_LOSS"


def upgrade() -> None:
    conn = op.get_bind()

    counts = preflight_counts(conn)
    logger.info("lab_lead user:manage reseed — pre-flight counts (0 expected):")
    for kind, n in sorted(counts.items()):
        logger.info("    %-32s %d", kind, n)

    force = os.getenv(_OVERRIDE_ENV, "").strip() == "1"
    try:
        reseed(conn, force=force)
    except ReseedPreflightError as exc:
        raise RuntimeError(
            str(exc) + f"\n\nSet {_OVERRIDE_ENV}=1 to accept the change deliberately.\n"
        ) from exc


def downgrade() -> None:
    """Revoke user:manage only where this migration could have issued it.

    Deliberately NOT a blanket delete on the capability: instance admins hold
    user:manage at ``instance://self`` from the M2 cutover, and dropping those
    would leave a deployment with nobody able to administer users at all. Only
    the lab-scoped rows this preset change introduced are removed.
    """
    from sqlalchemy import text

    from backend.authz.reseed import GRANT_SOURCE

    op.get_bind().execute(
        text(
            "DELETE FROM authz_capability_grants "
            "WHERE source = :src AND capability = 'user:manage' "
            "AND scope_ref LIKE '%/lab/%'"
        ),
        {"src": GRANT_SOURCE},
    )
