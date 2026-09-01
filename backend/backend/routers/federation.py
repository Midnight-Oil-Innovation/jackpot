# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""FED-B: Federation router.

Exposes the FED-A federation package over HTTP as
``/api/v1/federation/*``:

  GET  /instances        — list registered partners (Platform Admin)
  POST /instances        — register a partner          (Platform Admin)
  POST /search           — broadcast a L1 query        (authenticated user)
  POST /push             — receive an L2 push payload  (federation peer)
  POST /access-requests  — receive an L3 access req    (federation peer)

Auth model:

  * Admin endpoints (``GET/POST /instances``) use the standard JWT-cookie
    + ``require_capability`` guard already wired into the rest of
    the API.
  * The ``/search`` endpoint is internal-user-facing and requires a
    normal authenticated user. Federation results are
    DISCOVERABLE-equivalent metadata so any authenticated user can
    issue one.
  * Peer-to-peer endpoints (``/push`` and ``/access-requests``)
    authenticate via the ``X-JACKPOT-Federation-Key`` header. The
    presented key is compared (constant-time) against every enabled
    instance's secret looked up by ``federated_instances.api_key_secret_name``
    through the credentials facade (GCP Secret Manager in prod,
    InMemoryBackend in tests).

What this router does NOT do — by design:

  * It does not yet persist inbound L2 payloads (the
    ``federation_pushes`` table is not in the schema yet — Year 2 early
    per architecture.md §22). The endpoint authenticates, validates,
    and returns 202 with the payload echoed.
  * It does not yet drive the internal ``sample_access`` workflow from
    inbound L3 requests (Year 2 late per architecture.md §22). The
    endpoint authenticates, validates, and returns 202.

When L2/L3 IO is scheduled, the stubs at
``backend/backend/federation/{push,access}.py`` get wired up and the
202 paths here become calls into those modules.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, HttpUrl, field_validator

from backend.audit import log_audit
from backend.auth.guards import (
    authenticate_federation_peer,
    get_current_user,
    require_capability,
)
from backend.authz.principal import load_peer_principal
from backend.authz.visibility import sample_list_clause
from backend.credentials import credentials
from backend.database import execute_query, execute_write, get_db_dep
from backend.federation.client import FederationClient
from backend.federation.models import (
    FederatedInstance,
    FederationPushPayload,
    FederationQuery,
    FederationRole,
    require_secure_url,
)
from backend.federation.push import FederationPushJob
from backend.responses import error, success, success_list

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/federation", tags=["federation"])

# Audit actions kept local to the router (not added to backend/audit.py)
# until the broader federation audit surface is reviewed. Following the
# convention used by other routers that emit a small number of
# router-local actions.
AUDIT_REGISTER_INSTANCE = "REGISTER_FEDERATED_INSTANCE"
AUDIT_FEDERATION_SEARCH = "FEDERATION_SEARCH"
AUDIT_FEDERATION_PUSH_RECEIVED = "FEDERATION_PUSH_RECEIVED"
AUDIT_FEDERATION_ACCESS_REQUEST_RECEIVED = "FEDERATION_ACCESS_REQUEST_RECEIVED"


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class InstanceCreate(BaseModel):
    """POST /instances body — operator-supplied subset of FederatedInstance.

    Server fills id, created_at, updated_at, last_seen_at.
    """

    name: str = Field(..., min_length=1, max_length=255)
    base_url: HttpUrl
    role: FederationRole
    federation_enabled: bool = False
    min_sharing_level_for_federation: str = Field(default="DISCOVERABLE")
    hub_instance_url: HttpUrl | None = None
    api_key_secret_name: str = Field(..., min_length=1, max_length=255)

    @field_validator("base_url", "hub_instance_url")
    @classmethod
    def _reject_plaintext_urls(cls, v: HttpUrl | None, info) -> HttpUrl | None:
        return require_secure_url(v, field_name=info.field_name)


class FederationSearchRequest(BaseModel):
    """POST /search body — wraps a FederationQuery."""

    query: FederationQuery = Field(default_factory=FederationQuery)


class AccessRequestInbound(BaseModel):
    """POST /access-requests body.

    Mirrors :class:`backend.federation.models.FederationAccessRequest` but
    permits the caller to omit server-managed fields. We accept the full
    request object as-is so partners can include any fields they hold.
    """

    request_id: UUID
    requesting_instance_id: UUID
    requesting_user_email: str
    target_sample_id: str
    target_instance_id: UUID
    purpose: str
    duo_codes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialise(row: dict[str, Any]) -> dict[str, Any]:
    """Stringify UUID / datetime values so the response is JSON-safe."""
    out = dict(row)
    for k, v in out.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        elif isinstance(v, UUID):
            out[k] = str(v)
    return out


def _row_to_instance(row: dict[str, Any]) -> FederatedInstance:
    """Build a Pydantic FederatedInstance from a DB row."""
    return FederatedInstance.model_validate(row)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.get("/instances")
def list_instances(
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_capability("federation:configure_peer")(user)

    rows = execute_query(
        "SELECT * FROM federated_instances ORDER BY name ASC",
        conn=db,
    )
    return success_list(
        data=[_serialise(r) for r in rows],
        page=1,
        per_page=len(rows) or 1,
        total=len(rows),
    )


@router.post("/instances", status_code=201)
def register_instance(
    payload: InstanceCreate,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    require_capability("federation:configure_peer")(user)

    existing = execute_query(
        "SELECT id FROM federated_instances WHERE name = :n LIMIT 1",
        {"n": payload.name},
        conn=db,
    )
    if existing:
        return error(
            "CONFLICT",
            f"Federated instance '{payload.name}' is already registered.",
            status_code=409,
        )

    rows = execute_write(
        """
        INSERT INTO federated_instances
            (name, base_url, role, federation_enabled,
             min_sharing_level_for_federation, hub_instance_url,
             api_key_secret_name)
        VALUES
            (:name, :base_url, CAST(:role AS federation_role),
             :federation_enabled, :min_sharing_level_for_federation,
             :hub_instance_url, :api_key_secret_name)
        RETURNING *
        """,
        {
            "name": payload.name,
            "base_url": str(payload.base_url),
            "role": payload.role.value,
            "federation_enabled": payload.federation_enabled,
            "min_sharing_level_for_federation": payload.min_sharing_level_for_federation,
            "hub_instance_url": str(payload.hub_instance_url) if payload.hub_instance_url else None,
            "api_key_secret_name": payload.api_key_secret_name,
        },
        conn=db,
    )
    row = rows[0]
    log_audit(
        action=AUDIT_REGISTER_INSTANCE,
        actor_id=user["id"],
        resource_type="federated_instance",
        resource_id=str(row["id"]),
        before=None,
        after=_serialise(row),
        metadata=None,
        db_conn=db,
    )
    return success(data=_serialise(row), status_code=201)


# ---------------------------------------------------------------------------
# Outbound L1 query (search)
# ---------------------------------------------------------------------------


@router.post("/search")
async def federation_search(
    payload: FederationSearchRequest,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    # M2-B5: deliberately still auth-only, and the map row is corrected
    # rather than the route.
    #
    # The map assigns sample:read at INSTANCE scope. Nobody holds it there:
    # every preset granting sample:read issues it at lab scope, and giving an
    # Instance Administrator blanket sample:read would contradict §8.2 head-on
    # — the Surveillance Officer preset exists precisely so that instance-wide
    # sample reading is narrowed to surveillance_relevant rows rather than
    # conferred wholesale. So enforcing the row as written makes a working
    # route reachable by nobody.
    #
    # What the right verb is belongs with §7's federation work (M4): the
    # question this route actually asks is "may this user query our peers on
    # this deployment's behalf", which is not the same act as reading a
    # sample here, and the results come back filtered by the peer's own
    # policy regardless.

    rows = execute_query(
        "SELECT * FROM federated_instances WHERE federation_enabled = TRUE",
        conn=db,
    )
    partners = [_row_to_instance(r) for r in rows]

    def _resolve_key(instance: FederatedInstance) -> str:
        return credentials.get(instance.api_key_secret_name)

    async with FederationClient() as fc:
        results = await fc.query(
            payload.query,
            partners=partners,
            api_key_resolver=_resolve_key,
        )

    serialised = [r.model_dump(mode="json") for r in results]
    log_audit(
        action=AUDIT_FEDERATION_SEARCH,
        actor_id=user["id"],
        resource_type="federation_query",
        resource_id="search",
        before=None,
        after=None,
        metadata={
            "partner_count": len(partners),
            "result_count": len(serialised),
            "query": payload.query.model_dump(mode="json", exclude_none=True),
        },
        db_conn=db,
    )
    return success(data=serialised)


# ---------------------------------------------------------------------------
# Inbound L1 query
# ---------------------------------------------------------------------------

# Columns a federated result may carry. DISCOVERABLE-equivalent by
# construction (models.FederationQueryResult): no file URIs, no clinical
# metadata, no PII. The projection is an allowlist rather than SELECT * so a
# column added to `samples` later cannot silently start crossing the boundary.
_FEDERATION_RESULT_COLUMNS = (
    "s.sample_id AS sample_id",
    "s.organism_name AS organism",
    "s.date_collected AS date_collected",
    "s.collection_location_country AS country",
    "s.collection_location_state AS state",
    "s.source_type AS source_type",
    "s.sector AS sector",
    "s.quality_status AS quality_tier",
    "s.surveillance_relevant AS surveillance_relevant",
)

# Wire-level floor, independent of any agreement (§7.4). A peer whose
# agreement somehow granted more still cannot pull PRELIMINARY rows.
_FEDERATION_QUALITY_FLOOR = ("ANALYZABLE", "SUBMITTABLE")


@router.post("/query")
def federation_query_inbound(
    payload: FederationQuery,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    """Answer a peer's L1 query with what its sharing agreements allow.

    **Why this route exists rather than peer-auth on /api/v1/samples/.**
    §7.4 describes the inbound query landing on the partner's
    ``GET /api/v1/samples/``, filtered by the peer principal — "not a separate
    code path". That integration was never built: the samples list
    authenticates a JWT cookie and nothing else, and no test exercised an
    inbound federated query, so a real peer query would have 401'd. Given the
    choice of adding a second authentication mode to the most-read endpoint in
    the system, or putting the peer-facing route beside the two that already
    authenticate peers, this takes the second. What §7.4 actually cares about
    — that federated visibility is the *same decision* as local visibility, not
    a parallel implementation — is preserved: the filtering below is
    ``sample_list_clause``, the identical compiler every local list uses.

    Default-deny falls out (§7.3): a peer with no active agreement loads with
    an empty grant set, so the clause matches nothing and this returns [].
    """
    instance_row = authenticate_federation_peer(request, db)
    if not instance_row:
        return error("UNAUTHORIZED", "Invalid or missing federation key.", status_code=401)

    principal = load_peer_principal(str(instance_row["id"]), conn=db)
    vis_clause, params = sample_list_clause(principal)

    clauses = [vis_clause, "s.deletion_status = 'ACTIVE'", "s.is_archived = FALSE"]

    # The wire-level quality floor. The client also sets quality_tier_min, but
    # a floor that only exists on the caller's side is not a floor.
    clauses.append("s.quality_status = ANY(:fed_quality)")
    params["fed_quality"] = list(_FEDERATION_QUALITY_FLOOR)

    filters = {
        "organism": ("s.organism_name = :f_organism", payload.organism),
        "country": ("s.collection_location_country = :f_country", payload.country),
        "state": ("s.collection_location_state = :f_state", payload.state),
        "source_type": ("s.source_type = :f_source_type", payload.source_type),
    }
    for key, (sql, value) in filters.items():
        if value is not None:
            clauses.append(sql)
            params[f"f_{key}"] = value
    if payload.date_collected_from is not None:
        clauses.append("s.date_collected >= :f_from")
        params["f_from"] = payload.date_collected_from
    if payload.date_collected_to is not None:
        clauses.append("s.date_collected <= :f_to")
        params["f_to"] = payload.date_collected_to

    params["fed_limit"] = payload.page_size
    params["fed_offset"] = (payload.page - 1) * payload.page_size

    rows = execute_query(
        # The samples JOIN labs is load-bearing, not decoration: a sample's
        # scope is derived from its lineage and the org segment comes from
        # labs.organization_id (ADR 0015).
        f"SELECT {', '.join(_FEDERATION_RESULT_COLUMNS)} "  # noqa: S608 — constant projection
        "FROM samples s JOIN labs l ON l.id = s.lab_id "
        f"WHERE {' AND '.join(clauses)} "
        "ORDER BY s.date_collected DESC, s.sample_id "
        "LIMIT :fed_limit OFFSET :fed_offset",
        params,
        conn=db,
    )

    log_audit(
        action=AUDIT_FEDERATION_SEARCH,
        actor_id=None,
        resource_type="federation_query_inbound",
        resource_id=str(instance_row["id"]),
        before=None,
        after=None,
        metadata={
            "peer": instance_row.get("name"),
            "result_count": len(rows),
            "grants_held": len(principal.grants),
            "query": payload.model_dump(mode="json", exclude_none=True),
        },
        db_conn=db,
    )
    return success_list(
        data=[dict(r) for r in rows],
        page=payload.page,
        per_page=payload.page_size,
        total=len(rows),
    )


# ---------------------------------------------------------------------------
# Inbound L2 push
# ---------------------------------------------------------------------------


@router.post("/push", status_code=202)
def federation_push_inbound(
    payload: FederationPushPayload,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    instance_row = authenticate_federation_peer(request, db)
    if not instance_row:
        return error(
            "UNAUTHORIZED",
            "Invalid or missing federation key.",
            status_code=401,
        )

    # Track 1 stub: persist the qualification gate is delegated to
    # FederationPushJob.is_qualifying_sample-equivalent on the sender;
    # the receiver re-runs the AIS validate_push_payload hook (Track 1
    # always returns True) to keep the seam exercised end-to-end.
    job = FederationPushJob()
    sender = _row_to_instance(instance_row)
    if not job._hooks.validate_push_payload(payload, sender):  # noqa: SLF001
        return error(
            "FORBIDDEN",
            "Payload rejected by AIS validation.",
            status_code=403,
        )

    log_audit(
        action=AUDIT_FEDERATION_PUSH_RECEIVED,
        actor_id=None,
        resource_type="federation_push",
        resource_id=payload.sample_id,
        before=None,
        after=payload.model_dump(mode="json"),
        metadata={
            "source_instance_id": str(instance_row["id"]),
            "source_instance_name": instance_row.get("name"),
        },
        db_conn=db,
    )
    logger.info(
        "federation push received: sample=%s from instance=%s",
        payload.sample_id,
        instance_row.get("name"),
    )
    return success(
        data={
            "sample_id": payload.sample_id,
            "source_instance_id": str(instance_row["id"]),
            "received": True,
        },
        status_code=202,
    )


# ---------------------------------------------------------------------------
# Inbound L3 access request
# ---------------------------------------------------------------------------


@router.post("/access-requests", status_code=202)
def federation_access_request_inbound(
    payload: AccessRequestInbound,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    instance_row = authenticate_federation_peer(request, db)
    if not instance_row:
        return error(
            "UNAUTHORIZED",
            "Invalid or missing federation key.",
            status_code=401,
        )

    # Cross-check: the caller's authenticated instance must match the
    # requesting_instance_id in the body. Mismatched origins are a
    # spoofing signal and rejected.
    if str(instance_row["id"]) != str(payload.requesting_instance_id):
        return error(
            "FORBIDDEN",
            "requesting_instance_id does not match authenticated federation peer.",
            status_code=403,
        )

    log_audit(
        action=AUDIT_FEDERATION_ACCESS_REQUEST_RECEIVED,
        actor_id=None,
        resource_type="federation_access_request",
        resource_id=str(payload.request_id),
        before=None,
        after=payload.model_dump(mode="json"),
        metadata={
            "source_instance_id": str(instance_row["id"]),
            "source_instance_name": instance_row.get("name"),
        },
        db_conn=db,
    )
    logger.info(
        "federation access request received: request_id=%s target_sample=%s from instance=%s",
        payload.request_id,
        payload.target_sample_id,
        instance_row.get("name"),
    )
    return success(
        data={
            "request_id": str(payload.request_id),
            "status": "RECEIVED",
            "source_instance_id": str(instance_row["id"]),
        },
        status_code=202,
    )
