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
