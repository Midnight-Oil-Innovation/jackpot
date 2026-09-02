> **Status:** History — append-only learnings log. Point-in-time record.

# JACKPOT — Implementation Learnings

Auto-maintained by Claude Code. Updated after each router session.
Each entry records what was built, why key decisions were made, and what to watch out for.

> **Forward-looking note (May 2026 cluster-doc-merge refresh — 2026-05-16):** This document is a session-by-session implementation-learnings log. Each entry records what was true at the point in time it was written — the routers as they existed, the architectural framings as they stood, the CLI flags as they accepted them. The entries below do NOT necessarily reflect current canonical architecture. Two notable evolutions show up across entries:
>
> 1. **The install-scenario count** as referenced in the P0e CLI entry (Session P0e, 2026-05-02, line ~2473) and the `COMPOSE_PROFILES=...` profile mapping (same entry, line ~2516) describes current code state — the `jackpot init configure --scenario T --instance-name tribal` invocation works today, and the docker-compose.yml accepts the `tribal` / `multi-tenant` / `laptop` / `single-org` / `ci` profile names. The May 2026 Cluster A doc-merge work **consolidated the architectural scenario story to 4 install scenarios** (A self-hosted commodity / B HPC / C single-org cloud / D CI test), with federation, multi-tenancy, and Indigenous data sovereignty as runtime configurations layered on top of any scenario rather than as separate install scenarios. See `docs/architecture.md` v6.0 §3 for the current architectural model. The code consolidation (CLI flags, docker-compose profile names, `schema/jackpot_scenarios/` registry) will land post-P0e as the implementation catches up to the canonical architecture; until then, this file describes operational reality (what works in code today).
>
> 2. **Scenario T (Tribal-sovereignty deployment)** as referenced in the P0e CLI entry (e.g. "Scenario T defaults are baked, not opt-in" at line ~2458) was reframed as **sovereignty-as-runtime-policy** in the Cluster A merge. The four sovereignty-aware defaults (deletion-on-request, no auto-publish, federation off-by-default, CARE Principles compliance) are now runtime configurations enable-able on any scenario via `jackpot policy enable sovereignty`, not the defining characteristics of a separate deployment scenario. See `docs/architecture.md` §22 for the current framing. The CLI code that bakes these defaults at `jackpot init` time continues to function as documented in this entry; the post-P0e consolidation will move the same defaults under the sovereignty-runtime-policy umbrella.
>
> The entries below preserve the framings as they stood at the time. They document *when* implementation decisions were made and *what was learned*, which is the historical record this log exists to preserve. Companion canonical reference docs from the May 2026 cluster-merge work: `docs/architecture.md`, `docs/immune_platform.md`, `docs/detection_landscape.md`, `docs/platform_landscape.md`, `docs/strategic_vision.md`, `docs/governance_alignment.md`, `docs/federation.md` + `docs/federation_operations.md`, `docs/learning_strategic_vision.md` + `docs/learning_curriculum_design.md`, `docs/wastewater.md` + `docs/wastewater_software_landscape.md`, `docs/deploy/gcp.md`. See `CLAUDE.md`'s "Forward-looking note" and `docs/domain_reference.md` for the full source-of-truth map.

---

## Session A: organizations router — 2026-04-16

**What was built:** Full CRUD for `/api/v1/organizations/` (POST, GET list, GET {id}, PATCH, DELETE soft-delete) plus 13-test integration suite. New baseline: 329 tests passing, 79.95% coverage (+13 tests, +3.3%).

**Key decisions:**

- All endpoints use `Depends(get_db_dep)` and forward the same `db` session to `execute_write`, `execute_query`, and `log_audit` — this is the only way audit + business writes share a transaction per CLAUDE.md rule 41.
- Explicit 409 CONFLICT pre-check on `display_name` duplicate rather than catching the UNIQUE violation, so we can return our structured `error()` envelope cleanly instead of raising 500 and relying on a global handler.
- GET {id} allows the requester through if `is_platform_admin` OR `user.organization_id == org_id`. No lab-membership climb required — the spec just says "Platform Admin or org member" and users.organization_id is the direct membership link.
- Soft delete uses the same UPDATE_ORG audit action (with `metadata={"soft_delete": True}`) rather than inventing a new action constant — the AuditActions enum in CLAUDE.md has no DEACTIVATE_ORG, and the before/after state tells the same story.
- Serialisation helper `_serialise()` coerces `datetime` fields to ISO strings so `JSONResponse` can encode them — FastAPI's default encoder does this for response_model routes but we return raw `JSONResponse`.

**Watch out for:**

- **Pre-existing bug found and fixed:** `backend/audit.py` used `:before::jsonb` in its INSERT. SQLAlchemy's `text()` bind-param regex refuses to match `:name` when followed by `:`, so the JSONB casts were sent literally to Postgres and every audit write failed with a syntax error. Because the write happened inside the router's transaction, the error poisoned the transaction and silently rolled back the *business* write on commit — the API returned 201, but the org was never persisted. Switched to `CAST(:before AS JSONB)`. Apply the same pattern to any future `::type` cast with a bindparam.
- In local dev `get_current_user()` falls back to a synthetic Platform Admin dict when `MOCK_USER_EMAIL` doesn't resolve in the users table. To test the 403 path for a non-admin you must (a) INSERT the non-admin user, (b) `monkeypatch.setenv("MOCK_USER_EMAIL", ...)`, AND (c) `get_settings.cache_clear()` — otherwise the lru-cached settings keep the old email.
- Tests that create an org and assign a user to it must unwind `users.organization_id` before DELETE-ing the org, or the FK constraint fires during cleanup. `_cleanup_org()` now does both steps.
- Removed `backend/routers/organizations.py` from the coverage omit list in `pyproject.toml` — the stub-exclusion guidance only applies while a router is a stub.

**ASCII diagram:**

```
client ─► POST /api/v1/organizations/
           │
           ▼
  get_current_user(request)       ── own short-lived DB session (guards.py)
           │
           ▼
  require_platform_admin(user)    ── 403 if not admin
           │
           ▼
  ┌─ single injected db session (get_db_dep) ───────────────┐
  │   execute_query SELECT id FROM organizations …         │
  │   execute_write INSERT … RETURNING *                    │
  │   log_audit(CREATE_ORG, …, db_conn=db)                  │
  │       └─ execute_write INSERT audit_log                 │
  │          (CAST(:before AS JSONB), …)                    │
  │   on exit → session.commit() atomically persists both   │
  └─────────────────────────────────────────────────────────┘
           │
           ▼
  success(data=org_dict, status_code=201)
```

---

## Session B: labs + lab_membership router — 2026-04-16

**What was built:** Nine endpoints for `/api/v1/labs/` — lab CRUD (POST, GET list, GET {id}, PATCH, DELETE soft-delete) plus member lifecycle (GET/POST members, PATCH/DELETE members/{user_id}) — with 17-test integration suite. New baseline: 346 tests passing, 81.78% coverage (+17 tests, +1.83%). Router coverage: 93% (166 stmts, 12 missed — defensive branches).

**Key decisions:**

- GET list branches on `is_platform_admin`: admins see every lab paginated; others see only labs where `lab_membership.user_id = me`, via an INNER JOIN in the base query before `paginate()` wraps it. Kept the search-by-display_name filter uniform across both branches.
- POST /members validates three ways before insert: user must exist (404), permission_group must exist (404), and `(lab_id, user_id)` must not already be a member (409). The 409 pre-check beats catching the UNIQUE violation because it lets us return a structured envelope instead of a SQL error.
- All five state-changing endpoints log the correct AuditAction from the CLAUDE.md constants: `CREATE_LAB`, `UPDATE_LAB` (with `metadata={"soft_delete": True}` for DELETE), `ADD_LAB_MEMBER`, `CHANGE_MEMBER_ROLE`, `REMOVE_LAB_MEMBER`. No new constants invented.
- Ruff `SIM102` flagged nested `if not admin: if not member:` — collapsed to one `and` expression. `F841` flagged a discarded response from the "theirs lab" create in the list-test; dropped the assignment.

**Watch out for:**

- **FK `audit_log_user_id_fkey` persists through the rename migration.** The migration renames the column `user_id` → `actor_id` but the FK constraint keeps its original name. So deleting a test user that has any audit row (even one from a previous test) still raises `violates foreign key constraint "audit_log_user_id_fkey"`. `_cleanup_user()` must `UPDATE audit_log SET actor_id = NULL WHERE actor_id IN (SELECT id FROM users WHERE email = :e)` before DELETE. Learned the hard way on the director/reader tests.
- Three-step cleanup ordering for lab tests: (1) DELETE lab_membership rows pointing at the lab, (2) DELETE sequencing_labs rows with the same lab_id (FK from Critical Rule 21), (3) DELETE the lab. Skipping step 2 breaks tests that happen to run after any ingest-seeded data.
- `is_lab_director=True` plus `permission_group_id = 'Lab Director'` are independent columns — both must be set when adding a director. `require_lab_director` checks the boolean flag only, so a permission_group of Lab Director without the flag won't grant write access.
- Removed `backend/routers/labs.py` from `pyproject.toml` coverage omit — same rule as organizations.

**ASCII diagram:**

```
client ─► GET /api/v1/labs/
           │
           ▼
  get_current_user(request)
           │
     ┌─────┴─────┐
     │           │
  is_platform_  else (lab member only)
  admin?
     │           │
     ▼           ▼
  SELECT *    SELECT l.* FROM labs l
  FROM labs   JOIN lab_membership lm
              ON lm.lab_id = l.id
              WHERE lm.user_id = :me
     │           │
     └─────┬─────┘
           ▼
  paginate(query, page, per_page, sort_by, sort_dir)
  success_list(data, page, per_page, total)

client ─► POST /api/v1/labs/{id}/members
           │
           ▼
  require_lab_director(user, lab_id)  ── 403 if not director
           │
           ▼
  ┌─ single injected db session ─────────────────────────┐
  │  SELECT 1 FROM users WHERE id=:uid       → 404       │
  │  SELECT 1 FROM permission_groups         → 404       │
  │  SELECT 1 FROM lab_membership UNIQUE     → 409       │
  │  INSERT INTO lab_membership RETURNING *              │
  │  log_audit(ADD_LAB_MEMBER, db_conn=db)               │
  │  commit()                                            │
  └──────────────────────────────────────────────────────┘
           │
           ▼
  success(data=row, status_code=201)
```

---

## Session C: users router — 2026-04-16

**What was built:** Five endpoints for `/api/v1/users/` — `/me` (self + lab memberships), list (Platform Admin only), get by id (admin or self), PATCH (admin or self with field whitelist), DELETE soft-delete — plus 16-test integration suite. New baseline: 362 tests passing, 82.84% coverage (+16 tests, +1.06%). Router coverage: 98% (91 stmts, 2 missed).

**Key decisions:**

- Two editable-field sets on PATCH: `_SELF_EDITABLE = {"name"}` and `_ADMIN_EDITABLE = {"name", "is_platform_admin", "is_data_analyst", "is_active", "organization_id"}`. A non-admin touching any admin-only field returns 403 (not 422) — the request shape is valid, the actor is not. This is simpler and more grep-friendly than two separate Pydantic models.
- `/me` returns the user row plus a `lab_memberships` array (lab_id, lab_name, permission_group_id, permission_group_name, is_lab_director). Joined via `lab_membership → labs` + `permission_groups`. This is the one endpoint the frontend polls on every page load, so shoving memberships in saves a second round-trip.
- Added single new audit action `UPDATE_USER` — used for both PATCH and soft-delete (with `metadata={"soft_delete": True}`), same pattern as `UPDATE_ORG` / `UPDATE_LAB`. No `CREATE_USER` / `DELETE_USER` constants invented; user creation happens inside the OAuth flow, not via this router.
- `_SELF_EDITABLE`/`_ADMIN_EDITABLE` checks happen *before* the row fetch. This means an unauthorized PATCH returns 403 even when the target user does not exist — intentional, don't leak existence to non-admins.

**Watch out for:**

- `get_current_user()` in local dev falls back to a synthetic Platform Admin dict (id=1) when `MOCK_USER_EMAIL` does not resolve. Test fixtures that expect "non-admin" behavior must insert the user AND `monkeypatch.setenv("MOCK_USER_EMAIL", ...)` AND `get_settings.cache_clear()` — all three. Same trap as Sessions A/B.
- The `users` table has no `active` column — the soft-delete flag is `is_active`. Do not unify with orgs/labs (which use `active`).
- The `updated_at` column has no trigger, so every write statement must include `updated_at = NOW()` in its SET clause. Orgs/labs do not do this because they were written first and the column has a default; the users table should be patched with a trigger in a later migration, but for now explicit `updated_at` works.
- The `/me` `_get_lab_memberships` helper runs inside the same `db` session as the primary SELECT so both reads see a consistent snapshot — not strictly required (reads only) but keeps the session per-request pattern consistent.

**ASCII diagram:**

```
client ─► GET /api/v1/users/me
           │
           ▼
  get_current_user(request)          ── resolves MOCK_USER_EMAIL locally / JWT in GKE
           │
           ▼
  ┌─ injected db session (get_db_dep) ─────────────────┐
  │  SELECT * FROM users WHERE id = :me                 │
  │  SELECT lm.*, l.display_name, pg.name               │
  │    FROM lab_membership lm                           │
  │    JOIN labs l ON l.id = lm.lab_id                  │
  │    JOIN permission_groups pg                        │
  │      ON pg.id = lm.permission_group_id              │
  │    WHERE lm.user_id = :me                           │
  └─────────────────────────────────────────────────────┘
           │
           ▼
  { ...user, lab_memberships: [...] }

client ─► PATCH /api/v1/users/{id}  {is_platform_admin: true}
           │
     non-admin target=self             admin
           │                             │
           ▼                             ▼
  forbidden = {is_platform_admin}      allowed
  ── not in _SELF_EDITABLE                │
           │                             ▼
           ▼                  UPDATE users SET … RETURNING *
  403 ACCESS_DENIED           log_audit(UPDATE_USER, db_conn=db)
                              success(data=after)
```

---

## Session D: domain_whitelist router — 2026-04-16

**What was built:** Three endpoints for `/api/v1/domain-whitelist/` — GET list (paginated), POST add (normalise + dedup), DELETE remove (hard delete, not soft) — plus 9-test integration suite. New baseline: 371 tests passing, 83.36% coverage (+9 tests, +0.52%). Router coverage: 100% (51 stmts).

**Key decisions:**

- **Hard delete, not soft delete.** Orgs/labs/users all use soft delete because a deactivated row still has FK children (samples, memberships, audit log). Whitelist entries have no children — the domain is just a string that gates self-registration. Removing from the whitelist must take effect immediately, so a `DELETE` row is the right move. The `before` state is captured in the audit log to preserve history.
- **Normalise to lowercase at the API boundary.** Input `UPPER.example` is stored as `upper.example`. The UNIQUE constraint on `domain` is case-sensitive at the DB level, so without normalisation two case variants of the same domain could both be whitelisted. A case-insensitive pre-check before insert makes the 409 deterministic.
- Added two new audit actions — `ADD_WHITELIST_DOMAIN` and `REMOVE_WHITELIST_DOMAIN`. The spec section for governance (Rule 4) requires every state-changing endpoint to audit, and the domain list directly gates who can register, so the audit trail is non-optional.
- No PATCH endpoint — spec omits it. If admins want to fix a typo they remove the bad entry and add the new one; the two-step trail is clearer in audit review than a silent rename.

**Watch out for:**

- The seed data in `db/init.sql` includes `example-academic.edu` and `gmail.com` — the first list test asserts `example-academic.edu` is present, which works as long as the seed INSERT runs before the Alembic migrations in conftest. Seed INSERTs are at the bottom of `init.sql` and run as part of `conn.execute(text(sql))` before the Alembic step, so this is safe — but any future test that expects an empty whitelist would need to clean up seed entries first.
- `execute_write(...)` on a DELETE with no RETURNING still returns `[]`. The handler fetches the `before` row via `execute_query` first (for 404 and audit), which is the right pattern because Critical Rule 40 requires RETURNING only on INSERT/UPDATE.
- Removed `backend/routers/domain_whitelist.py` from `pyproject.toml` coverage omit — same pattern as every previous session.

**ASCII diagram:**

```
client ─► POST /api/v1/domain-whitelist/  {"domain": "UPPER.example"}
           │
           ▼
  require_platform_admin(user)       ── 403 if not admin
           │
           ▼
  normalised = payload.domain.strip().lower()   # "upper.example"
           │
           ▼
  ┌─ injected db session ──────────────────────────────────┐
  │  SELECT 1 FROM domain_whitelist WHERE domain=:d        │
  │     → if present → 409 CONFLICT                         │
  │  INSERT INTO domain_whitelist (domain, description)    │
  │     VALUES (:normalised, :desc) RETURNING *             │
  │  log_audit(ADD_WHITELIST_DOMAIN, db_conn=db)           │
  │  commit()                                              │
  └────────────────────────────────────────────────────────┘
           │
           ▼
  success(data=row, status_code=201)
```

---

## Session E: sequencing_labs router — 2026-04-16

**What was built:** Six endpoints for `/api/v1/sequencing-labs/` — list, POST create, GET by id, PATCH update, POST assign/{lab_id}, DELETE assign/{lab_id} — plus a new Alembic migration creating the `sequencing_lab_assignments` join table, plus a 13-test integration suite. New baseline: 384 tests passing, 84.20% coverage (+13 tests, +0.84%).

**Key decisions:**

- **Created a new Alembic migration (`919759af99a1`) for `sequencing_lab_assignments`.** Critical Rule 21 mandates the table but neither `db/init.sql` nor any existing migration had created it — this is a spec-mandated schema gap that Session E had to fill before endpoints could be written. The table enforces `UNIQUE(sequencing_lab_id, lab_id)` so 409 duplicates are caught at the DB level too, and cascades on delete of either parent row. The init.sql `sequencing_labs.lab_id` FK column is preserved (legacy 1:1 auto-link for the JACKPOT-lab-as-sequencing-lab case) — the join table is the additive, many-to-many channel.
- **List endpoint requires authentication but not admin.** Spec line: "any authenticated user" can see sequencing labs, because ingest forms need to populate a dropdown of valid `sequencing_lab` values. Only create/patch/assign/unassign require `require_platform_admin`.
- **Two-stage validation on assign:** pre-check both `sequencing_labs.id` and `labs.id` exist so we can return precise 404s, then pre-check assignment uniqueness for 409. Pure DB UNIQUE violation would force a 500 or a messy error-envelope wrap.
- **Four new audit actions** — `CREATE_SEQUENCING_LAB`, `UPDATE_SEQUENCING_LAB`, `ASSIGN_SEQUENCING_LAB`, `UNASSIGN_SEQUENCING_LAB`. The assignment/unassignment log entry sets `resource_type="sequencing_lab_assignment"` with `metadata={"sequencing_lab_id": ..., "lab_id": ...}` so a historical query by either parent id is possible via JSONB `metadata ->> 'lab_id'`.
- **PATCH uses `_UPDATABLE` whitelist** `{"name", "organization", "is_external", "is_active"}` — intentionally excludes `lab_id` (legacy auto-link column must not be edited through this endpoint) and `created_at`.

**Watch out for:**

- **The join table did not exist until this session.** Any prior code or test that references `sequencing_lab_assignments` against the stub DB would have failed until the migration was applied. `tests/conftest.py` runs `alembic upgrade head` after `db/init.sql`, so the table is available as soon as the migration file lands — no one-shot DB rebuild required.
- Seed contains `Example Sequencing Lab`, `Example Reference Lab`, and `Example Lab` (the last as a non-external auto-added entry). Tests assert the first two verbatim. If ingest code ever hardcodes a specific lab-name match, grep will surface the mismatch.
- `DELETE /assign/{lab_id}` 200s on first call and 404s on second — tests exercise both. There is no idempotent mode; callers must cope.
- The `valid_human_sample` test fixture lists `"sequencing_lab": "Example Lab"` which does *not* match the seed. That fixture is only used by ingest tests (Session G) and ingest validation is expected to treat it as unknown → 422. Don't try to "fix" the fixture here.

**ASCII diagram:**

```
           sequencing_labs                labs
           ┌────────────┐            ┌────────────┐
           │id          │◄──┐    ┌──►│id          │
           │name UNIQUE │   │    │   │display_name│
           │is_external │   │    │   │active      │
           │is_active   │   │    │   └────────────┘
           └────────────┘   │    │
                            │    │
                  sequencing_lab_assignments
                  ┌────────────────────────┐
                  │id                      │
                  │sequencing_lab_id ──────┘
                  │lab_id ─────────────────┐
                  │UNIQUE(sid, lid)        │
                  │created_at              │
                  └────────────────────────┘

client ─► POST /api/v1/sequencing-labs/{sid}/assign/{lid}
           │
           ▼
  require_platform_admin(user)            ── 403 if not admin
           │
           ▼
  ┌─ injected db session ─────────────────────────────────┐
  │  SELECT 1 FROM sequencing_labs WHERE id=:sid → 404    │
  │  SELECT 1 FROM labs WHERE id=:lid            → 404    │
  │  SELECT 1 FROM sequencing_lab_assignments             │
  │    WHERE sequencing_lab_id=:sid AND lab_id=:lid → 409 │
  │  INSERT INTO sequencing_lab_assignments RETURNING *   │
  │  log_audit(ASSIGN_SEQUENCING_LAB, db_conn=db)         │
  └───────────────────────────────────────────────────────┘
           │
           ▼
  success(data=row, status_code=201)
```

---

## 2026-04-16 — Session F: tokens router + project name filter

**What was built**

- Fleshed out stub `backend/routers/projects.py` into a real paginated list
  with `?name=` case-insensitive exact filter (for the CLI project lookup),
  plus `GET /api/v1/projects/{id}` for completeness. Authenticated only.
- Fleshed out stub `backend/routers/tokens.py` into 3 endpoints:
  `GET /`, `POST /`, `DELETE /{id}`. Tokens are owned by the caller; Platform
  Admin can revoke anyone's. Token value shown once on create, then only the
  SHA-256 hash lives in `personal_tokens.token_hash`.
- Alembic migration `e2dede78c435` adds `default_lab_id` + `default_project_id`
  FKs to `personal_tokens` (ON DELETE SET NULL).
- Added `CREATE_TOKEN` / `REVOKE_TOKEN` audit actions.
- Removed `projects.py` and `tokens.py` from `pyproject.toml` coverage omit
  list → both reach 100% stmt coverage.

**Key decisions**

- **SHA-256, not bcrypt**, for token hashing. The spec says "stored as hash
  in DB" — the DDL comment in `db/init.sql:100` already specifies SHA-256
  and the existing column is `token_hash` (fixed-width text). Bcrypt buys
  nothing here: API tokens already carry 256 bits of entropy from
  `secrets.token_urlsafe(32)`, so the slow-hash protection against rainbow
  tables is wasted cycles. SHA-256 also permits O(1) lookup by hash, which
  any future auth-via-token path will need. Bcrypt would force a
  full-table scan on every authenticated request. Noted this choice
  explicitly so a future reader doesn't flag it as a password-hashing bug.
- Kept the DB column name `last_used` (not `last_used_at`). The todo used
  the `_at` suffix casually; a rename migration for one column isn't worth
  the churn across init.sql + any external readers. Exposed as `last_used`
  in the API.
- Fresh `/projects` endpoint takes `?name=` as a query param and matches
  on `LOWER(display_name) = LOWER(:name)` — *exact* match, not ILIKE %%,
  because the CLI does `jackpot run --project "Foo Bar"` and needs
  deterministic resolution. A substring match would silently pick a
  different project if names overlapped.
- Pre-checked `default_lab_id` / `default_project_id` FKs *inside* the same
  transaction before INSERT, returning precise 404s. Without the pre-check
  the DB would raise a generic `ForeignKeyViolation` that bubbles up as 500.
- Platform-admin-can-revoke path reuses the already-fetched `before` row
  (SELECT-then-check) rather than doing a second DELETE with a compound
  predicate. That way audit log captures the full prior state regardless of
  who did the revoke.

**Watch out for**

- The `cleanup_user` helper in `tests/test_tokens_api.py` must DELETE from
  `personal_tokens` *before* deleting the user, or the `user_id` FK blocks
  the delete. Added that step to the helper.
- `secrets.token_urlsafe(32)` returns ~43 chars — assertion checks
  `len > 20` to stay robust if the byte length ever changes.
- Test `test_platform_admin_can_revoke_any_token` flips back to the dev
  seed email (`admin@example.org`) to exercise the admin branch; the
  conftest `monkeypatch` + `cache_clear()` pattern from earlier sessions
  handles this cleanly — the `autouse=True` fixture in conftest resets it
  after the test so other tests aren't polluted.

**Diagram — token create/list flow**

```
client ─► POST /api/v1/tokens/  {name, default_lab_id?, default_project_id?}
            │
            ▼
   get_current_user(request)
            │
            ▼
   pre-check FKs (db-scoped)         ── 404 on unknown lab/project
            │
            ▼
   raw = secrets.token_urlsafe(32)    ── only in memory, never logged
   hash = sha256(raw).hexdigest()
            │
            ▼
   INSERT personal_tokens RETURNING <public cols>
   log_audit(CREATE_TOKEN, db_conn=db)
            │
            ▼
   response = {..public row.., "token": raw}   ← shown once
            │
            ▼  (subsequent)
client ─► GET /api/v1/tokens/
            │
            ▼
   SELECT <public cols> FROM personal_tokens WHERE user_id = :uid
   (token_hash is NEVER in _PUBLIC_COLUMNS — impossible to leak)
```

---

## Session G: ingest router — 2026-04-16

**What was built:** `/api/v1/ingest/upload` (GUI multipart), `/api/v1/ingest/csv`
(bulk CSV), and `/api/v1/ingest/globus` (Platform-Admin webhook). 19 new tests.
New baseline: 418 tests passing, 85.33% coverage (+19 tests, +0.25%). Commit
`3c74b24`.

**Key decisions**

- **Shared `_ingest_one()` core** takes metadata, URI map, size map, user, db,
  and ingest_method. This keeps the validator → sequencing-lab check →
  epiweek → scrub_status → quality/surveillance → INSERT samples + sample_files
  → audit pipeline in exactly one place. `/upload` stages files first and
  computes URIs; `/csv` constructs URIs from the `gs://jackpot-staging/<sid>/`
  convention since CSV rows reference pre-staged files; `/globus` doesn't call
  it at all — it only notifies Lab Directors.
- **Column whitelist via `_SAMPLE_COLUMNS` frozenset**, then dynamic INSERT
  from sorted present keys. This lets the endpoint accept partial payloads
  (only Tier 1 required fields) without hand-writing a Pydantic model for
  every combination of source_type × tier. Bad keys are silently dropped.
  Trade-off vs. a strict Pydantic model: we rely on `validate_sample()` for
  semantic checks, and the whitelist for SQL safety.
- **scrub_status derived from `file_detector.get_file_type`**: any `FASTQ`
  present → `PENDING`; all `FASTA` → `SKIPPED`. This matches spec rule 4
  (raw reads scrubbed; consensus sequences skipped). The scrub_status
  applied identically to the samples row and each sample_files row so the
  scrubber queue picks them up consistently.
- **`compute_epiweeks(date_collected, precision)`** called in `_ingest_one`
  before INSERT — respects the validator's precision read from
  `metadata["date_collected_precision"]`. Year/month precision returns
  `None` across all four columns; day returns live MMWR + ISO values.
- **`/globus` uses `log_audit(CREATE_SAMPLE, resource_type='globus_deposit')`**
  even though no sample row is created. The action is still a "sample
  creation lifecycle event" — the downstream metadata completion workflow
  produces the actual row later. This preserves the chain of custody from
  first touch to final sample.
- **Type coercion in `_coerce_types()`**: `lab_id`, `project_id`, `host_age`,
  etc. can arrive as strings from JSON/CSV but the DB expects `INTEGER`.
  A focused coercion helper keeps the INSERT clean rather than scattering
  `int()` calls through the builder.
- **FASTA-only scrub skip** vs. validator "SKIP via override" distinction:
  FASTA upload auto-skips scrubber (it's already an assembled consensus —
  nothing to scrub). Raw FASTQ always starts at `PENDING`; the override
  request workflow (Lab Director → Platform Admin) is the only other path
  to `SKIPPED` for FASTQ.

**Watch out for**

- **DB NOT NULL vs. validator tier mismatch.** The `samples` table has
  `NOT NULL` on fields the validator considers Tier 2 (e.g. `date_sequenced`,
  `library_preparation_method`, `sequencing_protocol`). A client sending
  only BASE_REQUIRED metadata passes `validate_sample()` but the INSERT
  will 500 on a NOT NULL violation. For now the contract is: client sends
  all DB-NOT-NULL fields even for PRELIMINARY samples. A future migration
  could relax these NOT NULLs; for Month 1 we document the contract in
  tests — the `_base_metadata()` helper includes every NOT NULL field.
- **`sequencing_lab` is validated by `name`**, not by ID. The seed has
  "Example Sequencing Lab" and "Example Reference Lab";
  tests use "Example Sequencing Lab" as the canonical valid value
  (which exists in the DB seed). Using a name that
  doesn't exist in `sequencing_labs` returns 422 with a request-workflow
  message pointing to `POST /api/v1/sequencing-labs/requests`.
- **`UploadFile | None = File(None)`** requires `# noqa: B008` — FastAPI
  needs the call in the default to register the field. Also: FastAPI hands
  an empty-filename UploadFile when the client omits the field, so the
  upload endpoint checks `if fastq_r2 is not None and fastq_r2.filename`
  before including it.
- **`monkeypatch.setattr("backend.routers.ingest.stage_file", fake)`** —
  patch at the *router's* import site, not `backend.storage.stage_file`.
  Python's `from X import Y` binds the name into the importing module;
  patching the original only works if the router calls `storage.stage_file()`
  via attribute access. We import `stage_file` directly, so the router-level
  patch is the only working form. Same rule applies for any
  `monkeypatch` of an imported helper.
- **psycopg2 + SQLAlchemy auto-convert Python `list`s to PG arrays** when
  the target column is `TEXT[]`. `nucleic_acid_extraction_method`,
  `host_disease`, `purpose_for_collection`, etc. pass through cleanly —
  don't wrap them in custom casts.
- **CSV list-field parsing** accepts either JSON arrays (`["a","b"]`) or
  semicolon-delimited strings (`a;b`). The `_CSV_LIST_FIELDS` set lists
  known array columns. Unknown columns are passed through as strings and
  silently ignored by the `_SAMPLE_COLUMNS` filter — safer than rejecting
  them, since CSV templates may carry comment columns or ad-hoc notes.
- **`/globus` creates notifications via `create_notification()`** which
  swallows its own exceptions. A missing Lab Director assignment means
  `directors_notified: 0` is returned, not an error — this is the correct
  behavior (the deposit still happened; the lack of notification doesn't
  invalidate it).
- **Pre-commit `ruff-format` rewrites on first `gac`**, passes on second.
  Same pattern as Sessions B, C, E, F. No action needed beyond re-running
  `gac`.

**Diagram — GUI upload flow**

```
client ─► POST /api/v1/ingest/upload  (multipart: metadata, fastq_r1, fastq_r2?)
            │
            ▼
   get_current_user(request)
            │
            ▼
   json.loads(metadata) ── 422 on invalid JSON
            │
            ▼
   ┌─ single injected db session (get_db_dep) ───────────────┐
   │   for each upload: stage_file → gs://jackpot-staging/…  │
   │   _ingest_one(metadata, uri_map, size_map, user, db)    │
   │     ├─ validate_sample(metadata) ── 422 with tier data  │
   │     ├─ _check_sequencing_lab(name, db) ── 422 unknown   │
   │     ├─ compute_epiweeks(date_collected, precision)      │
   │     ├─ detect_files(filenames) ── R1/R2 pairing         │
   │     ├─ get_convenience_uris(detected, uri_map)          │
   │     ├─ scrub_status = PENDING (FASTQ) | SKIPPED (FASTA) │
   │     ├─ compute_quality_status(validation)               │
   │     ├─ compute_surveillance_relevant(org, targets, set) │
   │     ├─ INSERT samples … RETURNING *                     │
   │     ├─ INSERT sample_files per detected file            │
   │     └─ log_audit(CREATE_SAMPLE, tier=N, method=gui)     │
   │   commit → all writes atomic                            │
   └─────────────────────────────────────────────────────────┘
            │
            ▼
   success(data={...sample_row, files: [...]}, status_code=201)
```

---

## Session H: samples router — 2026-04-16

**What was built:** Six samples endpoints on `/api/v1/samples/` — GET list (with 11-parameter filter surface + `?select_all=true` + `can_see_sample` per row), GET {id} (+ file list), PATCH {id} (partial update + recompute quality + surveillance), DELETE {id} (soft-delete / archive), GET {id}/files, GET {id}/download (presigned URL). Plus a proper access-control module in `backend/permissions.py` with `can_access_sample`, `can_see_sample`, and `visibility_sql_clause` (SQL-side predicate). 32 integration tests. New baseline: **450 tests passing, 86.23% coverage** (+32 tests, +0.9%). Router coverage 89%; permissions module 88%.

**Key decisions:**

- **Two-tier access model.** `can_see_sample` includes `DISCOVERABLE` (shows in lists); `can_access_sample` excludes it (detail requires an approved `sample_access_requests` row). That is the only way the access-request workflow makes semantic sense — otherwise DISCOVERABLE would collapse into PUBLIC. Spec.md §5 Session H confirms: "Platform Admin → lab member → PUBLIC → host-operator oversight (surveillance_relevant only) → approved request" — no DISCOVERABLE on that ladder. todo.md's test hint conflicted ("DISCOVERABLE → 200 for authenticated users") and was ignored in favour of the spec.
- **Visibility enforced in SQL, not Python.** `visibility_sql_clause(user)` emits an OR'd EXISTS clause straight into the list WHERE, so the list endpoint paginates at the DB tier with no N+1 membership check. Platform Admin short-circuits to `"TRUE"`. Data analysts get `s.surveillance_relevant = TRUE` OR'd in for host-operator oversight.
- **LOCKED_FIELDS frozenset on PATCH.** Instead of silently dropping forbidden keys, any attempt to set `quality_status`, `surveillance_relevant`, `scrub_status`, `mmwr_week`, `iso_week`, `iso_year`, `mmwr_year`, `ingest_timestamp`, `is_deleted`, identifiers/accessions, pipeline outputs, or file URIs returns **422 with the offending field names**. Editable fields are a separate `_EDITABLE_FIELDS` whitelist — only the intersection is written. After the caller's update, the endpoint re-runs `validate_sample() → compute_quality_status()` and `compute_surveillance_relevant()` on the merged row and issues a second UPDATE, so derived state always matches the canonical source of truth.
- **Soft delete uses `is_deleted`, not `is_archived`.** todo.md H-4 says `is_archived=True` but the samples table in `db/init.sql` line 427 has `is_deleted BOOLEAN NOT NULL DEFAULT FALSE` plus `deleted_at` / `deleted_by_id`. Followed the schema and noted the reconciliation inline in todo.md. Log action stays `ARCHIVE_SAMPLE` (per AuditActions) — the action name describes the lifecycle stage, not the column name.
- **`raw_fastq` download restricted to Lab Directors.** Pre-scrub FASTQ may contain PHI; the download endpoint additionally checks `is_lab_director` on the sample's lab (Platform Admin bypasses). Other file types just require `can_access_sample`.
- **Pagination now allows `ingest_timestamp`.** Samples has no `created_at` — added `ingest_timestamp` to `pagination.ALLOWED_SORT_COLUMNS` and defaulted the samples list endpoint to `sort_by=ingest_timestamp`.
- **Test fixtures use `_switch_user(email, monkeypatch)` + `get_settings.cache_clear()`** so the `lru_cache`'d settings pick up the new mock email. The same pattern from Sessions A/B/C. Mandatory before every role-change test.

**Watch out for:**

- **The samples table does NOT have `created_at`/`updated_at`.** Do not copy the UPDATE ... `SET updated_at = NOW()` idiom from organizations/labs. It raises `UndefinedColumn`. The initial PATCH query had it and was silently passing tests until the first PATCH test hit it.
- **`sample_access_requests` FK blocks user DELETE in teardown.** `_cleanup_users()` must first `DELETE FROM sample_access_requests WHERE requester_id = :u OR owner_id = :u` before deleting the user. Audit log still needs the `UPDATE audit_log SET actor_id = NULL` step from Session B. Three-step cleanup now: access_requests → lab/project_membership → audit NULL → users.
- **Pre-commit ruff-format reformatted 4 files on the first `gac`,** failed the hook, then passed on the second. Also a SIM103 "return the condition directly" flagged `_base_access` (the last `if _has_approved_access_request(): return True; return False` was collapsible). Same "run gac twice" pattern as Sessions B/C/E/F/G — documented here for the sixth time.
- **Platform Admin uses `"TRUE"` in the SQL clause.** If future endpoints compose WHERE fragments via f-strings, that literal is a SQL keyword and is safe — but never substitute a user-supplied string there. The `visibility_sql_clause` helper intentionally returns only literals (`TRUE`, `PUBLIC`, `DISCOVERABLE`, `APPROVED`) plus parameterised `:uid`.
- **DISCOVERABLE detail returns 403 by design.** A test named `test_discoverable_sample_detail_requires_access` asserts this and also that granting an APPROVED `sample_access_requests` row flips it to 200. Reviewers reading from todo.md may be surprised — the reconciliation is the doc-comment at the top of `permissions.py` and at the top of the test module.

**ASCII diagram:**

```
client ─► GET /api/v1/samples/?lab_id=7&sharing_level=DISCOVERABLE
            │
            ▼
   get_current_user(request)
            │
            ▼
   visibility_sql_clause(user) ──► "(s.owner_id=:uid OR s.sharing_level IN
            │                        ('PUBLIC','DISCOVERABLE') OR EXISTS(…
            │                        lab_membership…) OR EXISTS(…project…)
            │                        OR EXISTS(…sample_access_requests…))"
            ▼
   ┌─ WHERE  s.is_deleted = FALSE                            ──┐
   │    AND  (visibility OR-ladder)                            │
   │    AND  s.lab_id = :lab_id                                │
   │    AND  s.sharing_level = :sharing_level                  │
   └──────────────────────────────────────────────────────────┘
            │
            ▼
   paginate() → (rows, total)
            │
            ▼
   success_list(data=rows, page, per_page, total)


client ─► GET /api/v1/samples/{id}
            │
            ▼
   _get_sample(id)  ── is_deleted=FALSE filter
            │
      ┌─────┴─────┐
      ▼           ▼
   None?       can_access_sample(user, sample, conn)
      │           │
      ▼           ├── Platform Admin  ─► 200
    404          ├── owner_id match  ─► 200
                  ├── lab_membership   ─► 200
                  ├── project_mbr      ─► 200
                  ├── sharing=PUBLIC   ─► 200
                  ├── data_analyst &&
                  │   surveillance     ─► 200
                  ├── APPROVED request ─► 200
                  └── else             ─► 403
```

---

---

## Session S: projects router + dataharmonizer — 2026-04-16

**What was built:** Fleshed out two stub routers. `projects` grew from GET-only to full CRUD: `POST /` (Lab Director on target lab OR Platform Admin), `GET /` (membership-filtered list with `?name=` + `?lab_id=` filters), `GET /{id}` (lab OR project member), `PATCH /{id}` (Lab Director on the project's lab). `dataharmonizer` went from stub to two real endpoints: `GET /templates/{source_type}/{tier}` (CSV download via `template_generator.generate_csv_template`) and `POST /validate` (row-by-row CSV validation via `validator.validate_sample`). New baseline: **477 tests passing, 86.99% coverage** (+27 tests, +0.76%). `dataharmonizer.py` removed from coverage omit, now at 94%; `projects.py` at 99%.

**Key decisions:**

- **Project access delegates to lab-level authorization.** `require_lab_director(user, project.lab_id)` for writes; list visibility is `(lab_id IN user's labs) OR (project_id IN user's projects)`. This matches spec.md: "members inherit lab access". A user invited to a single project sees only that project; a lab member sees all projects in the lab. Platform Admin short-circuits to all rows.
- **`AuditActions.CREATE_PROJECT` + `UPDATE_PROJECT` added.** Following the same pattern as `CREATE_LAB` / `UPDATE_LAB`. No `DELETE_PROJECT` — soft-delete via `active=FALSE` through PATCH; matches how `labs.py` handles the equivalent, except we skip the DELETE endpoint entirely for Month 1 (not in spec).
- **DataHarmonizer endpoints live on their own router, not under `/templates`.** todo.md wrote `/api/v1/templates/{source_type}/{tier}` as the example URL but the section title is "Implement dataharmonizer router". The existing `templates.py` already serves query-string-driven downloads. Rather than duplicate routes, the dataharmonizer surface got its own path-based route under `/api/v1/dataharmonizer/templates/{source_type}/{tier}` — zero collision with `/api/v1/templates/?source_type=...`.
- **Validation endpoint accepts both multipart file upload and raw `text/csv` body.** FastAPI's optional `UploadFile` (`file: UploadFile | None = File(default=None)`) gives us the form-upload path; when the field is absent we fall through to `await request.body()`. This lets the DataHarmonizer JS widget POST `text/csv` directly while the CLI can do a file upload. Empty body → 400.
- **Meta-row skipping in the CSV parser.** `generate_csv_template` emits 5 header rows (names, labels, tier tags, validation hints, example). The validator's `_parse_csv_rows` looks for rows containing any of `{REQUIRED, ANALYZABLE, SUBMITTABLE, OPTIONAL}` within the first 4 data rows and advances `data_start` past them — so a user who pastes an unedited template doesn't get the label row validated as a sample.
- **Commas-in-value become lists.** The parser splits any cell containing a comma into a list (except `gs://` URIs), since list-typed fields like `purpose_for_collection`, `host_disease`, `nucleic_acid_extraction_method` round-trip that way. Works fine with `csv.reader` which already handles cell quoting, so quoted `"a, b, c"` cells stay as a single string.
- **Test user cleanup needs project FK nullification.** Added `UPDATE projects SET created_by_id = NULL WHERE created_by_id = uid` before `DELETE FROM users`. Same three-step pattern from Session H (audit actor → project FK → user) — if a new table adds an FK to users, add another nullification here.

**Watch out for:**

- **`Isolate` source type has no source-specific required fields.** Used it as the happy-path test in validate tests. `Human` requires `external_case_id`, `biospecimen_type`, `reason_for_collection`, `host_disease` — the naive 7-column CSV that passes BASE_REQUIRED still fails Human's extras. Pick `Isolate` for "should be valid" fixtures.
- **Pre-commit ruff reformatted on first check.** Seventh session with the same finding — `gac` rewrites the file and exits non-zero the first time. Also surfaced an N806 on `META_MARKERS` being uppercase inside a function; renamed to `meta_markers`. Same pattern: run gac twice, let the first format and the second commit.
- **Data analysts do not automatically see all projects.** The list filter is `lab_membership OR project_membership`; `is_data_analyst` does not bypass project visibility. That's a surveillance-samples-only privilege, applied at the samples layer, not the project layer. Keep this boundary when wiring future endpoints.
- **`/api/v1/dataharmonizer/templates/{tier}` is case-insensitive.** `tier.upper()` before the enum lookup, so `preliminary`, `Preliminary`, and `PRELIMINARY` all work. The filename reflects the lowercase form.

**ASCII diagram — dataharmonizer validate flow:**

```
client ─► POST /api/v1/dataharmonizer/validate
            │   (multipart file OR raw text/csv body)
            ▼
   get_current_user(request)
            │
            ▼
   body_bytes = file.read() or request.body()
            │
            ├─ empty            ─► 400
            └─ invalid utf-8    ─► 400
            │
            ▼
   _parse_csv_rows(raw)
     ├─ row 1: header (field names)
     ├─ rows 2-5: skip if REQUIRED/ANALYZABLE/SUBMITTABLE/OPTIONAL marker
     ├─ each data row: split commas → list; else string
     └─ yield list[dict]
            │
            ├─ no rows          ─► 400
            │
            ▼
   for idx, record in enumerate(records):
       validate_sample(record) → ValidationResult
            │
            ▼
   return {total_rows, valid_rows, results: [{row, sample_id, valid,
           tier, sector, errors, warnings, tier2_missing, tier3_missing}]}
```

---

## Session J: viral pipeline parsers (Cecret / viralrecon / walkercreek) — 2026-04-17

**What was built:** Pipeline-level parsers in the `jackpot-nf` submodule for
three viral pipelines — Cecret (SARS-CoV-2 isolate + wastewater),
viralrecon (SARS-CoV-2 multi-caller), and walkercreek (Influenza/RSV) —
plus a shared parser layer, 44 new pytest cases, and fixture trees for
each pipeline. Backend baseline: 486 tests passing, 86.99% coverage
(+9 tests, stable coverage). Submodule at `nf/` bumped to commit
`2a098b0`; backend commit `6aeee66`.

**Key decisions:**

- **Sibling top-level packages** (`shared/` and `pipelines/` both at the
  `nf/` root): `pyproject.toml` only packages `shared`, and `pipelines/`
  is imported by tests via a `sys.path.insert` shim. Relative imports
  like `from ....shared.parsers import ...` fail because the two trees
  have no common Python package parent — everything uses **absolute
  imports** (`from shared.parsers import ...`). This is the only
  import style that works inside both the live Nextflow wrapper and
  the pytest harness.
- **Two result shapes, not one.** `ParsedResult` carries typed rows
  destined for a `/results/{result_type}` endpoint; `FileArtifact`
  describes a FASTA/BAM/etc. that will be POSTed to the
  `sample_files` table. Mixing them into one schema would have forced
  `sample_files` into `RESULT_SCHEMAS` and bent the result-registration
  contract. Kept separate.
- **Shared Pangolin/Nextclade parsers** under `shared/parsers/` rather
  than duplicating between Cecret and viralrecon. Both pipelines emit
  the same TSV/CSV structures; the only difference is which subdirectory
  the file lives in. Pipeline-level parsers just orchestrate where to
  look.
- **Freyja parser explodes one row per (sample, lineage)** with
  `ABUNDANCE_FLOOR=1e-6` to drop numerical-noise lineages. Avoids
  downstream dashboards showing "0.000000001 AY.4" as if it were a
  real detection.
- **iVar variants uses a sentinel result_type `"pipeline_metrics"`.**
  Not in `RESULT_SCHEMAS` — documented inline in the parser. It's a
  summary record (total / pass / fail variants), not a per-variant
  table; inventing a schema for this would be premature.
- **walkercreek consensus dual layout** (Illumina: nested
  `consensus/<sample>/<SEGMENT>.fa`; Nanopore: flat
  `consensus/<sample>_<SEGMENT>.fa`) handled by a single `rglob` +
  `path.parent` check. File subtype is `segment_HA` / `segment_NA`
  rather than plain `"consensus"` so downstream consumers can select
  a specific segment without re-parsing.
- **IRMA default_scheme derivation**: when typing_summary.tsv omits
  `scheme`, derive from `subtype` prefix (H1N1pdm09→h1n1, H3N2→h3n2,
  B→flub, RSV-*→rsv, else irma). Keeps WalkerCreek's historical output
  compatible with the modern scheme-aware table.
- **`SUPPORTED_PIPELINE_VERSIONS`** declared per pipeline so the
  register client can reject unknown versions at boundary. Cecret 3.6
  –3.66 enumerated; viralrecon 2.4.0–2.6.0; walkercreek 1.0.x–1.1.x.

**Watch out for:**

- **Submodule commit + pointer bump is two commits.** Fixing a parser
  bug requires: (1) commit in `nf/`, (2) `git add nf && gac` in the
  backend to bump the submodule SHA. Forgetting step 2 leaves CI
  using the old parser. Always verify `git status` in the backend
  shows `modified: nf (new commits)` after submodule work.
- **`uv run pytest` from the backend does not exercise the submodule
  tests.** The submodule has its own `pyproject.toml` and must be
  tested separately with `cd nf && uv run pytest`. The backend's 486
  tests do not cover the 79 submodule tests. Both must pass before
  claiming the session is done.
- **Fixture malformedness bites late.** An initial nextclade fixture had
  `qc.overallScore="bad"` (string in a float column) due to a miscount
  of tab characters — parse failure only surfaced in the test run, not
  at fixture-write time. Pattern going forward: keep fixtures minimal
  and move edge-case payloads inline via `tmp_path` in the tests that
  need them.
- **Freyja aggregated TSV leading blank column.** The first column
  header is empty (`\t` then `lineages\t...`); the row key is the
  filename (e.g. `AZ-WW-001.freyja.tsv`). Parsers must read the leading
  unnamed column to recover `sample_id` via filename stripping.
  Missing this yields silently-empty results.
- **Ruff auto-fix can reorder imports.** After a fixture cleanup pass,
  `uv run ruff check --fix` moved `noqa: E402` comments that pytest's
  `sys.path.insert` shim requires. Re-run tests after every
  ruff-format / ruff-check-fix cycle.

**ASCII diagram:**

```
nf/                       ← jackpot-nf submodule
├── shared/parsers/       ← reusable: types, pangolin, nextclade
│   ├── types.py          RunMetadata, ParsedResult, FileArtifact
│   ├── pangolin.py       lineage_report.csv → ParsedResult[pangolin_results]
│   └── nextclade.py      nextclade.tsv → ParsedResult[nextclade_results]
│
├── pipelines/
│   ├── cecret/parsers/
│   │   ├── __init__.py       orchestrates shared pangolin + nextclade
│   │   ├── freyja.py         aggregated-freyja.tsv → wastewater rows
│   │   └── consensus.py      consensus/*.consensus.fa → FileArtifact
│   ├── viralrecon/parsers/
│   │   ├── __init__.py       reuses shared; locates per-subdir files
│   │   ├── variants.py       ivar TSV → pipeline_metrics (total/pass/fail)
│   │   ├── freyja.py         re-export of cecret.freyja
│   │   └── consensus.py      consensus/{bcftools,ivar}/*.fa → FileArtifact
│   └── walkercreek/parsers/
│       ├── __init__.py       IRMA + consensus orchestrator
│       ├── irma.py           typing_summary.tsv → typing_results
│       └── consensus.py      dual-layout consensus → FileArtifact(segment_*)
│
└── tests/
    ├── fixtures/{cecret,viralrecon,walkercreek}/...
    ├── test_cecret_parsers.py        21 tests
    ├── test_viralrecon_parsers.py    10 tests
    └── test_walkercreek_parsers.py   13 tests

Backend commit 6aeee66 bumps nf pointer to submodule commit 2a098b0.
```

---

## Session K: bacterial isolate parsers (bactopia/Grandeur/mycosnp/tb-profiler) — 2026-04-17

**What was built:** Phase 13 of the jackpot-nf plugin — parsers for bactopia (K-1), Grandeur (K-2), mycosnp-nf (K-3), and tb-profiler (K-4), plus three new shared helpers (AMRFinderPlus, MLST, Kraken2), 15 fixtures, and 51 new unit tests (K-5, K-6). Submodule baseline: 137 tests passing (+51). Backend baseline unchanged at 486 tests / 86.99% (nf tests run inside the submodule, not in the parent pytest run).

**Key decisions:**

- **Shared AMR normalization threaded through `shared.hamronization_normalizer`** per the explicit spec requirement. `shared/parsers/amrfinderplus.py` wraps `normalize()` and exposes two entry points: `parse()` (runs the hAMRonize CLI on a raw AMRFinderPlus TSV) and `parse_canonical()` (skips the CLI when a `*.hamronized.tsv` already exists). Grandeur 4.x ships canonical outputs, so its parser prefers the shortcut and only falls back to `runner` when no canonical sibling is found. Bactopia always uses the CLI path.
- **Injectable `runner` callable** on every AMR parser so tests don't need `hamronize` on PATH. `runner` signature is the subset of `subprocess.run` the normalizer actually uses (`(cmd, *, capture_output, text) → CompletedProcess`). Tests pass in a closure that returns a canned canonical TSV. The `shared.hamronization_normalizer.run_hamronize()` binary-presence check is still first — tests monkeypatch `shutil.which` to return a truthy path before calling.
- **TB-profiler mirrors drug resistance into `amr_results`** per spec: each `dr_variants[].drugs[]` row becomes an `AMRResult` with `reference_database="WHO_catalogue"`, `reference_accession=f"WHO-Catalogue/{db_version}"`, `drug_class="antimycobacterial"`, `tool_name="tb-profiler"`. This lets TB resistance surface in platform-wide AMR search alongside bacterial AMR results without a special-case query. The original TB-typing row (`tb_typing_results` with `who_drug_susceptibility` JSONB) is still emitted for the WHO-catalogue-shaped view.
- **Run-level sentinel `_run_`** for mycosnp cohort outputs. SNP trees (`core.aln.treefile`) are cohort-level artifacts, not per-sample; they can't have a real `sample_id`. Exposed as `pipelines.mycosnp.parsers.tree.RUN_LEVEL_SAMPLE_ID = "_run_"` so any downstream consumer that groups by `sample_id` can detect and route cohort artifacts distinctly.
- **Canonical-takes-priority rule** in Grandeur AMR: if both `AZ-1.tsv` (raw) and `AZ-1.hamronized.tsv` (canonical) exist, only canonical is parsed. Test `test_canonical_takes_priority_over_raw` asserts the CLI runner is never invoked by raising `AssertionError` if it is — a loud failure is better than silently double-counting.
- **Bactopia `_QUAST_COLUMN_MAP` is a guard surface**: a separate `test_quast_column_map_covers_expected_keys` test asserts every mapped target matches one of seven known AssemblyQC columns. If upstream QUAST renames a metric, we want a test failure rather than a silent drop.
- **Absolute imports only** across all four pipelines (`from shared.parsers import RunMetadata`). Consistent with Session J's choice — the pipelines are sibling top-level packages under `nf/`, not submodules of `shared`.

**Watch out for:**

- **`_ALLELE_RE` matches dash-only alleles**: Tseemann's `mlst` emits `adk(-)` when the locus is present in the scheme but unassigned. The regex `^(?P<locus>[A-Za-z0-9_]+)\((?P<allele>[^)]+)\)$` captures this as `{"adk": "-"}`, not as a raw key `"adk(-)"`. First pass of `test_blank_st_becomes_none` asserted the raw-key fallback; corrected to assert `allele_calls["adk"] == "-"`.
- **`hamronize` CLI presence is checked before the runner runs**. `shared.hamronization_normalizer.run_hamronize()` calls `shutil.which("hamronize")` at the top and raises `HamronizationError` if missing — so an injected `runner` alone isn't enough. All AMR tests either (a) provide a canonical TSV and never hit the CLI path, or (b) monkeypatch `shutil.which` to return a truthy path. The bactopia `fake_runner` fixture does this explicitly for every test in the class.
- **TB-profiler `pipeline.software_version` fallback chain**: lineage parser prefers `data["pipeline"]["software_version"]`, falls back to `metadata.pipeline_version`, and only uses `None` if both are absent. `db_version` has no fallback — if the WHO catalogue version isn't in the JSON, the mirror rows get `reference_accession="WHO-Catalogue/None"` which is ugly but not wrong. Upstream tb-profiler always populates both in practice.
- **Mycosnp typing parser is strict**: if the TSV is missing the `sequence_type` column it raises `FungalTypingParseError` rather than silently dropping to a partial `TypingResult`. This is intentional — a missing scheme column usually means the tool failed halfway, and we want the failure loud.
- **Grandeur BLAST summary emits `pipeline_metrics`, not a dedicated model.** We don't have an `AlignmentSummary` schema and didn't want to invent one for a single consumer. If BLAST metrics become queryable via the API, promote to a Pydantic model then.
- **GFF3 and GFF both accepted** by the bactopia annotation collector. The `file_type` column uses the bare extension (`gff`) regardless — consumers shouldn't have to branch on the two variants.

**ASCII diagram:**

```
nf/
├── shared/parsers/
│   ├── amrfinderplus.py  wraps shared.hamronization_normalizer.normalize
│   │                     parse()            → raw TSV  → CLI  → canonical
│   │                     parse_canonical()  → canonical TSV directly
│   ├── mlst.py           Tseemann mlst TSV → TypingResult
│   └── kraken2.py        6-col report → TaxonomicProfile (top_only for isolates)
│
├── pipelines/
│   ├── bactopia/parsers/
│   │   ├── amr.py         amrfinderplus/<sample>.tsv → shared AMR (runs CLI)
│   │   ├── mlst.py        mlst/<sample>.tsv → shared MLST
│   │   ├── assembly.py    quast/report.tsv + shovill/*.contigs.fa → AssemblyQC + FileArtifact
│   │   └── annotation.py  bakta/prokka GFF → FileArtifact(file_type=gff)
│   │
│   ├── grandeur/parsers/
│   │   ├── amr.py         prefers *.hamronized.tsv (parse_canonical shortcut)
│   │   │                  falls back to raw *.tsv via CLI only if no canonical
│   │   ├── mlst.py        shared MLST
│   │   ├── kraken2.py     shared Kraken2 (top_only=True)
│   │   └── blast.py       -outfmt 6 tabular → pipeline_metrics
│   │
│   ├── mycosnp/parsers/
│   │   ├── snippy.py      snippy/<sample>/<sample>.txt → pipeline_metrics
│   │   ├── tree.py        tree/core.aln.treefile → FileArtifact(sample_id="_run_")
│   │   └── typing.py      typing/*_{scheme}.tsv → TypingResult
│   │
│   └── tb_profiler/parsers/
│       ├── lineage.py           results/<sample>.results.json → TBTypingResult
│       └── drug_resistance.py   dr_variants[] → (a) who_drug_susceptibility JSONB
│                                              → (b) amr_results mirror rows
│                                                    reference_database="WHO_catalogue"
│
└── tests/  (137 total, +51 for Session K)
    ├── fixtures/{bactopia,grandeur,mycosnp,tb_profiler}/...
    ├── test_bactopia_parsers.py       18 tests (incl. fake_runner fixture)
    ├── test_grandeur_parsers.py       11 tests (canonical-priority guard)
    ├── test_mycosnp_parsers.py        12 tests
    └── test_tb_profiler_parsers.py    10 tests

Submodule commit 2973e7a; backend bump tracks pointer.
```

## Session L: metagenomic parsers (nf-core/mag + nf-core/taxprofiler) — 2026-04-17

**What was built:** Parser modules for nf-core/mag (CheckM2 MAG QC, GTDB-Tk taxonomy, bin-FASTA registry) and nf-core/taxprofiler (Kraken2 full ranked list, Bracken abundance, DIAMOND summary) inside the `jackpot-nf` submodule, plus 36 new unit tests covering the one-sample-to-many-MAGs relationship end-to-end.

**Key decisions:**

- **MAG derived-sample design is spread across three emit sites.** MAGQC rows use `sample_id=parent, bin_id=bin_id` (parent parses out of `<parent>.<binner>.<n>` via the default `sample_id_resolver`), GTDB-Tk TaxonomicProfile rows use `sample_id=bin_id` (the bin *is* the derived sample), and the bin FASTA FileArtifact also uses `sample_id=bin_id`. The parser layer stays dumb about the `sample_associations` junction table — the backend registration endpoint is the sole owner of derived-sample + mag_bin wiring. This keeps parsers pure functions of file → model.
- **Shared Kraken2 parser now has two knobs: `top_only` and `species_only`.** Grandeur (isolate) keeps the default top-S behaviour. taxprofiler (metagenome) passes `top_only=False, species_only=False` and preserves every rank and row. Previously the species filter was unconditional inside the shared parser and silently dropped non-S rows even when `top_only=False`. Guard test `test_shared_kraken2_parser_used` asserts taxprofiler imports the shared module (not a fork).
- **Bin FASTA discovery uses a heuristic, not hardcoded paths.** nf-core/mag emits bins under many variants (`GenomeBinning/MetaBAT2/bins/`, `GenomeBinning/DAS_Tool/bins/`, `GenomeBinning/MaxBin2/`, etc.). `_is_bin_file()` walks the tree and accepts files whose parent chain hits `bins/` or a binner-named directory (metabat2/maxbin2/concoct/das_tool/dastool/semibin/genomebinning), explicitly excluding `Assembly/` so primary contigs don't leak in.
- **taxprofiler filename parsing uses `rpartition("_")` on the stripped stem.** Sample IDs may contain underscores; the last underscore is the sample/db delimiter. The db name feeds `reference_database` so surveillance queries can filter by Kraken2 DB (`standard` vs `viral-only` vs custom).
- **DIAMOND emits `pipeline_metrics`, not `taxonomic_profile`.** Raw BLAST outfmt-6 is too rich to shoehorn into TaxonomicProfile; instead we summarise into total_hits + top_subject + top_bitscore + top_identity_percent. Empty files still emit a zero-hits row so downstream reports don't silently drop samples.
- **Conservative missing-column handling.** `-` and `N/A` in CheckM2 numeric fields get dropped cleanly (field omitted from payload) rather than forcing a Pydantic ValidationError. Missing *required* columns (Name in CheckM2, required trio in GTDB-Tk/Bracken) raise typed ParseErrors.

**Watch out for:**

- **sample_associations is NOT set by the parser.** When writing the registration endpoint for MAG runs, iterate MAGQC rows, upsert each `bin_id` as a derived sample (parent = MAGQC.sample_id), then insert `sample_associations(parent_id=..., child_id=..., type='mag_bin')`. The parser layer intentionally omits this to keep it testable.
- **Two MAGQC rows per parent is the expected shape,** not a bug. `AZ-META-001` having `.MetaBAT2.1` and `.MetaBAT2.2` bins produces two MAGQC rows sharing `sample_id=AZ-META-001` with distinct `bin_id`s. The registration layer must handle duplicate parent writes idempotently.
- **Default `sample_id_resolver` splits on the first `.`.** If a sample naming scheme uses `.` in the parent ID itself (e.g. `sp.1_AZ.META.001`), the default resolver will chop it. Callers can pass a custom `sample_id_resolver` callable.
- **`species_only=True` is still the default on the shared Kraken2 parser** — Grandeur isolate paths are unchanged. Only taxprofiler opts out. Future metagenomic callers must remember to flip both flags.
- **Bracken fraction is stored as percent, rounded to 4 decimals.** `0.123456789` → `12.3457`. Already-rounded downstream consumers (Streamlit pages, BigQuery dashboards) should expect percent, not fraction.
- **DIAMOND needs ≥ 12 columns per row** (standard outfmt-6). Malformed rows are skipped silently; empty files emit a zero-hits summary.

**ASCII diagram:**

```
nf-core/mag output
├── CheckM2/checkm2_quality_report.tsv
│       └──► checkm2.parse → MAGQC rows
│                             sample_id=parent, bin_id=<parent>.<binner>.<n>
│                             (one parent → many MAGQC rows)
├── Taxonomy/GTDB-Tk/gtdbtk.{bac120,ar53}.summary.tsv
│       └──► gtdbtk.parse → TaxonomicProfile rows
│                            sample_id=bin_id  (derived sample)
└── GenomeBinning/<binner>/bins/*.fa
        └──► bin_registry.collect → FileArtifact rows
                                     sample_id=bin_id  (derived sample)
                                     file_subtype=mag_bin, file_type=fasta
       ╔════════════════════════════════════════════════════════╗
       ║  Backend registration endpoint (NOT the parser) is     ║
       ║  responsible for:                                      ║
       ║    1. Upserting derived sample rows keyed on bin_id    ║
       ║    2. Inserting sample_associations(parent→child,      ║
       ║       type='mag_bin')                                  ║
       ╚════════════════════════════════════════════════════════╝

nf-core/taxprofiler output
├── kraken2/<sample>_<db>.kraken2.kraken2.report.txt
│       └──► kraken2.parse  (shared Kraken2, top_only=False, species_only=False)
│                            → TaxonomicProfile rows (every rank retained)
├── bracken/<sample>_<db>.bracken.tsv
│       └──► bracken.parse → TaxonomicProfile rows
│                            abundance_percent = fraction * 100 (4dp)
└── diamond/<sample>_<db>.diamond.tsv  (BLAST outfmt-6)
        └──► diamond.parse → ONE pipeline_metrics row per sample
                              total_hits, top_subject, top_bitscore,
                              top_identity_percent
```

nf/ tree delta:

```
pipelines/
├── mag/
│   ├── __init__.py            SUPPORTED_PIPELINE_VERSIONS=[2.5.4,3.0.0,3.0.3,3.1.0]
│   └── parsers/
│       ├── __init__.py        orchestrator: checkm2 + gtdbtk + bin_registry
│       ├── checkm2.py         CheckM2 TSV → MAGQC  (sample_id_resolver hook)
│       ├── gtdbtk.py          bac120 + ar53 summary → TaxonomicProfile
│       └── bin_registry.py    bin FASTAs → FileArtifact(mag_bin)
└── taxprofiler/
    ├── __init__.py            SUPPORTED_PIPELINE_VERSIONS=[1.1.5,1.1.6,1.2.0]
    └── parsers/
        ├── __init__.py        orchestrator
        ├── kraken2.py         defers to shared.parsers.kraken2 (top_only=False)
        ├── bracken.py         abundance TSV → TaxonomicProfile
        └── diamond.py         BLAST outfmt-6 → pipeline_metrics

shared/parsers/kraken2.py      + species_only parameter (default True)

tests/  (173 total, +36 for Session L)
├── fixtures/mag/{CheckM2,GenomeBinning/{MetaBAT2,DAS_Tool}/bins,Taxonomy/GTDB-Tk}/
├── fixtures/taxprofiler/{kraken2,bracken,diamond}/
├── test_mag_parsers.py         20 tests (derived-sample wiring, bin-id=sample_id)
└── test_taxprofiler_parsers.py 16 tests (incl. shared-parser guard test)
```

Submodule commit a09ec7d; backend bump tracks pointer.

---

## Session M — nf-core/pathogensurveillance parser + parser version matrix — 2026-04-17

**What was built:** Session M phase 15: the 8-result-surface pathogensurveillance
wrapper (sendsketch / amrfinderplus / mlst / graphtyper / reference_selection /
phylogeny / report), a cross-pipeline AMR canonical-payload invariant that
catches divergence between the three AMR-producing wrappers (bactopia,
Grandeur, PSV), a shared `check_pipeline_version` helper, a full parser-version
matrix in `nf/README.md`, a minimal `pipeline_catalog` table with a
`parser_version` column, and a skip-by-default end-to-end integration test
that walks every wrapper against its fixture tree.

**Key decisions:**

- **Decoupled layout dict in pathogensurveillance orchestrator.** The parsers
  module hardcodes directory names in a `_LAYOUT` constant rather than scattering
  them through `parse()`. When nf-core/pathogensurveillance shuffles its top-level
  dirs between minor releases (they rename `variants/` frequently), only the
  dict moves — no per-call sites edit.
- **`pipeline_catalog` created minimally here, extended in Session N.** The
  spec puts the table creation in Month 2 session 31 but Session M's
  `parser_version` column can't land without the table. Solution: create the
  thinnest possible shape (id, pipeline_name, pipeline_version, parser_version,
  tier, is_active, timestamps) and let Session N `ALTER TABLE ADD COLUMN` the
  launch fields. `IF NOT EXISTS` keeps the path safe if the session order flips.
- **Reference selection: both layouts in one parser.** 1.1.0 ships two file
  formats (key/value pairs vs. header-plus-row) depending on the minor. The
  parser's layout-B check requires ALL first-row cells to be recognised field
  names — initial `set(first) & _FIELDS` matched layout A's first cell
  (`reference_accession`) and mis-parsed the value as a header.
- **Version check is exact-string, not semver.** Cecret tags include '3.66',
  viralrecon tags both '2.6' and '2.6.0' as distinct releases — semver range
  resolution would silently accept or reject in surprising ways. The spec
  already defines `SUPPORTED_PIPELINE_VERSIONS` as an enumerated list; trust it.
- **Version mismatch warns, does not raise.** Per spec.md line 382, pipeline
  version drift is non-blocking — the check builds a `pipeline_events`-ready
  message but the helper itself is pure (caller owns HTTP transport, so tests
  don't have to mock the network).
- **E2E test uses a `integration` pytest marker + `addopts = -m 'not integration'`.**
  Default `pytest` runs skip the 11 parse-every-fixture cases; CI runs them
  explicitly via `pytest -m integration`. Coverage is still enforced, just
  in a separate job.
- **Added `nf/` to backend ruff exclude.** The submodule has its own pyproject
  with matching line-length=100, but the backend's ruff was applying slightly
  different format rules (trailing-comma style). Excluding the submodule at
  the backend boundary is the right tooling separation — each repo owns its
  own ruff config.

**Watch out for:**

- The AMR invariant test depends on `bactopia_amr.shared_amr is shared_amr`
  (identity, not equivalence). If someone adds a local AMR parser to any of
  the three wrappers that bypasses the shared path, the identity check fails
  fast even if the payload happens to match for a given fixture.
- `pipeline_catalog` is deliberately under-specified — Session N must ALTER
  TABLE to add pipeline_uri, pipeline_revision, compute_config, etc. Don't
  assume the current column set is final.
- Integration test's `_sample_from_cmd_tail` greps the hamronize command for
  a `.tsv` argument to derive the sample_id. If the real hamronize CLI
  changes its positional-argument order or switches to stdin, update the
  fake runner.
- `pipeline_runs.parser_version_used` already exists from migration
  `acd770bb1753` — do not re-add it in future migrations.
- VCF fixtures: `AZ-PSV-002.vcf.gz` was generated via Python `gzip.open`,
  not `bgzip`. The parser uses `gzip.open()` so both work, but if a future
  change introduces `pysam.VariantFile` or similar, bgzip indexing will be
  required and the fixture needs regenerating.
- `addopts = "-m 'not integration'"` changes the default collect — new test
  files accidentally using `@pytest.mark.integration` will be silently
  deselected. Every marker use must be deliberate.

**ASCII diagram — M-3 version-check flow:**

```
wrapper launcher
  │
  ▼                                      SUPPORTED_PIPELINE_VERSIONS
RunMetadata(pipeline_name, version) ──► (pipelines/<name>/parsers/__init__.py)
  │                                              │
  │                                              ▼
  └──► shared.version_check.check_pipeline_version
                   │
                   ├── version in list?
                   │     ├── yes → VersionCheckResult(is_supported=True, warning_message=None)
                   │     └── no  → VersionCheckResult(is_supported=False, warning_message="...")
                   │
                   ▼
             caller posts to pipeline_events if warning_message is not None
             (non-blocking — parse proceeds either way)
```

nf/ tree delta:

```
pipelines/pathogensurveillance/
├── __init__.py                    SUPPORTED_PIPELINE_VERSIONS=[1.1.0]
└── parsers/
    ├── __init__.py                _LAYOUT dict; orchestrates 8 surfaces
    ├── identification.py          sendsketch → TaxonomicProfile (top hit)
    ├── amr.py                     defers to shared.parsers.amrfinderplus
    ├── mlst.py                    defers to shared.parsers.mlst
    ├── variants.py                graphtyper VCF → pipeline_metrics
    ├── reference_selection.py     two-layout TSV → pipeline_metrics
    ├── phylogeny.py               treefiles → FileArtifact (run-level)
    └── report.py                  HTML report → FileArtifact (run-level)

shared/version_check.py           check_pipeline_version(name, version, support)

tests/  (236 total: 225 unit + 11 integration)
├── fixtures/pathogensurveillance/{sendsketch,amrfinderplus,mlst,variants/graphtyper,
│   reference_selection,phylogeny/{core_gene,busco,snp},report}/
├── test_pathogensurveillance_parsers.py  32 tests
├── test_amr_normalization_invariant.py    5 tests (cross-pipeline)
├── test_version_check.py                 15 tests
└── test_pipeline_integration_e2e.py      11 tests @pytest.mark.integration
```

Backend delta:

```
db/migrations/versions/b1a4c9d2e8f0_add_pipeline_catalog_and_parser_.py
   CREATE TABLE pipeline_catalog (id, pipeline_name, pipeline_version,
       parser_version, tier, is_active, created_at, updated_at)
   UNIQUE (pipeline_name, pipeline_version)
   INDEX (tier, is_active)
pyproject.toml  ruff exclude += "nf/"
todo.md         M-1..M-5 checked off
```

Submodule commit d3b6005; backend commit 264470a.

## Session N — pipelines router (launch, monitor, resume, BYOP, promotion) — 2026-04-17

**What was built:** Full-fat replacement of the stub `pipelines` router —
eight endpoints covering launch, weblog callback, detail/paginated listings,
FAILED-gated resume, BYOP skeleton, and tier promotion — plus a new
`pipeline_config` module and a migration (`cea9c08543ee`) that adds six
operational tables.

**Key decisions:**

* **Fresh `run_id` and `pipeline_token` per launch.** `new_run_id()` returns
  `jp-<uuid4>` and `new_pipeline_token()` uses `secrets.token_urlsafe(32)`
  prefixed with `pt_`. The pair is stored on `pipeline_runs` and checked on
  every subsequent weblog / result callback via `hmac.compare_digest`. No
  user JWT on those endpoints — the token *is* the bearer.
* **Per-run isolation.** `work_dir_for(run_id)` → `gs://jackpot-work/{id}/work`,
  `result_uri_for(run_id)` → `gs://jackpot-results/{id}/`. Two runs never
  share a `workDir` prefix (Critical Rule 25). The Groovy config is
  generated fresh per run (Critical Rule 26), `resourceLabels` is populated
  every time (Critical Rule 27), and a slug of the lab name feeds the
  `jackpot_lab` label for GCP Billing attribution.
* **Compatibility check is data-driven, not hardcoded.** Rules live in
  `pipeline_catalog.compatibility_rules` JSONB. `source_types` +
  `required_scrub` emit hard blocks (422); `min_quality_status` + `organisms`
  emit soft warnings. Soft warnings return **202** with
  `code=SOFT_WARNINGS`; caller retries with `override_soft_warnings=true`
  to get 201. Hard blocks are never overridable.
* **Resume requires FAILED state and reuses the old `work_dir`.** New
  `run_id` + new `pipeline_token`, but `work_dir` is copied from the
  previous run so Nextflow `-resume` hits the existing task cache. A
  `pipeline_restarts` row links `new_run_id → previous_run_id` for
  auditability.
* **Promotion is gated by role, not by endpoint.** One endpoint
  (`POST /{catalog_id}/promote`) handles both project→lab (Lab Director)
  and lab→zoo (Platform Admin). Tier transition is strict: you can't
  skip from project to zoo in one call, and downgrades aren't allowed.
* **Local executor is a no-op.** `submit_to_batch()` returns a deterministic
  `batch-{run_id}` pseudo job id when `PIPELINE_EXECUTOR=local` so the launch
  flow is exercised end-to-end without actually starting Nextflow. Session Q
  wires up the real GCP Batch client.
* **Events pagination uses `received_at` (not `created_at`).** Added
  `received_at` to `ALLOWED_SORT_COLUMNS` in `backend/pagination.py`
  rather than aliasing or post-sorting client-side. Straightforward;
  no other table collides on that column name.

**Watch out for:**

* **`pipeline_events` / `pipeline_tasks` / `pipeline_files` were referenced
  by existing code (Session I) but didn't exist in the schema.** The old
  `receive_pipeline_event` wrapped DB writes in `try/except Exception` and
  silently swallowed the `UndefinedTable` error. Migration `cea9c08543ee`
  creates all six operational tables in one go; don't drop the try/except
  in the event handler until confirmed the migration has applied.
* **Soft-warning semantics are a 202, not a 200.** The response envelope's
  `success=false` with HTTP 202 is deliberate: the request is *accepted for
  further action* (confirming the override), not *completed*.
* **Non-admin tests rely on `MOCK_USER_EMAIL` swap.** The seed `<your-github-user>@...`
  is a Platform Admin, so negative access-control cases must create a
  throwaway user, `_switch_user` to that email, and clear `get_settings`
  cache. The `as_platform_admin` fixture reverts on teardown via pytest
  monkeypatch, so test ordering doesn't leak role state.
* **`pipeline_runs.sample_ids` is `INTEGER[]`, not `TEXT[]`.** The router
  accepts string `sample_id` values from clients (human-readable IDs like
  `AZ-001`) and translates to integer PKs before the INSERT — don't pass
  string arrays directly or PostgreSQL will reject them.
* **X-Pipeline-Token check uses `hmac.compare_digest`.** Not `==`. This is
  the standard timing-attack mitigation and must stay that way even if the
  token format changes.
* **BYOP stays UNVERIFIED.** The `POST /custom` endpoint writes a row and
  returns 202. Actual Nextflow fetch + schema verification is Month 3 — do
  not be tempted to shell out to `nextflow config` from the router.

**ASCII diagram — launch → monitor → results pipeline:**

```
POST /launch
  │  (pipeline_id, sample_ids, project_id, parameters)
  ▼
┌────────────────────────────────────────────────────────────┐
│ compute_pipeline_compatibility(catalog_row, samples)       │
│   ├── hard_blocks? → 422 INCOMPATIBLE_SAMPLES              │
│   └── soft_warnings? → 202 SOFT_WARNINGS (unless override) │
├────────────────────────────────────────────────────────────┤
│ new_run_id() + new_pipeline_token()                        │
│ work_dir_for(run_id)   → gs://jackpot-work/{id}/work       │
│ result_uri_for(run_id) → gs://jackpot-results/{id}/        │
│ generate_run_config(...)  ─► /tmp/jackpot_{run_id}.config  │
├────────────────────────────────────────────────────────────┤
│ INSERT pipeline_runs (status=QUEUED, pipeline_token,       │
│        work_dir, result_uri, parameters, soft_warnings)    │
│ submit_to_batch(...)  (no-op in local)                     │
│ log_audit(CREATE_PIPELINE_RUN)                             │
└────────────────────────────────────────────────────────────┘
  │
  │  Nextflow running on GCP Batch (or locally in dev)
  │
  ▼
POST /events (X-Pipeline-Token)                   ┌─ workflow.started   → status=RUNNING
  ├── hmac.compare_digest(token, run.token)       ├─ workflow.complete  → status=COMPLETED/FAILED
  ├── INSERT pipeline_events (raw JSONB)          │                        + load_pipeline_results
  └── route by event type ──────────────────────► ├─ process.*          → UPSERT pipeline_tasks
                                                  └─ process.failed     → run.status=FAILED

POST /{run_id}/results/{result_type} (X-Pipeline-Token)
  ├── RESULT_SCHEMAS[result_type] → Pydantic validation
  ├── INSERT <typed result table> (ON CONFLICT DO NOTHING)
  └── UPSERT pipeline_results metrics (jsonb merge)

GET /{run_id}                              POST /{run_id}/resume
  ├── _user_has_lab_access                   ├── previous.status == FAILED (400 otherwise)
  ├── run_dict (token stripped)              ├── new run_id + new token, REUSED work_dir
  ├── + recent_events (last 20)              ├── INSERT pipeline_restarts (new ↔ previous)
  └── + task_summary (status→count)          └── log_audit(RESUME_PIPELINE_RUN)

POST /custom               (Lab Director)    POST /{catalog_id}/promote
  └── project_pipelines            │              ├── project→lab : Lab Director
      status=UNVERIFIED            │              │    + UPDATE catalog tier/scope
      (Month 3: verify Nextflow)   │              │    + INSERT lab_pipelines
                                   │              └── lab→zoo    : Platform Admin
                                   │                   + UPDATE catalog tier=zoo
```

Backend delta:

```
backend/routers/pipelines.py                  full rewrite (~1040 lines, 8 endpoints)
backend/pipeline_config.py                    NEW — run_id/token/work_dir/config/submit_to_batch
backend/audit.py                              + CREATE/RESUME_PIPELINE_RUN,
                                                REGISTER_CUSTOM_PIPELINE, PROMOTE_PIPELINE
backend/config.py                             + pipeline_executor, jackpot_api_url,
                                                work_bucket, results_bucket, gcp_region
backend/pagination.py                         ALLOWED_SORT_COLUMNS += received_at
db/migrations/versions/cea9c08543ee_*.py      NEW — pipeline_events, pipeline_tasks,
                                                pipeline_files, pipeline_restarts,
                                                project_pipelines, lab_pipelines;
                                                +parameters/soft_warnings/catalog_id
                                                on pipeline_runs;
                                                +pipeline_uri/default_profile/
                                                 compatibility_rules/scope_* on catalog
tests/test_pipelines_router_api.py            NEW — 29 tests (launch, events, detail,
                                                pagination, resume, BYOP, promote)
```

Test delta: **486 → 515 passing tests** (+29); coverage 87.16% (≥60% threshold).

---

## Session O — sample_access router (2026-04-17)

### What shipped

- Four endpoints under `/api/v1/sample-access/`: `POST /requests`,
  `GET /requests`, `POST /requests/{id}/approve`, `POST /requests/{id}/deny`.
- `sample_access_grants` table: durable "read-unlock" artefact with
  `revoked` + `access_expires_at`, separated from the
  `sample_access_requests` conversation row.
- `can_access_sample()` / `visibility_sql_clause()` now honour
  unrevoked, unexpired grants **and** legacy `APPROVED` requests — no
  behaviour change for any existing sample endpoint.
- `run_access_request_job()` fully implemented: auto-approve at day 7,
  75-day-style warning 15 days before auto-approve, 7-day expiry
  warning, grant expiration, and "moot on sample-went-PUBLIC".

### Design: request row vs. grant row

The request row is the **conversation** — who asked, why, pending vs.
decided, who decided. The grant row is the **privilege** — who can read
what, until when. Splitting them means `can_access_sample()` answers in
one indexed lookup instead of re-deriving expiry from approval
timestamps. Revoking a grant does not rewrite history — the
`sample_access_requests` row stays `APPROVED`, the grant flips
`revoked=TRUE`, and the request transitions to `EXPIRED` only when the
backing grant is reclaimed by the expiry job. Audit stays clean.

### Backward-compat trick for `can_access_sample()`

Existing `tests/test_samples_router_api.py` inserts directly into
`sample_access_requests` with `status='APPROVED'` and no grant row. To
keep that fixture working without touching the test, the helper does
**both** in a single UNION ALL:

```sql
SELECT 1 FROM sample_access_grants
WHERE requester_id = :uid AND sample_id = :sid
  AND revoked = FALSE
  AND (access_expires_at IS NULL OR access_expires_at > NOW())
UNION ALL
SELECT 1 FROM sample_access_requests
WHERE requester_id = :uid AND sample_id = :sid
  AND status = 'APPROVED'
LIMIT 1
```

Because `_expire_grants()` also flips the linked request to `EXPIRED`,
the legacy fallback is self-healing: an APPROVED request *in the table*
is necessarily still active, so the OR doesn't leak stale access.

### Idempotency in the background job

All five sweep buckets run inside a single `with get_db() as db`
transaction — if any bucket raises, none commit, so a retry doesn't
double-fire warnings or half-expire grants. The approve-warning gate
uses `last_warning_sent_at IS NULL` (a one-shot), while the expiry
warning uses `last_warning_sent_at < access_expires_at - INTERVAL '7 days'`
so the column can be safely reused for the second warning without
losing the first-notification semantics.

### Pagination whitelist

`sample_access_requests` uses `requested_at`, not `created_at`, as its
timestamp column. The paginate() helper validates `sort_by` against a
central allow-list in `backend/pagination.py` — had to extend
`ALLOWED_SORT_COLUMNS` with `requested_at`, `approved_at`, `denied_at`,
`access_expires_at`, `status`. The router also translates the API's
default `sort_by=created_at` → `requested_at` so callers using the
generic default don't silently fall back to the whitelist's fallback.

### Test-fixture cleanup FK ordering

Five FK directions had to be handled before a user row can be deleted:

1. `lab_membership`, `project_membership` — direct DELETE.
2. `sample_access_requests.reviewed_by_id / approved_by_id / denied_by_id`
   — UPDATE ... = NULL (the request row lives on past the user).
3. `sample_access_grants.requester_id / granted_by_id` — DELETE.
4. `sample_access_requests.requester_id / owner_id` — DELETE (grants
   already gone).
5. `samples.owner_id` — for any sample the user happens to own, cascade
   the above two tables, then DELETE the sample, then DELETE the user.

The new `_cleanup_users()` helper encodes all five in one place so every
test can call it symmetrically in setup and teardown.

### Backend delta

```
backend/routers/sample_access.py              full rewrite (~500 lines, 4 endpoints)
backend/permissions.py                        _has_approved_access_request honours
                                                grants table + legacy APPROVED requests;
                                                visibility_sql_clause gains grants EXISTS
backend/jobs.py                               run_access_request_job implemented
                                                with 5 idempotent helpers
backend/audit.py                              + EXPIRE_ACCESS_GRANT, MOOT_ACCESS_REQUEST
backend/pagination.py                         ALLOWED_SORT_COLUMNS += requested_at,
                                                approved_at, denied_at,
                                                access_expires_at, status
db/migrations/versions/dc1d08fa8c41_*.py      NEW — +9 cols on sample_access_requests
                                                (justification, requested_duration_days,
                                                 auto_approve_after, access_expires_at,
                                                 approved_by_id/_at, denied_by_id/_at,
                                                 last_warning_sent_at);
                                                NEW table sample_access_grants;
                                                5 supporting indexes
tests/test_sample_access_router_api.py        NEW — 22 tests across create/list/
                                                approve/deny/can_access/job-sweep
pyproject.toml                                drop sample_access.py from coverage omit
```

Test delta: **515 → 537 passing tests** (+22); coverage 87.63%
(backend/routers/sample_access.py at 91%). All existing sample endpoint
tests continued to pass unchanged — the can_access_sample update was
purely additive.

---

## Session P — Streamlit researcher pages (9 pages + smoke tests) — 2026-04-17

**What was built:** Complete Streamlit researcher frontend under `frontend/` — 9 pages (dashboard, search, upload, data_entry, my_samples, datasets, access_requests, notifications, pipelines), a shared API client / session helpers / badge components, and a 12-test smoke suite that exercises every page import without a live Streamlit runtime. Net test delta: **537 → 549 passing tests** (+12), coverage 87.56%, still well above the 60% gate. Admin pages (lab_director, platform_admin, archive_requests, billing) are intentionally absent — Month 3 scope.

**Key decisions:**

- **Auto-discovery, not `st.navigation`.** Project pins streamlit==1.35.0; the explicit `st.Page`/`st.navigation` APIs landed in 1.36. Relying on Streamlit's filesystem page discovery (`frontend/pages/*.py` surfaces in the sidebar automatically) keeps us on the pinned version and saves an entrypoint rewrite when we eventually upgrade. `frontend/app.py` calls `main()` unconditionally at import time so auto-discovery still runs the landing page when Streamlit imports the module.
- **Envelope unwrap in the API client, not in every page.** `ApiClient.get/post/patch/delete` reads the `{success, data}` JACKPOT envelope and returns `body["data"]` directly; errors raise `ApiError(code, message, status_code)`. Page code never sees the wrapper. This keeps the pages from being littered with `["data"]` indexing and means the eventual FastAPI → real auth migration is a single-file change.
- **Test shim via `SimpleStreamlit`, not a headless browser.** `tests/test_streamlit_pages.py` installs a `sys.modules["streamlit"]` stub whose `__getattr__` returns a call-recording callable. Widgets return sensible defaults (text_input → `""` or supplied `value=`, checkbox → False, columns → list of shim instances, tabs/form/expander/container/sidebar → `_RecordingContext`). Pages import, their `render()` runs, and we assert `st.title` was called. Found two real bugs during test authoring: `with cols[i]:` failed because `columns()` returned plain `SimpleStreamlit` instances without context-manager protocol — fixed by adding `__enter__/__exit__` on the class itself (simpler than switching columns to a wrapper). No Playwright dependency, no browser, runs in 2s.
- **`FakeApiClient` with canned defaults for the common paths.** Rather than per-test fixtures, the fake has built-in defaults for `/users/me`, `/samples/`, `/samples/<id>`, `/sample-access/requests`, `/pipelines/`, `/pipelines/{id}/{tasks,events}`. This means a page smoke test doesn't need to know which endpoints a given page touches — it just imports and renders. Canned responses are keyed by `(method, path)` so specific tests can still override.
- **Two tiny backend additions for the frontend filters.** Added `owner_id` query parameter to `GET /samples/` (needed by dashboard and my_samples for "only mine") and a brand-new `GET /api/v1/pipelines/` list endpoint (needed by dashboard's active-runs panel). Both are small, spec-aligned additions rather than frontend-only workarounds. Also added `launched_at`/`completed_at` to `ALLOWED_SORT_COLUMNS` in `pagination.py` so pipeline lists sort cleanly. The pipelines router stays in the coverage omit list for now — its tests are in the Nextflow session.
- **Placeholder pages announce themselves.** `notifications.py` and `datasets.py` back Month 3 routers that don't exist yet. Both render an `st.info` banner explaining the deferral, call the final expected endpoint anyway, and gracefully treat `404`/`501`/NETWORK as an empty list — so the day the router ships, removing the banner is the only edit needed.
- **Post-submission edit warning is state-machine gated, not a second endpoint.** `data_entry.py`'s `_was_submitted()` checks `ncbi_submission_status`/`gisaid_submission_status`, `_submitted_warning()` compares the edited diff against `NCBI_GISAID_SENSITIVE_FIELDS`, and the save button won't fire the PATCH until the user has ticked an acknowledgement stored in `st.session_state["data_entry.ack_submitted"]`. Keeps backend simple — the guard is in the UI.
- **Selection persists across pagination.** `search.py` stores `search.selected_ids` as a `set` in `st.session_state`. Row checkboxes sync to the set (add on check, discard on uncheck); select-all-N uses the backend's `?select_all=true` path which returns IDs only. The action bar then reads from the same set, and `datasets.py` pulls the same session-state key for the cross-page hand-off.

**Watch out for:**

- **`with cols[i]:` needs a context-manager on the column object.** Streamlit's real `st.columns()` returns objects that implement `__enter__`/`__exit__`. The first run of the smoke tests failed on three pages with `'SimpleStreamlit' object does not support the context manager protocol`. If anyone later refactors `SimpleStreamlit` to return a narrower stub, put those two methods back — every page uses `with cols[i]:` somewhere.
- **`frontend/app.py` must call `main()` at import, not just under `__name__ == "__main__"`.** Streamlit's page loader imports the module; it never runs it as `__main__`. The current file guards both cases (`if __name__ == "__main__": main(); else: main()`) which is intentional belt-and-braces — don't "clean it up" without understanding that Streamlit never hits the `__main__` branch.
- **`my_samples.py` Edit button uses `st.switch_page("pages/data_entry.py")`** — available since Streamlit 1.30. If the pin ever drops below 1.30, swap to setting session state and asking the user to click Data Entry in the sidebar.
- **`sample-access` paths are hyphenated** (`/api/v1/sample-access/requests`), not underscored. Dashboard, access_requests page, and spec all agree, but I started to type `sample_access` multiple times — grep the page modules if a 404 shows up from the access-request panel.
- **`FakeApiClient._default()` has to match the shape each page expects, not just the backend's canonical envelope.** For example dashboard's access-requests panel accepts both list-shaped and `{results: [...]}` responses; the fake returns a bare list to exercise that fallback path. If a real endpoint changes shape, update both the fake defaults and the page's defensive handling in lockstep.
- **Coverage omit list already excludes pipelines/notifications/datasets.** Running `pytest` locally still shows 87.56% even though three of this session's routers aren't counted — that's by design (stub routers). Don't remove them from the omit list in `pyproject.toml` until their routers are fully implemented.

**ASCII diagram — page → session → API → backend:**

```
      frontend/pages/<page>.py  (thin display layer, no business logic)
              │
              │ get_client()
              ▼
   frontend/lib/api.ApiClient  ──────────── ApiError(code, msg, status)
        │            │                              ▲
        │            │  POST/GET with               │
        │            │  X-Mock-User-Email header    │
        │            ▼                              │
        │   httpx.Client  ─── JACKPOT envelope ─────┘
        │                     {success, data} / {success, error}
        │
        └── unwraps body["data"], returns plain dict / list to the page

   frontend/lib/session  caches /users/me under session_state["_jackpot_me"]
                         (my_user_id / is_platform_admin / my_director_lab_ids)

   tests/test_streamlit_pages.py
        monkeypatch sys.modules["streamlit"] → SimpleStreamlit   (records calls)
        monkeypatch api_mod.get_client       → FakeApiClient      (canned data)
        importlib.import_module(page)        → render() runs      (asserts st.title)
```

**File inventory:**

```
frontend/__init__.py                          NEW — package marker
frontend/lib/__init__.py                      NEW — package marker
frontend/components/__init__.py               NEW — package marker
frontend/pages/__init__.py                    NEW — package marker
frontend/app.py                               NEW — Streamlit entrypoint
frontend/lib/api.py                           NEW — ApiClient + ApiError + get_client
frontend/lib/session.py                       NEW — /users/me cache + role helpers
frontend/components/badges.py                 NEW — tier/sharing/scrub/run_status
frontend/pages/dashboard.py                   NEW — 3-panel researcher home
frontend/pages/search.py                      NEW — filter sidebar + bulk select
frontend/pages/upload.py                      NEW — drag-drop ingest + scrub skip
frontend/pages/data_entry.py                  NEW — guided edit + submit warning
frontend/pages/my_samples.py                  NEW — scope-filtered owner view
frontend/pages/datasets.py                    NEW — Month 3 placeholder
frontend/pages/access_requests.py             NEW — my/incoming tabs
frontend/pages/notifications.py               NEW — Month 3 placeholder
frontend/pages/pipelines.py                   NEW — launch + 4-tab monitor + resume
backend/routers/samples.py                    +owner_id filter param
backend/routers/pipelines.py                  +GET /api/v1/pipelines/ list endpoint
backend/pagination.py                         +launched_at/completed_at sort cols
tests/test_streamlit_pages.py                 NEW — 12 smoke tests
```

Test delta: **537 → 549 passing tests** (+12); coverage 87.56%. The 9 pages load cleanly, react to the stub API without exceptions, and the ApiClient/envelope/badge units pass their isolated tests. Full end-to-end (Playwright) is Month 3 per spec.md line 702 — not blocking for Month 2 sign-off.

---

## Session Q: GCP staging IaC (jackpot-iac) — 2026-04-16

**What was built:** Full Infrastructure-as-Code scaffold for the JACKPOT staging environment in a separate `jackpot-iac` repo — 7 reusable Terraform modules (network, cloud-sql, gke, gcs-buckets, artifact-registry, iam, secrets), thin staging wrapper + production stub, Helm chart `jackpot-api` with pre-upgrade Alembic migration Job, GitHub Actions `deploy-staging.yml` with Workload Identity Federation auth, idempotent `bootstrap_project.sh` for one-time GCP setup, `staging_smoke_test.sh` gate, and `docs/staging_access.md` + `docs/production_runbook.md` stub. 5 logical commits (Q-1 through Q-3, Q-6, Q-7) — Q-4 (`terraform apply`) and Q-5 (Cecret E2E) are intentionally left for manual execution because they create billable resources.

**Key decisions:**

- **Split Session Q scope from the user's original framing.** The original ask bundled `terraform apply` and a real Cecret E2E run into the autonomous pass, plus a `month-2-complete` tag at the end. I pushed back: applying is a billable, side-effecting action against a real GCP project, and tagging before post-apply verification is dishonest. The agreed split is what's reflected in the 5 commits — file work only — with Q-4/Q-5 operated manually and Q-8 gated on that confirmation.
- **Zero hardcoded values in modules.** Every `project_id`, `region`, `environment`, bucket name, SA email, and secret name derives from `var.project_id` / `var.region` / `"jackpot-${var.environment}-<purpose>"`. The staging wrapper is thin (50 lines of module calls); the production wrapper is a commented-out twin of staging with Month 3 TODOs — production stands up by uncommenting blocks and filling tfvars, not by editing module code.
- **Canonical naming authority lives in jackpot-backend, not jackpot-iac.** `jackpot-backend/docs/gcp_context.md` is the single source of truth for project IDs, regions, bucket naming, and SA emails. The jackpot-iac README points to it explicitly. This avoids two-repo naming drift — change the doc first, mirror into tfvars.
- **State bucket chicken-and-egg solved via a separate script.** Terraform's GCS backend needs `jackpot-staging-tfstate` to exist *before* `terraform init` runs. `scripts/bootstrap_project.sh` creates it via `gsutil` (plus enables 16 APIs, creates the deploy SA, and sets up Workload Identity Federation for GitHub Actions) as an idempotent pre-step. This keeps the state bucket out of the Terraform graph entirely.
- **Credentials to GitHub Actions via WIF, not SA JSON keys.** The bootstrap script creates a Workload Identity Federation pool + OIDC provider scoped to `example-org` repos. GHA exchanges its OIDC token for a short-lived GCP access token — no long-lived keys stored in repo secrets. The workflow's `id-token: write` permission is what authorizes the exchange.
- **Alembic migrations run as a Helm pre-upgrade Job, not an initContainer.** The migration Job uses `helm.sh/hook: pre-install,pre-upgrade`, which means the Deployment never rolls forward until `alembic upgrade head` exits 0. Using an initContainer would run migrations on every pod startup (race condition across replicas) rather than once per release.
- **ConfigMap checksum annotation forces rolling restart on env changes.** `checksum/config: {{ include "configmap.yaml" . | sha256sum }}` in the Deployment's pod template annotations means any ConfigMap edit changes the pod spec hash, which triggers a rolling update. Without this, env-var-only changes would not restart pods.
- **Secret Manager is metadata-only; values seeded post-apply.** The secrets module creates `google_secret_manager_secret` resources but no versions. After `terraform apply`, the operator runs the `terraform output secret_seed_commands` list to add real values. This keeps actual credentials out of Terraform state and the repo. Per-secret `roles/secretmanager.secretAccessor` bindings target the jackpot-api GSA specifically — tighter than the project-wide role.
- **Three node pools, each tuned to its workload.** api-pool (n2-standard-4, 1-3 nodes, on-demand) runs the FastAPI Deployment and Nextflow controllers; workspace-pool (n2-standard-8, 0-2, on-demand) for JupyterHub Month 3; scrubber-pool (n2-highmem-4, 0-3, spot) for SRA Human Scrubber Jobs. Workspace and scrubber pools carry `workload=` taints so only the matching pods schedule there. Scale-to-zero on both cold pools — cluster autoscaler brings them up on demand.
- **Bucket policy encoded per bucket.** sequences/references: versioning on; work: 90-day lifecycle, no versioning (per CLAUDE.md rule 38); backups: different region + Object Lock retention policy + 90-day lifecycle; staging: 30-day lifecycle (temporary pre-scrub). No versioning on work avoids fighting the lifecycle rule.
- **Secret short-names double as env-var keys.** The secrets module's default list (`secret-key`, `database-url`, `google-oauth-client-id`, …) is chosen so each short-name upper-cases into the env var the backend reads (`SECRET_KEY`, `DATABASE_URL`, `GOOGLE_OAUTH_CLIENT_ID`). The deploy workflow iterates the list and synthesizes `kubectl create secret generic --from-literal=$K=$V` without a manual mapping table.

**Watch out for:**

- **GPG signing is not configured in the jackpot-iac repo.** The baseline commit `f9a0e20` is unsigned. My first attempt at `git commit -c commit.gpgsign=true` failed with "gpg failed to sign the data" because no signing key is in this repo's config. Dropped the flag; subsequent commits are unsigned to match the repo's existing style. If we want signed commits, configure `user.signingkey` in the jackpot-iac repo first.
- **`gac` alias does not work in jackpot-iac.** `gac` runs `uv run ruff check --fix . && uv run ruff format .` before committing — there's no `pyproject.toml` in jackpot-iac, so ruff fails immediately. Use plain `git commit` in this repo. The `gac` alias is specific to jackpot-backend.
- **backend/config.py's bucket env var names do not match CLAUDE.md's canonical bucket list.** config.py expects `STORAGE_BUCKET_SEQUENCES`, `_RAW`, `_STAGING`, `_DATASETS`, `_SUBMISSIONS`; CLAUDE.md canonicalizes `sequences`, `references`, `results`, `staging`, `work`, `backups`. I resolved this by mapping `_RAW`→staging, `_DATASETS`→references, `_SUBMISSIONS`→portal-exports in `values-staging.yaml`. The clean fix is to rename the config fields in a follow-up — out of scope for Session Q.
- **`master_authorized_networks` defaults to empty (open endpoint).** This is fine for staging during initial bring-up but MUST be populated with the office/home/GHA NAT CIDRs before the project is promoted to production. The production tfvars.example flags this as a pre-apply requirement.
- **Production stub is copy-edit-tfvars, not rewrite — but you still must uncomment the module blocks.** `terraform/production/main.tf` and `outputs.tf` have all module blocks commented out. When activating production: fill in tfvars, uncomment the main.tf blocks, uncomment the matching outputs, then `terraform apply`. Keeping them commented prevents `plan` from erroring on an empty `project_id`.
- **Alembic migration Job name embeds image tag.** `{release}-migrate-{image.tag | trunc 20}` — if the same image tag is redeployed, the Helm pre-upgrade hook deletes the previous Job (hook-delete-policy: `before-hook-creation`), then recreates it. Safe for idempotent redeploys; beware if image.tag ever contains characters Kubernetes names reject (the template normalises underscores to dashes but doesn't escape other specials).
- **Deploy workflow checks out `<your-org>/jackpot-backend` at ref `staging`.** The cross-repo checkout uses the default GITHUB_TOKEN — if that token lacks read access to jackpot-backend, the workflow fails at the second `actions/checkout` step. If the repos are in the same org this works out of the box; otherwise a PAT with `contents:read` on jackpot-backend must be put in repo secrets and swapped in.
- **`terraform fmt`/`terraform validate`/`helm template` were NOT run locally.** Neither tool is installed on this workstation. CI or the first `terraform init && plan` will surface any HCL issues I missed. Validate modules before the first real apply: `cd terraform/staging && terraform init -backend=false && terraform validate`.

**ASCII diagram — deploy-staging flow:**

```
  git push origin staging
         │
         ▼
  GitHub Actions: deploy-staging.yml
         │
         ├─ checkout jackpot-iac
         ├─ checkout jackpot-backend @ staging
         │
         ├─ google-github-actions/auth
         │     │  OIDC token  →  projects/…/locations/global/workloadIdentityPools/
         │     │                   jackpot-staging-gh-pool/providers/github
         │     ▼
         │  short-lived access token for jackpot-staging-deploy@… SA
         │
         ├─ docker build + push jackpot-api:$(git rev-parse --short HEAD)
         │     → us-central1-docker.pkg.dev/<project>/jackpot/jackpot-api
         │
         ├─ get-gke-credentials (jackpot-staging-gke, us-central1)
         │
         ├─ gcloud secrets versions access latest × 5
         │     → kubectl create secret generic jackpot-api-secrets --from-literal …
         │
         ├─ helm upgrade --install jackpot-api ./helm/jackpot-api
         │     ├─ pre-upgrade hook:  Job  alembic upgrade head      (must succeed)
         │     └─ rolls:             Deployment  2 replicas on api-pool
         │                           ConfigMap (env + buckets)
         │                           Service (ClusterIP :80 → pod :8000)
         │                           ServiceAccount (WI annotation → jackpot-api GSA)
         │
         └─ ./scripts/staging_smoke_test.sh
               ├─ /health = 200 status=ok
               ├─ /openapi.json = 200
               └─ /api/v1/samples/ = 401/403 (auth gate works)
```

**File inventory (jackpot-iac, 43 files across 5 commits):**

```
Q-1 (commit 8151d3e): Terraform modules + staging root + production stub
  .gitignore                                             NEW
  README.md                                              EDIT — layout + bootstrap + env table
  scripts/bootstrap_project.sh                           NEW — 1-time GCP setup, WIF, state bucket
  terraform/modules/network/{main,variables,outputs}.tf  NEW — VPC, subnet, router, NAT, PSC
  terraform/modules/cloud-sql/{...}.tf                   NEW — Postgres 16, private IP, PITR, daily backups
  terraform/modules/gke/{...}.tf                         NEW — private cluster + 3 node pools
  terraform/modules/gcs-buckets/{...}.tf                 NEW — 7 buckets w/ versioning/lifecycle/Object Lock
  terraform/modules/artifact-registry/{...}.tf           NEW — Docker repo
  terraform/modules/iam/{...}.tf                         NEW — 3 GSAs + WI bindings + bucket/AR IAM
  terraform/staging/{providers,backend,variables,main,outputs}.tf + tfvars.example   NEW
  terraform/production/{...}.tf + tfvars.example         NEW — commented-out stub

Q-2 (commit 6131563): Secret Manager
  terraform/modules/secrets/{main,variables,outputs}.tf  NEW — metadata-only secrets
  terraform/staging/main.tf                              EDIT — wire up secrets module
  terraform/staging/outputs.tf                           EDIT — export secret_seed_commands

Q-3 (commit ab755ca): Helm chart + deploy pipeline
  terraform/modules/secrets/variables.tf                 EDIT — rename short-names to match env vars
  helm/jackpot-api/Chart.yaml                            NEW
  helm/jackpot-api/values.yaml                           NEW — defaults
  helm/jackpot-api/values-staging.yaml                   NEW — staging overrides
  helm/jackpot-api/templates/_helpers.tpl                NEW
  helm/jackpot-api/templates/serviceaccount.yaml         NEW — WI annotation
  helm/jackpot-api/templates/configmap.yaml              NEW — env + bucket vars
  helm/jackpot-api/templates/deployment.yaml             NEW — configmap checksum annotation
  helm/jackpot-api/templates/service.yaml                NEW — ClusterIP
  helm/jackpot-api/templates/job-migrations.yaml         NEW — Helm pre-upgrade hook
  .github/workflows/deploy-staging.yml                   NEW — WIF → build → push → migrate → helm

Q-6 (commit 5a46d9a): Smoke test
  scripts/staging_smoke_test.sh                          NEW — /health, /openapi, auth gate, --check-kube, --check-buckets

Q-7 (commit dcf95fd): Docs
  docs/staging_access.md                                 NEW — endpoints, access, seed, redeploy, logs, rollback
  docs/production_runbook.md                             NEW — Month 3 stub
  docs/.env.staging.example                              NEW — backend env var surface for staging
```

Next up (manual, user-operated): Q-4 = `terraform apply` + `gcloud secrets versions add` + first Helm deploy; Q-5 = end-to-end Cecret run through staging. Q-8 (git tag `month-2-complete`) is gated on both.

# Session 5 — First staging deploy (2026-04-17 evening)

**Paste this as the next entry in `docs/learnings.md`.** Style-matched to
the existing entries — prose-heavy, chronological, failure-first.

---

## Q-4 continuation + Q-5 smoke: First GCP staging deploy to green

Session 5 was meant to be a quick final step — push `jackpot-iac:staging`
and watch the workflow run. What it actually became was a marathon
debugging run chasing ten distinct root causes from ConfigMap format
through to corrupted secrets. The staging API is live and green at
session end. The path to get there was instructive, and each failure
mode is worth capturing for the next deploy in a new environment.

### Ten root causes in one session

The failures stacked. Each fix uncovered the next layer:

1. **`cors_origins` Pydantic JSON-parse.** Alembic migration Job died
   before touching the database. `cors_origins: list[str]` + a plain
   ConfigMap string value = `JSONDecodeError`. Fixed tactically by
   encoding `CORS_ORIGINS` in values-staging.yaml as a JSON-array
   string. Permanent fix (backlog P0.2) uses `Annotated[list[str],
   NoDecode]` + `field_validator` to accept multiple forms.

2. **Wrong DB name in `DATABASE_URL`.** Cloud SQL had `jackpot_db`.
   Secret Manager had `/jackpot` — someone followed
   `docs/staging_access.md` too quickly and dropped the `_db`. Fixed
   with `gcloud secrets versions add`. Backlog P1.1 makes Terraform
   own this Secret end-to-end.

3. **Alembic chain assumes `init.sql` pre-loaded.** Flagged in the code
   audit as WEAK-3. Migration 2 does `ALTER TABLE samples` where
   `samples` was created in `db/init.sql` — which runs in Docker Compose
   via the postgres entrypoint but doesn't run anywhere in GCP. Fixed
   with a one-off bootstrap Job (postgres:16-alpine image loads
   init.sql via a shared emptyDir volume, then jackpot image stamps
   Alembic at `a7fd1fcccb77`). Permanent fix (backlog P0.1) is a
   baseline migration containing the DDL.

4. **`jackpot-nf` submodule URL was a filesystem path.**
   `.gitmodules` said `url = /Users/glen/jackpot/jackpot-nf`.
   Worked on the Mac. Failed everywhere else. `jackpot-nf` hadn't been
   pushed to GitHub at all. Pushed to `<your-org>/jackpot-nf`, fixed the
   URL, matched the `schema` submodule pattern.

5. **`Dockerfile.api` didn't `COPY nf/`.** Even after the submodule was
   accessible, the image still didn't include the directory. `pipelines.py`
   does `sys.path.insert(0, "../nf")` at import time, so the entire
   FastAPI app crashed at startup with `ModuleNotFoundError: No module
   named 'shared'`. Fixed with a single COPY line. Permanent fix
   (backlog P0.3) moves `RESULT_SCHEMAS` into the backend package.

6. **Workflow didn't checkout submodules recursively.** Added
   `submodules: recursive` to `actions/checkout@v4`. But first we had
   to accidentally duplicate the line (fix #7 below).

7. **Duplicate YAML key.** The Python heredoc that applied the previous
   patch ran twice, producing `submodules: recursive` on two adjacent
   lines. PyYAML accepted it (last-wins on duplicate keys). GitHub
   Actions rejected it — 0s elapsed failure with every step showing
   `-`. Removed the duplicate. Lesson: `yaml.safe_load` is not a
   workflow linter.

8. **Submodule PAT auth dance.** With recursive submodules enabled, the
   checkout step got 403 on both `jackpot-nf` and `jackpot-schema`.
   Initial theory was missing PAT permissions (was actually right —
   that PAT was invalid, see #9). Working solution regardless: split
   the checkout into two steps, inject the PAT via git's `insteadOf`
   URL rewrite right before `git submodule update --init --recursive`,
   scrub it after.

9. **`CROSS_REPO_PAT` was actually a Google OAuth client secret.** The
   nastiest surprise. After fixing all the auth logic, a diagnostic
   step printed `PAT prefix: GOCSPX-j...` — which is a Google OAuth
   client secret prefix, not a GitHub PAT prefix. The secret had been
   overwritten during unrelated Secret Manager work a few hours
   earlier. `gh secret set CROSS_REPO_PAT` with the real PAT fixed it.

10. **Helm release stuck at `pending-upgrade`.** One of the earlier
    failed deploys had timed out under `--wait`, which doesn't
    auto-rollback. Revision 9 was stuck at `pending-upgrade`, blocking
    all subsequent upgrade attempts. Manual `helm rollback jackpot-api
    8` got it back to a `deployed` state; the next upgrade succeeded.

Final smoke-test failure (cosmetic only): the placeholder URL
`api.staging.jackpot.example.org` doesn't resolve anywhere. Rewired the
workflow's smoke test step to use `kubectl port-forward` against the
in-cluster Service. Green.

End state: Helm revision 12, STATUS `deployed`, 2/2 API pods Ready,
`/health` returns DB connected. All five Alembic migrations applied.

### The actionable takeaways

Seven things worth changing in the codebase or process based on
Session 5. Numbered to match the new TODO priority list:

- **P0.1** Alembic baseline migration so `upgrade head` works from
  empty.
- **P0.2** `cors_origins` validator for multi-format env input.
- **P0.3** Move `RESULT_SCHEMAS` out of `nf/` so `pipelines.py` doesn't
  need sys.path manipulation.
- **P1.1** Terraform-owned `DATABASE_URL` Secret.
- **P1.3** Public Ingress + DNS + cert for staging (unblocks real
  smoke test + OAuth).
- **P1.4** `helm upgrade --atomic` or auto-rollback.
- **P1.5** GitHub Actions Node 24 migration.

### The new operational doc

`docs/staging_access.md` was written during Q-7 but was mostly a stub.
After Session 5 it's the canonical staging runbook — deploy flow, DB
access, secret rotation, and the troubleshooting patterns discovered
for every one of the ten failure modes above. Including the bootstrap
Job YAML for fresh environments (until P0.1 lands).

Next up: run `local_test_checklist.md` on the laptop before any new GCP
activity. Then land P0.1 + P0.2 + P0.3 as three quick PRs. Then resume
the original router implementation plan (organizations → labs → users
→ ...).

## Q-9 — Alembic baseline migration (2026-04-24)

Closed the bootstrap gap. `alembic upgrade head` now builds the full
schema from an empty database via baseline revision `5adf11b77c19`.
The bootstrap Job and the postgres entrypoint mount are gone.

### Three things worth recording

- **Critical Rule numbering already had a 42 and a 44.** The Q-9
  task description said "Add Critical Rule 42" but rule 42 was
  already taken (Templates) and rule 44 already specified the
  empty-DB invariant — pointing at Q-9 as the open backlog. The
  resolution: append a new rule 52 with the verbatim text
  ("Alembic is the single source of truth"), and amend rule 44 to
  drop the bootstrap-Job paragraph and the "until Q-9 lands"
  caveat. When closing a backlog item, audit the rule that named
  it — odds are it needs an edit too. Bumped the "all 51 Critical
  Rules apply" line to 52.

- **conftest.py double-bootstrap was load-bearing dead weight after
  Q-9.** Pre-Q-9, conftest read `db/init.sql` then ran `alembic
  upgrade head` because the chain assumed the init.sql DDL existed.
  Post-Q-9, the alembic chain is self-sufficient — the init.sql
  load was actively misleading because it implied tests were proving
  something they weren't (production runs alembic alone). Dropping
  the load makes tests exercise the same path production uses.
  When you fix a chain to be self-sufficient, hunt for the test
  scaffolding that compensated for the gap and remove it too —
  otherwise the test suite still passes for the wrong reason.

- **The Helm "bootstrap Job" was never a chart template.** The
  Q-9 description implied there was a chart manifest to delete,
  but a search of `jackpot-iac/helm/jackpot-api/templates/` turned
  up only `job-migrations.yaml` (the canonical pre-upgrade alembic
  Job). The "bootstrap" was an inline `kubectl apply` heredoc
  living entirely inside `docs/staging_access.md §6`. The fix was
  to replace §6 with a one-time `alembic stamp 5adf11b77c19`
  instruction for environments deployed pre-Q-9. No cross-repo
  changes needed. When a task says "delete X from the chart",
  verify X actually lives in the chart before deleting anything.

## Q-10 — cors_origins multi-form validator (2026-04-24)

Closed the JSON-array-only constraint on `Settings.cors_origins`. The
field now accepts JSON arrays, comma-separated strings, empty strings,
`None`, and real lists via `Annotated[list[str], NoDecode]` + a
`mode="before"` validator. Reverted staging's `values-staging.yaml` to
plain comma-separated. Same Rule 45 ↔ Rule 53 split we did for
Rule 44 ↔ Rule 52 in Q-9.

### Three things worth recording

- **`NoDecode` requires pydantic-settings ≥2.3.0; the repo was
  pinned at 2.2.1.** The fix pattern documented in old Rule 45
  imports `NoDecode` from `pydantic_settings`, which only exists in
  2.3.0+. Closing Q-10 forced a dependency bump
  (`pydantic-settings>=2.3.0,<3`, resolved to 2.14.0). Whenever a
  documented "fix pattern" cites a symbol, sanity-check that the
  symbol is reachable from the pin set before closing the backlog
  item — otherwise the rule is aspirational, not actual.

- **Stale venv shebangs hide as test-fixture failures.** First test
  run after the dep bump exploded with
  `ImportError: cannot import name 'NoDecode'` even though
  `uv run python -c 'import pydantic_settings; ...'` proved the
  symbol was reachable. Root cause: every script in `.venv/bin/`
  had a shebang pointing at a sibling checkout's Python
  (`/Users/glen/...` instead of `/Users/glen/...`). When
  conftest.py ran `subprocess.run(["uv", "run", "alembic", ...])`,
  alembic loaded the wrong Python and saw the OLD pydantic_settings.
  Fix: `rm -rf .venv && uv sync`. Lesson: when an import error
  cites a `site-packages` path that isn't your CWD's venv, the
  venv's bin/ shebangs are stale; recreate the venv. `uv sync`
  alone won't rewrite shebangs of already-installed scripts.

- **Two tests per shape — once via constructor, once via env
  var — proves both the validator AND `NoDecode` work.** The
  constructor tests (`Settings(cors_origins="...")`) prove the
  validator's parsing logic. But pre-Q-10, the env-var path
  (`monkeypatch.setenv("CORS_ORIGINS", "...")` + `Settings()`)
  would have crashed at `json.loads()` BEFORE the validator could
  run, because pydantic-settings auto-decoded `list[*]` fields.
  Only the env-var test proves `NoDecode` is doing its job. If you
  ever add another `list[*]` Settings field, mirror this two-axis
  test pattern — `tests/test_config.py` is the template.

## Q-11 — Vendor RESULT_SCHEMAS into backend (2026-04-24)

Closed the cross-repo sys.path hack. `backend/routers/pipelines.py`
now imports `RESULT_SCHEMAS` from `backend.pipeline_schemas`, a
10-file package vendored from `nf/shared/schemas/` and kept in sync
via explicit code review. `Dockerfile.api` no longer `COPY nf/`s, and
a new `.dockerignore` excludes `nf/` from the build context.

### Three things worth recording

- **`.dockerignore` is build-context-wide, not Dockerfile-specific.**
  My first draft excluded `frontend/` on the theory that it was only
  needed by `Dockerfile.ui`. Wrong: `.dockerignore` applies to every
  build that uses the same context. The first compose rebuild blew
  up immediately with `target ui: failed to compute cache key ...
  "/frontend": not found`. Fix: drop `frontend/` from `.dockerignore`
  and leave a comment explaining the rule. Lesson: when sharing a
  build context across multiple Dockerfiles (the compose pattern),
  `.dockerignore` entries must be the intersection of what every
  Dockerfile DOESN'T need, not the union of what each one
  individually doesn't need.

- **Layout-preserving vendor beats flatten-into-one-module.** The
  user's plan offered two options: copy `nf/shared/schemas/` as a
  10-file package vs. flatten into a single
  `backend/pipeline_schemas.py`. Picked the package layout (10 files,
  not 1) because future schema changes on the nf side now diff
  cleanly file-for-file against the vendored copy. The
  flatten-into-one approach would force a manual re-merge every time
  any single schema changed upstream. Cost of the package layout: 9
  extra files in git. Benefit: trivial future syncs.

- **Pyright LSP reported a stale "import could not be resolved"
  error after the new package was created; the CLI Pyright run was
  clean.** First sign that the LSP cache hadn't picked up the new
  package directory yet — the file existed on disk but the LSP's
  workspace index was stale. `uv run pyright backend/routers/pipelines.py`
  reported `0 errors`. Treat new-package LSP misses as cache lag,
  not a real bug — verify with the CLI before chasing.

## UI-B — Upload page triage (2026-04-24)

Reframed from "browser walkthrough" to "backend-contract verification

+ page-code review" because this session has no headless-browser
  tooling. Drove every payload the page would send via curl, verified
  the API contract for each happy/error path, and read
  `frontend/pages/upload.py` + `frontend/lib/api.py` to confirm the
  error-rendering plumbing handles each path. Surfaced two real backend
  bugs and fixed both at root.

### Page surface inventory (current Upload page MVP)

| Expected field per UI-B task                          | Status                                                 |
| ----------------------------------------------------- | ------------------------------------------------------ |
| Sample type selector                                  | PRESENT (Human/Animal/Vector/Wastewater/Environmental) |
| Sector                                                | PRESENT but MANUAL — not auto-derived from source_type |
| Tier selector with descriptions                       | MISSING — only a live "estimated tier" badge           |
| Organism name                                         | PRESENT (free text — no autocomplete/dropdown)         |
| Collection country                                    | PRESENT (free text)                                    |
| Collection state + admin units                        | MISSING (only country)                                 |
| Date collected (year-only tolerance UI)               | PARTIAL — `st.date_input` forces a full date           |
| Host species                                          | MISSING                                                |
| Host age                                              | MISSING                                                |
| Host sex                                              | MISSING                                                |
| Isolation source                                      | MISSING                                                |
| Sequencing lab DROPDOWN from /api/v1/sequencing-labs/ | MISSING — free text input                              |
| Project DROPDOWN from /api/v1/projects/               | MISSING — `st.number_input` for project_id             |
| FASTQ R1/R2 file upload                               | PRESENT                                                |

The page is a working MVP: it relays metadata + files to the ingest
endpoint, surfaces the validator's tier on the response, and handles
errors via the ApiClient envelope. It is NOT the full-featured form
the UI-B task description envisaged. Recommend opening **UI-B2** for:
sequencing-lab + project dropdowns, sector auto-derivation, host
fields, isolation source, organism autocomplete, year-only date
tolerance UI.

### Per-scenario status

All scenarios driven via `curl POST /api/v1/ingest/upload` against
the live local stack with the mock identity (the maintainer, Platform
Admin, Example-Lab director). "Contract verified" = API returned
the expected envelope and the page-code review confirms `upload.py`
will render it via `st.error(f"Upload failed: {exc.message}")`.

| Step | Scenario                                     | Status                                                       |
| ---- | -------------------------------------------- | ------------------------------------------------------------ |
| 3    | GET /api/v1/sequencing-labs/ → 3 seeded labs | CONTRACT VERIFIED (Example Sequencing Lab, Example Reference Lab, Example Lab) |
| 3    | GET /api/v1/projects/ → ≥1                   | CONTRACT VERIFIED (Dev Project)                              |
| 4    | POST /api/v1/ingest/upload happy path        | CONTRACT VERIFIED — 201, sample_id returned, quality_status=PRELIMINARY, sector=clinical, scrub_status=PENDING |
| 5    | GET /api/v1/samples/{integer-id} retrieves   | CONTRACT VERIFIED. Note: endpoint requires the integer DB id, not the string sample_id — UI must capture `data.id` from the upload response |
| 5    | audit_log row written                        | CONTRACT VERIFIED (action=CREATE_SAMPLE, resource_type=sample) |
| 6    | Missing host_age (Tier 3 field) → 422        | NOT TRIGGERED — host_age is optional per current validator. The UI-B task description expected a Tier 3 requirement, but `validate_sample()` doesn't enforce it. Documented for product-owner review |
| 7    | CSV body named .fasta → 400                  | CONTRACT VERIFIED **after fix** — `Upload failed: fake.fasta has extension .fasta but its content could not be recognised as any known format. ...` |
| 8    | Gzipped CSV named .fastq.gz → 400            | CONTRACT VERIFIED **after fix** — same human-readable message, `_read_first_bytes` decompressed gzip first |
| 9    | Missing organism_name (BASE_REQUIRED) → 422  | CONTRACT VERIFIED — `Upload failed: Missing required field: organism_name` |
| 10   | Invalid enum value                           | FORECLOSED by UI — source_type/sharing/sector are all `st.selectbox`, can't pick an out-of-range value from the page |

### Bugs found and fixed

**Bug 1: file content vs extension validation skipped on upload.**

- **Symptom**: a CSV body uploaded as `fake.fasta` was accepted
  (returned 201 with the CSV staged into MinIO under a `.fasta` URI).
  Step 7 of the UI-B walkthrough was supposed to trigger this and
  didn't.
- **Root cause**: `backend/routers/ingest.py:upload()` called
  `detect_files()` on filenames but never invoked the existing
  `validate_file_type()` function from `backend/file_detector.py`,
  which IS the content-vs-extension sniffer (handles gzip
  transparently).
- **Fix** (`backend/routers/ingest.py:367-388`): for each uploaded
  file, write its bytes to a `tempfile.TemporaryDirectory` with the
  original filename, then call `validate_file_type(tmp_path)` before
  staging. `FileDetectorError` → `HTTPException(400, detail=str(exc))`
  which the new envelope handler wraps as
  `{"success": false, "error": {"code": "HTTP_400", "message": "..."}}`.
- **Regression tests**: `test_upload_rejects_csv_renamed_to_fasta`
  + `test_upload_rejects_gzipped_csv_renamed_to_fastq_gz` in
    `tests/test_ingest_api.py`. Cover both the bare-extension case and
    the gzip-peek case.

**Bug 2: HTTPException-based errors bypass the JACKPOT envelope.**

- **Symptom**: validator failures returned the raw FastAPI shape
  `{"detail": {"errors": [...], "warnings": [...], ...}}`. The
  ApiClient at `frontend/lib/api.py:141-147` looks for
  `body["error"]["message"]`; none present, so `err = {}`,
  `err.get("message")` is None, falls back to
  `resp.text` which is the entire JSON dump. The user would see
  `Upload failed: {"detail":{"errors":["Missing required field..."]}}`
  in the Streamlit toast — Critical Rule 24 violation.
- **Root cause**: `ingest.py` (14 raises), `samples.py` (16),
  `dataharmonizer.py` (3 — using raw `JSONResponse` instead of the
  helper), and a few others use FastAPI's `HTTPException` instead of
  `responses.error()`. Per-router rewrite is too invasive for this
  scope.
- **Fix** (`backend/main.py:117-160`): one global
  `@app.exception_handler(HTTPException)` that converts all
  HTTPException raises to the JACKPOT envelope (string detail →
  `error.message`, dict detail → `error.message` from first error
  entry + full structure preserved in `error.detail`). Plus a
  `RequestValidationError` handler so FastAPI's auto-422s also use
  the envelope (path/body validation errors get a clean string
  message like `"path.sample_id: Input should be a valid integer"`).
- **Also fixed**: `backend/routers/dataharmonizer.py` was using raw
  `JSONResponse({"detail": ...})` — replaced with `error()` helper
  for consistency (the global handler doesn't intercept this since
  it's not an HTTPException).
- **Regression tests**:
  `test_validation_error_uses_jackpot_envelope` (dict-detail path),
  `test_string_detail_http_exception_uses_envelope` (string-detail
  path) in `tests/test_ingest_api.py`. Existing tests that asserted
  on the old `resp.json()["detail"]` shape were updated to
  `resp.json()["error"]["message"]` /
  `resp.json()["error"]["detail"]` — affected
  `test_dataharmonizer_api.py` (×2),
  `test_samples_router_api.py` (×1),
  `test_ingest_api.py` (×2).

### Page-code review — error-rendering plumbing

Confirmed by reading `frontend/pages/upload.py:179-184` +
`frontend/lib/api.py:141-147`:

- **Envelope errors** (`success: false`) → `ApiError(code, message)`
  → `st.error(f"Upload failed: {exc.message}")`. Both server-defined
  codes (`HTTP_400` from file_detector, `HTTP_422` from validator)
  and ApiClient-defined codes (`NETWORK`, `BAD_RESPONSE`,
  `HTTP_ERROR`) flow through the same path.
- **Non-JSON error responses** (api.py:130-131) → `HTTP_ERROR` code
  with the raw response text. Should be rare given the new global
  handler returns JSONResponse for everything; left as defence in
  depth.
- After the fix, every error path returns a string suitable for
  direct display in `st.error()` — no JSON dumps, no stack traces.

### Out-of-scope / followup recommendations

- **UI-B2 (recommended new backlog item)**: build out the Upload
  page form with sequencing-lab dropdown, project dropdown, sector
  auto-derive from source_type, host fields, isolation source.
  Estimated effort: 1-2 sessions.
- **Browser walkthrough**: still required to confirm rendering
  matches the contract. Once UI-B2 lands, the human walk should
  click through happy + error paths and verify the actual `st.error`
  toast renders the messages I traced.
- **Other `HTTPException`-heavy routers** (`samples.py` has 16,
  `auth.py` has 2, `gisaid.py` has 2): now silently fixed by the
  global envelope handler. If individual routers want richer error
  codes (e.g. `SAMPLE_NOT_FOUND` instead of `HTTP_404`), they can
  migrate to `responses.error()` over time.

### Lessons

- **When the UI is a layer ahead of you, drive the contract not the
  pixels.** I couldn't see widgets render, but `curl` against the
  same endpoint with the same multipart form caught two real bugs
  the page would have surfaced as opaque toasts. The walkthrough
  doc was written assuming a browser; reframing to the API surface
  found the bugs faster than clicking would have.
- **A global FastAPI exception handler is the right blast radius
  for a contract-shape fix.** Per-router rewrites would have
  touched 16 files and broken the existing test contracts. The
  one-handler fix in main.py is reversible, idempotent for handlers
  that already use `responses.error()`, and the test-suite
  breakage was 5 line edits.
- **`tests/conftest.py` had `sequencing_lab="Example Lab"`
  pre-baked.** Someone foresaw the rename. The seed migration just
  caught reality up to the test fixture's expectations.

## Renaming a seed entity in already-deployed environments (2026-04-24)

Renamed the JACKPOT-internal organisation from "the host academic operator" to "Linux
Prophet" — same data-migration pattern that closed the seed-data rename earlier in the day. Three rows updated
in one migration: `organizations.display_name`,
`sequencing_labs.organization` (denormalised text), and
`domain_whitelist.domain` (`example-academic.edu` → `example.org`).

### The pattern

When a seeded entity needs to be renamed AND the environment is
already deployed somewhere (local, staging, prod, fork):

1. **Update the snapshot** in `db/SCHEMA.sql` so the human-readable
   reference matches the post-migration end state. Don't touch the
   landed baseline migration — that's the immutable starting point;
   the rename is a delta on top of it.
2. **Write a data migration** that lives at the head of the chain.
   Match by old value (`WHERE display_name = '<host-academic-operator>'`), not by id.
   Two reasons: (a) UNIQUE constraints on the column make the
   match unambiguous; (b) match-by-old-value is portable across
   forks and clones where ids may not have stayed `1`.
3. **Idempotent by construction** — re-running upgrade head on a
   DB already at the new value is a no-op (the WHERE clause
   matches nothing). Verified explicitly during this session.
4. **Reversible** — write the `downgrade()` body that flips the
   UPDATE back. Verified by `alembic downgrade -1 && upgrade head`
   round-trip.
5. **Update the test fixtures and assertions in the same commit.**
   Anything that asserts on the old value
   (`tests/test_organizations_api.py:240`,
   `tests/test_domain_whitelist_api.py:49`, etc.) will break the
   moment the migration runs in CI. Same commit = same review =
   one round-trip.
6. **Don't update generated code** (`backend/models_generated.py`)
   or schema-submodule-derived strings — those are out of band.

### Three things worth recording

- **Schema description vs task description.** The task asked to
  rename `name` and `slug` columns; the actual schema has
  `display_name` only and no slug column. Confirmed with the
  product owner before starting — a one-question check saves an
  invented schema change. Always verify column names from
  `\d <table>` before writing the UPDATE.
- **Match by old value, not by id, when the column has UNIQUE.**
  The migration could have hardcoded `WHERE id = 1`, but
  match-by-old-value is portable to staging (which may have
  different ids if seeded via different rounds) and idempotent
  for free. The `display_name` UNIQUE constraint guarantees
  uniqueness.
- **Domain mismatch caught at planning time.** The maintainer's email is
  `admin@example.org` but the new domain whitelist is
  `example.org`. Mock auth bypasses the whitelist for local
  dev so this isn't a daily-flow blocker, but flagged for the
  product owner: real Google OAuth sign-ups from `@example.org`
  won't be whitelisted by the seed if/when OAuth fronts the API.
  Surfacing the mismatch beats silently auto-correcting it.



## P0d Pre-Flight: Verifying source-repo canonicality before history-preserving migration — 2026-04-29

**What was built:** A diagnostic protocol (and the muscle memory for it) for confirming that all source repos for a `git filter-repo`-based monorepo migration are in clean canonical state on GitHub before the migration starts. Surfaced and resolved 4 distinct types of pre-migration drift across 6 source repos.

**Key decisions:**

- **Pull from GitHub, not local clones, during migration.** Local clones can have unpushed commits, dirty state, or stale view of `origin`. Migration tooling must use GitHub as the single source of truth. The pre-flight verifies this is safe.
- **Submodule pin vs sibling clone divergence is the failure mode to look for.** When the same repo exists as both a submodule and a standalone sibling clone, they almost always disagree about what `origin/main` is. The diagnostic uses `git merge-base --is-ancestor <submodule-pin> HEAD` against the sibling — three outcomes:
  - YES → sibling is strictly ahead, push it (case 1, easy)
  - NO with valid SHAs → genuine divergence, requires manual reconciliation
  - NO with `unknown revision` → submodule pin SHA doesn't exist locally in the sibling (sibling is behind GitHub), `git fetch origin` then re-test
- **`ahead/behind/dirty: 0/0/0` is the readiness gate.** A sweep loop over all source repos that prints these three numbers per repo. P0d cannot start until every line reads three zeros.

**Watch out for:**

- **`gh repo view --json isEmpty` is misleading.** Returns `false` if the repo has even a single auto-generated `LICENSE` file from GitHub's repo-creation form. Use `gh api repos/.../commits` to actually see how many commits and what they say. A "non-empty" repo with one `Initial commit` and only a LICENSE file is the cleanest possible starting state.
- **GitHub's auto-generated LICENSE is whatever was selected at repo creation.** For `Midnight-Oil-Innovation/jackpot`, this was Apache 2.0 from before the AGPL-3.0 decision was finalized. The fix is straightforward: `curl -L -o /tmp/agpl-3.0.txt https://www.gnu.org/licenses/agpl-3.0.txt && cp /tmp/agpl-3.0.txt LICENSE && gac "chore: replace Apache 2.0 with AGPL-3.0 license"`. GitHub's repo metadata (`gh api repos/X/Y --jq '.license'`) auto-detects from file contents within an hour.
- **The diagnostic command for unfetched-sibling detection has a subtle gotcha.** `git log --oneline <sha> 2>&1 | head -3` will return `fatal: ambiguous argument` if the SHA isn't in the local clone — that's the signal the sibling is behind GitHub. It looks like an error but is actually diagnostic data.
- **`git log --1` is a typo that fails.** Real flag is `git log -1` (single dash, no double). Easy to mistype and the error is non-obvious.

**ASCII diagram — the three submodule-vs-sibling drift cases:**

```
Case 1 (most common): sibling is ahead of submodule pin
  GitHub origin/<branch>:  ... → A → B (newest)
  jackpot-backend pin:     ... → A
  sibling clone HEAD:      ... → A → B
  is-ancestor: YES   →   push siblings, done

Case 2: sibling is behind GitHub (saw this for jackpot-nf)
  GitHub origin/<branch>:  ... → A → B → C → D → E (newest)
  jackpot-backend pin:     ... → A → B → C → D → E
  sibling clone HEAD:      ... → A
  is-ancestor with stale fetch: NO (E "unknown")
  → fetch + ff-only pull, sibling catches up, done

Case 3: genuine divergence (didn't hit this; flag if you do)
  GitHub origin/<branch>:  ... → A → B (canonical)
  sibling clone HEAD:      ... → A → X (local-only work on different line)
  is-ancestor: NO with both SHAs valid locally
  → manual reconciliation: rebase, merge, or pick-one-side
```

**Diagnostic loop (the readiness sweep):**

```bash
for repo in jackpot-backend jackpot-cli jackpot-iac jackpot-frontend jackpot-nf jackpot-schema; do
  echo "=== ~/jackpot/$repo ==="
  cd ~/jackpot/$repo
  echo "  branch: $(git branch --show-current)"
  echo "  HEAD:   $(git log -1 --oneline)"
  echo "  ahead:  $(git rev-list --count @{u}..HEAD 2>/dev/null) commits ahead of upstream"
  echo "  behind: $(git rev-list --count HEAD..@{u} 2>/dev/null) commits behind upstream"
  echo "  dirty:  $(git status --short | wc -l | tr -d ' ') uncommitted file changes"
done
```

Want every line to read `ahead: 0, behind: 0, dirty: 0`. Anything else is a loose end to tie up before P0d.

---

## `.claude/settings.json` for autonomous mode — Option B (scoped allow + explicit deny) — 2026-04-29

**What was built:** A refinement of `.claude/settings.json` for Claude Code autonomous mode that supports `/automode` without overly broad permissions. Replaces the "flat allowlist" approach with scoped patterns plus an explicit deny list. Verified the maintainer's pre-existing `CLAUDE_CODE_SUBAGENT_MODEL: "sonnet"` is the right cost/quality split (Opus orchestrator + Sonnet subagents).

**Key decisions:**

- **Scoped allow patterns over flat `Bash` and `Edit`.** A scoped pattern like `Bash(uv *)` covers `uv run`, `uv sync`, `uv pip install` without granting `Bash(*)` blanket access. `Edit(**)` and `Write(**)` are unavoidable for autonomous work but `Bash` should stay scoped.
- **Explicit deny list catches the destructive-by-default actions.** `Bash(rm -rf *)`, `Bash(git push --force *)`, `Bash(git reset --hard *)`, `Bash(sudo *)`, `Bash(curl * | bash)` all deny even though `Bash(rm *)` (single-file delete) and `Bash(git push *)` are allowed. This is the right granularity for trust without recklessness.
- **`Bash(rm *)` allowed; `Bash(rm -rf *)` denied.** Single-file `rm` is routine in P0d (deleting `__pycache__`, removing accidental files); recursive removal needs a pause.
- **`Bash(git push --force *)` denied even with `--force-with-lease`.** Force-push is essentially never necessary in autonomous mode; if it really is, force the operator to do it manually.
- **`CLAUDE_CODE_SUBAGENT_MODEL: "sonnet"` is non-negotiable for cost reasons.** Top-level orchestrator runs on `claude-opus-4-7` (the model setting at the top level); subagents run on Sonnet. With ~10 parallel subagents in a typical fan-out task, running them all on Opus would burn ~10x the budget for marginal quality gain.

**Watch out for:**

- **`hooks.Notification` with `osascript` requires macOS notification permissions enabled for the Terminal app.** Test once before a long autonomous session: `osascript -e 'display notification "test" with title "test"'` from your shell. If nothing appears, check System Settings → Notifications → Terminal (or whichever shell host you use) → Allow notifications. Otherwise `/automode` will silently fail to ping you when it stops.
- **`enabledPlugins.pyright-lsp` matters for refactor work.** Real-time type checking catches a meaningful percentage of import-path-rewrite bugs before tests do. Don't disable it during P0d.
- **`CLAUDE_CODE_DISABLE_AUTO_MEMORY: "1"` means Claude Code won't write to memory automatically.** Memory updates happen explicitly via the `memory_user_edits` tool when the user requests them. This is intentional — managing memory deliberately via the docs/CLAUDE.md + design-docs pattern is preferred over magic auto-write.
- **Claude Code must be restarted to pick up new `settings.json`.** `/exit` then re-launch `claude`. Verifying load: `> Show me your current permissions configuration`.

**Final structure (top-level keys):**

```
.claude/settings.json
├── env
│   ├── CLAUDE_CODE_DISABLE_AUTO_MEMORY: "1"
│   └── CLAUDE_CODE_SUBAGENT_MODEL: "sonnet"
├── permissions
│   ├── allow: [~50 scoped Bash patterns + Read(**) + Edit(**) + Write(**) + Glob + Grep + Task + WebFetch + WebSearch]
│   └── deny: [~10 patterns covering rm -rf, force-push, hard-reset, sudo, curl-pipe-bash]
├── model: "claude-opus-4-7"          # orchestrator
├── hooks.Notification: osascript ping when attention needed
├── enabledPlugins.pyright-lsp: true
├── effortLevel: "xhigh"
└── theme: "light"
```

---

## /automode and /ultrareview skills — 2026-04-29

**What was built:** Two new Claude Code skills under `.claude/commands/`. `/automode` is the persistent-autonomous-execution wrapper that lets a phase or task run without per-action confirmation. `/ultrareview` is the heavier sibling of `/simplify` — six parallel reviewers covering simplicity, security, performance, test coverage, documentation, and architectural consistency, with severity-ranked synthesis.

**Key decisions:**

- **Three-skill cadence: `/go` after every chunk → `/simplify` mid-phase → `/ultrareview` end-of-phase.** Each has different cost and scope. `/go` is verification-and-commit (seconds). `/simplify` is 4-agent simplification review (1-2 min). `/ultrareview` is 6-agent deep review (5-10 min plus the time to read findings). `/automode` is the wrapper that lets all three run without user babysitting.
- **`/automode` has explicit stop conditions.** Doesn't ask for routine confirmations (file edits, tests, lints, commits via `gac`) but DOES stop for: destructive actions outside the task scope, genuine ambiguity (multiple valid interpretations with materially different outcomes), test failures or errors needing human judgment, rate limits or auth errors, three-strike failure on autonomous fix attempts, task completion. Critical Rules from CLAUDE.md still apply.
- **`/ultrareview`'s six reviewers are non-overlapping.** Simplicity (deletable code, duplicated logic, over-abstraction), Security (injection risks, secrets, auth bypass, Critical-Rule compliance), Performance (N+1 queries, sync-when-async, unbounded loops, leaks), Test coverage (untested paths, weak tests, coverage delta), Documentation (CLAUDE.md/spec.md/todo.md/learnings.md updates, docstrings, inline rationale), Architectural consistency (module boundaries, import cycles, Rule-55 operator-agnostic compliance, pattern divergence).
- **`/ultrareview` synthesizes by severity, not by reviewer.** Output is ranked: Blockers (CRITICAL/HIGH security, broken tests, rule violations) → Should-fix-before-merge → Nice-to-have. Don't bury blockers in a long flat list.
- **Both skills explicitly invoke parallel subagents via the `Task` tool.** The prompt pattern is `> Use parallel subagents to do the following: Agent 1: ... Agent 2: ... Agent 3: ... When all agents complete, synthesize their outputs and report back.` This is a stronger prompt than "do A, B, and C in parallel" because it explicitly invokes the subagent mechanism.

**Watch out for:**

- **`/automode` does not bypass safety rules.** All 55 Critical Rules from CLAUDE.md remain in force during autonomous execution. Rule 55 (operator-agnostic production code) is the hardest one to violate accidentally during refactoring; `/ultrareview`'s Architectural Consistency reviewer specifically checks for it.
- **Long autonomous sessions degrade context.** After ~3-4 hours or ~10 substantive commits, end the session and start a new one. Pattern: `> Summarize what we've done in this session, what state the codebase is in, what the next 3-5 logical commits would be, and append this to docs/session-N-handoff.md. Then exit.` Next session starts with `> Read docs/session-N-handoff.md, then continue from where we left off. Enter /automode.`
- **`/automode off` is explicit.** Skill exits autonomous mode but doesn't undo changes. Use when wrapping up a phase or transitioning to interactive work.
- **`/ultrareview` is heavy.** Don't run it after every chunk — use `/simplify` or `/go` for that. Reserve `/ultrareview` for end-of-phase, before tag/release, or after a significant refactor.

---

## P0d migration — design pattern: "blueprint-with-parallel-fanout" — 2026-04-29

**What was built:** The master prompt template for P0d (JACKPOT monorepo migration), structured to take maximum advantage of Claude Code's subagent parallelism. Eight phases A-H, each declaring explicitly which work fans out to parallel subagents and which is sequential.

**Key decisions:**

- **Phase A (Inventory) parallelizes across source repos.** 6 subagents, one per source repo, fan out to read each repo's structure, count files, identify dependencies, find secrets, verify clean+pushed state. Independent work → ideal subagent fit.
- **Phase C (Execute merges) is sequential.** `git filter-repo` operations on the destination must happen in order because each one rewrites history. Cannot parallelize.
- **Phase E (Import-path rewrites) parallelizes across backend subdirectories.** 5 subagents working on `routers/`, `services/`, `models/`, `parsers/`, `tests/` in parallel — each subdirectory has independent import statements to rewrite.
- **Phase G (Phase 21.5 quick wins) parallelizes within the docs tree.** 8+ subagents writing the governance directory files, the FHIR mapping doc, the STLT deploy guides — all independent files.
- **Phase H (Final verification) ends with `/ultrareview` before tagging.** Six-agent deep review surfaces blockers; address before `git tag p0d-complete`.

**Watch out for:**

- **The `Use parallel subagents to do the following` prompt is required.** Claude Code does not always parallelize on its own; you have to invoke the subagent mechanism explicitly. Without that prompt, the orchestrator will do the work sequentially even when fan-out is obvious.
- **Subagent prompts must be self-contained.** Each subagent has its own context window and doesn't see the others' work. The orchestrator's prompt to each must include all the context that subagent needs.
- **Sequential phases must verify before moving on.** Phase C cannot start until Phase B confirmed the merge order. Phase E cannot start until Phase D's `uv sync` passes. The master prompt's phase-boundary "emit phase summary then continue" pattern enforces this.
- **The destination repo path matters.** `~/projects/jackpot/` (outside `~/jackpot/`) avoids confusion with source repos. `~/jackpot/jackpot-monorepo` would have collided with sibling source repos. The pre-flight cleanup includes deleting any leftover empty clones from earlier attempts.

**ASCII diagram — phase fan-out structure:**

Phase A — Inventory                Phase C — Merges (SEQUENTIAL)

```
Phase A — Inventory                Phase C — Merges (SEQUENTIAL)
┌─────────────┐                   ┌──────────────────────┐
│ subagent 1  │───┐               │ filter-repo backend  │
│ subagent 2  │───┤               │         ↓            │
│ subagent 3  │───┼─→ orchestrator│ filter-repo cli      │
│ subagent 4  │───┤   synthesis   │         ↓            │
│ subagent 5  │───┤               │ filter-repo iac      │
│ subagent 6  │───┘               │         ↓ ...        │
└─────────────┘                   └──────────────────────┘

Phase E — Import rewrites          Phase G — Phase 21.5 docs
┌─────────────────┐                ┌───────────────────────┐
│ routers/        │───┐            │ governance/charter.md │
│ services/       │───┤            │ governance/coi.md     │
│ models/         │───┼─→ tests    │ governance/care.md    │
│ parsers/        │───┤   per      │ docs/fhir-mapping.md  │
│ tests/          │───┘   batch    │ docs/deploy/stlt/*    │
└─────────────────┘                │ README.md             │
                                   └───────────────────────┘
```

## P0d — Monorepo migration to Midnight-Oil-Innovation/jackpot — 2026-04-29

**What was built:** Six source repos (jackpot-backend, jackpot-cli,
jackpot-iac, jackpot-nf, jackpot-schema; jackpot-frontend skipped as
vestigial) consolidated into a single AGPL-3.0 monorepo at
`Midnight-Oil-Innovation/jackpot` with full git history preserved
via `git filter-repo` subtree merges. Workspace consolidated under a
top-level uv pyproject (members: backend, cli, schema). CI workflows
unified at the monorepo root. Phase 21.5 governance + STLT + FHIR
documentation landed alongside.

**Key decisions:**

- *Two-pass git filter-repo for the backend.* Pass 1 dropped the
  unwanted paths (Apache LICENSE, .gitmodules, the schema/ and nf/
  submodule gitlinks, .DS_Store); pass 2 promoted spec.md, todo.md,
  NOTICE, COPYRIGHT, docs/, tests/ to the top level via a `__keep__/`
  staging prefix + a catch-all `:backend/` rename + a final unstrip
  rule. Single-pass with chained renames doesn't work because
  filter-repo applies renames sequentially — the catch-all clobbers
  the specific keep-rules. The two-pass split is cleaner than trying
  to interleave them.
- *jackpot-frontend NOT merged.* The repo was a vestigial stub; the
  canonical Streamlit lives under `backend/frontend/`. Per the maintainer's
  decision: do not import the stub at all (rather than parking it
  somewhere). Archive in Phase H.
- *backend's Apache LICENSE dropped during filter-repo.* Destination
  already had AGPL-3.0; spec.md §13 says license flipped April 2026.
  Dropping at filter-time is cleaner than resolving a merge conflict.
- *Workspace root is a "virtual" pyproject* (no `[project]` table) —
  uv 0.9 supports this; it expresses workspace membership without
  declaring the root as a package. Pytest config + coverage config +
  ruff config live at the root so `uv run pytest` / `uv run ruff`
  from the workspace top works uniformly.
- *Schema as a workspace member required a stub Python package*
  (`schema/jackpot_schema/__init__.py`) exposing `SCHEMA_YAML_PATH`,
  `SCHEMA_JSON_PATH`, `MAPPING_CONFIGS_DIR`. This satisfies Critical
  Rule 54 (no sys.path tricks) — the four backend modules that used
  to compute schema paths via `Path("schema/schema/...")` now do
  `from jackpot_schema import SCHEMA_YAML_PATH as SCHEMA_PATH`.
- *Pipelines kept its own pyproject + uv.lock outside the workspace.*
  Per the user's spec — though this means `pipelines/` parser tests
  run in a separate CI job and don't share workspace dependency
  resolution. Revisit before P0f BYOP work, since BYOP parsers may
  want to share types with backend.

**Watch out for:**

- *Coverage regression is real and unfixed.* pytest-cov via the
  editable workspace install measures backend coverage at ~40% even
  though tests all pass and behaviour is unchanged. Specifically,
  the `backend/storage/` subtree shows 0% measured even though
  storage tests run and pass (32 of them). Threshold lowered from
  60% → 35% as an interim; CLAUDE.md updated to document this.
  Restore the 60% bar once measurement is fixed.
- *Inherited Rule 55 violations exist in source code we imported
  but did NOT author.* Specifically: hardcoded `linuxprophet`
  references in `backend/setup/write_files*.py`, the baseline
  Alembic migration `5adf11b77c19...py:618` (seed data),
  `deploy/scripts/bootstrap_project.sh:152`, and
  `deploy/helm/jackpot-api/Chart.yaml:7,10`. The P0d migration fixed
  the `authors = ...` lines in the four pyproject.toml files because
  those were edited during P0d. The remaining inherited references
  should be cleaned up in a follow-up "Rule 55 sweep" commit;
  Cleanup A-J landed before P0d began but missed these.
- *Subagent tooling limits.* Phase A's parallel verification
  subagents could not use Bash; we did Phase A clones + inventory in
  the main agent thread instead. Document this for future P0d-style
  multi-agent fan-out work — plan for main-thread shell work and
  delegate read-only review or analysis to subagents.
- *Pyright errors shown locally are cosmetic.* The IDE-side Pyright
  reports `Import "jackpot_schema" could not be resolved` because it
  doesn't auto-discover the workspace `.venv`. The actual Python
  imports work and pytest passes. The pyrightconfig.json was moved
  to the workspace root and updated for the monorepo layout, but
  IDEs may still need a restart to pick it up.
- *git filter-repo defaults to refusing non-fresh clones.* Use
  `--force` after copying the source clone into a working dir.
  Filter-repo also removes the `origin` remote — that's expected;
  the filtered repo is meant to be re-attached as a different remote.
- *deploy-staging.yml workflow now operator-agnostic.* `CLUSTER_NAME`,
  `NAMESPACE`, and the secret-name prefix come from
  `${{ vars.GCP_CLUSTER_NAME }}`, `${{ vars.GCP_NAMESPACE }}`, and
  `${{ vars.GCP_SECRET_PREFIX }}` respectively. Set these in the
  GitHub Actions `staging` environment vars before the next deploy.

**ASCII diagram — P0d workspace layout:**

```
~/projects/jackpot/  (workspace root, uv.lock here)
├── backend/    (workspace member; FastAPI + Streamlit + ingest gate)
├── cli/        (workspace member; jackpot CLI + SDK)
├── schema/     (workspace member; LinkML schema + jackpot_schema helper)
├── pipelines/  (NOT a workspace member; member-local pyproject + uv.lock)
├── deploy/     (Terraform + Helm; no Python)
├── docs/       (product + design docs + STLT deploy guides + FHIR mapping)
├── governance/ (8 charter + policy files)
├── tests/      (backend integration tests vs Postgres testcontainer)
└── .github/workflows/  (test.yml + deploy-staging.yml; consolidated)
```

---

## P0d.1 — Post-execution cleanup: docker-compose location, frontend canonicalization — 2026-05-01

**What was built:** The four structural follow-ups that surfaced after P0d's `p0d-complete` tag was applied (commit `d32f40a`) but before the local dev stack actually ran. None of them were caught by P0d's own success criteria (tests pass, /ultrareview clean, gh archive done) because those criteria didn't include "`docker compose up` brings the full stack up." This entry documents the structural fixes that took P0d from "executed cleanly" to "validated end-to-end working" at tag `p0d-validated`.

**The four issues, in order encountered:**

1. **`docker-compose.yml` stayed at `backend/docker-compose.yml`** because the P0d filter-repo for `gotero/jackpot-backend` carried it along with the rest of the source repo's root-level files into `backend/`. From the monorepo root, `docker compose up` returned "no compose file found." The compose file's relative paths (`./schema`, `./frontend`, `context: .`) all resolved relative to the file's location, so even running it from `backend/` would have used wrong paths.

2. **Dockerfiles also at `backend/Dockerfile.{api,ui}`** with `COPY pyproject.toml uv.lock alembic.ini ./` and `COPY db/ ./db/` — paths that worked when build context was the old `jackpot-backend` repo root but were broken in the new monorepo where `alembic.ini` is at `backend/alembic.ini` and `db/` is at `backend/db/`. The Dockerfiles also did `COPY pyproject.toml uv.lock` without the workspace member pyproject files, which would have failed `uv sync --frozen` because workspace resolution requires all member pyproject.toml files to be present at sync time.

3. **`backend/frontend/` was treated by chat-side analysis as a stale shadow** of a canonical `frontend/` at the monorepo root. It wasn't. P0d's design (per the prior P0d entry above) deliberately kept the canonical Streamlit at `backend/frontend/` and skipped `gotero/jackpot-frontend` as a vestigial stub. Deleting `backend/frontend/` removed 18 working files (1,840 lines: `app.py`, `lib/api.py`, `lib/session.py`, `components/badges.py`, 9 researcher pages) under the wrong assumption that they were duplicates.

4. **Retroactive merge of `gotero/jackpot-frontend` brought in a half-stub** instead of recovering the deleted code. The archived gotero repo turned out to be a `uv init` skeleton (5-line "Hello from jackpot-frontend" `main.py`, placeholder pyproject.toml, the actual streamlit code copied as an unused subdirectory `frontend/frontend/`, plus a never-initialized `.gitmodules` submodule pointer to `gotero/jackpot-schema`). Confirmed why P0d had skipped this repo: there was nothing useful in it.

**Recovery sequence (for future migrations):**

```bash
# 1. Delete the half-stub from the bad merge
git rm -rf frontend/

# 2. Restore the canonical files from the parent of the deletion commit
git checkout <bad-deletion-commit>^ -- backend/frontend/

# 3. Move to the canonical location (root, per P0d intent)
git mv backend/frontend frontend

# 4. Single recovery commit that surfaces the full repair
gac "fix(p0d): restore canonical frontend at monorepo root"
```

**Key decisions:**

- *Frontend restored to `frontend/` at monorepo root, NOT to `backend/frontend/`.* The P0d execution's choice to keep frontend nested under `backend/` was internally consistent (Streamlit code shared `from backend.foo` imports easily), but it diverged from P0d's stated intent that "each top-level directory is a first-class component." The recovery used the relocate to honor the original intent. Cost: the streamlit code now uses `from frontend.lib.session import current_user` which works because the monorepo root is on sys.path inside the container.
- *docker-compose.yml at monorepo root, not `backend/`.* Standard monorepo pattern. The compose file's relative paths now resolve to canonical sibling directories (`./frontend`, `./schema`, `./pipelines`) at the root. This is the configuration most natural to "developer wants `docker compose up` to work from the repo top."
- *Dockerfiles copy the full uv workspace before `uv sync`.* Specifically: `COPY pyproject.toml uv.lock ./` then `COPY backend/ ./backend/` then `COPY cli/ ./cli/` then `COPY schema/ ./schema/`. Then `uv sync --frozen` resolves the workspace correctly because all member pyproject files exist. We accepted worse Docker layer caching (any source change invalidates the deps layer) for reproducibility — workspace member sources may reference each other's APIs, and partial copies can succeed at sync but fail at runtime.
- *entrypoint.sh now `cd /app/backend` before alembic, `cd /app` before uvicorn.* Alembic's `script_location = db/migrations` is relative to cwd, and `db/migrations` lives at `/app/backend/db/migrations` in the new layout. Uvicorn imports `backend.main:app` which requires `/app` on sys.path so the package at `/app/backend/__init__.py` resolves.
- *Add `p0d-validated` tag, leave `p0d-complete` where it is.* Two tags now: `p0d-complete` at d32f40a marks "Claude Code declared P0d done"; `p0d-validated` marks "stack actually runs end-to-end." Useful historical record of the gap.

**Watch out for:**

- *"Shadows that aren't shadows."* Before deleting an apparent duplicate during a migration, run `git ls-files <canonical-path>` to confirm the canonical version exists in the working tree. If `git ls-files frontend/` returns empty, then `backend/frontend/` is NOT a shadow — it's the only copy. The diagnostic costs nothing; deleting working code costs an hour of recovery.
- *`backend/backend/` for uv workspaces is a standard layout, not an anti-pattern.* When `backend/pyproject.toml` declares the package name as `backend`, the inner `backend/backend/__init__.py` is the canonical Python package directory. Imports resolve as `from backend.foo import bar` because the package metadata in `backend/pyproject.toml` points uv there. Same pattern at `pipelines/pipelines/`, `schema/schema/`, `cli/jackpot/`. Don't flatten these without checking the workspace config first.
- *git filter-repo `--to-subdirectory-filter` wraps source structure, doesn't flatten it.* If the source repo has `frontend/X.py` at its root, filter-repo with `--to-subdirectory-filter frontend` produces `frontend/X.py` (correct). If the source repo had `subdir/X.py`, the result is `frontend/subdir/X.py`. The destination layout depends entirely on the source layout.
- *Compose file location matters in monorepo migrations.* The default-correct location is the monorepo root, not nested under one of the components. If the source repo had its compose file at root (which is typical), filter-repo will move it to `<subdir>/docker-compose.yml` — it must then be promoted back to the root in a follow-up step. Same applies to `Dockerfile.*` and any cross-cutting config files.
- *P0d's success criteria didn't include "stack runs."* All 8 phases passed their declared exit criteria (tests green, /ultrareview clean, gotero/* archived, p0d-complete tag) but `docker compose up` was never validated. For future migrations, add to the success criteria: "From a fresh clone of the destination repo, `docker compose up` brings all services healthy and the integration smoke test passes." Validation gate, not just acceptance gate.

**ASCII diagram — the four files that needed to move from `backend/` to monorepo root:**

```
Before P0d.1                          After P0d.1
~/Projects/jackpot/                   ~/Projects/jackpot/
├── backend/                          ├── backend/
│   ├── docker-compose.yml ───────┐   │   ├── backend/  (Python pkg)
│   ├── Dockerfile.api ───────┐   │   │   ├── db/
│   ├── Dockerfile.ui ────┐   │   │   │   └── ...
│   ├── frontend/   ──────┼───┼───┼   │   └── (no Dockerfiles, no compose)
│   │   └── (canonical)   │   │   │   ├── docker-compose.yml ◄────┐
│   ├── pipelines/        │   │   │   ├── Dockerfile.api ◄──────┐ │
│   └── ...               │   │   │   ├── Dockerfile.ui ◄────┐  │ │
├── frontend/  (empty/    │   │   │   ├── frontend/  ◄───────┼──┼─┘
│       absent)           │   │   │   │   ├── app.py        │  │
├── pipelines/  (canonical)│  │   │   │   └── pages/         │  │
├── schema/  (canonical)  │   │   │   ├── pipelines/  (canonical)
└── ...                   │   │   │   ├── schema/  (canonical)
                          ▼   ▼   ▼   └── ...
                    moved to root    │
                                     │
                       Dockerfiles copy full workspace
                       members before `uv sync --frozen`
                       so workspace resolution sees all
                       member pyproject.toml files
```

**Total cleanup work:** 4 commits between `d32f40a` (p0d-complete) and `p0d-validated`:

1. `5dd4806 fix(p0d): remove stale frontend/ and pipelines/ shadows from backend/` (the bad commit — wiped working frontend)
2. `6b462f3 fix(p0d): docker-compose + Dockerfiles to monorepo root with workspace-aware paths` (correct: moved compose+Dockerfiles)
3. `0373156 chore(p0d): merge jackpot-frontend (root → frontend/) [retroactive Phase C step]` (the half-stub merge, kept for history despite being unused)
4. `8a01cd8 fix(p0d): restore canonical frontend at monorepo root, drop unused jackpot-frontend stub` (the recovery)

The bad commit (5dd4806) stays in history rather than being reverted — its presence + the recovery commit document the lesson better than a clean revert would.

---

## Phase 22 — Periodic review checkpoint after P0d — 2026-05-01

**What was built:** A four-agent parallel review of the post-P0d codebase plus four named security/deploy deliverables (SEC-1 CORS tightening, SEC-2 slowapi rate limiting, DEPLOY-1 production deploy gate, DEPLOY-2 PITR restore drill procedure). Findings synthesized into `docs/review_log.md`. Session 13 in `jackpot_session_summary_and_backlog.md` carries the full play-by-play.

**Key decisions:**

- *The "coverage measurement gap" framing in P0d's `learnings.md` was wrong.* When the post-P0d coverage dropped from 86.99% to 39%, we attributed it to a pytest-cov-can't-find-the-files measurement artifact. A dedicated diagnosis subagent in Phase 22A (`/tmp/phase22_agent3_coverage.md`) disproved this: pytest-cov correctly instruments `backend/backend/*.py`, the `.coverage` data file contains 43 entries at correct absolute paths, and the omit pattern `**/backend/storage/**` is excluding storage from the report (not measuring it at 0%). The drop is **organic dilution** — Sessions I–Q added ~660 statements with low/no coverage. Recovering 60% requires writing tests for those modules, not fixing tooling. Lesson: when test count stays roughly constant (639 across the migration) but coverage drops drastically, do the math against the new total stmts before reaching for "tooling broke."
- *Security defaults should land before production goes live, not after.* SEC-1 and SEC-2 are pre-emptive — there's no production deployment yet, no observed attack. But CORS `allow_methods=["*"]` and unrate-limited auth are the kind of things you regret only in retrospect. Cost was small (one config edit + one new module + 3 tests).
- *Production deploy approval lives in GitHub UI, not YAML.* The `environment: name: production` block in the workflow is the gate's _wiring_; the Required Reviewers list is configured per-environment under repo Settings. This is operator-agnostic by design (each instance sets its own approver list) and survives YAML edits — a malicious PR cannot grant itself approval rights without first changing the Settings UI.
- *PITR drill is documentation, not code, but the procedure has explicit pass criteria.* Row counts within ±1% of production at the target time, latest sample timestamp ≤ target, alembic_version match. A drill that just "successfully creates a clone instance" doesn't validate that the data is intact — the verification queries are the actual test.
- *macOS APFS case-insensitivity hides path-typo bugs.* Phase 22A agent 3 typed `/Users/glen/projects/jackpot/...` (lowercase) three times in its report. Commands worked because the filesystem resolved them to `/Users/glen/Projects/jackpot/...`. Codebase grep confirmed no production file has either lowercase or uppercase developer paths. Lesson for future agents: explicitly type the canonical case in reports even if the FS doesn't enforce it.
- *Inherited rule violations stay deferred to the natural fix point.* The 5 inherited Rule 55 violations (operator-specific values in `backend/setup/write_files*.py`, baseline migration `5adf11b77c19`, `Chart.yaml`, `bootstrap_project.sh`) were known going into Phase 22 and were not fixed during it. The natural place is P0e (`jackpot init` CLI), which is the operator-bootstrap mechanism — fixing these requires deciding what the post-`jackpot init` flow looks like for each file, and that decision belongs in P0e scope, not Phase 22. Documented as action item 11 in `review_log.md`.

**Watch out for:**

- *FastAPI routes decorated with `@limiter.limit(...)` MUST take `request: Request` as a parameter.* slowapi reads `request.client.host` (or X-Forwarded-For via the key_func) to identify the rate-limit bucket. If the parameter is missing, slowapi raises a confusing `Could not find Request object` at request time, not at startup. All 4 endpoints we decorated already had `request: Request` for other reasons; would have been a debugging trap otherwise.
- *Pydantic-settings `BaseSettings` reads env vars case-insensitively, but the env var name in the test must still match field-name conventions.* `RATE_LIMIT_ENABLED` (uppercase) is correctly mapped to `rate_limit_enabled` (lowercase field). When test sets `monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")` after `get_settings.cache_clear()`, the next call to `get_settings()` re-reads the env. The slowapi `Limiter` instance, however, was constructed at import time with `enabled=get_settings().rate_limit_enabled` and does NOT re-read settings on each request. So the test conftest must explicitly do `limiter.enabled = get_settings().rate_limit_enabled` after the env mutation, or rate-limit-disabled tests will trip the live limiter.
- *slowapi `_route_limits` is an internal dict.* The dedicated test asserting "ingest endpoints carry a 60/* limit" reaches into `live_limiter._route_limits.values()`. This is brittle to slowapi version changes. We pinned `slowapi==0.1.9`; bump only with care and re-run `tests/test_rate_limiting.py`.
- *RateLimitExceeded handler must produce the JACKPOT envelope.* slowapi's default returns `{"error": "Rate limit exceeded: 5 per 1 minute"}` — a bare dict without the `success`/`error.code`/`error.message` shape the frontend ApiClient expects (Critical Rule 24). Without our custom `_rate_limit_to_envelope` handler, a 429 response would crash the frontend's response unwrapper.
- *Production environment in GitHub also needs env-scoped secrets.* `GCP_PROJECT_ID`, `GCP_CLUSTER_NAME`, etc. should be set at the `production` environment scope, NOT at the repo scope, so the staging workflow cannot accidentally read production credentials. This is documented in `production-deploy.md` step 2 but is operator action, not a workflow concern.
- *Cloud SQL clone instances bill at the source instance's machine type.* A 90-minute drill against `db-custom-4-15360` is roughly $0.50; a forgotten clone left running for a month is ~$350. The cleanup step in the PITR drill is not optional.

**ASCII diagram — Phase 22 sub-phase flow:**

```
22A: Four parallel review subagents (read-only)
   ┌──────────────────────────┐
   │ Agent 1: Critical Rules  │ → /tmp/phase22_agent1_rules.md
   │ Agent 2: Spec drift      │ → /tmp/phase22_agent2_spec.md
   │ Agent 3: Coverage        │ → /tmp/phase22_agent3_coverage.md
   │ Agent 4: TODOs           │ → /tmp/phase22_agent4_todos.md
   └──────────────────────────┘
                ↓
22B: Synthesis (orchestrator reads all 4 → docs/review_log.md)  ── commit 8cbb993
                ↓
22C: Four named deliverables (sequential)
   ┌──────────────────────────────────────────────────┐
   │ SEC-1: Tighten CORS         ── commit cea62b6   │
   │ SEC-2: slowapi rate limit   ── commit a1ed4ab   │
   │ DEPLOY-1: prod deploy gate  ── commit f7680ea   │
   │ DEPLOY-2: PITR drill doc    ── commit 6d35d20   │
   └──────────────────────────────────────────────────┘
                ↓
22D: learnings.md + session_summary.md + todo.md updates,
     /ultrareview pass, then `git tag -a phase-22-complete`,
     then push.
```

**The pause-for-review pattern from `/automode`:** Phase 22 was a textbook fit for spawn-N-parallel-agents, synthesize, then sequential commits. The four review agents shared no state, each took ~5–40 minutes, and the orchestrator synthesizing their outputs took roughly the same wall time as one agent. Net: ~80 minutes of agent work compressed into ~40 wall-clock minutes. Reuse this pattern at every "after-P0X" review checkpoint.

---

## Coverage measurement bug — what we got wrong — 2026-05-01 (post-Phase-22)

**What was built:** The diagnosis and fix for a coverage-measurement misconfiguration that we carried wrong through P0d, the P0d.1 cleanup, all of Phase 22, and three `/ultrareview` passes. The "39% coverage post-P0d" number we quoted in `docs/CLAUDE.md`, `docs/learnings.md`, `docs/review_log.md`, `todo.md`, and the Phase 22 commit log was wrong by ~45 percentage points. Real coverage was 84% the whole time. Two `pyproject.toml` lines fix it.

**The bug:**

`pyproject.toml` had:

```toml
[tool.pytest.ini_options]
addopts = "--cov=backend --cov-report=term-missing --cov-fail-under=35"

[tool.coverage.run]
omit = [
    "**/backend/storage/**",
    "**/backend/routers/pipelines.py",
    ... 16 more entries ...
]
```

Two interacting problems:

1. **`--cov=backend` is a path-based source spec** that bypasses `[tool.coverage.run].omit`. When pytest-cov sees `--cov=<path>`, it treats the value as a directory to measure but does not also auto-load the `omit` list from pyproject.toml.
2. **pytest-cov does NOT auto-discover `[tool.coverage.run]` from pyproject.toml the way the `coverage` CLI does.** It needs `--cov-config=pyproject.toml` explicitly in addopts. Without it, the omit list is parsed (and `coverage.Coverage().load()` confirms it's there) but never reaches the report-time matcher.

Net effect: 17 large modules that were intentionally omit-listed (pre-implementation stubs, generated code, storage helpers, frontend/, migrations/) were all being measured at 0% and counted in the denominator. Real coverage was 84%; reported coverage was 39%.

**The fix (two `pyproject.toml` lines):**

```toml
addopts = "--cov --cov-config=pyproject.toml --cov-report=term-missing --cov-fail-under=80"

[tool.coverage.run]
source_pkgs = ["backend"]
omit = [...same list, plus tightened a few patterns...]
```

- `--cov` (bare, no path) reads source from `[tool.coverage.run].source_pkgs`.
- `--cov-config=pyproject.toml` makes pytest-cov load the omit list.
- `source_pkgs = ["backend"]` is the importable package name (more precise than a path-based source).
- Threshold restored from `35` to `80` — the real value.

**Verification:**

```
$ uv run pytest tests/
  Required test coverage of 80% reached. Total coverage: 84.09%
  615 passed, 1 skipped
```

**How we got it wrong (the meta-lesson):**

The Phase 22A coverage diagnosis subagent (the agent that wrote `/tmp/phase22_agent3_coverage.md`) ran `uv run pytest --cov=backend --cov-report=term-missing` to investigate — exactly the broken form. It correctly observed that the `.coverage` data file contained the right files, that `import backend` resolved to the right path, and that pytest-cov was instrumenting `backend/backend/*.py`. It then jumped to the wrong conclusion — "the 47-point drop is organic dilution from Sessions I–Q" — without testing the omit-list behavior. The hypothesis was plausible (Sessions I–Q DID add new code) and self-consistent (coverage IS measuring what it instruments), but it didn't match the numbers when you looked at any single module: `samples.py` showed 88%, `validator.py` 90%, `tokens.py` 100% — these are not "low coverage" numbers. The drag was concentrated in a small number of modules at exactly 0%, which is a measurement-bug signature, not a tested-poorly signature.

The user surfaced the discrepancy by asking "Why is the test coverage so low?" — and pulling on that thread for one minute revealed the real answer. **Lesson: when a coverage diagnosis agent reports a wide-spread drop, run the same `--cov` command both with and without an explicit path argument.** If the numbers diverge, the omit list is being ignored in one of them.

**Watch out for:**

- `pytest --cov=<path>` and `pytest --cov` (bare) produce different numbers when an omit list exists. Pick one form deliberately and write down which.
- The `[tool.coverage.run]` table in pyproject.toml is read by the `coverage` CLI but NOT by `pytest-cov` automatically. Always add `--cov-config=pyproject.toml` to addopts in pytest projects, or duplicate the omit list in a `.coveragerc`.
- A coverage report that shows multiple critical modules at exactly 0% with no missing-line ranges is a measurement signature, not a coverage signature. Tests that exist but contribute zero are not "weak tests" — they're not being credited.
- The `--cov-fail-under` threshold can make a misconfigured coverage measurement *passively LGTM* — we passed `35%` for weeks while the real number was `84%`. Set the threshold to the real expected value so a misconfiguration produces a noticeable failure.

**Documents that needed corrections:**

- `docs/CLAUDE.md` — line 33 ("≥615 tests, ≥35% coverage") and the Testing Philosophy block ("Post-P0d interim: 35%")
- `todo.md` Baseline line ("39.74% coverage")
- `docs/review_log.md` Test coverage health section (preserved as historical record; superseded by this entry)

**Related deferrals to revisit:**

- Action item 15 in `review_log.md` ("Restore 60% coverage by writing tests for Sessions I–Q") is partially obsolete — coverage is already 84%. The real remaining gaps are smaller and more specific: `harmonizer.py` 0%, `gisaid.py` 43%, `templates.py` 53%, `dlp_scanner.py` 71%. The "~100 new tests for Sessions I–Q" estimate was based on the wrong baseline; ~20 targeted tests against those four modules would close the meaningful gaps.
- Action item 5 (fix `learnings.md` + `CLAUDE.md` "0% storage" / "measurement gap" claims) is now fully resolved — the framing was wrong, and this entry retires it.

---

## P0e — `jackpot init` operator-bootstrap CLI + 13-item Phase 22 cleanup — 2026-05-02

**What was built:** The full `jackpot init` CLI (detect / scenario-info / configure / secrets / bootstrap / validate subcommands; `reconfigure` documented in the design lockdown but deferred to P0f) plus 13 Phase 22 cleanup items absorbed into the same phase. P0e shipped 26 commits across 5 streams (A through E), 970+ tests passing, 86%+ coverage. Full closeout in the `docs/review_log.md` "P0e closeout" section; this entry captures the patterns + lessons, not the per-commit log. (That file was deleted on 2026-05-08 as collateral in `06e67ee`, a schema-regeneration commit; recover it with `git show 06e67ee^:docs/review_log.md`. `docs/learnings.md` is the log going forward.)

**Key decisions:**

- *Pure-logic-in-schema, Click-wrappers-in-cli.* The detector and scenario registry live under `schema/jackpot_scenarios/` (workspace-co-located, importable from anywhere); the Click prompts wrapping the detector live under `cli/jackpot/init/`. Result: the inference policy is testable without subprocess gymnastics, and the CLI surface is replaceable (a future TUI / web installer could reuse the same pure functions). Same separation pattern the maintainer has been pushing for in routers (validator-policy vs router-orchestration).
- *Operator-agnostic by force, not convention.* Critical Rule 55 enforcement got teeth in P0e via Critical Rule 56 (`instances/ci/` ships with synthetic-only values) AND via the `jackpot init configure --instance-name ci` runtime check that REFUSES to overwrite the committed CI dir. The pattern is: rules that need to be enforced get enforced at the CLI boundary, not just documented in CLAUDE.md.
- *Compose profiles over per-scenario compose files.* Decision 2 collapsed what could've been 7 docker-compose-X.yml files into one canonical compose file with `profiles:` keys. The trade is "operator must set COMPOSE_PROFILES" (handled automatically by `jackpot init` writing it to `.env.local`) for "we maintain one compose file forever, not 7 in lockstep." The matrix-comment at the top of the compose file is the contract.
- *Idempotent everything.* `jackpot init configure` and `jackpot init secrets` are safe to re-run. Non-secret files overwrite by default (operators can pass `--no-overwrite-non-secrets` to preserve hand-edits); secret files preserve by default (operators must pass `--regenerate-secrets` AND confirm per-secret to rotate). Same baseline as Alembic — the surface should be safe to call again.
- *Hybrid GitHub-vars detection.* Decision 3's "detect `gh` is installed and authed, slurp existing repo vars from `gh api repos/$REPO/actions/variables`, present each as confirm prompt" pattern is a strict UX improvement for operators who already use GitHub Actions, and a no-op for everyone else. Hard rule embedded in the module: secrets are NEVER slurped from `gh api` (the GitHub API doesn't return secret values anyway, but the constraint is tested via `test_no_secrets_fetcher_exported` + `test_no_subprocess_call_references_secrets_endpoint`).
- *Local ed25519 keypairs for federation, defer central CA to P1.* Scenario E (federation member) and Scenario T (Tribal sovereignty — uses local keypair regardless of broader network policy) generate ed25519 keypairs at `jackpot init secrets` time. Public key committable to private operator repos for sharing; private key gitignored, 0600 perms. Federation protocol design supports BOTH local-keypair AND CA-cert auth modes simultaneously — peers record which mode each uses — so an operator-network that grows past 5 instances and wants central revocation can layer the CA on without breaking existing local-keypair peers (B-FED-1 trigger).
- *Scenario T defaults are baked, not opt-in.* `deletion_on_request=True`, `auto_publish_to_insdc=False`, `federation_enabled=False`, `consent_workflow_enabled=True` are all defaults a Tribal IT staffer running `jackpot init` does not have to read about to enable. Operator overrides them only via explicit prompts. CARE Principles enforcement on by default.

**Watch out for:**

- *`@dataclass(frozen=True)` + `__class_getitem__` on subclasses doesn't work.* Tried it for the `_Likelihood` test stub; pydantic raised a confusing error chain. Real solution was to drop the GCP DLP mock entirely and use `monkeypatch.setitem(sys.modules, "google.cloud.dlp_v2", None)` to force the import to fail (which exercises the operational fallback path the scanner is supposed to handle).
- *`google.cloud.dlp_v2.DlpServiceClient()` triggers ADC at construction time.* Mocking at module import doesn't intercept the credential probe — the client constructor immediately tries to read GCP credentials from the environment. Net effect: any test that exercises the dlp_enabled-and-content-present path will make a real network call unless you intercept at the function level (or skip it). I went with skip + 1 import-failure test that covers the operational fallback.
- *Click `enum=...` Query metadata is OpenAPI-only.* It does NOT enforce the value at request time. So `/api/v1/templates/?source_type=garbage` returns 200 with the default template, not 422. Spec-mode validation requires explicit pydantic models — flag for any future endpoint where input is sensitive.
- *`Settings()` `@lru_cache` interaction with `monkeypatch.setenv`.* Always `get_settings.cache_clear()` after monkeypatching env vars in tests. A class-level Limiter (e.g. slowapi's) constructed with `enabled=get_settings().rate_limit_enabled` at module import time also needs its `.enabled` attribute mutated separately — see `tests/conftest.py` `override_settings` for the pattern.
- *Pydantic v2 `@dataclass(frozen=True)` raises `ValidationError`, not `FrozenInstanceError`.* Tests that try to mutate a frozen pydantic model should expect the former.
- *`docker compose` `profiles:` keys interact with `depends_on`.* If service A in profile X depends_on service B in profile Y, and you activate only X, compose errors with "depends on undefined service B." Fix: `required: false` on the depends_on entry. Compose v2.6+.
- *Bootstrap action labels can mis-fire on fresh writes.* The first commit of B.2.4 set `action = "regenerated" if private_key_path.exists() else "wrote_new"` AFTER calling `write_bytes` — by then the file always exists. Caught by the live smoke test, not by unit tests. Capture pre-write state in a local before any I/O.

**ASCII diagram — `jackpot init` data flow:**

```
operator runs `jackpot init configure --scenario T --instance-name tribal`
                                     │
                                     ▼
            ┌────────────────────────────────────────────┐
            │ schema/jackpot_scenarios/                  │
            │   scenarios.py: ScenarioDefaults registry  │
            │   detector.py:  pure inference policy      │
            └────────────────────────────────────────────┘
                                     │
                                     ▼
            ┌────────────────────────────────────────────┐
            │ cli/jackpot/init/                          │
            │   detector.py:  Click-prompts wrapper      │
            │   github_vars.py: gh api detect-and-confirm│
            │   writers.py:   emit instance/<name>/*     │
            │   secrets.py:   JWT key + ed25519 keypair  │
            │   validator.py: /health smoke check        │
            └────────────────────────────────────────────┘
                                     │
                                     ▼
            ┌────────────────────────────────────────────┐
            │ instances/tribal/                          │
            │   jackpot.toml      ← canonical config     │
            │   .env.local        ← compose env vars     │
            │   values.local.yaml ← Helm overlay         │
            │   seed.sql          ← idempotent post-     │
            │                       alembic operator     │
            │                       seed updates         │
            │   secrets/          ← 0700, gitignored     │
            │     jwt_signing_key.txt              0600  │
            │     federation_private_key.pem       0600  │
            │     federation_public_key.pem        0644  │
            └────────────────────────────────────────────┘
                                     │
                                     ▼
              docker compose --env-file instances/tribal/.env.local up -d
              jackpot init bootstrap --instance tribal
              # alembic upgrade head; psql -f seed.sql; poll /health
```

**Per-scenario compose-profile activation:**

```
Scenario A (laptop)        → COMPOSE_PROFILES=laptop      → postgres+minio+minio_init+api+ui
Scenario B/C/E single-org  → COMPOSE_PROFILES=single-org  → postgres+api+ui
Scenario D multi-tenant    → COMPOSE_PROFILES=multi-tenant→ postgres+api+ui
Scenario T tribal          → COMPOSE_PROFILES=tribal      → postgres+api+ui
Scenario F CI              → COMPOSE_PROFILES=ci          → postgres+minio+minio_init+api  (no ui)
```

**Pattern for future operator-bootstrap work:** the
schema/cli split, the per-instance directory contract, and the
idempotency+secret-preservation rules are reusable for ANY tool that
turns operator config into runtime state. The compose-profiles pattern
also generalises beyond Docker — any "one definition, multiple
deployment shapes" tool (Helm charts via `--set`, Terraform via
workspaces, etc.) benefits from the same matrix-as-contract
documentation pattern.

---

## Session 18 — strategic positioning pivot + I-track planning — 2026-05-04

**What was built:** Not code — a positioning reframe and a four-item adoption-driving feature roadmap (the I-track: I-1 spreadsheet importer, I-2 submission package generation, C-1 pluggable credentials, I-3 backend-driven submission). The session translated "JACKPOT cannot win against funded incumbents on institutional procurement" into a concrete plan targeting the underserved spreadsheet-refugee market.

**Key decisions:**

- *Adoption pitch is "replace your spreadsheets and folder archaeology", not "compete with Pathogenwatch."* Sanger/CGPS, NIAID/Argonne, CZI/SIB, NCBI/CDC will always have more credibility than a single-developer project. The structural gap is working researchers (academic labs, public-health labs in non-G7 countries, tribal research entities, agricultural/veterinary genomics, environmental microbiology) using Excel + folders + ad-hoc scripts because none of the funded platforms fit their workflow. That's a much larger user pool and a more achievable adoption goal than displacing an incumbent.
- *JACKPOT is upstream of Seqsender/TOSTADAS, not parallel.* Seqsender solves the protocol mechanics (file uploads, API calls, format conversion). What's missing is pre-submission metadata curation, lifecycle tracking (accepted/rejected/embargoed/withdrawn/updated), and governance work (which samples to submit, IRB sign-off, internal data-sharing committee approvals). I-2 produces Seqsender-compatible packages and tracks lifecycle; it deliberately does NOT implement protocol mechanics in v1.
- *I-2 v1 explicitly excludes credential management.* The "researcher's laptop closes and changes IPs" problem makes backend-driven submission Scenario-A-hostile. By generating packages instead of running submissions, JACKPOT never holds NCBI/GISAID/ENA credentials — sidestepping both the laptop-connectivity problem and the sovereignty-credentials problem in one move. Backend execution becomes I-3, gated on C-1 credential infrastructure, and explicitly Scenario-aware (laptop → warning + package generation only; server → backend execution available).
- *Pluggable credential infrastructure (C-1) ships three backends, not GCP-only.* Env vars (default, works everywhere), file-based YAML (config-management-friendly), GCP Secret Manager (cloud deployments). AWS / Azure / OS keychain backends ship later as needed. The credential abstraction is invisible to consuming code (submission, future LLM features, federation API keys) — see Critical Rule 62.
- *Sequencing: I-1 → (I-2 || C-1) → I-3.* I-1 is the largest piece and ships first. I-2 and C-1 touch entirely different files (different routers, different config layer); they can ship in parallel. I-3 ships after both. This sequencing held in execution: Session 19 shipped I-1 + I-2 in parallel cleanly; Session 20 shipped C-1 → I-3a → I-3b → I-3c in sequence.
- *Indigenous genomic sovereignty is a longer-arc opportunity, not a 90-day strategy.* Trust takes years not months in Indigenous research contexts (Havasupai case is in everyone's institutional memory). The right approach is co-development with tribal partners (Native BioData Consortium, SING workshop network, CEIGR), not "platform vendor pitches finished product." Worth doing as a multi-year arc; not the right path for the near-term adoption push.

**Watch out for:**

- *Phase prefix taxonomy now has two axes.* P0f/P0g/P0h encode architectural area (file-references / executor-profiles / Slurm). I encodes adoption category (import/integration). C is one-off (credentials). Future tracks may add S (submission/sharing) if I gets crowded. Re-check this convention as the project grows; today it's clear enough.
- *"Adoption-driving" is a separate axis from "architectural progress."* Both matter, but only one of them shows up in user-visible feature changelogs. When choosing what to ship next, factor in both — and avoid back-loading adoption work behind too many architectural phases.

---

## P0g — execution profiles (G-1 → G-4) — 2026-05-04 → 2026-05-05

**What was built:** Per-run executor selection across the seven supported executor types (LOCAL, SLURM, PBS, LSF, GCP_BATCH, AWS_BATCH, KUBERNETES). G-1 + G-2 (PR #21) shipped LinkML schema + Alembic migration + seed for `execution_profiles` and `pipeline_default_profile`. G-3 + G-4 (PR #28) shipped 8 Jinja2 templates (base + 7 executor-specific overlays) plus the `pipeline_config/` package refactor (single 277-line file → package with backward-compat re-exports), profile renderer/resolver/types modules, launch-endpoint integration, `Settings.work_dir` field, `LAUNCH_WITH_PROFILE` audit action, and 35 new tests. Codified in **Critical Rule 59**.

**Key decisions:**

- *Executor selection is per-run, not per-deployment.* The same JACKPOT instance can submit one run to local Nextflow, the next to a Slurm cluster, the next to GCP Batch — using identical pipeline definitions in the zoo. This is the architectural unlock that makes scenarios A through G feasible from a single codebase. Selection priority at launch: explicit `profile_name` in request body > pipeline's first matching default profile by `pipeline_default_profile.priority` > deployment's `is_default=true` profile > `400 NO_PROFILE_AVAILABLE`. Missing-or-inactive named profile returns `400 PROFILE_NOT_FOUND` listing available names.
- *Partial unique index `WHERE is_default = TRUE` enforces "at most one default."* Postgres-native enforcement instead of trigger or application-level guard. PL/pgSQL `INSERT ... ON CONFLICT (name) DO NOTHING` keeps the seed idempotent for re-runs.
- *Migration chained against the actual current Alembic head, not a `tail -5` of files.* G-1+G-2 migration's `down_revision` was set after `alembic heads` showed I-3a's `3644749bf4c6` as current. P1's auth-refresh migration was later rebased onto G-1+G-2's `bac8dbb11c0b` once that landed first. Always verify head with `alembic heads`; never pick from a directory listing.
- *`pipeline_config/` became a package with full backward-compat re-exports.* Pre-G-3 was a single 277-line module; G-3 split it into renderer/resolver/types/templates while keeping `pipeline_config/__init__.py` re-exporting every pre-package public name. The existing import line in `routers/pipelines.py` did not change.
- *Legacy GCP-Batch path preserved as fallback during the transition.* When `NoProfileAvailableError` is raised by the resolver, the launch endpoint falls back to the pre-G-3 GCP Batch path. Removal is a follow-up PR after G-5 (profiles CRUD endpoints) ships and operators have a UI to configure profiles. This is an explicit transition window, not a permanent dual code path.
- *Cross-cutting tests live at workspace-root `./tests/`, not member-internal.* The launch-endpoint integration tests touch multiple workspace members (backend + schema), so they ship at workspace root. Workspace-internal unit tests (renderer, resolver) stay in their member's `tests/`. The convention: scope dictates location.

**Watch out for:**

- *Quick-fast pipelines default to LOCAL during seeding.* file_detector smoke runs, DLP scans, validation always run on the API server. Heavy pipelines (PHoeNIx, MIRA-NF, MycoSNP-NF, aquascope) have no default seeded — operators pick at launch or set one. Don't seed defaults for heavy pipelines and risk a runaway local execution on an under-provisioned API host.
- *`weblog_reachable=false` is mandatory for HPC profiles where compute nodes can't reach the API.* Many clusters block outbound HTTPS from compute nodes. The launch endpoint reads this flag from `execution_profiles.config_overrides` and either includes the `-weblog` directive (default) or omits it and starts the log poller (Critical Rule 60). The two paths can coexist for redundancy because the receiver dedups on `(run_id, task_id, status)`.
- *4-backtick outer fences + 3-backtick inner fences for spec prompts containing nested code blocks.* Typora otherwise mis-renders and prompts paste-fail in Claude Code sessions. Codified after multiple paste failures during P0g spec drafting.

---

## P1 — auth refresh endpoint with single-use rotation — 2026-05-05

**What was built:** `POST /api/v1/auth/refresh` accepting refresh tokens from the `refresh` cookie (priority) or JSON body (`refresh_token`), with cookie-wins-when-both-present logic for confused-deputy defense. Refresh tokens are JTI-tracked in a new `refresh_tokens` table; rotation is single-use; replay of a rotated token triggers `TOKEN_REPLAY_DETECTED` PLUS bulk-revocation of all the user's active refresh tokens PLUS an `AUTH_TOKEN_REPLAY_DETECTED` audit event. APScheduler job `cleanup_old_refresh_tokens` purges old revoked + expired rows past retention. Closes the deferred Phase 22 review item 12 / spec.md §13 fix #5 / P0e C.5 deferral. PR #22 (`ba03143`).

**Key decisions:**

- *Replay revocation must happen before raising the HTTPException.* The original implementation raised first, which short-circuited the audit-write side effect. Caught in the test phase: `fix(p1) — replay-detected revocation must happen before raising the HTTPException so the audit event fires`. Order matters when an exception is the primary control flow exit.
- *Cookie wins when both cookie and JSON body are present.* This is confused-deputy defense — if a malicious page tricks a user's browser into POSTing a body-supplied refresh token, the legitimate cookie token is the one that gets rotated. The body path exists only for non-browser clients (CLI, SDK).
- *Single-use rotation, not sliding TTL.* Each refresh issues a brand-new refresh token and marks the old one `revoked_reason=rotated`. Subsequent presentation of the rotated token IS the replay signal. JTI registration happens at issue time in `POST /google/login` and `POST /auth/refresh`; revocation happens at rotate time and at `POST /logout`.
- *Bulk-revocation on replay is defense in depth.* If a refresh token has been replayed, the assumption is the family is compromised. All active refresh tokens for that user are revoked, forcing re-authentication. This is more aggressive than necessary in some attack models, but the surface area of getting it wrong is small (user re-logs in) versus the surface area of getting it right (bulk-revoke catches the case where the attacker has the entire family).
- *Lifetimes: 15 min access / 7 d refresh / 30 d retention after revoke / daily cleanup.* `access_token_lifetime_seconds=900`, `refresh_token_lifetime_seconds=604800`, `refresh_token_retention_after_revoke_seconds=2592000`, `refresh_token_cleanup_interval_seconds=86400`. The 30-day retention preserves replay-detection ability for a month after revoke; older rows are purged for storage hygiene.
- *Three audit-action constants reserved at this PR.* `AUTH_TOKEN_REFRESHED`, `AUTH_TOKEN_REPLAY_DETECTED`, `AUTH_LOGOUT`. Plus `AUTH_TOKEN_REVOKED_BY_ADMIN` reserved-but-not-used for future admin-revoke functionality. Reserve the constant when the design implies the audit event, even if not yet emitted — it avoids churn later.

**Watch out for:**

- *`POST /logout` must work with missing/malformed/expired cookies.* Best-effort revoke before clearing cookies. Never raise from logout — the user already wants out.
- *Migration `down_revision` rebased once.* Original was `3644749bf4c6` (I-3a head, current at spec time); rebased to `bac8dbb11c0b` (G-1+G-2) once that landed first. The rebase was a single line edit, not a migration rewrite. Rebase migration `down_revision` rather than rewriting when the only change is parent reference.
- *Concurrent-refresh race.* If the same browser tab fires two refresh requests in flight (e.g. from a multi-tab UI), the first wins and rotates; the second presents an already-rotated token and triggers `TOKEN_REPLAY_DETECTED` → bulk revoke. Mitigation lives in the client (single-flight refresh promise) rather than the server. Front-end clients must serialize refresh.
- *Broader auth review intentionally deferred.* Session-management UI, refresh-token-family tracking, cross-device session detection, configurable token lifetimes per-user/per-role, token introspection endpoint, MFA, new auth providers (OIDC/SAML), API-token rotation, and B-FED-1 federation peer authentication are all logged in todo.md Phase P1 "What's deferred" subsection. Each is a separate design conversation, not a P1 increment.

---

## Worktree contamination — Sessions 20-21 saga + Critical Rule 61 — 2026-05-04 → 2026-05-05

**What was built:** Not code — a verification ritual codified as **Critical Rule 61**, after a severe case of cross-tree contamination during parallel-track Claude Code execution that almost cost the P1 work and consumed roughly half a session in diagnosis and surgical extraction. The mitigation is mechanical: assert `pwd -P` matches the expected worktree path, assert `git branch --show-current` matches the expected branch, refuse to proceed if either fails. Session 22 PR #27 (`c7df002`) committed the rule.

**Key decisions:**

- *The rule has teeth at session start, not in code review.* The check is the FIRST action of every Claude Code session running in a worktree. By the time bad commits are visible in code review, recovery is already expensive — the cheapest insurance is a 5-line bash check that refuses to proceed. Codified as Critical Rule 61.
- *Never `git switch` inside a worktree.* Each worktree is pinned to its anchor branch by virtue of being created with `-b`. Switching inside a worktree is what allows cross-tree contamination to happen in the first place.
- *Five-second pre-feature-branch verification trinity.* When running `git switch -c <branch>` from `development`, run `git pull --ff-only` + `git status --short` + `git log --oneline -3` against `origin/development` to confirm no local-only state silently scoops into the new feature branch. This caught the orphan-commit fallout in Session 22 (`152546b "updated docs"` got accidentally bundled into PR #26 because the governance feature branch was created from local development with that uncommitted commit, not from `origin/development`).
- *Surgical extraction beats wholesale recreation when work is at stake.* Recovery used `git checkout 'stash@{0}' -- <pathspec>` to extract only the truly-pure-P1 files, leaving contaminated `schema/schema/jackpot_schema.yaml`, `schema/schema/jackpot_schema.json`, and `backend/backend/models_generated.py` behind because they had cross-track P0g content mixed in. Don't blanket-restore from a contaminated stash; pathspec-restore only the files you've verified clean.
- *When parallel sessions share a single working tree, stashes are also shared.* Cross-session `git stash push` and `git stash pop` operations can pop each other's stashes. The corollary: if multiple Claude Code sessions are running on the same repo, EACH must work in its own `git worktree add <path>` directory, not the main clone. Stashing across sessions in a shared cwd is unreliable.

**Watch out for:**

- *Stash labels lie when they're written under duress.* The stash label `"phase-24.5: WIP across branches before rebase"` captured the actual cross-track contamination, not just Phase 24.5 work. Read the diff, not the label, before extracting.
- *Local branch refs can vanish silently.* The local `chore/pin-ruff-version` branch ref disappeared at some point during the saga. Rely on origin and on PR state, not on local refs, when reconstructing what shipped.
- *macOS `.DS_Store` blocks `git worktree remove`.* First attempt at removing `~/Projects/jackpot-p1` failed with "Directory not empty" because of a leftover `.DS_Store` from Finder. `--force` cleaned it up. Environmental quirk, not workflow issue, but worth knowing.
- *Test count and coverage are reliable signals of recovery completeness.* After P1 + P0g G-1+G-2 + P0g G-3+G-4 landed via the recovery path, baseline was 1527 tests passing, 87.85% coverage. If those numbers had regressed, something went uncaptured. Always re-baseline post-recovery.
- *Branch from `origin/<base>`, not local `<base>`, when local has unpushed commits.* The PR diff stays clean against the published state, and the unpushed commits land via their own PRs without getting bundled into unrelated work.

## P0c — Multi-tenancy middleware — 2026-08-29
**What was built:** `TenancyMiddleware` attaching org context (`request.state.org_context`) to every non-exempt request, the `get_org_context`/`require_org_access` guards, and the BYOP IDOR fix scoping all five mutating byop endpoints to owner/owner-lab/platform-admin.
**Key decisions:**
- Tenant identifier is `users.organization_id` from the authenticated principal — no tenant header invented; a header would be a second identity source the JWT doesn't vouch for.
- Cross-org denial is 404, not 403 (access_model.md §3.3: a tenant must never learn another tenant's resources exist). Missing org context is 403.
- Middleware is fail-open (resolution failure → context None, guards still refuse) so it can never 500 a request; enforcement lives in the guards.
- No migration: `byop_pipelines.owner_lab_id` already shipped in P0b DDL (`c871b28bbdab`); the router ORM just hadn't mapped it. P0c is application-layer only.
- BYOP list + detail reads stay unscoped per design §9 (bioinformaticians browse the catalog) — documented inline so reviewers see it's deliberate.
**Watch out for:**
- Middleware resolution duplicates the `get_current_user` DB lookup routes make via `Depends`; acceptable now, dedupe when M2 wires `permit()`.
- `_user_in_lab` in byop.py wraps `get_user_lab_membership` (Postgres) so the SQLite test harness can monkeypatch it — new lab-scoped guards should use the same seam.
- Per-endpoint capability enforcement is NOT P0c — it's the M2 cutover (access_model.md §10.3/§11); the endpoint→capability sweep lives in docs/endpoint_capability_map.md.

## M2 pre-cutover verification harness — 2026-08-29
**What was built:** Dark equivalence harness proving M0 permit() / M1 visibility / ACCESS-SEED reseed on real PostgreSQL before the irreversible M2 cutover (tests/authz/preflight.py + test_cutover_preflight.py, scripts/m2_preflight_report.py, docs/m2_preflight_report.md; PR #140).
**Key decisions:**
- Divergences legacy-vs-new are registered, not hidden: `EXPECTED_DIVERGENCES` maps each class to a predicate + rationale; tests assert zero unregistered divergences AND that every registered class still fires (stale-expectation check).
- Visibility safety invariant is unconditional: new clause must never over-grant (new ⊆ legacy per persona); narrowing is allowed and documented, widening fails the build.
- Report generator imports the registry by file path so rationales cannot drift from the tests.
**Watch out for:**
- `instance://self` does NOT contain `lab://N` (_scope_contains is URI-prefix) — reseeded admin grants match no lab resources. M2 blocker: scope redesign or admin ALLOW policy.
- Live chain lacks the grants unique index; reseed idempotency exists only after the staged migration creates it. Ordering pinned by test_reseed_duplicates_without_index.
- `tests` dotted imports are shadowed by cli/tests (regular package from the editable cli install); use `authz.preflight` under pytest, file-path import in scripts.
- Repo-wide gotcha: `git stash pop` in a worktree can pop ANOTHER session's stash — stashes are shared across worktrees. Check `git stash list` before pop.

## M2-B2 — sample-plane route guards — 2026-08-31

**What was built:** 20 of the 27 sample-plane routes moved off their in-route
ownership/visibility/director checks and onto `require_capability(...)`, and
the guard grew the attribute half it needed to make those decisions correctly.

**Key decisions:**

- **The guard now passes `LADDER_POLICIES`, not `policies=[]`.** M2-B1 left a
  note saying the attribute-policy paths "belong to the sample-visibility
  plane". That reading was too narrow: they belong to any *sample-scoped
  decision*, list or detail. A PUBLIC sample is readable by a non-member on
  the detail route too, and no grant expresses that — only a policy reading
  the row does. Passing the set on every call, including lab- and
  instance-scoped ones, is safe rather than sloppy: every policy predicate
  reads a resource attribute, a resource carrying none matches nothing, and
  the set has no DENY entry, so it can only widen and only for a sample.
- **`sample_resource()` fetches scope and attributes in one query.** The
  alternative — resolve the scope, then fetch attributes separately — costs a
  second round trip per request and invites the failure where one is fetched
  without the other. A guard holding the scope but not the attributes
  evaluates every policy against a missing value, which reads as DENY: the
  permissive rungs disappear silently rather than erroring.
- **`access:request` had to be a policy.** It appears in no §8.2 preset, and
  adding it to one would not have worked: the requester is by definition not
  a member of the lab they are asking about, so a lab-scoped grant never
  contains the target sample's scope, and an instance-scoped grant issued to
  everybody is the same thing as no check at all. The rule is a fact about
  the row — "this sample invites requests" — which is what an
  attribute-policy is for. It replaces the in-route
  `REQUESTABLE_SHARING_LEVELS` test one-for-one.
- **Seven list routes were NOT converted, and could not be.**
  `require_capability` resolves exactly one resource scope. A list endpoint
  names none; its authorization *is* the row filter. Guarding one at the
  instance root would require an instance-wide grant and deny every ordinary
  lab member the entire endpoint. They belong to M2-B7, which already owns
  compiling these rules into SQL. Recorded in the backlog and the map rather
  than approximated.
- **404 stays ahead of 403 on the sample routes.** The fetch runs first, so
  an archived or tombstoned sample is still "not found" rather than
  "forbidden" — that is `_get_sample`'s filter talking, not the authorization
  model. On the *file* routes the opposite convention already held (a denial
  collapses into `FILE_NOT_FOUND`), so the guard's `HTTPException` is caught
  and swallowed there. Letting the 403 through would have re-leaked the
  existence that helper exists to hide.

**Watch out for:**

- `promote` is a deliberate **widening**. The map assigns `sample:update`,
  which `lab_member_rw` holds; the legacy branch demanded a Lab Director. If
  the narrower rule was intended it needs its own verb, not a re-added
  branch.
- The `raw_fastq` Lab-Director check in `download` is deliberately still the
  legacy check. No §4 verb names "pre-scrub reads", and dropping it to finish
  the rewrite would have widened access to un-scrubbed data.
- **Project-only membership loses access here.** The legacy ladder admitted a
  project member; no preset grants at Project scope. Known and counted by
  reseed's pre-flight (`project_only_membership`), but B2 is where it first
  becomes reachable from a route.
- Ingest gained a check it never had: `lab_id` arrives in the caller's own
  metadata and nothing verified it, so any authenticated user could ingest
  into any lab. The CSV path checks per row, memoized per lab — without the
  memo a 1000-row upload would add 2000 queries.
- A stale `m2-b2-sample-plane` branch from the aborted 2026-08-31 attempt
  still pointed at `b95a218`, three commits before the PRE work. `git diff
  development...branch` was empty, which reads as "identical" but also means
  "strict ancestor". Check `git log HEAD..development`, not just the diff.

**ASCII diagram — where a sample-plane decision comes from after B2:**

```
  route (samples/files/imports/sample-access/ingest)
      |
      |  require_capability("sample:read_detail")(user, sample_id=42)
      v
  +---------------------------- guard ----------------------------+
  |  load_principal(user.id) ---> grants  (authz_capability_grants) |
  |  sample_resource(42)     ---> scope   org://o/lab/proj/sample   |
  |                           \-> attrs   sharing_level, owner_id,  |
  |                                       surveillance_relevant     |
  +---------------------------------------------------------------+
      |
      v
  permit(principal, capability, Resource(scope, attrs),
         Context(now=...), policies=LADDER_POLICIES)
      |
      +-- DENY policy matches? ------------------> DENY   (deny-wins)
      +-- grant covers scope, unexpired? --------> ALLOW  (structural)
      +-- ALLOW policy matches attrs? -----------> ALLOW  (attribute)
      +-- otherwise ----------------------------> DENY   (default)

  Lists take neither path yet — no single resource to name.  -> M2-B7
```

## M2-B3-PRE — pipeline:read holders and Project-scope resolution — 2026-09-01

**What was built:** the two prerequisites M2-B3 turned out to be blocked on,
plus map corrections for two document contradictions the same investigation
surfaced.

**Key decisions:**

- **`pipeline:read` went into every lab preset, read-only included.** It was
  in the §4 catalog but in no preset, so every route needing it was reachable
  by nobody — the third instance of that exact failure, after
  `pipeline:promote` and `pipeline:register_custom` in M2-B1. The catalog and
  the presets are two lists that have to agree and nothing checks that they
  do; `test_every_lab_preset_holds_pipeline_read` now checks this one, at the
  presets rather than at a route, so it fails where the capability goes
  missing.
- **Run-status reads are `pipeline:read`, not `pipeline:run`.** The map and
  §4 disagreed. §4's wording is explicit — "the pipeline zoo, the BYOP
  registry, and run status" — and `pipeline:run` is not held by read-only
  members, so taking the map literally would have removed run visibility from
  every Lab Reader watching a run on their own lab's samples. Watching a run
  is not launching one. (This entry first said `pipeline:run` sat only in
  `lab_lead` plus a Bioinformatics User extra. That was the reseed's
  misreading rather than §8.2 — M2-B3 found and corrected it; see that entry.)
- **BYOP catalog reads stay unscoped.** The map said `pipeline:read` at Lab;
  `byop.py` said reads are "INTENTIONALLY unscoped per design §9 (catalog
  browse)". Resolved toward the router: a pipeline definition is not tenant
  data, and this is the same shape as the sequencing-lab registry the map
  already calls AUTH-ONLY BY DESIGN. Mutations stay tenancy-guarded. The
  by-design count in the pre-flight suite moved 7 → 10 with a comment saying
  why, rather than being loosened to a range.
- **Project scope resolves like the other levels.** `scope_uri(project=…)`
  already existed; what was missing was `project_resource_scope()`. Naming the
  project rather than approximating it by its lab is what lets a cryptWWDB
  service principal hold `pipeline:write_results` on one project and nothing
  else (§9.4). Containment still runs downward, so a lab member's `…/lab/7`
  grant covers `…/lab/7/project/12` — scoping down costs existing members
  nothing, which two tests pin from both directions.
- **The guard's "not both" rule became "exactly one."** With a third
  identifier, a pairwise check would have needed three comparisons and would
  quietly miss the fourth when a fifth level arrives. It now counts what was
  passed and names them in the error.

**Watch out for:**

- B3 proper is 11 routes now, not 16 — three BYOP reads became auth-only and
  two are B7-class lists.
- Two open questions for B3, neither blocking: BYOP `owner_lab_id` is
  NULLABLE, so a lab-less pipeline has no lab scope to check against; and
  `_get_or_404_tenancy`'s "registering user" rung is an ownership rung with no
  grant behind it — the same shape sample ownership needed an attribute-policy
  for in PRE-A.
- The backlog's B3 note claimed M2 must "land the catalog entry" for
  `pipeline:read`. It was already in §4. Read the catalog before believing a
  note about it.

## M2-B3 — pipeline and BYOP route guards — 2026-09-01

**What was built:** the 11 remaining pipeline-plane routes moved onto
capability checks — 7 BYOP mutations, launch, resume, and the 3 run-status
reads.

**Key decisions:**

- **The schema had already answered the two "open questions".**
  `owner_lab_id` is nullable because `sharing_scope` admits `'private'` — a
  pipeline belonging to a person, not a lab. That makes the nullable column
  correct rather than a hole, and makes the registrant rung an ownership
  policy of exactly the shape PRE-A built for samples. Neither needed a
  judgement call; both needed reading the DDL.
- **Creation must not use the ownership rung, and a test caught it.** The
  first cut routed `create_pipeline` through `_may_manage`, which passes
  `registered_by_user_id`. At creation the caller *is* the registrant, so the
  policy matched every time and the lab check became vacuous — any
  authenticated user could register a pipeline into any lab. This was a
  widening, the direction that does not fail closed. Caught by an existing
  tenancy test (`test_byop_create_into_foreign_lab_is_403`) returning 201, and
  now pinned by its own regression test.
- **BYOP tests run the real engine against stubbed DB lookups.** Those router
  tests use in-memory SQLite with no Postgres, so the tempting move was to
  patch `_may_manage` wholesale. That would have asserted the test's copy of
  the ownership rule instead of the rule. The `authz_grants` fixture stubs
  only `load_principal` and the scope resolvers — the parts that touch a
  database — and lets the real `permit()` and the real `LADDER_POLICIES` run.
- **`_may_read_run` and the launch check are separate functions on purpose.**
  Reading a run is `pipeline:read`; launching and resuming are `pipeline:run`.
  A single shared helper would have made it one edit to collapse the
  distinction the whole batch exists to draw.
- **The per-sample launch checks were converted, not dropped** (the backlog
  entry is explicit). They moved from "is the caller in this sample's lab" to
  `sample:read_detail` at the sample's own scope, which additionally admits
  PUBLIC samples, the caller's own, and per-sample grants — paths the lab test
  could not see at all.

**Watch out for:**

- **A citation I repeated four times did not hold, and the review caught it.**
  I wrote "§8.2 puts `pipeline:run` in lab_lead + Bioinformatics User only" in
  the router, the map, this file and the backlog, and built a "deliberate
  narrowing" on it. §8.2's Lab Member (read-write) preset block lists
  `pipeline:run` outright — "can run pipelines but not approve submissions or
  access requests". The claim came from `reseed.py`, which excluded the verb
  from `lab_member_rw` on a misreading of §8.5's role-mapping prose, and I
  took the code's behaviour for the spec's intent because they were the only
  two things I checked against each other. The fix runs the other way: the
  reseed now grants it, `BIOINFORMATICS_EXTRA` is gone, and §8.5's phrasing is
  corrected so it cannot re-create the confusion. Launch access is unchanged
  for Collaborators; only read-only members lose it.
  The general lesson: when code and prose agree, that is one source, not two.
- A test that passed alone failed in full-suite order: `'Other Lab'` already
  existed, created by another module *without* a project, and the helper only
  seeded the project on the lab-insert path. Ensure each half independently.
- `POST /{run_id}/resume` takes a body, and FastAPI validates the body before
  the handler runs — a guard test that omits it gets 422, not 403, and proves
  nothing about the guard.

## M2-B7 — list endpoints onto visibility_sql_clause — 2026-09-01

**What was built:** all 8 list endpoints moved off `permissions.py`'s
hand-written ladder and onto filters compiled from the same grants and
policies `permit()` reads. `backend/permissions.py` now has zero production
callers.

**Key decisions:**

- **The equivalence harness was proving the wrong thing, and that came
  first.** `test_new_never_over_grants` and the per-row agreement test both
  ran with `policies=[]` — grants only. That is a strict subset of what a
  deployed list shows, so the proof described something nobody would run, and
  it would have stayed green while production silently dropped every PUBLIC
  and DISCOVERABLE row. Pointing them at `LADDER_POLICIES` and
  `SAMPLE_ATTRIBUTE_COLUMNS` *before* touching a router is what made the rest
  of the batch safe: the invariant held, and the per-row test failed exactly
  where it should have — it was still asking `permit()` a question without
  the attributes half the fragment's terms read.
- **One builder, not eight call sites.** Scope expression, policy set and
  attribute-column mapping all have to match the row-wise guard. Assembling
  them per route is how the two halves drift, and a list that drifts wider
  leaks rows with no error and no audit row. `sample_list_clause` assembles
  them once; routes pass table aliases.
- **Three scope levels, because not every list is sample-rooted.** Import
  sessions live at lab level and pipeline runs at project level, and
  `scope_sql` only emitted the sample path. `lab_scope_sql` and
  `project_scope_sql` fill that in. Both new builders pass **no policies** on
  purpose: every `LADDER_POLICIES` entry reads a sample attribute, and
  compiling those against a table that has no such column is either an error
  or, worse, a term that silently matches nothing.
- **`is_canonical_scope_sql` still byte-compares.** It now re-derives every
  candidate shape from the aliases it finds rather than loosening its regex to
  cover three forms. A regex that admits three shapes is one edit away from
  admitting four.
- **Two ownership rungs kept, two admin bypasses removed.** The request list
  and the run list each keep "rows you created" — no grant expresses that, and
  removing it would narrow access this batch was not asked to narrow. Both
  lost their `is_platform_admin` branch, because an instance-scoped grant
  already contains every path beneath it. The request list also lost its
  `is_lab_director` subquery, and the replacement is strictly more
  expressive: a director whose grant sits at org scope now sees their org's
  requests, which `lab_id IN (...)` could not express.

**Watch out for:**

- Every one of these queries now needs `JOIN labs` in reach. A sample's scope
  is derived from its lineage (ADR 0015) and the org segment comes from
  `labs.organization_id` — forget the join and the query fails loudly, which
  is the good case.
- `select_all` on the samples list is a separate code path from the paginated
  one. A filter applied to only one of them is exactly the gap a page-only
  test misses; there is now a test asserting the two return the same set.
- **The equivalence proof does not reach two of the eight lists.** It is
  built on `samples`, so `imports/sessions` and `pipelines/` have route tests
  and nothing more. Worth being explicit about rather than letting "the
  invariant suite passes" imply coverage it does not have: the imports list
  strictly narrows (a lab rung added on top of ownership), while the run list
  *can* widen — an org-scoped `pipeline:read` grant would show every lab in
  the org, which the legacy `lab_id IN (…)` form could not express. No preset
  issues org-scoped grants today, so the sets currently match.
- **The performance worry was backwards.** The backlog flagged that prefix
  `LIKE` over a computed expression cannot use an index and asked for a
  measurement. At 3,000 samples the new fragment costs 113 and runs in 5.3 ms;
  the legacy ladder costs 3,923 and runs in 7.1 ms. Both sequential-scan
  `samples`; the legacy one *also* ran four correlated `EXISTS` subqueries. No
  index added — it would have been speculative, and this is an improvement,
  not a regression.

## M2-B6 — SERVICE-principal pipeline callbacks — 2026-09-01

**What was built:** the two per-run callbacks (`/pipelines/events`,
`/pipelines/{run_id}/results/{result_type}`) gained an authorization call
beside their existing token check. First `PrincipalKind.SERVICE` on the route
surface.

**Key decisions:**

- **The token check did not move, shrink, or change.** It is the
  authentication half and the backlog said so explicitly. Authorization was
  added *after* it, and the ordering is deliberate: a bad token answers 401
  (who are you), not 403 (you may not), because a 403 would confirm to an
  unauthenticated caller that the run exists and is writable. Pinned by a
  test.
- **The positive check cannot fail today, and the docstring says so.** The
  principal is constructed from the same run the token authenticated against,
  so `permit()` always ALLOWs. Writing that down was more useful than
  inventing a failure mode to make the check look load-bearing. What the
  separation buys is the chokepoint: at M4/M5 a `data_source_lab` peer
  carrying the §8.4 preset reaches the same route with a different capability
  set, and the answer changes there rather than in the route.
- **The negative half is what is load-bearing now.** The principal holds
  `pipeline:write_results` and nothing else, so `permit()` refuses it
  `sample:read` and `sample:read_detail` on the samples its own run computes
  over. §8.4: "The absence is the security property, not an oversight." A
  capability set is only a security property if something breaks when it
  grows, so the set itself is asserted, along with the scope not reaching
  another project, the enclosing lab, or the instance root.
- **A run without `project_id` raises rather than falling back.** The column
  is NOT NULL, so a row lacking it means the caller did not SELECT it —
  which is exactly what the results route was doing before this batch.
  Defaulting to the instance root there would have handed a pipeline callback
  authority over the whole deployment; raising turns that mistake into a 500
  instead of a silent widening.

**Watch out for:**

- The results route's query now selects `project_id`. If a future edit drops
  it, `pipeline_run_principal` raises — loud, which is the intent — but the
  reason will not be obvious from the traceback alone.
- These grants are *constructed*, never stored. Nothing in
  `authz_capability_grants` should ever match one; `source="pipeline_token"`
  marks the difference.
- The engine still applies `not_after` to a SERVICE principal. Unused today
  (these grants carry no expiry) but asserted, so a future "services do not
  expire" shortcut has to break a test to land.

## M2-B4 — submission and import-mapping guards — 2026-09-01

**What was built:** 21 routes converted, and the systemic gap behind four
batches' worth of blockers closed.

**Key decisions:**

- **The blocker was one root cause, not six.** Six of B4 and B5's verbs were
  in no preset. So were two that M2-B1 found and one that M2-B3-PRE found. All
  eight came from the same event: the M2 catalog review added verbs to §4 and
  nobody updated §8.2's preset blocks. Fixing the six without fixing the
  mechanism would have left the seventh for the next batch.
- **The guard runs in four directions, and two of them are about the docs.**
  Catalog→preset catches "reachable by nobody". Preset→catalog catches a typo,
  which is silent otherwise — the grant is issued and matches nothing.
  §8.2↔`PRESET_GRANTS` catches the drift that caused M2-B3's `pipeline:run`
  bug. And the allowlist is checked for rot, so an entry cannot quietly
  contradict a later grant.
- **"Held by no preset" is a legitimate answer, so the test demands a reason
  rather than a grant.** Eight verbs are deliberately unheld — SERVICE verbs,
  peer verbs, one carried by an attribute-policy, one deferred to M3, one with
  no route yet. Requiring prose (and asserting it is longer than a shrug)
  turns each into a decision on the record.
- **prepare vs approve is a real narrowing and the tests say so.** The old
  check let a submission's creator send it. Six routes now need a Lab Lead.
  The creator rung is subsumed, not dropped — creating already required
  `submission:prepare`.

**Watch out for:**

- **The existing submission suite stayed green through all of this**, because
  the seeded admin is both a platform admin *and* Lab Director of lab 1, so it
  holds `lab_lead` and passes both halves. A batch whose whole point is a
  boundary needs a test that stands on each side of it; the general lesson is
  that a fixture holding every capability cannot detect a split.
- **FastAPI validates the request body before the handler runs**, so a guard
  test posting an invalid body gets 422 and proves nothing. This bit M2-B3
  (`/resume`) and bit twice more here (`mark-rejected` and `withdraw` both
  require a `reason`). Every "should be 403" assertion needs a *valid* body.
- An Instance Administrator holds neither `submission:prepare` nor
  `sample:read`, so a platform admin who is not a lab member cannot create or
  read a submission. That is consistent with `sample:create`, which admins
  also lack, and with §8.2's "Instance Administrator is operational, not a
  consent authority" — but it will surprise someone.
- **The catalog guard checks presence, not reachability, and that gap bit
  inside the same batch.** `GET /submissions/` unfiltered used to gate on
  `is_platform_admin`; swapping that for `sample:read` at the instance root
  produced a branch nobody could take, because every preset granting
  `sample:read` issues it at *lab* scope. The new test would not have caught
  it — a verb can be in a preset and still be unheld at the scope a route
  asks about. Found by reading the presets by hand while writing this entry,
  and independently by the review; fixed by making the route a filtered list
  (M2-B7's builder) instead, which removes the branch rather than repairing
  it. The limitation is now written into the test's own docstring.

## M2-B5 — governance route guards — 2026-09-01

**What was built:** 13 of 14 routes converted, plus the change that makes
membership mean anything after cutover.

**Key decisions:**

- **Membership now issues grants, and that was the point of the batch.** A
  `lab_membership` row stopped being a decision input at M2-B1, so a member
  added after cutover held nothing until someone ran a reseed — the row said
  Lab Collaborator and every route disagreed. `POST/PATCH/DELETE
  /labs/{id}/members` now sync grants on the request's own connection, so the
  row and the access land in one transaction; a half-applied pair is a member
  who is either invisible or over-privileged. §4.5 already scoped
  `user:manage` as "create/modify/deactivate users, **assign capabilities**" —
  issuing them is that assignment, not a side effect.
- **Delete-then-insert, scoped by `source`.** Syncing a changed role by diffing
  would have to reason about which of the old group's capabilities the new one
  also has. Replacing outright is simpler and obviously correct, and scoping
  the delete to `source='reseed'` keeps it off the per-sample access grants
  (`source='direct'`) that share the principal. Pinned by a test.
- **Split routes stay split.** `tokens` and `users` gate only the half that
  reaches another principal. Self is not a capability and cannot be: §3.1's
  scope tree has no user level, so "you are yourself" stays an identity
  comparison (§4.7). Gating the whole route would take every user's control of
  their own credentials.
- **One route was left auth-only on purpose.** `POST /federation/search` — see
  below.

**Watch out for:**

- **"Held at lab scope" is not "held at instance scope", and that bit twice in
  two batches.** B4's `GET /submissions/` and B5's `/federation/search` both
  gated a verb at the instance root that every preset issues at lab scope,
  making a working route reachable by nobody. The catalog guard added in B4
  does not catch this — it asserts a verb is in *some* preset, not that
  anything holds it where a route asks. Both were caught by reading the
  presets by hand.
- **`/federation/search` is left auth-only and the map row now carries the
  question.** Enforcing `sample:read` at Instance would need an
  Instance Administrator to hold blanket `sample:read`, which contradicts §8.2
  head-on — the Surveillance Officer preset exists precisely so instance-wide
  sample reading is narrowed to `surveillance_relevant` rather than conferred
  wholesale. The act is "query our peers on this deployment's behalf", not
  "read a sample here", so the right verb belongs with §7's federation work
  (M4) rather than being invented here.
- **`GET /organizations/{org_id}` keeps a membership rung deliberately.** Every
  preset issues `org:read` at lab scope and containment runs downward, so a
  lab-scoped grant does not cover the org above it — checking `org:read` at
  org scope would deny every ordinary member their own organization. Making
  it structural needs org-scoped grants at reseed, which changes what a
  membership conveys rather than how a route reads.
- `GET /projects/` loses the `project_membership` rung — the registered
  `project_only_membership` divergence reaching one more route, not a new loss.

## M2 (part a) — catch-up reseed, and the premise that did not survive contact — 2026-09-01

**What was built:** the reversible half of the cutover — migration
`a1c7d94e6b28` (pre-flight guard, counts logged, idempotent catch-up reseed)
and the deletion of `backend/permissions.py` — after the session's opening
verification showed the irreversible half could not ship.

**Key decisions:**

- **The entry's central claim was false, and checking it was the session.**
  M2 said the column drop was "bookkeeping that happens to be permanent"
  because B1..B7 had moved every guard onto `permit()`. They moved every
  *guard*. They did not move every *reader*. `grep is_platform_admin` returns
  eleven production modules: the tenant wall in `tenancy.py`, five in-route
  checks in `samples.py`, the self-approve carve-out in `deletion.py`, the
  admin-notification lookup in `federation/deletion_propagation.py`, and the
  identity plumbing in `guards.py` / `auth.py` / `users.py` / `imports.py`.
  Dropping the columns would have 500'd every one of those paths. The lesson
  is not "the entry was wrong" — entries written months ahead usually are. It
  is that "nothing reads X any more" is a claim with a two-second check behind
  it, and an irreversible migration is the wrong place to find out.
- **The dependency was inverted.** `docs/endpoint_capability_map.md` assigns
  the deletion-lifecycle checks to M3, and M3 `depends_on: M2`. So M2 as
  written had to drop columns that M3's not-yet-converted targets still read.
  Split instead: M2 keeps part (a), `M2-DROP` takes the drop and is blocked on
  M3. A cycle in a backlog shows up as a task that cannot be done in either
  order, which is what this looked like from inside.
- **`permissions.py` deleted, its `visibility_sql_clause` frozen into the test
  tree.** Nothing in production imported the module by M2-B7, but two tests
  did, and one of them — the 2c list-equivalence proof — needs the *old*
  fragment to compare against. A comparator that lives in production code
  stops being a comparator the moment production changes. It now sits in
  `tests/authz/preflight.py` beside `legacy_ladder`, under the same "do not
  fix this to match new behavior" banner.
- **The catch-up's `downgrade()` is a deliberate no-op.** Its grants are
  byte-identical to the additive migration's — same `source`, same
  `(principal_id, capability, scope_ref)` — because they *are* the same
  grants, issued late. No predicate selects "the rows this migration inserted"
  without also selecting rows it did not. Deleting on `source` would silently
  de-authorize users this migration never touched, so it deletes nothing and
  says why.
- **Counts are logged, not just enforced.** `reseed()` raises on a non-zero
  pre-flight and logs nothing when clean, so a clean run left no evidence the
  check happened. The migration now calls `preflight_counts()` itself and logs
  every kind including the zeros. The authoritative refusal still lives in
  `reseed()` — this is a read-only echo, deliberately not a second
  implementation of the rule.

**Watch out for:**

- **Approving a sample-access request grants nothing.** The approve endpoint
  writes `sample_access_grants`, but the only translation into
  `authz_capability_grants` is `reseed._sample_access_rows`, which runs at
  migration time. Neither `authz/policy.py` nor `authz/visibility.py` has an
  approved-request rung. M2-B5 built `sync_membership_grants` for exactly this
  failure on the membership side; sample access has no twin. It fails *closed*,
  so it is a functionality gap rather than a hole — and that is why nothing
  caught it: the tests that would have were calling the legacy
  `can_access_sample()`, which read the table directly. Now `M2-SAMPLE-ACCESS-SYNC`.
- **A test helper that reseeds is a smell, not a fix.** `_can_read_detail` in
  `tests/test_sample_access_router_api.py` runs a full reseed to bridge that
  gap. It carries a pointer to the backlog entry. When the sync lands, the
  helper should call the route instead.
- **A directory named after a dependency silently reclassifies its imports.**
  Deleting `backend/alembic/` changed 20 unrelated migration files: ruff's
  isort had been resolving `alembic` as a *first-party local package* because
  a directory of that name sat inside the source tree, so `from alembic import
  op` was sorting into the first-party block everywhere. With the orphan gone
  the real third-party distribution classifies correctly. Nothing was broken
  before and nothing is broken now — but the repo had been carrying a
  lint-classification skew for as long as the directory existed, and it only
  surfaced because CI runs `pre-commit --all-files` while the local hook sees
  only changed files. That gap is worth remembering on its own: a green local
  commit does not mean a green `--all-files`.
- **`backend/alembic/versions/` was never on the chain.** `alembic.ini` points
  at `backend/db/migrations`. ACCESS-SEED deliberately parked a
  reads-then-drops migration in the unreachable directory to move it in at M2;
  ADR 0016 then split that design in two and M2 deferred the drop, leaving a
  committed file carrying `DROP COLUMN` that no chain could reach and whose
  design was superseded. Deleted. A staged artifact outside the build path
  ages badly precisely because nothing fails while it rots.

**ASCII diagram** — the two-migration split, and where the drop went:

```
  b2f47c1a9e30            a1c7d94e6b28              M2-DROP (blocked on M3)
  additive                catch-up  [this session]  ┌──────────────────────┐
  ┌──────────────┐        ┌──────────────┐          │ convert 11 readers   │
  │ CREATE UNIQ  │        │ preflight    │          │  7 decision-path     │
  │ INDEX        │        │  counts →log │          │  1 lookup            │
  │ reseed()     │───────▶│ reseed()     │─────────▶│  3 plumbing          │
  └──────────────┘        │  (no-op if   │          │ THEN drop columns    │
   grants inert:          │   caught up) │          └──────────────────────┘
   nothing reads          └──────────────┘           irreversible; last
   them yet                downgrade: no-op
                           (rows indistinguishable
                            from the additive run)
```

## M2-SAMPLE-ACCESS-SYNC — approving a request now issues the grant — 2026-09-01

**What was built:** `sync_sample_access_grants()` beside `sync_membership_grants()`,
wired into all five paths that change per-sample access, closing the gap where
an approved requester was denied until the next migration.

**Key decisions:**

- **The bug was invisible because the test bridged it.** Between M2-B2 (when
  the detail route started deciding on grants) and this change, approving a
  request wrote `sample_access_grants` and nothing else — no policy reads the
  request tables, and the only translation was `reseed()`, at migration time.
  The tests that should have caught it were asserting through the legacy
  `can_access_sample()`, which read the tables directly and therefore always
  agreed with itself. The M2 session replaced that with a helper that ran a
  full reseed, which bridged the gap just as effectively. Deleting the bridge
  turned exactly two tests RED — and the *negative* tests (revoked and expired
  deny access) had been passing the whole time for the wrong reason, because
  nothing was ever granted. **A fail-closed bug hides inside its own negative
  tests.** When a gap denies rather than allows, half the suite confirms it.
- **State-reconciling, not event-driven.** The function takes "this sample's
  access changed" and makes the grants agree. Callers do not say what they
  did. That is what lets one function serve approve, auto-approve, expire,
  tombstone-seal and reverse-tombstone without five different signatures —
  and the deletion lifecycle needs the requester-less bulk form anyway.
- **One query, two callers.** `_SAMPLE_ACCESS_SQL` gained optional
  `:sample_id` / `:requester_id` filters instead of the sync growing its own
  query. Two definitions of "who currently has access" would be free to drift,
  and the drift would be invisible: both produce grant rows that `permit()`
  reads identically. The `CAST(:x AS INTEGER)` wrappers are load-bearing —
  PostgreSQL cannot infer a type for a NULL bind parameter.
- **Deleting scoped by `source='direct'` and by the sample's own scope.**
  Membership grants live at Lab scope with `source='reseed'`; per-sample
  access at Sample scope with `source='direct'`. A delete predicate loose in
  either dimension would strip a Lab Reader's lab access every time one shared
  sample was revoked.

**Watch out for:**

- **`conn=None` is a supported call shape in this codebase.** `execute_write`
  documents it as "an auto-committed internal transaction", and
  `approve_deletion` accepts it — the federation deletion-propagation test
  calls it that way. Wiring a function that required a real `Connection` into
  that path failed with `AttributeError: 'NoneType' object has no attribute
  'execute'` in one test out of 2600. Being stricter than the code calling you
  is a compatibility break, not defensive programming.
- **The uniqueness arbiter has no `source` column.** It is
  `(principal_id, capability, scope_ref)`, so the same capability at the same
  scope exists once regardless of which subsystem issued it, and
  `ON CONFLICT DO NOTHING` silently skips the second. It does not bite today
  because membership and per-sample grants never share a scope — but a future
  preset that grants at Sample scope would collide, and the losing row would
  vanish without a word. A test asserting otherwise is asserting against the
  index, not the code.

## M3 — deletion-governance policies, and the two that weren't — 2026-09-01

**What was built:** `deletion.separation_of_duties` as a real DENY policy, the
condition-language negation form it needs, and the conversion of three
deletion-lifecycle routes onto capabilities. The other two policies §6.2
describes did not ship, for different and specific reasons.

**Key decisions:**

- **A spec section describing three policies contained one.**
  `no_publish_while_deleting` reads as a DENY on `submission:approve` — but
  that capability is checked once at *Lab* scope, while the rule is per-sample
  across the submission's whole set. `submissions.py:497` already enforces it
  correctly as a set-level query returning a 422 that names each blocked
  sample. A policy would have been strictly worse *and* wrong-shaped.
  `no_federate_deleting` keys on `federation:push`, which exists nowhere in
  the codebase outside an example string in a comment — no route, no grant, no
  guard. Both are now their own backlog entries. **Checking whether a spec's
  rule has a call site is part of implementing it**, and neither the backlog
  nor the report caught this because both were derived from the same section.
- **The first DENY in a shared policy set breaks an invariant nobody wrote
  down as fragile.** `guards.py` passes the whole set on every call, and the
  docstring justified it: *"a resource carrying none matches nothing, and the
  set contains no DENY entry, so it can only ever widen."* Both clauses matter.
  "Matches nothing" is true for equality and **false for negation** — absent is
  not equal to `"ACTIVE"`, so a `{"not": "ACTIVE"}` DENY on a lab-scoped call
  carrying no attributes fires and denies everything. The replacement invariant
  is now written down and tested: a DENY may only read attributes
  `SAMPLE_ATTRIBUTE_COLUMNS` loads, and may only key on a capability whose
  routes resolve a Sample resource.
- **Absent had to mean "the rule applies".** `_conditions_satisfied` was
  equality-only, so `{"platform_admin_self_approve": False}` would not match a
  context that never set the key — the separation-of-duties DENY would have
  silently not fired for every caller but one. That is a rule failing OPEN on
  the authorization path. Hence `{"not": v}`, mirroring the resource
  predicates' `{"in": [...]}`.
- **`visibility.py` held a second copy of the condition semantics.** A local
  `_live()` duplicating `_conditions_satisfied`'s body. Extending one and not
  the other would have split `permit()` from the SQL clause — the exact
  divergence the M1 equivalence suite exists to catch, arriving through the
  door that suite does not watch. It now calls the one definition.

**Watch out for:**

- **The preset is the source of truth, and the test that says so was right.**
  A draft added `deletion:request` / `deletion:approve` to the
  `instance_administrator` preset, reasoning from the B-CARE-3 design doc's §10
  matrix ("Platform Admin (any)"). `test_reseed_presets_match_the_documented_ones`
  rejected it, and reading §8.2's own note showed the omission was deliberate:
  *"Instance Administrator is operational, not a consent authority."* On
  Scenario T the consent authority is the Tribal authority; elsewhere the Lab
  Lead holds the verb at lab scope. **Two design documents disagreed, and the
  one that had already resolved the disagreement was the one I was editing
  away from.** The preset change and the migration written to propagate it
  were both reverted. When code and prose disagree, find out which one already
  thought about it.
- **Changing `PRESET_GRANTS` is inert without a migration.** Grants are rows,
  not a live view of the preset. Any future preset edit needs a reseed
  migration to reach existing deployments — the one written for this change
  was deleted along with it, but the requirement stands.

## M4-A — sharing agreements, landed dark — 2026-09-01

**What was built:** the `sharing_agreements` / `sharing_agreement_grants`
tables, `sync_agreement_grants()` projecting them into
`authz_capability_grants` with `source='agreement'`, and
`load_peer_principal()`. Wired into no request path.

**Key decisions:**

- **The third sync, and deliberately the same shape as the first two.**
  `sync_membership_grants` (M2-B5) and `sync_sample_access_grants`
  (M2-SAMPLE-ACCESS-SYNC) both take an operator-facing source table with its
  own lifecycle and project it into `authz_capability_grants`, delete-then-
  insert, scoped by `source`. Agreements are the same problem a third time.
  Following the existing shape rather than inventing a fourth is most of what
  made this small: `permit()` keeps one place to look, and a reviewer who
  understands one sync understands all three.
- **`load_peer_principal` is four lines and worth having anyway.**
  `load_principal` was already kind-agnostic — grants are keyed by principal
  id, and kind is an argument — so a peer needed no new loading path, and
  building one would have been the second decision point §2.1 warns about. The
  wrapper exists to be *findable*: someone asking "how does a peer get its
  grants" should not have to already know the answer is the human loader with
  a different enum.
- **Reconciles per peer, not per agreement.** A peer may hold several
  agreements, and the question the decision path asks is "what does this peer
  hold" — which no single agreement can answer. Deactivating one must withdraw
  exactly its grants and leave the siblings; a per-agreement sync would have
  to diff across them to get that right.
- **Two tables, not one with a JSONB `grants` blob.** The grants have the same
  shape as every other grant in the system, so the sync is a projection rather
  than a JSON parse whose schema drifts silently against the column it feeds.

**Watch out for:**

- **`federation_role` enum values are lowercase** (`'hub'`, `'spoke'`,
  `'peer'`, `'data_source_lab'`) while the sharing-level and deletion-status
  columns are TEXT+CHECK in upper case. A fixture inserting `'SPOKE'` fails
  with `invalid input value for enum federation_role`. The house style moved
  to TEXT+CHECK after that table was written; both conventions are live.
- **`conditions` must be `json.dumps`'d on a `text()` insert.** The column is
  JSONB and the driver will not adapt a bare dict through a textual statement.
  A condition that does not survive the projection is a grant with no filter —
  which is a silent widening, not an error.
- **The peer id namespace is a UUID string, user ids are integers.** They
  cannot collide today. The delete predicate is `principal_id AND source`
  anyway, and only the source half is what keeps that from being a landmine if
  the namespaces ever meet.

## M4-B — the inbound half that was never built — 2026-09-01

**What was built:** `POST /api/v1/federation/query` (peer-authenticated,
agreement-filtered), `client._query_one` repointed at it,
`FederationPushJob.may_push_sample()` composing `permit()` with the three
gates, and — on that call site — `sovereignty.no_federate_deleting`.

**Key decisions:**

- **§7.4 described an integration that did not exist.** It reads as though the
  inbound query already landed on the partner's `GET /api/v1/samples/`,
  filtered by the peer principal — "not a separate code path". In fact
  `/api/v1/samples/` authenticates a JWT cookie and nothing else, so a real
  federated query would have **401'd**. This is the third time in this run of
  work that a design document described a wired integration point ahead of the
  code (M3's `federation:push`, M3's `no_publish_while_deleting` shape, this).
  The pattern is worth naming: **a spec section written from the plan reads
  identically to one written from the code.** Only grep tells them apart.
- **The gap was invisible because the only tests were on the calling side.**
  Every federation-key test hit `/api/v1/federation/*`; the client tests
  mocked the partner with `respx.get(".../api/v1/samples/")`. So the suite
  asserted the client called a URL, and nothing asserted anyone answered it.
  Repointing the client turned 27 mocks red — which is the first time the
  inbound contract was ever expressed as a test.
- **Peer auth went beside the routes that already have it, not onto the
  samples list.** The alternative was a second authentication mode on the
  most-read endpoint in the system. What §7.4 actually cares about — that
  federated visibility is the same *decision* as local visibility rather than
  a parallel implementation — is preserved either way, because the filtering
  is `sample_list_clause`, the identical compiler every local list uses.
- **`may_push_sample` composes rather than absorbs.** `is_qualifying_sample`
  kept its own function, its own name, and its six tests; the new function
  adds the `permit()` half in front of it. Order is a cost decision, not a
  correctness one — but a peer with no agreement should not have its rows
  inspected at all.

**Watch out for:**

- **`{"not": v}` means opposite things on a DENY and on an ALLOW, and the
  difference is whether absence is safe.** On `sovereignty.no_federate_deleting`
  a missing `deletion_status` denies an export — fail closed, correct. The
  same form on a Lab-scoped `submission:approve` would deny every approval.
  The invariant in `DELETION_POLICIES` is what keeps them apart, and it is
  tested rather than merely written down.
- **`IS DISTINCT FROM`, never `<>`, when compiling a negation to SQL.** A NULL
  column with `<>` yields NULL, which is falsy, so the term silently drops and
  the DENY stops firing on exactly the rows it exists to catch. The per-row
  and SQL halves would then disagree — and only on NULLs.
- **`samples_deletion_active_requested_chk` couples status and timestamp:**
  `(deletion_status = 'ACTIVE') = (deletion_requested_at IS NULL)`. A fixture
  inserting a non-ACTIVE row without the timestamp is not merely rejected — it
  was never a state the system could reach, so a test built on one would prove
  nothing.

## M2-DROP-PRE slice 1 — an audited escape that anyone could take — 2026-09-01

**What was built:** `deletion:self_approve` as a real §4 capability, the route
deriving §6.2-1b's escape from what the caller holds rather than what they
sent, and `deletion.py`'s legacy `is_platform_admin` check removed.

**Key decisions:**

- **The bug was in M3, and inventorying M2-DROP is what surfaced it.** M3
  moved separation-of-duties into a DENY policy with `platform_admin_self_approve`
  as a Context condition — and the route set that condition straight from
  `payload.platform_admin_self_approve`. The policy never checks the caller is
  an admin, because a policy *cannot*: a condition is a fact about the request,
  and the engine has no way to know whether the caller was entitled to assert
  it. **Correct for an engine, dangerous for a router.** Verified directly:
  a non-admin with `deletion:approve` at lab scope got ALLOW with the flag set.
- **It was never exploitable, and that is exactly why it was dangerous.**
  `deletion.py` still re-checked `is_platform_admin`, so end-to-end behaviour
  was right. But that check was item 2 on M2-DROP's removal list. The hole
  would have opened during a mechanical "convert the readers" pass, in a PR
  about *removing columns*, where nobody would be looking for an authorization
  change. Defence-in-depth hid the defect from the tests and would have
  handed it to the drop.
- **A regression test that passes without the fix proves nothing.** The first
  version of the guard test passed either way, because `deletion.py` was still
  catching it. Removing that legacy check — M2-DROP-PRE work regardless — is
  what made the test isolate the fix. It now fails without the route change
  and passes with it, which was verified by reverting the change and running
  it, not by assuming.
- **The escape is a capability, not a role check.** `deletion:self_approve` is
  held only by `instance_administrator` and confers no approval authority of
  its own — an actor without `deletion:approve` still cannot approve anything.
  That keeps §8.2's "operational, not a consent authority" line true, and the
  note now says so explicitly so the addition does not read as contradicting
  the sentence above it.

**Watch out for:**

- **A policy condition is caller-supplied unless the router proves otherwise.**
  Anything reaching `Context.conditions` from a request body is an assertion,
  not a fact. If lifting a DENY depends on one, the router must AND it with a
  held capability — the engine will not do it for you.
- **Preset edits need a migration, every time.** `PRESET_GRANTS` is a template;
  the grants are rows. `deletion:self_approve` reaches no existing admin until
  a reseed runs, so the preset change ships with `c4d81a06f2b7`.
- **Doc and code preset blocks must move together.**
  `test_reseed_presets_match_the_documented_ones` compares §8.2's fenced block
  against `PRESET_GRANTS`, and §8.2's continuation lines have a 16-space
  indent contract the parser depends on.

## M2-DROP-PRE slice 2 — deletion-plane verbs — 2026-09-01

**What was built:** Five §4 capabilities (`sample:read_unscrubbed`,
`deletion:read_report`, `deletion:reverse_tombstone`, `deletion:vacuum`,
`submission:retract`) replacing the last in-line `is_platform_admin` /
`is_lab_director` reads in `samples.py`.

**Key decisions:**

- **The record/content discriminator.** The open design question was a read
  verb whose natural form (`sample:read_detail`) excludes instance admins by
  §8.2 while the legacy flag admitted them. Resolved by asking what the route
  returns, not how sensitive it is: an instance admin keeps a route that reads
  or executes a governance *record* and loses one that returns sample *content*
  or makes a consent decision. `deletion-report` keeps the admin (it is
  lifecycle state plus an audit trail — the line `audit:read` already sits on);
  `raw_fastq` and `retraction-requests` do not.
- **`submission:retract` is not `submission:approve`.** Holder sets match
  exactly on the non-admin path, so reuse was the lazy option. Rejected because
  retraction is the deletion plane reaching outward: one verb for both would
  hand repository-retraction to every future preset that gains submission
  approval for submission reasons.
- **Ownership needed a policy, not a preset.** `_require_lab_tie` had three
  rungs — admin, owner, lab member. Two are grants; ownership cannot be, for
  the reason already written on the `sample:read` rungs (a grant row per
  sample). Added a `LADDER_POLICIES` `owner_id` ALLOW for
  `deletion:read_report`, or an owner who had left the lab would have lost the
  report — a narrowing nobody asked for.

**Watch out for:**

- **`admin@example.org` is a dual-role principal.** The baseline migration
  seeds it as platform admin *and* Lab Director of lab 1. Every test acting
  "as admin" therefore holds `instance_administrator` and `lab_lead` grants at
  once and cannot distinguish them. Both deliberate narrowings in this batch
  left the whole existing suite green. If a test needs to prove *which* grant
  answered, build a principal with one shape — see
  `tests/test_deletion_plane_capabilities.py`.
- **Guard ordering vs 404.** `sample_resource()` raises for an unknown id and
  the guard turns that into 403, so a `require_capability(sample_id=…)` placed
  before the row fetch reports "not allowed" for a sample that does not exist.
  All four converted routes fetch first.
- **A route described in prose is not a counted route.** These four lived in a
  "Residue — still on the legacy check" section, so `parse_map` never saw them
  and the preflight row count stayed 128 while the map already discussed them.
  Converting them moved it to 132.
- **`_tombstone` test fixtures need `deletion_requested_at`.**
  `samples_deletion_active_requested_chk` asserts
  `(deletion_status = 'ACTIVE') = (deletion_requested_at IS NULL)`.

## deletion:request ownership rung — 2026-09-01

**What was built:** The `LADDER_POLICIES` ownership ALLOW for
`deletion:request` that M3's comment said already existed, plus §5.3's
ownership roster and `tests/authz/test_ownership_rung.py` enforcing it.

**Key decisions:**

- **The roster is a table in §5.3, not a registry constant in the test.** A
  constant listing the rungs would restate the code beside the code and agree
  with it by construction. The doc is the second recording of the decision, so
  the guard is doc-vs-code — the pattern `test_catalog_preset_coverage.py`
  already uses for §8.2's presets.
- **`sample:update` is a recorded `no`, not an omission.** The legacy ladder
  gave an owner everything; the capability model gives them read, report and
  request. Editing metadata on a sample whose lab you have left is a write
  into someone else's tenant, so it stays excluded — but as a row in the table
  rather than as an absence.
- **Requesting is not approving.** The rung is safe to add because
  `deletion:approve` is a separate verb with §6.2-1b's DENY, which beats any
  ALLOW unconditionally, so an owner reaching the request route cannot walk it
  to a completed deletion.

**Watch out for:**

- **`_matches` compares capability by equality.** An ownership rung for
  `sample:read_detail` does nothing for `deletion:request`. "Ownership implies
  read/update" is prose that no mechanism implements; only the enumerated
  verbs are reachable.
- **The failure mode was a true-sounding comment.** M3 wrote "ownership is not
  lost — it is `LADDER_POLICIES`' `owner_id` rung" and no rung existed. Nothing
  threw, no test covered an owner outside the lab, and the narrowing shipped
  silently. Grep for the rule before writing the comment that says where it
  lives — Critical Rule 70, applied to policies rather than to capabilities.
- **Verify a new guard by breaking it.** Flipping the roster's
  `deletion:request` row to `no` must fail two of the four tests. A guard that
  has never been seen to fail is not known to be a guard.

## Instance-scope grant sync — role assignment that assigns something — 2026-09-01

**What was built:** `sync_instance_grants()`, the Instance-scope twin of M2-B5's
`sync_membership_grants()`, wired into the three sites that assign a role and
issued no grants: `PATCH /users/{id}`, and both halves of `POST /auth/dev-login`.

**Key decisions:**

- **The precedence rule moved into `instance_preset()` and is shared with
  `reseed()`.** `reseed()` read analysts as `is_data_analyst AND NOT
  is_platform_admin`; a live path restating that in a second place would let a
  principal's grants depend on whether a PATCH or a reseed wrote them last.
  One function, two callers, and `reseed()` refactored to a single query so it
  cannot drift.
- **Assertions go through routes, not the grants table.** "Promote a user, then
  have that user do the thing the role names" is what the change is for; the
  grants table is how. The two came apart in the first place because nothing
  was standing at the route end.
- **`sample:update`-style narrowings need a probe that discriminates.** The
  dev-login lab test first probed `GET /labs/{id}/members`, which needs
  `user:manage`; it failed for a Lab Director holding correct grants. Switched
  to `PATCH /labs/{id}` (`org:manage`), held by `lab_lead` and no other lab
  preset, so a 200 means *these* grants landed rather than any grants at all.

**Watch out for:**

- **A write to a decommissioned decision input is worse than a no-op.** Nothing
  has read `users.is_platform_admin` for a decision since M2-B1, so PATCHing it
  returned 200, changed the field, changed nobody's access — and armed the next
  `reseed()` to make it real later, with no signal at the time of the write.
  When a column stops being authoritative, every writer of it becomes a bug.
- **M2-B5 fixed `labs.py` and missed the identical code in `auth.py`.** Same
  membership INSERT, same missing sync, one file over. When wiring a
  cross-cutting call, grep for the *write*, not for the route.
- **`GET /labs/{id}/members` and the three sibling member routes require
  `user:manage` at Lab scope, which no lab preset holds.** So a Lab Lead cannot
  list or manage their own lab's membership — only an instance admin can. Found
  by accident here; not fixed, and not obviously intentional.

## Lab Leads locked out of their own lab's roster — 2026-09-01

**What was built:** `user:manage` added to the `lab_lead` preset, plus reseed
migration `a7f1c30d54b9` and `tests/test_lab_lead_member_management.py`.

**Root cause:** M2 replaced `require_lab_director(user, lab_id)` on the four
`/labs/{id}/members` routes with `require_capability("user:manage")` at Lab
scope. No lab preset held that verb, so the authority moved to instance admins
and nobody noticed. M2-B5 then wired grant issuance into three of those four
routes — correct code behind a door no lab principal could open.

**Key decisions:**

- **Reused `user:manage` rather than minting `lab:manage_members`.** The
  precedent is one entry above it in the same preset: `org:manage` sits in
  `lab_lead` scoped to their lab, with a comment saying the narrower vocabulary
  is tidier and is a later call, "not a reason to leave directors locked out
  now." Identical situation, so the same answer, and a new verb would have
  meant four route changes, a catalog entry and a second preset edit.
- **The safety argument is scope and nothing else.** `PATCH` and `DELETE
  /users/{id}` request `user:manage` with **no scope argument**, which resolves
  to `instance://self`. Containment runs downward, so a `lab://` grant cannot
  reach the root. Because the entire fix rests on that asymmetry, it is pinned
  by two negative tests — including a Lab Lead trying to set their own
  `is_platform_admin` — rather than left to the reader.

**Watch out for:**

- **When a guard changes vocabulary, the holders change with it, and only the
  route's own tests notice — if any test stands where the old holder stood.**
  Second instance in two days, after the `deletion:request` ownership rung.
  Both were verb swaps that silently moved authority; both were invisible
  because the tests that covered the route were written from the new holder's
  seat.
- **A preset edit needs its reseed migration or it reaches nobody**, and this
  one's downgrade must not blanket-delete `user:manage` — instance admins hold
  it at `instance://self` from the cutover, and dropping those rows would leave
  a deployment with no one able to administer users at all. Filtered on
  `scope_ref LIKE '%/lab/%'`.

## M2-DROP-PRE slice 3 — the tenant wall nobody called — 2026-09-01

**What was built:** Nothing. `backend/backend/tenancy.py` was deleted, along with
`tests/routers/test_tenancy.py` and the `TenancyMiddleware` registration in
`main.py`, and three sentences in `access_model.md` that described the module as
enforcing org isolation were corrected to describe what actually does.

The entry planned a conversion: `require_org_access` bypassed the tenant wall on
`is_platform_admin`, and per ADR 0015 that bypass should fall out of scope
containment instead of a flag. The mechanism was right. The premise was not —
`require_org_access` had no production callers. Neither did `get_org_context`.
Nothing in the codebase read the `request.state.org_context` the middleware set
on every non-exempt request, at the cost of one `get_current_user` DB lookup per
request.

**Key decisions:**

- *Deleting beat converting, and the reason is Rule 70 rather than laziness.* A
  correctly-implemented wall with no call site reads as done to every future
  reader and cannot be exercised by any test. The three `is_platform_admin`
  readers it carried were retired at zero conversion cost; 28 of 31 remain.
- *Org isolation was never in danger, because it was never here.* It is
  structural per ADR 0015: grants are rooted at `instance://self/org/N/…` and
  `_scope_contains` matches only at a segment boundary, so a cross-org row is
  refused by default-deny — no grant a tenant holds contains it.
  `visibility_sql_clause` compiles the same relation for the list path. byop.py,
  the entry's "mandatory IDOR case," had already converted to `permits()` under
  M2-B3 and never used `require_org_access` at all.
- *The doc said "DENY policy" and there is no such policy.* §5.4 claimed the
  tenant wall was "a DENY policy keyed on cross-org access; no grant punches
  through it." Both halves were false: `grep` over `authz/policy.py` finds no
  cross-org policy, and an Instance-scoped grant does punch through, by design.
  The bullet now says so, because "absolute" is the kind of word a future reader
  builds on.

**Watch out for:**

- **A module can be wired into `main.py` and still be dead.** Registering the
  middleware made `tenancy.py` look load-bearing from the import graph; only the
  grep for consumers of `request.state.org_context` showed the cargo was never
  picked up. Import-graph reachability is not enforcement.
- **The doc did not lie so much as get written first.** §5.4's sentence and
  `tenancy.py`'s docstring agree with each other perfectly, and both disagree
  with the code. That is what a spec written from the phase plan looks like from
  inside — self-consistent. Third instance recorded under Rule 70.
- **`docs/review_log.md` does not exist** — and the way it stopped existing is
  the finding. It was real: 404 lines at `8cbb993` (Phase 22 review), grown to
  469 by `620a56e` (P0e closeout). It was deleted on 2026-05-08 by `06e67ee`,
  *"Regenerate models_generated.py and jackpot_schema.json from cleaned YAML
  with seed values genericized"* — a 20-file schema-regeneration commit that
  also silently dropped three long-form docs (`review_log.md`,
  `jackpot_cdc_dmi_stlt_overview.md`, `jackpot_template_system_design.md`,
  ~1,955 lines between them). Nothing referenced them differently afterward, so
  the dangling pointers sat for nearly four months while `CLAUDE.md` kept
  instructing every session to write architectural plans into a file that was
  not there.
  Resolved this session by decision: **`learnings.md` is the log; the
  `review_log.md` references are struck.** Eleven live pointers redirected
  (`CLAUDE.md` ×4, `todo.md` ×3, the three `governance/` policy docs,
  `jackpot-init-cli.md`); historical prose in `learnings.md`,
  `jackpot_session_summary_and_backlog.md` and `docs/archived/` left alone,
  because those describe what a past session did and rewriting them would
  falsify the record. Verified before striking that the file's three still-open
  items (action 17 stub routers, action 19 testcontainers DinD, B-FED-1) are
  independently carried by `todo.md:902/913/917`, so nothing was orphaned.
  The general lesson is about the commit, not the file: **a
  regenerate-artifacts commit is exactly where a deletion hides**, because the
  diffstat is expected to be enormous and nobody reads it. Worth a glance at
  `--diff-filter=D` on any commit whose message promises only regeneration.
- **P0c is not deleted, only its scaffolding.** If P0c later wants a
  request-context carrier, note that it duplicates what `get_current_user` plus
  the principal's grant scopes already give every route — that is why this went
  rather than being converted. Rebuilding it is an hour if the need turns out to
  be real.

## M2-DROP-PRE slice 4 — who to tell, asked of the grant table — 2026-09-01

**What was built:** `authz/principal.py::capability_holders(capability, scope)`
— the reverse of `load_principal` — and the conversion of B-CARE-4's
non-compliant-peer alert onto it. That alert was the last LOOKUP-class reader of
`users.is_platform_admin`: a `SELECT id FROM users WHERE is_platform_admin =
TRUE AND is_active = TRUE` used to address a notification.

**Key decisions:**

- *The verb is `federation:configure_peer`, not "the instance-admin preset".*
  The backlog said "principals holding the instance_administrator preset at
  instance scope", which would have hard-coded a preset name into a lookup. The
  question the alert actually asks is "who can do something about this peer",
  and the something is suspension — which writes
  `federated_instances.federation_enabled`, a configure-peer act. Asking for the
  verb means a deployment that grants it outside the preset gets alerted
  correctly, and one that narrows the preset stops alerting people who can no
  longer act.
- *Containment runs one way and the SQL has to say so.* `_scope_contains`
  transcribed is `:scope = scope_ref OR :scope LIKE RTRIM(scope_ref,'/') || '/%'`
  — the GRANT scope contains the RESOURCE scope. Written backwards it would turn
  every lab-scoped grant into instance-wide reach, so both directions are pinned
  by tests, including the `org/1` vs `org/12` segment boundary.
- *Conditional grants are excluded, not assumed satisfied.* A condition is a
  fact about a request; a scheduled job has no request to check one against. The
  engine already answers this — an unset `Context.now` costs a time-bounded
  grant its effect rather than granting it unbounded — so the same discipline
  applies. Refusing here can only shorten a notification list, never widen
  access.
- *It is documented as not a decision function, in the docstring, at length.*
  It reads grants and cannot see DENY policies, so authorizing off it would
  reintroduce the second decision point §2.1 exists to prevent — and it would
  fail open, since a sovereignty DENY is invisible to it. The name says
  "holders", which is exactly the shape someone reaches for when they want a
  quick permission check.

**Watch out for:**

- **A `users` join is the only thing keeping peers out of a list of people.**
  `authz_capability_grants.principal_id` is `TEXT` and holds user ids *and*
  `federated_instances` UUIDs. A holder query that skipped the join would
  eventually hand a UUID to `create_notification` as a `recipient_id`.
- **The test that covered this route asserted on `u.is_platform_admin = TRUE`.**
  It would have kept passing after the column was dropped and the code stopped
  reading it — the assertion joined to `users`, not to the behaviour. Third
  instance in this phase of a test standing on the seat the change is moving.
  The replacement asserts against the grant, and a second test pins the
  narrowing in both directions: a holder *without* the flag is alerted, a
  flag-holder *without* the grant is not. Neither direction is observable
  through the seeded `admin@example.org`, who holds both.
- **An empty holder set is a silent failure**, so it logs. The audit row
  (`FEDERATION_PEER_NONCOMPLIANT`) is written before the alert either way, so
  the record survives a misconfigured deployment; what is lost is the push, and
  nobody notices a notification they never got.

---

## M2-DROP-PRE slices 5–8 — the rest of the readers — 2026-09-02

**What was built:** the remaining four slices of M2-DROP-PRE, retiring every
production *reader* of `users.is_platform_admin` / `users.is_data_analyst`.
The item is now shipped and M2-DROP is unblocked.

**Key decisions:**

- *Slice 5 — reads with no reader.* `guards.get_current_user` and
  `imports.py`'s CSV-import lookup both selected the two columns into a dict
  nothing consumed; the three real consumers each issued their own SELECT.
  Same shape as slice 3: removable at zero conversion cost. The local-dev
  fallback identity also advertised `is_platform_admin: True`, which conferred
  nothing after M2-B1 but made a possibly-grantless `id=1` *read* as an admin —
  the more dangerous half, because a field that looks like a bypass invites
  someone to restore it as one.
- *Slice 6 — the frontend was asking the wrong question, twice.* The plan was
  "`/me` returns held capabilities"; reading the consumers said neither wanted
  one. `access_requests.py` needed **nothing added** — the server has scoped
  that list by `access:approve_request` since M2-B7, and the client-side
  pre-filter was both redundant and wrong: a grant-holding non-director hit an
  early `return` and never issued the request, and a caller who was both admin
  and director fell into the per-lab loop and saw only those labs.
  `pipelines.py` needed a *per-row* answer, because `_may_manage` admits an
  instance grant, a lab grant at `owner_lab_id`, **or** the registrant — which
  no flat capability list expresses. Building the `/me` field would have been a
  third thing neither caller used.
- *Slice 7 — a preset, not a flag pair.* `PATCH /users/{id}` takes
  `instance_preset`. `INSTANCE_PRESETS` is deliberately a **subset** of
  `PRESET_GRANTS`, enforced inside `sync_instance_preset` and not only at the
  route: `lab_lead` is a real preset and an invalid thing to issue at the
  instance root, where its `deletion:approve` and `sample:read_unscrubbed`
  reach every sample on the deployment. A typo'd preset name must not be a
  privilege escalation.
- *Slice 8 — the role name stays, what it assigns changes.* dev-login keeps the
  six APGAP names: Critical Rule 1's sacred values, they name
  `permission_groups` rows, and they are the UAT matrix's vocabulary. None of
  that ends at M2-DROP; the boolean pair they were *stored* as does.

**Watch out for:**

- **A test written against the code it describes proves nothing until it is
  made to fail.** Slice 5's pin used a hand-rolled comment stripper that
  treated the *closing* delimiter of a multi-line SQL literal as a docstring
  opener and silently swallowed the rest of the module — it would not have
  failed, it would have stopped looking. Replaced with `ast.parse`, which
  cannot go blind. Slice 6's page test passed unchanged against pre-slice code
  because `render()` runs at import, so the *other* tab issued the call the
  assertion was standing on. Both were caught by making them red on purpose,
  not by reading them.
- **`extra="forbid"` is the half of a breaking rename that makes it worth
  doing.** Pydantic drops unknown fields, so a stale client sending the old
  body gets a 200 having assigned nothing. The first version of that test
  covered only a body containing *only* the legacy field and so missed the
  worse case: a partly-valid body 200s on the valid part while discarding the
  role.
- **A probe capability cannot detect over-granting.** Slice 8's first test
  probed `sample:read_surveillance` for `surveillance_officer` — the one
  capability it *shares* with `instance_administrator` — so wiring Data Analyst
  to the admin preset would have passed. Assert the set equality the docstring
  claims.
- **Starting from a blank slate only tests the INSERT.** dev-login switches
  identity repeatedly in one UAT run, and the Platform Admin → Lab Director
  switch-down is the only path where `sync_instance_preset`'s DELETE is
  load-bearing. No test covered it until slice 8 added one.
- **`preflight.py`'s reads of the flags are deliberate and must survive
  M2-DROP.** `legacy_ladder` and `legacy_visibility_sql_clause` are the frozen
  pre-M2 oracle the divergence registry compares against, and they build the
  flags from the `Persona` dataclass rather than a DB SELECT. Converting them
  destroys the comparison that makes the registry mean anything.
- **`INSTANCE_PRESETS` is derived from `INSTANCE_PRESET_FLAGS`,** which M2-DROP
  deletes. Inline it as a literal frozenset in the same commit; forgetting
  fails at import, which is the intent.
