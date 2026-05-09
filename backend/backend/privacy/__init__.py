"""backend.privacy — Track 1 privacy primitives + Track 2 AIS hook seams.

Track 1 — operational privacy primitives:
- Coarsening at output boundary (k-anonymity-style generalization)
- HRRT scrubber orchestration at ingest
- GCP DLP scanning at metadata write
- DP budget ledger placeholder

Track 2 — AISPrivacyHooks Protocol seams for AIS-augmented overlays
(DP noise, FL aggregation, HE compute, MPC, synthetic substitute).
Concrete impls live in backend.immune.sec.privacy_hooks.

See README.md for hook -> AIS-doc mapping and the two-track plan.
"""

from backend.privacy._ais_hooks import (
    AISPrivacyHooks,
    NullAISPrivacyHooks,
)
from backend.privacy.budget import (
    DPBudgetLedger,
    DPBudgetLedgerEntry,
)
from backend.privacy.coarsening import (
    Coarsener,
    CoarseningPolicy,
)
from backend.privacy.dlp import (
    DLPFinding,
    DLPScanner,
)
from backend.privacy.scrubber import (
    SCRUBBER_MAX_CONCURRENT,
    SCRUBBER_SKIP_TTL_HOURS,
    ScrubberOrchestrator,
    ScrubberRunRecord,
    ScrubberState,
)

__all__ = [
    # Track 2 hook surface
    "AISPrivacyHooks",
    "NullAISPrivacyHooks",
    # Track 1 - coarsening
    "Coarsener",
    "CoarseningPolicy",
    # Track 1 - DLP
    "DLPFinding",
    "DLPScanner",
    # Track 1 - scrubber
    "SCRUBBER_MAX_CONCURRENT",
    "SCRUBBER_SKIP_TTL_HOURS",
    "ScrubberOrchestrator",
    "ScrubberRunRecord",
    "ScrubberState",
    # Track 1 - budget
    "DPBudgetLedger",
    "DPBudgetLedgerEntry",
]
