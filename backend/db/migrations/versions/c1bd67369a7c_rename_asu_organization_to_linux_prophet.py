"""rename asu organization to linux prophet

Revision ID: c1bd67369a7c
Revises: e5315db18d40
Create Date: 2026-04-24 22:53:33.792568

Glen's lab "Otero Outpost" lives under the Linux Prophet organisation,
not ASU. Rename the JACKPOT-internal organisation record + the
denormalised organisation text on the seeded sequencing lab + the
domain-whitelist row that gated sign-ups.

WHERE matches by old value rather than by id so the migration is
portable across forks/clones and idempotent (re-running on an
already-renamed DB is a no-op). display_name has a UNIQUE constraint
so the match is unambiguous.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c1bd67369a7c"
down_revision: str | None = "e5315db18d40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE organizations SET display_name = 'Linux Prophet' WHERE display_name = 'ASU'")
    op.execute(
        "UPDATE sequencing_labs SET organization = 'Linux Prophet' WHERE organization = 'ASU'"
    )
    op.execute(
        "UPDATE domain_whitelist "
        "SET domain = 'linuxprophet.org', description = 'Linux Prophet' "
        "WHERE domain = 'asu.edu'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE domain_whitelist "
        "SET domain = 'asu.edu', description = 'Arizona State University' "
        "WHERE domain = 'linuxprophet.org'"
    )
    op.execute(
        "UPDATE sequencing_labs SET organization = 'ASU' WHERE organization = 'Linux Prophet'"
    )
    op.execute("UPDATE organizations SET display_name = 'ASU' WHERE display_name = 'Linux Prophet'")
