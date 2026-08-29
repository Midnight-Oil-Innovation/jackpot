"""B-CARE-3 — vacuum content-gone enforcement + external retraction stub

Sovereignty deletion implementation schema (design doc §5/§13):

1. ``samples.fastq_r1_uri`` becomes nullable — the vacuum step nulls the
   convenience URI columns, which was unsatisfiable against the baseline's
   NOT NULL (ADR-0013 "Enforcement belongs with the implementation").
2. CHECK ``samples_vacuumed_content_gone_chk`` — mechanical enforcement of
   the VACUUMED-means-content-gone invariant for the in-row content
   columns. Cross-table content (``sample_files``) is enforced in the
   service layer and pinned by the vacuum tests.
3. ``samples.vacuum_retry_at`` — set when a post-vacuum storage delete
   fails so the scheduled job retries it (§13 B-CARE-3c).
4. ``external_retraction_requests`` — B-CARE-3g stub table recording
   retraction intent (repository, accession, protocol); actual retraction
   protocols are deferred to v2.

Revision ID: d8f3b6c1a2e4
Revises: b3a1c4d7e9f2
Create Date: 2026-08-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8f3b6c1a2e4"
down_revision: str | None = "b3a1c4d7e9f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE samples ALTER COLUMN fastq_r1_uri DROP NOT NULL;"))
    op.execute(sa.text("ALTER TABLE samples ADD COLUMN IF NOT EXISTS vacuum_retry_at TIMESTAMPTZ;"))
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                     WHERE conname = 'samples_vacuumed_content_gone_chk'
                ) THEN
                    ALTER TABLE samples
                    ADD CONSTRAINT samples_vacuumed_content_gone_chk
                    CHECK (
                        deletion_status <> 'VACUUMED'
                        OR (
                            fastq_r1_uri IS NULL
                            AND fastq_r2_uri IS NULL
                            AND raw_fastq_uri IS NULL
                            AND consensus_fasta_uri IS NULL
                            AND assembly_uri IS NULL
                        )
                    );
                END IF;
            END $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS external_retraction_requests (
                id                   SERIAL PRIMARY KEY,
                sample_id            INTEGER NOT NULL REFERENCES samples(id),
                repository           TEXT NOT NULL,
                accession            TEXT,
                retraction_protocol  TEXT,
                requested_by_user_id INTEGER NOT NULL REFERENCES users(id),
                requested_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                status               TEXT NOT NULL DEFAULT 'RECORDED'
                    CHECK (status IN ('RECORDED', 'SENT', 'ACKNOWLEDGED', 'FAILED'))
            );
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS external_retraction_requests;"))
    op.execute(
        sa.text("ALTER TABLE samples DROP CONSTRAINT IF EXISTS samples_vacuumed_content_gone_chk;")
    )
    op.execute(sa.text("ALTER TABLE samples DROP COLUMN IF EXISTS vacuum_retry_at;"))
    # NOT NULL is not restored: rows vacuumed while the constraint was
    # absent may legitimately hold NULL and would block the downgrade.
