> **Status:** Canonical — architectural decision record.

# CARE Principles adopted alongside FAIR

Indigenous Data Sovereignty — Collective Benefit, Authority to Control,
Responsibility, Ethics — is a first-class design constraint, not an optional
overlay. The platform ships the enforcement primitives for all deployments
(residency, revocable consent, no-auto-publish defaults, federation
restrictions, audit portal); per-org policy enablement determines which apply.

## Consequences

Authority to Control is the load-bearing one for the schema: withdrawn-consent
data must actually leave the system, which is why soft-deletion alone is
insufficient and the tombstone-and-vacuum lifecycle exists. Compliance is
documented in `governance/care-principles-and-tribal-data-sovereignty.md`.
