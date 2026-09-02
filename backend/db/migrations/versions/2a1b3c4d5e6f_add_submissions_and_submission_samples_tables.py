"""add_submissions_and_submission_samples_tables

I-2 submission package generation. Two new tables:

- ``submissions`` — first-class submission entity with full lifecycle
  state machine (DRAFT → READY_TO_SUBMIT → SUBMITTED → ACCEPTED /
  PARTIAL_SUCCESS / REJECTED → EMBARGOED → RELEASED, plus terminal
  WITHDRAWN). Lab-scoped per Critical Rule 22.

- ``submission_samples`` — join table with per-sample status and
  per-repository accession columns. ``UNIQUE (submission_id,
  sample_id_fk)`` so the same sample can't appear twice in the same
  submission.

Per Critical Rule 4 every state transition writes log_audit. Per
Critical Rule 24 router responses use the standard envelope.

Revision ID: 2a1b3c4d5e6f
Revises:    9a1b2c3d4e5f
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2a1b3c4d5e6f"
down_revision = "9a1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── submissions ─────────────────────────────────────────────────
    op.execute(
        sa.text("""
        CREATE TABLE submissions (
            id                       BIGSERIAL PRIMARY KEY,
            created_by_user_id       INTEGER NOT NULL REFERENCES users(id),
            lab_id                   INTEGER NOT NULL REFERENCES labs(id),
            target_repository        VARCHAR(32) NOT NULL,
            title                    TEXT NOT NULL,
            description              TEXT,
            status                   VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
            bioproject_accession     TEXT,
            release_date             DATE,
            package_path             TEXT,
            package_generated_at     TIMESTAMPTZ,
            submitted_at             TIMESTAMPTZ,
            accepted_at              TIMESTAMPTZ,
            rejection_reason         TEXT,
            withdrawal_reason        TEXT,
            created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            is_archived               BOOLEAN NOT NULL DEFAULT FALSE,
            CONSTRAINT submissions_target_repository_valid CHECK (
                target_repository IN (
                    'NCBI', 'GISAID_EPICOV', 'GISAID_EPIFLU',
                    'GISAID_EPIPOX', 'ENA', 'DDBJ'
                )
            ),
            CONSTRAINT submissions_status_valid CHECK (
                status IN (
                    'DRAFT', 'READY_TO_SUBMIT', 'SUBMITTED',
                    'PARTIAL_SUCCESS', 'ACCEPTED', 'REJECTED',
                    'EMBARGOED', 'RELEASED', 'WITHDRAWN', 'FAILED'
                )
            )
        );
    """)
    )

    op.execute(
        sa.text("""
        CREATE INDEX submissions_lab_status_idx
            ON submissions (lab_id, status)
            WHERE is_archived = FALSE;
    """)
    )
    op.execute(
        sa.text("""
        CREATE INDEX submissions_creator_idx
            ON submissions (created_by_user_id)
            WHERE is_archived = FALSE;
    """)
    )
    op.execute(
        sa.text("""
        CREATE INDEX submissions_embargoed_release_idx
            ON submissions (status, release_date)
            WHERE status = 'EMBARGOED' AND is_archived = FALSE;
    """)
    )

    op.execute(
        sa.text("""
        CREATE OR REPLACE FUNCTION set_submissions_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    )
    op.execute(
        sa.text("""
        CREATE TRIGGER submissions_updated_at_trigger
            BEFORE UPDATE ON submissions
            FOR EACH ROW
            EXECUTE FUNCTION set_submissions_updated_at();
    """)
    )

    # ── submission_samples ──────────────────────────────────────────
    op.execute(
        sa.text("""
        CREATE TABLE submission_samples (
            id                          BIGSERIAL PRIMARY KEY,
            submission_id               BIGINT NOT NULL
                                        REFERENCES submissions(id) ON DELETE CASCADE,
            sample_id_fk                INTEGER NOT NULL
                                        REFERENCES samples(id),
            per_sample_status           VARCHAR(16) NOT NULL DEFAULT 'PENDING',
            biosample_accession         TEXT,
            sra_accession               TEXT,
            genbank_accession           TEXT,
            gisaid_accession            TEXT,
            ena_accession               TEXT,
            ddbj_accession              TEXT,
            per_sample_rejection_reason TEXT,
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT submission_samples_status_valid CHECK (
                per_sample_status IN ('PENDING', 'ACCEPTED', 'REJECTED')
            ),
            CONSTRAINT submission_samples_unique
                UNIQUE (submission_id, sample_id_fk)
        );
    """)
    )

    op.execute(
        sa.text("""
        CREATE INDEX submission_samples_status_idx
            ON submission_samples (submission_id, per_sample_status);
    """)
    )
    op.execute(
        sa.text("""
        CREATE INDEX submission_samples_sample_idx
            ON submission_samples (sample_id_fk);
    """)
    )

    op.execute(
        sa.text("""
        CREATE OR REPLACE FUNCTION set_submission_samples_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    )
    op.execute(
        sa.text("""
        CREATE TRIGGER submission_samples_updated_at_trigger
            BEFORE UPDATE ON submission_samples
            FOR EACH ROW
            EXECUTE FUNCTION set_submission_samples_updated_at();
    """)
    )

    op.execute(
        sa.text("""
        COMMENT ON TABLE submissions IS
            'I-2 submission lifecycle. Critical Rules 4, 22, 24.';
    """)
    )
    op.execute(
        sa.text("""
        COMMENT ON TABLE submission_samples IS
            'I-2 per-sample submission status with repository accession columns.';
    """)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS submission_samples_updated_at_trigger ON submission_samples;"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS set_submission_samples_updated_at();"))
    op.execute(sa.text("DROP INDEX IF EXISTS submission_samples_sample_idx;"))
    op.execute(sa.text("DROP INDEX IF EXISTS submission_samples_status_idx;"))
    op.execute(sa.text("DROP TABLE IF EXISTS submission_samples;"))

    op.execute(sa.text("DROP TRIGGER IF EXISTS submissions_updated_at_trigger ON submissions;"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS set_submissions_updated_at();"))
    op.execute(sa.text("DROP INDEX IF EXISTS submissions_embargoed_release_idx;"))
    op.execute(sa.text("DROP INDEX IF EXISTS submissions_creator_idx;"))
    op.execute(sa.text("DROP INDEX IF EXISTS submissions_lab_status_idx;"))
    op.execute(sa.text("DROP TABLE IF EXISTS submissions;"))
