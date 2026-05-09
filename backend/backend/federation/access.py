"""
Level 3 — Bidirectional cross-instance access requests.

Track 1 implementation. Year 2 late on the roadmap. The structure here is
a stub at the IO layer (no DB session, no presigned-URL minting, no copy
job). What's concrete is:
  - The integration point with the existing internal `sample_access`
    workflow — Level 3 reuses it, doesn't reinvent it
  - The cross-instance attribution model
  - The AIS hook seams for partner attestation and threshold approval

When L3 is scheduled, the IO gets wired up; the integration shape stays.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from backend.federation._ais_hooks import (
    AISFederationHooks,
    NullAISFederationHooks,
)
from backend.federation.models import (
    FederatedInstance,
    FederationAccessRequest,
)

logger = logging.getLogger(__name__)


class FederationAccessGateway:
    """Cross-instance access request handler. Track 1, Level 3.

    Two flows:

      Outbound: a user on THIS instance requests access to a sample held
        by a partner. We POST a FederationAccessRequest to the partner's
        gateway. Partner's Lab Director approves through their normal UI.
        On approval, we get back a presigned URL list and run the copy job.

      Inbound: a partner POSTs a FederationAccessRequest to us. We create
        a row in the existing internal `sample_access` workflow and notify
        the relevant Lab Director. Approval is handled exactly like an
        internal access request — same UI, same audit log, same email
        templates.

    AIS hook seams:
      - `attest_partner()` is called once per request before any state
        change. Track 1 NullAISFederationHooks always returns True.
      - `threshold_approve()` is called for any access request where the
        target sample has elevated sensitivity (CDC reportable, BSL-3+
        organism, etc.). Track 1 NullAISFederationHooks always returns
        True; the existing Lab Director approval is sufficient.
    """

    def __init__(self, *, hooks: AISFederationHooks | None = None) -> None:
        self._hooks: AISFederationHooks = hooks or NullAISFederationHooks()

    def build_outbound_request(
        self,
        *,
        target_sample_id: str,
        target_instance: FederatedInstance,
        requesting_instance_id,
        requesting_user_email: str,
        purpose: str,
        duo_codes: list[str] | None = None,
    ) -> FederationAccessRequest:
        """Construct an outbound access request to send to a partner."""
        return FederationAccessRequest(
            request_id=uuid4(),
            requesting_instance_id=requesting_instance_id,
            requesting_user_email=requesting_user_email,
            target_sample_id=target_sample_id,
            target_instance_id=target_instance.id,
            purpose=purpose,
            duo_codes=duo_codes or [],
            requested_at=datetime.now(UTC),
            status="PENDING",
        )

    async def submit_outbound(
        self,
        request: FederationAccessRequest,
        target: FederatedInstance,
    ) -> None:
        """Submit an outbound access request. Track 1 STUB.

        Wire-up TODO when L3 is scheduled (Year 2 late):
          - Resolve federation API key for target from Secret Manager
          - POST to {target.base_url}api/v1/federation/access-requests
          - Persist the request in `federation_access_requests` table
            (new — schema add when L3 schedules)
          - Subscribe to status updates via webhook from target
          - On APPROVED: trigger inbound copy job (separate worker)
        """
        # AIS HOOK: attest_partner — Track 2 verifies remote attestation
        # before sending any access request.
        if not self._hooks.attest_partner(target):
            logger.warning(
                "federation access: target %s failed attestation; withholding request",
                target.name,
            )
            return

        raise NotImplementedError(
            "FederationAccessGateway.submit_outbound: Level 3 IO not yet "
            "wired. See Year 2 late scheduling in jackpot_architecture.md §22."
        )

    async def receive_inbound(
        self,
        request: FederationAccessRequest,
        source: FederatedInstance,
    ) -> None:
        """Handle an inbound access request from a partner. Track 1 STUB.

        Wire-up TODO when L3 is scheduled (Year 2 late):
          - Validate the source partner exists in `federated_instances`
          - Validate the request's federation API key
          - Look up the target sample locally; verify it belongs to this
            instance
          - Create an internal `sample_access` row tagged with
            external_requester=source.name and external_request_id=
            request.request_id
          - Notify the sample's Lab Director via the existing notification
            pipeline
          - On approval (handled by the existing internal sample_access
            router): mint presigned URLs, POST status update + URLs back
            to source's webhook endpoint
        """
        # AIS HOOK: attest_partner — Track 2 verifies the source's TEE
        # attestation before accepting the request.
        if not self._hooks.attest_partner(source):
            logger.warning(
                "federation access: inbound source %s failed attestation; rejecting",
                source.name,
            )
            return

        # AIS HOOK: threshold_approve — Track 2 escalates sensitive samples
        # (CDC reportable, BSL-3+) to M-of-N approval. Track 1 default is
        # True; existing Lab Director approval is sufficient for Track 1.
        if not self._hooks.threshold_approve(
            action="GRANT_FEDERATION_ACCESS",
            affected_partners=[source],
        ):
            logger.warning(
                "federation access: threshold approval failed for inbound "
                "request from %s; rejecting",
                source.name,
            )
            return

        raise NotImplementedError(
            "FederationAccessGateway.receive_inbound: Level 3 IO not yet "
            "wired. See Year 2 late scheduling in jackpot_architecture.md §22."
        )
