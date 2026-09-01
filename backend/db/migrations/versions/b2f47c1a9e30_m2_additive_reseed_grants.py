"""M2 (additive half) — issue capability grants from stored APGAP roles.

The first of the two migrations ADR 0016 splits the cutover into. This one
is **reversible and changes no behavior**: it creates the uniqueness arbiter
the reseed depends on, then issues the grants. Nothing reads them —
``permissions.py``'s ladder still decides every request and no route calls
``permit()`` — so the grants are inert, which is one authority, not two.

Why it is separate from the cutover (ADR 0016): the reseed is the only step
whose output nobody could inspect under the original single-migration plan,
because it reads the legacy roles in the same transaction that drops them. M2
has no rollback by design (access_model.md §10, greenfield, no shim), so the
ability to look at real grant rows before the irreversible step is worth an
extra migration. The cutover migration re-runs ``reseed()`` as an idempotent
catch-up for rows created through the old paths in between.

**Index before reseed is load-bearing.** ``reseed()``'s
``ON CONFLICT DO NOTHING`` needs ``(principal_id, capability, scope_ref)`` to
be unique or a second run silently duplicates every grant. M0's migration
(a7c3e91d54b0) does not create it; this one must, before calling reseed.
Pinned by ``test_reseed_duplicates_without_index``.

**The pre-flight guard can stop this migration.** ``reseed()`` refuses to run
when the source data holds rows whose effective access changes at cutover
(M2-PRE-4). That is deliberate: the operator reconciles the rows, or sets
JACKPOT_RESEED_ACCEPT_DATA_LOSS=1 to accept the change. See
docs/m2_preflight_report.md §4.

**Note on importing application code.** This migration calls
``backend.authz.reseed``, per that module's documented design. The coupling is
safe in one direction only: ``reseed()`` reads ``users.is_platform_admin``,
``users.is_data_analyst`` and the permission-group enum, which the cutover
migration drops afterwards, so this migration can only ever run against a
schema where they still exist. It is not safe to delete, repurpose, **or change the
shape of** ``reseed()`` while this migration is in the chain — M2-B2-PRE-C
proved the second case by adding a column to its INSERT, which broke this
migration on a fresh database until the ALTER above was added — ``tests/conftest.py`` runs
``alembic upgrade head`` against an empty container every session, so doing so
fails the whole suite rather than failing quietly (Critical Rule 44).

Revision ID: b2f47c1a9e30
Revises: f4a7d2c9b1e3
Create Date: 2026-08-31
"""

import os
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from backend.authz.reseed import GRANT_SOURCE, ReseedPreflightError, reseed

revision: str = "b2f47c1a9e30"
down_revision: str | None = "f4a7d2c9b1e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UNIQUE_INDEX = "authz_capability_grants_principal_capability_scope_uniq"

_OVERRIDE_ENV = "JACKPOT_RESEED_ACCEPT_DATA_LOSS"

_ABORT_HELP = (
    "\n\n"
    "The reseed found lab memberships whose effective access would change at\n"
    "cutover. Nothing has been written — this migration aborted before its\n"
    "first INSERT.\n\n"
    "Reconcile the rows (see docs/m2_preflight_report.md §4 for what each\n"
    f"count means), or accept the change deliberately by setting\n"
    f"{_OVERRIDE_ENV}=1 and re-running the migration.\n"
)


def upgrade() -> None:
    conn = op.get_bind()

    # Uniqueness arbiter first — reseed's ON CONFLICT DO NOTHING depends on it.
    conn.execute(
        text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {_UNIQUE_INDEX} "
            "ON authz_capability_grants (principal_id, capability, scope_ref)"
        )
    )

    # reseed() writes not_after (M2-B2-PRE-C). This migration calls shared
    # application code, so when that code gains a column the column must exist
    # by the time this point in the chain is reached — on a fresh database
    # nothing later has run yet. c93e1f5a7b02 adds the same column for
    # databases already migrated past this revision; both are IF NOT EXISTS,
    # so whichever runs first wins and the other is a no-op.
    #
    # Editing a merged migration is normally forbidden. It is done here because
    # the alternative is worse — making reseed()'s INSERT column-adaptive to
    # keep a historical caller working — and because this chain has never been
    # applied outside CI and local dev (instances/ holds only ci). The general
    # lesson is recorded in this file's header: a migration that calls
    # application code is coupled to that code's future, not just its present.
    conn.execute(
        text("ALTER TABLE authz_capability_grants ADD COLUMN IF NOT EXISTS not_after TIMESTAMPTZ")
    )

    force = os.getenv(_OVERRIDE_ENV, "").strip() == "1"
    try:
        reseed(conn, force=force)
    except ReseedPreflightError as exc:
        raise RuntimeError(str(exc) + _ABORT_HELP) from exc


def downgrade() -> None:
    conn = op.get_bind()
    # Only rows this migration issued; a hand-granted capability with a
    # different source survives a downgrade.
    conn.execute(
        text("DELETE FROM authz_capability_grants WHERE source = :s"),
        {"s": GRANT_SOURCE},
    )
    conn.execute(text(f"DROP INDEX IF EXISTS {_UNIQUE_INDEX}"))
