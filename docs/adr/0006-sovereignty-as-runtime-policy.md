> **Status:** Canonical — architectural decision record.

# Indigenous data sovereignty is runtime policy, not a deployment scenario

Sovereignty was originally designed as a dedicated install scenario. It is now
modelled as a set of runtime policies any deployment enables after install:
deletion-on-request via the tombstone-and-vacuum lifecycle, no auto-publish to
NCBI/INSDC, federation restrictions, audit visibility, residency enforcement,
and revocable consent.

**What is built, measured 2026-09-03.** Deletion-on-request is implemented
(`backend/backend/deletion.py`). Federation restrictions and audit are
partial — the capability and the write path exist, the policy expression and
the read path do not. No auto-publish, residency enforcement and revocable
consent have no implementation. This does not alter the decision, which is
about where sovereignty lives in the architecture rather than about
completeness; it is recorded so the list above is not read as an inventory of
shipped features. See `B-CARE-CLAIMS-RECONCILE`.

The distinction this preserves: a Tribal college running JACKPOT for genomics
coursework picks Scenario A and enables nothing. A Tribal Nation health
department running under CARE Principles picks the same Scenario A and enables
sovereignty policies. Same install, same code, different configuration —
rather than a separate scenario that would fork the install matrix by
operator identity.

Supersedes the original "Scenario T" design. See `docs/architecture.md` §22.
