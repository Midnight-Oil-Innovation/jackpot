> **Status:** Reference — endpoint→capability map (ACCESS-GUARD-MAP; prerequisite for M2).

# Endpoint → Capability Map

Generated for ACCESS-GUARD-MAP; prerequisite for M2 guard rewrite.
Capability names drawn from access_model.md §4.
Scope levels: Instance / Org / Lab / Project / Sample (§3.1).
SoD DENY rules from §6.2-1b are noted in the Conditions column.

Rows marked "auth-only today" carry `get_current_user` (or a `Depends`
equivalent) plus in-route ownership/visibility logic, but no role-named
guard; the capability listed is what M2 must enforce via `permit()`.
Rows with a `require_capability(...)` call site already record their
capability in code (renamed in this session from role-named guards).
`—` in the Capability column means one of two things, distinguished by
the Conditions column:

- **AUTH-ONLY BY DESIGN** — the route needs authentication but no
  authorization decision, because the resource is definitionally the
  caller (`users/me`, the caller's own profile or API tokens) or there is
  no resource at all (stateless validation, public reference registries).
  A capability every principal always holds gates nothing and would only
  enlarge the grants table, and the §3.1 scope tree has no user level to
  express "you are yourself". These rows stay auth-only after M2 and are
  covered by route-level tests, not the capability matrix.
- **anything else** — a genuine catalog gap awaiting a verb.

All catalog gaps were resolved in the M2 pre-cutover review (see
`docs/m2_preflight_report.md` §1); the verbs added to §4 as a result are
`pipeline:read`, `lab:read`, `org:read`, `import:read`, `import:manage`,
`submission:prepare`, `access:request`, and `token:manage`.

| Method | Path | Capability | Scope | Conditions / Notes |
|--------|------|------------|-------|--------------------|
| POST | `/api/v1/auth/google/login` | — | Instance | PUBLIC (intentional — OAuth login entry) |
| POST | `/api/v1/auth/refresh` | — | Instance | PUBLIC (intentional — token refresh via cookie) |
| POST | `/api/v1/auth/logout` | — | Instance | PUBLIC (intentional — clears cookies) |
| POST | `/api/v1/auth/dev-login` | — | Instance | PUBLIC — intent VERIFIED: `env != "local"` returns 404 before any work (`routers/auth.py:557`); pinned by `test_dev_login_returns_404_outside_local_mode` |
| GET | `/api/v1/byop/telemetry` | — | Instance | AUTH-ONLY BY DESIGN — telemetry over the shared pipeline catalog; aggregate success rate / walltime / cost, not tenant data |
| POST | `/api/v1/byop/pipelines` | `pipeline:register_custom` | Lab | `permits("pipeline:register_custom", lab_id=owner_lab_id)` (M2-B3). Deliberately NOT the ownership rung: at creation the caller is always the registrant, so routing this through it would make the lab check vacuous. A lab-less (`sharing_scope='private'`) registration needs only authentication |
| GET | `/api/v1/byop/pipelines` | — | Instance | AUTH-ONLY BY DESIGN — catalog browse (`byop.py`: "list-all is INTENTIONALLY unscoped per design §9"); a pipeline definition is not tenant data. Mutations stay tenancy-guarded |
| GET | `/api/v1/byop/pipelines/{pipeline_id}` | — | Instance | AUTH-ONLY BY DESIGN — same catalog browse; `_get_or_404_tenancy` gates the mutations, not this read |
| PATCH | `/api/v1/byop/pipelines/{pipeline_id}` | `pipeline:register_custom` | Lab | `_may_manage` (M2-B3): `pipeline:register_custom` at `owner_lab_id`, OR the registrant via an attribute-policy. Denial collapses to 404 (§3.3) |
| PUT | `/api/v1/byop/pipelines/{pipeline_id}` | `pipeline:register_custom` | Lab | `_may_manage` (M2-B3) — same route function as PATCH |
| DELETE | `/api/v1/byop/pipelines/{pipeline_id}` | `pipeline:register_custom` | Lab | `_may_manage` (M2-B3); soft-delete to ARCHIVED |
| POST | `/api/v1/byop/pipelines/{pipeline_id}/revalidate` | `pipeline:register_custom` | Lab | `_may_manage` (M2-B3) |
| POST | `/api/v1/byop/pipelines/{pipeline_id}/deactivate` | `pipeline:register_custom` | Lab | `_may_manage` (M2-B3) |
| POST | `/api/v1/byop/pipelines/{pipeline_id}/archive` | `pipeline:register_custom` | Lab | `_may_manage` (M2-B3) |
| GET | `/api/v1/dataharmonizer/templates/{source_type}/{tier}` | — | Instance | PUBLIC (intentional — templates are public, Critical Rule 42) |
| POST | `/api/v1/dataharmonizer/validate` | — | Instance | AUTH-ONLY BY DESIGN — stateless validation utility; no resource, no scope, nothing to gate |
| GET | `/api/v1/domain-whitelist/` | `whitelist:manage` | Instance | `require_capability("whitelist:manage")` |
| POST | `/api/v1/domain-whitelist/` | `whitelist:manage` | Instance | `require_capability("whitelist:manage")` |
| DELETE | `/api/v1/domain-whitelist/{domain_id}` | `whitelist:manage` | Instance | `require_capability("whitelist:manage")` |
| GET | `/api/v1/federation/instances` | `federation:configure_peer` | Instance | `require_capability("federation:configure_peer")` |
| POST | `/api/v1/federation/instances` | `federation:configure_peer` OR `org:manage` | Instance | `require_capability("federation:configure_peer")` (§10.3 example) |
| POST | `/api/v1/federation/search` | `sample:read` | Instance | auth-only today; L1 federated query fan-out (§7.4) |
| POST | `/api/v1/federation/push` | `federation:push` | Lab | peer-key auth (`authenticate_federation_peer`); §6.2-3 `sovereignty.no_federate_deleting` DENY applies on the sender |
| POST | `/api/v1/federation/access-requests` | `access:approve_request` | Sample | peer-key auth + anti-spoofing body cross-check (403 on mismatch, §7.6-Q2); brokers into `sample_access` workflow (L3) |
| GET | `/api/v1/files/broken` | `sample:read` | Lab | `sample_list_clause` (M2-B7) — a broken file lists exactly when its sample lists |
| GET | `/api/v1/files/` | `sample:read` | Lab | `sample_list_clause` (M2-B7) |
| GET | `/api/v1/files/{file_id}` | `sample:read_detail` | Sample | `require_capability("sample:read_detail", sample_id=…)` on the referencing sample (M2-B2); a 403 is collapsed into FILE_NOT_FOUND so existence is not leaked |
| POST | `/api/v1/files/{file_id}/promote` | `sample:update` | Sample | `require_capability("sample:update", sample_id=…)` (M2-B2). WIDENED deliberately: the legacy branch required a Lab Director, the map's verb is also held by lab_member_rw |
| GET | `/api/v1/files/jobs/{job_id}` | `sample:read` | Sample | `require_capability("sample:read", sample_id=…)` on the job's file (M2-B2). Decided at **Sample** scope, not Lab: the job names one file, so its sample is resolvable and the narrower scope is the honest one |
| POST | `/api/v1/files/{file_id}/verify` | `sample:update` | Sample | `require_capability("sample:update", sample_id=…)` (M2-B2) |
| POST | `/api/v1/gisaid/export/{lab_id}` | `sample:read_detail` | Lab | `require_capability("sample:read_detail")` — export reads lab samples |
| GET | `/api/v1/import_mappings/` | `import:read` | Lab | auth-only today; mapping-config read |
| GET | `/api/v1/import_mappings/{mapping_id}` | `import:read` | Lab | auth-only today |
| POST | `/api/v1/import_mappings/` | `import:manage` | Lab | auth-only today; mapping-config write |
| PATCH | `/api/v1/import_mappings/{mapping_id}` | `import:manage` | Lab | auth-only today |
| DELETE | `/api/v1/import_mappings/{mapping_id}` | `import:manage` | Lab | auth-only today; soft-delete (is_active=false) |
| POST | `/api/v1/imports/sessions/` | `sample:create` | Lab | `require_capability("sample:create", lab_id=…)` (M2-B2); narrower than the membership test it replaced — a Lab Reader is a member but holds no `sample:create` |
| GET | `/api/v1/imports/sessions/` | `sample:read` | Lab | `lab_list_clause("sample:read")` (M2-B7), on top of the owner filter — a session stops listing when the caller loses access to its lab |
| GET | `/api/v1/imports/sessions/{session_id}` | `sample:read` | Lab | `require_capability("sample:read", lab_id=…)` on the session's lab (M2-B2), after the owner filter |
| PATCH | `/api/v1/imports/sessions/{session_id}` | `sample:create` | Lab | `require_capability("sample:create", lab_id=…)` (M2-B2) |
| POST | `/api/v1/imports/sessions/{session_id}/import` | `sample:create` | Lab | `require_capability("sample:create", lab_id=…)` (M2-B2); re-checked here, not trusted from session-creation time |
| DELETE | `/api/v1/imports/sessions/{session_id}` | `sample:create` | Lab | `require_capability("sample:create", lab_id=…)` (M2-B2); deletes staging session, not samples |
| POST | `/api/v1/ingest/upload` | `sample:create` | Lab | `require_capability("sample:create", lab_id=…)` (M2-B2), before any byte is staged |
| POST | `/api/v1/ingest/csv` | `sample:create` | Lab | `require_capability("sample:create", lab_id=…)` per row (M2-B2), memoized per lab; a denied row fails as that row's error and the rest of the upload proceeds |
| POST | `/api/v1/ingest/register` | `sample:create` | Lab | `require_capability("sample:create", lab_id=…)` (M2-B2). Closes a real gap: `lab_id` came from the request body and nothing checked it (BYOP no-copy registration, Rule 57) |
| POST | `/api/v1/ingest/globus` | `deposit:record` | Instance | `require_capability("deposit:record")` — records a deposit and notifies directors; creates no samples, so it is not `sample:create` (corrected in M2-B1). A SERVICE principal is the better long-term fit if the facility calls it directly (cf. M2-B6) |
| POST | `/api/v1/labs/` | `org:manage` | Instance | `require_capability("org:manage")` |
| GET | `/api/v1/labs/` | `lab:read` | Org | auth-only today; lab directory read |
| GET | `/api/v1/labs/{lab_id}` | `lab:read` | Lab | auth-only today |
| PATCH | `/api/v1/labs/{lab_id}` | `org:manage` | Lab | `require_capability("org:manage")` at lab scope |
| DELETE | `/api/v1/labs/{lab_id}` | `org:manage` | Instance | `require_capability("org:manage")` |
| GET | `/api/v1/labs/{lab_id}/members` | `user:manage` | Lab | `require_capability("user:manage")` |
| POST | `/api/v1/labs/{lab_id}/members` | `user:manage` | Lab | `require_capability("user:manage")` |
| PATCH | `/api/v1/labs/{lab_id}/members/{user_id}` | `user:manage` | Lab | `require_capability("user:manage")` |
| DELETE | `/api/v1/labs/{lab_id}/members/{user_id}` | `user:manage` | Lab | `require_capability("user:manage")` |
| POST | `/api/v1/organizations/` | `org:manage` | Instance | `require_capability("org:manage")` |
| GET | `/api/v1/organizations/` | `org:manage` | Instance | `require_capability("org:manage")` |
| GET | `/api/v1/organizations/{org_id}` | `org:read` | Org | auth-only today |
| PATCH | `/api/v1/organizations/{org_id}` | `org:manage` | Instance | `require_capability("org:manage")` |
| DELETE | `/api/v1/organizations/{org_id}` | `org:manage` | Instance | `require_capability("org:manage")` |
| GET | `/api/v1/pipelines/` | `pipeline:read` | Project | `project_list_clause("pipeline:read")` OR launched-by (M2-B7) — same verb and scope the per-run status routes check, so the list cannot show a run those routes would refuse |
| POST | `/api/v1/pipelines/launch` | `pipeline:run` | Project | `permits("pipeline:run", project_id=…)` (M2-B3). §8.2 puts the verb in Lab Lead and Lab Member RW, so who can launch is unchanged except that read-only members no longer can. The in-route per-sample checks were CONVERTED, not dropped — each input now takes `sample:read_detail` at its own sample scope, which also picks up PUBLIC, owned and per-sample-granted inputs the lab test could not see |
| POST | `/api/v1/pipelines/events` | `pipeline:write_results` | Instance | SERVICE-authenticated (NOT public): per-run `X-Pipeline-Token`, `hmac.compare_digest`, 401 on mismatch (`routers/pipelines.py:903`). Rule 60's never-raises applies to weblog delivery, not auth. M2 adds the SERVICE-principal `permit()` call |
| GET | `/api/v1/pipelines/{run_id}` | `pipeline:read` | Project | `_may_read_run` -> `permits("pipeline:read", project_id=…)` (M2-B3). Capability corrected from `pipeline:run` in M2-B3-PRE — §4 defines `pipeline:read` as covering run status, and the old reading would have hidden a lab's own runs from its Collaborators and Readers |
| GET | `/api/v1/pipelines/{run_id}/tasks` | `pipeline:read` | Project | `_may_read_run` -> `permits("pipeline:read", project_id=…)` (M2-B3). Capability corrected from `pipeline:run` in M2-B3-PRE — §4 defines `pipeline:read` as covering run status, and the old reading would have hidden a lab's own runs from its Collaborators and Readers |
| GET | `/api/v1/pipelines/{run_id}/events` | `pipeline:read` | Project | `_may_read_run` -> `permits("pipeline:read", project_id=…)` (M2-B3). Capability corrected from `pipeline:run` in M2-B3-PRE — §4 defines `pipeline:read` as covering run status, and the old reading would have hidden a lab's own runs from its Collaborators and Readers |
| POST | `/api/v1/pipelines/{run_id}/resume` | `pipeline:run` | Project | `permits("pipeline:run", project_id=…)` (M2-B3) — resume launches work, so the write verb, not the read one |
| POST | `/api/v1/pipelines/custom` | `pipeline:register_custom` | Lab | `require_capability("pipeline:register_custom")` |
| POST | `/api/v1/pipelines/{catalog_id}/promote` | `pipeline:promote` | Lab or Instance | `require_capability("pipeline:promote")` — lab scope for lab-tier target, instance scope for global tier |
| POST | `/api/v1/pipelines/{run_id}/results/{result_type}` | `pipeline:write_results` | Project | SERVICE-authenticated (NOT public): same per-run token check, `INVALID_TOKEN` 401 (`routers/pipelines.py:1495`). M2 adds the SERVICE-principal `permit()` call |
| POST | `/api/v1/profiles/` | — | Instance | AUTH-ONLY BY DESIGN — creates the caller's own USER profile (not an execution profile) |
| GET | `/api/v1/profiles/me` | — | Instance | AUTH-ONLY BY DESIGN — caller's own USER profile |
| GET | `/api/v1/profiles/{user_id}` | `user:manage` | Org | auth-only today; self OR user:manage at M2 |
| PUT | `/api/v1/profiles/{user_id}` | `user:manage` | Org | auth-only today; self OR user:manage at M2 |
| POST | `/api/v1/projects/` | `org:manage` | Lab | `require_capability("org:manage")` at lab scope (§4.5: org:manage covers projects) |
| GET | `/api/v1/projects/` | `sample:read` | Lab | auth-only today; membership-filtered list |
| GET | `/api/v1/projects/{project_id}` | `sample:read` | Project | auth-only today |
| PATCH | `/api/v1/projects/{project_id}` | `org:manage` | Lab | `require_capability("org:manage")` at lab scope |
| POST | `/api/v1/sample-access/requests` | `access:request` | Sample | `require_capability("access:request", sample_id=…)` (M2-B2). Carried by an ALLOW **policy** on DISCOVERABLE, not a grant: the requester is by definition not a member of the sample's lab, so no preset could hold it at a covering scope |
| GET | `/api/v1/sample-access/requests` | `sample:read` | Lab | `sample_list_clause("access:approve_request")` OR requester (M2-B7). Replaces the platform-admin bypass and the `is_lab_director` subquery; a director whose grant sits at org scope now sees their org's requests, which `lab_id IN (…)` could not express |
| POST | `/api/v1/sample-access/requests/{request_id}/approve` | `access:approve_request` | Sample | `require_capability("access:approve_request", sample_id=…)` (M2-B2); scoped, so a director of another lab no longer passes |
| POST | `/api/v1/sample-access/requests/{request_id}/deny` | `access:approve_request` | Sample | `require_capability("access:approve_request", sample_id=…)` (M2-B2) |
| GET | `/api/v1/samples/` | `sample:read` | Lab | `sample_list_clause` (M2-B7) — compiled from the same grants and LADDER_POLICIES `permit()` reads; `select_all` uses the identical fragment |
| GET | `/api/v1/samples/{sample_id}` | `sample:read_detail` | Sample | `require_capability("sample:read_detail", sample_id=…)` (M2-B2); fetch stays ahead of the guard so 404 semantics are unchanged |
| PATCH | `/api/v1/samples/{sample_id}` | `sample:update` | Sample | `require_capability("sample:update", sample_id=…)` (M2-B2); Lab Reader excluded by preset, not by a branch |
| DELETE | `/api/v1/samples/{sample_id}` | `sample:archive` | Sample | `require_capability("sample:archive", sample_id=…)` (M2-B2); `sample:archive` is lab_lead + instance_administrator only. Archive-vs-soft_delete semantics still open (M3) |
| GET | `/api/v1/samples/{sample_id}/files` | `sample:read_detail` | Sample | `require_capability("sample:read_detail", sample_id=…)` (M2-B2) |
| GET | `/api/v1/samples/{sample_id}/download` | `sample:read_detail` | Sample | `require_capability("sample:read_detail", sample_id=…)` (M2-B2). The narrower raw_fastq Lab-Director restriction inside the route is unchanged — no §4 verb names it; see Residue below |
| GET | `/api/v1/sequencing-labs/` | — | Instance | AUTH-ONLY BY DESIGN — registry of physical facilities; every ingesting user needs it |
| POST | `/api/v1/sequencing-labs/` | `org:manage` | Instance | `require_capability("org:manage")` |
| GET | `/api/v1/sequencing-labs/{seq_lab_id}` | — | Instance | AUTH-ONLY BY DESIGN — detail read of the same facility registry |
| PATCH | `/api/v1/sequencing-labs/{seq_lab_id}` | `org:manage` | Instance | `require_capability("org:manage")` |
| POST | `/api/v1/sequencing-labs/{seq_lab_id}/assign/{lab_id}` | `org:manage` | Instance | `require_capability("org:manage")` |
| DELETE | `/api/v1/sequencing-labs/{seq_lab_id}/assign/{lab_id}` | `org:manage` | Instance | `require_capability("org:manage")` |
| GET | `/api/v1/settings/public` | — | Instance | PUBLIC (intentional — public instance settings) |
| POST | `/api/v1/submissions/` | `submission:prepare` | Lab | auth-only today; pairs with `submission:approve` |
| GET | `/api/v1/submissions/` | `sample:read` | Lab | auth-only today |
| GET | `/api/v1/submissions/{submission_id}` | `sample:read` | Lab | auth-only today |
| PATCH | `/api/v1/submissions/{submission_id}` | `submission:prepare` | Lab | auth-only today |
| DELETE | `/api/v1/submissions/{submission_id}` | `submission:prepare` | Lab | auth-only today; soft-delete |
| POST | `/api/v1/submissions/{submission_id}/samples` | `submission:prepare` | Lab | auth-only today |
| DELETE | `/api/v1/submissions/{submission_id}/samples` | `submission:prepare` | Lab | auth-only today |
| POST | `/api/v1/submissions/{submission_id}/validate` | `submission:prepare` | Lab | auth-only today; readiness check, same authz question as CRUD |
| POST | `/api/v1/submissions/{submission_id}/generate` | `submission:prepare` | Lab | auth-only today; builds BioSample XML + optional file copy — heavier, same authz question |
| POST | `/api/v1/submissions/{submission_id}/mark-submitted` | `submission:approve` | Lab | auth-only today; §6.2-2 `deletion.no_publish_while_deleting` DENY (deletion_status != ACTIVE → 422) |
| POST | `/api/v1/submissions/{submission_id}/register-accessions` | `submission:approve` | Lab | auth-only today |
| POST | `/api/v1/submissions/{submission_id}/mark-rejected` | `submission:approve` | Lab | auth-only today |
| POST | `/api/v1/submissions/{submission_id}/withdraw` | `submission:approve` | Lab | auth-only today |
| POST | `/api/v1/submissions/{submission_id}/execute` | `submission:approve` | Lab | auth-only today; §6.2-2 DENY applies |
| POST | `/api/v1/submissions/{submission_id}/retry-execution` | `submission:approve` | Lab | auth-only today |
| GET | `/api/v1/submissions/{submission_id}/execution-logs` | `sample:read` | Lab | auth-only today |
| GET | `/api/v1/templates/` | — | Instance | PUBLIC (intentional — Rule 42, templates are public) |
| GET | `/api/v1/templates/enums` | — | Instance | PUBLIC (intentional — Rule 42) |
| GET | `/api/v1/templates/source-types` | — | Instance | PUBLIC (intentional — Rule 42) |
| GET | `/api/v1/tokens/` | `token:manage` | Instance | self path AUTH-ONLY BY DESIGN (caller's own tokens); `token:manage` required only to list another user's |
| POST | `/api/v1/tokens/` | — | Instance | AUTH-ONLY BY DESIGN — mints a token for the caller only; no other principal reachable |
| DELETE | `/api/v1/tokens/{token_id}` | `token:manage` | Instance | self path AUTH-ONLY BY DESIGN (owner revokes own); `token:manage` required only to revoke another user's |
| GET | `/api/v1/users/me` | — | Instance | AUTH-ONLY BY DESIGN — caller's own user record + memberships |
| GET | `/api/v1/users/` | `user:manage` | Instance | `require_capability("user:manage")` |
| GET | `/api/v1/users/{user_id}` | `user:manage` | Org | auth-only today; self OR user:manage at M2 |
| PATCH | `/api/v1/users/{user_id}` | `user:manage` | Org | auth-only today; self OR user:manage in-route |
| DELETE | `/api/v1/users/{user_id}` | `user:manage` | Instance | `require_capability("user:manage")` |
| GET | `/api/v1/wastewater/sites` | `sample:read_surveillance` | Org | `sample_list_clause` (M2-B7) |
| GET | `/api/v1/wastewater/lineage-abundance` | `sample:read_surveillance` | Org | `sample_list_clause` (M2-B7) |

## Sample plane after M2-B2

20 of the 27 sample-plane rows now carry a `require_capability(...)` call.
The other 7 do not, and the reason is structural rather than a shortfall.

**A route can only be guarded by `require_capability` when it names one
resource.** The guard resolves a scope from a `lab_id` or a `sample_id` and
asks one question about it. A list endpoint names none: its authorization
*is* the row filter, and asking the question at the instance root instead
would demand an instance-wide grant and deny every ordinary lab member the
whole endpoint. That is not a conservative approximation — it is a louder
version of exactly the silent-removal failure the B2 pre-work existed to
avoid. Those 7 rows are M2-B7's, which compiles the same rules into SQL via
`visibility_sql_clause` and keeps `new_visible ⊆ legacy_visible` as its
invariant:

| Method | Path |
|--------|------|
| GET | `/api/v1/samples/` |
| GET | `/api/v1/files/` |
| GET | `/api/v1/files/broken` |
| GET | `/api/v1/imports/sessions/` |
| GET | `/api/v1/sample-access/requests` |
| GET | `/api/v1/wastewater/sites` |
| GET | `/api/v1/wastewater/lineage-abundance` |

**M2-B7 landed these**, plus `GET /api/v1/pipelines/`. They no longer run on
`permissions.visibility_sql_clause`; see "List plane after M2-B7" below.

### What the guard gained

Sample-scoped decisions now carry the row's attributes
(`principal.sample_resource`), evaluated against `policy.LADDER_POLICIES`.
Without that, the three permissive rungs of the legacy ladder — a PUBLIC
sample readable by anyone, a surveillance-relevant row readable by a
`sample:read_surveillance` holder, a sample readable by its owner — would
have evaluated against absent attributes, which reads as DENY. B2's read
routes would have kept working for lab members and quietly stopped working
for everyone else.

`access:request` is the one capability held by no preset and no grant. It
is an ALLOW policy on `sharing_level = DISCOVERABLE`, because the whole
premise of the self-serve workflow is that the asker is *not* a member of
the lab they are asking.

### Residue — deliberately still on the legacy check

- `GET /api/v1/samples/{sample_id}/download?file_type=raw_fastq` keeps its
  in-route Lab-Director test. The map gives the route one capability,
  `sample:read_detail`, and this is a narrower restriction inside it with no
  §4 verb to name it. Dropping it to finish the rewrite would widen access
  to un-scrubbed reads. Needs a verb (M2-B5 owns catalog additions).
- `POST /api/v1/files/{file_id}/promote` moved the other way: the map's
  `sample:update` is held by `lab_member_rw`, so a Lab Collaborator can now
  promote where the legacy branch required a Director. Recorded as a
  deliberate widening, not an oversight — if the narrower rule was intended
  it needs its own verb rather than a re-added branch.

### Known divergence from the legacy ladder

Project-only membership. `permissions._base_access` admitted a project
member; no preset issues grants at Project scope, so after B2 a user whose
only tie to a sample is `project_membership` is denied. This is the
divergence `reseed()`'s pre-flight guard counts as `project_only_membership`
so an operator sees the number before cutover — not a new B2 finding, but
B2 is where it becomes reachable from a route.

Deletion-approval note (§10.3 example): no deletion-approval route exists
yet (the B-CARE-3 lifecycle routes land with P0c/M3). When it lands it
takes `deletion:approve` at Sample scope and inherits the §6.2-1b
`deletion.separation_of_duties` DENY (approver ≠ requester unless the
audited platform-admin self-approve flag is set).

## Pipeline plane after M2-B3

11 routes converted: 7 BYOP mutations, launch + resume, and the 3 run-status
reads. The original batch said 16; three BYOP catalog reads became AUTH-ONLY
BY DESIGN and two are B7-class lists (see below).

### The read/run split is the whole batch

§4 defines `pipeline:read` as "the pipeline zoo, the BYOP registry, and run
status"; `pipeline:run` is the launch verb, held by `lab_lead` and
`lab_member_rw` but not by `lab_member_ro`. Watching a run and starting one
are different acts. Getting this backwards fails in both directions:
`pipeline:run` on the status routes hides a lab's own runs from its read-only
members, and `pipeline:read` on launch lets a read-only member start
compute.

### What a BYOP pipeline belongs to

`byop_pipelines.owner_lab_id` is nullable, which looked like an open question
and turned out to be answered by the schema: `sharing_scope` admits
`'private'`, a pipeline belonging to a person rather than a lab. So:

- **lab-owned** — `pipeline:register_custom` at `owner_lab_id`.
- **private** (`owner_lab_id IS NULL`) — no lab scope exists, so only the
  registrant policy or an instance-wide grant can match. Correct, not a gap.
- **the registrant, either way** — an ALLOW policy on
  `registered_by_user_id`, the same shape sample ownership needed in PRE-A.
  As a grant it would mean a row written per registration and deleted per
  transfer.

The column stays nullable; the policy is what makes that safe.

**One trap, pinned by a regression test.** Creation must NOT go through the
ownership rung. At creation the caller is always the registrant, so the rung
matches every time and the lab check becomes vacuous — any authenticated user
could place a pipeline into any lab. `create_pipeline` asks the grant question
only.

### Deliberate narrowings

- **Launch and resume**: `pipeline:run` replaces "any lab or project member".
  §8.2's Lab Member (read-write) block holds the verb, so Collaborators and
  Bioinformatics Users are unaffected; **read-only members lose launch**,
  which they should never have had.

  This nearly went the other way. The reseed excluded `pipeline:run` from
  `lab_member_rw` and added it back only for Bioinformatics User, reading
  §8.5's "folded into Lab Member RW + `pipeline:run`" as meaning RW lacked
  it. §8.2's preset block says the opposite in as many words: "can run
  pipelines but not approve submissions or access requests". Shipping on the
  reseed's reading would have taken launch from every Lab Collaborator and
  called it intentional. Corrected here, in the reseed and in §8.5's prose.
- **BYOP mutation on a lab-owned pipeline**: `pipeline:register_custom` sits
  in `lab_lead`, so ordinary lab membership is no longer enough. A
  Bioinformatics User keeps full control of the pipelines they registered
  themselves, through the registrant rung.
- **Project-only membership** loses launch, as it lost sample access in B2.
  Same registered divergence (`project_only_membership`).

### The run list

`GET /api/v1/pipelines/` was a B7-class list and landed there: `pipeline:read`
at the run's project scope, OR the caller launched it.

## List plane after M2-B7

All 8 list endpoints now compile their filter from the same grants and
policies `permit()` reads. `backend/permissions.py` has **no production
callers left** — only the equivalence harness that compares against it.

### Why one builder, not eight call sites

Three things have to match the row-wise guard exactly: the scope expression,
the policy set, and the attribute-column mapping. Assembling them per call
site is how the two halves drift, and a list that drifts *wider* leaks rows
with no error and no audit entry. So they are assembled once —
`authz.visibility.sample_list_clause` — and the routes pass table aliases.

Three levels exist because not every list is sample-rooted:

| Builder | Scope SQL | Used by |
|---|---|---|
| `sample_list_clause` | `scope_sql` | samples, files ×2, wastewater ×2, sample-access |
| `lab_list_clause` | `lab_scope_sql` | import sessions |
| `project_list_clause` | `project_scope_sql` | pipeline runs |

The lab and project builders pass **no policies**, deliberately: every entry
in `LADDER_POLICIES` reads a *sample* attribute, so passing them would
compile predicates against columns those rows do not have. Rows at those
levels are decided by structural grants alone, which is what `permit()` does
for them too.

`is_canonical_scope_sql` accepts all three by re-deriving each candidate and
comparing bytes, rather than by loosening its regex — adding a level cannot
accidentally widen what it admits.

### Two ownership rungs kept

`sample-access/requests` and `pipelines/` each keep an OR on "rows you
created". No grant expresses "the request you filed" or "the run you
started", the legacy filters admitted both, and removing them would narrow
access this batch was not asked to narrow.

Their *other* rung replaced a legacy bypass in each case: the platform-admin
branch is gone from both, because an instance-scoped grant contains every
path beneath it.

### What the invariant covers, and what it does not

`tests/authz/test_cutover_preflight.py` asserts, on real PostgreSQL:

- `new_visible ⊆ legacy_visible` for every persona — unconditional;
- every legacy-only row attributed to a registered divergence class;
- the SQL fragment and `permit()` agreeing **row by row**.

M2-B7 pointed those at the production policy set and attribute columns. They
previously ran with `policies=[]`, which measures grants alone — a strict
subset of what the deployed list shows, and a proof about something nobody
runs.

**That proof reaches the six sample-rooted lists only.** It is built on
`samples`, so it cannot say anything about `imports/sessions` or
`pipelines/`. Those two are covered by route tests, and their relationship to
the legacy filter is worth stating plainly rather than implying:

- **`imports/sessions` narrows.** Ownership was previously the entire filter;
  a lab rung is added on top, so the new set is a strict subset. Nothing can
  appear that did not before.
- **`pipelines/` can widen, but only by configuration.** Legacy read
  `lab_id IN (SELECT lab_id FROM lab_membership …)`; the new filter is a
  `pipeline:read` grant covering the run's project scope. A lab-scoped grant
  gives the same set. An **org-scoped** grant would give more — every lab in
  the org — which the legacy form could not express. Today no preset issues
  org-scoped grants (reseed writes lab and instance scopes only), so the sets
  match; an operator who issues one later gets the wider reading, which is
  what an org-scoped grant is supposed to mean. Same class as the
  director-at-org-scope widening on the access-request list.

### Measured, not assumed

The backlog asked whether prefix `LIKE` over a computed expression needs an
expression index. Measured at 3,000 samples on PostgreSQL:

| | Estimated cost | Execution |
|---|---|---|
| New (`sample_list_clause`) | 113 | 5.3 ms |
| Legacy (`permissions.py`) | 3,923 | 7.1 ms |

Both sequential-scan `samples`. The new fragment is **faster**, because the
legacy ladder also ran four correlated `EXISTS` subqueries. No index added —
this is not a regression, and one would be speculative. Revisit if a
deployment's sample count makes the scan itself the problem; the scan, not
the fragment, is what would need fixing.

## Gaps

Routes with no user JWT. All three rows previously flagged
`PUBLIC (verify intent)` were reviewed against the handlers; the
outcome is one confirmation and two corrections:

- `POST /api/v1/auth/dev-login` — **PUBLIC, verified.** `settings.env != "local"`
  returns 404 as the first statement of the handler (`routers/auth.py:557`),
  before any lookup or write, and 404 rather than 403 so the route's existence
  is not confirmed in non-local deployments. Pinned by
  `tests/test_dev_login_endpoint.py::test_dev_login_returns_404_outside_local_mode`.
  Behavioral note, unchanged and intended: on success it mutates the cached
  `settings.mock_user_email`, switching identity process-wide for subsequent
  requests — the mechanism the UAT role-switch scripts rely on, unreachable
  outside local.
- `POST /api/v1/pipelines/events` — **not public.** Authenticates the per-run
  `X-Pipeline-Token` minted at launch, compared with `hmac.compare_digest`,
  401 on missing or wrong token (`routers/pipelines.py:903`). Both failure
  modes pinned (`tests/test_pipelines_router_api.py:892,908`). Rule 60's
  "receiver never raises" governs weblog *delivery* errors; a rejected token
  is a deliberate 401, and the H-4 log poller covers anything lost.
- `POST /api/v1/pipelines/{run_id}/results/{result_type}` — **not public.**
  Same per-run token check returning `INVALID_TOKEN` 401
  (`routers/pipelines.py:1495`); pinned by
  `tests/test_pipelines_registration_api.py:92,111`.

**M2 work on the two token routes.** The token today collapses authentication
and authorization: holding the run's token *is* the permission, because the
token is per-run. M2 keeps the token as authentication and adds a `permit()`
call with a SERVICE principal holding `pipeline:write_results` at the run's
project scope. The point is not that the token check is weak — it is that
separating the two is what makes the cryptWWDB property structural (§4.6,
§9.4): a `data_source_lab` principal holds `pipeline:write_results` and not
`sample:read_detail`, and `permit()` is where that becomes enforceable rather
than a consequence of how tokens happen to be minted.
- `GET /api/v1/settings/public`, `GET /api/v1/templates/*`, `GET /api/v1/dataharmonizer/templates/*`, `POST /api/v1/auth/{google/login,refresh,logout}` — intentionally public (login flow, public settings, Rule 42 public templates).
- Stub routers returning `{"status": "not implemented"}` (no auth, no data): `archive_requests`, `billing`, `dataset_access`, `datasets`, `ncbi_submissions`, `notifications`, `saved_searches`, `GET /api/v1/ingest/`. Guard when implemented; excluded from the table above.

Catalog gaps (`—` capability, authenticated routes): BYOP/pipeline/lab/org
registry reads, import-mapping CRUD, submission-package assembly,
self-scoped profile/token routes, and `sample-access` request creation
have no `domain:action` verb in the §4 catalog (which is explicitly
non-exhaustive). These need catalog entries (e.g. read-plane verbs and a
`submission:prepare`-class verb) during M2 reconciliation — deliberately
not invented here per the map rules.
