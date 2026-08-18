# JACKPOT session prompt template

> **Status:** Canonical — source-of-truth template for every session prompt that produces a code commit.

**Canonical structure for every JACKPOT session prompt that produces a code commit.** Referenced by Critical Rule N+5. All future session prompts must follow this template; chat-Claude drafting prompts and Claude Code executing them both treat this as the source of truth.

## Required sections (in order)

1. **Title** (H1) — `# Session prompt: <BACKLOG-ID> — <short description>`
2. **Operating Rules** — Critical Rule references (N pre-action verification, N+1 manual-edits threshold, N+3 stale upload detection, N+5 closing steps), language constraints, commit discipline, gac usage
3. **Role** — one-paragraph framing of what Claude Code is doing this session
4. **Session Task** — concrete deliverables, file structure, code skeletons where appropriate
5. **Acceptance Criteria** — numbered list, must include criteria 13–17 for the push/PR/merge/sync sequence (see below)
6. **Out of Scope** — bullet list, must include the `git worktree remove` exclusion
7. **Closing Steps** — the paste-ready bash block (see canonical block below)
8. **Source-of-truth docs to verify before coding** — bash `view` commands

## Lead-in for the maintainer (outside the prompt body)

Before launching Claude Code, the maintainer runs:

```bash
jackpot-worktree <branch-name>      # creates worktree + cd's into it
claude                              # launches Claude Code in the new cwd
```

The session prompt body assumes Claude Code is already in the worktree. The session-start checklist (Critical Rule N) runs as the first action inside Claude Code.

## Required acceptance criteria (every code-commit session)

In addition to session-specific criteria, every prompt must include these as the final numbered items:

```
13. `git push -u origin <branch>` succeeded
14. `gh pr create` succeeded; PR URL captured in session summary
15. `gh pr merge --squash --delete-branch` succeeded; merge SHA captured in session summary
16. `git -C ~/Projects/operation_jackpot/jackpot fetch --prune` and `git -C ~/Projects/operation_jackpot/jackpot pull --ff-only origin development` succeeded; main checkout HEAD now contains the merge commit
17. Session summary reports: PR URL, merge SHA, main checkout HEAD SHA after sync, and explicit "maintainer next step: run `jackpot-finish <branch>` from outside the session to remove the worktree and delete the local branch"
```

## Required Out of Scope (every code-commit session)

In addition to session-specific exclusions, every prompt must include:

```
- **`git worktree remove` of the current worktree** — git refuses to remove the in-use worktree, and the maintainer's `jackpot-finish` helper handles this from outside
```

## Canonical Closing Steps block (paste-ready)

```bash
# Push the branch to origin
git push -u origin <branch>

# Open the PR (customize title and body per session)
gh pr create --base development \
  --title "<commit-message-style-title>" \
  --body "$(cat <<'EOF'
## Summary

Closes <BACKLOG-ID> in `todo.md` <SECTION-NAME>.

<One-paragraph description of what the PR does and why.>

## What's in the PR

- <file 1> — <description>
- <file 2> — <description>
- <test files> — <description>
- `todo.md` — <checkbox flip description>

## Tests

\`\`\`
pytest <test-target> -v
================ N passed ================
\`\`\`

## Out-of-scope deviation (if applicable)

<Explain any departure from the spec, with justification. Omit this section if no deviation.>

## Related work / next steps

<Cross-references to in-flight or follow-up sessions. Omit if not relevant.>
EOF
)"

# Merge the PR (squash + delete remote branch)
gh pr merge --squash --delete-branch

# Sync the main checkout so it has the merge commit
git -C ~/Projects/operation_jackpot/jackpot fetch --prune
git -C ~/Projects/operation_jackpot/jackpot pull --ff-only origin development
git -C ~/Projects/operation_jackpot/jackpot log --oneline -3
```
> **`gh pr merge --delete-branch` deletes only the remote branch on GitHub (`origin/<branch>`).** The local branch ref is intentionally NOT deleted from inside the session — it's checked out in the current worktree, so git refuses to delete it anyway. The local branch is deleted by `jackpot-finish` after the worktree is removed.

After running the closing steps, the session summary must include:

- **PR URL:** (captured from `gh pr create` output)
- **Merge SHA:** (captured from `gh pr merge` output)
- **Main checkout HEAD after sync:** (captured from `git log --oneline -3` output above)
- **Maintainer next step:** Run `jackpot-finish <branch>` from `~/Projects/operation_jackpot/jackpot` to remove the worktree and delete the local branch

**Do NOT run `git worktree remove` from inside the session.** Git refuses to remove the current worktree, and the maintainer's `jackpot-finish` helper handles this from outside.

## Maintainer-side helpers (in `~/.zshrc`)

These shell functions are prerequisites for the workflow:

- **`jackpot-worktree <branch>`** — creates worktree at `~/Projects/operation_jackpot/jackpot_<branch>` branched from `origin/development`, cd's into it. Maintainer runs this before launching Claude Code.
- **`jackpot-finish <branch>`** — post-Claude-Code cleanup: syncs `development`, removes worktree at `~/Projects/operation_jackpot/jackpot_<branch>`, deletes local branch. Maintainer runs this after the session reports success.

## Sessions exempt from this template

Pure-research, pure-design, or pure-documentation sessions that produce no code commit are exempt from Closing Steps. Such sessions must declare the exemption explicitly in Operating Rules. All other sessions follow this template without exception.
