## Autonomous Operating Mode

### Before Starting Any Work

1. Read `spec.md` — understand the goals and constraints for the current sprint
2. Read `todo.md` — find the next unchecked task
3. Re-read this file (`docs/CLAUDE.md`) — all 43+ Critical Rules apply at all times
4. Confirm the baseline is stable: `uv run pytest` — ≥275 tests passing, ≥60% coverage

### Work Loop

- Take the **next unchecked item** from `todo.md`
- Cross-check it against `spec.md` before writing code
- Write the code — no placeholders, no `# TODO`, no `# ... rest of code here`
- Run the relevant tests: `uv run pytest tests/test_{module}.py -v`
- If tests pass: check the item off in `todo.md`, commit with `gac`, move to the next item
- If tests fail: fix and rerun — **never mark a task complete without passing tests**
- Every ~20 tasks: pause, review `spec.md` vs the current implementation for gaps,
  log findings to `docs/review_log.md`, and resolve all gaps before continuing

### Decision Rules

- **Never ask for confirmation** on anything resolvable by reading this file and running tests
- **Never lower the coverage threshold** — if a new file pulls coverage below 60%, add tests first
- **Never mark a task done** without `uv run pytest` showing it pass
- **Never write placeholder code** — every function must be fully implemented
- When blocked on intent: check `spec.md`, then the relevant section of this file,
  then log the question to `docs/review_log.md` and continue with the next unblocked task
- For non-trivial architectural changes: write the plan to `docs/review_log.md` and
  wait for explicit "Go" before proceeding

### Commit Convention

Use the `gac` alias for every commit: `gac "type: description"`
Valid types: `feat`, `fix`, `test`, `chore`, `refactor`
Examples: `gac "feat: organizations router — CRUD endpoints + tests"`
          `gac "fix: conftest alembic migration in test DB setup"`

---
