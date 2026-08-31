"""M2-B2-PRE-C — capability grants can carry an expiry.

Approved sample-access requests are time-bounded (§5: "a structural grant at
Sample scope, source=direct, time-bounded"). The legacy ladder enforced that
at decision time — ``access_expires_at IS NULL OR access_expires_at > NOW()``
in permissions.py — not only through the nightly expiry job, so the new model
must too or access outlives its expiry until the job next runs.

Stored as a column rather than a key inside ``conditions``: conditions mean
"must equal the request context", and an expiry is a comparison, not an
equality. Overloading the JSONB would make one field mean two things and
would need a reserved-key rule that nothing enforces.

Revision ID: c93e1f5a7b02
Revises: b2f47c1a9e30
Create Date: 2026-08-31
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "c93e1f5a7b02"
down_revision: str | None = "b2f47c1a9e30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.get_bind().execute(
        text("ALTER TABLE authz_capability_grants ADD COLUMN IF NOT EXISTS not_after TIMESTAMPTZ")
    )


def downgrade() -> None:
    op.get_bind().execute(
        text("ALTER TABLE authz_capability_grants DROP COLUMN IF EXISTS not_after")
    )
