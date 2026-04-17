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
