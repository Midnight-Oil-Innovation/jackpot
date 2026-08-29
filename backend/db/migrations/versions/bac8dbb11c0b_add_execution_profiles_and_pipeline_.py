"""add_execution_profiles_and_pipeline_default_profile

Phase P0g G-2 schema additions for per-run executor selection
(Critical Rule 59). Creates two tables — ``execution_profiles`` and
``pipeline_default_profile`` — plus a partial unique index that
enforces "at most one deployment-default profile" without blocking
the common case of many non-default profiles.

The seed step inserts a single ``default-local`` profile so existing
deployments have a fallback profile to launch with after upgrade. The
seed runs only when the deployment already has at least one user (so
the FK from ``execution_profiles.created_by_id`` to ``users.id`` can
be satisfied) and uses ``ON CONFLICT (name) DO NOTHING`` so re-running
``alembic upgrade head`` is idempotent.

Pipelines FK fallback: the spec calls for a UUID FK from
``pipeline_default_profile.pipeline_id`` to ``pipelines.pipeline_id``,
but the current schema does not expose pipelines as either a LinkML
class or a UUID-keyed SQL table — the closest analog,
``pipeline_catalog``, carries a SERIAL integer id. Per the G-1 prompt's
fallback guidance, this migration declares ``pipeline_id`` as
``UUID NOT NULL`` with no FK constraint; when the pipelines surface
gets a LinkML class with a UUID PK, a follow-up migration can add the
FK. See the PR body for the rationale.

Revision ID: bac8dbb11c0b
Revises:    3644749bf4c6
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "bac8dbb11c0b"
down_revision = "3644749bf4c6"
branch_labels = None
depends_on = None


_EXECUTOR_TYPES = (
    "LOCAL",
    "SLURM",
    "PBS",
    "LSF",
    "GCP_BATCH",
    "AWS_BATCH",
    "KUBERNETES",
)
_CONTAINER_ENGINES = ("DOCKER", "APPTAINER", "SINGULARITY", "NONE")


def _quoted_in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    # ── prerequisite: gen_random_uuid() lives in pgcrypto ───────────
    # Postgres 13+ ships pgcrypto in core; ``CREATE EXTENSION IF NOT
    # EXISTS`` is a no-op on existing installations and a safe
    # one-liner on fresh ones. Done here rather than in the baseline
    # migration because P0g is the first JACKPOT migration to need a
    # UUID DEFAULT.
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))

    # ── execution_profiles ─────────────────────────────────────────
    op.execute(
        sa.text(
            f"""
        CREATE TABLE execution_profiles (
            profile_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name              TEXT NOT NULL UNIQUE,
            executor_type     TEXT NOT NULL
                              CHECK (executor_type IN ({_quoted_in_list(_EXECUTOR_TYPES)})),
            container_engine  TEXT NOT NULL
                              CHECK (container_engine IN ({_quoted_in_list(_CONTAINER_ENGINES)})),
            work_dir          TEXT NOT NULL,
            config_overrides  JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            is_default        BOOLEAN NOT NULL DEFAULT FALSE,
            created_by_id     INTEGER NOT NULL REFERENCES users(id),
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            active            BOOLEAN NOT NULL DEFAULT TRUE
        );
        """
        )
    )

    # ── partial unique index: at most one is_default=true ──────────
    # The partial WHERE clause means only rows with is_default=TRUE
    # participate in the uniqueness check; many rows with FALSE are
    # always permitted.
    op.execute(
        sa.text(
            """
        CREATE UNIQUE INDEX idx_execution_profiles_one_default
            ON execution_profiles (is_default)
            WHERE is_default = TRUE;
        """
        )
    )

    # ── pipeline_default_profile ───────────────────────────────────
    # pipeline_id is UUID without an FK — see module docstring.
    # ON DELETE CASCADE on profile_id keeps the association table
    # tidy when an operator hard-deletes a profile (the typical path
    # is soft-delete via active=false; hard-delete is reserved for
    # operator cleanup).
    op.execute(
        sa.text(
            """
        CREATE TABLE pipeline_default_profile (
            pipeline_id  UUID NOT NULL,
            profile_id   UUID NOT NULL
                         REFERENCES execution_profiles(profile_id)
                         ON DELETE CASCADE,
            priority     INTEGER NOT NULL DEFAULT 100,
            PRIMARY KEY (pipeline_id, profile_id)
        );
        """
        )
    )

    # ── seed: default-local profile ────────────────────────────────
    # Idempotent (ON CONFLICT (name) DO NOTHING) and conditional on
    # at least one user existing (so the FK to users.id can be
    # satisfied). Fresh installations that run alembic upgrade head
    # before any user is created will skip the seed; operators can
    # create the default profile via the future G-9 CLI or by
    # re-running the migration after the first user lands.
    op.execute(
        sa.text(
            """
        DO $$
        DECLARE
            seed_user_id INTEGER;
        BEGIN
            SELECT id INTO seed_user_id FROM users ORDER BY id ASC LIMIT 1;
            IF seed_user_id IS NOT NULL THEN
                INSERT INTO execution_profiles (
                    name, executor_type, container_engine, work_dir,
                    config_overrides, is_default, created_by_id, active
                ) VALUES (
                    'default-local',
                    'LOCAL',
                    'DOCKER',
                    '/srv/jackpot/work',
                    '{}'::jsonb,
                    TRUE,
                    seed_user_id,
                    TRUE
                )
                ON CONFLICT (name) DO NOTHING;
            END IF;
        END $$;
        """
        )
    )

    # ── documentation comments ─────────────────────────────────────
    op.execute(
        sa.text(
            """
        COMMENT ON TABLE execution_profiles IS
            'Phase P0g — operator-configured execution profiles. Per '
            'Critical Rule 59, pipeline executor selection is per-run, '
            'not per-deployment. Soft-deleted via active=false.';
        """
        )
    )
    op.execute(
        sa.text(
            """
        COMMENT ON TABLE pipeline_default_profile IS
            'Phase P0g — default execution profile association for a '
            'pipeline. priority breaks ties when multiple defaults '
            'match (lower wins). pipeline_id is intentionally an '
            'unenforced UUID until pipelines gets a UUID-keyed table.';
        """
        )
    )


def downgrade() -> None:
    # Drop in reverse FK-dependency order: association table first,
    # then the partial unique index, then the parent table. The
    # pgcrypto extension is intentionally left in place — dropping it
    # would break unrelated installations that rely on it.
    op.execute(sa.text("DROP TABLE IF EXISTS pipeline_default_profile;"))
    op.execute(sa.text("DROP INDEX IF EXISTS idx_execution_profiles_one_default;"))
    op.execute(sa.text("DROP TABLE IF EXISTS execution_profiles;"))
