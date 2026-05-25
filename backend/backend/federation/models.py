"""
Pydantic v2 models for federation.

Field shapes match the schema described in jackpot_architecture.md §22 and
in the session summary Q5. The DB tables (`federated_instances`, the new
org-level federation columns) are defined in the LinkML schema and emitted
via the standard regen pipeline (see scripts_jackpot/regen_schema.py); the
Pydantic models here are the API-layer wrappers used by routers, the push
job, and the federation client.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class FederationRole(str, Enum):
    """The role of a JACKPOT instance in a federation topology.

    HUB:  Aggregates de-identified pushes from spokes (Level 2). Hosts the
          federation directory. Typically a state or national instance.
    SPOKE: Pushes surveillance-relevant samples to a hub. Most lab-scale
           deployments are spokes.
    PEER: Bidirectional Level 1/3 only — no hub-and-spoke relationship.
          Peer-of-peer federations between equally-sized agencies.
    DATA_SOURCE_LAB: cryptWWDB three-party model (Driver et al. 2024 §4) —
           the Lab produces pipeline_results (concentration data) via
           X-Pipeline-Token auth but holds no samples of its own. Distinct
           from PEER because FederationClient queryable predicates filter
           data-holding peers from pipeline-producing labs. (B-CWB-FED-1)
    """

    HUB = "hub"
    SPOKE = "spoke"
    PEER = "peer"
    DATA_SOURCE_LAB = "data_source_lab"


class FederatedInstance(BaseModel):
    """A registered partner JACKPOT deployment.

    Maps to the `federated_instances` table. One row per registered partner.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str = Field(..., description="Human-readable name (e.g. 'Arizona DHS')")
    base_url: HttpUrl = Field(..., description="Root URL of the partner's JACKPOT API")
    role: FederationRole
    federation_enabled: bool = Field(
        default=True, description="Master switch — set False to silently drop without removal."
    )
    min_sharing_level_for_federation: str = Field(
        ...,
        description="Lowest sharing_level eligible for federation. "
        "DISCOVERABLE for L1, LAB for L2 push, etc.",
    )
    hub_instance_url: HttpUrl | None = Field(
        default=None, description="If this instance is a SPOKE, the hub it pushes to."
    )
    api_key_secret_name: str = Field(
        ...,
        description="Name of the GCP Secret Manager entry holding the federation "
        "API key. Never the key itself — keys never live in DB rows.",
    )
    last_seen_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class FederationQuery(BaseModel):
    """Outbound query sent from this instance to a partner.

    Maps onto the existing `GET /api/v1/samples/` filter surface but
    restricted to fields that are safe to broadcast.
    """

    organism: str | None = None
    date_collected_from: date | None = None
    date_collected_to: date | None = None
    country: str | None = None
    state: str | None = None
    source_type: str | None = None
    quality_tier_min: str | None = Field(
        default="ANALYZABLE",
        description="Default ANALYZABLE — no PRELIMINARY samples leak across "
        "federation boundaries.",
    )
    page: int = 1
    page_size: int = Field(default=50, le=200)


class FederationQueryResult(BaseModel):
    """A single result row returned from a federated query.

    DISCOVERABLE-equivalent. No clinical metadata, no file URLs, no PII.
    """

    sample_id: str
    organism: str
    date_collected: date
    country: str | None
    state: str | None
    source_type: str
    sector: str | None
    quality_tier: str
    surveillance_relevant: bool
    source_instance_id: UUID = Field(
        ...,
        description="Which FederatedInstance this row came from. Always set "
        "by the client — never trust the partner's claim.",
    )
    source_instance_name: str


class FederationPushPayload(BaseModel):
    """The Level 2 nightly push payload — surveillance-relevant samples only.

    What's in it: FASTA presigned URL (24h), typing results, AMR profiles,
    lineage, and the de-identified metadata subset.

    What's NOT in it: raw FASTQ, host_age (only host_age_range), host_sex,
    case_id, collection_facility, host_disease details, access request
    history. See jackpot_architecture.md §22 Level 2 for the full negative
    list.
    """

    sample_id: str
    organism: str
    date_collected: date
    country: str | None
    state: str | None
    source_type: str
    sector: str | None
    quality_tier: str
    surveillance_relevant: bool

    fasta_url: HttpUrl = Field(
        ..., description="Presigned URL, 24h expiry. Hub fetches and re-stores."
    )

    typing_results: dict[str, Any] = Field(
        default_factory=dict,
        description="MLST / cgMLST / HierCC / TB lineage results by typing scheme.",
    )
    amr_profile: dict[str, Any] = Field(
        default_factory=dict, description="hAMRonization-normalized AMR call set."
    )
    lineage: str | None = None
    clade: str | None = None

    host_age_range: str | None = Field(
        default=None, description="Decade bucket only — never host_age. AgeRangeEnum value."
    )

    originating_lab: str
    submitting_lab: str | None = None
    data_generator: str | None = None
    pushed_at: datetime


class FederationAccessRequest(BaseModel):
    """A Level 3 cross-instance access request.

    Glue between the existing internal `sample_access` workflow and the
    federation layer. The internal workflow handles approval; this model
    wraps it with the cross-instance attribution and the post-approval
    file copy mechanics.
    """

    request_id: UUID
    requesting_instance_id: UUID
    requesting_user_email: str
    target_sample_id: str
    target_instance_id: UUID
    purpose: str = Field(..., description="Free-text purpose of access. Audited.")
    duo_codes: list[str] = Field(
        default_factory=list,
        description="GA4GH DUO codes asserted by the requester. Validated "
        "against the target sample's data_use_terms.",
    )
    requested_at: datetime
    status: str = Field(
        default="PENDING",
        description="PENDING / APPROVED / DENIED / EXPIRED. Mirrors internal "
        "sample_access workflow states.",
    )
    approved_at: datetime | None = None
    denied_at: datetime | None = None
    expires_at: datetime | None = None
