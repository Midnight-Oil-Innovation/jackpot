"""Pangolin SARS-CoV-2 lineage assignment — one row per sample."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PangolinResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(..., description="JACKPOT sample identifier.")
    lineage: str = Field(..., description="Assigned Pango lineage.")
    conflict: float | None = Field(None, ge=0, le=1)
    ambiguity_score: float | None = Field(None, ge=0, le=1)
    scorpio_call: str | None = None
    scorpio_support: float | None = Field(None, ge=0, le=1)
    scorpio_conflict: float | None = Field(None, ge=0, le=1)
    scorpio_notes: str | None = None
    pangolin_version: str = Field(..., description="Pangolin software version.")
    pangolin_data_version: str | None = Field(None, description="pangolin-data version.")
    scorpio_version: str | None = None
    constellation_version: str | None = None
    qc_status: str | None = Field(None, description="pass, fail, or fail with note.")
    qc_notes: str | None = None
    note: str | None = None
