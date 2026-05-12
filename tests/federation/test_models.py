# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Pydantic model tests for the federation package (FED-C).

Covers `FederatedInstance`, `FederationQuery`, `FederationQueryResult`,
`FederationPushPayload`, `FederationAccessRequest`, and the `FederationRole`
enum. Includes a negative-list check: `FederationPushPayload` must reject
payloads that try to smuggle host_age, raw FASTQ refs, or other known PII
fields through the API-layer model.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.federation.models import (
    FederatedInstance,
    FederationAccessRequest,
    FederationPushPayload,
    FederationQuery,
    FederationQueryResult,
    FederationRole,
)

# ---------------------------------------------------------------------------
# FederationRole
# ---------------------------------------------------------------------------


def test_federation_role_has_all_three_values() -> None:
    assert FederationRole.HUB.value == "hub"
    assert FederationRole.SPOKE.value == "spoke"
    assert FederationRole.PEER.value == "peer"
    assert {r.value for r in FederationRole} == {"hub", "spoke", "peer"}


def test_federation_role_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        FederationRole("not-a-role")


# ---------------------------------------------------------------------------
# FederatedInstance
# ---------------------------------------------------------------------------


def _instance_kwargs(**overrides):
    base = {
        "id": uuid4(),
        "name": "Arizona DHS",
        "base_url": "https://az.example.test/",
        "role": FederationRole.PEER,
        "federation_enabled": True,
        "min_sharing_level_for_federation": "DISCOVERABLE",
        "hub_instance_url": None,
        "api_key_secret_name": "fed/az-dhs/key",
        "last_seen_at": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return base


def test_federated_instance_happy_path() -> None:
    inst = FederatedInstance(**_instance_kwargs())
    assert inst.name == "Arizona DHS"
    assert inst.role is FederationRole.PEER
    assert inst.federation_enabled is True
    assert str(inst.base_url).startswith("https://az.example.test")


def test_federated_instance_rejects_missing_required_field() -> None:
    kwargs = _instance_kwargs()
    kwargs.pop("name")
    with pytest.raises(ValidationError):
        FederatedInstance(**kwargs)


def test_federated_instance_rejects_bad_url() -> None:
    with pytest.raises(ValidationError):
        FederatedInstance(**_instance_kwargs(base_url="not-a-url"))


def test_federated_instance_role_accepts_string_alias() -> None:
    inst = FederatedInstance(**_instance_kwargs(role="hub"))
    assert inst.role is FederationRole.HUB


# ---------------------------------------------------------------------------
# FederationQuery
# ---------------------------------------------------------------------------


def test_federation_query_defaults() -> None:
    q = FederationQuery()
    assert q.page == 1
    assert q.page_size == 50
    assert q.quality_tier_min == "ANALYZABLE"
    assert q.organism is None


def test_federation_query_caps_page_size() -> None:
    with pytest.raises(ValidationError):
        FederationQuery(page_size=500)


def test_federation_query_accepts_filters() -> None:
    q = FederationQuery(
        organism="SARS-CoV-2",
        date_collected_from=date(2026, 1, 1),
        date_collected_to=date(2026, 3, 31),
        country="US",
        state="AZ",
        source_type="clinical",
        page=2,
        page_size=25,
    )
    assert q.organism == "SARS-CoV-2"
    assert q.page == 2


# ---------------------------------------------------------------------------
# FederationQueryResult
# ---------------------------------------------------------------------------


def _query_result_kwargs(**overrides):
    base = {
        "sample_id": "AZ-001",
        "organism": "SARS-CoV-2",
        "date_collected": date(2026, 1, 15),
        "country": "US",
        "state": "AZ",
        "source_type": "clinical",
        "sector": "clinical",
        "quality_tier": "ANALYZABLE",
        "surveillance_relevant": True,
        "source_instance_id": uuid4(),
        "source_instance_name": "Arizona DHS",
    }
    base.update(overrides)
    return base


def test_federation_query_result_happy_path() -> None:
    r = FederationQueryResult(**_query_result_kwargs())
    assert r.sample_id == "AZ-001"
    assert r.source_instance_name == "Arizona DHS"


def test_federation_query_result_requires_source_attribution() -> None:
    kwargs = _query_result_kwargs()
    kwargs.pop("source_instance_id")
    with pytest.raises(ValidationError):
        FederationQueryResult(**kwargs)


# ---------------------------------------------------------------------------
# FederationPushPayload — positive
# ---------------------------------------------------------------------------


def _push_kwargs(**overrides):
    base = {
        "sample_id": "AZ-001",
        "organism": "SARS-CoV-2",
        "date_collected": date(2026, 1, 15),
        "country": "US",
        "state": "AZ",
        "source_type": "clinical",
        "sector": "clinical",
        "quality_tier": "ANALYZABLE",
        "surveillance_relevant": True,
        "fasta_url": "https://signed.example.test/fasta/AZ-001.fasta?token=abc",
        "typing_results": {"mlst": "ST-1"},
        "amr_profile": {"blaKPC": "present"},
        "lineage": "BA.2.86",
        "clade": "23I",
        "host_age_range": "30-39",
        "originating_lab": "Arizona DHS Lab",
        "submitting_lab": "Arizona DHS Lab",
        "data_generator": "Arizona DHS Lab",
        "pushed_at": datetime.now(UTC),
    }
    base.update(overrides)
    return base


def test_federation_push_payload_happy_path() -> None:
    p = FederationPushPayload(**_push_kwargs())
    assert p.sample_id == "AZ-001"
    assert p.host_age_range == "30-39"
    assert str(p.fasta_url).startswith("https://signed.example.test")


def test_federation_push_payload_rejects_missing_originating_lab() -> None:
    kwargs = _push_kwargs()
    kwargs.pop("originating_lab")
    with pytest.raises(ValidationError):
        FederationPushPayload(**kwargs)


def test_federation_push_payload_rejects_bad_fasta_url() -> None:
    with pytest.raises(ValidationError):
        FederationPushPayload(**_push_kwargs(fasta_url="not-a-url"))


# ---------------------------------------------------------------------------
# FederationPushPayload — negative-list (PII / raw-data smuggling defense)
#
# These are the fields jackpot_architecture.md §22 Level 2 lists as forbidden.
# Pydantic v2 defaults to ``extra="ignore"`` for BaseModel — these fields
# round-trip silently dropped, NOT propagated into the serialized payload.
# That's the contract the test enforces: even if a careless caller passes a
# raw_fastq_url or host_age, the wire payload never contains it.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "forbidden_field,value",
    [
        ("host_age", 47),
        ("host_sex", "M"),
        ("case_id", "CASE-2026-001"),
        ("collection_facility", "Example Hospital"),
        ("host_disease", ["covid-19"]),
        ("fastq_r1_uri", "gs://jackpot-sequences/example/R1.fastq.gz"),
        ("fastq_r2_uri", "gs://jackpot-sequences/example/R2.fastq.gz"),
        ("raw_fastq_url", "gs://jackpot-sequences/example/R1.fastq.gz"),
        ("external_case_id", "CASE-2026-001"),
    ],
)
def test_federation_push_payload_strips_forbidden_fields(forbidden_field: str, value) -> None:
    """Even if a caller sneaks a forbidden field in, the serialized payload
    must not contain it. Pydantic's default `extra="ignore"` is the line
    of defense; this test pins that contract."""
    payload = FederationPushPayload(**_push_kwargs(**{forbidden_field: value}))
    dumped = payload.model_dump()
    assert forbidden_field not in dumped, (
        f"forbidden field {forbidden_field!r} leaked into serialized payload"
    )
    # And the legal `host_age_range` (decade bucket) is the only host-age
    # signal that should survive.
    assert "host_age_range" in dumped


# ---------------------------------------------------------------------------
# FederationAccessRequest
# ---------------------------------------------------------------------------


def _access_kwargs(**overrides):
    base = {
        "request_id": uuid4(),
        "requesting_instance_id": uuid4(),
        "requesting_user_email": "alice@orgb.example.test",
        "target_sample_id": "AZ-001",
        "target_instance_id": uuid4(),
        "purpose": "Outbreak investigation 2026-Q1",
        "duo_codes": ["DUO:0000004"],
        "requested_at": datetime.now(UTC),
        "status": "PENDING",
    }
    base.update(overrides)
    return base


def test_federation_access_request_happy_path() -> None:
    r = FederationAccessRequest(**_access_kwargs())
    assert r.status == "PENDING"
    assert r.duo_codes == ["DUO:0000004"]


def test_federation_access_request_defaults() -> None:
    kwargs = _access_kwargs()
    kwargs.pop("status")
    kwargs.pop("duo_codes")
    r = FederationAccessRequest(**kwargs)
    assert r.status == "PENDING"
    assert r.duo_codes == []
    assert r.approved_at is None
    assert r.denied_at is None
    assert r.expires_at is None


def test_federation_access_request_rejects_missing_purpose() -> None:
    kwargs = _access_kwargs()
    kwargs.pop("purpose")
    with pytest.raises(ValidationError):
        FederationAccessRequest(**kwargs)
