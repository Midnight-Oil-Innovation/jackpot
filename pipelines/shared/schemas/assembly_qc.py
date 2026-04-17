"""Assembly quality metrics — one row per sample."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AssemblyQC(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(..., description="JACKPOT sample identifier.")
    total_length: int | None = Field(None, ge=0, description="Total assembly length in bp.")
    num_contigs: int | None = Field(None, ge=0)
    largest_contig: int | None = Field(None, ge=0)
    n50: int | None = Field(None, ge=0)
    l50: int | None = Field(None, ge=0)
    gc_percent: float | None = Field(None, ge=0, le=100)
    n_count: int | None = Field(None, ge=0, description="Total N bases in assembly.")
    coverage_depth: float | None = Field(None, ge=0)
    genome_completeness: float | None = Field(None, ge=0, le=100)
    contamination_percent: float | None = Field(None, ge=0, le=100)
    assembly_method: str | None = Field(None, description="Assembler / workflow name.")
    tool_name: str = Field(..., description="QC tool (e.g. QUAST, CheckM2).")
    tool_version: str | None = None
