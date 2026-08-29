"""add_file_references

Phase P0f schema additions for in-place file registration with
content-hash deduplication. Extends the existing sample_files table
with content_hash (SHA-256), cheap fingerprint pieces, storage_state
ENUM, alternate_uris, verification metadata, retention_policy,
original_uri (for MIRRORED), staged_for_run_id (for STAGED), and an
updated_at trigger.

The existing sample_files table already carries sample_id_fk, uri,
md5, file_size_bytes, scrub_status, paired_file_id, etc. — P0f
extends it rather than introducing a parallel file_references table.
See spec.md Phase P0f and Critical Rules 57 and 58.

Revision ID: 34382b7b82c6
Revises:    00b4bd99ddee
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "34382b7b82c6"
down_revision = "00b4bd99ddee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. ENUM type for storage state.
    op.execute(
        sa.text("""
        CREATE TYPE file_storage_state AS ENUM (
            'EXTERNAL',
            'MANAGED',
            'MIRRORED',
            'STAGED',
            'BROKEN'
        );
    """)
    )

    # 2. Extend the existing sample_files table with P0f columns.
    op.execute(
        sa.text("""
        ALTER TABLE sample_files
            ADD COLUMN content_hash             VARCHAR(64),
            ADD COLUMN head64k_hash             VARCHAR(64),
            ADD COLUMN tail64k_hash             VARCHAR(64),
            ADD COLUMN storage_state            file_storage_state
                                                NOT NULL
                                                DEFAULT 'EXTERNAL',
            ADD COLUMN alternate_uris           TEXT[]
                                                NOT NULL
                                                DEFAULT ARRAY[]::TEXT[],
            ADD COLUMN first_seen_at            TIMESTAMPTZ
                                                NOT NULL
                                                DEFAULT NOW(),
            ADD COLUMN last_verified_at         TIMESTAMPTZ,
            ADD COLUMN last_verification_status VARCHAR(32),
            ADD COLUMN retention_policy         VARCHAR(32)
                                                NOT NULL
                                                DEFAULT 'STANDARD',
            ADD COLUMN original_uri             TEXT,
            ADD COLUMN staged_for_run_id        UUID,
            ADD COLUMN updated_at               TIMESTAMPTZ
                                                NOT NULL
                                                DEFAULT NOW();
    """)
    )

    # 3. Backfill cheap-fingerprint columns from existing md5.
    op.execute(
        sa.text("""
        UPDATE sample_files
           SET head64k_hash = md5,
               tail64k_hash = md5
         WHERE md5 IS NOT NULL
           AND head64k_hash IS NULL;
    """)
    )

    # 4. Constraints.
    op.execute(
        sa.text("""
        ALTER TABLE sample_files
            ADD CONSTRAINT sample_files_managed_size_not_null
                CHECK (
                    storage_state NOT IN ('MANAGED', 'STAGED')
                    OR file_size_bytes IS NOT NULL
                ),
            ADD CONSTRAINT sample_files_mirrored_has_origin
                CHECK (
                    storage_state <> 'MIRRORED'
                    OR original_uri IS NOT NULL
                ),
            ADD CONSTRAINT sample_files_staged_has_run
                CHECK (
                    storage_state <> 'STAGED'
                    OR staged_for_run_id IS NOT NULL
                ),
            ADD CONSTRAINT sample_files_retention_valid
                CHECK (retention_policy IN
                    ('STANDARD', 'LONG_TERM', 'EPHEMERAL'));
    """)
    )

    # 5. Indexes for the dedup hot paths.
    op.execute(
        sa.text("""
        CREATE UNIQUE INDEX sample_files_content_hash_uniq
            ON sample_files (content_hash)
            WHERE content_hash IS NOT NULL;
    """)
    )
    op.execute(
        sa.text("""
        CREATE INDEX sample_files_fingerprint_idx
            ON sample_files (file_size_bytes, head64k_hash, tail64k_hash)
            WHERE content_hash IS NULL
              AND file_size_bytes IS NOT NULL;
    """)
    )
    op.execute(
        sa.text("""
        CREATE INDEX sample_files_verification_idx
            ON sample_files (storage_state, last_verified_at)
            WHERE storage_state IN ('EXTERNAL', 'MIRRORED');
    """)
    )

    # 6. updated_at trigger.
    op.execute(
        sa.text("""
        CREATE OR REPLACE FUNCTION set_sample_files_updated_at()
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
        CREATE TRIGGER sample_files_updated_at_trigger
            BEFORE UPDATE ON sample_files
            FOR EACH ROW
            EXECUTE FUNCTION set_sample_files_updated_at();
    """)
    )

    # 7. Documentation comment.
    op.execute(
        sa.text("""
        COMMENT ON TABLE sample_files IS
            'Sample-to-file association with file metadata. Phase P0f '
            'extended this table with content_hash, cheap fingerprint, '
            'storage_state, alternate_uris, and verification metadata. '
            'See Critical Rules 57 and 58.';
    """)
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS sample_files_updated_at_trigger ON sample_files;"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS set_sample_files_updated_at();"))
    op.execute(sa.text("DROP INDEX IF EXISTS sample_files_verification_idx;"))
    op.execute(sa.text("DROP INDEX IF EXISTS sample_files_fingerprint_idx;"))
    op.execute(sa.text("DROP INDEX IF EXISTS sample_files_content_hash_uniq;"))
    op.execute(
        sa.text("""
        ALTER TABLE sample_files
            DROP CONSTRAINT IF EXISTS sample_files_retention_valid,
            DROP CONSTRAINT IF EXISTS sample_files_staged_has_run,
            DROP CONSTRAINT IF EXISTS sample_files_mirrored_has_origin,
            DROP CONSTRAINT IF EXISTS sample_files_managed_size_not_null;
    """)
    )
    op.execute(
        sa.text("""
        ALTER TABLE sample_files
            DROP COLUMN IF EXISTS updated_at,
            DROP COLUMN IF EXISTS staged_for_run_id,
            DROP COLUMN IF EXISTS original_uri,
            DROP COLUMN IF EXISTS retention_policy,
            DROP COLUMN IF EXISTS last_verification_status,
            DROP COLUMN IF EXISTS last_verified_at,
            DROP COLUMN IF EXISTS first_seen_at,
            DROP COLUMN IF EXISTS alternate_uris,
            DROP COLUMN IF EXISTS storage_state,
            DROP COLUMN IF EXISTS tail64k_hash,
            DROP COLUMN IF EXISTS head64k_hash,
            DROP COLUMN IF EXISTS content_hash;
    """)
    )
    op.execute(sa.text("DROP TYPE IF EXISTS file_storage_state;"))
