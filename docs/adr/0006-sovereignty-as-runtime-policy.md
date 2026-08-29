> **Status:** Canonical — architectural decision record.

# Indigenous data sovereignty is runtime policy, not a deployment scenario

Sovereignty was originally designed as a dedicated install scenario. It is now
a set of runtime policies any deployment can enable after install:
deletion-on-request via the tombstone-and-vacuum lifecycle, no auto-publish to
NCBI/INSDC, federation restrictions, audit visibility, residency enforcement,
and revocable consent.

The distinction this preserves: a Tribal college running JACKPOT for genomics
coursework picks Scenario A and enables nothing. A Tribal Nation health
department running under CARE Principles picks the same Scenario A and enables
sovereignty policies. Same install, same code, different configuration —
rather than a separate scenario that would fork the install matrix by
operator identity.

Supersedes the original "Scenario T" design. See `docs/architecture.md` §22.
