# JACKPOT — Access and Grievance Procedure

## Scope

This document covers grievances about:

1. Access decisions made *by JACKPOT-the-software* — bugs, feature gaps,
   role-permission edge cases, sharing-level defaults that the
   complainant believes are wrong.
2. Governance decisions made *by the JACKPOT project* — feature
   prioritization, COI handling, operator-tier favoritism, license or
   contribution-policy disputes.
3. CARE-Principles or Tribal-sovereignty concerns specific to Scenario T
   deployments.

This document does NOT cover:

- Grievances about how a specific operator runs *their* JACKPOT
  instance. Those are between the complainant and the operator.
- Grievances about downstream platforms (NCBI, GISAID, Pathoplexus,
  etc.) that an operator submits data to. Those are between the
  complainant and the destination platform.

## Channels

In order of escalation:

1. **GitHub issue** at `Midnight-Oil-Innovation/jackpot/issues`. Public,
   discussable, and most effective for software bugs and feature
   requests. Use for category 1 grievances by default.

2. **Direct email** to the project's grievance contact (forthcoming;
   listed in `governance/coi-disclosures.md` once an advisory board is
   constituted). Use for category 2 grievances when public discussion
   would be inappropriate, and for category 3 grievances when the
   complainant prefers a non-public channel.

3. **Anonymous reporting form** (forthcoming, when the advisory board
   is constituted). Use when neither public discussion nor named-contact
   email feels safe.

4. **Advisory-board escalation** (forthcoming). For grievances that
   cannot be resolved through the maintainer channel, the advisory
   board provides an independent review.

## Response commitments

For category 1 (software):

- Acknowledgment within 1 week.
- Triage decision (accept / reject / need-more-info) within 2 weeks.
- For accepted issues, a target milestone or "no commitment yet" within
  4 weeks. The project does not commit to fix dates for free OSS work
  but does commit to being honest about whether and when work is
  planned.

For category 2 (governance):

- Acknowledgment within 1 week.
- A written response within 4 weeks — either resolution, escalation to
  the advisory board, or a documented reason the project cannot act.

For category 3 (CARE / sovereignty):

- Acknowledgment within 1 week.
- Direct engagement with a CARE-Principles-trained person on the
  project side (not necessarily a maintainer; the project commits to
  bringing in an external consultant if no maintainer has the relevant
  background).
- Resolution path agreed within 4 weeks.
- The project commits never to dismiss a Scenario T sovereignty
  grievance as "out of scope for the platform." If the platform's
  default behavior contributed to the grievance, the platform is the
  right place to fix it.

## What "resolution" can mean

- Code change that ships in a future release.
- Documentation change.
- Default-configuration change for the relevant scenario.
- Acknowledged-but-no-fix with a documented rationale and a path for
  the operator to work around it.
- Forwarding to the appropriate venue (e.g., a downstream-platform
  upstream issue) when the grievance is about something outside the
  project's scope.
- For category 2: a public statement of the decision and the reasoning,
  added to `docs/learnings.md`.

## Retaliation

The project commits not to take adverse action against anyone who files
a grievance in good faith. Adverse action includes (but is not limited
to) revoking commit access, blocking GitHub accounts, removing
attributions, or refusing to merge unrelated future contributions.

For Scenario T deployments where retaliation could include
withdrawal-of-support pressure on the originating Tribe, the project
explicitly disclaims any such leverage and commits to engaging via the
Tribal authority's preferred channel even if a grievance is active.

## Maintainer-side grievances

If a maintainer is the subject of a grievance, that maintainer recuses
themselves from the resolution process. Until the advisory board is
constituted, this means routing the grievance to a designated
non-maintainer reviewer (forthcoming). After the advisory board exists,
it handles maintainer-subject grievances.

## Public log

Resolved grievances are summarized (with personally identifying
information redacted unless the complainant explicitly opts in) in
`governance/grievance-log.md` (created when the first grievance is
resolved). This is to make the project's track record reviewable, not to
embarrass anyone.
