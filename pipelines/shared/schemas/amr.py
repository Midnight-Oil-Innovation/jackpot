"""Antimicrobial resistance hit — one row per detected gene per sample."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AMRResult(BaseModel):
    """Canonical AMR gene hit, produced by the hAMRonization normalizer."""

    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(..., description="JACKPOT sample identifier.")
    gene_symbol: str = Field(..., description="Normalized gene or allele symbol.")
    gene_name: str | None = Field(None, description="Full gene name if available.")
    drug_class: str | None = Field(None, description="Targeted antibiotic drug class.")
    drug: str | None = Field(None, description="Specific drug when narrower than class.")
    resistance_phenotype: str | None = Field(None, description="Predicted phenotype.")
    coverage_percent: float | None = Field(None, ge=0, le=100)
    identity_percent: float | None = Field(None, ge=0, le=100)
    reference_database: str | None = Field(
        None,
        description="e.g. NCBI, CARD, ResFinder, WHO_catalogue.",
    )
    reference_accession: str | None = Field(None, description="Hit accession in the DB.")
    contig_id: str | None = Field(None, description="Contig on which the hit was found.")
    start_pos: int | None = Field(None, ge=0)
    end_pos: int | None = Field(None, ge=0)
    strand: str | None = Field(None, description="+ or -.")
    tool_name: str = Field(
        ...,
        description="Tool that produced the call (amrfinderplus, rgi, etc.).",
    )
    tool_version: str | None = Field(None, description="Version string reported by the tool.")
