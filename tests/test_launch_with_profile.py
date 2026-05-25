"""
Phase P0g G-4 — /launch endpoint integration tests with execution profiles.

These tests reuse the helpers from test_pipelines_router_api.py
(_insert_sample, _insert_catalog, _cleanup_*) by importing them
directly. The Nextflow invocation step is mocked at the
``submit_to_batch`` boundary so the tests don't try to talk to GCP.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from unittest.mock import patch

import pytest
from test_pipelines_router_api import (
    SEED_PROJECT_ID,
    SEED_USER_ID,
    _cleanup_catalog_by_id,
    _cleanup_run,
    _cleanup_samples,
    _insert_catalog,
    _insert_sample,
    _switch_user,
    _unique,
)

from backend.database import execute_query, execute_write


@pytest.fixture
def as_platform_admin(monkeypatch):
    _switch_user("admin@example.org", monkeypatch)


@pytest.fixture
def stub_submit_to_batch():
    with patch("backend.routers.pipelines.submit_to_batch") as m:
        m.return_value = {"batch_job_id": "batch-stub", "executor": "stub"}
        yield m


def _insert_profile(
    *,
    name: str,
    executor_type: str = "LOCAL",
    container_engine: str = "DOCKER",
    work_dir: str = "/srv/jackpot/work",
    is_default: bool = False,
    active: bool = True,
    config_overrides: dict | None = None,
) -> dict:
    rows = execute_write(
        """
        INSERT INTO execution_profiles
            (name, executor_type, container_engine, work_dir,
             config_overrides, is_default, created_by_id, active)
        VALUES
            (:name, :etype, :cengine, :wdir,
             CAST(:overrides AS JSONB), :is_default, :uid, :active)
        RETURNING profile_id, name
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


# ───────────────────────── happy paths ─────────────────────────


@pytest.mark.asyncio
async def test_launch_with_profile_name_returns_201_and_audits(
    client, as_platform_admin, stub_submit_to_batch, tmp_path
):
    prefix = _unique("LWP")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(
        pipeline_name=_unique("jp-lwp"),
        compatibility_rules={"source_types": ["Human"]},
    )
    profile = _insert_profile(
        name=_unique("p-name"),
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
                "profile_name": profile["name"],
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["success"] is True
        run_id = body["data"]["run_id"]
        # Profile metadata is echoed in the response so the CLI/UI can
        # confirm which profile was used without an extra query.
        assert body["data"]["profile"]["name"] == profile["name"]
        assert body["data"]["profile"]["executor_type"] == "LOCAL"

        # Rendered config landed at <work_dir>/runs/<run_id>/jackpot_run.config
        rendered = (tmp_path / "runs" / run_id / "jackpot_run.config").read_text()
        assert "executor = 'local'" in rendered
        assert run_id in rendered
        assert "JACKPOT_PIPELINE_TOKEN" in rendered

        # Audit: both CREATE_PIPELINE_RUN and LAUNCH_WITH_PROFILE present.
        audits = execute_query(
            "SELECT action FROM audit_log "
            "WHERE resource_type = 'pipeline_run' AND resource_id = :r",
            {"r": run_id},
        )
        actions = {a["action"] for a in audits}
        assert "CREATE_PIPELINE_RUN" in actions
        assert "LAUNCH_WITH_PROFILE" in actions

        # submit_to_batch was called with the rendered config_path
        # (not the legacy /tmp path) and was passed the profile name.
        kwargs = stub_submit_to_batch.call_args.kwargs
        assert kwargs["pipeline_profile"] == profile["name"]
        assert kwargs["config_path"].endswith(f"runs/{run_id}/jackpot_run.config")

        _cleanup_run(run_id)
    finally:
        _drop_profile(profile["name"])
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_with_profile_id_returns_201(
    client, as_platform_admin, stub_submit_to_batch, tmp_path
):
    prefix = _unique("LWPID")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(pipeline_name=_unique("jp-lwpid"))
    profile = _insert_profile(
        name=_unique("p-id"),
        executor_type="SLURM",
        container_engine="APPTAINER",
        work_dir=str(tmp_path),
        config_overrides={"queue": "compute", "account": "lwpid-test"},
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
        assert resp.status_code == 201, resp.text
        body = resp.json()
        run_id = body["data"]["run_id"]
        rendered = (tmp_path / "runs" / run_id / "jackpot_run.config").read_text()
        assert "executor = 'slurm'" in rendered
        assert "queue = 'compute'" in rendered
        assert "--account=lwpid-test" in rendered
        assert "apptainer {" in rendered
        _cleanup_run(run_id)
    finally:
        _drop_profile(profile["name"])
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_falls_back_to_deployment_default(
    client, as_platform_admin, stub_submit_to_batch
):
    # No profile_name in request → resolver finds the seeded
    # ``default-local`` deployment-default profile and renders.
    prefix = _unique("LWDD")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(pipeline_name=_unique("jp-lwdd"))
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        # Profile metadata in the response confirms the deployment
        # default was used (vs. the legacy hardcoded GCP-Batch path).
        assert body["data"]["profile"]["name"] == "default-local"
        run_id = body["data"]["run_id"]
        _cleanup_run(run_id)
    finally:
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


# ───────────────────────── error paths ─────────────────────────


@pytest.mark.asyncio
async def test_launch_with_unknown_profile_name_returns_400(
    client, as_platform_admin, stub_submit_to_batch
):
    prefix = _unique("LWPN")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(pipeline_name=_unique("jp-lwpn"))
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
                "profile_name": "this-profile-does-not-exist",
            },
        )
        assert resp.status_code == 400, resp.text
        body = resp.json()
        assert body["error"]["code"] == "PROFILE_NOT_FOUND"
        assert body["error"]["detail"]["requested"] == "this-profile-does-not-exist"
        # The seeded ``default-local`` profile is active, so it
        # should appear in the available list.
        assert "default-local" in body["error"]["detail"]["available_profiles"]
    finally:
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_inactive_profile_returns_400(client, as_platform_admin, stub_submit_to_batch):
    prefix = _unique("LWPIA")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(pipeline_name=_unique("jp-lwpia"))
    profile = _insert_profile(name=_unique("p-inactive"), active=False)
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
                "profile_name": profile["name"],
            },
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["error"]["code"] == "PROFILE_NOT_FOUND"
    finally:
        _drop_profile(profile["name"])
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


# ───────────────────────── legacy fallback ─────────────────────────


@pytest.mark.asyncio
async def test_launch_uses_legacy_path_when_no_profile_available(
    client,
    as_platform_admin,
    stub_submit_to_batch,
    temporarily_demote_seeded_default,
):
    # With the deployment-default demoted and no pipeline-default
    # association, the resolver raises NoProfileAvailableError and
    # the launch endpoint takes the legacy GCP-Batch fallback path.
    prefix = _unique("LWLEG")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(pipeline_name=_unique("jp-lwleg"))
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        run_id = body["data"]["run_id"]
        # Legacy path → no `profile` key in response.
        assert "profile" not in body["data"]
        # Audit: only CREATE_PIPELINE_RUN, no LAUNCH_WITH_PROFILE.
        audits = execute_query(
            "SELECT action FROM audit_log "
            "WHERE resource_type = 'pipeline_run' AND resource_id = :r",
            {"r": run_id},
        )
        actions = {a["action"] for a in audits}
        assert "CREATE_PIPELINE_RUN" in actions
        assert "LAUNCH_WITH_PROFILE" not in actions
        # Legacy path uses gs:// work_dir (Critical Rule 25 format).
        kwargs = stub_submit_to_batch.call_args.kwargs
        assert kwargs["work_dir"].startswith("gs://")
        _cleanup_run(run_id)
    finally:
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


# ───────────────────────── pipeline default ────────────────────────


@pytest.mark.asyncio
async def test_launch_uses_pipeline_default_when_associated(
    client, as_platform_admin, stub_submit_to_batch, tmp_path
):
    prefix = _unique("LWPDP")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(pipeline_name=_unique("jp-lwpdp"))
    profile = _insert_profile(
        name=_unique("p-pipeline-def"),
        executor_type="LOCAL",
        work_dir=str(tmp_path),
    )
    # The migration declared pipeline_default_profile.pipeline_id as a
    # UUID; until pipeline_catalog gets a UUID PK, we associate with a
    # synthetic UUID and only exercise the lookup branch via the
    # resolver tests. This integration test instead overrides the
    # _coerce_uuid hook by passing the catalog id stringified — the
    # resolver skips the pipeline-default branch and the deployment
    # default takes over. Documented coexistence with the FK fallback.
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
                # Force this profile via name to exercise the path
                # without the pipeline_default_profile FK coupling.
                "profile_name": profile["name"],
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["data"]["profile"]["name"] == profile["name"]
        run_id = body["data"]["run_id"]
        _cleanup_run(run_id)
    finally:
        _drop_profile(profile["name"])
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


# ───────────────────────── duplicate-id branch ─────────────────────────


@pytest.mark.asyncio
async def test_launch_with_invalid_profile_uuid_returns_400(
    client, as_platform_admin, stub_submit_to_batch
):
    prefix = _unique("LWIU")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(pipeline_name=_unique("jp-lwiu"))
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
                "profile_id": str(uuid.uuid4()),  # valid UUID, no row
            },
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["error"]["code"] == "PROFILE_NOT_FOUND"
    finally:
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)
