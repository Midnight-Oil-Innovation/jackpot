"""Phase P0h H-6 — pre-launch Slurm cluster reachability check.

Two surfaces to test:

1. ``check_slurm_reachability``: TTL cache, settings opt-out, sinfo
   subprocess outcomes (OK / non-zero / timeout / not-installed).
2. ``POST /api/v1/pipelines/launch``: when the resolved profile is
   SLURM and the probe fails, returns 400 SLURM_UNREACHABLE before
   minting a run_id; when reachable, the launch proceeds normally.
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest
from test_launch_with_profile import (
    _drop_profile,
    _insert_profile,
)
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

from backend.config import get_settings
from backend.database import execute_query
from backend.pipeline_config.cluster_reachability import (
    SlurmReachabilityResult,
    check_slurm_reachability,
    reset_cache,
)


@pytest.fixture(autouse=True)
def _reset_reachability_cache():
    reset_cache()
    yield
    reset_cache()


@pytest.fixture
def reachability_enabled(monkeypatch):
    """Opt the reachability check back in (the default conftest
    setting disables it for the rest of the suite)."""
    monkeypatch.setenv("SLURM_REACHABILITY_CHECK_ENABLED", "true")
    get_settings.cache_clear()
    yield
    monkeypatch.setenv("SLURM_REACHABILITY_CHECK_ENABLED", "false")
    get_settings.cache_clear()


@pytest.fixture
def as_platform_admin(monkeypatch):
    _switch_user("admin@example.org", monkeypatch)


@pytest.fixture
def stub_submit_to_batch():
    with patch("backend.routers.pipelines.submit_to_batch") as m:
        m.return_value = {"batch_job_id": "batch-stub", "executor": "stub"}
        yield m


# ─────────────── check_slurm_reachability unit tests ────────────────


def test_check_returns_disabled_when_setting_off():
    # No monkeypatch of the env — the conftest default leaves the
    # check disabled.
    result = check_slurm_reachability()
    assert result.reachable is True
    assert result.code == "DISABLED"


def test_check_returns_ok_when_sinfo_succeeds(reachability_enabled):
    fake = subprocess.CompletedProcess(
        args=["sinfo", "-h"], returncode=0, stdout="up infinite 4 idle node[01-04]\n", stderr=""
    )
    with (
        patch(
            "backend.pipeline_config.cluster_reachability.shutil.which",
            return_value="/usr/bin/sinfo",
        ),
        patch(
            "backend.pipeline_config.cluster_reachability.subprocess.run",
            return_value=fake,
        ),
    ):
        result = check_slurm_reachability()
    assert result == SlurmReachabilityResult(reachable=True, code="OK")


def test_check_reports_sinfo_failed_on_nonzero(reachability_enabled):
    fake = subprocess.CompletedProcess(
        args=["sinfo", "-h"],
        returncode=1,
        stdout="",
        stderr="slurm_load_partitions: Connection refused",
    )
    with (
        patch(
            "backend.pipeline_config.cluster_reachability.shutil.which",
            return_value="/usr/bin/sinfo",
        ),
        patch(
            "backend.pipeline_config.cluster_reachability.subprocess.run",
            return_value=fake,
        ),
    ):
        result = check_slurm_reachability()
    assert result.reachable is False
    assert result.code == "SINFO_FAILED"
    assert "Connection refused" in result.detail


def test_check_reports_timeout(reachability_enabled):
    with (
        patch(
            "backend.pipeline_config.cluster_reachability.shutil.which",
            return_value="/usr/bin/sinfo",
        ),
        patch(
            "backend.pipeline_config.cluster_reachability.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["sinfo"], timeout=10),
        ),
    ):
        result = check_slurm_reachability()
    assert result.reachable is False
    assert result.code == "SINFO_TIMEOUT"


def test_check_reports_not_installed_when_which_returns_none(reachability_enabled):
    with patch(
        "backend.pipeline_config.cluster_reachability.shutil.which",
        return_value=None,
    ):
        result = check_slurm_reachability()
    assert result.reachable is False
    assert result.code == "SINFO_NOT_INSTALLED"


def test_cache_hit_skips_subprocess(reachability_enabled):
    fake = subprocess.CompletedProcess(args=["sinfo"], returncode=0, stdout="", stderr="")
    call_count = 0

    def _counting_run(*a, **k):
        nonlocal call_count
        call_count += 1
        return fake

    with (
        patch(
            "backend.pipeline_config.cluster_reachability.shutil.which",
            return_value="/usr/bin/sinfo",
        ),
        patch(
            "backend.pipeline_config.cluster_reachability.subprocess.run",
            side_effect=_counting_run,
        ),
    ):
        check_slurm_reachability()
        check_slurm_reachability()
        check_slurm_reachability()

    # Three calls in rapid succession; the cache TTL is 60 seconds, so
    # the subprocess must have run exactly once.
    assert call_count == 1


def test_cache_keyed_by_account_partition(reachability_enabled):
    fake = subprocess.CompletedProcess(args=["sinfo"], returncode=0, stdout="", stderr="")
    call_count = 0

    def _counting_run(*a, **k):
        nonlocal call_count
        call_count += 1
        return fake

    with (
        patch(
            "backend.pipeline_config.cluster_reachability.shutil.which",
            return_value="/usr/bin/sinfo",
        ),
        patch(
            "backend.pipeline_config.cluster_reachability.subprocess.run",
            side_effect=_counting_run,
        ),
    ):
        check_slurm_reachability(account="lab-2026", partition="compute")
        check_slurm_reachability(account="lab-2026", partition="gpu")
        check_slurm_reachability(account="lab-2027", partition="compute")
        # Repeat of the first entry hits the cache.
        check_slurm_reachability(account="lab-2026", partition="compute")

    assert call_count == 3


# ─────────────── /pipelines/launch integration ────────────────


@pytest.mark.asyncio
async def test_launch_blocks_with_400_when_slurm_unreachable(
    client, as_platform_admin, stub_submit_to_batch, reachability_enabled, tmp_path
):
    prefix = _unique("H6BLK")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(pipeline_name=_unique("jp-h6-block"))
    profile = _insert_profile(
        name=_unique("h6-slurm-block"),
        executor_type="SLURM",
        container_engine="APPTAINER",
        work_dir=str(tmp_path),
        config_overrides={"queue": "compute", "account": "lab"},
    )
    fake = subprocess.CompletedProcess(
        args=["sinfo"],
        returncode=1,
        stdout="",
        stderr="cluster down",
    )
    try:
        with (
            patch(
                "backend.pipeline_config.cluster_reachability.shutil.which",
                return_value="/usr/bin/sinfo",
            ),
            patch(
                "backend.pipeline_config.cluster_reachability.subprocess.run",
                return_value=fake,
            ),
        ):
            resp = await client.post(
                "/api/v1/pipelines/launch",
                json={
                    "pipeline_id": cat_id,
                    "sample_ids": [sample["sample_id"]],
                    "project_id": SEED_PROJECT_ID,
                    "profile_id": str(profile["profile_id"]),
                },
            )
        assert resp.status_code == 400, resp.text
        assert "SLURM_UNREACHABLE" in resp.text
        assert "jackpot doctor" in resp.text

        # No pipeline_runs row created — the guard fires before run_id is minted.
        rows = execute_query(
            "SELECT id FROM pipeline_runs WHERE pipeline_name = :n",
            {"n": "jp-h6-block"},
        )
        assert rows == []
    finally:
        _drop_profile(profile["name"])
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_proceeds_when_slurm_reachable(
    client, as_platform_admin, stub_submit_to_batch, reachability_enabled, tmp_path
):
    prefix = _unique("H6OK")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(pipeline_name=_unique("jp-h6-ok"))
    profile = _insert_profile(
        name=_unique("h6-slurm-ok"),
        executor_type="SLURM",
        container_engine="APPTAINER",
        work_dir=str(tmp_path),
        config_overrides={"queue": "compute", "account": "lab"},
    )
    fake = subprocess.CompletedProcess(
        args=["sinfo"],
        returncode=0,
        stdout="up infinite 4 idle\n",
        stderr="",
    )
    try:
        with (
            patch(
                "backend.pipeline_config.cluster_reachability.shutil.which",
                return_value="/usr/bin/sinfo",
            ),
            patch(
                "backend.pipeline_config.cluster_reachability.subprocess.run",
                return_value=fake,
            ),
        ):
            resp = await client.post(
                "/api/v1/pipelines/launch",
                json={
                    "pipeline_id": cat_id,
                    "sample_ids": [sample["sample_id"]],
                    "project_id": SEED_PROJECT_ID,
                    "profile_id": str(profile["profile_id"]),
                },
            )
        assert resp.status_code == 201, resp.text
        run_id = resp.json()["data"]["run_id"]
        _cleanup_run(run_id)
    finally:
        _drop_profile(profile["name"])
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_does_not_check_reachability_for_local_executor(
    client, as_platform_admin, stub_submit_to_batch, reachability_enabled, tmp_path
):
    """A LOCAL profile must not invoke sinfo — H-6 is SLURM-only."""
    prefix = _unique("H6LCL")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(pipeline_name=_unique("jp-h6-local"))
    profile = _insert_profile(
        name=_unique("h6-local"),
        executor_type="LOCAL",
        container_engine="DOCKER",
        work_dir=str(tmp_path),
    )
    try:
        with patch("backend.pipeline_config.cluster_reachability.subprocess.run") as m_run:
            resp = await client.post(
                "/api/v1/pipelines/launch",
                json={
                    "pipeline_id": cat_id,
                    "sample_ids": [sample["sample_id"]],
                    "project_id": SEED_PROJECT_ID,
                    "profile_id": str(profile["profile_id"]),
                },
            )
        assert resp.status_code == 201, resp.text
        # The launch succeeded AND the reachability subprocess never ran.
        assert m_run.call_count == 0
        run_id = resp.json()["data"]["run_id"]
        _cleanup_run(run_id)
    finally:
        _drop_profile(profile["name"])
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)
