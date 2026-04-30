# JACKPOT — Advisory Board

## Status

The JACKPOT advisory board does not yet exist. JACKPOT is currently a
single-maintainer project. This document is the forward-looking design
for the advisory board so that, when the project crosses the threshold
where formal multi-stakeholder governance becomes appropriate, the
mechanics are pre-agreed.

## When to constitute the board

The trigger condition is the *first* of the following:

- 3+ independent operators running JACKPOT in production (defined as:
  serving real-world surveillance workflows, not test deployments).
- 1+ operators in Scenario T (Tribal-sovereignty deployment).
- Maintainer commits to constitute the board (e.g., as a condition of a
  funding award that requires multi-stakeholder governance).

Until the trigger fires, the maintainer makes governance decisions
unilaterally and is publicly accountable via `docs/learnings.md`,
`docs/review_log.md`, and the `governance/grievance-log.md` (if
populated).

## Composition (target)

The advisory board has 5–7 members. Composition rotates so that no
single operator-tier dominates and no single jurisdiction dominates.
Target distribution:

| Seat | Constituency | Notes |
|---|---|---|
| 1 | State / territorial public-health agency operator | Scenario C representative |
| 2 | Tribal authority or Tribal Epidemiology Center operator | Scenario T or E representative — must include lived Tribal-sovereignty experience |
| 3 | Academic-research operator | Scenario A or B representative |
| 4 | Federation peer or hosted-SaaS operator | Scenario D or E representative |
| 5 | At-large public-health-data-systems expert | Independent, not currently running JACKPOT — provides outside perspective |
| 6 | Maintainer-side seat | Held by the canonical-project maintainer or designate |
| 7 | Optional rotating seat | For specific topics (security review, CARE-Principles deepening, FHIR/TEFCA integration); rotates based on the project's near-term priorities |

If the trigger condition is hit but fewer than 5 viable candidates
exist for the seats, the maintainer constitutes a smaller interim board
with at minimum: 1 operator representative, 1 Tribal/CARE expert (even
if not running JACKPOT), and 1 at-large.

## Selection

- **Operator seats (1–4).** Self-nomination, ratified by the seated
  board (or by the maintainer for the inaugural cohort). 2-year terms,
  staggered so half the operator seats turn over each year.

- **At-large seat (5).** Nominated by the seated board from a
  shortlist; selection requires consent from at least one operator
  representative and at least one CARE/sovereignty representative.
  3-year term.

- **Maintainer seat (6).** Held by the canonical-project maintainer
  while they remain active. Does not vote on COI matters concerning
  themselves.

- **Rotating seat (7).** Constituted ad-hoc for 6-month engagements
  when the board identifies a specific topic that benefits from
  outside expertise. The maintainer typically nominates; the board
  ratifies.

Compensation for advisory-board service: no honoraria from the project
(the project does not have project-side funding for honoraria as of this
writing). Travel reimbursement for in-person meetings is contingent on
the project having grant funding for it; otherwise, all meetings are
remote.

## Decision scope

The advisory board has the following responsibilities, in increasing
order of authority:

1. **Advisory.** Comment on roadmap, weigh in on prioritization, surface
   operator-tier perspectives the maintainer would otherwise miss.
   Default mode for most decisions.

2. **Reviewing.** Sign off on any change that affects the public-facing
   contract:
   - License changes (must require unanimous board consent + a public
     comment period).
   - The COI policy and disclosure list.
   - Default behaviors for Scenario T (the CARE-Principles-aligned
     defaults are a board-reviewed area, not a unilateral maintainer
     call).
   - Federation protocol breaking changes.
   - Security disclosure handling.

3. **Deciding.** Direct authority over:
   - Maintainer-subject COI grievances. The maintainer recuses; the
     remaining board members decide.
   - Project shutdown / hand-off decisions, per
     `governance/platform-shutdown-data-portability-plan.md`.
   - Successor-maintainer appointment if the canonical maintainer
     steps away.

The maintainer retains direct authority over:

- Day-to-day code review and merge decisions.
- Implementation choices that don't affect the public-facing contract.
- Bug fixes and security patches (with after-the-fact board
  notification for security patches).
- Routine release management.

## Meeting cadence

- Quarterly synchronous meetings (90 minutes each).
- Monthly written status updates from the maintainer to the board.
- Asynchronous voting via the project's GitHub Discussions or a
  board-only mailing list for time-sensitive decisions.
- Annual review of board composition and recharter.

## Public transparency

- Board membership is public, listed in this document under "Current
  members" (a section that gets populated when the board is
  constituted).
- Meeting minutes are summarized publicly within 2 weeks of each
  meeting (sensitive HR or COI material redacted).
- Board votes that result in a public-facing contract change are
  published with the vote breakdown.

## Current members

(None yet — see "When to constitute the board" above.)

When the inaugural board is seated, this section will list each member's
name, the seat they hold, the start of their term, and a brief
disclosure pointer to `governance/coi-disclosures.md`.

## Why this is forward-looking, not currently active

The project's current size doesn't justify the overhead of running a
formal board. Constituting one prematurely would risk:

- Performative governance — going through the motions without genuine
  decision authority because there's nothing material to decide.
- Operator-tier under-representation — a board with a single operator
  representative for any tier is structurally weak.
- Maintainer paralysis — adding a 5-person consensus requirement when
  the project is still in heavy iteration would slow useful work.

The trigger conditions above are the indicators that the project is
ready. Until then, the maintainer takes the responsibility of acting on
the principles documented in this `governance/` directory as if a board
were watching, even though one isn't.
