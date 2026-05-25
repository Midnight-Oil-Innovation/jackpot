"""HRRT scrubber orchestration interface.

Python-side orchestrator for ingest_scrubber.nf - submission, state polling,
6-state lifecycle management, 48h skip governance, concurrency control.

Track 1 - delegates Nextflow invocation and state-store reads to existing
pipeline launcher; Track 2 hook seam reserved for future overlays
(synthetic-substitute on skipped runs, anomalous-traffic detection on
unusually high skip-request volumes).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

from backend.privacy._ais_hooks import AISPrivacyHooks, NullAISPrivacyHooks

SCRUBBER_MAX_CONCURRENT: int = 10
SCRUBBER_SKIP_TTL_HOURS: int = 48


class ScrubberState(str, Enum):
    """6-state lifecycle for a scrubber run."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    PENDING_APPROVAL = "PENDING_APPROVAL"


@dataclass
class ScrubberRunRecord:
    """Audit record for one scrubber run."""

    sample_id: str
    state: ScrubberState
    submitted_at: datetime
    completed_at: datetime | None = None
    skip_approved_until: datetime | None = None
    skip_approved_by: str | None = None
    skip_justification: str | None = None
    failure_reason: str | None = None
    nextflow_run_id: str | None = None
    history: list[tuple[ScrubberState, datetime]] = field(default_factory=list)


class ScrubberOrchestrator:
    """Orchestration interface for ingest_scrubber.nf.

    Track 1 - submission, state polling, lifecycle management. Delegates
    Nextflow invocation to the existing pipeline launcher. Track 2 hook seam
    is wired but inert in Track 1 (NullAISPrivacyHooks).

    The 6-state lifecycle:
        PENDING -> IN_PROGRESS -> {COMPLETE | FAILED}
        PENDING -> PENDING_APPROVAL -> {SKIPPED | PENDING (TTL expired)}

    Skip governance: a skip request enters PENDING_APPROVAL with a
    skip_approved_until timestamp self.skip_ttl_hours in the future. After
    the TTL elapses without approval, the daily lifecycle reaper transitions
    the record back to PENDING. Approval (by an authorized actor) transitions
    to SKIPPED.

    Concurrency: at most self.max_concurrent samples in IN_PROGRESS at a time.
    """

    def __init__(
        self,
        max_concurrent: int = SCRUBBER_MAX_CONCURRENT,
        skip_ttl_hours: int = SCRUBBER_SKIP_TTL_HOURS,
        hooks: AISPrivacyHooks | None = None,
    ) -> None:
        self.max_concurrent = max_concurrent
        self.skip_ttl_hours = skip_ttl_hours
        self.hooks: AISPrivacyHooks = hooks or NullAISPrivacyHooks()

    def submit_scrub_run(
        self,
        sample_id: str,
        input_uri: str,
        actor_id: str,
    ) -> ScrubberRunRecord:
        """Queue a sample for scrubbing.

        TODO(privacy-scaffold): align with existing pipeline launcher API
        (likely backend.pipelines.launcher or backend.helpers.nextflow).
        Once aligned, this method submits the Nextflow run and writes the
        initial PENDING record to the scrubber-state store.
        """
        now = datetime.now(UTC)
        record = ScrubberRunRecord(
            sample_id=sample_id,
            state=ScrubberState.PENDING,
            submitted_at=now,
            history=[(ScrubberState.PENDING, now)],
        )
        return record

    def poll_state(self, sample_id: str) -> ScrubberState:
        """Read current state from the scrubber-state store.

        TODO(privacy-scaffold): align with existing state store
        (Postgres table updated by ingest_scrubber.nf webhook handler).
        """
        return ScrubberState.PENDING

    def get_lifecycle_history(
        self,
        sample_id: str,
    ) -> list[tuple[ScrubberState, datetime]]:
        """Return ordered state transitions for the sample's scrubber lifecycle.

        TODO(privacy-scaffold): wire to scrubber audit table.
        """
        return []

    def request_skip(
        self,
        sample_id: str,
        actor_id: str,
        justification: str,
    ) -> ScrubberRunRecord:
        """Submit a skip request, transitioning state to PENDING_APPROVAL.

        Skip requests stay valid for self.skip_ttl_hours - after the TTL
        elapses without approval, the request expires and the sample falls
        back to PENDING.

        TODO(privacy-scaffold): persist to skip-governance table; emit audit log.
        """
        now = datetime.now(UTC)
        record = ScrubberRunRecord(
            sample_id=sample_id,
            state=ScrubberState.PENDING_APPROVAL,
            submitted_at=now,
            skip_approved_until=now + timedelta(hours=self.skip_ttl_hours),
            skip_justification=justification,
            history=[
                (ScrubberState.PENDING, now - timedelta(seconds=1)),
                (ScrubberState.PENDING_APPROVAL, now),
            ],
        )
        return record

    def approve_skip(
        self,
        sample_id: str,
        approver_id: str,
    ) -> ScrubberRunRecord:
        """Approve a pending skip request, transitioning to SKIPPED.

        TODO(privacy-scaffold): wire to skip-governance table; emit audit log.
        Authorization check (approver must hold appropriate role) is done
        at the router layer, not here.
        """
        now = datetime.now(UTC)
        record = ScrubberRunRecord(
            sample_id=sample_id,
            state=ScrubberState.SKIPPED,
            submitted_at=now,
            skip_approved_until=now + timedelta(hours=self.skip_ttl_hours),
            skip_approved_by=approver_id,
        )
        return record

    def expire_stale_skip_requests(self) -> int:
        """Daily reaper - transition expired PENDING_APPROVAL back to PENDING.

        Returns count of records reaped. Called by the daily APScheduler job.

        TODO(privacy-scaffold): wire to scrubber-state store; iterate
        PENDING_APPROVAL records where skip_approved_until < now().
        """
        return 0
