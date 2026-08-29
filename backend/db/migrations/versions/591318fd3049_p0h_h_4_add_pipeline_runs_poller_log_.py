"""P0h H-4 — pipeline_runs.poller_log_offset

The H-4 sidecar log poller tails ``<work_dir>/runs/<run_id>/.nextflow.log``
on a 30-second cadence for active cluster runs and synthesises
weblog-equivalent state transitions when the compute nodes cannot
reach the API directly. The poller persists its byte position per run
so each tick processes only new lines.

Revision ID: 591318fd3049
Revises: f5f4727258b8
Create Date: 2026-05-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "591318fd3049"
down_revision: str | None = "f5f4727258b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
        ALTER TABLE pipeline_runs
            ADD COLUMN IF NOT EXISTS poller_log_offset BIGINT NOT NULL DEFAULT 0;
        """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE pipeline_runs DROP COLUMN IF EXISTS poller_log_offset;"))
