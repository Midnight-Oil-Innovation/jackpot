"""Nextclade clade / QC call — one row per sample."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class NextcladeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(..., description="JACKPOT sample identifier.")
    clade: str | None = Field(None, description="Assigned clade.")
    nextclade_pango: str | None = Field(None, description="Nextclade's pango call.")
    qc_overall_status: str | None = Field(None, description="good | mediocre | bad | fail.")
    qc_overall_score: float | None = None
    total_substitutions: int | None = Field(None, ge=0)
    total_deletions: int | None = Field(None, ge=0)
    total_insertions: int | None = Field(None, ge=0)
    total_missing: int | None = Field(None, ge=0)
    total_non_acgtns: int | None = Field(None, ge=0)
    total_frame_shifts: int | None = Field(None, ge=0)
    substitutions: list[str] | None = None
    aa_substitutions: list[str] | None = None
    nextclade_version: str = Field(..., description="Nextclade software version.")
    dataset_name: str | None = Field(None, description="Reference dataset used.")
    dataset_version: str | None = None
