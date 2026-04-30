"""Wastewater lineage abundance — one row per (sample, lineage)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WastewaterLineageAbundance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(..., description="JACKPOT wastewater sample identifier.")
    lineage: str = Field(..., description="Pango lineage deconvoluted by Freyja.")
    abundance: float = Field(..., ge=0, le=1, description="Estimated fraction in mixture.")
    confidence_interval_low: float | None = Field(None, ge=0, le=1)
    confidence_interval_high: float | None = Field(None, ge=0, le=1)
    coverage_depth: float | None = Field(None, ge=0)
    tool_name: str = Field(..., description="Deconvolution tool (e.g. freyja).")
    tool_version: str | None = None
    barcode_version: str | None = Field(None, description="Freyja barcode DB version.")
