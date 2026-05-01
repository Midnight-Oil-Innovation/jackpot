# jackpot-frontend — archived

> **This repository was archived on 2026-04-29 as part of the JACKPOT P0d
> monorepo migration.**
>
> The canonical home for all JACKPOT code, including everything that
> was in this repo, is now:
>
> ## → [`Midnight-Oil-Innovation/jackpot`](https://github.com/Midnight-Oil-Innovation/jackpot) ←
>
> Open new issues, PRs, and discussions on the canonical repo. This
> archived repo's history is preserved here for reference; equivalent
> history is also present in the monorepo via subtree-merge (where
> applicable — see below).

## What happened to the contents of this repo?

**This repo was NOT merged into the monorepo.** The canonical Streamlit researcher UI lives at `backend/frontend/` in the monorepo. This repo was a vestigial stub that never reached parity with the Streamlit implementation in `jackpot-backend/frontend/`, so during P0d it was deliberately not merged.

## What happened to this repo's history?

The full commit history of this repo was preserved during the P0d migration
via `git filter-repo` subtree merges into `Midnight-Oil-Innovation/jackpot`.
Every commit you see in this archived repo's `git log` is also reachable
from the monorepo's `main` branch (with paths rewritten to the new
subdirectory layout described above).

## Migration date

2026-04-29 (P0d phase complete).

## Why?

JACKPOT pivoted to an independent project under
`Midnight-Oil-Innovation` in April 2026 (license flipped Apache 2.0 →
AGPL-3.0, multi-deployment-target architecture introduced). The
six-repo + git-submodule layout was retired in favor of a single
monorepo workspace. See `spec.md §13` and `docs/learnings.md`'s P0d
entry in the canonical repo for the full rationale.
