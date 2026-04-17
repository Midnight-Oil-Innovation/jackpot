"""Metagenome-assembled genome QC — one row per MAG bin."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MAGQC(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(..., description="Parent metagenomic sample ID.")
    bin_id: str = Field(..., description="Unique MAG bin identifier within the run.")
    completeness_percent: float | None = Field(None, ge=0, le=100)
    contamination_percent: float | None = Field(None, ge=0, le=100)
    strain_heterogeneity: float | None = Field(None, ge=0, le=100)
    bin_size_bp: int | None = Field(None, ge=0)
    num_contigs: int | None = Field(None, ge=0)
    n50: int | None = Field(None, ge=0)
    gc_percent: float | None = Field(None, ge=0, le=100)
    taxonomy: str | None = Field(
        None,
        description="GTDB-Tk or classifier-assigned taxonomy for the bin.",
    )
    tool_name: str = Field(..., description="Tool producing QC (e.g. CheckM2, GUNC).")
    tool_version: str | None = None
