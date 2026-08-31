> **Status:** Reference — generated M2 pre-cutover checklist. Regenerate with
> `uv run python scripts/m2_preflight_report.py`; do not edit by hand
> except to tick checkboxes / annotate decisions inline in review.

# M2 Pre-Cutover Report

Map totals: 124 endpoints — 28 already wired to `require_capability`, 78 carrying a target capability but not yet guarded (ROUTE_LOCAL), 7 AUTH-ONLY BY DESIGN (permanently ungated — authentication is the whole decision), 0 catalog gaps, 11 PUBLIC (3 pending intent verification).

## 1. Catalog gaps

None. Every gap the ACCESS-GUARD-MAP pass found was resolved in
review and written into `docs/endpoint_capability_map.md`. Most
took a capability, adding `pipeline:read`, `lab:read`,
`org:read`, `import:read`, `import:manage`,
`submission:prepare`, `access:request`, and `token:manage` to
the §4 catalog. The remaining 7 were marked
AUTH-ONLY BY DESIGN — self-scope routes, the stateless
validation utility, and the sequencing-lab registry, where
authentication is the whole decision (§4.7). Those stay ungated
after M2 and are covered by route-level tests rather than the
capability matrix. The two personal-token routes carry both a
capability and the marker: the self path is ungated, and
`token:manage` gates only reaching another principal's tokens,
so they remain ROUTE_LOCAL work.

## 2. PUBLIC rows pending intent verification

- ☐ **POST `/api/v1/auth/dev-login`** — PUBLIC (verify intent — must be ENV=local only)
- ☐ **POST `/api/v1/pipelines/events`** — PUBLIC (verify intent — weblog receiver is best-effort by design, Rule 60; SERVICE-principal capability at M2)
- ☐ **POST `/api/v1/pipelines/{run_id}/results/{result_type}`** — PUBLIC (verify intent — pipeline-token path; SERVICE-principal capability at M2)

## 3. ROUTE_LOCAL rows (auth-only today)

78 routes carry `get_current_user` plus in-route ad-hoc
checks and a target capability the map names but no guard enforces yet
(a further 7 are AUTH-ONLY BY DESIGN and stay that way).
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

lab_membership rows where is_lab_director=TRUE but the permission group says Collaborator: legacy trusts the flag (all caps pass), reseed trusts the group name (member-RW grants only), so these users lose director-level access at cutover. Detected at migration time by reseed's pre-flight guard, not reconciled ahead of it: no deployment holds real membership rows yet, so a pre-M2 sweep would pass vacuously. The guard aborts with counts on any operator DB where the flag and the group disagree.

### `project-membership-no-grants`

Legacy member-level checks accept project membership via the project→lab join (guards.py:115-122); reseed reads only lab_membership, so project-only users lose guarded read access. Cutover either reseeds project memberships or accepts the narrowing explicitly; reseed's pre-flight guard reports the count at migration time so the choice is made against real numbers rather than assumed to be zero.

### `unmapped-group-skipped`

Memberships with a permission-group name absent from MEMBERSHIP_PRESETS ('Data Analyst' as a lab membership) are skipped with a warning by reseed — those users lose all guarded access at cutover. Reseed's pre-flight guard counts them before inserting anything and aborts unless the operator has explicitly accepted the loss; triage happens at migration time on the DB that actually has the rows, not ahead of M2 on one that does not.

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
- **Data-quality divergences are guarded at migration time, not
  reconciled ahead of M2**: `flag-group-mismatch`,
  `unmapped-group-skipped`, and `project-membership-no-grants` all
  depend on membership rows no deployment holds yet (`instances/`
  contains only `ci`; the baseline migration seeds one admin and one
  Lab Director). A pre-M2 sweep would pass vacuously. M2 must give
  `reseed()` a pre-flight guard that counts all three conditions
  before inserting, aborts with the counts, and takes an explicit
  operator override to proceed — so the check runs on whichever DB
  actually has the rows, including operators we never meet.
