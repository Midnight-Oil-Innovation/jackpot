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
