# Tribal authority deployment

## Who this is for

Tribal authorities that operate (or are building) public-health and
genomics capacity within the Tribe's own infrastructure and want
sovereignty-respecting defaults from the platform itself, not bolted on
afterward.

Most Tribal authority deployments run **Scenario T** — the
sovereignty-aware variant of Scenario A or E. Scenario T is the
single most important deployment shape for the project from a
sovereignty-and-ethics perspective and is treated as a first-class
scenario, not an edge case.

For the project's broader sovereignty alignment commitments, see
[`governance/care-principles-and-tribal-data-sovereignty.md`](../../../governance/care-principles-and-tribal-data-sovereignty.md).

## Fit rationale

Tribal authority deployments differ from state / territorial / local
deployments in ways that matter to the platform design:

- **The serving Tribe is sovereign.** Data ownership, access control,
  and benefits-sharing decisions belong to the Tribal authority, not
  to a federal or state agency. The platform's defaults must support
  that, not subtly undermine it.
- **Trust-and-verify partnerships.** Tribes that have had data taken
  and used without consent in the past (the field has a long history
  here) are reasonably wary. The platform's commitments need to be
  evident in defaults, not buried in option flags.
- **Capacity varies.** Some Tribes (Navajo Nation, Cherokee Nation,
  larger Pacific Northwest tribes) have substantial in-house data
  and bioinformatics capacity. Smaller Tribes may rely on Tribal
  Epidemiology Centers (see `tribal-epidemiology-center.md`) or on
  contracted bioinformatics services. JACKPOT must be deployable at
  either end.
- **Federal funding patterns are different.** Tribal authorities
  access funds through IHS, through Self-Determination Act 638
  contracts, through TECPHI (for TECs), and through a different
  ELC/PHIG flow than state agencies.

JACKPOT's Scenario T defaults are designed to make the platform
*usable* for a Tribal authority that has decided to take on pathogen-
genomics work, without requiring the authority to spend weeks
configuring sovereignty-protections that should have been on by
default.

## Install steps

1. **Pre-engagement.** Before any deployment work: talk to the
   project maintainers about the Scenario T defaults. The defaults
   are documented (see the CARE-Principles doc) but the project
   commits to direct engagement with any Tribal authority deploying
   Scenario T to confirm the defaults fit and to surface anything
   that should be different.

2. **Decide A vs E.** If you're a single Tribal Health Department
   running pathogen genomics standalone, that's Scenario A flavored
   T. If you're peering with a TEC or with other Tribes' instances,
   that's Scenario E flavored T.

3. **Provision your own infrastructure.** Tribal authority
   deployments run on infrastructure controlled by the Tribe. This
   can be on-prem, in a Tribal-owned cloud account, or in a cloud
   account contracted to a vendor that serves under the Tribe's
   data-handling rules. The reference Terraform under `deploy/`
   targets GCP; AWS and Azure equivalents are community-buildable
   and on the project backlog.

4. **Run `jackpot init` and select Scenario T.** This is critical.
   Scenario T configures the deployment with sovereignty-aware
   defaults at install time. If you select A or E and try to add
   the sovereignty defaults afterward, you'll likely miss some.

5. **Configure your Tribal Research Review Board (or equivalent).**
   The platform's pre-publish checklist asks for the TRRB's approval
   reference (a ticket ID, a meeting-minutes pointer, a research
   protocol number — whatever your TRRB uses). The platform does not
   try to replicate or replace the TRRB; it just makes sure the
   approval reference is captured before any external submission.

6. **Decide on federation peers (Scenario E flavored T only).**
   Scenario T defaults federation OFF. If you intend to peer with a
   TEC or with other Tribes, manually whitelist each peer instance
   after explicit agreement. There is no auto-discovery in Scenario T.

7. **Configure deletion-on-request workflow.** Scenario T uses
   tombstone-and-vacuum (hard delete from operator-side storage with
   only an audit trail of the *fact* of deletion). Decide who in
   the Tribal authority can approve deletion requests; configure the
   approver list in `jackpot init`.

8. **Document operator-side benefits-sharing.** Write your
   deployment's `docs/operator-benefits-sharing.md` describing how
   the Tribe receives benefits from data analyses (citation
   requirements, data-back arrangements, collaboration controls).

## Governance and data handling

This section is the most important in this guide.

- **Sample auto-publish to NCBI/INSDC:** OFF by default. Each export
  to a public repository is an explicit per-sample decision, with
  TRRB-approval reference recorded. There is no "publish all samples
  with sharing-level public" auto-batch in Scenario T.
- **Federation peering:** OFF by default. Manual whitelist only. No
  auto-discovery.
- **Sharing-level default:** PRIVATE, with sovereignty annotation
  visible at any access-request prompt.
- **Data-back from external analysis:** OFF by default. The Tribal
  authority decides per sample whether to subscribe to NCBI Pathogen
  Detection cluster updates / Pathogenwatch typing / etc.
- **Deletion-on-request:** Tombstone-and-vacuum (hard delete from
  operator-side storage). The audit log preserves the *fact* of the
  deletion (when, by whom, why) but not the deleted content. This
  is *not* the soft-delete pattern in Scenarios A/B/C.
- **Federation-aware deletion:** When federation is enabled and a
  sample has been shared with peers, deletion at the home instance
  propagates to peers as a deletion command. Default SLA: 30 days.
  Peers that fail to honor are flagged for the Tribal authority's
  review.
- **Pre-publish checklist:** Required (not optional) for any external
  submission. Captures TRRB approval reference, citation form, and
  post-publish data-back arrangement.
- **Previously-published tag:** Samples that were exported before a
  deletion request retain a "previously published" tag past vacuum,
  so the Tribal authority can track which external destinations may
  still hold derivatives.
- **DLP gate:** ON, and cannot be disabled in Scenario T.
- **No model-training use:** Tribal data is never used by the project
  for training models, building reference datasets, or any other
  project-side analytics. (True for all scenarios; called out
  explicitly here.)
- **Audit log retention:** 7 years minimum. Deletion events are never
  purged from the audit log even after the underlying sample is
  vacuumed.

## Funding sources

| Source | Eligibility | Use | Fit |
|---|---|---|---|
| **IHS direct service / Self-Determination Act 638** | Tribal authorities | Healthcare and public health | ✅ Direct fit for Tribe-deployed JACKPOT |
| **TECPHI (Tribal Epi Center PH Infrastructure)** | TECs (passed through to Tribes if the TEC supports Tribal deployments) | Public health capacity, data systems | ✅ Indirect fit |
| **CDC cooperative agreements specific to Tribal Nations** | Tribal authorities | Various | ✅ Variable; some lines exist |
| **ELC (when Tribal Nation receives directly)** | Eligible Tribal authorities | Lab capacity | ✅ When applicable |
| **Tribal own funds** | Self | Anything | ✅ Variable by Tribe |
| **Foundation funding (Doris Duke, RWJF, Wellcome)** | Various | Open-source infrastructure, sovereignty research | ✅ Possible for grant-focused deployments |

## Workforce considerations

The workforce capacity question matters more for Tribal authority
deployments than for state deployments because the operator-side team
is often smaller and the project-side maintainer cannot reasonably
"escalate to the on-call rotation" the way a vendor would.

- **Bioinformatics staff:** 0.25–1 FTE depending on Tribe size and
  sequencing volume.
- **Data sovereignty / TRRB liaison:** 0.1–0.25 FTE for the
  pre-publish checklist workflow.
- **IT operations:** 0.25–0.5 FTE for a managed-cloud deployment;
  more for on-prem.
- **Project maintainer engagement:** The project commits to engaging
  directly with Scenario T deployments at install time and on
  governance-relevant decisions. This is in addition to (not instead
  of) the deployment's own IT capacity.

## Common pitfalls

- **Selecting Scenario A and trying to retrofit sovereignty
  defaults.** Use Scenario T from the start. Retrofitting defaults
  is error-prone — easy to miss a flag.
- **Treating federation as "off" in name only.** Scenario T's
  federation-off default is meaningful: if you enable peering, do
  it deliberately, document the peer approval, and make sure your
  deletion workflow propagates.
- **Underestimating the pre-publish checklist's value.** It feels
  like overhead when sequencing volumes are small. It pays off when
  an audit later asks "what authorized this submission?" and you
  have a full chain.
- **Skipping the project-side engagement at install.** The project
  maintainers commit to engaging with Scenario T installs because
  the defaults need to fit your specific Tribal authority's
  governance structure. Use that engagement.

## Pilot partnerships

The project actively seeks Tribal-authority and TEC pilot partners.
The Northwest Portland Area Indian Health Board (NPAIHB) — and through
them, member Tribes in the Pacific Northwest — is named in the
project's design documents (`docs/jackpot_cdc_dmi_stlt_overview.md
§11`) as a pilot candidate. If your Tribe is interested in piloting,
the project welcomes a conversation.

## Further reading

- `governance/care-principles-and-tribal-data-sovereignty.md` — the
  full mapping from CARE Principles to JACKPOT defaults.
- `docs/jackpot_cdc_dmi_stlt_overview.md §6` and §7 — the
  architectural reasoning behind the Scenario T defaults.
- Carroll and others (2020). "The CARE Principles for Indigenous Data
  Governance." *Data Science Journal*, 19(1): 43.
- Native BioData Consortium — https://nativebio.org/
