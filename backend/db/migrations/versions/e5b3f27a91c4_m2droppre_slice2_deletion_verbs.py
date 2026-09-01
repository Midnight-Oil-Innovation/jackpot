"""M2-DROP-PRE slice 2 — issue the five verbs that replaced the last legacy reads.

``PRESET_GRANTS`` is a template, not a live view: the grants are rows, so a
capability added to a preset reaches nobody until a reseed runs. Slice 2 added

    instance_administrator  deletion:read_report, deletion:reverse_tombstone,
                            deletion:vacuum
    lab_lead                sample:read_unscrubbed, deletion:read_report,
                            submission:retract
    lab_member_rw           deletion:read_report
    lab_member_ro           deletion:read_report

and the five routes that previously read ``users.is_platform_admin`` /
``lab_membership.is_lab_director`` in-line now decide on those verbs. Without
this migration every existing principal keeps the old grant set and all five
routes become reachable by nobody — the exact failure ``pipeline:promote`` and
``pipeline:read`` hit in M2-B1 and M2-B3-PRE.

Purely additive: ``reseed()`` INSERTs with ``ON CONFLICT DO NOTHING`` against
``(principal_id, capability, scope_ref)``, so it issues the missing rows and
touches nothing else.

Revision ID: e5b3f27a91c4
Revises: c4d81a06f2b7
Create Date: 2026-09-01
"""

import logging
import os
from collections.abc import Sequence

from alembic import op

from backend.authz.reseed import ReseedPreflightError, preflight_counts, reseed

revision: str = "e5b3f27a91c4"
down_revision: str | None = "c4d81a06f2b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.runtime.migration")

_OVERRIDE_ENV = "JACKPOT_RESEED_ACCEPT_DATA_LOSS"

# Exactly what slice 2 introduced. Every one is new to the catalog in this
# batch, so no earlier migration can have issued them and the downgrade is
# identifiable — unlike a1c7d94e6b28's catch-up reseed.
_NEW_CAPABILITIES = (
    "deletion:read_report",
    "deletion:reverse_tombstone",
    "deletion:vacuum",
    "sample:read_unscrubbed",
    "submission:retract",
)


def upgrade() -> None:
    conn = op.get_bind()

    counts = preflight_counts(conn)
    logger.info("M2-DROP-PRE slice 2 preset reseed — pre-flight counts (0 expected):")
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
    """Revoke exactly the verbs this migration's preset changes introduced.

    No scope filter: unlike c4d81a06f2b7's instance-only verb, three of these
    are issued at lab scope as well, and the source filter is what keeps this
    from touching a grant an operator issued by hand.
    """
    from sqlalchemy import bindparam, text

    from backend.authz.reseed import GRANT_SOURCE

    op.get_bind().execute(
        text(
            "DELETE FROM authz_capability_grants WHERE source = :src AND capability IN :caps"
        ).bindparams(bindparam("caps", expanding=True)),
        {"src": GRANT_SOURCE, "caps": list(_NEW_CAPABILITIES)},
    )
