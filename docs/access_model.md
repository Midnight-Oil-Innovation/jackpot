> **Status:** Reference - access control model.

# JACKPOT — Access Model

**Document type:** Canonical authorization design.
**Audience:** primarily the implementer (build-against reference); secondarily external collaborators (cryptWWDB and immune-platform research groups) evaluating whether JACKPOT's access model fits their use cases.
**Status:** Design — north-star model. Implementation is staged across phases (see §11). This document describes the target model in full; the running code catches up to it over time.

> **Relationship to the current code.** As of this writing, authorization lives in a ~60-line attribute ladder in `backend/auth/permissions.py` plus two boolean flags (`is_platform_admin`, `is_data_analyst`) and per-lab `lab_membership` rows carrying one of six APGAP-inherited permission groups. That model was built for a single-organization clinical-genomics lab hierarchy. This document replaces it wholesale with a capability-first model designed for JACKPOT's actual requirements: federation between independent instances, multi-tenancy, surveillance anomaly triage, encrypted multi-party computation, and runtime sovereignty policy. The migration is greenfield (§10) — the APGAP role names are not preserved.

---

## 1. Why this exists

### 1.1 The problem with the inherited model

JACKPOT inherited its authorization model from APGAP, its pre-independence predecessor. That model is **role-first**: a user *is* a Lab Director, or *is* a Bioinformatics User, and the role bundles a fixed set of permissions. Two global boolean flags (`is_platform_admin`, `is_data_analyst`) sit above six per-lab permission groups (Platform Admin, Lab Director, Lab Collaborator, Lab Reader, Bioinformatics User, Data Analyst).

This worked when JACKPOT was a single organization's sequencing-and-analysis platform. It breaks as soon as you try to express the capabilities JACKPOT now needs:

- **"Receives federation requests from a peer instance"** — is that a Lab function or a Platform Admin function? Neither fits. It is not a property of any *person's role*; it is a capability exercised at a particular scope on behalf of a relationship between two instances.
- **"Reviews surveillance anomalies the immune platform flagged"** — the closest existing role is the global `is_data_analyst` flag, but that flag only grants cross-lab read of surveillance-relevant samples. It says nothing about anomaly triage, and bolting anomaly-triage onto the data-analyst flag would conflate two unrelated concerns.
- **"Computes on encrypted data it cannot read"** (the cryptWWDB third-party lab) — there is no role for "software that writes pipeline results but must never see source samples." Faking it with a human user account would over-privilege the automation.

Each new capability tempts a new role, and role-first models respond to that pressure with **role explosion**: a combinatorial sprawl of roles like `LabDirectorWhoAlsoReviewsFederation` or `DataAnalystWithAnomalyTriage`. The roles stop being meaningful identities and start being arbitrary permission buckets with confusing names.

### 1.2 What JACKPOT actually needs

The requirements that the inherited model cannot express cleanly:

1. **Multiple kinds of actor.** Humans, peer JACKPOT instances, and non-human service credentials (pipeline workers, SDK/CLI sessions, the cryptWWDB lab) all make authenticated requests. A model that assumes every requester is a human-with-a-role cannot represent the others without hacks.
2. **More scopes than global-and-lab.** Access decisions happen at the level of the whole instance, an organization, a lab, a project, and an individual sample — and, with multi-tenancy, an isolation boundary that walls organizations off from each other inside a shared deployment.
3. **Federation that is finer than instance-to-instance.** Two instances peering must not imply that every lab in one can see every lab in the other. Sharing has to be scoped and conditional.
4. **Sovereignty as enforceable policy.** Indigenous-data-sovereignty constraints (deletion-on-request, no-auto-publish, federation-off-by-default, CARE-Principles compliance) must be *unoverridable* access constraints, not documentation or convention.
5. **Capabilities that are not roles at all.** Some "capabilities" are automation behaviors (the immune platform emitting an anomaly; the federation receiver auto-evaluating qualification gates) that no principal "holds." Forcing these into a role model is a category error.

### 1.3 The shape of the solution

JACKPOT adopts a **capability-first, attribute-based access model**:

- Access is computed by a single pure function, `permit(principal, capability, resource, context) → ALLOW | DENY` (§5), evaluated against the *attributes* of all four inputs.
- **Capabilities** are fine-grained verbs (`sample:read_detail`, `federation:push`, `anomaly:triage`) granted to principals **at a scope** (§4).
- **Roles do not exist as a thing the engine checks.** "Roles" survive only as **presets** — named bundles of (capability, scope-template) pairs offered for provisioning convenience (§8). The engine never asks "what role is this principal?"; it asks "does this principal hold this capability at a scope that covers this resource, and do the applicable attribute-policies permit it?"
- **Deny always wins** (§5.4). Any applicable policy that denies makes the decision DENY, with no override mechanism. Sovereignty and isolation denials are therefore unconditionally unoverridable by construction.

The design rule we followed, and that future changes should follow: **design the capabilities (the verbs) and the scopes first; let the roles fall out last as convenience bundles.** Starting from "what do we call people" is the trap that produced the APGAP sprawl.

---

## 2. Core abstractions

Five concepts carry the entire model: **Principal**, **Capability**, **Scope**, **Resource**, and **Policy**. The decision function (§5) is a pure function of these. This section defines each at the schema level — the shapes the implementation builds against — without yet specifying storage tables (those come in the migration plan, §10) or the decision control flow (§5).

### 2.1 Principal — the *who*

A **principal** is any authenticated entity that makes a request the engine evaluates. There are three *kinds*, but they share one shape, and the engine never branches on kind — it reads attributes and capability grants identically for all three. This is the **unified principal abstraction**: one concept, one decision path, no per-kind special-casing.

| Kind | Authenticated by | Examples |
|---|---|---|
| `HUMAN` | Google OAuth → JWT cookie | A person triaging anomalies, a lab lead approving submissions |
| `PEER_INSTANCE` | `X-JACKPOT-Federation-Key` | Another JACKPOT instance pushing a federation request |
| `SERVICE` | pipeline-token / API token | A Nextflow weblog poster, the cryptWWDB third-party lab, an SDK/CLI session |

A principal carries:

```
Principal:
    id:            PrincipalId            # stable identifier
    kind:          HUMAN | PEER_INSTANCE | SERVICE
    grants:        list[CapabilityGrant]  # what it can do, and at what scope
    attributes:    dict[str, Any]         # everything the engine reads to decide
    on_behalf_of:  PrincipalId | None     # for SERVICE / PEER_INSTANCE acting for another
```

- **`grants`** is the principal's set of capability grants (§2.2). A human's grants come from their preset assignments (e.g. "Lab Lead @ lab 7"); a peer instance's grants come from sharing agreements (§7); a service principal's grants are minted narrow and explicit when its token is issued.
- **`attributes`** is the open bag the attribute-policies (§2.5) read. For a human it holds things like `org_id`, `lab_memberships`, `is_active`. For a peer instance it holds `peering_id`, `origin_instance`. For a service principal it holds `token_scope`, `on_behalf_of`. The engine does not enumerate a fixed attribute set — policies declare which attributes they read.
- **`on_behalf_of`** expresses delegation. The cryptWWDB lab is a `SERVICE` principal whose `on_behalf_of` points at the computation/relationship it serves; the result it writes is owned by the data owner, not by the lab. The audit log reads `on_behalf_of` so delegated actions are attributable to both the acting credential and the principal it acted for.

The payoff of unification: "a service principal acting on behalf of a federation relationship" — the exact cryptWWDB case — is expressible because `SERVICE`-ness and federation-relationship-ness are both just attributes on one principal shape, evaluated by one engine. There is no separate "service auth subsystem" and "federation auth subsystem" that must be kept in sync.

### 2.2 Capability — the *what*

A **capability** is a fine-grained verb naming one action, in the form `domain:action`. It is the atomic unit of permission. Capabilities are **not** held in the abstract — they are held *at a scope*, via a **CapabilityGrant**.

```
Capability:  str   # canonical "domain:action" identifier, e.g. "sample:read_detail"

CapabilityGrant:
    capability:  Capability
    scope_ref:   ScopeRef          # the scope at which this grant applies (§2.3)
    conditions:  list[Condition]   # optional attribute-conditions that further constrain it
    source:      GrantSource        # how the principal came to hold it (preset | agreement | direct)
```

- A grant ties one capability to one scope. "Lab Lead @ lab 7" expands into many grants, each pairing one capability (`sample:update`, `submission:approve`, …) with `scope_ref = lab:7`.
- **`conditions`** let a grant carry its own attribute-filters, used heavily by federation sharing agreements (§7) — e.g. a `federation:push` grant conditioned on `surveillance_relevant = TRUE AND contains_pii = FALSE`. Conditions on a grant are evaluated as part of the decision (§5) and compose with global attribute-policies.
- **`source`** records provenance for audit and revocation: `preset` (came from a role-preset assignment), `agreement` (came from a federation sharing agreement), or `direct` (granted explicitly to this principal).

The full capability catalog — the canonical verb list, organized by plane (sample, pipeline, federation, anomaly, governance) — is §4. Two properties to note now:

- **Some actions are deliberately *not* capabilities.** Automation behaviors — the immune platform *emitting* an anomaly, the federation receiver *auto-evaluating* qualification gates — are subsystem behaviors, not capabilities any principal holds. Only the *human-facing* halves (`anomaly:triage`, `federation:review_request`) are capabilities. Modeling automation as a capability would be a category error (no principal "holds" the right to have the system run its own scheduled logic).
- **Capabilities are additive only.** Holding a capability never *removes* access. All subtraction happens through policy denials (§2.5, §5.4). This keeps grant reasoning monotonic: adding a grant can only widen access, and the only thing that narrows it is a deny-policy.

### 2.3 Scope — the *where*

A **scope** is a node in JACKPOT's containment hierarchy. Capabilities are granted at a scope and **inherit downward**: a grant at lab scope applies to every project and sample under that lab. The scope tree (detailed in §3):

```
Instance → Org → Lab → Project → Sample
```

```
ScopeRef:
    level:  INSTANCE | ORG | LAB | PROJECT | SAMPLE
    id:     int | None     # the concrete entity id at that level; None only for INSTANCE-singleton

ScopeNode:
    ref:        ScopeRef
    parent:     ScopeRef | None    # None only for the Instance root
    # the tree is materialized so "does scope X contain scope Y?" is a cheap ancestor check
```

- A grant's `scope_ref` names the level and entity at which the capability applies.
- **Containment is the core relation.** The decision function asks: *is this capability granted at any scope that contains (or equals) the resource's scope?* "Contains" is ancestor-or-self in the tree. A grant at `org:3` covers a sample whose lab's org is 3; a grant at `sample:55` covers only sample 55.
- **Org is the isolation boundary.** Multi-tenancy (P0c) is implemented as org-level isolation: a principal's reachable scope subtree is bounded by its org unless a sharing agreement (§7) explicitly bridges to another instance. (Tenant and Org are the same concept in this model — see §3.2.)

### 2.4 Resource — the *thing being acted on*

A **resource** is whatever the capability acts upon. Every resource has a position in the scope tree (so the engine can ask the containment question) plus its own attributes (so attribute-policies can read it).

```
Resource:
    type:        str             # "sample", "submission", "pipeline_run", "federation_request", ...
    id:          int | str
    scope_ref:   ScopeRef        # where this resource sits in the tree
    attributes:  dict[str, Any]  # everything policies read: sharing_level, surveillance_relevant,
                                 # contains_pii, organism, deletion_status, owner_id, ...
```

A sample's `attributes` carries the fields today's `_base_access` ladder reads (`sharing_level`, `surveillance_relevant`, `owner_id`) plus the new ones the model needs (`deletion_status`, `contains_pii`, `origin_instance` for federated data). The resource's `scope_ref` is what the containment check uses; its `attributes` are what the attribute-policies (§2.5) read.

### 2.5 Policy — the *contextual rules*

A **policy** is a rule evaluated against the attributes of (principal, capability, resource, context). Policies are how the model expresses everything that is **not** pure structural scope-grant logic: sharing-level visibility, surveillance cross-lab read, sovereignty constraints, tenant isolation, federation conditions.

```
Policy:
    id:         str
    applies_to: Predicate          # when this policy is in play (matches on capability, resource type, ...)
    effect:     ALLOW | DENY
    rule:       Predicate          # evaluated against (principal, capability, resource, context) attributes
    rationale:  str                # human-readable "why this policy exists" (surfaced in audit/denials)
```

Two effects, with strict precedence (§5.4):

- A **DENY** policy that fires makes the whole decision DENY. No grant and no ALLOW policy can override it. This is how sovereignty and isolation become unconditionally enforceable: they are DENY policies, and deny always wins.
- An **ALLOW** policy can grant a path the scope-grants alone would not — e.g. "a `PUBLIC` sample is readable by anyone" is an ALLOW policy keyed on `resource.sharing_level == 'PUBLIC'`, independent of whether the principal has any scope grant. This is how the permissive parts of today's `_base_access` ladder (PUBLIC, DISCOVERABLE, surveillance-relevant) carry over.

The decision function combines scope-grants and policies into one verdict (§5). The mental split: **scope-grants answer "is this principal structurally entitled here?"; policies answer "does the context permit or forbid it regardless?"** Today's `_base_access` is exactly this split avant la lettre — ownership/lab/project membership are proto-scope-grants; PUBLIC/DISCOVERABLE/surveillance are proto-attribute-policies. The model makes the split explicit and extends it to federation, sovereignty, and tenancy.

### 2.6 Context — the *ambient request facts*

The fourth argument to `permit()` is **context**: ambient facts about the request that are neither principal nor resource. It is a flat attribute bag policies may read.

```
Context:
    now:               datetime          # for time-bounded grants / expiry
    request_origin:    LOCAL | FEDERATION # did this arrive via a federation channel?
    origin_instance:   InstanceId | None  # which peer, if FEDERATION
    sovereignty_mode:  bool               # is sovereignty-runtime-policy active on this instance?
    attributes:        dict[str, Any]     # extension point
```

Context is what lets the *same* capability check resolve differently depending on how the request arrived. A `sample:read_detail` from a local human and the "same" read arriving over a federation channel are distinguished by `context.request_origin` and evaluated against different policies (the federation path must match a sharing agreement; the local path need not).

---

## 3. The scope tree

### 3.1 The hierarchy

```
Instance
   └─ Org            ← isolation boundary (= "tenant"); owns labs and users
        └─ Lab       ← the workhorse scope; owns projects
             └─ Project   ← groups samples
                  └─ Sample   ← the leaf resource
```

Each level contains the levels beneath it. A capability granted at a level applies to that node and everything under it (downward inheritance). The decision function's structural question is always "is the capability granted at an ancestor-or-self scope of the resource?"

| Level | What it is | What it owns | Typical grant target |
|---|---|---|---|
| **Instance** | One running JACKPOT deployment (one database, one URL). The unit of *operation*. Federation peers attach here. | Orgs | Instance-wide capabilities (administer the deployment, review inbound federation, surveillance oversight) |
| **Org** | An organization inside the instance; the isolation boundary. The unit of *ownership and isolation*. | Labs, users | Org-wide administration |
| **Lab** | A working unit within an org. The most common scope for day-to-day grants. | Projects | Lab leadership, lab membership |
| **Project** | A grouping of samples within a lab (the Seqera-derived org/lab/project hierarchy). | Samples | Project-scoped collaboration; per-project federation agreements |
| **Sample** | The leaf data resource. | — | Per-sample access grants (the existing `sample_access_grants` mechanism) |

### 3.2 Why Tenant and Org are the same concept

Earlier drafts of this model treated "tenant" (the multi-tenancy isolation boundary) and "org" (the ownership entity) as separate layers. They are collapsed into one: **the Org *is* the isolation boundary.** "Multi-tenancy" means one Instance hosts multiple Orgs, each walled off from the others; the P0c multi-tenancy middleware enforces that wall at the Org level.

The collapse is justified because in every JACKPOT deployment scenario, the isolation boundary and the ownership entity coincide — a hosted-SaaS customer is exactly one org and is exactly one isolation domain. Keeping them separate would add a layer that is always 1:1 with org, which is pure ceremony. (If a future "consortium tenant containing multiple distinct orgs that share an isolation boundary" requirement ever appears, the model can reintroduce a Tenant level above Org without disturbing anything below it — but we are not paying for that layer speculatively.)

### 3.3 How deployments populate the tree

The same tree describes every deployment; the layers simply collapse or spread depending on scenario.

**Laptop (Scenario A, single-user):** one Instance, one Org, a lab or two. Instance ≈ Org in practice — there is exactly one of each, so the upper layers are present in the model but invisible in use.

```
Instance: laptop
└─ Org: "My Lab"
   ├─ Lab: Sequencing
   └─ Lab: Bioinformatics
```

**Single agency (Scenario A at agency scale / single-org cloud):** one Instance, one Org, several labs the agency oversees. The **Lab** scope now does real work — Virology members do not automatically see Bacteriology's in-progress samples.

```
Instance: agency-cloud
└─ Org: "State Public Health Dept"
   ├─ Lab: Virology
   ├─ Lab: Bacteriology
   └─ Lab: Wastewater Surveillance
```

**Hosted SaaS (Scenario C, cloud, multi-org):** one Instance hosts multiple isolated Orgs. The **Org isolation boundary** is the load-bearing scope — County A must never see County B's data, users, or existence. P0c middleware filters every query by the requesting principal's Org.

```
Instance: jackpot-saas-prod        (one deployment, one database)
├─ Org: "County A Health"          ← isolation boundary
│  ├─ Lab: County A Clinical
│  └─ Lab: County A Wastewater
└─ Org: "County B Health"          ← isolation boundary
   └─ Lab: County B Clinical
```

**Two agencies federating (multiple Instances):** two completely separate deployments — two databases, two URLs, two scope trees. There is **no shared scope above Instance.** The only thing connecting them is a federation peering relationship (§7); one instance appears inside the other's world only as a `PEER_INSTANCE` principal, never as a branch of its scope tree.

```
Instance: state-a-jackpot              Instance: state-b-jackpot
└─ Org: "State A PH"                    └─ Org: "State B PH"
   ├─ Lab: Virology                        ├─ Lab: Virology
   └─ Lab: Wastewater                      └─ Lab: Sequencing

        └────────── federation peering ──────────┘
                (no shared scope; a relationship, not a branch)
```

This last case is the crux of the federation design and the reason federation cannot be modeled as a scope-tree relationship: peering crosses *between* two independent trees rather than living *inside* one. §7 develops this as the two-layer model (peering channel + scoped sharing agreements).

---

## 4. Capability catalog

This section enumerates a **representative** set of capabilities, organized by plane. It is not exhaustive — greenfield means the precise list will shift as the implementation teaches us what's actually needed, and an over-specified catalog rots (the lesson of the APGAP role names). The exhaustive implementation-time checklist is the existing `AuditActions` taxonomy in `backend/audit.py` (~70 actions); this catalog establishes the *pattern* and covers the cases that drove the redesign.

Each capability is `domain:action`. Where a capability mutates state, the table notes the corresponding **audit action** it must emit — tying authorization to audit at design time, so no capability ships without an audit trail. Read-only capabilities have no audit action (reads are not audited as state changes).

### 4.1 Sample / data plane

| Capability | Meaning | Audit action |
|---|---|---|
| `sample:read` | See a sample in a list (list-level visibility) | — |
| `sample:read_detail` | Read full sample detail (the `can_access_sample` level) | — |
| `sample:read_surveillance` | Cross-scope read of `surveillance_relevant` samples (replaces the global `is_data_analyst` flag) | — |
| `sample:create` | Create a sample | `CREATE_SAMPLE` |
| `sample:update` | Edit sample metadata | `UPDATE_SAMPLE` |
| `sample:archive` | Archive a sample | `ARCHIVE_SAMPLE` |
| `sample:soft_delete` | Soft-delete (recoverable) | `SOFT_DELETE_SAMPLE` |
| `sample:hard_delete` | Permanent deletion | `HARD_DELETE_SAMPLE` |

`sample:read_surveillance` is the capability that the immune-platform and federation consuming-workflows depend on (§6, §7). It is the clean replacement for the `is_data_analyst` boolean — instead of a global flag, it is a capability granted at Instance scope to whoever does surveillance oversight.

### 4.2 Pipeline plane

| Capability | Meaning | Audit action |
|---|---|---|
| `pipeline:run` | Launch a pipeline run | `CREATE_PIPELINE_RUN` |
| `pipeline:write_results` | Write pipeline results (held by the Nextflow weblog poster and the cryptWWDB third-party lab) | `REGISTER_PIPELINE_RESULT` |
| `pipeline:register_custom` | Register a custom (BYOP) pipeline | `REGISTER_CUSTOM_PIPELINE` |
| `pipeline:promote` | Promote a pipeline to a higher lifecycle tier | `PROMOTE_PIPELINE` |

`pipeline:write_results` is the capability that makes the cryptWWDB "computes without seeing" property expressible (§9): the third-party lab is a `SERVICE` principal holding `pipeline:write_results` at a specific project scope and **not** holding `sample:read_detail` on the source samples. Capability separation enforces the privacy property structurally.

### 4.3 Federation plane

| Capability | Meaning | Audit action |
|---|---|---|
| `federation:configure_peer` | Establish/modify a peering relationship (Layer 1, §7) | `UPDATE_FEDERATED_INSTANCE` |
| `federation:write_agreement` | Create/modify a sharing agreement (Layer 2, §7) | `UPDATE_SHARING_AGREEMENT` |
| `federation:push` | Push data to a peer (held by a `PEER_INSTANCE` principal, via an agreement) | `FEDERATION_PUSH` |
| `federation:review_request` | Human review of an inbound federation request that passed auto-qualification | `REVIEW_FEDERATION_REQUEST` |
| `federation:approve_request` | Approve a reviewed inbound request | `APPROVE_FEDERATION_REQUEST` |

Note what is **not** here: the auto-evaluation of the 3-gate qualification logic (§2.2) is automation, not a capability. No principal holds "the right to have the instance run its qualification gates." Only the human-facing review/approve halves are capabilities — exactly the decomposition the Q4=c decision produced.

The audit actions named in this table (`UPDATE_FEDERATED_INSTANCE`, `UPDATE_SHARING_AGREEMENT`, `FEDERATION_PUSH`, `REVIEW_FEDERATION_REQUEST`, `APPROVE_FEDERATION_REQUEST`) are **proposed — not yet present in `backend/audit.py`'s `AuditActions`** and should be reconciled against the real constants when this lands. FED-D shipped the `federated_instances` table and the `FederationRole` enum but did not add federation `AuditActions`; the sharing-agreement actions are net-new for the Layer 2 model (§7).

This plane also connects to an already-shipped piece of state: the **`FederationRole` enum** (`hub` / `spoke` / `peer` / `data_source_lab`), carried on both `federated_instances.role` and `organizations.federation_role` (FED-D + B-CWB-FED-1). The `data_source_lab` role is the cryptWWDB third-party lab — a peer that authenticates via `X-Pipeline-Token`, produces `pipeline_results` via `pipeline:write_results`, and holds no `samples` of its own. §7 builds the peering and sharing-agreement model on top of this existing role enum rather than inventing a parallel one.

### 4.4 Anomaly / immune plane

| Capability | Meaning | Audit action |
|---|---|---|
| `anomaly:review` | See anomalies the immune subsystem flagged | — |
| `anomaly:triage` | Act on a flagged anomaly (dismiss, escalate, annotate) | `TRIAGE_ANOMALY` |
| `anomaly:configure_detector` | Configure detector parameters/lifecycle | `CONFIGURE_DETECTOR` |

The category-defining absence: **there is no `anomaly:emit`.** The immune subsystem *emitting* an anomaly is automation — a scheduled subsystem behavior, not a capability any principal holds (§2.2). "Reports anomalies," which felt like a single role in the APGAP framing, decomposes cleanly into one automation behavior (emission, not modeled here) plus two human capabilities (`anomaly:review`, `anomaly:triage`). This is the resolution of the Q5 design question.

### 4.5 Governance plane

| Capability | Meaning | Audit action |
|---|---|---|
| `access:approve_request` | Approve a sample access request | `APPROVE_ACCESS_REQUEST` |
| `access:revoke` | Revoke an access grant | `REVOKE_ACCESS` |
| `deletion:request` | Request deletion of a sample — drives the `ACTIVE → DELETION_REQUESTED` transition (see §6) | `sample_deletion_requested` |
| `deletion:approve` | Approve a deletion request (sovereignty-sensitive — see §6) | `APPROVE_DELETION` |
| `submission:approve` | Approve an outbound submission | `SUBMISSION_MARKED_SUBMITTED` |
| `scrub:approve_skip` | Approve a scrubber-skip request | `APPROVE_SCRUB_SKIP` |
| `key:rotate` | Rotate signing/federation keys | `ROTATE_KEY` |
| `whitelist:manage` | Manage the domain whitelist | `ADD_WHITELIST_DOMAIN` / `REMOVE_WHITELIST_DOMAIN` |
| `user:manage` | Create/modify/deactivate users, assign capabilities | `UPDATE_USER` / `CHANGE_MEMBER_ROLE` |
| `org:manage` | Create/modify orgs, labs, projects | `CREATE_ORG` / `CREATE_LAB` / `CREATE_PROJECT` |
| `audit:read` | Read the audit log | — |

These map almost one-to-one onto existing `audit.py` actions — the governance plane is the most stable because it is the part of the system APGAP already modeled well. The redesign mostly preserves these; what changes is that they become capabilities granted at a scope rather than implied by a role.

### 4.6 Compute plane (cryptWWDB / HE)

This plane is **net-new**, added when §7 surfaced the cryptWWDB integration: the `data_source_lab` peer and the HE compute path need capabilities distinct from raw data access, because the entire privacy property is that a principal can *compute* without being able to *read*. These are representative; the concrete set follows the `HEOperation` enum in `backend/backend/crypto/_ais_hooks.py`.

| Capability | Meaning | Audit action |
|---|---|---|
| `compute:he_aggregate` | Run a homomorphic aggregate over an encrypted dataset | `RUN_HE_OPERATION` |
| `compute:he_query` | Run a homomorphic query/match over ciphertext | `RUN_HE_OPERATION` |
| `compute:register_dataset` | Register an encrypted dataset for compute | `REGISTER_HE_DATASET` |

The structural point this plane makes (and the reason it is its own plane, not folded into the pipeline plane): a `data_source_lab` principal — or any cryptWWDB compute participant — holds a `compute:*` capability **and not** `sample:read_detail`. `permit()` therefore ALLOWs the HE operation and DENYs a raw read of the same dataset, which is exactly the "computes without seeing" guarantee made enforceable rather than promised. The `permit()` ↔ `policy_checker.access_policy` adapter (§7.4) maps an `HEOperation` to one of these capabilities via `he_operation_to_capability`; the audit actions are proposed (not yet in `audit.py`) and pair with `policy_checker.py`'s own in-memory `PolicyVerdict` log, which the federation router is responsible for persisting durably.

### 4.7 A note on what is *not* a capability

To make the boundary explicit, the following are **automation behaviors**, not capabilities — no principal holds them, and they do not appear in any grant:

- The immune subsystem emitting an anomaly record
- The federation receiver auto-evaluating the 3-gate qualification logic
- The scheduled jobs that auto-approve due access requests, expire grants, and moot public-sample requests (`jobs.py` today)
- The PII gates (SRA scrubber, GCP DLP) running at ingest

These are things the *system does on a schedule or in response to data*, not things a *principal is authorized to do*. They emit audit actions (e.g. `AUTO_APPROVE_ACCESS_REQUEST`, `EXPIRE_ACCESS_GRANT`, `SYSTEM_SKIP_SCRUB`) with a system actor rather than a principal actor, but they are never gated by `permit()`. Conflating automation with capability is the category error §2.2 warns against; this list is the catalog's statement of where that line falls.

---

## 5. The decision algorithm

This is the load-bearing section: how `permit(principal, capability, resource, context)` combines scope-grants and attribute-policies into a single ALLOW/DENY verdict, under strict deny-wins.

### 5.1 The algorithm in prose

```
permit(principal, capability, resource, context):
    1. Gather the principal's grants for `capability` (direct + preset + agreement),
       each tagged with the scope it was granted at.
    2. Locate the resource's scope in the tree.
    3. STRUCTURAL CHECK — is `capability` granted at any scope that contains
       (ancestor-or-self of) the resource's scope, with the grant's own
       conditions satisfied?  → produces a candidate ALLOW.
    4. POLICY EVALUATION — evaluate every policy whose `applies_to` matches:
         - if ANY policy with effect=DENY fires            → return DENY   (deny-wins)
         - collect ALLOW policies that fire
    5. VERDICT:
         - if step 4 produced a DENY                        → DENY
         - else if step 3 produced a candidate ALLOW        → ALLOW
         - else if step 4 produced an ALLOW policy          → ALLOW
         - else                                             → DENY  (default-deny)
```

Two independent paths can produce an ALLOW: a **structural** grant (step 3 — the principal is entitled by scope) or an **attribute** policy (step 4 — the context permits it regardless of grants, e.g. a PUBLIC sample). Either suffices. But **a single DENY policy beats both** — deny is evaluated first in the verdict and short-circuits everything. This is what makes sovereignty and org-isolation unconditionally enforceable (§6).

### 5.2 The `permit()` sketch

A reference sketch — not the final implementation (that lands in the migration phase, §10), but concrete enough to remove ambiguity about control flow. Deny-wins is visible in the ordering: the DENY scan happens before any ALLOW is honored.

```python
from dataclasses import dataclass
from enum import Enum


class Effect(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


def permit(
    principal: Principal,
    capability: str,
    resource: Resource,
    context: Context,
    *,
    policies: list[Policy],
    scope_tree: ScopeTree,
) -> Decision:
    """Pure authorization decision. Strict deny-wins; default-deny.

    No I/O: callers resolve `principal.grants`, `resource.scope_ref`,
    the applicable `policies`, and the `scope_tree` ancestry up front and
    pass them in. This keeps the decision deterministic and testable —
    the same inputs always produce the same verdict.
    """
    # ── Step 1-3: STRUCTURAL CHECK ────────────────────────────────────
    # Does the principal hold `capability` at a scope that contains the
    # resource's scope, with the grant's own conditions satisfied?
    structural_allow = False
    for grant in principal.grants:
        if grant.capability != capability:
            continue
        if not scope_tree.contains(grant.scope_ref, resource.scope_ref):
            # grant's scope is not an ancestor-or-self of the resource's scope
            continue
        if not _conditions_satisfied(grant.conditions, principal, resource, context):
            continue
        structural_allow = True
        break

    # ── Step 4: POLICY EVALUATION ─────────────────────────────────────
    # Deny-wins: a single firing DENY policy ends it. Evaluate denies first.
    policy_allow = False
    for policy in policies:
        if not _applies(policy.applies_to, capability, resource, context):
            continue
        fired = _evaluate(policy.rule, principal, capability, resource, context)
        if not fired:
            continue
        if policy.effect == Effect.DENY:
            # Unconditional. No grant, no ALLOW policy can override this.
            return Decision.DENY
        # policy.effect == Effect.ALLOW
        policy_allow = True

    # ── Step 5: VERDICT ───────────────────────────────────────────────
    # (No DENY fired, or we'd have returned above.)
    if structural_allow or policy_allow:
        return Decision.ALLOW
    return Decision.DENY  # default-deny
```

The helper predicates (`_conditions_satisfied`, `_applies`, `_evaluate`) evaluate a `Predicate` against the attribute bags of principal/resource/context. Their internals are an implementation detail (§10); what matters for the design is the **shape**: the structural check and the policy scan are independent, denies are absolute, and the floor is default-deny.

**Implementation note — no ORM.** JACKPOT has no SQLAlchemy ORM: data access is raw SQL via `text()` in `backend/backend/database.py`, with `target_metadata=None` in Alembic and hand-written migrations. So the caller's "resolve `principal.grants` and the `scope_tree` ancestry up front" step is itself raw SQL (joins over the membership/grant tables), not ORM navigation. More importantly, the per-resource `permit()` above is the *detail-check* path; the *list-filtering* path cannot call `permit()` per row. It needs a companion that compiles the same structural-grant-plus-policy logic into a single SQL `WHERE` fragment — exactly what `visibility_sql_clause()` does today for the `_base_access` ladder. The two must stay behaviorally identical (a row visible in a list must be detail-accessible iff `permit()` says so). Keeping `permit()` pure makes that equivalence testable: the SQL compiler and the row-wise function are checked against each other on the same fixtures. The SQL-compilation companion is specified in the migration/implementation plan (§10), not here — but the design constraint is stated now so §10 honors it.

### 5.3 How today's `_base_access` ladder maps onto this

The current `permissions.py` ladder is this algorithm avant la lettre. The mapping, to make the continuity explicit and de-risk the migration:

| Today's `_base_access` rung | Becomes |
|---|---|
| `is_platform_admin` → True | An Instance-scope grant of (effectively) all capabilities — the Instance Administrator preset (§8) |
| `owner_id == user.id` → True | A structural grant: ownership implies a Sample-scope grant of read/update capabilities |
| lab membership → True | A structural grant at Lab scope (the principal's lab membership *is* a scope grant) |
| project membership → True | A structural grant at Project scope |
| `sharing_level == 'PUBLIC'` → True | An **ALLOW policy** keyed on `resource.sharing_level == 'PUBLIC'` (step 4) |
| `sharing_level == 'DISCOVERABLE'` (list only) | An ALLOW policy that fires only for `capability == 'sample:read'`, not `sample:read_detail` |
| `is_data_analyst AND surveillance_relevant` → True | The `sample:read_surveillance` capability (§4.1) plus an ALLOW policy gating it on `resource.surveillance_relevant` |
| approved access request/grant → True | A structural grant at Sample scope, `source=direct`, time-bounded via the grant's conditions + `context.now` |

Every rung of the existing ladder has a clean home in the new model — structural rungs become scope-grants, attribute rungs become ALLOW policies. Nothing in the current behavior is lost; it is re-expressed in a model that can *also* express federation, sovereignty, and tenancy, which the ladder could not.

### 5.4 Strict deny-wins, restated

The conflict-resolution rule, stated once, authoritatively: **if any applicable DENY policy fires, the decision is DENY — unconditionally, with no precedence or override mechanism.** There is no priority number on policies, no "this grant outranks that deny." The only way to *not* be denied is for no DENY policy to fire.

Consequences, all intended:

- **Sovereignty constraints are absolute.** A sovereignty DENY (§6) cannot be overridden by any grant, however broad — not even an Instance Administrator's. This is the property tribal-sovereignty and CARE compliance require.
- **Org-isolation is absolute.** The tenant wall is a DENY policy keyed on cross-org access; no grant punches through it. P0c multi-tenancy is enforced here.
- **Reasoning is simple.** "Why was this denied?" always has a crisp answer: either a specific DENY policy fired (and `policy.rationale` says which and why), or nothing granted access and default-deny applied. There is no precedence chain to trace.

The cost — occasionally wanting "deny X in general but allow it in this one case" — is paid by *not writing the DENY policy so broadly*, rather than by overriding it. If a real case ever demands true override, precedence can be added later, scoped narrowly to the policies that need it, without retrofitting complexity the rest of the system doesn't use. v1 does not need it.

---

## 6. Sovereignty as attribute-policy

Per the Q8 decision, sovereignty is **not** a separate subsystem, a veto layer, or a special class of capability. It is a set of **DENY policies in the same engine**, evaluated by the same `permit()` function, riding on the deny-wins rule from §5.4. This section shows how the four sovereignty constraints express as policies.

> **Grounding note.** This section is written against `docs/architecture/sovereignty-compliant-deletion.md` (B-CARE-3-DESIGN, PR #20), read directly — §2 (the four-state lifecycle), §3 (state machine + per-transition authorization), §8 (already-published handling), §9 (federation propagation), §10 (the authorization matrix), and §12 (schema constraints). The policies below are bound to that doc's actual actor model. The one remaining placeholder is `is_tribal_authority_designee_for` (constraint 1): the doc establishes that a "Tribal authority designee" is the consent authority on Scenario T deployments but does not specify how that principal is represented in the schema — that representation is an open modeling question (flagged in §6.4).

### 6.1 Why policies, not a separate layer — and what sovereignty actually keys on

A separate sovereignty veto layer would be a second place where access is decided — and two decision points drift apart, leak edge cases, and double the audit surface (the exact failure mode the unified-principal abstraction avoids for principals, §2.1). Modeling sovereignty as policies in the one engine means: one decision point, one audit trail, one place to reason about "could this data leave / be published / be deleted." Deny-wins guarantees a sovereignty DENY is unconditional without any special-casing — it is just a DENY policy, and DENY policies already always win.

**There is no sovereignty *classification* attribute.** Sovereignty does not key on a `sovereignty_class` label on the sample (an earlier draft of this section invented one — `CARE_GOVERNED` / `TRIBAL` / `UNRESTRICTED` — that has no basis in the shipped design and is removed). The two real hooks are:

1. **`context.sovereignty_mode`** (§2.6) — a per-instance *runtime policy flag*. A deployment with sovereignty-runtime-policy enabled has `sovereignty_mode = True`. This is the master switch; per `docs/architecture.md` §22, sovereignty is a runtime-policy configuration on Scenario A, not a separate deployment scenario. When off, the sovereignty policies are present but their `rule` predicates short-circuit on `sovereignty_mode == False`.
2. **`resource.attributes["deletion_status"]`** — the shipped `samples.deletion_status` enum: `ACTIVE | DELETION_REQUESTED | TOMBSTONED | VACUUMED` (B-CARE-3-DESIGN §2). Sovereignty constraints express as transitions through this lifecycle and as guards keyed on which state a sample is in, **not** as a static governance label.

The per-runtime-policy *defaults* that ride on `sovereignty_mode` (also shipped in the design) are configuration, not policy logic: vacuum cadence (sovereignty-enabled deployments default to a 24h vacuum window; sovereignty-disabled default to 30 days), and derivative-analysis policy on deletion (sovereignty-enabled defaults to cluster-recompute; others to mark-stale-and-recompute or cluster-with-asterisk). These defaults are set by the runtime policy; the `permit()` policies below enforce the *access* consequences.

### 6.2 The constraints as policies

A correction up front, now that the design doc (§3, §10) has been read directly: **most deletion authorization is ordinary structural capability, not a sovereignty override.** The §10 authorization matrix maps deletion privileges onto the *existing* roles — sample submitter (own samples), lab member with `sample_access` (own lab's samples), Lab Director (own-lab), Platform Admin (any) — and every one of those is a normal scope-grant relationship the model already handles via §5's structural check and §8's presets. Sovereignty adds exactly **one** principal to the picture: the Tribal authority designee on sovereignty-mode (Scenario T) deployments. So the sovereignty *policy* surface here is much smaller than the earlier draft implied — it is the Tribal-authority addition plus a separation-of-duties guard, not a wholesale "rights-holder overrides ownership" rule.

**1. Deletion-request — mostly structural; sovereignty adds the Tribal authority designee.** The `ACTIVE → DELETION_REQUESTED` transition needs `deletion:request`. For the ordinary actors this is a plain capability granted at the relevant scope (owner→sample, lab member→lab, Lab Director→lab, Platform Admin→instance) — **no policy required; the §5 structural check covers it.** The only sovereignty-specific grant is an ALLOW that gives the Tribal authority designee `deletion:request` (and, per §10, `deletion:approve`) over samples scoped to their authority, available only under sovereignty mode:

```
Policy:
    id:         "sovereignty.tribal_authority_deletion"
    applies_to: capability in ("deletion:request", "deletion:approve")
                AND resource.type == "sample"
    effect:     ALLOW
    rule:       context.sovereignty_mode
                AND principal.attributes.get("is_tribal_authority_designee_for") == resource.scope_ref
                AND resource.attributes.get("deletion_status") in ("ACTIVE", "DELETION_REQUESTED")
    rationale:  "CARE 'Authority to Control': on a sovereignty deployment the Tribal
                 authority is the consent authority, and may both request and approve
                 deletion over samples within its authority, outside the operational
                 Lab-Director/Platform-Admin chain (design doc §10)."
```

This is the precise binding of what the earlier draft left as the placeholder `_principal_has_deletion_claim` — and the placeholder was wrong in shape. It is *not* a data-subject link (`is_data_subject_for`), which the doc never uses and which wastewater couldn't satisfy. It is the Tribal-authority-designee scope relationship, and it is the *only* sovereignty-specific addition; everything else is structural. The capability `deletion:request` is now listed in the §4.5 governance plane, with audit event `sample_deletion_requested` (the design doc's `audit_log.event_type` value; note the design uses lowercase event-type names like `sample_deletion_requested` / `sample_tombstoned` / `sample_vacuumed` / `outbreak_investigation_override`, which should be reconciled against `audit.py`'s `AuditActions` constants).

**1b. Separation-of-duties on approval — a DENY I missed.** §3 and §10 require that the approver of a deletion be a *different actor* than the requester, unless a Platform Admin explicitly self-approves with an audited `--platform-admin-self-approve` flag. That is a real authorization rule, and it is a DENY (it subtracts a path that a `deletion:approve` grant would otherwise permit). It is not sovereignty-specific — it is "intentional friction" the design applies to all deletion approvals:

```
Policy:
    id:         "deletion.separation_of_duties"
    applies_to: capability == "deletion:approve" AND resource.type == "sample"
    effect:     DENY
    rule:       principal.id == resource.attributes.get("deletion_requested_by_user_id")
                AND not context.attributes.get("platform_admin_self_approve", False)
    rationale:  "The approver of a deletion must differ from the requester (design doc
                 §3/§10), unless a Platform Admin explicitly self-approves (audited).
                 Consent withdrawal is processed through the agency's record-keeping,
                 not immediately self-executable."
```

Deny-wins makes this absolute except for the explicit, audited platform-admin escape — which is modeled as a `context` flag the self-approve flow sets, not as a grant. (This policy lives under the `deletion.` prefix rather than `sovereignty.` because it applies regardless of `sovereignty_mode`; it is deletion-governance, not sovereignty-specific.)

**2. No-publish-while-deleting — keyed on `deletion_status`, not request-origin.** The earlier draft modeled this as a DENY on non-LOCAL `submission:approve` under sovereignty mode. The design doc (§8) is different and cleaner: **a sample whose `deletion_status != ACTIVE` cannot be submitted to external repositories at all** — the submission endpoint blocks with a 422, universally, not just under sovereignty mode. The rule keys on the deletion lifecycle, not on who is asking:

```
Policy:
    id:         "deletion.no_publish_while_deleting"
    applies_to: capability == "submission:approve" AND resource.type == "sample"
    effect:     DENY
    rule:       resource.attributes.get("deletion_status") != "ACTIVE"
    rationale:  "A sample requested-for-deletion, tombstoned, or vacuumed must never be
                 submitted to an external repository (design doc §8); prevents the
                 publish-moments-before-deletion-approval failure mode."
```

This is universal (no `sovereignty_mode` clause) — the same shape as the federation tombstone-guard below, applied to the external-submission path. The *sovereignty-specific* part of §8 is not a `permit()` rule at all: it is the **Scenario-T consent-affirmation checklist**, a UI gate that requires the submitter to affirm the consent form authorizes external publication, recorded in the audit log. That is a human-in-the-loop workflow requirement (handled in the submission UI + audit, B-CARE-3e), not an authorization predicate — so it does not belong in `permit()`. The earlier draft's "no-auto-publish under non-LOCAL origin" framing was an over-reading of the todo.md summary; the doc does not gate publishing on request origin.

**3. Federation-off-by-default — the shipped floors plus a tombstone guard.** Federation is already gated by *shipped* structural mechanisms, not by this policy alone: `federated_instances.federation_enabled` defaults to `false`, `organizations.federation_enabled` defaults to `false`, and **`min_sharing_level_for_federation` exists on both** (`organizations` default `'PRIVATE'`, `federated_instances` default `'DISCOVERABLE'`). A sovereignty-active instance ships with federation disabled and zero sharing agreements (§7), so nothing federates until an operator both enables it and writes an agreement — default-deny plus these floors handle the common case structurally. The policy below is the belt-and-suspenders DENY that guards the one thing the floors don't: data already in the deletion lifecycle must never federate out, even if an agreement matches:

```
Policy:
    id:         "sovereignty.no_federate_deleting"
    applies_to: capability == "federation:push" AND context.request_origin == "FEDERATION"
    effect:     DENY
    rule:       resource.attributes.get("deletion_status") != "ACTIVE"
    rationale:  "A sample that is requested-for-deletion, tombstoned, or vacuumed
                 must never leave via federation, regardless of any sharing agreement."
```

This is the unconditionally-unoverridable property from §5.4 made concrete: even a valid sharing agreement (which produces a structural ALLOW for the peer principal) is beaten by this DENY. It also holds independent of `sovereignty_mode` — a non-ACTIVE sample should never federate out whether or not sovereignty policy is on, because tombstone propagation (B-CARE-4) is a *push of the deletion event*, not a push of the data. (Federation-off-*by-default* itself — the instance shipping with `federation_enabled = false` — is configuration, already shipped, not a `permit()` policy.)

The design doc §9 confirms and sharpens this: when a sample is tombstoned or vacuumed, peers that previously held a copy receive a **signed tombstone/vacuum event** (sample id, timestamp, deletion-reason *class* but not the free-text reason, and a propagation token) within an SLA — 1 hour for sovereignty deployments, 24 hours otherwise — and must return a signed acknowledgment, with non-compliant peers flagged or auto-suspended per operator policy. That is a distinct channel from data federation, and this DENY is precisely what *forces* the separation: because the data path is closed for non-ACTIVE samples, the only thing that can cross to a peer is the deletion directive. §7 must honor this — the federation model needs a tombstone-event push path alongside the data-sharing path, and per §9 the entire federation feature is gated on B-CARE-4 being able to satisfy this propagation contract.

**4. CARE compliance — the posture, made enforceable.** CARE (Collective benefit, Authority to control, Responsibility, Ethics) is broader than any single rule — it is a governance posture. In this model it manifests as `sovereignty_mode` being *enabled* (a deployment-level governance act, upstream of `permit()`), the per-runtime-policy defaults (§6.1) being *set* accordingly, and the policies above enforcing the access consequences. The model's contribution is making CARE *enforceable* rather than aspirational: once `sovereignty_mode` is on, the deny-policies make the sovereignty constraints structural facts of the running system, not documentation. The deletion lifecycle (request → tombstone → vacuum) is the "Authority to Control" principle given mechanical teeth — withdrawn-consent data actually leaves the system, with the audit log preserving the *fact* of deletion but not the deleted content (B-CARE-3-DESIGN §5).

### 6.3 The payoff

Because sovereignty is policies in the one engine, keyed on the shipped `deletion_status` lifecycle and the `sovereignty_mode` runtime flag:

- **A sovereignty audit is a policy audit.** "Show me every rule that could block governed data from leaving" is a query over the policy set where `id` starts with `sovereignty.` — not an inspection of a separate subsystem.
- **Sovereignty composes with everything else automatically.** A federated read of a sample in `DELETION_REQUESTED` state is evaluated by the same `permit()` that handles the peering, the sharing agreement, and the scope grant. The sovereignty DENY simply joins the policy scan and wins if it fires.
- **Turning sovereignty on is flipping one runtime flag.** A deployment without sovereignty requirements runs the same engine and the same policies; their `rule` predicates short-circuit on `sovereignty_mode == False` (except the deletion-lifecycle guards in constraints 1b, 2, and 3, which are correct to enforce unconditionally — they are deletion-governance, not sovereignty-gated). No separate code path, no separate build — exactly the §22 "sovereignty as runtime-policy configuration on Scenario A" framing.

### 6.4 Open modeling question — representing the Tribal authority designee

Constraint 1 binds the sole sovereignty-specific grant to a predicate `is_tribal_authority_designee_for(principal) == resource.scope_ref`. The design doc (§10) establishes *that* a Tribal authority designee exists and is the consent authority on Scenario T deployments — able to both request and approve deletion over samples "scoped to their authority," outside the operational Lab-Director/Platform-Admin chain — but it does not specify *how* that principal and that scoping are represented. Two questions for the implementation (P0c, with B-CARE-3a):

1. **Is the designee a HUMAN principal holding a capability at a scope, or a distinct principal kind?** The cleanest fit with §2.1 is: a HUMAN principal granted `deletion:request` + `deletion:approve` at the Org (or a dedicated authority) scope, via a Scenario-T-only preset. Then "scoped to their authority" is just the scope of the grant, and no special predicate is needed — it collapses into the ordinary structural check. That would make even this sovereignty addition structural rather than a policy, shrinking §6.2 constraint 1 to a preset (§8) plus the separation-of-duties carve-out the doc grants Scenario T (the designee *may* self-approve, unlike the general rule in 1b).
2. **What is "their authority" as a scope?** If a Tribal authority maps cleanly onto an Org, this is free. If a single authority spans multiple orgs, or a subset of one org's samples by some attribute (e.g. consent-cohort), it needs either a new scope level or an attribute-policy. This should be resolved against a real Scenario T deployment's structure before P0c implements it, not guessed at now.

The recommendation: **model the designee as a HUMAN principal with a Scenario-T preset at Org scope** (option 1), and revisit only if a real deployment shows authority and org don't coincide. That keeps the sovereignty policy surface minimal — the separation-of-duties DENY (1b) and the two deletion-lifecycle guards (2, 3) are then the *entire* sovereignty-specific authorization surface, and even the Tribal-authority path becomes structural. Until a Scenario T pilot exists, this stays an explicit open question rather than an invented mechanism.

---

## 7. Federation: two authorization layers over three flow levels

This is the section with the most shipped code behind it, so it is written as a *reconciliation* — the clean two-layer authorization model from the design conversation mapped onto what `backend/backend/federation/` actually implements (FED-A scaffold, FED-B router, FED-E peer-auth guard, B-CWB-POLICY-1 policy checker), read directly.

> **Grounding note.** Written against the uploaded `models.py`, `client.py`, `push.py`, `access.py`, `policy_checker.py`, `_ais_hooks.py`, and `routers/federation.py` (FED-B), plus the `guards.py` peer-auth helpers the router imports. Where this section describes *shipped* behavior it cites the file; where it describes the *agreements layer* it is proposing new design, flagged as such. Open reconciliation questions are collected in §7.6.

### 7.1 Two orthogonal taxonomies — and why both are needed

The shipped code and the design conversation use two different decompositions, and the confusion dissolves once you see they are **orthogonal**:

- **Three flow *levels* (shipped)** — about *what data moves*: **L1 query** (`FederationClient` fans a `FederationQuery` to partners, merges DISCOVERABLE-equivalent result rows), **L2 push** (`FederationPushJob` pushes de-identified surveillance payloads to a hub), **L3 access** (`FederationAccessGateway` brokers per-sample cross-instance access via the existing `sample_access` workflow).
- **Two authorization *layers* (the design)** — about *how access is decided*: **Layer 1 peering** (does a channel between two instances exist at all?), **Layer 2 sharing agreements** (what is a given peer permitted to do over that channel?).

The levels are *flows*; the layers are *authorization*. Every level is gated by both layers: a flow can only happen if a peering channel exists (Layer 1) **and** a sharing agreement permits that specific flow at that specific scope (Layer 2). The job of §7 is to show that Layer 1 is essentially shipped, Layer 2 is the new design, and `permit()` is how Layer 2 plugs into the shipped flow code.

### 7.2 Layer 1 — peering (shipped)

A **peering relationship** is a row in `federated_instances` (`models.py` `FederatedInstance`): `id`, `name`, `base_url`, `role` (the `FederationRole` enum — `hub` / `spoke` / `peer` / `data_source_lab`), `federation_enabled`, `min_sharing_level_for_federation`, `hub_instance_url`, `api_key_secret_name`. The channel is authenticated by the `X-JACKPOT-Federation-Key` header on the peer-to-peer endpoints (`/push`, `/access-requests`), validated by `authenticate_federation_peer(request, db)` imported from `backend.auth.guards` into `routers/federation.py` — the key is compared constant-time against every enabled instance's secret, looked up by `api_key_secret_name` through the credentials facade (GCP Secret Manager in prod, in-memory in tests). Admin-facing list/register endpoints use standard JWT + `require_platform_admin`; `/search` uses standard JWT (`get_current_user`). Keys never live in DB rows — only the Secret Manager entry *name* does.

Peering says **a channel exists and who is on the other end** — nothing about what flows. Two properties matter for the authorization model:

- **`federation_enabled` is the master switch, and it defaults `false` at both layers** — the `federated_instances` DB column (FED-D migration) and the Pydantic `FederatedInstance` model. (An earlier code state had the model defaulting `True`; that was reconciled to `false` so a `FederatedInstance` constructed without an explicit value cannot accidentally start with federation on.) This is federation-off-by-default (§6 constraint 3) realized as a default, not a policy: a newly-registered peer is inert until an operator explicitly enables it.
- **A peer is a principal.** A `federated_instances` row is exactly the `PEER_INSTANCE` (or, for cryptWWDB, `DATA_SOURCE_LAB`) principal kind from §2.1. The `FederationRole` distinguishes them: `data_source_lab` is the cryptWWDB Lab that produces `pipeline_results` via `X-Pipeline-Token` and holds no samples — modeled as a principal holding `pipeline:write_results` at a project scope and *not* holding `sample:read_detail`.

### 7.3 Layer 2 — sharing agreements (new design)

Here is the gap and the opportunity: **the shipped code has no sharing-agreement object.** What governs "what a peer may do" today is a mix — the peer principal's read visibility on the partner's `/api/v1/samples/` endpoint (L1), the org-wide qualification gates (L2), and per-sample `sample_access` grants (L3). None of that lets an operator say "Peer X may read *Salmonella* in Lab 3; Peer Y may see only PUBLIC." Per-peer differential access has no home.

A **sharing agreement** is that home, and it is exactly the `source=agreement` `CapabilityGrant` that §2.2 already reserved. An agreement is a set of **scoped, conditional capability grants to a specific peer-instance principal**:

```
SharingAgreement:
    id:             str
    peer:           PrincipalId        # the PEER_INSTANCE / DATA_SOURCE_LAB this grants to
    direction:      INBOUND | OUTBOUND # per-direction; asymmetric by construction
    grants:         list[CapabilityGrant]   # each: capability + scope_ref + conditions, source=agreement
    rationale:      str
```

Design properties, each falling out of the model rather than bolted on:

- **Default-deny.** No agreement → the peer principal holds no grants → `permit()` default-denies (§5.1). A freshly-peered instance can authenticate but can do nothing until an agreement grants it something.
- **Scoped.** Each grant names a `scope_ref` (Lab, Project, or Sample). "Peer X may read Lab 3" is a `sample:read` grant at `lab:3`. Downward inheritance (§2.3) does the rest.
- **Conditional.** A grant's `conditions` do the finer slicing the scope tree can't — `organism == 'Salmonella'`, `sharing_level >= DISCOVERABLE`, a time bound via `context.now`. These are the same condition predicates the structural check already evaluates (§5.2).
- **Per-direction and asymmetric.** `direction` is explicit and the two directions are independent objects. Hub-and-spoke falls out for free: a spoke has an OUTBOUND agreement (it pushes up) and the hub has an INBOUND one (it receives); a peer-of-peer relationship has matching agreements on both sides; nothing forces symmetry.

The three flow levels become **three capabilities an agreement can grant**:

| Flow level | Capability the agreement grants | Enforced by |
|---|---|---|
| L1 query | `sample:read` at a scope, with conditions | The partner's `/api/v1/samples/` list-filtering — the peer principal's grants run through the same `visibility_sql_clause` companion to `permit()` (§5.2) |
| L2 push | `federation:push` at a scope | The 3 qualification gates in `FederationPushJob.is_qualifying_sample` (§7.4) plus the agreement's conditions |
| L3 access | `access:approve_request` path via the existing `sample_access` workflow | `FederationAccessGateway` reuses the internal access workflow (§7.4); the agreement gates whether the inbound request is even entertained |

### 7.4 How `permit()` integrates with the shipped flow code

Three integration points, one per level, and they are the load-bearing claim of this section.

**L1 query — visibility falls out of the list-filtering path.** When instance A's `FederationClient` queries partner B, it calls `GET {B}/api/v1/samples/` with `X-JACKPOT-Federation-Key` (`client.py` `_query_one`). On B's side, `authenticate_federation_peer` (from `backend.auth.guards`, used by `routers/federation.py`) resolves the key to the `federated_instances` row — i.e. to A-as-principal. B's `/api/v1/samples/` then filters by what A-as-principal can see, using the **same `visibility_sql_clause` companion to `permit()`** that filters lists for local users (§5.2). So L1 federation visibility is not a separate code path — it is the local list-filtering path with a `PEER_INSTANCE` principal whose grants came from a sharing agreement. `FederationQuery`'s restricted field set and the forced `quality_tier_min=ANALYZABLE` (`client.py`) are an additional wire-level floor on top of that. *(The result rows are `FederationQueryResult` — DISCOVERABLE-equivalent, no file URLs, no PII — and the client stamps `source_instance_id` itself, never trusting the partner's claim.)*

**L2 push — the qualification gates are a policy, the agreement is the grant.** `FederationPushJob.is_qualifying_sample` enforces three gates (surveillance_relevant, `sharing_level >= min_sharing_level_for_federation`, `quality_status >= ANALYZABLE`). In the model these are an **ALLOW-gated-by-conditions** on the `federation:push` capability: the agreement grants `federation:push` at a scope; the three gates are conditions on that grant (or equivalently a policy keyed on the push capability). The sovereignty tombstone-guard from §6 constraint 3 (`deletion_status != ACTIVE` → DENY) sits over this and wins by deny-precedence — a sample mid-deletion never qualifies regardless of the gates.

**L3 access — reuses the existing `sample_access` workflow.** `FederationAccessGateway.receive_inbound` creates a row in the internal `sample_access` workflow tagged with the external requester (`access.py`), and approval is handled "exactly like an internal access request — same UI, same audit log." So L3 maps onto the existing access-grant capability (§4.5 `access:approve_request`): the agreement gates whether B will *entertain* an inbound request from A at all; if it will, the request becomes an ordinary `sample_access` row and the existing approval path takes over. The post-approval grant to A is a Sample-scope `CapabilityGrant` with `source=agreement`.

**The cryptWWDB path — `permit()` *is* the `access_policy` callable.** This is the cleanest integration and the one the shipped code most explicitly anticipates. `policy_checker.py` takes an injected `access_policy: Callable[[requester_id, operation, dataset_id], bool]`, and its own docstring says the router can "plug in the existing `can_access_sample()` machinery (or a federation-flavored variant)." That callable is where `permit()` plugs in. The router constructs the adapter:

```python
def make_access_policy(scope_tree, policies) -> AccessPolicy:
    """Adapt permit() to the PolicyChecker's (requester_id, operation, dataset_id) oracle."""
    def access_policy(requester_id: str, operation: HEOperation, dataset_id: str) -> bool:
        principal = resolve_peer_principal(requester_id)          # DATA_SOURCE_LAB / PEER_INSTANCE
        capability = he_operation_to_capability(operation)        # e.g. "compute:he_aggregate"
        resource = resolve_dataset_resource(dataset_id)           # the cryptWWDB dataset
        context = Context(request_origin="FEDERATION", origin_instance=principal.id, ...)
        return permit(
            principal, capability, resource, context,
            policies=policies, scope_tree=scope_tree,
        ) is Decision.ALLOW
    return access_policy
```

So `PolicyChecker` keeps its two jobs — access adjudication (now delegated to `permit()`) and the HE-specific **repeated-query side-channel detection** (the sliding-window replay guard, which `permit()` does *not* and should not replicate — it is an HE-protocol concern, not an authorization one). The division is clean: `permit()` answers "may this principal run this operation on this dataset," `PolicyChecker` adds "and not as a ciphertext replay," and the `attest_partner` AIS hook adds "and from an attested partner." The cryptWWDB privacy property — the `data_source_lab` computes without seeing — is structural: that principal holds a compute capability and not `sample:read_detail`, so `permit()` allows the HE operation and would deny a raw read.

### 7.5 The tombstone-propagation channel

Per §6 constraint 3 and the deletion design §9, a non-ACTIVE sample never federates as *data*, but its deletion *event* must propagate to every peer that previously received it (signed tombstone/vacuum events, 1h sovereignty / 24h default SLA, signed acknowledgments, non-compliant peers flagged or suspended). This is a **distinct channel from the three flow levels** — it carries directives, not samples — and B-CARE-4 owns it. The authorization model's only requirement here: emitting a tombstone event is *automation* (not a capability, §4.6), and *receiving/acknowledging* one is a peer-instance behavior gated by the peering channel (Layer 1), not by a data-sharing agreement (Layer 2). An operator who has peered but shares no data still receives tombstones for anything previously pushed — correctly, because the obligation to forget follows the data that already moved.

### 7.6 Open reconciliation questions

Genuine gaps between the model and the shipped code, to resolve in implementation rather than paper over:

1. **The two `min_sharing_level_for_federation` floors — and the fact the shipped L1 path ignores both.** The field exists on both `organizations` (default `PRIVATE`) and `federated_instances`/`FederatedInstance` (default `DISCOVERABLE`), and `FederationPushJob.is_qualifying_sample` takes a single value documented as "the org's." Reading `routers/federation.py` (FED-B) settles part of this: the shipped **L1 `/search` path filters partners only by `federation_enabled = TRUE`** and does *not* consult `min_sharing_level_for_federation` at all — the floor is enforced only in the (still-stubbed) L2 `is_qualifying_sample` path. So today the org/peer floor composition is simply *not exercised on L1*; it is an L2-push concept. **Remaining open:** when L2 IO is wired (Year 2 early), confirm whether the value passed to `is_qualifying_sample` is the org's floor, the peer's, or the stricter of the two. The directional oddity still stands and is worth a deliberate decision: a *lower* floor is *more* permissive (`_sharing_level_ge`), so the org default `PRIVATE` (0) is maximally permissive on the sharing-level axis — safe today only because `federation_enabled` defaults off (now at both layers, FED-FIX-1).

2. **`X-JACKPOT-Federation-Origin` and origin attribution — resolved for L3.** `client.py` sets `X-JACKPOT-Federation-Origin` to `str(partner.id)`, but the router does not read that header for identity; identity comes from `authenticate_federation_peer` (the key). For L3 the router adds a concrete anti-spoofing check: `/access-requests` rejects (403) any request whose body `requesting_instance_id` does not match the key-authenticated instance's id. So origin attribution on the inbound paths is key-derived and cross-checked against the body, not header-derived — the `X-JACKPOT-Federation-Origin` header is currently informational. §9's federation example traces this exact check.

3. **Sharing agreements are net-new schema.** Layer 2 as described needs a `sharing_agreements` table (or equivalent) that does not yet exist. It is the natural companion to `federated_instances` and slots into the same hand-written-migration convention (no ORM, §5.2). This is a P0c-or-later schema add, sequenced with the federation implementation phase, and should be called out in §11 phasing.

4. **`HEOperation → capability` mapping.** The adapter in §7.4 references `he_operation_to_capability` mapping onto the `compute:*` plane now catalogued in §4.6. What remains open is the *exact* `HEOperation` enum membership (it lives in `backend/backend/crypto/_ais_hooks.py`, which this draft has not read) and therefore the precise one-to-one mapping — to be pinned when the cryptWWDB compute path is implemented. The §4.6 entries are representative until then.

### 7.7 Sub-instance federation scope — lab-to-lab and its one edge

A natural question: the §9.3 example reads as "State A federates with State B," but can federation be narrower — say State A's *Lab 3* with State B's *Lab 7*? The answer is **yes for the data holder's side, with one honest edge on the consumer's side**, and the two layers split exactly along this question.

**The channel is always instance-to-instance; the grant is as fine as a sample.** Layer 1 peering *must* be instance-to-instance: a `federated_instances` row is keyed on `base_url` + `api_key_secret_name`, and `X-JACKPOT-Federation-Key` authenticates one *deployment* to another. A lab is not a network endpoint — it is a scope *inside* an instance's tree (§3.1), with no API or key of its own. So there is exactly one A↔B channel, not a per-lab mesh, and that is correct: one authenticated relationship per partner organization, not a key-management explosion.

The fine granularity lives entirely in the Layer 2 sharing agreement (§7.3), whose grants name a `scope_ref` that can be a Lab, Project, or Sample. "State A's Lab 3 federates with State B" decomposes to:

- *one* A↔B peering channel (Layer 1), plus
- a sharing agreement on **B** granting `State-A-as-principal` a capability **scoped to `B's lab:7`** (so A reaches only B's Lab 7), and — if bidirectional — a sharing agreement on **A** granting `State-B-as-principal` a capability scoped to `A's lab:3`.

Downward inheritance (§2.3) does the slicing: an agreement scoped at `lab:7` reaches that lab's projects and samples and nothing in `lab:1`. Indeed the §9.3 trace already demonstrated finer-than-lab granularity — `federation:push at "B's surveillance Project"` is a Project scope, narrower than a Lab. Lab-to-lab is simply the common case of a general capability the model already has.

**The edge: the consumer's sub-scope is not carried cross-instance.** The peering channel authenticates "State A's instance," not "State A's Lab 3." So an agreement on B grants to *A-as-instance* — B confines **which of B's labs A can reach**, but B cannot condition the grant on **which of A's labs will ultimately consume** the result. Once rows cross to A, which of A's labs sees them is A's own internal `permit()` decision, adjudicated when A's users read the federated rows locally. For most surveillance federation this is the right trust boundary: B trusts A-the-agency and A polices its own internal distribution. But if a deployment ever needs B to *enforce* "only A's Lab 3 may receive this, not A's Lab 7" as a cross-instance constraint, that requires the query to carry the originating sub-scope as an attribute B's policies could match on — a real design extension, not covered by the current §7. The shipped `X-JACKPOT-Federation-Origin` header (currently informational, §7.6 Q2) is the natural place such sub-scope attribution *could* live, but it is not wired for it today. Flagged so the boundary is explicit rather than discovered later.

---

## 8. Role presets

Presets are the bridge back to human ergonomics. The engine never checks a role (§1) — it checks capabilities at scopes. But operators do not want to assemble capability sets by hand, and APGAP-trained users expect named roles. A **preset** is a named bundle of `(capability, scope-template)` pairs that an operator applies to a principal to produce the actual grants. Applying a preset is sugar; the grants it produces are ordinary `CapabilityGrant` rows with `source=preset`. Two consequences worth stating up front: a principal may hold grants from *several* presets plus direct grants (they compose — union of capabilities, deny-wins still adjudicates), and editing a preset definition does **not** retroactively change already-issued grants (the grant is the fact; the preset was only the cookie-cutter). This is the opposite of the APGAP model, where the role *was* the authorization and changing it changed everyone's access at once.

### 8.1 Why presets are not roles

The distinction is the whole point of the redesign, so it is worth being precise:

- A **role** (APGAP) is an enum value stored on the principal; authorization code branches on it (`if user.role == LAB_DIRECTOR`). Adding a capability means finding every branch. Renaming is forbidden ("DO NOT rename"). The role is load-bearing at decision time.
- A **preset** (this model) is a template consulted only at *grant-issuing* time. At decision time it has vanished — `permit()` sees only capabilities and scopes. Adding a capability to a preset changes what *future* applications grant; it touches no decision logic. Renaming a preset is harmless. The preset is load-bearing only at administration time.

So presets can proliferate, be deployment-specific, be renamed freely, and be composed — none of which the APGAP roles could do — precisely because they carry no authority themselves.

### 8.2 The human presets

These cover the human principals. Capabilities reference the §4 planes; scope-templates are filled in when the preset is applied (e.g. "this lab" becomes `lab:<id>`).

**Instance Administrator** — replaces the `is_platform_admin` boolean. Effectively all capabilities at Instance scope. The one preset that should be rare and audited; it is the principal that can write sharing agreements, manage orgs, rotate keys, and read the audit log instance-wide.

```
Preset "Instance Administrator":
  scope-template: Instance
  capabilities: org:manage, user:manage, key:rotate, whitelist:manage,
                audit:read, access:approve_request, access:revoke,
                federation:configure_peer, federation:write_agreement,
                federation:review_request, federation:approve_request,
                anomaly:configure_detector, sample:read_surveillance
  note: Does NOT implicitly include deletion:approve over sovereignty-governed
        samples on Scenario T — that path is gated by the separation-of-duties
        DENY (§6.2 1b) and, where a Tribal authority exists, sits with that
        authority. Instance Administrator is operational, not a consent authority.
```

**Lab Lead** — replaces Lab Director. Full authority within one lab, including the human-judgment governance capabilities scoped to that lab.

```
Preset "Lab Lead":
  scope-template: Lab
  capabilities: sample:read, sample:read_detail, sample:create, sample:update,
                sample:archive, sample:soft_delete, deletion:request,
                deletion:approve, access:approve_request, access:revoke,
                pipeline:run, submission:approve
  note: deletion:approve here is the ordinary intra-lab path; the §6.2 1b
        separation-of-duties DENY still forbids approving one's own request.
```

**Lab Member (read-write)** — replaces Lab Collaborator. Does the work, cannot approve governance.

```
Preset "Lab Member (read-write)":
  scope-template: Lab
  capabilities: sample:read, sample:read_detail, sample:create, sample:update,
                deletion:request, pipeline:run
  note: Can request deletion but not approve it; can run pipelines but not
        approve submissions or access requests. The read-write/governance
        split is the main line between this and Lab Lead.
```

**Lab Member (read-only)** — replaces Lab Reader. Sees, does not touch.

```
Preset "Lab Member (read-only)":
  scope-template: Lab
  capabilities: sample:read, sample:read_detail
```

**Surveillance Officer** — *not* a scope-bound lab role; this is the capability-bundle that replaces the global `is_data_analyst` flag, and §4.1 already isolated its core capability. It is the cross-scope surveillance-read grant, applied at Instance (or Org) scope.

```
Preset "Surveillance Officer":
  scope-template: Instance (or Org)
  capabilities: sample:read_surveillance, anomaly:review, anomaly:triage
  note: This is usually the SAME human as a Lab Lead, holding this preset
        ADDITIONALLY at a wider scope. That composition is the point: Lab Lead
        @ lab:3 gives full control of lab 3; Surveillance Officer @ instance
        gives cross-lab read of surveillance_relevant samples plus anomaly
        triage — without giving detail-read of every sample everywhere.
        sample:read_surveillance is gated by an ALLOW policy on
        resource.surveillance_relevant (§5.3), so it is genuinely narrower than
        sample:read_detail @ instance.
```

### 8.3 The Scenario-T sovereignty preset

§6.4 left an open question — how to represent the Tribal authority designee — and recommended modeling it as a HUMAN principal with a Scenario-T preset at Org scope, which would collapse the one remaining sovereignty *policy* (constraint 1) into a structural grant. That preset is:

```
Preset "Tribal Authority Designee"  (Scenario T deployments only):
  scope-template: Org (or a dedicated authority scope, pending §6.4 resolution)
  capabilities: deletion:request, deletion:approve, submission:approve
  carve-out:    EXEMPT from the §6.2 1b separation-of-duties DENY — the
                designee MAY request and approve the same deletion, because
                the consent authority and the operational chain are
                deliberately the same office here (design doc §10).
```

This is the only preset with a policy carve-out, and it is the mechanism by which the §6.4 recommendation works: applying it grants the designee the deletion capabilities at the authority scope structurally, and the lone sovereignty-specific carve-out is the separation-of-duties exemption rather than a bespoke ALLOW policy. Whether "authority scope" is just the Org or needs its own scope level is the open part of §6.4, unchanged.

### 8.4 The federation presets

§7 made these concrete; they apply to non-human principals and are the administrative face of Layer 2 sharing agreements.

**Peer Instance** — the default applied to a `peer`/`hub`/`spoke` `federated_instances` row once an operator decides what to share. Note it grants *nothing* by default; the operator fills in the scope and conditions, which is the sharing agreement (§7.3).

```
Preset "Peer Instance (template)":
  scope-template: operator-chosen Lab or Project
  capabilities: sample:read   (with operator-supplied conditions, e.g.
                organism == X, sharing_level >= DISCOVERABLE)
  optional add-ons by topology:
    - hub receiving pushes:   federation:push INBOUND grant
    - spoke pushing up:       (the spoke holds no inbound grant; the hub does)
  note: This preset is deliberately near-empty. A peer that is merely peered
        (Layer 1) holds no grants; this preset is applied as the operator
        authors the sharing agreement, and its content IS that agreement.
```

**Data Source Lab** — the cryptWWDB `data_source_lab` peer. The preset that makes the "computes without seeing" property structural.

```
Preset "Data Source Lab"  (FederationRole.data_source_lab):
  scope-template: the cryptWWDB Project
  capabilities: pipeline:write_results, compute:he_aggregate, compute:he_query,
                compute:register_dataset
  EXPLICITLY NOT GRANTED: sample:read_detail, sample:read
  note: The absence is the security property, not an oversight. permit()
        ALLOWs the HE compute path and DENYs any raw read for this principal.
        Authenticated by X-Pipeline-Token (distinct from X-JACKPOT-Federation-
        Key); see §7.2 and the policy_checker repeated-query guard (§7.4).
```

### 8.5 Why this set, and how it maps back to APGAP

The six APGAP roles map onto presets without information loss, which is what makes the migration (§10) a reseed rather than a rewrite:

| APGAP role | Preset | Change |
|---|---|---|
| Platform Admin | Instance Administrator | now a preset, not a boolean; consent-authority paths split out |
| Lab Director | Lab Lead | scoped grants instead of a role enum; deletion-approve subject to separation-of-duties |
| Lab Collaborator | Lab Member (read-write) | unchanged in spirit; gains explicit `deletion:request` |
| Lab Reader | Lab Member (read-only) | unchanged |
| Bioinformatics User | *(folded into Lab Member RW + `pipeline:run`)* | `pipeline:run` is an independent capability, not a role — a Lab Member RW who runs pipelines simply holds it |
| Data Analyst | Surveillance Officer | now a scoped capability-bundle, not a global boolean; genuinely narrower (surveillance-relevant only) |

Two APGAP roles dissolve rather than map: **Bioinformatics User** was really "Lab Member who runs pipelines," and `pipeline:run` being its own capability (§4.2) means that is just a Lab Member RW with one extra capability — no separate preset needed. And the **`is_data_analyst` global boolean** becomes the Surveillance Officer preset applied at a wide scope, which is both more expressive (it can be Org-scoped, not only instance-global) and narrower (gated to `surveillance_relevant`). The net: six roles become four lab/instance presets plus two federation presets plus one Scenario-T preset, no capability that APGAP granted is lost, and several that APGAP *over*-granted (global data-analyst read; role-implied pipeline access) are now scoped down.

---

## 9. Worked examples

Four end-to-end traces, one per deployment shape. Each follows a concrete principal through `permit()` (or its list-filtering companion) and names the grants, policies, and shipped code touched. These are the payoff of the abstractions — if a scenario can't be traced cleanly here, the model has a gap.

### 9.1 Laptop (Scenario A) — one human, no federation, sovereignty off

**Setup.** Single operator runs `jackpot init` on an M3 laptop. The bootstrap seeds one HUMAN principal holding the **Instance Administrator** preset at Instance scope, and `sovereignty_mode = False`, `federation_enabled = False` everywhere. One Org, one Lab, one Project — all auto-created under the single Instance.

**Trace — the operator reads a sample they created.**
- `permit(operator, "sample:read_detail", sample_42, ctx)`.
- Step 3 structural check: the operator holds Instance-scope grants (from the preset) including `sample:read_detail`. `scope_tree.contains(instance, sample_42.scope)` is true (the sample's Sample→Project→Lab→Org→Instance chain bottoms out at the one Instance). Candidate ALLOW.
- Step 4 policy scan: no sovereignty policies fire (`sovereignty_mode == False` short-circuits constraints 1/1b-tribal; the deletion-lifecycle guards in 2/3 don't apply to a read of an ACTIVE sample). No DENY.
- Verdict: **ALLOW** via the structural path.

**What this shows.** The simplest deployment touches none of the federation, sovereignty, or multi-tenancy machinery — those policies are *present* but inert. The single-admin laptop behaves exactly like the old `is_platform_admin == True` short-circuit, but it gets there through the same `permit()` every other deployment uses. No special "single-user mode" code path. This is the §6.3 "turning sovereignty on is one flag" claim in its off position.

### 9.2 Single-org SaaS (Scenario D) — many humans, one tenant, sovereignty off

**Setup.** A hosted instance for one public-health lab. One Org (the tenant), several Labs under it, ~30 human principals: one Instance Administrator (the platform operator), several Lab Leads, many Lab Members RW/RO, two people additionally holding the Surveillance Officer preset at Org scope.

**Trace A — a Lab Member RW in Lab 3 tries to read a sample in Lab 7.**
- `permit(member, "sample:read_detail", sample_in_lab7, ctx)`.
- Step 3: the member's grants are all scoped to `lab:3` (from the Lab Member RW preset applied there). `scope_tree.contains(lab:3, sample_in_lab7.scope)` is **false** — `lab:7` is not under `lab:3`. No structural ALLOW.
- Step 4: is `sample_in_lab7` PUBLIC or DISCOVERABLE? If its `sharing_level` is `LAB` or `PRIVATE`, no ALLOW policy fires. No DENY needed.
- Verdict: **DENY** by default-deny. The member simply has no grant reaching Lab 7, and the sample isn't public.

**Trace B — a Surveillance Officer reads a `surveillance_relevant` sample in Lab 7.**
- Same principal would be denied a blanket `sample:read_detail` @ Lab 7 (they hold no grant there). But they hold **`sample:read_surveillance` at Org scope** (Surveillance Officer preset).
- `permit(officer, "sample:read_surveillance", sample_in_lab7, ctx)`.
- Step 3: `sample:read_surveillance` granted at `org:1`; `scope_tree.contains(org:1, sample_in_lab7.scope)` is true. Candidate ALLOW — *but* the capability is gated.
- Step 4: the ALLOW policy on `sample:read_surveillance` fires only if `resource.surveillance_relevant == True` (§5.3). This sample is surveillance-relevant → policy ALLOW. No DENY.
- Verdict: **ALLOW**, but narrowly — the same officer querying a *non*-surveillance sample in Lab 7 gets DENY (the gating policy doesn't fire, and there's no structural grant). This is the precise improvement over the APGAP `is_data_analyst` boolean: cross-lab reach, but only for the surveillance subset, and scoped to the Org rather than globally.

**What this shows.** Tenant isolation and the surveillance-read split both work without any federation or sovereignty machinery. The Org-as-tenant boundary (§3.2) is enforced purely by the scope-containment check — Lab 3's member can't reach Lab 7 because containment fails, not because a policy forbids it. Default-deny does the isolation work.

### 9.3 Two-state federation (Scenario E) — peering + a sharing agreement, hub-and-spoke

**Setup.** State A (a SPOKE) and State B (a HUB). Each is its own Instance with its own Org tree. At each end, a principal holding the **Instance Administrator** preset (via its `federation:configure_peer` / `org:manage` capabilities, §8.2) has registered the other in `federated_instances` (`POST /instances`) and set `federation_enabled = TRUE`. *(In the shipped router that endpoint is still guarded by the legacy `require_platform_admin` check; §10 migration rewrites that guard to the capability the Instance Administrator preset grants.)* A **sharing agreement** (Layer 2, §7.3) exists: State B holds an INBOUND agreement granting State-A-as-principal `federation:push` at `B's surveillance Project`; State A holds the OUTBOUND counterpart.

**Trace A — State A runs a federated L1 search across partners (`POST /search`).**
- An authenticated State-A user calls `/search`. The router selects `federated_instances WHERE federation_enabled = TRUE` → includes State B. `FederationClient.query` fans out, resolving B's key via `credentials.get(api_key_secret_name)`.
- On State B's side, B's `/api/v1/samples/` receives the query under State-A's key; `authenticate_federation_peer` resolves it to State-A-as-`PEER_INSTANCE`. B's list-filtering (`visibility_sql_clause`, §5.2) returns only what State-A-the-principal may read — which, absent a *read* grant in the agreement, is **only B's PUBLIC/DISCOVERABLE samples** (the ALLOW policy on `sharing_level`, not a structural grant). Rows come back as `FederationQueryResult` (DISCOVERABLE-equivalent, no PII, no file URLs), stamped with `source_instance_id` by the client.
- **What this shows:** L1 visibility is the *local* list-filtering path with a peer principal. The agreement granted `federation:push`, not `sample:read`, so State A sees B's discoverable metadata but cannot read into B's labs. The two capabilities are independent — exactly the per-flow separation §7.3 promised.

**Trace B — State A pushes a qualifying sample to hub B (L2, when wired).**
- State A's nightly `FederationPushJob` evaluates `is_qualifying_sample` for `sample_X`: `surveillance_relevant == True`, `sharing_level >= min_sharing_level_for_federation`, `quality_status >= ANALYZABLE`. Suppose all three hold.
- The sovereignty tombstone-guard (§6.2 constraint 3) is checked: `sample_X.deletion_status == ACTIVE` → no DENY. (Were it `DELETION_REQUESTED`, this DENY would win regardless of qualification — the mid-deletion sample never leaves.)
- In model terms: State-A-as-principal holds `federation:push` at the agreed scope (the agreement grant); the three gates are the grant's conditions; `permit(state_A, "federation:push", sample_X, ctx_federation)` → ALLOW.
- State A POSTs to `B/api/v1/federation/push` with its key. B's router calls `authenticate_federation_peer` → State-A row; runs the `validate_push_payload` AIS hook (Track 1: True); audits `FEDERATION_PUSH_RECEIVED`; returns 202. *(Persistence of the payload is the Year-2-early stub; the auth + validate + audit path is live.)*
- **What this shows:** the three shipped qualification gates are conditions on a `federation:push` grant, and the sovereignty guard composes over them by deny-precedence. Hub-and-spoke asymmetry falls out: A holds OUTBOUND push, B holds INBOUND receive, neither holds the other's read.

**Trace C — a State-A user requests access to a specific B sample (L3, when wired).**
- State A POSTs an `AccessRequestInbound` to `B/api/v1/federation/access-requests`. B's router authenticates the peer, then enforces the **anti-spoofing cross-check**: `instance_row["id"] == payload.requesting_instance_id` or 403. (This is the §7.6-Q2 resolution — origin is key-derived and must match the body.)
- On match: in the wired design, B creates an internal `sample_access` row tagged with the external requester (`access.py` `receive_inbound`), and B's Lab Lead approves it through the ordinary internal UI. The post-approval grant to State-A is a Sample-scope `CapabilityGrant` with `source=agreement`.
- **What this shows:** L3 reuses the existing access workflow entirely; the federation layer only brokers the request in and the grant out. The agreement gates whether B *entertains* the request; the existing `access:approve_request` capability (held by B's Lab Lead) gates whether it's *granted*.

### 9.4 cryptWWDB three-party (Scenario E + data_source_lab) — computes without seeing

**Setup.** The Driver et al. 2024 three-party model: **Muni A** and **Muni B** each hold wastewater sample data; the **Lab** runs the homomorphic computation but must never see either municipality's plaintext. The Lab is registered as a `federated_instances` row with `role = data_source_lab`, authenticated by `X-Pipeline-Token`, holding the **Data Source Lab** preset (§8.4): `pipeline:write_results` + `compute:*` at the cryptWWDB Project scope, and explicitly **not** `sample:read_detail`.

**Trace — the Lab runs an HE aggregate over the encrypted dataset.**
- The federation router forwards the encrypted query to the `PolicyChecker`, constructed with `access_policy = make_access_policy(scope_tree, policies)` (§7.4) — the adapter wrapping `permit()`.
- `PolicyChecker.check(request)` runs three gates in order:
  1. **`access_policy(requester_id, operation, dataset_id)`** → calls `permit(lab_principal, "compute:he_aggregate", dataset, ctx_federation)`. The Lab holds `compute:he_aggregate` at the cryptWWDB Project scope (preset grant); `scope_tree.contains` holds; no DENY fires. → ALLOW → the callable returns True.
  2. **`attest_partner(requester_instance)`** → Track 1 `NullAISFederationHooks` returns True (Track 2 would verify TEE attestation).
  3. **Repeated-query detection** → the sliding-window replay guard checks the `(requester_id, encrypted_operand_digest)` pair against `max_repeats_in_window`. First occurrence: allowed, timestamp recorded.
- Verdict: `PolicyVerdict(ALLOW)`. The HE backend runs the aggregate. The in-memory `audit_log` records the verdict; the router persists it durably.

**The security property, made structural.** Now suppose the Lab tries to read a municipality's raw sample instead:
- `permit(lab_principal, "sample:read_detail", muni_A_sample, ctx)`.
- Step 3: the Data Source Lab preset granted `compute:*` and `pipeline:write_results` — **not** `sample:read_detail`. No structural grant.
- Step 4: the sample is not PUBLIC (municipal wastewater data is `PRIVATE`/`LAB`). No ALLOW policy fires.
- Verdict: **DENY** by default-deny.
- **What this shows:** "computes without seeing" is not enforced by a special rule — it is the *absence* of a capability in the Lab's grant set. `permit()` ALLOWs the HE operation (capability present) and DENYs the raw read (capability absent) for the same principal over the same data. The privacy guarantee is structural, and the three-party non-collusion assumption (Driver et al. §4) sits *outside* the authorization model in the deployment topology, while the per-query replay defense sits in `PolicyChecker`, not `permit()` — a clean separation of three distinct concerns (authorization / replay / collusion).

### 9.5 What the four traces establish

| Concern | Enforced by | Shown in |
|---|---|---|
| Single-admin simplicity | structural grant at Instance scope; inert policies | 9.1 |
| Tenant isolation | scope-containment failure → default-deny | 9.2 A |
| Narrow surveillance read | gated ALLOW policy on `surveillance_relevant` | 9.2 B |
| Per-flow federation separation | independent capabilities (`sample:read` vs `federation:push`) | 9.3 A/B |
| Sovereignty over federation | deny-precedence of the deletion-lifecycle guard | 9.3 B |
| Federation origin integrity | key-auth + body cross-check (403 on mismatch) | 9.3 C |
| Compute-without-read | capability *absence* in the grant set | 9.4 |

Every row is the *same* `permit()` with different grants and policies — no scenario needed a bespoke code path. That is the thesis of the whole model: one decision function, attribute-and-scope driven, with roles as issuing-time presets and sovereignty/federation as policies and grants rather than special layers.

---

## 10. Migration from APGAP

The migration is **greenfield** — wipe and reseed, no compatibility shim, no dual-running of the old ladder beside the new engine. This was a deliberate decision (§1): JACKPOT is pre-production, there is no installed base of live deployments whose data must survive a model change, and a compat layer that translated APGAP roles into capabilities on the fly would be exactly the "second place where access is decided" that §2.1 and §6.1 warn against. The old model is removed in the same change that adds the new one.

This section is the *strategy*; the per-task sequencing is §11.

### 10.1 What "greenfield" means concretely

Three things are deleted outright, not migrated:

- The `~60-line attribute ladder` in `backend/auth/permissions.py` (`_base_access` and its callers).
- The two boolean columns `users.is_platform_admin` and `users.is_data_analyst`.
- The six-value APGAP permission-group enum on `lab_membership` rows.

Three things replace them:

- The `permit()` engine (§5) plus its `visibility_sql_clause` list-filtering companion.
- A grants table (capability + scope_ref + conditions + source, per §2.2) and a policy set (§2.5).
- A `sharing_agreements` table (§7.3) for the federation Layer 2 grants.

Because there is no installed base, "wipe" is literal: the migration drops the old columns/enum and the new tables start empty. What needs care is not *preserving* old data but *reseeding* the development and any demo deployments so they come up usable.

### 10.2 The reseed — stored roles become grants

The reseed is a one-time script (Python, per the no-`sed`/no-ORM conventions — raw SQL via `text()`, §5.2) that reads whatever principals exist and issues each the preset grants matching their old role. The mapping is the §8.5 table, run as data:

| Old stored fact | Reseed action |
|---|---|
| `is_platform_admin = TRUE` | apply **Instance Administrator** preset at `instance:<id>` |
| `is_data_analyst = TRUE` | apply **Surveillance Officer** preset at `org:<id>` (or `instance` for single-org) |
| `lab_membership` = Lab Director | apply **Lab Lead** preset at `lab:<id>` |
| `lab_membership` = Lab Collaborator | apply **Lab Member (read-write)** preset at `lab:<id>` |
| `lab_membership` = Lab Reader | apply **Lab Member (read-only)** preset at `lab:<id>` |
| `lab_membership` = Bioinformatics User | apply **Lab Member (read-write)** preset at `lab:<id>` **+** the `pipeline:run` capability |
| `lab_membership` = Platform Admin (group) | apply scope-appropriate admin preset (usually folds into the principal's Lab Lead / Instance Administrator grants) |

After the reseed runs and is verified, the old columns and enum are dropped in the same migration. The reseed reads them; the migration that contains the reseed removes them; there is never a window where both the boolean and the grants are authoritative.

### 10.3 The guard rewrite — role-checks become capability-checks

Distinct from the reseed (which moves *stored data*), the route guards move *decision logic* and must be tracked as their own migration work item: **every `require_*_role`-style guard (`require_platform_admin`, and any lab-role guard) maps to a `require_capability(...)` call, enumerated per endpoint.** The reseed handles "who holds what"; this handles "what each route checks." They are separate because a correct reseed with un-rewritten guards still checks the dead boolean, and rewritten guards with no reseed have no grants to check against — both halves must land together.

The rewrite is mechanical but must be done per-endpoint, because the right capability depends on what the endpoint *does*: `POST /federation/instances` needs `federation:configure_peer` (or `org:manage`); `POST /samples` needs `sample:create` at the target scope; a deletion-approval route needs `deletion:approve` and inherits the §6.2-1b separation-of-duties DENY for free. The deliverable is an **endpoint→capability map** — one row per guarded route — produced by walking every current `require_platform_admin` / lab-role call site. Guards should be *renamed* to their capability (not kept as role-named aliases): a guard still called `require_platform_admin` after the role is abolished re-invites the §9.3 drift, where a reader assumes the role survives. The engine checks capabilities (§8.1); the guard names must say so.

### 10.4 What does *not* change

Worth stating, because greenfield can read as "rewrite everything": the migration does **not** touch the things that were already right. The deletion-status lifecycle (§6, shipped), the federation flow code (FED-A/B, shipped — only its `require_platform_admin` guard is rewritten, not its logic), the `sample_access` workflow (L3 reuses it, §7.4), the audit log, the scrubber/DLP ingest gates, and the schema-codegen pipeline all stay. The migration is scoped to the *authorization decision layer* — `permissions.py`, the two booleans, the role enum, and the route guards — not the surrounding system.

---

## 11. Implementation phasing

The model is large; it lands in dependency order, not all at once. Each phase is independently testable and leaves the system in a working state. The sequencing is driven by what blocks what, and it slots into the existing roadmap (the access-model redesign sits ahead of P0c multi-tenancy, which several phases here feed).

### 11.1 Phase ordering

**Phase M0 — engine, behind a flag.** Build `permit()` (§5) and the grants/policy tables as new code, not yet wired into any route. Ship it dark: the engine exists, is unit-tested against the §9 worked examples as fixtures, but no endpoint calls it yet — the old ladder still runs. This de-risks everything downstream: the decision function is proven correct in isolation before anything depends on it.

**Phase M1 — the `visibility_sql_clause` companion.** Build the list-filtering SQL compiler (§5.2) and prove it behaviorally identical to `permit()` on the same fixtures (a row is list-visible iff `permit()` says detail-accessible). This is the highest-risk piece — two implementations of one logic that must not diverge — so it gets its own phase with cross-checking tests. Still dark; still no route uses it.

**Phase M2 — the reseed + cutover.** Write the §10.2 reseed script and the §10.3 endpoint→capability guard map. Then the cutover migration, in one change: run the reseed, rewrite every guard from role-check to `require_capability`, switch list endpoints to the `visibility_sql_clause` companion, and drop the old booleans/enum/`permissions.py` ladder. This is the one irreversible step; M0/M1 having proven the engine and companion is what makes it safe. Greenfield (§10) means no rollback-to-dual-running — the safety comes from M0/M1, not from a shim.

**Phase M3 — sovereignty policies.** Land the §6 policies (the deletion-lifecycle guards, the Scenario-T Tribal-authority preset and its separation-of-duties carve-out). These ride on the engine from M0 and the `deletion_status` lifecycle that already shipped, so M3 is additive — register policies, no decision-path change. Gated with `sovereignty_mode`; off-deployments are unaffected.

**Phase M4 — federation Layer 2 (`sharing_agreements`).** Add the `sharing_agreements` table (§7.6 Q3 — net-new schema, hand-written migration) and wire agreement-sourced grants into the engine. At this point federated L1 visibility stops being "PUBLIC/DISCOVERABLE only" and starts honoring per-peer agreements. The shipped FED-A/B flow code is unchanged; what changes is that the peer principal now has agreement grants for `permit()`/`visibility_sql_clause` to find. Sequences with or just after P0c.

**Phase M5 — compute plane / cryptWWDB wiring.** Add the §4.6 `compute:*` capabilities to the catalog and the `he_operation_to_capability` mapping (§7.6 Q4), then construct the `make_access_policy` adapter (§7.4) and inject `permit()` into `PolicyChecker.access_policy`. Gated on the cryptWWDB compute path being scheduled (Track 2); the `PolicyChecker` and its repeated-query guard already shipped, so this is the adapter plus the capability additions, not new infrastructure.

### 11.2 The dependency graph, briefly

```
M0 engine ──┬── M1 SQL companion ──┐
            │                       ├── M2 reseed + cutover ──┬── M3 sovereignty policies
            └───────────────────────┘                         ├── M4 sharing_agreements (≈ P0c)
                                                               └── M5 compute / cryptWWDB (Track 2)
```

M0 and M1 are the only hard prerequisites for everything else; M2 is the irreversible cutover; M3/M4/M5 are independent additive phases that can be sequenced by external priority (sovereignty pilot → M3 first; federation growth → M4 first; cryptWWDB schedule → M5 first).

### 11.3 What can be built in parallel, and what cannot

M0 and M1 can be developed concurrently by the same person in either order (they cross-check each other, so building them close together is good). Everything M3–M5 is independent *after* M2. The one thing that **cannot** be parallelized is M2 against M0/M1 — the cutover must not begin until the engine and the SQL companion are both proven, because M2 is the step with no rollback. This is the §11 analog of the project-wide "verify before operating" discipline: prove the new decision path in the dark (M0/M1) before the irreversible switch (M2).

### 11.4 Open items carried into implementation

Collected from the inline flags, so they aren't lost:

- **§6.4** — how the Tribal authority designee is represented (HUMAN principal + Scenario-T preset at Org scope is the recommendation; confirm against a real Scenario T deployment before M3).
- **§7.6 Q1** — the `min_sharing_level_for_federation` org/peer floor composition, to pin when L2 push IO is wired (within M4 or the separate FED L2-IO work).
- **§7.7** — cross-instance consumer sub-scope is not carried today (B can confine which of B's labs A reaches, but cannot condition on which of A's labs consumes). A design extension only if a deployment needs B to *enforce* recipient-lab restrictions; the `X-JACKPOT-Federation-Origin` header is the natural carrier if so. Not needed for M4's lab-to-lab support, which works on the data-holder's side.
- **§7.6 Q4 / §4.6** — the exact `HEOperation` enum membership, read from `backend/backend/crypto/_ais_hooks.py`, to finalize the `compute:*` capability set at M5.
- **FED-FIX-1** — the `federation_enabled` model-default fix; trivial, independent of the M-phases, do it whenever.
- The federation audit-action names (§4.3, §4.6) — proposed, not yet in `audit.py`; reconcile when M4/M5 land their audited actions, alongside the deletion design's lowercase `event_type` names (§6.2).

---

*End of the JACKPOT access-control model. §1–§11 complete: the why (§1), the abstractions (§2–§3), the catalog and engine (§4–§5), sovereignty and federation as first-class policy/grant concerns (§6–§7), the human and machine presets (§8), worked traces across all deployment shapes (§9), and the greenfield migration and phasing (§10–§11).*
