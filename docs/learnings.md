# JACKPOT — Implementation Learnings

Auto-maintained by Claude Code. Updated after each router session.
Each entry records what was built, why key decisions were made, and what to watch out for.

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
- `require_platform_admin` gates create/list-all/delete; `require_lab_director` gates PATCH + all member endpoints. GET {id} allows Platform Admin OR any lab member (via `get_user_lab_membership`). This mirrors APGAP's role boundaries exactly.
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
- The seed data in `db/init.sql` includes `asu.edu` and `gmail.com` — the first list test asserts `asu.edu` is present, which works as long as the seed INSERT runs before the Alembic migrations in conftest. Seed INSERTs are at the bottom of `init.sql` and run as part of `conn.execute(text(sql))` before the Alembic step, so this is safe — but any future test that expects an empty whitelist would need to clean up seed entries first.
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
- Spec says the list should show "Sonora Quest, LabCorp, Otero Outpost" but the actual seed only contains `Sonora Quest Laboratories`, `Laboratory Corporation of America`, and `Otero Lab` (as a non-external auto-added entry). The test asserts the first two verbatim — the third is renamed ("Otero Lab" not "Otero Outpost") and the test doesn't pin it. If ingest code ever hardcodes a "Otero Outpost" match, grep will surface the mismatch.
- `DELETE /assign/{lab_id}` 200s on first call and 404s on second — tests exercise both. There is no idempotent mode; callers must cope.
- The `valid_human_sample` test fixture lists `"sequencing_lab": "Otero Outpost"` which does *not* match the seed. That fixture is only used by ingest tests (Session G) and ingest validation is expected to treat it as unknown → 422. Don't try to "fix" the fixture here.

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
  seed email (`gotero@linuxprophet.com`) to exercise the admin branch; the
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
  "Sonora Quest Laboratories" and "Laboratory Corporation of America";
  tests use "Sonora Quest Laboratories" instead of the old fixture's
  "Otero Outpost" (which does not exist in the DB). Using a name that
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
- **Two-tier access model.** `can_see_sample` includes `DISCOVERABLE` (shows in lists); `can_access_sample` excludes it (detail requires an approved `sample_access_requests` row). That is the only way the access-request workflow makes semantic sense — otherwise DISCOVERABLE would collapse into PUBLIC. Spec.md §5 Session H confirms: "Platform Admin → lab member → PUBLIC → ADHS oversight (surveillance_relevant only) → approved request" — no DISCOVERABLE on that ladder. todo.md's test hint conflicted ("DISCOVERABLE → 200 for authenticated users") and was ignored in favour of the spec.
- **Visibility enforced in SQL, not Python.** `visibility_sql_clause(user)` emits an OR'd EXISTS clause straight into the list WHERE, so the list endpoint paginates at the DB tier with no N+1 membership check. Platform Admin short-circuits to `"TRUE"`. Data analysts get `s.surveillance_relevant = TRUE` OR'd in for ADHS oversight.
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
- **`Isolate` source type has no source-specific required fields.** Used it as the happy-path test in validate tests. `Human` requires `adhs_medsis_id`, `biospecimen_type`, `reason_for_collection`, `host_disease` — the naive 7-column CSV that passes BASE_REQUIRED still fails Human's extras. Pick `Isolate` for "should be valid" fixtures.
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
* **Non-admin tests rely on `MOCK_USER_EMAIL` swap.** The seed `gotero@...`
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
- **Credentials to GitHub Actions via WIF, not SA JSON keys.** The bootstrap script creates a Workload Identity Federation pool + OIDC provider scoped to `linuxprophet` repos. GHA exchanges its OIDC token for a short-lived GCP access token — no long-lived keys stored in repo secrets. The workflow's `id-token: write` permission is what authorizes the exchange.
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
- **Deploy workflow checks out `linuxprophet/jackpot-backend` at ref `staging`.** The cross-repo checkout uses the default GITHUB_TOKEN — if that token lacks read access to jackpot-backend, the workflow fails at the second `actions/checkout` step. If the repos are in the same org this works out of the box; otherwise a PAT with `contents:read` on jackpot-backend must be put in repo secrets and swapped in.
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
   `.gitmodules` said `url = /Users/glen/ASU/jackpot/jackpot-nf`.
   Worked on the Mac. Failed everywhere else. `jackpot-nf` hadn't been
   pushed to GitHub at all. Pushed to `gotero/jackpot-nf`, fixed the
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
  (`/Users/glen/ASU/...` instead of `/Users/glen/...`). When
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
