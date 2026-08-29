> **Status:** Reference — STLT deployment guide for Tribal Epidemiology Centers.

# Tribal Epidemiology Center deployment

## Who this is for

The 12 Tribal Epidemiology Centers (TECs) recognized by the Indian
Health Service. TECs serve member Tribes within their region with
public-health surveillance, data analysis, and epidemiology capacity.

The natural deployment shape for a TEC running JACKPOT is **Scenario
E (federation member)** with sovereignty-aware Scenario T defaults
applied — i.e., the TEC instance acts as a federation hub, and member
Tribes that want to participate run their own Scenario T instances
that peer with the TEC.

This pattern is documented in detail in
`docs/jackpot_cdc_dmi_stlt_overview.md §8` ("The TEC federation
pattern").

## Fit rationale

A TEC has structural attributes that make it well-suited as a
federation hub:

- **Established trust relationships** with member Tribes. Tribes that
  would not federate with a state health department or with CDC
  directly may federate with their TEC because the TEC is part of the
  Tribal-sovereignty support infrastructure.
- **Existing data-modernization capacity.** Several TECs (NPAIHB,
  Great Plains TEC, Southern Plains TEC) have substantial
  data-systems teams; running a federation hub is a fit for that
  capacity.
- **Cross-Tribe analysis use cases.** Outbreak investigations,
  surveillance reporting, and capacity-building research are
  inherently cross-Tribe; federation lets analysis happen without
  centralizing data.

For member Tribes, the TEC-federated pattern means:

- A Tribe can decide to participate or not, on a per-sample basis,
  with controls in their own Scenario T instance.
- The Tribe's data lives in the Tribe's infrastructure; the TEC sees
  what the Tribe shares.
- Deletion at the Tribe's instance propagates to the TEC's view via
  federation-aware deletion.

## Install steps

1. **Pre-engagement.** Before deployment, the TEC and the project
   should agree on the federation contract: what sample categories
   are eligible, what the deletion-propagation SLA is, what the
   citation-and-attribution form is, and how disagreements are
   handled.

2. **Provision the TEC-side infrastructure.** Cloud or on-prem,
   sized for hub-scale traffic (the TEC is receiving from N member
   Tribes, so the inbound bandwidth and storage budget is roughly
   N times a single Tribe's). The reference Terraform's
   state-deployment sizing is a reasonable starting point, scaled
   by member Tribe count.

3. **Run `jackpot init` and select Scenario E with Scenario T
   sovereignty defaults applied.** This is a hybrid; the install
   flow has explicit support. The TEC instance configures itself as
   federation-receiving capable but federation-discoverable only
   to manually-approved Tribal peers.

4. **Configure the federation peer-approval workflow.** Each member
   Tribe that wants to participate must be manually approved; the
   approval includes the contract reference (point 1).

5. **Set up the surveillance-reporting pipelines.** The TEC's
   downstream consumers (CDC programs, regional public-health
   collaboratives, member-Tribe-facing reports) typically have
   existing data formats. The TEC-side pipeline maps JACKPOT data
   to those formats.

6. **Configure the cross-Tribe analysis access controls.** A TEC
   analyst running an outbreak investigation across N Tribes' shared
   samples needs an explicit grant from each Tribe per use case —
   not blanket access. The platform's `sample_access` workflow
   supports this; configure your TEC's approval-of-access SLA.

7. **Document the TEC-Tribe federation contract.** Write a
   deployment-local `docs/tec-federation-contract.md` describing
   the federation terms in plain language. Member Tribes review and
   agree to this before peering.

## Governance and data handling

- **TEC instance defaults:** Scenario E with Scenario T overlays.
  Sample auto-publish OFF; deletion-on-request honored from any
  peer; pre-publish checklist required.
- **Federation peer model:** Manual whitelist only. New peer
  approvals go through a TEC-internal review (the TEC's data
  governance committee, typically).
- **Cross-Tribe analysis:** Per-sample access requests, not blanket.
  Even within a federation, individual Tribes retain authority to
  approve specific analyses.
- **Deletion propagation:** When a member Tribe deletes a sample,
  the TEC instance receives the deletion command and tombstone-and-
  vacuums its own copy within the federation SLA (default 30 days).
  The TEC retains a "previously held" audit record but not the
  content.
- **Reporting to CDC and other downstream consumers:** The TEC
  decides what aggregations are appropriate, with the consent of
  member Tribes for any sample-level disclosure. Aggregated
  surveillance data flows out per the TEC's existing CDC reporting
  agreements.
- **DLP gate:** ON, cannot be disabled.
- **Audit log retention:** 7 years minimum; deletion events
  permanently retained.

## Funding sources

| Source | Eligibility | Use | Fit |
|---|---|---|---|
| **TECPHI (Tribal Epi Center PH Infrastructure)** | All TECs | Public health capacity, data systems | ✅ Direct fit — primary line for TEC infrastructure |
| **CDC cooperative agreements with TECs** | All TECs | Surveillance, data systems | ✅ Direct fit |
| **IHS line items** | TECs through IHS | Various | ✅ Variable by TEC and year |
| **TECPHI passed through to member Tribes** | Member Tribes | Public health capacity | ✅ Indirect fit for the Tribe-side instance |
| **Foundation funding** | Various | Open source, capacity building | ⚠️ Possible for specific initiatives |

## Workforce considerations

- **Federation-hub operations:** 0.5–1 FTE. The hub does more than
  a single-Tribe instance because it's the integration point for
  member Tribes' data flows.
- **Cross-Tribe analyst capacity:** Variable — 1–3 FTE depending on
  the TEC's analytical mission.
- **Member-Tribe liaison:** 0.25–0.5 FTE for relationship and
  governance work with member Tribes that participate.
- **Data sovereignty / contract management:** 0.1–0.25 FTE for the
  per-Tribe federation contracts.

## Common pitfalls

- **Treating federation as a one-way data flow into the TEC.**
  Federation is bidirectional: the TEC's analyses flow back to
  member Tribes too. The data-back-from-analysis arrangement is part
  of the federation contract.
- **Skipping the per-Tribe contract.** "Standardizing" the
  federation terms across Tribes feels efficient but undercuts each
  Tribe's authority to set its own terms. Negotiate per Tribe.
- **Underbuilding the deletion propagation.** The federation-aware
  deletion is the most important mechanical commitment to member
  Tribes. Test it before going live; build alerting for SLA
  violations.
- **Letting the TEC's analytical needs drive defaults.** The hub's
  analytical convenience is not a justification for defaults that
  weaken member-Tribe controls. Defaults stay sovereignty-respecting
  even when the TEC analyst would prefer easier access.

## Pilot partnerships

NPAIHB (Northwest Portland Area Indian Health Board) is named in the
project's design documents as a pilot candidate. The pilot would
exercise the federation pattern with a small number of Pacific
Northwest member Tribes to validate the deletion-propagation SLA, the
per-Tribe contract workflow, and the cross-Tribe analysis access
controls.

## Further reading

- `governance/care-principles-and-tribal-data-sovereignty.md`
- `docs/jackpot_cdc_dmi_stlt_overview.md §8` — TEC federation pattern
- `docs/deploy/stlt/tribal-authority.md` — the member-Tribe-side guide
