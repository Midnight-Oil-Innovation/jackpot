> **Status:** Reference — redirect stub. This file is no longer the specification.

# JACKPOT — where the spec went

`spec.md` was the project specification through v2.2 (2026-04-29). It was
demoted on 2026-08-28 because it had drifted roughly four months behind the
code: it carried three mutually contradictory test baselines, described
already-shipped phases as future work, and restated the Critical Rules with
enough drift that it instructed agents to do the opposite of Rule 46.

Nothing replaced it wholesale. Its contents went to the places that were
already canonical for each kind of information:

| What you want | Where it lives now |
|---|---|
| What JACKPOT is, and its architecture | `docs/architecture.md` |
| Why a decision was made | `docs/adr/` |
| What a domain term means | `CONTEXT.md` |
| Binding implementation rules | `CLAUDE.md` (Critical Rules) |
| Current facts — versions, counts, migration head | `docs/STATUS.md` |
| What to work on next | `active_backlog.yaml` |
| What has already shipped | `todo.md` |
| Per-phase implementation specs (P0f, P0g, P0h, I-2, C-1) | `docs/archived/spec_v2.2_2026-04-29.md` |

The full original is preserved at
`docs/archived/spec_v2.2_2026-04-29.md`. Read it as history. Every status
claim in it is stale, and several contradict the live Critical Rules — do not
use it to settle a question about how the system behaves today.

## Why this file still exists

Around 155 references to `spec.md` are scattered across docs, tests, and
source comments. This stub keeps them resolving to something truthful instead
of a 404. When a reference is next touched, repoint it at the row above that
actually answers it.
