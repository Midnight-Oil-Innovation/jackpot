"""rename  example org and lab

Revision ID: 00b4bd99ddee
Revises: 8e963caa3d13
Create Date: 2026-04-28 13:51:26.516224

Phase 7 — final renaming step in the institutional-cleanup chain. The
prior c1bd67369a7c renamed ASU → Linux Prophet; e5315db18d40 renamed
Otero Lab → Otero Outpost. Per Critical Rule 55 (production code is
operator-agnostic), the seeded operator identity now lands on neutral
'Example Org' / 'Example Lab' / 'admin@example.org' values. The
operator-bootstrap layer (jackpot init, P0e) will rename these to
real operator values at install time.

WHERE matches by old value rather than by id so the migration is
portable across forks/clones and idempotent (re-running on an
already-renamed DB is a no-op).

P0e A.3 (Critical Rule 55): HISTORICAL — no-op on fresh installs.
The baseline migration `5adf11b77c19` was edited in P0e to seed the
`Example Org` / `Example Lab` / `admin@example.org` /
`Example Sequencing Lab` / `Example Reference Lab` end-state values
directly, so this rename now matches zero rows on a fresh install.
This file remains in the chain for any deployed environment that
was at the pre-P0e revision before the baseline edit landed.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "00b4bd99ddee"
down_revision: str | None = "8e963caa3d13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # organizations table: 'Linux Prophet' → 'Example Org'
    op.execute(
        "UPDATE organizations SET display_name = 'Example Org' WHERE display_name = 'Linux Prophet'"
    )

    # sequencing_labs.organization (denormalised text):
    op.execute(
        "UPDATE sequencing_labs SET organization = 'Example Org' "
        "WHERE organization = 'Linux Prophet'"
    )
    op.execute(
        "UPDATE sequencing_labs SET organization = 'Example Sequencing Lab' "
        "WHERE organization = 'Sonora Quest'"
    )
    op.execute(
        "UPDATE sequencing_labs SET organization = 'Example Reference Lab' "
        "WHERE organization = 'LabCorp'"
    )

    # sequencing_labs.name:
    op.execute("UPDATE sequencing_labs SET name = 'Example Lab' WHERE name = 'Otero Outpost'")
    op.execute(
        "UPDATE sequencing_labs SET name = 'Example Sequencing Lab' "
        "WHERE name = 'Sonora Quest Laboratories'"
    )
    op.execute(
        "UPDATE sequencing_labs SET name = 'Example Reference Lab' "
        "WHERE name = 'Laboratory Corporation of America'"
    )

    # labs.display_name: 'Otero Outpost' → 'Example Lab'
    op.execute("UPDATE labs SET display_name = 'Example Lab' WHERE display_name = 'Otero Outpost'")

    # domain_whitelist: 'linuxprophet.org' → 'example.org'
    op.execute(
        "UPDATE domain_whitelist "
        "SET domain = 'example.org', description = 'Example Org' "
        "WHERE domain = 'linuxprophet.org'"
    )

    # users: rename the seeded admin email
    op.execute(
        "UPDATE users SET email = 'admin@example.org' WHERE email = 'gotero@linuxprophet.com'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE users SET email = 'gotero@linuxprophet.com' WHERE email = 'admin@example.org'"
    )
    op.execute(
        "UPDATE domain_whitelist "
        "SET domain = 'linuxprophet.org', description = 'Linux Prophet' "
        "WHERE domain = 'example.org'"
    )
    op.execute("UPDATE labs SET display_name = 'Otero Outpost' WHERE display_name = 'Example Lab'")
    op.execute(
        "UPDATE sequencing_labs SET name = 'Laboratory Corporation of America' "
        "WHERE name = 'Example Reference Lab'"
    )
    op.execute(
        "UPDATE sequencing_labs SET name = 'Sonora Quest Laboratories' "
        "WHERE name = 'Example Sequencing Lab'"
    )
    op.execute("UPDATE sequencing_labs SET name = 'Otero Outpost' WHERE name = 'Example Lab'")
    op.execute(
        "UPDATE sequencing_labs SET organization = 'LabCorp' "
        "WHERE organization = 'Example Reference Lab'"
    )
    op.execute(
        "UPDATE sequencing_labs SET organization = 'Sonora Quest' "
        "WHERE organization = 'Example Sequencing Lab'"
    )
    op.execute(
        "UPDATE sequencing_labs SET organization = 'Example Org' "
        "WHERE organization = 'Linux Prophet'"
    )
    op.execute(
        "UPDATE organizations SET display_name = 'Linux Prophet' WHERE display_name = 'Example Org'"
    )
