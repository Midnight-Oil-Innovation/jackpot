"""schema_v4_2_case_sector_surveillance_quality

Revision ID: 1de94c16e612
Revises: a7fd1fcccb77
Create Date: 2026-04-08 18:42:18.756406

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1de94c16e612"
down_revision: str | None = "a7fd1fcccb77"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE samples
            ADD COLUMN IF NOT EXISTS case_id                            TEXT,
            ADD COLUMN IF NOT EXISTS case_source_system                 TEXT,
            ADD COLUMN IF NOT EXISTS case_type                          TEXT,
            ADD COLUMN IF NOT EXISTS sector                             TEXT NOT NULL DEFAULT 'clinical',
            ADD COLUMN IF NOT EXISTS surveillance_relevant              BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS surveillance_relevant_override
                BOOLEAN,
            ADD COLUMN IF NOT EXISTS surveillance_override_pending
                BOOLEAN,
            ADD COLUMN IF NOT EXISTS surveillance_override_category     TEXT,
            ADD COLUMN IF NOT EXISTS surveillance_override_reason       TEXT,
            ADD COLUMN IF NOT EXISTS surveillance_override_approved_by_id
                INTEGER,
            ADD COLUMN IF NOT EXISTS surveillance_override_date         DATE,
            ADD COLUMN IF NOT EXISTS target_organisms                   TEXT[],
            ADD COLUMN IF NOT EXISTS quality_status                     TEXT NOT NULL DEFAULT 'PRELIMINARY',
            ADD COLUMN IF NOT EXISTS date_collected_precision           TEXT NOT NULL DEFAULT 'day',
            ADD COLUMN IF NOT EXISTS read_type                          TEXT,
            ADD COLUMN IF NOT EXISTS assembly_type                      TEXT,
            ADD COLUMN IF NOT EXISTS mag_completeness_pct               DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS mag_contamination_pct              DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS mag_strain_heterogeneity_pct       DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS mag_bin_count                      INTEGER,
            ADD COLUMN IF NOT EXISTS originating_lab                    TEXT,
            ADD COLUMN IF NOT EXISTS submitting_lab                     TEXT,
            ADD COLUMN IF NOT EXISTS data_generator                     TEXT,
            ADD COLUMN IF NOT EXISTS ena_accession                      TEXT,
            ADD COLUMN IF NOT EXISTS data_use_terms                     TEXT,
            ADD COLUMN IF NOT EXISTS embargo_release_date               DATE,
            ADD COLUMN IF NOT EXISTS citation_request                   TEXT,
            ADD COLUMN IF NOT EXISTS date_received_lab                  DATE,
            ADD COLUMN IF NOT EXISTS date_sequence_uploaded             DATE,
            ADD COLUMN IF NOT EXISTS date_lineage_assigned              DATE,
            ADD COLUMN IF NOT EXISTS date_phenotype_reported            DATE;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE samples
            DROP COLUMN IF EXISTS case_id,
            DROP COLUMN IF EXISTS case_source_system,
            DROP COLUMN IF EXISTS case_type,
            DROP COLUMN IF EXISTS sector,
            DROP COLUMN IF EXISTS surveillance_relevant,
            DROP COLUMN IF EXISTS surveillance_relevant_override,
            DROP COLUMN IF EXISTS surveillance_override_pending,
            DROP COLUMN IF EXISTS surveillance_override_category,
            DROP COLUMN IF EXISTS surveillance_override_reason,
            DROP COLUMN IF EXISTS surveillance_override_approved_by_id,
            DROP COLUMN IF EXISTS surveillance_override_date,
            DROP COLUMN IF EXISTS target_organisms,
            DROP COLUMN IF EXISTS quality_status,
            DROP COLUMN IF EXISTS date_collected_precision,
            DROP COLUMN IF EXISTS read_type,
            DROP COLUMN IF EXISTS assembly_type,
            DROP COLUMN IF EXISTS mag_completeness_pct,
            DROP COLUMN IF EXISTS mag_contamination_pct,
            DROP COLUMN IF EXISTS mag_strain_heterogeneity_pct,
            DROP COLUMN IF EXISTS mag_bin_count,
            DROP COLUMN IF EXISTS originating_lab,
            DROP COLUMN IF EXISTS submitting_lab,
            DROP COLUMN IF EXISTS data_generator,
            DROP COLUMN IF EXISTS ena_accession,
            DROP COLUMN IF EXISTS data_use_terms,
            DROP COLUMN IF EXISTS embargo_release_date,
            DROP COLUMN IF EXISTS citation_request,
            DROP COLUMN IF EXISTS date_received_lab,
            DROP COLUMN IF EXISTS date_sequence_uploaded,
            DROP COLUMN IF EXISTS date_lineage_assigned,
            DROP COLUMN IF EXISTS date_phenotype_reported;
    """)
