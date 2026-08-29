"""add_import_sessions_and_import_mappings_tables

I-1 spreadsheet importer wizard. Two new tables:

- ``import_sessions`` — short-lived, server-side wizard state. Holds
  the uploaded file bytes (bytea, capped at 10 MB), the wizard's
  step-by-step decisions (column mapping, value mapping, file-reference
  pattern), and cached preview/diff results. TTL: 24 hours; cleanup job
  removes expired rows hourly.

- ``import_mappings`` — long-lived, lab-scoped reusable mapping
  templates. Distinct from import_sessions because the mapping config
  has different lifecycle from the in-flight session.

Per Critical Rule 22, both tables include ``lab_id`` from the start
even though P0c multi-tenancy hasn't shipped — anticipates the cutover
and avoids a follow-up migration.

Revision ID: 9a1b2c3d4e5f
Revises:    34382b7b82c6
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "9a1b2c3d4e5f"
down_revision = "34382b7b82c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── import_sessions ──────────────────────────────────────────────
    op.execute(
        sa.text("""
        CREATE TABLE import_sessions (
            id                       BIGSERIAL PRIMARY KEY,
            created_by_user_id       INTEGER NOT NULL REFERENCES users(id),
            lab_id                   INTEGER NOT NULL REFERENCES labs(id),
            file_name                TEXT NOT NULL,
            file_format              VARCHAR(8) NOT NULL,
            file_bytes               BYTEA NOT NULL,
            file_size_bytes          INTEGER NOT NULL,
            selected_sheet           TEXT,
            column_mapping           JSONB,
            value_mapping            JSONB,
            file_reference_pattern   JSONB,
            preview_results          JSONB,
            diff_results             JSONB,
            current_step             INTEGER NOT NULL DEFAULT 1,
            status                   VARCHAR(16) NOT NULL DEFAULT 'in_progress',
            created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at               TIMESTAMPTZ NOT NULL
                                     DEFAULT NOW() + INTERVAL '24 hours',
            CONSTRAINT import_sessions_format_valid
                CHECK (file_format IN ('xlsx', 'csv', 'tsv')),
            CONSTRAINT import_sessions_status_valid
                CHECK (status IN ('in_progress', 'imported', 'abandoned')),
            CONSTRAINT import_sessions_size_capped
                CHECK (file_size_bytes BETWEEN 0 AND 10485760),
            CONSTRAINT import_sessions_step_in_range
                CHECK (current_step BETWEEN 1 AND 8)
        );
    """)
    )

    op.execute(
        sa.text("""
        CREATE INDEX import_sessions_user_status_expires_idx
            ON import_sessions (created_by_user_id, status, expires_at);
    """)
    )
    op.execute(
        sa.text("""
        CREATE INDEX import_sessions_in_progress_expires_idx
            ON import_sessions (expires_at)
            WHERE status = 'in_progress';
    """)
    )

    # updated_at trigger — same pattern as F-2's sample_files trigger.
    op.execute(
        sa.text("""
        CREATE OR REPLACE FUNCTION set_import_sessions_updated_at()
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
        CREATE TRIGGER import_sessions_updated_at_trigger
            BEFORE UPDATE ON import_sessions
            FOR EACH ROW
            EXECUTE FUNCTION set_import_sessions_updated_at();
    """)
    )

    # ── import_mappings ──────────────────────────────────────────────
    op.execute(
        sa.text("""
        CREATE TABLE import_mappings (
            id                       BIGSERIAL PRIMARY KEY,
            lab_id                   INTEGER NOT NULL REFERENCES labs(id),
            display_name             TEXT NOT NULL,
            description              TEXT,
            column_mapping           JSONB NOT NULL,
            file_reference_pattern   JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_by_user_id       INTEGER NOT NULL REFERENCES users(id),
            created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_used_at             TIMESTAMPTZ,
            is_active                BOOLEAN NOT NULL DEFAULT TRUE
        );
    """)
    )

    op.execute(
        sa.text("""
        CREATE INDEX import_mappings_lab_active_idx
            ON import_mappings (lab_id, is_active);
    """)
    )

    op.execute(
        sa.text("""
        CREATE OR REPLACE FUNCTION set_import_mappings_updated_at()
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
        CREATE TRIGGER import_mappings_updated_at_trigger
            BEFORE UPDATE ON import_mappings
            FOR EACH ROW
            EXECUTE FUNCTION set_import_mappings_updated_at();
    """)
    )

    op.execute(
        sa.text("""
        COMMENT ON TABLE import_sessions IS
            'I-1 wizard state. TTL 24h; cleanup job purges expired rows.';
    """)
    )
    op.execute(
        sa.text("""
        COMMENT ON TABLE import_mappings IS
            'I-1 reusable column-to-field mapping templates per lab.';
    """)
    )


def downgrade() -> None:
    op.execute(
        sa.text("DROP TRIGGER IF EXISTS import_mappings_updated_at_trigger ON import_mappings;")
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS set_import_mappings_updated_at();"))
    op.execute(sa.text("DROP INDEX IF EXISTS import_mappings_lab_active_idx;"))
    op.execute(sa.text("DROP TABLE IF EXISTS import_mappings;"))

    op.execute(
        sa.text("DROP TRIGGER IF EXISTS import_sessions_updated_at_trigger ON import_sessions;")
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS set_import_sessions_updated_at();"))
    op.execute(sa.text("DROP INDEX IF EXISTS import_sessions_in_progress_expires_idx;"))
    op.execute(sa.text("DROP INDEX IF EXISTS import_sessions_user_status_expires_idx;"))
    op.execute(sa.text("DROP TABLE IF EXISTS import_sessions;"))
