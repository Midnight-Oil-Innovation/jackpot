"""Phase P0h H-3 — per-launch Slurm account override.

The active execution profile carries a default
``config_overrides.account`` (the lab's ledger). LaunchRequest's new
``launch_account`` field lets a lab member charge a specific grant
for one run without mutating the profile row. Override only carries
semantics when the resolved profile uses the SLURM executor;
non-Slurm + ``launch_account`` is rejected with 400.

P0c multi-tenancy middleware will validate the override against the
user's lab memberships once it lands; today the override is accepted
verbatim and an SLURM_LAUNCH_ACCOUNT_OVERRIDE audit row captures
actor + (before, after) account values.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from unittest.mock import patch

import pytest
from test_launch_with_profile import _drop_profile, _insert_profile
from test_pipelines_router_api import (
    SEED_PROJECT_ID,
    _cleanup_catalog_by_id,
    _cleanup_run,
    _cleanup_samples,
    _insert_catalog,
    _insert_sample,
    _switch_user,
    _unique,
)

from backend.database import execute_query, execute_write

# Inlined fixtures — peer of test_launch_with_profile.py. Cross-module
# fixture sharing requires a tests/ conftest.py that this repo does
# not ship (see the comment in test_auth_refresh.py); duplicating
# three small fixtures is preferable to adding one for this file.


@pytest.fixture
def as_platform_admin(monkeypatch):
    _switch_user("admin@example.org", monkeypatch)


@pytest.fixture
def stub_submit_to_batch():
    with patch("backend.routers.pipelines.submit_to_batch") as m:
        m.return_value = {"batch_job_id": "batch-stub", "executor": "stub"}
        yield m


@pytest.fixture
def temporarily_demote_seeded_default() -> Iterator[None]:
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


# ─────────────── happy path: SLURM + override ────────────────


@pytest.mark.asyncio
async def test_launch_account_override_replaces_profile_default_in_rendered_config(
    client, as_platform_admin, stub_submit_to_batch, tmp_path
):
    prefix = _unique("H3OVR")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(pipeline_name=_unique("jp-h3-override"))
    profile = _insert_profile(
        name=_unique("h3-slurm"),
        executor_type="SLURM",
        container_engine="APPTAINER",
        work_dir=str(tmp_path),
        config_overrides={"queue": "compute", "account": "lab-default"},
    )
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
                "profile_id": str(profile["profile_id"]),
                "launch_account": "grant-NIH-R01-12345",
            },
        )
        assert resp.status_code == 201, resp.text
        run_id = resp.json()["data"]["run_id"]

        rendered = (tmp_path / "runs" / run_id / "jackpot_run.config").read_text()
        assert "--account=grant-NIH-R01-12345" in rendered
        # Profile default was overridden, not appended.
        assert "--account=lab-default" not in rendered

        _cleanup_run(run_id)
    finally:
        _drop_profile(profile["name"])
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_account_override_writes_audit_row(
    client, as_platform_admin, stub_submit_to_batch, tmp_path
):
    prefix = _unique("H3AUD")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(pipeline_name=_unique("jp-h3-audit"))
    profile = _insert_profile(
        name=_unique("h3-audit-slurm"),
        executor_type="SLURM",
        container_engine="APPTAINER",
        work_dir=str(tmp_path),
        config_overrides={"queue": "gpu", "account": "lab-default-audit"},
    )
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
                "profile_id": str(profile["profile_id"]),
                "launch_account": "grant-NSF-DBI-99999",
            },
        )
        assert resp.status_code == 201
        run_id = resp.json()["data"]["run_id"]

        rows = execute_query(
            "SELECT action, before_state, after_state, metadata FROM audit_log "
            "WHERE resource_type = 'pipeline_run' AND resource_id = :r "
            "AND action = 'SLURM_LAUNCH_ACCOUNT_OVERRIDE'",
            {"r": run_id},
        )
        assert len(rows) == 1
        before = (
            rows[0]["before_state"]
            if isinstance(rows[0]["before_state"], dict)
            else json.loads(rows[0]["before_state"])
        )
        after = (
            rows[0]["after_state"]
            if isinstance(rows[0]["after_state"], dict)
            else json.loads(rows[0]["after_state"])
        )
        assert before == {"account": "lab-default-audit"}
        assert after == {"account": "grant-NSF-DBI-99999"}

        _cleanup_run(run_id)
    finally:
        _drop_profile(profile["name"])
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_without_override_keeps_profile_default(
    client, as_platform_admin, stub_submit_to_batch, tmp_path
):
    prefix = _unique("H3DEF")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(pipeline_name=_unique("jp-h3-default"))
    profile = _insert_profile(
        name=_unique("h3-default-slurm"),
        executor_type="SLURM",
        container_engine="APPTAINER",
        work_dir=str(tmp_path),
        config_overrides={"queue": "compute", "account": "lab-default-only"},
    )
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
                "profile_id": str(profile["profile_id"]),
            },
        )
        assert resp.status_code == 201
        run_id = resp.json()["data"]["run_id"]

        rendered = (tmp_path / "runs" / run_id / "jackpot_run.config").read_text()
        assert "--account=lab-default-only" in rendered

        # No override audit row when launch_account omitted.
        rows = execute_query(
            "SELECT action FROM audit_log "
            "WHERE resource_type = 'pipeline_run' AND resource_id = :r "
            "AND action = 'SLURM_LAUNCH_ACCOUNT_OVERRIDE'",
            {"r": run_id},
        )
        assert rows == []

        _cleanup_run(run_id)
    finally:
        _drop_profile(profile["name"])
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


# ─────────────── rejection: non-Slurm executor ────────────────


@pytest.mark.asyncio
async def test_launch_account_rejected_for_local_executor(
    client, as_platform_admin, stub_submit_to_batch, tmp_path
):
    prefix = _unique("H3LOC")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(pipeline_name=_unique("jp-h3-local"))
    profile = _insert_profile(
        name=_unique("h3-local-prof"),
        executor_type="LOCAL",
        container_engine="DOCKER",
        work_dir=str(tmp_path),
    )
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
                "profile_id": str(profile["profile_id"]),
                "launch_account": "should-not-be-accepted",
            },
        )
        assert resp.status_code == 400
        assert "LAUNCH_ACCOUNT_NOT_APPLICABLE" in resp.text
    finally:
        _drop_profile(profile["name"])
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_account_rejected_when_legacy_fallback_path(
    client,
    as_platform_admin,
    stub_submit_to_batch,
    temporarily_demote_seeded_default,
    tmp_path,
):
    """No execution profile resolves → legacy GCP-Batch fallback. The
    legacy path is non-Slurm, so launch_account must be rejected before
    falling through to it."""
    prefix = _unique("H3LEG")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(pipeline_name=_unique("jp-h3-legacy"))
    try:
        # Stub the legacy path's GCP requirements so we don't trip
        # gcp_project_id validation before reaching our 400.
        with patch.dict("os.environ", {"GCP_PROJECT_ID": "jackpot-test"}, clear=False):
            resp = await client.post(
                "/api/v1/pipelines/launch",
                json={
                    "pipeline_id": cat_id,
                    "sample_ids": [sample["sample_id"]],
                    "project_id": SEED_PROJECT_ID,
                    "launch_account": "should-not-be-accepted",
                },
            )
        assert resp.status_code == 400
        assert "LAUNCH_ACCOUNT_NOT_APPLICABLE" in resp.text
    finally:
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)
