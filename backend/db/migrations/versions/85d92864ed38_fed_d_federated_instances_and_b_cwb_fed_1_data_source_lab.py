"""FED-D federated_instances + organizations federation columns + B-CWB-FED-1 data_source_lab role

Schema migration backing the FED-A federation package (backend/backend/federation/).

What this migration does:

1. Creates the ``federation_role`` PostgreSQL ENUM with the four values
   needed by the cryptWWDB three-party model (Driver et al. 2024 §4):
   ``hub``, ``spoke``, ``peer``, ``data_source_lab``. The last value is
   B-CWB-FED-1 — the Lab produces pipeline_results via X-Pipeline-Token
   auth but holds no samples of its own, so FederationClient queryable
   predicates filter it differently from a data-holding peer.

2. Creates the ``federated_instances`` table — one row per registered
   partner deployment. Field shape matches the FED-A Pydantic
   ``FederatedInstance`` model in
   ``backend/backend/federation/models.py``. ``api_key_secret_name`` is
   a GCP Secret Manager reference, not the key itself — keys never live
   in DB rows (architecture §22).

3. Extends ``organizations`` with the four federation-policy columns
   per FED-A: ``min_sharing_level_for_federation``, ``federation_enabled``,
   ``hub_instance_url``, ``federation_role``.

Divergence from the FED-D session-prompt wording (FED-A models.py is the
source of truth per Critical Rule N+3):

  * Instance role column is named ``role`` (matches Pydantic field
    name) — not ``federation_role``.
  * Master switch column is ``federation_enabled`` with default FALSE
    (matches FED-A description: "set False to silently drop without
    removal"), not ``enabled`` with default TRUE.
  * Sharing-level column is ``min_sharing_level_for_federation`` (matches
    FED-A), not ``min_sharing_level_accepted``.
  * Liveness column is ``last_seen_at`` (matches FED-A), not
    ``last_health_check_at``.
  * The org-level ``federation_role`` is nullable (NULL = no role)
    rather than carrying a sentinel ``'none'`` enum value — cleaner SQL
    semantics, no migration needed when an org steps in or out of
    federation, and the enum stays valid for both the instance and the
    org columns. Application code must treat NULL as "no federation
    role".
  * ``min_sharing_level_for_federation`` is stored as TEXT with a CHECK
    constraint rather than as a Postgres ENUM, matching the existing
    ``samples.sharing_level`` column convention (baseline migration
    5adf11b77c19 line 296 — TEXT NOT NULL DEFAULT 'PRIVATE').

No SQLAlchemy ORM updates: this codebase queries the DB through raw SQL
via ``sqlalchemy.text()`` (see ``backend/backend/database.py``). The
Alembic env.py has ``target_metadata = None``. There is no
``backend/backend/db/models.py`` to update; the FED-A Pydantic model in
``backend/backend/federation/models.py`` is the API-layer counterpart
and already carries the matching FederatedInstance shape (+ the
DATA_SOURCE_LAB enum value added in this PR).

Revision ID: 85d92864ed38
Revises:    591318fd3049
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "85d92864ed38"
down_revision: str | None = "591318fd3049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# SharingLevelEnum values from backend/backend/models_generated.py.
# Stored as TEXT + CHECK to match the existing samples.sharing_level
# column convention (baseline migration 5adf11b77c19).
_SHARING_LEVELS = (
    "PRIVATE",
    "LAB",
    "DISCOVERABLE",
    "REGISTERED_ACCESS",
    "PUBLIC",
)


def upgrade() -> None:
    # pgcrypto already enabled by earlier migration (bac8dbb11c0b) but
    # CREATE EXTENSION IF NOT EXISTS is idempotent — guard against the
    # case where this migration runs against an environment that has
    # not yet reached bac8dbb11c0b.
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))

    # 1. federation_role ENUM type.
    op.execute(
        sa.text(
            """
        CREATE TYPE federation_role AS ENUM (
            'hub',
            'spoke',
            'peer',
            'data_source_lab'
        );
        """
        )
    )

    # 2. federated_instances table — matches FED-A Pydantic FederatedInstance.
    sharing_levels_sql = ", ".join(f"'{v}'" for v in _SHARING_LEVELS)
    op.execute(
        sa.text(
            f"""
        CREATE TABLE federated_instances (
            id                               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name                             TEXT NOT NULL UNIQUE,
            base_url                         TEXT NOT NULL,
            role                             federation_role NOT NULL,
            federation_enabled               BOOLEAN NOT NULL DEFAULT FALSE,
            min_sharing_level_for_federation TEXT NOT NULL DEFAULT 'DISCOVERABLE'
                                             CHECK (min_sharing_level_for_federation IN ({sharing_levels_sql})),
            hub_instance_url                 TEXT,
            api_key_secret_name              TEXT NOT NULL,
            last_seen_at                     TIMESTAMPTZ,
            created_at                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at                       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """  # noqa: S608 — sharing_levels_sql is built from a constant tuple, not user input
        )
    )

    op.execute(
        sa.text(
            """
        CREATE INDEX idx_federated_instances_role
            ON federated_instances (role)
            WHERE federation_enabled = TRUE;
        """
        )
    )

    # 3. updated_at trigger — same pattern as sample_files (34382b7b82c6).
    op.execute(
        sa.text(
            """
        CREATE OR REPLACE FUNCTION set_federated_instances_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
        )
    )
    op.execute(
        sa.text(
            """
        CREATE TRIGGER federated_instances_updated_at_trigger
            BEFORE UPDATE ON federated_instances
            FOR EACH ROW
            EXECUTE FUNCTION set_federated_instances_updated_at();
        """
        )
    )

    op.execute(
        sa.text(
            """
        COMMENT ON TABLE federated_instances IS
            'Registered partner JACKPOT deployments. Field shape mirrors '
            'the FED-A Pydantic FederatedInstance model in '
            'backend/backend/federation/models.py. api_key_secret_name '
            'is a GCP Secret Manager reference — keys never live in DB '
            'rows. data_source_lab role added per B-CWB-FED-1 for the '
            'cryptWWDB three-party model (Driver et al. 2024 §4).';
        """
        )
    )

    # 4. organizations federation-policy columns.
    op.execute(
        sa.text(
            f"""
        ALTER TABLE organizations
            ADD COLUMN min_sharing_level_for_federation TEXT
                NOT NULL DEFAULT 'PRIVATE'
                CHECK (min_sharing_level_for_federation IN ({sharing_levels_sql})),
            ADD COLUMN federation_enabled               BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN hub_instance_url                 TEXT,
            ADD COLUMN federation_role                  federation_role;
        """  # noqa: S608 — sharing_levels_sql is built from a constant tuple, not user input
        )
    )

    op.execute(
        sa.text(
            """
        COMMENT ON COLUMN organizations.federation_role IS
            'Federation role this organization plays in the partner '
            'topology. NULL = no federation role assigned. Shared enum '
            'with federated_instances.role; see B-CWB-FED-1 for the '
            'data_source_lab value.';
        """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
        ALTER TABLE organizations
            DROP COLUMN IF EXISTS federation_role,
            DROP COLUMN IF EXISTS hub_instance_url,
            DROP COLUMN IF EXISTS federation_enabled,
            DROP COLUMN IF EXISTS min_sharing_level_for_federation;
        """
        )
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS federated_instances_updated_at_trigger ON federated_instances;"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS set_federated_instances_updated_at();"))
    op.execute(sa.text("DROP INDEX IF EXISTS idx_federated_instances_role;"))
    op.execute(sa.text("DROP TABLE IF EXISTS federated_instances;"))
    op.execute(sa.text("DROP TYPE IF EXISTS federation_role;"))
