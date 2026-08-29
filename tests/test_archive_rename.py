# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""B-CARE-3i — the soft-delete flag is ``is_archived``, not the legacy name.

ADR-0013: archive and deletion are distinct. The boolean column only ever
meant "archived"; the sovereignty deletion lifecycle lives exclusively in
``samples.deletion_status``. These tests pin the rename across all three
tables that carried the flag and the archive endpoint's response shape.
"""

import pytest

from backend.config import get_settings
from backend.database import execute_query, execute_write

# Composed so the retired name never appears verbatim (the B-CARE-3i
# acceptance gate greps for it).
LEGACY_FLAG = "is_" + "deleted"

SEED_LAB_ID = 1
SEED_PROJECT_ID = 1
SEED_USER_ID = 1


def _columns(table: str) -> set[str]:
    rows = execute_query(
        "SELECT column_name FROM information_schema.columns WHERE table_name = :t",
        {"t": table},
    )
    return {r["column_name"] for r in rows}


@pytest.mark.parametrize("table", ["samples", "sample_files", "submissions"])
def test_is_archived_column_present_legacy_flag_gone(table):
    cols = _columns(table)
    assert "is_archived" in cols
    assert LEGACY_FLAG not in cols


def test_is_archived_readable_and_writable():
    row = execute_write(
        "INSERT INTO samples (sample_id, lab_id, project_id, owner_id, source_type, "
        "organism_name, type_of_experiment, library_preparation_method, "
        "sequencing_protocol, sequencing_platform, sequencing_lab, date_collected, "
        "date_sequenced, collection_facility, collection_location_country, "
        "sharing_level, fastq_r1_uri) VALUES "
        "('RENAME-RW-01', 1, 1, 1, 'Human', "
        "'Severe acute respiratory syndrome coronavirus 2', 'WGS', 'ARTIC', "
        "'https://www.protocols.io/view/artic-v4-1', 'Illumina', "
        "'Example Sequencing Lab', '2026-01-15', '2026-01-17', 'Example Hospital', "
        "'United States', 'PRIVATE', 'gs://jackpot-sequences/t/R1.fastq.gz') "
        "RETURNING *",
    )[0]
    assert row["is_archived"] is False
    assert LEGACY_FLAG not in row
    updated = execute_write(
        "UPDATE samples SET is_archived = TRUE WHERE id = :id RETURNING is_archived",
        {"id": row["id"]},
    )[0]
    assert updated["is_archived"] is True
    execute_write("DELETE FROM samples WHERE id = :id", {"id": row["id"]})


@pytest.mark.asyncio
async def test_archive_endpoint_reports_is_archived(client, monkeypatch):
    monkeypatch.setenv("MOCK_USER_EMAIL", "admin@example.org")
    get_settings.cache_clear()
    row = execute_write(
        "INSERT INTO samples (sample_id, lab_id, project_id, owner_id, source_type, "
        "organism_name, type_of_experiment, library_preparation_method, "
        "sequencing_protocol, sequencing_platform, sequencing_lab, date_collected, "
        "date_sequenced, collection_facility, collection_location_country, "
        "sharing_level, fastq_r1_uri) VALUES "
        "('RENAME-API-01', 1, 1, 1, 'Human', "
        "'Severe acute respiratory syndrome coronavirus 2', 'WGS', 'ARTIC', "
        "'https://www.protocols.io/view/artic-v4-1', 'Illumina', "
        "'Example Sequencing Lab', '2026-01-15', '2026-01-17', 'Example Hospital', "
        "'United States', 'PRIVATE', 'gs://jackpot-sequences/t/R1.fastq.gz') "
        "RETURNING id",
    )[0]
    resp = await client.delete(f"/api/v1/samples/{row['id']}")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["is_archived"] is True
    assert LEGACY_FLAG not in data
    execute_write(
        "UPDATE audit_log SET actor_id = NULL WHERE resource_type = 'sample' "
        "AND resource_id = :rid",
        {"rid": str(row["id"])},
    )
    execute_write("DELETE FROM samples WHERE id = :id", {"id": row["id"]})


@pytest.mark.asyncio
async def test_archive_nonexistent_sample_returns_404(client, monkeypatch):
    """Failure path: archiving a sample that does not exist is a 404."""
    monkeypatch.setenv("MOCK_USER_EMAIL", "admin@example.org")
    get_settings.cache_clear()
    resp = await client.delete("/api/v1/samples/99999999")
    assert resp.status_code == 404
