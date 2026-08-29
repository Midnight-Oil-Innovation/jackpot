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
`—` in the Capability column means the §4 catalog has no fitting verb
yet (catalog gap — §4 is explicitly non-exhaustive); flagged for the
M2 catalog reconciliation rather than inventing a verb here.

| Method | Path | Capability | Scope | Conditions / Notes |
|--------|------|------------|-------|--------------------|
| POST | `/api/v1/auth/google/login` | — | Instance | PUBLIC (intentional — OAuth login entry) |
| POST | `/api/v1/auth/refresh` | — | Instance | PUBLIC (intentional — token refresh via cookie) |
| POST | `/api/v1/auth/logout` | — | Instance | PUBLIC (intentional — clears cookies) |
| POST | `/api/v1/auth/dev-login` | — | Instance | PUBLIC (verify intent — must be ENV=local only) |
| GET | `/api/v1/byop/telemetry` | — | Lab | auth-only today; BYOP registry read (catalog gap) |
| POST | `/api/v1/byop/pipelines` | `pipeline:register_custom` | Lab | auth-only today |
| GET | `/api/v1/byop/pipelines` | — | Lab | auth-only today; registry read (catalog gap) |
| GET | `/api/v1/byop/pipelines/{pipeline_id}` | — | Lab | auth-only today; registry read (catalog gap) |
| PATCH | `/api/v1/byop/pipelines/{pipeline_id}` | `pipeline:register_custom` | Lab | auth-only today |
| PUT | `/api/v1/byop/pipelines/{pipeline_id}` | `pipeline:register_custom` | Lab | auth-only today |
| DELETE | `/api/v1/byop/pipelines/{pipeline_id}` | `pipeline:register_custom` | Lab | auth-only today |
| POST | `/api/v1/byop/pipelines/{pipeline_id}/revalidate` | `pipeline:register_custom` | Lab | auth-only today |
| POST | `/api/v1/byop/pipelines/{pipeline_id}/deactivate` | `pipeline:register_custom` | Lab | auth-only today |
| POST | `/api/v1/byop/pipelines/{pipeline_id}/archive` | `pipeline:register_custom` | Lab | auth-only today |
| GET | `/api/v1/dataharmonizer/templates/{source_type}/{tier}` | — | Instance | PUBLIC (intentional — templates are public, Critical Rule 42) |
| POST | `/api/v1/dataharmonizer/validate` | — | Instance | auth-only today; stateless validation utility, no resource |
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
| GET | `/api/v1/import_mappings/` | — | Lab | auth-only today; mapping-config read (catalog gap) |
| GET | `/api/v1/import_mappings/{mapping_id}` | — | Lab | auth-only today (catalog gap) |
| POST | `/api/v1/import_mappings/` | — | Lab | auth-only today; mapping-config write (catalog gap) |
| PATCH | `/api/v1/import_mappings/{mapping_id}` | — | Lab | auth-only today (catalog gap) |
| DELETE | `/api/v1/import_mappings/{mapping_id}` | — | Lab | auth-only today (catalog gap) |
| POST | `/api/v1/imports/sessions/` | `sample:create` | Lab | auth-only today; import staging |
| GET | `/api/v1/imports/sessions/` | `sample:read` | Lab | auth-only today |
| GET | `/api/v1/imports/sessions/{session_id}` | `sample:read` | Lab | auth-only today |
| PATCH | `/api/v1/imports/sessions/{session_id}` | `sample:create` | Lab | auth-only today |
| POST | `/api/v1/imports/sessions/{session_id}/import` | `sample:create` | Lab | auth-only today |
| DELETE | `/api/v1/imports/sessions/{session_id}` | `sample:create` | Lab | auth-only today; deletes staging session, not samples |
| POST | `/api/v1/ingest/upload` | `sample:create` | Lab | auth-only today |
| POST | `/api/v1/ingest/csv` | `sample:create` | Lab | auth-only today |
| POST | `/api/v1/ingest/register` | `sample:create` | Lab | auth-only today (BYOP no-copy registration, Rule 57) |
| POST | `/api/v1/ingest/globus` | `sample:create` | Instance | `require_capability("sample:create")` — admin-triggered Globus sweep |
| POST | `/api/v1/labs/` | `org:manage` | Instance | `require_capability("org:manage")` |
| GET | `/api/v1/labs/` | — | Org | auth-only today; lab directory read (catalog gap) |
| GET | `/api/v1/labs/{lab_id}` | — | Lab | auth-only today (catalog gap) |
| PATCH | `/api/v1/labs/{lab_id}` | `org:manage` | Lab | `require_capability("org:manage")` at lab scope |
| DELETE | `/api/v1/labs/{lab_id}` | `org:manage` | Instance | `require_capability("org:manage")` |
| GET | `/api/v1/labs/{lab_id}/members` | `user:manage` | Lab | `require_capability("user:manage")` |
| POST | `/api/v1/labs/{lab_id}/members` | `user:manage` | Lab | `require_capability("user:manage")` |
| PATCH | `/api/v1/labs/{lab_id}/members/{user_id}` | `user:manage` | Lab | `require_capability("user:manage")` |
| DELETE | `/api/v1/labs/{lab_id}/members/{user_id}` | `user:manage` | Lab | `require_capability("user:manage")` |
| POST | `/api/v1/organizations/` | `org:manage` | Instance | `require_capability("org:manage")` |
| GET | `/api/v1/organizations/` | `org:manage` | Instance | `require_capability("org:manage")` |
| GET | `/api/v1/organizations/{org_id}` | — | Org | auth-only today (catalog gap) |
| PATCH | `/api/v1/organizations/{org_id}` | `org:manage` | Instance | `require_capability("org:manage")` |
| DELETE | `/api/v1/organizations/{org_id}` | `org:manage` | Instance | `require_capability("org:manage")` |
| GET | `/api/v1/pipelines/` | — | Instance | auth-only today; pipeline zoo read (catalog gap) |
| POST | `/api/v1/pipelines/launch` | `pipeline:run` | Project | auth-only today; in-route sample-access checks |
| POST | `/api/v1/pipelines/events` | `pipeline:write_results` | Instance | PUBLIC (verify intent — weblog receiver is best-effort by design, Rule 60; SERVICE-principal capability at M2) |
| GET | `/api/v1/pipelines/{run_id}` | `pipeline:run` | Project | auth-only today; run-status read |
| GET | `/api/v1/pipelines/{run_id}/tasks` | `pipeline:run` | Project | auth-only today |
| GET | `/api/v1/pipelines/{run_id}/events` | `pipeline:run` | Project | auth-only today |
| POST | `/api/v1/pipelines/{run_id}/resume` | `pipeline:run` | Project | auth-only today |
| POST | `/api/v1/pipelines/custom` | `pipeline:register_custom` | Lab | `require_capability("pipeline:register_custom")` |
| POST | `/api/v1/pipelines/{catalog_id}/promote` | `pipeline:promote` | Lab or Instance | `require_capability("pipeline:promote")` — lab scope for lab-tier target, instance scope for global tier |
| POST | `/api/v1/pipelines/{run_id}/results/{result_type}` | `pipeline:write_results` | Project | PUBLIC (verify intent — pipeline-token path; SERVICE-principal capability at M2) |
| POST | `/api/v1/profiles/` | — | Instance | auth-only today; self-scoped profile create (catalog gap) |
| GET | `/api/v1/profiles/me` | — | Instance | auth-only today; self-scoped |
| GET | `/api/v1/profiles/{user_id}` | `user:manage` | Org | auth-only today; self OR user:manage at M2 |
| PUT | `/api/v1/profiles/{user_id}` | `user:manage` | Org | auth-only today; self OR user:manage at M2 |
| POST | `/api/v1/projects/` | `org:manage` | Lab | `require_capability("org:manage")` at lab scope (§4.5: org:manage covers projects) |
| GET | `/api/v1/projects/` | `sample:read` | Lab | auth-only today; membership-filtered list |
| GET | `/api/v1/projects/{project_id}` | `sample:read` | Project | auth-only today |
| PATCH | `/api/v1/projects/{project_id}` | `org:manage` | Lab | `require_capability("org:manage")` at lab scope |
| POST | `/api/v1/sample-access/requests` | — | Sample | auth-only today; request creation has no §4 verb (catalog gap — only approve/revoke exist) |
| GET | `/api/v1/sample-access/requests` | `sample:read` | Lab | auth-only today |
| POST | `/api/v1/sample-access/requests/{request_id}/approve` | `access:approve_request` | Sample | in-route Lab-Director-or-admin check today |
| POST | `/api/v1/sample-access/requests/{request_id}/deny` | `access:approve_request` | Sample | in-route Lab-Director-or-admin check today |
| GET | `/api/v1/samples/` | `sample:read` | Lab | auth-only today; `visibility_sql_clause` list filter |
| GET | `/api/v1/samples/{sample_id}` | `sample:read_detail` | Sample | auth-only today; `can_access_sample` in route |
| PATCH | `/api/v1/samples/{sample_id}` | `sample:update` | Sample | auth-only today |
| DELETE | `/api/v1/samples/{sample_id}` | `sample:archive` | Sample | in-route Lab-Director-or-admin check today; verify archive vs `sample:soft_delete` semantics at M2 |
| GET | `/api/v1/samples/{sample_id}/files` | `sample:read_detail` | Sample | auth-only today |
| GET | `/api/v1/samples/{sample_id}/download` | `sample:read_detail` | Sample | auth-only today |
| GET | `/api/v1/sequencing-labs/` | — | Instance | auth-only today; registry read (catalog gap) |
| POST | `/api/v1/sequencing-labs/` | `org:manage` | Instance | `require_capability("org:manage")` |
| GET | `/api/v1/sequencing-labs/{seq_lab_id}` | — | Instance | auth-only today (catalog gap) |
| PATCH | `/api/v1/sequencing-labs/{seq_lab_id}` | `org:manage` | Instance | `require_capability("org:manage")` |
| POST | `/api/v1/sequencing-labs/{seq_lab_id}/assign/{lab_id}` | `org:manage` | Instance | `require_capability("org:manage")` |
| DELETE | `/api/v1/sequencing-labs/{seq_lab_id}/assign/{lab_id}` | `org:manage` | Instance | `require_capability("org:manage")` |
| GET | `/api/v1/settings/public` | — | Instance | PUBLIC (intentional — public instance settings) |
| POST | `/api/v1/submissions/` | — | Lab | auth-only today; submission-package create has no §4 verb (catalog gap) |
| GET | `/api/v1/submissions/` | `sample:read` | Lab | auth-only today |
| GET | `/api/v1/submissions/{submission_id}` | `sample:read` | Lab | auth-only today |
| PATCH | `/api/v1/submissions/{submission_id}` | — | Lab | auth-only today (catalog gap) |
| DELETE | `/api/v1/submissions/{submission_id}` | — | Lab | auth-only today (catalog gap) |
| POST | `/api/v1/submissions/{submission_id}/samples` | — | Lab | auth-only today (catalog gap) |
| DELETE | `/api/v1/submissions/{submission_id}/samples` | — | Lab | auth-only today (catalog gap) |
| POST | `/api/v1/submissions/{submission_id}/validate` | — | Lab | auth-only today (catalog gap) |
| POST | `/api/v1/submissions/{submission_id}/generate` | — | Lab | auth-only today (catalog gap) |
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
| GET | `/api/v1/tokens/` | — | Instance | auth-only today; self-scoped API-token list (catalog gap) |
| POST | `/api/v1/tokens/` | — | Instance | auth-only today; self-scoped token mint (catalog gap) |
| DELETE | `/api/v1/tokens/{token_id}` | — | Instance | auth-only today; self-scoped (catalog gap) |
| GET | `/api/v1/users/me` | — | Instance | auth-only today; self-scoped |
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

Routes with no authentication at all, flagged `PUBLIC (verify intent)`
unless intentionally public:

- `POST /api/v1/auth/dev-login` — PUBLIC (verify intent): must be gated to `ENV=local`; confirm it 404s/403s in production.
- `POST /api/v1/pipelines/events` — PUBLIC (verify intent): Nextflow weblog receiver; deliberately never raises (Rule 60), but should authenticate the pipeline token as a SERVICE principal holding `pipeline:write_results` at M2.
- `POST /api/v1/pipelines/{run_id}/results/{result_type}` — PUBLIC (verify intent): result registration path; same SERVICE-principal treatment as the weblog receiver.
- `GET /api/v1/settings/public`, `GET /api/v1/templates/*`, `GET /api/v1/dataharmonizer/templates/*`, `POST /api/v1/auth/{google/login,refresh,logout}` — intentionally public (login flow, public settings, Rule 42 public templates).
- Stub routers returning `{"status": "not implemented"}` (no auth, no data): `archive_requests`, `billing`, `dataset_access`, `datasets`, `ncbi_submissions`, `notifications`, `saved_searches`, `GET /api/v1/ingest/`. Guard when implemented; excluded from the table above.

Catalog gaps (`—` capability, authenticated routes): BYOP/pipeline/lab/org
registry reads, import-mapping CRUD, submission-package assembly,
self-scoped profile/token routes, and `sample-access` request creation
have no `domain:action` verb in the §4 catalog (which is explicitly
non-exhaustive). These need catalog entries (e.g. read-plane verbs and a
`submission:prepare`-class verb) during M2 reconciliation — deliberately
not invented here per the map rules.
