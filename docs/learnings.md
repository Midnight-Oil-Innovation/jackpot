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
