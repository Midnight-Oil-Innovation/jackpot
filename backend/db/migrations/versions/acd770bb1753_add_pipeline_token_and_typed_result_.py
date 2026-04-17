"""add_pipeline_token_and_typed_result_tables

Revision ID: acd770bb1753
Revises: e2dede78c435
Create Date: 2026-04-17 00:52:34.924705

Adds the pipeline_runs columns needed by the jackpot-nf registration
protocol (external run_id, per-run pipeline_token, workdir, and
parser_version_used) and creates the nine typed result tables that
parsers POST into via the /api/v1/pipelines/{run_id}/results/{result_type}
endpoint. Also adds a pipeline_results table with a metrics JSONB column
that the registration endpoint merges into in the same transaction.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "acd770bb1753"
down_revision: str | None = "e2dede78c435"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE pipeline_runs
            ADD COLUMN IF NOT EXISTS run_id TEXT,
            ADD COLUMN IF NOT EXISTS pipeline_token TEXT,
            ADD COLUMN IF NOT EXISTS work_dir TEXT,
            ADD COLUMN IF NOT EXISTS parser_version_used TEXT
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS pipeline_runs_run_id_key "
        "ON pipeline_runs (run_id) WHERE run_id IS NOT NULL"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_results (
            id                SERIAL PRIMARY KEY,
            run_id            TEXT NOT NULL,
            sample_id         TEXT NOT NULL,
            pipeline_name     TEXT,
            pipeline_version  TEXT,
            metrics           JSONB NOT NULL DEFAULT '{}'::JSONB,
            results_json      JSONB,
            created_at        TIMESTAMPTZ DEFAULT NOW(),
            updated_at        TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (run_id, sample_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pangolin_results (
            id                       SERIAL PRIMARY KEY,
            run_id                   TEXT NOT NULL,
            sample_id                TEXT NOT NULL,
            lineage                  TEXT NOT NULL,
            conflict                 DOUBLE PRECISION,
            ambiguity_score          DOUBLE PRECISION,
            scorpio_call             TEXT,
            scorpio_support          DOUBLE PRECISION,
            scorpio_conflict         DOUBLE PRECISION,
            scorpio_notes            TEXT,
            pangolin_version         TEXT NOT NULL,
            pangolin_data_version    TEXT,
            scorpio_version          TEXT,
            constellation_version    TEXT,
            qc_status                TEXT,
            qc_notes                 TEXT,
            note                     TEXT,
            created_at               TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (run_id, sample_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS nextclade_results (
            id                  SERIAL PRIMARY KEY,
            run_id              TEXT NOT NULL,
            sample_id           TEXT NOT NULL,
            clade               TEXT,
            nextclade_pango     TEXT,
            qc_overall_status   TEXT,
            qc_overall_score    DOUBLE PRECISION,
            total_substitutions INTEGER,
            total_deletions     INTEGER,
            total_insertions    INTEGER,
            total_missing       INTEGER,
            total_non_acgtns    INTEGER,
            total_frame_shifts  INTEGER,
            substitutions       JSONB,
            aa_substitutions    JSONB,
            nextclade_version   TEXT NOT NULL,
            dataset_name        TEXT,
            dataset_version     TEXT,
            created_at          TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (run_id, sample_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS typing_results (
            id               SERIAL PRIMARY KEY,
            run_id           TEXT NOT NULL,
            sample_id        TEXT NOT NULL,
            scheme           TEXT NOT NULL,
            scheme_version   TEXT,
            sequence_type    TEXT,
            clade            TEXT,
            allele_calls     JSONB,
            tool_name        TEXT NOT NULL,
            tool_version     TEXT,
            created_at       TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (run_id, sample_id, scheme)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tb_typing_results (
            id                        SERIAL PRIMARY KEY,
            run_id                    TEXT NOT NULL,
            sample_id                 TEXT NOT NULL,
            main_lineage              TEXT,
            sub_lineage               TEXT,
            spoligotype               TEXT,
            drug_resistance_profile   TEXT,
            who_drug_susceptibility   JSONB,
            tbprofiler_version        TEXT NOT NULL,
            tbprofiler_db_version     TEXT,
            created_at                TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (run_id, sample_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS assembly_qc (
            id                     SERIAL PRIMARY KEY,
            run_id                 TEXT NOT NULL,
            sample_id              TEXT NOT NULL,
            total_length           BIGINT,
            num_contigs            INTEGER,
            largest_contig         INTEGER,
            n50                    INTEGER,
            l50                    INTEGER,
            gc_percent             DOUBLE PRECISION,
            n_count                BIGINT,
            coverage_depth         DOUBLE PRECISION,
            genome_completeness    DOUBLE PRECISION,
            contamination_percent  DOUBLE PRECISION,
            assembly_method        TEXT,
            tool_name              TEXT NOT NULL,
            tool_version           TEXT,
            created_at             TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (run_id, sample_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS amr_results (
            id                     SERIAL PRIMARY KEY,
            run_id                 TEXT NOT NULL,
            sample_id              TEXT NOT NULL,
            gene_symbol            TEXT NOT NULL,
            gene_name              TEXT,
            drug_class             TEXT,
            drug                   TEXT,
            resistance_phenotype   TEXT,
            coverage_percent       DOUBLE PRECISION,
            identity_percent       DOUBLE PRECISION,
            reference_database     TEXT,
            reference_accession    TEXT,
            contig_id              TEXT,
            start_pos              INTEGER,
            end_pos                INTEGER,
            strand                 TEXT,
            tool_name              TEXT NOT NULL,
            tool_version           TEXT,
            created_at             TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (run_id, sample_id, gene_symbol, contig_id, start_pos)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mag_qc (
            id                      SERIAL PRIMARY KEY,
            run_id                  TEXT NOT NULL,
            sample_id               TEXT NOT NULL,
            bin_id                  TEXT NOT NULL,
            completeness_percent    DOUBLE PRECISION,
            contamination_percent   DOUBLE PRECISION,
            strain_heterogeneity    DOUBLE PRECISION,
            bin_size_bp             BIGINT,
            num_contigs             INTEGER,
            n50                     INTEGER,
            gc_percent              DOUBLE PRECISION,
            taxonomy                TEXT,
            tool_name               TEXT NOT NULL,
            tool_version            TEXT,
            created_at              TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (run_id, sample_id, bin_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS taxonomic_profile (
            id                   SERIAL PRIMARY KEY,
            run_id               TEXT NOT NULL,
            sample_id            TEXT NOT NULL,
            taxon_id             TEXT NOT NULL,
            taxon_name           TEXT,
            rank                 TEXT,
            lineage              TEXT,
            abundance_percent    DOUBLE PRECISION,
            read_count           BIGINT,
            reference_database   TEXT,
            tool_name            TEXT NOT NULL,
            tool_version         TEXT,
            created_at           TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (run_id, sample_id, taxon_id, tool_name)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS wastewater_lineage_abundance (
            id                         SERIAL PRIMARY KEY,
            run_id                     TEXT NOT NULL,
            sample_id                  TEXT NOT NULL,
            lineage                    TEXT NOT NULL,
            abundance                  DOUBLE PRECISION NOT NULL,
            confidence_interval_low    DOUBLE PRECISION,
            confidence_interval_high   DOUBLE PRECISION,
            coverage_depth             DOUBLE PRECISION,
            tool_name                  TEXT NOT NULL,
            tool_version               TEXT,
            barcode_version            TEXT,
            created_at                 TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (run_id, sample_id, lineage)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS wastewater_lineage_abundance")
    op.execute("DROP TABLE IF EXISTS taxonomic_profile")
    op.execute("DROP TABLE IF EXISTS mag_qc")
    op.execute("DROP TABLE IF EXISTS amr_results")
    op.execute("DROP TABLE IF EXISTS assembly_qc")
    op.execute("DROP TABLE IF EXISTS tb_typing_results")
    op.execute("DROP TABLE IF EXISTS typing_results")
    op.execute("DROP TABLE IF EXISTS nextclade_results")
    op.execute("DROP TABLE IF EXISTS pangolin_results")
    op.execute("DROP TABLE IF EXISTS pipeline_results")
    op.execute("DROP INDEX IF EXISTS pipeline_runs_run_id_key")
    op.execute(
        """
        ALTER TABLE pipeline_runs
            DROP COLUMN IF EXISTS parser_version_used,
            DROP COLUMN IF EXISTS work_dir,
            DROP COLUMN IF EXISTS pipeline_token,
            DROP COLUMN IF EXISTS run_id
        """
    )
