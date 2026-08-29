# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""BYOP pipeline CRUD + lifecycle endpoints (P0f B-BYOP-4).

API surface from ``docs/byop_and_eukaryotic_design.md`` §8, mounted at
``/api/v1/byop``:

* ``POST   /pipelines``                 — register (Stage 1 then Stage 2 gate)
* ``GET    /pipelines``                 — list, filterable by status/engine
* ``GET    /pipelines/{id}``            — pipeline details
* ``PATCH``/``PUT`` ``/pipelines/{id}`` — update; re-gates when the manifest changes
* ``POST   /pipelines/{id}/revalidate`` — re-run Stage 1 + Stage 2 on stored manifest
* ``POST   /pipelines/{id}/deactivate`` — move to DEACTIVATED (§6)
* ``DELETE /pipelines/{id}``            — move to ARCHIVED, no hard delete (§8)
* ``POST   /pipelines/{id}/archive``    — same ARCHIVED transition, explicit verb

Write paths call B-BYOP-2 (``services.byop_validator.validate_manifest``)
then B-BYOP-3 (``services.byop_sandbox.run_sandbox``) in that order; a
failing stage returns 422 and nothing reaches the database. Failed
*re*-validation moves the pipeline to DEACTIVATED per §5.4/§6.

The SQLAlchemy ORM model and Pydantic schemas live in this module so the
tests can exercise every branch against in-memory SQLite (mirrors
``routers/profiles.py``).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from backend.auth.guards import get_current_user
from backend.database import get_db_dep
from backend.services.byop_sandbox import (
    OUTCOME_PASSED,
    TEST_DATA_DIR,
    run_sandbox,
)
from backend.services.byop_validator import validate_manifest

MANIFEST_SCHEMA_PATH = Path("schema/byop-pipeline-manifest.schema.json")

# §5.2e — operator license policy, overridable per deployment.
DEFAULT_ALLOWED_LICENSES = {
    "MIT",
    "Apache-2.0",
    "BSD-3-Clause",
    "GPL-3.0-or-later",
    "AGPL-3.0-or-later",
}

SOURCE_TYPES = {"git", "git_private", "tarball", "docker"}

# §6 lifecycle — states each transition is legal from.
DEACTIVATABLE_STATES = {"ACTIVE"}
ARCHIVABLE_STATES = {"ACTIVE", "DEACTIVATED"}


class Base(DeclarativeBase):
    """BYOP-router-local declarative base (SQLite test harness support)."""


class ByopPipeline(Base):
    __tablename__ = "byop_pipelines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    engine_type: Mapped[str] = mapped_column(String(32))
    engine_version: Mapped[str] = mapped_column(String(64))
    source_type: Mapped[str] = mapped_column(String(32))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_uploaded_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    docker_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    docker_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    manifest_yaml: Mapped[str] = mapped_column(Text)
    pipeline_status: Mapped[str] = mapped_column(String(32), default="SUBMITTED")
    validation_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    sandbox_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    registered_by_user_id: Mapped[str] = mapped_column(String(36))
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    license_spdx: Mapped[str] = mapped_column(String(64))
    citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_estimate_usd: Mapped[float | None] = mapped_column(Float, nullable=True)


class ByopPipelineCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_type: str = Field(...)
    source_url: str | None = None
    source_ref: str | None = None
    source_uploaded_uri: str | None = None
    source_sha256: str | None = None
    docker_image: str | None = None
    docker_digest: str | None = None
    manifest_yaml: str = Field(..., min_length=1)


class ByopPipelineUpdate(BaseModel):
    """§8 — update only certain fields; a new manifest re-runs both gates."""

    model_config = ConfigDict(from_attributes=True)

    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    manifest_yaml: str | None = Field(default=None, min_length=1)


class ByopPipelineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    display_name: str
    version: str
    description: str | None = None
    engine_type: str
    engine_version: str
    source_type: str
    source_url: str | None = None
    source_ref: str | None = None
    source_uploaded_uri: str | None = None
    source_sha256: str | None = None
    docker_image: str | None = None
    docker_digest: str | None = None
    manifest_yaml: str
    pipeline_status: str
    validation_log: str | None = None
    sandbox_log: str | None = None
    registered_by_user_id: str
    registered_at: datetime
    activated_at: datetime | None = None
    deactivated_at: datetime | None = None
    last_validated_at: datetime | None = None
    license_spdx: str
    citation: str | None = None
    cost_estimate_usd: float | None = None


router = APIRouter(prefix="/api/v1/byop", tags=["byop"])


def _now() -> datetime:
    return datetime.now(UTC)


def _env_set(var: str, default: set[str]) -> set[str]:
    raw = os.environ.get(var, "")
    return {item.strip() for item in raw.split(",") if item.strip()} or default


def _parse_manifest(manifest_yaml: str) -> dict:
    try:
        manifest = yaml.safe_load(manifest_yaml)
    except yaml.YAMLError as exc:
        raise HTTPException(
            status_code=422, detail=f"manifest_yaml is not valid YAML: {exc}"
        ) from exc
    if not isinstance(manifest, dict):
        raise HTTPException(status_code=422, detail="manifest_yaml must be a YAML mapping.")
    return manifest


def _run_stage1(manifest: dict):
    """B-BYOP-2 static validation with operator policy from the environment."""
    schema = json.loads(MANIFEST_SCHEMA_PATH.read_text())
    # ponytail: reference/permission grants come from flat env vars until an
    # operator-policy table lands; move to DB config when one exists.
    available_references = _env_set("JACKPOT_BYOP_AVAILABLE_REFERENCES", set())
    allowed_licenses = _env_set("JACKPOT_BYOP_ALLOWED_LICENSES", DEFAULT_ALLOWED_LICENSES)
    operator_permissions = _env_set("JACKPOT_BYOP_GRANTED_PERMISSIONS", {"read_metadata"})
    return validate_manifest(
        manifest, schema, available_references, allowed_licenses, operator_permissions
    )


def _run_stage2(pipeline_key: str, manifest: dict):
    """B-BYOP-3 sandbox dry-run against the manifest's declared runtime."""
    containers = manifest.get("containers") or [{}]
    engine = manifest.get("engine") or {}
    return run_sandbox(
        pipeline_id=pipeline_key,
        image=str(containers[0].get("image", "")),
        engine_type=str(engine.get("type", "")),
        entrypoint=str(engine.get("entrypoint", "")),
        sandbox_dir=str(TEST_DATA_DIR),
        isolation=os.environ.get("JACKPOT_BYOP_SANDBOX_ISOLATION", "docker"),
    )


def _gate(pipeline_key: str, manifest: dict) -> tuple[str, str]:
    """Run Stage 1 then Stage 2; 422 on failure. Returns (validation_log, sandbox_log)."""
    report = _run_stage1(manifest)
    validation_log = "\n".join(
        f"[{'PASS' if c.passed else 'FAIL'}] {c.check_name}: {c.message}" for c in report.checks
    )
    if not report.passed:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "VALIDATION_FAILED",
                "failed_checks": [
                    {"check_name": c.check_name, "message": c.message}
                    for c in report.checks
                    if not c.passed
                ],
            },
        )

    sandbox = _run_stage2(pipeline_key, manifest)
    if sandbox.outcome != OUTCOME_PASSED:
        raise HTTPException(
            status_code=422,
            detail={
                "error": sandbox.outcome,
                "failed_steps": [
                    {"step_name": s.step_name, "message": s.message}
                    for s in sandbox.steps
                    if not s.passed
                ],
            },
        )
    return validation_log, sandbox.sandbox_log


def _apply_manifest_fields(pipeline: ByopPipeline, manifest: dict) -> None:
    metadata = manifest.get("metadata") or {}
    engine = manifest.get("engine") or {}
    containers = manifest.get("containers") or [{}]
    cost = manifest.get("cost") or {}
    pipeline.name = str(metadata.get("name", ""))
    pipeline.display_name = str(metadata.get("display_name", ""))
    pipeline.version = str(metadata.get("version", ""))
    pipeline.description = metadata.get("description")
    pipeline.engine_type = str(engine.get("type", ""))
    pipeline.engine_version = str(engine.get("version", ""))
    pipeline.license_spdx = str(metadata.get("license", ""))
    pipeline.citation = metadata.get("citation")
    pipeline.cost_estimate_usd = cost.get("estimated_total_per_sample_usd")
    if containers[0].get("image"):
        pipeline.docker_image = str(containers[0]["image"])
    if containers[0].get("digest"):
        pipeline.docker_digest = str(containers[0]["digest"])


def _get_or_404(db: Session, pipeline_id: int) -> ByopPipeline:
    pipeline = db.get(ByopPipeline, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail=f"BYOP pipeline {pipeline_id} not found.")
    return pipeline


@router.post("/pipelines", response_model=ByopPipelineRead, status_code=status.HTTP_201_CREATED)
def create_pipeline(
    payload: ByopPipelineCreate,
    db: Annotated[Session, Depends(get_db_dep)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ByopPipeline:
    if payload.source_type not in SOURCE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"source_type must be one of {sorted(SOURCE_TYPES)}.",
        )
    manifest = _parse_manifest(payload.manifest_yaml)
    metadata = manifest.get("metadata") or {}
    pipeline_key = f"{metadata.get('name', 'unnamed')}-{metadata.get('version', '0')}"
    validation_log, sandbox_log = _gate(pipeline_key, manifest)

    now = _now()
    pipeline = ByopPipeline(
        source_type=payload.source_type,
        source_url=payload.source_url,
        source_ref=payload.source_ref,
        source_uploaded_uri=payload.source_uploaded_uri,
        source_sha256=payload.source_sha256,
        docker_image=payload.docker_image,
        docker_digest=payload.docker_digest,
        manifest_yaml=payload.manifest_yaml,
        pipeline_status="ACTIVE",
        validation_log=validation_log,
        sandbox_log=sandbox_log,
        registered_by_user_id=str(current_user["id"]),
        registered_at=now,
        activated_at=now,
        last_validated_at=now,
    )
    _apply_manifest_fields(pipeline, manifest)
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)
    return pipeline


@router.get("/pipelines", response_model=list[ByopPipelineRead])
def list_pipelines(
    db: Annotated[Session, Depends(get_db_dep)],
    current_user: Annotated[dict, Depends(get_current_user)],
    pipeline_status: str | None = None,
    engine_type: str | None = None,
) -> list[ByopPipeline]:
    query = db.query(ByopPipeline)
    if pipeline_status is not None:
        query = query.filter(ByopPipeline.pipeline_status == pipeline_status)
    if engine_type is not None:
        query = query.filter(ByopPipeline.engine_type == engine_type)
    return query.order_by(ByopPipeline.id).all()


@router.get("/pipelines/{pipeline_id}", response_model=ByopPipelineRead)
def get_pipeline(
    pipeline_id: int,
    db: Annotated[Session, Depends(get_db_dep)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ByopPipeline:
    return _get_or_404(db, pipeline_id)


@router.patch("/pipelines/{pipeline_id}", response_model=ByopPipelineRead)
@router.put("/pipelines/{pipeline_id}", response_model=ByopPipelineRead)
def update_pipeline(
    pipeline_id: int,
    payload: ByopPipelineUpdate,
    db: Annotated[Session, Depends(get_db_dep)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ByopPipeline:
    pipeline = _get_or_404(db, pipeline_id)
    if pipeline.pipeline_status == "ARCHIVED":
        raise HTTPException(status_code=409, detail="Archived pipelines are immutable.")

    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    if "manifest_yaml" in updates:
        manifest = _parse_manifest(updates["manifest_yaml"])
        pipeline_key = f"byop-{pipeline.id}"
        validation_log, sandbox_log = _gate(pipeline_key, manifest)
        pipeline.manifest_yaml = updates["manifest_yaml"]
        _apply_manifest_fields(pipeline, manifest)
        pipeline.validation_log = validation_log
        pipeline.sandbox_log = sandbox_log
        pipeline.last_validated_at = _now()
        pipeline.pipeline_status = "ACTIVE"
        pipeline.activated_at = pipeline.activated_at or _now()

    if "display_name" in updates:
        pipeline.display_name = updates["display_name"]
    if "description" in updates:
        pipeline.description = updates["description"]

    db.commit()
    db.refresh(pipeline)
    return pipeline


@router.delete("/pipelines/{pipeline_id}", response_model=ByopPipelineRead)
def delete_pipeline(
    pipeline_id: int,
    db: Annotated[Session, Depends(get_db_dep)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ByopPipeline:
    """§8 — DELETE moves to ARCHIVED; there is no hard delete."""
    pipeline = _get_or_404(db, pipeline_id)
    if pipeline.pipeline_status == "ARCHIVED":
        raise HTTPException(status_code=409, detail="Pipeline is already archived.")
    pipeline.pipeline_status = "ARCHIVED"
    db.commit()
    db.refresh(pipeline)
    return pipeline


@router.post("/pipelines/{pipeline_id}/revalidate", response_model=ByopPipelineRead)
def revalidate_pipeline(
    pipeline_id: int,
    db: Annotated[Session, Depends(get_db_dep)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ByopPipeline:
    """§5.4 — re-run both stages on the stored manifest.

    Failure does not 422: per the design doc, failed re-validation
    transitions the pipeline to DEACTIVATED and the row records why.
    """
    pipeline = _get_or_404(db, pipeline_id)
    if pipeline.pipeline_status == "ARCHIVED":
        raise HTTPException(status_code=409, detail="Archived pipelines cannot be revalidated.")

    manifest = _parse_manifest(pipeline.manifest_yaml)
    pipeline_key = f"byop-{pipeline.id}"
    now = _now()

    report = _run_stage1(manifest)
    pipeline.validation_log = "\n".join(
        f"[{'PASS' if c.passed else 'FAIL'}] {c.check_name}: {c.message}" for c in report.checks
    )
    if not report.passed:
        pipeline.pipeline_status = "DEACTIVATED"
        pipeline.deactivated_at = now
    else:
        sandbox = _run_stage2(pipeline_key, manifest)
        pipeline.sandbox_log = sandbox.sandbox_log
        if sandbox.outcome != OUTCOME_PASSED:
            pipeline.pipeline_status = "DEACTIVATED"
            pipeline.deactivated_at = now
        else:
            pipeline.pipeline_status = "ACTIVE"
            pipeline.activated_at = pipeline.activated_at or now
            pipeline.last_validated_at = now

    db.commit()
    db.refresh(pipeline)
    return pipeline


@router.post("/pipelines/{pipeline_id}/deactivate", response_model=ByopPipelineRead)
def deactivate_pipeline(
    pipeline_id: int,
    db: Annotated[Session, Depends(get_db_dep)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ByopPipeline:
    pipeline = _get_or_404(db, pipeline_id)
    if pipeline.pipeline_status not in DEACTIVATABLE_STATES:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot deactivate a pipeline in state {pipeline.pipeline_status}.",
        )
    pipeline.pipeline_status = "DEACTIVATED"
    pipeline.deactivated_at = _now()
    db.commit()
    db.refresh(pipeline)
    return pipeline


@router.post("/pipelines/{pipeline_id}/archive", response_model=ByopPipelineRead)
def archive_pipeline(
    pipeline_id: int,
    db: Annotated[Session, Depends(get_db_dep)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ByopPipeline:
    pipeline = _get_or_404(db, pipeline_id)
    if pipeline.pipeline_status not in ARCHIVABLE_STATES:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot archive a pipeline in state {pipeline.pipeline_status}.",
        )
    pipeline.pipeline_status = "ARCHIVED"
    db.commit()
    db.refresh(pipeline)
    return pipeline
