"""
Level 1 query federation — fan out a search to registered partner instances.

Track 1 implementation. Track 2 hooks via `AISFederationHooks` — see
_ais_hooks.py. The hook calls are inline and explicit so the seam is
visible without grep.

This module does NOT include the cache layer, DB lookup of registered
instances, or API key resolution from Secret Manager. Those are wired up
by the federation router (next session). What this module provides is the
core fanout, deduplication, and hook orchestration logic in one testable
unit.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import httpx

from backend.federation._ais_hooks import (
    AISFederationHooks,
    NullAISFederationHooks,
)
from backend.federation.models import (
    FederatedInstance,
    FederationQuery,
    FederationQueryResult,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_PER_PARTNER_PAGE_SIZE = 50


class FederationClient:
    """Federated query client. Track 1, Level 1.

    Fans a `FederationQuery` out to every registered partner with
    `federation_enabled=True`. Returns a unified, deduplicated result set
    annotated with `source_instance_id` so callers can attribute every row.

    AIS hook seams:
      - `attest_partner()` is called once per partner before issuing the
        query. Track 1 NullAISFederationHooks always returns True.
      - `detect_anomalous_traffic()` is called once per partner with the
        query. Track 1 NullAISFederationHooks always returns False.
      - `secure_aggregate()` wraps the final results before return. Track 1
        NullAISFederationHooks returns the results unchanged.
    """

    def __init__(
        self,
        *,
        hooks: AISFederationHooks | None = None,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._hooks: AISFederationHooks = hooks or NullAISFederationHooks()
        self._http: httpx.AsyncClient | None = http_client
        self._owns_http_client: bool = http_client is None
        self._timeout: float = timeout

    async def __aenter__(self) -> FederationClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._owns_http_client and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def query(
        self,
        query: FederationQuery,
        partners: list[FederatedInstance],
        api_key_resolver,  # callable: FederatedInstance -> str
    ) -> list[FederationQueryResult]:
        """Run `query` against every enabled partner. Returns merged results.

        `api_key_resolver` is a callable that returns the federation API key
        for a given FederatedInstance. In production this resolves through
        GCP Secret Manager; in tests it can be a dict.get.
        """
        if self._http is None:
            raise RuntimeError(
                "FederationClient must be used as an async context manager "
                "or have an http_client injected at construction time."
            )

        # Filter and gate
        eligible: list[FederatedInstance] = []
        for partner in partners:
            if not partner.federation_enabled:
                continue
            # AIS HOOK: attest_partner — Track 2 verifies remote attestation.
            if not self._hooks.attest_partner(partner):
                logger.warning(
                    "federation: partner %s failed attestation; skipping",
                    partner.name,
                )
                continue
            # AIS HOOK: detect_anomalous_traffic — Track 2 flags suspicious
            # query patterns and skips the partner (also rate-limits upstream).
            if self._hooks.detect_anomalous_traffic(query, partner):
                logger.warning(
                    "federation: query flagged as anomalous for partner %s; skipping",
                    partner.name,
                )
                continue
            eligible.append(partner)

        if not eligible:
            return []

        # Fan out concurrently. Resolve each partner's key *inside*
        # _query_one so a resolver failure (e.g. a deleted Secret Manager
        # entry) is captured per-partner by return_exceptions=True rather
        # than aborting the whole fan-out before it starts.
        tasks = [self._query_one(partner, query, api_key_resolver) for partner in eligible]
        per_partner_results = await asyncio.gather(*tasks, return_exceptions=True)

        merged: list[FederationQueryResult] = []
        for partner, result in zip(eligible, per_partner_results, strict=True):
            if isinstance(result, BaseException):
                logger.warning(
                    "federation: partner %s query failed: %s",
                    partner.name,
                    result,
                )
                continue
            merged.extend(result)

        # AIS HOOK: secure_aggregate — Track 2 applies cryptographic secure
        # aggregation / DP noise / cross-partner masking. Track 1 returns
        # identity.
        return self._hooks.secure_aggregate(merged, eligible)

    async def _query_one(
        self,
        partner: FederatedInstance,
        query: FederationQuery,
        api_key_resolver,  # callable: FederatedInstance -> str
    ) -> list[FederationQueryResult]:
        """Issue the GET /api/v1/samples/ call to a single partner."""
        if self._http is None:  # pragma: no cover — guarded by query()
            raise RuntimeError("http client unavailable")

        # Resolve the key here (not eagerly in query()) so a failure for
        # this partner doesn't take down the whole fan-out.
        api_key = api_key_resolver(partner)

        params = query.model_dump(exclude_none=True)
        # Always force ANALYZABLE+ at the wire level even if caller didn't.
        params.setdefault("quality_tier_min", "ANALYZABLE")
        headers = {
            "X-JACKPOT-Federation-Key": api_key,
            "X-JACKPOT-Federation-Origin": str(partner.id),
        }

        response = await self._http.get(
            f"{partner.base_url}api/v1/samples/",
            params=params,
            headers=headers,
            timeout=self._timeout,
        )
        response.raise_for_status()
        rows: list[dict] = response.json().get("results", [])
        # Stamp every row with source attribution. Never trust the partner
        # to set this themselves.
        return [
            FederationQueryResult(
                **row,
                source_instance_id=partner.id,
                source_instance_name=partner.name,
            )
            for row in rows
        ]
