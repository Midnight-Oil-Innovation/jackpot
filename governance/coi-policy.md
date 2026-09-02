# JACKPOT — Conflict-of-Interest Policy

## Purpose

JACKPOT is open-source infrastructure for public-health pathogen genomics.
Decisions about its direction — what features land, which operators get
prioritized integration support, which integrations are "blessed" — should
be reviewable in light of the maintainers' other commitments. This document
establishes the disclosure expectations.

## Maintainer disclosures

Each individual or entity with commit access to the canonical JACKPOT
repository (`Midnight-Oil-Innovation/jackpot`) discloses:

1. **Direct financial interests in operators of JACKPOT.** Equity,
   contracting income greater than 10% of annual income from a single
   operator, or board seats at organizations running JACKPOT in production.

2. **Active public-health contracts that involve JACKPOT-adjacent work.**
   Even if the operator is not running JACKPOT today, an active contract
   to deliver pathogen-genomics infrastructure to a state, Tribe, or
   federal agency is disclosable.

3. **Funder relationships.** Active grants, cooperative agreements, or
   philanthropic awards that fund the maintainer's JACKPOT-related
   work, with the funder's name, the period, and the broad scope.

4. **Competing-platform relationships.** Paid roles at peer pathogen-
   genomics platforms (Pathoplexus, GenSpectrum, Pathogenwatch,
   EnteroBase, BV-BRC, etc.). Volunteer or open-source contributions to
   peer platforms are not disclosable but should be noted in commit
   messages where directly relevant.

Disclosures are kept in `governance/coi-disclosures.md` (created when the
first disclosure is filed) and updated whenever the underlying relationship
materially changes. There is no "small enough to skip" threshold for
categories 1–3; any relationship in those categories is disclosed.

## Contributor expectations

Non-maintainer contributors are not obligated to file COI disclosures, but
PRs that materially shape governance, schema, or integration semantics
should include a one-line note in the PR description if the contributor
has a commercial interest in the outcome. Example: a PR to add a Pathogen-X
parser submitted by an employee of a vendor that sells Pathogen-X
sequencing kits should say so.

## Decision-trail expectations

Any decision that disproportionately benefits a single operator —
prioritizing a feature, accepting a non-standard integration contract,
defining the canonical default value for a configurable parameter — must be:

- Discussed in a public issue or PR before merge.
- Linked from the relevant `docs/learnings.md` entry, which is the
  decision log.
- Justified on the merits, not on operator identity. ("This benefits
  operator X" is not, by itself, a sufficient justification; "this
  shape is correct because of generalizable reason Y, and operator X
  happens to be the first to need it" is.)

## Prohibited patterns

The following are not acceptable, regardless of disclosure:

- Hardcoding any operator's name, identifier, or email domain in
  production code (Critical Rule 55 — see `docs/CLAUDE.md`).
- Accepting non-public payments to merge a PR.
- Granting write access to the canonical repo to anyone whose
  professional role primarily serves a single operator's interests.
  (Reading and reviewing is fine; writing requires neutrality.)
- Direct personal data sharing with any operator outside the documented
  federation/peer-instance protocol.

## Recourse

Concerns about a maintainer's compliance with this policy can be raised:

1. As a public issue in the JACKPOT repository.
2. By email to the project's COI contact (listed in
   `governance/coi-disclosures.md` once a contact is named).
3. Anonymously via a third-party reporting form (forthcoming, when the
   advisory board is constituted per `governance/advisory-board.md`).

Concerns about an operator's compliance with the AGPL-3.0 source-disclosure
requirements should be raised with that operator directly first; the
project does not enforce AGPL on behalf of downstream forks.
