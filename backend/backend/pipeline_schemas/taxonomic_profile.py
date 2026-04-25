"""Taxonomic classification — one row per (sample, taxon)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TaxonomicProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(..., description="JACKPOT sample identifier.")
    taxon_id: str = Field(..., description="Taxon identifier (e.g. NCBI taxid).")
    taxon_name: str | None = Field(None, description="Human-readable taxon name.")
    rank: str | None = Field(None, description="Taxonomic rank (species, genus, ...).")
    lineage: str | None = Field(None, description="Semicolon-separated full lineage.")
    abundance_percent: float | None = Field(None, ge=0, le=100)
    read_count: int | None = Field(None, ge=0)
    reference_database: str | None = Field(
        None,
        description="e.g. kraken2_standard, GTDB, RefSeq.",
    )
    tool_name: str = Field(..., description="Classifier (kraken2, bracken, sendsketch, gtdbtk).")
    tool_version: str | None = None
