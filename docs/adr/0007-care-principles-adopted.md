> **Status:** Canonical — architectural decision record.

# CARE Principles adopted alongside FAIR

Indigenous Data Sovereignty — Collective Benefit, Authority to Control,
Responsibility, Ethics — is a first-class design constraint, not an optional
overlay. The enforcement primitives are to be shipped for all deployments
rather than gated behind an edition or a scenario, with per-org policy
enablement determining which apply.

**Status of the primitives, measured 2026-09-03.** This sentence was written
in the present tense ("the platform ships") before the primitives existed.
Of the five it named — residency, revocable consent, no-auto-publish
defaults, federation restrictions, audit portal — federation restrictions
are partial and the other four are not built. The decision recorded here
stands; the tense was wrong. See `B-CARE-CLAIMS-RECONCILE` for the
measurement and `governance/care-principles-and-tribal-data-sovereignty.md`
for the per-behaviour table.

## Consequences

Authority to Control is the load-bearing one for the schema: withdrawn-consent
data must actually leave the system, which is why soft-deletion alone is
insufficient and the tombstone-and-vacuum lifecycle exists. Compliance is
documented in `governance/care-principles-and-tribal-data-sovereignty.md`.
