"""
Phase P0g G-3+G-4 — profile_renderer unit tests.

Renders one config per executor type from a fixture profile and
asserts the per-executor process block plus the shared base block
landed in the output. Container-engine variations are checked
explicitly. StrictUndefined behavior is exercised through the
GCP-Batch template, which requires a ``project`` override.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from jinja2 import UndefinedError

from backend.pipeline_config.profile_renderer import (
    _ALLOWED_EXECUTOR_TYPES,
    _template_name_for,
    render_nextflow_config,
    write_run_config,
)
from backend.pipeline_config.types import ExecutionProfile


def _profile(
    executor_type: str,
    *,
    container_engine: str = "DOCKER",
    config_overrides: dict | None = None,
    work_dir: str = "/srv/jackpot/work",
    name: str = "fixture-profile",
) -> ExecutionProfile:
    return ExecutionProfile(
        profile_id=uuid.uuid4(),
        name=name,
        executor_type=executor_type,
        container_engine=container_engine,
        work_dir=work_dir,
        config_overrides=config_overrides or {},
        is_default=False,
        active=True,
    )


_PIPELINE = {
    "pipeline_name": "jp-sc2",
    "pipeline_version": "1.2.3",
    "description": "Test SARS-CoV-2 pipeline",
    "author": "JACKPOT",
    "main_script": "main.nf",
}

_RENDER_KWARGS = {
    "pipeline": _PIPELINE,
    "run_id": "jp-deadbeef",
    "weblog_url": "http://api.test/api/v1/pipelines/events",
    "result_registration_url": "http://api.test/api/v1/pipelines/jp-deadbeef/results",
    "pipeline_token": "pt_test_token",
    "work_dir": "/srv/jackpot/work",
}


# ───────────────────────── manifest + plumbing ─────────────────────────


def test_base_manifest_and_weblog_emit_for_local():
    rendered = render_nextflow_config(profile=_profile("LOCAL"), **_RENDER_KWARGS)
    assert "manifest {" in rendered
    assert "name = 'jp-sc2'" in rendered
    assert "version = '1.2.3'" in rendered
    assert "weblog {" in rendered
    assert "url = 'http://api.test/api/v1/pipelines/events'" in rendered
    assert "JACKPOT_RESULT_REGISTRATION_URL = " in rendered
    assert "JACKPOT_PIPELINE_TOKEN = 'pt_test_token'" in rendered
    assert "workDir = '/srv/jackpot/work/runs/jp-deadbeef/work'" in rendered


def test_plugins_block_includes_validation_and_iridanext():
    rendered = render_nextflow_config(profile=_profile("LOCAL"), **_RENDER_KWARGS)
    assert "id 'nf-validation'" in rendered
    assert "id 'nf-iridanext'" in rendered


# ───────────────────────── per-executor blocks ─────────────────────────


def test_local_renders_local_executor():
    rendered = render_nextflow_config(profile=_profile("LOCAL"), **_RENDER_KWARGS)
    assert "executor = 'local'" in rendered


def test_slurm_uses_overrides_and_cluster_options():
    profile = _profile(
        "SLURM",
        config_overrides={
            "queue": "gpu",
            "account": "mylab-2026",
            "qos": "premium",
            "time": "12:00:00",
            "cluster_options": "--nodes=2 --exclusive",
        },
    )
    rendered = render_nextflow_config(profile=profile, **_RENDER_KWARGS)
    assert "executor = 'slurm'" in rendered
    assert "queue = 'gpu'" in rendered
    assert "time = '12:00:00'" in rendered
    assert "--account=mylab-2026" in rendered
    assert "--qos=premium" in rendered
    assert "--nodes=2 --exclusive" in rendered


def test_slurm_defaults_when_overrides_absent():
    rendered = render_nextflow_config(profile=_profile("SLURM"), **_RENDER_KWARGS)
    assert "queue = 'normal'" in rendered
    assert "time = '1h'" in rendered
    # No account/qos/cluster_options → no clusterOptions line.
    assert "clusterOptions" not in rendered


def test_pbs_renders_walltime_and_account():
    profile = _profile(
        "PBS",
        config_overrides={
            "queue": "compute",
            "account": "mylab",
            "time": "04:00:00",
        },
    )
    rendered = render_nextflow_config(profile=profile, **_RENDER_KWARGS)
    assert "executor = 'pbs'" in rendered
    assert "queue = 'compute'" in rendered
    assert "-A mylab" in rendered
    assert "-l walltime=04:00:00" in rendered


def test_lsf_renders_project_and_wallclock():
    profile = _profile(
        "LSF",
        config_overrides={"project": "mylab-budget", "time": "8:00"},
    )
    rendered = render_nextflow_config(profile=profile, **_RENDER_KWARGS)
    assert "executor = 'lsf'" in rendered
    assert "queue = 'normal'" in rendered
    assert "-P mylab-budget" in rendered
    assert "-W 8:00" in rendered


def test_gcp_batch_renders_google_block_and_resource_labels():
    profile = _profile(
        "GCP_BATCH",
        config_overrides={
            "project": "jackpot-prod",
            "region": "us-east1",
            "service_account": "nf@jackpot-prod.iam.gserviceaccount.com",
            "boot_disk_size_gb": 100,
        },
    )
    rendered = render_nextflow_config(profile=profile, **_RENDER_KWARGS)
    assert "executor = 'google-batch'" in rendered
    assert "project = 'jackpot-prod'" in rendered
    assert "location = 'us-east1'" in rendered
    assert "batch.bootDiskSize = 100.GB" in rendered
    assert "batch.serviceAccountEmail = 'nf@jackpot-prod.iam.gserviceaccount.com'" in rendered
    # Critical Rule 27: resourceLabels must appear for GCP runs.
    assert "resourceLabels" in rendered
    assert "'jackpot_run_id': 'jp-deadbeef'" in rendered
    assert "'pipeline_name': 'jp-sc2'" in rendered


def test_aws_batch_renders_aws_block():
    profile = _profile(
        "AWS_BATCH",
        config_overrides={
            "region": "us-west-2",
            "queue": "jackpot-queue",
            "cli_path": "/home/ec2-user/aws/bin/aws",
        },
    )
    rendered = render_nextflow_config(profile=profile, **_RENDER_KWARGS)
    assert "executor = 'awsbatch'" in rendered
    assert "queue = 'jackpot-queue'" in rendered
    assert "region = 'us-west-2'" in rendered
    assert "batch.cliPath = '/home/ec2-user/aws/bin/aws'" in rendered


def test_kubernetes_renders_namespace_and_service_account():
    profile = _profile(
        "KUBERNETES",
        config_overrides={
            "namespace": "jackpot",
            "service_account": "nf-runner",
            "compute_resource_type": "Job",
            "pull_policy": "IfNotPresent",
        },
    )
    rendered = render_nextflow_config(profile=profile, **_RENDER_KWARGS)
    assert "executor = 'k8s'" in rendered
    assert "namespace = 'jackpot'" in rendered
    assert "serviceAccount = 'nf-runner'" in rendered
    assert "computeResourceType = 'Job'" in rendered
    assert "pullPolicy = 'IfNotPresent'" in rendered


# ───────────────────────── container engine variants ───────────────────


def test_docker_engine_enables_docker_disables_others():
    rendered = render_nextflow_config(
        profile=_profile("LOCAL", container_engine="DOCKER"), **_RENDER_KWARGS
    )
    assert "docker {\n    enabled = true" in rendered
    assert "apptainer {\n    enabled = false" in rendered
    assert "singularity {\n    enabled = false" in rendered


def test_apptainer_engine_enables_apptainer_disables_others():
    rendered = render_nextflow_config(
        profile=_profile("LOCAL", container_engine="APPTAINER"), **_RENDER_KWARGS
    )
    assert "apptainer {\n    enabled = true\n    autoMounts = true" in rendered
    assert "docker {\n    enabled = false" in rendered
    assert "singularity {\n    enabled = false" in rendered


def test_singularity_engine_enables_singularity_disables_others():
    rendered = render_nextflow_config(
        profile=_profile("LOCAL", container_engine="SINGULARITY"), **_RENDER_KWARGS
    )
    assert "singularity {\n    enabled = true\n    autoMounts = true" in rendered
    assert "docker {\n    enabled = false" in rendered
    assert "apptainer {\n    enabled = false" in rendered


def test_none_engine_omits_all_three_blocks():
    rendered = render_nextflow_config(
        profile=_profile("LOCAL", container_engine="NONE"), **_RENDER_KWARGS
    )
    # No engine blocks rendered when container_engine == NONE.
    assert "docker {" not in rendered
    assert "apptainer {" not in rendered
    assert "singularity {" not in rendered


# ───────────────────────── StrictUndefined ─────────────────────────────


def test_gcp_batch_missing_project_raises_undefined_error():
    # The GCP-Batch template references config_overrides.project as a
    # required key. StrictUndefined turns the missing-key access into a
    # loud failure at render time, not an empty string in the output.
    profile = _profile("GCP_BATCH", config_overrides={"region": "us-east1"})
    with pytest.raises(UndefinedError):
        render_nextflow_config(profile=profile, **_RENDER_KWARGS)


# ───────────────────────── write_run_config ────────────────────────────


# ─────────────── R-1 #1: executor_type allowlist enforcement ───────────────


def test_template_name_for_allowed_executors():
    """Every allowed value resolves to its expected template filename
    (case-insensitively, since ``ExecutorTypeEnum`` values arrive as
    upper-case strings from the DB)."""
    for et in _ALLOWED_EXECUTOR_TYPES:
        assert _template_name_for(et) == f"{et}.config.j2"
        assert _template_name_for(et.upper()) == f"{et}.config.j2"


def test_template_name_for_rejects_path_traversal():
    """Parent-directory references must not slip through to
    PackageLoader.get_template. Attempting traversal raises ValueError."""
    with pytest.raises(ValueError):
        _template_name_for("../etc/passwd")
    with pytest.raises(ValueError):
        _template_name_for("../../secrets")


def test_template_name_for_rejects_unknown():
    """An unknown executor name raises ValueError. The error message
    deliberately does not echo the rejected value verbatim so an
    attacker cannot probe what was tried."""
    with pytest.raises(ValueError) as exc_info:
        _template_name_for("nimbus")
    assert "nimbus" not in str(exc_info.value)


def test_template_name_for_rejects_empty():
    """Empty string is not in the allowlist; rejected."""
    with pytest.raises(ValueError):
        _template_name_for("")


def test_write_run_config_writes_local_path(tmp_path: Path):
    config_text = render_nextflow_config(profile=_profile("LOCAL"), **_RENDER_KWARGS)
    target = write_run_config(
        rendered_config=config_text,
        work_dir=str(tmp_path),
        run_id="jp-test-id",
    )
    expected = tmp_path / "runs" / "jp-test-id" / "jackpot_run.config"
    assert Path(target) == expected
    assert expected.read_text() == config_text


def test_write_run_config_creates_parent_dirs(tmp_path: Path):
    config_text = "// some rendered content\n"
    target = write_run_config(
        rendered_config=config_text,
        work_dir=str(tmp_path / "nested" / "wd"),
        run_id="jp-mkdir",
    )
    expected = tmp_path / "nested" / "wd" / "runs" / "jp-mkdir" / "jackpot_run.config"
    assert Path(target) == expected
    assert expected.read_text() == config_text
