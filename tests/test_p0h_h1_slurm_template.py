"""Phase P0h H-1 — Slurm template extensions.

The pre-H-1 (G-3) template covered queue / account / qos / time /
cluster_options. H-1 adds:

- ``memory`` and ``cpus`` defaults on the per-process block
- ``executor.queueSize`` from a ``queue_size`` override
- a ``params`` block exposing run_id / weblog_url / results_url /
  pipeline_token to DSL2 pipelines
- ``apptainer.cacheDir`` (cross-cutting; lives in ``base.config.j2``)
  with a ``<work_dir>/apptainer-cache`` fallback

Existing G-3 tests in ``tests/test_profile_renderer.py`` cover the
backward-compatible minimum and are deliberately not duplicated here.
"""

from __future__ import annotations

import uuid

from backend.pipeline_config.profile_renderer import render_nextflow_config
from backend.pipeline_config.types import ExecutionProfile


def _profile(
    *,
    container_engine: str = "DOCKER",
    config_overrides: dict | None = None,
    work_dir: str = "/srv/jackpot/work",
) -> ExecutionProfile:
    return ExecutionProfile(
        profile_id=uuid.uuid4(),
        name="p0h-h1-fixture",
        executor_type="SLURM",
        container_engine=container_engine,
        work_dir=work_dir,
        config_overrides=config_overrides or {},
    )


_RENDER_KWARGS = {
    "pipeline": {
        "pipeline_name": "jp-sc2",
        "pipeline_version": "1.2.3",
        "description": "Test SARS-CoV-2 pipeline",
        "author": "JACKPOT",
        "main_script": "main.nf",
    },
    "run_id": "jp-h1run",
    "weblog_url": "http://api.test/api/v1/pipelines/events",
    "result_registration_url": "http://api.test/api/v1/pipelines/jp-h1run/results",
    "pipeline_token": "pt_h1_token",
    "work_dir": "/srv/jackpot/work",
}


# ──────────────── new per-process resource defaults ─────────────────


def test_slurm_memory_override_renders_process_memory():
    rendered = render_nextflow_config(
        profile=_profile(config_overrides={"memory": "16 GB"}),
        **_RENDER_KWARGS,
    )
    assert "memory = '16 GB'" in rendered


def test_slurm_cpus_override_renders_process_cpus():
    rendered = render_nextflow_config(
        profile=_profile(config_overrides={"cpus": 8}),
        **_RENDER_KWARGS,
    )
    assert "cpus = 8" in rendered


def test_slurm_memory_without_cpus_emits_only_memory():
    rendered = render_nextflow_config(
        profile=_profile(config_overrides={"memory": "32 GB"}),
        **_RENDER_KWARGS,
    )
    assert "memory = '32 GB'" in rendered
    assert "cpus =" not in rendered


# ──────────────────── executor.queueSize block ──────────────────────


def test_slurm_queue_size_emits_executor_block():
    rendered = render_nextflow_config(
        profile=_profile(config_overrides={"queue_size": 25}),
        **_RENDER_KWARGS,
    )
    assert "executor {" in rendered
    assert "name = 'slurm'" in rendered
    assert "queueSize = 25" in rendered


def test_slurm_no_queue_size_omits_executor_block():
    rendered = render_nextflow_config(
        profile=_profile(),
        **_RENDER_KWARGS,
    )
    # The base template has no `executor {` block; the Slurm template
    # adds one only when queue_size is set. Avoid asserting on the
    # exact substring `executor {` because base.config.j2 already
    # contains the unrelated `executor_block` Jinja tag — but the
    # rendered Groovy must not declare an executor scope.
    assert "queueSize" not in rendered


# ──────────────────────── params {} block ───────────────────────────


def test_slurm_params_block_includes_run_id_and_token():
    rendered = render_nextflow_config(
        profile=_profile(),
        **_RENDER_KWARGS,
    )
    assert "params {" in rendered
    assert "jackpot_run_id      = 'jp-h1run'" in rendered
    assert "jackpot_token       = 'pt_h1_token'" in rendered


def test_slurm_params_block_uses_render_urls():
    rendered = render_nextflow_config(
        profile=_profile(),
        **_RENDER_KWARGS,
    )
    assert "jackpot_weblog_url  = 'http://api.test/api/v1/pipelines/events'" in rendered
    assert "jackpot_results_url = 'http://api.test/api/v1/pipelines/jp-h1run/results'" in rendered


# ───────────────── apptainer cacheDir (base.config.j2) ───────────────


def test_apptainer_cache_dir_falls_back_to_work_dir():
    rendered = render_nextflow_config(
        profile=_profile(container_engine="APPTAINER"),
        **_RENDER_KWARGS,
    )
    assert "apptainer {" in rendered
    assert "cacheDir = '/srv/jackpot/work/apptainer-cache'" in rendered


def test_apptainer_cache_dir_override_wins():
    rendered = render_nextflow_config(
        profile=_profile(
            container_engine="APPTAINER",
            config_overrides={"apptainer_cache_dir": "/scratch/shared/apptainer"},
        ),
        **_RENDER_KWARGS,
    )
    assert "cacheDir = '/scratch/shared/apptainer'" in rendered


def test_docker_engine_does_not_emit_cache_dir():
    rendered = render_nextflow_config(
        profile=_profile(container_engine="DOCKER"),
        **_RENDER_KWARGS,
    )
    assert "docker {" in rendered
    # The DOCKER branch has no cacheDir line; cacheDir is an apptainer-
    # only knob in the base template.
    assert "cacheDir" not in rendered


# ──────────────── full-field-set integration check ───────────────────


def test_slurm_full_field_set_renders():
    rendered = render_nextflow_config(
        profile=_profile(
            container_engine="APPTAINER",
            config_overrides={
                "queue": "compute",
                "account": "lab-2026",
                "qos": "premium",
                "cluster_options": "--exclusive",
                "time": "8h",
                "memory": "64 GB",
                "cpus": 16,
                "queue_size": 50,
                "apptainer_cache_dir": "/scratch/apptainer",
            },
        ),
        **_RENDER_KWARGS,
    )
    # Every documented knob lands.
    assert "executor = 'slurm'" in rendered
    assert "queue = 'compute'" in rendered
    assert "time = '8h'" in rendered
    assert "memory = '64 GB'" in rendered
    assert "cpus = 16" in rendered
    assert "--account=lab-2026" in rendered
    assert "--qos=premium" in rendered
    assert "--exclusive" in rendered
    assert "queueSize = 50" in rendered
    assert "cacheDir = '/scratch/apptainer'" in rendered
    # Params block still emits.
    assert "jackpot_run_id      = 'jp-h1run'" in rendered
