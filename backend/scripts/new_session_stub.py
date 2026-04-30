#!/usr/bin/env python3
"""
new_session_stub.py — Generate a blank session stub for manual notes.
Usage: python3 new_session_stub.py >> jackpot_session_summary_and_backlog.md
"""

from datetime import date

today = date.today().isoformat()

stub = f"""
---

# Session N — {today}

## Context

<!-- Brief description of where this session picks up -->

---

## Topics Discussed

### XX. Topic title

<!-- Notes -->

---

## Backlog Updates from This Session

<!-- Any new or changed backlog items -->

---

## Next Steps

<!-- What to do next -->
"""

print(stub)
