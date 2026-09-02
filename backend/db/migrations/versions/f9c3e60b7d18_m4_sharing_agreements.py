"""M4-A — sharing_agreements, the home per-peer differential access never had.

access_model.md §7.3 and §7.6-3. Today "what a peer may do" is a mix of L1
read visibility, org-wide qualification gates, and per-sample access grants;
none of it can express "Peer X may read Salmonella in Lab 3; Peer Y may see
only PUBLIC". An agreement is that statement, and §2.2 already reserved the
grant source it produces (``source='agreement'``).

**Dark on arrival.** These tables are written by nobody and read by nobody at
this revision. ``sync_agreement_grants`` translates an agreement into
``authz_capability_grants`` rows, but no route calls it and no peer principal
is loaded on any request path yet — M4-B wires L1 visibility. This is the same
staging M0 used for the engine and M2's additive migration used for the
reseed: schema and translation first, reversibly, so the irreversible or
behavior-changing step lands alone and small.

**Two tables, not one with a JSONB grants blob.** The grants are the thing the
engine reads, and they have the same shape as every other grant in the system
(capability, scope_ref, conditions, not_after). Keeping them relational means
the agreement's grants can be inspected, indexed, and diffed with the same
queries as any other grant — and means ``sync_agreement_grants`` is a plain
projection rather than a JSON parse whose schema drifts silently.

**Why the agreement is not itself the grant table.** The same reason
``lab_membership`` is not: an operator-facing record has a lifecycle
(negotiated, rationale, activated, revoked) that the decision path should not
have to read or understand. ``authz_capability_grants`` stays the one place
``permit()`` looks, and the sync keeps it in step — exactly as
``sync_membership_grants`` (M2-B5) and ``sync_sample_access_grants``
(M2-SAMPLE-ACCESS-SYNC) already do for their own source tables.

Revision ID: f9c3e60b7d18
Revises: a1c7d94e6b28
Create Date: 2026-09-01
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "f9c3e60b7d18"
down_revision: str | None = "a1c7d94e6b28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DIRECTIONS = ("INBOUND", "OUTBOUND")


def upgrade() -> None:
    conn = op.get_bind()
    directions_sql = ", ".join(f"'{d}'" for d in _DIRECTIONS)

    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS sharing_agreements (
                id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                peer_instance_id  UUID NOT NULL
                                  REFERENCES federated_instances(id) ON DELETE CASCADE,
                direction         TEXT NOT NULL CHECK (direction IN ({directions_sql})),
                rationale         TEXT NOT NULL,
                active            BOOLEAN NOT NULL DEFAULT TRUE,
                created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """  # noqa: S608 — directions_sql is built from a module constant
        )
    )

    # A grant row is deliberately shaped like authz_capability_grants: the sync
    # is then a projection, and a reviewer comparing the two sees one shape.
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS sharing_agreement_grants (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                agreement_id  UUID NOT NULL
                              REFERENCES sharing_agreements(id) ON DELETE CASCADE,
                capability    TEXT NOT NULL,
                scope_ref     TEXT NOT NULL,
                conditions    JSONB NOT NULL DEFAULT '{}'::jsonb,
                not_after     TIMESTAMPTZ,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )

    # One agreement's grants are always fetched together (the sync reconciles
    # per agreement), and the peer lookup drives "what does this peer hold".
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS sharing_agreements_peer_idx "
            "ON sharing_agreements (peer_instance_id) WHERE active"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS sharing_agreement_grants_agreement_idx "
            "ON sharing_agreement_grants (agreement_id)"
        )
    )
    # The same capability at the same scope twice in one agreement is a
    # data-entry error, not two grants: authz_capability_grants would dedupe it
    # on its own uniqueness arbiter and the counts would disagree.
    conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS sharing_agreement_grants_uniq "
            "ON sharing_agreement_grants (agreement_id, capability, scope_ref)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    # Grants this feature issued into the shared table go first — they are
    # identified by source, and leaving them behind would authorize peers from
    # a feature that no longer exists.
    conn.execute(text("DELETE FROM authz_capability_grants WHERE source = 'agreement'"))
    conn.execute(text("DROP TABLE IF EXISTS sharing_agreement_grants"))
    conn.execute(text("DROP TABLE IF EXISTS sharing_agreements"))
