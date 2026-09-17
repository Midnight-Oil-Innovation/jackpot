> **Status:** Reference — ground truth for a reviewer-benchmark case.

# C — exception breadth

**Source:** `git diff 8b68bba..60486c5` (the state reviewed on PR #248 before the fix).

**The defect a reviewer must find:**

The handler catches bare `IntegrityError` and returns 409 "you already have a
pending access request". `sample_access_requests` has three foreign keys
(`sample_id`, `requester_id`, `owner_id`), so an FK violation — a reference to a
row that no longer exists — is reported to the caller as a duplicate. The fix is
to match `exc.orig.diag.constraint_name` against the intended unique index and
re-raise anything else.

**Not the answer, and all four were produced by a model that failed this case:**

- "information exposure via error message details" — the message is a fixed string
- "missing input validation on `payload.justification` / `requested_duration_days`" — Pydantic-validated
- "SQL injection via `(:days || ' days')::INTERVAL`" — `:days` is a **bound parameter**
- "missing transaction management for the rollback" — `db.rollback()` is two lines above

**Why it is a good case:** it separates reviewers that reason about *this schema*
from ones that pattern-match on `except` blocks and SQL strings.
