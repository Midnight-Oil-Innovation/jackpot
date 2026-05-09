"""DP budget ledger - Track 2 anchor for differential-privacy accountant.

Track 1 stores all queries with their epsilon value but Null hooks return
infinity for remaining budget - no enforcement until Track 2.

Track 2 wires concrete RDP/zCDP accountant via the AISPrivacyHooks seam.
Same call sites; only the hook implementation changes.

This module is the primary anchor for the dp_noise + track_dp_budget hooks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from backend.privacy._ais_hooks import AISPrivacyHooks, NullAISPrivacyHooks


@dataclass
class DPBudgetLedgerEntry:
    """One epsilon expenditure record."""

    requester_id: str
    query_signature: str
    epsilon_spent: float
    sensitivity: float
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class DPBudgetLedger:
    """Append-only DP budget ledger.

    Track 1 - records every query/epsilon pair. With NullAISPrivacyHooks,
    dp_noise is identity and track_dp_budget returns infinity, so Track 1
    deployments effectively have no enforcement (the ledger is purely
    audit-trail, ready for retroactive analysis once a real accountant is
    wired).

    Track 2 - backend.immune.sec.privacy_hooks wires a real accountant
    (RDP / zCDP / advanced composition). Same call sites; only the hook
    implementation changes.

    TODO(privacy-scaffold): once Track 1 callsites are wired, add an
    Alembic-backed persistence layer (dp_budget_ledger table). Track 1
    in-memory storage here is sufficient for the scaffold PR.
    """

    def __init__(
        self,
        hooks: AISPrivacyHooks | None = None,
    ) -> None:
        self.hooks: AISPrivacyHooks = hooks or NullAISPrivacyHooks()
        self._entries: list[DPBudgetLedgerEntry] = []

    def record_query(
        self,
        requester_id: str,
        query_signature: str,
        result: Any,
        sensitivity: float,
        epsilon: float,
    ) -> tuple[Any, float]:
        """Record a query, apply DP noise via hook, return (noised_result, remaining).

        Call order:
          1. hooks.dp_noise(result, sensitivity, epsilon) -> noised_result
          2. hooks.track_dp_budget(requester_id, epsilon) -> remaining
          3. ledger entry appended
          4. return (noised_result, remaining)

        Track 1 (NullAISPrivacyHooks):
          - dp_noise returns result unchanged
          - track_dp_budget returns float('inf')
          - ledger entry appended (audit-only)
        """
        noised = self.hooks.dp_noise(result, sensitivity=sensitivity, epsilon=epsilon)
        remaining = self.hooks.track_dp_budget(requester_id=requester_id, epsilon_spent=epsilon)
        self._entries.append(
            DPBudgetLedgerEntry(
                requester_id=requester_id,
                query_signature=query_signature,
                epsilon_spent=epsilon,
                sensitivity=sensitivity,
            )
        )
        return noised, remaining

    def remaining(self, requester_id: str) -> float:
        """Return remaining budget for a requester (Track 2 hooks; Track 1=inf)."""
        return self.hooks.track_dp_budget(requester_id=requester_id, epsilon_spent=0.0)

    def history(
        self,
        requester_id: str | None = None,
    ) -> list[DPBudgetLedgerEntry]:
        """Return ledger entries, optionally filtered by requester."""
        if requester_id is None:
            return list(self._entries)
        return [e for e in self._entries if e.requester_id == requester_id]
