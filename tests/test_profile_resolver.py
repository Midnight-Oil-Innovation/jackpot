"""
Phase P0g G-4 — profile_resolver tests.

Exercises the full resolution chain against the real test database
(testcontainers Postgres seeded by the conftest). Profiles are
inserted/cleaned up per-test; the migration-seeded ``default-local``
profile is left in place but is_default is taken into account.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator

import pytest

from backend.database import execute_query, execute_write
from backend.pipeline_config.profile_resolver import (
    NoProfileAvailableError,
    ProfileNotFoundError,
    resolve_profile,
)

SEED_USER_ID = 1


def _insert_profile(
    *,
    name: str,
    executor_type: str = "LOCAL",
    container_engine: str = "DOCKER",
    work_dir: str = "/srv/jackpot/work",
    config_overrides: dict | None = None,
    is_default: bool = False,
    active: bool = True,
) -> dict:
    rows = execute_write(
        """
        INSERT INTO execution_profiles
            (name, executor_type, container_engine, work_dir,
             config_overrides, is_default, created_by_id, active)
        VALUES
            (:name, :etype, :cengine, :wdir,
             CAST(:overrides AS JSONB), :is_default, :uid, :active)
        RETURNING profile_id, name, is_default
        """,
        {
            "name": name,
            "etype": executor_type,
            "cengine": container_engine,
            "wdir": work_dir,
            "overrides": json.dumps(config_overrides or {}),
            "is_default": is_default,
            "uid": SEED_USER_ID,
            "active": active,
        },
    )
    return rows[0]


def _drop_profile(name: str) -> None:
    execute_write("DELETE FROM execution_profiles WHERE name = :n", {"n": name})


def _associate(pipeline_id: str, profile_id, priority: int = 100) -> None:
    execute_write(
        """
        INSERT INTO pipeline_default_profile (pipeline_id, profile_id, priority)
        VALUES (:pid, :prof, :prio)
        """,
        {"pid": pipeline_id, "prof": profile_id, "prio": priority},
    )


def _drop_associations(pipeline_id: str) -> None:
    execute_write(
        "DELETE FROM pipeline_default_profile WHERE pipeline_id = :pid",
        {"pid": pipeline_id},
    )


@pytest.fixture
def fresh_pipeline_id() -> Iterator[str]:
    """Return a fresh UUID string and clean up associations afterwards."""
    pid = str(uuid.uuid4())
    yield pid
    _drop_associations(pid)


@pytest.fixture
def temporarily_demote_seeded_default() -> Iterator[None]:
    """
    Some tests need 'no deployment-default exists'. The bac8dbb11c0b
    seed inserts ``default-local`` with is_default=true. Flip it off
    for the test, restore on teardown.
    """
    rows = execute_query("SELECT name, is_default FROM execution_profiles WHERE is_default = TRUE")
    name = rows[0]["name"] if rows else None
    if name:
        execute_write(
            "UPDATE execution_profiles SET is_default = FALSE WHERE name = :n",
            {"n": name},
        )
    yield
    if name:
        execute_write(
            "UPDATE execution_profiles SET is_default = TRUE WHERE name = :n",
            {"n": name},
        )


# ───────────────────────── explicit selectors ──────────────────────────


def test_explicit_profile_name_resolves(fresh_pipeline_id):
    p = _insert_profile(name="resolver-test-explicit")
    try:
        result = resolve_profile(
            db_conn=None,
            pipeline_id=fresh_pipeline_id,
            profile_name="resolver-test-explicit",
        )
        assert result.name == "resolver-test-explicit"
        assert result.profile_id == p["profile_id"]
    finally:
        _drop_profile("resolver-test-explicit")


def test_explicit_profile_id_resolves(fresh_pipeline_id):
    p = _insert_profile(name="resolver-test-by-id", executor_type="SLURM")
    try:
        result = resolve_profile(
            db_conn=None,
            pipeline_id=fresh_pipeline_id,
            profile_id=str(p["profile_id"]),
        )
        assert result.executor_type == "SLURM"
    finally:
        _drop_profile("resolver-test-by-id")


def test_profile_id_wins_when_both_supplied(fresh_pipeline_id):
    by_id = _insert_profile(name="resolver-by-id-wins", executor_type="SLURM")
    # Insert a second profile to make the "name loses" assertion meaningful;
    # the row is referenced only to ensure resolution didn't pick it.
    _insert_profile(name="resolver-by-name-loses", executor_type="GCP_BATCH")
    try:
        result = resolve_profile(
            db_conn=None,
            pipeline_id=fresh_pipeline_id,
            profile_id=str(by_id["profile_id"]),
            profile_name="resolver-by-name-loses",
        )
        assert result.profile_id == by_id["profile_id"]
        assert result.executor_type == "SLURM"
    finally:
        _drop_profile("resolver-by-id-wins")
        _drop_profile("resolver-by-name-loses")


def test_inactive_explicit_raises_profile_not_found(fresh_pipeline_id):
    _insert_profile(name="resolver-inactive", active=False)
    try:
        with pytest.raises(ProfileNotFoundError) as excinfo:
            resolve_profile(
                db_conn=None,
                pipeline_id=fresh_pipeline_id,
                profile_name="resolver-inactive",
            )
        # Available list comes from active rows only — the seeded
        # default-local is active so it should appear.
        assert "default-local" in excinfo.value.available_profile_names
        assert "resolver-inactive" not in excinfo.value.available_profile_names
        assert excinfo.value.requested == "resolver-inactive"
    finally:
        _drop_profile("resolver-inactive")


def test_unknown_explicit_name_raises_profile_not_found(fresh_pipeline_id):
    with pytest.raises(ProfileNotFoundError) as excinfo:
        resolve_profile(
            db_conn=None,
            pipeline_id=fresh_pipeline_id,
            profile_name="does-not-exist",
        )
    assert excinfo.value.requested == "does-not-exist"
    assert isinstance(excinfo.value.available_profile_names, list)


# ───────────────────────── pipeline default ────────────────────────────


def test_pipeline_default_used_when_no_explicit(fresh_pipeline_id):
    p = _insert_profile(name="resolver-pdp", executor_type="SLURM")
    _associate(fresh_pipeline_id, p["profile_id"], priority=10)
    try:
        result = resolve_profile(db_conn=None, pipeline_id=fresh_pipeline_id)
        assert result.name == "resolver-pdp"
        assert result.executor_type == "SLURM"
    finally:
        _drop_profile("resolver-pdp")


def test_lowest_priority_wins_among_pipeline_defaults(fresh_pipeline_id):
    high = _insert_profile(name="resolver-high-prio", executor_type="LOCAL")
    low = _insert_profile(name="resolver-low-prio", executor_type="SLURM")
    _associate(fresh_pipeline_id, high["profile_id"], priority=100)
    _associate(fresh_pipeline_id, low["profile_id"], priority=10)
    try:
        result = resolve_profile(db_conn=None, pipeline_id=fresh_pipeline_id)
        assert result.name == "resolver-low-prio"
    finally:
        _drop_profile("resolver-high-prio")
        _drop_profile("resolver-low-prio")


# ───────────────────────── deployment default ──────────────────────────


def test_deployment_default_used_when_no_pipeline_default(fresh_pipeline_id):
    # Seeded default-local is is_default=true and active=true.
    result = resolve_profile(db_conn=None, pipeline_id=fresh_pipeline_id)
    assert result.name == "default-local"
    assert result.is_default is True


# ───────────────────────── exhausted chain ─────────────────────────────


def test_no_profile_available_raises_when_chain_empty(
    fresh_pipeline_id, temporarily_demote_seeded_default
):
    with pytest.raises(NoProfileAvailableError) as excinfo:
        resolve_profile(db_conn=None, pipeline_id=fresh_pipeline_id)
    assert isinstance(excinfo.value.configured_profile_names, list)


def test_no_profile_available_lists_pipeline_defaults(
    fresh_pipeline_id, temporarily_demote_seeded_default
):
    p = _insert_profile(name="resolver-inactive-default", active=False)
    _associate(fresh_pipeline_id, p["profile_id"], priority=1)
    try:
        with pytest.raises(NoProfileAvailableError) as excinfo:
            resolve_profile(db_conn=None, pipeline_id=fresh_pipeline_id)
        # Inactive profile is excluded from the configured list since
        # the resolver only lists active rows.
        assert excinfo.value.configured_profile_names == []
    finally:
        _drop_profile("resolver-inactive-default")
