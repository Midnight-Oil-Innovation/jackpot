"""P0g G-1 — Pydantic model validation for execution-profile classes.

Exercises the LinkML-generated Pydantic models for ``ExecutionProfile``
and ``PipelineDefaultProfile`` plus the two new enums. These tests
intentionally do not touch the database; they pin the model surface so
later G-N work (renderer, launcher, CLI) can rely on it.
"""

from __future__ import annotations

import datetime
from typing import Any

import pytest
from pydantic import ValidationError

from backend.models_generated import (
    ContainerEngineEnum,
    ExecutionProfile,
    ExecutorTypeEnum,
    PipelineDefaultProfile,
)


def _profile_kwargs(**overrides: Any) -> dict[str, Any]:
    """Minimal valid kwargs for ExecutionProfile; tests override a single field."""
    base: dict[str, Any] = dict(
        profile_id="00000000-0000-0000-0000-000000000001",
        name="default-local",
        executor_type=ExecutorTypeEnum.LOCAL,
        container_engine=ContainerEngineEnum.DOCKER,
        work_dir="/srv/jackpot/work",
        created_by_id=1,
        created_at=datetime.datetime(2026, 5, 4, 12, 0, 0),
    )
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    "executor",
    [
        ExecutorTypeEnum.LOCAL,
        ExecutorTypeEnum.SLURM,
        ExecutorTypeEnum.PBS,
        ExecutorTypeEnum.LSF,
        ExecutorTypeEnum.GCP_BATCH,
        ExecutorTypeEnum.AWS_BATCH,
        ExecutorTypeEnum.KUBERNETES,
    ],
)
def test_execution_profile_accepts_every_executor_type(executor):
    p = ExecutionProfile(**_profile_kwargs(executor_type=executor))
    # use_enum_values=True on ConfiguredBaseModel coerces enums to their str values.
    assert p.executor_type == executor.value


@pytest.mark.parametrize(
    "engine",
    [
        ContainerEngineEnum.DOCKER,
        ContainerEngineEnum.APPTAINER,
        ContainerEngineEnum.SINGULARITY,
        ContainerEngineEnum.NONE,
    ],
)
def test_execution_profile_accepts_every_container_engine(engine):
    p = ExecutionProfile(**_profile_kwargs(container_engine=engine))
    assert p.container_engine == engine.value


def test_execution_profile_rejects_unknown_executor_type():
    with pytest.raises(ValidationError):
        ExecutionProfile(**_profile_kwargs(executor_type="MESOS"))


def test_execution_profile_rejects_unknown_container_engine():
    with pytest.raises(ValidationError):
        ExecutionProfile(**_profile_kwargs(container_engine="PODMAN"))


def test_execution_profile_defaults_match_db_defaults():
    """is_default defaults to False; active defaults to True;
    config_overrides defaults to '{}'. These must agree with the
    DEFAULT clauses in the G-2 migration."""
    p = ExecutionProfile(**_profile_kwargs())
    assert p.is_default is False
    assert p.active is True
    assert p.config_overrides == "{}"


def test_execution_profile_required_fields_are_required():
    # Missing name — should reject.
    kwargs = _profile_kwargs()
    kwargs.pop("name")
    with pytest.raises(ValidationError):
        ExecutionProfile(**kwargs)


def test_pipeline_default_profile_accepts_valid_input():
    a = PipelineDefaultProfile(
        pipeline_id="aaaaaaaa-1111-2222-3333-cccccccccccc",
        profile_id="00000000-0000-0000-0000-000000000001",
        priority=1,
    )
    assert a.priority == 1


def test_pipeline_default_profile_priority_defaults_to_100():
    # Pyright sees `priority: int = Field(100, ...)` as a required positional
    # because the LinkML generator emits required=True on slots even when
    # ifabsent supplies a default. The runtime default is applied by Pydantic.
    a = PipelineDefaultProfile(  # pyright: ignore[reportCallIssue]
        pipeline_id="aaaaaaaa-1111-2222-3333-cccccccccccc",
        profile_id="00000000-0000-0000-0000-000000000001",
    )
    assert a.priority == 100


def test_pipeline_default_profile_required_fields_are_required():
    with pytest.raises(ValidationError):
        PipelineDefaultProfile(  # pyright: ignore[reportCallIssue]
            profile_id="00000000-0000-0000-0000-000000000001"
        )
    with pytest.raises(ValidationError):
        PipelineDefaultProfile(  # pyright: ignore[reportCallIssue]
            pipeline_id="aaaaaaaa-1111-2222-3333-cccccccccccc"
        )


def test_executor_type_enum_member_set():
    assert {e.value for e in ExecutorTypeEnum} == {
        "LOCAL",
        "SLURM",
        "PBS",
        "LSF",
        "GCP_BATCH",
        "AWS_BATCH",
        "KUBERNETES",
    }


def test_container_engine_enum_member_set():
    assert {e.value for e in ContainerEngineEnum} == {
        "DOCKER",
        "APPTAINER",
        "SINGULARITY",
        "NONE",
    }
