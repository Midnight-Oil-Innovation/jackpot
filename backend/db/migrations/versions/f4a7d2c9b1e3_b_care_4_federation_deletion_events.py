# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""B-CARE-4 — federation deletion-event propagation ledger

Design doc §9 (docs/architecture/sovereignty-compliant-deletion.md):
tombstone and vacuum events MUST be pushed to all federation peers
within a configurable SLA, peers MUST acknowledge with signed receipts,
and un-acknowledged peers are flagged non-compliant. This table is the
per-(event, peer) ledger the propagation job works from:

- ``payload``/``signature`` — the signed JSON tombstone/vacuum event
  (sample ID, event timestamp, deletion reason class, propagation token;
  never the free-text deletion reason — that is internal per §9).
- ``flag_after`` — when an un-acknowledged event becomes non-compliant
  (SLA for tombstone events, 2× SLA for vacuum events per §9).
- ``ack_signature`` — the peer's signed receipt, stored verbatim
  (signature format is owned by B-FED-1).

Revision ID: f4a7d2c9b1e3
Revises: d8f3b6c1a2e4
Create Date: 2026-08-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4a7d2c9b1e3"
down_revision: str | None = "d8f3b6c1a2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS federation_deletion_events (
                id                SERIAL PRIMARY KEY,
                sample_id_fk      INTEGER NOT NULL REFERENCES samples(id),
                event_type        TEXT NOT NULL
                                  CHECK (event_type IN ('TOMBSTONE', 'VACUUM')),
                peer_instance_id  UUID NOT NULL REFERENCES federated_instances(id),
                payload           JSONB NOT NULL,
                signature         TEXT,
                propagation_token TEXT NOT NULL,
                status            TEXT NOT NULL DEFAULT 'PENDING'
                                  CHECK (status IN ('PENDING', 'ACKNOWLEDGED', 'NON_COMPLIANT')),
                created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                flag_after        TIMESTAMPTZ NOT NULL,
                acknowledged_at   TIMESTAMPTZ,
                ack_signature     TEXT
            );
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS federation_deletion_events_status_idx "
            "ON federation_deletion_events (status);"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS federation_deletion_events_peer_status_idx "
            "ON federation_deletion_events (peer_instance_id, status);"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS federation_deletion_events;"))
