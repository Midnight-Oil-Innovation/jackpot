"""session_n_add_pipeline_events_tasks_files_restarts_catalog

Revision ID: cea9c08543ee
Revises: b1a4c9d2e8f0
Create Date: 2026-04-17 10:11:26.820032

Session N: pipelines router launch/monitor/resume + BYOP + promotion.

Creates the operational tables that back the launch → weblog → results
flow end to end:

* pipeline_events — raw Nextflow -weblog payloads (audit trail)
* pipeline_tasks  — one row per Nextflow task_id, updated on trace events
* pipeline_files  — output file registry populated by the results loader
* pipeline_restarts — links a resumed run_id back to its FAILED ancestor
* project_pipelines — BYOP skeleton (UNVERIFIED until Month 3)
* lab_pipelines — project→lab promotion records

Also adds columns to pipeline_runs that the launch endpoint needs
(result_uri is already there; add parameters JSONB + soft_warnings JSONB
so /resume can replay the same config) and adds a compatibility_rules
JSONB column to pipeline_catalog so launch's compat check is data-driven.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "cea9c08543ee"
down_revision: str | None = "b1a4c9d2e8f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE pipeline_runs
            ADD COLUMN IF NOT EXISTS parameters JSONB NOT NULL DEFAULT '{}'::JSONB,
            ADD COLUMN IF NOT EXISTS soft_warnings JSONB NOT NULL DEFAULT '[]'::JSONB,
            ADD COLUMN IF NOT EXISTS pipeline_catalog_id INTEGER
                REFERENCES pipeline_catalog(id)
        """
    )

    op.execute(
        """
        ALTER TABLE pipeline_catalog
            ADD COLUMN IF NOT EXISTS pipeline_uri TEXT,
            ADD COLUMN IF NOT EXISTS default_profile TEXT,
            ADD COLUMN IF NOT EXISTS compatibility_rules JSONB
                NOT NULL DEFAULT '{}'::JSONB,
            ADD COLUMN IF NOT EXISTS scope_lab_id INTEGER REFERENCES labs(id),
            ADD COLUMN IF NOT EXISTS scope_project_id INTEGER REFERENCES projects(id)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_events (
            id           BIGSERIAL PRIMARY KEY,
            run_id       TEXT NOT NULL,
            event_type   TEXT NOT NULL,
            event_json   JSONB NOT NULL,
            received_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS pipeline_events_run_id_idx "
        "ON pipeline_events (run_id, received_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_tasks (
            id            BIGSERIAL PRIMARY KEY,
            run_id        TEXT NOT NULL,
            task_id       TEXT NOT NULL,
            task_name     TEXT,
            status        TEXT,
            container     TEXT,
            cpus          INTEGER,
            memory_mb     BIGINT,
            duration_ms   BIGINT,
            submitted_at  TEXT,
            started_at    TEXT,
            completed_at  TEXT,
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (run_id, task_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS pipeline_tasks_run_id_idx ON pipeline_tasks (run_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_files (
            id          BIGSERIAL PRIMARY KEY,
            run_id      TEXT NOT NULL,
            sample_id   TEXT,
            file_uri    TEXT NOT NULL,
            file_type   TEXT NOT NULL,
            scope       TEXT NOT NULL DEFAULT 'sample',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (run_id, file_uri)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS pipeline_files_run_id_idx ON pipeline_files (run_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_restarts (
            id                BIGSERIAL PRIMARY KEY,
            new_run_id        TEXT NOT NULL,
            previous_run_id   TEXT NOT NULL,
            resumed_by_id     INTEGER REFERENCES users(id),
            resumed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (new_run_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS pipeline_restarts_previous_idx "
        "ON pipeline_restarts (previous_run_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS project_pipelines (
            id                 SERIAL PRIMARY KEY,
            project_id         INTEGER NOT NULL REFERENCES projects(id)
                                    ON DELETE CASCADE,
            pipeline_name      TEXT NOT NULL,
            github_url         TEXT NOT NULL,
            revision           TEXT NOT NULL,
            parameter_schema   JSONB NOT NULL DEFAULT '{}'::JSONB,
            status             TEXT NOT NULL DEFAULT 'UNVERIFIED',
            created_by_id      INTEGER REFERENCES users(id),
            created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (project_id, pipeline_name)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS lab_pipelines (
            id                          SERIAL PRIMARY KEY,
            lab_id                      INTEGER NOT NULL REFERENCES labs(id)
                                              ON DELETE CASCADE,
            pipeline_catalog_id         INTEGER REFERENCES pipeline_catalog(id),
            source_project_pipeline_id  INTEGER REFERENCES project_pipelines(id),
            promoted_by_id              INTEGER REFERENCES users(id),
            promoted_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (lab_id, pipeline_catalog_id)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS lab_pipelines")
    op.execute("DROP TABLE IF EXISTS project_pipelines")
    op.execute("DROP INDEX IF EXISTS pipeline_restarts_previous_idx")
    op.execute("DROP TABLE IF EXISTS pipeline_restarts")
    op.execute("DROP INDEX IF EXISTS pipeline_files_run_id_idx")
    op.execute("DROP TABLE IF EXISTS pipeline_files")
    op.execute("DROP INDEX IF EXISTS pipeline_tasks_run_id_idx")
    op.execute("DROP TABLE IF EXISTS pipeline_tasks")
    op.execute("DROP INDEX IF EXISTS pipeline_events_run_id_idx")
    op.execute("DROP TABLE IF EXISTS pipeline_events")

    op.execute(
        """
        ALTER TABLE pipeline_catalog
            DROP COLUMN IF EXISTS scope_project_id,
            DROP COLUMN IF EXISTS scope_lab_id,
            DROP COLUMN IF EXISTS compatibility_rules,
            DROP COLUMN IF EXISTS default_profile,
            DROP COLUMN IF EXISTS pipeline_uri
        """
    )

    op.execute(
        """
        ALTER TABLE pipeline_runs
            DROP COLUMN IF EXISTS pipeline_catalog_id,
            DROP COLUMN IF EXISTS soft_warnings,
            DROP COLUMN IF EXISTS parameters
        """
    )
