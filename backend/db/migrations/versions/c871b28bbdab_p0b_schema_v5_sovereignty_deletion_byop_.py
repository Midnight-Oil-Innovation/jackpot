"""P0b (Schema v5.0) — sovereignty deletion + BYOP registry + eukaryotic metadata + cryptWWDB readiness

Phase 24.5 close-out. Single migration off head ``85d92864ed38`` (FED-D).
Implements the DDL side of ``docs/architecture/p0b_schema_v5_migration_spec.md``
§3's ordered operation list. Raw SQL via ``op.execute(sa.text(...))`` with
``CREATE TABLE IF NOT EXISTS`` / ``ADD COLUMN IF NOT EXISTS`` per the applied
house style; ``target_metadata = None`` (this codebase queries via raw SQL,
not the SQLAlchemy ORM).

Ordered operations (spec §3):

1. ``byop_pipelines`` table (spec §2.6) — created first so the
   ``pipeline_results.byop_pipeline_id`` FK target exists. Enum-typed columns
   are TEXT + CHECK matching house convention. Tenancy columns
   (``owner_lab_id``, ``sharing_scope``, ``origin_instance_id``) are added at
   creation per the resolved design gap (spec §4); ``origin_instance_id`` is
   UUID to match ``federated_instances.id``.
2. ``samples`` sovereignty deletion columns (spec §2.1) — six columns;
   ``deletion_status`` is TEXT NOT NULL DEFAULT 'ACTIVE' (deliberate TEXT+CHECK
   divergence from sovereignty §12's native enum — spec §2.1/§4).
3. ``samples`` deletion value-set CHECK, ACTIVE/requested-at CHECK, and the
   composite ``(deletion_status, tombstoned_at)`` index (spec §2.2).
4. ``samples`` eukaryotic metadata columns (spec §2.7).
5. ``pipeline_results.tombstoned`` boolean (spec §2.3). No FK is added:
   ``pipeline_results.sample_id`` is value-matched TEXT with no ``REFERENCES``
   clause, so sovereignty §12's "MUST NOT cascade-delete" is vacuously
   satisfied (spec §2.3/§4).
6. ``pipeline_results`` BYOP linkage columns (spec §2.4) — after step 1.
7. ``wastewater_target_concentration`` readiness table (spec §2.9,
   B-CWB-SCHEMA-1) — follows the applied result-table pattern (``run_id`` /
   ``sample_id`` TEXT, no FK).

No-op close-outs (spec §3 step 8, emit no DDL):
  * ``audit_log`` deletion event names (spec §2.10) are application-level
    string constants written into ``audit_log.action`` in P0c (B-CARE-3f) —
    there is no ``audit_log.event_type`` column and no enum to extend.
  * ``wastewater_upstream_of`` (spec §2.8, B-CWB-SCHEMA-2) is a new value on
    the free-TEXT ``sample_associations.association_type`` — yaml/enum only,
    no DDL.

Supersession note (spec §4): ``byop_pipelines`` is the canonical BYOP registry
and **supersedes** the applied ``project_pipelines`` skeleton (migration
``cea9c08543ee``), whose docstring labels it the "BYOP skeleton (UNVERIFIED)".
``project_pipelines`` is NOT dropped here — ``lab_pipelines.source_project_pipeline_id``
references it; its retirement is tracked as P0c ``B-P0C-DEPRECATE-PROJPIPE``.

DDL-only objects (``byop_pipelines``, the ``pipeline_results`` columns, and
``wastewater_target_concentration``) produce no yaml/LinkML class; every other
applied result/operational table is DDL-only too. The LinkML enums that back
the P0b yaml edits (DeletionStatusEnum, the four BYOP enums,
ParasiteDevelopmentalStageEnum, SamplePreservationMethodEnum, the 38 net-new
OrganismNameEnum values, and wastewater_upstream_of) live in
``schema/schema/jackpot_schema.yaml`` and drive the Pydantic/JSON layer via
``scripts/regen_schema.py``; they are not created by this migration.

Revision ID: c871b28bbdab
Revises: 85d92864ed38
Create Date: 2026-07-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c871b28bbdab"
down_revision: str | None = "85d92864ed38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. byop_pipelines table (spec §2.6) — create first: pipeline_results
    #    .byop_pipeline_id (step 6) targets it. Enum-typed columns are
    #    TEXT + CHECK, matching the deletion_status decision and house
    #    convention. FK targets labs / federated_instances are already applied.
    op.execute(
        sa.text(
            """
        CREATE TABLE IF NOT EXISTS byop_pipelines (
            id                      SERIAL PRIMARY KEY,
            name                    TEXT NOT NULL,
            display_name            TEXT NOT NULL,
            version                 TEXT NOT NULL,
            description             TEXT,
            engine_type             TEXT NOT NULL
                CHECK (engine_type IN ('nextflow','snakemake','wdl','manifest')),
            engine_version          TEXT NOT NULL,
            source_type             TEXT NOT NULL
                CHECK (source_type IN ('git','git_private','tarball','docker')),
            source_url              TEXT,
            source_ref              TEXT,
            source_uploaded_uri     TEXT,
            source_sha256           TEXT,
            docker_image            TEXT,
            docker_digest           TEXT,
            manifest_yaml           TEXT NOT NULL,
            applicable_organisms    TEXT[],
            applicable_source_types TEXT[],
            applicable_data_types   TEXT[],
            owner_lab_id            INTEGER REFERENCES labs(id),
            sharing_scope           TEXT NOT NULL DEFAULT 'lab'
                CHECK (sharing_scope IN ('private','lab','federation')),
            origin_instance_id      UUID REFERENCES federated_instances(id),
            pipeline_status         TEXT NOT NULL DEFAULT 'SUBMITTED'
                CHECK (pipeline_status IN (
                    'SUBMITTED','VALIDATING','SANDBOX_PENDING','SANDBOX_RUNNING',
                    'ACTIVE','DEACTIVATED','ARCHIVED','VALIDATION_FAILED',
                    'SANDBOX_FAILED','SANDBOX_TIMEOUT')),
            validation_log          TEXT,
            sandbox_log             TEXT,
            registered_by_user_id   INTEGER NOT NULL REFERENCES users(id),
            registered_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            activated_at            TIMESTAMPTZ,
            deactivated_at          TIMESTAMPTZ,
            last_validated_at       TIMESTAMPTZ,
            license_spdx            TEXT NOT NULL,
            citation                TEXT,
            cost_estimate_usd       DOUBLE PRECISION,
            UNIQUE (name, version)
        );
        """
        )
    )
    op.execute(
        sa.text(
            """
        COMMENT ON TABLE byop_pipelines IS
            'Canonical BYOP pipeline registry (P0b, byop design §7). Supersedes '
            'the project_pipelines "BYOP skeleton (UNVERIFIED)" (migration '
            'cea9c08543ee); project_pipelines is retained (lab_pipelines FK) and '
            'retired in P0c B-P0C-DEPRECATE-PROJPIPE. sharing_scope=federation '
            'publishes to peers via copy-on-import; origin_instance_id is '
            'federation provenance, not a live cross-instance reference.';
        """
        )
    )

    # 2. samples sovereignty deletion columns (spec §2.1). deletion_status is
    #    TEXT + CHECK (see step 3), a deliberate divergence from sovereignty
    #    §12's native enum.
    op.execute(
        sa.text(
            """
        ALTER TABLE samples
            ADD COLUMN IF NOT EXISTS deletion_status               TEXT NOT NULL DEFAULT 'ACTIVE',
            ADD COLUMN IF NOT EXISTS deletion_requested_at         TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS deletion_requested_by_user_id INTEGER REFERENCES users(id),
            ADD COLUMN IF NOT EXISTS deletion_reason               TEXT,
            ADD COLUMN IF NOT EXISTS tombstoned_at                 TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS vacuumed_at                   TIMESTAMPTZ;
        """
        )
    )

    # 3. samples deletion constraints + index (spec §2.2). Existing rows all
    #    default to ACTIVE / requested_at NULL, satisfying both CHECKs.
    op.execute(
        sa.text(
            """
        ALTER TABLE samples
            ADD CONSTRAINT samples_deletion_status_values_chk
            CHECK (deletion_status IN ('ACTIVE','DELETION_REQUESTED','TOMBSTONED','VACUUMED'));
        """
        )
    )
    op.execute(
        sa.text(
            """
        ALTER TABLE samples
            ADD CONSTRAINT samples_deletion_active_requested_chk
            CHECK ((deletion_status = 'ACTIVE') = (deletion_requested_at IS NULL));
        """
        )
    )
    op.execute(
        sa.text(
            """
        CREATE INDEX IF NOT EXISTS samples_deletion_status_tombstoned_at_idx
            ON samples (deletion_status, tombstoned_at);
        """
        )
    )

    # 4. samples eukaryotic metadata columns (spec §2.7). Enum-typed columns
    #    are plain TEXT in DDL (no CHECK), matching how existing enum-backed
    #    sample columns are stored (biospecimen_type, host_sex, etc.).
    op.execute(
        sa.text(
            """
        ALTER TABLE samples
            ADD COLUMN IF NOT EXISTS parasite_developmental_stage TEXT,
            ADD COLUMN IF NOT EXISTS sample_preservation_method    TEXT,
            ADD COLUMN IF NOT EXISTS parasitemia_percent           DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS multiplicity_of_infection     INTEGER,
            ADD COLUMN IF NOT EXISTS coinfection_organisms         TEXT[];
        """
        )
    )

    # 5. pipeline_results.tombstoned (spec §2.3). No FK change: sample_id is
    #    value-matched TEXT with no REFERENCES clause.
    op.execute(
        sa.text(
            """
        ALTER TABLE pipeline_results
            ADD COLUMN IF NOT EXISTS tombstoned BOOLEAN NOT NULL DEFAULT FALSE;
        """
        )
    )

    # 6. pipeline_results BYOP linkage columns (spec §2.4). FK target
    #    byop_pipelines exists from step 1. byop_pipeline_id is nullable:
    #    null for curated-zoo runs, set for BYOP runs.
    op.execute(
        sa.text(
            """
        ALTER TABLE pipeline_results
            ADD COLUMN IF NOT EXISTS byop_pipeline_id      INTEGER REFERENCES byop_pipelines(id),
            ADD COLUMN IF NOT EXISTS byop_pipeline_version TEXT;
        """
        )
    )

    # 7. wastewater_target_concentration readiness table (spec §2.9,
    #    B-CWB-SCHEMA-1). Applied result-table pattern: run_id / sample_id
    #    TEXT, no FK, UNIQUE including the discriminating dimension. [THIN-SOURCE]
    op.execute(
        sa.text(
            """
        CREATE TABLE IF NOT EXISTS wastewater_target_concentration (
            id                     SERIAL PRIMARY KEY,
            run_id                 TEXT NOT NULL,
            sample_id              TEXT NOT NULL,
            target                 TEXT NOT NULL,
            target_type            TEXT,
            concentration          DOUBLE PRECISION,
            concentration_unit     TEXT NOT NULL,
            flow_rate_mgd          DOUBLE PRECISION,
            below_lod              BOOLEAN NOT NULL DEFAULT FALSE,
            lod_value              DOUBLE PRECISION,
            collection_timestamp   TIMESTAMPTZ,
            tool_name              TEXT,
            tool_version           TEXT,
            created_at             TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (run_id, sample_id, target)
        );
        """
        )
    )

    # 8. No-op close-outs (spec §3 step 8): audit_log event constants (§2.10)
    #    and wastewater_upstream_of (§2.8) require no DDL. Intentionally empty.


def downgrade() -> None:
    # Reverse order; drop dependents before targets.

    # 7. wastewater_target_concentration.
    op.execute(sa.text("DROP TABLE IF EXISTS wastewater_target_concentration;"))

    # 6. pipeline_results BYOP columns (drop before byop_pipelines table).
    op.execute(
        sa.text(
            """
        ALTER TABLE pipeline_results
            DROP COLUMN IF EXISTS byop_pipeline_id,
            DROP COLUMN IF EXISTS byop_pipeline_version;
        """
        )
    )

    # 5. pipeline_results.tombstoned.
    op.execute(sa.text("ALTER TABLE pipeline_results DROP COLUMN IF EXISTS tombstoned;"))

    # 4. samples eukaryotic columns.
    op.execute(
        sa.text(
            """
        ALTER TABLE samples
            DROP COLUMN IF EXISTS parasite_developmental_stage,
            DROP COLUMN IF EXISTS sample_preservation_method,
            DROP COLUMN IF EXISTS parasitemia_percent,
            DROP COLUMN IF EXISTS multiplicity_of_infection,
            DROP COLUMN IF EXISTS coinfection_organisms;
        """
        )
    )

    # 3. samples deletion index + constraints (drop before the columns).
    op.execute(sa.text("DROP INDEX IF EXISTS samples_deletion_status_tombstoned_at_idx;"))
    op.execute(
        sa.text(
            "ALTER TABLE samples DROP CONSTRAINT IF EXISTS samples_deletion_active_requested_chk;"
        )
    )
    op.execute(
        sa.text("ALTER TABLE samples DROP CONSTRAINT IF EXISTS samples_deletion_status_values_chk;")
    )

    # 2. samples deletion columns.
    op.execute(
        sa.text(
            """
        ALTER TABLE samples
            DROP COLUMN IF EXISTS deletion_status,
            DROP COLUMN IF EXISTS deletion_requested_at,
            DROP COLUMN IF EXISTS deletion_requested_by_user_id,
            DROP COLUMN IF EXISTS deletion_reason,
            DROP COLUMN IF EXISTS tombstoned_at,
            DROP COLUMN IF EXISTS vacuumed_at;
        """
        )
    )

    # 1. byop_pipelines table.
    op.execute(sa.text("DROP TABLE IF EXISTS byop_pipelines;"))
