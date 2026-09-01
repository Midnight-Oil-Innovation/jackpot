"""
Level 2 — De-identified hub push.

Track 1 implementation. Year 2 early on the roadmap, but the qualification
logic (which samples are eligible to push) is solvable now and lives here
so the path forward is clear.

This module is a STUB at the IO layer (no DB session, no GCS presigner,
no actual HTTP push) but the qualification logic and the AIS hook surface
are concrete. When the L2 work is scheduled, the IO gets wired up and the
stubs in `push_to_hub()` get replaced.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from backend.federation._ais_hooks import (
    AISFederationHooks,
    NullAISFederationHooks,
)
from backend.federation.models import (
    FederatedInstance,
    FederationPushPayload,
)

logger = logging.getLogger(__name__)


class FederationPushJob:
    """Nightly Level 2 hub-push job. Track 1.

    AIS hook seams:
      - `validate_push_payload()` is called once per outbound payload.
        Track 1 NullAISFederationHooks always returns True.
      - `threshold_approve()` is called for any non-routine push event
        (first-time push to a hub, schema change, retry of failed pushes).
        Track 1 NullAISFederationHooks always returns True.
    """

    def __init__(self, *, hooks: AISFederationHooks | None = None) -> None:
        self._hooks: AISFederationHooks = hooks or NullAISFederationHooks()

    @staticmethod
    def is_qualifying_sample(
        *,
        surveillance_relevant: bool,
        sharing_level: str,
        quality_status: str,
        min_sharing_level_for_federation: str,
    ) -> bool:
        """Decide whether a sample is eligible for the L2 push.

        Three gates from jackpot_architecture.md §22:
          1. surveillance_relevant must be True
          2. sharing_level >= the org's min_sharing_level_for_federation
          3. quality_status >= ANALYZABLE (no PRELIMINARY ever leaks across
             federation boundaries)
        """
        if not surveillance_relevant:
            return False
        if not _sharing_level_ge(sharing_level, min_sharing_level_for_federation):
            return False
        return _quality_status_ge(quality_status, "ANALYZABLE")

    @staticmethod
    def may_push_sample(
        principal,
        resource,
        *,
        surveillance_relevant: bool,
        sharing_level: str,
        quality_status: str,
        min_sharing_level_for_federation: str,
        context=None,
    ) -> bool:
        """The full L2 push decision: authorization AND the three gates.

        §7.4 splits this in two and both halves are required. The agreement
        grants ``federation:push`` at a scope — that is the authorization, and
        it is what ``permit()`` answers. The three qualification gates are the
        operational floor on top, and they are not expressible as a grant
        because two of them (quality, sharing level) are properties of the row
        rather than of the relationship.

        Order matters for what it costs, not for what it decides: ``permit()``
        runs first because a peer with no agreement should not have its rows
        inspected at all.

        **Deny-wins is why this function is the point of the exercise.** A
        DENY policy on ``federation:push`` — §6.2-3's tombstone guard, which
        stops a sample mid-deletion from ever federating out — beats a valid
        agreement here and nowhere else. Calling the gates without
        ``permit()`` would leave that policy with nothing to attach to.

        Not yet reached by ``push_to_hub``, whose IO is still stubbed. This is
        the decision function that stub will call, and it is tested as such.
        """
        from backend.authz import Context, Decision, permit
        from backend.authz.policy import ACTIVE_POLICIES

        decision = permit(
            principal,
            "federation:push",
            resource,
            context or Context(conditions={}),
            policies=ACTIVE_POLICIES,
        )
        if decision is not Decision.ALLOW:
            return False
        return FederationPushJob.is_qualifying_sample(
            surveillance_relevant=surveillance_relevant,
            sharing_level=sharing_level,
            quality_status=quality_status,
            min_sharing_level_for_federation=min_sharing_level_for_federation,
        )

    def build_payload(
        self,
        *,
        sample: dict,  # row from samples table joined with typing/AMR results
        fasta_presigned_url: str,
    ) -> FederationPushPayload:
        """Compose the de-identified push payload for one qualifying sample.

        Builds the minimum information the hub needs for surveillance — and
        nothing more. The negative list (raw FASTQ, host_age, host_sex,
        case_id, etc.) is enforced by NEVER reading those fields here, not
        by trying to filter them out at the end.
        """
        return FederationPushPayload(
            sample_id=sample["sample_id"],
            organism=sample["organism"],
            date_collected=sample["date_collected"],
            country=sample.get("country"),
            state=sample.get("state"),
            source_type=sample["source_type"],
            sector=sample.get("sector"),
            quality_tier=sample["quality_status"],
            surveillance_relevant=sample["surveillance_relevant"],
            fasta_url=fasta_presigned_url,
            typing_results=sample.get("typing_results", {}),
            amr_profile=sample.get("amr_profile", {}),
            lineage=sample.get("lineage"),
            clade=sample.get("clade"),
            host_age_range=sample.get("host_age_range"),
            originating_lab=sample["originating_lab"],
            submitting_lab=sample.get("submitting_lab"),
            data_generator=sample.get("data_generator"),
            pushed_at=datetime.now(UTC),
        )

    async def push_to_hub(
        self,
        payload: FederationPushPayload,
        target: FederatedInstance,
    ) -> None:
        """Push one payload to the hub. Track 1 STUB.

        Wire-up TODO when L2 is scheduled (Year 2 early):
          - Resolve the federation API key for `target` from Secret Manager
          - POST to `{target.base_url}api/v1/federation/push` with the
            payload, the federation key, and a request-id for idempotency
          - On 409 (already-have-this-version) treat as success
          - On 5xx, retry with backoff and tracking in `federation_pushes`
            table; alert if retries exceed N
          - Audit-log every push attempt (success and failure)
        """
        # AIS HOOK: validate_push_payload — Track 2 detects "self-attack"
        # outbound payloads (unexpectedly different from the instance's
        # typical push profile).
        if not self._hooks.validate_push_payload(payload, target):
            logger.error(
                "federation push: payload for %s rejected by AIS validation; withholding",
                payload.sample_id,
            )
            return

        # AIS HOOK: threshold_approve — Track 2 enforces M-of-N approval for
        # non-routine push events (first-time push, schema bump, etc.). For
        # routine nightly pushes, callers should not pass an action that
        # triggers this hook in Track 2 implementations.
        if not self._hooks.threshold_approve(
            action="ROUTINE_PUSH",
            affected_partners=[target],
        ):
            logger.error(
                "federation push: threshold approval failed for %s; withholding",
                payload.sample_id,
            )
            return

        raise NotImplementedError(
            "FederationPushJob.push_to_hub: Level 2 IO not yet wired. "
            "See Year 2 early scheduling in jackpot_architecture.md §22."
        )


# ---------------------------------------------------------------------------
# Helpers — kept private so the qualification logic above stays readable.
# ---------------------------------------------------------------------------

_SHARING_LEVEL_ORDER: dict[str, int] = {
    "PRIVATE": 0,
    "LAB": 1,
    "DISCOVERABLE": 2,
    "REGISTERED_ACCESS": 3,
    "PUBLIC": 4,
}

_QUALITY_STATUS_ORDER: dict[str, int] = {
    "PRELIMINARY": 0,
    "ANALYZABLE": 1,
    "SUBMITTABLE": 2,
}


def _sharing_level_ge(actual: str, minimum: str) -> bool:
    return _SHARING_LEVEL_ORDER.get(actual, -1) >= _SHARING_LEVEL_ORDER.get(minimum, 99)


def _quality_status_ge(actual: str, minimum: str) -> bool:
    return _QUALITY_STATUS_ORDER.get(actual, -1) >= _QUALITY_STATUS_ORDER.get(minimum, 99)
