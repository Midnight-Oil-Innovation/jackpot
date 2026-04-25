"""MLST / serotyping call — one row per sample."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TypingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(..., description="JACKPOT sample identifier.")
    scheme: str = Field(..., description="Typing scheme name (e.g. mlst_senterica, h1n1).")
    scheme_version: str | None = Field(None, description="Scheme version or database date.")
    sequence_type: str | None = Field(None, description="ST designation or subtype.")
    clade: str | None = Field(None, description="Clade / serotype / subtype where applicable.")
    allele_calls: dict | None = Field(None, description="Per-locus allele map.")
    tool_name: str = Field(..., description="Tool that produced the call.")
    tool_version: str | None = Field(None, description="Version string reported by the tool.")
