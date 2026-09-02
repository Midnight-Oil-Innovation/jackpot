"""M2-DROP-PRE — issue the deletion:self_approve grant to instance admins.

``PRESET_GRANTS`` is a template, not a live view: the grants are rows, so a
capability added to a preset reaches nobody until a reseed runs. M2-DROP-PRE
added ``deletion:self_approve`` to ``instance_administrator``, and without this
migration every existing admin would keep the old grant set — which, given the
route now derives §6.2-1b's escape from the held capability rather than from
the request body, would silently take self-approval away from the actors the
design grants it to.

Purely additive: ``reseed()`` INSERTs with ``ON CONFLICT DO NOTHING`` against
``(principal_id, capability, scope_ref)``, so it issues the one missing row per
admin and touches nothing else.

Revision ID: c4d81a06f2b7
Revises: f9c3e60b7d18
Create Date: 2026-09-01
"""

import logging
import os
from collections.abc import Sequence

from alembic import op

from backend.authz.reseed import ReseedPreflightError, preflight_counts, reseed

revision: str = "c4d81a06f2b7"
down_revision: str | None = "f9c3e60b7d18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.runtime.migration")

_OVERRIDE_ENV = "JACKPOT_RESEED_ACCEPT_DATA_LOSS"


def upgrade() -> None:
    conn = op.get_bind()

    counts = preflight_counts(conn)
    logger.info("M2-DROP-PRE preset reseed — pre-flight counts (0 expected):")
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
    """Revoke exactly the verb this migration's preset change introduced.

    Identifiable, unlike a1c7d94e6b28's catch-up: no earlier migration could
    have issued ``deletion:self_approve`` because no preset listed it.
    """
    from sqlalchemy import text

    from backend.authz.reseed import GRANT_SOURCE
    from backend.authz.scope import scope_uri

    op.get_bind().execute(
        text(
            "DELETE FROM authz_capability_grants "
            "WHERE scope_ref = :scope AND source = :src "
            "AND capability = 'deletion:self_approve'"
        ),
        {"scope": scope_uri(), "src": GRANT_SOURCE},
    )
