"""
JACKPOT federation package.

This package implements JACKPOT's three-level federation architecture:

  Level 1 — Query federation (Month 2-3, Track 1):
      DISCOVERABLE-equivalent metadata search across registered partners.
      No clinical metadata, no file URLs, 30-min cache.

  Level 2 — De-identified hub push (Year 2 early, Track 1):
      Spoke instances push surveillance data nightly. Payload is FASTA +
      typing + AMR + lineage + organism + date + country/state. Raw FASTQ
      and PII never leave the spoke.

  Level 3 — Bidirectional sharing (Year 2 late, Track 1):
      Cross-instance access requests. Org B requests samples from Org A.
      Org A approves via the same UI as internal access requests. Files
      copied via presigned URL.

The package is structured as two parallel tracks (see README.md):

  Track 1 (build now): client.py / push.py / access.py implement the three
      levels using the existing JACKPOT primitives — JWT auth, presigned
      URLs, the same can_access_sample() permission model used internally.

  Track 2 (scaffold for AIS): _ais_hooks.py defines extension points where
      AIS-flavored augmentation slots in later — secure aggregation on
      query results, attestation checks on partners, anomaly detection on
      cross-federation traffic, threshold approval for sensitive shares.
      Track 1 ships with no-op default implementations of every hook;
      Track 2 work overrides them via dependency injection.

Cross-references:
  - jackpot_architecture.md §22 (federation)
  - jackpot_session_summary_and_backlog.md (Q5, B-FED-1)
  - Jackpot_AIS.md §1.6 (inter-instance signaling), §1.8 (tolerance)
"""

from backend.federation._ais_hooks import (
    AISFederationHooks,
    NullAISFederationHooks,
)
from backend.federation.access import FederationAccessGateway
from backend.federation.client import FederationClient
from backend.federation.models import (
    FederatedInstance,
    FederationAccessRequest,
    FederationPushPayload,
    FederationQuery,
    FederationQueryResult,
    FederationRole,
)
from backend.federation.push import FederationPushJob

__all__ = [
    # Models
    "FederatedInstance",
    "FederationQuery",
    "FederationQueryResult",
    "FederationPushPayload",
    "FederationAccessRequest",
    "FederationRole",
    # Implementations
    "FederationClient",
    "FederationPushJob",
    "FederationAccessGateway",
    # AIS extension points
    "AISFederationHooks",
    "NullAISFederationHooks",
]
