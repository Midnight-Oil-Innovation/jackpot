# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""DB-integration tests for ``load_inputs_from_db`` (B-CWB-MB-1-DB).

Unlike ``test_mass_balance.py`` (pure compute, no DB), this file needs a
real Postgres testcontainer. ``tests/wastewater/conftest.py`` overrides
the root ``initialize_test_db`` / ``override_settings`` autouse fixtures
with no-ops for the whole directory; both are redefined here (same body
as the root ``tests/conftest.py`` versions) so this module gets the real
testcontainer-backed DB instead. A cross-package ``tests.conftest``
import is ambiguous (``cli/tests`` is also an implicit-namespace
``tests`` package), so the fixtures are duplicated rather than imported.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from backend.config import get_settings
from backend.credentials import _reset_backend
from backend.database import execute_write, reset_engine
from backend.wastewater.mass_balance import (
    ConcentrationUnit,
    FlowUnit,
    load_inputs_from_db,
)

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"


@pytest.fixture(scope="session", autouse=True)
def initialize_test_db(test_db_url):
    env = os.environ.copy()
    env["DATABASE_URL"] = test_db_url
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        env=env,
        cwd=_BACKEND_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("Alembic upgrade failed: " + result.stdout + result.stderr)
    yield


@pytest.fixture(autouse=True)
def override_settings(test_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", test_db_url)
    monkeypatch.setenv("ENV", "local")
    get_settings.cache_clear()
    _reset_backend()
    reset_engine()
    yield
    get_settings.cache_clear()
    _reset_backend()
    reset_engine()


SAMPLE_PREFIX = "WW-MB-DB-"
TARGET = "sars-cov-2"


def _insert_sample(sample_id: str) -> int:
    rows = execute_write(
        """
        INSERT INTO samples (
            sample_id, lab_id, project_id, owner_id, source_type,
            organism_name, type_of_experiment, library_preparation_method,
            sequencing_protocol, sequencing_platform, sequencing_lab,
            date_collected, date_sequenced, collection_facility,
            collection_location_country, sharing_level, fastq_r1_uri,
            surveillance_relevant
        ) VALUES (
            :sample_id, 1, 1, 1, 'Wastewater',
            'Severe acute respiratory syndrome coronavirus 2', 'WGS',
            'ARTIC', 'https://www.protocols.io/view/artic-v4-1', 'Illumina',
            'Example Sequencing Lab', '2026-01-15', '2026-01-17',
            'Example Hospital', 'United States', 'PRIVATE',
            'gs://test/R1.fq.gz', FALSE
        ) RETURNING id
        """,
        {"sample_id": sample_id},
    )
    return rows[0]["id"]


def _insert_concentration(
    sample_id: str,
    *,
    flow_rate_mgd: float | None,
    concentration: float | None,
    concentration_unit: str = ConcentrationUnit.COPIES_PER_L.value,
    below_lod: bool = False,
    lod_value: float | None = None,
) -> None:
    execute_write(
        """
        INSERT INTO wastewater_target_concentration (
            run_id, sample_id, target, concentration, concentration_unit,
            flow_rate_mgd, below_lod, lod_value, collection_timestamp
        ) VALUES (
            'run-1', :sample_id, :target, :concentration, :concentration_unit,
            :flow_rate_mgd, :below_lod, :lod_value, NOW()
        )
        """,
        {
            "sample_id": sample_id,
            "target": TARGET,
            "concentration": concentration,
            "concentration_unit": concentration_unit,
            "flow_rate_mgd": flow_rate_mgd,
            "below_lod": below_lod,
            "lod_value": lod_value,
        },
    )


@pytest.fixture
def upstream_downstream_pair():
    upstream_id = f"{SAMPLE_PREFIX}UP"
    downstream_id = f"{SAMPLE_PREFIX}DOWN"
    upstream_pk = _insert_sample(upstream_id)
    downstream_pk = _insert_sample(downstream_id)
    execute_write(
        """
        INSERT INTO sample_associations
            (source_sample_id, target_sample_id, association_type)
        VALUES (:upstream_pk, :downstream_pk, 'wastewater_upstream_of')
        """,
        {"upstream_pk": upstream_pk, "downstream_pk": downstream_pk},
    )
    yield upstream_id, downstream_id
    execute_write(
        "DELETE FROM sample_associations WHERE source_sample_id = :u AND target_sample_id = :d",
        {"u": upstream_pk, "d": downstream_pk},
    )
    execute_write(
        "DELETE FROM wastewater_target_concentration WHERE sample_id IN (:u, :d)",
        {"u": upstream_id, "d": downstream_id},
    )
    execute_write(
        "DELETE FROM samples WHERE id IN (:u, :d)", {"u": upstream_pk, "d": downstream_pk}
    )


def test_load_inputs_from_db_resolves_upstream_and_downstream(upstream_downstream_pair) -> None:
    upstream_id, downstream_id = upstream_downstream_pair
    _insert_concentration(upstream_id, flow_rate_mgd=1.0, concentration=10.0)
    _insert_concentration(downstream_id, flow_rate_mgd=2.0, concentration=60.0)

    inputs = load_inputs_from_db(downstream_id, TARGET, session=None)

    assert inputs.upstream_flow.value == 1.0
    assert inputs.upstream_flow.unit == FlowUnit.MGD
    assert inputs.upstream_concentration.value == 10.0
    assert inputs.downstream_flow.value == 2.0
    assert inputs.downstream_concentration.value == 60.0
    assert inputs.target_pathogen_id == TARGET
    assert inputs.timestamp is not None


def test_load_inputs_from_db_below_lod_substitutes_zero_with_lod(upstream_downstream_pair) -> None:
    upstream_id, downstream_id = upstream_downstream_pair
    _insert_concentration(upstream_id, flow_rate_mgd=1.0, concentration=None)
    _insert_concentration(
        downstream_id,
        flow_rate_mgd=2.0,
        concentration=None,
        below_lod=True,
        lod_value=5.0,
    )

    inputs = load_inputs_from_db(downstream_id, TARGET, session=None)

    assert inputs.downstream_concentration.value == 0.0
    assert inputs.downstream_concentration.lod == 5.0


def test_load_inputs_from_db_missing_association_raises() -> None:
    orphan_id = f"{SAMPLE_PREFIX}ORPHAN"
    _insert_sample(orphan_id)
    try:
        with pytest.raises(ValueError, match="wastewater_upstream_of"):
            load_inputs_from_db(orphan_id, TARGET, session=None)
    finally:
        execute_write("DELETE FROM samples WHERE sample_id = :sid", {"sid": orphan_id})


def test_load_inputs_from_db_missing_concentration_row_raises(upstream_downstream_pair) -> None:
    upstream_id, downstream_id = upstream_downstream_pair
    _insert_concentration(upstream_id, flow_rate_mgd=1.0, concentration=10.0)
    # No concentration row for downstream.

    with pytest.raises(ValueError, match="wastewater_target_concentration"):
        load_inputs_from_db(downstream_id, TARGET, session=None)
