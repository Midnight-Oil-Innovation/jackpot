"""add_pipeline_catalog_and_parser_version

Revision ID: b1a4c9d2e8f0
Revises: acd770bb1753
Create Date: 2026-04-17 12:00:00.000000

Session M-3: introduces the ``pipeline_catalog`` table and the
``parser_version`` column called out in spec.md line 379.

The catalog is the backing table for the zoo/lab/project three-tier
pipeline hierarchy (Session N adds the launch endpoint that reads
from it).  This migration creates the *minimal* shape required so
the Session M parser-version workflow has something to point at:

* ``(pipeline_name, pipeline_version)`` uniquely identifies a row.
* ``parser_version`` is semver, bumped when the matching parser in
  ``jackpot-nf/pipelines/<name>/parsers`` changes shape — callers
  compare against ``pipeline_runs.parser_version_used`` to detect
  drift at replay time.
* ``tier`` is one of 'zoo' / 'lab' / 'project' — Session N enforces
  hierarchy semantics; here we just need the column so seed rows
  can be written.

Future Session N/O migrations will ALTER TABLE to add launch-related
fields (pipeline_uri, pipeline_revision, compute_config, etc.) —
adding a column is cheap, so we deliberately keep the catalog thin
here rather than speculating on shape.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b1a4c9d2e8f0"
down_revision: str | None = "acd770bb1753"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_catalog (
            id                SERIAL PRIMARY KEY,
            pipeline_name     TEXT NOT NULL,
            pipeline_version  TEXT NOT NULL,
            parser_version    TEXT NOT NULL,
            tier              TEXT NOT NULL DEFAULT 'zoo',
            is_active         BOOLEAN NOT NULL DEFAULT TRUE,
            created_at        TIMESTAMPTZ DEFAULT NOW(),
            updated_at        TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (pipeline_name, pipeline_version)
        )
        """
    )
    op.execute(
        """
        ALTER TABLE pipeline_catalog
            ADD COLUMN IF NOT EXISTS parser_version TEXT NOT NULL DEFAULT '0.0.0'
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS pipeline_catalog_tier_active_idx "
        "ON pipeline_catalog (tier, is_active)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS pipeline_catalog_tier_active_idx")
    op.execute("DROP TABLE IF EXISTS pipeline_catalog")
