# JACKPOT — CARE Principles and Tribal Data Sovereignty

## What CARE Principles are

The CARE Principles for Indigenous Data Governance are a complement to
the FAIR Data Principles, developed by the Global Indigenous Data
Alliance (GIDA) and published in 2020. They are:

- **C — Collective benefit.** Data ecosystems shall be designed and
  function in ways that enable Indigenous Peoples to derive benefit
  from the data.
- **A — Authority to control.** Indigenous Peoples' rights and
  interests in Indigenous data must be recognized; their authority to
  control such data must be empowered.
- **R — Responsibility.** Those working with Indigenous data have a
  responsibility to share how that data is used to support Indigenous
  Peoples' self-determination and collective benefit.
- **E — Ethics.** Indigenous Peoples' rights and well-being should be
  the primary concern at all stages of the data life cycle and across
  the data ecosystem.

FAIR (Findable, Accessible, Interoperable, Reusable) is about making
data *useful*. CARE is about making data *just*. They are intended to
be applied together, not in tension. The CARE preamble explicitly
states: "the FAIR Principles are necessary but not sufficient for
addressing Indigenous Peoples' rights and interests."

JACKPOT formally adopts both. This document walks through how each CARE
principle maps to specific JACKPOT architectural and default-behavior
decisions.

## The sovereignty policy set

CARE-aligned operation is a set of runtime policies, not a deployment
scenario. An operator picks the infrastructure shape that matches them —
usually A, self-hosted commodity — and enables the sovereignty policies
afterwards. ADR-0006 records that decision and supersedes the original
"Scenario T" design, in which sovereignty was an install-time scenario of
its own.

The intent the old design carried is preserved: an operator should not
have to remember to flip a series of toggles individually. The policies
below are meant to be enabled as a named set, defaulting to the
sovereignty-respecting position and requiring explicit configuration to
relax.

**Implementation status, measured 2026-09-03.** This table is a design
commitment. Four of these behaviours have no enforcement in the codebase
today, and the table says so per row rather than leaving the reader to
assume. Status is against `backend/backend/` and `cli/`; see
`B-CARE-CLAIMS-RECONCILE` and `B-SOVEREIGNTY-POLICY-PRESET`.

| Behavior | Default without the policy | Sovereignty-respecting position | Status |
|---|---|---|---|
| Sample auto-publish to NCBI/INSDC | Per sharing-level | OFF — explicit per-sample approval required | ❌ Not built — no reader for `auto_publish_to_insdc` |
| Federation peering | Off | Off — and federation discovery defaults to manual whitelist | 🔶 Partial — `whitelist:manage` and an allowlist projection exist; not expressed as policy |
| Sample sharing-level default | PRIVATE | PRIVATE, with sovereignty annotation visible at the access-request prompt | 🔶 Partial — sharing levels enforced; the annotation is not built |
| Data-back from external analysis | Per deployment | OFF by default | ❌ Not built |
| Deletion-on-request semantics | Soft-delete (`deleted_at` set) | Hard delete via tombstone-and-vacuum lifecycle | ✅ Built — `backend/backend/deletion.py`, wired into jobs and the authz reseed |
| Pipeline result retention | Per deployment | Per-pipeline configurable; default 1 year then archive | ❌ Not built |
| Audit log retention | 7 years | 7 years; never purged of *deletion events*, even after vacuum | 🔶 Partial — the audit trail is written on every state change (Critical Rule 4); there is no read path and no retention policy |

The one marked ✅ is the load-bearing one. ADR-0007 identifies Authority
to Control as the principle the schema must serve, because withdrawn-consent
data has to actually leave the system — which is why soft deletion alone is
insufficient and the tombstone-and-vacuum lifecycle exists.

There is not yet a mechanism that applies these as a named set.
`B-SOVEREIGNTY-POLICY-PRESET` covers it. Until then the individual
behaviours that exist are configured on their own, and the ones that do
not exist cannot be configured at all.

## C — Collective Benefit → JACKPOT defaults

**Principle.** Data should benefit the Indigenous community it derives
from, not just the researchers, agencies, or commercial entities that
analyze it.

**JACKPOT alignment.**

- **Citation defaults.** Deployments with the sovereignty policies enabled require citation
  attribution in any sample-export envelope (`benefits-sharing-
  framework.md`). The originating Tribe's name appears as a structured
  field, not as a free-text afterthought.
- **Data-back to source.** When a downstream analysis (typing,
  cluster assignment, AMR profile, novel-organism detection) is
  computed on a sample originating from such a deployment, the
  result flows back to the originating Tribe. The Tribe sees the
  result attached to its sample without having to harvest it from a
  paper.
- **Operator-side benefit-sharing policies.** These operators are
  encouraged to publish a deployment-local
  `docs/operator-benefits-sharing.md` describing how data benefits flow
  back to the Tribal community. The platform makes this discoverable
  via the deployment's `/about` page.

## A — Authority to Control → JACKPOT defaults

**Principle.** The Indigenous community must retain decision-making
authority over how data about them is collected, accessed, used,
shared, and retired.

**JACKPOT alignment.**

- **Tribal authority owns the deployment.** A sovereignty-policy deployment runs in
  infrastructure controlled by the Tribal authority, not in a
  centralized service. The serving Tribe holds the database, the
  storage, the OAuth provider, the encryption keys.
- **No auto-publish.** The defaults table above documents that
  These deployments never auto-publish samples to public
  repositories. Each export is an explicit decision, recorded with
  approver identity in the audit log.
- **Per-sample sharing-level granularity.** Even within such a
  deployment, individual samples can be marked PRIVATE, INTERNAL
  (across the deployment), CONSORTIUM (peers in a defined sharing
  agreement), or PUBLIC. The default is PRIVATE.
- **Federation off-by-default + manual whitelist.** Federation
  peering is off by default. When the Tribe enables it, peer
  discovery is manual (the Tribe approves each peer instance);
  there is no "discoverable by default" mode.
- **Deletion-on-request is real.** When a Tribal authority asks that
  a sample be deleted, the platform tombstones the sample (visible to
  the audit log as a deletion event) and then vacuums file URIs,
  storage objects, pipeline-result blobs, and cached artifacts. The
  audit log preserves the *fact* of the deletion (when, by whom, why)
  but not the deleted content. This is **not** the soft-delete pattern
  used in Scenarios A/B/C — it is hard delete from operator-side
  storage.

## R — Responsibility → JACKPOT defaults

**Principle.** Anyone working with Indigenous data has an active
responsibility to support Indigenous self-determination, not merely a
passive obligation to avoid harm.

**JACKPOT alignment.**

- **Pre-publish checklist.** These deployments include a
  pre-publish checklist that surfaces CARE-relevant questions before
  any public-repository submission: Has the Tribal Research Review
  Board (or equivalent) approved? Is the citation form correct? Is
  the post-publish data-back arrangement documented? The checklist is
  required, not optional, for their submissions.
- **Federation-aware deletion propagation.** When a Tribal authority
  deletes a sample, the deletion event propagates to any federation
  peers that received the sample. Peers are expected to honor the
  deletion within an SLA (default 30 days); peers that fail to honor
  are flagged for the Tribal authority's review.
- **Previously-published tag.** Samples that were exported before a
  deletion request are tagged "previously published" in the audit log.
  The tag persists past vacuum so the Tribal authority can track which
  external destinations may still hold derivatives, even if the
  internal record is gone.
- **Project-side responsibility.** The JACKPOT project commits to:
  - Engaging with CARE-Principles-trained reviewers (potentially
    external consultants) when handling sovereignty-relevant grievances
    (`access-grievance-procedure.md`).
  - Naming a Tribal/CARE seat on the future advisory board
    (`advisory-board.md`).
  - Never using these deployments as case studies, marketing
    references, or grant exhibits without explicit consent from the
    serving Tribe.

## E — Ethics → JACKPOT defaults

**Principle.** Indigenous Peoples' rights and well-being are the
primary concern at all stages of the data life cycle.

**JACKPOT alignment.**

- **Defaults that fail safe.** When an operator deployment-config is
  ambiguous, the platform defaults to the *more* restrictive
  interpretation under these policies. Example: if a sample's sharing-level
  is missing from a CSV import, the platform sets PRIVATE, not the
  permissive equivalent.
- **DLP-gate hard requirement.** These deployments cannot disable
  the DLP free-text scanner (Critical Rule 43). This is a structural
  protection against accidental PII leakage in metadata fields.
- **No leakage via derived data.** Pipeline results that include
  sample identifiers (cluster IDs, lineage assignments, etc.) are
  subject to the same sharing-level constraints as the source samples.
  The platform's federation-emit step strips identifiers in
  cross-jurisdiction exports unless the destination is on the manual
  whitelist for that level of detail.
- **Right to refuse without consequence.** A Tribal authority can
  decline any platform default, opt out of any feature, refuse any
  federation peer, and stop using the platform entirely without losing
  access to their accumulated data. The platform's data-portability
  guarantees (`platform-shutdown-data-portability-plan.md`) apply
  symmetrically — operators can leave as easily as they can stay.
- **No model-training use.** This data is never used by the
  project for model training, reference-dataset assembly, or any other
  project-side analytics. This is true for all scenarios but called
  out explicitly here because the temptation is highest for
  unique-data populations.

## What "Tribal authority" means in JACKPOT vocabulary

The platform's role-based access model maps to Tribal-sovereignty roles
as follows:

| Tribal role | JACKPOT role | Notes |
|---|---|---|
| Tribal Health Authority Director | Platform Admin | Full deployment authority |
| Tribal Research Review Board chair | Platform Admin or Lab Director | Reviews pre-publish checklist; can block submissions |
| Tribal lab clinical staff | Lab Collaborator | Day-to-day sample upload and analysis |
| Tribal lab data analyst | Data Analyst | Read access plus pipeline-launch authority |
| Tribal IT operator | Bioinformatics User | Infrastructure and pipeline maintenance |

The mapping is operator-configurable. It is not tied to an install
scenario: ADR-0006 makes sovereignty runtime policy, so the roles are
assigned in the running deployment rather than chosen at install. The default mapping above is a reference; serving Tribes are
expected to adapt it to their own organizational structure.

## What this document is not

This document is a project-side commitment to design the platform in a
CARE-aligned way. It is not legal advice for Tribal authorities choosing
to deploy JACKPOT, it is not a substitute for the serving Tribe's
internal IRB or research-review processes, and it is not an assertion
that JACKPOT-the-platform discharges any sovereignty obligation that
belongs to the operator. The serving Tribe holds the sovereignty; the
platform supports the exercise of it.

## Further reading

- Carroll and others (2020). "The CARE Principles for Indigenous Data
  Governance." *Data Science Journal*, 19(1): 43.
  https://doi.org/10.5334/dsj-2020-043
- Global Indigenous Data Alliance (GIDA). https://www.gida-global.org/
- US Indigenous Data Sovereignty Network. https://usindigenousdata.org/
- Native BioData Consortium. https://nativebio.org/
- Northwest Portland Area Indian Health Board (NPAIHB) Tribal
  Epidemiology Center model deployments — design partner candidates.

For the project's parallel North Star Architecture / CDC DMI alignment
analysis, see `docs/jackpot_cdc_dmi_stlt_overview.md §11` (CARE
Principles section). For the Pathoplexus governance-pattern parallel,
see `docs/jackpot_pathoplexus_loculus_overview.md §12.1`.
