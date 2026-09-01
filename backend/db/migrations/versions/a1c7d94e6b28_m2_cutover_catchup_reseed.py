"""M2 cutover (part a) — catch-up reseed.

The second of the two migrations ADR 0016 splits the cutover into, and the
last one that is still safe to run: it issues grants, it drops nothing.

**What it is for.** ``b2f47c1a9e30`` reseeded every stored APGAP role into
capability grants. Rows created through the legacy paths *after* that
migration hold roles with no grants behind them — ``PATCH /users/{id}`` still
writes ``is_platform_admin``, ``auth/dev-login`` still creates users with both
flags, and any membership added by a path that predates M2-B5's
``sync_membership_grants`` never issued anything. Since M2-B1 the guards
decide on grants alone, so such a user is authorized for nothing until a
reseed runs. This is that reseed.

**Idempotent by construction.** ``reseed()`` is ``ON CONFLICT DO NOTHING``
against ``(principal_id, capability, scope_ref)``, the arbiter
``b2f47c1a9e30`` creates. Re-running it issues only what is missing, which is
what makes a catch-up meaningful rather than a duplicate.

**Counts are surfaced, not just enforced.** ``reseed()`` refuses to run when
the source data holds rows whose effective access changes at cutover
(M2-PRE-4) — but only *raises* on non-zero, and logs nothing when clean. The
M2 backlog entry asks for the counts themselves, so this migration calls
``preflight_counts()`` first and logs every kind including the zeros. An
operator reading ``alembic upgrade head`` output should see the numbers the
cutover decision rests on, not infer them from the absence of an abort. The
authoritative refusal still lives in ``reseed()``; this is a read-only echo of
the same query, deliberately not a second implementation of the rule.

**What this migration does NOT do.** It does not drop
``users.is_platform_admin``, ``users.is_data_analyst``, the
``PermissionGroups`` enum, or the legacy ladder. The M2 entry originally
paired the drop with this reseed on the premise that nothing read those
columns any more. Eleven production modules still do — the tenant wall in
``tenancy.py``, the deletion-lifecycle checks in ``samples.py`` and
``deletion.py`` that M3 owns, the platform-admin notification lookup in
``federation/deletion_propagation.py``, and the identity plumbing in
``guards.py`` / ``auth.py`` / ``users.py`` / ``imports.py``. Dropping the
columns under them would 500 every one of those paths. The drop is backlog
item ``M2-DROP``, blocked on M3. See docs/m2_preflight_report.md §4.

**Note on importing application code.** Same coupling as ``b2f47c1a9e30``,
same direction, same reason: ``reseed()`` reads the legacy role columns, so
this migration can only ever run against a schema where they still exist —
which, since the drop is deferred, is now every schema. It is not safe to
delete, repurpose, or change the shape of ``reseed()`` while either migration
is in the chain.

Revision ID: a1c7d94e6b28
Revises: c93e1f5a7b02
Create Date: 2026-08-31
"""

import logging
import os
from collections.abc import Sequence

from alembic import op

from backend.authz.reseed import ReseedPreflightError, preflight_counts, reseed

revision: str = "a1c7d94e6b28"
down_revision: str | None = "c93e1f5a7b02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.runtime.migration")

_OVERRIDE_ENV = "JACKPOT_RESEED_ACCEPT_DATA_LOSS"

_ABORT_HELP = (
    "\n\n"
    "The catch-up reseed found lab memberships whose effective access would\n"
    "change at cutover. Nothing has been written — this migration aborted\n"
    "before its first INSERT.\n\n"
    "Reconcile the rows (see docs/m2_preflight_report.md §4 for what each\n"
    f"count means), or accept the change deliberately by setting\n"
    f"{_OVERRIDE_ENV}=1 and re-running the migration.\n"
)


def upgrade() -> None:
    conn = op.get_bind()

    # Read-only, and before anything else: these numbers describe the source
    # data rather than the result of a partial reseed. Logged in full — a zero
    # is a finding too, because it is the evidence that the kind was checked.
    counts = preflight_counts(conn)
    logger.info("M2 catch-up reseed — pre-flight counts (0 is the expected value):")
    for kind, n in sorted(counts.items()):
        logger.info("    %-32s %d", kind, n)

    force = os.getenv(_OVERRIDE_ENV, "").strip() == "1"
    if force and any(counts.values()):
        logger.warning(
            "M2 catch-up reseed — %s=1: proceeding over the findings above. "
            "The affected users' effective access changes at this migration.",
            _OVERRIDE_ENV,
        )

    try:
        reseed(conn, force=force)
    except ReseedPreflightError as exc:
        raise RuntimeError(str(exc) + _ABORT_HELP) from exc


def downgrade() -> None:
    """Deliberately a no-op.

    This migration issues grants that are indistinguishable from the ones
    ``b2f47c1a9e30`` issued — same ``source``, same
    ``(principal_id, capability, scope_ref)`` — because they are the same
    grants, caught up late. There is no predicate that selects "the rows this
    migration inserted" without also selecting rows the additive migration
    inserted, and deleting those would silently de-authorize users this
    migration never touched.

    Downgrading past the additive migration removes every reseeded grant,
    which is the honest place for that to happen. A no-op here is not a gap;
    it is the absence of a lie.
    """
