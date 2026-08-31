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
| GET | `/api/v1/byop/telemetry` | `pipeline:read` | Lab | auth-only today; BYOP registry read |
| POST | `/api/v1/byop/pipelines` | `pipeline:register_custom` | Lab | auth-only today |
| GET | `/api/v1/byop/pipelines` | `pipeline:read` | Lab | auth-only today; registry read |
| GET | `/api/v1/byop/pipelines/{pipeline_id}` | `pipeline:read` | Lab | auth-only today; registry read |
| PATCH | `/api/v1/byop/pipelines/{pipeline_id}` | `pipeline:register_custom` | Lab | auth-only today |
| PUT | `/api/v1/byop/pipelines/{pipeline_id}` | `pipeline:register_custom` | Lab | auth-only today |
| DELETE | `/api/v1/byop/pipelines/{pipeline_id}` | `pipeline:register_custom` | Lab | auth-only today |
| POST | `/api/v1/byop/pipelines/{pipeline_id}/revalidate` | `pipeline:register_custom` | Lab | auth-only today |
| POST | `/api/v1/byop/pipelines/{pipeline_id}/deactivate` | `pipeline:register_custom` | Lab | auth-only today |
| POST | `/api/v1/byop/pipelines/{pipeline_id}/archive` | `pipeline:register_custom` | Lab | auth-only today |
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
| GET | `/api/v1/files/broken` | `sample:read` | Lab | auth-only today |
| GET | `/api/v1/files/` | `sample:read` | Lab | auth-only today |
| GET | `/api/v1/files/{file_id}` | `sample:read_detail` | Sample | auth-only today |
| POST | `/api/v1/files/{file_id}/promote` | `sample:update` | Sample | in-route Lab-Director-or-admin check today |
| GET | `/api/v1/files/jobs/{job_id}` | `sample:read` | Lab | auth-only today |
| POST | `/api/v1/files/{file_id}/verify` | `sample:update` | Sample | auth-only today |
| POST | `/api/v1/gisaid/export/{lab_id}` | `sample:read_detail` | Lab | `require_capability("sample:read_detail")` — export reads lab samples |
| GET | `/api/v1/import_mappings/` | `import:read` | Lab | auth-only today; mapping-config read |
| GET | `/api/v1/import_mappings/{mapping_id}` | `import:read` | Lab | auth-only today |
| POST | `/api/v1/import_mappings/` | `import:manage` | Lab | auth-only today; mapping-config write |
| PATCH | `/api/v1/import_mappings/{mapping_id}` | `import:manage` | Lab | auth-only today |
| DELETE | `/api/v1/import_mappings/{mapping_id}` | `import:manage` | Lab | auth-only today; soft-delete (is_active=false) |
| POST | `/api/v1/imports/sessions/` | `sample:create` | Lab | auth-only today; import staging |
| GET | `/api/v1/imports/sessions/` | `sample:read` | Lab | auth-only today |
| GET | `/api/v1/imports/sessions/{session_id}` | `sample:read` | Lab | auth-only today |
| PATCH | `/api/v1/imports/sessions/{session_id}` | `sample:create` | Lab | auth-only today |
| POST | `/api/v1/imports/sessions/{session_id}/import` | `sample:create` | Lab | auth-only today |
| DELETE | `/api/v1/imports/sessions/{session_id}` | `sample:create` | Lab | auth-only today; deletes staging session, not samples |
| POST | `/api/v1/ingest/upload` | `sample:create` | Lab | auth-only today |
| POST | `/api/v1/ingest/csv` | `sample:create` | Lab | auth-only today |
| POST | `/api/v1/ingest/register` | `sample:create` | Lab | auth-only today (BYOP no-copy registration, Rule 57) |
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
| GET | `/api/v1/pipelines/` | `pipeline:read` | Instance | auth-only today; pipeline zoo read |
| POST | `/api/v1/pipelines/launch` | `pipeline:run` | Project | auth-only today; in-route sample-access checks |
| POST | `/api/v1/pipelines/events` | `pipeline:write_results` | Instance | SERVICE-authenticated (NOT public): per-run `X-Pipeline-Token`, `hmac.compare_digest`, 401 on mismatch (`routers/pipelines.py:903`). Rule 60's never-raises applies to weblog delivery, not auth. M2 adds the SERVICE-principal `permit()` call |
| GET | `/api/v1/pipelines/{run_id}` | `pipeline:run` | Project | auth-only today; run-status read |
| GET | `/api/v1/pipelines/{run_id}/tasks` | `pipeline:run` | Project | auth-only today |
| GET | `/api/v1/pipelines/{run_id}/events` | `pipeline:run` | Project | auth-only today |
| POST | `/api/v1/pipelines/{run_id}/resume` | `pipeline:run` | Project | auth-only today |
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
| POST | `/api/v1/sample-access/requests` | `access:request` | Sample | auth-only today; pairs with `access:approve_request` |
| GET | `/api/v1/sample-access/requests` | `sample:read` | Lab | auth-only today |
| POST | `/api/v1/sample-access/requests/{request_id}/approve` | `access:approve_request` | Sample | in-route Lab-Director-or-admin check today |
| POST | `/api/v1/sample-access/requests/{request_id}/deny` | `access:approve_request` | Sample | in-route Lab-Director-or-admin check today |
| GET | `/api/v1/samples/` | `sample:read` | Lab | auth-only today; `visibility_sql_clause` list filter |
| GET | `/api/v1/samples/{sample_id}` | `sample:read_detail` | Sample | auth-only today; `can_access_sample` in route |
| PATCH | `/api/v1/samples/{sample_id}` | `sample:update` | Sample | auth-only today |
| DELETE | `/api/v1/samples/{sample_id}` | `sample:archive` | Sample | in-route Lab-Director-or-admin check today; verify archive vs `sample:soft_delete` semantics at M2 |
| GET | `/api/v1/samples/{sample_id}/files` | `sample:read_detail` | Sample | auth-only today |
| GET | `/api/v1/samples/{sample_id}/download` | `sample:read_detail` | Sample | auth-only today |
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
| GET | `/api/v1/wastewater/sites` | `sample:read_surveillance` | Org | auth-only today |
| GET | `/api/v1/wastewater/lineage-abundance` | `sample:read_surveillance` | Org | auth-only today |

Deletion-approval note (§10.3 example): no deletion-approval route exists
yet (the B-CARE-3 lifecycle routes land with P0c/M3). When it lands it
takes `deletion:approve` at Sample scope and inherits the §6.2-1b
`deletion.separation_of_duties` DENY (approver ≠ requester unless the
audited platform-admin self-approve flag is set).

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
