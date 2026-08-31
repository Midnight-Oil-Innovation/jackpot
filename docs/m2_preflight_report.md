> **Status:** Reference — generated M2 pre-cutover checklist. Regenerate with
> `uv run python scripts/m2_preflight_report.py`; do not edit by hand
> except to tick checkboxes / annotate decisions inline in review.

# M2 Pre-Cutover Report

Map totals: 124 endpoints — 28 already wired to `require_capability`, 56 auth-only (ROUTE_LOCAL), 29 catalog gaps, 11 PUBLIC (3 pending intent verification).

## 1. Catalog gaps — proposed capabilities (maintainer review required)

Proposals follow the §4 `domain:action` convention; existing verbs
reused where one fits. Edit the proposal column in review; the M2
cutover session writes the agreed values into the map and the §4
catalog. The map file itself is deliberately untouched until then.

| ✓ | Method | Path | Scope | Proposed capability |
|---|--------|------|-------|---------------------|
| ☐ | GET | `/api/v1/byop/telemetry` | Lab | `pipeline:read` |
| ☐ | GET | `/api/v1/byop/pipelines` | Lab | `pipeline:read` |
| ☐ | GET | `/api/v1/byop/pipelines/{pipeline_id}` | Lab | `pipeline:read` |
| ☐ | POST | `/api/v1/dataharmonizer/validate` | Instance | `metadata:validate (new verb — stateless utility; or keep auth-only)` |
| ☐ | GET | `/api/v1/import_mappings/` | Lab | `import:read (new domain)` |
| ☐ | GET | `/api/v1/import_mappings/{mapping_id}` | Lab | `import:read (new domain)` |
| ☐ | POST | `/api/v1/import_mappings/` | Lab | `import:manage (new domain)` |
| ☐ | PATCH | `/api/v1/import_mappings/{mapping_id}` | Lab | `import:manage (new domain)` |
| ☐ | DELETE | `/api/v1/import_mappings/{mapping_id}` | Lab | `import:manage (new domain)` |
| ☐ | GET | `/api/v1/labs/` | Org | `lab:read (new verb)` |
| ☐ | GET | `/api/v1/labs/{lab_id}` | Lab | `lab:read (new verb)` |
| ☐ | GET | `/api/v1/organizations/{org_id}` | Org | `org:read (new verb)` |
| ☐ | GET | `/api/v1/pipelines/` | Instance | `pipeline:read` |
| ☐ | POST | `/api/v1/profiles/` | Instance | `profile:manage (new domain — execution profiles)` |
| ☐ | GET | `/api/v1/profiles/me` | Instance | `user:read_self (new verb — self-scope)` |
| ☐ | POST | `/api/v1/sample-access/requests` | Sample | `access:request (new verb, pairs with access:approve_request)` |
| ☐ | GET | `/api/v1/sequencing-labs/` | Instance | `sequencing_lab:read (new domain)` |
| ☐ | GET | `/api/v1/sequencing-labs/{seq_lab_id}` | Instance | `sequencing_lab:read (new domain)` |
| ☐ | POST | `/api/v1/submissions/` | Lab | `submission:prepare (new verb)` |
| ☐ | PATCH | `/api/v1/submissions/{submission_id}` | Lab | `submission:prepare (new verb)` |
| ☐ | DELETE | `/api/v1/submissions/{submission_id}` | Lab | `submission:prepare (new verb)` |
| ☐ | POST | `/api/v1/submissions/{submission_id}/samples` | Lab | `submission:prepare (new verb)` |
| ☐ | DELETE | `/api/v1/submissions/{submission_id}/samples` | Lab | `submission:prepare (new verb)` |
| ☐ | POST | `/api/v1/submissions/{submission_id}/validate` | Lab | `submission:prepare (new verb)` |
| ☐ | POST | `/api/v1/submissions/{submission_id}/generate` | Lab | `submission:prepare (new verb)` |
| ☐ | GET | `/api/v1/tokens/` | Instance | `token:manage (new domain — self-scope resource)` |
| ☐ | POST | `/api/v1/tokens/` | Instance | `token:manage (new domain — self-scope resource)` |
| ☐ | DELETE | `/api/v1/tokens/{token_id}` | Instance | `token:manage (new domain — self-scope resource)` |
| ☐ | GET | `/api/v1/users/me` | Instance | `user:read_self (new verb — self-scope)` |

## 2. PUBLIC rows pending intent verification

- ☐ **POST `/api/v1/auth/dev-login`** — PUBLIC (verify intent — must be ENV=local only)
- ☐ **POST `/api/v1/pipelines/events`** — PUBLIC (verify intent — weblog receiver is best-effort by design, Rule 60; SERVICE-principal capability at M2)
- ☐ **POST `/api/v1/pipelines/{run_id}/results/{result_type}`** — PUBLIC (verify intent — pipeline-token path; SERVICE-principal capability at M2)

## 3. ROUTE_LOCAL rows (auth-only today)

56 routes carry `get_current_user` plus in-route ad-hoc
checks (ownership, visibility, director-or-admin). No single legacy
decision function exists per route, so they are NOT machine-comparable
pre-cutover; the preflight equivalence matrix covers only the wired
`require_capability` rows and the sample read/see/list ladder. Each
ROUTE_LOCAL row must be verified by route-level tests in the M2 PR
itself when its guard is rewritten.

## 4. Known divergence classes (legacy vs. new model)

Mirrored from `tests/authz/preflight.py::EXPECTED_DIVERGENCES`; the
preflight matrix asserts each class fires and nothing else diverges.
Lift this section into the M2 cutover PR body.

### `admin-bypass-vs-scoped-grants`

Legacy platform-admin bypass (guards.py:108) allows every capability everywhere; reseeded instance_administrator grants are scoped to instance://self, and _scope_contains is pure URI-prefix, so instance://self does NOT contain lab://N. Every lab-scoped admin cell, and every instance cell for a capability outside the §8.2 admin preset, denies under the new model. RESOLVED by ADR 0015 (docs/adr/0015-single-rooted-scope-uri.md): every scope becomes a path under instance://self, so the admin grant prefixes lab scopes structurally. This class disappears once M2 lands the canonical serialization; until then the divergence stands and is asserted.

### `surveillance-cap-new-only`

Data analysts gain an explicit instance-scoped sample:read_surveillance grant from the surveillance_officer preset; the legacy guard has no analyst branch at all (analyst rights lived only in the visibility ladder). New model intentionally allows.

### `director-passes-all-lab-caps`

Legacy directorship is all-capabilities-at-lab (guards.py:123 trusts is_lab_director for ANY non-member-level capability); the lab_lead preset enumerates 12 capabilities, so out-of-preset verbs (org:manage, user:manage, whitelist:manage, federation:*, pipeline:promote, sample:read_surveillance at lab scope) deny under the new model. Intentional §8.2 narrowing — document per-route in the cutover PR.

### `member-rw-write-caps-new-only`

Legacy require_capability demands directorship for every non-member-level capability, so collaborators could not create/update via a guarded route; the lab_member_rw preset intentionally grants sample:create/update/deletion:request (and pipeline:run for Bioinformatics User). New model intentionally allows — §8.2/§8.5 design.

### `flag-group-mismatch`

lab_membership rows where is_lab_director=TRUE but the permission group says Collaborator: legacy trusts the flag (all caps pass), reseed trusts the group name (member-RW grants only). Data-quality reconciliation required before cutover: flag and group must agree or the cutover changes these users' effective access.

### `project-membership-no-grants`

Legacy member-level checks accept project membership via the project→lab join (guards.py:115-122); reseed reads only lab_membership, so project-only users lose guarded read access. Cutover must either reseed project memberships or accept the narrowing explicitly.

### `unmapped-group-skipped`

Memberships with a permission-group name absent from MEMBERSHIP_PRESETS ('Data Analyst' as a lab membership) are skipped with a warning by reseed — those users lose all guarded access at cutover. The reseed run's warnings must be triaged to zero before M2.

## 5. Additional preflight findings

- **Unique-index ordering is load-bearing**: the live chain's
  `authz_capability_grants` has no `(principal_id, capability,
  scope_ref)` unique index; `reseed()`'s `ON CONFLICT DO NOTHING`
  only dedupes once the staged migration creates it (it does, before
  calling reseed). Pinned by
  `test_reseed_duplicates_without_index`.
- **Federation PEER_INSTANCE principals** have no reseed source —
  peer-key routes keep their own auth path; out of the matrix.
- **`require_capability` call sites that never pass `lab_id`** are
  admin-only in practice regardless of the declared Scope column;
  the cutover rewrite must take the map's Scope as authoritative.
