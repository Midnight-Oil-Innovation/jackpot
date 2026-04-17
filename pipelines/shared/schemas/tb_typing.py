"""Mycobacterium tuberculosis lineage + drug resistance — one row per sample."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TBTypingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(..., description="JACKPOT sample identifier.")
    main_lineage: str | None = Field(None, description="TB-Profiler main lineage.")
    sub_lineage: str | None = Field(None, description="TB-Profiler sub-lineage.")
    spoligotype: str | None = Field(None, description="Spoligotype octal code.")
    drug_resistance_profile: str | None = Field(
        None,
        description="Summary profile (e.g. MDR, XDR, sensitive).",
    )
    who_drug_susceptibility: dict | None = Field(
        None,
        description=(
            "Per-drug susceptibility map from the WHO catalogue, "
            "including predicted phenotype and supporting variants."
        ),
    )
    tbprofiler_version: str = Field(..., description="TB-Profiler software version.")
    tbprofiler_db_version: str | None = Field(None, description="TB-Profiler DB release.")
